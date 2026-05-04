import { describe, expect, it } from 'vitest';
import { repairConfig } from '@/tools/video-editor/lib/migrate';
import { serializeForDisk, validateSerializedConfig } from '@/tools/video-editor/lib/serialize';
import { TimelineDomainError, serializeTimelineConfigSnapshot, serializeTimelinePair } from '@/tools/video-editor/lib/timeline-domain';
import type { ResolvedTimelineConfig, TimelineConfig, TimelineClip } from '@/tools/video-editor/types';

describe('video-editor serialization', () => {
  it('preserves exact source fields and strips resolved-only data', () => {
    const resolved = {
      output: {
        resolution: '1280x720',
        fps: 30,
        file: 'out.mp4',
        background_scale: 1,
      },
      tracks: [
        {
          id: 'V1',
          kind: 'visual',
          label: 'V1',
          scale: 1,
          fit: 'manual',
          opacity: 1,
          blendMode: 'normal',
          extra: 'strip-me',
        },
      ],
      clips: [
        {
          id: 'clip-1',
          at: 1,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 5,
          opacity: 0.8,
          transition: { type: 'crossfade', duration: 0.4 },
          continuous: { type: 'custom:glow', intensity: 0.6 },
          assetEntry: { file: 'foo.png', src: 'https://example.com/foo.png' },
          extra: 'strip-me',
        },
      ],
      registry: {
        'asset-1': { file: 'foo.png', src: 'https://example.com/foo.png' },
      },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.output.background_scale).toBe(1);
    expect(serialized.clips[0]).not.toHaveProperty('assetEntry');
    expect(serialized.clips[0]).not.toHaveProperty('extra');
    expect(serialized.tracks?.[0]).not.toHaveProperty('extra');
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('round-trips pinnedShotGroups through serializeForDisk and validation', () => {
    const resolved = {
      output: {
        resolution: '1280x720',
        fps: 30,
        file: 'out.mp4',
      },
      tracks: [
        {
          id: 'V1',
          kind: 'visual',
          label: 'V1',
        },
      ],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 5,
        },
      ],
      registry: {
        'asset-1': { file: 'foo.png', src: 'https://example.com/foo.png' },
      },
    } as unknown as ResolvedTimelineConfig;

    const pinnedShotGroups: TimelineConfig['pinnedShotGroups'] = [
      {
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-1'],
        mode: 'images',
        imageClipSnapshot: [
          {
            clipId: 'clip-1',
            assetKey: 'asset-1',
            start: 0,
            end: 5,
            meta: {
              clipType: 'hold',
              hold: 5,
            },
          },
        ],
      },
    ];

    const serialized = serializeForDisk(resolved, pinnedShotGroups);

    expect(() => validateSerializedConfig(serialized)).not.toThrow();
    expect(serialized.pinnedShotGroups).toEqual(pinnedShotGroups);
  });

  // Sprint 2 schema-lift backward-compatibility guarantee: a pre-Sprint-2
  // timeline (with only the four built-in clipTypes and no theme / overrides)
  // round-trips through validateSerializedConfig untouched, and through
  // serializeForDisk preserving every field. New optional fields stay absent
  // unless the caller explicitly populates them.
  it('round-trips a pre-Sprint-2 timeline without injecting new optional fields', () => {
    const preSprint2Config: TimelineConfig = {
      output: {
        resolution: '1280x720',
        fps: 30,
        file: 'output.mp4',
      },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
      ],
      clips: [
        { id: 'clip-media', at: 0, track: 'V1', clipType: 'media', asset: 'a1', from: 0, to: 5 },
        { id: 'clip-hold', at: 5, track: 'V1', clipType: 'hold', asset: 'a2', hold: 3 },
        { id: 'clip-text', at: 8, track: 'V1', clipType: 'text', hold: 2, text: { content: 'hi' } },
        { id: 'clip-fx', at: 10, track: 'V1', clipType: 'effect-layer', hold: 1 },
      ],
    };

    expect(() => validateSerializedConfig(preSprint2Config)).not.toThrow();

    // serializeForDisk preserves the closed clipType union and emits no new
    // top-level fields when no `extras` are passed.
    const resolved = {
      output: preSprint2Config.output,
      tracks: preSprint2Config.tracks ?? [],
      clips: preSprint2Config.clips,
      registry: {},
    } as unknown as ResolvedTimelineConfig;
    const round = serializeForDisk(resolved);
    expect(round).toEqual(preSprint2Config);
    expect(round).not.toHaveProperty('theme');
    expect(round).not.toHaveProperty('theme_overrides');
    expect(round).not.toHaveProperty('generation_defaults');
  });

  it('tolerates an open clipType string (Sprint 2 SD-024 widening)', () => {
    const themedConfig: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        // Unknown clipType — Sprint 5 ships strict registry validation; for
        // now the validator must NOT reject this.
        { id: 'clip-themed', at: 0, track: 'V1', clipType: 'theme:karaoke-bouncing-ball', hold: 2 } as TimelineClip,
      ],
    };
    expect(() => validateSerializedConfig(themedConfig)).not.toThrow();
  });

  it('round-trips Sprint 2 schema-lift fields when callers populate them', () => {
    const resolved = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          asset: 'a1',
          from: 0,
          to: 5,
          // Sprint 2 clip-level lift fields:
          params: { intensity: 0.4 },
          pool_id: 'pool-visual-a',
          clip_order: 1,
          source_uuid: 'abcd1234',
        },
      ],
      registry: {},
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved, undefined, {
      theme: 'cinema-noir',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'kling-1.6' },
    });

    expect(serialized.theme).toBe('cinema-noir');
    expect(serialized.theme_overrides).toEqual({ visual: { canvas: { fps: 24 } } });
    expect(serialized.generation_defaults).toEqual({ model: 'kling-1.6' });
    expect(serialized.clips[0]).toMatchObject({
      params: { intensity: 0.4 },
      pool_id: 'pool-visual-a',
      clip_order: 1,
      source_uuid: 'abcd1234',
    });
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('serializes theme extras directly from resolved configs', () => {
    const resolved = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
      registry: {},
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.theme).toBe('2rp');
    expect(serialized.theme_overrides).toEqual({ visual: { canvas: { fps: 24 } } });
    expect(serialized.generation_defaults).toEqual({ model: 'sequence-v1' });
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('round-trips legacy pinnedShotGroups through repairConfig before serialization', () => {
    const repaired = repairConfig({
      output: {
        resolution: '1280x720',
        fps: 30,
        file: 'out.mp4',
      },
      tracks: [
        {
          id: 'V1',
          kind: 'visual',
          label: 'V1',
        },
      ],
      clips: [
        {
          id: 'clip-2',
          at: 5,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-2',
          hold: 3,
        },
        {
          id: 'clip-1',
          at: 1,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 4,
        },
      ],
      pinnedShotGroups: [{
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-2', 'clip-1'],
        mode: 'images',
        imageClipSnapshot: [
          {
            clipId: 'clip-1',
            assetKey: 'asset-1',
            start: 1,
            end: 5,
            meta: { clipType: 'hold', hold: 4 },
          },
        ],
        ...({
          start: 1,
          children: [
            { clipId: 'clip-1', offset: 0, duration: 4 },
            { clipId: 'clip-2', offset: 4, duration: 3 },
          ],
        } as unknown as object),
      }],
    } as TimelineConfig);

    expect(repaired.pinnedShotGroups).toEqual([{
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
      imageClipSnapshot: [
        {
          clipId: 'clip-1',
          assetKey: 'asset-1',
          start: 1,
          end: 5,
          meta: { clipType: 'hold', hold: 4 },
        },
      ],
    }]);

    const serialized = serializeForDisk({
      output: repaired.output,
      tracks: repaired.tracks ?? [],
      clips: repaired.clips,
      registry: {},
    } as unknown as ResolvedTimelineConfig, repaired.pinnedShotGroups);

    expect(() => validateSerializedConfig(serialized)).not.toThrow();
    expect(serialized.pinnedShotGroups).toEqual(repaired.pinnedShotGroups);
    expect(serialized.pinnedShotGroups?.[0]).not.toHaveProperty('start');
    expect(serialized.pinnedShotGroups?.[0]).not.toHaveProperty('children');
  });

  it('throws a structured TimelineDomainError for unexpected serialized keys', () => {
    expect(() => validateSerializedConfig({
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', extra: 'nope' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 1 }],
    } as TimelineConfig)).toThrow(TimelineDomainError);
  });

  it('serializes config-only and pair-aware contracts through the shared domain serializer', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [{ id: 'clip-1', at: 0, track: 'video', asset: 'asset-1' }],
    };

    const configOnly = serializeTimelineConfigSnapshot(config);
    expect(configOnly.level).toBe('config-only');
    expect(configOnly.config.tracks?.map((track) => track.id)).toEqual(['V1', 'V2', 'V3', 'A1']);
    expect(configOnly.issues.map((issue) => issue.code)).toContain('malformed_non_hold_trim_zero_duration');

    const pairAware = serializeTimelinePair(config, {
      assets: { 'asset-1': { file: 'video.mp4', duration: 3.5 } },
    });
    expect(pairAware.level).toBe('pair-aware');
    expect(pairAware.config.clips[0]).toMatchObject({ from: 0, to: 3.5 });
    expect(pairAware.registry.assets['asset-1']).toEqual({ file: 'video.mp4', duration: 3.5 });
  });
});
