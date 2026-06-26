#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const repoRoot = process.cwd();
const maturityPath = path.join(repoRoot, 'config/extensions/family-maturity.json');
const docs = [
  path.join(repoRoot, 'docs/extensions/phase4-readiness.md'),
  path.join(repoRoot, 'docs/extensions/foundation-closure-assessment.md'),
];

const isRelease = process.argv.includes('--release');
const isWrite = process.argv.includes('--write');
const isAudit = process.argv.includes('--audit') || (!isRelease && !isWrite);

function fail(message) {
  console.error(`[docs-maturity-sync] ${message}`);
  process.exit(1);
}

function warn(message) {
  console.warn(`[docs-maturity-sync] ${message}`);
}

if (!fs.existsSync(maturityPath)) {
  fail(`Missing maturity registry: ${maturityPath}`);
}

const maturity = JSON.parse(fs.readFileSync(maturityPath, 'utf8'));
if (!Array.isArray(maturity)) {
  fail('Maturity registry must be an array.');
}

function buildTable() {
  const header = [
    '| Family | Declaration | Execution | Trusted | Bridged | Host Adapter | Notes |',
    '|---|---|---|---|---|---|---|',
  ];
  const rows = maturity.map((family) => {
    const bridged = family.legacyCompatibility?.bridged ? 'Yes' : 'No';
    const trusted = family.requiresTrustedCode ? 'Yes' : 'No';
    const adapter = family.hostAdapter ? `\`${path.basename(family.hostAdapter)}\`` : '—';
    const notes = family.hostIntegrationNotes ? family.hostIntegrationNotes.replace(/\|/g, '\\|').replace(/\n/g, ' ') : '';
    return `| ${family.label ?? family.kind} | ${family.declarationMaturity} | ${family.executionMaturity} | ${trusted} | ${bridged} | ${adapter} | ${notes} |`;
  });
  return [...header, ...rows, ''].join('\n');
}

const generatedTable = buildTable();
const startMarker = '<!-- family-maturity-table-start -->';
const endMarker = '<!-- family-maturity-table-end -->';

let allOk = true;

for (const docPath of docs) {
  if (!fs.existsSync(docPath)) {
    const msg = `Missing doc: ${docPath}`;
    if (isRelease) fail(msg);
    warn(msg);
    allOk = false;
    continue;
  }

  const content = fs.readFileSync(docPath, 'utf8');
  const startIdx = content.indexOf(startMarker);
  const endIdx = content.indexOf(endMarker);

  if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
    const msg = `Missing or malformed family maturity markers in ${path.relative(repoRoot, docPath)}.`;
    if (isWrite) {
      // Append markers and table at end of file
      const separator = content.endsWith('\n\n') ? '' : content.endsWith('\n') ? '\n' : '\n\n';
      const appendix = `${separator}## Family Maturity Snapshot\n\n${startMarker}\n${generatedTable}${endMarker}\n`;
      fs.writeFileSync(docPath, content + appendix, 'utf8');
      console.log(`[docs-maturity-sync] Appended maturity table to ${path.relative(repoRoot, docPath)}.`);
      continue;
    }
    if (isRelease) fail(msg);
    warn(msg);
    allOk = false;
    continue;
  }

  const before = content.slice(0, startIdx + startMarker.length);
  const after = content.slice(endIdx);
  const existingBlock = content.slice(startIdx + startMarker.length, endIdx).trim();
  const expectedBlock = generatedTable.trim();

  if (existingBlock !== expectedBlock) {
    if (isWrite) {
      const newContent = `${before}\n${generatedTable}${after}`;
      fs.writeFileSync(docPath, newContent, 'utf8');
      console.log(`[docs-maturity-sync] Updated maturity table in ${path.relative(repoRoot, docPath)}.`);
      continue;
    }
    const msg = `Stale maturity table in ${path.relative(repoRoot, docPath)}.`;
    if (isRelease) fail(msg);
    warn(msg);
    allOk = false;
    continue;
  }

  console.log(`[docs-maturity-sync] ${path.relative(repoRoot, docPath)} is up to date.`);
}

if (isWrite) {
  console.log('[docs-maturity-sync] Write pass complete.');
  process.exit(0);
}

if (!allOk) {
  if (isRelease) {
    fail('One or more docs maturity tables are stale or missing.');
  }
  warn('Audit completed with warnings; run with --write to regenerate tables.');
  process.exit(0);
}

console.log('[docs-maturity-sync] All docs maturity tables are in sync.');
