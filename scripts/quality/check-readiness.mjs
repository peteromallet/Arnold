#!/usr/bin/env node
/**
 * M5 Readiness Gate — Structured Readiness Row Validator
 *
 * Parses `docs/extensions/phase4-readiness.md` and validates every "cleared"
 * readiness row in the M5 section against the anchors (test and code) it
 * declares.  A row must have: ID, Category, Owner, Status, Test Anchor, Code
 * Anchor, Objective Pass Condition, and Notes.  For rows with status "cleared",
 * the test anchor must resolve to a real test block in the referenced file, and
 * the code anchor must resolve to a real export in the referenced file.
 *
 * Exit code:
 *   0 — all cleared rows have valid anchors and required fields
 *   1 — one or more cleared rows have missing/invalid anchors or fields
 *
 * Usage:
 *   node scripts/quality/check-readiness.mjs
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname, basename, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const READINESS_DOC_PATH = resolve(
  repoRoot,
  'docs/extensions/phase4-readiness.md',
);

const LABEL = '[readiness]';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const REQUIRED_COLUMNS = [
  'ID',
  'Category',
  'Owner',
  'Status',
  'Test Anchor',
  'Code Anchor',
  'Objective Pass Condition',
  'Notes',
];

// ---------------------------------------------------------------------------
// Markdown table parser for readiness rows
// ---------------------------------------------------------------------------

/**
 * @typedef {object} ReadinessRow
 * @property {string} id
 * @property {string} category
 * @property {string} owner
 * @property {string} status
 * @property {string} testAnchor
 * @property {string} codeAnchor
 * @property {string} passCondition
 * @property {string} notes
 */

/**
 * Parse a pipe-delimited markdown table row into a key-value map.
 * @param {string} headerLine - the header row (e.g. "| ID | Category | ... |")
 * @param {string} dataLine - the data row
 * @returns {Record<string, string> | null}
 */
function parseTableRow(headerLine, dataLine) {
  const headerCells = headerLine
    .split('|')
    .slice(1, -1)
    .map((c) => c.trim());

  const dataCells = dataLine
    .split('|')
    .slice(1, -1)
    .map((c) => c.trim());

  if (headerCells.length !== dataCells.length) return null;

  /** @type {Record<string, string>} */
  const row = {};
  for (let i = 0; i < headerCells.length; i++) {
    row[headerCells[i]] = dataCells[i];
  }
  return row;
}

/**
 * Parse readiness rows from the M5 section of the readiness doc.
 * Only rows that belong to the M5 readiness table (with header containing
 * "M5 Readiness Rows" or similar) are parsed.
 *
 * @returns {ReadinessRow[]}
 */
function parseReadinessRows() {
  if (!existsSync(READINESS_DOC_PATH)) {
    throw new Error(`Readiness doc not found: ${READINESS_DOC_PATH}`);
  }

  const content = readFileSync(READINESS_DOC_PATH, 'utf8');
  const lines = content.split('\n');

  /** @type {ReadinessRow[]} */
  const rows = [];

  let inM5Section = false;
  let inM5Table = false;
  let headerLine = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Detect M5 section heading
    if (line.startsWith('## M5:')) {
      inM5Section = true;
      inM5Table = false;
      headerLine = '';
      continue;
    }

    // Exit M5 section on next ## heading
    if (inM5Section && line.startsWith('## ') && !line.startsWith('## M5:') && !line.startsWith('###')) {
      inM5Section = false;
      inM5Table = false;
      continue;
    }

    if (!inM5Section) continue;

    // Detect the M5 readiness table subheading
    if (line.startsWith('### M5 Readiness Rows')) {
      inM5Table = true;
      // The next non-empty line starting with | should be the header
      continue;
    }

    if (!inM5Table) continue;

    // Skip blank lines
    if (line === '') continue;

    // If we hit a non-table line, stop table parsing
    if (!line.startsWith('|')) {
      inM5Table = false;
      continue;
    }

    // This is a table row
    if (!headerLine) {
      // Check if this looks like a header row (contains column names)
      if (line.includes('ID') && line.includes('Category') && line.includes('Status')) {
        headerLine = line;
      }
      // Otherwise it might be a separator row or data before header — skip
      continue;
    }

    // Skip separator rows
    if (/^\|[\s\-:|]+\|$/.test(line)) continue;

    // Parse the data row
    const parsed = parseTableRow(headerLine, line);
    if (!parsed) {
      console.warn(`${LABEL} Could not parse table row at line ${i + 1}: ${line}`);
      continue;
    }

    // Skip rows that are not M5 rows (e.g., example rows)
    const id = parsed['ID'] || '';
    if (!id.startsWith('M5-')) continue;

    const status = (parsed['Status'] || '').toLowerCase().trim();

    rows.push({
      id,
      category: parsed['Category'] || '',
      owner: parsed['Owner'] || '',
      status,
      testAnchor: parsed['Test Anchor'] || '',
      codeAnchor: parsed['Code Anchor'] || '',
      passCondition: parsed['Objective Pass Condition'] || '',
      notes: parsed['Notes'] || '',
    });
  }

  return rows;
}

