import { describe, expect, it, beforeEach } from 'vitest';
import {
  defineExtension,
  validateExtensionId,
  validateContributionId,
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
  createExtensionContext,
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
  setEditorShellRoot,
  getEditorShellRoot,
} from '@/sdk/index';
import type {
  ReighExtension,
  ExtensionManifest,
  ExtensionContribution,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  ProcessManifestEntry,
  // M6 contribution types
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
  MetadataFacetValueKind,
  AssetDetailSectionDescriptor,
  // M11 live-data types
  LiveSourceKind,
  LiveSourceStatus,
  LiveSourceDiagnostic,
  LiveSource,
  LiveChannelKind,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSampleFormat,
  LiveSampleFrame,
  LiveSample,
  LivePermissionState,
  LiveSourcePermission,
  LiveRecordingMode,
  LiveRecordingState,
  LiveLearnMode,
  LiveBakeTargetKind,
  LiveBakeTarget,
  LiveBakeSelection,
  LiveBakeResult,
  SteeringDecisionKind,
  SteeringParameterHotness,
  SteeringPriorSamplePolicy,
  SteeringProvenance,
  SteeringParameterChange,
  SteeringLineage,
  SteeringDecision,
  GenerationSessionLiveDelivery,
  BindingResolutionStatus,
  LiveBinding,
  LiveBindingResolution,
  LiveBindingMetadata,
  LiveSessionsService,
  GenerationSession,
  CreativeContext,
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
  DeterminismStatus,
  RenderRoute,
  RenderBlockerReason,
  CapabilityFinding,
  ShaderContribution,
  ShaderInlineSource,
  ShaderRegistrationService,
} from '@/sdk/index';

// ---------------------------------------------------------------------------
// ID validation
// ---------------------------------------------------------------------------

describe('validateExtensionId', () => {
  it('accepts valid dot-separated IDs', () => {
    expect(validateExtensionId('com.example.my-ext')).toEqual([]);
    expect(validateExtensionId('myExtension')).toEqual([]);
    expect(validateExtensionId('a.b.c')).toEqual([]);
    expect(validateExtensionId('toolbar-extra')).toEqual([]);
    expect(validateExtensionId('my_ext_v2')).toEqual([]);
  });

  it('rejects empty strings', () => {
    const errors = validateExtensionId('');
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('non-empty');
  });

  it('rejects IDs starting with a digit', () => {
    const errors = validateExtensionId('1bad');
    expect(errors.length).toBeGreaterThan(0);
  });

  it('rejects IDs with spaces or special chars', () => {
    expect(validateExtensionId('bad id').length).toBeGreaterThan(0);
    expect(validateExtensionId('bad/id').length).toBeGreaterThan(0);
    expect(validateExtensionId('bad@id').length).toBeGreaterThan(0);
  });

  it('rejects IDs longer than 128 characters', () => {
    const long = 'a'.repeat(129);
    expect(validateExtensionId(long).length).toBeGreaterThan(0);
  });

  it('accepts exactly 128 characters', () => {
    const ok = 'a' + 'b'.repeat(127);
    expect(validateExtensionId(ok)).toEqual([]);
  });
});

