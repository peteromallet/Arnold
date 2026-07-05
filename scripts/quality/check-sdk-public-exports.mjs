#!/usr/bin/env node
/**
 * M15 SDK Public Export Audit
 *
 * Walks `src/sdk/index.ts` using TypeScript-aware resolution to identify
 * every public export and flags any that originate from internal paths
 * (outside `src/sdk/`) without an entry in the explained allowlist.
 *
 * Supports two modes:
 *
 *   --audit     (default)  Reports violations as warnings. Exit non-zero
 *                          only when the allowlist config itself is missing
 *                          or malformed.
 *
 *   --release              Full enforcement: any unlisted internal re-export
 *                          causes a hard failure. Run before cutting a release.
 *
 * The allowlist lives at `config/governance/sdk-public-export-allowlist.json`.
 * Every entry includes a justification explaining why the re-export belongs
 * on the public boundary.
 *
 * Internal paths resolved via the `@/` tsconfig alias (`@/` → `src/`).
 */

import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import ts from 'typescript';

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

const LABEL = '[sdk-public-exports]';
const REPO_ROOT = process.cwd();
const SDK_ENTRY = path.join(REPO_ROOT, 'src', 'sdk', 'index.ts');
const ALLOWLIST_PATH = path.join(
  REPO_ROOT,
  'config',
  'governance',
  'sdk-public-export-allowlist.json',
);
const TSCONFIG_PATH = path.join(REPO_ROOT, 'tsconfig.json');

// ---------------------------------------------------------------------------
// Helpers: path resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a module specifier to an absolute file path using tsconfig path
 * mappings. Returns null if the specifier cannot be resolved to a local file
 * (e.g. node_modules, ambient type declarations).
 */
function resolveSpecifier(specifier, fromDir) {
  // Sibling imports (./ or ../)
  if (specifier.startsWith('.')) {
    const resolved = resolveCandidate(
      path.resolve(fromDir, specifier),
    );
    return resolved;
  }

  // Named path alias: @/ → src/
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

  // Bare specifier — treated as external (npm package, node built-in, etc.)
  return null;
}

/**
 * Try common TypeScript extensions to find the actual file on disk.
 */
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

/**
 * Determine whether a resolved file path is "internal" — meaning it lives
 * outside the `src/sdk/` directory.
 */
function isInternalPath(resolvedPath) {
  if (!resolvedPath) return false;
  const sdkDir = path.join(REPO_ROOT, 'src', 'sdk') + path.sep;
  return !resolvedPath.startsWith(sdkDir);
}

// ---------------------------------------------------------------------------
// TypeScript AST walking
// ---------------------------------------------------------------------------

/**
 * Map from ts.SyntaxKind to a human-readable declaration kind string.
 */
const DECLARATION_KIND_MAP = {
  [ts.SyntaxKind.TypeAliasDeclaration]: 'type',
  [ts.SyntaxKind.InterfaceDeclaration]: 'interface',
  [ts.SyntaxKind.FunctionDeclaration]: 'function',
  [ts.SyntaxKind.VariableStatement]: 'const',
  [ts.SyntaxKind.ClassDeclaration]: 'class',
  [ts.SyntaxKind.EnumDeclaration]: 'enum',
};

/**
 * Extract all export declarations from a TypeScript source file.
 *
 * Returns an array of export descriptors:
 *   - Declared exports:       { name, kind: 'declared', declarationKind }
 *   - Re-exports from path:   { name, kind: 'value'|'type', source: absolutePath }
 */
