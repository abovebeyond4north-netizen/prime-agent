import ast
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from autonomy.controller import execute_goal, status
from autonomy.curriculum import certified, coverage, next_task
from autonomy.memory import ResearchMemory
from autonomy.policy import choose, compile_policy, dispatch
from autonomy.search import SKETCHES, SearchEngine, normalized_digest
from autonomy.tasks import FAMILIES, SUITE_VERSION, Task, goal_contract, suite_digest
from autonomy.verifier import TaskVerifier
from core.ast_validator import parse, validate


class ContractRunner:
    """Oracle fake for controller tests; never executes candidate code."""
    def __init__(self, image="fake"):
        self.deadline = self.stop_file = None
        self.container_runs = 0
        self.max_container_runs = 2000

    def boot(self):
        self.container_runs += 1

    def execute(self, source, cases, entrypoint="binary_search", max_steps=500000):
        self.container_runs += 1
        if entrypoint == "choose_operator":
            values = ast.literal_eval(ast.parse(source).body[0].body[0].value)
            outputs = [max(range(len(values)), key=values.__getitem__)]
        else:
            outputs = Task(entrypoint).expected(cases)
        return {"outputs": outputs, "cpu_seconds": 0.001, "peak_bytes": 1000, "steps_per_case": [10] * len(cases)}


def certification(task):
    return {"source": SKETCHES[task.family], "report": {"passed": True, "suite_version": SUITE_VERSION,
            "task": task.key, "suite_digest": suite_digest(), "gates": [{"number": i, "passed": True} for i in range(1, 11)]}}


