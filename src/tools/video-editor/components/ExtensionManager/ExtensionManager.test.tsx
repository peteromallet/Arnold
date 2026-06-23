// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExtensionManager } from '@/tools/video-editor/components/ExtensionManager/ExtensionManager';
import { ManagerLoadingState } from '@/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary';
import type { Diagnostic, DiagnosticCollection, DisposeHandle } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

const mockUseVideoEditorRuntime = vi.fn();

vi.mock('@/tools/video-editor/contexts/DataProviderContext', () => ({
  useVideoEditorRuntime: () => mockUseVideoEditorRuntime(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface PackageEntryInput {
  extensionId: string;
  packageState: string;
  stateReason?: string;
  label?: string;
  version?: string;
  publisher?: string;
  description?: string;
}

function makeEntry(input: PackageEntryInput) {
  return {
    extensionId: input.extensionId,
    packageState: input.packageState,
    stateReason: input.stateReason ?? '',
    packageMetadata: input.label
      ? {
          label: input.label,
          version: input.version ?? '1.0.0',
          publisher: input.publisher,
          description: input.description,
        }
      : null,
  };
}

function makeRuntime(entries: PackageEntryInput[], extensions: unknown[] = []) {
  return {
    config: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      overlays: [],
      assetParsers: [],
      outputFormats: [],
      processes: [],
      searchProviders: [],
      metadataFacets: [],
      assetDetailSections: [],
      effects: [],
      transitions: [],
      shaders: [],
      agentTools: [],
    },
    extensions,
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set<string>(),
    settingsDefaults: {},
    assetParsers: [],
    outputFormats: [],
    processes: [],
    searchProviders: [],
    metadataFacets: [],
    assetDetailSections: [],
    effects: [],
    transitions: [],
    shaders: [],
    agentTools: [],
    requirements: [],
    packageStateInventory: entries.map(makeEntry),
  };
}

function makeRepository(overrides?: Partial<Record<string, unknown>>) {
  return {
    initialize: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn().mockResolvedValue(undefined),
    isDisposed: false,
    putPackRecord: vi.fn().mockResolvedValue(undefined),
    updatePackRecord: vi.fn().mockResolvedValue(undefined),
    getPackRecord: vi.fn().mockResolvedValue(null),
    getAllPackRecords: vi.fn().mockResolvedValue([]),
    deletePackRecord: vi.fn().mockResolvedValue(undefined),
    putEnablementState: vi.fn().mockResolvedValue(undefined),
    getEnablementState: vi.fn().mockResolvedValue(null),
    getAllEnablementStates: vi.fn().mockResolvedValue([]),
    deleteEnablementState: vi.fn().mockResolvedValue(undefined),
    putDevOverride: vi.fn().mockResolvedValue(undefined),
    getDevOverride: vi.fn().mockResolvedValue(null),
    getAllDevOverrides: vi.fn().mockResolvedValue([]),
    deleteDevOverride: vi.fn().mockResolvedValue(undefined),
    putSettingsSnapshot: vi.fn().mockResolvedValue(undefined),
    getSettingsSnapshot: vi.fn().mockResolvedValue(null),
    getAllSettingsSnapshots: vi.fn().mockResolvedValue([]),
    deleteSettingsSnapshot: vi.fn().mockResolvedValue(undefined),
    appendLifecycleEvent: vi.fn().mockResolvedValue(undefined),
    queryLifecycleEvents: vi.fn().mockResolvedValue([]),
    getLifecycleEvents: vi.fn().mockResolvedValue([]),
    getLock: vi.fn().mockResolvedValue({ entries: {}, lastUpdatedAt: '' }),
    putLockEntry: vi.fn().mockResolvedValue(undefined),
    deleteLockEntry: vi.fn().mockResolvedValue(undefined),
    getFullExtensionState: vi.fn().mockResolvedValue({
      enablement: {},
      devOverrides: {},
      settings: {},
      packs: {},
    }),
    ...(overrides ?? {}),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExtensionManager — enable/disable controls', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  describe('toggle visibility', () => {
    it('shows an enable/disable toggle for loaded packages when repository is provided', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      expect(toggle).toBeInTheDocument();
      expect(toggle).toHaveTextContent('Enabled');
    });

    it('shows toggle as Disabled for disabled-by-user packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'disabled-by-user', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /enable ext\.a/i });
      expect(toggle).toBeInTheDocument();
      expect(toggle).toHaveTextContent('Disabled');
    });

    it('does NOT show toggle for invalid packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'invalid', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });

    it('does NOT show toggle for incompatible packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'incompatible', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });

    it('does NOT show toggle for duplicate packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'duplicate', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });

    it('does NOT show toggle for runtime-error packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'runtime-error', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });

    it('does NOT show toggle for settings-error packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'settings-error', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });

    it('does NOT show toggle when repository is not provided', () => {
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: null,
        triggerExtensionRefresh: undefined,
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /ext\.a/i })).not.toBeInTheDocument();
    });
  });

  describe('putEnablementState calls', () => {
    it('calls putEnablementState with enabled=false and user-facing reason when disabling a loaded package', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      await waitFor(() => {
        expect(repo.putEnablementState).toHaveBeenCalledTimes(1);
      });

      const callArg = (repo.putEnablementState as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.extensionId).toBe('ext.a');
      expect(callArg.enabled).toBe(false);
      expect(callArg.toggleReason).toBe('User disabled via extension manager');
      expect(callArg.lastToggledAt).toBeTruthy();
    });

    it('calls putEnablementState with enabled=true and user-facing reason when enabling a disabled package', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'disabled-by-user', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /enable ext\.a/i });
      await user.click(toggle);

      await waitFor(() => {
        expect(repo.putEnablementState).toHaveBeenCalledTimes(1);
      });

      const callArg = (repo.putEnablementState as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.extensionId).toBe('ext.a');
      expect(callArg.enabled).toBe(true);
      expect(callArg.toggleReason).toBe('User enabled via extension manager');
    });

    it('triggers refresh after successful enablement state save', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      await waitFor(() => {
        expect(triggerRefresh).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('save-in-flight state', () => {
    it('shows Saving… state and disables the button while save is in flight', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      // Make putEnablementState never resolve so we can observe the saving state
      let resolveSave: () => void = () => {};
      repo.putEnablementState = vi.fn().mockImplementation(
        () => new Promise<void>((resolve) => { resolveSave = resolve; }),
      );

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      // Button should now show saving state and be disabled
      await waitFor(() => {
        expect(screen.getByText('Saving…')).toBeInTheDocument();
      });

      const savingButton = screen.getByRole('button', { name: /saving ext\.a enablement state/i });
      expect(savingButton).toBeDisabled();

      // Resolve the save
      resolveSave();
    });
  });

  describe('failed-save state', () => {
    it('shows error message and allows retry when save fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();

      // First call fails, second succeeds
      let callCount = 0;
      repo.putEnablementState = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve(undefined);
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      const { rerender } = render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      // Error message should appear
      await waitFor(() => {
        expect(screen.getByText(/Failed to save: Network error/)).toBeInTheDocument();
      });

      // The toggle should now act as a retry button (clicking it resets to idle/idle state)
      const retryButton = screen.getByRole('button', { name: /retry saving ext\.a enablement state/i });
      expect(retryButton).toBeInTheDocument();

      // Click retry — this resets error state back to showing the toggle
      await user.click(retryButton);

      // Now the toggle should be the disable button again
      await waitFor(() => {
        expect(screen.queryByText(/Failed to save/)).not.toBeInTheDocument();
      });

      const newToggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(newToggle);

      // Second call should succeed
      await waitFor(() => {
        expect(repo.putEnablementState).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('disabled packages remain visible and inspectable (SD3)', () => {
    it('renders disabled-by-user packages with full metadata, state badge, and reason', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          {
            extensionId: 'ext.disabled',
            packageState: 'disabled-by-user',
            stateReason: 'User disabled via extension manager',
            label: 'Disabled Package',
            version: '2.0.0',
            publisher: 'Test Publisher',
            description: 'A disabled test package',
          },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Package is visible
      expect(screen.getByText('Disabled Package')).toBeInTheDocument();
      expect(screen.getByText('v2.0.0')).toBeInTheDocument();
      expect(screen.getByText('Test Publisher')).toBeInTheDocument();
      expect(screen.getByText('A disabled test package')).toBeInTheDocument();

      // State badge (there are two "Disabled" texts: one in the toggle button, one in the badge)
      const disabledTexts = screen.getAllByText('Disabled');
      expect(disabledTexts.length).toBeGreaterThanOrEqual(2);

      // State reason is displayed
      expect(screen.getByText('User disabled via extension manager')).toBeInTheDocument();

      // Enable toggle is present
      expect(screen.getByRole('button', { name: /enable ext\.disabled/i })).toBeInTheDocument();
    });

    it('renders invalid packages with full metadata and state badge (no toggle)', () => {
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          {
            extensionId: 'ext.invalid',
            packageState: 'invalid',
            stateReason: 'Missing required dependency com.example.foo',
            label: 'Invalid Package',
            version: '1.0.0',
            publisher: 'Bad Publisher',
          },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Package is visible with all metadata
      expect(screen.getByText('Invalid Package')).toBeInTheDocument();
      expect(screen.getByText('v1.0.0')).toBeInTheDocument();
      expect(screen.getByText('Bad Publisher')).toBeInTheDocument();

      // State badge
      expect(screen.getByText('Invalid')).toBeInTheDocument();

      // State reason
      expect(screen.getByText('Missing required dependency com.example.foo')).toBeInTheDocument();

      // No toggle (invalid packages cannot be toggled)
      expect(screen.queryByRole('button', { name: /ext\.invalid/i })).not.toBeInTheDocument();
    });

    it('renders all 7 package states with badges and preserves reason text', () => {
      const repo = makeRepository();
      const entries = [
        { extensionId: 'ext.loaded', packageState: 'loaded', stateReason: 'Loaded successfully', label: 'Loaded Pkg' },
        { extensionId: 'ext.disabled', packageState: 'disabled-by-user', stateReason: 'User disabled via extension manager', label: 'Disabled Pkg' },
        { extensionId: 'ext.invalid', packageState: 'invalid', stateReason: 'Manifest parse error', label: 'Invalid Pkg' },
        { extensionId: 'ext.incompatible', packageState: 'incompatible', stateReason: 'API version mismatch', label: 'Incompat Pkg' },
        { extensionId: 'ext.dup', packageState: 'duplicate', stateReason: 'Installed pack takes precedence', label: 'Dupe Pkg' },
        { extensionId: 'ext.settingserr', packageState: 'settings-error', stateReason: 'Settings schema validation failed', label: 'SettingsErr Pkg' },
        { extensionId: 'ext.rterr', packageState: 'runtime-error', stateReason: 'Integrity hash mismatch', label: 'RuntimeErr Pkg' },
      ];

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime(entries),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // All packages rendered
      expect(screen.getByText('Loaded Pkg')).toBeInTheDocument();
      expect(screen.getByText('Disabled Pkg')).toBeInTheDocument();
      expect(screen.getByText('Invalid Pkg')).toBeInTheDocument();
      expect(screen.getByText('Incompat Pkg')).toBeInTheDocument();
      expect(screen.getByText('Dupe Pkg')).toBeInTheDocument();
      expect(screen.getByText('SettingsErr Pkg')).toBeInTheDocument();
      expect(screen.getByText('RuntimeErr Pkg')).toBeInTheDocument();

      // All state badges present (note: "Disabled" appears in both the toggle button and badge)
      expect(screen.getByText('Loaded')).toBeInTheDocument();
      expect(screen.getAllByText('Disabled').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Invalid')).toBeInTheDocument();
      expect(screen.getByText('Incompatible')).toBeInTheDocument();
      expect(screen.getByText('Duplicate')).toBeInTheDocument();
      expect(screen.getByText('Settings Error')).toBeInTheDocument();
      expect(screen.getByText('Runtime Error')).toBeInTheDocument();

      // All reason texts preserved
      expect(screen.getByText('Loaded successfully')).toBeInTheDocument();
      expect(screen.getByText('User disabled via extension manager')).toBeInTheDocument();
      expect(screen.getByText('Manifest parse error')).toBeInTheDocument();
      expect(screen.getByText('API version mismatch')).toBeInTheDocument();
      expect(screen.getByText('Installed pack takes precedence')).toBeInTheDocument();
      expect(screen.getByText('Settings schema validation failed')).toBeInTheDocument();
      expect(screen.getByText('Integrity hash mismatch')).toBeInTheDocument();

      // Summary bar shows correct counts
      expect(screen.getByText('7 packages')).toBeInTheDocument();
      expect(screen.getByText('1 loaded')).toBeInTheDocument();
      expect(screen.getByText('1 disabled')).toBeInTheDocument();
      expect(screen.getByText('4 issues')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('renders empty state when no packages in inventory', () => {
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([]),
        extensionStateRepository: null,
        triggerExtensionRefresh: undefined,
      });

      render(<ExtensionManager />);

      expect(screen.getByText('No packages in inventory.')).toBeInTheDocument();
    });
  });

  describe('data attributes', () => {
    it('sets data-video-editor-extension-toggle on toggleable packages', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      expect(toggle).toHaveAttribute('data-video-editor-extension-toggle', 'ext.a');
    });

    it('sets data-video-editor-extension-save-error when save fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.putEnablementState = vi.fn().mockRejectedValue(new Error('Boom'));

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: /disable ext\.a/i });
      await user.click(toggle);

      await waitFor(() => {
        const errorEl = document.querySelector('[data-video-editor-extension-save-error="ext.a"]');
        expect(errorEl).toBeInTheDocument();
        expect(errorEl).toHaveTextContent('Failed to save: Boom');
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Persistent trust warning tests (T10)
// ---------------------------------------------------------------------------

describe('ExtensionManager — persistent trust warning', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  function expectTrustWarningVisible() {
    const warning = screen.getByRole('note', { name: 'Extension trust warning' });
    expect(warning).toBeInTheDocument();
    expect(warning).toHaveTextContent('Extensions run as trusted, unsandboxed code.');
    expect(warning).toHaveTextContent('Manifest permissions are declarative and are not enforced at runtime.');
  }

  it('shows the trust warning during loading state', () => {
    render(<ManagerLoadingState />);

    expect(screen.getByText('Loading extensions…')).toBeInTheDocument();
    expectTrustWarningVisible();
  });

  it('shows the trust warning in empty inventory state', () => {
    mockUseVideoEditorRuntime.mockReturnValue({
      extensionRuntime: makeRuntime([]),
      extensionStateRepository: null,
      triggerExtensionRefresh: undefined,
    });

    render(<ExtensionManager />);

    expect(screen.getByText('No packages in inventory.')).toBeInTheDocument();
    expectTrustWarningVisible();
  });

  it('shows the trust warning above populated package inventory', () => {
    mockUseVideoEditorRuntime.mockReturnValue({
      extensionRuntime: makeRuntime([
        { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
      ]),
      extensionStateRepository: makeRepository(),
      triggerExtensionRefresh: vi.fn(),
    });

    render(<ExtensionManager />);

    expect(screen.getByText('Package A')).toBeInTheDocument();
    expectTrustWarningVisible();
  });

  it('keeps the trust warning visible when a package detail section is expanded', async () => {
    const user = userEvent.setup();
    const repo = makeRepository();
    repo.getSettingsSnapshot = vi.fn().mockResolvedValue(null);
    mockUseVideoEditorRuntime.mockReturnValue({
      extensionRuntime: makeRuntime([
        { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
      ]),
      extensionStateRepository: repo,
      triggerExtensionRefresh: vi.fn(),
    });

    render(<ExtensionManager />);

    await user.click(screen.getByRole('button', { name: 'Show extension settings' }));

    await waitFor(() => {
      expect(screen.getByText('No saved settings for this extension.')).toBeInTheDocument();
    });
    expectTrustWarningVisible();
  });
});

// ---------------------------------------------------------------------------
// Settings persistence tests (T7)
// ---------------------------------------------------------------------------

describe('ExtensionManager — settings persistence', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  describe('settings section visibility', () => {
    it('renders a collapsed Settings toggle on every package card', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
          { extensionId: 'ext.b', packageState: 'disabled-by-user', label: 'Package B' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Both packages have settings toggle buttons
      const toggles = screen.getAllByRole('button', { name: 'Show extension settings' });
      expect(toggles).toHaveLength(2);
    });

    it('renders settings section for disabled-by-user packages (SD3 visibility)', () => {
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.disabled',
        schemaVersion: 1,
        values: { theme: 'dark' },
        lastWrittenAt: new Date().toISOString(),
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          {
            extensionId: 'ext.disabled',
            packageState: 'disabled-by-user',
            label: 'Disabled Package',
            stateReason: 'User disabled via extension manager',
          },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Settings toggle should be present on the disabled package
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      expect(toggle).toBeInTheDocument();
    });

    it('renders settings section for invalid packages (SD3 visibility)', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          {
            extensionId: 'ext.invalid',
            packageState: 'invalid',
            label: 'Invalid Package',
            stateReason: 'Missing manifest',
          },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Settings toggle should be present on the invalid package
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      expect(toggle).toBeInTheDocument();
    });
  });

  describe('settings loading', () => {
    it('loads settings from repository when expanded', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'dark', fontSize: '14' },
        lastWrittenAt: '2026-01-15T10:30:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      // Should call getSettingsSnapshot
      await waitFor(() => {
        expect(repo.getSettingsSnapshot).toHaveBeenCalledWith('ext.a');
      });

      // Should show the saved values
      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
        expect(screen.getByText('dark')).toBeInTheDocument();
        expect(screen.getByText('fontSize')).toBeInTheDocument();
        expect(screen.getByText('14')).toBeInTheDocument();
      });
    });

    it('shows no-settings state when no snapshot exists', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue(null);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      // Should show no-settings message
      await waitFor(() => {
        expect(screen.getByText('No saved settings for this extension.')).toBeInTheDocument();
      });
    });

    it('shows loading state while fetching settings', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      let resolveLoad: (value: unknown) => void = () => {};
      repo.getSettingsSnapshot = vi.fn().mockImplementation(
        () => new Promise((resolve) => { resolveLoad = resolve; }),
      );

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      // Should show loading indicator
      await waitFor(() => {
        expect(screen.getByText('Loading settings…')).toBeInTheDocument();
      });

      // Resolve
      resolveLoad({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { key: 'val' },
        lastWrittenAt: new Date().toISOString(),
      });
    });
  });

  describe('settings save', () => {
    it('saves settings through putSettingsSnapshot with correct values', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      // Expand and load settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      // Click Edit
      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      // Change the value
      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      // Save
      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      await waitFor(() => {
        expect(repo.putSettingsSnapshot).toHaveBeenCalledTimes(1);
      });

      const callArg = (repo.putSettingsSnapshot as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.extensionId).toBe('ext.a');
      expect(callArg.values).toEqual({ theme: 'dark' });
      expect(callArg.lastWrittenAt).toBeTruthy();
    });

    it('triggers refresh after successful settings save', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      await waitFor(() => {
        expect(triggerRefresh).toHaveBeenCalledTimes(1);
      });
    });

    it('shows saving state while save is in flight', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      let resolveSave: (value: unknown) => void = () => {};
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });
      repo.putSettingsSnapshot = vi.fn().mockImplementation(
        () => new Promise((resolve) => { resolveSave = resolve; }),
      );

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByText('Saving settings…')).toBeInTheDocument();
      });

      resolveSave(undefined);
    });

    it('shows error state and retry when save fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });
      repo.putSettingsSnapshot = vi.fn().mockRejectedValue(new Error('Storage full'));

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      // Error should appear
      await waitFor(() => {
        expect(screen.getByText(/Settings error: Storage full/)).toBeInTheDocument();
      });

      // Retry button should be present
      const retryBtn = screen.getByRole('button', { name: 'Retry extension settings' });
      expect(retryBtn).toBeInTheDocument();
    });
  });

  describe('settings cancel', () => {
    it('reverts to last saved values on cancel', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light', count: '5' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      // Click Edit
      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      // Change a value
      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      // Cancel
      const cancelBtn = screen.getByRole('button', { name: 'Cancel extension settings changes' });
      await user.click(cancelBtn);

      // Should revert to read-only view with original values
      await waitFor(() => {
        expect(screen.getByText('light')).toBeInTheDocument();
      });
      expect(screen.queryByDisplayValue('dark')).not.toBeInTheDocument();
    });

    it('cancel is disabled when no changes have been made', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const cancelBtn = screen.getByRole('button', { name: 'Cancel extension settings changes' });
      expect(cancelBtn).toBeDisabled();
    });
  });

  describe('settings reset', () => {
    it('deletes settings via deleteSettingsSnapshot and shows no-settings state', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      const triggerRefresh = vi.fn();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: triggerRefresh,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      // Click Edit to enter editing mode
      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      // Click Reset
      const resetBtn = screen.getByRole('button', { name: 'Reset extension settings' });
      await user.click(resetBtn);

      await waitFor(() => {
        expect(repo.deleteSettingsSnapshot).toHaveBeenCalledWith('ext.a');
      });

      await waitFor(() => {
        expect(triggerRefresh).toHaveBeenCalled();
      });
    });

    it('shows error state when reset fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });
      repo.deleteSettingsSnapshot = vi.fn().mockRejectedValue(new Error('Permission denied'));

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const resetBtn = screen.getByRole('button', { name: 'Reset extension settings' });
      await user.click(resetBtn);

      await waitFor(() => {
        expect(screen.getByText(/Settings error: Permission denied/)).toBeInTheDocument();
      });
    });
  });

  describe('settings data attributes', () => {
    it('sets data-video-editor-extension-settings-toggle on the collapsed toggle', () => {
      const repo = makeRepository();
      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = document.querySelector('[data-video-editor-extension-settings-toggle="ext.a"]');
      expect(toggle).toBeInTheDocument();
    });

    it('sets data-video-editor-extension-settings-empty when no snapshot', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue(null);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        const emptyEl = document.querySelector('[data-video-editor-extension-settings-empty="ext.a"]');
        expect(emptyEl).toBeInTheDocument();
      });
    });

    it('sets data-video-editor-extension-settings-error when save fails', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: '2026-01-15T10:00:00Z',
      });
      repo.putSettingsSnapshot = vi.fn().mockRejectedValue(new Error('Boom'));

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await user.click(toggle);

      await waitFor(() => {
        expect(screen.getByText('theme')).toBeInTheDocument();
      });

      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      const field = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(field);
      await user.type(field, 'dark');

      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      await waitFor(() => {
        const errorEl = document.querySelector('[data-video-editor-extension-settings-error="ext.a"]');
        expect(errorEl).toBeInTheDocument();
        expect(errorEl).toHaveTextContent('Settings error: Boom');
      });
    });

    it('shows blocked reconciliation state and no editable controls for unsupported schema (no properties)', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue(null);

      const manifest = {
        id: 'ext.raw',
        version: '1.0.0',
        label: 'Raw Settings Package',
        settingsSchema: {
          version: 1,
          schema: {
            type: 'object',
            required: ['mode'],
          },
        },
        contributions: [],
      };

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime(
          [{ extensionId: 'ext.raw', packageState: 'loaded', label: 'Raw Settings Package' }],
          [{ manifest }],
        ),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      await user.click(screen.getByRole('button', { name: 'Show extension settings' }));

      // No raw JSON editor should exist
      await waitFor(() => {
        expect(screen.queryByRole('textbox', { name: 'Raw JSON settings editor' })).not.toBeInTheDocument();
      });

      // Blocked reconciliation diagnostic should be visible
      const reconciliationEl = document.querySelector('[data-video-editor-extension-settings-reconciliation-state="blocked"]');
      expect(reconciliationEl).toBeInTheDocument();

      // No Save button should be available (no editing mode means no save)
      expect(screen.queryByRole('button', { name: 'Save extension settings' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Save raw JSON extension settings' })).not.toBeInTheDocument();

      // No Edit button for blocked unsupported schema
      expect(screen.queryByRole('button', { name: 'Edit extension settings' })).not.toBeInTheDocument();

      // Settings should indicate no saved settings
      expect(screen.getByText('No saved settings for this extension.')).toBeInTheDocument();
    });

    it('shows existing snapshot values read-only for unsupported schema with saved data', async () => {
      const user = userEvent.setup();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.raw',
        schemaVersion: 1,
        values: { mode: 'safe', theme: 'dark' },
        lastWrittenAt: '2026-01-15T10:30:00Z',
      });

      const manifest = {
        id: 'ext.raw',
        version: '1.0.0',
        label: 'Raw Settings Package',
        settingsSchema: {
          version: 1,
          schema: {
            type: 'object',
            required: ['mode'],
          },
        },
        contributions: [],
      };

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime(
          [{ extensionId: 'ext.raw', packageState: 'loaded', label: 'Raw Settings Package' }],
          [{ manifest }],
        ),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
      });

      render(<ExtensionManager />);

      await user.click(screen.getByRole('button', { name: 'Show extension settings' }));

      // Existing snapshot values should be displayed read-only
      await waitFor(() => {
        expect(screen.getByText('mode')).toBeInTheDocument();
        expect(screen.getByText('safe')).toBeInTheDocument();
        expect(screen.getByText('theme')).toBeInTheDocument();
        expect(screen.getByText('dark')).toBeInTheDocument();
      });

      // No raw JSON editor
      expect(screen.queryByRole('textbox', { name: 'Raw JSON settings editor' })).not.toBeInTheDocument();

      // Blocked reconciliation diagnostic should be visible
      const reconciliationEl = document.querySelector('[data-video-editor-extension-settings-reconciliation-state="blocked"]');
      expect(reconciliationEl).toBeInTheDocument();

      // No Save or Edit buttons
      expect(screen.queryByRole('button', { name: 'Save extension settings' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Edit extension settings' })).not.toBeInTheDocument();

      // Read-only indicator
      expect(screen.getByText('Read-only')).toBeInTheDocument();

      // Last saved time should be visible
      expect(screen.getByText(/Last saved:/)).toBeInTheDocument();

      // Save should not have been called
      expect(repo.putSettingsSnapshot).not.toHaveBeenCalled();
    });
  });
});

