import tempfile
import unittest
from pathlib import Path

from research.public_queries import sampled_rules, universe
from research.query_scale import rule_partition, study


class QueryScaleTests(unittest.TestCase):
    def test_partition_is_disjoint_and_does_not_reuse_development_rules(self):
        partitions = [rule_partition(i) for i in range(4)]
        rules = [rule for part in partitions for rule in part[:6]]
        self.assertEqual(len(set(rules)),24)
        self.assertTrue(set(rules).issubset(set(universe())))
        self.assertTrue(set(rules).isdisjoint(sampled_rules(620016)[:6]+sampled_rules(620017)[:6]))
        self.assertEqual(partitions,[rule_partition(i) for i in range(4)])
        self.assertTrue(all(part[6:] == [(5,1,1,1,1),(3,5,1,1,1)] for part in partitions))

    def test_invalid_shard_and_existing_state_fail_before_execution(self):
        for invalid in (-1,4,True,'0'):
            with self.assertRaises(ValueError):
                rule_partition(invalid)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                study(Path(root),1,0)


if __name__ == '__main__':
    unittest.main()
