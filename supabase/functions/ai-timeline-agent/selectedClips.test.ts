import { describe, expect, it, vi } from 'vitest';
import { getPairTimelineClipDuration } from '../../../src/tools/video-editor/lib/timeline-domain.ts';
import { prepareTimelineConfigForPersistence } from './db.ts';
import {
  enrichClipsWithPrompts,
  normalizeSelectedClips,
  resolveSelectionContext,
  resolveTimelinePlacement,
} from './selectedClips.ts';

function makeTimelineState(clips: unknown[], assets: Record<string, unknown> = {}) {
  return {
    config: { clips },
    registry: { assets },
  } as unknown as import('./types.ts').TimelineState;
}

function createSupabaseAdmin(rows: unknown, error: { message: string } | null = null) {
  const inMock = vi.fn().mockResolvedValue({ data: rows, error });
  const selectMock = vi.fn(() => ({ in: inMock }));
  const fromMock = vi.fn(() => ({ select: selectMock }));

  return {
    supabaseAdmin: {
      from: fromMock,
    } as unknown as import('./types.ts').SupabaseAdmin,
    fromMock,
    selectMock,
    inMock,
  };
}

describe('normalizeSelectedClips', () => {
  it('keeps clip ids for timeline attachments and includes generation_id when present', () => {
    expect(normalizeSelectedClips([{
      clip_id: 'clip-1',
      generation_id: 'gen-1',
      variant_id: 'variant-1',
      url: 'https://example.com/image.png',
      media_type: 'image',
    }])).toEqual([{
      clip_id: 'clip-1',
      generation_id: 'gen-1',
      variant_id: 'variant-1',
      url: 'https://example.com/image.png',
      media_type: 'image',
    }]);
  });

  it('preserves the exact timeline clip id while trimming variant_id during normalization', () => {
    expect(normalizeSelectedClips([{
      clip_id: '  clip-timeline-7  ',
      generation_id: 'gen-7',
      variant_id: '  variant-7  ',
      url: 'https://example.com/timeline-7.png',
      media_type: 'image',
    }])).toEqual([{
      clip_id: 'clip-timeline-7',
      generation_id: 'gen-7',
      variant_id: 'variant-7',
      url: 'https://example.com/timeline-7.png',
      media_type: 'image',
    }]);
  });

  it('accepts gallery attachments with generation_id and synthesizes clip ids', () => {
    expect(normalizeSelectedClips([{
      clip_id: '',
      generation_id: 'gen-2',
      url: 'https://example.com/video.mp4',
      media_type: 'video',
    }])).toEqual([{
      clip_id: 'gallery-gen-2',
      generation_id: 'gen-2',
      url: 'https://example.com/video.mp4',
      media_type: 'video',
    }]);
  });

  it('rejects attachments without a usable clip or generation id', () => {
    expect(normalizeSelectedClips([{
      clip_id: '',
      url: 'https://example.com/image.png',
      media_type: 'image',
    }])).toEqual([]);
  });

  it('keeps prompt metadata when present on the incoming payload', () => {
    expect(normalizeSelectedClips([{
      clip_id: 'clip-3',
      generation_id: 'gen-3',
      url: 'https://example.com/image.png',
      media_type: 'image',
      prompt: '  moody portrait lighting  ',
    }])).toEqual([{
      clip_id: 'clip-3',
      generation_id: 'gen-3',
      url: 'https://example.com/image.png',
      media_type: 'image',
      prompt: 'moody portrait lighting',
    }]);
  });

  it('preserves explicit shot metadata when present on the incoming payload', () => {
    expect(normalizeSelectedClips([{
      clip_id: 'clip-4',
      generation_id: 'gen-4',
      url: 'https://example.com/shot.png',
      media_type: 'image',
      is_timeline_backed: true,
      shot_id: '  shot-4  ',
      shot_name: '  Hero Shot  ',
      shot_selection_clip_count: 4,
      track_id: '  V1  ',
      at: 10.5,
      duration: 2.25,
    }])).toEqual([{
      clip_id: 'clip-4',
      generation_id: 'gen-4',
      url: 'https://example.com/shot.png',
      media_type: 'image',
      is_timeline_backed: true,
      shot_id: 'shot-4',
      shot_name: 'Hero Shot',
      shot_selection_clip_count: 4,
      track_id: 'V1',
      at: 10.5,
      duration: 2.25,
    }]);
  });
});

