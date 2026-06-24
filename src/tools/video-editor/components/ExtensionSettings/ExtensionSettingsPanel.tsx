/**
 * ExtensionSettingsPanel — SchemaForm-backed extension settings UI (M4, T7).
 *
 * Renders an editable settings form for a single extension, driven by the
 * extension manifest's `settingsSchema`.  Uses
 * {@link analyzeManifestSettingsSchema} to produce a SchemaForm-compatible
 * schema with supported/unsupported classification,
 * {@link reconcileSettingsSnapshot} for loading and classifying saved values,
 * {@link createExtensionSettingsService} for localStorage-backed persistence,
 * and {@link SchemaForm} for rendering, validation, and focus management.
 *
 * Behaviours:
 *  - Load persisted values on mount and after save via reconciliation.
 *  - Display compact inline reconciliation diagnostics (clean/repaired/
 *    needs-review/blocked) matching the manager surface.
 *  - Unsupported schemas (arrays, nested objects, $ref, combinators,
 *    conditionals) show read-only blocker diagnostics + compact preview
 *    of any existing saved values — no editable controls.
 *  - Save: validate all fields via SchemaForm.validateAndFocus(); on success,
 *    write each changed value through the settings service.
 *  - Reset: clear all persisted overrides and re-materialize defaults.
 *  - Cancel: revert the form state to the reconciled baseline values.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  SchemaForm,
  type SchemaFormHandle,
} from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import {
  analyzeManifestSettingsSchema,
  reconcileSettingsSnapshot,
  type ReconciliationResult,
  type ReconciliationState,
} from '@/tools/video-editor/runtime/extensionSettings';
import {
  createExtensionSettingsService,
  type ExtensionSettingsService,
} from '@reigh/editor-sdk';
import type { ExtensionManifest, ExtensionDiagnostic } from '@reigh/editor-sdk';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Info,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ExtensionSettingsPanelProps {
  /** The extension whose settings are being edited. */
  extensionId: string;
  /** The extension manifest (must include settingsSchema for a form to render). */
  manifest: ExtensionManifest;
  /** Additional CSS class on the root wrapper. */
  className?: string;
  /**
   * Callback invoked with adapter diagnostics (e.g. malformed schema).
   * Consumer should surface these through the active diagnostic collection.
   */
  onDiagnostics?: (diagnostics: ExtensionDiagnostic[]) => void;
}

// ---------------------------------------------------------------------------
// Reconciliation display helpers (shared style with manager)
// ---------------------------------------------------------------------------

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

