// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Mutable slot renderer registry for fine-grained test control
// ---------------------------------------------------------------------------

type SlotRendererFn = (context: VideoEditorRenderContext) => ReactNode;

let __slotRenderers: Partial<Record<string, SlotRendererFn>> = {};

function __setSlotRenderers(renderers: Partial<Record<string, SlotRendererFn>>) {
  __slotRenderers = { ...renderers };
}

function __clearSlotRenderers() {
  __slotRenderers = {};
}

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

vi.mock('@/tools/video-editor/hooks/timelineStore.ts', () => ({
  useTimelineEditorData: () => ({
    dataRef: { current: null },
    data: null,
    selectedClipIds: new Set<string>(),
    selectedTrackId: null,
    resolvedConfig: null,
    deviceClass: 'desktop' as const,
    precisionEnabled: false,
    interactionMode: 'browse' as const,
    gestureOwner: null,
    inspectorTarget: { kind: 'timeline' as const },
  }),
  useTimelineEditorOps: () => ({
    applyEdit: vi.fn(),
    handleDeleteClips: vi.fn(),
    moveSelectedClipsToTrack: vi.fn(),
    handleToggleMuteClips: vi.fn(),
    handleSplitSelectedClip: vi.fn(),
    clearSelection: vi.fn(),
    setInspectorTarget: vi.fn(),
    setContextTarget: vi.fn(),
    setPrecisionEnabled: vi.fn(),
    setInteractionMode: vi.fn(),
  }),
  useTimelineChromeContext: () => ({
    saveStatus: 'saved' as const,
    isConflictExhausted: false,
    retrySaveAfterConflict: vi.fn(),
    reloadFromServer: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    canUndo: false,
    canRedo: false,
    checkpoints: [],
    jumpToCheckpoint: vi.fn(),
    createManualCheckpoint: vi.fn(),
    timelineName: 'Test Timeline',
    setScaleWidth: vi.fn(),
    startRender: vi.fn(),
    renderStatus: 'idle' as const,
    renderProgress: null,
    renderResultUrl: null,
    renderResultFilename: null,
    renderDirty: false,
  }),
  useTimelinePlaybackContext: () => ({
    currentTime: 0,
    previewRef: { current: { togglePlayPause: vi.fn(), seek: vi.fn() } },
    formatTime: (t: number) => `${t.toFixed(1)}s`,
  }),
}));

