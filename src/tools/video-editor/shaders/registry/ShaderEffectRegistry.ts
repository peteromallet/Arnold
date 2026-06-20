import type { DiagnosticSeverity, DisposeHandle, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  ShaderEffectRegistry,
  ShaderEffectRegistryLookup,
  ShaderEffectRegistryRecord,
  ShaderEffectRegistrySnapshot,
  ShaderEffectRegistrySubscriber,
} from '@/tools/video-editor/shaders/registry/types.ts';

interface InternalRecord {
  readonly token: symbol;
  readonly key: string;
  readonly record: ShaderEffectRegistryRecord;
  disposed: boolean;
}

function createRegistryKey(lookup: ShaderEffectRegistryLookup): string {
  return `${lookup.ownerExtensionId ?? ''}\u0000${lookup.shaderId}`;
}

function cloneAndFreeze<T>(value: T): T {
  if (Array.isArray(value)) {
    return Object.freeze(value.map((entry) => cloneAndFreeze(entry))) as T;
  }

  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).map(([key, entry]) => [
      key,
      cloneAndFreeze(entry),
    ]);
    return Object.freeze(Object.fromEntries(entries)) as T;
  }

  return value;
}

function emitDiagnostic(
  diagnostics: ExtensionDiagnostic[],
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  extensionId?: string,
  contributionId?: string,
  detail?: Record<string, unknown>,
): void {
  diagnostics.push(cloneAndFreeze({
    severity,
    code,
    message,
    ...(extensionId ? { extensionId } : {}),
    ...(contributionId ? { contributionId } : {}),
    ...(detail ? { detail } : {}),
  }));
}

function safeDispose(entry: InternalRecord, diagnostics: ExtensionDiagnostic[]): void {
  if (entry.disposed) return;
  entry.disposed = true;

  try {
    entry.record.dispose?.();
  } catch (error) {
    emitDiagnostic(
      diagnostics,
      'error',
      'shader-effect-registry/dispose-failed',
      `Shader "${entry.record.shaderId}" dispose failed: ${String(error)}`,
      entry.record.ownerExtensionId,
      entry.record.contributionId,
      {
        shaderId: entry.record.shaderId,
        ownerExtensionId: entry.record.ownerExtensionId,
      },
    );
  }
}

function freezeRecord(record: ShaderEffectRegistryRecord): ShaderEffectRegistryRecord {
  return cloneAndFreeze(record);
}

function sortEntries(entries: InternalRecord[]): InternalRecord[] {
  return [...entries].sort((a, b) => {
    const ownerA = a.record.ownerExtensionId ?? '';
    const ownerB = b.record.ownerExtensionId ?? '';
    const ownerCmp = ownerA.localeCompare(ownerB);
    if (ownerCmp !== 0) return ownerCmp;

    const shaderCmp = a.record.shaderId.localeCompare(b.record.shaderId);
    if (shaderCmp !== 0) return shaderCmp;

    return a.record.contributionId.localeCompare(b.record.contributionId);
  });
}

