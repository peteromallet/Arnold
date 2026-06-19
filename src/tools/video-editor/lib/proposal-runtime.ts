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
} from '@/sdk/index';
import type { TimelineOps } from '@/sdk/index';
import type { TimelineReader } from '@/sdk/index';

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
  const { timelineOps, reader } = options;

  // ── State ──────────────────────────────────────────────────────────────

  /** Map of proposal ID → proposal. */
  const proposals = new Map<string, TimelineProposal>();

  /** Registered listeners. */
  const listeners = new Set<ProposalListener>();

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
    overrides?: Partial<Pick<TimelineProposal, 'previewDiff' | 'previewable' | 'diagnostics'>>,
  ): TimelineProposal {
    const updated: TimelineProposal = {
      ...proposal,
      ...overrides,
      state: nextState,
      updatedAt: now(),
    };

    proposals.set(updated.id, updated);
    notify(updated);
    return updated;
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

  // ── get / list / currentVersion ────────────────────────────────────────

  function get(proposalId: string): TimelineProposal | undefined {
    return proposals.get(proposalId);
  }

  function list(state?: ProposalState): readonly TimelineProposal[] {
    const all = Array.from(proposals.values());
    if (state === undefined) {
      return all;
    }
    return all.filter((p) => p.state === state);
  }

  return {
    subscribe,
    create,
    preview,
    accept,
    reject,
    get,
    list,
    get currentVersion(): number {
      return reader.snapshot().currentVersion;
    },
  };
}
