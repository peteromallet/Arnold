import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { useRenderState } from '@/tools/video-editor/hooks/useRenderState';
import { createProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type { ExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface';
import {
  EffectRegistryProvider,
  useEffectRegistryContext,
} from '@/tools/video-editor/effects/registry/EffectRegistryContext';
import type {
  EffectRegistry,
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry';
import {
  DataProviderContext,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext';
import { createDiagnosticCollection } from '@reigh/editor-sdk';
import type { RenderPlannerResult } from '@/tools/video-editor/runtime/renderPlanner';

const mocks = vi.hoisted(() => ({
  startClientRender: vi.fn(),
}));

const renderPlannerMocks = vi.hoisted(() => ({
  buildExportReadinessPlan: vi.fn(),
  planRender: vi.fn(),
}));

vi.mock('@/tools/video-editor/runtime/renderPlanner', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/runtime/renderPlanner')>(
    '@/tools/video-editor/runtime/renderPlanner',
  );
  renderPlannerMocks.buildExportReadinessPlan.mockImplementation(actual.buildExportReadinessPlan);
  renderPlannerMocks.planRender.mockImplementation(actual.planRender);
  return {
    ...actual,
    buildExportReadinessPlan: renderPlannerMocks.buildExportReadinessPlan,
    planRender: renderPlannerMocks.planRender,
  };
});

function makePlannerResult(blockers: RenderPlannerResult['blockers'] = []): RenderPlannerResult {
  const routes = ['preview', 'browser-export', 'worker-export', 'sidecar-export'] as const;
  return {
    guard: {
      diagnostics: [],
      findings: [],
      blockers,
      unknownClipTypes: [],
      unknownEffects: [],
      unknownTransitions: [],
      inactiveExtensionIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      hasBlockingErrors: blockers.length > 0,
    },
    findings: blockers,
    blockers,
    routes: routes.map((route) => ({
      route,
      blockerCount: blockers.filter((blocker) => blocker.route === route).length,
      findingCount: blockers.filter((blocker) => blocker.route === route).length,
      blocked: blockers.some((blocker) => blocker.route === route),
    })),
    routePlans: routes.map((route) => ({
      route,
      blockerCount: blockers.filter((blocker) => blocker.route === route).length,
      findingCount: blockers.filter((blocker) => blocker.route === route).length,
      blocked: blockers.some((blocker) => blocker.route === route),
      requiredCapabilities: [],
      determinism: 'deterministic',
      blockers: blockers.filter((blocker) => blocker.route === route),
      diagnostics: blockers.filter((blocker) => blocker.route === route),
      outputFormatIds: [],
      processRequirements: [],
      nextActions: [],
      artifactCompletion: {
        status: 'complete',
        requiredProfiles: [],
        completeProfiles: [],
        incompleteProfiles: [],
        blockedProfiles: [],
        profiles: [],
      },
    })),
    diagnostics: blockers,
    nextActions: [],
    canBrowserExport: !blockers.some((blocker) => blocker.route === 'browser-export'),
    canWorkerExport: !blockers.some((blocker) => blocker.route === 'worker-export'),
    canSidecarExport: !blockers.some((blocker) => blocker.route === 'sidecar-export'),
  };
}

const renderRouterMocks = vi.hoisted(() => ({
  decideRenderRoute: vi.fn((timeline: ResolvedTimelineConfig | null | undefined) => {
    const clip = timeline?.clips?.[0];
    if (clip?.generation?.sequence_lane === 'remotion_module' && !clip?.generation?.artifact_id) {
      const message = `Generated remotion_module clip "${clip.id}" is missing artifact metadata.`;
      return {
        route: 'preview-only',
        hasThemedClip: false,
        hasMediaClip: false,
        hasContributedClip: false,
        reason: 'remotion_module_missing_artifact',
        planner: {
          selectedPlannerRoute: 'preview',
          plannerResult: makePlannerResult([
            {
              id: `router.generatedModule.${clip.id}.missingArtifact.preview`,
              severity: 'error',
              route: 'preview',
              reason: 'missing-material',
              message,
              clipId: clip.id,
              detail: {
                source: 'render-router',
                legacyReason: 'remotion_module_missing_artifact',
              },
            },
          ]),
        },
      };
    }

    if (clip?.clipType === 'generated-module') {
      return {
        route: 'worker-banodoco',
        hasThemedClip: false,
        hasMediaClip: false,
        hasContributedClip: false,
        reason: 'generated_remotion_module',
        planner: {
          selectedPlannerRoute: 'worker-export',
          plannerResult: makePlannerResult(),
        },
      };
    }

    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: true,
      hasContributedClip: false,
      reason: 'pure_native_clips',
      planner: {
        selectedPlannerRoute: 'browser-export',
        plannerResult: makePlannerResult(),
      },
    };
  }),
}));

vi.mock('@/tools/video-editor/hooks/useClientRender', () => ({
  useClientRender: () => mocks.startClientRender,
}));

vi.mock('@/tools/video-editor/lib/renderRouter', () => ({
  decideRenderRoute: renderRouterMocks.decideRenderRoute,
}));

const guardMocks = vi.hoisted(() => ({
  collectBuiltInKnownIds: vi.fn(),
  collectExtensionDeclaredIds: vi.fn(),
  hasTimelineShaderMetadata: vi.fn(),
  scanExportConfig: vi.fn(),
}));

vi.mock('@/tools/video-editor/runtime/exportGuard', () => ({
  collectBuiltInKnownIds: guardMocks.collectBuiltInKnownIds,
  collectExtensionDeclaredIds: guardMocks.collectExtensionDeclaredIds,
  hasTimelineShaderMetadata: guardMocks.hasTimelineShaderMetadata,
  scanExportConfig: guardMocks.scanExportConfig,
}));

const buildConfig = (clip: ResolvedTimelineConfig['clips'][number]): ResolvedTimelineConfig => ({
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'out.mp4',
  },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips: [clip],
  registry: {},
});

function makeProcessAttachRecord() {
  return createProcessResultAttachRecord({
    processDescriptor: {
      id: 'proc.descriptor',
      extensionId: 'ext.process',
      processId: 'dataset-process',
      label: 'Dataset Process',
      description: 'Produces attached refs.',
      protocol: 'stdio-jsonrpc',
      availableRoutes: ['browser-export'],
      operations: [
        {
          id: 'exportDataset',
          label: 'Export Dataset',
          routes: ['browser-export'],
          outputKinds: ['material', 'artifact'],
          requiredCapabilities: ['browser-export'],
          determinism: 'process-dependent',
        },
      ],
      requiredBy: [{ source: 'extension', extensionId: 'ext.process', contributionId: 'proc.descriptor' }],
      capabilities: { defaultRoute: 'browser-export', determinism: 'process-dependent', capabilityRequirements: [] },
      blockers: [],
      nextActions: [],
      spec: {
        id: 'dataset-process',
        label: 'Dataset Process',
        version: { semver: '1.0.0', declaredBy: 'ext.process', contributionId: 'proc.descriptor' },
      },
    } as any,
    attachedAt: '2026-07-04T22:30:00.000Z',
    result: {
      requestId: 'request-1',
      processId: 'dataset-process',
      operationId: 'exportDataset',
      status: 'completed',
      returnedMaterials: [{
        id: 'mat-attached',
        mediaKind: 'video',
        locator: { kind: 'provider', uri: 'provider://materials/mat-attached' },
        determinism: 'process-dependent',
        replacementPolicy: 'materialize-on-export',
        producerExtensionId: 'ext.shader',
        provenance: {
          contributionId: 'ext.shader.clip',
          shaderId: 'shader.preview.clip',
        },
      }],
      artifacts: [{
        id: 'artifact-1',
        route: 'browser-export',
        determinism: 'process-dependent',
        mediaKind: 'video',
        locator: { kind: 'provider', uri: 'provider://artifacts/artifact-1' },
        consumedMaterialRefs: [],
        findings: [],
      }],
      diagnostics: [],
      logs: [],
      availableActions: [],
    } as any,
  });
}

