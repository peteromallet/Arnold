import { describe, expect, it } from 'vitest';
import {
  buildInsertSequenceDraftEdit,
  buildReplaceSequenceDraftEdit,
} from '@/tools/video-editor/lib/sequence-drafts';
import {
  buildTimelineData,
  rowsToConfig,
  type ClipMeta,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import type { ClipOrderMap } from '@/tools/video-editor/lib/timeline-data';
import type { ValidatedSequenceDraft } from '@/tools/video-editor/sequences/validation';
import type { TimelineConfig } from '@/tools/video-editor/types';

const draft: ValidatedSequenceDraft = {
  clipType: 'section-hook',
  hold: 3,
  params: {
    kicker: '2RP',
    title: 'Renaissance systems',
  },
};

const buildData = async (
  overrides: Partial<TimelineConfig> = {},
): Promise<TimelineData> => {
  const config: TimelineConfig = {
    output: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'Visual 1' },
      { id: 'V2', kind: 'visual', label: 'Visual 2' },
    ],
    clips: [],
    theme: '2rp',
    theme_overrides: {
      visual: {
        color: {
          accent: '#00ff88',
        },
      },
    },
    ...overrides,
  };
  return buildTimelineData(config, { assets: {} });
};

const applyRowsMutation = (
  current: TimelineData,
  mutation: Extract<ReturnType<typeof buildInsertSequenceDraftEdit>, { ok: true }>['mutation'],
): TimelineConfig => {
  const meta: Record<string, ClipMeta> = {
    ...current.meta,
    ...(mutation.metaUpdates ?? {}),
  };
  for (const id of mutation.metaDeletes ?? []) {
    delete meta[id];
  }
  const clipOrder: ClipOrderMap = mutation.clipOrderOverride ?? current.clipOrder;
  return rowsToConfig(
    mutation.rows,
    meta,
    current.output,
    clipOrder,
    current.tracks,
    current.config.pinnedShotGroups,
    current.config,
  );
};

