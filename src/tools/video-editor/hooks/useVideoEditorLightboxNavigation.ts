import { useCallback, useMemo } from 'react';
import type { Shot } from '@/domains/generation/types';
import type { LightboxNavigationProps } from '@/domains/media-lightbox/types';
import { getClipTypeOverlayBehavior, getRegisteredClipTypeDescriptor } from '@/tools/video-editor/clip-types';
import { getShotColor } from '@/tools/video-editor/hooks/useShotGroups';
import { isOpenableAssetType } from '@/tools/video-editor/lib/editor-utils';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';

interface NavigableItem {
  assetKey: string;
  clipId: string;
  shotGroupId: string | null;
}

interface NavigationModel {
  items: NavigableItem[];
  currentIndex: number;
}

export interface VideoEditorLightboxIndicator {
  shotGroupLabel: string | null;
  shotGroupColor: string | null;
  positionInGroup: { current: number; total: number } | null;
  positionInList: { current: number; total: number };
}

interface UseVideoEditorLightboxNavigationProps {
  lightboxAssetKey: string | null;
  lightboxClipId: string | null;
  data: TimelineData | null;
  shots: Shot[] | undefined;
  setLightboxAssetKey: (assetKey: string | null) => void;
  setLightboxClipId: (clipId: string | null) => void;
}

interface UseVideoEditorLightboxNavigationResult {
  navigation: LightboxNavigationProps | undefined;
  indicator: VideoEditorLightboxIndicator | null;
}

function buildNavigationModel(
  lightboxAssetKey: string | null,
  lightboxClipId: string | null,
  data: TimelineData | null,
): NavigationModel | null {
  if (!lightboxAssetKey || !data) {
    return null;
  }

  const rowIndexByTrackId = new Map(data.rows.map((row, rowIndex) => [row.id, rowIndex] as const));
  const trackKindById = new Map(data.tracks.map((track) => [track.id, track.kind] as const));
  const actionByClipId = new Map<string, { start: number; rowIndex: number }>();

  for (const [rowIndex, row] of data.rows.entries()) {
    for (const action of row.actions) {
      actionByClipId.set(action.id, { start: action.start, rowIndex });
    }
  }

  const pinnedShotGroups = data.config.pinnedShotGroups ?? [];
  const groupByClipId = new Map<string, NonNullable<TimelineData['config']['pinnedShotGroups']>[number]>();
  for (const group of pinnedShotGroups) {
    for (const clipId of group.clipIds) {
      if (!groupByClipId.has(clipId)) {
        groupByClipId.set(clipId, group);
      }
    }
  }

  const originClipId = (
    lightboxClipId && data.meta[lightboxClipId]
      ? lightboxClipId
      : Object.keys(data.meta).find((clipId) => data.meta[clipId]?.asset === lightboxAssetKey)
  ) ?? null;

  if (!originClipId) {
    return null;
  }

  const originMeta = data.meta[originClipId];
  if (!originMeta) {
    return null;
  }

  const originTrackId = originMeta.track;
  const originGroup = groupByClipId.get(originClipId) ?? null;

  const buildItem = (clipId: string): NavigableItem | null => {
    const meta = data.meta[clipId];
    const overlayBehavior = getClipTypeOverlayBehavior(
      getRegisteredClipTypeDescriptor(meta?.clipType),
    );
    if (!meta?.asset || !overlayBehavior.lightboxEnabled) {
      return null;
    }

    if (trackKindById.get(meta.track) !== 'visual') {
      return null;
    }

    if (!actionByClipId.has(clipId) || !rowIndexByTrackId.has(meta.track)) {
      return null;
    }

    const resolvedAsset = data.resolvedConfig.registry[meta.asset];
    const rawAsset = data.registry.assets[meta.asset];
    const src = resolvedAsset?.src ?? rawAsset?.file;
    const type = resolvedAsset?.type ?? rawAsset?.type;
    if (!isOpenableAssetType(type, src)) {
      return null;
    }

    return {
      assetKey: meta.asset,
      clipId,
      shotGroupId: groupByClipId.get(clipId)?.shotId ?? null,
    };
  };

  const compareClipIds = (leftClipId: string, rightClipId: string) => {
    const leftAction = actionByClipId.get(leftClipId);
    const rightAction = actionByClipId.get(rightClipId);
    return (leftAction?.start ?? 0) - (rightAction?.start ?? 0);
  };

  const tierOneClipIds = originGroup
    ? [...originGroup.clipIds].sort(compareClipIds)
    : [];

  const tierOneSet = new Set(tierOneClipIds);
  const originRow = data.rows[rowIndexByTrackId.get(originTrackId) ?? -1];
  const tierTwoClipIds = (originRow?.actions ?? [])
    .map((action) => action.id)
    .filter((clipId) => !tierOneSet.has(clipId))
    .sort(compareClipIds);

  const seenTierClipIds = new Set([...tierOneClipIds, ...tierTwoClipIds]);
  const tierThreeClipIds: string[] = [];
  for (const row of data.rows) {
    if (row.id === originTrackId || trackKindById.get(row.id) !== 'visual') {
      continue;
    }

    const orderedRowClipIds = [...row.actions]
      .sort((left, right) => left.start - right.start)
      .map((action) => action.id);

    for (const clipId of orderedRowClipIds) {
      if (seenTierClipIds.has(clipId)) {
        continue;
      }

      seenTierClipIds.add(clipId);
      tierThreeClipIds.push(clipId);
    }
  }

  const orderedItems: NavigableItem[] = [];
  const seenAssetKeys = new Set<string>();
  for (const clipId of [...tierOneClipIds, ...tierTwoClipIds, ...tierThreeClipIds]) {
    const item = buildItem(clipId);
    if (!item || seenAssetKeys.has(item.assetKey)) {
      continue;
    }

    seenAssetKeys.add(item.assetKey);
    orderedItems.push(item);
  }

  const currentIndex = orderedItems.findIndex((item) => item.assetKey === lightboxAssetKey);
  if (currentIndex === -1) {
    return null;
  }

  return {
    items: orderedItems,
    currentIndex,
  };
}

