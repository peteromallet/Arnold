import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserVideoEditor } from '@/tools/video-editor/browser/BrowserVideoEditor';
import { mountVideoEditor } from '@/tools/video-editor/browser/mountVideoEditor';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';

const runtimeProviderSpy = vi.fn();

vi.mock('@/tools/video-editor/contexts/EditorRuntimeProvider', () => ({
  EditorRuntimeProvider: ({ children, ...props }: any) => {
    runtimeProviderSpy(props);
    return <div data-testid="runtime-provider">{children}</div>;
  },
}));

vi.mock('@/tools/video-editor/components/VideoEditorShell', () => ({
  VideoEditorShell: ({ mode, timelineId }: { mode: string; timelineId: string }) => (
    <div data-testid="video-editor-shell">{`${mode}:${timelineId}`}</div>
  ),
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

describe('BrowserVideoEditor', () => {
  it('mounts the real shell through the generic runtime provider with injected services', () => {
    const assetResolver = { resolveAssetUrl: vi.fn((file: string) => `https://assets.example/${file}`) };
    const exporter = { render: vi.fn() };

    render(
      <BrowserVideoEditor
        dataProvider={provider}
        timelineId="timeline-1"
        timelineName="Demo timeline"
        userId={null}
        assetResolver={assetResolver}
        exporter={exporter}
        hostContext={{ projectId: 'project-1' }}
      />,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('video-editor-shell')).toHaveTextContent('full:timeline-1');
    expect(runtimeProviderSpy).toHaveBeenCalledWith(expect.objectContaining({
      dataProvider: provider,
      timelineId: 'timeline-1',
      timelineName: 'Demo timeline',
      userId: null,
      runtime: expect.objectContaining({
        assetResolver,
        exporter,
        hostContext: { projectId: 'project-1' },
      }),
    }));
  });

  it('wraps the stock shell with renderLayout without replacing the public runtime bootstrap', () => {
    render(
      <BrowserVideoEditor
        dataProvider={provider}
        timelineId="timeline-1"
        renderLayout={(shell) => <div data-testid="layout-shell">{shell}</div>}
      />,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('layout-shell')).toBeInTheDocument();
    expect(screen.getByTestId('video-editor-shell')).toHaveTextContent('full:timeline-1');
  });

  it('imperatively mounts, updates, and unmounts the browser editor', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);

    let mounted!: ReturnType<typeof mountVideoEditor>;

    act(() => {
      mounted = mountVideoEditor(container, {
        dataProvider: provider,
        timelineId: 'timeline-1',
        mode: 'compact',
      });
    });

    expect(container.textContent).toContain('compact:timeline-1');

    act(() => {
      mounted.update({
        dataProvider: provider,
        timelineId: 'timeline-2',
        mode: 'full',
      });
    });

    expect(container.textContent).toContain('full:timeline-2');

    act(() => {
      mounted.unmount();
    });

    expect(container.textContent).toBe('');
    container.remove();
  });
});
