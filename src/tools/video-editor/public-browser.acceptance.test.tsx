import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  BrowserVideoEditor,
  InMemoryDataProvider,
} from '@/tools/video-editor/browser';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser-provider';
import { createEmbedDemoTimelineFixture } from '@/tools/video-editor/testing';

const runtimeProviderSpy = vi.fn();

vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
  THEME_PACKAGE_REGISTRY: {},
}));

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

afterEach(() => {
  runtimeProviderSpy.mockClear();
});

describe('public browser SDK acceptance', () => {
  it('mounts the standalone shell from the public browser entrypoint with a shared fixture timeline', () => {
    const fixture = createEmbedDemoTimelineFixture();
    const provider = new InMemoryDataProvider({
      timelines: {
        [fixture.timelineId]: fixture,
      },
    });

    render(
      <BrowserVideoEditor
        dataProvider={provider}
        timelineId={fixture.timelineId}
        timelineName={fixture.timelineName}
        renderLayout={(shell) => <div data-testid="layout-shell">{shell}</div>}
      />,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('layout-shell')).toBeInTheDocument();
    expect(screen.getByTestId('video-editor-shell')).toHaveTextContent(`full:${fixture.timelineId}`);
    expect(runtimeProviderSpy).toHaveBeenCalledWith(expect.objectContaining({
      timelineId: fixture.timelineId,
      timelineName: fixture.timelineName,
    }));
  });

  it('mounts a custom shell from the public browser-provider entrypoint with the shared fixture timeline', () => {
    const fixture = createEmbedDemoTimelineFixture();
    const provider = new InMemoryDataProvider({
      timelines: {
        [fixture.timelineId]: fixture,
      },
    });

    render(
      <BrowserVideoEditorProvider
        dataProvider={provider}
        timelineId={fixture.timelineId}
        timelineName={fixture.timelineName}
      >
        <div data-testid="custom-shell">Custom fixture shell</div>
      </BrowserVideoEditorProvider>,
    );

    expect(screen.getByTestId('runtime-provider')).toBeInTheDocument();
    expect(screen.getByTestId('custom-shell')).toHaveTextContent('Custom fixture shell');
    expect(runtimeProviderSpy).toHaveBeenCalledWith(expect.objectContaining({
      timelineId: fixture.timelineId,
      timelineName: fixture.timelineName,
    }));
  });
});