export function useVideoEditorLightboxNavigation({
  lightboxAssetKey,
  lightboxClipId,
  data,
  shots,
  setLightboxAssetKey,
  setLightboxClipId,
}: UseVideoEditorLightboxNavigationProps): UseVideoEditorLightboxNavigationResult {
  const navigationModel = useMemo(
    () => buildNavigationModel(lightboxAssetKey, lightboxClipId, data),
    [data, lightboxAssetKey, lightboxClipId],
  );

  const navigateByOffset = useCallback((offset: number) => {
    if (!navigationModel) {
      return;
    }

    const nextItem = navigationModel.items[navigationModel.currentIndex + offset];
    if (!nextItem) {
      return;
    }

    setLightboxAssetKey(nextItem.assetKey);
    setLightboxClipId(nextItem.clipId);
  }, [navigationModel, setLightboxAssetKey, setLightboxClipId]);

  const navigation = useMemo<LightboxNavigationProps | undefined>(() => {
    if (!navigationModel) {
      return undefined;
    }

    return {
      onNext: () => navigateByOffset(1),
      onPrevious: () => navigateByOffset(-1),
      showNavigation: true,
      hasNext: navigationModel.currentIndex < navigationModel.items.length - 1,
      hasPrevious: navigationModel.currentIndex > 0,
    };
  }, [navigateByOffset, navigationModel]);

  const indicator = useMemo<VideoEditorLightboxIndicator | null>(() => {
    if (!navigationModel) {
      return null;
    }

    const currentItem = navigationModel.items[navigationModel.currentIndex];
    if (!currentItem) {
      return null;
    }

    const currentShotGroupId = currentItem.shotGroupId;
    const itemsInGroup = currentShotGroupId
      ? navigationModel.items.filter((item) => item.shotGroupId === currentShotGroupId)
      : [];
    const indexInGroup = currentShotGroupId
      ? itemsInGroup.findIndex((item) => item.assetKey === currentItem.assetKey)
      : -1;

    return {
      shotGroupLabel: currentShotGroupId
        ? shots?.find((shot) => shot.id === currentShotGroupId)?.name ?? null
        : null,
      shotGroupColor: currentShotGroupId ? getShotColor(currentShotGroupId) : null,
      positionInGroup: currentShotGroupId && indexInGroup !== -1
        ? { current: indexInGroup + 1, total: itemsInGroup.length }
        : null,
      positionInList: {
        current: navigationModel.currentIndex + 1,
        total: navigationModel.items.length,
      },
    };
  }, [navigationModel, shots]);

  return {
    navigation,
    indicator,
  };
}
