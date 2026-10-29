"""Frozen internal evaluation of selective reuse and a primitive-planning ablation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import time

from research.composition_contract import learn
from research.composition_lifecycle import FIRST, SECOND
from research.composition_search import PRIMITIVES, run
from research.composition_validation import coefficients
from research.selective_reuse import MODES, solve_batch


def tasks():
    rows = [('composition_favoring', 2**power, 2**power-1+offset)
            for power in (10, 11, 12) for offset in range(10)]
    seen = {(a, b) for _, a, b in rows}
    rng = random.Random(261026171)
    generated = 0
    for _ in range(20000):
        program = tuple(rng.choice(PRIMITIVES) for _ in range(rng.randint(18, 30)))
        a, b = coefficients(program)
        if abs(a) < 1024 or (a, b) in seen:
            continue
        rows.append(('random_primitive', a, b))
        seen.add((a, b))
        generated += 1
        if generated == 60:
            break
    if generated != 60:
        raise ValueError('fixed task generator did not produce enough distinct functions')
    rows.extend([('unsupported', a, b) for a, b in ((7, 5), (11, -7), (0, 17))])
    return rows


def study(root):
    root = Path(root)
    if root.exists():
        raise ValueError('study root must be new')
    root.mkdir(parents=True)
    cohort = tasks()
    examples = [[(x, a*x+b) for x in (-5, 2, 7)] for _, a, b in cohort]
    trials = []
    for trial in range(3):
        state = root/f'trial-{trial}'
        start = time.perf_counter_ns()
        training = [learn(state, [[(x, a*x+b) for x in (-2, 0, 3)] for a, b in batch])
                    for batch in (FIRST, SECOND)]
        setup_ns = time.perf_counter_ns()-start
        if any(result['status'] != 'stored' for result in training):
            raise ValueError('training library was not stored')
        arms = {}
        order = MODES[trial:]+MODES[:trial]
        for mode in order:
            start = time.perf_counter_ns()
            batch = solve_batch(state, examples, mode=mode, budget=10000, planner_states=128)
            elapsed = time.perf_counter_ns()-start
            for (_, a, b), result in zip(cohort, batch['results']):
                program = result['program']
                if program is not None:
                    if coefficients(program) != (a, b):
                        raise ValueError('independent symbolic certificate failed')
                    for x in (-(2**255-1), -17, 0, 19, 2**255-1):
                        if run(program, x) != a*x+b:
                            raise ValueError('large signed-integer audit failed')
                if result['cost'] > 10000 or result['planner_states'] > 128:
                    raise ValueError('resource cap exceeded')
            def summary(indices):
                return {'solved': sum(batch['results'][i]['program'] is not None for i in indices),
                        'primitive_evaluations': sum(batch['results'][i]['cost'] for i in indices),
                        'planner_states': sum(batch['results'][i]['planner_states'] for i in indices),
                        'planner_edges': sum(batch['results'][i]['planner_edges'] for i in indices)}
            arms[mode] = {'checkpoint': batch['checkpoint'], 'summary': summary(range(len(cohort))),
                          'cohorts': {name: summary([i for i, (c, _, _) in enumerate(cohort) if c == name])
                                      for name in sorted({c for c, _, _ in cohort})},
                          'search_and_load_ns': elapsed,
                          'end_to_end_ns': elapsed+(setup_ns if mode in ('selective', 'unconditional') else 0),
                          'results': batch['results']}
        lost = {mode: [cohort[i][1:] for i, result in enumerate(arms['primitive']['results'])
                       if result['program'] is not None and arms[mode]['results'][i]['program'] is None]
                for mode in MODES if mode != 'primitive'}
        trials.append({'trial': trial, 'order': order, 'setup_ns': setup_ns,
                       'training_evaluations': sum(item['cost'] for item in training),
                       'arms': arms, 'lost_forward_successes': lost})
    medians = {mode: statistics.median(t['arms'][mode]['end_to_end_ns'] for t in trials) for mode in MODES}
    accepted = all(not t['lost_forward_successes']['selective'] and
                   t['arms']['selective']['summary']['solved'] > t['arms']['primitive']['summary']['solved']
                   for t in trials) and medians['selective'] <= 0.9*medians['primitive']
    memory_attribution = (accepted and all(t['arms']['selective']['summary']['solved'] >
                                          t['arms']['backward_primitive']['summary']['solved'] for t in trials)
                          and medians['selective'] < medians['backward_primitive'])
    return {'protocol': 'selective-reuse-1', 'code_commit': os.environ.get('GITHUB_SHA'),
            'policy_sha256': hashlib.sha256(Path(__file__).with_name('selective_reuse.py').read_bytes()).hexdigest(),
            'tasks': cohort, 'trials': trials, 'median_end_to_end_ns': medians,
            'acceptance_passed': accepted, 'memory_attribution_supported': memory_attribution,
            'limits': ['Internally generated, explicitly composition-favoring and random cohorts; not external holdout.',
                       'Three timing repetitions on the same tasks are not independent replications.',
                       'Separate caps: 10000 primitive evaluations and 128 planner states; not equal wall deadlines.',
                       'Wall times include library training, compression, Git/SQLite storage/load and routing for memory arms.',
                       'Training state is shared physically but charged in full to each memory-arm counterfactual.',
                       'Timing excludes common task generation and post-result certificates/audits.',
                       'Supplied affine model and planner; no autonomous primitive invention or production promotion.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.state)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    summary = {key: result[key] for key in ('protocol', 'code_commit', 'policy_sha256',
               'median_end_to_end_ns', 'acceptance_passed', 'memory_attribution_supported', 'limits')}
    summary['trials'] = [{'trial': t['trial'], 'training_evaluations': t['training_evaluations'],
                         'lost_forward_successes': t['lost_forward_successes'],
                         'arms': {mode: {key: arm[key] for key in ('summary', 'cohorts', 'end_to_end_ns')}
                                  for mode, arm in t['arms'].items()}} for t in result['trials']]
    print('SELECTIVE_REUSE_RESULT '+json.dumps(summary, sort_keys=True), flush=True)
