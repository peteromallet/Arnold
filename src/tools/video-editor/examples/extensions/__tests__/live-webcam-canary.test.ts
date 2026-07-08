// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  type CreativeContext,
  type ExtensionContext,
  type LiveSessionsService,
  type ReighExtension,
} from '@/sdk/index';
import { createExtensionContext } from '@/tools/video-editor/runtime/extensionContextFactory';
import {
  createLiveWebcamCanaryExtension,
  createLiveWebcamPreviewClip,
  startLiveWebcamCanary,
} from '@/tools/video-editor/examples/extensions/live-webcam-canary';
import {
  createExtensionLifecycleHost,
  type ExtensionLifecycleHost,
} from '@/tools/video-editor/runtime/extensionLifecycle';
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

const EXTENSION_ID = 'com.reigh.examples.live-webcam-canary';
const SOURCE_ID = `${EXTENSION_ID}:webcam`;

function createTrack() {
  return { stop: vi.fn() };
}

function installMediaMocks(options: {
  getUserMedia?: ReturnType<typeof vi.fn>;
} = {}) {
  const track = createTrack();
  const stream = {
    getTracks: vi.fn(() => [track]),
  } as unknown as MediaStream;
  const getUserMedia = options.getUserMedia ?? vi.fn().mockResolvedValue(stream);

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });

  const drawImage = vi.fn();
  const getContext = vi
    .spyOn(HTMLCanvasElement.prototype, 'getContext')
    .mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
  const toDataURL = vi
    .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
    .mockReturnValue('data:image/png;base64,WEBCAM_FRAME');
  const play = vi
    .spyOn(HTMLMediaElement.prototype, 'play')
    .mockResolvedValue(undefined);
  const pause = vi
    .spyOn(HTMLMediaElement.prototype, 'pause')
    .mockImplementation(() => undefined);
  const bitmap = { close: vi.fn() };
  const createImageBitmapMock = vi.fn().mockResolvedValue(bitmap);
  vi.stubGlobal('createImageBitmap', createImageBitmapMock);

  return {
    stream,
    track,
    getUserMedia,
    drawImage,
    getContext,
    toDataURL,
    play,
    pause,
    bitmap,
    createImageBitmapMock,
  };
}

function makeSessions(registry: LiveDataRegistry, extensionId = EXTENSION_ID): LiveSessionsService {
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

function makeCtx(
  extension: ReighExtension,
  registry: LiveDataRegistry,
): ExtensionContext {
  return createExtensionContext(extension, {
    sessions: makeSessions(registry),
  } as Partial<CreativeContext>);
}

function makeHostContextFactory(registry: LiveDataRegistry) {
  return (extension: ReighExtension): ExtensionContext => (
    createExtensionContext(extension, {
      sessions: makeSessions(registry, extension.manifest.id as string),
    } as Partial<CreativeContext>)
  );
}

function makeConfig(clip: Record<string, unknown>): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [clip as ResolvedTimelineConfig['clips'][number]],
    registry: {},
  };
}

