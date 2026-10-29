import tempfile
import unittest
from unittest.mock import patch

from research.evaluation_allocation_study import FROZEN_CONFIG, run_development_study


class EvaluationAllocationStudyTests(unittest.TestCase):
    def test_study_collects_shared_development_matrix_without_holdout(self):
        calls = []

        def fake_evaluate(root, genome, seed, phase, *args):
            calls.append((genome.id, seed, phase))
            task_keys = [f"{seed}:task-{index}" for index in range(6)]
            passed = 2 + genome.profile["parent_limit"] % 4
            return {
                "seed": seed,
                "goal": FROZEN_CONFIG["goal"],
                "status": "attempt_budget",
                "goal_reached": False,
                "audit_passed": False,
                "coverage": passed / len(task_keys),
                "attempts": FROZEN_CONFIG["max_attempts"],
                "wall_seconds": 1.0,
                "container_runs": passed + 1,
                "model_calls": 0,
                "checkpoint": None,
                "search_profile_digest": genome.profile_digest,
                "task_outcomes": {
                    key: index < passed for index, key in enumerate(task_keys)
                },
            }

        with tempfile.TemporaryDirectory() as root, patch(
            "research.evaluation_allocation_study._evaluate_once",
            side_effect=fake_evaluate,
        ):
            report = run_development_study(root)

        self.assertEqual(len(calls), 8)
        self.assertTrue(all(call[2] == "allocation-development" for call in calls))
        self.assertTrue(report["config"]["development_only"])
        self.assertFalse(report["config"]["holdout_rows_included"])
        self.assertEqual(len(report["config"]["development_suite_digests"]), 2)
        self.assertEqual(len(report["config"]["search_policy_protocol_digest"]), 64)
        self.assertEqual(len(report["config"]["replay_source_sha256"]), 64)
        self.assertEqual(report["screen"]["candidate_count"], 4)
        self.assertEqual(report["screen"]["item_count"], 12)
        self.assertGreater(report["screen"]["distinct_score_rows"], 1)
        self.assertGreater(report["screen"]["positive_baseline_successes"], 0)
        self.assertIsNotNone(report["replay"])
        self.assertFalse(report["acceptance_passed"])
        self.assertFalse(report["cost_accounting"]["setup_inclusive_wall_supported"])
        self.assertEqual(len(report["receipt_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
