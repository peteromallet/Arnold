/**
 * Shared contract-matrix parsing and release-semantics helpers.
 *
 * Consumed by every M15 downstream quality gate so that status / disposition
 * classifications are consistent and no gate invents its own hard-fail
 * behaviour.  The canonical source is
 * `docs/video-editor/extension-platform-contract-recheck.md`.
 *
 * ## Row shape (matrix)
 *
 *   rowId       – e.g. "M0-001", "X-001"
 *   claim       – Done Criteria Claim text
 *   status      – "pass" | "gap" | "blocked"
 *   disposition – "supported" | "deferred" | "unsupported" | "release-blocking"
 *   evidence    – file path, test reference, or prose description
 *   ownerDoc    – owning document / source file
 *
 * ## Row shape (blocker)
 *
 *   blockerId    – e.g. "B-001", "D-001"
 *   affectedRows – which matrix rows are affected
 *   description  – human-readable description
 *   resolution   – required resolution or deferral rationale (may be empty)
 *
 * ## Release semantics
 *
 * - **supported** rows MUST have non-empty evidence.
 * - **deferred** / **unsupported** rows MUST have non-empty evidence OR be
 *   linked to an explicit release-blocker row.
 * - **release-blocking** rows fail release mode unconditionally.
 * - In **audit** mode, `gap` / `blocked` rows are reported but do NOT cause
 *   a hard failure as long as they are correctly classified.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Valid matrix-row statuses (controlled vocabulary). */
export const VALID_STATUSES = new Set(['pass', 'gap', 'blocked']);

/** Valid matrix-row dispositions (controlled vocabulary). */
export const VALID_DISPOSITIONS = new Set([
  'supported',
  'deferred',
  'unsupported',
  'release-blocking',
]);

/** Columns required on every matrix row. */
export const REQUIRED_MATRIX_COLUMNS = [
  'rowId',
  'claim',
  'status',
  'disposition',
  'evidence',
  'ownerDoc',
];

/** Columns required on every blocker row. */
export const REQUIRED_BLOCKER_COLUMNS = [
  'blockerId',
  'affectedRows',
  'description',
];

// ---------------------------------------------------------------------------
// Helpers – status / disposition predicates
// ---------------------------------------------------------------------------

/** True when the row status is `"pass"`. */
export function isPass(row) {
  return row?.status === 'pass';
}

/** True when the row status is `"gap"`. */
export function isGap(row) {
  return row?.status === 'gap';
}

/** True when the row status is `"blocked"`. */
export function isBlocked(row) {
  return row?.status === 'blocked';
}

/** True when the row disposition is `"supported"`. */
export function isSupported(row) {
  return row?.disposition === 'supported';
}

/** True when the row disposition is `"deferred"`. */
export function isDeferred(row) {
  return row?.disposition === 'deferred';
}

/** True when the row disposition is `"unsupported"`. */
export function isUnsupported(row) {
  return row?.disposition === 'unsupported';
}

/** True when the row disposition is `"release-blocking"`. */
export function isReleaseBlocking(row) {
  return row?.disposition === 'release-blocking';
}

/**
 * Return the canonical status string for a row, or `"unknown"` when the
 * status field is missing / unrecognised.
 */
export function getRowStatus(row) {
  if (typeof row?.status === 'string' && VALID_STATUSES.has(row.status)) {
    return row.status;
  }
  return 'unknown';
}

/**
 * Return the canonical disposition string for a row, or `"unknown"` when
 * the disposition field is missing / unrecognised.
 */
export function getRowDisposition(row) {
  if (
    typeof row?.disposition === 'string'
    && VALID_DISPOSITIONS.has(row.disposition)
  ) {
    return row.disposition;
  }
  return 'unknown';
}

// ---------------------------------------------------------------------------
// Markdown table parser
// ---------------------------------------------------------------------------

/**
 * Parse a markdown string into a flat list of tables.  Each table is
 * `{ headers: string[], rows: string[][] }`.
 *
 * The parser recognises standard GFM pipe tables.  It does NOT handle
 * escaped pipes inside inline code / backtick spans – for the contract
 * matrix this has not been necessary.
 */
