import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import { afterAll } from "vitest";

const originalRmSync = fs.rmSync.bind(fs);
const pendingCleanup = new Set<Promise<void>>();

function isTransientRecursiveRemoveError(error: unknown): boolean {
	if (!(error instanceof Error) || !("code" in error)) return false;
	const code = (error as NodeJS.ErrnoException).code;
	return code === "ENOTEMPTY" || code === "EBUSY" || code === "EPERM";
}

/**
 * Agent-trace tests intentionally exercise background upload scheduling. The test can
 * finish its assertions while the successful scheduled upload is still persisting its
 * cursor. A synchronous retry cannot resolve that race because it blocks the same event
 * loop the cursor write needs to finish.
 *
 * Keep production scheduling and every assertion unchanged. If recursive cleanup of an
 * agent-traces-test-* root hits a transient filesystem race, hand that cleanup to the
 * asynchronous fs implementation so the event loop can drain the in-flight upload. The
 * promise is tracked and awaited below, so cleanup failures remain test failures instead
 * of being hidden.
 */
fs.rmSync = ((...args: Parameters<typeof fs.rmSync>): ReturnType<typeof fs.rmSync> => {
	const [path, options] = args;
	const isAgentTraceTempRoot =
		typeof path === "string" &&
		path.includes("agent-traces-test-") &&
		options &&
		typeof options === "object" &&
		options.recursive;

	try {
		return originalRmSync(...args);
	} catch (error) {
		if (!isAgentTraceTempRoot || !isTransientRecursiveRemoveError(error)) throw error;

		const cleanup = fs.promises
			.rm(path, {
				...options,
				force: true,
				recursive: true,
				maxRetries: Math.max(options.maxRetries ?? 0, 20),
				retryDelay: Math.max(options.retryDelay ?? 0, 10),
			})
			.finally(() => pendingCleanup.delete(cleanup));
		pendingCleanup.add(cleanup);
		return;
	}
}) as typeof fs.rmSync;

// Keep named ESM imports such as `import { rmSync } from "node:fs"` in sync
// with the patched default export before test modules are evaluated.
syncBuiltinESMExports();

afterAll(async () => {
	if (pendingCleanup.size === 0) return;
	await Promise.all([...pendingCleanup]);
});
