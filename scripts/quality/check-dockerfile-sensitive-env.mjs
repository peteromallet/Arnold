import { readFileSync } from 'node:fs';

const dockerfile = readFileSync('Dockerfile', 'utf8');
const physicalLines = dockerfile.split(/\r?\n/);
const sensitiveNamePattern = /(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|CREDENTIAL|KEY)/i;
const allowedArgNames = new Set([
  // Supabase anon keys are public browser credentials. They are inlined into
  // Vite client bundles and protected by Supabase RLS, not secrecy.
  'VITE_SUPABASE_ANON_KEY',
]);

const violations = [];
const logicalLines = [];
let current = '';
let startLine = 0;

for (let index = 0; index < physicalLines.length; index += 1) {
  const rawLine = physicalLines[index];
  const trimmed = rawLine.trim();
  if (trimmed.length === 0 && current.length === 0) {
    continue;
  }
  if (trimmed.startsWith('#') && current.length === 0) {
    continue;
  }

  if (current.length === 0) {
    startLine = index + 1;
  }

  const hasContinuation = /\\\s*$/.test(rawLine);
  current += ` ${rawLine.replace(/\\\s*$/, '').trim()}`;

  if (!hasContinuation) {
    logicalLines.push({ line: startLine, text: current.trim() });
    current = '';
  }
}

if (current.length > 0) {
  logicalLines.push({ line: startLine, text: current.trim() });
}

for (const logicalLine of logicalLines) {
  const trimmed = logicalLine.text;
  if (trimmed.length === 0 || trimmed.startsWith('#')) {
    continue;
  }

  const instructionMatch = trimmed.match(/^(ARG|ENV)\s+(.+)$/i);
  if (!instructionMatch) {
    continue;
  }

  const instruction = instructionMatch[1].toUpperCase();
  const rest = instructionMatch[2].trim();
  const names = rest
    .split(/\s+/)
    .map((entry) => entry.split('=')[0])
    .filter(Boolean);

  for (const name of names) {
    if (!sensitiveNamePattern.test(name)) {
      continue;
    }
    if (instruction === 'ARG' && allowedArgNames.has(name)) {
      continue;
    }
    violations.push(`${instruction} ${name} on line ${logicalLine.line}`);
  }
}

if (violations.length > 0) {
  console.error('[dockerfile-sensitive-env] Sensitive-looking Docker ARG/ENV names found:');
  for (const violation of violations) {
    console.error(`  - ${violation}`);
  }
  process.exit(1);
}

console.log('[dockerfile-sensitive-env] ok');
