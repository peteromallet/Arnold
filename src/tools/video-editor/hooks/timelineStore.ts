import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type MutableRefObject,
  type PropsWithChildren,
  type RefObject,
  type SetStateAction,
} from 'react';
import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore, type StoreApi } from 'zustand/vanilla';
import { defaultPreferences, type EditorPreferences } from '@/tools/video-editor/hooks/useEditorPreferences';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types';
import { createInteractionState } from '@/tools/video-editor/lib/interaction-state';
import {
  createMobileInteractionPolicy,
  resolveInputModalityFromPointerType,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import type { DropPosition } from '@/tools/video-editor/lib/drop-position';
import type { TimelineCanvasHandle } from '@/tools/video-editor/types/timeline-canvas';
import type { PreviewHandle } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview';

export interface TimelineAvailabilityState {
  mounted: boolean;
}

export interface TimelineStoreBootstrap {
  data: TimelineEditorDataContextValue;
  ops: TimelineEditorOpsContextValue;
  chrome: TimelineChromeContextValue;
  playback: TimelinePlaybackContextValue;
}

export interface TimelineStoreState extends TimelineStoreBootstrap {
  availability: TimelineAvailabilityState;
  setMounted: (mounted: boolean) => void;
  syncDataSlice: (data: TimelineEditorDataContextValue) => void;
  syncOpsSlice: (ops: TimelineEditorOpsContextValue) => void;
  syncChromeSlice: (chrome: TimelineChromeContextValue) => void;
  syncPlaybackSlice: (playback: TimelinePlaybackContextValue) => void;
  syncSlices: (bootstrap: Partial<TimelineStoreBootstrap>) => void;
  resetSlices: () => void;
}

export type TimelineStoreApi = StoreApi<TimelineStoreState>;

const initialInteractionPolicy = createMobileInteractionPolicy('desktop');
const emptyDropPosition: DropPosition = {
  time: 0,
  rowIndex: 0,
  trackId: undefined,
  trackKind: null,
  trackName: '',
  isNewTrack: false,
  isReject: false,
  newTrackKind: null,
  screenCoords: {
    rowTop: 0,
    rowLeft: 0,
    rowWidth: 0,
    rowHeight: 0,
    clipLeft: 0,
    clipWidth: 0,
    ghostCenter: 0,
  },
};

const noop = (): void => {};
const noopAsync = async (): Promise<void> => {};
const noopSetState = <T,>(_value: SetStateAction<T>): void => {};
const clonePreferences = (): EditorPreferences => ({
  ...defaultPreferences,
  assetPanel: {
    ...defaultPreferences.assetPanel,
    hidden: [...defaultPreferences.assetPanel.hidden],
  },
});

function createMutableRef<T>(value: T): MutableRefObject<T> {
  return { current: value };
}

function createNullableRef<T>(): RefObject<T> {
  return { current: null };
}

function createInitialDataSlice(): TimelineEditorDataContextValue {
  const selectedClipIds = new Set<string>();
  const selectedClipIdsRef = createMutableRef(new Set<string>());
  const additiveSelectionRef = createMutableRef(false);
  const dataRef = createMutableRef<TimelineEditorDataContextValue['data']>(null);
  const pendingOpsRef = createMutableRef(0);
  const interactionStateRef = createMutableRef(createInteractionState());
  const editAreaRef = createMutableRef<HTMLElement | null>(null);

  return {
    data: null,
    resolvedConfig: null,
    deviceClass: initialInteractionPolicy.deviceClass,
    inputModality: initialInteractionPolicy.inputModality,
    interactionMode: initialInteractionPolicy.interactionMode,
    gestureOwner: initialInteractionPolicy.gestureOwner,
    precisionEnabled: initialInteractionPolicy.precisionEnabled,
    contextTarget: initialInteractionPolicy.contextTarget,
    inspectorTarget: initialInteractionPolicy.inspectorTarget,
    interactionPolicy: initialInteractionPolicy,
    selectedClipId: null,
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
    selectedTrackId: null,
    primaryClipId: null,
    selectedClip: null,
    selectedTrack: null,
    selectedClipHasPredecessor: false,
    compositionSize: { width: 0, height: 0 },
    trackScaleMap: {},
    scale: 5,
    scaleWidth: defaultPreferences.scaleWidth,
    isLoading: false,
    dataRef,
    pendingOpsRef,
    interactionStateRef,
    coordinator: {
      update: () => emptyDropPosition,
      showSecondaryGhosts: noop,
      end: noop,
      lastPosition: null,
      editAreaRef,
    },
    indicatorRef: createMutableRef(null),
    editAreaRef,
    preferences: clonePreferences(),
    timelineRef: createNullableRef<TimelineCanvasHandle>(),
    timelineWrapperRef: createNullableRef<HTMLDivElement>(),
  };
}

function createInitialOpsSlice(): TimelineEditorOpsContextValue {
  const setInputModality: TimelineEditorOpsContextValue['setInputModality'] = noop;
  const setInteractionMode: TimelineEditorOpsContextValue['setInteractionMode'] = noop;
  const setGestureOwner: TimelineEditorOpsContextValue['setGestureOwner'] = noop;
  const setPrecisionEnabled: TimelineEditorOpsContextValue['setPrecisionEnabled'] = noop;
  const setContextTarget: TimelineEditorOpsContextValue['setContextTarget'] = noop;
  const setInspectorTarget: TimelineEditorOpsContextValue['setInspectorTarget'] = noop;
  const setSelectedClipId: TimelineEditorOpsContextValue['setSelectedClipId'] = noopSetState;
  const setSelectedTrackId: TimelineEditorOpsContextValue['setSelectedTrackId'] = noopSetState;
  const selectClip: TimelineEditorOpsContextValue['selectClip'] = noop;
  const selectClips: TimelineEditorOpsContextValue['selectClips'] = noop;
  const addToSelection: TimelineEditorOpsContextValue['addToSelection'] = noop;
  const clearSelection: TimelineEditorOpsContextValue['clearSelection'] = noop;
  const setActiveClipTab: TimelineEditorOpsContextValue['setActiveClipTab'] = noop;
  const setAssetPanelState: TimelineEditorOpsContextValue['setAssetPanelState'] = noop;
  const registerGenerationAsset: TimelineEditorOpsContextValue['registerGenerationAsset'] = () => null;
  const onCursorDrag: TimelineEditorOpsContextValue['onCursorDrag'] = noop;
  const onClickTimeArea: TimelineEditorOpsContextValue['onClickTimeArea'] = () => undefined;
  const onActionResizeStart: TimelineEditorOpsContextValue['onActionResizeStart'] = noop;
  const onClipEdgeResizeEnd: TimelineEditorOpsContextValue['onClipEdgeResizeEnd'] = noop;
  const onOverlayChange: TimelineEditorOpsContextValue['onOverlayChange'] = noop;
  const onTimelineDragOver: TimelineEditorOpsContextValue['onTimelineDragOver'] = noop;
  const onTimelineDragLeave: TimelineEditorOpsContextValue['onTimelineDragLeave'] = noop;
  const onTimelineDrop: TimelineEditorOpsContextValue['onTimelineDrop'] = noopAsync;
  const handleAssetDrop: TimelineEditorOpsContextValue['handleAssetDrop'] = noop;
  const handleUpdateClips: TimelineEditorOpsContextValue['handleUpdateClips'] = noop;
  const handleUpdateClipsDeep: TimelineEditorOpsContextValue['handleUpdateClipsDeep'] = noop;
  const handleDeleteClips: TimelineEditorOpsContextValue['handleDeleteClips'] = noop;
  const handleDeleteClip: TimelineEditorOpsContextValue['handleDeleteClip'] = noop;
  const handleSelectedClipChange: TimelineEditorOpsContextValue['handleSelectedClipChange'] = noop;
  const handleResetClipPosition: TimelineEditorOpsContextValue['handleResetClipPosition'] = noop;
  const handleResetClipsPosition: TimelineEditorOpsContextValue['handleResetClipsPosition'] = noop;
  const handleSplitSelectedClip: TimelineEditorOpsContextValue['handleSplitSelectedClip'] = noop;
  const handleSplitClipAtTime: TimelineEditorOpsContextValue['handleSplitClipAtTime'] = noop;
  const handleSplitClipsAtPlayhead: TimelineEditorOpsContextValue['handleSplitClipsAtPlayhead'] = noop;
  const handleToggleMuteClips: TimelineEditorOpsContextValue['handleToggleMuteClips'] = noop;
  const handleToggleMute: TimelineEditorOpsContextValue['handleToggleMute'] = noop;
  const handleDetachAudioClip: TimelineEditorOpsContextValue['handleDetachAudioClip'] = noop;
  const handleTrackPopoverChange: TimelineEditorOpsContextValue['handleTrackPopoverChange'] = noop;
  const handleMoveTrack: TimelineEditorOpsContextValue['handleMoveTrack'] = noop;
  const handleRemoveTrack: TimelineEditorOpsContextValue['handleRemoveTrack'] = noop;
  const moveSelectedClipToTrack: TimelineEditorOpsContextValue['moveSelectedClipToTrack'] = noop;
  const moveSelectedClipsToTrack: TimelineEditorOpsContextValue['moveSelectedClipsToTrack'] = noop;
  const moveClipToRow: TimelineEditorOpsContextValue['moveClipToRow'] = noop;
  const createTrackAndMoveClip: TimelineEditorOpsContextValue['createTrackAndMoveClip'] = noop;
  const uploadFiles: TimelineEditorOpsContextValue['uploadFiles'] = noopAsync;
  const applyEdit: TimelineEditorOpsContextValue['applyEdit'] = noop;
  const patchRegistry: TimelineEditorOpsContextValue['patchRegistry'] = noop;
  const unpatchRegistry: TimelineEditorOpsContextValue['unpatchRegistry'] = noop;
  const registerAsset: TimelineEditorOpsContextValue['registerAsset'] = noopAsync;

  return {
    setInputModality,
    setInputModalityFromPointerType: resolveInputModalityFromPointerType,
    setInteractionMode,
    setGestureOwner,
    setPrecisionEnabled,
    setContextTarget,
    setInspectorTarget,
    setSelectedClipId,
    isClipSelected: () => false,
    selectClip,
    selectClips,
    replaceTimelineSelection: selectClips,
    addToSelection,
    clearSelection,
    setSelectedTrackId,
    setActiveClipTab,
    setAssetPanelState,
    registerGenerationAsset,
    onCursorDrag,
    onClickTimeArea,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onOverlayChange,
    onTimelineDragOver,
    onTimelineDragLeave,
    onTimelineDrop,
    handleAssetDrop,
    handleUpdateClips,
    handleUpdateClipsDeep,
    handleDeleteClips,
    handleDeleteClip,
    handleSelectedClipChange,
    handleResetClipPosition,
    handleResetClipsPosition,
    handleSplitSelectedClip,
    handleSplitClipAtTime,
    handleSplitClipsAtPlayhead,
    handleToggleMuteClips,
    handleToggleMute,
    handleDetachAudioClip,
    handleTrackPopoverChange,
    handleMoveTrack,
    handleRemoveTrack,
    moveSelectedClipToTrack,
    moveSelectedClipsToTrack,
    moveClipToRow,
    createTrackAndMoveClip,
    uploadFiles,
    applyEdit,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
  };
}

function createInitialChromeSlice(): TimelineChromeContextValue {
  return {
    timelineName: null,
    saveStatus: 'saved',
    isConflictExhausted: false,
    renderStatus: 'idle',
    renderLog: '',
    renderDirty: false,
    renderProgress: null,
    renderResultUrl: null,
    renderResultFilename: null,
    undo: noop,
    redo: noop,
    canUndo: false,
    canRedo: false,
    checkpoints: [],
    jumpToCheckpoint: noop,
    createManualCheckpoint: noopAsync,
    setScaleWidth: noop,
    handleAddTrack: noop,
    handleClearUnusedTracks: noop,
    unusedTrackCount: 0,
    handleAddText: noop,
    handleAddTextAt: noop,
    reloadFromServer: noopAsync,
    retrySaveAfterConflict: noopAsync,
    startRender: noopAsync,
  };
}

function createInitialPlaybackSlice(): TimelinePlaybackContextValue {
  return {
    currentTime: 0,
    previewRef: createNullableRef<PreviewHandle>(),
    playerContainerRef: createNullableRef<HTMLDivElement>(),
    onPreviewTimeUpdate: noop,
    formatTime: (time) => `${time}`,
  };
}

function createInitialSlices(): TimelineStoreBootstrap {
  return {
    data: createInitialDataSlice(),
    ops: createInitialOpsSlice(),
    chrome: createInitialChromeSlice(),
    playback: createInitialPlaybackSlice(),
  };
}

export function createTimelineStore(bootstrap?: Partial<TimelineStoreBootstrap>): TimelineStoreApi {
  const initialSlices = createInitialSlices();
  const seededSlices = {
    data: bootstrap?.data ?? initialSlices.data,
    ops: bootstrap?.ops ?? initialSlices.ops,
    chrome: bootstrap?.chrome ?? initialSlices.chrome,
    playback: bootstrap?.playback ?? initialSlices.playback,
  };
  const initialMounted = bootstrap !== undefined;

  return createStore<TimelineStoreState>((set) => ({
    availability: { mounted: initialMounted },
    ...seededSlices,
    setMounted: (mounted) => {
      set((state) => (
        state.availability.mounted === mounted
          ? state
          : { availability: { mounted } }
      ));
    },
    syncDataSlice: (data) => {
      set((state) => (
        state.data === data && state.availability.mounted
          ? state
          : {
              availability: state.availability.mounted ? state.availability : { mounted: true },
              data,
            }
      ));
    },
    syncOpsSlice: (ops) => {
      set((state) => (
        state.ops === ops && state.availability.mounted
          ? state
          : {
              availability: state.availability.mounted ? state.availability : { mounted: true },
              ops,
            }
      ));
    },
    syncChromeSlice: (chrome) => {
      set((state) => (
        state.chrome === chrome && state.availability.mounted
          ? state
          : {
              availability: state.availability.mounted ? state.availability : { mounted: true },
              chrome,
            }
      ));
    },
    syncPlaybackSlice: (playback) => {
      set((state) => (
        state.playback === playback && state.availability.mounted
          ? state
          : {
              availability: state.availability.mounted ? state.availability : { mounted: true },
              playback,
            }
      ));
    },
    syncSlices: (bootstrap) => {
      set((state) => {
        const nextData = bootstrap.data ?? state.data;
        const nextOps = bootstrap.ops ?? state.ops;
        const nextChrome = bootstrap.chrome ?? state.chrome;
        const nextPlayback = bootstrap.playback ?? state.playback;
        const nextMounted = true;

        if (
          state.data === nextData
          && state.ops === nextOps
          && state.chrome === nextChrome
          && state.playback === nextPlayback
          && state.availability.mounted === nextMounted
        ) {
          return state;
        }

        return {
          availability: { mounted: nextMounted },
          data: nextData,
          ops: nextOps,
          chrome: nextChrome,
          playback: nextPlayback,
        };
      });
    },
    resetSlices: () => {
      set(() => ({
        availability: { mounted: false },
        ...createInitialSlices(),
      }));
    },
  }));
}

const TimelineStoreContext = createContext<TimelineStoreApi | null>(null);
const fallbackTimelineStore = createTimelineStore();

export function TimelineStoreProvider({
  store,
  children,
}: PropsWithChildren<{ store: TimelineStoreApi }>) {
  return createElement(TimelineStoreContext.Provider, { value: store }, children);
}

export function useTimelineStoreApi(): TimelineStoreApi {
  const store = useContext(TimelineStoreContext);
  if (!store) {
    throw new Error('useTimelineStoreApi must be used within TimelineStoreProvider');
  }

  return store;
}

export function useTimelineStoreApiSafe(): TimelineStoreApi | null {
  return useContext(TimelineStoreContext);
}

function useBoundTimelineStore<T>(
  selector: (state: TimelineStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(useTimelineStoreApi(), selector, equalityFn);
}

function useSafeTimelineStoreValue<T>(
  selector: (state: TimelineStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T | null {
  const providedStore = useTimelineStoreApiSafe();
  const store = providedStore ?? fallbackTimelineStore;
  const mounted = useStoreWithEqualityFn(store, (state) => state.availability.mounted);
  const value = useStoreWithEqualityFn(store, selector, equalityFn);
  return providedStore && mounted ? value : null;
}

export function useTimelineAvailabilityState() {
  const providedStore = useTimelineStoreApiSafe();
  const store = providedStore ?? fallbackTimelineStore;
  const mounted = useStoreWithEqualityFn(store, (state) => state.availability.mounted);

  return useMemo(() => ({
    hasProvider: providedStore !== null,
    mounted: providedStore !== null && mounted,
  }), [mounted, providedStore]);
}

export function useTimelineStoreLifecycle() {
  return useBoundTimelineStore((state) => ({
    mounted: state.availability.mounted,
    setMounted: state.setMounted,
    syncDataSlice: state.syncDataSlice,
    syncOpsSlice: state.syncOpsSlice,
    syncChromeSlice: state.syncChromeSlice,
    syncPlaybackSlice: state.syncPlaybackSlice,
    syncSlices: state.syncSlices,
    resetSlices: state.resetSlices,
  }), shallow);
}

export function useTimelineDataSlice(): TimelineEditorDataContextValue {
  return useBoundTimelineStore((state) => state.data, shallow);
}

export function useTimelineDataSelector<T>(
  selector: (data: TimelineEditorDataContextValue) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useBoundTimelineStore((state) => selector(state.data), equalityFn);
}

export function useTimelineDataSliceSafe(): TimelineEditorDataContextValue | null {
  return useSafeTimelineStoreValue((state) => state.data, shallow);
}

export function useTimelineOpsSlice(): TimelineEditorOpsContextValue {
  return useBoundTimelineStore((state) => state.ops, shallow);
}

export function useTimelineOpsSelector<T>(
  selector: (ops: TimelineEditorOpsContextValue) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useBoundTimelineStore((state) => selector(state.ops), equalityFn);
}

export function useTimelineOpsSliceSafe(): TimelineEditorOpsContextValue | null {
  return useSafeTimelineStoreValue((state) => state.ops, shallow);
}

export function useTimelineChromeSlice(): TimelineChromeContextValue {
  return useBoundTimelineStore((state) => state.chrome, shallow);
}

export function useTimelineChromeSelector<T>(
  selector: (chrome: TimelineChromeContextValue) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useBoundTimelineStore((state) => selector(state.chrome), equalityFn);
}

export function useTimelineChromeSliceSafe(): TimelineChromeContextValue | null {
  return useSafeTimelineStoreValue((state) => state.chrome, shallow);
}

export function useTimelinePlaybackSlice(): TimelinePlaybackContextValue {
  return useBoundTimelineStore((state) => state.playback, shallow);
}

export function useTimelinePlaybackSelector<T>(
  selector: (playback: TimelinePlaybackContextValue) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useBoundTimelineStore((state) => selector(state.playback), equalityFn);
}

export function useTimelinePlaybackSliceSafe(): TimelinePlaybackContextValue | null {
  return useSafeTimelineStoreValue((state) => state.playback, shallow);
}

export function useTimelineMutableAdapters() {
  return useBoundTimelineStore((state) => ({
    dataRef: state.data.dataRef,
    pendingOpsRef: state.data.pendingOpsRef,
    interactionStateRef: state.data.interactionStateRef,
    selectedClipIdsRef: state.data.selectedClipIdsRef,
    additiveSelectionRef: state.data.additiveSelectionRef,
  }), shallow);
}

export function useTimelineMutableAdaptersSafe() {
  return useSafeTimelineStoreValue((state) => ({
    dataRef: state.data.dataRef,
    pendingOpsRef: state.data.pendingOpsRef,
    interactionStateRef: state.data.interactionStateRef,
    selectedClipIdsRef: state.data.selectedClipIdsRef,
    additiveSelectionRef: state.data.additiveSelectionRef,
  }), shallow);
}

export const useTimelineEditorData = useTimelineDataSlice;
export const useTimelineEditorDataSafe = useTimelineDataSliceSafe;
export const useTimelineEditorOps = useTimelineOpsSlice;
export const useTimelineEditorOpsSafe = useTimelineOpsSliceSafe;
export const useTimelineChromeContext = useTimelineChromeSlice;
export const useTimelineChromeContextSafe = useTimelineChromeSliceSafe;
export const useTimelinePlaybackContext = useTimelinePlaybackSlice;
export const useTimelinePlaybackContextSafe = useTimelinePlaybackSliceSafe;
