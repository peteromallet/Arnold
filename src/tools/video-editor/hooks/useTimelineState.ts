import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { useIsMobile, useIsTablet } from '@/shared/hooks/mobile';
import {
  editorClearTimelineSelection,
  systemResetTimelineSelection,
  useTimelineMultiSelect,
  userSelectTimelineClip,
  userSelectTimelineClips,
} from '@/shared/state/selectionStore';
import { createInteractionState, type InteractionStateRef } from '@/tools/video-editor/lib/interaction-state';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import { ROW_HEIGHT, TIMELINE_START_LEFT } from '@/tools/video-editor/lib/coordinate-utils';
import { useAssetManagement } from '@/tools/video-editor/hooks/useAssetManagement';
import { useAssetOperations } from '@/tools/video-editor/hooks/useAssetOperations';
import { useClipEditing } from '@/tools/video-editor/hooks/useClipEditing';
import { useClipResize } from '@/tools/video-editor/hooks/useClipResize';
import { useDerivedTimeline } from '@/tools/video-editor/hooks/useDerivedTimeline';
import { useDragCoordinator } from '@/tools/video-editor/hooks/useDragCoordinator';
import { useEditorPreferences } from '@/tools/video-editor/hooks/useEditorPreferences';
import { useExternalDrop } from '@/tools/video-editor/hooks/useExternalDrop';
import { useTimelinePlayback } from '@/tools/video-editor/hooks/useTimelinePlayback';
import { useRenderState } from '@/tools/video-editor/hooks/useRenderState';
import { useTimelineHistory } from '@/tools/video-editor/hooks/useTimelineHistory';
import { useTimelineQueries } from '@/tools/video-editor/hooks/useTimelineQueries';
import { useTimelineSave } from '@/tools/video-editor/hooks/useTimelineSave';
import { useTimelineSelection } from '@/tools/video-editor/hooks/useTimelineSelection';
import {
  createTimelineStore,
  type TimelineStoreApi,
  type TimelineStoreBootstrap,
} from '@/tools/video-editor/hooks/timelineStore';
import {
  createTimelineCommandRunner,
  MEDIA_COMMAND_DESCRIPTORS,
  provisionRegisteredTimelineMedia,
} from '@/tools/video-editor/commands';
import type {
  TimelineChromeContextValue,
  TimelineEditorCommandInput,
  TimelineEditorCommandResult,
  TimelineEditorContextValue,
  TimelineEditorCommands,
  TimelinePlaybackContextValue,
  UseTimelineStateResult,
} from '@/tools/video-editor/hooks/useTimelineState.types';
import {
  createMobileInteractionPolicy,
  getDefaultInteractionMode,
  resolveInputModalityFromPointerType,
  resolveTimelineDeviceClass,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { useTimelineTrackManagement } from '@/tools/video-editor/hooks/useTimelineTrackManagement';

export type { EditorPreferences } from '@/tools/video-editor/hooks/useEditorPreferences';
export type { RenderStatus } from '@/tools/video-editor/hooks/useRenderState';
export type { SaveStatus } from '@/tools/video-editor/hooks/useTimelineSave';

type SelectionHook = ReturnType<typeof useTimelineSelection>;
type MultiSelectHook = ReturnType<typeof useTimelineMultiSelect>;
type DragCoordinatorHook = ReturnType<typeof useDragCoordinator>;
type TimelinePlaybackHook = ReturnType<typeof useTimelinePlayback>;
type TimelineTrackManagementHook = ReturnType<typeof useTimelineTrackManagement>;
type AssetManagementHook = ReturnType<typeof useAssetManagement>;
type ClipResizeHook = ReturnType<typeof useClipResize>;
type ClipEditingHook = ReturnType<typeof useClipEditing>;
type ExternalDropHook = ReturnType<typeof useExternalDrop>;
type TimelineHistoryHook = ReturnType<typeof useTimelineHistory>;
type RenderStateHook = ReturnType<typeof useRenderState>;

const editorCommandRunner = createTimelineCommandRunner([...MEDIA_COMMAND_DESCRIPTORS]);

function useTimelineEditorContextValue({
  data,
  interactionPolicy,
  selection,
  multiSelect,
  selectedTrackId,
  compositionSize,
  trackScaleMap,
  scale,
  scaleWidth,
  isLoading,
  dataRef,
  pendingOpsRef,
  interactionStateRef,
  editorPreferences,
  setSelectedTrackId,
  setActiveClipTab,
  setAssetPanelState,
  dragCoordinator,
  playback,
  assetManagement,
  clipResize,
  clipEditing,
  externalDrop,
  trackManagement,
  uploadFiles,
  applyEdit,
  commands,
  patchRegistry,
  unpatchRegistry,
  registerAsset,
  setInputModality,
  setInputModalityFromPointerType,
  setInteractionMode,
  setGestureOwner,
  setPrecisionEnabled,
  setContextTarget,
  setInspectorTarget,
}: {
  data: TimelineData | null;
  interactionPolicy: ReturnType<typeof createMobileInteractionPolicy>;
  selection: SelectionHook;
  multiSelect: MultiSelectHook;
  selectedTrackId: string | null;
  compositionSize: { width: number; height: number };
  trackScaleMap: Record<string, number>;
  scale: number;
  scaleWidth: number;
  isLoading: boolean;
  dataRef: ReturnType<typeof useTimelineSave>['dataRef'];
  pendingOpsRef: ReturnType<typeof useTimelineSave>['pendingOpsRef'];
  interactionStateRef: InteractionStateRef;
  editorPreferences: ReturnType<typeof useEditorPreferences>['preferences'];
  setSelectedTrackId: ReturnType<typeof useTimelineSave>['setSelectedTrackId'];
  setActiveClipTab: ReturnType<typeof useEditorPreferences>['setActiveClipTab'];
  setAssetPanelState: ReturnType<typeof useEditorPreferences>['setAssetPanelState'];
  dragCoordinator: DragCoordinatorHook;
  playback: TimelinePlaybackHook;
  assetManagement: AssetManagementHook;
  clipResize: ClipResizeHook;
  clipEditing: ClipEditingHook;
  externalDrop: ExternalDropHook;
  trackManagement: TimelineTrackManagementHook;
  uploadFiles: ReturnType<typeof useAssetOperations>['uploadFiles'];
  applyEdit: ReturnType<typeof useTimelineSave>['applyEdit'];
  commands: TimelineEditorCommands;
  patchRegistry: ReturnType<typeof useTimelineSave>['patchRegistry'];
  unpatchRegistry: ReturnType<typeof useTimelineSave>['unpatchRegistry'];
  registerAsset: ReturnType<typeof useAssetOperations>['registerAsset'];
  setInputModality: Dispatch<SetStateAction<ReturnType<typeof createMobileInteractionPolicy>['inputModality']>>;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => ReturnType<typeof createMobileInteractionPolicy>['inputModality'];
  setInteractionMode: Dispatch<SetStateAction<ReturnType<typeof createMobileInteractionPolicy>['interactionMode']>>;
  setGestureOwner: Dispatch<SetStateAction<ReturnType<typeof createMobileInteractionPolicy>['gestureOwner']>>;
  setPrecisionEnabled: Dispatch<SetStateAction<boolean>>;
  setContextTarget: Dispatch<SetStateAction<ReturnType<typeof createMobileInteractionPolicy>['contextTarget']>>;
  setInspectorTarget: Dispatch<SetStateAction<ReturnType<typeof createMobileInteractionPolicy>['inspectorTarget']>>;
}): TimelineEditorContextValue {
  const onActionResizeStart = clipResize.onActionResizeStart;
  const onClipEdgeResizeEnd = clipResize.onClipEdgeResizeEnd;

  return useMemo<TimelineEditorContextValue>(() => ({
    data,
    resolvedConfig: selection.resolvedConfig,
    deviceClass: interactionPolicy.deviceClass,
    inputModality: interactionPolicy.inputModality,
    interactionMode: interactionPolicy.interactionMode,
    gestureOwner: interactionPolicy.gestureOwner,
    precisionEnabled: interactionPolicy.precisionEnabled,
    contextTarget: interactionPolicy.contextTarget,
    inspectorTarget: interactionPolicy.inspectorTarget,
    interactionPolicy,
    selectedClipId: selection.primaryClipId,
    selectedClipIds: selection.selectedClipIds,
    selectedClipIdsRef: selection.selectedClipIdsRef,
    additiveSelectionRef: selection.additiveSelectionRef,
    selectedTrackId,
    primaryClipId: selection.primaryClipId,
    selectedClip: selection.selectedClip,
    selectedTrack: selection.selectedTrack,
    selectedClipHasPredecessor: selection.selectedClipHasPredecessor,
    compositionSize,
    trackScaleMap,
    scale,
    scaleWidth,
    isLoading,
    dataRef,
    pendingOpsRef,
    interactionStateRef,
    coordinator: dragCoordinator.coordinator,
    indicatorRef: dragCoordinator.indicatorRef,
    editAreaRef: dragCoordinator.editAreaRef,
    preferences: editorPreferences,
    timelineRef: playback.timelineRef,
    timelineWrapperRef: playback.timelineWrapperRef,
    setInputModality,
    setInputModalityFromPointerType,
    setInteractionMode,
    setGestureOwner,
    setPrecisionEnabled,
    setContextTarget,
    setInspectorTarget,
    isClipSelected: multiSelect.isClipSelected,
    selectClip: (clipId, opts) => userSelectTimelineClip(clipId, {
      additive: Boolean(opts?.toggle),
      preserveIfSelected: opts?.preserveSelection,
    }),
    selectClips: (clipIds) => userSelectTimelineClips(clipIds, { additive: false }),
    addToSelection: (clipIds) => userSelectTimelineClips(clipIds, { additive: true }),
    clearSelection: editorClearTimelineSelection,
    setSelectedTrackId,
    setActiveClipTab,
    setAssetPanelState,
    registerGenerationAsset: assetManagement.registerGenerationAsset,
    onCursorDrag: playback.onCursorDrag,
    onClickTimeArea: playback.onClickTimeArea,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onOverlayChange: clipEditing.onOverlayChange,
    onTimelineDragOver: externalDrop.onTimelineDragOver,
    onTimelineDragLeave: externalDrop.onTimelineDragLeave,
    onTimelineDrop: externalDrop.onTimelineDrop,
    handleAssetDrop: assetManagement.handleAssetDrop,
    handleUpdateClips: clipEditing.handleUpdateClips,
    handleUpdateClipsDeep: clipEditing.handleUpdateClipsDeep,
    handleDeleteClips: clipEditing.handleDeleteClips,
    handleDeleteClip: clipEditing.handleDeleteClip,
    handleSelectedClipChange: clipEditing.handleSelectedClipChange,
    handleResetClipPosition: clipEditing.handleResetClipPosition,
    handleResetClipsPosition: clipEditing.handleResetClipsPosition,
    handleSplitSelectedClip: clipEditing.handleSplitSelectedClip,
    handleSplitClipAtTime: clipEditing.handleSplitClipAtTime,
    handleSplitClipsAtPlayhead: clipEditing.handleSplitClipsAtPlayhead,
    handleToggleMuteClips: clipEditing.handleToggleMuteClips,
    handleToggleMute: clipEditing.handleToggleMute,
    handleDetachAudioClip: clipEditing.handleDetachAudioClip,
    handleTrackPopoverChange: trackManagement.handleTrackPopoverChange,
    handleMoveTrack: trackManagement.handleMoveTrack,
    handleRemoveTrack: trackManagement.handleRemoveTrack,
    moveSelectedClipToTrack: trackManagement.moveSelectedClipToTrack,
    moveSelectedClipsToTrack: trackManagement.moveSelectedClipsToTrack,
    moveClipToRow: trackManagement.moveClipToRow,
    createTrackAndMoveClip: trackManagement.createTrackAndMoveClip,
    uploadFiles,
    applyEdit,
    commands,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
  }), [
    applyEdit,
    commands,
    assetManagement.handleAssetDrop,
    assetManagement.registerGenerationAsset,
    clipEditing.handleDeleteClip,
    clipEditing.handleDeleteClips,
    clipEditing.handleDetachAudioClip,
    clipEditing.handleResetClipPosition,
    clipEditing.handleResetClipsPosition,
    clipEditing.handleSelectedClipChange,
    clipEditing.handleSplitClipAtTime,
    clipEditing.handleSplitClipsAtPlayhead,
    clipEditing.handleSplitSelectedClip,
    clipEditing.handleToggleMute,
    clipEditing.handleToggleMuteClips,
    clipEditing.handleUpdateClips,
    clipEditing.handleUpdateClipsDeep,
    clipEditing.onOverlayChange,
    compositionSize,
    data,
    dataRef,
    dragCoordinator.coordinator,
    dragCoordinator.editAreaRef,
    dragCoordinator.indicatorRef,
    editorPreferences,
    externalDrop.onTimelineDragLeave,
    externalDrop.onTimelineDragOver,
    externalDrop.onTimelineDrop,
    interactionPolicy,
    interactionStateRef,
    isLoading,
    multiSelect.isClipSelected,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    patchRegistry,
    pendingOpsRef,
    playback.onClickTimeArea,
    playback.onCursorDrag,
    playback.timelineRef,
    playback.timelineWrapperRef,
    registerAsset,
    scale,
    scaleWidth,
    selectedTrackId,
    selection.additiveSelectionRef,
    selection.primaryClipId,
    selection.resolvedConfig,
    selection.selectedClip,
    selection.selectedClipHasPredecessor,
    selection.selectedClipIds,
    selection.selectedClipIdsRef,
    selection.selectedTrack,
    setActiveClipTab,
    setAssetPanelState,
    setContextTarget,
    setGestureOwner,
    setInputModality,
    setInputModalityFromPointerType,
    setInspectorTarget,
    setInteractionMode,
    setPrecisionEnabled,
    setSelectedTrackId,
    trackManagement.createTrackAndMoveClip,
    trackManagement.handleMoveTrack,
    trackManagement.handleRemoveTrack,
    trackManagement.handleTrackPopoverChange,
    trackManagement.moveClipToRow,
    trackManagement.moveSelectedClipToTrack,
    trackManagement.moveSelectedClipsToTrack,
    trackScaleMap,
    unpatchRegistry,
    uploadFiles,
  ]);
}

function useTimelineChromeContextValue({
  timelineName,
  saveStatus,
  isConflictExhausted,
  render,
  history,
  setScaleWidth,
  trackManagement,
  clipEditing,
  reloadFromServer,
  retrySaveAfterConflict,
  startRender,
}: {
  timelineName: string | null;
  saveStatus: ReturnType<typeof useTimelineSave>['saveStatus'];
  isConflictExhausted: boolean;
  render: Pick<RenderStateHook, 'renderStatus' | 'renderLog' | 'renderDirty' | 'renderProgress' | 'renderResultUrl' | 'renderResultFilename'>;
  history: Pick<TimelineHistoryHook, 'undo' | 'redo' | 'canUndo' | 'canRedo' | 'checkpoints' | 'jumpToCheckpoint' | 'createManualCheckpoint'>;
  setScaleWidth: ReturnType<typeof useEditorPreferences>['setScaleWidth'];
  trackManagement: Pick<TimelineTrackManagementHook, 'handleAddTrack' | 'handleClearUnusedTracks' | 'unusedTrackCount'>;
  clipEditing: Pick<ClipEditingHook, 'handleAddText' | 'handleAddTextAt'>;
  reloadFromServer: ReturnType<typeof useTimelineSave>['reloadFromServer'];
  retrySaveAfterConflict: ReturnType<typeof useTimelineSave>['retrySaveAfterConflict'];
  startRender: ReturnType<typeof useRenderState>['startRender'];
}): TimelineChromeContextValue {
  return useMemo<TimelineChromeContextValue>(() => ({
    timelineName,
    saveStatus,
    isConflictExhausted,
    renderStatus: render.renderStatus,
    renderLog: render.renderLog,
    renderDirty: render.renderDirty,
    renderProgress: render.renderProgress,
    renderResultUrl: render.renderResultUrl,
    renderResultFilename: render.renderResultFilename,
    undo: history.undo,
    redo: history.redo,
    canUndo: history.canUndo,
    canRedo: history.canRedo,
    checkpoints: history.checkpoints,
    jumpToCheckpoint: history.jumpToCheckpoint,
    createManualCheckpoint: history.createManualCheckpoint,
    setScaleWidth,
    handleAddTrack: trackManagement.handleAddTrack,
    handleClearUnusedTracks: trackManagement.handleClearUnusedTracks,
    unusedTrackCount: trackManagement.unusedTrackCount,
    handleAddText: clipEditing.handleAddText,
    handleAddTextAt: clipEditing.handleAddTextAt,
    reloadFromServer,
    retrySaveAfterConflict,
    startRender,
  }), [
    clipEditing.handleAddText,
    clipEditing.handleAddTextAt,
    history.canRedo,
    history.canUndo,
    history.checkpoints,
    history.createManualCheckpoint,
    history.jumpToCheckpoint,
    history.redo,
    history.undo,
    isConflictExhausted,
    reloadFromServer,
    render.renderDirty,
    render.renderLog,
    render.renderProgress,
    render.renderResultFilename,
    render.renderResultUrl,
    render.renderStatus,
    retrySaveAfterConflict,
    saveStatus,
    setScaleWidth,
    startRender,
    timelineName,
    trackManagement.handleAddTrack,
    trackManagement.handleClearUnusedTracks,
    trackManagement.unusedTrackCount,
  ]);
}

function useTimelinePlaybackContextValue({
  playback,
}: {
  playback: Pick<TimelinePlaybackHook, 'currentTime' | 'previewRef' | 'playerContainerRef' | 'onPreviewTimeUpdate' | 'formatTime'>;
}): TimelinePlaybackContextValue {
  return useMemo<TimelinePlaybackContextValue>(() => ({
    currentTime: playback.currentTime,
    previewRef: playback.previewRef,
    playerContainerRef: playback.playerContainerRef,
    onPreviewTimeUpdate: playback.onPreviewTimeUpdate,
    formatTime: playback.formatTime,
  }), [
    playback.currentTime,
    playback.formatTime,
    playback.onPreviewTimeUpdate,
    playback.playerContainerRef,
    playback.previewRef,
  ]);
}

function syncInitialTimelineStoreBootstrap(
  store: TimelineStoreApi,
  bootstrap: TimelineStoreBootstrap,
) {
  const state = store.getState();
  if (state.availability.mounted) {
    return;
  }

  store.getState().syncSlices(bootstrap);
}

export function useTimelineState(): UseTimelineStateResult {
  const runtime = useVideoEditorRuntime();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const playback = useTimelinePlayback();
  const preferences = useEditorPreferences(runtime.timelineId);
  const resolveAssetUrl = useCallback(async (file: string) => {
    if (runtime.assetResolver) {
      return await runtime.assetResolver.resolveAssetUrl(file);
    }

    return await runtime.provider.resolveAssetUrl(file);
  }, [runtime.assetResolver, runtime.provider]);
  const queries = useTimelineQueries(runtime.provider, runtime.timelineId, resolveAssetUrl);
  // Shared gate observed by drag/resize writers and read by save/persistence/poll.
  const interactionStateRef = useRef(createInteractionState());
  const storeRef = useRef<ReturnType<typeof createTimelineStore> | null>(null);
  if (storeRef.current === null) {
    storeRef.current = createTimelineStore();
  }
  const deviceClass = useMemo(
    () => resolveTimelineDeviceClass({ isMobile, isTablet }),
    [isMobile, isTablet],
  );
  const defaultInteractionMode = getDefaultInteractionMode(deviceClass);
  const initialInteractionPolicyRef = useRef(createMobileInteractionPolicy(deviceClass));
  const previousDefaultInteractionModeRef = useRef(defaultInteractionMode);
  const [inputModality, setInputModality] = useState(initialInteractionPolicyRef.current.inputModality);
  const [interactionMode, setInteractionMode] = useState(initialInteractionPolicyRef.current.interactionMode);
  const [gestureOwner, setGestureOwner] = useState(initialInteractionPolicyRef.current.gestureOwner);
  const [precisionEnabled, setPrecisionEnabled] = useState(initialInteractionPolicyRef.current.precisionEnabled);
  const [contextTarget, setContextTarget] = useState(initialInteractionPolicyRef.current.contextTarget);
  const [inspectorTarget, setInspectorTarget] = useState(initialInteractionPolicyRef.current.inspectorTarget);
  const save = useTimelineSave(queries, runtime.provider, interactionStateRef, storeRef.current);
  const history = useTimelineHistory({
    dataRef: save.dataRef,
    commitData: save.commitData,
    interactionStateRef,
  });
  const derived = useDerivedTimeline(save.data, save.selectedClipId, save.selectedTrackId);
  const render = useRenderState(derived.resolvedConfig, derived.renderMetadata, runtime.exporter ?? null);
  const assetOperations = useAssetOperations(
    runtime.provider,
    runtime.timelineId,
    runtime.userId,
    queryClient,
    save.pendingOpsRef,
  );
  const {
    data,
    dataRef,
    eventBus,
    isConflictExhausted,
    selectedTrackId,
    saveStatus,
    setSelectedTrackId,
    applyEdit,
    patchRegistry,
    unpatchRegistry,
    reloadFromServer,
    retrySaveAfterConflict,
    pendingOpsRef,
    isLoading,
  } = save;
  const {
    compositionSize,
    trackScaleMap,
  } = derived;
  const {
    renderStatus,
    renderLog,
    renderDirty,
    renderProgress,
    renderResultUrl,
    renderResultFilename,
    setRenderDirty,
    startRender,
  } = render;
  const {
    canUndo,
    canRedo,
    checkpoints,
    undo,
    redo,
    jumpToCheckpoint,
    createManualCheckpoint,
    onBeforeCommit,
  } = history;
  const {
    scale,
    scaleWidth,
    preferences: editorPreferences,
    setScaleWidth,
    setActiveClipTab,
    setAssetPanelState,
  } = preferences;
  const {
    registerAsset,
    uploadAsset,
    uploadFiles,
    invalidateAssetRegistry,
  } = assetOperations;
  const selectedProjectId = runtime.hostContext?.projectId ?? runtime.project.projectId;
  const selection = useTimelineSelection({
    data,
    selectedTrackId,
  });
  const multiSelect = useTimelineMultiSelect();

  useEffect(() => {
    systemResetTimelineSelection();
  }, [runtime.timelineId]);
  const setInputModalityFromPointerType = useCallback((pointerType: string | null | undefined) => {
    const nextModality = resolveInputModalityFromPointerType(pointerType);
    setInputModality(nextModality);
    return nextModality;
  }, []);

  const interactionPolicy = useMemo(() => ({
    deviceClass,
    inputModality,
    interactionMode,
    gestureOwner,
    precisionEnabled,
    contextTarget,
    inspectorTarget,
  }), [
    contextTarget,
    deviceClass,
    gestureOwner,
    inputModality,
    inspectorTarget,
    interactionMode,
    precisionEnabled,
  ]);

  useEffect(() => {
    return eventBus.on('beforeCommit', onBeforeCommit);
  }, [eventBus, onBeforeCommit]);

  useEffect(() => {
    return eventBus.on('pruneSelection', selection.pruneSelection);
  }, [eventBus, selection.pruneSelection]);

  useEffect(() => {
    return eventBus.on('saveSuccess', () => {
      setRenderDirty(true);
    });
  }, [eventBus, setRenderDirty]);

  useEffect(() => {
    setInteractionMode((currentMode) => (
      currentMode === previousDefaultInteractionModeRef.current
        ? defaultInteractionMode
        : currentMode
    ));
    previousDefaultInteractionModeRef.current = defaultInteractionMode;
  }, [defaultInteractionMode]);

  const dragCoordinator = useDragCoordinator({
    dataRef,
    scale,
    scaleWidth,
    startLeft: TIMELINE_START_LEFT,
    rowHeight: ROW_HEIGHT,
  });

  const assetManagement = useAssetManagement({
    store: storeRef.current,
    dataRef,
    selectedTrackId,
    selectedProjectId,
    selectClip: multiSelect.selectClip,
    setSelectedTrackId,
    applyEdit,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
    uploadAsset,
    invalidateAssetRegistry,
    resolveAssetUrl,
  });

  const clipResize = useClipResize({
    dataRef,
    applyEdit,
  });

  const clipEditing = useClipEditing({
    dataRef,
    resolvedConfig: selection.resolvedConfig,
    selectedClipId: selection.primaryClipId,
    selectedTrack: selection.selectedTrack,
    currentTime: playback.currentTime,
    selectClip: multiSelect.selectClip,
    setSelectedTrackId,
    applyEdit,
  });

  const externalDrop = useExternalDrop({
    store: storeRef.current,
    dataRef,
    pendingOpsRef,
    scale,
    scaleWidth,
    selectedTrackId,
    applyEdit,
    patchRegistry,
    registerAsset,
    uploadAsset,
    invalidateAssetRegistry,
    resolveAssetUrl,
    coordinator: dragCoordinator.coordinator,
    registerGenerationAsset: assetManagement.registerGenerationAsset,
    uploadImageGeneration: assetManagement.uploadImageGeneration,
    uploadVideoGeneration: assetManagement.uploadVideoGeneration,
    handleAssetDrop: assetManagement.handleAssetDrop,
    handleAddTextAt: clipEditing.handleAddTextAt,
    onSeekToTime: playback.onClickTimeArea,
  });

  const trackManagement = useTimelineTrackManagement({
    dataRef,
    resolvedConfig: selection.resolvedConfig,
    selectedClipId: selection.primaryClipId,
    setSelectedTrackId,
    applyEdit,
  });

  const timelineCommands = useMemo<TimelineEditorCommands>(() => {
    const getCurrentData = () => {
      const current = dataRef.current ?? data;
      if (!current) {
        throw new Error('Timeline data is not ready.');
      }
      return current;
    };

    const buildAddMediaCommand = ({ trackId, at, assetKey }: { trackId: string; at: number; assetKey: string }) => {
      const current = getCurrentData();
      const asset = provisionRegisteredTimelineMedia(assetKey, current.registry.assets[assetKey]);
      if (!asset) {
        return null;
      }

      return {
        type: 'add-media' as const,
        payload: {
          trackId,
          at,
          asset,
        },
      };
    };

    const buildSwapCommand = ({ clipId, assetKey }: { clipId: string; assetKey: string }) => {
      const current = getCurrentData();
      const asset = provisionRegisteredTimelineMedia(assetKey, current.registry.assets[assetKey]);
      if (!asset) {
        return null;
      }

      return {
        type: 'swap' as const,
        payload: {
          clipId,
          asset,
        },
      };
    };

    const validate = (input: TimelineEditorCommandInput | unknown, options?: Parameters<typeof editorCommandRunner.validate>[2]) => {
      return editorCommandRunner.validate(getCurrentData(), input, options);
    };

    const dryRun = (input: TimelineEditorCommandInput | unknown, options?: Parameters<typeof editorCommandRunner.dryRun>[2]) => {
      return editorCommandRunner.dryRun(getCurrentData(), input, options);
    };

    const apply = (input: TimelineEditorCommandInput | unknown, options?: Parameters<TimelineEditorCommands['apply']>[1]): TimelineEditorCommandResult => {
      const current = getCurrentData();
      const result = editorCommandRunner.apply(current, input, options);
      if (result.status !== 'rejected' && result.nextData.stableSignature !== current.stableSignature) {
        save.commitData(result.nextData, {
          save: options?.save,
          selectedClipId: options?.selectedClipId,
          selectedTrackId: options?.selectedTrackId,
          transactionId: result.transaction.transactionId,
          commandHistory: {
            transaction: result.transaction,
            history: result.history,
          },
        });
      }

      return result;
    };

    return {
      buildAddMediaCommand,
      buildSwapCommand,
      validate,
      dryRun,
      apply,
    };
  }, [data, dataRef, save]);

  const editor = useTimelineEditorContextValue({
    data,
    interactionPolicy,
    selection,
    multiSelect,
    selectedTrackId,
    compositionSize,
    trackScaleMap,
    scale,
    scaleWidth,
    isLoading,
    dataRef,
    pendingOpsRef,
    interactionStateRef,
    editorPreferences,
    setSelectedTrackId,
    setActiveClipTab,
    setAssetPanelState,
    dragCoordinator,
    playback,
    assetManagement,
    clipResize,
    clipEditing,
    externalDrop,
    trackManagement,
    uploadFiles,
    applyEdit,
    commands: timelineCommands,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
    setInputModality,
    setInputModalityFromPointerType,
    setInteractionMode,
    setGestureOwner,
    setPrecisionEnabled,
    setContextTarget,
    setInspectorTarget,
  });

  const editorData = useMemo(() => ({
    data: editor.data,
    resolvedConfig: editor.resolvedConfig,
    deviceClass: editor.deviceClass,
    inputModality: editor.inputModality,
    interactionMode: editor.interactionMode,
    gestureOwner: editor.gestureOwner,
    precisionEnabled: editor.precisionEnabled,
    contextTarget: editor.contextTarget,
    inspectorTarget: editor.inspectorTarget,
    interactionPolicy: editor.interactionPolicy,
    selectedClipId: editor.selectedClipId,
    selectedClipIds: editor.selectedClipIds,
    selectedClipIdsRef: editor.selectedClipIdsRef,
    additiveSelectionRef: editor.additiveSelectionRef,
    selectedTrackId: editor.selectedTrackId,
    primaryClipId: editor.primaryClipId,
    selectedClip: editor.selectedClip,
    selectedTrack: editor.selectedTrack,
    selectedClipHasPredecessor: editor.selectedClipHasPredecessor,
    compositionSize: editor.compositionSize,
    trackScaleMap: editor.trackScaleMap,
    scale: editor.scale,
    scaleWidth: editor.scaleWidth,
    isLoading: editor.isLoading,
    dataRef: editor.dataRef,
    pendingOpsRef: editor.pendingOpsRef,
    interactionStateRef: editor.interactionStateRef,
    coordinator: editor.coordinator,
    indicatorRef: editor.indicatorRef,
    editAreaRef: editor.editAreaRef,
    preferences: editor.preferences,
    timelineRef: editor.timelineRef,
    timelineWrapperRef: editor.timelineWrapperRef,
  }), [editor]);

  const onActionResizeStart = editor.onActionResizeStart;
  const onClipEdgeResizeEnd = editor.onClipEdgeResizeEnd;

  const editorOps = useMemo(() => ({
    setInputModality: editor.setInputModality,
    setInputModalityFromPointerType: editor.setInputModalityFromPointerType,
    setInteractionMode: editor.setInteractionMode,
    setGestureOwner: editor.setGestureOwner,
    setPrecisionEnabled: editor.setPrecisionEnabled,
    setContextTarget: editor.setContextTarget,
    setInspectorTarget: editor.setInspectorTarget,
    isClipSelected: editor.isClipSelected,
    selectClip: editor.selectClip,
    selectClips: editor.selectClips,
    addToSelection: editor.addToSelection,
    clearSelection: editor.clearSelection,
    setSelectedTrackId: editor.setSelectedTrackId,
    setActiveClipTab: editor.setActiveClipTab,
    setAssetPanelState: editor.setAssetPanelState,
    registerGenerationAsset: editor.registerGenerationAsset,
    onCursorDrag: editor.onCursorDrag,
    onClickTimeArea: editor.onClickTimeArea,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onOverlayChange: editor.onOverlayChange,
    onTimelineDragOver: editor.onTimelineDragOver,
    onTimelineDragLeave: editor.onTimelineDragLeave,
    onTimelineDrop: editor.onTimelineDrop,
    handleAssetDrop: editor.handleAssetDrop,
    handleUpdateClips: editor.handleUpdateClips,
    handleUpdateClipsDeep: editor.handleUpdateClipsDeep,
    handleDeleteClips: editor.handleDeleteClips,
    handleDeleteClip: editor.handleDeleteClip,
    handleSelectedClipChange: editor.handleSelectedClipChange,
    handleResetClipPosition: editor.handleResetClipPosition,
    handleResetClipsPosition: editor.handleResetClipsPosition,
    handleSplitSelectedClip: editor.handleSplitSelectedClip,
    handleSplitClipAtTime: editor.handleSplitClipAtTime,
    handleSplitClipsAtPlayhead: editor.handleSplitClipsAtPlayhead,
    handleToggleMuteClips: editor.handleToggleMuteClips,
    handleToggleMute: editor.handleToggleMute,
    handleDetachAudioClip: editor.handleDetachAudioClip,
    handleTrackPopoverChange: editor.handleTrackPopoverChange,
    handleMoveTrack: editor.handleMoveTrack,
    handleRemoveTrack: editor.handleRemoveTrack,
    moveSelectedClipToTrack: editor.moveSelectedClipToTrack,
    moveSelectedClipsToTrack: editor.moveSelectedClipsToTrack,
    moveClipToRow: editor.moveClipToRow,
    createTrackAndMoveClip: editor.createTrackAndMoveClip,
    uploadFiles: editor.uploadFiles,
    applyEdit: editor.applyEdit,
    commands: timelineCommands,
    patchRegistry: editor.patchRegistry,
    unpatchRegistry: editor.unpatchRegistry,
    registerAsset: editor.registerAsset,
  }), [editor, onActionResizeStart, onClipEdgeResizeEnd, timelineCommands]);

  const chrome = useTimelineChromeContextValue({
    timelineName: runtime.timelineName ?? null,
    saveStatus,
    isConflictExhausted,
    render: {
      renderStatus,
      renderLog,
      renderDirty,
      renderProgress,
      renderResultUrl,
      renderResultFilename,
    },
    history: {
      undo,
      redo,
      canUndo,
      canRedo,
      checkpoints,
      jumpToCheckpoint,
      createManualCheckpoint,
    },
    setScaleWidth,
    trackManagement: {
      handleAddTrack: trackManagement.handleAddTrack,
      handleClearUnusedTracks: trackManagement.handleClearUnusedTracks,
      unusedTrackCount: trackManagement.unusedTrackCount,
    },
    clipEditing: {
      handleAddText: clipEditing.handleAddText,
      handleAddTextAt: clipEditing.handleAddTextAt,
    },
    reloadFromServer,
    retrySaveAfterConflict,
    startRender,
  });

  const playbackValue = useTimelinePlaybackContextValue({ playback });

  // Seed the external store before descendants render for the first time so
  // mounted-provider readers such as AgentChat and pending-add helpers do not
  // observe the placeholder slice values from createTimelineStore().
  syncInitialTimelineStoreBootstrap(storeRef.current, {
    data: editorData,
    ops: editorOps,
    chrome,
    playback: playbackValue,
  });

  useLayoutEffect(() => {
    storeRef.current.getState().syncSlices({
      data: editorData,
      ops: editorOps,
      chrome,
      playback: playbackValue,
    });
  }, [chrome, editorData, editorOps, playbackValue]);

  return {
    store: storeRef.current,
    editor,
    editorData,
    editorOps,
    chrome,
    playback: playbackValue,
  };
}
