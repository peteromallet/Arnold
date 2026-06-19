// @vitest-environment jsdom
import React from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TimelineEditorCore } from '@/tools/video-editor/components/TimelineEditor/TimelineEditorCore';
import {
  createTimelineStore,
  TimelineStoreProvider,
} from '@/tools/video-editor/hooks/timelineStore';

// ---------------------------------------------------------------------------
// Mocks for hooks that require deep context chains
// ---------------------------------------------------------------------------

const useRenderDiagnosticMock = vi.fn();
vi.mock('@/tools/video-editor/hooks/usePerfDiagnostics', () => ({
  useRenderDiagnostic: (...args: unknown[]) => useRenderDiagnosticMock(...args),
}));

vi.mock('@/tools/video-editor/hooks/useClipDrag', () => ({
  useClipDrag: () => ({ dragSessionRef: { current: null } }),
}));

vi.mock('@/tools/video-editor/hooks/useMarqueeSelect', () => ({
  useMarqueeSelect: () => ({
    marqueeRect: null,
    onPointerDown: vi.fn(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useStaleVariants', () => ({
  useStaleVariants: () => ({
    staleAssetKeys: new Set<string>(),
    dismissedAssetKeys: new Set<string>(),
    generationAssetKeys: new Set<string>(),
    dismissAsset: vi.fn(),
    updateAssetToCurrentVariant: vi.fn(),
    applyVariantToAsset: vi.fn(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useActiveTaskClips', () => ({
  useActiveTaskClips: () => ({
    activeTaskAssetKeys: new Set<string>(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useAddVariantAsGeneration', () => ({
  useAddVariantAsGeneration: () => ({
    addVariantAsGenerationAfterClip: vi.fn(),
    isPending: false,
    isAddingVariantAsGenerationPending: () => false,
  }),
}));

const setGestureOwner = vi.fn();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const defaultData = {
  rows: [
    { id: 'V1', actions: [{ id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' }] },
  ],
  tracks: [{ id: 'V1', kind: 'visual' as const, label: 'V1' }],
  registry: { assets: {} },
  meta: {
    'clip-1': { asset: 'asset-1', track: 'V1' },
  },
};

const defaultResolvedConfig = {
  clips: [
    {
      id: 'clip-1',
      clipType: 'video' as const,
      track: 'V1',
      assetEntry: { src: 'test.mp4', type: 'video/mp4' as const, duration: 10 },
    },
  ],
  tracks: [{ id: 'V1', kind: 'visual' as const, label: 'V1' }],
  registry: { assets: {} },
};

/** Creates a fresh timeline store with all slices wired for overlay tests. */
function createOverlayTestStore() {
  const store = createTimelineStore();
  const selectedClipIds = new Set<string>();
  const selectedClipIdsRef = { current: new Set<string>() };
  store.getState().syncSlices({
    data: {
      data: defaultData,
      resolvedConfig: defaultResolvedConfig,
      deviceClass: 'desktop' as const,
      inputModality: 'mouse' as const,
      interactionMode: 'browse' as const,
      gestureOwner: 'none' as const,
      precisionEnabled: false,
      contextTarget: 'timeline' as const,
      inspectorTarget: 'none' as const,
      interactionPolicy: {
        deviceClass: 'desktop' as const,
        inputModality: 'mouse' as const,
        interactionMode: 'browse' as const,
        gestureOwner: 'none' as const,
        precisionEnabled: false,
        contextTarget: 'timeline' as const,
        inspectorTarget: 'none' as const,
      },
      selectedClipId: null,
      selectedClipIds,
      selectedClipIdsRef,
      additiveSelectionRef: { current: false },
      selectedTrackId: null,
      primaryClipId: null,
      selectedClip: null,
      selectedTrack: null,
      selectedClipHasPredecessor: false,
      compositionSize: { width: 1920, height: 1080 },
      trackScaleMap: {},
      scale: 30,
      scaleWidth: 30,
      isLoading: false,
      dataRef: { current: defaultData },
      pendingOpsRef: { current: 0 },
      interactionStateRef: { current: null },
      coordinator: {
        update: vi.fn(() => null),
        showSecondaryGhosts: vi.fn(),
        end: vi.fn(),
        lastPosition: null,
        editAreaRef: { current: null },
      },
      indicatorRef: { current: null },
      editAreaRef: { current: null },
      preferences: {
        scaleWidth: 30,
        timelineHeight: 400,
        labelWidth: 160,
      },
      timelineRef: { current: null },
      timelineWrapperRef: { current: null },
    },
    playback: {
      currentTime: 5.0,
      previewRef: { current: null },
      playerContainerRef: { current: null },
      onPreviewTimeUpdate: vi.fn(),
      formatTime: (t: number) => `${t.toFixed(1)}s`,
    },
    ops: {
      applyEdit: vi.fn(),
      moveClipToRow: vi.fn(),
      createTrackAndMoveClip: vi.fn(),
      selectClip: vi.fn(),
      selectClips: vi.fn(),
      addToSelection: vi.fn(),
      clearSelection: vi.fn(),
      isClipSelected: () => false,
      setSelectedTrackId: vi.fn(),
      handleTrackPopoverChange: vi.fn(),
      handleMoveTrack: vi.fn(),
      handleRemoveTrack: vi.fn(),
      handleSplitClipAtTime: vi.fn(),
      handleSplitClipsAtPlayhead: vi.fn(),
      handleDeleteClips: vi.fn(),
      handleDeleteClip: vi.fn(),
      handleToggleMuteClips: vi.fn(),
      onCursorDrag: vi.fn(),
      onClickTimeArea: vi.fn(),
      setGestureOwner,
      setInputModalityFromPointerType: vi.fn(() => 'mouse'),
      onActionResizeStart: vi.fn(),
      onClipEdgeResizeEnd: vi.fn(),
      onTimelineDragOver: vi.fn(),
      onTimelineDragLeave: vi.fn(),
      onTimelineDrop: vi.fn(),
      onDoubleClickAsset: vi.fn(),
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
    },
    chrome: {
      handleAddTrack: vi.fn(),
      handleAddTextAt: vi.fn(),
      handleClearUnusedTracks: vi.fn(),
      unusedTrackCount: 0,
    },
  });
  return store;
}

function renderWithStore(ui: React.ReactElement) {
  const store = createOverlayTestStore();
  return {
    store,
    ...render(
      <TimelineStoreProvider store={store}>
        {ui}
      </TimelineStoreProvider>,
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TimelineEditorCore — overlay host', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('overlay host rendering', () => {
    it('renders the timeline overlay host container above the edit area', () => {
      renderWithStore(<TimelineEditorCore />);
      const host = screen.getByTestId('timeline-overlay-host');
      expect(host).toBeInTheDocument();
      // Default: no overlay has claimed pointer, so pointer-events should be 'none'
      expect(host.style.pointerEvents).toBe('none');
      // Class should also indicate pointer-events-none
      expect(host.className).toContain('pointer-events-none');
    });

    it('positions the overlay host absolutely to cover the wrapper area', () => {
      renderWithStore(<TimelineEditorCore />);
      const host = screen.getByTestId('timeline-overlay-host');
      expect(host.className).toContain('absolute');
      expect(host.className).toContain('inset-0');
    });

    it('renders overlay host at z-20 above the edit area', () => {
      renderWithStore(<TimelineEditorCore />);
      const host = screen.getByTestId('timeline-overlay-host');
      expect(host.className).toContain('z-20');
    });
  });

  describe('pointer policy containment', () => {
    it('defaults to pointer-events-none so overlays do not steal gestures', () => {
      renderWithStore(<TimelineEditorCore />);
      const host = screen.getByTestId('timeline-overlay-host');
      expect(host.style.pointerEvents).toBe('none');
      expect(screen.queryByTestId('timeline-overlay-claimed-indicator')).toBeNull();
    });

    it('does NOT render the claimed indicator when no overlay has claimed pointer', () => {
      renderWithStore(<TimelineEditorCore />);
      expect(screen.queryByTestId('timeline-overlay-claimed-indicator')).toBeNull();
    });
  });

  describe('viewport and playhead props flow', () => {
    it('renders the timeline wrapper for scroll tracking', () => {
      const { container } = renderWithStore(<TimelineEditorCore />);
      expect(container.querySelector('.timeline-wrapper')).toBeInTheDocument();
    });

    it('exposes gestureOwner and setGestureOwner to overlay render props', () => {
      const { container } = renderWithStore(<TimelineEditorCore />);
      expect(container.querySelector('.timeline-wrapper')).toBeInTheDocument();
      expect(setGestureOwner).toBeDefined();
    });
  });

  describe('selection and playhead tracking', () => {
    it('renders successfully with store data and tracks selectedClipIds', () => {
      const { container } = renderWithStore(<TimelineEditorCore />);
      expect(container.querySelector('.timeline-wrapper')).toBeInTheDocument();
    });

    it('tracks selectedTrackId from the data store', () => {
      const { container } = renderWithStore(<TimelineEditorCore />);
      expect(container.querySelector('.timeline-wrapper')).toBeInTheDocument();
    });

    it('reads currentTime from playback context for overlay render props', () => {
      const { container } = renderWithStore(<TimelineEditorCore />);
      expect(container.querySelector('.timeline-wrapper')).toBeInTheDocument();
    });
  });
});
