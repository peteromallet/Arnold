import { describe, expect, it } from 'vitest';
import { repairConfig } from '@/tools/video-editor/lib/migrate';
import { serializeClipForDisk, serializeForDisk, validateSerializedConfig } from '@/tools/video-editor/lib/serialize';
import {
  TIMELINE_POSTPROCESS_SHADER_APP_KEY,
  TimelineDomainError,
  serializeTimelineConfigSnapshot,
  serializeTimelinePair,
  validateTimelineConfigSnapshot,
} from '@/tools/video-editor/lib/timeline-domain';
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

  it('round-trips top-level app extension data through validation and serialization', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 1 }],
      app: { foo: 'bar' },
    };

    expect(validateTimelineConfigSnapshot(config).ok).toBe(true);

    const serialized = serializeTimelineConfigSnapshot(config).config;
    expect(serialized.app).toEqual({ foo: 'bar' });
    expect(serialized.app).not.toBe(config.app);
  });

  it('round-trips clip-level app extension data through validation and serialization', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          hold: 1,
          app: { 'x-reigh': { pinned: true } },
        },
      ],
    };

    expect(validateTimelineConfigSnapshot(config).ok).toBe(true);

    const serialized = serializeTimelineConfigSnapshot(config).config;
    expect(serialized.clips[0].app).toEqual({ 'x-reigh': { pinned: true } });
    expect(serialized.clips[0].app).not.toBe(config.clips[0].app);
    expect(serialized.clips[0].app?.['x-reigh']).not.toBe(config.clips[0].app?.['x-reigh']);
  });

  it('round-trips track-level app extension data through validation and serialization', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', app: { 'x-host': { mutedByPreset: true } } }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 1 }],
    };

    expect(validateTimelineConfigSnapshot(config).ok).toBe(true);

    const serialized = serializeTimelineConfigSnapshot(config).config;
    expect(serialized.tracks?.[0].app).toEqual({ 'x-host': { mutedByPreset: true } });
    expect(serialized.tracks?.[0].app).not.toBe(config.tracks?.[0].app);
    expect(serialized.tracks?.[0].app?.['x-host']).not.toBe(config.tracks?.[0].app?.['x-host']);
  });

  it('still rejects unknown sibling keys outside the app extension namespace', () => {
    const validation = validateTimelineConfigSnapshot({
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 1 }],
      garbage: 1,
    } as unknown as TimelineConfig);

    expect(validation.ok).toBe(false);
    expect(validation.issues).toMatchObject([
      {
        code: 'unexpected_top_level_key',
        message: "Serialized timeline has unexpected top-level key 'garbage'.",
        path: 'garbage',
      },
    ]);
  });

  it('preserves nested app x-reigh pinnedShotGroups data for the migration target', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 1 }],
      app: {
        'x-reigh': {
          pinnedShotGroups: [
            {
              shotId: 'shot-1',
              trackId: 'V1',
              clipIds: ['clip-1'],
            },
          ],
        },
      },
    };

    expect(validateTimelineConfigSnapshot(config).ok).toBe(true);

    const serialized = serializeTimelineConfigSnapshot(config).config;
    expect(serialized.app?.['x-reigh']).toEqual({
      pinnedShotGroups: [
        {
          shotId: 'shot-1',
          trackId: 'V1',
          clipIds: ['clip-1'],
        },
      ],
    });
    expect(serialized.app?.['x-reigh']).not.toBe(config.app?.['x-reigh']);
  });

  // ── M8: Transition params snapshot and round-trip ─────────────────────

  it('preserves transition.params through serializeForDisk round-trip', () => {
    const resolved = {
      output: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 3,
          transition: {
            type: 'crossfade',
            duration: 0.5,
            params: { easing: 'ease-in-out', intensity: 0.8 },
          },
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].transition).toBeDefined();
    expect(serialized.clips[0].transition?.type).toBe('crossfade');
    expect(serialized.clips[0].transition?.duration).toBe(0.5);
    expect(serialized.clips[0].transition?.params).toEqual({
      easing: 'ease-in-out',
      intensity: 0.8,
    });
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('preserves transition.params immutably through sanitizeTimelineClipSnapshot', () => {
    const clip: TimelineClip = {
      id: 'clip-1',
      at: 0,
      track: 'V1',
      clipType: 'hold',
      asset: 'asset-1',
      hold: 3,
      transition: {
        type: 'wipe',
        duration: 0.3,
        params: { direction: 'left', feather: 0.1 },
      },
    };

    const sanitized = serializeClipForDisk(clip);

    expect(sanitized.transition).toBeDefined();
    expect(sanitized.transition?.type).toBe('wipe');
    expect(sanitized.transition?.duration).toBe(0.3);
    expect(sanitized.transition?.params).toEqual({
      direction: 'left',
      feather: 0.1,
    });
    // Params object reference is preserved (same object identity for non-app fields)
    expect(sanitized.transition?.params).toBe(clip.transition?.params);
  });

  it('round-trips persisted transition params through serializeTimelineConfigSnapshot', () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 3,
          transition: {
            type: 'slide-push',
            duration: 0.6,
            params: {
              axis: 'x',
              overshoot: 1.05,
              nested: { key: 'value' },
            },
          },
        },
      ],
    };

    const snapshot = serializeTimelineConfigSnapshot(config);

    expect(snapshot.config.clips[0].transition).toBeDefined();
    expect(snapshot.config.clips[0].transition?.params).toEqual({
      axis: 'x',
      overshoot: 1.05,
      nested: { key: 'value' },
    });
    expect(snapshot.issues.every((i) => i.severity !== 'error')).toBe(true);
  });

  it('tolerates missing transition.params (backward compatible)', () => {
    const resolved = {
      output: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 3,
          transition: { type: 'crossfade', duration: 0.4 },
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].transition).toBeDefined();
    expect(serialized.clips[0].transition?.type).toBe('crossfade');
    expect(serialized.clips[0].transition?.params).toBeUndefined();
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('preserves empty transition.params object through round-trip', () => {
    const resolved = {
      output: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-1',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          asset: 'asset-1',
          hold: 3,
          transition: { type: 'zoom-through', duration: 0.7, params: {} },
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);
    expect(serialized.clips[0].transition?.params).toEqual({});
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  // ── M13: Shader metadata persistence ─────────────────────────────────

  it('round-trips clip-local and postprocess shader metadata through disk serialization', () => {
    const clipShader = {
      scope: 'clip',
      extensionId: 'com.example.shader',
      contributionId: 'clip-glow-shader',
      shaderId: 'shader.clipGlow',
      label: 'Clip glow',
      uniforms: { intensity: 0.75, tint: '#ffcc00' },
      enabled: true,
    } as const;
    const postprocessShader = {
      scope: 'postprocess',
      extensionId: 'com.example.shader',
      contributionId: 'grade-postprocess-shader',
      shaderId: 'shader.postGrade',
      label: 'Post grade',
      uniforms: { exposure: 0.2 },
      enabled: true,
    } as const;
    const resolved = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-shader',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          hold: 3,
          app: { shader: clipShader, untouched: { survives: true } },
        },
      ],
      registry: {},
      app: { [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: postprocessShader },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].app?.shader).toEqual(clipShader);
    expect(serialized.clips[0].app?.untouched).toEqual({ survives: true });
    expect(serialized.app?.[TIMELINE_POSTPROCESS_SHADER_APP_KEY]).toEqual(postprocessShader);
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  // ── M9: Keyframe serialization round-trip tests ──────────────────────

  it('round-trips clip keyframes through serializeForDisk and validation', () => {
    const resolved = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-kf',
          at: 0,
          track: 'V1',
          clipType: 'contributed:my-clip-type',
          asset: 'asset-1',
          hold: 5,
          params: { intensity: 0.5, color: '#ff0000' },
          keyframes: {
            intensity: [
              { time: 0, value: 0, interpolation: 'linear' },
              { time: 2.5, value: 1, interpolation: 'linear' },
              { time: 5, value: 0, interpolation: 'hold' },
            ],
            color: [
              { time: 0, value: '#ff0000', interpolation: 'hold' },
            ],
          },
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].keyframes).toBeDefined();
    expect(serialized.clips[0].keyframes?.intensity).toEqual([
      { time: 0, value: 0, interpolation: 'linear' },
      { time: 2.5, value: 1, interpolation: 'linear' },
      { time: 5, value: 0, interpolation: 'hold' },
    ]);
    expect(serialized.clips[0].keyframes?.color).toEqual([
      { time: 0, value: '#ff0000', interpolation: 'hold' },
    ]);
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('round-trips keyframes through serializeTimelineConfigSnapshot canonicalization', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'output.mp4' },
      clips: [
        {
          id: 'clip-animated',
          at: 0,
          track: 'V1',
          clipType: 'contributed:animated-text',
          hold: 4,
          params: { text: 'Hello' },
          keyframes: {
            scale: [
              { time: 0, value: 0.5, interpolation: 'linear' },
              { time: 2, value: 1.5, interpolation: 'linear' },
              { time: 4, value: 0.8, interpolation: 'linear' },
            ],
            visible: [
              { time: 0, value: true, interpolation: 'hold' },
              { time: 3, value: false, interpolation: 'hold' },
            ],
          },
        },
      ],
    };

    const snapshot = serializeTimelineConfigSnapshot(config);

    expect(snapshot.config.clips[0].keyframes).toBeDefined();
    expect(snapshot.config.clips[0].keyframes?.scale).toEqual([
      { time: 0, value: 0.5, interpolation: 'linear' },
      { time: 2, value: 1.5, interpolation: 'linear' },
      { time: 4, value: 0.8, interpolation: 'linear' },
    ]);
    expect(snapshot.config.clips[0].keyframes?.visible).toEqual([
      { time: 0, value: true, interpolation: 'hold' },
      { time: 3, value: false, interpolation: 'hold' },
    ]);
    expect(snapshot.issues.every((i) => i.severity !== 'error')).toBe(true);
  });

  it('tolerates missing keyframes on clips (backward compatible)', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'output.mp4' },
      clips: [
        {
          id: 'clip-no-kf',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          hold: 3,
          params: { intensity: 0.5 },
        },
      ],
    };

    const snapshot = serializeTimelineConfigSnapshot(config);

    expect(snapshot.config.clips[0].keyframes).toBeUndefined();
    expect(snapshot.config.clips[0].params).toEqual({ intensity: 0.5 });
    expect(snapshot.issues.every((i) => i.severity !== 'error')).toBe(true);
  });

  it('preserves empty keyframes object through round-trip', () => {
    const resolved = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-empty-kf',
          at: 0,
          track: 'V1',
          clipType: 'contributed:my-type',
          asset: 'asset-1',
          hold: 3,
          keyframes: {},
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);
    expect(serialized.clips[0].keyframes).toEqual({});
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  // ── M9: Automation clip payload round-trip tests ─────────────────────

  it('round-trips automation clip params through serializeForDisk and validation', () => {
    const automationParams = {
      target: {
        contributionId: 'myExt.myContrib',
        parameterPath: 'intensity',
      },
      keyframes: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 1, value: 0.8, interpolation: 'linear' },
        { time: 2, value: 0.2, interpolation: 'hold' },
      ],
      enabled: true,
    };

    const resolved = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-auto',
          at: 0,
          track: 'V1',
          clipType: 'automation',
          hold: 2,
          params: automationParams,
        },
      ],
      registry: {},
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].clipType).toBe('automation');
    expect(serialized.clips[0].params).toEqual(automationParams);
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('round-trips automation clip through serializeTimelineConfigSnapshot canonicalization', () => {
    const automationParams = {
      target: {
        contributionId: 'ext.filter',
        parameterPath: 'blur.radius',
      },
      keyframes: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 5, value: 10, interpolation: 'linear' },
      ],
      enabled: false,
    };

    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'output.mp4' },
      clips: [
        {
          id: 'clip-automation',
          at: 0,
          track: 'V1',
          clipType: 'automation',
          hold: 5,
          params: automationParams,
        },
      ],
    };

    const snapshot = serializeTimelineConfigSnapshot(config);

    expect(snapshot.config.clips[0].clipType).toBe('automation');
    expect(snapshot.config.clips[0].params).toEqual(automationParams);
    expect(snapshot.issues.every((i) => i.severity !== 'error')).toBe(true);
  });

  it('round-trips a clip with both keyframes and automation-style params', () => {
    const resolved = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-hybrid',
          at: 0,
          track: 'V1',
          clipType: 'contributed:advanced',
          asset: 'asset-1',
          hold: 4,
          params: {
            baseColor: '#00ff00',
            automationRef: {
              target: { contributionId: 'ext.helper', parameterPath: 'speed' },
              keyframes: [{ time: 0, value: 1, interpolation: 'linear' }],
              enabled: true,
            },
          },
          keyframes: {
            opacity: [
              { time: 0, value: 1, interpolation: 'linear' },
              { time: 4, value: 0, interpolation: 'linear' },
            ],
          },
        },
      ],
      registry: { 'asset-1': { file: 'foo.png' } },
    } as unknown as ResolvedTimelineConfig;

    const serialized = serializeForDisk(resolved);

    expect(serialized.clips[0].keyframes?.opacity).toEqual([
      { time: 0, value: 1, interpolation: 'linear' },
      { time: 4, value: 0, interpolation: 'linear' },
    ]);
    expect(serialized.clips[0].params).toEqual({
      baseColor: '#00ff00',
      automationRef: {
        target: { contributionId: 'ext.helper', parameterPath: 'speed' },
        keyframes: [{ time: 0, value: 1, interpolation: 'linear' }],
        enabled: true,
      },
    });
    expect(() => validateSerializedConfig(serialized)).not.toThrow();
  });

  it('keyframes survive pair-aware canonicalization with asset registry', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'output.mp4' },
      clips: [
        {
          id: 'clip-pair-kf',
          at: 0,
          track: 'V1',
          clipType: 'contributed:typed',
          asset: 'asset-dur',
          from: 0,
          to: 6,
          keyframes: {
            rotation: [
              { time: 0, value: 0, interpolation: 'linear' },
              { time: 6, value: 360, interpolation: 'linear' },
            ],
          },
        },
      ],
    };

    const pair = serializeTimelinePair(config, {
      assets: { 'asset-dur': { file: 'video.mp4', duration: 6 } },
    });

    expect(pair.config.clips[0].keyframes?.rotation).toEqual([
      { time: 0, value: 0, interpolation: 'linear' },
      { time: 6, value: 360, interpolation: 'linear' },
    ]);
    expect(pair.registry.assets['asset-dur']).toEqual({ file: 'video.mp4', duration: 6 });
    expect(pair.issues.every((i) => i.severity !== 'error')).toBe(true);
  });
});
