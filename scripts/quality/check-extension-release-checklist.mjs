#!/usr/bin/env node
/**
 * M15 Extension Platform Release Checklist Gate
 *
 * Loads the canonical release checklist
 * (`docs/video-editor/extension-platform-release-checklist.md`) and validates
 * that every release-blocking row has verifiable evidence.  In release mode,
 * any release-blocking row with missing / unresolvable evidence causes a hard
 * failure.
 *
 * ## Modes
 *
 *   --audit     (default)  Report missing evidence and unresolvable references
 *                          as warnings.  Only exit non-zero when the checklist
 *                          itself cannot be parsed or is structurally invalid.
 *
 *   --release              Apply strict release rules: every release-blocking
 *                          row MUST have evidence that resolves to an existing
 *                          artifact (file, gate output, or matrix row).  Any
 *                          release-blocking gap causes a hard failure.
 *
 * ## Evidence resolution
 *
 * The gate resolves evidence references by:
 *   1. Checking file paths — paths containing `/` and a recognised extension
 *      (`.ts`, `.tsx`, `.md`, `.json`, `.mjs`, `.yaml`) are checked on disk.
 *   2. Checking gate scripts — references to `scripts/quality/check-*.mjs`
 *      are verified to exist.
 *   3. Checking matrix rows — references to `S-###`, `D-###`, `CR:*`, `M#-###`
 *      are resolved against the contract-recheck and supported/deferred matrices.
 *   4. Checking npm scripts — references like `npm run <name>` are verified
 *      against `package.json`.
 *
 * ## Dependencies
 *
 * Uses the shared matrix helper (`./lib/extension-contract-matrix.mjs`) for
 * consistent status/disposition predicates and matrix loading (SD1).
 */

import { readFileSync, existsSync, statSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  loadContractMatrix,
  isReleaseBlocking,
  isSupported,
  isDeferred,
  isUnsupported,
} from './lib/extension-contract-matrix.mjs';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const CHECKLIST_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-release-checklist.md',
);

const SUPPORTED_DEFERRED_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);

const PACKAGE_JSON_PATH = resolve(repoRoot, 'package.json');

const LABEL = '[release-checklist]';

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
// Types
// ---------------------------------------------------------------------------

/**
 * @typedef {object} ChecklistRow
 * @property {string}   num        – item number (e.g. "1", "42")
 * @property {string}   domain     – evidence domain
 * @property {string}   check      – what must be true
 * @property {string}   evidence   – raw evidence string
 * @property {boolean}  releaseBlocking – true when Release? = "yes"
 * @property {number}   lineNumber – approximate line in source doc
 */

/**
 * @typedef {object} EvidenceResult
 * @property {boolean}  resolved   – true when at least one reference resolved
 * @property {string[]} resolvedPaths – paths/files that were found
 * @property {string[]} unresolvedRefs – references that could not be resolved
 */

// ---------------------------------------------------------------------------
// Checklist parser
// ---------------------------------------------------------------------------

/**
 * Parse the release checklist markdown and return structured rows from § 2.
 *
 * § 2 contains multiple sub-section tables (2.1–2.10).  Each table has:
 *   | # | Domain | Check | Evidence | Release? |
 *
 * @returns {ChecklistRow[]}
 */
