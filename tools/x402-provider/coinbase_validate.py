#!/usr/bin/env python3
"""Validate live x402 resources with Coinbase CDP's public Bazaar preflight."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_VALIDATE_URL = "https://api.cdp.coinbase.com/platform/v2/x402/validate"
TRANSIENT_REACHABILITY_CHECK = "endpoint_reachable"


class CoinbaseValidateError(RuntimeError):
    """Permanent Coinbase validation request failure."""


class TransientCoinbaseError(CoinbaseValidateError):
    """Retryable Coinbase validation transport/service failure."""


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
        error = f"Coinbase validate HTTP {exc.code}: {detail}"
        if exc.code == 429 or 500 <= exc.code <= 599:
            raise TransientCoinbaseError(error) from exc
        raise CoinbaseValidateError(error) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise TransientCoinbaseError(f"Coinbase validate unavailable: {reason}") from exc

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


def is_transient_reachability_failure(summary: dict[str, Any]) -> bool:
    """Return true only when endpoint reachability caused the required failures."""
    failures = summary.get("requiredFailures")
    if not isinstance(failures, list) or not failures:
        return False
    saw_reachability = False
    for failure in failures:
        if not isinstance(failure, dict):
            return False
        check = failure.get("check")
        detail = str(failure.get("detail") or "").lower()
        if check == TRANSIENT_REACHABILITY_CHECK:
            saw_reachability = True
            continue
        if detail.startswith("skipped: endpoint not reachable") or detail.startswith(
            "skipped: preflight checks failed"
        ):
            continue
        return False
    return saw_reachability


def validate_resource(
    resource: str, *, retries: int = 0, retry_delay: float = 1.0, **kwargs: Any
) -> dict[str, Any]:
    for attempt in range(retries + 1):
        try:
            raw = post_validate(resource, **kwargs)
        except TransientCoinbaseError:
            if attempt >= retries:
                raise
            if retry_delay > 0:
                time.sleep(retry_delay * (2**attempt))
            continue
        summary = assess(raw)
        if summary["accepted"] or not is_transient_reachability_failure(summary):
            return {"resource": resource, "summary": summary, "raw": raw, "attempts": attempt + 1}
        if attempt < retries and retry_delay > 0:
            time.sleep(retry_delay * (2**attempt))
    return {"resource": resource, "summary": summary, "raw": raw, "attempts": retries + 1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resources", nargs="+")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--validate-url", default=DEFAULT_VALIDATE_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.retries < 0:
        parser.error("--retries must be non-negative")
    if args.retry_delay < 0:
        parser.error("--retry-delay must be non-negative")

    results = []
    ok = True
    for resource in args.resources:
        try:
            result = validate_resource(
                resource,
                method=args.method,
                validate_url=args.validate_url,
                timeout=args.timeout,
                retries=args.retries,
                retry_delay=args.retry_delay,
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
