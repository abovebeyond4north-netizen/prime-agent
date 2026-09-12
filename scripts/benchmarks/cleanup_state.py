from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MISSING_SANDBOX_KEY_ERROR = "Repository secret PRIME_SANDBOX_API_KEY is not configured"


def can_skip_cleanup(report: Any) -> bool:
    """Return true only when trusted evidence proves no sandbox could have been created."""
    if not isinstance(report, dict):
        return False

    errors = report.get("errors")
    sandboxes = report.get("sandboxes")
    return (
        isinstance(errors, list)
        and MISSING_SANDBOX_KEY_ERROR in errors
        and sandboxes == []
    )


def can_skip_cleanup_from_path(report_path: Path) -> bool:
    """Load a benchmark report and fail closed on missing or malformed evidence."""
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
    args = parser.parse_args()
    print("true" if can_skip_cleanup_from_path(args.report) else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
