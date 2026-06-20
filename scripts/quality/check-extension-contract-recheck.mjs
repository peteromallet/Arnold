#!/usr/bin/env node
/**
 * M15 Contract-Recheck Gate
 *
 * Loads the canonical extension-platform contract-recheck matrix and applies
 * the shared release-semantics rules from the `extension-contract-matrix`
 * helper module.  Supports two modes:
 *
 *   --audit    (default)  Report gaps, blocked statuses, and non-supported
 *                         dispositions as warnings.  Only exit non-zero when
 *                         rows are malformed (i.e. the matrix itself is not
 *                         well-formed).  This is the mode wired into the
 *                         normal `quality:check` path.
 *
 *   --release            Apply strict release rules: missing evidence,
 *                         release-blocking rows, and malformed rows all cause
 *                         a hard failure.  Run this before cutting a release.
 *
 * Failures are visible in command output so the risk surface is transparent.
 */

import {
  loadContractMatrix,
  validateRows,
  checkReleaseSemantics,
} from './lib/extension-contract-matrix.mjs';

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

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const label = '[contract-recheck]';

console.log(`${label} Running in ${mode} mode…`);

let matrixRows = [];
let blockerRows = [];

try {
  const matrix = loadContractMatrix();
  matrixRows = matrix.matrixRows;
  blockerRows = matrix.blockerRows;
} catch (err) {
  console.error(`${label} Failed to load contract matrix: ${err.message}`);
  process.exit(1);
}

console.log(
  `${label} Loaded ${matrixRows.length} matrix row(s) and ${blockerRows.length} blocker row(s).`,
);

// ---- Always run structural validation first ----
const validation = validateRows(matrixRows, blockerRows);

if (!validation.valid) {
  console.error(`${label} Structural validation FAILED:`);
  for (const err of validation.errors) {
    console.error(`${label}   - ${err}`);
  }
  for (const warn of validation.warnings) {
    console.warn(`${label}   [warn] ${warn}`);
  }
  // Malformed rows are always a hard failure regardless of mode.
  console.error(
    `${label} The contract-recheck matrix is not well-formed. ` +
      `Fix the structural issues above before this gate can pass.`,
  );
  process.exit(1);
}

console.log(`${label} Structural validation passed.`);

// ---- Release-semantics check ----
const releaseCheck = checkReleaseSemantics(matrixRows, blockerRows, mode);

// Report failures
for (const failure of releaseCheck.failures) {
  console.error(`${label} FAIL: ${failure}`);
}

// Report warnings
for (const warning of releaseCheck.warnings) {
  console.warn(`${label} WARN: ${warning}`);
}

// ---- Row-level summary ----
const gapRows = matrixRows.filter((r) => r.status === 'gap');
const blockedRows = matrixRows.filter((r) => r.status === 'blocked');
const deferredRows = matrixRows.filter((r) => r.disposition === 'deferred');
const unsupportedRows = matrixRows.filter((r) => r.disposition === 'unsupported');
const releaseBlockingRows = matrixRows.filter(
  (r) => r.disposition === 'release-blocking',
);

if (gapRows.length > 0) {
  console.warn(
    `${label} ${gapRows.length} row(s) with "gap" status: ` +
      gapRows.map((r) => `${r.rowId}(${r.disposition})`).join(', '),
  );
}

if (blockedRows.length > 0) {
  console.warn(
    `${label} ${blockedRows.length} row(s) with "blocked" status: ` +
      blockedRows.map((r) => `${r.rowId}(${r.disposition})`).join(', '),
  );
}

if (deferredRows.length > 0) {
  console.warn(
    `${label} ${deferredRows.length} row(s) with "deferred" disposition: ` +
      deferredRows.map((r) => `${r.rowId}(${r.status})`).join(', '),
  );
}

if (unsupportedRows.length > 0) {
  console.warn(
    `${label} ${unsupportedRows.length} row(s) with "unsupported" disposition: ` +
      unsupportedRows.map((r) => `${r.rowId}(${r.status})`).join(', '),
  );
}

if (releaseBlockingRows.length > 0) {
  console.warn(
    `${label} ${releaseBlockingRows.length} row(s) with "release-blocking" disposition: ` +
      releaseBlockingRows.map((r) => `${r.rowId}(${r.status})`).join(', '),
  );
}

// ---- Exit decision ----
if (!releaseCheck.pass) {
  const failureText =
    releaseCheck.failures.length === 1 ? 'failure' : 'failures';
  console.error(
    `${label} ${mode.toUpperCase()} FAILED with ` +
      `${releaseCheck.failures.length} ${failureText}.`,
  );
  process.exit(1);
}

console.log(
  `${label} ${mode.toUpperCase()} PASSED. ` +
    `${matrixRows.length} row(s) reviewed, ${releaseCheck.warnings.length} warning(s).`,
);
process.exit(0);
