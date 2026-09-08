"""Run only this trusted controller on the host; candidates execute in Docker."""
import argparse
import fcntl
import hashlib
import json
import time
import uuid
from pathlib import Path
from benchmarks.task_suite import TASK_ID, WEIGHTS
from core.ledger import capability, metrics
from core.rollback import VersionController
from evaluator.verifier import Verifier
from memory.skill_store import MemoryEngine
from sandbox.runner import SandboxRunner
from synthesizer.context_builder import build_context
from synthesizer.generator import CandidateSynthesizer, select_strategy
from autonomy.controller import execute_goal, solve, status as research_status
from autonomy.tasks import goal_contract


def run(root, iterations, provider, image):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        memory = MemoryEngine(root)
        vcs = VersionController(root)
        verifier = Verifier(SandboxRunner(image))
        generator = CandidateSynthesizer(provider)
        previous_rate = 0.0
        for index in range(iterations):
            start = time.monotonic()
            generation = uuid.uuid4().hex
            parent = memory.current()
            active = vcs.read(parent) if parent else {}
            strategy = select_strategy(memory.history())
            source = ""
            try:
                source = generator.generate(strategy, build_context(active, memory.failures()), index)
                report = verifier.verify(source, active)
            except Exception as error:
                report = {"passed": False, "gates": [], "generation_error": type(error).__name__}
            updated = dict(active)
            promoted = False
            if report["passed"]:
                old = active.get(TASK_ID)
                # Require a measurable objective margin for replacements.
                if old is None or report["objective"] > old["objective"] + 0.001:
                    updated[TASK_ID] = {"source": source, "objective": report["objective"], "report": report}
                    promoted = True
            measurement = metrics(capability(active, WEIGHTS), capability(updated, WEIGHTS),
                                  time.monotonic() - start, previous_rate)
            previous_rate = measurement["efficiency_per_second"]
            failed_gate = next((gate["name"] for gate in report["gates"] if not gate["passed"]), None)
            episode = {"generation": generation, "strategy": strategy, "provider": provider,
                       "source": source, "mutation_seed": index, "image": image,
                       "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "report": report,
                       "promoted": promoted, "failed_gate": failed_gate, "metrics": measurement}
            memory.db.execute("BEGIN IMMEDIATE")
            try:
                if promoted:
                    commit = vcs.snapshot(updated, parent)
                    memory.activate(commit)
                    episode["checkpoint"] = commit
                reward = measurement["delta"]
                memory.record(source, report["passed"], strategy, reward, episode)
                memory.db.execute("COMMIT")
            except Exception:
                memory.db.execute("ROLLBACK")
                raise
            print(json.dumps(episode, sort_keys=True), flush=True)
            if failed_gate == "isolation_boot":
                raise RuntimeError("Isolation unavailable; stopped without promotion")
        memory.db.close()


def rollback(root, commit):
    root = Path(root).resolve()
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        memory = MemoryEngine(root)
        vcs = VersionController(root)
        if not memory.db.execute("SELECT 1 FROM checkpoints WHERE sha=?", (commit,)).fetchone():
            raise ValueError("checkpoint was not promoted by this laboratory")
        vcs.read(commit)
        memory.db.execute("BEGIN IMMEDIATE")
        try:
            previous = memory.current()
            memory.activate(commit)
            memory.event({"rollback_from": previous, "rollback_to": commit})
            memory.db.execute("COMMIT")
        except Exception:
            memory.db.execute("ROLLBACK")
            raise
        memory.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "status", "rollback", "autonomous", "plan", "research-status", "solve"])
    parser.add_argument("--state", default=str(Path(__file__).parent / ".lab-state"))
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--provider", choices=["demo", "search", "api"], default="demo")
    parser.add_argument("--image", default="recursive-ai-runner:local")
    parser.add_argument("--checkpoint")
    parser.add_argument("--skill", default="gcd")
    parser.add_argument("--arguments", default="[12,18]")
    parser.add_argument("--goal", default="algorithms toolkit")
    parser.add_argument("--tier", type=int, default=2)
    parser.add_argument("--target", type=float, default=1.0)
    parser.add_argument("--max-attempts", type=int, default=64)
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--max-stagnation", type=int, default=16)
    parser.add_argument("--max-model-calls", type=int, default=12)
    parser.add_argument("--max-containers", type=int, default=2000)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000:
        parser.error("iterations must be in [1, 1000]")
    if args.command == "solve":
        print(json.dumps(solve(args.state, args.skill, json.loads(args.arguments), args.image), indent=2))
    elif args.command == "plan":
        print(json.dumps(goal_contract(args.goal, args.tier, args.target), indent=2))
    elif args.command == "research-status":
        print(json.dumps(research_status(args.state), indent=2))
    elif args.command == "autonomous":
        summary = execute_goal(args.state, args.goal, args.tier, args.target,
                               args.max_attempts, args.max_seconds, args.max_stagnation,
                               args.max_model_calls, args.max_containers,
                               "search" if args.provider == "demo" else args.provider, args.image)
        if summary["status"] != "goal_reached":
            raise SystemExit(2)
    elif args.command == "run":
        run(args.state, args.iterations, "demo" if args.provider == "search" else args.provider, args.image)
    elif args.command == "rollback":
        if not args.checkpoint:
            parser.error("rollback requires --checkpoint")
        rollback(args.state, args.checkpoint)
    else:
        memory = MemoryEngine(args.state)
        print(json.dumps({"checkpoint": memory.current(), "strategies": memory.history(), "evidence": memory.evidence()}, indent=2))
        memory.db.close()


if __name__ == "__main__":
    main()
