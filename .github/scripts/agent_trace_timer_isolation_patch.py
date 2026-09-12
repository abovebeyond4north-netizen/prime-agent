from pathlib import Path

path = Path("packages/coding-agent/test/agent-traces.test.ts")
text = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label}, found {count}")
    text = text.replace(old, new, 1)


def replace_in_test(title: str, old: str, new: str, label: str) -> None:
    global text
    start_marker = f'\tit("{title}", async () => {{'
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"missing test: {title}")
    next_test = text.find('\n\tit("', start + len(start_marker))
    end = len(text) if next_test < 0 else next_test
    section = text[start:end]
    count = section.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label} in {title}, found {count}")
    section = section.replace(old, new, 1)
    text = text[:start] + section + text[end:]


replace_once(
    '''async function advanceTimersUntil(condition: () => boolean): Promise<void> {
\tfor (let step = 0; step < 200 && !condition(); step += 1) {
\t\tawait stat(new URL(import.meta.url));
\t\tif (!condition() && vi.getTimerCount() > 0) {
\t\t\tawait vi.advanceTimersToNextTimerAsync();
\t\t}
\t}
\tif (!condition()) {
\t\tthrow new Error("Timed out advancing fake timers to the expected condition");
\t}
}
''',
    '''async function advanceTimersUntil(condition: () => boolean): Promise<void> {
\tfor (let step = 0; step < 200 && !condition(); step += 1) {
\t\tawait stat(new URL(import.meta.url));
\t\tif (!condition() && vi.getTimerCount() > 0) {
\t\t\tawait vi.advanceTimersToNextTimerAsync();
\t\t}
\t}
\tif (!condition()) {
\t\tthrow new Error("Timed out advancing fake timers to the expected condition");
\t}
}

async function waitForAsyncWork(condition: () => boolean): Promise<void> {
\tfor (let step = 0; step < 200 && !condition(); step += 1) {
\t\t// Yield through real filesystem I/O so promises and persistence callbacks can
\t\t// settle without moving Vitest's fake clock or firing unrelated timers.
\t\tawait stat(new URL(import.meta.url));
\t\tawait Promise.resolve();
\t}
\tif (!condition()) {
\t\tthrow new Error("Timed out waiting for asynchronous work to reach the expected condition");
\t}
}
''',
    "async-work wait helper insertion",
)

coalescing = "coalesces new content that persists during an in-flight upload into one follow-up upload"
replace_in_test(
    coalescing,
    '''\t\tvi.useFakeTimers();
\t\tconst cwd = join(tempDir, "project");
''',
    '''\t\tvi.useFakeTimers();
\t\tconst setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
\t\tconst cwd = join(tempDir, "project");
''',
    "coalescing test timer spy",
)
replace_in_test(
    coalescing,
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn,
\t\t});
''',
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn,
\t\t\t// Keep the request timeout beyond the 60s scheduler window so this
\t\t\t// scheduler test never advances through an unrelated request timeout.
\t\t\trequestTimeoutMs: 120_000,
\t\t});
''',
    "coalescing request timeout isolation",
)
replace_in_test(
    coalescing,
    '''\t\t// New content lands while the first upload is still in flight.
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\tawait advanceTimersUntil(() => vi.getTimerCount() > 0);
\t\tawait vi.advanceTimersToNextTimerAsync();
\t\texpect(calls).toHaveLength(1);

\t\treleaseFetch();
''',
    '''\t\t// New content lands while the first upload is still in flight. Wait for
\t\t// persistence to arm the controller's throttle timer without advancing fake
\t\t// time, then advance exactly that 60s scheduler window. The request timeout
\t\t// is intentionally later, so no unrelated timer can satisfy this step.
\t\tconst timerCallStart = setTimeoutSpy.mock.calls.length;
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\tawait waitForAsyncWork(() =>
\t\t\tsetTimeoutSpy.mock.calls
\t\t\t\t.slice(timerCallStart)
\t\t\t\t.some((call) => Number(call[1]) === 60_000),
\t\t);
\t\tawait vi.advanceTimersByTimeAsync(60_000);
\t\texpect(calls).toHaveLength(1);

\t\treleaseFetch();
''',
    "coalescing scheduler synchronization block",
)

throttled = "schedules automatic uploads at most once per minute and only after new entries persist"
replace_in_test(
    throttled,
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn: createFetchRecorder(calls),
\t\t});
''',
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn: createFetchRecorder(calls),
\t\t\trequestTimeoutMs: 120_000,
\t\t});
''',
    "throttle request timeout isolation",
)
replace_in_test(
    throttled,
    '''\t\tawait advanceTimersUntil(() => calls.length === 1);

\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(60_000);
''',
    '''\t\tawait advanceTimersUntil(() => calls.length === 1);

\t\t// A fetch invocation is observable before its success cursor and controller
\t\t// completion settle. Synchronize on the durable cursor before checking the
\t\t// next persist's throttle schedule, without advancing fake time.
\t\tconst sessionFile = sessionManager.getSessionFile() as string;
\t\tconst uploadedBodySize = Buffer.byteLength(readFileSync(sessionFile, "utf8"));
\t\tawait waitForAsyncWork(() => readOutboxEntry(tempDir, sessionFile)?.size === uploadedBodySize);
\t\tawait stat(new URL(import.meta.url));

\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\tawait waitForAsyncWork(() => setTimeoutSpy.mock.calls.some((call) => Number(call[1]) === 60_000));
\t\texpect(setTimeoutSpy.mock.calls.some((call) => Number(call[1]) === 60_000)).toBe(true);
''',
    "throttle durable-completion synchronization block",
)

path.write_text(text)
