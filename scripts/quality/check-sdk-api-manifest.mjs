#!/usr/bin/env node
/**
 * M2a SDK Public API Manifest Auditor
 *
 * Generates and checks a machine-readable manifest of every public export
 * from `src/sdk/index.ts`.  The manifest captures enough detail to detect
 * signature regressions, removed exports, and new exports across releases.
 *
 * Modes:
 *
 *   --write-baseline    Walks the current entrypoint, normalizes every
 *                       exported declaration / re-export, and writes the
 *                       manifest to `config/governance/sdk-public-api-manifest.json`.
 *                       Existing content is replaced.
 *
 *   (default) check     Walks the current entrypoint, generates a fresh
 *                       manifest in memory, and diffs it against the
 *                       committed baseline manifest plus the approvals
 *                       file.  Reports any unapproved additions, removals,
 *                       or signature changes.
 *
 * Approval file:
 *   `config/governance/sdk-public-api-approvals.json`
 *   A human-edited file that signs off on intentional API changes so the
 *   check mode doesn't fail on planned evolution.  Entries are keyed by
 *   export name and include an `approvedDeclarationHash` and justification.
 *
 * Manifest schema (per entry):
 *   - name                    Export name
 *   - kind                    Declaration kind (type | interface | function |
 *                             const | class | enum | reexport-value |
 *                             reexport-type)
 *   - source                  Module specifier (null for inline declarations)
 *   - declarationHash         SHA-256 of normalized declaration text
 *   - namespace               'type' | 'value' | 'both'
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import ts from 'typescript';

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const args = new Set(process.argv.slice(2));

let mode = 'check';
if (args.has('--write-baseline')) {
  mode = 'write-baseline';
} else if (args.has('--check')) {
  mode = 'check';
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LABEL = '[sdk-api-manifest]';
const REPO_ROOT = process.cwd();
const SDK_ENTRY = path.join(REPO_ROOT, 'src', 'sdk', 'index.ts');
const MANIFEST_PATH = path.join(
  REPO_ROOT,
  'config',
  'governance',
  'sdk-public-api-manifest.json',
);
const APPROVALS_PATH = path.join(
  REPO_ROOT,
  'config',
  'governance',
  'sdk-public-api-approvals.json',
);

// ---------------------------------------------------------------------------
// Helpers: path resolution
// ---------------------------------------------------------------------------

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

function resolveSpecifier(specifier, fromDir) {
  if (specifier.startsWith('.')) {
    const resolved = resolveCandidate(
      path.resolve(fromDir, specifier),
    );
    return resolved;
  }

  if (specifier.startsWith('@/') || specifier.startsWith('@reigh/')) {
    let mapped = specifier;
    if (specifier.startsWith('@/')) {
      mapped = path.join('src', specifier.slice(2));
    } else if (specifier === '@reigh/editor-sdk') {
      mapped = path.join('src', 'sdk', 'index.ts');
    }
    const resolved = resolveCandidate(path.join(REPO_ROOT, mapped));
    return resolved;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Helpers: TypeScript AST
// ---------------------------------------------------------------------------

function hasExportModifier(node) {
  if (!node.modifiers) return false;
  return node.modifiers.some(
    (m) => m.kind === ts.SyntaxKind.ExportKeyword,
  );
}

/**
 * Normalize declaration text: strip comments and collapse whitespace.
 */
