#!/usr/bin/env node
/**
 * M2b T30 — SDK-Internal No-Barrel-Import Gate Negative Coverage Tests
 *
 * Proves that the no-barrel-import gate catches deliberate barrel-import
 * violations, including both `./index` and `../index` raw specifiers.
 *
 * Uses Node.js built-in test runner (node:test) and fixture files under
 * `scripts/quality/__fixtures__/barrel-import-violation/`.
 *
 * Also proves the updated check-sdk-public-exports gate fails in release
 * mode when inline declarations or obsolete inline allowlist entries exist.
 */

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');
const gateScript = resolve(moduleDir, 'check-sdk-no-barrel-imports.mjs');
const publicExportsScript = resolve(moduleDir, 'check-sdk-public-exports.mjs');

/**
 * Build a temporary SDK directory structure that mimics the real src/sdk/
 * layout with a barrel (index.ts) and fixture source files.
 *
 * @param {{ barrelContent?: string, files?: Array<{ relPath: string, content: string }> }} opts
 * @returns {{ root: string, sdkDir: string, cleanup: () => void }}
 */
function setupTempSdkDir(opts = {}) {
  const tempRoot = mkdtempSync(join(os.tmpdir(), 'barrel-gate-test-'));
  const sdkDir = join(tempRoot, 'src', 'sdk');

  // Create the sdk directory first
  execSync(`mkdir -p "${sdkDir}"`, { encoding: 'utf8' });

  // Create barrel
  const barrelContent = opts.barrelContent ?? 'export type { DisposeHandle } from "./dispose";\n';
  writeFileSync(join(sdkDir, 'index.ts'), barrelContent, 'utf8');

  // Place fixture files
  if (opts.files) {
    for (const { relPath, content } of opts.files) {
      const fullPath = join(sdkDir, relPath);
      const dir = dirname(fullPath);
      execSync(`mkdir -p "${dir}"`, { encoding: 'utf8' });
      writeFileSync(fullPath, content, 'utf8');
    }
  }

  return {
    root: tempRoot,
    sdkDir,
    cleanup: () => {
      try { rmSync(tempRoot, { recursive: true, force: true }); } catch { /* best-effort */ }
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Run the no-barrel-import gate against a temporary SDK directory.
 * Returns { exitCode, stdout, stderr }.
 */
function runBarrelGate(tempSdkDir, mode = '--release') {
  try {
    const result = execSync(
      `node "${gateScript}" ${mode} --sdk-dir="${tempSdkDir}"`,
      { cwd: repoRoot, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 },
    );
    return { exitCode: 0, stdout: result, stderr: '' };
  } catch (err) {
    return {
      exitCode: err.status ?? 1,
      stdout: err.stdout ?? '',
      stderr: err.stderr ?? err.message,
    };
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('check-sdk-no-barrel-imports — Barrel Detection', () => {

  // -----------------------------------------------------------------------
  // 1. Clean file (should pass)
  // -----------------------------------------------------------------------
  it('passes on clean SDK files with direct canonical imports', () => {
    const { sdkDir, cleanup } = setupTempSdkDir({
      barrelContent: 'export type { DisposeHandle } from "./dispose";\nexport const foo = 1;\n',
      files: [
        {
          relPath: 'clean-file.ts',
          content: `import type { DisposeHandle } from './dispose';\nexport const clean = 1;\n`,
        },
      ],
    });

    try {
      const result = runBarrelGate(sdkDir, '--release');
      assert.strictEqual(
        result.exitCode, 0,
        `Expected exit 0 for clean file. Got ${result.exitCode}. stderr: ${result.stderr}`,
      );
      assert.ok(
        result.stdout.includes('RELEASE PASSED'),
        `Expected RELEASE PASSED in output. Got: ${result.stdout}`,
      );
    } finally {
      cleanup();
    }
  });

  // -----------------------------------------------------------------------
  // 2. ./index barrel import (should fail)
  // -----------------------------------------------------------------------
  it('catches ./index barrel import from file directly in sdk/', () => {
    const { sdkDir, cleanup } = setupTempSdkDir({
      barrelContent: 'export type { DisposeHandle } from "./dispose";\n',
      files: [
        {
          relPath: 'violating-file.ts',
          content: `import type { DisposeHandle } from './index';\nexport const violation = 1;\n`,
        },
      ],
    });

    try {
      const result = runBarrelGate(sdkDir, '--release');
      assert.strictEqual(
        result.exitCode, 1,
        `Expected exit 1 for ./index barrel import. Got ${result.exitCode}.`,
      );
      const combined = result.stdout + result.stderr;
      assert.ok(
        combined.includes('barrel import') || combined.includes('RELEASE FAILED'),
        `Expected barrel-import violation message. Got: ${combined}`,
      );
      assert.ok(
        combined.includes('./index'),
        `Expected './index' in violation report. Got: ${combined}`,
      );
    } finally {
      cleanup();
    }
  });

  // -----------------------------------------------------------------------
  // 3. ../index barrel import from deep path (should fail)
  // -----------------------------------------------------------------------
  it('catches ../index barrel import from file in sdk/ subdirectory', () => {
    const { sdkDir, cleanup } = setupTempSdkDir({
      barrelContent: 'export type { DisposeHandle } from "./dispose";\n',
      files: [
        {
          relPath: 'video/deep-file.ts',
          content: `import type { DisposeHandle } from '../index';\nexport const deepViolation = 1;\n`,
        },
      ],
    });

    try {
      const result = runBarrelGate(sdkDir, '--release');
      assert.strictEqual(
        result.exitCode, 1,
        `Expected exit 1 for ../index barrel import. Got ${result.exitCode}.`,
      );
      const combined = result.stdout + result.stderr;
      assert.ok(
        combined.includes('barrel import') || combined.includes('RELEASE FAILED'),
        `Expected barrel-import violation message. Got: ${combined}`,
      );
    } finally {
      cleanup();
    }
  });

  // -----------------------------------------------------------------------
  // 4. ../../index barrel import from deep path (should fail)
  // -----------------------------------------------------------------------
  it('catches ../../index barrel import from file deep in sdk/', () => {
    const { sdkDir, cleanup } = setupTempSdkDir({
      barrelContent: 'export type { DisposeHandle } from "./dispose";\n',
      files: [
        {
          relPath: 'video/families/deep-file.ts',
          content: `import type { DisposeHandle } from '../../index';\nexport const deepViolation = 1;\n`,
        },
      ],
    });

    try {
      const result = runBarrelGate(sdkDir, '--release');
      assert.strictEqual(
        result.exitCode, 1,
        `Expected exit 1 for ../../index barrel import. Got ${result.exitCode}.`,
      );
      const combined = result.stdout + result.stderr;
      assert.ok(
        combined.includes('barrel import') || combined.includes('RELEASE FAILED'),
        `Expected barrel-import violation message. Got: ${combined}`,
      );
    } finally {
      cleanup();
    }
  });

  // -----------------------------------------------------------------------
  // 5. Audit mode warns but does not fail
  // -----------------------------------------------------------------------
  it('audit mode warns on violations but exits 0', () => {
    const { sdkDir, cleanup } = setupTempSdkDir({
      barrelContent: 'export type { DisposeHandle } from "./dispose";\n',
      files: [
        {
          relPath: 'violating-file.ts',
          content: `import type { DisposeHandle } from './index';\nexport const violation = 1;\n`,
        },
      ],
    });

    try {
      const result = runBarrelGate(sdkDir, '--audit');
      assert.strictEqual(
        result.exitCode, 0,
        `Expected exit 0 in audit mode. Got ${result.exitCode}.`,
      );
      const combined = result.stdout + result.stderr;
      assert.ok(
        combined.includes('AUDIT') || combined.includes('violation'),
        `Expected audit warning. Got: ${combined}`,
      );
    } finally {
      cleanup();
    }
  });

  // -----------------------------------------------------------------------
  // 6. @/sdk and @reigh/editor-sdk alias coverage
  // NOTE: These alias-based barrel imports are caught by the TypeScript
  // resolution layer in the real gate run against the real repo.  They
  // cannot be tested in a temp directory because tsconfig paths alias
  // @/ → src/ which directs to the real repo, not the temp fixture.
  // The real gate run (`node scripts/quality/check-sdk-no-barrel-imports.mjs
  // --release`) covers these paths.  Relative specifier coverage (./index,
  // ../index, ../../index) is the focus of this fixture-based test suite.
  // -----------------------------------------------------------------------
});

describe('check-sdk-public-exports — No-Inline Barrel Gate', () => {

  // -----------------------------------------------------------------------
  // 8. Release mode fails when inline declarations exist in barrel
  // -----------------------------------------------------------------------
  it('release mode fails when barrel has inline exported declarations', () => {
    const tempDir = mkdtempSync(join(os.tmpdir(), 'pubexport-gate-test-'));
    const sdkDir = join(tempDir, 'src', 'sdk');

    try {
      // Create minimal sdk dir with barrel that has an inline declaration
      execSync(`mkdir -p "${sdkDir}"`, { encoding: 'utf8' });

      const barrelContent = `// Inline declaration - should NOT be allowed in pure barrel
export interface InlineViolation {
  name: string;
}
export type { DisposeHandle } from './dispose';
`;
      writeFileSync(join(sdkDir, 'index.ts'), barrelContent, 'utf8');
      // Create a minimal allowlist
      const govDir = join(tempDir, 'config', 'governance');
      execSync(`mkdir -p "${govDir}"`, { encoding: 'utf8' });
      writeFileSync(join(govDir, 'sdk-public-export-allowlist.json'), JSON.stringify({
        allowlist: [],
        inlineDeclarations: [],
      }), 'utf8');

      try {
        execSync(
          `node "${publicExportsScript}" --release`,
          { cwd: tempDir, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 },
        );
        assert.fail('Expected release mode to fail on inline declarations');
      } catch (err) {
        const combined = (err.stdout ?? '') + (err.stderr ?? '');
        assert.ok(
          combined.includes('inline') && combined.includes('declaration'),
          `Expected inline declaration failure. Got: ${combined}`,
        );
        assert.ok(
          combined.includes('InlineViolation'),
          `Expected InlineViolation mentioned. Got: ${combined}`,
        );
      }
    } finally {
      try { rmSync(tempDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  });

  // -----------------------------------------------------------------------
  // 9. Release mode fails when inline allowlist has obsolete entries
  // -----------------------------------------------------------------------
  it('release mode fails when inlineDeclarations has obsolete entries', () => {
    const tempDir = mkdtempSync(join(os.tmpdir(), 'pubexport-obsolete-test-'));
    const sdkDir = join(tempDir, 'src', 'sdk');

    try {
      execSync(`mkdir -p "${sdkDir}"`, { encoding: 'utf8' });

      // Pure barrel — no inline declarations
      const barrelContent = `export type { DisposeHandle } from './dispose';
`;
      writeFileSync(join(sdkDir, 'index.ts'), barrelContent, 'utf8');

      // Allowlist with an obsolete inline declaration entry
      const govDir = join(tempDir, 'config', 'governance');
      execSync(`mkdir -p "${govDir}"`, { encoding: 'utf8' });
      writeFileSync(join(govDir, 'sdk-public-export-allowlist.json'), JSON.stringify({
        allowlist: [],
        inlineDeclarations: [
          {
            symbol: 'GhostDeclaration',
            owner: 'src/sdk/index.ts',
            rationale: 'This declaration no longer exists',
            expiration: 'M2b',
          },
        ],
      }), 'utf8');

      try {
        execSync(
          `node "${publicExportsScript}" --release`,
          { cwd: tempDir, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 },
        );
        assert.fail('Expected release mode to fail on obsolete inline entries');
      } catch (err) {
        const combined = (err.stdout ?? '') + (err.stderr ?? '');
        assert.ok(
          combined.includes('obsolete') && combined.includes('GhostDeclaration'),
          `Expected obsolete inline entry failure for GhostDeclaration. Got: ${combined}`,
        );
      }
    } finally {
      try { rmSync(tempDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  });

  // -----------------------------------------------------------------------
  // 10. Release mode passes with clean pure-re-export barrel
  // -----------------------------------------------------------------------
  it('release mode passes with clean pure-re-export barrel', () => {
    const tempDir = mkdtempSync(join(os.tmpdir(), 'pubexport-clean-test-'));
    const sdkDir = join(tempDir, 'src', 'sdk');

    try {
      execSync(`mkdir -p "${sdkDir}"`, { encoding: 'utf8' });

      // Pure barrel — only re-exports
      const barrelContent = `export type { DisposeHandle } from './dispose';
export { createDiagnosticCollection } from './diagnostics';
`;
      writeFileSync(join(sdkDir, 'index.ts'), barrelContent, 'utf8');

      // Clean allowlist
      const govDir = join(tempDir, 'config', 'governance');
      execSync(`mkdir -p "${govDir}"`, { encoding: 'utf8' });
      writeFileSync(join(govDir, 'sdk-public-export-allowlist.json'), JSON.stringify({
        allowlist: [],
        inlineDeclarations: [],
      }), 'utf8');

      const result = execSync(
        `node "${publicExportsScript}" --release`,
        { cwd: tempDir, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 },
      );
      assert.ok(
        result.includes('RELEASE PASSED'),
        `Expected RELEASE PASSED. Got: ${result}`,
      );
      assert.ok(
        result.includes('0 declared'),
        `Expected 0 declared. Got: ${result}`,
      );
    } finally {
      try { rmSync(tempDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  });
});
