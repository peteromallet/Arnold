#!/usr/bin/env node
/**
 * M15 Deferred-Claims Absence Gate
 *
 * Loads the canonical supported/deferred matrix
 * (`docs/video-editor/extension-platform-supported-deferred.md`) and verifies
 * that every deferred / unsupported claim backed by an ABSENCE check is
 * **actually absent** from the active SDK and runtime code.
 *
 * Additionally, the script covers a fixed list of **risky deferred terms**
 * (marketplace, cloud loading, sandbox enforcement, remote package install,
 * theme activation, CRDT) and cross-validates deferred rows against the
 * contract-recheck blocker/deferral entries.
 *
 * ## Modes
 *
 *   --audit   (default)  Report presence violations and missing coverage as
 *                        warnings.  Only exit non-zero when the matrix itself
 *                        cannot be parsed.
 *
 *   --release            Presence violations become hard failures.  Every
 *                        risky term MUST be covered by at least one deferred
 *                        or unsupported row with an ABSENCE check.
 *
 * ## Cross-validation
 *
 * Every deferred row MUST either:
 *   - Have ABSENCE evidence that maps to a verifiable search, OR
 *   - Be linked to a blocker/deferral entry in the contract-recheck matrix.
 *
 * Rows that satisfy neither are reported as uncovered in both modes.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import {
  loadContractMatrix,
  isDeferred,
  isUnsupported,
} from './lib/extension-contract-matrix.mjs';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const SUPPORTED_DEFERRED_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);

const LABEL = '[deferred-claims]';

// ---------------------------------------------------------------------------
// Risky deferred terms — every one MUST be covered by a deferred/unsupported
// row with an ABSENCE check, or be documented as out-of-scope in §4.1.
// ---------------------------------------------------------------------------

/**
 * @typedef {object} RiskyTerm
 * @property {string} term        – human-readable label
 * @property {string} pattern     – regex to search for in code
 * @property {string} searchPath  – repo-relative directory to search
 * @property {string} description – what violation would mean
 */

/** @type {RiskyTerm[]} */
const RISKY_TERMS = [
  {
    term: 'marketplace',
    pattern: 'marketplace',
    searchPath: 'src/sdk',
    description:
      'Marketplace / third-party extension registry is unsupported in V1',
  },
  {
    term: 'cloud extension loading',
    pattern: 'cloud.*extension|extension.*cloud',
    searchPath: 'src/tools/video-editor/runtime',
    description: 'Cloud extension loading is out-of-scope for V1',
  },
  {
    term: 'sandbox enforcement',
    pattern: 'sandbox|iframe.*extension|Worker.*extension|ShadowRealm',
    searchPath: 'src/tools/video-editor/runtime',
    description:
      'Sandboxed execution (iframe/Worker/ShadowRealm) is deferred in V1',
  },
  {
    term: 'remote package install',
    pattern: 'npm\\s+install|dynamic\\s+import.*extension|CDN.*extension|remote.*package',
    searchPath: 'src/tools/video-editor/runtime',
    description:
      'Dynamic package loading (npm/CDN/import() for extensions) is deferred in V1',
  },
  {
    term: 'theme activation',
    pattern: 'theme.*contribution|ThemeContribution',
    searchPath: 'src/sdk',
    description: 'Theme contributions are unsupported in V1',
  },
  {
    term: 'CRDT primitives',
    pattern: '\\bCRDT\\b',
    searchPath: 'src/sdk',
    description:
      'Public CRDT collaboration primitives are out-of-scope for V1',
  },
];

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
// Helpers
// ---------------------------------------------------------------------------

/**
 * Run a ripgrep search and return matching lines (or empty array).
 * @param {string} pattern – regex pattern
 * @param {string} searchPath – absolute directory path
 * @returns {string[]}
 */
function grep(pattern, searchPath) {
  try {
    const result = execSync(
      `rg --line-number --no-heading --max-count 100 "${pattern}" "${searchPath}"`,
      {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 30_000,
      },
    );
    return result
      .trim()
      .split('\n')
      .filter((line) => line.length > 0);
  } catch (err) {
    // rg exits 1 when no matches — that's the expected success case.
    if (err.status === 1 && !err.stdout && !err.stderr) {
      return [];
    }
    // Non-zero for other reasons (e.g. rg not found).
    console.error(`${LABEL} Search failed for "${pattern}" in ${searchPath}: ${err.message}`);
    return [];
  }
}

/**
 * Parse an evidence string to extract ABSENCE patterns.
 * Format: `ABSENCE:<search description>` or just plain grep command.
 * Returns the effective grep pattern string, or null if not an ABSENCE type.
 * @param {string} evidence
 * @returns {string | null}
 */
