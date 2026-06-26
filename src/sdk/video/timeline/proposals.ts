/**
 * Proposal contracts for the timeline proposal system.
 *
 * Contains the core proposal types (ProposalState, TimelineProposal,
 * ProposalRuntime, panel contracts, envelope, and import types).
 * These are M3 data contracts consumed by the host proposal UI and
 * edge-function proposal envelopes.
 *
 * @publicContract
 */

import type { TimelinePatch, TimelineDiff, TimelinePreviewResult, TimelinePatchDiagnostic } from './patch';
import type { TimelineProposalInput } from './reader';
import type { DisposeHandle } from '../../dispose';

// ---------------------------------------------------------------------------
// M3: TimelineProposal
// ---------------------------------------------------------------------------

/** Lifecycle state of a proposal. */
export type ProposalState =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'stale'
  | 'expired';

/**
 * Structured detail carried by a proposal that reached stale or expired state.
 *
 * Produced by the runtime when a proposal's baseVersion no longer matches
 * the current reader version (stale) or when its TTL has elapsed (expired).
 * Carried on {@link TimelineProposal.expiryDetail} so the UI can surface
 * clear diagnostics without parsing raw timeline-patch codes.
 */
export interface ProposalExpiryDetail {
  /** Why the proposal transitioned to stale/expired. */
  reason: 'base-version-mismatch' | 'ttl-elapsed' | 'manual';
  /** The baseVersion the proposal was created against. */
  baseVersion: number;
  /** The current reader version at the time the proposal transitioned. */
  currentVersion: number;
  /** When the proposal was created (epoch ms). */
  createdAt: number;
  /** When the proposal transitioned to stale/expired (epoch ms). */
  expiredAt: number;
  /** The TTL in ms that was configured when the proposal was created, if any. */
  ttlMs?: number;
}

/** A proposal to mutate the timeline, submitted by an extension or tool. */
export interface TimelineProposal {
  /** Unique proposal identifier assigned by the runtime. */
  id: string;
  /** The source that created this proposal (extension ID, tool name, etc.). */
  source: string;
  /** Human-readable rationale / description. */
  rationale?: string;
  /** Current lifecycle state. */
  state: ProposalState;
  /** The patch to apply if accepted. */
  patch: TimelinePatch;
  /**
   * The baseVersion the proposal was created against.
   * If the current reader version differs at acceptance time, the proposal
   * is stale and must be rejected or refreshed.
   */
  baseVersion: number;
  /**
   * Whether this proposal's effects can be previewed (ghost-rendered)
   * without committing. Reserved operations are non-previewable.
   */
  previewable: boolean;
  /** The diff produced when this proposal was last previewed, if any. */
  previewDiff?: TimelineDiff;
  /** Timestamp when the proposal was created (epoch ms). */
  createdAt: number;
  /** Timestamp when the proposal last changed state (epoch ms). */
  updatedAt: number;
  /**
   * Epoch-ms timestamp after which the proposal is considered expired.
   * When set, the runtime may auto-expire the proposal once this time
   * has elapsed.  If absent, the proposal has no TTL.
   */
  expiresAt?: number;
  /**
   * When the proposal became stale or expired, this carries structured
   * detail about the conflict (version drift, TTL elapsed, etc.).
   * Absent for proposals in pending/accepted/rejected state.
   */
  expiryDetail?: ProposalExpiryDetail;
  /** Diagnostics produced during validation or preview, if any. */
  diagnostics?: readonly TimelinePatchDiagnostic[];
}

/** Listener callback for proposal state changes. */
export type ProposalListener = (proposal: TimelineProposal) => void;

// ---------------------------------------------------------------------------
// M3: ProposalRuntime
// ---------------------------------------------------------------------------

/**
 * Provider-scoped proposal runtime.
 *
 * Manages the lifecycle of TimelineProposals: creation, preview, acceptance,
 * rejection, and stale detection. Proposals are in-memory and provider-scoped
 * for M3; page refresh drops unaccepted proposals.
 */
export interface ProposalRuntime {
  /**
   * Subscribe to proposal state changes.
   * The listener is called whenever any proposal changes state.
   * Returns a DisposeHandle for unsubscription.
   */
  subscribe(listener: ProposalListener): DisposeHandle;

  /**
   * Create a new pending proposal. If a proposal from the same source
   * already exists in 'pending' state, it is atomically replaced
   * (replaceForSource semantics).
   */
  create(input: TimelineProposalInput): TimelineProposal;

  /**
   * Preview a pending proposal against the current reader snapshot.
   * Returns the projected diff. Does not mutate canonical timeline state.
   * Updates the proposal's previewDiff and previewable fields.
   */
  preview(proposalId: string): TimelinePreviewResult;

