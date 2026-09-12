from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


source = "packages/coding-agent/src/utils/tools-manager.ts"
replace_once(source, 'import extractZip from "extract-zip";\n', '')
replace_once(
    source,
    'const RIPGREP_INSTALL_URL = "https://github.com/BurntSushi/ripgrep#installation";\n',
    'const RIPGREP_INSTALL_URL = "https://github.com/BurntSushi/ripgrep#installation";\n'
    'const POWERSHELL_ZIP_EXTRACT_COMMAND =\n'
    '\t\'$ErrorActionPreference = "Stop"; Expand-Archive -LiteralPath $env:PRIME_AGENT_ARCHIVE -DestinationPath $env:PRIME_AGENT_DEST -Force\';\n',
)
replace_once(
    source,
    '// Download and install a tool\nclass UnsupportedToolPlatformError extends Error {}\n',
    '''function extractZipOnWindows(archivePath: string, extractDir: string): void {
\tconst result = spawnSyncHidden(
\t\t"powershell.exe",
\t\t["-NoProfile", "-NonInteractive", "-Command", POWERSHELL_ZIP_EXTRACT_COMMAND],
\t\t{
\t\t\tstdio: "pipe",
\t\t\ttimeout: DOWNLOAD_TIMEOUT_MS,
\t\t\tenv: {
\t\t\t\t...process.env,
\t\t\t\tPRIME_AGENT_ARCHIVE: archivePath,
\t\t\t\tPRIME_AGENT_DEST: extractDir,
\t\t\t},
\t\t},
\t);
\tif (result.error || result.status !== 0) {
\t\tconst output = result.stderr?.toString().trim() || result.stdout?.toString().trim();
\t\tconst errMsg = result.error?.message ?? output ?? `exit code ${result.status ?? "unknown"}`;
\t\tthrow new Error(`Failed to extract ZIP archive: ${errMsg}`);
\t}
}

// Download and install a tool
class UnsupportedToolPlatformError extends Error {}
''',
)
replace_once(
    source,
    '''\t\t} else if (assetName.endsWith(".zip")) {
\t\t\tawait extractZip(archivePath, { dir: extractDir });
''',
    '''\t\t} else if (assetName.endsWith(".zip") && plat === "win32") {
\t\t\textractZipOnWindows(archivePath, extractDir);
''',
)

package_json = "packages/coding-agent/package.json"
replace_once(package_json, '\n\t\t"extract-zip": "^2.0.1",', '')

test = "packages/coding-agent/test/tools-manager.test.ts"
replace_once(test, '\n\textractZip: async (_source: string, _options: { dir: string }): Promise<void> => {},', '')
replace_once(
    test,
    '''\nvi.mock("extract-zip", () => ({
\tdefault: (source: string, options: { dir: string }) => toolState.extractZip(source, options),
}));
''',
    '',
)
replace_once(test, '\n\t\ttoolState.extractZip = async () => {};', '')
replace_once(
    test,
    '''function writeExecutable(filePath: string, exitCode = 0): void {
\twriteFileSync(filePath, `#!/bin/sh\\nexit ${exitCode}\\n`, "utf8");
\tchmodSync(filePath, 0o755);
}
''',
    '''function writeExecutable(filePath: string, exitCode = 0): void {
\twriteFileSync(filePath, `#!/bin/sh\\nexit ${exitCode}\\n`, "utf8");
\tchmodSync(filePath, 0o755);
}

function writePowerShellExtractor(binaryExitCode = 0): void {
\tconst powershellPath = join(pathDir, "powershell.exe");
\twriteFileSync(
\t\tpowershellPath,
\t\t`#!/bin/sh
set -eu
cat > "$PRIME_AGENT_DEST/rg.exe" <<'PRIME_AGENT_EOF'
#!/bin/sh
exit ${binaryExitCode}
PRIME_AGENT_EOF
chmod +x "$PRIME_AGENT_DEST/rg.exe"
`,
\t\t"utf8",
\t);
\tchmodSync(powershellPath, 0o755);
}
''',
)
replace_once(
    test,
    '''\t\ttoolState.extractZip = async (_source, options) => {
\t\t\twriteExecutable(join(options.dir, "rg.exe"));
\t\t};
''',
    '\t\twritePowerShellExtractor();\n',
)
replace_once(
    test,
    '''\t\ttoolState.extractZip = async (_source, options) => {
\t\t\twriteExecutable(join(options.dir, "rg.exe"), 1);
\t\t};
''',
    '\t\twritePowerShellExtractor(1);\n',
)
marker = '\n\tit("formats actionable platform-specific ripgrep warnings", () => {\n'
addition = '''
\tit("reports PowerShell ZIP extraction failures without leaving a managed binary", async () => {
\t\ttoolState.platform = "win32";
\t\twriteExecutable(join(pathDir, "powershell.exe"), 1);
\t\tvi.stubGlobal(
\t\t\t"fetch",
\t\t\tvi
\t\t\t\t.fn()
\t\t\t\t.mockResolvedValueOnce(new Response(JSON.stringify({ tag_name: "15.1.0" }), { status: 200 }))
\t\t\t\t.mockResolvedValueOnce(new Response(new Uint8Array([1]), { status: 200 })),
\t\t);

\t\tawait expect(ensureToolWithStatus("rg")).resolves.toMatchObject({
\t\t\tstatus: "unavailable",
\t\t\treason: "download_failed",
\t\t\tdetail: expect.stringContaining("Failed to extract ZIP archive"),
\t\t});
\t\texpect(existsSync(join(toolState.toolsDir, "rg.exe"))).toBe(false);
\t});
'''
replace_once(test, marker, addition + marker)
