import { updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils.ts';
import {
  findGroupForTrack,
  orderClipIdsByAt,
  resolveGroupTrackId,
} from '@/tools/video-editor/lib/pinned-group-projection.ts';
import { ensureGroupContiguity } from '@/tools/video-editor/lib/shot-group-contiguity.ts';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { PinnedShotGroup, PinnedShotImageClipSnapshot } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

type ShotGroupLocator = {
  shotId: string;
  trackId: string;
};

type ShotGroupModeInput = ShotGroupLocator & {
  clipIds: string[];
  mode?: PinnedShotGroup['mode'];
  videoAssetKey?: string;
  imageClipSnapshot?: PinnedShotGroup['imageClipSnapshot'];
};

type ShotGroupUpdates = Partial<Omit<PinnedShotGroup, 'shotId' | 'trackId'>>;

function cloneImageClipSnapshot(
  imageClipSnapshot: PinnedShotGroup['imageClipSnapshot'],
): PinnedShotGroup['imageClipSnapshot'] {
  return imageClipSnapshot?.map((snapshot) => ({
    ...snapshot,
    meta: { ...snapshot.meta },
  }));
}

export function clonePinnedShotGroup(group: PinnedShotGroup): PinnedShotGroup {
  return {
    ...group,
    clipIds: [...group.clipIds],
    imageClipSnapshot: cloneImageClipSnapshot(group.imageClipSnapshot),
  };
}

function buildPinnedShotGroupEntry(
  currentData: TimelineData,
  {
    shotId,
    trackId,
    clipIds,
    mode = 'images',
    videoAssetKey,
    imageClipSnapshot,
  }: ShotGroupModeInput,
): PinnedShotGroup {
  return {
    shotId,
    trackId,
    clipIds: orderClipIdsByAt(clipIds, {
      clips: currentData.config.clips,
      rows: currentData.rows,
    }),
    mode,
    ...(videoAssetKey ? { videoAssetKey } : {}),
    ...(imageClipSnapshot ? { imageClipSnapshot: cloneImageClipSnapshot(imageClipSnapshot) } : {}),
  };
}

function findLocatedPinnedShotGroup(
  currentData: TimelineData,
  locator: ShotGroupLocator,
  groups = currentData.config.pinnedShotGroups ?? [],
): {
  matchedGroup: PinnedShotGroup | undefined;
  resolvedTrackId: string;
} {
  const matchedGroup = findGroupForTrack(groups, locator.shotId, locator.trackId, currentData.rows);
  return {
    matchedGroup,
    resolvedTrackId: matchedGroup ? resolveGroupTrackId(matchedGroup, currentData.rows) : locator.trackId,
  };
}

export function buildPinnedShotGroupsOverride(
  currentData: TimelineData,
  nextGroup: ShotGroupModeInput,
  existingGroups = currentData.config.pinnedShotGroups ?? [],
): NonNullable<TimelineData['config']['pinnedShotGroups']> {
  const builtGroup = buildPinnedShotGroupEntry(currentData, nextGroup);
  const { matchedGroup } = findLocatedPinnedShotGroup(currentData, nextGroup, existingGroups);
  const existingIndex = matchedGroup ? existingGroups.indexOf(matchedGroup) : -1;

  if (existingIndex < 0) {
    return [...existingGroups.map(clonePinnedShotGroup), builtGroup];
  }

  return existingGroups.map((group, index) => (
    index === existingIndex ? builtGroup : clonePinnedShotGroup(group)
  ));
}

export function buildPinShotGroupMutation(
  currentData: TimelineData | null,
  group: ShotGroupModeInput,
) {
  if (!currentData) {
    return null;
  }

  return {
    type: 'pinnedShotGroups' as const,
    pinnedShotGroups: buildPinnedShotGroupsOverride(currentData, group),
  };
}

export function buildUnpinShotGroupMutation(
  currentData: TimelineData | null,
  { shotId, trackId }: ShotGroupLocator,
) {
  if (!currentData) {
    return null;
  }

  const { matchedGroup } = findLocatedPinnedShotGroup(currentData, { shotId, trackId });

  return {
    type: 'pinnedShotGroups' as const,
    pinnedShotGroups: (currentData.config.pinnedShotGroups ?? [])
      .filter((group) => (
        matchedGroup
          ? group !== matchedGroup
          : group.shotId !== shotId || group.trackId !== trackId
      ))
      .map(clonePinnedShotGroup),
  };
}

export function buildUpdatePinnedShotGroupMutation(
  currentData: TimelineData | null,
  { shotId, trackId }: ShotGroupLocator,
  updates: ShotGroupUpdates,
) {
  if (!currentData) {
    return null;
  }

  const { matchedGroup, resolvedTrackId } = findLocatedPinnedShotGroup(currentData, { shotId, trackId });

  return {
    type: 'pinnedShotGroups' as const,
    pinnedShotGroups: (currentData.config.pinnedShotGroups ?? []).map((group) => {
      if (group !== matchedGroup) {
        return clonePinnedShotGroup(group);
      }

      return buildPinnedShotGroupEntry(currentData, {
        shotId,
        trackId: resolvedTrackId,
        clipIds: updates.clipIds ?? group.clipIds,
        mode: updates.mode ?? group.mode,
        videoAssetKey: updates.videoAssetKey ?? group.videoAssetKey,
        imageClipSnapshot: updates.imageClipSnapshot ?? group.imageClipSnapshot,
      });
    }),
  };
}

export function buildDeleteShotGroupMutation({
  currentData,
  group,
}: {
  currentData: TimelineData | null;
  group: { shotId: string; trackId: string; clipIds: string[] };
}) {
  if (!currentData) {
    return null;
  }

  const deletedClipIds = [...new Set(group.clipIds)];
  const deletedClipIdSet = new Set(deletedClipIds);
  const { matchedGroup } = findLocatedPinnedShotGroup(currentData, group);

  return {
    type: 'rows' as const,
    rows: currentData.rows.map((row) => ({
      ...row,
      actions: row.actions.filter((action) => !deletedClipIdSet.has(action.id)),
    })),
    metaDeletes: deletedClipIds,
    pinnedShotGroupsOverride: (currentData.config.pinnedShotGroups ?? [])
      .filter((candidate) => (
        matchedGroup
          ? candidate !== matchedGroup
          : candidate.shotId !== group.shotId || candidate.trackId !== group.trackId
      ))
      .map(clonePinnedShotGroup),
  };
}

function getClipDuration(meta: ClipMeta, action: TimelineAction): number {
  if (typeof meta.hold === 'number' && Number.isFinite(meta.hold) && meta.hold > 0) {
    return meta.hold;
  }

  if (
    typeof meta.from === 'number'
    && typeof meta.to === 'number'
    && Number.isFinite(meta.from)
    && Number.isFinite(meta.to)
    && meta.to > meta.from
  ) {
    return Math.max(0.05, (meta.to - meta.from) / Math.max(meta.speed ?? 1, 0.01));
  }

  return Math.max(0.05, action.end - action.start);
}

function getTimelineDurationFromSourceDuration({
  sourceDurationSeconds,
  from = 0,
  speed = 1,
}: {
  sourceDurationSeconds?: number;
  from?: number;
  speed?: number;
}): number | null {
  if (
    typeof sourceDurationSeconds !== 'number'
    || !Number.isFinite(sourceDurationSeconds)
    || sourceDurationSeconds <= 0
  ) {
    return null;
  }

  const safeFrom = Number.isFinite(from) ? Math.max(0, from) : 0;
  const safeSpeed = Number.isFinite(speed) && speed > 0 ? speed : 1;
  const remainingSourceDuration = sourceDurationSeconds - safeFrom;
  if (remainingSourceDuration <= 0) {
    return 0.05;
  }

  return Math.max(0.05, remainingSourceDuration / safeSpeed);
}

function snapshotClipMeta(meta: ClipMeta): PinnedShotImageClipSnapshot['meta'] {
  return {
    clipType: meta.clipType,
    from: meta.from,
    to: meta.to,
    speed: meta.speed,
    hold: meta.hold,
    volume: meta.volume,
    x: meta.x,
    y: meta.y,
    width: meta.width,
    height: meta.height,
    cropTop: meta.cropTop,
    cropBottom: meta.cropBottom,
    cropLeft: meta.cropLeft,
    cropRight: meta.cropRight,
    opacity: meta.opacity,
    text: meta.text,
    entrance: meta.entrance,
    exit: meta.exit,
    continuous: meta.continuous,
    transition: meta.transition,
    effects: meta.effects,
    params: meta.params,
    pool_id: meta.pool_id,
    clip_order: meta.clip_order,
    source_uuid: meta.source_uuid,
    generation: meta.generation,
  };
}

export function buildSwitchShotGroupToFinalVideoMutation({
  currentData,
  shotId,
  rowId,
  clipIds,
  assetKey,
  durationSeconds,
}: {
  currentData: TimelineData | null;
  shotId: string;
  rowId: string;
  clipIds: string[];
  assetKey: string;
  durationSeconds?: number | null;
}) {
  if (!currentData || clipIds.length === 0) {
    return null;
  }

  const existingPinnedGroups = currentData.config.pinnedShotGroups ?? [];
  const pinnedGroup = findGroupForTrack(existingPinnedGroups, shotId, rowId, currentData.rows);
  const resolvedTrackId = pinnedGroup ? resolveGroupTrackId(pinnedGroup, currentData.rows) : rowId;
  const sourceClipIds = pinnedGroup?.mode === 'images' ? pinnedGroup.clipIds : clipIds;
  const clipIdSet = new Set(sourceClipIds);
  const targetRow = currentData.rows.find((row) => row.id === resolvedTrackId);
  if (!targetRow) {
    return null;
  }

  const imageActions = targetRow.actions.filter((action) => clipIdSet.has(action.id));
  if (imageActions.length !== sourceClipIds.length) {
    return null;
  }

  const startTime = Math.min(...imageActions.map((action) => action.start));
  const endTime = Math.max(...imageActions.map((action) => action.end));
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime <= startTime) {
    return null;
  }

  const imageClipSnapshot = sourceClipIds.flatMap((sourceClipId) => {
    const sourceMeta = currentData.meta[sourceClipId];
    const sourceAction = imageActions.find((action) => action.id === sourceClipId);
    if (!sourceMeta || !sourceAction) {
      return [];
    }

    return [{
      clipId: sourceClipId,
      assetKey: sourceMeta.asset,
      start: sourceAction.start,
      end: sourceAction.end,
      meta: snapshotClipMeta(sourceMeta),
    }];
  });
  if (imageClipSnapshot.length !== sourceClipIds.length) {
    return null;
  }

  const videoClipId = getNextClipId(currentData.meta);
  const targetTrack = currentData.tracks.find((track) => track.id === resolvedTrackId);
  const isManualVisualTrack = targetTrack?.kind === 'visual' && targetTrack.fit === 'manual';
  const imageSpanDuration = endTime - startTime;
  const duration = Math.min(
    imageSpanDuration,
    getTimelineDurationFromSourceDuration({ sourceDurationSeconds: durationSeconds ?? undefined }) ?? imageSpanDuration,
  );
  const videoMeta: ClipMeta = {
    asset: assetKey,
    track: resolvedTrackId,
    clipType: 'media',
    from: 0,
    to: duration,
    speed: 1,
    volume: 1,
    opacity: 1,
    x: isManualVisualTrack ? 100 : undefined,
    y: isManualVisualTrack ? 100 : undefined,
    width: isManualVisualTrack ? 320 : undefined,
    height: isManualVisualTrack ? 240 : undefined,
  };
  const videoAction: TimelineAction = {
    id: videoClipId,
    start: startTime,
    end: startTime + duration,
    effectId: `effect-${videoClipId}`,
  };

  const insertionIndex = targetRow.actions.findIndex((action) => clipIdSet.has(action.id));
  const nextRows = currentData.rows.map((row) => {
    const remainingActions = row.actions.filter((action) => !clipIdSet.has(action.id));
    if (row.id !== resolvedTrackId) {
      return remainingActions.length === row.actions.length ? row : { ...row, actions: remainingActions };
    }

    const nextActions = insertionIndex < 0
      ? [...remainingActions, videoAction]
      : [...remainingActions.slice(0, insertionIndex), videoAction, ...remainingActions.slice(insertionIndex)];
    return { ...row, actions: nextActions };
  });
  const nextClipOrder = updateClipOrder(currentData.clipOrder, resolvedTrackId, (ids) => {
    const filtered = ids.filter((id) => !clipIdSet.has(id));
    const orderInsertionIndex = ids.findIndex((id) => clipIdSet.has(id));
    return orderInsertionIndex < 0
      ? [...filtered, videoClipId]
      : [...filtered.slice(0, orderInsertionIndex), videoClipId, ...filtered.slice(orderInsertionIndex)];
  });

  return {
    type: 'rows' as const,
    rows: nextRows,
    metaUpdates: { [videoClipId]: videoMeta },
    metaDeletes: sourceClipIds,
    clipOrderOverride: nextClipOrder,
    pinnedShotGroupsOverride: buildPinnedShotGroupsOverride(currentData, {
      shotId,
      trackId: resolvedTrackId,
      clipIds: [videoClipId],
      mode: 'video',
      videoAssetKey: assetKey,
      imageClipSnapshot,
    }),
  };
}