function walkExports(sourceFile) {
  /** @type {Array<{ name: string, kind: 'declared' | 'value' | 'type', source?: string, declarationKind?: string }>} */
  const exports = [];

  ts.forEachChild(sourceFile, function visit(node) {
    // export type X = ...
    // export interface X { ... }
    // export function X(...) { ... }
    // export const X = ...
    // export class X { ... }
    if (
      ts.isExportDeclaration(node) === false &&
      ts.isTypeAliasDeclaration(node) &&
      hasExportModifier(node)
    ) {
      exports.push({ name: node.name.text, kind: 'declared', declarationKind: 'type' });
    } else if (
      ts.isInterfaceDeclaration(node) &&
      hasExportModifier(node)
    ) {
      exports.push({ name: node.name.text, kind: 'declared', declarationKind: 'interface' });
    } else if (
      ts.isFunctionDeclaration(node) &&
      hasExportModifier(node) &&
      node.name
    ) {
      exports.push({ name: node.name.text, kind: 'declared', declarationKind: 'function' });
    } else if (
      ts.isVariableStatement(node) &&
      hasExportModifier(node)
    ) {
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) {
          exports.push({ name: decl.name.text, kind: 'declared', declarationKind: 'const' });
        }
      }
    } else if (
      ts.isClassDeclaration(node) &&
      hasExportModifier(node) &&
      node.name
    ) {
      exports.push({ name: node.name.text, kind: 'declared', declarationKind: 'class' });
    } else if (
      ts.isEnumDeclaration(node) &&
      hasExportModifier(node)
    ) {
      exports.push({ name: node.name.text, kind: 'declared', declarationKind: 'enum' });
    }

    // export { A, B } from './foo';
    // export type { A, B } from './foo';
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
            exports.push({
              name,
              kind: isTypeOnly ? 'type' : 'value',
              source: resolved ?? specifier,
            });
          } else {
            // export { A } from no module — these are re-exports of local
            // bindings from imports declared at the top of the file.
            exports.push({ name, kind: 'declared' });
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  });

  return exports;
}

/**
 * Check whether a node has the `export` modifier.
 */
function hasExportModifier(node) {
  if (!node.modifiers) return false;
  return node.modifiers.some(
    (m) => m.kind === ts.SyntaxKind.ExportKeyword,
  );
}

// ---------------------------------------------------------------------------
// Allowlist loading
// ---------------------------------------------------------------------------

/**
 * Load and validate the allowlist config.
 * Returns { allowlist, inlineDeclarations, errors }.
 *   - allowlist: Map<string, Set<string>> from source path to set of allowed export names.
 *   - inlineDeclarations: Map<string, { symbol, owner, rationale, expiration }> from symbol name to entry.
 */
function loadAllowlist() {
  /** @type {string[]} */
  const errors = [];

  if (!fs.existsSync(ALLOWLIST_PATH)) {
    errors.push(`Allowlist config not found: ${path.relative(REPO_ROOT, ALLOWLIST_PATH)}`);
    return { allowlist: null, inlineDeclarations: null, errors };
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(ALLOWLIST_PATH, 'utf8'));
  } catch (err) {
    errors.push(`Allowlist config is not valid JSON: ${err.message}`);
    return { allowlist: null, inlineDeclarations: null, errors };
  }

  if (!Array.isArray(raw.allowlist)) {
    errors.push(`Allowlist config is missing the 'allowlist' array.`);
    return { allowlist: null, inlineDeclarations: null, errors };
  }

  /** @type {Map<string, Set<string>>} */
  const map = new Map();

  for (let i = 0; i < raw.allowlist.length; i++) {
    const entry = raw.allowlist[i];
    const idx = `allowlist[${i}]`;

    if (typeof entry.sourcePath !== 'string' || entry.sourcePath.length === 0) {
      errors.push(`${idx}: missing or empty 'sourcePath'.`);
      continue;
    }
    if (!Array.isArray(entry.exports)) {
      errors.push(`${idx}: missing or invalid 'exports' array.`);
      continue;
    }
    if (typeof entry.justification !== 'string' || entry.justification.length === 0) {
      errors.push(`${idx}: missing or empty 'justification'.`);
      continue;
    }

    const sourcePath = entry.sourcePath;
    const resolvedSource = resolveSpecifier(
      sourcePath,
      path.dirname(SDK_ENTRY),
    );

    if (!resolvedSource) {
      errors.push(`${idx}: cannot resolve sourcePath '${sourcePath}' to a local file.`);
      continue;
    }

    const existing = map.get(resolvedSource) ?? new Set();
    for (const exportName of entry.exports) {
      existing.add(exportName);
    }
    map.set(resolvedSource, existing);
  }

  // ---- Parse inlineDeclarations ----
  /** @type {Map<string, { symbol: string, owner: string, rationale: string, expiration: string }>} */
  const inlineMap = new Map();

  if (Array.isArray(raw.inlineDeclarations)) {
    for (let i = 0; i < raw.inlineDeclarations.length; i++) {
      const entry = raw.inlineDeclarations[i];
      const idx = `inlineDeclarations[${i}]`;

      if (typeof entry.symbol !== 'string' || entry.symbol.length === 0) {
        errors.push(`${idx}: missing or empty 'symbol'.`);
        continue;
      }
      if (typeof entry.owner !== 'string' || entry.owner.length === 0) {
        errors.push(`${idx}: missing or empty 'owner'.`);
        continue;
      }
      if (typeof entry.rationale !== 'string' || entry.rationale.length === 0) {
        errors.push(`${idx}: missing or empty 'rationale'.`);
        continue;
      }
      if (typeof entry.expiration !== 'string' || entry.expiration.length === 0) {
        errors.push(`${idx}: missing or empty 'expiration'.`);
        continue;
      }

      inlineMap.set(entry.symbol, {
        symbol: entry.symbol,
        owner: entry.owner,
        rationale: entry.rationale,
        expiration: entry.expiration,
      });
    }
  }

  return { allowlist: map, inlineDeclarations: inlineMap, errors };
}

