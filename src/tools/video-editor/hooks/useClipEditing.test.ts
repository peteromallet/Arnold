import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Shot } from '@/domains/generation/types';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { patchAffectsDuration, recalcActionEnd } from '@/tools/video-editor/lib/clip-editing-utils';
import { getConfigSignature } from '@/tools/video-editor/lib/config-utils';
import { useClipEditing } from '@/tools/video-editor/hooks/useClipEditing';
import { usePinnedGroupSync, usePinnedShotGroups } from '@/tools/video-editor/hooks/usePinnedShotGroups';
import { useSwitchToFinalVideo } from '@/tools/video-editor/hooks/useSwitchToFinalVideo';
import { repairConfig } from '@/tools/video-editor/lib/migrate';
import { configToRows, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { TimelineEventBus } from '@/tools/video-editor/hooks/useTimelineEventBus';
import { useTimelineCommit } from '@/tools/video-editor/hooks/useTimelineCommit';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';
import { extractVideoMetadataFromUrl } from '@/shared/lib/media/videoMetadata';

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

vi.mock('@/shared/lib/media/videoMetadata', () => ({
  extractVideoMetadataFromUrl: vi.fn(),
}));

const mockedExtractVideoMetadataFromUrl = vi.mocked(extractVideoMetadataFromUrl);

const makePinnedGroup = (args: {
  shotId: string;
  trackId: string;
  clipIds: string[];
  mode?: 'images' | 'video';
  videoAssetKey?: string;
  imageClipSnapshot?: TimelineConfig['pinnedShotGroups'] extends Array<infer Group>
    ? Group extends { imageClipSnapshot?: infer Snapshot } ? Snapshot : never
    : never;
}) => ({
  shotId: args.shotId,
  trackId: args.trackId,
  clipIds: args.clipIds,
  ...(args.mode ? { mode: args.mode } : {}),
  ...(args.videoAssetKey ? { videoAssetKey: args.videoAssetKey } : {}),
  ...(args.imageClipSnapshot ? { imageClipSnapshot: args.imageClipSnapshot } : {}),
});

const makeTimelineData = (overrides?: {
  rows?: TimelineRow[];
  meta?: Record<string, ClipMeta>;
}): TimelineData => ({
  config: { output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' }, clips: [] },
  configVersion: 1,
  registry: { assets: {} },
  resolvedConfig: { output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' }, tracks: [], clips: [], registry: {} },
  rows: overrides?.rows ?? [],
  meta: overrides?.meta ?? {},
  effects: {},
  assetMap: {},
  output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
  tracks: [],
  clipOrder: {},
  signature: 'signature',
  stableSignature: 'stable-signature',
});

function makeConfigTimelineData(config: TimelineConfig, registry: AssetRegistry): TimelineData {
  const canonicalConfig = repairConfig(config);
  const rowData = configToRows(canonicalConfig);

  return {
    config: canonicalConfig,
    configVersion: 1,
    registry,
    resolvedConfig: {
      output: { ...canonicalConfig.output },
      tracks: (canonicalConfig.tracks ?? []).map((track) => ({ ...track })),
      clips: canonicalConfig.clips.map((clip) => ({
        ...clip,
        assetEntry: clip.asset ? {
          ...registry.assets[clip.asset],
          src: registry.assets[clip.asset]?.file ?? '',
        } : undefined,
      })),
      registry: Object.fromEntries(
        Object.entries(registry.assets).map(([assetId, entry]) => [
          assetId,
          { ...entry, src: entry.file },
        ]),
      ),
    },
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: Object.fromEntries(Object.entries(registry.assets).map(([assetId, entry]) => [assetId, entry.file])),
    output: { ...canonicalConfig.output },
    tracks: (canonicalConfig.tracks ?? []).map((track) => ({ ...track })),
    clipOrder: rowData.clipOrder,
    signature: 'signature',
    stableSignature: 'stable-signature',
  };
}

describe('useClipEditing duration recalculation', () => {
  it('recalcActionEnd handles speed, from, to, and hold patches', () => {
    const action = { id: 'clip-1', start: 5, end: 9, effectId: 'effect-clip-1' };

    expect(recalcActionEnd(action, { from: 0, to: 4, speed: 2 })).toBe(7);
    expect(recalcActionEnd(action, { from: 1, to: 4, speed: 1 })).toBe(8);
    expect(recalcActionEnd(action, { from: 0, to: 3, speed: 1 })).toBe(8);
    expect(recalcActionEnd(action, { from: 0, to: 3, speed: 2, hold: 10 })).toBe(10);
  });

  it('patchAffectsDuration only flags duration keys', () => {
    expect(patchAffectsDuration({ speed: 2 })).toBe(true);
    expect(patchAffectsDuration({ from: 1 })).toBe(true);
    expect(patchAffectsDuration({ to: 3 })).toBe(true);
    expect(patchAffectsDuration({ hold: 10 })).toBe(true);
    expect(patchAffectsDuration({ x: 20 })).toBe(false);
    expect(patchAffectsDuration({ opacity: 0.5 })).toBe(false);
  });

  it('recalculates action.end for single-clip duration edits', () => {
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeTimelineData({
        rows: [{ id: 'V1', actions: [{ id: 'clip-1', start: 0, end: 4, effectId: 'effect-clip-1' }] }],
        meta: { 'clip-1': { track: 'V1', from: 0, to: 4, speed: 1 } },
      }),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: null,
      selectedClipId: 'clip-1',
      selectedTrack: null,
      currentTime: 0,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleSelectedClipChange({ speed: 2 });
    });

    expect(applyEdit).toHaveBeenCalledWith({
      type: 'rows',
      rows: [{ id: 'V1', actions: [{ id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' }] }],
      metaUpdates: { 'clip-1': { speed: 2 } },
    });
  });

  it('recalculates action.end for bulk duration edits', () => {
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeTimelineData({
        rows: [
          {
            id: 'V1',
            actions: [
              { id: 'clip-1', start: 0, end: 4, effectId: 'effect-clip-1' },
              { id: 'clip-2', start: 4, end: 7, effectId: 'effect-clip-2' },
            ],
          },
        ],
        meta: {
          'clip-1': { track: 'V1', from: 0, to: 4, speed: 1 },
          'clip-2': { track: 'V1', from: 0, to: 3, speed: 1 },
        },
      }),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: null,
      selectedClipId: null,
      selectedTrack: null,
      currentTime: 0,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleUpdateClips(['clip-1', 'clip-2'], { speed: 2 });
    });

    expect(applyEdit).toHaveBeenCalledWith({
      type: 'rows',
      rows: [
        {
          id: 'V1',
          actions: [
            { id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' },
            { id: 'clip-2', start: 4, end: 5.5, effectId: 'effect-clip-2' },
          ],
        },
      ],
      metaUpdates: {
        'clip-1': { speed: 2 },
        'clip-2': { speed: 2 },
      },
    });
  });
});

describe('useClipEditing pinned group guards', () => {
  it('allows explicit full-group deletion through the shot menu path', () => {
    vi.mocked(toast.error).mockClear();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
            { id: 'clip-2', at: 5, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1', 'clip-2'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png' },
            'asset-2': { file: 'two.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: dataRef.current.resolvedConfig,
      selectedClipId: 'clip-1',
      selectedTrack: null,
      currentTime: 0,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleDeleteClips(['clip-1', 'clip-2'], { allowPinnedGroupDelete: true });
    });

    expect(applyEdit).toHaveBeenCalledWith({
      type: 'rows',
      rows: [{ id: 'V1', actions: [] }],
      metaDeletes: ['clip-1', 'clip-2'],
    }, { semantic: true });
  });

  it('blocks grouped clip deletion outside the shot menu path', () => {
    vi.mocked(toast.error).mockClear();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: dataRef.current.resolvedConfig,
      selectedClipId: 'clip-1',
      selectedTrack: null,
      currentTime: 0,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleDeleteClips(['clip-1']);
    });

    expect(applyEdit).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Use Delete shot from the shot menu');
  });

  it('blocks grouped single-clip deletion handlers used by keyboard Backspace/Delete paths', () => {
    vi.mocked(toast.error).mockClear();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: dataRef.current.resolvedConfig,
      selectedClipId: 'clip-1',
      selectedTrack: null,
      currentTime: 0,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleDeleteClip('clip-1');
    });

    expect(applyEdit).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Use Delete shot from the shot menu');
  });

  it('blocks grouped clip split operations used by the keyboard s path', () => {
    vi.mocked(toast.error).mockClear();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useClipEditing({
      dataRef,
      resolvedConfig: dataRef.current.resolvedConfig,
      selectedClipId: 'clip-1',
      selectedTrack: null,
      currentTime: 2,
      selectClip: vi.fn(),
      setSelectedTrackId: vi.fn(),
      applyEdit,
    }));

    act(() => {
      result.current.handleSplitSelectedClip();
    });

    expect(applyEdit).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Use Delete shot from the shot menu');
  });
});

