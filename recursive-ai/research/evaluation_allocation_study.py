"""Frozen development-only study for evaluation-allocation replay."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from autonomy.tasks import goal_contract
from research import evaluation_allocation_replay
from research.evaluation_allocation_replay import replay
from research.search_policy_evolution import (
    _evaluate_once,
    development_evaluation_matrices,
    initial_population,
    search_policy_protocol_digest,
)


FROZEN_CONFIG = {
    "protocol": "evaluation-allocation-development-study-1",
    "goal": "compound arithmetic",
    "tier": 2,
    "target": 1.0,
    "population": 4,
    "replicates": 2,
    "base_seed": 43100,
    "task_count": 4,
    "max_attempts": 12,
    "max_seconds": 90,
    "max_stagnation": 8,
    "max_model_calls": 0,
    "max_containers": 200,
    "provider": "search",
    "image": "recursive-ai-runner:local",
    "replay_core_size": 4,
    "replay_warmup_candidates": 2,
    "replay_seed": 43102,
    "development_only": True,
    "holdout_rows_included": False,
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def run_development_study(root, setup_started=None):
    config = dict(FROZEN_CONFIG)
    seeds = [config["base_seed"] + index for index in range(config["replicates"])]
    config["development_suite_digests"] = [
        goal_contract(
            config["goal"],
            tier=config["tier"],
            target=config["target"],
            task_seed=seed,
            task_count=config["task_count"],
        )["suite_digest"]
        for seed in seeds
    ]
    config["search_policy_protocol_digest"] = search_policy_protocol_digest()
    config["replay_source_sha256"] = hashlib.sha256(
        Path(evaluation_allocation_replay.__file__).read_bytes()
    ).hexdigest()
    config["study_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config["sha256"] = _digest(config)
    root = Path(root).resolve()
    archive = {}
    population = initial_population(config["population"], seed=config["base_seed"])
    started = time.monotonic()
    for order, genome in enumerate(population):
        rows = []
        for seed in seeds:
            row = _evaluate_once(
                root,
                genome,
                seed,
                "allocation-development",
                config["goal"],
                config["tier"],
                config["target"],
                config["task_count"],
                config["max_attempts"],
                config["max_seconds"],
                config["max_stagnation"],
                config["max_model_calls"],
                config["max_containers"],
                config["provider"],
                config["image"],
            )
            row["generation"] = 0
            rows.append(row)
        archive[genome.id] = {
            "genome": genome.descriptor(),
            "development_rows": rows,
            "first_generation": 0,
            "collection_order": order,
        }
    evaluation_wall_seconds = time.monotonic() - started
    export = development_evaluation_matrices(archive, 1)
    matrix = export["matrices"][0]
    baseline = min(matrix["candidates"], key=lambda candidate: candidate["order"])
    distinct_rows = len({tuple(candidate["scores"]) for candidate in matrix["candidates"]})
    positive_baseline_successes = sum(baseline["scores"])
    replay_report = None
    if distinct_rows > 1 and positive_baseline_successes > 0:
        replay_report = replay(
            matrix,
            core_size=config["replay_core_size"],
            warmup_candidates=config["replay_warmup_candidates"],
            seed=config["replay_seed"],
        )
    setup_inclusive_wall_seconds = (
        time.monotonic() - setup_started if setup_started is not None else None
    )
    report = {
        "protocol": config["protocol"],
        "config": config,
        "source_sha256": config["study_source_sha256"],
        "development_evaluation": export,
        "screen": {
            "candidate_count": len(matrix["candidates"]),
            "item_count": len(matrix["items"]),
            "distinct_score_rows": distinct_rows,
            "positive_baseline_successes": positive_baseline_successes,
            "nondegenerate": distinct_rows > 1,
        },
        "replay": replay_report,
        "cost_accounting": {
            "evaluation_wall_seconds": evaluation_wall_seconds,
            "matched_trial_budgets": True,
            "setup_inclusive_wall_seconds": setup_inclusive_wall_seconds,
            "setup_inclusive_wall_supported": setup_started is not None,
            "reason": (
                None if setup_started is not None
                else "runtime image build occurs outside this process"
            ),
        },
        "acceptance_passed": False,
        "limits": [
            "Development evidence only; no holdout task is constructed or evaluated.",
            "A degenerate matrix or zero baseline successes blocks replay.",
            "No efficiency claim is admissible without setup-inclusive runtime.",
            "This same-operator study cannot establish independent replication.",
        ],
    }
    report["receipt_sha256"] = _digest(report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".evaluation-allocation-study")
    parser.add_argument("--output", required=True)
    parser.add_argument("--setup-start-file")
    args = parser.parse_args()
    setup_started = None
    if args.setup_start_file:
        setup_started = float(Path(args.setup_start_file).read_text())
    report = run_development_study(args.root, setup_started=setup_started)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
