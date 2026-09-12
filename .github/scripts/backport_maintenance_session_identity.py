from pathlib import Path
from urllib.request import urlopen


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


agent_session = "packages/coding-agent/src/core/agent-session.ts"
replace_once(
    agent_session,
    "\t\t\t\t\tsummaryCall,\n\t\t\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\t\t));",
    "\t\t\t\t\tsummaryCall,\n\t\t\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\t\t\tthis.sessionId,\n\t\t\t\t));",
)
replace_once(
    agent_session,
    "\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t);",
    "\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\tthis.sessionId,\n\t\t);",
)
replace_once(
    agent_session,
    "\t\t\theaders,\n\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t);",
    "\t\t\theaders,\n\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tthis.sessionId,\n\t\t);",
)
replace_once(
    agent_session,
    "\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsignal: this._branchSummaryAbortController.signal,\n\t\t\t\t\tcustomInstructions,",
    "\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsignal: this._branchSummaryAbortController.signal,\n\t\t\t\t\tsessionId: this.sessionId,\n\t\t\t\t\tcustomInstructions,",
)

branch_summary = "packages/coding-agent/src/core/compaction/branch-summarization.ts"
replace_once(
    branch_summary,
    "\t/** Request headers for the model */\n\theaders?: Record<string, string>;\n\t/** Abort signal for cancellation */",
    "\t/** Request headers for the model */\n\theaders?: Record<string, string>;\n\t/** Owning conversation identity for provider routing and caching. */\n\tsessionId?: string;\n\t/** Abort signal for cancellation */",
)
replace_once(
    branch_summary,
    "\t\tmodel,\n\t\tapiKey,\n\t\theaders,\n\t\tsignal,",
    "\t\tmodel,\n\t\tapiKey,\n\t\theaders,\n\t\tsessionId,\n\t\tsignal,",
)
replace_once(
    branch_summary,
    "\t\t\t\t{ apiKey, headers, signal, maxTokens: 2048 },",
    "\t\t\t\t{ apiKey, headers, sessionId, signal, maxTokens: 2048 },",
)

compaction = "packages/coding-agent/src/core/compaction/compaction.ts"
replace_once(
    compaction,
    "\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<SummarySlice> {",
    "\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<SummarySlice> {",
)
replace_once(
    compaction,
    "\t\t\t? { maxTokens, signal, apiKey, headers, reasoning: thinkingLevel }\n\t\t\t: { maxTokens, signal, apiKey, headers };",
    "\t\t\t? { maxTokens, signal, apiKey, headers, sessionId, reasoning: thinkingLevel }\n\t\t\t: { maxTokens, signal, apiKey, headers, sessionId };",
)
replace_once(
    compaction,
    "\tsummaryCall: SummaryCallRunner = (call) => call(headers),\n\tretry?: ProviderRetryPolicy,\n): Promise<CompactionResult> {",
    "\tsummaryCall: SummaryCallRunner = (call) => call(headers),\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<CompactionResult> {",
)
# Three maintenance-summary call sites: split history, split turn-prefix, and history-only.
text = Path(compaction).read_text()
needle = "\t\t\t\t\t\t\tretry,\n\t\t\t\t\t\t),"
if text.count(needle) != 1:
    raise SystemExit(f"expected split history summary call once, found {text.count(needle)}")
text = text.replace(needle, "\t\t\t\t\t\t\tretry,\n\t\t\t\t\t\t\tsessionId,\n\t\t\t\t\t\t),", 1)
needle = "\t\t\t\t\tretry,\n\t\t\t\t),"
if text.count(needle) < 2:
    raise SystemExit(f"expected at least two remaining summary calls, found {text.count(needle)}")
text = text.replace(needle, "\t\t\t\t\tretry,\n\t\t\t\t\tsessionId,\n\t\t\t\t),", 1)
text = text.replace(needle, "\t\t\t\t\tretry,\n\t\t\t\t\tsessionId,\n\t\t\t\t),", 1)
Path(compaction).write_text(text)
replace_once(
    compaction,
    "\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<SummarySlice> {\n\tconst maxTokens = Math.floor(0.5 * reserveTokens);",
    "\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<SummarySlice> {\n\tconst maxTokens = Math.floor(0.5 * reserveTokens);",
)
replace_once(
    compaction,
    "\t\t\t\t\t? { maxTokens, signal, apiKey, headers, reasoning: thinkingLevel }\n\t\t\t\t\t: { maxTokens, signal, apiKey, headers },",
    "\t\t\t\t\t? { maxTokens, signal, apiKey, headers, sessionId, reasoning: thinkingLevel }\n\t\t\t\t\t: { maxTokens, signal, apiKey, headers, sessionId },",
)

refinement = "packages/coding-agent/src/core/refinement/refinement.ts"
replace_once(
    refinement,
    "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n): Promise<RefinementPlan> {",
    "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tsessionId?: string,\n): Promise<RefinementPlan> {",
)
replace_once(
    refinement,
    "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t},",
    "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsessionId,\n\t\t\t\t},",
)
replace_once(
    refinement,
    "\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<AutoRefineReview> {",
    "\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<AutoRefineReview> {",
)
# The review call has the same option shape after the planning call was patched.
text = Path(refinement).read_text()
needle = "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t},"
if text.count(needle) != 1:
    raise SystemExit(f"expected review completion option block once, found {text.count(needle)}")
text = text.replace(needle, "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsessionId,\n\t\t\t\t},", 1)
Path(refinement).write_text(text)
replace_once(
    refinement,
    "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n): Promise<RefinementResult> {\n\tconst plan = await planRefinement(messages, state, history, model, apiKey, options, headers, signal, thinkingLevel);",
    "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tsessionId?: string,\n): Promise<RefinementResult> {\n\tconst plan = await planRefinement(\n\t\tmessages,\n\t\tstate,\n\t\thistory,\n\t\tmodel,\n\t\tapiKey,\n\t\toptions,\n\t\theaders,\n\t\tsignal,\n\t\tthinkingLevel,\n\t\tsessionId,\n\t);",
)

# Copy the upstream regression exactly from the fixing commit, pinned by immutable SHA.
test_url = "https://raw.githubusercontent.com/PrimeIntellect-ai/prime-agent/66658d2cf73153340f23133fbc16eafac31423e8/packages/coding-agent/test/suite/regressions/6009-opencode-maintenance-session.test.ts"
test_path = Path("packages/coding-agent/test/suite/regressions/6009-opencode-maintenance-session.test.ts")
with urlopen(test_url, timeout=30) as response:
    test_path.write_bytes(response.read())

Path("packages/coding-agent/.changes/maintenance-session-identity.md").write_text(
    "- Fixed OpenCode compaction, refinement, and branch summaries failing because requests omitted the conversation identity.\n"
)
