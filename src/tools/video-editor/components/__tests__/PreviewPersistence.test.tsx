// @vitest-environment jsdom
import React, { forwardRef, useImperativeHandle } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VideoEditorShell } from '@/tools/video-editor/components/VideoEditorShell';

const useTimelineEditorDataMock = vi.fn();
const useTimelineEditorOpsMock = vi.fn();
const useTimelinePlaybackContextMock = vi.fn();
const useTimelineChromeContextMock = vi.fn();
const usePanesMock = vi.fn();
const useTimelineRealtimeMock = vi.fn();
const useKeyboardShortcutsMock = vi.fn();
let editorDataValue: any;
let editorOpsValue: any;
let overlayEditorProps: any;

vi.mock('@/tools/video-editor/hooks/timelineStore', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/hooks/timelineStore')>(
    '@/tools/video-editor/hooks/timelineStore',
  );

  return {
    ...actual,
    useTimelineEditorData: () => useTimelineEditorDataMock(),
    useTimelineEditorOps: () => useTimelineEditorOpsMock(),
    useTimelinePlaybackContext: () => useTimelinePlaybackContextMock(),
    useTimelineChromeContext: () => useTimelineChromeContextMock(),
    useTimelineDataSelector: (selector: (value: any) => unknown) => selector(useTimelineEditorDataMock()),
    useTimelineOpsSelector: (selector: (value: any) => unknown) => selector(useTimelineEditorOpsMock()),
    useTimelinePlaybackSelector: (selector: (value: any) => unknown) => selector(useTimelinePlaybackContextMock()),
    useTimelineChromeSelector: (selector: (value: any) => unknown) => selector(useTimelineChromeContextMock()),
  };
});

vi.mock('@/shared/contexts/PanesContext', async () => {
  const actual = await vi.importActual<typeof import('@/shared/contexts/PanesContext')>(
    '@/shared/contexts/PanesContext',
  );

  return {
    ...actual,
    usePanes: () => usePanesMock(),
  };
});

vi.mock('@/tools/video-editor/hooks/useTimelineRealtime', () => ({
  useTimelineRealtime: () => useTimelineRealtimeMock(),
}));

vi.mock('@/tools/video-editor/hooks/useKeyboardShortcuts', () => ({
  useKeyboardShortcuts: (options: any) => useKeyboardShortcutsMock(options),
}));

vi.mock('@/tools/video-editor/hooks/usePerfDiagnostics', () => ({
  useRenderDiagnostic: vi.fn(),
  useEffectDiagnostic: () => vi.fn(),
}));

vi.mock('@/tools/video-editor/lib/perf-diagnostics', () => ({
  bootDiagnostics: vi.fn(),
  MemoryPressureDetector: {
    start: vi.fn(),
    stop: vi.fn(),
  },
}));

vi.mock('@/shared/lib/typedEvents', () => ({
  dispatchAppEvent: vi.fn(),
}));

vi.mock('@/shared/hooks/useHomeNavigation', () => ({
  useHomeNavigation: () => ({
    navigateHome: vi.fn(),
  }),
}));

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: () => false,
  useIsTablet: () => false,
}));

vi.mock('@/tools/video-editor/components/AgentChat', () => ({
  AgentChat: () => <div data-testid="agent-chat" />,
}));

vi.mock('@/tools/video-editor/components/TimelineEditor/TimelineEditor', () => ({
  TimelineEditor: () => <div data-testid="timeline-editor" />,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/PropertiesPanel', () => ({
  PropertiesPanel: () => <div data-testid="properties-panel" />,
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/OverlayEditor', () => ({
  default: (props: any) => {
    overlayEditorProps = props;
    return (
      <div
        data-testid="overlay-editor"
        data-device-class={props.deviceClass}
        data-gesture-owner={props.gestureOwner}
        data-input-modality={props.inputModality}
        data-interaction-mode={props.interactionMode}
      />
    );
  },
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: forwardRef(function MockButton({ children, variant: _variant, size: _size, asChild: _asChild, ...props }: any, ref) {
    return (
      <button ref={ref} type="button" {...props}>
        {children}
      </button>
    );
  }),
}));

vi.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
}));

vi.mock('@/shared/components/ui/slider', () => ({
  Slider: ({ value, onValueChange: _onValueChange, min: _min, max: _max, step: _step, ...props }: any) => (
    <div data-testid="slider" data-value={JSON.stringify(value)} {...props} />
  ),
}));

vi.mock('@/shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: any) => <>{children}</>,
  DropdownMenuTrigger: ({ children }: any) => <>{children}</>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick, ...props }: any) => (
    <button type="button" onClick={onClick} {...props}>
      {children}
    </button>
  ),
  DropdownMenuLabel: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSeparator: () => <div data-testid="dropdown-separator" />,
}));

