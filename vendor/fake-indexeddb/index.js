class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    if (!listener) {
      return;
    }

    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }

  dispatch(type, event = {}) {
    const listeners = Array.from(this.listeners.get(type) ?? []);
    for (const listener of listeners) {
      listener({ target: this, ...event });
    }
  }
}

class FakeDOMStringList {
  constructor(values) {
    this.values = values;
  }

  contains(value) {
    return this.values.includes(value);
  }

  item(index) {
    return this.values[index] ?? null;
  }

  get length() {
    return this.values.length;
  }
}

class FakeRequest extends FakeEventTarget {
  constructor() {
    super();
    this.result = undefined;
    this.error = null;
    this.readyState = 'pending';
  }
}

// Minimal IDBKeyRange stub
export class IDBKeyRange {
  static only(value) {
    return { type: 'only', value };
  }

  static lowerBound(lower, open = false) {
    return { type: 'lowerBound', lower, open };
  }

  static upperBound(upper, open = false) {
    return { type: 'upperBound', upper, open };
  }

  static bound(lower, upper, lowerOpen = false, upperOpen = false) {
    return { type: 'bound', lower, upper, lowerOpen, upperOpen };
  }
}

class FakeIndex {
  constructor(name, keyPath, unique, records) {
    this.name = name;
    this.keyPath = keyPath;
    this.unique = unique;
    this.records = records;
  }

  get(key) {
    // Not used directly — syncLedgerIndexedDb uses getAll
    const request = new FakeRequest();
    queueMicrotask(() => {
      for (const [_k, record] of this.records) {
        if (record[this.keyPath] === key) {
          request.result = record;
          request.dispatch('success');
          return;
        }
      }
      request.result = undefined;
      request.dispatch('success');
    });
    return request;
  }

  getAll(query) {
    const request = new FakeRequest();
    queueMicrotask(() => {
      const results = [];
      for (const [_k, record] of this.records) {
        if (!query || query.type === 'only') {
          if (!query || record[this.keyPath] === query.value) {
            results.push(record);
          }
        } else {
          results.push(record);
        }
      }
      request.result = results;
      request.dispatch('success');
    });
    return request;
  }

  getAllKeys(query) {
    const request = new FakeRequest();
    queueMicrotask(() => {
      const results = [];
      for (const [key, record] of this.records) {
        if (!query || query.type === 'only') {
          if (!query || record[this.keyPath] === query.value) {
            results.push(key);
          }
        } else {
          results.push(key);
        }
      }
      request.result = results;
      request.dispatch('success');
    });
    return request;
  }

  openCursor(query, _direction) {
    // Minimal stub — not used by syncLedgerIndexedDb
    const request = new FakeRequest();
    queueMicrotask(() => {
      request.result = undefined;
      request.dispatch('success');
    });
    return request;
  }

  openKeyCursor(query, _direction) {
    const request = new FakeRequest();
    queueMicrotask(() => {
      request.result = undefined;
      request.dispatch('success');
    });
    return request;
  }

  count(query) {
    const request = new FakeRequest();
    queueMicrotask(() => {
      let count = 0;
      for (const [_k, record] of this.records) {
        if (!query || query.type === 'only') {
          if (!query || record[this.keyPath] === query.value) {
            count += 1;
          }
        } else {
          count += 1;
        }
      }
      request.result = count;
      request.dispatch('success');
    });
    return request;
  }
}

class FakeObjectStore {
  constructor(records, transaction, indexes, keyPath) {
    this.records = records;
    this.transaction = transaction;
    this._indexes = indexes ?? new Map();
    this.keyPath = keyPath ?? null;
  }

  get indexNames() {
    return new FakeDOMStringList(Array.from(this._indexes.keys()));
  }

  put(value, key) {
    return this.transaction.runRequest(() => {
      let effectiveKey = key;
      if (effectiveKey === undefined) {
        effectiveKey = this.keyPath ? value[this.keyPath] : value.key;
      }
      this.records.set(effectiveKey, value);
      return effectiveKey;
    });
  }

  get(key) {
    return this.transaction.runRequest(() => this.records.get(key));
  }

  delete(key) {
    return this.transaction.runRequest(() => {
      this.records.delete(key);
      return undefined;
    });
  }

  getAll(query) {
    return this.transaction.runRequest(() => {
      const results = [];
      for (const [_k, record] of this.records) {
        results.push(record);
      }
      return results;
    });
  }

  getAllKeys(query) {
    return this.transaction.runRequest(() => {
      const results = [];
      for (const [key, _record] of this.records) {
        results.push(key);
      }
      return results;
    });
  }

  index(name) {
    if (!this._indexes.has(name)) {
      throw new Error(`Index not found: ${name}`);
    }
    const indexDef = this._indexes.get(name);
    return new FakeIndex(name, indexDef.keyPath, indexDef.unique, this.records);
  }

  createIndex(name, keyPath, options = {}) {
    if (this._indexes.has(name)) {
      return;
    }
    this._indexes.set(name, {
      keyPath,
      unique: options?.unique ?? false,
    });
    return {
      name,
      keyPath,
      unique: options?.unique ?? false,
    };
  }

  deleteIndex(name) {
    this._indexes.delete(name);
  }

  clear() {
    return this.transaction.runRequest(() => {
      this.records.clear();
      return undefined;
    });
  }

  count(query) {
    return this.transaction.runRequest(() => this.records.size);
  }
}