function parseChecklist() {
  if (!existsSync(CHECKLIST_PATH)) {
    throw new Error(`Release checklist not found: ${CHECKLIST_PATH}`);
  }

  const markdown = readFileSync(CHECKLIST_PATH, 'utf8');
  const lines = markdown.split('\n');

  /** @type {ChecklistRow[]} */
  const rows = [];

  // State machine
  let inSection2 = false;       // inside § 2
  let inSubTable = false;       // inside a sub-table (detected header row)
  let headerCells = null;       // the header cells of the current table
  let currentSubSection = '';   // e.g. "2.1 SDK Boundary & Public Exports"

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    const lineNum = i + 1;

    // ---- Section detection ----
    if (trimmed.startsWith('## 2. Release Checklist')) {
      inSection2 = true;
      inSubTable = false;
      headerCells = null;
      continue;
    }

    if (trimmed.startsWith('## 3.') || trimmed.startsWith('## 4.')) {
      inSection2 = false;
      inSubTable = false;
      headerCells = null;
      continue;
    }

    if (!inSection2) continue;

    // ---- Sub-section detection (§ 2.1 – 2.10) ----
    const subMatch = trimmed.match(/^###\s+2\.\d+\s+(.+)/);
    if (subMatch) {
      currentSubSection = subMatch[1].trim();
      inSubTable = false;
      headerCells = null;
      continue;
    }

    // ---- Table row detection ----
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());

      // Separator row
      if (cells.every((c) => /^:?-{3,}:?$/.test(c))) {
        inSubTable = true; // we've seen the header -> separator sequence
        continue;
      }

      // Header row detection
      if (!inSubTable && !headerCells) {
        // Check if this looks like a header row
        const hasHash = cells.some((c) => c === '#');
        const hasDomain = cells.some((c) => /^Domain$/i.test(c));
        const hasCheck = cells.some((c) => /^Check$/i.test(c));
        const hasEvidence = cells.some((c) => /^Evidence$/i.test(c));
        const hasRelease = cells.some((c) => /^Release\?$/i.test(c));

        if (hasHash && hasDomain && hasCheck && hasEvidence && hasRelease) {
          headerCells = cells;
          // Next line should be separator, which sets inSubTable = true
          continue;
        }

        // May also be a non-header row before we've seen the separator
        // (e.g. section 1.1 tables). Skip unless we're in a sub-table.
        continue;
      }

      // Data row
      if (inSubTable && cells.length >= 5) {
        const num = cells[0] || '';
        // Skip non-numeric rows (may be subsection headers or other content)
        if (!/^\d+$/.test(num)) continue;

        const domain = cells[1] || '';
        const check = cells[2] || '';
        const evidence = cells[3] || '';
        const releaseCol = (cells[4] || '').toLowerCase().trim();
        const releaseBlocking = releaseCol === 'yes';

        rows.push({
          num,
          domain,
          check,
          evidence,
          releaseBlocking,
          lineNumber: lineNum,
        });
      }

      continue;
    }

    // ---- Non-table line resets sub-table state ----
    if (trimmed.length > 0 && !trimmed.startsWith('|')) {
      inSubTable = false;
      headerCells = null;
    }
  }

  return rows;
}

// ---------------------------------------------------------------------------
// Evidence resolution
// ---------------------------------------------------------------------------

/**
 * Extract individual evidence references from an evidence string.
 *
 * Splits on `;` first (major groups), then `,` within groups for file lists.
 * Recognises these reference types:
 *   - File paths: `src/...`, `docs/...`, `scripts/...`, `config/...`
 *   - npm scripts: `npm run <name>`
 *   - Matrix row IDs: `S-###`, `D-###`, `CR:*`, `M#-###`
 *   - Gate script refs: `scripts/quality/check-*.mjs`
 *
 * @param {string} evidence
 * @returns {string[]}
 */
