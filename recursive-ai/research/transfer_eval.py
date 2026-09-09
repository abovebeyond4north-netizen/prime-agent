"""Cross-family policy-transfer evaluation with strict state separation.

A learned training run may transfer only aggregate operator evidence into a fresh
held-out run. Candidate source, checkpoints, archives, task answers and skills never
cross the boundary.
"""
import hashlib
import json
import math
import statistics
from pathlib import Path
from autonomy.controller import execute_goal
from autonomy.memory import ResearchMemory
from autonomy.tasks import goal_contract

MODES = ("fixed", "learned_scratch", "learned_transfer")


def _mean(values):
    return statistics.fmean(values) if values else None


def _median(values):
    return statistics.median(values) if values else None


def _sign_test_p(differences):
    signs = [value for value in differences if value != 0]
    n = len(signs)
    if n == 0:
        return 1.0
    wins = sum(value < 0 for value in signs)
    tail = min(wins, n - wins)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2 ** n)
    return min(1.0, 2 * probability)


def _contract(goal, tier, task_seed, task_count):
    return goal_contract(goal, tier=tier, task_seed=task_seed, task_count=task_count)


def _families(goal, tier, task_seed, task_count):
    return {task["family"] for task in _contract(goal, tier, task_seed, task_count)["tasks"]}


def _require_disjoint(train_goal, holdout_goal, tier, seed, task_count):
    train_families = _families(train_goal, tier, seed, task_count)
    holdout_families = _families(holdout_goal, tier, seed, task_count)
    overlap = train_families & holdout_families
    if overlap:
        raise ValueError("training and holdout families must be disjoint: " + ",".join(sorted(overlap)))
    return train_families, holdout_families


def _read_prior(root):
    memory = ResearchMemory(root)
    try:
        return memory.global_operators()
    finally:
        memory.db.close()


def _row(summary, replicate, seed, mode):
    return {
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
        "policy_prior_digest": summary.get("policy_prior_digest"),
    }


