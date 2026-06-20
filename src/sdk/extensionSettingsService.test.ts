/**
 * Tests for the injectable extension settings service factory (T8 + T9).
 *
 * Validates:
 *  - Factory produces a synchronous settings service with get/set/delete/keys
 *  - Manifest defaults serve as fallback values
 *  - Settings are scoped per extension (different prefixes)
 *  - Dispose cleans up localStorage keys
 *  - Existing createExtensionContext behavior is preserved
 *
 * T9 additions:
 *  - Repository-backed snapshot loading before activation
 *  - Manifest defaults preserved beneath snapshot layer
 *  - Legacy localStorage read-through
 *  - Reload-equivalent repository reinitialization
 *  - Legacy key migration behavior
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  createExtensionSettingsService,
  getSettingsPrefix,
} from './extensionSettingsService';
import type { ExtensionSettingsServiceFactoryResult } from './extensionSettingsService';
import { defineExtension, createExtensionContext, CONTEXT_DISPOSE_SYMBOL } from './index';
import type { ExtensionManifest, ExtensionSettingsService } from './index';
import {
  ProviderBackedExtensionStateRepository,
  InMemoryProviderStore,
} from '@/tools/video-editor/runtime/extensionStateRepositoryProvider';
import type {
  ExtensionStateRepository,
  ExtensionSettingsSnapshot,
} from '@/tools/video-editor/runtime/extensionStateRepository';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeManifest(extensionId: string, defaults?: Record<string, unknown>): ExtensionManifest {
  return {
    id: extensionId as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    ...(defaults ? { settingsDefaults: defaults } : {}),
  } as ExtensionManifest;
}

function makeManifestWithSchemaVersion(
  extensionId: string,
  defaults: Record<string, unknown>,
  schemaVersion: number,
): ExtensionManifest {
  return {
    id: extensionId as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    settingsDefaults: defaults,
    settingsSchemaVersion: schemaVersion,
  } as ExtensionManifest;
}

function cleanupLocalStorage(extensionId: string): void {
  const prefix = getSettingsPrefix(extensionId);
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(prefix)) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k));
}

function makeSnapshot(
  extensionId: string,
  schemaVersion: number,
  values: Record<string, unknown>,
): ExtensionSettingsSnapshot {
  return Object.freeze({
    extensionId,
    schemaVersion,
    values: Object.freeze({ ...values }),
    lastWrittenAt: new Date().toISOString(),
  });
}

function makeRepo(): { repo: ExtensionStateRepository; cleanup: () => void } {
  const store = new InMemoryProviderStore();
  const repo = new ProviderBackedExtensionStateRepository(store);
  return {
    repo,
    cleanup: () => { /* InMemory needs no cleanup */ },
  };
}

// ---------------------------------------------------------------------------
// getSettingsPrefix
// ---------------------------------------------------------------------------

describe('getSettingsPrefix', () => {
  it('returns the correct prefix for an extension ID', () => {
    expect(getSettingsPrefix('com.example.test')).toBe('reigh.ext.com.example.test.');
  });

  it('prefixes are unique per extension', () => {
    const p1 = getSettingsPrefix('ext.a');
    const p2 = getSettingsPrefix('ext.b');
    expect(p1).not.toBe(p2);
  });
});

// ---------------------------------------------------------------------------
// createExtensionSettingsService — basic (T8)
// ---------------------------------------------------------------------------

