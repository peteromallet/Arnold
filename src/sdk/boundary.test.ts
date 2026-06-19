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
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
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
  // M6: Parser / output format / search provider
  ParserContribution,
  OutputFormatContribution,
  SearchProviderContribution,
  CompileOnlyOutputResult,
  ExportService,
  AssetReadSurface,
  MaterialReadSurface,
  MetadataFacetDescriptor,
  // M10: Agent tool contribution types
  AgentToolContribution,
  AgentToolInputSchema,
  AgentToolInputProperty,
  ToolResultFamily,
  ToolResult,
  ToolMutationProposalResult,
  ToolGenerationSessionResult,
  ToolMaterialArtifactResult,
  ToolEnrichmentSearchResult,
  ToolExportResult,
  ToolProcessResult,
  ToolUISummaryResult,
  ToolSourceRef,
  ToolArtifactRef,
  ToolSearchResultMatch,
  ToolResultDiagnostic,
  AgentToolInvocationRequest,
  AgentToolRequestContext,
  AgentToolExportContext,
  GenerationSession,
  AgentToolRegistrationService,
  AgentToolHandler,
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
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
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
      'agentTools',
      'apiVersion',
      'chrome',
      'clipTypes',
      'commands',
      'creative',
      'effects',
      'extension',
      'services',
      'transitions',
    ]);
  });

  it('has no extra enumerable properties', () => {
    const allowed = new Set([
      'agentTools',
      'apiVersion',
      'extension',
      'chrome',
      'services',
      'creative',
      'commands',
      'effects',
      'transitions',
      'clipTypes',
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
      'agentTools',
      'apiVersion',
      'extension',
      'chrome',
      'services',
      'creative',
      'commands',
      'effects',
      'transitions',
      'clipTypes',
    ];

    const actualKeys = Object.keys(ctx).sort();
    expect(actualKeys.sort()).toEqual(declaredKeys.sort());

    // No extra keys present
    for (const key of actualKeys) {
      expect(declaredKeys).toContain(key);
    }
  });
});

// ---------------------------------------------------------------------------
// M6: Contribution kind bridging — parser active, output/search typed
// ---------------------------------------------------------------------------

