/**
 * DiagnosticPanel — Host-owned diagnostic display surface.
 *
 * Reachable from the status bar and from ContributionErrorBoundary fallback
 * "View diagnostics" actions. Subscribes via `useSyncExternalStore` to the
 * provider-scoped `DiagnosticCollection`, groups diagnostics by extension and
 * contribution, supports severity filtering, and displays 1-based source
 * ranges verbatim.
 *
 * Accessibility:
 * - `role="region"` with `aria-label="Diagnostics panel"`
 * - `aria-live="polite"` on the diagnostics list for screen-reader updates
 * - Focus is moved to the panel container when it becomes visible
 * - Interactive elements have accessible labels
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  MapPinOff,
  X,
  ChevronDown,
  ChevronRight,
  Filter,
} from 'lucide-react';
import type {
  DiagnosticCollection,
  Diagnostic,
  DiagnosticSeverity,
  DiagnosticSourceRange,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DiagnosticPanelProps {
  /** Provider-scoped diagnostic collection to subscribe to. */
  diagnosticCollection: DiagnosticCollection;
  /**
   * Optional initial filter applied when the panel is opened from a
   * fallback "View diagnostics" action. When provided, the panel starts
   * filtered to the given extension and/or contribution.
   */
  initialFilter?: {
    extensionId?: string;
    contributionId?: string;
  };
  /**
   * Optional set of target IDs that have stale source-map entries.
   * When a diagnostic's detail references a target in this set, a stale
   * source-map badge is shown next to the diagnostic.
   */
  sourceMapStaleTargetIds?: ReadonlySet<string>;
  /** Called when the panel requests to be closed. */
  onClose?: () => void;
}

interface DiagnosticGroup {
  extensionId: string;
  contributions: Map<string, Diagnostic[]>;
  totalCount: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_ICON: Record<DiagnosticSeverity, typeof AlertTriangle> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const SEVERITY_COLOR: Record<DiagnosticSeverity, string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
};

const SEVERITY_BG: Record<DiagnosticSeverity, string> = {
  error: 'bg-red-500/10 border-red-500/30',
  warning: 'bg-yellow-500/10 border-yellow-500/30',
  info: 'bg-blue-500/10 border-blue-500/30',
};

function formatSourceRange(range: DiagnosticSourceRange): string {
  if (range.startLine === range.endLine && range.startCol === range.endCol) {
    return `${range.startLine}:${range.startCol}`;
  }
  return `${range.startLine}:${range.startCol}–${range.endLine}:${range.endCol}`;
}

