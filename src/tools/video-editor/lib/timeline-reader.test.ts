/**
 * Tests for TimelineReader and stable TimelineSnapshot projection.
 *
 * @publicContract
 */

import { describe, expect, it } from 'vitest';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader';
import type {
  TimelineReader,
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineTrackSummary,
  ProjectExtensionRequirement,
} from '@/sdk/index';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  TimelineConfig,
  AssetRegistry,
} from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const emptyRegistry: AssetRegistry = { assets: {} };

function makeBaseConfig(): TimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'Visual 1' },
      { id: 'A1', kind: 'audio', label: 'Audio 1', muted: true },
    ],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-1',
        from: 0,
        to: 2,
        speed: 1,
      },
      {
        id: 'clip-2',
        at: 2,
        track: 'V1',
        clipType: 'hold',
        hold: 3,
      },
      {
        id: 'clip-3',
        at: 5,
        track: 'A1',
        clipType: 'audio',
        asset: 'asset-audio',
        from: 0,
        to: 4,
        speed: 2,
      },
    ],
  };
}

const sampleRequirements: readonly ProjectExtensionRequirement[] = [
  {
    extensionId: 'com.example.ext',
    versionRange: '>=1.0.0',
    posture: 'required',
  },
  {
    extensionId: 'com.other.ext',
    versionRange: '^2.0.0',
    posture: 'optional',
  },
];

// ---------------------------------------------------------------------------
// Snapshot shape
// ---------------------------------------------------------------------------

describe('createTimelineReader — snapshot shape', () => {
  it('returns a snapshot with all required top-level keys', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot();

    expect(snap).toHaveProperty('projectId');
    expect(snap).toHaveProperty('baseVersion');
    expect(snap).toHaveProperty('currentVersion');
    expect(snap).toHaveProperty('extensionRequirements');
    expect(snap).toHaveProperty('clips');
    expect(snap).toHaveProperty('tracks');
    expect(snap).toHaveProperty('assetKeys');
    expect(snap).toHaveProperty('app');
  });

  it('returns projectId as null when not provided', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().projectId).toBeNull();
  });

  it('returns the provided projectId', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data, projectId: 'proj-42' });

    expect(reader.snapshot().projectId).toBe('proj-42');
  });

  it('baseVersion and currentVersion match configVersion', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry, undefined, 7);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot();
    expect(snap.baseVersion).toBe(7);
    expect(snap.currentVersion).toBe(7);
  });

  it('returns empty extensionRequirements when none provided', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().extensionRequirements).toEqual([]);
  });

  it('returns the provided extensionRequirements', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: sampleRequirements,
    });

    expect(reader.snapshot().extensionRequirements).toEqual(sampleRequirements);
  });
});

// ---------------------------------------------------------------------------
// Clip summaries
// ---------------------------------------------------------------------------

