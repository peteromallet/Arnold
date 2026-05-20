#!/usr/bin/env node
import { existsSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = new Set(process.argv.slice(2));
const enforce =
  args.has('--enforce') ||
  process.env.SLOT_FIRST_PGTAP_ENFORCE === '1' ||
  process.env.CI_SLOT_FIRST_ENFORCE === '1';

const testRoots = [
  'supabase/tests/slot-first',
  'supabase/tests/slot_first',
];

function commandExists(command) {
  return spawnSync('sh', ['-c', `command -v ${command}`], { encoding: 'utf8' }).status === 0;
}

function walk(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, out);
      continue;
    }
    if (/\.sql$/i.test(entry.name)) out.push(full);
  }
  return out;
}

const dbUrl =
  process.env.SLOT_FIRST_DATABASE_URL ||
  process.env.DATABASE_URL ||
  process.env.SUPABASE_DB_URL ||
  process.env.POSTGRES_URL ||
  '';
const hasPgEnv = Boolean(process.env.PGHOST || process.env.PGDATABASE);
const files = [
  ...testRoots.flatMap((root) => walk(resolve(repoRoot, root))),
  ...walk(resolve(repoRoot, 'supabase/tests')).filter((file) => /slot[-_].*\.sql$/i.test(file)),
].sort();

const uniqueFiles = [...new Set(files)];

if (uniqueFiles.length === 0) {
  const message = '[slot-pgtap] no slot-first pgTAP SQL files found under supabase/tests.';
  if (process.env.SLOT_FIRST_PGTAP_REQUIRE_TESTS === '1') {
    console.error(`${message} SLOT_FIRST_PGTAP_REQUIRE_TESTS=1 makes this fatal.`);
    process.exit(1);
  }
  console.warn(`${message} M0 audit mode records the empty suite and exits successfully.`);
  process.exit(0);
}

if (!commandExists('psql')) {
  const message = '[slot-pgtap] psql is not available; pgTAP execution is skipped.';
  if (enforce) {
    console.error(`${message} Install psql or unset enforcement for M0 audit mode.`);
    process.exit(1);
  }
  console.warn(`${message} Audit mode did not count health checks as DB coverage.`);
  process.exit(0);
}

if (!dbUrl && !hasPgEnv) {
  const message = '[slot-pgtap] no database connection was provided.';
  if (enforce) {
    console.error(`${message} Set SLOT_FIRST_DATABASE_URL, DATABASE_URL, SUPABASE_DB_URL, POSTGRES_URL, or PG* env.`);
    process.exit(1);
  }
  console.warn(`${message} Audit mode skipped live pgTAP execution.`);
  process.exit(0);
}

for (const file of uniqueFiles) {
  const display = file.replace(`${repoRoot}/`, '');
  console.log(`[slot-pgtap] running ${display}`);
  const cmdArgs = dbUrl
    ? [dbUrl, '-v', 'ON_ERROR_STOP=1', '-f', file]
    : ['-v', 'ON_ERROR_STOP=1', '-f', file];
  const result = spawnSync('psql', cmdArgs, {
    cwd: repoRoot,
    env: process.env,
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    console.error(`[slot-pgtap] FAIL: ${display}`);
    process.exit(result.status ?? 1);
  }
}

console.log(`[slot-pgtap] ok: ${uniqueFiles.length} pgTAP file(s) passed.`);
