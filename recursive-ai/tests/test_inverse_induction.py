import unittest
from autonomy.search import BOUND, adapt_inverse_scaffold, infer_inverse_rule
from core.ast_validator import parse, validate
from research.inverse_induction import RuleTask


class InverseInductionTests(unittest.TestCase):
    def test_heldout_predicates_are_uniquely_induced(self):
        for coefficients in ((2, 3, 2), (3, 1, 2), (4, 0, 3)):
            task = RuleTask(*coefficients)
            cases = task.public()
            rule = infer_inverse_rule([(n[0], y) for n, y in zip(cases, task.expected(cases))])
            self.assertEqual(rule, coefficients)
            source = adapt_inverse_scaffold(task.family, {'lower_bound:tier1': {'source': BOUND}}, rule)
            validate(parse(source))

    def test_invalid_rules_do_not_emit_source(self):
        for rule in ((0, 0, 1), (1, 0, 0), (1, 0, 2), (True, 0, 1), (2, 0, 2)):
            with self.assertRaises(ValueError):
                adapt_inverse_scaffold('inverse', {}, rule)

    def test_only_bounded_public_examples_are_admitted(self):
        for examples in ([], [(0, True)], [(2**257, 1)], [(1, 2)], [(0, 0)] * 65):
            with self.assertRaises(ValueError):
                infer_inverse_rule(examples)
        self.assertIsNone(infer_inverse_rule([(0, 0), (1, 0), (1, 1)]))


if __name__ == '__main__':
    unittest.main()
