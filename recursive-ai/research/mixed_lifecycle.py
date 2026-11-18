"""Research-only matched scaffold and fresh-process checkpoint replay study."""
import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from autonomy.procedure import propose
from autonomy.search import BOUND, expand_inverse_grammar, normalized_digest
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask, construct, infer
from sandbox.runner import SandboxRunner

PARAMETERS = ((3, 2, 1, 0, 1), (3, 2, 1, 0, 2), (4, 2, 1, 4, 3))
SUPPLIED = {'upper':'n + 1','direction':'forward','comparison':'<=','result':'low - 1'}


def record(task, source, report, hypothesis=None, configuration=None):
    return {'source':source, 'report':report,
            'descriptor':asdict(task) if isinstance(task, MixedTask) else {'family':task.family},
            'mixed':isinstance(task, MixedTask), 'hypothesis':hypothesis, 'configuration':configuration}


def replay(root, seed):
    memory = MemoryEngine(root)
    try:
        checkpoint = memory.current()
    finally:
        memory.db.close()
    manifest = VersionController(root).read(checkpoint)
    runner = SandboxRunner()
    runner.max_container_runs = 20
    runner.boot()
    outputs = {}
    for key, skill in sorted(manifest.items()):
        task = MixedTask(**skill['descriptor']) if skill['mixed'] else Task(**skill['descriptor'])
        if skill['mixed']:
            if construct(task.family, skill['hypothesis'], skill['configuration']) != skill['source']:
                raise ValueError('persisted model does not reconstruct source')
        cases = task.samples(64, seed=seed, audit=True)
        result = TaskVerifier(runner).check(skill['source'], task, cases)
        if skill['mixed']:
            for (n,), k in zip(cases, result['outputs']):
                assert task.value(k) <= task.d*n < task.value(k+1)
        outputs[key] = hashlib.sha256(json.dumps(result['outputs']).encode()).hexdigest()
    return {'checkpoint':checkpoint, 'containers':runner.container_runs,
            'outputs':outputs, 'cases':64*len(manifest), 'fresh_process':True}


def fresh_replay(root, seed):
    result = subprocess.run([sys.executable, '-m', 'research.mixed_lifecycle',
                             '--replay', str(root), '--seed', str(seed)],
                            capture_output=True, text=True, timeout=180, check=True)
    return json.loads(result.stdout)


def study(root, seed):
    if root.exists():
        raise ValueError('study requires a new state directory')
    root.mkdir(parents=True)
    runner = SandboxRunner()
    donor, training = Task('lower_bound'), Task('integer_sqrt')
    donor_report = TaskVerifier(runner).verify(BOUND, donor, {})
    assert donor_report['passed']
    active = {donor.key:record(donor, BOUND, donor_report)}
    source, model, discovery = propose(runner, training, active)
    training_report = TaskVerifier(runner).verify(source, training, active)
    assert training_report['passed']
    active[training.key] = record(training, source, training_report)
    frozen = dict(model['configuration'])
    order = ('learned', 'supplied') if seed % 2 else ('supplied', 'learned')
    arms = {}
    for mode in order:
        state = root / mode
        memory, versions = MemoryEngine(state), VersionController(state)
        base = versions.snapshot(active)
        memory.activate(base)
        manifest = dict(active)
        rows = []
        for degree,p,r,q,d in PARAMETERS:
            task = MixedTask(degree=degree,p=p,r=r,q=q,d=d)
            public = task.public()
            examples = [(case[0], value) for case,value in zip(public,task.expected(public))]
            old, hypothesis = expand_inverse_grammar(examples), infer(examples)
            assert old['status'] == 'expansion_budget_exhausted'
            assert hypothesis['status'] == 'unique'
            configuration = frozen if mode == 'learned' else SUPPLIED
            candidate = construct(task.family, hypothesis, configuration)
            evaluation = SandboxRunner()
            evaluation.max_container_runs = 40
            report = TaskVerifier(evaluation).verify(candidate, task, active)
            assert report['passed'], report
            cases = task.samples(512, seed=seed, audit=True)
            for offset in range(0,len(cases),32):
                batch = cases[offset:offset+32]
                result = TaskVerifier(evaluation).check(candidate, task, batch)
                for (n,), k in zip(batch,result['outputs']):
                    assert task.value(k) <= task.d*n < task.value(k+1)
            manifest[task.key] = record(task,candidate,report,hypothesis,configuration)
            rows.append({'parameters':[degree,p,r,q,d], 'report':report,
                         'containers':evaluation.container_runs, 'shifted_cases':len(cases),
                         'normalized_source':normalized_digest(candidate), 'frozen_status':old['status']})
        extended = versions.snapshot(manifest, parent=base)
        memory.activate(extended)
        memory.db.close()
        first = fresh_replay(state, seed+1000)
        assert first['checkpoint'] == extended
        memory = MemoryEngine(state)
        memory.activate(base)
        memory.db.close()
        rolled_back = fresh_replay(state, seed+1000)
        assert rolled_back['checkpoint'] == base
        assert set(rolled_back['outputs']) == set(active)
        assert all(first['outputs'][key] == value for key,value in rolled_back['outputs'].items())
        memory = MemoryEngine(state)
        memory.activate(extended)
        memory.db.close()
        restored = fresh_replay(state, seed+1000)
        assert restored['checkpoint'] == extended and restored['outputs'] == first['outputs']
        retention = SandboxRunner()
        retention.max_container_runs = 40
        retained = []
        for task in (donor,training):
            report = TaskVerifier(retention).verify(manifest[task.key]['source'],task,{})
            assert report['passed']
            retained.append(report)
        arms[mode] = {'rows':rows, 'base':base, 'extended':extended,
                      'restart':first, 'rollback':rolled_back, 'restored':restored,
                      'retention':retained, 'retention_containers':retention.container_runs,
                      'lifecycle_containers':sum(x['containers'] for x in (first,rolled_back,restored))}
    for left,right in zip(arms['learned']['rows'],arms['supplied']['rows']):
        assert left['parameters'] == right['parameters']
        assert left['normalized_source'] == right['normalized_source']
        assert left['containers'] == right['containers']
    return {'seed':seed, 'order':order, 'arms':arms, 'training_containers':runner.container_runs,
            'discovery':discovery, 'frozen_configuration':frozen, 'receiving_arm_budget':40,
            'outcome':'matched_scaffold_tie', 'production_promotion':False,
            'limits':['Developer-defined grammar and public-identifiable diagnostic fixtures.',
                      'Git/SQLite replay uses research manifests, not autonomous production integration.',
                      'Rollback is an explicit checkpoint switch, not recovery from real-world distribution shift.',
                      'Supplied arm needs no procedure acquisition; shared training cost is not an advantage.',
                      'Same operator/environment class; no independent external evaluation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--state',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--replay',type=Path)
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(args.replay,args.seed)))
    else:
        if args.state is None or args.output is None:
            parser.error('--state and --output required')
        result = study(args.state,args.seed)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print('MIXED_LIFECYCLE_RESULT '+json.dumps(result,sort_keys=True),flush=True)
