import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

MODULE_DIR = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(MODULE_DIR))
MODULE_PATH = MODULE_DIR / "daily_snapshot.py"
spec = importlib.util.spec_from_file_location("daily_snapshot", MODULE_PATH)
daily = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = daily
spec.loader.exec_module(daily)


class DailySnapshotTests(unittest.TestCase):
    def test_persist_replaces_latest_and_history_without_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            old = (daily.DATA_DIR, daily.LATEST, daily.HISTORY)
            daily.DATA_DIR = root
            daily.LATEST = root / "latest.json"
            daily.HISTORY = root / "history.jsonl"
            try:
                daily.persist({"date": "2026-09-22", "resource_count": 1})
                daily.persist({"date": "2026-09-23", "resource_count": 2})

                latest = json.loads(daily.LATEST.read_text(encoding="utf-8"))
                self.assertEqual(latest["date"], "2026-09-23")

                history = [
                    json.loads(line)
                    for line in daily.HISTORY.read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(
                    [item["date"] for item in history],
                    ["2026-09-22", "2026-09-23"],
                )
                self.assertEqual(list(root.glob(".*.tmp")), [])
            finally:
                daily.DATA_DIR, daily.LATEST, daily.HISTORY = old

    def test_persist_replaces_same_day_instead_of_duplicating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            old = (daily.DATA_DIR, daily.LATEST, daily.HISTORY)
            daily.DATA_DIR = root
            daily.LATEST = root / "latest.json"
            daily.HISTORY = root / "history.jsonl"
            try:
                daily.persist({"date": "2026-09-23", "resource_count": 1})
                daily.persist({"date": "2026-09-23", "resource_count": 3})
                lines = daily.HISTORY.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["resource_count"], 3)
            finally:
                daily.DATA_DIR, daily.LATEST, daily.HISTORY = old

    def test_fetch_provider_health_records_deployment_metadata(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = json.dumps(
            {
                "ok": True,
                "mode": "x402-paid",
                "paymentEnabled": True,
                "gitCommit": "abc123",
                "gitBranch": "main",
            }
        ).encode("utf-8")
        response.__enter__.return_value = response
        with mock.patch.object(daily.urllib.request, "urlopen", return_value=response):
            health = daily.fetch_provider_health("https://example.com/health", timeout=1)
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["http_status"], 200)
        self.assertEqual(health["mode"], "x402-paid")
        self.assertTrue(health["payment_enabled"])
        self.assertEqual(health["git_commit"], "abc123")
        self.assertGreaterEqual(health["latency_ms"], 0)

    def test_fetch_provider_health_degrades_to_unreachable_without_raising(self):
        error = daily.urllib.error.URLError("temporary DNS failure")
        with mock.patch.object(daily.urllib.request, "urlopen", side_effect=error):
            health = daily.fetch_provider_health("https://example.com/health", timeout=1)
        self.assertEqual(health["status"], "unreachable")
        self.assertIsNone(health["http_status"])
        self.assertIn("temporary DNS failure", health["error"])


if __name__ == "__main__":
    unittest.main()