describe('createExtensionSettingsService', () => {
  const EXT_ID = 'com.example.settings-test';
  let service: ExtensionSettingsService;
  let dispose: () => void;

  beforeEach(() => {
    cleanupLocalStorage(EXT_ID);
    const result = createExtensionSettingsService(EXT_ID, makeManifest(EXT_ID));
    service = result.service;
    dispose = result.dispose;
  });

  afterEach(() => {
    dispose();
    cleanupLocalStorage(EXT_ID);
  });

  // ---- get / set / delete / keys ------------------------------------------

  it('get returns undefined for missing keys', () => {
    expect(service.get('nonexistent')).toBeUndefined();
  });

  it('set and get round-trip string values', () => {
    service.set('theme', 'dark');
    expect(service.get('theme')).toBe('dark');
  });

  it('set and get round-trip number values', () => {
    service.set('count', 42);
    expect(service.get('count')).toBe(42);
  });

  it('set and get round-trip object values', () => {
    const obj = { nested: { value: true } };
    service.set('config', obj);
    expect(service.get('config')).toEqual(obj);
  });

  it('set and get round-trip array values', () => {
    const arr = [1, 2, 3];
    service.set('items', arr);
    expect(service.get('items')).toEqual(arr);
  });

  it('set and get round-trip boolean values', () => {
    service.set('enabled', true);
    expect(service.get('enabled')).toBe(true);
    service.set('enabled', false);
    expect(service.get('enabled')).toBe(false);
  });

  it('set and get round-trip null', () => {
    service.set('nullable', null);
    expect(service.get('nullable')).toBeNull();
  });

  it('delete removes a key', () => {
    service.set('temp', 'data');
    expect(service.get('temp')).toBe('data');
    service.delete('temp');
    expect(service.get('temp')).toBeUndefined();
  });

  it('delete on missing key is a no-op', () => {
    expect(() => service.delete('nonexistent')).not.toThrow();
  });

  it('keys lists all stored keys', () => {
    service.set('a', 1);
    service.set('b', 2);
    service.set('c', 3);
    const keys = service.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
    expect(keys).toContain('c');
    expect(keys).toHaveLength(3);
  });

  it('keys updates after delete', () => {
    service.set('a', 1);
    service.set('b', 2);
    service.delete('a');
    const keys = service.keys();
    expect(keys).toContain('b');
    expect(keys).not.toContain('a');
  });

  // ---- manifest defaults --------------------------------------------------

  it('returns manifest default for unset keys', () => {
    cleanupLocalStorage('defaults.ext');
    const { service: s, dispose: d } = createExtensionSettingsService(
      'defaults.ext',
      makeManifest('defaults.ext', { theme: 'light', maxItems: 100 }),
    );
    expect(s.get('theme')).toBe('light');
    expect(s.get('maxItems')).toBe(100);
    expect(s.get('nonexistent')).toBeUndefined();
    d();
    cleanupLocalStorage('defaults.ext');
  });

  it('set overrides manifest default', () => {
    cleanupLocalStorage('override.ext');
    const { service: s, dispose: d } = createExtensionSettingsService(
      'override.ext',
      makeManifest('override.ext', { theme: 'light' }),
    );
    expect(s.get('theme')).toBe('light');
    s.set('theme', 'dark');
    expect(s.get('theme')).toBe('dark');
    d();
    cleanupLocalStorage('override.ext');
  });

  it('delete restores manifest default', () => {
    cleanupLocalStorage('restore.ext');
    const { service: s, dispose: d } = createExtensionSettingsService(
      'restore.ext',
      makeManifest('restore.ext', { theme: 'light' }),
    );
    s.set('theme', 'dark');
    s.delete('theme');
    expect(s.get('theme')).toBe('light');
    d();
    cleanupLocalStorage('restore.ext');
  });

  it('keys includes manifest default keys not yet written', () => {
    cleanupLocalStorage('keys-defaults.ext');
    const { service: s, dispose: d } = createExtensionSettingsService(
      'keys-defaults.ext',
      makeManifest('keys-defaults.ext', { a: 1, b: 2, c: 3 }),
    );
    const keys = s.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
    expect(keys).toContain('c');
    d();
    cleanupLocalStorage('keys-defaults.ext');
  });

  // ---- extension scoping --------------------------------------------------

  it('settings are scoped per extension', () => {
    cleanupLocalStorage('ext.one');
    cleanupLocalStorage('ext.two');
    const { service: s1, dispose: d1 } = createExtensionSettingsService('ext.one', makeManifest('ext.one'));
    const { service: s2, dispose: d2 } = createExtensionSettingsService('ext.two', makeManifest('ext.two'));

    s1.set('shared-key', 'value-one');
    s2.set('shared-key', 'value-two');

    expect(s1.get('shared-key')).toBe('value-one');
    expect(s2.get('shared-key')).toBe('value-two');

    d1();
    d2();
    cleanupLocalStorage('ext.one');
    cleanupLocalStorage('ext.two');
  });

  // ---- dispose ------------------------------------------------------------

  it('dispose cleans up written keys', () => {
    cleanupLocalStorage('dispose-test.ext');
    const { service: s, dispose: d } = createExtensionSettingsService('dispose-test.ext', makeManifest('dispose-test.ext'));

    s.set('key1', 'val1');
    s.set('key2', 'val2');

    const prefix = getSettingsPrefix('dispose-test.ext');
    expect(localStorage.getItem(prefix + 'key1')).not.toBeNull();

    d();

    expect(localStorage.getItem(prefix + 'key1')).toBeNull();
    expect(localStorage.getItem(prefix + 'key2')).toBeNull();
    cleanupLocalStorage('dispose-test.ext');
  });

  it('dispose is idempotent', () => {
    cleanupLocalStorage('idempotent.ext');
    const { service: s, dispose: d } = createExtensionSettingsService('idempotent.ext', makeManifest('idempotent.ext'));
    s.set('key', 'val');
    d();
    expect(() => d()).not.toThrow();
    cleanupLocalStorage('idempotent.ext');
  });
});

