"""Bounded public experimentation; never consumes protected evaluation feedback."""
from research.boolean_induction import induce


def discover(query, budget=16):
    """Query a public oracle and abstain when word-homogeneity is contradicted.

    The experiment policy and hypothesis class are developer supplied. Passing
    these probes is evidence, not proof of generalization or invention.
    """
    if type(budget) is not int or not 4 <= budget <= 16:
        raise ValueError('budget must be an integer from 4 to 16')
    observations = []

    def observe(a, b, width):
        value = query(a, b, width)
        if type(value) is not int or not 0 <= value < 1 << width:
            raise ValueError('public oracle returned an invalid word')
        observations.append((a, b, width, value))
        return value

    table = {(a, b): observe(a, b, 1) for a in (0, 1) for b in (0, 1)}
    proposal = induce(observations)
    for width in (2, 8, 32):
        mask = (1 << width) - 1
        for a, b in ((0, 0), (mask, 0), (0, mask), (mask, mask)):
            if len(observations) == budget:
                return {'status': 'abstained', 'reason': 'experiment_budget_exhausted',
                        'source': None, 'observations': observations}
            expected = sum(table[(a >> bit) & 1, (b >> bit) & 1] << bit
                           for bit in range(width))
            if observe(a, b, width) != expected:
                return {'status': 'abstained', 'reason': 'hypothesis_contradicted',
                        'source': None, 'observations': observations}
    return {**proposal, 'observations': observations, 'public_labels': len(observations),
            'experiment_policy': 'uniform-word-probes-v1', 'certified': False}
