"""Descriptive paired holdout evidence; never used to select or promote policies.

Exact one-sided sign tests test directional win probability, not mean gain.
Holm correction controls the family of three resource comparisons within ONE
prespecified study. It does not correct adaptive reuse across studies.
"""
import math
import statistics

METRICS = ("attempts", "container_runs", "model_calls")
MAX_PAIRS = 1024


def _index(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_PAIRS:
        raise ValueError("expected 1..1024 trial rows")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("trial must be a mapping")
        seed, goal = row.get("seed"), row.get("goal")
        if type(seed) is not int or not isinstance(goal, str) or not goal:
            raise ValueError("each trial needs an integer seed and nonempty goal")
        key = (goal, seed)
        if key in indexed:
            raise ValueError("duplicate goal/seed pair")
        for flag in ("goal_reached", "audit_passed"):
            if type(row.get(flag)) is not bool:
                raise ValueError("correctness flags must be booleans")
        coverage = row.get("coverage")
        if type(coverage) not in (int, float) or not math.isfinite(coverage) or not 0 <= coverage <= 1:
            raise ValueError("coverage must be finite in [0,1]")
        for metric in METRICS:
            value = row.get(metric)
            if type(value) is not int or not 0 <= value <= 10**12:
                raise ValueError("resource counters must be bounded nonnegative integers")
        indexed[key] = row
    return indexed


def _sign_p(wins, losses):
    n = wins + losses
    if not n:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / (2 ** n)


def paired_resource_evidence(finalist_rows, baseline_rows):
    """Match exact trial identities and report fixed-alpha, corrected evidence.

    O(m*n^2) worst-case integer arithmetic for exact binomial tails (m=3),
    O(n) stored rows, bounded by MAX_PAIRS. No random state or dependencies.
    Failed trials remain in the report and block the supported-gain label.
    """
    finalist, baseline = _index(finalist_rows), _index(baseline_rows)
    if finalist.keys() != baseline.keys():
        raise ValueError("baseline and finalist must have identical goal/seed pairs")
    keys = sorted(finalist)
    all_correct = all(
        finalist[key]["goal_reached"] and finalist[key]["audit_passed"]
        and baseline[key]["goal_reached"] and baseline[key]["audit_passed"]
        for key in keys
    )
    coverage_non_regression = all(
        finalist[key]["coverage"] >= baseline[key]["coverage"] for key in keys
    )
    metrics = {}
    for metric in METRICS:
        deltas = [finalist[key][metric] - baseline[key][metric] for key in keys]
        wins = sum(delta < 0 for delta in deltas)
        losses = sum(delta > 0 for delta in deltas)
        metrics[metric] = {
            "mean_delta_finalist_minus_baseline": statistics.fmean(deltas),
            "median_delta_finalist_minus_baseline": statistics.median(deltas),
            "min_delta": min(deltas), "max_delta": max(deltas),
            "wins": wins, "losses": losses, "ties": len(deltas) - wins - losses,
            "one_sided_sign_p": _sign_p(wins, losses),
        }
    ordered = sorted(metrics, key=lambda metric: metrics[metric]["one_sided_sign_p"])
    adjusted = 0.0
    for index, metric in enumerate(ordered):
        adjusted = max(adjusted, min(1.0, (len(ordered) - index) * metrics[metric]["one_sided_sign_p"]))
        metrics[metric]["holm_adjusted_p"] = adjusted
    # A cheap failed run or a resource tradeoff cannot support an overall gain.
    no_resource_regression = all(value["max_delta"] <= 0 for value in metrics.values())
    directional_support = any(value["holm_adjusted_p"] <= 0.05 for value in metrics.values())
    supported = all_correct and coverage_non_regression and no_resource_regression and directional_support
    return {
        "pairs": len(keys),
        "metrics": metrics,
        "all_correct": all_correct,
        "coverage_non_regression_every_pair": coverage_non_regression,
        "resource_non_regression_every_pair": no_resource_regression,
        "status": "supported_directional_resource_gain" if supported else "gain_not_established",
        "alpha": 0.05,
        "automatic_promotion": False,
        "assumptions": [
            "independent prespecified holdout pairs; exchangeable signs under the null",
            "one frozen finalist selected without inspecting these holdouts",
            "Holm correction covers three resource metrics within this study only",
            "sign tests concern win probability, not effect size or universal generalization",
            "wall time is excluded because machine load is a confounder",
            "identical or correlated task instances across seeds are not independent evidence",
        ],
    }
