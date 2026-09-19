import unittest
from research.pareto_selection import pareto_order


def record(name, costs, correct=True):
    return {"name": name, "development_rows": [
        dict(generation=0, goal="gcd", seed=i, attempts=cost,
             container_runs=cost, model_calls=0, coverage=float(correct),
             goal_reached=correct, audit_passed=correct)
        for i, cost in enumerate(costs)
    ]}


class ParetoSelectionTests(unittest.TestCase):
    def test_complementary_specialists_survive(self):
        a, b, c = record("a", [1, 9]), record("b", [9, 1]), record("c", [10, 10])
        fronts = pareto_order([a, b, c], 0)
        self.assertEqual(fronts, [[a, b], [c]])

    def test_correctness_beats_cheap_failure(self):
        a, b = record("correct", [10, 10]), record("failed", [0, 0], False)
        self.assertEqual(pareto_order([b, a], 0), [[a], [b]])

    def test_identical_policies_share_front(self):
        a, b = record("a", [4, 4]), record("b", [4, 4])
        self.assertEqual(pareto_order([a, b], 0), [[a, b]])

    def test_unmatched_and_duplicate_cases_rejected(self):
        with self.assertRaises(ValueError):
            pareto_order([record("a", [1]), record("b", [1, 2])], 0)
        duplicate = record("a", [1, 2])
        duplicate["development_rows"][1]["seed"] = 0
        with self.assertRaises(ValueError):
            pareto_order([duplicate], 0)


if __name__ == "__main__":
    unittest.main()
