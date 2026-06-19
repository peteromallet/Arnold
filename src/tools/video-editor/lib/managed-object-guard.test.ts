/**
 * Tests for ManagedObjectGuard.
 *
 * Covers:
 * - Managed clip detection via managedBy, extension namespace, and source_uuid
 * - Unmanaged clip returns null
 * - Track managed detection via generatedMeta
 * - detachManagedApp helper
 * - Already-detached clips bypass warning
 * - User-authored clips bypass warning
 */

import { describe, it, expect } from 'vitest';
import {
  createManagedObjectGuard,
  detachManagedApp,
  type ManagedObjectGuard,
  type ManagedObjectInfo,
} from '@/tools/video-editor/lib/managed-object-guard';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  TimelineConfig,
  AssetRegistry,
} from '@/tools/video-editor/types/index';
import type { ProjectExtensionRequirement, TimelineReader } from '@/sdk/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const emptyRegistry: AssetRegistry = { assets: {} };

function makeRequirement(extensionId: string): ProjectExtensionRequirement {
  return {
    extensionId,
    versionRange: '>=1.0.0',
    posture: 'required' as any,
  };
}

async function buildReader(
  config: TimelineConfig,
  extensionIds: string[] = [],
): Promise<{ reader: TimelineReader; data: TimelineData }> {
  const data = await buildTimelineData(config, emptyRegistry);
  const reader = createTimelineReader({
    data,
    extensionRequirements: extensionIds.map(makeRequirement),
  });
  return { reader, data };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ManagedObjectGuard', () => {
  describe('checkClipManaged', () => {
    it('returns null for an unmanaged clip', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          { id: 'clip-1', at: 0, track: 'track-1', clipType: 'video', from: 0, to: 5, speed: 1 },
        ],
      };
      const { reader } = await buildReader(config, []);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null for nonexistent clip', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [],
        clips: [],
      };
      const { reader } = await buildReader(config, []);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('nonexistent')).toBeNull();
    });

    it('detects clip managed via app.managedBy', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { managedBy: 'ext.dsl' } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      const info = guard.checkClipManaged('clip-1');
      expect(info).not.toBeNull();
      expect(info!.objectId).toBe('clip-1');
      expect(info!.kind).toBe('clip');
      expect(info!.managedBy).toBe('ext.dsl');
    });

    it('detects clip managed via extension namespace in app', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { 'ext.dsl': { someData: true } } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      const info = guard.checkClipManaged('clip-1');
      expect(info).not.toBeNull();
      expect(info!.managedBy).toBe('ext.dsl');
    });

    it('detects clip managed via source_uuid matching extension', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            source_uuid: 'ext.dsl',
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      const info = guard.checkClipManaged('clip-1');
      expect(info).not.toBeNull();
      expect(info!.managedBy).toBe('ext.dsl');
    });

    it('returns generatedMeta when clip has __generated__ in app', async () => {
      const generatedMeta = {
        extensionId: 'ext.dsl',
        contributionId: 'gen-foo',
        provenance: { prompt: 'test' },
        generatedAt: 1700000000000,
        sourceMapEntryId: 'sme-1',
      };
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: {
              managedBy: 'ext.dsl',
              __generated__: generatedMeta,
            } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      const info = guard.checkClipManaged('clip-1');
      expect(info).not.toBeNull();
      expect(info!.generatedMeta).toBeDefined();
      expect(info!.generatedMeta!.extensionId).toBe('ext.dsl');
      expect(info!.contributionId).toBe('gen-foo');
      expect(info!.sourceMapEntryId).toBe('sme-1');
      expect(info!.provenance).toEqual({ prompt: 'test' });
    });

    it('returns null for non-managed extension keys when extension not registered', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { 'ext.unknown': { data: true } } as any,
          },
        ],
      };
      // extension not in requirements, so 'ext.unknown' is not a known extension
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('does not flag clip as managed when only non-extension app keys exist', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { customKey: 'someValue' } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    // ── already-detached clips bypass warning ──────────────────────

    it('returns null for a clip whose managedBy was cleared (detached)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: {} as any, // managedBy was cleared by detach
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null after __generated__ metadata was removed (detached)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { customKey: 'still-present' } as any, // __generated__ removed
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null after extension namespace keys were cleared from app (detached)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { someData: true } as any, // extension namespace keys removed
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null after source_uuid was cleared (detached)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            // source_uuid cleared — not present
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('detachManagedApp output applied to a clip results in guard returning null', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: { custom: 'value', note: 'was managed, now detached' } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null for a clip with empty app (treated as detached)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
            app: {} as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    it('returns null for a clip with no app (treated as user-authored)', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 5,
            speed: 1,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('clip-1')).toBeNull();
    });

    // ── user-authored clips bypass warning ─────────────────────────

    it('does not flag a manually created clip with only non-extension app metadata', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'user-clip-1',
            at: 0,
            track: 'track-1',
            clipType: 'video',
            from: 0,
            to: 10,
            speed: 1,
            app: { notes: 'manually added', color: 'blue' } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('user-clip-1')).toBeNull();
    });

    it('does not flag a clip created by the user without any provenance', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'user-clip-2',
            at: 5,
            track: 'track-1',
            clipType: 'hold',
            hold: 3,
            label: 'user hold clip',
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('user-clip-2')).toBeNull();
    });

    it('does not flag a user-created audio clip', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-a1', kind: 'audio', label: 'A1' }],
        clips: [
          {
            id: 'user-audio-1',
            at: 0,
            track: 'track-a1',
            clipType: 'audio',
            from: 0,
            to: 8,
            speed: 1,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('user-audio-1')).toBeNull();
    });

    it('does not flag a hold clip created by the user', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'user-hold-1',
            at: 2,
            track: 'track-1',
            clipType: 'hold',
            hold: 5,
            app: { userLabel: 'my hold' } as any,
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('user-hold-1')).toBeNull();
    });

    it('does not flag a user-created text clip', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [
          {
            id: 'user-text-1',
            at: 1,
            track: 'track-1',
            clipType: 'text',
            from: 0,
            to: 4,
            speed: 1,
            text: 'Hello World',
          },
        ],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkClipManaged('user-text-1')).toBeNull();
    });
  });

  describe('checkTrackManaged', () => {
    it('returns null for a track without generatedMeta', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'track-1', kind: 'visual', label: 'V1' }],
        clips: [],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkTrackManaged('track-1')).toBeNull();
    });

    it('detects track managed via generatedMeta', async () => {
      const generatedMeta = {
        extensionId: 'ext.dsl',
        contributionId: 'track-gen-1',
      };
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [
          {
            id: 'track-1',
            kind: 'visual',
            label: 'V1',
            app: { __generated__: generatedMeta } as any,
          },
        ],
        clips: [],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      const info = guard.checkTrackManaged('track-1');
      expect(info).not.toBeNull();
      expect(info!.objectId).toBe('track-1');
      expect(info!.kind).toBe('track');
      expect(info!.managedBy).toBe('ext.dsl');
    });

    it('returns null for nonexistent track', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [],
        clips: [],
      };
      const { reader } = await buildReader(config, []);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkTrackManaged('nonexistent')).toBeNull();
    });

    it('returns null for user-authored track without generatedMeta', async () => {
      const config: TimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [
          { id: 'track-1', kind: 'visual', label: 'V1', app: { notes: 'custom' } as any },
        ],
        clips: [],
      };
      const { reader } = await buildReader(config, ['ext.dsl']);
      const guard = createManagedObjectGuard(reader);
      expect(guard.checkTrackManaged('track-1')).toBeNull();
    });
  });
});

