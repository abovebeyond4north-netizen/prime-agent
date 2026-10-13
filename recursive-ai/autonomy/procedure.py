"""Bounded public-example procedure discovery; candidates execute in the sandbox."""
import hashlib
import itertools
import math

from autonomy.search import expand_inverse_grammar


def configurations():
    return [dict(zip(('upper', 'direction', 'comparison', 'result'), values))
            for values in itertools.product(('n', 'n + 1'), ('reverse', 'forward'),
                                            ('<', '<='), ('low', 'low - 1'))]


def build_candidate(entrypoint, rule, degree, configuration):
    if (not isinstance(entrypoint, str) or not entrypoint.isidentifier() or entrypoint.startswith('_')
            or not isinstance(rule, (list, tuple)) or len(rule) != 3
            or any(type(v) is not int for v in rule) or type(degree) is not int or not 2 <= degree <= 4
            or configuration not in configurations()):
        raise ValueError('invalid candidate parameters')
    p, q, d = rule
    if not (1 <= p <= 4 and 0 <= q <= 4 and 1 <= d <= 4 and p + q >= d
            and math.gcd(math.gcd(p, q), d) == 1):
        raise ValueError('invalid predicate rule')
    predicate = f'{p} * ' + ' * '.join(['mid'] * degree) + f' + {q} * mid'
    first, second = ('high = mid', 'low = mid + 1') if configuration['direction'] == 'reverse' else ('low = mid + 1', 'high = mid')
    return (f'def {entrypoint}(n):\n    low = 0\n    high = {configuration["upper"]}\n'
            f'    while low < high:\n        mid = (low + high) // 2\n'
            f'        if {predicate} {configuration["comparison"]} {d} * n:\n'
            f'            {first}\n        else:\n            {second}\n'
            f'    return {configuration["result"]}\n')


def discover(runner, entrypoint, examples):
    expansion = expand_inverse_grammar(examples)
    if expansion['status'] != 'unique':
        return {'status': expansion['status'], 'model': None, 'screens': [], 'expansion': expansion}
    inputs = [(n,) for n, _ in examples]
    expected = [k for _, k in examples]
    screens, matches = [], []
    for configuration in configurations():
        source = build_candidate(entrypoint, expansion['rule'], expansion['degree'], configuration)
        error = None
        try:
            result = runner.execute(source, inputs, entrypoint=entrypoint, max_steps=5000)
            passed = result['outputs'] == expected
        except RuntimeError as exception:
            if any(reason in str(exception) for reason in ('budget exhausted', 'operator stop')):
                raise
            passed, error = False, type(exception).__name__
        screens.append({'configuration': configuration, 'passed_public': passed, 'error': error,
                        'source_sha256': hashlib.sha256(source.encode()).hexdigest()})
        if passed:
            matches.append(configuration)
    model = ({'entrypoint': entrypoint, 'rule': expansion['rule'], 'degree': expansion['degree'],
              'configuration': matches[0]} if len(matches) == 1 else None)
    return {'status': 'unique' if model else 'ambiguous' if matches else 'no_fit',
            'model': model, 'screens': screens, 'expansion': expansion}



def propose(runner, task, active):
    cases = task.public()
    examples = [(case[0], value) for case, value in zip(cases, task.expected(cases))]
    expansion = expand_inverse_grammar(examples)
    if expansion['status'] != 'unique':
        raise ValueError('inverse predicate is not uniquely identified')
    for key, skill in sorted(active.items()):
        model = skill.get('procedure_model')
        if model is None:
            continue
        donor = build_candidate(model['entrypoint'], model['rule'], model['degree'], model['configuration'])
        if donor != skill['source']:
            raise ValueError('procedure model does not reconstruct certified source')
        transferred = {'entrypoint': task.family, 'rule': expansion['rule'],
                       'degree': expansion['degree'], 'configuration': dict(model['configuration'])}
        source = build_candidate(**transferred)
        return source, transferred, {'status': 'reused', 'parent_source_sha256': hashlib.sha256(donor.encode()).hexdigest()}
    runner.boot()
    discovery = discover(runner, task.family, examples)
    if discovery['model'] is None:
        raise ValueError('inverse procedure is not uniquely identified')
    return build_candidate(**discovery['model']), discovery['model'], discovery
