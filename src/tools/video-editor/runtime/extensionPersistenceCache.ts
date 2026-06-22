/**
 * Cache-backed ExtensionStateRepository adapter (T4) with settings and
 * proposal facades (T5).
 *
 * Provides a hydrated in-memory cache over an async FullSnapshotStore so
 * that providers (browser-local, Supabase, etc.) can implement a single
 * load-save-delete contract while the cache handles all the CRUD semantics.
 *
 * ## Invariants
 *
 * 1. **Hydrate once** — `initialize()` loads the full snapshot from the
 *    backing store exactly once.  Subsequent calls are no-ops.
 *
 * 2. **Reads from memory** — after successful hydration every read
 *    (getPackRecord, getEnablementState, etc.) is served from the
 *    in-memory cache.  No store round-trips after initialization.
 *
 * 3. **Writes visible immediately** — every write (putPackRecord,
 *    putEnablementState, etc.) mutates the in-memory cache synchronously
 *    before the returned Promise resolves.  Any read performed after the
 *    write's Promise resolves will see the updated value.
 *
 * 4. **Flush asynchronously** — after a write the dirty state is flushed
 *    to the backing store on a microtask boundary.  Flushes are
 *    debounced: multiple writes in the same tick produce a single flush.
 *    The caller does not wait for the flush; write Promises resolve
 *    immediately after the in-memory update.
 *
 * 5. **Diagnostics on flush failures** — if `saveSnapshot` rejects, a
 *    warning-level diagnostic is pushed into the diagnostics array and
 *    the dirty flag is preserved so the next write will retry.
 *
 * 6. **Fail-closed on hydration errors** — if `loadSnapshot` rejects or
 *    the stored JSON cannot be parsed, an error diagnostic is emitted and
 *    the repository enters a failed state.  No partial state is exposed:
 *    every method except `isDisposed` and `dispose()` throws until the
 *    repository is disposed.
 *
 * 7. **Schema version tracking** — every snapshot carries a
 *    `meta.schemaVersion`.  Compatible versions hydrate normally.
 *    Migrations run for older versions.  Unknown future versions fail
 *    closed with diagnostics.
 *
 * 8. **Proposal facades** — proposals are stored in the same hydrated
 *    snapshot alongside settings, enablement, and pack records.  M2
 *    supports create / read / status-update / list only.
 */

import type {
  ExtensionStateRepository,
  ExtensionPackRecord,
  ExtensionEnablementState,
  DevOverrideState,
  ExtensionSettingsSnapshot,
  ExtensionLifecycleEvent,
  ExtensionLockEntry,
  ExtensionLock,
  LifecycleEventQuery,
  FullExtensionState,
} from './extensionStateRepository';
import type {
  ExtensionPersistenceService,
  ExtensionPersistenceCapabilities,
  ExtensionProposal,
  ExtensionPersistenceScope,
  ExtensionProposalStatus,
  ExtensionProposalQuery,
} from '../data/DataProvider';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// FullSnapshotStore
// ---------------------------------------------------------------------------

/**
 * A store that persists the entire extension state as a single serialized
 * snapshot.
 *
 * Used by {@link CachedExtensionStateRepository} to hydrate once at
 * initialization and flush asynchronously after writes.
 *
 * Providers implement this contract instead of the full
 * {@link ExtensionStateRepository} — the cache handles all the CRUD
 * semantics on top of the simpler load-save-delete interface.
 */
export interface FullSnapshotStore {
  /**
   * Load the full serialized snapshot.
   *
   * Returns `null` when no snapshot has ever been persisted (first-run /
   * fresh state).
   */
  loadSnapshot(): Promise<string | null>;

  /**
   * Persist the full serialized snapshot.
   *
   * Overwrites any previously stored snapshot.
   */
  saveSnapshot(serialized: string): Promise<void>;

