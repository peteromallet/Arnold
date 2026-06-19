/**
 * ProposalPanel — Host-owned proposal management UI.
 *
 * Subscribes to the provider-scoped ProposalRuntime via useSyncExternalStore
 * and renders proposal count/status, source, rationale, previewability,
 * stale status, diagnostics, sparse before/after TimelineDiff summaries,
 * and preview/accept/reject action buttons.
 *
 * Designed to be inserted under TimelineEditorShellCore's toolbar/status-bar
 * region or as a standalone panel following the DiagnosticPanel pattern.
 *
 * Accessibility:
 * - role="region" with aria-label="Proposal panel"
 * - aria-live="polite" on the proposal list for screen-reader updates
 * - Interactive elements have accessible labels
 */

import {
  useCallback,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  Check,
  Eye,
  EyeOff,
  X,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  AlertCircle,
  Info,
  Clock,
} from 'lucide-react';
import type {
  ProposalRuntime,
  TimelineProposal,
  ProposalState,
  TimelineDiff,
  TimelineDiffEntry,
  TimelinePatchDiagnostic,
  DisposeHandle,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProposalPanelProps {
  /** Provider-scoped ProposalRuntime to subscribe to. */
  proposalRuntime: ProposalRuntime;
  /** Called when the panel requests to be closed. */
  onClose?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATE_LABEL: Record<ProposalState, string> = {
  pending: 'Pending',
  accepted: 'Accepted',
  rejected: 'Rejected',
  stale: 'Stale',
};

const STATE_COLOR: Record<ProposalState, string> = {
  pending: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  accepted: 'bg-green-500/15 text-green-400 border-green-500/30',
  rejected: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
  stale: 'bg-red-500/15 text-red-400 border-red-500/30',
};

const SEVERITY_ICON: Record<string, typeof AlertTriangle> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const SEVERITY_COLOR: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
};

const DIFF_KIND_LABEL: Record<string, string> = {
  added: 'Added',
  removed: 'Removed',
  modified: 'Modified',
  reordered: 'Reordered',
};

const DIFF_KIND_COLOR: Record<string, string> = {
  added: 'text-green-400',
  removed: 'text-red-400',
  modified: 'text-yellow-400',
  reordered: 'text-blue-400',
};

function formatTimestamp(epochMs: number): string {
  try {
    return new Date(epochMs).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return 'unknown';
  }
}

/**
 * Sparse before/after summary for a diff entry.
 * Shows only the top-level scalar keys with non-empty values,
 * omitting deeply nested objects and arrays for readability.
 */
function sparseSummary(record: Record<string, unknown> | undefined): string | null {
  if (!record || Object.keys(record).length === 0) return null;
  const entries = Object.entries(record)
    .filter(([, v]) => v !== undefined && v !== null && typeof v !== 'object')
    .slice(0, 6);
  if (entries.length === 0) return null;
  const summary = entries.map(([k, v]) => `${k}=${String(v)}`).join(', ');
  const more = Object.keys(record).length > 6 ? ' …' : '';
  return summary + more;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ProposalPanel({
  proposalRuntime,
  onClose,
}: ProposalPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Subscribe to the ProposalRuntime via useSyncExternalStore.
  // Cache the snapshot to avoid infinite re-render loops — ProposalRuntime.list()
  // returns a new array reference each call, but React requires getSnapshot to be
  // referentially stable between notifications.
  const snapshotRef = useRef<readonly TimelineProposal[]>(proposalRuntime.list());

  const subscribe = useCallback(
    (handler: () => void): (() => void) => {
      const handle: DisposeHandle = proposalRuntime.subscribe(() => {
        // Update the cached snapshot on every notification, then tell React to
        // re-read via the getSnapshot callback.
        snapshotRef.current = proposalRuntime.list();
        handler();
      });
      return () => handle.dispose();
    },
    [proposalRuntime],
  );

  const proposals = useSyncExternalStore(
    subscribe,
    () => snapshotRef.current,
  );

  // ---- State ----------------------------------------------------------
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [showAccepted, setShowAccepted] = useState(true);
  const [showRejected, setShowRejected] = useState(false);
  const [actionStatus, setActionStatus] = useState<{
    proposalId: string;
    message: string;
    severity: 'error' | 'info';
  } | null>(null);

  // ---- Filtering ------------------------------------------------------
  const filteredProposals = useMemo(() => {
    return proposals.filter((p) => {
      if (p.state === 'accepted' && !showAccepted) return false;
      if (p.state === 'rejected' && !showRejected) return false;
      return true;
    });
  }, [proposals, showAccepted, showRejected]);

  // Sort: pending first, then stale, then accepted, then rejected; newest first within each
  const sortedProposals = useMemo(() => {
    const order: Record<ProposalState, number> = {
      pending: 0,
      stale: 1,
      accepted: 2,
      rejected: 3,
    };
    return [...filteredProposals].sort((a, b) => {
      const orderDiff = order[a.state] - order[b.state];
      if (orderDiff !== 0) return orderDiff;
      return b.updatedAt - a.updatedAt;
    });
  }, [filteredProposals]);

  const pendingCount = proposals.filter((p) => p.state === 'pending').length;
  const staleCount = proposals.filter((p) => p.state === 'stale').length;

  // ---- Handlers -------------------------------------------------------
  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handlePreview = useCallback(
    (proposalId: string) => {
      try {
        proposalRuntime.preview(proposalId);
        setActionStatus({
          proposalId,
          message: 'Preview updated.',
          severity: 'info',
        });
      } catch (err) {
        setActionStatus({
          proposalId,
          message: `Preview failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime],
  );

  const handleAccept = useCallback(
    (proposalId: string) => {
      try {
        proposalRuntime.accept(proposalId);
        setActionStatus({
          proposalId,
          message: 'Proposal accepted and applied.',
          severity: 'info',
        });
      } catch (err) {
        setActionStatus({
          proposalId,
          message: `Accept failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime],
  );

  const handleReject = useCallback(
    (proposalId: string) => {
      try {
        proposalRuntime.reject(proposalId, 'Rejected by user');
        setActionStatus({
          proposalId,
          message: 'Proposal rejected.',
          severity: 'info',
        });
      } catch (err) {
        setActionStatus({
          proposalId,
          message: `Reject failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime],
  );

  // Auto-clear action status after 4s
  const actionStatusTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setTimedStatus = useCallback(
    (status: { proposalId: string; message: string; severity: 'error' | 'info' }) => {
      setActionStatus(status);
      if (actionStatusTimeoutRef.current) {
        clearTimeout(actionStatusTimeoutRef.current);
      }
      actionStatusTimeoutRef.current = setTimeout(() => setActionStatus(null), 4000);
    },
    [],
  );

  // Wrap handlers with auto-clear
  const handlePreviewTimed = useCallback(
    (id: string) => {
      try {
        const result = proposalRuntime.preview(id);
        setTimedStatus({
          proposalId: id,
          message: `Preview ${result.fullyPreviewable ? 'complete' : 'partial'} (${result.diff.entries.length} changes).`,
          severity: 'info',
        });
      } catch (err) {
        setTimedStatus({
          proposalId: id,
          message: `Preview failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime, setTimedStatus],
  );

  const handleAcceptTimed = useCallback(
    (id: string) => {
      try {
        const diff = proposalRuntime.accept(id);
        setTimedStatus({
          proposalId: id,
          message: `Accepted — ${diff.entries.length} changes applied.`,
          severity: 'info',
        });
      } catch (err) {
        setTimedStatus({
          proposalId: id,
          message: `Accept failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime, setTimedStatus],
  );

  const handleRejectTimed = useCallback(
    (id: string) => {
      try {
        proposalRuntime.reject(id, 'Rejected by user');
        setTimedStatus({
          proposalId: id,
          message: 'Proposal rejected.',
          severity: 'info',
        });
      } catch (err) {
        setTimedStatus({
          proposalId: id,
          message: `Reject failed: ${err instanceof Error ? err.message : String(err)}`,
          severity: 'error',
        });
      }
    },
    [proposalRuntime, setTimedStatus],
  );

  // ---- Render ---------------------------------------------------------

  const totalCount = sortedProposals.length;

  return (
    <div
      ref={panelRef}
      role="region"
      aria-label="Proposal panel"
      tabIndex={-1}
      data-video-editor-proposal-panel="true"
      className="flex flex-col rounded-lg border border-white/10 bg-zinc-900 text-xs text-zinc-200 shadow-2xl"
      style={{ maxHeight: '60vh', minWidth: '340px', maxWidth: '560px' }}
    >
      {/* ---- Header ---------------------------------------------------- */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-zinc-300">Proposals</span>
          {totalCount > 0 && (
            <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {totalCount}
            </span>
          )}
          {pendingCount > 0 && (
            <span className="rounded-full bg-yellow-500/15 px-1.5 py-0.5 text-[10px] text-yellow-400">
              {pendingCount} pending
            </span>
          )}
          {staleCount > 0 && (
            <span className="rounded-full bg-red-500/15 px-1.5 py-0.5 text-[10px] text-red-400">
              {staleCount} stale
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setShowAccepted((v) => !v)}
            aria-pressed={showAccepted}
            aria-label={`${showAccepted ? 'Hide' : 'Show'} accepted proposals`}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              showAccepted
                ? 'bg-green-500/10 text-green-400'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Accepted
          </button>
          <button
            type="button"
            onClick={() => setShowRejected((v) => !v)}
            aria-pressed={showRejected}
            aria-label={`${showRejected ? 'Hide' : 'Show'} rejected proposals`}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              showRejected
                ? 'bg-zinc-500/10 text-zinc-400'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Rejected
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
              aria-label="Close proposal panel"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ---- Action status feedback ------------------------------------ */}
      {actionStatus && (
        <div
          className={`border-b px-3 py-1.5 text-[10px] ${
            actionStatus.severity === 'error'
              ? 'border-red-500/20 bg-red-500/5 text-red-400'
              : 'border-blue-500/20 bg-blue-500/5 text-blue-400'
          }`}
          role="status"
          aria-live="polite"
        >
          {actionStatus.message}
        </div>
      )}

      {/* ---- Proposal list --------------------------------------------- */}
      <div
        className="overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label={`${totalCount} proposal${totalCount === 1 ? '' : 's'}`}
        aria-relevant="additions removals"
      >
        {sortedProposals.length === 0 ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <Info className="h-5 w-5 text-zinc-600" aria-hidden="true" />
            <p className="text-[11px] text-zinc-500">No proposals.</p>
          </div>
        ) : (
          <div className="flex flex-col">
            {sortedProposals.map((proposal) => {
              const isExpanded = expandedIds.has(proposal.id);
              const isPending = proposal.state === 'pending';
              const isStale = proposal.state === 'stale';

              return (
                <div
                  key={proposal.id}
                  data-video-editor-proposal-item="true"
                  data-video-editor-proposal-state={proposal.state}
                  data-video-editor-proposal-id={proposal.id}
                  className="border-b border-white/5 last:border-b-0"
                >
                  {/* Proposal header */}
                  <button
                    type="button"
                    onClick={() => toggleExpand(proposal.id)}
                    className="flex w-full items-center gap-1.5 px-3 py-2 text-left hover:bg-white/5 transition-colors"
                    aria-expanded={isExpanded}
                    aria-label={`Proposal from ${proposal.source}: ${proposal.rationale ?? 'no rationale'} — ${STATE_LABEL[proposal.state]}`}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                    ) : (
                      <ChevronRight className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                    )}
                    <div className="min-w-0 flex-1">
                      {/* Source + rationale */}
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-zinc-300 truncate">
                          {proposal.source}
                        </span>
                        <span
                          className={`shrink-0 rounded border px-1 py-0 text-[9px] font-medium uppercase tracking-[0.12em] ${STATE_COLOR[proposal.state]}`}
                          data-video-editor-proposal-state-badge="true"
                        >
                          {STATE_LABEL[proposal.state]}
                        </span>
                        {proposal.previewable && (
                          <Eye
                            className="h-2.5 w-2.5 shrink-0 text-green-400"
                            aria-label="Previewable"
                            data-video-editor-proposal-previewable="true"
                          />
                        )}
                        {!proposal.previewable && isPending && (
                          <EyeOff
                            className="h-2.5 w-2.5 shrink-0 text-zinc-500"
                            aria-label="Not previewable"
                            data-video-editor-proposal-not-previewable="true"
                          />
                        )}
                        {isStale && (
                          <Clock
                            className="h-2.5 w-2.5 shrink-0 text-red-400"
                            aria-label="Stale"
                            data-video-editor-proposal-stale="true"
                          />
                        )}
                      </div>
                      {/* Rationale + patch summary */}
                      <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-zinc-500">
                        {proposal.rationale && (
                          <span className="truncate max-w-[200px]">
                            {proposal.rationale}
                          </span>
                        )}
                        <span className="shrink-0 tabular-nums">
                          v{proposal.baseVersion}
                        </span>
                        <span className="shrink-0 tabular-nums">
                          {proposal.patch.operations.length} op{proposal.patch.operations.length !== 1 ? 's' : ''}
                        </span>
                        {proposal.previewDiff && (
                          <span className="shrink-0 tabular-nums">
                            {proposal.previewDiff.entries.length} change{proposal.previewDiff.entries.length !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                      {/* Timestamp */}
                      <div className="mt-0.5 text-[9px] text-zinc-600">
                        {formatTimestamp(proposal.updatedAt)}
                      </div>
                    </div>
                  </button>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="flex flex-col border-t border-white/5">
                      {/* Diagnostics */}
                      {proposal.diagnostics && proposal.diagnostics.length > 0 && (
                        <DiagnosticsSection diagnostics={proposal.diagnostics} />
                      )}

                      {/* Preview diff */}
                      {proposal.previewDiff && (
                        <DiffSection diff={proposal.previewDiff} />
                      )}

                      {/* Patch operation summary */}
                      {proposal.patch.operations.length > 0 && (
                        <div className="border-t border-white/5 px-6 py-1.5">
                          <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-[0.12em]">
                            Patch Operations ({proposal.patch.operations.length})
                          </span>
                          <div className="mt-1 flex flex-col gap-0.5">
                            {proposal.patch.operations.map((op, i) => (
                              <div
                                key={i}
                                className="flex items-center gap-1.5 text-[10px] text-zinc-500"
                              >
                                <span className="rounded bg-zinc-800 px-1 py-0 text-[9px] text-zinc-400 tabular-nums">
                                  #{i}
                                </span>
                                <span className="font-mono text-[10px]">{op.op}</span>
                                {op.payload && Object.keys(op.payload).length > 0 && (
                                  <span className="truncate text-zinc-600">
                                    {Object.entries(op.payload)
                                      .filter(([, v]) => v !== undefined)
                                      .map(([k, v]) => `${k}=${typeof v === 'object' ? '…' : String(v)}`)
                                      .join(', ')}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Action buttons */}
                      {isPending && (
                        <div className="flex items-center gap-1 border-t border-white/5 px-3 py-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePreviewTimed(proposal.id);
                            }}
                            className="flex items-center gap-1 rounded border border-white/10 bg-zinc-800 px-2 py-1 text-[10px] text-zinc-300 hover:bg-zinc-700 transition-colors"
                            aria-label={`Preview proposal from ${proposal.source}`}
                            data-video-editor-proposal-action="preview"
                          >
                            <Eye className="h-3 w-3" aria-hidden="true" />
                            Preview
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAcceptTimed(proposal.id);
                            }}
                            className="flex items-center gap-1 rounded border border-green-500/30 bg-green-500/10 px-2 py-1 text-[10px] text-green-400 hover:bg-green-500/20 transition-colors"
                            aria-label={`Accept proposal from ${proposal.source}`}
                            data-video-editor-proposal-action="accept"
                          >
                            <Check className="h-3 w-3" aria-hidden="true" />
                            Accept
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRejectTimed(proposal.id);
                            }}
                            className="flex items-center gap-1 rounded border border-red-500/30 bg-red-500/10 px-2 py-1 text-[10px] text-red-400 hover:bg-red-500/20 transition-colors"
                            aria-label={`Reject proposal from ${proposal.source}`}
                            data-video-editor-proposal-action="reject"
                          >
                            <X className="h-3 w-3" aria-hidden="true" />
                            Reject
                          </button>
                        </div>
                      )}

                      {/* Stale proposals: show re-preview option */}
                      {isStale && (
                        <div className="flex items-center gap-1 border-t border-white/5 px-3 py-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePreviewTimed(proposal.id);
                            }}
                            className="flex items-center gap-1 rounded border border-white/10 bg-zinc-800 px-2 py-1 text-[10px] text-zinc-300 hover:bg-zinc-700 transition-colors"
                            aria-label={`Re-preview stale proposal from ${proposal.source}`}
                            data-video-editor-proposal-action="preview"
                          >
                            <Eye className="h-3 w-3" aria-hidden="true" />
                            Re-preview
                          </button>
                          <span className="text-[10px] text-zinc-500 ml-1">
                            Proposal is stale — base version no longer matches current timeline.
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Renders a list of diagnostics for a proposal. */
function DiagnosticsSection({
  diagnostics,
}: {
  diagnostics: readonly TimelinePatchDiagnostic[];
}) {
  return (
    <div className="border-b border-white/5 px-6 py-2">
      <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-[0.12em]">
        Diagnostics ({diagnostics.length})
      </span>
      <div className="mt-1 flex flex-col gap-1">
        {diagnostics.map((diag, i) => {
          const SevIcon = SEVERITY_ICON[diag.severity] ?? AlertCircle;
          return (
            <div
              key={i}
              data-video-editor-proposal-diagnostic="true"
              data-video-editor-proposal-diagnostic-severity={diag.severity}
              data-video-editor-proposal-diagnostic-code={diag.code}
              className="flex items-start gap-1.5"
            >
              <SevIcon
                className={`mt-0.5 h-2.5 w-2.5 shrink-0 ${SEVERITY_COLOR[diag.severity] ?? 'text-zinc-400'}`}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <span className="text-[10px] text-zinc-400 break-words">
                  {diag.message}
                </span>
                {diag.code && (
                  <span className="ml-1 text-[9px] text-zinc-600">
                    [{diag.code}]
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Renders a sparse diff summary for a proposal. */
function DiffSection({ diff }: { diff: TimelineDiff }) {
  const [expandedDiff, setExpandedDiff] = useState(false);

  const showCount = 5;
  const hasMore = diff.entries.length > showCount;
  const visibleEntries = expandedDiff
    ? diff.entries
    : diff.entries.slice(0, showCount);

  return (
    <div className="border-b border-white/5 px-6 py-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-[0.12em]">
          Diff ({diff.entries.length} change{diff.entries.length !== 1 ? 's' : ''})
        </span>
        <span className="text-[9px] text-zinc-600 tabular-nums">
          v{diff.version}
        </span>
      </div>
      <div className="mt-1 flex flex-col gap-1">
        {visibleEntries.map((entry, i) => (
          <DiffEntryRow key={i} entry={entry} index={i} />
        ))}
        {hasMore && !expandedDiff && (
          <button
            type="button"
            onClick={() => setExpandedDiff(true)}
            className="text-[9px] text-zinc-500 hover:text-zinc-300 transition-colors text-left"
          >
            +{diff.entries.length - showCount} more changes…
          </button>
        )}
        {expandedDiff && hasMore && (
          <button
            type="button"
            onClick={() => setExpandedDiff(false)}
            className="text-[9px] text-zinc-500 hover:text-zinc-300 transition-colors text-left"
          >
            Show less
          </button>
        )}
      </div>
      {diff.affectedObjectIds.length > 0 && (
        <div className="mt-1.5 text-[9px] text-zinc-600">
          Affected: {diff.affectedObjectIds.slice(0, 5).join(', ')}
          {diff.affectedObjectIds.length > 5 ? ` +${diff.affectedObjectIds.length - 5} more` : ''}
        </div>
      )}
    </div>
  );
}

/** Renders a single diff entry row with sparse before/after summaries. */
function DiffEntryRow({
  entry,
  index,
}: {
  entry: TimelineDiffEntry;
  index: number;
}) {
  const beforeSummary = sparseSummary(entry.before);
  const afterSummary = sparseSummary(entry.after);

  return (
    <div
      className="flex items-start gap-1.5"
      data-video-editor-proposal-diff-entry="true"
      data-video-editor-proposal-diff-kind={entry.kind}
      data-video-editor-proposal-diff-granularity={entry.granularity}
    >
      <span className="shrink-0 rounded bg-zinc-800 px-1 py-0 text-[9px] text-zinc-500 tabular-nums">
        #{index + 1}
      </span>
      <span className={`shrink-0 text-[10px] font-medium ${DIFF_KIND_COLOR[entry.kind] ?? 'text-zinc-400'}`}>
        {DIFF_KIND_LABEL[entry.kind] ?? entry.kind}
      </span>
      <span className="text-[10px] text-zinc-500">{entry.granularity}</span>
      <span className="truncate font-mono text-[10px] text-zinc-400">
        {entry.target}
      </span>
      {beforeSummary && (
        <span className="truncate text-[9px] text-zinc-600" title={beforeSummary}>
          ← {beforeSummary}
        </span>
      )}
      {afterSummary && (
        <span className="truncate text-[9px] text-zinc-500" title={afterSummary}>
          → {afterSummary}
        </span>
      )}
    </div>
  );
}