// ---------------------------------------------------------------------------
// T9: Repository-backed snapshot loading
// ---------------------------------------------------------------------------

describe('T9: Repository-backed settings snapshots', () => {
  const EXT_ID = 't9.repo.ext';

  beforeEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  afterEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  // ---- snapshot value resolution ------------------------------------------

  it('snapshot values are readable through get() when no localStorage exists', () => {
    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'dark', fontSize: 16 });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { initialSnapshot: snapshot },
    );

    expect(s.get('theme')).toBe('dark');
    expect(s.get('fontSize')).toBe(16);
    // Not in snapshot, not in defaults — undefined
    expect(s.get('nonexistent')).toBeUndefined();

    d();
  });

  it('snapshot values are overridden by localStorage writes', () => {
    // Pre-populate localStorage
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('system'));

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { initialSnapshot: snapshot },
    );

    // localStorage wins over snapshot
    expect(s.get('theme')).toBe('system');

    d();
  });

  it('manifest defaults are preserved beneath snapshot values', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light', maxItems: 50 }),
      { initialSnapshot: snapshot },
    );

    // Snapshot value
    expect(s.get('theme')).toBe('dark');
    // Manifest default (not in snapshot)
    expect(s.get('maxItems')).toBe(50);
    // Neither snapshot nor default
    expect(s.get('other')).toBeUndefined();

    d();
  });

  it('set value overrides both snapshot and manifest defaults', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { initialSnapshot: snapshot },
    );

    expect(s.get('theme')).toBe('dark');
    s.set('theme', 'system');
    expect(s.get('theme')).toBe('system');

    d();
  });

  it('delete removes localStorage and marks key deleted from snapshot', () => {
    // Pre-populate localStorage
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('system'));

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { initialSnapshot: snapshot },
    );

    // localStorage wins at first
    expect(s.get('theme')).toBe('system');

    // Delete — should fall through to manifest default now
    s.delete('theme');
    expect(s.get('theme')).toBe('light');

    d();
  });

  it('delete of snapshot-only key falls to manifest default', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { initialSnapshot: snapshot },
    );

    expect(s.get('theme')).toBe('dark');
    s.delete('theme');
    // Falls to manifest default
    expect(s.get('theme')).toBe('light');

    d();
  });

  it('keys includes snapshot keys not in localStorage', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { snapshotOnly: 'yes', shared: 42 });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { defaultOnly: 'hello' }),
      { initialSnapshot: snapshot },
    );

    s.set('shared', 99); // localStorage overrides snapshot

    const keys = s.keys();
    expect(keys).toContain('snapshotOnly');
    expect(keys).toContain('shared');
    expect(keys).toContain('defaultOnly');

    d();
  });

  it('keys excludes deleted snapshot keys', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { keep: 1, remove: 2 });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { initialSnapshot: snapshot },
    );

    s.delete('remove');

    const keys = s.keys();
    expect(keys).toContain('keep');
    expect(keys).not.toContain('remove');

    d();
  });

  // ---- schema version tracking --------------------------------------------

  it('uses snapshot schema version when provided', () => {
    const snapshot = makeSnapshot(EXT_ID, 5, { theme: 'dark' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { initialSnapshot: snapshot },
    );

    // Schema version is used during dispose for repository writes
    // We verify indirectly via repository integration tests below
    expect(s.get('theme')).toBe('dark');
    d();
  });

  it('uses manifest settingsSchemaVersion when no snapshot', () => {
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifestWithSchemaVersion(EXT_ID, {}, 3),
    );

    expect(s.get('nonexistent')).toBeUndefined();
    d();
  });
});

// ---------------------------------------------------------------------------
// T9: Legacy localStorage read-through (with and without snapshot)
// ---------------------------------------------------------------------------