describe('useTimelineCommit pinned shot reconciliation', () => {
  it('applies soft-tag pinned shot group edits without rewriting clip geometry', () => {
    const eventBus = new TimelineEventBus();
    const lastSavedSignatureRef = { current: 'stable-signature' };
    const initialData = makeConfigTimelineData(
      {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        clips: [
          { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 },
          { id: 'clip-2', at: 2, track: 'V1', clipType: 'hold', hold: 2 },
        ],
      },
      { assets: {} },
    );

    const { result } = renderHook(() => useTimelineCommit({ eventBus, lastSavedSignatureRef }));

    act(() => {
      result.current.commitData(initialData, { save: false, selectedTrackId: 'V1' });
    });

    act(() => {
      result.current.applyEdit({
        type: 'pinnedShotGroups',
        pinnedShotGroups: [makePinnedGroup({
          shotId: 'shot-1',
          trackId: 'V1',
          clipIds: ['clip-1', 'clip-2'],
          mode: 'images',
        })],
      });
    });

    expect(result.current.dataRef.current?.resolvedConfig.clips).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'clip-1', at: 0, track: 'V1', hold: 2 }),
      expect.objectContaining({ id: 'clip-2', at: 2, track: 'V1', hold: 2 }),
    ]));
    expect(result.current.dataRef.current?.signature).toBe(
      getConfigSignature(result.current.dataRef.current!.resolvedConfig),
    );
    const projectedGroup = result.current.dataRef.current?.config.pinnedShotGroups?.[0];
    expect(projectedGroup).toEqual({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
    });

    const bypassAttempt = {
      ...result.current.dataRef.current!.resolvedConfig,
      clips: result.current.dataRef.current!.resolvedConfig.clips.map((clip) => ({
        ...clip,
        at: 0,
      })),
    };

    act(() => {
      result.current.applyEdit({
        type: 'config',
        resolvedConfig: bypassAttempt,
        pinnedShotGroupsOverride: [makePinnedGroup({
          shotId: 'shot-1',
          trackId: 'V1',
          clipIds: ['clip-1', 'clip-2'],
          mode: 'images',
        })],
      });
    });

    expect(result.current.dataRef.current?.resolvedConfig.clips).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'clip-1', at: 0, track: 'V1', hold: 2 }),
      expect.objectContaining({ id: 'clip-2', at: 0, track: 'V1', hold: 2 }),
    ]));
    expect(result.current.dataRef.current?.signature).toBe(
      getConfigSignature(result.current.dataRef.current!.resolvedConfig),
    );
  });
});

