import express from "express";
import { createX402Server } from "@coinbase/cdp-sdk/x402";
import { paymentMiddlewareFromHTTPServer } from "@x402/express";

import { fetchBasePreflight, isEvmAddress } from "./onchain.mjs";

const PORT = Number(process.env.PORT ?? 8402);
const PRICE = process.env.X402_PRICE ?? "$0.01";
const PREFLIGHT_PRICE = process.env.X402_PREFLIGHT_PRICE ?? "$0.01";
const DISCOVERY_URL =
  process.env.X402_DISCOVERY_URL ??
  "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources";
const BASE_RPC_URL = process.env.BASE_RPC_URL ?? "https://mainnet.base.org";
const BASE_RPC_TIMEOUT_MS = Math.max(
  1_000,
  Math.min(30_000, Number(process.env.BASE_RPC_TIMEOUT_MS ?? 8_000)),
);
const PREFLIGHT_CACHE_TTL_MS = Math.max(
  1_000,
  Math.min(60_000, Number(process.env.PREFLIGHT_CACHE_TTL_MS ?? 15_000)),
);
const PREFLIGHT_CACHE_MAX = 512;

const cdpCredentialNames = ["CDP_API_KEY_ID", "CDP_API_KEY_SECRET", "CDP_WALLET_SECRET"];
const paymentEnabled = cdpCredentialNames.every((name) => Boolean(process.env[name]));

const app = express();
app.disable("x-powered-by");

function parsePriceUsd(resource) {
  const knownUsdc = new Set([
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    "0x036cbd53842c5426634e7929541ec2318f3dcf7e",
  ]);
  const prices = [];
  for (const req of resource.accepts ?? []) {
    const asset = String(req?.asset ?? "").toLowerCase();
    const name = String(req?.extra?.name ?? "").toLowerCase();
    const symbol = String(req?.extra?.symbol ?? "").toLowerCase();
    if (!(knownUsdc.has(asset) || name.includes("usd coin") || symbol === "usdc")) continue;
    const amount = Number(req?.amount);
    if (Number.isFinite(amount)) prices.push(amount / 1_000_000);
  }
  return prices.length ? Math.min(...prices) : null;
}

function farmingLikely(calls, payers) {
  return calls >= 100 && payers >= 50 && payers / Math.max(calls, 1) >= 0.85;
}

function rank(resource, nowMs = Date.now()) {
  const quality = resource.quality ?? {};
  const calls = Math.max(0, Number(quality.l30DaysTotalCalls ?? 0));
  const payers = Math.max(0, Number(quality.l30DaysUniquePayers ?? 0));
  const reuse = payers > 0 ? calls / payers : 0;
  const last = Date.parse(quality.lastCalledAt ?? "");
  const ageDays = Number.isFinite(last) ? Math.max(0, (nowMs - last) / 86_400_000) : 30;
  const suspicious = farmingLikely(calls, payers);
  const organic = payers >= 3 && reuse >= 3 && !suspicious;
  const recency = Math.exp(-(ageDays / 14));
  const demand =
    Math.log1p(payers) *
    Math.log1p(reuse) *
    Math.log1p(calls) *
    recency *
    (suspicious ? 0.08 : organic ? 1 : 0.35);
  const priceUsd = parsePriceUsd(resource);
  const revenue30d = priceUsd == null ? null : priceUsd * calls;
  const monetization = priceUsd == null ? 0.5 : Math.log1p(Math.max(0, revenue30d));
  return {
    resource: resource.resource,
    serviceName: resource.serviceName ?? "",
    description: resource.description ?? "",
    tags: resource.tags ?? [],
    priceUsd,
    calls30d: calls,
    uniquePayers30d: payers,
    callsPerPayer: reuse,
    lastCalledAt: quality.lastCalledAt ?? null,
    repeatDemand: organic,
    suspectedFarming: suspicious,
    estimatedRevenue30d: revenue30d,
    opportunityScore: demand * (1 + monetization),
  };
}

async function fetchCatalog() {
  const rows = [];
  let offset = 0;
  let total = Infinity;
  while (offset < total) {
    const url = new URL(DISCOVERY_URL);
    url.searchParams.set("limit", "500");
    url.searchParams.set("offset", String(offset));
    const response = await fetch(url, {
      headers: { "user-agent": "prime-agent-x402-provider/1.0" },
      signal: AbortSignal.timeout(20_000),
    });
    if (!response.ok) throw new Error("Bazaar request failed: " + response.status);
    const payload = await response.json();
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (!items.length) break;
    rows.push(...items);
    offset += items.length;
    total = Number(payload.pagination?.total ?? offset);
  }
  return rows;
}

