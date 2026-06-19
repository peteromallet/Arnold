import { describe, expect, it, vi } from 'vitest';
import {
  buildTimelineData,
  buildTimelineDataWithResolver,
  configToRows,
  loadTimelineJsonFromProvider,
  loadTranscript,
  rowsToConfig,
} from '@/tools/video-editor/lib/timeline-data';
import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';
import { serializeForDisk, validateSerializedConfig } from '@/tools/video-editor/lib/serialize';
import type { AssetResolver } from '@/tools/video-editor/data/AssetResolver';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
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
      route: 'browser-remotion',
      reason: 'pure_native_clips',
    });
  });

  it('loads timeline data through assetResolver.onResolve and reports missing assets through onMissing', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'clip-ok', at: 0, track: 'V1', clipType: 'media', asset: 'asset-ok', from: 0, to: 2 },
        { id: 'clip-missing', at: 2, track: 'V1', clipType: 'media', asset: 'asset-missing', from: 0, to: 2 },
      ],
    };
    const assetRegistry: AssetRegistry = {
      assets: {
        'asset-ok': { file: 'asset-ok.mp4', type: 'video/mp4' },
      },
    };
    const provider: DataProvider = {
      loadTimeline: vi.fn(async () => ({ config, configVersion: 4 })),
      saveTimeline: vi.fn(async () => 4),
      loadAssetRegistry: vi.fn(async () => assetRegistry),
      resolveAssetUrl: vi.fn(async () => {
        throw new Error('legacy resolveAssetUrl should not be called');
      }),
    };
    const assetResolver: AssetResolver = {
      resolveAssetUrl: vi.fn(async (file: string) => `legacy:${file}`),
      onResolve: vi.fn(async ({ file }: { file: string }) => `resolver:${file}`),
      onMissing: vi.fn(async () => {}),
    };

    const data = await loadTimelineJsonFromProvider(provider, assetResolver, 'timeline-1');

    expect(data.configVersion).toBe(4);
    expect(assetResolver.onResolve).toHaveBeenCalledWith({
      file: 'asset-ok.mp4',
      timelineId: 'timeline-1',
    });
    expect(assetResolver.onMissing).toHaveBeenCalledWith(expect.objectContaining({
      assetId: 'asset-missing',
      clipId: 'clip-missing',
      timelineId: 'timeline-1',
      reason: 'missing_asset',
    }));
    expect(data.resolvedConfig.registry['asset-ok']?.src).toBe('resolver:asset-ok.mp4');
  });

  it('rebuilds timeline data through assetResolver.onResolve for refresh paths', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'clip-refresh', at: 0, track: 'V1', clipType: 'media', asset: 'asset-refresh', from: 0, to: 2 },
      ],
    };
    const assetRegistry: AssetRegistry = {
      assets: {
        'asset-refresh': { file: 'asset-refresh.mp4', type: 'video/mp4' },
      },
    };
    const assetResolver: AssetResolver = {
      resolveAssetUrl: vi.fn(async () => {
        throw new Error('legacy resolveAssetUrl should not be called');
      }),
      onResolve: vi.fn(async ({ file }: { file: string }) => `refresh:${file}`),
    };

    const data = await buildTimelineDataWithResolver(
      config,
      assetRegistry,
      assetResolver,
      7,
      'timeline-refresh',
    );

    expect(assetResolver.onResolve).toHaveBeenCalledWith({
      file: 'asset-refresh.mp4',
      timelineId: 'timeline-refresh',
    });
    expect(data.configVersion).toBe(7);
    expect(data.resolvedConfig.registry['asset-refresh']?.src).toBe('refresh:asset-refresh.mp4');
  });

  it('loads transcripts through assetResolver.onProfileLoad when available', async () => {
    const assetResolver: AssetResolver = {
      resolveAssetUrl: vi.fn(async (file: string) => file),
      onProfileLoad: vi.fn(async ({ assetId }: { assetId: string }) => ({
        transcript: {
          segments: [{ start: 0, end: 1, text: `segment:${assetId}` }],
        },
      })),
    };

    await expect(loadTranscript(assetResolver, 'asset-1', 'timeline-1')).resolves.toEqual([
      { start: 0, end: 1, text: 'segment:asset-1' },
    ]);
    expect(assetResolver.onProfileLoad).toHaveBeenCalledWith({
      assetId: 'asset-1',
      timelineId: 'timeline-1',
    });
  });

  it('falls back to legacy loadAssetProfile when no profile hook is installed', async () => {
    const assetResolver: AssetResolver = {
      resolveAssetUrl: vi.fn(async (file: string) => file),
      loadAssetProfile: vi.fn(async (assetId: string) => ({
        transcript: {
          segments: [{ start: 1, end: 2, text: `legacy:${assetId}` }],
        },
      })),
    };

    await expect(loadTranscript(assetResolver, 'asset-2', 'timeline-legacy')).resolves.toEqual([
      { start: 1, end: 2, text: 'legacy:asset-2' },
    ]);
    expect(assetResolver.loadAssetProfile).toHaveBeenCalledWith('asset-2');
  });

  // ── M9: Keyframe round-trip through configToRows / rowsToConfig ──────

  it('round-trips keyframes through configToRows and rowsToConfig', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-kf',
          at: 0,
          track: 'V1',
          clipType: 'contributed:animated',
          hold: 4,
          params: { text: 'Animated' },
          keyframes: {
            opacity: [
              { time: 0, value: 0, interpolation: 'linear' },
              { time: 2, value: 1, interpolation: 'linear' },
              { time: 4, value: 0.5, interpolation: 'hold' },
            ],
          },
        },
      ],
    };

    const { rows, meta, clipOrder, tracks } = configToRows(config);

    expect(meta['clip-kf'].keyframes).toEqual({
      opacity: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 2, value: 1, interpolation: 'linear' },
        { time: 4, value: 0.5, interpolation: 'hold' },
      ],
    });

    const roundTripped = rowsToConfig(rows, meta, config.output, clipOrder, tracks, undefined, config);

    expect(roundTripped.clips[0].keyframes).toEqual({
      opacity: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 2, value: 1, interpolation: 'linear' },
        { time: 4, value: 0.5, interpolation: 'hold' },
      ],
    });
  });

  it('round-trips keyframes through buildTimelineData and rowsToConfig', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-kf-build',
          at: 0,
          track: 'V1',
          clipType: 'contributed:keyframed',
          hold: 5,
          params: { color: '#ff0000' },
          keyframes: {
            intensity: [
              { time: 0, value: 0, interpolation: 'linear' },
              { time: 5, value: 1, interpolation: 'linear' },
            ],
          },
        },
      ],
    };

    const data = await buildTimelineData(config, registry);

    expect(data.meta['clip-kf-build'].keyframes).toEqual({
      intensity: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 5, value: 1, interpolation: 'linear' },
      ],
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

    expect(roundTripped.clips[0].keyframes).toEqual({
      intensity: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 5, value: 1, interpolation: 'linear' },
      ],
    });
    expect(roundTripped.clips[0].params).toEqual({ color: '#ff0000' });
  });
});
