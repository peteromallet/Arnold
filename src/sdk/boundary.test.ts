/**
 * SDK boundary and flagship example import compliance tests.
 *
 * Proves:
 *   1. The flagship example imports exclusively from @reigh/editor-sdk.
 *   2. No internal video-editor imports leak into extension code.
 *   3. @reigh/editor-sdk exports are sufficient to write an extension.
 *   4. ExtensionContext exposes no raw internal members (DataProvider,
 *      applyEdit, timeline store, internal mutation escape hatches).
 */

import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  defineExtension,
  createExtensionContext,
  validateExtensionId,
  validateContributionId,
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
} from '@/sdk/index';
import type {
  ReighExtension,
  ExtensionManifest,
  ExtensionContribution,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  ExportDiagnostic,
  ContributionKind,
  VideoEditorSlotName,
  ExtensionSettingsService,
  ExtensionI18nService,
  ExtensionDiagnosticsService,
  ExtensionChromeService,
  CreativeContext,
  ProcessManifestEntry,
  ExtensionPermissionDeclaration,
  ProjectExtensionRequirement,
  ProjectExtensionRequirements,
  DefineExtensionOptions,
  ExtensionActivateFn,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeSavePayload,
  ChromeRenderStatusPayload,
  ChromeEventPayload,
  DiagnosticSeverity,
} from '@/sdk/index';

// ---------------------------------------------------------------------------
// Helpers — path resolution and import extraction
// ---------------------------------------------------------------------------

const REPO_ROOT = path.resolve(import.meta.dirname, '../..');

const FLAGSHIP_DIR = path.join(
  REPO_ROOT,
  'src',
  'tools',
  'video-editor',
  'examples',
  'extensions',
  'flagship-local',
);

/** Regex matching any static or dynamic import/export-from specifier. */
const IMPORT_SPECIFIER_RE =
  /(?:import|export)\b[\s\S]*?\bfrom\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;

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
    } else if (
      entry.isFile() &&
      (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx'))
    ) {
      files.push(fullPath);
    }
  }
  return files;
}

function isVideoEditorInternal(
  relativePath: string,
  specifier: string,
): boolean {
  if (specifier.startsWith('@/tools/video-editor')) return true;

  if (specifier.startsWith('.')) {
    const resolved = path.resolve(path.dirname(relativePath), specifier);
    const relative = path.relative(REPO_ROOT, resolved);
    const normalizedSep = relative.split(path.sep).join('/');
    if (normalizedSep.startsWith('src/tools/video-editor/')) return true;

    for (const ext of ['.ts', '.tsx', '/index.ts', '/index.tsx']) {
      const candidate = path.resolve(
        path.dirname(relativePath),
        specifier + ext,
      );
      const candidateRel = path
        .relative(REPO_ROOT, candidate)
        .split(path.sep)
        .join('/');
      if (candidateRel.startsWith('src/tools/video-editor/')) return true;
    }
  }

  return false;
}

// ---------------------------------------------------------------------------
// 1. Flagship example import compliance
// ---------------------------------------------------------------------------

describe('Flagship local extension — import boundary', () => {
  const flagshipFiles = walkTsFiles(FLAGSHIP_DIR);

  it('has at least one TypeScript file (the flagship index)', () => {
    expect(flagshipFiles.length).toBeGreaterThan(0);
  });

  for (const filePath of flagshipFiles) {
    const relativePath = path.relative(REPO_ROOT, filePath);

    describe(relativePath, () => {
      const content = fs.readFileSync(filePath, 'utf8');
      const specifiers = extractSpecifiers(content);

      it('imports exclusively from @reigh/editor-sdk (no video-editor internals)', () => {
        for (const specifier of specifiers) {
          expect(isVideoEditorInternal(relativePath, specifier)).toBe(false);
        }
      });

      it('imports from @reigh/editor-sdk', () => {
        const hasSdkImport = specifiers.some(
          (s) => s === '@reigh/editor-sdk',
        );
        expect(hasSdkImport).toBe(true);
      });

      it('has no bare-specifier imports other than @reigh/editor-sdk', () => {
        for (const specifier of specifiers) {
          if (!specifier.startsWith('.') && !specifier.startsWith('@/')) {
            expect(specifier).toBe('@reigh/editor-sdk');
          }
        }
      });
    });
  }
});

// ---------------------------------------------------------------------------
// 2. SDK sufficiency — every API the flagship uses is actually exported
// ---------------------------------------------------------------------------