function emptyExtensionRuntime(): ExtensionRuntime {
  const config = {
    slots: {},
    dialogHost: { dialogs: [] },
    registry: { panels: [], inspectorSections: [] },
    overlays: [],
    assetParsers: [],
    outputFormats: [],
    processes: [],
    searchProviders: [],
    metadataFacets: [],
    assetDetailSections: [],
    effects: [],
    transitions: [],
    shaders: [],
    agentTools: [],
  } as ExtensionRuntime['config'];

  return {
    config,
    extensions: [],
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set(),
    contributionIndex: {},
    compositionGraph: {
      nodes: [{ id: 'timeline-postprocess', kind: 'timeline-postprocess', detail: { scope: 'postprocess' } }],
      edges: [],
      referenceStates: [],
      diagnostics: [],
    },
    settingsDefaults: {},
    assetParsers: config.assetParsers,
    outputFormats: config.outputFormats,
    processes: config.processes,
    searchProviders: config.searchProviders,
    metadataFacets: config.metadataFacets,
    assetDetailSections: config.assetDetailSections,
    effects: config.effects,
    transitions: config.transitions,
    shaders: config.shaders,
    agentTools: config.agentTools,
    requirements: [],
    packageStateInventory: [],
  };
}

function makeExtensionRuntime(overrides?: Partial<ExtensionRuntime>): ExtensionRuntime {
  const config = (overrides?.config ?? {
    slots: {},
    dialogHost: { dialogs: [] },
    registry: { panels: [], inspectorSections: [] },
    overlays: [],
    assetParsers: [],
    outputFormats: [],
    processes: [],
    searchProviders: [],
    metadataFacets: [],
    assetDetailSections: [],
    effects: [],
    transitions: [],
    shaders: [],
    agentTools: [],
  }) as ExtensionRuntime['config'];

  return {
    config,
    extensions: [],
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set(),
    contributionIndex: {},
    compositionGraph: {
      nodes: [{ id: 'timeline-postprocess', kind: 'timeline-postprocess', detail: { scope: 'postprocess' } }],
      edges: [],
      referenceStates: [],
      diagnostics: [],
    },
    settingsDefaults: {},
    assetParsers: overrides?.assetParsers ?? config.assetParsers,
    outputFormats: overrides?.outputFormats ?? config.outputFormats,
    processes: overrides?.processes ?? config.processes,
    searchProviders: overrides?.searchProviders ?? config.searchProviders,
    metadataFacets: overrides?.metadataFacets ?? config.metadataFacets,
    assetDetailSections: overrides?.assetDetailSections ?? config.assetDetailSections,
    effects: overrides?.effects ?? config.effects,
    transitions: overrides?.transitions ?? config.transitions,
    shaders: overrides?.shaders ?? config.shaders,
    agentTools: overrides?.agentTools ?? config.agentTools,
    requirements: [],
    packageStateInventory: [],
    ...overrides,
  };
}

function makeTimelineWithEffect(effectId: string): ResolvedTimelineConfig {
  return buildConfig({
    id: 'clip-with-effect',
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 1,
    continuous: {
      type: effectId,
      params: {},
    },
  } as ResolvedTimelineConfig['clips'][number]);
}

function makeEffectRecord(
  effectId: string,
  capabilityStatus: 'supported' | 'blocked' = 'supported',
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `contrib.${effectId}`,
    component: ({ children }) => children,
    provenance: 'trusted-loader',
    ownerExtensionId: 'provider-ext',
    status: 'active',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: capabilityStatus,
          determinism: 'deterministic',
          ...(capabilityStatus === 'blocked'
            ? {
                blockerReason: 'route-unsupported',
                message: `Effect "${effectId}" cannot browser-export.`,
              }
            : {}),
        },
      ],
    },
  };
}

let capturedRegistry: EffectRegistry | null = null;

function CaptureRegistry({ children }: { children: ReactNode }) {
  capturedRegistry = useEffectRegistryContext().registry;
  return <>{children}</>;
}

function RegistryWrapper({ children }: { children: ReactNode }) {
  return (
    <EffectRegistryProvider>
      <CaptureRegistry>{children}</CaptureRegistry>
    </EffectRegistryProvider>
  );
}

function nonEmptyExtensionRuntime(): ExtensionRuntime {
  return makeExtensionRuntime({
    extensions: [
      {
        manifest: {
          id: 'provider-ext' as any,
          version: '1.0.0',
          contributions: [],
        },
      } as any,
    ],
  });
}

function cleanGuardResult() {
  return {
    diagnostics: [],
    findings: [],
    blockers: [],
    unknownClipTypes: [],
    unknownEffects: [],
    unknownTransitions: [],
    inactiveExtensionIds: {
      effectIds: new Set(),
      transitionIds: new Set(),
      clipTypeIds: new Set(),
    },
    hasBlockingErrors: false,
  };
}

function installSnapshotAwareGuardMock() {
  guardMocks.collectBuiltInKnownIds.mockReturnValue({
    clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
    effectTypes: new Set(),
    transitionTypes: new Set(),
  });
  guardMocks.collectExtensionDeclaredIds.mockReturnValue({
    effectIds: new Set(),
    transitionIds: new Set(),
    clipTypeIds: new Set(),
  });
  guardMocks.scanExportConfig.mockImplementation((
    config: ResolvedTimelineConfig | null,
    _builtIn: unknown,
    _extIds: unknown,
    snapshot?: EffectRegistrySnapshot,
  ) => {
    const effectId = (config?.clips[0]?.continuous as { type?: string } | undefined)?.type;
    const record = effectId ? snapshot?.get(effectId) : undefined;

    if (!effectId || !record) {
      return {
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: `Continuous effect "${effectId ?? 'unknown'}" is not recognised. Ensure the required extension or registry is installed.`,
            detail: { clipId: 'clip-with-effect', effectType: effectId },
          },
        ],
        unknownEffects: effectId ? [effectId] : [],
        hasBlockingErrors: true,
      };
    }

    const browserExport = record.renderability.capabilities.find((capability) => capability.route === 'browser-export');
    if (browserExport?.status !== 'supported') {
      return {
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unrenderable-effect',
            message: browserExport?.message ?? `Continuous effect "${effectId}" is registered but does not support browser export.`,
            detail: {
              clipId: 'clip-with-effect',
              effectType: effectId,
              renderRoute: 'browser-export',
            },
          },
        ],
        hasBlockingErrors: true,
      };
    }

    return cleanGuardResult();
  });
}

