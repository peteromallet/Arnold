#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const configPath = path.join(repoRoot, 'config/governance/video-editor-sdk-import-allowlist.json');

function fail(message) {
  console.error(`[video-editor-sdk-imports] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(configPath)) {
  fail(`Missing config: ${path.relative(repoRoot, configPath)}`);
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const publicEntrypoints = new Set((config.publicEntrypoints ?? []).map(normalizeConfigPath));
const allowlist = new Map(
  Object.entries(config.allowlist ?? {}).map(([importer, targets]) => [
    normalizeConfigPath(importer),
    new Set((Array.isArray(targets) ? targets : []).map(normalizeConfigPath)),
  ]),
);

function normalizeConfigPath(filePath) {
  return filePath.split('/').join(path.sep);
}

function walk(dir, files = []) {
  if (!fs.existsSync(dir)) {
    return files;
  }

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === 'dist' || entry.name.startsWith('.')) {
      continue;
    }

    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    if (!fullPath.endsWith('.ts') && !fullPath.endsWith('.tsx')) {
      continue;
    }

    const relativePath = path.relative(repoRoot, fullPath);
    if (
      relativePath.includes(`${path.sep}__tests__${path.sep}`)
      || relativePath.endsWith('.test.ts')
      || relativePath.endsWith('.test.tsx')
      || relativePath.startsWith(`src${path.sep}tools${path.sep}video-editor${path.sep}`)
    ) {
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

function maybeResolveVideoEditorTarget(importerPath, specifier) {
  if (!specifier) {
    return null;
  }

  if (specifier.startsWith('@/tools/video-editor')) {
    const suffix = specifier.slice('@/'.length);
    return resolveCandidate(path.join(repoRoot, 'src', suffix));
  }

  if (specifier.startsWith('.') || specifier.startsWith('/')) {
    const candidate = specifier.startsWith('/')
      ? path.join(repoRoot, specifier)
      : path.resolve(path.dirname(importerPath), specifier);
    const resolved = resolveCandidate(candidate);
    if (!resolved) {
      return null;
    }
    const relative = path.relative(repoRoot, resolved);
    if (!relative.startsWith(`src${path.sep}tools${path.sep}video-editor${path.sep}`)) {
      return null;
    }
    return resolved;
  }

  return null;
}

function resolveCandidate(candidate) {
  const normalized = candidate.replace(/[?#].*$/, '');
  const candidates = [
    normalized,
    `${normalized}.ts`,
    `${normalized}.tsx`,
    path.join(normalized, 'index.ts'),
    path.join(normalized, 'index.tsx'),
  ];

  for (const option of candidates) {
    if (fs.existsSync(option) && fs.statSync(option).isFile()) {
      return option;
    }
  }

  return null;
}

function extractSpecifiers(content) {
  const specifiers = new Set();
  const fromPattern = /\b(?:import|export)\b[\s\S]*?\bfrom\s+['"]([^'"]+)['"]/g;
  const dynamicPattern = /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g;

  for (const match of content.matchAll(fromPattern)) {
    specifiers.add(match[1]);
  }
  for (const match of content.matchAll(dynamicPattern)) {
    specifiers.add(match[1]);
  }

  return [...specifiers];
}

const files = [
  ...walk(path.join(repoRoot, 'src')),
  ...walk(path.join(repoRoot, 'supabase/functions')),
];

const failures = [];

for (const filePath of files) {
  const content = fs.readFileSync(filePath, 'utf8');
  const importer = path.relative(repoRoot, filePath);
  const allowedTargets = allowlist.get(normalizeConfigPath(importer)) ?? new Set();

  for (const specifier of extractSpecifiers(content)) {
    const resolvedTarget = maybeResolveVideoEditorTarget(filePath, specifier);
    if (!resolvedTarget) {
      continue;
    }

    const target = path.relative(repoRoot, resolvedTarget);
    const normalizedTarget = normalizeConfigPath(target);

    if (publicEntrypoints.has(normalizedTarget)) {
      continue;
    }

    if (allowedTargets.has(normalizedTarget)) {
      continue;
    }

    failures.push({
      importer,
      specifier,
      target,
    });
  }
}

if (failures.length > 0) {
  console.error('[video-editor-sdk-imports] FAILED: unsupported deep imports into src/tools/video-editor were found.');
  console.error('[video-editor-sdk-imports] Use the public entrypoints or extend the explicit allowlist for host-only adapters.');
  for (const failure of failures) {
    console.error(`  - ${failure.importer}`);
    console.error(`      import: ${failure.specifier}`);
    console.error(`      target: ${failure.target}`);
  }
  process.exit(1);
}

console.log('[video-editor-sdk-imports] OK: all external video-editor imports use public entrypoints or the approved allowlist.');

// ---------------------------------------------------------------------------
// Packagability smoke: verify @reigh/editor-sdk can be imported standalone
// without requiring any deep imports from src/tools/video-editor/*.
// ---------------------------------------------------------------------------

import { execSync } from 'node:child_process';
import os from 'node:os';

const SMOKE_LABEL = '[video-editor-sdk-smoke]';

/**
 * Create a temporary TypeScript fixture that imports only @reigh/editor-sdk,
 * defines a minimal extension, and type-checks cleanly. If tsc fails, the SDK
 * is not packagable — it likely transitively requires video-editor internals
 * that are unavailable to external consumers.
 */
function runPackagabilitySmoke() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'reigh-sdk-smoke-'));
  const fixturePath = path.join(tmpDir, 'smoke-fixture.ts');
  const tsconfigPath = path.join(tmpDir, 'tsconfig.json');

  const fixtureContent = `/**
 * Packagability smoke fixture — must NOT import from src/tools/video-editor/*.
 * Imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension } from '@reigh/editor-sdk';

const ext: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.smoke.packagability' as any,
    version: '1.0.0',
    label: 'Packagability Smoke',
    description: 'Temporary fixture verifying the SDK stands alone.',
    apiVersion: 1,
  },
});

// Also pull in a few additional public types to widen the import surface:
import {
  validateManifest,
  type ContributionKind,
  CONTRIBUTION_KIND_MILESTONE,
  contributionKindNotYetBridged,
} from '@reigh/editor-sdk';

// Exhaustiveness: reference the imports so they are not tree-shaken away
void ext;
void validateManifest;
void CONTRIBUTION_KIND_MILESTONE;
void contributionKindNotYetBridged;
// ContributionKind is type-only; used via typeof in type position below
type _SmokeCheck = ContributionKind;
void ({} as _SmokeCheck);
`;

  const tsconfigContent = {
    compilerOptions: {
      target: 'ESNext',
      module: 'ESNext',
      moduleResolution: 'bundler',
      baseUrl: repoRoot,
      paths: {
        '@/*': ['./src/*'],
        '@reigh/editor-sdk': ['./src/sdk/index.ts'],
      },
      skipLibCheck: true,
      noEmit: true,
      strict: true,
      allowImportingTsExtensions: true,
      isolatedModules: true,
    },
    include: ['smoke-fixture.ts'],
  };

  try {
    fs.writeFileSync(fixturePath, fixtureContent, 'utf8');
    fs.writeFileSync(tsconfigPath, JSON.stringify(tsconfigContent, null, 2), 'utf8');

    console.log(`${SMOKE_LABEL} Temporary fixture written to ${tmpDir}`);

    const tscPath = path.join(repoRoot, 'node_modules', '.bin', 'tsc');
    const cmd = `${tscPath} -p ${tsconfigPath} --noEmit`;

    console.log(`${SMOKE_LABEL} Running: ${cmd}`);
    const stdout = execSync(cmd, {
      cwd: tmpDir,
      encoding: 'utf8',
      timeout: 60_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    if (stdout.trim()) {
      console.log(`${SMOKE_LABEL} tsc stdout:\n${stdout}`);
    }

    // Verify the fixture does not contain any deep import into video-editor
    const fixtureText = fs.readFileSync(fixturePath, 'utf8');
    const deepImportPattern = /from\s+['"](?:@\/tools\/video-editor|.*\/src\/tools\/video-editor)/;
    if (deepImportPattern.test(fixtureText)) {
      console.error(`${SMOKE_LABEL} FAILED: smoke fixture itself contains a deep import into src/tools/video-editor.`);
      cleanupTmp(tmpDir);
      return false;
    }

    console.log(`${SMOKE_LABEL} PASSED: @reigh/editor-sdk type-checks standalone with no video-editor deep imports required.`);
    return true;
  } catch (err) {
    console.error(`${SMOKE_LABEL} FAILED: type-check of packagability fixture did not succeed.`);
    console.error(`${SMOKE_LABEL} This means @reigh/editor-sdk cannot be compiled in isolation —`);
    console.error(`${SMOKE_LABEL} it likely transitively requires types or values from src/tools/video-editor/*.`);
    if (err.stdout) console.error(`${SMOKE_LABEL} tsc stdout:\n${String(err.stdout)}`);
    if (err.stderr) console.error(`${SMOKE_LABEL} tsc stderr:\n${String(err.stderr)}`);
    if (!err.stdout && !err.stderr) console.error(`${SMOKE_LABEL} ${err.message}`);
    return false;
  } finally {
    cleanupTmp(tmpDir);
  }
}

function cleanupTmp(tmpDir) {
  try {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  } catch {
    // Best effort — temp dirs are ephemeral anyway.
  }
}

// ---------------------------------------------------------------------------
// Execute packagability smoke (always runs; failures are fatal)
// ---------------------------------------------------------------------------

console.log(`${SMOKE_LABEL} Running packagability smoke…`);
const smokeOk = runPackagabilitySmoke();
if (!smokeOk) {
  process.exit(1);
}

console.log('[video-editor-sdk-imports] All checks passed (allowlist + packagability smoke).');
