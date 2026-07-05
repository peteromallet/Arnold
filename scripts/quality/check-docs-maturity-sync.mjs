#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const args = process.argv.slice(2);
const argSet = new Set(args);
const isRelease = argSet.has('--release');
const isWrite = argSet.has('--write');

function readOption(name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`));
  if (inline) {
    return inline.slice(name.length + 1);
  }

  const index = args.indexOf(name);
  if (index !== -1 && index + 1 < args.length) {
    return args[index + 1];
  }

  return null;
}

const repoRoot = path.resolve(readOption('--repo-root') ?? process.cwd());
const maturityPath = path.join(repoRoot, 'config/extensions/family-maturity.json');
const maturityDocs = [
  path.join(repoRoot, 'docs/extensions/phase4-readiness.md'),
  path.join(repoRoot, 'docs/extensions/foundation-closure-assessment.md'),
];
const claimDocs = [
  path.join(repoRoot, 'docs/extensions/phase4-readiness.md'),
  path.join(repoRoot, 'docs/extensions/foundation-closure-assessment.md'),
  path.join(repoRoot, 'docs/extensions/composition-spine/m0-release-examples.md'),
];

const LABEL = '[docs-maturity-sync]';
const startMarker = '<!-- family-maturity-table-start -->';
const endMarker = '<!-- family-maturity-table-end -->';

const DENIAL_CONTEXT_RE =
  /\b(does not|do not|did not|must not|must avoid|avoid implying|avoids implying|cannot|can't|should not|should avoid|is not|are not|no\b|not\b|never|without|unsupported|out of scope|anti-scope|excluded|exclusion|deferred|blocked|not cleared|not yet|reserved|planning-only|compatibility-only|source material only|future callers|future milestone|future deliverable|only as exclusions|explicitly scoped outside|remains blocked|stay outside)\b/i;
const POSITIVE_CLAIM_RE =
  /\b(supports?|supported|implements?|implemented|provides?|enabled?|enables?|allows?|uses?|includes?|brokers?|enforces?|isolates?|reviews?|installs?|loads?|discovers?|runs?|renders?|previews?|exports?|materializes?|executes?|certif(?:y|ies|ied)|controls?|safe|safely)\b/i;

const CLAIM_RULES = [
  {
    id: 'sandbox',
    description: 'sandbox / permission-enforcement capability',
    termPattern:
      /\b(sandbox(?:ing)?|permission broker|permission enforcement|code signing|iframe isolation|runtime enforcement)\b/i,
  },
  {
    id: 'marketplace',
    description: 'marketplace / remote-install capability',
    termPattern:
      /\b(marketplace|remote install|package install|remote extension discovery|dependency manager)\b/i,
  },
  {
    id: 'headless-renderer',
    description: 'headless-renderer capability',
    termPattern:
      /\b(headless renderer|headless rendering|webgpu renderer|visual graph editor)\b/i,
  },
  {
    id: 'physical-device',
    description: 'physical-device control capability',
    termPattern:
      /\b(physical-device|physical device|device control)\b/i,
  },
  {
    id: 'machine-path-executable-package',
    description:
      'machine-path / executable-package runtime, preview, export, or certification claim',
    termPattern:
      /\b(machine-path|executable-package)\b/i,
    capabilityPattern:
      /\b(preview(?: support)?|export(?: support)?|render(?:ing)?|execute|execution|runtime|sandbox(?:ing)?|certif(?:y|ies|ied|ication)|trusted-only|trusted only|physical-device|headless|control|safe|safety)\b/i,
  },
  {
    id: 'output-format-sidecar-runtime',
    description:
      'output-format / sidecar runtime-support claim beyond route-planning evidence',
    termPattern:
      /\b(output format|output-format|sidecar|sidecar-export)\b/i,
    capabilityPattern:
      /\b(runtime support|runtime execution|execution support|preview support|sandbox(?:ing)?|marketplace|headless|physical-device|certif(?:y|ies|ied|ication)|trusted-only|trusted only)\b/i,
  },
];

const warnings = [];
const failures = [];

function warn(message) {
  warnings.push(message);
  console.warn(`${LABEL} ${message}`);
}

function fail(message) {
  failures.push(message);
  console.error(`${LABEL} ${message}`);
}

function reportPolicyIssue(message) {
  if (isRelease || isWrite) {
    fail(message);
    return;
  }
  warn(message);
}

function relativeDoc(docPath) {
  return path.relative(repoRoot, docPath);
}

if (!fs.existsSync(maturityPath)) {
  fail(`Missing maturity registry: ${maturityPath}`);
}

let maturity = [];
if (failures.length === 0) {
  try {
    maturity = JSON.parse(fs.readFileSync(maturityPath, 'utf8'));
  } catch (error) {
    fail(`Unable to parse maturity registry: ${error.message}`);
  }
}

if (failures.length === 0 && !Array.isArray(maturity)) {
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
    const notes = family.hostIntegrationNotes
      ? family.hostIntegrationNotes.replace(/\|/g, '\\|').replace(/\n/g, ' ')
      : '';
    return `| ${family.label ?? family.kind} | ${family.declarationMaturity} | ${family.executionMaturity} | ${trusted} | ${bridged} | ${adapter} | ${notes} |`;
  });
  return [...header, ...rows, ''].join('\n');
}

function syncMaturityTables() {
  const generatedTable = buildTable();

  for (const docPath of maturityDocs) {
    if (!fs.existsSync(docPath)) {
      reportPolicyIssue(`Missing doc: ${docPath}`);
      continue;
    }

    const content = fs.readFileSync(docPath, 'utf8');
    const startIdx = content.indexOf(startMarker);
    const endIdx = content.indexOf(endMarker);

    if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
      const msg = `Missing or malformed family maturity markers in ${relativeDoc(docPath)}.`;
      if (isWrite) {
        const separator = content.endsWith('\n\n')
          ? ''
          : content.endsWith('\n')
            ? '\n'
            : '\n\n';
        const appendix = `${separator}## Family Maturity Snapshot\n\n${startMarker}\n${generatedTable}${endMarker}\n`;
        fs.writeFileSync(docPath, content + appendix, 'utf8');
        console.log(`${LABEL} Appended maturity table to ${relativeDoc(docPath)}.`);
        continue;
      }

      reportPolicyIssue(msg);
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
        console.log(`${LABEL} Updated maturity table in ${relativeDoc(docPath)}.`);
        continue;
      }

      reportPolicyIssue(`Stale maturity table in ${relativeDoc(docPath)}.`);
      continue;
    }

    console.log(`${LABEL} ${relativeDoc(docPath)} is up to date.`);
  }
}

