from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


mode = "packages/coding-agent/src/modes/agents-view/agents-view-mode.ts"
replace_once(
    mode,
    'const HEARTBEAT_POLL_INTERVAL_MS = 15000;\n',
    'const HEARTBEAT_POLL_INTERVAL_MS = 15000;\nconst SAVED_CATALOG_RECONCILE_INTERVAL_MS = 75;\n',
)
replace_once(
    mode,
    '\tprivate savedCatalogRefreshPending = false;\n',
    '\tprivate savedCatalogRefreshPending = false;\n\tprivate savedCatalogReconcileTimer: ReturnType<typeof setTimeout> | undefined;\n',
)
replace_once(
    mode,
    '''\t\tconst generation = ++this.savedCatalogGeneration;\n\t\tthis.persistentState.savedCatalogGeneration = generation;\n\t\tthis.savedCatalogRefreshPending = true;\n''',
    '''\t\tconst generation = ++this.savedCatalogGeneration;\n\t\tthis.persistentState.savedCatalogGeneration = generation;\n\t\tif (this.savedCatalogReconcileTimer) {\n\t\t\tclearTimeout(this.savedCatalogReconcileTimer);\n\t\t\tthis.savedCatalogReconcileTimer = undefined;\n\t\t}\n\t\tthis.savedCatalogRefreshPending = true;\n''',
)
replace_once(
    mode,
    '''\t\t\tconst onSession = (session: AgentConnectionSavedSessionInfo) => {\n\t\t\t\tif (generation !== this.savedCatalogGeneration) return;\n\t\t\t\tprogressiveSessions.set(resolvePath(canonicalizePath(session.path)), session);\n\t\t\t\tthis.savedSessions = [...progressiveSessions.values()];\n\t\t\t\tthis.persistentState.savedSessions = this.savedSessions;\n\t\t\t\tthis.reconcileCatalogs();\n\t\t\t};\n''',
    '''\t\t\tconst onSession = (session: AgentConnectionSavedSessionInfo) => {\n\t\t\t\tif (generation !== this.savedCatalogGeneration) return;\n\t\t\t\tprogressiveSessions.set(resolvePath(canonicalizePath(session.path)), session);\n\t\t\t\t// Keep a bounded batch window so a continuous stream still appears progressively.\n\t\t\t\tif (this.savedCatalogReconcileTimer) return;\n\t\t\t\tthis.savedCatalogReconcileTimer = setTimeout(() => {\n\t\t\t\t\tif (generation !== this.savedCatalogGeneration) return;\n\t\t\t\t\tthis.savedCatalogReconcileTimer = undefined;\n\t\t\t\t\tthis.savedSessions = [...progressiveSessions.values()];\n\t\t\t\t\tthis.persistentState.savedSessions = this.savedSessions;\n\t\t\t\t\tthis.reconcileCatalogs();\n\t\t\t\t}, SAVED_CATALOG_RECONCILE_INTERVAL_MS);\n\t\t\t\tthis.savedCatalogReconcileTimer.unref?.();\n\t\t\t};\n''',
)
replace_once(
    mode,
    '''\t\t} finally {\n\t\t\tif (generation === this.savedCatalogGeneration) {\n\t\t\t\tthis.savedCatalogRefreshPending = false;\n\t\t\t\tthis.resolveMissingSelectionAnchor();\n\t\t\t}\n\t\t}\n\t}\n\n\tprivate async refreshHeartbeats''',
    '''\t\t} finally {\n\t\t\tif (generation === this.savedCatalogGeneration) {\n\t\t\t\tif (this.savedCatalogReconcileTimer) {\n\t\t\t\t\tclearTimeout(this.savedCatalogReconcileTimer);\n\t\t\t\t\tthis.savedCatalogReconcileTimer = undefined;\n\t\t\t\t}\n\t\t\t\tthis.savedCatalogRefreshPending = false;\n\t\t\t\tthis.resolveMissingSelectionAnchor();\n\t\t\t}\n\t\t}\n\t}\n\n\tprivate async refreshHeartbeats''',
)
replace_once(
    mode,
    '''\t\tthis.stopped = true;\n\t\tthis.savedCatalogGeneration += 1;\n\t\tthis.heartbeatCatalogGeneration += 1;\n\t\tif (this.heartbeatPollTimer) {\n''',
    '''\t\tthis.stopped = true;\n\t\tthis.savedCatalogGeneration += 1;\n\t\tthis.heartbeatCatalogGeneration += 1;\n\t\tif (this.savedCatalogReconcileTimer) {\n\t\t\tclearTimeout(this.savedCatalogReconcileTimer);\n\t\t\tthis.savedCatalogReconcileTimer = undefined;\n\t\t}\n\t\tif (this.heartbeatPollTimer) {\n''',
)

