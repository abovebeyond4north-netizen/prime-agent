# x402 Market Provider

A low-marginal-cost x402 seller service for Prime Agent. It currently exposes two products:

- Bazaar market opportunities ranked by repeat demand, recency, safely inferable USDC monetization, and an activity-farming penalty.
- A Base onchain preflight that bundles common agent counterparty checks into one paid response.

The market endpoint uses Coinbase's public Bazaar catalog. The onchain preflight reads confirmed Base state through JSON-RPC and has no paid upstream dependency by default.

## Credentials

The service starts in public-analysis mode when payment credentials are absent. To activate paid x402 settlement through Coinbase CDP, supply these environment variables at runtime:

- `CDP_API_KEY_ID`
- `CDP_API_KEY_SECRET`
- `CDP_WALLET_SECRET`

No private key or credential is stored in this repository. When all three values are present, `createX402Server` activates the x402 payment gate. Without them, the same analysis routes remain public so hosting and demand validation can run safely.

Optional runtime settings:

- `PORT` (default `8402`)
- `X402_PRICE` (default `$0.01`) for the Bazaar opportunity route
- `X402_PREFLIGHT_PRICE` (default `$0.01`) for the Base preflight route
- `X402_DISCOVERY_URL` (defaults to Coinbase's public x402 discovery endpoint)
- `BASE_RPC_URL` (default `https://mainnet.base.org`)
- `BASE_RPC_TIMEOUT_MS` (default `8000`, clamped to 1-30 seconds)
- `PREFLIGHT_CACHE_TTL_MS` (default `15000`, clamped to 1-60 seconds)

The default Base RPC is suitable for development and initial demand validation. Set `BASE_RPC_URL` to a production RPC provider when sustained paid traffic requires higher limits.

## Run

```bash
cd tools/x402-provider
npm install
npm test
npm start
```

Free health check:

```bash
curl http://localhost:8402/health
```

Bazaar market route:

```text
GET /v1/x402/opportunities?limit=25&organicOnly=true
```

Base preflight route:

```text
GET /v1/onchain/preflight?address=0x1111111111111111111111111111111111111111
GET /v1/onchain/preflight?address=0x1111111111111111111111111111111111111111&spender=0x2222222222222222222222222222222222222222
```

The preflight bundles these Base mainnet reads:

- chain ID validation
- native ETH balance
- confirmed transaction count / nonce
- contract bytecode detection
- EIP-1967 implementation-slot proxy detection
- native USDC balance
- optional native USDC allowance for a supplied spender

It returns exact integer quantities plus human-readable ETH/USDC amounts. The `riskSummary.flags` field is deliberately descriptive rather than a fraud or solvency score.

The preflight uses one JSON-RPC batch and a bounded 15-second response cache by default, keeping upstream request count and marginal cost low. Cache capacity is capped at 512 query keys to avoid unbounded address-driven memory growth.

When payment credentials are configured, the official CDP x402 integration returns `402 Payment Required` to unpaid clients and settles a valid x402 payment before a route handler runs. Routes created with `createX402Server` are eligible for CDP Bazaar discovery after real settlement through the CDP facilitator.

## Product logic

The product avoids LLM inference on the hot path. Public registry transforms and deterministic Base reads keep marginal cost low enough to test millipayment economics. The next expansion decision should be driven by independent paid wallets, repeat-payer retention, cache hit rate, and RPC cost per successful settlement rather than raw request counts.
