"""Ten gates generalized to trusted task contracts with deterministic work limits."""
import hashlib
import json
import math
import statistics
from core.ast_validator import parse, validate
from core.ledger import objective
from evaluator.verifier import GATES
from autonomy.tasks import SUITE_VERSION, Task, task_from_key, suite_digest


class TaskVerifier:
    def __init__(self, runner, reuse_regression_checks=False):
        if type(reuse_regression_checks) is not bool:
            raise ValueError('reuse_regression_checks must be boolean')
        self.runner = runner
        self.reuse_regression_checks = reuse_regression_checks
        self._regression_successes = {}
        self.regression_cache_hits = 0
        self.regression_executions = 0

    def check_regression(self, source, task, cases):
        # Session-local only: protected cases and candidate checks never use this cache.
        key = hashlib.sha256(json.dumps(
            [source, task.key, cases, task.expected(cases), suite_digest(),
             getattr(self.runner, 'image', None)], sort_keys=True
        ).encode()).hexdigest() if self.reuse_regression_checks else None
        if self.reuse_regression_checks and key in self._regression_successes:
            self.regression_cache_hits += 1
            return
        self.regression_executions += 1
        self.check(source, task, cases)
        if self.reuse_regression_checks:
            if len(self._regression_successes) >= 64:
                self._regression_successes.pop(next(iter(self._regression_successes)))
            self._regression_successes[key] = True

    def check(self, source, task, cases):
        result = self.runner.execute(source, cases, entrypoint=task.family)
        expected = task.expected(cases)
        if result["outputs"] != expected:
            raise ValueError("output mismatch")
        return result

    def verify(self, source, task, active):
        gates = []
        measurement = {}
        tested = 0
        initial_cache_hits = self.regression_cache_hits
        for number, name in enumerate(GATES, 1):
            try:
                if number == 1:
                    tree = parse(source)
                elif number == 2:
                    validate(tree)
                    if not any(getattr(node, "name", None) == task.family for node in tree.body):
                        raise ValueError("missing required entrypoint")
                elif number == 3:
                    self.runner.boot()
                elif number == 4:
                    self.check(source, task, task.public())
                elif number == 5:
                    self.check(source, task, task.properties())
                    # Preserve every certified task at its recorded difficulty.
                    for key, skill in active.items():
                        if ":tier" in key:
                            old_task = task_from_key(key)
                        elif key == "binary_search":
                            old_task = Task("binary_search")
                        else:
                            continue
                        self.check_regression(skill["source"], old_task, old_task.public() + old_task.properties())
                elif number == 6:
                    cases = task.samples(128)
                    self.check(source, task, cases)
                    tested += len(cases)
                elif number == 7:
                    self.check(source, task, task.properties())
                elif number == 8:
                    cases = task.performance()
                    trials = [self.check(source, task, cases) for _ in range(3)]
                    measurement = {"cpu_seconds": statistics.median(r["cpu_seconds"] for r in trials),
                                   "peak_bytes": max(r["peak_bytes"] for r in trials),
                                   "max_steps": max(max(r["steps_per_case"]) for r in trials)}
                    limit = task.performance_step_limit
                    if measurement["max_steps"] > limit or measurement["cpu_seconds"] > 0.2 or measurement["peak_bytes"] > 8_000_000:
                        raise ValueError("performance budget exceeded")
                elif number == 9:
                    cases = task.samples(1000)
                    self.check(source, task, cases)
                    tested += len(cases)
                else:
                    cases = task.samples(64)
                    values = [json.dumps(self.check(source, task, cases)["outputs"], separators=(",", ":")) for _ in range(3)]
                    if len(set(values)) != 1:
                        raise ValueError("nondeterministic output")
                gates.append({"number": number, "name": name, "passed": True})
                if number == 5:
                    gates[-1]['reused_regression_checks'] = self.regression_cache_hits - initial_cache_hits
            except Exception as error:
                gates.append({"number": number, "name": name, "passed": False, "error_type": type(error).__name__})
                return {"passed": False, "task": task.key, "suite_version": SUITE_VERSION, "suite_digest": suite_digest(), "gates": gates}
        return {"passed": True, "task": task.key, "suite_version": SUITE_VERSION, "suite_digest": suite_digest(), "gates": gates,
                "random_cases": tested, "measurements": measurement,
                "objective": objective(source, tree, measurement["cpu_seconds"], measurement["peak_bytes"])}

    def audit(self, active, contract):
        reports = []
        for descriptor in contract["tasks"]:
            key = descriptor["key"]
            if key not in active:
                continue
            task = task_from_key(key)
            cases = task.samples(512, audit=True)
            try:
                self.check(active[key]["source"], task, cases)
                passed = True
            except Exception:
                passed = False
            # Exact binomial lower bound for all-success samples, Bonferroni-adjusted.
            alpha = 0.05 / len(contract["tasks"])
            lower = math.exp(math.log(alpha) / len(cases)) if passed else 0.0
            reports.append({"task": key, "passed": passed, "cases": len(cases),
                            "simultaneous_lower_bound": lower})
        return {"passed": bool(reports) and all(report["passed"] and report["simultaneous_lower_bound"] >= contract["audit_lower_bound"] for report in reports),
                "reports": reports, "distribution": "independent shifted audit", "confidence_level": 0.95}