function normalizeDeclarationText(sourceText, node) {
  // Get the raw text for the node
  const raw = sourceText.slice(node.pos, node.end).trim();

  // Remove single-line comments
  let cleaned = raw.replace(/\/\/.*$/gm, '');
  // Remove multi-line comments
  cleaned = cleaned.replace(/\/\*[\s\S]*?\*\//g, '');
  // Collapse whitespace
  cleaned = cleaned.replace(/\s+/g, ' ').trim();

  return cleaned;
}

function sha256(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

/**
 * Determine the TypeScript namespace(s) an export belongs to.
 * Returns 'type', 'value', or 'both'.
 */
function determineNamespace(kind) {
  // Inline declarations
  switch (kind) {
    case 'type':
    case 'interface':
      return 'type';
    case 'function':
    case 'const':
    case 'var':
    case 'let':
    case 'class':
      return 'value';
    case 'enum':
      return 'both';
    // Re-exports
    case 'reexport-value':
      return 'value';
    case 'reexport-type':
      return 'type';
    default:
      return 'value';
  }
}

// ---------------------------------------------------------------------------
// Walk exports
// ---------------------------------------------------------------------------

function walkExports(sourceFile) {
  const sourceText = sourceFile.text;
  /** @type {Array<{ name: string, kind: string, source: string | null, declarationHash: string, declarationText: string, namespace: string }>} */
  const exports = [];

  ts.forEachChild(sourceFile, function visit(node) {
    // ---- Inline declared exports ----

    if (ts.isTypeAliasDeclaration(node) && hasExportModifier(node)) {
      const text = normalizeDeclarationText(sourceText, node);
      const kind = 'type';
      exports.push({
        name: node.name.text,
        kind,
        source: null,
        declarationHash: sha256(text),
        declarationText: text,
        namespace: determineNamespace(kind),
      });
    } else if (ts.isInterfaceDeclaration(node) && hasExportModifier(node)) {
      const text = normalizeDeclarationText(sourceText, node);
      const kind = 'interface';
      exports.push({
        name: node.name.text,
        kind,
        source: null,
        declarationHash: sha256(text),
        declarationText: text,
        namespace: determineNamespace(kind),
      });
    } else if (
      ts.isFunctionDeclaration(node) &&
      hasExportModifier(node) &&
      node.name
    ) {
      const text = normalizeDeclarationText(sourceText, node);
      const kind = 'function';
      exports.push({
        name: node.name.text,
        kind,
        source: null,
        declarationHash: sha256(text),
        declarationText: text,
        namespace: determineNamespace(kind),
      });
    } else if (ts.isVariableStatement(node) && hasExportModifier(node)) {
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) {
          // For const declarations, capture only the specific declaration
          const declText = normalizeDeclarationText(sourceText, decl);
          const fullText = normalizeDeclarationText(sourceText, node);
          const kind = 'const';
          exports.push({
            name: decl.name.text,
            kind,
            source: null,
            declarationHash: sha256(fullText),
            declarationText: fullText,
            namespace: determineNamespace(kind),
          });
        }
      }
    } else if (
      ts.isClassDeclaration(node) &&
      hasExportModifier(node) &&
      node.name
    ) {
      const text = normalizeDeclarationText(sourceText, node);
      const kind = 'class';
      exports.push({
        name: node.name.text,
        kind,
        source: null,
        declarationHash: sha256(text),
        declarationText: text,
        namespace: determineNamespace(kind),
      });
    } else if (ts.isEnumDeclaration(node) && hasExportModifier(node)) {
      const text = normalizeDeclarationText(sourceText, node);
      const kind = 'enum';
      exports.push({
        name: node.name.text,
        kind,
        source: null,
        declarationHash: sha256(text),
        declarationText: text,
        namespace: determineNamespace(kind),
      });
    }

    // ---- Re-exports ----
    if (ts.isExportDeclaration(node)) {
      const isTypeOnly = node.isTypeOnly;
      const clause = node.exportClause;
      const moduleSpecifier = node.moduleSpecifier;

      if (clause && ts.isNamedExports(clause)) {
        for (const element of clause.elements) {
          const name = element.name.text;
          if (moduleSpecifier && ts.isStringLiteral(moduleSpecifier)) {
            const specifier = moduleSpecifier.text;
            const resolved = resolveSpecifier(
              specifier,
              path.dirname(sourceFile.fileName),
            );
            // Store the module specifier as-written (portable).
            const source = specifier;
            const kind = isTypeOnly ? 'reexport-type' : 'reexport-value';

            // For re-exports, the "declaration text" is the re-export statement
            const reexportText = `export${isTypeOnly ? ' type' : ''} { ${name} } from '${specifier}';`;
            exports.push({
              name,
              kind,
              source,
              declarationHash: sha256(reexportText),
              declarationText: reexportText,
              namespace: determineNamespace(kind),
            });
          } else {
            // Re-exports of imported bindings (no module specifier)
            const kind = isTypeOnly ? 'reexport-type' : 'reexport-value';
            exports.push({
              name,
              kind,
              source: null,
              declarationHash: sha256(`export { ${name} };`),
              declarationText: `export { ${name} };`,
              namespace: determineNamespace(kind),
            });
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  });

  return exports;
}

// ---------------------------------------------------------------------------
// Main: create TypeScript program and walk
// ---------------------------------------------------------------------------

function buildProgram() {
  const sourceText = fs.readFileSync(SDK_ENTRY, 'utf8');

  const compilerOptions = {
    target: ts.ScriptTarget.ESNext,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    baseUrl: REPO_ROOT,
    paths: {
      '@/*': ['./src/*'],
      '@reigh/editor-sdk': ['./src/sdk/index.ts'],
    },
    skipLibCheck: true,
  };

  const host = ts.createCompilerHost(compilerOptions);
  const originalGetSourceFile = host.getSourceFile.bind(host);
  host.getSourceFile = (fileName, languageVersion) => {
    if (fileName === SDK_ENTRY) {
      return ts.createSourceFile(fileName, sourceText, languageVersion, true);
    }
    return originalGetSourceFile(fileName, languageVersion);
  };

  const program = ts.createProgram({
    rootNames: [SDK_ENTRY],
    options: compilerOptions,
    host,
  });

  const sourceFile = program.getSourceFile(SDK_ENTRY);
  return { sourceFile, sourceText, program };
}

function generateManifest() {
  if (!fs.existsSync(SDK_ENTRY)) {
    console.error(`${LABEL} SDK entrypoint not found: ${SDK_ENTRY}`);
    process.exit(1);
  }

  const { sourceFile } = buildProgram();
  if (!sourceFile) {
    console.error(`${LABEL} Failed to parse SDK entrypoint as TypeScript.`);
    process.exit(1);
  }

  const exports = walkExports(sourceFile);

  // Build manifest with metadata
  const manifest = {
    $schema: '../../config/schemas/sdk-public-api-manifest.schema.json',
    description:
      'Machine-readable manifest of every public export from @reigh/editor-sdk. ' +
      'Generated by scripts/quality/check-sdk-api-manifest.mjs --write-baseline. ' +
      'Used by the check mode to detect unapproved additions, removals, and signature changes.',
    generatedAt: new Date().toISOString(),
    generatedFrom: path.relative(REPO_ROOT, SDK_ENTRY),
    exportCount: exports.length,
    exports,
  };

  return manifest;
}

// ---------------------------------------------------------------------------
// Write baseline mode
// ---------------------------------------------------------------------------

function writeBaseline() {
  const manifest = generateManifest();

  fs.mkdirSync(path.dirname(MANIFEST_PATH), { recursive: true });
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  console.log(
    `${LABEL} Baseline written: ${path.relative(REPO_ROOT, MANIFEST_PATH)}`,
  );
  console.log(`${LABEL} ${manifest.exportCount} export(s) captured.`);
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Check mode
// ---------------------------------------------------------------------------

function loadBaselineManifest() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    console.error(
      `${LABEL} Baseline manifest not found: ${path.relative(REPO_ROOT, MANIFEST_PATH)}`,
    );
    console.error(
      `${LABEL} Run with --write-baseline to generate the initial manifest.`,
    );
    process.exit(1);
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  } catch (err) {
    console.error(`${LABEL} Baseline manifest is not valid JSON: ${err.message}`);
    process.exit(1);
  }

  if (!Array.isArray(raw.exports)) {
    console.error(`${LABEL} Baseline manifest is missing the 'exports' array.`);
    process.exit(1);
  }

  return raw;
}

function loadApprovals() {
  if (!fs.existsSync(APPROVALS_PATH)) {
    // No approvals file — treat as empty
    return { approvedChanges: {} };
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(APPROVALS_PATH, 'utf8'));
  } catch (err) {
    console.error(`${LABEL} Approvals file is not valid JSON: ${err.message}`);
    process.exit(1);
  }

  if (typeof raw.approvedChanges !== 'object' || raw.approvedChanges === null) {
    console.error(
      `${LABEL} Approvals file is missing the 'approvedChanges' object.`,
    );
    process.exit(1);
  }

  return raw;
}

function checkManifest() {
  const current = generateManifest();
  const baseline = loadBaselineManifest();
  const approvals = loadApprovals();

  // Build lookup maps
  const baselineMap = new Map();
  for (const entry of baseline.exports) {
    baselineMap.set(entry.name, entry);
  }

  const currentMap = new Map();
  for (const entry of current.exports) {
    currentMap.set(entry.name, entry);
  }

  const approvedMap = new Map();
  for (const [name, approval] of Object.entries(approvals.approvedChanges)) {
    approvedMap.set(name, approval);
  }

  // ---- Detect differences ----

  /** @type {Array<{ name: string, issue: string, detail: string }>} */
  const issues = [];

  // 1. New exports (in current but not baseline)
  for (const [name, entry] of currentMap) {
    if (!baselineMap.has(name)) {
      const approval = approvedMap.get(name);
      if (
        approval &&
        approval.approvedDeclarationHash === entry.declarationHash
      ) {
        // Approved addition
        continue;
      }
      issues.push({
        name,
        issue: 'new-export',
        detail: `Export '${name}' (${entry.kind}, ${entry.namespace}) is present but not in the baseline manifest.`,
      });
    }
  }

  // 2. Removed exports (in baseline but not current)
  for (const [name, entry] of baselineMap) {
    if (!currentMap.has(name)) {
      const approval = approvedMap.get(name);
      if (approval && approval.action === 'remove') {
        // Approved removal
        continue;
      }
      issues.push({
        name,
        issue: 'removed-export',
        detail: `Export '${name}' (${entry.kind}, ${entry.namespace}) was in the baseline but is no longer exported.`,
      });
    }
  }

  // 3. Changed exports (same name, different hash)
  for (const [name, currentEntry] of currentMap) {
    const baselineEntry = baselineMap.get(name);
    if (!baselineEntry) continue;

    if (currentEntry.declarationHash !== baselineEntry.declarationHash) {
      const approval = approvedMap.get(name);
      if (
        approval &&
        approval.approvedDeclarationHash === currentEntry.declarationHash
      ) {
        // Approved change
        continue;
      }
      issues.push({
        name,
        issue: 'signature-changed',
        detail: `Export '${name}' (${currentEntry.kind}) signature has changed.\n` +
          `  Baseline hash: ${baselineEntry.declarationHash}\n` +
          `  Current hash:  ${currentEntry.declarationHash}`,
      });
    }
  }

  // ---- Report ----

  if (issues.length === 0) {
    console.log(
      `${LABEL} CHECK PASSED. ${current.exportCount} export(s) match the baseline manifest.`,
    );
    process.exit(0);
  }

  const newExports = issues.filter((i) => i.issue === 'new-export');
  const removedExports = issues.filter((i) => i.issue === 'removed-export');
  const changedExports = issues.filter((i) => i.issue === 'signature-changed');

  console.error(
    `${LABEL} CHECK FAILED: ${issues.length} issue(s) detected.`,
  );
  if (newExports.length > 0) {
    console.error(
      `${LABEL}   ${newExports.length} new export(s):`,
    );
    for (const issue of newExports) {
      console.error(`${LABEL}     - ${issue.detail}`);
    }
  }
  if (removedExports.length > 0) {
    console.error(
      `${LABEL}   ${removedExports.length} removed export(s):`,
    );
    for (const issue of removedExports) {
      console.error(`${LABEL}     - ${issue.detail}`);
    }
  }
  if (changedExports.length > 0) {
    console.error(
      `${LABEL}   ${changedExports.length} changed export(s):`,
    );
    for (const issue of changedExports) {
      console.error(`${LABEL}     - ${issue.detail}`);
    }
  }

  console.error(
    `${LABEL} To approve these changes, update ${path.relative(REPO_ROOT, APPROVALS_PATH)} ` +
      `with entries keyed by export name, each containing 'approvedDeclarationHash' ` +
      `and 'justification'. Or run --write-baseline to accept all changes.`,
  );

  process.exit(1);
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);
console.log(`${LABEL} Entrypoint: ${path.relative(REPO_ROOT, SDK_ENTRY)}`);

if (mode === 'write-baseline') {
  writeBaseline();
} else {
  checkManifest();
}
