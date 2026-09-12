from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MISSING_SANDBOX_KEY_ERROR = "Repository secret PRIME_SANDBOX_API_KEY is not configured"


def can_skip_cleanup(report: Any, *, sandbox_run_started: bool = True) -> bool:
    """Return true only when trusted evidence proves cleanup cannot be required."""
    if not sandbox_run_started:
        return True
    if not isinstance(report, dict):
        return False

    errors = report.get("errors")
    sandboxes = report.get("sandboxes")
    return isinstance(errors, list) and MISSING_SANDBOX_KEY_ERROR in errors and sandboxes == []


def can_skip_cleanup_from_path(report_path: Path, *, sandbox_run_started: bool = True) -> bool:
    """Load a benchmark report and fail closed on missing or malformed evidence."""
    if not sandbox_run_started:
        return True
    try:
        report = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return can_skip_cleanup(report)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether benchmark finalizer cleanup can be safely skipped."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--sandbox-run-not-started",
        action="store_true",
        help="Trusted workflow evidence proves the sandbox benchmark command never started.",
    )
    args = parser.parse_args()
    print(
        "true"
        if can_skip_cleanup_from_path(
            args.report,
            sandbox_run_started=not args.sandbox_run_not_started,
        )
        else "false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
