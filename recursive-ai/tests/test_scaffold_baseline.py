import unittest
from autonomy.procedure import build_candidate
from autonomy.search import BOUND, normalized_digest
from research.grammar_expansion import PowerTask
from research.scaffold_baseline import PARAMETERS, classify, supplied

class ScaffoldBaselineTests(unittest.TestCase):
    def test_negative_and_tied_outcomes_are_not_reported_as_gains(self):
        left={'passed':True,'containers':30,'normalized_source':'a'}
        self.assertEqual(classify(left,dict(left)), 'tie')
        self.assertEqual(classify(left,dict(left,containers=31)), 'reuse_advantage')
        self.assertEqual(classify(left,dict(left,containers=29)), 'scaffold_advantage')
        self.assertEqual(classify(left,dict(left,passed=False)), 'certification_failure')
        self.assertEqual(classify(left,dict(left,normalized_source='b')), 'different_programs')

    def test_scaffold_and_expected_configuration_construct_same_syntax(self):
        configuration={'upper':'n + 1','direction':'forward','comparison':'<=','result':'low - 1'}
        for degree,p,q,d in PARAMETERS:
            task=PowerTask(degree,p,q,d)
            adapter=supplied(task,{'lower_bound:tier1':{'source':BOUND}})
            candidate=build_candidate(task.family,(p,q,d),degree,configuration)
            self.assertEqual(normalized_digest(adapter), normalized_digest(candidate))

    def test_ambiguous_public_labels_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'uniquely'):
            supplied(PowerTask(4,2,3,4),{'lower_bound:tier1':{'source':BOUND}})

if __name__ == '__main__':
    unittest.main()
