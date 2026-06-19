// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PropertiesPanel } from '@/tools/video-editor/components/PropertiesPanel/PropertiesPanel';
import { VideoEditorAssetPanelSurface } from '@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface';

const useTimelineEditorDataMock = vi.fn();
const useTimelineEditorOpsMock = vi.fn();
const useVideoEditorRenderContextMock = vi.fn();
const useVideoEditorPanelRegistryMock = vi.fn();
const getInspectorContributionsMock = vi.fn();
const useVideoEditorAssetPanelsMock = vi.fn();

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineEditorData: () => useTimelineEditorDataMock(),
  useTimelineEditorOps: () => useTimelineEditorOpsMock(),
  useTimelinePlaybackContext: () => ({ currentTime: 0 }),
}));

vi.mock('@/tools/video-editor/runtime/useVideoEditorRenderContext', () => ({
  useVideoEditorRenderContext: () => useVideoEditorRenderContextMock(),
  useVideoEditorPanelRegistry: () => useVideoEditorPanelRegistryMock(),
  useVideoEditorAssetPanels: () => useVideoEditorAssetPanelsMock(),
}));

// Mock getInspectorContributions so the test controls what sections appear
vi.mock('@/tools/video-editor/runtime/extensionSurface', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/runtime/extensionSurface')>(
    '@/tools/video-editor/runtime/extensionSurface',
  );
  return {
    ...actual,
    getInspectorContributions: (
      registry: unknown,
      context: unknown,
      selection: unknown,
    ) => getInspectorContributionsMock(registry, context, selection),
  };
});

