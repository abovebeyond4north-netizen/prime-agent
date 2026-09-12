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
    "coalescing timer spy",
)
replace_in_test(
    coalescing,
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn,
\t\t});
''',
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn,
\t\t\t// Keep request timeout behavior outside this scheduler-specific test.
\t\t\trequestTimeoutMs: 600_000,
\t\t});
''',
    "coalescing request-timeout isolation",
)
replace_in_test(
    coalescing,
    '''\t\tsessionManager.appendMessage(createUserMessage("hello"));
\t\tsessionManager.appendMessage(createAssistantMessage("hi"));
\t\tawait advanceTimersUntil(() => calls.length === 1);

\t\t// New content lands while the first upload is still in flight.
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\tawait advanceTimersUntil(() => vi.getTimerCount() > 0);
\t\tawait vi.advanceTimersToNextTimerAsync();
\t\texpect(calls).toHaveLength(1);

\t\treleaseFetch();
\t\tawait advanceTimersUntil(() => calls.length === 2);
\t\tconst finalBody = readFileSync(sessionManager.getSessionFile() as string, "utf8");
\t\texpect(calls[1].init.body).toBe(finalBody);
\t\t// Drain the follow-up upload's completion so its chain cannot leak into later fake-timer tests.
\t\tawait advanceTimersUntil(
\t\t\t() =>
\t\t\t\treadOutboxEntry(tempDir, sessionManager.getSessionFile() as string)?.size === Buffer.byteLength(finalBody),
\t\t);
''',
    '''\t\tsessionManager.appendMessage(createUserMessage("hello"));
\t\tsessionManager.appendMessage(createAssistantMessage("hi"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(1_000);
\t\t// Fire only the controller's known debounce. From here until the first
\t\t// request finishes, async progress is observed without advancing fake time.
\t\tawait vi.advanceTimersByTimeAsync(1_000);
\t\tawait waitForAsyncWork(() => calls.length === 1);

\t\t// New content lands while the first upload is still in flight. It should
\t\t// record pending work and arm the one-minute throttle, but must not issue a
\t\t// concurrent request.
\t\tconst persistTimerStart = setTimeoutSpy.mock.calls.length;
\t\tsessionManager.appendMessage(createUserMessage("more"));
\t\tsessionManager.appendMessage(createAssistantMessage("content"));
\t\texpect(
\t\t\tsetTimeoutSpy.mock.calls.slice(persistTimerStart).some((call) => Number(call[1]) === 60_000),
\t\t).toBe(true);
\t\texpect(calls).toHaveLength(1);

\t\t// Completing the first request re-arms exactly one follow-up cycle for the
\t\t// pending content. Wait for that re-arm with the clock frozen.
\t\tconst completionTimerStart = setTimeoutSpy.mock.calls.length;
\t\treleaseFetch();
\t\tawait waitForAsyncWork(() =>
\t\t\tsetTimeoutSpy.mock.calls.slice(completionTimerStart).some((call) => Number(call[1]) === 60_000),
\t\t);
\t\texpect(calls).toHaveLength(1);

\t\tawait vi.advanceTimersByTimeAsync(59_999);
\t\texpect(calls).toHaveLength(1);
\t\tawait vi.advanceTimersByTimeAsync(1);
\t\tawait waitForAsyncWork(() => calls.length === 2);
\t\tconst finalBody = readFileSync(sessionManager.getSessionFile() as string, "utf8");
\t\texpect(calls[1].init.body).toBe(finalBody);
\t\t// Drain the follow-up upload without moving time, then prove no third upload
\t\t// was accidentally scheduled by the coalescing path.
\t\tawait waitForAsyncWork(
\t\t\t() =>
\t\t\t\treadOutboxEntry(tempDir, sessionManager.getSessionFile() as string)?.size === Buffer.byteLength(finalBody),
\t\t);
\t\tawait vi.advanceTimersByTimeAsync(60_000);
\t\texpect(calls).toHaveLength(2);
''',
    "coalescing deterministic scheduler block",
)

throttled = "schedules automatic uploads at most once per minute and only after new entries persist"
replace_in_test(
    throttled,
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn: createFetchRecorder(calls),
\t\t});

\t\tsessionManager.appendMessage(createUserMessage("hello"));
\t\tsessionManager.appendMessage(createAssistantMessage("hi"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(1_000);
\t\tawait advanceTimersUntil(() => calls.length === 1);

\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(60_000);
''',
    '''\t\t\tbaseUrl: "https://api.example.test",
\t\t\tfetchFn: createFetchRecorder(calls),
\t\t\trequestTimeoutMs: 600_000,
\t\t});

\t\tsessionManager.appendMessage(createUserMessage("hello"));
\t\tsessionManager.appendMessage(createAssistantMessage("hi"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(1_000);
\t\tawait vi.advanceTimersByTimeAsync(1_000);
\t\tawait waitForAsyncWork(() => calls.length === 1);

\t\t// Fetch is observable before the upload cursor is durable. Wait for the
\t\t// completed upload with fake time frozen, then verify the next persisted
\t\t// entry is held for the full remaining minute.
\t\tconst sessionFile = sessionManager.getSessionFile() as string;
\t\tconst firstBodySize = Buffer.byteLength(readFileSync(sessionFile, "utf8"));
\t\tawait waitForAsyncWork(() => readOutboxEntry(tempDir, sessionFile)?.size === firstBodySize);
\t\tawait stat(new URL(import.meta.url));

\t\tsetTimeoutSpy.mockClear();
\t\tsessionManager.appendMessage(createUserMessage("next"));
\t\texpect(Number(setTimeoutSpy.mock.calls.at(-1)?.[1])).toBe(60_000);
\t\tawait vi.advanceTimersByTimeAsync(59_999);
\t\texpect(calls).toHaveLength(1);
\t\tawait vi.advanceTimersByTimeAsync(1);
\t\tawait waitForAsyncWork(() => calls.length === 2);
''',
    "throttle deterministic boundary block",
)

path.write_text(text)
