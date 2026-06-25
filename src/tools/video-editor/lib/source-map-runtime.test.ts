/**
 * Tests for SourceMapRuntime — provider-scoped source-map entry lifecycle.
 *
 * @publicContract
 */

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { createSourceMapRuntime } from '@/tools/video-editor/lib/source-map-runtime';
import type {
  SourceMapRuntime,
  SourceMapEntry,
  TimelineOps,
  TimelineReader,
} from '@/sdk/index';
import type {
  TimelineDiff,
  TimelineDiffGranularity,
  TimelinePatch,
} from '@/sdk/video/timeline/patch.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface StoredEntry {
  value: unknown;
}

/** Build a mock app data store. */
function makeMockStore() {
  const store: Record<string, Record<string, unknown>> = {};

  return {
    getApp(extId: string): Record<string, unknown> {
      return store[extId] ?? {};
    },
    setApp(extId: string, data: Record<string, unknown>): void {
      store[extId] = { ...data };
    },
    getRaw(extId: string, key: string): unknown {
      return store[extId]?.[key];
    },
    setRaw(extId: string, key: string, value: unknown): void {
      store[extId] ??= {};
      store[extId][key] = value;
    },
    deleteRaw(extId: string, key: string): void {
      if (store[extId]) {
        delete store[extId][key];
        if (Object.keys(store[extId]).length === 0) {
          delete store[extId];
        }
      }
    },
    getAll(): Record<string, Record<string, unknown>> {
      return store;
    },
  };
}

function makeMockTimelineOps(store: ReturnType<typeof makeMockStore>, version: { current: number }): TimelineOps {
  return {
    validate: vi.fn(),
    preview: vi.fn(),
    apply: vi.fn((patch: TimelinePatch) => {
      for (const op of patch.operations) {
        if (op.op === 'project-data.write') {
          const key = op.payload?.key as string;
          const value = op.payload?.value;
          store.setRaw(op.target, key, value);
        } else if (op.op === 'project-data.delete') {
          const key = op.payload?.key as string;
          store.deleteRaw(op.target, key);
        }
      }
      version.current += 1;
      return { version: version.current, entries: [], affectedObjectIds: [] } as TimelineDiff;
    }),
    checkpoint: vi.fn(),
    rollback: vi.fn(),
    setAllTracksMuted: vi.fn(),
  };
}

function makeMockReader(store: ReturnType<typeof makeMockStore>, version: { current: number }): TimelineReader {
  return {
    snapshot: vi.fn(() => ({
      projectId: 'test-project',
      baseVersion: version.current,
      currentVersion: version.current,
      extensionRequirements: [],
      clips: [],
      tracks: [],
      assetKeys: [],
      app: store.getAll() as Record<string, unknown>,
    })),
  };
}

