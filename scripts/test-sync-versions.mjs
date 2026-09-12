#!/usr/bin/env node

import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const scriptPath = resolve(fileURLToPath(new URL('./sync-versions.js', import.meta.url)));
const fixtureRoot = mkdtempSync(join(tmpdir(), 'prime-agent-sync-versions-'));

try {
	const validDir = join(fixtureRoot, 'packages', 'valid');
	const brokenDir = join(fixtureRoot, 'packages', 'broken');
	mkdirSync(validDir, { recursive: true });
	mkdirSync(brokenDir, { recursive: true });

	const validManifestPath = join(validDir, 'package.json');
	const validManifest = '{\n\t"name": "@fixture/valid",\n\t"version": "1.0.0"\n}\n';
	writeFileSync(validManifestPath, validManifest);
	writeFileSync(join(brokenDir, 'package.json'), '{ invalid json\n');

	const result = spawnSync(process.execPath, [scriptPath], {
		cwd: fixtureRoot,
		encoding: 'utf8',
	});

	assert.notEqual(result.status, 0, 'sync should fail when any workspace manifest is unreadable');
	assert.match(result.stderr, /Failed to read .*package\.json:/);
	assert.match(result.stderr, /Refusing to sync versions/);
	assert.equal(
		readFile(validManifestPath),
		validManifest,
		'sync must not mutate readable manifests after a workspace read failure',
	);

	console.log('sync-versions fail-closed regression test passed');
} finally {
	rmSync(fixtureRoot, { recursive: true, force: true });
}

function readFile(path) {
	return requireReadFile(path);
}

function requireReadFile(path) {
	return Buffer.from(awaitRead(path)).toString('utf8');
}

function awaitRead(path) {
	return new Uint8Array(requireFsRead(path));
}

function requireFsRead(path) {
	return (await import('node:fs')).readFileSync(path);
}
