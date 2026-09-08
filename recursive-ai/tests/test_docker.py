"""Requires a Docker daemon and the locally built runner image."""
import shutil
import unittest
from evaluator.verifier import Verifier
from sandbox.runner import SandboxRunner
from synthesizer.generator import BINARY
from autonomy.policy import dispatch
from autonomy.search import SKETCHES
from autonomy.tasks import FAMILIES, Task
from autonomy.verifier import TaskVerifier


@unittest.skipUnless(shutil.which("docker"), "Docker CLI unavailable")
class DockerIntegrationTests(unittest.TestCase):
    def test_real_ten_gate_execution(self):
        report = Verifier(SandboxRunner()).verify(BINARY, {})
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["gates"]), 10)

    def test_infinite_loop_is_terminated(self):
        runner = SandboxRunner(timeout=5)
        runner.boot()
        with self.assertRaises(RuntimeError):
            runner.execute("def binary_search(values, target):\n    while True:\n        pass\n", [([], 0)])

    def test_mutation_rejected(self):
        runner = SandboxRunner()
        runner.boot()
        with self.assertRaises(RuntimeError):
            runner.execute("def binary_search(values, target):\n    values[0] = 99\n    return 0\n", [([1], 1)])

@unittest.skipUnless(shutil.which("docker"), "Docker CLI unavailable")
class AutonomousDockerTests(unittest.TestCase):
    def test_all_families_in_real_sandbox(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                report = TaskVerifier(SandboxRunner()).verify(SKETCHES[family], Task(family, 2), {})
                self.assertTrue(report["passed"], report)

    def test_linear_search_fails_work_budget(self):
        code = "def lower_bound(values, target):\n    for index in range(len(values)):\n        if values[index] >= target:\n            return index\n    return len(values)\n"
        report = TaskVerifier(SandboxRunner()).verify(code, Task("lower_bound"), {})
        self.assertFalse(report["passed"])
        self.assertEqual(report["gates"][-1]["name"], "performance")

    def test_learned_policy_runs_in_container(self):
        operator, source = dispatch(SandboxRunner(), [(1, 0, 1), (2, 2, 1), (1, 0, 1), (1, 0, 1)])
        self.assertEqual(operator, "repair")


if __name__ == "__main__":
    unittest.main()
