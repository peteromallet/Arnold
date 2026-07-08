// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import type * as React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  type AgentToolInvocationRequest,
  type AgentToolRegistrationService,
  type CreativeContext,
  type ExtensionContext,
  type LiveBakeResult,
  type LiveChannelDescriptor,
  type LiveSessionsService,
  type ReighExtension,
  type ToolGenerationSessionResult,
} from '@/sdk/index';
import { createExtensionContext } from '@/tools/video-editor/runtime/extensionContextFactory';
import {
  createLiveGeneratedFrameCanaryExtension,
  type LiveGeneratedFrameCanaryController,
  type LiveGeneratedFrameSession,
} from '@/tools/video-editor/examples/extensions/live-generated-frame-canary';
import {
  createLiveWebcamCanaryExtension,
  startLiveWebcamCanary,
} from '@/tools/video-editor/examples/extensions/live-webcam-canary';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext';
import { removeLiveBindingsFromResolvedConfig } from '@/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel';
import {
  createExtensionLifecycleHost,
  type ExtensionLifecycleHost,
} from '@/tools/video-editor/runtime/extensionLifecycle';
import {
  createAgentToolRegistry,
  type AgentToolRegistry,
} from '@/tools/video-editor/runtime/agentToolRegistry';
import {
  createLiveDataRegistry,
  type LiveDataRegistry,
} from '@/tools/video-editor/runtime/liveDataRegistry';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard';
import { buildExportReadinessPlan } from '@/tools/video-editor/runtime/renderPlanner';
import { scanTimelineLiveBindings } from '@/tools/video-editor/lib/timeline-domain';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry';

const WEBCAM_EXTENSION_ID = 'com.reigh.examples.live-webcam-canary';
const WEBCAM_SOURCE_ID = `${WEBCAM_EXTENSION_ID}:webcam`;
const GENERATED_EXTENSION_ID = 'com.reigh.examples.live-generated-frame-canary';
const GENERATED_TOOL_ID = 'generated-frame.session';

vi.mock('remotion', async () => ({
  AbsoluteFill: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="absolute-fill" {...props}>{children}</div>
  ),
  Sequence: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="sequence" {...props}>{children}</div>
  ),
  useCurrentFrame: () => 0,
  useRemotionEnvironment: () => ({ isRendering: false, isClientSideRendering: false }),
}));

vi.mock('@banodoco/timeline-composition/theme-api', async () => {
  const React = await import('react');
  const theme = {
    color: { accent: '#ffffff', bg: '#000000', fg: '#ffffff' },
    type: {
      families: { heading: 'Georgia, serif', body: 'Inter, sans-serif', mono: 'monospace' },
      size: { base: 56, small: 32, large: 128 },
      weight: { normal: 300, bold: 500 },
      lineHeight: 1.1,
    },
    motion: { fadeMs: 500 },
    canvas: { width: 1920, height: 1080, fps: 30 },
  };
  const ThemeContext = React.createContext(theme);
  return {
    DEFAULT_THEME: { id: 'default', visual: theme },
    ThemeProvider: ({ children }: React.PropsWithChildren<{ value: unknown }>) => (
      <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>
    ),
    useTheme: () => React.useContext(ThemeContext),
  };
});

vi.mock('@banodoco/timeline-composition/registry.generated', async () => ({
  THEME_PACKAGE_CLIP_TYPES: [],
  THEME_PACKAGE_REGISTRY: {},
}));

vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', async () => ({
  AudioAnalysisProvider: ({ children }: React.PropsWithChildren) => (
    <div data-testid="audio-analysis-provider">{children}</div>
  ),
}));

vi.mock('@/tools/video-editor/compositions/VisualClip', async () => ({
  VisualClipSequence: () => <div data-testid="visual-clip-sequence" />,
}));

vi.mock('@/tools/video-editor/compositions/TextClip', async () => ({
  TextClipSequence: () => <div data-testid="text-clip-sequence" />,
}));

