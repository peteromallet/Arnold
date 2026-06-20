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
import * as sdkStar from '@/sdk/index';
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
  CompileOnlyOutputFormatContribution,
  RenderDependentOutputFormatContribution,
  RenderArtifactManifest,
  RenderArtifactSidecarDescriptor,
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
  SteeringParameterHotness,
  SteeringPriorSamplePolicy,
  SteeringProvenance,
  SteeringParameterChange,
  SteeringLineage,
  SteeringDecision,
  GenerationSessionLiveDelivery,
  LiveChannelDescriptor,
  // M12 planner requirement types
  CapabilityVersion,
  CapabilitySourceRef,
  RouteFitMetadata,
  CapabilityRequirement,
  IntegrationCapabilities,
  SamplingConfig,
  SamplingResult,
  TimelineRenderPassSummary,
  ProcessSpec,
  ProcessContribution,
  ProcessStatus,
  ProcessRoundtripRequest,
  ProcessRoundtripResult,
  ShaderContribution,
  ShaderInlineSource,
  ShaderRegistrationService,
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
    if (normalizedSep.startsWith('src/tools/video-editor/examples/extensions/flagship-local/')) {
      return false;
    }
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
      if (candidateRel.startsWith('src/tools/video-editor/examples/extensions/flagship-local/')) {
        return false;
      }
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
      const isTsxFile = filePath.endsWith('.tsx');

      it('imports exclusively from @reigh/editor-sdk (no video-editor internals)', () => {
        for (const specifier of specifiers) {
          expect(isVideoEditorInternal(relativePath, specifier)).toBe(false);
        }
      });

      it('imports from @reigh/editor-sdk', () => {
        if (isTsxFile) return;

        const hasSdkImport = specifiers.some(
          (s) => s === '@reigh/editor-sdk',
        );
        expect(hasSdkImport).toBe(true);
      });

      it('has no bare-specifier imports other than @reigh/editor-sdk', () => {
        const allowedBareSpecifiers = isTsxFile
          ? new Set(['@reigh/editor-sdk', 'react', 'remotion'])
          : new Set(['@reigh/editor-sdk']);

        for (const specifier of specifiers) {
          if (!specifier.startsWith('.') && !specifier.startsWith('@/')) {
            expect(allowedBareSpecifiers.has(specifier)).toBe(true);
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
      'shaders',
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
      'shaders',
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

  it('creative has exactly 10 reserved stubs, all frozen', () => {
    const creativeKeys = Object.keys(ctx.creative).sort();
    expect(creativeKeys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'proposals',
      'reader',
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
      'shaders',
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
    expect(contributionKindNotYetBridged('agent')).toBeNull();
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

describe('M10: Contribution kind bridging — agentTool and agent active', () => {
  it('agentTool is M10-active (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('agentTool')).toBeNull();
  });

  it('agent is M10-active (contributionKindNotYetBridged returns null)', () => {
    expect(contributionKindNotYetBridged('agent')).toBeNull();
  });

  it('CONTRIBUTION_KIND_MILESTONE maps agentTool correctly', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.agentTool).toBe('M10');
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
    expect(contributionKindNotYetBridged('shader')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M13: Dedicated shader contribution and registration boundary
// ---------------------------------------------------------------------------

describe('M13: shader contributions stay separate from component effects', () => {
  const shaderSource: ShaderInlineSource = {
    kind: 'inline',
    fragment: 'void main() { gl_FragColor = vec4(1.0); }',
  };

  const shaderContribution: ShaderContribution = {
    id: 'postprocess-grade' as any,
    kind: 'shader',
    shaderId: 'shader.postprocessGrade',
    label: 'Postprocess Grade',
    pass: 'postprocess',
    source: shaderSource,
    uniforms: [
      { name: 'u_time', label: 'Time', type: 'time', default: 0 },
      {
        name: 'u_mode',
        label: 'Mode',
        type: 'enum',
        default: 'warm',
        options: [
          { label: 'Warm', value: 'warm' },
          { label: 'Cool', value: 'cool' },
        ],
      },
    ],
    textures: [
      {
        name: 'compositedFrame',
        uniform: 'u_frame',
        sourceKind: 'clip-frame',
      },
    ],
    fallback: 'bypass',
  };

  it('normalizes kind: shader as bridged M13 metadata', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.shader).toBe('M13');
    expect(contributionKindNotYetBridged('shader')).toBeNull();
  });

  it('defineExtension preserves shader shape and does not create effect metadata', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m13.shader' as any,
        version: '1.0.0',
        label: 'M13 Shader Boundary',
        contributions: [shaderContribution],
      },
    });
    const contribution = ext.manifest.contributions![0] as ShaderContribution;
    expect(contribution.kind).toBe('shader');
    expect(contribution.shaderId).toBe('shader.postprocessGrade');
    expect((contribution as unknown as { effectId?: string }).effectId).toBeUndefined();
  });

  it('ctx.shaders registration does not call ctx.effects.registerComponent', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m13.shader-service' as any,
        version: '1.0.0',
        label: 'M13 Shader Service',
        contributions: [shaderContribution],
      },
    });
    const effectCalls: string[] = [];
    const shaderCalls: string[] = [];
    const shaderService: ShaderRegistrationService = {
      registerShader(shaderId, source) {
        shaderCalls.push(`${shaderId}:${source.kind}`);
        return { dispose() {} };
      },
    };

    const ctx = createExtensionContext(
      ext,
      undefined,
      undefined,
      {
        registerComponent(effectId) {
          effectCalls.push(effectId);
          return { dispose() {} };
        },
      },
      undefined,
      undefined,
      undefined,
      shaderService,
    );

    ctx.shaders.registerShader('shader.postprocessGrade', shaderSource);
    expect(shaderCalls).toEqual(['shader.postprocessGrade:inline']);
    expect(effectCalls).toEqual([]);
  });

  it('unwired shader registration emits only shader not-wired diagnostics', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m13.shader-unwired' as any,
        version: '1.0.0',
        label: 'M13 Shader Unwired',
        contributions: [shaderContribution],
      },
    });
    const ctx = createExtensionContext(ext);

    ctx.shaders.registerShader('shader.postprocessGrade', shaderSource);

    const codes = ctx.services.diagnostics.diagnostics.map((diagnostic) => diagnostic.code);
    expect(codes).toContain('shaders/not-wired');
    expect(codes).not.toContain('effects/not-wired');
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