// ---------------------------------------------------------------------------
// M7b T10: Forbidden exports — symbols that must never appear in the
// root SDK barrel.  These were deliberately removed from the public
// boundary and must not be reintroduced.
// ---------------------------------------------------------------------------

/**
 * Map from forbidden export name to a short justification explaining why it
 * is prohibited from the public barrel.
 *
 * Process-spec / lifecycle / status types are internal to the process manager
 * and must not leak through the public SDK entrypoint.  Process task result
 * states (roundtrip request / action / result, progress events, log summaries)
 * and process output-kind vocabulary are similarly internal.
 *
 * Sidecar-route process vocabulary is enforced separately via a name-pattern
 * gate (see FORBIDDEN_SIDECAR_PATTERNS below).
 *
 * @type {Map<string, string>}
 */
const FORBIDDEN_EXPORTS = new Map([
  // Process spec / lifecycle / status — internal process-manager surface
  [
    'ProcessSpec',
    'Process specification type is internal to the process manager.  Use ProcessManifestEntry or ProcessContribution instead.',
  ],
  [
    'ProcessLifecycleState',
    'Process lifecycle state type is internal to the process manager.',
  ],
  [
    'ProcessStatusBase',
    'Process status base interface is internal to the process manager.',
  ],
  [
    'ProcessStatus',
    'Process status discriminated union is internal to the process manager.',
  ],

  // Process task result states — roundtrip request / action / result
  [
    'ProcessRoundtripRequest',
    'Process roundtrip request type is internal process vocabulary.',
  ],
  [
    'ProcessRoundtripAction',
    'Process roundtrip action type is internal process vocabulary.',
  ],
  [
    'ProcessRoundtripResult',
    'Process roundtrip result type is internal process vocabulary.',
  ],

  // Process event / log vocabulary
  [
    'ProcessProgressEvent',
    'Process progress event type is internal process vocabulary.',
  ],
  [
    'ProcessLogSummary',
    'Process log summary type is internal process vocabulary.',
  ],

  // Process output-kind vocabulary
  [
    'ProcessOutputKind',
    'Process output kind type is internal process vocabulary.',
  ],
]);

/**
 * Regex patterns that match sidecar-route process vocabulary which must
 * never appear in the root SDK barrel.
 *
 * The three allowed sidecar artifact types are:
 *   - RenderArtifactSidecarDescriptor
 *   - RenderArtifactSidecarKind
 *   - SidecarArtifactManifestProfile
 *
 * Any other export whose name contains "Sidecar" is suspicious and will be
 * flagged as forbidden sidecar-route process vocabulary.
 *
 * @type {Array<{ pattern: RegExp, justification: string }>}
 */
const FORBIDDEN_SIDECAR_PATTERNS = [
  {
    pattern: /Sidecar/i,
    justification:
      'Sidecar-named export not in the allowed artifact-sidecar set ' +
      '(RenderArtifactSidecarDescriptor, RenderArtifactSidecarKind, ' +
      'SidecarArtifactManifestProfile).  This may be sidecar-route ' +
      'process vocabulary leaking into the public barrel.',
  },
];

