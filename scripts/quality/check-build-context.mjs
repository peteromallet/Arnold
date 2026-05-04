#!/usr/bin/env node
// Guards against the class of bug that broke the Railway deploy on c99e760ec:
// references to paths outside the repo (the Docker build context). When a
// package.json file: dep or a vite/vitest alias points outside the repo, the
// docker --check gate stays green but `npm ci` fails on Railway with a
// misleading "no package-lock.json" message and the bundler fails to load
// generated imports.
//
// This check trips fast (<1s) and explains the fix.

import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const errors = [];

const packageJson = JSON.parse(readFileSync(resolve(repoRoot, 'package.json'), 'utf8'));
for (const section of ['dependencies', 'devDependencies', 'optionalDependencies']) {
  const deps = packageJson[section] ?? {};
  for (const [name, spec] of Object.entries(deps)) {
    if (typeof spec !== 'string' || !spec.startsWith('file:')) continue;
    const target = spec.slice('file:'.length);
    const absolute = resolve(repoRoot, target);
    if (!absolute.startsWith(repoRoot + '/') && absolute !== repoRoot) {
      errors.push(
        `package.json ${section}["${name}"] = "${spec}" resolves to ${absolute}, ` +
        `which is outside the repo. Vendor it under reigh-app/vendor/ instead — ` +
        `Railway's build context is the repo root and cannot reach sibling dirs.`,
      );
      continue;
    }
    if (!existsSync(absolute)) {
      errors.push(
        `package.json ${section}["${name}"] points to ${target} but ${absolute} ` +
        `does not exist.`,
      );
    }
  }
}

const aliasFiles = [
  { file: 'config/vite/vite.config.ts', label: 'vite' },
  { file: 'config/testing/vitest.config.ts', label: 'vitest' },
];
const aliasPattern = /['"]@workspace-[a-z0-9-]+['"]\s*:\s*path\.resolve\(\s*([^,]+)\s*,\s*['"]([^'"]+)['"]\s*\)/g;
for (const { file, label } of aliasFiles) {
  const path = resolve(repoRoot, file);
  if (!existsSync(path)) continue;
  const source = readFileSync(path, 'utf8');
  const fileDir = dirname(path);
  for (const match of source.matchAll(aliasPattern)) {
    const baseExpr = match[1].trim();
    const relative = match[2];
    // We assume path.resolve(__dirname, '...') / path.resolve(projectRoot, '...').
    // For __dirname the base is the directory of this config file; for
    // projectRoot it's the repo root. Both cases are covered by anchoring at
    // the file's dir or at repoRoot — pick the one that yields a path inside
    // the repo when possible.
    const base = baseExpr === '__dirname' ? fileDir : repoRoot;
    const absolute = resolve(base, relative);
    if (!absolute.startsWith(repoRoot + '/') && absolute !== repoRoot) {
      errors.push(
        `${file} (${label}) defines an @workspace-* alias that escapes the repo: ` +
        `${baseExpr} + "${relative}" -> ${absolute}. Point it at vendor/ instead.`,
      );
    }
  }
}

if (errors.length > 0) {
  console.error('[build-context] FAIL:');
  for (const error of errors) {
    console.error(`  - ${error}`);
  }
  process.exit(1);
}
console.log('[build-context] ok');
