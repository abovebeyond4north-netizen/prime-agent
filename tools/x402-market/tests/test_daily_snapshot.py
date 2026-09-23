import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
