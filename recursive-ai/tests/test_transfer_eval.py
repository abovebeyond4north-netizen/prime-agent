import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from autonomy.memory import ResearchMemory
from autonomy.policy import choose, combine_evidence, transfer_prior
from research.transfer_eval import run_transfer_evaluation


class TransferEvaluationTests(unittest.TestCase):
    def test_transfer_prior_is_bounded_and_prefers_observed_success(self):
        raw = [(1, 0.0, 1.0), (2, 2.0, 2.0), (0, 0.0, 0.0), (0, 0.0, 0.0)]
        prior = transfer_prior(raw, strength=4.0)
        self.assertAlmostEqual(sum(row[0] for row in prior), 4.0)
        combined = combine_evidence([(0, 0.0, 0.0)] * 4, raw, strength=4.0)
        self.assertEqual(choose(combined), 1)
        with self.assertRaises(ValueError):
            transfer_prior(raw, strength=33)
        with self.assertRaises(ValueError):
            combine_evidence([(0, 0.0, 0.0)] * 3, raw)

    def test_global_operator_evidence_aggregates_without_source(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            memory.db.execute("INSERT INTO operator_evidence VALUES (?,?,?,?,?)", ("a", "direct", 2, 1.0, 3.0))
            memory.db.execute("INSERT INTO operator_evidence VALUES (?,?,?,?,?)", ("b", "direct", 3, 2.0, 4.0))
            memory.db.execute("INSERT INTO operator_evidence VALUES (?,?,?,?,?)", ("a", "repair", 1, 1.0, 1.5))
            memory.db.commit()
            evidence = memory.global_operators()
            memory.db.close()
            self.assertEqual(evidence[0], (5, 3.0, 7.0))
            self.assertEqual(evidence[1], (1, 1.0, 1.5))
            self.assertEqual(evidence[2:], [(0, 0.0, 0.0), (0, 0.0, 0.0)])

    def test_overlapping_train_and_holdout_families_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "disjoint"):
                run_transfer_evaluation(root, train_goal="gcd", holdout_goal="number theory", replicates=1)

    def test_only_operator_evidence_crosses_the_transfer_boundary(self):
        calls = []

        def fake_execute(root, **kwargs):
            root = Path(root)
            root.mkdir(parents=True, exist_ok=True)
            description = kwargs["description"]
            if description == "binary_search":
                memory = ResearchMemory(root)
                memory.db.execute("INSERT INTO operator_evidence VALUES (?,?,?,?,?)", ("lower_bound", "direct", 1, 0.0, 1.0))
                memory.db.execute("INSERT INTO operator_evidence VALUES (?,?,?,?,?)", ("lower_bound", "repair", 1, 1.0, 1.0))
                memory.db.commit()
                memory.db.close()
                attempts = 2
            else:
                prior = kwargs.get("policy_prior")
                mode = "fixed" if kwargs["policy_mode"] == "fixed" else ("learned_transfer" if prior is not None else "learned_scratch")
                calls.append({"root": root.name, "mode": mode, "prior": prior})
                attempts = 1 if mode == "learned_transfer" else 2
            return {
                "status": "goal_reached",
                "audit": {"passed": True},
                "coverage": 1.0,
                "total_attempts": attempts,
                "wall_seconds": float(attempts),
                "container_runs": attempts * 2,
                "model_calls": 0,
                "checkpoint": "checkpoint-" + root.name,
                "policy_prior_digest": ("transferred" if kwargs.get("policy_prior") is not None else None),
            }

        with tempfile.TemporaryDirectory() as root, patch("research.transfer_eval.execute_goal", side_effect=fake_execute):
            report = run_transfer_evaluation(
                root,
                train_goal="binary_search",
                holdout_goal="gcd",
                tier=1,
                replicates=2,
                base_seed=7,
                prior_strength=4.0,
                max_seconds=10,
            )
            self.assertEqual(len(report["training_trials"]), 2)
            self.assertEqual(len(report["holdout_trials"]), 6)
            self.assertEqual({call["mode"] for call in calls}, {"fixed", "learned_scratch", "learned_transfer"})
            transfer_calls = [call for call in calls if call["mode"] == "learned_transfer"]
            self.assertTrue(all(call["prior"] is not None for call in transfer_calls))
            self.assertTrue(all(len(call["prior"]) == 4 for call in transfer_calls))
            self.assertTrue(all(call["prior"] is None for call in calls if call["mode"] != "learned_transfer"))
            self.assertEqual(len({call["root"] for call in calls}), 6)
            comparison = report["summary"]["transfer_vs_learned_scratch"]
            self.assertEqual(comparison["mean_attempt_delta_transfer_minus_control"], -1.0)
            destination = Path(root) / "transfer-evaluation" / report["study_id"] / "report.json"
            self.assertTrue(destination.exists())
            persisted = json.loads(destination.read_text())
            self.assertEqual(persisted["config"]["transfer_boundary"], "aggregate_operator_evidence_only")


if __name__ == "__main__":
    unittest.main()