// ---------------------------------------------------------------------------
// Anchor resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a "file:describe → it" test anchor to a real test in the codebase.
 *
 * Format: `path/file.test.ts:describe block name → it name`
 * The file path is relative to repo root.
 *
 * @param {string} anchor - the test anchor string
 * @returns {{ valid: boolean, reason?: string, file?: string, describeBlock?: string, itName?: string }}
 */
function resolveTestAnchor(anchor) {
  if (!anchor || anchor === '-') {
    return { valid: false, reason: 'Missing test anchor' };
  }
  if (anchor.startsWith('(doc-only')) {
    return { valid: false, reason: 'Doc-only rows must have executable test anchors or remain pending/blocked' };
  }

  // Parse: "file:describe block → it name"
  // Handle format like: "extensionLifecycle.test.ts:createExtensionDiagnosticsService → overwrites spoofed..."
  const fileMatch = anchor.match(/^([^:]+\.(?:test\.(?:ts|tsx|mjs)|spec\.(?:ts|tsx)))\s*:\s*(.+)/);
  if (!fileMatch) {
    // Try format: "ExtensionManager.test.tsx:ExtensionManager — direct entry read-only (T11) → does NOT show..."
    // The describe block may contain " — " instead of " → "
    const altMatch = anchor.match(/^([^:]+\.(?:test\.(?:ts|tsx|mjs)|spec\.(?:ts|tsx)))\s*:\s*(.+)/);
    if (!altMatch) {
      return { valid: false, reason: `Cannot parse test anchor format: "${anchor}"` };
    }
  }

  const filePath = fileMatch[1].trim();
  const rest = fileMatch[2].trim();

  // Split on " → " to get describe block and it name
  const arrowIdx = rest.lastIndexOf(' → ');
  let describeBlock, itName;
  if (arrowIdx >= 0) {
    describeBlock = rest.substring(0, arrowIdx).trim();
    itName = rest.substring(arrowIdx + 3).trim();
  } else {
    // Maybe just a describe block reference
    describeBlock = rest;
    itName = '';
  }

  const absPath = resolve(repoRoot, filePath);
  if (!existsSync(absPath)) {
    return { valid: false, reason: `Test file not found: ${filePath}`, file: filePath };
  }

  const content = readFileSync(absPath, 'utf8');

  // Look for the describe block
  if (describeBlock) {
    // The describe block may be nested like "ExtensionLifecycleHost — recovery-key registry (T2)"
    // Try to find it as a describe() call
    const describePatterns = [
      // Exact match: describe('ExtensionLifecycleHost — recovery-key registry (T2)',
      new RegExp(`describe\\s*\\(\\s*['"\`]${escapeRegex(describeBlock)}['"\`]`),
      // Match parts: if describe block contains " → ", try each part
    ];

    let describeFound = false;
    for (const pattern of describePatterns) {
      if (pattern.test(content)) {
        describeFound = true;
        break;
      }
    }

    if (!describeFound) {
      // Try splitting on " → " for nested describes
      const parts = describeBlock.split(' → ');
      let searchContent = content;
      let allFound = true;
      for (const part of parts) {
        const re = new RegExp(`describe\\s*\\(\\s*['"\`]${escapeRegex(part.trim())}['"\`]`);
        if (!re.test(searchContent)) {
          allFound = false;
          break;
        }
      }
      if (!allFound) {
        return {
          valid: false,
          reason: `Describe block "${describeBlock}" not found in ${filePath}`,
          file: filePath,
          describeBlock,
        };
      }
    }
  }

  // Look for the it block if specified (also accepts describe() blocks
  // since readiness rows may reference a describe block as the terminal anchor)
  if (itName) {
    const itPattern = new RegExp(`it\\s*\\(\\s*['"\`]${escapeRegex(itName)}['"\`]`);
    const testPattern = new RegExp(`test\\s*\\(\\s*['"\`]${escapeRegex(itName)}['"\`]`);
    const descPattern = new RegExp(`describe\\s*\\(\\s*['"\`]${escapeRegex(itName)}['"\`]`);
    if (!itPattern.test(content) && !testPattern.test(content) && !descPattern.test(content)) {
      return {
        valid: false,
        reason: `it()/test()/describe() block "${itName}" not found in ${filePath}`,
        file: filePath,
        itName,
      };
    }
  }

  return { valid: true, file: filePath, describeBlock, itName };
}

