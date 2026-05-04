#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const configPath = path.join(repoRoot, 'config/governance/video-editor-sdk-import-allowlist.json');

function fail(message) {
  console.error(`[video-editor-sdk-imports] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(configPath)) {
  fail(`Missing config: ${path.relative(repoRoot, configPath)}`);
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const publicEntrypoints = new Set((config.publicEntrypoints ?? []).map(normalizeConfigPath));
const allowlist = new Map(
  Object.entries(config.allowlist ?? {}).map(([importer, targets]) => [
    normalizeConfigPath(importer),
    new Set((Array.isArray(targets) ? targets : []).map(normalizeConfigPath)),
  ]),
);

function normalizeConfigPath(filePath) {
  return filePath.split('/').join(path.sep);
}

function walk(dir, files = []) {
  if (!fs.existsSync(dir)) {
    return files;
  }

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === 'dist' || entry.name.startsWith('.')) {
      continue;
    }

    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    if (!fullPath.endsWith('.ts') && !fullPath.endsWith('.tsx')) {
      continue;
    }

    const relativePath = path.relative(repoRoot, fullPath);
    if (
      relativePath.includes(`${path.sep}__tests__${path.sep}`)
      || relativePath.endsWith('.test.ts')
      || relativePath.endsWith('.test.tsx')
      || relativePath.startsWith(`src${path.sep}tools${path.sep}video-editor${path.sep}`)
    ) {
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

function maybeResolveVideoEditorTarget(importerPath, specifier) {
  if (!specifier) {
    return null;
  }

  if (specifier.startsWith('@/tools/video-editor')) {
    const suffix = specifier.slice('@/'.length);
    return resolveCandidate(path.join(repoRoot, 'src', suffix));
  }

  if (specifier.startsWith('.') || specifier.startsWith('/')) {
    const candidate = specifier.startsWith('/')
      ? path.join(repoRoot, specifier)
      : path.resolve(path.dirname(importerPath), specifier);
    const resolved = resolveCandidate(candidate);
    if (!resolved) {
      return null;
    }
    const relative = path.relative(repoRoot, resolved);
    if (!relative.startsWith(`src${path.sep}tools${path.sep}video-editor${path.sep}`)) {
      return null;
    }
    return resolved;
  }

  return null;
}

function resolveCandidate(candidate) {
  const normalized = candidate.replace(/[?#].*$/, '');
  const candidates = [
    normalized,
    `${normalized}.ts`,
    `${normalized}.tsx`,
    path.join(normalized, 'index.ts'),
    path.join(normalized, 'index.tsx'),
  ];

  for (const option of candidates) {
    if (fs.existsSync(option) && fs.statSync(option).isFile()) {
      return option;
    }
  }

  return null;
}

function extractSpecifiers(content) {
  const specifiers = new Set();
  const fromPattern = /\b(?:import|export)\b[\s\S]*?\bfrom\s+['"]([^'"]+)['"]/g;
  const dynamicPattern = /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g;

  for (const match of content.matchAll(fromPattern)) {
    specifiers.add(match[1]);
  }
  for (const match of content.matchAll(dynamicPattern)) {
    specifiers.add(match[1]);
  }

  return [...specifiers];
}

const files = [
  ...walk(path.join(repoRoot, 'src')),
  ...walk(path.join(repoRoot, 'supabase/functions')),
];

const failures = [];

for (const filePath of files) {
  const content = fs.readFileSync(filePath, 'utf8');
  const importer = path.relative(repoRoot, filePath);
  const allowedTargets = allowlist.get(normalizeConfigPath(importer)) ?? new Set();

  for (const specifier of extractSpecifiers(content)) {
    const resolvedTarget = maybeResolveVideoEditorTarget(filePath, specifier);
    if (!resolvedTarget) {
      continue;
    }

    const target = path.relative(repoRoot, resolvedTarget);
    const normalizedTarget = normalizeConfigPath(target);

    if (publicEntrypoints.has(normalizedTarget)) {
      continue;
    }

    if (allowedTargets.has(normalizedTarget)) {
      continue;
    }

    failures.push({
      importer,
      specifier,
      target,
    });
  }
}

if (failures.length > 0) {
  console.error('[video-editor-sdk-imports] FAILED: unsupported deep imports into src/tools/video-editor were found.');
  console.error('[video-editor-sdk-imports] Use the public entrypoints or extend the explicit allowlist for host-only adapters.');
  for (const failure of failures) {
    console.error(`  - ${failure.importer}`);
    console.error(`      import: ${failure.specifier}`);
    console.error(`      target: ${failure.target}`);
  }
  process.exit(1);
}

console.log('[video-editor-sdk-imports] OK: all external video-editor imports use public entrypoints or the approved allowlist.');
