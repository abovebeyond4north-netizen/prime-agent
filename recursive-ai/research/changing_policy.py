"""CPU-only reference experiment; no candidate code execution or promotion.

Learners infer an integer threshold from outcome feedback. Test inputs are
fractional and never supplied to observe(). This is logical split separation,
not a security boundary or an independent external evaluation.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path


class ThresholdMemory:
    def __init__(self, mode):
        if mode not in ('fixed', 'frozen', 'revising'):
            raise ValueError('unknown mode')
        self.mode = mode
        self.possible = set(range(1, 16))
        self.updates = 0
        self.resets = 0

    def predict(self, x, explicit=None):
        threshold = explicit if explicit is not None else sorted(self.possible)[len(self.possible) // 2]
        return int(x >= threshold)

    def observe(self, x, outcome):
        if self.mode == 'fixed':
            return
        compatible = {t for t in self.possible if int(x >= t) == outcome}
        if not compatible:
            if self.mode == 'frozen':
                return
            compatible = {t for t in range(1, 16) if int(x >= t) == outcome}
            self.resets += 1
        self.possible = compatible
        self.updates += 1

    def state(self):
        return dict(mode=self.mode, possible=sorted(self.possible), updates=self.updates, resets=self.resets)

    @classmethod
    def restore(cls, state):
        learner = cls(state['mode'])
        learner.possible = set(state['possible'])
        learner.updates, learner.resets = state['updates'], state['resets']
        return learner


def run_schedule(seed):
    rng = random.Random(seed)
    low, high = rng.randint(2, 5), rng.randint(11, 14)
    schedule = [low, high, low]
    learners = {mode: ThresholdMemory(mode) for mode in ('fixed', 'frozen', 'revising')}
    rows = []
    for window, threshold in enumerate(schedule):
        serving = list(range(17))
        rng.shuffle(serving)
        tests = [x + 0.5 for x in range(16)]
        for mode, learner in learners.items():
            for x in serving:
                learner.observe(x, int(x >= threshold))
            # Round-trip serialized learning state before testing unseen inputs.
            learner = ThresholdMemory.restore(json.loads(json.dumps(learner.state())))
            learners[mode] = learner
            before = learner.state()
            correct = sum(learner.predict(x) == int(x >= threshold) for x in tests)
            explicit_correct = sum(learner.predict(x, explicit=8) == int(x >= 8) for x in tests)
            assert before == learner.state(), 'evaluation mutated learning state'
            rows.append(dict(window=window, mode=mode, correct=correct, total=len(tests),
                             explicit_correct=explicit_correct, serving_observations=len(serving),
                             state=learner.state()))
    return dict(seed=seed, rows=rows)


def run_study(seeds=(104729, 130363, 155921)):
    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError('at least three distinct schedules required')
    trials = [run_schedule(seed) for seed in seeds]
    checks = []
    for trial in trials:
        totals = {mode: sum(r['correct'] for r in trial['rows'] if r['mode'] == mode)
                  for mode in ('fixed', 'frozen', 'revising')}
        checks.append(totals['revising'] > max(totals['fixed'], totals['frozen'])
                      and all(r['explicit_correct'] == r['total'] for r in trial['rows']))
    return dict(protocol='changing-threshold-v1', seeds=list(seeds), trials=trials,
                reference_acceptance=all(checks), automatic_promotion=False,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limitations=['Handwritten finite hypothesis class; not autonomous algorithm discovery.',
                             'Equal observations, not equal compute; updates and resets are reported.',
                             'Same-process synthetic evaluator; no external or real-world validation.',
                             'Published schedules are reusable regression cases, not future sealed holdouts.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run_study(), indent=2, sort_keys=True) + '\n')
