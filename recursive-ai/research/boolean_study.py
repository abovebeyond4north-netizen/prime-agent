"""Fixed one-bit to word transfer experiment; no protected feedback reaches induction."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import secrets

from autonomy.verifier import TaskVerifier
from research.boolean_induction import MODES, induce
from sandbox.runner import SandboxRunner

DEVELOPMENT = (6, 8)
HOLDOUT = tuple(value for value in range(16) if value not in DEVELOPMENT)


@dataclass(frozen=True)
class BooleanTask:
    truth: int
    family = 'bit_transform'
    performance_step_limit = 200

    @property
    def key(self):
        return f'research:boolean-word:{self.truth}'

    def public(self):
        return [(a, b, 1) for a in (0, 1) for b in (0, 1)]

    def expected(self, cases):
        outputs = []
        for a, b, width in cases:
            result = 0
            for bit in range(width):
                index = 2*((a >> bit) & 1) + ((b >> bit) & 1)
                if (self.truth >> index) & 1:
                    result |= 1 << bit
            outputs.append(result)
        return outputs

    def samples(self, count, seed=None, audit=False):
        rng = random.Random(secrets.randbits(128) if seed is None else seed)
        cases = []
        widths = (2, 3, 8, 16, 32, 64, 128, 256) if audit else (2, 3, 4, 8, 16, 32)
        for _ in range(count):
            width = rng.choice(widths)
            cases.append((rng.getrandbits(width+2), rng.getrandbits(width+2), width))
        return cases

    def properties(self):
        return [(a, b, width) for width in (2, 8, 64, 256)
                for a, b in ((0, 0), (0, (1 << width)-1), ((1 << width)-1, 0),
                             ((1 << width)-1, (1 << width)-1), (1 << width, (1 << (width+1))-1))]

    def performance(self):
        return [(2**256-1, 2**255-1, 256), (2**257, 2**258-1, 256)]


class ShiftedTask(BooleanTask):
    """Same one-bit examples; intentionally violates word-homogeneity."""
    def expected(self, cases):
        ordinary = super().expected(cases)
        return [value if width == 1 else value ^ ((1 << width)-1)
                for (_, _, width), value in zip(cases, ordinary)]


def evaluate(task, proposal, image, seed):
    if proposal['status'] == 'abstained':
        return {'certified': False, 'containers': 0, 'abstained': True}
    runner = SandboxRunner(image)
    runner.max_container_runs = 20
    verifier = TaskVerifier(runner)
    report = verifier.verify(proposal['source'], task, {})
    result = {'certified': report['passed'], 'report': report, 'audit_cases': 0}
    if report['passed']:
        cases = task.samples(128, seed=seed, audit=True)
        for offset in range(0, len(cases), 32):
            verifier.check(proposal['source'], task, cases[offset:offset+32])
        result['audit_cases'] = len(cases)
    result['containers'] = runner.container_runs
    return result


def study(shard):
    if type(shard) is not int or shard not in (0, 1):
        raise ValueError('shard must be 0 or 1')
    image = os.environ.get('CONTRACT_RUNNER_IMAGE', 'recursive-ai-runner:local')
    rows = []
    for index, truth in enumerate(HOLDOUT[shard*7:shard*7+7]):
        task = BooleanTask(truth)
        public = task.public()
        examples = [(*case, value) for case, value in zip(public, task.expected(public))]
        # Freeze every arm's proposal before any protected evaluator call.
        proposals = {mode: induce(examples, mode) for mode in MODES}
        row = {'truth': truth, 'public': examples, 'proposals': proposals, 'arms': {}}
        offset = (index+shard) % 3
        order = MODES[offset:]+MODES[:offset]
        for mode in order:
            row['arms'][mode] = evaluate(task, proposals[mode], image, 1031026+truth)
        if not row['arms']['compositional']['certified']:
            raise ValueError('compositional candidate failed certification')
        if any(data['certified'] and not row['arms']['compositional']['certified']
               for data in row['arms'].values()):
            raise ValueError('baseline success lost')
        rows.append(row)
    summary = {mode: {'certified': sum(row['arms'][mode]['certified'] for row in rows),
                      'containers': sum(row['arms'][mode]['containers'] for row in rows),
                      'public_labels_per_task': 4,
                      'audit_cases': sum(row['arms'][mode].get('audit_cases', 0) for row in rows)}
               for mode in MODES}
    control = ShiftedTask(6)
    public = control.public()
    proposal = induce([(*case, value) for case, value in zip(public, control.expected(public))])
    negative = evaluate(control, proposal, image, 1031026)
    if negative['certified']:
        raise ValueError('word-homogeneity violation escaped protected checks')
    return {'protocol': 'boolean-word-transfer-1', 'code_commit': os.environ.get('GITHUB_SHA'),
            'shard': shard, 'development_truths': DEVELOPMENT, 'holdout_truths': HOLDOUT,
            'rows': rows, 'summary': summary, 'image': image, 'shifted_negative_control': negative,
            'learner_digest': hashlib.sha256(Path(__file__).with_name('boolean_induction.py').read_bytes()).hexdigest(),
            'production_promotion': False, 'independent_evaluation': False,
            'limits': ['Developer-supplied Boolean algebra and compiler; only operation coefficients are learned.',
                       'Four one-bit observations cannot prove arbitrary unknown functions are bitwise homogeneous.',
                       'Finite internal task family with complete one-bit truth tables, not open-world discovery.',
                       'Lookup and no-interaction controls isolate word transfer and Boolean interaction, not all SOTA methods.',
                       'Selector is trusted public-only host code; generated programs execute only in Docker.',
                       'No persistent skill promotion, independent operators, or external-domain evaluation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.shard)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('BOOLEAN_STUDY_RESULT '+json.dumps(result, sort_keys=True), flush=True)
