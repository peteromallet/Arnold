/**
 * ExtensionStateRepository contract for M14.
 *
 * Defines the persistence abstraction for extension state: installed packs,
 * enablement, dev overrides, settings, schema versions, lifecycle events,
 * and project lock metadata.
 *
 * The contract explicitly separates:
 *   - preserve-on-disable: disable unregisters contributions but preserves
 *     settings, pack records, and lifecycle history.
 *   - delete-on-uninstall: uninstall deletes settings, pack records, and
 *     enablement state, but preserves lifecycle events for audit.
 *
 * Storage adapters (IndexedDB, provider-backed) implement this interface
 * in later tasks (T6, T7).
 */

import type {
  IntegrityHash,
  InstalledExtensionMetadata,
  InstalledExtensionPackage,
  ExtensionManifest,
  ExtensionDiagnostic,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Extension pack record (persisted)
// ---------------------------------------------------------------------------

/**
 * A persisted record of an installed extension pack.
 *
 * Stored in the repository after a successful install.  The record is
 * preserved on disable and deleted on uninstall.
 *
 * Bundle content bytes live in browser-local IndexedDB (SD2); this record
 * holds the metadata and a content reference key.
 */
export interface ExtensionPackRecord {
  /** Unique extension identifier. */
  readonly extensionId: string;
  /** Manifest version at install time. */
  readonly version: string;
  /** API version targeted by this pack. */
  readonly apiVersion?: number;
  /** SHA-256 SRI integrity of the installed bundle. */
  readonly integrity: IntegrityHash;
  /** ISO 8601 timestamp of installation. */
  readonly installedAt: string;
  /** ISO 8601 timestamp of last update (or same as installedAt). */
  readonly updatedAt?: string;
  /** Reference key for bundle content in IndexedDB. */
  readonly bundleContentRef: string;
  /** Manifest snapshot at install time (for diagnostics/conflict resolution). */
  readonly manifestSnapshot: ExtensionManifest;
  /** Publisher identity. */
  readonly publisher?: string;
  /** SPDX license identifier. */
  readonly license?: string;
  /** Icon URL or data URI. */
  readonly icon?: string;
}

// ---------------------------------------------------------------------------
// Enablement state (persisted)
// ---------------------------------------------------------------------------

/**
 * The enablement state of a single installed extension.
 *
 * Preserved on disable. Deleted on uninstall.
 */
export interface ExtensionEnablementState {
  /** The extension this state describes. */
  readonly extensionId: string;
  /** Whether the extension is currently enabled. */
  readonly enabled: boolean;
  /** ISO 8601 timestamp of the last enable/disable toggle. */
  readonly lastToggledAt: string;
  /** Human-readable reason for the last toggle (e.g. "user disabled via manager"). */
  readonly toggleReason?: string;
}

// ---------------------------------------------------------------------------
// Dev override state (persisted)
// ---------------------------------------------------------------------------

/**
 * Dev-only override preference for an extension that has both a local
 * (workspace source) and an installed (bundle) form.
 *
 * Default conflict resolution policy (SD6): installed-wins.
 * Dev overrides allow a developer to prefer the local source version.
 */
export interface DevOverrideState {
  /** The extension this override applies to. */
  readonly extensionId: string;
  /** When true, the local workspace source is preferred over the installed bundle. */
  readonly preferLocalSource: boolean;
  /** ISO 8601 timestamp when the override was set. */
  readonly setAt: string;
  /** ISO 8601 timestamp when the override was last changed. */
  readonly updatedAt?: string;
}

// ---------------------------------------------------------------------------
// Settings snapshot (persisted)
// ---------------------------------------------------------------------------

/**
 * A snapshot of per-extension settings with schema version tracking.
 *
 * Preserved on disable. Deleted on uninstall.
 */
export interface ExtensionSettingsSnapshot {
  /** The extension these settings belong to. */
  readonly extensionId: string;
  /** The settings schema version active when this snapshot was written. */
  readonly schemaVersion: number;
  /** The settings key-value map. */
  readonly values: Record<string, unknown>;
  /** ISO 8601 timestamp of the last settings write. */
  readonly lastWrittenAt: string;
}

// ---------------------------------------------------------------------------
// Lifecycle event (persisted append-only log)
// ---------------------------------------------------------------------------

/** Kinds of lifecycle events recorded by the repository. */
export type LifecycleEventKind =
  | 'install'
  | 'uninstall'
  | 'enable'
  | 'disable'
  | 'load'
  | 'unload'
  | 'activation_success'
  | 'activation_failure'
  | 'migration_start'
  | 'migration_success'
  | 'migration_failure'
  | 'migration_reset'
  | 'integrity_pass'
  | 'integrity_fail'
  | 'dependency_blocked'
  | 'dependency_degraded'
  | 'conflict_override_set'
  | 'conflict_override_cleared';

/**
 * A single lifecycle event for an extension.
 *
 * Appended to the repository on significant state transitions.
 * Preserved across disable and uninstall for audit purposes.
 */
export interface ExtensionLifecycleEvent {
  /** Unique event identifier (UUID). */
  readonly id: string;
  /** The extension this event pertains to. */
  readonly extensionId: string;
  /** The kind of lifecycle event. */
  readonly kind: LifecycleEventKind;
  /** ISO 8601 timestamp of the event. */
  readonly timestamp: string;
  /** Human-readable description of the event. */
  readonly message: string;
  /** Structured detail (e.g. error stack, migration versions, dependency IDs). */
  readonly detail?: Record<string, unknown>;
  /** Optional associated diagnostic. */
  readonly diagnostic?: ExtensionDiagnostic;
}

// ---------------------------------------------------------------------------
// Project lock metadata (persisted)
// ---------------------------------------------------------------------------

/**
 * A single entry in the project-level extension lock.
 *
 * Updated when an installed extension is enabled.  Contains the information
 * required to reproduce the extension state for team/project consistency.
 *
 * This is project metadata, not extension-owned data (SD2).
 */
export interface ExtensionLockEntry {
  /** The extension identifier. */
  readonly extensionId: string;
  /** The installed pack version. */
  readonly version: string;
  /**
   * Acceptable version range for the extension.
   * Defaults to the exact installed version when not explicitly set.
   */
  readonly versionRange?: string;
  /** Contribution IDs referenceable by this extension. */
  readonly contributionRefs: readonly string[];
  /** SHA-256 SRI integrity hash of the installed bundle. */
  readonly integrity: IntegrityHash;
  /** ISO 8601 timestamp when this lock entry was created. */
  readonly lockedAt: string;
  /** ISO 8601 timestamp of the last update. */
  readonly updatedAt?: string;
}

/**
 * The full project lock: a collection of lock entries keyed by extension ID.
 */
export interface ExtensionLock {
  /** Lock entries keyed by extension ID. */
  readonly entries: Record<string, ExtensionLockEntry>;
  /** ISO 8601 timestamp of the last lock mutation. */
  readonly lastUpdatedAt: string;
}

// ---------------------------------------------------------------------------
// Query / filter helpers
// ---------------------------------------------------------------------------

/** Query criteria for listing lifecycle events. */
export interface LifecycleEventQuery {
  /** Filter by extension ID (exact match). */
  extensionId?: string;
  /** Filter by one or more event kinds. */
  kinds?: readonly LifecycleEventKind[];
  /** Inclusive start timestamp (ISO 8601). */
  since?: string;
  /** Inclusive end timestamp (ISO 8601). */
  until?: string;
  /** Maximum number of events to return (default: 100). */
  limit?: number;
}

// ---------------------------------------------------------------------------
// ExtensionStateRepository interface
// ---------------------------------------------------------------------------

/**
 * The persistence contract for extension state.
 *
 * Implementations provide storage for installed packs, enablement, dev
 * overrides, settings, lifecycle events, and project lock metadata.
 *
 * ## Preserve-on-disable semantics
 *
 * Disabling an extension MUST:
 * 1. Update the enablement state to `enabled: false`.
 * 2. Append an `enable` → `disable` lifecycle event.
 * 3. Preserve the pack record, settings snapshot, and lifecycle history.
 *
 * The caller (ExtensionLoader / manager) is responsible for unregistering
 * contributions and cleaning up runtime registries.
 *
 * ## Delete-on-uninstall semantics
 *
 * Uninstalling an extension MUST:
 * 1. Delete the pack record.
 * 2. Delete the enablement state.
 * 3. Delete the settings snapshot.
 * 4. Delete any dev override state.
 * 5. Remove the lock entry from project lock metadata.
 * 6. Append an `uninstall` lifecycle event (preserved for audit).
 * 7. Preserve all prior lifecycle events (for audit).
 */
export interface ExtensionStateRepository {
  // -----------------------------------------------------------------------
  // Repository lifecycle
  // -----------------------------------------------------------------------

  /**
   * Initialize the repository (open database, load provider state, etc.).
   *
   * Must be called before any other method.  Idempotent — subsequent
   * calls are no-ops.
   */
  initialize(): Promise<void>;

  /**
   * Dispose the repository, closing any open connections.
   *
   * Idempotent — subsequent calls are no-ops.  After disposal, all
   * methods reject with a descriptive error.
   */
  dispose(): Promise<void>;

  /** Whether the repository has been disposed. */
  readonly isDisposed: boolean;

  // -----------------------------------------------------------------------
  // Pack records
  // -----------------------------------------------------------------------

  /**
   * Persist a newly installed extension pack record.
   *
   * Rejects if a pack record with the same extension ID already exists.
   */
  putPackRecord(record: ExtensionPackRecord): Promise<void>;

  /**
   * Update an existing pack record (e.g. after an upgrade).
   *
   * Rejects if no record exists for the given extension ID.
   */
  updatePackRecord(extensionId: string, record: ExtensionPackRecord): Promise<void>;

  /**
   * Retrieve a pack record by extension ID.
   *
   * Returns `null` when no record exists for the given ID.
   */
  getPackRecord(extensionId: string): Promise<ExtensionPackRecord | null>;

  /**
   * Retrieve all installed pack records.
   */
  getAllPackRecords(): Promise<ExtensionPackRecord[]>;

  /**
   * Delete a pack record (used during uninstall).
   *
   * Idempotent — succeeds even if no record exists.
   */
  deletePackRecord(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Enablement state
  // -----------------------------------------------------------------------

  /**
   * Persist enablement state for an extension.
   *
   * Overwrites any existing enablement state for the same extension ID.
   */
  putEnablementState(state: ExtensionEnablementState): Promise<void>;

  /**
   * Retrieve enablement state for an extension.
   *
   * Returns `null` when no state exists (extension not installed).
   */
  getEnablementState(extensionId: string): Promise<ExtensionEnablementState | null>;

  /**
   * Retrieve enablement state for all installed extensions.
   *
   * Returns only extensions that have recorded enablement state.
   */
  getAllEnablementStates(): Promise<ExtensionEnablementState[]>;

  /**
   * Delete enablement state for an extension (used during uninstall).
   *
   * Idempotent.
   */
  deleteEnablementState(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Dev override state
  // -----------------------------------------------------------------------

  /**
   * Persist a dev override preference.
   *
   * Overwrites any existing override for the same extension ID.
   */
  putDevOverride(override: DevOverrideState): Promise<void>;

  /**
   * Retrieve dev override state for an extension.
   *
   * Returns `null` when no override exists.
   */
  getDevOverride(extensionId: string): Promise<DevOverrideState | null>;

  /**
   * Retrieve all dev overrides.
   */
  getAllDevOverrides(): Promise<DevOverrideState[]>;

  /**
   * Delete a dev override (e.g. on revert-to-installed or uninstall).
   *
   * Idempotent.
   */
  deleteDevOverride(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Settings snapshots
  // -----------------------------------------------------------------------

  /**
   * Persist an extension settings snapshot.
   *
   * Overwrites any existing snapshot for the same extension ID.
   */
  putSettingsSnapshot(snapshot: ExtensionSettingsSnapshot): Promise<void>;

  /**
   * Retrieve a settings snapshot for an extension.
   *
   * Returns `null` when no snapshot exists.
   */
  getSettingsSnapshot(extensionId: string): Promise<ExtensionSettingsSnapshot | null>;

  /**
   * Retrieve all settings snapshots.
   */
  getAllSettingsSnapshots(): Promise<ExtensionSettingsSnapshot[]>;

  /**
   * Delete a settings snapshot (used during uninstall).
   *
   * Idempotent.
   */
  deleteSettingsSnapshot(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Lifecycle events (append-only log)
  // -----------------------------------------------------------------------

  /**
   * Append a lifecycle event to the repository.
   *
   * Events are immutable once written.  Each event must have a unique ID.
   */
  appendLifecycleEvent(event: ExtensionLifecycleEvent): Promise<void>;

  /**
   * Query lifecycle events matching the given criteria.
   *
   * Returns events in reverse chronological order (newest first).
   */
  queryLifecycleEvents(query: LifecycleEventQuery): Promise<ExtensionLifecycleEvent[]>;

  /**
   * Retrieve all lifecycle events for a given extension.
   *
   * Convenience wrapper around queryLifecycleEvents.
   */
  getLifecycleEvents(extensionId: string, limit?: number): Promise<ExtensionLifecycleEvent[]>;

  // -----------------------------------------------------------------------
  // Project lock metadata
  // -----------------------------------------------------------------------

  /**
   * Retrieve the full project extension lock.
   *
   * Returns an empty lock when no entries exist.
   */
  getLock(): Promise<ExtensionLock>;

  /**
   * Upsert a lock entry for a specific extension.
   *
   * If an entry already exists for the extension ID, it is overwritten.
   */
  putLockEntry(entry: ExtensionLockEntry): Promise<void>;

  /**
   * Delete a lock entry for an extension (on uninstall).
   *
   * Idempotent.
   */
  deleteLockEntry(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Composite / convenience
  // -----------------------------------------------------------------------

  /**
   * Retrieve the full enablement + override + settings state for all
   * installed extensions in a single query.
   *
   * Used by the loader to build the activation list.
   */
  getFullExtensionState(): Promise<FullExtensionState>;
}

// ---------------------------------------------------------------------------
// Composite state
// ---------------------------------------------------------------------------

/**
 * Aggregated extension state returned by getFullExtensionState().
 *
 * Combines enablement, dev override, and settings snapshots into a
 * single structure for loader consumption.
 */
export interface FullExtensionState {
  /** Enablement states keyed by extension ID. */
  readonly enablement: Record<string, ExtensionEnablementState>;
  /** Dev overrides keyed by extension ID. */
  readonly devOverrides: Record<string, DevOverrideState>;
  /** Settings snapshots keyed by extension ID. */
  readonly settings: Record<string, ExtensionSettingsSnapshot>;
  /** Pack records keyed by extension ID. */
  readonly packs: Record<string, ExtensionPackRecord>;
  /** The current project lock. */
  readonly lock: ExtensionLock;
}

// ---------------------------------------------------------------------------
// Conversion helpers
// ---------------------------------------------------------------------------

/**
 * Convert an InstalledExtensionMetadata + manifest + bundleContentRef
 * into a persisted ExtensionPackRecord.
 */
export function toPackRecord(
  metadata: InstalledExtensionMetadata,
  manifest: ExtensionManifest,
  bundleContentRef: string,
): ExtensionPackRecord {
  return Object.freeze({
    extensionId: metadata.extensionId as string,
    version: metadata.version,
    apiVersion: metadata.apiVersion,
    integrity: metadata.integrity,
    installedAt: metadata.installedAt ?? new Date().toISOString(),
    updatedAt: metadata.installedAt ?? new Date().toISOString(),
    bundleContentRef,
    manifestSnapshot: manifest,
    publisher: metadata.publisher,
    license: metadata.license,
    icon: metadata.icon,
  });
}

/**
 * Extract an ExtensionPackRecord from a full InstalledExtensionPackage.
 */
export function toPackRecordFromPackage(
  pack: InstalledExtensionPackage,
  bundleContentRef: string,
): ExtensionPackRecord {
  return toPackRecord(pack.metadata, pack.manifest, bundleContentRef);
}

/**
 * Create an initial enablement state for a newly installed extension.
 */
export function createEnablementState(
  extensionId: string,
  enabled: boolean = true,
  reason?: string,
): ExtensionEnablementState {
  return Object.freeze({
    extensionId,
    enabled,
    lastToggledAt: new Date().toISOString(),
    toggleReason: reason ?? (enabled ? 'Installed and enabled' : 'Installed but disabled'),
  });
}

/**
 * Create an initial settings snapshot from manifest defaults.
 */
export function createSettingsSnapshot(
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

/**
 * Create a lifecycle event with a generated UUID v4 ID.
 */
export function createLifecycleEvent(
  extensionId: string,
  kind: LifecycleEventKind,
  message: string,
  detail?: Record<string, unknown>,
  diagnostic?: ExtensionDiagnostic,
): ExtensionLifecycleEvent {
  return Object.freeze({
    id: crypto.randomUUID?.() ?? `${extensionId}-${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    extensionId,
    kind,
    timestamp: new Date().toISOString(),
    message,
    ...(detail ? { detail: Object.freeze({ ...detail }) } : {}),
    ...(diagnostic ? { diagnostic } : {}),
  });
}
