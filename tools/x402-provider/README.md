# x402 Market Provider

A first sellable x402 service for Prime Agent: a paid API that ranks public x402 Bazaar resources by repeat demand, recency, safely inferable USDC monetization, and a simple activity-farming penalty.

The service uses Coinbase's public Bazaar catalog as its upstream dataset, so there is no paid data dependency in the request path.

## Credentials

The provider uses Coinbase CDP's official x402 resource-server integration. Supply these as environment variables at runtime:

- `CDP_API_KEY_ID`
- `CDP_API_KEY_SECRET`
- `CDP_WALLET_SECRET`

No private key or credential is stored in this repository. `createX402Server` provisions/manages the receiver wallet through CDP.

Optional runtime settings:

- `PORT` (default `8402`)
- `X402_PRICE` (default `$0.01`)
- `X402_DISCOVERY_URL` (defaults to Coinbase's public x402 discovery endpoint)

## Run

```bash
cd tools/x402-provider
npm install
npm start
```

Free health check:

```bash
curl http://localhost:8402/health
```

Paid route:

```text
GET /v1/x402/opportunities?limit=25&organicOnly=true
```

The official CDP x402 integration returns `402 Payment Required` to unpaid clients and settles a valid x402 payment before the route handler runs. Routes created with `createX402Server` are eligible for CDP Bazaar discovery after real settlement through the CDP facilitator.

## Product logic

This first product deliberately avoids LLM inference on the hot path. It turns a public, noisy registry into a compact ranked market signal. That keeps marginal cost low and lets actual paid usage determine whether to expand into deeper enrichment, monitoring, historical trend data, or seller analytics.
