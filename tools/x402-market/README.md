# x402 Market Intelligence

A zero-key scanner for Coinbase's public x402 Bazaar catalog. It ranks resources by observed 30-day demand, repeat usage, recency, safely inferable USDC price/revenue, and a heuristic penalty for one-call-per-wallet activity.

## Run

```bash
python3 tools/x402-market/market_scan.py --top 50 --format markdown
python3 tools/x402-market/market_scan.py --top 200 --format json --output x402-market.json
```

The public feed used by default is:

`https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources`

No Coinbase credentials or Python dependencies are required for the scanner.

## Signals

- `calls_30d`: Bazaar `quality.l30DaysTotalCalls`
- `unique_payers_30d`: Bazaar `quality.l30DaysUniquePayers`
- `calls_per_payer`: repeat-use proxy
- `repeat_demand`: at least 3 payers, at least 3 calls/payer, not flagged as likely farming
- `suspected_farming`: high-volume resource where payers are at least 85% of calls
- `estimated_revenue_30d`: calls × price when the payment requirement is recognizable USDC
- `opportunity_score`: log-scaled buyer breadth × reuse × calls × recency × organic-demand multiplier × monetization

The score is for discovery, not proof of profit. Bazaar counters are third-party measurements and should be cross-checked with settlement/on-chain data before capital allocation.

## Tests

```bash
python3 -m unittest discover -s tools/x402-market/tests -v
```
