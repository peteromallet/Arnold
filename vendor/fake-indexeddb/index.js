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
}

class FakeRequest extends FakeEventTarget {
  constructor() {
    super();
    this.result = undefined;
    this.error = null;
  }
}

class FakeObjectStore {
  constructor(records, transaction) {
    this.records = records;
    this.transaction = transaction;
  }

  put(value, key) {
    return this.transaction.runRequest(() => {
      this.records.set(key, value);
      return undefined;
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

  getAllKeys() {
    return this.transaction.runRequest(() => Array.from(this.records.keys()));
  }
}

class FakeTransaction extends FakeEventTarget {
  constructor(recordsByStore, storeName) {
    super();
    this.recordsByStore = recordsByStore;
    this.storeName = storeName;
    this.pendingRequests = 0;
    this.completeQueued = false;
    this.error = null;
  }

  objectStore(name) {
    if (name !== this.storeName) {
      throw new Error(`Unknown object store: ${name}`);
    }

    return new FakeObjectStore(this.recordsByStore.get(name), this);
  }

  runRequest(executor) {
    const request = new FakeRequest();
    this.pendingRequests += 1;

    queueMicrotask(() => {
      try {
        request.result = executor();
        request.dispatch("success");
      } catch (error) {
        request.error = error;
        this.error = error;
        request.dispatch("error");
        this.dispatch("error");
      } finally {
        this.pendingRequests -= 1;
        if (this.pendingRequests === 0 && !this.completeQueued && !this.error) {
          this.completeQueued = true;
          queueMicrotask(() => this.dispatch("complete"));
        }
      }
    });

    return request;
  }
}

class FakeDatabase {
  constructor(name, version, recordsByStore) {
    this.name = name;
    this.version = version;
    this.recordsByStore = recordsByStore;
  }

  get objectStoreNames() {
    return new FakeDOMStringList(Array.from(this.recordsByStore.keys()));
  }

  createObjectStore(name) {
    if (!this.recordsByStore.has(name)) {
      this.recordsByStore.set(name, new Map());
    }

    return {
      name,
    };
  }

  transaction(name) {
    if (!this.recordsByStore.has(name)) {
      throw new Error(`Unknown object store: ${name}`);
    }

    return new FakeTransaction(this.recordsByStore, name);
  }

  close() {}
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
      const database = new FakeDatabase(name, version, recordsByStore);

      this.databases.set(name, {
        version,
        recordsByStore,
      });

      request.result = database;
      if (shouldUpgrade) {
        request.dispatch("upgradeneeded");
      }
      request.dispatch("success");
    });

    return request;
  }
}

export function createFakeIndexedDB() {
  return new FakeIndexedDBFactory();
}

export const indexedDB = createFakeIndexedDB();
export default indexedDB;