// ---------------------------------------------------------------------------
// M11: Live Data Bridge — boundary tests
// ---------------------------------------------------------------------------

describe('M11: live-data type interfaces are importable from @reigh/editor-sdk', () => {
  it('LiveSourceKind sealed union covers all 10 documented values', () => {
    const kinds: LiveSourceKind[] = [
      'webcam', 'microphone', 'midi', 'serial', 'bluetooth',
      'generated', 'screen-capture', 'audio-device', 'osc', 'custom',
    ];
    expect(kinds).toHaveLength(10);
    // Verify each value is a valid LiveSourceKind
    for (const k of kinds) {
      const typed: LiveSourceKind = k;
      expect(typeof typed).toBe('string');
    }
  });

  it('LiveSource is constructable and sealed', () => {
    const src: LiveSource = {
      id: 'boundary-src-1',
      kind: 'webcam',
      status: 'active',
      diagnostics: [{ severity: 'info', code: 'live/ok', message: 'Running' }],
      label: 'Boundary Test Source',
      permission: { state: 'granted', reason: 'Boundary test' },
      recording: { active: true, mode: 'stream' },
      learnMode: 'idle',
    };
    expect(src.id).toBe('boundary-src-1');
    expect(src.kind).toBe('webcam');
    expect(src.status).toBe('active');
    expect(src.permission?.state).toBe('granted');
    expect(src.recording?.active).toBe(true);
    expect(src.learnMode).toBe('idle');
  });

  it('LiveChannelDescriptor is string-compatible across boundary', () => {
    // Branded string type must remain string-compatible
    const ch: LiveChannelDescriptor = 'boundary-channel' as LiveChannelDescriptor;
    expect(typeof ch).toBe('string');
    expect(ch.length).toBeGreaterThan(0);
    // String methods work
    expect(ch.toUpperCase()).toBe('BOUNDARY-CHANNEL');
    // Can be used in string interpolation
    expect(`channel: ${ch}`).toBe('channel: boundary-channel');
    // Can be assigned to string variable
    const plain: string = ch;
    expect(plain).toBe('boundary-channel');
  });

  it('LiveSampleFrame covers all data formats', () => {
    const rawFrame: LiveSampleFrame = {
      timestamp: 0, data: new Uint8Array([1, 2, 3]), format: 'raw',
    };
    const jsonFrame: LiveSampleFrame = {
      timestamp: 1, data: { key: 'value' }, format: 'json',
    };
    const binFrame: LiveSampleFrame = {
      timestamp: 2, data: new ArrayBuffer(8), format: 'binary',
    };
    const encFrame: LiveSampleFrame = {
      timestamp: 3, data: new Uint8Array([4, 5, 6]), format: 'encoded',
    };
    expect(rawFrame.format).toBe('raw');
    expect(jsonFrame.format).toBe('json');
    expect(binFrame.format).toBe('binary');
    expect(encFrame.format).toBe('encoded');
  });

  it('LiveBakeSelection supports partial and full bake', () => {
    const full: LiveBakeSelection = {
      sourceId: 'src-1',
      targets: [{ kind: 'asset', ref: 'out-1' }],
    };
    expect(full.channelIds).toBeUndefined();
    expect(full.timeRange).toBeUndefined();

    const partial: LiveBakeSelection = {
      sourceId: 'src-1',
      channelIds: ['ch-video' as LiveChannelDescriptor],
      timeRange: [0, 5000],
      frameRange: [12, 48],
      sampleRange: [0, 150],
      takeId: 'take-7',
      targets: [
        { kind: 'keyframe', ref: 'param.x', params: { interpolation: 'linear' } },
        { kind: 'sidecar', ref: 'meta.json' },
      ],
    };
    expect(partial.channelIds).toHaveLength(1);
    expect(partial.frameRange).toEqual([12, 48]);
    expect(partial.takeId).toBe('take-7');
    expect(partial.targets).toHaveLength(2);
    expect(partial.targets[0].kind).toBe('keyframe');
    expect(partial.targets[1].kind).toBe('sidecar');
  });

  it('SteeringDecision covers supersede, fork, and reject', () => {
    const lineageBase: SteeringLineage = {
      generationIndex: 1,
      steerHash: 'hash',
      parentRefs: ['s0'],
      producerVersion: '1.0.0',
      provenance: { prompt: 'Prompt', model: 'model-a', seed: 1 },
    };

    const supersede: SteeringDecision = {
      kind: 'supersede',
      sessionId: 's1',
      lineage: lineageBase,
      replacementChannelId: 'ch-new' as LiveChannelDescriptor,
    };
    const fork: SteeringDecision = {
      kind: 'fork',
      sessionId: 's1',
      lineage: { ...lineageBase, generationIndex: 2 },
    };
    const reject: SteeringDecision = {
      kind: 'reject',
      sessionId: 's1',
      lineage: lineageBase,
      reason: 'Quality below threshold',
    };

    expect(supersede.kind).toBe('supersede');
    expect(fork.kind).toBe('fork');
    expect(reject.kind).toBe('reject');
    expect(supersede.replacementChannelId).toBeDefined();
    expect(fork.replacementChannelId).toBeUndefined();
    expect(reject.reason).toBe('Quality below threshold');
  });

  it('LiveBinding covers all resolution states', () => {
    const states: BindingResolutionStatus[] = [
      'resolved', 'unresolved', 'orphaned', 'disposed', 'missing',
    ];
    const bindings: LiveBinding[] = states.map((s, i) => ({
      bindingId: `bind-${i}`,
      sourceId: `src-${i}`,
      status: s,
      ...(s !== 'resolved' ? {
        diagnostic: {
          severity: 'warning' as const,
          code: `live/${s}`,
          message: `Binding is ${s}`,
        },
      } : {}),
    }));
    expect(bindings).toHaveLength(5);
    expect(bindings[0].status).toBe('resolved');
    expect(bindings[0].diagnostic).toBeUndefined();
    expect(bindings[4].status).toBe('missing');
    expect(bindings[4].diagnostic?.code).toBe('live/missing');
  });

  it('LiveBindingResolution resolves or diagnoses every state', () => {
    const resolved: LiveBindingResolution = {
      bindingId: 'b1',
      status: 'resolved',
      source: { id: 's1', kind: 'generated', status: 'active', diagnostics: [] },
      channel: { channelId: 'ch' as LiveChannelDescriptor, kind: 'video', sourceId: 's1' },
    };
    expect(resolved.status).toBe('resolved');
    expect(resolved.source).toBeDefined();
    expect(resolved.channel).toBeDefined();

    const missing: LiveBindingResolution = {
      bindingId: 'b2',
      status: 'missing',
      diagnostic: { severity: 'error', code: 'live/missing-source', message: 'Source not found' },
    };
    expect(missing.status).toBe('missing');
    expect(missing.source).toBeUndefined();
    expect(missing.diagnostic?.code).toBe('live/missing-source');
  });

  it('LiveBindingMetadata reports aggregate counts', () => {
    const meta: LiveBindingMetadata = {
      bindings: [
        { bindingId: 'b1', sourceId: 's1', status: 'resolved' },
        { bindingId: 'b2', sourceId: 's2', status: 'orphaned' },
        { bindingId: 'b3', sourceId: 's3', status: 'disposed' },
        { bindingId: 'b4', sourceId: 's4', status: 'unresolved' },
      ],
      unresolvedCount: 1,
      orphanedCount: 1,
      disposedCount: 1,
    };
    expect(meta.bindings).toHaveLength(4);
    expect(meta.unresolvedCount).toBe(1);
    expect(meta.orphanedCount).toBe(1);
    expect(meta.disposedCount).toBe(1);
  });

  it('LiveSessionsService has all required methods', () => {
    // Compile-time proof: the interface is complete
    const svc: LiveSessionsService = {
      registerSource: () => ({ dispose() {} }),
      getSource: () => undefined,
      listSources: () => [],
      openChannel: () => 'ch' as LiveChannelDescriptor,
      closeChannel: () => {},
      getChannelMetadata: () => undefined,
      pushSample: () => {},
      subscribeSamples: () => ({ dispose() {} }),
      bake: () => ({ sourceId: '', targets: [], diagnostics: [], success: true }),
      removeLiveBindings: () => {},
      resolveBinding: () => ({ bindingId: '', status: 'missing' }),
      getBindingMetadata: () => ({ bindings: [], unresolvedCount: 0, orphanedCount: 0, disposedCount: 0 }),
      applySteeringDecision: () => {},
      getDiagnostics: () => [],
    };
    expect(typeof svc.registerSource).toBe('function');
    expect(typeof svc.openChannel).toBe('function');
    expect(typeof svc.bake).toBe('function');
    expect(typeof svc.removeLiveBindings).toBe('function');
    expect(typeof svc.resolveBinding).toBe('function');
    expect(typeof svc.getBindingMetadata).toBe('function');
    expect(typeof svc.applySteeringDecision).toBe('function');
  });
});

