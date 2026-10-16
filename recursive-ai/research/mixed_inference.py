"""Public-example inference with no task, oracle or evaluator dependencies."""
import math


def infer(examples):
    if not isinstance(examples, (list, tuple)) or not 1 <= len(examples) <= 64:
        raise ValueError('expected 1..64 public examples')
    for row in examples:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or any(type(value) is not int for value in row)
                or not 0 <= row[1] <= row[0] or row[0].bit_length() > 256):
            raise ValueError('invalid public inverse example')
    stages = []
    compatible = []
    for degree in (3, 4):
        fits = []
        for p in range(1, 5):
            for r in range(1, 5):
                for q in range(5):
                    for d in range(1, 5):
                        if math.gcd(math.gcd(p, r), math.gcd(q, d)) != 1 or p+r+q < d:
                            continue
                        if all(p*k**degree+r*k*k+q*k <= d*n < p*(k+1)**degree+r*(k+1)**2+q*(k+1)
                               for n, k in examples):
                            fits.append((p, r, q, d))
        stages.append({'degree': degree, 'raw_hypotheses': 320, 'compatible': len(fits)})
        compatible.extend((degree, rule) for rule in fits)
    if compatible:
        unique = len(compatible) == 1
        return {'status': 'unique' if unique else 'ambiguous',
                'degree': compatible[0][0] if unique else None,
                'rule': compatible[0][1] if unique else None, 'stages': stages}
    return {'status': 'no_fit', 'rule': None, 'degree': None, 'stages': stages}
