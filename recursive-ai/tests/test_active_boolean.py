import unittest

from research.active_boolean import discover
from research.boolean_study import BooleanTask, ShiftedTask


def oracle(task):
    return lambda a, b, width: task.expected([(a, b, width)])[0]


class ActiveBooleanTests(unittest.TestCase):
    def test_all_bitwise_rules_survive_public_experiments_without_certification(self):
        for truth in range(16):
            result = discover(oracle(BooleanTask(truth)))
            self.assertEqual(result['status'], 'candidate')
            self.assertEqual(result['public_labels'], 16)
            self.assertFalse(result['certified'])

    def test_shifted_rules_rejected_after_five_queries(self):
        for truth in range(16):
            result = discover(oracle(ShiftedTask(truth)))
            self.assertEqual(result['reason'], 'hypothesis_contradicted')
            self.assertEqual(len(result['observations']), 5)
            self.assertIsNone(result['source'])

    def test_insufficient_budget_abstains_without_exceeding_limit(self):
        for budget in range(4, 16):
            result = discover(oracle(BooleanTask(6)), budget)
            self.assertEqual(result['reason'], 'experiment_budget_exhausted')
            self.assertEqual(len(result['observations']), budget)

    def test_invalid_budget_does_not_query(self):
        def forbidden(*args):
            self.fail('queried invalid budget')
        for budget in (True, 3, 17, 4.0):
            with self.assertRaises(ValueError):
                discover(forbidden, budget)

    def test_invalid_oracle_results_fail_closed(self):
        for value in (True, -1, 2, None):
            with self.assertRaises(ValueError):
                discover(lambda *args: value)

    def test_unprobed_behavior_remains_unproven(self):
        def deceptive(a, b, width):
            return (a ^ b) if width != 64 else 0
        result = discover(deceptive)
        self.assertEqual(result['status'], 'candidate')
        self.assertFalse(result['certified'])
        self.assertNotEqual(deceptive(1, 0, 64), 1)


if __name__ == '__main__':
    unittest.main()
