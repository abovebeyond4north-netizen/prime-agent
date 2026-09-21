import base64
import importlib.util
import json
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "smoke_check.py"
spec = importlib.util.spec_from_file_location("x402_smoke_check", MODULE_PATH)
smoke = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)

def encoded_requirement(path, service_name, tags):
    payload = {
        "resource": {
            "url": f"https://prime-agent-x402-provider.onrender.com{path}",
            "description": service_name + " — test",
            "mimeType": "application/json",
            "serviceName": service_name,
            "tags": tags,
        },
        "extensions": {
            "bazaar": {
                "info": {
                    "input": {
                        "type": "http",
                        "method": "GET",
                        "queryParams": {},
                    }
                },
                "schema": {"type": "object"},
            }
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class SmokeCheckTests(unittest.TestCase):
    def test_health_public_mode(self):
        health = {
            "ok": True,
            "product": "prime-agent-x402-market",
            "route": "/v1/x402/opportunities",
            "paymentEnabled": False,
            "mode": "public-analysis",
            "gitCommit": "abc123",
            "gitBranch": "main",
        }
        smoke.validate_health(health, "abc123")

    def test_health_rejects_wrong_commit(self):
        health = {
            "ok": True,
            "product": "prime-agent-x402-market",
            "route": "/v1/x402/opportunities",
            "paymentEnabled": False,
            "mode": "public-analysis",
            "gitCommit": "old",
            "gitBranch": "main",
        }
        with self.assertRaises(AssertionError):
            smoke.validate_health(health, "new")

    def test_health_only_mode_accepts_deployed_main_commit(self):
        health = {
            "ok": True,
            "product": "prime-agent-x402-market",
            "route": "/v1/x402/opportunities",
            "paymentEnabled": False,
            "mode": "public-analysis",
            "gitCommit": "previous-deployed-main-commit",
            "gitBranch": "main",
        }
        smoke.validate_health(health)

    def test_public_market_contract(self):
        health = {"paymentEnabled": False}
        body = b'{"source":"Coinbase public x402 Bazaar discovery catalog","opportunities":[],"count":0}'
        payload = smoke.validate_market(health, 200, {}, body)
        self.assertEqual(payload["count"], 0)

    def test_paid_market_contract(self):
        health = {"paymentEnabled": True}
        header = encoded_requirement(
            "/v1/x402/opportunities",
            "Prime Agent Market Intel",
            ["x402", "seller-market", "agents", "demand", "base"],
        )
        self.assertIsNone(
            smoke.validate_market(health, 402, {"PAYMENT-REQUIRED": header}, b"")
        )

    def test_token_verdict_discovery_contract(self):
        header = encoded_requirement(
            "/v1/token/verdict",
            "Prime Agent Token Verdict",
            ["token-risk", "erc20", "base", "onchain", "liquidity"],
        )
        requirement = smoke.validate_discoverable_402(
            {"PAYMENT-REQUIRED": header},
            "/v1/token/verdict",
            "Prime Agent Token Verdict",
            {"token-risk", "erc20", "base"},
        )
        self.assertEqual(requirement["resource"]["serviceName"], "Prime Agent Token Verdict")

    def test_discovery_contract_rejects_wrong_service_name(self):
        header = encoded_requirement(
            "/v1/token/verdict",
            "Wrong Service",
            ["token-risk", "erc20", "base"],
        )
        with self.assertRaises(AssertionError):
            smoke.validate_discoverable_402(
                {"PAYMENT-REQUIRED": header},
                "/v1/token/verdict",
                "Prime Agent Token Verdict",
                {"token-risk", "erc20", "base"},
            )

    def test_paid_market_requires_payment_header(self):
        health = {"paymentEnabled": True}
        with self.assertRaises(AssertionError):
            smoke.validate_market(health, 402, {}, b"")


if __name__ == "__main__":
    unittest.main()
