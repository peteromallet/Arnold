#!/usr/bin/env node
/**
 * Coverage for the extension family conformance gate — M7b sidecar-blocker
 * and requirement-key awareness.
 *
 * Uses temporary fixtures where practical.  The registry is dynamically
 * imported via tsx path resolution, so negative M7b-key tests operate
 * against the checked-in registry while the sidecar-blocker checks use
 * temp directories for the file-system reads.
 */

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import os from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');
const gateScript = resolve(moduleDir, 'check-extension-family-conformance.mjs');

function writeRepoFile(root, relPath, content) {
  const absPath = join(root, relPath);
  mkdirSync(dirname(absPath), { recursive: true });
  writeFileSync(absPath, content, 'utf8');
}

function replaceInFile(root, relPath, searchValue, replaceValue) {
  const absPath = join(root, relPath);
  const next = readFileSync(absPath, 'utf8').replaceAll(searchValue, replaceValue);
  writeFileSync(absPath, next, 'utf8');
}

function runGate(root, mode = '--audit') {
  try {
    const result = execSync(
      `npx tsx "${gateScript}" ${mode} --repo-root="${root}" 2>&1`,
      {
        cwd: repoRoot,
        encoding: 'utf8',
        stdio: 'pipe',
        timeout: 30_000,
      },
    );
    return { exitCode: 0, stdout: result, stderr: '' };
  } catch (error) {
    return {
      exitCode: error.status ?? 1,
      stdout: error.stdout ?? '',
      stderr: error.stderr ?? error.message,
    };
  }
}

/**
 * Sets up a temp repo that mirrors the real repo's structure enough for
 * the sidecar-blocker file-system checks to run.  The temp dir must
 * contain the schema, maturity JSON, and adapter/projector files at the
 * expected paths.  The registry import resolves from the real project
 * root regardless of --repo-root (tsx uses the real tsconfig).
 */
function setupTempRepoForSidecarChecks() {
  const root = mkdtempSync(join(os.tmpdir(), 'family-conformance-'));

  // Copy the schema from the real repo
  const schemaSrc = join(repoRoot, 'config/contracts/reigh-extension.schema.json');
  writeRepoFile(root, 'config/contracts/reigh-extension.schema.json', readFileSync(schemaSrc, 'utf8'));

  // Copy family-maturity.json
  const maturitySrc = join(repoRoot, 'config/extensions/family-maturity.json');
  writeRepoFile(root, 'config/extensions/family-maturity.json', readFileSync(maturitySrc, 'utf8'));

  // Copy the outputFormat projector
  const projectorSrc = join(repoRoot, 'src/tools/video-editor/runtime/families/projectors/outputFormatProjector.ts');
  writeRepoFile(
    root,
    'src/tools/video-editor/runtime/families/projectors/outputFormatProjector.ts',
    readFileSync(projectorSrc, 'utf8'),
  );

  // Copy the process adapter
  const processAdapterSrc = join(repoRoot, 'src/tools/video-editor/runtime/families/processAdapter.ts');
  writeRepoFile(
    root,
    'src/tools/video-editor/runtime/families/processAdapter.ts',
    readFileSync(processAdapterSrc, 'utf8'),
  );

  // Copy extensionSurface.ts (needed for inline-projection check)
  const extSurfaceSrc = join(repoRoot, 'src/tools/video-editor/runtime/extensionSurface.ts');
  if (existsSync(extSurfaceSrc)) {
    writeRepoFile(
      root,
      'src/tools/video-editor/runtime/extensionSurface.ts',
      readFileSync(extSurfaceSrc, 'utf8'),
    );
  }

  // Copy projector directory (needed for projector import checks)
  const projectorsDir = join(repoRoot, 'src/tools/video-editor/runtime/families/projectors');
  if (existsSync(projectorsDir)) {
    for (const f of readdirSync(projectorsDir)) {
      if (f.endsWith('.ts')) {
        writeRepoFile(
          root,
          `src/tools/video-editor/runtime/families/projectors/${f}`,
          readFileSync(join(projectorsDir, f), 'utf8'),
        );
      }
    }
  }

  return {
    root,
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

describe('check-extension-family-conformance — M7b sidecar-blocker and requirement-key awareness', () => {
  it('passes against the checked-in repository (audit mode)', () => {
    const result = runGate(repoRoot, '--audit');
    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Checking sidecar-blocker awareness/);
  });

  it('recognizes M7b requirement keys for outputFormat and process families', () => {
    const result = runGate(repoRoot, '--audit');
    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    // The output should NOT warn about missing M7b keys for outputFormat/process
    assert.doesNotMatch(
      result.stdout + result.stderr,
      /outputFormat.*is missing M7b requirement key/,
    );
    assert.doesNotMatch(
      result.stdout + result.stderr,
      /process.*is missing M7b requirement key/,
    );
  });

  it('passes sidecar-blocker checks on a fixture that mirrors the real project', () => {
    const { root, cleanup } = setupTempRepoForSidecarChecks();
    try {
      const result = runGate(root, '--audit');
      // The gate may produce other warnings but should not produce sidecar-blocker warnings
      assert.doesNotMatch(
        result.stdout + result.stderr,
        /sidecar-blocker awareness is incomplete/,
      );
    } finally {
      cleanup();
    }
  });

  it('fails when outputFormat projector loses sidecar-export references', () => {
    const { root, cleanup } = setupTempRepoForSidecarChecks();
    try {
      replaceInFile(
        root,
        'src/tools/video-editor/runtime/families/projectors/outputFormatProjector.ts',
        'sidecar-export',
        'unsupported-route',
      );

      const result = runGate(root, '--audit');
      assert.match(
        result.stdout + result.stderr,
        /does not reference sidecar-export routes/,
      );
    } finally {
      cleanup();
    }
  });

  it('fails when outputFormat projector loses buildOutputFormatBlockers', () => {
    const { root, cleanup } = setupTempRepoForSidecarChecks();
    try {
      replaceInFile(
        root,
        'src/tools/video-editor/runtime/families/projectors/outputFormatProjector.ts',
        'buildOutputFormatBlockers',
        'buildLegacyBlockers',
      );

      const result = runGate(root, '--audit');
      assert.match(
        result.stdout + result.stderr,
        /is missing buildOutputFormatBlockers/,
      );
    } finally {
      cleanup();
    }
  });

  it('fails when process adapter loses process-dependent references', () => {
    const { root, cleanup } = setupTempRepoForSidecarChecks();
    try {
      // Remove all process-dependent, sidecar, and route-scoped references
      const adapterPath = join(
        root,
        'src/tools/video-editor/runtime/families/processAdapter.ts',
      );
      let content = readFileSync(adapterPath, 'utf8');
      content = content.replace(/process-dependent/g, 'unknown-state');
      content = content.replace(/sidecar/g, 'auxiliary');
      content = content.replace(/route-scoped/g, 'global');
      writeFileSync(adapterPath, content, 'utf8');

      const result = runGate(root, '--audit');
      assert.match(
        result.stdout + result.stderr,
        /does not reference sidecar or route-scoped concepts/,
      );
    } finally {
      cleanup();
    }
  });
});