describe('createTimelineReader — clip summaries', () => {
  it('produces one summary per clip', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const clips = reader.snapshot().clips;
    expect(clips).toHaveLength(3);
  });

  it('includes id, track, at, clipType, and duration for every clip', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    for (const clip of reader.snapshot().clips) {
      expect(typeof clip.id).toBe('string');
      expect(clip.id.length).toBeGreaterThan(0);
      expect(typeof clip.track).toBe('string');
      expect(typeof clip.at).toBe('number');
      expect(typeof clip.duration).toBe('number');
      expect(clip.duration).toBeGreaterThanOrEqual(0);
    }
  });

  it('computes correct duration for from/to clips', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const clip1 = reader.snapshot().clips.find((c) => c.id === 'clip-1');
    expect(clip1).toBeDefined();
    // from=0, to=2, speed=1 => duration = 2 seconds
    expect(clip1!.duration).toBeCloseTo(2, 2);
  });

  it('computes correct duration for hold clips', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const clip2 = reader.snapshot().clips.find((c) => c.id === 'clip-2');
    expect(clip2).toBeDefined();
    expect(clip2!.duration).toBe(3);
  });

  it('computes correct duration with speed factor', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const clip3 = reader.snapshot().clips.find((c) => c.id === 'clip-3');
    expect(clip3).toBeDefined();
    // from=0, to=4, speed=2 => duration = (4-0)/2 = 2 seconds
    expect(clip3!.duration).toBeCloseTo(2, 2);
  });

  it('marks clips as unmanaged by default', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    for (const clip of reader.snapshot().clips) {
      expect(clip.managed).toBe(false);
      expect(clip).not.toHaveProperty('managedBy');
    }
  });

  it('detects managed clips via app.managedBy', async () => {
    const config: TimelineConfig = {
      ...makeBaseConfig(),
      clips: [
        {
          id: 'clip-managed',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: { managedBy: 'com.example.ext' },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: sampleRequirements,
    });

    const clip = reader.snapshot().clips.find((c) => c.id === 'clip-managed');
    expect(clip).toBeDefined();
    expect(clip!.managed).toBe(true);
    expect(clip!.managedBy).toBe('com.example.ext');
  });

  it('detects managed clips via extension-namespaced app key', async () => {
    const config: TimelineConfig = {
      ...makeBaseConfig(),
      clips: [
        {
          id: 'clip-ns',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: { 'com.example.ext': { someData: 42 } },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: sampleRequirements,
    });

    const clip = reader.snapshot().clips.find((c) => c.id === 'clip-ns');
    expect(clip).toBeDefined();
    expect(clip!.managed).toBe(true);
    expect(clip!.managedBy).toBe('com.example.ext');
  });

  it('does not mark clip as managed for unknown extension IDs in app', async () => {
    const config: TimelineConfig = {
      ...makeBaseConfig(),
      clips: [
        {
          id: 'clip-unknown',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: { someRandomKey: true },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: sampleRequirements,
    });

    const clip = reader.snapshot().clips.find((c) => c.id === 'clip-unknown');
    expect(clip).toBeDefined();
    expect(clip!.managed).toBe(false);
  });

  it('skips clips not present in meta', async () => {
    // Add a track with no clips and ensure no ghost summaries appear
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().clips).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Track summaries
// ---------------------------------------------------------------------------

describe('createTimelineReader — track summaries', () => {
  it('produces one summary per track', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().tracks).toHaveLength(2);
  });

  it('includes id, kind, label, muted for every track', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    for (const track of reader.snapshot().tracks) {
      expect(typeof track.id).toBe('string');
      expect(['visual', 'audio']).toContain(track.kind);
      expect(typeof track.label).toBe('string');
      expect(typeof track.muted).toBe('boolean');
    }
  });

  it('reports muted correctly', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const v1 = reader.snapshot().tracks.find((t) => t.id === 'V1');
    const a1 = reader.snapshot().tracks.find((t) => t.id === 'A1');
    expect(v1!.muted).toBe(false);
    expect(a1!.muted).toBe(true);
  });

  it('defaults muted to false when not set', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'T1', kind: 'visual', label: 'Track' }],
      clips: [],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().tracks[0].muted).toBe(false);
  });

  it('includes track app data when present', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [
        {
          id: 'T1',
          kind: 'visual',
          label: 'Track with app',
          app: { customKey: 'value' },
        },
      ],
      clips: [],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const track = reader.snapshot().tracks[0];
    expect(track.app).toEqual({ customKey: 'value' });
  });

  it('omits app when not present on track', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    for (const track of reader.snapshot().tracks) {
      expect(track).not.toHaveProperty('app');
    }
  });
});

// ---------------------------------------------------------------------------
// Asset keys
// ---------------------------------------------------------------------------

describe('createTimelineReader — asset keys', () => {
  it('returns empty assetKeys when registry is empty', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().assetKeys).toEqual([]);
  });

  it('returns registered asset keys', async () => {
    const registry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'asset-1.mp4', type: 'video/mp4' },
        'asset-audio': { file: 'audio.wav', type: 'audio/wav' },
      },
    };
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, registry);
    const reader = createTimelineReader({ data });

    const keys = reader.snapshot().assetKeys;
    expect(keys).toHaveLength(2);
    expect(keys).toContain('asset-1');
    expect(keys).toContain('asset-audio');
  });
});