// ---------------------------------------------------------------------------
// Pre-existing routing tests (with no extensionRuntime — guard skipped)
// ---------------------------------------------------------------------------

describe('useRenderState render routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
    guardMocks.collectBuiltInKnownIds.mockReturnValue({
      clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
      effectTypes: new Set(['fade', 'slide-up']),
      transitionTypes: new Set(['crossfade']),
    });
    guardMocks.collectExtensionDeclaredIds.mockReturnValue({
      effectIds: new Set(),
      transitionIds: new Set(),
      clipTypeIds: new Set(),
    });
    guardMocks.scanExportConfig.mockReturnValue({
      diagnostics: [],
      unknownClipTypes: [],
      unknownEffects: [],
      unknownTransitions: [],
      inactiveExtensionIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      hasBlockingErrors: false,
    });
  });

  it('invokes the client renderer only for client-route timelines', async () => {
    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    expect(result.current.renderStatus).toBe('idle');
  });

  it('uses an injected exporter instead of the client renderer when one is supplied', async () => {
    const exporter = {
      render: vi.fn(async () => ({
        id: 'job-1',
        subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
          listener({
            phase: 'complete',
            progress: 1,
            resultUrl: 'blob:https://example.com/rendered',
            log: 'done',
          });
          return () => undefined;
        },
      })),
    };

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      {
        fps: 30,
        durationInFrames: 30,
        compositionWidth: 1920,
        compositionHeight: 1080,
      },
      exporter,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(exporter.render).toHaveBeenCalledTimes(1);
    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('done');
    expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    expect(result.current.renderResultFilename).toBe('out.mp4');
  });

  it('records a concise render log when an injected exporter fails without progress text', async () => {
    const exporter = {
      render: vi.fn(async () => ({
        id: 'job-1',
        subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
          listener({
            phase: 'failed',
            progress: 0.4,
          });
          return () => undefined;
        },
      })),
    };

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      {
        fps: 30,
        durationInFrames: 30,
        compositionWidth: 1920,
        compositionHeight: 1080,
      },
      exporter,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(exporter.render).toHaveBeenCalledTimes(1);
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toBe('Render failed during execution.');
  });

  it('routes render-router load failures through planner diagnostics', async () => {
    const collection = createDiagnosticCollection();
    const runtimeValue = {
      diagnosticCollection: collection,
    } as unknown as VideoEditorRuntimeContextValue;
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DataProviderContext.Provider value={runtimeValue}>
        {children}
      </DataProviderContext.Provider>
    );
    renderRouterMocks.decideRenderRoute.mockImplementationOnce(() => {
      throw new Error('dynamic import failed');
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
    ), { wrapper });

    await act(async () => {
      await result.current.startRender();
    });

    const plannerDiagnostic = collection.getSnapshot().find(
      (diagnostic) => diagnostic.detail?.source === 'render-planner',
    );
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toBe('Render routing unavailable: dynamic import failed');
    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(plannerDiagnostic).toBeDefined();
    expect(plannerDiagnostic).toMatchObject({
      severity: 'error',
      code: 'planner/browser-export/route-unsupported',
      message: 'Render routing unavailable: dynamic import failed',
    });
    expect(plannerDiagnostic?.detail).toMatchObject({
      phase: 'dynamic-import',
      route: 'browser-export',
      reason: 'route-unsupported',
    });
    expect(renderPlannerMocks.planRender).toHaveBeenCalledWith(expect.objectContaining({
      diagnostics: expect.arrayContaining([
        expect.objectContaining({
          id: 'planner.renderRouter.dynamicImportFailure',
          route: 'browser-export',
          reason: 'route-unsupported',
          message: 'Render routing unavailable: dynamic import failed',
          detail: expect.objectContaining({
            source: 'render-router-import',
            phase: 'dynamic-import',
            errorName: 'Error',
          }),
        }),
      ]),
    }));
  });

  it('preserves injected exporter failed progress text in the render log', async () => {
    const exporter = {
      render: vi.fn(async () => ({
        id: 'job-1',
        subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
          listener({
            phase: 'failed',
            progress: 0.7,
            log: 'Encoder exited with code 42.',
          });
          return () => undefined;
        },
      })),
    };

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      {
        fps: 30,
        durationInFrames: 30,
        compositionWidth: 1920,
        compositionHeight: 1080,
      },
      exporter,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(exporter.render).toHaveBeenCalledTimes(1);
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toBe('Encoder exited with code 42.');
  });

  it('blocks malformed remotion_module metadata without invoking the client renderer', async () => {
    const collection = createDiagnosticCollection();
    const runtimeValue = {
      diagnosticCollection: collection,
    } as unknown as VideoEditorRuntimeContextValue;
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DataProviderContext.Provider value={runtimeValue}>
        {children}
      </DataProviderContext.Provider>
    );

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-bad',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
        },
      }),
      null,
    ), { wrapper });

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    const plannerDiagnostic = collection.getSnapshot().find(
      (diagnostic) => diagnostic.detail?.source === 'render-planner',
    );
    expect(plannerDiagnostic).toBeDefined();
    expect(plannerDiagnostic?.detail).toMatchObject({
      legacyReason: 'remotion_module_missing_artifact',
      providerRoute: 'preview-only',
    });
    expect(result.current.renderLog).toBe(plannerDiagnostic?.message);
  });

  it('surfaces worker-unavailable state for valid remotion_module routes without client fallback', async () => {
    const collection = createDiagnosticCollection();
    const runtimeValue = {
      diagnosticCollection: collection,
    } as unknown as VideoEditorRuntimeContextValue;
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DataProviderContext.Provider value={runtimeValue}>
        {children}
      </DataProviderContext.Provider>
    );

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-good',
        clipType: 'generated-module',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }),
      null,
    ), { wrapper });

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    const plannerDiagnostic = collection.getSnapshot().find(
      (diagnostic) => diagnostic.detail?.source === 'render-planner',
    );
    expect(plannerDiagnostic).toBeDefined();
    expect(plannerDiagnostic?.detail).toMatchObject({
      legacyReason: 'generated_remotion_module',
      providerRoute: 'worker-banodoco',
    });
    expect(result.current.renderLog).toBe(plannerDiagnostic?.message);
  });

  it('surfaces generated-module preview blocks from router planner context', async () => {
    const plannerMessage = 'Planner context says generated module artifact "artifact-missing" is absent.';
    renderRouterMocks.decideRenderRoute.mockImplementationOnce(() => ({
      route: 'preview-only',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: false,
      reason: 'remotion_module_missing_artifact',
      planner: {
        selectedPlannerRoute: 'preview',
        plannerResult: makePlannerResult([
          {
            id: 'router.generatedModule.clip-module-bad.missingArtifact.preview',
            severity: 'error',
            route: 'preview',
            reason: 'missing-material',
            message: plannerMessage,
            clipId: 'clip-module-bad',
            detail: {
              source: 'render-router',
              legacyReason: 'remotion_module_missing_artifact',
            },
          },
        ]),
      },
    }));

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-bad',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
        },
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain(plannerMessage);
    expect(result.current.renderLog).not.toContain('Render route "remotion_module_missing_artifact" is not exportable.');
    expect(mocks.startClientRender).not.toHaveBeenCalled();
  });

  it('uses planner blocker text for worker provider unavailability', async () => {
    const plannerMessage = 'Planner worker blocker text from route availability.';
    renderPlannerMocks.planRender.mockReturnValueOnce(makePlannerResult([
      {
        id: 'planner.request.worker-export.worker-banodoco.unavailable',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
        message: plannerMessage,
        detail: {
          source: 'render-request',
          routeAvailability: 'unavailable',
          providerId: 'worker-banodoco',
        },
      },
    ]));

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-good',
        clipType: 'generated-module',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain(plannerMessage);
    expect(result.current.renderLog).not.toContain('Render provider unavailable');
    expect(renderPlannerMocks.planRender).toHaveBeenCalledWith(expect.objectContaining({
      request: expect.objectContaining({
        route: 'worker-export',
        routeAvailability: [
          expect.objectContaining({
            route: 'worker-export',
            available: false,
            providerId: 'worker-banodoco',
          }),
        ],
      }),
    }));
    expect(mocks.startClientRender).not.toHaveBeenCalled();
  });

  it('uses planner blocker text for external provider unavailability', async () => {
    const plannerMessage = 'Planner sidecar blocker text from route availability.';
    renderRouterMocks.decideRenderRoute.mockImplementationOnce(() => ({
      route: 'external',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: false,
      reason: 'external_provider_required',
      planner: {
        selectedPlannerRoute: 'sidecar-export',
        plannerResult: makePlannerResult(),
      },
    }));
    renderPlannerMocks.planRender.mockReturnValueOnce(makePlannerResult([
      {
        id: 'planner.request.sidecar-export.external.unavailable',
        severity: 'error',
        route: 'sidecar-export',
        reason: 'route-unsupported',
        message: plannerMessage,
        detail: {
          source: 'render-request',
          routeAvailability: 'unavailable',
          providerId: 'external',
        },
      },
    ]));

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-external',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain(plannerMessage);
    expect(result.current.renderLog).not.toContain('Render provider unavailable');
    expect(renderPlannerMocks.planRender).toHaveBeenCalledWith(expect.objectContaining({
      request: expect.objectContaining({
        route: 'sidecar-export',
        routeAvailability: [
          expect.objectContaining({
            route: 'sidecar-export',
            available: false,
            providerId: 'external',
          }),
        ],
      }),
    }));
    expect(mocks.startClientRender).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Export guard tests
// ---------------------------------------------------------------------------

describe('useRenderState export guard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
  });

  describe('empty-runtime fast path', () => {
    it('skips guard work when extensionRuntime is undefined', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.collectExtensionDeclaredIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      // Native routing preserved
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('skips guard work when extensionRuntime is empty (no extensions, no inactive reserved)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.collectExtensionDeclaredIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      // Native routing preserved
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('does not let timeline shader preview metadata bypass export readiness', async () => {
      const message = 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".';
      guardMocks.hasTimelineShaderMetadata.mockReturnValueOnce(true);
      guardMocks.scanExportConfig.mockReturnValue({
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unrenderable-shader',
            message,
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip',
            detail: {
              clipId: 'c1',
              shaderId: 'shader.preview.clip',
              shaderScope: 'clip',
              renderRoute: 'browser-export',
            },
          },
        ],
        blockers: [
          {
            id: 'export.shader.clip.c1.shader.preview.clip.browser-export.missing-materializer',
            severity: 'error',
            route: 'browser-export',
            reason: 'missing-material',
            message,
            clipId: 'c1',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip',
            detail: {
              shaderId: 'shader.preview.clip',
              shaderScope: 'clip',
            },
          },
        ],
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
          app: {
            shader: {
              scope: 'clip',
              extensionId: 'ext.shader',
              contributionId: 'ext.shader.clip',
              shaderId: 'shader.preview.clip',
            },
          },
        }),
        null,
        null,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain(message);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('skips guard work when resolvedConfig is null even with extensions', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      const { result } = renderHook(() => useRenderState(
        null, // no config
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked (null config = nothing to scan)
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
    });

    it('skips guard work when resolvedConfig has zero clips even with extensions', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      const emptyConfig: ResolvedTimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [],
        clips: [],
        registry: {},
      };

      const { result } = renderHook(() => useRenderState(
        emptyConfig,
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
    });
  });

  describe('export guard — blocking errors', () => {
    it('blocks render when export guard finds blocking errors (truly unknown clip type)', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      // Setup guard to return a blocking error
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-clip-type',
            message: 'Clip type "alien-format" is not recognised.',
            detail: { clipId: 'c1', clipType: 'alien-format' },
          },
        ],
        unknownClipTypes: ['alien-format'],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Render was blocked
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export readiness blocked by the render planner');
      expect(result.current.renderLog).toContain('alien-format');
      // Native routing was preserved — client render was NOT invoked
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(renderPlannerMocks.buildExportReadinessPlan).toHaveBeenCalledTimes(1);
    });

    it('blocks exporter render too when guard finds blocking errors', async () => {
      const exporter = {
        render: vi.fn(),
      };

      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "crazy-spin" is not recognised.',
            detail: { clipId: 'c1', effectType: 'crazy-spin' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: ['crazy-spin'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        exporter as any,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export readiness blocked by the render planner');
      expect(result.current.renderLog).toContain('crazy-spin');
      expect(exporter.render).not.toHaveBeenCalled();
    });

    it('blocks with concise structured diagnostics in render log', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-clip-type',
            message: 'Clip type "alien-format" is not recognised.',
            detail: { clipId: 'c1', clipType: 'alien-format' },
          },
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "star-wipe" is declared by an inactive extension.',
            detail: { clipId: 'c2', transitionType: 'star-wipe' },
          },
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Continuous effect "hyperspace" is not recognised.',
            detail: { clipId: 'c3', effectType: 'hyperspace' },
          },
        ],
        unknownClipTypes: ['alien-format'],
        unknownEffects: ['hyperspace'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(['star-wipe']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      const log = result.current.renderLog;
      expect(log).toContain('Export readiness blocked by the render planner');
      expect(log).toContain('[browser-export/missing-contribution]');
      expect(log).toContain('alien-format');
      expect(log).toContain('hyperspace');
      expect(log).not.toContain('star-wipe');
    });

    it('publishes export and planner diagnostics to the provider collection during guard execution', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });
      const collection = createDiagnosticCollection();
      const runtimeValue = {
        diagnosticCollection: collection,
      } as unknown as VideoEditorRuntimeContextValue;
      const wrapper = ({ children }: { children: ReactNode }) => (
        <DataProviderContext.Provider value={runtimeValue}>
          {children}
        </DataProviderContext.Provider>
      );

      guardMocks.scanExportConfig.mockReturnValue({
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Continuous effect "hyperspace" is not recognised.',
            detail: { clipId: 'c1', effectType: 'hyperspace' },
          },
        ],
        blockers: [
          {
            id: 'export.effect.c1.continuous.hyperspace.missing',
            severity: 'error',
            route: 'browser-export',
            reason: 'missing-contribution',
            message: 'Continuous effect "hyperspace" is not recognised.',
            clipId: 'c1',
            detail: { effectType: 'hyperspace', slot: 'continuous' },
          },
        ],
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ), { wrapper });

      await act(async () => {
        await result.current.startRender();
      });

      const diagnostics = collection.getSnapshot();
      expect(diagnostics.some((diagnostic) => diagnostic.detail?.source === 'export-guard')).toBe(true);
      expect(diagnostics.some((diagnostic) => diagnostic.detail?.source === 'render-planner')).toBe(true);
    });

    it('uses planner blockers as the canonical render readiness decision', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        ...cleanGuardResult(),
        diagnostics: [],
        blockers: [
          {
            id: 'planner.compat.effect.browser-export.missing',
            severity: 'error',
            route: 'browser-export',
            reason: 'missing-contribution',
            message: 'Planner says the effect contribution is missing.',
          },
        ],
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('feeds guard scan output to planner readiness before blocking render', async () => {
      const plannerMessage = 'Planner readiness blocks the timeline after reading guard input.';
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });
      const guardResult = {
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'warning' as const,
            code: 'export/provider-warning',
            message: 'Guard scan found provider context.',
            detail: { clipId: 'c1', providerId: 'provider-a' },
          },
        ],
        hasBlockingErrors: false,
      };

      guardMocks.scanExportConfig.mockReturnValue(guardResult);
      renderPlannerMocks.buildExportReadinessPlan.mockReturnValueOnce(makePlannerResult([
        {
          id: 'planner.provider.browser-export.blocked',
          severity: 'error',
          route: 'browser-export',
          reason: 'route-unsupported',
          message: plannerMessage,
          detail: {
            source: 'render-planner',
            providerId: 'provider-a',
          },
        },
      ]));

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      expect(renderPlannerMocks.buildExportReadinessPlan).toHaveBeenCalledWith(expect.objectContaining({
        guard: guardResult,
        extensionRuntime: extRuntime,
      }));
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain(plannerMessage);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('does not use raw guard diagnostic text when planner blockers exist', async () => {
      const rawGuardMessage = 'RAW GUARD DIAGNOSTIC SHOULD STAY OUT OF THE USER LOG';
      const plannerMessage = 'Planner blocker says the export contribution is missing.';
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        ...cleanGuardResult(),
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: rawGuardMessage,
            detail: { clipId: 'c1', effectType: 'raw-effect' },
          },
        ],
        hasBlockingErrors: true,
      });
      renderPlannerMocks.buildExportReadinessPlan.mockReturnValueOnce(makePlannerResult([
        {
          id: 'planner.compat.effect.browser-export.missing',
          severity: 'error',
          route: 'browser-export',
          reason: 'missing-contribution',
          message: plannerMessage,
          detail: {
            source: 'render-planner',
            effectType: 'raw-effect',
          },
        },
      ]));

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain(plannerMessage);
      expect(result.current.renderLog).not.toContain(rawGuardMessage);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });
  });

  describe('export guard — warnings only (preserve native routing)', () => {
    it('allows render when only extension-declared (inactive) warnings are present', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [
                {
                  id: 'contrib.future' as any,
                  kind: 'transition' as any,
                  transitionId: 'future-transition',
                },
              ],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "future-transition" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', transitionType: 'future-transition' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(['future-transition']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Native routing preserved — client render invoked
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderLog).toBe('');
    });

    it('allows render when guard finds no issues at all', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderLog).toBe('');
    });
  });

  describe('export guard — native routing preservation', () => {
    it('preserves existing preview-only block when guard passes', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      // Guard passes — no blocking errors
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-module-bad',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
          },
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard passed but preview-only blocked it — native routing preserved
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Render blocked');
      expect(result.current.renderLog).toContain('missing artifact metadata');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('passes extension contributions to collectExtensionDeclaredIds', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'ext-a' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c1' as any, kind: 'effect' as any, effectId: 'my-effect' },
                { id: 'c2' as any, kind: 'transition' as any, transitionId: 'my-transition' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['my-effect']),
        transitionIds: new Set(['my-transition']),
        clipTypeIds: new Set(),
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // collectExtensionDeclaredIds was called with the contributions
      expect(guardMocks.collectExtensionDeclaredIds).toHaveBeenCalledTimes(1);
      const callArg = guardMocks.collectExtensionDeclaredIds.mock.calls[0][0];
      expect(callArg).toHaveLength(2);
      expect(callArg[0].effectId).toBe('my-effect');
      expect(callArg[1].transitionId).toBe('my-transition');

      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });
  });

  describe('export guard — pure-native no-extension routing parity', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      mocks.startClientRender.mockResolvedValue(undefined);
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });
      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
    });

    it('routes pure-native media clip through client renderer with no extension runtime (identical to pre-extension behavior)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, client renderer invoked — same as pre-extension
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('routes pure-native media clip through client renderer with empty extension runtime (same as no extensions)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped because runtime is empty, client renderer invoked
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('routes pure-native clip through injected exporter with no extension runtime', async () => {
      const exporter = {
        render: vi.fn(async () => ({
          id: 'job-1',
          subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
            listener({
              phase: 'complete',
              progress: 1,
              resultUrl: 'blob:https://example.com/rendered',
              log: 'done',
            });
            return () => undefined;
          },
        })),
      };

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        {
          fps: 30,
          durationInFrames: 30,
          compositionWidth: 1920,
          compositionHeight: 1080,
        },
        exporter,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, exporter used (not client renderer)
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(exporter.render).toHaveBeenCalledTimes(1);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('done');
      expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    });

    it('routes pure-native clip through injected exporter with empty extension runtime (same as no extensions)', async () => {
      const exporter = {
        render: vi.fn(async () => ({
          id: 'job-1',
          subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
            listener({
              phase: 'complete',
              progress: 1,
              resultUrl: 'blob:https://example.com/rendered',
              log: 'done',
            });
            return () => undefined;
          },
        })),
      };

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        {
          fps: 30,
          durationInFrames: 30,
          compositionWidth: 1920,
          compositionHeight: 1080,
        },
        exporter,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped (empty runtime), exporter used — same routing as no extensions
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(exporter.render).toHaveBeenCalledTimes(1);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('done');
      expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    });

    it('preserves preview-only routing with no extension runtime (identical to pre-extension behavior)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-module-bad',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
          },
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, preview-only block preserved
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Render blocked');
      expect(result.current.renderLog).toContain('missing artifact metadata');
    });
  });

  describe('export guard — project requirement diagnostics', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      mocks.startClientRender.mockResolvedValue(undefined);
    });

    it('activates guard when extensions are present and emits no-error log for known native IDs', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'project-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-bridged' as any, kind: 'slot', slot: 'toolbar' },
              ],
            },
          } as any,
        ],
      });

      // Setup guard to return clean (all native IDs known)
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });
      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toBe('');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('emits blocking errors when project uses IDs not declared by any extension', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'project-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-bridged' as any, kind: 'slot', slot: 'toolbar' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "missing-effect" is not recognised. Ensure the required extension or registry is installed.',
            detail: { clipId: 'c1', effectType: 'missing-effect' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: ['missing-effect'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Blocked because the effect is not declared by any extension and not built-in
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export readiness blocked by the render planner');
      expect(result.current.renderLog).toContain('missing-effect');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('preserves routing when project uses IDs declared by inactive extension contributions (warnings only)', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'future-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-future-effect' as any, kind: 'effect' as any, effectId: 'future-effect' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['future-effect']),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "future-effect" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', effectType: 'future-effect' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(['future-effect']),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Not blocked — warning only, routing preserved
      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toBe('');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('scans config for project requirements when multiple extensions contribute IDs', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'ext-fx' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-fx1' as any, kind: 'effect' as any, effectId: 'custom-fx' },
              ],
            },
          } as any,
          {
            manifest: {
              id: 'ext-trans' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-tr1' as any, kind: 'transition' as any, transitionId: 'custom-transition' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['custom-fx']),
        transitionIds: new Set(['custom-transition']),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "custom-fx" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', effectType: 'custom-fx' },
          },
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "custom-transition" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', transitionType: 'custom-transition' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(['custom-fx']),
          transitionIds: new Set(['custom-transition']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard invoked (extensions present), warnings emitted, routing preserved
      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toBe('');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });
  });

  describe('export guard — provider registry snapshots', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      capturedRegistry = null;
      mocks.startClientRender.mockResolvedValue(undefined);
      installSnapshotAwareGuardMock();
    });

    it('passes the current provider snapshot into readiness checks and blocks missing effect IDs', async () => {
      const { result } = renderHook(() => useRenderState(
        makeTimelineWithEffect('missing-provider-effect'),
        null,
        null,
        nonEmptyExtensionRuntime(),
      ), { wrapper: RegistryWrapper });

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      const snapshot = guardMocks.scanExportConfig.mock.calls[0][3] as EffectRegistrySnapshot;
      expect(snapshot.records).toHaveLength(0);
      expect(snapshot.has('missing-provider-effect')).toBe(false);
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('missing-provider-effect');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('blocks provider records that are registered but cannot browser-export', async () => {
      const { result } = renderHook(() => useRenderState(
        makeTimelineWithEffect('preview-only-provider-effect'),
        null,
        null,
        nonEmptyExtensionRuntime(),
      ), { wrapper: RegistryWrapper });

      act(() => {
        capturedRegistry!.register(makeEffectRecord('preview-only-provider-effect', 'blocked'));
      });

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      const snapshot = guardMocks.scanExportConfig.mock.calls[0][3] as EffectRegistrySnapshot;
      expect(snapshot.get('preview-only-provider-effect')?.renderability.capabilities).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            route: 'browser-export',
            status: 'blocked',
          }),
        ]),
      );
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('cannot browser-export');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('recomputes readiness from updated provider snapshots', async () => {
      const { result } = renderHook(() => useRenderState(
        makeTimelineWithEffect('late-provider-effect'),
        null,
        null,
        nonEmptyExtensionRuntime(),
      ), { wrapper: RegistryWrapper });

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderLog).toContain('late-provider-effect');
      expect(mocks.startClientRender).not.toHaveBeenCalled();

      act(() => {
        capturedRegistry!.register(makeEffectRecord('late-provider-effect', 'supported'));
      });

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(2);
      const firstSnapshot = guardMocks.scanExportConfig.mock.calls[0][3] as EffectRegistrySnapshot;
      const secondSnapshot = guardMocks.scanExportConfig.mock.calls[1][3] as EffectRegistrySnapshot;
      expect(firstSnapshot.records).toHaveLength(0);
      expect(secondSnapshot.has('late-provider-effect')).toBe(true);
      expect(secondSnapshot.records).toHaveLength(1);
      expect(result.current.renderLog).toBe('');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });
  });