function stripCodeBlocks(markdown) {
  return markdown.replace(/```[\s\S]*?```/g, '');
}

function stripInlineCode(markdown) {
  return markdown.replace(/`[^`]*`/g, '');
}

function normalizeClaimUnit(text) {
  return stripInlineCode(text)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_>#]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function extractClaimUnits(markdown) {
  const text = stripCodeBlocks(markdown);
  const lines = text.split('\n');
  const units = [];
  let currentText = [];
  let currentStartLine = 1;

  function flushCurrent() {
    if (currentText.length === 0) {
      return;
    }

    const joined = normalizeClaimUnit(currentText.join(' '));
    if (joined.length > 0) {
      units.push({
        line: currentStartLine,
        text: joined,
      });
    }
    currentText = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const trimmed = rawLine.trim();

    if (trimmed.length === 0) {
      flushCurrent();
      continue;
    }

    if (trimmed.startsWith('#')) {
      flushCurrent();
      continue;
    }

    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      flushCurrent();
      const normalized = normalizeClaimUnit(trimmed);
      if (normalized.length > 0) {
        units.push({
          line: index + 1,
          text: normalized,
        });
      }
      continue;
    }

    if (currentText.length === 0) {
      currentStartLine = index + 1;
    }
    currentText.push(trimmed);
  }

  flushCurrent();
  return units;
}

function classifyClaim(unitText) {
  return POSITIVE_CLAIM_RE.test(unitText) ? 'positive' : 'ambiguous';
}

function scanDocsClaims() {
  for (const docPath of claimDocs) {
    if (!fs.existsSync(docPath)) {
      reportPolicyIssue(`Missing doc-claims scan target: ${relativeDoc(docPath)}.`);
      continue;
    }

    const units = extractClaimUnits(fs.readFileSync(docPath, 'utf8'));

    for (const unit of units) {
      for (const rule of CLAIM_RULES) {
        if (!rule.termPattern.test(unit.text)) {
          continue;
        }
        if (rule.capabilityPattern && !rule.capabilityPattern.test(unit.text)) {
          continue;
        }
        if (DENIAL_CONTEXT_RE.test(unit.text)) {
          continue;
        }

        const claimKind = classifyClaim(unit.text);
        const excerpt = unit.text.length > 220
          ? `${unit.text.slice(0, 217)}...`
          : unit.text;
        reportPolicyIssue(
          `${relativeDoc(docPath)}:${unit.line} contains an unsupported ${claimKind} claim about ${rule.description}. Context: "${excerpt}"`,
        );
      }
    }

    console.log(`${LABEL} Scanned ${relativeDoc(docPath)} for unsupported capability claims.`);
  }
}

if (failures.length === 0) {
  syncMaturityTables();
  scanDocsClaims();
}

if (isWrite && failures.length === 0) {
  console.log(`${LABEL} Write pass complete.`);
}

if (failures.length > 0) {
  console.error(
    `${LABEL} ${(isRelease || isWrite) ? 'RELEASE' : 'AUDIT'} FAILED with ${failures.length} issue(s).`,
  );
  process.exit(1);
}

if (warnings.length > 0) {
  console.warn(`${LABEL} AUDIT PASSED with ${warnings.length} warning(s).`);
  process.exit(0);
}

console.log(`${LABEL} ${(isRelease || isWrite) ? 'RELEASE' : 'AUDIT'} PASSED.`);
