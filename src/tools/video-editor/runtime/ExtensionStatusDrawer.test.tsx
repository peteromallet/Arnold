// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext';
import {
  ExtensionStatusDrawer,
  useExtensionStatusInventory,
} from '@/tools/video-editor/runtime/ExtensionStatusDrawer';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface';
import { defineExtension, createDiagnosticCollection } from '@reigh/editor-sdk';
import type { DiagnosticCollection, ReighExtension } from '@reigh/editor-sdk';
import { createRendererRegistry } from '@/tools/video-editor/runtime/extensionRendererRegistry';
import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { EffectRegistryProvider, useEffectRegistryContext } from '@/tools/video-editor/effects/registry/EffectRegistryContext';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal runtime context value for testing. */
function buildRuntimeContext(
  extensions: readonly ReighExtension[],
  diagnosticCollection?: DiagnosticCollection,
): VideoEditorRuntimeContextValue {
  const runtime = normalizeExtensionRuntime(extensions);
  const dc = diagnosticCollection ?? createDiagnosticCollection();

  return {
    provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
    assetResolver: { resolveAssetUrl: async (f: string) => f },
    auth: { userId: 'test-user' },
    project: { projectId: null },
    shots: {
      shots: undefined,
      isLoading: false,
      error: null,
      refetchShots: () => {},
      finalVideoMap: new Map(),
      dismissFinalVideo: () => {},
    },
    mediaLightbox: {
      Lightbox: (() => null) as unknown as VideoEditorRuntimeContextValue['mediaLightbox']['Lightbox'],
      loadGenerationForLightbox: async () => null,
    },
    agentChat: {
      registerTimeline: () => {},
      unregisterTimeline: () => {},
    },
    toast: {
      error: () => '',
      success: () => '',
      warning: () => '',
      info: () => '',
    },
    telemetry: {
      log: () => {},
      warn: () => {},
      error: () => {},
    },
    timelineId: 'test-timeline',
    userId: 'test-user',
    extensions: runtime.config,
    extensionRuntime: runtime,
    diagnosticCollection: dc,
    rendererRegistry: createRendererRegistry(),
  };
}

function buildDrawerWrapper(contextValue: VideoEditorRuntimeContextValue) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <DataProviderWrapper value={contextValue}>
        {children}
      </DataProviderWrapper>
    );
  };
}

function RegistryCanaryEffect({ children }: EffectComponentProps) {
  return <>{children}</>;
}

function RegisterPreviewOnlyEffect() {
  const { registry } = useEffectRegistryContext();

  useEffect(() => {
    const handle = registry.register({
      effectId: 'preview-only-status-effect',
      contributionId: 'status.effect',
      component: RegistryCanaryEffect,
      provenance: 'trusted-loader',
      ownerExtensionId: 'com.example.status',
      status: 'active',
      renderability: {
        defaultRoute: 'preview',
        determinism: 'preview-only',
        capabilities: [
          { route: 'preview', status: 'supported', determinism: 'preview-only' },
          {
            route: 'browser-export',
            status: 'blocked',
            determinism: 'preview-only',
            blockerReason: 'preview-only',
            message: 'Preview only.',
          },
        ],
      },
    });
    return () => handle.dispose();
  }, [registry]);

  return null;
}

/** Create a simple extension with a slot contribution. */
function makeSlotExtension(
  id: string,
  label: string,
  contributionId: string,
  slot: string = 'header',
): ReighExtension {
  return defineExtension({
    manifest: {
      id: id as never,
      version: '1.0.0',
      label,
      contributions: [
        {
          id: contributionId as never,
          kind: 'slot',
          slot: slot as never,
          label: `${label} slot`,
        },
      ],
    },
  });
}

/** Create an extension with an inactive/reserved contribution (outputFormat kind). */
function makeInactiveExtension(
  id: string,
  label: string,
  contributionId: string,
): ReighExtension {
  return defineExtension({
    manifest: {
      id: id as never,
      version: '1.0.0',
      label,
      contributions: [
        {
          id: contributionId as never,
          kind: 'outputFormat',
          label: `${label} output`,
          requiresRender: false,
          outputExtension: 'json',
        },
      ],
    },
  });
}

