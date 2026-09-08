"""Autonomous sessions terminate with a measured goal assessment or a named limit."""
import fcntl
import hashlib
import json
import math
import time
from pathlib import Path
from core.rollback import VersionController
from sandbox.runner import SandboxRunner
from autonomy.curriculum import certified, coverage, next_task
from autonomy.memory import ResearchMemory
from autonomy.policy import dispatch
from autonomy.search import SearchEngine
from autonomy.tasks import goal_contract, task_from_key
from autonomy.verifier import TaskVerifier


def execute_goal(root, description="algorithms toolkit", tier=2, target=1.0,
                 max_attempts=64, max_seconds=900, max_stagnation=16,
                 max_model_calls=12, max_containers=2000,
                 provider="search", image="recursive-ai-runner:local", task_seed=0, task_count=6):
    for name, value, ceiling in (("attempts", max_attempts, 1000), ("stagnation", max_stagnation, 1000),
                                  ("model calls", max_model_calls, 1000), ("containers", max_containers, 10000)):
        if type(value) is not int or not (0 if name == "model calls" else 1) <= value <= ceiling:
            raise ValueError("invalid budget: " + name)
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= 86400:
        raise ValueError("wall budget must be in (0,86400]")
    if provider not in ("search", "api"):
        raise ValueError("unknown provider")
    contract = goal_contract(description, tier, target, task_seed, task_count)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        memory = ResearchMemory(root)
        try:
            return _session(memory, root, contract, start, max_attempts, max_seconds,
                            max_stagnation, max_model_calls, max_containers, provider, image)
        finally:
            memory.db.close()


def _session(memory, root, contract, start, max_attempts, max_seconds,
             max_stagnation, max_model_calls, max_containers, provider, image):
    memory.register(contract)
    vcs = VersionController(root)
    runner = SandboxRunner(image)
    runner.deadline = start + max_seconds
    runner.stop_file = root / "STOP"
    runner.max_container_runs = max_containers
    verifier = TaskVerifier(runner)
    search = SearchEngine(provider, max_model_calls=max_model_calls)
    parent = memory.current()
    active = vcs.read(parent) if parent else {}
    previous_summary = memory.db.execute("SELECT summary FROM research_goals WHERE id=?", (contract["id"],)).fetchone()[0]
    if previous_summary:
        previous_summary = json.loads(previous_summary)
        if previous_summary["status"] in ("goal_reached", "audit_failed") and previous_summary["checkpoint"] == parent:
            return previous_summary
    initial = coverage(contract, active)
    stagnant = 0
    session_attempts = 0
    stop_reason = "attempt_budget"
    audit = None
    memory.event({"goal_started": contract["id"], "contract": contract, "initial_coverage": initial})

    def budget_reason():
        if runner.stop_file.exists():
            return "operator_stop"
        if time.monotonic() >= runner.deadline:
            return "wall_budget"
        if runner.container_runs >= max_containers:
            return "container_budget"
        return None

    while True:
        reason = budget_reason()
        if reason:
            stop_reason = reason
            break
        if coverage(contract, active) + 1e-12 >= contract["target"]:
            audit = verifier.audit(certified(active), contract)
            stop_reason = "goal_reached" if audit["passed"] else (budget_reason() or "audit_failed")
            break
        used = memory.db.execute("SELECT attempts FROM research_goals WHERE id=?", (contract["id"],)).fetchone()[0]
        if used >= max_attempts:
            break
        if stagnant >= max_stagnation:
            stop_reason = "stagnation"
            break
        task = next_task(contract, active, memory.attempts(contract["id"]))
        if task is None:
            stop_reason = "no_verifiable_task"
            break
        attempt = memory.reserve_attempt(contract["id"], task.key, max_attempts)
        task_attempt = memory.attempts(contract["id"])[task.key]
        session_attempts += 1
        candidate_start = time.monotonic()
        source, policy_source, operator, origin = "", "", "direct", "none"
        report = {"passed": False, "gates": []}
        evidence = memory.operators(task.family)
        parents = memory.parents(task.family)
        error = None
        try:
            if any(task_from_key(key).family == task.family for key in certified(active)):
                operator = "transfer"
            else:
                operator, policy_source = dispatch(runner, evidence)
            if provider == "api" and operator in ("direct", "repair"):
                memory.reserve_model_call(contract["id"], max_model_calls)
            source, origin = search.propose(task, operator, parents, certified(active), task_attempt,
                                           runner.deadline - time.monotonic())
            report = verifier.verify(source, task, active)
        except Exception as exception:
            error = type(exception).__name__
            if "model call budget exhausted" in str(exception):
                stop_reason = "model_call_budget"
        before = coverage(contract, active)
        updated = dict(active)
        passed = report["passed"] is True and len(report.get("gates", [])) == 10 and all(g["passed"] for g in report["gates"])
        if passed:
            updated[task.key] = {"source": source, "report": report, "objective": report["objective"],
                                 "task": task.descriptor(), "origin": origin}
        after = coverage(contract, updated)
        gain = max(0.0, after - before)
        elapsed = time.monotonic() - candidate_start
        failed_gate = next((gate["name"] for gate in report.get("gates", []) if not gate["passed"]), None)
        episode = {"goal_id": contract["id"], "attempt": attempt, "task": task.descriptor(),
                   "operator": operator, "origin": origin, "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                   "parent": parents[0]["digest"] if parents else None, "report": report,
                   "delta": gain, "coverage": after, "seconds": elapsed,
                   "provider": provider, "model_usage": search.model.last_usage,
                   "error_type": error, "failed_gate": failed_gate, "promoted": passed}
        memory.db.execute("BEGIN IMMEDIATE")
        try:
            if passed:
                parent = vcs.snapshot(updated, parent)
                memory.activate(parent)
                episode["checkpoint"] = parent
            if source:
                memory.archive(task, source, report, episode["parent"], operator, float(passed), elapsed)
            if policy_source:
                episode["policy_digest"] = memory.save_policy(policy_source, evidence)
            memory.event(episode)
            memory.db.execute("COMMIT")
        except Exception:
            memory.db.execute("ROLLBACK")
            raise
        active = updated
        stagnant = 0 if gain > 0 else stagnant + 1
        print(json.dumps(episode, sort_keys=True), flush=True)
        if stop_reason == "model_call_budget":
            break
        if failed_gate == "isolation_boot":
            stop_reason = budget_reason() or "isolation_unavailable"
            break
        if error and not source:
            stop_reason = budget_reason() or "generation_or_policy_error"
            break
    summary = {"goal_id": contract["id"], "status": stop_reason, "checkpoint": memory.current(),
               "initial_coverage": initial, "coverage": coverage(contract, active),
               "target": contract["target"], "certified_tasks": sorted(set(contract["weights"]) & set(certified(active))),
               "session_attempts": session_attempts,
               "total_attempts": memory.db.execute("SELECT attempts FROM research_goals WHERE id=?", (contract["id"],)).fetchone()[0],
               "wall_seconds": time.monotonic() - start, "container_runs": runner.container_runs,
               "model_calls": memory.db.execute("SELECT count(*) FROM model_reservations WHERE goal=?", (contract["id"],)).fetchone()[0],
               "audit": audit, "provider": provider, "image": image,
               "policy_revisions": memory.db.execute("SELECT count(*) FROM learning_policies").fetchone()[0]}
    memory.finish(contract["id"], summary)
    print(json.dumps({"summary": summary}, sort_keys=True), flush=True)
    return summary