// ---------------------------------------------------------------------------
// App data projection
// ---------------------------------------------------------------------------

describe('createTimelineReader — app data projection', () => {
  it('returns empty app when config has no app', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().app).toEqual({});
  });

  it('returns config app data', async () => {
    const config: TimelineConfig = {
      ...makeBaseConfig(),
      app: { 'com.example.ext': { key1: 'val1' } },
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    expect(reader.snapshot().app).toEqual({ 'com.example.ext': { key1: 'val1' } });
  });

  it('returns a shallow clone of app data (immutability)', async () => {
    const appData = { 'com.example.ext': { nested: true } };
    const config: TimelineConfig = {
      ...makeBaseConfig(),
      app: appData,
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap1 = reader.snapshot();
    const snap2 = reader.snapshot();

    // Same content, different reference
    expect(snap1.app).toEqual(snap2.app);
    expect(snap1.app).not.toBe(snap2.app);
    expect(snap1.app).not.toBe(appData);
  });
});

// ---------------------------------------------------------------------------
// Immutability / non-exposure of internals
// ---------------------------------------------------------------------------

describe('createTimelineReader — hides internals', () => {
  it('snapshot does not expose raw rows', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot() as Record<string, unknown>;
    expect(snap).not.toHaveProperty('rows');
    expect(snap).not.toHaveProperty('meta');
    expect(snap).not.toHaveProperty('effects');
    expect(snap).not.toHaveProperty('registry');
    expect(snap).not.toHaveProperty('resolvedConfig');
    expect(snap).not.toHaveProperty('clipOrder');
    expect(snap).not.toHaveProperty('signature');
    expect(snap).not.toHaveProperty('stableSignature');
    expect(snap).not.toHaveProperty('assetMap');
    expect(snap).not.toHaveProperty('config');
    expect(snap).not.toHaveProperty('configVersion');
  });

  it('snapshot clip summaries do not expose raw meta fields', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    for (const clip of reader.snapshot().clips) {
      const c = clip as Record<string, unknown>;
      expect(c).not.toHaveProperty('asset');
      expect(c).not.toHaveProperty('from');
      expect(c).not.toHaveProperty('to');
      expect(c).not.toHaveProperty('speed');
      expect(c).not.toHaveProperty('hold');
      expect(c).not.toHaveProperty('volume');
      expect(c).not.toHaveProperty('x');
      expect(c).not.toHaveProperty('y');
      expect(c).not.toHaveProperty('width');
      expect(c).not.toHaveProperty('height');
      expect(c).not.toHaveProperty('opacity');
      expect(c).not.toHaveProperty('text');
      expect(c).not.toHaveProperty('entrance');
      expect(c).not.toHaveProperty('exit');
      expect(c).not.toHaveProperty('effects');
      expect(c).not.toHaveProperty('params');
      expect(c).not.toHaveProperty('generation');
    }
  });
});

// ---------------------------------------------------------------------------
// Getter-based reader (dynamic data)
// ---------------------------------------------------------------------------

