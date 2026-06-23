/**
 * ExtensionSettingsPanel — SchemaForm-backed extension settings UI (M4).
 *
 * Renders an editable settings form for a single extension, driven by the
 * extension manifest's `settingsSchema`.  Uses {@link adaptManifestSettingsSchema}
 * to produce a SchemaForm-compatible schema, {@link createExtensionSettingsService}
 * for persistence, and {@link SchemaForm} for rendering, validation, and focus
 * management.
 *
 * Behaviours:
 *  - Load persisted values on mount and after save.
 *  - Save: validate all fields via SchemaForm.validateAndFocus(); on success,
 *    write each changed value through the settings service (Ajv-backed atomic
 *    validation is enforced by the service, not this component).
 *  - Reset: clear all persisted overrides and revert to manifest defaults.
 *  - Cancel: revert the form state to the last-saved values without writing.
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
  type StandardSchema,
} from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import {
  adaptManifestSettingsSchema,
} from '@/tools/video-editor/runtime/extensionSettings';
import {
  createExtensionSettingsService,
  type ExtensionSettingsService,
} from '@reigh/editor-sdk';
import type { ExtensionManifest, ExtensionDiagnostic } from '@reigh/editor-sdk';
import { cn } from '@/shared/components/ui/contracts/cn.ts';

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
// Component
// ---------------------------------------------------------------------------

export function ExtensionSettingsPanel({
  extensionId,
  manifest,
  className,
  onDiagnostics,
}: ExtensionSettingsPanelProps) {
  // ---- Adapt the manifest settings schema to StandardSchema ---------------
  const adapted = useMemo(
    () => adaptManifestSettingsSchema(manifest),
    [manifest],
  );

  // ---- Settings service (lazily created, idempotent per mount) -------------
  const serviceRef = useRef<ExtensionSettingsService | null>(null);
  if (!serviceRef.current) {
    const result = createExtensionSettingsService(extensionId, manifest);
    serviceRef.current = result.service;
  }
  const settings = serviceRef.current;

  // ---- Load persisted values from the settings service --------------------
  // Derive keys from the adapted schema properties so that after a reset
  // (which calls settings.delete() on every key, excluding them from
  // settings.keys()), we still enumerate defaults via settings.get().
  function loadSavedValues(): Record<string, unknown> {
    const merged: Record<string, unknown> = {};
    if (adapted.schema) {
      for (const key of Object.keys(adapted.schema.properties)) {
        merged[key] = settings.get(key);
      }
    }
    return merged;
  }

  const [savedValues, setSavedValues] = useState<Record<string, unknown>>(
    loadSavedValues,
  );
  const [editValues, setEditValues] = useState<Record<string, unknown>>(
    () => ({ ...savedValues }),
  );

  // Re-load when the manifest or extensionId changes.
  useEffect(() => {
    const fresh = loadSavedValues();
    setSavedValues(fresh);
    setEditValues({ ...fresh });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extensionId, manifest]);

  // Emit adapter diagnostics on mount / manifest change.
  useEffect(() => {
    onDiagnostics?.(adapted.diagnostics as ExtensionDiagnostic[]);
  }, [adapted.diagnostics, onDiagnostics]);

  // ---- SchemaForm ref for validateAndFocus --------------------------------
  const formRef = useRef<SchemaFormHandle>(null);

  // ---- Actions ------------------------------------------------------------

  /** Handle a single field change (optimistic — not yet persisted). */
  const handleChange = useCallback((name: string, value: unknown) => {
    setEditValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  /** Derive the set of known setting keys from the adapted schema. */
  const settingKeys = useMemo(
    () => (adapted.schema ? Object.keys(adapted.schema.properties) : []),
    [adapted.schema],
  );

  /** Save: validate all fields → persist changed values. */
  const handleSave = useCallback(() => {
    const valid = formRef.current?.validateAndFocus() ?? true;
    if (!valid) return;

    // Collect only changed keys (iterate over schema-defined keys)
    for (const key of settingKeys) {
      const current = editValues[key];
      const saved = savedValues[key];
      if (current !== saved) {
        settings.set(key, current);
      }
    }

    // Reload saved state
    const fresh = loadSavedValues();
    setSavedValues(fresh);
    setEditValues({ ...fresh });
  }, [editValues, savedValues, settings, settingKeys]);

  /** Reset: clear all overrides and revert to defaults. */
  const handleReset = useCallback(() => {
    for (const key of settingKeys) {
      settings.delete(key);
    }
    const fresh = loadSavedValues();
    setSavedValues(fresh);
    setEditValues({ ...fresh });
  }, [settings, settingKeys]);

  /** Cancel: revert edit state to last-saved values. */
  const handleCancel = useCallback(() => {
    setEditValues({ ...savedValues });
  }, [savedValues]);

  // ---- Render -------------------------------------------------------------

  // No valid settings schema → nothing to render.
  if (!adapted.schema) {
    return (
      <div
        className={cn('extension-settings-panel extension-settings-panel--empty', className)}
        role="status"
        data-testid="extension-settings-empty"
      >
        <p className="text-sm text-muted-foreground">
          No editable settings schema for this extension.
        </p>
      </div>
    );
  }

  const hasChanges =
    JSON.stringify(editValues) !== JSON.stringify(savedValues);

  return (
    <div
      className={cn('extension-settings-panel', className)}
      data-testid="extension-settings-panel"
    >
      <SchemaForm
        ref={formRef}
        schema={adapted.schema as StandardSchema}
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
          disabled={!hasChanges}
          className="extension-settings-panel__save"
          data-testid="extension-settings-save"
          aria-label="Save settings"
        >
          Save
        </button>
        <button
          type="button"
          onClick={handleCancel}
          disabled={!hasChanges}
          className="extension-settings-panel__cancel"
          data-testid="extension-settings-cancel"
          aria-label="Cancel changes"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="extension-settings-panel__reset"
          data-testid="extension-settings-reset"
          aria-label="Reset to defaults"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
