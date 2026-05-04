import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRenderState } from '@/tools/video-editor/hooks/useRenderState';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

const mocks = vi.hoisted(() => ({
  startClientRender: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useClientRender', () => ({
  useClientRender: () => mocks.startClientRender,
}));

vi.mock('@/tools/video-editor/lib/renderRouter', () => ({
  decideRenderRoute: (timeline: ResolvedTimelineConfig | null | undefined) => {
    const clip = timeline?.clips?.[0];
    if (clip?.generation?.sequence_lane === 'remotion_module' && !clip?.generation?.artifact_id) {
      return {
        route: 'preview-only',
        hasThemedClip: false,
        hasMediaClip: false,
        reason: 'remotion_module_missing_artifact',
      };
    }

    if (clip?.clipType === 'generated-module') {
      return {
        route: 'worker-banodoco',
        hasThemedClip: false,
        hasMediaClip: false,
        reason: 'generated_remotion_module',
      };
    }

    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: true,
      reason: 'pure_native_clips',
    };
  },
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

describe('useRenderState render routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
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

  it('blocks malformed remotion_module metadata without invoking the client renderer', async () => {
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

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Render blocked');
    expect(result.current.renderLog).toContain('remotion_module_missing_artifact');
  });

  it('surfaces worker-unavailable state for valid remotion_module routes without client fallback', async () => {
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

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Worker render unavailable');
    expect(result.current.renderLog).toContain('generated_remotion_module');
  });
});