describe('createTimelineReader — getter-based', () => {
  it('supports a getter function for data', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);

    let called = 0;
    const reader = createTimelineReader({
      data: () => {
        called++;
        return data;
      },
    });

    reader.snapshot();
    reader.snapshot();
    expect(called).toBe(2);
  });

  it('reflects updated data when getter returns new state', async () => {
    const config1: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
    };
    const config2: TimelineConfig = {
      ...config1,
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 },
        { id: 'clip-2', at: 2, track: 'V1', clipType: 'hold', hold: 3 },
      ],
    };

    const data1 = await buildTimelineData(config1, emptyRegistry, undefined, 1);
    const data2 = await buildTimelineData(config2, emptyRegistry, undefined, 2);

    let current = data1;
    const reader = createTimelineReader({
      data: () => current,
      projectId: 'proj-1',
    });

    expect(reader.snapshot().clips).toHaveLength(1);
    expect(reader.snapshot().baseVersion).toBe(1);

    current = data2;
    expect(reader.snapshot().clips).toHaveLength(2);
    expect(reader.snapshot().baseVersion).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('createTimelineReader — edge cases', () => {
  it('handles empty timeline (no clips, no tracks)', async () => {
    // buildTimelineData canonicalizes and may add default tracks.
    // The reader reflects whatever tracks are present in the canonicalized data.
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [],
      clips: [],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot();
    expect(snap.clips).toEqual([]);
    expect(snap.assetKeys).toEqual([]);
    expect(snap.app).toEqual({});
    // Tracks may be present due to canonicalization; just verify shape.
    for (const track of snap.tracks) {
      expect(typeof track.id).toBe('string');
      expect(['visual', 'audio']).toContain(track.kind);
      expect(typeof track.label).toBe('string');
      expect(typeof track.muted).toBe('boolean');
    }
  });

  it('handles clips with no duration (zero from/to, no hold)', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'zero-clip',
          at: 0,
          track: 'V1',
          clipType: 'media',
          asset: 'some-asset',
          from: 0,
          to: 0,
          speed: 1,
        },
      ],
    };
    const data = await buildTimelineData(
      config,
      { assets: { 'some-asset': { file: 'f.mp4', type: 'video/mp4' } } },
    );
    const reader = createTimelineReader({ data });

    const clip = reader.snapshot().clips[0];
    expect(clip.duration).toBe(0);
  });

  it('snapshot clips are in config order', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const ids = reader.snapshot().clips.map((c) => c.id);
    expect(ids).toEqual(['clip-1', 'clip-2', 'clip-3']);
  });

  it('snapshot tracks are in config order', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const ids = reader.snapshot().tracks.map((t) => t.id);
    expect(ids).toEqual(['V1', 'A1']);
  });
});

// ---------------------------------------------------------------------------
// Representative timeline snapshots (T9)
// ---------------------------------------------------------------------------

