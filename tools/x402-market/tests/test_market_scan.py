import importlib.util
import pathlib
import sys
import unittest
from datetime import datetime, timezone

MODULE_PATH = pathlib.Path(__file__).parents[1] / "market_scan.py"
spec = importlib.util.spec_from_file_location("market_scan", MODULE_PATH)
market_scan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = market_scan
spec.loader.exec_module(market_scan)

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def item(calls, payers, amount="10000", name="Web Search", description="search web pages", last="2026-09-18T00:00:00Z"):
    return {
        "resource": "https://example.com/search",
        "serviceName": name,
        "description": description,
        "tags": ["search", "web"],
        "accepts": [{"asset": market_scan.BASE_USDC, "amount": amount, "network": "eip155:8453", "scheme": "exact"}],
        "quality": {"l30DaysTotalCalls": calls, "l30DaysUniquePayers": payers, "lastCalledAt": last},
    }


class MarketScanTests(unittest.TestCase):
    def test_price_and_revenue(self):
        row = market_scan.score_resource(item(100, 10, "10000"), now=NOW)
        self.assertAlmostEqual(row.price_usd, 0.01)
        self.assertAlmostEqual(row.estimated_revenue_30d, 1.0)
        self.assertTrue(row.repeat_demand)

    def test_farming_penalty(self):
        organic = market_scan.score_resource(item(1000, 20), now=NOW)
        farmed = market_scan.score_resource(item(1000, 950), now=NOW)
        self.assertFalse(organic.suspected_farming)
        self.assertTrue(farmed.suspected_farming)
        self.assertGreater(organic.opportunity_score, farmed.opportunity_score)

    def test_recency_decay(self):
        fresh = market_scan.score_resource(item(100, 10), now=NOW)
        stale = market_scan.score_resource(item(100, 10, last="2026-07-01T00:00:00Z"), now=NOW)
        self.assertGreater(fresh.demand_score, stale.demand_score)

    def test_category(self):
        row = market_scan.score_resource(item(10, 3), now=NOW)
        self.assertEqual(row.category, "search-retrieval")

    def test_analysis_sort(self):
        rows = market_scan.analyze([item(10, 3), item(1000, 20)], now=NOW)
        self.assertGreaterEqual(rows[0].opportunity_score, rows[1].opportunity_score)


if __name__ == "__main__":
    unittest.main()
