#!/usr/bin/env node
/**
 * M15 Frontend Closure Matrix Gate
 *
 * Loads the canonical frontend closure matrix
 * (`docs/video-editor/frontend-closure-matrix.md`) and validates:
 *
 *  1. Required columns are present on every primitive row.
 *  2. Evidence links resolve to existing files on disk.
 *  3. State coverage (empty / loading / error / disabled) is documented.
 *  4. Deferred / unsupported rows link to supported/deferred evidence or
 *     an absence-check / blocker.
 *
 * Uses the shared matrix helper (`extension-contract-matrix.mjs`) for
 * consistent status / disposition predicates and release semantics.
 *
 * ## Modes
 *
 *   --audit     (default)  Report gaps, blocked statuses, and deferred
 *                          dispositions as warnings.  Only exit non-zero
 *                          when rows are malformed or supported evidence
 *                          is missing.
 *
 *   --release              Apply strict release rules: missing evidence,
 *                          undocumented deferred linkage, and malformed
 *                          rows all cause a hard failure.
 *
 * Failures are visible in command output so the risk surface is transparent.
 */

import { readFileSync, existsSync, statSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  isSupported,
  isDeferred,
  isUnsupported,
  isReleaseBlocking,
  isPass,
  isGap,
  isBlocked,
  getRowStatus,
  getRowDisposition,
  VALID_STATUSES,
  VALID_DISPOSITIONS,
  loadContractMatrix,
} from './lib/extension-contract-matrix.mjs';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const FRONTEND_CLOSURE_PATH = resolve(
  repoRoot,
  'docs/video-editor/frontend-closure-matrix.md',
);

const SUPPORTED_DEFERRED_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);

const LABEL = '[frontend-closure]';

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
// Default is 'audit' when neither flag is present.

const isRelease = mode === 'release';

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

/**
 * Required columns for every frontend closure primitive row.
 * Unlike the contract-recheck matrix, these columns are extracted from
 * markdown section fields rather than a table, except for §13 which
 * uses a conventional table.
 */
export const REQUIRED_FC_COLUMNS = [
  'primitive',
  'hostAffordance',
  'uiStates',
  'accessibility',
  'evidence',
  'status',
  'disposition',
  'contractRecheck',
];

/**
 * The four UI states every primitive must document.
 */
const UI_STATE_NAMES = ['empty', 'loading', 'error', 'disabled'];

/** Status symbols used in state coverage cells. */
const VALID_STATE_SYMBOLS = new Set(['■', '□', '—']);

// ---------------------------------------------------------------------------
// Markdown parser — frontend closure matrix
// ---------------------------------------------------------------------------

/**
 * @typedef {object} FCRow
 * @property {string} primitive       – component / surface name
 * @property {string} hostAffordance  – slot name or host registration path
 * @property {string} uiStates        – raw UI states string
 * @property {string} accessibility   – ARIA / keyboard expectations
 * @property {string} evidence        – file paths, test references
 * @property {string} status          – 'pass' | 'gap' | 'blocked'
 * @property {string} disposition     – 'supported' | 'deferred' | 'unsupported' | 'release-blocking'
 * @property {string} contractRecheck – CR: row IDs
 * @property {number} lineNumber      – approximate line number in source doc
 */

/**
 * Parse the frontend-closure-matrix.md and return structured rows.
 *
 * The matrix uses two formats:
 *  - Sections 3–12: Each primitive is a sub-section with labeled fields
 *    (e.g. `- **Host affordance:** …`, `- **Status:** \`pass\``).
 *  - Section 13: A conventional GFM pipe table.
 *
 * Section 14 (accessibility gaps) and Section 15 (statistics) are NOT
 * primitive rows.
 *
 * @returns {FCRow[]}
 */
