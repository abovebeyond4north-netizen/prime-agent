"""Compile evidence into an executable search policy; never execute it on the host."""
import math
from core.ast_validator import parse, validate
from autonomy.memory import OPERATORS


def choose(evidence):
    for index, (attempts, _, _) in enumerate(evidence):
        if attempts == 0:
            return index
    total = sum(row[0] for row in evidence)
    scores = [reward / attempts + math.sqrt(2 * math.log(total) / attempts)
              for attempts, reward, _ in evidence]
    return max(range(len(scores)), key=scores.__getitem__)


def compile_policy(evidence):
    # Beta-style optimism decays as evidence accumulates. Coefficients change from outcomes.
    total = max(1, sum(row[0] for row in evidence))
    scores = [reward / attempts + math.sqrt(2 * math.log(total) / attempts) if attempts else 1_000_000
              for attempts, reward, _ in evidence]
    source = "def choose_operator():\n    scores = " + repr(scores) + "\n    best = 0\n    for index in range(1, len(scores)):\n        if scores[index] > scores[best]:\n            best = index\n    return best\n"
    validate(parse(source))
    return source


def dispatch(runner, evidence):
    source = compile_policy(evidence)
    expected = choose(evidence)
    result = runner.execute(source, [()], entrypoint="choose_operator", max_steps=1000)
    if result["outputs"] != [expected] or not 0 <= expected < len(OPERATORS):
        raise RuntimeError("learned policy failed its action contract")
    return OPERATORS[expected], source
