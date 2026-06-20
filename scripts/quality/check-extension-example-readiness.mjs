#!/usr/bin/env node
/**
 * M15 Pre-Doc Example Readiness Gate
 *
 * Reads the canonical supported/deferred matrix
 * (`docs/video-editor/extension-platform-supported-deferred.md`) and
 * governance outputs (`config/governance/contract-surface-map.json`,
 * `config/governance/sdk-public-export-allowlist.json`) to determine which
 * example files are safe to reference in author-contract docs and quickstart
 * guides.
 *
 * ## What this gate enforces
 *
 * 1. Every EX: and EXT: evidence reference in a **supported** row must
 *    resolve to an existing file or directory on disk.
 * 2. Example files that demonstrate deferred, unsupported, or
 *    release-blocking behaviour are flagged as **unsupported docs
 *    candidates** and cause the check to fail (even in audit mode).
 * 3. Every example file under `src/examples/` must import exclusively
 *    from `@reigh/editor-sdk` (the public boundary).  Internal imports
 *    (`src/tools/video-editor/` etc.) are not allowed in public examples.
 * 4. Examples that exist on disk but have no corresponding **supported**
 *    matrix row are reported as unclassified.
 *
 * ## Modes
 *
 *   --audit     (default)  Report missing examples, internal imports, and
 *                          unclassified files as warnings.  Only fail when
 *                          a supported row's example is missing or an
 *                          unsupported-docs-candidate file exists.
 *
 *   --release             Same as audit, plus hard-fail on unclassified
 *                         examples and internal imports in example files.
 *
 * ## Machine-readable output
 *
 * The gate always writes a JSON record of docs-safe example IDs to stdout
 * as its final line, e.g.:
 *
 *   {"docsSafeExampleIds":["toolbar-example","command-extension",…]}
 *
 * This JSON is consumed by downstream doc-generation tooling.
 *
 * ## Dependencies
 *
 * Consumes the shared classification predicates from
 * `./lib/extension-contract-matrix.mjs` (SD1) but does NOT re-parse the
 * contract-recheck matrix — it only reads the supported/deferred matrix.
 */

import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs';
import { resolve, dirname, relative, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const SUPPORTED_DEFERRED_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);

const CONTRACT_SURFACE_MAP_PATH = resolve(
  repoRoot,
  'config/governance/contract-surface-map.json',
);

const SDK_EXPORT_ALLOWLIST_PATH = resolve(
  repoRoot,
  'config/governance/sdk-public-export-allowlist.json',
);

const EXAMPLES_DIR = resolve(repoRoot, 'src/examples');
const EXTENSIONS_DIR = resolve(
  repoRoot,
  'src/tools/video-editor/examples/extensions',
);

const LABEL = '[example-readiness]';

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

const isRelease = mode === 'release';

// ---------------------------------------------------------------------------
// Supported/deferred matrix parser
// ---------------------------------------------------------------------------

/**
 * @typedef {object} MatrixRow
 * @property {string} rowId        – e.g. "S-001", "D-001"
 * @property {string} behavior     – human-readable behaviour description
 * @property {string} classification – "supported" | "deferred" | "unsupported" | "release-blocking"
 * @property {string} evidence     – raw evidence string with EX:/EXT: refs
 */

/**
 * @typedef {object} ExampleRef
 * @property {string} refType       – "EX" or "EXT"
 * @property {string} refPath       – the path portion of the reference
 * @property {string} sourceRowId   – the matrix row ID that references it
 * @property {string} classification – the row's classification
 */

/**
 * Parse the supported/deferred matrix markdown and return structured rows.
 *
 * @returns {{ supportedRows: MatrixRow[], deferredRows: MatrixRow[], unsupportedRows: MatrixRow[], releaseBlockingRows: MatrixRow[] }}
 */
