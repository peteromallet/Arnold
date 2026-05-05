import { useCallback } from 'react';
import { generateUUID } from '@/shared/lib/taskCreation/ids.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { getFinalVideoReplacementDurationContract } from '@/tools/video-editor/lib/timeline-asset-durations.ts';
import { resolveFinalVideoDurationSeconds } from '@/tools/video-editor/lib/finalVideoAssets.ts';
import {
  executeGenerationAssetRegistrationPlan,
  planFinalVideoGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans.ts';
import {
  buildSwitchShotGroupToFinalVideoMutation,
  buildSwitchShotGroupToImagesMutation,
  buildUpdateShotGroupToLatestVideoMutation,
} from '@/tools/video-editor/lib/shot-group-commands.ts';
import { findGroupForTrack, resolveGroupTrackId } from '@/tools/video-editor/lib/pinned-group-projection.ts';
import type {
  TimelineApplyEdit,
  TimelineDataRef,
  TimelinePatchRegistry,
  TimelineRegisterAsset,
  TimelineUnpatchRegistry,
} from '@/tools/video-editor/hooks/timeline-state-types.ts';
import type { ShotFinalVideo } from '@/tools/video-editor/hooks/useFinalVideoAvailable.ts';

interface UseSwitchToFinalVideoArgs {
  applyEdit: TimelineApplyEdit;
  dataRef: TimelineDataRef;
  finalVideoMap: Map<string, ShotFinalVideo>;
  patchRegistry: TimelinePatchRegistry;
  unpatchRegistry: TimelineUnpatchRegistry;
  registerAsset: TimelineRegisterAsset;
}

function planFinalVideoAssetRegistration(
  finalVideo: ShotFinalVideo,
  currentData: TimelineDataRef['current'],
): Promise<{
  plan: Extract<ReturnType<typeof planFinalVideoGenerationAssetRegistration>, { ok: true }>;
  assetDurationSeconds: number | null;
}> {
  return (async () => {
    const durationContract = getFinalVideoReplacementDurationContract(
      await resolveFinalVideoDurationSeconds(finalVideo, currentData?.registry.assets),
    );
    const assetKey = generateUUID();
    const plan = planFinalVideoGenerationAssetRegistration({
      assetId: assetKey,
      generationId: finalVideo.id,
      imageUrl: finalVideo.location,
      thumbUrl: finalVideo.thumbnailUrl ?? finalVideo.location,
      assetDurationSeconds: durationContract.assetDurationSeconds,
    });
    if (!plan.ok) {
      throw new Error('Failed to plan final video asset registration.');
    }
    return {
      plan,
      assetDurationSeconds: durationContract.assetDurationSeconds,
    };
  })();
}

function buildRestoreShotGroupVideoMutation({
  currentData,
  shotId,
  rowId,
  assetKey,
  targetGenerationId,
}: {
  currentData: TimelineDataRef['current'];
  shotId: string;
  rowId: string;
  assetKey: string;
  targetGenerationId?: string;
}) {
  if (targetGenerationId) {
    const rollbackMutation = buildUpdateShotGroupToLatestVideoMutation({
      currentData,
      shotId,
      rowId,
      assetKey,
      targetGenerationId,
    });
    if (rollbackMutation) {
      return rollbackMutation;
    }
  }

  if (!currentData) {
    return null;
  }

  const pinnedShotGroups = currentData.config.pinnedShotGroups ?? [];
  const foundGroup = findGroupForTrack(pinnedShotGroups, shotId, rowId, currentData.rows);
  const pinnedGroup = foundGroup?.mode === 'video' && typeof foundGroup.videoAssetKey === 'string' && foundGroup.videoAssetKey.length > 0
    ? foundGroup
    : undefined;
  const resolvedTrackId = pinnedGroup ? resolveGroupTrackId(pinnedGroup, currentData.rows) : rowId;
  const videoClipId = pinnedGroup?.clipIds[0];
  const hasVideoClip = Boolean(
    videoClipId
    && currentData.rows.find((row) => row.id === resolvedTrackId)?.actions.some((action) => action.id === videoClipId)
    && currentData.meta[videoClipId],
  );
  if (!pinnedGroup || !videoClipId || !hasVideoClip) {
    return null;
  }

  return {
    type: 'rows' as const,
    rows: currentData.rows,
    metaUpdates: {
      [videoClipId]: {
        asset: assetKey,
      },
    },
    pinnedShotGroupsOverride: pinnedShotGroups.map((group) => (
      group === pinnedGroup
        ? { ...group, trackId: resolvedTrackId, videoAssetKey: assetKey }
        : group
    )),
  };
}

export function useSwitchToFinalVideo({
  applyEdit,
  dataRef,
  finalVideoMap,
  patchRegistry,
  unpatchRegistry,
  registerAsset,
}: UseSwitchToFinalVideoArgs) {
  const runtime = useVideoEditorRuntime();
  const switchToFinalVideo = useCallback(async ({ shotId, clipIds, rowId }: { shotId: string; clipIds: string[]; rowId: string }) => {
    const finalVideo = finalVideoMap.get(shotId);
    if (!finalVideo) {
      return;
    }

    const { plan, assetDurationSeconds } = await planFinalVideoAssetRegistration(finalVideo, dataRef.current);
    const mutation = buildSwitchShotGroupToFinalVideoMutation({
      currentData: dataRef.current,
      shotId,
      rowId,
      clipIds,
      assetKey: plan.assetId,
      durationSeconds: assetDurationSeconds,
    });
    if (!mutation) {
      return;
    }

    const { assetKey, persistPromise } = executeGenerationAssetRegistrationPlan({
      plan,
      patchRegistry,
      registerAsset,
    });
    applyEdit(mutation);
    void persistPromise.catch((error) => {
      console.error('[TimelineEditor] Failed to persist final video asset:', error);
      const rollbackMutation = buildSwitchShotGroupToImagesMutation({
        currentData: dataRef.current,
        shotId,
        rowId,
      });
      if (rollbackMutation) {
        applyEdit(rollbackMutation);
      }
      unpatchRegistry(assetKey);
      runtime.toast.error('Failed to save asset');
    });
  }, [applyEdit, dataRef, finalVideoMap, patchRegistry, registerAsset, runtime.toast, unpatchRegistry]);

  const updateToLatestVideo = useCallback(async ({ shotId, rowId }: { shotId: string; rowId: string }) => {
    const finalVideo = finalVideoMap.get(shotId);
    if (!finalVideo) {
      return;
    }

    const currentGroup = dataRef.current
      ? findGroupForTrack(dataRef.current.config.pinnedShotGroups ?? [], shotId, rowId, dataRef.current.rows)
      : undefined;
    const oldVideoAssetKey = currentGroup?.mode === 'video' ? currentGroup.videoAssetKey : undefined;
    const oldVideoGenerationId = oldVideoAssetKey
      ? dataRef.current?.registry.assets[oldVideoAssetKey]?.generationId
      : undefined;
    const { plan, assetDurationSeconds } = await planFinalVideoAssetRegistration(finalVideo, dataRef.current);
    const mutation = buildUpdateShotGroupToLatestVideoMutation({
      currentData: dataRef.current,
      shotId,
      rowId,
      assetKey: plan.assetId,
      targetGenerationId: finalVideo.id,
      durationSeconds: assetDurationSeconds,
    });
    if (!mutation) {
      return;
    }

    const { assetKey, persistPromise } = executeGenerationAssetRegistrationPlan({
      plan,
      patchRegistry,
      registerAsset,
    });
    applyEdit(mutation);
    void persistPromise.catch((error) => {
      console.error('[TimelineEditor] Failed to persist final video asset:', error);
      const rollbackMutation = oldVideoAssetKey
        ? buildRestoreShotGroupVideoMutation({
            currentData: dataRef.current,
            shotId,
            rowId,
            assetKey: oldVideoAssetKey,
            targetGenerationId: oldVideoGenerationId,
          })
        : null;
      if (rollbackMutation) {
        applyEdit(rollbackMutation);
      }
      unpatchRegistry(assetKey);
      runtime.toast.error('Failed to save asset');
    });
  }, [applyEdit, dataRef, finalVideoMap, patchRegistry, registerAsset, runtime.toast, unpatchRegistry]);

  const switchToImages = useCallback(({ shotId, rowId }: { shotId: string; rowId: string }) => {
    const mutation = buildSwitchShotGroupToImagesMutation({
      currentData: dataRef.current,
      shotId,
      rowId,
    });
    if (!mutation) {
      return;
    }

    applyEdit(mutation);
  }, [applyEdit, dataRef]);

  return {
    switchToFinalVideo,
    updateToLatestVideo,
    switchToImages,
  };
}
