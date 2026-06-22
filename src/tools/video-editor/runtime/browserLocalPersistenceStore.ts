/**
 * Browser-local FullSnapshotStore implementation (T7).
 *
 * Splits the cached extension state snapshot across two browser storage
 * mechanisms per SD2:
 *
 * - **localStorage** — carries the small parts of the snapshot (meta,
 *   packs, enablement, overrides, settings, events, lock).  Keyed by
 *   `reigh.ext-state.{userId}.{timelineId}`.
 * - **IndexedDB** — carries proposal payloads which can be large.
 *   Database `reigh.ext-proposals`, object store `proposals`, scoped
 *   by a composite `scopeKey` field.
 *
 * ## Malformed data handling
 *
 * On `loadSnapshot()` the store validates the localStorage JSON before
 * combining it with IndexedDB proposals.  If the localStorage JSON is
 * unparseable or the root is not a plain object, the method **throws**
 * a descriptive error.  The cache ({@link CachedExtensionStateRepository})
 * catches the error, emits a hydration diagnostic, and enters its
 * fail-closed state — no partial state is exposed and the corrupt data
 * is never treated as a first-run empty state.
 *
 * ## IndexedDB patterns
 *
 * Follows the same connection/transaction/recovery patterns as
 * `extensionStateRepositoryIndexedDB.ts`, which has passing tests with
 * fake-indexeddb.
 */

import type { FullSnapshotStore } from './extensionPersistenceCache';
import type {
  ExtensionPersistenceScope,
  ExtensionPersistenceService,
  ExtensionProposal,
} from '../data/DataProvider';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import { createCachedExtensionPersistenceService } from './extensionPersistenceCache';

// ---------------------------------------------------------------------------
// localStorage key
// ---------------------------------------------------------------------------

/**
 * Namespaced localStorage key scoped by userId and timelineId.
 *
 * Example: `reigh.ext-state.alice.timeline-001`
 */
function localStorageKey(scope: ExtensionPersistenceScope): string {
  return `reigh.ext-state.${scope.userId}.${scope.timelineId}`;
}

// ---------------------------------------------------------------------------
// IndexedDB helpers (follows extensionStateRepositoryIndexedDB.ts exactly)
// ---------------------------------------------------------------------------

const PROPOSAL_DB_NAME = 'reigh.ext-proposals';
const PROPOSAL_DB_VERSION = 1;
const PROPOSAL_STORE = 'proposals';

interface ProposalRecord {
  /** Scoped record key: `{scopeKey}:{proposalId}` — used as IndexedDB keyPath. */
  id: string;
  /** The original proposal ID (without scope prefix). */
  proposalId: string;
  /** Composite scope key: `{userId}:{timelineId}` */
  scopeKey: string;
  extensionId: string;
  status: string;
  payload: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  label?: string;
}

function proposalScopeKey(scope: ExtensionPersistenceScope): string {
  return `${scope.userId}:${scope.timelineId}`;
}

function getIndexedDb(): IDBFactory {
  if (typeof indexedDB === 'undefined') {
    throw new Error('IndexedDB is not available in this environment');
  }
  return indexedDB;
}

function shouldRecover(error: unknown): boolean {
  if (error instanceof DOMException) {
    return [
      'AbortError',
      'InvalidStateError',
      'NotFoundError',
      'UnknownError',
      'VersionError',
    ].includes(error.name);
  }
  return false;
}

function openProposalDatabase(): Promise<IDBDatabase> {
  const indexedDb = getIndexedDb();
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDb.open(PROPOSAL_DB_NAME, PROPOSAL_DB_VERSION);

    request.addEventListener('upgradeneeded', () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(PROPOSAL_STORE)) {
        db.createObjectStore(PROPOSAL_STORE, { keyPath: 'id' });
      }
    });

    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () =>
      reject(request.error ?? new Error('Failed to open proposal IndexedDB')),
    );
    request.addEventListener('blocked', () =>
      reject(new Error('Proposal IndexedDB open blocked')),
    );
  });
}

async function deleteProposalDatabase(): Promise<void> {
  const indexedDb = getIndexedDb();
  return new Promise<void>((resolve, reject) => {
    const req = indexedDb.deleteDatabase(PROPOSAL_DB_NAME);
    req.addEventListener('success', () => resolve());
    req.addEventListener('error', () =>
      reject(req.error ?? new Error('Failed to delete proposal IndexedDB')),
    );
    req.addEventListener('blocked', () =>
      reject(new Error('Proposal IndexedDB delete blocked')),
    );
  });
}