function parseSupportedDeferredMatrix() {
  if (!existsSync(SUPPORTED_DEFERRED_PATH)) {
    throw new Error(
      `Supported/deferred matrix not found: ${SUPPORTED_DEFERRED_PATH}`,
    );
  }

  const markdown = readFileSync(SUPPORTED_DEFERRED_PATH, 'utf8');
  const lines = markdown.split('\n');

  /** @type {MatrixRow[]} */
  const supportedRows = [];
  /** @type {MatrixRow[]} */
  const deferredRows = [];
  /** @type {MatrixRow[]} */
  const unsupportedRows = [];
  /** @type {MatrixRow[]} */
  const releaseBlockingRows = [];

  // State machine: track which section we're in
  /** @type {'none' | 'supported' | 'deferred' | 'scope'} */
  let section = 'none';
  let inSupportedTable = false;
  let inDeferredTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // ---- section detection ----
    if (line.startsWith('## 2. Supported V1 Behavior Matrix')) {
      section = 'supported';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 3. Deferred / Unsupported V1 Behavior Matrix')) {
      section = 'deferred';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 4. V1 Scope Boundaries')) {
      section = 'scope';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 5.') || line.startsWith('## 6.') || line.startsWith('## 7.') || line.startsWith('## 8.')) {
      section = 'none';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    // ---- sub-section: enter a table ----
    if (section === 'supported' && line.startsWith('###') && line.includes('|')) {
      inSupportedTable = true;
      continue;
    }

    if (section === 'deferred' && line.startsWith('###')) {
      inDeferredTable = true;
      continue;
    }

    // ---- table row parsing ----
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());

      // Skip header and separator rows
      if (
        cells.every((c) => /^:?-{3,}:?$/.test(c)) ||
        cells.some((c) =>
          /^(Row ID|Behavior|Classification|Evidence|Concern|V1 Answer)$/i.test(c),
        )
      ) {
        continue;
      }

      if (section === 'supported' && cells.length >= 4) {
        const classification = (cells[2] || '')
          .replace(/[*_]{1,2}/g, '')
          .toLowerCase()
          .trim();

        const row = {
          rowId: cells[0] || '',
          behavior: cells[1] || '',
          classification: cells[2] || '',
          evidence: cells[3] || '',
        };

        if (classification === 'supported') {
          supportedRows.push(row);
        }
      }

      if (section === 'deferred' && cells.length >= 4) {
        const classification = (cells[2] || '')
          .replace(/[*_]{1,2}/g, '')
          .toLowerCase()
          .trim();

        const row = {
          rowId: cells[0] || '',
          behavior: cells[1] || '',
          classification: cells[2] || '',
          evidence: cells[3] || '',
        };

        if (classification === 'deferred') {
          deferredRows.push(row);
        } else if (classification === 'unsupported') {
          unsupportedRows.push(row);
        } else if (classification === 'release-blocking') {
          releaseBlockingRows.push(row);
        }
      }

      // Also handle out-of-scope table (§ 4.1)
      if (section === 'scope' && cells.length >= 2) {
        // These are unsupported by default
        unsupportedRows.push({
          rowId: '',
          behavior: cells[0] || '',
          classification: 'unsupported',
          evidence: cells[1] || '',
        });
      }
    }
  }

  return { supportedRows, deferredRows, unsupportedRows, releaseBlockingRows };
}

// ---------------------------------------------------------------------------
// Evidence reference extraction
// ---------------------------------------------------------------------------

/**
 * Extract EX: and EXT: references from an evidence string.
 *
 * @param {string} evidence
 * @returns {Array<{ type: 'EX'|'EXT', path: string }>}
 */
function extractExampleRefs(evidence) {
  /** @type {Array<{ type: 'EX'|'EXT', path: string }>} */
  const refs = [];

  // Split the evidence string on semicolons into segments, then process each.
  // Semicolons separate evidence-type groups; commas separate items within a group.
  const segments = evidence.split(/\s*;\s*/);

  for (const segment of segments) {
    const trimmed = segment.trim();

    // EX: prefix — may be followed by a comma-separated list of filenames
    if (trimmed.startsWith('EX:')) {
      const value = trimmed.slice(3).trim();
      const files = value.split(/,\s*/).filter((f) => f.length > 0);
      for (const file of files) {
        refs.push({ type: 'EX', path: file.trim() });
      }
      continue;
    }

    // EXT: prefix — may be followed by a comma-separated list of paths
    if (trimmed.startsWith('EXT:')) {
      const value = trimmed.slice(4).trim();
      const paths = value.split(/,\s*/).filter((p) => p.length > 0);
      for (const p of paths) {
        refs.push({ type: 'EXT', path: p.trim() });
      }
      continue;
    }
  }

  return refs;
}

