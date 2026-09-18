"""Sample-efficient evolution of bounded search-policy configurations.

The search policy controls only:
- UCB exploration pressure for choosing synthesis operators;
- quality/novelty/size weights for archive parent sampling;
- the maximum number of archive parents exposed to synthesis.

It cannot modify task oracles, evaluators, AST policy, sandboxing, holdouts,
promotion rules, or executable controller code.

The study combines:
- quality-diversity archives and branching lineage;
- novelty rejection for near-duplicate policies;
- successive-halving style racing so weak policies receive fewer evaluations;
- a cross-family holdout against the immutable default policy.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

from autonomy.controller import execute_goal
from autonomy.search_profile import (
    DEFAULT_SEARCH_PROFILE,
    SEARCH_PROFILE_KEYS,
    normalize_search_profile,
    search_profile_digest,
)
from autonomy.tasks import goal_contract, task_from_key


NOVELTY_FLOOR = 0.035


def search_policy_protocol_digest():
    root = Path(__file__).resolve().parents[1]
    paths = (
        "research/search_policy_evolution.py",
        "autonomy/controller.py",
        "autonomy/memory.py",
        "autonomy/policy.py",
        "autonomy/search.py",
        "autonomy/search_profile.py",
        "autonomy/verifier.py",
        "core/ast_validator.py",
        "sandbox/runner_harness.py",
    )
    return hashlib.sha256(
        b"".join((root / path).read_bytes() for path in paths)
    ).hexdigest()


@dataclass(frozen=True)
class SearchPolicyGenome:
    ucb_exploration: float
    parent_quality_weight: float
    parent_novelty_weight: float
    parent_size_weight: float
    parent_limit: int
    parents: tuple = ()
    generation: int = 0

    @property
    def profile(self):
        return normalize_search_profile({
            "ucb_exploration": self.ucb_exploration,
            "parent_quality_weight": self.parent_quality_weight,
            "parent_novelty_weight": self.parent_novelty_weight,
            "parent_size_weight": self.parent_size_weight,
            "parent_limit": self.parent_limit,
        })

    @property
    def profile_digest(self):
        return search_profile_digest(self.profile)

    @property
    def id(self):
        payload = {
            "profile": self.profile,
            "parents": list(self.parents),
            "generation": self.generation,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:20]

    def descriptor(self):
        return {
            "id": self.id,
            "profile": self.profile,
            "profile_digest": self.profile_digest,
            "parents": list(self.parents),
            "generation": self.generation,
        }


def genome_from_profile(profile=None, parents=(), generation=0):
    normalized = normalize_search_profile(profile)
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer")
    if not isinstance(parents, (list, tuple)) or any(not isinstance(item, str) for item in parents):
        raise ValueError("parents must be a sequence of genome ids")
    return SearchPolicyGenome(
        normalized["ucb_exploration"],
        normalized["parent_quality_weight"],
        normalized["parent_novelty_weight"],
        normalized["parent_size_weight"],
        normalized["parent_limit"],
        tuple(parents),
        generation,
    )


def genome_from_descriptor(descriptor):
    if not isinstance(descriptor, dict):
        raise ValueError("genome descriptor must be a mapping")
    genome = genome_from_profile(
        descriptor.get("profile"),
        parents=tuple(descriptor.get("parents", ())),
        generation=descriptor.get("generation", 0),
    )
    if descriptor.get("id") is not None and descriptor["id"] != genome.id:
        raise ValueError("genome descriptor id mismatch")
    return genome


def _normalized_vector(profile):
    profile = normalize_search_profile(profile)
    weight_total = math.fsum(
        profile[key]
        for key in (
            "parent_quality_weight",
            "parent_novelty_weight",
            "parent_size_weight",
        )
    )
    return (
        (profile["ucb_exploration"] - 0.05) / 7.95,
        profile["parent_quality_weight"] / weight_total,
        profile["parent_novelty_weight"] / weight_total,
        profile["parent_size_weight"] / weight_total,
        (profile["parent_limit"] - 1) / 15.0,
    )


def profile_distance(left, right):
    a, b = _normalized_vector(left), _normalized_vector(right)
    return math.sqrt(
        math.fsum((x - y) ** 2 for x, y in zip(a, b)) / len(a)
    )


def _bounded(value, low, high):
    return round(min(high, max(low, float(value))), 6)


def mutate(parent, seed, generation, scale=0.35):
    if not isinstance(parent, SearchPolicyGenome):
        raise TypeError("parent must be a SearchPolicyGenome")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or not 0 < scale <= 1:
        raise ValueError("scale must be in (0,1]")
    rng = random.Random(seed)
    profile = parent.profile

    # Multiplicative exploration mutation respects the wide positive range.
    if rng.random() < 0.8:
        profile["ucb_exploration"] = _bounded(
            profile["ucb_exploration"] * math.exp(rng.uniform(-scale, scale)),
            0.05,
            8.0,
        )

    for key in (
        "parent_quality_weight",
        "parent_novelty_weight",
        "parent_size_weight",
    ):
        if rng.random() < 0.75:
            profile[key] = _bounded(
                profile[key] + rng.uniform(-scale, scale),
                0.0,
                4.0,
            )

    if math.fsum(
        profile[key]
        for key in (
            "parent_quality_weight",
            "parent_novelty_weight",
            "parent_size_weight",
        )
    ) <= 0:
        profile["parent_quality_weight"] = 1.0

    if rng.random() < 0.75:
        profile["parent_limit"] = max(
            1,
            min(16, profile["parent_limit"] + rng.choice((-3, -2, -1, 1, 2, 3))),
        )

    child = genome_from_profile(profile, parents=(parent.id,), generation=generation)
    if child.profile_digest == parent.profile_digest:
        profile["ucb_exploration"] = _bounded(
            profile["ucb_exploration"] * (1.25 if profile["ucb_exploration"] < 4 else 0.8),
            0.05,
            8.0,
        )
        child = genome_from_profile(profile, parents=(parent.id,), generation=generation)
    return child


def recombine(left, right, seed, generation):
    if not isinstance(left, SearchPolicyGenome) or not isinstance(right, SearchPolicyGenome):
        raise TypeError("parents must be SearchPolicyGenome values")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    a, b = left.profile, right.profile
    profile = {
        "ucb_exploration": _bounded(
            math.sqrt(a["ucb_exploration"] * b["ucb_exploration"])
            * math.exp(rng.uniform(-0.12, 0.12)),
            0.05,
            8.0,
        ),
        "parent_quality_weight": _bounded(
            (a["parent_quality_weight"] + b["parent_quality_weight"]) / 2
            + rng.uniform(-0.1, 0.1),
            0.0,
            4.0,
        ),
        "parent_novelty_weight": _bounded(
            (a["parent_novelty_weight"] + b["parent_novelty_weight"]) / 2
            + rng.uniform(-0.1, 0.1),
            0.0,
            4.0,
        ),
        "parent_size_weight": _bounded(
            (a["parent_size_weight"] + b["parent_size_weight"]) / 2
            + rng.uniform(-0.1, 0.1),
            0.0,
            4.0,
        ),
        "parent_limit": int(round((a["parent_limit"] + b["parent_limit"]) / 2)),
    }
    if math.fsum(
        profile[key]
        for key in (
            "parent_quality_weight",
            "parent_novelty_weight",
            "parent_size_weight",
        )
    ) <= 0:
        profile["parent_quality_weight"] = 1.0
    return genome_from_profile(
        profile,
        parents=(left.id, right.id),
        generation=generation,
    )


def initial_population(size, seed=0):
    if type(size) is not int or not 2 <= size <= 12:
        raise ValueError("population must be in [2,12]")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    anchors = [
        DEFAULT_SEARCH_PROFILE,
        {
            "ucb_exploration": 0.6,
            "parent_quality_weight": 0.85,
            "parent_novelty_weight": 0.10,
            "parent_size_weight": 0.05,
            "parent_limit": 4,
        },
        {
            "ucb_exploration": 4.0,
            "parent_quality_weight": 0.45,
            "parent_novelty_weight": 0.45,
            "parent_size_weight": 0.10,
            "parent_limit": 12,
        },
        {
            "ucb_exploration": 1.2,
            "parent_quality_weight": 0.60,
            "parent_novelty_weight": 0.15,
            "parent_size_weight": 0.25,
            "parent_limit": 5,
        },
    ]
    result = []
    seen = set()
    for profile in anchors:
        if len(result) >= size:
            break
        genome = genome_from_profile(profile)
        if genome.profile_digest not in seen:
            seen.add(genome.profile_digest)
            result.append(genome)

    rng = random.Random(seed)
    attempts = 0
    while len(result) < size and attempts < size * 100:
        attempts += 1
        raw = {
            "ucb_exploration": round(math.exp(rng.uniform(math.log(0.2), math.log(6.0))), 6),
            "parent_quality_weight": round(rng.uniform(0.1, 1.5), 6),
            "parent_novelty_weight": round(rng.uniform(0.0, 1.5), 6),
            "parent_size_weight": round(rng.uniform(0.0, 0.75), 6),
            "parent_limit": rng.randint(2, 14),
        }
        genome = genome_from_profile(raw)
        if genome.profile_digest in seen:
            continue
        if result and min(profile_distance(genome.profile, item.profile) for item in result) < NOVELTY_FLOOR:
            continue
        seen.add(genome.profile_digest)
        result.append(genome)
    if len(result) != size:
        raise RuntimeError("unable to initialize a sufficiently novel policy population")
    return result


def _trial_row(summary, seed, goal):
    return {
        "seed": seed,
        "goal": goal,
        "status": summary["status"],
        "goal_reached": summary["status"] == "goal_reached",
        "audit_passed": bool(summary.get("audit") and summary["audit"].get("passed")),
        "coverage": float(summary["coverage"]),
        "attempts": int(summary["total_attempts"]),
        "wall_seconds": float(summary["wall_seconds"]),
        "container_runs": int(summary["container_runs"]),
        "model_calls": int(summary["model_calls"]),
        "checkpoint": summary.get("checkpoint"),
        "search_profile_digest": summary.get("search_profile_digest"),
    }


def summarize_trials(rows):
    if not rows:
        raise ValueError("at least one trial is required")
    return {
        "trials": len(rows),
        "goal_reached_rate": statistics.fmean(float(row["goal_reached"]) for row in rows),
        "audit_pass_rate": statistics.fmean(float(row["audit_passed"]) for row in rows),
        "mean_coverage": statistics.fmean(row["coverage"] for row in rows),
        "mean_attempts": statistics.fmean(row["attempts"] for row in rows),
        "mean_wall_seconds": statistics.fmean(row["wall_seconds"] for row in rows),
        "mean_container_runs": statistics.fmean(row["container_runs"] for row in rows),
        "mean_model_calls": statistics.fmean(row["model_calls"] for row in rows),
    }


def fitness_vector(summary):
    return (
        summary["goal_reached_rate"],
        summary["audit_pass_rate"],
        summary["mean_coverage"],
        -summary["mean_attempts"],
        -summary["mean_container_runs"],
        -summary["mean_wall_seconds"],
    )


def _families(goal, tier, seed, task_count):
    contract = goal_contract(goal, tier=tier, task_seed=seed, task_count=task_count)
    return {
        task_from_key(descriptor["key"]).family
        for descriptor in contract["tasks"]
    }


def _evaluate_once(
    study_root,
    genome,
    seed,
    phase,
    goal,
    tier,
    target,
    task_count,
    max_attempts,
    max_seconds,
    max_stagnation,
    max_model_calls,
    max_containers,
    provider,
    image,
):
    trial_root = Path(study_root) / phase / genome.id / f"seed-{seed}"
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
        policy_mode="learned",
        search_profile=genome.profile,
    )
    return _trial_row(summary, seed, goal)


def _generation_rows(record, generation):
    return [
        row for row in record["development_rows"]
        if row.get("generation") == generation
    ]


def _rank_quality_diverse(records, count, generation):
    if not records:
        return []
    ordered = sorted(
        records,
        key=lambda record: (
            fitness_vector(summarize_trials(_generation_rows(record, generation))),
            record["genome"]["id"],
        ),
        reverse=True,
    )
    count = min(count, len(ordered))
    selected = [ordered[0]]
    remaining = ordered[1:]
    rank_quality = {
        record["genome"]["id"]: (len(ordered) - rank) / len(ordered)
        for rank, record in enumerate(ordered)
    }
    while remaining and len(selected) < count:
        def score(record):
            novelty = min(
                profile_distance(record["genome"]["profile"], item["genome"]["profile"])
                for item in selected
            )
            return (
                0.85 * rank_quality[record["genome"]["id"]] + 0.15 * novelty,
                fitness_vector(summarize_trials(_generation_rows(record, generation))),
                record["genome"]["id"],
            )
        choice = max(remaining, key=score)
        remaining.remove(choice)
        selected.append(choice)
    return selected


def _make_next_population(survivors, population, generation, seed, archive):
    genomes = [genome_from_descriptor(survivors[0]["genome"])]
    known_profiles = [
        record["genome"]["profile"]
        for record in archive.values()
    ]
    seen = {genome.profile_digest for genome in genomes}
    rng = random.Random(seed + generation * 1_000_033)
    attempts = 0
    while len(genomes) < population and attempts < population * 200:
        attempts += 1
        if len(survivors) > 1 and attempts % 2 == 0:
            left_index = rng.randrange(len(survivors))
            right_index = (left_index + 1 + rng.randrange(len(survivors) - 1)) % len(survivors)
            child = recombine(
                genome_from_descriptor(survivors[left_index]["genome"]),
                genome_from_descriptor(survivors[right_index]["genome"]),
                rng.randrange(2**31),
                generation,
            )
        else:
            parent = genome_from_descriptor(
                survivors[rng.randrange(len(survivors))]["genome"]
            )
            child = mutate(parent, rng.randrange(2**31), generation)
        if child.profile_digest in seen:
            continue
        if known_profiles and min(
            profile_distance(child.profile, profile) for profile in known_profiles
        ) < NOVELTY_FLOOR:
            continue
        seen.add(child.profile_digest)
        known_profiles.append(child.profile)
        genomes.append(child)
    if len(genomes) != population:
        raise RuntimeError("novelty rejection exhausted the bounded offspring budget")
    return genomes


def _holdout_comparison(finalist, baseline):
    all_correct = (
        finalist["goal_reached_rate"] == 1.0
        and finalist["audit_pass_rate"] == 1.0
        and baseline["goal_reached_rate"] == 1.0
        and baseline["audit_pass_rate"] == 1.0
    )
    no_regression = (
        all_correct
        and finalist["mean_coverage"] + 1e-12 >= baseline["mean_coverage"]
        and finalist["mean_attempts"] <= baseline["mean_attempts"] + 1e-12
        and finalist["mean_container_runs"] <= baseline["mean_container_runs"] + 1e-12
    )
    improved = (
        no_regression
        and (
            finalist["mean_coverage"] > baseline["mean_coverage"] + 1e-12
            or finalist["mean_attempts"] + 1e-12 < baseline["mean_attempts"]
            or finalist["mean_container_runs"] + 1e-12 < baseline["mean_container_runs"]
        )
    )
    status = (
        "holdout_improved" if improved
        else "holdout_non_regression" if no_regression
        else "holdout_regressed" if all_correct
        else "holdout_incomplete"
    )
    return {
        "status": status,
        "all_correct": all_correct,
        "no_regression": no_regression,
        "improved": improved,
        "attempt_delta_finalist_minus_baseline": (
            finalist["mean_attempts"] - baseline["mean_attempts"]
        ),
        "container_delta_finalist_minus_baseline": (
            finalist["mean_container_runs"] - baseline["mean_container_runs"]
        ),
        "coverage_delta_finalist_minus_baseline": (
            finalist["mean_coverage"] - baseline["mean_coverage"]
        ),
    }


def run_search_policy_evolution(
    root,
    train_goal="compound arithmetic",
    holdout_goal="sorted search",
    tier=1,
    target=1.0,
    population=4,
    generations=2,
    development_replicates=2,
    holdout_replicates=2,
    base_seed=2000,
    task_count=4,
    max_attempts=32,
    max_seconds=420,
    max_stagnation=12,
    max_model_calls=0,
    max_containers=1000,
    provider="search",
    image="recursive-ai-runner:local",
):
    for name, value, lower, upper in (
        ("population", population, 2, 12),
        ("generations", generations, 1, 6),
        ("development_replicates", development_replicates, 1, 4),
        ("holdout_replicates", holdout_replicates, 1, 6),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{name} must be in [{lower},{upper}]")
    if type(base_seed) is not int:
        raise ValueError("base_seed must be an integer")
    if population * generations * development_replicates > 192:
        raise ValueError("search-policy study exceeds the 192 development-trial bound")

    development_seed_matrix = [
        [
            base_seed + generation * 10_000 + index
            for index in range(development_replicates)
        ]
        for generation in range(generations)
    ]
    holdout_seeds = [
        base_seed + 100_000 + index for index in range(holdout_replicates)
    ]
    train_families = set()
    for seeds in development_seed_matrix:
        for seed in seeds:
            train_families.update(
                _families(train_goal, tier, seed, task_count)
            )
    holdout_families = _families(holdout_goal, tier, holdout_seeds[0], task_count)
    overlap = train_families & holdout_families
    if overlap:
        raise ValueError(
            "train and holdout task families must be disjoint: "
            + ",".join(sorted(overlap))
        )

    train_suite = goal_contract(
        train_goal, tier=tier, target=target,
        task_seed=development_seed_matrix[0][0], task_count=task_count,
    )
    holdout_suite = goal_contract(
        holdout_goal, tier=tier, target=target,
        task_seed=holdout_seeds[0], task_count=task_count,
    )
    config = {
        "train_goal": train_goal,
        "holdout_goal": holdout_goal,
        "tier": tier,
        "target": target,
        "population": population,
        "generations": generations,
        "development_replicates": development_replicates,
        "holdout_replicates": holdout_replicates,
        "development_seeds_by_generation": development_seed_matrix,
        "holdout_seeds": holdout_seeds,
        "task_count": task_count,
        "max_attempts": max_attempts,
        "max_seconds": max_seconds,
        "max_stagnation": max_stagnation,
        "max_model_calls": max_model_calls,
        "max_containers": max_containers,
        "provider": provider,
        "image": image,
        "train_suite_digest": train_suite["suite_digest"],
        "holdout_suite_digest": holdout_suite["suite_digest"],
        "search_policy_protocol_digest": search_policy_protocol_digest(),
        "evolvable_surface": list(SEARCH_PROFILE_KEYS),
        "selection": "quality_diversity_successive_halving",
        "novelty_floor": NOVELTY_FLOOR,
        "train_families": sorted(train_families),
        "holdout_families": sorted(holdout_families),
        "immutable_boundary": [
            "task families and host oracles",
            "AST safety policy",
            "sandbox configuration",
            "verification gates",
            "development and holdout task definitions",
            "promotion logic",
        ],
    }
    study_id = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    study_root = Path(root).resolve() / "search-policy-evolution" / study_id
    study_root.mkdir(parents=True, exist_ok=True)
    report_path = study_root / "report.json"
    if report_path.exists():
        prior = json.loads(report_path.read_text())
        if prior.get("config") == config:
            return prior

    archive = {}
    generation_reports = []
    current = initial_population(population, seed=base_seed)
    actual_development_trials = 0

    for generation in range(generations):
        generation_records = []
        for genome in current:
            record = archive.setdefault(
                genome.id,
                {
                    "genome": genome.descriptor(),
                    "development_rows": [],
                    "first_generation": generation,
                },
            )
            generation_records.append(record)

        survivors = list(generation_records)
        race_rounds = []
        generation_seeds = development_seed_matrix[generation]
        for round_index, seed in enumerate(generation_seeds):
            for record in survivors:
                if any(
                    row["seed"] == seed and row.get("generation") == generation
                    for row in record["development_rows"]
                ):
                    continue
                genome = genome_from_descriptor(record["genome"])
                row = _evaluate_once(
                    study_root, genome, seed,
                    f"development-generation-{generation}-round-{round_index}",
                    train_goal, tier, target, task_count, max_attempts, max_seconds,
                    max_stagnation, max_model_calls, max_containers, provider, image,
                )
                row["generation"] = generation
                record["development_rows"].append(row)
                actual_development_trials += 1

            keep = (
                max(2, math.ceil(len(survivors) / 2))
                if round_index + 1 < len(generation_seeds)
                else max(2, min(len(survivors), population // 2))
            )
            survivors = _rank_quality_diverse(survivors, keep, generation)
            race_rounds.append({
                "round": round_index,
                "seed": seed,
                "evaluated": len(generation_records) if round_index == 0 else None,
                "survivors": [record["genome"]["id"] for record in survivors],
            })

        generation_reports.append({
            "generation": generation,
            "population": [record["genome"]["id"] for record in generation_records],
            "racing": race_rounds,
            "survivors": [record["genome"]["id"] for record in survivors],
            "best": max(
                survivors,
                key=lambda record: (
                    fitness_vector(summarize_trials(_generation_rows(record, generation))),
                    record["genome"]["id"],
                ),
            )["genome"]["id"],
        })

        if generation + 1 < generations:
            current = _make_next_population(
                survivors, population, generation + 1, base_seed, archive
            )

    final_survivors = [
        archive[genome_id]
        for genome_id in generation_reports[-1]["survivors"]
    ]
    finalist_record = max(
        final_survivors,
        key=lambda record: (
            fitness_vector(
                summarize_trials(
                    _generation_rows(record, generations - 1)
                )
            ),
            record["genome"]["id"],
        ),
    )
    finalist = genome_from_descriptor(finalist_record["genome"])
    baseline = genome_from_profile(DEFAULT_SEARCH_PROFILE)

    def evaluate_holdout(genome, phase):
        rows = [
            _evaluate_once(
                study_root, genome, seed, phase,
                holdout_goal, tier, target, task_count, max_attempts, max_seconds,
                max_stagnation, max_model_calls, max_containers, provider, image,
            )
            for seed in holdout_seeds
        ]
        return {"rows": rows, "summary": summarize_trials(rows)}

    finalist_holdout = evaluate_holdout(finalist, "cross-family-holdout-finalist")
    baseline_holdout = evaluate_holdout(baseline, "cross-family-holdout-baseline")
    comparison = _holdout_comparison(
        finalist_holdout["summary"], baseline_holdout["summary"]
    )

    naive_development_trials = population * generations * development_replicates
    report = {
        "study_id": study_id,
        "config": config,
        "generations": generation_reports,
        "archive": sorted(
            (
                {
                    **record,
                    "development_summary": summarize_trials(record["development_rows"])
                    if record["development_rows"] else None,
                }
                for record in archive.values()
            ),
            key=lambda record: (record["first_generation"], record["genome"]["id"]),
        ),
        "finalist": finalist_record["genome"],
        "baseline": baseline.descriptor(),
        "sample_efficiency": {
            "actual_development_trials": actual_development_trials,
            "naive_full_evaluation_trials": naive_development_trials,
            "trials_avoided": naive_development_trials - actual_development_trials,
            "fraction_saved": (
                1.0 - actual_development_trials / naive_development_trials
                if naive_development_trials else 0.0
            ),
        },
        "cross_family_holdout": {
            "finalist": finalist_holdout,
            "baseline": baseline_holdout,
            "comparison": comparison,
        },
        "promotion": {
            "automatic": False,
            "eligible": comparison["improved"],
            "reason": (
                "A policy is only eligible after correct audited cross-family holdout "
                "performance with no coverage, attempt, or container regression. "
                "Adoption remains a separate reviewed change."
            ),
        },
        "interpretation": (
            "This is bounded search-policy evolution with sample-efficient racing and "
            "cross-family transfer testing. It evaluates search strategy, not evaluator "
            "correctness, and does not establish open-ended recursive self-improvement."
        ),
    }
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(report_path)
    return report
