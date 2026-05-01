import { describe, expect, it } from 'vitest';
import { buildTimelineData, configToRows, rowsToConfig } from '@/tools/video-editor/lib/timeline-data';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';

const registry: AssetRegistry = { assets: {} };

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
      generation: { prompt: 'make a sharp opener' },
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
            generation: { prompt: 'make a sharp opener' },
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
      generation: { prompt: 'make a sharp opener' },
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

  it('keeps no-theme timelines valid when rows are serialized back to config', () => {
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
  });
});
