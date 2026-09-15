import json
import tempfile
import unittest
from pathlib import Path

from research.frontier_discovery import DiscoveryLedger
from research.verified_discovery import parse_verification_plan, run_verified_discovery


PRIMARY = """def experiment(x):
    return 1 if x % 2 == 0 else 0
"""

INDEPENDENT = """def experiment(x):
    if x % 2:
        return 0
    return 1
"""


class FakeRunner:
    def __init__(self, peak=1000):
        self.peak = peak
        self.booted = False
        self.calls = 0

    def boot(self):
        self.booted = True

    def execute(self, source, cases, entrypoint="experiment", max_steps=500000):
        self.calls += 1
        namespace = {}
        exec(source, {"__builtins__": {}}, namespace)
        function = namespace[entrypoint]
        outputs = [function(*case) for case in cases]
        return {"outputs": outputs, "cpu_seconds": 0.001, "peak_bytes": self.peak}


def anchor_candidate(root):
    root = Path(root)
    frontier = root / "frontier-discovery"
    study = "study-1"
    candidate = {
        "id": "candidate-1",
        "kind": "residual_anomaly",
        "statement": "Investigate whether even inputs map to one.",
        "score": 0.8,
        "components": {},
        "evidence_ids": ["observation-1"],
        "domains": ["math"],
        "verification_status": "candidate",
    }
    report_dir = frontier / study
    report_dir.mkdir(parents=True)
    ledger = DiscoveryLedger(frontier / "ledger.jsonl")
    record = ledger.append(
        {
            "event_id": "frontier-event",
            "created_at": "2026-09-15T00:00:00+00:00",
            "study_id": study,
            "input_sha256": "a" * 64,
            "candidate_ids": [candidate["id"]],
            "verification_status": "unverified_candidates_only",
            "candidate_report_sha256": "b" * 64,
        }
    )
    report = {
        "study_id": study,
        "verification_status": "unverified_candidates_only",
        "candidates": [candidate],
        "ledger_record_hash": record["record_hash"],
    }
    (report_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return report, candidate


def plan_for(candidate, expected=None):
    if expected is None:
        expected = [1, 0, 1, 0]
    return {
        "study_id": "study-1",
        "candidate_id": candidate["id"],
        "hypothesis": candidate["statement"],
        "entrypoint": "experiment",
        "primary_source": PRIMARY,
        "independent_source": INDEPENDENT,
        "prediction": {
            "name": "declared prediction",
            "cases": [[2], [3], [4], [5]],
            "expected_outputs": expected,
        },
        "falsification_suites": [
            {
                "name": "boundary counterexamples",
                "cases": [[0], [-1], [-2], [101]],
                "expected_outputs": [1, 0, 1, 0],
            }
        ],
        "replicates": 3,
        "max_cpu_seconds": 0.5,
        "max_peak_bytes": 1000000,
    }


class VerifiedDiscoveryTests(unittest.TestCase):
    def test_verified_requires_preregistration_replication_and_independence(self):
        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate)
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            runner = FakeRunner()
            result = run_verified_discovery(root, plan_path=path, runner=runner)
            report = result["report"]
            self.assertEqual(report["verification_status"], "verified_under_protocol")
            self.assertFalse(report["capability_promotion"])
            self.assertTrue(result["ledger_verified"])
            self.assertIsNotNone(result["verified_knowledge_record_hash"])
            self.assertTrue(runner.booted)
            self.assertEqual(runner.calls, 12)
            ledger = DiscoveryLedger(Path(root) / "verified-discovery" / "ledger.jsonl")
            records = ledger._records()
            self.assertEqual(records[0]["event"], "verification_preregistered")
            self.assertEqual(records[1]["event"], "verification_completed")
            self.assertEqual(records[1]["preregistration_record_hash"], records[0]["record_hash"])

    def test_consensus_counterexample_rejects_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate, expected=[0, 1, 0, 1])
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            result = run_verified_discovery(root, plan_path=path, runner=FakeRunner())
            self.assertEqual(result["report"]["verification_status"], "rejected")
            self.assertIsNone(result["verified_knowledge_record_hash"])

    def test_resource_failure_is_inconclusive_not_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate)
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            result = run_verified_discovery(root, plan_path=path, runner=FakeRunner(peak=2_000_000))
            self.assertEqual(result["report"]["verification_status"], "inconclusive")
            self.assertIsNone(result["verified_knowledge_record_hash"])

    def test_hypothesis_must_match_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate)
            plan["hypothesis"] = "different claim"
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_verified_discovery(root, plan_path=path, runner=FakeRunner())

    def test_independent_source_must_be_structurally_distinct(self):
        candidate = {"id": "candidate-1", "statement": "s"}
        plan = plan_for(candidate)
        plan["independent_source"] = PRIMARY
        with self.assertRaises(ValueError):
            parse_verification_plan(plan)

    def test_requires_falsification_suite_and_three_replicates(self):
        candidate = {"id": "candidate-1", "statement": "s"}
        plan = plan_for(candidate)
        plan["falsification_suites"] = []
        with self.assertRaises(ValueError):
            parse_verification_plan(plan)
        plan = plan_for(candidate)
        plan["replicates"] = 2
        with self.assertRaises(ValueError):
            parse_verification_plan(plan)

    def test_frontier_ledger_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate)
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            ledger_path = Path(root) / "frontier-discovery" / "ledger.jsonl"
            record = json.loads(ledger_path.read_text().splitlines()[0])
            record["candidate_ids"] = []
            ledger_path.write_text(json.dumps(record) + "\n")
            with self.assertRaises(ValueError):
                run_verified_discovery(root, plan_path=path, runner=FakeRunner())

    def test_sandbox_exception_is_inconclusive_and_audited(self):
        class BrokenRunner(FakeRunner):
            def boot(self):
                raise RuntimeError("unavailable")

        with tempfile.TemporaryDirectory() as root:
            _, candidate = anchor_candidate(root)
            plan = plan_for(candidate)
            path = Path(root) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            result = run_verified_discovery(root, plan_path=path, runner=BrokenRunner())
            self.assertEqual(result["report"]["verification_status"], "inconclusive")
            self.assertEqual(result["report"]["execution_error_type"], "RuntimeError")
            ledger = DiscoveryLedger(Path(root) / "verified-discovery" / "ledger.jsonl")
            self.assertTrue(ledger.verify())


if __name__ == "__main__":
    unittest.main()
