"""DSL validation and controller tests; fake runner never executes candidate source."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from autonomy.controller import execute_goal, solve, status
from autonomy.curriculum import coverage, next_task
from autonomy.expressions import ExpressionTask, PROBES, canonical, generate_tasks
from autonomy.search import SearchEngine, compile_expression
from autonomy.tasks import Task, goal_contract, task_from_key
from autonomy.verifier import TaskVerifier
from core.ast_validator import parse, validate
from sandbox.runner import SandboxRunner
from main import main
from tests.test_autonomy import ContractRunner, certification


class ExpressionTests(unittest.TestCase):
    def test_legacy_cli_dispatch(self):
        with patch("sys.argv", ["main.py", "run", "--state", "unused"]), patch("main.run") as run:
            main()
            run.assert_called_once_with("unused", 4, "demo", "recursive-ai-runner:local")

    def test_rejects_code_and_unbounded_grammar(self):
        bad = [True, None, 100, "__import__", ["eval", "a"], ["add", "a"],
               {"oracle": "return 0"}, ["gcd", "a", "b", 1]]
        deep = "a"
        for _ in range(7):
            deep = ["abs", deep]
        bad.append(deep)
        for expression in bad:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                canonical(expression)
        for key in ("expression:" + "00" * 2000 + ":tier1", "expression:zz:tier1", "expression:ff:tier1"):
            with self.assertRaises(ValueError):
                task_from_key(key)

    def test_commutative_canonicalization_and_roundtrip(self):
        self.assertEqual(canonical(["gcd", "a", "b"]), canonical(["gcd", "b", "a"]))
        self.assertNotEqual(canonical(["sub", "a", "b"]), canonical(["sub", "b", "a"]))
        for task in generate_tasks(73):
            restored = task_from_key(task.key)
            self.assertEqual(restored, task)
            self.assertEqual(restored.expected(PROBES), task.expected(PROBES))
            self.assertEqual(restored.with_tier(2).family, task.family)

    def test_seeded_admission_and_novelty(self):
        tasks = generate_tasks(73, 12)
        self.assertEqual(tasks, generate_tasks(73, 12))
        self.assertNotEqual(tasks, generate_tasks(74, 12))
        self.assertEqual(len({tuple(task.expected(PROBES)) for task in tasks}), 12)
        for seed, count in [(-1, 1), (0, 0), (0, 13), (True, 1)]:
            with self.assertRaises(ValueError):
                generate_tasks(seed, count)

    def test_oracle_known_values(self):
        task = ExpressionTask(canonical(["add", ["gcd", "a", "b"], ["mul", "a", "b"]]))
        self.assertEqual(task.expected([(0, 0), (-12, 18), (7, 0), (3, 11)]), [0, -210, 7, 34])
        for op, answer in [("sub", -8), ("min", 3), ("max", 11), ("abs", 3)]:
            expression = [op, "a"] if op == "abs" else [op, "a", "b"]
            self.assertEqual(ExpressionTask(canonical(expression)).expected([(3, 11)]), [answer])

    def test_goal_frozen_before_search_and_dependencies(self):
        contract = goal_contract("compound arithmetic", 2, task_seed=73, task_count=3)
        frozen = json.dumps(contract, sort_keys=True)
        self.assertEqual(len(contract["tasks"]), 7)
        self.assertEqual(next_task(contract, {}, {}).family, "gcd")
        gcd = Task("gcd")
        active = {gcd.key: certification(gcd)}
        chosen = next_task(contract, active, {})
        self.assertIsInstance(chosen, ExpressionTask)
        self.assertEqual(chosen.tier, 1)
        self.assertAlmostEqual(coverage(contract, active), 1 / 7)
        active["unrelated"] = {}
        self.assertEqual(json.dumps(contract, sort_keys=True), frozen)
        self.assertAlmostEqual(coverage(contract, active), 1 / 7)

    def test_compiler_requires_and_reuses_verified_primitive(self):
        task = generate_tasks(73, 1)[0]
        with self.assertRaises(ValueError):
            compile_expression(task, {})
        gcd = Task("gcd")
        active = {gcd.key: certification(gcd)}
        code, origin = SearchEngine().propose(task, "direct", [], active, 1, 60)
        self.assertEqual(origin, "expression_compilation")
        self.assertTrue(code.startswith(active[gcd.key]["source"]))
        validate(parse(code))

    def test_goal_checkpoint_resume_and_invocation(self):
        tasks = {task.family: task for task in generate_tasks(73, 3)}

        class ExpressionRunner(ContractRunner):
            def execute(self, source, cases, entrypoint="binary_search", max_steps=500000):
                if entrypoint not in tasks:
                    return super().execute(source, cases, entrypoint, max_steps)
                self.container_runs += 1
                return {"outputs": tasks[entrypoint].expected(cases), "cpu_seconds": 0.001,
                        "peak_bytes": 1000, "steps_per_case": [10] * len(cases)}

        with tempfile.TemporaryDirectory() as root, patch("autonomy.controller.SandboxRunner", ExpressionRunner), contextlib.redirect_stdout(io.StringIO()):
            options = {"description": "compound arithmetic", "tier": 2, "task_seed": 73, "task_count": 3}
            result = execute_goal(root, **options)
            self.assertEqual(result["status"], "goal_reached", result)
            self.assertEqual(result["coverage"], 1)
            self.assertEqual(len(result["certified_tasks"]), 7)
            self.assertEqual(execute_goal(root, **options), result)
            persisted = status(root)[0]["contract"]
            self.assertTrue(all(task_from_key(item["key"]) for item in persisted["tasks"]))
            task = next(iter(tasks.values()))
            self.assertEqual(solve(root, task.family, [-12, 18])["output"], task.expected([(-12, 18)])[0])
            for args in ([True, 1], [2**513, 1], [[1], 2]):
                with self.assertRaises(ValueError):
                    solve(root, task.family, args)


@unittest.skipUnless(shutil.which("docker"), "Docker CLI unavailable")
class ExpressionDockerTests(unittest.TestCase):
    def test_compiled_program_against_independent_interpreter(self):
        gcd = Task("gcd")
        runner = SandboxRunner()
        gcd_report = TaskVerifier(runner).verify(certification(gcd)["source"], gcd, {})
        self.assertTrue(gcd_report["passed"], gcd_report)
        active = {gcd.key: {"source": certification(gcd)["source"], "report": gcd_report}}
        for task in generate_tasks(73, 3):
            with self.subTest(task=task.family):
                code = compile_expression(task, active)
                report = TaskVerifier(runner).verify(code, task.with_tier(2), active)
                self.assertTrue(report["passed"], report)
                wrong = f"def {task.family}(a, b):\n    return 0\n"
                rejection = TaskVerifier(runner).verify(wrong, task, active)
                self.assertFalse(rejection["passed"])
                self.assertEqual(rejection["gates"][-1]["number"], 4)


if __name__ == "__main__":
    unittest.main()
