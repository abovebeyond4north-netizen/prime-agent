from pathlib import Path
from urllib.request import urlopen


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1))


agent_session = "packages/coding-agent/src/core/agent-session.ts"
replace_once(agent_session, "\t\t\t\t\tsummaryCall,\n\t\t\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\t\t));", "\t\t\t\t\tsummaryCall,\n\t\t\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\t\t\tthis.sessionId,\n\t\t\t\t));")
replace_once(agent_session, "\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t);", "\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tproviderRetryPolicy(this.settingsManager),\n\t\t\tthis.sessionId,\n\t\t);")
replace_once(agent_session, "\t\t\theaders,\n\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t);", "\t\t\theaders,\n\t\t\tsignal,\n\t\t\tthis.thinkingLevel,\n\t\t\tthis.sessionId,\n\t\t);")
replace_once(agent_session, "\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsignal: this._branchSummaryAbortController.signal,\n\t\t\t\t\tcustomInstructions,", "\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsignal: this._branchSummaryAbortController.signal,\n\t\t\t\t\tsessionId: this.sessionId,\n\t\t\t\t\tcustomInstructions,")

branch_summary = "packages/coding-agent/src/core/compaction/branch-summarization.ts"
replace_once(branch_summary, "\t/** Request headers for the model */\n\theaders?: Record<string, string>;\n\t/** Abort signal for cancellation */", "\t/** Request headers for the model */\n\theaders?: Record<string, string>;\n\t/** Owning conversation identity for provider routing and caching. */\n\tsessionId?: string;\n\t/** Abort signal for cancellation */")
replace_once(branch_summary, "\t\tmodel,\n\t\tapiKey,\n\t\theaders,\n\t\tsignal,", "\t\tmodel,\n\t\tapiKey,\n\t\theaders,\n\t\tsessionId,\n\t\tsignal,")
replace_once(branch_summary, "\t\t\t\t{ apiKey, headers, signal, maxTokens: 2048 },", "\t\t\t\t{ apiKey, headers, sessionId, signal, maxTokens: 2048 },")

compaction = "packages/coding-agent/src/core/compaction/compaction.ts"
replace_once(
    compaction,
    "export async function generateSummary(\n\tcurrentMessages: AgentMessage[],\n\tmodel: Model<any>,\n\treserveTokens: number,\n\tapiKey: string,\n\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tcustomInstructions?: string,\n\tpreviousSummary?: string,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<SummarySlice> {",
    "export async function generateSummary(\n\tcurrentMessages: AgentMessage[],\n\tmodel: Model<any>,\n\treserveTokens: number,\n\tapiKey: string,\n\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tcustomInstructions?: string,\n\tpreviousSummary?: string,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<SummarySlice> {",
)
replace_once(compaction, "\t\t\t? { maxTokens, signal, apiKey, headers, reasoning: thinkingLevel }\n\t\t\t: { maxTokens, signal, apiKey, headers };", "\t\t\t? { maxTokens, signal, apiKey, headers, sessionId, reasoning: thinkingLevel }\n\t\t\t: { maxTokens, signal, apiKey, headers, sessionId };")
replace_once(compaction, "\tsummaryCall: SummaryCallRunner = (call) => call(headers),\n\tretry?: ProviderRetryPolicy,\n): Promise<CompactionResult> {", "\tsummaryCall: SummaryCallRunner = (call) => call(headers),\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<CompactionResult> {")
replace_once(
    compaction,
    "\t\t\t\t\t\t\tpreviousSummary,\n\t\t\t\t\t\t\tthinkingLevel,\n\t\t\t\t\t\t\tretry,\n\t\t\t\t\t\t),",
    "\t\t\t\t\t\t\tpreviousSummary,\n\t\t\t\t\t\t\tthinkingLevel,\n\t\t\t\t\t\t\tretry,\n\t\t\t\t\t\t\tsessionId,\n\t\t\t\t\t\t),",
)
replace_once(
    compaction,
    "\t\t\t\t\tcallHeaders,\n\t\t\t\t\tsignal,\n\t\t\t\t\tthinkingLevel,\n\t\t\t\t\tretry,\n\t\t\t\t),",
    "\t\t\t\t\tcallHeaders,\n\t\t\t\t\tsignal,\n\t\t\t\t\tthinkingLevel,\n\t\t\t\t\tretry,\n\t\t\t\t\tsessionId,\n\t\t\t\t),",
)
replace_once(
    compaction,
    "\t\t\t\tpreviousSummary,\n\t\t\t\tthinkingLevel,\n\t\t\t\tretry,\n\t\t\t),",
    "\t\t\t\tpreviousSummary,\n\t\t\t\tthinkingLevel,\n\t\t\t\tretry,\n\t\t\t\tsessionId,\n\t\t\t),",
)
replace_once(compaction, "async function generateTurnPrefixSummary(\n\tmessages: AgentMessage[],\n\tmodel: Model<any>,\n\treserveTokens: number,\n\tapiKey: string,\n\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<SummarySlice> {", "async function generateTurnPrefixSummary(\n\tmessages: AgentMessage[],\n\tmodel: Model<any>,\n\treserveTokens: number,\n\tapiKey: string,\n\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<SummarySlice> {")
replace_once(compaction, "\t\t\t\t\t? { maxTokens, signal, apiKey, headers, reasoning: thinkingLevel }\n\t\t\t\t\t: { maxTokens, signal, apiKey, headers },", "\t\t\t\t\t? { maxTokens, signal, apiKey, headers, sessionId, reasoning: thinkingLevel }\n\t\t\t\t\t: { maxTokens, signal, apiKey, headers, sessionId },")