vi.mock('@/shared/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }: any) => <>{children}</>,
  AlertDialogAction: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
  AlertDialogCancel: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
  AlertDialogContent: ({ children }: any) => <div>{children}</div>,
  AlertDialogDescription: ({ children }: any) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: any) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: any) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@remotion/player', () => ({
  Player: forwardRef(function MockPlayer(_props: any, ref) {
    const api = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      seekTo: vi.fn(),
      play: vi.fn(),
      pause: vi.fn(),
      toggle: vi.fn(),
      isPlaying: vi.fn(() => false),
    };

    useImperativeHandle(ref, () => api, []);

    return <div data-testid="mock-player" />;
  }),
}));

function renderShell(mode: 'compact' | 'full') {
  return render(
    <MemoryRouter
      initialEntries={['/tools/video-editor?timeline=timeline-1']}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <VideoEditorShell mode={mode} timelineId="timeline-1" />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  overlayEditorProps = null;
  useKeyboardShortcutsMock.mockReset();
  const selectedClipIds = new Set<string>();
  const previewRef = { current: null };
  const playerContainerRef = { current: null };
  const setInspectorTarget = vi.fn();
  const setContextTarget = vi.fn();
  const setInteractionMode = vi.fn();
  const setPrecisionEnabled = vi.fn();
  const setInputModalityFromPointerType = vi.fn(() => 'touch');
  const setGestureOwner = vi.fn();

  editorDataValue = {
    data: {
      rows: [],
      meta: {},
    },
    resolvedConfig: {
      output: {
        fps: 30,
        resolution: '1280x720',
      },
      clips: [
        {
          id: 'clip-1',
          at: 0,
          from: 0,
          to: 1,
        },
      ],
      registry: {},
    },
    selectedClipId: null,
    selectedClipIds,
    selectedTrackId: null,
    deviceClass: 'desktop',
    inputModality: 'mouse',
    interactionMode: 'select',
    gestureOwner: 'none',
    precisionEnabled: false,
    inspectorTarget: { kind: 'timeline' },
    trackScaleMap: {},
    compositionSize: { width: 1280, height: 720 },
  };
  useTimelineEditorDataMock.mockReturnValue(editorDataValue);

  editorOpsValue = {
    moveSelectedClipsToTrack: vi.fn(),
    handleToggleMuteClips: vi.fn(),
    handleSplitSelectedClip: vi.fn(),
    handleDeleteClips: vi.fn(),
    clearSelection: vi.fn(),
    selectClips: vi.fn(),
    setSelectedClipId: vi.fn(),
    setInspectorTarget,
    setContextTarget,
    setInteractionMode,
    setPrecisionEnabled,
    setInputModalityFromPointerType,
    setGestureOwner,
    onOverlayChange: vi.fn(),
    onDoubleClickAsset: vi.fn(),
  };
  useTimelineEditorOpsMock.mockReturnValue(editorOpsValue);

  useTimelinePlaybackContextMock.mockReturnValue({
    currentTime: 0,
    previewRef,
    playerContainerRef,
    onPreviewTimeUpdate: vi.fn(),
    formatTime: vi.fn(() => '0:00'),
  });

  useTimelineChromeContextMock.mockReturnValue({
    timelineName: 'Persistence Test',
    saveStatus: 'saved',
    isConflictExhausted: false,
    renderStatus: 'idle',
    renderLog: '',
    renderDirty: false,
    renderProgress: null,
    renderResultUrl: null,
    renderResultFilename: null,
    undo: vi.fn(),
    redo: vi.fn(),
    canUndo: false,
    canRedo: false,
    checkpoints: [],
    jumpToCheckpoint: vi.fn(),
    createManualCheckpoint: vi.fn(),
    setScaleWidth: vi.fn(),
    handleAddTrack: vi.fn(),
    handleClearUnusedTracks: vi.fn(),
    unusedTrackCount: 0,
    handleAddText: vi.fn(),
    handleAddTextAt: vi.fn(),
    reloadFromServer: vi.fn(),
    retrySaveAfterConflict: vi.fn(),
    startRender: vi.fn(),
  });

  usePanesMock.mockReturnValue({
    isGenerationsPaneLocked: false,
    setIsGenerationsPaneLocked: vi.fn(),
  });

  useTimelineRealtimeMock.mockReturnValue({
    isOpen: false,
    setOpen: vi.fn(),
    keepLocalChanges: vi.fn(),
    discardAndReload: vi.fn(),
  });
});

