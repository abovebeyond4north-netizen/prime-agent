#!/usr/bin/env python3
"""Validate live x402 resources with Coinbase CDP's public Bazaar preflight."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_VALIDATE_URL = "https://api.cdp.coinbase.com/platform/v2/x402/validate"


def post_validate(
    resource: str,
    *,
    method: str = "GET",
    validate_url: str = DEFAULT_VALIDATE_URL,
    timeout: float = 30.0,
) -> dict[str, Any]:
    payload = json.dumps({"resource": resource, "method": method}).encode("utf-8")
    request = urllib.request.Request(
        validate_url,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "prime-agent-x402-coinbase-preflight/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        detail = body.decode("utf-8", errors="replace")
        raise RuntimeError(f"Coinbase validate HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Coinbase validate unavailable: {exc.reason}") from exc

    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Coinbase validate returned non-JSON response") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Coinbase validate returned non-object JSON")
    return result


def _walk_checks(value: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if (
            ("passed" in value or "pass" in value)
            and ("check" in value or "name" in value)
        ):
            checks.append(value)
        for child in value.values():
            checks.extend(_walk_checks(child))
    elif isinstance(value, list):
        for child in value:
            checks.extend(_walk_checks(child))
    return checks


def assess(result: dict[str, Any]) -> dict[str, Any]:
    checks = _walk_checks(result)
    required_failures = []
    for check in checks:
        passed = check.get("passed", check.get("pass"))
        severity = str(check.get("severity", "")).lower()
        if passed is False and severity in {"required", "error", "critical"}:
            required_failures.append(
                {
                    "check": check.get("check", check.get("name")),
                    "severity": severity,
                    "detail": check.get("detail", check.get("message")),
                }
            )

    valid = result.get("valid")
    simulation = result.get("simulation")
    outcome = simulation.get("outcome") if isinstance(simulation, dict) else None

    accepted = (
        valid is not False
        and not required_failures
        and (outcome is None or str(outcome).lower() == "accepted")
    )

    # Require a positive signal from Coinbase rather than treating an unknown
    # response shape as a pass.
    has_positive_signal = valid is True or (
        outcome is not None and str(outcome).lower() == "accepted"
    )
    accepted = accepted and has_positive_signal

    return {
        "accepted": accepted,
        "valid": valid,
        "simulationOutcome": outcome,
        "checksObserved": len(checks),
        "requiredFailures": required_failures,
    }


def validate_resource(resource: str, **kwargs: Any) -> dict[str, Any]:
    raw = post_validate(resource, **kwargs)
    summary = assess(raw)
    return {"resource": resource, "summary": summary, "raw": raw}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resources", nargs="+")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--validate-url", default=DEFAULT_VALIDATE_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    results = []
    ok = True
    for resource in args.resources:
        try:
            result = validate_resource(
                resource,
                method=args.method,
                validate_url=args.validate_url,
                timeout=args.timeout,
            )
        except Exception as exc:
            result = {
                "resource": resource,
                "summary": {"accepted": False},
                "error": str(exc),
            }
        results.append(result)
        ok = ok and bool(result["summary"].get("accepted"))

    print(json.dumps({"ok": ok, "results": results}, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
