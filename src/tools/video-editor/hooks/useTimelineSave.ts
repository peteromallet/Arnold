import {
  useEffect,
  useRef,
} from 'react';
import type { InteractionStateRef } from '@/tools/video-editor/lib/interaction-state';
import { useTimelineCommit } from '@/tools/video-editor/hooks/useTimelineCommit';
import { TimelineEventBus } from '@/tools/video-editor/hooks/useTimelineEventBus';
import { useTimelinePersistence } from '@/tools/video-editor/hooks/useTimelinePersistence';
import { usePollSync, type UsePollSyncQueries } from '@/tools/video-editor/hooks/usePollSync';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
export { shouldAcceptPolledData } from '@/tools/video-editor/lib/timeline-save-utils';
export type { SaveStatus } from '@/tools/video-editor/hooks/useTimelinePersistence';

type UseTimelineSaveQueries = UsePollSyncQueries;

export type { InteractionStateRef } from '@/tools/video-editor/lib/interaction-state';

export function useTimelineSave(
  queries: UseTimelineSaveQueries,
  provider: DataProvider,
  interactionStateRef: InteractionStateRef,
  store: TimelineStoreApi,
) {
  const { timelineId, assetResolver } = useVideoEditorRuntime();
  const resolveAssetUrl = (file: string) => {
    if (assetResolver) {
      return Promise.resolve(assetResolver.resolveAssetUrl(file));
    }

    return provider.resolveAssetUrl(file);
  };
  const lastSavedSignatureRef = useRef('');
  const savedSeqRef = useRef(0);
  const configVersionRef = useRef(1);
  const eventBusRef = useRef(new TimelineEventBus());
  const commit = useTimelineCommit({
    eventBus: eventBusRef.current,
    lastSavedSignatureRef,
  });
  const persistence = useTimelinePersistence({
    store,
    provider,
    timelineId,
    resolveAssetUrl,
    eventBus: eventBusRef.current,
    dataRef: commit.dataRef,
    commitData: commit.commitData,
    selectedClipIdRef: commit.selectedClipIdRef,
    selectedTrackIdRef: commit.selectedTrackIdRef,
    editSeqRef: commit.editSeqRef,
    savedSeqRef,
    configVersionRef,
    lastSavedSignatureRef,
    interactionStateRef,
  });

  useEffect(() => {
    return eventBusRef.current.on('scheduleSave', persistence.scheduleSave);
  }, [persistence.scheduleSave]);

  usePollSync({
    store,
    queries,
    provider,
    resolveAssetUrl,
    commitData: commit.commitData,
    dataRef: commit.dataRef,
    selectedClipIdRef: commit.selectedClipIdRef,
    selectedTrackIdRef: commit.selectedTrackIdRef,
    editSeqRef: commit.editSeqRef,
    pendingOpsRef: commit.pendingOpsRef,
    savedSeqRef,
    configVersionRef,
    lastSavedSignatureRef,
    isSavingRef: persistence.isSavingRef,
    interactionStateRef,
  });

  return {
    data: commit.data,
    dataRef: commit.dataRef,
    isConflictExhausted: persistence.isConflictExhausted,
    selectedClipId: commit.selectedClipId,
    selectedTrackId: commit.selectedTrackId,
    saveStatus: persistence.saveStatus,
    setSelectedTrackId: commit.setSelectedTrackId,
    applyEdit: commit.applyEdit,
    patchRegistry: commit.patchRegistry,
    unpatchRegistry: commit.unpatchRegistry,
    commitData: commit.commitData,
    eventBus: eventBusRef.current,
    reloadFromServer: persistence.reloadFromServer,
    retrySaveAfterConflict: persistence.retrySaveAfterConflict,
    editSeqRef: commit.editSeqRef,
    pendingOpsRef: commit.pendingOpsRef,
    savedSeqRef,
    selectedClipIdRef: commit.selectedClipIdRef,
    selectedTrackIdRef: commit.selectedTrackIdRef,
    isLoading: queries.timelineQuery.isLoading && !commit.data,
  };
}
