/**
 * Settings schema-version migration utilities (T10).
 *
 * Provides schema-version change detection, migration handler invocation,
 * and reset-to-defaults fallback for extension-owned settings during
 * activation. Emits lifecycle-event diagnostics through an optional
 * repository callback so that success, failure, and reset events are
 * persisted for audit.
 */

import type {
  ExtensionManifest,
  MigrationDeclaration,
} from '@/sdk/index';
import type {
  ExtensionStateRepository,
  ExtensionSettingsSnapshot,
  ExtensionLifecycleEvent,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import { createLifecycleEvent } from '@/tools/video-editor/runtime/extensionStateRepository';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * A settings migration handler function provided by the extension.
 *
 * Receives the current settings values (from the snapshot), the manifest
 * defaults (for reference), and the from/to schema versions. Returns the
 * migrated values or a promise resolving to them.
 *
 * If the handler throws or returns a rejected promise, the migration is
 * considered failed and settings are reset to defaults.
 */
export type SettingsMigrationHandler = (
  currentValues: Readonly<Record<string, unknown>>,
  manifestDefaults: Readonly<Record<string, unknown>>,
  fromSchemaVersion: number,
  toSchemaVersion: number,
) => Record<string, unknown> | Promise<Record<string, unknown>>;

/**
 * The outcome of a settings migration run.
 */
export interface SettingsMigrationResult {
  /** The final settings values (migrated or reset to defaults). */
  readonly values: Record<string, unknown>;
  /** The schema version to persist going forward. */
  readonly schemaVersion: number;
  /** True if a migration handler was invoked and succeeded. */
  readonly migrated: boolean;
  /** If migration failed, the error. Null otherwise. */
  readonly failure?: Error;
  /** True when settings were reset to manifest defaults (no handler or handler failed). */
  readonly resetToDefaults: boolean;
  /** Lifecycle events emitted during migration (for repository persistence). */
  readonly lifecycleEvents: readonly ExtensionLifecycleEvent[];
}

/**
 * Options for running a settings migration.
 */
export interface RunSettingsMigrationOptions {
  /** The extension manifest (for settingsSchema/Defaults and migration declarations). */
  readonly manifest: ExtensionManifest;
  /** The persisted settings snapshot (may have an older schema version). */
  readonly snapshot: ExtensionSettingsSnapshot;
  /**
   * Optional map of migration handler names to implementations.
   * Keys should match the `handler` field in MigrationDeclaration entries.
   */
  readonly migrationHandlers?: Readonly<Record<string, SettingsMigrationHandler>>;
  /**
   * Optional repository for persisting lifecycle events.
   * When provided, lifecycle events are appended (serialized awaits to
   * avoid read-modify-write races in non-transactional stores).
   */
  readonly repository?: ExtensionStateRepository;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the settings schema version from a manifest.
 *
 * Prefers `manifest.settingsSchema?.version` over the legacy
 * `manifest.settingsSchemaVersion` field. Falls back to 1 when neither
 * is present.
 */
export function getManifestSettingsSchemaVersion(manifest: ExtensionManifest): number {
  if (
    manifest.settingsSchema &&
    typeof (manifest.settingsSchema as Record<string, unknown>).version === 'number'
  ) {
    return (manifest.settingsSchema as Record<string, unknown>).version as number;
  }
  if (typeof (manifest as Record<string, unknown>).settingsSchemaVersion === 'number') {
    return (manifest as Record<string, unknown>).settingsSchemaVersion as number;
  }
  return 1;
}

/**
 * Find settings-kind migration declarations that could bridge the given
 * schema version gap. Returns declarations sorted by fromVersion (ascending)
 * to support chaining.
 */
export function findSettingsMigrationDeclarations(
  manifest: ExtensionManifest,
  _fromSchemaVersion: number,
  _toSchemaVersion: number,
): readonly MigrationDeclaration[] {
  const migrations = manifest.migrations;
  if (!migrations || migrations.length === 0) return [];

  const candidates: MigrationDeclaration[] = [];

  for (const m of migrations) {
    // Accept both typed MigrationDeclaration and legacy Record<string, unknown>
    const mig = m as Record<string, unknown>;
    if (mig.kind !== 'settings') continue;

    // We need typed fields for the declaration to be usable
    if (typeof mig.fromVersion !== 'string' || typeof mig.toVersion !== 'string') continue;

    candidates.push(m as unknown as MigrationDeclaration);
  }

  // Sort by fromVersion for deterministic chaining
  candidates.sort((a, b) => {
    // Simple numeric comparison of the last number in the semver-like string
    // For settings schema versions, we use integer versions
    const parseVer = (v: string): number => {
      const num = parseInt(v, 10);
      return Number.isNaN(num) ? 0 : num;
    };
    return parseVer(a.fromVersion) - parseVer(b.fromVersion);
  });

  return candidates;
}

// ---------------------------------------------------------------------------
// Main migration function
// ---------------------------------------------------------------------------

/**
 * Run settings migration between two schema versions.
 *
 * Compares the schema version in `snapshot` with the manifest's declared
 * settings schema version. When they differ:
 *
 * 1. Looks for applicable `kind: 'settings'` migration declarations in the
 *    manifest that bridge the gap.
 * 2. If a matching handler is provided in `migrationHandlers`, invokes it
 *    with the current settings values.
 * 3. On success, returns the migrated values with the new schema version.
 * 4. If no matching declaration or handler is found, or the handler throws,
 *    resets to manifest defaults with the new schema version.
 *
 * Lifecycle events (`migration_start`, `migration_success`, `migration_failure`,
 * `migration_reset`) are emitted through the optional repository. Repository
 * writes are serialized (awaited) to prevent read-modify-write races.
 *
 * @param extensionId  The extension identifier (for lifecycle events).
 * @param options      Migration options.
 * @returns The migration result with final values and lifecycle events.
 */
export async function runSettingsMigration(
  extensionId: string,
  options: RunSettingsMigrationOptions,
): Promise<SettingsMigrationResult> {
  const { manifest, snapshot, migrationHandlers, repository } = options;

  const manifestSchemaVersion = getManifestSettingsSchemaVersion(manifest);
  const snapshotSchemaVersion = snapshot.schemaVersion;

  const manifestDefaults: Record<string, unknown> =
    (manifest.settingsDefaults as Record<string, unknown> | undefined) ?? {};

  const currentValues: Record<string, unknown> = { ...(snapshot.values as Record<string, unknown>) };
  const lifecycleEvents: ExtensionLifecycleEvent[] = [];

  /** Append a lifecycle event, optionally persisting to repository (serialized). */
  async function emitEvent(
    kind: ExtensionLifecycleEvent['kind'],
    message: string,
    detail?: Record<string, unknown>,
  ): Promise<void> {
    const event = createLifecycleEvent(extensionId, kind, message, detail);
    lifecycleEvents.push(event);

    if (repository && !repository.isDisposed) {
      try {
        await repository.appendLifecycleEvent(event);
      } catch {
        // Repository write failed — event still captured in returned list
      }
    }
  }

  // No schema version change — nothing to migrate
  if (manifestSchemaVersion === snapshotSchemaVersion) {
    return {
      values: currentValues,
      schemaVersion: manifestSchemaVersion,
      migrated: false,
      resetToDefaults: false,
      lifecycleEvents,
    };
  }

  await emitEvent(
    'migration_start',
    `Settings schema migration started: v${snapshotSchemaVersion} → v${manifestSchemaVersion}`,
    { fromSchemaVersion: snapshotSchemaVersion, toSchemaVersion: manifestSchemaVersion },
  );

  // Find applicable migration declarations
  const declarations = findSettingsMigrationDeclarations(
    manifest,
    snapshotSchemaVersion,
    manifestSchemaVersion,
  );

  // If no declarations, reset to defaults
  if (declarations.length === 0) {
    await emitEvent(
      'migration_reset',
      `No settings migration declarations found for v${snapshotSchemaVersion} → v${manifestSchemaVersion}; resetting to defaults.`,
      { fromSchemaVersion: snapshotSchemaVersion, toSchemaVersion: manifestSchemaVersion },
    );

    return {
      values: { ...manifestDefaults },
      schemaVersion: manifestSchemaVersion,
      migrated: false,
      resetToDefaults: true,
      failure: new Error(
        `No settings migration declarations found; settings reset to manifest defaults (v${manifestSchemaVersion})`,
      ),
      lifecycleEvents,
    };
  }

  // Try each declaration in order (chaining).
  // Start with migrationSucceeded = false — only set to true when
  // at least one handler is actually invoked and succeeds.
  let migratedValues = { ...currentValues };
  let migrationSucceeded = false;
  let anyHandlerInvoked = false;

  for (const decl of declarations) {
    const handlerName = decl.handler;
    if (!handlerName) {
      // Declaration has no handler — skip it (not an error by itself)
      continue;
    }

    const handler = migrationHandlers?.[handlerName];
    if (!handler) {
      // Handler not provided → this IS a failure
      await emitEvent(
        'migration_failure',
        `Settings migration handler "${handlerName}" not found; resetting to defaults.`,
        {
          handler: handlerName,
          fromVersion: decl.fromVersion,
          toVersion: decl.toVersion,
          fromSchemaVersion: snapshotSchemaVersion,
          toSchemaVersion: manifestSchemaVersion,
        },
      );
      migrationSucceeded = false;
      anyHandlerInvoked = true;
      break;
    }

    try {
      const result = handler(
        migratedValues,
        manifestDefaults,
        snapshotSchemaVersion,
        manifestSchemaVersion,
      );
      const newValues = result instanceof Promise ? await result : result;
      migratedValues = { ...newValues };
      migrationSucceeded = true;
      anyHandlerInvoked = true;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      await emitEvent(
        'migration_failure',
        `Settings migration handler "${handlerName}" threw: ${error.message}`,
        {
          handler: handlerName,
          fromVersion: decl.fromVersion,
          toVersion: decl.toVersion,
          error: error.message,
          stack: error.stack,
        },
      );
      migrationSucceeded = false;
      anyHandlerInvoked = true;
      break;
    }
  }

  // If no handler was invoked at all (all declarations had no handler field),
  // treat as reset
  if (!anyHandlerInvoked) {
    await emitEvent(
      'migration_reset',
      `No usable settings migration handlers found for v${snapshotSchemaVersion} → v${manifestSchemaVersion}; resetting to defaults.`,
      { fromSchemaVersion: snapshotSchemaVersion, toSchemaVersion: manifestSchemaVersion },
    );

    return {
      values: { ...manifestDefaults },
      schemaVersion: manifestSchemaVersion,
      migrated: false,
      resetToDefaults: true,
      failure: new Error(
        `No usable settings migration handlers; settings reset to manifest defaults (v${manifestSchemaVersion})`,
      ),
      lifecycleEvents,
    };
  }

  if (migrationSucceeded) {
    await emitEvent(
      'migration_success',
      `Settings schema migration succeeded: v${snapshotSchemaVersion} → v${manifestSchemaVersion}`,
      {
        fromSchemaVersion: snapshotSchemaVersion,
        toSchemaVersion: manifestSchemaVersion,
        declarationsProcessed: declarations.length,
      },
    );

    return {
      values: migratedValues,
      schemaVersion: manifestSchemaVersion,
      migrated: true,
      resetToDefaults: false,
      lifecycleEvents,
    };
  }

  // Migration failed or had no usable handlers — reset to defaults
  await emitEvent(
    'migration_reset',
    `Settings migration failed or incomplete; resetting to defaults (v${manifestSchemaVersion}).`,
    { fromSchemaVersion: snapshotSchemaVersion, toSchemaVersion: manifestSchemaVersion },
  );

  return {
    values: { ...manifestDefaults },
    schemaVersion: manifestSchemaVersion,
    migrated: false,
    resetToDefaults: true,
    failure: new Error('Migration handlers unavailable or failed; settings reset to defaults'),
    lifecycleEvents,
  };
}
