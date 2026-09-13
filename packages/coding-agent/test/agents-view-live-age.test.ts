import stripAnsi from "strip-ansi";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentsViewMode } from "../src/modes/agents-view/agents-view-mode.js";
import { type AgentsViewRow, buildAgentsViewRows } from "../src/modes/agents-view/agents-view-state.js";
import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";
import { initTheme, stopThemeWatcher } from "../src/modes/interactive/theme/theme.js";

function summary(overrides: Partial<SessionSummary> = {}): SessionSummary {
	return {
		id: "stale-active",
		activeSessionId: "stale-active",
		lifecycle: "live",
		activity: "idle",
		isSessionActive: false,
		sessionId: "stale-session",
		sessionFile: "/tmp/stale.jsonl",
		cwd: "/tmp",
		isStreaming: false,
		isCompacting: false,
		attachedClients: 0,
		messageCount: 1,
		sessionActions: { queuedCount: 0, steering: [], followUps: [] },
		...overrides,
	};
}

function invoke(method: string, self: object, ...args: unknown[]): unknown {
	const member = Reflect.get(AgentsViewMode.prototype, method) as ((...a: unknown[]) => unknown) | undefined;
	if (typeof member !== "function") throw new Error(`AgentsViewMode.${method} no longer exists`);
	return member.call(self, ...args);
}

describe("agents view live stale-age rendering", () => {
	beforeEach(() => {
		initTheme("dark");
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-01-01T00:00:10Z"));
	});

	afterEach(() => {
		vi.useRealTimers();
		stopThemeWatcher();
	});

	it("recomputes a stale age at render time without rebuilding the row model", () => {
		const rows = buildAgentsViewRows([summary({ lastHeardFromAt: "2026-01-01T00:00:00Z" })]);
		const self = {
			rows,
			selectedIndex: -1,
			workingIconFrame: 0,
			expandedSubagentParents: new Set<string>(),
			isPendingDeleteRow: () => false,
			isPendingKillSubagentRow: () => false,
			getRowIcon(section: AgentsViewRow["section"]): string {
				return invoke("getRowIcon", self, section) as string;
			},
			formatRowIcon(section: AgentsViewRow["section"], icon: string): string {
				return invoke("formatRowIcon", self, section, icon) as string;
			},
		};
		const render = (): string => stripAnsi(invoke("renderRow", self, rows[0]!, 160) as string);

		expect(rows[0]?.statusLabel).toBe("last heard 10s ago");
		expect(render()).toContain("last heard 10s ago");
		vi.setSystemTime(new Date("2026-01-01T00:00:11Z"));
		expect(render()).toContain("last heard 11s ago");
		expect(rows[0]?.statusLabel).toBe("last heard 10s ago");
	});
});