class FakeTransaction extends FakeEventTarget {
  constructor(recordsByStore, storeName, indexesByStore, storeOptionsByStore) {
    super();
    this.recordsByStore = recordsByStore;
    this.storeName = storeName;
    this.indexesByStore = indexesByStore ?? new Map();
    this.storeOptionsByStore = storeOptionsByStore ?? new Map();
    this.pendingRequests = 0;
    this.completeQueued = false;
    this.error = null;
  }

  objectStore(name) {
    if (!this.recordsByStore.has(name)) {
      throw new Error(`Unknown object store: ${name}`);
    }

    const storeIndexes = this.indexesByStore.get(name) ?? new Map();
    const storeOptions = this.storeOptionsByStore.get(name) ?? {};
    return new FakeObjectStore(this.recordsByStore.get(name), this, storeIndexes, storeOptions.keyPath ?? null);
  }

  runRequest(executor) {
    const request = new FakeRequest();
    this.pendingRequests += 1;

    queueMicrotask(() => {
      try {
        request.result = executor();
        request.readyState = 'done';
        request.dispatch('success');
      } catch (error) {
        request.error = error;
        request.readyState = 'done';
        this.error = error;
        request.dispatch('error');
        this.dispatch('error');
      } finally {
        this.pendingRequests -= 1;
        if (this.pendingRequests === 0 && !this.completeQueued && !this.error) {
          this.completeQueued = true;
          queueMicrotask(() => this.dispatch('complete'));
        }
      }
    });

    return request;
  }

  abort() {
    this.error = new DOMException('Transaction aborted', 'AbortError');
    this.dispatch('abort');
  }
}

class FakeDatabase {
  constructor(name, version, recordsByStore, indexesByStore, storeOptionsByStore) {
    this.name = name;
    this.version = version;
    this.recordsByStore = recordsByStore;
    this.indexesByStore = indexesByStore ?? new Map();
    this.storeOptionsByStore = storeOptionsByStore ?? new Map();
    this._closed = false;
  }

  get objectStoreNames() {
    return new FakeDOMStringList(Array.from(this.recordsByStore.keys()));
  }

  createObjectStore(name, options = {}) {
    if (!this.recordsByStore.has(name)) {
      this.recordsByStore.set(name, new Map());
    }
    if (!this.indexesByStore.has(name)) {
      this.indexesByStore.set(name, new Map());
    }

    const storeOptions = {
      keyPath: options?.keyPath ?? null,
      autoIncrement: options?.autoIncrement ?? false,
    };
    this.storeOptionsByStore.set(name, storeOptions);

    return {
      name,
      ...storeOptions,
      createIndex: (indexName, keyPath, indexOptions = {}) => {
        const indexes = this.indexesByStore.get(name);
        if (!indexes.has(indexName)) {
          indexes.set(indexName, {
            keyPath,
            unique: indexOptions?.unique ?? false,
          });
        }
        return { name: indexName, keyPath, unique: indexOptions?.unique ?? false };
      },
      deleteIndex: (indexName) => {
        const indexes = this.indexesByStore.get(name);
        indexes?.delete(indexName);
      },
    };
  }

  deleteObjectStore(name) {
    this.recordsByStore.delete(name);
    this.indexesByStore.delete(name);
    this.storeOptionsByStore.delete(name);
  }

  transaction(nameOrNames, _mode) {
    // Normalize to single store name
    const name = Array.isArray(nameOrNames) ? nameOrNames[0] : nameOrNames;
    if (!this.recordsByStore.has(name)) {
      throw new Error(`Unknown object store: ${name}`);
    }

    return new FakeTransaction(this.recordsByStore, name, this.indexesByStore, this.storeOptionsByStore);
  }

  close() {
    this._closed = true;
  }
}

class FakeIndexedDBFactory {
  constructor() {
    this.databases = new Map();
  }

  open(name, version = 1) {
    const request = new FakeRequest();

    queueMicrotask(() => {
      const existing = this.databases.get(name);
      const shouldUpgrade = !existing || version > existing.version;
      const recordsByStore = existing?.recordsByStore ?? new Map();
      const indexesByStore = existing?.indexesByStore ?? new Map();
      const storeOptionsByStore = existing?.storeOptionsByStore ?? new Map();
      const database = new FakeDatabase(name, version, recordsByStore, indexesByStore, storeOptionsByStore);

      this.databases.set(name, {
        version,
        recordsByStore,
        indexesByStore,
        storeOptionsByStore,
      });

      request.result = database;
      request.readyState = 'done';
      if (shouldUpgrade) {
        request.dispatch('upgradeneeded');
      }
      request.dispatch('success');
    });

    return request;
  }

  deleteDatabase(name) {
    const request = new FakeRequest();

    queueMicrotask(() => {
      this.databases.delete(name);
      request.result = undefined;
      request.readyState = 'done';
      request.dispatch('success');
    });

    return request;
  }

  cmp(a, b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
  }

  databases() {
    const request = new FakeRequest();
    queueMicrotask(() => {
      request.result = Array.from(this.databases.entries()).map(([name, info]) => ({
        name,
        version: info.version,
      }));
      request.readyState = 'done';
      request.dispatch('success');
    });
    return request;
  }
}

// Singleton instance shared by the module and global
const _instance = new FakeIndexedDBFactory();

export function createFakeIndexedDB() {
  return new FakeIndexedDBFactory();
}

export function resetFakeIndexedDB() {
  _instance.databases.clear();
}

export const indexedDB = _instance;
export default indexedDB;