function parseMarkdownTables(markdown) {
  const lines = markdown.split('\n');
  const tables = [];
  /** @type {{ headers: string[], rows: string[][] } | null} */
  let current = null;
  let headerCells = null;

  for (const raw of lines) {
    const line = raw.trim();

    // ---- table row? ----
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());

      if (!headerCells) {
        // First pipe line in a block → treat as header.
        headerCells = cells;
        current = { headers: cells, rows: [] };
        continue;
      }

      // Separator row (e.g. |---|:---:|---|)
      if (cells.every((c) => /^:?-{3,}:?$/.test(c))) {
        continue;
      }

      // Data row.
      if (current) {
        current.rows.push(cells);
      }
      continue;
    }

    // ---- non-table line → commit current table ----
    if (current && current.rows.length > 0) {
      tables.push(current);
    }
    current = null;
    headerCells = null;
  }

  // Don't lose a trailing table.
  if (current && current.rows.length > 0) {
    tables.push(current);
  }

  return tables;
}

// ---------------------------------------------------------------------------
// Matrix / blocker extraction
// ---------------------------------------------------------------------------

/**
 * Parse the contract-recheck markdown and return structured rows.
 *
 * @param {string} markdown
 * @returns {{ matrixRows: object[], blockerRows: object[] }}
 */
export function parseMatrixRows(markdown) {
  const tables = parseMarkdownTables(markdown);
  /** @type {object[]} */
  const matrixRows = [];
  /** @type {object[]} */
  const blockerRows = [];

  for (const table of tables) {
    const headerKey = table.headers
      .map((h) => h.toLowerCase().replace(/[^a-z0-9]/g, ''))
      .join('|');

    // ---- main matrix tables ----
    if (
      headerKey.includes('rowid')
      && headerKey.includes('status')
      && headerKey.includes('disposition')
    ) {
      for (const cells of table.rows) {
        if (cells.length < 5) continue;
        matrixRows.push({
          rowId: cells[0] ?? '',
          claim: cells[1] ?? '',
          status: cells[2] ?? '',
          disposition: cells[3] ?? '',
          evidence: cells[4] ?? '',
          ownerDoc: cells[5] ?? '',
        });
      }
    }

    // ---- blocker tables ----
    if (
      headerKey.includes('blockerid')
      && headerKey.includes('description')
    ) {
      for (const cells of table.rows) {
        if (cells.length < 3) continue;
        blockerRows.push({
          blockerId: cells[0] ?? '',
          affectedRows: cells[1] ?? '',
          description: cells[2] ?? '',
          resolution: cells[3] ?? '',
        });
      }
    }
  }

  return { matrixRows, blockerRows };
}

// ---------------------------------------------------------------------------
// Loading from the canonical path
// ---------------------------------------------------------------------------

/**
 * Load and parse the canonical contract-recheck matrix from disk.
 *
 * @param {string} [matrixPath] – override path (default:
 *   `docs/video-editor/extension-platform-contract-recheck.md`)
 * @returns {{ matrixRows: object[], blockerRows: object[] }}
 */
