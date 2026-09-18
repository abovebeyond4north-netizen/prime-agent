import hashlib
import json
import math
from autonomy.tasks import SUITE_VERSION, Task, task_from_key, suite_digest


CURRICULUM_PROFILE_KEYS = ("retry_weight", "family_balance_weight", "unlock_weight")
DEFAULT_CURRICULUM_PROFILE = {
    "retry_weight": 1.0,
    "family_balance_weight": 0.0,
    "unlock_weight": 0.0,
}


def normalize_curriculum_profile(profile=None):
    """Validate the bounded, data-only curriculum genome.

    The profile may change task ordering only. It cannot add task families, alter
    prerequisites, change evaluators, or bypass certification gates.
    """
    if profile is None:
        return dict(DEFAULT_CURRICULUM_PROFILE)
    if not isinstance(profile, dict) or set(profile) != set(CURRICULUM_PROFILE_KEYS):
        raise ValueError("curriculum profile has wrong shape")
    normalized = {}
    for key in CURRICULUM_PROFILE_KEYS:
        value = profile[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("curriculum profile values must be finite numbers")
        if not 0.0 <= float(value) <= 4.0:
            raise ValueError("curriculum profile values must be in [0,4]")
        normalized[key] = float(value)
    return normalized


def curriculum_profile_digest(profile=None):
    normalized = normalize_curriculum_profile(profile)
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def certified(active):
    return {key: value for key, value in active.items()
            if value.get("report", {}).get("suite_version") == SUITE_VERSION
            and value["report"].get("suite_digest") == suite_digest()
            and value["report"].get("task") == key
            and value["report"].get("passed") is True
            and [gate.get("number") for gate in value["report"].get("gates", [])] == list(range(1, 11))
            and all(gate.get("passed") is True for gate in value["report"]["gates"])}


def coverage(contract, active):
    verified = certified(active)
    return min(1.0, math.fsum(weight for key, weight in contract["weights"].items() if key in verified))


def next_task(contract, active, attempts, profile=None):
    verified = certified(active)
    profile = normalize_curriculum_profile(profile)
    eligible = []
    remaining = []
    for descriptor in contract["tasks"]:
        task = task_from_key(descriptor["key"])
        if task.key not in verified:
            remaining.append(task)
        if task.key in verified:
            continue
        if task.tier > 1 and task.with_tier(task.tier - 1).key not in verified:
            continue
        if any(Task(dependency, 1).key not in verified for dependency in task.prerequisites):
            continue
        eligible.append(task)
    if not eligible:
        return None

    def family_attempts(family):
        total = 0
        for key, count in attempts.items():
            try:
                if task_from_key(key).family == family:
                    total += count
            except (TypeError, ValueError):
                continue
        return total

    def unlock_count(family):
        return sum(family in task.prerequisites for task in remaining)

    def rank(task):
        retries = attempts.get(task.key, 0)
        adaptive_score = (
            profile["retry_weight"] * retries
            + profile["family_balance_weight"] * family_attempts(task.family)
            - profile["unlock_weight"] * unlock_count(task.family)
        )
        # Tier remains the first immutable ordering key so evolution cannot skip
        # prerequisite difficulty progression. The default profile exactly
        # reproduces the previous (tier, attempts, key) ordering.
        return (task.tier, adaptive_score, retries, task.key)

    return min(eligible, key=rank)
