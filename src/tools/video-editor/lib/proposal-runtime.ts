/**
 * ProposalRuntime — provider-scoped, in-memory proposal lifecycle manager.
 *
 * Manages TimelineProposal state transitions (pending → accepted/rejected/stale),
 * subscription notifications, preview against current reader snapshots, and
 * acceptance through TimelineOps with base-version revalidation.
 *
 * @publicContract — implements the ProposalRuntime interface from the SDK.
 *   Accept always applies through TimelineOps; never bypasses commitData/history.
 */

import type {
  ProposalRuntime,
  TimelineProposal,
  TimelineProposalInput,
  ProposalState,
  ProposalListener,
  TimelinePreviewResult,
  TimelineDiff,
  DisposeHandle,
  ProposalExpiryDetail,
  ProposalEnvelope,
  ProposalImportResult,
  ProposalImportStatus,
  ProposalImportDiagnostic,
} from '@/sdk/index';
import type { TimelineOps } from '@/sdk/index';
import type { TimelineReader } from '@/sdk/index';

import { validateTimelinePatch } from './timeline-patch';

// ---------------------------------------------------------------------------
// Persistence provider (lightweight bridge to DataProvider proposal CRUD)
// ---------------------------------------------------------------------------

/** Minimal proposal record shape used by the runtime persistence bridge. */
export interface ProposalPersistenceRecord {
  readonly id: string;
  readonly source: string;
  readonly state: string;
  readonly rationale?: string;
  readonly baseVersion: number;
  readonly expiresAt?: number;
  readonly createdAt: number;
  readonly updatedAt: number;
  readonly patch: Record<string, unknown>;
  readonly diagnostics?: readonly Record<string, unknown>[];
  readonly expiryDetail?: Record<string, unknown>;
}

/** Lightweight proposal persistence provider accepted by ProposalRuntime. */
export interface ProposalPersistenceProvider {
  /** Persist a new proposal record. Returns the created record ID. */
  createProposal(record: Omit<ProposalPersistenceRecord, 'id'>): Promise<string>;

  /** Update the status (and optional detail) of an existing proposal. */
  updateProposalStatus(
    id: string,
    status: string,
    detail?: Record<string, unknown>,
  ): Promise<void>;

  /** Load all proposal records for the current scope. */
  loadAllProposals(): Promise<ProposalPersistenceRecord[]>;
}

// ---------------------------------------------------------------------------
// Bridge: ExtensionPersistenceService → ProposalPersistenceProvider
// ---------------------------------------------------------------------------

/**
 * Minimal subset of ExtensionPersistenceService needed by the bridge.
 * Avoids a hard import of DataProvider.ts from the lib layer.
 */
export interface ProposalServiceBridge {
  readonly capabilities: { readonly proposals: boolean };
  createProposal?(record: {
    extensionId: string;
    status: string;
    payload: Record<string, unknown>;
    title?: string;
    detail?: Record<string, unknown>;
    baseVersion?: number;
    expiresAt?: number;
    acceptedAt?: string;
    rejectedAt?: string;
  }): Promise<{ id: string } | string>;
  updateProposalStatus?(
    id: string,
    status: string,
    detail?: Record<string, unknown>,
  ): Promise<{ id: string } | void>;
  queryProposals?(query: {
    extensionId?: string;
    statuses?: readonly string[];
  }): Promise<Array<{
    id: string;
    extensionId: string;
    status: string;
    payload: Record<string, unknown>;
    detail?: Record<string, unknown>;
    baseVersion?: number;
    expiresAt?: number;
    createdAt: string;
    updatedAt: string;
  }>>;
}

/**
 * Adapt an {@link ProposalServiceBridge} (typically an
 * {@link ExtensionPersistenceService}) into a {@link ProposalPersistenceProvider}
 * consumable by {@link createProposalRuntime}.
 *
 * Proposals are stored with `extensionId = 'ai-timeline-agent'` and the
 * patch/state/version fields are carried in the payload so the runtime can
 * reconstruct them on hydration.
 */