describe('useSwitchToFinalVideo', () => {
  it('snapshots image clips before switching to video and writes pinnedShotGroupsOverride in one edit', async () => {
    mockedExtractVideoMetadataFromUrl.mockResolvedValue({
      duration_seconds: 8,
      frame_rate: 30,
      total_frames: 240,
      width: 1920,
      height: 1080,
      file_size: 0,
    });
    const applyEdit = vi.fn();
    const patchRegistry = vi.fn();
    const registerAsset = vi.fn(async () => undefined);
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 4, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
            { id: 'clip-2', at: 9, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1', 'clip-2'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png', generationId: 'gen-1' },
            'asset-2': { file: 'two.png', type: 'image/png', generationId: 'gen-2' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useSwitchToFinalVideo({
      applyEdit,
      dataRef,
      finalVideoMap: new Map([['shot-1', { id: 'final-1', location: 'https://example.com/final.mp4', thumbnailUrl: null }]]),
      patchRegistry,
      registerAsset,
    }));

    await act(async () => {
      await result.current.switchToFinalVideo({ shotId: 'shot-1', clipIds: ['clip-1', 'clip-2'], rowId: 'V1' });
    });

    await waitFor(() => {
      expect(applyEdit).toHaveBeenCalledTimes(1);
    });
    const mutation = applyEdit.mock.calls[0][0];
    expect(mutation.type).toBe('rows');
    expect(mutation.metaDeletes).toEqual(['clip-1', 'clip-2']);
    expect(mutation.pinnedShotGroupsOverride).toEqual([expect.objectContaining({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-3'],
      mode: 'video',
      videoAssetKey: expect.any(String),
      imageClipSnapshot: [
        { clipId: 'clip-1', assetKey: 'asset-1', start: 4, end: 9, meta: { clipType: 'hold', hold: 5, opacity: undefined, from: undefined, to: undefined, speed: undefined, volume: undefined, x: undefined, y: undefined, width: undefined, height: undefined, cropTop: undefined, cropBottom: undefined, cropLeft: undefined, cropRight: undefined, text: undefined, entrance: undefined, exit: undefined, continuous: undefined, transition: undefined, effects: undefined } },
        { clipId: 'clip-2', assetKey: 'asset-2', start: 9, end: 14, meta: { clipType: 'hold', hold: 5, opacity: undefined, from: undefined, to: undefined, speed: undefined, volume: undefined, x: undefined, y: undefined, width: undefined, height: undefined, cropTop: undefined, cropBottom: undefined, cropLeft: undefined, cropRight: undefined, text: undefined, entrance: undefined, exit: undefined, continuous: undefined, transition: undefined, effects: undefined } },
      ],
    })]);
    expect(mutation.rows).toEqual([
      {
        id: 'V1',
        actions: [
          { id: 'clip-3', start: 4, end: 12, effectId: 'effect-clip-3' },
        ],
      },
    ]);
    expect(patchRegistry).toHaveBeenCalledTimes(1);
  });

  it('updates a video-mode shot group to the latest final video in one edit', async () => {
    mockedExtractVideoMetadataFromUrl.mockResolvedValue({
      duration_seconds: 6,
      frame_rate: 30,
      total_frames: 180,
      width: 1920,
      height: 1080,
      file_size: 0,
    });
    const applyEdit = vi.fn();
    const patchRegistry = vi.fn();
    const registerAsset = vi.fn(async () => undefined);
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-3', at: 7, track: 'V1', clipType: 'media', asset: 'asset-video', from: 0, to: 10, speed: 1 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-3'],
            mode: 'video',
            videoAssetKey: 'asset-video',
            imageClipSnapshot: [
              { clipId: 'clip-1', assetKey: 'asset-1', start: 7, end: 10, meta: { clipType: 'hold', hold: 3 } },
            ],
          })],
        },
        {
          assets: {
            'asset-video': { file: 'video-old.mp4', type: 'video/mp4', generationId: 'final-old' },
            'asset-1': { file: 'one.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useSwitchToFinalVideo({
      applyEdit,
      dataRef,
      finalVideoMap: new Map([['shot-1', { id: 'final-new', location: 'https://example.com/final-new.mp4', thumbnailUrl: null }]]),
      patchRegistry,
      registerAsset,
    }));

    await act(async () => {
      await result.current.updateToLatestVideo({ shotId: 'shot-1', rowId: 'V1' });
    });

    await waitFor(() => {
      expect(patchRegistry).toHaveBeenCalledTimes(1);
      expect(registerAsset).toHaveBeenCalledTimes(1);
      expect(applyEdit).toHaveBeenCalledTimes(1);
    });

    const mutation = applyEdit.mock.calls[0][0];
    expect(mutation.type).toBe('rows');
    expect(mutation.rows).toEqual([
      {
        id: 'V1',
        actions: [
          { id: 'clip-3', start: 7, end: 13, effectId: 'effect-clip-3' },
        ],
      },
    ]);
    expect(mutation.metaUpdates).toEqual({
      'clip-3': {
        asset: expect.any(String),
        to: 6,
      },
    });
    expect(mutation.pinnedShotGroupsOverride).toEqual([expect.objectContaining({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-3'],
      mode: 'video',
      videoAssetKey: expect.any(String),
      imageClipSnapshot: [
        { clipId: 'clip-1', assetKey: 'asset-1', start: 7, end: 10, meta: { clipType: 'hold', hold: 3 } },
      ],
    })]);
  });

  it('restores image clips from snapshot in one edit when switching back to images', () => {
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-3', at: 7, track: 'V1', clipType: 'media', asset: 'asset-video', from: 0, to: 10, speed: 1 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-3'],
            mode: 'video',
            videoAssetKey: 'asset-video',
            imageClipSnapshot: [
              { clipId: 'clip-1', assetKey: 'asset-1', start: 7, end: 10, meta: { clipType: 'hold', hold: 3 } },
              { clipId: 'clip-2', assetKey: 'asset-2', start: 10, end: 14, meta: { clipType: 'hold', hold: 4 } },
            ],
          })],
        },
        {
          assets: {
            'asset-video': { file: 'video.mp4', type: 'video/mp4' },
            'asset-1': { file: 'one.png', type: 'image/png' },
            'asset-2': { file: 'two.png', type: 'image/png' },
          },
        },
      ),
    };

    const { result } = renderHook(() => useSwitchToFinalVideo({
      applyEdit,
      dataRef,
      finalVideoMap: new Map(),
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(async () => undefined),
    }));

    act(() => {
      result.current.switchToImages({ shotId: 'shot-1', rowId: 'V1' });
    });

    expect(applyEdit).toHaveBeenCalledTimes(1);
    const mutation = applyEdit.mock.calls[0][0];
    expect(mutation.type).toBe('rows');
    expect(mutation.metaDeletes).toEqual(['clip-3']);
    expect(mutation.pinnedShotGroupsOverride).toEqual([expect.objectContaining({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
      imageClipSnapshot: [
        { clipId: 'clip-1', assetKey: 'asset-1', start: 7, end: 10, meta: { clipType: 'hold', hold: 3 } },
        { clipId: 'clip-2', assetKey: 'asset-2', start: 10, end: 14, meta: { clipType: 'hold', hold: 4 } },
      ],
    })]);
    expect(mutation.rows).toEqual([
      {
        id: 'V1',
        actions: [
          { id: 'clip-1', start: 7, end: 10, effectId: 'effect-clip-1' },
          { id: 'clip-2', start: 10, end: 14, effectId: 'effect-clip-2' },
        ],
      },
    ]);
  });
});