// ---------------------------------------------------------------------------
// Diagnostic badge and inline detail tests (T9)
// ---------------------------------------------------------------------------

/** Build a single Diagnostic object for testing. */
function makeDiagnostic(overrides: Partial<Diagnostic> = {}): Diagnostic {
  return {
    id: overrides.id ?? `diag-${Math.random().toString(36).slice(2, 8)}`,
    severity: overrides.severity ?? 'error',
    code: overrides.code ?? 'test/error',
    message: overrides.message ?? 'Test diagnostic message',
    extensionId: overrides.extensionId,
    contributionId: overrides.contributionId,
    sourceRange: overrides.sourceRange,
    relatedRanges: overrides.relatedRanges,
    milestone: overrides.milestone,
    source: overrides.source,
    detail: overrides.detail,
  };
}

/** Build a mock DiagnosticCollection that supports subscribe/getSnapshot. */
function makeDiagnosticCollection(initial: Diagnostic[] = []) {
  let snapshot: readonly Diagnostic[] = initial;
  const listeners = new Set<() => void>();

  return {
    collection: {
      getSnapshot: vi.fn(() => snapshot),
      subscribe: vi.fn((listener: () => void): DisposeHandle => {
        listeners.add(listener);
        return { dispose: () => listeners.delete(listener) };
      }),
    } as unknown as DiagnosticCollection,
    /** Update the snapshot and notify all listeners (simulates live update). */
    setSnapshot(diagnostics: Diagnostic[]) {
      snapshot = diagnostics;
      for (const listener of listeners) {
        listener();
      }
    },
  };
}