async function waitForReady(host: ExtensionLifecycleHost) {
  await Promise.resolve();
  await Promise.resolve();
  expect(host.lifecycles.get(EXTENSION_ID)?.state).toBe('active');
}

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('live-webcam-canary extension', () => {
  it('publishes unsupported diagnostics and cleans the source when getUserMedia is unavailable', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    });
    const registry = createLiveDataRegistry();
    const extension = createLiveWebcamCanaryExtension({ autoCapture: false, disposeSourceOnDispose: true });
    const ctx = makeCtx(extension, registry);

    const controller = startLiveWebcamCanary(ctx, { autoCapture: false, disposeSourceOnDispose: true });
    await expect(controller.ready).resolves.toBeNull();

    expect(ctx.services.diagnostics.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'live-webcam/unsupported',
      }),
    ]);
    expect(registry.getSource(SOURCE_ID)).toBeUndefined();
    expect(registry.getSnapshot().tombstones).toEqual([
      expect.objectContaining({ id: SOURCE_ID, status: 'disposed' }),
    ]);
  });

  it('publishes permission diagnostics and stops cleanup before any frame channel remains', async () => {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError'));
    installMediaMocks({ getUserMedia });
    const registry = createLiveDataRegistry();
    const extension = createLiveWebcamCanaryExtension({ autoCapture: false, disposeSourceOnDispose: true });
    const ctx = makeCtx(extension, registry);

    const controller = startLiveWebcamCanary(ctx, { autoCapture: false, disposeSourceOnDispose: true });
    await expect(controller.ready).resolves.toBeNull();

    expect(getUserMedia).toHaveBeenCalledWith({ video: { width: 640, height: 360 }, audio: false });
    expect(ctx.services.diagnostics.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'live-webcam/permission-denied',
      }),
    ]);
    expect(registry.getSnapshot().channels).toEqual([]);
    expect(registry.getSource(SOURCE_ID)).toBeUndefined();
  });

  it('opens a webcam frame channel, pushes preview frames, and bakes image, video, and RenderMaterial refs', async () => {
    const media = installMediaMocks();
    const registry = createLiveDataRegistry();
    const extension = createLiveWebcamCanaryExtension({ autoCapture: false, now: () => 1234 });
    const ctx = makeCtx(extension, registry);

    const controller = startLiveWebcamCanary(ctx, { autoCapture: false, now: () => 1234, disposeSourceOnDispose: true });
    const session = await controller.ready;

    expect(session).not.toBeNull();
    expect(session?.channelId).toBe(controller.channelId);
    expect(registry.getChannelMetadata(session!.channelId)).toEqual(expect.objectContaining({
      sourceId: SOURCE_ID,
      kind: 'video',
    }));

    await expect(controller.captureOnce()).resolves.toBe(true);
    expect(media.getUserMedia).toHaveBeenCalledTimes(1);
    expect(media.drawImage).toHaveBeenCalledTimes(1);
    expect(media.createImageBitmapMock).toHaveBeenCalledTimes(1);

    const sample = registry.getLatestSample(session!.channelId);
    expect(sample?.frame).toEqual(expect.objectContaining({
      timestamp: 1234,
      format: 'json',
      data: expect.objectContaining({
        src: 'data:image/png;base64,WEBCAM_FRAME',
        state: 'final',
        progress: 100,
        frameIndex: 0,
      }),
      metadata: expect.objectContaining({ frameIndex: 0, width: 640, height: 360 }),
    }));
    expect(controller.previewClip).toEqual(expect.objectContaining({
      clipType: 'live-frame-preview',
      params: expect.objectContaining({
        livePreview: true,
        liveBindings: [expect.objectContaining({
          sourceId: SOURCE_ID,
          sourceKind: 'webcam',
          channelId: session!.channelId,
        })],
      }),
    }));

    expect(controller.bakeImage('webcam-image').success).toBe(true);
    expect(controller.bakeVideo('webcam-video').success).toBe(true);
    const materialBake = controller.bakeRenderMaterial('webcam-material');
    expect(materialBake.success).toBe(true);
    expect(materialBake.targets[0].diagnostics?.[0].detail).toEqual(expect.objectContaining({
      renderMaterial: expect.objectContaining({
        id: 'webcam-material',
        mediaKind: 'video',
        determinism: 'deterministic',
        replacementPolicy: 'replace-live-ref',
      }),
    }));

    controller.dispose();
    expect(media.track.stop).toHaveBeenCalledTimes(1);
    expect(media.bitmap.close).toHaveBeenCalledTimes(1);
    expect(registry.getSnapshot().channels).toEqual([]);
  });

  it('cleans browser resources on provider removal while unresolved bindings stay export-blocked', async () => {
    const media = installMediaMocks();
    const registry = createLiveDataRegistry();
    let controller: ReturnType<typeof startLiveWebcamCanary> | undefined;
    const extension = createLiveWebcamCanaryExtension({
      autoCapture: false,
      onReady(next) {
        controller = next;
      },
    });
    const host = createExtensionLifecycleHost(registry);

    host.synchronize([extension], makeHostContextFactory(registry));
    await waitForReady(host);
    await controller!.ready;
    await controller!.captureOnce();
    const previewClip = controller!.previewClip;

    host.synchronize([], makeHostContextFactory(registry));

    expect(media.track.stop).toHaveBeenCalledTimes(1);
    expect(registry.getSource(SOURCE_ID)).toBeUndefined();
    expect(registry.getSnapshot().tombstones).toEqual([
      expect.objectContaining({
        id: SOURCE_ID,
        status: 'orphaned',
        extensionId: EXTENSION_ID,
      }),
    ]);

    const liveScan = scanTimelineLiveBindings(makeConfig(previewClip), {
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

    const exportScan = scanExportConfig(
      makeConfig(previewClip),
      collectBuiltInKnownIds(),
      collectExtensionDeclaredIds([]),
    );
    expect(exportScan.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        code: 'export/live-binding-unresolved',
      }),
    ]));
    expect(buildExportReadinessPlan({ guard: exportScan }).canBrowserExport).toBe(false);

    host.disposeAll();
  });

  it('cleans browser resources on HMR replacement and provider disposeAll', async () => {
    const hmrMedia = installMediaMocks();
    const hmrRegistry = createLiveDataRegistry();
    const hmrHost = createExtensionLifecycleHost(hmrRegistry);
    let hmrController: ReturnType<typeof startLiveWebcamCanary> | undefined;
    const hmrExtension = createLiveWebcamCanaryExtension({
      sourceId: `${SOURCE_ID}:hmr-a`,
      autoCapture: false,
      onReady(next) {
        hmrController = next;
      },
    });

    hmrHost.synchronize([hmrExtension], makeHostContextFactory(hmrRegistry));
    await waitForReady(hmrHost);
    await hmrController!.ready;
    hmrHost.synchronize([
      createLiveWebcamCanaryExtension({
        sourceId: `${SOURCE_ID}:hmr-b`,
        autoCapture: false,
        width: 800,
      }),
    ], makeHostContextFactory(hmrRegistry));
    expect(hmrMedia.track.stop).toHaveBeenCalledTimes(1);
    hmrHost.disposeAll();

    vi.restoreAllMocks();
    const disposeAllMedia = installMediaMocks();
    const disposeAllRegistry = createLiveDataRegistry();
    const disposeAllHost = createExtensionLifecycleHost(disposeAllRegistry);
    let disposeAllController: ReturnType<typeof startLiveWebcamCanary> | undefined;
    disposeAllHost.synchronize([
      createLiveWebcamCanaryExtension({
        sourceId: `${SOURCE_ID}:dispose-all`,
        autoCapture: false,
        onReady(next) {
          disposeAllController = next;
        },
      }),
    ], makeHostContextFactory(disposeAllRegistry));
    await waitForReady(disposeAllHost);
    await disposeAllController!.ready;
    disposeAllHost.disposeAll();
    expect(disposeAllMedia.track.stop).toHaveBeenCalledTimes(1);
  });
});
