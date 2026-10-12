"""Tool-enforced boundary for configuration an autonomous search may change."""
from copy import deepcopy


MUTABLE_PATHS = frozenset({
    "curriculum.retry_weight",
    "curriculum.family_balance_weight",
    "curriculum.unlock_weight",
    "search.ucb_exploration",
    "search.parent_quality_weight",
    "search.parent_novelty_weight",
    "search.parent_size_weight",
    "search.parent_limit",
})

PROTECTED_ROOTS = frozenset({
    "evaluator",
    "holdout",
    "policy_floor",
    "promotion",
    "rollback",
    "sandbox",
})


def apply_configuration_patch(configuration, changes, *, enforce=True):
    """Apply flat dotted-path changes, rejecting writes outside the mutable genome.

    ``enforce=False`` exists only for preregistered prompt-only ablations. Production
    callers must use the default write-time enforcement.
    """
    if not isinstance(configuration, dict) or not isinstance(changes, dict):
        raise TypeError("configuration and changes must be dictionaries")
    if len(changes) > 32:
        raise ValueError("configuration patch is too large")
    result = deepcopy(configuration)
    for path, value in changes.items():
        if not isinstance(path, str) or not path or path.startswith(".") or path.endswith("."):
            raise ValueError("configuration paths must be non-empty dotted strings")
        root = path.split(".", 1)[0]
        if enforce and (root in PROTECTED_ROOTS or path not in MUTABLE_PATHS):
            raise PermissionError("configuration path is protected: " + path)
        result[path] = value
    return result


def assert_profile_paths(namespace, profile):
    """Fail closed before profile-specific value normalization."""
    if profile is None:
        return
    if not isinstance(profile, dict):
        raise ValueError(namespace + " profile has wrong shape")
    for key in profile:
        path = namespace + "." + str(key)
        if path not in MUTABLE_PATHS:
            raise PermissionError("configuration path is protected: " + path)
