import type { DragEvent, MutableRefObject } from 'react';
import type { GenerationDropData } from '@/shared/lib/dnd/dragDrop.ts';
import { getDragType } from '@/shared/lib/dnd/dragDrop.ts';
import {
  resolveAssetUrlWithResolver,
  type AssetResolver,
} from '@/tools/video-editor/data/AssetResolver.ts';
import { createAutoScroller } from '@/tools/video-editor/lib/auto-scroll.ts';
import { getCompatibleTrackId, updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils.ts';
import { getTrackIndex } from '@/tools/video-editor/lib/editor-utils.ts';
import { inferDragKind } from '@/tools/video-editor/lib/drop-position.ts';
import { resolveOverlaps } from '@/tools/video-editor/lib/resolve-overlaps.ts';
import {
  getDroppedGenerationDurationContract,
} from '@/tools/video-editor/lib/timeline-asset-durations.ts';
import {
  buildAssetDropEdit,
  getPlayableAssetKind,
  planAssetDropTarget,
  planGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans.ts';
import {
  createEffectLayerClipMeta,
  getNextClipId,
  type ClipMeta,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data.ts';
import type { UseAssetManagementResult } from '@/tools/video-editor/hooks/useAssetManagement.ts';
import type { DragCoordinator } from '@/tools/video-editor/hooks/useDragCoordinator.ts';
import type {
  TimelineApplyEdit,
  TimelineInvalidateAssetRegistry,
  TimelinePatchRegistry,
  TimelineUploadAsset,
} from '@/tools/video-editor/hooks/timeline-state-types.ts';
import type { TrackKind } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

export type TimelineDropPosition = NonNullable<ReturnType<DragCoordinator['update']>>;

export function isGenerationDragType(dragType: ReturnType<typeof getDragType>) {
  return dragType === 'generation' || dragType === 'generation-multi';
}

export function createTrack(
  dataRef: MutableRefObject<TimelineData | null>,
  kind: 'audio' | 'visual',
  insertAtTop: boolean,
  label?: string,
): { trackId: string; insertAtTop: boolean } | null {
  const current = dataRef.current;
  if (!current) {
    return null;
  }

  const prefix = kind === 'audio' ? 'A' : 'V';
  const nextNumber = getTrackIndex(current.tracks, prefix) + 1;
  const trackId = `${prefix}${nextNumber}`;
  const nextTrack = { id: trackId, kind, label: label ?? trackId };
  const nextRow = { id: trackId, actions: [] };

  dataRef.current = {
    ...current,
    tracks: insertAtTop ? [nextTrack, ...current.tracks] : [...current.tracks, nextTrack],
    rows: insertAtTop ? [nextRow, ...current.rows] : [...current.rows, nextRow],
  };

  return { trackId, insertAtTop };
}

export function createTrackAtTop(
  dataRef: MutableRefObject<TimelineData | null>,
  kind: 'audio' | 'visual',
  label?: string,
): { trackId: string; insertAtTop: true } | null {
  const createdTrack = createTrack(dataRef, kind, true, label);
  return createdTrack ? { ...createdTrack, insertAtTop: true } : null;
}

export function createTrackForDrop(
  dataRef: MutableRefObject<TimelineData | null>,
  kind: 'audio' | 'visual',
  insertAtTop: boolean,
  label?: string,
): { trackId: string; insertAtTop: boolean } | null {
  return insertAtTop
    ? createTrackAtTop(dataRef, kind, label)
    : createTrack(dataRef, kind, false, label);
}

export function removeAction(rows: TimelineData['rows'], actionId: string) {
  return rows.map((row) => ({
    ...row,
    actions: row.actions.filter((action) => action.id !== actionId),
  }));
}

export function inferFileDropKind(file: File): TrackKind {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return ['.mp3', '.wav', '.aac', '.m4a'].includes(extension) ? 'audio' : 'visual';
}

export function isImageFile(file: File): boolean {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return file.type.startsWith('image/')
    || ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.avif'].includes(extension);
}

export function isVideoFile(file: File): boolean {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return file.type.startsWith('video/')
    || ['.mp4', '.mov', '.webm', '.m4v', '.avi'].includes(extension);
}

export function handleTextToolDrop({
  dataRef,
  dropPosition,
  insertAtTop,
  handleAddTextAt,
}: {
  dataRef: MutableRefObject<TimelineData | null>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  handleAddTextAt?: (trackId: string, time: number) => void;
}): boolean {
  if (!handleAddTextAt || !dataRef.current) {
    return false;
  }

  let targetTrackId = dropPosition.isNewTrack ? undefined : dropPosition.trackId;
  if (!targetTrackId) {
    targetTrackId = createTrackForDrop(dataRef, 'visual', insertAtTop)?.trackId;
  }

  if (!targetTrackId) {
    return true;
  }

  handleAddTextAt(targetTrackId, dropPosition.time);
  return true;
}

export function handleEffectLayerDrop({
  dataRef,
  dropPosition,
  insertAtTop,
  selectedTrackId,
  applyEdit,
}: {
  dataRef: MutableRefObject<TimelineData | null>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  selectedTrackId: string | null;
  applyEdit: TimelineApplyEdit;
}): boolean {
  let current = dataRef.current;
  if (!current) {
    return false;
  }

  let targetTrackId = dropPosition.isNewTrack
    ? null
    : getCompatibleTrackId(current.tracks, dropPosition.trackId, 'visual', selectedTrackId);

  if (!targetTrackId) {
    targetTrackId = createTrackForDrop(dataRef, 'visual', insertAtTop)?.trackId ?? null;
    current = dataRef.current;
  }

  if (!targetTrackId || !current) {
    return true;
  }

  const clipId = getNextClipId(current.meta);
  const clipMeta = createEffectLayerClipMeta(targetTrackId);
  const duration = clipMeta.hold ?? 5;
  const action: TimelineAction = {
    id: clipId,
    start: Math.max(0, dropPosition.time),
    end: Math.max(0, dropPosition.time) + duration,
    effectId: `effect-${clipId}`,
  };
  const rowsWithClip = current.rows.map((row) => (
    row.id === targetTrackId
      ? { ...row, actions: [...row.actions, action] }
      : row
  ));
  const { rows: nextRows, metaPatches, adjustments: _adjustments } = resolveOverlaps(
    rowsWithClip,
    targetTrackId,
    clipId,
    current.meta,
  );
  const resolvedAction = nextRows
    .find((row) => row.id === targetTrackId)
    ?.actions.find((candidate) => candidate.id === clipId);
  const nextClipOrder = updateClipOrder(current.clipOrder, targetTrackId, (ids) => [...ids, clipId]);

  applyEdit({
    type: 'rows',
    rows: nextRows,
    metaUpdates: {
      ...metaPatches,
      [clipId]: {
        ...clipMeta,
        hold: resolvedAction ? Math.max(0.05, resolvedAction.end - resolvedAction.start) : clipMeta.hold,
      },
    },
    clipOrderOverride: nextClipOrder,
  });
  return true;
}

export async function handleFileDrop({
  files,
  dataRef,
  timelineId,
  pendingOpsRef,
  dropPosition,
  insertAtTop,
  selectedTrackId,
  applyEdit,
  patchRegistry,
  uploadAsset,
  invalidateAssetRegistry,
  assetResolver,
  registerGenerationAsset,
  uploadImageGeneration,
  uploadVideoGeneration,
  dropAsset,
}: {
  files: File[];
  dataRef: MutableRefObject<TimelineData | null>;
  timelineId: string;
  pendingOpsRef: MutableRefObject<number>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  selectedTrackId: string | null;
  applyEdit: TimelineApplyEdit;
  patchRegistry: TimelinePatchRegistry;
  uploadAsset: TimelineUploadAsset;
  invalidateAssetRegistry: TimelineInvalidateAssetRegistry;
  assetResolver: AssetResolver;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  uploadImageGeneration: UseAssetManagementResult['uploadImageGeneration'];
  uploadVideoGeneration: UseAssetManagementResult['uploadVideoGeneration'];
  dropAsset: UseAssetManagementResult['handleAssetDrop'];
}): Promise<boolean> {
  if (!files.length || !dataRef.current) {
    return false;
  }

  const defaultClipDuration = 5;
  let timeOffset = 0;

  for (const file of files) {
    const kind = inferFileDropKind(file);
    let compatibleTrackId = dropPosition.isNewTrack
      ? null
      : getCompatibleTrackId(dataRef.current.tracks, dropPosition.trackId, kind, selectedTrackId);

    if (!compatibleTrackId) {
      compatibleTrackId = createTrackForDrop(dataRef, kind, insertAtTop)?.trackId ?? null;
    }

    if (!compatibleTrackId || !dataRef.current) {
      continue;
    }

    const clipTime = dropPosition.time + timeOffset;
    timeOffset += defaultClipDuration;

    const skeletonId = `uploading-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const skeletonMeta: ClipMeta = {
      asset: `uploading:${file.name}`,
      track: compatibleTrackId,
      clipType: kind === 'audio' ? 'media' : 'hold',
      hold: kind === 'audio' ? undefined : defaultClipDuration,
      from: kind === 'audio' ? 0 : undefined,
      to: kind === 'audio' ? defaultClipDuration : undefined,
    };
    const skeletonAction: TimelineAction = {
      id: skeletonId,
      start: clipTime,
      end: clipTime + defaultClipDuration,
      effectId: `effect-${skeletonId}`,
    };

    const nextRows = dataRef.current.rows.map((row) =>
      row.id === compatibleTrackId
        ? { ...row, actions: [...row.actions, skeletonAction] }
        : row,
    );
    applyEdit({
      type: 'rows',
      rows: nextRows,
      metaUpdates: { [skeletonId]: skeletonMeta },
    }, { save: false });

    pendingOpsRef.current += 1;
    void (async () => {
      try {
        if (isImageFile(file)) {
          const generationData = await uploadImageGeneration(file);
          const current = dataRef.current;
          if (!current) {
            return;
          }

          applyEdit({
            type: 'rows',
            rows: removeAction(current.rows, skeletonId),
            metaDeletes: [skeletonId],
          });
          const assetId = registerGenerationAsset(generationData);
          if (assetId) {
            dropAsset(assetId, compatibleTrackId ?? undefined, clipTime);
          }
          return;
        }

        if (isVideoFile(file)) {
          const generationData = await uploadVideoGeneration(file);
          const current = dataRef.current;
          if (!current) {
            return;
          }

          applyEdit({
            type: 'rows',
            rows: removeAction(current.rows, skeletonId),
            metaDeletes: [skeletonId],
          });
          const assetId = registerGenerationAsset(generationData);
          if (assetId) {
            dropAsset(assetId, compatibleTrackId ?? undefined, clipTime);
          }
          return;
        }

        const result = await uploadAsset(file);
        const sourceUrl = await resolveAssetUrlWithResolver(assetResolver, {
          file: result.entry.file,
          assetId: result.assetId,
          entry: result.entry,
          timelineId,
        });
        patchRegistry(result.assetId, result.entry, sourceUrl);

        const current = dataRef.current;
        if (!current) {
          return;
        }

        applyEdit({
          type: 'rows',
          rows: removeAction(current.rows, skeletonId),
          metaDeletes: [skeletonId],
        });
        dropAsset(result.assetId, compatibleTrackId ?? undefined, clipTime);
        void invalidateAssetRegistry();
      } catch (error) {
        console.error('[drop] Upload failed:', error);
        const current = dataRef.current;
        if (!current) {
          return;
        }

        applyEdit({
          type: 'rows',
          rows: removeAction(current.rows, skeletonId),
          metaDeletes: [skeletonId],
        }, { save: false });
      } finally {
        pendingOpsRef.current -= 1;
      }
    })();
  }

  return true;
}

export function handleMultiGenerationDrop({
  generationItems,
  dataRef,
  dropPosition,
  insertAtTop,
  registerGenerationAsset,
  selectedTrackId,
  dropAsset,
}: {
  generationItems: GenerationDropData[];
  dataRef: MutableRefObject<TimelineData | null>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  selectedTrackId: string | null;
  dropAsset: UseAssetManagementResult['handleAssetDrop'];
}): boolean {
  if (!generationItems.length || !dataRef.current) {
    return false;
  }

  let targetTrackId = dropPosition.isNewTrack ? undefined : dropPosition.trackId;
  let forceNewTrack = dropPosition.isNewTrack;
  let timeOffset = 0;

  for (const generationData of generationItems) {
    const durationContract = getDroppedGenerationDurationContract(generationData);
    const assetDurationSeconds = durationContract.assetDurationSeconds;
    const clipSpanSeconds = durationContract.clipSpanSeconds ?? 5;
    const registrationPlan = planGenerationAssetRegistration({
      generationId: generationData.generationId,
      variantId: generationData.variantId,
      variantType: generationData.variantType,
      imageUrl: generationData.imageUrl,
      thumbUrl: generationData.thumbUrl,
      assetDurationSeconds,
      metadata: generationData.metadata,
    });
    if (!registrationPlan.ok) {
      continue;
    }

    const playableKind = getPlayableAssetKind(registrationPlan.assetEntry);
    if (!playableKind) {
      continue;
    }
    const assetKind = playableKind === 'audio' ? 'audio' : 'visual';
    const targetPlan = planAssetDropTarget({
      current: dataRef.current,
      assetKind,
      trackId: targetTrackId,
      selectedTrackId,
      forceNewTrack,
      insertAtTop: forceNewTrack ? insertAtTop : false,
      time: dropPosition.time + timeOffset,
      duration: clipSpanSeconds,
    });
    if (!targetPlan.ok) {
      continue;
    }
    const previewEdit = buildAssetDropEdit({
      current: targetPlan.preparedCurrent,
      assetKey: registrationPlan.assetId,
      assetEntry: registrationPlan.assetEntry,
      trackId: targetPlan.trackId,
      time: targetPlan.snappedTime ?? (dropPosition.time + timeOffset),
      clipSpanSeconds,
    });
    if (!previewEdit) {
      continue;
    }

    const trackIdsBeforeDrop = new Set(dataRef.current.tracks.map((track) => track.id));
    const assetId = registerGenerationAsset({
      ...generationData,
      assetId: registrationPlan.assetId,
      ...(assetDurationSeconds !== null ? { durationSeconds: assetDurationSeconds } : {}),
    });

    if (!assetId) {
      continue;
    }

    dropAsset(
      assetId,
      targetTrackId,
      dropPosition.time + timeOffset,
      forceNewTrack,
      forceNewTrack ? insertAtTop : false,
    );

    timeOffset += previewEdit.duration;

    if (!forceNewTrack || !dataRef.current) {
      continue;
    }

    const createdTrackId = dataRef.current.tracks.find((track) => !trackIdsBeforeDrop.has(track.id))?.id
      ?? (insertAtTop ? dataRef.current.tracks[0]?.id : dataRef.current.tracks[dataRef.current.tracks.length - 1]?.id);
    if (createdTrackId) {
      targetTrackId = createdTrackId;
    }
    forceNewTrack = false;
  }

  return true;
}

export function handleSingleGenerationDrop({
  generationData,
  dataRef,
  dropPosition,
  insertAtTop,
  registerGenerationAsset,
  selectedTrackId,
  dropAsset,
}: {
  generationData: GenerationDropData;
  dataRef: MutableRefObject<TimelineData | null>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  selectedTrackId: string | null;
  dropAsset: UseAssetManagementResult['handleAssetDrop'];
}): boolean {
  if (!dataRef.current) {
    return false;
  }

  const durationContract = getDroppedGenerationDurationContract(generationData);
  const assetDurationSeconds = durationContract.assetDurationSeconds;
  const clipSpanSeconds = durationContract.clipSpanSeconds ?? 5;
  const registrationPlan = planGenerationAssetRegistration({
    generationId: generationData.generationId,
    variantId: generationData.variantId,
    variantType: generationData.variantType,
    imageUrl: generationData.imageUrl,
    thumbUrl: generationData.thumbUrl,
    assetDurationSeconds,
    metadata: generationData.metadata,
  });
  if (!registrationPlan.ok) {
    return true;
  }
  const playableKind = getPlayableAssetKind(registrationPlan.assetEntry);
  if (!playableKind) {
    return true;
  }
  const assetKind = playableKind === 'audio' ? 'audio' : 'visual';
  const targetPlan = planAssetDropTarget({
    current: dataRef.current,
    assetKind,
    trackId: dropPosition.isNewTrack ? undefined : dropPosition.trackId,
    selectedTrackId,
    forceNewTrack: dropPosition.isNewTrack,
    insertAtTop,
    time: dropPosition.time,
    duration: clipSpanSeconds,
  });
  if (!targetPlan.ok) {
    return true;
  }
  const previewEdit = buildAssetDropEdit({
    current: targetPlan.preparedCurrent,
    assetKey: registrationPlan.assetId,
    assetEntry: registrationPlan.assetEntry,
    trackId: targetPlan.trackId,
    time: targetPlan.snappedTime ?? dropPosition.time,
    clipSpanSeconds,
  });
  if (!previewEdit) {
    return true;
  }

  const assetId = registerGenerationAsset({
    ...generationData,
    assetId: registrationPlan.assetId,
    ...(assetDurationSeconds !== null ? { durationSeconds: assetDurationSeconds } : {}),
  });
  if (!assetId) {
    return true;
  }

  dropAsset(
    assetId,
    dropPosition.isNewTrack ? undefined : dropPosition.trackId,
    dropPosition.time,
    dropPosition.isNewTrack,
    insertAtTop,
  );
  return true;
}

export function handleAssetDrop({
  assetKey,
  assetKind,
  dataRef,
  dropPosition,
  insertAtTop,
  selectedTrackId,
  dropAsset,
}: {
  assetKey: string;
  assetKind: TrackKind;
  dataRef: MutableRefObject<TimelineData | null>;
  dropPosition: TimelineDropPosition;
  insertAtTop: boolean;
  selectedTrackId: string | null;
  dropAsset: UseAssetManagementResult['handleAssetDrop'];
}): boolean {
  if (!assetKey || !dataRef.current) {
    return false;
  }

  if (dropPosition.isNewTrack) {
    dropAsset(assetKey, undefined, dropPosition.time, true, insertAtTop);
    return true;
  }

  const compatibleTrackId = getCompatibleTrackId(
    dataRef.current.tracks,
    dropPosition.trackId,
    assetKind || 'visual',
    selectedTrackId,
  );
  if (!compatibleTrackId) {
    return true;
  }

  dropAsset(assetKey, compatibleTrackId, dropPosition.time);
  return true;
}

export function finalizeExternalDrop({
  event,
  coordinator,
  autoScrollerRef,
  externalDragFrameRef,
  latestExternalDragRef,
  latestExternalPositionRef,
}: {
  event: DragEvent<HTMLDivElement>;
  coordinator: DragCoordinator;
  autoScrollerRef: MutableRefObject<ReturnType<typeof createAutoScroller> | null>;
  externalDragFrameRef: MutableRefObject<number | null>;
  latestExternalDragRef: MutableRefObject<{
    clientX: number;
    clientY: number;
    sourceKind: TrackKind | null;
  } | null>;
  latestExternalPositionRef: MutableRefObject<ReturnType<DragCoordinator['update']> | null>;
}): TimelineDropPosition {
  event.preventDefault();
  delete event.currentTarget.dataset.dragOver;
  autoScrollerRef.current?.stop();
  autoScrollerRef.current = null;
  if (externalDragFrameRef.current !== null) {
    window.cancelAnimationFrame(externalDragFrameRef.current);
    externalDragFrameRef.current = null;
  }

  if (latestExternalDragRef.current) {
    latestExternalPositionRef.current = coordinator.update({
      clientX: latestExternalDragRef.current.clientX,
      clientY: latestExternalDragRef.current.clientY,
      sourceKind: latestExternalDragRef.current.sourceKind,
    });
  }

  const dropPosition = coordinator.lastPosition
    ?? latestExternalPositionRef.current
    ?? coordinator.update({
      clientX: event.clientX,
      clientY: event.clientY,
      sourceKind: inferDragKind(event),
    });

  latestExternalDragRef.current = null;
  latestExternalPositionRef.current = null;
  coordinator.end();
  return dropPosition;
}
