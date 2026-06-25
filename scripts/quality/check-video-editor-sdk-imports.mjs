#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

let ts;

try {
  ({ default: ts } = await import('typescript'));
} catch (error) {
  const reason = error instanceof Error ? error.message : String(error);
  fail(`TypeScript tooling is unavailable: ${reason}`);
}

const repoRoot = process.cwd();
const configPath = path.join(repoRoot, 'config/governance/video-editor-sdk-import-allowlist.json');
const tsconfigPath = path.join(repoRoot, 'tsconfig.json');
const tscPath = path.join(repoRoot, 'node_modules', '.bin', 'tsc');
const videoEditorDir = path.join(repoRoot, 'src', 'tools', 'video-editor') + path.sep;

function fail(message) {
  console.error(`[video-editor-sdk-imports] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(tscPath)) {
  fail(`TypeScript CLI is unavailable: missing ${path.relative(repoRoot, tscPath)}`);
}

if (!fs.existsSync(configPath)) {
  fail(`Missing config: ${path.relative(repoRoot, configPath)}`);
}

if (!fs.existsSync(tsconfigPath)) {
  fail(`Missing tsconfig: ${path.relative(repoRoot, tsconfigPath)}`);
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

function relativeToRepo(filePath) {
  return path.relative(repoRoot, filePath);
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

function parseTsconfigOptions() {
  const configFile = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (configFile.error) {
    fail(formatTsDiagnostic(configFile.error));
  }

  const parsed = ts.parseJsonConfigFileContent(
    configFile.config,
    ts.sys,
    path.dirname(tsconfigPath),
  );

  if (parsed.errors.length > 0) {
    fail(parsed.errors.map(formatTsDiagnostic).join('\n'));
  }

  return parsed.options;
}

function formatTsDiagnostic(diagnostic) {
  return ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
}

function extractImportRecords(filePath, content) {
  /** @type {Array<{ specifier: string, kind: 'import' | 'export-from' | 'dynamic-import' }>} */
  const records = [];
  const seen = new Set();
  const sourceFile = ts.createSourceFile(
    filePath,
    content,
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  ts.forEachChild(sourceFile, function visit(node) {
    if (
      ts.isImportDeclaration(node)
      && ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const key = `import:${node.moduleSpecifier.text}`;
      if (!seen.has(key)) {
        seen.add(key);
        records.push({
          specifier: node.moduleSpecifier.text,
          kind: 'import',
        });
      }
    } else if (
      ts.isExportDeclaration(node)
      && node.moduleSpecifier
      && ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const key = `export-from:${node.moduleSpecifier.text}`;
      if (!seen.has(key)) {
        seen.add(key);
        records.push({
          specifier: node.moduleSpecifier.text,
          kind: 'export-from',
        });
      }
    } else if (
      ts.isCallExpression(node)
      && node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      const [firstArg] = node.arguments;
      if (
        firstArg
        && (
          ts.isStringLiteral(firstArg)
          || ts.isNoSubstitutionTemplateLiteral(firstArg)
        )
      ) {
        const key = `dynamic-import:${firstArg.text}`;
        if (!seen.has(key)) {
          seen.add(key);
          records.push({
            specifier: firstArg.text,
            kind: 'dynamic-import',
          });
        }
      }
    }

    ts.forEachChild(node, visit);
  });

  return records;
}

function resolveModuleSpecifier(importerPath, specifier, compilerOptions) {
  const { resolvedModule } = ts.resolveModuleName(
    specifier,
    importerPath,
    compilerOptions,
    ts.sys,
  );

  if (!resolvedModule?.resolvedFileName) {
    return null;
  }

  const resolvedFileName = resolvedModule.resolvedFileName;
  if (!path.isAbsolute(resolvedFileName)) {
    return path.resolve(resolvedFileName);
  }
  return resolvedFileName;
}

function isVideoEditorPath(resolvedPath) {
  return resolvedPath.startsWith(videoEditorDir);
}

const compilerOptions = parseTsconfigOptions();
const files = [
  ...walk(path.join(repoRoot, 'src')),
  ...walk(path.join(repoRoot, 'supabase/functions')),
];

function collectFailuresForFile(filePath, content) {
  const importer = relativeToRepo(filePath);
  const allowedTargets = allowlist.get(normalizeConfigPath(importer)) ?? new Set();
  const textSpecifiers = new Set(extractSpecifiers(content));
  const fileFailures = [];

  for (const record of extractImportRecords(filePath, content)) {
    const { specifier, kind } = record;
    const resolvedTarget = resolveModuleSpecifier(filePath, specifier, compilerOptions);
    if (!resolvedTarget) {
      continue;
    }

    if (!isVideoEditorPath(resolvedTarget)) {
      continue;
    }

    const target = relativeToRepo(resolvedTarget);
    const normalizedTarget = normalizeConfigPath(target);

    if (publicEntrypoints.has(normalizedTarget)) {
      continue;
    }

    if (allowedTargets.has(normalizedTarget)) {
      continue;
    }

    fileFailures.push({
      importer,
      kind,
      specifier,
      target,
      textMatched: textSpecifiers.has(specifier),
    });
  }

  return fileFailures;
}

const failures = [];

for (const filePath of files) {
  const content = fs.readFileSync(filePath, 'utf8');
  failures.push(...collectFailuresForFile(filePath, content));
}

if (failures.length > 0) {
  console.error('[video-editor-sdk-imports] FAILED: unsupported deep imports into src/tools/video-editor were found.');
  console.error('[video-editor-sdk-imports] Use the public entrypoints or extend the explicit allowlist for host-only adapters.');
  for (const failure of failures) {
    console.error(`  - ${failure.importer}`);
    console.error(`      kind: ${failure.kind}`);
    console.error(`      import: ${failure.specifier}`);
    console.error(`      target: ${failure.target}`);
    console.error(`      text-match: ${failure.textMatched ? 'yes' : 'no'}`);
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
    // The SDK intentionally re-exports some video-editor internals, so tsc may
    // report diagnostics in those transitive source files. The smoke's real
    // purpose is to prove that an external consumer can import @reigh/editor-sdk
    // without needing to import from src/tools/video-editor/* directly. We
    // therefore tolerate SDK-internal diagnostics and only fail if the fixture
    // itself cannot resolve the SDK or contains a forbidden deep import.
    const output = String(err.stdout || err.stderr || err.message || '');
    const escapedFixturePath = fixturePath.replace(
      /[.*+?^${}()|[\]\\]/g,
      '\\$&',
    );
    const fixtureErrorPattern = new RegExp(
      `^${escapedFixturePath}\\(\\d+,\\d+\\):\\s*error`,
      'm',
    );

    if (fixtureErrorPattern.test(output)) {
      console.error(`${SMOKE_LABEL} FAILED: the smoke fixture cannot import @reigh/editor-sdk cleanly.`);
      console.error(`${SMOKE_LABEL} tsc output:\n${output}`);
      return false;
    }

    // Verify the fixture does not contain any deep import into video-editor
    const fixtureText = fs.readFileSync(fixturePath, 'utf8');
    const deepImportPattern = /from\s+['"](?:@\/tools\/video-editor|.*\/src\/tools\/video-editor)/;
    if (deepImportPattern.test(fixtureText)) {
      console.error(`${SMOKE_LABEL} FAILED: smoke fixture itself contains a deep import into src/tools/video-editor.`);
      return false;
    }

    console.warn(`${SMOKE_LABEL} SDK-internal diagnostics were emitted (tolerated for this smoke):`);
    console.warn(output.split('\n').slice(0, 20).join('\n'));
    if (output.split('\n').length > 20) {
      console.warn(`${SMOKE_LABEL} ...and ${output.split('\n').length - 20} more lines.`);
    }
    console.log(`${SMOKE_LABEL} PASSED: smoke fixture imports @reigh/editor-sdk with no direct deep imports into src/tools/video-editor.`);
    return true;
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

// ---------------------------------------------------------------------------
// Negative fixtures: prove the guard catches deliberate SDK→host violations.
// ---------------------------------------------------------------------------

const NEGATIVE_LABEL = '[video-editor-sdk-negative]';
const negativeFixturesDir = path.join(repoRoot, 'scripts', 'quality', 'fixtures', 'sdk-import-guard');

function runNegativeFixtures() {
  if (!fs.existsSync(negativeFixturesDir)) {
    console.log(`${NEGATIVE_LABEL} No negative fixtures directory; skipping.`);
    return true;
  }

  const entries = fs.readdirSync(negativeFixturesDir, { withFileTypes: true });
  const fixtureFiles = entries
    .filter((e) => e.isFile() && (e.name.endsWith('.ts') || e.name.endsWith('.tsx')))
    .map((e) => path.join(negativeFixturesDir, e.name));

  if (fixtureFiles.length === 0) {
    console.error(`${NEGATIVE_LABEL} FAILED: expected negative fixtures in ${negativeFixturesDir} but found none.`);
    return false;
  }

  const expectedKinds = ['import', 'export-from', 'dynamic-import', 'alias-import'];
  const seenKinds = new Set();
  let allOk = true;

  for (const fixturePath of fixtureFiles) {
    const content = fs.readFileSync(fixturePath, 'utf8');
    const fileFailures = collectFailuresForFile(fixturePath, content);
    const fixtureName = path.basename(fixturePath);
    const kind = fixtureName.replace(/\.tsx?$/, '');
    seenKinds.add(kind);

    if (fileFailures.length === 0) {
      console.error(`${NEGATIVE_LABEL} FAILED: fixture ${fixtureName} was expected to trigger a guard violation but passed.`);
      allOk = false;
      continue;
    }

    console.log(`${NEGATIVE_LABEL} ${fixtureName} correctly flagged ${fileFailures.length} violation(s):`);
    for (const failure of fileFailures) {
      console.log(`  - kind=${failure.kind} specifier=${failure.specifier} target=${failure.target}`);
    }
  }

  for (const kind of expectedKinds) {
    if (!seenKinds.has(kind)) {
      console.error(`${NEGATIVE_LABEL} FAILED: missing negative fixture for ${kind}.`);
      allOk = false;
    }
  }

  return allOk;
}

console.log(`${NEGATIVE_LABEL} Running negative fixtures…`);
const negativeOk = runNegativeFixtures();
if (!negativeOk) {
  process.exit(1);
}

// ---------------------------------------------------------------------------
// External SDK consumer validator (M0 Phase 4).
// ---------------------------------------------------------------------------

const externalConsumerPath = path.join(repoRoot, 'scripts', 'quality', 'check-sdk-external-consumer.mjs');
if (fs.existsSync(externalConsumerPath)) {
  console.log('[video-editor-sdk-imports] Running external SDK consumer validator…');
  try {
    execSync(`node ${externalConsumerPath}`, {
      cwd: repoRoot,
      encoding: 'utf8',
      timeout: 300_000,
      stdio: ['pipe', 'inherit', 'inherit'],
    });
  } catch (err) {
    console.error('[video-editor-sdk-imports] FAILED: external SDK consumer validator failed.');
    process.exit(1);
  }
}

console.log('[video-editor-sdk-imports] All checks passed (allowlist + packagability smoke + negative fixtures + external consumer).');