// ---------------------------------------------------------------------------
// T10: Settings notification registry helper for manager tests
// ---------------------------------------------------------------------------

function makeNotificationRegistry() {
  const listeners = new Map<string, Set<() => void>>();
  const serviceDisposeHandles = new Map<string, { dispose: () => void }>();
  let disposed = false;

  return {
    subscribeToExtension(extensionId: string, listener: () => void) {
      if (!listeners.has(extensionId)) {
        listeners.set(extensionId, new Set());
      }
      listeners.get(extensionId)!.add(listener);
      return {
        dispose: () => {
          listeners.get(extensionId)?.delete(listener);
        },
      };
    },
    notifySettingsChanged(extensionId: string) {
      if (disposed) return;
      const extListeners = listeners.get(extensionId);
      if (extListeners) {
        for (const l of extListeners) {
          try { l(); } catch { /* ignore */ }
        }
      }
    },
    registerService: vi.fn().mockReturnValue({ dispose: vi.fn() }),
    subscribe: vi.fn().mockReturnValue({ dispose: vi.fn() }),
    get isDisposed() { return disposed; },
    dispose() { disposed = true; listeners.clear(); },
    getRegisteredExtensionIds: vi.fn().mockReturnValue([]),
  };
}

// ---------------------------------------------------------------------------
// T10: Settings notification coherence tests
// ---------------------------------------------------------------------------