  /**
   * Accept a pending proposal. Revalidates baseVersion against the current
   * reader snapshot; if stale, the proposal is marked stale and the call
   * fails with a diagnostic. On success, applies the patch through
   * TimelineOps and marks the proposal accepted.
   *
   * Throws on stale baseVersion or if the proposal is not in 'pending' state.
   */
  accept(proposalId: string): TimelineDiff;

  /**
   * Reject a pending proposal, moving it to 'rejected' state.
   * No timeline mutation occurs.
   */
  reject(proposalId: string, reason?: string): void;

  /**
   * Get a proposal by ID, or undefined if not found.
   */
  get(proposalId: string): TimelineProposal | undefined;

  /**
   * List all proposals, optionally filtered by state.
   */
  list(state?: ProposalState): readonly TimelineProposal[];

  /**
   * Get the current reader snapshot version for baseVersion comparisons.
   */
  readonly currentVersion: number;

  /**
   * Scan pending proposals and transition any whose TTL has elapsed
   * to 'expired' state, populating {@link TimelineProposal.expiryDetail}.
   *
   * @param maxAgeMs - Proposals older than this many ms (relative to now)
   *   are eligible for expiry.  A value of 0 expires every pending proposal.
   * @returns The proposals that were transitioned to 'expired' in this call.
   */
  expireStale(maxAgeMs: number): readonly TimelineProposal[];
}

// ---------------------------------------------------------------------------
// M3: Host-owned proposal UI contract (surface shape only)
// ---------------------------------------------------------------------------

/**
 * Contract for the host-owned proposal panel UI surface.
 *
 * The actual UI is implemented by the host using existing
 * TimelineEditorShellCore, AlertDialog, and DiagnosticPanel components.
 * This interface defines the data shape the UI surface expects from the
 * proposal runtime — it does not prescribe rendering details.
 */
export interface ProposalPanelState {
  /** All proposals currently known to the runtime. */
  proposals: readonly TimelineProposal[];
  /** The proposal currently selected for preview, if any. */
  selectedProposalId: string | null;
  /** Whether the proposal panel is visible. */
  visible: boolean;
}

/** Action types the proposal UI can dispatch. */
export type ProposalPanelAction =
  | { type: 'select'; proposalId: string }
  | { type: 'deselect' }
  | { type: 'accept'; proposalId: string }
  | { type: 'reject'; proposalId: string; reason?: string }
  | { type: 'preview'; proposalId: string }
  | { type: 'toggleVisibility' };

/**
 * Serialized proposal envelope returned by edge functions (e.g. the
 * ai-timeline-agent) when operating in proposal mode.
 *
 * This shape is wire-stable and consumed by the client-side
 * `normalizeInvokeResponse` path to hydrate the ProposalPanel UI without
 * parsing unstructured agent response text.
 */
export interface ProposalEnvelope {
  /** The proposals produced by this edge invocation. */
  proposals: readonly TimelineProposal[];
  /**
   * The config version the proposals were created against.
   * Used by the client to detect stale/conflict before rendering the panel.
   */
  baseVersion: number;
  /**
   * Human-readable summary produced by the agent alongside the proposals.
   * May be empty when only proposals are returned.
   */
  summary?: string;
  /**
   * Whether any mutation was applied during this invocation.
   * In pure proposal mode this is always false; the field is present so
   * the client can distinguish proposal-only responses from apply-mode
   * responses that also carry proposals.
   */
  mutationApplied: boolean;
}

// ---------------------------------------------------------------------------
// M1: Proposal import contracts
// ---------------------------------------------------------------------------

/** Status of an individual proposal within an import batch. */
export type ProposalImportStatus = 'imported' | 'skipped' | 'rejected';

/** Diagnostic produced during proposal import validation. */
export interface ProposalImportDiagnostic {
  /** Diagnostic severity. */
  severity: 'error' | 'warning';
  /** Diagnostic code (e.g. 'proposal-import/missing-id'). */
  code: string;
  /** Human-readable diagnostic message. */
  message: string;
  /** Zero-based index of the proposal in the envelope's proposals array. */
  proposalIndex?: number;
  /** The proposal ID, if available. */
  proposalId?: string;
  /** Additional structured detail. */
  detail?: Record<string, unknown>;
}

/** Result of importing proposals from a ProposalEnvelope. */
export interface ProposalImportResult {
  /** Number of proposals successfully imported. */
  imported: number;
  /** Number of proposals skipped (e.g. non-pending state). */
  skipped: number;
  /** Number of proposals rejected during import validation. */
  rejected: number;
  /** Individual per-proposal status entries. */
  statuses: readonly { proposalId: string; status: ProposalImportStatus }[];
  /** Diagnostics produced during import, if any. */
  diagnostics: readonly ProposalImportDiagnostic[];
}
