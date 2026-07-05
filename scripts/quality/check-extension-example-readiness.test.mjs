#!/usr/bin/env node
/**
 * Negative coverage for the extension example readiness gate.
 *
 * Proves the EX-01 through EX-04 release-example contract checks fail on:
 *   1. Broken doc refs
 *   2. Unsupported target paths
 *   3. Missing material statuses
 *   4. Missing stale planner actions
 *   5. Missing sidecar blockers
 *   6. Incomplete artifact routes
 *   7. Missing graph-path markers
 */

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
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');
const gateScript = resolve(moduleDir, 'check-extension-example-readiness.mjs');

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

function baselineMatrix() {
  return `# Supported / Deferred

## 2. Supported V1 Behavior Matrix
### | Supported |
| Row ID | Behavior | Classification | Evidence |
| --- | --- | --- | --- |
| S-001 | EX-01 | supported | EX: clip-shader-example.ts |
| S-002 | EX-02 | supported | EX: effect-live-example.ts |
| S-003 | EX-03 | supported | EX: transition-mask-example.ts |
| S-004 | EX-04 | supported | EX: output-format-sidecar-composed-example.ts |

## 3. Deferred / Unsupported V1 Behavior Matrix
### Deferred
| Row ID | Behavior | Classification | Evidence |
| --- | --- | --- | --- |
`;
}

function baselineReleaseExamplesDoc() {
  return `# Release Examples

## EX-01 - Clip + Shader + Shader-Uniform Keyframes
- \`src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:1-3\`
- \`src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:1-6\`

## EX-02 - Effect + Live Data + Bake
- \`src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx:1-6\`
- \`src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx:1-8\`

## EX-03 - Transition + Agent-Produced Mask Material
- \`src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-transition-mask-canary.integration.test.tsx:1-4\`
- \`src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx:1-8\`

## EX-04 - Output Format + Sidecar/Process Dependency With Non-Video Artifact Output
- \`src/examples/output-format-sidecar-composed-example.ts:1-8\`
- \`src/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx:1-3\`
- \`src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx:1-8\`
`;
}

function baselineExampleFile(name) {
  return `import type { ReighExtension } from '@reigh/editor-sdk';

export const ${name.replace(/-/g, '_')} = {} as ReighExtension;
`;
}

