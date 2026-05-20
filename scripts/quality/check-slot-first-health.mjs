#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import net from 'node:net';

const args = new Set(process.argv.slice(2));
const enforce =
  args.has('--enforce') ||
  process.env.SLOT_FIRST_HEALTH_ENFORCE === '1' ||
  process.env.CI_SLOT_FIRST_ENFORCE === '1';

const envKeys = [
  'SLOT_FIRST_DATABASE_URL',
  'DATABASE_URL',
  'SUPABASE_DB_URL',
  'POSTGRES_URL',
  'PGHOST',
  'PGDATABASE',
  'PGUSER',
  'SUPABASE_URL',
  'SUPABASE_SERVICE_ROLE_KEY',
  'SUPABASE_ACCESS_TOKEN',
  'SUPABASE_PROJECT_REF',
];
const tools = ['psql', 'pg_dump', 'supabase'];
const ports = [54321, 54322, 54323, 54324, 5432];

function commandExists(command) {
  return spawnSync('sh', ['-c', `command -v ${command}`], { encoding: 'utf8' }).status === 0;
}

function checkPort(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port, timeout: 700 });
    socket.on('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.on('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.on('error', () => resolve(false));
  });
}

const presentEnv = envKeys.filter((key) => process.env[key]);
const presentTools = tools.filter(commandExists);
const openPorts = [];
for (const port of ports) {
  if (await checkPort(port)) openPorts.push(port);
}

console.log('[slot-first-health] readiness diagnostics only; this is not DB test coverage.');
console.log(`[slot-first-health] env keys present: ${presentEnv.length > 0 ? presentEnv.join(', ') : '(none)'}`);
console.log(`[slot-first-health] tools present: ${presentTools.length > 0 ? presentTools.join(', ') : '(none)'}`);
console.log(`[slot-first-health] local postgres/supabase ports open: ${openPorts.length > 0 ? openPorts.join(', ') : '(none)'}`);

const hasDbTarget = presentEnv.some((key) =>
  ['SLOT_FIRST_DATABASE_URL', 'DATABASE_URL', 'SUPABASE_DB_URL', 'POSTGRES_URL', 'PGHOST', 'PGDATABASE'].includes(key),
);
const hasDbTool = presentTools.includes('psql') || presentTools.includes('supabase');

if (enforce && (!hasDbTarget || !hasDbTool)) {
  console.error('[slot-first-health] FAIL: enforcement requires DB connection details and psql or Supabase CLI.');
  process.exit(1);
}

console.log('[slot-first-health] ok');
