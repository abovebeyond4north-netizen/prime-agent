const BASE_CHAIN_ID = 8453;
const DEFAULT_BASE_RPC_URL = "https://mainnet.base.org";
const DEFAULT_DEXSCREENER_URL = "https://api.dexscreener.com";
const EIP1967_IMPLEMENTATION_SLOT =
  "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";

const SELECTORS = Object.freeze({
  name: "0x06fdde03",
  symbol: "0x95d89b41",
  decimals: "0x313ce567",
  totalSupply: "0x18160ddd",
  owner: "0x8da5cb5b",
});

export function isEvmAddress(value) {
  return /^0x[0-9a-fA-F]{40}$/.test(String(value ?? ""));
}

function normalizeAddress(value) {
  const address = String(value ?? "");
  if (!isEvmAddress(address)) throw new TypeError("invalid_token_address");
  return address.toLowerCase();
}

function asHex(value, field) {
  if (typeof value !== "string" || !/^0x[0-9a-fA-F]*$/.test(value)) {
    throw new Error("invalid_rpc_" + field);
  }
  return value;
}

function parseUint(hex, field) {
  const value = asHex(hex, field);
  if (value === "0x") return null;
  return BigInt(value);
}

function decodeAddress(hex) {
  const value = asHex(hex, "address");
  if (value === "0x" || value.length < 42) return null;
  const address = "0x" + value.slice(-40).toLowerCase();
  return /^0x0{40}$/.test(address) ? null : address;
}

function decodeString(hex) {
  const value = asHex(hex, "string");
  const data = value.slice(2);
  if (!data) return null;

  try {
    if (data.length >= 128) {
      const offset = Number(BigInt("0x" + data.slice(0, 64)));
      const offsetHex = offset * 2;
      if (offset >= 0 && offsetHex + 64 <= data.length) {
        const length = Number(BigInt("0x" + data.slice(offsetHex, offsetHex + 64)));
        const start = offsetHex + 64;
        const end = start + length * 2;
        if (length >= 0 && end <= data.length) {
          const decoded = Buffer.from(data.slice(start, end), "hex").toString("utf8").replace(/\0+$/g, "");
          return decoded || null;
        }
      }
    }

    if (data.length >= 64) {
      const decoded = Buffer.from(data.slice(0, 64), "hex").toString("utf8").replace(/\0+$/g, "");
      return decoded || null;
    }
  } catch {
    return null;
  }
  return null;
}

function formatUnits(value, decimals) {
  if (value == null || decimals == null) return null;
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 255) return null;
  const raw = value.toString().padStart(decimals + 1, "0");
  if (decimals === 0) return raw;
  const whole = raw.slice(0, -decimals) || "0";
  const fraction = raw.slice(-decimals).replace(/0+$/, "");
  return fraction ? whole + "." + fraction : whole;
}

function implementationFromSlot(hex) {
  const value = asHex(hex, "implementation_slot");
  const data = value.slice(2).padStart(64, "0");
  if (data.length !== 64 || /^0{64}$/.test(data)) return null;
  const address = "0x" + data.slice(-40).toLowerCase();
  return /^0x0{40}$/.test(address) ? null : address;
}

async function rpcBatch({ address, rpcUrl, fetchImpl, timeoutMs }) {
  const requests = [
    { id: 1, required: true, field: "chain_id", method: "eth_chainId", params: [] },
    { id: 2, required: true, field: "code", method: "eth_getCode", params: [address, "latest"] },
    {
      id: 3,
      required: true,
      field: "implementation_slot",
      method: "eth_getStorageAt",
      params: [address, EIP1967_IMPLEMENTATION_SLOT, "latest"],
    },
    {
      id: 4,
      required: false,
      field: "name",
      method: "eth_call",
      params: [{ to: address, data: SELECTORS.name }, "latest"],
    },
    {
      id: 5,
      required: false,
      field: "symbol",
      method: "eth_call",
      params: [{ to: address, data: SELECTORS.symbol }, "latest"],
    },
    {
      id: 6,
      required: false,
      field: "decimals",
      method: "eth_call",
      params: [{ to: address, data: SELECTORS.decimals }, "latest"],
    },
    {
      id: 7,
      required: false,
      field: "total_supply",
      method: "eth_call",
      params: [{ to: address, data: SELECTORS.totalSupply }, "latest"],
    },
    {
      id: 8,
      required: false,
      field: "owner",
      method: "eth_call",
      params: [{ to: address, data: SELECTORS.owner }, "latest"],
    },
  ];

  const response = await fetchImpl(rpcUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "user-agent": "prime-agent-token-verdict/1.0",
    },
    body: JSON.stringify(requests.map(({ required, field, ...request }) => request)),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error("base_rpc_http_" + response.status);

  const payload = await response.json();
  if (!Array.isArray(payload)) throw new Error("base_rpc_batch_unsupported");
  const byId = new Map(payload.map((item) => [Number(item?.id), item]));
  const results = new Map();

  for (const request of requests) {
    const item = byId.get(request.id);
    if (!item) {
      if (request.required) throw new Error("base_rpc_missing_" + request.field);
      results.set(request.field, null);
      continue;
    }
    if (item.error) {
      if (request.required) {
        throw new Error("base_rpc_error_" + (item.error?.code ?? "unknown") + "_" + request.field);
      }
      results.set(request.field, null);
      continue;
    }
    results.set(request.field, item.result ?? null);
  }
  return results;
}

