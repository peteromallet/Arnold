#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = new Set(process.argv.slice(2));
const enforce =
  args.has('--enforce') ||
  process.env.SLOT_FIRST_FIXTURE_LEGACY_ENFORCE === '1' ||
  process.env.CI_SLOT_FIRST_ENFORCE === '1';

const legacyPattern = /\b(generations|generation_variants|shot_generations|generation_id|variant_id|parent_generation_id|pair_shot_generation_id|child_generation_id|primary_variant_id)\b/g;
const testFilePattern = /((^|\/)(test_[^/]+|[^/]+_test)\.py|\.((test|spec)\.(ts|tsx|js|jsx|mjs|cjs|sql)|test\.sql|spec\.sql))$/i;
const skipDirs = new Set(['.git', 'node_modules', 'dist', 'build', 'coverage', 'test-results']);

function walk(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (skipDirs.has(entry.name) || entry.name.startsWith('_archived_')) continue;
      walk(full, out);
      continue;
    }
    if (testFilePattern.test(full.replace(repoRoot + '/', ''))) out.push(full);
  }
  return out;
}

const offenders = [];
for (const file of walk(repoRoot).sort()) {
  const relative = file.replace(`${repoRoot}/`, '');
  const content = readFileSync(file, 'utf8');
  const lines = content.split('\n');
  for (let index = 0; index < lines.length; index += 1) {
    legacyPattern.lastIndex = 0;
    const matches = [...lines[index].matchAll(legacyPattern)];
    if (matches.length === 0) continue;
    offenders.push({
      file: relative,
      line: index + 1,
      terms: [...new Set(matches.map((match) => match[1]))].join(', '),
    });
  }
}

if (offenders.length > 0) {
  const files = new Set(offenders.map((offender) => offender.file));
  const heading = `[test-fixture-legacy] found ${offenders.length} legacy reference(s) in ${files.size} test/spec file(s).`;
  if (enforce) {
    console.error(heading);
    for (const offender of offenders.slice(0, 200)) {
      console.error(` - ${offender.file}:${offender.line} (${offender.terms})`);
    }
    if (offenders.length > 200) console.error(` - ... ${offenders.length - 200} more`);
    process.exit(1);
  }
  console.warn(`${heading} M0 audit mode is inactive; M4 flips enforcement.`);
  for (const offender of offenders.slice(0, 50)) {
    console.warn(` - ${offender.file}:${offender.line} (${offender.terms})`);
  }
  if (offenders.length > 50) console.warn(` - ... ${offenders.length - 50} more`);
  process.exit(0);
}

console.log('[test-fixture-legacy] ok: no legacy references found in active test/spec files.');
