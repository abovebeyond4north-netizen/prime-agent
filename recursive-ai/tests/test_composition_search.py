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


if __name__ == '__main__':
    unittest.main()
