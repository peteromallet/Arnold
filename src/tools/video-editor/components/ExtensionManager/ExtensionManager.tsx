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
import { adaptManifestSettingsSchema } from '@/tools/video-editor/runtime/extensionSettings';

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
  | 'error'
  | 'raw-json';

// ---------------------------------------------------------------------------
// Package settings section (host repository path)
// ---------------------------------------------------------------------------

function PackageSettingsSection({
  extensionId,
  repository,
  onRefresh,
  manifest,
}: {
  extensionId: string;
  repository: ExtensionStateRepository | null;
  onRefresh: () => void;
  manifest?: ExtensionManifest | null;
}) {
  const [sectionState, setSectionState] = useState<SettingsSectionState>('collapsed');
  const [savedSnapshot, setSavedSnapshot] = useState<ExtensionSettingsSnapshot | null>(null);
  const [editValues, setEditValues] = useState<Record<string, unknown>>({});
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [rawJsonText, setRawJsonText] = useState<string>('');
  const [rawJsonError, setRawJsonError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Determine whether the manifest schema is supported by the key-value editor.
  const schemaAdaptation = useMemo(() => {
    if (!manifest || !manifest.settingsSchema) return null;
    return adaptManifestSettingsSchema(manifest);
  }, [manifest]);

  // Supported schema: key-value editor can render typed fields.
  const hasSupportedSchema = schemaAdaptation?.schema !== null && schemaAdaptation?.schema !== undefined;
  // Unsupported schema: manifest has settingsSchema but it can't be rendered as key-value.
  const hasUnsupportedSchema = schemaAdaptation !== null && schemaAdaptation.schema === null;

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Load settings from the repository when expanding.
  const handleExpand = useCallback(async () => {
    if (sectionState === 'loading' || sectionState === 'saving') return;
    if (sectionState !== 'collapsed') {
      setSectionState('collapsed');
      setRawJsonError(null);
      return;
    }

    // Route unsupported schemas to raw JSON mode.
    if (hasUnsupportedSchema) {
      setSectionState('loading');
      setSettingsError(null);
      setRawJsonError(null);

      try {
        if (repository) {
          const snapshot = await repository.getSettingsSnapshot(extensionId);
          if (mountedRef.current) {
            setSavedSnapshot(snapshot);
            const jsonText = snapshot
              ? JSON.stringify(snapshot.values, null, 2)
              : '{}';
            setRawJsonText(jsonText);
            setSectionState('raw-json');
          }
        } else {
          if (mountedRef.current) {
            setSavedSnapshot(null);
            setRawJsonText('{}');
            setSectionState('raw-json');
          }
        }
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
    setRawJsonError(null);

    try {
      if (repository) {
        const snapshot = await repository.getSettingsSnapshot(extensionId);
        if (mountedRef.current) {
          setSavedSnapshot(snapshot);
          setEditValues(snapshot ? { ...snapshot.values } : {});
          setSectionState(snapshot ? 'idle' : 'idle');
        }
      } else {
        if (mountedRef.current) {
          setSavedSnapshot(null);
          setEditValues({});
          setSectionState('idle');
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to load settings');
        setSectionState('error');
      }
    }
  }, [sectionState, extensionId, repository]);

  // Enter editing mode
  const handleStartEdit = useCallback(() => {
    setSectionState('editing');
    setSettingsError(null);
  }, []);

  // Update a single field value (optimistic, not persisted)
  const handleFieldChange = useCallback((key: string, value: unknown) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Save settings through the repository
  const handleSave = useCallback(async () => {
    if (!repository) return;
    setSectionState('saving');
    setSettingsError(null);

    const now = new Date().toISOString();
    const snapshot: ExtensionSettingsSnapshot = {
      extensionId,
      schemaVersion: savedSnapshot?.schemaVersion ?? 1,
      values: { ...editValues },
      lastWrittenAt: now,
    };

    try {
      await repository.putSettingsSnapshot(snapshot);
      if (mountedRef.current) {
        setSavedSnapshot(snapshot);
        setSectionState('idle');
        onRefresh();
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to save settings');
        setSectionState('error');
      }
    }
  }, [extensionId, editValues, onRefresh, repository, savedSnapshot]);

  // Cancel: revert to last saved values
  const handleCancel = useCallback(() => {
    setEditValues(savedSnapshot ? { ...savedSnapshot.values } : {});
    setSectionState('idle');
    setSettingsError(null);
  }, [savedSnapshot]);

  // Reset: delete settings and revert to empty
  const handleReset = useCallback(async () => {
    if (!repository) return;
    setSectionState('saving');
    setSettingsError(null);

    try {
      await repository.deleteSettingsSnapshot(extensionId);
      if (mountedRef.current) {
        setSavedSnapshot(null);
        setEditValues({});
        setSectionState('idle');
        onRefresh();
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to reset settings');
        setSectionState('error');
      }
    }
  }, [extensionId, onRefresh, repository]);

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

  // ---- Raw JSON mode handlers --------------------------------------------

  /** Save raw JSON: validate syntax, then persist. */
  const handleRawJsonSave = useCallback(async () => {
    if (!repository) return;

    // Validate JSON syntax
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawJsonText);
    } catch (err) {
      setRawJsonError(
        err instanceof SyntaxError
          ? `Invalid JSON: ${err.message}`
          : 'Invalid JSON: unable to parse',
      );
      return;
    }

    // Must be an object (settings are key-value)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      setRawJsonError('Settings must be a JSON object (e.g. {"key": "value"}), not an array or primitive.');
      return;
    }

    setSectionState('saving');
    setRawJsonError(null);
    setSettingsError(null);

    const now = new Date().toISOString();
    const snapshot: ExtensionSettingsSnapshot = {
      extensionId,
      schemaVersion: savedSnapshot?.schemaVersion ?? manifest?.settingsSchema?.version ?? 1,
      values: parsed as Record<string, unknown>,
      lastWrittenAt: now,
    };

    try {
      await repository.putSettingsSnapshot(snapshot);
      if (mountedRef.current) {
        setSavedSnapshot(snapshot);
        setSectionState('raw-json');
        onRefresh();
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to save settings');
        setSectionState('error');
      }
    }
  }, [extensionId, manifest, onRefresh, rawJsonText, repository, savedSnapshot]);

  /** Cancel raw JSON editing: revert to last saved. */
  const handleRawJsonCancel = useCallback(() => {
    const jsonText = savedSnapshot
      ? JSON.stringify(savedSnapshot.values, null, 2)
      : '{}';
    setRawJsonText(jsonText);
    setRawJsonError(null);
    // Stay in raw-json mode; user can collapse if desired.
  }, [savedSnapshot]);

  /** Reset raw JSON: delete snapshot and revert to empty object. */
  const handleRawJsonReset = useCallback(async () => {
    if (!repository) return;
    setSectionState('saving');
    setRawJsonError(null);
    setSettingsError(null);

    try {
      await repository.deleteSettingsSnapshot(extensionId);
      if (mountedRef.current) {
        setSavedSnapshot(null);
        setRawJsonText('{}');
        setSectionState('raw-json');
        onRefresh();
      }
    } catch (err) {
      if (mountedRef.current) {
        setSettingsError(err instanceof Error ? err.message : 'Failed to reset settings');
        setSectionState('error');
      }
    }
  }, [extensionId, onRefresh, repository]);

  /** Retry after raw JSON error. */
  const handleRawJsonRetry = useCallback(() => {
    setSettingsError(null);
    setSectionState('collapsed');
    setTimeout(() => {
      if (mountedRef.current) {
        setSectionState('loading');
        handleExpand();
      }
    }, 0);
  }, [handleExpand]);

  const hasSnapshot = savedSnapshot !== null;
  const hasValues = Object.keys(editValues).length > 0;
  const isDirty = hasSnapshot
    ? JSON.stringify(editValues) !== JSON.stringify(savedSnapshot.values)
    : hasValues;

  const settingsKeys = Object.keys(editValues).sort();

  // Raw JSON dirty check
  const rawJsonDirty = (() => {
    if (savedSnapshot) {
      try {
        const parsed = JSON.parse(rawJsonText);
        return JSON.stringify(parsed) !== JSON.stringify(savedSnapshot.values);
      } catch {
        return true; // Invalid JSON is always "dirty"
      }
    }
    try {
      const parsed = JSON.parse(rawJsonText);
      return Object.keys(parsed as Record<string, unknown>).length > 0;
    } catch {
      return rawJsonText.trim() !== '' && rawJsonText.trim() !== '{}';
    }
  })();

  // Schema diagnostic message for unsupported schemas
  const schemaDiagnostics = schemaAdaptation?.diagnostics
    ?.map((d) => d.message)
    .join('; ') ?? null;

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
            <button
              type="button"
              onClick={handleStartEdit}
              className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Edit extension settings"
              data-video-editor-extension-settings-edit={extensionId}
            >
              Edit
            </button>
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

      {/* Editing: inline key-value editor */}
      {sectionState === 'editing' && (
        <div>
          <div className="flex items-center gap-1 mb-1.5 text-[11px] text-muted-foreground">
            <Settings className="h-3 w-3" />
            <span>Editing settings</span>
          </div>
          {settingsKeys.length > 0 ? (
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
              disabled={!isDirty}
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

      {/* Error (key-value or raw JSON) */}
      {sectionState === 'error' && (settingsError || rawJsonError) && (
        <div
          className="rounded bg-red-500/10 border border-red-500/30 px-2 py-1 text-[11px] text-red-400"
          role="alert"
          data-video-editor-extension-settings-error={extensionId}
        >
          <div className="flex items-center justify-between gap-2">
            <span>Settings error: {settingsError || rawJsonError}</span>
            <button
              type="button"
              onClick={hasUnsupportedSchema ? handleRawJsonRetry : handleSettingsRetry}
              className="shrink-0 text-[10px] underline hover:text-red-300 transition-colors"
              aria-label="Retry extension settings"
              data-video-editor-extension-settings-retry={extensionId}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Raw JSON mode — unsupported schemas */}
      {sectionState === 'raw-json' && (
        <div data-video-editor-extension-settings-raw-json={extensionId}>
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
            <span className="text-[10px] text-yellow-400/80 font-medium">Raw JSON</span>
          </div>
          {schemaDiagnostics && (
            <div className="mb-1.5 rounded bg-yellow-500/10 border border-yellow-500/30 px-2 py-1 text-[10px] text-yellow-400/80">
              {schemaDiagnostics}
            </div>
          )}
          <textarea
            value={rawJsonText}
            onChange={(e) => {
              setRawJsonText(e.target.value);
              setRawJsonError(null);
            }}
            rows={8}
            className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-y"
            aria-label="Raw JSON settings editor"
            spellCheck={false}
            data-video-editor-extension-settings-raw-json-textarea={extensionId}
          />
          {rawJsonError && (
            <div
              className="mt-1 rounded bg-red-500/10 border border-red-500/30 px-2 py-1 text-[11px] text-red-400"
              role="alert"
              data-video-editor-extension-settings-raw-json-error={extensionId}
            >
              {rawJsonError}
            </div>
          )}
          <div className="mt-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleRawJsonSave}
              disabled={!rawJsonDirty}
              className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Save raw JSON extension settings"
              data-video-editor-extension-settings-raw-json-save={extensionId}
            >
              <Save className="h-3 w-3" />
              Save
            </button>
            <button
              type="button"
              onClick={handleRawJsonCancel}
              disabled={!rawJsonDirty}
              className="inline-flex items-center gap-1 rounded bg-muted/50 border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Cancel raw JSON settings changes"
              data-video-editor-extension-settings-raw-json-cancel={extensionId}
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
            <button
              type="button"
              onClick={handleRawJsonReset}
              className="inline-flex items-center gap-1 rounded bg-red-500/10 border border-red-500/30 px-2 py-0.5 text-[10px] font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              aria-label="Reset raw JSON extension settings"
              data-video-editor-extension-settings-raw-json-reset={extensionId}
            >
              <Undo2 className="h-3 w-3" />
              Reset
            </button>
          </div>
          {savedSnapshot && (
            <div className="mt-1 text-[10px] text-muted-foreground/50">
              Last saved: {new Date(savedSnapshot.lastWrittenAt).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Package card
// ---------------------------------------------------------------------------

function PackageCard({
  entry,
  contributionSummary,
  repository,
  onToggleRequest,
  manifest,
  diagnosticSummary,
}: {
  entry: PackageStateInventoryEntry;
  contributionSummary: ContributionSummary | null;
  repository: ExtensionStateRepository | null;
  onToggleRequest: () => void;
  manifest?: ExtensionManifest | null;
  diagnosticSummary?: PackageDiagnosticSummary;
}) {
  const { extensionId, packageState, stateReason, packageMetadata } = entry;
  const label = packageMetadata?.label ?? extensionId;
  const version = packageMetadata?.version;
  const publisher = packageMetadata?.publisher;
  const description = packageMetadata?.description;

  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [diagnosticsExpanded, setDiagnosticsExpanded] = useState(false);

  const isToggleable = packageState === 'loaded' || packageState === 'disabled-by-user';
  const isCurrentlyEnabled = packageState === 'loaded';

  // Derive diagnostic counts from summary or fallback to zero
  const diagErrorCount = diagnosticSummary?.errorCount ?? 0;
  const diagWarningCount = diagnosticSummary?.warningCount ?? 0;
  const diagInfoCount = diagnosticSummary?.infoCount ?? 0;
  const hasDiagnostics = diagErrorCount > 0 || diagWarningCount > 0 || diagInfoCount > 0;

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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ExtensionManager() {
  const { extensionRuntime, extensionStateRepository, triggerExtensionRefresh, diagnosticCollection } = useVideoEditorRuntime();
  const packageStateInventory = extensionRuntime?.packageStateInventory ?? [];

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

  // Derive contribution summaries per package from the runtime
  const contributionSummaries = useMemo(() => {
    if (!extensionRuntime) return new Map<string, ContributionSummary | null>();
    const map = new Map<string, ContributionSummary | null>();
    for (const entry of packageStateInventory) {
      map.set(
        entry.extensionId,
        deriveContributionSummary(entry.extensionId, extensionRuntime),
      );
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
    );
  }

  return (
    <div className="flex flex-col gap-3">
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
          />
        ))}
      </div>
    </div>
  );
}
