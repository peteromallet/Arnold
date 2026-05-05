import { useCallback, useEffect, useRef } from 'react';
import type { Shot } from '@/domains/generation/types/index.ts';
import { getMediaUrl, getThumbnailUrl } from '@/shared/lib/media/mediaTypeHelpers.ts';
import { selectTimelineImages } from '@/shared/lib/shotImageSelectors.ts';
import { buildAssetDropEdit, type UseAssetManagementResult } from '@/tools/video-editor/hooks/useAssetManagement.ts';
import type { TimelineApplyEdit, TimelineDataRef } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import {
  buildPinShotGroupMutation,
  buildUnpinShotGroupMutation,
  buildUpdatePinnedShotGroupMutation,
  clonePinnedShotGroup,
} from '@/tools/video-editor/lib/shot-group-commands.ts';
import { orderClipIdsByAt, resolveGroupTrackId } from '@/tools/video-editor/lib/pinned-group-projection.ts';
import { ensureGroupContiguity } from '@/tools/video-editor/lib/shot-group-contiguity.ts';
import type { ClipMeta, TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { PinnedShotGroup } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

interface UsePinnedShotGroupsArgs {
  dataRef: TimelineDataRef;
  applyEdit: TimelineApplyEdit;
}

interface UsePinnedGroupSyncArgs extends UsePinnedShotGroupsArgs {
  data: TimelineData | null;
  shots: Shot[] | undefined;
  registerGenerationAsset: UseAssetManagementResult['registerGenerationAsset'];
  isInteractionActive?: () => boolean;
  debounceMs?: number;
}

type PinnedShotGroupUpdates = Partial<Omit<PinnedShotGroup, 'shotId' | 'trackId'>>;

function getPinnedShotGroups(dataRef: TimelineDataRef) {
  return dataRef.current?.config.pinnedShotGroups;
}

function readPinnedShotGroups(dataRef: TimelineDataRef): NonNullable<ReturnType<typeof getPinnedShotGroups>> {
  return getPinnedShotGroups(dataRef) ?? [];
}

function getSyncableShotImages(shot: Shot | undefined) {
  return selectTimelineImages(shot?.images ?? []);
}

function areStringArraysEqual(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function getClipGenerationId(current: TimelineData, clipId: string): string | undefined {
  const assetKey = current.meta[clipId]?.asset;
  const generationId = assetKey ? current.registry.assets[assetKey]?.generationId : undefined;
  return typeof generationId === 'string' && generationId.length > 0 ? generationId : undefined;
}

function getAverageDuration(actions: TimelineAction[]) {
  if (actions.length === 0) {
    return 5;
  }

  const total = actions.reduce((sum, action) => sum + Math.max(0.05, action.end - action.start), 0);
  return total / actions.length;
}

function appendActionToTrack({
  current,
  trackId,
  action,
}: {
  current: TimelineData;
  trackId: string;
  action: TimelineAction;
}): TimelineData {
  return {
    ...current,
    rows: current.rows.map((row) => (
      row.id === trackId
        ? { ...row, actions: [...row.actions, action] }
        : row
    )),
    clipOrder: {
      ...current.clipOrder,
      [trackId]: [...(current.clipOrder[trackId] ?? []), action.id],
    },
  };
}

export function usePinnedShotGroups({
  dataRef,
  applyEdit,
}: UsePinnedShotGroupsArgs) {
  const pinGroup = useCallback((shotId: string, trackId: string, clipIds: string[]) => {
    const current = dataRef.current;
    const mutation = buildPinShotGroupMutation(current, {
      shotId,
      trackId,
      clipIds,
      mode: 'images',
    });
    if (!mutation) {
      return;
    }

    applyEdit(mutation);
  }, [applyEdit, dataRef]);

  const unpinGroup = useCallback((shotId: string, trackId: string) => {
    const mutation = buildUnpinShotGroupMutation(dataRef.current, { shotId, trackId });
    if (!mutation) {
      return;
    }

    applyEdit(mutation);
  }, [applyEdit, dataRef]);

  const updatePinnedGroup = useCallback((shotId: string, trackId: string, updates: PinnedShotGroupUpdates) => {
    const mutation = buildUpdatePinnedShotGroupMutation(dataRef.current, { shotId, trackId }, updates);
    if (!mutation) {
      return;
    }

    applyEdit(mutation);
  }, [applyEdit, dataRef]);

  return {
    pinGroup,
    unpinGroup,
    updatePinnedGroup,
  };
}

export function usePinnedGroupSync({
  data,
  dataRef,
  applyEdit,
  shots,
  registerGenerationAsset,
  isInteractionActive: _isInteractionActive,
  debounceMs = 300,
}: UsePinnedGroupSyncArgs) {
  const timeoutRef = useRef<number | null>(null);
  const isInteractionActive = _isInteractionActive ?? (() => false);

  useEffect(() => {
    const current = dataRef.current;
    const pinnedShotGroups = current?.config.pinnedShotGroups ?? [];
    if (!data || !shots || pinnedShotGroups.length === 0) {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      return;
    }

    const clearScheduledSync = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const scheduleSync = () => {
      clearScheduledSync();
      timeoutRef.current = window.setTimeout(() => {
        timeoutRef.current = null;
        runSync();
      }, debounceMs);
    };

    const runSync = () => {
      const latest = dataRef.current;
      if (!latest) {
        return;
      }

      if (isInteractionActive()) {
        scheduleSync();
        return;
      }

      let workingData = latest;
      let workingPinnedShotGroups = (latest.config.pinnedShotGroups ?? []).map(clonePinnedShotGroup);
      const accumulatedMetaUpdates: Record<string, ClipMeta> = {};
      const accumulatedMetaDeletes = new Set<string>();
      let hasChanges = false;

      for (const group of workingPinnedShotGroups) {
        if (group.mode !== 'images') {
          continue;
        }

        const resolvedTrackId = resolveGroupTrackId(group, workingData.rows);
        const storedTrackId = group.trackId;

        const shot = shots.find((candidate) => candidate.id === group.shotId);
        const desiredImages = getSyncableShotImages(shot);
        const desiredGenerationIds = desiredImages
          .map((image) => image.generation_id)
          .filter((generationId): generationId is string => typeof generationId === 'string' && generationId.length > 0);

        const targetRowIndex = workingData.rows.findIndex((row) => row.id === resolvedTrackId);
        if (targetRowIndex < 0) {
          continue;
        }

        const targetRow = workingData.rows[targetRowIndex];
        const orderedCurrentClipIds = orderClipIdsByAt(group.clipIds, { rows: [targetRow] });
        const currentGenerationIds = orderedCurrentClipIds
          .map((clipId) => getClipGenerationId(workingData, clipId))
          .filter((generationId): generationId is string => typeof generationId === 'string' && generationId.length > 0);

        if (areStringArraysEqual(currentGenerationIds, desiredGenerationIds)) {
          continue;
        }

        const groupActions = targetRow.actions.filter((action) => group.clipIds.includes(action.id));
        if (groupActions.length === 0) {
          continue;
        }

        const firstGroupAction = targetRow.actions.findIndex((action) => action.id === groupActions[0]?.id);
        const lastGroupAction = targetRow.actions.findIndex((action) => action.id === groupActions[groupActions.length - 1]?.id);
        if (firstGroupAction < 0 || lastGroupAction < 0) {
          continue;
        }

        const beforeActions = targetRow.actions.slice(0, firstGroupAction);
        const afterActions = targetRow.actions.slice(lastGroupAction + 1);
        const beforeActionIds = new Set(beforeActions.map((action) => action.id));
        const afterActionIds = new Set(afterActions.map((action) => action.id));
        const originalGroupEnd = groupActions[groupActions.length - 1]?.end ?? groupActions[0].end;
        const averageDuration = getAverageDuration(groupActions);
        const groupActionById = new Map(groupActions.map((action) => [action.id, action]));
        const availableClipIds = [...orderedCurrentClipIds];

        let groupWorkingData: TimelineData = {
          ...workingData,
          rows: workingData.rows.map((row, rowIndex) => (
            rowIndex === targetRowIndex
              ? { ...row, actions: [...beforeActions] }
              : row
          )),
          clipOrder: {
            ...workingData.clipOrder,
            [resolvedTrackId]: (workingData.clipOrder[resolvedTrackId] ?? []).filter((clipId) => beforeActionIds.has(clipId)),
          },
        };

        const nextGroupClipIds: string[] = [];
        const usedClipIds = new Set<string>();
        let cursor = groupActions[0]?.start ?? 0;

        for (const desiredImage of desiredImages) {
          const desiredGenerationId = desiredImage.generation_id;
          const imageUrl = getMediaUrl(desiredImage);
          if (typeof desiredGenerationId !== 'string' || desiredGenerationId.length === 0) {
            continue;
          }
          if (!imageUrl) {
            continue;
          }

          const reusableClipId = availableClipIds.find((clipId) => (
            !usedClipIds.has(clipId)
            && getClipGenerationId(workingData, clipId) === desiredGenerationId
          ));

          if (reusableClipId) {
            const sourceAction = groupActionById.get(reusableClipId);
            const duration = sourceAction
              ? Math.max(0.05, sourceAction.end - sourceAction.start)
              : averageDuration;
            const action: TimelineAction = {
              id: reusableClipId,
              start: cursor,
              end: cursor + duration,
              effectId: `effect-${reusableClipId}`,
            };
            groupWorkingData = appendActionToTrack({
              current: groupWorkingData,
              trackId: resolvedTrackId,
              action,
            });
            nextGroupClipIds.push(reusableClipId);
            usedClipIds.add(reusableClipId);
            cursor = action.end;
            continue;
          }

          const assetKey = registerGenerationAsset({
            generationId: desiredGenerationId,
            variantType: 'image',
            imageUrl,
            thumbUrl: getThumbnailUrl(desiredImage) ?? imageUrl,
            metadata: {
              content_type: desiredImage.contentType ?? desiredImage.type ?? 'image/png',
            },
          });
          if (!assetKey) {
            continue;
          }

          const latestRegistryEntry = dataRef.current?.registry.assets[assetKey];
          if (latestRegistryEntry) {
            groupWorkingData = {
              ...groupWorkingData,
              registry: {
                ...groupWorkingData.registry,
                assets: {
                  ...groupWorkingData.registry.assets,
                  [assetKey]: latestRegistryEntry,
                },
              },
            };
          }

          const nextEdit = buildAssetDropEdit({
            current: groupWorkingData,
            assetKey,
            trackId: resolvedTrackId,
            time: cursor,
          });
          if (!nextEdit) {
            continue;
          }

          Object.assign(accumulatedMetaUpdates, nextEdit.metaUpdates);
          nextGroupClipIds.push(nextEdit.clipId);
          cursor += nextEdit.duration;
          groupWorkingData = {
            ...groupWorkingData,
            rows: nextEdit.rows,
            meta: {
              ...groupWorkingData.meta,
              ...nextEdit.metaUpdates,
            },
            clipOrder: nextEdit.clipOrderOverride,
          };
        }

        const removedClipIds = group.clipIds.filter((clipId) => !nextGroupClipIds.includes(clipId));
        for (const clipId of removedClipIds) {
          accumulatedMetaDeletes.add(clipId);
        }

        const afterShift = cursor - originalGroupEnd;
        const shiftedAfterActions = afterActions.map((action) => ({
          ...action,
          start: action.start + afterShift,
          end: action.end + afterShift,
        }));
        const rebuiltRow = groupWorkingData.rows[targetRowIndex];
        const nextRows = groupWorkingData.rows.map((row, rowIndex) => (
          rowIndex === targetRowIndex
            ? { ...row, actions: [...rebuiltRow.actions, ...shiftedAfterActions] }
            : row
        ));
        const nextClipOrder = {
          ...groupWorkingData.clipOrder,
          [resolvedTrackId]: [
            ...(groupWorkingData.clipOrder[resolvedTrackId] ?? []),
            ...(workingData.clipOrder[resolvedTrackId] ?? []).filter((clipId) => afterActionIds.has(clipId)),
          ],
        };
        const orderedNextGroupClipIds = orderClipIdsByAt(nextGroupClipIds, { rows: nextRows });
        const nextGroups = workingPinnedShotGroups
          .map((candidate) => (
            candidate.shotId === group.shotId && candidate.trackId === storedTrackId
              ? {
                  ...clonePinnedShotGroup(candidate),
                  ...(resolvedTrackId !== storedTrackId ? { trackId: resolvedTrackId } : {}),
                  clipIds: orderedNextGroupClipIds,
                }
              : clonePinnedShotGroup(candidate)
          ))
          .filter((candidate) => (
            candidate.shotId !== group.shotId
            || (candidate.trackId !== storedTrackId && candidate.trackId !== resolvedTrackId)
            || candidate.clipIds.length > 0
          ));

        workingPinnedShotGroups = nextGroups;
        workingData = {
          ...groupWorkingData,
          config: {
            ...groupWorkingData.config,
            pinnedShotGroups: nextGroups,
          },
          rows: nextRows,
          clipOrder: nextClipOrder,
        };
        hasChanges = true;
      }

      if (!hasChanges) {
        return;
      }

      const contiguousRows = ensureGroupContiguity(workingData.rows, workingPinnedShotGroups);

      applyEdit({
        type: 'rows',
        rows: contiguousRows,
        metaUpdates: Object.keys(accumulatedMetaUpdates).length > 0 ? accumulatedMetaUpdates : undefined,
        metaDeletes: accumulatedMetaDeletes.size > 0 ? [...accumulatedMetaDeletes] : undefined,
        clipOrderOverride: workingData.clipOrder,
        pinnedShotGroupsOverride: workingPinnedShotGroups,
      });
    };

    scheduleSync();

    return () => {
      clearScheduledSync();
    };
  }, [applyEdit, data, dataRef, debounceMs, isInteractionActive, registerGenerationAsset, shots]);
}
