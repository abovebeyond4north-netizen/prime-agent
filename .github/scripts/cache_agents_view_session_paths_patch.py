from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


source = "packages/coding-agent/src/modes/agents-view/agents-view-state.ts"
replace_once(source, 'import { basename, resolve } from "node:path";\n', 'import { basename, isAbsolute, resolve } from "node:path";\n')
replace_once(
    source,
    '''function canonicalSessionPath(path: string): string {\n\treturn resolve(canonicalizePath(path));\n}\n''',
    '''const SESSION_PATH_CACHE_LIMIT = 4096;\nconst SESSION_PATH_CACHE_TTL_MS = 60_000;\ninterface CachedSessionPath {\n\tvalue: string;\n\texpiresAt: number;\n}\n\n// UI-only cache: canonicalizing session aliases can hit the filesystem on every\n// row-model rebuild. Cache both successful resolutions and missing-path fallbacks;\n// file or symlink changes become visible after the short TTL.\nconst canonicalSessionPathCache = new Map<string, CachedSessionPath>();\n\nfunction canonicalSessionPath(path: string): string {\n\tconst key = isAbsolute(path) ? path : `${process.cwd()}\\0${path}`;\n\tconst now = Date.now();\n\tconst cached = canonicalSessionPathCache.get(key);\n\tif (cached) {\n\t\tcanonicalSessionPathCache.delete(key);\n\t\tif (cached.expiresAt > now) {\n\t\t\tcanonicalSessionPathCache.set(key, cached);\n\t\t\treturn cached.value;\n\t\t}\n\t}\n\n\tconst value = resolve(canonicalizePath(path));\n\tif (canonicalSessionPathCache.size >= SESSION_PATH_CACHE_LIMIT) {\n\t\tconst oldestKey = canonicalSessionPathCache.keys().next().value;\n\t\tif (oldestKey !== undefined) canonicalSessionPathCache.delete(oldestKey);\n\t}\n\tcanonicalSessionPathCache.set(key, { value, expiresAt: now + SESSION_PATH_CACHE_TTL_MS });\n\treturn value;\n}\n''',
)

test_path = Path("packages/coding-agent/test/agents-view-path-cache.test.ts")
test_path.write_text('''import { mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";\nimport { tmpdir } from "node:os";\nimport { join, resolve } from "node:path";\nimport { afterEach, describe, expect, test, vi } from "vitest";\nimport { getAgentsViewSummaryIdentity } from "../src/modes/agents-view/agents-view-state.js";\nimport type { SessionSummary } from "../src/modes/daemon/daemon-session-list.js";\nimport * as paths from "../src/utils/paths.js";\n\nfunction summary(sessionFile: string): SessionSummary {\n\treturn { id: "cache-test", sessionId: "cache-test", sessionFile } as SessionSummary;\n}\n\nafterEach(() => {\n\tvi.restoreAllMocks();\n});\n\ndescribe("agents view canonical session-path cache", () => {\n\ttest("reuses a successful canonical path within the TTL", () => {\n\t\tconst root = mkdtempSync(join(tmpdir(), "agents-view-path-cache-"));\n\t\ttry {\n\t\t\tconst real = join(root, "session.jsonl");\n\t\t\tconst alias = join(root, "alias.jsonl");\n\t\t\twriteFileSync(real, "");\n\t\t\tsymlinkSync(real, alias);\n\t\t\tconst canonicalize = vi.spyOn(paths, "canonicalizePath");\n\n\t\t\tfor (let lookup = 0; lookup < 3; lookup++) {\n\t\t\t\texpect(getAgentsViewSummaryIdentity(summary(alias))).toBe(`file:${realpathSync(real)}`);\n\t\t\t}\n\t\t\texpect(canonicalize).toHaveBeenCalledExactlyOnceWith(alias);\n\t\t} finally {\n\t\t\trmSync(root, { recursive: true, force: true });\n\t\t}\n\t});\n\n\ttest("caches missing-path fallbacks and refreshes after one minute", () => {\n\t\tconst missing = join(tmpdir(), `agents-view-missing-${process.pid}.jsonl`);\n\t\tconst start = Date.now();\n\t\tconst now = vi.spyOn(Date, "now").mockReturnValue(start);\n\t\tconst canonicalize = vi.spyOn(paths, "canonicalizePath");\n\n\t\texpect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);\n\t\tnow.mockReturnValue(start + 59_999);\n\t\texpect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);\n\t\texpect(canonicalize).toHaveBeenCalledTimes(1);\n\n\t\tnow.mockReturnValue(start + 60_000);\n\t\texpect(getAgentsViewSummaryIdentity(summary(missing))).toBe(`file:${resolve(missing)}`);\n\t\texpect(canonicalize).toHaveBeenCalledTimes(2);\n\t});\n});\n''')

Path("packages/coding-agent/.changes/agents-view-session-path-cache.md").write_text(
    "- Reduced agents-view rebuild overhead by caching canonical session-path identities with a bounded short-lived cache.\n"
)
