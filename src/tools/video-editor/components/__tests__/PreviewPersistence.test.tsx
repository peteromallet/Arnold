// @vitest-environment jsdom
 
import React, { forwardRef, useImperativeHandle } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const useTimelineEditorDataMock = vi.fn();
const useTimelineEditorOpsMock = vi.fn();
const useTimelinePlaybackContextMock = vi.fn();
const useTimelineChromeContextMock = vi.fn();
const usePanesStoreMock = vi.fn();
const useTimelineRealtimeMock = vi.fn();
const useKeyboardShortcutsMock = vi.fn();
const useVideoEditorRenderContextMock = vi.fn();
const useVideoEditorSlotRenderersMock = vi.fn();
const useVideoEditorAssetPanelsMock = vi.fn();
let editorDataValue: any;
let editorOpsValue: any;
let chromeValue: any;
let playbackValue: any;
let slotRenderersValue: any;
let overlayEditorProps: any;
let CompactPreviewComponent: any;
let CustomTwoPaneVideoEditorShellComponent: any;
let VideoEditorShellComponent: any;

vi.mock('@banodoco/timeline-schema', () => ({
  resolveTheme: vi.fn(() => null),
}), { virtual: true });

vi.mock('@banodoco/timeline-composition/theme-api', () => ({
  ThemeProvider: ({ children }: any) => <>{children}</>,
  useTheme: () => null,
}), { virtual: true });

vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
  THEME_PACKAGE_REGISTRY: {},
}), { virtual: true });

vi.mock('@banodoco/timeline-composition/theme-api', () => ({
  DEFAULT_THEME: {
    id: 'default',
    visual: {
      canvas: {
        width: 1280,
        height: 720,
        fps: 30,
      },
    },
  },
  ThemeProvider: ({ children }: any) => <>{children}</>,
  useTheme: () => ({
    id: 'default',
    visual: {
      canvas: {
        width: 1280,
        height: 720,
        fps: 30,
      },
    },
  }),
}), { virtual: true });

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

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (value: any) => unknown) => selector(usePanesStoreMock()),
}));

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

vi.mock('@/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel', () => ({
  SequenceCreatorPanel: () => <div data-testid="sequence-creator-panel" />,
}));

vi.mock('@/tools/video-editor/components/ThemeChip', () => ({
  ThemeChip: () => <div data-testid="theme-chip" />,
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/RemotionPreview', () => ({
  RemotionPreview: forwardRef(function MockRemotionPreview({ compact = false, config }: any, ref) {
    const api = {
      seek: vi.fn(),
      play: vi.fn(),
      pause: vi.fn(),
      togglePlayPause: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      seekTo: vi.fn(),
      toggle: vi.fn(),
      isPlaying: vi.fn(() => false),
      get isPlayingProp() {
        return false;
      },
    };

    useImperativeHandle(ref, () => api, []);

    return (
      <div data-testid="mock-preview">
        <div data-testid="mock-player" data-compact={compact ? 'true' : 'false'} />
        {!compact && config?.output?.resolution ? <div>{config.output.resolution}</div> : null}
      </div>
    );
  }),
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/PropertiesPanel', () => ({
  PropertiesPanel: () => <div data-testid="properties-panel" />,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface', () => ({
  VideoEditorAssetPanelSurface: ({ includeBuiltIn }: { includeBuiltIn?: boolean }) => (
    <div data-testid="asset-panel-surface" data-include-built-in={String(Boolean(includeBuiltIn))} />
  ),
}));

vi.mock('@/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel', () => ({
  SequenceCreatorPanel: () => <div data-testid="sequence-creator-panel" />,
}));

