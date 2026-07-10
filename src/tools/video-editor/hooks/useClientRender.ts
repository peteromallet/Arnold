import { useCallback } from 'react';
import type { ComponentType, Dispatch, SetStateAction } from 'react';
import { toast } from '@/shared/components/ui/toast.tsx';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer.tsx';
import type { RenderBlocker } from '@/tools/video-editor/runtime/renderability.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

type RenderStatus = 'idle' | 'rendering' | 'done' | 'error';
type RenderProgress = { current: number; total: number; percent: number; phase: string } | null;
type RenderResult = { url: string | null; filename: string | null };

interface CompositionMetadata {
  fps: number;
  durationInFrames: number;
  compositionWidth: number;
  compositionHeight: number;
}

interface UseClientRenderOptions {
  resolvedConfig: ResolvedTimelineConfig | null;
  metadata: CompositionMetadata | null;
  setRenderStatus: Dispatch<SetStateAction<RenderStatus>>;
  setRenderProgress: Dispatch<SetStateAction<RenderProgress>>;
  setRenderLog: Dispatch<SetStateAction<string>>;
  setRenderDirty: Dispatch<SetStateAction<boolean>>;
  setRenderResult: Dispatch<SetStateAction<RenderResult>>;
}

export interface ClientRenderExecutionResult {
  status: 'done' | 'error';
  message: string;
  blocker?: RenderBlocker;
}

interface CanRenderIssue {
  message?: string;
}

interface WebRendererModule {
  canRenderMediaOnWeb: (options: Record<string, unknown>) => Promise<{
    canRender?: boolean;
    issues?: CanRenderIssue[];
    resolvedVideoCodec?: string;
    resolvedAudioCodec?: string | null;
  }>;
  renderMediaOnWeb: (options: Record<string, unknown>) => Promise<unknown>;
}

const FREE_LICENSE_KEY = 'free-license';

let webRendererCache: WebRendererModule | null = null;

const getWebRendererModule = async (): Promise<WebRendererModule> => {
  if (webRendererCache) return webRendererCache;

  try {
    const mod = await import('@remotion/web-renderer') as unknown as WebRendererModule;
    webRendererCache = mod;
    return mod;
  } catch (err) {
    console.error('[useClientRender] Failed to import @remotion/web-renderer:', err);
    throw new Error(
      'Could not load @remotion/web-renderer. Make sure the package is installed: npm install @remotion/web-renderer',
    );
  }
};

const appendLogLine = (setRenderLog: UseClientRenderOptions['setRenderLog'], message: string) => {
  setRenderLog((current) => current ? `${current}\n${message}` : message);
};

const getFileExtension = (videoCodec: string | undefined) => {
  if (!videoCodec) {
    return 'mp4';
  }

  if (videoCodec.startsWith('vp') || videoCodec.includes('av1')) {
    return 'webm';
  }

  return 'mp4';
};

const getMimeType = (extension: string) => extension === 'webm' ? 'video/webm' : 'video/mp4';

const createWebCodecsUnsupportedBlocker = (message: string): RenderBlocker => ({
  id: 'client-render.webcodecs.browser-export.route-unsupported',
  severity: 'error',
  route: 'browser-export',
  reason: 'route-unsupported',
  message,
  detail: {
    source: 'use-client-render',
    phase: 'webcodecs-preflight',
    api: 'VideoEncoder',
  },
});

const getBlobFromResult = async (
  result: unknown,
  extension: string,
): Promise<Blob | null> => {
  if (result instanceof Blob) {
    return result;
  }

  if (result instanceof ArrayBuffer) {
    return new Blob([result], { type: getMimeType(extension) });
  }

  if (ArrayBuffer.isView(result)) {
    return new Blob([result.buffer.slice(result.byteOffset, result.byteOffset + result.byteLength)], {
      type: getMimeType(extension),
    });
  }

  if (!result || typeof result !== 'object') {
    return null;
  }

  const record = result as Record<string, unknown>;

  // @remotion/web-renderer returns { getBlob: () => Promise<Blob> }
  if (typeof record.getBlob === 'function') {
    return await (record.getBlob as () => Promise<Blob>)();
  }

  const blobCandidate = record.blob ?? record.result ?? record.data;
  if (blobCandidate instanceof Blob) {
    return blobCandidate;
  }

  const bufferCandidate = record.arrayBuffer ?? record.buffer;
  if (bufferCandidate instanceof ArrayBuffer) {
    return new Blob([bufferCandidate], { type: getMimeType(extension) });
  }

  if (typeof record.save === 'function') {
    const saveResult = await (record.save as () => Promise<unknown>)();
    return getBlobFromResult(saveResult, extension);
  }

  return null;
};

