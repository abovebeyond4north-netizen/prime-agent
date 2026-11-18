import unittest

from research.composition_validation import TASKS, TRAINING, coefficients


class ValidationTests(unittest.TestCase):
    def test_disjoint_tasks(self):
        self.assertEqual(len(set(TASKS)), 48)
        self.assertFalse(set(TASKS) & set(TRAINING))
        self.assertTrue(all(a not in (16, 32) for a, _ in TASKS))

    def test_symbolic_certificate(self):
        self.assertEqual(coefficients(()), (1, 0))
        self.assertEqual(coefficients(('double', 'increment')), (2, 1))
        self.assertEqual(coefficients(('increment', 'negate', 'double')), (-2, -2))
        with self.assertRaises(ValueError):
            coefficients(('invalid',))


if __name__ == '__main__':
    unittest.main()
