import type { useAssetManagement } from '@/tools/video-editor/hooks/useAssetManagement';
import type { useClipEditing } from '@/tools/video-editor/hooks/useClipEditing';
import type { useClipResize } from '@/tools/video-editor/hooks/useClipResize';
import type { useDragCoordinator } from '@/tools/video-editor/hooks/useDragCoordinator';
import type { useExternalDrop } from '@/tools/video-editor/hooks/useExternalDrop';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';
import type { useTimelinePlayback } from '@/tools/video-editor/hooks/useTimelinePlayback';
import type { useTimelineTrackManagement } from '@/tools/video-editor/hooks/useTimelineTrackManagement';
import type {
  TimelineApplyEdit,
  TimelineCheckpoints,
  TimelineCreateManualCheckpoint,
  TimelineDataRef,
  TimelineJumpToCheckpoint,
  TimelinePatchRegistry,
  TimelinePendingOpsRef,
  TimelineRegisterAsset,
  TimelineReloadFromServer,
  TimelineRenderProgress,
  TimelineResolvedConfig,
  TimelineRetrySaveAfterConflict,
  TimelineSelectedClip,
  TimelineSelectedTrack,
  TimelineSetScaleWidth,
  TimelineSetSelectedTrackId,
  TimelineStartRender,
  TimelineUnpatchRegistry,
  TimelineUploadFiles,
} from '@/tools/video-editor/hooks/timeline-state-types';
import type { ClipTab, EditorPreferences } from '@/tools/video-editor/hooks/useEditorPreferences';
import type { RenderStatus } from '@/tools/video-editor/hooks/useRenderState';
import type { SaveStatus } from '@/tools/video-editor/hooks/useTimelineSave';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { SelectClipOptions, UseTimelineMultiSelectResult } from '@/shared/state/selectionStore';
import type {
  MobileInteractionPolicy,
  TimelineContextTarget,
  TimelineGestureOwner,
  TimelineInputModality,
  TimelineInspectorTarget,
  TimelineInteractionMode,
} from '@/tools/video-editor/lib/mobile-interaction-model';

type DragCoordinatorHook = ReturnType<typeof useDragCoordinator>;
type TimelinePlaybackHook = ReturnType<typeof useTimelinePlayback>;
type TimelineTrackManagementHook = ReturnType<typeof useTimelineTrackManagement>;
type AssetManagementHook = ReturnType<typeof useAssetManagement>;
type ClipResizeHook = ReturnType<typeof useClipResize>;
type ClipEditingHook = ReturnType<typeof useClipEditing>;
type ExternalDropHook = ReturnType<typeof useExternalDrop>;
type TimelineSetActiveClipTab = (tab: ClipTab) => void;
type TimelineSetAssetPanelState = (patch: Partial<EditorPreferences['assetPanel']>) => void;
export type TimelineActionResizeStart = ClipResizeHook['onActionResizeStart'];
export type TimelineClipEdgeResizeEnd = ClipResizeHook['onClipEdgeResizeEnd'];

export interface TimelineEditorDataContextValue {
  data: TimelineData | null;
  resolvedConfig: TimelineResolvedConfig;
  deviceClass: MobileInteractionPolicy['deviceClass'];
  inputModality: TimelineInputModality;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  precisionEnabled: boolean;
  contextTarget: TimelineContextTarget;
  inspectorTarget: TimelineInspectorTarget;
  interactionPolicy: MobileInteractionPolicy;
  selectedClipId: string | null;
  selectedClipIds: UseTimelineMultiSelectResult['selectedClipIds'];
  selectedClipIdsRef: UseTimelineMultiSelectResult['selectedClipIdsRef'];
  additiveSelectionRef: UseTimelineMultiSelectResult['additiveSelectionRef'];
  selectedTrackId: string | null;
  primaryClipId: UseTimelineMultiSelectResult['primaryClipId'];
  selectedClip: TimelineSelectedClip;
  selectedTrack: TimelineSelectedTrack;
  selectedClipHasPredecessor: boolean;
  compositionSize: { width: number; height: number };
  trackScaleMap: Record<string, number>;
  scale: number;
  scaleWidth: number;
  isLoading: boolean;
  dataRef: TimelineDataRef;
  pendingOpsRef: TimelinePendingOpsRef;
  interactionStateRef: import('@/tools/video-editor/lib/interaction-state').InteractionStateRef;
  coordinator: DragCoordinatorHook['coordinator'];
  indicatorRef: DragCoordinatorHook['indicatorRef'];
  editAreaRef: DragCoordinatorHook['editAreaRef'];
  preferences: EditorPreferences;
  timelineRef: TimelinePlaybackHook['timelineRef'];
  timelineWrapperRef: TimelinePlaybackHook['timelineWrapperRef'];
}