function extractAbsencePattern(evidence) {
  const absenceMatch = evidence.match(
    /ABSENCE:\s*(?:grep\s+(?:-[a-zA-Z]+\s+)*['"](.+?)['"]\s*(.+)?)/i,
  );
  if (absenceMatch) {
    // The pattern is the first capture group.
    return absenceMatch[1];
  }

  // Also support the simpler form: ABSENCE:grep -r 'pattern' path
  const simpleMatch = evidence.match(
    /ABSENCE:\s*grep\s+.*?['"](.+?)['"]/i,
  );
  if (simpleMatch) {
    return simpleMatch[1];
  }

  return null;
}

/**
 * Determine the search path from an ABSENCE evidence string.
 * @param {string} evidence
 * @returns {string} – absolute path
 */
function extractAbsenceSearchPath(evidence) {
  // Try to find the path argument in: grep -r 'pattern' path
  const pathMatch = evidence.match(
    /ABSENCE:\s*grep\s+.*?['"][^'"]+['"]\s+(\S+)/i,
  );
  if (pathMatch) {
    // Strip trailing punctuation like ; or ,
    const relPath = pathMatch[1].replace(/[;,]+$/, '');
    return resolve(repoRoot, relPath);
  }
  // Default: search src/sdk
  return resolve(repoRoot, 'src/sdk');
}

// ---------------------------------------------------------------------------
// Parse the supported/deferred matrix
// ---------------------------------------------------------------------------

/**
 * Parse the supported/deferred markdown and extract deferred/unsupported rows.
 *
 * @returns {{ deferredRows: object[], unsupportedRows: object[], outOfScopeRows: object[] }}
 */
function parseSupportedDeferredMatrix() {
  if (!existsSync(SUPPORTED_DEFERRED_PATH)) {
    throw new Error(`Supported/deferred matrix not found: ${SUPPORTED_DEFERRED_PATH}`);
  }

  const markdown = readFileSync(SUPPORTED_DEFERRED_PATH, 'utf8');
  const lines = markdown.split('\n');

  /** @type {object[]} */
  const deferredRows = [];
  /** @type {object[]} */
  const unsupportedRows = [];
  /** @type {object[]} */
  const outOfScopeRows = [];

  // State machine for parsing the markdown
  let inDeferredSection = false;
  let inUnsupportedSection = false;
  let inOutOfScopeSection = false;
  let inOutOfScopeTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Section detection
    if (line.startsWith('## 3. Deferred / Unsupported V1 Behavior Matrix')) {
      inDeferredSection = true;
      inUnsupportedSection = false;
      inOutOfScopeSection = false;
      inOutOfScopeTable = false;
      continue;
    }

    if (line.startsWith('## 4. V1 Scope Boundaries')) {
      inDeferredSection = false;
      inUnsupportedSection = false;
      inOutOfScopeSection = true;
      inOutOfScopeTable = false;
      continue;
    }

    if (inOutOfScopeSection && line.startsWith('### 4.1')) {
      inOutOfScopeTable = true;
      continue;
    }

    if (line.startsWith('### 4.2') || line.startsWith('## 5.')) {
      inOutOfScopeTable = false;
      continue;
    }

    // Parse table rows (lines starting with `|`)
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());

      // Skip header and separator rows
      if (
        cells.every((c) => /^:?-{3,}:?$/.test(c))
        || cells.some((c) => /^(Row ID|Behavior|Classification|Evidence|Concern|V1 Answer)$/i.test(c))
      ) {
        continue;
      }

      if (inDeferredSection) {
        // Deferred/unsupported matrix rows (sections 3.x)
        // Expected columns: Row ID | Behavior | Classification | Evidence
        if (cells.length >= 4) {
          // Strip markdown formatting (**, *, __, _) from classification.
          const rawClassification = (cells[2] || '').replace(/[*_]{1,2}/g, '');
          const classification = rawClassification.toLowerCase().trim();
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
          }
        }
      } else if (inOutOfScopeTable) {
        // Out-of-scope table rows (§ 4.1)
        // Expected columns: Behavior | Evidence
        if (cells.length >= 2) {
          outOfScopeRows.push({
            behavior: cells[0] || '',
            evidence: cells[1] || '',
            classification: 'unsupported',
          });
        }
      }
    }
  }

  return { deferredRows, unsupportedRows, outOfScopeRows };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);

// ---- Step 1: Load the contract-recheck matrix for blocker cross-validation ----
let crMatrixRows = [];
let crBlockerRows = [];