export function createProposalPersistenceBridge(
  service: ProposalServiceBridge,
): ProposalPersistenceProvider {
  const EXTENSION_ID = 'ai-timeline-agent';

  return {
    async createProposal(
      record: Omit<ProposalPersistenceRecord, 'id'>,
    ): Promise<string> {
      if (!service.createProposal) {
        throw new Error('Proposal creation not supported by this provider');
      }
      const result = await service.createProposal({
        extensionId: EXTENSION_ID,
        status: record.state,
        payload: {
          source: record.source,
          rationale: record.rationale,
          baseVersion: record.baseVersion,
          patch: record.patch,
          state: record.state,
          createdAt: record.createdAt,
          updatedAt: record.updatedAt,
          ...(record.diagnostics ? { diagnostics: record.diagnostics } : {}),
          ...(record.expiryDetail ? { expiryDetail: record.expiryDetail } : {}),
        },
        ...(typeof record.rationale === 'string' ? { title: record.rationale.slice(0, 200) } : {}),
        baseVersion: record.baseVersion,
        expiresAt: record.expiresAt,
      });
      return typeof result === 'string' ? result : result.id;
    },

    async updateProposalStatus(
      id: string,
      status: string,
      detail?: Record<string, unknown>,
    ): Promise<void> {
      if (!service.updateProposalStatus) {
        throw new Error('Proposal status updates not supported by this provider');
      }
      await service.updateProposalStatus(id, status, detail);
    },

    async loadAllProposals(): Promise<ProposalPersistenceRecord[]> {
      if (!service.queryProposals) {
        return [];
      }
      const records = await service.queryProposals({
        extensionId: EXTENSION_ID,
        statuses: ['pending'],
      });
      return records.map((r) => {
        const p = r.payload ?? {};
        return {
          id: r.id,
          source: typeof p.source === 'string' ? p.source : r.extensionId,
          state: r.status,
          rationale: typeof p.rationale === 'string' ? p.rationale : undefined,
          baseVersion:
            typeof p.baseVersion === 'number'
              ? p.baseVersion
              : r.baseVersion ?? 1,
          expiresAt: r.expiresAt,
          createdAt:
            typeof p.createdAt === 'number'
              ? p.createdAt
              : new Date(r.createdAt).getTime(),
          updatedAt:
            typeof p.updatedAt === 'number'
              ? p.updatedAt
              : new Date(r.updatedAt).getTime(),
          patch: (typeof p.patch === 'object' && p.patch !== null
            ? p.patch
            : {}) as Record<string, unknown>,
          diagnostics: Array.isArray(p.diagnostics)
            ? (p.diagnostics as readonly Record<string, unknown>[])
            : undefined,
          expiryDetail:
            typeof p.expiryDetail === 'object' && p.expiryDetail !== null
              ? (p.expiryDetail as Record<string, unknown>)
              : undefined,
        };
      });
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let nextProposalId = 0;

/** Generate a unique proposal ID. */
function generateProposalId(): string {
  nextProposalId += 1;
  return `proposal-${nextProposalId}-${Date.now().toString(36)}`;
}

/** Current epoch milliseconds. */
function now(): number {
  return Date.now();
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateProposalRuntimeOptions {
  /** Stable TimelineOps adapter for applying accepted proposals. */
  timelineOps: TimelineOps;

  /** Stable TimelineReader for base-version checks and preview snapshots. */
  reader: TimelineReader;

  /**
   * Optional persistence provider for proposals.
   *
   * When provided, the runtime will hydrate proposals on construction and
   * persist create/reject/stale/expired transitions.  When absent or
   * explicitly `null`, proposals live in-memory only and a diagnostic is
   * surfaced through the `diagnostics` getter.
   */
  persistenceProvider?: ProposalPersistenceProvider | null;
}

/**
 * Create a provider-scoped, in-memory ProposalRuntime.
 *
 * ## replaceForSource semantics
 *
 * `create()` atomically replaces any existing pending proposal from the same
 * `source`.  This lets an extension or tool reissue a proposal without
 * accumulating duplicate pending entries.
 *
 * ## Stale detection on accept
 *
 * `accept()` re-reads the current version from the configured reader and
 * compares it against the proposal's `baseVersion`.  If they differ (and the
 * baseVersion is not 0, which means "no expectation"), the proposal is
 * marked `stale` and the accept is rejected with an error diagnostic.
 *
 * ## Apply-only-through-TimelineOps
 *
 * `accept()` applies the proposal's patch exclusively through the
 * `timelineOps.apply()` path.  It never manipulates TimelineData directly
 * or bypasses commitData/history.
 */
export function createProposalRuntime(
  options: CreateProposalRuntimeOptions,
): ProposalRuntime {
  const { timelineOps, reader, persistenceProvider } = options;

  // ── State ──────────────────────────────────────────────────────────────

  /** Map of proposal ID → proposal. */
  const proposals = new Map<string, TimelineProposal>();

  /** Registered listeners. */
  const listeners = new Set<ProposalListener>();

  /** Whether persistence is explicitly unavailable. */
  const persistenceUnsupported = persistenceProvider === null;

  /** Accumulated diagnostics (unsupported-provider, etc.). */
  const runtimeDiagnostics: Array<{
    severity: string;
    code: string;
    message: string;
    proposalId?: string;
    proposalIndex?: number;
  }> = [];

  if (persistenceUnsupported) {
    runtimeDiagnostics.push({
      severity: 'warning',
      code: 'proposal/persistence-unsupported',
      message:
        'Proposal persistence is unavailable with the current provider. ' +
        'Proposals will be lost on page refresh.',
    });
  }

  // ── Persistence helpers ────────────────────────────────────────────────

  async function persistCreate(proposal: TimelineProposal): Promise<void> {
    if (!persistenceProvider) return;
    try {
      await persistenceProvider.createProposal({
        source: proposal.source,
        state: proposal.state,
        rationale: proposal.rationale,
        baseVersion: proposal.baseVersion,
        expiresAt: proposal.expiresAt,
        createdAt: proposal.createdAt,
        updatedAt: proposal.updatedAt,
        patch: proposal.patch as unknown as Record<string, unknown>,
        diagnostics: proposal.diagnostics as readonly Record<string, unknown>[] | undefined,
      });
    } catch {
      // Persistence failures are non-fatal for proposal operations.
      // Diagnostics already captured via runtimeDiagnostics.
    }
  }

  async function persistTransition(
    id: string,
    state: ProposalState,
    detail?: Record<string, unknown>,
  ): Promise<void> {
    if (!persistenceProvider) return;
    try {
      await persistenceProvider.updateProposalStatus(id, state, detail);
    } catch {
      // Non-fatal.
    }
  }

  // ── Notification ───────────────────────────────────────────────────────

  function notify(proposal: TimelineProposal): void {
    for (const listener of listeners) {
      try {
        listener(proposal);
      } catch {
        // Silently drop listener errors so one broken listener doesn't
        // prevent others from receiving notifications.
      }
    }
  }

  // ── State transitions ──────────────────────────────────────────────────

  function transition(
    proposal: TimelineProposal,
    nextState: ProposalState,
    overrides?: Partial<Pick<TimelineProposal, 'previewDiff' | 'previewable' | 'diagnostics' | 'expiryDetail'>>,
  ): TimelineProposal {
    const updated: TimelineProposal = {
      ...proposal,
      ...overrides,
      state: nextState,
      updatedAt: now(),
    };

    proposals.set(updated.id, updated);
    notify(updated);

    // Persist the transition
    const detail =
      updated.expiryDetail
        ? (updated.expiryDetail as unknown as Record<string, unknown>)
        : undefined;
    void persistTransition(updated.id, nextState, detail);

    return updated;
  }

  // ── Auto-expiry check ──────────────────────────────────────────────────

  /**
   * Check all pending proposals and expire any whose TTL has elapsed.
   * Called automatically before list() and get() so consumers never see
   * expired proposals as pending.
   */
  function autoExpire(): void {
    const nowMs = now();
    for (const [, proposal] of proposals) {
      if (proposal.state !== 'pending') continue;
      if (proposal.expiresAt === undefined) continue;
      if (proposal.expiresAt > nowMs) continue;

      // TTL has elapsed — mark expired
      const expiryDetail: ProposalExpiryDetail = {
        reason: 'ttl-elapsed',
        baseVersion: proposal.baseVersion,
        currentVersion: reader.snapshot().currentVersion,
        createdAt: proposal.createdAt,
        expiredAt: nowMs,
        ttlMs: proposal.expiresAt - proposal.createdAt,
      };

      transition(proposal, 'expired', { expiryDetail });
    }
  }

  // ── subscribe ──────────────────────────────────────────────────────────

  function subscribe(listener: ProposalListener): DisposeHandle {
    listeners.add(listener);

    let disposed = false;
    return {
      dispose(): void {
        if (!disposed) {
          disposed = true;
          listeners.delete(listener);
        }
      },
    };
  }

  // ── create (with replaceForSource) ─────────────────────────────────────

  function create(input: TimelineProposalInput): TimelineProposal {
    // Atomically replace any existing pending proposal from the same source.
    for (const [id, existing] of proposals) {
      if (existing.source === input.source && existing.state === 'pending') {
        proposals.delete(id);
        // Only need to delete the first match — replaceForSource ensures
        // at most one pending per source.
        break;
      }
    }

    const proposal: TimelineProposal = {
      id: generateProposalId(),
      source: input.source,
      rationale: input.rationale,
      state: 'pending',
      patch: input.patch,
      baseVersion: input.baseVersion,
      previewable: false,
      createdAt: now(),
      updatedAt: now(),
    };

    proposals.set(proposal.id, proposal);

    // Persist the new proposal
    void persistCreate(proposal);

    // Attempt an initial preview so the proposal immediately carries
    // a previewDiff and previewable flag for UI consumption.
    try {
      const result = preview(proposal.id);
      // preview() already updates the stored proposal in-place and notifies.
      // We just need to return the latest stored version.
      const updated = proposals.get(proposal.id);
      if (updated) {
        return updated;
      }
    } catch {
      // If preview fails (e.g. no data loaded), leave the proposal as-is
      // without a previewDiff.
    }

    notify(proposal);
    return proposal;
  }

  // ── preview ────────────────────────────────────────────────────────────

  function preview(proposalId: string): TimelinePreviewResult {
    const proposal = proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`ProposalRuntime.preview: proposal "${proposalId}" not found.`);
    }

    const result = timelineOps.preview(proposal.patch);

    // Update the proposal in-place with preview results.
    transition(proposal, proposal.state, {
      previewDiff: result.diff,
      previewable: result.fullyPreviewable,
      diagnostics: result.diagnostics.length > 0 ? result.diagnostics : undefined,
    });

    return result;
  }

  // ── accept ─────────────────────────────────────────────────────────────

  function accept(proposalId: string): TimelineDiff {
    // Auto-expire any TTL-elapsed proposals before checking state.
    // This ensures that proposals whose expiresAt has passed cannot be
    // accepted even when get()/list() haven't been called recently.
    autoExpire();

    const proposal = proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`ProposalRuntime.accept: proposal "${proposalId}" not found.`);
    }

    if (proposal.state !== 'pending') {
      throw new Error(
        `ProposalRuntime.accept: proposal "${proposalId}" is in "${proposal.state}" state. ` +
        `Only pending proposals can be accepted.`,
      );
    }

    // ── Base-version revalidation ──────────────────────────────────────
    const currentSnap = reader.snapshot();
    const currentVersion = currentSnap.currentVersion;

    // Version 0 means "no base-version expectation" (e.g. initial proposals
    // before the first provider load, or extensions that intentionally
    // bypass version gating).
    if (proposal.baseVersion !== 0 && proposal.baseVersion !== currentVersion) {
      // Mark the proposal stale so consumers can observe the transition.
      const expiryDetail: ProposalExpiryDetail = {
        reason: 'base-version-mismatch',
        baseVersion: proposal.baseVersion,
        currentVersion,
        createdAt: proposal.createdAt,
        expiredAt: now(),
      };

      transition(proposal, 'stale', {
        diagnostics: [
          {
            severity: 'error',
            code: 'timeline-patch/stale-base-version' as const,
            message:
              `Cannot accept proposal "${proposalId}": baseVersion ` +
              `(${proposal.baseVersion}) does not match current timeline ` +
              `version (${currentVersion}). The proposal is now stale. ` +
              `Re-snapshot the current state and create a new proposal.`,
          },
        ],
        expiryDetail,
      });

      throw new Error(
        `ProposalRuntime.accept: proposal "${proposalId}" baseVersion ` +
        `(${proposal.baseVersion}) does not match current version ` +
        `(${currentVersion}). Proposal marked stale.`,
      );
    }

    // ── Apply through TimelineOps ──────────────────────────────────────
    const diff = timelineOps.apply(proposal.patch);

    // Mark accepted.
    transition(proposal, 'accepted');

    return diff;
  }

  // ── reject ─────────────────────────────────────────────────────────────

  function reject(proposalId: string, _reason?: string): void {
    const proposal = proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`ProposalRuntime.reject: proposal "${proposalId}" not found.`);
    }

    if (proposal.state !== 'pending') {
      throw new Error(
        `ProposalRuntime.reject: proposal "${proposalId}" is in "${proposal.state}" state. ` +
        `Only pending proposals can be rejected.`,
      );
    }

    transition(proposal, 'rejected');
  }

  // ── expireStale ────────────────────────────────────────────────────────

  function expireStale(maxAgeMs: number): readonly TimelineProposal[] {
    const nowMs = now();
    const expired: TimelineProposal[] = [];

    for (const [, proposal] of proposals) {
      if (proposal.state !== 'pending') continue;

      const age = nowMs - proposal.createdAt;
      // A value of 0 expires every pending proposal (per SDK contract).
      if (maxAgeMs !== 0 && age <= maxAgeMs) continue;

      const expiryDetail: ProposalExpiryDetail = {
        reason: 'ttl-elapsed',
        baseVersion: proposal.baseVersion,
        currentVersion: reader.snapshot().currentVersion,
        createdAt: proposal.createdAt,
        expiredAt: nowMs,
        ttlMs: maxAgeMs,
      };

      const updated = transition(proposal, 'expired', { expiryDetail });
      expired.push(updated);
    }

    return expired;
  }

  // ── get / list / currentVersion ────────────────────────────────────────

  function get(proposalId: string): TimelineProposal | undefined {
    // Auto-expire before returning so stale proposals are never seen as pending
    autoExpire();
    return proposals.get(proposalId);
  }

  function list(state?: ProposalState): readonly TimelineProposal[] {
    // Auto-expire before returning so stale proposals are never seen as pending
    autoExpire();
    const all = Array.from(proposals.values());
    if (state === undefined) {
      return all;
    }
    return all.filter((p) => p.state === state);
  }

  // ── Hydration from persistence provider ────────────────────────────────

  /**
   * Hydrate proposals from the configured persistence provider.
   * Called once during construction.  Pending proposals are loaded;
   * non-pending and expired proposals are skipped.
   */
  async function hydrateFromProvider(): Promise<void> {
    if (!persistenceProvider) return;

    try {
      const records = await persistenceProvider.loadAllProposals();
      for (const record of records) {
        // Only hydrate pending proposals (others are terminal/archived)
        if (record.state !== 'pending') continue;

        // Skip proposals that already exist (avoid duplicates on re-hydration)
        if (proposals.has(record.id)) continue;

        const proposal: TimelineProposal = {
          id: record.id,
          source: record.source,
          rationale: record.rationale,
          state: record.state as ProposalState,
          patch: record.patch as unknown as TimelineProposal['patch'],
          baseVersion: record.baseVersion,
          expiresAt: record.expiresAt,
          previewable: false,
          createdAt: record.createdAt,
          updatedAt: record.updatedAt,
          diagnostics: record.diagnostics as TimelineProposal['diagnostics'],
          expiryDetail: record.expiryDetail as TimelineProposal['expiryDetail'],
        };

        proposals.set(proposal.id, proposal);

        // Auto-expire if TTL has elapsed
        if (proposal.expiresAt !== undefined && proposal.expiresAt <= now()) {
          autoExpire();
        }
      }
    } catch {
      // Hydration failure is non-fatal; proposals remain in-memory only.
      runtimeDiagnostics.push({
        severity: 'warning',
        code: 'proposal/hydration-failed',
        message:
          'Failed to hydrate proposals from persistence provider. ' +
          'Proposals will be in-memory only.',
      });
    }
  }

  // ── Diagnostics getter ─────────────────────────────────────────────────

  function getDiagnostics(): Array<{
    severity: string;
    code: string;
    message: string;
    proposalId?: string;
    proposalIndex?: number;
  }> {
    return runtimeDiagnostics;
  }

  // ── importProposal (CANONICAL PUBLIC IMPORT API) ──────────────────────
  // M1-LOCKED: importProposal is the sole canonical public proposal import
  // API.  No importEnvelope alias exists or will be introduced — the name
  // contract is settled.  importEdgeProposals serves as the envelope-level
  // wrapper (see bottom of this file).
  //
  // M3: Import a pre-built TimelineProposal (e.g. from an edge response
  // envelope) into the runtime, preserving the server-assigned ID and all
  // fields.  Unlike create(), this does NOT auto-generate an ID, does NOT
  // apply replaceForSource semantics, and does NOT trigger an immediate
  // preview.
  //
  // M1 update: validates the proposal's patch through validateTimelinePatch,
  // rejects malformed proposals before persistence/notification, reports
  // duplicate IDs diagnostically (instead of silently skipping), and returns
  // a status indicator so callers (e.g. importEdgeProposals) can build a
  // structured ProposalImportResult.

  function importProposal(proposal: TimelineProposal): 'imported' | 'duplicate' | 'rejected' {
    // ── Validate required fields ───────────────────────────────────────
    if (!proposal.id || !proposal.source || !proposal.patch) {
      runtimeDiagnostics.push({
        severity: 'error',
        code: 'proposal/import-invalid-shape',
        message: `importProposal: proposal is missing required fields (id, source, or patch). Proposal not imported.`,
        proposalId: proposal.id || undefined,
      });
      return 'rejected';
    }

    // ── Validate patch structure through validateTimelinePatch ─────────
    // Reuse the canonical validator so we don't duplicate schema checks.
    // Only error-level diagnostics cause rejection; warnings (e.g. reserved
    // ops) are preserved as non-blocking diagnostics on the stored proposal.
    const patchValidation = validateTimelinePatch(proposal.patch);
    if (!patchValidation.valid) {
      for (const diag of patchValidation.diagnostics) {
        runtimeDiagnostics.push({
          severity: diag.severity,
          code: diag.code,
          message: diag.message,
          proposalId: proposal.id,
        });
      }
      return 'rejected';
    }

    // ── Duplicate detection ────────────────────────────────────────────
    // If a proposal with this ID already exists, skip (preserves first-write
    // semantics) but report the duplicate diagnostically instead of silently
    // returning.
    if (proposals.has(proposal.id)) {
      runtimeDiagnostics.push({
        severity: 'warning',
        code: 'proposal/import-duplicate-id',
        message: `importProposal: proposal with ID "${proposal.id}" already exists. Skipping duplicate.`,
        proposalId: proposal.id,
      });
      return 'duplicate';
    }

    // ── Normalize optional fields with defaults ────────────────────────
    // Collect any warning-level diagnostics from validateTimelinePatch
    // (e.g. reserved-op warnings) as proposal-level diagnostics.
    const patchWarnings = patchValidation.diagnostics.filter(
      (d) => d.severity !== 'error',
    );

    const normalized: TimelineProposal = {
      id: proposal.id,
      source: proposal.source,
      rationale: proposal.rationale,
      state: proposal.state === 'pending' ? 'pending' : proposal.state,
      patch: proposal.patch,
      baseVersion: proposal.baseVersion ?? 0,
      previewable: proposal.previewable ?? false,
      previewDiff: proposal.previewDiff,
      createdAt: proposal.createdAt ?? now(),
      updatedAt: proposal.updatedAt ?? now(),
      expiresAt: proposal.expiresAt,
      expiryDetail: proposal.expiryDetail,
      diagnostics:
        patchWarnings.length > 0
          ? [
              ...(proposal.diagnostics ?? []),
              ...patchWarnings.map((d) => ({
                severity: d.severity as 'error' | 'warning',
                code: d.code,
                message: d.message,
              })),
            ]
          : proposal.diagnostics,
    };

    proposals.set(normalized.id, normalized);

    // Auto-expire TTL proposals that have already elapsed
    if (normalized.state === 'pending' && normalized.expiresAt !== undefined && normalized.expiresAt <= now()) {
      autoExpire();
    }

    // Persist the imported proposal
    void persistCreate(normalized);

    // Notify listeners so UI (ProposalPanel) picks up the import
    notify(normalized);

    return 'imported';
  }

  // ── Kick off hydration ─────────────────────────────────────────────────

  void hydrateFromProvider();

  // ── Return ─────────────────────────────────────────────────────────────

  const runtime: ProposalRuntime & {
    diagnostics: Array<{
      severity: string;
      code: string;
      message: string;
      proposalId?: string;
      proposalIndex?: number;
    }>;
    importProposal(proposal: TimelineProposal): 'imported' | 'duplicate' | 'rejected';
  } = {
    subscribe,
    create,
    preview,
    accept,
    reject,
    expireStale,
    get,
    list,
    importProposal,
    get currentVersion(): number {
      return reader.snapshot().currentVersion;
    },
    get diagnostics() {
      return getDiagnostics();
    },
  };

  return runtime;
}