export interface TimelineEditorOpsContextValue {
  setInputModality: (inputModality: TimelineInputModality) => void;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => TimelineInputModality;
  setInteractionMode: (mode: TimelineInteractionMode) => void;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  setPrecisionEnabled: (enabled: boolean) => void;
  setContextTarget: (target: TimelineContextTarget) => void;
  setInspectorTarget: (target: TimelineInspectorTarget) => void;
  isClipSelected: UseTimelineMultiSelectResult['isClipSelected'];
  selectClip: (clipId: string, opts?: SelectClipOptions) => void;
  selectClips: (clipIds: Iterable<string>) => void;
  addToSelection: (clipIds: Iterable<string>) => void;
  clearSelection: () => void;
  setSelectedTrackId: TimelineSetSelectedTrackId;
  setActiveClipTab: TimelineSetActiveClipTab;
  setAssetPanelState: TimelineSetAssetPanelState;
  registerGenerationAsset: AssetManagementHook['registerGenerationAsset'];
  onCursorDrag: TimelinePlaybackHook['onCursorDrag'];
  onClickTimeArea: TimelinePlaybackHook['onClickTimeArea'];
  onActionResizeStart: TimelineActionResizeStart;
  onClipEdgeResizeEnd: TimelineClipEdgeResizeEnd;
  onOverlayChange: ClipEditingHook['onOverlayChange'];
  onTimelineDragOver: ExternalDropHook['onTimelineDragOver'];
  onTimelineDragLeave: ExternalDropHook['onTimelineDragLeave'];
  onTimelineDrop: ExternalDropHook['onTimelineDrop'];
  handleAssetDrop: AssetManagementHook['handleAssetDrop'];
  handleUpdateClips: ClipEditingHook['handleUpdateClips'];
  handleUpdateClipsDeep: ClipEditingHook['handleUpdateClipsDeep'];
  handleDeleteClips: ClipEditingHook['handleDeleteClips'];
  handleDeleteClip: ClipEditingHook['handleDeleteClip'];
  handleSelectedClipChange: ClipEditingHook['handleSelectedClipChange'];
  handleResetClipPosition: ClipEditingHook['handleResetClipPosition'];
  handleResetClipsPosition: ClipEditingHook['handleResetClipsPosition'];
  handleSplitSelectedClip: ClipEditingHook['handleSplitSelectedClip'];
  handleSplitClipAtTime: ClipEditingHook['handleSplitClipAtTime'];
  handleSplitClipsAtPlayhead: ClipEditingHook['handleSplitClipsAtPlayhead'];
  handleToggleMuteClips: ClipEditingHook['handleToggleMuteClips'];
  handleToggleMute: ClipEditingHook['handleToggleMute'];
  handleDetachAudioClip: ClipEditingHook['handleDetachAudioClip'];
  handleTrackPopoverChange: TimelineTrackManagementHook['handleTrackPopoverChange'];
  handleMoveTrack: TimelineTrackManagementHook['handleMoveTrack'];
  handleRemoveTrack: TimelineTrackManagementHook['handleRemoveTrack'];
  moveSelectedClipToTrack: TimelineTrackManagementHook['moveSelectedClipToTrack'];
  moveSelectedClipsToTrack: TimelineTrackManagementHook['moveSelectedClipsToTrack'];
  moveClipToRow: TimelineTrackManagementHook['moveClipToRow'];
  createTrackAndMoveClip: TimelineTrackManagementHook['createTrackAndMoveClip'];
  uploadFiles: TimelineUploadFiles;
  applyEdit: TimelineApplyEdit;
  patchRegistry: TimelinePatchRegistry;
  unpatchRegistry: TimelineUnpatchRegistry;
  registerAsset: TimelineRegisterAsset;
  onDoubleClickAsset?: (assetKey: string, clipId?: string) => void;
  setLightboxAssetKey?: (assetKey: string | null) => void;
}

/**
 * @deprecated Prefer `TimelineEditorDataContextValue` and `TimelineEditorOpsContextValue`.
 */
export interface TimelineEditorContextValue extends TimelineEditorDataContextValue, TimelineEditorOpsContextValue {}

export interface TimelineChromeContextValue {
  timelineName: string | null;
  saveStatus: SaveStatus;
  isConflictExhausted: boolean;
  renderStatus: RenderStatus;
  renderLog: string;
  renderDirty: boolean;
  renderProgress: TimelineRenderProgress;
  renderResultUrl: string | null;
  renderResultFilename: string | null;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  checkpoints: TimelineCheckpoints;
  jumpToCheckpoint: TimelineJumpToCheckpoint;
  createManualCheckpoint: TimelineCreateManualCheckpoint;
  setScaleWidth: TimelineSetScaleWidth;
  handleAddTrack: TimelineTrackManagementHook['handleAddTrack'];
  handleClearUnusedTracks: TimelineTrackManagementHook['handleClearUnusedTracks'];
  unusedTrackCount: TimelineTrackManagementHook['unusedTrackCount'];
  handleAddText: ClipEditingHook['handleAddText'];
  handleAddTextAt: ClipEditingHook['handleAddTextAt'];
  reloadFromServer: TimelineReloadFromServer;
  retrySaveAfterConflict: TimelineRetrySaveAfterConflict;
  startRender: TimelineStartRender;
}

export interface TimelinePlaybackContextValue {
  currentTime: number;
  previewRef: TimelinePlaybackHook['previewRef'];
  playerContainerRef: TimelinePlaybackHook['playerContainerRef'];
  onPreviewTimeUpdate: TimelinePlaybackHook['onPreviewTimeUpdate'];
  formatTime: TimelinePlaybackHook['formatTime'];
}

export interface UseTimelineStateResult {
  store: TimelineStoreApi;
  editor: TimelineEditorContextValue;
  editorData: TimelineEditorDataContextValue;
  editorOps: TimelineEditorOpsContextValue;
  chrome: TimelineChromeContextValue;
  playback: TimelinePlaybackContextValue;
}
