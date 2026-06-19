import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import type { FC, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { defineExtension } from '@reigh/editor-sdk';
import { useAddToVideoEditor } from '@/domains/media-lightbox/hooks/useAddToVideoEditor';
import {
  ADD_GENERATION_QUERY_PARAM,
  readPendingAdds,
} from '@/domains/media-lightbox/hooks/addToVideoEditorConstants';
import { AgentChatProvider, useAgentChatBridge } from '@/shared/contexts/AgentChatContext';
import {
  __getSelectionStateForTests,
  editorReplaceTimelineSelection,
  systemResetSelectionForProjectChange,
  userSelectGalleryItem,
} from '@/shared/state/selectionStore';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import { buildVideoEditorLightboxMedia, VideoEditorProvider } from '@/tools/video-editor/contexts/VideoEditorProvider';
import type { EffectRegistryRecord } from '@/tools/video-editor/effects/registry/types';
import { useEffectRegistryContext } from '@/tools/video-editor/effects/registry/EffectRegistryContext';
import {
  INTERNAL_GESTURE_TIMELINE_MUTATIONS,
  PUBLIC_TIMELINE_COMMAND_NAMES,
  PUBLIC_TIMELINE_COMMAND_SCOPE,
  isPublicTimelineCommandName,
  useTimelineCommands,
  useTimelineCommandsSafe,
} from '@/tools/video-editor/hooks/useTimelineCommands';
import {
  createTimelineStore,
  TimelineStoreProvider,
  useTimelineAvailabilityState,
  useTimelineChromeContext,
  useTimelineEditorData,
  useTimelineEditorOps,
  useTimelinePlaybackContext,
} from '@/tools/video-editor/hooks/timelineStore';
import {
  shouldAllowTouchClipDrag,
  shouldAllowTouchMarquee,
  shouldExpandTouchTrimHandles,
  shouldPreserveTouchSelectionForMove,
  shouldToggleTouchSelection,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import { configToRows, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { VIDEO_EDITOR_HOST_PORT_NAMES } from '@/tools/video-editor/runtime/ports';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import { createVideoEditorEffectCatalog } from '@/tools/video-editor/lib/effect-catalog';

const navigateMock = vi.fn();
const useEffectsMock = vi.fn();
const useResolvedEffectCatalogMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

const mocks = {
  setInputModality: vi.fn(),
  setInputModalityFromPointerType: vi.fn(() => 'touch'),
  setInteractionMode: vi.fn(),
  setGestureOwner: vi.fn(),
  setPrecisionEnabled: vi.fn(),
  setContextTarget: vi.fn(),
  setInspectorTarget: vi.fn(),
  selectClip: vi.fn(),
  selectClips: vi.fn(),
};

vi.mock('@/tools/video-editor/hooks/useEffects', () => ({
  useEffects: (...args: unknown[]) => useEffectsMock(...args),
}));

vi.mock('@/tools/video-editor/hooks/useEffectRegistry', () => ({
  useEffectRegistry: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useEffectResources', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/tools/video-editor/hooks/useEffectResources')>();
  return {
    ...actual,
    EffectCatalogProvider: ({ children }: { children: any }) => children,
    useResolvedEffectCatalog: (...args: unknown[]) => useResolvedEffectCatalogMock(...args),
  };
});

vi.mock('@/tools/video-editor/hooks/useTimelineClipsForAttachments', () => ({
  useTimelineClipsForAttachments: () => [
    {
      clipId: 'clip-1',
      assetKey: 'asset-1',
      url: 'https://example.com/image.png',
      mediaType: 'image',
      isTimelineBacked: true,
    },
  ],
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => ({
    shots: [],
    isLoading: false,
    error: null,
    refetchShots: vi.fn(),
    allImagesCount: 0,
    noShotImagesCount: 0,
  }),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: () => ({
    settings: {
      lastTimelineId: 'timeline-staged',
    },
  }),
}));

vi.mock('@/tools/travel-between-images/hooks/video/useShotFinalVideos', () => ({
  useShotFinalVideos: () => ({
    finalVideoMap: new Map(),
    isLoading: false,
  }),
}));

vi.mock('@/tools/video-editor/hooks/useTimelineState', () => ({
  useTimelineState: () => {
    const editor = {
      data: null,
      resolvedConfig: { registry: {} },
      deviceClass: 'tablet',
      inputModality: 'mouse',
      interactionMode: 'select',
      gestureOwner: 'timeline',
      precisionEnabled: false,
      contextTarget: { kind: 'timeline' },
      inspectorTarget: { kind: 'clip', clipId: 'clip-1' },
      interactionPolicy: {
        deviceClass: 'tablet',
        inputModality: 'mouse',
        interactionMode: 'select',
        gestureOwner: 'timeline',
        precisionEnabled: false,
        contextTarget: { kind: 'timeline' },
        inspectorTarget: { kind: 'clip', clipId: 'clip-1' },
      },
      selectedClipId: 'clip-1',
      selectedClipIds: ['clip-1'],
      selectedClipIdsRef: { current: ['clip-1'] },
      additiveSelectionRef: { current: false },
      selectedTrackId: 'track-1',
      primaryClipId: 'clip-1',
      selectedClip: null,
      selectedTrack: null,
      selectedClipHasPredecessor: false,
      compositionSize: { width: 1920, height: 1080 },
      trackScaleMap: {},
      scale: 1,
      scaleWidth: 1,
      isLoading: false,
      dataRef: { current: null },
      pendingOpsRef: { current: [] },
      interactionStateRef: { current: { drag: false, resize: false, listeners: new Set() } },
      coordinator: null,
      indicatorRef: { current: null },
      editAreaRef: { current: null },
      preferences: {
        activeClipTab: 'style',
        assetPanel: { isOpen: true },
      },
      timelineRef: { current: null },
      timelineWrapperRef: { current: null },
      setInputModality: mocks.setInputModality,
      setInputModalityFromPointerType: mocks.setInputModalityFromPointerType,
      setInteractionMode: mocks.setInteractionMode,
      setGestureOwner: mocks.setGestureOwner,
      setPrecisionEnabled: mocks.setPrecisionEnabled,
      setContextTarget: mocks.setContextTarget,
      setInspectorTarget: mocks.setInspectorTarget,
      isClipSelected: vi.fn(() => true),
      selectClip: mocks.selectClip,
      selectClips: mocks.selectClips,
      addToSelection: vi.fn(),
      clearSelection: vi.fn(),
      setSelectedTrackId: vi.fn(),
      setActiveClipTab: vi.fn(),
      setAssetPanelState: vi.fn(),
      registerGenerationAsset: vi.fn(),
      onCursorDrag: vi.fn(),
      onClickTimeArea: vi.fn(),
      onActionResizeStart: vi.fn(),
      onClipEdgeResizeEnd: vi.fn(),
      onOverlayChange: vi.fn(),
      onTimelineDragOver: vi.fn(),
      onTimelineDragLeave: vi.fn(),
      onTimelineDrop: vi.fn(),
      handleAssetDrop: vi.fn(),
      handleUpdateClips: vi.fn(),
      handleUpdateClipsDeep: vi.fn(),
      handleDeleteClips: vi.fn(),
      handleDeleteClip: vi.fn(),
      handleSelectedClipChange: vi.fn(),
      handleResetClipPosition: vi.fn(),
      handleResetClipsPosition: vi.fn(),
      handleSplitSelectedClip: vi.fn(),
      handleSplitClipAtTime: vi.fn(),
      handleSplitClipsAtPlayhead: vi.fn(),
      handleToggleMuteClips: vi.fn(),
      handleToggleMute: vi.fn(),
      handleDetachAudioClip: vi.fn(),
      handleTrackPopoverChange: vi.fn(),
      handleMoveTrack: vi.fn(),
      handleRemoveTrack: vi.fn(),
      moveSelectedClipToTrack: vi.fn(),
      moveSelectedClipsToTrack: vi.fn(),
      moveClipToRow: vi.fn(),
      createTrackAndMoveClip: vi.fn(),
      uploadFiles: vi.fn(),
      applyEdit: vi.fn(),
      patchRegistry: vi.fn(),
      unpatchRegistry: vi.fn(),
      registerAsset: vi.fn(),
    };
    const chrome = {
      timelineName: 'Timeline',
      saveStatus: 'saved' as const,
      isConflictExhausted: false,
      renderStatus: 'idle' as const,
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
    };
    const playback = {
      currentTime: 12.5,
      previewRef: { current: null },
      playerContainerRef: { current: null },
      onPreviewTimeUpdate: vi.fn(),
      formatTime: vi.fn(() => '0:12'),
    };

    return {
      store: createTimelineStore({
        data: editor,
        ops: editor,
        chrome,
        playback,
      }),
      editor,
      chrome,
      playback,
    };
  },
}));

function Consumer() {
  const runtime = useVideoEditorRuntime();
  const editorData = useTimelineEditorData();
  const editorOps = useTimelineEditorOps();
  const chrome = useTimelineChromeContext();
  const playback = useTimelinePlaybackContext();
  const agentChatBridge = useAgentChatBridge();

  return (
    <div>
      <span>{editorData.selectedClipId}</span>
      <span>{editorData.deviceClass}</span>
      <span>{editorData.inputModality}</span>
      <span>{editorData.interactionMode}</span>
      <span>{editorData.gestureOwner}</span>
      <span>{editorData.contextTarget?.kind}</span>
      <span>{editorData.inspectorTarget?.kind}</span>
      <span>{editorData.interactionPolicy.deviceClass}</span>
      <span data-testid="interaction-policy">{JSON.stringify(editorData.interactionPolicy)}</span>
      <span>{String(editorData.interactionStateRef.current.drag)}</span>
      <span>{typeof editorData.additiveSelectionRef?.current}</span>
      <span>{typeof editorOps.selectClip}</span>
      <span>{typeof editorOps.selectClips}</span>
      <span>{chrome.saveStatus}</span>
      <span>{playback.currentTime}</span>
      <span data-testid="agent-chat-timeline-id">{agentChatBridge.timelineId}</span>
      <span data-testid="runtime-project-id">{runtime.project.projectId}</span>
      <span data-testid="runtime-user-id">{runtime.auth.userId}</span>
      <span data-testid="runtime-shots-count">{runtime.shots.shots?.length ?? 0}</span>
      <span data-testid="runtime-resolver-type">{typeof runtime.assetResolver.resolveAssetUrl}</span>
      <button
        type="button"
        onClick={() => {
          editorOps.setInputModality('touch');
          editorOps.setInputModalityFromPointerType('touch');
          editorOps.setInteractionMode('trim');
          editorOps.setGestureOwner('trim');
          editorOps.setPrecisionEnabled(true);
          editorOps.setContextTarget({ kind: 'clip', clipId: 'clip-1' });
          editorOps.setInspectorTarget({ kind: 'selection', clipIds: ['clip-1'] });
        }}
      >
        update interaction
      </button>
    </div>
  );
}

function buildCommandTimelineData(): TimelineData {
  const config = {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
  } as const;
  const rowData = configToRows(config);
  const resolvedConfig = {
    output: { ...config.output },
    tracks: config.tracks.map((track) => ({ ...track })),
    clips: config.clips.map((clip) => ({ ...clip, assetEntry: undefined })),
    registry: {},
  };

  return {
    config: {
      ...config,
      tracks: config.tracks.map((track) => ({ ...track })),
      clips: config.clips.map((clip) => ({ ...clip })),
    },
    configVersion: 1,
    registry: { assets: {} },
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: {},
    output: { ...config.output },
    tracks: config.tracks.map((track) => ({ ...track })),
    clipOrder: rowData.clipOrder,
    signature: 'signature',
    stableSignature: 'stable-signature',
  };
}

function buildDuplicateCommandTimelineData(): TimelineData {
  const config = {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-source',
        from: 0,
        to: 2,
        speed: 1,
        volume: 1,
      },
      {
        id: 'clip-2',
        at: 2,
        track: 'V1',
        clipType: 'hold',
        hold: 1,
      },
    ],
  } as const;
  const rowData = configToRows(config);
  const resolvedConfig = {
    output: { ...config.output },
    tracks: config.tracks.map((track) => ({ ...track })),
    clips: config.clips.map((clip) => ({ ...clip, assetEntry: undefined })),
    registry: {},
  };

  return {
    config: {
      ...config,
      tracks: config.tracks.map((track) => ({ ...track })),
      clips: config.clips.map((clip) => ({ ...clip })),
    },
    configVersion: 1,
    registry: {
      assets: {
        'asset-source': {
          file: 'https://example.com/source.mp4',
          type: 'video/mp4',
          duration: 2,
          generationId: 'generation-source',
        },
        'asset-dup': {
          file: 'https://example.com/dup.mp4',
          type: 'video/mp4',
          duration: 2,
          generationId: 'generation-dup',
        },
      },
    },
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: {},
    output: { ...config.output },
    tracks: config.tracks.map((track) => ({ ...track })),
    clipOrder: rowData.clipOrder,
    signature: 'signature-dup',
    stableSignature: 'stable-signature-dup',
  };
}

function buildCommandTestStore(overrides?: {
  applyEdit?: (...args: unknown[]) => void;
  registerAsset?: (...args: unknown[]) => Promise<unknown>;
  patchRegistry?: (...args: unknown[]) => void;
  unpatchRegistry?: (...args: unknown[]) => void;
  data?: TimelineData;
  mounted?: boolean;
}) {
  const baseStore = createTimelineStore();
  const current = overrides?.data ?? buildCommandTimelineData();
  const store = createTimelineStore({
    data: {
      ...baseStore.getState().data,
      data: current,
      resolvedConfig: current.resolvedConfig,
      selectedTrackId: 'V1',
      dataRef: { current },
      pendingOpsRef: { current: 0 },
    },
    ops: {
      ...baseStore.getState().ops,
      applyEdit: overrides?.applyEdit ?? vi.fn(),
      registerAsset: overrides?.registerAsset ?? vi.fn(async () => undefined),
      patchRegistry: overrides?.patchRegistry ?? vi.fn(),
      unpatchRegistry: overrides?.unpatchRegistry ?? vi.fn(),
    },
  });
  if (overrides?.mounted === false) {
    store.getState().setMounted(false);
  }
  return store;
}

const media = {
  id: 'generation-1',
  generation_id: 'generation-1',
  location: 'https://example.com/image.png',
  imageUrl: 'https://example.com/image.png',
  thumbUrl: 'https://example.com/image-thumb.png',
  type: 'image',
} as const;

const LifecycleComponent: FC<{ children: ReactNode }> = ({ children }) => children;
const LifecycleReplacementComponent: FC<{ children: ReactNode }> = ({ children }) => children;

function trustedEffectRecord(
  effectId: string,
  ownerExtensionId: string,
  dispose: () => void,
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `${ownerExtensionId}.effect`,
    component: LifecycleComponent,
    provenance: 'trusted-loader',
    ownerExtensionId,
    status: 'active',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    dispose,
  };
}

