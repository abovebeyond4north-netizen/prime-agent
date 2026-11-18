import unittest

from research.evaluation_allocation_replay import replay


def matrix():
    return {
        "complete": True,
        "items": [{"task": f"task-{index}"} for index in range(8)],
        "candidates": [
            {"id": "a", "order": 0, "scores": [1, 1, 1, 1, 1, 1, 0, 0],
             "runs": [{"wall_seconds": 2.0}]},
            {"id": "b", "order": 1, "scores": [1, 1, 1, 1, 0, 0, 0, 0],
             "runs": [{"wall_seconds": 2.0}]},
            {"id": "c", "order": 2, "scores": [0, 0, 0, 0, 1, 1, 1, 1],
             "runs": [{"wall_seconds": 2.0}]},
            {"id": "d", "order": 3, "scores": [1, 0, 1, 0, 1, 0, 1, 0],
             "runs": [{"wall_seconds": 2.0}]},
        ],
    }


def core_sensitive_matrix():
    return {
        "complete": True,
        "items": [{"task": f"task-{index}"} for index in range(4)],
        "candidates": [
            {"id": "a", "order": 0, "scores": [1, 0, 1, 1]},
            {"id": "b", "order": 1, "scores": [0, 1, 1, 1]},
            {"id": "c", "order": 2, "scores": [0, 1, 0, 0]},
        ],
    }


class EvaluationAllocationReplayTests(unittest.TestCase):
    def test_replay_has_full_random_informative_and_confirmation_ablations(self):
        report = replay(matrix(), core_size=2, warmup_candidates=2, seed=19)
        self.assertEqual(report["full_evaluation"]["selected"], "a")
        self.assertEqual(set(report["policies"]), {
            "shared_random", "shared_informative",
            "random_confirmed", "informative_confirmed",
        })
        self.assertTrue(report["policies"]["informative_confirmed"]["agrees_with_full"])
        self.assertEqual(
            report["policies"]["informative_confirmed"]["lost_full_winner_successes"], []
        )
        self.assertLess(
            report["policies"]["shared_informative"]["evaluation_cells"],
            report["full_evaluation"]["evaluation_cells"],
        )
        self.assertEqual(report["cost_accounting"]["source_collection_wall_seconds"], 8.0)
        self.assertFalse(report["cost_accounting"]["policy_runtime_supported"])
        self.assertFalse(report["acceptance_passed"])
        self.assertEqual(len(report["receipt_sha256"]), 64)

    def test_replay_is_deterministic(self):
        self.assertEqual(replay(matrix(), seed=7), replay(matrix(), seed=7))

    def test_confirmation_decisions_depend_on_each_policy_core(self):
        report = replay(
            core_sensitive_matrix(), core_size=1, warmup_candidates=2, seed=1
        )
        random_policy = report["policies"]["random_confirmed"]
        informative_policy = report["policies"]["informative_confirmed"]
        self.assertEqual(random_policy["confirmation_rounds"][0]["observed_items"], [1])
        self.assertEqual(
            informative_policy["confirmation_rounds"][0]["observed_items"], [0]
        )
        self.assertNotEqual(
            random_policy["confirmation_rounds"][0]["survivors"],
            informative_policy["confirmation_rounds"][0]["survivors"],
        )
        self.assertNotEqual(random_policy["selected"], informative_policy["selected"])

    def test_rejects_protected_or_non_discriminating_evidence(self):
        protected = matrix()
        protected["holdout_rows_included"] = True
        with self.assertRaisesRegex(ValueError, "holdout"):
            replay(protected)
        tied = matrix()
        for candidate in tied["candidates"]:
            candidate["scores"] = [1] * 8
        with self.assertRaisesRegex(ValueError, "non-discriminating"):
            replay(tied)

    def test_rejects_malformed_matrix_and_protocol(self):
        cases = [
            {},
            {**matrix(), "complete": False},
            {**matrix(), "candidates": matrix()["candidates"][:2]},
            {**matrix(), "items": matrix()["items"][:3]},
            {**matrix(), "candidates": [
                {**candidate, "order": 0} for candidate in matrix()["candidates"]
            ]},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                replay(case)
        with self.assertRaises(ValueError):
            replay(matrix(), core_size=8)
        with self.assertRaises(ValueError):
            replay(matrix(), warmup_candidates=4)
        with self.assertRaises(ValueError):
            replay(matrix(), seed=True)


if __name__ == "__main__":
    unittest.main()
