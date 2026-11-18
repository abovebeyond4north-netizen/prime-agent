"""Internal fresh-task evaluation of removing known redundant inverse edges."""
import json
import time

from research.composition_search import search
from research.composition_validation import coefficients


def study():
    rows = []
    for index, (a, b) in enumerate((a, b) for a in (-256, 256, 512) for b in range(-8, 8)):
        arms = {}
        for prune in ((False, True) if index % 2 else (True, False)):
            start = time.perf_counter_ns()
            result = search([(x, a*x+b) for x in (-3, 1, 4)], 10000,
                            eager=True, prune_inverse=prune)
            elapsed = time.perf_counter_ns()-start
            if result['program'] is not None and coefficients(result['program']) != (a, b):
                raise ValueError('symbolic certification failed')
            arms['pruned' if prune else 'eager'] = {**result, 'elapsed_ns': elapsed}
        rows.append({'target': (a, b), 'arms': arms})
    summary = {name: {'solved': sum(r['arms'][name]['program'] is not None for r in rows),
                      'cost': sum(r['arms'][name]['cost'] for r in rows),
                      'elapsed_ns': sum(r['arms'][name]['elapsed_ns'] for r in rows)}
               for name in ('eager', 'pruned')}
    lost = [r['target'] for r in rows if r['arms']['eager']['program'] is not None
            and r['arms']['pruned']['program'] is None]
    return {'summary': summary, 'lost': lost, 'rows': rows,
            'limits': ['One local timing trial, internally controlled tasks.',
                       'Supplied algebraic identity, not learned invention.',
                       'Defaults unchanged; no production promotion.']}


if __name__ == '__main__':
    print(json.dumps(study(), separators=(',', ':')))
