import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { getShellEnv } from "../src/utils/shell.js";

const GUARD_VARS: Record<string, string> = {
	GIT_EDITOR: "true",
	GIT_SEQUENCE_EDITOR: "true",
	GIT_TERMINAL_PROMPTS: "0",
	GIT_ASKPASS: "true",
	SSH_ASKPASS_REQUIRE: "never",
	EDITOR: "true",
	VISUAL: "true",
	PAGER: "cat",
	GIT_PAGER: "cat",
	DEBIAN_FRONTEND: "noninteractive",
};

const KEPT = Object.keys(GUARD_VARS);

describe("getShellEnv", () => {
	const saved: Record<string, string | undefined> = {};

	beforeEach(() => {
		for (const key of KEPT) {
			saved[key] = process.env[key];
			delete process.env[key];
		}
	});

	afterEach(() => {
		for (const key of KEPT) {
			const value = saved[key];
			if (value === undefined) delete process.env[key];
			else process.env[key] = value;
		}
	});

	it("sets non-interactive defaults for agent-spawned shells", () => {
		const env = getShellEnv();
		for (const [key, value] of Object.entries(GUARD_VARS)) {
			expect(env[key]).toBe(value);
		}
	});

	it("overrides inherited interactive terminal settings", () => {
		process.env.EDITOR = "vim";
		process.env.PAGER = "less";
		process.env.GIT_SEQUENCE_EDITOR = "vim";
		process.env.GIT_ASKPASS = "/usr/bin/git-credential-manager";
		process.env.SSH_ASKPASS_REQUIRE = "force";
		const env = getShellEnv();
		expect(env.EDITOR).toBe("true");
		expect(env.PAGER).toBe("cat");
		expect(env.GIT_SEQUENCE_EDITOR).toBe("true");
		expect(env.GIT_ASKPASS).toBe("true");
		expect(env.SSH_ASKPASS_REQUIRE).toBe("never");
	});

	it("keeps unrelated inherited variables intact", () => {
		process.env.PRIME_AGENT_SHELL_ENV_TEST = "sentinel";
		try {
			const env = getShellEnv();
			expect(env.PRIME_AGENT_SHELL_ENV_TEST).toBe("sentinel");
		} finally {
			delete process.env.PRIME_AGENT_SHELL_ENV_TEST;
		}
	});
});
