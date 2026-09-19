# x402 Market Provider

A low-marginal-cost x402 seller service for Prime Agent. The API ranks public x402 Bazaar resources by repeat demand, recency, safely inferable USDC monetization, and an activity-farming penalty.

The request path uses Coinbase's public Bazaar catalog as its upstream dataset, so it does not require paid data APIs or LLM inference.

## Payment model

The server uses the standard x402 resource-server stack:

- `@x402/express`
- `@x402/core`
- `@x402/evm`
- `@x402/extensions`

A private key is **not** required by the seller process. To activate payment gating, set only a public EVM receiving address:

- `PAY_TO=0x...`

By default the provider targets Base mainnet (`eip155:8453`) through PayAI at `https://facilitator.payai.network`. PayAI's ordinary exact-payment path currently requires no merchant API key and exposes Bazaar discovery. The facilitator is configurable so it can be replaced without changing application code.

If `PAY_TO` is absent or malformed, the service stays online in public-analysis mode instead of failing startup.

Optional runtime settings:

- `PORT` (Render supplies this automatically)
- `X402_PRICE` (default `$0.01`)
- `X402_NETWORK` (default `eip155:8453`)
- `X402_FACILITATOR_URL` (default `https://facilitator.payai.network`)
- `X402_DISCOVERY_URL` (defaults to Coinbase's public x402 discovery endpoint)

## Run

```bash
cd tools/x402-provider
npm install
npm start
```

Health check:

```bash
curl http://localhost:8402/health
```

Market endpoint:

```text
GET /v1/x402/opportunities?limit=25&organicOnly=true
```

When `PAY_TO` is configured, an unpaid request receives HTTP 402 and the client must settle the configured price before the handler executes.

## Discovery

The paid route declares the x402 Bazaar discovery extension with:

- example input
- input schema
- output example
- output schema
- a machine-readable endpoint description

A facilitator that supports Bazaar indexing can catalog the endpoint after a real settlement carrying the extension. Catalog behavior is facilitator-specific, so successful settlement and successful indexing are monitored separately.

## Product logic

The service deliberately avoids LLM inference on the hot path. It converts a noisy public marketplace into a compact ranked market signal, keeping marginal delivery cost low and allowing actual paid usage to determine whether to expand into historical trend monitoring, seller analytics, enrichment, or adjacent paid APIs.

## Safety and custody

The repository never stores a wallet private key. `PAY_TO` is only the public receiving address. Ownership and withdrawal remain under the wallet holder's control.
