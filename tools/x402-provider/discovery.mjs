import {
  bazaarResourceServerExtension,
  declareDiscoveryExtension,
  validateDiscoveryExtension,
} from "@x402/extensions/bazaar";

export const DEFAULT_PUBLIC_BASE_URL =
  "https://prime-agent-x402-provider.onrender.com";

function cleanBaseUrl(value) {
  const url = new URL(String(value || DEFAULT_PUBLIC_BASE_URL));
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("public_base_url_must_be_http");
  }
  return url.toString().replace(/\/$/, "");
}

export function buildDiscoveryBundle(publicBaseUrl = DEFAULT_PUBLIC_BASE_URL) {
  const baseUrl = cleanBaseUrl(publicBaseUrl);

  const marketDescription =
    "Rank x402 seller opportunities by repeat buyers, call reuse, recency, USDC monetization, and suspicious-activity penalties.";
  const tokenDescription =
    "Inspect a Base ERC-20 token using deterministic contract, liquidity, market-age, ownership, and proxy signals without LLM inference.";

  const marketDiscovery = declareDiscoveryExtension({
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
          description:
            "Exclude resources that do not show repeat independent payer demand.",
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

  marketDiscovery.bazaar.info.input.method = "GET";

  const tokenVerdictDiscovery = declareDiscoveryExtension({
    input: { address: "0x1111111111111111111111111111111111111111" },
    inputSchema: {
      type: "object",
      required: ["address"],
      properties: {
        address: {
          type: "string",
          pattern: "^0x[0-9a-fA-F]{40}$",
          description: "Base mainnet ERC-20 contract address to inspect.",
        },
      },
    },
    output: {
      example: {
        network: "base-mainnet",
        token: "0x1111111111111111111111111111111111111111",
        metadata: { symbol: "TOKEN", decimals: 18 },
        market: { pairCount: 2, totalLiquidityUsd: 250000 },
        verdict: {
          riskSignalScore: 0,
          signalLevel: "limited-observed-signals",
          flags: [],
        },
      },
      schema: {
        type: "object",
        properties: {
          observedAt: { type: "string" },
          network: { type: "string" },
          chainId: { type: "integer" },
          token: { type: "string" },
          contract: { type: "object" },
          metadata: { type: "object" },
          market: { type: "object" },
          verdict: { type: "object" },
          coverage: { type: "object" },
          sources: { type: "object" },
          cache: { type: "object" },
        },
      },
    },
  });

  tokenVerdictDiscovery.bazaar.info.input.method = "GET";

  const marketResource = {
    url: baseUrl + "/v1/x402/opportunities",
    description: marketDescription,
    mimeType: "application/json",
    serviceName: "Prime Agent Market Intel",
    tags: ["x402", "seller-market", "agents", "demand", "base"],
  };

  const tokenVerdictResource = {
    url: baseUrl + "/v1/token/verdict",
    description: tokenDescription,
    mimeType: "application/json",
    serviceName: "Prime Agent Token Verdict",
    tags: ["token-risk", "erc20", "base", "onchain", "liquidity"],
  };

  const declarations = {
    market: marketDiscovery,
    tokenVerdict: tokenVerdictDiscovery,
  };

  return {
    baseUrl,
    marketDescription,
    tokenDescription,
    marketDiscovery,
    tokenVerdictDiscovery,
    marketResource,
    tokenVerdictResource,
    declarations,
  };
}

export function validateDiscoveryBundle(bundle) {
  const errors = [];

  for (const [name, declaration] of Object.entries(bundle.declarations)) {
    const extension = declaration?.bazaar;
    if (!extension) {
      errors.push(name + ": missing bazaar extension");
      continue;
    }
    const result = validateDiscoveryExtension(extension);
    if (!result.valid) {
      for (const error of result.errors ?? ["unknown validation error"]) {
        errors.push(name + ": " + error);
      }
    }
  }

  for (const [name, resource] of [
    ["market", bundle.marketResource],
    ["tokenVerdict", bundle.tokenVerdictResource],
  ]) {
    if (resource.serviceName.length > 32) {
      errors.push(name + ": serviceName exceeds 32 characters");
    }
    if (resource.tags.length > 5) {
      errors.push(name + ": more than 5 tags");
    }
    for (const tag of resource.tags) {
      if (tag.length > 32 || !/^[\x20-\x7E]+$/.test(tag)) {
        errors.push(name + ": invalid tag " + JSON.stringify(tag));
      }
    }
    if (!/^[\x20-\x7E]+$/.test(resource.serviceName)) {
      errors.push(name + ": serviceName must be printable ASCII");
    }
    const url = new URL(resource.url);
    if (!["http:", "https:"].includes(url.protocol)) {
      errors.push(name + ": resource URL must be absolute HTTP(S)");
    }
  }

  return { valid: errors.length === 0, errors };
}

export function registerBazaarExtension(resourceServer) {
  if (typeof resourceServer.registerExtension === "function") {
    resourceServer.registerExtension(bazaarResourceServerExtension);
    return resourceServer;
  }
  if (typeof resourceServer.useExtension === "function") {
    resourceServer.useExtension(bazaarResourceServerExtension);
    return resourceServer;
  }
  throw new Error("x402 resource server lacks Bazaar extension registration API");
}