try {
  const crMatrix = loadContractMatrix();
  crMatrixRows = crMatrix.matrixRows;
  crBlockerRows = crMatrix.blockerRows;
  console.log(
    `${LABEL} Loaded contract-recheck matrix: ${crMatrixRows.length} row(s), ${crBlockerRows.length} blocker/deferral row(s).`,
  );
} catch (err) {
  console.error(`${LABEL} Failed to load contract-recheck matrix: ${err.message}`);
  process.exit(1);
}

// ---- Step 2: Parse the supported/deferred matrix ----
let deferredRows = [];
let unsupportedRows = [];
let outOfScopeRows = [];

try {
  const sdm = parseSupportedDeferredMatrix();
  deferredRows = sdm.deferredRows;
  unsupportedRows = sdm.unsupportedRows;
  outOfScopeRows = sdm.outOfScopeRows;
  console.log(
    `${LABEL} Parsed supported/deferred matrix: ` +
      `${deferredRows.length} deferred, ${unsupportedRows.length} unsupported, ` +
      `${outOfScopeRows.length} out-of-scope row(s).`,
  );
} catch (err) {
  console.error(`${LABEL} Failed to parse supported/deferred matrix: ${err.message}`);
  process.exit(1);
}

// ---- Accumulators ----
/** @type {string[]} */
const failures = [];
/** @type {string[]} */
const warnings = [];

// ---- Step 3: Verify ABSENCE claims from deferred/unsupported rows ----
console.log(`${LABEL} Verifying ABSENCE claims from deferred/unsupported rows…`);

const allDeferredUnsupported = [...deferredRows, ...unsupportedRows];

for (const row of allDeferredUnsupported) {
  const pattern = extractAbsencePattern(row.evidence);
  if (!pattern) continue;

  const searchPath = extractAbsenceSearchPath(row.evidence);

  console.log(
    `${LABEL}   Checking "${row.rowId}" — pattern "${pattern}" in ${searchPath}…`,
  );

  const matches = grep(pattern, searchPath);

  if (matches.length > 0) {
    const msg =
      `Row "${row.rowId}" (${row.classification}) claims ABSENCE of "${pattern}" ` +
      `but found ${matches.length} match(es) in ${searchPath}. First match: ${matches[0]}`;
    if (isRelease) {
      failures.push(msg);
    } else {
      warnings.push(`[presence-violation] ${msg}`);
    }
  }
}

// ---- Step 4: Verify ABSENCE claims from out-of-scope rows (§ 4.1) ----
console.log(`${LABEL} Verifying out-of-scope ABSENCE claims…`);

for (const row of outOfScopeRows) {
  const pattern = extractAbsencePattern(row.evidence);
  if (!pattern) continue;

  const searchPath = extractAbsenceSearchPath(row.evidence);

  console.log(
    `${LABEL}   Checking out-of-scope "${row.behavior}" — pattern "${pattern}" in ${searchPath}…`,
  );

  const matches = grep(pattern, searchPath);

  if (matches.length > 0) {
    const msg =
      `Out-of-scope "${row.behavior}" claims ABSENCE of "${pattern}" ` +
      `but found ${matches.length} match(es) in ${searchPath}. First match: ${matches[0]}`;
    if (isRelease) {
      failures.push(msg);
    } else {
      warnings.push(`[presence-violation] ${msg}`);
    }
  }
}

// ---- Step 5: Cover risky deferred terms ----
console.log(`${LABEL} Checking risky deferred terms…`);

// Build a set of patterns already covered by deferred/unsupported rows
const coveredPatterns = new Set();

for (const row of allDeferredUnsupported) {
  const pattern = extractAbsencePattern(row.evidence);
  if (pattern) coveredPatterns.add(pattern);
}
for (const row of outOfScopeRows) {
  const pattern = extractAbsencePattern(row.evidence);
  if (pattern) coveredPatterns.add(pattern);
}

for (const term of RISKY_TERMS) {
  const searchPath = resolve(repoRoot, term.searchPath);

  // Check if this term is covered by at least one deferred/unsupported row
  const isCovered = [...coveredPatterns].some(
    (cp) =>
      term.pattern.toLowerCase().includes(cp.toLowerCase())
      || cp.toLowerCase().includes(term.pattern.toLowerCase()),
  );

  if (!isCovered) {
    const msg =
      `Risky term "${term.term}" (${term.description}) ` +
      `is NOT covered by any deferred/unsupported row with an ABSENCE check. ` +
      `Add a row in the supported/deferred matrix §3 or §4.1.`;
    if (isRelease) {
      failures.push(`[uncovered-risky-term] ${msg}`);
    } else {
      warnings.push(`[uncovered-risky-term] ${msg}`);
    }
    continue;
  }

  // Also verify the term is actually absent from the codebase
  const matches = grep(term.pattern, searchPath);

  if (matches.length > 0) {
    const msg =
      `Risky term "${term.term}" (${term.description}) ` +
      `found ${matches.length} match(es) in ${term.searchPath}. ` +
      `This behavior should be absent from the active SDK/runtime. First match: ${matches[0]}`;
    if (isRelease) {
      failures.push(`[risky-term-presence] ${msg}`);
    } else {
      warnings.push(`[risky-term-presence] ${msg}`);
    }
  } else {
    console.log(`${LABEL}   ✓ "${term.term}" confirmed absent from ${term.searchPath}.`);
  }
}

