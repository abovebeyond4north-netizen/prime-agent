import unittest

from research.composition_search import compress, run, search


class CompositionSearchTests(unittest.TestCase):
    def test_search_and_unseen_inputs(self):
        result = search([(x, 2*x+1) for x in (-2, 0, 3)])
        self.assertEqual(result['status'], 'candidate')
        for x in range(-100, 100):
            self.assertEqual(run(result['program'], x), 2*x+1)

    def test_compression_requires_net_saving(self):
        self.assertIsNone(compress([('double', 'increment')]))
        learned = compress([('double', 'increment')]*5)
        self.assertEqual(learned, ('double', 'increment'))

    def test_macros_pay_expanded_cost(self):
        result = search([(0, 99)], budget=1, macro=('double', 'increment'))
        self.assertEqual(result['cost'], 0)
        self.assertEqual(result['status'], 'exhausted')

    def test_budget_and_program_bounds(self):
        for invalid in (True, -1, 100001):
            with self.assertRaises(ValueError):
                search([(1, 2)], invalid)
        with self.assertRaises(ValueError):
            run(('import',), 1)
        with self.assertRaises(ValueError):
            run(('double',)*33, 1)

    def test_identity_and_ambiguous_public_fit(self):
        self.assertEqual(search([(2, 2)], budget=0)['program'], ())
        result = search([(0, 0)])
        self.assertNotEqual(run(result['program'], 1), 2)

    def test_large_intermediate_values_remain_valid(self):
        self.assertEqual(run(('double',), 10**13), 2*10**13)

    def test_recognize_success_before_budget_exhausts(self):
        examples = [(0, 1), (2, 3)]
        self.assertEqual(search(examples, budget=2)['status'], 'exhausted')
        result = search(examples, budget=2, eager=True)
        self.assertEqual(result['program'], ('increment',))
        self.assertEqual(result['cost'], 2)

    def test_eager_preserves_development_successes_at_no_extra_cost(self):
        for a in (-2, 2, 4):
            for b in range(-3, 4):
                for budget in (0, 3, 30, 300, 3000):
                    examples = [(x, a*x+b) for x in (-2, 0, 3)]
                    old = search(examples, budget)
                    new = search(examples, budget, eager=True)
                    self.assertLessEqual(new['cost'], old['cost'])
                    if old['program'] is not None:
                        self.assertIsNotNone(new['program'])
                    if new['program'] is not None:
                        self.assertTrue(all(run(new['program'], x) == a*x+b for x in range(-10, 11)))

    def test_eager_requires_boolean(self):
        with self.assertRaises(ValueError):
            search([(0, 1)], eager=1)

    def test_inverse_pruning_preserves_development_solutions(self):
        for a in (-4, 2, 8):
            for b in range(-4, 5):
                examples = [(x, a*x+b) for x in (-3, 0, 2)]
                old = search(examples, 3000, eager=True)
                new = search(examples, 3000, eager=True, prune_inverse=True)
                if old['program'] is not None:
                    self.assertEqual(old['program'], new['program'])
                    self.assertLessEqual(new['cost'], old['cost'])
                if new['program'] is not None:
                    self.assertTrue(all(run(new['program'], x) == a*x+b for x in range(-20, 21)))

    def test_pruning_requires_boolean(self):
        with self.assertRaises(ValueError):
            search([(0, 1)], prune_inverse=1)


if __name__ == '__main__':
    unittest.main()
