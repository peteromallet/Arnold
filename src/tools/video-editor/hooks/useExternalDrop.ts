import { useCallback, useEffect, useRef } from 'react';
import {
  getGenerationDropData,
  getMultiGenerationDropData,
  getShotDropData,
  getDragType,
} from '@/shared/lib/dnd/dragDrop';
import { useShots } from '@/shared/contexts/ShotsContext';
import { getMediaUrl, getThumbnailUrl } from '@/shared/lib/media/mediaTypeHelpers';
import { inferDragKind } from '@/tools/video-editor/lib/drop-position';
import { resolveFinalVideoDurationSeconds } from '@/tools/video-editor/lib/finalVideoAssets';
import type { DragCoordinator } from '@/tools/video-editor/hooks/useDragCoordinator';
import {
  buildAssetDropEdit,
  resolveAssetDropTarget,
  type UseAssetManagementResult,
} from '@/tools/video-editor/hooks/useAssetManagement';
import type {
  TimelineApplyEdit,
  TimelineInvalidateAssetRegistry,
  TimelinePatchRegistry,
  TimelineRegisterAsset,
  TimelineUploadAsset,
} from '@/tools/video-editor/hooks/timeline-state-types';
import { type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import {
  finalizeExternalDrop,
  handleAssetDrop,
  handleEffectLayerDrop,
  handleFileDrop,
  handleMultiGenerationDrop,
  handleSingleGenerationDrop,
  handleTextToolDrop,
  isGenerationDragType,
  type TimelineDropPosition,
} from '@/tools/video-editor/lib/external-drop-utils';
import { RafLoopDetector } from '@/tools/video-editor/lib/perf-diagnostics';
import { buildPinnedShotGroupsOverride } from '@/tools/video-editor/lib/shot-group-commands';
import type { TrackKind } from '@/tools/video-editor/types';
import { createAutoScroller } from '@/tools/video-editor/lib/auto-scroll';
import type { Shot } from '@/domains/generation/types';
import { useFinalVideoAvailable } from '@/tools/video-editor/hooks/useFinalVideoAvailable';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';

async function resolveFinalVideoDurationSecondsWithRetry(
  finalVideo: Parameters<typeof resolveFinalVideoDurationSeconds>[0],
  assets?: TimelineData['registry']['assets'],
): Promise<number | null> {
  const firstAttempt = await resolveFinalVideoDurationSeconds(finalVideo, assets);
  if (typeof firstAttempt === 'number') {
    return firstAttempt;
  }

  return resolveFinalVideoDurationSeconds(finalVideo, assets);
}

async function dispatchTimelineDrop({
  event,
  dataRef,
  pendingOpsRef,
  dropPosition,
  selectedTrackId,
  applyEdit,
  patchRegistry,
  uploadAsset,
  invalidateAssetRegistry,
  resolveAssetUrl,
  registerGenerationAsset,
  uploadImageGeneration,
  uploadVideoGeneration,
  dropAsset,
  handleAddTextAt,
  shots,
  finalVideoMap,
}: {
  event: React.DragEvent<HTMLDivElement>;
  dataRef: React.MutableRefObject<TimelineData | null>;
  pendingOpsRef: React.MutableRefObject<number>;
  dropPosition: TimelineDropPosition;
  selectedTrackId: string | null;
  applyEdit: TimelineApplyEdit;
  patchRegistry: TimelinePatchRegistry;
  uploadAsset: TimelineUploadAsset;
  invalidateAssetRegistry: TimelineInvalidateAssetRegistry;
  resolveAssetUrl: (file: string) => Promise<string>;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  uploadImageGeneration: UseAssetManagementResult['uploadImageGeneration'];
  uploadVideoGeneration: UseAssetManagementResult['uploadVideoGeneration'];
  dropAsset: UseAssetManagementResult['handleAssetDrop'];
  handleAddTextAt?: (trackId: string, time: number) => void;
  shots: Shot[] | undefined;
  finalVideoMap: Map<string, { id: string; location: string; thumbnailUrl: string | null; durationSeconds?: number | null }>;
}) {
  const insertAtTop = Boolean(dropPosition.isNewTrackTop);

  if (event.dataTransfer.types.includes('text-tool')) {
    handleTextToolDrop({ dataRef, dropPosition, insertAtTop, handleAddTextAt });
    return;
  }

  if (event.dataTransfer.types.includes('effect-layer')) {
    handleEffectLayerDrop({ dataRef, dropPosition, insertAtTop, selectedTrackId, applyEdit });
    return;
  }

  if (await handleFileDrop({
    files: Array.from(event.dataTransfer.files),
    dataRef,
    pendingOpsRef,
    dropPosition,
    insertAtTop,
    selectedTrackId,
    applyEdit,
    patchRegistry,
    uploadAsset,
    invalidateAssetRegistry,
    resolveAssetUrl,
    registerGenerationAsset,
    uploadImageGeneration,
    uploadVideoGeneration,
    dropAsset,
  })) {
    return;
  }

  const shotData = getShotDropData(event);
  if (shotData) {
    const finalVideo = finalVideoMap.get(shotData.shotId);
    if (finalVideo) {
      const durationSeconds = await resolveFinalVideoDurationSecondsWithRetry(finalVideo, dataRef.current?.registry.assets);
      const resolvedTarget = resolveAssetDropTarget({
        dataRef,
        assetKind: 'visual',
        trackId: dropPosition.isNewTrack ? undefined : dropPosition.trackId,
        selectedTrackId,
        forceNewTrack: dropPosition.isNewTrack,
        insertAtTop,
        time: dropPosition.time,
        duration: durationSeconds ?? 5,
      });
      if (!resolvedTarget) {
        return;
      }

      const assetKey = registerGenerationAsset({
        generationId: finalVideo.id,
        variantType: 'video',
        imageUrl: finalVideo.location,
        thumbUrl: finalVideo.thumbnailUrl ?? finalVideo.location,
        ...(typeof durationSeconds === 'number' ? { durationSeconds } : {}),
        metadata: {
          content_type: 'video/mp4',
        },
      });
      if (!assetKey) {
        return;
      }

      const nextEdit = buildAssetDropEdit({
        current: resolvedTarget.current,
        assetKey,
        trackId: resolvedTarget.trackId,
        time: resolvedTarget.snappedTime ?? dropPosition.time,
      });
      if (!nextEdit) {
        return;
      }

      const nextData: TimelineData = {
        ...resolvedTarget.current,
        rows: nextEdit.rows,
        meta: {
          ...resolvedTarget.current.meta,
          ...nextEdit.metaUpdates,
        },
        clipOrder: nextEdit.clipOrderOverride,
      };

      applyEdit({
        type: 'rows',
        rows: nextEdit.rows,
        metaUpdates: nextEdit.metaUpdates,
        clipOrderOverride: nextEdit.clipOrderOverride,
        pinnedShotGroupsOverride: buildPinnedShotGroupsOverride(nextData, {
          shotId: shotData.shotId,
          trackId: resolvedTarget.trackId,
          clipIds: [nextEdit.clipId],
          mode: 'video',
          videoAssetKey: assetKey,
        }),
      }, {
        selectedClipId: nextEdit.clipId,
        selectedTrackId: resolvedTarget.trackId,
      });
      return;
    }

    const shot = shots?.find((candidate) => candidate.id === shotData.shotId);
    const shotImages = shotData.imageGenerationIds
      .map((generationId) => shot?.images?.find((image) => image.generation_id === generationId))
      .filter((image): image is NonNullable<NonNullable<typeof shot>['images']>[number] => {
        return Boolean(image?.generation_id && getMediaUrl(image));
      });
    const shotGroupDuration = shotImages.length * 5;
    const resolvedTarget = resolveAssetDropTarget({
      dataRef,
      assetKind: 'visual',
      trackId: dropPosition.isNewTrack ? undefined : dropPosition.trackId,
      selectedTrackId,
      forceNewTrack: dropPosition.isNewTrack,
      insertAtTop,
      time: dropPosition.time,
      duration: shotGroupDuration,
    });

    if (!shot || !resolvedTarget || shotImages.length === 0) {
      return;
    }

    let workingData = resolvedTarget.current;
    const metaUpdates: Record<string, TimelineData['meta'][string]> = {};
    const createdClipIds: string[] = [];
    const baseTime = resolvedTarget.snappedTime ?? dropPosition.time;
    let timeOffset = 0;

    for (const shotImage of shotImages) {
      const imageUrl = getMediaUrl(shotImage);
      if (!shotImage.generation_id) continue;
      if (!imageUrl) continue;
      const assetKey = registerGenerationAsset({
        generationId: shotImage.generation_id,
        variantType: 'image',
        imageUrl,
        thumbUrl: getThumbnailUrl(shotImage) ?? imageUrl,
        metadata: {
          content_type: shotImage.contentType ?? shotImage.type ?? 'image/png',
        },
      });
      if (!assetKey) {
        continue;
      }

      const nextEdit = buildAssetDropEdit({
        current: workingData,
        assetKey,
        trackId: resolvedTarget.trackId,
        time: baseTime + timeOffset,
      });
      if (!nextEdit) {
        continue;
      }

      Object.assign(metaUpdates, nextEdit.metaUpdates);
      createdClipIds.push(nextEdit.clipId);
      timeOffset += nextEdit.duration;
      workingData = {
        ...workingData,
        rows: nextEdit.rows,
        meta: {
          ...workingData.meta,
          ...nextEdit.metaUpdates,
        },
        clipOrder: nextEdit.clipOrderOverride,
      };
    }

    if (createdClipIds.length === 0) {
      return;
    }

    const nextPinnedShotGroups = buildPinnedShotGroupsOverride(workingData, {
      shotId: shot.id,
      trackId: resolvedTarget.trackId,
      clipIds: createdClipIds,
      mode: 'images',
    });

    applyEdit({
      type: 'rows',
      rows: workingData.rows,
      metaUpdates,
      clipOrderOverride: workingData.clipOrder,
      pinnedShotGroupsOverride: nextPinnedShotGroups,
    }, {
      selectedClipId: createdClipIds[0] ?? null,
      selectedTrackId: resolvedTarget.trackId,
    });
    return;
  }

  const multiGenerationData = getMultiGenerationDropData(event);
  if (multiGenerationData?.length) {
    handleMultiGenerationDrop({
      generationItems: multiGenerationData,
      dataRef,
      dropPosition,
      insertAtTop,
      registerGenerationAsset,
      patchRegistry,
      dropAsset,
    });
    return;
  }

  const generationData = getGenerationDropData(event);
  if (generationData) {
    handleSingleGenerationDrop({
      generationData,
      dataRef,
      dropPosition,
      insertAtTop,
      registerGenerationAsset,
      dropAsset,
    });
    return;
  }

  handleAssetDrop({
    assetKey: event.dataTransfer.getData('asset-key'),
    assetKind: event.dataTransfer.getData('asset-kind') as TrackKind,
    dataRef,
    dropPosition,
    insertAtTop,
    selectedTrackId,
    dropAsset,
  });
}

export interface UseExternalDropArgs {
  store?: TimelineStoreApi;
  dataRef: React.MutableRefObject<TimelineData | null>;
  pendingOpsRef: React.MutableRefObject<number>;
  scale: number;
  scaleWidth: number;
  selectedTrackId: string | null;
  applyEdit: TimelineApplyEdit;
  patchRegistry: TimelinePatchRegistry;
  registerAsset: TimelineRegisterAsset;
  uploadAsset: TimelineUploadAsset;
  invalidateAssetRegistry: TimelineInvalidateAssetRegistry;
  resolveAssetUrl: (file: string) => Promise<string>;
  coordinator: DragCoordinator;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  uploadImageGeneration: UseAssetManagementResult['uploadImageGeneration'];
  uploadVideoGeneration: UseAssetManagementResult['uploadVideoGeneration'];
  handleAssetDrop: UseAssetManagementResult['handleAssetDrop'];
  handleAddTextAt?: (trackId: string, time: number) => void;
  onSeekToTime?: (time: number) => void;
}

export interface UseExternalDropResult {
  onTimelineDragOver: (event: React.DragEvent<HTMLDivElement>) => void;
  onTimelineDragLeave: (event: React.DragEvent<HTMLDivElement>) => void;
  onTimelineDrop: (event: React.DragEvent<HTMLDivElement>) => void;
}

export function useExternalDrop({
  store,
  dataRef,
  pendingOpsRef,
  selectedTrackId,
  applyEdit,
  patchRegistry,
  uploadAsset,
  invalidateAssetRegistry,
  resolveAssetUrl,
  coordinator,
  registerGenerationAsset,
  uploadImageGeneration,
  uploadVideoGeneration,
  handleAssetDrop: dropAsset,
  handleAddTextAt,
  onSeekToTime,
}: UseExternalDropArgs): UseExternalDropResult {
  const { shots } = useShots();
  const { finalVideoMap } = useFinalVideoAvailable();
  const externalDragFrameRef = useRef<number | null>(null);
  const autoScrollerRef = useRef<ReturnType<typeof createAutoScroller> | null>(null);
  const latestExternalDragRef = useRef<{
    clientX: number;
    clientY: number;
    sourceKind: TrackKind | null;
  } | null>(null);
  const latestExternalPositionRef = useRef<ReturnType<DragCoordinator['update']> | null>(null);
  const getDataRef = useCallback(() => {
    const storeDataRef = store?.getState().data.dataRef;
    return storeDataRef && storeDataRef.current !== null ? storeDataRef : dataRef;
  }, [dataRef, store]);
  const getPendingOpsRef = useCallback(() => {
    return store?.getState().data.pendingOpsRef ?? pendingOpsRef;
  }, [pendingOpsRef, store]);
  const getSelectedTrackId = useCallback(() => {
    return store?.getState().data.selectedTrackId ?? selectedTrackId;
  }, [selectedTrackId, store]);
  const getApplyEdit = useCallback(() => {
    return store?.getState().ops.applyEdit ?? applyEdit;
  }, [applyEdit, store]);
  const getPatchRegistry = useCallback(() => {
    return store?.getState().ops.patchRegistry ?? patchRegistry;
  }, [patchRegistry, store]);

  const clearExternalDragState = useCallback(() => {
    if (externalDragFrameRef.current !== null) {
      window.cancelAnimationFrame(externalDragFrameRef.current);
      externalDragFrameRef.current = null;
    }
    autoScrollerRef.current?.stop();
    autoScrollerRef.current = null;
    latestExternalDragRef.current = null;
    latestExternalPositionRef.current = null;
    coordinator.end();
  }, [coordinator]);

  useEffect(() => {
    return () => {
      clearExternalDragState();
    };
  }, [clearExternalDragState]);

  const onTimelineDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    const dragType = getDragType(event);
    const types = Array.from(event.dataTransfer.types);
    if (!types.includes('asset-key')
      && !types.includes('text-tool')
      && !types.includes('effect-layer')
      && dragType !== 'file'
      && dragType !== 'shot'
      && !isGenerationDragType(dragType)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.dataset.dragOver = 'true';
    latestExternalDragRef.current = {
      clientX: event.clientX,
      clientY: event.clientY,
      sourceKind: inferDragKind(event),
    };
    if (!autoScrollerRef.current && coordinator.editAreaRef.current) {
      autoScrollerRef.current = createAutoScroller(coordinator.editAreaRef.current, (clientX, clientY) => {
        const currentDrag = latestExternalDragRef.current;
        if (!currentDrag) {
          return;
        }

        latestExternalPositionRef.current = coordinator.update({
          clientX,
          clientY,
          sourceKind: currentDrag.sourceKind,
        });
      });
    }
    autoScrollerRef.current?.update(event.clientX, event.clientY);

    if (externalDragFrameRef.current !== null) {
      return;
    }

    externalDragFrameRef.current = window.requestAnimationFrame(() => {
      RafLoopDetector.track('externalDrop');
      externalDragFrameRef.current = null;
      const currentDrag = latestExternalDragRef.current;
      if (!currentDrag) {
        return;
      }

      latestExternalPositionRef.current = coordinator.update({
        clientX: currentDrag.clientX,
        clientY: currentDrag.clientY,
        sourceKind: currentDrag.sourceKind,
      });
    });
  }, [coordinator]);

  const onTimelineDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    delete event.currentTarget.dataset.dragOver;
    clearExternalDragState();
  }, [clearExternalDragState]);

  const onTimelineDrop = useCallback(async (event: React.DragEvent<HTMLDivElement>) => {
    const dropPosition = finalizeExternalDrop({
      event,
      coordinator,
      autoScrollerRef,
      externalDragFrameRef,
      latestExternalDragRef,
      latestExternalPositionRef,
    });
    await dispatchTimelineDrop({
      event,
      dataRef: getDataRef(),
      pendingOpsRef: getPendingOpsRef(),
      dropPosition,
      selectedTrackId: getSelectedTrackId(),
      applyEdit: getApplyEdit(),
      patchRegistry: getPatchRegistry(),
      uploadAsset,
      invalidateAssetRegistry,
      resolveAssetUrl,
      registerGenerationAsset,
      uploadImageGeneration,
      uploadVideoGeneration,
      dropAsset,
      handleAddTextAt,
      shots,
      finalVideoMap,
    });
    onSeekToTime?.(dropPosition.time);
  }, [
    coordinator,
    dropAsset,
    getApplyEdit,
    getDataRef,
    getPatchRegistry,
    getPendingOpsRef,
    getSelectedTrackId,
    invalidateAssetRegistry,
    registerGenerationAsset,
    resolveAssetUrl,
    shots,
    finalVideoMap,
    handleAddTextAt,
    onSeekToTime,
    uploadAsset,
    uploadImageGeneration,
    uploadVideoGeneration,
  ]);

  return {
    onTimelineDragOver,
    onTimelineDragLeave,
    onTimelineDrop,
  };
}
