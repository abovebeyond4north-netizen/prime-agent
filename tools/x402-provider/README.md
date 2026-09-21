# x402 Market Provider

A low-marginal-cost x402 seller service for Prime Agent. The provider currently exposes two paid API products:

- **Market opportunities** — ranks public x402 Bazaar resources by repeat demand, recency, safely inferable USDC monetization, and an activity-farming penalty.
- **Base token verdict** — inspects a Base token with deterministic contract and market-structure signals, without LLM inference.

The market route uses Coinbase's public Bazaar catalog. The token-verdict route uses Base JSON-RPC plus DEX Screener's Base token-pairs endpoint. Both are designed so the paid request path can remain inexpensive enough for micropayment testing.

## Payment model

The server uses the standard x402 resource-server stack:

- `@x402/express`
- `@x402/core`
- `@x402/evm`
- `@x402/extensions`

A private key is **not** required by the seller process. To activate payment gating, set only a public EVM receiving address:

- `PAY_TO=0x...`

By default the provider targets Base mainnet (`eip155:8453`) through PayAI at `https://facilitator.payai.network`. The facilitator is configurable so it can be replaced without changing application code.

If `PAY_TO` is absent or malformed, the service stays online in public-analysis mode instead of failing startup.

Optional runtime settings:

- `PORT` (Render supplies this automatically)
- `X402_PRICE` (default `$0.01`) for the market-opportunity route
- `X402_TOKEN_VERDICT_PRICE` (default `$0.01`)
- `X402_NETWORK` (default `eip155:8453`)
- `X402_FACILITATOR_URL` (default `https://facilitator.payai.network`)
- `X402_DISCOVERY_URL` (defaults to Coinbase's public x402 discovery endpoint)
- `X402_PUBLIC_BASE_URL` (defaults to Render's external URL, then the production provider URL; used to publish absolute Bazaar resource URLs)
- `BASE_RPC_URL` (default `https://mainnet.base.org`)
- `DEXSCREENER_URL` (default `https://api.dexscreener.com`)
- `TOKEN_VERDICT_TIMEOUT_MS` (default `8000`, bounded to 1–30 seconds)
- `TOKEN_VERDICT_CACHE_TTL_MS` (default `60000`, bounded to 5 seconds–5 minutes)
- `TOKEN_VERDICT_CACHE_MAX` (default `1024`, bounded to 32–10,000 entries)

## Run

```bash
cd tools/x402-provider
npm install
npm test
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

Token-verdict endpoint:

```text
GET /v1/token/verdict?address=0x1111111111111111111111111111111111111111
```

When `PAY_TO` is configured, an unpaid request receives HTTP 402 and the client must settle the configured route price before the handler executes.

## Token verdict methodology

The first verdict version deliberately uses transparent, deterministic signals rather than an opaque model score. On a cache miss it performs one batched Base RPC request and one DEX Screener token-pairs request.

It checks:

- deployed bytecode
- standard ERC-20 name, symbol, decimals, and total supply when exposed
- `owner()` when exposed
- EIP-1967 implementation-slot proxy detection
- Base DEX pair presence
- observed Base DEX liquidity
- age of the highest-liquidity pair
- observed liquidity relative to reported FDV

The response includes a `riskSignalScore`, a signal level, and the exact flags that contributed to the score. **A low score means fewer observed warning signals; it does not mean a token is safe.**

The MVP explicitly does **not** claim to detect:

- sell restrictions or honeypot behavior
- malicious source-code logic
- holder concentration
- blacklists or transfer taxes
- off-chain identity or reputation

Those capabilities should only be added when they can be measured reliably and economically.

DEX Screener enrichment is fail-soft: if market enrichment is unavailable, the endpoint still returns its on-chain analysis and marks market data unavailable rather than falsely treating an outage as “no market.”

## Discovery and acquisition

Both paid routes publish the x402 Bazaar discovery extension with example input, input schema, output example, output schema, and machine-readable endpoint descriptions.

The payment manifest also publishes provider metadata directly on the resource object:

- market API: `Prime Agent Market Intel`
- token API: `Prime Agent Token Verdict`
- absolute production resource URLs
- up to five short search tags per route
- `application/json` MIME metadata

The token verdict tags are `token-risk`, `erc20`, `base`, `onchain`, and `liquidity`. These are intentionally aligned with agent search intent rather than branding.

At startup, the provider validates both Bazaar declarations with `validateDiscoveryExtension`. Invalid discovery metadata fails startup instead of silently shipping an unindexable paid route. The resource server also registers the Bazaar server extension so the HTTP method is enriched into the discovery declaration.

Production smoke checks decode the real `PAYMENT-REQUIRED` header and assert that the live paid routes expose:

- the expected absolute resource path
- the expected service name
- required search tags
- a Bazaar discovery block
- HTTP/GET discovery metadata
- a machine-readable Bazaar schema

A facilitator still controls its own catalog. A correct 402 declaration is necessary but does not itself prove the route has been indexed. Catalog visibility and successful settlement should therefore be monitored separately.

## Revenue telemetry

Every successfully delivered paid handler writes a structured log event:

```json
{"event":"x402_paid_delivery","route":"/v1/token/verdict","price":"$0.01","network":"eip155:8453","cacheStatus":"hit"}
```

Because the x402 middleware runs before the handler, this event is emitted only when a paid-mode request reaches the protected resource handler. Render logs can therefore be used to count paid deliveries and compare route usage. Settlement receipts remain the authoritative source for on-chain payment reconciliation.

## Product economics

The token-verdict route defaults to **$0.01**. It avoids LLM inference, batches contract reads into one RPC request, and caches complete verdicts for one minute by default. The initial seller experiment should be evaluated on independent paying wallets, repeat-payer retention, cache-hit rate, upstream failure rate, and gross revenue per upstream request—not raw request counts alone.

## Safety and custody

The repository never stores a wallet private key. `PAY_TO` is only the public receiving address. Ownership and withdrawal remain under the wallet holder's control.
