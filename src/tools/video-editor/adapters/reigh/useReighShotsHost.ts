import { useCallback, useMemo, useState } from 'react';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useShotFinalVideos, type ShotFinalVideo } from '@/tools/travel-between-images/hooks/video/useShotFinalVideos';
import type { VideoEditorShotsHost } from '@/tools/video-editor/runtime/ports';

const MAX_DISMISSED_FINAL_VIDEOS = 256;
const dismissedFinalVideoIds = new Set<string>();

export function useReighShotsHost(projectId: string | null): VideoEditorShotsHost {
  const {
    shots,
    isLoading,
    error,
    refetchShots,
    allImagesCount,
    noShotImagesCount,
  } = useShots();
  const { finalVideoMap } = useShotFinalVideos(projectId);
  const [, forceRender] = useState(0);

  const dismissFinalVideo = useCallback((finalVideoId: string) => {
    dismissedFinalVideoIds.add(finalVideoId);
    if (dismissedFinalVideoIds.size > MAX_DISMISSED_FINAL_VIDEOS) {
      const oldest = dismissedFinalVideoIds.values().next().value;
      if (oldest !== undefined) {
        dismissedFinalVideoIds.delete(oldest);
      }
    }
    forceRender((count) => count + 1);
  }, []);

  const visibleFinalVideoMap = useMemo(() => {
    const filtered = new Map<string, ShotFinalVideo>();

    for (const [shotId, finalVideo] of finalVideoMap.entries()) {
      if (!dismissedFinalVideoIds.has(finalVideo.id)) {
        filtered.set(shotId, finalVideo);
      }
    }

    return filtered;
  }, [finalVideoMap]);

  return useMemo(() => ({
    shots,
    isLoading,
    error,
    refetchShots,
    allImagesCount,
    noShotImagesCount,
    finalVideoMap: visibleFinalVideoMap,
    dismissFinalVideo,
  }), [
    allImagesCount,
    dismissFinalVideo,
    error,
    isLoading,
    noShotImagesCount,
    refetchShots,
    shots,
    visibleFinalVideoMap,
  ]);
}