describe('M11: GenerationSession typed channel boundary', () => {
  it('getSampleChannel returns LiveChannelDescriptor that is string-compatible', () => {
    const session: GenerationSession = {
      id: 'boundary-gen',
      progress: 100,
      cancelled: false,
      done: true,
      diagnostics: [],
      onProgress: () => ({ dispose() {} }),
      cancel: () => {},
      getSampleChannel: () => 'boundary-gen-ch' as LiveChannelDescriptor,
      onSample: () => ({ dispose() {} }),
      getSteeringLineage: () => undefined,
      complete: () => {},
    };
    const channel = session.getSampleChannel();
    // String compatibility
    expect(typeof channel).toBe('string');
    // Can be used as plain string
    const plain: string = channel;
    expect(plain).toBe('boundary-gen-ch');
  });

  it('onSample delivers typed LiveSample', () => {
    let delivered: LiveSample | undefined;
    const session: GenerationSession = {
      id: 'boundary-gen-2',
      progress: 50,
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress: () => ({ dispose() {} }),
      cancel: () => {},
      getSampleChannel: () => 'ch' as LiveChannelDescriptor,
      onSample: (listener) => {
        listener({
          channelId: 'ch' as LiveChannelDescriptor,
          frame: { timestamp: 100, data: new Uint8Array([9]), format: 'raw' },
          sequenceNumber: 7,
        });
        return { dispose() {} };
      },
      getSteeringLineage: () => ({
        generationIndex: 1,
        steerHash: 'abc',
        parentRefs: ['boundary-gen-1'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 7 },
      }),
      complete: () => {},
    };
    session.onSample((s) => { delivered = s; });
    expect(delivered).toBeDefined();
    expect(delivered!.sequenceNumber).toBe(7);
    expect(delivered!.frame.timestamp).toBe(100);
  });

  it('getSteeringLineage returns full lineage when steered', () => {
    const lineage: SteeringLineage = {
      generationIndex: 4,
      steerHash: 'steer-hash-4',
      parentRefs: ['gen-1', 'gen-2', 'gen-3'],
      producerVersion: '3.0.0-beta',
      provenance: { prompt: 'Prompt', model: 'model-a', seed: 4 },
      provenanceTags: ['forked', 'quality-approved'],
    };
    const session: GenerationSession = {
      id: 'boundary-gen-3',
      progress: 100,
      cancelled: false,
      done: true,
      diagnostics: [],
      onProgress: () => ({ dispose() {} }),
      cancel: () => {},
      getSampleChannel: () => 'ch' as LiveChannelDescriptor,
      onSample: () => ({ dispose() {} }),
      getSteeringLineage: () => lineage,
      complete: () => {},
    };
    const result = session.getSteeringLineage();
    expect(result).toBe(lineage);
    expect(result!.generationIndex).toBe(4);
    expect(result!.parentRefs).toHaveLength(3);
    expect(result!.provenanceTags).toContain('forked');
  });

  it('ToolGenerationSessionResult can carry explicit live delivery activation metadata', () => {
    const steeringDecision: SteeringDecision = {
      kind: 'supersede',
      sessionId: 'boundary-live',
      lineage: {
        generationIndex: 1,
        steerHash: 'hash-live',
        parentRefs: ['boundary-parent'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 1 },
      },
      replacementChannelId: 'boundary-live:replacement' as LiveChannelDescriptor,
    };
    const liveDelivery: GenerationSessionLiveDelivery = {
      origin: 'agent-tool',
      steeringDecision,
      activeChannels: ['boundary-live:frames' as LiveChannelDescriptor],
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
    };
    const result: ToolGenerationSessionResult = {
      family: 'generation/session',
      session: {
        id: 'boundary-live',
        progress: 25,
        cancelled: false,
        done: false,
        diagnostics: [],
        liveDelivery,
        onProgress: () => ({ dispose() {} }),
        cancel: () => {},
        getSampleChannel: () => 'boundary-live:frames' as LiveChannelDescriptor,
        onSample: () => ({ dispose() {} }),
        getSteeringLineage: () => steeringDecision.lineage,
        complete: () => {},
      },
      liveDelivery,
    };

    expect(result.liveDelivery?.steeringDecision.lineage.steerHash).toBe('hash-live');
    expect(result.session.liveDelivery?.activeChannels).toEqual(['boundary-live:frames']);
  });
});