def status(root):
    memory = ResearchMemory(root)
    try:
        return [{"id": goal_id, "contract": json.loads(contract), "attempts": attempts,
                 "status": state, "summary": json.loads(summary) if summary else None}
                for goal_id, contract, attempts, state, summary in memory.db.execute("SELECT * FROM research_goals")]
    finally:
        memory.db.close()


def solve(root, family, arguments, image="recursive-ai-runner:local"):
    if not isinstance(arguments, list) or len(json.dumps(arguments)) > 100000:
        raise ValueError("arguments must be a bounded JSON array")
    if family == "fibonacci":
        valid = len(arguments) == 1 and type(arguments[0]) is int and 0 <= arguments[0] <= 800
    elif family == "gcd" or family.startswith("compound_"):
        valid = len(arguments) == 2 and all(type(value) is int and value.bit_length() <= 512 for value in arguments)
    else:
        valid = (len(arguments) == 2 and isinstance(arguments[0], list) and len(arguments[0]) <= 10000
                 and type(arguments[1]) is int and arguments[1].bit_length() <= 1024
                 and all(type(value) is int and value.bit_length() <= 1024 for value in arguments[0])
                 and arguments[0] == sorted(arguments[0]))
    if not valid:
        raise ValueError("arguments outside the supported task domain")
    memory = ResearchMemory(root)
    try:
        checkpoint = memory.current()
        active = certified(VersionController(root).read(checkpoint)) if checkpoint else {}
        matching = [(key, skill) for key, skill in active.items() if task_from_key(key).family == family]
        if not matching:
            raise ValueError("skill has no current certification")
        key, skill = max(matching, key=lambda pair: task_from_key(pair[0]).tier)
        runner = SandboxRunner(image)
        runner.boot()
        result = runner.execute(skill["source"], [arguments], entrypoint=family)
        return {"task": key, "checkpoint": checkpoint, "output": result["outputs"][0]}
    finally:
        memory.db.close()
