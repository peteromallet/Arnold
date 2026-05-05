import { useMemo } from 'react';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { useTimelineEditorData } from '@/tools/video-editor/hooks/timelineStore.ts';
import { getClipTimelineDuration } from '@/tools/video-editor/lib/config-utils.ts';
import type { SelectedMediaClip } from '@/tools/video-editor/hooks/useSelectedMediaClips.ts';

export function useTimelineClipsForAttachments(): SelectedMediaClip[] {
  const { data, resolvedConfig } = useTimelineEditorData();
  const { shots } = useVideoEditorRuntime().shots;

  return useMemo(() => {
    if (!resolvedConfig) {
      return [];
    }

    const pinnedGroups = data?.config.pinnedShotGroups ?? [];
    const shotNameById = new Map((shots ?? []).map((shot) => [shot.id, shot.name]));
    const shotByClipId = new Map(
      pinnedGroups.flatMap((group) => group.clipIds.map((clipId) => [clipId, group] as const)),
    );

    return resolvedConfig.clips.reduce<SelectedMediaClip[]>((acc, clip) => {
      const assetKey = clip.asset;
      const assetEntry = assetKey ? resolvedConfig.registry[assetKey] : undefined;
      const shotGroup = shotByClipId.get(clip.id);
      const shotName = shotGroup ? shotNameById.get(shotGroup.shotId) : undefined;
      const shotFields = shotGroup
        ? {
          shotId: shotGroup.shotId,
          ...(shotName ? { shotName } : {}),
          shotSelectionClipCount: shotGroup.clipIds.length,
        }
        : {};

      if (!assetKey || !assetEntry?.src || !assetEntry.type) {
        return acc;
      }

      if (assetEntry.type.startsWith('image/')) {
        acc.push({
          clipId: clip.id,
          assetKey,
          url: assetEntry.src,
          mediaType: 'image',
          isTimelineBacked: true,
          generationId: assetEntry.generationId,
          variantId: assetEntry.variantId,
          trackId: clip.track,
          at: clip.at,
          duration: getClipTimelineDuration(clip),
          ...shotFields,
        });
      } else if (assetEntry.type.startsWith('video/')) {
        acc.push({
          clipId: clip.id,
          assetKey,
          url: assetEntry.src,
          mediaType: 'video',
          isTimelineBacked: true,
          generationId: assetEntry.generationId,
          variantId: assetEntry.variantId,
          trackId: clip.track,
          at: clip.at,
          duration: getClipTimelineDuration(clip),
          ...shotFields,
        });
      }

      return acc;
    }, []);
  }, [data?.config.pinnedShotGroups, resolvedConfig, shots]);
}
