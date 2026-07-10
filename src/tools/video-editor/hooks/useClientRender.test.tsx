import { act, renderHook } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from '@/shared/components/ui/toast.tsx';
import { useClientRender } from '@/tools/video-editor/hooks/useClientRender';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

vi.mock('@/shared/components/ui/toast.tsx', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

const resolvedConfig: ResolvedTimelineConfig = {
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'out.mp4',
  },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips: [
    {
      id: 'clip-1',
      trackId: 'V1',
      start: 0,
      duration: 60,
      media: { type: 'video', src: 'https://example.test/video.mp4' },
    },
  ],
  registry: {},
};

const metadata = {
  fps: 30,
  durationInFrames: 60,
  compositionWidth: 1920,
  compositionHeight: 1080,
};

function makeStateSetter<T>(initialValue: T) {
  let currentValue = initialValue;
  const setter = vi.fn((nextValue: SetStateAction<T>) => {
    currentValue = typeof nextValue === 'function'
      ? (nextValue as (value: T) => T)(currentValue)
      : nextValue;
  }) as unknown as Dispatch<SetStateAction<T>>;

  return {
    setter,
    get value() {
      return currentValue;
    },
  };
}

describe('useClientRender', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('VideoEncoder', undefined);
  });

  it('returns structured blocker provenance when WebCodecs is unsupported', async () => {
    const renderStatus = makeStateSetter<'idle' | 'rendering' | 'done' | 'error'>('idle');
    const renderProgress = makeStateSetter<{ current: number; total: number; percent: number; phase: string } | null>(null);
    const renderLog = makeStateSetter('');
    const renderDirty = makeStateSetter(true);
    const renderResult = makeStateSetter<{ url: string | null; filename: string | null }>({
      url: null,
      filename: null,
    });

    const { result } = renderHook(() => useClientRender({
      resolvedConfig,
      metadata,
      setRenderStatus: renderStatus.setter,
      setRenderProgress: renderProgress.setter,
      setRenderLog: renderLog.setter,
      setRenderDirty: renderDirty.setter,
      setRenderResult: renderResult.setter,
    }));

    let clientRenderResult: Awaited<ReturnType<typeof result.current>> | undefined;
    await act(async () => {
      clientRenderResult = await result.current();
    });

    expect(clientRenderResult).toEqual({
      status: 'error',
      message: 'WebCodecs not supported in this browser',
      blocker: {
        id: 'client-render.webcodecs.browser-export.route-unsupported',
        severity: 'error',
        route: 'browser-export',
        reason: 'route-unsupported',
        message: 'WebCodecs not supported in this browser',
        detail: {
          source: 'use-client-render',
          phase: 'webcodecs-preflight',
          api: 'VideoEncoder',
        },
      },
    });
    expect(renderStatus.value).toBe('error');
    expect(renderLog.value).toBe('WebCodecs not supported in this browser');
    expect(renderProgress.setter).not.toHaveBeenCalled();
    expect(renderDirty.setter).not.toHaveBeenCalled();
    expect(renderResult.setter).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('WebCodecs not supported in this browser');
    expect(toast.success).not.toHaveBeenCalled();
  });
});