describe('ExtensionManager — settings notification coherence (T10)', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  describe('manager subscribes to runtime notifications', () => {
    it('reloads and reconciles settings when runtime notifies via registry', async () => {
      const notifReg = makeNotificationRegistry();
      const repo = makeRepository();
      const savedDate = new Date().toISOString();

      // Initial snapshot
      repo.getSettingsSnapshot = vi.fn()
        .mockResolvedValueOnce({
          extensionId: 'ext.a',
          schemaVersion: 1,
          values: { theme: 'light' },
          lastWrittenAt: savedDate,
        })
        // Second call (after notification) returns updated values
        .mockResolvedValueOnce({
          extensionId: 'ext.a',
          schemaVersion: 1,
          values: { theme: 'dark' },
          lastWrittenAt: new Date().toISOString(),
        });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
        settingsNotificationRegistry: notifReg as any,
      });

      render(<ExtensionManager />);

      // Expand settings section
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await act(async () => {
        fireEvent.click(toggle);
      });

      // Should show initial value
      await waitFor(() => {
        expect(screen.getByText('light')).toBeInTheDocument();
      });

      // Simulate runtime settings change via notification
      await act(async () => {
        notifReg.notifySettingsChanged('ext.a');
      });

      // Should reload and show updated value
      await waitFor(() => {
        expect(screen.getByText('dark')).toBeInTheDocument();
      });

      // Repository should have been called twice (initial load + reload)
      expect(repo.getSettingsSnapshot).toHaveBeenCalledTimes(2);
    });

    it('does NOT reload when settings section is collapsed', async () => {
      const notifReg = makeNotificationRegistry();
      const repo = makeRepository();
      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: new Date().toISOString(),
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
        settingsNotificationRegistry: notifReg as any,
      });

      render(<ExtensionManager />);

      // Don't expand — notify while collapsed
      await act(async () => {
        notifReg.notifySettingsChanged('ext.a');
      });

      // getSettingsSnapshot should NOT have been called since section is collapsed
      // (the subscription only activates when expanded)
      expect(repo.getSettingsSnapshot).not.toHaveBeenCalled();
    });

    it('does not reload when notification registry is absent', async () => {
      const repo = makeRepository();
      let loadCount = 0;
      repo.getSettingsSnapshot = vi.fn().mockImplementation(async () => {
        loadCount++;
        return {
          extensionId: 'ext.a',
          schemaVersion: 1,
          values: { key: `load-${loadCount}` },
          lastWrittenAt: new Date().toISOString(),
        };
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
        // No settingsNotificationRegistry provided
      });

      render(<ExtensionManager />);

      // Expand settings section
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await act(async () => {
        fireEvent.click(toggle);
      });

      await waitFor(() => {
        expect(screen.getByText('load-1')).toBeInTheDocument();
      });

      // Should have loaded once (on expand) and no subscription to trigger reload
      expect(repo.getSettingsSnapshot).toHaveBeenCalledTimes(1);
    });
  });

  describe('manager save notifies through registry', () => {
    it('calls notifySettingsChanged after successful save', async () => {
      const user = userEvent.setup();
      const notifReg = makeNotificationRegistry();
      const notifySpy = vi.spyOn(notifReg, 'notifySettingsChanged');
      const repo = makeRepository();

      repo.getSettingsSnapshot = vi.fn().mockResolvedValue({
        extensionId: 'ext.a',
        schemaVersion: 1,
        values: { theme: 'light' },
        lastWrittenAt: new Date().toISOString(),
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
        settingsNotificationRegistry: notifReg as any,
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await act(async () => {
        fireEvent.click(toggle);
      });

      await waitFor(() => {
        expect(screen.getByText('light')).toBeInTheDocument();
      });

      // Click Edit
      const editBtn = screen.getByRole('button', { name: 'Edit extension settings' });
      await user.click(editBtn);

      // Change a value
      const input = screen.getByRole('textbox', { name: 'Settings value for theme' });
      await user.clear(input);
      await user.type(input, 'dark');

      // Click Save
      const saveBtn = screen.getByRole('button', { name: 'Save extension settings' });
      await user.click(saveBtn);

      await waitFor(() => {
        expect(repo.putSettingsSnapshot).toHaveBeenCalledTimes(1);
      });

      // Should have notified through the registry
      await waitFor(() => {
        expect(notifySpy).toHaveBeenCalledWith('ext.a');
      });

      notifySpy.mockRestore();
    });

    it('does NOT notify when repository is absent (save is no-op)', async () => {
      const notifReg = makeNotificationRegistry();
      const notifySpy = vi.spyOn(notifReg, 'notifySettingsChanged');

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: null,
        triggerExtensionRefresh: vi.fn(),
        settingsNotificationRegistry: notifReg as any,
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await act(async () => {
        fireEvent.click(toggle);
      });

      // No Edit button should appear since there's no repository
      // (or it would be there but clicking Save wouldn't do anything)
      // The key point: notifySettingsChanged should NOT be called
      expect(notifySpy).not.toHaveBeenCalled();

      notifySpy.mockRestore();
    });
  });

  describe('notification unsubscription', () => {
    it('unsubscribes from registry when section collapses', async () => {
      const notifReg = makeNotificationRegistry();
      const repo = makeRepository();
      let loadCount = 0;
      repo.getSettingsSnapshot = vi.fn().mockImplementation(async () => {
        loadCount++;
        return {
          extensionId: 'ext.a',
          schemaVersion: 1,
          values: { key: `load-${loadCount}` },
          lastWrittenAt: new Date().toISOString(),
        };
      });

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: repo,
        triggerExtensionRefresh: vi.fn(),
        settingsNotificationRegistry: notifReg as any,
      });

      render(<ExtensionManager />);

      // Expand settings
      const toggle = screen.getByRole('button', { name: 'Show extension settings' });
      await act(async () => {
        fireEvent.click(toggle);
      });

      await waitFor(() => {
        expect(screen.getByText('load-1')).toBeInTheDocument();
      });

      // First notification — should reload
      await act(async () => {
        notifReg.notifySettingsChanged('ext.a');
      });

      await waitFor(() => {
        expect(screen.getByText('load-2')).toBeInTheDocument();
      });

      // Collapse settings section
      const hideBtn = screen.getByRole('button', { name: 'Hide extension settings' });
      await act(async () => {
        fireEvent.click(hideBtn);
      });

      // Notify again — should NOT reload (subscription disposed)
      await act(async () => {
        notifReg.notifySettingsChanged('ext.a');
      });

      // Wait a tick and verify load count hasn't increased
      await new Promise((r) => setTimeout(r, 50));
      expect(loadCount).toBe(2); // Only initial load + first notification
    });
  });
});

