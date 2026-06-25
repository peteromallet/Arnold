#!/usr/bin/env node

/**
 * M2a — SDK-Internal No-Barrel-Import Gate
 *
 * Scans non-test source files under `src/sdk/**` and flags any import that
 * resolves to the public SDK barrel (`src/sdk/index.ts`).  SDK-internal
 * modules must import canonical sources directly rather than reaching through
 * the public entrypoint.
 *
 * Supports two modes:
 *
 *   --audit     (default)  Reports violations as warnings.  Exit zero even
 *                          when violations exist.  The gate will switch to
 *                          enforcement in Step 14.
 *
 *   --release              Full enforcement: any barrel import from an
 *                          SDK-internal source file causes a hard failure.
 *
 * Barrel paths that resolve to `src/sdk/index.ts`:
 *   - `@/sdk` / `@/sdk/index`
 *   - `@reigh/editor-sdk`
 *   - Any relative path that resolves to `src/sdk/index.ts` (e.g. `./index`
 *     from files directly in `src/sdk/`, `../../index` from deeper modules)
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

let ts;
try {
  ({ default: ts } = await import('typescript'));
} catch (error) {
  const reason = error instanceof Error ? error.message : String(error);
  console.error('[sdk-no-barrel-imports] TypeScript tooling is unavailable:', reason);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const args = new Set(process.argv.slice(2));

/** @type {'audit' | 'release'} */
let mode = 'audit';
if (args.has('--release')) {
  mode = 'release';
} else if (args.has('--audit')) {
  mode = 'audit';
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LABEL = '[sdk-no-barrel-imports]';
const REPO_ROOT = process.cwd();
const SDK_DIR = path.join(REPO_ROOT, 'src', 'sdk');
const SDK_BARREL = path.join(SDK_DIR, 'index.ts');
const TSCONFIG_PATH = path.join(REPO_ROOT, 'tsconfig.json');

// ---------------------------------------------------------------------------
// Barrel-import exception list
//
// Some SDK-internal files legitimately import from the public barrel because
// the types they consume are M2b family inline declarations that have not yet
// been extracted to canonical modules.  Each entry records the importer
// (relative to repo root), the barrel specifier, the imported names, and a
// justification tracing the dependency to its eventual canonical home.
// ---------------------------------------------------------------------------

/**
 * @typedef {{ importer: string, specifier: string, names: string[], justification: string, expires: string }} BarrelImportException
 */

/** @type {BarrelImportException[]} */
const BARREL_IMPORT_EXCEPTIONS = [
  {
    importer: 'src/sdk/video/timeline/reader.ts',
    specifier: '@/sdk/index',
    names: [
      'ProjectExtensionRequirement',
      'SourceMapEntry',
      'GeneratedObjectMeta',
    ],
    justification:
      'M2b family inline declarations (project extension requirements / ' +
      'source-map / generated-object contracts).  These types are still inline ' +
      'in src/sdk/index.ts pending M2b extraction to a canonical module.',
    expires: 'M2b',
  },
];

// Build a lookup: Map<importer, Set<specifier>>
const exceptionMap = new Map();
for (const exc of BARREL_IMPORT_EXCEPTIONS) {
  const key = path.resolve(REPO_ROOT, exc.importer);
  const specs = exceptionMap.get(key) ?? new Set();
  specs.add(exc.specifier);
  exceptionMap.set(key, specs);
}

// ---------------------------------------------------------------------------
// Helpers: file discovery
// ---------------------------------------------------------------------------

/**
 * Recursively collect .ts / .tsx files inside a directory, skipping:
 *   - node_modules
 *   - __tests__ directories
 *   - *.test.ts / *.test.tsx files
 *   - The barrel entrypoint itself (src/sdk/index.ts)
 */
function collectNonTestSourceFiles(dir) {
  /** @type {string[]} */
  const results = [];

  if (!fs.existsSync(dir)) {
    return results;
  }

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);

    if (entry.name === 'node_modules') continue;

    if (entry.isDirectory()) {
      if (entry.name === '__tests__') continue;
      results.push(...collectNonTestSourceFiles(fullPath));
      continue;
    }

    if (!entry.isFile()) continue;
    if (!fullPath.endsWith('.ts') && !fullPath.endsWith('.tsx')) continue;
    if (fullPath.endsWith('.test.ts') || fullPath.endsWith('.test.tsx')) continue;
    if (path.resolve(fullPath) === path.resolve(SDK_BARREL)) continue;

    results.push(fullPath);
  }

  return results;
}

// ---------------------------------------------------------------------------
// TypeScript resolution helpers
// ---------------------------------------------------------------------------

/**
 * Parse tsconfig.json and return compiler options for module resolution.
 */
function parseTsconfigOptions() {
  const configFile = ts.readConfigFile(TSCONFIG_PATH, ts.sys.readFile);
  if (configFile.error) {
    throw new Error(
      `Failed to read tsconfig: ${ts.flattenDiagnosticMessageText(configFile.error.messageText, '\n')}`,
    );
  }
  const parsed = ts.parseJsonConfigFileContent(
    configFile.config,
    ts.sys,
    path.dirname(TSCONFIG_PATH),
  );
  if (parsed.errors.length > 0) {
    throw new Error(
      parsed.errors.map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('\n'),
    );
  }
  return parsed.options;
}

// ---------------------------------------------------------------------------
// AST import-gathering
// ---------------------------------------------------------------------------

/**
 * Extract import / export-from / dynamic-import specifiers from a source file
 * using the TypeScript AST.
 *
 * @param {string} filePath
 * @param {string} content
 * @returns {Array<{ specifier: string, kind: 'import' | 'export-from' | 'dynamic-import', line: number }>}
 */