describe('M11: CreativeContext sessions is typed as LiveSessionsService', () => {
  it('CreativeContext.sessions is no longer unknown — accepts LiveSessionsService', () => {
    // Type-level proof: we can assign a LiveSessionsService to CreativeContext.sessions
    const sessionsSvc: LiveSessionsService = {
      registerSource: () => ({ dispose() {} }),
      getSource: () => undefined,
      listSources: () => [],
      openChannel: () => 'ch' as LiveChannelDescriptor,
      closeChannel: () => {},
      getChannelMetadata: () => undefined,
      pushSample: () => {},
      subscribeSamples: () => ({ dispose() {} }),
      bake: () => ({ sourceId: '', targets: [], diagnostics: [], success: true }),
      removeLiveBindings: () => {},
      resolveBinding: () => ({ bindingId: '', status: 'missing' }),
      getBindingMetadata: () => ({ bindings: [], unresolvedCount: 0, orphanedCount: 0, disposedCount: 0 }),
      applySteeringDecision: () => {},
      getDiagnostics: () => [],
    };

    const ctx: CreativeContext = {
      project: {},
      timeline: {} as any,
      reader: {} as any,
      proposals: {} as any,
      assets: {} as any,
      materials: {} as any,
      sessions: sessionsSvc,
      export: {} as any,
      stage: {},
      writing: {},
    };
    expect(ctx.sessions).toBe(sessionsSvc);
    expect(typeof ctx.sessions.registerSource).toBe('function');
  });
});

