import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import type { ShotFinalVideo } from '@/tools/travel-between-images/hooks/video/useShotFinalVideos';

export type { ShotFinalVideo };

export function useFinalVideoAvailable() {
  const { shots } = useVideoEditorRuntime();

  return {
    finalVideoMap: shots.finalVideoMap,
    dismissFinalVideo: shots.dismissFinalVideo,
  };
}