describe('resolveTimelinePlacement', () => {
  it('returns an after_source placement for a timeline-backed clip that still exists on the loaded timeline', () => {
    const timelineState = makeTimelineState([{
      id: 'clip-1',
      at: 8,
      track: 'V1',
      hold: 2.5,
    }]);

    expect(resolveTimelinePlacement({
      clip_id: 'clip-1',
      url: 'https://example.com/1.png',
      media_type: 'image',
      is_timeline_backed: true,
    }, timelineState, 'timeline-1')).toEqual({
      timeline_id: 'timeline-1',
      source_clip_id: 'clip-1',
      target_track: 'V1',
      insertion_time: 10.5,
      intent: 'after_source',
    });
  });

  it('returns null for gallery-only clips with no timeline backing', () => {
    const timelineState = makeTimelineState([{
      id: 'clip-1',
      at: 8,
      track: 'V1',
      hold: 2.5,
    }]);

    expect(resolveTimelinePlacement({
      clip_id: 'gallery-gen-1',
      url: 'https://example.com/1.png',
      media_type: 'image',
      is_timeline_backed: false,
    }, timelineState, 'timeline-1')).toBeNull();
  });

  it('does not treat gallery clip ids as timeline anchors even when variant_id is present', () => {
    const timelineState = makeTimelineState([{
      id: 'clip-1',
      at: 8,
      track: 'V1',
      hold: 2.5,
    }]);

    const [galleryClip] = normalizeSelectedClips([{
      clip_id: '',
      generation_id: 'gen-2',
      variant_id: 'variant-2',
      url: 'https://example.com/gallery.png',
      media_type: 'image',
      is_timeline_backed: true,
    }]);

    expect(galleryClip).toEqual({
      clip_id: 'gallery-gen-2',
      generation_id: 'gen-2',
      variant_id: 'variant-2',
      url: 'https://example.com/gallery.png',
      media_type: 'image',
      is_timeline_backed: true,
    });
    expect(resolveTimelinePlacement(galleryClip, timelineState, 'timeline-1')).toBeNull();
  });
});

describe('resolveSelectionContext', () => {
  it('resolves timeline clips from the live timeline config with track, at, and duration', () => {
    const timelineState = makeTimelineState([{
      id: 'clip-1',
      at: 3.5,
      track: 'V2',
      hold: 1.25,
    }]);

    expect(resolveSelectionContext([{
      clip_id: 'clip-1',
      generation_id: 'gen-1',
      variant_id: 'variant-1',
      url: 'https://example.com/1.png',
      media_type: 'image',
      track_id: 'stale-track',
      at: 99,
      duration: 99,
      shot_id: 'shot-1',
      shot_name: 'Hero',
    }], timelineState, 'timeline-1')).toEqual([{
      timeline_id: 'timeline-1',
      clip_id: 'clip-1',
      generation_id: 'gen-1',
      variant_id: 'variant-1',
      track_id: 'V2',
      at: 3.5,
      duration: 1.25,
      shot_id: 'shot-1',
      shot_name: 'Hero',
      source: 'timeline',
      is_on_timeline: true,
    }]);
  });

  it('uses pair-aware registry duration semantics for malformed non-hold clips', () => {
    const timelineState = makeTimelineState(
      [{
        id: 'clip-video',
        at: 6,
        track: 'V3',
        clipType: 'media',
        asset: 'asset-video',
        speed: 2,
      }],
      {
        'asset-video': {
          file: 'video.mp4',
          duration: 10,
        },
      },
    );
    const expectedDuration = getPairTimelineClipDuration(
      timelineState.config.clips[0] as Parameters<typeof getPairTimelineClipDuration>[0],
      timelineState.registry as Parameters<typeof getPairTimelineClipDuration>[1],
    );

    expect(resolveSelectionContext([{
      clip_id: 'clip-video',
      url: 'https://example.com/video.mp4',
      media_type: 'video',
    }], timelineState, 'timeline-1')).toEqual([{
      timeline_id: 'timeline-1',
      clip_id: 'clip-video',
      track_id: 'V3',
      at: 6,
      duration: expectedDuration,
      source: 'timeline',
      is_on_timeline: true,
    }]);
    expect(expectedDuration).toBe(5);
  });

  it('treats gallery-prefixed or missing clip ids as non-timeline selections', () => {
    const timelineState = makeTimelineState([{
      id: 'clip-1',
      at: 3.5,
      track: 'V2',
      hold: 1.25,
    }]);

    expect(resolveSelectionContext([
      {
        clip_id: 'gallery-gen-2',
        generation_id: 'gen-2',
        variant_id: 'variant-2',
        url: 'https://example.com/gallery.png',
        media_type: 'image',
      },
      {
        clip_id: 'clip-missing',
        generation_id: 'gen-3',
        url: 'https://example.com/missing.png',
        media_type: 'image',
      },
    ], timelineState, 'timeline-1')).toEqual([
      {
        timeline_id: 'timeline-1',
        clip_id: 'gallery-gen-2',
        generation_id: 'gen-2',
        variant_id: 'variant-2',
        track_id: '',
        at: 0,
        duration: 0,
        source: 'gallery',
        is_on_timeline: false,
      },
      {
        timeline_id: 'timeline-1',
        clip_id: 'clip-missing',
        generation_id: 'gen-3',
        track_id: '',
        at: 0,
        duration: 0,
        source: 'gallery',
        is_on_timeline: false,
      },
    ]);
  });
});