function extractImportRecords(filePath, content) {
  /** @type {Array<{ specifier: string, kind: 'import' | 'export-from' | 'dynamic-import', line: number }>} */
  const records = [];
  const seen = new Set();

  const sourceFile = ts.createSourceFile(
    filePath,
    content,
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  function getLine(pos) {
    return sourceFile.getLineAndCharacterOfPosition(pos).line + 1;
  }

  ts.forEachChild(sourceFile, function visit(node) {
    // import { X } from 'specifier'
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
          line: getLine(node.getStart()),
        });
      }
    }

    // export { X } from 'specifier'
    if (
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
          line: getLine(node.getStart()),
        });
      }
    }

    // import('specifier')
    if (
      ts.isCallExpression(node)
      && node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      const [firstArg] = node.arguments;
      if (
        firstArg
        && (ts.isStringLiteral(firstArg) || ts.isNoSubstitutionTemplateLiteral(firstArg))
      ) {
        const key = `dynamic-import:${firstArg.text}`;
        if (!seen.has(key)) {
          seen.add(key);
          records.push({
            specifier: firstArg.text,
            kind: 'dynamic-import',
            line: getLine(node.getStart()),
          });
        }
      }
    }

    ts.forEachChild(node, visit);
  });

  return records;
}

// ---------------------------------------------------------------------------
// Barrel-resolution check
// ---------------------------------------------------------------------------

/**
 * Given a resolved absolute file path, determine whether it is the public
 * SDK barrel (`src/sdk/index.ts`).
 */
function isSdkBarrel(resolvedPath) {
  if (!resolvedPath) return false;
  return path.resolve(resolvedPath) === path.resolve(SDK_BARREL);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);
console.log(`${LABEL} SDK barrel: ${path.relative(REPO_ROOT, SDK_BARREL)}`);
console.log(`${LABEL} Scanning SDK-internal source files under ${path.relative(REPO_ROOT, SDK_DIR)}/`);

if (mode === 'audit') {
  console.log(`${LABEL} NOTE: Audit mode active — violations are warnings only.`);
  console.log(`${LABEL}       Use --release for strict enforcement (planned for Step 14).`);
}

// ---- Collect source files ----
const sourceFiles = collectNonTestSourceFiles(SDK_DIR);
console.log(`${LABEL} Found ${sourceFiles.length} non-test SDK source file(s).`);

// ---- Parse tsconfig for resolution ----
let compilerOptions;
try {
  compilerOptions = parseTsconfigOptions();
} catch (err) {
  console.error(`${LABEL} Failed to parse tsconfig: ${err.message}`);
  process.exit(1);
}

// ---- Scan each file ----
/** @type {Array<{ importer: string, specifier: string, kind: string, line: number, resolved: string }>} */
const violations = [];

for (const filePath of sourceFiles) {
  const content = fs.readFileSync(filePath, 'utf8');
  const records = extractImportRecords(filePath, content);

  for (const record of records) {
    const { resolvedModule } = ts.resolveModuleName(
      record.specifier,
      filePath,
      compilerOptions,
      ts.sys,
    );

    if (!resolvedModule?.resolvedFileName) {
      continue;
    }

    const resolved = path.resolve(resolvedModule.resolvedFileName);

    if (isSdkBarrel(resolved)) {
      // Check exception list: skip if this importer+specifier is allowed
      const resolvedImporter = path.resolve(filePath);
      const allowedSpecs = exceptionMap.get(resolvedImporter);
      if (allowedSpecs && allowedSpecs.has(record.specifier)) {
        continue;
      }

      violations.push({
        importer: path.relative(REPO_ROOT, filePath),
        specifier: record.specifier,
        kind: record.kind,
        line: record.line,
        resolved: path.relative(REPO_ROOT, resolved),
      });
    }
  }
}

// ---- Report ----
if (violations.length > 0) {
  const header = mode === 'release' ? 'RELEASE FAILURE:' : 'WARNING:';
  console.error(
    `${LABEL} ${header} ${violations.length} barrel import(s) detected from SDK-internal source file(s):`,
  );

  for (const v of violations) {
    console.error(
      `${LABEL}   ${v.importer}:${v.line} — ${v.kind} '${v.specifier}' → ${v.resolved}`,
    );
  }

  console.error(
    `${LABEL} SDK-internal modules must import canonical sources directly,`,
    `${LABEL} not through the public barrel. Replace barrel imports with`,
    `${LABEL} direct imports from the defining module.`,
  );
} else {
  console.log(`${LABEL} No barrel imports found in SDK-internal source files.`);
}

// ---- Exit decision ----
// In audit mode: warn but always exit 0 (explicit until Step 14).
// In release mode: exit non-zero on violations.
if (mode === 'release' && violations.length > 0) {
  console.error(
    `${LABEL} RELEASE FAILED: ${violations.length} SDK-internal barrel import(s) must be resolved.`,
  );
  process.exit(1);
}

if (violations.length > 0) {
  console.warn(
    `${LABEL} AUDIT: ${violations.length} barrel import(s) found. ` +
      `These are warnings only in audit mode. Use --release for strict enforcement.`,
  );
}

if (BARREL_IMPORT_EXCEPTIONS.length > 0) {
  console.log(
    `${LABEL} NOTE: ${BARREL_IMPORT_EXCEPTIONS.length} monitored barrel-import exception(s) ` +
      `are active (expires: ${[...new Set(BARREL_IMPORT_EXCEPTIONS.map(e => e.expires))].join(', ')}).`,
  );
}

console.log(
  `${LABEL} ${mode.toUpperCase()} PASSED. ` +
    `${sourceFiles.length} file(s) scanned, ${violations.length} violation(s).`,
);
process.exit(0);