export function buildUpdateShotGroupToLatestVideoMutation({
  currentData,
  shotId,
  rowId,
  assetKey,
  targetGenerationId,
  durationSeconds,
}: {
  currentData: TimelineData | null;
  shotId: string;
  rowId: string;
  assetKey: string;
  targetGenerationId: string;
  durationSeconds?: number | null;
}) {
  if (!currentData) {
    return null;
  }

  const existingPinnedGroups = currentData.config.pinnedShotGroups ?? [];
  const foundGroup = findGroupForTrack(existingPinnedGroups, shotId, rowId, currentData.rows);
  const pinnedGroup = foundGroup?.mode === 'video' && typeof foundGroup.videoAssetKey === 'string' && foundGroup.videoAssetKey.length > 0
    ? foundGroup
    : undefined;
  const resolvedTrackId = pinnedGroup ? resolveGroupTrackId(pinnedGroup, currentData.rows) : rowId;
  const videoClipId = pinnedGroup?.clipIds[0];
  const targetRow = currentData.rows.find((row) => row.id === resolvedTrackId);
  const videoAction = videoClipId ? targetRow?.actions.find((action) => action.id === videoClipId) : undefined;
  const videoMeta = videoClipId ? currentData.meta[videoClipId] : undefined;
  const currentGenerationId = pinnedGroup?.videoAssetKey
    ? currentData.registry.assets[pinnedGroup.videoAssetKey]?.generationId
    : undefined;
  if (!pinnedGroup || !videoClipId || !videoAction || !videoMeta || currentGenerationId === targetGenerationId) {
    return null;
  }

  const currentDuration = Math.max(0.05, videoAction.end - videoAction.start);
  const nextDuration = Math.min(
    currentDuration,
    getTimelineDurationFromSourceDuration({
      sourceDurationSeconds: durationSeconds ?? undefined,
      from: typeof videoMeta.from === 'number' ? videoMeta.from : 0,
      speed: typeof videoMeta.speed === 'number' ? videoMeta.speed : 1,
    }) ?? currentDuration,
  );
  const hasDurationChange = Math.abs(nextDuration - currentDuration) > 0.0001;
  const nextRows = hasDurationChange
    ? currentData.rows.map((row) => {
        if (row.id !== resolvedTrackId) {
          return row;
        }

        return {
          ...row,
          actions: row.actions.map((action) => (
            action.id === videoClipId
              ? { ...action, end: action.start + nextDuration }
              : action
          )),
        };
      })
    : currentData.rows;
  const from = typeof videoMeta.from === 'number' ? videoMeta.from : 0;
  const speed = typeof videoMeta.speed === 'number' && videoMeta.speed > 0 ? videoMeta.speed : 1;

  return {
    type: 'rows' as const,
    rows: nextRows,
    metaUpdates: {
      [videoClipId]: {
        asset: assetKey,
        ...(hasDurationChange ? { to: from + nextDuration * speed } : {}),
      },
    },
    pinnedShotGroupsOverride: buildPinnedShotGroupsOverride(currentData, {
      shotId,
      trackId: resolvedTrackId,
      clipIds: pinnedGroup.clipIds,
      mode: pinnedGroup.mode,
      videoAssetKey: assetKey,
      imageClipSnapshot: pinnedGroup.imageClipSnapshot,
    }),
  };
}