describe('M11: internal live-data types are NOT re-exported from @reigh/editor-sdk', () => {
  const M11_INTERNAL_FORBIDDEN = [
    // Live data registry internals
    'liveRegistry',
    'LiveRegistry',
    'createLiveRegistry',
    'liveDataRegistry',
    // Ring buffer internals
    'ringBuffer',
    'RingBuffer',
    'createRingBuffer',
    'RingBufferConfig',
    'RingBufferState',
    // Binding scanner internals
    'bindingScanner',
    'BindingScanner',
    'createBindingScanner',
    'pureBindingScanner',
    'scanBindings',
    // Bake internals
    'bakeExecutor',
    'BakeExecutor',
    'executeBake',
    'bakePipeline',
    // Steering internals
    'steeringResolver',
    'SteeringResolver',
    'resolveSteering',
    // Source lifecycle internals
    'sourceManager',
    'SourceManager',
    'createSourceManager',
    'sourceLifecycle',
    // Channel internals
    'channelManager',
    'ChannelManager',
    'openLiveChannel',
    'closeLiveChannel',
    // Sample ring buffer internals
    'sampleRingBuffer',
    'SampleRingBuffer',
    // Export guard internals
    'liveExportGuard',
    'LiveExportGuard',
    'checkLiveExportBlockers',
    // Provider integration
    'liveProviderBridge',
    'LiveProviderBridge',
  ];

  it('none of the forbidden M11 internal names appear as SDK value exports', () => {
    const valueExports = Object.keys(sdkStar);
    for (const forbidden of M11_INTERNAL_FORBIDDEN) {
      expect(valueExports).not.toContain(forbidden);
    }
  });

  it('forbidden M11 internal names are not accessible on the SDK namespace', () => {
    const ns = sdkStar as Record<string, unknown>;
    for (const forbidden of M11_INTERNAL_FORBIDDEN) {
      expect(ns[forbidden]).toBeUndefined();
    }
  });
});