  /**
   * Delete the snapshot entirely.
   *
   * Used during uninstall of the last extension or explicit cache
   * invalidation.  Idempotent — succeeds even when no snapshot exists.
   */
  deleteSnapshot(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Schema version constants
// ---------------------------------------------------------------------------

/**
 * Current schema version for the full snapshot shape.
 *
 * - Version 0: snapshot without explicit meta; treated as v0 and migrated to
 *   the current version.
 * - Version 1 (current): includes `meta.schemaVersion`, `meta.createdAt`,
 *   `meta.updatedAt`, and per-extension `proposals`.
 *
 * When the schema shape changes, increment this constant and add a migration
 * hook via {@link CachedExtensionStateRepository.registerMigration}.
 */
export const CURRENT_SNAPSHOT_SCHEMA_VERSION = 1;

// ---------------------------------------------------------------------------
// Diagnostic codes
// ---------------------------------------------------------------------------

const DIAG_CODE_HYDRATION_LOAD_FAILED =
  'extension_cache_hydration_load_failed' as const;
const DIAG_CODE_HYDRATION_PARSE_FAILED =
  'extension_cache_hydration_parse_failed' as const;
const DIAG_CODE_FLUSH_FAILED = 'extension_cache_flush_failed' as const;
const DIAG_CODE_FUTURE_SCHEMA_VERSION =
  'extension_cache_future_schema_version' as const;
const DIAG_CODE_MIGRATION_START =
  'extension_cache_migration_start' as const;
const DIAG_CODE_MIGRATION_SUCCESS =
  'extension_cache_migration_success' as const;
const DIAG_CODE_MIGRATION_FAILURE =
  'extension_cache_migration_failure' as const;

// ---------------------------------------------------------------------------
// Migration hook types
// ---------------------------------------------------------------------------

/**
 * A migration hook that transforms a cached state from one schema version
 * to the next.
 *
 * @param state  The state at the earlier version (mutated in-place).
 * @returns The migrated state (typically the same object reference).
 * @throws If migration cannot proceed (fail-closed).
 */
export type SnapshotMigrationHook = (state: CachedState) => CachedState;

// ---------------------------------------------------------------------------
// Internal cached state shape
// ---------------------------------------------------------------------------

/**
 * Metadata carried by every snapshot for schema-version tracking.
 */
interface SnapshotMeta {
  /** The schema version this snapshot was written with. */
  schemaVersion: number;
  /** ISO 8601 timestamp of first snapshot creation. */
  createdAt: string;
  /** ISO 8601 timestamp of last snapshot write. */
  updatedAt: string;
}

interface CachedState {
  /** Snapshot-level metadata. */
  meta: SnapshotMeta;
  packs: Record<string, ExtensionPackRecord>;
  enablement: Record<string, ExtensionEnablementState>;
  overrides: Record<string, DevOverrideState>;
  settings: Record<string, ExtensionSettingsSnapshot>;
  events: ExtensionLifecycleEvent[];
  lock: ExtensionLock;
  /** Proposals keyed by proposal ID (M2 foundation). */
  proposals: Record<string, ExtensionProposal>;
}

function emptyLock(): ExtensionLock {
  return {
    entries: {},
    lastUpdatedAt: new Date().toISOString(),
  };
}

function emptyMeta(): SnapshotMeta {
  const now = new Date().toISOString();
  return {
    schemaVersion: CURRENT_SNAPSHOT_SCHEMA_VERSION,
    createdAt: now,
    updatedAt: now,
  };
}

function emptyState(): CachedState {
  return {
    meta: emptyMeta(),
    packs: {},
    enablement: {},
    overrides: {},
    settings: {},
    events: [],
    lock: emptyLock(),
    proposals: {},
  };
}

function cloneState(state: CachedState): CachedState {
  return {
    meta: { ...state.meta },
    packs: { ...state.packs },
    enablement: { ...state.enablement },
    overrides: { ...state.overrides },
    settings: { ...state.settings },
    events: [...state.events],
    lock: {
      entries: { ...state.lock.entries },
      lastUpdatedAt: state.lock.lastUpdatedAt,
    },
    proposals: { ...state.proposals },
  };
}

// ---------------------------------------------------------------------------
// Snapshot meta helpers
// ---------------------------------------------------------------------------

/**
 * Parse snapshot meta from an unknown value, returning `null` when the
 * value is missing or malformed.
 */
function parseSnapshotMeta(raw: unknown): SnapshotMeta | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== 'object' || Array.isArray(raw)) return null;

  const obj = raw as Record<string, unknown>;
  const schemaVersion =
    typeof obj.schemaVersion === 'number' && Number.isFinite(obj.schemaVersion)
      ? obj.schemaVersion
      : -1;

  // schemaVersion must be a non-negative integer
  if (schemaVersion < 0 || !Number.isInteger(schemaVersion)) return null;

  const now = new Date().toISOString();
  const createdAt =
    typeof obj.createdAt === 'string' && obj.createdAt.length > 0
      ? obj.createdAt
      : now;
  const updatedAt =
    typeof obj.updatedAt === 'string' && obj.updatedAt.length > 0
      ? obj.updatedAt
      : now;

  return { schemaVersion, createdAt, updatedAt };
}

// ---------------------------------------------------------------------------
// CachedExtensionStateRepository
// ---------------------------------------------------------------------------