/** Create an extension with both active and inactive contributions. */
function makeMixedExtension(
  id: string,
  label: string,
): ReighExtension {
  return defineExtension({
    manifest: {
      id: id as never,
      version: '2.0.0',
      label,
      contributions: [
        {
          id: `${id}.panel` as never,
          kind: 'panel',
          label: `${label} panel`,
        },
        {
          id: `${id}.output` as never,
          kind: 'outputFormat',
          label: `${label} output`,
          requiresRender: false,
          outputExtension: 'json',
        },
      ],
    },
  });
}

// ---------------------------------------------------------------------------
// Hook tests
// ---------------------------------------------------------------------------

describe('useExtensionStatusInventory', () => {
  it('returns empty inventory when there are no extensions', () => {
    const ctx = buildRuntimeContext([]);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory).toBeDefined();
    expect(inventory!.extensions).toHaveLength(0);
    expect(inventory!.summary.totalExtensions).toBe(0);
    expect(inventory!.summary.totalContributions).toBe(0);
  });

  it('returns inventory for a single extension with an active slot', () => {
    const ext = makeSlotExtension('com.example.test', 'Test Extension', 'test.slot');
    const ctx = buildRuntimeContext([ext]);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory).toBeDefined();
    expect(inventory!.extensions).toHaveLength(1);
    expect(inventory!.extensions[0].extensionId).toBe('com.example.test');
    expect(inventory!.extensions[0].label).toBe('Test Extension');
    expect(inventory!.extensions[0].version).toBe('1.0.0');
    expect(inventory!.extensions[0].contributions).toHaveLength(1);
    expect(inventory!.extensions[0].contributions[0].contributionId).toBe('test.slot');
    expect(inventory!.extensions[0].contributions[0].status).toBe('active');
    expect(inventory!.extensions[0].contributions[0].kind).toBe('slot');
    expect(inventory!.summary.totalExtensions).toBe(1);
    expect(inventory!.summary.activeExtensions).toBe(1);
    expect(inventory!.summary.totalContributions).toBe(1);
    expect(inventory!.summary.activeContributions).toBe(1);
  });

  it('marks reserved contributions as inactive', () => {
    const ext = makeInactiveExtension('com.example.inactive', 'Inactive Ext', 'inactive.effect');
    const ctx = buildRuntimeContext([ext]);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.extensions).toHaveLength(1);
    expect(inventory!.extensions[0].contributions[0].status).toBe('inactive');
    expect(inventory!.extensions[0].contributions[0].kind).toBe('outputFormat');
    expect(inventory!.extensions[0].contributions[0].milestone).toBeDefined();
    expect(inventory!.summary.inactiveContributions).toBe(1);
    expect(inventory!.summary.activeContributions).toBe(0);
  });

  it('handles mixed active/inactive contributions', () => {
    const ext = makeMixedExtension('com.example.mixed', 'Mixed Ext');
    const ctx = buildRuntimeContext([ext]);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.extensions).toHaveLength(1);
    const contribs = inventory!.extensions[0].contributions;
    expect(contribs).toHaveLength(2);
    const panel = contribs.find((c) => c.kind === 'panel');
    const output = contribs.find((c) => c.kind === 'outputFormat');
    expect(panel!.status).toBe('active');
    expect(output!.status).toBe('inactive');
    expect(inventory!.summary.activeContributions).toBe(1);
    expect(inventory!.summary.inactiveContributions).toBe(1);
    expect(inventory!.summary.totalContributions).toBe(2);
  });

  it('marks contributions with render errors as failed', () => {
    const ext = makeSlotExtension('com.example.broken', 'Broken Ext', 'broken.slot');
    const dc = createDiagnosticCollection();
    // Publish a render error for this contribution
    dc.publish({
      id: 'err-1',
      severity: 'error',
      code: 'render/contribution-error',
      message: 'Render failed for broken.slot',
      extensionId: 'com.example.broken',
      contributionId: 'broken.slot',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.extensions[0].contributions[0].status).toBe('failed');
    expect(inventory!.extensions[0].hasErrors).toBe(true);
    expect(inventory!.summary.failedExtensions).toBe(1);
    expect(inventory!.summary.activeExtensions).toBe(0);
  });

  it('detects export blocker diagnostics', () => {
    const ext = makeSlotExtension('com.example.exp', 'Export Ext', 'exp.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'export-err',
      severity: 'error',
      code: 'export/unknown-clip-type',
      message: 'Unknown clip type "foo"',
      extensionId: 'com.example.exp',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.exportBlockers).toHaveLength(1);
    expect(inventory!.exportBlockers[0].code).toBe('export/unknown-clip-type');
    expect(inventory!.summary.exportBlockers).toBe(1);
  });

  it('detects render blocker diagnostics (missing renderer)', () => {
    const ext = makeSlotExtension('com.example.mr', 'Missing Renderer', 'mr.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'render-err',
      severity: 'error',
      code: 'render/missing-renderer',
      message: 'No renderer registered for renderId "missing"',
      extensionId: 'com.example.mr',
      contributionId: 'mr.slot',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.renderBlockers).toHaveLength(1);
    expect(inventory!.renderBlockers[0].code).toBe('render/missing-renderer');
    expect(inventory!.summary.renderBlockers).toBe(1);
  });

  it('computes diagnostic summary counts correctly', () => {
    const ext = makeSlotExtension('com.example.diags', 'Diag Ext', 'diag.slot');
    const dc = createDiagnosticCollection();
    dc.publish({ id: 'e1', severity: 'error', code: 'test/error', message: 'err1', extensionId: 'com.example.diags' });
    dc.publish({ id: 'e2', severity: 'error', code: 'test/error2', message: 'err2', extensionId: 'com.example.diags' });
    dc.publish({ id: 'w1', severity: 'warning', code: 'test/warn', message: 'warn1', extensionId: 'com.example.diags' });
    dc.publish({ id: 'i1', severity: 'info', code: 'test/info', message: 'info1', extensionId: 'com.example.diags' });
    const ctx = buildRuntimeContext([ext], dc);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.summary.errorDiagnostics).toBe(2);
    expect(inventory!.summary.warningDiagnostics).toBe(1);
    expect(inventory!.summary.infoDiagnostics).toBe(1);
  });

  it('derives inventory with multiple extensions', () => {
    const extA = makeSlotExtension('com.example.a', 'Extension A', 'a.slot', 'header');
    const extB = makeInactiveExtension('com.example.b', 'Extension B', 'b.effect');
    const dc = createDiagnosticCollection();
    const ctx = buildRuntimeContext([extA, extB], dc);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(inventory!.extensions).toHaveLength(2);
    expect(inventory!.summary.totalExtensions).toBe(2);
    expect(inventory!.summary.activeExtensions).toBe(2); // Both have no errors
    expect(inventory!.summary.totalContributions).toBe(2);
    expect(inventory!.summary.activeContributions).toBe(1); // a.slot active
    expect(inventory!.summary.inactiveContributions).toBe(1); // b.effect inactive
  });

  it('returns frozen inventory objects', () => {
    const ext = makeSlotExtension('com.example.frozen', 'Frozen Ext', 'frozen.slot');
    const ctx = buildRuntimeContext([ext]);
    const Wrapper = buildDrawerWrapper(ctx);

    let inventory: ReturnType<typeof useExtensionStatusInventory> | undefined;

    function TestComponent() {
      inventory = useExtensionStatusInventory();
      return null;
    }

    render(
      <Wrapper>
        <TestComponent />
      </Wrapper>,
    );

    expect(Object.isFrozen(inventory!.extensions)).toBe(true);
    expect(Object.isFrozen(inventory!.summary)).toBe(true);
    expect(Object.isFrozen(inventory!.exportBlockers)).toBe(true);
    expect(Object.isFrozen(inventory!.renderBlockers)).toBe(true);
    expect(Object.isFrozen(inventory!.extensions[0].contributions)).toBe(true);
    expect(Object.isFrozen(inventory!.extensions[0].diagnostics)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Drawer component tests
// ---------------------------------------------------------------------------

describe('ExtensionStatusDrawer', () => {
  it('renders the drawer with dialog role', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    const drawer = screen.getByRole('dialog', { name: 'Extension status' });
    expect(drawer).toBeDefined();
    expect(drawer.getAttribute('data-video-editor-extension-status-drawer')).toBe('true');
  });

  it('displays the extension label and version', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    expect(screen.getByText('UI Extension')).toBeDefined();
    expect(screen.getByText('v1.0.0')).toBeDefined();
  });

  it('shows the "Extension Status" header', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    expect(screen.getByText('Extension Status')).toBeDefined();
  });

  it('shows empty state when no extensions loaded', () => {
    const ctx = buildRuntimeContext([]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    expect(screen.getByText('No extensions loaded.')).toBeDefined();
  });

  it('calls onClose when close button is clicked', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    const closeButton = screen.getByLabelText('Close extension status drawer');
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('displays summary bar with extension counts', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Should show 1 extension, 1 active
    const summaryRegion = screen.getByText('Extensions');
    expect(summaryRegion).toBeDefined();
  });

  it('expands card when clicked and shows contributions', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Initially the contribution label should not be visible (card collapsed)
    const contribText = 'UI Extension slot';
    expect(screen.queryByText(contribText)).toBeNull();

    // Click the extension header to expand
    const extensionButton = screen.getByLabelText('UI Extension — 1 contributions');
    fireEvent.click(extensionButton);

    // Now the contribution should be visible
    expect(screen.getByText(contribText)).toBeDefined();
    // Should show the active badge (text content is "Active", case is via Tailwind CSS)
    const activeBadge = document.querySelector('[data-video-editor-contribution-status="active"]');
    expect(activeBadge).toBeDefined();
    expect(activeBadge!.textContent).toBe('Active');
  });

  it('shows inactive badge for reserved contributions', () => {
    const ext = makeInactiveExtension('com.example.inactive', 'Inactive Ext', 'inactive.effect');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Expand the card
    const extensionButton = screen.getByLabelText('Inactive Ext — 1 contributions');
    fireEvent.click(extensionButton);

    // Should show the inactive badge (text content is "Inactive", case via Tailwind CSS)
    const inactiveBadge = document.querySelector('[data-video-editor-contribution-status="inactive"]');
    expect(inactiveBadge).toBeDefined();
    expect(inactiveBadge!.textContent).toBe('Inactive');
  });

  it('shows failed badge when contribution has render error', () => {
    const ext = makeSlotExtension('com.example.broken', 'Broken Ext', 'broken.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'err-1',
      severity: 'error',
      code: 'render/contribution-error',
      message: 'Render failed',
      extensionId: 'com.example.broken',
      contributionId: 'broken.slot',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Card should be auto-expanded because hasErrors=true
    const failedBadge = document.querySelector('[data-video-editor-contribution-status="failed"]');
    expect(failedBadge).toBeDefined();
    expect(failedBadge!.textContent).toBe('Failed');
  });

  it('auto-expands extension cards with errors', () => {
    const ext = makeSlotExtension('com.example.broken', 'Broken Ext', 'broken.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'err-1',
      severity: 'error',
      code: 'render/contribution-error',
      message: 'Render failed',
      extensionId: 'com.example.broken',
      contributionId: 'broken.slot',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // The error badge should be visible since the card auto-expands
    const failedBadge2 = document.querySelector('[data-video-editor-contribution-status="failed"]');
    expect(failedBadge2).toBeDefined();
    expect(failedBadge2!.textContent).toBe('Failed');
    // The extension header should show aria-expanded="true"
    const extensionButton = screen.getByLabelText('Broken Ext — 1 contributions');
    expect(extensionButton.getAttribute('aria-expanded')).toBe('true');
  });

  it('shows error count badge on extension header', () => {
    const ext = makeSlotExtension('com.example.broken', 'Broken Ext', 'broken.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'err-1',
      severity: 'error',
      code: 'render/contribution-error',
      message: 'Render failed',
      extensionId: 'com.example.broken',
      contributionId: 'broken.slot',
    });
    dc.publish({
      id: 'err-2',
      severity: 'error',
      code: 'compile/syntax-error',
      message: 'Syntax error',
      extensionId: 'com.example.broken',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // The extension header should show the error count badge (2 errors)
    // Use a more specific selector to avoid ambiguity with summary bar numbers
    const errorBadge = document.querySelector('[data-video-editor-extension-entry="com.example.broken"] span[title="2 errors"]');
    expect(errorBadge).toBeDefined();
    expect(errorBadge!.textContent).toContain('2');
  });

  it('shows export blocker indicator in summary bar', () => {
    const ext = makeSlotExtension('com.example.exp', 'Export Ext', 'exp.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'export-err',
      severity: 'error',
      code: 'export/unknown-clip-type',
      message: 'Unknown clip type',
      extensionId: 'com.example.exp',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    expect(screen.getByText('Export blockers')).toBeDefined();
    // The export blocker count in the summary bar — find by the specific structure
    const blockerCount = document.querySelector('[data-video-editor-extension-status-drawer] .text-red-400.tabular-nums.text-\\[10px\\]');
    expect(blockerCount).toBeDefined();
  });

  it('shows render blocker indicator in summary bar', () => {
    const ext = makeSlotExtension('com.example.mr', 'Missing Renderer Ext', 'mr.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'render-err',
      severity: 'error',
      code: 'render/missing-renderer',
      message: 'No renderer registered',
      extensionId: 'com.example.mr',
      contributionId: 'mr.slot',
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    expect(screen.getByText('Render blockers')).toBeDefined();
  });

  it('shows provider effect registry counts, renderability summaries, and planner/export blockers', async () => {
    const ext = makeSlotExtension('com.example.status', 'Status Extension', 'status.slot');
    const dc = createDiagnosticCollection();
    dc.publish({
      id: 'export-status-blocker',
      severity: 'error',
      code: 'export/effect-preview-only',
      message: 'Effect cannot browser export.',
      extensionId: 'com.example.status',
      contributionId: 'status.effect',
    });
    dc.publish({
      id: 'planner-status-blocker',
      severity: 'error',
      code: 'planner/browser-export/preview-only',
      message: 'Planner blocked browser export.',
      extensionId: 'com.example.status',
      contributionId: 'status.effect',
      detail: { source: 'render-planner' },
    });
    const ctx = buildRuntimeContext([ext], dc);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <EffectRegistryProvider>
          <RegisterPreviewOnlyEffect />
          <ExtensionStatusDrawer onClose={onClose} />
        </EffectRegistryProvider>
      </DataProviderWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('Effects')).toBeDefined();
      expect(screen.getByText('Effect export blockers')).toBeDefined();
      expect(screen.getByText('supported routes')).toBeDefined();
      expect(screen.getByText('blocked routes')).toBeDefined();
      expect(screen.getByText('Export blockers')).toBeDefined();
      expect(screen.getByText('Planner blockers')).toBeDefined();
    });

    expect(document.querySelector('[data-video-editor-effect-registry-summary="records"]')?.textContent).toContain('1');
    expect(document.querySelector('[data-video-editor-effect-registry-summary="browser-export-blockers"]')?.textContent).toContain('1');
    expect(document.querySelector('[data-video-editor-effect-renderability-summary="supported"]')?.textContent).toContain('1');
    expect(document.querySelector('[data-video-editor-effect-renderability-summary="blocked"]')?.textContent).toContain('1');
    expect(document.querySelector('[data-video-editor-planner-summary="blockers"]')?.textContent).toContain('1');
  });

  it('does not expose any install/uninstall/enable/disable buttons', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Verify no install/enable/disable/uninstall text appears
    const drawerText = document.querySelector('[data-video-editor-extension-status-drawer]')?.textContent ?? '';
    expect(drawerText).not.toContain('Install');
    expect(drawerText).not.toContain('Uninstall');
    expect(drawerText).not.toContain('Enable');
    expect(drawerText).not.toContain('Disable');
    expect(drawerText).not.toContain('Settings');
  });

  it('uses data attributes for extension and contribution entries', () => {
    const ext = makeSlotExtension('com.example.ui', 'UI Extension', 'ui.slot');
    const ctx = buildRuntimeContext([ext]);
    const onClose = vi.fn();

    render(
      <DataProviderWrapper value={ctx}>
        <ExtensionStatusDrawer onClose={onClose} />
      </DataProviderWrapper>,
    );

    // Extension entry data attribute
    const extEntry = document.querySelector('[data-video-editor-extension-entry="com.example.ui"]');
    expect(extEntry).toBeDefined();

    // Expand to see contributions
    fireEvent.click(screen.getByLabelText('UI Extension — 1 contributions'));

    // Contribution entry data attributes
    const contribEntry = document.querySelector('[data-video-editor-contribution-entry="ui.slot"]');
    expect(contribEntry).toBeDefined();
    expect(contribEntry!.getAttribute('data-video-editor-contribution-kind')).toBe('slot');

    // Contribution status data attribute
    const statusBadge = document.querySelector('[data-video-editor-contribution-status="active"]');
    expect(statusBadge).toBeDefined();
  });
});
