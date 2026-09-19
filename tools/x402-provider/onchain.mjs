const BASE_CHAIN_ID = 8453;
const DEFAULT_BASE_RPC_URL = "https://mainnet.base.org";
const BASE_USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913";
const EIP1967_IMPLEMENTATION_SLOT =
  "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";

const BALANCE_OF_SELECTOR = "70a08231";
const ALLOWANCE_SELECTOR = "dd62ed3e";

export function isEvmAddress(value) {
  return /^0x[0-9a-fA-F]{40}$/.test(String(value ?? ""));
}

function normalizeAddress(value) {
  const address = String(value ?? "");
  if (!isEvmAddress(address)) throw new TypeError("invalid_evm_address");
  return address.toLowerCase();
}

function addressWord(address) {
  return normalizeAddress(address).slice(2).padStart(64, "0");
}

function parseHexQuantity(value, field) {
  if (typeof value !== "string" || !/^0x[0-9a-fA-F]+$/.test(value)) {
    throw new Error("invalid_rpc_" + field);
  }
  return BigInt(value);
}

function formatUnits(value, decimals) {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const raw = absolute.toString().padStart(decimals + 1, "0");
  const whole = raw.slice(0, -decimals) || "0";
  const fraction = raw.slice(-decimals).replace(/0+$/, "");
  const rendered = fraction ? whole + "." + fraction : whole;
  return negative ? "-" + rendered : rendered;
}

function proxyImplementation(storageValue) {
  if (typeof storageValue !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(storageValue)) {
    throw new Error("invalid_rpc_implementation_slot");
  }
  if (/^0x0{64}$/i.test(storageValue)) return null;
  const address = "0x" + storageValue.slice(-40).toLowerCase();
  return /^0x0{40}$/.test(address) ? null : address;
}

function buildBatch(address, spender) {
  const owner = normalizeAddress(address);
  const requests = [
    { id: 1, jsonrpc: "2.0", method: "eth_chainId", params: [] },
    { id: 2, jsonrpc: "2.0", method: "eth_getBalance", params: [owner, "latest"] },
    { id: 3, jsonrpc: "2.0", method: "eth_getTransactionCount", params: [owner, "latest"] },
    { id: 4, jsonrpc: "2.0", method: "eth_getCode", params: [owner, "latest"] },
    {
      id: 5,
      jsonrpc: "2.0",
      method: "eth_getStorageAt",
      params: [owner, EIP1967_IMPLEMENTATION_SLOT, "latest"],
    },
    {
      id: 6,
      jsonrpc: "2.0",
      method: "eth_call",
      params: [{ to: BASE_USDC, data: "0x" + BALANCE_OF_SELECTOR + addressWord(owner) }, "latest"],
    },
  ];
  if (spender) {
    const normalizedSpender = normalizeAddress(spender);
    requests.push({
      id: 7,
      jsonrpc: "2.0",
      method: "eth_call",
      params: [
        {
          to: BASE_USDC,
          data: "0x" + ALLOWANCE_SELECTOR + addressWord(owner) + addressWord(normalizedSpender),
        },
        "latest",
      ],
    });
  }
  return requests;
}

async function rpcBatch({ rpcUrl, address, spender, fetchImpl, timeoutMs }) {
  const requests = buildBatch(address, spender);
  const response = await fetchImpl(rpcUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "user-agent": "prime-agent-x402-preflight/1.0",
    },
    body: JSON.stringify(requests),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error("base_rpc_http_" + response.status);

  const payload = await response.json();
  if (!Array.isArray(payload)) throw new Error("base_rpc_batch_unsupported");

  const byId = new Map(payload.map((item) => [Number(item?.id), item]));
  const values = new Map();
  for (const request of requests) {
    const result = byId.get(request.id);
    if (!result) throw new Error("base_rpc_missing_result_" + request.id);
    if (result.error) {
      const code = result.error?.code ?? "unknown";
      throw new Error("base_rpc_error_" + code + "_for_" + request.method);
    }
    values.set(request.id, result.result);
  }
  return values;
}

export async function fetchBasePreflight({
  address,
  spender = null,
  rpcUrl = DEFAULT_BASE_RPC_URL,
  fetchImpl = globalThis.fetch,
  timeoutMs = 8_000,
} = {}) {
  const owner = normalizeAddress(address);
  const normalizedSpender = spender ? normalizeAddress(spender) : null;
  if (typeof fetchImpl !== "function") throw new TypeError("fetch_unavailable");

  const values = await rpcBatch({
    rpcUrl,
    address: owner,
    spender: normalizedSpender,
    fetchImpl,
    timeoutMs,
  });

  const chainId = Number(parseHexQuantity(values.get(1), "chain_id"));
  if (chainId !== BASE_CHAIN_ID) throw new Error("unexpected_chain_id_" + chainId);

  const nativeWei = parseHexQuantity(values.get(2), "native_balance");
  const nonce = parseHexQuantity(values.get(3), "nonce");
  const code = String(values.get(4) ?? "");
  if (!/^0x(?:[0-9a-fA-F]{2})*$/.test(code)) throw new Error("invalid_rpc_code");
  const implementation = proxyImplementation(String(values.get(5) ?? ""));
  const usdcAtomic = parseHexQuantity(values.get(6), "usdc_balance");
  const allowanceAtomic = normalizedSpender
    ? parseHexQuantity(values.get(7), "usdc_allowance")
    : null;

  const isContract = code !== "0x";
  const flags = [];
  if (isContract) flags.push("contract_account");
  if (implementation) flags.push("eip1967_proxy");
  if (nativeWei === 0n) flags.push("zero_native_balance");
  if (!isContract && nonce === 0n) flags.push("no_outbound_transactions");
  if (usdcAtomic === 0n) flags.push("zero_usdc_balance");
  if (normalizedSpender && allowanceAtomic === 0n) flags.push("zero_usdc_allowance");

  return {
    observedAt: new Date().toISOString(),
    network: "base-mainnet",
    chainId,
    address: owner,
    account: {
      type: isContract ? "contract" : "eoa",
      nonce: nonce.toString(),
      bytecodeBytes: isContract ? Math.max(0, (code.length - 2) / 2) : 0,
      proxy: {
        eip1967Detected: Boolean(implementation),
        implementation,
      },
    },
    balances: {
      native: {
        symbol: "ETH",
        wei: nativeWei.toString(),
        amount: formatUnits(nativeWei, 18),
      },
      usdc: {
        token: BASE_USDC,
        atomic: usdcAtomic.toString(),
        amount: formatUnits(usdcAtomic, 6),
      },
    },
    allowance: normalizedSpender
      ? {
          token: BASE_USDC,
          spender: normalizedSpender,
          atomic: allowanceAtomic.toString(),
          amount: formatUnits(allowanceAtomic, 6),
        }
      : null,
    riskSummary: {
      flags,
      flagCount: flags.length,
      interpretation:
        "Descriptive preflight signals only; flags are not proof of fraud, solvency, identity, or transaction safety.",
    },
    source: "Base JSON-RPC latest confirmed state",
  };
}

export const BASE_PREFLIGHT_CONSTANTS = Object.freeze({
  chainId: BASE_CHAIN_ID,
  rpcUrl: DEFAULT_BASE_RPC_URL,
  usdc: BASE_USDC,
  eip1967ImplementationSlot: EIP1967_IMPLEMENTATION_SLOT,
});