describe('usePinnedShotGroups', () => {
  it('pins groups from config clip geometry instead of raw selection order', () => {
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 4, track: 'V1', clipType: 'hold', hold: 2 },
            { id: 'clip-2', at: 1, track: 'V1', clipType: 'hold', hold: 3 },
          ],
        },
        { assets: {} },
      ),
    };

    const { result } = renderHook(() => usePinnedShotGroups({
      dataRef,
      applyEdit,
    }));

    act(() => {
      result.current.pinGroup('shot-1', 'V1', ['clip-1', 'clip-2']);
    });

    expect(applyEdit).toHaveBeenCalledWith({
      type: 'pinnedShotGroups',
      pinnedShotGroups: [makePinnedGroup({
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-2', 'clip-1'],
        mode: 'images',
      })],
    });
  });
});

describe('usePinnedGroupSync', () => {
  it('debounces image-mode sync and applies rows edits through applyEdit', () => {
    vi.useFakeTimers();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png', generationId: 'gen-1' },
          },
        },
      ),
    };
    const shots: Shot[] = [{
      id: 'shot-1',
      name: 'Shot 1',
      images: [
        { generation_id: 'gen-1', imageUrl: 'https://example.com/one.png', type: 'image/png', timeline_frame: 0 },
        { generation_id: 'gen-2', imageUrl: 'https://example.com/two.png', type: 'image/png', timeline_frame: 1 },
      ],
    } as Shot];
    const registerGenerationAsset = vi.fn((generation: { generationId: string; imageUrl: string }) => {
      const assetId = 'asset-2';
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: 'image/png',
        generationId: generation.generationId,
      };
      return assetId;
    });

    renderHook(() => usePinnedGroupSync({
      data: dataRef.current,
      dataRef,
      applyEdit,
      shots,
      registerGenerationAsset,
      debounceMs: 25,
    }));

    act(() => {
      vi.advanceTimersByTime(24);
    });
    expect(applyEdit).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(applyEdit).toHaveBeenCalledTimes(1);
    const mutation = applyEdit.mock.calls[0][0];
    expect(mutation.type).toBe('rows');
    expect(mutation.pinnedShotGroupsOverride).toEqual([expect.objectContaining({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
    })]);
    vi.useRealTimers();
  });

  it('re-arms pinned-group sync until resize interaction ends', () => {
    vi.useFakeTimers();
    const applyEdit = vi.fn();
    const interactionStateRef = { current: { drag: false, resize: true } };
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png', generationId: 'gen-1' },
          },
        },
      ),
    };

    renderHook(() => usePinnedGroupSync({
      data: dataRef.current,
      dataRef,
      applyEdit,
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/one.png', type: 'image/png', timeline_frame: 0 },
          { generation_id: 'gen-2', imageUrl: 'https://example.com/two.png', type: 'image/png', timeline_frame: 1 },
        ],
      } as Shot],
      registerGenerationAsset: vi.fn(() => {
        dataRef.current.registry.assets['asset-2'] = {
          file: 'https://example.com/two.png',
          type: 'image/png',
          generationId: 'gen-2',
        };
        return 'asset-2';
      }),
      isInteractionActive: () => interactionStateRef.current.drag || interactionStateRef.current.resize,
      debounceMs: 25,
    }));

    act(() => {
      vi.advanceTimersByTime(25);
    });
    expect(applyEdit).not.toHaveBeenCalled();

    interactionStateRef.current.resize = false;

    act(() => {
      vi.advanceTimersByTime(24);
    });
    expect(applyEdit).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(applyEdit).toHaveBeenCalledTimes(1);
    expect(applyEdit.mock.calls[0][0]).toEqual(expect.objectContaining({
      type: 'rows',
      pinnedShotGroupsOverride: [expect.objectContaining({
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-1', 'clip-2'],
      })],
    }));
    vi.useRealTimers();
  });

  it('does not sync pinned groups that are in video mode', () => {
    vi.useFakeTimers();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'media', asset: 'asset-1', from: 0, to: 5, speed: 1 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'video',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'video.mp4', type: 'video/mp4', generationId: 'final-1' },
          },
        },
      ),
    };

    renderHook(() => usePinnedGroupSync({
      data: dataRef.current,
      dataRef,
      applyEdit,
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [{ generation_id: 'gen-1', imageUrl: 'https://example.com/one.png', type: 'image/png' }],
      } as Shot],
      registerGenerationAsset: vi.fn(),
      debounceMs: 25,
    }));

    act(() => {
      vi.advanceTimersByTime(25);
    });

    expect(applyEdit).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('skips pinned image sync entries that have no usable media URL', () => {
    vi.useFakeTimers();
    const applyEdit = vi.fn();
    const registerGenerationAsset = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png', generationId: 'gen-1' },
          },
        },
      ),
    };

    renderHook(() => usePinnedGroupSync({
      data: dataRef.current,
      dataRef,
      applyEdit,
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/one.png', type: 'image/png', timeline_frame: 0 },
          { generation_id: 'gen-2', imageUrl: '   ', type: 'image/png', timeline_frame: 1 },
        ],
      } as Shot],
      registerGenerationAsset,
      debounceMs: 25,
    }));

    act(() => {
      vi.advanceTimersByTime(25);
    });

    expect(registerGenerationAsset).not.toHaveBeenCalled();
    expect(applyEdit).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('re-arms sync while interactions are active and rebuilds clipIds from the live row order once it applies', () => {
    vi.useFakeTimers();
    const applyEdit = vi.fn();
    const dataRef = {
      current: makeConfigTimelineData(
        {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [
            { id: 'clip-1', at: 7, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 5 },
          ],
          pinnedShotGroups: [makePinnedGroup({
            shotId: 'shot-1',
            trackId: 'V1',
            clipIds: ['clip-1'],
            mode: 'images',
          })],
        },
        {
          assets: {
            'asset-1': { file: 'one.png', type: 'image/png', generationId: 'gen-1' },
          },
        },
      ),
    };
    const shots: Shot[] = [{
      id: 'shot-1',
      name: 'Shot 1',
      images: [
        { generation_id: 'gen-1', imageUrl: 'https://example.com/one.png', type: 'image/png', timeline_frame: 0 },
        { generation_id: 'gen-2', imageUrl: 'https://example.com/two.png', type: 'image/png', timeline_frame: 1 },
      ],
    } as Shot];
    const registerGenerationAsset = vi.fn((generation: { generationId: string; imageUrl: string }) => {
      const assetId = 'asset-2';
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: 'image/png',
        generationId: generation.generationId,
      };
      return assetId;
    });
    let interactionActive = true;

    renderHook(() => usePinnedGroupSync({
      data: dataRef.current,
      dataRef,
      applyEdit,
      shots,
      registerGenerationAsset,
      isInteractionActive: () => interactionActive,
      debounceMs: 25,
    }));

    act(() => {
      vi.advanceTimersByTime(25);
    });

    expect(applyEdit).not.toHaveBeenCalled();

    interactionActive = false;

    act(() => {
      vi.advanceTimersByTime(24);
    });

    expect(applyEdit).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(applyEdit).toHaveBeenCalledTimes(1);
    expect(applyEdit.mock.calls[0][0].pinnedShotGroupsOverride).toEqual([expect.objectContaining({
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
    })]);
    vi.useRealTimers();
  });
});
