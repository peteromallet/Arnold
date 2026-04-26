import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LayoutMainContent } from './LayoutMainContent';

const panesState = vi.hoisted(() => ({
  state: {
    isEditorPaneLocked: false,
    effectiveEditorPaneHeight: 0,
    isTasksPaneLocked: true,
    tasksPaneWidth: 320,
    isShotsPaneLocked: true,
    shotsPaneWidth: 260,
    isGenerationsPaneLocked: true,
    isGenerationsPaneOpen: false,
    effectiveGenerationsPaneHeight: 180,
  },
}));
const useHeaderStateMock = vi.fn();
const useViewportResponsiveMock = vi.fn();
const useVideoEditorRouteStateMock = vi.fn();
const globalHeaderMock = vi.fn();
const globalProcessingWarningMock = vi.fn();

const defaultPanesState = {
  isTasksPaneLocked: true,
  tasksPaneWidth: 320,
  isShotsPaneLocked: true,
  shotsPaneWidth: 260,
  isGenerationsPaneLocked: true,
  isGenerationsPaneOpen: false,
  effectiveGenerationsPaneHeight: 180,
  editorPaneHeight: 540,
};

vi.mock('react-router-dom', () => ({
  Outlet: () => <div data-testid="layout-outlet" />,
}));

vi.mock('@/shared/components/GlobalHeader', () => ({
  GlobalHeader: (props: unknown) => {
    globalHeaderMock(props);
    return <div data-testid="global-header" />;
  },
}));

vi.mock('@/shared/components/ProcessingWarnings', () => ({
  GlobalProcessingWarning: (props: unknown) => {
    globalProcessingWarningMock(props);
    return <div data-testid="processing-warning" />;
  },
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: typeof panesState.state) => unknown) => selector(panesState.state),
}));

vi.mock('@/shared/contexts/ToolPageHeaderContext', () => ({
  useHeaderState: () => useHeaderStateMock(),
}));

vi.mock('@/shared/hooks/responsive/useViewportResponsive', () => ({
  useViewportResponsive: () => useViewportResponsiveMock(),
}));

vi.mock('@/app/hooks/useVideoEditorRouteState', () => ({
  useVideoEditorRouteState: () => useVideoEditorRouteStateMock(),
}));

describe('LayoutMainContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    panesState.state = {
      isEditorPaneLocked: false,
      effectiveEditorPaneHeight: 0,
      ...defaultPanesState,
    };
    useHeaderStateMock.mockReturnValue({
      header: <div data-testid="tool-header">Header</div>,
    });
    useViewportResponsiveMock.mockReturnValue({
      isSm: false,
      isMd: false,
      isLg: true,
      isXl: true,
      is2Xl: false,
      contentWidth: 1280,
      contentHeight: 720,
    });
    useVideoEditorRouteStateMock.mockReturnValue({
      isEditorRoute: false,
      isVideoEditorShellActive: false,
    });
  });

  it('renders global layout pieces and applies pane offsets', () => {
    const onOpenSettings = vi.fn();
    const { container } = render(
      <LayoutMainContent isMobileSplitView={false} onOpenSettings={onOpenSettings} />
    );

    expect(screen.getByTestId('global-header')).toBeInTheDocument();
    expect(screen.getByTestId('processing-warning')).toBeInTheDocument();
    expect(screen.getByTestId('tool-header')).toBeInTheDocument();
    expect(screen.getByTestId('layout-outlet')).toBeInTheDocument();
    expect(globalHeaderMock).toHaveBeenCalledWith(
      expect.objectContaining({
        contentOffsetRight: 336,
        contentOffsetLeft: 260,
        onOpenSettings,
      })
    );
    expect(globalProcessingWarningMock).toHaveBeenCalledWith(
      expect.objectContaining({
        onOpenSettings,
      })
    );

    const contentContainer = container.querySelector('.content-container');
    expect(contentContainer).not.toBeNull();
    expect(contentContainer).toHaveStyle({
      marginRight: '320px',
      marginLeft: '260px',
      paddingTop: '0px',
      paddingBottom: '180px',
      willChange: 'margin, padding',
    });
  });

  it('does not apply top padding when the editor pane is hidden', () => {
    panesState.state = {
      ...defaultPanesState,
      isEditorPaneLocked: false,
      effectiveEditorPaneHeight: 360,
    };

    const { container } = render(
      <LayoutMainContent isMobileSplitView={false} onOpenSettings={vi.fn()} />
    );

    const contentContainer = container.querySelector('.content-container');
    expect(contentContainer).not.toBeNull();
    expect(contentContainer).toHaveStyle({
      paddingTop: '0px',
    });
  });

  it('keeps content in place while the editor pane is only hovering open', () => {
    panesState.state = {
      ...defaultPanesState,
      isEditorPaneLocked: false,
      effectiveEditorPaneHeight: 360,
    };

    const { container } = render(
      <LayoutMainContent isMobileSplitView={false} onOpenSettings={vi.fn()} />
    );

    const contentContainer = container.querySelector('.content-container');
    expect(contentContainer).not.toBeNull();
    expect(contentContainer).toHaveStyle({
      paddingTop: '0px',
    });
  });

  it('applies bottom padding in the video editor shell when the generations pane is locked', () => {
    useVideoEditorRouteStateMock.mockReturnValue({
      isEditorRoute: true,
      isVideoEditorShellActive: true,
    });
    panesState.state = {
      ...defaultPanesState,
      isGenerationsPaneLocked: true,
      isGenerationsPaneOpen: false,
      effectiveGenerationsPaneHeight: 180,
    };

    const { container } = render(
      <LayoutMainContent isMobileSplitView={false} onOpenSettings={vi.fn()} />
    );

    const contentContainer = container.querySelector('.content-container');
    expect(contentContainer).not.toBeNull();
    expect(contentContainer).toHaveStyle({
      paddingBottom: '180px',
    });
  });

  it('keeps bottom padding at zero in the video editor shell when the generations pane is closed', () => {
    useVideoEditorRouteStateMock.mockReturnValue({
      isEditorRoute: true,
      isVideoEditorShellActive: true,
    });
    panesState.state = {
      ...defaultPanesState,
      isGenerationsPaneLocked: false,
      isGenerationsPaneOpen: false,
      effectiveGenerationsPaneHeight: 180,
    };

    const { container } = render(
      <LayoutMainContent isMobileSplitView={false} onOpenSettings={vi.fn()} />
    );

    const contentContainer = container.querySelector('.content-container');
    expect(contentContainer).not.toBeNull();
    expect(contentContainer).toHaveStyle({
      paddingBottom: '0px',
    });
  });
});