export function buildSwitchShotGroupToImagesMutation({
  currentData,
  shotId,
  rowId,
}: {
  currentData: TimelineData | null;
  shotId: string;
  rowId: string;
}) {
  if (!currentData) {
    return null;
  }

  const existingPinnedGroups = currentData.config.pinnedShotGroups ?? [];
  const foundGroup = findGroupForTrack(existingPinnedGroups, shotId, rowId, currentData.rows);
  const pinnedGroup = foundGroup?.mode === 'video' ? foundGroup : undefined;
  const resolvedTrackId = pinnedGroup ? resolveGroupTrackId(pinnedGroup, currentData.rows) : rowId;
  const targetRow = currentData.rows.find((row) => row.id === resolvedTrackId);
  const videoClipId = pinnedGroup?.clipIds[0];
  const videoActionIndex = targetRow?.actions.findIndex((action) => action.id === videoClipId) ?? -1;
  const videoAction = videoActionIndex >= 0 ? targetRow?.actions[videoActionIndex] : undefined;
  if (!pinnedGroup || !targetRow || !videoClipId || !videoAction || !pinnedGroup.imageClipSnapshot?.length) {
    return null;
  }

  const restoredMetaUpdates: Record<string, ClipMeta> = {};
  let cursor = videoAction.start;
  const restoredActions = pinnedGroup.imageClipSnapshot.map((snapshot) => {
    const clipMeta: ClipMeta = {
      ...snapshot.meta,
      asset: snapshot.assetKey,
      track: resolvedTrackId,
    };
    restoredMetaUpdates[snapshot.clipId] = clipMeta;
    const duration = getClipDuration(clipMeta, videoAction);
    const start = typeof snapshot.start === 'number' ? snapshot.start : cursor;
    const end = typeof snapshot.end === 'number' ? snapshot.end : start + duration;
    cursor = end;

    return {
      id: snapshot.clipId,
      start,
      end,
      effectId: `effect-${snapshot.clipId}`,
    };
  });
  const orderedRestoredActions = [...restoredActions].sort((left, right) => {
    if (left.start !== right.start) {
      return left.start - right.start;
    }
    return left.id.localeCompare(right.id);
  });
  const restoredClipIds = orderedRestoredActions.map((action) => action.id);
  const nextRows = currentData.rows.map((row) => {
    if (row.id !== resolvedTrackId) {
      return row;
    }

    const remainingActions = row.actions.filter((action) => action.id !== videoClipId);
    return {
      ...row,
      actions: [
        ...remainingActions.slice(0, videoActionIndex),
        ...orderedRestoredActions,
        ...remainingActions.slice(videoActionIndex),
      ],
    };
  });
  const nextClipOrder = updateClipOrder(currentData.clipOrder, resolvedTrackId, (ids) => {
    const filtered = ids.filter((id) => id !== videoClipId);
    const insertionIndex = ids.indexOf(videoClipId);
    return insertionIndex < 0
      ? [...filtered, ...restoredClipIds]
      : [...filtered.slice(0, insertionIndex), ...restoredClipIds, ...filtered.slice(insertionIndex)];
  });

  const nextPinnedShotGroups = buildPinnedShotGroupsOverride(currentData, {
    shotId,
    trackId: resolvedTrackId,
    clipIds: restoredClipIds,
    mode: 'images',
    imageClipSnapshot: pinnedGroup.imageClipSnapshot,
  });
  const contiguousRows = ensureGroupContiguity(nextRows, nextPinnedShotGroups);

  return {
    type: 'rows' as const,
    rows: contiguousRows,
    metaUpdates: restoredMetaUpdates,
    metaDeletes: [videoClipId],
    clipOrderOverride: nextClipOrder,
    pinnedShotGroupsOverride: nextPinnedShotGroups,
  };
}