// ---------------------------------------------------------------------------
// File resolution helpers
// ---------------------------------------------------------------------------

/**
 * Resolve an EX: reference path to an absolute file path.
 * EX: references without a leading directory are assumed to be in
 * `src/examples/`.  References with a directory prefix are resolved
 * relative to the repo root.
 *
 * @param {string} exPath
 * @returns {string}
 */
function resolveExPath(exPath) {
  // Strip leading/trailing whitespace and punctuation
  const cleaned = exPath.replace(/[;,]+$/, '').trim();

  if (cleaned.includes('/')) {
    // Has a directory prefix — resolve from repo root
    // But strip any leading src/ if present to avoid double-prefixing
    const normalized = cleaned.startsWith('src/') ? cleaned : cleaned;
    return resolve(repoRoot, normalized);
  }

  // Bare filename — look in src/examples/
  return resolve(EXAMPLES_DIR, cleaned);
}

/**
 * Resolve an EXT: reference path.
 *
 * EXT: references can be:
 *   - Directory paths: `flagship-local/` → resolves to the extension directory
 *   - File paths within an extension: `flagship-local/FlagshipEffectComponent.tsx` → resolves to that file
 *   - Test paths: `__tests__/flagship-local-transition.test.ts` → resolves to the test file
 *
 * Returns { absPath, isFile } where isFile=true means the reference points to
 * a specific file rather than a directory.
 *
 * @param {string} extPath
 * @returns {{ absPath: string, isFile: boolean }}
 */
function resolveExtPath(extPath) {
  const cleaned = extPath.replace(/[;,]+$/, '').trim().replace(/\/$/, '');

  // Determine if it looks like a file (has a file extension)
  const isFile = /\.(ts|tsx|js|jsx|json)$/i.test(cleaned);

  // If the path starts with __tests__/, it's a test file in the extensions
  // __tests__ directory. Resolve relative to the extensions dir.
  if (cleaned.startsWith('__tests__/')) {
    return {
      absPath: resolve(EXTENSIONS_DIR, cleaned),
      isFile: true,
    };
  }

  // If the path already includes src/, resolve from repo root
  if (cleaned.startsWith('src/')) {
    return {
      absPath: resolve(repoRoot, cleaned),
      isFile,
    };
  }

  // Otherwise resolve relative to the extensions directory
  return {
    absPath: resolve(EXTENSIONS_DIR, cleaned),
    isFile,
  };
}

/**
 * Check that an EX: example file exists and hasn't been deleted.
 *
 * @param {string} absPath
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkExFile(absPath) {
  if (!existsSync(absPath)) {
    return { exists: false, reason: `File not found: ${absPath}` };
  }

  try {
    const stat = statSync(absPath);
    if (!stat.isFile()) {
      return { exists: false, reason: `Not a regular file: ${absPath}` };
    }
  } catch {
    return { exists: false, reason: `Cannot stat file: ${absPath}` };
  }

  return { exists: true };
}

/**
 * Check that an EXT: example directory exists and has the required files
 * (index.ts and reigh-extension.json).
 *
 * @param {string} absDir
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkExtDir(absDir) {
  if (!existsSync(absDir)) {
    return { exists: false, reason: `Directory not found: ${absDir}` };
  }

  try {
    const stat = statSync(absDir);
    if (!stat.isDirectory()) {
      return { exists: false, reason: `Not a directory: ${absDir}` };
    }
  } catch {
    return { exists: false, reason: `Cannot stat directory: ${absDir}` };
  }

  const indexFile = resolve(absDir, 'index.ts');
  const manifestFile = resolve(absDir, 'reigh-extension.json');

  if (!existsSync(indexFile)) {
    return {
      exists: false,
      reason: `Extension directory missing index.ts: ${absDir}`,
    };
  }

  if (!existsSync(manifestFile)) {
    return {
      exists: false,
      reason: `Extension directory missing reigh-extension.json: ${absDir}`,
    };
  }

  return { exists: true };
}

// ---------------------------------------------------------------------------
// Import boundary check
// ---------------------------------------------------------------------------

/**
 * Check that a TypeScript source file only imports from @reigh/editor-sdk
 * (the public SDK entrypoint).  Returns a list of internal-import violations.
 *
 * @param {string} absPath
 * @returns {{ clean: boolean, violations: string[] }}
 */