vi.mock('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx', async () => {
  const actual = await vi.importActual<
    typeof import('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx')
  >('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx');
  return {
    ...actual,
    useClipTypeRegistrySnapshot: () => ({
      records: Object.freeze([]),
      diagnostics: Object.freeze([]),
      get: () => undefined,
      has: () => false,
    }),
  };
});

function installMediaMocks(options: { getUserMedia?: ReturnType<typeof vi.fn> } = {}) {
  const track = { stop: vi.fn() };
  const stream = { getTracks: vi.fn(() => [track]) } as unknown as MediaStream;
  const getUserMedia = options.getUserMedia ?? vi.fn().mockResolvedValue(stream);

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });

  const getContext = vi
    .spyOn(HTMLCanvasElement.prototype, 'getContext')
    .mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,WEBCAM_INTEGRATION');
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ close: vi.fn() }));

  return { stream, track, getUserMedia, getContext };
}

function makeSessions(registry: LiveDataRegistry, extensionId = WEBCAM_EXTENSION_ID): LiveSessionsService {
  return {
    registerSource(source) {
      return registry.registerSourceWithOwner(source, extensionId);
    },
    getSource(sourceId) {
      return registry.getSource(sourceId);
    },
    listSources() {
      return registry.listSources();
    },
    openChannel(sourceId, kind, metadata) {
      return registry.openChannel(sourceId, kind, metadata);
    },
    closeChannel(channelId) {
      registry.closeChannel(channelId);
    },
    getChannelMetadata(channelId) {
      return registry.getChannelMetadata(channelId);
    },
    pushSample(channelId, frame) {
      registry.pushSample(channelId, frame);
    },
    subscribeSamples(channelId, listener) {
      return registry.subscribeSamples(channelId, listener);
    },
    bake(selection) {
      return registry.bake(selection);
    },
    removeLiveBindings(sourceId) {
      registry.removeLiveBindings(sourceId);
    },
    resolveBinding(bindingId) {
      return registry.resolveBinding(bindingId);
    },
    getBindingMetadata() {
      return registry.getBindingMetadata();
    },
    applySteeringDecision(decision) {
      registry.applySteeringDecision(decision);
    },
    getDiagnostics(sourceId) {
      return registry.getDiagnostics(sourceId);
    },
  };
}

function makeHostContextFactory(registry: LiveDataRegistry) {
  return (extension: ReighExtension): ExtensionContext => createExtensionContext(extension, {
    sessions: makeSessions(registry, extension.manifest.id as string),
  } as Partial<CreativeContext>);
}

function makeAgentTools(registry: AgentToolRegistry, extensionId = GENERATED_EXTENSION_ID): AgentToolRegistrationService {
  return {
    registerTool(toolId, handler) {
      return registry.registerTool(extensionId, toolId, handler);
    },
    async invokeProcess() {
      return {
        family: 'process',
        diagnostics: [{
          severity: 'info',
          code: 'agent-tool/process-not-available',
          message: 'Process invocation is not available in integration tests.',
        }],
      };
    },
  };
}

function makeGeneratedContext(
  extension: ReighExtension,
  liveRegistry: LiveDataRegistry,
  agentRegistry: AgentToolRegistry,
): ExtensionContext {
  return createExtensionContext(
    extension,
    { sessions: makeSessions(liveRegistry, GENERATED_EXTENSION_ID) } as Partial<CreativeContext>,
    undefined,
    undefined,
    undefined,
    undefined,
    makeAgentTools(agentRegistry),
  );
}

function runtimeWithLiveRegistry(liveDataRegistry?: LiveDataRegistry): VideoEditorRuntimeContextValue {
  return {
    provider: {},
    assetResolver: {},
    auth: {},
    project: {},
    shots: {},
    mediaLightbox: {},
    agentChat: {},
    toast: {},
    telemetry: {},
    timelineId: 'timeline-integration',
    userId: 'user-integration',
    extensions: {},
    liveDataRegistry,
  } as unknown as VideoEditorRuntimeContextValue;
}

function makeConfig(clip: Record<string, unknown>): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [clip as ResolvedTimelineConfig['clips'][number]],
    registry: {},
  };
}

