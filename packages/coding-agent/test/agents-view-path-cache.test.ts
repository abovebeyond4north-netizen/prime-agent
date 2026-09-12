import { mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";
import { getAgentsViewSummaryIdentity } from "../src/modes/agents-view/agents-view-state.js";
import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";
import * as paths from "../src/utils/paths.js";

function summary(sessionFile: string): SessionSummary {
	return { id: "cache-test", sessionId: "cache-test", sessionFile } as SessionSummary;
}

afterEach(() => {
	vi.restoreAllMocks();
});

describe("agents view canonical session-path cache", () => {
	test("reuses a successful canonical path within the TTL", () => {
		const root = mkdtempSync(join(tmpdir(), "agents-view-path-cache-"));
		try {
			const real = join(root, "session.jsonl");
			const alias = join(root, "alias.jsonl");
			writeFileSync(real, "");
			symlinkSync(real, alias);
			const canonicalize = vi.spyOn(paths, "canonicalizePath");

			for (let lookup = 0; lookup < 3; lookup++) {
				expect(getAgentsViewSummaryIdentity(summary(alias))).toBe(`file:${realpathSync(real)}`);
			}
			expect(canonicalize).toHaveBeenCalledExactlyOnceWith(alias);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test("caches missing-path fallbacks and refreshes after one minute", () => {
		const missing = join(tmpdir(), `agents-view-missing-${process.pid}.jsonl`);
		const start = Date.now();
		const now = vi.spyOn(Date, "now").mockReturnValue(start);
		const canonicalize = vi.spyOn(paths, "canonicalizePath");

		expect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);
		now.mockReturnValue(start + 59_999);
		expect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);
		expect(canonicalize).toHaveBeenCalledTimes(1);

		now.mockReturnValue(start + 60_000);
		expect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);
		expect(canonicalize).toHaveBeenCalledTimes(2);
	});
});
