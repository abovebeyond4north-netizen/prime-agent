"""Fresh internal evaluation of early successor recognition, without macro reuse."""
import hashlib
import json
from pathlib import Path
import time

from research.composition_search import search
from research.composition_validation import coefficients

TASKS = tuple((a, b) for a in (-128, -64, 128) for b in range(-12, 12))


def study():
    trials = []
    for trial in range(3):
        rows = []
        for index, (a, b) in enumerate(TASKS):
            arms = {}
            order = (False, True) if (trial+index) % 2 else (True, False)
            for eager in order:
                start = time.perf_counter_ns()
                result = search([(x, a*x+b) for x in (-3, 1, 4)], 10000, eager=eager)
                elapsed = time.perf_counter_ns()-start
                if result['program'] is not None and coefficients(result['program']) != (a, b):
                    raise ValueError('symbolic certification failed')
                arms['eager' if eager else 'baseline'] = {**result, 'elapsed_ns': elapsed}
            rows.append({'target': (a, b), 'arms': arms})
        summary = {name: {'solved': sum(row['arms'][name]['program'] is not None for row in rows),
                          'cost': sum(row['arms'][name]['cost'] for row in rows),
                          'elapsed_ns': sum(row['arms'][name]['elapsed_ns'] for row in rows)}
                   for name in ('baseline', 'eager')}
        lost = [row['target'] for row in rows if row['arms']['baseline']['program'] is not None
                and row['arms']['eager']['program'] is None]
        trials.append({'summary': summary, 'lost_baseline_tasks': lost, 'rows': rows})
    return {'protocol': 'eager-recognition-1', 'trials': trials,
            'source_sha256': hashlib.sha256(Path(__file__).with_name('composition_search.py').read_bytes()).hexdigest(),
            'accepted': all(not t['lost_baseline_tasks'] and
                            t['summary']['eager']['solved'] > t['summary']['baseline']['solved'] and
                            t['summary']['eager']['cost'] < t['summary']['baseline']['cost']
                            for t in trials),
            'limits': ['Internal disjoint task set, not independent external evaluation.',
                       'Same-process timing repetitions, not independent replications.',
                       'Developer-written search correction, not autonomous invention.',
                       'No macro use, production promotion or persistent lifecycle change.']}


if __name__ == '__main__':
    print(json.dumps(study(), separators=(',', ':')))
