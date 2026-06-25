/**
 * Tests for settings schema-version migration (T10).
 *
 * Validates:
 *  - Schema version detection from manifest (settingsSchema.version + legacy settingsSchemaVersion)
 *  - Migration declaration discovery for kind: 'settings'
 *  - runSettingsMigration: no-op when versions match
 *  - runSettingsMigration: handler invocation on version mismatch
 *  - runSettingsMigration: reset to defaults when no migration declarations
 *  - runSettingsMigration: reset to defaults when handler not found
 *  - runSettingsMigration: reset to defaults when handler throws
 *  - runSettingsMigration: lifecycle events emitted (start, success, failure, reset)
 *  - runSettingsMigration: chaining multiple declarations
 *  - runSettingsMigration: async handler support
 *  - Integration with repository for lifecycle event persistence
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  runSettingsMigration,
  getManifestSettingsSchemaVersion,
  findSettingsMigrationDeclarations,
} from './extensionSettingsMigration';
import type {
  SettingsMigrationHandler,
  SettingsMigrationResult,
} from './extensionSettingsMigration';
import type { ExtensionManifest, MigrationDeclaration } from './index';
import type { SettingsSnapshot } from './contracts';
import { InMemoryStateRepository } from './__tests__/inMemoryStateRepository';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeManifest(overrides?: Partial<ExtensionManifest>): ExtensionManifest {
  return {
    id: 'test.extension' as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    ...overrides,
  } as ExtensionManifest;
}

function makeManifestWithSchema(
  extensionId: string,
  schemaVersion: number,
  defaults?: Record<string, unknown>,
  migrations?: MigrationDeclaration[],
): ExtensionManifest {
  return {
    id: extensionId as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    settingsSchema: { version: schemaVersion },
    ...(defaults ? { settingsDefaults: defaults } : {}),
    ...(migrations ? { migrations } : {}),
  } as ExtensionManifest;
}

function makeManifestWithLegacySchemaVersion(
  extensionId: string,
  settingsSchemaVersion: number,
  defaults?: Record<string, unknown>,
): ExtensionManifest {
  return {
    id: extensionId as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    settingsSchemaVersion,
    ...(defaults ? { settingsDefaults: defaults } : {}),
  } as ExtensionManifest;
}

function makeSnapshot(
  extensionId: string,
  schemaVersion: number,
  values: Record<string, unknown>,
): SettingsSnapshot {
  return Object.freeze({
    extensionId,
    schemaVersion,
    values: Object.freeze({ ...values }),
    lastWrittenAt: new Date().toISOString(),
  });
}

function makeRepo(): { repo: InMemoryStateRepository; cleanup: () => Promise<void> } {
  const repo = new InMemoryStateRepository();
  return {
    repo,
    cleanup: async () => {
      if (!repo.isDisposed) await repo.dispose();
    },
  };
}

// ---------------------------------------------------------------------------
// getManifestSettingsSchemaVersion
// ---------------------------------------------------------------------------

describe('getManifestSettingsSchemaVersion', () => {
  it('returns version from settingsSchema.version', () => {
    const manifest = makeManifestWithSchema('ext.a', 5);
    expect(getManifestSettingsSchemaVersion(manifest)).toBe(5);
  });

  it('returns version from legacy settingsSchemaVersion', () => {
    const manifest = makeManifestWithLegacySchemaVersion('ext.a', 3);
    expect(getManifestSettingsSchemaVersion(manifest)).toBe(3);
  });

  it('returns 1 when neither field is present', () => {
    const manifest = makeManifest();
    expect(getManifestSettingsSchemaVersion(manifest)).toBe(1);
  });

  it('prefers settingsSchema.version over legacy field', () => {
    const manifest = {
      ...makeManifestWithLegacySchemaVersion('ext.a', 3),
      settingsSchema: { version: 7 },
    } as ExtensionManifest;
    expect(getManifestSettingsSchemaVersion(manifest)).toBe(7);
  });
});

// ---------------------------------------------------------------------------
// findSettingsMigrationDeclarations
// ---------------------------------------------------------------------------

describe('findSettingsMigrationDeclarations', () => {
  it('returns empty when manifest has no migrations', () => {
    const manifest = makeManifest();
    const result = findSettingsMigrationDeclarations(manifest, 1, 2);
    expect(result).toEqual([]);
  });

  it('returns empty when no settings-kind migrations exist', () => {
    const manifest = makeManifest({
      migrations: [
        { kind: 'contribution', fromVersion: '1.0.0', toVersion: '2.0.0' },
        { kind: 'manifest', fromVersion: '1.0.0', toVersion: '2.0.0' },
      ] as any[],
    });
    const result = findSettingsMigrationDeclarations(manifest, 1, 2);
    expect(result).toEqual([]);
  });

  it('returns settings-kind migrations', () => {
    const m1: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'migrateV1toV2',
    };
    const manifest = makeManifest({
      migrations: [m1],
    });
    const result = findSettingsMigrationDeclarations(manifest, 1, 2);
    expect(result).toHaveLength(1);
    expect(result[0].handler).toBe('migrateV1toV2');
  });

  it('filters out non-settings kinds', () => {
    const m1: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'migrate',
    };
    const m2: MigrationDeclaration = {
      kind: 'contribution',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'other',
    };
    const manifest = makeManifest({
      migrations: [m1, m2],
    });
    const result = findSettingsMigrationDeclarations(manifest, 1, 2);
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe('settings');
  });

  it('sorts declarations by fromVersion', () => {
    const m1: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '3.0.0',
      toVersion: '4.0.0',
      handler: 'last',
    };
    const m2: MigrationDeclaration = {
      kind: 'settings',
      fromVersion: '1.0.0',
      toVersion: '2.0.0',
      handler: 'first',
    };
    const manifest = makeManifest({
      migrations: [m1, m2],
    });
    const result = findSettingsMigrationDeclarations(manifest, 1, 4);
    expect(result[0].handler).toBe('first');
    expect(result[1].handler).toBe('last');
  });

  it('handles legacy plain-object migration entries', () => {
    const manifest = makeManifest({
      migrations: [
        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'legacy' },
      ] as any[],
    });
    const result = findSettingsMigrationDeclarations(manifest, 1, 2);
    expect(result).toHaveLength(1);
    expect(result[0].handler).toBe('legacy');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — no-op when versions match
// ---------------------------------------------------------------------------

describe('runSettingsMigration — no-op', () => {
  const EXT_ID = 't10.noop.ext';

  it('returns snapshot values unchanged when schema versions match', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'light' });
    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'dark', fontSize: 16 });

    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });

    expect(result.migrated).toBe(false);
    expect(result.resetToDefaults).toBe(false);
    expect(result.schemaVersion).toBe(2);
    expect(result.values.theme).toBe('dark');
    expect(result.values.fontSize).toBe(16);
    expect(result.lifecycleEvents).toHaveLength(0);
  });

  it('returns snapshot values when no settingsSchema declared (both default to 1)', async () => {
    const manifest = makeManifest({ id: EXT_ID as any } as Partial<ExtensionManifest>);
    // snapshot with schemaVersion 1 and no manifest settingsSchema -> both are 1
    const snapshot = makeSnapshot(EXT_ID, 1, { custom: 'value' });
    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });
    expect(result.migrated).toBe(false);
    expect(result.resetToDefaults).toBe(false);
    expect(result.values.custom).toBe('value');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — migration success
// ---------------------------------------------------------------------------

describe('runSettingsMigration — success', () => {
  const EXT_ID = 't10.success.ext';

  it('invokes handler and returns migrated values', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 3, { theme: 'light', maxItems: 100 }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'v1tov2' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark', oldKey: 'oldValue' });

    const handler: SettingsMigrationHandler = (values, defaults, fromV, toV) => {
      return {
        theme: values.theme,
        newKey: 'newValue',
        _migratedFrom: fromV,
        _migratedTo: toV,
      };
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { v1tov2: handler },
    });

    expect(result.migrated).toBe(true);
    expect(result.resetToDefaults).toBe(false);
    expect(result.schemaVersion).toBe(3);
    expect(result.values.theme).toBe('dark');
    expect(result.values.newKey).toBe('newValue');
    expect(result.values._migratedFrom).toBe(1);
    expect(result.values._migratedTo).toBe(3);
    // oldKey was not carried forward by the handler (intentional)
  });

  it('lifecycle events include migration_start and migration_success', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'light' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'doit' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = (values) => ({ ...values });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { doit: handler },
    });

    expect(result.lifecycleEvents).toHaveLength(2);
    expect(result.lifecycleEvents[0].kind).toBe('migration_start');
    expect(result.lifecycleEvents[1].kind).toBe('migration_success');
  });

  it('passes manifest defaults to handler for reference', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { defaultTheme: 'system' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'check' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { userTheme: 'dark' });

    let capturedDefaults: Record<string, unknown> = {};

    const handler: SettingsMigrationHandler = (values, defaults) => {
      capturedDefaults = { ...defaults };
      return { ...values, theme: defaults.defaultTheme };
    };

    await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { check: handler },
    });

    expect(capturedDefaults.defaultTheme).toBe('system');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — reset to defaults when no declarations
// ---------------------------------------------------------------------------

describe('runSettingsMigration — reset when no declarations', () => {
  const EXT_ID = 't10.reset.ext';

  it('resets to manifest defaults when no migration declarations exist', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 3, { theme: 'system', maxItems: 100 });
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark', oldSetting: 'legacy' });

    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });

    expect(result.migrated).toBe(false);
    expect(result.resetToDefaults).toBe(true);
    expect(result.schemaVersion).toBe(3);
    expect(result.values.theme).toBe('system');
    expect(result.values.maxItems).toBe(100);
    // oldSetting should be gone (reset to defaults)
    expect(result.values.oldSetting).toBeUndefined();
  });

  it('emits migration_start and migration_reset lifecycle events', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' });
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'old' });

    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });

    expect(result.lifecycleEvents).toHaveLength(2);
    expect(result.lifecycleEvents[0].kind).toBe('migration_start');
    expect(result.lifecycleEvents[1].kind).toBe('migration_reset');
    expect(result.lifecycleEvents[1].message).toContain('resetting to defaults');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — handler not found
// ---------------------------------------------------------------------------

describe('runSettingsMigration — handler not found', () => {
  const EXT_ID = 't10.nohandler.ext';

  it('resets to defaults when handler name is not in migrationHandlers', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'missing' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'old' });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { otherHandler: (v) => v },
    });

    expect(result.resetToDefaults).toBe(true);
    expect(result.values.theme).toBe('default');
  });

  it('emits migration_failure when handler not found', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, {}, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'missing' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, {});

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: {},
    });

    const failureEvents = result.lifecycleEvents.filter((e) => e.kind === 'migration_failure');
    expect(failureEvents).toHaveLength(1);
    expect(failureEvents[0].message).toContain('not found');
  });

  it('resets when handler field is empty/undefined in declaration', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0' }, // no handler
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'old' });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: {},
    });

    expect(result.resetToDefaults).toBe(true);
    expect(result.values.theme).toBe('default');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — handler throws
// ---------------------------------------------------------------------------

describe('runSettingsMigration — handler throws', () => {
  const EXT_ID = 't10.throws.ext';

  it('resets to defaults when handler throws', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'explode' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'old' });

    const handler: SettingsMigrationHandler = () => {
      throw new Error('Boom!');
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { explode: handler },
    });

    expect(result.resetToDefaults).toBe(true);
    expect(result.values.theme).toBe('default');
    expect(result.failure).toBeDefined();
    expect(result.failure!.message).toContain('Migration handlers unavailable or failed');
  });

  it('emits migration_failure when handler throws', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, {}, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'boom' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, {});

    const handler: SettingsMigrationHandler = () => {
      throw new Error('Migration error!');
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { boom: handler },
    });

    const failureEvents = result.lifecycleEvents.filter((e) => e.kind === 'migration_failure');
    expect(failureEvents).toHaveLength(1);
    expect(failureEvents[0].message).toContain('Migration error!');
    expect(failureEvents[0].detail?.error).toBe('Migration error!');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — async handler support
// ---------------------------------------------------------------------------

describe('runSettingsMigration — async handler', () => {
  const EXT_ID = 't10.async.ext';

  it('awaits async handlers and returns migrated values', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'asyncMigrate' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = async (values) => {
      await new Promise((r) => setTimeout(r, 10));
      return { ...values, asyncFlag: true };
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { asyncMigrate: handler },
    });

    expect(result.migrated).toBe(true);
    expect(result.values.theme).toBe('dark');
    expect(result.values.asyncFlag).toBe(true);
  });

  it('resets to defaults when async handler rejects', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'fallback' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'failAsync' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = async () => {
      await new Promise((r) => setTimeout(r, 10));
      throw new Error('Async failure');
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { failAsync: handler },
    });

    expect(result.resetToDefaults).toBe(true);
    expect(result.values.theme).toBe('fallback');
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — chaining multiple declarations
// ---------------------------------------------------------------------------

describe('runSettingsMigration — chaining', () => {
  const EXT_ID = 't10.chain.ext';

  it('chains multiple handlers in declaration order', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 3, { step: 0 }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'step1' },
      { kind: 'settings', fromVersion: '2.0.0', toVersion: '3.0.0', handler: 'step2' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { original: true });

    const step1: SettingsMigrationHandler = (values) => ({
      ...values,
      step1Applied: true,
    });

    const step2: SettingsMigrationHandler = (values) => ({
      ...values,
      step2Applied: true,
    });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { step1, step2 },
    });

    expect(result.migrated).toBe(true);
    expect(result.values.original).toBe(true);
    expect(result.values.step1Applied).toBe(true);
    expect(result.values.step2Applied).toBe(true);
  });

  it('aborts chaining on first failure and resets', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 3, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'step1' },
      { kind: 'settings', fromVersion: '2.0.0', toVersion: '3.0.0', handler: 'step2Fail' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { original: true });

    const step1: SettingsMigrationHandler = (values) => ({
      ...values,
      step1Applied: true,
    });

    const step2Fail: SettingsMigrationHandler = () => {
      throw new Error('Step 2 failure');
    };

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { step1, step2Fail },
    });

    // Should reset to defaults because chain aborted
    expect(result.resetToDefaults).toBe(true);
    expect(result.values.theme).toBe('default');
    expect(result.values.original).toBeUndefined();
    expect(result.values.step1Applied).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — repository integration
// ---------------------------------------------------------------------------

describe('runSettingsMigration — repository integration', () => {
  const EXT_ID = 't10.repo.ext';

  let repo: InMemoryStateRepository;
  let cleanup: () => Promise<void>;

  beforeEach(async () => {
    const r = makeRepo();
    repo = r.repo;
    cleanup = r.cleanup;
    await repo.initialize();
  });

  afterEach(async () => {
    await cleanup();
  });

  it('persists lifecycle events to repository', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'go' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const handler: SettingsMigrationHandler = (values) => values;

    await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { go: handler },
      repository: repo,
    });

    // Give fire-and-forget events time to write
    await new Promise((r) => setTimeout(r, 30));

    const events = await repo.getLifecycleEvents(EXT_ID);
    const migrationEvents = events
      .filter((e) =>
        ['migration_start', 'migration_success', 'migration_failure', 'migration_reset'].includes(e.kind),
      )
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    expect(migrationEvents).toHaveLength(2);
    expect(migrationEvents[0].kind).toBe('migration_start');
    expect(migrationEvents[1].kind).toBe('migration_success');
  });

  it('persists migration_reset to repository when no declarations exist', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' });
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      repository: repo,
    });

    await new Promise((r) => setTimeout(r, 30));

    const events = await repo.getLifecycleEvents(EXT_ID);
    const resetEvents = events.filter((e) => e.kind === 'migration_reset');
    expect(resetEvents).toHaveLength(1);
    expect(resetEvents[0].message).toContain('resetting to defaults');
  });

  it('does not throw when repository is disposed', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' });
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    await repo.dispose();

    // Should not throw even though repo is disposed
    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      repository: repo,
    });

    expect(result.resetToDefaults).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// runSettingsMigration — edge cases
// ---------------------------------------------------------------------------

describe('runSettingsMigration — edge cases', () => {
  const EXT_ID = 't10.edge.ext';

  it('handles empty snapshot values', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' }, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'go' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, {});

    const handler: SettingsMigrationHandler = (values) => ({
      ...values,
      migrated: true,
    });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { go: handler },
    });

    expect(result.values.migrated).toBe(true);
  });

  it('handles undefined manifest defaults', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, undefined, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'go' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { existing: true });

    const handler: SettingsMigrationHandler = (values) => values;

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { go: handler },
    });

    expect(result.migrated).toBe(true);
    expect(result.values.existing).toBe(true);
  });

  it('legacy settingsSchemaVersion mismatch triggers migration', async () => {
    const manifest = makeManifestWithLegacySchemaVersion(EXT_ID, 5, { theme: 'v5' });
    const snapshot = makeSnapshot(EXT_ID, 2, { theme: 'v2' });

    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });

    expect(result.resetToDefaults).toBe(true);
    expect(result.schemaVersion).toBe(5);
    expect(result.values.theme).toBe('v5');
  });

  it('multiple settings-kind declarations use all of them', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 3, {}, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'a' },
      { kind: 'settings', fromVersion: '2.0.0', toVersion: '3.0.0', handler: 'b' },
      { kind: 'contribution', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'c' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, { count: 0 });

    const a: SettingsMigrationHandler = (values) => ({ ...values, count: (values.count as number) + 1 });
    const b: SettingsMigrationHandler = (values) => ({ ...values, count: (values.count as number) + 10 });

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { a, b },
    });

    expect(result.migrated).toBe(true);
    expect(result.values.count).toBe(11); // 0 + 1 + 10
  });

  it('migration result has failure field when reset', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, { theme: 'default' });
    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark' });

    const result = await runSettingsMigration(EXT_ID, { manifest, snapshot });

    expect(result.failure).toBeDefined();
    expect(result.failure!.message).toContain('settings reset to manifest defaults');
  });

  it('migration result has no failure on success', async () => {
    const manifest = makeManifestWithSchema(EXT_ID, 2, {}, [
      { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'go' },
    ]);

    const snapshot = makeSnapshot(EXT_ID, 1, {});
    const handler: SettingsMigrationHandler = (v) => v;

    const result = await runSettingsMigration(EXT_ID, {
      manifest,
      snapshot,
      migrationHandlers: { go: handler },
    });

    expect(result.failure).toBeUndefined();
  });
});