describe('M6: contribution kind bridging (parser M6-active, output/search typed)', () => {
  it('parser is M6-active (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('outputFormat is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
  });

  it('searchProvider is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('searchProvider')).toBe('M6');
  });

  it('render-dependent output declarations remain declarable but reserved for execution', () => {
    // outputFormat (both compile-only and render-dependent) is declarable
    // in manifests but its runtime execution is reserved in M6.
    const bridged = contributionKindNotYetBridged('outputFormat');
    expect(bridged).toBe('M6');

    // Contrast: parser IS bridged at M6
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('unsupported contribution behavior is explicit (returns owning milestone)', () => {
    // Every reserved/unsupported kind returns its milestone so consumers
    // get a clear diagnostic, not silent ignorance.
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('agentTool')).toBeNull();
    expect(contributionKindNotYetBridged('agent')).toBe('M10');
  });

  it('CONTRIBUTION_KIND_MILESTONE maps M6 kinds to M6', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.parser).toBe('M6');
    expect(CONTRIBUTION_KIND_MILESTONE.outputFormat).toBe('M6');
    expect(CONTRIBUTION_KIND_MILESTONE.searchProvider).toBe('M6');
  });

  it('existing bridged M1/M2/M4 kinds remain unchanged', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    expect(contributionKindNotYetBridged('panel')).toBeNull();
    expect(contributionKindNotYetBridged('inspectorSection')).toBeNull();
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('keybinding')).toBeNull();
    expect(contributionKindNotYetBridged('contextMenuItem')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M6: ExtensionManifest accepts M6 contributions in contributions array
// ---------------------------------------------------------------------------

describe('M6: ExtensionManifest contributions accept parser/outputFormat/searchProvider', () => {
  it('defineExtension accepts a manifest with a parser contribution', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.parser-test' as any,
        version: '1.0.0',
        label: 'M6 Parser Test',
        contributions: [
          {
            id: 'img-parser' as any,
            kind: 'parser',
            label: 'Image Metadata Parser',
            acceptMimeTypes: ['image/jpeg', 'image/png'],
            required: true,
          },
        ],
      },
    });
    expect(ext.manifest.id).toBe('com.m6.parser-test');
    expect(ext.manifest.contributions![0].kind).toBe('parser');
  });

  it('defineExtension accepts a manifest with an outputFormat contribution (compile-only)', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.output-test' as any,
        version: '1.0.0',
        label: 'M6 Output Test',
        contributions: [
          {
            id: 'metadata-json' as any,
            kind: 'outputFormat',
            label: 'Metadata JSON',
            requiresRender: false,
            outputExtension: 'json',
            outputMimeType: 'application/json',
          },
        ],
      },
    });
    expect(ext.manifest.id).toBe('com.m6.output-test');
    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
  });

  it('defineExtension accepts a manifest with an outputFormat contribution (render-dependent, reserved)', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.output-reserved' as any,
        version: '1.0.0',
        label: 'M6 Reserved Output',
        contributions: [
          {
            id: 'mp4-export' as any,
            kind: 'outputFormat',
            label: 'MP4 Export',
            requiresRender: true,
            outputExtension: 'mp4',
            outputMimeType: 'video/mp4',
          },
        ],
      },
    });
    expect(ext.manifest.id).toBe('com.m6.output-reserved');
    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
    expect((ext.manifest.contributions![0] as any).requiresRender).toBe(true);
  });

  it('defineExtension accepts a manifest with a searchProvider contribution', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.search-test' as any,
        version: '1.0.0',
        label: 'M6 Search Test',
        contributions: [
          {
            id: 'semantic-search' as any,
            kind: 'searchProvider',
            label: 'Semantic Search',
            description: 'Semantic asset search',
            resultKinds: ['asset'],
          },
        ],
      },
    });
    expect(ext.manifest.id).toBe('com.m6.search-test');
    expect(ext.manifest.contributions![0].kind).toBe('searchProvider');
  });

  it('defineExtension rejects duplicate contribution IDs across M6 kinds', () => {
    expect(() =>
      defineExtension({
        manifest: {
          id: 'com.m6.dup' as any,
          version: '1.0.0',
          label: 'M6 Duplicate Test',
          contributions: [
            {
              id: 'dup-id' as any,
              kind: 'parser',
              label: 'Parser',
              acceptMimeTypes: ['image/jpeg'],
            },
            {
              id: 'dup-id' as any,
              kind: 'outputFormat',
              label: 'Output',
              requiresRender: false,
              outputExtension: 'json',
            },
          ],
        },
      }),
    ).toThrow(/Duplicate contribution ID/);
  });
});

// ---------------------------------------------------------------------------
// M10: Agent tool contributions — manifest typing, boundary, and governance
// ---------------------------------------------------------------------------

