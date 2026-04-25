const DATABASE_NAME = 'reigh.local-media';
const DATABASE_VERSION = 1;
const OBJECT_STORE_NAME = 'reigh.local-media-handles';

export type HandlePermissionMode = 'read' | 'readwrite';

export interface PersistedLocalMediaHandle {
  kind: string;
  name: string;
  queryPermission: (descriptor?: { mode?: HandlePermissionMode }) => Promise<PermissionState>;
  requestPermission: (descriptor?: { mode?: HandlePermissionMode }) => Promise<PermissionState>;
  getFile?: () => Promise<File>;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);

    request.addEventListener('upgradeneeded', () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(OBJECT_STORE_NAME)) {
        database.createObjectStore(OBJECT_STORE_NAME);
      }
    });

    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('Failed to open IndexedDB')));
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  execute: (store: IDBObjectStore) => IDBRequest<T> | void,
): Promise<T | void> {
  const database = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(OBJECT_STORE_NAME, mode);
    const store = transaction.objectStore(OBJECT_STORE_NAME);
    const request = execute(store);

    transaction.addEventListener('complete', () => {
      database.close();
    });
    transaction.addEventListener('abort', () => {
      database.close();
      reject(transaction.error ?? new Error('IndexedDB transaction aborted'));
    });
    transaction.addEventListener('error', () => {
      database.close();
      reject(transaction.error ?? new Error('IndexedDB transaction failed'));
    });

    if (!request) {
      resolve();
      return;
    }

    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('IndexedDB request failed')));
  });
}

export async function saveHandle(id: string, handle: PersistedLocalMediaHandle): Promise<void> {
  await withStore('readwrite', (store) => store.put(handle, id));
}

export async function loadHandle(id: string): Promise<PersistedLocalMediaHandle | null> {
  const handle = (await withStore('readonly', (store) => store.get(id))) as PersistedLocalMediaHandle | undefined;
  return handle ?? null;
}

export async function deleteHandle(id: string): Promise<void> {
  await withStore('readwrite', (store) => store.delete(id));
}

export async function listHandleIds(): Promise<string[]> {
  return ((await withStore('readonly', (store) => store.getAllKeys())) as IDBValidKey[]).map(String);
}

export async function ensurePermission(
  handle: PersistedLocalMediaHandle,
  mode: HandlePermissionMode = 'read',
): Promise<PermissionState> {
  const currentPermission = await handle.queryPermission({ mode });
  if (currentPermission !== 'prompt') {
    return currentPermission;
  }

  if (!navigator.userActivation?.isActive) {
    return 'prompt';
  }

  return handle.requestPermission({ mode });
}
