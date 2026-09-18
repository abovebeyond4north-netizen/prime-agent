#!/usr/bin/env python3
"""Persist a compact daily x402 market snapshot for trend detection."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from market_scan import analyze, category_summary, fetch_catalog

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LATEST = DATA_DIR / "latest.json"
HISTORY = DATA_DIR / "history.jsonl"
MAX_DAYS = 365


def build_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    rows = analyze(fetch_catalog(), now=now)
    top = [asdict(row) for row in rows[:50]]
    return {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "resource_count": len(rows),
        "repeat_demand_count": sum(1 for row in rows if row.repeat_demand),
        "suspected_farming_count": sum(1 for row in rows if row.suspected_farming),
        "categories": category_summary(rows),
        "top": top,
    }


def persist(snapshot: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    previous: list[dict] = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                previous.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    by_date = {str(item.get("date")): item for item in previous if item.get("date")}
    by_date[str(snapshot["date"])] = snapshot
    ordered = sorted(by_date.values(), key=lambda item: str(item["date"]))[-MAX_DAYS:]
    HISTORY.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in ordered), encoding="utf-8")


def main() -> int:
    snapshot = build_snapshot()
    persist(snapshot)
    print(
        f"saved {snapshot['date']}: {snapshot['resource_count']} resources, "
        f"{snapshot['repeat_demand_count']} repeat-demand resources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
