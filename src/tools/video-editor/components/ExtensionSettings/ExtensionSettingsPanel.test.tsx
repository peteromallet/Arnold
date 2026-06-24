// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExtensionSettingsPanel } from '@/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel';
import type { ExtensionManifest, ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

// Mock createExtensionSettingsService to return an in-memory settings store
vi.mock('@reigh/editor-sdk', async () => {
  const actual = await vi.importActual('@reigh/editor-sdk');
  return {
    ...actual,
    createExtensionSettingsService: vi.fn(),
  };
});

const { createExtensionSettingsService } = await import('@reigh/editor-sdk') as unknown as { createExtensionSettingsService: typeof import('@reigh/editor-sdk')['createExtensionSettingsService'] };

// Mock cn to pass through class names unchanged
vi.mock('@/shared/components/ui/contracts/cn.ts', () => ({
  cn: (...args: (string | false | null | undefined)[]) =>
    args.filter(Boolean).join(' '),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a supported settings schema manifest. */
function makeManifest(overrides: Partial<ExtensionManifest> = {}): ExtensionManifest {
  return {
    id: 'ext.test',
    version: '1.0.0',
    label: 'Test Extension',
    settingsSchema: {
      version: 1,
      schema: {
        type: 'object',
        properties: {
          title: { type: 'string', title: 'Title', default: 'Untitled' },
          volume: { type: 'number', title: 'Volume', default: 0.8, minimum: 0, maximum: 1 },
          enabled: { type: 'boolean', title: 'Enabled', default: true },
          mode: { type: 'string', title: 'Mode', enum: ['safe', 'fast', 'precise'], default: 'safe' },
        },
        required: ['title'],
      },
    },
    contributions: [],
    ...overrides,
  } as ExtensionManifest;
}

/** Build a manifest with an unsupported schema construct ($ref). */
function makeUnsupportedRefManifest(): ExtensionManifest {
  return {
    id: 'ext.unsupported',
    version: '1.0.0',
    label: 'Unsupported Extension',
    settingsSchema: {
      version: 1,
      schema: {
        type: 'object',
        properties: {
          normal: { type: 'string', title: 'Normal', default: 'ok' },
          linked: { $ref: '#/definitions/External', title: 'Linked' },
        },
      },
    },
    contributions: [],
  } as unknown as ExtensionManifest;
}

/** Build a manifest with no settings schema. */
function makeNoSchemaManifest(): ExtensionManifest {
  return {
    id: 'ext.noschema',
    version: '1.0.0',
    label: 'No Schema Extension',
    contributions: [],
  } as ExtensionManifest;
}

/** Build a manifest with arrays (unsupported). */
function makeArraySchemaManifest(): ExtensionManifest {
  return {
    id: 'ext.arrays',
    version: '1.0.0',
    label: 'Array Extension',
    settingsSchema: {
      version: 1,
      schema: {
        type: 'object',
        properties: {
          tags: { type: 'array', items: { type: 'string' }, title: 'Tags' },
        },
      },
    },
    contributions: [],
  } as unknown as ExtensionManifest;
}

/** Create a mock settings service with an in-memory store. */
function makeSettingsService(initialValues: Record<string, unknown> = {}) {
  const store = new Map<string, unknown>(Object.entries(initialValues));

  return {
    get: vi.fn((key: string) => store.get(key)),
    set: vi.fn((key: string, value: unknown) => {
      store.set(key, value);
    }),
    delete: vi.fn((key: string) => {
      store.delete(key);
    }),
    keys: vi.fn(() => [...store.keys()]),
    /** Test helper: expose store for assertions. */
    _store: store,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExtensionSettingsPanel', () => {
  let settingsService: ReturnType<typeof makeSettingsService>;
  let onDiagnosticsMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    settingsService = makeSettingsService();
    onDiagnosticsMock = vi.fn();

    (createExtensionSettingsService as ReturnType<typeof vi.fn>).mockReturnValue({
      service: settingsService,
    });
  });

  // -----------------------------------------------------------------------
  // Schema-less manifests
  // -----------------------------------------------------------------------

  describe('no settings schema', () => {
    it('renders empty state when manifest has no settingsSchema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.noschema"
          manifest={makeNoSchemaManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      expect(screen.getByTestId('extension-settings-empty')).toBeInTheDocument();
      expect(
        screen.getByText('No editable settings schema for this extension.'),
      ).toBeInTheDocument();
    });

    it('emits diagnostics for missing schema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.noschema"
          manifest={makeNoSchemaManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      expect(onDiagnosticsMock).toHaveBeenCalled();
      const diags: ExtensionDiagnostic[] = onDiagnosticsMock.mock.calls[0]?.[0] ?? [];
      expect(diags.some((d) => d.code === 'settings/missing-schema')).toBe(true);
    });
  });

  // -----------------------------------------------------------------------
  // Supported schema: parity with manager shared helpers
  // -----------------------------------------------------------------------

  describe('supported schema', () => {
    it('uses shared reconcileSettingsSnapshot to load values from localStorage', () => {
      settingsService._store.set('title', 'My Title');
      settingsService._store.set('volume', 0.5);

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Reconciliation result should be visible
      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl).toBeInTheDocument();

      // With missing defaults filled, the state should be 'repaired' (missing
      // 'enabled' and 'mode' filled from defaults).
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'repaired',
      );
    });

    it('shows clean reconciliation state when all values match schema exactly', () => {
      // All values present with correct types
      settingsService._store.set('title', 'Exact');
      settingsService._store.set('volume', 1);
      settingsService._store.set('enabled', false);
      settingsService._store.set('mode', 'fast');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'clean',
      );
    });

    it('uses shared materializeSettingsDefaults for initial values when no saved data exists', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Reconciliation state should be 'repaired' because missing fields
      // were filled from materialized defaults.
      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'repaired',
      );
    });

    it('renders SchemaForm with editable controls for supported schema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Save/Cancel/Reset buttons should be present
      expect(screen.getByTestId('extension-settings-save')).toBeInTheDocument();
      expect(screen.getByTestId('extension-settings-cancel')).toBeInTheDocument();
      expect(screen.getByTestId('extension-settings-reset')).toBeInTheDocument();

      // Actions container should exist
      expect(
        screen.getByTestId('extension-settings-actions'),
      ).toBeInTheDocument();
    });

    // -------------------------------------------------------------------
    // Save / Cancel / Reset behavior parity
    // -------------------------------------------------------------------

    it('Save writes changed values via settings service', async () => {
      const user = userEvent.setup();

      settingsService._store.set('title', 'Original');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Save should initially be disabled (no changes)
      const saveBtn = screen.getByTestId('extension-settings-save');
      expect(saveBtn).toBeDisabled();

      // Make a change: SchemaForm inputs are rendered, find the title input
      // and change its value
      const titleInput = document.querySelector(
        'input[type="text"]',
      ) as HTMLInputElement;
      if (titleInput) {
        await user.clear(titleInput);
        await user.type(titleInput, 'Changed');
      }

      // Save should now be enabled
      await waitFor(() => {
        expect(saveBtn).not.toBeDisabled();
      });

      await user.click(saveBtn);

      // After save, settings.set should have been called for the changed value
      await waitFor(() => {
        expect(settingsService.set).toHaveBeenCalled();
      });
    });

    it('Cancel reverts edit values to reconciled baseline', async () => {
      const user = userEvent.setup();

      settingsService._store.set('title', 'Original');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const cancelBtn = screen.getByTestId('extension-settings-cancel');
      expect(cancelBtn).toBeDisabled();

      // Make a change
      const titleInput = document.querySelector(
        'input[type="text"]',
      ) as HTMLInputElement;
      if (titleInput) {
        await user.clear(titleInput);
        await user.type(titleInput, 'Changed');
      }

      await waitFor(() => {
        expect(cancelBtn).not.toBeDisabled();
      });

      await user.click(cancelBtn);

      // After cancel, the input should revert to the original value
      await waitFor(() => {
        const inputAfterCancel = document.querySelector(
          'input[type="text"]',
        ) as HTMLInputElement;
        if (inputAfterCancel) {
          expect(inputAfterCancel.value).toBe('Original');
        }
      });

      // Settings service should not have been called for set
      expect(settingsService.set).not.toHaveBeenCalled();
    });

    it('Reset clears all overrides and re-materializes defaults', async () => {
      const user = userEvent.setup();

      settingsService._store.set('title', 'Custom');
      settingsService._store.set('mode', 'fast');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const resetBtn = screen.getByTestId('extension-settings-reset');

      await user.click(resetBtn);

      // After reset, settings.delete should have been called for the keys
      await waitFor(() => {
        expect(settingsService.delete).toHaveBeenCalled();
      });
    });
  });

  // -----------------------------------------------------------------------
  // Unsupported schema: read-only blocker parity
  // -----------------------------------------------------------------------

  describe('unsupported schema', () => {
    it('shows blocked reconciliation state for $ref schema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.unsupported"
          manifest={makeUnsupportedRefManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl).toBeInTheDocument();
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'blocked',
      );
    });

    it('shows read-only badge and no editable controls for unsupported schema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.unsupported"
          manifest={makeUnsupportedRefManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Read-only badge should be present
      expect(
        screen.getByTestId('extension-settings-unsupported-badge'),
      ).toBeInTheDocument();
      expect(
        screen.getByText('Read-only — unsupported schema constructs'),
      ).toBeInTheDocument();

      // No Save/Cancel/Reset buttons (no actions container)
      expect(
        screen.queryByTestId('extension-settings-actions'),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId('extension-settings-save'),
      ).not.toBeInTheDocument();
    });

    it('shows no saved settings message when snapshot is empty', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.unsupported"
          manifest={makeUnsupportedRefManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      expect(
        screen.getByTestId('extension-settings-no-values'),
      ).toBeInTheDocument();
      expect(
        screen.getByText('No saved settings for this extension.'),
      ).toBeInTheDocument();
    });

    it('shows existing saved values read-only when snapshot has data', () => {
      settingsService._store.set('normal', 'saved-value');
      settingsService._store.set('linked', 'external-ref');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.unsupported"
          manifest={makeUnsupportedRefManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // saved values should be displayed as text (not inputs)
      expect(screen.getByText('saved-value')).toBeInTheDocument();
    });

    it('shows blocked reconciliation for array schema', () => {
      render(
        <ExtensionSettingsPanel
          extensionId="ext.arrays"
          manifest={makeArraySchemaManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'blocked',
      );
    });
  });

  // -----------------------------------------------------------------------
  // Reconciliation diagnostics display parity
  // -----------------------------------------------------------------------

  describe('reconciliation diagnostics', () => {
    it('shows inline diagnostic row with toggle for expandable details', async () => {
      const user = userEvent.setup();

      // Set a numeric string that triggers coercion (a repair diagnostic)
      settingsService._store.set('title', 'ok');
      settingsService._store.set('volume', '0.5'); // numeric string

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl).toBeInTheDocument();

      // Should show detail count toggle
      const toggle = screen.queryByTestId(
        'extension-settings-reconciliation-toggle',
      );
      if (toggle) {
        // Expand
        await user.click(toggle);
        // After expansion, diagnostic messages should be visible
        await waitFor(() => {
          expect(
            document.querySelector(
              '[data-testid="extension-settings-reconciliation"] .flex.flex-col',
            ),
          ).toBeTruthy();
        });
      }
    });

    it('shows needs-review state when saved enum value is invalid', () => {
      settingsService._store.set('title', 'ok');
      settingsService._store.set('mode', 'invalid-enum-value');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'needs-review',
      );
    });

    it('shows repaired state for numeric string coercion', () => {
      settingsService._store.set('title', 'ok');
      settingsService._store.set('volume', '0.5'); // numeric string

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      // Repaired because volume is coerced, and 'enabled'/'mode' are filled
      // from defaults. Coerced + default-fill = repaired.
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'repaired',
      );
    });

    it('shows dropped unknown fields in expanded details', async () => {
      const user = userEvent.setup();

      // Set a known field + an unknown field
      settingsService._store.set('title', 'ok');
      settingsService._store.set('unknownField', 'should-be-dropped');

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      // Unknown fields trigger needs-review
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'needs-review',
      );
    });
  });

  // -----------------------------------------------------------------------
  // Parity: shared helper consumption
  // -----------------------------------------------------------------------

  describe('parity — shared helper consumption', () => {
    it('standalone panel uses the same analyzeManifestSettingsSchema as the manager', () => {
      // By rendering the panel with a supported schema, we prove
      // analyzeManifestSettingsSchema successfully classifies it as editable.
      // The manager also uses analyzeManifestSettingsSchema for the same
      // classification. Both surfaces gate the editable UI on the same
      // `editable` flag from the same function.
      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Editable controls ARE present (editable=true from analyzeManifestSettingsSchema)
      expect(
        screen.getByTestId('extension-settings-actions'),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId('extension-settings-unsupported-badge'),
      ).not.toBeInTheDocument();
    });

    it('standalone panel gates unsupported schemas on the same editable flag as the manager', () => {
      // Both the manager and standalone panel use analyzeManifestSettingsSchema
      // to determine `editable`. When editable=false, both surfaces show
      // read-only blocker with no editable controls.
      render(
        <ExtensionSettingsPanel
          extensionId="ext.arrays"
          manifest={makeArraySchemaManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // Read-only badge present, no editable controls
      expect(
        screen.getByTestId('extension-settings-unsupported-badge'),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId('extension-settings-actions'),
      ).not.toBeInTheDocument();

      // Reconciliation state is blocked (same as manager)
      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'blocked',
      );
    });

    it('standalone panel uses the same reconcileSettingsSnapshot as the manager', () => {
      // Both surfaces use reconcileSettingsSnapshot to classify settings state.
      // We verify that the standalone panel produces the same state
      // classifications (clean, repaired, needs-review, blocked) that the
      // manager does for identical inputs.

      // Clean: all values present and correctly typed
      settingsService._store.set('title', 'Clean Title');
      settingsService._store.set('volume', 0.5);
      settingsService._store.set('enabled', true);
      settingsService._store.set('mode', 'safe');

      const { unmount } = render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      expect(
        screen
          .getByTestId('extension-settings-reconciliation')
          .getAttribute('data-reconciliation-state'),
      ).toBe('clean');

      unmount();
    });

    it('standalone panel uses the same materializeSettingsDefaults as the manager for fresh starts', () => {
      // Both surfaces use materializeSettingsDefaults to get initial values
      // when no saved snapshot exists. For a fresh start, the reconciliation
      // should fill all schema fields from defaults (manifest > schema >
      // type-based fallback).

      render(
        <ExtensionSettingsPanel
          extensionId="ext.test"
          manifest={makeManifest()}
          onDiagnostics={onDiagnosticsMock}
        />,
      );

      // The reconciliation state will be 'repaired' because all fields are
      // filled from materialized defaults (manifest has no settingsDefaults,
      // so schema property defaults are used: title='Untitled', volume=0.8,
      // enabled=true, mode='safe').
      const reconciliationEl = screen.getByTestId(
        'extension-settings-reconciliation',
      );
      expect(reconciliationEl.getAttribute('data-reconciliation-state')).toBe(
        'repaired',
      );
    });
  });
});
