import tempfile
import unittest
from unittest.mock import patch

from autonomy.search_profile import normalize_search_profile, search_profile_digest
from research.selection_comparison import compare_parent_selection, evaluation_integrity_canaries


def fake_execute(root, **kwargs):
    profile = normalize_search_profile(kwargs["search_profile"])
    weight_total = sum(profile[key] for key in
                       ("parent_quality_weight", "parent_novelty_weight", "parent_size_weight"))
    novelty = profile["parent_novelty_weight"] / weight_total
    attempts = max(1, 24 - round(min(profile["ucb_exploration"], 4) * 2) - round(novelty * 8))
    return {
        "status": "goal_reached", "audit": {"passed": True}, "coverage": 1.0,
        "total_attempts": attempts, "wall_seconds": attempts / 100,
        "container_runs": attempts + 3, "model_calls": 0,
        "checkpoint": f"checkpoint-{kwargs['task_seed']}",
        "search_profile_digest": search_profile_digest(profile),
    }


class SelectionComparisonTests(unittest.TestCase):
    def test_comparison_runs_matched_arms_without_promoting(self):
        calls = []
        def record(root, **kwargs):
            calls.append((kwargs["description"], kwargs["task_seed"], str(root)))
            return fake_execute(root, **kwargs)

        with tempfile.TemporaryDirectory() as root, patch(
            "research.search_policy_evolution.execute_goal", side_effect=record
        ):
            report = compare_parent_selection(
                root, train_goal="compound arithmetic", holdout_goal="sorted search",
                population=4, generations=1, development_replicates=2,
                holdout_replicates=6, base_seed=73, task_count=3,
                max_attempts=32, max_model_calls=0,
            )
        self.assertEqual(report["development_trials_per_arm"], 6)
        self.assertEqual(report["holdout_pairs"], 6)
        self.assertEqual(len(calls), 36)
        self.assertEqual(set(report["resource_totals_by_arm"]),
                         {"quality_diversity", "pareto"})
        self.assertEqual(report["resource_totals_by_arm"]["pareto"]["holdout"]["model_calls"], 0)
        self.assertEqual({seed for goal, seed, _ in calls if goal == "sorted search"},
                         {100073 + i for i in range(6)})
        self.assertFalse(report["promotion"]["automatic"])
        self.assertFalse(report["promotion"]["eligible"])
        self.assertEqual(report["holdout_comparison_pareto_minus_quality_diversity"]["pairs"], 6)
        self.assertTrue(report["evaluation_integrity_canaries"]["all_passed"])
        self.assertTrue(all(report["evaluation_integrity_canaries"]["checks"].values()))

    def test_fails_closed_if_shared_baseline_disagrees(self):
        counts = {}
        def inconsistent(root, **kwargs):
            row = fake_execute(root, **kwargs)
            if kwargs["description"] == "sorted search":
                seed = kwargs["task_seed"]
                counts[seed] = counts.get(seed, 0) + 1
                if counts[seed] == 4:
                    row["total_attempts"] += 1
            return row
        with tempfile.TemporaryDirectory() as root, patch(
            "research.search_policy_evolution.execute_goal", side_effect=inconsistent
        ):
            with self.assertRaisesRegex(ValueError, "shared_baseline_consistency"):
                compare_parent_selection(
                    root, train_goal="compound arithmetic", holdout_goal="sorted search",
                    population=2, generations=1, development_replicates=1,
                    holdout_replicates=1, base_seed=73, task_count=2,
                )

    def test_canaries_reject_proxy_gain_without_correctness(self):
        with tempfile.TemporaryDirectory() as root, patch(
            "research.search_policy_evolution.execute_goal", side_effect=fake_execute
        ):
            report_calls = []
            from research.search_policy_evolution import run_search_policy_evolution
            for mode in ("quality_diversity", "pareto"):
                report_calls.append(run_search_policy_evolution(
                    root + "/" + mode, parent_selection=mode,
                    train_goal="compound arithmetic", holdout_goal="sorted search",
                    population=2, generations=1, development_replicates=1,
                    holdout_replicates=2, base_seed=73, task_count=2,
                ))
        report_calls[1]["cross_family_holdout"]["finalist"]["rows"][0]["audit_passed"] = False
        result = evaluation_integrity_canaries(*report_calls)
        self.assertFalse(result["all_passed"])
        self.assertFalse(result["checks"]["correctness_before_resources"])


if __name__ == "__main__":
    unittest.main()