describe('sequence draft row mutations', () => {
  it('inserts a normal sequence clip on the selected visual track and selects it', async () => {
    const data = await buildData();
    const result = buildInsertSequenceDraftEdit(data, draft, {
      at: 2,
      selectedTrackId: 'V2',
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.selectedClipId).toBe(result.clipId);
    expect(result.selectedTrackId).toBe('V2');
    expect(result.mutation.clipOrderOverride.V2).toEqual([result.clipId]);
    expect(result.mutation.metaUpdates?.[result.clipId]).toMatchObject({
      track: 'V2',
      clipType: 'section-hook',
      hold: 3,
      params: draft.params,
    });

    const persisted = applyRowsMutation(data, result.mutation);
    expect(persisted.clips[0]).toMatchObject({
      id: result.clipId,
      track: 'V2',
      at: 2,
      clipType: 'section-hook',
      hold: 3,
      params: draft.params,
    });
    expect(persisted.theme).toBe('2rp');
    expect(persisted.theme_overrides).toEqual(data.config.theme_overrides);
  });

  it('defaults insertion to the first visual track and resolves overlaps', async () => {
    const data = await buildData({
      clips: [
        {
          id: 'clip-0',
          track: 'V1',
          at: 0,
          clipType: 'section-hook',
          hold: 3,
          params: { title: 'Existing' },
        },
      ],
    });
    const result = buildInsertSequenceDraftEdit(data, draft, { at: 1 });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const action = result.mutation.rows
      .find((row) => row.id === 'V1')
      ?.actions.find((candidate) => candidate.id === result.clipId);
    expect(action).toMatchObject({ start: 3, end: 6 });
    expect(result.mutation.clipOrderOverride.V1).toEqual(['clip-0', result.clipId]);
  });

  it('uses the nearest free visual track before trimming the inserted sequence', async () => {
    const data = await buildData({
      clips: [
        {
          id: 'clip-0',
          track: 'V1',
          at: 0,
          clipType: 'section-hook',
          hold: 5,
          params: { title: 'Existing' },
        },
      ],
    });
    const result = buildInsertSequenceDraftEdit(data, draft, {
      at: 1,
      selectedTrackId: 'V1',
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const action = result.mutation.rows
      .find((row) => row.id === 'V2')
      ?.actions.find((candidate) => candidate.id === result.clipId);
    expect(result.selectedTrackId).toBe('V2');
    expect(action).toMatchObject({ start: 1, end: 4 });
    expect(result.mutation.metaUpdates?.[result.clipId]).toMatchObject({
      track: 'V2',
      hold: 3,
    });
  });

  it('replaces a selected visual clip at the same track/start using the generated hold', async () => {
    const data = await buildData({
      clips: [
        {
          id: 'clip-0',
          track: 'V1',
          at: 2,
          clipType: 'media',
          hold: 8,
        },
      ],
    });
    const result = buildReplaceSequenceDraftEdit(data, draft, {
      selectedClipId: 'clip-0',
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.mutation.metaDeletes).toEqual(['clip-0']);
    expect(result.mutation.clipOrderOverride.V1).toEqual([result.clipId]);
    const persisted = applyRowsMutation(data, result.mutation);
    expect(persisted.clips).toHaveLength(1);
    expect(persisted.clips[0]).toMatchObject({
      id: result.clipId,
      track: 'V1',
      at: 2,
      clipType: 'section-hook',
      hold: 3,
      params: draft.params,
    });
    expect(persisted.theme).toBe('2rp');
  });

  it('replaces all selected visual clips with one sequence at the earliest selected start', async () => {
    const data = await buildData({
      clips: [
        {
          id: 'clip-0',
          track: 'V1',
          at: 4,
          clipType: 'media',
          hold: 2,
        },
        {
          id: 'clip-1',
          track: 'V1',
          at: 7,
          clipType: 'media',
          hold: 2,
        },
        {
          id: 'clip-2',
          track: 'V2',
          at: 2,
          clipType: 'media',
          hold: 1,
        },
      ],
    });
    const result = buildReplaceSequenceDraftEdit(data, draft, {
      selectedClipId: 'clip-1',
      selectedClipIds: ['clip-0', 'clip-1', 'clip-2'],
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.selectedClipId).toBe(result.clipId);
    expect(result.selectedTrackId).toBe('V1');
    expect(result.mutation.metaDeletes).toEqual(['clip-0', 'clip-1', 'clip-2']);
    expect(result.mutation.clipOrderOverride.V1).toEqual([result.clipId]);
    expect(result.mutation.clipOrderOverride.V2).toEqual([]);
    expect(result.mutation.metaUpdates?.[result.clipId]).toMatchObject({
      track: 'V1',
      clipType: 'section-hook',
    });
    const persisted = applyRowsMutation(data, result.mutation);
    expect(persisted.clips).toHaveLength(1);
    expect(persisted.clips[0]).toMatchObject({
      id: result.clipId,
      track: 'V1',
      at: 2,
      clipType: 'section-hook',
      hold: 3,
    });
  });

  it('rejects audio-track replacement targets instead of creating an invisible sequence', async () => {
    const data = await buildData({
      tracks: [
        { id: 'A1', kind: 'audio', label: 'Audio 1' },
      ],
      clips: [
        {
          id: 'clip-0',
          track: 'A1',
          at: 0,
          clipType: 'media',
          hold: 5,
        },
      ],
    });

    expect(buildReplaceSequenceDraftEdit(data, draft, { selectedClipId: 'clip-0' })).toEqual({
      ok: false,
      error: 'replace_target_not_visual',
    });
  });

  it('returns a no_visual_track error when insertion has no visual row', async () => {
    const data = await buildData({
      tracks: [{ id: 'A1', kind: 'audio', label: 'Audio 1' }],
    });

    expect(buildInsertSequenceDraftEdit(data, draft, { at: 0 })).toEqual({
      ok: false,
      error: 'no_visual_track',
    });
  });
});
