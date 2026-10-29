"""Frozen-learner, three-arm internal transfer and end-to-end timing check."""
import hashlib
import json
from pathlib import Path
import time

from research.composition_search import compress, search

TRAINING = ((2, 1), (4, 2), (4, 3), (8, 4), (8, 6), (8, 7))
TASKS = tuple((a, b) for a in (-32, -16, 64) for b in range(-8, 8))
ARMS = ('primitive', 'learned', 'irrelevant')


def coefficients(program):
    """Independent affine certificate for the finite primitive language."""
    a, b = 1, 0
    for token in program:
        if token == 'increment':
            b += 1
        elif token == 'double':
            a, b = 2*a, 2*b
        elif token == 'negate':
            a, b = -a, -b
        else:
            raise ValueError('invalid primitive')
    return a, b


def study():
    trials = []
    for trial in range(3):
        start = time.perf_counter_ns()
        training = [search([(x, a*x+b) for x in (-2, 0, 3)], 100000)
                    for a, b in TRAINING]
        macro = compress([item['program'] for item in training])
        setup_ns = time.perf_counter_ns()-start
        rows = []
        for index, (a, b) in enumerate(TASKS):
            results = {}
            offset = (trial+index) % len(ARMS)
            for arm in ARMS[offset:]+ARMS[:offset]:
                abstraction = {'primitive': None, 'learned': macro,
                               'irrelevant': ('negate', 'negate')}[arm]
                start = time.perf_counter_ns()
                result = search([(x, a*x+b) for x in (-3, 1, 4)], 10000, abstraction)
                elapsed = time.perf_counter_ns()-start
                program = result['program']
                if program is not None and coefficients(program) != (a, b):
                    raise ValueError('independent symbolic certificate failed')
                results[arm] = {**result, 'search_ns': elapsed,
                                'certified_affine': program is not None}
            rows.append({'target': (a, b), 'arms': results})
        summaries = {}
        for arm in ARMS:
            summaries[arm] = {
                'solved': sum(row['arms'][arm]['certified_affine'] for row in rows),
                'primitive_evaluations': sum(row['arms'][arm]['cost'] for row in rows),
                'end_to_end_ns': sum(row['arms'][arm]['search_ns'] for row in rows)
                                + (setup_ns if arm == 'learned' else 0)}
        regressions = [row['target'] for row in rows
                       if row['arms']['primitive']['certified_affine']
                       and not row['arms']['learned']['certified_affine']]
        trials.append({'trial': trial, 'macro': macro, 'setup_ns': setup_ns,
                       'training_cost': sum(item['cost'] for item in training),
                       'summary': summaries, 'lost_baseline_tasks': regressions, 'rows': rows})
    accepted = all(not trial['lost_baseline_tasks'] and
                   trial['summary']['learned']['solved'] >= trial['summary']['primitive']['solved'] and
                   all(trial['summary']['learned']['end_to_end_ns'] < trial['summary'][arm]['end_to_end_ns']
                       for arm in ('primitive', 'irrelevant')) for trial in trials)
    return {'learner_sha256': hashlib.sha256(Path(__file__).with_name('composition_search.py').read_bytes()).hexdigest(),
            'budget_per_task': 10000, 'trials': trials, 'acceptance_passed': accepted,
            'limits': ['Same-operator internal transfer; no externally controlled holdout.',
                       'Three timing repetitions are not independent replications.',
                       'Irrelevant macro is identity: controls overhead, not all alternative abstractions.',
                       'Timings exclude certificate checks and report generation.',
                       'No persistence, promotion, Docker or production integration.']}


if __name__ == '__main__':
    print(json.dumps(study(), indent=2))
