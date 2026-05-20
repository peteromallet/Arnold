#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = new Set(process.argv.slice(2));
const enforce =
  args.has('--enforce') ||
  process.env.SLOT_FIRST_SCHEMA_DRIFT_ENFORCE === '1' ||
  process.env.CI_SLOT_FIRST_ENFORCE === '1';

function commandExists(command) {
  return spawnSync('sh', ['-c', `command -v ${command}`], { encoding: 'utf8' }).status === 0;
}

function normalizeName(name) {
  return name
    .replace(/"/g, '')
    .replace(/^public\./i, '')
    .trim()
    .toLowerCase();
}

function addMatches(source, regex, set, prefix) {
  for (const match of source.matchAll(regex)) {
    set.add(`${prefix}:${normalizeName(match[1])}`);
  }
}

function parseObjects(source) {
  const objects = new Set();
  addMatches(source, /\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?((?:"?[\w]+"?\.)?"?[\w]+"?)/gi, objects, 'table');
  addMatches(source, /\bcreate\s+(?:or\s+replace\s+)?view\s+((?:"?[\w]+"?\.)?"?[\w]+"?)/gi, objects, 'view');
  addMatches(source, /\bcreate\s+materialized\s+view\s+(?:if\s+not\s+exists\s+)?((?:"?[\w]+"?\.)?"?[\w]+"?)/gi, objects, 'view');
  addMatches(source, /\bcreate\s+(?:or\s+replace\s+)?function\s+((?:"?[\w]+"?\.)?"?[\w]+"?)\s*\(/gi, objects, 'function');
  addMatches(source, /\bcreate\s+(?:or\s+replace\s+)?trigger\s+"?([\w]+)"?/gi, objects, 'trigger');
  return objects;
}

function parseColumns(source) {
  const columns = new Set();
  const createTable = /\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?((?:"?[\w]+"?\.)?"?[\w]+"?)\s*\(([\s\S]*?)\);/gi;
  for (const match of source.matchAll(createTable)) {
    const table = normalizeName(match[1]);
    for (const rawLine of match[2].split('\n')) {
      const line = rawLine.trim();
      if (!line || /^(constraint|primary|foreign|unique|check|exclude)\b/i.test(line)) continue;
      const columnMatch = line.match(/^"?([\w]+)"?\s+/);
      if (columnMatch) columns.add(`column:${table}.${normalizeName(columnMatch[1])}`);
    }
  }
  const alterColumn = /\balter\s+table\s+(?:only\s+)?((?:"?[\w]+"?\.)?"?[\w]+"?)\s+add\s+column\s+(?:if\s+not\s+exists\s+)?"?([\w]+)"?/gi;
  for (const match of source.matchAll(alterColumn)) {
    columns.add(`column:${normalizeName(match[1])}.${normalizeName(match[2])}`);
  }
  return columns;
}

function walkSql(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      walkSql(full, out);
      continue;
    }
    if (/\.sql$/i.test(entry.name)) out.push(full);
  }
  return out;
}

function loadTrackedSchema() {
  const sql = walkSql(resolve(repoRoot, 'supabase/migrations'))
    .sort()
    .map((file) => readFileSync(file, 'utf8'))
    .join('\n');
  return new Set([...parseObjects(sql), ...parseColumns(sql)]);
}

function loadLiveSchemaDump() {
  const dumpPath = process.env.SLOT_FIRST_SCHEMA_DUMP || process.env.SCHEMA_DUMP_PATH;
  if (dumpPath) {
    const absolute = resolve(repoRoot, dumpPath);
    if (!existsSync(absolute)) {
      throw new Error(`schema dump path does not exist: ${absolute}`);
    }
    return readFileSync(absolute, 'utf8');
  }

  const dbUrl =
    process.env.SLOT_FIRST_DATABASE_URL ||
    process.env.DATABASE_URL ||
    process.env.SUPABASE_DB_URL ||
    process.env.POSTGRES_URL ||
    '';
  if (!dbUrl) return null;
  if (!commandExists('pg_dump')) return null;

  const result = spawnSync(
    'pg_dump',
    ['--schema-only', '--no-owner', '--no-privileges', '--schema', 'public', dbUrl],
    { cwd: repoRoot, encoding: 'utf8', env: process.env },
  );
  if (result.status !== 0) {
    throw new Error(result.stderr || 'pg_dump failed');
  }
  return result.stdout;
}

const tracked = loadTrackedSchema();
let liveDump = null;
try {
  liveDump = loadLiveSchemaDump();
} catch (error) {
  console.error(`[schema-drift] FAIL: ${error.message}`);
  process.exit(1);
}

if (!liveDump) {
  const message = '[schema-drift] no live schema dump or pg_dump-capable DB connection available.';
  if (enforce) {
    console.error(`${message} Set SLOT_FIRST_SCHEMA_DUMP or DATABASE_URL plus pg_dump.`);
    process.exit(1);
  }
  console.warn(`${message} M0 audit mode skipped drift enforcement.`);
  console.log(`[schema-drift] tracked migration object/column keys parsed: ${tracked.size}`);
  process.exit(0);
}

const live = new Set([...parseObjects(liveDump), ...parseColumns(liveDump)]);
const ignored = /^(table|view|function|trigger|column):(schema_migrations|supabase_migrations|pg_|graphql|realtime|auth\.|storage\.)/;
const extras = [...live].filter((key) => !ignored.test(key) && !tracked.has(key)).sort();

if (extras.length > 0) {
  const heading = `[schema-drift] found ${extras.length} live public schema key(s) without tracked migration evidence:`;
  if (enforce) {
    console.error(heading);
    for (const key of extras) console.error(` - ${key}`);
    process.exit(1);
  }
  console.warn(heading);
  for (const key of extras.slice(0, 50)) console.warn(` - ${key}`);
  if (extras.length > 50) console.warn(` - ... ${extras.length - 50} more`);
  console.warn('[schema-drift] audit mode is inactive in M0; M4 flips enforcement.');
  process.exit(0);
}

console.log(`[schema-drift] ok: ${live.size} live key(s) matched tracked migration evidence.`);
