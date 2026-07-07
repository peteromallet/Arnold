#!/usr/bin/env node
/**
 * Trust Model Truth Gate
 *
 * Scans extension-facing SDK, schema, UI, docs, example, and quality-script
 * surfaces for active claims that V1 extensions are sandboxed, permission
 * enforced, marketplace safe, third-party safe, untrusted-source ready, or
 * capability gated. Explicit negation and future-deferral language is allowed.
 *
 * This gate is intentionally separate from contribution drift checks: it
 * audits trust-model language, not manifest kind/schema enumeration drift.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const args = process.argv.slice(2);
const argSet = new Set(args);
const mode = argSet.has('--audit') ? 'audit' : 'release';
const LABEL = '[trust-model-truth]';

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
const selfPath = path.resolve(new URL(import.meta.url).pathname);

const SOURCE_EXTENSIONS = new Set(['.ts', '.tsx', '.js', '.mjs', '.json', '.md', '.txt']);

const SCAN_TARGETS = [
  'config/contracts/reigh-extension.schema.json',
  'src/sdk',
  'src/tools/video-editor/components/ExtensionManager',
  'src/tools/video-editor/examples/extensions',
  'docs/extensions',
  'docs/video-editor',
  'scripts/quality',
];

const DENIAL_CONTEXT_RE =
  /\b(?:no|not|never|without|none|false|cannot|can't|does not|do not|is not|are not|isn't|aren't|lack(?:s|ing)?|missing|absent|absence|unsupported|out[- ]of[- ]scope|anti[- ]scope|excluded|exclusion|avoid(?:s|ing)?|blocked until|non[- ]enforced|not enforced|not runtime[- ]enforced|not mediated|not surfaced|not authorized|descriptive only|metadata only|declarative (?:metadata|access disclosure)s? only|trusted[- ]local|unsandboxed)\b/i;

const FUTURE_CONTEXT_RE =
  /\b(?:future|deferred|later|eventual|planned|aspirational|not yet|until|before|beyond|expected .*milestone|tracked as future|must exist|must be added|must gate|must run|must present|when .* (?:exists|exist|introduced|arrives)|if .* (?:introduces|introduced|exists)|requires? .* before|m\d+\+?|reserved for m\d+|future isolation|brokered-host-api epic|future work)\b/i;

const RULES = [
  {
    id: 'sandbox-or-isolation',
    description: 'sandboxing or isolation support',
    pattern:
      /\b(?:sandbox(?:ed|ing)?|iframe isolation|worker isolation|shadowrealm|process isolation|isolated (?:javascript )?realm|isolation boundary|sandbox isolation)\b/i,
  },
  {
    id: 'runtime-permission-enforcement',
    description: 'runtime permission enforcement, permission brokers, or permission gates',
    pattern:
      /\b(?:runtime permission enforcement|permission enforcement|runtime enforcement|permission broker|brokered host api|permission prompts?|permission gating|permission gate|gate browser api access|permissions? (?:are |is )?(?:enforced|checked)|enforced permissions?|host-mediated browser api access)\b/i,
  },
  {
    id: 'marketplace-or-third-party-safety',
    description: 'marketplace safety or third-party extension safety',
    pattern:
      /\b(?:marketplace(?: review| safety)?|third[- ]party (?:safety|safe|extension support|package registry|package|extension|registry)|safe third[- ]party|remote extension discovery|remote install|dependency manager|package install)\b/i,
  },
  {
    id: 'untrusted-extension-support',
    description: 'untrusted, arbitrary, or remote extension support',
    pattern:
      /\b(?:untrusted (?:extension|extensions|source|sources|package|packages|code)|arbitrary (?:extension|extensions|package|packages)|remote (?:extension|extensions|package|packages|source|sources))\b/i,
  },
  {
    id: 'permission-checks',
    description: 'permission checks, permission approvals, or granted capabilities',
    pattern:
      /\b(?:permission checks?|checks? permissions?|permission-checked|permission validation|permission approval|approval prompt|grant(?:ed|ing)? capabilities?|permission grant(?:s|ed)?|requested permissions?)\b/i,
  },
  {
    id: 'capability-gates',
    description: 'capability gates or capability-based enforcement',
    pattern:
      /\b(?:capability gates?|capability-based gating|capability-based enforcement|capability enforcement|capability-based proxy|capabilities? (?:are |is )?(?:granted|approved|enforced|gated)|gate actual host-mediated browser api access)\b/i,
  },
];

function toRepoPath(filePath) {
  return path.relative(repoRoot, filePath).replaceAll(path.sep, '/');
}

function exists(target) {
  try {
    fs.accessSync(target, fs.constants.R_OK);
    return true;
  } catch {
    return false;
  }
}

function isExcludedPath(relativePath) {
  return (
    relativePath.includes('/node_modules/')
    || relativePath.includes('/.git/')
    || relativePath.includes('/.megaplan/')
    || relativePath.includes('/vendor/')
    || relativePath.includes('/dist/')
    || relativePath.includes('/coverage/')
    || relativePath.includes('/__fixtures__/')
    || relativePath.includes('/fixtures/')
    || relativePath.includes('/__tests__/')
    || /\.test\.[cm]?[jt]sx?$/.test(relativePath)
    || /\.spec\.[cm]?[jt]sx?$/.test(relativePath)
  );
}

function isRelevantVideoEditorDoc(relativePath) {
  if (!relativePath.startsWith('docs/video-editor/')) {
    return true;
  }
  const base = path.basename(relativePath).toLowerCase();
  return base.includes('extension') || base.includes('trust') || base.includes('readiness');
}

function isQualityScriptFile(relativePath) {
  return relativePath.startsWith('scripts/quality/') && relativePath.endsWith('.mjs');
}

function shouldScanFile(filePath) {
  const relativePath = toRepoPath(filePath);
  if (path.resolve(filePath) === selfPath) {
    return false;
  }
  if (isExcludedPath(`/${relativePath}`)) {
    return false;
  }
  if (!SOURCE_EXTENSIONS.has(path.extname(filePath))) {
    return false;
  }
  if (relativePath.startsWith('docs/video-editor/') && !isRelevantVideoEditorDoc(relativePath)) {
    return false;
  }
  if (relativePath.startsWith('scripts/quality/') && !isQualityScriptFile(relativePath)) {
    return false;
  }
  return true;
}

function collectFiles(targetPath, results) {
  const stat = fs.statSync(targetPath);
  if (stat.isFile()) {
    if (shouldScanFile(targetPath)) {
      results.push(targetPath);
    }
    return;
  }

  if (!stat.isDirectory()) {
    return;
  }

  for (const entry of fs.readdirSync(targetPath, { withFileTypes: true })) {
    const child = path.join(targetPath, entry.name);
    const relativePath = `/${toRepoPath(child)}`;
    if (entry.isDirectory() && isExcludedPath(relativePath)) {
      continue;
    }
    collectFiles(child, results);
  }
}

function scanFiles() {
  const files = [];
  for (const target of SCAN_TARGETS) {
    const absolute = path.resolve(repoRoot, target);
    if (!exists(absolute)) {
      continue;
    }
    collectFiles(absolute, files);
  }

  return [...new Set(files)].sort((a, b) => toRepoPath(a).localeCompare(toRepoPath(b)));
}

function normalize(text) {
  return text
    .replace(/[“”]/g, '"')
    .replace(/[’]/g, "'")
    .replace(/[—–]/g, '-')
    .replace(/\s+/g, ' ')
    .trim();
}

function contextFor(lines, index) {
  const start = Math.max(0, index - 5);
  const end = Math.min(lines.length, index + 3);
  return normalize(lines.slice(start, end).join(' '));
}

function isQualityScriptRuleDefinition(relativePath, line) {
  if (!relativePath.startsWith('scripts/quality/')) {
    return false;
  }

  return /\b(?:CLAIM_RULES|RISKY_TERMS|DENIAL_CONTEXT|POSITIVE_CLAIM|termPattern|capabilityPattern|const .*_RE|new RegExp)\b/.test(line)
    || /\b(?:id|term|pattern|description):/.test(line)
    || /\/\\b/.test(line);
}

function isAllowedContext(context) {
  return DENIAL_CONTEXT_RE.test(context) || FUTURE_CONTEXT_RE.test(context);
}

function findViolations(filePath) {
  const relativePath = toRepoPath(filePath);
  const text = fs.readFileSync(filePath, 'utf8');
  const lines = text.split(/\r?\n/);
  const violations = [];

  for (let index = 0; index < lines.length; index += 1) {
    const line = normalize(lines[index]);
    if (!line || isQualityScriptRuleDefinition(relativePath, line)) {
      continue;
    }

    const matchingRules = RULES.filter((rule) => rule.pattern.test(line));
    if (matchingRules.length === 0) {
      continue;
    }

    const context = contextFor(lines, index);
    if (isAllowedContext(context)) {
      continue;
    }

    for (const rule of matchingRules) {
      violations.push({
        file: relativePath,
        line: index + 1,
        rule: rule.id,
        description: rule.description,
        excerpt: line.length > 240 ? `${line.slice(0, 237)}...` : line,
      });
    }
  }

  return violations;
}

const files = scanFiles();
const violations = files.flatMap(findViolations);

console.log(`${LABEL} scanned ${files.length} file(s) in ${mode} mode.`);

if (violations.length > 0) {
  const stream = mode === 'audit' ? console.warn : console.error;
  stream(`${LABEL} found ${violations.length} active unsupported trust-model claim(s):`);
  for (const violation of violations) {
    stream(
      `${LABEL} ${violation.file}:${violation.line} [${violation.rule}] `
      + `${violation.description}: ${violation.excerpt}`,
    );
  }

  if (mode === 'audit') {
    console.log(`${LABEL} OK (audit mode): active claims reported as warnings.`);
    process.exit(0);
  }

  console.error(
    `${LABEL} FAILED: rewrite the claim with explicit negation/non-enforcement wording, `
      + 'or defer it to a future isolation or brokered-host-API epic.',
  );
  process.exit(1);
}

console.log(`${LABEL} OK: no active unsupported trust-model claims detected.`);