vi.mock('@/tools/video-editor/hooks/useKeyboardShortcuts.ts', () => ({
  useKeyboardShortcuts: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useTimelineRealtime.ts', () => ({
  useTimelineRealtime: () => ({
    isOpen: false,
    setOpen: vi.fn(),
    keepLocalChanges: vi.fn(),
    discardAndReload: vi.fn(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useEditorSync.ts', () => ({
  useEditorSync: () => ({
    syncState: 'idle' as const,
    syncError: null,
    isSyncAvailable: false,
    performSync: vi.fn(),
    lastSyncResult: null,
  }),
}));

vi.mock('@/tools/video-editor/hooks/usePerfDiagnostics.ts', () => ({
  useRenderDiagnostic: vi.fn(),
}));

vi.mock('@/tools/video-editor/components/CommandPalette/CommandPalette.tsx', () => ({
  CommandPalette: ({ open }: { open: boolean }) =>
    open ? <div data-testid="command-palette">Command Palette</div> : null,
}));

vi.mock('@/tools/video-editor/lib/perf-diagnostics.ts', () => ({
  bootDiagnostics: vi.fn(),
  MemoryPressureDetector: { start: vi.fn(), stop: vi.fn() },
}));

vi.mock('@/tools/video-editor/runtime/useVideoEditorRenderContext.ts', () => ({
  useVideoEditorSlotRenderers: () => __slotRenderers,
  useVideoEditorRenderContext: () => ({
    provider: {} as any,
    timelineId: 'test-timeline',
    timelineName: 'Test Timeline',
    userId: 'user-1',
    extensions: { slots: {}, dialogHost: { dialogs: [] }, registry: { panels: [], inspectorSections: [] } },
    data: {} as any,
    ops: {} as any,
    chrome: {} as any,
    playback: {} as any,
  }),
  useVideoEditorAssetPanels: () => [],
  useVideoEditorDialogDescriptors: () => [],
  useVideoEditorPanelRegistry: () => ({ panels: [], inspectorSections: [] }),
  useResolvedVideoEditorPanelRegistry: () => ({
    assetPanels: [],
    inspectorSections: { all: [], beforeDefault: [], afterDefault: [] },
  }),
  useVideoEditorInspectorSections: () => [],
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx', () => ({
  PreviewPanel: () => <div data-testid="preview-panel">Preview</div>,
  default: () => <div data-testid="preview-panel">Preview</div>,
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/useVideoEditorPreviewSurface.tsx', () => ({
  useVideoEditorPreviewSurface: () => ({
    slotRef: { current: null },
    portal: null,
  }),
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx', () => ({
  PropertiesPanel: () => <div data-testid="properties-panel">Properties</div>,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface.tsx', () => ({
  VideoEditorAssetPanelSurface: () => <div data-testid="asset-panel-surface">Asset Panel</div>,
}));

vi.mock('@/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx', () => ({
  SequenceCreatorPanel: () => null,
}));

vi.mock('@/tools/video-editor/components/ThemeChip.tsx', () => ({
  ThemeChip: () => null,
}));

vi.mock('@/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx', () => ({
  TimelineEditor: () => <div data-testid="timeline-editor">Timeline Editor</div>,
}));

vi.mock('@/tools/video-editor/lib/config-utils.ts', () => ({
  getTimelineDurationInFrames: () => 300,
  parseResolution: () => ({ width: 1920, height: 1080 }),
}));

vi.mock('@/tools/video-editor/lib/keyboard-delete.ts', () => ({
  buildKeyboardDeleteMutation: () => null,
}));

vi.mock('@/tools/video-editor/lib/mobile-interaction-model.ts', () => ({
  areTimelineInteractionTargetsEqual: () => true,
}));

vi.mock('@/shared/lib/typedEvents.ts', () => ({
  dispatchAppEvent: vi.fn(),
}));

vi.mock('@/shared/state/selectionStore.ts', () => ({
  editorReplaceTimelineSelection: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { TimelineEditorShellCore } from '@/tools/video-editor/components/TimelineEditorShellCore';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TimelineEditorShellCore surface slots', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __clearSlotRenderers();
  });

  // ---- Baseline rendering ---------------------------------------------------
  it('renders the shell without crashing with default props', () => {
    const { container } = render(
      <TimelineEditorShellCore timelineId="test-timeline" />,
    );
    expect(container.querySelector('[data-video-editor-shell-region]')).toBeTruthy();
  });

  it('renders the timeline editor component', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);
    expect(screen.getByTestId('timeline-editor')).toBeTruthy();
  });

  it('opens the host command palette for reserved CtrlOrCmd+Shift+P', async () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    fireEvent.keyDown(window, {
      key: 'p',
      ctrlKey: true,
      shiftKey: true,
    });

    await waitFor(() => expect(screen.getByTestId('command-palette')).toBeTruthy());
  });

  it('renders the preview panel component', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);
    expect(screen.getByTestId('preview-panel')).toBeTruthy();
  });

  it('renders the properties panel component', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);
    expect(screen.getByTestId('properties-panel')).toBeTruthy();
  });

  // ---- Reserved slot canaries --------------------------------------------
  it('renders canaries for codePanel, writingPanel, and stagePanel', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const codeCanary = document.querySelector('[data-video-editor-slot="codePanel"]');
    const writingCanary = document.querySelector('[data-video-editor-slot="writingPanel"]');
    const stageCanary = document.querySelector('[data-video-editor-slot="stagePanel"]');

    expect(codeCanary).toBeTruthy();
    expect(writingCanary).toBeTruthy();
    expect(stageCanary).toBeTruthy();
  });

  it('renders canaries with canary data attribute', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const canaries = document.querySelectorAll('[data-video-editor-canary="true"]');
    expect(canaries.length).toBe(3);

    canaries.forEach((el) => {
      expect(el.getAttribute('data-video-editor-canary')).toBe('true');
    });
  });

  it('renders canaries with visible milestone in legend text', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const codeCanary = document.querySelector('[data-video-editor-slot="codePanel"]');
    const writingCanary = document.querySelector('[data-video-editor-slot="writingPanel"]');
    const stageCanary = document.querySelector('[data-video-editor-slot="stagePanel"]');

    expect(codeCanary?.textContent).toContain('M4');
    expect(writingCanary?.textContent).toContain('M4');
    expect(stageCanary?.textContent).toContain('M3');
  });

  it('renders canaries with visible slot label text', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const codeCanary = document.querySelector('[data-video-editor-slot="codePanel"]');
    const writingCanary = document.querySelector('[data-video-editor-slot="writingPanel"]');
    const stageCanary = document.querySelector('[data-video-editor-slot="stagePanel"]');

    expect(codeCanary?.textContent).toContain('Code panel canary');
    expect(writingCanary?.textContent).toContain('Writing panel canary');
    expect(stageCanary?.textContent).toContain('Stage panel canary');
  });

  // ---- Shell region data attributes -----------------------------------------
  it('renders host-owned shell regions with correct data attributes', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const rightPanel = document.querySelector('[data-video-editor-shell-region="rightPanel"]');
    const reservedSlots = document.querySelector('[data-video-editor-shell-region="reservedSlots"]');

    expect(rightPanel).toBeTruthy();
    expect(reservedSlots).toBeTruthy();
  });

  it('does not render leftPanel region when no leftPanel slot renderer is registered', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const leftPanel = document.querySelector('[data-video-editor-shell-region="leftPanel"]');
    expect(leftPanel).toBeNull();
  });

  // ---- Reserved slots container styling -------------------------------------
  it('wraps reserved slots in a flex container with border', () => {
    const { container } = render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const reservedContainer = container.querySelector('[data-video-editor-shell-region="reservedSlots"]');
    expect(reservedContainer).toBeTruthy();
    expect(reservedContainer?.classList.contains('flex')).toBe(true);
    expect(reservedContainer?.classList.contains('flex-wrap')).toBe(true);
  });

  // ---- Static surface slots do NOT render when no renderer and not reserved --
  it('does not render leftPanel slot when no renderer is registered', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const leftPanelSlot = document.querySelector('[data-video-editor-slot="leftPanel"]');
    expect(leftPanelSlot).toBeNull();
  });

  it('does not render rightPanel slot when no renderer is registered (falls through to default content)', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const rightPanelSlot = document.querySelector('[data-video-editor-slot="rightPanel"]');
    expect(rightPanelSlot).toBeNull();
  });

  // ---- Desktop containment is coherent ---------------------------------------
  it('renders the desktop layout grid with correct columns when no left panel', () => {
    const { container } = render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const main = container.querySelector('main');
    expect(main).toBeTruthy();
    const style = main?.getAttribute('style') ?? '';
    expect(style).toContain('minmax(0,1fr) 360px');
  });

  // ---- Multiple reserved slots render in deterministic order -----------------
  it('renders reserved slots in deterministic order: codePanel, writingPanel, stagePanel', () => {
    const { container } = render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const reservedContainer = container.querySelector('[data-video-editor-shell-region="reservedSlots"]');
    const children = reservedContainer?.querySelectorAll('[data-video-editor-slot]');
    expect(children?.length).toBe(3);

    const slotNames = Array.from(children ?? []).map((el) =>
      el.getAttribute('data-video-editor-slot'),
    );
    expect(slotNames).toEqual(['codePanel', 'writingPanel', 'stagePanel']);
  });

  // ---- Force condensed mode still renders reserved slots ---------------------
  it('renders reserved placeholders in condensed mode', () => {
    render(<TimelineEditorShellCore timelineId="test-timeline" forceCondensed />);

    const codePlaceholder = document.querySelector('[data-video-editor-slot="codePanel"]');
    expect(codePlaceholder).toBeTruthy();
  });
});