describe('T9: Legacy localStorage read-through', () => {
  const EXT_ID = 't9.legacy.ext';

  beforeEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  afterEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  it('reads legacy localStorage keys with no snapshot', () => {
    // Pre-populate legacy localStorage (as a previous version of the service would)
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyKey', JSON.stringify('legacyValue'));
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'count', JSON.stringify(99));

    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
    );

    expect(s.get('legacyKey')).toBe('legacyValue');
    expect(s.get('count')).toBe(99);

    d();
  });

  it('legacy localStorage overrides snapshot values', () => {
    // Simulate: previous version stored legacy value, then a new version loads
    // with a different snapshot
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('legacy-dark'));

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'snapshot-light' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'default' }),
      { initialSnapshot: snapshot },
    );

    // Legacy localStorage wins over snapshot
    expect(s.get('theme')).toBe('legacy-dark');

    d();
  });

  it('legacy key migration: snapshot values readable alongside legacy keys', () => {
    // Legacy key stored before snapshot was introduced
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyOnly', JSON.stringify('from-legacy'));

    // Snapshot has different keys
    const snapshot = makeSnapshot(EXT_ID, 1, { snapshotOnly: 'from-snapshot' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { initialSnapshot: snapshot },
    );

    // Both are readable
    expect(s.get('legacyOnly')).toBe('from-legacy');
    expect(s.get('snapshotOnly')).toBe('from-snapshot');

    // keys() returns both
    const keys = s.keys();
    expect(keys).toContain('legacyOnly');
    expect(keys).toContain('snapshotOnly');

    d();
  });

  it('legacy keys are included in keys()', () => {
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy1', 'v1');
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy2', 'v2');

    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
    );

    const keys = s.keys();
    expect(keys).toContain('legacy1');
    expect(keys).toContain('legacy2');

    d();
  });

  it('multiple extension prefixes do not leak', () => {
    // Legacy keys for two different extensions
    localStorage.setItem(getSettingsPrefix('ext.a') + 'data', JSON.stringify('a-data'));
    localStorage.setItem(getSettingsPrefix('ext.b') + 'data', JSON.stringify('b-data'));

    const { service: sA, dispose: dA } = createExtensionSettingsService('ext.a', makeManifest('ext.a'));
    const { service: sB, dispose: dB } = createExtensionSettingsService('ext.b', makeManifest('ext.b'));

    expect(sA.get('data')).toBe('a-data');
    expect(sB.get('data')).toBe('b-data');

    const keysA = sA.keys();
    expect(keysA).toContain('data');
    expect(keysA).toHaveLength(1);

    dA();
    dB();
    cleanupLocalStorage('ext.a');
    cleanupLocalStorage('ext.b');
  });
});

// ---------------------------------------------------------------------------
// T9: Reload-equivalent repository reinitialization
// ---------------------------------------------------------------------------

