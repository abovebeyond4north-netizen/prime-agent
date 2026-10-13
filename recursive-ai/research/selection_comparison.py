"""Preregistered, non-promoting comparison of search-policy parent selectors."""
import hashlib
import json
from pathlib import Path

from research.paired_evidence import METRICS, paired_resource_evidence
from research.search_policy_evolution import run_search_policy_evolution


def _identity(rows):
    keys = [(row["goal"], row["seed"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate evaluation identity")
    return set(keys)


def evaluation_integrity_canaries(reference, candidate):
    """Return explicit fail-closed checks for common evaluation exploits."""
    left, right = reference["config"], candidate["config"]
    matched_fields = (
        "train_suite_digest", "holdout_suite_digest",
        "search_policy_protocol_digest", "development_seeds_by_generation",
        "holdout_seeds", "train_families", "holdout_families",
        "max_attempts", "max_seconds", "max_stagnation", "max_model_calls",
        "max_containers", "provider", "image", "population", "generations",
        "task_count", "tier", "target",
    )
    baseline_a = reference["cross_family_holdout"]["baseline"]["rows"]
    baseline_b = candidate["cross_family_holdout"]["baseline"]["rows"]
    finalist_a = reference["cross_family_holdout"]["finalist"]["rows"]
    finalist_b = candidate["cross_family_holdout"]["finalist"]["rows"]
    baseline_fields = (
        "goal", "seed", "goal_reached", "audit_passed", "coverage", "attempts",
        "container_runs", "model_calls", "search_profile_digest",
    )

    def measurements(rows):
        return sorted(tuple(row[field] for field in baseline_fields) for row in rows)

    checks = {
        "matched_protocol": all(left[field] == right[field] for field in matched_fields),
        "split_isolation": not (set(left["train_families"]) & set(left["holdout_families"])),
        "equal_development_trials": (
            reference["sample_efficiency"]["actual_development_trials"]
            == candidate["sample_efficiency"]["actual_development_trials"]
        ),
        "matched_unique_holdouts": False,
        "shared_baseline_consistency": measurements(baseline_a) == measurements(baseline_b),
        "independent_baseline_recheck": (
            not candidate.get("baseline_execution", {}).get("reused", False)
            or candidate["baseline_execution"].get("independent_rechecks") == 1
        ),
        "correctness_before_resources": all(
            row["goal_reached"] and row["audit_passed"]
            for row in finalist_a + finalist_b
        ),
    }
    try:
        identities = _identity(finalist_a)
        checks["matched_unique_holdouts"] = bool(identities) and all(
            _identity(rows) == identities
            for rows in (finalist_b, baseline_a, baseline_b)
        )
    except ValueError:
        checks["matched_unique_holdouts"] = False
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "purpose": "Detect protocol drift, leakage, replay, baseline tampering, and proxy-only resource gains.",
    }


def compare_parent_selection(root, **options):
    """Run both selectors on matched budgets and fresh, cross-family holdouts.

    Neither selector sees the other's results during development. The comparison
    only reads final reports after both independent studies have completed.
    """
    if "parent_selection" in options:
        raise ValueError("parent_selection is controlled by this comparison")
    root = Path(root).resolve()
    study_root = root / "selection-comparison"
    study_root.mkdir(parents=True, exist_ok=True)
    protocol_path = study_root / "protocol.json"
    protocol = {"version": "matched-parent-selection-v1", "options": options,
                "arms": ["quality_diversity", "pareto"], "automatic_promotion": False}
    if protocol_path.exists():
        if json.loads(protocol_path.read_text()) != protocol:
            raise ValueError("comparison root is bound to another protocol")
    else:
        temporary = protocol_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
        temporary.replace(protocol_path)
    reference = run_search_policy_evolution(
        study_root / "quality_diversity", parent_selection="quality_diversity",
        **options
    )
    candidate = run_search_policy_evolution(
        study_root / "pareto", parent_selection="pareto",
        _shared_holdout_baseline=reference["cross_family_holdout"]["baseline"],
        **options
    )
    arms = {"quality_diversity": reference, "pareto": candidate}
    left, right = reference["config"], candidate["config"]
    canaries = evaluation_integrity_canaries(reference, candidate)
    if not canaries["all_passed"]:
        failed = sorted(name for name, passed in canaries["checks"].items() if not passed)
        raise ValueError(f"evaluation integrity canary failed: {', '.join(failed)}")
    for field in ("train_suite_digest", "holdout_suite_digest",
                  "search_policy_protocol_digest", "development_seeds_by_generation",
                  "holdout_seeds", "train_families", "holdout_families",
                  "max_attempts", "max_seconds", "max_stagnation",
                  "max_model_calls", "max_containers", "provider", "image",
                  "population", "generations", "task_count", "tier", "target"):
        if left[field] != right[field]:
            raise ValueError(f"unmatched comparison protocol: {field}")
    if set(left["train_families"]) & set(left["holdout_families"]):
        raise ValueError("development and holdout families overlap")
    if (reference["sample_efficiency"]["actual_development_trials"] !=
            candidate["sample_efficiency"]["actual_development_trials"]):
        raise ValueError("unequal development trial counts")
    baseline_a = reference["cross_family_holdout"]["baseline"]["rows"]
    baseline_b = candidate["cross_family_holdout"]["baseline"]["rows"]
    finalist_a = reference["cross_family_holdout"]["finalist"]["rows"]
    finalist_b = candidate["cross_family_holdout"]["finalist"]["rows"]
    identities = _identity(finalist_a)
    if not identities or any(_identity(rows) != identities for rows in
                             (finalist_b, baseline_a, baseline_b)):
        raise ValueError("unmatched holdout identities")
    baseline_fields = ("goal", "seed", "goal_reached", "audit_passed",
                       "coverage", "attempts", "container_runs", "model_calls",
                       "search_profile_digest")
    def baseline_measurements(rows):
        return sorted(tuple(row[field] for field in baseline_fields) for row in rows)
    if baseline_measurements(baseline_a) != baseline_measurements(baseline_b):
        raise ValueError("shared baseline has inconsistent outcomes across arms")
    evidence = paired_resource_evidence(finalist_b, finalist_a)
    def resources(study):
        development = [row for record in study["archive"]
                       for row in record["development_rows"]]
        holdout = (study["cross_family_holdout"]["finalist"]["rows"] +
                   study["cross_family_holdout"]["baseline"]["rows"])
        return {
            phase: {metric: sum(row[metric] for row in rows) for metric in METRICS}
            for phase, rows in (("development", development), ("holdout", holdout))
        }
    # The existing statistic tests resources conditional on correctness. Explicitly
    # require both arms to reach the goal and pass audits before discussing gain.
    report = {
        "protocol": "matched-parent-selection-v1",
        "arm_study_ids": {mode: value["study_id"] for mode, value in arms.items()},
        "protocol_digest": hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest(),
        "development_trials_per_arm": candidate["sample_efficiency"]["actual_development_trials"],
        # Logical per-arm totals retain the shared baseline for comparable
        # experimental accounting; actual execution skips its repeated trials.
        "resource_totals_by_arm": {mode: resources(value) for mode, value in arms.items()},
        "execution_efficiency": {
            "baseline_evaluations_avoided": candidate["baseline_execution"]["reused_trials"],
            "independent_baseline_rechecks": candidate["baseline_execution"]["independent_rechecks"],
            "estimated_container_runs_avoided": candidate["baseline_execution"]["estimated_container_runs_avoided"],
            "logical_accounting_includes_reused_baseline": True,
        },
        "holdout_pairs": len(identities),
        "holdout_families": left["holdout_families"],
        "holdout_comparison_pareto_minus_quality_diversity": evidence,
        "evaluation_integrity_canaries": canaries,
        "promotion": {"automatic": False, "eligible": False},
        "limitations": [
            "A single seed schedule is an exploratory comparison, not a replicated search study.",
            "Reusing these holdouts to tune selectors would invalidate independent confirmation.",
            "The common reference baseline is reused across arms after one independently rechecked holdout; other reused rows are not reexecuted in the candidate arm.",
            "Replay-based screening is not implemented in this comparison.",
        ],
    }
    path = study_root / "comparison.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
    return report
