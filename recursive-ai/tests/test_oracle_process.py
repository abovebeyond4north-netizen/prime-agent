import json
import sys
import unittest
from unittest.mock import patch

from research.fallback_study import rule_partition
from research.mixed_features import MixedTask
from research.oracle_process import acquire_via_process
from research.query_fallback import acquire_fallback


class OracleProcessTests(unittest.TestCase):
    def test_process_matches_frozen_policy_on_all_study_rules_and_controls(self):
        rules = [rule for shard in range(4) for rule in rule_partition(shard)[:6]]
        rules += rule_partition(0)[6:]
        for degree, p, r, q, d in rules:
            task = MixedTask(degree=degree, p=p, r=r, q=q, d=d)
            label = lambda n: task.expected([(n,)])[0]
            for mode in ('extended_fixed', 'boundary_fallback'):
                with self.subTest(rule=(degree, p, r, q, d), mode=mode):
                    expected = json.loads(json.dumps(acquire_fallback(label, mode, 920022)))
                    actual = acquire_via_process(label, mode, 920022)
                    self.assertEqual(actual, expected)

    def run_worker(self, source, label=lambda n: 0, timeout=5):
        with patch('research.oracle_process._command', return_value=[sys.executable, '-c', source]):
            return acquire_via_process(label, 'boundary_fallback', 1, timeout)

    def test_parent_rejects_invalid_request_before_calling_oracle(self):
        calls = []
        with self.assertRaises(ValueError):
            self.run_worker('print(\'{"query":true}\',flush=True); input()', calls.append)
        self.assertEqual(calls, [])

    def test_parent_enforces_budget_independently_of_worker(self):
        calls = []
        def label(n):
            calls.append(n)
            return 0
        with self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
            self.run_worker('for i in range(129):\n print(\'{"query":0}\',flush=True)\n input()', label)
        self.assertEqual(len(calls), 128)

    def test_false_transcript_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'transcript mismatch'):
            self.run_worker('print(\'{"result":{"examples":[[1,0]],"label_queries":1}}\',flush=True)')

    def test_deadline_and_failed_worker_fail_closed(self):
        with self.assertRaises(TimeoutError):
            self.run_worker('import time; time.sleep(10)', timeout=0.1)
        with self.assertRaisesRegex(RuntimeError, 'without a result'):
            self.run_worker('raise SystemExit(1)')

    def test_environment_secrets_are_not_inherited(self):
        source = ('import os,json; '
                  'assert "SELECTOR_TEST_SECRET" not in os.environ; '
                  'print(json.dumps({"result":{"examples":[],"label_queries":0}}),flush=True)')
        with patch.dict('os.environ', {'SELECTOR_TEST_SECRET': 'private'}):
            self.assertEqual(self.run_worker(source)['label_queries'], 0)


if __name__ == '__main__':
    unittest.main()
