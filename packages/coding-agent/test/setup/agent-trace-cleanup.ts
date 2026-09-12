import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";

const originalRmSync = fs.rmSync.bind(fs);

/**
 * Agent-trace tests intentionally exercise background upload scheduling. A completed
 * assertion can therefore overlap the final cursor write by a few filesystem ticks.
 * Keep the production scheduler untouched, but make cleanup of this suite's uniquely
 * named temporary roots resilient to transient ENOTEMPTY/EBUSY/EPERM races using
 * Node's built-in bounded retry/backoff support.
 */
fs.rmSync = ((...args: Parameters<typeof fs.rmSync>): ReturnType<typeof fs.rmSync> => {
	const [path, options] = args;
	if (
		typeof path === "string" &&
		path.includes("agent-traces-test-") &&
		options &&
		typeof options === "object" &&
		options.recursive
	) {
		return originalRmSync(path, {
			...options,
			maxRetries: Math.max(options.maxRetries ?? 0, 20),
			retryDelay: Math.max(options.retryDelay ?? 0, 10),
		});
	}
	return originalRmSync(...args);
}) as typeof fs.rmSync;

// Keep named ESM imports such as `import { rmSync } from "node:fs"` in sync
// with the patched default export before test modules are evaluated.
syncBuiltinESMExports();
