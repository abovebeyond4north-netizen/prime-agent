import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PUBLIC_BASE_URL,
  buildDiscoveryBundle,
  validateDiscoveryBundle,
} from "./discovery.mjs";

test("discovery bundle validates against official Bazaar extension validator", () => {
  const bundle = buildDiscoveryBundle(DEFAULT_PUBLIC_BASE_URL);
  const result = validateDiscoveryBundle(bundle);
  assert.deepEqual(result, { valid: true, errors: [] });
});

test("resource metadata is absolute, searchable, and within Bazaar limits", () => {
  const bundle = buildDiscoveryBundle("https://seller.example.com/");

  for (const resource of [bundle.marketResource, bundle.tokenVerdictResource]) {
    const url = new URL(resource.url);
    assert.equal(url.protocol, "https:");
    assert.ok(resource.serviceName.length <= 32);
    assert.match(resource.serviceName, /^[\x20-\x7E]+$/);
    assert.ok(resource.tags.length <= 5);
    assert.ok(resource.tags.length >= 3);
    for (const tag of resource.tags) {
      assert.ok(tag.length <= 32);
      assert.match(tag, /^[\x20-\x7E]+$/);
    }
  }

  assert.equal(
    bundle.tokenVerdictResource.url,
    "https://seller.example.com/v1/token/verdict",
  );
  assert.equal(bundle.tokenVerdictResource.serviceName, "Prime Agent Token Verdict");
  assert.ok(bundle.tokenVerdictResource.tags.includes("token-risk"));
  assert.ok(bundle.tokenVerdictResource.tags.includes("base"));
});

test("token verdict declaration includes machine-readable address input", () => {
  const bundle = buildDiscoveryBundle();
  const info = bundle.tokenVerdictDiscovery.bazaar.info;
  assert.equal(info.input.queryParams.address, "0x1111111111111111111111111111111111111111");
  assert.equal(info.input.method, "GET");
  assert.equal(info.input.type, "http");
});

test("non-http public base URLs are rejected", () => {
  assert.throws(
    () => buildDiscoveryBundle("file:///tmp/provider"),
    /public_base_url_must_be_http/,
  );
});
