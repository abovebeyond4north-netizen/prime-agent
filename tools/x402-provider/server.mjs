import express from "express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { declareDiscoveryExtension } from "@x402/extensions/bazaar";

const PORT = Number(process.env.PORT ?? 8402);
const PRICE = process.env.X402_PRICE ?? "$0.01";
const NETWORK = process.env.X402_NETWORK ?? "eip155:8453";
const FACILITATOR_URL = process.env.X402_FACILITATOR_URL ?? "https://facilitator.payai.network";
const PAY_TO = (process.env.PAY_TO ?? "").trim();
const DISCOVERY_URL =
  process.env.X402_DISCOVERY_URL ??
  "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources";

const validPayTo = /^0x[a-fA-F0-9]{40}$/.test(PAY_TO);
const paymentEnabled = validPayTo;

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

if (paymentEnabled) {
  const facilitatorClient = new HTTPFacilitatorClient({ url: FACILITATOR_URL });
  const resourceServer = new x402ResourceServer(facilitatorClient).register(
    "eip155:*",
    new ExactEvmScheme(),
  );

  const discovery = declareDiscoveryExtension({
    input: { limit: 25, organicOnly: true },
    inputSchema: {
      type: "object",
      properties: {
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 100,
          description: "Maximum number of ranked opportunities to return.",
        },
        organicOnly: {
          type: "boolean",
          description: "Exclude resources that do not show repeat independent payer demand.",
        },
      },
    },
    output: {
      example: {
        count: 1,
        opportunities: [
          {
            resource: "https://example.com/api",
            serviceName: "Example API",
            priceUsd: 0.01,
            calls30d: 1000,
            uniquePayers30d: 25,
            callsPerPayer: 40,
            repeatDemand: true,
            opportunityScore: 123.45,
          },
        ],
      },
      schema: {
        type: "object",
        properties: {
          generatedAt: { type: "string" },
          source: { type: "string" },
          methodology: { type: "string" },
          count: { type: "integer" },
          opportunities: { type: "array", items: { type: "object" } },
        },
      },
    },
  });

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
          description:
            "Rank x402 seller opportunities by repeat buyers, call reuse, recency, USDC monetization, and suspicious-activity penalties.",
          mimeType: "application/json",
          extensions: { ...discovery },
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
    paymentEnabled,
    mode: paymentEnabled ? "x402-paid" : "public-analysis",
    network: paymentEnabled ? NETWORK : null,
    facilitator: paymentEnabled ? FACILITATOR_URL : null,
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

app.listen(PORT, () => {
  console.log("x402 market provider listening on :" + PORT);
  if (PAY_TO && !validPayTo) {
    console.warn("PAY_TO is present but is not a valid 20-byte EVM address; payment gate disabled.");
  }
  console.log(
    paymentEnabled
      ? "x402 paid mode: GET /v1/x402/opportunities (" + PRICE + ", " + NETWORK + ")"
      : "public analysis mode: GET /v1/x402/opportunities (set PAY_TO to activate payments)",
  );
});
