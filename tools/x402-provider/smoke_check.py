#!/usr/bin/env python3
"""External production smoke check for the x402 market provider.

Uses only the Python standard library so it can run cheaply in GitHub Actions.
It verifies the health contract and either the public Bazaar-backed response or
the unpaid HTTP 402 challenge in paid mode. Push checks can additionally verify
that production has deployed an expected commit.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
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


def decode_payment_required(headers: dict[str, str]) -> dict[str, Any]:
    normalized = {key.lower(): value for key, value in headers.items()}
    encoded = normalized.get("payment-required")
    if not encoded:
        raise AssertionError("Missing PAYMENT-REQUIRED header")
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        return decode_json(raw)
    except Exception as exc:
        raise AssertionError(f"Invalid PAYMENT-REQUIRED header: {exc}") from exc


def validate_discoverable_402(
    headers: dict[str, str],
    expected_path: str,
    expected_service_name: str,
    required_tags: set[str],
) -> dict[str, Any]:
    requirement = decode_payment_required(headers)
    resource = requirement.get("resource")
    assert isinstance(resource, dict), requirement

    url = resource.get("url")
    assert isinstance(url, str) and url.startswith(("https://", "http://")), resource
    assert urllib.parse.urlsplit(url).path == expected_path, resource

    # Service metadata is optional in x402. Older middleware versions accept only
    # a string resource URL; newer versions can surface serviceName/tags. Validate
    # the enrichment when present without making core 402 conformance depend on it.
    if resource.get("serviceName") is not None:
        assert resource.get("serviceName") == expected_service_name, resource
    if resource.get("tags") is not None:
        tags = set(resource.get("tags") or [])
        assert required_tags.issubset(tags), resource

    description = str(resource.get("description") or "")
    assert expected_service_name in description, resource

    extensions = requirement.get("extensions")
    assert isinstance(extensions, dict), requirement
    bazaar = extensions.get("bazaar")
    assert isinstance(bazaar, dict), extensions
    info = bazaar.get("info")
    assert isinstance(info, dict), bazaar
    input_info = info.get("input")
    assert isinstance(input_info, dict), info
    assert input_info.get("type") == "http", input_info
    assert input_info.get("method") == "GET", input_info
    assert isinstance(bazaar.get("schema"), dict), bazaar
    return requirement


def validate_health(health: dict[str, Any], expected_commit: str | None = None) -> None:
    assert health.get("ok") is True, health
    assert health.get("product") == "prime-agent-x402-market", health
    assert health.get("route") == "/v1/x402/opportunities", health
    if expected_commit is not None:
        assert health.get("gitCommit") == expected_commit, health
    assert health.get("gitBranch") == "main", health
    assert health.get("mode") in {"public-analysis", "x402-paid"}, health
    assert bool(health.get("paymentEnabled")) == (health.get("mode") == "x402-paid"), health


def wait_for_health(
    base_url: str,
    expected_commit: str | None = None,
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
    target = f"commit {expected_commit}" if expected_commit is not None else "a healthy deployment"
    raise AssertionError(
        f"Production did not reach {target} after {attempts} attempts: {last_error}{detail}"
    )


def validate_market(
    health: dict[str, Any],
    status: int,
    headers: dict[str, str],
    body: bytes,
) -> dict[str, Any] | None:
    if health.get("paymentEnabled"):
        assert status == 402, f"Expected HTTP 402 in paid mode, got {status}"
        validate_discoverable_402(
            headers,
            "/v1/x402/opportunities",
            "Prime Agent Market Intel",
            {"x402", "seller-market", "agents"},
        )
        return None

    assert status == 200, f"Expected HTTP 200 in public mode, got {status}"
    payload = decode_json(body)
    assert payload.get("source") == "Coinbase public x402 Bazaar discovery catalog", payload
    assert isinstance(payload.get("opportunities"), list), payload
    assert isinstance(payload.get("count"), int), payload
    return payload


def run(base_url: str, expected_commit: str | None, attempts: int, delay_seconds: float) -> dict[str, Any]:
    health = wait_for_health(base_url, expected_commit, attempts, delay_seconds)
    endpoint = f"{base_url.rstrip('/')}/v1/x402/opportunities?limit=1&organicOnly=true"
    status, headers, body = request(endpoint)
    payload = validate_market(health, status, headers, body)

    token_status = None
    if health.get("paymentEnabled"):
        token_url = (
            f"{base_url.rstrip('/')}/v1/token/verdict"
            "?address=0x1111111111111111111111111111111111111111"
        )
        token_status, token_headers, _token_body = request(token_url)
        assert token_status == 402, f"Expected token verdict HTTP 402, got {token_status}"
        validate_discoverable_402(
            token_headers,
            "/v1/token/verdict",
            "Prime Agent Token Verdict",
            {"token-risk", "erc20", "base"},
        )

    result = {
        "ok": True,
        "gitCommit": health["gitCommit"],
        "mode": health["mode"],
        "marketStatus": status,
        "marketCount": payload.get("count") if payload else None,
        "tokenVerdictStatus": token_status,
    }
    print(json.dumps(result, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-commit")
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