// ---------------------------------------------------------------------------
// M6: Export behavior — compile-only formats invoke registry, render-dependent
// formats are rejected, and existing Render behavior is unchanged
// ---------------------------------------------------------------------------

const exportMocks = vi.hoisted(() => ({
  executeCompileOnlyOutput: vi.fn(),
}));

vi.mock('@/tools/video-editor/runtime/outputFormatRegistry', async () => {
  const actual = await vi.importActual('@/tools/video-editor/runtime/outputFormatRegistry');
  return {
    ...actual,
    executeCompileOnlyOutput: exportMocks.executeCompileOnlyOutput,
  };
});

describe('useRenderState — M6 export behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
    guardMocks.collectBuiltInKnownIds.mockReturnValue({
      clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
      effectTypes: new Set(['fade', 'slide-up']),
      transitionTypes: new Set(['crossfade']),
    });
    guardMocks.collectExtensionDeclaredIds.mockReturnValue({
      effectIds: new Set(),
      transitionIds: new Set(),
      clipTypeIds: new Set(),
    });
    guardMocks.scanExportConfig.mockReturnValue({
      diagnostics: [],
      unknownClipTypes: [],
      unknownEffects: [],
      unknownTransitions: [],
      inactiveExtensionIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      hasBlockingErrors: false,
    });
    exportMocks.executeCompileOnlyOutput.mockReset();
  });

  // ---- exportFormats categorization ---------------------------------------

  it('categorizes output formats into compile-only and render-dependent from extension runtime config', () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-meta-json', extensionId: 'ext-a', label: 'Metadata JSON', requiresRender: false, outputExtension: 'json', disabled: false },
          { id: 'fmt-csv', extensionId: 'ext-a', label: 'CSV Export', requiresRender: false, outputExtension: 'csv', disabled: false },
          { id: 'fmt-mp4', extensionId: 'ext-b', label: 'MP4 Video', requiresRender: true, outputExtension: 'mp4', disabled: false },
          { id: 'fmt-disabled', extensionId: 'ext-b', label: 'Disabled Format', requiresRender: false, outputExtension: 'bin', disabled: true, disabledReason: 'Not yet implemented' },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    expect(result.current.exportFormats.compileOnly).toHaveLength(2);
    expect(result.current.exportFormats.compileOnly.map((f) => f.id)).toEqual(['fmt-meta-json', 'fmt-csv']);
    expect(result.current.exportFormats.renderDependent).toHaveLength(2);
    expect(result.current.exportFormats.renderDependent.map((f) => f.id)).toEqual(['fmt-mp4', 'fmt-disabled']);
  });

  it('returns empty arrays when no output formats are registered', () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    expect(result.current.exportFormats.compileOnly).toHaveLength(0);
    expect(result.current.exportFormats.renderDependent).toHaveLength(0);
  });

  it('returns empty arrays when extension runtime is undefined', () => {
    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      undefined,
    ));

    expect(result.current.exportFormats.compileOnly).toHaveLength(0);
    expect(result.current.exportFormats.renderDependent).toHaveLength(0);
  });

  // ---- startExport — compile-only invocation --------------------------------

  it('invokes executeCompileOnlyOutput for a valid compile-only format with timeline and assets', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue({
      artifact: { id: 'artifact-1', determinism: 'deterministic', diagnostics: [] },
      data: new Uint8Array([1, 2, 3]),
      hasBlockingErrors: false,
    });

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'Metadata JSON', requiresRender: false, outputExtension: 'json', outputMimeType: 'application/json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(exportMocks.executeCompileOnlyOutput).toHaveBeenCalledTimes(1);
    const callArgs = exportMocks.executeCompileOnlyOutput.mock.calls[0];
    expect(callArgs[1].formatId).toBe('fmt-json');
    expect(callArgs[1].extensionId).toBe('ext-a');
    expect(callArgs[1].timeline).toBeDefined();
    expect(callArgs[1].assets).toBeDefined();
    expect(result.current.exportStatus).toBe('done');
    expect(result.current.exportResultUrl).toBeTruthy();
    expect(result.current.exportResultFilename).toBe('export.json');
  });

  it('sets exportStatus to done and produces a downloadable blob on success', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue({
      artifact: { id: 'artifact-1', determinism: 'deterministic', diagnostics: [] },
      data: new Uint8Array([7, 8, 9]),
      hasBlockingErrors: false,
    });

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-csv', extensionId: 'ext-a', label: 'CSV', requiresRender: false, outputExtension: 'csv', outputMimeType: 'text/csv', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-csv', new Map([['fmt-csv', {}]]));
    });

    expect(result.current.exportStatus).toBe('done');
    expect(result.current.exportResultFilename).toBe('export.csv');
    expect(result.current.exportResultUrl).toMatch(/^blob:/);
    expect(result.current.exportLog).toContain('Export complete');
  });

  it('sets exportStatus to error when compile-only registry is empty', async () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map()); // empty Map = no handlers registered
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('no compile-only output handlers registered');
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  it('surfaces compile-only missing-handler planner text before guard or execution', async () => {
    const plannerMessage = 'Planner compile-only blocker text before execution.';
    renderPlannerMocks.planRender.mockReturnValueOnce(makePlannerResult([
      {
        id: 'planner.outputFormat.ext-a.fmt-json.browser-export.compile-handler-missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        message: plannerMessage,
        extensionId: 'ext-a',
        contributionId: 'fmt-json',
        detail: {
          source: 'render-request',
          outputFormatId: 'fmt-json',
          requestedRoute: 'browser-export',
          compileOnlyHandlerAvailable: false,
        },
      },
    ]));
    guardMocks.scanExportConfig.mockImplementation(() => {
      throw new Error('guard should not run before compile-only handler availability blocks');
    });
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map());
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain(plannerMessage);
    expect(renderPlannerMocks.planRender).toHaveBeenCalledWith(expect.objectContaining({
      request: expect.objectContaining({
        outputFormatId: 'fmt-json',
        routes: ['browser-export'],
        compileOnlyHandlerAvailable: false,
      }),
    }));
    expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  it('sets exportStatus to error when resolvedConfig is null', async () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      null, // no config
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map());
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('no timeline configuration');
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  // ---- startExport — render-dependent rejection ----------------------------

  it('rejects render-dependent format from the planner route result and does not invoke executeCompileOnlyOutput', async () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-mp4', extensionId: 'ext-b', label: 'MP4 Video', requiresRender: true, outputExtension: 'mp4', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-mp4', new Map());
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('not available on browser-export');
    expect(result.current.exportLog).toContain('MP4 Video');
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  it('rejects disabled output formats from planner diagnostics when disabledReason is provided', async () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-future', extensionId: 'ext-b', label: 'Future Format', requiresRender: true, outputExtension: 'fut', disabled: true, disabledReason: 'Needs real-time encoder integration' },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-future', new Map());
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('Needs real-time encoder integration');
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  it('rejects unknown format ID with planner missing-contribution error', async () => {
    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('non-existent-format', new Map());
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('not registered');
    expect(exportMocks.executeCompileOnlyOutput).not.toHaveBeenCalled();
  });

  // ---- startExport — exceptions from output registry -----------------------

  it('sets exportStatus to error when executeCompileOnlyOutput returns null', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue(null);

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('not available in the compile-only registry');
  });

  it('sets exportStatus to error when executeCompileOnlyOutput throws', async () => {
    exportMocks.executeCompileOnlyOutput.mockRejectedValue(new Error('Handler crashed'));

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('Handler crashed');
  });

  // ---- startExport — export state transitions ------------------------------

  it('transitions through exporting → done during compile-only export', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue({
      artifact: { id: 'artifact-1', determinism: 'deterministic', diagnostics: [] },
      data: new Uint8Array([1, 2, 3]),
      hasBlockingErrors: false,
    });

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    // After export completes, status should be 'done'
    expect(result.current.exportStatus).toBe('done');
    expect(result.current.exportLog).toContain('Export complete');
    expect(result.current.exportResultUrl).toMatch(/^blob:/);
    expect(result.current.exportResultFilename).toBe('export.json');
  });

  it('transitions through exporting → error on handler exception', async () => {
    exportMocks.executeCompileOnlyOutput.mockRejectedValue(new Error('Boom'));

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(result.current.exportStatus).toBe('error');
    expect(result.current.exportLog).toContain('Export failed');
    expect(result.current.exportLog).toContain('Boom');
  });

  // ---- startExport — diagnostics in result ---------------------------------

  it('includes diagnostic count in export log when result has diagnostics', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue({
      artifact: {
        id: 'artifact-1',
        determinism: 'deterministic',
        diagnostics: [
          { severity: 'warning', code: 'fmt/warning', message: 'Some warning' },
          { severity: 'info', code: 'fmt/info', message: 'Some info' },
        ],
      },
      data: new Uint8Array([1]),
      hasBlockingErrors: false,
    });

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(result.current.exportStatus).toBe('done');
    expect(result.current.exportLog).toContain('[2 diagnostic(s)]');
  });

  it('includes blocking errors note in export log when hasBlockingErrors is true', async () => {
    exportMocks.executeCompileOnlyOutput.mockResolvedValue({
      artifact: {
        id: 'artifact-1',
        determinism: 'deterministic',
        diagnostics: [
          { severity: 'error', code: 'fmt/error', message: 'Blocking error' },
        ],
      },
      data: new Uint8Array([1]),
      hasBlockingErrors: true,
    });

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
    });

    expect(result.current.exportStatus).toBe('done');
    expect(result.current.exportLog).toContain('with blocking errors');
  });

  // ---- Render behavior unchanged when export formats are present -----------

  it('preserves existing render routing when compile-only export formats are registered', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    // Render still invokes guard and routes normally
    expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
    expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    expect(result.current.renderStatus).toBe('idle');
  });

  it('preserves existing exporter-based render routing when compile-only formats are registered', async () => {
    const exporter = {
      render: vi.fn(async () => ({
        id: 'job-1',
        subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
          listener({
            phase: 'complete',
            progress: 1,
            resultUrl: 'blob:https://example.com/rendered',
            log: 'done',
          });
          return () => undefined;
        },
      })),
    };

    const extRuntime = makeExtensionRuntime({
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      { fps: 30, durationInFrames: 30, compositionWidth: 1920, compositionHeight: 1080 },
      exporter,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(exporter.render).toHaveBeenCalledTimes(1);
    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('done');
    expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
  });

  it('preserves render block when export guard finds blocking errors even with compile-only formats present', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
      config: {
        slots: {},
        dialogHost: { dialogs: [] },
        registry: { panels: [], inspectorSections: [] },
        outputFormats: [
          { id: 'fmt-json', extensionId: 'ext-a', label: 'JSON', requiresRender: false, outputExtension: 'json', disabled: false },
        ],
      } as any,
    });

    guardMocks.scanExportConfig.mockReturnValue({
      diagnostics: [
        {
          severity: 'error',
          code: 'export/unknown-clip-type',
          message: 'Clip type alien-format is not recognised.',
          detail: { clipId: 'c1', clipType: 'alien-format' },
        },
      ],
      unknownClipTypes: ['alien-format'],
      unknownEffects: [],
      unknownTransitions: [],
      inactiveExtensionIds: { effectIds: new Set(), transitionIds: new Set(), clipTypeIds: new Set() },
      hasBlockingErrors: true,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({ id: 'c1', clipType: 'media', track: 'V1', at: 0, hold: 1 }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    // Render was blocked by guard despite having export formats
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Export readiness blocked by the render planner');
    expect(result.current.renderLog).toContain('alien-format');
    expect(mocks.startClientRender).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Export guard — clip-type registry snapshot integration
// ---------------------------------------------------------------------------

describe('useRenderState export guard — clip-type registry snapshot', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
    guardMocks.collectBuiltInKnownIds.mockReturnValue({
      clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
      effectTypes: new Set(),
      transitionTypes: new Set(),
    });
    guardMocks.collectExtensionDeclaredIds.mockReturnValue({
      effectIds: new Set(),
      transitionIds: new Set(),
      clipTypeIds: new Set(),
    });
  });

  it('passes clipTypeRegistrySnapshot to scanExportConfig when guard runs', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
    });

    guardMocks.scanExportConfig.mockReturnValue({
      ...cleanGuardResult(),
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'c1',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
    const callArgs = guardMocks.scanExportConfig.mock.calls[0];
    expect(callArgs).toHaveLength(8);
    expect(callArgs[5]).toBeDefined();
    expect(callArgs[7]).toBeUndefined();
  });

  it('passes provider-held process attach evidence into export and router planning call sites', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
      processes: [
        {
          id: 'proc.descriptor',
          extensionId: 'ext.process',
          processId: 'dataset-process',
          label: 'Dataset Process',
          protocol: 'stdio-jsonrpc',
          availableRoutes: ['browser-export'],
          operations: [],
          requiredBy: [],
          blockers: [],
          nextActions: [],
          capabilities: { defaultRoute: 'browser-export', determinism: 'process-dependent', capabilityRequirements: [] },
          spec: { id: 'dataset-process', label: 'Dataset Process' },
        },
      ] as any,
    });
    const attachRecord = makeProcessAttachRecord();
    const runtimeValue = {
      processStatuses: [{ processId: 'dataset-process', state: 'ready' }],
      processResultAttachRecords: [attachRecord],
    } as unknown as VideoEditorRuntimeContextValue;
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DataProviderContext.Provider value={runtimeValue}>
        {children}
      </DataProviderContext.Provider>
    );

    guardMocks.scanExportConfig.mockReturnValue({
      ...cleanGuardResult(),
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'c1',
        clipType: 'generated-module',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
      null,
      extRuntime,
    ), { wrapper });

    await act(async () => {
      await result.current.startRender();
    });

    expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
    expect(guardMocks.scanExportConfig.mock.calls[0]?.[7]).toEqual([attachRecord]);

    expect(renderRouterMocks.decideRenderRoute).toHaveBeenCalledTimes(1);
    expect(renderRouterMocks.decideRenderRoute.mock.calls[0]?.[2]).toMatchObject({
      compositionGraph: extRuntime.compositionGraph,
      processes: extRuntime.processes,
      processStatuses: runtimeValue.processStatuses,
      processResultAttachRecords: [attachRecord],
    });
  });

  it('includes clipType details in render log for blocking clip-type errors', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
    });

    guardMocks.scanExportConfig.mockReturnValue({
      ...cleanGuardResult(),
      diagnostics: [
        {
          severity: 'error',
          code: 'export/unrenderable-clip-type',
          message: 'Clip type "stale-clip-type" is registered but inactive and cannot be used for export or preview.',
          extensionId: 'ext.stale',
          contributionId: 'test:clipType:stale-clip-type',
          detail: {
            clipId: 'c1',
            clipType: 'stale-clip-type',
            clipTypeStatus: 'inactive',
            provenance: 'bundled-extension',
          },
        },
      ],
      hasBlockingErrors: true,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'c1',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Export readiness blocked by the render planner');
    expect(result.current.renderLog).toContain('stale-clip-type');
    expect(result.current.renderLog).toContain('route-unsupported');
    expect(result.current.renderLog).toContain('inactive');
    expect(mocks.startClientRender).not.toHaveBeenCalled();
  });

  it('includes clipType details in render log for warning diagnostics', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
    });

    guardMocks.scanExportConfig.mockReturnValue({
      ...cleanGuardResult(),
      diagnostics: [
        {
          severity: 'warning',
          code: 'export/unknown-clip-type',
          message: 'Clip type "future-clip" is declared by an inactive extension and may not be available at export time.',
          detail: { clipId: 'c1', clipType: 'future-clip' },
        },
      ],
      hasBlockingErrors: false,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'c1',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
      null,
      extRuntime,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    // Warning only — native routing preserved
    expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    expect(result.current.renderLog).toBe('');
  });

  it('publishes clip-type diagnostics to the provider collection', async () => {
    const extRuntime = makeExtensionRuntime({
      extensions: [
        {
          manifest: {
            id: 'test-ext' as any,
            version: '1.0.0',
            contributions: [],
          },
        } as any,
      ],
    });
    const collection = createDiagnosticCollection();
    const runtimeValue = {
      diagnosticCollection: collection,
    } as unknown as VideoEditorRuntimeContextValue;
    const wrapper = ({ children }: { children: ReactNode }) => (
      <DataProviderContext.Provider value={runtimeValue}>
        {children}
      </DataProviderContext.Provider>
    );

    guardMocks.scanExportConfig.mockReturnValue({
      ...cleanGuardResult(),
      diagnostics: [
        {
          severity: 'error',
          code: 'export/unrenderable-clip-type',
          message: 'Clip type "stale-clip-type" is registered but inactive.',
          extensionId: 'ext.stale',
          contributionId: 'test:clipType:stale-clip-type',
          detail: { clipId: 'c1', clipType: 'stale-clip-type', clipTypeStatus: 'inactive' },
        },
      ],
      blockers: [
        {
          id: 'export.clipType.c1.stale-clip-type.inactive.browser-export',
          severity: 'error',
          route: 'browser-export',
          reason: 'inactive-extension',
          message: 'Clip type "stale-clip-type" on route "browser-export" is registered but inactive.',
          clipId: 'c1',
          detail: { clipType: 'stale-clip-type' },
        },
      ],
      hasBlockingErrors: true,
    });

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'c1',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
      null,
      extRuntime,
    ), { wrapper });

    await act(async () => {
      await result.current.startRender();
    });

    const diagnostics = collection.getSnapshot();
    expect(diagnostics.some((diagnostic) => diagnostic.detail?.source === 'export-guard')).toBe(true);
    expect(diagnostics.some((diagnostic) => diagnostic.detail?.source === 'render-planner')).toBe(true);
  });
});
});
