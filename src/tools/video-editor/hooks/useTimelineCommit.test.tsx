// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useTimelineCommit } from './useTimelineCommit';
import { TimelineEventBus } from './useTimelineEventBus';
import { configToRows, type TimelineData } from '../lib/timeline-data';
import { getConfigSignature, getStableConfigSignature } from '../lib/config-utils';
import type { PinnedShotImageClipSnapshot, TimelineConfig } from '../types';

function makeVideoModeGroupData(): TimelineData {
  // Video-mode pinned group: a single video clip on V1, plus an imageClipSnapshot
  // recording the previous image clips the group used to have (pre-switch).
  const imageClipSnapshot: PinnedShotImageClipSnapshot[] = [
    {
      clipId: 'clip-img-a',
      assetKey: 'img-a',
      meta: { clipType: 'hold', hold: 1 },
    },
    {
      clipId: 'clip-img-b',
      assetKey: 'img-b',
      meta: { clipType: 'hold', hold: 2 },
    },
  ];

  const config: TimelineConfig = {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    theme: '2rp',
    theme_overrides: { visual: { canvas: { fps: 24 } } },
    generation_defaults: { model: 'sequence-v1' },
    clips: [
      {
        id: 'clip-video',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'video-asset',
        from: 0,
        to: 3,
        speed: 1,
      },
    ],
    pinnedShotGroups: [
      {
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-video'],
        mode: 'video',
        videoAssetKey: 'video-asset',
        imageClipSnapshot,
      },
    ],
  };

  const rowData = configToRows(config);
  const resolvedConfig = {
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((t) => ({ ...t })),
    clips: config.clips.map((clip) => ({ ...clip, assetEntry: undefined })),
    registry: {},
    theme: config.theme,
    theme_overrides: config.theme_overrides,
    generation_defaults: config.generation_defaults,
  };

  return {
    config,
    configVersion: 1,
    registry: { assets: {} },
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: {},
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((t) => ({ ...t })),
    clipOrder: rowData.clipOrder,
    signature: getConfigSignature(resolvedConfig),
    stableSignature: getStableConfigSignature(config, { assets: {} }),
  };
}

describe('useTimelineCommit — delete-shot / auto-restore regression', () => {
  it('deleting a video-mode group\'s video clip does NOT auto-insert image snapshots', () => {
    const eventBus = new TimelineEventBus();
    const lastSavedSignatureRef = { current: '' };

    const { result } = renderHook(() => useTimelineCommit({
      eventBus,
      lastSavedSignatureRef,
    }));

    // Seed the hook with the initial timeline data.
    act(() => {
      result.current.commitData(makeVideoModeGroupData(), { save: false });
    });

    const initial = result.current.dataRef.current!;
    expect(initial.rows[0].actions.map((a) => a.id)).toEqual(['clip-video']);
    expect(initial.config.pinnedShotGroups?.[0].clipIds).toEqual(['clip-video']);
    expect(initial.config.pinnedShotGroups?.[0].mode).toBe('video');
    expect(initial.config.pinnedShotGroups?.[0].imageClipSnapshot).toHaveLength(2);

    // Delete the video clip via a rows mutation: rows now have no actions on V1,
    // and the video clip's meta is deleted. No pinnedShotGroupsOverride is passed,
    // so the reconciler (deleted) is the only code that *would* have re-inserted
    // the image snapshots. This test proves that behavior is gone.
    const rowsWithoutVideo = initial.rows.map((row) => ({ ...row, actions: [] }));

    act(() => {
      result.current.applyEdit({
        type: 'rows',
        rows: rowsWithoutVideo,
        metaDeletes: ['clip-video'],
      }, { save: false });
    });

    const after = result.current.dataRef.current!;

    // (a) The video clip is gone from rows, meta, and config clips.
    const allActionIds = after.rows.flatMap((row) => row.actions.map((a) => a.id));
    expect(allActionIds).not.toContain('clip-video');
    expect(after.meta['clip-video']).toBeUndefined();
    expect(after.config.clips.find((c) => c.id === 'clip-video')).toBeUndefined();

    // (b) NO image clips from imageClipSnapshot were auto-inserted.
    expect(allActionIds).not.toContain('clip-img-a');
    expect(allActionIds).not.toContain('clip-img-b');
    expect(after.config.clips.find((c) => c.id === 'clip-img-a')).toBeUndefined();
    expect(after.config.clips.find((c) => c.id === 'clip-img-b')).toBeUndefined();

    // (c) The group entry is preserved (no auto-delete either). clipIds still
    // reference the deleted video clip id because the mutation did not pass a
    // pinnedShotGroupsOverride — rendering will show a degraded placeholder.
    const groupAfter = after.config.pinnedShotGroups?.[0];
    expect(groupAfter).toBeDefined();
    expect(groupAfter?.shotId).toBe('shot-1');
    expect(groupAfter?.mode).toBe('video');
    expect(groupAfter?.videoAssetKey).toBe('video-asset');
    // Snapshot metadata is preserved so a later explicit switchToImages() can still use it.
    expect(groupAfter?.imageClipSnapshot).toHaveLength(2);
    expect(after.config).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
    expect(after.resolvedConfig).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
  });

  it('delete-shot with pinnedShotGroupsOverride removes the group in the same commit', () => {
    const eventBus = new TimelineEventBus();
    const lastSavedSignatureRef = { current: '' };

    const { result } = renderHook(() => useTimelineCommit({
      eventBus,
      lastSavedSignatureRef,
    }));

    act(() => {
      result.current.commitData(makeVideoModeGroupData(), { save: false });
    });

    const initial = result.current.dataRef.current!;
    const rowsWithoutVideo = initial.rows.map((row) => ({ ...row, actions: [] }));

    act(() => {
      result.current.applyEdit({
        type: 'rows',
        rows: rowsWithoutVideo,
        metaDeletes: ['clip-video'],
        // Explicit delete-shot: remove the group entry in the same commit.
        pinnedShotGroupsOverride: [],
      }, { save: false });
    });

    const after = result.current.dataRef.current!;
    expect(after.config.pinnedShotGroups ?? []).toEqual([]);
    expect(after.config.clips).toEqual([]);
  });

  it('config mutations preserve theme extras through serializeForDisk and registry-backed rebuild', () => {
    const eventBus = new TimelineEventBus();
    const lastSavedSignatureRef = { current: '' };

    const { result } = renderHook(() => useTimelineCommit({
      eventBus,
      lastSavedSignatureRef,
    }));

    act(() => {
      result.current.commitData(makeVideoModeGroupData(), { save: false });
    });

    const initial = result.current.dataRef.current!;

    act(() => {
      result.current.applyEdit({
        type: 'config',
        resolvedConfig: {
          ...initial.resolvedConfig,
          tracks: initial.resolvedConfig.tracks.map((track) => (
            track.id === 'V1' ? { ...track, label: 'Renamed Visual' } : track
          )),
        },
      }, { save: false });
    });

    const after = result.current.dataRef.current!;
    expect(after.config.tracks?.[0]?.label).toBe('Renamed Visual');
    expect(after.config).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
    expect(after.resolvedConfig).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
  });
});
