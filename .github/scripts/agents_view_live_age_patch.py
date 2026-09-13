from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


state = "packages/coding-agent/src/modes/agents-view/agents-view-state.ts"
replace_once(
    state,
    "function getSessionStatusLabel(summary: SessionSummary, heartbeat?: UnifiedSessionHeartbeat): string {",
    "export function getSessionStatusLabel(summary: SessionSummary, heartbeat?: UnifiedSessionHeartbeat): string {",
)

mode = "packages/coding-agent/src/modes/agents-view/agents-view-mode.ts"
replace_once(
    mode,
    "\tgetAgentsViewSessionTitle,\n\tgetAgentsViewSummaryIdentity as getSummaryIdentity,",
    "\tgetAgentsViewSessionTitle,\n\tgetSessionStatusLabel,\n\tgetAgentsViewSummaryIdentity as getSummaryIdentity,",
)
replace_once(
    mode,
    "\t\t\t// Age labels are baked into rows at build time; ticking them needs a rebuild.\n\t\t\tif (hasStaleAge) this.rebuildRows();\n",
    "",
)
replace_once(
    mode,
    "\t\tconst status =\n\t\t\trow.summary.statusLabel !== undefined || row.summary.lastHeardFromAt !== undefined\n\t\t\t\t? row.statusLabel\n\t\t\t\t: undefined;",
    "\t\tconst status =\n\t\t\trow.summary.lastHeardFromAt !== undefined\n\t\t\t\t? getSessionStatusLabel(row.summary, row.heartbeat)\n\t\t\t\t: row.summary.statusLabel !== undefined\n\t\t\t\t\t? row.statusLabel\n\t\t\t\t\t: undefined;",
)

test = Path("packages/coding-agent/test/agents-view-live-age.test.ts")
test.write_text(
    '''import stripAnsi from "strip-ansi";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentsViewMode } from "../src/modes/agents-view/agents-view-mode.js";
import { type AgentsViewRow, buildAgentsViewRows } from "../src/modes/agents-view/agents-view-state.js";
import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";
import { initTheme, stopThemeWatcher } from "../src/modes/interactive/theme/theme.js";

function summary(overrides: Partial<SessionSummary> = {}): SessionSummary {
\treturn {
\t\tid: "stale-active",
\t\tactiveSessionId: "stale-active",
\t\tlifecycle: "live",
\t\tactivity: "idle",
\t\tisSessionActive: false,
\t\tsessionId: "stale-session",
\t\tsessionFile: "/tmp/stale.jsonl",
\t\tcwd: "/tmp",
\t\tisStreaming: false,
\t\tisCompacting: false,
\t\tattachedClients: 0,
\t\tmessageCount: 1,
\t\tsessionActions: { queuedCount: 0, steering: [], followUps: [] },
\t\t...overrides,
\t};
}

function invoke(method: string, self: object, ...args: unknown[]): unknown {
\tconst member = Reflect.get(AgentsViewMode.prototype, method) as ((...a: unknown[]) => unknown) | undefined;
\tif (typeof member !== "function") throw new Error(`AgentsViewMode.${method} no longer exists`);
\treturn member.call(self, ...args);
}

describe("agents view live stale-age rendering", () => {
\tbeforeEach(() => {
\t\tinitTheme("dark");
\t\tvi.useFakeTimers();
\t\tvi.setSystemTime(new Date("2026-01-01T00:00:10Z"));
\t});

\tafterEach(() => {
\t\tvi.useRealTimers();
\t\tstopThemeWatcher();
\t});

\tit("recomputes a stale age at render time without rebuilding the row model", () => {
\t\tconst rows = buildAgentsViewRows([summary({ lastHeardFromAt: "2026-01-01T00:00:00Z" })]);
\t\tconst self = {
\t\t\trows,
\t\t\tselectedIndex: -1,
\t\t\tworkingIconFrame: 0,
\t\t\texpandedSubagentParents: new Set<string>(),
\t\t\tisPendingDeleteRow: () => false,
\t\t\tisPendingKillSubagentRow: () => false,
\t\t\tgetRowIcon(section: AgentsViewRow["section"]): string {
\t\t\t\treturn invoke("getRowIcon", self, section) as string;
\t\t\t},
\t\t\tformatRowIcon(section: AgentsViewRow["section"], icon: string): string {
\t\t\t\treturn invoke("formatRowIcon", self, section, icon) as string;
\t\t\t},
\t\t};
\t\tconst render = (): string => stripAnsi(invoke("renderRow", self, rows[0]!, 160) as string);

\t\texpect(rows[0]?.statusLabel).toBe("last heard 10s ago");
\t\texpect(render()).toContain("last heard 10s ago");
\t\tvi.setSystemTime(new Date("2026-01-01T00:00:11Z"));
\t\texpect(render()).toContain("last heard 11s ago");
\t\texpect(rows[0]?.statusLabel).toBe("last heard 10s ago");
\t});
});
'''
)

Path("packages/coding-agent/.changes/agents-view-live-age.md").write_text(
    "- Reduced agents-view refresh overhead by rendering stale session ages from the current clock without rebuilding the row model.\n"
)
