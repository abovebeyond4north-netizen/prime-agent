import tempfile
import unittest
from unittest.mock import patch

from autonomy.memory import ResearchMemory
from autonomy.policy import choose
from autonomy.search_profile import (
    DEFAULT_SEARCH_PROFILE,
    normalize_search_profile,
    search_profile_digest,
)
from autonomy.tasks import Task
from research.search_policy_evolution import (
    initial_population,
    mutate,
    profile_distance,
    recombine,
    run_search_policy_evolution,
)


class SearchPolicyEvolutionTests(unittest.TestCase):
    def test_search_profile_validation_preserves_old_defaults(self):
        self.assertEqual(
            normalize_search_profile(None),
            DEFAULT_SEARCH_PROFILE,
        )
        self.assertEqual(
            search_profile_digest(None),
            search_profile_digest(DEFAULT_SEARCH_PROFILE),
        )
        invalid = [
            {},
            {
                **DEFAULT_SEARCH_PROFILE,
                "ucb_exploration": 0.0,
            },
            {
                **DEFAULT_SEARCH_PROFILE,
                "parent_quality_weight": 0.0,
                "parent_novelty_weight": 0.0,
                "parent_size_weight": 0.0,
            },
            {
                **DEFAULT_SEARCH_PROFILE,
                "parent_limit": 17,
            },
        ]
        for profile in invalid:
            with self.assertRaises(ValueError):
                normalize_search_profile(profile)

    def test_ucb_exploration_changes_breadth_pressure(self):
        evidence = [
            (100, 80.0, 1.0),
            (10, 5.0, 1.0),
            (100, 30.0, 1.0),
            (100, 20.0, 1.0),
        ]
        self.assertEqual(choose(evidence, exploration=0.05), 0)
        self.assertEqual(choose(evidence, exploration=8.0), 1)

    def test_archive_parent_weights_remain_bounded_and_deterministic(self):
        report_full = {"gates": [{"passed": True}] * 10}
        report_half = {"gates": [{"passed": index < 5} for index in range(10)]}
        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            task = Task("gcd")
            memory.archive(
                task,
                "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n",
                report_full,
                None,
                "direct",
                1.0,
                0.01,
            )
            memory.archive(
                task,
                "def gcd(a, b):\n    a = abs(a)\n    b = abs(b)\n    while b:\n        a, b = b, a % b\n    return a\n",
                report_half,
                None,
                "mutation",
                0.0,
                0.01,
            )
            quality_first = memory.parents(
                "gcd", limit=2, quality_weight=1.0, novelty_weight=0.0, size_weight=0.0
            )
            novelty_first = memory.parents(
                "gcd", limit=2, quality_weight=0.0, novelty_weight=1.0, size_weight=0.0
            )
            self.assertEqual(len(quality_first), 2)
            self.assertEqual(len(novelty_first), 2)
            self.assertEqual(quality_first[0]["quality"], 1.0)
            self.assertEqual(novelty_first[0]["quality"], 1.0)
            with self.assertRaises(ValueError):
                memory.parents(
                    "gcd", quality_weight=0.0, novelty_weight=0.0, size_weight=0.0
                )
            memory.db.close()

        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            task = Task("gcd")
            memory.archive(
                task,
                "def gcd(",
                {"gates": []},
                None,
                "direct",
                0.0,
                0.01,
            )
            self.assertEqual(memory.parents("gcd"), [])
            memory.db.close()

    def test_genome_mutation_recombination_and_novelty(self):
        population = initial_population(4, seed=19)
        child_a = mutate(population[0], seed=7, generation=1)
        child_b = mutate(population[0], seed=7, generation=1)
        self.assertEqual(child_a, child_b)
        self.assertNotEqual(child_a.profile_digest, population[0].profile_digest)
        hybrid = recombine(population[1], population[2], seed=11, generation=1)
        self.assertEqual(hybrid.generation, 1)
        self.assertEqual(len(hybrid.parents), 2)
        self.assertGreater(profile_distance(population[0].profile, population[1].profile), 0)

    def test_successive_halving_saves_trials_and_cross_family_holdout_gates(self):
        calls = []

        def fake_execute(root, **kwargs):
            profile = normalize_search_profile(kwargs.get("search_profile"))
            calls.append((kwargs["description"], kwargs["task_seed"], profile))
            weight_total = (
                profile["parent_quality_weight"]
                + profile["parent_novelty_weight"]
                + profile["parent_size_weight"]
            )
            novelty = profile["parent_novelty_weight"] / weight_total
            # In this deterministic fake, greater exploration and novelty are
            # more sample-efficient, so a non-default policy can be discovered.
            attempts = max(
                1,
                24
                - int(round(min(profile["ucb_exploration"], 4.0) * 2))
                - int(round(novelty * 8)),
            )
            return {
                "status": "goal_reached",
                "audit": {"passed": True},
                "coverage": 1.0,
                "total_attempts": attempts,
                "wall_seconds": attempts / 100.0,
                "container_runs": attempts + 3,
                "model_calls": 0,
                "checkpoint": f"checkpoint-{kwargs['description']}-{kwargs['task_seed']}",
                "search_profile_digest": search_profile_digest(profile),
            }

        with tempfile.TemporaryDirectory() as root, patch(
            "research.search_policy_evolution.execute_goal",
            side_effect=fake_execute,
        ):
            report = run_search_policy_evolution(
                root,
                train_goal="compound arithmetic",
                holdout_goal="sorted search",
                population=4,
                generations=1,
                development_replicates=2,
                holdout_replicates=2,
                base_seed=73,
                task_count=3,
                max_attempts=32,
                max_seconds=30,
                max_model_calls=0,
                max_containers=100,
            )

        efficiency = report["sample_efficiency"]
        self.assertEqual(efficiency["naive_full_evaluation_trials"], 8)
        self.assertEqual(efficiency["actual_development_trials"], 6)
        self.assertEqual(efficiency["trials_avoided"], 2)
        self.assertGreater(efficiency["fraction_saved"], 0)
        self.assertTrue(
            set(report["config"]["train_families"]).isdisjoint(
                report["config"]["holdout_families"]
            )
        )
        comparison = report["cross_family_holdout"]["comparison"]
        self.assertTrue(comparison["all_correct"])
        self.assertTrue(comparison["no_regression"])
        self.assertTrue(comparison["improved"])
        self.assertFalse(report["promotion"]["automatic"])
        self.assertTrue(report["promotion"]["eligible"])
        self.assertTrue(calls)


if __name__ == "__main__":
    unittest.main()
