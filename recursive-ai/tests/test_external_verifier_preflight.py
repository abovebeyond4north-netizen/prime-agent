import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.external_verifier_preflight import (
    PROTOCOL,
    cache_decision,
    digest_files,
    evaluation_identity,
    resource_preflight,
)


class ExternalVerifierPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.dataset = self.root / "dataset.jsonl"
        self.predictions = self.root / "predictions.jsonl"
        self.evaluator = self.root / "evaluator.py"
        self.result = self.root / "result.json"
        self.dataset.write_text('{"instance_id":"sample"}\n')
        self.predictions.write_text('{"instance_id":"sample","model_patch":"valid"}\n')
        self.evaluator.write_text("def verify(): return True\n")
        self.result.write_text(json.dumps({"resolved": True}))

    def tearDown(self):
        self.temporary.cleanup()

    def identity(self):
        return evaluation_identity(
            benchmark_revision="230023d821dff5f58d18446ce6dab0b588205c9f",
            datasets=(self.dataset,),
            predictions=self.predictions,
            evaluators=(self.evaluator,),
        )

    def receipt(self, identity):
        receipt = dict(identity)
        receipt["result_sha256"] = digest_files((self.result,))
        return receipt

    def test_identity_is_deterministic_and_namespaced(self):
        first = self.identity()
        second = self.identity()
        self.assertEqual(first, second)
        self.assertEqual(first["protocol"], PROTOCOL)
        self.assertEqual(first["run_id"], f"nucleus-{first['evaluation_sha256'][:24]}")

    def test_identity_rejects_moving_or_ambiguous_revision(self):
        for revision in ("main", "230023d", "", "G" * 40):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                evaluation_identity(
                    benchmark_revision=revision,
                    datasets=(self.dataset,),
                    predictions=self.predictions,
                    evaluators=(self.evaluator,),
                )

    def test_changed_patch_forces_distinct_run(self):
        first = self.identity()
        self.predictions.write_text('{"instance_id":"sample","model_patch":"changed"}\n')
        second = self.identity()
        self.assertNotEqual(first["predictions_sha256"], second["predictions_sha256"])
        self.assertNotEqual(first["run_id"], second["run_id"])

    def test_changed_dataset_or_evaluator_forces_distinct_run(self):
        first = self.identity()
        self.dataset.write_text('{"instance_id":"fresh"}\n')
        changed_dataset = self.identity()
        self.dataset.write_text('{"instance_id":"sample"}\n')
        self.evaluator.write_text("def verify(): return False\n")
        changed_evaluator = self.identity()
        self.assertNotEqual(first["run_id"], changed_dataset["run_id"])
        self.assertNotEqual(first["run_id"], changed_evaluator["run_id"])

    def test_exact_receipt_and_result_are_reusable(self):
        identity = self.identity()
        decision = cache_decision(self.receipt(identity), identity, result=self.result)
        self.assertEqual(decision, {"reusable": True, "reasons": []})

    def test_missing_receipt_or_result_fails_closed(self):
        identity = self.identity()
        self.assertFalse(cache_decision(None, identity, result=self.result)["reusable"])
        decision = cache_decision(self.receipt(identity), identity)
        self.assertEqual(decision["reasons"], ["result file absent"])

    def test_mismatch_or_result_tampering_fails_closed(self):
        identity = self.identity()
        receipt = self.receipt(identity)
        receipt["benchmark_revision"] = "different"
        mismatch = cache_decision(receipt, identity, result=self.result)
        self.assertFalse(mismatch["reusable"])
        self.assertIn("benchmark_revision mismatch", mismatch["reasons"])
        receipt = self.receipt(identity)
        self.result.write_text(json.dumps({"resolved": False}))
        tampered = cache_decision(receipt, identity, result=self.result)
        self.assertEqual(tampered["reasons"], ["result digest mismatch"])

    def test_resource_preflight_reports_each_requirement(self):
        disk = type("usage", (), {"total": 100, "used": 20, "free": 70 * 1024**3})
        with patch("research.external_verifier_preflight.shutil.disk_usage", return_value=disk), patch(
            "research.external_verifier_preflight.shutil.which", return_value="/usr/bin/docker"
        ):
            report = resource_preflight(self.root)
        self.assertTrue(report["ready"])
        self.assertTrue(all(report["checks"].values()))

        insufficient = type("usage", (), {"total": 100, "used": 80, "free": 20 * 1024**3})
        with patch("research.external_verifier_preflight.shutil.disk_usage", return_value=insufficient), patch(
            "research.external_verifier_preflight.shutil.which", return_value=None
        ):
            report = resource_preflight(self.root)
        self.assertFalse(report["ready"])
        self.assertFalse(report["checks"]["docker_cli_available"])
        self.assertFalse(report["checks"]["minimum_free_space"])


if __name__ == "__main__":
    unittest.main()