const getProgressUpdate = (
  value: unknown,
  fallbackTotal: number,
): NonNullable<RenderProgress> => {
  if (typeof value === 'number') {
    const current = Math.min(fallbackTotal, Math.max(1, Math.floor(value) + 1));
    return {
      current,
      total: fallbackTotal,
      percent: Math.round((current / Math.max(1, fallbackTotal)) * 100),
      phase: 'rendering',
    };
  }

  if (!value || typeof value !== 'object') {
    return {
      current: 0,
      total: fallbackTotal,
      percent: 0,
      phase: 'rendering',
    };
  }

  const record = value as Record<string, unknown>;

  // @remotion/web-renderer passes { progress: 0..1, renderedFrames, encodedFrames, ... }
  if (typeof record.progress === 'number' && record.progress >= 0 && record.progress <= 1) {
    const percent = Math.round(record.progress * 100);
    const current = typeof record.renderedFrames === 'number' ? record.renderedFrames : Math.round(record.progress * fallbackTotal);
    return {
      current,
      total: fallbackTotal,
      percent,
      phase: 'rendering',
    };
  }

  const total = typeof record.total === 'number'
    ? record.total
    : typeof record.totalFrames === 'number'
      ? record.totalFrames
      : fallbackTotal;
  const current = typeof record.current === 'number'
    ? record.current
    : typeof record.frame === 'number'
      ? record.frame + 1
      : 0;
  const percent = typeof record.percent === 'number'
    ? record.percent
    : Math.round((current / Math.max(1, total)) * 100);
  const phase = typeof record.phase === 'string' ? record.phase : 'rendering';

  return {
    current: Math.min(total, Math.max(0, current)),
    total,
    percent: Math.max(0, Math.min(100, Math.round(percent))),
    phase,
  };
};

export function useClientRender({
  resolvedConfig,
  metadata,
  setRenderStatus,
  setRenderProgress,
  setRenderLog,
  setRenderDirty,
  setRenderResult,
}: UseClientRenderOptions) {
  return useCallback(async () => {
    if (!resolvedConfig || !metadata) {
      const message = 'Timeline is not ready to render yet';
      toast.error(message);
      return { status: 'error', message } satisfies ClientRenderExecutionResult;
    }

    if (typeof VideoEncoder === 'undefined') {
      const message = 'WebCodecs not supported in this browser';
      const blocker = createWebCodecsUnsupportedBlocker(message);
      setRenderStatus('error');
      appendLogLine(setRenderLog, message);
      toast.error(message);
      return { status: 'error', message, blocker } satisfies ClientRenderExecutionResult;
    }

    setRenderStatus('rendering');
    setRenderProgress({
      current: 0,
      total: metadata.durationInFrames,
      percent: 0,
      phase: 'preparing',
    });
    setRenderResult({ url: null, filename: null });
    setRenderLog('');
    try {
      const { canRenderMediaOnWeb, renderMediaOnWeb } = await getWebRendererModule();

      // Ensure dimensions are even (H264 requires multiples of 2)
      const width = metadata.compositionWidth % 2 === 0 ? metadata.compositionWidth : metadata.compositionWidth + 1;
      const height = metadata.compositionHeight % 2 === 0 ? metadata.compositionHeight : metadata.compositionHeight + 1;

      // canRenderMediaOnWeb expects width/height as top-level options
      const canRenderOptions = {
        width,
        height,
        videoCodec: 'h264',
        audioCodec: 'aac',
      } satisfies Record<string, unknown>;

      const canRender = await canRenderMediaOnWeb(canRenderOptions);
      if (!canRender.canRender) {
        const message = canRender.issues?.map((issue) => issue.message).filter(Boolean).join('\n')
          || 'This browser cannot render the selected video format.';
        throw new Error(message);
      }

      const resolvedVideoCodec = canRender.resolvedVideoCodec ?? 'h264';
      const resolvedAudioCodec = canRender.resolvedAudioCodec ?? null;
      const extension = getFileExtension(resolvedVideoCodec);
      appendLogLine(setRenderLog, `Rendering ${width}x${height} @ ${metadata.fps}fps with ${resolvedVideoCodec}${resolvedAudioCodec ? ` + ${resolvedAudioCodec}` : ''}`);

      // renderMediaOnWeb expects a composition object
      const composition = {
        id: 'video-editor-timeline-renderer',
        component: TimelineRenderer as ComponentType<{ config: ResolvedTimelineConfig }>,
        fps: metadata.fps,
        width,
        height,
        durationInFrames: metadata.durationInFrames,
      };

      const renderResult = await renderMediaOnWeb({
        composition,
        inputProps: { config: resolvedConfig },
        licenseKey: FREE_LICENSE_KEY,
        videoCodec: resolvedVideoCodec,
        audioCodec: resolvedAudioCodec,
        onProgress: (progress: unknown) => {
          setRenderProgress(getProgressUpdate(progress, metadata.durationInFrames));
        },
      } satisfies Record<string, unknown>);

      const blob = await getBlobFromResult(renderResult, extension);
      if (!blob) {
        throw new Error('Browser renderer completed without a downloadable file');
      }

      const filename = `timeline-render-${new Date().toISOString().replace(/[:.]/g, '-')}.${extension}`;
      const url = URL.createObjectURL(blob);
      setRenderProgress({
        current: metadata.durationInFrames,
        total: metadata.durationInFrames,
        percent: 100,
        phase: 'done',
      });
      setRenderDirty(false);
      setRenderResult({ url, filename });
      setRenderStatus('done');
      appendLogLine(setRenderLog, `Saved ${filename}`);
      toast.success('Render complete');
      return { status: 'done', message: `Saved ${filename}` } satisfies ClientRenderExecutionResult;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown render error';
      setRenderStatus('error');
      appendLogLine(setRenderLog, message);
      toast.error('Render failed', { description: message });
      return { status: 'error', message } satisfies ClientRenderExecutionResult;
    }
  }, [
    metadata,
    resolvedConfig,
    setRenderDirty,
    setRenderLog,
    setRenderProgress,
    setRenderResult,
    setRenderStatus,
  ]);
}
