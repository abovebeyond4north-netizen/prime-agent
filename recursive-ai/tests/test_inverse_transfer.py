import ast
import unittest
from unittest.mock import patch

from autonomy.search import BOUND, SKETCHES, SearchEngine, inverse_transfer
from autonomy.tasks import INVERSE_FAMILIES, Task, goal_contract
from core.ast_validator import parse, validate


class InverseTransferTests(unittest.TestCase):
    def test_new_goals_preserve_default_contract_and_dependencies(self):
        self.assertEqual(len(goal_contract(tier=2)['tasks']), 12)
        contract = goal_contract('numeric inverses', tier=1)
        self.assertEqual([row['family'] for row in contract['tasks']],
                         ['lower_bound', *INVERSE_FAMILIES])

    def test_independent_oracles_cover_boundary_values(self):
        for family in INVERSE_FAMILIES:
            task = Task(family)
            for k in (1, 2, 3, 100, 10**30):
                n = k * k if family == 'integer_sqrt' else k * (k + 1) // 2
                self.assertEqual(task.expected([(n - 1,), (n,), (n + 1,)])[:2], [k - 1, k])

    def test_transfer_requires_recognized_parent_and_valid_syntax(self):
        for family in INVERSE_FAMILIES:
            task = Task(family)
            self.assertIsNone(inverse_transfer(task, {}))
            self.assertIsNone(inverse_transfer(task, {'lower_bound:tier1': {'source': 'def lower_bound(values, target):\n    return 0\n'}}))
            source = inverse_transfer(task, {'lower_bound:tier1': {'source': BOUND}})
            validate(parse(source))
            tree = ast.parse(source)
            self.assertEqual(tree.body[0].name, family)
            self.assertEqual([arg.arg for arg in tree.body[0].args.args], ['n'])
            self.assertIn('high = n + 1', source)
            self.assertIn('return low - 1', source)

    def test_ablation_changes_proposal_without_changing_oracle(self):
        task = Task('integer_sqrt')
        engine = SearchEngine()
        active = {'lower_bound:tier1': {'source': BOUND}}
        source, origin = engine.propose(task, 'direct', [], active, 1, 60)
        self.assertEqual(origin, 'inverse_scaffold_transfer')
        with patch('autonomy.search.inverse_transfer', return_value=None):
            ablated, origin = engine.propose(task, 'direct', [], active, 2, 60)
        self.assertEqual(origin, 'sketch_search')
        self.assertEqual(ablated, SKETCHES['integer_sqrt'])
        self.assertNotEqual(source, ablated)


if __name__ == '__main__':
    unittest.main()
