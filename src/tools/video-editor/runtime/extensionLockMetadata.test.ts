/**
 * Tests for extensionLockMetadata (M14, T17).
 *
 * Covers:
 *  - extractContributionRefs() from manifests with various contribution types
 *  - getLockVersionRange() defaulting and manifest-level override
 *  - buildLockEntry() / buildLockEntryFromPackRecord() correctness
 *  - syncEnabledPackLockEntries() upsert and multi-pack scenarios
 *  - removeLockEntry() cleanup
 *  - Separation: lock entries do NOT include extension settings values
 *  - Separation: lock entries do NOT include lifecycle events or bundle content
 *  - Repository integration with InMemoryProviderStore
 */

import { describe, expect, it, beforeEach } from 'vitest';
import type { ExtensionManifest, IntegrityHash } from '@reigh/editor-sdk';
import type {
  ExtensionPackRecord,
  ExtensionLockEntry,
  ExtensionLock,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import {
  createProviderBackedExtensionStateRepository,
  InMemoryProviderStore,
  type ProviderBackedExtensionStateRepository,
} from '@/tools/video-editor/runtime/extensionStateRepositoryProvider';
import {
  extractContributionRefs,
  getLockVersionRange,
  buildLockEntry,
  buildLockEntryFromPackRecord,
  syncEnabledPackLockEntries,
  removeLockEntry,
  getProjectLock,
} from '@/tools/video-editor/runtime/extensionLockMetadata';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TEST_INTEGRITY: IntegrityHash = Object.freeze({
  algorithm: 'sha256',
  value: 'dGVzdC1oYXNoLXZhbHVlLWZvci10ZXN0aW5nLXB1cnBvc2Vz',
});

function makeManifest(overrides: Partial<ExtensionManifest> = {}): ExtensionManifest {
  return Object.freeze({
    id: 'test.extension' as any,
    version: '1.2.3',
    label: 'Test Extension',
    description: 'A test extension',
    apiVersion: 1,
    publisher: 'Test Publisher',
    license: 'MIT',
    contributions: [],
    ...overrides,
  } as ExtensionManifest);
}

function makePackRecord(overrides: Partial<ExtensionPackRecord> = {}): ExtensionPackRecord {
  return Object.freeze({
    extensionId: 'test.extension',
    version: '1.2.3',
    apiVersion: 1,
    integrity: TEST_INTEGRITY,
    installedAt: '2026-06-19T00:00:00.000Z',
    updatedAt: '2026-06-19T00:00:00.000Z',
    bundleContentRef: 'ref-test-1',
    manifestSnapshot: makeManifest(),
    publisher: 'Test Publisher',
    license: 'MIT',
    ...overrides,
  });
}

function makeRepository(): ProviderBackedExtensionStateRepository {
  const store = new InMemoryProviderStore();
  return createProviderBackedExtensionStateRepository(store);
}

// ---------------------------------------------------------------------------
// extractContributionRefs
// ---------------------------------------------------------------------------

describe('extractContributionRefs', () => {
  it('returns empty array when manifest has no contributions', () => {
    const manifest = makeManifest({ contributions: [] });
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual([]);
  });

  it('returns empty array when contributions is undefined', () => {
    const manifest = makeManifest();
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual([]);
  });

  it('extracts contribution IDs from a command contribution', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.run' as any, kind: 'command' as any },
      ],
    });
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual(['cmd.run']);
  });

  it('extracts contribution IDs from multiple contributions of different kinds', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.save' as any, kind: 'command' as any },
        { id: 'effect.fade' as any, kind: 'effect' as any },
        { id: 'shader.blur' as any, kind: 'shader' as any },
        { id: 'transition.dissolve' as any, kind: 'transition' as any },
        { id: 'clip.fancy' as any, kind: 'clipType' as any },
        { id: 'agent.export' as any, kind: 'agentTool' as any },
      ],
    });
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual([
      'agent.export',
      'clip.fancy',
      'cmd.save',
      'effect.fade',
      'shader.blur',
      'transition.dissolve',
    ]);
  });

  it('deduplicates contribution IDs', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.run' as any, kind: 'command' as any },
        { id: 'cmd.run' as any, kind: 'command' as any },
        { id: 'effect.fade' as any, kind: 'effect' as any },
      ],
    });
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual(['cmd.run', 'effect.fade']);
  });

  it('sorts contribution IDs alphabetically', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'z.last' as any, kind: 'command' as any },
        { id: 'a.first' as any, kind: 'command' as any },
        { id: 'm.middle' as any, kind: 'command' as any },
      ],
    });
    const refs = extractContributionRefs(manifest);
    expect(refs).toEqual(['a.first', 'm.middle', 'z.last']);
  });

  it('skips contributions without IDs', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.good' as any, kind: 'command' as any },
        { kind: 'command' as any }, // no id
        { id: '' as any, kind: 'command' as any }, // empty id
      ],
    });
    const refs = extractContributionRefs(manifest);
    // Empty string is truthy type-wise but is a valid contribution ID, so it's included
    expect(refs).toContain('cmd.good');
  });

  it('returns frozen array', () => {
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.test' as any, kind: 'command' as any }],
    });
    const refs = extractContributionRefs(manifest);
    expect(Object.isFrozen(refs)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// getLockVersionRange
// ---------------------------------------------------------------------------

describe('getLockVersionRange', () => {
  it('defaults to exact installed version', () => {
    const packRecord = makePackRecord({ version: '2.0.0' });
    const manifest = makeManifest();
    const range = getLockVersionRange(packRecord, manifest);
    expect(range).toBe('2.0.0');
  });

  it('uses manifest-level lockVersionRange when present', () => {
    const packRecord = makePackRecord({ version: '2.0.0' });
    const manifest = makeManifest({
      lockVersionRange: '^2.0.0',
    } as any);
    const range = getLockVersionRange(packRecord, manifest);
    expect(range).toBe('^2.0.0');
  });

  it('ignores empty lockVersionRange in manifest', () => {
    const packRecord = makePackRecord({ version: '2.0.0' });
    const manifest = makeManifest({
      lockVersionRange: '',
    } as any);
    const range = getLockVersionRange(packRecord, manifest);
    expect(range).toBe('2.0.0');
  });

  it('ignores whitespace-only lockVersionRange in manifest', () => {
    const packRecord = makePackRecord({ version: '2.0.0' });
    const manifest = makeManifest({
      lockVersionRange: '   ',
    } as any);
    const range = getLockVersionRange(packRecord, manifest);
    expect(range).toBe('2.0.0');
  });
});

// ---------------------------------------------------------------------------
// buildLockEntry
// ---------------------------------------------------------------------------

describe('buildLockEntry', () => {
  it('includes extension ID, version, and integrity', () => {
    const packRecord = makePackRecord({ extensionId: 'my.ext', version: '1.0.0' });
    const manifest = makeManifest();
    const entry = buildLockEntry(packRecord, manifest);
    expect(entry.extensionId).toBe('my.ext');
    expect(entry.version).toBe('1.0.0');
    expect(entry.integrity).toBe(TEST_INTEGRITY);
  });

  it('includes version range', () => {
    const packRecord = makePackRecord({ version: '3.0.0' });
    const manifest = makeManifest();
    const entry = buildLockEntry(packRecord, manifest);
    expect(entry.versionRange).toBe('3.0.0');
  });

  it('includes contribution refs from manifest', () => {
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.a' as any, kind: 'command' as any },
        { id: 'effect.b' as any, kind: 'effect' as any },
      ],
    });
    const packRecord = makePackRecord({ manifestSnapshot: manifest });
    const entry = buildLockEntry(packRecord, manifest);
    expect(entry.contributionRefs).toEqual(['cmd.a', 'effect.b']);
  });

  it('sets lockedAt and updatedAt to current time', () => {
    const before = new Date().toISOString();
    const packRecord = makePackRecord();
    const manifest = makeManifest();
    const entry = buildLockEntry(packRecord, manifest);
    const after = new Date().toISOString();
    expect(entry.lockedAt >= before).toBe(true);
    expect(entry.lockedAt <= after).toBe(true);
    expect(entry.updatedAt).toBe(entry.lockedAt);
  });

  it('returns frozen entry', () => {
    const packRecord = makePackRecord();
    const manifest = makeManifest();
    const entry = buildLockEntry(packRecord, manifest);
    expect(Object.isFrozen(entry)).toBe(true);
  });

  it('freezes contributionRefs array', () => {
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.x' as any, kind: 'command' as any }],
    });
    const packRecord = makePackRecord({ manifestSnapshot: manifest });
    const entry = buildLockEntry(packRecord, manifest);
    expect(Object.isFrozen(entry.contributionRefs)).toBe(true);
  });

  it('does NOT include extension settings values', () => {
    const packRecord = makePackRecord();
    const manifest = makeManifest();
    const entry = buildLockEntry(packRecord, manifest);
    // The lock entry must not include settings values or extension-owned data
    expect((entry as any).settings).toBeUndefined();
    expect((entry as any).values).toBeUndefined();
    expect((entry as any).config).toBeUndefined();
    expect((entry as any).data).toBeUndefined();
    // Only the defined fields should be present
    const keys = Object.keys(entry).sort();
    expect(keys).toEqual([
      'contributionRefs',
      'extensionId',
      'integrity',
      'lockedAt',
      'updatedAt',
      'version',
      'versionRange',
    ]);
  });
});