async function withProposalStore<T>(
  mode: IDBTransactionMode,
  execute: (store: IDBObjectStore) => IDBRequest<T>,
  { allowRecovery = true }: { allowRecovery?: boolean } = {},
): Promise<T> {
  let database: IDBDatabase | null = null;
  try {
    database = await openProposalDatabase();
    return await new Promise<T>((resolve, reject) => {
      let settled = false;
      const transaction = database!.transaction(PROPOSAL_STORE, mode);
      const store = transaction.objectStore(PROPOSAL_STORE);
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
      request.addEventListener('error', () =>
        fail(request.error ?? new Error('Proposal IndexedDB request failed')),
      );
      transaction.addEventListener('abort', () =>
        fail(transaction.error ?? new Error('Proposal IndexedDB transaction aborted')),
      );
      transaction.addEventListener('error', () =>
        fail(transaction.error ?? new Error('Proposal IndexedDB transaction failed')),
      );
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
    await deleteProposalDatabase();
    return withProposalStore(mode, execute, { allowRecovery: false });
  }
}

// ---------------------------------------------------------------------------
// Proposal CRUD helpers (scope-filtered)
// ---------------------------------------------------------------------------

/**
 * Load all proposals for the given scope from IndexedDB.
 *
 * On error (IndexedDB unavailable) returns an empty record — proposals
 * are best-effort; the base state in localStorage is the authoritative
 * source for non-proposal fields.
 */
async function loadAllProposals(
  scope: ExtensionPersistenceScope,
): Promise<Record<string, ExtensionProposal>> {
  try {
    const records = await withProposalStore<ProposalRecord[]>(
      'readonly',
      (s) => s.getAll(),
    );
    const sk = proposalScopeKey(scope);
    const result: Record<string, ExtensionProposal> = {};
    for (const record of records) {
      if (record.scopeKey === sk) {
        result[record.proposalId] = {
          id: record.proposalId,
          extensionId: record.extensionId,
          status: record.status as ExtensionProposal['status'],
          payload: record.payload,
          createdAt: record.createdAt,
          updatedAt: record.updatedAt,
          ...(record.label !== undefined ? { label: record.label } : {}),
        };
      }
    }
    return result;
  } catch {
    // IndexedDB unavailable — return empty, proposals are best-effort
    return {};
  }
}

/**
 * Persist all proposals for the given scope to IndexedDB.
 *
 * Uses a delete-then-insert strategy for simplicity: all existing
 * proposals for this scope are removed, then the current set is
 * written.  This avoids diffing.
 *
 * On error (quota / unavailable) the operation is a silent no-op.
 * Proposal loss is acceptable because the base state in localStorage
 * remains consistent, and the cache will retry on the next flush.
 */
async function saveAllProposals(
  scope: ExtensionPersistenceScope,
  proposals: Record<string, ExtensionProposal>,
): Promise<void> {
  try {
    const sk = proposalScopeKey(scope);

    // Delete existing proposals for this scope
    const existing = await withProposalStore<ProposalRecord[]>(
      'readonly',
      (s) => s.getAll(),
    );
    const toDelete = existing
      .filter((r) => r.scopeKey === sk)
      .map((r) => r.id);

    for (const id of toDelete) {
      await withProposalStore('readwrite', (s) => s.delete(id));
    }

    // Insert current proposals (keyed by scopeKey:proposalId)
    for (const proposal of Object.values(proposals)) {
      const record: ProposalRecord = {
        id: `${sk}:${proposal.id}`,
        proposalId: proposal.id,
        scopeKey: sk,
        extensionId: proposal.extensionId,
        status: proposal.status,
        payload: proposal.payload,
        createdAt: proposal.createdAt,
        updatedAt: proposal.updatedAt,
        ...(proposal.label !== undefined ? { label: proposal.label } : {}),
      };
      await withProposalStore('readwrite', (s) => s.put(record));
    }
  } catch {
    // IndexedDB unavailable — silent no-op
  }
}

/**
 * Delete all proposals for the given scope from IndexedDB.
 */
async function deleteAllProposals(
  scope: ExtensionPersistenceScope,
): Promise<void> {
  try {
    const sk = proposalScopeKey(scope);
    const existing = await withProposalStore<ProposalRecord[]>(
      'readonly',
      (s) => s.getAll(),
    );
    const toDelete = existing
      .filter((r) => r.scopeKey === sk)
      .map((r) => r.id);

    for (const id of toDelete) {
      await withProposalStore('readwrite', (s) => s.delete(id));
    }
  } catch {
    // IndexedDB unavailable — silent no-op
  }
}

// ---------------------------------------------------------------------------
// BrowserLocalFullSnapshotStore
// ---------------------------------------------------------------------------

/**
 * A {@link FullSnapshotStore} that persists the cached extension state
 * snapshot across browser-local mechanisms.
 *
 * - **localStorage** stores the snapshot **without** proposals (meta,
 *   packs, enablement, overrides, settings, events, lock).
 * - **IndexedDB** stores proposal payloads keyed by proposal ID and
 *   filtered by a composite `scopeKey`.
 *
 * ## Malformed JSON → fail-closed
 *
 * `loadSnapshot()` validates the localStorage JSON before combining it
 * with IndexedDB proposals.  If the stored JSON cannot be parsed or the
 * root is not a plain object, the method **throws** a descriptive error.
 * The cache (CachedExtensionStateRepository) catches the error, emits a
 * hydration diagnostic, and enters its fail-closed state.  This ensures
 * corrupt local data is never mistaken for a first-run empty state and
 * no partial state is exposed.
 */
export class BrowserLocalFullSnapshotStore implements FullSnapshotStore {
  private readonly _scope: ExtensionPersistenceScope;

  constructor(scope: ExtensionPersistenceScope) {
    this._scope = scope;
  }

  // -------------------------------------------------------------------
  // FullSnapshotStore
  // -------------------------------------------------------------------

  async loadSnapshot(): Promise<string | null> {
    const key = localStorageKey(this._scope);

    // 1. Read base state from localStorage
    let baseRaw: string | null = null;
    try {
      baseRaw = localStorage.getItem(key);
    } catch {
      // localStorage unavailable — treat as empty
      return null;
    }

    if (baseRaw === null || baseRaw === undefined) {
      // No snapshot has ever been saved for this scope
      return null;
    }

    // 2. Validate the stored JSON (fail-closed on malformed data)
    let base: Record<string, unknown>;
    try {
      base = JSON.parse(baseRaw);
      if (base === null || typeof base !== 'object' || Array.isArray(base)) {
        // Malformed root — fail-closed so the cache emits a diagnostic
        throw new Error(
          'Browser-local extension state snapshot root is not a plain object',
        );
      }
    } catch (error: unknown) {
      // Parse error — malformed data, fail-closed so the cache emits a diagnostic
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Browser-local extension state snapshot is malformed: ${message}`,
      );
    }

    // 3. Load proposals from IndexedDB and merge
    const proposals = await loadAllProposals(this._scope);
    base.proposals = proposals;

    return JSON.stringify(base);
  }

  async saveSnapshot(serialized: string): Promise<void> {
    // Parse the full snapshot
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(serialized);
    } catch {
      // The cache always serializes valid JSON — this guard is defensive
      return;
    }

    // Extract proposals (stored in IndexedDB)
    const proposals =
      (parsed.proposals as Record<string, ExtensionProposal>) ?? {};

    // Remove proposals from the base state (stored in localStorage)
    const { proposals: _proposals, ...base } = parsed;

    // 4. Save base state to localStorage
    try {
      const baseSerialized = JSON.stringify(base);
      localStorage.setItem(localStorageKey(this._scope), baseSerialized);
    } catch {
      // localStorage quota exceeded or unavailable
      // Proposals are still saved below (best-effort)
    }

    // 5. Save proposals to IndexedDB
    await saveAllProposals(this._scope, proposals);
  }

  async deleteSnapshot(): Promise<void> {
    // Clear localStorage key
    try {
      localStorage.removeItem(localStorageKey(this._scope));
    } catch {
      // localStorage unavailable — silent no-op
    }

    // Clear IndexedDB proposals for this scope
    await deleteAllProposals(this._scope);
  }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a browser-local {@link ExtensionPersistenceService} for the given
 * scope.
 *
 * This is the **single factory entry point** per SD1.  It wires a
 * {@link BrowserLocalFullSnapshotStore} into the shared cache-backed
 * persistence service so callers get the full
 * {@link ExtensionPersistenceService} contract including proposals.
 *
 * @param scope        The user + timeline scope for all persistence operations.
 * @param diagnostics  Optional output array for cache diagnostics.
 * @returns A ready-to-initialize extension persistence service backed by
 *          browser-local storage.
 */
export function createBrowserLocalExtensionPersistenceService(
  scope: ExtensionPersistenceScope,
  diagnostics?: ExtensionDiagnostic[],
): ExtensionPersistenceService {
  const store = new BrowserLocalFullSnapshotStore(scope);
  return createCachedExtensionPersistenceService(store, diagnostics, scope);
}
