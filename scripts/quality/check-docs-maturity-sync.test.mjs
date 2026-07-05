#!/usr/bin/env node

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execSync } from 'node:child_process';
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import os from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');
const gateScript = resolve(moduleDir, 'check-docs-maturity-sync.mjs');

function writeRepoFile(root, relPath, content) {
  const absPath = join(root, relPath);
  mkdirSync(dirname(absPath), { recursive: true });
  writeFileSync(absPath, content, 'utf8');
}

function replaceInFile(root, relPath, searchValue, replaceValue) {
  const absPath = join(root, relPath);
  const next = readFileSync(absPath, 'utf8').replace(searchValue, replaceValue);
  writeFileSync(absPath, next, 'utf8');
}

function baselineMaturityRegistry() {
  return JSON.stringify(
    [
      {
        kind: 'outputFormat',
        label: 'Output Format',
        declarationMaturity: 'typed',
        executionMaturity: 'delegated',
        requiresTrustedCode: false,
        legacyCompatibility: { bridged: true },
        hostAdapter: 'src/tools/video-editor/runtime/families/outputFormatAdapter.ts',
        hostIntegrationNotes:
          'Output format types are declared but runtime execution is reserved.',
      },
      {
        kind: 'process',
        label: 'Process',
        declarationMaturity: 'typed',
        executionMaturity: 'delegated',
        requiresTrustedCode: true,
        legacyCompatibility: { bridged: true },
        hostAdapter: 'src/tools/video-editor/runtime/families/processAdapter.ts',
        hostIntegrationNotes:
          'Process descriptors remain host-scoped and route-scoped.',
      },
    ],
    null,
    2,
  ) + '\n';
}

function baselineTable() {
  return [
    '| Family | Declaration | Execution | Trusted | Bridged | Host Adapter | Notes |',
    '|---|---|---|---|---|---|---|',
    '| Output Format | typed | delegated | No | Yes | `outputFormatAdapter.ts` | Output format types are declared but runtime execution is reserved. |',
    '| Process | typed | delegated | Yes | Yes | `processAdapter.ts` | Process descriptors remain host-scoped and route-scoped. |',
    '',
  ].join('\n');
}

function baselinePhase4Doc() {
  return `# Phase 4 Extension Readiness Gate

## Trust And Sandbox Posture

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime
  enforcement, sandbox isolation, code signing, or a permission broker.
- Public promotion is blocked until a real sandbox or permission broker exists.
- Docs must avoid implying marketplace review or safe third-party execution.

## Family Maturity Snapshot

<!-- family-maturity-table-start -->
${baselineTable()}<!-- family-maturity-table-end -->
`;
}

function baselineFoundationDoc() {
  return `# Foundation Closure Assessment

## Trust Posture

- No sandbox, permission broker, marketplace, remote install, or signing claims
  are made in the docs, examples, or manager surfaces.
- The current posture remains trusted/unsandboxed local packages only.

## Family Maturity Snapshot

<!-- family-maturity-table-start -->
${baselineTable()}<!-- family-maturity-table-end -->
`;
}

function baselineReleaseExamplesDoc() {
  return `# Release Examples

## EX-04 - Output Format + Sidecar/Process Dependency With Non-Video Artifact Output

- The output format projects a route-scoped requires path for the trusted
  process and operation needed to run the sidecar-export route.
- EX-04 claims only graph facts, route blockers, repair actions, and artifact
  evidence. It does not claim sandboxing, marketplace, headless rendering,
  process execution support, preview support, or runtime certification for
  machine-path / executable-package profiles.
`;
}

function setupTempRepo() {
  const root = mkdtempSync(join(os.tmpdir(), 'docs-maturity-sync-'));

  writeRepoFile(root, 'config/extensions/family-maturity.json', baselineMaturityRegistry());
  writeRepoFile(root, 'docs/extensions/phase4-readiness.md', baselinePhase4Doc());
  writeRepoFile(
    root,
    'docs/extensions/foundation-closure-assessment.md',
    baselineFoundationDoc(),
  );
  writeRepoFile(
    root,
    'docs/extensions/composition-spine/m0-release-examples.md',
    baselineReleaseExamplesDoc(),
  );

  return {
    root,
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

function runGate(root, mode = '--release') {
  try {
    const stdout = execSync(
      `node "${gateScript}" ${mode} --repo-root="${root}"`,
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

describe('check-docs-maturity-sync', () => {
  it('passes against the checked-in repository', () => {
    const result = runGate(repoRoot);
    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /RELEASE PASSED/);
  });

  it('passes on the baseline fixture set', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      const result = runGate(root);
      assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
      assert.match(result.stdout, /RELEASE PASSED/);
    } finally {
      cleanup();
    }
  });

  it('fails when a maturity table is stale', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/phase4-readiness.md',
        '| Process | typed | delegated | Yes | Yes | `processAdapter.ts` | Process descriptors remain host-scoped and route-scoped. |',
        '| Process | typed | delegated | Yes | Yes | `processAdapter.ts` | stale row |',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /Stale maturity table/);
    } finally {
      cleanup();
    }
  });

  it('fails on unsupported positive sandbox claims', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/phase4-readiness.md',
        'Public promotion is blocked until a real sandbox or permission broker exists.',
        'Public promotion uses a real sandbox and permission broker today.',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /unsupported positive claim/);
      assert.match(result.stdout + result.stderr, /sandbox/);
    } finally {
      cleanup();
    }
  });

  it('fails on ambiguous marketplace claims', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/foundation-closure-assessment.md',
        'No sandbox, permission broker, marketplace, remote install, or signing claims\n  are made in the docs, examples, or manager surfaces.',
        'Marketplace integration remains under discussion.',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /unsupported ambiguous claim/);
      assert.match(result.stdout + result.stderr, /marketplace/);
    } finally {
      cleanup();
    }
  });

  it('allows explicit anti-scope denials for sandbox, marketplace, and headless renderer', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/composition-spine/m0-release-examples.md',
        'process execution support, preview support, or runtime certification for\n  machine-path / executable-package profiles.',
        'process execution support, preview support, runtime certification, or headless renderer support for\n  machine-path / executable-package profiles.',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
      assert.match(result.stdout, /RELEASE PASSED/);
    } finally {
      cleanup();
    }
  });

  it('fails on machine-path and executable-package runtime preview claims', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/composition-spine/m0-release-examples.md',
        'process execution support, preview support, or runtime certification for\n  machine-path / executable-package profiles.',
        'preview support and runtime certification for machine-path / executable-package profiles.',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /machine-path \/ executable-package/);
    } finally {
      cleanup();
    }
  });

  it('fails on output-format sidecar runtime-support claims', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/composition-spine/m0-release-examples.md',
        '- The output format projects a route-scoped requires path for the trusted\n  process and operation needed to run the sidecar-export route.',
        '- The output format sidecar path includes runtime support and preview support for sidecar-export.',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /output-format \/ sidecar runtime-support claim/);
    } finally {
      cleanup();
    }
  });
});