function parseFrontendClosureMatrix() {
  if (!existsSync(FRONTEND_CLOSURE_PATH)) {
    throw new Error(`Frontend closure matrix not found: ${FRONTEND_CLOSURE_PATH}`);
  }

  const markdown = readFileSync(FRONTEND_CLOSURE_PATH, 'utf8');
  const lines = markdown.split('\n');

  /** @type {FCRow[]} */
  const rows = [];

  // State machine tracking
  let currentSection = '';        // e.g. 'core-shell', 'active-surfaces', 'deferred-table'
  let inDeferredTable = false;   // inside §13 pipe table
  let inA11yGaps = false;        // inside §14 (skip)
  let inStatistics = false;      // inside §15 (skip)
  let inCrossReference = false;  // inside §16+ (skip)

  // For section-based primitives (§§3–12), we accumulate fields across
  // multiple lines and flush when we hit the next sub-section.
  /** @type {Partial<FCRow> | null} */
  let currentRow = null;
  /** @type {number} */
  let currentRowLine = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    const lineNum = i + 1;

    // ---- Section detection ----
    if (trimmed.startsWith('## 3. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'core-shell';
      inDeferredTable = false;
      inA11yGaps = false;
      inStatistics = false;
      inCrossReference = false;
      continue;
    }
    if (trimmed.startsWith('## 4. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'active-surfaces';
      continue;
    }
    if (trimmed.startsWith('## 5. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'reserved-canary';
      continue;
    }
    if (trimmed.startsWith('## 6. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'diagnostic';
      continue;
    }
    if (trimmed.startsWith('## 7. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'form-parameter';
      continue;
    }
    if (trimmed.startsWith('## 8. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'command-palette';
      continue;
    }
    if (trimmed.startsWith('## 9. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'proposal';
      continue;
    }
    if (trimmed.startsWith('## 10. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'inspector-properties';
      continue;
    }
    if (trimmed.startsWith('## 11. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'confirmation';
      continue;
    }
    if (trimmed.startsWith('## 12. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'preview-export';
      continue;
    }
    if (trimmed.startsWith('## 13. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'deferred-table';
      inDeferredTable = false; // wait for the pipe table
      continue;
    }
    if (trimmed.startsWith('## 14. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'a11y-gaps';
      inA11yGaps = true;
      inDeferredTable = false;
      continue;
    }
    if (trimmed.startsWith('## 15. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'statistics';
      inStatistics = true;
      inA11yGaps = false;
      inDeferredTable = false;
      continue;
    }
    if (trimmed.startsWith('## 16. ') || trimmed.startsWith('## 17. ')) {
      flushRow(currentRow, rows);
      currentRow = null;
      currentSection = 'appendix';
      inCrossReference = true;
      inStatistics = false;
      inA11yGaps = false;
      inDeferredTable = false;
      continue;
    }

    // Skip non-primitive sections
    if (inStatistics || inCrossReference) continue;
    if (inA11yGaps) {
      // §14 is cross-cutting gaps — not primitive rows, but we still
      // parse its table for awareness. For now, skip.
      continue;
    }

    // ---- Sub-section detection (§§3–12): ### X.Y PrimitiveName ----
    const subMatch = trimmed.match(/^###\s+\d+\.\d+\s+(.+)/);
    if (subMatch && !inDeferredTable) {
      flushRow(currentRow, rows);
      currentRow = {
        primitive: subMatch[1].trim(),
        hostAffordance: '',
        uiStates: '',
        accessibility: '',
        evidence: '',
        status: '',
        disposition: '',
        contractRecheck: '',
        lineNumber: lineNum,
      };
      currentRowLine = lineNum;
      continue;
    }

    // ---- §13 Deferred table ----
    if (currentSection === 'deferred-table') {
      // Detect the pipe table start
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        const cells = line
          .split('|')
          .slice(1, -1)
          .map((c) => c.trim());

        // Skip header and separator rows
        if (
          cells.every((c) => /^:?-{3,}:?$/.test(c)) ||
          cells.some((c) =>
            /^(Primitive|Host Affordance)$/i.test(c),
          )
        ) {
          inDeferredTable = true;
          continue;
        }

        if (inDeferredTable && cells.length >= 8) {
          const primitive = cells[0] || '';
          // Bold-stripped primitive name
          const primitiveClean = primitive.replace(/[*_]{1,2}/g, '').trim();

          rows.push({
            primitive: primitiveClean,
            hostAffordance: cells[1] || '',
            uiStates: cells[2] || '',
            accessibility: cells[3] || '',
            evidence: cells[4] || '',
            status: (cells[5] || '').replace(/`/g, '').trim(),
            disposition: (cells[6] || '').replace(/`/g, '').trim(),
            contractRecheck: cells[7] || '',
            lineNumber: lineNum,
          });
        }
      } else if (inDeferredTable && !trimmed.startsWith('|')) {
        // End of deferred table
        inDeferredTable = false;
      }
      continue;
    }

    // ---- Field extraction for section-based primitives (§§3–12) ----
    if (currentRow) {
      // Strip leading "- " or "  - " list marker before matching field names
      const fieldText = trimmed.replace(/^[-*]\s+/, '').trim();

      // **Host affordance:** value
      const haMatch = fieldText.match(/^\*\*Host affordance:\*\*\s*(.+)/i);
      if (haMatch) {
        currentRow.hostAffordance = haMatch[1].trim();
        continue;
      }

      // **UI states:** value (may be empty — states are on sub-lines)
      const uiMatch = fieldText.match(/^\*\*UI states:\*\*\s*(.*)/i);
      if (uiMatch) {
        currentRow.uiStates = (currentRow.uiStates || '') + (uiMatch[1]?.trim() || '');
        continue;
      }

      // UI state sub-lines: "  - **Empty:** ■ description"
      const stateSubMatch = trimmed.match(
        /^\s*[-*]\s*\*\*(Empty|Loading|Error|Disabled):\*\*\s*(.+)/i,
      );
      if (stateSubMatch && currentRow.uiStates !== undefined) {
        const stateName = stateSubMatch[1].toLowerCase();
        const stateDesc = stateSubMatch[2].trim();
        // Append to uiStates
        currentRow.uiStates =
          (currentRow.uiStates ? currentRow.uiStates + '\n' : '') +
          `${stateName}: ${stateDesc}`;
        continue;
      }

      // **Accessibility:** value
      const a11yMatch = fieldText.match(/^\*\*Accessibility:\*\*\s*(.+)/i);
      if (a11yMatch) {
        currentRow.accessibility = a11yMatch[1].trim();
        continue;
      }

      // **Evidence:** value
      const evMatch = fieldText.match(/^\*\*Evidence:\*\*\s*(.+)/i);
      if (evMatch) {
        currentRow.evidence = evMatch[1].trim();
        continue;
      }

      // **Status:** `value`
      const statusMatch = fieldText.match(
        /^\*\*Status:\*\*\s*`?(pass|gap|blocked)`?/i,
      );
      if (statusMatch) {
        currentRow.status = statusMatch[1].toLowerCase().trim();
        continue;
      }

      // **Disposition:** `value` (may have parenthetical note)
      const dispMatch = fieldText.match(
        /^\*\*Disposition:\*\*\s*`?(supported|deferred|unsupported|release-blocking)`?/i,
      );
      if (dispMatch) {
        currentRow.disposition = dispMatch[1].toLowerCase().trim();
        continue;
      }

      // **Contract-recheck:** value
      const crMatch = fieldText.match(/^\*\*Contract-recheck:\*\*\s*(.+)/i);
      if (crMatch) {
        currentRow.contractRecheck = crMatch[1].trim();
        continue;
      }
    }
  }

  // Flush any remaining row
  flushRow(currentRow, rows);

  return rows;
}

/**
 * Flush an accumulated row into the rows array if it has enough fields.
 * @param {Partial<FCRow> | null} row
 * @param {FCRow[]} rows
 */
function flushRow(row, rows) {
  if (!row) return;
  // Don't flush rows that have no status or disposition — they're likely
  // section headers that got caught by sub-section detection.
  if (!row.status && !row.disposition) return;
  // Fill in defaults for optional fields
  rows.push({
    primitive: row.primitive || '<unknown>',
    hostAffordance: row.hostAffordance || '',
    uiStates: row.uiStates || '',
    accessibility: row.accessibility || '',
    evidence: row.evidence || '',
    status: row.status || '',
    disposition: row.disposition || '',
    contractRecheck: row.contractRecheck || '',
    lineNumber: row.lineNumber || 0,
  });
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

/**
 * Validate that a row has all required columns.
 * @param {FCRow} row
 * @returns {string[]} error messages
 */
function validateRequiredColumns(row) {
  const errors = [];
  const primitive = row.primitive || '<unknown>';

  for (const col of REQUIRED_FC_COLUMNS) {
    const value = row[col];
    if (typeof value !== 'string' || value.trim().length === 0) {
      errors.push(
        `Row "${primitive}" (line ~${row.lineNumber}) is missing required column "${col}".`,
      );
    }
  }

  return errors;
}

/**
 * Validate controlled vocabulary for status and disposition.
 * @param {FCRow} row
 * @returns {string[]} error messages
 */
function validateControlledVocabulary(row) {
  const errors = [];
  const primitive = row.primitive || '<unknown>';

  if (row.status && !VALID_STATUSES.has(row.status)) {
    errors.push(
      `Row "${primitive}" has unrecognised status "${row.status}". ` +
      `Valid statuses: ${[...VALID_STATUSES].join(', ')}.`,
    );
  }

  if (row.disposition && !VALID_DISPOSITIONS.has(row.disposition)) {
    errors.push(
      `Row "${primitive}" has unrecognised disposition "${row.disposition}". ` +
      `Valid dispositions: ${[...VALID_DISPOSITIONS].join(', ')}.`,
    );
  }

  return errors;
}

/**
 * Extract file paths from an evidence string.  Looks for:
 *   - `src/...` paths (with optional `.ts`, `.tsx`, `.js`, `.jsx` extensions)
 *   - Backtick-quoted file paths: `\`path/to/file.tsx\``
 *
 * @param {string} evidence
 * @returns {string[]} list of path-like substrings
 */
function extractEvidencePaths(evidence) {
  const paths = [];

  // Backtick-quoted paths: `src/tools/.../Foo.tsx`
  const backtickRe = /`([^`]+\.(?:ts|tsx|js|jsx|json|md))`/g;
  let match;
  while ((match = backtickRe.exec(evidence)) !== null) {
    paths.push(match[1]);
  }

  // Bare src/ paths with extensions
  const bareRe = /\b(src\/[^\s,;)]+\.(?:ts|tsx|js|jsx))\b/g;
  while ((match = bareRe.exec(evidence)) !== null) {
    const p = match[1].replace(/[;,)]+$/, '');
    if (!paths.includes(p)) paths.push(p);
  }

  return paths;
}

/**
 * Check that evidence file paths resolve to existing files.
 * @param {FCRow} row
 * @returns {{ errors: string[], warnings: string[], resolvedFiles: string[] }}
 */
function validateEvidencePaths(row) {
  const errors = [];
  const warnings = [];
  const resolvedFiles = [];
  const primitive = row.primitive || '<unknown>';

  const paths = extractEvidencePaths(row.evidence);

  if (paths.length === 0) {
    // No file paths found — not necessarily an error (evidence may be
    // descriptive or reference a directory / test runner pattern).
    // We'll flag it as a warning.
    warnings.push(
      `Row "${primitive}" has evidence but no parseable file paths found in: "${row.evidence.substring(0, 80)}..."`,
    );
    return { errors, warnings, resolvedFiles };
  }

  for (const rawPath of paths) {
    const absPath = resolve(repoRoot, rawPath);
    if (!existsSync(absPath)) {
      errors.push(
        `Row "${primitive}" evidence references "${rawPath}" which does not exist on disk.`,
      );
      continue;
    }

    try {
      const stat = statSync(absPath);
      if (!stat.isFile()) {
        warnings.push(
          `Row "${primitive}" evidence references "${rawPath}" which is not a regular file.`,
        );
        continue;
      }
    } catch {
      errors.push(
        `Row "${primitive}" evidence references "${rawPath}" which cannot be stat'd.`,
      );
      continue;
    }

    resolvedFiles.push(absPath);
  }

  return { errors, warnings, resolvedFiles };
}

/**
 * Parse the UI states string to check coverage.
 * Recognises patterns like:
 *   "empty: ■ Renders all reserved slots..."
 *   "- **Empty:** ■ Description"
 *   "□ States not tested..."
 *
 * @param {string} uiStates
 * @returns {{ covered: Set<string>, gaps: Set<string>, nas: Set<string> }}
 */
function parseStateCoverage(uiStates) {
  /** @type {Set<string>} */
  const covered = new Set();
  /** @type {Set<string>} */
  const gaps = new Set();
  /** @type {Set<string>} */
  const nas = new Set();

  if (!uiStates || uiStates.trim().length === 0) {
    // All states undocumented
    for (const s of UI_STATE_NAMES) {
      gaps.add(s);
    }
    return { covered, gaps, nas };
  }

  // Try to match patterns like:
  //   empty: ■ ...   or   **Empty:** ■ ...   or   - **Empty:** ■ ...
  for (const stateName of UI_STATE_NAMES) {
    // Build a regex that captures the state marker after the state name
    const re = new RegExp(
      `\\b${stateName}\\b[\\s:*\\-]*([■□—])`,
      'i',
    );
    const match = uiStates.match(re);
    if (match) {
      const symbol = match[1];
      if (symbol === '■') covered.add(stateName);
      else if (symbol === '□') gaps.add(stateName);
      else if (symbol === '—') nas.add(stateName);
    } else {
      // Also check for prose descriptions that imply coverage
      // e.g., "□ States not tested" means all states are gapped
      if (/□\s*States?\s*not\s*tested/i.test(uiStates)) {
        gaps.add(stateName);
      } else {
        // Undocumented
        gaps.add(stateName);
      }
    }
  }

  return { covered, gaps, nas };
}

/**
 * Validate state coverage for a row.
 * @param {FCRow} row
 * @returns {string[]} warnings
 */
function validateStateCoverage(row) {
  const warnings = [];
  const primitive = row.primitive || '<unknown>';
  const { covered, gaps, nas } = parseStateCoverage(row.uiStates);

  const undocumented = [];
  for (const stateName of UI_STATE_NAMES) {
    if (!covered.has(stateName) && !gaps.has(stateName) && !nas.has(stateName)) {
      undocumented.push(stateName);
    }
  }

  if (undocumented.length > 0) {
    warnings.push(
      `Row "${primitive}" has undocumented UI states: ${undocumented.join(', ')}. ` +
      `Document with ■ (satisfied), □ (gap), or — (not applicable).`,
    );
  }

  if (gaps.size > 0) {
    warnings.push(
      `Row "${primitive}" has documented state gaps: ${[...gaps].join(', ')}.`,
    );
  }

  return warnings;
}

// ---------------------------------------------------------------------------
// Deferred / unsupported row linkage validation
// ---------------------------------------------------------------------------

/**
 * Check that deferred or unsupported rows are properly linked.
 *
 * Per SD2, deferred/unsupported rows must have:
 *  - Evidence that includes an ABSENCE check, OR
 *  - Evidence that links to a blocker (BLOCKER: / DEFER: / CR:), OR
 *  - A contract-recheck reference that maps to a known deferred row
 *    in the supported/deferred matrix.
 *
 * @param {FCRow} row
 * @param {Set<string>} crDeferredRowIds  – row IDs from contract-recheck that have deferred/unsupported disposition
 * @returns {string[]} warnings or failures
 */
function validateDeferredLinkage(row, crDeferredRowIds) {
  const issues = [];
  const primitive = row.primitive || '<unknown>';
  const disposition = row.disposition;

  if (!isDeferred(row) && !isUnsupported(row)) return issues;

  // Check for ABSENCE evidence
  const hasAbsence = /ABSENCE:/i.test(row.evidence);

  // Check for blocker/deferral references
  const hasBlockerRef =
    /BLOCKER:/i.test(row.evidence) || /DEFER:/i.test(row.evidence);

  // Check for CR: references
  const hasCrRef = /CR:/i.test(row.evidence);

  // Check if the contract-recheck reference maps to deferred rows
  const crRefs = extractCrRefs(row.contractRecheck);
  const hasDeferredCrRef = crRefs.some((ref) => crDeferredRowIds.has(ref));

  if (!hasAbsence && !hasBlockerRef && !hasCrRef && !hasDeferredCrRef) {
    issues.push(
      `Row "${primitive}" is "${disposition}" but has no ABSENCE evidence, ` +
      `no BLOCKER/DEFER reference, and no contract-recheck link to a deferred row. ` +
      `Add absence-check evidence or an explicit blocker/deferral link.`,
    );
  }

  return issues;
}

/**
 * Extract CR: row IDs from a contract-recheck string.
 * Handles formats like:
 *   "CR:M2-013, CR:M1-002"
 *   "CR:M4-001, CR:M4-003, CR:M4-004, CR:M4-005"
 *   "CR:M12-011 (part of D-023)"
 *
 * @param {string} crString
 * @returns {string[]}
 */
function extractCrRefs(crString) {
  if (!crString) return [];
  const refs = [];
  const re = /CR:([A-Za-z]+\d+-\d+)/g;
  let match;
  while ((match = re.exec(crString)) !== null) {
    refs.push(match[1]);
  }
  return refs;
}

// ---------------------------------------------------------------------------
// Load contract-recheck deferred rows for cross-validation
// ---------------------------------------------------------------------------

/**
 * Load the contract-recheck matrix and extract the set of row IDs that
 * are classified as deferred or unsupported.
 *
 * @returns {Set<string>}
 */
function loadCrDeferredRowIds() {
  try {
    const { matrixRows } = loadContractMatrix();
    const deferredIds = new Set();
    for (const row of matrixRows) {
      if (isDeferred(row) || isUnsupported(row)) {
        if (row.rowId) deferredIds.add(row.rowId);
      }
    }
    return deferredIds;
  } catch {
    // If the contract-recheck matrix can't be loaded, return an empty set.
    // The gate will still validate other aspects.
    console.warn(`${LABEL} Could not load contract-recheck matrix for deferred cross-validation.`);
    return new Set();
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} Running in ${mode} mode…`);

// ---- Step 1: Parse the frontend closure matrix ----
/** @type {FCRow[]} */
let fcRows = [];

try {
  fcRows = parseFrontendClosureMatrix();
  console.log(
    `${LABEL} Parsed ${fcRows.length} primitive row(s) from frontend closure matrix.`,
  );
} catch (err) {
  console.error(`${LABEL} Failed to parse frontend closure matrix: ${err.message}`);
  process.exit(1);
}

if (fcRows.length === 0) {
  console.error(`${LABEL} No primitive rows found in the frontend closure matrix.`);
  process.exit(1);
}

// ---- Step 2: Load contract-recheck deferred row IDs ----
const crDeferredRowIds = loadCrDeferredRowIds();
console.log(
  `${LABEL} Loaded ${crDeferredRowIds.size} deferred/unsupported row ID(s) from contract-recheck matrix.`,
);

// ---- Accumulators ----
/** @type {string[]} */
const failures = [];
/** @type {string[]} */
const warnings = [];

// ---- Step 3: Validate every row ----
console.log(`${LABEL} Validating ${fcRows.length} row(s)…`);

const seenPrimitives = new Set();

for (const row of fcRows) {
  const primitive = row.primitive || '<unknown>';

  // Check for duplicate primitives
  if (seenPrimitives.has(primitive)) {
    warnings.push(`Duplicate primitive "${primitive}" (line ~${row.lineNumber}).`);
  }
  seenPrimitives.add(primitive);

  // ---- Required columns ----
  const columnErrors = validateRequiredColumns(row);
  for (const err of columnErrors) {
    failures.push(`[missing-column] ${err}`);
  }

  // ---- Controlled vocabulary ----
  const vocabErrors = validateControlledVocabulary(row);
  for (const err of vocabErrors) {
    failures.push(`[bad-vocabulary] ${err}`);
  }

  // Skip further checks for rows with structural failures
  if (columnErrors.length > 0 || vocabErrors.length > 0) {
    continue;
  }

  // ---- State coverage ----
  const stateWarnings = validateStateCoverage(row);
  for (const w of stateWarnings) {
    warnings.push(`[state-coverage] ${w}`);
  }

  // ---- Evidence paths ----
  const evidenceCheck = validateEvidencePaths(row);

  for (const err of evidenceCheck.errors) {
    // Missing evidence files for supported rows → failure
    // For deferred/unsupported rows → warning
    if (isSupported(row) && mode === 'release') {
      failures.push(`[missing-evidence] ${err}`);
    } else if (isSupported(row)) {
      failures.push(`[missing-evidence] ${err}`);
    } else {
      warnings.push(`[missing-evidence] ${err}`);
    }
  }

  for (const w of evidenceCheck.warnings) {
    warnings.push(`[evidence] ${w}`);
  }

  // ---- Deferred / unsupported linkage ----
  const linkageIssues = validateDeferredLinkage(row, crDeferredRowIds);
  for (const issue of linkageIssues) {
    if (isRelease) {
      failures.push(`[deferred-linkage] ${issue}`);
    } else {
      warnings.push(`[deferred-linkage] ${issue}`);
    }
  }

  // ---- Gap / blocked status reporting ----
  if (isGap(row) || isBlocked(row)) {
    warnings.push(
      `Row "${primitive}" has status "${row.status}" and disposition ` +
      `"${row.disposition}". Verify this classification is correct.`,
    );
  }

  // ---- Release-blocking rows ----
  if (isReleaseBlocking(row)) {
    const msg =
      `Row "${primitive}" is classified as "release-blocking". ` +
      `Resolve the blocker or reclassify before release.`;
    if (isRelease) {
      failures.push(`[release-blocking] ${msg}`);
    } else {
      warnings.push(`[release-blocking] ${msg}`);
    }
  }
}

// ---- Step 4: Summary statistics ----
const supportedRows = fcRows.filter((r) => isSupported(r));
const deferredRows = fcRows.filter((r) => isDeferred(r));
const unsupportedRows = fcRows.filter((r) => isUnsupported(r));
const releaseBlockingRows = fcRows.filter((r) => isReleaseBlocking(r));
const passRows = fcRows.filter((r) => isPass(r));
const gapRows = fcRows.filter((r) => isGap(r));
const blockedRows = fcRows.filter((r) => isBlocked(r));

console.log(`${LABEL} Summary:`);
console.log(`${LABEL}   Total rows:         ${fcRows.length}`);
console.log(`${LABEL}   Supported:          ${supportedRows.length}`);
console.log(`${LABEL}   Deferred:           ${deferredRows.length}`);
console.log(`${LABEL}   Unsupported:        ${unsupportedRows.length}`);
console.log(`${LABEL}   Release-blocking:   ${releaseBlockingRows.length}`);
console.log(`${LABEL}   Pass:               ${passRows.length}`);
console.log(`${LABEL}   Gap:                ${gapRows.length}`);
console.log(`${LABEL}   Blocked:            ${blockedRows.length}`);

// ---- Step 5: Report ----
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

// ---- Step 6: Exit decision ----
const hasFailures = failures.length > 0;

if (hasFailures) {
  console.error(
    `${LABEL} ${mode.toUpperCase()} FAILED with ${failures.length} failure(s) and ${warnings.length} warning(s).`,
  );
  process.exit(1);
}

console.log(
  `${LABEL} ${mode.toUpperCase()} PASSED. ` +
  `${fcRows.length} row(s) validated, ${warnings.length} warning(s).`,
);
process.exit(0);
