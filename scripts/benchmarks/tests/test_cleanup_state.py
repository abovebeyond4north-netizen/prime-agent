import json
import tempfile
import unittest
from pathlib import Path

from cleanup_state import MISSING_SANDBOX_KEY_ERROR, can_skip_cleanup, can_skip_cleanup_from_path


class CleanupStateTest(unittest.TestCase):
    def test_skips_only_for_missing_key_with_no_sandboxes(self) -> None:
        report = {"errors": [MISSING_SANDBOX_KEY_ERROR], "sandboxes": []}
        self.assertTrue(can_skip_cleanup(report))

    def test_does_not_skip_when_a_sandbox_was_created(self) -> None:
        report = {
            "errors": [MISSING_SANDBOX_KEY_ERROR],
            "sandboxes": [{"id": "sandbox-1"}],
        }
        self.assertFalse(can_skip_cleanup(report))

    def test_does_not_skip_for_other_failures(self) -> None:
        report = {"errors": ["benchmark failed"], "sandboxes": []}
        self.assertFalse(can_skip_cleanup(report))

    def test_does_not_skip_without_complete_evidence(self) -> None:
        self.assertFalse(can_skip_cleanup({"errors": [MISSING_SANDBOX_KEY_ERROR]}))
        self.assertFalse(can_skip_cleanup({"sandboxes": []}))
        self.assertFalse(can_skip_cleanup(None))

    def test_path_loader_fails_closed_for_malformed_or_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            malformed = root / "malformed.json"
            malformed.write_text("not json")
            self.assertFalse(can_skip_cleanup_from_path(malformed))
            self.assertFalse(can_skip_cleanup_from_path(root / "missing.json"))

    def test_path_loader_accepts_exact_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps({"errors": [MISSING_SANDBOX_KEY_ERROR], "sandboxes": []}))
            self.assertTrue(can_skip_cleanup_from_path(report_path))


if __name__ == "__main__":
    unittest.main()