test = "packages/coding-agent/test/agents-view-mode.test.ts"
replace_once(
    test,
    'import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";\n',
    'import type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";\nimport * as savedSessionCatalog from "../src/modes/daemon/saved-session-catalog.js";\n',
)
replace_once(
    test,
    '''function invoke(method: string, self: object, ...args: unknown[]): unknown {\n\tconst member = Reflect.get(AgentsViewMode.prototype, method) as ((...a: unknown[]) => unknown) | undefined;\n\tif (typeof member !== "function") throw new Error(`AgentsViewMode.${method} no longer exists`);\n\treturn member.call(self, ...args);\n}\n''',
    '''function invoke(method: string, self: object, ...args: unknown[]): unknown {\n\tconst member = Reflect.get(AgentsViewMode.prototype, method) as ((...a: unknown[]) => unknown) | undefined;\n\tif (typeof member !== "function") throw new Error(`AgentsViewMode.${method} no longer exists`);\n\treturn member.call(self, ...args);\n}\n\nfunction savedSession(id: string): AgentConnectionSavedSessionInfo {\n\treturn {\n\t\tid,\n\t\tpath: `/tmp/${id}.jsonl`,\n\t\tcwd: "/tmp",\n\t\tcreated: new Date(0),\n\t\tmodified: new Date(0),\n\t\tmessageCount: 1,\n\t\tfirstMessage: id,\n\t\tallMessagesText: id,\n\t};\n}\n\nfunction deferredSavedCatalog() {\n\tlet resolve!: (sessions: AgentConnectionSavedSessionInfo[]) => void;\n\tlet onSession: ((session: AgentConnectionSavedSessionInfo) => void) | undefined;\n\tconst promise = new Promise<AgentConnectionSavedSessionInfo[]>((res) => {\n\t\tresolve = res;\n\t});\n\tvi.spyOn(savedSessionCatalog, "listDaemonSavedSessions").mockImplementationOnce(\n\t\tasync (_client, _context, _scope, callbacks) => {\n\t\t\tonSession = callbacks?.onSession;\n\t\t\treturn promise;\n\t\t},\n\t);\n\treturn {\n\t\tresolve,\n\t\temit(session: AgentConnectionSavedSessionInfo): void {\n\t\t\tif (!onSession) throw new Error("Saved catalog refresh has not started");\n\t\t\tonSession(session);\n\t\t},\n\t};\n}\n''',
)
marker = '\nfunction createUiServices(): InteractiveModeUiServices {\n'
addition = '''\ndescribe("AgentsViewMode saved catalog batching", () => {\n\tbeforeEach(() => vi.useFakeTimers());\n\tafterEach(() => vi.useRealTimers());\n\n\tit("coalesces streamed saved sessions into bounded progressive reconciles", async () => {\n\t\tconst previous = [savedSession("previous")];\n\t\tconst persistentState: AgentsViewPersistentState = {\n\t\t\tsavedSessions: previous,\n\t\t\tlastSuccessfulSavedSessions: previous,\n\t\t\tsavedCatalogLoaded: true,\n\t\t};\n\t\tconst view = new AgentsViewMode({ config: {}, uiServices: createUiServices() }, persistentState);\n\t\tReflect.set(view, "client", {});\n\t\tconst reconcile = vi.fn(() => invoke("reconcileCatalogs", view));\n\t\tReflect.set(view, "reconcileCatalogs", reconcile);\n\t\tconst catalog = deferredSavedCatalog();\n\t\tconst refresh = invoke("refreshSavedSessions", view) as Promise<boolean>;\n\t\tconst first = savedSession("first");\n\t\tconst second = savedSession("second");\n\t\tconst third = savedSession("third");\n\t\tcatalog.emit(first);\n\t\tawait vi.advanceTimersByTimeAsync(25);\n\t\tcatalog.emit(second);\n\t\tawait vi.advanceTimersByTimeAsync(49);\n\t\tcatalog.emit(third);\n\n\t\texpect(Reflect.get(view, "savedSessions")).toBe(previous);\n\t\texpect(reconcile).not.toHaveBeenCalled();\n\t\texpect(vi.getTimerCount()).toBe(1);\n\n\t\tawait vi.advanceTimersByTimeAsync(1);\n\t\texpect(reconcile).toHaveBeenCalledOnce();\n\t\texpect(Reflect.get(view, "savedSessions")).toEqual([previous[0], first, second, third]);\n\t\texpect(persistentState.savedSessions).toBe(Reflect.get(view, "savedSessions"));\n\n\t\tconst final = [first, second, third];\n\t\tcatalog.resolve(final);\n\t\tawait expect(refresh).resolves.toBe(true);\n\t\texpect(Reflect.get(view, "savedSessions")).toBe(final);\n\t\texpect(Reflect.get(view, "savedCatalogReconcileTimer")).toBeUndefined();\n\t\texpect(vi.getTimerCount()).toBe(0);\n\t\tstopThemeWatcher();\n\t});\n\n\tit("publishes a completed scan immediately and cancels a pending batch", async () => {\n\t\tconst view = new AgentsViewMode({ config: {}, uiServices: createUiServices() }, {});\n\t\tReflect.set(view, "client", {});\n\t\tconst reconcile = vi.fn(() => invoke("reconcileCatalogs", view));\n\t\tReflect.set(view, "reconcileCatalogs", reconcile);\n\t\tconst catalog = deferredSavedCatalog();\n\t\tconst refresh = invoke("refreshSavedSessions", view) as Promise<boolean>;\n\t\tcatalog.emit(savedSession("partial"));\n\t\texpect(vi.getTimerCount()).toBe(1);\n\n\t\tconst final = [savedSession("canonical")];\n\t\tcatalog.resolve(final);\n\t\tawait expect(refresh).resolves.toBe(true);\n\t\texpect(Reflect.get(view, "savedSessions")).toBe(final);\n\t\texpect(reconcile).toHaveBeenCalledOnce();\n\t\texpect(Reflect.get(view, "savedCatalogReconcileTimer")).toBeUndefined();\n\t\texpect(vi.getTimerCount()).toBe(0);\n\t\tawait vi.advanceTimersByTimeAsync(100);\n\t\texpect(reconcile).toHaveBeenCalledOnce();\n\t\tstopThemeWatcher();\n\t});\n});\n'''
replace_once(test, marker, addition + marker)

changes = "packages/coding-agent/.changes/agents-view-saved-catalog-batching.md"
Path(changes).write_text(
    "- Improved agents-view saved-session loading by batching streamed catalog reconciliation, avoiding repeated full rebuilds while preserving progressive updates.\n"
)