describe('createTimelineReader — representative timeline snapshots', () => {
  it('produces a full snapshot for a media-heavy timeline', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'media-heavy.mp4' },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'Primary' },
        { id: 'V2', kind: 'visual', label: 'Overlay' },
        { id: 'A1', kind: 'audio', label: 'Audio', muted: false },
      ],
      clips: [
        { id: 'c1', at: 0, track: 'V1', clipType: 'media', asset: 'a1', from: 0, to: 5, speed: 1 },
        { id: 'c2', at: 5, track: 'V1', clipType: 'media', asset: 'a2', from: 2, to: 6, speed: 2 },
        { id: 'c3', at: 0, track: 'V2', clipType: 'media', asset: 'a1', from: 10, to: 15, speed: 1 },
        { id: 'c4', at: 0, track: 'A1', clipType: 'audio', asset: 'a3', from: 0, to: 7, speed: 1 },
      ],
      app: { 'com.example.ext': { projectSetting: 'enabled', count: 42 } },
    };
    const registry: AssetRegistry = {
      assets: {
        a1: { file: 'a1.mp4', type: 'video/mp4' },
        a2: { file: 'a2.mp4', type: 'video/mp4' },
        a3: { file: 'a3.wav', type: 'audio/wav' },
      },
    };
    const data = await buildTimelineData(config, registry, undefined, 3);
    const reader = createTimelineReader({
      data,
      projectId: 'proj-media-heavy',
      extensionRequirements: [
        { extensionId: 'com.example.ext', versionRange: '>=1.0.0', posture: 'required' },
      ],
    });

    const snap = reader.snapshot();

    // Top-level fields
    expect(snap.projectId).toBe('proj-media-heavy');
    expect(snap.baseVersion).toBe(3);
    expect(snap.currentVersion).toBe(3);
    expect(snap.extensionRequirements).toHaveLength(1);

    // Clips
    expect(snap.clips).toHaveLength(4);
    expect(snap.clips[0]).toMatchObject({ id: 'c1', track: 'V1', at: 0, clipType: 'media', duration: 5, managed: false });
    expect(snap.clips[1]).toMatchObject({ id: 'c2', track: 'V1', at: 5, clipType: 'media', duration: 2, managed: false }); // (6-2)/2 = 2
    expect(snap.clips[2]).toMatchObject({ id: 'c3', track: 'V2', at: 0, clipType: 'media', duration: 5, managed: false });
    expect(snap.clips[3]).toMatchObject({ id: 'c4', track: 'A1', at: 0, clipType: 'audio', duration: 7, managed: false });

    // Tracks
    expect(snap.tracks).toHaveLength(3);
    expect(snap.tracks[0]).toMatchObject({ id: 'V1', kind: 'visual', label: 'Primary', muted: false });
    expect(snap.tracks[1]).toMatchObject({ id: 'V2', kind: 'visual', label: 'Overlay', muted: false });
    expect(snap.tracks[2]).toMatchObject({ id: 'A1', kind: 'audio', label: 'Audio', muted: false });

    // Assets
    expect(snap.assetKeys).toHaveLength(3);
    expect(snap.assetKeys).toContain('a1');
    expect(snap.assetKeys).toContain('a2');
    expect(snap.assetKeys).toContain('a3');

    // App data
    expect(snap.app).toEqual({ 'com.example.ext': { projectSetting: 'enabled', count: 42 } });
  });

  it('produces a full snapshot for a hold-only timeline with mixed mute states', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1280x720', fps: 24, file: 'holds.mp4' },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'Visuals' },
        { id: 'A1', kind: 'audio', label: 'Music', muted: true },
        { id: 'A2', kind: 'audio', label: 'SFX', muted: false },
      ],
      clips: [
        { id: 'h1', at: 0, track: 'V1', clipType: 'hold', hold: 4 },
        { id: 'h2', at: 4, track: 'V1', clipType: 'hold', hold: 2.5 },
        { id: 'h3', at: 0, track: 'A2', clipType: 'audio', asset: 'sfx1', from: 0, to: 3, speed: 1 },
      ],
    };
    const registry: AssetRegistry = {
      assets: { sfx1: { file: 'sfx1.wav', type: 'audio/wav' } },
    };
    const data = await buildTimelineData(config, registry, undefined, 10);
    const reader = createTimelineReader({ data, projectId: 'proj-holds' });

    const snap = reader.snapshot();

    expect(snap.projectId).toBe('proj-holds');
    expect(snap.baseVersion).toBe(10);
    expect(snap.currentVersion).toBe(10);

    expect(snap.clips).toHaveLength(3);
    expect(snap.clips[0]).toMatchObject({ id: 'h1', track: 'V1', at: 0, duration: 4 });
    expect(snap.clips[1]).toMatchObject({ id: 'h2', track: 'V1', at: 4, duration: 2.5 });
    expect(snap.clips[2]).toMatchObject({ id: 'h3', track: 'A2', at: 0, duration: 3 });

    expect(snap.tracks).toHaveLength(3);
    expect(snap.tracks[0].muted).toBe(false);
    expect(snap.tracks[1].muted).toBe(true);
    expect(snap.tracks[2].muted).toBe(false);

    expect(snap.assetKeys).toEqual(['sfx1']);
    expect(snap.app).toEqual({});
  });

  it('produces a full snapshot with managed clips and extension project data', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'managed.mp4' },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'Main', app: { 'com.example.ext': { trackMeta: true } } },
      ],
      clips: [
        {
          id: 'm1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          asset: 'gen1',
          hold: 3,
          app: { managedBy: 'com.example.ext', generation: 'gen-abc' },
        },
        {
          id: 'm2',
          at: 3,
          track: 'V1',
          clipType: 'hold',
          hold: 2,
          app: { 'com.other.ext': { someNs: 'data' } },
        },
        {
          id: 'm3',
          at: 5,
          track: 'V1',
          clipType: 'media',
          asset: 'gen2',
          hold: 1,
          source_uuid: 'com.other.ext',
        },
      ],
      app: {
        'com.example.ext': { projectData: { key: 'value' } },
        'com.other.ext': { anotherKey: 123 },
      },
    };
    const registry: AssetRegistry = {
      assets: {
        gen1: { file: 'gen1.mp4', type: 'video/mp4' },
        gen2: { file: 'gen2.mp4', type: 'video/mp4' },
      },
    };
    const data = await buildTimelineData(config, registry, undefined, 5);
    const reader = createTimelineReader({
      data,
      projectId: 'proj-managed',
      extensionRequirements: [
        { extensionId: 'com.example.ext', versionRange: '>=1.0.0', posture: 'required' },
        { extensionId: 'com.other.ext', versionRange: '^2.0.0', posture: 'optional' },
      ],
    });

    const snap = reader.snapshot();

    // Managed clip detection
    const m1 = snap.clips.find((c) => c.id === 'm1');
    expect(m1).toBeDefined();
    expect(m1!.managed).toBe(true);
    expect(m1!.managedBy).toBe('com.example.ext');

    const m2 = snap.clips.find((c) => c.id === 'm2');
    expect(m2).toBeDefined();
    expect(m2!.managed).toBe(true);
    expect(m2!.managedBy).toBe('com.other.ext');

    const m3 = snap.clips.find((c) => c.id === 'm3');
    expect(m3).toBeDefined();
    expect(m3!.managed).toBe(true);
    expect(m3!.managedBy).toBe('com.other.ext'); // source_uuid match

    // Track with app data
    expect(snap.tracks[0].app).toEqual({ 'com.example.ext': { trackMeta: true } });

    // App data
    expect(snap.app).toEqual({
      'com.example.ext': { projectData: { key: 'value' } },
      'com.other.ext': { anotherKey: 123 },
    });

    expect(snap.assetKeys).toHaveLength(2);
    expect(snap.baseVersion).toBe(5);
  });

  it('produces a full snapshot for a complex reordered timeline', async () => {
    // Clips are in config order; verify snapshot preserves that order
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'reordered.mp4' },
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'A1', kind: 'audio', label: 'A1' },
      ],
      clips: [
        // Interleaved across tracks but in config order
        { id: 'c3', at: 10, track: 'V1', clipType: 'hold', hold: 2 },
        { id: 'c1', at: 0, track: 'V1', clipType: 'media', asset: 'a1', from: 0, to: 10, speed: 1 },
        { id: 'c4', at: 0, track: 'A1', clipType: 'audio', asset: 'a2', from: 5, to: 10, speed: 1 },
        { id: 'c2', at: 5, track: 'V1', clipType: 'hold', hold: 3 },
      ],
    };
    const registry: AssetRegistry = {
      assets: {
        a1: { file: 'a1.mp4', type: 'video/mp4' },
        a2: { file: 'a2.wav', type: 'audio/wav' },
      },
    };
    const data = await buildTimelineData(config, registry, undefined, 8);
    const reader = createTimelineReader({ data, projectId: 'proj-reordered' });

    const snap = reader.snapshot();

    // Clips in exact config order
    const ids = snap.clips.map((c) => c.id);
    expect(ids).toEqual(['c3', 'c1', 'c4', 'c2']);

    // Verify individual durations
    expect(snap.clips[0].duration).toBe(2);   // c3 hold=2
    expect(snap.clips[1].duration).toBe(10);  // c1 (10-0)/1 = 10
    expect(snap.clips[2].duration).toBe(5);   // c4 (10-5)/1 = 5
    expect(snap.clips[3].duration).toBe(3);   // c2 hold=3

    // Tracks in config order
    expect(snap.tracks.map((t) => t.id)).toEqual(['V1', 'A1']);
  });
});