/**
 * Set of sidecar-related export names that are explicitly allowed in the
 * public barrel (artifact-sidecar types, not process-sidecar vocabulary).
 *
 * @type {Set<string>}
 */
const ALLOWED_SIDECAR_EXPORT_NAMES = new Set([
  'RenderArtifactSidecarDescriptor',
  'RenderArtifactSidecarKind',
  'SidecarArtifactManifestProfile',
]);

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);
console.log(`${LABEL} Entrypoint: ${path.relative(REPO_ROOT, SDK_ENTRY)}`);

if (!fs.existsSync(SDK_ENTRY)) {
  console.error(`${LABEL} SDK entrypoint not found: ${SDK_ENTRY}`);
  process.exit(1);
}

// ---- Load allowlist ----
const { allowlist, inlineDeclarations, errors: allowlistErrors } = loadAllowlist();

if (allowlistErrors.length > 0) {
  console.error(`${LABEL} Allowlist config errors:`);
  for (const err of allowlistErrors) {
    console.error(`${LABEL}   - ${err}`);
  }
  if (allowlist === null) {
    console.error(
      `${LABEL} Cannot proceed without a valid allowlist. ` +
        `Fix the config at ${path.relative(REPO_ROOT, ALLOWLIST_PATH)}.`,
    );
    process.exit(1);
  }
  // Non-fatal errors: allowlist exists but has individual entry issues.
  // Continue with what we have.
}

// ---- Create TypeScript program ----
const sourceText = fs.readFileSync(SDK_ENTRY, 'utf8');

// Create a minimal compiler host for a single file
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
if (!sourceFile) {
  console.error(`${LABEL} Failed to parse SDK entrypoint as TypeScript.`);
  process.exit(1);
}

// ---- Walk exports ----
const allExports = walkExports(sourceFile);

console.log(`${LABEL} Found ${allExports.length} export(s) total.`);

// ---- M7b T10: Forbidden exports gate ----
// Fail fast if any export name is on the hard deny-list.  This runs before
// the allowlist check and applies in both audit and release modes so that
// forbidden process / sidecar-route vocabulary can never accidentally land
// on the public boundary.

/** @type {Array<{ name: string, justification: string }>} */
const forbiddenHits = [];

for (const exp of allExports) {
  // ---- Exact-name forbidden check ----
  const justification = FORBIDDEN_EXPORTS.get(exp.name);
  if (justification) {
    forbiddenHits.push({ name: exp.name, justification });
    continue;
  }

  // ---- Sidecar-pattern forbidden check (skip allowed artifact types) ----
  if (ALLOWED_SIDECAR_EXPORT_NAMES.has(exp.name)) {
    continue;
  }

  for (const entry of FORBIDDEN_SIDECAR_PATTERNS) {
    if (entry.pattern.test(exp.name)) {
      forbiddenHits.push({ name: exp.name, justification: entry.justification });
      break;
    }
  }
}

if (forbiddenHits.length > 0) {
  console.error(
    `${LABEL} FORBIDDEN EXPORT FAILURE: ${forbiddenHits.length} prohibited ` +
      `export(s) detected in the public SDK barrel.`,
  );
  for (const hit of forbiddenHits) {
    console.error(`${LABEL}   - ${hit.name}`);
    console.error(`${LABEL}     ${hit.justification}`);
  }
  console.error(
    `${LABEL} These symbols were deliberately removed from the public SDK ` +
      `boundary and must not be reintroduced.  Remove them from ` +
      `${path.relative(REPO_ROOT, SDK_ENTRY)}.`,
  );
  process.exit(1);
}

// ---- Classify exports ----
/** @type {Array<{ name: string, source: string, kind: string }>} */
const internalReexports = [];
let declaredCount = 0;
let siblingReexportCount = 0;