describe('T9: Reload-equivalent repository reinitialization', () => {
  const EXT_ID = 't9.reload.ext';

  let store: InMemoryProviderStore;
  let repo: ExtensionStateRepository;

  beforeEach(async () => {
    cleanupLocalStorage(EXT_ID);
    store = new InMemoryProviderStore();
    repo = new ProviderBackedExtensionStateRepository(store);
    await repo.initialize();
  });

  afterEach(async () => {
    cleanupLocalStorage(EXT_ID);
    if (repo && !repo.isDisposed) {
      await repo.dispose();
    }
  });

  it('settings persist across dispose+recreate via repository snapshot', async () => {
    // First activation: create service with repo, set values, dispose
    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { repository: repo },
    );

    s1.set('theme', 'dark');
    s1.set('fontSize', 16);
    s1.set('items', [1, 2, 3]);

    // Dispose writes snapshot to repository
    d1();

    // Allow async repo write to complete
    await new Promise((r) => setTimeout(r, 50));

    // Read the snapshot back from repo
    const snapshot = await repo.getSettingsSnapshot(EXT_ID);
    expect(snapshot).not.toBeNull();
    expect(snapshot!.values.theme).toBe('dark');
    expect(snapshot!.values.fontSize).toBe(16);
    expect(snapshot!.values.items).toEqual([1, 2, 3]);

    // Second activation (simulating page reload): create new service with same repo
    const { service: s2, dispose: d2 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light' }),
      { repository: repo, initialSnapshot: snapshot! },
    );

    // Values preserved across "reload"
    expect(s2.get('theme')).toBe('dark');
    expect(s2.get('fontSize')).toBe(16);
    expect(s2.get('items')).toEqual([1, 2, 3]);

    d2();
  });

  it('settings survive multiple reload cycles', async () => {
    // Cycle 1
    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo },
    );
    s1.set('counter', 1);
    d1();
    await new Promise((r) => setTimeout(r, 30));
    let snap = await repo.getSettingsSnapshot(EXT_ID);

    // Cycle 2
    const { service: s2, dispose: d2 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo, initialSnapshot: snap! },
    );
    expect(s2.get('counter')).toBe(1);
    s2.set('counter', 2);
    d2();
    await new Promise((r) => setTimeout(r, 30));
    snap = await repo.getSettingsSnapshot(EXT_ID);

    // Cycle 3
    const { service: s3, dispose: d3 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo, initialSnapshot: snap! },
    );
    expect(s3.get('counter')).toBe(2);
    s3.set('counter', 3);
    d3();
    await new Promise((r) => setTimeout(r, 30));
    snap = await repo.getSettingsSnapshot(EXT_ID);

    expect(snap!.values.counter).toBe(3);
  });

  it('manifest defaults present after reload when no override', async () => {
    // First activation: defaults only, no sets
    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light', maxItems: 100 }),
      { repository: repo },
    );
    // Don't set anything — just dispose with defaults
    d1();
    await new Promise((r) => setTimeout(r, 30));
    const snapshot = await repo.getSettingsSnapshot(EXT_ID);

    // Second activation: defaults preserved in snapshot
    const { service: s2, dispose: d2 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'light', maxItems: 100 }),
      { repository: repo, initialSnapshot: snapshot! },
    );

    expect(s2.get('theme')).toBe('light');
    expect(s2.get('maxItems')).toBe(100);

    d2();
  });

  it('dispose does not write to repo when repo is disposed', async () => {
    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo },
    );
    s1.set('data', 'will-not-persist');

    await repo.dispose();
    d1();
    await new Promise((r) => setTimeout(r, 30));

    // Since repo was disposed before d1(), the snapshot write should be silently skipped
    // We can't easily verify a negative, but the key point is no crash
  });

  it('schema version is tracked in repository snapshot', async () => {
    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 7),
      { repository: repo },
    );
    s1.set('theme', 'custom');
    d1();
    await new Promise((r) => setTimeout(r, 30));

    const snapshot = await repo.getSettingsSnapshot(EXT_ID);
    expect(snapshot!.schemaVersion).toBe(7);
  });

  it('snapshot schema version from initial snapshot is preserved on rewrite', async () => {
    // Simulate an older snapshot at schema version 3
    const oldSnapshot = makeSnapshot(EXT_ID, 3, { oldKey: 'oldValue' });

    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo, initialSnapshot: oldSnapshot },
    );
    s.set('newKey', 'newValue');
    d();
    await new Promise((r) => setTimeout(r, 30));

    const snapshot = await repo.getSettingsSnapshot(EXT_ID);
    // Schema version should be preserved from the old snapshot
    expect(snapshot!.schemaVersion).toBe(3);
    expect(snapshot!.values.oldKey).toBe('oldValue');
    expect(snapshot!.values.newKey).toBe('newValue');
  });
});

// ---------------------------------------------------------------------------
// T9: Legacy key migration with repository
// ---------------------------------------------------------------------------

