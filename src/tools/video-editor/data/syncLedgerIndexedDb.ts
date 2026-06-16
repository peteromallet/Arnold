const DATABASE_NAME = 'reigh.sync-ledger';
const DATABASE_VERSION = 1;
const BOOKMARK_STORE_NAME = 'sync-bookmarks';
const KEEP_BOTH_STORE_NAME = 'sync-keep-both-artifacts';

export type SyncSpoke = 'local' | 'app';

export interface SyncBookmarkRecord {
  timeline_id: string;
  spoke: SyncSpoke;
  spoke_version: number;
  spoke_hash: string | null;
  spoke_event_id: string | null;
  hub_version: number;
  hub_hash: string | null;
  hub_event_id: string | null;
  synced_at: string;
}

export interface KeepBothArtifactRecord {
  id: string;
  timeline_id: string;
  spoke: SyncSpoke;
  created_at: string;
  artifact: Record<string, unknown>;
}

type BookmarkRow = SyncBookmarkRecord & { key: string };
type KeepBothArtifactRow = KeepBothArtifactRecord & { key: string };

export function buildSyncBookmarkKey(timelineId: string, spoke: SyncSpoke): string {
  return `${timelineId}:${spoke}`;
}

export function buildKeepBothArtifactKey(
  timelineId: string,
  createdAt: string,
  artifactId: string,
): string {
  return `${timelineId}:${createdAt}:${artifactId}`;
}

function getIndexedDb(): IDBFactory {
  if (typeof indexedDB === 'undefined') {
    throw new Error('IndexedDB is not available in this environment');
  }
  return indexedDB;
}

function openDatabase(): Promise<IDBDatabase> {
  const indexedDb = getIndexedDb();
  return new Promise((resolve, reject) => {
    const request = indexedDb.open(DATABASE_NAME, DATABASE_VERSION);

    request.addEventListener('upgradeneeded', () => {
      const database = request.result;

      if (!database.objectStoreNames.contains(BOOKMARK_STORE_NAME)) {
        database.createObjectStore(BOOKMARK_STORE_NAME, { keyPath: 'key' });
      }

      if (!database.objectStoreNames.contains(KEEP_BOTH_STORE_NAME)) {
        const store = database.createObjectStore(KEEP_BOTH_STORE_NAME, { keyPath: 'key' });
        store.createIndex('timeline_id', 'timeline_id', { unique: false });
      } else {
        const transaction = request.transaction;
        if (transaction) {
          const store = transaction.objectStore(KEEP_BOTH_STORE_NAME);
          if (!store.indexNames.contains('timeline_id')) {
            store.createIndex('timeline_id', 'timeline_id', { unique: false });
          }
        }
      }
    });

    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('Failed to open IndexedDB')));
    request.addEventListener('blocked', () => reject(new Error('IndexedDB open blocked')));
  });
}

function deleteDatabase(): Promise<void> {
  const indexedDb = getIndexedDb();
  return new Promise((resolve, reject) => {
    const request = indexedDb.deleteDatabase(DATABASE_NAME);
    request.addEventListener('success', () => resolve());
    request.addEventListener('error', () => reject(request.error ?? new Error('Failed to delete IndexedDB')));
    request.addEventListener('blocked', () => reject(new Error('IndexedDB delete blocked')));
  });
}