export function createShaderEffectRegistry(): ShaderEffectRegistry {
  const records = new Map<string, InternalRecord>();
  const subscribers = new Set<ShaderEffectRegistrySubscriber>();
  const diagnostics: ExtensionDiagnostic[] = [];

  let frozenSnapshot: ShaderEffectRegistrySnapshot | null = null;
  let disposed = false;

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function getByLookup(lookup: ShaderEffectRegistryLookup): ShaderEffectRegistryRecord | undefined {
    return records.get(createRegistryKey(lookup))?.record;
  }

  function hasByLookup(lookup: ShaderEffectRegistryLookup): boolean {
    return records.has(createRegistryKey(lookup));
  }

  function getSnapshot(): ShaderEffectRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const snapshotRecords = Object.freeze(
      sortEntries([...records.values()]).map((entry) => entry.record),
    );

    frozenSnapshot = Object.freeze({
      records: snapshotRecords,
      diagnostics: Object.freeze([...diagnostics]),
      get: (shaderId: string, ownerExtensionId?: string) => getByLookup({ shaderId, ownerExtensionId }),
      getByLookup,
      has: (shaderId: string, ownerExtensionId?: string) => hasByLookup({ shaderId, ownerExtensionId }),
      hasByLookup,
    });

    return frozenSnapshot;
  }

  function notifySubscribers(): void {
    const snapshot = getSnapshot();
    subscribers.forEach((subscriber) => {
      try {
        subscriber(snapshot);
      } catch {
        // Subscriber failures are isolated from registry lifecycle work.
      }
    });
  }

  function guardDisposed(operation: string): boolean {
    if (!disposed) return false;
    emitDiagnostic(
      diagnostics,
      'warning',
      'shader-effect-registry/disposed',
      `ShaderEffectRegistry operation "${operation}" called after dispose.`,
    );
    invalidateSnapshot();
    return true;
  }

  function removeEntry(lookup: ShaderEffectRegistryLookup, expectedToken?: symbol): void {
    const key = createRegistryKey(lookup);
    const existing = records.get(key);
    if (!existing || (expectedToken && existing.token !== expectedToken)) return;

    records.delete(key);
    safeDispose(existing, diagnostics);
    invalidateSnapshot();
    notifySubscribers();
  }

  function register(record: ShaderEffectRegistryRecord): DisposeHandle {
    if (guardDisposed('register')) {
      return { dispose(): void {} };
    }

    const frozenRecord = freezeRecord(record);
    const key = createRegistryKey(frozenRecord);
    const existing = records.get(key);

    if (existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'shader-effect-registry/duplicate-shader',
        `Shader "${frozenRecord.shaderId}" is already registered for this owner. The previous record will be replaced.`,
        frozenRecord.ownerExtensionId,
        frozenRecord.contributionId,
        {
          shaderId: frozenRecord.shaderId,
          ownerExtensionId: frozenRecord.ownerExtensionId,
          previousContributionId: existing.record.contributionId,
          previousStatus: existing.record.status,
        },
      );
      safeDispose(existing, diagnostics);
    }

    const token = Symbol(key);
    records.set(key, {
      token,
      key,
      record: frozenRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(frozenRecord, token);
      },
    };
  }

  function updateRecord(
    lookup: ShaderEffectRegistryLookup,
    updater: (current: ShaderEffectRegistryRecord) => ShaderEffectRegistryRecord,
    newDispose?: ShaderEffectRegistryRecord['dispose'],
  ): DisposeHandle {
    if (guardDisposed('updateRecord')) {
      return { dispose(): void {} };
    }

    const key = createRegistryKey(lookup);
    const existing = records.get(key);
    if (!existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'shader-effect-registry/update-missing-shader',
        `Shader "${lookup.shaderId}" cannot be updated because it is not registered for this owner.`,
        lookup.ownerExtensionId,
        undefined,
        lookup,
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    const nextRecord = freezeRecord({
      ...updater(existing.record),
      ...(newDispose ? { dispose: newDispose } : {}),
    });
    const nextKey = createRegistryKey(nextRecord);

    if (nextKey !== key) {
      emitDiagnostic(
        diagnostics,
        'error',
        'shader-effect-registry/update-shader-key-mismatch',
        `Shader "${lookup.shaderId}" update returned mismatched owner or shader ID.`,
        nextRecord.ownerExtensionId,
        nextRecord.contributionId,
        {
          shaderId: lookup.shaderId,
          ownerExtensionId: lookup.ownerExtensionId,
          nextShaderId: nextRecord.shaderId,
          nextOwnerExtensionId: nextRecord.ownerExtensionId,
        },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    safeDispose(existing, diagnostics);

    const token = Symbol(key);
    records.set(key, {
      token,
      key,
      record: nextRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(nextRecord, token);
      },
    };
  }

  function unregister(shaderId: string, ownerExtensionId?: string): void {
    if (guardDisposed('unregister')) return;
    removeEntry({ shaderId, ownerExtensionId });
  }

  function unregisterByLookup(lookup: ShaderEffectRegistryLookup): void {
    if (guardDisposed('unregisterByLookup')) return;
    removeEntry(lookup);
  }

  function unregisterOwner(ownerExtensionId: string): void {
    if (guardDisposed('unregisterOwner')) return;

    const owned = [...records.values()].filter(
      (entry) => entry.record.ownerExtensionId === ownerExtensionId,
    );
    if (owned.length === 0) return;

    owned.forEach((entry) => {
      records.delete(entry.key);
      safeDispose(entry, diagnostics);
    });

    invalidateSnapshot();
    notifySubscribers();
  }

  function resolve(shaderId: string, ownerExtensionId?: string): ShaderEffectRegistryRecord | undefined {
    return getByLookup({ shaderId, ownerExtensionId });
  }

  function subscribe(subscriber: ShaderEffectRegistrySubscriber): DisposeHandle {
    subscribers.add(subscriber);
    return {
      dispose(): void {
        subscribers.delete(subscriber);
      },
    };
  }

  function dispose(): void {
    if (disposed) return;
    disposed = true;

    const entries = [...records.values()];
    records.clear();
    entries.forEach((entry) => safeDispose(entry, diagnostics));
    invalidateSnapshot();
    notifySubscribers();
    subscribers.clear();
  }

  return {
    register,
    updateRecord,
    unregister,
    unregisterByLookup,
    unregisterOwner,
    resolve,
    resolveByLookup: getByLookup,
    subscribe,
    getSnapshot,
    dispose,
  };
}
