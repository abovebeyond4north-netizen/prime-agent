"""Research-only held-out predicates; candidates never execute on the host."""
import argparse
import hashlib
import json
import math
import random
import secrets
from dataclasses import dataclass
from pathlib import Path

from autonomy.search import adapt_inverse_scaffold, infer_inverse_rule
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from sandbox.runner import SandboxRunner


@dataclass(frozen=True)
class RuleTask:
    p: int
    q: int
    d: int

    @property
    def family(self):
        return f'induced_inverse_{self.p}_{self.q}_{self.d}'

    @property
    def key(self):
        return 'research:' + self.family

    performance_step_limit = 10000

    def public(self):
        return [(n,) for n in range(64)]

    def expected(self, cases):
        return [(math.isqrt(self.q * self.q + 4 * self.p * self.d * n) - self.q) // (2 * self.p)
                for (n,) in cases]

    def samples(self, count, seed=None, audit=False):
        rng = random.Random(secrets.randbits(128) if seed is None else seed)
        return [(rng.getrandbits(256 if audit else 32),) for _ in range(count)]

    def properties(self):
        cases = []
        for k in (1, 2, 3, 100, 10**12):
            boundary = (self.p * k * k + self.q * k + self.d - 1) // self.d
            cases.extend([(max(0, boundary - 1),), (boundary,), (boundary + 1,)])
        return cases

    def performance(self):
        return [(2**128 - 1,), (2**256 - 1,), (10**70,)]


def study(parent_source, seed):
    active = {'lower_bound:tier1': {'source': parent_source}}
    rows = []
    for coefficients in ((2, 3, 2), (3, 1, 2), (4, 0, 3)):
        task = RuleTask(*coefficients)
        cases = task.public()
        labels = [(case[0], answer) for case, answer in zip(cases, task.expected(cases))]
        inferred = infer_inverse_rule(labels)
        if inferred != coefficients:
            raise AssertionError('held-out rule not uniquely recovered')
        source = adapt_inverse_scaffold(task.family, active, inferred)
        frozen = adapt_inverse_scaffold(task.family, active, (1, 0, 1))
        reports = {}
        for mode, candidate in [('induced', source), ('frozen_square', frozen)]:
            runner = SandboxRunner()
            reports[mode] = TaskVerifier(runner).verify(candidate, task, {})
            reports[mode]['containers'] = runner.container_runs
        assert reports['induced']['passed'] and not reports['frozen_square']['passed']
        evaluator = SandboxRunner()
        evaluator.boot()
        shifted = task.samples(1024, seed=seed, audit=True)
        for offset in range(0, len(shifted), 64):
            TaskVerifier(evaluator).check(source, task, shifted[offset:offset + 64])
        rows.append({'coefficients': coefficients, 'inferred_from_public_labels': inferred,
                     'public_examples': labels, 'reports': reports,
                     'shifted_cases_passed': len(shifted), 'shifted_containers': evaluator.container_runs,
                     'source': source, 'source_sha256': hashlib.sha256(source.encode()).hexdigest()})
    assert infer_inverse_rule([(0, 0)]) is None
    return {'seed': seed, 'heldout_rules': rows, 'ambiguous_labels_refused': True,
            'donor_source_sha256': hashlib.sha256(parent_source.encode()).hexdigest(),
            'automatic_promotion': False,
            'limitations': ['Finite developer-authored grammar and scaffold, not unrestricted rule invention.',
                            'Research predicates are not registered production task families or promoted checkpoints.',
                            'Public labels supplied by trusted oracle; shifted cases never enter induction.',
                            'Separate closed-form oracle; same operator and environment class.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-source', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.parent_source.read_text(), args.seed)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('INDUCTION_RESULT ' + json.dumps(result, sort_keys=True))
