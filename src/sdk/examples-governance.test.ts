/**
 * SDK import governance test for extension examples.
 *
 * Verifies that every TypeScript file under src/examples/:
 *   1. Imports from @reigh/editor-sdk (the public SDK entrypoint)
 *   2. Does NOT deep-import from src/tools/video-editor/* internals
 *
 * This test is the executable proof for the governance rule enforced
 * by scripts/quality/check-video-editor-sdk-imports.mjs at the CLI level.
 */

import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const EXAMPLES_DIR = path.join(REPO_ROOT, 'src', 'examples');

/** Regex matching any import/export-from specifier (static + dynamic). */
const IMPORT_SPECIFIER_RE = /(?:import|export)\b[\s\S]*?\bfrom\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;

function extractSpecifiers(content: string): string[] {
  const specifiers = new Set<string>();
  for (const match of content.matchAll(IMPORT_SPECIFIER_RE)) {
    const specifier = match[1] ?? match[2];
    if (specifier) {
      specifiers.add(specifier);
    }
  }
  return [...specifiers];
}

function walkTsFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) return files;

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkTsFiles(fullPath));
    } else if (entry.isFile() && (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx'))) {
      files.push(fullPath);
    }
  }
  return files;
}

/** Check if a specifier resolves into src/tools/video-editor internals. */
function isVideoEditorInternal(relativePath: string, specifier: string): boolean {
  // Direct alias-based imports to video-editor internals
  if (specifier.startsWith('@/tools/video-editor')) return true;

  // Relative imports that resolve into src/tools/video-editor
  if (specifier.startsWith('.')) {
    const resolved = path.resolve(path.dirname(relativePath), specifier);
    // Normalize to check against the known forbidden directory
    const relative = path.relative(REPO_ROOT, resolved);
    const normalizedSep = relative.split(path.sep).join('/');
    if (normalizedSep.startsWith('src/tools/video-editor/')) return true;

    // Also check with possible extensions
    for (const ext of ['.ts', '.tsx', '/index.ts', '/index.tsx']) {
      const candidate = path.resolve(path.dirname(relativePath), specifier + ext);
      const candidateRel = path.relative(REPO_ROOT, candidate).split(path.sep).join('/');
      if (candidateRel.startsWith('src/tools/video-editor/')) return true;
    }
  }

  return false;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Extension example import governance', () => {
  const exampleFiles = walkTsFiles(EXAMPLES_DIR);

  it('has at least one example file to govern', () => {
    expect(exampleFiles.length).toBeGreaterThan(0);
  });

  for (const filePath of exampleFiles) {
    const relativePath = path.relative(REPO_ROOT, filePath);

    describe(relativePath, () => {
      const content = fs.readFileSync(filePath, 'utf8');
      const specifiers = extractSpecifiers(content);

      it('imports only from @reigh/editor-sdk (no video-editor internals)', () => {
        for (const specifier of specifiers) {
          expect(isVideoEditorInternal(relativePath, specifier)).toBe(false);
        }
      });

      it('imports from @reigh/editor-sdk', () => {
        const hasSdkImport = specifiers.some((s) => s === '@reigh/editor-sdk');
        expect(hasSdkImport).toBe(true);
      });

      it('has no bare-specifier imports other than @reigh/editor-sdk', () => {
        // Every non-relative import must be @reigh/editor-sdk
        for (const specifier of specifiers) {
          if (!specifier.startsWith('.') && !specifier.startsWith('@/')) {
            expect(specifier).toBe('@reigh/editor-sdk');
          }
        }
      });
    });
  }
});