for (const exp of allExports) {
  if (exp.kind === 'declared' || exp.source === undefined) {
    declaredCount++;
    continue;
  }

  const resolvedSource =
    typeof exp.source === 'string' && path.isAbsolute(exp.source)
      ? exp.source
      : resolveSpecifier(exp.source, path.dirname(SDK_ENTRY));

  if (!resolvedSource || !isInternalPath(resolvedSource)) {
    // External or unresolved — skip (npm packages, etc.)
    siblingReexportCount++;
    continue;
  }

  internalReexports.push({
    name: exp.name,
    source: resolvedSource,
    kind: exp.kind,
  });
}

console.log(
  `${LABEL} ${declaredCount} declared, ${siblingReexportCount} sibling re-export(s), ` +
    `${internalReexports.length} internal re-export(s).`,
);

// ---- Check against allowlist ----
const violations = [];

for (const reexp of internalReexports) {
  const allowedForSource = allowlist?.get(reexp.source);
  if (!allowedForSource || !allowedForSource.has(reexp.name)) {
    violations.push({
      name: reexp.name,
      source: path.relative(REPO_ROOT, reexp.source),
      kind: reexp.kind,
    });
  }
}

// ---- Also check: does the allowlist reference any exports not actually present? ----
const obsoleteAllowlistEntries = [];
if (allowlist) {
  for (const [sourcePath, allowedNames] of allowlist) {
    const reexportsFromSource = internalReexports.filter(
      (r) => r.source === sourcePath,
    );
    const actualNames = new Set(reexportsFromSource.map((r) => r.name));
    for (const allowedName of allowedNames) {
      if (!actualNames.has(allowedName)) {
        obsoleteAllowlistEntries.push({
          name: allowedName,
          source: path.relative(REPO_ROOT, sourcePath),
        });
      }
    }
  }
}

// ---- Inline declaration gate ----
/** @type {Array<{ name: string, declarationKind: string }>} */
const inlineDeclarations_all = [];
for (const exp of allExports) {
  if (exp.kind === 'declared' && exp.declarationKind) {
    inlineDeclarations_all.push({
      name: exp.name,
      declarationKind: exp.declarationKind,
    });
  }
}

/** @type {Array<{ name: string, declarationKind: string }>} */
const unlistedInlineDeclarations = [];

if (inlineDeclarations && inlineDeclarations.size > 0) {
  for (const decl of inlineDeclarations_all) {
    if (!inlineDeclarations.has(decl.name)) {
      unlistedInlineDeclarations.push(decl);
    }
  }
}

// ---- Check for obsolete inline declaration entries ----
const obsoleteInlineEntries = [];
if (inlineDeclarations) {
  const actualInlineNames = new Set(inlineDeclarations_all.map((d) => d.name));
  for (const [symbol] of inlineDeclarations) {
    if (!actualInlineNames.has(symbol)) {
      obsoleteInlineEntries.push(symbol);
    }
  }
}

// ---- Report ----
if (violations.length > 0) {
  const header =
    mode === 'release'
      ? 'RELEASE FAILURE:'
      : 'WARNING:';
  console.error(
    `${LABEL} ${header} ${violations.length} unlisted internal re-export(s) detected:`,
  );
  for (const v of violations) {
    console.error(
      `${LABEL}   - ${v.name} (${v.kind}) re-exported from ${v.source}`,
    );
  }
  console.error(
    `${LABEL} Add these to ${path.relative(REPO_ROOT, ALLOWLIST_PATH)} ` +
      `with a justification, or remove them from the public SDK boundary.`,
  );
}

if (obsoleteAllowlistEntries.length > 0) {
  console.warn(
    `${LABEL} NOTE: ${obsoleteAllowlistEntries.length} allowlist entry/entries ` +
      `reference exports no longer present:`,
  );
  for (const e of obsoleteAllowlistEntries) {
    console.warn(`${LABEL}   - ${e.name} from ${e.source}`);
  }
}

// ---- Inline declaration report ----
console.log(
  `${LABEL} Inline declarations: ${inlineDeclarations_all.length} total ` +
    `(${[...new Set(inlineDeclarations_all.map((d) => d.declarationKind))].sort().join(', ')}).`,
);