/**
 * Resolve a "file:symbol" code anchor to a real export in the codebase.
 *
 * Format: `path/file.ts:exportedSymbol`
 * The file path is relative to repo root.
 *
 * @param {string} anchor - the code anchor string
 * @returns {{ valid: boolean, reason?: string, file?: string, symbol?: string }}
 */
function resolveCodeAnchor(anchor) {
  if (!anchor || anchor === '-') {
    return { valid: false, reason: 'Missing code anchor' };
  }

  // Parse: "file:symbol"
  // Handle format like: "extensionLifecycle.ts:createExtensionDiagnosticsService"
  // Or: "docs/extensions/trust-and-security.md" (doc file, no symbol needed)
  const match = anchor.match(/^(.+?):(.+)$/);
  let filePath, symbol;

  if (match) {
    filePath = match[1].trim();
    symbol = match[2].trim();
  } else {
    // Maybe just a file path (for doc-only anchors)
    filePath = anchor.trim();
    symbol = '';
  }

  const absPath = resolve(repoRoot, filePath);
  if (!existsSync(absPath)) {
    return { valid: false, reason: `Source file not found: ${filePath}`, file: filePath };
  }

  // For .md files, just check existence — don't search for symbols
  if (filePath.endsWith('.md')) {
    return { valid: true, file: filePath, symbol: '' };
  }

  // For source files, search for the exported symbol
  if (symbol) {
    const content = readFileSync(absPath, 'utf8');

    // Look for the symbol as an export
    const exportPatterns = [
      // export function/const/class/interface/type/enum symbol
      new RegExp(`export\\s+(?:declare\\s+)?(?:async\\s+)?(?:const|function|class|interface|type|enum)\\s+${escapeRegex(symbol)}\\b`),
      // export { symbol } or export { symbol as ... }
      new RegExp(`export\\s*\\{[^}]*\\b${escapeRegex(symbol)}\\b[^}]*\\}`),
      // default export with the name
      new RegExp(`export\\s+default\\s+(?:function|class)?\\s*${escapeRegex(symbol)}\\b`),
    ];

    let found = false;
    for (const pattern of exportPatterns) {
      if (pattern.test(content)) {
        found = true;
        break;
      }
    }

    if (!found) {
      return {
        valid: false,
        reason: `Symbol "${symbol}" not found as an export in ${filePath}`,
        file: filePath,
        symbol,
      };
    }
  }

  return { valid: true, file: filePath, symbol };
}

