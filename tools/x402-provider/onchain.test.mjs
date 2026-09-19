import assert from "node:assert/strict";
import test from "node:test";

import { BASE_PREFLIGHT_CONSTANTS, fetchBasePreflight, isEvmAddress } from "./onchain.mjs";

const OWNER = "0x1111111111111111111111111111111111111111";
const SPENDER = "0x2222222222222222222222222222222222222222";
const IMPLEMENTATION = "3333333333333333333333333333333333333333";

function quantity(value) {
  return "0x" + BigInt(value).toString(16);
}

test("isEvmAddress accepts only 20-byte hex addresses", () => {
  assert.equal(isEvmAddress(OWNER), true);
  assert.equal(isEvmAddress("0x1234"), false);
  assert.equal(isEvmAddress("not-an-address"), false);
});

test("fetchBasePreflight batches deterministic Base reads and normalizes values", async () => {
  let observedRequests;
  const fetchImpl = async (_url, init) => {
    observedRequests = JSON.parse(init.body);
    return {
      ok: true,
      json: async () =>
        observedRequests.map((request) => {
          const results = {
            eth_chainId: "0x2105",
            eth_getBalance: quantity(1_500_000_000_000_000_000n),
            eth_getTransactionCount: quantity(2),
            eth_getCode: "0x6001600055",
            eth_getStorageAt: "0x" + "0".repeat(24) + IMPLEMENTATION,
            eth_call:
              request.id === 6 ? quantity(1_234_567) : quantity(2_000_000),
          };
          return { id: request.id, jsonrpc: "2.0", result: results[request.method] };
        }),
    };
  };

  const result = await fetchBasePreflight({
    address: OWNER,
    spender: SPENDER,
    rpcUrl: "https://rpc.invalid.test",
    fetchImpl,
  });

  assert.equal(observedRequests.length, 7);
  assert.equal(observedRequests[0].method, "eth_chainId");
  assert.equal(observedRequests[5].method, "eth_call");
  assert.equal(
    observedRequests[5].params[0].data,
    "0x70a08231" + OWNER.slice(2).padStart(64, "0"),
  );
  assert.equal(
    observedRequests[6].params[0].data,
    "0xdd62ed3e" +
      OWNER.slice(2).padStart(64, "0") +
      SPENDER.slice(2).padStart(64, "0"),
  );

  assert.equal(result.chainId, 8453);
  assert.equal(result.address, OWNER);
  assert.equal(result.account.type, "contract");
  assert.equal(result.account.nonce, "2");
  assert.equal(result.account.bytecodeBytes, 5);
  assert.equal(
    result.account.proxy.implementation,
    "0x" + IMPLEMENTATION,
  );
  assert.equal(result.balances.native.amount, "1.5");
  assert.equal(result.balances.usdc.amount, "1.234567");
  assert.equal(result.allowance.amount, "2");
  assert.deepEqual(result.riskSummary.flags, ["contract_account", "eip1967_proxy"]);
});

test("fetchBasePreflight fails closed when RPC is not Base mainnet", async () => {
  const fetchImpl = async (_url, init) => {
    const requests = JSON.parse(init.body);
    return {
      ok: true,
      json: async () =>
        requests.map((request) => ({
          id: request.id,
          jsonrpc: "2.0",
          result:
            request.method === "eth_chainId"
              ? "0x1"
              : request.method === "eth_getCode"
                ? "0x"
                : request.method === "eth_getStorageAt"
                  ? "0x" + "0".repeat(64)
                  : "0x0",
        })),
    };
  };

  await assert.rejects(
    fetchBasePreflight({ address: OWNER, rpcUrl: "https://rpc.invalid.test", fetchImpl }),
    /unexpected_chain_id_1/,
  );
});

test("fetchBasePreflight rejects invalid addresses before network access", async () => {
  let called = false;
  await assert.rejects(
    fetchBasePreflight({
      address: "0x1234",
      fetchImpl: async () => {
        called = true;
        throw new Error("should not execute");
      },
    }),
    /invalid_evm_address/,
  );
  assert.equal(called, false);
});

test("Base constants pin official Base mainnet and native USDC", () => {
  assert.equal(BASE_PREFLIGHT_CONSTANTS.chainId, 8453);
  assert.equal(BASE_PREFLIGHT_CONSTANTS.rpcUrl, "https://mainnet.base.org");
  assert.equal(
    BASE_PREFLIGHT_CONSTANTS.usdc,
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
  );
});