function extractReferences(evidence) {
  /** @type {string[]} */
  const refs = [];

  // Split on semicolons for major groups
  const groups = evidence.split(';');

  for (const group of groups) {
    const trimmed = group.trim();

    // npm run references
    const npmMatch = trimmed.match(/`npm run ([a-z][a-z0-9:_-]*)`/);
    if (npmMatch) {
      refs.push(`npm:${npmMatch[1]}`);
      continue;
    }

    // Backtick-quoted file paths
    const backtickRe = /`([^`]+)`/g;
    let match;
    while ((match = backtickRe.exec(trimmed)) !== null) {
      const inner = match[1].trim();
      // Skip if it looks like an npm command we already captured
      if (inner.startsWith('npm run ')) continue;
      refs.push(inner);
    }

    // Bare file paths (src/, docs/, scripts/, config/, vendor/)
    const bareRe =
      /\b((?:src|docs|scripts|config|vendor)\/[^\s,;)]+(?:\.(?:ts|tsx|js|jsx|json|md|mjs|yaml|yml|toml|css)))\b/g;
    while ((match = bareRe.exec(trimmed)) !== null) {
      const p = match[1].replace(/[;,)]+$/, '');
      if (!refs.includes(p)) refs.push(p);
    }

    // Matrix row IDs: S-###, D-###, M#-###, CR:*
    const rowIdRe = /\b([SD]-\d{3}|M\d+-\d{3}|CR:[A-Za-z]+-\d+)\b/g;
    while ((match = rowIdRe.exec(trimmed)) !== null) {
      const id = match[1];
      if (!refs.includes(id)) refs.push(id);
    }
  }

  return refs;
}

/**
 * Check that a file path reference exists on disk.
 *
 * @param {string} ref
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkFileExists(ref) {
  // Strip any trailing parenthetical notes like "(2023 lines)"
  const cleaned = ref.replace(/\s*\([^)]*\)\s*$/, '').trim();
  const absPath = resolve(repoRoot, cleaned);

  if (!existsSync(absPath)) {
    return { exists: false, reason: `File not found: ${cleaned}` };
  }

  try {
    const stat = statSync(absPath);
    if (!stat.isFile() && !stat.isDirectory()) {
      return { exists: false, reason: `Not a file or directory: ${cleaned}` };
    }
  } catch {
    return { exists: false, reason: `Cannot stat: ${cleaned}` };
  }

  return { exists: true };
}

/**
 * Check that an npm script exists in package.json.
 *
 * @param {string} scriptName
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkNpmScript(scriptName) {
  try {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf8'));
    if (pkg.scripts && typeof pkg.scripts[scriptName] === 'string') {
      return { exists: true };
    }
    return {
      exists: false,
      reason: `npm script "${scriptName}" not found in package.json`,
    };
  } catch (err) {
    return {
      exists: false,
      reason: `Cannot read package.json: ${err.message}`,
    };
  }
}

/**
 * Resolve a matrix row ID reference against the loaded matrices.
 *
 * @param {string} ref            – e.g. "S-017", "M1-001", "CR:M2-013"
 * @param {object[]} matrixRows   – contract-recheck matrix rows
 * @param {Set<string>} sdRowIds  – supported/deferred row IDs
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkMatrixRowRef(ref, matrixRows, sdRowIds) {
  // Supported/deferred row IDs
  if (/^[SD]-\d{3}$/.test(ref)) {
    if (sdRowIds.has(ref)) {
      return { exists: true };
    }
    return {
      exists: false,
      reason: `Matrix row "${ref}" not found in supported/deferred matrix`,
    };
  }

  // Contract-recheck row IDs (M#-###)
  if (/^M\d+-\d{3}$/.test(ref)) {
    const found = matrixRows.some((r) => r.rowId === ref);
    if (found) return { exists: true };
    return {
      exists: false,
      reason: `Matrix row "${ref}" not found in contract-recheck matrix`,
    };
  }

  // CR: cross-references
  if (ref.startsWith('CR:')) {
    // These are resolved against the contract-recheck matrix
    const crId = ref.slice(3);
    const found = matrixRows.some((r) => r.rowId === crId);
    if (found) return { exists: true };
    return {
      exists: false,
      reason: `Cross-reference "${ref}" not found in contract-recheck matrix`,
    };
  }

  return { exists: false, reason: `Unrecognised matrix row ID format: "${ref}"` };
}

// ---------------------------------------------------------------------------
// Row-level evidence validation
// ---------------------------------------------------------------------------

/**
 * Validate a single checklist row's evidence references.
 *
 * @param {ChecklistRow} row
 * @param {object[]} matrixRows
 * @param {Set<string>} sdRowIds
 * @returns {{ allResolved: boolean, results: EvidenceResult[] }}
 */
function validateRowEvidence(row, matrixRows, sdRowIds) {
  const refs = extractReferences(row.evidence);

  if (refs.length === 0) {
    // No parseable references — this is a failure for release-blocking rows
    return {
      allResolved: false,
      results: [
        {
          resolved: false,
          resolvedPaths: [],
          unresolvedRefs: ['<no parseable references>'],
        },
      ],
    };
  }

  /** @type {EvidenceResult[]} */
  const results = [];
  let allResolved = true;

  for (const ref of refs) {
    /** @type {EvidenceResult} */
    let result = {
      resolved: false,
      resolvedPaths: [],
      unresolvedRefs: [],
    };

    // npm script reference
    if (ref.startsWith('npm:')) {
      const scriptName = ref.slice(4);
      const check = checkNpmScript(scriptName);
      if (check.exists) {
        result.resolved = true;
        result.resolvedPaths.push(`npm run ${scriptName}`);
      } else {
        result.unresolvedRefs.push(ref);
        allResolved = false;
      }
      results.push(result);
      continue;
    }

    // Matrix row ID
    if (/^[SD]-\d{3}$/.test(ref) || /^M\d+-\d{3}$/.test(ref) || ref.startsWith('CR:')) {
      const check = checkMatrixRowRef(ref, matrixRows, sdRowIds);
      if (check.exists) {
        result.resolved = true;
        result.resolvedPaths.push(ref);
      } else {
        result.unresolvedRefs.push(check.reason || ref);
        allResolved = false;
      }
      results.push(result);
      continue;
    }

    // File path reference
    if (
      ref.includes('/') ||
      /\.(ts|tsx|js|jsx|json|md|mjs|yaml|yml|toml|css)$/.test(ref)
    ) {
      const check = checkFileExists(ref);
      if (check.exists) {
        result.resolved = true;
        result.resolvedPaths.push(ref);
      } else {
        result.unresolvedRefs.push(check.reason || ref);
        allResolved = false;
      }
      results.push(result);
      continue;
    }

    // Unrecognised reference format
    result.unresolvedRefs.push(`Unrecognised reference: "${ref}"`);
    allResolved = false;
    results.push(result);
  }

  return { allResolved, results };
}

// ---------------------------------------------------------------------------
// Load supported/deferred matrix row IDs
// ---------------------------------------------------------------------------

/**
 * Parse the supported/deferred matrix to extract all row IDs.
 *
 * @returns {Set<string>}
 */
function loadSdRowIds() {
  const ids = new Set();

  if (!existsSync(SUPPORTED_DEFERRED_PATH)) {
    console.warn(
      `${LABEL} Supported/deferred matrix not found: ${SUPPORTED_DEFERRED_PATH}`,
    );
    return ids;
  }

  try {
    const markdown = readFileSync(SUPPORTED_DEFERRED_PATH, 'utf8');
    const lines = markdown.split('\n');

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        const cells = trimmed
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

        const rowId = cells[0] || '';
        if (/^[SD]-\d{3}$/.test(rowId)) {
          ids.add(rowId);
        }
      }
    }
  } catch (err) {
    console.warn(
      `${LABEL} Failed to parse supported/deferred matrix: ${err.message}`,
    );
  }

  return ids;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);

// ---- Step 1: Parse the checklist ----
/** @type {ChecklistRow[]} */
let rows = [];

try {
  rows = parseChecklist();
  console.log(`${LABEL} Parsed ${rows.length} checklist row(s).`);
} catch (err) {
  console.error(`${LABEL} Failed to parse checklist: ${err.message}`);
  process.exit(1);
}

if (rows.length === 0) {
  console.error(`${LABEL} No checklist rows found. The checklist appears empty.`);
  process.exit(1);
}

// ---- Step 2: Load matrices for cross-reference ----
let matrixRows = [];
let blockerRows = [];

try {
  const matrix = loadContractMatrix();
  matrixRows = matrix.matrixRows;
  blockerRows = matrix.blockerRows;
  console.log(
    `${LABEL} Loaded ${matrixRows.length} contract-recheck row(s) and ${blockerRows.length} blocker row(s).`,
  );
} catch (err) {
  console.warn(
    `${LABEL} Could not load contract-recheck matrix: ${err.message}. Cross-reference resolution will be limited.`,
  );
}

const sdRowIds = loadSdRowIds();
console.log(
  `${LABEL} Loaded ${sdRowIds.size} supported/deferred row ID(s).`,
);

// ---- Step 3: Validate every row ----
console.log(`${LABEL} Validating ${rows.length} row(s)…`);

/** @type {string[]} */
const failures = [];
/** @type {string[]} */
const warnings = [];

// Tally release-blocking rows
const releaseBlockingRows = rows.filter((r) => r.releaseBlocking);
const auditOnlyRows = rows.filter((r) => !r.releaseBlocking);

console.log(
  `${LABEL} ${releaseBlockingRows.length} release-blocking row(s), ${auditOnlyRows.length} audit-only row(s).`,
);

for (const row of rows) {
  const label = `#${row.num} [${row.domain}]`;

  // Validate evidence
  const { allResolved, results } = validateRowEvidence(
    row,
    matrixRows,
    sdRowIds,
  );

  if (!allResolved) {
    for (const result of results) {
      if (!result.resolved) {
        const unresolvedList = result.unresolvedRefs.join(', ');
        const msg = `${label}: ${row.check.substring(0, 80)}... — unresolved: ${unresolvedList}`;

        if (row.releaseBlocking && isRelease) {
          failures.push(`[evidence-unresolved] ${msg}`);
        } else if (row.releaseBlocking) {
          // Release-blocking but in audit mode → warning
          warnings.push(`[release-blocking-audit] ${msg}`);
        } else {
          // Audit-only row → warning
          warnings.push(`[audit] ${msg}`);
        }
      }
    }
  }

  // Check for contract-recheck release-blocking cross-reference
  if (
    row.releaseBlocking &&
    (row.domain === 'Contract' || row.domain === 'Deferred')
  ) {
    // Verify that the contract-recheck matrix has no release-blocking rows
    // (checked at the aggregate level below)
  }
}

