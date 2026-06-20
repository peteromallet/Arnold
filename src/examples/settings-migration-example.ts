/**
 * settings-migration-example — T10 settings schema-version migration example.
 *
 * Demonstrates:
 *   1. A `MigrationDeclaration` of kind 'settings' in the extension manifest.
 *   2. A `SettingsMigrationHandler` function that migrates settings from
 *      an older schema version to the current one.
 *   3. Use of `runSettingsMigration()` to execute the migration and
 *      produce a `SettingsMigrationResult` with lifecycle events.
 *   4. The `StateRepository` and `SettingsSnapshot` contracts required
 *      for repository-backed settings persistence.
 *
 * Settings migrations allow extensions to evolve their settings schema
 * across versions. When the persisted schema version differs from the
 * manifest's declared version, migration handlers transform the stored
 * values. On failure, settings reset to manifest defaults.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 */

import { defineExtension, runSettingsMigration, getManifestSettingsSchemaVersion, createLifecycleEvent } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionManifest,
  SettingsMigrationHandler,
  SettingsMigrationResult,
  RunSettingsMigrationOptions,
  MigrationDeclaration,
  SettingsSnapshot,
  StateRepository,
  LifecycleEvent,
  ExtensionSettingsService,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Migration handler — migrates settings from v1 to v2
// ---------------------------------------------------------------------------

/**
 * Example migration handler: moves a flat `volume` setting into a nested
 * `audio.volume` key and adds a new `audio.muted` default.
 */
export const migrateV1ToV2: SettingsMigrationHandler = (
  currentValues: Readonly<Record<string, unknown>>,
  manifestDefaults: Readonly<Record<string, unknown>>,
  _fromSchemaVersion: number,
  _toSchemaVersion: number,
): Record<string, unknown> => {
  const migrated: Record<string, unknown> = { ...currentValues };

  // Migrate flat `volume` → nested `audio.volume`
  if ('volume' in migrated && !('audio' in migrated)) {
    const volume = migrated.volume;
    delete migrated.volume;
    migrated.audio = { volume, muted: false };
  }

  // Apply any new defaults not present in the current values
  for (const [key, value] of Object.entries(manifestDefaults)) {
    if (!(key in migrated)) {
      migrated[key] = value;
    }
  }

  return migrated;
};

// ---------------------------------------------------------------------------
// Manifest with settings schema and migration declarations
// ---------------------------------------------------------------------------

/**
 * A minimal manifest for demonstrating settings migration.
 * Declares settingsSchemaVersion: 2 and a migration from v1 to v2.
 */
export const settingsMigrationManifest: ExtensionManifest = {
  id: 'com.reigh.examples.settings-migration' as any,
  version: '2.0.0',
  label: 'Settings Migration Example',
  description: 'Demonstrates settings schema-version migration via T10 SDK surface.',
  apiVersion: 1,
  settingsSchema: {
    version: 2,
  },
  settingsDefaults: {
    'audio.volume': 0.8,
    'audio.muted': false,
    'ui.theme': 'dark',
  },
  migrations: [
    {
      kind: 'settings',
      fromVersion: '1',
      toVersion: '2',
      handler: 'migrateV1ToV2',
      description: 'Migrates flat volume → nested audio.volume with muted default.',
    } as MigrationDeclaration,
  ],
};

// ---------------------------------------------------------------------------
// Minimal state repository stub for example purposes
// ---------------------------------------------------------------------------

/**
 * A minimal in-memory StateRepository stub that satisfies the SDK contract.
 * Real implementations would persist to IndexedDB, Supabase, or Astrid bridge.
 */
export function createExampleRepository(): StateRepository {
  const disposed = false;
  const snapshots: SettingsSnapshot[] = [];
  const events: LifecycleEvent[] = [];

  return {
    get isDisposed(): boolean {
      return disposed;
    },
    async putSettingsSnapshot(snapshot: SettingsSnapshot): Promise<void> {
      if (disposed) return;
      snapshots.push(snapshot);
    },
    async appendLifecycleEvent(event: LifecycleEvent): Promise<void> {
      if (disposed) return;
      events.push(event);
    },
  };
}

// ---------------------------------------------------------------------------
// Example migration runner
// ---------------------------------------------------------------------------

/**
 * Run a settings migration for the example manifest.
 *
 * Simulates a scenario where the stored snapshot has schema version 1
 * and the manifest declares version 2, triggering the migration handler.
 *
 * @returns The migration result with final settings values and lifecycle events.
 */
export async function runExampleMigration(): Promise<SettingsMigrationResult> {
  const manifest = settingsMigrationManifest;
  const repository = createExampleRepository();

  // Simulate a persisted snapshot from the older schema version
  const snapshot: SettingsSnapshot = {
    extensionId: 'com.reigh.examples.settings-migration',
    schemaVersion: 1, // older version
    values: {
      volume: 0.5, // flat volume — will be migrated to audio.volume
      'ui.theme': 'light',
    },
    lastWrittenAt: new Date().toISOString(),
  };

  const options: RunSettingsMigrationOptions = {
    manifest,
    snapshot,
    migrationHandlers: {
      migrateV1ToV2,
    },
    repository,
  };

  const result = await runSettingsMigration(
    'com.reigh.examples.settings-migration',
    options,
  );

  return result;
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const settingsMigrationExample: ReighExtension = defineExtension({
  manifest: settingsMigrationManifest,
});

/** Re-export types and helpers for SDK consumers. */
export type {
  SettingsMigrationHandler,
  SettingsMigrationResult,
  RunSettingsMigrationOptions,
  MigrationDeclaration,
  SettingsSnapshot,
  StateRepository,
  LifecycleEvent,
  ExtensionSettingsService,
};
export { runSettingsMigration, getManifestSettingsSchemaVersion, createLifecycleEvent };