// ---------------------------------------------------------------------------
// M3: Edge proposal envelope import helper
// ---------------------------------------------------------------------------

/**
 * Import proposals from an edge {@link ProposalEnvelope} into a
 * {@link ProposalRuntime}.
 *
 * Preserves server-assigned IDs, baseVersion, rationale, operations, preview
 * state, and expiry.  Already-terminal proposals (accepted, rejected) are
 * skipped and diagnostically reported rather than silently dropped.
 *
 * M1 update: returns a structured {@link ProposalImportResult} with
 * per-proposal statuses and diagnostics instead of a bare count.
 * Malformed proposals are rejected by importProposal's internal
 * validateTimelinePatch check before persistence or notification.
 *
 * @returns A {@link ProposalImportResult} with imported/skipped/rejected
 * counts, per-proposal status entries, and any diagnostics produced.
 */
export function importEdgeProposals(
  envelope: ProposalEnvelope,
  runtime: ProposalRuntime & {
    importProposal?(proposal: TimelineProposal): 'imported' | 'duplicate' | 'rejected';
  },
): ProposalImportResult {
  // ── Envelope-level validation ────────────────────────────────────────
  if (!envelope.proposals || !Array.isArray(envelope.proposals)) {
    return {
      imported: 0,
      skipped: 0,
      rejected: 0,
      statuses: [],
      diagnostics: [
        {
          severity: 'error',
          code: 'proposal-import/invalid-envelope',
          message: 'ProposalEnvelope.proposals must be an array.',
        },
      ],
    };
  }

  if (envelope.proposals.length === 0) {
    return { imported: 0, skipped: 0, rejected: 0, statuses: [], diagnostics: [] };
  }

  if (typeof runtime.importProposal !== 'function') {
    return {
      imported: 0,
      skipped: envelope.proposals.length,
      rejected: 0,
      statuses: envelope.proposals.map((p) => ({
        proposalId: p.id,
        status: 'skipped' as const,
      })),
      diagnostics: [
        {
          severity: 'error',
          code: 'proposal-import/unsupported',
          message: 'Runtime does not support proposal import.',
        },
      ],
    };
  }

  // ── Per-proposal import ──────────────────────────────────────────────
  const diagnostics: ProposalImportDiagnostic[] = [];
  const statuses: { proposalId: string; status: ProposalImportStatus }[] = [];
  let imported = 0;
  let skipped = 0;
  let rejected = 0;

  for (let i = 0; i < envelope.proposals.length; i++) {
    const proposal = envelope.proposals[i];

    // Skip terminal states — only pending proposals are actionable.
    // Report them diagnostically so callers know why they were excluded.
    if (proposal.state !== 'pending') {
      diagnostics.push({
        severity: 'warning',
        code: 'proposal-import/skipped-terminal',
        message: `Proposal "${proposal.id}" skipped: state is "${proposal.state}" (only pending proposals are imported).`,
        proposalIndex: i,
        proposalId: proposal.id,
      });
      statuses.push({ proposalId: proposal.id, status: 'skipped' });
      skipped += 1;
      continue;
    }

    // Delegate to importProposal which now validates via
    // validateTimelinePatch, rejects malformed proposals before
    // persistence/notification, and returns a status indicator.
    const result = runtime.importProposal(proposal);

    switch (result) {
      case 'imported':
        statuses.push({ proposalId: proposal.id, status: 'imported' });
        imported += 1;
        break;
      case 'duplicate':
        statuses.push({ proposalId: proposal.id, status: 'skipped' });
        skipped += 1;
        break;
      case 'rejected':
        statuses.push({ proposalId: proposal.id, status: 'rejected' });
        rejected += 1;
        break;
      default:
        // Defensive: treat unknown status as rejected
        statuses.push({ proposalId: proposal.id, status: 'rejected' });
        rejected += 1;
    }
  }

  return { imported, skipped, rejected, statuses, diagnostics };
}