function checkImportBoundary(absPath) {
  if (!existsSync(absPath)) {
    return { clean: false, violations: [`File not found: ${absPath}`] };
  }

  const content = readFileSync(absPath, 'utf8');
  const violations = [];

  // Find all import/require statements
  const importRe = /from\s+['"]([^'"]+)['"]/g;
  let match;

  while ((match = importRe.exec(content)) !== null) {
    const specifier = match[1];

    // Allow @reigh/editor-sdk imports
    if (specifier === '@reigh/editor-sdk') continue;

    // Allow relative imports within the examples/extensions directories
    if (specifier.startsWith('./') || specifier.startsWith('../')) continue;

    // Allow standard library and npm packages
    if (
      !specifier.startsWith('@/') &&
      !specifier.startsWith('src/') &&
      !specifier.includes('video-editor')
    ) {
      // Looks like an npm package — allow it
      continue;
    }

    // Internal imports are violations
    violations.push(
      `Internal import "${specifier}" in ${relative(repoRoot, absPath)}`,
    );
  }

  // Also check for dynamic imports / require()
  const dynamicImportRe = /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  while ((match = dynamicImportRe.exec(content)) !== null) {
    const specifier = match[1];
    if (specifier === '@reigh/editor-sdk') continue;
    if (specifier.startsWith('./') || specifier.startsWith('../')) continue;
    if (
      !specifier.startsWith('@/') &&
      !specifier.startsWith('src/') &&
      !specifier.includes('video-editor')
    ) {
      continue;
    }
    violations.push(
      `Internal dynamic import "${specifier}" in ${relative(repoRoot, absPath)}`,
    );
  }

  return { clean: violations.length === 0, violations };
}

// ---------------------------------------------------------------------------
// Governance cross-reference
// ---------------------------------------------------------------------------

/**
 * Load the contract-surface-map and sdk-public-export-allowlist.
 *
 * @returns {{ contractSurfaceMap: object, exportAllowlist: object }}
 */
