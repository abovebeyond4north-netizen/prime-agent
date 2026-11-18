import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import evaluation_allocation_replay, evaluation_allocation_study
from research.evaluation_allocation_study import (
    FROZEN_CONFIG,
    _digest,
    run_development_study,
)


class EvaluationAllocationStudyTests(unittest.TestCase):
    def test_preserved_saturated_receipt_matches_artifact_and_sources(self):
        receipt_path = (
            Path(__file__).resolve().parents[1]
            / "evaluation_allocation_study_results.json"
        )
        raw = receipt_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "54b4d6ddf429fe02f12799ea3bff9fdd49d7c9436a6f368142f039839a4bf204",
        )
        report = json.loads(raw)

        receipt = dict(report)
        receipt_sha256 = receipt.pop("receipt_sha256")
        self.assertEqual(receipt_sha256, _digest(receipt))

        config = dict(report["config"])
        config_sha256 = config.pop("sha256")
        self.assertEqual(config_sha256, _digest(config))
        self.assertEqual(
            config["study_source_sha256"],
            hashlib.sha256(
                Path(evaluation_allocation_study.__file__).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            config["replay_source_sha256"],
            hashlib.sha256(
                Path(evaluation_allocation_replay.__file__).read_bytes()
            ).hexdigest(),
        )

        matrix = dict(report["development_evaluation"])
        matrix_sha256 = matrix.pop("sha256")
        self.assertEqual(matrix_sha256, _digest(matrix))
        candidates = report["development_evaluation"]["matrices"][0]["candidates"]
        self.assertEqual(len(candidates), 4)
        self.assertTrue(
            all(len(candidate["scores"]) == 18 for candidate in candidates)
        )
        self.assertTrue(
            all(sum(candidate["scores"]) == 18 for candidate in candidates)
        )
        self.assertEqual(
            sum(
                run["model_calls"]
                for candidate in candidates
                for run in candidate["runs"]
            ),
            0,
        )
        self.assertEqual(report["screen"]["distinct_score_rows"], 1)
        self.assertEqual(report["screen"]["positive_baseline_successes"], 18)
        self.assertIsNone(report["replay"])
        self.assertFalse(report["acceptance_passed"])
        self.assertTrue(report["cost_accounting"]["matched_trial_budgets"])
        self.assertTrue(
            report["cost_accounting"]["setup_inclusive_wall_supported"]
        )

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

