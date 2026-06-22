/**
 * Tests for CachedExtensionStateRepository migration behavior.
 *
 * These focus on the {@link CachedExtensionStateRepository.registerMigration}
 * contract: validation of target versions, successful upgrades from older
 * schema versions, and fail-closed behavior when a migration throws.
 */

import { describe, expect, it } from 'vitest';
import {
  CachedExtensionStateRepository,
  CURRENT_SNAPSHOT_SCHEMA_VERSION,
  type FullSnapshotStore,
} from './extensionPersistenceCache';
import type { ExtensionSettingsSnapshot } from './extensionStateRepository';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeStore(serialized: string | null): FullSnapshotStore {
  return {
    async loadSnapshot(): Promise<string | null> {
      return serialized;
    },
    async saveSnapshot(): Promise<void> {
      // no-op for migration tests
    },
    async deleteSnapshot(): Promise<void> {
      // no-op for migration tests
    },
  };
}

function makeV0Snapshot(
  overrides: Record<string, unknown> = {},
): string {
  return JSON.stringify({
    meta: {
      schemaVersion: 0,
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
    },
    packs: {},
    enablement: {},
    overrides: {},
    settings: {},
    events: [],
    lock: {
      entries: {},
      lastUpdatedAt: '2026-01-01T00:00:00.000Z',
    },
    proposals: {},
    ...overrides,
  });
}

function makeSettingsSnapshot(
  extensionId: string,
  values: Record<string, unknown>,
): ExtensionSettingsSnapshot {
  return {
    extensionId,
    schemaVersion: 1,
    values,
    lastWrittenAt: '2026-06-22T00:00:00.000Z',
  };
}

// ---------------------------------------------------------------------------
// Migration registration
// ---------------------------------------------------------------------------

describe('CachedExtensionStateRepository.registerMigration', () => {
  it('rejects target versions less than or equal to zero', () => {
    const repo = new CachedExtensionStateRepository(makeStore(null));

    expect(() =>
      repo.registerMigration(0, (state) => state),
    ).toThrow(/target version must be > 0/i);

    expect(() =>
      repo.registerMigration(-1, (state) => state),
    ).toThrow(/target version must be > 0/i);
  });

  it('rejects target versions greater than the current schema version', () => {
    const repo = new CachedExtensionStateRepository(makeStore(null));

    expect(() =>
      repo.registerMigration(CURRENT_SNAPSHOT_SCHEMA_VERSION + 1, (state) => state),
    ).toThrow(/exceeds current schema version/i);
  });

  it('applies a registered migration during hydration and updates schema version', async () => {
    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const repo = new CachedExtensionStateRepository(
      makeStore(makeV0Snapshot()),
      diagnostics,
    );

    let migrationRan = false;
    repo.registerMigration(1, (state) => {
      migrationRan = true;
      state.settings['migrated.ext'] = makeSettingsSnapshot('migrated.ext', {
        upgraded: true,
      });
      return state;
    });

    await repo.initialize();

    expect(migrationRan).toBe(true);
    expect(
      diagnostics.some((d) => d.code === 'extension_cache_migration_start'),
    ).toBe(true);
    expect(
      diagnostics.some((d) => d.code === 'extension_cache_migration_success'),
    ).toBe(true);

    const settings = await repo.getSettingsSnapshot('migrated.ext');
    expect(settings).not.toBeNull();
    expect(settings!.values.upgraded).toBe(true);

    await repo.dispose();
  });

  it('fails closed when a migration throws, emitting a diagnostic', async () => {
    const diagnostics: Array<{ severity: string; code: string; message: string; milestone?: string }> = [];
    const repo = new CachedExtensionStateRepository(
      makeStore(makeV0Snapshot()),
      diagnostics,
    );

    repo.registerMigration(1, () => {
      throw new Error('migration intentionally failed');
    });

    await repo.initialize();

    const errors = diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);
    expect(
      errors.some((d) => d.code === 'extension_cache_migration_failure'),
    ).toBe(true);

    // No partial state is exposed after a failed migration
    await expect(repo.getSettingsSnapshot('any')).rejects.toThrow(/hydrat/i);
    await expect(repo.getEnablementState('any')).rejects.toThrow(/hydrat/i);
    await expect(repo.getFullExtensionState()).rejects.toThrow(/hydrat/i);

    await repo.dispose();
  });
});