describe('detachManagedApp', () => {
  const extIds = new Set(['ext.dsl', 'ext.fx']);

  it('returns undefined for undefined app', () => {
    expect(detachManagedApp(undefined, extIds)).toBeUndefined();
  });

  it('removes managedBy key', () => {
    const app = { managedBy: 'ext.dsl', customField: 'value' };
    const result = detachManagedApp(app, extIds);
    expect(result).toEqual({ customField: 'value' });
  });

  it('removes __generated__ key', () => {
    const app = { __generated__: { extensionId: 'ext.dsl' }, other: 1 };
    const result = detachManagedApp(app, extIds);
    expect(result).toEqual({ other: 1 });
  });

  it('removes extension namespace keys', () => {
    const app = { 'ext.dsl': { data: true }, 'ext.fx': { fx: true }, keep: 'me' };
    const result = detachManagedApp(app, extIds);
    expect(result).toEqual({ keep: 'me' });
  });

  it('returns undefined when all keys are removed', () => {
    const app = { managedBy: 'ext.dsl', __generated__: {} };
    const result = detachManagedApp(app, extIds);
    expect(result).toBeUndefined();
  });

  it('returns original app when no keys are managed', () => {
    const app = { custom: 'value' };
    const result = detachManagedApp(app, extIds);
    // Should return the same reference since nothing changed
    expect(result).toBe(app);
  });

  it('removes all managed keys simultaneously from a full managed app', () => {
    const app = {
      managedBy: 'ext.dsl',
      __generated__: { extensionId: 'ext.dsl', contributionId: 'gen-1' },
      'ext.dsl': { data: true },
      'ext.fx': { fx: true },
      userKey: 'preserve-me',
    };
    const result = detachManagedApp(app, extIds);
    expect(result).toEqual({ userKey: 'preserve-me' });
  });
});
