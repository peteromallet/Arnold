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
 *   node scripts/quality/check-readiness.mjs --strict
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
// CLI flags
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const strictMode = args.includes('--strict');

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
// Evidence validation (strict mode)
// ---------------------------------------------------------------------------

/**
 * Extract the test file paths that are arguments to `vitest run` inside the
 * `test:readiness` npm script. Flags such as `--config` and their values are
 * skipped.
 *
 * @param {string} script
 * @returns {string[]}
 */
function extractTestReadinessFiles(script) {
  if (!script) return [];

  const tokens = script.split(/\s+/);
  const files = [];
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (token === '--config') {
      i++; // skip the config path
      continue;
    }
    if (token.startsWith('--')) continue;
    if (/\.(?:test|spec)\.(?:ts|tsx|mjs)$/.test(token)) {
      files.push(token);
    }
  }
  return files;
}

/**
 * Validate that a cleared row has runnable evidence.
 *
 * - Doc-only or missing anchors are rejected.
 * - Playwright/spec files under `tests/e2e/` require a `(slow gate)` note and
 *   a `Command: npx playwright test ...` line.
 * - All other cleared rows require the referenced test file to be listed as
 *   a vitest argument in `npm run test:readiness`.
 *
 * @param {ReadinessRow} row
 * @param {string[]} testReadinessFiles
 * @returns {{ valid: boolean, reason?: string }}
 */
function validateEvidence(row, testReadinessFiles) {
  const anchor = (row.testAnchor || '').trim();

  if (!anchor) {
    return { valid: false, reason: 'cleared row missing Test Anchor' };
  }
  if (anchor.startsWith('(doc-only')) {
    return { valid: false, reason: 'cleared row has doc-only Test Anchor; doc-only rows must remain pending/blocked or gain an executable anchor' };
  }

  // Extract file path from anchor (everything before the first ':' or the whole anchor if no ':')
  const colonIdx = anchor.indexOf(':');
  const filePath = colonIdx >= 0 ? anchor.substring(0, colonIdx).trim() : anchor;

  if (!filePath) {
    return { valid: false, reason: 'Test Anchor does not reference a file' };
  }

  // Playwright / e2e spec files are classified as slow gates.
  if (filePath.startsWith('tests/e2e/')) {
    const notes = (row.notes || '').trim();
    if (!notes.startsWith('(slow gate)')) {
      return { valid: false, reason: `e2e Test Anchor ${filePath} must be classified with a Notes column starting with "(slow gate)"` };
    }
    if (!/Command:\s*npx playwright test/.test(notes)) {
      return { valid: false, reason: `e2e Test Anchor ${filePath} Notes must contain a "Command: npx playwright test ..." line` };
    }
    return { valid: true };
  }

  // Non-e2e cleared rows must be wired into the fast `test:readiness` command.
  if (!testReadinessFiles.includes(filePath)) {
    return { valid: false, reason: `Test Anchor ${filePath} is not included in the "test:readiness" script; add it to the vitest arguments so the release gate exercises it` };
  }

  return { valid: true };
}

// ---------------------------------------------------------------------------
// Row validation
// ---------------------------------------------------------------------------

/**
 * Validate a single readiness row.
 * @param {ReadinessRow} row
 * @param {boolean} strictMode
 * @param {string[]} testReadinessFiles
 * @returns {{ valid: boolean, errors: string[], warnings: string[] }}
 */
function validateRow(row, strictMode, testReadinessFiles) {
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
    // Strict mode: doc-only or missing anchors are not acceptable for cleared rows.
    if (strictMode) {
      const anchor = (row.testAnchor || '').trim();
      if (!anchor) {
        errors.push(`${row.id}: cleared row missing Test Anchor (strict mode)`);
      } else if (anchor.startsWith('(doc-only')) {
        errors.push(`${row.id}: cleared row has doc-only Test Anchor; doc-only rows must remain pending/blocked or gain an executable anchor (strict mode)`);
      }
    }

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

    // Strict mode: cleared rows must have runnable evidence.
    if (strictMode && testResult.valid) {
      const evidenceResult = validateEvidence(row, testReadinessFiles);
      if (!evidenceResult.valid) {
        errors.push(`${row.id}: Evidence validation failed — ${evidenceResult.reason}`);
      }
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log(`${LABEL} M5 Readiness Row Validator${strictMode ? ' (strict mode)' : ''}\n`);

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

// Load the test:readiness script so strict mode can enforce that every cleared
// unit-test row is wired into the fast release gate.
let testReadinessFiles = [];
try {
  const packageJsonPath = resolve(repoRoot, 'package.json');
  const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf8'));
  testReadinessFiles = extractTestReadinessFiles(packageJson.scripts?.['test:readiness']);
} catch (err) {
  console.warn(`${LABEL} Could not read test:readiness script: ${err.message}`);
}

console.log(`${LABEL} Found ${rows.length} M5 readiness rows.`);
if (strictMode) {
  console.log(`${LABEL} test:readiness vitest arguments: ${testReadinessFiles.length > 0 ? testReadinessFiles.join(', ') : '(none found)'}\n`);
} else {
  console.log(`${LABEL} Running in backwards-compatible anchor-only mode. Pass --strict to enforce evidence wiring.\n`);
}

/** @type {string[]} */
const failures = [];
let clearedCount = 0;
let clearedValidCount = 0;

for (const row of rows) {
  const prefix = `[${row.id}]`;

  if (row.status === 'cleared') {
    clearedCount++;
    const { valid, errors, warnings } = validateRow(row, strictMode, testReadinessFiles);

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
console.log(`${LABEL} Cleared rows with valid anchors${strictMode ? ' and evidence' : ''}: ${clearedValidCount}`);
console.log(`${LABEL} Failures: ${failures.length}`);

if (failures.length > 0) {
  console.error(`\n${LABEL} FAILED: ${failures.length} validation failure(s).`);
  process.exitCode = 1;
} else {
  const passMessage = strictMode
    ? 'PASSED: All cleared rows have valid anchors and runnable evidence.'
    : 'PASSED: All cleared rows have valid anchors.';
  console.log(`\n${LABEL} ${passMessage}`);
}
