"""Quality-diversity evolution for bounded curriculum policies.

This module evolves only three numeric task-ordering parameters. Candidate programs
still flow through the existing AST policy, Docker sandbox, ten verification gates,
and independent audit. Evaluator code, task oracles, controller logic, and promotion
rules are never part of the genome.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

from autonomy.controller import execute_goal
from autonomy.curriculum import (
    CURRICULUM_PROFILE_KEYS,
    DEFAULT_CURRICULUM_PROFILE,
    curriculum_profile_digest,
    normalize_curriculum_profile,
)
from autonomy.tasks import goal_contract


@dataclass(frozen=True)
class CurriculumGenome:
    retry_weight: float
    family_balance_weight: float
    unlock_weight: float
    parents: tuple = ()
    generation: int = 0

    @property
    def profile(self):
        return normalize_curriculum_profile({
            "retry_weight": self.retry_weight,
            "family_balance_weight": self.family_balance_weight,
            "unlock_weight": self.unlock_weight,
        })

    @property
    def profile_digest(self):
        return curriculum_profile_digest(self.profile)

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
    normalized = normalize_curriculum_profile(profile)
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer")
    if not isinstance(parents, (list, tuple)) or any(not isinstance(item, str) for item in parents):
        raise ValueError("parents must be a sequence of genome ids")
    return CurriculumGenome(
        normalized["retry_weight"],
        normalized["family_balance_weight"],
        normalized["unlock_weight"],
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


def _bounded(value):
    return round(min(4.0, max(0.0, float(value))), 6)


def profile_distance(left, right):
    a = normalize_curriculum_profile(left)
    b = normalize_curriculum_profile(right)
    squared = sum((a[key] - b[key]) ** 2 for key in CURRICULUM_PROFILE_KEYS)
    return math.sqrt(squared) / (4.0 * math.sqrt(len(CURRICULUM_PROFILE_KEYS)))


def mutate(parent, seed, generation, scale=0.75):
    if not isinstance(parent, CurriculumGenome):
        raise TypeError("parent must be a CurriculumGenome")
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or not 0 < scale <= 2:
        raise ValueError("scale must be in (0,2]")
    rng = random.Random(seed)
    profile = parent.profile
    changed = False
    for key in CURRICULUM_PROFILE_KEYS:
        if rng.random() < 0.75:
            candidate = _bounded(profile[key] + rng.uniform(-scale, scale))
            changed = changed or candidate != profile[key]
            profile[key] = candidate
    if not changed:
        key = CURRICULUM_PROFILE_KEYS[rng.randrange(len(CURRICULUM_PROFILE_KEYS))]
        delta = scale if profile[key] <= 2.0 else -scale
        profile[key] = _bounded(profile[key] + delta)
    return genome_from_profile(profile, parents=(parent.id,), generation=generation)


def recombine(left, right, seed, generation):
    if not isinstance(left, CurriculumGenome) or not isinstance(right, CurriculumGenome):
        raise TypeError("parents must be CurriculumGenome values")
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    a, b = left.profile, right.profile
    profile = {}
    for key in CURRICULUM_PROFILE_KEYS:
        midpoint = (a[key] + b[key]) / 2.0
        profile[key] = _bounded(midpoint + rng.uniform(-0.25, 0.25))
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
        DEFAULT_CURRICULUM_PROFILE,
        {"retry_weight": 0.5, "family_balance_weight": 1.0, "unlock_weight": 0.5},
        {"retry_weight": 1.5, "family_balance_weight": 0.5, "unlock_weight": 1.5},
        {"retry_weight": 0.25, "family_balance_weight": 1.5, "unlock_weight": 2.0},
    ]
    result = []
    seen = set()
    for index, profile in enumerate(anchors):
        if len(result) >= size:
            break
        genome = genome_from_profile(profile, generation=0)
        if genome.profile_digest not in seen:
            seen.add(genome.profile_digest)
            result.append(genome)
    rng = random.Random(seed)
    while len(result) < size:
        profile = {
            key: round(rng.uniform(0.0, 2.5), 6)
            for key in CURRICULUM_PROFILE_KEYS
        }
        genome = genome_from_profile(profile, generation=0)
        if genome.profile_digest not in seen:
            seen.add(genome.profile_digest)
            result.append(genome)
    return result


def _trial_row(summary, seed):
    return {
        "seed": seed,
        "status": summary["status"],
        "goal_reached": summary["status"] == "goal_reached",
        "audit_passed": bool(summary.get("audit") and summary["audit"].get("passed")),
        "coverage": float(summary["coverage"]),
        "attempts": int(summary["total_attempts"]),
        "wall_seconds": float(summary["wall_seconds"]),
        "container_runs": int(summary["container_runs"]),
        "model_calls": int(summary["model_calls"]),
        "checkpoint": summary.get("checkpoint"),
        "curriculum_profile_digest": summary.get("curriculum_profile_digest"),
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
    """Lexicographic objective: correctness first, then measured efficiency."""
    return (
        summary["goal_reached_rate"],
        summary["audit_pass_rate"],
        summary["mean_coverage"],
        -summary["mean_attempts"],
        -summary["mean_container_runs"],
        -summary["mean_wall_seconds"],
    )


def _evaluate_genome(study_root, genome, seeds, phase, goal, tier, target,
                     task_count, max_attempts, max_seconds, max_stagnation,
                     max_model_calls, max_containers, provider, image):
    rows = []
    for seed in seeds:
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
            curriculum_profile=genome.profile,
        )
        rows.append(_trial_row(summary, seed))
    return {"rows": rows, "summary": summarize_trials(rows)}


def _select_quality_diverse(records, count):
    if not records:
        return []
    ordered = sorted(
        records,
        key=lambda record: (fitness_vector(record["development"]["summary"]), record["genome"]["id"]),
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
                0.80 * rank_quality[record["genome"]["id"]] + 0.20 * novelty,
                fitness_vector(record["development"]["summary"]),
                record["genome"]["id"],
            )
        choice = max(remaining, key=score)
        remaining.remove(choice)
        selected.append(choice)
    return selected


def _make_next_population(survivors, population, generation, seed):
    # Preserve one elite and force the rest of each generation to be new
    # branches. This keeps even the minimum population size evolutionary.
    genomes = [genome_from_descriptor(survivors[0]["genome"])]
    seen = {genome.profile_digest for genome in genomes}
    rng = random.Random(seed + generation * 1_000_003)
    attempts = 0
    while len(genomes) < population and attempts < population * 50:
        attempts += 1
        if len(survivors) > 1 and attempts % 2 == 0:
            left_index = rng.randrange(len(survivors))
            right_index = (left_index + 1 + rng.randrange(len(survivors) - 1)) % len(survivors)
            left = genome_from_descriptor(survivors[left_index]["genome"])
            right = genome_from_descriptor(survivors[right_index]["genome"])
            child = recombine(left, right, rng.randrange(2**31), generation)
        else:
            parent_record = survivors[rng.randrange(len(survivors))]
            parent = genome_from_descriptor(parent_record["genome"])
            child = mutate(parent, rng.randrange(2**31), generation)
        if child.profile_digest not in seen:
            seen.add(child.profile_digest)
            genomes.append(child)
    if len(genomes) != population:
        raise RuntimeError("unable to create a diverse bounded population")
    return genomes


def _holdout_comparison(finalist, baseline):
    success = (
        finalist["goal_reached_rate"] == 1.0
        and finalist["audit_pass_rate"] == 1.0
        and baseline["goal_reached_rate"] == 1.0
        and baseline["audit_pass_rate"] == 1.0
    )
    no_regression = (
        success
        and finalist["mean_coverage"] + 1e-12 >= baseline["mean_coverage"]
        and finalist["mean_attempts"] <= baseline["mean_attempts"] + 1e-12
    )
    improved = (
        no_regression
        and (
            finalist["mean_coverage"] > baseline["mean_coverage"] + 1e-12
            or finalist["mean_attempts"] + 1e-12 < baseline["mean_attempts"]
        )
    )
    if improved:
        status = "holdout_improved"
    elif no_regression:
        status = "holdout_non_regression"
    elif success:
        status = "holdout_regressed"
    else:
        status = "holdout_incomplete"
    return {
        "status": status,
        "all_correct": success,
        "no_regression": no_regression,
        "improved": improved,
        "attempt_delta_finalist_minus_baseline": (
            finalist["mean_attempts"] - baseline["mean_attempts"]
        ),
        "coverage_delta_finalist_minus_baseline": (
            finalist["mean_coverage"] - baseline["mean_coverage"]
        ),
    }


def run_curriculum_evolution(
    root,
    goal="compound arithmetic",
    tier=2,
    target=1.0,
    population=4,
    generations=2,
    development_replicates=2,
    holdout_replicates=2,
    base_seed=1000,
    task_count=6,
    max_attempts=64,
    max_seconds=900,
    max_stagnation=16,
    max_model_calls=0,
    max_containers=2000,
    provider="search",
    image="recursive-ai-runner:local",
):
    for name, value, lower, upper in (
        ("population", population, 2, 12),
        ("generations", generations, 1, 8),
        ("development_replicates", development_replicates, 1, 8),
        ("holdout_replicates", holdout_replicates, 1, 8),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{name} must be in [{lower},{upper}]")
    if type(base_seed) is not int:
        raise ValueError("base_seed must be an integer")
    if population * generations * development_replicates > 256:
        raise ValueError("evolution study exceeds the 256 development-trial bound")

    development_seeds = [base_seed + index for index in range(development_replicates)]
    holdout_seeds = [base_seed + 100_000 + index for index in range(holdout_replicates)]
    if set(development_seeds) & set(holdout_seeds):
        raise RuntimeError("holdout seeds must be disjoint from development seeds")

    suite = goal_contract(goal, tier, target, development_seeds[0], task_count)
    config = {
        "goal": goal,
        "tier": tier,
        "target": target,
        "population": population,
        "generations": generations,
        "development_replicates": development_replicates,
        "holdout_replicates": holdout_replicates,
        "development_seeds": development_seeds,
        "holdout_seeds": holdout_seeds,
        "task_count": task_count,
        "max_attempts": max_attempts,
        "max_seconds": max_seconds,
        "max_stagnation": max_stagnation,
        "max_model_calls": max_model_calls,
        "max_containers": max_containers,
        "provider": provider,
        "image": image,
        "suite_digest": suite["suite_digest"],
        "evolvable_surface": list(CURRICULUM_PROFILE_KEYS),
        "immutable_boundary": [
            "task families and oracles",
            "AST safety policy",
            "sandbox configuration",
            "verification gates",
            "holdout seeds during development",
            "promotion logic",
        ],
    }
    study_id = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    study_root = Path(root).resolve() / "curriculum-evolution" / study_id
    study_root.mkdir(parents=True, exist_ok=True)
    report_path = study_root / "report.json"
    if report_path.exists():
        prior = json.loads(report_path.read_text())
        if prior.get("config") == config:
            return prior

    current = initial_population(population, seed=base_seed)
    archive = {}
    generations_report = []

    for generation in range(generations):
        generation_records = []
        for genome in current:
            if genome.id not in archive:
                development = _evaluate_genome(
                    study_root, genome, development_seeds, "development",
                    goal, tier, target, task_count, max_attempts, max_seconds,
                    max_stagnation, max_model_calls, max_containers, provider, image,
                )
                archive[genome.id] = {
                    "genome": genome.descriptor(),
                    "development": development,
                    "first_generation": generation,
                }
            generation_records.append(archive[genome.id])

        all_records = list(archive.values())
        survivor_count = max(2, population // 2)
        survivors = _select_quality_diverse(all_records, survivor_count)
        generations_report.append({
            "generation": generation,
            "population": [record["genome"]["id"] for record in generation_records],
            "survivors": [record["genome"]["id"] for record in survivors],
            "best": max(
                all_records,
                key=lambda record: (
                    fitness_vector(record["development"]["summary"]),
                    record["genome"]["id"],
                ),
            )["genome"]["id"],
        })
        if generation + 1 < generations:
            current = _make_next_population(
                survivors, population, generation + 1, base_seed
            )

    finalist_record = max(
        archive.values(),
        key=lambda record: (
            fitness_vector(record["development"]["summary"]),
            record["genome"]["id"],
        ),
    )
    finalist = genome_from_descriptor(finalist_record["genome"])
    baseline = genome_from_profile(DEFAULT_CURRICULUM_PROFILE)

    finalist_holdout = _evaluate_genome(
        study_root, finalist, holdout_seeds, "holdout-finalist",
        goal, tier, target, task_count, max_attempts, max_seconds,
        max_stagnation, max_model_calls, max_containers, provider, image,
    )
    baseline_holdout = _evaluate_genome(
        study_root, baseline, holdout_seeds, "holdout-baseline",
        goal, tier, target, task_count, max_attempts, max_seconds,
        max_stagnation, max_model_calls, max_containers, provider, image,
    )
    comparison = _holdout_comparison(
        finalist_holdout["summary"], baseline_holdout["summary"]
    )

    report = {
        "study_id": study_id,
        "config": config,
        "generations": generations_report,
        "archive": sorted(
            archive.values(),
            key=lambda record: (record["first_generation"], record["genome"]["id"]),
        ),
        "finalist": finalist_record["genome"],
        "baseline": baseline.descriptor(),
        "holdout": {
            "finalist": finalist_holdout,
            "baseline": baseline_holdout,
            "comparison": comparison,
        },
        "promotion": {
            "automatic": False,
            "eligible": comparison["improved"],
            "reason": (
                "This study produces evidence only. A profile can be adopted by a later "
                "separately verified change; evaluator and controller code are never self-modified."
            ),
        },
        "interpretation": (
            "Quality-diversity evolution of a bounded curriculum policy. Holdout improvement "
            "supports this profile on the declared task distribution only; it is not evidence "
            "of open-ended recursive self-improvement."
        ),
    }
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(report_path)
    return report