/**
 * Escape special regex characters in a string.
 * @param {string} s
 * @returns {string}
 */
function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ---------------------------------------------------------------------------
// Row validation
// ---------------------------------------------------------------------------

/**
 * Validate a single readiness row.
 * @param {ReadinessRow} row
 * @returns {{ valid: boolean, errors: string[], warnings: string[] }}
 */
function validateRow(row) {
  const errors = [];
  const warnings = [];

  // Check required columns
  if (!row.id) errors.push(`Row missing ID`);
  if (!row.category) errors.push(`${row.id}: missing Category`);
  if (!row.owner) errors.push(`${row.id}: missing Owner`);
  if (!row.status) errors.push(`${row.id}: missing Status`);

  if (!row.testAnchor && row.status !== 'cleared') {
    // Pending/blocked rows may omit test anchor
  } else if (!row.testAnchor && row.status === 'cleared') {
    errors.push(`${row.id}: cleared row missing Test Anchor`);
  }

  if (!row.codeAnchor) {
    errors.push(`${row.id}: missing Code Anchor`);
  }

  if (!row.passCondition) errors.push(`${row.id}: missing Objective Pass Condition`);

  // Only validate anchors for cleared rows
  if (row.status === 'cleared') {
    // Validate test anchor
    const testResult = resolveTestAnchor(row.testAnchor);
    if (!testResult.valid) {
      errors.push(`${row.id}: Test anchor invalid — ${testResult.reason}`);
    }

    // Validate code anchor
    const codeResult = resolveCodeAnchor(row.codeAnchor);
    if (!codeResult.valid) {
      errors.push(`${row.id}: Code anchor invalid — ${codeResult.reason}`);
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} M5 Readiness Row Validator\n`);

let rows;
try {
  rows = parseReadinessRows();
} catch (err) {
  console.error(`${LABEL} Failed to parse readiness doc: ${err.message}`);
  process.exit(1);
}

if (rows.length === 0) {
  console.error(`${LABEL} No M5 readiness rows found in ${READINESS_DOC_PATH}`);
  process.exit(1);
}

console.log(`${LABEL} Found ${rows.length} M5 readiness rows.\n`);

/** @type {string[]} */
const failures = [];
let clearedCount = 0;
let clearedValidCount = 0;

for (const row of rows) {
  const prefix = `[${row.id}]`;

  if (row.status === 'cleared') {
    clearedCount++;
    const { valid, errors, warnings } = validateRow(row);

    if (valid) {
      clearedValidCount++;
      console.log(`${LABEL}   ✓ ${prefix} ${row.category} — ${row.owner}`);
    } else {
      console.error(`${LABEL}   ✗ ${prefix} FAILED:`);
      for (const err of errors) {
        console.error(`       ${err}`);
        failures.push(`${prefix} ${err}`);
      }
    }

    for (const warn of warnings) {
      console.warn(`       ⚠ ${warn}`);
    }
  } else if (row.status === 'pending' || row.status === 'blocked') {
    console.log(`${LABEL}   - ${prefix} ${row.category} (${row.status})`);
  } else {
    console.warn(`${LABEL}   ? ${prefix} unknown status: "${row.status}"`);
  }
}

// ---- Summary ----
console.log(`\n${LABEL} === Summary ===`);
console.log(`${LABEL} Total M5 rows: ${rows.length}`);
console.log(`${LABEL} Cleared rows: ${clearedCount}`);
console.log(`${LABEL} Cleared rows with valid anchors: ${clearedValidCount}`);
console.log(`${LABEL} Failures: ${failures.length}`);

if (failures.length > 0) {
  console.error(`\n${LABEL} FAILED: ${failures.length} anchor validation failure(s).`);
  process.exitCode = 1;
} else {
  console.log(`\n${LABEL} PASSED: All cleared rows have valid anchors.`);
}
