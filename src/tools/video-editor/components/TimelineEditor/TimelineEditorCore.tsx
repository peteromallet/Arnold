import { memo, useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { shallow } from 'zustand/shallow';
import {
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import type { Shot } from '@/domains/generation/types/index.ts';
import { userSelectTimelineClip } from '@/shared/state/selectionStore.ts';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import '@/tools/video-editor/components/TimelineEditor/timeline-overrides.css';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics.ts';
import { ClipAction } from '@/tools/video-editor/components/TimelineEditor/ClipAction.tsx';
import { DropIndicator } from '@/tools/video-editor/components/TimelineEditor/DropIndicator.tsx';
import { TimelineCanvas } from '@/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx';
import { ROW_HEIGHT, TIMELINE_START_LEFT } from '@/tools/video-editor/lib/coordinate-utils.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import {
  useTimelineChromeSelector,
  useTimelineDataSelector,
  useTimelineOpsSelector,
  useTimelinePlaybackSelector,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import { useClipDrag } from '@/tools/video-editor/hooks/useClipDrag.ts';
import { useActiveTaskClips } from '@/tools/video-editor/hooks/useActiveTaskClips.ts';
import { useMarqueeSelect } from '@/tools/video-editor/hooks/useMarqueeSelect.ts';
import type { ShotGroup } from '@/tools/video-editor/hooks/useShotGroups.ts';
import { useStaleVariants } from '@/tools/video-editor/hooks/useStaleVariants.ts';
import { useAddVariantAsGeneration } from '@/tools/video-editor/hooks/useAddVariantAsGeneration.ts';
import { useTimelineScale } from '@/tools/video-editor/hooks/useTimelineScale.ts';
import {
  clampClipToMediaDuration,
  convertOverhangToHold,
  detectClipOverhang,
} from '@/tools/video-editor/lib/overhang.ts';
import { getTimelinePostprocessShader } from '@/tools/video-editor/lib/timeline-domain.ts';
import type { TimelineActionResizeStart, TimelineClipEdgeResizeEnd } from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type { ResolvedTimelineClip, TimelinePostprocessShaderMetadata, TrackDefinition } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';
import type {
  TimelineOverlayContribution,
  TimelineOverlayRenderProps,
} from '@/tools/video-editor/runtime/extensionSurface';

const EMPTY_ASSET_GENERATION_MAP: Record<string, string> = {};
const EMPTY_CLIP_IDS = new Set<string>();
const EMPTY_SHOT_GROUPS: ShotGroup[] = [];
const EMPTY_FINAL_VIDEO_MAP = new Map<string, DoubleClickFinalVideo>();
const EMPTY_SHOTS: Shot[] = [];

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

export interface TimelineEditorCoreProps {
  onOpenSequenceCreator?: () => void;
  finalVideoMap?: Map<string, DoubleClickFinalVideo>;
  shotGroups?: ShotGroup[];
  staleShotGroupIds?: Set<string>;
  activeTaskClipIds?: Set<string>;
  shotGroupClipIds?: Set<string>;
  onShotGroupNavigate?: (shotId: string) => void;
  onShotGroupGenerateVideo?: (shotId: string) => void;
  onShotGroupSwitchToFinalVideo?: (group: { shotId: string; clipIds: string[]; rowId: string }) => void;
  onShotGroupSwitchToImages?: (group: { shotId: string; rowId: string }) => void;
  onShotGroupUpdateToLatestVideo?: (group: { shotId: string; rowId: string }) => void;
  onShotGroupUnpin?: (group: { shotId: string; trackId: string }) => void;
  onShotGroupDelete?: (group: { shotId: string; trackId: string; clipIds: string[] }) => void;
  canCreateShotFromSelection?: boolean;
  existingShots?: Shot[];
  onCreateShotFromSelection?: () => Promise<Shot | null>;
  onGenerateVideoFromSelection?: () => void | Promise<void>;
  onNavigateToShot?: (shot: Shot) => void;
  onOpenGenerateVideo?: (shot: Shot) => void;
  isCreatingShot?: boolean;
  duplicatingClipId?: string | null;
  onDuplicateGenerationClip?: (clipId: string) => void | Promise<void>;
  onOpenShotVideoModal?: (shotId: string, reason: 'pinned-group' | 'final-video-file') => void;
}

function TimelineEditorCoreComponent({
  onOpenSequenceCreator,
  finalVideoMap = EMPTY_FINAL_VIDEO_MAP,
  shotGroups = EMPTY_SHOT_GROUPS,
  staleShotGroupIds,
  activeTaskClipIds,
  shotGroupClipIds = EMPTY_CLIP_IDS,
  onShotGroupNavigate,
  onShotGroupGenerateVideo,
  onShotGroupSwitchToFinalVideo,
  onShotGroupSwitchToImages,
  onShotGroupUpdateToLatestVideo,
  onShotGroupUnpin,
  onShotGroupDelete,
  canCreateShotFromSelection = false,
  existingShots = EMPTY_SHOTS,
  onCreateShotFromSelection,
  onGenerateVideoFromSelection,
  onNavigateToShot,
  onOpenGenerateVideo,
  isCreatingShot = false,
  duplicatingClipId = null,
  onDuplicateGenerationClip,
  onOpenShotVideoModal,
}: TimelineEditorCoreProps) {
  useRenderDiagnostic('TimelineEditorCore');
  const [newTrackDropLabel, setNewTrackDropLabel] = useState<string | null>(null);
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
    setContextTarget,
    setInspectorTarget,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onTimelineDragOver,
    onTimelineDragLeave,
    onTimelineDrop,
    onDoubleClickAsset,
    patchRegistry,
    registerAsset,
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
    setContextTarget: ops.setContextTarget,
    setInspectorTarget: ops.setInspectorTarget,
    onActionResizeStart: ops.onActionResizeStart,
    onClipEdgeResizeEnd: ops.onClipEdgeResizeEnd,
    onTimelineDragOver: ops.onTimelineDragOver,
    onTimelineDragLeave: ops.onTimelineDragLeave,
    onTimelineDrop: ops.onTimelineDrop,
    onDoubleClickAsset: ops.onDoubleClickAsset,
    patchRegistry: ops.patchRegistry,
    registerAsset: ops.registerAsset,
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

  const { staleAssetKeys, dismissedAssetKeys, generationAssetKeys, dismissAsset, updateAssetToCurrentVariant, applyVariantToAsset } = useStaleVariants({
    registry: resolvedConfig?.registry,
    patchRegistry,
    registerAsset,
  });
  const { addVariantAsGenerationAfterClip, isPending: isAddingVariantAsGenerationPending } = useAddVariantAsGeneration();
  const { activeTaskAssetKeys } = useActiveTaskClips({ registry: resolvedConfig?.registry });

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
    userSelectTimelineClip(clipId, { additive: false });
    setSelectedTrackId(trackId);
  }, [setSelectedTrackId]);
  const postprocessShader = resolvedConfig
    ? getTimelinePostprocessShader(resolvedConfig)
    : undefined;
  const handlePostprocessShaderSelect = useCallback((shader: TimelinePostprocessShaderMetadata) => {
    clearSelection();
    setSelectedTrackId(null);
    const target = {
      kind: 'shader' as const,
      shaderScope: 'postprocess' as const,
      shaderId: shader.shaderId,
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
    };
    setContextTarget(target);
    setInspectorTarget(target);
  }, [clearSelection, setContextTarget, setInspectorTarget, setSelectedTrackId]);

  const { pixelToTime, pixelsPerSecond } = useTimelineScale({
    scale,
    scaleWidth,
    startLeft: TIMELINE_START_LEFT,
  });

  // ---- Timeline overlay host state -------------------------------------------
  const [overlayScrollLeft, setOverlayScrollLeft] = useState(0);
  const [overlayScrollTop, setOverlayScrollTop] = useState(0);
  const [claimedOverlayId, setClaimedOverlayId] = useState<string | null>(null);
  const overlayViewportRef = useRef<{ width: number; height: number }>({ width: 0, height: 0 });
  const currentTime = useTimelinePlaybackSelector((pb) => pb.currentTime);
  const selectedClipIdsSet = useMemo(
    () => new Set(selectedClipIds),
    [selectedClipIds],
  );

  const handleOverlayScroll = useCallback(
    (metrics: { scrollLeft: number; scrollTop: number }) => {
      setOverlayScrollLeft(metrics.scrollLeft);
      setOverlayScrollTop(metrics.scrollTop);
    },
    [],
  );

  const handleClaimPointer = useCallback((overlayId: string) => {
    setClaimedOverlayId(overlayId);
  }, []);

  const handleReleasePointer = useCallback((overlayId: string) => {
    setClaimedOverlayId((current) => (current === overlayId ? null : current));
  }, []);

  // Resolve overlay viewport dimensions from the timeline wrapper
  useLayoutEffect(() => {
    const wrapper = timelineWrapperRef.current;
    if (!wrapper) return;
    const editArea = wrapper.querySelector<HTMLElement>('.timeline-canvas-edit-area');
    if (editArea) {
      overlayViewportRef.current = {
        width: editArea.clientWidth,
        height: editArea.clientHeight,
      };
    }
  });

  // Compute overlay render props (memoised to keep contributions stable)
  const overlayRenderProps = useMemo<Omit<TimelineOverlayRenderProps, 'pointerClaimed' | 'claimPointer' | 'releasePointer'>>(() => {
    // Compute total dimensions
    let maxEnd = 0;
    if (data) {
      for (const row of data.rows) {
        for (const action of row.actions) {
          maxEnd = Math.max(maxEnd, action.end);
        }
      }
    }
    const totalWidth = TIMELINE_START_LEFT + (Math.ceil((maxEnd + 20) / scale) + 1) * scaleWidth;
    const totalHeight = ((data?.rows.length ?? 0) + 1) * ROW_HEIGHT;

    return {
      scrollLeft: overlayScrollLeft,
      scrollTop: overlayScrollTop,
      viewportWidth: overlayViewportRef.current.width,
      viewportHeight: overlayViewportRef.current.height,
      totalWidth,
      totalHeight,
      pixelsPerSecond,
      startLeft: TIMELINE_START_LEFT,
      playheadTime: currentTime,
      isPlaying: false,
      selectedClipIds: selectedClipIdsSet,
      selectedTrackId,
      gestureOwner,
      setGestureOwner,
    };
  }, [
    overlayScrollLeft,
    overlayScrollTop,
    currentTime,
    selectedClipIdsSet,
    selectedTrackId,
    gestureOwner,
    setGestureOwner,
    data,
    scale,
    scaleWidth,
    pixelsPerSecond,
  ]);

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

    if (resolution.type === 'lightbox') {
      onDoubleClickAsset?.(resolution.assetKey, clipId);
      return;
    }

    if (resolution.type === 'video-modal') {
      onOpenShotVideoModal?.(resolution.shotId, resolution.reason);
    }
  }, [data?.meta, data?.registry?.assets, dataRef, finalVideoMap, onDoubleClickAsset, onOpenShotVideoModal]);

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
        onOpenSequenceCreator={onOpenSequenceCreator}
        isTaskActive={isTaskActive}
        isVariantStale={isStale && !isDismissed}
        isGenerationAsset={isGenAsset}
        isDuplicatingGeneration={duplicatingClipId === action.id}
        onDuplicateGeneration={isGenAsset ? onDuplicateGenerationClip : undefined}
        onUpdateVariant={isGenAsset && assetKey ? () => void updateAssetToCurrentVariant(assetKey) : undefined}
        onDismissStale={isStale && assetKey ? () => dismissAsset(assetKey) : undefined}
        variantPickerGenerationId={assetEntry?.generationId}
        variantPickerCurrentVariantId={assetEntry?.variantId ?? null}
        onApplyVariant={isGenAsset && assetKey ? (variant) => applyVariantToAsset(assetKey, variant) : undefined}
        onAddVariantAsGeneration={isGenAsset ? (variant) => addVariantAsGenerationAfterClip(action.id, variant) : undefined}
        isAddingVariantAsGeneration={(variantId) => isAddingVariantAsGenerationPending(action.id, variantId)}
        canCreateShotFromSelection={canCreateShotFromSelection}
        existingShots={existingShots}
        onCreateShotFromSelection={onCreateShotFromSelection}
        onGenerateVideoFromSelection={onGenerateVideoFromSelection}
        onNavigateToShot={onNavigateToShot}
        onOpenGenerateVideo={onOpenGenerateVideo}
        isCreatingShot={isCreatingShot}
        overhangDurationSeconds={clipOverhang?.overhangTimelineDurationSeconds}
        overhangEndFraction={clipOverhang?.mediaEndFraction}
      />
    );
  }, [
    activeTaskAssetKeys,
    addVariantAsGenerationAfterClip,
    applyVariantToAsset,
    canCreateShotFromSelection,
    data,
    deviceClass,
    dismissAsset,
    dismissedAssetKeys,
    duplicatingClipId,
    existingShots,
    generationAssetKeys,
    handleClipSelect,
    handleConvertClipOverhangToHold,
    handleDeleteClip,
    handleDeleteClips,
    handleDoubleClickVideoClip,
    handleExpandTinyClip,
    handleSplitClipHere,
    handleSplitClipsAtPlayhead,
    handleToggleMuteClips,
    handleTrimClipToMediaEnd,
    isAddingVariantAsGenerationPending,
    isClipSelected,
    isCreatingShot,
    onCreateShotFromSelection,
    onDoubleClickAsset,
    onDuplicateGenerationClip,
    onGenerateVideoFromSelection,
    onNavigateToShot,
    onOpenGenerateVideo,
    onOpenSequenceCreator,
    primaryClipId,
    resolvedClipMap,
    selectedClipIds,
    shotGroupClipIds,
    staleAssetKeys,
    thumbnailMap,
    trackMap,
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
          onShotGroupNavigate={onShotGroupNavigate}
          onShotGroupGenerateVideo={onShotGroupGenerateVideo}
          onShotGroupUnpin={onShotGroupUnpin}
          onShotGroupDelete={onShotGroupDelete}
          onShotGroupSwitchToFinalVideo={onShotGroupSwitchToFinalVideo}
          onShotGroupSwitchToImages={onShotGroupSwitchToImages}
          onShotGroupUpdateToLatestVideo={onShotGroupUpdateToLatestVideo}
          onSelectClips={selectClips}
          dragSessionRef={dragSessionRef}
          interactionStateRef={interactionStateRef}
          marqueeRect={marqueeRect}
          onEditAreaPointerDown={onMarqueePointerDown}
          onAddTrack={handleAddTrack}
          onAddTextAt={handleAddTextAt}
          onOpenSequenceCreator={onOpenSequenceCreator}
          unusedTrackCount={unusedTrackCount}
          onClearUnusedTracks={handleClearUnusedTracks}
          newTrackDropLabel={newTrackDropLabel}
          onScroll={handleOverlayScroll}
          postprocessShader={postprocessShader}
          onSelectPostprocessShader={handlePostprocessShaderSelect}
        />
        {/* Timeline overlay host — renders extension overlays above the edit area.
            Defaults to pointer-events-none so overlays don't steal gestures unless
            they explicitly claim pointer via claimPointer(). */}
        <div
          className="pointer-events-none absolute inset-0 z-20"
          style={{ pointerEvents: claimedOverlayId ? 'auto' : 'none' }}
          data-testid="timeline-overlay-host"
        >
          {claimedOverlayId && (
            <div
              data-testid="timeline-overlay-claimed-indicator"
              data-claimed-overlay-id={claimedOverlayId}
              className="sr-only"
              role="status"
              aria-live="polite"
            >
              Overlay {claimedOverlayId} has claimed pointer
            </div>
          )}
        </div>
        <DropIndicator ref={indicatorRef} editAreaRef={editAreaRef} onNewTrackLabel={setNewTrackDropLabel} />
      </div>
    </div>
  );
}

export const TimelineEditorCore = memo(TimelineEditorCoreComponent);
