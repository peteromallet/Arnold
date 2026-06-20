/**
 * IndexedDB-backed implementation of ExtensionStateRepository (T6).
 *
 * Uses the same IndexedDB pattern as syncLedgerIndexedDb.ts (which has
 * passing tests with fake-indexeddb). Each operation opens a fresh
 * connection, executes the transaction, and closes.
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
// Constants
// ---------------------------------------------------------------------------

const DB_NAME = 'reigh.extension-state';
const DB_VERSION = 1;
const STORE_PACKS = 'pack-records';
const STORE_ENABLEMENT = 'enablement-states';
const STORE_OVERRIDES = 'dev-overrides';
const STORE_SETTINGS = 'settings-snapshots';
const STORE_EVENTS = 'lifecycle-events';
const STORE_LOCK = 'lock-entries';
const STORE_BUNDLES = 'bundle-content';

const ALL_STORES = [
  STORE_PACKS, STORE_ENABLEMENT, STORE_OVERRIDES,
  STORE_SETTINGS, STORE_EVENTS, STORE_LOCK, STORE_BUNDLES,
];

// ---------------------------------------------------------------------------
// IndexedDB helpers (matches syncLedgerIndexedDb pattern exactly)
// ---------------------------------------------------------------------------

function getIndexedDb(): IDBFactory {
  if (typeof indexedDB === 'undefined') {
    throw new Error('IndexedDB is not available in this environment');
  }
  return indexedDB;
}

function shouldRecover(error: unknown): boolean {
  if (error instanceof DOMException) {
    return ['AbortError', 'InvalidStateError', 'NotFoundError', 'UnknownError', 'VersionError'].includes(error.name);
  }
  return false;
}

function openDatabase(): Promise<IDBDatabase> {
  const indexedDb = getIndexedDb();
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDb.open(DB_NAME, DB_VERSION);

    request.addEventListener('upgradeneeded', () => {
      const db = request.result;
      for (const storeName of ALL_STORES) {
        if (!db.objectStoreNames.contains(storeName)) {
          if (storeName === STORE_EVENTS || storeName === STORE_BUNDLES) {
            db.createObjectStore(storeName, { keyPath: 'id' });
          } else {
            db.createObjectStore(storeName, { keyPath: 'extensionId' });
          }
        }
      }
    });

    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('Failed to open IndexedDB')));
    request.addEventListener('blocked', () => reject(new Error('IndexedDB open blocked')));
  });
}

async function deleteDatabase(): Promise<void> {
  const indexedDb = getIndexedDb();
  return new Promise<void>((resolve, reject) => {
    const req = indexedDb.deleteDatabase(DB_NAME);
    req.addEventListener('success', () => resolve());
    req.addEventListener('error', () => reject(req.error ?? new Error('Failed to delete IndexedDB')));
    req.addEventListener('blocked', () => reject(new Error('IndexedDB delete blocked')));
  });
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  execute: (store: IDBObjectStore) => IDBRequest<T>,
  { allowRecovery = true }: { allowRecovery?: boolean } = {},
): Promise<T> {
  let database: IDBDatabase | null = null;
  try {
    database = await openDatabase();
    return await new Promise<T>((resolve, reject) => {
      let settled = false;
      const transaction = database!.transaction(storeName, mode);
      const store = transaction.objectStore(storeName);
      const request = execute(store);

      const fail = (error: unknown) => {
        if (!settled) {
          settled = true;
          reject(error);
        }
      };

      request.addEventListener('success', () => {
        // Store result but don't resolve yet — wait for transaction complete
      });
      request.addEventListener('error', () => fail(request.error ?? new Error('IndexedDB request failed')));
      transaction.addEventListener('abort', () => fail(transaction.error ?? new Error('IndexedDB transaction aborted')));
      transaction.addEventListener('error', () => fail(transaction.error ?? new Error('IndexedDB transaction failed')));
      transaction.addEventListener('complete', () => {
        if (!settled) {
          settled = true;
          resolve(request.result);
        }
        database?.close();
        database = null;
      });
    });
  } catch (error) {
    if (database) {
      database.close();
    }
    if (!allowRecovery || !shouldRecover(error)) {
      throw error;
    }
    await deleteDatabase();
    return withStore(storeName, mode, execute, { allowRecovery: false });
  }
}

// ---------------------------------------------------------------------------
// Repository Implementation
// ---------------------------------------------------------------------------

export class IndexedDBExtensionStateRepository implements ExtensionStateRepository {
  private _disposed = false;
  private _initialized = false;

  async initialize(): Promise<void> {
    if (this._disposed) throw new Error('Repository is disposed');
    if (this._initialized) return;
    try {
      const db = await openDatabase();
      db.close();
      this._initialized = true;
    } catch (error) {
      if (shouldRecover(error)) {
        await deleteDatabase();
        const db = await openDatabase();
        db.close();
        this._initialized = true;
      } else {
        throw error;
      }
    }
  }

  async dispose(): Promise<void> {
    this._disposed = true;
    this._initialized = false;
  }

  get isDisposed(): boolean { return this._disposed; }

  private check(): void {
    if (this._disposed) throw new Error('Repository is disposed');
    if (!this._initialized) throw new Error('Repository not initialized');
  }

  // ---- pack records -------------------------------------------------------

  async putPackRecord(record: ExtensionPackRecord): Promise<void> {
    this.check();
    const existing = await withStore<ExtensionPackRecord | undefined>(
      STORE_PACKS, 'readonly', (s) => s.get(record.extensionId),
    );
    if (existing) throw new Error(`Pack record already exists for extension "${record.extensionId}"`);
    await withStore(STORE_PACKS, 'readwrite', (s) => s.put(record));
  }

  async updatePackRecord(extensionId: string, record: ExtensionPackRecord): Promise<void> {
    this.check();
    const existing = await withStore<ExtensionPackRecord | undefined>(
      STORE_PACKS, 'readonly', (s) => s.get(extensionId),
    );
    if (!existing) throw new Error(`No pack record exists for extension "${extensionId}"`);
    await withStore(STORE_PACKS, 'readwrite', (s) => s.put(record));
  }

  async getPackRecord(extensionId: string): Promise<ExtensionPackRecord | null> {
    this.check();
    const result = await withStore<ExtensionPackRecord | undefined>(
      STORE_PACKS, 'readonly', (s) => s.get(extensionId),
    );
    return result ?? null;
  }

  async getAllPackRecords(): Promise<ExtensionPackRecord[]> {
    this.check();
    return withStore<ExtensionPackRecord[]>(STORE_PACKS, 'readonly', (s) => s.getAll());
  }

  async deletePackRecord(extensionId: string): Promise<void> {
    this.check();
    await withStore(STORE_PACKS, 'readwrite', (s) => s.delete(extensionId));
  }

  // ---- enablement state ---------------------------------------------------

  async putEnablementState(state: ExtensionEnablementState): Promise<void> {
    this.check();
    await withStore(STORE_ENABLEMENT, 'readwrite', (s) => s.put(state));
  }

  async getEnablementState(extensionId: string): Promise<ExtensionEnablementState | null> {
    this.check();
    const result = await withStore<ExtensionEnablementState | undefined>(
      STORE_ENABLEMENT, 'readonly', (s) => s.get(extensionId),
    );
    return result ?? null;
  }

  async getAllEnablementStates(): Promise<ExtensionEnablementState[]> {
    this.check();
    return withStore<ExtensionEnablementState[]>(STORE_ENABLEMENT, 'readonly', (s) => s.getAll());
  }

  async deleteEnablementState(extensionId: string): Promise<void> {
    this.check();
    await withStore(STORE_ENABLEMENT, 'readwrite', (s) => s.delete(extensionId));
  }

  // ---- dev overrides ------------------------------------------------------

  async putDevOverride(override: DevOverrideState): Promise<void> {
    this.check();
    await withStore(STORE_OVERRIDES, 'readwrite', (s) => s.put(override));
  }

  async getDevOverride(extensionId: string): Promise<DevOverrideState | null> {
    this.check();
    const result = await withStore<DevOverrideState | undefined>(
      STORE_OVERRIDES, 'readonly', (s) => s.get(extensionId),
    );
    return result ?? null;
  }

  async getAllDevOverrides(): Promise<DevOverrideState[]> {
    this.check();
    return withStore<DevOverrideState[]>(STORE_OVERRIDES, 'readonly', (s) => s.getAll());
  }

  async deleteDevOverride(extensionId: string): Promise<void> {
    this.check();
    await withStore(STORE_OVERRIDES, 'readwrite', (s) => s.delete(extensionId));
  }

  // ---- settings snapshots -------------------------------------------------

  async putSettingsSnapshot(snapshot: ExtensionSettingsSnapshot): Promise<void> {
    this.check();
    await withStore(STORE_SETTINGS, 'readwrite', (s) => s.put(snapshot));
  }

  async getSettingsSnapshot(extensionId: string): Promise<ExtensionSettingsSnapshot | null> {
    this.check();
    const result = await withStore<ExtensionSettingsSnapshot | undefined>(
      STORE_SETTINGS, 'readonly', (s) => s.get(extensionId),
    );
    return result ?? null;
  }

  async getAllSettingsSnapshots(): Promise<ExtensionSettingsSnapshot[]> {
    this.check();
    return withStore<ExtensionSettingsSnapshot[]>(STORE_SETTINGS, 'readonly', (s) => s.getAll());
  }

  async deleteSettingsSnapshot(extensionId: string): Promise<void> {
    this.check();
    await withStore(STORE_SETTINGS, 'readwrite', (s) => s.delete(extensionId));
  }

  // ---- lifecycle events ---------------------------------------------------

  async appendLifecycleEvent(event: ExtensionLifecycleEvent): Promise<void> {
    this.check();
    const existing = await withStore<ExtensionLifecycleEvent | undefined>(
      STORE_EVENTS, 'readonly', (s) => s.get(event.id),
    );
    if (existing) throw new Error(`Lifecycle event with ID "${event.id}" already exists`);
    await withStore(STORE_EVENTS, 'readwrite', (s) => s.put(event));
  }

  async queryLifecycleEvents(query: LifecycleEventQuery): Promise<ExtensionLifecycleEvent[]> {
    this.check();
    let all = await withStore<ExtensionLifecycleEvent[]>(STORE_EVENTS, 'readonly', (s) => s.getAll());

    if (query.extensionId) all = all.filter((e) => e.extensionId === query.extensionId);
    if (query.kinds && query.kinds.length > 0) all = all.filter((e) => query.kinds!.includes(e.kind));
    if (query.since) all = all.filter((e) => e.timestamp >= query.since!);
    if (query.until) all = all.filter((e) => e.timestamp <= query.until!);

    all.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    const limit = query.limit ?? 100;
    if (all.length > limit) all = all.slice(0, limit);
    return all;
  }

  async getLifecycleEvents(extensionId: string, limit?: number): Promise<ExtensionLifecycleEvent[]> {
    return this.queryLifecycleEvents({ extensionId, limit });
  }

  // ---- project lock metadata ----------------------------------------------

  async getLock(): Promise<ExtensionLock> {
    this.check();
    const entries = await withStore<ExtensionLockEntry[]>(STORE_LOCK, 'readonly', (s) => s.getAll());
    const entriesMap: Record<string, ExtensionLockEntry> = {};
    let maxUpdatedAt = '1970-01-01T00:00:00.000Z';
    for (const entry of entries) {
      entriesMap[entry.extensionId] = entry;
      if (entry.updatedAt && entry.updatedAt > maxUpdatedAt) maxUpdatedAt = entry.updatedAt;
      if (entry.lockedAt > maxUpdatedAt) maxUpdatedAt = entry.lockedAt;
    }
    return {
      entries: entriesMap,
      lastUpdatedAt: maxUpdatedAt === '1970-01-01T00:00:00.000Z' ? new Date().toISOString() : maxUpdatedAt,
    };
  }

  async putLockEntry(entry: ExtensionLockEntry): Promise<void> {
    this.check();
    await withStore(STORE_LOCK, 'readwrite', (s) => s.put(entry));
  }

  async deleteLockEntry(extensionId: string): Promise<void> {
    this.check();
    await withStore(STORE_LOCK, 'readwrite', (s) => s.delete(extensionId));
  }

  // ---- composite ----------------------------------------------------------

  async getFullExtensionState(): Promise<FullExtensionState> {
    this.check();
    const [enablementList, overridesList, settingsList, packsList, lock] = await Promise.all([
      withStore<ExtensionEnablementState[]>(STORE_ENABLEMENT, 'readonly', (s) => s.getAll()),
      withStore<DevOverrideState[]>(STORE_OVERRIDES, 'readonly', (s) => s.getAll()),
      withStore<ExtensionSettingsSnapshot[]>(STORE_SETTINGS, 'readonly', (s) => s.getAll()),
      withStore<ExtensionPackRecord[]>(STORE_PACKS, 'readonly', (s) => s.getAll()),
      this.getLock(),
    ]);

    const enablement: Record<string, ExtensionEnablementState> = {};
    for (const e of enablementList) enablement[e.extensionId] = e;

    const devOverrides: Record<string, DevOverrideState> = {};
    for (const o of overridesList) devOverrides[o.extensionId] = o;

    const settings: Record<string, ExtensionSettingsSnapshot> = {};
    for (const s of settingsList) settings[s.extensionId] = s;

    const packs: Record<string, ExtensionPackRecord> = {};
    for (const p of packsList) packs[p.extensionId] = p;

    return { enablement, devOverrides, settings, packs, lock };
  }

  // ---- bundle content -----------------------------------------------------

  async putBundleContent(ref: string, content: string): Promise<void> {
    this.check();
    await withStore(STORE_BUNDLES, 'readwrite', (s) => s.put({ id: ref, content }));
  }

  async getBundleContent(ref: string): Promise<string | null> {
    this.check();
    const record = await withStore<{ id: string; content: string } | undefined>(
      STORE_BUNDLES, 'readonly', (s) => s.get(ref),
    );
    return record?.content ?? null;
  }

  async deleteBundleContent(ref: string): Promise<void> {
    this.check();
    await withStore(STORE_BUNDLES, 'readwrite', (s) => s.delete(ref));
  }
}

export function createIndexedDBExtensionStateRepository(): IndexedDBExtensionStateRepository {
  return new IndexedDBExtensionStateRepository();
}