describe('@reigh/editor-sdk sufficiency', () => {
  // Value exports used by the flagship
  it('exports defineExtension (used by flagship)', () => {
    expect(typeof defineExtension).toBe('function');
  });

  it('exports createExtensionContext (consumer API)', () => {
    expect(typeof createExtensionContext).toBe('function');
  });

  // Type exports — we test that they resolve at the value level where possible
  it('exports ExtensionContext that is constructable via createExtensionContext', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.sufficiency.test' as any,
        version: '1.0.0',
        label: 'Sufficiency Test',
        contributions: [],
      },
    });
    const ctx: ExtensionContext = createExtensionContext(ext);
    expect(ctx.apiVersion).toBe(1);
    expect(ctx.extension.id).toBe('com.sufficiency.test');
  });

  it('exports DisposeHandle type compatible with chrome.subscribe', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.disposehandle.test' as any,
        version: '1.0.0',
        label: 'Dispose Test',
        contributions: [],
      },
    });
    const ctx = createExtensionContext(ext);
    const handle: DisposeHandle = ctx.chrome.subscribe('toast', () => {});
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });

  it('exports all service interfaces used by flagship', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.services.test' as any,
        version: '1.0.0',
        label: 'Services Test',
        contributions: [],
      },
    });
    const ctx = createExtensionContext(ext);

    // ExtensionSettingsService
    const settings: ExtensionSettingsService = ctx.services.settings;
    expect(typeof settings.get).toBe('function');
    expect(typeof settings.set).toBe('function');
    expect(typeof settings.delete).toBe('function');
    expect(typeof settings.keys).toBe('function');

    // ExtensionI18nService
    const i18n: ExtensionI18nService = ctx.services.i18n;
    expect(typeof i18n.t).toBe('function');

    // ExtensionDiagnosticsService
    const diag: ExtensionDiagnosticsService = ctx.services.diagnostics;
    expect(typeof diag.report).toBe('function');
    expect(Array.isArray(diag.diagnostics)).toBe(true);

    // ExtensionChromeService
    const chrome: ExtensionChromeService = ctx.chrome;
    expect(typeof chrome.toast).toBe('function');
    expect(typeof chrome.progress).toBe('function');
    expect(typeof chrome.subscribe).toBe('function');
    expect(typeof chrome.focus).toBe('function');
    expect(typeof chrome.announce).toBe('function');
  });

  it('exports creative stubs that throw typed errors', () => {
    const stubs: CreativeContext = createCreativeContextStubs();
    expect(() => stubs.project).toThrow(ExtensionNotImplementedError);
    expect(() => stubs.timeline).toThrow(ExtensionNotImplementedError);
  });

  it('exports all ID validation helpers', () => {
    expect(typeof validateExtensionId).toBe('function');
    expect(typeof validateContributionId).toBe('function');
    expect(validateExtensionId('com.test.valid')).toEqual([]);
  });

  it('exports contribution kind bridging helpers', () => {
    expect(typeof contributionKindNotYetBridged).toBe('function');
    expect(typeof CONTRIBUTION_KIND_MILESTONE).toBe('object');
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('effect')).toBe('M3');
  });
});

// ---------------------------------------------------------------------------
// 3. ExtensionContext exposes no raw internal members
// ---------------------------------------------------------------------------

