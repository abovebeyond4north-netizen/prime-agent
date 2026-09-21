export const PAYAI_FACILITATOR_URL = "https://facilitator.payai.network";
export const CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402";

export function resolveFacilitatorConfig(env = process.env) {
  const mode = String(env.X402_FACILITATOR_MODE ?? "payai").trim().toLowerCase();

  if (mode === "payai") {
    return {
      mode,
      url: String(env.X402_FACILITATOR_URL ?? PAYAI_FACILITATOR_URL).trim(),
      authenticated: false,
    };
  }

  if (mode === "cdp") {
    const apiKeyId = String(env.CDP_API_KEY_ID ?? "").trim();
    const apiKeySecret = String(env.CDP_API_KEY_SECRET ?? "").trim();
    if (!apiKeyId || !apiKeySecret) {
      throw new Error(
        "X402_FACILITATOR_MODE=cdp requires CDP_API_KEY_ID and CDP_API_KEY_SECRET",
      );
    }
    return {
      mode,
      url: CDP_FACILITATOR_URL,
      authenticated: true,
    };
  }

  throw new Error(
    "Unsupported X402_FACILITATOR_MODE " +
      JSON.stringify(mode) +
      "; expected payai or cdp",
  );
}

export function buildFacilitatorClient({
  config,
  createPayAiClient,
  createCdpClient,
}) {
  if (!config || !config.mode) throw new TypeError("facilitator_config_required");

  if (config.mode === "cdp") {
    if (typeof createCdpClient !== "function") {
      throw new TypeError("createCdpClient_required");
    }
    return createCdpClient();
  }

  if (config.mode === "payai") {
    if (typeof createPayAiClient !== "function") {
      throw new TypeError("createPayAiClient_required");
    }
    return createPayAiClient(config.url);
  }

  throw new Error("unsupported_facilitator_mode_" + config.mode);
}
