import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser/BrowserVideoEditorProvider';
import { defineExtension } from '@reigh/editor-sdk';
import type { ExtensionContext, DisposeHandle } from '@reigh/editor-sdk';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import {
  EXTENSION_SMOKE_CONTRIBUTION_ID,
  EXTENSION_SMOKE_QUERY_PARAM,
  EXTENSION_SMOKE_ACTIVE_VALUE,
} from '@/sdk/smoke/extensionSmoke';

const runtimeProviderSpy = vi.fn();

vi.mock('@/tools/video-editor/contexts/EditorRuntimeProvider', () => ({
  EditorRuntimeProvider: ({ children, ...props }: any) => {
    runtimeProviderSpy(props);
    return <div data-testid="runtime-provider">{children}</div>;
  },
}));

// Preserve original window.location so smoke-query tests can override search.
const originalLocation = window.location;

const provider: DataProvider = {
  loadTimeline: vi.fn(),
  saveTimeline: vi.fn(),
  loadAssetRegistry: vi.fn(),
  resolveAssetUrl: vi.fn(async (file: string) => file),
};

beforeEach(() => {
  // Restore a clean window.location before each test.
  Object.defineProperty(window, 'location', {
    value: { ...originalLocation, search: '' },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  runtimeProviderSpy.mockClear();
  Object.defineProperty(window, 'location', {
    value: originalLocation,
    writable: true,
    configurable: true,
  });
});

describe('BrowserVideoEditorProvider', () => {
  it('mounts the standalone runtime without importing the stock shell', () => {
    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId="timeline-1"
        timelineName="Provider demo"
        userId={null}
        hostContext={{ projectId: 'project-1' }}
      >
        <div data-testid="custom-shell">Custom shell</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('custom-shell')).toHaveTextContent('Custom shell');
    expect(runtimeProviderSpy).toHaveBeenCalledWith(expect.objectContaining({
      dataProvider: provider,
      timelineId: 'timeline-1',
      timelineName: 'Provider demo',
      userId: null,
      runtime: expect.objectContaining({
        hostContext: { projectId: 'project-1' },
      }),
    }));
  });

  // ---------------------------------------------------------------------------
  // T15: Compatibility tests — direct extensions prop for SDK/browser embeds
  // ---------------------------------------------------------------------------
  // Prove the direct `extensions` prop works for SDK/browser embeds WITHOUT
  // installed pack records, repository enablement, or any repository state,
  // and still synchronizes through the same lifecycle host pipeline.

  it('forwards direct extensions to the runtime provider when no repository or bundleStore is provided', () => {
    const extensionId = 'com.t15.direct-browser';
    const disposeSpy = vi.fn();

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'T15 direct browser extension',
        contributions: [
          {
            id: 't15.cmd' as never,
            kind: 'command',
            command: `${extensionId}.directCmd`,
            label: 'T15 direct command',
          },
        ],
      },
      activate(_ctx: ExtensionContext): DisposeHandle {
        disposeSpy();
        return { dispose: disposeSpy };
      },
    });

    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId="timeline-t15"
        userId={null}
        extensions={[extension]}
      >
        <div data-testid="t15-child">T15 child</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('t15-child')).toHaveTextContent('T15 child');

    // Verify extensions are forwarded to EditorRuntimeProvider unchanged.
    // The mock captures props that include the resolved extensions.
    const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
    expect(callArgs).toBeDefined();
    expect(callArgs.extensions).toHaveLength(1);
    expect(callArgs.extensions[0].manifest.id).toBe(extensionId);
    expect(callArgs.extensions[0].manifest.version).toBe('1.0.0');
  });

  it('supports SDK/browser embeds with multiple direct extensions and no repository at all', () => {
    const extA = defineExtension({
      manifest: {
        id: 'com.t15.multi-a' as never,
        version: '1.0.0',
        label: 'T15 Multi A',
        contributions: [
          {
            id: 't15.multi-a.cmd' as never,
            kind: 'command',
            command: 'com.t15.multi-a.cmd',
            label: 'T15 A command',
          },
        ],
      },
      activate(_ctx: ExtensionContext): DisposeHandle {
        return { dispose() {} };
      },
    });

    const extB = defineExtension({
      manifest: {
        id: 'com.t15.multi-b' as never,
        version: '2.0.0',
        label: 'T15 Multi B',
        contributions: [
          {
            id: 't15.multi-b.effect' as never,
            kind: 'effect',
            label: 'T15 B Effect',
            effectId: 'com.t15.multi-b.effect',
          },
        ],
      },
      activate(_ctx: ExtensionContext): DisposeHandle {
        return { dispose() {} };
      },
    });

    // No repository, no bundleStore — purely direct extensions
    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId="timeline-t15-multi"
        userId={null}
        extensions={[extA, extB]}
      >
        <div data-testid="t15-multi-child">Multi extensions</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('t15-multi-child')).toHaveTextContent('Multi extensions');

    const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
    expect(callArgs.extensions).toHaveLength(2);
    expect(callArgs.extensions[0].manifest.id).toBe('com.t15.multi-a');
    expect(callArgs.extensions[1].manifest.id).toBe('com.t15.multi-b');
  });

  it('does not require repository or bundleStore to be set — undefined defaults work', () => {
    // SDK/browser embed consumers should be able to omit repository and
    // bundleStore entirely without errors or warnings.
    const extension = defineExtension({
      manifest: {
        id: 'com.t15.norepo' as never,
        version: '1.0.0',
        label: 'T15 no repo',
        contributions: [],
      },
      activate(_ctx: ExtensionContext): DisposeHandle {
        return { dispose() {} };
      },
    });

    // Explicitly pass only extensions — repository and bundleStore are not
    // provided at all (they default to undefined in the component).
    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId="timeline-t15-standalone"
        userId={null}
        extensions={[extension]}
      >
        <div data-testid="t15-standalone">Standalone</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('t15-standalone')).toHaveTextContent('Standalone');

    // The extension must be forwarded through the hook's fast-path to the
    // runtime provider without any loader/resolution step.
    const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
    expect(callArgs.extensions).toHaveLength(1);
    expect(callArgs.extensions[0].manifest.id).toBe('com.t15.norepo');
  });

  it('passes an empty extensions array when no extensions prop is provided', () => {
    // Default behavior: when extensions prop is omitted, EditorRuntimeProvider
    // receives an empty array (not undefined).
    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId="timeline-t15-empty"
        userId={null}
      >
        <div data-testid="t15-empty">Empty</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('t15-empty')).toHaveTextContent('Empty');

    const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
    expect(callArgs.extensions).toBeDefined();
    expect(callArgs.extensions).toHaveLength(0);
  });

  // ---------------------------------------------------------------------------
  // Smoke extension injection via ?extensionSmoke=1
  // ---------------------------------------------------------------------------

  describe('?extensionSmoke=1 injection', () => {
    it('prepends the smoke extension when ?extensionSmoke=1 is present', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: `?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}` },
        writable: true,
        configurable: true,
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-1"
          userId={null}
        >
          <div data-testid="smoke-child">Smoke inject</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-child')).toHaveTextContent('Smoke inject');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      expect(callArgs.extensions).toHaveLength(1);
      expect(callArgs.extensions[0].manifest.id).toBe('com.reigh.smoke.extension-smoke');
      // Verify the smoke extension carries its stable contribution
      const contrib = callArgs.extensions[0].manifest.contributions?.[0];
      expect(contrib).toBeDefined();
      expect(contrib.id).toBe(EXTENSION_SMOKE_CONTRIBUTION_ID);
      expect(contrib.kind).toBe('slot');
      expect(contrib.slot).toBe('statusBar');
    });

    it('does NOT inject the smoke extension when query param is absent', () => {
      // Clean search (empty) — no ?extensionSmoke present
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: '' },
        writable: true,
        configurable: true,
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-no-param"
          userId={null}
        >
          <div data-testid="smoke-no-param">No param</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-no-param')).toHaveTextContent('No param');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      // Default: empty extensions array when no extensions prop and no smoke param
      expect(callArgs.extensions).toHaveLength(0);
    });

    it('does NOT inject the smoke extension when extensionSmoke=0 (not exactly 1)', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: '?extensionSmoke=0' },
        writable: true,
        configurable: true,
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-zero"
          userId={null}
        >
          <div data-testid="smoke-zero">Zero</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-zero')).toHaveTextContent('Zero');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      expect(callArgs.extensions).toHaveLength(0);
    });

    it('does NOT inject the smoke extension when extensionSmoke=true (not exactly 1)', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: '?extensionSmoke=true' },
        writable: true,
        configurable: true,
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-true"
          userId={null}
        >
          <div data-testid="smoke-true">True</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-true')).toHaveTextContent('True');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      expect(callArgs.extensions).toHaveLength(0);
    });

    it('prepends smoke extension before direct extensions preserving order', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: `?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}` },
        writable: true,
        configurable: true,
      });

      const directExt = defineExtension({
        manifest: {
          id: 'com.test.direct-order' as never,
          version: '1.0.0',
          label: 'Direct extension for order test',
          contributions: [
            {
              id: 'direct.cmd' as never,
              kind: 'command',
              command: 'com.test.direct-order.cmd',
              label: 'Direct command',
            },
          ],
        },
        activate(_ctx: ExtensionContext): DisposeHandle {
          return { dispose() {} };
        },
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-order"
          userId={null}
          extensions={[directExt]}
        >
          <div data-testid="smoke-order">Order</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-order')).toHaveTextContent('Order');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      expect(callArgs.extensions).toHaveLength(2);
      // Smoke extension must be first (prepended)
      expect(callArgs.extensions[0].manifest.id).toBe('com.reigh.smoke.extension-smoke');
      // Direct extension must follow in original order
      expect(callArgs.extensions[1].manifest.id).toBe('com.test.direct-order');
    });

    it('injects smoke as the only extension when no direct extensions are provided', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: `?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}` },
        writable: true,
        configurable: true,
      });

      // extensions prop is undefined — smoke should become the sole extension
      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-only"
          userId={null}
        >
          <div data-testid="smoke-only">Only smoke</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-only')).toHaveTextContent('Only smoke');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      expect(callArgs.extensions).toHaveLength(1);
      expect(callArgs.extensions[0].manifest.id).toBe('com.reigh.smoke.extension-smoke');
    });

    it('smoke extension has an activate function and no permissions', () => {
      Object.defineProperty(window, 'location', {
        value: { ...originalLocation, search: `?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}` },
        writable: true,
        configurable: true,
      });

      render(
        <BrowserVideoEditorProvider
          dataProvider={provider}
          timelineId="timeline-smoke-activate"
          userId={null}
        >
          <div data-testid="smoke-activate">Activate check</div>
        </BrowserVideoEditorProvider>,
      );

      expect(screen.getByTestId('smoke-activate')).toHaveTextContent('Activate check');

      const callArgs = runtimeProviderSpy.mock.calls[0]?.[0];
      const smokeExt = callArgs.extensions[0];
      expect(typeof smokeExt.activate).toBe('function');
      expect(smokeExt.manifest.permissions).toBeUndefined();
      expect(smokeExt.manifest.dependsOn).toBeUndefined();
    });
  });
});