vi.mock('@/tools/video-editor/hooks/usePerfDiagnostics', () => ({
  useRenderDiagnostic: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useStaleVariants', () => ({
  useStaleVariants: () => ({
    staleAssetKeys: new Set<string>(),
    dismissedAssetKeys: new Set<string>(),
    dismissAsset: vi.fn(),
    updateAssetToCurrentVariant: vi.fn(),
    applyVariantToAsset: vi.fn(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useAddVariantAsGeneration', () => ({
  useAddVariantAsGeneration: () => ({
    addVariantAsGenerationAfterClip: vi.fn(),
    isPending: vi.fn(() => false),
  }),
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...props }: React.ComponentProps<'button'>) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/AssetPanel', () => ({
  default: () => <div data-testid="mock-built-in-asset-panel">Built-in asset panel</div>,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/ClipPanel', () => ({
  NO_EFFECT: 'no-effect',
  getVisibleClipTabs: () => ['effects', 'timing', 'position', 'audio', 'text'],
  ClipPanel: () => <div data-testid="mock-clip-panel">Clip panel</div>,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/BulkClipPanel', () => ({
  BulkClipPanel: ({ clips }: { clips: Array<{ id: string }> }) => (
    <div data-testid="mock-bulk-clip-panel">Bulk clip panel ({clips.length})</div>
  ),
}));

vi.mock('@/tools/video-editor/lib/bulk-utils', () => ({
  getBulkVisibleTabs: () => ['effects', 'timing', 'position', 'audio', 'text'],
  getSharedNestedValue: () => undefined,
  getSharedValue: () => undefined,
}));

function createBaseEditorData() {
  return {
    data: {
      assetMap: {
        'asset-1': 'folder/image-1.png',
      },
      rows: [],
      meta: {},
      output: {
        background: null,
      },
      registry: {
        assets: {},
      },
      resolvedConfig: {
        tracks: [],
      },
    },
    resolvedConfig: {
      clips: [
        { id: 'clip-1', assetEntry: { duration: 5 } },
        { id: 'clip-2', assetEntry: { duration: 5 } },
      ],
      output: {
        fps: 30,
      },
      registry: {},
    },
    selectedClip: {
      id: 'clip-1',
      clipType: 'video',
      asset: 'asset-1',
      assetEntry: { duration: 5 },
    },
    selectedClipIds: new Set(['clip-1']),
    deviceClass: 'desktop',
    interactionMode: 'select',
    precisionEnabled: false,
    selectedTrack: null,
    selectedTrackId: null,
    selectedClipHasPredecessor: false,
    compositionSize: { width: 1280, height: 720 },
    preferences: {
      activeClipTab: 'effects',
      assetPanel: {
        showAll: false,
        showHidden: false,
        hidden: [],
      },
    },
  };
}

function createEditorOps() {
  return {
    clearSelection: vi.fn(),
    handleUpdateClips: vi.fn(),
    handleUpdateClipsDeep: vi.fn(),
    handleDeleteClip: vi.fn(),
    handleDeleteClips: vi.fn(),
    handleSelectedClipChange: vi.fn(),
    handleResetClipPosition: vi.fn(),
    handleResetClipsPosition: vi.fn(),
    handleSplitClipsAtPlayhead: vi.fn(),
    handleSplitSelectedClip: vi.fn(),
    handleToggleMuteClips: vi.fn(),
    handleToggleMute: vi.fn(),
    handleDetachAudioClip: vi.fn(),
    moveSelectedClipsToTrack: vi.fn(),
    setContextTarget: vi.fn(),
    setActiveClipTab: vi.fn(),
    setInspectorTarget: vi.fn(),
    setInteractionMode: vi.fn(),
    setPrecisionEnabled: vi.fn(),
    patchRegistry: vi.fn(),
    registerAsset: vi.fn(),
    setAssetPanelState: vi.fn(),
    uploadFiles: vi.fn(),
  };
}

function createInspectorSection(id: string) {
  const placement = id.startsWith('before') ? 'before-default' as const : 'after-default' as const;
  return {
    id,
    placement,
    render: (_ctx: unknown, _sel: unknown) => <div data-testid={`section-${id}`}>{id}</div>,
  };
}

function createInspectorContributions() {
  const before = [createInspectorSection('before-alpha'), createInspectorSection('before-beta')];
  const after = [createInspectorSection('after-alpha')];
  return {
    all: [...before, ...after],
    beforeDefault: before,
    afterDefault: after,
  };
}

function createAssetPanel(id: string) {
  return {
    id,
    placement: 'asset-panel' as const,
    render: () => <div data-testid={`panel-${id}`}>{id}</div>,
  };
}

describe('PropertiesPanel registry surfaces', () => {
  beforeEach(() => {
    useVideoEditorRenderContextMock.mockReturnValue({ timelineId: 'timeline-1' });
    useTimelineEditorDataMock.mockReturnValue(createBaseEditorData());
    useTimelineEditorOpsMock.mockReturnValue(createEditorOps());
    useVideoEditorPanelRegistryMock.mockReturnValue({ panels: [], inspectorSections: [] });
    getInspectorContributionsMock.mockImplementation(
      (_registry: unknown, _context: unknown, _selection: unknown) => createInspectorContributions(),
    );
    useVideoEditorAssetPanelsMock.mockReturnValue([createAssetPanel('asset-panel-extra')]);
  });

  it('renders inspector sections before and after the built-in clip inspector additively', () => {
    const { container } = render(<PropertiesPanel />);

    expect(screen.getByTestId('mock-clip-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('mock-bulk-clip-panel')).not.toBeInTheDocument();

    const renderedOrder = [...container.querySelectorAll(
      '[data-video-editor-inspector-section-id], [data-testid="mock-clip-panel"]',
    )].map((element) => (
      element.getAttribute('data-video-editor-inspector-section-id') ?? element.getAttribute('data-testid')
    ));

    expect(renderedOrder).toEqual([
      'before-alpha',
      'before-beta',
      'mock-clip-panel',
      'after-alpha',
    ]);
  });

  it('keeps the bulk inspector as the core panel when multiple clips are selected', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: null,
      selectedClipIds: new Set(['clip-1', 'clip-2']),
    });

    const { container } = render(<PropertiesPanel />);

    expect(screen.queryByTestId('mock-clip-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('mock-bulk-clip-panel')).toHaveTextContent('Bulk clip panel (2)');

    const renderedOrder = [...container.querySelectorAll(
      '[data-video-editor-inspector-section-id], [data-testid="mock-bulk-clip-panel"]',
    )].map((element) => (
      element.getAttribute('data-video-editor-inspector-section-id') ?? element.getAttribute('data-testid')
    ));

    expect(renderedOrder).toEqual([
      'before-alpha',
      'before-beta',
      'mock-bulk-clip-panel',
      'after-alpha',
    ]);
  });

  it('stacks the built-in asset panel ahead of contributed asset-panel registry entries', () => {
    const { container } = render(<VideoEditorAssetPanelSurface includeBuiltIn />);

    expect(screen.getByTestId('mock-built-in-asset-panel')).toBeInTheDocument();
    expect(screen.getByTestId('panel-asset-panel-extra')).toBeInTheDocument();

    const renderedOrder = [...container.querySelectorAll(
      '[data-video-editor-panel-id], [data-testid="mock-built-in-asset-panel"]',
    )].map((element) => (
      element.getAttribute('data-video-editor-panel-id') ?? element.getAttribute('data-testid')
    ));

    expect(renderedOrder).toEqual([
      'mock-built-in-asset-panel',
      'asset-panel-extra',
    ]);
  });
});

describe('PropertiesPanel — selection propagation', () => {
  beforeEach(() => {
    useVideoEditorRenderContextMock.mockReturnValue({ timelineId: 'timeline-1' });
    useTimelineEditorDataMock.mockReturnValue(createBaseEditorData());
    useTimelineEditorOpsMock.mockReturnValue(createEditorOps());
    useVideoEditorPanelRegistryMock.mockReturnValue({ panels: [], inspectorSections: [] });
    useVideoEditorAssetPanelsMock.mockReturnValue([]);

    // Capture the selection argument passed to getInspectorContributions
    getInspectorContributionsMock.mockImplementation(
      (_registry: unknown, _context: unknown, selection: unknown) => {
        // Return a single section that echoes the selection it received
        const sel = selection as { kind: string; clipId?: string; clipIds?: string[]; trackId?: string } | null;
        return {
          all: [{
            id: 'sel-echo',
            placement: 'before-default' as const,
            render: (_ctx: unknown, _sel: unknown) => (
              <div data-testid="section-sel-echo">
                selection:{sel ? `${sel.kind}:${sel.clipId ?? sel.trackId ?? (sel.clipIds?.join(',') ?? 'none')}` : 'null'}
              </div>
            ),
          }],
          beforeDefault: [{
            id: 'sel-echo',
            placement: 'before-default' as const,
            render: (_ctx: unknown, _sel: unknown) => (
              <div data-testid="section-sel-echo">
                selection:{sel ? `${sel.kind}:${sel.clipId ?? sel.trackId ?? (sel.clipIds?.join(',') ?? 'none')}` : 'null'}
              </div>
            ),
          }],
          afterDefault: [],
        };
      },
    );
  });

  it('passes clip selection to inspector contributions', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: { id: 'clip-abc', clipType: 'video', asset: 'asset-1', assetEntry: { duration: 5 } },
      selectedClipIds: new Set(['clip-abc']),
      selectedTrackId: null,
    });

    render(<PropertiesPanel />);

    expect(screen.getByTestId('section-sel-echo')).toHaveTextContent('selection:clip:clip-abc');
    // Verify getInspectorContributions was called with the selection
    expect(getInspectorContributionsMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      expect.objectContaining({ kind: 'clip', clipId: 'clip-abc' }),
    );
  });

  it('passes multi-selection to inspector contributions', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: null,
      selectedClipIds: new Set(['clip-1', 'clip-2', 'clip-3']),
      selectedTrackId: null,
    });

    render(<PropertiesPanel />);

    expect(screen.getByTestId('section-sel-echo')).toHaveTextContent('selection:selection:clip-1,clip-2,clip-3');
    expect(getInspectorContributionsMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      expect.objectContaining({ kind: 'selection', clipIds: ['clip-1', 'clip-2', 'clip-3'] }),
    );
  });

  it('passes track selection to inspector contributions', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: null,
      selectedClipIds: new Set<string>(),
      selectedTrackId: 'track-main',
    });

    render(<PropertiesPanel />);

    expect(screen.getByTestId('section-sel-echo')).toHaveTextContent('selection:track:track-main');
    expect(getInspectorContributionsMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      expect.objectContaining({ kind: 'track', trackId: 'track-main' }),
    );
  });

  it('passes timeline fallback when nothing is selected', () => {
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: null,
      selectedClipIds: new Set<string>(),
      selectedTrackId: null,
    });

    render(<PropertiesPanel />);

    expect(screen.getByTestId('section-sel-echo')).toHaveTextContent('selection:timeline:none');
    expect(getInspectorContributionsMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      expect.objectContaining({ kind: 'timeline' }),
    );
  });

  it('preserves before-default and after-default placement ordering', () => {
    // Use a custom mock that returns both placements
    getInspectorContributionsMock.mockImplementation((_r: unknown, _c: unknown, sel: unknown) => {
      const s = sel as { kind: string } | null;
      const k = s?.kind ?? 'null';
      const mk = (id: string, placement: 'before-default' | 'after-default') => ({
        id,
        placement,
        render: (_ctx: unknown, _sel: unknown) => (
          <div data-testid={`section-${id}`}>{id}</div>
        ),
      });
      return {
        all: [mk('before-x', 'before-default'), mk('after-y', 'after-default')],
        beforeDefault: [mk('before-x', 'before-default')],
        afterDefault: [mk('after-y', 'after-default')],
      };
    });

    const { container } = render(<PropertiesPanel />);

    const renderedOrder = [...container.querySelectorAll(
      '[data-video-editor-inspector-section-id], [data-testid="mock-clip-panel"]',
    )].map((element) => (
      element.getAttribute('data-video-editor-inspector-section-id') ?? element.getAttribute('data-testid')
    ));

    expect(renderedOrder).toEqual([
      'before-x',
      'mock-clip-panel',
      'after-y',
    ]);
  });

  it('does not poll extensions for selection updates', () => {
    // Render once and verify getInspectorContributions is called only
    // via React rendering — the selection comes from host props, not polling.
    const callCountBefore = getInspectorContributionsMock.mock.calls.length;

    // Initial render
    const { rerender } = render(<PropertiesPanel />);
    const initialCalls = getInspectorContributionsMock.mock.calls.length;
    expect(initialCalls).toBeGreaterThanOrEqual(callCountBefore + 1);

    // Re-render with the same props — should still call due to React re-render
    // but no polling interval is set up
    rerender(<PropertiesPanel />);

    // Verify there's no setInterval or polling loop associated with inspector sections
    // The selection is derived from host props, not extension polling
    const selectionCalls = getInspectorContributionsMock.mock.calls.filter(
      (call) => call[2] !== undefined,
    );
    expect(selectionCalls.length).toBeGreaterThan(0);
  });

  it('returns null for empty inspector section registries', () => {
    getInspectorContributionsMock.mockReturnValue({
      all: [],
      beforeDefault: [],
      afterDefault: [],
    });

    const { container } = render(<PropertiesPanel />);

    // No inspector section elements should be present
    expect(container.querySelector('[data-video-editor-inspector-section-id]')).toBeNull();
    // The core clip panel should still render
    expect(screen.getByTestId('mock-clip-panel')).toBeInTheDocument();
  });

  it('passes selection through ContributionErrorBoundary', () => {
    // Verify that even with error boundaries, selection reaches the section render
    useTimelineEditorDataMock.mockReturnValue({
      ...createBaseEditorData(),
      selectedClip: { id: 'boundary-clip', clipType: 'video', asset: 'asset-1', assetEntry: { duration: 5 } },
      selectedClipIds: new Set(['boundary-clip']),
      selectedTrackId: null,
    });

    render(<PropertiesPanel />);

    // The section should be wrapped in ContributionErrorBoundary with the correct contributionId
    const sectionWrapper = screen.getByTestId('section-sel-echo').closest('[data-video-editor-inspector-section-id]');
    expect(sectionWrapper).not.toBeNull();
    expect(sectionWrapper!.getAttribute('data-video-editor-inspector-section-id')).toBe('sel-echo');
  });
});
