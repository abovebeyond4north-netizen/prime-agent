"""Opt-in research skill service; never shares production controller state."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from autonomy.curriculum import certified
from autonomy.tasks import suite_digest
from autonomy.verifier import TaskVerifier
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask, construct
from research.oracle_process import acquire_via_process
from sandbox.runner import SandboxRunner

FORMAT = 'contained-public-skill-1'


def adapter_digest():
    root = Path(__file__).resolve().parents[1]
    paths = ('research/skill_contract.py', 'research/mixed_features.py',
             'research/mixed_inference.py', 'research/public_queries.py',
             'research/query_fallback.py', 'research/oracle_process.py',
             'research/grammar_expansion.py', 'autonomy/procedure.py', 'autonomy/curriculum.py',
             'sandbox/runner.py', 'sandbox/Dockerfile', 'sandbox/selector.Dockerfile',
             'core/rollback.py', 'memory/skill_store.py', 'evaluator/verifier.py', 'core/ledger.py')
    components = [(p, hashlib.sha256((root/p).read_bytes()).hexdigest()) for p in paths]
    return hashlib.sha256(json.dumps([suite_digest(), components], sort_keys=True).encode()).hexdigest()


def task_contract(descriptor):
    if not isinstance(descriptor, dict) or set(descriptor) != {'degree', 'p', 'r', 'q', 'd'}:
        raise ValueError('invalid mixed task contract')
    if any(type(v) is not int for v in descriptor.values()):
        raise ValueError('integer task parameters required')
    if (descriptor['degree'] not in (3, 4, 5) or
            any(not 1 <= descriptor[k] <= 5 for k in ('p', 'r')) or
            not 0 <= descriptor['q'] <= 4 or not 1 <= descriptor['d'] <= 4 or
            descriptor['p']+descriptor['r']+descriptor['q'] < descriptor['d']):
        raise ValueError('task contract outside bounded service domain')
    return MixedTask(**descriptor)


@contextmanager
def state_session(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root/'contract.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = root/'contract-format.json'
        if marker.exists():
            if json.loads(marker.read_text()) != FORMAT:
                raise ValueError('wrong contract state format')
        else:
            if any(p.name != 'contract.lock' for p in root.iterdir()):
                raise ValueError('dedicated empty state directory required')
            with marker.open('x') as stream:
                json.dump(FORMAT, stream)
        memory = MemoryEngine(root)
        try:
            yield memory, VersionController(root)
        finally:
            memory.db.close()


def read_skills(versions, checkpoint):
    if checkpoint is None:
        return {}
    manifest = versions.read(checkpoint)
    if (not isinstance(manifest, dict) or set(manifest) != {'format', 'adapter_digest', 'skills'} or
            manifest['format'] != FORMAT or manifest['adapter_digest'] != adapter_digest() or
            not isinstance(manifest['skills'], dict) or not 1 <= len(manifest['skills']) <= 8):
        raise ValueError('unsupported or stale contract checkpoint')
    skills = manifest['skills']
    if set(certified(skills)) != set(skills):
        raise ValueError('checkpoint contains uncertified or stale skills')
    for key, skill in skills.items():
        task = task_contract(skill['descriptor'])
        if (key != task.key or
                hashlib.sha256(skill['source'].encode()).hexdigest() != skill['source_sha256'] or
                construct(task.family, skill['hypothesis'], skill['configuration']) != skill['source']):
            raise ValueError('persisted contract does not reconstruct source')
    return skills


def acquire(root, descriptor, public_label, configuration, *, seed=0, max_containers=128,
            max_seconds=180, image='recursive-ai-runner:local', selector_image='recursive-ai-selector:local'):
    task = task_contract(descriptor)
    if not isinstance(configuration, dict):
        raise ValueError('data-only construction configuration required')
    configuration = dict(configuration)
    # Validate the supplied frozen construction procedure before creating state.
    construct(task.family, {'status': 'unique', 'degree': 3, 'rule': [1, 1, 0, 1]}, configuration)
    if not callable(public_label) or type(seed) is not int:
        raise ValueError('public label callable and integer seed required')
    if type(max_containers) is not int or not 2 <= max_containers <= 128:
        raise ValueError('container budget must be 2..128 including the selector')
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 600:
        raise ValueError('invalid wall budget')
    start = time.monotonic()
    stop_file = Path(root)/'STOP'
    if stop_file.exists():
        raise RuntimeError('operator stop requested')
    with state_session(root) as (memory, versions):
        parent = memory.current()
        active = read_skills(versions, parent)
        if task.key in active:
            if active[task.key]['configuration'] != configuration:
                raise ValueError('existing skill uses a different construction contract')
            return {'status': 'already_certified', 'checkpoint': parent, 'task': task.key,
                    'label_queries': 0, 'containers': 0}
        if len(active) >= 8:
            raise ValueError('contract skill capacity exhausted')
        memory.db.execute('CREATE TABLE IF NOT EXISTS contract_attempts(task TEXT PRIMARY KEY)')
        try:
            memory.db.execute('INSERT INTO contract_attempts VALUES (?)', (task.key,))
        except sqlite3.IntegrityError as error:
            raise ValueError('contract already attempted; protected feedback cannot trigger reacquisition') from error
        label_calls = 0
        def guarded_label(n):
            nonlocal label_calls
            if stop_file.exists() or time.monotonic() >= start+max_seconds:
                raise RuntimeError('operator stop or wall budget reached')
            label_calls += 1
            return public_label(n)
        try:
            selection = acquire_via_process(guarded_label, 'boundary_fallback', seed,
                timeout=min(30, max_seconds), backend='docker', image=selector_image)
            if selection['label_queries'] != label_calls or not 64 <= label_calls <= 128:
                raise ValueError('public acquisition count mismatch')
        except Exception as error:
            memory.event({'status': 'acquisition_failed', 'task': task.key,
                          'error_type': type(error).__name__, 'public_callback_calls': label_calls})
            raise
        result = {'status': 'abstained', 'checkpoint': parent, 'task': task.key,
                  'label_queries': selection['label_queries'], 'containers': 1,
                  'selection': selection, 'configuration_origin': 'caller_supplied'}
        if selection['hypothesis']['status'] != 'unique':
            memory.event(result)
            return result
        source = construct(task.family, selection['hypothesis'], configuration)
        runner = SandboxRunner(image)
        runner.deadline, runner.stop_file = start+max_seconds, stop_file
        runner.max_container_runs = min(20, max_containers-1)
        verifier = TaskVerifier(runner)
        report = verifier.verify(source, task, {})
        result['report'] = report
        result['candidate_containers'] = runner.container_runs
        candidate = {'source': source, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                     'report': report, 'descriptor': asdict(task), 'hypothesis': selection['hypothesis'],
                     'configuration': dict(configuration), 'acquisition': selection}
        if task.key not in certified({task.key: candidate}):
            result.update(status='certification_failed', containers=1+runner.container_runs)
            memory.event(result)
            return result
        runner.max_container_runs = max_containers-1
        retention = {}
        for key, skill in active.items():
            previous = task_contract(skill['descriptor'])
            checked = verifier.verify(skill['source'], previous, {})
            retention[key] = checked
            if key not in certified({key: {'report': checked}}):
                result.update(status='retention_failed', retention=retention, containers=1+runner.container_runs)
                memory.event(result)
                return result
        cases = task.samples(128, seed=seed+1, audit=True)
        try:
            for offset in range(0, len(cases), 32):
                verifier.check(source, task, cases[offset:offset+32])
        except Exception as error:
            result.update(status='audit_failed', retention=retention, error_type=type(error).__name__,
                          containers=1+runner.container_runs)
            memory.event(result)
            return result
        updated = dict(active, **{task.key: candidate})
        manifest = {'format': FORMAT, 'adapter_digest': adapter_digest(), 'skills': updated}
        result.update(status='certified', retention=retention, audit_cases=len(cases),
                      containers=1+runner.container_runs)
        if stop_file.exists() or time.monotonic() >= runner.deadline:
            result['status'] = 'operator_stop_or_wall_budget'
            memory.event(result)
            return result
        memory.db.execute('BEGIN IMMEDIATE')
        try:
            checkpoint = versions.snapshot(manifest, parent)
            if stop_file.exists() or time.monotonic() >= runner.deadline:
                raise RuntimeError('operator stop or wall budget before activation')
            memory.activate(checkpoint)
            result['checkpoint'] = checkpoint
            memory.event(result)
            memory.db.execute('COMMIT')
        except Exception:
            memory.db.execute('ROLLBACK')
            raise
        return result


def invoke(root, key, n, image='recursive-ai-runner:local'):
    if type(n) is not int or not 0 <= n or n.bit_length() > 256:
        raise ValueError('invocation input outside nonnegative 256-bit integers')
    with state_session(root) as (memory, versions):
        checkpoint = memory.current()
        skills = read_skills(versions, checkpoint)
        if key not in skills:
            raise ValueError('skill has no current contract certification')
        skill = skills[key]
        runner = SandboxRunner(image)
        runner.max_container_runs = 2
        runner.boot()
        result = TaskVerifier(runner).check(skill['source'], task_contract(skill['descriptor']), [(n,)])
        return {'checkpoint': checkpoint, 'task': key, 'output': result['outputs'][0],
                'containers': runner.container_runs}


def activate(root, checkpoint):
    with state_session(root) as (memory, versions):
        if memory.db.execute('SELECT 1 FROM checkpoints WHERE sha=?', (checkpoint,)).fetchone() is None:
            raise ValueError('checkpoint was not promoted by this state')
        read_skills(versions, checkpoint)
        memory.db.execute('BEGIN IMMEDIATE')
        try:
            memory.activate(checkpoint)
            memory.event({'contract_checkpoint_activated': checkpoint})
            memory.db.execute('COMMIT')
        except Exception:
            memory.db.execute('ROLLBACK')
            raise
        return {'checkpoint': checkpoint}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('invoke', 'activate'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--key')
    parser.add_argument('--input', type=int)
    parser.add_argument('--checkpoint')
    parser.add_argument('--image', default='recursive-ai-runner:local')
    args = parser.parse_args()
    if args.command == 'invoke':
        result = invoke(args.state, args.key, args.input, args.image)
    else:
        result = activate(args.state, args.checkpoint)
    print(json.dumps(result, sort_keys=True))