describe('VideoEditorShell preview persistence', () => {
  it('uses a safe fallback fps before resolved config is available', () => {
    editorDataValue = {
      ...editorDataValue,
      resolvedConfig: null,
      compositionSize: null,
    };
    useTimelineEditorDataMock.mockReturnValue(editorDataValue);

    renderShell('full');

    expect(useKeyboardShortcutsMock).toHaveBeenCalled();
    expect(useKeyboardShortcutsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      timelineFps: 30,
    });
  });

  it('keeps the same preview DOM node mounted across compact/full transitions', () => {
    const view = renderShell('compact');

    const initialNode = screen.getByTestId('mock-player');
    expect(screen.getAllByTestId('mock-player')).toHaveLength(1);
    expect(screen.queryByText('1280x720')).not.toBeInTheDocument();

    view.rerender(
      <MemoryRouter
        initialEntries={['/tools/video-editor?timeline=timeline-1']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <VideoEditorShell mode="full" timelineId="timeline-1" />
      </MemoryRouter>,
    );

    const sameNode = screen.getByTestId('mock-player');
    expect(screen.getAllByTestId('mock-player')).toHaveLength(1);
    expect(sameNode).toBe(initialNode);
    expect(screen.getByText('1280x720')).toBeInTheDocument();
  });

  it('shows the phone mode bar and routes mode changes through editor ops', () => {
    const setInspectorTarget = vi.fn();
    const setContextTarget = vi.fn();
    const setInteractionMode = vi.fn();
    const setPrecisionEnabled = vi.fn();

    useTimelineEditorDataMock.mockReturnValue({
      ...editorDataValue,
      deviceClass: 'phone',
      interactionMode: 'browse',
      precisionEnabled: false,
      selectedClipIds: new Set(['clip-1']),
      selectedClipId: 'clip-1',
      inspectorTarget: { kind: 'clip', clipId: 'clip-1' },
    });
    useTimelineEditorOpsMock.mockReturnValue({
      ...editorOpsValue,
      setInspectorTarget,
      setContextTarget,
      setInteractionMode,
      setPrecisionEnabled,
    });

    renderShell('full');

    expect(screen.getByRole('toolbar', { name: 'Phone timeline mode bar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Browse' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Select' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Move' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Trim' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Precision' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Move' }).className).toContain('min-h-11');
    expect(screen.getByRole('button', { name: 'Precision' }).className).toContain('min-h-11');

    fireEvent.click(screen.getByRole('button', { name: 'Move' }));
    fireEvent.click(screen.getByRole('button', { name: 'Precision' }));

    expect(setInteractionMode).toHaveBeenCalledWith('move');
    expect(setPrecisionEnabled).toHaveBeenCalledWith(true);
    expect(setContextTarget).toHaveBeenCalled();
    expect(setInspectorTarget).toHaveBeenCalled();
  });

  it('uses a selection-aware inspector affordance in compact tablet layout', () => {
    const setInspectorTarget = vi.fn();
    const setContextTarget = vi.fn();

    useTimelineEditorDataMock.mockReturnValue({
      ...editorDataValue,
      deviceClass: 'tablet',
      selectedClipIds: new Set(['clip-1']),
      selectedClipId: 'clip-1',
      inspectorTarget: { kind: 'clip', clipId: 'clip-1' },
    });
    useTimelineEditorOpsMock.mockReturnValue({
      ...editorOpsValue,
      setInspectorTarget,
      setContextTarget,
    });

    renderShell('compact');

    const inspectorButtons = screen.getAllByRole('button', { name: 'Clip' });
    expect(inspectorButtons.length).toBeGreaterThan(0);

    fireEvent.click(inspectorButtons[0]);

    expect(setInspectorTarget).toHaveBeenCalled();
    expect(setContextTarget).toHaveBeenCalled();
  });

  it('passes preview interaction policy into the overlay editor and announces preview state', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...editorDataValue,
      deviceClass: 'phone',
      inputModality: 'touch',
      interactionMode: 'trim',
      gestureOwner: 'preview',
      precisionEnabled: true,
      selectedClipId: 'clip-1',
      selectedClipIds: new Set(['clip-1']),
    });

    renderShell('full');

    expect(screen.getByRole('region', { name: 'Preview panel' })).toBeInTheDocument();
    expect(screen.getByText(/Preview overlay transform active\./)).toBeInTheDocument();
    expect(screen.getByText(/Mode trim\. Precision enabled\./)).toBeInTheDocument();
    expect(screen.getByText(/Timeline mode trim\. Precision enabled\. Preview transform active\./)).toBeInTheDocument();
    expect(screen.getByTestId('overlay-editor')).toHaveAttribute('data-device-class', 'phone');
    expect(screen.getByTestId('overlay-editor')).toHaveAttribute('data-gesture-owner', 'preview');
    expect(screen.getByTestId('overlay-editor')).toHaveAttribute('data-input-modality', 'touch');
    expect(screen.getByTestId('overlay-editor')).toHaveAttribute('data-interaction-mode', 'trim');
    expect(overlayEditorProps.setGestureOwner).toBe(editorOpsValue.setGestureOwner);
    expect(overlayEditorProps.setInputModalityFromPointerType).toBe(editorOpsValue.setInputModalityFromPointerType);
  });
});