if (unlistedInlineDeclarations.length > 0) {
  const header =
    mode === 'release'
      ? 'INLINE DECLARATION GATE:'
      : 'INLINE DECLARATION NOTE:';
  console.warn(
    `${LABEL} ${header} ${unlistedInlineDeclarations.length} inline export(s) ` +
      `not listed in inlineDeclarations:`,
  );
  for (const d of unlistedInlineDeclarations) {
    console.warn(
      `${LABEL}   - ${d.name} (${d.declarationKind})`,
    );
  }
  console.warn(
    `${LABEL} Add these to the 'inlineDeclarations' array in ` +
      `${path.relative(REPO_ROOT, ALLOWLIST_PATH)} ` +
      `with symbol, owner, rationale, and expiration fields.`,
  );
}

if (obsoleteInlineEntries.length > 0) {
  const header =
    mode === 'release'
      ? 'RELEASE FAILURE:'
      : 'NOTE:';
  console.error(
    `${LABEL} ${header} ${obsoleteInlineEntries.length} obsolete inline declaration ` +
      `entry/entries reference symbols no longer present:`,
  );
  for (const e of obsoleteInlineEntries) {
    console.error(`${LABEL}   - ${e}`);
  }
  if (mode === 'release') {
    console.error(
      `${LABEL} Remove these entries from the 'inlineDeclarations' array in ` +
        `${path.relative(REPO_ROOT, ALLOWLIST_PATH)}.`,
    );
    process.exit(1);
  }
}

// ---- No-inline barrel gate (release mode) ----
if (mode === 'release' && inlineDeclarations_all.length > 0) {
  console.error(
    `${LABEL} RELEASE FAILURE: ${inlineDeclarations_all.length} inline ` +
      `declaration(s) found in the public barrel.`,
  );
  console.error(
    `${LABEL} src/sdk/index.ts must be a pure re-export barrel with no ` +
      `inline exported interfaces, types, functions, classes, enums, or consts.`,
  );
  for (const d of inlineDeclarations_all) {
    console.error(`${LABEL}   - ${d.name} (${d.declarationKind})`);
  }
  console.error(
    `${LABEL} Move each declaration to a canonical module under src/sdk/ ` +
      `and re-export it from the barrel.`,
  );
  process.exit(1);
}

// ---- Exit decision ----
if (mode === 'release' && violations.length > 0) {
  console.error(
    `${LABEL} RELEASE FAILED: ` +
      `${violations.length} unlisted internal re-export(s) must be resolved.`,
  );
  process.exit(1);
}

if (violations.length > 0) {
  // Audit mode with violations: warn but don't fail
  console.warn(
    `${LABEL} AUDIT: ${violations.length} unlisted re-export(s) found. ` +
      `These are warnings only in audit mode. Use --release for strict enforcement.`,
  );
}

console.log(
  `${LABEL} ${mode.toUpperCase()} PASSED. ` +
    `${allExports.length} export(s) reviewed, ` +
    `${violations.length} violation(s), ` +
    `${obsoleteAllowlistEntries.length} obsolete allowlist entry/entries, ` +
    `${unlistedInlineDeclarations.length} unlisted inline declaration(s), ` +
    `${obsoleteInlineEntries.length} obsolete inline declaration entry/entries.`,
);

// ---------------------------------------------------------------------------
// Invoke the SDK-internal no-barrel-import gate (M2a T4).
// ---------------------------------------------------------------------------

const noBarrelImportScript = path.join(
  REPO_ROOT,
  'scripts',
  'quality',
  'check-sdk-no-barrel-imports.mjs',
);

if (fs.existsSync(noBarrelImportScript)) {
  console.log(`${LABEL} Running SDK-internal no-barrel-import gate…`);
  try {
    const passThroughFlag = mode === 'release' ? ' --release' : ' --audit';
    execSync(`node ${noBarrelImportScript}${passThroughFlag}`, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      timeout: 60_000,
      stdio: ['pipe', 'inherit', 'inherit'],
    });
  } catch (err) {
    if (mode === 'release') {
      console.error(
        `${LABEL} SDK-internal barrel import(s) found — release blocked.`,
      );
      process.exit(1);
    }
    // In audit mode, tolerate failures from the sub-script (it exits 1 on
    // release mode only, but just in case).
  }
} else {
  console.warn(
    `${LABEL} No-barrel-import gate not found at ${path.relative(REPO_ROOT, noBarrelImportScript)}; skipping.`,
  );
}

process.exit(0);