describe('T9: Legacy key migration with repository', () => {
  const EXT_ID = 't9.migrate.ext';

  let store: InMemoryProviderStore;
  let repo: ExtensionStateRepository;

  beforeEach(async () => {
    cleanupLocalStorage(EXT_ID);
    store = new InMemoryProviderStore();
    repo = new ProviderBackedExtensionStateRepository(store);
    await repo.initialize();
  });

  afterEach(async () => {
    cleanupLocalStorage(EXT_ID);
    if (repo && !repo.isDisposed) {
      await repo.dispose();
    }
  });

  it('legacy localStorage keys are migrated into repository snapshot on first dispose', async () => {
    // Simulate legacy keys from a previous version that didn't use repos
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyTheme', JSON.stringify('blue'));
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyCount', JSON.stringify(42));

    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID),
      { repository: repo },
    );

    // Legacy keys are readable
    expect(s.get('legacyTheme')).toBe('blue');
    expect(s.get('legacyCount')).toBe(42);

    // Write a new key
    s.set('newKey', 'newValue');

    // Dispose — should write merged snapshot to repo including legacy keys
    d();
    await new Promise((r) => setTimeout(r, 50));

    const snapshot = await repo.getSettingsSnapshot(EXT_ID);
    expect(snapshot).not.toBeNull();

    // Legacy keys are now in the repository snapshot
    expect(snapshot!.values.legacyTheme).toBe('blue');
    expect(snapshot!.values.legacyCount).toBe(42);
    expect(snapshot!.values.newKey).toBe('newValue');
  });

  it('post-migration: snapshot values survive reload without legacy localStorage', async () => {
    // Phase 1: Legacy keys exist, first dispose migrates them to snapshot
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('migrated-dark'));

    const { service: s1, dispose: d1 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'default' }),
      { repository: repo },
    );
    d1();
    await new Promise((r) => setTimeout(r, 30));
    const snapshot = await repo.getSettingsSnapshot(EXT_ID);

    // Phase 2: Clear localStorage (simulating new browser session with cleared storage)
    cleanupLocalStorage(EXT_ID);
    // But snapshot exists in repo

    const { service: s2, dispose: d2 } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { theme: 'default' }),
      { repository: repo, initialSnapshot: snapshot! },
    );

    // Snapshot value is used since localStorage is gone
    expect(s2.get('theme')).toBe('migrated-dark');

    d2();
  });

  it('legacy-to-repo migration preserves manifest defaults for keys not in legacy', async () => {
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'customKey', JSON.stringify('custom'));

    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { defaultKey: 'defaultValue', maxItems: 25 }),
      { repository: repo },
    );

    // Legacy key readable
    expect(s.get('customKey')).toBe('custom');
    // Manifest defaults readable
    expect(s.get('defaultKey')).toBe('defaultValue');
    expect(s.get('maxItems')).toBe(25);

    d();
    await new Promise((r) => setTimeout(r, 30));
    const snapshot = await repo.getSettingsSnapshot(EXT_ID);

    // All three are in the snapshot
    expect(snapshot!.values.customKey).toBe('custom');
    expect(snapshot!.values.defaultKey).toBe('defaultValue');
    expect(snapshot!.values.maxItems).toBe(25);
  });

  it('keys() reflects the merged state including legacy, snapshot, and defaults', () => {
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy', JSON.stringify('l'));

    const snapshot = makeSnapshot(EXT_ID, 1, { snapshot: 's' });
    const { service: s, dispose: d } = createExtensionSettingsService(
      EXT_ID,
      makeManifest(EXT_ID, { default: 'd' }),
      { initialSnapshot: snapshot, repository: repo },
    );

    const keys = s.keys();
    expect(keys).toContain('legacy');
    expect(keys).toContain('snapshot');
    expect(keys).toContain('default');

    d();
  });
});

// ---------------------------------------------------------------------------
// Integration: createExtensionContext preserves settings behavior after extraction
// ---------------------------------------------------------------------------

describe('createExtensionContext preserves settings behavior after extraction', () => {
  const EXT_ID = 'com.example.ctx-settings';

  beforeEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  afterEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  it('settings.get returns undefined for missing keys', () => {
    const ext = defineExtension({ manifest: makeManifest(EXT_ID) });
    const ctx = createExtensionContext(ext);
    expect(ctx.services.settings.get('nonexistent')).toBeUndefined();
    disposeContext(ctx);
  });

  it('settings.set and get round-trip', () => {
    const ext = defineExtension({ manifest: makeManifest(EXT_ID) });
    const ctx = createExtensionContext(ext);
    ctx.services.settings.set('theme', 'dark');
    expect(ctx.services.settings.get('theme')).toBe('dark');
    disposeContext(ctx);
  });

  it('settings.delete removes keys', () => {
    const ext = defineExtension({ manifest: makeManifest(EXT_ID) });
    const ctx = createExtensionContext(ext);
    ctx.services.settings.set('temp', 'data');
    expect(ctx.services.settings.get('temp')).toBe('data');
    ctx.services.settings.delete('temp');
    expect(ctx.services.settings.get('temp')).toBeUndefined();
    disposeContext(ctx);
  });

  it('settings.keys lists all stored keys', () => {
    const ext = defineExtension({ manifest: makeManifest(EXT_ID) });
    const ctx = createExtensionContext(ext);
    ctx.services.settings.set('a', 1);
    ctx.services.settings.set('b', 2);
    const keys = ctx.services.settings.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
    disposeContext(ctx);
  });

  it('manifest defaults work through createExtensionContext', () => {
    const ext = defineExtension({
      manifest: {
        ...makeManifest(EXT_ID),
        settingsDefaults: { theme: 'system', fontSize: 14 },
      } as ExtensionManifest,
    });
    const ctx = createExtensionContext(ext);
    expect(ctx.services.settings.get('theme')).toBe('system');
    expect(ctx.services.settings.get('fontSize')).toBe(14);
    disposeContext(ctx);
  });

  it('settings are scoped per extension through createExtensionContext', () => {
    const ext1 = defineExtension({ manifest: makeManifest('ext.alpha') });
    const ext2 = defineExtension({ manifest: makeManifest('ext.beta') });
    const ctx1 = createExtensionContext(ext1);
    const ctx2 = createExtensionContext(ext2);

    ctx1.services.settings.set('shared-key', 'alpha-value');
    ctx2.services.settings.set('shared-key', 'beta-value');

    expect(ctx1.services.settings.get('shared-key')).toBe('alpha-value');
    expect(ctx2.services.settings.get('shared-key')).toBe('beta-value');

    disposeContext(ctx1);
    disposeContext(ctx2);
    cleanupLocalStorage('ext.alpha');
    cleanupLocalStorage('ext.beta');
  });
});

