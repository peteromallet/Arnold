import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser/BrowserVideoEditorProvider';
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
});
