import { useMemo } from 'react';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useTimelineEditorData } from '@/tools/video-editor/hooks/timelineStore';
import { getClipTimelineDuration } from '@/tools/video-editor/lib/config-utils';

export type SelectedMediaClip = {
  clipId: string;
  assetKey: string;
  url: string;
  mediaType: 'image' | 'video';
  isTimelineBacked: boolean;
  generationId?: string;
  variantId?: string;
  shotId?: string;
  shotName?: string;
  shotSelectionClipCount?: number;
  trackId?: string;
  at?: number;
  duration?: number;
  isPlaceholder?: boolean;
};

type SummaryMediaClip = Pick<SelectedMediaClip, 'mediaType' | 'shotId' | 'shotSelectionClipCount'>;

function formatMediaCount(count: number, mediaType: 'image' | 'video', more = false) {
  const noun = `${mediaType}${count === 1 ? '' : 's'}`;
  if (more) {
    return `${count} more ${noun}`;
  }

  return `${count} ${noun}`;
}

function buildMediaBreakdown(imageCount: number, videoCount: number, more = false) {
  return [
    imageCount > 0 ? formatMediaCount(imageCount, 'image', more) : null,
    videoCount > 0 ? formatMediaCount(videoCount, 'video', more) : null,
  ].filter((part): part is string => part !== null);
}

function buildCountSummaryBody(imageCount: number, videoCount: number) {
  return buildMediaBreakdown(imageCount, videoCount).join(', ');
}

function buildSummaryBody(clips: SummaryMediaClip[]) {
  if (clips.length === 0) {
    return '';
  }

  const shotGroups = new Map<string, {
    clipCount: number;
    expectedClipCount: number;
    imageCount: number;
    videoCount: number;
    firstIndex: number;
  }>();

  clips.forEach((clip, index) => {
    if (!clip.shotId || typeof clip.shotSelectionClipCount !== 'number' || clip.shotSelectionClipCount < 1) {
      return;
    }

    const existing = shotGroups.get(clip.shotId);
    if (existing) {
      existing.clipCount += 1;
      if (clip.mediaType === 'image') {
        existing.imageCount += 1;
      } else {
        existing.videoCount += 1;
      }
      return;
    }

    shotGroups.set(clip.shotId, {
      clipCount: 1,
      expectedClipCount: clip.shotSelectionClipCount,
      imageCount: clip.mediaType === 'image' ? 1 : 0,
      videoCount: clip.mediaType === 'video' ? 1 : 0,
      firstIndex: index,
    });
  });

  const fullShotGroups = Array.from(shotGroups.entries())
    .filter(([, group]) => group.clipCount === group.expectedClipCount)
    .sort((a, b) => a[1].firstIndex - b[1].firstIndex);
  const fullShotIds = new Set(fullShotGroups.map(([shotId]) => shotId));

  const shotCount = fullShotGroups.length;
  const shotImageCount = fullShotGroups.reduce((sum, [, group]) => sum + group.imageCount, 0);
  const shotVideoCount = fullShotGroups.reduce((sum, [, group]) => sum + group.videoCount, 0);
  const shotPart = shotCount > 0
    ? `${shotCount} shot${shotCount === 1 ? '' : 's'} (${buildMediaBreakdown(shotImageCount, shotVideoCount).join(', ')})`
    : '';

  const remainingClips = clips.filter((clip) => !(clip.shotId && fullShotIds.has(clip.shotId)));
  const remainingImageCount = remainingClips.filter((clip) => clip.mediaType === 'image').length;
  const remainingVideoCount = remainingClips.length - remainingImageCount;
  const remainingParts = buildMediaBreakdown(remainingImageCount, remainingVideoCount, shotCount > 0);

  if (shotPart && remainingParts.length > 0) {
    return `${shotPart} and ${remainingParts.join(', ')}`;
  }

  if (shotPart) {
    return shotPart;
  }

  return remainingParts.join(', ');
}

export function buildSummary(clips: SummaryMediaClip[]): string;
export function buildSummary(imageCount: number, videoCount: number): string;
export function buildSummary(
  clipsOrImageCount: SummaryMediaClip[] | number,
  videoCount = 0,
) {
  const body = Array.isArray(clipsOrImageCount)
    ? buildSummaryBody(clipsOrImageCount)
    : buildCountSummaryBody(clipsOrImageCount, videoCount);
  return body ? `attaching ${body}` : '';
}

export function buildAttachedSummary(clips: SummaryMediaClip[]) {
  const body = buildSummaryBody(clips);
  return body ? `${body} attached` : null;
}

export function useSelectedMediaClips(): { clips: SelectedMediaClip[]; summary: string } {
  const { data, selectedClipIds, resolvedConfig } = useTimelineEditorData();
  const { shots } = useShots();

  return useMemo(() => {
    if (!resolvedConfig || selectedClipIds.size === 0) {
      return { clips: [], summary: '' };
    }

    const pinnedGroups = data?.config.pinnedShotGroups ?? [];
    const shotNameById = new Map((shots ?? []).map((shot) => [shot.id, shot.name]));
    const shotByClipId = new Map(
      pinnedGroups.flatMap((group) => group.clipIds.map((clipId) => [clipId, group] as const)),
    );
    const fullySelectedShotIds = new Set(
      pinnedGroups
        .filter((group) => group.clipIds.every((clipId) => selectedClipIds.has(clipId)))
        .map((group) => group.shotId),
    );

    const clips = [...selectedClipIds].reduce<SelectedMediaClip[]>((acc, clipId) => {
      const clip = resolvedConfig.clips.find((item) => item.id === clipId);
      const assetKey = clip?.asset;
      const assetEntry = assetKey ? resolvedConfig.registry[assetKey] : undefined;
      const shotGroup = shotByClipId.get(clipId);
      const shotName = shotGroup ? shotNameById.get(shotGroup.shotId) : undefined;
      const shotFields = shotGroup
        ? {
          shotId: shotGroup.shotId,
          ...(shotName ? { shotName } : {}),
          ...(fullySelectedShotIds.has(shotGroup.shotId) ? { shotSelectionClipCount: shotGroup.clipIds.length } : {}),
        }
        : {};

      if (!assetKey || !assetEntry?.src || !assetEntry.type) {
        return acc;
      }

      if (assetEntry.type.startsWith('image/')) {
        acc.push({
          clipId,
          assetKey,
          url: assetEntry.src,
          mediaType: 'image' as const,
          isTimelineBacked: true,
          generationId: assetEntry.generationId,
          variantId: assetEntry.variantId,
          trackId: clip.track,
          at: clip.at,
          duration: getClipTimelineDuration(clip),
          ...shotFields,
        });
        return acc;
      }

      if (assetEntry.type.startsWith('video/')) {
        acc.push({
          clipId,
          assetKey,
          url: assetEntry.src,
          mediaType: 'video' as const,
          isTimelineBacked: true,
          generationId: assetEntry.generationId,
          variantId: assetEntry.variantId,
          trackId: clip.track,
          at: clip.at,
          duration: getClipTimelineDuration(clip),
          ...shotFields,
        });
        return acc;
      }

      return acc;
    }, []);

    return {
      clips,
      summary: buildSummary(clips),
    };
  }, [data?.config.pinnedShotGroups, resolvedConfig, selectedClipIds, shots]);
}