describe('M10: AgentToolContribution manifest acceptance', () => {
  it('defineExtension accepts a manifest with an agentTool contribution', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m10.agent-tool-test' as any,
        version: '1.0.0',
        label: 'M10 Agent Tool Test',
        contributions: [
          {
            id: 'my-agent-tool' as any,
            kind: 'agentTool' as const,
            toolId: 'com.m10.agent-tool-test.myTool',
            label: 'My Agent Tool',
            description: 'A host-mediated agent tool',
          },
        ],
      },
    });
    expect(ext.manifest.id).toBe('com.m10.agent-tool-test');
    expect(ext.manifest.contributions![0].kind).toBe('agentTool');
  });

  it('AgentToolContribution has required toolId and label fields', () => {
    const contribution: AgentToolContribution = {
      id: 'tool-1' as any,
      kind: 'agentTool',
      toolId: 'com.example.myTool',
      label: 'Example Tool',
    };
    expect(contribution.kind).toBe('agentTool');
    expect(contribution.toolId).toBe('com.example.myTool');
    expect(contribution.label).toBe('Example Tool');
  });

  it('AgentToolContribution accepts optional inputSchema', () => {
    const schema: AgentToolInputSchema = {
      type: 'object',
      properties: {
        prompt: {
          type: 'string',
          title: 'Prompt',
          description: 'The generation prompt',
        },
        temperature: {
          type: 'number',
          title: 'Temperature',
          default: 0.7,
        },
      },
      required: ['prompt'],
    };

    const contribution: AgentToolContribution = {
      id: 'tool-2' as any,
      kind: 'agentTool',
      toolId: 'com.example.genTool',
      label: 'Generation Tool',
      description: 'Generates content from a prompt',
      inputSchema: schema,
      resultFamilies: ['generation/session', 'ui/summary'],
      order: 10,
      when: 'ctx.creative.timeline != null',
    };

    expect(contribution.inputSchema?.type).toBe('object');
    expect(contribution.inputSchema?.required).toEqual(['prompt']);
    expect(contribution.resultFamilies).toEqual(['generation/session', 'ui/summary']);
    expect(contribution.order).toBe(10);
    expect(contribution.when).toBe('ctx.creative.timeline != null');
  });

  it('AgentToolInputProperty supports string, number, boolean, and nested object types', () => {
    const strProp: AgentToolInputProperty = { type: 'string', title: 'Name' };
    const numProp: AgentToolInputProperty = { type: 'number', default: 42 };
    const boolProp: AgentToolInputProperty = { type: 'boolean', default: true };
    const enumProp: AgentToolInputProperty = {
      type: 'string',
      title: 'Format',
      enum: ['json', 'xml', 'yaml'],
    };
    const nestedProp: AgentToolInputProperty = {
      type: 'object',
      properties: {
        x: { type: 'number' },
        y: { type: 'number' },
      },
      required: ['x', 'y'],
    };

    expect(strProp.type).toBe('string');
    expect(numProp.type).toBe('number');
    expect(boolProp.type).toBe('boolean');
    expect(enumProp.enum).toEqual(['json', 'xml', 'yaml']);
    expect(nestedProp.properties?.x.type).toBe('number');
    expect(nestedProp.required).toEqual(['x', 'y']);
  });

  it('defineExtension rejects duplicate contribution IDs with agentTool', () => {
    expect(() =>
      defineExtension({
        manifest: {
          id: 'com.m10.dup-agent' as any,
          version: '1.0.0',
          label: 'M10 Duplicate Test',
          contributions: [
            {
              id: 'dup-tool-id' as any,
              kind: 'agentTool',
              toolId: 'com.m10.dup-agent.toolA',
              label: 'Tool A',
            },
            {
              id: 'dup-tool-id' as any,
              kind: 'agentTool',
              toolId: 'com.m10.dup-agent.toolB',
              label: 'Tool B',
            },
          ],
        },
      }),
    ).toThrow(/Duplicate contribution ID/);
  });
});

// ---------------------------------------------------------------------------
// M10: ToolResult families and grouped union
// ---------------------------------------------------------------------------

