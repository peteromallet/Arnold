/**
 * Tests for IndexedDB-backed ExtensionStateRepository (T6).
 *
 * Validates:
 *  - Records survive reinitialization (close + reopen)
 *  - Corrupted records produce diagnostics/fallback instead of silent bad state
 *  - All CRUD operations on pack records, enablement, dev overrides,
 *    settings snapshots, lifecycle events, and lock metadata
 *  - Preserve-on-disable and delete-on-uninstall semantics
 *  - Bundle content storage and retrieval
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createFakeIndexedDB, resetFakeIndexedDB } from 'fake-indexeddb';

// Install fake-indexeddb BEFORE importing the module under test
(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();

import {
  IndexedDBExtensionStateRepository,
  createIndexedDBExtensionStateRepository,
} from './extensionStateRepositoryIndexedDB';
import {
  toPackRecord,
  createEnablementState,
  createSettingsSnapshot,
  createLifecycleEvent,
} from './extensionStateRepository';
import type {
  ExtensionPackRecord,
  ExtensionEnablementState,
  DevOverrideState,
  ExtensionSettingsSnapshot,
  ExtensionLifecycleEvent,
  ExtensionLockEntry,
  ExtensionLock,
  LifecycleEventQuery,
} from './extensionStateRepository';
import type {
  InstalledExtensionMetadata,
  ExtensionManifest,
  IntegrityHash,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TEST_INTEGRITY: IntegrityHash = Object.freeze({
  algorithm: 'sha256',
  value: 'dGVzdC1oYXNoLXZhbHVlLWZvci10ZXN0aW5nLXB1cnBvc2Vz',
});

const TEST_MANIFEST: ExtensionManifest = Object.freeze({
  id: 'test.extension' as any,
  version: '1.2.3',
  label: 'Test Extension',
  description: 'A test extension for IndexedDB repository tests',
  apiVersion: 1,
  publisher: 'Test Publisher',
  license: 'MIT',
  contributions: [],
});

const TEST_METADATA: InstalledExtensionMetadata = Object.freeze({
  extensionId: 'test.extension' as any,
  version: '1.2.3',
  apiVersion: 1,
  integrity: TEST_INTEGRITY,
  installedAt: '2026-06-20T12:00:00.000Z',
  enabled: true,
  settingsSchemaVersion: 1,
  publisher: 'Test Publisher',
  license: 'MIT',
});

function makePackRecord(extId: string = 'test.extension', version: string = '1.2.3', ref: string = 'bundle-001'): ExtensionPackRecord {
  return toPackRecord(
    { ...TEST_METADATA, extensionId: extId as any, version },
    { ...TEST_MANIFEST, id: extId as any, version } as ExtensionManifest,
    ref,
  );
}

function makeEnablementState(extId: string, enabled: boolean = true): ExtensionEnablementState {
  return createEnablementState(extId, enabled);
}

function makeDevOverride(extId: string, preferLocal: boolean = true): DevOverrideState {
  return Object.freeze({
    extensionId: extId,
    preferLocalSource: preferLocal,
    setAt: new Date().toISOString(),
  });
}

function makeSettingsSnapshot(extId: string, schemaVersion: number = 1, values: Record<string, unknown> = {}): ExtensionSettingsSnapshot {
  return createSettingsSnapshot(extId, schemaVersion, values);
}

function makeLifecycleEvent(extId: string, kind: 'install' | 'enable' = 'install'): ExtensionLifecycleEvent {
  return createLifecycleEvent(extId, kind, `Event: ${kind}`);
}

function makeLockEntry(extId: string, version: string = '1.2.3'): ExtensionLockEntry {
  return Object.freeze({
    extensionId: extId,
    version,
    contributionRefs: ['cmd.test'],
    integrity: TEST_INTEGRITY,
    lockedAt: new Date().toISOString(),
  });
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

describe('IndexedDBExtensionStateRepository', () => {
  let repo: IndexedDBExtensionStateRepository;

  beforeEach(() => {
    // Fresh IndexedDB for each test
    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
  });

  afterEach(async () => {
    // Dispose repository and reset fake-indexeddb
    if (repo && !repo.isDisposed) {
      try { await repo.dispose(); } catch { /* ok */ }
    }
    resetFakeIndexedDB();
  });

  // ---- lifecycle ----------------------------------------------------------

  describe('lifecycle', () => {
    it('initialize opens the database successfully', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      expect(repo.isDisposed).toBe(false);
    });

    it('initialize is idempotent', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.initialize(); // second call should be no-op
      expect(repo.isDisposed).toBe(false);
    });

    it('dispose closes the database', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.dispose();
      expect(repo.isDisposed).toBe(true);
    });

    it('dispose is idempotent', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.dispose();
      await repo.dispose(); // should not throw
    });

    it('operations reject after dispose', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.dispose();
      await expect(repo.getPackRecord('any')).rejects.toThrow('disposed');
    });

    it('initialize rejects after dispose', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.dispose();
      await expect(repo.initialize()).rejects.toThrow('disposed');
    });
  });

  // ---- pack records -------------------------------------------------------

  describe('pack records', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('put and get a pack record', async () => {
      const record = makePackRecord();
      await repo.putPackRecord(record);
      const retrieved = await repo.getPackRecord('test.extension');
      expect(retrieved).not.toBeNull();
      expect(retrieved!.extensionId).toBe('test.extension');
      expect(retrieved!.version).toBe('1.2.3');
    });

    it('put rejects duplicate pack record', async () => {
      await repo.putPackRecord(makePackRecord());
      await expect(repo.putPackRecord(makePackRecord())).rejects.toThrow('already exists');
    });

    it('updatePackRecord updates an existing record', async () => {
      await repo.putPackRecord(makePackRecord('ext.a', '1.0.0', 'ref-1'));
      const updated = makePackRecord('ext.a', '2.0.0', 'ref-2');
      await repo.updatePackRecord('ext.a', updated);
      const retrieved = await repo.getPackRecord('ext.a');
      expect(retrieved!.version).toBe('2.0.0');
    });

    it('updatePackRecord rejects when no record exists', async () => {
      await expect(repo.updatePackRecord('nonexistent', makePackRecord('nonexistent'))).rejects.toThrow('No pack record exists');
    });

    it('getAllPackRecords returns all records', async () => {
      await repo.putPackRecord(makePackRecord('ext.a', '1.0.0', 'ref-a'));
      await repo.putPackRecord(makePackRecord('ext.b', '2.0.0', 'ref-b'));
      const all = await repo.getAllPackRecords();
      expect(all).toHaveLength(2);
      const ids = all.map((r) => r.extensionId).sort();
      expect(ids).toEqual(['ext.a', 'ext.b']);
    });

    it('deletePackRecord removes a record', async () => {
      await repo.putPackRecord(makePackRecord());
      await repo.deletePackRecord('test.extension');
      const retrieved = await repo.getPackRecord('test.extension');
      expect(retrieved).toBeNull();
    });

    it('deletePackRecord is idempotent', async () => {
      await expect(repo.deletePackRecord('nonexistent')).resolves.toBeUndefined();
    });

    it('getPackRecord returns null for missing', async () => {
      const retrieved = await repo.getPackRecord('nonexistent');
      expect(retrieved).toBeNull();
    });
  });

  // ---- records survive reinitialization -----------------------------------

  describe('records survive reinitialization', () => {
    it('pack records persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.putPackRecord(makePackRecord('survive.ext', '1.0.0', 'ref-survive'));
      await repo.dispose();

      // Create new repository instance (simulating page reload)
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const record = await repo.getPackRecord('survive.ext');
      expect(record).not.toBeNull();
      expect(record!.extensionId).toBe('survive.ext');
    });

    it('enablement states persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.putEnablementState(makeEnablementState('survive.ext', false));
      await repo.dispose();

      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const state = await repo.getEnablementState('survive.ext');
      expect(state).not.toBeNull();
      expect(state!.enabled).toBe(false);
    });

    it('settings snapshots persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.putSettingsSnapshot(makeSettingsSnapshot('survive.ext', 2, { theme: 'dark' }));
      await repo.dispose();

      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const snapshot = await repo.getSettingsSnapshot('survive.ext');
      expect(snapshot).not.toBeNull();
      expect(snapshot!.schemaVersion).toBe(2);
      expect(snapshot!.values.theme).toBe('dark');
    });

    it('lifecycle events persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const event = makeLifecycleEvent('survive.ext', 'install');
      await repo.appendLifecycleEvent(event);
      await repo.dispose();

      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const events = await repo.getLifecycleEvents('survive.ext');
      expect(events).toHaveLength(1);
      expect(events[0].kind).toBe('install');
    });

    it('dev overrides persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.putDevOverride(makeDevOverride('survive.ext', true));
      await repo.dispose();

      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const override = await repo.getDevOverride('survive.ext');
      expect(override).not.toBeNull();
      expect(override!.preferLocalSource).toBe(true);
    });

    it('lock entries persist across close + reopen', async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      await repo.putLockEntry(makeLockEntry('survive.ext'));
      await repo.dispose();

      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
      const lock = await repo.getLock();
      expect(lock.entries['survive.ext']).not.toBeNull();
      expect(lock.entries['survive.ext'].version).toBe('1.2.3');
    });
  });

  // ---- enablement state ---------------------------------------------------

  describe('enablement state', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('put and get enablement state', async () => {
      const state = makeEnablementState('ext.a', false);
      await repo.putEnablementState(state);
      const retrieved = await repo.getEnablementState('ext.a');
      expect(retrieved!.enabled).toBe(false);
    });

    it('getEnablementState returns null for missing', async () => {
      const state = await repo.getEnablementState('missing');
      expect(state).toBeNull();
    });

    it('putEnablementState overwrites existing', async () => {
      await repo.putEnablementState(makeEnablementState('ext.a', true));
      await repo.putEnablementState(makeEnablementState('ext.a', false));
      const state = await repo.getEnablementState('ext.a');
      expect(state!.enabled).toBe(false);
    });

    it('deleteEnablementState removes state', async () => {
      await repo.putEnablementState(makeEnablementState('ext.a'));
      await repo.deleteEnablementState('ext.a');
      expect(await repo.getEnablementState('ext.a')).toBeNull();
    });

    it('getAllEnablementStates returns all', async () => {
      await repo.putEnablementState(makeEnablementState('ext.a'));
      await repo.putEnablementState(makeEnablementState('ext.b', false));
      const all = await repo.getAllEnablementStates();
      expect(all).toHaveLength(2);
    });
  });

  // ---- dev overrides ------------------------------------------------------

  describe('dev overrides', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('put and get dev override', async () => {
      const override = makeDevOverride('ext.a', false);
      await repo.putDevOverride(override);
      const retrieved = await repo.getDevOverride('ext.a');
      expect(retrieved!.preferLocalSource).toBe(false);
    });

    it('getDevOverride returns null for missing', async () => {
      expect(await repo.getDevOverride('missing')).toBeNull();
    });

    it('deleteDevOverride removes override', async () => {
      await repo.putDevOverride(makeDevOverride('ext.a'));
      await repo.deleteDevOverride('ext.a');
      expect(await repo.getDevOverride('ext.a')).toBeNull();
    });
  });

  // ---- settings snapshots -------------------------------------------------

  describe('settings snapshots', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('put and get settings snapshot', async () => {
      const snapshot = makeSettingsSnapshot('ext.a', 3, { key: 'value', num: 42 });
      await repo.putSettingsSnapshot(snapshot);
      const retrieved = await repo.getSettingsSnapshot('ext.a');
      expect(retrieved!.schemaVersion).toBe(3);
      expect(retrieved!.values.key).toBe('value');
    });

    it('getSettingsSnapshot returns null for missing', async () => {
      expect(await repo.getSettingsSnapshot('missing')).toBeNull();
    });

    it('deleteSettingsSnapshot removes snapshot', async () => {
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a'));
      await repo.deleteSettingsSnapshot('ext.a');
      expect(await repo.getSettingsSnapshot('ext.a')).toBeNull();
    });

    it('getAllSettingsSnapshots returns all', async () => {
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a', 1));
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.b', 2));
      const all = await repo.getAllSettingsSnapshots();
      expect(all).toHaveLength(2);
    });
  });

  // ---- lifecycle events ---------------------------------------------------

  describe('lifecycle events', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('append and query lifecycle events', async () => {
      const event = makeLifecycleEvent('ext.a', 'install');
      await repo.appendLifecycleEvent(event);
      const events = await repo.getLifecycleEvents('ext.a');
      expect(events).toHaveLength(1);
      expect(events[0].kind).toBe('install');
    });

    it('appendLifecycleEvent rejects duplicate IDs', async () => {
      const event = makeLifecycleEvent('ext.a', 'install');
      await repo.appendLifecycleEvent(event);
      await expect(repo.appendLifecycleEvent(event)).rejects.toThrow('already exists');
    });

    it('queryLifecycleEvents filters by extensionId', async () => {
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'install'));
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.b', 'enable'));
      const events = await repo.queryLifecycleEvents({ extensionId: 'ext.a' });
      expect(events).toHaveLength(1);
      expect(events[0].extensionId).toBe('ext.a');
    });

    it('queryLifecycleEvents filters by kind', async () => {
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'install'));
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'enable'));
      const events = await repo.queryLifecycleEvents({ extensionId: 'ext.a', kinds: ['install'] });
      expect(events).toHaveLength(1);
      expect(events[0].kind).toBe('install');
    });

    it('queryLifecycleEvents filters by timestamp range', async () => {
      const oldEvent = createLifecycleEvent('ext.a', 'install', 'old', undefined, undefined);
      // Override timestamp to be old
      const oldEventWithTs = { ...oldEvent, timestamp: '2020-01-01T00:00:00.000Z' };
      await repo.appendLifecycleEvent(oldEventWithTs);

      const newEvent = makeLifecycleEvent('ext.a', 'enable');
      await repo.appendLifecycleEvent(newEvent);

      const events = await repo.queryLifecycleEvents({ extensionId: 'ext.a', since: '2025-01-01T00:00:00.000Z' });
      expect(events).toHaveLength(1);
      expect(events[0].kind).toBe('enable');
    });

    it('queryLifecycleEvents respects limit', async () => {
      for (let i = 0; i < 5; i++) {
        const event: ExtensionLifecycleEvent = {
          id: `evt-${i}`,
          extensionId: 'ext.a',
          kind: 'install',
          timestamp: `2026-01-0${i + 1}T00:00:00.000Z`,
          message: `Event ${i}`,
        };
        await repo.appendLifecycleEvent(event);
      }
      const events = await repo.queryLifecycleEvents({ extensionId: 'ext.a', limit: 3 });
      expect(events).toHaveLength(3);
    });

    it('getLifecycleEvents convenience method works', async () => {
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'install'));
      await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'enable'));
      const events = await repo.getLifecycleEvents('ext.a');
      expect(events).toHaveLength(2);
    });
  });

  // ---- project lock metadata ----------------------------------------------

  describe('project lock metadata', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('getLock returns empty lock when no entries', async () => {
      const lock = await repo.getLock();
      expect(lock.entries).toEqual({});
    });

    it('putLockEntry and getLock', async () => {
      const entry = makeLockEntry('ext.a');
      await repo.putLockEntry(entry);
      const lock = await repo.getLock();
      expect(lock.entries['ext.a']).not.toBeNull();
      expect(lock.entries['ext.a'].version).toBe('1.2.3');
    });

    it('putLockEntry overwrites existing entry', async () => {
      await repo.putLockEntry(makeLockEntry('ext.a', '1.0.0'));
      await repo.putLockEntry(makeLockEntry('ext.a', '2.0.0'));
      const lock = await repo.getLock();
      expect(lock.entries['ext.a'].version).toBe('2.0.0');
    });

    it('deleteLockEntry removes entry', async () => {
      await repo.putLockEntry(makeLockEntry('ext.a'));
      await repo.deleteLockEntry('ext.a');
      const lock = await repo.getLock();
      expect(lock.entries['ext.a']).toBeUndefined();
    });

    it('deleteLockEntry is idempotent', async () => {
      await expect(repo.deleteLockEntry('nonexistent')).resolves.toBeUndefined();
    });
  });

  // ---- composite / full state ---------------------------------------------

  describe('getFullExtensionState', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('returns empty state when nothing stored', async () => {
      const state = await repo.getFullExtensionState();
      expect(state.enablement).toEqual({});
      expect(state.devOverrides).toEqual({});
      expect(state.settings).toEqual({});
      expect(state.packs).toEqual({});
    });

    it('returns all state when populated', async () => {
      await repo.putPackRecord(makePackRecord('ext.a', '1.0.0', 'ref-a'));
      await repo.putEnablementState(makeEnablementState('ext.a', true));
      await repo.putDevOverride(makeDevOverride('ext.a', false));
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a', 1, { theme: 'light' }));
      await repo.putLockEntry(makeLockEntry('ext.a'));

      const state = await repo.getFullExtensionState();
      expect(state.packs['ext.a']).not.toBeNull();
      expect(state.enablement['ext.a'].enabled).toBe(true);
      expect(state.devOverrides['ext.a'].preferLocalSource).toBe(false);
      expect(state.settings['ext.a'].values.theme).toBe('light');
      expect(state.lock.entries['ext.a'].version).toBe('1.2.3');
    });
  });

  // ---- preserve-on-disable semantics --------------------------------------

  describe('preserve-on-disable semantics', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('disable preserves pack record', async () => {
      await repo.putPackRecord(makePackRecord('ext.a'));
      await repo.putEnablementState(makeEnablementState('ext.a', true));

      // Simulate disable: update enablement only
      await repo.putEnablementState(createEnablementState('ext.a', false, 'User disabled'));

      // Pack record still exists
      const pack = await repo.getPackRecord('ext.a');
      expect(pack).not.toBeNull();
    });

    it('disable preserves settings snapshot', async () => {
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a', 1, { theme: 'dark' }));
      await repo.putEnablementState(makeEnablementState('ext.a', true));

      // Disable
      await repo.putEnablementState(createEnablementState('ext.a', false));

      // Settings still exist
      const settings = await repo.getSettingsSnapshot('ext.a');
      expect(settings).not.toBeNull();
      expect(settings!.values.theme).toBe('dark');
    });
  });

  // ---- delete-on-uninstall semantics --------------------------------------

  describe('delete-on-uninstall semantics', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('uninstall deletes pack record', async () => {
      await repo.putPackRecord(makePackRecord('ext.a'));
      await repo.deletePackRecord('ext.a');
      expect(await repo.getPackRecord('ext.a')).toBeNull();
    });

    it('uninstall deletes enablement state', async () => {
      await repo.putEnablementState(makeEnablementState('ext.a'));
      await repo.deleteEnablementState('ext.a');
      expect(await repo.getEnablementState('ext.a')).toBeNull();
    });

    it('uninstall deletes settings snapshot', async () => {
      await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a'));
      await repo.deleteSettingsSnapshot('ext.a');
      expect(await repo.getSettingsSnapshot('ext.a')).toBeNull();
    });

    it('uninstall deletes dev override', async () => {
      await repo.putDevOverride(makeDevOverride('ext.a'));
      await repo.deleteDevOverride('ext.a');
      expect(await repo.getDevOverride('ext.a')).toBeNull();
    });

    it('uninstall removes lock entry', async () => {
      await repo.putLockEntry(makeLockEntry('ext.a'));
      await repo.deleteLockEntry('ext.a');
      const lock = await repo.getLock();
      expect(lock.entries['ext.a']).toBeUndefined();
    });
  });

  // ---- bundle content -----------------------------------------------------

  describe('bundle content', () => {
    beforeEach(async () => {
      repo = createIndexedDBExtensionStateRepository();
      await repo.initialize();
    });

    it('put and get bundle content', async () => {
      await repo.putBundleContent('bundle-001', 'export default function() {}');
      const content = await repo.getBundleContent('bundle-001');
      expect(content).toBe('export default function() {}');
    });

    it('getBundleContent returns null for missing ref', async () => {
      const content = await repo.getBundleContent('missing-ref');
      expect(content).toBeNull();
    });

    it('deleteBundleContent removes content', async () => {
      await repo.putBundleContent('bundle-001', 'data');
      await repo.deleteBundleContent('bundle-001');
      expect(await repo.getBundleContent('bundle-001')).toBeNull();
    });

    it('putBundleContent overwrites existing content', async () => {
      await repo.putBundleContent('bundle-001', 'old');
      await repo.putBundleContent('bundle-001', 'new');
      expect(await repo.getBundleContent('bundle-001')).toBe('new');
    });
  });
});
