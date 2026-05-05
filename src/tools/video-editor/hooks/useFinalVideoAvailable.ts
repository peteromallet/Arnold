import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import type { ShotFinalVideo } from '@/tools/travel-between-images/hooks/video/useShotFinalVideos.ts';

export type { ShotFinalVideo };

export function useFinalVideoAvailable() {
  const { shots } = useVideoEditorRuntime();

  return {
    finalVideoMap: shots.finalVideoMap,
    dismissFinalVideo: shots.dismissFinalVideo,
  };
}
