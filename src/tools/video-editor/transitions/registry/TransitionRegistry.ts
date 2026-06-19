import type { DiagnosticSeverity, DisposeHandle, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  TransitionRegistry,
  TransitionRegistryRecord,
  TransitionRegistrySnapshot,
  TransitionRegistrySubscriber,
} from '@/tools/video-editor/transitions/registry/types.ts';

interface InternalRecord {
  readonly token: symbol;
  readonly record: TransitionRegistryRecord;
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
      'transition-registry/dispose-failed',
      `Transition "${entry.record.transitionId}" dispose failed: ${String(error)}`,
      entry.record.ownerExtensionId,
      entry.record.contributionId,
      { transitionId: entry.record.transitionId },
    );
  }
}

function freezeDiagnostics(diagnostics: readonly ExtensionDiagnostic[] | undefined): readonly ExtensionDiagnostic[] {
  return Object.freeze([...(diagnostics ?? [])].map((diagnostic) => Object.freeze({ ...diagnostic })));
}

function freezeRenderability(
  renderability: TransitionRegistryRecord['renderability'],
): TransitionRegistryRecord['renderability'] {
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

function freezeRecord(record: TransitionRegistryRecord): TransitionRegistryRecord {
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
    return a.record.transitionId.localeCompare(b.record.transitionId);
  });
}

export function createTransitionRegistry(): TransitionRegistry {
  const records = new Map<string, InternalRecord>();
  const subscribers = new Set<TransitionRegistrySubscriber>();
  const diagnostics: ExtensionDiagnostic[] = [];

  let frozenSnapshot: TransitionRegistrySnapshot | null = null;
  let disposed = false;

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function getSnapshot(): TransitionRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const snapshotRecords = Object.freeze(
      sortEntries([...records.values()]).map((entry) => entry.record),
    );

    frozenSnapshot = Object.freeze({
      records: snapshotRecords,
      diagnostics: Object.freeze([...diagnostics]),
      get: (transitionId: string) => records.get(transitionId)?.record,
      has: (transitionId: string) => records.has(transitionId),
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
      'transition-registry/disposed',
      `TransitionRegistry operation "${operation}" called after dispose.`,
    );
    invalidateSnapshot();
    return true;
  }

  function removeEntry(transitionId: string, expectedToken?: symbol): void {
    const existing = records.get(transitionId);
    if (!existing || (expectedToken && existing.token !== expectedToken)) return;

    records.delete(transitionId);
    safeDispose(existing, diagnostics);
    invalidateSnapshot();
    notifySubscribers();
  }

  function register(record: TransitionRegistryRecord): DisposeHandle {
    if (guardDisposed('register')) {
      return { dispose(): void {} };
    }

    const frozenRecord = freezeRecord(record);
    const existing = records.get(frozenRecord.transitionId);

    if (existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'transition-registry/duplicate-transition',
        `Transition "${frozenRecord.transitionId}" is already registered. The previous record will be replaced.`,
        frozenRecord.ownerExtensionId,
        frozenRecord.contributionId,
        {
          transitionId: frozenRecord.transitionId,
          previousOwnerExtensionId: existing.record.ownerExtensionId,
          previousContributionId: existing.record.contributionId,
        },
      );
      safeDispose(existing, diagnostics);
    }

    const token = Symbol(frozenRecord.transitionId);
    records.set(frozenRecord.transitionId, {
      token,
      record: frozenRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(frozenRecord.transitionId, token);
      },
    };
  }

  function updateRecord(
    transitionId: string,
    updater: (current: TransitionRegistryRecord) => TransitionRegistryRecord,
    newDispose?: TransitionRegistryRecord['dispose'],
  ): DisposeHandle {
    if (guardDisposed('updateRecord')) {
      return { dispose(): void {} };
    }

    const existing = records.get(transitionId);
    if (!existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'transition-registry/update-missing-transition',
        `Transition "${transitionId}" cannot be updated because it is not registered.`,
        undefined,
        undefined,
        { transitionId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    const nextRecord = freezeRecord({
      ...updater(existing.record),
      ...(newDispose ? { dispose: newDispose } : {}),
    });

    if (nextRecord.transitionId !== transitionId) {
      emitDiagnostic(
        diagnostics,
        'error',
        'transition-registry/update-transition-id-mismatch',
        `Transition "${transitionId}" update returned mismatched transition ID "${nextRecord.transitionId}".`,
        nextRecord.ownerExtensionId,
        nextRecord.contributionId,
        { transitionId, nextTransitionId: nextRecord.transitionId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    safeDispose(existing, diagnostics);

    const token = Symbol(transitionId);
    records.set(transitionId, {
      token,
      record: nextRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(transitionId, token);
      },
    };
  }

  function unregister(transitionId: string): void {
    if (guardDisposed('unregister')) return;
    removeEntry(transitionId);
  }

  function unregisterOwner(ownerExtensionId: string): void {
    if (guardDisposed('unregisterOwner')) return;

    const owned = [...records.values()].filter(
      (entry) => entry.record.ownerExtensionId === ownerExtensionId,
    );
    if (owned.length === 0) return;

    owned.forEach((entry) => {
      records.delete(entry.record.transitionId);
      safeDispose(entry, diagnostics);
    });

    invalidateSnapshot();
    notifySubscribers();
  }

  function resolve(transitionId: string): TransitionRegistryRecord | undefined {
    return records.get(transitionId)?.record;
  }

  function subscribe(subscriber: TransitionRegistrySubscriber): DisposeHandle {
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
