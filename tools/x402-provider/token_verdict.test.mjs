import assert from "node:assert/strict";
import test from "node:test";

import {
  TOKEN_VERDICT_CONSTANTS,
  inspectBaseToken,
  isEvmAddress,
} from "./token_verdict.mjs";

const TOKEN = "0x1111111111111111111111111111111111111111";
const OWNER = "0x2222222222222222222222222222222222222222";
const IMPLEMENTATION = "3333333333333333333333333333333333333333";
const NOW = Date.parse("2026-09-19T12:00:00Z");

function quantity(value) {
  return "0x" + BigInt(value).toString(16);
}

function word(value) {
  return BigInt(value).toString(16).padStart(64, "0");
}

function abiString(value) {
  const bytes = Buffer.from(value, "utf8");
  const body = bytes.toString("hex").padEnd(Math.ceil(bytes.length / 32) * 64 || 64, "0");
  return "0x" + word(32) + word(bytes.length) + body;
}

function addressWord(address) {
  return "0x" + address.slice(2).padStart(64, "0");
}

function zeroSlot() {
  return "0x" + "0".repeat(64);
}

function makeFetch({
  chainId = "0x2105",
  code = "0x6001600055",
  implementationSlot = zeroSlot(),
  name = abiString("Example Token"),
  symbol = abiString("EXM"),
  decimals = quantity(18),
  totalSupply = quantity(1_000_000n * 10n ** 18n),
  owner = addressWord("0x0000000000000000000000000000000000000000"),
  optionalErrors = new Set(),
  pairs = [],
  dexStatus = 200,
} = {}) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url: String(url), init });

    if (String(init.method ?? "GET").toUpperCase() === "POST") {
      const requests = JSON.parse(init.body);
      const byId = {
        1: chainId,
        2: code,
        3: implementationSlot,
        4: name,
        5: symbol,
        6: decimals,
        7: totalSupply,
        8: owner,
      };
      return {
        ok: true,
        status: 200,
        json: async () =>
          requests.map((request) =>
            optionalErrors.has(request.id)
              ? {
                  id: request.id,
                  jsonrpc: "2.0",
                  error: { code: -32000, message: "execution reverted" },
                }
              : { id: request.id, jsonrpc: "2.0", result: byId[request.id] },
          ),
      };
    }

    return {
      ok: dexStatus >= 200 && dexStatus < 300,
      status: dexStatus,
      json: async () => pairs,
    };
  };
  return { fetchImpl, calls };
}

test("isEvmAddress accepts only 20-byte hexadecimal addresses", () => {
  assert.equal(isEvmAddress(TOKEN), true);
  assert.equal(isEvmAddress("0x1234"), false);
  assert.equal(isEvmAddress("not-an-address"), false);
});

test("inspectBaseToken returns normalized metadata and mature liquid market signals", async () => {
  const pairCreatedAt = NOW - 10 * 24 * 60 * 60 * 1000;
  const { fetchImpl, calls } = makeFetch({
    pairs: [
      {
        chainId: "base",
        dexId: "uniswap",
        pairAddress: "0x4444444444444444444444444444444444444444",
        url: "https://dexscreener.com/base/example",
        baseToken: { address: TOKEN, name: "Example Token", symbol: "EXM" },
        quoteToken: {
          address: "0x4200000000000000000000000000000000000006",
          name: "Wrapped Ether",
          symbol: "WETH",
        },
        priceUsd: "1.25",
        liquidity: { usd: 250000 },
        fdv: 5000000,
        marketCap: 4500000,
        volume: { h24: 100000 },
        txns: { h24: { buys: 80, sells: 70 } },
        pairCreatedAt,
      },
    ],
  });

  const result = await inspectBaseToken({
    address: TOKEN,
    rpcUrl: "https://rpc.invalid.test",
    dexScreenerUrl: "https://dex.invalid.test",
    fetchImpl,
    nowMs: NOW,
  });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "https://rpc.invalid.test");
  assert.equal(
    calls[1].url,
    "https://dex.invalid.test/token-pairs/v1/base/" + TOKEN,
  );
  assert.equal(result.chainId, 8453);
  assert.equal(result.metadata.name, "Example Token");
  assert.equal(result.metadata.symbol, "EXM");
  assert.equal(result.metadata.decimals, 18);
  assert.equal(result.metadata.totalSupply, "1000000");
  assert.equal(result.contract.hasCode, true);
  assert.equal(result.contract.owner, null);
  assert.equal(result.contract.eip1967Proxy.detected, false);
  assert.equal(result.market.pairCount, 1);
  assert.equal(result.market.totalLiquidityUsd, 250000);
  assert.equal(result.market.topPair.transactions24h, 150);
  assert.equal(result.market.liquidityToFdvPct, 5);
  assert.equal(result.verdict.riskSignalScore, 0);
  assert.equal(result.verdict.signalLevel, "limited-observed-signals");
  assert.deepEqual(result.verdict.flags, []);
});

