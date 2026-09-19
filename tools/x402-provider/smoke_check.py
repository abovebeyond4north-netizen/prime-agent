#!/usr/bin/env python3
"""External production smoke check for the x402 market provider.

Uses only the Python standard library so it can run cheaply in GitHub Actions.
It verifies deployment/main SHA alignment, the health contract, and either the
public Bazaar-backed response or the unpaid HTTP 402 challenge in paid mode.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


USER_AGENT = "prime-agent-x402-smoke/1.0"


def request(url: str, timeout: int = 60) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return int(response.status), dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), dict(exc.headers.items()), exc.read()


def decode_json(body: bytes) -> dict[str, Any]:
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"Expected JSON object, got {type(value).__name__}")
    return value


def validate_health(health: dict[str, Any], expected_commit: str) -> None:
    assert health.get("ok") is True, health
    assert health.get("product") == "prime-agent-x402-market", health
    assert health.get("route") == "/v1/x402/opportunities", health
    assert health.get("gitCommit") == expected_commit, health
    assert health.get("gitBranch") == "main", health
    assert health.get("mode") in {"public-analysis", "x402-paid"}, health
    assert bool(health.get("paymentEnabled")) == (health.get("mode") == "x402-paid"), health


def wait_for_health(
    base_url: str,
    expected_commit: str,
    attempts: int = 20,
    delay_seconds: float = 15.0,
) -> dict[str, Any]:
    last_error: Exception | None = None
    last_health: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        try:
            status, _headers, body = request(f"{base_url.rstrip('/')}/health")
            if status != 200:
                raise AssertionError(f"Health returned HTTP {status}")
            health = decode_json(body)
            last_health = health
            validate_health(health, expected_commit)
            return health
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(delay_seconds)

    detail = f"; last health={last_health}" if last_health is not None else ""
    raise AssertionError(
        f"Production did not match commit {expected_commit} after {attempts} attempts: {last_error}{detail}"
    )


def validate_market(
    health: dict[str, Any],
    status: int,
    headers: dict[str, str],
    body: bytes,
) -> dict[str, Any] | None:
    if health.get("paymentEnabled"):
        assert status == 402, f"Expected HTTP 402 in paid mode, got {status}"
        normalized = {key.lower(): value for key, value in headers.items()}
        assert normalized.get("payment-required"), "Missing PAYMENT-REQUIRED header"
        return None

    assert status == 200, f"Expected HTTP 200 in public mode, got {status}"
    payload = decode_json(body)
    assert payload.get("source") == "Coinbase public x402 Bazaar discovery catalog", payload
    assert isinstance(payload.get("opportunities"), list), payload
    assert isinstance(payload.get("count"), int), payload
    return payload


def run(base_url: str, expected_commit: str, attempts: int, delay_seconds: float) -> dict[str, Any]:
    health = wait_for_health(base_url, expected_commit, attempts, delay_seconds)
    endpoint = f"{base_url.rstrip('/')}/v1/x402/opportunities?limit=1&organicOnly=true"
    status, headers, body = request(endpoint)
    payload = validate_market(health, status, headers, body)
    result = {
        "ok": True,
        "gitCommit": health["gitCommit"],
        "mode": health["mode"],
        "marketStatus": status,
        "marketCount": payload.get("count") if payload else None,
    }
    print(json.dumps(result, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--delay-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        run(args.url, args.expected_commit, max(1, args.attempts), max(0.0, args.delay_seconds))
        return 0
    except Exception as exc:
        print(f"x402 production smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
