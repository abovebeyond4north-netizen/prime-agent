"""Preregistered matched-wall evaluation of selective composition reuse."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time

from research.composition_contract import learn
from research.composition_lifecycle import FIRST, SECOND
from research.composition_search import PRIMITIVES, run
from research.composition_validation import coefficients
from research.selective_reuse import solve_batch
from research.selective_reuse_study import tasks as previous_tasks

MODES = ('primitive', 'backward_primitive', 'selective')
WALL_BUDGET_NS = 1_500_000_000


def tasks():
    rows = [('baseline_positive', -1, offset) for offset in range(3, 10)]
    rows += [('baseline_positive', 1, offset) for offset in range(9, 12)]
    rows += [('baseline_positive', 2, 20)]
    rows += [('composition_favoring', 2**power, 2**power-1+offset)
             for power in (10, 11) for offset in range(20, 30)]
    excluded = {(a, b) for _, a, b in previous_tasks()} | {(a, b) for _, a, b in rows}
    rng = random.Random(261026481)
    while sum(cohort == 'random_primitive' for cohort, _, _ in rows) < 20:
        program = tuple(rng.choice(PRIMITIVES) for _ in range(rng.randint(18, 30)))
        target = coefficients(program)
        if abs(target[0]) >= 1024 and target not in excluded:
            rows.append(('random_primitive', *target))
            excluded.add(target)
    rows += [('unsupported', 13, 9), ('unsupported', 0, -19), ('unsupported', -3, 11)]
    return rows


def evaluate_arm(root, cohort, mode, wall_budget_ns=WALL_BUDGET_NS):
    if mode not in MODES or type(wall_budget_ns) is not int or wall_budget_ns <= 0:
        raise ValueError('invalid study arm')
    start = time.perf_counter_ns()
    training = []
    if mode == 'selective':
        training = [learn(root, [[(x, a*x+b) for x in (-2, 0, 3)] for a, b in batch])
                    for batch in (FIRST, SECOND)]
        if any(result['status'] != 'stored' for result in training):
            raise ValueError('training library was not stored')
    setup_ns = time.perf_counter_ns()-start
    deadline = start+wall_budget_ns
    outcomes = []
    for name, a, b in cohort:
        if time.perf_counter_ns() >= deadline:
            break
        examples = [[(x, a*x+b) for x in (-5, 2, 7)]]
        result = solve_batch(root if mode == 'selective' else None, examples,
                             mode=mode, budget=10000, planner_states=128)['results'][0]
        program = result['program']
        if program is not None:
            if coefficients(program) != (a, b):
                raise ValueError('symbolic certificate failed')
            for x in (-(2**255-1), -17, 0, 19, 2**255-1):
                if run(program, x) != a*x+b:
                    raise ValueError('large signed-integer audit failed')
        outcomes.append({'cohort': name, 'target': [a, b], 'result': result})
    elapsed_ns = time.perf_counter_ns()-start
    names = sorted({name for name, _, _ in cohort})
    return {
        'mode': mode,
        'wall_budget_ns': wall_budget_ns,
        'setup_ns': setup_ns,
        'elapsed_ns': elapsed_ns,
        'budget_met': elapsed_ns <= wall_budget_ns,
        'completed': len(outcomes) == len(cohort),
        'training_evaluations': sum(item['cost'] for item in training),
        'summary': {
            'evaluated': len(outcomes),
            'solved': sum(item['result']['program'] is not None for item in outcomes),
            'primitive_evaluations': sum(item['result']['cost'] for item in outcomes),
            'planner_states': sum(item['result']['planner_states'] for item in outcomes),
            'planner_edges': sum(item['result']['planner_edges'] for item in outcomes),
        },
        'cohorts': {name: {
            'evaluated': sum(item['cohort'] == name for item in outcomes),
            'solved': sum(item['cohort'] == name and item['result']['program'] is not None
                          for item in outcomes),
        } for name in names},
        'outcomes': outcomes,
    }


def study(root):
    root = Path(root)
    if root.exists():
        raise ValueError('study root must be new')
    root.mkdir(parents=True)
    cohort = tasks()
    trials = []
    for trial in range(3):
        arms = {}
        order = MODES[trial:]+MODES[:trial]
        for mode in order:
            arms[mode] = evaluate_arm(root/f'trial-{trial}-{mode}', cohort, mode)
        baseline = {tuple(item['target']) for item in arms['primitive']['outcomes']
                    if item['result']['program'] is not None}
        lost = {mode: sorted(baseline-{tuple(item['target']) for item in arms[mode]['outcomes']
                                      if item['result']['program'] is not None})
                for mode in MODES if mode != 'primitive'}
        trials.append({'trial': trial, 'order': order, 'arms': arms,
                       'lost_baseline_successes': lost})
    accepted = all(
        all(arm['budget_met'] and arm['completed'] for arm in trial['arms'].values()) and
        trial['arms']['primitive']['cohorts']['baseline_positive']['solved'] > 0 and
        not trial['lost_baseline_successes']['selective'] and
        trial['arms']['selective']['summary']['solved'] >
        trial['arms']['primitive']['summary']['solved']
        for trial in trials)
    memory_attribution = accepted and all(
        trial['arms']['selective']['summary']['solved'] >
        trial['arms']['backward_primitive']['summary']['solved'] for trial in trials)
    return {
        'protocol': 'selective-reuse-matched-wall-1',
        'code_commit': os.environ.get('GITHUB_SHA'),
        'policy_sha256': hashlib.sha256(
            Path(__file__).with_name('selective_reuse.py').read_bytes()).hexdigest(),
        'evaluator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'tasks': cohort,
        'wall_budget_ns': WALL_BUDGET_NS,
        'trials': trials,
        'acceptance_passed': accepted,
        'memory_attribution_supported': memory_attribution,
        'limits': [
            'Developer-controlled internal affine tasks; not an independent external distribution.',
            'A wall deadline is checked between bounded tasks, not by preempting a task in flight.',
            'Three timing repetitions on one runner are not independent replications.',
            'Supplied affine model and planner; no autonomous primitive invention or promotion.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.state)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    summary = {key: result[key] for key in ('protocol', 'code_commit', 'policy_sha256',
               'evaluator_sha256', 'wall_budget_ns', 'acceptance_passed',
               'memory_attribution_supported', 'limits')}
    summary['trials'] = [{'trial': trial['trial'], 'order': trial['order'],
                          'lost_baseline_successes': trial['lost_baseline_successes'],
                          'arms': {mode: {key: arm[key] for key in
                                   ('setup_ns', 'elapsed_ns', 'budget_met', 'completed',
                                    'training_evaluations', 'summary', 'cohorts')}
                                   for mode, arm in trial['arms'].items()}}
                         for trial in result['trials']]
    print('SELECTIVE_REUSE_WALL_RESULT '+json.dumps(summary, sort_keys=True), flush=True)
