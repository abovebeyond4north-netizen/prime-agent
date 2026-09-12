from pathlib import Path

path = Path("packages/coding-agent/test/agent-traces.test.ts")
text = path.read_text()

old = '''\tit("coalesces new content that persists during an in-flight upload into one follow-up upload", async () => {
\t\tvi.useFakeTimers();
\t\tconst cwd = join(tempDir, "project");
'''
new = '''\tit("coalesces new content that persists during an in-flight upload into one follow-up upload", async () => {
\t\tvi.useFakeTimers();
\t\tconst setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
\t\tconst cwd = join(tempDir, "project");
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one coalescing test header, found {text.count(old)}")
text = text.replace(old, new, 1)

old = '''\t\t// New content lands while the first upload is still in flight.
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\tawait advanceTimersUntil(() => vi.getTimerCount() > 0);
\t\tawait vi.advanceTimersToNextTimerAsync();
\t\texpect(calls).toHaveLength(1);

\t\treleaseFetch();
'''
new = '''\t\t// New content lands while the first upload is still in flight. Identify the
\t\t// controller's throttle timer by its delay instead of advancing whichever
\t\t// global timer happens to be next (the in-flight request owns its own timeout).
\t\tconst timerCallStart = setTimeoutSpy.mock.calls.length;
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\tawait advanceTimersUntil(() =>
\t\t\tsetTimeoutSpy.mock.calls
\t\t\t\t.slice(timerCallStart)
\t\t\t\t.some((call) => Number(call[1]) === 60_000),
\t\t);
\t\texpect(calls).toHaveLength(1);

\t\treleaseFetch();
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one coalescing timer block, found {text.count(old)}")
text = text.replace(old, new, 1)

old = '''\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(60_000);
'''
new = '''\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\texpect(setTimeoutSpy.mock.calls.some((call) => Number(call[1]) === 60_000)).toBe(true);
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one throttle assertion block, found {text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text)