function shouldRecover(error: unknown): boolean {
  return error instanceof DOMException
    ? ['AbortError', 'InvalidStateError', 'NotFoundError', 'UnknownError', 'VersionError'].includes(error.name)
    : error instanceof Error;
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
        if (!settled) {
          settled = true;
          resolve(request.result);
        }
      });
      request.addEventListener('error', () => fail(request.error ?? new Error('IndexedDB request failed')));
      transaction.addEventListener('abort', () => fail(transaction.error ?? new Error('IndexedDB transaction aborted')));
      transaction.addEventListener('error', () => fail(transaction.error ?? new Error('IndexedDB transaction failed')));
      transaction.addEventListener('complete', () => {
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

function validateHeadShape(
  version: number,
  hash: string | null,
  eventId: string | null,
  label: string,
): void {
  if (!Number.isInteger(version) || version < 0) {
    throw new Error(`${label}_version must be a non-negative integer`);
  }
  if (version === 0) {
    if (hash !== null || eventId !== null) {
      throw new Error(`${label}_hash and ${label}_event_id must be null when ${label}_version is 0`);
    }
    return;
  }
  if (!hash || !eventId) {
    throw new Error(`${label}_hash and ${label}_event_id are required when ${label}_version is non-zero`);
  }
}

function validateBookmarkRecord(record: SyncBookmarkRecord): void {
  if (!record.timeline_id) {
    throw new Error('timeline_id is required');
  }
  if (record.spoke !== 'local' && record.spoke !== 'app') {
    throw new Error('spoke must be local or app');
  }
  if (!record.synced_at) {
    throw new Error('synced_at is required');
  }
  validateHeadShape(record.spoke_version, record.spoke_hash, record.spoke_event_id, 'spoke');
  validateHeadShape(record.hub_version, record.hub_hash, record.hub_event_id, 'hub');
}

function toBookmarkRow(record: SyncBookmarkRecord): BookmarkRow {
  validateBookmarkRecord(record);
  return {
    ...record,
    key: buildSyncBookmarkKey(record.timeline_id, record.spoke),
  };
}

function fromBookmarkRow(row: BookmarkRow | undefined): SyncBookmarkRecord | null {
  if (!row) {
    return null;
  }
  const { key: _key, ...record } = row;
  validateBookmarkRecord(record);
  return record;
}

function toKeepBothArtifactRow(record: KeepBothArtifactRecord): KeepBothArtifactRow {
  if (!record.timeline_id || !record.id || !record.created_at) {
    throw new Error('timeline_id, id, and created_at are required for keep-both artifacts');
  }
  if (record.spoke !== 'local' && record.spoke !== 'app') {
    throw new Error('spoke must be local or app');
  }
  return {
    ...record,
    key: buildKeepBothArtifactKey(record.timeline_id, record.created_at, record.id),
  };
}

function fromKeepBothArtifactRow(row: KeepBothArtifactRow | undefined): KeepBothArtifactRecord | null {
  if (!row) {
    return null;
  }
  const { key: _key, ...record } = row;
  return record;
}

export async function loadSyncBookmark(
  timelineId: string,
  spoke: SyncSpoke,
): Promise<SyncBookmarkRecord | null> {
  const row = await withStore<BookmarkRow | undefined>(
    BOOKMARK_STORE_NAME,
    'readonly',
    (store) => store.get(buildSyncBookmarkKey(timelineId, spoke)),
  );
  return fromBookmarkRow(row);
}

export async function saveSyncBookmark(record: SyncBookmarkRecord): Promise<void> {
  await withStore<IDBValidKey>(
    BOOKMARK_STORE_NAME,
    'readwrite',
    (store) => store.put(toBookmarkRow(record)),
  );
}

export async function deleteSyncBookmark(
  timelineId: string,
  spoke: SyncSpoke,
): Promise<void> {
  await withStore<undefined>(
    BOOKMARK_STORE_NAME,
    'readwrite',
    (store) => store.delete(buildSyncBookmarkKey(timelineId, spoke)),
  );
}

export async function saveKeepBothArtifact(record: KeepBothArtifactRecord): Promise<void> {
  await withStore<IDBValidKey>(
    KEEP_BOTH_STORE_NAME,
    'readwrite',
    (store) => store.put(toKeepBothArtifactRow(record)),
  );
}

export async function loadKeepBothArtifact(
  timelineId: string,
  createdAt: string,
  artifactId: string,
): Promise<KeepBothArtifactRecord | null> {
  const row = await withStore<KeepBothArtifactRow | undefined>(
    KEEP_BOTH_STORE_NAME,
    'readonly',
    (store) => store.get(buildKeepBothArtifactKey(timelineId, createdAt, artifactId)),
  );
  return fromKeepBothArtifactRow(row);
}

export async function listKeepBothArtifacts(
  timelineId: string,
): Promise<KeepBothArtifactRecord[]> {
  const rows = await withStore<KeepBothArtifactRow[]>(
    KEEP_BOTH_STORE_NAME,
    'readonly',
    (store) => store.index('timeline_id').getAll(IDBKeyRange.only(timelineId)),
  );
  return rows
    .map((row) => fromKeepBothArtifactRow(row))
    .filter((row): row is KeepBothArtifactRecord => row !== null)
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
}