function setupTempRepo() {
  const root = mkdtempSync(join(os.tmpdir(), 'example-readiness-'));

  writeRepoFile(
    root,
    'config/governance/contract-surface-map.json',
    '{}\n',
  );
  writeRepoFile(
    root,
    'config/governance/sdk-public-export-allowlist.json',
    '{"allowlist":[]}\n',
  );
  writeRepoFile(
    root,
    'docs/video-editor/extension-platform-supported-deferred.md',
    baselineMatrix(),
  );
  writeRepoFile(
    root,
    'docs/extensions/composition-spine/m0-release-examples.md',
    baselineReleaseExamplesDoc(),
  );

  writeRepoFile(root, 'src/examples/clip-shader-example.ts', baselineExampleFile('clip-shader-example'));
  writeRepoFile(root, 'src/examples/effect-live-example.ts', baselineExampleFile('effect-live-example'));
  writeRepoFile(root, 'src/examples/transition-mask-example.ts', baselineExampleFile('transition-mask-example'));
  writeRepoFile(root, 'src/examples/output-format-sidecar-composed-example.ts', [
    'const EX04_GRAPH_PATH_MARKER = "EX-04/output-format-sidecar-composed";',
    'const EX04_ROUTE_CONSTRAINTS = ["sidecar-export"];',
    'const blocker = { reason: \'process-dependent\' };',
    'const evidence = {',
    '  graphPathMarker: EX04_GRAPH_PATH_MARKER,',
    '  routeConstraints: EX04_ROUTE_CONSTRAINTS,',
    '  requiredProfiles: [\'sidecar\'],',
    '};',
    'throw new Error(\'EX-04 artifact evidence route constraints must match the sidecar-export route.\');',
    'void blocker; void evidence;',
    '',
  ].join('\n'));

  writeRepoFile(root, 'src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts', [
    'export const ids = {',
    '  extensionId: "clip-local-shader-canary",',
    '};',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx', [
    'const shaderUniformEvidence = {',
    '  targetKind: \'shader-uniform\',',
    '  targetPath: \'uniforms.intensity\',',
    '};',
    'const shaderBlocker = { reason: \'missing-material\' };',
    'void shaderUniformEvidence; void shaderBlocker;',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx', [
    'const liveEdge = {',
    '  targetKind: \'effect-param\',',
    '  targetPath: \'intensity\',',
    '};',
    'const exportDiagnostic = { code: \'export/live-binding-unresolved\' };',
    'const plannerBlocker = { reason: \'live-unbaked\' };',
    'void liveEdge; void exportDiagnostic; void plannerBlocker;',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-transition-mask-canary.integration.test.tsx', [
    'const transitionMask = {',
    '  targetSlot: \'transition-mask\',',
    '  consumedKind: \'mask-material\',',
    '};',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx', [
    'type MaterialState = {',
    '  state: \'missing\' | \'pending\' | \'resolved\' | \'stale\' | \'failed\';',
    '};',
    'const plannerAction = { kind: \'materialize\' };',
    'const graphMarkerAssert = edge.detail?.graphPathMarker === contract.graphPathMarker;',
    'const routeProfileMarker = \'route-completion-profile-sidecar\';',
    'const processBlockerMarker = /requires the Example Analyzer process/i;',
    'void plannerAction; void graphMarkerAssert; void routeProfileMarker; void processBlockerMarker;',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx', [
    'export function RouteCompletionDashboard() {',
    '  return null;',
    '}',
    '',
  ].join('\n'));
  writeRepoFile(root, 'src/tools/video-editor/runtime/composition/materialRuntime.test.ts', [
    'expect(resolveMaterialAttachEntry(runtime, \'mat-stale\', transitionMaskContext)).toMatchObject({',
    '  diagnostic: {',
    '    detail: {',
    '      materialStatus: \'stale\',',
    '      materialSlot: \'transition-mask\',',
    '      repairAction: { kind: \'materialize\' },',
    '    },',
    '  },',
    '});',
    '',
  ].join('\n'));

  return {
    root,
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

function runGate(root) {
  try {
    const stdout = execSync(
      `node "${gateScript}" --release --repo-root="${root}"`,
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

describe('check-extension-example-readiness — release example contract coverage', () => {
  it('passes against the checked-in repository', () => {
    const result = runGate(repoRoot);
    assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /RELEASE PASSED/);
  });

  it('passes on the baseline EX-01 through EX-04 fixture set', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      const result = runGate(root);
      assert.strictEqual(result.exitCode, 0, result.stdout + result.stderr);
      assert.match(result.stdout, /RELEASE PASSED/);
    } finally {
      cleanup();
    }
  });

  it('fails on broken EX-01 doc refs', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'docs/extensions/composition-spine/m0-release-examples.md',
        'src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:1-3',
        'src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:50-60',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-01 broken ref/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-02 references an unsupported target path', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      writeRepoFile(root, 'src/tools/video-editor/examples/extensions/__tests__/process-runtime-canary.integration.test.tsx', 'export const noop = true;\n');
      replaceInFile(
        root,
        'docs/extensions/composition-spine/m0-release-examples.md',
        'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx:1-8`',
        'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx:1-8`\n- `src/tools/video-editor/examples/extensions/__tests__/process-runtime-canary.integration.test.tsx:1-1`',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-02 references unsupported target path/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-03 material status coverage drops a required status', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
        '\'missing\' | \'pending\' | \'resolved\' | \'stale\' | \'failed\'',
        '\'missing\' | \'pending\' | \'resolved\' | \'failed\'',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-03 material status coverage failed/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-03 stale planner action evidence disappears', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'src/tools/video-editor/runtime/composition/materialRuntime.test.ts',
        'repairAction: { kind: \'materialize\' },',
        'repairAction: {},',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-03 stale planner action evidence failed/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-04 sidecar blocker evidence disappears', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'src/examples/output-format-sidecar-composed-example.ts',
        'reason: \'process-dependent\'',
        'reason: \'stopped\'',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-04 sidecar blocker and artifact-route evidence failed/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-04 artifact-route evidence stops using the sidecar route constraints', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'src/examples/output-format-sidecar-composed-example.ts',
        'routeConstraints: EX04_ROUTE_CONSTRAINTS,',
        'routeConstraints: [\'preview\'],',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-04 sidecar blocker and artifact-route evidence failed/);
    } finally {
      cleanup();
    }
  });

  it('fails when EX-04 graph-path marker assertions disappear', () => {
    const { root, cleanup } = setupTempRepo();
    try {
      replaceInFile(
        root,
        'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
        'edge.detail?.graphPathMarker === contract.graphPathMarker;',
        'true;',
      );

      const result = runGate(root);
      assert.strictEqual(result.exitCode, 1);
      assert.match(result.stdout + result.stderr, /EX-04 graph-path and dashboard acceptance evidence failed/);
    } finally {
      cleanup();
    }
  });
});
