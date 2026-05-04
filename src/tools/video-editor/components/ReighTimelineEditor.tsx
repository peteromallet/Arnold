import { memo, useCallback, useMemo, useState } from 'react';
import { shallow } from 'zustand/shallow';
import type { Shot } from '@/domains/generation/types';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { VideoGenerationModal } from '@/tools/travel-between-images/components/VideoGenerationModal';
import { TimelineEditorCore, resolveSelectedGenerationIdsForShotCreation } from '@/tools/video-editor/components/TimelineEditor/TimelineEditorCore';
import { useActiveTaskClips } from '@/tools/video-editor/hooks/useActiveTaskClips';
import { useFinalVideoAvailable } from '@/tools/video-editor/hooks/useFinalVideoAvailable';
import { usePinnedGroupSync, usePinnedShotGroups } from '@/tools/video-editor/hooks/usePinnedShotGroups';
import { useShotGroupHandlers } from '@/tools/video-editor/hooks/useShotGroupHandlers';
import { useShotGroups } from '@/tools/video-editor/hooks/useShotGroups';
import { useSwitchToFinalVideo } from '@/tools/video-editor/hooks/useSwitchToFinalVideo';
import {
  useTimelineDataSelector,
  useTimelineOpsSelector,
} from '@/tools/video-editor/hooks/timelineStore';
import { buildDuplicateClipEdit } from '@/tools/video-editor/lib/duplicate-clip';
import { duplicateGenerationAsset } from '@/tools/video-editor/lib/generation-utils';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data';

interface ReighTimelineEditorProps {
  onOpenSequenceCreator?: () => void;
}

const EMPTY_ASSET_GENERATION_MAP: Record<string, string> = {};

function ReighTimelineEditorComponent({ onOpenSequenceCreator }: ReighTimelineEditorProps) {
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
    dataRef,
    selectedClipIds,
    interactionStateRef,
  } = useTimelineDataSelector((timeline) => ({
    data: timeline.data,
    resolvedConfig: timeline.resolvedConfig,
    dataRef: timeline.dataRef,
    selectedClipIds: timeline.selectedClipIds,
    interactionStateRef: timeline.interactionStateRef,
  }), shallow);
  const {
    applyEdit,
    patchRegistry,
    unpatchRegistry,
    registerAsset,
    registerGenerationAsset,
  } = useTimelineOpsSelector((ops) => ({
    applyEdit: ops.applyEdit,
    patchRegistry: ops.patchRegistry,
    unpatchRegistry: ops.unpatchRegistry,
    registerAsset: ops.registerAsset,
    registerGenerationAsset: ops.registerGenerationAsset,
  }), shallow);

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

  const selectionShotCreationState = useMemo(() => {
    if (!data?.rows || !data?.meta) {
      return { canCreateShot: false, generationIds: [] as string[] };
    }

    return resolveSelectedGenerationIdsForShotCreation({
      rows: data.rows,
      meta: data.meta,
      assetGenerationMap,
      selectedClipIds,
    });
  }, [assetGenerationMap, data?.meta, data?.rows, selectedClipIds]);

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
  }, [selectionShotCreationState.generationIds, shots]);

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

    const selectedClipId = [...selectedClipIds][0];
    const trackId = selectedClipId ? data?.meta[selectedClipId]?.track : undefined;

    const result = await createShot({ generationIds: selectionShotCreationState.generationIds });
    if (result?.shot && trackId) {
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

  const { activeTaskAssetKeys } = useActiveTaskClips({ registry: resolvedConfig?.registry });
  const { finalVideoMap, dismissFinalVideo } = useFinalVideoAvailable();
  const shotGroups = useShotGroups(
    data?.rows ?? [],
    shots,
    data?.config.pinnedShotGroups,
  );
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

  const isInteractionActive = useCallback(() => {
    return interactionStateRef.current.drag || interactionStateRef.current.resize;
  }, [interactionStateRef]);

  usePinnedGroupSync({
    data,
    dataRef,
    applyEdit,
    shots,
    registerGenerationAsset,
    isInteractionActive,
  });

  const handleOpenShotVideoModal = useCallback((shotId: string) => {
    const shot = shots?.find((candidate) => candidate.id === shotId);
    if (shot) {
      setVideoModalShot(shot);
    }
  }, [shots]);

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
        metaUpdates: duplicateEdit.metaUpdates as Record<string, Partial<ClipMeta>>,
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

  return (
    <>
      <TimelineEditorCore
        onOpenSequenceCreator={onOpenSequenceCreator}
        finalVideoMap={finalVideoMap}
        shotGroups={shotGroups}
        staleShotGroupIds={staleShotGroupIds}
        activeTaskClipIds={activeTaskClipIds}
        shotGroupClipIds={shotGroupClipIds}
        onShotGroupNavigate={handleShotGroupNavigate}
        onShotGroupGenerateVideo={handleShotGroupGenerateVideo}
        onShotGroupUnpin={handleShotGroupUnpin}
        onShotGroupDelete={handleDeleteShotGroup}
        onShotGroupSwitchToFinalVideo={handleShotGroupSwitchToFinalVideo}
        onShotGroupSwitchToImages={handleShotGroupSwitchToImages}
        onShotGroupUpdateToLatestVideo={handleUpdateToLatestVideo}
        canCreateShotFromSelection={selectionShotCreationState.canCreateShot}
        existingShots={existingShotsForSelection}
        onCreateShotFromSelection={handleCreateShotFromSelection}
        onGenerateVideoFromSelection={handleGenerateVideoFromSelection}
        onNavigateToShot={handleNavigateToShot}
        onOpenGenerateVideo={handleOpenGenerateVideo}
        isCreatingShot={isCreating}
        duplicatingClipId={duplicatingClipId}
        onDuplicateGenerationClip={handleDuplicateGenerationClip}
        onOpenShotVideoModal={handleOpenShotVideoModal}
      />

      {videoModalShot && (
        <VideoGenerationModal
          isOpen={true}
          onClose={() => { setVideoModalShot(null); setVideoModalShowImages(false); }}
          shot={videoModalShot}
          defaultTopOpen={videoModalShowImages}
        />
      )}
    </>
  );
}

export const ReighTimelineEditor = memo(ReighTimelineEditorComponent);