function groupDiagnostics(diagnostics: readonly Diagnostic[]): DiagnosticGroup[] {
  const byExtension = new Map<string, Map<string, Diagnostic[]>>();

  for (const d of diagnostics) {
    const extId = d.extensionId ?? '(no-owner)';
    const contribId = d.contributionId ?? '(no-contribution)';

    if (!byExtension.has(extId)) {
      byExtension.set(extId, new Map());
    }
    const byContrib = byExtension.get(extId)!;
    if (!byContrib.has(contribId)) {
      byContrib.set(contribId, []);
    }
    byContrib.get(contribId)!.push(d);
  }

  const groups: DiagnosticGroup[] = [];
  for (const [extensionId, contributions] of byExtension) {
    let totalCount = 0;
    for (const diags of contributions.values()) {
      totalCount += diags.length;
    }
    groups.push({ extensionId, contributions, totalCount });
  }

  // Sort: extensions with errors first, then by extension ID
  groups.sort((a, b) => {
    const aErrors = [...a.contributions.values()].flat().filter((d) => d.severity === 'error').length;
    const bErrors = [...b.contributions.values()].flat().filter((d) => d.severity === 'error').length;
    if (aErrors !== bErrors) return bErrors - aErrors;
    return a.extensionId.localeCompare(b.extensionId);
  });

  return groups;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DiagnosticPanel({
  diagnosticCollection,
  initialFilter,
  onClose,
  sourceMapStaleTargetIds,
}: DiagnosticPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Subscribe to the collection via useSyncExternalStore.
  // The SDK's subscribe() returns a DisposeHandle, but useSyncExternalStore
  // expects a cleanup function — wrap accordingly.
  const subscribe = useCallback(
    (handler: () => void) => {
      const handle = diagnosticCollection.subscribe(handler);
      return () => handle.dispose();
    },
    [diagnosticCollection],
  );

  const diagnostics = useSyncExternalStore(
    subscribe,
    diagnosticCollection.getSnapshot.bind(diagnosticCollection),
  );

  // ---- State --------------------------------------------------------------
  const [severityFilter, setSeverityFilter] = useState<Set<DiagnosticSeverity>>(
    new Set(['error', 'warning', 'info']),
  );
  const [extensionFilter, setExtensionFilter] = useState<string | null>(
    initialFilter?.extensionId ?? null,
  );
  const [contributionFilter, setContributionFilter] = useState<string | null>(
    initialFilter?.contributionId ?? null,
  );
  const [expandedExtensions, setExpandedExtensions] = useState<Set<string>>(
    new Set(),
  );
  const [expandedContributions, setExpandedContributions] = useState<Set<string>>(
    new Set(),
  );

  // Auto-expand on initial filter
  useEffect(() => {
    if (initialFilter?.extensionId) {
      setExpandedExtensions((prev) => new Set(prev).add(initialFilter.extensionId!));
    }
  }, [initialFilter?.extensionId]);

  // Focus the panel when it mounts
  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  // ---- Filtering ----------------------------------------------------------

  const filteredDiagnostics = useMemo(() => {
    let result = diagnostics;

    if (extensionFilter) {
      result = result.filter((d) => (d.extensionId ?? '(no-owner)') === extensionFilter);
    }
    if (contributionFilter) {
      result = result.filter((d) => (d.contributionId ?? '(no-contribution)') === contributionFilter);
    }
    result = result.filter((d) => severityFilter.has(d.severity));

    return result;
  }, [diagnostics, extensionFilter, contributionFilter, severityFilter]);

  const groups = useMemo(() => groupDiagnostics(filteredDiagnostics), [filteredDiagnostics]);

  // Derive unique extensions and contributions for filter dropdowns
  const allExtensions = useMemo(() => {
    const exts = new Set<string>();
    for (const d of diagnostics) {
      exts.add(d.extensionId ?? '(no-owner)');
    }
    return [...exts].sort();
  }, [diagnostics]);

  // ---- Handlers -----------------------------------------------------------
  const toggleSeverity = useCallback((sev: DiagnosticSeverity) => {
    setSeverityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) {
        next.delete(sev);
      } else {
        next.add(sev);
      }
      return next;
    });
  }, []);

  const toggleExtensionExpand = useCallback((extId: string) => {
    setExpandedExtensions((prev) => {
      const next = new Set(prev);
      if (next.has(extId)) {
        next.delete(extId);
      } else {
        next.add(extId);
      }
      return next;
    });
  }, []);

  const toggleContributionExpand = useCallback((key: string) => {
    setExpandedContributions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setExtensionFilter(null);
    setContributionFilter(null);
    setSeverityFilter(new Set(['error', 'warning', 'info']));
  }, []);

  const hasActiveFilters =
    extensionFilter !== null ||
    contributionFilter !== null ||
    severityFilter.size < 3;

  // ---- Render -------------------------------------------------------------

  const totalCount = filteredDiagnostics.length;
  const errorCount = filteredDiagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = filteredDiagnostics.filter((d) => d.severity === 'warning').length;
  const infoCount = filteredDiagnostics.filter((d) => d.severity === 'info').length;

  return (
    <div
      ref={panelRef}
      role="region"
      aria-label="Diagnostics panel"
      tabIndex={-1}
      data-video-editor-diagnostic-panel="true"
      className="flex flex-col rounded-lg border border-white/10 bg-zinc-900 text-xs text-zinc-200 shadow-2xl"
      style={{ maxHeight: '60vh', minWidth: '320px', maxWidth: '520px' }}
    >
      {/* ---- Header -------------------------------------------------------- */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 text-zinc-400" aria-hidden="true" />
          <span className="font-medium text-zinc-300">Diagnostics</span>
          {totalCount > 0 && (
            <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {totalCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="rounded px-1.5 py-0.5 text-[10px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
              aria-label="Clear all filters"
            >
              Clear filters
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
              aria-label="Close diagnostics panel"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ---- Severity filter toggles --------------------------------------- */}
      <div className="flex items-center gap-1 border-b border-white/5 px-3 py-1.5">
        <Filter className="h-3 w-3 text-zinc-500" aria-hidden="true" />
        {(['error', 'warning', 'info'] as const).map((sev) => {
          const isActive = severityFilter.has(sev);
          const Icon = SEVERITY_ICON[sev];
          const counts = { error: errorCount, warning: warningCount, info: infoCount };
          return (
            <button
              key={sev}
              type="button"
              onClick={() => toggleSeverity(sev)}
              aria-pressed={isActive}
              aria-label={`${sev} diagnostics (${counts[sev]})`}
              className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                isActive
                  ? `${SEVERITY_BG[sev]} ${SEVERITY_COLOR[sev]}`
                  : 'bg-transparent text-zinc-600'
              }`}
            >
              <Icon className="h-2.5 w-2.5" aria-hidden="true" />
              <span className="capitalize">{sev}</span>
              <span className="tabular-nums">({counts[sev]})</span>
            </button>
          );
        })}
      </div>

      {/* ---- Extension filter ---------------------------------------------- */}
      {allExtensions.length > 1 && (
        <div className="border-b border-white/5 px-3 py-1.5">
          <label className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span>Extension:</span>
            <select
              value={extensionFilter ?? ''}
              onChange={(e) => setExtensionFilter(e.target.value || null)}
              className="rounded border border-white/10 bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300 focus:outline-none focus:border-zinc-500"
              aria-label="Filter by extension"
            >
              <option value="">All extensions</option>
              {allExtensions.map((ext) => (
                <option key={ext} value={ext}>
                  {ext}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {/* ---- Diagnostic list ----------------------------------------------- */}
      <div
        className="overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label={`${totalCount} diagnostic${totalCount === 1 ? '' : 's'}`}
        aria-relevant="additions removals"
      >
        {groups.length === 0 ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <Info className="h-5 w-5 text-zinc-600" aria-hidden="true" />
            <p className="text-[11px] text-zinc-500">
              {hasActiveFilters
                ? 'No diagnostics match the current filters.'
                : 'No diagnostics.'}
            </p>
          </div>
        ) : (
          <div className="flex flex-col">
            {groups.map((group) => {
              const extKey = group.extensionId;
              const isExtExpanded = expandedExtensions.has(extKey);

              return (
                <div key={extKey} className="border-b border-white/5 last:border-b-0">
                  {/* Extension header */}
                  <button
                    type="button"
                    onClick={() => toggleExtensionExpand(extKey)}
                    className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left hover:bg-white/5 transition-colors"
                    aria-expanded={isExtExpanded}
                    aria-label={`${group.extensionId} — ${group.totalCount} diagnostic${group.totalCount === 1 ? '' : 's'}`}
                  >
                    {isExtExpanded ? (
                      <ChevronDown className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                    ) : (
                      <ChevronRight className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
                    )}
                    <span className="font-medium text-zinc-300 truncate">
                      {group.extensionId}
                    </span>
                    <span className="rounded-full bg-zinc-800 px-1 py-0 text-[10px] text-zinc-500 tabular-nums">
                      {group.totalCount}
                    </span>
                  </button>

                  {/* Extension body */}
                  {isExtExpanded && (
                    <div className="flex flex-col">
                      {[...group.contributions.entries()]
                        .sort(([a], [b]) => a.localeCompare(b))
                        .map(([contribId, diags]) => {
                          const contribKey = `${extKey}::${contribId}`;
                          const isContribExpanded = expandedContributions.has(contribKey);

                          return (
                            <div key={contribKey} className="border-t border-white/5">
                              {/* Contribution header */}
                              <button
                                type="button"
                                onClick={() => toggleContributionExpand(contribKey)}
                                className="flex w-full items-center gap-1.5 pl-6 pr-3 py-1 text-left hover:bg-white/5 transition-colors"
                                aria-expanded={isContribExpanded}
                                aria-label={`${contribId} — ${diags.length} diagnostic${diags.length === 1 ? '' : 's'}`}
                              >
                                {isContribExpanded ? (
                                  <ChevronDown className="h-2.5 w-2.5 shrink-0 text-zinc-600" aria-hidden="true" />
                                ) : (
                                  <ChevronRight className="h-2.5 w-2.5 shrink-0 text-zinc-600" aria-hidden="true" />
                                )}
                                <span className="text-[11px] text-zinc-400 truncate">
                                  {contribId}
                                </span>
                                <span className="rounded-full bg-zinc-800 px-1 py-0 text-[9px] text-zinc-600 tabular-nums">
                                  {diags.length}
                                </span>
                              </button>

                              {/* Diagnostic items */}
                              {isContribExpanded && (
                                <div className="flex flex-col">
                                  {diags.map((diag) => {
                                    const SevIcon = SEVERITY_ICON[diag.severity];
                                    return (
                                      <div
                                        key={diag.id ?? `${diag.code}-${diag.message}`}
                                        data-video-editor-diagnostic-item="true"
                                        data-video-editor-diagnostic-severity={diag.severity}
                                        data-video-editor-diagnostic-code={diag.code}
                                        data-video-editor-diagnostic-source-map-stale={
                                          sourceMapStaleTargetIds &&
                                          diag.detail &&
                                          typeof diag.detail.clipId === 'string' &&
                                          sourceMapStaleTargetIds.has(diag.detail.clipId)
                                            ? 'true'
                                            : 'false'
                                        }
                                        className="flex flex-col gap-0.5 border-t border-white/5 pl-10 pr-3 py-1.5 hover:bg-white/5 transition-colors"
                                      >
                                        {/* Row 1: severity icon + message */}
                                        <div className="flex items-start gap-1.5">
                                          <SevIcon
                                            className={`mt-0.5 h-2.5 w-2.5 shrink-0 ${SEVERITY_COLOR[diag.severity]}`}
                                            aria-hidden="true"
                                          />
                                          <div className="min-w-0 flex-1">
                                            <span className="text-[11px] text-zinc-300 break-words">
                                              {diag.message}
                                            </span>
                                            {diag.code && (
                                              <span className="ml-1 text-[10px] text-zinc-600">
                                                [{diag.code}]
                                              </span>
                                            )}
                                          </div>
                                        </div>

                                        {/* Source-map stale indicator */}
                                        {sourceMapStaleTargetIds &&
                                          diag.detail &&
                                          typeof diag.detail.clipId === 'string' &&
                                          sourceMapStaleTargetIds.has(diag.detail.clipId) && (
                                            <div className="pl-4 flex items-center gap-1">
                                              <MapPinOff className="h-2.5 w-2.5 text-purple-400" aria-hidden="true" />
                                              <span
                                                className="text-[10px] text-purple-400 font-medium"
                                                data-video-editor-diagnostic-source-map-stale-badge="true"
                                              >
                                                Source map stale
                                              </span>
                                            </div>
                                        )}
                                        {/* Row 2: source range (verbatim 1-based) */}
                                        {diag.sourceRange && (
                                          <div className="pl-4">
                                            <span
                                              className="text-[10px] text-zinc-500 font-mono"
                                              data-video-editor-diagnostic-source-range="true"
                                            >
                                              {formatSourceRange(diag.sourceRange)}
                                            </span>
                                            {diag.relatedRanges && diag.relatedRanges.length > 0 && (
                                              <span className="ml-1 text-[10px] text-zinc-600 font-mono">
                                                +{diag.relatedRanges.length} related
                                              </span>
                                            )}
                                          </div>
                                        )}

                                        {/* Row 3: detail (summary) */}
                                        {diag.detail && Object.keys(diag.detail).length > 0 && (
                                          <div className="pl-4">
                                            <span className="text-[10px] text-zinc-600 break-words">
                                              {Object.entries(diag.detail)
                                                .filter(([, v]) => v !== undefined && typeof v !== 'object')
                                                .map(([k, v]) => `${k}=${v}`)
                                                .join(', ')}
                                            </span>
                                          </div>
                                        )}

                                        {/* Milestone badge */}
                                        {diag.milestone && (
                                          <div className="pl-4">
                                            <span className="rounded bg-zinc-800 px-1 py-0 text-[9px] text-zinc-500">
                                              {diag.milestone}
                                            </span>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
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
