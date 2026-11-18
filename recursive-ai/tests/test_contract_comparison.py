import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.contract_comparison import ARMS, prior_rules, rules, study
from research.public_queries import universe
from research.skill_contract import acquire
from tests.test_skill_contract import OracleRunner, selector


class ComparisonTests(unittest.TestCase):
    def test_disjoint_unfiltered_sample(self):
        selected = rules(0)[:3]+rules(1)[:3]
        self.assertEqual(len(set(selected)), 6)
        self.assertTrue(set(selected).issubset(universe()))
        self.assertFalse(set(selected) & prior_rules())
        self.assertEqual(rules(0)[-1], (5, 1, 1, 1, 1))
        for invalid in (-1, 2, True):
            with self.assertRaises(ValueError):
                rules(invalid)

    def test_orchestration_and_cache_ablation(self):
        def replay(state, task, image, controller):
            return {'output': task.expected([(2**255-1,)])[0], 'containers': 2}
        with tempfile.TemporaryDirectory() as temp, \
                patch('research.skill_contract.acquire_via_process', side_effect=selector), \
                patch('research.skill_contract.SandboxRunner', OracleRunner), \
                patch('research.contract_comparison.replay', side_effect=replay):
            result = study(Path(temp)/'state', 0)
            self.assertTrue(result['parity'])
            self.assertFalse(result['capability_gain_established'])
            for row in result['rows']:
                self.assertEqual(set(row['order']), set(ARMS))
                signatures = [row['arms'][arm]['signature'] for arm in ARMS]
                self.assertEqual(signatures[0], signatures[1])
                self.assertEqual(signatures[0], signatures[2])
            for arm in ('direct', 'controller'):
                self.assertEqual(result['summary'][arm]['repeat_labels'], 0)
                self.assertEqual(result['summary'][arm]['repeat_containers'], 0)
            self.assertGreater(result['summary']['no_reuse']['repeat_labels'], 0)
            self.assertGreater(result['summary']['no_reuse']['repeat_containers'], 0)
            json.dumps(result)

    def test_existing_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'new state'):
                study(temp, 0)

    def test_cost_regression_fails_comparison(self):
        def altered(*args, **kwargs):
            result = acquire(*args, **kwargs)
            result['containers'] += 1
            return result
        with tempfile.TemporaryDirectory() as temp, \
                patch('research.skill_contract.acquire_via_process', side_effect=selector), \
                patch('research.skill_contract.SandboxRunner', OracleRunner), \
                patch('research.contract_comparison.acquire_skill_contract', side_effect=altered), \
                patch('research.contract_comparison.replay', return_value={'output': 0, 'containers': 2}):
            with self.assertRaisesRegex(ValueError, 'cached repeat consumed'):
                study(Path(temp)/'state', 0)


if __name__ == '__main__':
    unittest.main()