describe('enrichClipsWithPrompts', () => {
  it('adds prompt metadata for clips with generation_id using one batched generations query', async () => {
    const { supabaseAdmin, fromMock, selectMock, inMock } = createSupabaseAdmin([
      {
        id: 'gen-1',
        params: {
          originalParams: {
            orchestrator_details: {
              prompt: 'style prompt',
            },
          },
        },
      },
      {
        id: 'gen-2',
        params: {
          prompt: 'fallback prompt',
        },
      },
    ]);

    await expect(enrichClipsWithPrompts(supabaseAdmin, [
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
      { clip_id: 'clip-3', generation_id: 'gen-1', url: 'https://example.com/3.png', media_type: 'image' },
    ])).resolves.toEqual([
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image', prompt: 'style prompt' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video', prompt: 'fallback prompt' },
      { clip_id: 'clip-3', generation_id: 'gen-1', url: 'https://example.com/3.png', media_type: 'image', prompt: 'style prompt' },
    ]);

    expect(fromMock).toHaveBeenCalledWith('generations');
    expect(selectMock).toHaveBeenCalledWith('id, params');
    expect(inMock).toHaveBeenCalledTimes(1);
    expect(inMock).toHaveBeenCalledWith('id', ['gen-1', 'gen-2']);
  });

  it('passes clips through unchanged when none have generation_id', async () => {
    const clips = [{
      clip_id: 'clip-1',
      variant_id: 'variant-1',
      url: 'https://example.com/1.png',
      media_type: 'image' as const,
    }];
    const { supabaseAdmin, fromMock } = createSupabaseAdmin([]);

    await expect(enrichClipsWithPrompts(supabaseAdmin, clips)).resolves.toEqual(clips);
    expect(fromMock).not.toHaveBeenCalled();
  });

  it('leaves prompt undefined when params are missing or null', async () => {
    const { supabaseAdmin } = createSupabaseAdmin([
      { id: 'gen-1', params: null },
      { id: 'gen-2' },
    ]);

    await expect(enrichClipsWithPrompts(supabaseAdmin, [
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
    ])).resolves.toEqual([
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
    ]);
  });

  it('returns early for an empty clip list without hitting the database', async () => {
    const { supabaseAdmin, fromMock } = createSupabaseAdmin([]);

    await expect(enrichClipsWithPrompts(supabaseAdmin, [])).resolves.toEqual([]);
    expect(fromMock).not.toHaveBeenCalled();
  });

  it('uses orchestrator prompt before params.prompt and metadata.prompt', async () => {
    const { supabaseAdmin } = createSupabaseAdmin([
      {
        id: 'gen-1',
        params: {
          prompt: 'params prompt',
          metadata: { prompt: 'metadata prompt' },
          originalParams: {
            orchestrator_details: {
              prompt: 'orchestrator prompt',
            },
          },
        },
      },
      {
        id: 'gen-2',
        params: {
          metadata: { prompt: 'metadata only prompt' },
        },
      },
    ]);

    await expect(enrichClipsWithPrompts(supabaseAdmin, [
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'image' },
    ])).resolves.toEqual([
      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image', prompt: 'orchestrator prompt' },
      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'image', prompt: 'metadata only prompt' },
    ]);
  });
});

describe('prepareTimelineConfigForPersistence', () => {
  it('reconciles stale pinned shot group clipIds and trackId before pair-aware canonicalization', () => {
    const nextConfig = prepareTimelineConfigForPersistence({
      output: {
        file: 'out.mp4',
        fps: 30,
        resolution: '1920x1080',
      },
      tracks: [{ id: 'V2', kind: 'visual', label: 'Visual 2' }],
      clips: [
        {
          id: 'clip-b',
          at: 3,
          track: 'V2',
          clipType: 'media',
          asset: 'asset-b',
        },
        {
          id: 'clip-a',
          at: 1,
          track: 'V2',
          clipType: 'media',
          asset: 'asset-a',
        },
      ],
      pinnedShotGroups: [{
        shotId: 'shot-1',
        trackId: 'stale-track',
        clipIds: ['missing-clip', 'clip-b', 'clip-a'],
        mode: 'images',
      }],
    }, {
      assets: {
        'asset-a': { file: 'a.mp4', type: 'video/mp4', duration: 8 },
        'asset-b': { file: 'b.mp4', type: 'video/mp4', duration: 6 },
      },
    });

    expect(nextConfig.pinnedShotGroups).toEqual([{
      shotId: 'shot-1',
      trackId: 'V2',
      clipIds: ['clip-a', 'clip-b'],
      mode: 'images',
    }]);
    expect(nextConfig.clips[0]).toEqual(expect.objectContaining({
      id: 'clip-b',
      from: 0,
      to: 6,
    }));
    expect(nextConfig.clips[1]).toEqual(expect.objectContaining({
      id: 'clip-a',
      from: 0,
      to: 8,
    }));
  });
});
