#!/usr/bin/env node

/**
 * External SDK consumer validator.
 *
 * M0 boundary proof: an out-of-repo package that imports @reigh/editor-sdk
 * must type-check with zero diagnostics from SDK files, must not resolve any
 * dependency into src/tools/video-editor, and must be able to evaluate the SDK
 * value exports in a plain Node context.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { execSync } from 'node:child_process';
import os from 'node:os';

let ts;
try {
  ({ default: ts } = await import('typescript'));
} catch (error) {
  const reason = error instanceof Error ? error.message : String(error);
  fail(`TypeScript tooling is unavailable: ${reason}`);
}

const repoRoot = process.cwd();
const tscPath = path.join(repoRoot, 'node_modules', '.bin', 'tsc');
const tsxPath = path.join(repoRoot, 'node_modules', '.bin', 'tsx');
const sdkSourceDir = path.join(repoRoot, 'src', 'sdk');
const videoEditorDir = path.join(repoRoot, 'src', 'tools', 'video-editor') + path.sep;
const label = '[sdk-external-consumer]';

function fail(message) {
  console.error(`${label} ${message}`);
  process.exit(1);
}

if (!fs.existsSync(tscPath)) {
  fail(`TypeScript CLI is unavailable: missing ${path.relative(repoRoot, tscPath)}`);
}

// ---------------------------------------------------------------------------
// 1. Build a package-like copy of the SDK with internal aliases rewritten.
// ---------------------------------------------------------------------------

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'reigh-sdk-consumer-'));
const packageDir = path.join(tmpDir, 'sdk-package');
const consumerDir = path.join(tmpDir, 'consumer');
const consumerNodeModules = path.join(consumerDir, 'node_modules');

fs.mkdirSync(packageDir, { recursive: true });
fs.mkdirSync(consumerDir, { recursive: true });

function copySdk(dir, rel = '') {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const srcPath = path.join(dir, entry.name);
    const destRel = path.join(rel, entry.name);
    const destPath = path.join(packageDir, destRel);

    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'smoke') {
        continue;
      }
      fs.mkdirSync(destPath, { recursive: true });
      copySdk(srcPath, destRel);
      continue;
    }

    if (!entry.name.endsWith('.ts') || entry.name.endsWith('.test.ts')) {
      continue;
    }

    let content = fs.readFileSync(srcPath, 'utf8');

    // Rewrite @/sdk/* specifiers to relative paths inside the package.
    function rewriteSdkSpecifier(match, quote, specifier) {
      const targetInPackage = path.join(packageDir, specifier.replace('@/sdk/', ''));
      const importerDir = path.dirname(path.join(packageDir, destRel));
      let relative = path.relative(importerDir, targetInPackage);
      if (!relative.startsWith('.')) {
        relative = `./${relative}`;
      }
      return `${match.startsWith('import(') ? 'import(' : 'from '}${quote}${relative.replace(/\\/g, '/')}${quote}`;
    }

    content = content.replace(
      /from\s+(['"])(@\/sdk\/[^'"]+)\1/g,
      (m, quote, spec) => rewriteSdkSpecifier(m, quote, spec),
    );
    content = content.replace(
      /import\s*\(\s*(['"])(@\/sdk\/[^'"]+)\1\s*\)/g,
      (m, quote, spec) => rewriteSdkSpecifier(m, quote, spec),
    );

    fs.writeFileSync(destPath, content, 'utf8');
  }
}

copySdk(sdkSourceDir);

fs.writeFileSync(
  path.join(packageDir, 'package.json'),
  JSON.stringify(
    {
      name: '@reigh/editor-sdk',
      version: '0.0.0-smoke',
      type: 'module',
      main: 'index.ts',
      types: 'index.ts',
    },
    null,
    2,
  ),
  'utf8',
);

// ---------------------------------------------------------------------------
// 2. Create a minimal external consumer.
// ---------------------------------------------------------------------------

const consumerFixturePath = path.join(consumerDir, 'smoke.ts');
const directFixturePath = path.join(consumerDir, 'direct-modules.ts');

const consumerFixture = `/**
 * External SDK consumer smoke fixture.
 * Imports the public package surface only — no repo aliases, no Vite context.
 */
import * as sdk from '@reigh/editor-sdk';

// Reference the namespace so the import is not tree-shaken away.
const keys: string[] = Object.keys(sdk);
console.log('[sdk-consumer-runtime] exported keys:', keys.length);
`;

const directFixture = `/**
 * External SDK direct-module smoke fixture.
 * Pulls representative direct modules from core and video families to prove
 * they are individually importable outside the repo.
 */