test("inspectBaseToken combines ownership, upgradeability, liquidity, age, and FDV signals", async () => {
  const { fetchImpl } = makeFetch({
    implementationSlot: "0x" + "0".repeat(24) + IMPLEMENTATION,
    owner: addressWord(OWNER),
    pairs: [
      {
        chainId: "base",
        dexId: "aerodrome",
        pairAddress: "0x5555555555555555555555555555555555555555",
        baseToken: { address: TOKEN, name: "Example Token", symbol: "EXM" },
        quoteToken: { address: "0x6666666666666666666666666666666666666666" },
        priceUsd: "0.01",
        liquidity: { usd: 5000 },
        fdv: 10_000_000,
        marketCap: 8_000_000,
        volume: { h24: 25000 },
        txns: { h24: { buys: 40, sells: 50 } },
        pairCreatedAt: NOW - 6 * 60 * 60 * 1000,
      },
    ],
  });

  const result = await inspectBaseToken({
    address: TOKEN,
    fetchImpl,
    nowMs: NOW,
  });

  assert.equal(result.contract.owner, OWNER);
  assert.equal(
    result.contract.eip1967Proxy.implementation,
    "0x" + IMPLEMENTATION,
  );
  assert.equal(result.verdict.riskSignalScore, 70);
  assert.equal(result.verdict.signalLevel, "elevated");
  assert.deepEqual(
    result.verdict.flags.map((flag) => flag.code),
    [
      "owner_detected",
      "upgradeable_proxy_detected",
      "low_observed_liquidity",
      "very_new_market",
      "low_liquidity_to_fdv",
    ],
  );
});

test("optional ERC-20 call reverts reduce coverage without failing the endpoint", async () => {
  const { fetchImpl } = makeFetch({
    optionalErrors: new Set([4, 5, 6, 7, 8]),
    pairs: [
      {
        chainId: "base",
        dexId: "uniswap",
        pairAddress: "0x7777777777777777777777777777777777777777",
        baseToken: { address: TOKEN },
        quoteToken: { address: "0x8888888888888888888888888888888888888888" },
        liquidity: { usd: 100000 },
        fdv: 1_000_000,
        volume: { h24: 1000 },
        txns: { h24: { buys: 2, sells: 1 } },
        pairCreatedAt: NOW - 30 * 24 * 60 * 60 * 1000,
      },
    ],
  });

  const result = await inspectBaseToken({
    address: TOKEN,
    fetchImpl,
    nowMs: NOW,
  });

  assert.equal(result.metadata.name, null);
  assert.equal(result.metadata.decimals, null);
  assert.equal(result.contract.owner, null);
  assert.equal(result.verdict.riskSignalScore, 5);
  assert.equal(result.verdict.flags[0].code, "incomplete_erc20_metadata");
});

test("DEX Screener outage is reported but does not become a false no-market penalty", async () => {
  const { fetchImpl } = makeFetch({ dexStatus: 503 });

  const result = await inspectBaseToken({
    address: TOKEN,
    fetchImpl,
    nowMs: NOW,
  });

  assert.equal(result.market.sourceAvailable, false);
  assert.equal(result.market.pairCount, 0);
  assert.equal(result.verdict.riskSignalScore, 0);
  assert.deepEqual(
    result.verdict.flags.map((flag) => flag.code),
    ["market_data_unavailable"],
  );
});

test("wrong-chain RPC fails closed before requesting DEX market data", async () => {
  const { fetchImpl, calls } = makeFetch({ chainId: "0x1" });

  await assert.rejects(
    inspectBaseToken({ address: TOKEN, fetchImpl, nowMs: NOW }),
    /unexpected_chain_id_1/,
  );
  assert.equal(calls.length, 1);
});

test("invalid token address fails before any network request", async () => {
  let called = false;
  await assert.rejects(
    inspectBaseToken({
      address: "0x1234",
      fetchImpl: async () => {
        called = true;
        throw new Error("unexpected network access");
      },
    }),
    /invalid_token_address/,
  );
  assert.equal(called, false);
});

test("constants pin Base mainnet and the documented token-pairs upstream", () => {
  assert.equal(TOKEN_VERDICT_CONSTANTS.chainId, 8453);
  assert.equal(TOKEN_VERDICT_CONSTANTS.rpcUrl, "https://mainnet.base.org");
  assert.equal(TOKEN_VERDICT_CONSTANTS.dexScreenerUrl, "https://api.dexscreener.com");
  assert.equal(TOKEN_VERDICT_CONSTANTS.selectors.decimals, "0x313ce567");
});