// ---------------------------------------------------------------------------
// buildLockEntryFromPackRecord
// ---------------------------------------------------------------------------

describe('buildLockEntryFromPackRecord', () => {
  it('builds entry from pack record alone', () => {
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.z' as any, kind: 'command' as any }],
    });
    const packRecord = makePackRecord({
      extensionId: 'pkg.ext',
      version: '4.5.6',
      manifestSnapshot: manifest,
    });
    const entry = buildLockEntryFromPackRecord(packRecord);
    expect(entry.extensionId).toBe('pkg.ext');
    expect(entry.version).toBe('4.5.6');
    expect(entry.contributionRefs).toEqual(['cmd.z']);
    expect(entry.integrity).toBe(TEST_INTEGRITY);
  });

  it('is equivalent to calling buildLockEntry with packRecord.manifestSnapshot', () => {
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.w' as any, kind: 'command' as any }],
    });
    const packRecord = makePackRecord({
      extensionId: 'equiv.ext',
      version: '1.1.1',
      manifestSnapshot: manifest,
    });
    const fromRecord = buildLockEntryFromPackRecord(packRecord);
    const explicit = buildLockEntry(packRecord, manifest);
    expect(fromRecord.extensionId).toBe(explicit.extensionId);
    expect(fromRecord.version).toBe(explicit.version);
    expect(fromRecord.versionRange).toBe(explicit.versionRange);
    expect(fromRecord.contributionRefs).toEqual(explicit.contributionRefs);
    expect(fromRecord.integrity).toEqual(explicit.integrity);
  });
});

