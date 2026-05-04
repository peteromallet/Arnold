import { describe, expect, it, vi } from 'vitest';
import { executeDuplicateGeneration } from './duplicate-generation.ts';
import { resolveClipGenerationIds, resolveSelectedClipShot } from './clips.ts';

function createSupabaseAdmin({
  generationRows = [],
  maybeSingleData = null,
  rpcData = null,
}: {
  generationRows?: unknown[];
  maybeSingleData?: unknown;
  rpcData?: unknown;
} = {}) {
  const inMock = vi.fn().mockResolvedValue({ data: generationRows, error: null });
  const maybeSingleMock = vi.fn().mockResolvedValue({ data: maybeSingleData, error: null });
  const eqMock = vi.fn(() => ({ maybeSingle: maybeSingleMock }));
  const selectMock = vi.fn(() => ({
    in: inMock,
    eq: eqMock,
    maybeSingle: maybeSingleMock,
  }));
  const fromMock = vi.fn(() => ({ select: selectMock }));
  const rpcMaybeSingleMock = vi.fn().mockResolvedValue({ data: rpcData, error: null });
  const rpcMock = vi.fn(() => ({ maybeSingle: rpcMaybeSingleMock }));

  return {
    supabaseAdmin: {
      from: fromMock,
      rpc: rpcMock,
    } as unknown as import('../types.ts').SupabaseAdmin,
    fromMock,
    selectMock,
    inMock,
    eqMock,
    maybeSingleMock,
    rpcMock,
  };
}

function makeTimelineState(
  config: Partial<import('../../../../src/tools/video-editor/index.ts').TimelineConfig> = {},
) {
  return {
    config: {
      output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
      clips: [],
      tracks: [],
      pinnedShotGroups: [],
      ...config,
    },
    configVersion: 1,
    registry: { assets: {} },
    projectId: 'project-1',
    shotNamesById: {},
  } as unknown as import('../types.ts').TimelineState;
}

describe('resolveClipGenerationIds', () => {
  it('falls back to generation_id when the clip lookup misses', () => {
    const result = resolveClipGenerationIds(
      [
        { clip_id: 'clip-1', generation_id: 'gen-direct-1' },
        { clip_id: 'gallery-gen-2', generation_id: 'gen-direct-2' },
      ],
      {
        assets: {
          'asset-1': {
            file: 'https://example.com/image.png',
            generationId: 'gen-from-timeline',
          },
        },
      },
      {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [
          {
            id: 'clip-1',
            asset: 'asset-1',
            at: 0,
            track: 'V1',
            clipType: 'hold',
            hold: 5,
          },
        ],
        tracks: [],
      },
    );

    expect(result).toEqual(['gen-from-timeline', 'gen-direct-2']);
  });
});

describe('resolveSelectedClipShot', () => {
  it('prefers an explicit shot_id over pinned groups and generation fallback', async () => {
    const { supabaseAdmin, fromMock } = createSupabaseAdmin();

    await expect(resolveSelectedClipShot(
      supabaseAdmin,
      makeTimelineState({
        pinnedShotGroups: [{ shotId: 'shot-pinned', trackId: 'V1', clipIds: ['clip-1'], mode: 'images' }],
      }),
      [{
        clip_id: 'clip-1',
        url: 'https://example.com/clip.png',
        media_type: 'image',
        generation_id: 'gen-1',
        shot_id: 'shot-explicit',
      }],
    )).resolves.toMatchObject({
      shotId: 'shot-explicit',
      source: 'explicit',
    });

    expect(fromMock).not.toHaveBeenCalled();
  });

  it('resolves a shared pinned shot for selected timeline clips when explicit metadata is absent', async () => {
    const { supabaseAdmin, fromMock } = createSupabaseAdmin();

    await expect(resolveSelectedClipShot(
      supabaseAdmin,
      makeTimelineState({
        pinnedShotGroups: [{ shotId: 'shot-pinned', trackId: 'V1', clipIds: ['clip-1', 'clip-2'], mode: 'images' }],
      }),
      [
        { clip_id: 'clip-1', url: 'https://example.com/clip-1.png', media_type: 'image' },
        { clip_id: 'clip-2', url: 'https://example.com/clip-2.png', media_type: 'image' },
      ],
    )).resolves.toMatchObject({
      shotId: 'shot-pinned',
      source: 'pinned',
    });

    expect(fromMock).not.toHaveBeenCalled();
  });

  it('falls back to generation lookup when selected clips do not carry shot metadata', async () => {
    const { supabaseAdmin, fromMock, selectMock, inMock } = createSupabaseAdmin({
      generationRows: [
        { generation_id: 'gen-1', shot_id: 'shot-generated' },
        { generation_id: 'gen-2', shot_id: 'shot-generated' },
      ],
    });

    await expect(resolveSelectedClipShot(
      supabaseAdmin,
      makeTimelineState(),
      [
        { clip_id: 'gallery-gen-1', url: 'https://example.com/clip-1.png', media_type: 'image', generation_id: 'gen-1' },
        { clip_id: 'gallery-gen-2', url: 'https://example.com/clip-2.png', media_type: 'image', generation_id: 'gen-2' },
      ],
    )).resolves.toEqual({
      shotId: 'shot-generated',
      source: 'generation',
    });

    expect(fromMock).toHaveBeenCalledWith('shot_generations');
    expect(selectMock).toHaveBeenCalledWith('shot_id, generation_id');
    expect(inMock).toHaveBeenCalledWith('generation_id', ['gen-1', 'gen-2']);
  });
});

describe('executeDuplicateGeneration', () => {
  it('keeps the fast path when selected clips already share an explicit shot_id', async () => {
    const { supabaseAdmin, inMock, eqMock, maybeSingleMock, rpcMock } = createSupabaseAdmin({
      maybeSingleData: { shot_id: 'shot-from-db', timeline_frame: 24 },
      rpcData: {
        new_generation_id: 'gen-new',
        location: 'https://example.com/new.png',
        type: 'image',
      },
    });

    const result = await executeDuplicateGeneration(
      { generation_id: 'gen-source' },
      makeTimelineState(),
      [{
        clip_id: 'clip-1',
        url: 'https://example.com/clip.png',
        media_type: 'image',
        generation_id: 'gen-clip',
        shot_id: 'shot-explicit',
      }],
      supabaseAdmin,
    );

    expect(result.result).toContain('Duplicated gen-source -> gen-new.');
    expect(eqMock).toHaveBeenCalledWith('generation_id', 'gen-source');
    expect(maybeSingleMock).toHaveBeenCalledTimes(1);
    expect(inMock).not.toHaveBeenCalled();
    expect(rpcMock).toHaveBeenCalledWith('duplicate_as_new_generation', {
      p_shot_id: 'shot-explicit',
      p_generation_id: 'gen-source',
      p_project_id: 'project-1',
      p_timeline_frame: 24,
    });
  });
});
