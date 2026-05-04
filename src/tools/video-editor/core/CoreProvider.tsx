import { useMemo, type ReactNode } from 'react';
import { TimelineStoreProvider, type TimelineMutableAdapters } from '@/tools/video-editor/hooks/timelineStore';
import { useTimelineState } from '@/tools/video-editor/hooks/useTimelineState';
import type { UseTimelineStateResult } from '@/tools/video-editor/hooks/useTimelineState.types';
import type { VideoEditorCorePorts } from '@/tools/video-editor/core/core-ports';
import { CoreRuntimeProvider } from '@/tools/video-editor/core/core-runtime';

export interface CoreProviderRenderState extends UseTimelineStateResult {
  mutableAdapters: TimelineMutableAdapters;
}

type CoreProviderChildren =
  | ReactNode
  | ((state: CoreProviderRenderState) => ReactNode);

interface CoreProviderProps {
  ports: VideoEditorCorePorts;
  timelineId: string;
  timelineName?: string | null;
  userId: string;
  children: CoreProviderChildren;
}

function CoreProviderBody({ children }: { children: CoreProviderChildren }) {
  const state = useTimelineState();

  const mutableAdapters = useMemo<TimelineMutableAdapters>(() => ({
    dataRef: state.editorData.dataRef,
    pendingOpsRef: state.editorData.pendingOpsRef,
    interactionStateRef: state.editorData.interactionStateRef,
    selectedClipIdsRef: state.editorData.selectedClipIdsRef,
    additiveSelectionRef: state.editorData.additiveSelectionRef,
    timelineRef: state.editorData.timelineRef,
    timelineWrapperRef: state.editorData.timelineWrapperRef,
    previewRef: state.playback.previewRef,
    playerContainerRef: state.playback.playerContainerRef,
    ops: state.editorOps,
  }), [state.editorData, state.editorOps, state.playback]);

  const renderState = useMemo<CoreProviderRenderState>(() => ({
    ...state,
    mutableAdapters,
  }), [mutableAdapters, state]);

  return (
    <TimelineStoreProvider store={state.store}>
      {typeof children === 'function'
        ? children(renderState)
        : children}
    </TimelineStoreProvider>
  );
}

export function CoreProvider({
  ports,
  timelineId,
  timelineName,
  userId,
  children,
}: CoreProviderProps) {
  const runtime = useMemo(() => ({
    provider: ports.dataProvider,
    timelineId,
    timelineName,
    userId,
  }), [ports.dataProvider, timelineId, timelineName, userId]);

  return (
    <CoreRuntimeProvider runtime={runtime} ports={ports}>
      <CoreProviderBody>{children}</CoreProviderBody>
    </CoreRuntimeProvider>
  );
}