function loadGovernanceData() {
  let contractSurfaceMap = {};
  let exportAllowlist = { allowlist: [] };

  if (existsSync(CONTRACT_SURFACE_MAP_PATH)) {
    try {
      contractSurfaceMap = JSON.parse(
        readFileSync(CONTRACT_SURFACE_MAP_PATH, 'utf8'),
      );
    } catch (err) {
      console.warn(
        `${LABEL} Could not parse contract-surface-map: ${err.message}`,
      );
    }
  }

  if (existsSync(SDK_EXPORT_ALLOWLIST_PATH)) {
    try {
      exportAllowlist = JSON.parse(
        readFileSync(SDK_EXPORT_ALLOWLIST_PATH, 'utf8'),
      );
    } catch (err) {
      console.warn(
        `${LABEL} Could not parse sdk-public-export-allowlist: ${err.message}`,
      );
    }
  }

  return { contractSurfaceMap, exportAllowlist };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…\n`);

// ---- Step 1: Parse the supported/deferred matrix ----
console.log(`${LABEL} Parsing supported/deferred matrix…`);

let supportedRows = [];
let deferredRows = [];
let unsupportedRows = [];
let releaseBlockingRows = [];

try {
  const sdm = parseSupportedDeferredMatrix();
  supportedRows = sdm.supportedRows;
  deferredRows = sdm.deferredRows;
  unsupportedRows = sdm.unsupportedRows;
  releaseBlockingRows = sdm.releaseBlockingRows;

  console.log(
    `${LABEL} Parsed matrix: ${supportedRows.length} supported, ` +
      `${deferredRows.length} deferred, ${unsupportedRows.length} unsupported, ` +
      `${releaseBlockingRows.length} release-blocking row(s).`,
  );
} catch (err) {
  console.error(`${LABEL} Failed to parse supported/deferred matrix: ${err.message}`);
  process.exit(1);
}

// ---- Step 2: Load governance data ----
console.log(`${LABEL} Loading governance data…`);
const { contractSurfaceMap, exportAllowlist } = loadGovernanceData();

// ---- Step 3: Extract example references from supported rows ----
console.log(`${LABEL} Extracting example references from supported rows…`);

/** @type {ExampleRef[]} */
const supportedExampleRefs = [];

for (const row of supportedRows) {
  const refs = extractExampleRefs(row.evidence);
  for (const ref of refs) {
    supportedExampleRefs.push({
      refType: ref.type,
      refPath: ref.path,
      sourceRowId: row.rowId,
      classification: 'supported',
    });
  }
}

console.log(
  `${LABEL} Found ${supportedExampleRefs.length} example reference(s) in supported rows.`,
);

// ---- Step 4: Extract example references from deferred/unsupported rows ----
// These are "unsupported docs candidates" — examples demonstrating
// behaviour that is explicitly deferred/unsupported.

/** @type {ExampleRef[]} */
const unsupportedExampleRefs = [];

for (const row of [...deferredRows, ...unsupportedRows, ...releaseBlockingRows]) {
  const refs = extractExampleRefs(row.evidence);
  for (const ref of refs) {
    unsupportedExampleRefs.push({
      refType: ref.type,
      refPath: ref.path,
      sourceRowId: row.rowId,
      classification: row.classification.replace(/[*_]{1,2}/g, '').toLowerCase().trim(),
    });
  }
}

if (unsupportedExampleRefs.length > 0) {
  console.log(
    `${LABEL} Found ${unsupportedExampleRefs.length} example reference(s) in deferred/unsupported rows — ` +
      `these will be flagged as unsupported docs candidates.`,
  );
}

// ---- Step 5: Verify supported example references ----
console.log(`\n${LABEL} Verifying supported example references…`);

/** @type {string[]} */
const failures = [];
/** @type {string[]} */
const warnings = [];
/** @type {Set<string>} */
const docsSafeExampleIds = new Set();
/** @type {Map<string, string>} */
const failedExampleIds = new Map();

for (const ref of supportedExampleRefs) {
  const refLabel = `${ref.refType}:${ref.refPath} (from row ${ref.sourceRowId})`;

  if (ref.refType === 'EX') {
    const absPath = resolveExPath(ref.refPath);
    const check = checkExFile(absPath);

    if (!check.exists) {
      const msg = `Supported example ${refLabel} does not exist: ${check.reason}`;
      failures.push(msg);
      failedExampleIds.set(ref.refPath, check.reason || 'missing');
      continue;
    }

    // Check import boundary for .ts files
    if (absPath.endsWith('.ts') || absPath.endsWith('.tsx')) {
      const boundaryCheck = checkImportBoundary(absPath);
      if (!boundaryCheck.clean) {
        for (const violation of boundaryCheck.violations) {
          const msg = `Supported example ${refLabel} has internal import: ${violation}`;
          if (isRelease) {
            failures.push(msg);
          } else {
            warnings.push(msg);
          }
        }
        // Don't disqualify from docs-safe in audit mode for import issues
        if (isRelease) {
          failedExampleIds.set(ref.refPath, 'internal-imports');
          continue;
        }
      }
    }

    // Derive a stable example ID from the filename
    const exampleId = basename(absPath, '.ts').replace(/\.tsx$/, '');
    docsSafeExampleIds.add(exampleId);
    console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId}`);
  }

  if (ref.refType === 'EXT') {
    const { absPath, isFile } = resolveExtPath(ref.refPath);

    if (isFile) {
      // EXT reference points to a specific file (e.g. FlagshipEffectComponent.tsx)
      // or a test file (e.g. __tests__/flagship-local-transition.test.ts)
      const check = checkExFile(absPath);

      if (!check.exists) {
        const msg = `Supported extension file ${refLabel} does not exist: ${check.reason}`;
        failures.push(msg);
        failedExampleIds.set(ref.refPath, check.reason || 'missing');
        continue;
      }

      // For files within extension directories, derive example ID from the
      // extension directory name.
      // e.g. flagship-local/FlagshipEffectComponent.tsx → flagship-local
      // e.g. __tests__/flagship-local-transition.test.ts → flagship-local
      const relToExt = relative(EXTENSIONS_DIR, absPath);
      const parts = relToExt.split('/');

      let exampleId;
      if (parts[0] === '__tests__') {
        // Test files: derive from the test filename, stripping .test.ts(x) suffix
        const testFile = basename(absPath);
        exampleId = testFile
          .replace(/\.(test|integration)\.(ts|tsx)$/, '')
          .replace(/\.(ts|tsx)$/, '');
      } else {
        // Non-test files: use the top-level extension directory name
        exampleId = parts[0];
      }

      if (exampleId && exampleId !== '..') {
        docsSafeExampleIds.add(exampleId);
      }
      console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId} (file)`);
    } else {
      // EXT reference points to a directory (e.g. flagship-local/)
      const check = checkExtDir(absPath);

      if (!check.exists) {
        const msg = `Supported extension directory ${refLabel} does not exist: ${check.reason}`;
        failures.push(msg);
        failedExampleIds.set(ref.refPath, check.reason || 'missing');
        continue;
      }

      // Check import boundary for the index.ts in the extension directory
      const indexFile = resolve(absPath, 'index.ts');
      if (existsSync(indexFile)) {
        const boundaryCheck = checkImportBoundary(indexFile);
        if (!boundaryCheck.clean) {
          for (const violation of boundaryCheck.violations) {
            const msg = `Supported extension example ${refLabel} has internal import: ${violation}`;
            if (isRelease) {
              failures.push(msg);
            } else {
              warnings.push(msg);
            }
          }
          if (isRelease) {
            failedExampleIds.set(ref.refPath, 'internal-imports');
            continue;
          }
        }
      }

      // Derive a stable example ID from the directory name
      const exampleId = basename(absPath);
      docsSafeExampleIds.add(exampleId);
      console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId}`);
    }
  }
}