describe('TimelineEditorShellCore with registered slot renderers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __clearSlotRenderers();
  });

  it('renders a registered leftPanel slot renderer in the left panel region', () => {
    const leftPanelRenderer = vi.fn(() => <div data-testid="left-panel-content">Left Panel Content</div>);
    __setSlotRenderers({ leftPanel: leftPanelRenderer });

    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const leftPanelRegion = document.querySelector('[data-video-editor-shell-region="leftPanel"]');
    expect(leftPanelRegion).toBeTruthy();
    expect(screen.getByTestId('left-panel-content')).toBeTruthy();
    expect(leftPanelRenderer).toHaveBeenCalled();
  });

  it('renders a registered rightPanel slot renderer instead of default properties panel', () => {
    const rightPanelRenderer = vi.fn(() => <div data-testid="right-panel-content">Right Panel Content</div>);
    __setSlotRenderers({ rightPanel: rightPanelRenderer });

    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    expect(screen.getByTestId('right-panel-content')).toBeTruthy();
    expect(screen.queryByTestId('properties-panel')).toBeNull();
    expect(rightPanelRenderer).toHaveBeenCalled();
  });

  it('renders a registered dialogs slot renderer', () => {
    const dialogsRenderer = vi.fn(() => <div data-testid="dialogs-content">Dialog Content</div>);
    __setSlotRenderers({ dialogs: dialogsRenderer });

    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    expect(screen.getByTestId('dialogs-content')).toBeTruthy();
    expect(dialogsRenderer).toHaveBeenCalled();
  });

  it('renders a registered header slot renderer wrapped in error boundary context', () => {
    const headerRenderer = vi.fn(() => <div data-testid="header-content">Header</div>);
    __setSlotRenderers({ header: headerRenderer });

    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    expect(screen.getByTestId('header-content')).toBeTruthy();
    expect(headerRenderer).toHaveBeenCalled();
  });

  it('replaces canary with registered renderer for reserved slots', () => {
    const codePanelRenderer = vi.fn(() => <div data-testid="code-panel-content">Code Panel Content</div>);
    __setSlotRenderers({ codePanel: codePanelRenderer });

    render(<TimelineEditorShellCore timelineId="test-timeline" />);

    // Should render the actual content, not the canary
    expect(screen.getByTestId('code-panel-content')).toBeTruthy();
    // The canary should NOT be rendered for codePanel when a renderer is registered
    expect(document.querySelector('[data-video-editor-canary="true"][data-video-editor-slot="codePanel"]')).toBeNull();
    expect(codePanelRenderer).toHaveBeenCalled();
  });

  it('renders desktop layout with leftPanel column when leftPanel renderer registered', () => {
    const leftPanelRenderer = vi.fn(() => <div data-testid="left-panel-content">Left</div>);
    __setSlotRenderers({ leftPanel: leftPanelRenderer });

    const { container } = render(<TimelineEditorShellCore timelineId="test-timeline" />);

    const main = container.querySelector('main');
    const style = main?.getAttribute('style') ?? '';
    // When leftPanel is registered, grid columns should include an auto column for it
    expect(style).toContain('auto');
    expect(style).toContain('minmax(0,1fr)');
    expect(style).toContain('360px');
  });
});