describe('M10: ToolResult union — grouped families', () => {
  it('ToolResultFamily covers all 7 stable families', () => {
    const families: ToolResultFamily[] = [
      'mutation/proposal',
      'generation/session',
      'material/artifact',
      'enrichment/search',
      'export',
      'process',
      'ui/summary',
    ];
    expect(families).toHaveLength(7);
  });

  it('ToolMutationProposalResult has family mutation/proposal with patches', () => {
    const result: ToolMutationProposalResult = {
      family: 'mutation/proposal',
      rationale: 'Re-align clip to beat grid',
      patches: [],
      affectedObjectIds: ['clip-1', 'clip-2'],
      sourceRefs: [
        { sourceId: 'clip-1', outputId: 'clip-1-modified', description: 'Beat-aligned' },
      ],
      diagnostics: [
        { severity: 'info', code: 'agent-tool/beat-grid-applied', message: 'Beat grid applied' },
      ],
    };
    expect(result.family).toBe('mutation/proposal');
    expect(result.rationale).toBeDefined();
    expect(Array.isArray(result.patches)).toBe(true);
    expect(result.affectedObjectIds).toEqual(['clip-1', 'clip-2']);
    expect(result.sourceRefs![0].sourceId).toBe('clip-1');
    expect(result.diagnostics![0].code).toBe('agent-tool/beat-grid-applied');
  });

  it('ToolGenerationSessionResult has family generation/session with session handle', () => {
    const session: GenerationSession = {
      id: 'session-1',
      progress: 50,
      progressLabel: 'Generating...',
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress() {
        return { dispose() {} };
      },
      cancel() {},
      getSampleChannel() {
        return 'channel-1';
      },
      complete() {},
    };
    const result: ToolGenerationSessionResult = {
      family: 'generation/session',
      session,
      rationale: 'Generating B-roll suggestions',
    };
    expect(result.family).toBe('generation/session');
    expect(result.session.id).toBe('session-1');
    expect(result.session.progress).toBe(50);
    expect(result.session.cancelled).toBe(false);
  });

  it('ToolMaterialArtifactResult has family material/artifact with refs', () => {
    const ref: ToolArtifactRef = {
      ref: 'asset-key-1',
      kind: 'asset',
      label: 'Generated image',
      meta: { width: 1920, height: 1080 },
    };
    const result: ToolMaterialArtifactResult = {
      family: 'material/artifact',
      refs: [ref],
      rationale: 'Generated storyboard images',
    };
    expect(result.family).toBe('material/artifact');
    expect(result.refs).toHaveLength(1);
    expect(result.refs[0].kind).toBe('asset');
    expect(result.refs[0].meta?.width).toBe(1920);
  });

  it('ToolEnrichmentSearchResult has family enrichment/search with suggestions and matches', () => {
    const match: ToolSearchResultMatch = {
      key: 'asset-1',
      score: 0.95,
      label: 'Mountain sunset',
    };
    const result: ToolEnrichmentSearchResult = {
      family: 'enrichment/search',
      suggestions: { 'asset-1': { tags: ['sunset', 'mountain'] } },
      matches: [match],
      rationale: 'Semantic search over asset metadata',
    };
    expect(result.family).toBe('enrichment/search');
    expect(result.matches![0].score).toBe(0.95);
    expect(result.suggestions!['asset-1'].tags).toEqual(['sunset', 'mountain']);
  });

  it('ToolExportResult has family export with planner-compatible findings', () => {
    const result: ToolExportResult = {
      family: 'export',
      findings: [{ findingType: 'missing-font', severity: 'warning' }],
      rationale: 'Pre-export compatibility check',
    };
    expect(result.family).toBe('export');
    expect(result.findings).toHaveLength(1);
  });

  it('ToolProcessResult has family process with pending diagnostic', () => {
    const result: ToolProcessResult = {
      family: 'process',
      diagnostics: [
        {
          severity: 'info',
          code: 'agent-tool/process-not-available',
          message: 'Process execution not available until M12.',
        },
      ],
    };
    expect(result.family).toBe('process');
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('agent-tool/process-not-available');
  });

  it('ToolUISummaryResult has family ui/summary with summary text', () => {
    const result: ToolUISummaryResult = {
      family: 'ui/summary',
      summary: 'The timeline has 3 clips with a total duration of 45 seconds.',
      detail: { clipCount: 3, totalDuration: 45 },
    };
    expect(result.family).toBe('ui/summary');
    expect(result.summary).toContain('45 seconds');
    expect(result.detail?.clipCount).toBe(3);
  });

  it('ToolResult union discriminates all 7 families', () => {
    const results: ToolResult[] = [
      { family: 'mutation/proposal', patches: [] },
      { family: 'generation/session', session: { id: 's', progress: 0, cancelled: false, done: false, diagnostics: [], onProgress() { return { dispose() {} }; }, cancel() {}, getSampleChannel() { return ''; }, complete() {} } },
      { family: 'material/artifact', refs: [] },
      { family: 'enrichment/search' },
      { family: 'export' },
      { family: 'process', diagnostics: [{ severity: 'info', code: 'agent-tool/test', message: 'test' }] },
      { family: 'ui/summary', summary: 'test' },
    ];
    expect(results).toHaveLength(7);
    for (const r of results) {
      expect(r.family).toBeDefined();
    }
  });

  it('ToolResultDiagnostic requires agent-tool/ code prefix', () => {
    const diag: ToolResultDiagnostic = {
      severity: 'error',
      code: 'agent-tool/validation-failed',
      message: 'Input validation failed',
      detail: { field: 'prompt', reason: 'required' },
    };
    expect(diag.code).toMatch(/^agent-tool\//);
    expect(diag.severity).toBe('error');
    expect(diag.detail?.field).toBe('prompt');
  });

  it('ToolSourceRef maps source to output with description', () => {
    const ref: ToolSourceRef = {
      sourceId: 'clip-a',
      outputId: 'clip-a-optimized',
      description: 'Optimized clip timing',
    };
    expect(ref.sourceId).toBe('clip-a');
    expect(ref.outputId).toBe('clip-a-optimized');
  });

  it('ToolArtifactRef supports asset, material, and placeholder kinds', () => {
    const assetRef: ToolArtifactRef = { ref: 'key-1', kind: 'asset', label: 'Asset' };
    const materialRef: ToolArtifactRef = { ref: 'key-2', kind: 'material', label: 'Material' };
    const placeholderRef: ToolArtifactRef = { ref: 'key-3', kind: 'placeholder', label: 'Placeholder' };

    expect(assetRef.kind).toBe('asset');
    expect(materialRef.kind).toBe('material');
    expect(placeholderRef.kind).toBe('placeholder');
  });
});

// ---------------------------------------------------------------------------
// M10: AgentToolInvocationRequest, context, and export context
// ---------------------------------------------------------------------------

describe('M10: AgentToolInvocationRequest and context contracts', () => {
  it('AgentToolInvocationRequest carries toolId, extensionId, contributionId, and optional input', () => {
    const request: AgentToolInvocationRequest = {
      toolId: 'com.example.myTool',
      extensionId: 'com.example',
      contributionId: 'my-tool-contribution',
      input: { prompt: 'Generate a title card' },
    };
    expect(request.toolId).toBe('com.example.myTool');
    expect(request.extensionId).toBe('com.example');
    expect(request.contributionId).toBe('my-tool-contribution');
    expect(request.input?.prompt).toBe('Generate a title card');
  });

  it('AgentToolRequestContext carries timeline, assets, materials, export, and meta', () => {
    const ctx: AgentToolRequestContext = {
      timeline: { clips: [], tracks: [] } as any,
      assets: [{ key: 'asset-1', metadata: { duration: 10 } }],
      materials: [{ key: 'mat-1', metadata: { type: 'video' } }],
      export: {
        outputFormatId: 'metadata-json',
        blockers: [],
        contributionIds: ['contrib-1'],
      },
      meta: { requestKind: 'analysis' },
    };
    expect(ctx.assets).toHaveLength(1);
    expect(ctx.assets![0].key).toBe('asset-1');
    expect(ctx.export?.outputFormatId).toBe('metadata-json');
    expect(ctx.meta?.requestKind).toBe('analysis');
  });

  it('AgentToolExportContext carries format, blockers, and contribution IDs', () => {
    const exportCtx: AgentToolExportContext = {
      outputFormatId: 'mp4-export',
      blockers: [{ reason: 'missing-font' }],
      contributionIds: ['effect-1', 'transition-1'],
    };
    expect(exportCtx.outputFormatId).toBe('mp4-export');
    expect(exportCtx.blockers).toHaveLength(1);
    expect(exportCtx.contributionIds).toEqual(['effect-1', 'transition-1']);
  });

  it('AgentToolRequestContext.export is optional', () => {
    const ctx: AgentToolRequestContext = {
      assets: [{ key: 'a' }],
    };
    expect(ctx.export).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// M10: GenerationSession contract
// ---------------------------------------------------------------------------

describe('M10: GenerationSession contract', () => {
  function makeSession(overrides?: Partial<GenerationSession>): GenerationSession {
    return {
      id: 'gen-session-1',
      progress: 0,
      progressLabel: 'Starting...',
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress(_listener: (progress: number, label?: string) => void) {
        return { dispose() {} };
      },
      cancel() {},
      getSampleChannel() {
        return 'preview-channel-1';
      },
      complete(_result?: Record<string, unknown>) {},
      ...overrides,
    };
  }

  it('exposes readonly id, progress, cancelled, done, and diagnostics', () => {
    const session = makeSession();
    expect(session.id).toBe('gen-session-1');
    expect(session.progress).toBe(0);
    expect(session.cancelled).toBe(false);
    expect(session.done).toBe(false);
    expect(Array.isArray(session.diagnostics)).toBe(true);
  });

  it('onProgress returns a DisposeHandle', () => {
    const session = makeSession();
    const calls: number[] = [];
    const handle = session.onProgress((p) => calls.push(p));
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });

  it('cancel() is idempotent (safe to call multiple times)', () => {
    const session = makeSession();
    expect(() => {
      session.cancel();
      session.cancel();
      session.cancel();
    }).not.toThrow();
  });

  it('getSampleChannel returns a non-empty string', () => {
    const session = makeSession();
    const channel = session.getSampleChannel();
    expect(typeof channel).toBe('string');
    expect(channel.length).toBeGreaterThan(0);
  });

  it('complete() is safe to call once (subsequent calls ignored)', () => {
    const session = makeSession();
    expect(() => {
      session.complete({ output: 'result' });
      session.complete({ output: 'ignored' });
    }).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// M10: ExtensionContext.agentTools registration boundary
// ---------------------------------------------------------------------------

describe('M10: ExtensionContext.agentTools registration boundary', () => {
  function makeCtx(): ExtensionContext {
    const ext = defineExtension({
      manifest: {
        id: 'com.m10.boundary' as any,
        version: '1.0.0',
        label: 'M10 Boundary Test Extension',
        contributions: [],
      },
    });
    return createExtensionContext(ext);
  }

  it('ExtensionContext has agentTools property', () => {
    const ctx = makeCtx();
    expect(ctx.agentTools).toBeDefined();
    expect(typeof ctx.agentTools.registerTool).toBe('function');
    expect(typeof ctx.agentTools.invokeProcess).toBe('function');
  });

  it('agentTools.registerTool returns a DisposeHandle', () => {
    const ctx = makeCtx();
    const handler: AgentToolHandler = (_req) => ({
      family: 'ui/summary',
      summary: 'ok',
    });
    const handle = ctx.agentTools.registerTool('com.example.tool', handler);
    expect(typeof handle.dispose).toBe('function');
    // Safe to call multiple times
    handle.dispose();
    handle.dispose();
  });

  it('agentTools.registerTool emits not-wired diagnostic when provider absent', () => {
    const ctx = makeCtx();
    const handler: AgentToolHandler = (_req) => ({
      family: 'ui/summary',
      summary: 'ok',
    });
    ctx.agentTools.registerTool('com.example.unwired', handler);
    const diagnostics = ctx.services.diagnostics.diagnostics;
    const notWiredDiag = diagnostics.find((d) => d.code === 'agentTools/not-wired');
    expect(notWiredDiag).toBeDefined();
    expect(notWiredDiag!.severity).toBe('error');
  });

  it('agentTools.invokeProcess returns ToolProcessResult with pending diagnostic', async () => {
    const ctx = makeCtx();
    const result = await ctx.agentTools.invokeProcess('com.example.tool', {
      command: 'echo',
      args: ['hello'],
    });
    expect(result.family).toBe('process');
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('agent-tool/process-not-available');
    expect(result.diagnostics[0].severity).toBe('info');
  });

  it('agentTools has exactly 2 methods (registerTool, invokeProcess)', () => {
    const ctx = makeCtx();
    const keys = Object.keys(ctx.agentTools).sort();
    expect(keys).toEqual(['invokeProcess', 'registerTool']);
  });

  it('createExtensionContext accepts optional agentTools parameter for provider wiring', () => {
    const wiredService: AgentToolRegistrationService = {
      registerTool(_toolId: string, _handler: AgentToolHandler) {
        return { dispose() {} };
      },
      async invokeProcess(_toolId: string, _config: any) {
        return {
          family: 'process' as const,
          diagnostics: [{
            severity: 'info' as const,
            code: 'agent-tool/wired' as const,
            message: 'Wired process call.',
          }],
        };
      },
    };

    const ext = defineExtension({
      manifest: {
        id: 'com.m10.wired' as any,
        version: '1.0.0',
        label: 'Wired Test',
        contributions: [],
      },
    });
    const ctx = createExtensionContext(
      ext,
      undefined, // creativeOverrides
      undefined, // commands
      undefined, // effects
      undefined, // transitions
      undefined, // clipTypes
      wiredService, // agentTools
    );
    expect(ctx.agentTools).toBe(wiredService);

    // Wired service does NOT emit not-wired diagnostic
    const diagnostics = ctx.services.diagnostics.diagnostics;
    const notWiredDiag = diagnostics.find((d) => d.code === 'agentTools/not-wired');
    expect(notWiredDiag).toBeUndefined();
  });

  it('agentTools context property is frozen (same as other context members)', () => {
    const ctx = makeCtx();
    expect(Object.isFrozen(ctx)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// M10: Contribution kind milestone metadata for agent tools
// ---------------------------------------------------------------------------

describe('M10: Contribution kind bridging — agentTool active, agent reserved', () => {
  it('agentTool is M10-active (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('agentTool')).toBeNull();
  });

  it('agent remains reserved (returns M10)', () => {
    expect(contributionKindNotYetBridged('agent')).toBe('M10');
  });

  it('CONTRIBUTION_KIND_MILESTONE maps agentTool correctly', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.agentTool).toBeDefined();
    expect(CONTRIBUTION_KIND_MILESTONE.agent).toBe('M10');
  });

  it('all other bridged kinds remain unchanged after M10 activation', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    expect(contributionKindNotYetBridged('panel')).toBeNull();
    expect(contributionKindNotYetBridged('command')).toBeNull();
    expect(contributionKindNotYetBridged('keybinding')).toBeNull();
    expect(contributionKindNotYetBridged('contextMenuItem')).toBeNull();
    expect(contributionKindNotYetBridged('effect')).toBeNull();
    expect(contributionKindNotYetBridged('transition')).toBeNull();
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M10: Governance — no video-editor internal imports for agent tool types
// ---------------------------------------------------------------------------

describe('M10: Agent tool governance — no internal video-editor imports', () => {
  it('AgentToolContribution is importable from @reigh/editor-sdk (public SDK only)', () => {
    // Type-only check: AgentToolContribution resolves from the public SDK
    const ext = defineExtension({
      manifest: {
        id: 'com.m10.gov' as any,
        version: '1.0.0',
        label: 'Governance Test',
        contributions: [
          {
            id: 'gov-tool' as any,
            kind: 'agentTool' as const,
            toolId: 'com.m10.gov.govTool',
            label: 'Governance Tool',
            description: 'Tool for governance testing',
            resultFamilies: ['ui/summary'],
          } satisfies AgentToolContribution,
        ],
      },
    });
    expect(ext.manifest.contributions).toHaveLength(1);
    const contrib = ext.manifest.contributions![0] as AgentToolContribution;
    expect(contrib.kind).toBe('agentTool');
    expect(contrib.toolId).toBe('com.m10.gov.govTool');
    expect(contrib.resultFamilies).toEqual(['ui/summary']);
  });

  it('AgentToolHandler and ToolResult are typed exclusively through public SDK', () => {
    // Compile-time proof: handler returns a ToolResult via public types only
    const handler: AgentToolHandler = (request: AgentToolInvocationRequest): ToolResult => {
      if (request.input?.kind === 'summary') {
        return {
          family: 'ui/summary',
          summary: `Tool ${request.toolId} completed.`,
        };
      }
      return {
        family: 'process',
        diagnostics: [{
          severity: 'info',
          code: 'agent-tool/unsupported-input',
          message: 'Unsupported input kind.',
        }],
      };
    };
    const result = handler({
      toolId: 'com.test.tool',
      extensionId: 'com.test',
      contributionId: 'test-contrib',
    });
    expect(result.family).toBe('process');
    expect((result as ToolProcessResult).diagnostics[0].code).toBe('agent-tool/unsupported-input');
  });

  it('ExtensionManifest contributions array accepts AgentToolContribution in the union', () => {
    const manifest: ExtensionManifest = {
      id: 'com.m10.union' as any,
      version: '1.0.0',
      label: 'Union Test',
      contributions: [
        {
          id: 'slot-1' as any,
          kind: 'slot',
          slot: 'toolbar',
        },
        {
          id: 'tool-1' as any,
          kind: 'agentTool',
          toolId: 'com.m10.union.tool1',
          label: 'Union Tool',
        },
      ],
    };
    expect(manifest.contributions).toHaveLength(2);
    expect(manifest.contributions![0].kind).toBe('slot');
    expect(manifest.contributions![1].kind).toBe('agentTool');
  });
});
