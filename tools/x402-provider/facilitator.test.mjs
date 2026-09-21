import assert from "node:assert/strict";
import test from "node:test";

import {
  CDP_FACILITATOR_URL,
  PAYAI_FACILITATOR_URL,
  buildFacilitatorClient,
  resolveFacilitatorConfig,
} from "./facilitator.mjs";

test("PayAI remains the default facilitator", () => {
  assert.deepEqual(resolveFacilitatorConfig({}), {
    mode: "payai",
    url: PAYAI_FACILITATOR_URL,
    authenticated: false,
  });
});

test("PayAI URL remains configurable", () => {
  const config = resolveFacilitatorConfig({
    X402_FACILITATOR_MODE: "payai",
    X402_FACILITATOR_URL: "https://facilitator.example.test",
  });
  assert.equal(config.url, "https://facilitator.example.test");
});

test("CDP mode requires both API-key environment values", () => {
  assert.throws(
    () =>
      resolveFacilitatorConfig({
        X402_FACILITATOR_MODE: "cdp",
        CDP_API_KEY_ID: "id-only",
      }),
    /requires CDP_API_KEY_ID and CDP_API_KEY_SECRET/,
  );
});

test("CDP mode selects Coinbase hosted facilitator without wallet secret", () => {
  const config = resolveFacilitatorConfig({
    X402_FACILITATOR_MODE: "cdp",
    CDP_API_KEY_ID: "key-id",
    CDP_API_KEY_SECRET: "key-secret",
  });
  assert.deepEqual(config, {
    mode: "cdp",
    url: CDP_FACILITATOR_URL,
    authenticated: true,
  });
});

test("client builder does not invoke CDP factory in default PayAI mode", () => {
  const calls = [];
  const client = buildFacilitatorClient({
    config: resolveFacilitatorConfig({}),
    createPayAiClient: (url) => {
      calls.push(["payai", url]);
      return { provider: "payai" };
    },
    createCdpClient: () => {
      calls.push(["cdp"]);
      return { provider: "cdp" };
    },
  });
  assert.deepEqual(client, { provider: "payai" });
  assert.deepEqual(calls, [["payai", PAYAI_FACILITATOR_URL]]);
});

test("client builder invokes only CDP factory in explicit CDP mode", () => {
  const config = resolveFacilitatorConfig({
    X402_FACILITATOR_MODE: "cdp",
    CDP_API_KEY_ID: "key-id",
    CDP_API_KEY_SECRET: "key-secret",
  });
  const calls = [];
  const client = buildFacilitatorClient({
    config,
    createPayAiClient: () => {
      calls.push(["payai"]);
      return { provider: "payai" };
    },
    createCdpClient: () => {
      calls.push(["cdp"]);
      return { provider: "cdp" };
    },
  });
  assert.deepEqual(client, { provider: "cdp" });
  assert.deepEqual(calls, [["cdp"]]);
});

test("unknown facilitator mode fails closed", () => {
  assert.throws(
    () => resolveFacilitatorConfig({ X402_FACILITATOR_MODE: "mystery" }),
    /expected payai or cdp/,
  );
});
