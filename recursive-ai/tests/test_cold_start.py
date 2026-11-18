import unittest
from research.cold_start import compare


def arm(cost):
    return {'summary':{'status':'goal_reached','audit':{'passed':True},'container_runs':cost,'total_attempts':7},
            'shifted':{'passed':True},'sources':{'task':'normalized-digest'}}

class ColdStartTests(unittest.TestCase):
    def test_cost_outcomes_are_neutral(self):
        self.assertEqual(compare(arm(99),arm(82))['outcome'],'supplied_advantage')
        self.assertEqual(compare(arm(82),arm(82))['outcome'],'tie')
        self.assertEqual(compare(arm(81),arm(82))['outcome'],'learned_advantage')

    def test_unverified_results_are_rejected(self):
        bad=arm(82)
        bad['shifted']['passed']=False
        with self.assertRaises(ValueError):
            compare(arm(99),bad)
        bad=arm(82)
        bad['sources']={'task':'different'}
        with self.assertRaises(ValueError):
            compare(arm(99),bad)

if __name__ == '__main__':
    unittest.main()