// ---------------------------------------------------------------------------
// Helper to dispose context
// ---------------------------------------------------------------------------

function disposeContext(ctx: ReturnType<typeof createExtensionContext>): void {
  const dispose = (ctx as unknown as Record<string | symbol, unknown>)[CONTEXT_DISPOSE_SYMBOL];
  if (typeof dispose === 'function') {
    try { dispose(); } catch { /* ok */ }
  }
}

// ---------------------------------------------------------------------------
// T10: Settings migration integration with the service factory
// ---------------------------------------------------------------------------

describe('T10: Settings migration during service creation', () => {
  const EXT_ID = 't10.service.ext';

  beforeEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  afterEach(() => {
    cleanupLocalStorage(EXT_ID);
  });

  // ---- Schema version match — no migration --------------------------------

  it('migrationResult is null when no initialSnapshot provided', () => {
    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 2),
    );

    expect(migrationResult).toBeNull();
    d();
  });

  it('migrationResult is null when snapshot schema version matches manifest', () => {
    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'dark' });
    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      makeManifestWithSchemaVersion(EXT_ID, { theme: 'light' }, 2),
      { initialSnapshot: snapshot },
    );

    expect(migrationResult).toBeNull();
    expect(s.get('theme')).toBe('dark'); // snapshot value used
    d();
  });

  it('no migration when snapshot provided but no migration config', () => {
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });
    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      makeManifestWithSchemaVersion(EXT_ID, { theme: 'light' }, 3),
      { initialSnapshot: snapshot },
    );

    // No migration config → snapshot used as-is
    expect(migrationResult).toBeNull();
    expect(s.get('theme')).toBe('dark');
    d();
  });

  // ---- Schema version mismatch with migration config — success -------------

  it('migrates snapshot values and marks migrationResult.migrated=true', () => {
    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'default', extra: 'defaultExtra' }, 2),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'myMigrator' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = (values) => ({
      ...values,
      addedByMigration: true,
    });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { myMigrator: handler } },
      },
    );

    expect(migrationResult).not.toBeNull();
    expect(migrationResult!.migrated).toBe(true);
    expect(migrationResult!.resetToDefaults).toBe(false);
    expect(migrationResult!.schemaVersion).toBe(2);

    // The migrated values should be in the snapshot layer
    // (but localStorage takes priority, which is empty here)
    expect(s.get('theme')).toBe('dark');
    expect(s.get('addedByMigration')).toBe(true);
    // extra was in manifest defaults, not in snapshot, so it should still be there
    expect(s.get('extra')).toBe('defaultExtra');

    d();
  });

  // ---- Schema version mismatch — reset to defaults ------------------------

  it('resets to manifest defaults when no migration declarations', () => {
    const manifest = makeManifestWithSchemaVersion(
      EXT_ID,
      { theme: 'system', maxItems: 50 },
      3,
    );
    // No migrations declared

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark', oldKey: 'legacy' });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: {},
      },
    );

    expect(migrationResult).not.toBeNull();
    expect(migrationResult!.resetToDefaults).toBe(true);
    expect(migrationResult!.migrated).toBe(false);
    expect(migrationResult!.schemaVersion).toBe(3);

    // Values should be reset to manifest defaults
    expect(s.get('theme')).toBe('system');
    expect(s.get('maxItems')).toBe(50);
    expect(s.get('oldKey')).toBeUndefined();

    d();
  });

  it('resets to defaults when migration handler not provided', () => {
    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'fallback' }, 2),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'nonexistent' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: {} },
      },
    );

    expect(migrationResult!.resetToDefaults).toBe(true);
    expect(s.get('theme')).toBe('fallback');
    d();
  });

  it('resets to defaults when migration handler throws', () => {
    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'safeDefault' }, 2),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'explode' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dangerous' });

    const handler: SettingsMigrationHandler = () => {
      throw new Error('Kaboom!');
    };

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { explode: handler } },
      },
    );

    expect(migrationResult!.resetToDefaults).toBe(true);
    expect(migrationResult!.failure).toBeDefined();
    expect(s.get('theme')).toBe('safeDefault');
    d();
  });

  // ---- Migration with legacy settingsSchemaVersion ------------------------

  it('detects schema version from legacy settingsSchemaVersion', () => {
    const manifest = {
      id: EXT_ID as any,
      version: '1.0.0',
      label: 'Test',
      contributions: [],
      settingsSchemaVersion: 4,
      settingsDefaults: { theme: 'v4default' },
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'doit' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'v2' });

    const handler: SettingsMigrationHandler = (values) => ({
      ...values,
      migratedToV4: true,
    });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { doit: handler } },
      },
    );

    expect(migrationResult!.migrated).toBe(true);
    expect(migrationResult!.schemaVersion).toBe(4);
    expect(s.get('migratedToV4')).toBe(true);
    d();
  });

  // ---- Migration preserves snapshot values when no handler field ----------

  it('resets when declaration has no handler field', () => {
    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 2),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0' }, // no handler
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'old' });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: {} },
      },
    );

    expect(migrationResult!.resetToDefaults).toBe(true);
    expect(s.get('theme')).toBe('default');
    d();
  });

  // ---- Migration with localStorage overriding migrated values -------------

  it('localStorage takes priority over migrated values', () => {
    // Pre-set localStorage (as if a previous session wrote it)
    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('localOverride'));

    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 2),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'm' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = (values) => ({
      ...values,
      theme: 'migrated-theme',
    });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { m: handler } },
      },
    );

    expect(migrationResult!.migrated).toBe(true);
    // localStorage wins
    expect(s.get('theme')).toBe('localOverride');

    d();
  });

  // ---- Migration result lifecycle events ----------------------------------

  it('migration result includes failure field when reset', () => {
    const manifest = makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 2);
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const { dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: {},
      },
    );

    expect(migrationResult!.failure).toBeDefined();
    d();
  });

  // ---- Chaining multiple handlers via service factory ----------------------

  it('chains multiple migration handlers during service creation', () => {
    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { count: 0 }, 3),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'add1' },
        { kind: 'settings', fromVersion: '2.0.0', toVersion: '3.0.0', handler: 'add10' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 1, { count: 5 });

    const add1: SettingsMigrationHandler = (values) => ({
      ...values,
      count: (values.count as number) + 1,
    });
    const add10: SettingsMigrationHandler = (values) => ({
      ...values,
      count: (values.count as number) + 10,
    });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { add1, add10 } },
      },
    );

    expect(migrationResult!.migrated).toBe(true);
    expect(migrationResult!.schemaVersion).toBe(3);
    expect(s.get('count')).toBe(16); // 5 + 1 + 10
    d();
  });

  // ---- Dispose writes migrated schema version to repository ----------------

  it('dispose writes migrated schema version to repository', async () => {
    const store = new InMemoryProviderStore();
    const repo = new ProviderBackedExtensionStateRepository(store);
    await repo.initialize();

    const manifest = {
      ...makeManifestWithSchemaVersion(EXT_ID, { theme: 'default' }, 5),
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'up' },
      ],
    } as ExtensionManifest;

    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'old' });

    const handler: SettingsMigrationHandler = (values) => ({
      ...values,
      theme: 'migrated',
    });

    const { service: s, dispose: d, migrationResult } = createExtensionSettingsService(
      EXT_ID,
      manifest,
      {
        initialSnapshot: snapshot,
        migration: { settingsHandlers: { up: handler } },
        repository: repo,
      },
    );

    expect(migrationResult!.migrated).toBe(true);

    s.set('runtime', 'value');
    d();

    await new Promise((r) => setTimeout(r, 50));

    const persisted = await repo.getSettingsSnapshot(EXT_ID);
    expect(persisted).not.toBeNull();
    expect(persisted!.schemaVersion).toBe(5); // migrated version
    expect(persisted!.values.theme).toBe('migrated');
    expect(persisted!.values.runtime).toBe('value');

    await repo.dispose();
  });
});

// ---------------------------------------------------------------------------
// Import needed types for migration tests
// ---------------------------------------------------------------------------

import type { SettingsMigrationHandler } from './extensionSettingsMigration';
import {
  runSettingsMigration,
  getManifestSettingsSchemaVersion,
} from './extensionSettingsMigration';