// ---- Step 6: Check for on-disk example files with no supported matrix row ----
console.log(`\n${LABEL} Checking for unclassified on-disk examples…`);

/**
 * Collect all example files in src/examples/
 * @returns {string[]}
 */
function listExampleFiles() {
  if (!existsSync(EXAMPLES_DIR)) return [];

  try {
    return readdirSync(EXAMPLES_DIR)
      .filter((f) => f.endsWith('.ts') || f.endsWith('.tsx'))
      .map((f) => resolve(EXAMPLES_DIR, f));
  } catch {
    return [];
  }
}

const onDiskExamples = listExampleFiles();

// Build a set of resolved paths from supported example refs
const resolvedSupportedExPaths = new Set();
for (const ref of supportedExampleRefs) {
  if (ref.refType === 'EX') {
    resolvedSupportedExPaths.add(resolveExPath(ref.refPath));
  }
}

// Build a set of resolved paths from unsupported example refs
const resolvedUnsupportedExPaths = new Set();
for (const ref of unsupportedExampleRefs) {
  if (ref.refType === 'EX') {
    resolvedUnsupportedExPaths.add(resolveExPath(ref.refPath));
  }
}

for (const absPath of onDiskExamples) {
  const relPath = relative(repoRoot, absPath);

  if (resolvedSupportedExPaths.has(absPath)) {
    // Already accounted for
    continue;
  }

  if (resolvedUnsupportedExPaths.has(absPath)) {
    // Example exists for a deferred/unsupported behaviour — flag it
    const msg =
      `Example "${relPath}" exists on disk but corresponds to deferred/unsupported behaviour. ` +
      `This is an unsupported docs candidate. Either reclassify the matrix row or remove the example.`;
    failures.push(`[unsupported-docs-candidate] ${msg}`);
    continue;
  }

  // Unclassified example on disk
  const msg =
    `Example "${relPath}" exists on disk but has no corresponding row in the ` +
    `supported/deferred matrix. Add a supported row with EX: evidence, or ` +
    `document the file as deferred/unsupported.`;
  if (isRelease) {
    failures.push(`[unclassified-example] ${msg}`);
  } else {
    warnings.push(`[unclassified-example] ${msg}`);
  }
}

