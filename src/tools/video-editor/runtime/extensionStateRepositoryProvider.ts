/**
 * Provider-backed implementation of ExtensionStateRepository (T7).
 *
 * Stores extension metadata (enablement, dev overrides, settings snapshots,
 * lifecycle events, lock entries) in a provider-backed store using reserved
 * tool-settings keys. Bundle content bytes are NOT stored in provider-backed
 * state per SD2 — they remain in browser-local IndexedDB.
 *
 * Reserved keys:
 *   reigh.ext.state.enablement  — Record<string, ExtensionEnablementState>
 *   reigh.ext.state.overrides   — Record<string, DevOverrideState>
 *   reigh.ext.state.settings   — Record<string, ExtensionSettingsSnapshot>
 *   reigh.ext.state.events     — ExtensionLifecycleEvent[] (append-only)
 *   reigh.ext.state.lock       — ExtensionLock
 *   reigh.ext.state.packs      — Record<string, ExtensionPackRecord>
 *
 * This adapter uses a simple provider interface that supports get/set/delete
 * for string-keyed JSON state. It is designed to work with any provider that
 * exposes a key-value storage API (localStorage, Supabase tool-settings, etc.).
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

// ---------------------------------------------------------------------------
// Provider-backed storage interface (subset of tool-settings)
// ---------------------------------------------------------------------------

/**
 * Minimal provider-backed storage interface.
 *
 * Concrete implementations may wrap localStorage (for testing) or the
 * Supabase tool-settings service (for production).
 */
export interface ProviderBackedStore {
  /** Retrieve a value by key. Returns null when not found. */
  get(key: string): Promise<string | null>;
  /** Store a value under a key. Overwrites any existing value. */
  set(key: string, value: string): Promise<void>;
  /** Delete a value by key. Idempotent. */
  delete(key: string): Promise<void>;
}

// ---------------------------------------------------------------------------
// Reserved key constants
// ---------------------------------------------------------------------------

const KEY_ENABLEMENT = 'reigh.ext.state.enablement';
const KEY_OVERRIDES = 'reigh.ext.state.overrides';
const KEY_SETTINGS = 'reigh.ext.state.settings';
const KEY_EVENTS = 'reigh.ext.state.events';
const KEY_LOCK = 'reigh.ext.state.lock';
const KEY_PACKS = 'reigh.ext.state.packs';

// ---------------------------------------------------------------------------
// In-memory fallback store (for testing / no-provider scenarios)
// ---------------------------------------------------------------------------

/**
 * An in-memory implementation of ProviderBackedStore for testing.
 */
export class InMemoryProviderStore implements ProviderBackedStore {
  private _store = new Map<string, string>();

  async get(key: string): Promise<string | null> {
    return this._store.get(key) ?? null;
  }

  async set(key: string, value: string): Promise<void> {
    this._store.set(key, value);
  }

  async delete(key: string): Promise<void> {
    this._store.delete(key);
  }

  /** Expose the raw store for test assertions. */
  get raw(): ReadonlyMap<string, string> {
    return this._store;
  }
}

// ---------------------------------------------------------------------------
// localStorage-backed store (for direct local extensions)
// ---------------------------------------------------------------------------

/**
 * A localStorage-backed implementation of ProviderBackedStore.
 */
export class LocalStorageProviderStore implements ProviderBackedStore {
  async get(key: string): Promise<string | null> {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  async set(key: string, value: string): Promise<void> {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Quota exceeded or unavailable — silently no-op
    }
  }

  async delete(key: string): Promise<void> {
    try {
      localStorage.removeItem(key);
    } catch {
      // localStorage unavailable — silently no-op
    }
  }
}

// ---------------------------------------------------------------------------
// JSON helpers
// ---------------------------------------------------------------------------