describe('ExtensionManager — diagnostic badges and inline details', () => {
  beforeEach(() => {
    mockUseVideoEditorRuntime.mockReset();
  });

  describe('diagnostic badge counts', () => {
    it('shows error badge with count when a package has error diagnostics', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Something broke' }),
        makeDiagnostic({ extensionId: 'ext.a', severity: 'error', code: 'E002', message: 'Another error' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      // Error badge with count 2
      const errorBadge = screen.getByText('2');
      expect(errorBadge).toBeInTheDocument();
      const errorContainer = errorBadge.closest('[data-video-editor-extension-diag-count="error"]');
      expect(errorContainer).toBeInTheDocument();
    });

    it('shows warning badge with count when a package has warning diagnostics', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.a', severity: 'warning', code: 'W001', message: 'Deprecated API' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const warningBadge = document.querySelector('[data-video-editor-extension-diag-count="warning"]');
      expect(warningBadge).toBeInTheDocument();
      expect(warningBadge).toHaveTextContent('1');
    });

    it('shows info badge with count when a package has info diagnostics', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.a', severity: 'info', code: 'I001', message: 'FYI' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const infoBadge = document.querySelector('[data-video-editor-extension-diag-count="info"]');
      expect(infoBadge).toBeInTheDocument();
      expect(infoBadge).toHaveTextContent('1');
    });

    it('shows all three severity badges when a package has mixed diagnostics', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'error' }),
        makeDiagnostic({ extensionId: 'ext.a', severity: 'warning', code: 'W001', message: 'warn' }),
        makeDiagnostic({ extensionId: 'ext.a', severity: 'info', code: 'I001', message: 'info' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      expect(document.querySelector('[data-video-editor-extension-diag-count="error"]')).toBeInTheDocument();
      expect(document.querySelector('[data-video-editor-extension-diag-count="warning"]')).toBeInTheDocument();
      expect(document.querySelector('[data-video-editor-extension-diag-count="info"]')).toBeInTheDocument();
    });

    it('does NOT show diagnostic badges when no diagnostics exist', () => {
      const { collection } = makeDiagnosticCollection([]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      expect(document.querySelector('[data-video-editor-extension-diagnostic-badges]')).not.toBeInTheDocument();
    });

    it('groups diagnostics by extensionId — only shows badges for the correct package', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'error A' }),
        makeDiagnostic({ extensionId: 'ext.b', severity: 'warning', code: 'W001', message: 'warn B' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
          { extensionId: 'ext.b', packageState: 'loaded', label: 'Package B' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      // ext.a should have error badge only
      const aBadges = document.querySelector('[data-video-editor-extension-package-id="ext.a"]')!
        .querySelector('[data-video-editor-extension-diagnostic-badges="ext.a"]')!;
      expect(aBadges).toBeInTheDocument();
      expect(aBadges.querySelector('[data-video-editor-extension-diag-count="error"]')).toBeInTheDocument();
      expect(aBadges.querySelector('[data-video-editor-extension-diag-count="warning"]')).not.toBeInTheDocument();

      // ext.b should have warning badge only
      const bBadges = document.querySelector('[data-video-editor-extension-package-id="ext.b"]')!
        .querySelector('[data-video-editor-extension-diagnostic-badges="ext.b"]')!;
      expect(bBadges).toBeInTheDocument();
      expect(bBadges.querySelector('[data-video-editor-extension-diag-count="warning"]')).toBeInTheDocument();
      expect(bBadges.querySelector('[data-video-editor-extension-diag-count="error"]')).not.toBeInTheDocument();
    });

    it('shows diagnostic badges for disabled-by-user packages (SD3 visibility)', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.disabled', severity: 'error', code: 'E001', message: 'error' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.disabled', packageState: 'disabled-by-user', label: 'Disabled Pkg', stateReason: 'User disabled' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      expect(document.querySelector('[data-video-editor-extension-diag-count="error"]')).toBeInTheDocument();
    });

    it('shows diagnostic badges for invalid packages (SD3 visibility)', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ extensionId: 'ext.invalid', severity: 'error', code: 'E001', message: 'error' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.invalid', packageState: 'invalid', label: 'Invalid Pkg', stateReason: 'Bad manifest' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      expect(document.querySelector('[data-video-editor-extension-diag-count="error"]')).toBeInTheDocument();
    });
  });

  describe('expandable diagnostic details', () => {
    it('shows a collapsed Diagnostics toggle when there are diagnostics', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Broken' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      expect(toggle).toBeInTheDocument();
      expect(toggle).toHaveTextContent('Diagnostics');
      expect(toggle).toHaveTextContent('(1)');
    });

    it('expands to show diagnostic messages when toggled', async () => {
      const user = userEvent.setup();
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Something broke' }),
        makeDiagnostic({ id: 'diag-2', extensionId: 'ext.a', severity: 'warning', code: 'W001', message: 'Deprecated' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      await user.click(toggle);

      // Diagnostic messages should now be visible
      expect(screen.getByText('Something broke')).toBeInTheDocument();
      expect(screen.getByText('[E001]')).toBeInTheDocument();
      expect(screen.getByText('Deprecated')).toBeInTheDocument();
      expect(screen.getByText('[W001]')).toBeInTheDocument();

      // Toggle label should change
      expect(screen.getByRole('button', { name: 'Hide diagnostics for Package A' })).toBeInTheDocument();
    });

    it('shows contributionId alongside diagnostic message when present', async () => {
      const user = userEvent.setup();
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({
          id: 'diag-1',
          extensionId: 'ext.a',
          severity: 'error',
          code: 'E001',
          message: 'Render failed',
          contributionId: 'myRenderer',
        }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      await user.click(toggle);

      expect(screen.getByText('Render failed')).toBeInTheDocument();
      expect(screen.getByText('in myRenderer')).toBeInTheDocument();
    });

    it('collapses diagnostics when toggle is clicked again', async () => {
      const user = userEvent.setup();
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Broken' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      await user.click(toggle);
      expect(screen.getByText('Broken')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Hide diagnostics for Package A' }));
      expect(screen.queryByText('Broken')).not.toBeInTheDocument();
    });

    it('does NOT show Diagnostics toggle when there are no diagnostics for the package', () => {
      const { collection } = makeDiagnosticCollection([]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      expect(screen.queryByRole('button', { name: /diagnostics for Package A/i })).not.toBeInTheDocument();
    });
  });

  describe('live diagnostic updates', () => {
    it('re-renders badge counts when diagnostics are added without reopening the tab', () => {
      const { collection, setSnapshot } = makeDiagnosticCollection([]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      // Initially no badges
      expect(document.querySelector('[data-video-editor-extension-diagnostic-badges]')).not.toBeInTheDocument();

      // Publish diagnostics — simulate live update
      act(() => {
        setSnapshot([
          makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'New error' }),
        ]);
      });

      // Error badge should appear without reopening the tab
      const errorBadge = document.querySelector('[data-video-editor-extension-diag-count="error"]');
      expect(errorBadge).toBeInTheDocument();
      expect(errorBadge).toHaveTextContent('1');
    });

    it('re-renders badge counts when diagnostics are removed without reopening the tab', () => {
      const { collection, setSnapshot } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Old error' }),
        makeDiagnostic({ id: 'diag-2', extensionId: 'ext.a', severity: 'warning', code: 'W001', message: 'Old warning' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      // Initially both badges present
      expect(document.querySelector('[data-video-editor-extension-diag-count="error"]')).toBeInTheDocument();
      expect(document.querySelector('[data-video-editor-extension-diag-count="warning"]')).toBeInTheDocument();

      // Remove all diagnostics
      act(() => {
        setSnapshot([]);
      });

      // Badges should disappear
      expect(document.querySelector('[data-video-editor-extension-diagnostic-badges]')).not.toBeInTheDocument();
    });

    it('updates badge counts in the expanded diagnostic details when new diagnostics arrive', async () => {
      const user = userEvent.setup();
      const { collection, setSnapshot } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'First error' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      // Expand diagnostics
      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      await user.click(toggle);
      expect(screen.getByText('First error')).toBeInTheDocument();

      // Live-update: add a second diagnostic while expanded
      act(() => {
        setSnapshot([
          makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'First error' }),
          makeDiagnostic({ id: 'diag-2', extensionId: 'ext.a', severity: 'warning', code: 'W001', message: 'New warning' }),
        ]);
      });

      // Both diagnostics should be visible without reopening
      expect(screen.getByText('First error')).toBeInTheDocument();
      expect(screen.getByText('New warning')).toBeInTheDocument();

      // Badge count should update
      const warningBadge = document.querySelector('[data-video-editor-extension-diag-count="warning"]');
      expect(warningBadge).toBeInTheDocument();
      expect(warningBadge).toHaveTextContent('1');

      // Toggle count should update
      expect(toggle).toHaveTextContent('(2)');
    });
  });

  describe('data attributes for diagnostics', () => {
    it('sets data-video-editor-extension-diagnostics on the diagnostics container', async () => {
      const user = userEvent.setup();
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Test' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const container = document.querySelector('[data-video-editor-extension-diagnostics="ext.a"]');
      expect(container).toBeInTheDocument();
    });

    it('sets data-video-editor-extension-diagnostics-toggle on the toggle button', () => {
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Test' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = document.querySelector('[data-video-editor-extension-diagnostics-toggle="ext.a"]');
      expect(toggle).toBeInTheDocument();
    });

    it('sets data-video-editor-extension-diag-item and severity/code attrs on each diagnostic item', async () => {
      const user = userEvent.setup();
      const { collection } = makeDiagnosticCollection([
        makeDiagnostic({ id: 'diag-1', extensionId: 'ext.a', severity: 'error', code: 'E001', message: 'Test' }),
      ]);

      mockUseVideoEditorRuntime.mockReturnValue({
        extensionRuntime: makeRuntime([
          { extensionId: 'ext.a', packageState: 'loaded', label: 'Package A' },
        ]),
        extensionStateRepository: makeRepository(),
        triggerExtensionRefresh: vi.fn(),
        diagnosticCollection: collection as DiagnosticCollection,
      });

      render(<ExtensionManager />);

      const toggle = screen.getByRole('button', { name: 'Show diagnostics for Package A' });
      await user.click(toggle);

      const item = document.querySelector('[data-video-editor-extension-diag-item="true"]');
      expect(item).toBeInTheDocument();
      expect(item).toHaveAttribute('data-video-editor-extension-diag-severity', 'error');
      expect(item).toHaveAttribute('data-video-editor-extension-diag-code', 'E001');
    });
  });
});