const DIAG_SEVERITY_ICON: Record<ExtensionDiagnostic['severity'], typeof AlertCircle> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const DIAG_SEVERITY_COLOR: Record<ExtensionDiagnostic['severity'], string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExtensionSettingsPanel({
  extensionId,
  manifest,
  className,
  onDiagnostics,
}: ExtensionSettingsPanelProps) {
  // ---- Analyse the manifest settings schema (T1/T7) -------------------------
  const schemaAnalysis = useMemo(
    () => analyzeManifestSettingsSchema(manifest),
    [manifest],
  );

  const hasUnsupportedSchema =
    schemaAnalysis.schema !== null && !schemaAnalysis.editable;

  const isBlocked =
    schemaAnalysis.schema === null || !schemaAnalysis.editable;

  // ---- Settings service (lazily created, idempotent per mount) -------------
  const serviceRef = useRef<ExtensionSettingsService | null>(null);
  if (!serviceRef.current) {
    const result = createExtensionSettingsService(extensionId, manifest);
    serviceRef.current = result.service;
  }
  const settings = serviceRef.current;

  // ---- Build raw snapshot from localStorage values -------------------------
  const buildRawSnapshot = useCallback((): Record<string, unknown> | null => {
    const keys = settings.keys();
    if (keys.length === 0) return null;
    const snap: Record<string, unknown> = {};
    for (const key of keys) {
      snap[key] = settings.get(key);
    }
    return snap;
  }, [settings]);

  // ---- Reconciliation state ------------------------------------------------
  const [reconciliationResult, setReconciliationResult] =
    useState<ReconciliationResult | null>(null);
  const [reconciliationExpanded, setReconciliationExpanded] = useState(false);

  // Baseline values for dirty detection (reconciled values at load time).
  // For unsupported schemas, this holds the raw snapshot values for read-only
  // display (reconciliation returns empty values when blocked).
  const baseValuesRef = useRef<Record<string, unknown>>({});

  // ---- Edit state ----------------------------------------------------------
  const [editValues, setEditValues] = useState<Record<string, unknown>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  // ---- Load and reconcile on mount / manifest change -----------------------
  useEffect(() => {
    let cancelled = false;

    function loadAndReconcile() {
      const rawSnapshot = buildRawSnapshot();

      if (hasUnsupportedSchema) {
        // Unsupported schema: run reconciliation for blocker diagnostics,
        // but display raw snapshot values read-only (same pattern as manager).
        const result = reconcileSettingsSnapshot({
          manifest,
          snapshot: rawSnapshot,
        });

        if (cancelled) return;

        setReconciliationResult(result);

        const displayValues = rawSnapshot ? { ...rawSnapshot } : {};
        setEditValues(displayValues);
        baseValuesRef.current = displayValues;
      } else {
        // Supported schema: use reconciled values for editing.
        const result = reconcileSettingsSnapshot({
          manifest,
          snapshot: rawSnapshot,
        });

        if (cancelled) return;

        setReconciliationResult(result);
        setEditValues({ ...result.values });
        baseValuesRef.current = { ...result.values };
      }

      setLoadError(null);
    }

    try {
      loadAndReconcile();
    } catch (err) {
      if (!cancelled) {
        setLoadError(
          err instanceof Error ? err.message : 'Failed to load settings',
        );
      }
    }

    return () => {
      cancelled = true;
    };
  }, [extensionId, manifest, buildRawSnapshot, hasUnsupportedSchema]);

  // Emit adapter diagnostics on mount / manifest change.
  useEffect(() => {
    if (schemaAnalysis.diagnostics.length > 0) {
      onDiagnostics?.(schemaAnalysis.diagnostics as ExtensionDiagnostic[]);
    }
  }, [schemaAnalysis.diagnostics, onDiagnostics]);

  // ---- SchemaForm ref for validateAndFocus --------------------------------
  const formRef = useRef<SchemaFormHandle>(null);

  // ---- Actions ------------------------------------------------------------

  /** Handle a single field change (optimistic — not yet persisted). */
  const handleChange = useCallback((name: string, value: unknown) => {
    setEditValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  /** Derive the set of known setting keys from the adapted schema. */
  const settingKeys = useMemo(
    () =>
      schemaAnalysis.schema
        ? Object.keys(schemaAnalysis.schema.properties)
        : [],
    [schemaAnalysis.schema],
  );

  /** Save: validate all fields → persist changed values. */
  const handleSave = useCallback(() => {
    if (isBlocked) return;

    const valid = formRef.current?.validateAndFocus() ?? true;
    if (!valid) return;

    // Write each current edit value to the settings service
    for (const key of settingKeys) {
      settings.set(key, editValues[key]);
    }

    // Also delete any localStorage keys that are no longer in the schema
    const currentKeys = new Set(settings.keys());
    for (const key of currentKeys) {
      if (!settingKeys.includes(key)) {
        settings.delete(key);
      }
    }

    // Re-run reconciliation with the freshly saved snapshot
    const rawSnapshot = buildRawSnapshot();
    const result = reconcileSettingsSnapshot({
      manifest,
      snapshot: rawSnapshot,
    });
    setReconciliationResult(result);
    setEditValues({ ...result.values });
    baseValuesRef.current = { ...result.values };
  }, [
    editValues,
    settings,
    settingKeys,
    manifest,
    buildRawSnapshot,
    isBlocked,
  ]);

  /** Reset: clear all overrides and re-materialize defaults. */
  const handleReset = useCallback(() => {
    if (isBlocked) return;

    // Delete all known localStorage keys
    for (const key of settings.keys()) {
      settings.delete(key);
    }

    // Re-run reconciliation with null snapshot to re-materialize defaults
    const result = reconcileSettingsSnapshot({
      manifest,
      snapshot: null,
    });
    setReconciliationResult(result);
    setEditValues({ ...result.values });
    baseValuesRef.current = { ...result.values };
  }, [settings, manifest, isBlocked]);

  /** Cancel: revert edit state to reconciled baseline values. */
  const handleCancel = useCallback(() => {
    setEditValues({ ...baseValuesRef.current });
  }, []);

  // ---- Derived state -------------------------------------------------------

  const hasValues = Object.keys(editValues).length > 0;
  // Compare against the reconciled baseline so auto-repairs (default-fill,
  // type coercion) don't falsely flag the form as dirty.
  const isDirty =
    JSON.stringify(editValues) !== JSON.stringify(baseValuesRef.current);

  // ---- Reconciliation diagnostic helpers ----------------------------------
  const reconciliationDiagCount =
    reconciliationResult?.diagnostics.filter(
      (d) => !d.code?.startsWith('settings/unsupported-schema'),
    ).length ?? 0;

  // ---- Render -------------------------------------------------------------

  // No valid settings schema → nothing editable.
  if (!schemaAnalysis.schema && schemaAnalysis.diagnostics.length > 0) {
    return (
      <div
        className={cn(
          'extension-settings-panel extension-settings-panel--empty',
          className,
        )}
        role="status"
        data-testid="extension-settings-empty"
      >
        <p className="text-sm text-muted-foreground">
          No editable settings schema for this extension.
        </p>
        {schemaAnalysis.diagnostics.map((d, i) => (
          <p
            key={`diag-${i}`}
            className="text-[11px] text-muted-foreground/70 mt-1"
          >
            {d.message}
          </p>
        ))}
      </div>
    );
  }

  // No settings schema at all
  if (!schemaAnalysis.schema) {
    return (
      <div
        className={cn(
          'extension-settings-panel extension-settings-panel--empty',
          className,
        )}
        role="status"
        data-testid="extension-settings-empty"
      >
        <p className="text-sm text-muted-foreground">
          No editable settings schema for this extension.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn('extension-settings-panel', className)}
      data-testid="extension-settings-panel"
    >
      {/* ---- Reconciliation diagnostic row ---- */}
      {reconciliationResult && (
        <div
          className={`mb-3 rounded border px-2 py-1 text-[10px] ${reconciliationRowStyle(reconciliationResult.state)}`}
          data-testid="extension-settings-reconciliation"
          data-reconciliation-state={reconciliationResult.state}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 font-medium">
              <ReconciliationIcon state={reconciliationResult.state} />
              {reconciliationBadgeLabel(reconciliationResult.state)}
            </span>
            {reconciliationDiagCount > 0 && (
              <button
                type="button"
                onClick={() =>
                  setReconciliationExpanded((prev) => !prev)
                }
                className="inline-flex items-center gap-0.5 text-[10px] underline hover:opacity-80 transition-opacity"
                aria-expanded={reconciliationExpanded}
                aria-label={`${
                  reconciliationExpanded ? 'Hide' : 'Show'
                } reconciliation details`}
                data-testid="extension-settings-reconciliation-toggle"
              >
                {reconciliationDiagCount} detail
                {reconciliationDiagCount !== 1 ? 's' : ''}
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
                .filter(
                  (d) => !d.code?.startsWith('settings/unsupported-schema'),
                )
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

      {/* Load error */}
      {loadError && (
        <div
          className="mb-3 rounded bg-red-500/10 border border-red-500/30 px-2 py-1 text-[11px] text-red-400"
          role="alert"
          data-testid="extension-settings-error"
        >
          {loadError}
        </div>
      )}

      {/* ---- Unsupported schema: read-only blocker ---- */}
      {hasUnsupportedSchema && (
        <>
          <div
            className="mb-2 flex items-center gap-1 text-[11px] text-yellow-400/80 font-medium"
            data-testid="extension-settings-unsupported-badge"
          >
            <AlertTriangle className="h-3 w-3" />
            Read-only — unsupported schema constructs
          </div>
          {hasValues && (
            <div className="mb-2 space-y-1">
              {Object.keys(editValues)
                .sort()
                .map((key) => (
                  <div
                    key={key}
                    className="flex items-center gap-2 py-0.5 text-[11px]"
                  >
                    <span className="font-medium text-muted-foreground min-w-[80px] truncate">
                      {key}
                    </span>
                    <span className="text-foreground/80 truncate">
                      {String(editValues[key] ?? '')}
                    </span>
                  </div>
                ))}
            </div>
          )}
          {!hasValues && (
            <p
              className="text-[11px] text-muted-foreground/60"
              data-testid="extension-settings-no-values"
            >
              No saved settings for this extension.
            </p>
          )}
        </>
      )}

      {/* ---- Supported schema: editable form ---- */}
      {!hasUnsupportedSchema && (
        <>
          <SchemaForm
            ref={formRef}
            schema={schemaAnalysis.schema}
            values={editValues}
            onChange={handleChange}
          />

          <div
            className="extension-settings-panel__actions"
            style={{
              display: 'flex',
              gap: '0.5rem',
              marginTop: '1rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--border)',
            }}
            data-testid="extension-settings-actions"
          >
            <button
              type="button"
              onClick={handleSave}
              disabled={!isDirty || isBlocked}
              className="extension-settings-panel__save"
              data-testid="extension-settings-save"
              aria-label="Save settings"
            >
              Save
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={!isDirty}
              className="extension-settings-panel__cancel"
              data-testid="extension-settings-cancel"
              aria-label="Cancel changes"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={isBlocked}
              className="extension-settings-panel__reset"
              data-testid="extension-settings-reset"
              aria-label="Reset to defaults"
            >
              Reset
            </button>
          </div>
        </>
      )}
    </div>
  );
}