// ---- Step 4: Cross-check contract-recheck release-blocking rows ----
const crReleaseBlockingRows = matrixRows.filter((r) => isReleaseBlocking(r));
if (crReleaseBlockingRows.length > 0) {
  const blockerList = crReleaseBlockingRows
    .map((r) => r.rowId)
    .join(', ');
  const msg = `Contract-recheck matrix has ${crReleaseBlockingRows.length} release-blocking row(s): ${blockerList}`;
  if (isRelease) {
    failures.push(`[contract-recheck-release-blocking] ${msg}`);
  } else {
    warnings.push(`[contract-recheck-release-blocking] ${msg}`);
  }
}

// ---- Step 5: Summary statistics ----
console.log(`${LABEL} Summary:`);
console.log(`${LABEL}   Total rows:               ${rows.length}`);
console.log(`${LABEL}   Release-blocking rows:    ${releaseBlockingRows.length}`);
console.log(`${LABEL}   Audit-only rows:          ${auditOnlyRows.length}`);

const passedReleaseBlocking =
  releaseBlockingRows.length -
  failures.filter((f) => f.includes('[evidence-unresolved]')).length;
console.log(`${LABEL}   Release-blocking passed:  ${Math.max(0, passedReleaseBlocking)}`);

// ---- Step 6: Report ----
if (failures.length > 0) {
  console.error(`${LABEL} FAILURES (${failures.length}):`);
  for (const f of failures) {
    console.error(`${LABEL}   FAIL: ${f}`);
  }
}

if (warnings.length > 0) {
  console.warn(`${LABEL} WARNINGS (${warnings.length}):`);
  for (const w of warnings) {
    console.warn(`${LABEL}   WARN: ${w}`);
  }
}

// ---- Step 7: Exit decision ----
const hasFailures = failures.length > 0;

if (hasFailures) {
  console.error(
    `${LABEL} ${mode.toUpperCase()} FAILED with ${failures.length} failure(s) and ${warnings.length} warning(s).`,
  );
  process.exit(1);
}

console.log(
  `${LABEL} ${mode.toUpperCase()} PASSED. ` +
  `${rows.length} row(s) validated, ${warnings.length} warning(s).`,
);
process.exit(0);