/**
 * A cache-backed {@link ExtensionStateRepository} adapter.
 *
 * Hydrates once from a {@link FullSnapshotStore} during `initialize()`,
 * then serves all reads from an in-memory cache.  Writes are immediately
 * visible in memory and flushed asynchronously to the backing store.
 *
 * ## Fail-closed behavior
 *
 * If hydration fails (store error or parse error), the repository enters
 * a failed state.  No partial state is exposed: every method except
 * `isDisposed` and `dispose()` throws a descriptive error.  Callers must
 * `dispose()` and create a new instance to retry.
 *
 * ## Usage
 *
 * ```ts
 * const store: FullSnapshotStore = new MyProviderSnapshotStore(scope);
 * const diagnostics: ExtensionDiagnostic[] = [];
 * const repo = new CachedExtensionStateRepository(store, diagnostics);
 * await repo.initialize();
 * // ... use repo ...
 * await repo.dispose();
 * ```
 */
export class CachedExtensionStateRepository
  implements ExtensionStateRepository
{
  private readonly _store: FullSnapshotStore;
  private readonly _diagnostics: ExtensionDiagnostic[];
  private readonly _migrations: Map<number, SnapshotMigrationHook>;
  private _state: CachedState | null = null;
  private _hydrated = false;
  private _hydrationError: Error | null = null;
  private _disposed = false;
  private _dirty = false;
  private _flushScheduled = false;
  private _generation = 0;

  /**
   * @param store       The backing full-snapshot store.
   * @param diagnostics An output array for diagnostics (mutated in-place
   *                    on hydration parse errors and flush failures).
   */
  constructor(
    store: FullSnapshotStore,
    diagnostics: ExtensionDiagnostic[] = [],
  ) {
    this._store = store;
    this._diagnostics = diagnostics;
    this._migrations = new Map();
  }

  // -------------------------------------------------------------------
  // Migration registration (T5)
  // -------------------------------------------------------------------

  /**
   * Register a migration hook for upgrading from one schema version to the
   * next.
   *
   * Hooks are stored keyed by the *target* version (the version produced
   * after the migration runs).  For example, a hook that upgrades v1 → v2
   * is registered with `registerMigration(2, hook)`.
   *
   * Migrations are applied in ascending version order during hydration
   * when the loaded snapshot has a lower schema version than the current
   * code.
   *
   * @param targetVersion  The schema version produced by this migration.
   * @param hook           The migration function.
   */
  registerMigration(
    targetVersion: number,
    hook: SnapshotMigrationHook,
  ): void {
    if (targetVersion <= 0) {
      throw new Error(
        `Migration target version must be > 0, got ${targetVersion}`,
      );
    }
    if (targetVersion > CURRENT_SNAPSHOT_SCHEMA_VERSION) {
      throw new Error(
        `Migration target version ${targetVersion} exceeds current schema version ${CURRENT_SNAPSHOT_SCHEMA_VERSION}`,
      );
    }
    this._migrations.set(targetVersion, hook);
  }

  // -------------------------------------------------------------------
  // Repository lifecycle
  // -------------------------------------------------------------------

  async initialize(): Promise<void> {
    if (this._disposed) {
      throw new Error('Repository is disposed');
    }
    if (this._hydrated) {
      return; // Idempotent
    }

    try {
      const raw = await this._store.loadSnapshot();

      if (raw !== null && raw !== undefined) {
        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch (parseError: unknown) {
          const message =
            parseError instanceof Error
              ? parseError.message
              : String(parseError);
          this._diagnostics.push({
            severity: 'error',
            code: DIAG_CODE_HYDRATION_PARSE_FAILED,
            message: `Failed to parse cached extension state snapshot: ${message}`,
            milestone: 'm2',
          });
          this._hydrationError = new Error(
            `Hydration failed: unable to parse snapshot JSON — ${message}`,
          );
          // Fail closed — _state remains null, _hydrated remains false
          return;
        }

        // Minimal shape validation: must be a non-null object
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          this._diagnostics.push({
            severity: 'error',
            code: DIAG_CODE_HYDRATION_PARSE_FAILED,
            message:
              'Failed to parse cached extension state snapshot: root value is not an object',
            milestone: 'm2',
          });
          this._hydrationError = new Error(
            'Hydration failed: snapshot root is not an object',
          );
          return;
        }

        const obj = parsed as Record<string, unknown>;

        // Parse meta (schema version tracking)
        const meta = parseSnapshotMeta(obj.meta);

        // --- Version-aware hydration ---
        const storedVersion = meta?.schemaVersion ?? 0;

        if (storedVersion > CURRENT_SNAPSHOT_SCHEMA_VERSION) {
          // Unknown future version — fail closed
          this._diagnostics.push({
            severity: 'error',
            code: DIAG_CODE_FUTURE_SCHEMA_VERSION,
            message:
              `Snapshot schema version ${storedVersion} is newer than ` +
              `current version ${CURRENT_SNAPSHOT_SCHEMA_VERSION}. ` +
              'This version of the editor cannot read this snapshot.',
            milestone: 'm2',
          });
          this._hydrationError = new Error(
            `Hydration failed: snapshot schema version ${storedVersion} ` +
            `exceeds current version ${CURRENT_SNAPSHOT_SCHEMA_VERSION}`,
          );
          // Fail closed
          return;
        }

        // Build base state from the stored fields with fallback-to-empty
        this._state = {
          meta: meta ?? emptyMeta(),
          packs:
            obj.packs !== null && typeof obj.packs === 'object' && !Array.isArray(obj.packs)
              ? (obj.packs as Record<string, ExtensionPackRecord>)
              : {},
          enablement:
            obj.enablement !== null &&
            typeof obj.enablement === 'object' &&
            !Array.isArray(obj.enablement)
              ? (obj.enablement as Record<string, ExtensionEnablementState>)
              : {},
          overrides:
            obj.overrides !== null &&
            typeof obj.overrides === 'object' &&
            !Array.isArray(obj.overrides)
              ? (obj.overrides as Record<string, DevOverrideState>)
              : {},
          settings:
            obj.settings !== null &&
            typeof obj.settings === 'object' &&
            !Array.isArray(obj.settings)
              ? (obj.settings as Record<string, ExtensionSettingsSnapshot>)
              : {},
          events: Array.isArray(obj.events)
            ? (obj.events as ExtensionLifecycleEvent[])
            : [],
          lock:
            obj.lock !== null &&
            typeof obj.lock === 'object' &&
            !Array.isArray(obj.lock) &&
            typeof (obj.lock as Record<string, unknown>).entries === 'object'
              ? (obj.lock as ExtensionLock)
              : emptyLock(),
          proposals:
            obj.proposals !== null &&
            typeof obj.proposals === 'object' &&
            !Array.isArray(obj.proposals)
              ? (obj.proposals as Record<string, ExtensionProposal>)
              : {},
        };

        // --- Run pending migrations (storedVersion → CURRENT) ---
        if (storedVersion < CURRENT_SNAPSHOT_SCHEMA_VERSION) {
          try {
            this.runMigrations(storedVersion);
          } catch (migrationError: unknown) {
            const message =
              migrationError instanceof Error
                ? migrationError.message
                : String(migrationError);
            this._diagnostics.push({
              severity: 'error',
              code: DIAG_CODE_MIGRATION_FAILURE,
              message: `Migration from v${storedVersion} to v${CURRENT_SNAPSHOT_SCHEMA_VERSION} failed: ${message}`,
              milestone: 'm2',
            });
            this._hydrationError =
              migrationError instanceof Error
                ? migrationError
                : new Error(`Migration failed: ${message}`);
            this._state = null;
            // Fail closed
            return;
          }
        }

        // Ensure meta reflects current version after migration
        this._state.meta.schemaVersion = CURRENT_SNAPSHOT_SCHEMA_VERSION;
      } else {
        // No snapshot exists — start with empty state
        this._state = emptyState();
      }

      this._hydrated = true;
      this._hydrationError = null;
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : String(error);
      this._diagnostics.push({
        severity: 'error',
        code: DIAG_CODE_HYDRATION_LOAD_FAILED,
        message: `Failed to load extension state snapshot from store: ${message}`,
        milestone: 'm2',
      });
      this._hydrationError =
        error instanceof Error
          ? error
          : new Error(`Hydration failed: ${message}`);
      // Fail closed — _state remains null, _hydrated remains false
    }
  }

  /**
   * Run all registered migrations in ascending version order from
   * `fromVersion` (exclusive) to `CURRENT_SNAPSHOT_SCHEMA_VERSION`
   * (inclusive).
   *
   * Emits diagnostics for migration start/success.  On failure the
   * error propagates to `initialize()` which emits a failure diagnostic
   * and enters fail-closed state.
   */
  private runMigrations(fromVersion: number): void {
    for (
      let target = fromVersion + 1;
      target <= CURRENT_SNAPSHOT_SCHEMA_VERSION;
      target++
    ) {
      const hook = this._migrations.get(target);
      if (!hook) {
        // No migration registered for this step — skip.  The state was
        // already coerced with fallback-to-empty semantics.
        continue;
      }

      this._diagnostics.push({
        severity: 'info',
        code: DIAG_CODE_MIGRATION_START,
        message: `Running migration to schema version ${target}`,
        milestone: 'm2',
      });

      hook(this._state!);

      // Update meta version after each successful step
      this._state!.meta.schemaVersion = target;

      this._diagnostics.push({
        severity: 'info',
        code: DIAG_CODE_MIGRATION_SUCCESS,
        message: `Migration to schema version ${target} completed`,
        milestone: 'm2',
      });
    }
  }

  async dispose(): Promise<void> {
    this._disposed = true;

    // Best-effort final flush — do not emit diagnostics on dispose
    if (this._dirty && this._hydrated && this._state !== null) {
      try {
        const serialized = JSON.stringify(this._state);
        await this._store.saveSnapshot(serialized);
      } catch {
        // Swallow — dispose must complete
      }
    }

    this._state = null;
    this._hydrated = false;
    this._hydrationError = null;
    this._dirty = false;
    this._flushScheduled = false;
  }

  get isDisposed(): boolean {
    return this._disposed;
  }

  // -------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------

  /**
   * Assert the repository is hydrated and return the in-memory state.
   *
   * Throws with a descriptive message when disposed, uninitialized, or
   * in a fail-closed hydration-error state.
   */
  private requireHydrated(): CachedState {
    if (this._disposed) {
      throw new Error('Repository is disposed');
    }
    if (this._hydrationError) {
      throw new Error(
        `Repository failed to hydrate: ${this._hydrationError.message}`,
      );
    }
    if (!this._hydrated || this._state === null) {
      throw new Error('Repository not initialized — call initialize() first');
    }
    return this._state;
  }

  /**
   * Mark the cache dirty and schedule an asynchronous flush.
   *
   * Each call bumps a generation counter so that in-flight flushes can
   * detect concurrent writes and reschedule themselves.  Multiple writes
   * in the same synchronous tick produce a single scheduled flush.
   */
  private markDirty(): void {
    this._dirty = true;
    this._generation++;
    // Update meta.updatedAt when we have a loaded state
    if (this._state) {
      this._state.meta.updatedAt = new Date().toISOString();
    }
    this.scheduleFlush();
  }

  /**
   * Schedule a flush on the next microtask boundary.
   *
   * Debounces: if a flush is already scheduled (but not yet executing)
   * this is a no-op.  The generation counter ensures that writes
   * occurring during an in-flight flush are not lost.
   */
  private scheduleFlush(): void {
    if (this._flushScheduled || this._disposed) {
      return;
    }
    this._flushScheduled = true;
    // Schedule on microtask boundary so writes in the same tick are batched
    Promise.resolve().then(() => this.performFlush());
  }

  /**
   * Execute a single flush cycle, then reschedule if writes arrived
   * during the flush.
   *
   * Serializes the current in-memory state and calls `saveSnapshot` on
   * the backing store.  On failure a warning diagnostic is emitted and
   * the dirty flag is preserved so the next write will retry.
   *
   * After a successful save the dirty flag is cleared only when the
   * generation counter has not changed since the snapshot was taken
   * (i.e. no writes occurred during the async `saveSnapshot` call).
   */
  private async performFlush(): Promise<void> {
    this._flushScheduled = false;

    if (!this._dirty || !this._hydrated || this._state === null || this._disposed) {
      return;
    }

    // Capture generation at snapshot time
    const genAtStart = this._generation;

    // Snapshot the current state so we don't race with concurrent writes
    const snapshot = cloneState(this._state);

    try {
      const serialized = JSON.stringify(snapshot);
      await this._store.saveSnapshot(serialized);

      // Only clear dirty if no writes arrived during the async save
      if (this._generation === genAtStart) {
        this._dirty = false;
      }
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : String(error);
      this._diagnostics.push({
        severity: 'warning',
        code: DIAG_CODE_FLUSH_FAILED,
        message: `Failed to flush extension state cache: ${message}`,
        milestone: 'm2',
      });
      // Keep dirty flag set so next write will retry
    }

    // If writes arrived during our flush, schedule another one
    if (this._dirty && !this._disposed) {
      this.scheduleFlush();
    }
  }

  // -------------------------------------------------------------------
  // Pack records
  // -------------------------------------------------------------------

  async putPackRecord(record: ExtensionPackRecord): Promise<void> {
    const state = this.requireHydrated();
    if (state.packs[record.extensionId]) {
      throw new Error(
        `Pack record already exists for extension "${record.extensionId}"`,
      );
    }
    state.packs[record.extensionId] = { ...record };
    this.markDirty();
  }

  async updatePackRecord(
    extensionId: string,
    record: ExtensionPackRecord,
  ): Promise<void> {
    const state = this.requireHydrated();
    if (!state.packs[extensionId]) {
      throw new Error(
        `No pack record exists for extension "${extensionId}"`,
      );
    }
    state.packs[extensionId] = { ...record };
    this.markDirty();
  }

  async getPackRecord(
    extensionId: string,
  ): Promise<ExtensionPackRecord | null> {
    const state = this.requireHydrated();
    return state.packs[extensionId] ?? null;
  }

  async getAllPackRecords(): Promise<ExtensionPackRecord[]> {
    const state = this.requireHydrated();
    return Object.values(state.packs);
  }

  async deletePackRecord(extensionId: string): Promise<void> {
    const state = this.requireHydrated();
    delete state.packs[extensionId];
    this.markDirty();
  }

  // -------------------------------------------------------------------
  // Enablement state
  // -------------------------------------------------------------------

  async putEnablementState(state: ExtensionEnablementState): Promise<void> {
    const cache = this.requireHydrated();
    cache.enablement[state.extensionId] = { ...state };
    this.markDirty();
  }

  async getEnablementState(
    extensionId: string,
  ): Promise<ExtensionEnablementState | null> {
    const cache = this.requireHydrated();
    return cache.enablement[extensionId] ?? null;
  }

  async getAllEnablementStates(): Promise<ExtensionEnablementState[]> {
    const cache = this.requireHydrated();
    return Object.values(cache.enablement);
  }

  async deleteEnablementState(extensionId: string): Promise<void> {
    const cache = this.requireHydrated();
    delete cache.enablement[extensionId];
    this.markDirty();
  }

  // -------------------------------------------------------------------
  // Dev override state
  // -------------------------------------------------------------------

  async putDevOverride(override: DevOverrideState): Promise<void> {
    const cache = this.requireHydrated();
    cache.overrides[override.extensionId] = { ...override };
    this.markDirty();
  }

  async getDevOverride(
    extensionId: string,
  ): Promise<DevOverrideState | null> {
    const cache = this.requireHydrated();
    return cache.overrides[extensionId] ?? null;
  }

  async getAllDevOverrides(): Promise<DevOverrideState[]> {
    const cache = this.requireHydrated();
    return Object.values(cache.overrides);
  }

  async deleteDevOverride(extensionId: string): Promise<void> {
    const cache = this.requireHydrated();
    delete cache.overrides[extensionId];
    this.markDirty();
  }

  // -------------------------------------------------------------------
  // Settings snapshots
  // -------------------------------------------------------------------

  async putSettingsSnapshot(
    snapshot: ExtensionSettingsSnapshot,
  ): Promise<void> {
    const cache = this.requireHydrated();
    cache.settings[snapshot.extensionId] = { ...snapshot };
    this.markDirty();
  }

  async getSettingsSnapshot(
    extensionId: string,
  ): Promise<ExtensionSettingsSnapshot | null> {
    const cache = this.requireHydrated();
    return cache.settings[extensionId] ?? null;
  }

  async getAllSettingsSnapshots(): Promise<ExtensionSettingsSnapshot[]> {
    const cache = this.requireHydrated();
    return Object.values(cache.settings);
  }

  async deleteSettingsSnapshot(extensionId: string): Promise<void> {
    const cache = this.requireHydrated();
    delete cache.settings[extensionId];
    this.markDirty();
  }

  // -------------------------------------------------------------------
  // Lifecycle events (append-only log)
  // -------------------------------------------------------------------

  async appendLifecycleEvent(event: ExtensionLifecycleEvent): Promise<void> {
    const cache = this.requireHydrated();

    // Reject duplicate event IDs
    if (cache.events.some((e) => e.id === event.id)) {
      throw new Error(
        `Lifecycle event with ID "${event.id}" already exists`,
      );
    }

    cache.events.push({ ...event });
    this.markDirty();
  }

  async queryLifecycleEvents(
    query: LifecycleEventQuery,
  ): Promise<ExtensionLifecycleEvent[]> {
    const cache = this.requireHydrated();
    let results = [...cache.events];

    if (query.extensionId) {
      results = results.filter((e) => e.extensionId === query.extensionId);
    }
    if (query.kinds && query.kinds.length > 0) {
      results = results.filter((e) => query.kinds!.includes(e.kind));
    }
    if (query.since) {
      results = results.filter((e) => e.timestamp >= query.since!);
    }
    if (query.until) {
      results = results.filter((e) => e.timestamp <= query.until!);
    }

    // Sort newest first
    results.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    const limit = query.limit ?? 100;
    if (results.length > limit) {
      results = results.slice(0, limit);
    }

    return results;
  }

  async getLifecycleEvents(
    extensionId: string,
    limit?: number,
  ): Promise<ExtensionLifecycleEvent[]> {
    return this.queryLifecycleEvents({ extensionId, limit });
  }

  // -------------------------------------------------------------------
  // Project lock metadata
  // -------------------------------------------------------------------

  async getLock(): Promise<ExtensionLock> {
    const cache = this.requireHydrated();
    return {
      entries: { ...cache.lock.entries },
      lastUpdatedAt: cache.lock.lastUpdatedAt,
    };
  }

  async putLockEntry(entry: ExtensionLockEntry): Promise<void> {
    const cache = this.requireHydrated();
    const entries = { ...cache.lock.entries, [entry.extensionId]: entry };
    cache.lock = {
      entries,
      lastUpdatedAt: new Date().toISOString(),
    };
    this.markDirty();
  }

  async deleteLockEntry(extensionId: string): Promise<void> {
    const cache = this.requireHydrated();
    const entries = { ...cache.lock.entries };
    delete entries[extensionId];
    cache.lock = {
      entries,
      lastUpdatedAt: new Date().toISOString(),
    };
    this.markDirty();
  }

  // -------------------------------------------------------------------
  // Proposals (M2 foundation, T5)
  // -------------------------------------------------------------------

  /**
   * Create a new proposal in the cached state.
   *
   * @returns The unique ID of the created proposal.
   */
  async createProposal(
    proposal: Omit<ExtensionProposal, 'id' | 'createdAt' | 'updatedAt'>,
  ): Promise<string> {
    const cache = this.requireHydrated();

    const id =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `${proposal.extensionId}-proposal-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

    const now = new Date().toISOString();
    const record: ExtensionProposal = {
      id,
      extensionId: proposal.extensionId,
      status: proposal.status,
      payload: { ...proposal.payload },
      createdAt: now,
      updatedAt: now,
      ...(proposal.label !== undefined ? { label: proposal.label } : {}),
      ...(proposal.baseVersion !== undefined ? { baseVersion: proposal.baseVersion } : {}),
      ...(proposal.expiresAt !== undefined ? { expiresAt: proposal.expiresAt } : {}),
      ...(proposal.acceptedAt !== undefined ? { acceptedAt: proposal.acceptedAt } : {}),
      ...(proposal.rejectedAt !== undefined ? { rejectedAt: proposal.rejectedAt } : {}),
    };

    cache.proposals[id] = record;
    this.markDirty();
    return id;
  }

  /**
   * Retrieve a proposal by ID.
   *
   * @returns The proposal, or `null` if not found.
   */
  async getProposal(proposalId: string): Promise<ExtensionProposal | null> {
    const cache = this.requireHydrated();
    return cache.proposals[proposalId] ?? null;
  }

  /**
   * Update the status of an existing proposal.
   *
   * Sets `updatedAt` to the current timestamp.  Rejects if the proposal
   * does not exist.
   */
  async updateProposalStatus(
    proposalId: string,
    status: ExtensionProposalStatus,
    detail?: Record<string, unknown>,
  ): Promise<void> {
    const cache = this.requireHydrated();
    const existing = cache.proposals[proposalId];
    if (!existing) {
      throw new Error(`Proposal "${proposalId}" not found`);
    }

    cache.proposals[proposalId] = {
      ...existing,
      status,
      ...(detail !== undefined ? { detail } : {}),
      updatedAt: new Date().toISOString(),
    };
    this.markDirty();
  }

  /**
   * List proposals matching the given query criteria.
   *
   * Returns proposals in reverse chronological order (newest first).
   */
  async listProposals(
    query?: ExtensionProposalQuery,
  ): Promise<ExtensionProposal[]> {
    const cache = this.requireHydrated();
    let results = Object.values(cache.proposals);

    if (query?.extensionId) {
      results = results.filter((p) => p.extensionId === query.extensionId);
    }
    if (query?.statuses && query.statuses.length > 0) {
      results = results.filter((p) => query.statuses!.includes(p.status));
    }

    // Sort newest first
    results.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

    const limit = query?.limit ?? 50;
    if (results.length > limit) {
      results = results.slice(0, limit);
    }

    return results;
  }

  // -------------------------------------------------------------------
  // Composite / convenience
  // -------------------------------------------------------------------

  async getFullExtensionState(): Promise<FullExtensionState> {
    const cache = this.requireHydrated();
    return {
      enablement: { ...cache.enablement },
      devOverrides: { ...cache.overrides },
      settings: { ...cache.settings },
      packs: { ...cache.packs },
      lock: {
        entries: { ...cache.lock.entries },
        lastUpdatedAt: cache.lock.lastUpdatedAt,
      },
    };
  }
}

/**
 * Create a cache-backed extension state repository.
 *
 * @param store       The backing full-snapshot store.
 * @param diagnostics An output array for diagnostics.
 */
export function createCachedExtensionStateRepository(
  store: FullSnapshotStore,
  diagnostics?: ExtensionDiagnostic[],
): CachedExtensionStateRepository {
  return new CachedExtensionStateRepository(store, diagnostics);
}

// ---------------------------------------------------------------------------
// CachedExtensionPersistenceService (T5)
// ---------------------------------------------------------------------------

/**
 * A cache-backed {@link ExtensionPersistenceService} that wraps a
 * {@link CachedExtensionStateRepository} and adds proposal facades,
 * all backed by the same hydrated snapshot.
 *
 * ## Lifecycle
 *
 * - `initialize()` delegates to the underlying repository's `initialize()`.
 * - `dispose()` delegates to the underlying repository's `dispose()`.
 * - After disposal, all methods reject.
 *
 * ## Capabilities
 *
 * Advertises `state: true`, `settings: true`, and `proposals: true`
 * when the underlying repository is available.  The actual capability
 * truth is determined by the shared conformance suite per the
 * factory-plus-conformance model (see {@link DataProvider}).
 */
export class CachedExtensionPersistenceService
  implements ExtensionPersistenceService
{
  private readonly _repository: CachedExtensionStateRepository;
  readonly scope: ExtensionPersistenceScope;

  constructor(
    repository: CachedExtensionStateRepository,
    scope: ExtensionPersistenceScope = { userId: 'unknown', timelineId: 'unknown' },
  ) {
    this._repository = repository;
    this.scope = scope;
  }

  // -- ExtensionPersistenceService ---------------------------------------

  get capabilities(): ExtensionPersistenceCapabilities {
    return {
      state: true,
      settings: true,
      proposals: true,
    };
  }

  get stateRepository(): ExtensionStateRepository {
    return this._repository;
  }

  get repository(): ExtensionStateRepository {
    return this._repository;
  }

  // -- Lifecycle ----------------------------------------------------------

  async initialize(): Promise<void> {
    await this._repository.initialize();
  }

  async dispose(): Promise<void> {
    await this._repository.dispose();
  }

  get isDisposed(): boolean {
    return this._repository.isDisposed;
  }

  // -- Settings -----------------------------------------------------------

  async putSettings(snapshot: ExtensionSettingsSnapshot): Promise<void> {
    return this._repository.putSettingsSnapshot(snapshot);
  }

  async getSettings(extensionId: string): Promise<ExtensionSettingsSnapshot | null> {
    return this._repository.getSettingsSnapshot(extensionId);
  }

  async getAllSettings(): Promise<ExtensionSettingsSnapshot[]> {
    return this._repository.getAllSettingsSnapshots();
  }

  async deleteSettings(extensionId: string): Promise<void> {
    return this._repository.deleteSettingsSnapshot(extensionId);
  }

  // -- Proposals ----------------------------------------------------------

  async createProposal(
    proposal: Omit<ExtensionProposal, 'id' | 'createdAt' | 'updatedAt'>,
  ): Promise<string> {
    return this._repository.createProposal(proposal);
  }

  async getProposal(proposalId: string): Promise<ExtensionProposal | null> {
    return this._repository.getProposal(proposalId);
  }

  async updateProposalStatus(
    proposalId: string,
    status: ExtensionProposalStatus,
    detail?: Record<string, unknown>,
  ): Promise<void> {
    return this._repository.updateProposalStatus(proposalId, status, detail);
  }

  async queryProposals(
    query?: ExtensionProposalQuery,
  ): Promise<ExtensionProposal[]> {
    return this._repository.listProposals(query);
  }

  async listProposals(
    query?: ExtensionProposalQuery,
  ): Promise<ExtensionProposal[]> {
    return this._repository.listProposals(query);
  }
}

/**
 * Create a cache-backed extension persistence service.
 *
 * @param store       The backing full-snapshot store.
 * @param diagnostics An output array for diagnostics.
 */
export function createCachedExtensionPersistenceService(
  store: FullSnapshotStore,
  diagnostics?: ExtensionDiagnostic[],
  scope?: ExtensionPersistenceScope,
): CachedExtensionPersistenceService {
  const repository = new CachedExtensionStateRepository(store, diagnostics);
  return new CachedExtensionPersistenceService(repository, scope);
}