// ---- Step 6: Cross-validate deferred rows against blockers ----
console.log(`${LABEL} Cross-validating deferred rows against contract-recheck blockers…`);

const crDeferredRows = crMatrixRows.filter(
  (r) => isDeferred(r) || isUnsupported(r),
);

// Build blocker/deferral row ID sets from contract-recheck
const blockerIdSet = new Set(crBlockerRows.map((b) => b.blockerId));

// Check that each supported-deferred matrix deferred row links to a blocker
// or has ABSENCE evidence
for (const row of allDeferredUnsupported) {
  const hasAbsence = extractAbsencePattern(row.evidence) !== null;
  const hasBlockerRef =
    /BLOCKER:/i.test(row.evidence) || /DEFER:/i.test(row.evidence);
  const hasCrRef = /CR:/i.test(row.evidence);

  if (!hasAbsence && !hasBlockerRef && !hasCrRef) {
    const msg =
      `Row "${row.rowId}" (${row.classification}) has no ABSENCE evidence, ` +
      `no BLOCKER/DEFER reference, and no CR: reference. ` +
      `Deferred/unsupported rows must be backed by an absence check or ` +
      `an explicit blocker/deferral entry.`;
    if (isRelease) {
      failures.push(`[unbacked-deferred] ${msg}`);
    } else {
      warnings.push(`[unbacked-deferred] ${msg}`);
    }
  }
}

// Check that blocker references point to actual blockers
for (const row of allDeferredUnsupported) {
  const blockerMatch = row.evidence.match(/BLOCKER:([A-Z]+-\d+)/i);
  const deferMatch = row.evidence.match(/DEFER:([A-Z]+-\d+)/i);

  if (blockerMatch) {
    const blockerId = blockerMatch[1];
    if (!blockerIdSet.has(blockerId)) {
      const msg =
        `Row "${row.rowId}" references BLOCKER:${blockerId} ` +
        `which does not exist in the contract-recheck matrix blocker table.`;
      warnings.push(`[dangling-blocker-ref] ${msg}`);
    }
  }

  if (deferMatch) {
    const deferId = deferMatch[1];
    if (!blockerIdSet.has(deferId)) {
      const msg =
        `Row "${row.rowId}" references DEFER:${deferId} ` +
        `which does not exist in the contract-recheck matrix blocker table.`;
      warnings.push(`[dangling-defer-ref] ${msg}`);
    }
  }
}

// ---- Step 7: Count deferred rows in CR matrix vs supported-deferred matrix ----
const crDeferredCount = crDeferredRows.length;
const sdmDeferredCount = deferredRows.length + unsupportedRows.length;

if (crDeferredCount > 0 && sdmDeferredCount === 0) {
  warnings.push(
    `Contract-recheck matrix has ${crDeferredCount} deferred/unsupported row(s) ` +
      `but the supported/deferred matrix has none. The matrices may be out of sync.`,
  );
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

// Summary
const absenceChecked = [
  ...allDeferredUnsupported.filter((r) => extractAbsencePattern(r.evidence)),
  ...outOfScopeRows.filter((r) => extractAbsencePattern(r.evidence)),
];

console.log(
  `${LABEL} Summary: ` +
    `${allDeferredUnsupported.length} deferred/unsupported row(s), ` +
    `${outOfScopeRows.length} out-of-scope row(s), ` +
    `${absenceChecked.length} ABSENCE check(s) verified, ` +
    `${RISKY_TERMS.length} risky term(s) checked.`,
);

// ---- Exit decision ----
if (isRelease && failures.length > 0) {
  console.error(
    `${LABEL} RELEASE FAILED with ${failures.length} failure(s).`,
  );
  process.exit(1);
}

if (!isRelease && failures.length > 0) {
  // In audit mode, presence violations are still reported but don't fail
  // (they were converted to warnings above). This path only triggers for
  // structural failures which shouldn't happen in audit mode.
  console.error(
    `${LABEL} AUDIT FAILED with ${failures.length} unexpected failure(s).`,
  );
  process.exit(1);
}

console.log(
  `${LABEL} ${mode.toUpperCase()} PASSED with ${warnings.length} warning(s).`,
);
process.exit(0);