async function fetchDexPairs({ address, dexScreenerUrl, fetchImpl, timeoutMs }) {
  const endpoint =
    dexScreenerUrl.replace(/\/$/, "") +
    "/token-pairs/v1/base/" +
    encodeURIComponent(address);

  const response = await fetchImpl(endpoint, {
    headers: { "user-agent": "prime-agent-token-verdict/1.0" },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error("dexscreener_http_" + response.status);
  const payload = await response.json();
  return Array.isArray(payload) ? payload : [];
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function marketSummary(pairs, address, nowMs) {
  const normalized = address.toLowerCase();
  const relevant = pairs.filter((pair) => {
    if (String(pair?.chainId ?? "").toLowerCase() !== "base") return false;
    const base = String(pair?.baseToken?.address ?? "").toLowerCase();
    const quote = String(pair?.quoteToken?.address ?? "").toLowerCase();
    return base === normalized || quote === normalized;
  });

  let totalLiquidityUsd = 0;
  let topPair = null;
  for (const pair of relevant) {
    const liquidityUsd = Math.max(0, finiteNumber(pair?.liquidity?.usd) ?? 0);
    totalLiquidityUsd += liquidityUsd;
    if (!topPair || liquidityUsd > topPair.liquidityUsd) {
      const created = finiteNumber(pair?.pairCreatedAt);
      const ageHours =
        created != null && created > 0 ? Math.max(0, (nowMs - created) / 3_600_000) : null;
      const buys24h = Math.max(0, finiteNumber(pair?.txns?.h24?.buys) ?? 0);
      const sells24h = Math.max(0, finiteNumber(pair?.txns?.h24?.sells) ?? 0);
      topPair = {
        dexId: String(pair?.dexId ?? ""),
        pairAddress: String(pair?.pairAddress ?? ""),
        url: typeof pair?.url === "string" ? pair.url : null,
        liquidityUsd,
        priceUsd: finiteNumber(pair?.priceUsd),
        fdvUsd: finiteNumber(pair?.fdv),
        marketCapUsd: finiteNumber(pair?.marketCap),
        volume24hUsd: Math.max(0, finiteNumber(pair?.volume?.h24) ?? 0),
        buys24h,
        sells24h,
        transactions24h: buys24h + sells24h,
        pairCreatedAt: created,
        pairAgeHours: ageHours,
      };
    }
  }

  const fdv = topPair?.fdvUsd;
  const liquidityToFdvPct =
    fdv != null && fdv > 0 && totalLiquidityUsd > 0 ? (totalLiquidityUsd / fdv) * 100 : null;

  return {
    pairCount: relevant.length,
    totalLiquidityUsd,
    topPair,
    liquidityToFdvPct,
  };
}

function addFlag(flags, code, severity, detail, points) {
  flags.push({ code, severity, detail, points });
}

function assessSignals({ hasCode, metadata, owner, implementation, market }) {
  const flags = [];

  if (!hasCode) {
    addFlag(flags, "no_contract_code", "critical", "The address has no deployed bytecode.", 100);
  }

  if (metadata.decimals == null || metadata.totalSupplyAtomic == null) {
    addFlag(
      flags,
      "incomplete_erc20_metadata",
      "info",
      "Standard ERC-20 metadata calls did not all return usable values.",
      5,
    );
  }

  if (metadata.decimals != null && (metadata.decimals < 0 || metadata.decimals > 36)) {
    addFlag(
      flags,
      "unusual_decimals",
      "caution",
      "Token decimals are outside the common 0-36 range.",
      10,
    );
  }

  if (owner) {
    addFlag(
      flags,
      "owner_detected",
      "caution",
      "A non-zero owner() address was returned; privileges depend on the contract implementation.",
      10,
    );
  }

  if (implementation) {
    addFlag(
      flags,
      "upgradeable_proxy_detected",
      "caution",
      "The EIP-1967 implementation slot is populated, so token logic may be upgradeable.",
      10,
    );
  }

  if (market.pairCount === 0) {
    addFlag(
      flags,
      "no_dex_market_found",
      "elevated",
      "DEX Screener returned no Base trading pair for this token.",
      35,
    );
  } else if (market.totalLiquidityUsd < 10_000) {
    addFlag(
      flags,
      "low_observed_liquidity",
      "elevated",
      "Observed Base DEX liquidity is below $10,000.",
      30,
    );
  } else if (market.totalLiquidityUsd < 50_000) {
    addFlag(
      flags,
      "thin_observed_liquidity",
      "caution",
      "Observed Base DEX liquidity is below $50,000.",
      15,
    );
  }

  if (market.topPair?.pairAgeHours != null && market.topPair.pairAgeHours < 24) {
    addFlag(
      flags,
      "very_new_market",
      "caution",
      "The highest-liquidity observed pair is less than 24 hours old.",
      10,
    );
  }

  if (market.liquidityToFdvPct != null && market.liquidityToFdvPct < 1) {
    addFlag(
      flags,
      "low_liquidity_to_fdv",
      "caution",
      "Observed liquidity is below 1% of the top pair's reported FDV.",
      10,
    );
  }

  const score = Math.min(100, flags.reduce((sum, flag) => sum + flag.points, 0));
  const signalLevel =
    !hasCode ? "invalid-token" : score >= 50 ? "elevated" : score >= 20 ? "caution" : "limited-observed-signals";

  return { score, signalLevel, flags };
}

export async function inspectBaseToken({
  address,
  rpcUrl = DEFAULT_BASE_RPC_URL,
  dexScreenerUrl = DEFAULT_DEXSCREENER_URL,
  fetchImpl = globalThis.fetch,
  timeoutMs = 8_000,
  nowMs = Date.now(),
} = {}) {
  const token = normalizeAddress(address);
  if (typeof fetchImpl !== "function") throw new TypeError("fetch_unavailable");

  const rpc = await rpcBatch({
    address: token,
    rpcUrl,
    fetchImpl,
    timeoutMs,
  });

  const chainId = Number(parseUint(rpc.get("chain_id"), "chain_id"));
  if (chainId !== BASE_CHAIN_ID) throw new Error("unexpected_chain_id_" + chainId);

  const code = asHex(rpc.get("code"), "code");
  const hasCode = code !== "0x";
  const implementation = implementationFromSlot(rpc.get("implementation_slot"));

  const decimalsBig = rpc.get("decimals") == null ? null : parseUint(rpc.get("decimals"), "decimals");
  const decimals =
    decimalsBig != null && decimalsBig <= 255n ? Number(decimalsBig) : null;
  const supply =
    rpc.get("total_supply") == null ? null : parseUint(rpc.get("total_supply"), "total_supply");
  const owner = rpc.get("owner") == null ? null : decodeAddress(rpc.get("owner"));

  const metadata = {
    name: rpc.get("name") == null ? null : decodeString(rpc.get("name")),
    symbol: rpc.get("symbol") == null ? null : decodeString(rpc.get("symbol")),
    decimals,
    totalSupplyAtomic: supply?.toString() ?? null,
    totalSupply: supply != null && decimals != null ? formatUnits(supply, decimals) : null,
  };

  let dexPairs = [];
  let dexScreenerAvailable = true;
  try {
    dexPairs = await fetchDexPairs({
      address: token,
      dexScreenerUrl,
      fetchImpl,
      timeoutMs,
    });
  } catch {
    dexScreenerAvailable = false;
  }

  const market = dexScreenerAvailable
    ? marketSummary(dexPairs, token, nowMs)
    : {
        pairCount: 0,
        totalLiquidityUsd: 0,
        topPair: null,
        liquidityToFdvPct: null,
      };

  const assessment = assessSignals({
    hasCode,
    metadata,
    owner,
    implementation,
    market,
  });

  if (!dexScreenerAvailable) {
    assessment.flags.push({
      code: "market_data_unavailable",
      severity: "info",
      detail: "DEX Screener market enrichment was unavailable; market-related signals are incomplete.",
      points: 0,
    });
  }

  return {
    observedAt: new Date(nowMs).toISOString(),
    network: "base-mainnet",
    chainId,
    token,
    contract: {
      hasCode,
      bytecodeBytes: hasCode ? Math.max(0, (code.length - 2) / 2) : 0,
      owner,
      eip1967Proxy: {
        detected: Boolean(implementation),
        implementation,
      },
    },
    metadata,
    market: {
      ...market,
      sourceAvailable: dexScreenerAvailable,
    },
    verdict: {
      riskSignalScore: assessment.score,
      signalLevel: assessment.signalLevel,
      flags: assessment.flags.map(({ points, ...flag }) => flag),
      methodology:
        "Deterministic public-chain and market-structure signals. Lower scores mean fewer observed signals, not proof that a token is safe.",
    },
    coverage: {
      checked: [
        "deployed bytecode",
        "standard ERC-20 metadata",
        "owner() when exposed",
        "EIP-1967 implementation slot",
        "Base DEX pair presence",
        "observed liquidity",
        "pair age",
        "liquidity-to-FDV ratio",
      ],
      notChecked: [
        "sell simulation or honeypot behavior",
        "source-code audit",
        "holder concentration",
        "blacklist or transfer-tax behavior",
        "off-chain identity",
      ],
    },
    sources: {
      rpc: "Base JSON-RPC latest state",
      market: dexScreenerAvailable ? "DEX Screener Base token pairs" : null,
    },
  };
}

export const TOKEN_VERDICT_CONSTANTS = Object.freeze({
  chainId: BASE_CHAIN_ID,
  rpcUrl: DEFAULT_BASE_RPC_URL,
  dexScreenerUrl: DEFAULT_DEXSCREENER_URL,
  eip1967ImplementationSlot: EIP1967_IMPLEMENTATION_SLOT,
  selectors: SELECTORS,
});
