import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "smoke_check.py"
spec = importlib.util.spec_from_file_location("x402_smoke_check", MODULE_PATH)
smoke = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)


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
        self.assertIsNone(
            smoke.validate_market(health, 402, {"PAYMENT-REQUIRED": "encoded"}, b"")
        )

    def test_paid_market_requires_payment_header(self):
        health = {"paymentEnabled": True}
        with self.assertRaises(AssertionError):
            smoke.validate_market(health, 402, {}, b"")


if __name__ == "__main__":
    unittest.main()
