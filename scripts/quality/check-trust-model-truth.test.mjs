#!/usr/bin/env node

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');
const gateScript = resolve(moduleDir, 'check-trust-model-truth.mjs');
const fixtureRoot = resolve(moduleDir, '__fixtures__/trust-model-truth');

function runGate(root) {
  try {
    const stdout = execFileSync(
      process.execPath,
      [gateScript, '--release', `--repo-root=${root}`],
      {
        cwd: repoRoot,
        encoding: 'utf8',
        stdio: 'pipe',
        timeout: 30_000,
      },
    );
    return { exitCode: 0, stdout, stderr: '' };
  } catch (error) {
    return {
      exitCode: error.status ?? 1,
      stdout: error.stdout ?? '',
      stderr: error.stderr ?? error.message,
    };
  }
}

describe('check-trust-model-truth', () => {
  it('passes against the checked-in repository', () => {
    const result = runGate(repoRoot);
    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OK: no active unsupported trust-model claims detected/);
  });

  it('fails when an active unsupported trust claim is present', () => {
    const result = runGate(resolve(fixtureRoot, 'active-unsupported'));
    const output = result.stdout + result.stderr;

    assert.strictEqual(result.exitCode, 1, output);
    assert.match(output, /active unsupported trust-model claim/);
    assert.match(output, /docs\/extensions\/trust\.txt:3 \[sandbox-or-isolation\]/);
    assert.match(output, /permission-checks/);
  });

  it('passes explicit negation, deferred, and non-enforced trust statements', () => {
    const result = runGate(resolve(fixtureRoot, 'allowed-statements'));

    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OK: no active unsupported trust-model claims detected/);
  });

  it('is wired into package quality checks as a separate script', () => {
    const packageJson = JSON.parse(readFileSync(resolve(repoRoot, 'package.json'), 'utf8'));
    const trustScript = packageJson.scripts['check:trust-model-truth'];
    const qualityCheck = packageJson.scripts['quality:check'];

    assert.match(trustScript, /^node scripts\/quality\/check-trust-model-truth\.mjs --release$/);
    assert.match(qualityCheck, /npm run check:trust-model-truth/);
    assert.doesNotMatch(qualityCheck, /node scripts\/quality\/check-trust-model-truth\.mjs/);
  });
});