function AddToVideoEditorConsumer() {
  const { onClick, phase } = useAddToVideoEditor(media);
  const availability = useTimelineAvailabilityState();

  return (
    <div>
      <span data-testid="add-phase">{phase}</span>
      <span data-testid="timeline-mounted">{String(availability.mounted)}</span>
      <button type="button" onClick={onClick}>
        add to video editor
      </button>
    </div>
  );
}

describe('VideoEditorProvider', () => {
  beforeEach(() => {
    navigateMock.mockReset();
    systemResetSelectionForProjectChange();
    localStorage.clear();
    Object.values(mocks).forEach((mock) => mock.mockClear());
    useEffectsMock.mockReset();
    useEffectsMock.mockReturnValue({ data: [] });
    useResolvedEffectCatalogMock.mockReset();
    useResolvedEffectCatalogMock.mockReturnValue(createVideoEditorEffectCatalog());
  });

  it('builds fallback lightbox media for raw video assets without a generation id', () => {
    expect(buildVideoEditorLightboxMedia('asset-1', {
      file: 'folder/video.mp4',
      src: 'https://example.com/video.mp4',
      thumbnailUrl: 'https://example.com/video.jpg',
      type: 'video/mp4',
    })).toEqual(expect.objectContaining({
      id: 'asset-1',
      generation_id: 'asset-1',
      location: 'https://example.com/video.mp4',
      thumbUrl: 'https://example.com/video.jpg',
      type: 'video',
    }));
  });

  it('provides editor data, editor ops, chrome, and playback contexts together', () => {
    const provider: DataProvider = {
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AgentChatProvider>
            <VideoEditorProvider dataProvider={provider} projectId="project-1" timelineId="timeline-1" userId="user-1">
              <Consumer />
            </VideoEditorProvider>
          </AgentChatProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText('clip-1')).toBeInTheDocument();
    expect(screen.getAllByText('tablet')).toHaveLength(2);
    expect(screen.getByText('mouse')).toBeInTheDocument();
    expect(screen.getByText('select')).toBeInTheDocument();
    expect(screen.getAllByText('timeline')).toHaveLength(2);
    expect(screen.getByTestId('interaction-policy')).toHaveTextContent(JSON.stringify({
      deviceClass: 'tablet',
      inputModality: 'mouse',
      interactionMode: 'select',
      gestureOwner: 'timeline',
      precisionEnabled: false,
      contextTarget: { kind: 'timeline' },
      inspectorTarget: { kind: 'clip', clipId: 'clip-1' },
    }));
    expect(screen.getByText('false')).toBeInTheDocument();
    expect(screen.getByText('boolean')).toBeInTheDocument();
    expect(screen.getAllByText('function')).toHaveLength(3);
    expect(screen.getByText('saved')).toBeInTheDocument();
    expect(screen.getByText('12.5')).toBeInTheDocument();
    expect(screen.getByTestId('agent-chat-timeline-id')).toHaveTextContent('timeline-1');
    expect(screen.getByTestId('runtime-project-id')).toHaveTextContent('project-1');
    expect(screen.getByTestId('runtime-user-id')).toHaveTextContent('user-1');
    expect(screen.getByTestId('runtime-shots-count')).toHaveTextContent('0');
    expect(screen.getByTestId('runtime-resolver-type')).toHaveTextContent('function');

    fireEvent.click(screen.getByRole('button', { name: 'update interaction' }));

    expect(mocks.setInputModality).toHaveBeenCalledWith('touch');
    expect(mocks.setInputModalityFromPointerType).toHaveBeenCalledWith('touch');
    expect(mocks.setInteractionMode).toHaveBeenCalledWith('trim');
    expect(mocks.setGestureOwner).toHaveBeenCalledWith('trim');
    expect(mocks.setPrecisionEnabled).toHaveBeenCalledWith(true);
    expect(mocks.setContextTarget).toHaveBeenCalledWith({ kind: 'clip', clipId: 'clip-1' });
    expect(mocks.setInspectorTarget).toHaveBeenCalledWith({ kind: 'selection', clipIds: ['clip-1'] });
    expect(__getSelectionStateForTests().clipDataById.get('clip-1')).toEqual(expect.objectContaining({
      clipId: 'clip-1',
      url: 'https://example.com/image.png',
    }));
  });

  it('uses an injected effect catalog without enabling the legacy effect query', () => {
    const provider: DataProvider = {
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    const injectedCatalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'effect-1',
        type: 'effect',
        name: 'Standalone Fade',
        slug: 'standalone-fade',
        code: 'export default function Effect() { return null; }',
        category: 'entrance',
        description: 'Standalone effect',
        created_by: { is_you: true },
        is_public: false,
      }],
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AgentChatProvider>
            <VideoEditorProvider
              dataProvider={provider}
              timelineId="timeline-1"
              userId="user-1"
              effectCatalog={injectedCatalog}
            >
              <Consumer />
            </VideoEditorProvider>
          </AgentChatProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(useEffectsMock).toHaveBeenCalledWith('user-1', { enabled: false });
    expect(useResolvedEffectCatalogMock).toHaveBeenCalledWith('user-1', injectedCatalog);
  });

  it('cleans extension-owned effect records and command contributions on removal after HMR replacement', async () => {
    const provider: DataProvider = {
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    const extensionId = 'com.example.video-provider-lifecycle';
    const commandId = `${extensionId}.run`;
    const disposeOriginal = vi.fn();
    const disposeReplacement = vi.fn();
    let hmrHandle: { dispose(): void } | null = null;
    let latestEffectIds: readonly string[] = [];
    let latestCommandIds: readonly string[] = [];

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Video provider lifecycle extension',
        contributions: [
          {
            id: 'lifecycle.command' as never,
            kind: 'command',
            command: commandId,
            label: 'Run lifecycle command',
          },
        ],
      },
      activate(ctx) {
        return ctx.commands.registerCommand(commandId, vi.fn());
      },
    });

    function CaptureVideoProviderLifecycle() {
      const { registry, snapshot } = useEffectRegistryContext();
      const runtime = useVideoEditorRuntime();

      latestEffectIds = snapshot.records.map((record) => record.effectId);
      latestCommandIds = runtime.commandRegistry?.getSnapshot().commands.map((command) => command.commandId) ?? [];

      useEffect(() => {
        const originalHandle = registry.register(
          trustedEffectRecord('trusted-video-fx', extensionId, disposeOriginal),
        );
        hmrHandle = registry.updateRecord('trusted-video-fx', (current) => ({
          ...current,
          contributionId: `${extensionId}.effect.hmr`,
          component: LifecycleReplacementComponent,
        }), disposeReplacement);

        return () => {
          originalHandle.dispose();
          hmrHandle?.dispose();
        };
      }, [registry]);

      return null;
    }

    const props = {
      dataProvider: provider,
      projectId: 'project-1',
      timelineId: 'timeline-1',
      userId: 'user-1',
    };

    const { rerender } = render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AgentChatProvider>
            <VideoEditorProvider {...props} extensions={[extension]}>
              <CaptureVideoProviderLifecycle />
            </VideoEditorProvider>
          </AgentChatProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(latestEffectIds).toContain('trusted-video-fx');
      expect(latestCommandIds).toContain(commandId);
    });
    expect(disposeOriginal).toHaveBeenCalledTimes(1);
    expect(disposeReplacement).not.toHaveBeenCalled();

    rerender(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AgentChatProvider>
            <VideoEditorProvider {...props} extensions={[]}>
              <CaptureVideoProviderLifecycle />
            </VideoEditorProvider>
          </AgentChatProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(latestEffectIds).not.toContain('trusted-video-fx');
      expect(latestCommandIds).not.toContain(commandId);
    });
    expect(disposeOriginal).toHaveBeenCalledTimes(1);
    expect(disposeReplacement).toHaveBeenCalledTimes(1);

    hmrHandle?.dispose();
    hmrHandle?.dispose();
    expect(disposeReplacement).toHaveBeenCalledTimes(1);
  });

  it('lifts save status changes through the provider boundary', () => {
    const provider: DataProvider = {
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    const onSaveStatusChange = vi.fn();

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AgentChatProvider>
            <VideoEditorProvider
              dataProvider={provider}
              timelineId="timeline-1"
              userId="user-1"
              onSaveStatusChange={onSaveStatusChange}
            >
              <Consumer />
            </VideoEditorProvider>
          </AgentChatProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(onSaveStatusChange).toHaveBeenCalledWith('saved');
  });

  it('lets editor timeline replacement update selection while preserving gallery attachments', () => {
    userSelectGalleryItem({
      id: 'gallery-1',
      url: 'https://example.com/gallery.png',
      type: 'image/png',
      generationId: 'gen-gallery',
    }, { additive: false });

    editorReplaceTimelineSelection(['clip-1']);

    const selectionState = __getSelectionStateForTests();
    expect(selectionState.timeline.selectedClipIds).toEqual(new Set(['clip-1']));
    expect(selectionState.clipDataById.get('clip-1')).toBeUndefined();
    expect(selectionState.gallery.selectedGalleryIds).toEqual(new Set(['gallery-1']));
  });

  it('matches the touch interaction decision table for drag, marquee, trim, and selection routing', () => {
    expect({
      phoneTouchDragInSelect: shouldAllowTouchClipDrag('phone', 'touch', 'select'),
      phoneTouchDragInMove: shouldAllowTouchClipDrag('phone', 'touch', 'move'),
      tabletTouchMarqueeInSelect: shouldAllowTouchMarquee('tablet', 'touch', 'select'),
      tabletTouchMarqueeInMove: shouldAllowTouchMarquee('tablet', 'touch', 'move'),
      tabletMouseMarqueeInSelect: shouldAllowTouchMarquee('tablet', 'mouse', 'select'),
      phoneTouchTrimHandlesInTrim: shouldExpandTouchTrimHandles('phone', 'touch', 'trim'),
      phoneTouchTrimHandlesInSelect: shouldExpandTouchTrimHandles('phone', 'touch', 'select'),
      phoneTouchToggleSelectionInSelect: shouldToggleTouchSelection('phone', 'touch', 'select'),
      tabletTouchPreserveSelectionInMove: shouldPreserveTouchSelectionForMove('tablet', 'touch', 'move'),
      tabletMousePreserveSelectionInMove: shouldPreserveTouchSelectionForMove('tablet', 'mouse', 'move'),
    }).toEqual({
      phoneTouchDragInSelect: false,
      phoneTouchDragInMove: true,
      tabletTouchMarqueeInSelect: true,
      tabletTouchMarqueeInMove: false,
      tabletMouseMarqueeInSelect: true,
      phoneTouchTrimHandlesInTrim: true,
      phoneTouchTrimHandlesInSelect: false,
      phoneTouchToggleSelectionInSelect: true,
      tabletTouchPreserveSelectionInMove: true,
      tabletMousePreserveSelectionInMove: false,
    });
  });

  it('keeps the mounted-vs-staged add boundary when a store provider exists but the editor is not mounted', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TimelineStoreProvider store={createTimelineStore()}>
            <AddToVideoEditorConsumer />
          </TimelineStoreProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('timeline-mounted')).toHaveTextContent('false');

    fireEvent.click(screen.getByRole('button', { name: 'add to video editor' }));

    expect(screen.getByTestId('add-phase')).toHaveTextContent('staged');
    expect(readPendingAdds()).toEqual(['generation-1']);
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('drops immediately when the mounted timeline store is available', () => {
    const current = buildCommandTimelineData();
    const patchRegistry = vi.fn((assetId: string, entry: Record<string, unknown>) => {
      current.registry.assets[assetId] = entry as never;
    });
    const registerAsset = vi.fn(async () => undefined);
    const applyEdit = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    const store = buildCommandTestStore({
      data: current,
      patchRegistry,
      registerAsset,
      applyEdit,
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TimelineStoreProvider store={store}>
            <AddToVideoEditorConsumer />
          </TimelineStoreProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('timeline-mounted')).toHaveTextContent('true');

    fireEvent.click(screen.getByRole('button', { name: 'add to video editor' }));

    expect(patchRegistry).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        generationId: 'generation-1',
        file: 'https://example.com/image.png',
        type: 'image/png',
      }),
      'https://example.com/image.png',
    );
    expect(registerAsset).toHaveBeenCalledTimes(1);
    expect(applyEdit).toHaveBeenCalledTimes(1);
    const insertedAssetId = patchRegistry.mock.calls[0]?.[0] as string;
    const mutation = applyEdit.mock.calls[0]?.[0] as {
      type: string;
      rows: Array<{ actions: Array<{ start: number; end: number }> }>;
      metaUpdates: Record<string, { asset: string }>;
    };
    expect(mutation.type).toBe('rows');
    expect(mutation.rows[0]?.actions.at(-1)).toEqual(expect.objectContaining({
      start: 2,
      end: 7,
    }));
    expect(Object.values(mutation.metaUpdates)).toContainEqual(expect.objectContaining({
      asset: insertedAssetId,
    }));
    expect(readPendingAdds()).toEqual([]);
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('navigates on the second staged click when the editor is not mounted', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AddToVideoEditorConsumer />
        </QueryClientProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'add to video editor' }));
    fireEvent.click(screen.getByRole('button', { name: 'add to video editor' }));

    expect(readPendingAdds()).toEqual(['generation-1']);
    expect(navigateMock).toHaveBeenCalledWith(
      `/tools/video-editor?timeline=timeline-staged&${ADD_GENERATION_QUERY_PARAM}=generation-1`,
    );
  });

  it('keeps staged add-to-editor behavior when a timeline provider exists but the mounted store is unavailable', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    const store = buildCommandTestStore({ mounted: false });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TimelineStoreProvider store={store}>
            <AddToVideoEditorConsumer />
          </TimelineStoreProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('timeline-mounted')).toHaveTextContent('false');

    fireEvent.click(screen.getByRole('button', { name: 'add to video editor' }));

    expect(readPendingAdds()).toEqual(['generation-1']);
    expect(screen.getByTestId('add-phase')).toHaveTextContent('staged');
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('exposes the mounted timeline command facade and keeps the safe hook nullable outside a mounted editor', () => {
    const store = buildCommandTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const outside = renderHook(() => useTimelineCommandsSafe());
    expect(outside.result.current).toBeNull();

    const inside = renderHook(() => ({
      commands: useTimelineCommands(),
      safeCommands: useTimelineCommandsSafe(),
    }), { wrapper });

    const commandNames = Object.keys(inside.result.current.commands).sort();
    expect(commandNames).toEqual([...PUBLIC_TIMELINE_COMMAND_NAMES].sort());
    expect(commandNames.every(isPublicTimelineCommandName)).toBe(true);
    expect(PUBLIC_TIMELINE_COMMAND_SCOPE).toBe('non-gesture');
    expect(inside.result.current.safeCommands).not.toBeNull();
  });

  it('returns structured public-command failures for missing assets', () => {
    const store = buildCommandTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const { result } = renderHook(() => useTimelineCommands(), { wrapper });
    const response = result.current.addClip({ assetId: 'missing-asset', time: 0 });

    expect(response).toEqual({
      ok: false,
      error: {
        code: 'asset_not_found',
        message: "Asset 'missing-asset' is not registered in the timeline registry.",
      },
    });
  });

  it('returns structured addClip failures without mutating timeline state', () => {
    const applyEdit = vi.fn();
    const store = buildCommandTestStore({
      data: buildDuplicateCommandTimelineData(),
      applyEdit,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const { result } = renderHook(() => useTimelineCommands(), { wrapper });
    const response = result.current.addClip({ assetId: 'asset-dup' });

    expect(response).toEqual({
      ok: false,
      error: {
        code: 'invalid_argument',
        message: 'addClip requires a target time unless `afterClipId` is provided.',
      },
    });
    expect(applyEdit).not.toHaveBeenCalled();
  });

  it('returns structured registerAsset failures without patching the registry for invalid generation inputs', async () => {
    const patchRegistry = vi.fn();
    const registerAsset = vi.fn(async () => undefined);
    const store = buildCommandTestStore({
      patchRegistry,
      registerAsset,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const { result } = renderHook(() => useTimelineCommands(), { wrapper });
    const response = await result.current.registerAsset({
      generationId: 'generation-1',
      imageUrl: '',
      variantType: 'image',
    });

    expect(response).toEqual({
      ok: false,
      error: {
        code: 'invalid_argument',
        message: 'registerAsset requires a non-empty media URL.',
      },
    });
    expect(patchRegistry).not.toHaveBeenCalled();
    expect(registerAsset).not.toHaveBeenCalled();
  });

  it('supports duplicate-style addClip insertion after an existing clip through the public facade', () => {
    const applyEdit = vi.fn();
    const store = buildCommandTestStore({
      data: buildDuplicateCommandTimelineData(),
      applyEdit,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const { result } = renderHook(() => useTimelineCommands(), { wrapper });
    const response = result.current.addClip({
      assetId: 'asset-dup',
      afterClipId: 'clip-1',
    });

    expect(response.ok).toBe(true);
    if (!response.ok) {
      throw new Error('Expected duplicate insertion to succeed');
    }

    expect(applyEdit).toHaveBeenCalledTimes(1);
    const mutation = applyEdit.mock.calls[0]?.[0] as {
      type: string;
      rows: Array<{ id: string; actions: Array<{ id: string; start: number; end: number }> }>;
      metaUpdates: Record<string, { asset: string; track: string }>;
      clipOrderOverride: Record<string, string[]>;
    };
    const options = applyEdit.mock.calls[0]?.[1] as {
      selectedClipId: string;
      selectedTrackId: string;
      semantic: boolean;
    };

    expect(mutation.type).toBe('rows');
    expect(mutation.rows[0]?.actions.map((action) => ({
      id: action.id,
      start: action.start,
      end: action.end,
    }))).toEqual([
      { id: 'clip-1', start: 0, end: 2 },
      { id: response.data.clipId, start: 2, end: 4 },
      { id: 'clip-2', start: 4, end: 5 },
    ]);
    expect(mutation.metaUpdates[response.data.clipId]).toMatchObject({
      asset: 'asset-dup',
      track: 'V1',
    });
    expect(mutation.clipOrderOverride).toEqual({
      V1: ['clip-1', response.data.clipId, 'clip-2'],
    });
    expect(options).toEqual({
      selectedClipId: response.data.clipId,
      selectedTrackId: 'V1',
      semantic: true,
    });
  });

  it('rolls back optimistic registry patches when public registerAsset persistence fails', async () => {
    const patchRegistry = vi.fn();
    const unpatchRegistry = vi.fn();
    const registerAsset = vi.fn(async () => {
      throw new Error('persist failed');
    });
    const store = buildCommandTestStore({
      patchRegistry,
      registerAsset,
      unpatchRegistry,
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TimelineStoreProvider store={store}>{children}</TimelineStoreProvider>
    );

    const { result } = renderHook(() => useTimelineCommands(), { wrapper });
    const response = await result.current.registerAsset({
      generationId: 'generation-1',
      imageUrl: 'https://example.com/image.png',
      variantType: 'image',
    });

    expect(response).toEqual({
      ok: false,
      error: {
        code: 'asset_registration_failed',
        message: 'persist failed',
        cause: expect.any(Error),
      },
    });
    expect(patchRegistry).toHaveBeenCalledTimes(1);
    expect(registerAsset).toHaveBeenCalledTimes(1);
    expect(unpatchRegistry).toHaveBeenCalledTimes(1);
  });

  it('keeps the sprint 2 governance inventory markers in the checklist and allowlist', () => {
    const checklist = readFileSync(
      join(process.cwd(), 'tasks/2026-05-03-video-editor-sprint2-ports-and-commands-checklist.md'),
      'utf8',
    );
    const allowlist = readFileSync(
      join(process.cwd(), 'eslint.supabase-facade-allowlist.js'),
      'utf8',
    );

    expect(checklist).toContain('useTimelineCommandsSafe()');
    expect(checklist).toContain('### Command-facade caller set');
    expect(checklist).toContain('VIDEO_EDITOR_HOST_PORT_NAMES');
    expect(checklist).toContain('src/domains/media-lightbox/hooks/useAddToVideoEditor.ts');
    expect(checklist).toContain('src/tools/video-editor/hooks/useAddVariantAsGeneration.ts');
    expect(checklist).toContain('src/tools/video-editor/hooks/useSwitchToFinalVideo.ts');
    expect(checklist).toContain('src/tools/video-editor/hooks/useExternalDrop.ts');
    expect(checklist).toContain('non-gesture facade');
    for (const portName of VIDEO_EDITOR_HOST_PORT_NAMES) {
      expect(checklist).toContain(`\`${portName}\``);
    }
    for (const gestureOnlyHook of INTERNAL_GESTURE_TIMELINE_MUTATIONS) {
      expect(checklist).toContain(gestureOnlyHook);
    }
    expect(allowlist).toContain('src/tools/video-editor/adapters/reigh/generationLookup.ts');
    expect(allowlist).toContain('src/tools/video-editor/adapters/reigh/useReighEffectsCatalog.ts');
    expect(allowlist).toContain('src/tools/video-editor/adapters/reigh/variantPromotionLookup.ts');
  });
});