// ---------------------------------------------------------------------------
// Provider configVersion behavior (T9)
// ---------------------------------------------------------------------------

describe('createTimelineReader — provider configVersion behavior', () => {
  it('baseVersion and currentVersion always equal configVersion from TimelineData', async () => {
    for (const version of [0, 1, 5, 42, 999]) {
      const config = makeBaseConfig();
      const data = await buildTimelineData(config, emptyRegistry, undefined, version);
      const reader = createTimelineReader({ data });

      const snap = reader.snapshot();
      expect(snap.baseVersion).toBe(version);
      expect(snap.currentVersion).toBe(version);
    }
  });

  it('each buildTimelineData call with different configVersion produces independent snapshots', async () => {
    const config = makeBaseConfig();
    const dataV3 = await buildTimelineData(config, emptyRegistry, undefined, 3);
    const dataV7 = await buildTimelineData(config, emptyRegistry, undefined, 7);

    const reader3 = createTimelineReader({ data: dataV3 });
    const reader7 = createTimelineReader({ data: dataV7 });

    expect(reader3.snapshot().baseVersion).toBe(3);
    expect(reader3.snapshot().currentVersion).toBe(3);
    expect(reader7.snapshot().baseVersion).toBe(7);
    expect(reader7.snapshot().currentVersion).toBe(7);
  });

  it('version is preserved when configVersion is 0 (initial state)', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'empty.mp4' },
      tracks: [],
      clips: [],
    };
    const data = await buildTimelineData(config, emptyRegistry, undefined, 0);
    const reader = createTimelineReader({ data, projectId: 'fresh-project' });

    const snap = reader.snapshot();
    expect(snap.baseVersion).toBe(0);
    expect(snap.currentVersion).toBe(0);
    expect(snap.projectId).toBe('fresh-project');
    expect(snap.clips).toEqual([]);
  });

  it('version is independent of timeline content', async () => {
    // Same version, different content — version remains stable
    const configA = makeBaseConfig();
    const configB: TimelineConfig = {
      output: { resolution: '1280x720', fps: 24, file: 'diff.mp4' },
      tracks: [{ id: 'T1', kind: 'visual', label: 'Only' }],
      clips: [],
    };

    const dataA = await buildTimelineData(configA, emptyRegistry, undefined, 15);
    const dataB = await buildTimelineData(configB, emptyRegistry, undefined, 15);

    const readerA = createTimelineReader({ data: dataA });
    const readerB = createTimelineReader({ data: dataB });

    expect(readerA.snapshot().baseVersion).toBe(15);
    expect(readerB.snapshot().baseVersion).toBe(15);

    // Content differs but version is the same
    expect(readerA.snapshot().clips.length).toBeGreaterThan(0);
    expect(readerB.snapshot().clips).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Version-based stale proposal invalidation (T9)
// ---------------------------------------------------------------------------

describe('createTimelineReader — version-based stale proposal invalidation', () => {
  it('getter-based reader reflects configVersion changes for staleness detection', async () => {
    // Simulate a proposal flow:
    // 1. Reader points to initial data at version N
    // 2. Proposal is created based on snapshot at version N
    // 3. An edit is committed, bumping version to N+1
    // 4. Reader now returns version N+1 — proposal is stale

    const config = makeBaseConfig();
    const dataV1 = await buildTimelineData(config, emptyRegistry, undefined, 1);
    const dataV2 = await buildTimelineData(config, emptyRegistry, undefined, 2);

    let currentData: TimelineData = dataV1;
    const reader = createTimelineReader({
      data: () => currentData,
      projectId: 'proj-stale-test',
    });

    // Step 1: Take initial snapshot — proposal base
    const proposalBase = reader.snapshot();
    expect(proposalBase.baseVersion).toBe(1);
    expect(proposalBase.currentVersion).toBe(1);

    // Step 2: Simulate an edit — provider bumps version
    currentData = dataV2;

    // Step 3: Reader now reflects new version
    const currentView = reader.snapshot();
    expect(currentView.baseVersion).toBe(2);
    expect(currentView.currentVersion).toBe(2);

    // Step 4: Staleness check — proposalBase version != current reader version
    const isStale = proposalBase.baseVersion !== currentView.baseVersion;
    expect(isStale).toBe(true);
  });

  it('stale proposal detection: re-snapshotting after version bump yields fresh base', async () => {
    const config = makeBaseConfig();
    const dataV1 = await buildTimelineData(config, emptyRegistry, undefined, 1);
    const dataV3 = await buildTimelineData(config, emptyRegistry, undefined, 3);

    let currentData: TimelineData = dataV1;
    const reader = createTimelineReader({
      data: () => currentData,
      projectId: 'proj-fresh-base',
    });

    // Proposal formed at V1
    const oldSnap = reader.snapshot();
    expect(oldSnap.baseVersion).toBe(1);

    // Edit bumps to V3
    currentData = dataV3;

    // Old snapshot is stale
    const newSnap = reader.snapshot();
    expect(oldSnap.baseVersion).not.toBe(newSnap.baseVersion);
    expect(newSnap.baseVersion).toBe(3);

    // New snapshot forms a valid base for a fresh proposal
    const freshBase = reader.snapshot();
    expect(freshBase.baseVersion).toBe(3);
    expect(freshBase.currentVersion).toBe(3);
    // No staleness when comparing fresh base to current reader
    expect(freshBase.baseVersion).toBe(reader.snapshot().baseVersion);
  });

  it('version stepping across multiple edits for sequential proposal invalidation', async () => {
    const config = makeBaseConfig();

    // Build data at versions 5, 6, 7
    const dataV5 = await buildTimelineData(config, emptyRegistry, undefined, 5);
    const dataV6 = await buildTimelineData(config, emptyRegistry, undefined, 6);
    const dataV7 = await buildTimelineData(config, emptyRegistry, undefined, 7);

    let currentData = dataV5;
    const reader = createTimelineReader({ data: () => currentData });

    // Proposal A based on V5
    const snapA = reader.snapshot();
    expect(snapA.baseVersion).toBe(5);

    // Edit 1 bumps to V6 — Proposal A becomes stale
    currentData = dataV6;
    expect(reader.snapshot().baseVersion).toBe(6);
    expect(snapA.baseVersion).not.toBe(reader.snapshot().baseVersion);

    // Proposal B based on V6
    const snapB = reader.snapshot();
    expect(snapB.baseVersion).toBe(6);

    // Edit 2 bumps to V7 — Proposal B becomes stale
    currentData = dataV7;
    expect(reader.snapshot().baseVersion).toBe(7);
    expect(snapB.baseVersion).not.toBe(reader.snapshot().baseVersion);

    // Proposal C based on V7
    const snapC = reader.snapshot();
    expect(snapC.baseVersion).toBe(7);
    expect(snapC.baseVersion).toBe(reader.snapshot().baseVersion); // fresh
  });

  it('static reader always returns the same version (no staleness possible)', async () => {
    // A static (non-getter) reader pins to a single snapshot forever.
    // There is no mechanism for staleness because the data never changes.
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry, undefined, 10);
    const reader = createTimelineReader({ data, projectId: 'static-proj' });

    const snap1 = reader.snapshot();
    const snap2 = reader.snapshot();
    const snap3 = reader.snapshot();

    expect(snap1.baseVersion).toBe(10);
    expect(snap1.baseVersion).toBe(snap2.baseVersion);
    expect(snap1.baseVersion).toBe(snap3.baseVersion);
    expect(snap1).toEqual(snap2);
    expect(snap1).toEqual(snap3);
  });

  it('proposal staleness check is reliable across getter-based reader', async () => {
    // Pattern: store proposalBaseVersion from snapshot, compare to reader.snapshot().baseVersion before accept
    const config = makeBaseConfig();
    const dataA = await buildTimelineData(config, emptyRegistry, undefined, 10);
    const dataB = await buildTimelineData(config, emptyRegistry, undefined, 11);

    let current = dataA;
    const reader = createTimelineReader({ data: () => current });

    function isProposalStale(proposalBaseVersion: number): boolean {
      return proposalBaseVersion !== reader.snapshot().baseVersion;
    }

    // Fresh proposal
    const proposalVersion = reader.snapshot().baseVersion;
    expect(isProposalStale(proposalVersion)).toBe(false);

    // Data changes
    current = dataB;
    expect(isProposalStale(proposalVersion)).toBe(true);

    // New proposal on fresh data
    const newProposalVersion = reader.snapshot().baseVersion;
    expect(isProposalStale(newProposalVersion)).toBe(false);
    expect(newProposalVersion).toBe(11);
  });
});
