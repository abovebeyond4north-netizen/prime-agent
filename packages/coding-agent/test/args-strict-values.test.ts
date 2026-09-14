import { describe, expect, test } from "vitest";
import { parseArgs } from "../src/cli/args.js";

describe("strict CLI value parsing", () => {
	test("missing value flags fail instead of becoming extension flags", () => {
		const result = parseArgs(["--model", "--provider", "anthropic"]);
		expect(result.diagnostics).toContainEqual({ type: "error", message: "--model requires a value" });
		expect(result.provider).toBe("anthropic");
		expect(result.unknownFlags.has("model")).toBe(false);
	});

	test("invalid mode fails with valid choices", () => {
		const result = parseArgs(["--mode", "interactive"]);
		expect(result.diagnostics.some((diagnostic) => diagnostic.type === "error" && diagnostic.message.includes("Invalid mode") && diagnostic.message.includes("text") && diagnostic.message.includes("daemon"))).toBe(true);
	});

	test("value flags do not consume the end-of-options delimiter", () => {
		const result = parseArgs(["--system-prompt", "--", "--model", "foo"]);
		expect(result.diagnostics).toContainEqual({ type: "error", message: "--system-prompt requires a value" });
		expect(result.messages).toEqual(["--model", "foo"]);
	});

	test("well-formed values remain unchanged", () => {
		const result = parseArgs(["--model", "claude", "--mode", "json", "--system-prompt", "---\nrole: test"]);
		expect(result.model).toBe("claude");
		expect(result.mode).toBe("json");
		expect(result.systemPrompt).toBe("---\nrole: test");
		expect(result.diagnostics).toEqual([]);
	});
});
