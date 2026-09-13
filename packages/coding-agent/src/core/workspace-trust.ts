import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { CONFIG_DIR_NAME } from "../config.js";

const PROJECT_TRUST_ENV = "PRIME_AGENT_TRUST_PROJECT";

const EXECUTABLE_SETTING_KEYS = new Set([
	"extensions",
	"skills",
	"prompts",
	"themes",
	"packages",
	"mcpServers",
	"shellCommandPrefix",
	"shellPath",
	"npmCommand",
	"sessionDir",
]);

export interface WorkspaceTrustFinding {
	kind: "resource" | "settings";
	path: string;
	detail: string;
}

function hasConfiguredValue(value: unknown): boolean {
	if (value === undefined || value === null || value === false) return false;
	if (Array.isArray(value)) return value.length > 0;
	if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
	if (typeof value === "string") return value.trim().length > 0;
	return true;
}

export function isProjectTrustExplicitlyGranted(env: NodeJS.ProcessEnv = process.env): boolean {
	const value = env[PROJECT_TRUST_ENV]?.trim().toLowerCase();
	return value === "1" || value === "true" || value === "yes";
}

export function detectProjectExecutableConfiguration(cwd: string): WorkspaceTrustFinding[] {
	const workspace = resolve(cwd);
	const configDir = join(workspace, CONFIG_DIR_NAME);
	const findings: WorkspaceTrustFinding[] = [];

	for (const relativePath of ["extensions", "skills", "prompts", "themes"]) {
		const path = join(configDir, relativePath);
		if (existsSync(path)) {
			findings.push({
				kind: "resource",
				path,
				detail: `project ${relativePath}`,
			});
		}
	}

	const agentsSkills = join(workspace, ".agents", "skills");
	if (existsSync(agentsSkills)) {
		findings.push({ kind: "resource", path: agentsSkills, detail: "project agent skills" });
	}

	for (const fileName of ["SYSTEM.md", "APPEND_SYSTEM.md"]) {
		for (const path of [join(workspace, fileName), join(configDir, fileName)]) {
			if (existsSync(path)) {
				findings.push({ kind: "resource", path, detail: `project ${fileName}` });
			}
		}
	}

	const settingsPath = join(configDir, "settings.json");
	if (existsSync(settingsPath)) {
		try {
			const parsed: unknown = JSON.parse(readFileSync(settingsPath, "utf-8"));
			if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
				findings.push({
					kind: "settings",
					path: settingsPath,
					detail: "project settings are not a JSON object",
				});
			} else {
				for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
					if (EXECUTABLE_SETTING_KEYS.has(key) && hasConfiguredValue(value)) {
						findings.push({
							kind: "settings",
							path: settingsPath,
							detail: `project setting ${key}`,
						});
					}
				}
			}
		} catch {
			// A malformed project settings file is ambiguous. Fail closed rather than
			// letting another loader interpret it differently later in startup.
			findings.push({
				kind: "settings",
				path: settingsPath,
				detail: "project settings could not be parsed safely",
			});
		}
	}

	return findings;
}

export function assertWorkspaceTrustedForExecutableConfiguration(
	cwd: string,
	env: NodeJS.ProcessEnv = process.env,
): void {
	const findings = detectProjectExecutableConfiguration(cwd);
	if (findings.length === 0 || isProjectTrustExplicitlyGranted(env)) {
		return;
	}

	const details = findings.map((finding) => finding.detail).join(", ");
	throw new Error(
		`Refusing to load project-scoped executable configuration from an untrusted workspace (${details}). ` +
			`Inspect the repository first, then set ${PROJECT_TRUST_ENV}=1 for this process to grant explicit trust.`,
	);
}
