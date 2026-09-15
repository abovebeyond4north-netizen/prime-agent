import json
import tempfile
import unittest
from pathlib import Path

from research.frontier_discovery import (
    DiscoveryLedger,
    FrontierDiscovery,
    parse_frontier_input,
    run_frontier_discovery,
)


class FrontierDiscoveryTests(unittest.TestCase):
    def sample(self):
        return {
            "claims": [
                {
                    "id": "claim-positive",
                    "subject": "System X",
                    "relation": "requires",
                    "object": "Condition Y",
                    "polarity": True,
                    "confidence": 0.92,
                    "source": "source-a",
                    "domain": "biology",
                    "signature": ["feedback", "threshold", "phase-change"],
                },
                {
                    "id": "claim-negative",
                    "subject": "system x",
                    "relation": "requires",
                    "object": "condition y",
                    "polarity": False,
                    "confidence": 0.86,
                    "source": "source-b",
                    "domain": "economics",
                    "signature": ["feedback", "threshold", "phase-change"],
                },
            ],
            "observations": [
                {
                    "id": "observation-1",
                    "expected": 10.0,
                    "observed": 15.0,
                    "uncertainty": 1.0,
                    "source": "instrument-a",
                    "domain": "physics",
                    "signature": ["feedback", "threshold", "phase-change"],
                    "prior_probability": 0.1,
                    "posterior_probability": 0.8,
                }
            ],
            "known_patterns": ["linear proportional response"],
        }

    def test_detects_independent_contradiction(self):
        engine = FrontierDiscovery(parse_frontier_input(self.sample()))
        candidates = engine.contradiction_candidates()
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.kind, "contradiction")
        self.assertEqual(set(candidate.evidence_ids), {"claim-positive", "claim-negative"})
        self.assertGreater(candidate.score, 0.7)
        self.assertEqual(candidate.verification_status, "candidate")

    def test_residual_uses_standardized_deviation_and_bayesian_surprise(self):
        engine = FrontierDiscovery(parse_frontier_input(self.sample()))
        candidate = engine.residual_candidates()[0]
        self.assertEqual(candidate.kind, "residual_anomaly")
        self.assertGreater(candidate.components["surprise"], 0.7)
        self.assertEqual(candidate.components["falsifiability"], 1.0)

    def test_cross_domain_analogy_uses_structural_signature(self):
        engine = FrontierDiscovery(parse_frontier_input(self.sample()))
        candidates = engine.analogy_candidates(similarity_threshold=0.9)
        pairs = {frozenset(candidate.evidence_ids) for candidate in candidates}
        self.assertIn(frozenset(("claim-positive", "observation-1")), pairs)
        self.assertTrue(all(candidate.components["cross_domain"] == 1.0 for candidate in candidates))

    def test_known_pattern_reduces_novelty(self):
        raw = self.sample()
        raw["known_patterns"] = ["feedback threshold phase-change"]
        engine = FrontierDiscovery(parse_frontier_input(raw))
        candidate = engine.contradiction_candidates()[0]
        self.assertLess(candidate.components["novelty"], 0.6)

    def test_input_bounds_and_duplicate_ids_fail_closed(self):
        raw = self.sample()
        raw["observations"][0]["id"] = "claim-positive"
        with self.assertRaises(ValueError):
            parse_frontier_input(raw)

    def test_hash_chained_ledger_detects_tampering(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "ledger.jsonl"
            ledger = DiscoveryLedger(path)
            first = ledger.append({"study_id": "a"})
            second = ledger.append({"study_id": "b"})
            self.assertEqual(second["previous_hash"], first["record_hash"])
            self.assertTrue(ledger.verify())

            lines = path.read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            record["study_id"] = "tampered"
            lines[0] = json.dumps(record)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertFalse(ledger.verify())
            with self.assertRaises(ValueError):
                ledger.append({"study_id": "c"})

    def test_run_persists_unverified_report_without_promotion(self):
        with tempfile.TemporaryDirectory() as root:
            input_path = Path(root) / "evidence.json"
            input_path.write_text(json.dumps(self.sample()), encoding="utf-8")
            report = run_frontier_discovery(root, input_path=input_path, top_k=4)
            self.assertEqual(report["verification_status"], "unverified_candidates_only")
            self.assertLessEqual(report["candidate_count"], 4)
            self.assertTrue(report["ledger_verified"])
            destination = Path(root) / "frontier-discovery" / report["study_id"] / "report.json"
            persisted = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(persisted["study_id"], report["study_id"])
            self.assertEqual(persisted["ledger_record_hash"], report["ledger_record_hash"])

    def test_demo_mode_runs_without_external_access(self):
        with tempfile.TemporaryDirectory() as root:
            report = run_frontier_discovery(root, top_k=3)
            self.assertEqual(report["source"]["kind"], "built-in-demo")
            self.assertGreater(report["candidate_count"], 0)
            self.assertTrue(report["ledger_verified"])


if __name__ == "__main__":
    unittest.main()