function safeJsonParse<T>(raw: string | null, fallback: T): T {
  if (raw === null || raw === undefined) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------------
// Provider-backed repository implementation
// ---------------------------------------------------------------------------

export class ProviderBackedExtensionStateRepository implements ExtensionStateRepository {
  private _store: ProviderBackedStore;
  private _disposed = false;

  constructor(store: ProviderBackedStore) {
    this._store = store;
  }

  // ---- lifecycle ----------------------------------------------------------

  async initialize(): Promise<void> {
    if (this._disposed) {
      throw new Error('Repository is disposed');
    }
    // Provider-backed store is always ready — no explicit init needed
  }

  async dispose(): Promise<void> {
    this._disposed = true;
  }

  get isDisposed(): boolean {
    return this._disposed;
  }

  private requireStore(): ProviderBackedStore {
    if (this._disposed) throw new Error('Repository is disposed');
    return this._store;
  }

  // ---- pack records -------------------------------------------------------

  async putPackRecord(record: ExtensionPackRecord): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_PACKS);
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(raw, {});

    if (packs[record.extensionId]) {
      throw new Error(`Pack record already exists for extension "${record.extensionId}"`);
    }

    packs[record.extensionId] = record;
    await store.set(KEY_PACKS, JSON.stringify(packs));
  }

  async updatePackRecord(extensionId: string, record: ExtensionPackRecord): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_PACKS);
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(raw, {});

    if (!packs[extensionId]) {
      throw new Error(`No pack record exists for extension "${extensionId}"`);
    }

    packs[extensionId] = record;
    await store.set(KEY_PACKS, JSON.stringify(packs));
  }

  async getPackRecord(extensionId: string): Promise<ExtensionPackRecord | null> {
    const store = this.requireStore();
    const raw = await store.get(KEY_PACKS);
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(raw, {});
    return packs[extensionId] ?? null;
  }

  async getAllPackRecords(): Promise<ExtensionPackRecord[]> {
    const store = this.requireStore();
    const raw = await store.get(KEY_PACKS);
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(raw, {});
    return Object.values(packs);
  }

  async deletePackRecord(extensionId: string): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_PACKS);
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(raw, {});
    delete packs[extensionId];
    await store.set(KEY_PACKS, JSON.stringify(packs));
  }

  // ---- enablement state ---------------------------------------------------

  async putEnablementState(state: ExtensionEnablementState): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_ENABLEMENT);
    const states = safeJsonParse<Record<string, ExtensionEnablementState>>(raw, {});
    states[state.extensionId] = state;
    await store.set(KEY_ENABLEMENT, JSON.stringify(states));
  }

  async getEnablementState(extensionId: string): Promise<ExtensionEnablementState | null> {
    const store = this.requireStore();
    const raw = await store.get(KEY_ENABLEMENT);
    const states = safeJsonParse<Record<string, ExtensionEnablementState>>(raw, {});
    return states[extensionId] ?? null;
  }

  async getAllEnablementStates(): Promise<ExtensionEnablementState[]> {
    const store = this.requireStore();
    const raw = await store.get(KEY_ENABLEMENT);
    const states = safeJsonParse<Record<string, ExtensionEnablementState>>(raw, {});
    return Object.values(states);
  }

  async deleteEnablementState(extensionId: string): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_ENABLEMENT);
    const states = safeJsonParse<Record<string, ExtensionEnablementState>>(raw, {});
    delete states[extensionId];
    await store.set(KEY_ENABLEMENT, JSON.stringify(states));
  }

  // ---- dev overrides ------------------------------------------------------

  async putDevOverride(override: DevOverrideState): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_OVERRIDES);
    const overrides = safeJsonParse<Record<string, DevOverrideState>>(raw, {});
    overrides[override.extensionId] = override;
    await store.set(KEY_OVERRIDES, JSON.stringify(overrides));
  }

  async getDevOverride(extensionId: string): Promise<DevOverrideState | null> {
    const store = this.requireStore();
    const raw = await store.get(KEY_OVERRIDES);
    const overrides = safeJsonParse<Record<string, DevOverrideState>>(raw, {});
    return overrides[extensionId] ?? null;
  }

  async getAllDevOverrides(): Promise<DevOverrideState[]> {
    const store = this.requireStore();
    const raw = await store.get(KEY_OVERRIDES);
    const overrides = safeJsonParse<Record<string, DevOverrideState>>(raw, {});
    return Object.values(overrides);
  }

  async deleteDevOverride(extensionId: string): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_OVERRIDES);
    const overrides = safeJsonParse<Record<string, DevOverrideState>>(raw, {});
    delete overrides[extensionId];
    await store.set(KEY_OVERRIDES, JSON.stringify(overrides));
  }

  // ---- settings snapshots -------------------------------------------------

  async putSettingsSnapshot(snapshot: ExtensionSettingsSnapshot): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_SETTINGS);
    const settings = safeJsonParse<Record<string, ExtensionSettingsSnapshot>>(raw, {});
    settings[snapshot.extensionId] = snapshot;
    await store.set(KEY_SETTINGS, JSON.stringify(settings));
  }

  async getSettingsSnapshot(extensionId: string): Promise<ExtensionSettingsSnapshot | null> {
    const store = this.requireStore();
    const raw = await store.get(KEY_SETTINGS);
    const settings = safeJsonParse<Record<string, ExtensionSettingsSnapshot>>(raw, {});
    return settings[extensionId] ?? null;
  }

  async getAllSettingsSnapshots(): Promise<ExtensionSettingsSnapshot[]> {
    const store = this.requireStore();
    const raw = await store.get(KEY_SETTINGS);
    const settings = safeJsonParse<Record<string, ExtensionSettingsSnapshot>>(raw, {});
    return Object.values(settings);
  }

  async deleteSettingsSnapshot(extensionId: string): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_SETTINGS);
    const settings = safeJsonParse<Record<string, ExtensionSettingsSnapshot>>(raw, {});
    delete settings[extensionId];
    await store.set(KEY_SETTINGS, JSON.stringify(settings));
  }

  // ---- lifecycle events ---------------------------------------------------

  async appendLifecycleEvent(event: ExtensionLifecycleEvent): Promise<void> {
    const store = this.requireStore();
    const raw = await store.get(KEY_EVENTS);
    const events = safeJsonParse<ExtensionLifecycleEvent[]>(raw, []);

    // Reject duplicate IDs
    if (events.some((e) => e.id === event.id)) {
      throw new Error(`Lifecycle event with ID "${event.id}" already exists`);
    }

    events.push(event);
    await store.set(KEY_EVENTS, JSON.stringify(events));
  }

  async queryLifecycleEvents(query: LifecycleEventQuery): Promise<ExtensionLifecycleEvent[]> {
    const store = this.requireStore();
    const raw = await store.get(KEY_EVENTS);
    let all = safeJsonParse<ExtensionLifecycleEvent[]>(raw, []);

    // Filter in-memory
    if (query.extensionId) {
      all = all.filter((e) => e.extensionId === query.extensionId);
    }
    if (query.kinds && query.kinds.length > 0) {
      all = all.filter((e) => query.kinds!.includes(e.kind));
    }
    if (query.since) {
      all = all.filter((e) => e.timestamp >= query.since!);
    }
    if (query.until) {
      all = all.filter((e) => e.timestamp <= query.until!);
    }

    // Sort newest first
    all.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    const limit = query.limit ?? 100;
    if (all.length > limit) {
      all = all.slice(0, limit);
    }

    return all;
  }

  async getLifecycleEvents(extensionId: string, limit?: number): Promise<ExtensionLifecycleEvent[]> {
    return this.queryLifecycleEvents({ extensionId, limit });
  }

  // ---- project lock metadata ----------------------------------------------

  async getLock(): Promise<ExtensionLock> {
    const store = this.requireStore();
    const raw = await store.get(KEY_LOCK);
    const lock = safeJsonParse<ExtensionLock>(raw, {
      entries: {},
      lastUpdatedAt: new Date().toISOString(),
    });
    return Object.freeze({
      entries: Object.freeze({ ...lock.entries }),
      lastUpdatedAt: lock.lastUpdatedAt,
    });
  }

  async putLockEntry(entry: ExtensionLockEntry): Promise<void> {
    const store = this.requireStore();
    const lock = await this.getLock();
    const entries = { ...lock.entries, [entry.extensionId]: entry };
    const newLock: ExtensionLock = {
      entries,
      lastUpdatedAt: new Date().toISOString(),
    };
    await store.set(KEY_LOCK, JSON.stringify(newLock));
  }

  async deleteLockEntry(extensionId: string): Promise<void> {
    const store = this.requireStore();
    const lock = await this.getLock();
    const entries = { ...lock.entries };
    delete entries[extensionId];
    const newLock: ExtensionLock = {
      entries,
      lastUpdatedAt: new Date().toISOString(),
    };
    await store.set(KEY_LOCK, JSON.stringify(newLock));
  }

  // ---- composite ----------------------------------------------------------

  async getFullExtensionState(): Promise<FullExtensionState> {
    const store = this.requireStore();
    const [enablementRaw, overridesRaw, settingsRaw, packsRaw, lock] = await Promise.all([
      store.get(KEY_ENABLEMENT),
      store.get(KEY_OVERRIDES),
      store.get(KEY_SETTINGS),
      store.get(KEY_PACKS),
      this.getLock(),
    ]);

    const enablement = safeJsonParse<Record<string, ExtensionEnablementState>>(enablementRaw, {});
    const devOverrides = safeJsonParse<Record<string, DevOverrideState>>(overridesRaw, {});
    const settings = safeJsonParse<Record<string, ExtensionSettingsSnapshot>>(settingsRaw, {});
    const packs = safeJsonParse<Record<string, ExtensionPackRecord>>(packsRaw, {});

    return Object.freeze({ enablement, devOverrides, settings, packs, lock });
  }
}

/**
 * Create a provider-backed extension state repository.
 */
export function createProviderBackedExtensionStateRepository(
  store: ProviderBackedStore,
): ProviderBackedExtensionStateRepository {
  return new ProviderBackedExtensionStateRepository(store);
}
