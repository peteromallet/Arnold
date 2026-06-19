import type { DiagnosticSeverity, DisposeHandle, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  EffectRegistry,
  EffectRegistryRecord,
  EffectRegistrySnapshot,
  EffectRegistrySubscriber,
} from '@/tools/video-editor/effects/registry/types.ts';

interface InternalRecord {
  readonly token: symbol;
  readonly record: EffectRegistryRecord;
  disposed: boolean;
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
  diagnostics.push(Object.freeze({
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
      'effect-registry/dispose-failed',
      `Effect "${entry.record.effectId}" dispose failed: ${String(error)}`,
      entry.record.ownerExtensionId,
      entry.record.contributionId,
      { effectId: entry.record.effectId },
    );
  }
}

function freezeDiagnostics(diagnostics: readonly ExtensionDiagnostic[] | undefined): readonly ExtensionDiagnostic[] {
  return Object.freeze([...(diagnostics ?? [])].map((diagnostic) => Object.freeze({ ...diagnostic })));
}

function freezeRenderability(
  renderability: EffectRegistryRecord['renderability'],
): EffectRegistryRecord['renderability'] {
  return Object.freeze({
    ...renderability,
    capabilities: Object.freeze(
      renderability.capabilities.map((capability) => Object.freeze({ ...capability })),
    ),
    ...(renderability.blockers
      ? {
          blockers: Object.freeze(
            renderability.blockers.map((blocker) => Object.freeze({ ...blocker })),
          ),
        }
      : {}),
  });
}

function freezeRecord(record: EffectRegistryRecord): EffectRegistryRecord {
  return Object.freeze({
    ...record,
    renderability: freezeRenderability(record.renderability),
    ...(record.diagnostics ? { diagnostics: freezeDiagnostics(record.diagnostics) } : {}),
  });
}

function sortEntries(entries: InternalRecord[]): InternalRecord[] {
  return [...entries].sort((a, b) => {
    const ownerA = a.record.ownerExtensionId ?? '';
    const ownerB = b.record.ownerExtensionId ?? '';
    const ownerCmp = ownerA.localeCompare(ownerB);
    if (ownerCmp !== 0) return ownerCmp;
    return a.record.effectId.localeCompare(b.record.effectId);
  });
}

export function createEffectRegistry(): EffectRegistry {
  const records = new Map<string, InternalRecord>();
  const subscribers = new Set<EffectRegistrySubscriber>();
  const diagnostics: ExtensionDiagnostic[] = [];

  let frozenSnapshot: EffectRegistrySnapshot | null = null;
  let disposed = false;

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function getSnapshot(): EffectRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const snapshotRecords = Object.freeze(
      sortEntries([...records.values()]).map((entry) => entry.record),
    );

    frozenSnapshot = Object.freeze({
      records: snapshotRecords,
      diagnostics: Object.freeze([...diagnostics]),
      get: (effectId: string) => records.get(effectId)?.record,
      has: (effectId: string) => records.has(effectId),
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
      'effect-registry/disposed',
      `EffectRegistry operation "${operation}" called after dispose.`,
    );
    invalidateSnapshot();
    return true;
  }

  function removeEntry(effectId: string, expectedToken?: symbol): void {
    const existing = records.get(effectId);
    if (!existing || (expectedToken && existing.token !== expectedToken)) return;

    records.delete(effectId);
    safeDispose(existing, diagnostics);
    invalidateSnapshot();
    notifySubscribers();
  }

  function register(record: EffectRegistryRecord): DisposeHandle {
    if (guardDisposed('register')) {
      return { dispose(): void {} };
    }

    const frozenRecord = freezeRecord(record);
    const existing = records.get(frozenRecord.effectId);

    if (existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'effect-registry/duplicate-effect',
        `Effect "${frozenRecord.effectId}" is already registered. The previous record will be replaced.`,
        frozenRecord.ownerExtensionId,
        frozenRecord.contributionId,
        {
          effectId: frozenRecord.effectId,
          previousOwnerExtensionId: existing.record.ownerExtensionId,
          previousContributionId: existing.record.contributionId,
        },
      );
      safeDispose(existing, diagnostics);
    }

    const token = Symbol(frozenRecord.effectId);
    records.set(frozenRecord.effectId, {
      token,
      record: frozenRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(frozenRecord.effectId, token);
      },
    };
  }

  function updateRecord(
    effectId: string,
    updater: (current: EffectRegistryRecord) => EffectRegistryRecord,
    newDispose?: EffectRegistryRecord['dispose'],
  ): DisposeHandle {
    if (guardDisposed('updateRecord')) {
      return { dispose(): void {} };
    }

    const existing = records.get(effectId);
    if (!existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'effect-registry/update-missing-effect',
        `Effect "${effectId}" cannot be updated because it is not registered.`,
        undefined,
        undefined,
        { effectId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    const nextRecord = freezeRecord({
      ...updater(existing.record),
      ...(newDispose ? { dispose: newDispose } : {}),
    });

    if (nextRecord.effectId !== effectId) {
      emitDiagnostic(
        diagnostics,
        'error',
        'effect-registry/update-effect-id-mismatch',
        `Effect "${effectId}" update returned mismatched effect ID "${nextRecord.effectId}".`,
        nextRecord.ownerExtensionId,
        nextRecord.contributionId,
        { effectId, nextEffectId: nextRecord.effectId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    safeDispose(existing, diagnostics);

    const token = Symbol(effectId);
    records.set(effectId, {
      token,
      record: nextRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(effectId, token);
      },
    };
  }

  function unregister(effectId: string): void {
    if (guardDisposed('unregister')) return;
    removeEntry(effectId);
  }

  function unregisterOwner(ownerExtensionId: string): void {
    if (guardDisposed('unregisterOwner')) return;

    const owned = [...records.values()].filter(
      (entry) => entry.record.ownerExtensionId === ownerExtensionId,
    );
    if (owned.length === 0) return;

    owned.forEach((entry) => {
      records.delete(entry.record.effectId);
      safeDispose(entry, diagnostics);
    });

    invalidateSnapshot();
    notifySubscribers();
  }

  function resolve(effectId: string): EffectRegistryRecord | undefined {
    return records.get(effectId)?.record;
  }

  function subscribe(subscriber: EffectRegistrySubscriber): DisposeHandle {
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
    unregisterOwner,
    resolve,
    subscribe,
    getSnapshot,
    dispose,
  };
}
