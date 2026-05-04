import { createContext, useContext, useMemo, type PropsWithChildren } from 'react';
import {
  DataProviderWrapper,
  useVideoEditorRuntime,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext';
import type { Shot } from '@/domains/generation/types';
import type { VideoEditorCorePorts, VideoEditorFinalVideo } from '@/tools/video-editor/core/core-ports';

const VideoEditorCorePortsContext = createContext<VideoEditorCorePorts | null>(null);
const EMPTY_SHOTS: Shot[] = [];
const EMPTY_FINAL_VIDEO_MAP = new Map<string, VideoEditorFinalVideo>();

export interface VideoEditorCoreRuntimeValue extends VideoEditorRuntimeContextValue {
  ports: VideoEditorCorePorts;
}

interface CoreRuntimeProviderProps extends PropsWithChildren {
  ports: VideoEditorCorePorts;
  runtime: VideoEditorRuntimeContextValue;
}

export function CoreRuntimeProvider({
  ports,
  runtime,
  children,
}: CoreRuntimeProviderProps) {
  return (
    <DataProviderWrapper value={runtime}>
      <VideoEditorCorePortsContext.Provider value={ports}>
        {children}
      </VideoEditorCorePortsContext.Provider>
    </DataProviderWrapper>
  );
}

export function useVideoEditorCorePorts(): VideoEditorCorePorts {
  const runtime = useVideoEditorRuntime();
  const ports = useContext(VideoEditorCorePortsContext);

  return useMemo(() => (
    ports ?? {
      dataProvider: runtime.provider,
      selectedProjectId: null,
      shots: EMPTY_SHOTS,
      finalVideoMap: EMPTY_FINAL_VIDEO_MAP,
    }
  ), [ports, runtime.provider]);
}

export function useVideoEditorCoreRuntime(): VideoEditorCoreRuntimeValue {
  const runtime = useVideoEditorRuntime();
  const ports = useVideoEditorCorePorts();

  return useMemo(() => ({
    ...runtime,
    provider: ports.dataProvider,
    ports,
  }), [ports, runtime]);
}
