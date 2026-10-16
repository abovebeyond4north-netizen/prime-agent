"""Bounded public-query acquisition; no protected examples enter selection."""
import math
import random
from collections import Counter
from functools import lru_cache

from research.mixed_inference import infer


def universe():
    return [(degree,p,r,q,d) for degree in (3,4) for p in range(1,5)
            for r in range(1,5) for q in range(5) for d in range(1,5)
            if math.gcd(math.gcd(p,r),math.gcd(q,d)) == 1 and p+r+q >= d]


def compatible(rule, n, k):
    degree,p,r,q,d = rule
    return p*k**degree+r*k*k+q*k <= d*n < p*(k+1)**degree+r*(k+1)**2+q*(k+1)


@lru_cache(maxsize=200000)
def prediction(rule, n):
    degree,p,r,q,d = rule
    low, high = 0, n+1
    while low < high:
        mid = (low+high)//2
        if p*mid**degree+r*mid*mid+q*mid <= d*n:
            low = mid+1
        else:
            high = mid
    return low-1


def pool():
    boundaries = sorted({(p*k**degree+r*k*k+q*k+d-1)//d
                         for degree,p,r,q,d in universe() for k in range(1,17)})
    return sorted(set(range(32)) | {2**j for j in range(32)} |
                  {boundaries[i*(len(boundaries)-1)//127] for i in range(128)})


def acquire(oracle, mode, seed, prediction_budget=200000):
    if mode not in ('fixed','random','active'):
        raise ValueError('unknown query policy')
    candidates, available = universe(), pool()
    fixed = list(range(32))+[2**j for j in range(32)]
    rng = random.Random(seed)
    examples, trace, work = [], [], 0
    for index in range(64):
        if mode == 'fixed':
            n = fixed[index]
        elif index < 16:
            n = index
        else:
            thresholds = {(p*k**degree+r*k*k+q*k+d-1)//d
                          for degree,p,r,q,d in candidates for k in range(1,17)}
            unused = sorted((set(available) | thresholds) - {row[0] for row in examples})
            if mode == 'random':
                n = rng.choice(unused)
            elif len(candidates) <= 1 or work+len(unused)*len(candidates) > prediction_budget:
                n = unused[0]
            else:
                def score(value):
                    counts = Counter(prediction(rule,value) for rule in candidates)
                    return (len(candidates)**2-sum(count*count for count in counts.values()),-value)
                n = max(unused,key=score)
                work += len(unused)*len(candidates)
        k = oracle(n)
        if type(k) is not int or not 0 <= k <= n:
            raise ValueError('invalid public label')
        examples.append((n,k))
        candidates = [rule for rule in candidates if compatible(rule,n,k)]
        trace.append(len(candidates))
    return {'hypothesis':infer(examples), 'examples':examples, 'compatible_counts':trace,
            'label_queries':len(examples), 'prediction_lookups':work,
            'prediction_ceiling':prediction_budget}


def sampled_rules(seed=620016):
    return random.Random(seed).sample(universe(),6)+[(5,1,1,1,1),(3,5,1,1,1)]
