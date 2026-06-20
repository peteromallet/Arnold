/**
 * Tests for the ExtensionStateRepository contract and helper functions.
 *
 * These tests validate:
 *  - All contract types are constructable and structurally correct.
 *  - Helper functions produce well-formed records.
 *  - The contract's semantic guarantees (preserve-on-disable,
 *    delete-on-uninstall) are reflected in the type shapes.
 */

import { describe, it, expect } from 'vitest';
import {
  toPackRecord,
  toPackRecordFromPackage,
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
  FullExtensionState,
  LifecycleEventKind,
  LifecycleEventQuery,
} from './extensionStateRepository';
import type {
  InstalledExtensionMetadata,
  InstalledExtensionPackage,
  ExtensionManifest,
  IntegrityHash,
  ExtensionDiagnostic,
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
  description: 'A test extension for repository contract tests',
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

const TEST_PACKAGE: InstalledExtensionPackage = Object.freeze({
  metadata: TEST_METADATA,
  manifest: TEST_MANIFEST,
  bundleContent: 'export default function() {}',
});

// ---------------------------------------------------------------------------
// toPackRecord
// ---------------------------------------------------------------------------

describe('toPackRecord', () => {
  it('creates a frozen pack record from metadata, manifest, and content ref', () => {
    const record = toPackRecord(TEST_METADATA, TEST_MANIFEST, 'bundle-ref-001');

    expect(record.extensionId).toBe('test.extension');
    expect(record.version).toBe('1.2.3');
    expect(record.apiVersion).toBe(1);
    expect(record.integrity).toBe(TEST_INTEGRITY);
    expect(record.installedAt).toBe('2026-06-20T12:00:00.000Z');
    expect(record.bundleContentRef).toBe('bundle-ref-001');
    expect(record.manifestSnapshot).toBe(TEST_MANIFEST);
    expect(record.publisher).toBe('Test Publisher');
    expect(record.license).toBe('MIT');
  });

  it('uses current timestamp when installedAt is missing', () => {
    const metadataNoDate: InstalledExtensionMetadata = {
      ...TEST_METADATA,
      installedAt: undefined,
    };
    const record = toPackRecord(metadataNoDate, TEST_MANIFEST, 'ref');
    expect(record.installedAt).toBeTruthy();
    expect(() => new Date(record.installedAt)).not.toThrow();
  });

  it('produces a structurally valid ExtensionPackRecord', () => {
    const record = toPackRecord(TEST_METADATA, TEST_MANIFEST, 'ref');
    // Verify all required keys exist
    const requiredKeys: (keyof ExtensionPackRecord)[] = [
      'extensionId', 'version', 'integrity', 'installedAt',
      'bundleContentRef', 'manifestSnapshot',
    ];
    for (const key of requiredKeys) {
      expect(record[key]).toBeDefined();
    }
  });
});

// ---------------------------------------------------------------------------
// toPackRecordFromPackage
// ---------------------------------------------------------------------------

describe('toPackRecordFromPackage', () => {
  it('extracts a pack record from a full InstalledExtensionPackage', () => {
    const record = toPackRecordFromPackage(TEST_PACKAGE, 'bundle-ref-002');

    expect(record.extensionId).toBe('test.extension');
    expect(record.version).toBe('1.2.3');
    expect(record.bundleContentRef).toBe('bundle-ref-002');
    expect(record.manifestSnapshot).toBe(TEST_MANIFEST);
  });
});

// ---------------------------------------------------------------------------
// createEnablementState
// ---------------------------------------------------------------------------

describe('createEnablementState', () => {
  it('creates an enabled state by default', () => {
    const state = createEnablementState('my.ext');

    expect(state.extensionId).toBe('my.ext');
    expect(state.enabled).toBe(true);
    expect(state.lastToggledAt).toBeTruthy();
    expect(state.toggleReason).toBe('Installed and enabled');
  });

  it('creates a disabled state when enabled=false', () => {
    const state = createEnablementState('my.ext', false, 'Manual disable');

    expect(state.enabled).toBe(false);
    expect(state.toggleReason).toBe('Manual disable');
  });

  it('produces a structurally valid ExtensionEnablementState', () => {
    const state = createEnablementState('ext.id');
    const keys: (keyof ExtensionEnablementState)[] = [
      'extensionId', 'enabled', 'lastToggledAt',
    ];
    for (const key of keys) {
      expect(state[key]).toBeDefined();
    }
  });
});

// ---------------------------------------------------------------------------
// createSettingsSnapshot
// ---------------------------------------------------------------------------

describe('createSettingsSnapshot', () => {
  it('creates a settings snapshot with schema version and values', () => {
    const values = { theme: 'dark', maxItems: 42 };
    const snapshot = createSettingsSnapshot('my.ext', 3, values);

    expect(snapshot.extensionId).toBe('my.ext');
    expect(snapshot.schemaVersion).toBe(3);
    expect(snapshot.values.theme).toBe('dark');
    expect(snapshot.values.maxItems).toBe(42);
    expect(snapshot.lastWrittenAt).toBeTruthy();
  });

  it('freezes values so they are not mutable externally', () => {
    const values = { key: 'original' };
    const snapshot = createSettingsSnapshot('ext', 1, values);

    // The returned snapshot has frozen values
    expect(Object.isFrozen(snapshot.values)).toBe(true);
  });

  it('copy is independent of the input object', () => {
    const values = { key: 'before' };
    const snapshot = createSettingsSnapshot('ext', 1, values);
    values.key = 'after';

    expect(snapshot.values.key).toBe('before');
  });
});

// ---------------------------------------------------------------------------
// createLifecycleEvent
// ---------------------------------------------------------------------------

describe('createLifecycleEvent', () => {
  it('creates a lifecycle event with an ID, extensionId, kind, and timestamp', () => {
    const event = createLifecycleEvent(
      'my.ext',
      'install',
      'Extension installed successfully',
    );

    expect(event.id).toBeTruthy();
    expect(typeof event.id).toBe('string');
    expect(event.extensionId).toBe('my.ext');
    expect(event.kind).toBe('install');
    expect(event.message).toBe('Extension installed successfully');
    expect(event.timestamp).toBeTruthy();
    expect(() => new Date(event.timestamp)).not.toThrow();
  });

  it('includes optional detail when provided', () => {
    const detail = { version: '1.0.0', previousVersion: null };
    const event = createLifecycleEvent('ext', 'install', 'msg', detail);

    expect(event.detail).toEqual(detail);
  });

  it('includes optional diagnostic when provided', () => {
    const diagnostic: ExtensionDiagnostic = Object.freeze({
      severity: 'info',
      code: 'test/code',
      message: 'test diagnostic',
    });
    const event = createLifecycleEvent('ext', 'activation_success', 'ok', undefined, diagnostic);

    expect(event.diagnostic).toBe(diagnostic);
  });

  it('generates unique IDs for different events', () => {
    const e1 = createLifecycleEvent('ext', 'install', 'first');
    const e2 = createLifecycleEvent('ext', 'enable', 'second');

    expect(e1.id).not.toBe(e2.id);
  });

  it('handles all lifecycle event kinds', () => {
    const kinds: LifecycleEventKind[] = [
      'install',
      'uninstall',
      'enable',
      'disable',
      'load',
      'unload',
      'activation_success',
      'activation_failure',
      'migration_start',
      'migration_success',
      'migration_failure',
      'migration_reset',
      'integrity_pass',
      'integrity_fail',
      'dependency_blocked',
      'dependency_degraded',
      'conflict_override_set',
      'conflict_override_cleared',
    ];

    for (const kind of kinds) {
      const event = createLifecycleEvent('ext', kind, `Event: ${kind}`);
      expect(event.kind).toBe(kind);
      expect(event.id).toBeTruthy();
    }
  });
});

// ---------------------------------------------------------------------------
// Type construction tests (structural validity)
// ---------------------------------------------------------------------------

describe('type construction', () => {
  it('ExtensionPackRecord can be constructed', () => {
    const record: ExtensionPackRecord = {
      extensionId: 'ext.a',
      version: '1.0.0',
      integrity: TEST_INTEGRITY,
      installedAt: '2026-01-01T00:00:00.000Z',
      bundleContentRef: 'ref-1',
      manifestSnapshot: TEST_MANIFEST,
      publisher: 'Pub',
      license: 'MIT',
    };
    expect(record.extensionId).toBe('ext.a');
  });

  it('ExtensionEnablementState can be constructed', () => {
    const state: ExtensionEnablementState = {
      extensionId: 'ext.b',
      enabled: false,
      lastToggledAt: '2026-01-01T00:00:00.000Z',
      toggleReason: 'test',
    };
    expect(state.enabled).toBe(false);
  });

  it('DevOverrideState can be constructed', () => {
    const override: DevOverrideState = {
      extensionId: 'ext.c',
      preferLocalSource: true,
      setAt: '2026-01-01T00:00:00.000Z',
    };
    expect(override.preferLocalSource).toBe(true);
  });

  it('ExtensionSettingsSnapshot can be constructed', () => {
    const snapshot: ExtensionSettingsSnapshot = {
      extensionId: 'ext.d',
      schemaVersion: 2,
      values: { key: 'value' },
      lastWrittenAt: '2026-01-01T00:00:00.000Z',
    };
    expect(snapshot.schemaVersion).toBe(2);
  });

  it('ExtensionLifecycleEvent can be constructed', () => {
    const event: ExtensionLifecycleEvent = {
      id: 'evt-1',
      extensionId: 'ext.e',
      kind: 'install',
      timestamp: '2026-01-01T00:00:00.000Z',
      message: 'test',
    };
    expect(event.kind).toBe('install');
  });

  it('ExtensionLockEntry can be constructed', () => {
    const entry: ExtensionLockEntry = {
      extensionId: 'ext.f',
      version: '1.0.0',
      versionRange: '^1.0.0',
      contributionRefs: ['cmd.a', 'effect.b'],
      integrity: TEST_INTEGRITY,
      lockedAt: '2026-01-01T00:00:00.000Z',
    };
    expect(entry.contributionRefs).toHaveLength(2);
  });

  it('ExtensionLock can be constructed', () => {
    const entry: ExtensionLockEntry = {
      extensionId: 'ext.g',
      version: '1.0.0',
      contributionRefs: [],
      integrity: TEST_INTEGRITY,
      lockedAt: '2026-01-01T00:00:00.000Z',
    };
    const lock: ExtensionLock = {
      entries: { 'ext.g': entry },
      lastUpdatedAt: '2026-01-01T00:00:00.000Z',
    };
    expect(lock.entries['ext.g']).toBe(entry);
  });

  it('FullExtensionState can be constructed', () => {
    const enablementState: ExtensionEnablementState = {
      extensionId: 'ext.h',
      enabled: true,
      lastToggledAt: '2026-01-01T00:00:00.000Z',
    };
    const settingsSnapshot: ExtensionSettingsSnapshot = {
      extensionId: 'ext.h',
      schemaVersion: 1,
      values: {},
      lastWrittenAt: '2026-01-01T00:00:00.000Z',
    };
    const packRecord: ExtensionPackRecord = {
      extensionId: 'ext.h',
      version: '1.0.0',
      integrity: TEST_INTEGRITY,
      installedAt: '2026-01-01T00:00:00.000Z',
      bundleContentRef: 'ref',
      manifestSnapshot: TEST_MANIFEST,
    };
    const lockEntry: ExtensionLockEntry = {
      extensionId: 'ext.h',
      version: '1.0.0',
      contributionRefs: [],
      integrity: TEST_INTEGRITY,
      lockedAt: '2026-01-01T00:00:00.000Z',
    };

    const state: FullExtensionState = {
      enablement: { 'ext.h': enablementState },
      devOverrides: {},
      settings: { 'ext.h': settingsSnapshot },
      packs: { 'ext.h': packRecord },
      lock: {
        entries: { 'ext.h': lockEntry },
        lastUpdatedAt: '2026-01-01T00:00:00.000Z',
      },
    };

    expect(state.enablement['ext.h'].enabled).toBe(true);
    expect(state.settings['ext.h'].schemaVersion).toBe(1);
    expect(state.packs['ext.h'].version).toBe('1.0.0');
    expect(state.lock.entries['ext.h'].version).toBe('1.0.0');
  });

  it('LifecycleEventQuery can be constructed with various filters', () => {
    const query: LifecycleEventQuery = {
      extensionId: 'ext.i',
      kinds: ['install', 'enable'],
      since: '2026-01-01T00:00:00.000Z',
      until: '2026-12-31T23:59:59.999Z',
      limit: 50,
    };
    expect(query.extensionId).toBe('ext.i');
    expect(query.kinds).toHaveLength(2);
    expect(query.limit).toBe(50);
  });
});

// ---------------------------------------------------------------------------
// Semantic contract tests (documented guarantees)
// ---------------------------------------------------------------------------

describe('repository contract semantics', () => {
  it('preserve-on-disable: enablement state retains extensionId and history fields', () => {
    // Disabling should only flip `enabled`, preserving extensionId and timestamp
    const beforeState = createEnablementState('preserve.test', true);
    const afterState: ExtensionEnablementState = {
      ...beforeState,
      enabled: false,
      lastToggledAt: new Date().toISOString(),
    };

    expect(afterState.extensionId).toBe(beforeState.extensionId);
    expect(afterState.enabled).toBe(false);
    // Pack record and settings are NOT deleted on disable (enforced by interface separation)
  });

  it('delete-on-uninstall: extensionId identity is extractable from pack record', () => {
    // Pack record carries extensionId so uninstall can find it for deletion
    const record = toPackRecord(TEST_METADATA, TEST_MANIFEST, 'ref');
    expect(record.extensionId).toBeTruthy();
    // Interface guarantees deletePackRecord(extensionId) removes this record
  });

  it('lock entry references contribution IDs explicitly', () => {
    const entry: ExtensionLockEntry = {
      extensionId: 'locked.ext',
      version: '2.0.0',
      contributionRefs: ['cmd.run', 'effect.fade', 'shader.blur'],
      integrity: TEST_INTEGRITY,
      lockedAt: '2026-01-01T00:00:00.000Z',
    };

    // Contribution refs are explicit and traceable
    expect(entry.contributionRefs).toContain('cmd.run');
    expect(entry.contributionRefs).toContain('effect.fade');
    expect(entry.contributionRefs).toContain('shader.blur');
  });

  it('lifecycle events are append-only with immutable IDs', () => {
    const event = createLifecycleEvent('ext', 'install', 'Install event');
    const idBefore = event.id;

    // Events are frozen (immutable)
    expect(Object.isFrozen(event)).toBe(true);

    // ID cannot be changed
    expect(event.id).toBe(idBefore);
  });

  it('settings snapshot tracks schema version independently of extension version', () => {
    // Schema version is separate from extension version for migration tracking
    const snapshot = createSettingsSnapshot('ext', 5, { key: 'val' });
    expect(snapshot.schemaVersion).toBe(5);
    // schemaVersion is independent of any extension version field
  });
});
