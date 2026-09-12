from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


source = "packages/coding-agent/src/core/agent-traces.ts"
replace_once(
    source,
    '''class AgentTraceUploadController {\n\tprivate timeout: NodeJS.Timeout | undefined;\n\tprivate pending = false;\n\tprivate inFlight: Promise<void> | undefined;\n\tprivate lastUploadStartedAt: number | undefined;\n\tprivate notBeforeAt = 0;\n''',
    '''class AgentTraceUploadController {\n\tprivate timeout: NodeJS.Timeout | undefined;\n\tprivate pending = false;\n\tprivate inFlight: Promise<void> | undefined;\n\tprivate lastUploadStartedAt: number | undefined;\n\tprivate notBeforeAt = 0;\n\tprivate unsubscribePersist: (() => void) | undefined;\n''',
)
replace_once(
    source,
    '''\tupdate(options: AgentTraceUploadInstallOptions): void {\n\t\tthis.options = options;\n\t}\n\n\tschedule = (): void => {\n''',
    '''\tupdate(options: AgentTraceUploadInstallOptions): void {\n\t\tthis.options = options;\n\t}\n\n\tattach(): void {\n\t\tif (!this.unsubscribePersist) {\n\t\t\tthis.unsubscribePersist = this.sessionManager.onPersist(this.schedule);\n\t\t}\n\t}\n\n\tasync stop(): Promise<void> {\n\t\tthis.unsubscribePersist?.();\n\t\tthis.unsubscribePersist = undefined;\n\t\tthis.pending = false;\n\t\tif (this.timeout) {\n\t\t\tclearTimeout(this.timeout);\n\t\t\tthis.timeout = undefined;\n\t\t}\n\t\tawait this.inFlight;\n\t}\n\n\tschedule = (): void => {\n''',
)
replace_once(
    source,
    '''\tcontroller = new AgentTraceUploadController(sessionManager, options);\n\ttraceUploadControllers.set(sessionManager, controller);\n\tsessionManager.onPersist(controller.schedule);\n}\n''',
    '''\tcontroller = new AgentTraceUploadController(sessionManager, options);\n\ttraceUploadControllers.set(sessionManager, controller);\n\tcontroller.attach();\n}\n\nexport async function uninstallAgentTraceUpload(sessionManager: SessionManager): Promise<void> {\n\tconst controller = traceUploadControllers.get(sessionManager);\n\tif (!controller) return;\n\ttraceUploadControllers.delete(sessionManager);\n\tawait controller.stop();\n\tconst sessionFile = sessionManager.getSessionFile();\n\tif (sessionFile) {\n\t\tlocallyManagedSessionFiles.delete(sessionFile);\n\t}\n}\n''',
)


test = "packages/coding-agent/test/agent-traces.test.ts"
replace_once(
    test,
    '''\tinstallAgentTraceUpload,\n''',
    '''\tinstallAgentTraceUpload as installAgentTraceUploadCore,\n''',
)
replace_once(
    test,
    '''\tuploadAllAgentTraces,\n} from "../src/core/agent-traces.js";\n''',
    '''\tuninstallAgentTraceUpload,\n\tuploadAgentTraceFile,\n\tuploadAllAgentTraces,\n} from "../src/core/agent-traces.js";\n''',
)
replace_once(
    test,
    '''\tuploadAgentTraceFile,\n\tuninstallAgentTraceUpload,\n\tuploadAgentTraceFile,\n''',
    '''\tuninstallAgentTraceUpload,\n\tuploadAgentTraceFile,\n''',
)
replace_once(
    test,
    '''function createAssistantMessage(text: string): AssistantMessage {\n''',
    '''const installedTraceUploadManagers = new Set<SessionManager>();\n\nfunction installAgentTraceUpload(...args: Parameters<typeof installAgentTraceUploadCore>): void {\n\tinstalledTraceUploadManagers.add(args[0]);\n\tinstallAgentTraceUploadCore(...args);\n}\n\nfunction createAssistantMessage(text: string): AssistantMessage {\n''',
)
replace_once(
    test,
    '''\tafterEach(() => {\n\t\tvi.restoreAllMocks();\n\t\tvi.useRealTimers();\n''',
    '''\tafterEach(async () => {\n\t\tfor (const sessionManager of installedTraceUploadManagers) {\n\t\t\tawait uninstallAgentTraceUpload(sessionManager);\n\t\t}\n\t\tinstalledTraceUploadManagers.clear();\n\t\tvi.restoreAllMocks();\n\t\tvi.useRealTimers();\n''',
)

config = "packages/coding-agent/vitest.config.ts"
replace_once(config, '\n\t\tsetupFiles: ["./test/setup/agent-trace-cleanup.ts"],', '')

change = Path("packages/coding-agent/.changes/trace-upload-deterministic-teardown.md")
change.write_text("- Made agent-trace test teardown deterministic by draining scheduled uploads before removing temporary files.\n")
