import express from "express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import {
  buildDiscoveryBundle,
  registerBazaarExtension,
  validateDiscoveryBundle,
} from "./discovery.mjs";
import { inspectBaseToken, isEvmAddress } from "./token_verdict.mjs";

const PORT = Number(process.env.PORT ?? 8402);
const PRICE = process.env.X402_PRICE ?? "$0.01";
const TOKEN_VERDICT_PRICE = process.env.X402_TOKEN_VERDICT_PRICE ?? "$0.01";
const NETWORK = process.env.X402_NETWORK ?? "eip155:8453";
const FACILITATOR_URL = process.env.X402_FACILITATOR_URL ?? "https://facilitator.payai.network";
const PAY_TO = (process.env.PAY_TO ?? "").trim();
const DISCOVERY_URL =
  process.env.X402_DISCOVERY_URL ??
  "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources";
const BASE_RPC_URL = process.env.BASE_RPC_URL ?? "https://mainnet.base.org";
const DEXSCREENER_URL = process.env.DEXSCREENER_URL ?? "https://api.dexscreener.com";
const TOKEN_VERDICT_TIMEOUT_MS = boundedNumber("TOKEN_VERDICT_TIMEOUT_MS", 8_000, 1_000, 30_000);
const TOKEN_VERDICT_CACHE_TTL_MS = boundedNumber(
  "TOKEN_VERDICT_CACHE_TTL_MS",
  60_000,
  5_000,
  300_000,
);
const TOKEN_VERDICT_CACHE_MAX = boundedNumber("TOKEN_VERDICT_CACHE_MAX", 1_024, 32, 10_000);
const PUBLIC_BASE_URL =
  process.env.X402_PUBLIC_BASE_URL ??
  process.env.RENDER_EXTERNAL_URL ??
  "https://prime-agent-x402-provider.onrender.com";

const validPayTo = /^0x[a-fA-F0-9]{40}$/.test(PAY_TO);
const paymentEnabled = validPayTo;

const app = express();
app.disable("x-powered-by");

const discoveryBundle = buildDiscoveryBundle(PUBLIC_BASE_URL);
const discoveryValidation = validateDiscoveryBundle(discoveryBundle);
if (!discoveryValidation.valid) {
  throw new Error(
    "invalid_bazaar_discovery_metadata: " + discoveryValidation.errors.join("; "),
  );
}

function logPaidDelivery(route, price, extra = {}) {
  if (!paymentEnabled) return;
  console.log(
    JSON.stringify({
      event: "x402_paid_delivery",
      route,
      price,
      network: NETWORK,
      at: new Date().toISOString(),
      ...extra,
    }),
  );
}

function boundedNumber(name, fallback, minimum, maximum) {
  const parsed = Number(process.env[name] ?? fallback);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, Math.floor(parsed)));
}

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
      headers: { "user-agent": "prime-agent-x402-provider/2.0" },
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

const tokenVerdictCache = new Map();

function readTokenVerdictCache(key) {
  const entry = tokenVerdictCache.get(key);
  if (!entry) return null;
  const ageMs = Date.now() - entry.at;
  if (ageMs >= TOKEN_VERDICT_CACHE_TTL_MS) {
    tokenVerdictCache.delete(key);
    return null;
  }
  tokenVerdictCache.delete(key);
  tokenVerdictCache.set(key, entry);
  return { value: entry.value, ageMs };
}

function writeTokenVerdictCache(key, value) {
  while (tokenVerdictCache.size >= TOKEN_VERDICT_CACHE_MAX) {
    const oldest = tokenVerdictCache.keys().next().value;
    if (oldest == null) break;
    tokenVerdictCache.delete(oldest);
  }
  tokenVerdictCache.set(key, { at: Date.now(), value });
}

async function tokenVerdict(address) {
  const key = address.toLowerCase();
  const cached = readTokenVerdictCache(key);
  if (cached) {
    return {
      ...cached.value,
      cache: { status: "hit", ageMs: cached.ageMs, ttlMs: TOKEN_VERDICT_CACHE_TTL_MS },
    };
  }

  const value = await inspectBaseToken({
    address: key,
    rpcUrl: BASE_RPC_URL,
    dexScreenerUrl: DEXSCREENER_URL,
    timeoutMs: TOKEN_VERDICT_TIMEOUT_MS,
  });
  writeTokenVerdictCache(key, value);
  return {
    ...value,
    cache: { status: "miss", ageMs: 0, ttlMs: TOKEN_VERDICT_CACHE_TTL_MS },
  };
}