class AutonomyTests(unittest.TestCase):
    def test_fixed_denominator_and_goal_validation(self):
        contract = goal_contract("count_occurrences", 2)
        self.assertEqual(len(contract["tasks"]), 6)
        self.assertAlmostEqual(sum(contract["weights"].values()), 1)
        self.assertEqual(coverage(contract, {"invented_easy_task": {}}), 0)
        with self.assertRaisesRegex(ValueError, "Unverifiable"):
            goal_contract("become superintelligent")
        for tier, target in [(0, 1), (4, 1), (1, float("nan")), (1, 2)]:
            with self.assertRaises(ValueError):
                goal_contract(tier=tier, target=target)

    def test_oracles_and_difficulty(self):
        for family, value in {"lower_bound": 1, "upper_bound": 3, "binary_search": 1, "count_occurrences": 2}.items():
            self.assertEqual(Task(family).expected([([1, 2, 2, 3], 2)]), [value])
        self.assertEqual(Task("gcd").expected([(0, 0), (-12, 18)]), [0, 6])
        self.assertEqual(Task("fibonacci").expected([(0,), (10,)]), [0, 55])
        self.assertEqual(Task("gcd", 3).samples(10, seed=9), Task("gcd", 3).samples(10, seed=9))
        self.assertNotEqual(Task("gcd", 1).samples(10, seed=9), Task("gcd", 3).samples(10, seed=9))

    def test_curriculum_prerequisites(self):
        contract = goal_contract("count_occurrences", 2)
        self.assertEqual(next_task(contract, {}, {}).family, "lower_bound")
        active = {Task("lower_bound").key: certification(Task("lower_bound"))}
        self.assertEqual(next_task(contract, active, {}).family, "upper_bound")
        active[Task("upper_bound").key] = certification(Task("upper_bound"))
        self.assertEqual(next_task(contract, active, {}).family, "count_occurrences")
        active[Task("upper_bound").key]["report"]["passed"] = False
        self.assertNotIn(Task("upper_bound").key, certified(active))

    def test_policy_code_changes_from_evidence(self):
        before, after = [(0, 0, 0)] * 4, [(1, 0, 1), (2, 2, 1), (1, 0, 1), (1, 0, 1)]
        self.assertNotEqual(compile_policy(before), compile_policy(after))
        self.assertEqual(choose(before), 0)
        self.assertEqual(choose(after), 1)
        operator, source = dispatch(ContractRunner(), after)
        self.assertEqual(operator, "repair")
        validate(parse(source))

    def test_repair_uses_archived_source(self):
        engine = SearchEngine()
        for family in FAMILIES:
            task = Task(family)
            source, _ = engine.propose(task, "direct", [], {}, 1, 60)
            repaired, origin = engine.propose(task, "repair", [{"source": source}], {}, 2, 60)
            self.assertEqual(origin, "archive_return_repair")
            self.assertEqual(normalized_digest(repaired), normalized_digest(SKETCHES[family]))
            validate(parse(repaired))

    def test_composition_reuses_prerequisites(self):
        active = {Task(family).key: certification(Task(family)) for family in ("lower_bound", "upper_bound")}
        source, origin = SearchEngine().propose(Task("count_occurrences"), "direct", [], active, 1, 60)
        self.assertEqual(origin, "skill_composition")
        self.assertEqual({n.name for n in ast.parse(source).body}, {"lower_bound", "upper_bound", "count_occurrences"})

    def test_generalized_ten_gates(self):
        for family in FAMILIES:
            report = TaskVerifier(ContractRunner()).verify(SKETCHES[family], Task(family, 2), {})
            self.assertTrue(report["passed"], report)
            self.assertEqual(len(report["gates"]), 10)
            self.assertEqual(report["random_cases"], 1128)

    def test_step_budget_rejects_bloat(self):
        runner = ContractRunner()
        original = runner.execute
        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            result["steps_per_case"] = [10000] * len(result["outputs"])
            return result
        runner.execute = slow
        report = TaskVerifier(runner).verify(SKETCHES["lower_bound"], Task("lower_bound"), {})
        self.assertFalse(report["passed"])
        self.assertEqual(report["gates"][-1]["name"], "performance")

    def test_goal_completion_resume(self):
        with tempfile.TemporaryDirectory() as root, patch("autonomy.controller.SandboxRunner", ContractRunner), contextlib.redirect_stdout(io.StringIO()):
            result = execute_goal(root, tier=2)
            self.assertEqual(result["status"], "goal_reached", result)
            self.assertEqual(result["coverage"], 1.0)
            self.assertEqual(len(result["certified_tasks"]), 12)
            self.assertTrue(result["audit"]["passed"])
            self.assertEqual(execute_goal(root, tier=2), result)
            self.assertEqual(status(root)[0]["attempts"], result["total_attempts"])

    def test_attempt_limit_persists(self):
        with tempfile.TemporaryDirectory() as root, patch("autonomy.controller.SandboxRunner", ContractRunner), contextlib.redirect_stdout(io.StringIO()):
            result = execute_goal(root, tier=2, max_attempts=1)
            self.assertEqual(result["status"], "attempt_budget")
            again = execute_goal(root, tier=2, max_attempts=1)
            self.assertEqual(again["session_attempts"], 0)
            self.assertEqual(again["total_attempts"], 1)

    def test_stop_file_and_invalid_budget(self):
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stdout(io.StringIO()):
            Path(root, "STOP").touch()
            result = execute_goal(root)
            self.assertEqual(result["status"], "operator_stop")
            self.assertEqual(result["session_attempts"], 0)
            with self.assertRaises(ValueError):
                execute_goal(root, max_seconds=float("nan"))

    def test_audit_failure_is_terminal_for_same_checkpoint(self):
        with tempfile.TemporaryDirectory() as root, patch("autonomy.controller.SandboxRunner", ContractRunner), patch.object(TaskVerifier, "audit", return_value={"passed": False}), contextlib.redirect_stdout(io.StringIO()):
            result = execute_goal(root, description="gcd", tier=1)
            self.assertEqual(result["status"], "audit_failed")
            self.assertEqual(execute_goal(root, description="gcd", tier=1), result)

    def test_model_call_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            memory.reserve_model_call("goal", 1)
            with self.assertRaises(RuntimeError):
                memory.reserve_model_call("goal", 1)
            memory.db.close()

    def test_duplicate_gates_and_stale_certificates_do_not_count(self):
        task = Task("gcd")
        item = certification(task)
        item["report"]["gates"] = [{"number": 1, "passed": True}] * 10
        self.assertEqual(certified({task.key: item}), {})
        item = certification(task)
        item["report"]["suite_digest"] = "old"
        self.assertEqual(certified({task.key: item}), {})

    def test_stagnation_stops_without_inventing_progress(self):
        failed = {"passed": False, "gates": [{"number": 4, "name": "public", "passed": False}]}
        with tempfile.TemporaryDirectory() as root, patch("autonomy.controller.SandboxRunner", ContractRunner), patch.object(TaskVerifier, "verify", return_value=failed), contextlib.redirect_stdout(io.StringIO()):
            result = execute_goal(root, max_stagnation=2)
            self.assertEqual(result["status"], "stagnation")
            self.assertEqual(result["session_attempts"], 2)
            self.assertEqual(result["coverage"], 0)

    def test_missing_docker_fails_closed(self):
        with tempfile.TemporaryDirectory() as root, patch("sandbox.runner.shutil.which", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            result = execute_goal(root, description="gcd", tier=1)
            self.assertEqual(result["status"], "generation_or_policy_error")
            self.assertEqual(result["coverage"], 0)


if __name__ == "__main__":
    unittest.main()
