import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch

from autonomy.controller import execute_goal
from autonomy.search import SKETCHES
from autonomy.tasks import Task, goal_contract
from autonomy.verifier import TaskVerifier
from tests.test_autonomy import ContractRunner, certification


class RegressionReuseTests(unittest.TestCase):
    def test_default_reexecutes_and_opt_in_reuses_only_regression(self):
        task = Task('gcd')
        for enabled, hits in [(False, 0), (True, 1)]:
            runner = ContractRunner()
            verifier = TaskVerifier(runner, enabled)
            for _ in range(2):
                report = verifier.verify(SKETCHES['fibonacci'], Task('fibonacci'),
                                         {task.key: certification(task)})
                self.assertTrue(report['passed'])
                self.assertEqual(report['random_cases'], 1128)
                self.assertEqual(len(report['gates']), 10)
            self.assertEqual(verifier.regression_cache_hits, hits)
            self.assertEqual(verifier.regression_executions, 2 - hits)
            # Each candidate still needs all twelve non-regression containers.
            self.assertEqual(runner.container_runs, 26 - hits)

    def test_source_case_or_image_change_requires_execution(self):
        runner = ContractRunner()
        runner.image = 'fixed-image-a'
        verifier = TaskVerifier(runner, True)
        task = Task('gcd')
        source = SKETCHES['gcd']
        cases = task.public()
        for src, inputs in [(source, cases), (source + '\n', cases), (source, cases[:1])]:
            verifier.check_regression(src, task, inputs)
        runner.image = 'fixed-image-b'
        verifier.check_regression(source, task, cases)
        self.assertEqual(verifier.regression_executions, 4)
        self.assertEqual(verifier.regression_cache_hits, 0)

    def test_failures_and_interruptions_are_not_cached(self):
        verifier = TaskVerifier(ContractRunner(), True)
        task = Task('gcd')
        for failure in [ValueError('output mismatch'), RuntimeError('container budget exhausted')]:
            with patch.object(verifier, 'check', side_effect=failure):
                for _ in range(2):
                    with self.assertRaises(type(failure)):
                        verifier.check_regression(SKETCHES['gcd'], task, task.public())
        self.assertEqual(verifier.regression_executions, 4)
        self.assertEqual(verifier._regression_successes, {})

    def test_candidate_checks_and_audits_never_consult_cache(self):
        verifier = TaskVerifier(ContractRunner(), True)
        task = Task('gcd')
        verifier.check_regression(SKETCHES['gcd'], task, task.public())
        with patch.object(verifier, 'check', side_effect=ValueError('fresh check failed')):
            self.assertFalse(verifier.verify(SKETCHES['gcd'], task, {})['passed'])
            self.assertFalse(verifier.audit({task.key: certification(task)}, goal_contract('gcd', tier=1))['passed'])

    def test_cache_is_bounded_and_new_session_is_cold(self):
        verifier = TaskVerifier(ContractRunner(), True)
        task = Task('gcd')
        for index in range(70):
            verifier.check_regression(SKETCHES['gcd'] + '\n' * index, task, task.public())
        self.assertEqual(len(verifier._regression_successes), 64)
        verifier.check_regression(SKETCHES['gcd'], task, task.public())
        self.assertEqual(verifier.regression_executions, 71)
        fresh = TaskVerifier(verifier.runner, True)
        fresh.check_regression(SKETCHES['gcd'], task, task.public())
        self.assertEqual(fresh.regression_cache_hits, 0)

    def test_controller_mode_validation_and_terminal_summary_separation(self):
        with self.assertRaises(ValueError):
            execute_goal('unused', reuse_regression_checks='yes')
        with tempfile.TemporaryDirectory() as root, patch('autonomy.controller.SandboxRunner', ContractRunner), contextlib.redirect_stdout(io.StringIO()):
            baseline = execute_goal(root, description='number theory', tier=2, max_model_calls=0)
            cached = execute_goal(root, description='number theory', tier=2,
                                  max_model_calls=0, reuse_regression_checks=True)
            self.assertFalse(baseline['reuse_regression_checks'])
            self.assertTrue(cached['reuse_regression_checks'])
            self.assertTrue(cached['audit']['passed'])
            self.assertEqual(cached['regression_cache_hits'], 0)


if __name__ == '__main__':
    unittest.main()