function makeLiveMediaConfig(binding: Record<string, unknown>): ResolvedTimelineConfig {
  return makeConfig({
    id: 'clip-live-media',
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 2,
    app: {
      live: {
        bindings: [binding],
      },
    },
  });
}

function renderPreview(config: ResolvedTimelineConfig, registry: LiveDataRegistry) {
  return render(
    <DataProviderWrapper value={runtimeWithLiveRegistry(registry)}>
      <TimelineRenderer config={config} />
    </DataProviderWrapper>,
  );
}

function replacements(result: LiveBakeResult): any[] {
  return (result as unknown as { replacements: any[] }).replacements;
}

function activeLiveFrameClipTypeSnapshot(): ClipTypeRegistrySnapshot {
  const record: ClipTypeRegistryRecord = {
    clipTypeId: 'live-frame-preview',
    contributionId: 'live-webcam-canary-preview',
    renderer: { render: () => null },
    provenance: 'trusted-loader',
    status: 'active',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        { route: 'preview', status: 'supported', determinism: 'deterministic' },
        { route: 'browser-export', status: 'supported', determinism: 'deterministic' },
      ],
    },
  };
  return Object.freeze({
    records: Object.freeze([record]),
    diagnostics: Object.freeze([]),
    get: (clipTypeId: string) => (clipTypeId === record.clipTypeId ? record : undefined),
    has: (clipTypeId: string) => clipTypeId === record.clipTypeId,
  });
}

async function waitForReady(host: ExtensionLifecycleHost, extensionId: string) {
  await Promise.resolve();
  await Promise.resolve();
  expect(host.lifecycles.get(extensionId)?.state).toBe('active');
}

function activateGeneratedCanary(options: { now?: () => number } = {}) {
  const liveRegistry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
  const agentRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
  let controller: LiveGeneratedFrameCanaryController | undefined;
  const extension = createLiveGeneratedFrameCanaryExtension({
    now: options.now,
    onReady(next) {
      controller = next;
    },
  });

  for (const contribution of extension.manifest.contributions ?? []) {
    if (contribution.kind === 'agentTool') {
      agentRegistry.ingestAgentToolContribution(GENERATED_EXTENSION_ID, contribution);
    }
  }

  const handle = extension.activate(makeGeneratedContext(extension, liveRegistry, agentRegistry));
  expect(controller).toBeDefined();

  return {
    liveRegistry,
    agentRegistry,
    controller: controller!,
    dispose() {
      handle?.dispose();
      agentRegistry.dispose();
      liveRegistry.dispose();
    },
  };
}

function makeRequest(input: Record<string, unknown>): AgentToolInvocationRequest {
  return {
    toolId: GENERATED_TOOL_ID,
    extensionId: GENERATED_EXTENSION_ID,
    contributionId: 'generated-frame-session-contribution',
    context: { projectId: 'project-integration' },
    input,
  };
}

async function invokeGeneratedSession(
  agentRegistry: AgentToolRegistry,
  input: Record<string, unknown>,
): Promise<ToolGenerationSessionResult> {
  const result = await agentRegistry.invokeTool(makeRequest(input));
  expect(result).toEqual(expect.objectContaining({ family: 'generation/session' }));
  return result as ToolGenerationSessionResult;
}

