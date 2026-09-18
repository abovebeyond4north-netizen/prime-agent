import tempfile
import unittest
from unittest.mock import patch

from autonomy.curriculum import (
    DEFAULT_CURRICULUM_PROFILE,
    curriculum_profile_digest,
    next_task,
    normalize_curriculum_profile,
)
from autonomy.memory import ResearchMemory
from autonomy.tasks import SUITE_VERSION, Task, goal_contract, suite_digest
from research.evolution import (
    initial_population,
    mutate,
    profile_distance,
    recombine,
    run_curriculum_evolution,
)


def certification(task):
    return {
        "source": "def placeholder():\n    return 0\n",
        "report": {
            "passed": True,
            "suite_version": SUITE_VERSION,
            "suite_digest": suite_digest(),
            "task": task.key,
            "gates": [{"number": index, "passed": True} for index in range(1, 11)],
        },
    }


class EvolutionTests(unittest.TestCase):
    def test_profile_validation_and_default_compatibility(self):
        self.assertEqual(
            normalize_curriculum_profile(None),
            DEFAULT_CURRICULUM_PROFILE,
        )
        self.assertEqual(
            curriculum_profile_digest(None),
            curriculum_profile_digest(DEFAULT_CURRICULUM_PROFILE),
        )
        for invalid in (
            {},
            {"retry_weight": 1, "family_balance_weight": 0, "unlock_weight": 5},
            {"retry_weight": float("nan"), "family_balance_weight": 0, "unlock_weight": 0},
        ):
            with self.assertRaises(ValueError):
                normalize_curriculum_profile(invalid)

    def test_curriculum_genome_changes_only_eligible_order(self):
        contract = goal_contract("sorted search", tier=1)
        lower = Task("lower_bound")
        active = {lower.key: certification(lower)}
        attempts = {}
        default_choice = next_task(contract, active, attempts)
        self.assertEqual(default_choice.family, "binary_search")

        unlock_profile = {
            "retry_weight": 1.0,
            "family_balance_weight": 0.0,
            "unlock_weight": 4.0,
        }
        evolved_choice = next_task(contract, active, attempts, unlock_profile)
        self.assertEqual(evolved_choice.family, "upper_bound")
        self.assertEqual(evolved_choice.tier, 1)

    def test_mutation_and_recombination_are_deterministic_and_bounded(self):
        population = initial_population(4, seed=17)
        child_a = mutate(population[0], seed=9, generation=1)
        child_b = mutate(population[0], seed=9, generation=1)
        self.assertEqual(child_a, child_b)
        self.assertNotEqual(child_a.profile_digest, population[0].profile_digest)
        hybrid = recombine(population[1], population[2], seed=13, generation=1)
        for value in hybrid.profile.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 4.0)
        self.assertGreater(profile_distance(population[0].profile, population[1].profile), 0)

    def test_candidate_lineage_is_persisted_without_execution(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            task = Task("gcd")
            report = {"gates": [{"passed": True}] * 10}
            first = memory.archive(
                task,
                "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n",
                report,
                None,
                "direct",
                0.0,
                0.01,
            )
            second = memory.archive(
                task,
                "def gcd(a, b):\n    a = abs(a)\n    b = abs(b)\n    while b:\n        a, b = b, a % b\n    return a\n",
                report,
                first,
                "mutation",
                1.0,
                0.01,
                candidate_parents=[first],
                origin="test_mutation",
            )
            edges = memory.lineage("gcd")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0]["child_digest"], second)
            self.assertEqual(edges[0]["parent_digest"], first)
            parents = memory.parents("gcd", limit=2)
            self.assertEqual({row["digest"] for row in parents}, {first, second})
            memory.db.close()

    def test_evolution_uses_fresh_holdout_and_requires_non_regression(self):
        def fake_execute(root, **kwargs):
            profile = normalize_curriculum_profile(kwargs.get("curriculum_profile"))
            # Higher unlock weight is deliberately better in this deterministic
            # fake so the study has a known evolutionary signal.
            attempts = max(1, 20 - int(round(profile["unlock_weight"] * 4)))
            seed = kwargs["task_seed"]
            return {
                "status": "goal_reached",
                "audit": {"passed": True},
                "coverage": 1.0,
                "total_attempts": attempts,
                "wall_seconds": attempts / 100.0,
                "container_runs": attempts + 2,
                "model_calls": 0,
                "checkpoint": f"checkpoint-{seed}",
                "curriculum_profile_digest": curriculum_profile_digest(profile),
            }

        with tempfile.TemporaryDirectory() as root, patch(
            "research.evolution.execute_goal", side_effect=fake_execute
        ):
            report = run_curriculum_evolution(
                root,
                population=4,
                generations=2,
                development_replicates=2,
                holdout_replicates=2,
                base_seed=31,
                max_attempts=32,
                max_seconds=30,
                max_model_calls=0,
                max_containers=100,
            )
        self.assertTrue(
            set(report["config"]["development_seeds"]).isdisjoint(
                report["config"]["holdout_seeds"]
            )
        )
        self.assertGreaterEqual(len(report["archive"]), 4)
        self.assertTrue(report["holdout"]["comparison"]["no_regression"])
        self.assertTrue(report["holdout"]["comparison"]["improved"])
        self.assertFalse(report["promotion"]["automatic"])
        self.assertTrue(report["promotion"]["eligible"])


if __name__ == "__main__":
    unittest.main()
