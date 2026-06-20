/**
 * live-webcam-canary — M11 browser webcam live-data canary extension.
 *
 * Demonstrates the webcam path from browser permission to provider-scoped
 * frame channel, live-frame-preview metadata, and deterministic bake refs.
 *
 * This file must not import editor internals. It uses only the public SDK.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  DisposeHandle,
  ExtensionContext,
  LiveBakeResult,
  LiveChannelDescriptor,
  LiveSampleFrame,
  LiveSourceDiagnostic,
  ReighExtension,
} from '@reigh/editor-sdk';

const EXTENSION_ID = 'com.reigh.examples.live-webcam-canary';
const SOURCE_ID = `${EXTENSION_ID}:webcam`;
const BINDING_ID = `${EXTENSION_ID}:preview-binding`;
const PREVIEW_CLIP_ID = `${EXTENSION_ID}:preview`;
const DEFAULT_WIDTH = 640;
const DEFAULT_HEIGHT = 360;

type CanvasLike = HTMLCanvasElement & {
  toDataURL(type?: string, quality?: unknown): string;
};

export interface LiveWebcamCanarySession {
  readonly sourceId: string;
  readonly channelId: LiveChannelDescriptor;
  readonly stream: MediaStream;
  readonly previewClip: Record<string, unknown>;
}

export interface LiveWebcamCanaryController extends DisposeHandle {
  readonly sourceId: string;
  readonly channelId: LiveChannelDescriptor | undefined;
  readonly previewClip: Record<string, unknown>;
  readonly ready: Promise<LiveWebcamCanarySession | null>;
  captureOnce(): Promise<boolean>;
  bakeImage(ref?: string): LiveBakeResult;
  bakeVideo(ref?: string): LiveBakeResult;
  bakeRenderMaterial(ref?: string): LiveBakeResult;
}

export interface LiveWebcamCanaryOptions {
  readonly sourceId?: string;
  readonly bindingId?: string;
  readonly previewClipId?: string;
  readonly width?: number;
  readonly height?: number;
  readonly captureIntervalMs?: number;
  readonly autoCapture?: boolean;
  readonly disposeSourceOnDispose?: boolean;
  readonly now?: () => number;
  readonly onReady?: (controller: LiveWebcamCanaryController) => void;
}

function report(
  ctx: ExtensionContext,
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  const diagnostic: LiveSourceDiagnostic = {
    severity,
    code,
    message,
    sourceId: SOURCE_ID,
    detail,
  };
  ctx.services.diagnostics.report({
    severity,
    code,
    message,
    detail,
  });
  return diagnostic;
}

function stopStream(stream: MediaStream | null): void {
  if (!stream) return;
  for (const track of stream.getTracks()) {
    try {
      track.stop();
    } catch {
      // MediaTrack.stop() is best-effort during teardown.
    }
  }
}

function makePreviewClip(options: {
  sourceId: string;
  bindingId: string;
  channelId?: string;
  clipId: string;
  width: number;
  height: number;
}): Record<string, unknown> {
  const binding = {
    bindingId: options.bindingId,
    sourceId: options.sourceId,
    sourceKind: 'webcam',
    channelId: options.channelId,
    ownerExtensionId: EXTENSION_ID,
    sampling: { mode: 'latest' },
    placeholder: {
      label: 'Live Webcam Canary',
      progress: 0,
    },
    metadata: {
      canary: 'live-webcam',
      preview: true,
    },
  };

  return {
    id: options.clipId,
    at: 0,
    duration: 2,
    track: 'V1',
    clipType: 'live-frame-preview',
    params: {
      livePreview: true,
      liveBindings: [binding],
      width: options.width,
      height: options.height,
    },
    app: {
      livePreview: true,
      live: {
        bindings: [binding],
      },
    },
  };
}

export function createLiveWebcamPreviewClip(
  channelId?: LiveChannelDescriptor,
  options: Partial<LiveWebcamCanaryOptions> = {},
): Record<string, unknown> {
  return makePreviewClip({
    sourceId: options.sourceId ?? SOURCE_ID,
    bindingId: options.bindingId ?? BINDING_ID,
    clipId: options.previewClipId ?? PREVIEW_CLIP_ID,
    channelId,
    width: options.width ?? DEFAULT_WIDTH,
    height: options.height ?? DEFAULT_HEIGHT,
  });
}

export function startLiveWebcamCanary(
  ctx: ExtensionContext,
  options: LiveWebcamCanaryOptions = {},
): LiveWebcamCanaryController {
  const sourceId = options.sourceId ?? SOURCE_ID;
  const bindingId = options.bindingId ?? BINDING_ID;
  const width = options.width ?? DEFAULT_WIDTH;
  const height = options.height ?? DEFAULT_HEIGHT;
  const now = options.now ?? (() => (typeof performance === 'undefined' ? Date.now() : performance.now()));
  const captureIntervalMs = options.captureIntervalMs ?? 250;
  const disposeSourceOnDispose = options.disposeSourceOnDispose ?? false;

  let disposed = false;
  let stream: MediaStream | null = null;
  let video: HTMLVideoElement | null = null;
  let canvas: CanvasLike | null = null;
  let channelId: LiveChannelDescriptor | undefined;
  let frameIndex = 0;
  let interval: ReturnType<typeof setInterval> | null = null;
  let sourceHandle: DisposeHandle | null = null;
  const imageBitmaps: Array<{ close?: () => void }> = [];

  const previewClip = () => createLiveWebcamPreviewClip(channelId, {
    sourceId,
    bindingId,
    width,
    height,
    previewClipId: options.previewClipId,
  });

  const cleanupBrowserResources = () => {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
    for (const bitmap of imageBitmaps.splice(0)) {
      try {
        bitmap.close?.();
      } catch {
        // Ignore ImageBitmap close failures during cleanup.
      }
    }
    stopStream(stream);
    stream = null;
    if (video) {
      try {
        video.pause();
        video.srcObject = null;
      } catch {
        // Ignore media element teardown differences across browsers/tests.
      }
      video = null;
    }
    canvas = null;
    if (channelId) {
      ctx.creative.sessions.closeChannel(channelId);
      channelId = undefined;
    }
  };

  const disposeSource = () => {
    if (!sourceHandle) return;
    sourceHandle.dispose();
    sourceHandle = null;
  };

  const failBeforeReady = (
    severity: LiveSourceDiagnostic['severity'],
    code: string,
    message: string,
    detail?: Record<string, unknown>,
  ): null => {
    report(ctx, severity, code, message, detail);
    cleanupBrowserResources();
    disposeSource();
    return null;
  };

  const captureOnce = async (): Promise<boolean> => {
    if (disposed || !channelId || !video || !canvas) return false;
    const context = canvas.getContext('2d');
    if (!context || typeof context.drawImage !== 'function') {
      report(ctx, 'error', 'live-webcam/canvas-unavailable', 'Canvas 2D capture is unavailable for webcam preview.');
      return false;
    }

    context.drawImage(video, 0, 0, width, height);

    if (typeof createImageBitmap === 'function') {
      try {
        const bitmap = await createImageBitmap(canvas);
        imageBitmaps.push(bitmap);
      } catch (err) {
        report(ctx, 'warning', 'live-webcam/image-bitmap-unavailable', 'ImageBitmap creation failed; using canvas data URL only.', {
          error: String(err),
        });
      }
    }

    const src = canvas.toDataURL('image/png');
    const timestamp = now();
    const frame: LiveSampleFrame = {
      timestamp,
      format: 'json',
      data: {
        src,
        state: 'final',
        progress: 100,
        frameIndex,
        width,
        height,
      },
      metadata: {
        frameIndex,
        width,
        height,
        capturedAt: new Date().toISOString(),
      },
    };
    frameIndex += 1;
    ctx.creative.sessions.pushSample(channelId, frame);
    return true;
  };

  sourceHandle = ctx.creative.sessions.registerSource({
    id: sourceId,
    kind: 'webcam',
    label: 'Live Webcam Canary',
    permission: {
      state: 'prompt',
      reason: 'Capture live webcam frames for the M11 canary preview.',
      requestedAt: new Date().toISOString(),
    },
    recording: {
      active: false,
      mode: 'stream',
    },
    metadata: {
      canary: 'live-webcam',
      ownerExtensionId: EXTENSION_ID,
    },
  });

  const ready = (async (): Promise<LiveWebcamCanarySession | null> => {
    const mediaDevices = typeof navigator === 'undefined' ? undefined : navigator.mediaDevices;
    if (!mediaDevices || typeof mediaDevices.getUserMedia !== 'function') {
      return failBeforeReady(
        'error',
        'live-webcam/unsupported',
        'Webcam capture is unavailable because navigator.mediaDevices.getUserMedia is not supported.',
      );
    }

    try {
      stream = await mediaDevices.getUserMedia({ video: { width, height }, audio: false });
    } catch (err) {
      return failBeforeReady(
        'error',
        'live-webcam/permission-denied',
        'Webcam permission was denied or the camera could not be opened.',
        { error: String(err) },
      );
    }

    if (disposed || !stream) {
      stopStream(stream);
      return null;
    }

    channelId = ctx.creative.sessions.openChannel(sourceId, 'video', {
      label: 'Webcam frames',
      width,
      height,
      canary: 'live-webcam',
    });
    video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    canvas = document.createElement('canvas') as CanvasLike;
    canvas.width = width;
    canvas.height = height;

    try {
      await video.play();
    } catch (err) {
      report(ctx, 'warning', 'live-webcam/video-play-warning', 'Webcam video element could not autoplay; frame capture can still be driven manually.', {
        error: String(err),
      });
    }

    if (options.autoCapture ?? true) {
      void captureOnce();
      if (captureIntervalMs > 0) {
        interval = setInterval(() => {
          void captureOnce();
        }, captureIntervalMs);
      }
    }

    report(ctx, 'info', 'live-webcam/stream-ready', 'Live webcam canary stream is ready.', {
      sourceId,
      channelId,
      width,
      height,
    });

    return {
      sourceId,
      channelId,
      stream,
      previewClip: previewClip(),
    };
  })();

  const controller: LiveWebcamCanaryController = {
    sourceId,
    get channelId() {
      return channelId;
    },
    get previewClip() {
      return previewClip();
    },
    ready,
    captureOnce,
    bakeImage(ref = `${sourceId}:image-asset`) {
      return ctx.creative.sessions.bake({
        sourceId,
        channelIds: channelId ? [channelId] : undefined,
        targets: [{ kind: 'asset', ref, params: { mediaKind: 'image' } }],
      });
    },
    bakeVideo(ref = `${sourceId}:video-asset`) {
      return ctx.creative.sessions.bake({
        sourceId,
        channelIds: channelId ? [channelId] : undefined,
        targets: [{ kind: 'asset', ref, params: { mediaKind: 'video' } }],
      });
    },
    bakeRenderMaterial(ref = `${sourceId}:render-material`) {
      return ctx.creative.sessions.bake({
        sourceId,
        channelIds: channelId ? [channelId] : undefined,
        targets: [{
          kind: 'render-material',
          ref,
          params: {
            producerExtensionId: EXTENSION_ID,
            producerVersion: '1.0.0',
          },
        }],
      });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cleanupBrowserResources();
      if (disposeSourceOnDispose) {
        disposeSource();
      }
    },
  };

  options.onReady?.(controller);

  return controller;
}

export function createLiveWebcamCanaryExtension(
  options: LiveWebcamCanaryOptions = {},
): ReighExtension {
  return defineExtension({
    manifest: {
      id: EXTENSION_ID as any,
      version: '1.0.0',
      label: 'Live Webcam Canary',
      description: 'M11 canary for webcam permission, frame channels, live preview, bake, and cleanup.',
      apiVersion: 1,
      contributions: [
        {
          id: 'live-webcam-canary-preview' as any,
          kind: 'clipType',
          clipTypeId: 'live-frame-preview',
          label: 'Live Webcam Preview',
          order: 10,
        } as any,
      ],
      messages: {
        'activation.started': 'Live Webcam Canary activating.',
        'activation.ready': 'Live Webcam Canary ready.',
        'activation.disposed': 'Live Webcam Canary disposed.',
      },
    } as any,
    activate(ctx) {
      return startLiveWebcamCanary(ctx, options);
    },
  });
}

export const liveWebcamCanaryExtension = createLiveWebcamCanaryExtension();

export default liveWebcamCanaryExtension;
