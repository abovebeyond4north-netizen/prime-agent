import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "coinbase_validate.py"
spec = importlib.util.spec_from_file_location("coinbase_validate", MODULE_PATH)
coinbase = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = coinbase
spec.loader.exec_module(coinbase)


class CoinbaseValidateTests(unittest.TestCase):
    def test_accepts_valid_and_accepted_simulation(self):
        result = {
            "valid": True,
            "simulation": {"outcome": "accepted"},
            "checks": [
                {"check": "resource.absolute_url", "severity": "required", "passed": True}
            ],
        }
        summary = coinbase.assess(result)
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["requiredFailures"], [])

    def test_rejects_required_failure(self):
        result = {
            "valid": True,
            "simulation": {"outcome": "accepted"},
            "checks": [
                {
                    "check": "bazaar.routeTemplate.matches_resource",
                    "severity": "required",
                    "passed": False,
                    "detail": "route does not match",
                }
            ],
        }
        summary = coinbase.assess(result)
        self.assertFalse(summary["accepted"])
        self.assertEqual(
            summary["requiredFailures"][0]["check"],
            "bazaar.routeTemplate.matches_resource",
        )

    def test_rejects_nonaccepted_simulation(self):
        summary = coinbase.assess(
            {"valid": True, "simulation": {"outcome": "rejected"}}
        )
        self.assertFalse(summary["accepted"])

    def test_rejects_unknown_response_without_positive_signal(self):
        summary = coinbase.assess({"message": "unexpected response"})
        self.assertFalse(summary["accepted"])

    def test_recursively_finds_nested_required_checks(self):
        result = {
            "valid": True,
            "simulation": {"outcome": "accepted"},
            "report": {
                "groups": [
                    {
                        "checks": [
                            {
                                "name": "nested.check",
                                "severity": "critical",
                                "pass": False,
                                "message": "bad",
                            }
                        ]
                    }
                ]
            },
        }
        summary = coinbase.assess(result)
        self.assertFalse(summary["accepted"])
        self.assertEqual(summary["checksObserved"], 1)

    def test_reachability_timeout_is_retryable(self):
        summary = coinbase.assess({
            "valid": False,
            "checks": [
                {"check": "endpoint_reachable", "severity": "required", "passed": False, "detail": "Endpoint timed out after 10 seconds"},
                {"check": "returns_402", "severity": "required", "passed": False, "detail": "Skipped: endpoint not reachable"},
                {"check": "parse", "severity": "required", "passed": False, "detail": "Skipped: preflight checks failed"},
            ],
        })
        self.assertTrue(coinbase.is_transient_reachability_failure(summary))

    def test_real_validation_failure_is_not_retryable(self):
        summary = coinbase.assess({
            "valid": False,
            "checks": [
                {"check": "endpoint_reachable", "severity": "required", "passed": False, "detail": "Endpoint timed out after 10 seconds"},
                {"check": "accepts[0].network", "severity": "required", "passed": False, "detail": "wrong network"},
            ],
        })
        self.assertFalse(coinbase.is_transient_reachability_failure(summary))


if __name__ == "__main__":
    unittest.main()
