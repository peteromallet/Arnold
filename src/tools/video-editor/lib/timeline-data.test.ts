import { describe, expect, it } from 'vitest';
import { buildTimelineData, configToRows, rowsToConfig } from '@/tools/video-editor/lib/timeline-data';
import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';
import { serializeForDisk, validateSerializedConfig } from '@/tools/video-editor/lib/serialize';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';

const registry: AssetRegistry = { assets: {} };

const trustedSequenceGeneration = {
  sequence_lane: 'trusted_v1',
  sequence_creator: {
    name: 'AI sequence draft',
    prompt: 'make a sharp opener',
    draft_index: 0,
    intent: { freeform: 'Snap the title twice, then hold on the proof point.' },
  },
};

const buildSequenceConfig = (): TimelineConfig => ({
  output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  theme: '2rp',
  theme_overrides: { visual: { palette: { primary: '#ff0000' } } },
  generation_defaults: { model: 'sequence-model' },
  clips: [
    {
      id: 'clip-sequence',
      at: 1,
      track: 'V1',
      clipType: 'section-hook',
      hold: 3,
      params: {
        eyebrow: 'Market signal',
        title: 'AI sequence draft',
      },
      pool_id: 'pool-1',
      clip_order: 4,
      source_uuid: 'source-1',
      generation: trustedSequenceGeneration,
    },
  ],
  pinnedShotGroups: [
    {
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-sequence'],
      mode: 'images',
      imageClipSnapshot: [
        {
          clipId: 'clip-sequence',
          start: 1,
          end: 4,
          meta: {
            clipType: 'section-hook',
            hold: 3,
            params: { title: 'AI sequence draft' },
            pool_id: 'pool-1',
            clip_order: 4,
            source_uuid: 'source-1',
            generation: trustedSequenceGeneration,
          },
        },
      ],
    },
  ],
});

describe('timeline data sequence clip persistence', () => {
  it('preserves sequence clip schema-lift fields and top-level extras through buildTimelineData and rowsToConfig', async () => {
    const config = buildSequenceConfig();

    const data = await buildTimelineData(config, registry);
    expect(data.config.theme).toBe('2rp');
    expect(data.config.theme_overrides).toEqual(config.theme_overrides);
    expect(data.config.generation_defaults).toEqual(config.generation_defaults);
    expect(data.meta['clip-sequence']).toMatchObject({
      clipType: 'section-hook',
      hold: 3,
      params: config.clips[0].params,
      pool_id: 'pool-1',
      clip_order: 4,
      source_uuid: 'source-1',
      generation: config.clips[0].generation,
    });
    expect(data.config.pinnedShotGroups?.[0]?.imageClipSnapshot?.[0]?.meta).toMatchObject({
      params: { title: 'AI sequence draft' },
      pool_id: 'pool-1',
      clip_order: 4,
      source_uuid: 'source-1',
      generation: trustedSequenceGeneration,
    });

    const roundTripped = rowsToConfig(
      data.rows,
      data.meta,
      data.output,
      data.clipOrder,
      data.tracks,
      data.config.pinnedShotGroups,
      data.config,
    );

    expect(roundTripped).toMatchObject({
      theme: '2rp',
      theme_overrides: config.theme_overrides,
      generation_defaults: config.generation_defaults,
    });
    expect(roundTripped.clips[0]).toEqual({
      id: 'clip-sequence',
      at: 1,
      track: 'V1',
      clipType: 'section-hook',
      hold: 3,
      params: config.clips[0].params,
      pool_id: 'pool-1',
      clip_order: 4,
      source_uuid: 'source-1',
      generation: config.clips[0].generation,
    });
  });

  it('round-trips trusted generation provenance additively while preserving legacy no-generation clips', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-trusted',
          at: 0,
          track: 'V1',
          clipType: 'section-hook',
          hold: 2,
          params: { title: 'Trusted provenance' },
          generation: trustedSequenceGeneration,
        },
        {
          id: 'clip-legacy',
          at: 2,
          track: 'V1',
          clipType: 'media',
          asset: 'legacy-video',
          from: 0,
          to: 3,
        },
      ],
    };
    const assetRegistry: AssetRegistry = {
      assets: {
        'legacy-video': { file: 'legacy-video.mp4', type: 'video/mp4' },
      },
    };

    const data = await buildTimelineData(config, assetRegistry);
    expect(data.meta['clip-trusted'].generation).toEqual(trustedSequenceGeneration);
    expect(data.meta['clip-legacy'].generation).toBeUndefined();

    const roundTripped = rowsToConfig(
      data.rows,
      data.meta,
      data.output,
      data.clipOrder,
      data.tracks,
      data.config.pinnedShotGroups,
      data.config,
    );
    const trustedClip = roundTripped.clips.find((clip) => clip.id === 'clip-trusted');
    const legacyClip = roundTripped.clips.find((clip) => clip.id === 'clip-legacy');

    expect(trustedClip?.generation).toEqual(trustedSequenceGeneration);
    expect(legacyClip).not.toHaveProperty('generation');
    expect(() => validateSerializedConfig(roundTripped)).not.toThrow();

    const serialized = serializeForDisk(data.resolvedConfig);
    expect(serialized.clips.find((clip) => clip.id === 'clip-trusted')?.generation).toEqual(
      trustedSequenceGeneration,
    );
    expect(serialized.clips.find((clip) => clip.id === 'clip-legacy')).not.toHaveProperty('generation');
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('keeps no-theme timelines valid when rows are serialized back to config', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
    };
    const { rows, meta, clipOrder, tracks } = configToRows(config);

    const roundTripped = rowsToConfig(rows, meta, config.output, clipOrder, tracks, undefined, config);

    expect(roundTripped).not.toHaveProperty('theme');
    expect(roundTripped).not.toHaveProperty('theme_overrides');
    expect(roundTripped).not.toHaveProperty('generation_defaults');
    expect(roundTripped.clips[0]).toEqual(config.clips[0]);

    const data = await buildTimelineData(config, registry);
    const serialized = serializeForDisk(data.resolvedConfig);
    expect(serialized.clips[0]).toEqual(config.clips[0]);
    expect(serialized.clips[0]).not.toHaveProperty('generation');
    expect(decideRenderRoute(serialized)).toMatchObject({
      route: 'client',
      reason: 'pure_native_clips',
    });
  });
});
