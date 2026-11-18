import copy
import unittest
from unittest.mock import patch
from research.procedure_reuse import acceptance, rediscover


def arm(containers):
    return {'summary': {'status': 'goal_reached', 'audit': {'passed': True},
                        'session_attempts': 3, 'container_runs': containers},
            'sources': {'task': 'digest'}, 'shifted': {'passed': True}}


class ProcedureReuseTests(unittest.TestCase):
    def test_acceptance_requires_gain_and_matching_verified_programs(self):
        result = acceptance(arm(57), arm(91))
        self.assertEqual(result['containers_saved'], 34)
        for field, value in [('sources', {'task': 'different'}), ('shifted', {'passed': False})]:
            bad = arm(91)
            bad[field] = value
            with self.assertRaises(ValueError):
                acceptance(arm(57), bad)
        for field, value in [('status', 'audit_failed'), ('audit', {'passed': False}), ('session_attempts', 4)]:
            bad = arm(91)
            bad['summary'][field] = value
            with self.assertRaises(ValueError):
                acceptance(arm(57), bad)
        with self.assertRaises(ValueError):
            acceptance(arm(91), arm(91))

    def test_ablation_retains_source_and_report_without_mutating_checkpoint(self):
        active = {'task': {'source': 'source', 'report': {'passed': True}, 'procedure_model': {'configuration': 'model'}}}
        before = copy.deepcopy(active)
        with patch('research.procedure_reuse.propose', return_value=('candidate', {}, {})) as proposal:
            rediscover('runner', 'task', active)
        self.assertEqual(active, before)
        self.assertEqual(proposal.call_args.args[2], {'task': {'source': 'source', 'report': {'passed': True}}})


if __name__ == '__main__':
    unittest.main()
