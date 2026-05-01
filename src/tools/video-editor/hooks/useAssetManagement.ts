import { useCallback } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import { toast } from '@/shared/components/ui/runtime/sonner';
import type { GenerationDropData } from '@/shared/lib/dnd/dragDrop';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { getMediaUrl, getThumbnailUrl } from '@/shared/lib/media/mediaTypeHelpers';
import { uploadBlobToStorage, uploadImageToStorage } from '@/shared/lib/media/imageUploader';
import { extractVideoMetadata } from '@/shared/lib/media/videoMetadata';
import { extractVideoPosterFrame } from '@/shared/lib/media/videoPosterExtractor';
import { generateClientThumbnail, uploadImageWithThumbnail } from '@/shared/media/clientThumbnailGenerator';
import type { SelectClipOptions } from '@/shared/state/selectionStore';
import { createExternalUploadGeneration } from '@/integrations/supabase/repositories/generationMutationsRepository';
import { generateUUID } from '@/shared/lib/taskCreation/ids';
import { findNearestFreeTrack, getCompatibleTrackId, trySnapToEdge, updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { getTrackIndex } from '@/tools/video-editor/lib/editor-utils';
import {
  getNextClipId,
  type ClipMeta,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import type {
  TimelineApplyEdit,
  TimelineInvalidateAssetRegistry,
  TimelinePatchRegistry,
  TimelineRegisterAsset,
  TimelineUnpatchRegistry,
  TimelineUploadAsset,
} from '@/tools/video-editor/hooks/timeline-state-types';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas';
import type { AssetRegistryEntry, ClipType } from '@/tools/video-editor/types';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';

function estimateAssetDuration(
  assetEntry: AssetRegistryEntry | undefined,
  assetKind: 'audio' | 'visual',
): number {
  if (assetKind === 'audio') return assetEntry?.duration ?? 10;
  if (assetEntry?.type?.startsWith('image')) return 5;
  return assetEntry?.duration ?? 5;
}

function getPlayableAssetKind(assetEntry: AssetRegistryEntry | undefined): 'image' | 'video' | 'audio' | null {
  const mimeType = assetEntry?.type?.toLowerCase() ?? '';
  const file = (assetEntry?.file ?? assetEntry?.src ?? '').toLowerCase();

  if (mimeType.startsWith('image/') || /\.(png|jpe?g|gif|webp|avif|svg)$/i.test(file)) {
    return 'image';
  }
  if (mimeType.startsWith('video/') || /\.(mp4|mov|webm|m4v)$/i.test(file)) {
    return 'video';
  }
  if (mimeType.startsWith('audio/') || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(file)) {
    return 'audio';
  }

  return null;
}

type UploadedGenerationData = GenerationDropData & {
  durationSeconds?: number;
};

export interface UseAssetManagementArgs {
  store?: TimelineStoreApi;
  dataRef: MutableRefObject<TimelineData | null>;
  selectedTrackId: string | null;
  selectedProjectId: string | null;
  selectClip: (clipId: string, opts?: SelectClipOptions) => void;
  setSelectedTrackId: Dispatch<SetStateAction<string | null>>;
  applyEdit: TimelineApplyEdit;
  patchRegistry: TimelinePatchRegistry;
  unpatchRegistry: TimelineUnpatchRegistry;
  registerAsset: TimelineRegisterAsset;
  uploadAsset: TimelineUploadAsset;
  invalidateAssetRegistry: TimelineInvalidateAssetRegistry;
  resolveAssetUrl: (file: string) => Promise<string>;
}

export interface UseAssetManagementResult {
  registerGenerationAsset: (data: UploadedGenerationData | null) => string | null;
  uploadImageGeneration: (file: File) => Promise<{
    generationId: string;
    variantType: 'image';
    imageUrl: string;
    thumbUrl: string;
    metadata: {
      content_type: string;
      original_filename: string;
    };
  }>;
  uploadVideoGeneration: (file: File) => Promise<{
    generationId: string;
    variantType: 'video';
    imageUrl: string;
    thumbUrl: string;
    durationSeconds?: number;
    metadata: {
      content_type: string;
      original_filename: string;
    };
  }>;
  handleAssetDrop: (assetKey: string, trackId: string | undefined, time: number, forceNewTrack?: boolean, insertAtTop?: boolean) => void;
}

export interface AssetDropTargetResolution {
  current: TimelineData;
  trackId: string;
  snappedTime?: number;
}

export interface BuildAssetDropEditResult {
  clipId: string;
  duration: number;
  rows: TimelineData['rows'];
  metaUpdates: Record<string, ClipMeta>;
  clipOrderOverride: TimelineData['clipOrder'];
}

export function resolveAssetDropTarget({
  dataRef,
  assetKind,
  trackId,
  selectedTrackId,
  forceNewTrack = false,
  insertAtTop = false,
  time,
  duration,
}: {
  dataRef: MutableRefObject<TimelineData | null>;
  assetKind: 'audio' | 'visual';
  trackId: string | undefined;
  selectedTrackId: string | null;
  forceNewTrack?: boolean;
  insertAtTop?: boolean;
  time?: number;
  duration?: number;
}): AssetDropTargetResolution | null {
  let current = dataRef.current;
  if (!current) {
    return null;
  }

  let resolvedTrackId = forceNewTrack
    ? null
    : getCompatibleTrackId(current.tracks, trackId, assetKind, selectedTrackId);

  // When time/duration are provided, find the nearest free track (above or below)
  if (resolvedTrackId && time != null && duration != null) {
    const snapResult = trySnapToEdge(current.rows, resolvedTrackId, time, duration);
    if (snapResult.snapped) {
      return { current, trackId: resolvedTrackId, snappedTime: snapResult.time };
    }
    resolvedTrackId = findNearestFreeTrack(
      current.tracks, current.rows, resolvedTrackId, assetKind, time, duration,
    );
  }

  if (!resolvedTrackId) {
    const latest = dataRef.current;
    if (!latest) {
      return null;
    }

    // When overlap search exhausted all tracks, skip re-check and create a new track
    const existingTrackId = (forceNewTrack || (time != null && duration != null))
      ? null
      : getCompatibleTrackId(latest.tracks, trackId, assetKind, selectedTrackId);
    if (existingTrackId) {
      current = latest;
      resolvedTrackId = existingTrackId;
    } else {
      const prefix = assetKind === 'audio' ? 'A' : 'V';
      const nextNumber = getTrackIndex(latest.tracks, prefix) + 1;
      resolvedTrackId = `${prefix}${nextNumber}`;
      const newTrack = {
        id: resolvedTrackId,
        kind: assetKind,
        label: `${prefix}${nextNumber}`,
      };
      current = {
        ...latest,
        tracks: insertAtTop ? [newTrack, ...latest.tracks] : [...latest.tracks, newTrack],
        rows: insertAtTop ? [{ id: resolvedTrackId, actions: [] }, ...latest.rows] : [...latest.rows, { id: resolvedTrackId, actions: [] }],
      };
      dataRef.current = current;
    }
  }

  return resolvedTrackId
    ? { current, trackId: resolvedTrackId }
    : null;
}

export function buildAssetDropEdit({
  current,
  assetKey,
  trackId,
  time,
}: {
  current: TimelineData;
  assetKey: string;
  trackId: string;
  time: number;
}): BuildAssetDropEditResult | null {
  const assetEntry = current.registry.assets[assetKey];
  const playableKind = getPlayableAssetKind(assetEntry);
  if (!assetEntry || !playableKind) {
    return null;
  }
  const track = current.tracks.find((candidate) => candidate.id === trackId);
  if (!track) {
    return null;
  }
  if (track.kind === 'visual' && playableKind === 'audio') {
    return null;
  }
  if (track.kind === 'audio' && playableKind === 'image') {
    return null;
  }

  const clipId = getNextClipId(current.meta);
  const isImage = playableKind === 'image';
  const isVideo = playableKind === 'video';
  const isManual = track.fit === 'manual';
  const clipType: ClipType = isImage ? 'hold' : 'media';
  const baseDuration = isVideo
    ? (assetEntry?.duration ?? 5)
    : isImage
      ? 5
      : Math.max(1, assetEntry?.duration ?? 5);

  let clipMeta: ClipMeta;
  let duration: number;

  if (track.kind === 'audio') {
    duration = assetEntry?.duration ?? 10;
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType: 'media',
      from: 0,
      to: duration,
      speed: 1,
      volume: 1,
    };
  } else if (isImage) {
    duration = 5;
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType,
      hold: duration,
      opacity: 1,
      x: isManual ? 100 : undefined,
      y: isManual ? 100 : undefined,
      width: isManual ? 320 : undefined,
      height: isManual ? 240 : undefined,
    };
  } else {
    duration = baseDuration;
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType,
      from: 0,
      to: duration,
      speed: 1,
      volume: 1,
      opacity: 1,
      x: isManual ? 100 : undefined,
      y: isManual ? 100 : undefined,
      width: isManual ? 320 : undefined,
      height: isManual ? 240 : undefined,
    };
  }

  const action: TimelineAction = {
    id: clipId,
    start: time,
    end: time + duration,
    effectId: `effect-${clipId}`,
  };

  return {
    clipId,
    duration,
    rows: current.rows.map((row) => (row.id === trackId ? { ...row, actions: [...row.actions, action] } : row)),
    metaUpdates: { [clipId]: clipMeta },
    clipOrderOverride: updateClipOrder(current.clipOrder, trackId, (ids) => [...ids, clipId]),
  };
}

