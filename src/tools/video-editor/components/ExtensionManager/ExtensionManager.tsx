/**
 * ExtensionManager — Manager host for the Extensions tab in PropertiesPanel.
 *
 * Displays the package state inventory from the extension runtime, with
 * status badges, metadata, state reasons, and per-package enable/disable
 * controls backed by ExtensionStateRepository.putEnablementState.
 *
 * Scope boundary (SD2): Only manages packages already loaded/supplied by
 * the host; does not add external package resolution, install, update,
 * delete, discovery, or marketplace flows.
 *
 * Visibility principle (SD3): Disabled packages remain visible and
 * inspectable; invalid, incompatible, and duplicate packages are never
 * hidden.
 */

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Ban,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Info,
  Layers,
  Loader2,
  Puzzle,
  Save,
  Settings,
  ShieldX,
  ToggleLeft,
  ToggleRight,
  Undo2,
  X,
  Zap,
} from 'lucide-react';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import type { PackageState } from '@/tools/video-editor/runtime/extensionLoader';
import type { PackageStateInventoryEntry } from '@/tools/video-editor/runtime/extensionSurface';
import type { ContributionKind, Diagnostic, DiagnosticSeverity, ExtensionManifest } from '@reigh/editor-sdk';
import type {
  ExtensionEnablementState,
  ExtensionSettingsSnapshot,
  ExtensionStateRepository,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import {
  analyzeManifestSettingsSchema,
  reconcileSettingsSnapshot,
  type ReconciliationResult,
  type ReconciliationState,
} from '@/tools/video-editor/runtime/extensionSettings';
import type { ExtensionSettingsNotificationRegistry } from '@/tools/video-editor/runtime/extensionSettingsNotification';
import {
  SchemaForm,
  type SchemaFormHandle,
} from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import { ExtensionTrustWarningBanner } from './ExtensionTrustWarningBanner';

// ---------------------------------------------------------------------------
// State display helpers
// ---------------------------------------------------------------------------

const PACKAGE_STATE_CONFIG: Record<
  PackageState,
  { label: string; icon: typeof CheckCircle; color: string; bg: string }
> = {
  loaded: {
    label: 'Loaded',
    icon: CheckCircle,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10 border-emerald-500/30',
  },
  'disabled-by-user': {
    label: 'Disabled',
    icon: Ban,
    color: 'text-zinc-400',
    bg: 'bg-zinc-500/10 border-zinc-500/30',
  },
  invalid: {
    label: 'Invalid',
    icon: ShieldX,
    color: 'text-red-400',
    bg: 'bg-red-500/10 border-red-500/30',
  },
  incompatible: {
    label: 'Incompatible',
    icon: AlertTriangle,
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10 border-yellow-500/30',
  },
  duplicate: {
    label: 'Duplicate',
    icon: Info,
    color: 'text-blue-400',
    bg: 'bg-blue-500/10 border-blue-500/30',
  },
  'settings-error': {
    label: 'Settings Error',
    icon: AlertCircle,
    color: 'text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/30',
  },
  'runtime-error': {
    label: 'Runtime Error',
    icon: AlertCircle,
    color: 'text-red-400',
    bg: 'bg-red-500/10 border-red-500/30',
  },
};

function PackageStateBadge({ state }: { state: PackageState }) {
  const config = PACKAGE_STATE_CONFIG[state];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${config.bg} ${config.color}`}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Contribution summary helpers
// ---------------------------------------------------------------------------

/** Short human-readable label for each contribution kind. */
const CONTRIBUTION_KIND_LABEL: Partial<Record<ContributionKind, string>> = {
  slot: 'Slot',
  dialog: 'Dialog',
  panel: 'Panel',
  inspectorSection: 'Inspector section',
  overlay: 'Overlay',
  parser: 'Parser',
  outputFormat: 'Output format',
  searchProvider: 'Search provider',
  metadataFacet: 'Metadata facet',
  assetDetailSection: 'Asset detail',
  effect: 'Effect',
  transition: 'Transition',
  shader: 'Shader',
  agentTool: 'Agent tool',
  process: 'Process',
};

export interface ContributionSummary {
  /** Total contributions declared in the extension manifest. */
  readonly declared: number;
  /** Number of contributions currently active (bridged) in the runtime. */
  readonly active: number;
  /** Number of contributions reserved but not yet bridged. */
  readonly inactive: number;
  /** Sorted, deduplicated list of contribution kind labels for the summary. */
  readonly kinds: readonly string[];
}

function deriveContributionSummary(
  extensionId: string,
  extensionRuntime: import('@/tools/video-editor/runtime/extensionSurface').ExtensionRuntime,
): ContributionSummary | null {
  // Find the matching active extension
  const ext = extensionRuntime.extensions.find(
    (e) => (e.manifest.id as string) === extensionId,
  );
  if (!ext) {
    // Non-active package — no contribution data available from active extensions
    return null;
  }

  const declared = ext.manifest.contributions?.length ?? 0;

  // Count active contributions: those whose ID appears in the normalized config
  const activeIds = new Set<string>();
  for (const slotKey of Object.keys(extensionRuntime.config.slots)) {
    activeIds.add(slotKey);
  }
  for (const d of extensionRuntime.config.dialogHost.dialogs) {
    activeIds.add(d.id);
  }
  for (const p of extensionRuntime.config.registry.panels) {
    activeIds.add(p.id);
  }
  for (const s of extensionRuntime.config.registry.inspectorSections) {
    activeIds.add(s.id);
  }
  for (const o of extensionRuntime.config.overlays) {
    activeIds.add(o.id);
  }

  // Also count pipeline descriptor contributions as active
  for (const ap of extensionRuntime.config.assetParsers) {
    activeIds.add(ap.id);
  }
  for (const of_ of extensionRuntime.config.outputFormats) {
    activeIds.add(of_.id);
  }
  for (const sp of extensionRuntime.config.searchProviders) {
    activeIds.add(sp.id);
  }
  for (const mf of extensionRuntime.config.metadataFacets) {
    activeIds.add(mf.id);
  }
  for (const ads of extensionRuntime.config.assetDetailSections) {
    activeIds.add(ads.id);
  }
  for (const eff of extensionRuntime.config.effects) {
    activeIds.add(eff.id);
  }
  for (const tr of extensionRuntime.config.transitions) {
    activeIds.add(tr.id);
  }
  for (const sh of extensionRuntime.config.shaders) {
    activeIds.add(sh.id);
  }
  for (const at of extensionRuntime.config.agentTools) {
    activeIds.add(at.id);
  }
  for (const pr of extensionRuntime.config.processes) {
    activeIds.add(pr.id);
  }

  // Determine which declared contributions are active
  let active = 0;
  const kindSet = new Set<string>();
  for (const contrib of ext.manifest.contributions ?? []) {
    const contribId = contrib.id as string;
    if (activeIds.has(contribId)) {
      active++;
    }
    const kindLabel = CONTRIBUTION_KIND_LABEL[contrib.kind] ?? contrib.kind;
    kindSet.add(kindLabel);
  }

  const inactive = extensionRuntime.inactiveReserved.filter(
    (r) => r.extensionId === extensionId,
  ).length;

  return {
    declared,
    active,
    inactive,
    kinds: [...kindSet].sort(),
  };
}

// ---------------------------------------------------------------------------
// Diagnostic severity styling helpers
// ---------------------------------------------------------------------------

const DIAG_SEVERITY_ICON: Record<DiagnosticSeverity, typeof AlertCircle> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const DIAG_SEVERITY_COLOR: Record<DiagnosticSeverity, string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
};

const DIAG_SEVERITY_BG: Record<DiagnosticSeverity, string> = {
  error: 'bg-red-500/10 border-red-500/30',
  warning: 'bg-yellow-500/10 border-yellow-500/30',
  info: 'bg-blue-500/10 border-blue-500/30',
};

// ---------------------------------------------------------------------------
// Per-package diagnostic summary (from DiagnosticCollection snapshot)
// ---------------------------------------------------------------------------

export interface PackageDiagnosticSummary {
  readonly errorCount: number;
  readonly warningCount: number;
  readonly infoCount: number;
  readonly diagnostics: readonly Diagnostic[];
}

// ---------------------------------------------------------------------------
// Enable/disable save state
// ---------------------------------------------------------------------------

type SaveState = 'idle' | 'saving' | 'error';

const DISABLE_REASON = 'User disabled via extension manager';
const ENABLE_REASON = 'User enabled via extension manager';

// ---------------------------------------------------------------------------
// Settings section states
// ---------------------------------------------------------------------------

type SettingsSectionState =
  | 'collapsed'
  | 'loading'
  | 'idle'
  | 'editing'
  | 'saving'
  | 'error';



// ---------------------------------------------------------------------------
// Package settings section (host repository path)
// ---------------------------------------------------------------------------

function PackageSettingsSection({
  extensionId,
  repository,
  onRefresh,
  manifest,
  settingsNotificationRegistry,
}: {
  extensionId: string;
  repository: ExtensionStateRepository | null;
  onRefresh: () => void;
  manifest?: ExtensionManifest | null;
  /** T10: Host-visible notification registry for manager/runtime coherence. */
  settingsNotificationRegistry?: ExtensionSettingsNotificationRegistry | null;
}) {
  const [sectionState, setSectionState] = useState<SettingsSectionState>('collapsed');
  const [savedSnapshot, setSavedSnapshot] = useState<ExtensionSettingsSnapshot | null>(null);
  const [editValues, setEditValues] = useState<Record<string, unknown>>({});
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [reconciliationResult, setReconciliationResult] = useState<ReconciliationResult | null>(null);
  const [reconciliationExpanded, setReconciliationExpanded] = useState(false);
  // Snapshot of reconciled values at load time, used as the "clean" baseline
  // for dirty detection so repairs (default-fill, coercion) don't look like
  // user edits.
  const baseValuesRef = useRef<Record<string, unknown>>({});
  const schemaFormRef = useRef<SchemaFormHandle>(null);
  const mountedRef = useRef(true);
  // T10: Track whether a save is in flight so the notification reload callback
  // can skip reloading during our own save (avoids redundant re-fetch).
  const savingRef = useRef(false);

  // Fully analyse the manifest schema (T1): returns schema, diagnostics,
  // unsupportedFields, and editable flag.  Replaces the older
  // adaptManifestSettingsSchema call so we can gate the editable surface and
  // feed the analysis into reconcileSettingsSnapshot.
  const schemaAnalysis = useMemo(() => {
    if (!manifest || !manifest.settingsSchema) return null;
    return analyzeManifestSettingsSchema(manifest);
  }, [manifest]);

  // Unsupported schema: manifest has settingsSchema but either the adapter
  // returned no schema at all OR the schema has unsupported constructs
  // ($ref, combinators, arrays, nested objects, conditionals).
  const hasUnsupportedSchema =
    schemaAnalysis !== null && !schemaAnalysis.editable;

  // ---- Reconciliation derived values (T4) — must be before callbacks that
  //      reference them to avoid temporal dead zone. ------------------------
  const reconciliationState: ReconciliationState | null =
    reconciliationResult?.state ?? null;
  const isBlocked = reconciliationState === 'blocked';

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // T10: Subscribe to settings change notifications from the shared registry.
  // When runtime code writes through settings.set()/settings.delete(), the
  // manager reloads and reconciles the updated values without remounting.
  useEffect(() => {
    if (!settingsNotificationRegistry || settingsNotificationRegistry.isDisposed) return;

    // Only subscribe when the section is expanded (not collapsed).
    if (sectionState === 'collapsed') return;

    let cancelled = false;

    const handle = settingsNotificationRegistry.subscribeToExtension(
      extensionId,
      async () => {
        // Skip reload during our own save to avoid redundant re-fetch.
        if (!mountedRef.current || cancelled || savingRef.current) return;

        try {
          const snapshot = repository
            ? await repository.getSettingsSnapshot(extensionId)
            : null;

          if (!mountedRef.current || cancelled) return;

          if (manifest) {
            const result = reconcileSettingsSnapshot({ manifest, snapshot });
            setReconciliationResult(result);
            setSavedSnapshot(snapshot);
            setEditValues(result.values);
            baseValuesRef.current = { ...result.values };
          } else {
            setSavedSnapshot(snapshot);
            const fallbackValues = snapshot ? { ...snapshot.values } : {};
            setEditValues(fallbackValues);
            baseValuesRef.current = fallbackValues;
          }
        } catch {
          // Reload failed — silently keep current values.
        }
      },
    );

    return () => {
      cancelled = true;
      handle.dispose();
    };
  }, [sectionState, extensionId, repository, manifest, settingsNotificationRegistry]);

  // Load settings from the repository when expanding.
  const handleExpand = useCallback(async () => {
    if (sectionState === 'loading' || sectionState === 'saving') return;
    if (sectionState !== 'collapsed') {
      setSectionState('collapsed');
      return;
    }

    // Unsupported schemas: load snapshot, run reconciliation for blocker
    // diagnostics, then display read-only preview (no editable controls).
    if (hasUnsupportedSchema) {
      setSectionState('loading');
      setSettingsError(null);
      setReconciliationResult(null);

      try {
        let snapshot: ExtensionSettingsSnapshot | null = null;
        if (repository) {
          snapshot = await repository.getSettingsSnapshot(extensionId);
        }

        if (!mountedRef.current) return;

        // Run reconciliation even for unsupported schemas so the diagnostic
        // row can show why the schema is blocked.
        if (manifest) {
          const result = reconcileSettingsSnapshot({ manifest, snapshot });
          setReconciliationResult(result);
        }

        setSavedSnapshot(snapshot);
        // Display values read-only (empty object if no snapshot).
        const displayValues = snapshot ? { ...snapshot.values } : {};
        setEditValues(displayValues);
        baseValuesRef.current = displayValues;
        setSectionState('idle');
      } catch (err) {
        if (mountedRef.current) {
          setSettingsError(err instanceof Error ? err.message : 'Failed to load settings');
          setSectionState('error');
        }
      }
      return;
    }

    setSectionState('loading');
    setSettingsError(null);
    setReconciliationResult(null);

    try {
      let snapshot: ExtensionSettingsSnapshot | null = null;
      if (repository) {
        snapshot = await repository.getSettingsSnapshot(extensionId);
      }

      if (!mountedRef.current) return;

      // Run reconciliation (T3) when a manifest is available so the
      // manager surface always has a classified state + diagnostics.
      if (manifest) {
        const result = reconcileSettingsSnapshot({ manifest, snapshot });
        setReconciliationResult(result);
        setSavedSnapshot(snapshot);
        setEditValues(result.values);
        baseValuesRef.current = { ...result.values };
        setSectionState('idle');
      } else {
        // No manifest — fall back to raw snapshot values (legacy path).
        setSavedSnapshot(snapshot);
        const fallbackValues = snapshot ? { ...snapshot.values } : {};
        setEditValues(fallbackValues);
        baseValuesRef.current = fallbackValues;
        setSectionState('idle');
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to load settings');
        setSectionState('error');
      }
    }
  }, [sectionState, hasUnsupportedSchema, extensionId, repository, manifest]);

  // Enter editing mode (blocked when reconciliation state is blocked).
  const handleStartEdit = useCallback(() => {
    if (isBlocked) return;
    setSectionState('editing');
    setSettingsError(null);
  }, [isBlocked]);

  // Update a single field value (optimistic, not persisted)
  const handleFieldChange = useCallback((key: string, value: unknown) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Save settings through the repository (blocked when reconciliation is blocked).
  const handleSave = useCallback(async () => {
    if (!repository || isBlocked) return;

    // Validate all SchemaForm fields and focus the first invalid widget.
    if (schemaFormRef.current && !schemaFormRef.current.validateAndFocus()) {
      // Validation failed — focus already directed to the first error.
      return;
    }

    setSectionState('saving');
    setSettingsError(null);
    savingRef.current = true;

    const now = new Date().toISOString();
    const snapshot: ExtensionSettingsSnapshot = {
      extensionId,
      schemaVersion: manifest?.settingsSchema?.version ?? 1,
      values: { ...editValues },
      lastWrittenAt: now,
    };

    try {
      await repository.putSettingsSnapshot(snapshot);
      if (mountedRef.current) {
        setSavedSnapshot(snapshot);
        setSectionState('idle');
        onRefresh();

        // T10: Publish save through the shared notification path so active
        // extensions and other host consumers see the update.
        if (settingsNotificationRegistry && !settingsNotificationRegistry.isDisposed) {
          settingsNotificationRegistry.notifySettingsChanged(extensionId);
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to save settings');
        setSectionState('error');
      }
    } finally {
      savingRef.current = false;
    }
  }, [extensionId, editValues, onRefresh, repository, manifest, isBlocked, settingsNotificationRegistry]);

  // Cancel: revert to the reconciled baseline values (not raw snapshot).
  const handleCancel = useCallback(() => {
    setEditValues({ ...baseValuesRef.current });
    setSectionState('idle');
    setSettingsError(null);
  }, []);

  // Reset: delete settings, clear reconciliation, re-materialize defaults.
  const handleReset = useCallback(async () => {
    if (!repository || isBlocked) return;
    setSectionState('saving');
    setSettingsError(null);

    try {
      await repository.deleteSettingsSnapshot(extensionId);
      if (mountedRef.current) {
        setSavedSnapshot(null);
        setReconciliationResult(null);
        // Re-materialize: re-run reconciliation with null snapshot
        if (manifest) {
          const result = reconcileSettingsSnapshot({ manifest, snapshot: null });
          setReconciliationResult(result);
          setEditValues(result.values);
          baseValuesRef.current = { ...result.values };
        } else {
          setEditValues({});
          baseValuesRef.current = {};
        }
        setSectionState('idle');
        onRefresh();
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to reset settings');
        setSectionState('error');
      }
    }
  }, [extensionId, onRefresh, repository, manifest, isBlocked]);

  // Retry after error
  const handleSettingsRetry = useCallback(() => {
    setSettingsError(null);
    setSectionState('collapsed');
    // Trigger re-expand
    setTimeout(() => {
      if (mountedRef.current) {
        setSectionState('loading');
        handleExpand();
      }
    }, 0);
  }, [handleExpand]);



  const hasSnapshot = savedSnapshot !== null;
  const hasValues = Object.keys(editValues).length > 0;
  // Compare against the reconciled baseline so auto-repairs (default-fill,
  // type coercion) don't falsely flag the form as dirty.
  const isDirty =
    JSON.stringify(editValues) !== JSON.stringify(baseValuesRef.current);

  const settingsKeys = Object.keys(editValues).sort();

  // ---- Reconciliation diagnostic helpers (T4) ---------------------------

  /** Count of reconciliation diagnostics that are not schema-adapter noise. */
  const reconciliationDiagCount =
    reconciliationResult?.diagnostics.filter(
      (d) => !d.code?.startsWith('settings/unsupported-schema'),
    ).length ?? 0;

  /** Human-readable label for the reconciliation state badge. */
  function reconciliationBadgeLabel(state: ReconciliationState): string {
    switch (state) {
      case 'clean':
        return 'Settings OK';
      case 'repaired':
        return 'Auto-repaired';
      case 'needs-review':
        return 'Needs review';
      case 'blocked':
        return 'Settings blocked';
    }
  }

  /** Severity-driven color classes for the reconciliation row. */
  function reconciliationRowStyle(state: ReconciliationState): string {
    switch (state) {
      case 'clean':
        return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
      case 'repaired':
        return 'bg-blue-500/10 border-blue-500/30 text-blue-400';
      case 'needs-review':
        return 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400';
      case 'blocked':
        return 'bg-red-500/10 border-red-500/30 text-red-400';
    }
  }

  /** Icon component per reconciliation state. */
  function ReconciliationIcon({ state }: { state: ReconciliationState }) {
    switch (state) {
      case 'clean':
        return <CheckCircle className="h-3 w-3 shrink-0" />;
      case 'repaired':
        return <Info className="h-3 w-3 shrink-0" />;
      case 'needs-review':
        return <AlertTriangle className="h-3 w-3 shrink-0" />;
      case 'blocked':
        return <AlertCircle className="h-3 w-3 shrink-0" />;
    }
  }

  return (
    <div className="mt-2 border-t border-border pt-2" data-video-editor-extension-settings={extensionId}>
      {/* Collapsed: show expand toggle */}
      {sectionState === 'collapsed' && (
        <button
          type="button"
          onClick={handleExpand}
          className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Show extension settings"
          data-video-editor-extension-settings-toggle={extensionId}
        >
          <Settings className="h-3 w-3" />
          <span>Settings</span>
          {hasSnapshot && (
            <span className="text-[10px] text-muted-foreground/60">
              ({settingsKeys.length} value{settingsKeys.length !== 1 ? 's' : ''})
            </span>
          )}
          <ChevronRight className="h-3 w-3" />
        </button>
      )}

      {/* Loading */}
      {sectionState === 'loading' && (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground" role="status" aria-label="Loading settings">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Loading settings…</span>
        </div>
      )}

      {/* ---- Reconciliation diagnostic row (T4) ---- */}
      {reconciliationResult &&
        (sectionState === 'idle' || sectionState === 'editing') && (
          <div
            className={`mt-1.5 rounded border px-2 py-1 text-[10px] ${reconciliationRowStyle(reconciliationResult.state)}`}
            data-video-editor-extension-settings-reconciliation={extensionId}
            data-video-editor-extension-settings-reconciliation-state={reconciliationResult.state}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1 font-medium">
                <ReconciliationIcon state={reconciliationResult.state} />
                {reconciliationBadgeLabel(reconciliationResult.state)}
              </span>
              {reconciliationDiagCount > 0 && (
                <button
                  type="button"
                  onClick={() => setReconciliationExpanded((prev) => !prev)}
                  className="inline-flex items-center gap-0.5 text-[10px] underline hover:opacity-80 transition-opacity"
                  aria-expanded={reconciliationExpanded}
                  aria-label={`${reconciliationExpanded ? 'Hide' : 'Show'} reconciliation details`}
                  data-video-editor-extension-settings-reconciliation-toggle={extensionId}
                >
                  {reconciliationDiagCount} detail{reconciliationDiagCount !== 1 ? 's' : ''}
                  {reconciliationExpanded ? (
                    <ChevronDown className="h-2.5 w-2.5" />
                  ) : (
                    <ChevronRight className="h-2.5 w-2.5" />
                  )}
                </button>
              )}
            </div>
            {reconciliationExpanded && reconciliationDiagCount > 0 && (
              <div className="mt-1 flex flex-col gap-0.5 max-h-32 overflow-y-auto">
                {reconciliationResult.diagnostics
                  .filter((d) => !d.code?.startsWith('settings/unsupported-schema'))
                  .map((diag, idx) => {
                    const SevIcon = DIAG_SEVERITY_ICON[diag.severity];
                    return (
                      <div
                        key={`${diag.code ?? 'diag'}-${idx}`}
                        className="flex items-start gap-1 text-[10px] text-foreground/80"
                      >
                        <SevIcon
                          className={`mt-0.5 h-2.5 w-2.5 shrink-0 ${DIAG_SEVERITY_COLOR[diag.severity]}`}
                          aria-hidden="true"
                        />
                        <span>{diag.message}</span>
                      </div>
                    );
                  })}
                {reconciliationResult.droppedUnknownFields.length > 0 && (
                  <div className="text-[10px] text-muted-foreground/70 mt-0.5">
                    Dropped unknown fields:{' '}
                    {reconciliationResult.droppedUnknownFields.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      {/* No settings saved, not editing */}
      {(sectionState === 'idle') && !hasValues && (
        <div>
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={handleExpand}
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Hide extension settings"
            >
              <Settings className="h-3 w-3" />
              <span>Settings</span>
              <ChevronDown className="h-3 w-3" />
            </button>
          </div>
          <div className="mt-1.5 text-[11px] text-muted-foreground/60" data-video-editor-extension-settings-empty={extensionId}>
            No saved settings for this extension.
          </div>
        </div>
      )}

      {/* Idle: show saved values (read-only) */}
      {sectionState === 'idle' && hasValues && (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <button
              type="button"
              onClick={handleExpand}
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Hide extension settings"
            >
              <Settings className="h-3 w-3" />
              <span>Settings</span>
              <ChevronDown className="h-3 w-3" />
            </button>
            {!hasUnsupportedSchema && (
              <button
                type="button"
                onClick={handleStartEdit}
                disabled={isBlocked}
                className="text-[10px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                aria-label="Edit extension settings"
                data-video-editor-extension-settings-edit={extensionId}
              >
                Edit
              </button>
            )}
            {hasUnsupportedSchema && (
              <span className="text-[10px] text-yellow-400/80 font-medium">Read-only</span>
            )}
          </div>
          {settingsKeys.map((key) => (
            <div key={key} className="flex items-center gap-2 py-0.5 text-[11px]">
              <span className="font-medium text-muted-foreground min-w-[80px] truncate">{key}</span>
              <span className="text-foreground/80 truncate">{String(editValues[key] ?? '')}</span>
            </div>
          ))}
          {savedSnapshot && (
            <div className="mt-1 text-[10px] text-muted-foreground/50">
              Last saved: {new Date(savedSnapshot.lastWrittenAt).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* Editing: SchemaForm (supported schemas) or fallback key-value editor */}
      {sectionState === 'editing' && (
        <div>
          <div className="flex items-center gap-1 mb-1.5 text-[11px] text-muted-foreground">
            <Settings className="h-3 w-3" />
            <span>Editing settings</span>
          </div>
          {schemaAnalysis?.schema ? (
            <SchemaForm
              ref={schemaFormRef}
              schema={schemaAnalysis.schema}
              values={editValues}
              onChange={handleFieldChange}
            />
          ) : settingsKeys.length > 0 ? (
            settingsKeys.map((key) => (
              <div key={key} className="flex items-center gap-2 py-0.5">
                <label className="text-[11px] font-medium text-muted-foreground min-w-[80px] truncate">
                  {key}
                </label>
                <input
                  type="text"
                  value={String(editValues[key] ?? '')}
                  onChange={(e) => handleFieldChange(key, e.target.value)}
                  className="flex-1 rounded border border-border bg-background px-1.5 py-0.5 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  aria-label={`Settings value for ${key}`}
                  data-video-editor-extension-settings-field={key}
                />
              </div>
            ))
          ) : (
            <div className="text-[11px] text-muted-foreground/60">No settings keys defined.</div>
          )}
          {/* Action buttons */}
          <div className="mt-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleSave}
              disabled={!isDirty || isBlocked}
              className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Save extension settings"
              data-video-editor-extension-settings-save={extensionId}
            >
              <Save className="h-3 w-3" />
              Save
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={!isDirty}
              className="inline-flex items-center gap-1 rounded bg-muted/50 border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Cancel extension settings changes"
              data-video-editor-extension-settings-cancel={extensionId}
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 rounded bg-red-500/10 border border-red-500/30 px-2 py-0.5 text-[10px] font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              aria-label="Reset extension settings"
              data-video-editor-extension-settings-reset={extensionId}
            >
              <Undo2 className="h-3 w-3" />
              Reset
            </button>
          </div>
        </div>
      )}

      {/* Saving */}
      {sectionState === 'saving' && (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground" role="status" aria-label="Saving settings">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Saving settings…</span>
        </div>
      )}

      {/* Error */}
      {sectionState === 'error' && settingsError && (
        <div
          className="rounded bg-red-500/10 border border-red-500/30 px-2 py-1 text-[11px] text-red-400"
          role="alert"
          data-video-editor-extension-settings-error={extensionId}
        >
          <div className="flex items-center justify-between gap-2">
            <span>Settings error: {settingsError}</span>
            <button
              type="button"
              onClick={handleSettingsRetry}
              className="shrink-0 text-[10px] underline hover:text-red-300 transition-colors"
              aria-label="Retry extension settings"
              data-video-editor-extension-settings-retry={extensionId}
            >
              Retry
            </button>
          </div>
        </div>
      )}


    </div>
  );
}

// ---------------------------------------------------------------------------
// Package card
// ---------------------------------------------------------------------------

type PermissionDisclosure = NonNullable<ExtensionManifest['permissions']>[number];
type PermissionPosture = NonNullable<PermissionDisclosure['posture']>;

const DISCLOSED_ACCESS_LABELS: readonly {
  key: keyof PermissionPosture;
  label: string;
}[] = [
  { key: 'network', label: 'Network' },
  { key: 'filesystem', label: 'Filesystem' },
  { key: 'env', label: 'Environment' },
  { key: 'processes', label: 'Processes' },
];

function getDisclosedAccessLabels(disclosure: PermissionDisclosure): readonly string[] {
  return DISCLOSED_ACCESS_LABELS
    .filter(({ key }) => disclosure.posture?.[key])
    .map(({ label }) => label);
}

function PackageCard({
  entry,
  contributionSummary,
  repository,
  onToggleRequest,
  manifest,
  diagnosticSummary,
  settingsNotificationRegistry,
}: {
  entry: PackageStateInventoryEntry;
  contributionSummary: ContributionSummary | null;
  repository: ExtensionStateRepository | null;
  onToggleRequest: () => void;
  manifest?: ExtensionManifest | null;
  diagnosticSummary?: PackageDiagnosticSummary;
  /** T10: Host-visible notification registry for manager/runtime coherence. */
  settingsNotificationRegistry?: ExtensionSettingsNotificationRegistry | null;
}) {
  const { extensionId, packageState, stateReason, packageMetadata } = entry;
  const label = packageMetadata?.label ?? extensionId;
  const version = packageMetadata?.version;
  const publisher = packageMetadata?.publisher;
  const description = packageMetadata?.description;

  // T11: Direct host-supplied extensions are read-only (no install/update/toggle affordances).
  const isDirectEntry = stateReason === 'Direct host-supplied extension';

  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [diagnosticsExpanded, setDiagnosticsExpanded] = useState(false);

  const isToggleable = (packageState === 'loaded' || packageState === 'disabled-by-user') && !isDirectEntry;
  const isCurrentlyEnabled = packageState === 'loaded';

  // Derive diagnostic counts from summary or fallback to zero
  const diagErrorCount = diagnosticSummary?.errorCount ?? 0;
  const diagWarningCount = diagnosticSummary?.warningCount ?? 0;
  const diagInfoCount = diagnosticSummary?.infoCount ?? 0;
  const hasDiagnostics = diagErrorCount > 0 || diagWarningCount > 0 || diagInfoCount > 0;
  const permissionDisclosures = manifest?.permissions ?? [];

  const contribLine = useMemo(() => {
    if (!contributionSummary) return null;
    if (contributionSummary.declared === 0) return null;

    const parts: string[] = [];
    parts.push(`${contributionSummary.declared} contribution${contributionSummary.declared !== 1 ? 's' : ''}`);
    if (contributionSummary.active > 0 && contributionSummary.active < contributionSummary.declared) {
      parts.push(`${contributionSummary.active} active`);
    }
    if (contributionSummary.inactive > 0) {
      parts.push(`${contributionSummary.inactive} inactive`);
    }

    return parts.join(' · ');
  }, [contributionSummary]);

  const handleToggle = useCallback(async () => {
    if (!repository) return;

    const newEnabled = !isCurrentlyEnabled;
    const reason = newEnabled ? ENABLE_REASON : DISABLE_REASON;
    const now = new Date().toISOString();

    const enablementState: ExtensionEnablementState = {
      extensionId,
      enabled: newEnabled,
      lastToggledAt: now,
      toggleReason: reason,
    };

    setSaveState('saving');
    setSaveError(null);

    try {
      await repository.putEnablementState(enablementState);
      setSaveState('idle');
      onToggleRequest();
    } catch (err) {
      setSaveState('error');
      setSaveError(err instanceof Error ? err.message : 'Failed to save enablement state');
    }
  }, [extensionId, isCurrentlyEnabled, onToggleRequest, repository]);

  const handleRetry = useCallback(() => {
    setSaveState('idle');
    setSaveError(null);
  }, []);

  return (
    <div
      className="rounded-lg border border-border bg-card/60 p-3 transition-colors"
      data-video-editor-extension-package-id={extensionId}
      data-video-editor-extension-package-state={packageState}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Puzzle className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-medium text-foreground">
              {label}
            </span>
            {version && (
              <span className="shrink-0 text-[11px] text-muted-foreground">
                v{version}
              </span>
            )}
          </div>
          {publisher && (
            <div className="mt-0.5 text-[11px] text-muted-foreground/70">
              {publisher}
            </div>
          )}
          {description && (
            <div className="mt-1 line-clamp-2 text-xs text-muted-foreground/80">
              {description}
            </div>
          )}
          {contribLine && (
            <div className="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground/70">
              <Layers className="h-3 w-3 shrink-0" />
              <span>{contribLine}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Diagnostic badges — show error/warning/info counts per package */}
          {hasDiagnostics && (
            <div className="flex items-center gap-1" data-video-editor-extension-diagnostic-badges={extensionId}>
              {diagErrorCount > 0 && (
                <span
                  className="inline-flex items-center gap-0.5 rounded-full bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-400 tabular-nums"
                  title={`${diagErrorCount} error${diagErrorCount === 1 ? '' : 's'}`}
                  data-video-editor-extension-diag-count="error"
                >
                  <AlertCircle className="h-2.5 w-2.5" aria-hidden="true" />
                  {diagErrorCount}
                </span>
              )}
              {diagWarningCount > 0 && (
                <span
                  className="inline-flex items-center gap-0.5 rounded-full bg-yellow-500/10 px-1.5 py-0.5 text-[10px] text-yellow-400 tabular-nums"
                  title={`${diagWarningCount} warning${diagWarningCount === 1 ? '' : 's'}`}
                  data-video-editor-extension-diag-count="warning"
                >
                  <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                  {diagWarningCount}
                </span>
              )}
              {diagInfoCount > 0 && (
                <span
                  className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/10 px-1.5 py-0.5 text-[10px] text-blue-400 tabular-nums"
                  title={`${diagInfoCount} info diagnostic${diagInfoCount === 1 ? '' : 's'}`}
                  data-video-editor-extension-diag-count="info"
                >
                  <Info className="h-2.5 w-2.5" aria-hidden="true" />
                  {diagInfoCount}
                </span>
              )}
            </div>
          )}
          {isToggleable && repository && (
            <button
              type="button"
              onClick={
                saveState === 'error'
                  ? handleRetry
                  : saveState === 'saving'
                    ? undefined
                    : handleToggle
              }
              disabled={saveState === 'saving'}
              className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors hover:bg-muted/60 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={
                saveState === 'saving'
                  ? `Saving ${extensionId} enablement state`
                  : saveState === 'error'
                    ? `Retry saving ${extensionId} enablement state`
                    : isCurrentlyEnabled
                      ? `Disable ${extensionId}`
                      : `Enable ${extensionId}`
              }
              data-video-editor-extension-toggle={extensionId}
            >
              {saveState === 'saving' ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  <span className="text-muted-foreground">Saving…</span>
                </>
              ) : isCurrentlyEnabled ? (
                <>
                  <ToggleRight className="h-3 w-3 text-emerald-400" />
                  <span className="text-emerald-400">Enabled</span>
                </>
              ) : (
                <>
                  <ToggleLeft className="h-3 w-3 text-zinc-400" />
                  <span className="text-zinc-400">Disabled</span>
                </>
              )}
            </button>
          )}
          {isDirectEntry && (
            <span
              className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium bg-blue-500/10 border-blue-500/30 text-blue-400"
              title="Direct host-supplied extension — read-only"
              data-video-editor-extension-direct-entry={extensionId}
            >
              <Zap className="h-3 w-3" />
              Direct
            </span>
          )}
          <PackageStateBadge state={packageState} />
        </div>
      </div>
      {stateReason && (
        <div className="mt-2 rounded bg-muted/50 px-2 py-1 text-[11px] text-muted-foreground">
          {stateReason}
        </div>
      )}
      {saveState === 'error' && saveError && (
        <div
          className="mt-2 rounded bg-red-500/10 border border-red-500/30 px-2 py-1 text-[11px] text-red-400"
          role="alert"
          data-video-editor-extension-save-error={extensionId}
        >
          Failed to save: {saveError}
        </div>
      )}

      {permissionDisclosures.length > 0 && (
        <div
          className="mt-2 rounded border border-border bg-muted/30 px-2 py-1.5 text-[11px]"
          data-video-editor-extension-access-disclosures={extensionId}
        >
          <div className="mb-1 flex items-center gap-1 text-muted-foreground">
            <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
            <span className="font-medium text-foreground">Access disclosures</span>
          </div>
          <div className="flex flex-col gap-1.5">
            {permissionDisclosures.map((disclosure, index) => {
              const labels = getDisclosedAccessLabels(disclosure);
              const key = `${index}-${disclosure.reason}`;
              return (
                <div
                  key={key}
                  className="flex flex-col gap-1"
                  data-video-editor-extension-access-disclosure="true"
                >
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="text-muted-foreground/70">Disclosed access:</span>
                    {labels.length > 0 ? (
                      labels.map((label) => (
                        <span
                          key={label}
                          className="inline-flex items-center rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                        >
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="text-muted-foreground/70">No broad access disclosed</span>
                    )}
                  </div>
                  <div className="text-muted-foreground/80">
                    <span className="text-muted-foreground/70">Declaration reason:</span>{' '}
                    <span>{disclosure.reason}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Expandable diagnostic details — per-package inline diagnostics from DiagnosticCollection */}
      {hasDiagnostics && (
        <div className="mt-2 border-t border-border pt-2" data-video-editor-extension-diagnostics={extensionId}>
          <button
            type="button"
            onClick={() => setDiagnosticsExpanded((prev) => !prev)}
            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            aria-expanded={diagnosticsExpanded}
            aria-label={`${diagnosticsExpanded ? 'Hide' : 'Show'} diagnostics for ${label}`}
            data-video-editor-extension-diagnostics-toggle={extensionId}
          >
            {diagnosticsExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <AlertCircle className="h-3 w-3" />
            <span>Diagnostics</span>
            <span className="text-[10px] tabular-nums">
              ({diagErrorCount + diagWarningCount + diagInfoCount})
            </span>
          </button>

          {diagnosticsExpanded && (
            <div
              className="mt-1.5 flex flex-col gap-1 max-h-48 overflow-y-auto"
              role="log"
              aria-live="polite"
              aria-label={`${diagErrorCount + diagWarningCount + diagInfoCount} diagnostic${diagErrorCount + diagWarningCount + diagInfoCount === 1 ? '' : 's'} for ${label}`}
              aria-relevant="additions removals"
            >
              {diagnosticSummary?.diagnostics.map((diag, idx) => {
                const SevIcon = DIAG_SEVERITY_ICON[diag.severity];
                const diagId = diag.id ?? `${diag.code}-${idx}`;
                return (
                  <div
                    key={diagId}
                    data-video-editor-extension-diag-item="true"
                    data-video-editor-extension-diag-severity={diag.severity}
                    data-video-editor-extension-diag-code={diag.code}
                    className={`rounded border px-2 py-1 text-[10px] ${DIAG_SEVERITY_BG[diag.severity]}`}
                  >
                    <div className="flex items-start gap-1.5">
                      <SevIcon
                        className={`mt-0.5 h-2.5 w-2.5 shrink-0 ${DIAG_SEVERITY_COLOR[diag.severity]}`}
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <span className={`break-words ${DIAG_SEVERITY_COLOR[diag.severity]}`}>
                          {diag.message}
                        </span>
                        {diag.code && (
                          <span className="ml-1 text-muted-foreground/60">[{diag.code}]</span>
                        )}
                        {diag.contributionId && (
                          <span className="ml-1 text-muted-foreground/40">
                            in {diag.contributionId}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Settings section — visible for all package states (SD3) */}
      <PackageSettingsSection
        extensionId={extensionId}
        repository={repository}
        onRefresh={onToggleRequest}
        manifest={manifest}
        settingsNotificationRegistry={settingsNotificationRegistry}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------

function ManagerSummaryBar({
  entries,
}: {
  entries: readonly PackageStateInventoryEntry[];
}) {
  const counts = useMemo(() => {
    const result: Record<PackageState, number> = {
      loaded: 0,
      'disabled-by-user': 0,
      invalid: 0,
      incompatible: 0,
      duplicate: 0,
      'settings-error': 0,
      'runtime-error': 0,
    };
    for (const e of entries) {
      result[e.packageState]++;
    }
    return result;
  }, [entries]);

  const hasIssues =
    counts.invalid > 0 ||
    counts.incompatible > 0 ||
    counts['runtime-error'] > 0 ||
    counts['settings-error'] > 0;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-border bg-card/40 px-3 py-2 text-xs text-muted-foreground"
      aria-label={`Extension summary: ${entries.length} packages, ${counts.loaded} loaded`}
    >
      <span className="flex items-center gap-1">
        <Puzzle className="h-3.5 w-3.5" />
        {entries.length} package{entries.length !== 1 ? 's' : ''}
      </span>
      {counts.loaded > 0 && (
        <span className="flex items-center gap-1 text-emerald-400">
          <CheckCircle className="h-3 w-3" />
          {counts.loaded} loaded
        </span>
      )}
      {counts['disabled-by-user'] > 0 && (
        <span className="flex items-center gap-1 text-zinc-400">
          <Ban className="h-3 w-3" />
          {counts['disabled-by-user']} disabled
        </span>
      )}
      {hasIssues && (
        <span className="flex items-center gap-1 text-red-400">
          <AlertCircle className="h-3 w-3" />
          {counts.invalid + counts.incompatible + counts['runtime-error'] +
            counts['settings-error']}{' '}
          issue{(counts.invalid + counts.incompatible + counts['runtime-error'] + counts['settings-error']) !== 1 ? 's' : ''}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module-level constants
// ---------------------------------------------------------------------------

/** Stable frozen reference for empty diagnostics — required by useSyncExternalStore. */
const EMPTY_DIAGNOSTIC_SNAPSHOT: readonly Diagnostic[] = Object.freeze([]);
const EMPTY_PACKAGE_STATE_INVENTORY: readonly PackageStateInventoryEntry[] = Object.freeze([]);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ExtensionManager() {
  const { extensionRuntime, extensionStateRepository, triggerExtensionRefresh, diagnosticCollection, settingsNotificationRegistry } = useVideoEditorRuntime();
  const packageStateInventory = extensionRuntime?.packageStateInventory ?? EMPTY_PACKAGE_STATE_INVENTORY;

  // Subscribe to live diagnostic updates from the provider-scoped DiagnosticCollection.
  const allDiagnostics = useSyncExternalStore(
    useCallback(
      (listener: () => void) => {
        if (!diagnosticCollection) return () => {};
        const handle = diagnosticCollection.subscribe(listener);
        return () => handle.dispose();
      },
      [diagnosticCollection],
    ),
    useCallback(
      () => diagnosticCollection?.getSnapshot() ?? EMPTY_DIAGNOSTIC_SNAPSHOT,
      [diagnosticCollection],
    ),
    () => EMPTY_DIAGNOSTIC_SNAPSHOT,
  );

  // Derive contribution summaries per package from the runtime.
  // Prefer the precomputed PackageContributionSummary from normalizeExtensionRuntime,
  // falling back to the live deriveContributionSummary for backward compatibility.
  const contributionSummaries = useMemo(() => {
    if (!extensionRuntime) return new Map<string, ContributionSummary | null>();
    const map = new Map<string, ContributionSummary | null>();
    for (const entry of packageStateInventory) {
      const precomputed = entry.contributionSummary;
      if (precomputed) {
        // Convert PackageContributionSummary → ContributionSummary (subset used by UI)
        map.set(entry.extensionId, {
          declared: precomputed.declared,
          active: precomputed.active >= 0 ? precomputed.active : 0,
          inactive: precomputed.inactive >= 0 ? precomputed.inactive : 0,
          kinds: precomputed.kinds,
        });
      } else {
        // Fallback: derive from active runtime descriptors
        map.set(
          entry.extensionId,
          deriveContributionSummary(entry.extensionId, extensionRuntime),
        );
      }
    }
    return map;
  }, [extensionRuntime, packageStateInventory]);

  // Manifest lookup: extensionId → ExtensionManifest
  const manifestLookup = useMemo(() => {
    const map = new Map<string, ExtensionManifest>();
    if (extensionRuntime) {
      for (const ext of extensionRuntime.extensions) {
        map.set(ext.manifest.id as string, ext.manifest as ExtensionManifest);
      }
    }
    return map;
  }, [extensionRuntime]);

  // Derive per-package diagnostic summaries from the live diagnostic snapshot
  const packageDiagnostics = useMemo(() => {
    const map = new Map<string, PackageDiagnosticSummary>();
    for (const entry of packageStateInventory) {
      const extDiags = allDiagnostics.filter(
        (d) => (d.extensionId ?? '') === entry.extensionId,
      );
      map.set(entry.extensionId, {
        errorCount: extDiags.filter((d) => d.severity === 'error').length,
        warningCount: extDiags.filter((d) => d.severity === 'warning').length,
        infoCount: extDiags.filter((d) => d.severity === 'info').length,
        diagnostics: extDiags,
      });
    }
    return map;
  }, [allDiagnostics, packageStateInventory]);

  if (packageStateInventory.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <ExtensionTrustWarningBanner />
        <div
          className="flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground"
          role="status"
          aria-label="No packages in inventory"
        >
          <Zap className="h-8 w-8 opacity-40" />
          <span className="text-sm">No packages in inventory.</span>
          <span className="text-xs text-muted-foreground/60">
            Extensions supplied by the host will appear here.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ExtensionTrustWarningBanner />
      <ManagerSummaryBar entries={packageStateInventory} />
      <div className="flex flex-col gap-2">
        {packageStateInventory.map((entry) => (
          <PackageCard
            key={entry.extensionId}
            entry={entry}
            contributionSummary={
              contributionSummaries.get(entry.extensionId) ?? null
            }
            repository={extensionStateRepository ?? null}
            onToggleRequest={triggerExtensionRefresh ?? (() => {})}
            manifest={manifestLookup.get(entry.extensionId) ?? null}
            diagnosticSummary={packageDiagnostics.get(entry.extensionId)}
            settingsNotificationRegistry={settingsNotificationRegistry ?? null}
          />
        ))}
      </div>
    </div>
  );
}
