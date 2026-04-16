import { memo, useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { shallow } from 'zustand/shallow';
import {
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import type { Shot } from '@/domains/generation/types';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useShots } from '@/shared/contexts/ShotsContext';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { VideoGenerationModal } from '@/tools/travel-between-images/components/VideoGenerationModal';
import '@/tools/video-editor/components/TimelineEditor/timeline-overrides.css';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { ClipAction } from '@/tools/video-editor/components/TimelineEditor/ClipAction';
import { DropIndicator } from '@/tools/video-editor/components/TimelineEditor/DropIndicator';
import { TimelineCanvas } from '@/tools/video-editor/components/TimelineEditor/TimelineCanvas';
import { ROW_HEIGHT, TIMELINE_START_LEFT } from '@/tools/video-editor/lib/coordinate-utils';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import {
  useTimelineChromeSelector,
  useTimelineDataSelector,
  useTimelineOpsSelector,
} from '@/tools/video-editor/hooks/timelineStore';
import { useClipDrag } from '@/tools/video-editor/hooks/useClipDrag';
import { useActiveTaskClips } from '@/tools/video-editor/hooks/useActiveTaskClips';
import { useFinalVideoAvailable } from '@/tools/video-editor/hooks/useFinalVideoAvailable';
import { useMarqueeSelect } from '@/tools/video-editor/hooks/useMarqueeSelect';
import { usePinnedGroupSync, usePinnedShotGroups } from '@/tools/video-editor/hooks/usePinnedShotGroups';
import { useShotGroups } from '@/tools/video-editor/hooks/useShotGroups';
import { useStaleVariants } from '@/tools/video-editor/hooks/useStaleVariants';
import { useShotGroupHandlers } from '@/tools/video-editor/hooks/useShotGroupHandlers';
import { useSwitchToFinalVideo } from '@/tools/video-editor/hooks/useSwitchToFinalVideo';
import { useTimelineScale } from '@/tools/video-editor/hooks/useTimelineScale';
import { buildDuplicateClipEdit } from '@/tools/video-editor/lib/duplicate-clip';
import { duplicateGenerationAsset } from '@/tools/video-editor/lib/generation-utils';
import {
  clampClipToMediaDuration,
  convertOverhangToHold,
  detectClipOverhang,
} from '@/tools/video-editor/lib/overhang';
import type { TimelineActionResizeStart, TimelineClipEdgeResizeEnd } from '@/tools/video-editor/hooks/useTimelineState.types';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

const EMPTY_ASSET_GENERATION_MAP: Record<string, string> = {};
const log = import.meta.env.DEV ? (...args: Parameters<typeof console.log>) => console.log(...args) : () => {};

interface DoubleClickPinnedGroup {
  shotId: string;
  clipIds: string[];
}

interface DoubleClickFinalVideo {
  id: string;
  location?: string | null;
}

type VideoClipDoubleClickResolution =
  | { type: 'lightbox'; assetKey: string; generationId?: string }
  | { type: 'video-modal'; shotId: string; reason: 'pinned-group' | 'final-video-file' }
  | { type: 'none' };

export function resolveVideoClipDoubleClickResolution({
  clipId,
  assetKey,
  generationId,
  fileUrl,
  pinnedShotGroups,
  finalVideoMap,
}: {
  clipId: string;
  assetKey?: string;
  generationId?: string;
  fileUrl?: string;
  pinnedShotGroups: DoubleClickPinnedGroup[];
  finalVideoMap: Map<string, DoubleClickFinalVideo>;
}): VideoClipDoubleClickResolution {
  if (assetKey) {
    return { type: 'lightbox', assetKey, generationId };
  }

  const pinnedGroup = pinnedShotGroups.find((group) => group.clipIds.includes(clipId));
  if (pinnedGroup) {
    return { type: 'video-modal', shotId: pinnedGroup.shotId, reason: 'pinned-group' };
  }

  if (fileUrl) {
    for (const [shotId, finalVideo] of finalVideoMap.entries()) {
      if (finalVideo.location === fileUrl) {
        return { type: 'video-modal', shotId, reason: 'final-video-file' };
      }
    }
  }

  return { type: 'none' };
}

function useStableValue<T extends Record<string, string>>(value: T): T {
  const ref = useRef(value);
  const previous = ref.current;
  const previousKeys = Object.keys(previous);
  const nextKeys = Object.keys(value);
  const isEqual = previousKeys.length === nextKeys.length
    && nextKeys.every((key) => previous[key] === value[key]);

  if (!isEqual) {
    ref.current = value;
  }

  return ref.current;
}

export function resolveSelectedGenerationIdsForShotCreation({
  rows,
  meta,
  assetGenerationMap,
  selectedClipIds,
}: {
  rows: TimelineRow[];
  meta: Record<string, ClipMeta>;
  assetGenerationMap: Record<string, string>;
  selectedClipIds: Iterable<string>;
}) {
  const selectedSet = new Set(selectedClipIds);
  if (selectedSet.size === 0) {
    return { canCreateShot: false, generationIds: [] as string[] };
  }

  const orderedSelections = rows
      .flatMap((row, trackIndex) => row.actions
      .filter((action) => selectedSet.has(action.id))
      .map((action) => {
        const assetKey = meta[action.id]?.asset;
        const generationId = assetKey ? assetGenerationMap[assetKey] : undefined;

        return {
          trackIndex,
          start: action.start,
          generationId,
        };
      }))
    .sort((left, right) => left.trackIndex - right.trackIndex || left.start - right.start);

  const generationIds = orderedSelections
    .map((selection) => selection.generationId)
    .filter((generationId): generationId is string => typeof generationId === 'string' && generationId.length > 0);

  return {
    canCreateShot: orderedSelections.length > 0 && generationIds.length === orderedSelections.length,
    generationIds,
  };
}

export function resolveWaveformAudioSrc(
  clip: ResolvedTimelineClip | undefined,
  track: TrackDefinition | undefined,
): string | undefined {
  if (!clip || !track || !clip.assetEntry?.src) {
    return undefined;
  }

  if (clip.clipType === 'text' || clip.clipType === 'effect-layer') {
    return undefined;
  }

  if (track.kind === 'audio') {
    return clip.volume === 0 ? undefined : clip.assetEntry.src;
  }

  if (
    track.kind === 'visual'
    && clip.assetEntry.type?.startsWith('video/')
    && (clip.volume ?? 1) > 0
  ) {
    return clip.assetEntry.src;
  }

  return undefined;
}

function TimelineEditorComponent() {
  useRenderDiagnostic('TimelineEditor');
  const [newTrackDropLabel, setNewTrackDropLabel] = useState<string | null>(null);
  const [videoModalShot, setVideoModalShot] = useState<Shot | null>(null);
  const [videoModalShowImages, setVideoModalShowImages] = useState(false);
  const [duplicatingClipId, setDuplicatingClipId] = useState<string | null>(null);
  const { createShot, isCreating } = useShotCreation();
  const { navigateToShot } = useShotNavigation();
  const { selectedProjectId } = useProjectSelectionContext();
  const { shots } = useShots();
  const {
    data,
    resolvedConfig,
    timelineRef,
    timelineWrapperRef,
    dataRef,
    deviceClass,
    inputModality,
    interactionMode,
    gestureOwner,
    primaryClipId,
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
    scale,
    scaleWidth,
    coordinator,
    indicatorRef,
    editAreaRef,
    selectedTrackId,
    interactionStateRef,
  } = useTimelineDataSelector((timeline) => ({
    data: timeline.data,
    resolvedConfig: timeline.resolvedConfig,
    timelineRef: timeline.timelineRef,
    timelineWrapperRef: timeline.timelineWrapperRef,
    dataRef: timeline.dataRef,
    deviceClass: timeline.deviceClass,
    inputModality: timeline.inputModality,
    interactionMode: timeline.interactionMode,
    gestureOwner: timeline.gestureOwner,
    primaryClipId: timeline.primaryClipId,
    selectedClipIds: timeline.selectedClipIds,
    selectedClipIdsRef: timeline.selectedClipIdsRef,
    additiveSelectionRef: timeline.additiveSelectionRef,
    scale: timeline.scale,
    scaleWidth: timeline.scaleWidth,
    coordinator: timeline.coordinator,
    indicatorRef: timeline.indicatorRef,
    editAreaRef: timeline.editAreaRef,
    selectedTrackId: timeline.selectedTrackId,
    interactionStateRef: timeline.interactionStateRef,
  }), shallow);
  const {
    applyEdit,
    moveClipToRow,
    createTrackAndMoveClip,
    selectClip,
    selectClips,
    addToSelection,
    clearSelection,
    isClipSelected,
    setSelectedTrackId,
    handleTrackPopoverChange,
    handleMoveTrack,
    handleRemoveTrack,
    handleSplitClipAtTime,
    handleSplitClipsAtPlayhead,
    handleDeleteClips,
    handleDeleteClip,
    handleToggleMuteClips,
    onCursorDrag,
    onClickTimeArea,
    setGestureOwner,
    setInputModalityFromPointerType,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onTimelineDragOver,
    onTimelineDragLeave,
    onTimelineDrop,
    onDoubleClickAsset,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
    registerGenerationAsset,
  } = useTimelineOpsSelector((ops) => ({
    applyEdit: ops.applyEdit,
    moveClipToRow: ops.moveClipToRow,
    createTrackAndMoveClip: ops.createTrackAndMoveClip,
    selectClip: ops.selectClip,
    selectClips: ops.selectClips,
    addToSelection: ops.addToSelection,
    clearSelection: ops.clearSelection,
    isClipSelected: ops.isClipSelected,
    setSelectedTrackId: ops.setSelectedTrackId,
    handleTrackPopoverChange: ops.handleTrackPopoverChange,
    handleMoveTrack: ops.handleMoveTrack,
    handleRemoveTrack: ops.handleRemoveTrack,
    handleSplitClipAtTime: ops.handleSplitClipAtTime,
    handleSplitClipsAtPlayhead: ops.handleSplitClipsAtPlayhead,
    handleDeleteClips: ops.handleDeleteClips,
    handleDeleteClip: ops.handleDeleteClip,
    handleToggleMuteClips: ops.handleToggleMuteClips,
    onCursorDrag: ops.onCursorDrag,
    onClickTimeArea: ops.onClickTimeArea,
    setGestureOwner: ops.setGestureOwner,
    setInputModalityFromPointerType: ops.setInputModalityFromPointerType,
    onActionResizeStart: ops.onActionResizeStart,
    onClipEdgeResizeEnd: ops.onClipEdgeResizeEnd,
    onTimelineDragOver: ops.onTimelineDragOver,
    onTimelineDragLeave: ops.onTimelineDragLeave,
    onTimelineDrop: ops.onTimelineDrop,
    onDoubleClickAsset: ops.onDoubleClickAsset,
    patchRegistry: ops.patchRegistry,
    unpatchRegistry: ops.unpatchRegistry,
    registerAsset: ops.registerAsset,
    registerGenerationAsset: ops.registerGenerationAsset,
  }), shallow);
  const {
    handleAddTrack,
    handleAddTextAt,
    handleClearUnusedTracks,
    unusedTrackCount,
  } = useTimelineChromeSelector((chrome) => ({
    handleAddTrack: chrome.handleAddTrack,
    handleAddTextAt: chrome.handleAddTextAt,
    handleClearUnusedTracks: chrome.handleClearUnusedTracks,
    unusedTrackCount: chrome.unusedTrackCount,
  }), shallow);
  const trackSensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const resizeStartHandler: TimelineActionResizeStart = onActionResizeStart;
  const clipEdgeResizeEndHandler: TimelineClipEdgeResizeEnd = onClipEdgeResizeEnd;
  const isInteractionActive = useCallback(() => {
    return interactionStateRef.current.drag || interactionStateRef.current.resize;
  }, [interactionStateRef]);

  // useClipDrag handles all internal clip drag interactions (horizontal moves,
  // cross-track moves, and new-track creation) using the same fixed-position
  // drop indicators as external HTML5 drag-drop.
  const { dragSessionRef } = useClipDrag({
    timelineWrapperRef,
    dataRef,
    interactionStateRef,
    deviceClass,
    interactionMode,
    gestureOwner,
    setGestureOwner,
    setInputModalityFromPointerType,
    moveClipToRow,
    createTrackAndMoveClip,
    applyEdit,
    selectClip,
    selectClips,
    selectedClipIdsRef,
    additiveSelectionRef,
    coordinator,
    rowHeight: ROW_HEIGHT,
    scale,
    scaleWidth,
    startLeft: TIMELINE_START_LEFT,
  });

  const { marqueeRect, onPointerDown: onMarqueePointerDown } = useMarqueeSelect({
    editAreaRef,
    deviceClass,
    interactionMode,
    gestureOwner,
    setGestureOwner,
    setInputModalityFromPointerType,
    selectClips,
    addToSelection,
    clearSelection,
  });

  const { staleAssetKeys, dismissedAssetKeys, generationAssetKeys, dismissAsset, updateAssetToCurrentVariant } = useStaleVariants({
    registry: resolvedConfig?.registry,
    patchRegistry,
    registerAsset,
  });
  const { activeTaskAssetKeys } = useActiveTaskClips({ registry: resolvedConfig?.registry });
  const { finalVideoMap, dismissFinalVideo } = useFinalVideoAvailable();

  useLayoutEffect(() => {
    const wrapper = timelineWrapperRef.current;
    const nextEditArea = wrapper?.querySelector<HTMLElement>('.timeline-canvas-edit-area') ?? null;
    editAreaRef.current = nextEditArea;

    return () => {
      if (editAreaRef.current === nextEditArea) {
        editAreaRef.current = null;
      }
    };
  }, [data, editAreaRef, timelineWrapperRef]);

  const scaleCount = useMemo(() => {
    if (!data) {
      return 1;
    }

    let maxEnd = 0;
    for (const row of data.rows) {
      for (const action of row.actions) {
        maxEnd = Math.max(maxEnd, action.end);
      }
    }

    return Math.ceil((maxEnd + 20) / scale) + 1;
  }, [data, scale]);

  const thumbnailMap = useMemo<Record<string, string>>(() => {
    if (!resolvedConfig) {
      return {};
    }

    return resolvedConfig.clips.reduce<Record<string, string>>((acc, clip) => {
      if (clip.clipType === 'text' || !clip.assetEntry) {
        return acc;
      }

      if (clip.assetEntry.type?.startsWith('image')) {
        acc[clip.id] = clip.assetEntry.src;
      } else if (clip.assetEntry.type?.startsWith('video') && clip.assetEntry.thumbnailUrl) {
        acc[clip.id] = clip.assetEntry.thumbnailUrl;
      }

      return acc;
    }, {});
  }, [resolvedConfig]);

  const handleClipSelect = useCallback((clipId: string, trackId: string) => {
    selectClip(clipId);
    setSelectedTrackId(trackId);
  }, [selectClip, setSelectedTrackId]);

  const { pixelsPerSecond, pixelToTime } = useTimelineScale({
    scale,
    scaleWidth,
    startLeft: TIMELINE_START_LEFT,
  });
  const shotGroups = useShotGroups(
    data?.rows ?? [],
    shots,
    data?.config.pinnedShotGroups,
  );
  const assetGenerationMap = useMemo<Record<string, string>>(() => {
    const assets = data?.registry?.assets;
    if (!assets) {
      return EMPTY_ASSET_GENERATION_MAP;
    }

    return Object.entries(assets).reduce<Record<string, string>>((acc, [assetKey, assetEntry]) => {
      if (typeof assetEntry?.generationId === 'string' && assetEntry.generationId.length > 0) {
        acc[assetKey] = assetEntry.generationId;
      }
      return acc;
    }, {});
  }, [data?.registry?.assets]);
  const stableAssetGenerationMap = useStableValue(assetGenerationMap);
  const resolvedClipMap = useMemo(() => {
    if (!resolvedConfig) {
      return new Map<string, ResolvedTimelineClip>();
    }

    return new Map(resolvedConfig.clips.map((clip) => [clip.id, clip]));
  }, [resolvedConfig]);
  const trackMap = useMemo(() => {
    if (!resolvedConfig) {
      return new Map<string, TrackDefinition>();
    }

    return new Map(resolvedConfig.tracks.map((track) => [track.id, track]));
  }, [resolvedConfig]);

  const selectionShotCreationState = useMemo(() => {
    if (!data?.rows || !data?.meta) {
      return { canCreateShot: false, generationIds: [] as string[] };
    }

    return resolveSelectedGenerationIdsForShotCreation({
      rows: data.rows,
      meta: data.meta,
      assetGenerationMap: stableAssetGenerationMap,
      selectedClipIds,
    });
  }, [data?.rows, data?.meta, stableAssetGenerationMap, selectedClipIds]);

  const existingShotsForSelection = useMemo(() => {
    if (selectionShotCreationState.generationIds.length === 0 || !shots?.length) {
      return [] as Shot[];
    }

    return shots.filter((shot) => {
      const shotGenerationIds = new Set(
        (shot.images ?? [])
          .map((image) => image.generation_id)
          .filter((generationId): generationId is string => typeof generationId === 'string' && generationId.length > 0),
      );

      return selectionShotCreationState.generationIds.every((generationId) => shotGenerationIds.has(generationId));
    });
  }, [shots, selectionShotCreationState.generationIds]);

  const {
    pinGroup,
    unpinGroup,
  } = usePinnedShotGroups({
    dataRef,
    applyEdit,
  });

  const handleCreateShotFromSelection = useCallback(async (): Promise<Shot | null> => {
    if (!selectionShotCreationState.canCreateShot) {
      return null;
    }

    // Determine the track from the first selected clip
    const selectedClipId = [...selectedClipIds][0];
    const trackId = selectedClipId ? data?.meta[selectedClipId]?.track : undefined;

    const result = await createShot({ generationIds: selectionShotCreationState.generationIds });
    if (result?.shot && trackId) {
      // Auto-pin the new shot group on the timeline
      pinGroup(result.shot.id, trackId, [...selectedClipIds]);
    }
    if (result?.shot) {
      return result.shot;
    }
    return null;
  }, [createShot, data?.meta, pinGroup, selectedClipIds, selectionShotCreationState]);

  const handleGenerateVideoFromSelection = useCallback(async () => {
    if (!selectionShotCreationState.canCreateShot) {
      return;
    }

    // If exactly one existing shot already contains the selected generations, use it directly
    if (existingShotsForSelection.length === 1) {
      setVideoModalShot(existingShotsForSelection[0]);
      return;
    }

    const selectedClipId = [...selectedClipIds][0];
    const trackId = selectedClipId ? data?.meta[selectedClipId]?.track : undefined;

    const result = await createShot({ generationIds: selectionShotCreationState.generationIds });
    if (!result?.shotId) {
      return;
    }

    if (trackId) {
      pinGroup(result.shotId, trackId, [...selectedClipIds]);
    }

    const createdShot = result.shot ?? shots?.find((shot) => shot.id === result.shotId) ?? null;
    if (createdShot) {
      setVideoModalShot(createdShot);
    }
  }, [createShot, data?.meta, existingShotsForSelection, pinGroup, selectedClipIds, selectionShotCreationState, shots]);

  const handleNavigateToShot = useCallback((shot: Shot) => {
    navigateToShot(shot, { isNewlyCreated: true });
  }, [navigateToShot]);

  const handleOpenGenerateVideo = useCallback((shot: Shot) => {
    setVideoModalShot(shot);
  }, []);

  const {
    switchToFinalVideo,
    updateToLatestVideo,
    switchToImages,
  } = useSwitchToFinalVideo({
    applyEdit,
    dataRef,
    finalVideoMap,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
  });
  const {
    shotGroupClipIds,
    activeTaskClipIds,
    staleShotGroupIds,
    handleShotGroupNavigate,
    handleShotGroupGenerateVideo,
    handleDeleteShotGroup,
    handleUpdateToLatestVideo,
    handleShotGroupUnpin,
    handleShotGroupSwitchToFinalVideo,
    handleShotGroupSwitchToImages,
  } = useShotGroupHandlers({
    shots,
    shotGroups,
    data,
    resolvedRegistry: resolvedConfig?.registry,
    activeTaskAssetKeys,
    finalVideoMap,
    applyEdit,
    dataRef,
    dismissFinalVideo,
    switchToFinalVideo,
    switchToImages,
    updateToLatestVideo,
    unpinGroup,
    setVideoModalShot,
    setVideoModalShowImages,
  });
  usePinnedGroupSync({
    data,
    dataRef,
    applyEdit,
    shots,
    registerGenerationAsset,
    isInteractionActive,
  });

  const clientXToTime = useCallback((clientX: number): number => {
    const wrapper = timelineWrapperRef.current;
    if (!wrapper) return 0;
    const editArea = wrapper.querySelector<HTMLElement>('.timeline-canvas-edit-area');
    const grid = editArea;
    const rect = (editArea ?? wrapper).getBoundingClientRect();
    const scrollLeft = grid?.scrollLeft ?? 0;
    return Math.max(0, pixelToTime(clientX - rect.left + scrollLeft));
  }, [pixelToTime, timelineWrapperRef]);

  const handleDoubleClickVideoClip = useCallback((clipId: string) => {
    const assetKey = data?.meta[clipId]?.asset;
    const generationId = assetKey ? data?.registry?.assets[assetKey]?.generationId : undefined;
    const fileUrl = assetKey ? data?.registry?.assets[assetKey]?.file : undefined;
    const resolution = resolveVideoClipDoubleClickResolution({
      clipId,
      assetKey,
      generationId,
      fileUrl,
      pinnedShotGroups: dataRef.current?.config.pinnedShotGroups ?? [],
      finalVideoMap,
    });
    log('[video-editor] handleDoubleClickVideoClip:start', {
      clipId,
      assetKey: assetKey ?? null,
      generationId: generationId ?? null,
      fileUrl: fileUrl ?? null,
      resolution,
    });

    if (resolution.type === 'lightbox') {
      log('[video-editor] handleDoubleClickVideoClip:open-lightbox', {
        clipId,
        assetKey: resolution.assetKey,
        generationId: resolution.generationId ?? null,
      });
      onDoubleClickAsset?.(resolution.assetKey, clipId);
      return;
    }

    if (resolution.type === 'video-modal') {
      const shot = shots?.find((s) => s.id === resolution.shotId);
      log('[video-editor] handleDoubleClickVideoClip:open-video-modal', {
        clipId,
        shotId: resolution.shotId,
        reason: resolution.reason,
        foundShot: Boolean(shot),
      });
      if (shot) {
        setVideoModalShot(shot);
      }
      return;
    }

    log('[video-editor] handleDoubleClickVideoClip:no-match', {
      clipId,
      assetKey: assetKey ?? null,
      generationId: generationId ?? null,
      fileUrl: fileUrl ?? null,
    });
  }, [dataRef, shots, data?.meta, data?.registry?.assets, finalVideoMap, onDoubleClickAsset]);

  const handleSplitClipHere = useCallback((clipId: string, clientX: number) => {
    const time = clientXToTime(clientX);
    handleSplitClipAtTime(clipId, time);
  }, [clientXToTime, handleSplitClipAtTime]);

  const handleExpandTinyClip = useCallback((clipId: string) => {
    const current = dataRef.current;
    if (!current) return;
    const row = current.rows.find((r) => r.actions.some((a) => a.id === clipId));
    const action = row?.actions.find((a) => a.id === clipId);
    if (!row || !action) return;
    const duration = action.end - action.start;
    if (duration >= 0.5) return;
    const newEnd = action.start + 0.5;
    const clipMeta = current.meta[clipId];
    const metaUpdates: Record<string, Partial<ClipMeta>> = {};
    if (clipMeta && typeof clipMeta.hold === 'number') {
      metaUpdates[clipId] = { hold: 0.5 };
    }
    applyEdit({
      type: 'rows',
      rows: current.rows.map((r) =>
        r.id !== row.id ? r : {
          ...r,
          actions: r.actions.map((a) =>
            a.id !== clipId ? a : { ...a, end: newEnd },
          ),
        },
      ),
      ...(Object.keys(metaUpdates).length > 0 ? { metaUpdates } : {}),
    });
  }, [applyEdit, dataRef]);

  const handleDuplicateGenerationClip = useCallback(async (clipId: string) => {
    if (!selectedProjectId) {
      toast.error('Select a project before duplicating a generation.');
      return;
    }

    const current = dataRef.current;
    if (!current) {
      return;
    }

    const clipMeta = current.meta[clipId];
    const assetKey = clipMeta?.asset;
    const assetEntry = assetKey ? current.registry.assets[assetKey] : undefined;
    const generationId = assetEntry?.generationId;
    if (!generationId) {
      toast.error('This clip is not linked to a generation.');
      return;
    }

    setDuplicatingClipId(clipId);
    try {
      const duplicatedGeneration = await duplicateGenerationAsset({
        generationId,
        projectId: selectedProjectId,
      });
      const duplicatedAssetKey = registerGenerationAsset({
        generationId: duplicatedGeneration.generationId,
        variantId: duplicatedGeneration.variantId,
        variantType: duplicatedGeneration.variantType,
        imageUrl: duplicatedGeneration.imageUrl,
        thumbUrl: duplicatedGeneration.thumbUrl,
        durationSeconds: typeof assetEntry?.duration === 'number' ? assetEntry.duration : undefined,
        metadata: {
          content_type: assetEntry?.type ?? (
            duplicatedGeneration.variantType === 'video' ? 'video/mp4' : 'image/png'
          ),
        },
      });

      if (!duplicatedAssetKey) {
        throw new Error('Failed to register the duplicated asset.');
      }

      const nextCurrent = dataRef.current;
      if (!nextCurrent) {
        throw new Error('Timeline state was unavailable after registering the duplicated asset.');
      }

      const duplicateEdit = buildDuplicateClipEdit(nextCurrent, clipId, duplicatedAssetKey);
      if (!duplicateEdit) {
        throw new Error('Failed to insert the duplicated clip on the timeline.');
      }

      applyEdit({
        type: 'rows',
        rows: duplicateEdit.rows,
        metaUpdates: duplicateEdit.metaUpdates,
        clipOrderOverride: duplicateEdit.clipOrderOverride,
      }, {
        selectedClipId: duplicateEdit.clipId,
        selectedTrackId: duplicateEdit.trackId,
        semantic: true,
      });
    } catch (error) {
      normalizeAndPresentError(error, {
        context: 'video-editor:duplicate-generation-clip',
        toastTitle: 'Failed to duplicate generation',
      });
    } finally {
      setDuplicatingClipId((currentClipId) => (currentClipId === clipId ? null : currentClipId));
    }
  }, [applyEdit, dataRef, registerGenerationAsset, selectedProjectId]);

  const handleTrimClipToMediaEnd = useCallback((clipId: string) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const clipMeta = current.meta[clipId];
    const assetKey = clipMeta?.asset;
    const assetEntry = assetKey ? current.registry.assets[assetKey] : undefined;
    if (!clipMeta || !assetEntry?.type?.startsWith('video') || typeof assetEntry.duration !== 'number') {
      return;
    }

    const sourceRow = current.rows.find((row) => row.actions.some((action) => action.id === clipId));
    const sourceAction = sourceRow?.actions.find((action) => action.id === clipId);
    if (!sourceRow || !sourceAction) {
      return;
    }

    const clamped = clampClipToMediaDuration({
      action: sourceAction,
      clipMeta,
      sourceDurationSeconds: assetEntry.duration,
    });
    if (!clamped) {
      return;
    }

    applyEdit({
      type: 'rows',
      rows: current.rows.map((row) => {
        if (row.id !== sourceRow.id) {
          return row;
        }

        return {
          ...row,
          actions: row.actions.map((action) => (
            action.id === clipId ? clamped.nextAction : action
          )),
        };
      }),
      metaUpdates: {
        [clipId]: clamped.metaPatch,
      },
    }, {
      selectedClipId: clipId,
      selectedTrackId: clipMeta.track,
      semantic: true,
    });
  }, [applyEdit, dataRef]);

  const handleConvertClipOverhangToHold = useCallback((clipId: string) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const clipMeta = current.meta[clipId];
    const assetKey = clipMeta?.asset;
    const assetEntry = assetKey ? current.registry.assets[assetKey] : undefined;
    if (!clipMeta || !assetEntry?.type?.startsWith('video') || typeof assetEntry.duration !== 'number') {
      return;
    }

    const conversion = convertOverhangToHold({
      current,
      clipId,
      sourceDurationSeconds: assetEntry.duration,
      frameRate: assetEntry.fps,
    });
    if (!conversion) {
      return;
    }

    applyEdit({
      type: 'rows',
      rows: conversion.rows,
      metaUpdates: conversion.metaUpdates,
      clipOrderOverride: conversion.clipOrderOverride,
    }, {
      selectedClipId: conversion.holdClipId,
      selectedTrackId: conversion.trackId,
      semantic: true,
    });
  }, [applyEdit, dataRef]);

  const getActionRender = useCallback((action: TimelineAction, _row: TimelineRow, clipWidth: number) => {
    const clipMeta = data?.meta[action.id];
    if (!clipMeta) {
      return null;
    }

    const resolvedClip = resolvedClipMap.get(action.id);
    const track = resolvedClip ? trackMap.get(resolvedClip.track) : undefined;
    const clipWidthPx = clipWidth;
    const thumbnailSrc = clipWidthPx >= 40 ? thumbnailMap[action.id] : undefined;
    const assetKey = clipMeta.asset;
    const audioSrc = resolveWaveformAudioSrc(resolvedClip, track);
    const isStale = assetKey ? staleAssetKeys.has(assetKey) : false;
    const isDismissed = assetKey ? dismissedAssetKeys.has(assetKey) : false;
    const isGenAsset = assetKey ? generationAssetKeys.has(assetKey) : false;
    const isTaskActive = assetKey && !shotGroupClipIds.has(action.id) ? activeTaskAssetKeys.has(assetKey) : false;
    const assetEntry = assetKey ? data?.registry?.assets[assetKey] : undefined;
    const assetType = assetEntry?.type;
    const isVideoClip = typeof assetType === 'string' && assetType.startsWith('video');
    const clipOverhang = isVideoClip
      ? detectClipOverhang({
          clipMeta,
          timelineDurationSeconds: action.end - action.start,
          sourceDurationSeconds: assetEntry?.duration,
        })
      : null;

    return (
      <ClipAction
        action={action}
        clipMeta={clipMeta}
        isVideoClip={isVideoClip}
        isInPinnedShotGroup={shotGroupClipIds.has(action.id)}
        isSelected={isClipSelected(action.id)}
        isPrimary={primaryClipId === action.id}
        showOverflowMenu={deviceClass !== 'desktop'}
        selectedClipIds={[...selectedClipIds]}
        thumbnailSrc={thumbnailSrc}
        audioSrc={audioSrc}
        clipWidth={clipWidthPx}
        onSelect={handleClipSelect}
        onDoubleClickAsset={onDoubleClickAsset}
        onDoubleClickVideoClip={handleDoubleClickVideoClip}
        onExpandTinyClip={handleExpandTinyClip}
        onSplitHere={handleSplitClipHere}
        onSplitClipsAtPlayhead={handleSplitClipsAtPlayhead}
        onTrimToMediaEnd={clipOverhang ? handleTrimClipToMediaEnd : undefined}
        onConvertOverhangToHold={clipOverhang ? handleConvertClipOverhangToHold : undefined}
        onDeleteClips={handleDeleteClips}
        onDeleteClip={handleDeleteClip}
        onToggleMuteClips={handleToggleMuteClips}
        isTaskActive={isTaskActive}
        isVariantStale={isStale && !isDismissed}
        isGenerationAsset={isGenAsset}
        isDuplicatingGeneration={duplicatingClipId === action.id}
        onDuplicateGeneration={isGenAsset ? handleDuplicateGenerationClip : undefined}
        onUpdateVariant={isGenAsset && assetKey ? () => void updateAssetToCurrentVariant(assetKey) : undefined}
        onDismissStale={isStale && assetKey ? () => dismissAsset(assetKey) : undefined}
        canCreateShotFromSelection={selectionShotCreationState.canCreateShot}
        existingShots={existingShotsForSelection}
        onCreateShotFromSelection={handleCreateShotFromSelection}
        onGenerateVideoFromSelection={handleGenerateVideoFromSelection}
        onNavigateToShot={handleNavigateToShot}
        onOpenGenerateVideo={handleOpenGenerateVideo}
        isCreatingShot={isCreating}
        overhangDurationSeconds={clipOverhang?.overhangTimelineDurationSeconds}
        overhangEndFraction={clipOverhang?.mediaEndFraction}
      />
    );
  }, [
    selectionShotCreationState.canCreateShot,
    existingShotsForSelection,
    activeTaskAssetKeys,
    deviceClass,
    shotGroupClipIds,
    data,
    dismissAsset,
    dismissedAssetKeys,
    duplicatingClipId,
    generationAssetKeys,
    handleDuplicateGenerationClip,
    handleCreateShotFromSelection,
    handleDoubleClickVideoClip,
    handleExpandTinyClip,
    handleClipSelect,
    handleDeleteClip,
    handleDeleteClips,
    handleConvertClipOverhangToHold,
    handleGenerateVideoFromSelection,
    handleNavigateToShot,
    handleOpenGenerateVideo,
    handleSplitClipHere,
    handleSplitClipsAtPlayhead,
    handleTrimClipToMediaEnd,
    handleToggleMuteClips,
    isCreating,
    isClipSelected,
    onDoubleClickAsset,
    primaryClipId,
    resolvedClipMap,
    trackMap,
    selectedClipIds,
    staleAssetKeys,
    thumbnailMap,
    updateAssetToCurrentVariant,
  ]);

  const handleTrackDragEnd = useCallback(({ active, over }: DragEndEvent) => {
    if (!over) {
      return;
    }

    const activeSortableId = String(active.id);
    const overSortableId = String(over.id);
    if (
      activeSortableId === overSortableId ||
      !activeSortableId.startsWith('track-') ||
      !overSortableId.startsWith('track-')
    ) {
      return;
    }

    const activeTrackId = activeSortableId.slice('track-'.length);
    const overTrackId = overSortableId.slice('track-'.length);
    handleMoveTrack(activeTrackId, overTrackId);
  }, [handleMoveTrack]);

  if (!data) {
    return null;
  }

  return (
    <div className="flex h-full overflow-hidden rounded-xl border border-border bg-card/80">
      <div
        ref={timelineWrapperRef as React.RefObject<HTMLDivElement>}
        className="timeline-wrapper relative min-w-0 flex-1 overflow-hidden"
        onDragOver={onTimelineDragOver}
        onDragLeave={onTimelineDragLeave}
        onDrop={onTimelineDrop}
      >
        <TimelineCanvas
          ref={timelineRef as React.RefObject<import('@/tools/video-editor/types/timeline-canvas').TimelineCanvasHandle>}
          rows={data.rows}
          tracks={data.tracks}
          deviceClass={deviceClass}
          inputModality={inputModality}
          interactionMode={interactionMode}
          gestureOwner={gestureOwner}
          scale={scale}
          scaleWidth={scaleWidth}
          scaleSplitCount={5}
          startLeft={TIMELINE_START_LEFT}
          rowHeight={ROW_HEIGHT}
          minScaleCount={scaleCount}
          maxScaleCount={scaleCount}
          selectedTrackId={selectedTrackId}
          getActionRender={getActionRender}
          onSelectTrack={setSelectedTrackId}
          onTrackChange={handleTrackPopoverChange}
          onRemoveTrack={handleRemoveTrack}
          onTrackDragEnd={handleTrackDragEnd}
          trackSensors={trackSensors}
          onCursorDrag={onCursorDrag}
          onClickTimeArea={onClickTimeArea}
          setInputModalityFromPointerType={setInputModalityFromPointerType}
          setGestureOwner={setGestureOwner}
          onActionResizeStart={resizeStartHandler}
          onClipEdgeResizeEnd={clipEdgeResizeEndHandler}
          shotGroups={shotGroups}
          finalVideoMap={finalVideoMap}
          staleShotGroupIds={staleShotGroupIds}
          activeTaskClipIds={activeTaskClipIds}
          onShotGroupNavigate={handleShotGroupNavigate}
          onShotGroupGenerateVideo={handleShotGroupGenerateVideo}
          onShotGroupUnpin={handleShotGroupUnpin}
          onShotGroupDelete={handleDeleteShotGroup}
          onShotGroupSwitchToFinalVideo={handleShotGroupSwitchToFinalVideo}
          onShotGroupSwitchToImages={handleShotGroupSwitchToImages}
          onShotGroupUpdateToLatestVideo={handleUpdateToLatestVideo}
          onSelectClips={selectClips}
          dragSessionRef={dragSessionRef}
          interactionStateRef={interactionStateRef}
          marqueeRect={marqueeRect}
          onEditAreaPointerDown={onMarqueePointerDown}
          onAddTrack={handleAddTrack}
          onAddTextAt={handleAddTextAt}
          unusedTrackCount={unusedTrackCount}
          onClearUnusedTracks={handleClearUnusedTracks}
          newTrackDropLabel={newTrackDropLabel}
        />
        <DropIndicator ref={indicatorRef} editAreaRef={editAreaRef} onNewTrackLabel={setNewTrackDropLabel} />
      </div>

      {videoModalShot && (
        <>
          {/* VideoGenerationModal only uses app-wide providers, so it can open from timeline selection flow. */}
          <VideoGenerationModal
            isOpen={true}
            onClose={() => { setVideoModalShot(null); setVideoModalShowImages(false); }}
            shot={videoModalShot}
            defaultTopOpen={videoModalShowImages}
          />
        </>
      )}
    </div>
  );
}

export const TimelineEditor = memo(TimelineEditorComponent);