if (paymentEnabled) {
  const facilitatorClient = new HTTPFacilitatorClient({ url: FACILITATOR_URL });
  const resourceServer = new x402ResourceServer(facilitatorClient).register(
    "eip155:*",
    new ExactEvmScheme(),
  );
  registerBazaarExtension(resourceServer);

  app.use(
    paymentMiddleware(
      {
        "GET /v1/x402/opportunities": {
          accepts: {
            scheme: "exact",
            price: PRICE,
            network: NETWORK,
            payTo: PAY_TO,
          },
          resource: discoveryBundle.marketResource.url,
          description:
            discoveryBundle.marketResource.serviceName +
            " — " +
            discoveryBundle.marketDescription +
            " Tags: " +
            discoveryBundle.marketResource.tags.join(", ") +
            ".",
          mimeType: "application/json",
          serviceName: discoveryBundle.marketResource.serviceName,
          tags: discoveryBundle.marketResource.tags,
          extensions: { ...discoveryBundle.marketDiscovery },
        },
        "GET /v1/token/verdict": {
          accepts: {
            scheme: "exact",
            price: TOKEN_VERDICT_PRICE,
            network: NETWORK,
            payTo: PAY_TO,
          },
          resource: discoveryBundle.tokenVerdictResource.url,
          description:
            discoveryBundle.tokenVerdictResource.serviceName +
            " — " +
            discoveryBundle.tokenDescription +
            " Tags: " +
            discoveryBundle.tokenVerdictResource.tags.join(", ") +
            ".",
          mimeType: "application/json",
          serviceName: discoveryBundle.tokenVerdictResource.serviceName,
          tags: discoveryBundle.tokenVerdictResource.tags,
          extensions: { ...discoveryBundle.tokenVerdictDiscovery },
        },
      },
      resourceServer,
    ),
  );
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    product: "prime-agent-x402-market",
    route: "/v1/x402/opportunities",
    routes: ["/v1/x402/opportunities", "/v1/token/verdict"],
    paymentEnabled,
    mode: paymentEnabled ? "x402-paid" : "public-analysis",
    network: paymentEnabled ? NETWORK : null,
    facilitator: paymentEnabled ? FACILITATOR_URL : null,
    gitCommit: process.env.RENDER_GIT_COMMIT ?? null,
    gitBranch: process.env.RENDER_GIT_BRANCH ?? null,
    serviceUrl: process.env.RENDER_EXTERNAL_URL ?? null,
    discovery: {
      publicBaseUrl: discoveryBundle.baseUrl,
      services: [
        {
          name: discoveryBundle.marketResource.serviceName,
          url: discoveryBundle.marketResource.url,
          tags: discoveryBundle.marketResource.tags,
        },
        {
          name: discoveryBundle.tokenVerdictResource.serviceName,
          url: discoveryBundle.tokenVerdictResource.url,
          tags: discoveryBundle.tokenVerdictResource.tags,
        },
      ],
    },
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
    logPaidDelivery("/v1/x402/opportunities", PRICE, {
      resultCount: selected.length,
    });
  } catch (error) {
    console.error(error);
    res.status(502).json({ error: "market_data_unavailable" });
  }
});

app.get("/v1/token/verdict", async (req, res) => {
  const address = String(req.query.address ?? "");
  if (!isEvmAddress(address)) {
    return res.status(400).json({ error: "invalid_token_address" });
  }

  try {
    const result = await tokenVerdict(address);
    logPaidDelivery("/v1/token/verdict", TOKEN_VERDICT_PRICE, {
      token: address.toLowerCase(),
      cacheStatus: result.cache?.status ?? null,
    });
    return res.json(result);
  } catch (error) {
    console.error(error);
    return res.status(502).json({ error: "token_verdict_upstream_unavailable" });
  }
});

app.listen(PORT, () => {
  console.log("x402 market provider listening on :" + PORT);
  if (PAY_TO && !validPayTo) {
    console.warn("PAY_TO is present but is not a valid 20-byte EVM address; payment gate disabled.");
  }
  console.log(
    paymentEnabled
      ? "x402 paid mode: market " +
        PRICE +
        ", token verdict " +
        TOKEN_VERDICT_PRICE +
        " (" +
        NETWORK +
        ")"
      : "public analysis mode: market + token verdict routes (set PAY_TO to activate payments)",
  );
});
