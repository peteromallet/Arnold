import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser/BrowserVideoEditorProvider';
import { defineExtension } from '@reigh/editor-sdk';
import type { ExtensionContext, DisposeHandle } from '@reigh/editor-sdk';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';

const runtimeProviderSpy = vi.fn();

vi.mock('@/tools/video-editor/contexts/EditorRuntimeProvider', () => ({
  EditorRuntimeProvider: ({ children, ...props }: any) => {
    runtimeProviderSpy(props);
    return <div data-testid="runtime-provider">{children}</div>;
  },
}));

const provider: DataProvider = {
  loadTimeline: vi.fn(),
  saveTimeline: vi.fn(),
  loadAssetRegistry: vi.fn(),
  resolveAssetUrl: vi.fn(async (file: string) => file),
};

afterEach(() => {
  runtimeProviderSpy.mockClear();
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
});