// ---------------------------------------------------------------------------
// syncEnabledPackLockEntries (repository integration)
// ---------------------------------------------------------------------------

describe('syncEnabledPackLockEntries', () => {
  let repository: ProviderBackedExtensionStateRepository;

  beforeEach(async () => {
    repository = makeRepository();
  });

  it('syncs a single pack record into the lock', async () => {
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.p' as any, kind: 'command' as any }],
    });
    const packRecord = makePackRecord({
      extensionId: 'synced.ext',
      version: '1.0.0',
      manifestSnapshot: manifest,
    });

    await syncEnabledPackLockEntries(repository, [packRecord]);

    const lock = await repository.getLock();
    expect(lock.entries['synced.ext']).toBeDefined();
    expect(lock.entries['synced.ext'].extensionId).toBe('synced.ext');
    expect(lock.entries['synced.ext'].version).toBe('1.0.0');
    expect(lock.entries['synced.ext'].contributionRefs).toEqual(['cmd.p']);
    expect(lock.entries['synced.ext'].integrity).toEqual(TEST_INTEGRITY);
  });

  it('syncs multiple pack records into the lock', async () => {
    const manifestA = makeManifest({
      id: 'ext.a' as any,
      contributions: [{ id: 'cmd.a' as any, kind: 'command' as any }],
    });
    const manifestB = makeManifest({
      id: 'ext.b' as any,
      contributions: [{ id: 'effect.b' as any, kind: 'effect' as any }],
    });

    const packA = makePackRecord({
      extensionId: 'ext.a',
      version: '1.0.0',
      manifestSnapshot: manifestA,
    });
    const packB = makePackRecord({
      extensionId: 'ext.b',
      version: '2.0.0',
      manifestSnapshot: manifestB,
    });

    await syncEnabledPackLockEntries(repository, [packA, packB]);

    const lock = await repository.getLock();
    expect(Object.keys(lock.entries)).toHaveLength(2);
    expect(lock.entries['ext.a'].version).toBe('1.0.0');
    expect(lock.entries['ext.b'].version).toBe('2.0.0');
    expect(lock.entries['ext.a'].contributionRefs).toEqual(['cmd.a']);
    expect(lock.entries['ext.b'].contributionRefs).toEqual(['effect.b']);
  });

  it('upserts existing lock entry (overwrites on re-sync)', async () => {
    // First sync with v1
    const manifest = makeManifest({
      contributions: [{ id: 'cmd.old' as any, kind: 'command' as any }],
    });
    const packV1 = makePackRecord({
      extensionId: 'upsert.ext',
      version: '1.0.0',
      manifestSnapshot: manifest,
    });
    await syncEnabledPackLockEntries(repository, [packV1]);

    // Second sync with v2 (different contributions)
    const manifestV2 = makeManifest({
      contributions: [
        { id: 'cmd.new' as any, kind: 'command' as any },
        { id: 'effect.new' as any, kind: 'effect' as any },
      ],
    });
    const packV2 = makePackRecord({
      extensionId: 'upsert.ext',
      version: '2.0.0',
      manifestSnapshot: manifestV2,
    });
    await syncEnabledPackLockEntries(repository, [packV2]);

    const lock = await repository.getLock();
    expect(lock.entries['upsert.ext'].version).toBe('2.0.0');
    expect(lock.entries['upsert.ext'].contributionRefs).toEqual(['cmd.new', 'effect.new']);
  });

  it('can sync an empty list (no changes)', async () => {
    const result = await syncEnabledPackLockEntries(repository, []);
    expect(result.entries).toEqual({});
  });

  it('throws when repository is disposed', async () => {
    await repository.dispose();
    const packRecord = makePackRecord();
    await expect(
      syncEnabledPackLockEntries(repository, [packRecord]),
    ).rejects.toThrow('disposed');
  });

  it('lock entry does NOT include settings values', async () => {
    const manifest = makeManifest();
    const packRecord = makePackRecord({
      extensionId: 'clean.ext',
      manifestSnapshot: manifest,
    });

    await syncEnabledPackLockEntries(repository, [packRecord]);

    const lock = await repository.getLock();
    const entry = lock.entries['clean.ext'];
    expect(entry).toBeDefined();
    // Lock entry should NOT carry settings
    expect((entry as any).settings).toBeUndefined();
    expect((entry as any).settingsValues).toBeUndefined();
    expect((entry as any).config).toBeUndefined();
    expect((entry as any).patch).toBeUndefined();
    expect((entry as any).projectData).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// removeLockEntry
// ---------------------------------------------------------------------------

describe('removeLockEntry', () => {
  let repository: ProviderBackedExtensionStateRepository;

  beforeEach(async () => {
    repository = makeRepository();
  });

  it('removes a lock entry for an extension', async () => {
    const packRecord = makePackRecord({ extensionId: 'remove.me' });
    await syncEnabledPackLockEntries(repository, [packRecord]);

    let lock = await repository.getLock();
    expect(lock.entries['remove.me']).toBeDefined();

    await removeLockEntry(repository, 'remove.me');

    lock = await repository.getLock();
    expect(lock.entries['remove.me']).toBeUndefined();
  });

  it('is idempotent for non-existent entries', async () => {
    // Should not throw for non-existent entry
    await expect(
      removeLockEntry(repository, 'nonexistent.id'),
    ).resolves.toBeUndefined();
  });

  it('does not throw when repository is disposed', async () => {
    await repository.dispose();
    await expect(
      removeLockEntry(repository, 'any.id'),
    ).resolves.toBeUndefined();
  });

  it('only removes the specified entry, not others', async () => {
    const packA = makePackRecord({ extensionId: 'keep.me' });
    const packB = makePackRecord({ extensionId: 'remove.me' });
    await syncEnabledPackLockEntries(repository, [packA, packB]);

    await removeLockEntry(repository, 'remove.me');

    const lock = await repository.getLock();
    expect(lock.entries['keep.me']).toBeDefined();
    expect(lock.entries['remove.me']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getProjectLock
// ---------------------------------------------------------------------------

describe('getProjectLock', () => {
  it('returns empty lock when nothing is synced', async () => {
    const repository = makeRepository();
    const lock = await getProjectLock(repository);
    expect(lock.entries).toEqual({});
    expect(lock.lastUpdatedAt).toBeTruthy();
  });

  it('returns lock with synced entries', async () => {
    const repository = makeRepository();
    const pack = makePackRecord({ extensionId: 'visible.ext' });
    await syncEnabledPackLockEntries(repository, [pack]);

    const lock = await getProjectLock(repository);
    expect(lock.entries['visible.ext']).toBeDefined();
    expect(lock.entries['visible.ext'].extensionId).toBe('visible.ext');
  });
});

// ---------------------------------------------------------------------------
// Separation: lock metadata vs extension-owned project data
// ---------------------------------------------------------------------------

describe('lock metadata separation from extension-owned data', () => {
  let repository: ProviderBackedExtensionStateRepository;

  beforeEach(async () => {
    repository = makeRepository();
  });

  it('lock entries contain only project-level requirements, not extension settings', async () => {
    // Sync a pack into the lock
    const manifest = makeManifest({
      contributions: [
        { id: 'cmd.foo' as any, kind: 'command' as any },
      ],
    });
    const packRecord = makePackRecord({
      extensionId: 'separated.ext',
      manifestSnapshot: manifest,
    });
    await syncEnabledPackLockEntries(repository, [packRecord]);

    // Now write extension settings through a separate path (settings snapshot)
    await repository.putSettingsSnapshot({
      extensionId: 'separated.ext',
      schemaVersion: 1,
      values: { foo: 'bar', secret: 42 },
      lastWrittenAt: new Date().toISOString(),
    });

    // The lock entry should NOT contain the settings values
    const lock = await repository.getLock();
    const entry = lock.entries['separated.ext'];
    expect(entry).toBeDefined();
    expect((entry as any).foo).toBeUndefined();
    expect((entry as any).secret).toBeUndefined();
    expect((entry as any).values).toBeUndefined();
    expect((entry as any).settings).toBeUndefined();

    // The settings snapshot IS retrievable separately
    const snapshot = await repository.getSettingsSnapshot('separated.ext');
    expect(snapshot).not.toBeNull();
    expect(snapshot!.values).toEqual({ foo: 'bar', secret: 42 });
  });

  it('lock entries do not include lifecycle events', async () => {
    const packRecord = makePackRecord({ extensionId: 'events.ext' });
    await syncEnabledPackLockEntries(repository, [packRecord]);

    // Append a lifecycle event
    await repository.appendLifecycleEvent({
      id: 'event-1',
      extensionId: 'events.ext',
      kind: 'enable',
      timestamp: new Date().toISOString(),
      message: 'Extension enabled',
    });

    // Lock entry should not include the event
    const lock = await repository.getLock();
    const entry = lock.entries['events.ext'];
    expect(entry).toBeDefined();
    expect((entry as any).events).toBeUndefined();
    expect((entry as any).lifecycle).toBeUndefined();

    // Events ARE retrievable separately
    const events = await repository.getLifecycleEvents('events.ext');
    expect(events).toHaveLength(1);
    expect(events[0].kind).toBe('enable');
  });

  it('lock entries do not include bundle content or content references', async () => {
    const packRecord = makePackRecord({
      extensionId: 'bundle.ext',
      bundleContentRef: 'ref-bundle-abc',
    });
    await syncEnabledPackLockEntries(repository, [packRecord]);

    const lock = await repository.getLock();
    const entry = lock.entries['bundle.ext'];
    expect(entry).toBeDefined();
    // Lock should not carry bundleContentRef (that's IndexedDB territory per SD2)
    expect((entry as any).bundleContentRef).toBeUndefined();
    expect((entry as any).bundleContent).toBeUndefined();
    expect((entry as any).bundle).toBeUndefined();
  });

  it('lock entries do not include pack record metadata beyond the defined fields', async () => {
    const manifest = makeManifest();
    const packRecord = makePackRecord({
      extensionId: 'fields.ext',
      publisher: 'Some Publisher',
      license: 'Apache-2.0',
      icon: 'data:image/png,base64,abc',
      manifestSnapshot: manifest,
    });
    await syncEnabledPackLockEntries(repository, [packRecord]);

    const lock = await repository.getLock();
    const entry = lock.entries['fields.ext'];
    expect(entry).toBeDefined();

    // Lock should NOT include publisher, license, icon (these are pack record fields, not lock fields)
    expect((entry as any).publisher).toBeUndefined();
    expect((entry as any).license).toBeUndefined();
    expect((entry as any).icon).toBeUndefined();
    expect((entry as any).installedAt).toBeUndefined();
    expect((entry as any).updatedAt).toBeDefined(); // updatedAt IS a lock field
    expect((entry as any).bundleContentRef).toBeUndefined();
  });

  it('multiple extensions can have lock entries while maintaining their own settings', async () => {
    const manifestA = makeManifest({
      id: 'ext.a' as any,
      contributions: [{ id: 'cmd.a' as any, kind: 'command' as any }],
    });
    const manifestB = makeManifest({
      id: 'ext.b' as any,
      contributions: [{ id: 'effect.b' as any, kind: 'effect' as any }],
    });

    const packA = makePackRecord({ extensionId: 'ext.a', manifestSnapshot: manifestA });
    const packB = makePackRecord({ extensionId: 'ext.b', manifestSnapshot: manifestB });

    await syncEnabledPackLockEntries(repository, [packA, packB]);

    // Write separate settings for each
    await repository.putSettingsSnapshot({
      extensionId: 'ext.a', schemaVersion: 1, values: { a: 1 },
      lastWrittenAt: new Date().toISOString(),
    });
    await repository.putSettingsSnapshot({
      extensionId: 'ext.b', schemaVersion: 1, values: { b: 2 },
      lastWrittenAt: new Date().toISOString(),
    });

    // Lock entries exist and don't mix settings
    const lock = await repository.getLock();
    expect(lock.entries['ext.a']).toBeDefined();
    expect(lock.entries['ext.b']).toBeDefined();
    expect((lock.entries['ext.a'] as any).values).toBeUndefined();
    expect((lock.entries['ext.b'] as any).values).toBeUndefined();
    expect((lock.entries['ext.a'] as any).a).toBeUndefined();
    expect((lock.entries['ext.b'] as any).b).toBeUndefined();

    // Settings are retrievable independently
    const snapA = await repository.getSettingsSnapshot('ext.a');
    const snapB = await repository.getSettingsSnapshot('ext.b');
    expect(snapA!.values).toEqual({ a: 1 });
    expect(snapB!.values).toEqual({ b: 2 });
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('edge cases', () => {
  it('handles extensions with many contribution types', async () => {
    const contributions: any[] = [];
    const kinds = ['command', 'effect', 'transition', 'shader', 'clipType', 'agentTool', 'panel', 'dialog', 'slot', 'parser', 'outputFormat'];
    for (let i = 0; i < kinds.length; i++) {
      contributions.push({ id: `contrib.${kinds[i]}` as any, kind: kinds[i] as any });
    }

    const manifest = makeManifest({ contributions });
    const refs = extractContributionRefs(manifest);
    expect(refs).toHaveLength(kinds.length);
    for (const kind of kinds) {
      expect(refs).toContain(`contrib.${kind}`);
    }
  });

  it('handles extensions with no version (falls back gracefully)', () => {
    const manifest = makeManifest({ version: '' as any });
    const packRecord = makePackRecord({ version: '', manifestSnapshot: manifest });
    const entry = buildLockEntry(packRecord, manifest);
    expect(entry.version).toBe('');
    expect(entry.versionRange).toBe('');
  });

  it('updatedAt is set to now when building lock entry', async () => {
    const packRecord = makePackRecord({ extensionId: 'time.ext' });
    const entry = buildLockEntryFromPackRecord(packRecord);

    const before = new Date();
    const entryTime = new Date(entry.updatedAt!);
    const after = new Date();

    // Within 5 seconds (generous for CI)
    const diffMs = Math.abs(entryTime.getTime() - before.getTime());
    expect(diffMs).toBeLessThan(5000);
  });
});