// ---- Step 7: Check for unsupported example refs that resolve to existing files ----
console.log(`\n${LABEL} Checking unsupported-docs-candidate references…`);

for (const ref of unsupportedExampleRefs) {
  const refLabel = `${ref.refType}:${ref.refPath} (${ref.classification} row ${ref.sourceRowId})`;

  let exists = false;

  if (ref.refType === 'EX') {
    const absPath = resolveExPath(ref.refPath);
    exists = existsSync(absPath) && statSync(absPath).isFile();
  } else if (ref.refType === 'EXT') {
    const { absPath, isFile } = resolveExtPath(ref.refPath);
    if (isFile) {
      exists = existsSync(absPath) && statSync(absPath).isFile();
    } else {
      exists = existsSync(absPath) && statSync(absPath).isDirectory();
    }
  }

  if (exists) {
    const msg =
      `Example ${refLabel} exists on disk but is classified as "${ref.classification}" ` +
      `in the supported/deferred matrix. This is an unsupported docs candidate — ` +
      `docs must not reference deferred/unsupported behaviour.`;
    failures.push(`[unsupported-docs-candidate] ${msg}`);
  }
}

// ---- Step 8: Report ----
console.log(`\n${LABEL} === Results ===\n`);

if (failures.length > 0) {
  console.error(`${LABEL} FAILURES (${failures.length}):`);
  for (const f of failures) {
    console.error(`  ✗ ${f}`);
  }
}

if (warnings.length > 0) {
  console.warn(`${LABEL} WARNINGS (${warnings.length}):`);
  for (const w of warnings) {
    console.warn(`  ⚠ ${w}`);
  }
}

// ---- Machine-readable output ----
const sortedIds = [...docsSafeExampleIds].sort();
const machineOutput = {
  docsSafeExampleIds: sortedIds,
  failedExampleIds: [...failedExampleIds.keys()].sort(),
  summary: {
    totalSupportedRefs: supportedExampleRefs.length,
    totalFailed: failedExampleIds.size,
    totalSafe: sortedIds.length,
    unsupportedCandidates: unsupportedExampleRefs.length,
    unclassifiedWarnings: warnings.filter((w) =>
      w.startsWith('[unclassified-example]'),
    ).length,
  },
};

console.log(`\n${LABEL} Machine-readable output:`);
console.log(JSON.stringify(machineOutput));

// ---- Exit decision ----
if (failures.length > 0) {
  const failureText = failures.length === 1 ? 'failure' : 'failures';
  console.error(
    `\n${LABEL} ${mode.toUpperCase()} FAILED with ${failures.length} ${failureText}.`,
  );
  // Write a non-zero exit for tooling
  process.exitCode = 1;
} else {
  console.log(
    `\n${LABEL} ${mode.toUpperCase()} PASSED. ` +
      `${sortedIds.length} docs-safe example(s), ${warnings.length} warning(s).`,
  );
}

// Ensure the JSON was written as the last substantive output
// (process.exit handles the flush)