refinement = "packages/coding-agent/src/core/refinement/refinement.ts"
replace_once(refinement, "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n): Promise<RefinementPlan> {", "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tsessionId?: string,\n): Promise<RefinementPlan> {")
replace_once(refinement, "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t},", "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsessionId,\n\t\t\t\t},")
replace_once(refinement, "\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n): Promise<AutoRefineReview> {", "\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tretry?: ProviderRetryPolicy,\n\tsessionId?: string,\n): Promise<AutoRefineReview> {")
# After the planning completion block has sessionId, the review completion block is the only remaining match.
replace_once(refinement, "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t},", "\t\t\t\t\tsignal,\n\t\t\t\t\tapiKey,\n\t\t\t\t\theaders,\n\t\t\t\t\tsessionId,\n\t\t\t\t},")
replace_once(refinement, "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n): Promise<RefinementResult> {\n\tconst plan = await planRefinement(messages, state, history, model, apiKey, options, headers, signal, thinkingLevel);", "\theaders?: Record<string, string>,\n\tsignal?: AbortSignal,\n\tthinkingLevel?: ThinkingLevel,\n\tsessionId?: string,\n): Promise<RefinementResult> {\n\tconst plan = await planRefinement(\n\t\tmessages,\n\t\tstate,\n\t\thistory,\n\t\tmodel,\n\t\tapiKey,\n\t\toptions,\n\t\theaders,\n\t\tsignal,\n\t\tthinkingLevel,\n\t\tsessionId,\n\t);")

test_url = "https://raw.githubusercontent.com/PrimeIntellect-ai/prime-agent/66658d2cf73153340f23133fbc16eafac31423e8/packages/coding-agent/test/suite/regressions/6009-opencode-maintenance-session.test.ts"
test_path = Path("packages/coding-agent/test/suite/regressions/6009-opencode-maintenance-session.test.ts")
with urlopen(test_url, timeout=30) as response:
    test_path.write_bytes(response.read())
Path("packages/coding-agent/.changes/maintenance-session-identity.md").write_text("- Fixed OpenCode compaction, refinement, and branch summaries failing because requests omitted the conversation identity.\n")
