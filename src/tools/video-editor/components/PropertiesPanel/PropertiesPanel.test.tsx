// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PropertiesPanel } from '@/tools/video-editor/components/PropertiesPanel/PropertiesPanel';
import { VideoEditorAssetPanelSurface } from '@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface';

const useTimelineEditorDataMock = vi.fn();
const useTimelineEditorOpsMock = vi.fn();
const useVideoEditorRenderContextMock = vi.fn();
const useVideoEditorInspectorSectionsMock = vi.fn();
const useVideoEditorAssetPanelsMock = vi.fn();

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineEditorData: () => useTimelineEditorDataMock(),
  useTimelineEditorOps: () => useTimelineEditorOpsMock(),
}));

vi.mock('@/tools/video-editor/runtime/useVideoEditorRenderContext', () => ({
  useVideoEditorRenderContext: () => useVideoEditorRenderContextMock(),
  useVideoEditorInspectorSections: (placement?: 'before-default' | 'after-default') => useVideoEditorInspectorSectionsMock(placement),
  useVideoEditorAssetPanels: () => useVideoEditorAssetPanelsMock(),
}));

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
  return {
    id,
    placement: id.startsWith('before') ? 'before-default' as const : 'after-default' as const,
    render: () => <div data-testid={`section-${id}`}>{id}</div>,
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
    useVideoEditorInspectorSectionsMock.mockImplementation((placement?: 'before-default' | 'after-default') => {
      if (placement === 'before-default') {
        return [createInspectorSection('before-alpha'), createInspectorSection('before-beta')];
      }

      if (placement === 'after-default') {
        return [createInspectorSection('after-alpha')];
      }

      return [];
    });
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