describe('ExtensionContext — no internal members exposed', () => {
  let ctx: ExtensionContext;

  function makeCtx(): ExtensionContext {
    const ext = defineExtension({
      manifest: {
        id: 'com.boundary.test' as any,
        version: '1.0.0',
        label: 'Boundary Test Extension',
        description: 'Used for boundary verification',
        apiVersion: 1,
        contributions: [
          {
            id: 'boundary-slot' as any,
            kind: 'slot',
            slot: 'toolbar',
            order: 10,
            label: 'Boundary slot',
          },
        ],
      },
    });
    return createExtensionContext(ext);
  }

  beforeEach(() => {
    ctx = makeCtx();
  });

  // ---- exactly the approved surface ---------------------------------------

  it('has exactly the expected own property names', () => {
    const keys = Object.keys(ctx).sort();
    expect(keys).toEqual([
      'apiVersion',
      'chrome',
      'creative',
      'extension',
      'services',
    ]);
  });

  it('has no extra enumerable properties', () => {
    const allowed = new Set([
      'apiVersion',
      'extension',
      'chrome',
      'services',
      'creative',
    ]);
    for (const key of Object.keys(ctx)) {
      expect(allowed.has(key)).toBe(true);
    }
  });

  // ---- no DataProvider -----------------------------------------------------

  it('does not expose DataProvider', () => {
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.DataProvider).toBeUndefined();
    expect(ctxAny.dataProvider).toBeUndefined();
    expect(ctxAny.provider).toBeUndefined();
    expect(ctxAny.data).toBeUndefined();
    expect(ctxAny.dataProviderRef).toBeUndefined();
    expect(ctxAny.getDataProvider).toBeUndefined();
  });

  // ---- no applyEdit / mutation escape hatches ------------------------------

  it('does not expose applyEdit', () => {
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.applyEdit).toBeUndefined();
    expect(ctxAny.edit).toBeUndefined();
    expect(ctxAny.mutate).toBeUndefined();
    expect(ctxAny.patch).toBeUndefined();
    expect(ctxAny.commit).toBeUndefined();
    expect(ctxAny.transact).toBeUndefined();
  });

  // ---- no timeline store ---------------------------------------------------

  it('does not expose timeline store', () => {
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.timelineStore).toBeUndefined();
    expect(ctxAny.timeline).toBeUndefined();
    expect(ctxAny.store).toBeUndefined();
    expect(ctxAny.getTimeline).toBeUndefined();
    expect(ctxAny.timelineRef).toBeUndefined();
  });

  // ---- no internal ops -----------------------------------------------------

  it('does not expose internal ops', () => {
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.ops).toBeUndefined();
    expect(ctxAny.internalOps).toBeUndefined();
    expect(ctxAny._internal).toBeUndefined();
    expect(ctxAny.__editorInternals).toBeUndefined();
    expect(ctxAny._editor).toBeUndefined();
  });

  // ---- no raw services beyond the approved set -----------------------------

  it('services has exactly 3 members (settings, i18n, diagnostics)', () => {
    const serviceKeys = Object.keys(ctx.services).sort();
    expect(serviceKeys).toEqual(['diagnostics', 'i18n', 'settings']);
  });

  it('services.settings has only the public API', () => {
    const settingKeys = Object.keys(ctx.services.settings).sort();
    // get, set, delete, keys — no internal props
    expect(settingKeys).toEqual(['delete', 'get', 'keys', 'set']);
  });

  it('services.i18n has only the public API', () => {
    const i18nKeys = Object.keys(ctx.services.i18n).sort();
    expect(i18nKeys).toEqual(['t']);
  });

  it('services.diagnostics has only the public API', () => {
    const diagKeys = Object.keys(ctx.services.diagnostics).sort();
    expect(diagKeys).toEqual(['diagnostics', 'report']);
  });

  // ---- chrome has only the approved API ------------------------------------

  it('chrome has exactly 5 methods (toast, progress, subscribe, focus, announce)', () => {
    const chromeKeys = Object.keys(ctx.chrome).sort();
    expect(chromeKeys).toEqual(['announce', 'focus', 'progress', 'subscribe', 'toast']);
  });

  // ---- creative stubs are present but no real internals --------------------

  it('creative has exactly 8 reserved stubs, all frozen', () => {
    const creativeKeys = Object.keys(ctx.creative).sort();
    expect(creativeKeys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'sessions',
      'stage',
      'timeline',
      'writing',
    ]);
    expect(Object.isFrozen(ctx.creative)).toBe(true);
  });

  // ---- extension metadata is readonly and doesn't leak internals -----------

  it('extension has exactly the approved metadata keys', () => {
    const extKeys = Object.keys(ctx.extension).sort();
    expect(extKeys).toEqual([
      'description',
      'id',
      'label',
      'manifest',
      'version',
    ]);
  });

  // ---- frozen / immutability -----------------------------------------------

  it('context is frozen', () => {
    expect(Object.isFrozen(ctx)).toBe(true);
  });

  it('extension metadata object is frozen', () => {
    expect(Object.isFrozen(ctx.extension)).toBe(true);
  });

  it('services object is frozen', () => {
    expect(Object.isFrozen(ctx.services)).toBe(true);
  });

  it('cannot add new properties to context', () => {
    expect(() => {
      (ctx as any).newProp = 'value';
    }).toThrow();
  });

  // ---- no Symbol-keyed internal escape hatches (other than dispose) --------

  it('has only the approved dispose Symbol (non-enumerable)', () => {
    const symbols = Object.getOwnPropertySymbols(ctx);
    // CONTEXT_DISPOSE_SYMBOL is the only symbol attached
    expect(symbols.length).toBeLessThanOrEqual(1);
    if (symbols.length === 1) {
      expect(symbols[0]).toBe(CONTEXT_DISPOSE_SYMBOL);
    }
  });

  // ---- no global / window pollution from context ---------------------------

  it('does not expose any window-scoped references', () => {
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.window).toBeUndefined();
    expect(ctxAny.global).toBeUndefined();
    expect(ctxAny.globalThis).toBeUndefined();
    expect(ctxAny.document).toBeUndefined();
  });

  // ---- disposeExtensionContextServices works and is safe -------------------

  it('disposeExtensionContextServices does not throw on a valid context', () => {
    expect(() => disposeExtensionContextServices(ctx)).not.toThrow();
  });

  it('disposeExtensionContextServices does not throw when called twice', () => {
    disposeExtensionContextServices(ctx);
    expect(() => disposeExtensionContextServices(ctx)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 4. Type-level assertion — ExtensionContext has no index signature for
//    arbitrary property access. This is a compile-time check; we verify at
//    runtime that direct property enumeration matches expectations.
// ---------------------------------------------------------------------------

describe('ExtensionContext — type safety guard', () => {
  it('ExtensionContext own keys match the interface declaration', () => {
    // If the ExtensionContext interface had an index signature like
    // [key: string]: unknown, all string keys would be "allowed" by TS.
    // The runtime check below guards that only declared keys exist.
    const ext = defineExtension({
      manifest: {
        id: 'com.typesafety.test' as any,
        version: '1.0.0',
        label: 'Type Safety Test',
        contributions: [],
      },
    });
    const ctx = createExtensionContext(ext);

    const declaredKeys = [
      'apiVersion',
      'extension',
      'chrome',
      'services',
      'creative',
    ];

    const actualKeys = Object.keys(ctx).sort();
    expect(actualKeys.sort()).toEqual(declaredKeys.sort());

    // No extra keys present
    for (const key of actualKeys) {
      expect(declaredKeys).toContain(key);
    }
  });
});