describe('validateContributionId', () => {
  it('validates the same as extension IDs', () => {
    expect(validateContributionId('myToolbar')).toEqual([]);
    expect(validateContributionId('').length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// defineExtension — literal ID preservation and freezing
// ---------------------------------------------------------------------------

describe('defineExtension', () => {
  const validManifest: ExtensionManifest = {
    id: 'com.example.test' as any,
    version: '1.0.0',
    label: 'Test Extension',
    description: 'A test extension for SDK verification',
    apiVersion: 1,
    contributions: [
      {
        id: 'toolbar-main' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 10,
        label: 'Main toolbar widget',
      },
    ],
  };

  it('returns a frozen object', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(Object.isFrozen(ext)).toBe(true);
    expect(Object.isFrozen(ext.manifest)).toBe(true);
  });

  it('preserves literal extension ID', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.id).toBe('com.example.test');
  });

  it('preserves literal contribution IDs', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].id).toBe('toolbar-main');
  });

  it('preserves contribution order', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].order).toBe(10);
  });

  it('preserves contribution kind', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].kind).toBe('slot');
  });

  it('preserves slot name', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].slot).toBe('toolbar');
  });

  it('freezes contributions array', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(Object.isFrozen(ext.manifest.contributions!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.contributions![0])).toBe(true);
  });

  it('preserves activate function when provided', () => {
    const activate = () => {};
    const ext = defineExtension({ manifest: validManifest, activate });
    expect(ext.activate).toBe(activate);
  });

  it('throws on invalid extension ID', () => {
    expect(() =>
      defineExtension({
        manifest: { ...validManifest, id: '' as any },
      }),
    ).toThrow(/Invalid extension ID/);
  });

  it('throws on duplicate contribution IDs', () => {
    expect(() =>
      defineExtension({
        manifest: {
          ...validManifest,
          contributions: [
            { id: 'dup' as any, kind: 'slot' as const, slot: 'toolbar' as const },
            { id: 'dup' as any, kind: 'slot' as const, slot: 'statusBar' as const },
          ],
        },
      }),
    ).toThrow(/Duplicate contribution ID/);
  });

  it('throws on invalid contribution ID', () => {
    expect(() =>
      defineExtension({
        manifest: {
          ...validManifest,
          contributions: [
            { id: '' as any, kind: 'slot' as const, slot: 'toolbar' as const },
          ],
        },
      }),
    ).toThrow(/Invalid contribution ID/);
  });

  it('freezes nested arrays (permissions, processes, dependsOn) when provided', () => {
    const manifestWithAll: ExtensionManifest = {
      ...validManifest,
      permissions: [{ reason: 'testing', posture: { network: true } }],
      processes: [
        {
          id: 'proc1',
          label: 'Test process',
          spawn: { command: 'echo', args: ['hello'] },
          protocol: 'stdio-jsonrpc',
        },
      ],
      dependsOn: [{ extensionId: 'com.other.lib', versionRange: '^1.0.0' }],
    };
    const ext = defineExtension({ manifest: manifestWithAll });
    expect(Object.isFrozen(ext.manifest.permissions!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.permissions![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn![0])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

describe('contributionKindNotYetBridged', () => {
  it('returns null for M1-bridged kinds', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    expect(contributionKindNotYetBridged('panel')).toBeNull();
    expect(contributionKindNotYetBridged('inspectorSection')).toBeNull();
  });

  it('returns milestone name for not-yet-bridged kinds', () => {
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('parser')).toBeNull();
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
    expect(contributionKindNotYetBridged('searchProvider')).toBe('M6');
    expect(contributionKindNotYetBridged('agentTool')).toBeNull();
    expect(contributionKindNotYetBridged('agent')).toBeNull();
  });

  it('parser is M6-active (returns null)', () => {
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('outputFormat is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
  });

  it('searchProvider is typed but execution is reserved (returns M6)', () => {
    expect(contributionKindNotYetBridged('searchProvider')).toBe('M6');
  });

  it('render-dependent output declarations remain declarable but reserved for execution', () => {
    const bridged = contributionKindNotYetBridged('outputFormat');
    expect(bridged).toBe('M6');
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('unsupported contribution behavior is explicit (returns owning milestone)', () => {
    expect(contributionKindNotYetBridged('clipType')).toBeNull();
    expect(contributionKindNotYetBridged('shader')).toBeNull();
    expect(contributionKindNotYetBridged('agentTool')).toBeNull();
    expect(contributionKindNotYetBridged('agent')).toBeNull();
  });

  it('shader is M13-active as its own contribution kind', () => {
    expect(CONTRIBUTION_KIND_MILESTONE.shader).toBe('M13');
    expect(contributionKindNotYetBridged('shader')).toBeNull();
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
    expect(contributionKindNotYetBridged('shader')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M13: defineExtension accepts dedicated shader contributions
// ---------------------------------------------------------------------------

describe('M13: shader SDK contracts', () => {
  const inlineShaderSource: ShaderInlineSource = {
    kind: 'inline',
    fragment: 'void main() { gl_FragColor = vec4(1.0); }',
  };

  const shaderContribution: ShaderContribution = {
    id: 'clip-glow-shader' as any,
    kind: 'shader',
    shaderId: 'shader.clipGlow',
    label: 'Clip Glow Shader',
    pass: {
      kind: 'clip',
      inputTextureUniform: 'u_clip',
      colorSpace: 'srgb',
      alpha: 'preserve',
    },
    source: inlineShaderSource,
    uniforms: [
      {
        name: 'u_intensity',
        label: 'Intensity',
        type: 'float',
        default: 0.5,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        name: 'u_tint',
        label: 'Tint',
        type: 'color',
        default: '#ffcc00',
      },
      {
        name: 'u_source',
        label: 'Source',
        type: 'textureRef',
        default: { kind: 'clip-frame' },
      },
    ],
    textures: [
      {
        name: 'clipFrame',
        uniform: 'u_clip',
        sourceKind: 'clip-frame',
        required: true,
        colorSpace: 'srgb',
        filter: 'linear',
        wrap: 'clamp-to-edge',
      },
    ],
    fallback: 'bypass',
  };

  it('preserves shader contribution metadata without normalizing to effect', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.example.shader' as any,
        version: '1.0.0',
        label: 'Shader Extension',
        contributions: [shaderContribution],
      },
    });

    const contribution = ext.manifest.contributions![0] as ShaderContribution;
    expect(contribution.kind).toBe('shader');
    expect(contribution.shaderId).toBe('shader.clipGlow');
    expect((contribution as unknown as { effectId?: string }).effectId).toBeUndefined();
    expect(Object.isFrozen(contribution.uniforms!)).toBe(true);
    expect(Object.isFrozen(contribution.textures!)).toBe(true);
  });

  it('ctx.shaders is a dedicated registration service and does not call ctx.effects', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.example.shader-service' as any,
        version: '1.0.0',
        label: 'Shader Service Extension',
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

    const handle = ctx.shaders.registerShader('shader.clipGlow', inlineShaderSource);
    expect(typeof handle.dispose).toBe('function');
    expect(shaderCalls).toEqual(['shader.clipGlow:inline']);
    expect(effectCalls).toEqual([]);
  });

  it('unwired shader registration reports shader diagnostics, not effect diagnostics', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.example.shader-unwired' as any,
        version: '1.0.0',
        label: 'Shader Unwired Extension',
        contributions: [shaderContribution],
      },
    });
    const ctx = createExtensionContext(ext);

    ctx.shaders.registerShader('shader.clipGlow', inlineShaderSource);

    const codes = ctx.services.diagnostics.diagnostics.map((diagnostic) => diagnostic.code);
    expect(codes).toContain('shaders/not-wired');
    expect(codes).not.toContain('effects/not-wired');
  });
});

// ---------------------------------------------------------------------------
// M6: defineExtension accepts parser/outputFormat/searchProvider contributions
// ---------------------------------------------------------------------------

describe('M6: defineExtension accepts M6 contribution types', () => {
  it('accepts a manifest with a parser contribution', () => {
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

  it('accepts a manifest with a compile-only outputFormat contribution', () => {
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
    expect((ext.manifest.contributions![0] as any).requiresRender).toBe(false);
  });

  it('accepts a manifest with a render-dependent outputFormat contribution (reserved)', () => {
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

  it('accepts a manifest with a searchProvider contribution', () => {
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

  it('accepts a manifest with all three M6 contribution kinds', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.all' as any,
        version: '1.0.0',
        label: 'M6 All Contributions',
        contributions: [
          {
            id: 'my-parser' as any,
            kind: 'parser',
            label: 'My Parser',
            acceptMimeTypes: ['image/png'],
          },
          {
            id: 'my-output' as any,
            kind: 'outputFormat',
            label: 'My Output',
            requiresRender: false,
            outputExtension: 'json',
          },
          {
            id: 'my-search' as any,
            kind: 'searchProvider',
            label: 'My Search',
          },
        ],
      },
    });
    expect(ext.manifest.contributions).toHaveLength(3);
    expect(ext.manifest.contributions![0].kind).toBe('parser');
    expect(ext.manifest.contributions![1].kind).toBe('outputFormat');
    expect(ext.manifest.contributions![2].kind).toBe('searchProvider');
  });

  it('rejects duplicate contribution IDs across M6 kinds', () => {
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

  it('render-dependent output declarations remain declarable but reserved', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m6.render-dependent' as any,
        version: '1.0.0',
        label: 'Render Dependent Test',
        contributions: [
          {
            id: 'hd-render' as any,
            kind: 'outputFormat',
            label: 'HD Render',
            requiresRender: true,
            outputExtension: 'mp4',
            outputMimeType: 'video/mp4',
          },
        ],
      },
    });
    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
    expect((ext.manifest.contributions![0] as any).requiresRender).toBe(true);
    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
    expect(contributionKindNotYetBridged('parser')).toBeNull();
  });

  it('unsupported contribution behavior is explicit in CONTRIBUTION_KIND_MILESTONE', () => {
    // clipType is now M9-bridged, so it returns null from contributionKindNotYetBridged.
    // Verify the milestone map still records the owning milestone.
    expect((CONTRIBUTION_KIND_MILESTONE as Record<string, string>)['clipType']).toBe('M9');
    expect(contributionKindNotYetBridged('clipType' as any)).toBeNull();

    const reservedKinds = [
      { kind: 'agentTool', expectedMilestone: 'M10' },
      { kind: 'agent', expectedMilestone: 'M10' },
    ];
    for (const { kind, expectedMilestone } of reservedKinds) {
      expect((CONTRIBUTION_KIND_MILESTONE as Record<string, string>)[kind]).toBe(expectedMilestone);
      expect(contributionKindNotYetBridged(kind as any)).toBeNull();
    }
  });
});

// ---------------------------------------------------------------------------
// Type-level tests (compile-time assertions)
// ---------------------------------------------------------------------------

describe('SDK type exports are complete', () => {
  it('ReighExtension has manifest and optional activate', () => {
    const ext: ReighExtension = defineExtension({ manifest: validManifest() });
    expect(ext.manifest.id).toBe('com.example.test');
    expect(typeof ext.activate).toBe('undefined');
  });

  it('ExtensionManifest supports all reserved fields', () => {
    const manifest: ExtensionManifest = {
      id: 'com.example.full' as any,
      version: '2.0.0',
      label: 'Full Manifest',
      apiVersion: 1,
      contributions: [],
      permissions: [],
      processes: [],
      migrations: [],
      comments: 'hello',
      dependsOn: [],
      renderability: {},
    };
    const ext = defineExtension({ manifest });
    expect(ext.manifest.id).toBe('com.example.full');
  });

  it('ProcessManifestEntry shape validates correctly', () => {
    const process: ProcessManifestEntry = {
      id: 'my-process',
      label: 'My Process',
      spawn: {
        command: 'node',
        args: ['--version'],
        env: { NODE_ENV: 'development' },
        cwd: '/tmp',
      },
      protocol: 'stdio-jsonrpc',
      healthCheck: 'ping',
      shutdown: 'SIGTERM',
      restartPolicy: 'on-failure',
    };
    expect(process.protocol).toBe('stdio-jsonrpc');
  });
});

// ---------------------------------------------------------------------------
// createExtensionContext — conservative shell
// ---------------------------------------------------------------------------

describe('createExtensionContext', () => {
  let extension: ReighExtension;
  let ctx: ExtensionContext;

  beforeEach(() => {
    extension = defineExtension({
      manifest: {
        id: 'com.example.ctx-test' as any,
        version: '2.3.4',
        label: 'Context Test Extension',
        description: 'Used for ExtensionContext tests',
        apiVersion: 1,
        contributions: [
          {
            id: 'ctx-slot' as any,
            kind: 'slot',
            slot: 'toolbar',
            order: 10,
            label: 'Test slot',
          },
        ],
      },
    });
    ctx = createExtensionContext(extension);
  });

  // ---- approved members ---------------------------------------------------

  it('exposes apiVersion: 1', () => {
    expect(ctx.apiVersion).toBe(1);
  });

  it('exposes readonly extension metadata', () => {
    expect(ctx.extension.id).toBe('com.example.ctx-test');
    expect(ctx.extension.version).toBe('2.3.4');
    expect(ctx.extension.label).toBe('Context Test Extension');
    expect(ctx.extension.description).toBe('Used for ExtensionContext tests');
    expect(ctx.extension.manifest).toBe(extension.manifest);
  });

  it('exposes chrome service', () => {
    expect(ctx.chrome).toBeDefined();
    expect(typeof ctx.chrome.toast).toBe('function');
    expect(typeof ctx.chrome.progress).toBe('function');
    expect(typeof ctx.chrome.subscribe).toBe('function');
    expect(typeof ctx.chrome.focus).toBe('function');
    expect(typeof ctx.chrome.announce).toBe('function');
  });

  it('exposes services.settings', () => {
    expect(ctx.services.settings).toBeDefined();
    expect(typeof ctx.services.settings.get).toBe('function');
    expect(typeof ctx.services.settings.set).toBe('function');
    expect(typeof ctx.services.settings.delete).toBe('function');
    expect(typeof ctx.services.settings.keys).toBe('function');
  });

  it('exposes services.i18n', () => {
    expect(ctx.services.i18n).toBeDefined();
    expect(typeof ctx.services.i18n.t).toBe('function');
  });

  it('exposes services.diagnostics', () => {
    expect(ctx.services.diagnostics).toBeDefined();
    expect(typeof ctx.services.diagnostics.report).toBe('function');
    expect(Array.isArray(ctx.services.diagnostics.diagnostics)).toBe(true);
  });

  it('exposes creative stubs', () => {
    expect(ctx.creative).toBeDefined();
    expect(Object.isFrozen(ctx.creative)).toBe(true);
  });

  // ---- creative stubs throw typed errors ----------------------------------

  it('creative.project throws ExtensionNotImplementedError', () => {
    expect(() => ctx.creative.project).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.project;
    } catch (err) {
      expect(err).toBeInstanceOf(ExtensionNotImplementedError);
      expect((err as ExtensionNotImplementedError).feature).toBe('project');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
      expect((err as ExtensionNotImplementedError).message).toContain(
        'ctx.creative.project',
      );
      expect((err as ExtensionNotImplementedError).message).toContain('M2');
    }
  });

  it('creative.timeline throws ExtensionNotImplementedError', () => {
    expect(() => ctx.creative.timeline).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.timeline;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });

  it('creative.assets throws with M6 milestone', () => {
    expect(() => ctx.creative.assets).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.assets;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('assets');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M6');
    }
  });

  it('creative.materials throws with M6 milestone', () => {
    expect(() => ctx.creative.materials).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.materials;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('materials');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M6');
    }
  });

  it('creative.sessions throws with M11 milestone', () => {
    expect(() => ctx.creative.sessions).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.sessions;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('sessions');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M11');
    }
  });

  it('creative.export throws with M2 milestone', () => {
    expect(() => ctx.creative.export).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.export;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('export');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
    }
  });

  it('creative.stage throws with M5 milestone', () => {
    expect(() => ctx.creative.stage).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.stage;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('stage');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M5');
    }
  });

  it('creative.writing throws with M2 milestone', () => {
    expect(() => ctx.creative.writing).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.writing;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('writing');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
    }
  });

  // ---- settings service ---------------------------------------------------

  it('settings.get returns undefined for missing keys', () => {
    expect(ctx.services.settings.get('nonexistent')).toBeUndefined();
  });

  it('settings.set and get round-trip', () => {
    ctx.services.settings.set('theme', 'dark');
    expect(ctx.services.settings.get('theme')).toBe('dark');
  });

  it('settings.set and get round-trip objects', () => {
    const obj = { nested: { value: 42 } };
    ctx.services.settings.set('config', obj);
    expect(ctx.services.settings.get('config')).toEqual(obj);
  });

  it('settings.delete removes keys', () => {
    ctx.services.settings.set('temp', 'data');
    expect(ctx.services.settings.get('temp')).toBe('data');
    ctx.services.settings.delete('temp');
    expect(ctx.services.settings.get('temp')).toBeUndefined();
  });

  it('settings.keys lists all stored keys', () => {
    ctx.services.settings.set('a', 1);
    ctx.services.settings.set('b', 2);
    const keys = ctx.services.settings.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
  });

  it('settings are scoped per extension', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.other.ext' as any,
        version: '1.0.0',
        label: 'Other',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    ctx.services.settings.set('shared-key', 'ext1-value');
    ctx2.services.settings.set('shared-key', 'ext2-value');

    expect(ctx.services.settings.get('shared-key')).toBe('ext1-value');
    expect(ctx2.services.settings.get('shared-key')).toBe('ext2-value');

    // Cleanup
    ctx.services.settings.delete('shared-key');
    ctx2.services.settings.delete('shared-key');
  });

  // ---- i18n service -------------------------------------------------------

  it('i18n.t returns the key verbatim when no replacements', () => {
    expect(ctx.services.i18n.t('hello.world')).toBe('hello.world');
  });

  it('i18n.t replaces placeholders', () => {
    const result = ctx.services.i18n.t('Hello, {{name}}!', { name: 'World' });
    expect(result).toBe('Hello, World!');
  });

  it('i18n.t replaces multiple placeholders', () => {
    const result = ctx.services.i18n.t('{{greeting}}, {{name}}!', {
      greeting: 'Hi',
      name: 'Alice',
    });
    expect(result).toBe('Hi, Alice!');
  });

  it('i18n.t replaces numeric values as strings', () => {
    const result = ctx.services.i18n.t('Count: {{n}}', { n: 42 });
    expect(result).toBe('Count: 42');
  });

  // ---- diagnostics service ------------------------------------------------

  it('diagnostics.report stores diagnostics with auto-filled extensionId', () => {
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'test/info',
      message: 'Test diagnostic',
    });
    const diags = ctx.services.diagnostics.diagnostics;
    expect(diags).toHaveLength(1);
    expect(diags[0].extensionId).toBe('com.example.ctx-test');
    expect(diags[0].severity).toBe('info');
    expect(diags[0].code).toBe('test/info');
    expect(diags[0].message).toBe('Test diagnostic');
  });

  it('diagnostics.report freezes stored diagnostics', () => {
    ctx.services.diagnostics.report({
      severity: 'warning',
      code: 'test/warn',
      message: 'Warning',
    });
    const diags = ctx.services.diagnostics.diagnostics;
    expect(Object.isFrozen(diags[0])).toBe(true);
  });

  // ---- chrome service -----------------------------------------------------

  it('chrome.toast does not throw', () => {
    expect(() => ctx.chrome.toast('Hello')).not.toThrow();
  });

  it('chrome.progress does not throw', () => {
    expect(() => ctx.chrome.progress(50, 'Rendering...')).not.toThrow();
  });

  it('chrome.subscribe returns a DisposeHandle', () => {
    const handle = ctx.chrome.subscribe('toast', () => {});
    expect(handle).toBeDefined();
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });

  it('chrome.subscribe delivers toast events to handlers', () => {
    const received: Array<{ message: string; severity: string }> = [];
    const handle = ctx.chrome.subscribe('toast', (payload) => {
      received.push(payload as any);
    });
    ctx.chrome.toast('Test message', 'warning');
    expect(received).toHaveLength(1);
    expect(received[0].message).toBe('Test message');
    expect(received[0].severity).toBe('warning');
    handle.dispose();
  });

  it('chrome.subscribe dispose removes the handler', () => {
    const received: string[] = [];
    const handle = ctx.chrome.subscribe('toast', (payload: any) => {
      received.push(payload.message);
    });
    handle.dispose();
    ctx.chrome.toast('After dispose');
    expect(received).toHaveLength(0);
  });

  it('chrome.subscribe delivers progress events', () => {
    const received: Array<{ percent: number; label?: string }> = [];
    const handle = ctx.chrome.subscribe('progress', (payload: any) => {
      received.push(payload);
    });
    ctx.chrome.progress(75, 'Exporting...');
    expect(received).toHaveLength(1);
    expect(received[0].percent).toBe(75);
    expect(received[0].label).toBe('Exporting...');
    handle.dispose();
  });

  // ---- chrome.focus -------------------------------------------------------

  describe('chrome.focus', () => {
    let shellRoot: HTMLElement;

    beforeEach(() => {
      // Create a fresh shell root for each test
      shellRoot = document.createElement('div');
      shellRoot.setAttribute('data-test-shell', 'true');
      document.body.appendChild(shellRoot);
      setEditorShellRoot(shellRoot);
    });

    afterEach(() => {
      setEditorShellRoot(null);
      if (shellRoot.parentNode) {
        shellRoot.parentNode.removeChild(shellRoot);
      }
    });

    it('focuses an element inside the shell root', () => {
      const btn = document.createElement('button');
      btn.id = 'inside-btn';
      shellRoot.appendChild(btn);

      ctx.chrome.focus('#inside-btn');
      expect(document.activeElement).toBe(btn);
    });

    it('diagnoses a selector not found anywhere', () => {
      ctx.chrome.focus('#nonexistent');
      const diags = ctx.services.diagnostics.diagnostics;
      const focusDiags = diags.filter((d) => d.code === 'chrome/focus-missing-selector');
      expect(focusDiags).toHaveLength(1);
      expect(focusDiags[0].severity).toBe('warning');
      expect(focusDiags[0].message).toContain('#nonexistent');
    });

    it('diagnoses an out-of-shell (portal) target', () => {
      // Create element outside shell root but inside document
      const portalBtn = document.createElement('button');
      portalBtn.id = 'portal-btn';
      document.body.appendChild(portalBtn);

      ctx.chrome.focus('#portal-btn');
      const diags = ctx.services.diagnostics.diagnostics;
      const focusDiags = diags.filter((d) => d.code === 'chrome/focus-out-of-shell');
      expect(focusDiags).toHaveLength(1);
      expect(focusDiags[0].severity).toBe('warning');
      expect(focusDiags[0].message).toContain('portal');

      // Cleanup
      document.body.removeChild(portalBtn);
    });

    it('diagnoses when no shell root is mounted', () => {
      setEditorShellRoot(null);

      ctx.chrome.focus('.any-selector');
      const diags = ctx.services.diagnostics.diagnostics;
      const focusDiags = diags.filter((d) => d.code === 'chrome/focus-no-shell');
      expect(focusDiags).toHaveLength(1);
      expect(focusDiags[0].severity).toBe('warning');
      expect(focusDiags[0].message).toContain('no editor shell root');
    });

    it('does not focus elements outside the shell root', () => {
      const outsideBtn = document.createElement('button');
      outsideBtn.id = 'outside-btn';
      document.body.appendChild(outsideBtn);

      const prevActive = document.activeElement;
      ctx.chrome.focus('#outside-btn');
      // Should NOT have focused the outside element
      expect(document.activeElement).not.toBe(outsideBtn);
      // Should have emitted a diagnostic
      const diags = ctx.services.diagnostics.diagnostics;
      const focusDiags = diags.filter((d) => d.code === 'chrome/focus-out-of-shell');
      expect(focusDiags).toHaveLength(1);

      document.body.removeChild(outsideBtn);
    });
  });

  // ---- chrome.announce ----------------------------------------------------

  describe('chrome.announce', () => {
    let shellRoot: HTMLElement;

    beforeEach(() => {
      shellRoot = document.createElement('div');
      document.body.appendChild(shellRoot);
      setEditorShellRoot(shellRoot);
    });

    afterEach(() => {
      setEditorShellRoot(null);
      if (shellRoot.parentNode) {
        shellRoot.parentNode.removeChild(shellRoot);
      }
    });

    it('creates an aria-live host node on first call', () => {
      ctx.chrome.announce('Hello, world!');

      const liveRegion = shellRoot.querySelector('[data-video-editor-aria-live]');
      expect(liveRegion).not.toBeNull();
      expect(liveRegion!.getAttribute('aria-live')).toBe('polite');
      expect(liveRegion!.getAttribute('aria-atomic')).toBe('true');
    });

    it('sets the announced text (after rAF)', async () => {
      ctx.chrome.announce('Test announcement');

      // Wait for requestAnimationFrame
      await new Promise((resolve) => requestAnimationFrame(resolve));

      const liveRegion = shellRoot.querySelector('[data-video-editor-aria-live]');
      expect(liveRegion).not.toBeNull();
      expect(liveRegion!.textContent).toBe('Test announcement');
    });

    it('respects assertive politeness', () => {
      ctx.chrome.announce('Important!', 'assertive');

      const liveRegion = shellRoot.querySelector('[data-video-editor-aria-live]');
      expect(liveRegion).not.toBeNull();
      expect(liveRegion!.getAttribute('aria-live')).toBe('assertive');
    });

    it('reuses the same aria-live host for subsequent calls', () => {
      ctx.chrome.announce('First');
      ctx.chrome.announce('Second', 'assertive');

      const regions = shellRoot.querySelectorAll('[data-video-editor-aria-live]');
      expect(regions).toHaveLength(1);
      expect(regions[0].getAttribute('aria-live')).toBe('assertive');
    });

    it('does not throw when no shell root is mounted', () => {
      setEditorShellRoot(null);

      expect(() => ctx.chrome.announce('No shell')).not.toThrow();
    });

    it('clears text before setting new text for re-announcement', async () => {
      ctx.chrome.announce('First message');

      // Wait for rAF
      await new Promise((resolve) => requestAnimationFrame(resolve));

      const liveRegion = shellRoot.querySelector('[data-video-editor-aria-live]');
      expect(liveRegion!.textContent).toBe('First message');

      // The clear happens synchronously, then rAF sets new text
      // So after the announce call but before rAF, textContent should be ''
      ctx.chrome.announce('Second message');
      // Synchronously cleared
      expect(liveRegion!.textContent).toBe('');

      // After rAF, new text is set
      await new Promise((resolve) => requestAnimationFrame(resolve));
      expect(liveRegion!.textContent).toBe('Second message');
    });
  });

  // ---- no internal mutation escape hatch ----------------------------------

  it('does not expose DataProvider', () => {
    expect((ctx as any).DataProvider).toBeUndefined();
    expect((ctx as any).dataProvider).toBeUndefined();
    expect((ctx as any).provider).toBeUndefined();
    expect((ctx as any).data).toBeUndefined();
  });

  it('does not expose applyEdit', () => {
    expect((ctx as any).applyEdit).toBeUndefined();
    expect((ctx as any).edit).toBeUndefined();
    expect((ctx as any).mutate).toBeUndefined();
  });

  it('does not expose timeline store', () => {
    expect((ctx as any).timelineStore).toBeUndefined();
    expect((ctx as any).timeline).toBeUndefined();
    expect((ctx as any).store).toBeUndefined();
    expect((ctx as any).getTimeline).toBeUndefined();
  });

  it('does not expose internal ops', () => {
    expect((ctx as any).ops).toBeUndefined();
    expect((ctx as any).internalOps).toBeUndefined();
    expect((ctx as any)._internal).toBeUndefined();
    expect((ctx as any).__editorInternals).toBeUndefined();
  });

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

  // ---- frozen / readonly --------------------------------------------------

  it('context is frozen', () => {
    expect(Object.isFrozen(ctx)).toBe(true);
  });

  it('extension metadata object is frozen', () => {
    expect(Object.isFrozen(ctx.extension)).toBe(true);
  });

  it('services object is frozen', () => {
    expect(Object.isFrozen(ctx.services)).toBe(true);
  });

  it('apiVersion cannot be reassigned (throws in strict mode)', () => {
    expect(() => {
      (ctx as any).apiVersion = 999;
    }).toThrow();
  });

  it('extension metadata cannot be mutated', () => {
    expect(() => {
      (ctx.extension as any).version = '999.0.0';
    }).toThrow();
  });

  it('manifest is the same frozen object from defineExtension', () => {
    // defineExtension freezes the manifest, and the context preserves that reference
    expect(ctx.extension.manifest).toBe(extension.manifest);
    expect(Object.isFrozen(ctx.extension.manifest)).toBe(true);
  });

  it('creative cannot be reassigned', () => {
    expect(() => {
      (ctx as any).creative = {};
    }).toThrow();
  });

  // ---- multiple contexts are independent -----------------------------------

  it('two contexts for different extensions have independent diagnostics', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.independent.ext' as any,
        version: '1.0.0',
        label: 'Independent',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'ctx1',
      message: 'From ctx1',
    });
    ctx2.services.diagnostics.report({
      severity: 'warning',
      code: 'ctx2',
      message: 'From ctx2',
    });

    expect(ctx.services.diagnostics.diagnostics).toHaveLength(1);
    expect(ctx.services.diagnostics.diagnostics[0].code).toBe('ctx1');
    expect(ctx2.services.diagnostics.diagnostics).toHaveLength(1);
    expect(ctx2.services.diagnostics.diagnostics[0].code).toBe('ctx2');
  });

  it('two contexts for different extensions have independent subscribers', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.independent2.ext' as any,
        version: '1.0.0',
        label: 'Independent2',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    const received1: string[] = [];
    const received2: string[] = [];
    ctx.chrome.subscribe('toast', (p: any) => received1.push(p.message));
    ctx2.chrome.subscribe('toast', (p: any) => received2.push(p.message));

    ctx.chrome.toast('Only ctx1');
    expect(received1).toEqual(['Only ctx1']);
    expect(received2).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// createCreativeContextStubs — standalone
// ---------------------------------------------------------------------------

describe('createCreativeContextStubs', () => {
  it('returns a frozen object', () => {
    const stubs = createCreativeContextStubs();
    expect(Object.isFrozen(stubs)).toBe(true);
  });

  it('every member throws ExtensionNotImplementedError', () => {
    const stubs = createCreativeContextStubs();
    const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as string[];
    for (const member of members) {
      expect(
        () => (stubs as Record<string, unknown>)[member],
        `creative.${member} should throw`,
      ).toThrow(ExtensionNotImplementedError);
    }
  });

  it('each member has the correct feature and milestone', () => {
    const stubs = createCreativeContextStubs();
    const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as string[];
    for (const member of members) {
      try {
        (stubs as Record<string, unknown>)[member];
        // should not reach here
        expect(true).toBe(false);
      } catch (err) {
        expect(err).toBeInstanceOf(ExtensionNotImplementedError);
        const e = err as ExtensionNotImplementedError;
        expect(e.feature).toBe(member);
        expect(e.milestone).toBe(
          (CREATIVE_MEMBER_MILESTONE as Record<string, string>)[member],
        );
      }
    }
  });

  it('all 10 creative members are enumerable', () => {
    const stubs = createCreativeContextStubs();
    const keys = Object.keys(stubs).sort();
    expect(keys).toEqual([
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
  });
});

// ---------------------------------------------------------------------------
// ExtensionNotImplementedError
// ---------------------------------------------------------------------------

describe('ExtensionNotImplementedError', () => {
  it('is an instance of Error', () => {
    const err = new ExtensionNotImplementedError('project', 'M2');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ExtensionNotImplementedError);
    expect(err.name).toBe('ExtensionNotImplementedError');
  });

  it('has feature and milestone properties', () => {
    const err = new ExtensionNotImplementedError('timeline', 'M3');
    expect(err.feature).toBe('timeline');
    expect(err.milestone).toBe('M3');
  });

  it('has a descriptive message', () => {
    const err = new ExtensionNotImplementedError('assets', 'M6');
    expect(err.message).toBe(
      'ctx.creative.assets is not implemented until M6.',
    );
  });
});

// ---------------------------------------------------------------------------
// CREATIVE_MEMBER_MILESTONE
// ---------------------------------------------------------------------------

describe('CREATIVE_MEMBER_MILESTONE', () => {
  it('has entries for all 10 creative members', () => {
    const keys = Object.keys(CREATIVE_MEMBER_MILESTONE).sort();
    expect(keys).toEqual([
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
  });

  it('all values are milestone strings starting with M', () => {
    for (const milestone of Object.values(CREATIVE_MEMBER_MILESTONE)) {
      expect(milestone).toMatch(/^M\d+$/);
    }
  });
});

// ---------------------------------------------------------------------------
// M11: Live Data Bridge — source, channel, sample, bake, permission,
// recording, learn, steering, and binding-resolution type tests
// ---------------------------------------------------------------------------

describe('M11: LiveSourceKind', () => {
  it('accepts all documented kind values', () => {
    const kinds: LiveSourceKind[] = [
      'webcam',
      'microphone',
      'midi',
      'serial',
      'bluetooth',
      'generated',
      'screen-capture',
      'audio-device',
      'osc',
      'custom',
    ];
    expect(kinds).toHaveLength(10);
    for (const k of kinds) {
      expect(typeof k).toBe('string');
    }
  });
});

describe('M11: LiveSourceStatus', () => {
  it('covers all lifecycle states', () => {
    const states: LiveSourceStatus[] = [
      'inactive',
      'activating',
      'active',
      'error',
      'disposed',
      'orphaned',
    ];
    expect(states).toHaveLength(6);
  });
});

describe('M11: LiveSourceDiagnostic', () => {
  it('is constructable', () => {
    const diag: LiveSourceDiagnostic = {
      severity: 'error',
      code: 'live/permission-denied',
      message: 'Camera permission denied',
      sourceId: 'src-1',
      detail: { device: 'webcam-1' },
    };
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('live/permission-denied');
    expect(diag.sourceId).toBe('src-1');
  });
});

describe('M11: LiveSource', () => {
  it('is constructable (minimal)', () => {
    const src: LiveSource = {
      id: 'src-1',
      kind: 'webcam',
      status: 'active',
      diagnostics: [],
    };
    expect(src.id).toBe('src-1');
    expect(src.kind).toBe('webcam');
    expect(src.status).toBe('active');
    expect(src.diagnostics).toHaveLength(0);
  });

  it('is constructable (full)', () => {
    const src: LiveSource = {
      id: 'src-2',
      kind: 'generated',
      status: 'activating',
      label: 'AI Generator',
      diagnostics: [{ severity: 'info', code: 'live/starting', message: 'Starting...' }],
      metadata: { model: 'v2' },
      permission: { state: 'prompt', reason: 'Need camera access' },
      recording: { active: true, mode: 'stream' },
      learnMode: 'idle',
    };
    expect(src.label).toBe('AI Generator');
    expect(src.permission?.state).toBe('prompt');
    expect(src.recording?.active).toBe(true);
    expect(src.learnMode).toBe('idle');
  });
});

describe('M11: LiveChannelKind', () => {
  it('covers all channel kinds', () => {
    const kinds: LiveChannelKind[] = ['video', 'audio', 'midi', 'osc', 'data', 'control'];
    expect(kinds).toHaveLength(6);
  });
});

describe('M11: LiveChannelDescriptor', () => {
  it('is string-compatible (branded string)', () => {
    const ch: LiveChannelDescriptor = 'ch-1' as LiveChannelDescriptor;
    // String operations work
    expect(ch.length).toBe(4);
    expect(ch.toUpperCase()).toBe('CH-1');
    expect(typeof ch).toBe('string');
  });

  it('can be used as a map key', () => {
    const ch: LiveChannelDescriptor = 'ch-map' as LiveChannelDescriptor;
    const map = new Map<LiveChannelDescriptor, string>();
    map.set(ch, 'value');
    expect(map.get(ch)).toBe('value');
  });
});

describe('M11: LiveChannelMetadata', () => {
  it('is constructable', () => {
    const meta: LiveChannelMetadata = {
      channelId: 'ch-1' as LiveChannelDescriptor,
      kind: 'video',
      sourceId: 'src-1',
      label: 'Webcam Feed',
      metadata: { fps: 30 },
    };
    expect(meta.channelId).toBe('ch-1');
    expect(meta.kind).toBe('video');
    expect(meta.sourceId).toBe('src-1');
    expect(meta.label).toBe('Webcam Feed');
  });
});

describe('M11: LiveSampleFormat', () => {
  it('covers all sample formats', () => {
    const formats: LiveSampleFormat[] = ['raw', 'encoded', 'json', 'binary'];
    expect(formats).toHaveLength(4);
  });
});

describe('M11: LiveSampleFrame', () => {
  it('is constructable with Uint8Array data', () => {
    const frame: LiveSampleFrame = {
      timestamp: 100,
      data: new Uint8Array([1, 2, 3]),
      format: 'raw',
      metadata: { size: 3 },
    };
    expect(frame.timestamp).toBe(100);
    expect(frame.format).toBe('raw');
  });

  it('is constructable with JSON data', () => {
    const frame: LiveSampleFrame = {
      timestamp: 200,
      data: { value: 42 },
      format: 'json',
    };
    expect(frame.timestamp).toBe(200);
    expect((frame.data as Record<string, unknown>).value).toBe(42);
  });
});

describe('M11: LiveSample', () => {
  it('is constructable', () => {
    const sample: LiveSample = {
      channelId: 'ch-1' as LiveChannelDescriptor,
      frame: { timestamp: 0, data: new Uint8Array(), format: 'raw' },
      sequenceNumber: 42,
    };
    expect(sample.channelId).toBe('ch-1');
    expect(sample.sequenceNumber).toBe(42);
  });
});

describe('M11: LivePermissionState', () => {
  it('covers all permission states', () => {
    const states: LivePermissionState[] = ['prompt', 'granted', 'denied', 'unavailable'];
    expect(states).toHaveLength(4);
  });
});

describe('M11: LiveSourcePermission', () => {
  it('is constructable', () => {
    const perm: LiveSourcePermission = {
      state: 'granted',
      reason: 'Camera access for preview',
      deviceLabel: 'FaceTime HD Camera',
      requestedAt: '2026-06-20T00:00:00Z',
    };
    expect(perm.state).toBe('granted');
    expect(perm.deviceLabel).toBe('FaceTime HD Camera');
    expect(perm.requestedAt).toBe('2026-06-20T00:00:00Z');
  });
});

describe('M11: LiveRecordingMode', () => {
  it('covers all recording modes', () => {
    const modes: LiveRecordingMode[] = ['stream', 'take', 'loop', 'trigger'];
    expect(modes).toHaveLength(4);
  });
});

describe('M11: LiveRecordingState', () => {
  it('is constructable', () => {
    const rec: LiveRecordingState = {
      active: true,
      mode: 'take',
      startedAt: '2026-06-20T00:00:00Z',
      duration: 5000,
      takeIndex: 3,
    };
    expect(rec.active).toBe(true);
    expect(rec.mode).toBe('take');
    expect(rec.takeIndex).toBe(3);
  });
});

describe('M11: LiveLearnMode', () => {
  it('covers all learn modes', () => {
    const modes: LiveLearnMode[] = ['idle', 'mapping', 'calibrating', 'tracking'];
    expect(modes).toHaveLength(4);
  });
});

describe('M11: LiveBakeTargetKind', () => {
  it('covers all bake target kinds', () => {
    const kinds: LiveBakeTargetKind[] = [
      'asset',
      'keyframe',
      'automation',
      'clip',
      'sidecar',
      'render-material',
    ];
    expect(kinds).toHaveLength(6);
  });
});

describe('M11: LiveBakeTarget', () => {
  it('is constructable', () => {
    const target: LiveBakeTarget = {
      kind: 'asset',
      ref: 'asset-key-1',
      params: { format: 'png' },
    };
    expect(target.kind).toBe('asset');
    expect(target.ref).toBe('asset-key-1');
    expect(target.params).toEqual({ format: 'png' });
  });
});

describe('M11: LiveBakeSelection', () => {
  it('is constructable (full)', () => {
    const selection: LiveBakeSelection = {
      sourceId: 'src-1',
      channelIds: ['ch-1' as LiveChannelDescriptor],
      timeRange: [0, 5000],
      frameRange: [10, 120],
      sampleRange: [0, 100],
      takeId: 'take-a',
      targets: [{ kind: 'keyframe', ref: 'param.opacity' }],
    };
    expect(selection.sourceId).toBe('src-1');
    expect(selection.channelIds).toHaveLength(1);
    expect(selection.timeRange).toEqual([0, 5000]);
    expect(selection.frameRange).toEqual([10, 120]);
    expect(selection.takeId).toBe('take-a');
    expect(selection.targets).toHaveLength(1);
  });

  it('is constructable (minimal — all channels, all time)', () => {
    const selection: LiveBakeSelection = {
      sourceId: 'src-1',
      targets: [{ kind: 'asset', ref: 'output-key' }],
    };
    expect(selection.channelIds).toBeUndefined();
    expect(selection.timeRange).toBeUndefined();
    expect(selection.frameRange).toBeUndefined();
    expect(selection.sampleRange).toBeUndefined();
    expect(selection.takeId).toBeUndefined();
  });
});

describe('M11: LiveBakeResult', () => {
  it('is constructable (success)', () => {
    const result: LiveBakeResult = {
      sourceId: 'src-1',
      targets: [
        {
          target: { kind: 'asset', ref: 'output-key' },
          outputRef: 'baked-asset-1',
        },
      ],
      diagnostics: [],
      success: true,
    };
    expect(result.success).toBe(true);
    expect(result.targets).toHaveLength(1);
    expect(result.targets[0].outputRef).toBe('baked-asset-1');
  });

  it('is constructable (failure)', () => {
    const result: LiveBakeResult = {
      sourceId: 'src-1',
      targets: [
        {
          target: { kind: 'asset', ref: 'output-key' },
          outputRef: '',
          diagnostics: [{ severity: 'error', code: 'live/bake-failed', message: 'No samples to bake' }],
        },
      ],
      diagnostics: [{ severity: 'error', code: 'live/bake-failed', message: 'Bake failed' }],
      success: false,
    };
    expect(result.success).toBe(false);
    expect(result.diagnostics).toHaveLength(1);
  });
});

describe('M11: SteeringDecisionKind', () => {
  it('covers all steering decision kinds', () => {
    const kinds: SteeringDecisionKind[] = ['supersede', 'fork', 'reject'];
    expect(kinds).toHaveLength(3);
  });
});

describe('M11: Steering resolver contract types', () => {
  it('covers parameter hotness, prior-sample policy, provenance, and changes', () => {
    const hotness: SteeringParameterHotness[] = ['hot', 'non-hot'];
    const policies: SteeringPriorSamplePolicy[] = ['replace', 'fork', 'retain', 'discard'];
    const provenance: SteeringProvenance = {
      prompt: 'A slow pan across clouds',
      model: 'reigh-gen-v1',
      seed: 42,
      producerExtensionId: 'ext.generator',
      tags: ['user-approved'],
    };
    const change: SteeringParameterChange = {
      path: 'params.prompt',
      previousValue: 'Clouds',
      nextValue: 'Storm clouds',
      hotness: 'hot',
    };

    expect(hotness).toHaveLength(2);
    expect(policies).toHaveLength(4);
    expect(provenance.model).toBe('reigh-gen-v1');
    expect(change.hotness).toBe('hot');
  });
});

describe('M11: SteeringLineage', () => {
  it('is constructable', () => {
    const lineage: SteeringLineage = {
      generationIndex: 3,
      steerHash: 'abc123',
      parentRefs: ['session-1', 'session-2'],
      producerVersion: '1.2.0',
      provenance: {
        prompt: 'A slow pan across clouds',
        model: 'reigh-gen-v1',
        seed: 42,
        producerExtensionId: 'ext.generator',
      },
      provenanceTags: ['steered', 'user-approved'],
    };
    expect(lineage.generationIndex).toBe(3);
    expect(lineage.steerHash).toBe('abc123');
    expect(lineage.parentRefs).toEqual(['session-1', 'session-2']);
    expect(lineage.producerVersion).toBe('1.2.0');
    expect(lineage.provenanceTags).toEqual(['steered', 'user-approved']);
  });
});

describe('M11: SteeringDecision', () => {
  it('is constructable (supersede)', () => {
    const decision: SteeringDecision = {
      kind: 'supersede',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 1,
        steerHash: 'hash1',
        parentRefs: ['session-0'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 1 },
      },
      reason: 'Better quality available',
      replacementChannelId: 'ch-new' as LiveChannelDescriptor,
    };
    expect(decision.kind).toBe('supersede');
    expect(decision.sessionId).toBe('session-1');
    expect(decision.replacementChannelId).toBe('ch-new');
  });

  it('is constructable (reject)', () => {
    const decision: SteeringDecision = {
      kind: 'reject',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 0,
        steerHash: 'hash0',
        parentRefs: ['session-0'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 1 },
      },
      reason: 'Generation failed quality check',
    };
    expect(decision.kind).toBe('reject');
    expect(decision.replacementChannelId).toBeUndefined();
  });
});

describe('M11: BindingResolutionStatus', () => {
  it('covers all resolution states', () => {
    const states: BindingResolutionStatus[] = [
      'resolved',
      'unresolved',
      'orphaned',
      'disposed',
      'missing',
    ];
    expect(states).toHaveLength(5);
  });
});

describe('M11: LiveBinding', () => {
  it('is constructable (resolved)', () => {
    const binding: LiveBinding = {
      bindingId: 'bind-1',
      sourceId: 'src-1',
      channelId: 'ch-1' as LiveChannelDescriptor,
      targetClipId: 'clip-1',
      status: 'resolved',
    };
    expect(binding.bindingId).toBe('bind-1');
    expect(binding.sourceId).toBe('src-1');
    expect(binding.status).toBe('resolved');
  });

  it('is constructable (orphaned with diagnostic)', () => {
    const binding: LiveBinding = {
      bindingId: 'bind-2',
      sourceId: 'src-orphan',
      status: 'orphaned',
      diagnostic: {
        severity: 'warning',
        code: 'live/orphaned-source',
        message: 'Source extension was disposed',
        sourceId: 'src-orphan',
      },
    };
    expect(binding.status).toBe('orphaned');
    expect(binding.diagnostic?.code).toBe('live/orphaned-source');
  });
});

describe('M11: LiveBindingResolution', () => {
  it('is constructable (resolved)', () => {
    const resolution: LiveBindingResolution = {
      bindingId: 'bind-1',
      status: 'resolved',
      source: {
        id: 'src-1',
        kind: 'webcam',
        status: 'active',
        diagnostics: [],
      },
      channel: {
        channelId: 'ch-1' as LiveChannelDescriptor,
        kind: 'video',
        sourceId: 'src-1',
      },
    };
    expect(resolution.status).toBe('resolved');
    expect(resolution.source?.id).toBe('src-1');
    expect(resolution.channel?.channelId).toBe('ch-1');
  });

  it('is constructable (unresolved with diagnostic)', () => {
    const resolution: LiveBindingResolution = {
      bindingId: 'bind-2',
      status: 'unresolved',
      diagnostic: {
        severity: 'info',
        code: 'live/source-inactive',
        message: 'Source is not yet active',
      },
    };
    expect(resolution.status).toBe('unresolved');
    expect(resolution.source).toBeUndefined();
    expect(resolution.diagnostic?.code).toBe('live/source-inactive');
  });
});

describe('M11: LiveBindingMetadata', () => {
  it('is constructable', () => {
    const meta: LiveBindingMetadata = {
      bindings: [
        {
          bindingId: 'bind-1',
          sourceId: 'src-1',
          status: 'resolved',
        },
        {
          bindingId: 'bind-2',
          sourceId: 'src-2',
          status: 'orphaned',
        },
      ],
      unresolvedCount: 0,
      orphanedCount: 1,
      disposedCount: 0,
    };
    expect(meta.bindings).toHaveLength(2);
    expect(meta.orphanedCount).toBe(1);
    expect(meta.unresolvedCount).toBe(0);
  });
});

describe('M11: LiveSessionsService interface shape', () => {
  it('can be implemented with a stub', () => {
    const svc: LiveSessionsService = {
      registerSource(_src) {
        return { dispose() {} };
      },
      getSource(_id) { return undefined; },
      listSources() { return []; },
      openChannel(_sid, _kind, _meta) { return 'ch-1' as LiveChannelDescriptor; },
      closeChannel(_ch) {},
      getChannelMetadata(_ch) { return undefined; },
      pushSample(_ch, _frame) {},
      subscribeSamples(_ch, _listener) { return { dispose() {} }; },
      bake(_sel) {
        return { sourceId: '', targets: [], diagnostics: [], success: true };
      },
      removeLiveBindings(_sid) {},
      resolveBinding(_bid) {
        return { bindingId: _bid, status: 'missing' };
      },
      getBindingMetadata() {
        return { bindings: [], unresolvedCount: 0, orphanedCount: 0, disposedCount: 0 };
      },
      applySteeringDecision(_dec) {},
      getDiagnostics(_sid) { return []; },
    };
    expect(typeof svc.registerSource).toBe('function');
    expect(typeof svc.openChannel).toBe('function');
    expect(typeof svc.bake).toBe('function');
    expect(typeof svc.resolveBinding).toBe('function');
    expect(typeof svc.getBindingMetadata).toBe('function');
  });
});

describe('M11: GenerationSession updated with typed channels', () => {
  it('getSampleChannel returns LiveChannelDescriptor (string-compatible)', () => {
    // Type-level proof: a GenerationSession can be implemented
    const session: GenerationSession = {
      id: 'gen-1',
      progress: 50,
      progressLabel: 'Generating...',
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress(_listener) { return { dispose() {} }; },
      cancel() {},
      getSampleChannel() { return 'gen-1-channel' as LiveChannelDescriptor; },
      onSample(_listener) { return { dispose() {} }; },
      getSteeringLineage() { return undefined; },
      complete(_result) {},
    };
    // String compatibility: the returned value can be used as a string
    const ch: LiveChannelDescriptor = session.getSampleChannel();
    expect(typeof ch).toBe('string');
    expect(ch.length).toBeGreaterThan(0);
  });

  it('onSample can be subscribed', () => {
    let received: LiveSample | undefined;
    const session: GenerationSession = {
      id: 'gen-2',
      progress: 0,
      cancelled: false,
      done: false,
      diagnostics: [],
      onProgress() { return { dispose() {} }; },
      cancel() {},
      getSampleChannel() { return 'ch' as LiveChannelDescriptor; },
      onSample(listener) {
        listener({
          channelId: 'ch' as LiveChannelDescriptor,
          frame: { timestamp: 0, data: new Uint8Array(), format: 'raw' },
          sequenceNumber: 1,
        });
        return { dispose() {} };
      },
      getSteeringLineage() { return undefined; },
      complete() {},
    };
    session.onSample((s) => { received = s; });
    expect(received).toBeDefined();
    expect(received!.sequenceNumber).toBe(1);
  });

  it('getSteeringLineage returns lineage when available', () => {
    const lineage: SteeringLineage = {
      generationIndex: 5,
      steerHash: 'hash5',
      parentRefs: ['gen-1', 'gen-2'],
      producerVersion: '2.0.0',
      provenance: { prompt: 'Prompt', model: 'model-a', seed: 5 },
    };
    const session: GenerationSession = {
      id: 'gen-3',
      progress: 100,
      cancelled: false,
      done: true,
      diagnostics: [],
      onProgress() { return { dispose() {} }; },
      cancel() {},
      getSampleChannel() { return 'ch' as LiveChannelDescriptor; },
      onSample() { return { dispose() {} }; },
      getSteeringLineage() { return lineage; },
      complete() {},
    };
    const result = session.getSteeringLineage();
    expect(result).toBeDefined();
    expect(result!.generationIndex).toBe(5);
    expect(result!.steerHash).toBe('hash5');
  });

  it('accepts explicit live delivery metadata on SDK session results', () => {
    const steeringDecision: SteeringDecision = {
      kind: 'fork',
      sessionId: 'gen-live',
      lineage: {
        generationIndex: 2,
        steerHash: 'hash2',
        parentRefs: ['gen-previous'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 2 },
      },
      reason: 'Non-hot steering change',
    };
    const liveDelivery: GenerationSessionLiveDelivery = {
      origin: 'agent-tool',
      steeringDecision,
      activeChannels: ['gen-live:frames' as LiveChannelDescriptor],
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
    };
    const session: GenerationSession = {
      id: 'gen-live',
      progress: 10,
      cancelled: false,
      done: false,
      diagnostics: [],
      liveDelivery,
      finalRefs: ['asset-final'],
      bakedRefs: ['asset-baked'],
      onProgress() { return { dispose() {} }; },
      cancel() {},
      getSampleChannel() { return 'gen-live:frames' as LiveChannelDescriptor; },
      onSample() { return { dispose() {} }; },
      getSteeringLineage() { return steeringDecision.lineage; },
      complete() {},
    };

    expect(session.liveDelivery?.steeringDecision.kind).toBe('fork');
    expect(session.finalRefs).toEqual(['asset-final']);
    expect(session.bakedRefs).toEqual(['asset-baked']);
  });
});

describe('M11: Updated CREATIVE_MEMBER_MILESTONE', () => {
  it('sessions milestone is M11', () => {
    expect(CREATIVE_MEMBER_MILESTONE.sessions).toBe('M11');
  });

  it('other milestones are unchanged', () => {
    expect(CREATIVE_MEMBER_MILESTONE.project).toBe('M2');
    expect(CREATIVE_MEMBER_MILESTONE.timeline).toBe('M3');
    expect(CREATIVE_MEMBER_MILESTONE.assets).toBe('M6');
    expect(CREATIVE_MEMBER_MILESTONE.export).toBe('M2');
  });
});


// ---------------------------------------------------------------------------
// M12: Planner requirement contracts — constructability
// ---------------------------------------------------------------------------

describe('M12: CapabilityVersion is constructable', () => {
  it('accepts minimal fields', () => {
    const v: CapabilityVersion = { semver: '1.0.0' };
    expect(v.semver).toBe('1.0.0');
  });

  it('accepts full provenance fields', () => {
    const v: CapabilityVersion = {
      semver: '2.1.0',
      declaredBy: 'com.example.ext',
      contributionId: 'my-effect',
    };
    expect(v.declaredBy).toBe('com.example.ext');
    expect(v.contributionId).toBe('my-effect');
  });
});

describe('M12: CapabilitySourceRef is constructable', () => {
  it('accepts extension source ref', () => {
    const ref: CapabilitySourceRef = {
      source: 'extension',
      extensionId: 'com.example.ext',
      contributionId: 'my-effect',
      version: { semver: '1.0.0' },
    };
    expect(ref.source).toBe('extension');
    expect(ref.extensionId).toBe('com.example.ext');
    expect(ref.version?.semver).toBe('1.0.0');
  });

  it('accepts built-in source ref', () => {
    const ref: CapabilitySourceRef = { source: 'built-in' };
    expect(ref.source).toBe('built-in');
    expect(ref.extensionId).toBeUndefined();
  });

  it('accepts registry source ref', () => {
    const ref: CapabilitySourceRef = { source: 'registry', contributionId: 'reg-1' };
    expect(ref.source).toBe('registry');
  });

  it('accepts manifest source ref', () => {
    const ref: CapabilitySourceRef = { source: 'manifest', extensionId: 'com.example.ext' };
    expect(ref.source).toBe('manifest');
  });

  it('accepts provider source ref', () => {
    const ref: CapabilitySourceRef = { source: 'provider' };
    expect(ref.source).toBe('provider');
  });
});

describe('M12: RouteFitMetadata is constructable', () => {
  it('accepts supported fit', () => {
    const fit: RouteFitMetadata = {
      route: 'browser-export' as RenderRoute,
      fit: 'supported',
    };
    expect(fit.route).toBe('browser-export');
    expect(fit.fit).toBe('supported');
  });

  it('accepts blocked fit with reason', () => {
    const fit: RouteFitMetadata = {
      route: 'worker-export' as RenderRoute,
      fit: 'blocked',
      reason: 'route-unsupported' as RenderBlockerReason,
      message: 'Worker export is not supported for this effect',
    };
    expect(fit.fit).toBe('blocked');
    expect(fit.reason).toBe('route-unsupported');
    expect(fit.message).toBe('Worker export is not supported for this effect');
  });

  it('accepts degraded fit', () => {
    const fit: RouteFitMetadata = {
      route: 'sidecar-export' as RenderRoute,
      fit: 'degraded',
      reason: 'missing-contribution' as RenderBlockerReason,
    };
    expect(fit.fit).toBe('degraded');
  });

  it('accepts unknown fit', () => {
    const fit: RouteFitMetadata = {
      route: 'preview' as RenderRoute,
      fit: 'unknown',
    };
    expect(fit.fit).toBe('unknown');
  });
});

describe('M12: CapabilityRequirement is constructable', () => {
  const sourceRef: CapabilitySourceRef = {
    source: 'extension',
    extensionId: 'com.example.ext',
  };

  it('accepts minimal required fields', () => {
    const req: CapabilityRequirement = {
      id: 'req-1',
      sourceRef,
      route: 'browser-export' as RenderRoute,
      requiredCapabilities: ['browser-export'],
      determinism: 'deterministic' as DeterminismStatus,
    };
    expect(req.id).toBe('req-1');
    expect(req.sourceRef.source).toBe('extension');
    expect(req.route).toBe('browser-export');
    expect(req.requiredCapabilities).toEqual(['browser-export']);
    expect(req.determinism).toBe('deterministic');
  });

  it('accepts full fields with route-fit, version, findings, and blocking flag', () => {
    const finding: CapabilityFinding = {
      id: 'finding-1',
      severity: 'warning',
      route: 'browser-export' as RenderRoute,
      reason: 'unknown' as RenderBlockerReason,
      message: 'Capability not verified',
    };
    const req: CapabilityRequirement = {
      id: 'req-2',
      sourceRef,
      route: 'worker-export' as RenderRoute,
      requiredCapabilities: ['worker-export', 'sidecar-export'],
      determinism: 'process-dependent' as DeterminismStatus,
      routeFit: {
        route: 'worker-export' as RenderRoute,
        fit: 'blocked',
        reason: 'route-unsupported' as RenderBlockerReason,
        message: 'Not supported',
      },
      version: { semver: '2.0.0', declaredBy: 'com.example.ext' },
      findings: [finding],
      blocking: true,
    };
    expect(req.routeFit?.fit).toBe('blocked');
    expect(req.version?.semver).toBe('2.0.0');
    expect(req.findings).toHaveLength(1);
    expect(req.blocking).toBe(true);
  });

  it('accepts empty requiredCapabilities', () => {
    const req: CapabilityRequirement = {
      id: 'req-3',
      sourceRef: { source: 'built-in' },
      route: 'preview' as RenderRoute,
      requiredCapabilities: [],
      determinism: 'unknown' as DeterminismStatus,
    };
    expect(req.requiredCapabilities).toHaveLength(0);
  });
});

describe('M12: IntegrationCapabilities is constructable', () => {
  const sourceRef: CapabilitySourceRef = { source: 'extension', extensionId: 'com.example.ext' };
  const req: CapabilityRequirement = {
    id: 'req-1',
    sourceRef,
    route: 'browser-export' as RenderRoute,
    requiredCapabilities: ['browser-export'],
    determinism: 'deterministic' as DeterminismStatus,
  };

  it('accepts minimal fields with empty arrays', () => {
    const caps: IntegrationCapabilities = {
      routes: [],
      determinism: 'unknown' as DeterminismStatus,
      capabilityRequirements: [],
      sourceRefs: [],
      fullySupported: true,
      anyBlocked: false,
    };
    expect(caps.routes).toHaveLength(0);
    expect(caps.fullySupported).toBe(true);
    expect(caps.anyBlocked).toBe(false);
  });

  it('accepts scoped extension and contribution IDs', () => {
    const caps: IntegrationCapabilities = {
      extensionId: 'com.example.ext',
      contributionId: 'my-effect',
      routes: ['browser-export' as RenderRoute],
      determinism: 'deterministic' as DeterminismStatus,
      capabilityRequirements: [req],
      sourceRefs: [sourceRef],
      fullySupported: true,
      anyBlocked: false,
    };
    expect(caps.extensionId).toBe('com.example.ext');
    expect(caps.contributionId).toBe('my-effect');
    expect(caps.capabilityRequirements).toHaveLength(1);
  });

  it('accepts multiple routes and requirements', () => {
    const caps: IntegrationCapabilities = {
      routes: ['browser-export' as RenderRoute, 'worker-export' as RenderRoute],
      determinism: 'preview-only' as DeterminismStatus,
      capabilityRequirements: [req],
      sourceRefs: [sourceRef],
      fullySupported: false,
      anyBlocked: true,
    };
    expect(caps.routes).toHaveLength(2);
    expect(caps.anyBlocked).toBe(true);
  });
});

describe('M12: output, artifact, sampling, and process contracts are constructable', () => {
  const finding: CapabilityFinding = {
    id: 'finding-1',
    severity: 'info',
    route: 'browser-export' as RenderRoute,
    message: 'Collected during manifest construction',
  };

  const materialRef = {
    id: 'mat-main',
    mediaKind: 'video' as const,
    locator: { kind: 'asset-registry' as const, uri: 'asset://mat-main' },
    determinism: 'deterministic' as DeterminismStatus,
    replacementPolicy: 'preserve-live-ref' as const,
  };

  it('distinguishes compile-only and render-dependent output contributions', () => {
    const compileOnly: CompileOnlyOutputFormatContribution = {
      id: 'metadata-json' as any,
      kind: 'outputFormat',
      label: 'Metadata JSON',
      requiresRender: false,
      outputExtension: 'json',
      outputMimeType: 'application/json',
    };
    const renderDependent: RenderDependentOutputFormatContribution = {
      id: 'show-control' as any,
      kind: 'outputFormat',
      label: 'Show Control Package',
      requiresRender: true,
      outputExtension: 'zip',
      outputMimeType: 'application/zip',
      render: {
        routes: ['browser-export' as RenderRoute, 'sidecar-export' as RenderRoute],
        processId: 'show-control-process',
        operationId: 'export-show-control',
        requiredCapabilities: ['sidecar-export'],
        determinism: 'process-dependent' as DeterminismStatus,
      },
    };

    expect(compileOnly.requiresRender).toBe(false);
    expect(renderDependent.requiresRender).toBe(true);
    expect(renderDependent.render.processId).toBe('show-control-process');
  });

  it('keeps existing manifest acceptance for output formats and adds process contributions', () => {
    const ext = defineExtension({
      manifest: {
        id: 'com.m12.contracts' as any,
        version: '1.0.0',
        label: 'M12 Contracts',
        contributions: [
          {
            id: 'render-output' as any,
            kind: 'outputFormat',
            label: 'Rendered Output',
            requiresRender: true,
            outputExtension: 'mp4',
            render: {
              routes: ['browser-export' as RenderRoute],
              determinism: 'deterministic' as DeterminismStatus,
            },
          } satisfies RenderDependentOutputFormatContribution,
          {
            id: 'local-process' as any,
            kind: 'process',
            spec: {
              id: 'local-process',
              label: 'Local Process',
              spawn: {
                command: 'node',
                args: ['worker.js'],
                env: { NODE_ENV: 'test' },
              },
              protocol: 'stdio-jsonrpc',
              operations: [
                {
                  id: 'roundtrip',
                  label: 'Roundtrip',
                  outputKinds: ['material', 'sidecar'],
                  routes: ['sidecar-export' as RenderRoute],
                },
              ],
            },
          } satisfies ProcessContribution,
        ],
      },
    });

    const processContribution = ext.manifest.contributions![1] as ProcessContribution;
    expect(ext.manifest.contributions).toHaveLength(2);
    expect(processContribution.kind).toBe('process');
    expect(Object.isFrozen(ext.manifest.contributions)).toBe(true);
    expect(Object.isFrozen(processContribution)).toBe(true);
    expect(Object.isFrozen(processContribution.spec)).toBe(true);
    expect(Object.isFrozen(processContribution.spec.spawn)).toBe(true);
    expect(Object.isFrozen(processContribution.spec.spawn.args!)).toBe(true);
    expect(Object.isFrozen(processContribution.spec.operations!)).toBe(true);
    expect(Object.isFrozen(processContribution.spec.operations![0])).toBe(true);
  });

  it('constructs artifact manifests and sidecar descriptors', () => {
    const sidecar: RenderArtifactSidecarDescriptor = {
      filename: 'manifest.provenance.json',
      mimeType: 'application/json',
      kind: 'provenance',
      byteSize: 42,
      renderGroupId: 'group-main',
      passName: 'beauty',
    };
    const manifest: RenderArtifactManifest = {
      id: 'manifest-1',
      schemaVersion: 1,
      artifactId: 'artifact-1',
      route: 'browser-export' as RenderRoute,
      determinism: 'deterministic' as DeterminismStatus,
      producerExtensionId: 'com.example.render',
      producerVersion: '1.0.0',
      outputFormatId: 'show-control',
      consumedMaterialRefs: [materialRef],
      sidecars: [sidecar],
      diagnostics: [finding],
      inputHashes: { 'asset://mat-main': 'sha256:abc' },
      renderGroupId: 'group-main',
      passName: 'beauty',
    };

    expect(manifest.sidecars[0].kind).toBe('provenance');
    expect(manifest.consumedMaterialRefs[0].id).toBe('mat-main');
    expect(manifest.inputHashes!['asset://mat-main']).toBe('sha256:abc');
  });

  it('constructs sampling config and result vocabulary', () => {
    const config: SamplingConfig = {
      id: 'dataset-config',
      strategy: 'clip-slices',
      sources: [{ kind: 'clip', id: 'clip-1', clipId: 'clip-1' }],
      range: { startFrame: 0, endFrame: 48 },
      fps: 24,
      resolution: '1920x1080',
      includeLabels: true,
      includeCaptions: true,
      includeProvenance: true,
      attachments: [{ kind: 'cue', sidecarKind: 'cue', required: true }],
    };
    const result: SamplingResult = {
      configId: 'dataset-config',
      items: [
        {
          id: 'sample-1',
          sourceRef: config.sources[0],
          range: config.range,
          frame: 24,
          timestampSeconds: 1,
          manifestEntryId: 'manifest-entry-1',
        },
      ],
      manifestRefs: ['manifest-entry-1'],
      diagnostics: [finding],
    };

    expect(config.strategy).toBe('clip-slices');
    expect(result.items[0].timestampSeconds).toBe(1);
    expect(result.manifestRefs).toEqual(['manifest-entry-1']);
  });

  it('constructs render-group pass summaries', () => {
    const pass: TimelineRenderPassSummary = {
      id: 'group-main.beauty',
      passName: 'beauty',
      required: true,
      composable: true,
      materialRefId: 'mat-main',
      status: 'resolved',
    };
    expect(pass.required).toBe(true);
    expect(pass.status).toBe('resolved');
  });

  it('constructs process specs, statuses, and roundtrip request/results', () => {
    const spec: ProcessSpec = {
      id: 'blender-mcp',
      label: 'Blender MCP',
      spawn: { command: 'blender-mcp', args: ['--stdio'] },
      protocol: 'stdio-jsonrpc',
      healthCheck: 'ping',
      operations: [{ id: 'render-pass', label: 'Render Pass', outputKinds: ['material', 'sidecar'] }],
    };
    const statuses: ProcessStatus[] = [
      { processId: spec.id, state: 'not-installed', installHint: 'Install blender-mcp' },
      { processId: spec.id, state: 'stopped' },
      { processId: spec.id, state: 'starting', startedAt: '2026-06-20T00:00:00.000Z' },
      { processId: spec.id, state: 'ready', pid: 1234 },
      {
        processId: spec.id,
        state: 'busy',
        operationId: 'render-pass',
        progress: { operationId: 'render-pass', percent: 50 },
      },
      { processId: spec.id, state: 'degraded', healthCheck: 'ping', diagnostics: [{ severity: 'warning', code: 'process/slow', message: 'Slow health check' }] },
      { processId: spec.id, state: 'failed', errorCode: 'spawn-failed', recoverable: true },
      { processId: spec.id, state: 'stopping', reason: 'user-requested' },
    ];
    const request: ProcessRoundtripRequest = {
      id: 'roundtrip-1',
      processId: spec.id,
      operationId: 'render-pass',
      inputMaterialRefs: [materialRef],
      params: { passName: 'beauty' },
      frameRange: { startFrame: 0, endFrame: 24 },
      renderGroupId: 'group-main',
      passNames: ['beauty'],
    };
    const result: ProcessRoundtripResult = {
      requestId: request.id,
      processId: spec.id,
      operationId: request.operationId,
      status: 'completed',
      returnedMaterials: [
        {
          ...materialRef,
          durationSeconds: 1,
          metadata: { passName: 'beauty', renderGroupId: 'group-main' },
        },
      ],
      sidecars: [{ filename: 'render.log', mimeType: 'text/plain', kind: 'log' }],
      availableActions: ['insert-as-clip', 'create-proposal'],
    };

    expect(statuses.map((status) => status.state)).toEqual([
      'not-installed',
      'stopped',
      'starting',
      'ready',
      'busy',
      'degraded',
      'failed',
      'stopping',
    ]);
    expect(request.passNames).toEqual(['beauty']);
    expect(result.returnedMaterials[0].metadata!.passName).toBe('beauty');
  });
});

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function validManifest(): ExtensionManifest {
  return {
    id: 'com.example.test' as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
  };
}
