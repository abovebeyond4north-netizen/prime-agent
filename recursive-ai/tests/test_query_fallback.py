import unittest

from research.fallback_study import rule_partition
from research.mixed_features import MixedTask
from research.public_queries import acquire, sampled_rules
from research.query_fallback import PublicOracle, acquire_fallback
from research.query_scale import rule_partition as previous_partition


class FallbackTests(unittest.TestCase):
    def test_known_lost_baseline_is_preserved_without_extra_queries(self):
        task = MixedTask(degree=3,p=4,r=3,q=1,d=2)
        label = lambda n:task.expected([(n,)])[0]
        baseline = acquire(label,'fixed',820020)['hypothesis']
        self.assertEqual(baseline['status'],'unique')
        for mode in ('extended_fixed','boundary_fallback'):
            report = acquire_fallback(label,mode,820020)
            self.assertEqual(report['hypothesis'],baseline)
            self.assertEqual(report['label_queries'],64)
            self.assertEqual(report['additional_queries'],0)

    def test_ambiguous_case_stays_within_budget_and_queries_match_report(self):
        task = MixedTask(degree=4,p=4,r=4,q=0,d=3)
        for mode in ('extended_fixed','boundary_fallback'):
            calls = []
            def label(n):
                calls.append(n)
                return task.expected([(n,)])[0]
            report = acquire_fallback(label,mode,2)
            self.assertEqual(report['baseline_hypothesis']['status'],'ambiguous')
            self.assertLessEqual(len(calls),128)
            self.assertEqual(calls,[n for n,_ in report['examples']])
            if report['hypothesis']['status'] == 'unique':
                self.assertEqual(tuple(report['hypothesis']['rule']),(4,4,0,3))

    def test_gateway_rejects_invalid_requests_and_enforces_limit(self):
        oracle = PublicOracle(lambda n:0,1)
        for invalid in (True,-1,2**256):
            with self.assertRaises(ValueError):
                oracle(invalid)
        self.assertEqual(oracle.calls,0)
        self.assertEqual(oracle(0),0)
        with self.assertRaises(RuntimeError):
            oracle(1)
        with self.assertRaises(ValueError):
            PublicOracle(lambda n:True)(1)

    def test_fresh_sample_excludes_every_prior_query_rule(self):
        old = set(sampled_rules(620016)[:6]+sampled_rules(620017)[:6])
        old.update(r for i in range(4) for r in previous_partition(i)[:6])
        fresh = [r for i in range(4) for r in rule_partition(i)[:6]]
        self.assertEqual(len(set(fresh)),24)
        self.assertTrue(set(fresh).isdisjoint(old))


if __name__ == '__main__':
    unittest.main()