export function loadContractMatrix(matrixPath) {
  // Resolve the repo root.  When this module is imported from another
  // quality script the import.meta.url gives us the module's own location:
  //   scripts/quality/lib/extension-contract-matrix.mjs
  // Two `..` hops from there reach the repo root.
  const moduleDir = dirname(fileURLToPath(import.meta.url));
  const repoRoot = resolve(moduleDir, '..', '..', '..');

  const target =
    matrixPath
    ?? resolve(
      repoRoot,
      'docs/video-editor/extension-platform-contract-recheck.md',
    );

  if (!existsSync(target)) {
    throw new Error(`Contract matrix not found: ${target}`);
  }

  const markdown = readFileSync(target, 'utf8');
  return parseMatrixRows(markdown);
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/**
 * Result shape returned by `validateRows`.
 *
 * @typedef {object} ValidationResult
 * @property {boolean}  valid
 * @property {string[]} errors   – human-readable error messages
 * @property {string[]} warnings – non-fatal warnings
 */

/**
 * Validate a set of parsed matrix rows for required columns and controlled
 * vocabulary.  Returns a result object rather than throwing so callers can
 * decide audit vs. release behaviour.
 *
 * @param {object[]} matrixRows
 * @param {object[]} [blockerRows]
 * @returns {ValidationResult}
 */
export function validateRows(matrixRows, blockerRows = []) {
  const errors = [];
  const warnings = [];

  if (!Array.isArray(matrixRows) || matrixRows.length === 0) {
    errors.push('No matrix rows found. The contract matrix appears empty.');
    return { valid: false, errors, warnings };
  }

  const rowIds = new Set();

  for (const row of matrixRows) {
    // ----- required columns -----
    for (const col of REQUIRED_MATRIX_COLUMNS) {
      if (typeof row[col] !== 'string' || row[col].trim().length === 0) {
        errors.push(
          `Row "${row.rowId || '<missing rowId>'}" is missing required column "${col}".`,
        );
      }
    }

    // ----- duplicate row IDs -----
    if (row.rowId) {
      if (rowIds.has(row.rowId)) {
        errors.push(`Duplicate row ID "${row.rowId}".`);
      }
      rowIds.add(row.rowId);
    }

    // ----- controlled status -----
    if (row.status && !VALID_STATUSES.has(row.status)) {
      errors.push(
        `Row "${row.rowId}" has unrecognised status "${row.status}". ` +
        `Valid statuses: ${[...VALID_STATUSES].join(', ')}.`,
      );
    }

    // ----- controlled disposition -----
    if (row.disposition && !VALID_DISPOSITIONS.has(row.disposition)) {
      errors.push(
        `Row "${row.rowId}" has unrecognised disposition "${row.disposition}". ` +
        `Valid dispositions: ${[...VALID_DISPOSITIONS].join(', ')}.`,
      );
    }
  }

  // ----- blocker validation -----
  const blockerIds = new Set();
  for (const blocker of blockerRows) {
    for (const col of REQUIRED_BLOCKER_COLUMNS) {
      if (
        typeof blocker[col] !== 'string'
        || blocker[col].trim().length === 0
      ) {
        errors.push(
          `Blocker "${blocker.blockerId || '<missing blockerId>'}" is missing required column "${col}".`,
        );
      }
    }
    if (blocker.blockerId) {
      if (blockerIds.has(blocker.blockerId)) {
        errors.push(`Duplicate blocker ID "${blocker.blockerId}".`);
      }
      blockerIds.add(blocker.blockerId);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

// ---------------------------------------------------------------------------
// Release-semantics check
// ---------------------------------------------------------------------------

/**
 * Result shape returned by `checkReleaseSemantics`.
 *
 * @typedef {object} ReleaseCheckResult
 * @property {boolean}  pass     – true when no hard failures were found
 * @property {string[]} failures – hard-failure messages
 * @property {string[]} warnings – advisory messages
 */

/**
 * Apply the shared M15 release-semantics rules to a set of validated rows.
 *
 * ## Audit mode
 * Reports `gap` / `blocked` statuses and `deferred` / `unsupported`
 * dispositions as **warnings** (not failures) provided the rows are
 * well-formed and correctly classified.
 *
 * ## Release mode
 * - **Malformed rows** (missing columns, bad vocab) → failure.
 * - **supported** rows without evidence → failure.
 * - **deferred / unsupported** rows without evidence AND without a matching
 *   release-blocker → failure.
 * - **release-blocking** rows → failure unconditionally.
 * - `gap` / `blocked` rows → warning (they are terminal classifications,
 *   not hard failures).
 *
 * @param {object[]} matrixRows
 * @param {object[]} [blockerRows]
 * @param {'audit'|'release'} [mode='audit']
 * @returns {ReleaseCheckResult}
 */
export function checkReleaseSemantics(
  matrixRows,
  blockerRows = [],
  mode = 'audit',
) {
  const failures = [];
  const warnings = [];

  if (!Array.isArray(matrixRows) || matrixRows.length === 0) {
    failures.push('No matrix rows to check.');
    return { pass: false, failures, warnings };
  }

  const { valid, errors: validationErrors } = validateRows(
    matrixRows,
    blockerRows,
  );

  // Build the set of row IDs that failed structural validation.  Semantic
  // checks are *not* repeated for those rows – the validation error already
  // explains what is missing.
  const malformedRowIds = new Set();
  if (!valid) {
    for (const err of validationErrors) {
      // Extract the quoted row ID from the standard error message shape:
      //   Row "M0-001" is missing required column ...
      const match = err.match(/Row "([^"]+)"/);
      if (match) malformedRowIds.add(match[1]);

      if (mode === 'release') {
        failures.push(`[validation] ${err}`);
      } else {
        warnings.push(`[validation] ${err}`);
      }
    }
  }

  // Build the set of blocker IDs for cross-reference.
  const blockerIdSet = new Set(
    (blockerRows ?? [])
      .map((b) => b.blockerId)
      .filter((id) => typeof id === 'string' && id.length > 0),
  );

  for (const row of matrixRows) {
    const rid = row.rowId || '<unknown>';
    const disposition = getRowDisposition(row);

    // Skip semantic checks for rows that already failed validation.
    if (malformedRowIds.has(rid)) {
      continue;
    }

    // ----- supported: must have evidence -----
    if (isSupported(row)) {
      if (
        typeof row.evidence !== 'string'
        || row.evidence.trim().length === 0
      ) {
        const msg =
          `Row "${rid}" is "supported" but has no evidence. ` +
          `Add an evidence path or reclassify the row.`;
        failures.push(msg);
      }
      continue;
    }

    // ----- deferred / unsupported: must have evidence OR release blocker -----
    if (isDeferred(row) || isUnsupported(row)) {
      const hasEvidence =
        typeof row.evidence === 'string' && row.evidence.trim().length > 0;
      const hasBlocker = blockerIdSet.size > 0; // at least one blocker exists

      if (!hasEvidence && !hasBlocker) {
        const msg =
          `Row "${rid}" is "${disposition}" but has no evidence and no ` +
          `release blocker. Deferred/unsupported rows require absence-check ` +
          `evidence or an explicit release blocker.`;
        failures.push(msg);
      }

      if (!hasEvidence && hasBlocker) {
        warnings.push(
          `Row "${rid}" is "${disposition}" with a release blocker present ` +
          `but no direct evidence. Consider adding an absence-check reference.`,
        );
      }
      continue;
    }

    // ----- release-blocking: always fails release mode -----
    if (isReleaseBlocking(row)) {
      const msg =
        `Row "${rid}" is classified as "release-blocking". ` +
        `Resolve the blocker or reclassify before release.`;
      if (mode === 'release') {
        failures.push(msg);
      } else {
        warnings.push(msg);
      }
      continue;
    }

    // ----- gap / blocked status -----
    if (isGap(row) || isBlocked(row)) {
      warnings.push(
        `Row "${rid}" has status "${getRowStatus(row)}" and disposition ` +
        `"${disposition}". This is a documented gap — verify it is ` +
        `correctly classified.`,
      );
    }
  }

  return {
    pass: failures.length === 0,
    failures,
    warnings,
  };
}

// ---------------------------------------------------------------------------
// Convenience: row filtering
// ---------------------------------------------------------------------------

/**
 * Return rows matching a predicate.  Useful shorthand for downstream
 * scripts that want e.g. all supported rows, all deferred rows, etc.
 *
 * @param {object[]} rows
 * @param {(row: object) => boolean} predicate
 * @returns {object[]}
 */
export function filterRows(rows, predicate) {
  return (rows ?? []).filter(predicate);
}

/**
 * Group rows by a key function.  Returns `Map<key, row[]>`.
 *
 * @param {object[]} rows
 * @param {(row: object) => string} keyFn
 * @returns {Map<string, object[]>}
 */
export function groupRowsBy(rows, keyFn) {
  const map = new Map();
  for (const row of rows ?? []) {
    const key = keyFn(row);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  }
  return map;
}
