"""Matched controller continuation and fixed-budget ablation of procedure memory."""
import argparse
import contextlib
import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from autonomy.controller import execute_goal
from autonomy.curriculum import certified
from autonomy.memory import ResearchMemory
from autonomy.procedure import propose
from autonomy.tasks import INVERSE_FAMILIES, Task
from autonomy.verifier import TaskVerifier
from core.rollback import VersionController
from sandbox.runner import SandboxRunner


def rediscover(runner, task, active):
    # The control retains all certified source and evidence; only model lookup is ablated.
    without_models = {key: {name: value for name, value in skill.items() if name != 'procedure_model'}
                      for key, skill in active.items()}
    return propose(runner, task, without_models)


def source_digests(root, checkpoint):
    return {key: hashlib.sha256(skill['source'].encode()).hexdigest()
            for key, skill in certified(VersionController(root).read(checkpoint)).items()}


def acceptance(reuse, rediscovery):
    for arm in (reuse, rediscovery):
        if arm['summary']['status'] != 'goal_reached' or not arm['summary']['audit']['passed']:
            raise ValueError('both matched arms must complete fresh audits')
        if not arm['shifted']['passed']:
            raise ValueError('extra shifted checks failed')
    if reuse['sources'] != rediscovery['sources']:
        raise ValueError('candidate sources differ between matched arms')
    left, right = reuse['summary'], rediscovery['summary']
    if left['session_attempts'] != right['session_attempts']:
        raise ValueError('attempt counts differ')
    saved = right['container_runs'] - left['container_runs']
    if saved <= 0:
        raise ValueError('no measured container saving')
    return {'passed': True, 'containers_saved': saved,
            'continuation_reduction': saved / right['container_runs'], 'same_sources': True,
            'same_attempts': True, 'fresh_audits_passed': True}


def continuation(training, root, mode, max_containers):
    shutil.copytree(training, root)
    override = patch('autonomy.controller.propose_procedure', rediscover) if mode == 'rediscover' else contextlib.nullcontext()
    with override:
        summary = execute_goal(root, description='numeric inverses', tier=2,
                               max_attempts=16, max_model_calls=0, max_containers=max_containers,
                               max_seconds=600, learn_inverse_procedure=True)
    memory = ResearchMemory(root)
    try:
        episodes = [json.loads(raw) for (raw,) in memory.db.execute('SELECT payload FROM events ORDER BY id')]
    finally:
        memory.db.close()
    episodes = [e for e in episodes if e.get('goal_id') == summary['goal_id'] and 'attempt' in e]
    return {'summary': summary, 'sources': source_digests(root, summary['checkpoint']),
            'procedure_events': [e['procedure_evidence'] for e in episodes if e.get('procedure_evidence')]}


def shifted_check(root, checkpoint, seed):
    manifest = certified(VersionController(root).read(checkpoint))
    runner = SandboxRunner()
    runner.boot()
    counts = {}
    for family in INVERSE_FAMILIES:
        task = Task(family, 2)
        cases = task.samples(256, seed=seed, audit=True)
        for offset in range(0, len(cases), 32):
            result = TaskVerifier(runner).check(manifest[task.key]['source'], task, cases[offset:offset + 32])
            for (n,), k in zip(cases[offset:offset + 32], result['outputs']):
                value = k*k if family == 'integer_sqrt' else k*(k+1)//2
                successor = (k+1)*(k+1) if family == 'integer_sqrt' else (k+1)*(k+2)//2
                if not value <= n < successor:
                    raise ValueError('independent integer postcondition failed')
        counts[task.key] = len(cases)
    return {'passed': True, 'cases': counts, 'seed': seed, 'containers': runner.container_runs}


def study(root, seed):
    if root.exists():
        raise ValueError('study state must be a new directory')
    root.mkdir(parents=True)
    training_root = root / 'training'
    training = execute_goal(training_root, description='numeric inverses', tier=1,
                            max_attempts=16, max_model_calls=0, max_seconds=600,
                            learn_inverse_procedure=True)
    if training['status'] != 'goal_reached':
        raise ValueError('training did not complete')
    order = ('reuse', 'rediscover') if seed % 2 else ('rediscover', 'reuse')
    arms = {}
    for mode in order:
        arm_root = root / mode
        arm = continuation(training_root, arm_root, mode, 2000)
        arm['shifted'] = shifted_check(arm_root, arm['summary']['checkpoint'], seed)
        arms[mode] = arm
    result = acceptance(arms['reuse'], arms['rediscover'])
    cap = arms['reuse']['summary']['container_runs']
    capped = {mode: continuation(training_root, root / ('capped-' + mode), mode, cap) for mode in order}
    if capped['reuse']['summary']['status'] != 'goal_reached':
        raise ValueError('reuse failed its observed continuation budget')
    if capped['rediscover']['summary']['status'] == 'goal_reached':
        raise ValueError('fixed-budget ablation did not distinguish capability')
    if capped['rediscover']['summary']['container_runs'] > cap:
        raise ValueError('control exceeded container budget')
    result['fixed_budget'] = cap
    result['fixed_budget_coverage_gain'] = capped['reuse']['summary']['coverage'] - capped['rediscover']['summary']['coverage']
    if result['fixed_budget_coverage_gain'] <= 0:
        raise ValueError('no certified coverage gain at fixed budget')
    return {'seed': seed, 'order': order, 'training': training, 'arms': arms, 'capped': capped,
            'acceptance': result, 'shared_training_containers': training['container_runs'],
            'including_training_reduction': result['containers_saved'] / (training['container_runs'] + arms['rediscover']['summary']['container_runs']),
            'limits': ['Bounded production inverse tasks; no open-world capability claim.',
                       'Three seeds are same-operator, same-environment-class replications.',
                       'Fixed budget selected from first reuse measurement, then replayed from frozen training state.',
                       'Shifted test seeds do not enter procedure selection; evaluator remains developer-controlled.',
                       'Comparison is reuse versus rediscovery, not the supplied-scaffold adapter.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.state, args.seed)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PROCEDURE_REUSE_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
