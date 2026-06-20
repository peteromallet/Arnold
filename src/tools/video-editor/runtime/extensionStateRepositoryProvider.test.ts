/**
 * Tests for provider-backed ExtensionStateRepository (T7).
 *
 * Validates:
 *  - All CRUD operations through the ProviderBackedStore interface
 *  - Reserved keys are used for metadata only (no bundle bytes)
 *  - InMemoryProviderStore and LocalStorageProviderStore work correctly
 *  - Preserve-on-disable and delete-on-uninstall semantics
 *  - JSON corruption produces fallback, not crash
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  ProviderBackedExtensionStateRepository,
  InMemoryProviderStore,
  LocalStorageProviderStore,
  createProviderBackedExtensionStateRepository,
} from './extensionStateRepositoryProvider';
import type { ProviderBackedStore } from './extensionStateRepositoryProvider';
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
  description: 'A test extension',
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
// Run tests against both InMemory and LocalStorage stores
// ---------------------------------------------------------------------------

function runTests(storeFactory: () => { store: ProviderBackedStore; cleanup: () => void | Promise<void> }, label: string) {
  describe(`ProviderBackedExtensionStateRepository with ${label}`, () => {
    let repo: ProviderBackedExtensionStateRepository;
    let cleanupFn: () => void | Promise<void>;

    beforeEach(async () => {
      const { store, cleanup } = storeFactory();
      repo = createProviderBackedExtensionStateRepository(store);
      cleanupFn = cleanup;
      await repo.initialize();
    });

    afterEach(async () => {
      if (repo && !repo.isDisposed) {
        try { await repo.dispose(); } catch { /* ok */ }
      }
      await cleanupFn();
    });

    // ---- lifecycle --------------------------------------------------------

    describe('lifecycle', () => {
      it('initialize succeeds', async () => {
        expect(repo.isDisposed).toBe(false);
      });

      it('dispose marks as disposed', async () => {
        await repo.dispose();
        expect(repo.isDisposed).toBe(true);
      });

      it('operations reject after dispose', async () => {
        await repo.dispose();
        await expect(repo.getPackRecord('any')).rejects.toThrow('disposed');
      });
    });

    // ---- pack records -----------------------------------------------------

    describe('pack records', () => {
      it('put and get pack record', async () => {
        const record = makePackRecord();
        await repo.putPackRecord(record);
        const retrieved = await repo.getPackRecord('test.extension');
        expect(retrieved).not.toBeNull();
        expect(retrieved!.version).toBe('1.2.3');
      });

      it('put rejects duplicate', async () => {
        await repo.putPackRecord(makePackRecord());
        await expect(repo.putPackRecord(makePackRecord())).rejects.toThrow('already exists');
      });

      it('update updates existing', async () => {
        await repo.putPackRecord(makePackRecord('ext.a', '1.0.0', 'ref-1'));
        await repo.updatePackRecord('ext.a', makePackRecord('ext.a', '2.0.0', 'ref-2'));
        const r = await repo.getPackRecord('ext.a');
        expect(r!.version).toBe('2.0.0');
      });

      it('update rejects when missing', async () => {
        await expect(repo.updatePackRecord('nonexistent', makePackRecord('nonexistent'))).rejects.toThrow('No pack record exists');
      });

      it('delete pack record', async () => {
        await repo.putPackRecord(makePackRecord());
        await repo.deletePackRecord('test.extension');
        expect(await repo.getPackRecord('test.extension')).toBeNull();
      });

      it('getAllPackRecords returns all', async () => {
        await repo.putPackRecord(makePackRecord('ext.a'));
        await repo.putPackRecord(makePackRecord('ext.b'));
        expect(await repo.getAllPackRecords()).toHaveLength(2);
      });

      it('getPackRecord returns null for missing', async () => {
        expect(await repo.getPackRecord('missing')).toBeNull();
      });
    });

    // ---- enablement state -------------------------------------------------

    describe('enablement state', () => {
      it('put and get', async () => {
        await repo.putEnablementState(makeEnablementState('ext.a', false));
        const state = await repo.getEnablementState('ext.a');
        expect(state!.enabled).toBe(false);
      });

      it('returns null for missing', async () => {
        expect(await repo.getEnablementState('missing')).toBeNull();
      });

      it('overwrites existing', async () => {
        await repo.putEnablementState(makeEnablementState('ext.a', true));
        await repo.putEnablementState(makeEnablementState('ext.a', false));
        expect((await repo.getEnablementState('ext.a'))!.enabled).toBe(false);
      });

      it('delete removes state', async () => {
        await repo.putEnablementState(makeEnablementState('ext.a'));
        await repo.deleteEnablementState('ext.a');
        expect(await repo.getEnablementState('ext.a')).toBeNull();
      });

      it('getAll returns all', async () => {
        await repo.putEnablementState(makeEnablementState('ext.a'));
        await repo.putEnablementState(makeEnablementState('ext.b'));
        expect(await repo.getAllEnablementStates()).toHaveLength(2);
      });
    });

    // ---- dev overrides ----------------------------------------------------

    describe('dev overrides', () => {
      it('put and get', async () => {
        await repo.putDevOverride(makeDevOverride('ext.a', false));
        const o = await repo.getDevOverride('ext.a');
        expect(o!.preferLocalSource).toBe(false);
      });

      it('returns null for missing', async () => {
        expect(await repo.getDevOverride('missing')).toBeNull();
      });

      it('delete removes', async () => {
        await repo.putDevOverride(makeDevOverride('ext.a'));
        await repo.deleteDevOverride('ext.a');
        expect(await repo.getDevOverride('ext.a')).toBeNull();
      });
    });

    // ---- settings snapshots -----------------------------------------------

    describe('settings snapshots', () => {
      it('put and get', async () => {
        await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a', 3, { k: 'v' }));
        const s = await repo.getSettingsSnapshot('ext.a');
        expect(s!.schemaVersion).toBe(3);
        expect(s!.values.k).toBe('v');
      });

      it('returns null for missing', async () => {
        expect(await repo.getSettingsSnapshot('missing')).toBeNull();
      });

      it('delete removes', async () => {
        await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a'));
        await repo.deleteSettingsSnapshot('ext.a');
        expect(await repo.getSettingsSnapshot('ext.a')).toBeNull();
      });
    });

    // ---- lifecycle events -------------------------------------------------

    describe('lifecycle events', () => {
      it('append and query', async () => {
        await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'install'));
        const events = await repo.getLifecycleEvents('ext.a');
        expect(events).toHaveLength(1);
        expect(events[0].kind).toBe('install');
      });

      it('rejects duplicate IDs', async () => {
        const event = makeLifecycleEvent('ext.a', 'install');
        await repo.appendLifecycleEvent(event);
        await expect(repo.appendLifecycleEvent(event)).rejects.toThrow('already exists');
      });

      it('filters by kind', async () => {
        await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'install'));
        await repo.appendLifecycleEvent(makeLifecycleEvent('ext.a', 'enable'));
        const events = await repo.queryLifecycleEvents({ extensionId: 'ext.a', kinds: ['install'] });
        expect(events).toHaveLength(1);
      });

      it('respects limit', async () => {
        for (let i = 0; i < 5; i++) {
          await repo.appendLifecycleEvent({
            id: `evt-${i}`,
            extensionId: 'ext.a',
            kind: 'install',
            timestamp: `2026-01-0${i + 1}T00:00:00.000Z`,
            message: `Event ${i}`,
          });
        }
        expect(await repo.queryLifecycleEvents({ limit: 3 })).toHaveLength(3);
      });
    });

    // ---- lock metadata ----------------------------------------------------

    describe('lock metadata', () => {
      it('empty lock', async () => {
        const lock = await repo.getLock();
        expect(lock.entries).toEqual({});
      });

      it('put and get lock entry', async () => {
        await repo.putLockEntry(makeLockEntry('ext.a'));
        const lock = await repo.getLock();
        expect(lock.entries['ext.a'].version).toBe('1.2.3');
      });

      it('delete lock entry', async () => {
        await repo.putLockEntry(makeLockEntry('ext.a'));
        await repo.deleteLockEntry('ext.a');
        expect((await repo.getLock()).entries['ext.a']).toBeUndefined();
      });
    });

    // ---- full state -------------------------------------------------------

    describe('getFullExtensionState', () => {
      it('returns empty when nothing stored', async () => {
        const state = await repo.getFullExtensionState();
        expect(state.enablement).toEqual({});
        expect(state.packs).toEqual({});
      });

      it('returns populated state', async () => {
        await repo.putPackRecord(makePackRecord('ext.a'));
        await repo.putEnablementState(makeEnablementState('ext.a', true));
        await repo.putLockEntry(makeLockEntry('ext.a'));
        const state = await repo.getFullExtensionState();
        expect(state.packs['ext.a']).not.toBeNull();
        expect(state.enablement['ext.a'].enabled).toBe(true);
      });
    });

    // ---- semantics --------------------------------------------------------

    describe('semantics', () => {
      it('preserve-on-disable: pack record survives disable', async () => {
        await repo.putPackRecord(makePackRecord('ext.a'));
        await repo.putEnablementState(createEnablementState('ext.a', false));
        expect(await repo.getPackRecord('ext.a')).not.toBeNull();
      });

      it('delete-on-uninstall: all metadata removed', async () => {
        await repo.putPackRecord(makePackRecord('ext.a'));
        await repo.putEnablementState(makeEnablementState('ext.a'));
        await repo.putSettingsSnapshot(makeSettingsSnapshot('ext.a'));
        await repo.putDevOverride(makeDevOverride('ext.a'));
        await repo.putLockEntry(makeLockEntry('ext.a'));

        // Full uninstall
        await repo.deletePackRecord('ext.a');
        await repo.deleteEnablementState('ext.a');
        await repo.deleteSettingsSnapshot('ext.a');
        await repo.deleteDevOverride('ext.a');
        await repo.deleteLockEntry('ext.a');

        expect(await repo.getPackRecord('ext.a')).toBeNull();
        expect(await repo.getEnablementState('ext.a')).toBeNull();
        expect(await repo.getSettingsSnapshot('ext.a')).toBeNull();
        expect(await repo.getDevOverride('ext.a')).toBeNull();
        expect((await repo.getLock()).entries['ext.a']).toBeUndefined();
      });
    });
  });
}