function makeRuntime() {
  const store = makeMockStore();
  const version = { current: 1 };
  const timelineOps = makeMockTimelineOps(store, version);
  const reader = makeMockReader(store, version);
  const runtime = createSourceMapRuntime({ timelineOps, reader });
  return { runtime, store, version, timelineOps, reader };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SourceMapRuntime', () => {
  let runtime: SourceMapRuntime;
  let store: ReturnType<typeof makeMockStore>;
  let timelineOps: TimelineOps;

  beforeEach(() => {
    const ctx = makeRuntime();
    runtime = ctx.runtime;
    store = ctx.store;
    timelineOps = ctx.timelineOps;
  });

  // ── create ────────────────────────────────────────────────────────────
  describe('create', () => {
    it('creates a new source-map entry with a generated ID', () => {
      const entry = runtime.create(
        'ext.a',
        'clip-1',
        'clip',
        'file:///dsl/main.ts',
        10, 0, 15, 0,
      );

      expect(entry.id).toMatch(/^sme-/);
      expect(entry.source).toBe('ext.a');
      expect(entry.targetId).toBe('clip-1');
      expect(entry.targetGranularity).toBe('clip');
      expect(entry.sourceUri).toBe('file:///dsl/main.ts');
      expect(entry.sourceStartLine).toBe(10);
      expect(entry.sourceStartColumn).toBe(0);
      expect(entry.sourceEndLine).toBe(15);
      expect(entry.sourceEndColumn).toBe(0);
      expect(entry.stale).toBe(false);
      expect(entry.meta).toBeUndefined();
    });

    it('persists the entry via project-data.write', () => {
      const entry = runtime.create('ext.a', 'clip-1', 'clip', 'file:///a.ts', 1, 0, 3, 0);
      
      // Verify it was applied through TimelineOps
      expect(timelineOps.apply).toHaveBeenCalled();
      
      // Verify the entry is in the store
      const raw = store.getRaw('ext.a', `__sm__:${entry.id}`);
      expect(raw).toBeDefined();
      expect((raw as Record<string, unknown>).id).toBe(entry.id);
    });

    it('creates entries with distinct IDs', () => {
      const e1 = runtime.create('ext.a', 'c1', 'clip', 'f1', 0, 0, 1, 0);
      const e2 = runtime.create('ext.a', 'c2', 'clip', 'f2', 0, 0, 1, 0);

      expect(e1.id).not.toBe(e2.id);
    });

    it('stores optional meta', () => {
      const entry = runtime.create(
        'ext.a', 'clip-1', 'clip', 'f.ts', 0, 0, 1, 0,
        { priority: 'high', tags: ['foo'] },
      );

      expect(entry.meta).toEqual({ priority: 'high', tags: ['foo'] });
      
      const raw = store.getRaw('ext.a', `__sm__:${entry.id}`);
      expect((raw as Record<string, unknown>).meta).toEqual({ priority: 'high', tags: ['foo'] });
    });
  });

  // ── get ───────────────────────────────────────────────────────────────
  describe('get', () => {
    it('returns undefined for non-existent entry', () => {
      expect(runtime.get('ext.a', 'sme-nonexistent')).toBeUndefined();
    });

    it('returns the created entry', () => {
      const entry = runtime.create('ext.a', 'clip-1', 'clip', 'f.ts', 0, 0, 1, 0);
      const retrieved = runtime.get('ext.a', entry.id);

      expect(retrieved).toBeDefined();
      expect(retrieved!.id).toBe(entry.id);
      expect(retrieved!.targetId).toBe('clip-1');
    });

    it('returns undefined for entry in different extension', () => {
      const entry = runtime.create('ext.a', 'clip-1', 'clip', 'f.ts', 0, 0, 1, 0);
      expect(runtime.get('ext.b', entry.id)).toBeUndefined();
    });
  });

  // ── getForTarget ──────────────────────────────────────────────────────
  describe('getForTarget', () => {
    it('returns empty array when no entries match', () => {
      expect(runtime.getForTarget('ext.a', 'nonexistent')).toEqual([]);
    });

    it('returns entries for the given target', () => {
      runtime.create('ext.a', 'clip-1', 'clip', 'f1.ts', 0, 0, 1, 0);
      runtime.create('ext.a', 'clip-1', 'clip', 'f2.ts', 5, 0, 10, 0);
      runtime.create('ext.a', 'clip-2', 'clip', 'f1.ts', 0, 0, 1, 0);

      const results = runtime.getForTarget('ext.a', 'clip-1');
      expect(results).toHaveLength(2);
      expect(results.every((e) => e.targetId === 'clip-1')).toBe(true);
    });

    it('only returns entries from the specified extension', () => {
      runtime.create('ext.a', 'clip-1', 'clip', 'f.ts', 0, 0, 1, 0);
      expect(runtime.getForTarget('ext.b', 'clip-1')).toEqual([]);
    });
  });

  // ── getForSource ──────────────────────────────────────────────────────
  describe('getForSource', () => {
    it('returns empty array when no entries match', () => {
      expect(runtime.getForSource('ext.a', 'nonexistent.ts')).toEqual([]);
    });

    it('returns entries for the given source URI', () => {
      runtime.create('ext.a', 'c1', 'clip', 'file:///main.ts', 1, 0, 2, 0);
      runtime.create('ext.a', 'c2', 'clip', 'file:///main.ts', 3, 0, 4, 0);
      runtime.create('ext.a', 'c3', 'clip', 'file:///other.ts', 0, 0, 1, 0);

      const results = runtime.getForSource('ext.a', 'file:///main.ts');
      expect(results).toHaveLength(2);
      expect(results.every((e) => e.sourceUri === 'file:///main.ts')).toBe(true);
    });

    it('only returns entries from the specified extension', () => {
      runtime.create('ext.a', 'c1', 'clip', 'shared.ts', 0, 0, 1, 0);
      expect(runtime.getForSource('ext.b', 'shared.ts')).toEqual([]);
    });
  });

  // ── markStale ─────────────────────────────────────────────────────────
  describe('markStale', () => {
    it('marks matching entries as stale', () => {
      runtime.create('ext.a', 'c1', 'clip', 'file:///main.ts', 0, 0, 1, 0);
      runtime.create('ext.a', 'c2', 'clip', 'file:///main.ts', 2, 0, 3, 0);
      runtime.create('ext.a', 'c3', 'clip', 'file:///other.ts', 0, 0, 1, 0);

      const updated = runtime.markStale('ext.a', 'file:///main.ts');

      expect(updated).toHaveLength(2);
      expect(updated.every((e) => e.stale)).toBe(true);

      // Verify persistence
      const all = runtime.getForSource('ext.a', 'file:///main.ts');
      expect(all.every((e) => e.stale)).toBe(true);

      // Unaffected entries remain non-stale
      const other = runtime.getForSource('ext.a', 'file:///other.ts');
      expect(other).toHaveLength(1);
      expect(other[0].stale).toBe(false);
    });

    it('returns already-stale entries without re-writing', () => {
      const entry = runtime.create('ext.a', 'c1', 'clip', 'f.ts', 0, 0, 1, 0);
      
      // First markStale
      runtime.markStale('ext.a', 'f.ts');
      
      // Second markStale should include the entry
      const updated = runtime.markStale('ext.a', 'f.ts');
      expect(updated).toHaveLength(1);
      expect(updated[0].stale).toBe(true);
    });

    it('returns empty array for no matches', () => {
      expect(runtime.markStale('ext.a', 'nonexistent')).toEqual([]);
    });
  });

  // ── markStaleForTarget ────────────────────────────────────────────────
  describe('markStaleForTarget', () => {
    it('marks entries for a specific target as stale', () => {
      runtime.create('ext.a', 'clip-1', 'clip', 'f1.ts', 0, 0, 1, 0);
      runtime.create('ext.a', 'clip-1', 'clip', 'f2.ts', 0, 0, 1, 0);
      runtime.create('ext.a', 'clip-2', 'clip', 'f1.ts', 0, 0, 1, 0);

      const updated = runtime.markStaleForTarget('ext.a', 'clip-1');

      expect(updated).toHaveLength(2);
      expect(updated.every((e) => e.stale && e.targetId === 'clip-1')).toBe(true);

      // clip-2 unaffected
      const forClip2 = runtime.getForTarget('ext.a', 'clip-2');
      expect(forClip2).toHaveLength(1);
      expect(forClip2[0].stale).toBe(false);
    });

    it('returns empty array for no matches', () => {
      expect(runtime.markStaleForTarget('ext.a', 'nonexistent')).toEqual([]);
    });
  });

  // ── delete ────────────────────────────────────────────────────────────
  describe('delete', () => {
    it('deletes an existing entry', () => {
      const entry = runtime.create('ext.a', 'c1', 'clip', 'f.ts', 0, 0, 1, 0);

      expect(runtime.delete('ext.a', entry.id)).toBe(true);
      expect(runtime.get('ext.a', entry.id)).toBeUndefined();
    });

    it('returns false for non-existent entry', () => {
      expect(runtime.delete('ext.a', 'nonexistent')).toBe(false);
    });

    it('only deletes from the specified extension', () => {
      const entry = runtime.create('ext.a', 'c1', 'clip', 'f.ts', 0, 0, 1, 0);
      expect(runtime.delete('ext.b', entry.id)).toBe(false);
      expect(runtime.get('ext.a', entry.id)).toBeDefined();
    });
  });

  // ── list ──────────────────────────────────────────────────────────────
  describe('list', () => {
    it('returns empty for extension with no entries', () => {
      expect(runtime.list('ext.a')).toEqual([]);
    });

    it('returns all entries for an extension', () => {
      runtime.create('ext.a', 'c1', 'clip', 'f1', 0, 0, 1, 0);
      runtime.create('ext.a', 'c2', 'clip', 'f2', 0, 0, 1, 0);

      const all = runtime.list('ext.a');
      expect(all).toHaveLength(2);
    });

    it('does not return entries from other extensions', () => {
      runtime.create('ext.a', 'ca', 'clip', 'fa', 0, 0, 1, 0);
      runtime.create('ext.b', 'cb', 'clip', 'fb', 0, 0, 1, 0);

      const aEntries = runtime.list('ext.a');
      expect(aEntries).toHaveLength(1);
      expect(aEntries[0].source).toBe('ext.a');
    });

    it('does not return non-source-map keys from project-data', () => {
      // Directly inject non-source-map data
      store.setRaw('ext.a', 'someConfig', { foo: 'bar' });
      runtime.create('ext.a', 'c1', 'clip', 'f1', 0, 0, 1, 0);

      const all = runtime.list('ext.a');
      expect(all).toHaveLength(1); // Only the source-map entry
    });
  });

  // ── Integration scenarios ─────────────────────────────────────────────
  describe('integration', () => {
    it('supports full lifecycle: create → query → mark stale → delete', () => {
      // Create entries
      const e1 = runtime.create('ext.dsl', 'clip-hero', 'clip', 'dsl://hero.section', 5, 2, 12, 0);
      const e2 = runtime.create('ext.dsl', 'clip-hero', 'clip', 'dsl://hero.section', 12, 0, 20, 0);
      const e3 = runtime.create('ext.dsl', 'clip-outro', 'clip', 'dsl://outro.section', 1, 0, 8, 0);

      // Query by target
      const heroEntries = runtime.getForTarget('ext.dsl', 'clip-hero');
      expect(heroEntries).toHaveLength(2);

      // Query by source
      const heroSectionEntries = runtime.getForSource('ext.dsl', 'dsl://hero.section');
      expect(heroSectionEntries).toHaveLength(2);

      // Mark stale after source edit
      const staleEntries = runtime.markStale('ext.dsl', 'dsl://hero.section');
      expect(staleEntries).toHaveLength(2);
      expect(staleEntries.every((e) => e.stale)).toBe(true);

      // Outro entries unaffected
      const outroEntries = runtime.getForTarget('ext.dsl', 'clip-outro');
      expect(outroEntries[0].stale).toBe(false);

      // Delete one stale entry
      expect(runtime.delete('ext.dsl', e1.id)).toBe(true);

      // Remaining entries
      expect(runtime.list('ext.dsl')).toHaveLength(2); // e2 + e3
    });

    it('stale flag survives re-read', () => {
      const entry = runtime.create('ext.a', 'c1', 'clip', 'f.ts', 0, 0, 1, 0);
      
      runtime.markStale('ext.a', 'f.ts');
      
      // Re-read through get
      const retrieved = runtime.get('ext.a', entry.id);
      expect(retrieved!.stale).toBe(true);
      
      // Re-read through list
      const all = runtime.list('ext.a');
      expect(all[0].stale).toBe(true);
    });

    it('delete removes from project-data and subsequent reads', () => {
      const entry = runtime.create('ext.a', 'c1', 'clip', 'f.ts', 0, 0, 1, 0);
      
      runtime.delete('ext.a', entry.id);
      
      expect(runtime.get('ext.a', entry.id)).toBeUndefined();
      expect(runtime.list('ext.a')).toEqual([]);
      expect(runtime.getForTarget('ext.a', 'c1')).toEqual([]);
    });

    it('handles multiple extensions independently', () => {
      runtime.create('ext.x', 'cx', 'clip', 'fx', 0, 0, 1, 0);
      runtime.create('ext.y', 'cy', 'clip', 'fy', 0, 0, 1, 0);

      expect(runtime.list('ext.x')).toHaveLength(1);
      expect(runtime.list('ext.y')).toHaveLength(1);

      runtime.markStale('ext.x', 'fx');
      
      const xEntries = runtime.list('ext.x');
      expect(xEntries[0].stale).toBe(true);
      
      const yEntries = runtime.list('ext.y');
      expect(yEntries[0].stale).toBe(false);
    });

    it('handles entries with track and asset granularity', () => {
      const e1 = runtime.create('ext.a', 'track-v1', 'track', 'dsl://music.ts', 0, 0, 10, 0);
      const e2 = runtime.create('ext.a', 'asset-bg', 'asset', 'dsl://bg.ts', 0, 0, 5, 0);

      expect(e1.targetGranularity).toBe('track');
      expect(e2.targetGranularity).toBe('asset');
    });

    it('handles entries with detailed source positions', () => {
      const entry = runtime.create(
        'ext.a', 'clip-1', 'clip',
        'file:///dsl/complex.ts',
        42, 5, 67, 12,
      );

      expect(entry.sourceStartLine).toBe(42);
      expect(entry.sourceStartColumn).toBe(5);
      expect(entry.sourceEndLine).toBe(67);
      expect(entry.sourceEndColumn).toBe(12);
    });
  });
});
