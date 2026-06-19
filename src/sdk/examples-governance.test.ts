/**
 * SDK import governance test for extension examples.
 *
 * Verifies that every TypeScript file under src/examples/:
 *   1. Imports from @reigh/editor-sdk (the public SDK entrypoint)
 *   2. Does NOT deep-import from src/tools/video-editor/* internals
 *   3. Examples collectively cover every public SDK surface class
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
const SDK_INDEX = path.join(REPO_ROOT, 'src', 'sdk', 'index.ts');

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
// SDK surface extraction
// ---------------------------------------------------------------------------

/** Regex matching `export (type|interface|class|function|const|let|var) Name`. */
const SDK_EXPORT_RE = /^export\s+(?:(?:declare\s+)?(?:type|interface|class|function|const|let|var)\s+)([A-Za-z_$][\w$]*)/gm;

/**
 * Extract the set of named exports from src/sdk/index.ts.
 * Uses a simple regex-based approach that captures type, interface,
 * class, function, const, let, and var exports.
 */
function extractSdkExports(): Set<string> {
  const content = fs.readFileSync(SDK_INDEX, 'utf8');
  const names = new Set<string>();
  for (const match of content.matchAll(SDK_EXPORT_RE)) {
    names.add(match[1]);
  }
  return names;
}

/**
 * Extract all names imported from @reigh/editor-sdk in a given file.
 * Handles both `import { A, B } from '@reigh/editor-sdk'` and
 * `import type { C } from '@reigh/editor-sdk'` forms.
 */
function extractSdkImports(filePath: string): Set<string> {
  const content = fs.readFileSync(filePath, 'utf8');
  const names = new Set<string>();

  // Match import { ... } from '@reigh/editor-sdk' (value + type imports)
  const importBlockRe = /import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+['"]@reigh\/editor-sdk['"]/g;
  for (const match of content.matchAll(importBlockRe)) {
    const block = match[1];
    // Split on commas, handle `as` aliases
    for (const part of block.split(',')) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      // Handle `Name as Alias` — take the original name
      const nameMatch = trimmed.match(/^([A-Za-z_$][\w$]*)\s*(?:as\s+[A-Za-z_$][\w$]*)?/);
      if (nameMatch) {
        names.add(nameMatch[1]);
      }
    }
  }

  // Match default imports: import Name from '@reigh/editor-sdk'
  const defaultImportRe = /import\s+([A-Za-z_$][\w$]*)\s+from\s+['"]@reigh\/editor-sdk['"]/g;
  for (const match of content.matchAll(defaultImportRe)) {
    names.add(match[1]);
  }

  return names;
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

  describe('Public surface class coverage', () => {
    const sdkExports = extractSdkExports();

    // Collect all names imported from @reigh/editor-sdk across all examples
    const allSdkImports = new Set<string>();
    for (const filePath of exampleFiles) {
      const imports = extractSdkImports(filePath);
      for (const name of imports) {
        allSdkImports.add(name);
      }
    }

    // Exports that are internal helpers not expected in consumer examples
    const INTERNAL_EXPORTS = new Set([
      'CONTEXT_DISPOSE_SYMBOL',    // Symbol key, not intended for direct consumer use
      'disposeExtensionContextServices', // Internal lifecycle, not consumer-facing
    ]);

    it('has SDK exports to validate', () => {
      expect(sdkExports.size).toBeGreaterThan(0);
    });

    for (const exportName of sdkExports) {
      if (INTERNAL_EXPORTS.has(exportName)) {
        it(`SKIP: ${exportName} is an internal helper (excluded from coverage)`, () => {
          // Internal helpers are excluded from the public surface coverage requirement
        });
        continue;
      }

      it(`public export "${exportName}" is imported by at least one example`, () => {
        expect(allSdkImports.has(exportName)).toBe(true);
      });
    }
  });
});

// ---------------------------------------------------------------------------
// Frontend closure checklist presence assertion
// ---------------------------------------------------------------------------

describe('Frontend closure checklist governance', () => {
  const CHECKLIST_PATH = path.join(
    REPO_ROOT,
    'docs',
    'video-editor',
    'frontend-closure-checklist.md',
  );

  it('checklist document exists at the canonical path', () => {
    expect(fs.existsSync(CHECKLIST_PATH)).toBe(true);
  });

  const CHECKLIST_SECTIONS = [
    'Host surface identity',
    'State completeness',
    'Diagnostic fallback',
    'Accessibility behavior',
    'Test path',
  ];

  for (const section of CHECKLIST_SECTIONS) {
    it(`checklist contains required section: "${section}"`, () => {
      const content = fs.readFileSync(CHECKLIST_PATH, 'utf8');
      expect(content.includes(section)).toBe(true);
    });
  }
});
