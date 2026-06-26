import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const repoRoot = process.cwd();
const readmePath = resolve(repoRoot, 'README.md');
const mapPath = resolve(repoRoot, 'config/governance/contract-surface-map.json');

function fail(message) {
  console.error(`[check-contract-surface-map] ${message}`);
  process.exit(1);
}

if (!existsSync(mapPath)) {
  fail(`Missing map file: ${mapPath}`);
}
if (!existsSync(readmePath)) {
  fail(`Missing README: ${readmePath}`);
}

let mapping;
try {
  mapping = JSON.parse(readFileSync(mapPath, 'utf8'));
} catch (error) {
  fail(`Invalid JSON in ${mapPath}: ${String(error)}`);
}

if (!mapping || typeof mapping !== 'object' || Array.isArray(mapping)) {
  fail('Map must be a JSON object of gate -> file[]');
}

const readme = readFileSync(readmePath, 'utf8');
const errors = [];

for (const [gate, surfaces] of Object.entries(mapping)) {
  if (gate === 'description' || gate.startsWith('_')) continue;
  if (!Array.isArray(surfaces) || surfaces.length === 0) {
    errors.push(`Gate "${gate}" must map to a non-empty array`);
    continue;
  }

  const gateTokenPlain = `\`${gate}\``;
  const gateTokenNpm = `\`npm run ${gate}\``;
  if (!readme.includes(gateTokenPlain) && !readme.includes(gateTokenNpm)) {
    errors.push(`README is missing gate command reference: ${gate}`);
  }

  for (const surface of surfaces) {
    if (typeof surface !== 'string' || !surface.trim()) {
      errors.push(`Gate "${gate}" includes an invalid surface entry`);
      continue;
    }

    const absSurface = resolve(repoRoot, surface);
    if (!existsSync(absSurface)) {
      errors.push(`Mapped surface does not exist: ${surface}`);
    }
    if (!readme.includes(`\`${surface}\``)) {
      errors.push(`README gate mapping section is missing surface path: ${surface}`);
    }
  }
}

if (errors.length > 0) {
  errors.forEach((entry) => console.error(`[check-contract-surface-map] ${entry}`));
  process.exit(1);
}

console.log('[check-contract-surface-map] ok');
