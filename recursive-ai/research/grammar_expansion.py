"""Research-only public-driven grammar expansion with a separate bitwise oracle."""
import argparse
import hashlib
import json
import random
import secrets
from dataclasses import dataclass
from pathlib import Path

from autonomy.search import adapt_inverse_scaffold, expand_inverse_grammar, infer_inverse_rule
from autonomy.verifier import TaskVerifier
from sandbox.runner import SandboxRunner


@dataclass(frozen=True)
class PowerTask:
    degree: int
    p: int
    q: int
    d: int

    @property
    def family(self):
        return f'expanded_inverse_{self.degree}_{self.p}_{self.q}_{self.d}'

    @property
    def key(self):
        return 'research:' + self.family

    performance_step_limit = 10000

    def public(self):
        return [(n,) for n in list(range(32)) + [2**j for j in range(32)]]

    def expected(self, cases):
        answers = []
        for (n,) in cases:
            target = self.d * n
            value = 0
            for bit in reversed(range((target.bit_length() + self.degree - 1) // self.degree + 1)):
                candidate = value | (1 << bit)
                if self.p * candidate**self.degree + self.q * candidate <= target:
                    value = candidate
            answers.append(value)
        return answers

    def samples(self, count, seed=None, audit=False):
        rng = random.Random(secrets.randbits(128) if seed is None else seed)
        return [(rng.getrandbits(256 if audit else 32),) for _ in range(count)]

    def properties(self):
        cases = []
        for k in (1, 2, 3, 100, 10**12):
            boundary = (self.p * k**self.degree + self.q * k + self.d - 1) // self.d
            cases.extend([(max(0, boundary - 1),), (boundary,), (boundary + 1,)])
        return cases

    def performance(self):
        return [(2**128 - 1,), (2**256 - 1,), (10**70,)]


def study(parent_source, seed):
    active = {'lower_bound:tier1': {'source': parent_source}}
    rows = []
    for parameters in ((3, 1, 0, 1), (3, 2, 1, 1), (4, 1, 1, 2)):
        task = PowerTask(*parameters)
        cases = task.public()
        labels = [(case[0], answer) for case, answer in zip(cases, task.expected(cases))]
        frozen_rule = infer_inverse_rule(labels)
        expansion = expand_inverse_grammar(labels)
        assert frozen_rule is None
        assert expansion['status'] == 'unique' and expansion['degree'] == task.degree
        assert expansion['rule'] == (task.p, task.q, task.d)
        source = adapt_inverse_scaffold(task.family, active, expansion['rule'], expansion['degree'])
        runner = SandboxRunner()
        report = TaskVerifier(runner).verify(source, task, {})
        assert report['passed']
        evaluator = SandboxRunner()
        evaluator.boot()
        shifted = task.samples(1024, seed=seed, audit=True)
        for offset in range(0, len(shifted), 64):
            batch = shifted[offset:offset + 64]
            result = TaskVerifier(evaluator).check(source, task, batch)
            for (n,), k in zip(batch, result['outputs']):
                assert task.p * k**task.degree + task.q * k <= task.d * n
                assert task.p * (k + 1)**task.degree + task.q * (k + 1) > task.d * n
        rows.append({'parameters': parameters, 'public_examples': labels,
                     'expansion_trace': expansion, 'frozen_quadratic_emits_rule': False,
                     'report': report, 'certification_containers': runner.container_runs,
                     'shifted_cases_passed': len(shifted), 'shifted_containers': evaluator.container_runs,
                     'integer_inequality_postconditions_passed': True,
                     'source': source, 'source_sha256': hashlib.sha256(source.encode()).hexdigest()})
    return {'seed': seed, 'rows': rows, 'automatic_promotion': False,
            'information_boundary': 'Only public input-output pairs enter expansion; no degree or coefficients supplied.',
            'limitations': ['Multiplication production and degree-4/240-raw-hypothesis ceiling are developer-defined.',
                            'Research tasks are not promoted production capabilities.',
                            'Separate bitwise oracle and explicit inequalities; evaluator is developer-controlled.',
                            'Same operator and environment class; finite task distribution.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-source', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.parent_source.read_text(), args.seed)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('GRAMMAR_EXPANSION_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
