import unittest
from autonomy.search import expand_inverse_grammar, infer_inverse_rule
from research.grammar_expansion import PowerTask


class GrammarExpansionTests(unittest.TestCase):
    def test_public_examples_trigger_feature_composition(self):
        for parameters in ((3, 1, 0, 1), (3, 2, 1, 1), (4, 1, 1, 2)):
            task = PowerTask(*parameters)
            cases = task.public()
            labels = [(c[0], y) for c, y in zip(cases, task.expected(cases))]
            self.assertIsNone(infer_inverse_rule(labels))
            result = expand_inverse_grammar(labels)
            self.assertEqual(result['status'], 'unique')
            self.assertEqual(result['degree'], task.degree)
            self.assertEqual(result['rule'], (task.p, task.q, task.d))
            self.assertTrue(all(stage['compatible_rules'] == 0 for stage in result['stages'][:-1]))

    def test_ambiguity_stops_without_expansion_and_exhaustion_is_bounded(self):
        ambiguous = expand_inverse_grammar([(0, 0)])
        self.assertEqual(ambiguous['status'], 'ambiguous')
        self.assertEqual(len(ambiguous['stages']), 1)
        impossible = expand_inverse_grammar([(1, 0), (1, 1)])
        self.assertEqual(impossible['status'], 'expansion_budget_exhausted')
        self.assertEqual(len(impossible['stages']), 3)
        self.assertEqual(sum(s['raw_hypotheses'] for s in impossible['stages']), 240)

    def test_bitwise_oracle_satisfies_exact_postconditions(self):
        for parameters in ((3, 1, 0, 1), (3, 2, 1, 1), (4, 1, 1, 2)):
            task = PowerTask(*parameters)
            cases = task.samples(20, seed=91, audit=True) + task.properties()
            for (n,), k in zip(cases, task.expected(cases)):
                self.assertLessEqual(task.p * k**task.degree + task.q * k, task.d * n)
                self.assertGreater(task.p * (k + 1)**task.degree + task.q * (k + 1), task.d * n)


if __name__ == '__main__':
    unittest.main()
