"""Development-only replay of sparse evaluation allocation policies."""
import hashlib
import json
import math
import random
from pathlib import Path


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _validate(matrix):
    if not isinstance(matrix, dict) or matrix.get("complete") is not True:
        raise ValueError("a complete development matrix is required")
    if matrix.get("holdout_rows_included") is True:
        raise ValueError("protected holdout rows are not admissible")
    items = matrix.get("items")
    candidates = matrix.get("candidates")
    if not isinstance(items, list) or len(items) < 4:
        raise ValueError("at least four development items are required")
    if not isinstance(candidates, list) or len(candidates) < 3:
        raise ValueError("at least three candidates are required")
    ids = [candidate.get("id") for candidate in candidates]
    if any(not isinstance(candidate_id, str) or not candidate_id for candidate_id in ids):
        raise ValueError("candidate ids must be nonempty strings")
    if len(set(ids)) != len(ids):
        raise ValueError("candidate ids must be unique")
    orders = [candidate.get("order") for candidate in candidates]
    if any(type(order) is not int or order < 0 for order in orders):
        raise ValueError("candidate generation order must be a nonnegative integer")
    if len(set(orders)) != len(orders):
        raise ValueError("candidate generation order must be unique")
    rows = {}
    for candidate in candidates:
        scores = candidate.get("scores")
        if not isinstance(scores, list) or len(scores) != len(items):
            raise ValueError("candidate score vectors must match the item count")
        if any(
            isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(score) or not 0 <= score <= 1
            for score in scores
        ):
            raise ValueError("scores must be finite numbers in [0,1]")
        rows[candidate["id"]] = tuple(float(score) for score in scores)
    if len(set(rows.values())) < 2:
        raise ValueError("matrix is non-discriminating")
    ordered_ids = [
        candidate["id"] for candidate in sorted(
            candidates, key=lambda candidate: (candidate["order"], candidate["id"])
        )
    ]
    return ordered_ids, rows, items, candidates


def _pick(candidate_ids, rows, indexes):
    if not indexes:
        raise ValueError("selection requires observed items")
    means = {
        candidate_id: math.fsum(rows[candidate_id][index] for index in indexes) / len(indexes)
        for candidate_id in candidate_ids
    }
    winner = min(candidate_ids, key=lambda candidate_id: (-means[candidate_id], candidate_id))
    return winner, means


def _confirm(candidate_ids, rows, observed, core, item_order):
    survivors = list(candidate_ids)
    ordered_items = list(core) + [index for index in item_order if index not in core]
    prefix_size = len(core)
    rounds = []
    while len(survivors) > 1:
        prefix = ordered_items[:prefix_size]
        for candidate_id in survivors:
            observed[candidate_id].update(prefix)
        winner, means = _pick(survivors, rows, prefix)
        keep = max(1, math.ceil(len(survivors) / 2))
        survivors = sorted(survivors, key=lambda item: (-means[item], item))[:keep]
        rounds.append({
            "items": len(prefix),
            "observed_items": list(prefix),
            "survivors": list(survivors),
        })
        prefix_size = min(
            len(ordered_items), max(prefix_size + 1, prefix_size * 2)
        )
        if len(prefix) == len(ordered_items) and len(survivors) > 1:
            survivors = [winner]
    return survivors[0], rounds


def replay(matrix, core_size=2, warmup_candidates=2, seed=0):
    candidate_ids, rows, items, candidates = _validate(matrix)
    if type(core_size) is not int or not 1 <= core_size < len(items):
        raise ValueError("core size must be smaller than the item count")
    if type(warmup_candidates) is not int or not 1 <= warmup_candidates < len(candidate_ids):
        raise ValueError("warmup candidate count is invalid")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    all_indexes = list(range(len(items)))
    full_winner, full_means = _pick(candidate_ids, rows, all_indexes)
    warmup = candidate_ids[:warmup_candidates]
    informativeness = []
    for index in all_indexes:
        values = [rows[candidate_id][index] for candidate_id in warmup]
        mean = math.fsum(values) / len(values)
        informativeness.append((mean * (1 - mean), index))
    informative_core = [
        index for _, index in sorted(informativeness, key=lambda pair: (-pair[0], pair[1]))
        [:core_size]
    ]
    rng = random.Random(seed)
    random_core = sorted(rng.sample(all_indexes, core_size))
    confirmation_order = list(all_indexes)
    rng.shuffle(confirmation_order)

    policies = {}
    for name, core, confirm in (
        ("shared_random", random_core, False),
        ("shared_informative", informative_core, False),
        ("random_confirmed", random_core, True),
        ("informative_confirmed", informative_core, True),
    ):
        observed = {
            candidate_id: set(all_indexes if candidate_id in warmup else core)
            for candidate_id in candidate_ids
        }
        selected, _ = _pick(candidate_ids, rows, core)
        rounds = []
        if confirm:
            selected, rounds = _confirm(
                candidate_ids, rows, observed, core, confirmation_order
            )
        lost = [
            index for index in all_indexes
            if rows[full_winner][index] >= 1 and rows[selected][index] < 1
        ]
        cells = sum(len(indexes) for indexes in observed.values())
        policies[name] = {
            "selected": selected,
            "agrees_with_full": selected == full_winner,
            "full_score_regret": full_means[full_winner] - full_means[selected],
            "lost_full_winner_successes": lost,
            "evaluation_cells": cells,
            "cell_fraction_of_full": cells / (len(candidate_ids) * len(items)),
            "confirmation_rounds": rounds,
        }

    run_wall_seconds = math.fsum(
        run.get("wall_seconds", 0.0)
        for candidate in candidates for run in candidate.get("runs", [])
        if isinstance(run, dict) and isinstance(run.get("wall_seconds", 0.0), (int, float))
    )
    result = {
        "protocol": "evaluation-allocation-replay-1",
        "input_sha256": _digest(matrix),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seed": seed,
        "candidate_count": len(candidate_ids),
        "item_count": len(items),
        "full_evaluation": {
            "selected": full_winner,
            "scores": full_means,
            "evaluation_cells": len(candidate_ids) * len(items),
        },
        "policies": policies,
        "cost_accounting": {
            "source_collection_wall_seconds": run_wall_seconds,
            "policy_runtime_supported": False,
            "reason": "source reports do not attribute setup/runtime to individual cells",
        },
        "acceptance_passed": False,
        "limits": [
            "Development replay only; protected holdouts are inadmissible.",
            "Evaluation-cell reductions are projections, not measured runtime savings.",
            "Acceptance remains false until setup-inclusive policy runtimes are measured.",
        ],
    }
    result["receipt_sha256"] = _digest(result)
    return result
