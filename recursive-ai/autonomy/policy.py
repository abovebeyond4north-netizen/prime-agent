"""Compile evidence into executable search policies; never execute them on the host."""
import math
from core.ast_validator import parse, validate
from autonomy.memory import OPERATORS


def _validate_evidence(evidence):
    if not isinstance(evidence, (list, tuple)) or len(evidence) != len(OPERATORS):
        raise ValueError("operator evidence has wrong shape")
    normalized = []
    for row in evidence:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("operator evidence rows must be triples")
        attempts, reward, seconds = row
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in row):
            raise ValueError("operator evidence must be finite numeric values")
        if attempts < 0 or reward < 0 or seconds < 0 or reward > attempts + 1e-12:
            raise ValueError("operator evidence outside supported bounds")
        normalized.append((float(attempts), float(reward), float(seconds)))
    return normalized


def transfer_prior(evidence, strength=4.0):
    """Compress cross-family outcomes into a bounded pseudo-count prior.

    Total pseudo-count mass is exactly ``strength``. No candidate source, task answers,
    checkpoints, or family identifiers are transferred. Operators unseen during training
    receive the global mean reward rate rather than an artificial zero-probability prior.
    """
    rows = _validate_evidence(evidence)
    if not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0 <= strength <= 32:
        raise ValueError("prior strength must be in [0,32]")
    total_attempts = sum(row[0] for row in rows)
    if strength == 0 or total_attempts == 0:
        return [(0.0, 0.0, 0.0) for _ in OPERATORS]
    total_reward = sum(row[1] for row in rows)
    total_seconds = sum(row[2] for row in rows)
    global_rate = total_reward / total_attempts
    global_seconds = total_seconds / total_attempts
    pseudo_attempts = float(strength) / len(OPERATORS)
    prior = []
    for attempts, reward, seconds in rows:
        reward_rate = reward / attempts if attempts else global_rate
        seconds_rate = seconds / attempts if attempts else global_seconds
        prior.append((pseudo_attempts, pseudo_attempts * reward_rate, pseudo_attempts * seconds_rate))
    return prior


def combine_evidence(local, prior=None, strength=4.0):
    """Blend family-local evidence with a bounded cross-family prior."""
    local_rows = _validate_evidence(local)
    if prior is None:
        return local_rows
    prior_rows = transfer_prior(prior, strength)
    return [tuple(a + b for a, b in zip(local_row, prior_row))
            for local_row, prior_row in zip(local_rows, prior_rows)]


def choose(evidence):
    """UCB1 policy used by the adaptive condition."""
    evidence = _validate_evidence(evidence)
    for index, (attempts, _, _) in enumerate(evidence):
        if attempts == 0:
            return index
    total = sum(row[0] for row in evidence)
    scores = [reward / attempts + math.sqrt(2 * math.log(total) / attempts)
              for attempts, reward, _ in evidence]
    return max(range(len(scores)), key=scores.__getitem__)


def choose_fixed(evidence):
    """Non-learning round-robin control with identical action space."""
    evidence = _validate_evidence(evidence)
    attempts = sum(row[0] for row in evidence)
    return int(attempts) % len(OPERATORS)


def compile_policy(evidence):
    evidence = _validate_evidence(evidence)
    # Beta-style optimism decays as evidence accumulates. Coefficients change from outcomes.
    total = max(1.0, sum(row[0] for row in evidence))
    scores = [reward / attempts + math.sqrt(2 * math.log(total) / attempts) if attempts else 1_000_000
              for attempts, reward, _ in evidence]
    source = "def choose_operator():\n    scores = " + repr(scores) + "\n    best = 0\n    for index in range(1, len(scores)):\n        if scores[index] > scores[best]:\n            best = index\n    return best\n"
    validate(parse(source))
    return source


def compile_fixed_policy(evidence):
    """Compile a deterministic control policy without reading rewards."""
    expected = choose_fixed(evidence)
    source = f"def choose_operator():\n    return {expected}\n"
    validate(parse(source))
    return source


def _execute_policy(runner, source, expected):
    result = runner.execute(source, [()], entrypoint="choose_operator", max_steps=1000)
    if result["outputs"] != [expected] or not 0 <= expected < len(OPERATORS):
        raise RuntimeError("policy failed its action contract")
    return OPERATORS[expected], source


def dispatch(runner, evidence):
    source = compile_policy(evidence)
    return _execute_policy(runner, source, choose(evidence))


def dispatch_fixed(runner, evidence):
    source = compile_fixed_policy(evidence)
    return _execute_policy(runner, source, choose_fixed(evidence))
