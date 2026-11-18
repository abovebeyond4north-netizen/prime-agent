"""Preserve fixed-example solutions; acquire extra public labels after ambiguity."""
import random

from research.public_queries import acquire, compatible, pool, universe


class PublicOracle:
    def __init__(self, label, limit=128):
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('invalid public query limit')
        self.label, self.limit, self.calls = label, limit, 0

    def __call__(self, n):
        if type(n) is not int or n < 0 or n.bit_length() > 256:
            raise ValueError('invalid public input')
        if self.calls >= self.limit:
            raise RuntimeError('public query budget exhausted')
        self.calls += 1
        k = self.label(n)
        if type(k) is not int or not 0 <= k <= n:
            raise ValueError('invalid public label')
        return k


def acquire_fallback(label, mode, seed):
    if mode not in ('extended_fixed','boundary_fallback'):
        raise ValueError('invalid fallback policy')
    oracle = PublicOracle(label)
    report = acquire(oracle,'fixed',seed)
    baseline = report['hypothesis']
    report.update({'baseline_hypothesis':baseline, 'policy':mode,
                   'label_ceiling':128, 'additional_queries':0})
    if baseline['status'] != 'ambiguous':
        return report
    candidates = [rule for rule in universe()
                  if all(compatible(rule,n,k) for n,k in report['examples'])]
    available, rng = pool(), random.Random(seed)
    original = {n for n,_ in report['examples']}
    extension = [n for n in range(32,160) if n not in original][:64]
    for index in range(64):
        if len(candidates) <= 1:
            break
        if mode == 'extended_fixed':
            n = extension[index]
        else:
            thresholds = {(p*k**degree+r*k*k+q*k+d-1)//d
                          for degree,p,r,q,d in candidates for k in range(1,17)}
            unused = sorted((set(available)|thresholds)-{n for n,_ in report['examples']})
            n = rng.choice(unused)
        k = oracle(n)
        report['examples'].append((n,k))
        candidates = [rule for rule in candidates if compatible(rule,n,k)]
        report['compatible_counts'].append(len(candidates))
    unique = len(candidates) == 1
    report['hypothesis'] = {'status':'unique' if unique else 'ambiguous' if candidates else 'no_fit',
                            'degree':candidates[0][0] if unique else None,
                            'rule':candidates[0][1:] if unique else None,
                            'compatible':len(candidates)}
    report['label_queries'] = oracle.calls
    report['additional_queries'] = oracle.calls-64
    return report
