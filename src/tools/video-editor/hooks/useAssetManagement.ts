import { useCallback } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { GenerationDropData } from '@/shared/lib/dnd/dragDrop';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { getMediaUrl, getThumbnailUrl } from '@/shared/lib/media/mediaTypeHelpers';
import { uploadBlobToStorage, uploadImageToStorage } from '@/shared/lib/media/imageUploader';
import { extractVideoMetadata } from '@/shared/lib/media/videoMetadata';
import { extractVideoPosterFrame } from '@/shared/lib/media/videoPosterExtractor';
import { generateClientThumbnail, uploadImageWithThumbnail } from '@/shared/media/clientThumbnailGenerator';
import type { SelectClipOptions } from '@/shared/state/selectionStore';
import { createExternalUploadGeneration } from '@/integrations/supabase/repositories/generationMutationsRepository';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import {
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import {
  buildAssetDropEdit,
  estimateAssetDuration,
  executeGenerationAssetRegistrationPlan,
  getPlayableAssetKind,
  planAssetDropTarget,
  planGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans';
import type {
  TimelineApplyEdit,
  TimelineInvalidateAssetRegistry,
  TimelinePatchRegistry,
  TimelineRegisterAsset,
  TimelineUnpatchRegistry,
  TimelineUploadAsset,
} from '@/tools/video-editor/hooks/timeline-state-types';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';

type UploadedGenerationData = GenerationDropData & {
  assetId?: string;
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
export { buildAssetDropEdit };
export type { BuildAssetDropEditResult } from '@/tools/video-editor/lib/timeline-asset-plans';

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
  const plan = planAssetDropTarget({
    current: dataRef.current,
    assetKind,
    trackId,
    selectedTrackId,
    forceNewTrack,
    insertAtTop,
    time,
    duration,
  });
  if (!plan.ok) {
    return null;
  }

  dataRef.current = plan.preparedCurrent;
  return {
    current: plan.preparedCurrent,
    trackId: plan.trackId,
    ...(plan.snappedTime !== undefined ? { snappedTime: plan.snappedTime } : {}),
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
  const runtime = useVideoEditorRuntime();
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

    const plan = planGenerationAssetRegistration({
      generationId: generationData.generationId,
      assetId: generationData.assetId,
      variantId: generationData.variantId,
      variantType: generationData.variantType,
      imageUrl: getMediaUrl(generationData),
      thumbUrl: getThumbnailUrl(generationData),
      assetDurationSeconds: generationData.durationSeconds,
      metadata: generationData.metadata,
    });
    if (!plan.ok) {
      console.warn('[video-editor] Skipping generation asset registration because media URL is empty', {
        generationId: generationData.generationId,
        variantId: generationData.variantId,
        variantType: generationData.variantType,
      });
      return null;
    }

    const { assetKey, persistPromise } = executeGenerationAssetRegistrationPlan({
      plan,
      patchRegistry: getPatchRegistry(),
      registerAsset: getRegisterAsset(),
    });
    void persistPromise.catch((error) => {
      console.error('[video-editor] Failed to persist generation asset:', error);
      getUnpatchRegistry()(assetKey);
      runtime.toast.error('Failed to save asset');
    });

    return assetKey;
  }, [getPatchRegistry, getRegisterAsset, getUnpatchRegistry, runtime.toast]);

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
      runtime.toast.error('Only image, video, and audio assets can be added to the timeline');
      return;
    }
    const assetKind = playableKind === 'audio' ? 'audio' : 'visual';
    const duration = estimateAssetDuration(assetEntry, assetKind);
    const targetPlan = planAssetDropTarget({
      current,
      assetKind,
      trackId,
      selectedTrackId: getSelectedTrackId(),
      forceNewTrack,
      insertAtTop,
      time,
      duration,
    });
    if (!targetPlan.ok) {
      return;
    }
    const resolvedTarget = {
      current: targetPlan.preparedCurrent,
      trackId: targetPlan.trackId,
      snappedTime: targetPlan.snappedTime,
    };
    const nextEdit = buildAssetDropEdit({
      current: resolvedTarget.current,
      assetKey,
      trackId: resolvedTarget.trackId,
      time: resolvedTarget.snappedTime ?? time,
    });
    if (!nextEdit) {
      return;
    }
    latestDataRef.current = resolvedTarget.current;
    getApplyEdit()({
      type: 'rows',
      rows: nextEdit.rows,
      metaUpdates: nextEdit.metaUpdates,
      clipOrderOverride: nextEdit.clipOrderOverride,
    });
    getSelectClip()(nextEdit.clipId);
    getSetSelectedTrackId()(resolvedTarget.trackId);
  }, [getApplyEdit, getDataRef, getSelectedTrackId, getSelectClip, getSetSelectedTrackId, runtime.toast]);

  return {
    registerGenerationAsset,
    uploadImageGeneration,
    uploadVideoGeneration,
    handleAssetDrop,
  };
}
