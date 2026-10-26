"""Frozen direct/controller parity test and no-reuse ablation; not external transfer."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from functools import lru_cache

from autonomy.controller import acquire_skill_contract
from core.rollback import VersionController
from research.fallback_study import rule_partition as fallback_partition
from research.public_queries import sampled_rules, universe
from research.query_scale import rule_partition as scale_partition
from research.skill_contract import acquire, task_contract

CONFIG = {'upper': 'n + 1', 'direction': 'forward', 'comparison': '<=', 'result': 'low - 1'}
SEED = 1030026
ARMS = ('direct', 'controller', 'no_reuse')
FIELDS = ('degree', 'p', 'r', 'q', 'd')


@lru_cache(maxsize=1)
def prior_rules():
    excluded = set(sampled_rules(620016) + sampled_rules(620017))
    for shard in range(4):
        excluded.update(scale_partition(shard))
        excluded.update(fallback_partition(shard))
    excluded.update(((3, 1, 1, 0, 1), (3, 1, 1, 1, 2), (4, 1, 1, 2, 3),
                     (3, 2, 1, 0, 1), (3, 2, 1, 0, 2), (4, 2, 1, 4, 3),
                     (4, 3, 3, 0, 1), (3, 4, 3, 1, 2)))
    return frozenset(excluded)


def rules(shard):
    if type(shard) is not int or shard not in (0, 1):
        raise ValueError('shard must be 0 or 1')
    population = [rule for rule in universe() if rule not in prior_rules()]
    heldout = random.Random(SEED).sample(population, 6)
    return heldout[shard*3:shard*3+3] + [(5, 1, 1, 1, 1)]


def signature(result, state):
    value = {key: result.get(key) for key in
             ('status', 'label_queries', 'containers', 'candidate_containers', 'audit_cases', 'selection')}
    report = result.get('report', {})
    value['gates'] = report.get('gates')
    value['source_sha256'] = None
    if result['status'] == 'certified':
        manifest = VersionController(state).read(result['checkpoint'])
        value['source_sha256'] = manifest['skills'][result['task']]['source_sha256']
    return value


def replay(state, task, image, controller):
    n = 2**255 - 1
    if controller:
        command = [sys.executable, 'main.py', 'contract-invoke', '--contract-state', str(state),
                   '--contract-key', task.key, '--contract-input', str(n), '--image', image]
    else:
        command = [sys.executable, '-m', 'research.skill_contract', 'invoke', '--state', str(state),
                   '--key', task.key, '--input', str(n), '--image', image]
    run = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
    result = json.loads(run.stdout)
    k = result['output']
    if type(k) is not int or not task.value(k) <= task.d*n < task.value(k+1):
        raise ValueError('replay failed exact integer postcondition')
    return result


def study(root, shard):
    root = Path(root)
    if root.exists():
        raise ValueError('comparison requires new state root')
    root.mkdir(parents=True)
    image = os.environ.get('CONTRACT_RUNNER_IMAGE', 'recursive-ai-runner:local')
    selector_image = os.environ.get('RECURSIVE_SELECTOR_IMAGE', 'recursive-ai-selector:local')
    rows = []
    for index, parameters in enumerate(rules(shard)):
        descriptor = dict(zip(FIELDS, parameters))
        task = task_contract(descriptor)
        row = {'parameters': parameters, 'arms': {}}
        offset = (shard*3+index) % len(ARMS)
        order = ARMS[offset:] + ARMS[:offset]
        row['order'] = order
        for arm in order:
            state = root / f'{index}-{arm}'
            function = acquire if arm == 'direct' else acquire_skill_contract
            calls = 0
            def label(n):
                nonlocal calls
                calls += 1
                return task.expected([(n,)])[0]
            options = dict(seed=SEED+shard*100+index, max_containers=128, max_seconds=180,
                           image=image, selector_image=selector_image)
            start = time.monotonic()
            initial = function(state, descriptor, label, CONFIG, **options)
            elapsed = time.monotonic()-start
            if calls != initial['label_queries'] or calls > 128:
                raise ValueError('observed callback count exceeds or disagrees with report')
            data = {'initial': initial, 'callback_calls': calls, 'wall_seconds': elapsed,
                    'signature': signature(initial, state)}
            if initial['status'] == 'certified':
                data['restart'] = replay(state, task, image, arm != 'direct')
                before = calls
                repeat_state = root / f'{index}-{arm}-fresh' if arm == 'no_reuse' else state
                repeated = function(repeat_state, descriptor, label, CONFIG, **options)
                data.update(repeated=repeated, repeated_callback_calls=calls-before)
                expected_status = 'certified' if arm == 'no_reuse' else 'already_certified'
                if repeated['status'] != expected_status:
                    raise ValueError('unexpected repeat acquisition result')
                if arm != 'no_reuse' and (calls != before or repeated['containers'] != 0):
                    raise ValueError('cached repeat consumed labels or containers')
                if arm == 'no_reuse' and signature(repeated, repeat_state) != data['signature']:
                    raise ValueError('fresh-state ablation changed acquisition semantics')
                data['repeat_restart'] = replay(repeat_state, task, image, arm != 'direct')
                if data['repeat_restart']['output'] != data['restart']['output']:
                    raise ValueError('repeat changed exact output')
            row['arms'][arm] = data
        signatures = [row['arms'][arm]['signature'] for arm in ARMS]
        if any(value != signatures[0] for value in signatures[1:]):
            raise ValueError('interface altered acquisition/certification/source/cost')
        if parameters[0] == 5 and any(x['initial']['status'] == 'certified' for x in row['arms'].values()):
            raise ValueError('out-of-grammar control certified')
        rows.append(row)
    summary = {}
    for arm in ARMS:
        data = [row['arms'][arm] for row in rows]
        summary[arm] = {
            'certified': sum(x['initial']['status'] == 'certified' for x in data),
            'initial_labels': sum(x['callback_calls'] for x in data),
            'initial_containers': sum(x['initial']['containers'] for x in data),
            'repeat_labels': sum(x.get('repeated_callback_calls', 0) for x in data),
            'repeat_containers': sum(x.get('repeated', {}).get('containers', 0) for x in data),
            'replay_containers': sum(x.get(k, {}).get('containers', 0)
                                     for x in data for k in ('restart', 'repeat_restart')),
            'initial_wall_seconds': sum(x['wall_seconds'] for x in data),
        }
    return {'protocol': 'contract-comparison-1', 'sampling_seed': SEED, 'shard': shard,
            'adapter_commit': os.environ.get('GITHUB_SHA'), 'rows': rows, 'summary': summary,
            'runner_image': image, 'selector_image': selector_image,
            'configuration': CONFIG, 'parity': True, 'capability_gain_established': False,
            'limits': ['Six unfiltered new internal rules plus a repeated degree-5 negative control.',
                       'Same finite grammar, trusted provider and internally controlled evaluator.',
                       'No-reuse ablation deliberately omits persistent state; repeated work is not a new algorithm gain.',
                       'Wall times include host orchestration and are descriptive, not a statistical speed claim.',
                       'Fresh per-task states isolate caching; cross-task retention is tested separately.',
                       'No independent operator replication or external-domain transfer.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--shard', type=int, required=True)
    args = parser.parse_args()
    result = study(args.state, args.shard)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('CONTRACT_COMPARISON_RESULT '+json.dumps(result, sort_keys=True), flush=True)
