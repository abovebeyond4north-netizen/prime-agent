import { describe, expect, it } from "vitest";
import type { AgentConnectionRlmChildAgentSnapshot } from "../src/modes/agent-connection/types.js";
import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";
import {
	countDirectSubagentStatuses,
	countRosterSubagentStatuses,
} from "../src/modes/interactive/components/subagent-summary-line.js";

function snapshot(
	id: string,
	status: AgentConnectionRlmChildAgentSnapshot["status"],
	overrides: Partial<AgentConnectionRlmChildAgentSnapshot> = {},
): AgentConnectionRlmChildAgentSnapshot {
	return { id, label: id, status, sessionDir: `/tmp/${id}`, ...overrides };
}

function roster(
	id: string,
	overrides: Partial<SessionSummary> = {},
): SessionSummary {
	return {
		id,
		sessionId: id,
		lifecycle: "live",
		runtimeKind: "subagent",
		rlmChildId: id,
		...overrides,
	} as SessionSummary;
}

describe("subagent summary subtree counting", () => {
	it("counts nested snapshots while excluding unrelated branches", () => {
		const children = [
			snapshot("direct", "running"),
			snapshot("nested", "done", { parentId: "direct", activeSessionId: "nested-session" }),
			snapshot("foreign", "running", { parentId: "another-root" }),
		];

		expect(countDirectSubagentStatuses(children, undefined)).toEqual({
			total: 2,
			running: 1,
			idle: 1,
			inactive: 0,
		});
	});

	it("keeps cancelled snapshots as traversal links without counting them", () => {
		const children = [
			snapshot("cancelled-bridge", "cancelled"),
			snapshot("live-descendant", "running", { parentId: "cancelled-bridge" }),
		];

		expect(countDirectSubagentStatuses(children, undefined)).toEqual({
			total: 1,
			running: 1,
			idle: 0,
			inactive: 0,
		});
	});

	it("uses archived roster rows as links to live descendants without counting the archived row", () => {
		const summaries = [
			roster("direct", { parentSessionId: "root-session", rosterStatus: "idle" }),
			roster("archived-bridge", {
				parentSessionId: "root-session",
				lifecycle: "archived",
				rosterStatus: "inactive",
			}),
			roster("nested", { parentSessionId: "archived-bridge", rosterStatus: "running" }),
			roster("foreign", { parentSessionId: "another-root", rosterStatus: "running" }),
		];

		expect(countRosterSubagentStatuses(summaries, { sessionId: "root-session" })).toEqual({
			total: 2,
			running: 1,
			idle: 1,
			inactive: 0,
		});
	});
});