export function useAssetManagement({
  store,
  dataRef,
  selectedTrackId,
  selectedProjectId,
  selectClip,
  setSelectedTrackId,
  applyEdit,
  patchRegistry,
  unpatchRegistry,
  registerAsset,
}: UseAssetManagementArgs): UseAssetManagementResult {
  const getDataRef = useCallback(() => {
    const storeDataRef = store?.getState().data.dataRef;
    return storeDataRef && storeDataRef.current !== null ? storeDataRef : dataRef;
  }, [dataRef, store]);
  const getSelectedTrackId = useCallback(() => {
    return store?.getState().data.selectedTrackId ?? selectedTrackId;
  }, [selectedTrackId, store]);
  const getPatchRegistry = useCallback(() => {
    return store?.getState().ops.patchRegistry ?? patchRegistry;
  }, [patchRegistry, store]);
  const getUnpatchRegistry = useCallback(() => {
    return store?.getState().ops.unpatchRegistry ?? unpatchRegistry;
  }, [store, unpatchRegistry]);
  const getRegisterAsset = useCallback(() => {
    return store?.getState().ops.registerAsset ?? registerAsset;
  }, [registerAsset, store]);
  const getApplyEdit = useCallback(() => {
    return store?.getState().ops.applyEdit ?? applyEdit;
  }, [applyEdit, store]);
  const getSelectClip = useCallback(() => {
    return store?.getState().ops.selectClip ?? selectClip;
  }, [selectClip, store]);
  const getSetSelectedTrackId = useCallback(() => {
    return store?.getState().ops.setSelectedTrackId ?? setSelectedTrackId;
  }, [setSelectedTrackId, store]);

  const registerGenerationAsset = useCallback((generationData: UploadedGenerationData | null) => {
    if (!generationData) {
      return null;
    }

    const imageUrl = getMediaUrl(generationData);
    if (!imageUrl) {
      console.warn('[video-editor] Skipping generation asset registration because media URL is empty', {
        generationId: generationData.generationId,
        variantId: generationData.variantId,
        variantType: generationData.variantType,
      });
      return null;
    }
    const thumbnailUrl = getThumbnailUrl(generationData) ?? imageUrl;
    const lowerImageUrl = imageUrl.toLowerCase();

    const mimeType = (() => {
      const metadataContentType = typeof generationData.metadata?.content_type === 'string'
        ? generationData.metadata.content_type.toLowerCase()
        : null;
      if (metadataContentType?.includes('/')) {
        return metadataContentType;
      }
      if (metadataContentType === 'video' || generationData.variantType === 'video' || /\.(mp4|mov|webm|m4v)$/i.test(lowerImageUrl)) {
        return 'video/mp4';
      }
      if (metadataContentType === 'audio' || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(lowerImageUrl)) {
        return 'audio/mpeg';
      }
      if (/\.(txt|json|md|csv|vtt|srt|pdf)$/i.test(lowerImageUrl)) {
        return metadataContentType?.includes('/') ? metadataContentType : 'application/octet-stream';
      }
      return 'image/png';
    })();

    const assetId = generateUUID();
    const entry: AssetRegistryEntry = {
      file: imageUrl,
      type: mimeType,
      ...(typeof generationData.durationSeconds === 'number'
        ? { duration: generationData.durationSeconds }
        : {}),
      generationId: generationData.generationId,
      variantId: generationData.variantId,
      ...(thumbnailUrl !== imageUrl
        ? { thumbnailUrl }
        : {}),
    };

    getPatchRegistry()(assetId, entry, imageUrl);
    void getRegisterAsset()(assetId, entry).catch((error) => {
      console.error('[video-editor] Failed to persist generation asset:', error);
      getUnpatchRegistry()(assetId);
      toast.error('Failed to save asset');
    });

    return assetId;
  }, [getPatchRegistry, getRegisterAsset, getUnpatchRegistry]);

  const uploadImageGeneration = useCallback(async (file: File) => {
    if (!selectedProjectId) {
      throw new Error('External image drop requires a selected project');
    }

    let imageUrl = '';
    let thumbnailUrl = '';

    try {
      const thumbnailResult = await generateClientThumbnail(file, 300, 0.8);
      const uploadResult = await uploadImageWithThumbnail(file, thumbnailResult.thumbnailBlob);
      imageUrl = uploadResult.imageUrl;
      thumbnailUrl = uploadResult.thumbnailUrl;
    } catch (error) {
      normalizeAndPresentError(error, { context: `video-editor:external-drop:${file.name}`, showToast: false });
      imageUrl = await uploadImageToStorage(file, 3);
      thumbnailUrl = imageUrl;
    }

    const generation = await createExternalUploadGeneration({
      imageUrl,
      thumbnailUrl,
      fileType: 'image',
      projectId: selectedProjectId,
      generationParams: {
        prompt: `Uploaded ${file.name}`,
        extra: {
          source: 'external_upload',
          original_filename: file.name,
          file_type: file.type || 'image',
          file_size: file.size,
        },
      },
    });

    return {
      generationId: generation.id,
      variantType: 'image' as const,
      imageUrl,
      thumbUrl: thumbnailUrl,
      metadata: {
        content_type: file.type || 'image',
        original_filename: file.name,
      },
    };
  }, [selectedProjectId]);

  const uploadVideoGeneration = useCallback(async (file: File) => {
    if (!selectedProjectId) {
      throw new Error('No project selected');
    }

    const videoUrl = await uploadImageToStorage(file);

    let thumbnailUrl = videoUrl;
    try {
      const thumbnailBlob = await extractVideoPosterFrame(file);
      thumbnailUrl = await uploadBlobToStorage(thumbnailBlob, 'thumbnail.jpg', 'image/jpeg');
    } catch (error) {
      normalizeAndPresentError(error, { context: `video-editor:external-video-thumbnail:${file.name}`, showToast: false });
    }

    let durationSeconds: number | undefined;
    try {
      const metadata = await extractVideoMetadata(file);
      durationSeconds = metadata.duration_seconds;
    } catch (error) {
      normalizeAndPresentError(error, { context: `video-editor:external-video-metadata:${file.name}`, showToast: false });
    }

    const generation = await createExternalUploadGeneration({
      imageUrl: videoUrl,
      thumbnailUrl,
      fileType: 'video',
      projectId: selectedProjectId,
      generationParams: {
        prompt: file.name.replace(/\.[^.]+$/, ''),
        extra: {
          source: 'external_upload',
          original_filename: file.name,
          file_type: file.type || 'video/mp4',
          file_size: file.size,
        },
      },
    });

    return {
      generationId: generation.id,
      variantType: 'video' as const,
      imageUrl: videoUrl,
      thumbUrl: thumbnailUrl,
      durationSeconds,
      metadata: {
        content_type: file.type || 'video/mp4',
        original_filename: file.name,
      },
    };
  }, [selectedProjectId]);

  const handleAssetDrop = useCallback((assetKey: string, trackId: string | undefined, time: number, forceNewTrack = false, insertAtTop = false) => {
    const latestDataRef = getDataRef();
    const current = latestDataRef.current;
    const assetEntry = current?.registry.assets[assetKey];
    const playableKind = getPlayableAssetKind(assetEntry);
    if (!assetEntry || !playableKind) {
      toast.error('Only image, video, and audio assets can be added to the timeline');
      return;
    }
    const assetKind = playableKind === 'audio' ? 'audio' : 'visual';
    const duration = estimateAssetDuration(assetEntry, assetKind);
    const resolvedTarget = resolveAssetDropTarget({
      dataRef: latestDataRef,
      assetKind,
      trackId,
      selectedTrackId: getSelectedTrackId(),
      forceNewTrack,
      insertAtTop,
      time,
      duration,
    });
    if (!resolvedTarget) {
      return;
    }
    const nextEdit = buildAssetDropEdit({
      current: resolvedTarget.current,
      assetKey,
      trackId: resolvedTarget.trackId,
      time: resolvedTarget.snappedTime ?? time,
    });
    if (!nextEdit) {
      return;
    }
    getApplyEdit()({
      type: 'rows',
      rows: nextEdit.rows,
      metaUpdates: nextEdit.metaUpdates,
      clipOrderOverride: nextEdit.clipOrderOverride,
    });
    getSelectClip()(nextEdit.clipId);
    getSetSelectedTrackId()(resolvedTarget.trackId);
  }, [getApplyEdit, getDataRef, getSelectedTrackId, getSelectClip, getSetSelectedTrackId]);

  return {
    registerGenerationAsset,
    uploadImageGeneration,
    uploadVideoGeneration,
    handleAssetDrop,
  };
}
