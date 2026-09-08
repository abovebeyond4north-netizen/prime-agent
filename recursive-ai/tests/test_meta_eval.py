import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from autonomy.memory import OPERATORS
from autonomy.policy import choose_fixed, compile_fixed_policy
from core.ast_validator import parse, validate
from research.meta_eval import run_meta_evaluation, summarize


class MetaEvaluationTests(unittest.TestCase):
    def test_fixed_policy_ignores_rewards_and_cycles(self):
        evidence = [(1, 1000.0, 1.0), (1, 0.0, 1.0), (1, 0.0, 1.0), (0, 0.0, 0.0)]
        self.assertEqual(choose_fixed(evidence), 3)
        source = compile_fixed_policy(evidence)
        validate(parse(source))
        self.assertIn("return 3", source)
        self.assertEqual(len(OPERATORS), 4)

    def test_summary_uses_paired_deltas(self):
        rows = []
        for seed in range(3):
            rows.append({"seed": seed, "mode": "fixed", "goal_reached": True, "audit_passed": True,
                         "coverage": 1.0, "attempts": 5, "wall_seconds": 5.0,
                         "container_runs": 10, "model_calls": 0})
            rows.append({"seed": seed, "mode": "learned", "goal_reached": True, "audit_passed": True,
                         "coverage": 1.0, "attempts": 4, "wall_seconds": 4.0,
                         "container_runs": 8, "model_calls": 0})
        result = summarize(rows)
        self.assertEqual(result["paired_mean_attempt_delta_learned_minus_fixed"], -1.0)
        self.assertEqual(result["paired_attempt_sign_test_p"], 0.25)
        self.assertEqual(result["by_mode"]["learned"]["goal_reached_rate"], 1.0)

    def test_trials_use_isolated_state_and_persist_report(self):
        calls = []

        def fake_execute(root, **kwargs):
            root = Path(root)
            root.mkdir(parents=True, exist_ok=True)
            calls.append((root.name, kwargs["task_seed"], kwargs["policy_mode"]))
            learned = kwargs["policy_mode"] == "learned"
            return {
                "status": "goal_reached",
                "audit": {"passed": True},
                "coverage": 1.0,
                "total_attempts": 3 if learned else 4,
                "wall_seconds": 2.0 if learned else 3.0,
                "container_runs": 6 if learned else 8,
                "model_calls": 0,
                "checkpoint": f"checkpoint-{kwargs['task_seed']}-{kwargs['policy_mode']}",
            }

        with tempfile.TemporaryDirectory() as root, patch("research.meta_eval.execute_goal", side_effect=fake_execute):
            report = run_meta_evaluation(root, replicates=2, base_seed=11, max_seconds=10)
            self.assertEqual(len(report["trials"]), 4)
            self.assertEqual(len({name for name, _, _ in calls}), 4)
            self.assertEqual({seed for _, seed, _ in calls}, {11, 12})
            self.assertEqual({mode for _, _, mode in calls}, {"fixed", "learned"})
            destination = Path(root) / "meta-evaluation" / report["study_id"] / "report.json"
            self.assertTrue(destination.exists())
            persisted = json.loads(destination.read_text())
            self.assertEqual(persisted["study_id"], report["study_id"])
            self.assertEqual(report["summary"]["paired_mean_attempt_delta_learned_minus_fixed"], -1.0)

    def test_invalid_replicates_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                run_meta_evaluation(root, replicates=0)


if __name__ == "__main__":
    unittest.main()
