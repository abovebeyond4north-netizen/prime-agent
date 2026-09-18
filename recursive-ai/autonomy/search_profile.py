"""Bounded search-policy configuration for autonomous program search.

The profile contains data only. It may change exploration pressure and how archived
candidate parents are ranked, but it cannot modify evaluators, task oracles,
verification gates, sandbox configuration, or promotion logic.
"""
import hashlib
import json
import math

SEARCH_PROFILE_KEYS = (
    "ucb_exploration",
    "parent_quality_weight",
    "parent_novelty_weight",
    "parent_size_weight",
    "parent_limit",
)

DEFAULT_SEARCH_PROFILE = {
    "ucb_exploration": 2.0,
    "parent_quality_weight": 0.70,
    "parent_novelty_weight": 0.25,
    "parent_size_weight": 0.05,
    "parent_limit": 8,
}


def normalize_search_profile(profile=None):
    if profile is None:
        return dict(DEFAULT_SEARCH_PROFILE)
    if not isinstance(profile, dict) or set(profile) != set(SEARCH_PROFILE_KEYS):
        raise ValueError("search profile has wrong shape")

    normalized = {}
    exploration = profile["ucb_exploration"]
    if (
        not isinstance(exploration, (int, float))
        or isinstance(exploration, bool)
        or not math.isfinite(exploration)
        or not 0.05 <= float(exploration) <= 8.0
    ):
        raise ValueError("ucb_exploration must be in [0.05,8]")
    normalized["ucb_exploration"] = float(exploration)

    weights = []
    for key in (
        "parent_quality_weight",
        "parent_novelty_weight",
        "parent_size_weight",
    ):
        value = profile[key]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or not 0.0 <= float(value) <= 4.0
        ):
            raise ValueError("parent weights must be finite values in [0,4]")
        normalized[key] = float(value)
        weights.append(float(value))
    if math.fsum(weights) <= 0.0:
        raise ValueError("at least one parent ranking weight must be positive")

    parent_limit = profile["parent_limit"]
    if type(parent_limit) is not int or not 1 <= parent_limit <= 16:
        raise ValueError("parent_limit must be an integer in [1,16]")
    normalized["parent_limit"] = parent_limit
    return normalized


def normalized_parent_weights(profile=None):
    profile = normalize_search_profile(profile)
    keys = (
        "parent_quality_weight",
        "parent_novelty_weight",
        "parent_size_weight",
    )
    total = math.fsum(profile[key] for key in keys)
    return tuple(profile[key] / total for key in keys)


def search_profile_digest(profile=None):
    normalized = normalize_search_profile(profile)
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
