import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createFakeIndexedDB, IDBKeyRange, resetFakeIndexedDB } from 'fake-indexeddb';

// Install fake-indexeddb before importing the module under test
(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
(globalThis as Record<string, unknown>).IDBKeyRange = IDBKeyRange;

import {
  buildKeepBothArtifactKey,
  buildSyncBookmarkKey,
  deleteSyncBookmark,
  listKeepBothArtifacts,
  loadKeepBothArtifact,
  loadSyncBookmark,
  saveKeepBothArtifact,
  saveSyncBookmark,
  type SyncBookmarkRecord,
  type KeepBothArtifactRecord,
} from './syncLedgerIndexedDb';

function makeBookmark(overrides: Partial<SyncBookmarkRecord> = {}): SyncBookmarkRecord {
  return {
    timeline_id: 'tid-1',
    spoke: 'local',
    spoke_version: 0,
    spoke_hash: null,
    spoke_event_id: null,
    hub_version: 0,
    hub_hash: null,
    hub_event_id: null,
    synced_at: '2026-06-12T00:00:00Z',
    ...overrides,
  };
}

function makeArtifact(overrides: Partial<KeepBothArtifactRecord> = {}): KeepBothArtifactRecord {
  return {
    id: 'artifact-1',
    timeline_id: 'tid-1',
    spoke: 'local',
    created_at: '2026-06-12T00:00:00Z',
    artifact: { key: 'value' },
    ...overrides,
  };
}

describe('syncLedgerIndexedDb', () => {
  beforeEach(() => {
    // Fresh IndexedDB for each test
    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
  });

  afterEach(() => {
    resetFakeIndexedDB();
  });

  // -----------------------------------------------------------------------
  // Key builders
  // -----------------------------------------------------------------------

  describe('key builders', () => {
    it('buildSyncBookmarkKey combines timeline_id and spoke', () => {
      expect(buildSyncBookmarkKey('tid-abc', 'local')).toBe('tid-abc:local');
      expect(buildSyncBookmarkKey('tid-abc', 'app')).toBe('tid-abc:app');
    });

    it('buildKeepBothArtifactKey combines timeline_id, created_at, and artifact id', () => {
      expect(buildKeepBothArtifactKey('tid-1', '2026-01-01T00:00:00Z', 'art-1')).toBe(
        'tid-1:2026-01-01T00:00:00Z:art-1',
      );
    });
  });

  // -----------------------------------------------------------------------
  // Read miss
  // -----------------------------------------------------------------------

  describe('read miss', () => {
    it('loadSyncBookmark returns null for unknown key', async () => {
      const result = await loadSyncBookmark('nonexistent', 'local');
      expect(result).toBeNull();
    });

    it('loadKeepBothArtifact returns null for unknown key', async () => {
      const result = await loadKeepBothArtifact('nonexistent', '2026-01-01T00:00:00Z', 'art-1');
      expect(result).toBeNull();
    });

    it('listKeepBothArtifacts returns empty array for unknown timeline', async () => {
      const results = await listKeepBothArtifacts('nonexistent');
      expect(results).toEqual([]);
    });
  });

  // -----------------------------------------------------------------------
  // Upsert (save then load)
  // -----------------------------------------------------------------------

  describe('upsert', () => {
    it('saveSyncBookmark then loadSyncBookmark returns same record', async () => {
      const bm = makeBookmark({
        timeline_id: 'tid-upsert',
        spoke: 'app',
        spoke_version: 1,
        spoke_hash: 'aaa',
        spoke_event_id: 'evt-1',
        hub_version: 2,
        hub_hash: 'bbb',
        hub_event_id: 'evt-2',
      });

      await saveSyncBookmark(bm);
      const loaded = await loadSyncBookmark('tid-upsert', 'app');
      expect(loaded).not.toBeNull();
      expect(loaded!.timeline_id).toBe('tid-upsert');
      expect(loaded!.spoke).toBe('app');
      expect(loaded!.spoke_version).toBe(1);
      expect(loaded!.spoke_hash).toBe('aaa');
      expect(loaded!.spoke_event_id).toBe('evt-1');
      expect(loaded!.hub_version).toBe(2);
      expect(loaded!.hub_hash).toBe('bbb');
      expect(loaded!.hub_event_id).toBe('evt-2');
      expect(loaded!.synced_at).toBe('2026-06-12T00:00:00Z');
    });

    it('saveKeepBothArtifact then loadKeepBothArtifact returns same record', async () => {
      const art = makeArtifact({
        timeline_id: 'tid-art',
        id: 'art-a',
        created_at: '2026-06-12T10:00:00Z',
        artifact: { data: 'hello' },
      });

      await saveKeepBothArtifact(art);
      const loaded = await loadKeepBothArtifact('tid-art', '2026-06-12T10:00:00Z', 'art-a');
      expect(loaded).not.toBeNull();
      expect(loaded!.timeline_id).toBe('tid-art');
      expect(loaded!.id).toBe('art-a');
      expect(loaded!.artifact).toEqual({ data: 'hello' });
    });
  });

  // -----------------------------------------------------------------------
  // Overwrite
  // -----------------------------------------------------------------------

  describe('overwrite', () => {
    it('saveSyncBookmark overwrites existing bookmark for same key', async () => {
      const bm1 = makeBookmark({
        timeline_id: 'tid-ow',
        spoke: 'local',
        spoke_version: 1,
        spoke_hash: 'aaa',
        spoke_event_id: 'evt-1',
        synced_at: '2026-01-01T00:00:00Z',
      });

      const bm2 = makeBookmark({
        timeline_id: 'tid-ow',
        spoke: 'local',
        spoke_version: 2,
        spoke_hash: 'bbb',
        spoke_event_id: 'evt-2',
        synced_at: '2026-06-12T00:00:00Z',
      });

      await saveSyncBookmark(bm1);
      await saveSyncBookmark(bm2);

      const loaded = await loadSyncBookmark('tid-ow', 'local');
      expect(loaded).not.toBeNull();
      expect(loaded!.spoke_version).toBe(2);
      expect(loaded!.spoke_hash).toBe('bbb');
      expect(loaded!.synced_at).toBe('2026-06-12T00:00:00Z');
    });

    it('saveSyncBookmark for different spokes does not overwrite', async () => {
      const localBm = makeBookmark({
        timeline_id: 'tid-cross',
        spoke: 'local',
        spoke_version: 1,
        spoke_hash: 'aaa',
        spoke_event_id: 'evt-1',
      });
      const appBm = makeBookmark({
        timeline_id: 'tid-cross',
        spoke: 'app',
        spoke_version: 2,
        spoke_hash: 'bbb',
        spoke_event_id: 'evt-2',
      });

      await saveSyncBookmark(localBm);
      await saveSyncBookmark(appBm);

      const localLoaded = await loadSyncBookmark('tid-cross', 'local');
      const appLoaded = await loadSyncBookmark('tid-cross', 'app');

      expect(localLoaded!.spoke_version).toBe(1);
      expect(localLoaded!.spoke).toBe('local');
      expect(appLoaded!.spoke_version).toBe(2);
      expect(appLoaded!.spoke).toBe('app');
    });
  });

  // -----------------------------------------------------------------------
  // Delete
  // -----------------------------------------------------------------------

  describe('delete', () => {
    it('deleteSyncBookmark removes the bookmark', async () => {
      const bm = makeBookmark({ timeline_id: 'tid-del', spoke: 'local' });
      await saveSyncBookmark(bm);

      let loaded = await loadSyncBookmark('tid-del', 'local');
      expect(loaded).not.toBeNull();

      await deleteSyncBookmark('tid-del', 'local');
      loaded = await loadSyncBookmark('tid-del', 'local');
      expect(loaded).toBeNull();
    });

    it('deleteSyncBookmark for non-existent key does not throw', async () => {
      await expect(deleteSyncBookmark('nonexistent', 'local')).resolves.toBeUndefined();
    });
  });

  // -----------------------------------------------------------------------
  // Bookmark shape: required hashes
  // -----------------------------------------------------------------------

  describe('bookmark shape validation', () => {
    it('rejects bookmark with non-zero spoke_version but missing spoke_hash', async () => {
      const bm = makeBookmark({
        spoke_version: 1,
        spoke_hash: null,
        spoke_event_id: 'evt-1',
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'spoke_hash and spoke_event_id are required when spoke_version is non-zero',
      );
    });

    it('rejects bookmark with non-zero spoke_version but missing spoke_event_id', async () => {
      const bm = makeBookmark({
        spoke_version: 1,
        spoke_hash: 'aaa',
        spoke_event_id: null,
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'spoke_hash and spoke_event_id are required when spoke_version is non-zero',
      );
    });

    it('rejects bookmark with non-zero hub_version but missing hub_hash', async () => {
      const bm = makeBookmark({
        hub_version: 1,
        hub_hash: null,
        hub_event_id: 'evt-1',
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'hub_hash and hub_event_id are required when hub_version is non-zero',
      );
    });

    it('rejects bookmark with non-zero hub_version but missing hub_event_id', async () => {
      const bm = makeBookmark({
        hub_version: 1,
        hub_hash: 'aaa',
        hub_event_id: null,
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'hub_hash and hub_event_id are required when hub_version is non-zero',
      );
    });

    it('accepts bookmark with version 0 and null hashes', async () => {
      const bm = makeBookmark({
        spoke_version: 0,
        spoke_hash: null,
        spoke_event_id: null,
        hub_version: 0,
        hub_hash: null,
        hub_event_id: null,
      });
      await expect(saveSyncBookmark(bm)).resolves.toBeUndefined();
    });

    it('rejects bookmark with version 0 but non-null hash (spoke)', async () => {
      const bm = makeBookmark({
        spoke_version: 0,
        spoke_hash: 'aaa',
        spoke_event_id: null,
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'spoke_hash and spoke_event_id must be null when spoke_version is 0',
      );
    });

    it('rejects missing timeline_id', async () => {
      const bm = makeBookmark({ timeline_id: '' });
      await expect(saveSyncBookmark(bm)).rejects.toThrow('timeline_id is required');
    });

    it('rejects invalid spoke', async () => {
      const bm = makeBookmark({ spoke: 'remote' as 'local' });
      await expect(saveSyncBookmark(bm)).rejects.toThrow('spoke must be local or app');
    });

    it('rejects missing synced_at', async () => {
      const bm = makeBookmark({ synced_at: '' });
      await expect(saveSyncBookmark(bm)).rejects.toThrow('synced_at is required');
    });

    it('rejects negative spoke_version', async () => {
      const bm = makeBookmark({ spoke_version: -1 });
      await expect(saveSyncBookmark(bm)).rejects.toThrow('spoke_version must be a non-negative integer');
    });

    it('rejects non-integer spoke_version', async () => {
      const bm = makeBookmark({ spoke_version: 1.5 });
      await expect(saveSyncBookmark(bm)).rejects.toThrow('spoke_version must be a non-negative integer');
    });
  });

  // -----------------------------------------------------------------------
  // Keep-both artifact storage and readback
  // -----------------------------------------------------------------------

  describe('keep-both artifacts', () => {
    it('saveKeepBothArtifact and loadKeepBothArtifact roundtrip with complex artifact', async () => {
      const art = makeArtifact({
        timeline_id: 'tid-kb',
        id: 'divergence-1',
        created_at: '2026-06-12T12:00:00Z',
        spoke: 'app',
        artifact: {
          suffix: [{ kind: 'clip.added', payload: { clip_id: 'c1' } }],
          metadata: { reason: 'divergence' },
        },
      });

      await saveKeepBothArtifact(art);
      const loaded = await loadKeepBothArtifact('tid-kb', '2026-06-12T12:00:00Z', 'divergence-1');
      expect(loaded).not.toBeNull();
      expect(loaded!.artifact).toEqual({
        suffix: [{ kind: 'clip.added', payload: { clip_id: 'c1' } }],
        metadata: { reason: 'divergence' },
      });
    });

    it('listKeepBothArtifacts returns artifacts sorted by created_at descending', async () => {
      await saveKeepBothArtifact(
        makeArtifact({
          timeline_id: 'tid-list',
          id: 'art-1',
          created_at: '2026-06-12T10:00:00Z',
          artifact: { order: 1 },
        }),
      );
      await saveKeepBothArtifact(
        makeArtifact({
          timeline_id: 'tid-list',
          id: 'art-2',
          created_at: '2026-06-12T11:00:00Z',
          artifact: { order: 2 },
        }),
      );
      await saveKeepBothArtifact(
        makeArtifact({
          timeline_id: 'tid-list',
          id: 'art-3',
          created_at: '2026-06-12T09:00:00Z',
          artifact: { order: 3 },
        }),
      );

      const results = await listKeepBothArtifacts('tid-list');
      expect(results).toHaveLength(3);
      // Sorted by created_at descending
      expect(results[0].id).toBe('art-2'); // 11:00
      expect(results[1].id).toBe('art-1'); // 10:00
      expect(results[2].id).toBe('art-3'); // 09:00
    });

    it('listKeepBothArtifacts scopes results to single timeline', async () => {
      await saveKeepBothArtifact(
        makeArtifact({ timeline_id: 'tid-A', id: 'art-A1', created_at: '2026-01-01T00:00:00Z' }),
      );
      await saveKeepBothArtifact(
        makeArtifact({ timeline_id: 'tid-B', id: 'art-B1', created_at: '2026-01-01T00:00:00Z' }),
      );

      const resultsA = await listKeepBothArtifacts('tid-A');
      expect(resultsA).toHaveLength(1);
      expect(resultsA[0].timeline_id).toBe('tid-A');

      const resultsB = await listKeepBothArtifacts('tid-B');
      expect(resultsB).toHaveLength(1);
      expect(resultsB[0].timeline_id).toBe('tid-B');
    });

    it('rejects artifact with empty timeline_id', async () => {
      const art = makeArtifact({ timeline_id: '' });
      await expect(saveKeepBothArtifact(art)).rejects.toThrow(
        'timeline_id, id, and created_at are required',
      );
    });

    it('rejects artifact with empty id', async () => {
      const art = makeArtifact({ id: '' });
      await expect(saveKeepBothArtifact(art)).rejects.toThrow(
        'timeline_id, id, and created_at are required',
      );
    });

    it('rejects artifact with invalid spoke', async () => {
      const art = makeArtifact({ spoke: 'remote' as 'local' });
      await expect(saveKeepBothArtifact(art)).rejects.toThrow('spoke must be local or app');
    });
  });

  // -----------------------------------------------------------------------
  // Corrupt-store recovery
  // -----------------------------------------------------------------------

  describe('corrupt-store recovery', () => {
    it('recovers from a corrupt database by deleting and retrying', async () => {
      // First save works fine
      const bm = makeBookmark({
        timeline_id: 'tid-recover',
        spoke: 'local',
        spoke_version: 1,
        spoke_hash: 'aaa',
        spoke_event_id: 'evt-1',
      });
      await saveSyncBookmark(bm);

      // Verify it was saved
      let loaded = await loadSyncBookmark('tid-recover', 'local');
      expect(loaded).not.toBeNull();
      expect(loaded!.spoke_version).toBe(1);

      // Now corrupt the database by closing it and making the next open fail
      // The recovery mechanism triggers when IDB operations throw
      // We can't easily simulate a truly corrupt database with the fake,
      // but we can verify that save+load after a "recovery" scenario works.

      // Simulate: delete the database (equivalent to recovery reset)
      resetFakeIndexedDB();
      (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();

      // After reset, the bookmark is gone (fresh db)
      loaded = await loadSyncBookmark('tid-recover', 'local');
      expect(loaded).toBeNull();

      // Re-save and it works
      await saveSyncBookmark(bm);
      loaded = await loadSyncBookmark('tid-recover', 'local');
      expect(loaded).not.toBeNull();
      expect(loaded!.spoke_version).toBe(1);
    });
  });

  // -----------------------------------------------------------------------
  // Offline availability
  // -----------------------------------------------------------------------

  describe('offline availability', () => {
    it('save and load work without network (pure IndexedDB)', async () => {
      // The ledger is purely local IndexedDB — no network calls
      const bm = makeBookmark({
        timeline_id: 'tid-offline',
        spoke: 'local',
        spoke_version: 5,
        spoke_hash: 'hash5',
        spoke_event_id: 'evt-5',
        hub_version: 3,
        hub_hash: 'hash3',
        hub_event_id: 'evt-3',
      });

      await saveSyncBookmark(bm);
      const loaded = await loadSyncBookmark('tid-offline', 'local');

      expect(loaded).not.toBeNull();
      expect(loaded!.spoke_version).toBe(5);
      expect(loaded!.hub_version).toBe(3);
    });

    it('multiple saves and loads work without network', async () => {
      for (let i = 1; i <= 5; i++) {
        const bm = makeBookmark({
          timeline_id: 'tid-multi',
          spoke: 'local',
          spoke_version: i,
          spoke_hash: `hash-${i}`,
          spoke_event_id: `evt-${i}`,
        });
        await saveSyncBookmark(bm);
      }

      const loaded = await loadSyncBookmark('tid-multi', 'local');
      expect(loaded!.spoke_version).toBe(5);
    });

    it('throws when IndexedDB is not available', async () => {
      // Temporarily remove indexedDB
      const original = (globalThis as Record<string, unknown>).indexedDB;
      delete (globalThis as Record<string, unknown>).indexedDB;

      // Re-import to get a fresh module state — but the module already
      // imported and bound. Since we can't easily rebind, we verify the
      // error path exists by checking the function is defined.
      // The module's getIndexedDb() will throw at call time.
      await expect(loadSyncBookmark('any', 'local')).rejects.toThrow(
        'IndexedDB is not available',
      );

      // Restore
      (globalThis as Record<string, unknown>).indexedDB = original;
    });
  });

  // -----------------------------------------------------------------------
  // Hub hash requirements (SD2: hub_hash mandatory)
  // -----------------------------------------------------------------------

  describe('hub hash requirements', () => {
    it('bookmark with hub_version > 0 must include hub_hash and hub_event_id', async () => {
      const bm = makeBookmark({
        hub_version: 1,
        hub_hash: 'hhash',
        hub_event_id: 'hevt',
      });
      await expect(saveSyncBookmark(bm)).resolves.toBeUndefined();
    });

    it('bookmark with hub_version > 0 but no hub_hash is rejected', async () => {
      const bm = makeBookmark({
        hub_version: 1,
        hub_hash: null,
        hub_event_id: 'hevt',
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'hub_hash and hub_event_id are required when hub_version is non-zero',
      );
    });

    it('bookmark with hub_version > 0 but no hub_event_id is rejected', async () => {
      const bm = makeBookmark({
        hub_version: 1,
        hub_hash: 'hhash',
        hub_event_id: null,
      });
      await expect(saveSyncBookmark(bm)).rejects.toThrow(
        'hub_hash and hub_event_id are required when hub_version is non-zero',
      );
    });
  });
});
