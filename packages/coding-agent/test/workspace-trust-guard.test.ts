import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
	assertWorkspaceTrustedForExecutableConfiguration,
	detectProjectExecutableConfiguration,
	isProjectTrustExplicitlyGranted,
} from "../src/core/workspace-trust.js";

const cleanupPaths: string[] = [];

function workspace(name: string): string {
	const path = join(tmpdir(), `prime-workspace-trust-${name}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
	mkdirSync(path, { recursive: true });
	cleanupPaths.push(path);
	return path;
}

afterEach(() => {
	while (cleanupPaths.length > 0) {
		const path = cleanupPaths.pop();
		if (path) rmSync(path, { recursive: true, force: true });
	}
});

describe("workspace trust guard", () => {
	it("allows a workspace without project executable configuration", () => {
		const cwd = workspace("plain");
		expect(detectProjectExecutableConfiguration(cwd)).toEqual([]);
		expect(() => assertWorkspaceTrustedForExecutableConfiguration(cwd, {})).not.toThrow();
	});

	it("blocks project-local extensions by default", () => {
		const cwd = workspace("extension");
		const extensionDir = join(cwd, ".prime", "agent", "extensions");
		mkdirSync(extensionDir, { recursive: true });
		writeFileSync(join(extensionDir, "canary.ts"), "throw new Error('must not execute');\n", "utf-8");

		expect(detectProjectExecutableConfiguration(cwd)).toEqual(
			expect.arrayContaining([expect.objectContaining({ detail: "project extensions" })]),
		);
		expect(() => assertWorkspaceTrustedForExecutableConfiguration(cwd, {})).toThrow(/untrusted workspace/);
	});

	it("allows project executable configuration only after explicit process trust", () => {
		const cwd = workspace("trusted");
		const extensionDir = join(cwd, ".prime", "agent", "extensions");
		mkdirSync(extensionDir, { recursive: true });
		writeFileSync(join(extensionDir, "canary.ts"), "export default () => {};\n", "utf-8");

		expect(isProjectTrustExplicitlyGranted({ PRIME_AGENT_TRUST_PROJECT: "true" })).toBe(true);
		expect(() =>
			assertWorkspaceTrustedForExecutableConfiguration(cwd, { PRIME_AGENT_TRUST_PROJECT: "1" }),
		).not.toThrow();
	});

	it("blocks executable project settings but permits benign settings", () => {
		const cwd = workspace("settings");
		const configDir = join(cwd, ".prime", "agent");
		mkdirSync(configDir, { recursive: true });
		const settingsPath = join(configDir, "settings.json");

		writeFileSync(settingsPath, JSON.stringify({ defaultThinkingLevel: "high" }), "utf-8");
		expect(detectProjectExecutableConfiguration(cwd)).toEqual([]);

		writeFileSync(settingsPath, JSON.stringify({ packages: ["npm:untrusted-package"] }), "utf-8");
		expect(detectProjectExecutableConfiguration(cwd)).toEqual(
			expect.arrayContaining([expect.objectContaining({ detail: "project setting packages" })]),
		);
		expect(() => assertWorkspaceTrustedForExecutableConfiguration(cwd, {})).toThrow(/project setting packages/);
	});

	it("fails closed for malformed project settings", () => {
		const cwd = workspace("malformed");
		const configDir = join(cwd, ".prime", "agent");
		mkdirSync(configDir, { recursive: true });
		writeFileSync(join(configDir, "settings.json"), "{not-json", "utf-8");

		expect(() => assertWorkspaceTrustedForExecutableConfiguration(cwd, {})).toThrow(/could not be parsed safely/);
	});
});
