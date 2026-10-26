from pathlib import Path
import tempfile
import unittest

from research.selective_reuse_study import tasks as previous_tasks
from research.selective_reuse_wall_study import evaluate_arm, tasks


class MatchedWallStudyTests(unittest.TestCase):
    def test_tasks_are_fresh_and_include_positive_baseline(self):
        current = tasks()
        self.assertEqual(len(current), 54)
        self.assertEqual(len({(a, b) for _, a, b in current}), len(current))
        self.assertFalse({(a, b) for _, a, b in current} &
                         {(a, b) for _, a, b in previous_tasks()})
        self.assertEqual(sum(name == 'baseline_positive' for name, _, _ in current), 11)

    def test_real_baseline_has_positive_successes(self):
        cohort = [row for row in tasks() if row[0] == 'baseline_positive']
        with tempfile.TemporaryDirectory() as directory:
            arm = evaluate_arm(Path(directory)/'unused', cohort, 'primitive', 500_000_000)
        self.assertTrue(arm['budget_met'])
        self.assertTrue(arm['completed'])
        self.assertGreater(arm['summary']['solved'], 0)

    def test_matched_arm_schema_and_invalid_configuration(self):
        cohort = [('baseline_positive', -1, 3)]
        with tempfile.TemporaryDirectory() as directory:
            arm = evaluate_arm(Path(directory)/'unused', cohort, 'backward_primitive',
                               500_000_000)
        self.assertEqual(arm['wall_budget_ns'], 500_000_000)
        self.assertEqual(arm['summary']['evaluated'], 1)
        self.assertEqual(arm['cohorts']['baseline_positive']['evaluated'], 1)
        for mode, budget in (('bad', 1), ('primitive', 0), ('primitive', True)):
            with self.assertRaises(ValueError):
                evaluate_arm(None, cohort, mode, budget)


if __name__ == '__main__':
    unittest.main()
