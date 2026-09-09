"""Replicated learned-vs-fixed policy evaluation with isolated trial state."""
import hashlib
import json
import math
import statistics
from pathlib import Path
from autonomy.controller import execute_goal

MODES = ("fixed", "learned")


def _mean(values):
    return statistics.fmean(values) if values else None


def _median(values):
    return statistics.median(values) if values else None


def _sign_test_p(differences):
    """Exact two-sided sign test; zeros are excluded."""
    signs = [value for value in differences if value != 0]
    n = len(signs)
    if n == 0:
        return 1.0
    wins = sum(value < 0 for value in signs)
    tail = min(wins, n - wins)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2 ** n)
    return min(1.0, 2 * probability)


def summarize(rows):
    by_mode = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        by_mode[mode] = {
            "replicates": len(selected),
            "goal_reached_rate": _mean([float(row["goal_reached"]) for row in selected]),
            "audit_pass_rate": _mean([float(row["audit_passed"]) for row in selected]),
            "mean_coverage": _mean([row["coverage"] for row in selected]),
            "mean_attempts": _mean([row["attempts"] for row in selected]),
            "median_attempts": _median([row["attempts"] for row in selected]),
            "mean_wall_seconds": _mean([row["wall_seconds"] for row in selected]),
            "mean_container_runs": _mean([row["container_runs"] for row in selected]),
            "mean_model_calls": _mean([row["model_calls"] for row in selected]),
        }
    fixed = {row["seed"]: row for row in rows if row["mode"] == "fixed"}
    learned = {row["seed"]: row for row in rows if row["mode"] == "learned"}
    paired = []
    for seed in sorted(set(fixed) & set(learned)):
        a, b = fixed[seed], learned[seed]
        paired.append({
            "seed": seed,
            "attempt_delta_learned_minus_fixed": b["attempts"] - a["attempts"],
            "wall_delta_learned_minus_fixed": b["wall_seconds"] - a["wall_seconds"],
            "coverage_delta_learned_minus_fixed": b["coverage"] - a["coverage"],
            "goal_reached_delta_learned_minus_fixed": int(b["goal_reached"]) - int(a["goal_reached"]),
        })
    attempt_differences = [row["attempt_delta_learned_minus_fixed"] for row in paired]
    return {
        "by_mode": by_mode,
        "paired": paired,
        "paired_mean_attempt_delta_learned_minus_fixed": _mean(attempt_differences),
        "paired_attempt_sign_test_p": _sign_test_p(attempt_differences),
        "interpretation": "descriptive experimental evidence; do not claim general recursive improvement from one study",
    }


def run_meta_evaluation(root, goal="algorithms toolkit", tier=2, target=1.0,
                        replicates=3, base_seed=0, task_count=6,
                        max_attempts=64, max_seconds=900, max_stagnation=16,
                        max_model_calls=0, max_containers=2000,
                        provider="search", image="recursive-ai-runner:local"):
    if type(replicates) is not int or not 1 <= replicates <= 50:
        raise ValueError("replicates must be in [1,50]")
    if type(base_seed) is not int:
        raise ValueError("base_seed must be an integer")
    config = {
        "goal": goal,
        "tier": tier,
        "target": target,
        "replicates": replicates,
        "base_seed": base_seed,
        "task_count": task_count,
        "max_attempts": max_attempts,
        "max_seconds": max_seconds,
        "max_stagnation": max_stagnation,
        "max_model_calls": max_model_calls,
        "max_containers": max_containers,
        "provider": provider,
        "image": image,
    }
    study_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:20]
    study_root = Path(root).resolve() / "meta-evaluation" / study_id
    study_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for replicate in range(replicates):
        seed = base_seed + replicate
        for mode in MODES:
            trial_root = study_root / f"seed-{seed}-{mode}"
            summary = execute_goal(
                trial_root,
                description=goal,
                tier=tier,
                target=target,
                max_attempts=max_attempts,
                max_seconds=max_seconds,
                max_stagnation=max_stagnation,
                max_model_calls=max_model_calls,
                max_containers=max_containers,
                provider=provider,
                image=image,
                task_seed=seed,
                task_count=task_count,
                policy_mode=mode,
            )
            rows.append({
                "replicate": replicate,
                "seed": seed,
                "mode": mode,
                "status": summary["status"],
                "goal_reached": summary["status"] == "goal_reached",
                "audit_passed": bool(summary.get("audit") and summary["audit"].get("passed")),
                "coverage": summary["coverage"],
                "attempts": summary["total_attempts"],
                "wall_seconds": summary["wall_seconds"],
                "container_runs": summary["container_runs"],
                "model_calls": summary["model_calls"],
                "checkpoint": summary["checkpoint"],
            })
    report = {
        "study_id": study_id,
        "config": config,
        "trials": rows,
        "summary": summarize(rows),
    }
    temporary = study_root / "report.json.tmp"
    destination = study_root / "report.json"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(destination)
    return report
