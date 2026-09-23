#!/usr/bin/env python3
"""Persist a compact daily x402 market snapshot for trend detection."""
from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from market_scan import analyze, category_summary, fetch_catalog

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LATEST = DATA_DIR / "latest.json"
HISTORY = DATA_DIR / "history.jsonl"
MAX_DAYS = 365
PROVIDER_HEALTH_URL = "https://prime-agent-x402-provider.onrender.com/health"


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a text file atomically and avoid leaving partial snapshots."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def fetch_provider_health(
    url: str = PROVIDER_HEALTH_URL, timeout: float = 10.0
) -> dict:
    started = time.monotonic()
    request = urllib.request.Request(
        url, headers={"User-Agent": "prime-agent-x402-daily-snapshot/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read()
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("health response is not a JSON object")
        latency_ms = round((time.monotonic() - started) * 1000)
        healthy = status == 200 and payload.get("ok") is True
        return {
            "status": "healthy" if healthy else "provider_failure",
            "http_status": status,
            "latency_ms": latency_ms,
            "mode": payload.get("mode"),
            "payment_enabled": payload.get("paymentEnabled"),
            "git_commit": payload.get("gitCommit"),
            "git_branch": payload.get("gitBranch"),
        }
    except urllib.error.HTTPError as exc:
        return {
            "status": "provider_failure",
            "http_status": int(exc.code),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": f"HTTP {exc.code}",
        }
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "unreachable",
            "http_status": None,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": str(getattr(exc, "reason", exc)),
        }


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
        "provider_health": fetch_provider_health(),
        "top": top,
    }


def persist(snapshot: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(LATEST, json.dumps(snapshot, indent=2) + "\n")

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
    _atomic_write_text(HISTORY, "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in ordered))


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
