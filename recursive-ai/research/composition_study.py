"""Internal development sweep, not a preregistered or external holdout."""
import json

from research.composition_search import compress, run, search


def study():
    training = []
    for a, b in ((2, 1), (4, 2), (4, 3), (8, 4), (8, 6), (8, 7)):
        result = search([(x, a*x+b) for x in (-2, 0, 3)], 100000)
        training.append(result)
    macro = compress([row['program'] for row in training])
    rows = []
    # Complete offset sweep avoids reporting only macro-friendly examples.
    for a in (16, 32):
        for b in range(32):
            arms = {}
            for name, abstraction in (('primitive', None), ('learned', macro)):
                result = search([(x, a*x+b) for x in (-3, 1, 4)], 10000, abstraction)
                if result['program'] is not None:
                    assert all(run(result['program'], x) == a*x+b for x in range(-100, 101))
                arms[name] = result
            rows.append({'a': a, 'b': b, 'arms': arms})
    summary = {name: {'solved': sum(row['arms'][name]['program'] is not None for row in rows),
                      'primitive_evaluations': sum(row['arms'][name]['cost'] for row in rows)}
               for name in ('primitive', 'learned')}
    return {'training_cost': sum(row['cost'] for row in training), 'macro': macro,
            'summary': summary, 'rows': rows, 'audit_inputs_per_solved_task': 201,
            'limits': ['Developer-supplied primitives and compression/search algorithms.',
                       'Internal development tasks; not protected or independent evaluation.',
                       'Costs count primitive evaluations, not compression, queue work or wall time.',
                       'No generated Python execution, persistence, promotion or production change.']}


if __name__ == '__main__':
    print(json.dumps(study(), indent=2))