def _mode_summary(rows):
    result = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        result[mode] = {
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
    return result


def _paired(rows, control):
    control_rows = {row["seed"]: row for row in rows if row["mode"] == control}
    transfer_rows = {row["seed"]: row for row in rows if row["mode"] == "learned_transfer"}
    paired = []
    for seed in sorted(set(control_rows) & set(transfer_rows)):
        base, transfer = control_rows[seed], transfer_rows[seed]
        paired.append({
            "seed": seed,
            "attempt_delta_transfer_minus_control": transfer["attempts"] - base["attempts"],
            "wall_delta_transfer_minus_control": transfer["wall_seconds"] - base["wall_seconds"],
            "coverage_delta_transfer_minus_control": transfer["coverage"] - base["coverage"],
            "goal_reached_delta_transfer_minus_control": int(transfer["goal_reached"]) - int(base["goal_reached"]),
        })
    differences = [row["attempt_delta_transfer_minus_control"] for row in paired]
    nonzero = [value for value in differences if value != 0]
    return {
        "control": control,
        "pairs": paired,
        "mean_attempt_delta_transfer_minus_control": _mean(differences),
        "attempt_sign_test_p": _sign_test_p(differences),
        "transfer_attempt_win_rate_nonzero": (_mean([float(value < 0) for value in nonzero]) if nonzero else None),
    }


def summarize(training_rows, holdout_rows):
    return {
        "training": {
            "goal_reached_rate": _mean([float(row["goal_reached"]) for row in training_rows]),
            "audit_pass_rate": _mean([float(row["audit_passed"]) for row in training_rows]),
            "mean_attempts": _mean([row["attempts"] for row in training_rows]),
            "mean_wall_seconds": _mean([row["wall_seconds"] for row in training_rows]),
        },
        "holdout_by_mode": _mode_summary(holdout_rows),
        "transfer_vs_learned_scratch": _paired(holdout_rows, "learned_scratch"),
        "transfer_vs_fixed": _paired(holdout_rows, "fixed"),
        "interpretation": (
            "Cross-family transfer evidence only. A beneficial result supports reusable search-policy bias "
            "within these declared task distributions; it is not proof of open-ended recursive self-improvement."
        ),
    }


def run_transfer_evaluation(root, train_goal="sorted search", holdout_goal="number theory",
                            tier=1, target=1.0, replicates=3, base_seed=0, task_count=6,
                            prior_strength=4.0, max_attempts=64, max_seconds=900,
                            max_stagnation=16, max_model_calls=0, max_containers=2000,
                            provider="search", image="recursive-ai-runner:local"):
    if type(replicates) is not int or not 1 <= replicates <= 20:
        raise ValueError("replicates must be in [1,20]")
    if type(base_seed) is not int:
        raise ValueError("base_seed must be an integer")
    if not isinstance(prior_strength, (int, float)) or not math.isfinite(prior_strength) or not 0 <= prior_strength <= 32:
        raise ValueError("prior_strength must be in [0,32]")

    train_families, holdout_families = _require_disjoint(
        train_goal, holdout_goal, tier, base_seed, task_count
    )
    train_contract = _contract(train_goal, tier, base_seed, task_count)
    holdout_contract = _contract(holdout_goal, tier, base_seed, task_count)
    if train_contract["suite_digest"] != holdout_contract["suite_digest"]:
        raise ValueError("training and holdout contracts must use the same trusted suite")
    suite_digest = train_contract["suite_digest"]

    config = {
        "train_goal": train_goal,
        "holdout_goal": holdout_goal,
        "tier": tier,
        "target": target,
        "replicates": replicates,
        "base_seed": base_seed,
        "task_count": task_count,
        "prior_strength": prior_strength,
        "max_attempts": max_attempts,
        "max_seconds": max_seconds,
        "max_stagnation": max_stagnation,
        "max_model_calls": max_model_calls,
        "max_containers": max_containers,
        "provider": provider,
        "image": image,
        "suite_digest": suite_digest,
        "train_families": sorted(train_families),
        "holdout_families": sorted(holdout_families),
        "transfer_boundary": "aggregate_operator_evidence_only",
    }
    study_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:20]
    study_root = Path(root).resolve() / "transfer-evaluation" / study_id
    study_root.mkdir(parents=True, exist_ok=True)
    training_rows = []
    holdout_rows = []
    priors = []

    for replicate in range(replicates):
        seed = base_seed + replicate
        # Generated curricula can vary their family names with the seed, so recheck the
        # no-overlap invariant for every replicate rather than trusting the base seed.
        _require_disjoint(train_goal, holdout_goal, tier, seed, task_count)
        train_root = study_root / f"seed-{seed}-train"
        train_summary = execute_goal(
            train_root,
            description=train_goal,
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
            policy_mode="learned",
        )
        prior = _read_prior(train_root)
        prior_digest = hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest()
        training_rows.append({
            "replicate": replicate,
            "seed": seed,
            "status": train_summary["status"],
            "goal_reached": train_summary["status"] == "goal_reached",
            "audit_passed": bool(train_summary.get("audit") and train_summary["audit"].get("passed")),
            "coverage": train_summary["coverage"],
            "attempts": train_summary["total_attempts"],
            "wall_seconds": train_summary["wall_seconds"],
            "container_runs": train_summary["container_runs"],
            "model_calls": train_summary["model_calls"],
            "prior_digest": prior_digest,
        })
        priors.append({"replicate": replicate, "seed": seed, "digest": prior_digest, "evidence": prior})

        for mode in MODES:
            trial_root = study_root / f"seed-{seed}-holdout-{mode}"
            policy_mode = "fixed" if mode == "fixed" else "learned"
            policy_prior = prior if mode == "learned_transfer" else None
            summary = execute_goal(
                trial_root,
                description=holdout_goal,
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
                policy_mode=policy_mode,
                policy_prior=policy_prior,
                prior_strength=prior_strength,
            )
            holdout_rows.append(_row(summary, replicate, seed, mode))

    report = {
        "study_id": study_id,
        "config": config,
        "training_trials": training_rows,
        "transferred_priors": priors,
        "holdout_trials": holdout_rows,
        "summary": summarize(training_rows, holdout_rows),
    }
    temporary = study_root / "report.json.tmp"
    destination = study_root / "report.json"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(destination)
    return report