// ---------------------------------------------------------------------------
// Register tests for each store type
// ---------------------------------------------------------------------------

runTests(
  () => ({ store: new InMemoryProviderStore(), cleanup: () => {} }),
  'InMemoryProviderStore',
);

runTests(
  () => {
    // Clear localStorage before test
    const keysToClean: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('reigh.ext.state.')) {
        keysToClean.push(key);
      }
    }
    keysToClean.forEach((k) => localStorage.removeItem(k));

    return {
      store: new LocalStorageProviderStore(),
      cleanup: () => {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith('reigh.ext.state.')) {
            localStorage.removeItem(key);
          }
        }
      },
    };
  },
  'LocalStorageProviderStore',
);

// ---------------------------------------------------------------------------
// Reserved keys — verify no bundle bytes stored in provider-backed state
// ---------------------------------------------------------------------------

describe('Provider-backed store reserved key usage', () => {
  it('uses reserved tool-settings keys for metadata only', async () => {
    const store = new InMemoryProviderStore();
    const repo = createProviderBackedExtensionStateRepository(store);
    await repo.initialize();

    await repo.putPackRecord(makePackRecord('ext.a'));
    await repo.putEnablementState(makeEnablementState('ext.a'));

    // Verify keys are the reserved ones
    const rawKeys = Array.from(store.raw.keys()).sort();
    expect(rawKeys).toContain('reigh.ext.state.packs');
    expect(rawKeys).toContain('reigh.ext.state.enablement');

    // Verify no bundle bytes are stored in provider-backed keys
    for (const key of rawKeys) {
      const value = store.raw.get(key) ?? '';
      // Bundle content should not appear in provider state
      expect(value).not.toContain('export default');
      expect(value).not.toContain('function(');
    }

    await repo.dispose();
  });
});

// ---------------------------------------------------------------------------
// JSON corruption fallback
// ---------------------------------------------------------------------------

describe('Provider-backed store corruption handling', () => {
  it('recovers from corrupted JSON with empty fallback', async () => {
    const store = new InMemoryProviderStore();
    // Pre-populate with corrupted data
    await store.set('reigh.ext.state.packs', 'not-valid-json{{{');
    await store.set('reigh.ext.state.enablement', '{corrupt}');

    const repo = createProviderBackedExtensionStateRepository(store);
    await repo.initialize();

    // Should not crash — returns empty/null
    const packs = await repo.getAllPackRecords();
    expect(packs).toEqual([]);

    const enablement = await repo.getEnablementState('any');
    expect(enablement).toBeNull();

    // Should still be able to write after corruption recovery
    await repo.putPackRecord(makePackRecord('ext.a'));
    const retrieved = await repo.getPackRecord('ext.a');
    expect(retrieved).not.toBeNull();
    expect(retrieved!.extensionId).toBe('ext.a');

    await repo.dispose();
  });
});