function hostChannelFor(agentRegistry: AgentToolRegistry, sourceId: string): LiveChannelDescriptor {
  const channel = agentRegistry.getSnapshot().sessions
    .flatMap((session) => session.liveDelivery?.activeChannels ?? [])
    .find((candidate) => candidate.startsWith(`${sourceId}:ch-`));
  expect(channel).toBeDefined();
  return channel as LiveChannelDescriptor;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('M11 live data bridge integration', () => {
  it('keeps webcam samples live through preview, blocks orphaned export after provider disposal, and clears after remove', async () => {
    const media = installMediaMocks();
    const registry = createLiveDataRegistry();
    const host = createExtensionLifecycleHost(registry);
    let controller: ReturnType<typeof startLiveWebcamCanary> | undefined;
    const extension = createLiveWebcamCanaryExtension({
      autoCapture: false,
      onReady(next) {
        controller = next;
      },
    });

    host.synchronize([extension], makeHostContextFactory(registry));
    await waitForReady(host, WEBCAM_EXTENSION_ID);
    const session = await controller!.ready;
    expect(session).not.toBeNull();
    await expect(controller!.captureOnce()).resolves.toBe(true);
    expect(registry.getSource(WEBCAM_SOURCE_ID)?.status).toBe('active');
    expect(registry.getSampleCount(session!.channelId)).toBe(1);

    renderPreview(makeConfig(controller!.previewClip), registry);
    const preview = screen.getByTestId('live-frame-preview');
    expect(preview.querySelector('img')?.getAttribute('src')).toBe('data:image/png;base64,WEBCAM_INTEGRATION');
    expect(preview.getAttribute('data-live-frame-state')).toBe('final');

    host.synchronize([], makeHostContextFactory(registry));
    expect(media.track.stop).toHaveBeenCalledTimes(1);
    expect(registry.getSource(WEBCAM_SOURCE_ID)).toBeUndefined();
    expect(registry.getSnapshot().tombstones).toEqual([
      expect.objectContaining({
        id: WEBCAM_SOURCE_ID,
        status: 'orphaned',
        extensionId: WEBCAM_EXTENSION_ID,
      }),
    ]);

    const orphanedConfig = makeConfig(controller!.previewClip);
    const liveScan = scanTimelineLiveBindings(orphanedConfig, {
      sources: registry.getSnapshot().tombstones.map((tombstone) => ({
        sourceId: tombstone.id,
        kind: tombstone.kind,
        status: tombstone.status,
        ownerExtensionId: tombstone.extensionId,
      })),
    });
    expect(liveScan.bindings[0]).toEqual(expect.objectContaining({
      status: 'orphaned',
      blocksExport: true,
    }));

    const extensionIds = collectExtensionDeclaredIds(extension.manifest.contributions ?? []);
    const clipTypeSnapshot = activeLiveFrameClipTypeSnapshot();
    const blocked = scanExportConfig(
      orphanedConfig,
      collectBuiltInKnownIds(),
      extensionIds,
      undefined,
      undefined,
      clipTypeSnapshot,
    );
    expect(blocked.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: 'export/live-binding-unresolved' }),
    ]));
    expect(buildExportReadinessPlan({ guard: blocked }).canBrowserExport).toBe(false);

    const clearedConfig = removeLiveBindingsFromResolvedConfig(orphanedConfig, WEBCAM_SOURCE_ID);
    expect(clearedConfig).not.toBeNull();
    const cleared = scanExportConfig(
      clearedConfig!,
      collectBuiltInKnownIds(),
      extensionIds,
      undefined,
      undefined,
      clipTypeSnapshot,
    );
    expect(cleared.diagnostics.filter((diagnostic) => diagnostic.code === 'export/live-binding-unresolved')).toEqual([]);
    expect(buildExportReadinessPlan({ guard: cleared }).canBrowserExport).toBe(true);

    host.disposeAll();
  });

  it('carries GenerationSession steering through live samples, partial bake, full bake, and export guard clearance', async () => {
    let now = 6000;
    const test = activateGeneratedCanary({ now: () => {
      now += 10;
      return now;
    } });

    const supersedeResult = await invokeGeneratedSession(test.agentRegistry, {
      sessionId: 'session-int-supersede',
      steeringKind: 'supersede',
      generationIndex: 1,
      parentRefs: ['seed-frame'],
      takeId: 'take-main',
    });
    const supersedeSession = supersedeResult.session as LiveGeneratedFrameSession;
    expect(supersedeSession.liveDelivery.steeringDecision.kind).toBe('supersede');

    const forkResult = await invokeGeneratedSession(test.agentRegistry, {
      sessionId: 'session-int-fork',
      steeringKind: 'fork',
      generationIndex: 2,
      parentRefs: [supersedeSession.sourceId],
      takeId: 'take-main',
      prompt: 'fork the accepted canary frame',
      model: 'deterministic-canary',
      seed: 2026,
    });
    const forkSession = forkResult.session as LiveGeneratedFrameSession;
    const sourceId = `${GENERATED_EXTENSION_ID}:generated:session-int-fork`;
    const channelId = hostChannelFor(test.agentRegistry, sourceId);

    expect(forkSession.liveDelivery.steeringDecision.kind).toBe('fork');
    expect(test.liveRegistry.getSource(sourceId)).toEqual(expect.objectContaining({
      status: 'inactive',
      metadata: expect.objectContaining({
        generationIndex: 2,
        parentRefs: [supersedeSession.sourceId],
      }),
    }));
    expect(forkSession.emitPending(0)).toBe(true);
    expect(forkSession.emitRefining(0)).toBe(true);
    expect(forkSession.emitFinal(0)).toBe(true);
    expect(test.liveRegistry.getSamples(channelId).map((sample) => (sample.frame.data as any).state)).toEqual([
      'pending',
      'refining',
      'final',
    ]);
    expect(test.agentRegistry.getSnapshot().sessions.at(-1)?.liveDelivery).toEqual(expect.objectContaining({
      canActivate: true,
      generationIndex: 2,
      parentRefs: [supersedeSession.sourceId],
      steeringDecision: expect.objectContaining({ kind: 'fork' }),
      progress: 100,
      sampleCount: 3,
    }));

    forkSession.acceptTake('take-main');
    expect(forkSession.emitFrame({
      state: 'final',
      progress: 100,
      frameIndex: 1,
      takeId: 'take-alt',
      accepted: false,
    })).toBe(true);

    const liveBinding = {
      bindingId: `${sourceId}:preview-binding`,
      sourceId,
      sourceKind: 'generated',
      channelId,
      resolutionStatus: 'active',
    };
    const liveGuard = scanExportConfig(
      makeLiveMediaConfig(liveBinding),
      collectBuiltInKnownIds(),
      collectExtensionDeclaredIds([]),
    );
    expect(liveGuard.findings.map((finding) => finding.detail?.resolutionStatus)).toContain('active');
    expect(buildExportReadinessPlan({ guard: liveGuard }).canBrowserExport).toBe(false);

    const partial = test.controller.bakeAcceptedTake('generated-int-take-main', 'take-main');
    expect(partial.success).toBe(true);
    expect(replacements(partial)[0]).toEqual(expect.objectContaining({
      input: expect.objectContaining({
        sampleCount: 3,
        range: expect.objectContaining({ takeId: 'take-main' }),
      }),
    }));
    const partialGuard = scanExportConfig(
      makeLiveMediaConfig({
        ...liveBinding,
        bake: {
          status: 'partial',
          deterministicRefs: [replacements(partial)[0].deterministicRef],
          unresolvedRanges: [{ startFrame: 1, endFrame: 2 }],
        },
      }),
      collectBuiltInKnownIds(),
      collectExtensionDeclaredIds([]),
    );
    expect(partialGuard.findings.map((finding) => finding.detail?.resolutionStatus)).toContain('partiallyBaked');
    expect(buildExportReadinessPlan({ guard: partialGuard }).canBrowserExport).toBe(false);

    const asset = test.controller.bakeAsset('generated-int-full-asset');
    const material = test.controller.bakeRenderMaterial('generated-int-full-material');
    expect(asset.success).toBe(true);
    expect(material.success).toBe(true);
    expect(replacements(asset)[0].deterministicRef).toEqual(expect.objectContaining({
      kind: 'asset',
      ref: 'generated-int-full-asset',
    }));
    expect(replacements(material)[0].renderMaterial).toEqual(expect.objectContaining({
      id: 'generated-int-full-material',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
    }));

    const fullGuard = scanExportConfig(
      makeLiveMediaConfig({
        ...liveBinding,
        bake: {
          status: 'complete',
          deterministicRefs: [replacements(asset)[0].deterministicRef],
        },
      }),
      collectBuiltInKnownIds(),
      collectExtensionDeclaredIds([]),
    );
    expect(fullGuard.diagnostics.filter((diagnostic) => diagnostic.code === 'export/live-binding-unresolved')).toEqual([]);
    expect(buildExportReadinessPlan({ guard: fullGuard }).canBrowserExport).toBe(true);

    test.dispose();
  });
});