import { FamilyAdapterRegistryImpl } from '@reigh/editor-sdk/core/families/familyAdapter';
import { normalizeAdapters } from '@reigh/editor-sdk/core/families/familyAdapterCoordinator';
import { createDiagnosticCollection } from '@reigh/editor-sdk';
import type { EffectContribution } from '@reigh/editor-sdk/video/families/effects';
import { KNOWN_CONTRIBUTION_KINDS } from '@reigh/editor-sdk';

const registry = new FamilyAdapterRegistryImpl();
void normalizeAdapters;
void createDiagnosticCollection;
void KNOWN_CONTRIBUTION_KINDS;
void ({} as EffectContribution);
console.log('[sdk-consumer-runtime-direct] registry size:', registry.snapshot().size);
`;

fs.writeFileSync(consumerFixturePath, consumerFixture, 'utf8');
fs.writeFileSync(directFixturePath, directFixture, 'utf8');

fs.writeFileSync(
  path.join(consumerDir, 'package.json'),
  JSON.stringify(
    {
      name: 'reigh-sdk-external-consumer',
      version: '0.0.0',
      type: 'module',
      dependencies: {
        '@reigh/editor-sdk': 'file:../sdk-package',
      },
    },
    null,
    2,
  ),
  'utf8',
);

fs.writeFileSync(
  path.join(consumerDir, 'tsconfig.json'),
  JSON.stringify(
    {
      compilerOptions: {
        target: 'ESNext',
        module: 'ESNext',
        moduleResolution: 'bundler',
        baseUrl: '.',
        paths: {
          '@reigh/editor-sdk': ['../sdk-package/index.ts'],
          '@reigh/editor-sdk/*': ['../sdk-package/*.ts'],
        },
        strict: true,
        noEmit: true,
        skipLibCheck: true,
        allowImportingTsExtensions: true,
        isolatedModules: true,
        esModuleInterop: true,
      },
      include: ['smoke.ts', 'direct-modules.ts', '../sdk-package/**/*.ts'],
    },
    null,
    2,
  ),
  'utf8',
);

// Re-use the repo's node_modules so third-party types (ajv, etc.) resolve.
const repoNodeModules = path.join(repoRoot, 'node_modules');
try {
  fs.symlinkSync(repoNodeModules, consumerNodeModules);
  fs.symlinkSync(repoNodeModules, path.join(packageDir, 'node_modules'));
} catch (error) {
  // If symlink fails (e.g. Windows without privileges), copy is too expensive;
  // fail fast and ask the operator to run on a POSIX-ish environment.
  fail(`Unable to symlink repo node_modules into consumer temp dir: ${error instanceof Error ? error.message : error}`);
}

// ---------------------------------------------------------------------------
// 3. Type-check the consumer and fail on any diagnostic from SDK files.
// ---------------------------------------------------------------------------

console.log(`${label} Type-checking external consumer against copied SDK…`);

let tscOutput = '';
let tscOk = false;
try {
  tscOutput = execSync(`${tscPath} -p ${path.join(consumerDir, 'tsconfig.json')} --noEmit`, {
    cwd: consumerDir,
    encoding: 'utf8',
    timeout: 120_000,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  tscOk = true;
} catch (err) {
  tscOutput = String(err.stdout || err.stderr || err.message || '');
}

if (!tscOk) {
  console.error(`${label} FAILED: external consumer type-check failed.`);
  console.error(tscOutput);
  cleanup();
  process.exit(1);
}

// tsc succeeded overall; now verify no diagnostic originated from SDK package files.
const sdkPackagePrefix = path.normalize(`${packageDir}${path.sep}`);
const sdkDiagnosticPattern = new RegExp(
  `^${escapeRegex(sdkPackagePrefix)}[^()]+\\(\\d+,\\d+\\):\\s*error`,
  'm',
);

if (sdkDiagnosticPattern.test(tscOutput)) {
  console.error(`${label} FAILED: diagnostics were emitted from SDK source files.`);
  console.error(tscOutput);
  cleanup();
  process.exit(1);
}

console.log(`${label} PASSED: external consumer type-checks with no SDK-source diagnostics.`);

// ---------------------------------------------------------------------------
// 4. Static import-graph assertion: no resolved module under src/tools/video-editor.
// ---------------------------------------------------------------------------

console.log(`${label} Checking import graph for host-internal resolutions…`);

const compilerOptions = parseConsumerTsconfig();
const graphFailures = [];
const visited = new Set();
const queue = [consumerFixturePath, directFixturePath];

function parseConsumerTsconfig() {
  const configPath = path.join(consumerDir, 'tsconfig.json');
  const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
  if (configFile.error) {
    fail(formatTsDiagnostic(configFile.error));
  }
  const parsed = ts.parseJsonConfigFileContent(
    configFile.config,
    ts.sys,
    path.dirname(configPath),
  );
  if (parsed.errors.length > 0) {
    fail(parsed.errors.map(formatTsDiagnostic).join('\n'));
  }
  return parsed.options;
}

function formatTsDiagnostic(diagnostic) {
  return ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
}

function collectSpecifiers(filePath, content) {
  const specifiers = [];
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
      specifiers.push(node.moduleSpecifier.text);
    } else if (
      ts.isExportDeclaration(node)
      && node.moduleSpecifier
      && ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specifiers.push(node.moduleSpecifier.text);
    } else if (
      ts.isCallExpression(node)
      && node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      const [firstArg] = node.arguments;
      if (firstArg && (ts.isStringLiteral(firstArg) || ts.isNoSubstitutionTemplateLiteral(firstArg))) {
        specifiers.push(firstArg.text);
      }
    }
    ts.forEachChild(node, visit);
  });
  return specifiers;
}

while (queue.length > 0) {
  const current = queue.shift();
  if (visited.has(current)) {
    continue;
  }
  visited.add(current);

  if (!fs.existsSync(current)) {
    continue;
  }

  const content = fs.readFileSync(current, 'utf8');
  for (const specifier of collectSpecifiers(current, content)) {
    const { resolvedModule } = ts.resolveModuleName(
      specifier,
      current,
      compilerOptions,
      ts.sys,
    );
    if (!resolvedModule?.resolvedFileName) {
      continue;
    }
    const resolved = path.resolve(resolvedModule.resolvedFileName);
    if (resolved.startsWith(videoEditorDir)) {
      graphFailures.push({ importer: current, specifier, resolved });
    } else if (resolved.startsWith(sdkPackagePrefix) && !visited.has(resolved)) {
      queue.push(resolved);
    }
  }
}

if (graphFailures.length > 0) {
  console.error(`${label} FAILED: import graph resolves into src/tools/video-editor:`);
  for (const failure of graphFailures) {
    console.error(`  - ${path.relative(tmpDir, failure.importer)} -> ${failure.specifier}`);
    console.error(`      resolved: ${failure.resolved}`);
  }
  cleanup();
  process.exit(1);
}

console.log(`${label} PASSED: import graph contains no src/tools/video-editor resolutions.`);

// ---------------------------------------------------------------------------
// 5. Runtime value smoke: evaluate the SDK package in Node.
// ---------------------------------------------------------------------------

console.log(`${label} Running runtime value smoke in Node…`);

if (!fs.existsSync(tsxPath)) {
  fail(`tsx is unavailable: missing ${path.relative(repoRoot, tsxPath)}`);
}

function runRuntimeSmoke(fixturePath) {
  const name = path.basename(fixturePath);
  let runtimeOutput = '';
  let runtimeOk = false;
  try {
    runtimeOutput = execSync(`${tsxPath} ${fixturePath}`, {
      cwd: consumerDir,
      encoding: 'utf8',
      timeout: 60_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    runtimeOk = true;
  } catch (err) {
    runtimeOutput = String(err.stdout || err.stderr || err.message || '');
  }

  if (!runtimeOk) {
    console.error(`${label} FAILED: runtime smoke "${name}" threw an error while loading the SDK package.`);
    console.error(runtimeOutput);
    return false;
  }

  console.log(`${label} PASSED: runtime smoke "${name}" evaluated in Node without a top-level load error.`);

  const keyCountMatch = runtimeOutput.match(/exported keys:\s*(\d+)/);
  if (keyCountMatch) {
    console.log(`${label} Runtime reported ${keyCountMatch[1]} top-level exported bindings.`);
  }

  if (runtimeOutput.trim()) {
    console.log(`${label} Runtime output:\n${runtimeOutput.split('\n').map((l) => `  ${l}`).join('\n')}`);
  }

  return true;
}

if (!runRuntimeSmoke(consumerFixturePath) || !runRuntimeSmoke(directFixturePath)) {
  cleanup();
  process.exit(1);
}

console.log(`${label} All external-consumer checks passed.`);
cleanup();
process.exit(0);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function cleanup() {
  try {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  } catch {
    // Best effort.
  }
}
