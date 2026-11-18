import unittest
from unittest.mock import patch

from core.ast_validator import parse, validate
from research.boolean_induction import induce
from research.boolean_study import BooleanTask, DEVELOPMENT, HOLDOUT, ShiftedTask, evaluate


def observations(truth):
    task = BooleanTask(truth)
    return [(*case, value) for case, value in zip(task.public(), task.expected(task.public()))]


class BooleanInductionTests(unittest.TestCase):
    def test_development_coefficients_and_safe_source(self):
        for truth, coefficients in ((6, [0, 1, 1, 0]), (8, [0, 0, 0, 1])):
            result = induce(observations(truth))
            self.assertEqual(result['coefficients'], coefficients)
            self.assertTrue(validate(parse(result['source'])))
        self.assertEqual(set(DEVELOPMENT) | set(HOLDOUT), set(range(16)))
        self.assertFalse(set(DEVELOPMENT) & set(HOLDOUT))

    def test_order_invariant_and_truth_id_not_passed_to_learner(self):
        rows = observations(6)
        self.assertEqual(induce(rows), induce(list(reversed(rows))))

    def test_linear_ablation_abstains_on_interaction(self):
        self.assertEqual(induce(observations(8), 'linear')['status'], 'abstained')
        self.assertEqual(induce(observations(6), 'linear')['status'], 'candidate')
        with patch('research.boolean_study.SandboxRunner') as runner:
            result = evaluate(BooleanTask(8), induce(observations(8), 'linear'), 'unused', 1)
        runner.assert_not_called()
        self.assertEqual(result['containers'], 0)

    def test_malformed_or_incomplete_observations_fail_closed(self):
        rows = observations(6)
        for bad in (rows[:3], rows+[rows[0]], rows[:3]+[rows[0]],
                    [(True, 0, 1, 0)]+rows[1:], [(0, 0, 2, 0)]+rows[1:],
                    [(0, 0, 1, 2)]+rows[1:]):
            with self.assertRaises(ValueError):
                induce(bad)
        with self.assertRaises(ValueError):
            induce(rows, 'unbounded')

    def test_independent_oracle_masks_high_bits(self):
        self.assertEqual(BooleanTask(6).expected([(7, 2, 2)]), [1])
        self.assertEqual(BooleanTask(8).expected([(7, 2, 2)]), [2])
        self.assertEqual(BooleanTask(15).expected([(999, 0, 256)]), [2**256-1])

    def test_public_observations_do_not_prove_word_homogeneity(self):
        ordinary, shifted = BooleanTask(6), ShiftedTask(6)
        self.assertEqual(ordinary.expected(ordinary.public()), shifted.expected(shifted.public()))
        self.assertNotEqual(ordinary.expected([(0, 0, 8)]), shifted.expected([(0, 0, 8)]))


if __name__ == '__main__':
    unittest.main()