vi.mock('@/tools/video-editor/components/ThemeChip', () => ({
  ThemeChip: () => <div data-testid="theme-chip" />,
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

vi.mock('@/tools/video-editor/runtime/useVideoEditorRenderContext', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/runtime/useVideoEditorRenderContext')>(
    '@/tools/video-editor/runtime/useVideoEditorRenderContext',
  );

  return {
    ...actual,
    useVideoEditorRenderContext: () => useVideoEditorRenderContextMock(),
    useVideoEditorSlotRenderers: () => useVideoEditorSlotRenderersMock(),
    useVideoEditorAssetPanels: () => useVideoEditorAssetPanelsMock(),
  };
});

function renderShell(mode: 'compact' | 'full') {
  return render(
    <MemoryRouter
      initialEntries={['/tools/video-editor?timeline=timeline-1']}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <VideoEditorShellComponent mode={mode} timelineId="timeline-1" />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  overlayEditorProps = null;
  slotRenderersValue = {};
  useVideoEditorAssetPanelsMock.mockReset();
  useVideoEditorAssetPanelsMock.mockReturnValue([]);
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
    selectClip: vi.fn(),
    selectClips: vi.fn(),
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
    ...(playbackValue = {
      currentTime: 0,
      previewRef,
      playerContainerRef,
      onPreviewTimeUpdate: vi.fn(),
      formatTime: vi.fn(() => '0:00'),
    }),
  });

  useTimelineChromeContextMock.mockReturnValue({
    ...(chromeValue = {
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
    }),
  });

  useVideoEditorSlotRenderersMock.mockImplementation(() => slotRenderersValue);
  useVideoEditorRenderContextMock.mockImplementation(() => ({
    provider: {} as any,
    timelineId: 'timeline-1',
    timelineName: chromeValue.timelineName,
    userId: 'user-1',
    extensions: {
      slots: slotRenderersValue,
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
    },
    data: editorDataValue,
    ops: editorOpsValue,
    chrome: chromeValue,
    playback: playbackValue,
  }));

  usePanesStoreMock.mockReturnValue({
    isEditorPaneLocked: false,
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

beforeEach(async () => {
  ({ CompactPreview: CompactPreviewComponent } = await import('@/tools/video-editor/components/CompactPreview'));
  ({ CustomTwoPaneVideoEditorShell: CustomTwoPaneVideoEditorShellComponent } = await import('@/tools/video-editor/examples/CustomTwoPaneVideoEditorExample'));
  ({ VideoEditorShell: VideoEditorShellComponent } = await import('@/tools/video-editor/components/VideoEditorShell'));
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

  it('keeps one shared preview player active across compact/full transitions', () => {
    const view = renderShell('compact');

    expect(screen.getByTestId('mock-player')).toHaveAttribute('data-compact', 'true');
    expect(screen.queryByText('1280x720')).not.toBeInTheDocument();

    view.rerender(
      <MemoryRouter
        initialEntries={['/tools/video-editor?timeline=timeline-1']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <VideoEditorShellComponent mode="full" timelineId="timeline-1" />
      </MemoryRouter>,
    );

    expect(screen.getAllByTestId('mock-player')).toHaveLength(1);
    expect(screen.getByTestId('mock-player')).toHaveAttribute('data-compact', 'false');
    expect(screen.getByTitle('Settings')).toBeInTheDocument();
  });

  it('preserves the default shell fallbacks when no slot overrides are provided', () => {
    renderShell('full');

    expect(screen.getByRole('region', { name: 'Preview panel' })).toBeInTheDocument();
    expect(screen.getByTestId('timeline-editor')).toBeInTheDocument();
    expect(screen.getByTestId('properties-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('asset-panel-surface')).not.toBeInTheDocument();
    expect(screen.queryByText('Custom header')).not.toBeInTheDocument();
  });

  it('keeps the shared app-mode render control labelled Render and does not advertise a local-only action', () => {
    renderShell('full');

    const renderButton = screen.getByRole('button', { name: 'Render' });
    expect(renderButton).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Render locally' })).not.toBeInTheDocument();

    fireEvent.click(renderButton);

    expect(chromeValue.startRender).toHaveBeenCalledTimes(1);
  });

  it('renders slot-backed fallbacks and shell section overrides through the shared runtime slot hooks', () => {
    slotRenderersValue = {
      header: () => <div>Custom header</div>,
      toolbar: () => <div>Custom toolbar</div>,
      assetPanel: () => <div>Custom asset panel</div>,
      inspectorPanel: () => <div>Custom inspector panel</div>,
      timelineFooter: () => <div>Custom timeline footer</div>,
      statusBar: () => <div>Custom status bar</div>,
    };

    renderShell('full');

    expect(screen.getByText('Custom header')).toBeInTheDocument();
    expect(screen.getByText('Custom toolbar')).toBeInTheDocument();
    expect(screen.getByText('Custom asset panel')).toBeInTheDocument();
    expect(screen.getByText('Custom inspector panel')).toBeInTheDocument();
    expect(screen.getByText('Custom timeline footer')).toBeInTheDocument();
    expect(screen.getByText('Custom status bar')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Preview panel' })).toBeInTheDocument();
  });

  it('falls back to the registry-backed asset panel surface when asset panels are contributed without a slot override', () => {
    useVideoEditorAssetPanelsMock.mockReturnValue([{ id: 'asset-panel-extra' }]);

    renderShell('full');

    expect(screen.getByTestId('asset-panel-surface')).toHaveAttribute('data-include-built-in', 'false');
    expect(screen.getByTestId('properties-panel')).toBeInTheDocument();
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

  it('renders the standalone compact preview through the shared preview surface', () => {
    render(
      <MemoryRouter initialEntries={['/']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <CompactPreviewComponent timelineId="timeline-1" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('region', { name: 'Preview panel' })).toBeInTheDocument();
    expect(screen.getByTestId('mock-player')).toBeInTheDocument();
    expect(screen.getByText(/Timeline timeline/i)).toBeInTheDocument();
  });

  it('renders a custom two-pane shell from the shared preview, timeline, asset, and inspector primitives', () => {
    render(
      <MemoryRouter initialEntries={['/tools/video-editor?timeline=timeline-1']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <CustomTwoPaneVideoEditorShellComponent />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('custom-two-pane-shell')).toBeInTheDocument();
    expect(screen.getByText('Custom two-pane shell')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Preview panel' })).toBeInTheDocument();
    expect(screen.getByTestId('mock-player')).toBeInTheDocument();
    expect(screen.getByTestId('timeline-editor')).toBeInTheDocument();
    expect(screen.getByTestId('asset-panel-surface')).toHaveAttribute('data-include-built-in', 'true');
    expect(screen.getByTestId('properties-panel')).toBeInTheDocument();
  });
});
