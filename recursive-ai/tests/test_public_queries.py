import unittest

from research.mixed_features import MixedTask
from research.public_queries import acquire, sampled_rules


class PublicQueryTests(unittest.TestCase):
    def test_policies_obey_label_and_compute_ceilings(self):
        task = MixedTask(degree=3,p=2,r=1,q=0,d=1)
        for mode in ('fixed','random','active'):
            calls = []
            def oracle(n):
                calls.append(n)
                return task.expected([(n,)])[0]
            report = acquire(oracle,mode,123)
            self.assertEqual(report['label_queries'],64)
            self.assertEqual(calls,[n for n,_ in report['examples']])
            self.assertLessEqual(report['prediction_lookups'],200000)
            if report['hypothesis']['status'] == 'unique':
                self.assertEqual(tuple(report['hypothesis']['rule']),(2,1,0,1))

    def test_sampling_and_abstention_are_reproducible(self):
        self.assertEqual(sampled_rules(),sampled_rules())
        report = acquire(lambda n:0,'active',1,prediction_budget=0)
        self.assertEqual(report['hypothesis']['status'],'no_fit')
        self.assertEqual(report['prediction_lookups'],0)
        with self.assertRaises(ValueError):
            acquire(lambda n:True,'fixed',1)


if __name__ == '__main__':
    unittest.main()