let cache = { at: 0, rows: [] };
async function marketSnapshot() {
  if (Date.now() - cache.at < 300_000 && cache.rows.length) return cache.rows;
  const resources = await fetchCatalog();
  const rows = resources.map((resource) => rank(resource));
  rows.sort((a, b) => b.opportunityScore - a.opportunityScore);
  cache = { at: Date.now(), rows };
  return rows;
}

const preflightCache = new Map();

function preflightCacheKey(address, spender) {
  return address.toLowerCase() + ":" + (spender ? spender.toLowerCase() : "");
}

function getCachedPreflight(key) {
  const entry = preflightCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.at >= PREFLIGHT_CACHE_TTL_MS) {
    preflightCache.delete(key);
    return null;
  }
  preflightCache.delete(key);
  preflightCache.set(key, entry);
  return entry.value;
}

function setCachedPreflight(key, value) {
  while (preflightCache.size >= PREFLIGHT_CACHE_MAX) {
    const oldest = preflightCache.keys().next().value;
    if (oldest === undefined) break;
    preflightCache.delete(oldest);
  }
  preflightCache.set(key, { at: Date.now(), value });
}

async function onchainPreflight(address, spender) {
  const key = preflightCacheKey(address, spender);
  const cached = getCachedPreflight(key);
  if (cached) return { ...cached, cache: "hit" };

  const value = await fetchBasePreflight({
    address,
    spender,
    rpcUrl: BASE_RPC_URL,
    timeoutMs: BASE_RPC_TIMEOUT_MS,
  });
  setCachedPreflight(key, value);
  return { ...value, cache: "miss" };
}

if (paymentEnabled) {
  const x402Server = await createX402Server({
    builderCode: "prime_x402_market",
    routes: {
      "GET /v1/x402/opportunities": {
        price: PRICE,
        description:
          "Rank public x402 Bazaar services by repeat buyers, call reuse, recency, USDC monetization, and suspicious-activity penalties.",
      },
      "GET /v1/onchain/preflight": {
        price: PREFLIGHT_PRICE,
        description:
          "Return a low-latency Base wallet preflight with ETH and USDC balances, nonce, contract/proxy detection, and optional USDC allowance.",
      },
    },
  });
  app.use(paymentMiddlewareFromHTTPServer(x402Server));
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    product: "prime-agent-x402-market",
    routes: ["/v1/x402/opportunities", "/v1/onchain/preflight"],
    paymentEnabled,
    mode: paymentEnabled ? "x402-paid" : "public-analysis",
  });
});

app.get("/v1/x402/opportunities", async (req, res) => {
  try {
    const limit = Math.max(1, Math.min(100, Number(req.query.limit ?? 25)));
    const organicOnly = String(req.query.organicOnly ?? "true") !== "false";
    const rows = await marketSnapshot();
    const selected = (organicOnly ? rows.filter((row) => row.repeatDemand) : rows).slice(0, limit);
    res.json({
      generatedAt: new Date().toISOString(),
      source: "Coinbase public x402 Bazaar discovery catalog",
      methodology:
        "Observed 30-day calls and unique payers; repeat-use and recency weighting; high payer-to-call ratios at scale are penalized; revenue is estimated only for recognizable USDC requirements.",
      count: selected.length,
      opportunities: selected,
    });
  } catch (error) {
    console.error(error);
    res.status(502).json({ error: "market_data_unavailable" });
  }
});

app.get("/v1/onchain/preflight", async (req, res) => {
  const address = String(req.query.address ?? "");
  const spender = req.query.spender == null ? null : String(req.query.spender);
  if (!isEvmAddress(address)) {
    return res.status(400).json({ error: "invalid_address" });
  }
  if (spender && !isEvmAddress(spender)) {
    return res.status(400).json({ error: "invalid_spender" });
  }

  try {
    const preflight = await onchainPreflight(address, spender);
    return res.json(preflight);
  } catch (error) {
    console.error(error);
    return res.status(502).json({ error: "base_rpc_unavailable" });
  }
});

app.listen(PORT, () => {
  console.log("x402 market provider listening on :" + PORT);
  console.log(
    paymentEnabled
      ? "paid endpoints: /v1/x402/opportunities (" +
          PRICE +
          "), /v1/onchain/preflight (" +
          PREFLIGHT_PRICE +
          ")"
      : "public analysis mode: x402 payment credentials not configured",
  );
});
