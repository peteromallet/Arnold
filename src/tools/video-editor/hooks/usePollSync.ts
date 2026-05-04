import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MutableRefObject } from 'react';
import { isInteractionActive, onInteractionEnd, type InteractionStateRef } from '@/tools/video-editor/lib/interaction-state';
import { shouldAcceptPolledData } from '@/tools/video-editor/lib/timeline-save-utils';
import { buildTimelineData, preserveUploadingClips, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import type { CommitDataOptions } from '@/tools/video-editor/hooks/useTimelineCommit';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore';

const TIMELINE_SYNC_LOG_TAG = '[TimelineSync]';

type PollCheckPhase = 'preflight' | 'timeout';
type ConfigVersionUpdateSource = 'poll';

export interface UsePollSyncQueries {
  timelineQuery: {
    data: TimelineData | undefined;
    isLoading: boolean;
  };
  assetRegistryQuery: {
    data: Awaited<ReturnType<DataProvider['loadAssetRegistry']>> | undefined;
  };
}

interface TimelinePollGate {
  editSeq: number;
  savedSeq: number;
  pendingOps: number;
  isSaving: boolean;
  interactionActive?: boolean;
}

export interface PollRejectionInput extends TimelinePollGate {
  polledConfigVersion: number;
  currentConfigVersion: number;
  polledStableSignature: string;
  lastSavedStableSignature: string;
}

interface UsePollSyncOptions {
  store?: TimelineStoreApi;
  queries: UsePollSyncQueries;
  provider: DataProvider;
  resolveAssetUrl?: (file: string) => Promise<string>;
  commitData: (nextData: TimelineData, options?: CommitDataOptions) => void;
  dataRef: MutableRefObject<TimelineData | null>;
  selectedClipIdRef: MutableRefObject<string | null>;
  selectedTrackIdRef: MutableRefObject<string | null>;
  editSeqRef: MutableRefObject<number>;
  pendingOpsRef: MutableRefObject<number>;
  savedSeqRef: MutableRefObject<number>;
  configVersionRef: MutableRefObject<number>;
  lastSavedSignatureRef: MutableRefObject<string>;
  isSavingRef: MutableRefObject<boolean>;
  interactionStateRef: InteractionStateRef;
}

export function isTimelinePollIdle({ editSeq, savedSeq, pendingOps, isSaving, interactionActive }: TimelinePollGate): boolean {
  if (interactionActive) {
    return false;
  }
  return savedSeq >= editSeq && !isSaving && pendingOps === 0;
}

export function getTimelinePollRejectionReason({
  editSeq,
  savedSeq,
  pendingOps,
  isSaving,
  interactionActive,
  polledConfigVersion,
  currentConfigVersion,
  polledStableSignature,
  lastSavedStableSignature,
}: PollRejectionInput): string | null {
  if (!isTimelinePollIdle({ editSeq, savedSeq, pendingOps, isSaving, interactionActive })) {
    if (interactionActive) {
      return 'interaction active';
    }

    if (savedSeq < editSeq) {
      return 'unsaved edits';
    }

    if (pendingOps > 0) {
      return 'pending ops';
    }

    if (isSaving) {
      return 'saving';
    }

    return 'busy';
  }

  if (polledConfigVersion < currentConfigVersion) {
    return 'stale version';
  }

  if (
    !shouldAcceptPolledData(
      editSeq,
      savedSeq,
      pendingOps,
      polledStableSignature,
      lastSavedStableSignature,
    )
  ) {
    return polledConfigVersion === currentConfigVersion ? 'own echo' : 'signature match';
  }

  return null;
}

export function usePollSync({
  store,
  queries,
  provider,
  resolveAssetUrl,
  commitData,
  dataRef,
  selectedClipIdRef,
  selectedTrackIdRef,
  editSeqRef,
  pendingOpsRef,
  savedSeqRef,
  configVersionRef,
  lastSavedSignatureRef,
  isSavingRef,
  interactionStateRef,
}: UsePollSyncOptions): void {
  const lastRegistryDataRef = useRef<Awaited<ReturnType<DataProvider['loadAssetRegistry']>> | null>(null);
  const commitDataRef = useRef(commitData);
  const latestObservedRemoteConfigVersionRef = useRef<number | null>(null);
  // Newest polled timeline data observed while a drag/resize was in flight.
  // Replayed via the normal commit path on gesture end.
  const deferredPolledDataRef = useRef<TimelineData | null>(null);
  // Bumped on gesture end to re-trigger the poll-acceptance effect against
  // whatever the latest polled payload is.
  const [interactionEndTick, setInteractionEndTick] = useState(0);
  const getDataRef = useCallback(() => {
    const storeDataRef = store?.getState().data.dataRef;
    return storeDataRef && storeDataRef.current !== null ? storeDataRef : dataRef;
  }, [dataRef, store]);
  const getPendingOpsRef = useCallback(() => {
    const storePendingOpsRef = store?.getState().data.pendingOpsRef;
    return storePendingOpsRef ? storePendingOpsRef : pendingOpsRef;
  }, [pendingOpsRef, store]);
  const getInteractionStateRef = useCallback(() => {
    const storeInteractionStateRef = store?.getState().data.interactionStateRef;
    return storeInteractionStateRef ? storeInteractionStateRef : interactionStateRef;
  }, [interactionStateRef, store]);

  useLayoutEffect(() => {
    commitDataRef.current = commitData;
  }, [commitData]);

  useEffect(() => {
    const polledVersion = queries.timelineQuery.data?.configVersion;
    if (queries.timelineQuery.data && typeof polledVersion === 'number') {
      latestObservedRemoteConfigVersionRef.current = polledVersion;
    }
  }, [queries.timelineQuery.data]);

  const logTimelineSync = useCallback((message: string, details?: Record<string, unknown>) => {
    if (!import.meta.env.DEV) {
      return;
    }

    console.log(TIMELINE_SYNC_LOG_TAG, message, details);
  }, []);

  const logConfigVersionUpdate = useCallback((source: ConfigVersionUpdateSource, nextVersion: number) => {
    if (!import.meta.env.DEV) {
      return;
    }

    if (configVersionRef.current === nextVersion) {
      return;
    }

    console.log(TIMELINE_SYNC_LOG_TAG, 'configVersionRef updated', {
      source,
      from: configVersionRef.current,
      to: nextVersion,
    });
  }, [configVersionRef]);

  const getPollRejectionReason = useCallback((polledData: TimelineData): string | null => {
    return getTimelinePollRejectionReason({
      editSeq: editSeqRef.current,
      savedSeq: savedSeqRef.current,
      pendingOps: getPendingOpsRef().current,
      isSaving: isSavingRef.current,
      interactionActive: isInteractionActive(getInteractionStateRef()),
      polledConfigVersion: polledData.configVersion,
      currentConfigVersion: configVersionRef.current,
      polledStableSignature: polledData.stableSignature,
      lastSavedStableSignature: lastSavedSignatureRef.current,
    });
  }, [
    configVersionRef,
    editSeqRef,
    isSavingRef,
    lastSavedSignatureRef,
    getInteractionStateRef,
    getPendingOpsRef,
    savedSeqRef,
  ]);

  const logPollRejection = useCallback((phase: PollCheckPhase, polledData: TimelineData, reason: string) => {
    logTimelineSync(`poll rejected (${phase}: ${reason})`, {
      polledConfigVersion: polledData.configVersion,
      currentConfigVersion: configVersionRef.current,
      latestObservedRemoteConfigVersion: latestObservedRemoteConfigVersionRef.current,
      editSeq: editSeqRef.current,
      savedSeq: savedSeqRef.current,
      pendingOps: getPendingOpsRef().current,
      isSaving: isSavingRef.current,
    });
  }, [
    configVersionRef,
    editSeqRef,
    getPendingOpsRef,
    isSavingRef,
    logTimelineSync,
    savedSeqRef,
  ]);

  // Wake the poll-acceptance effect once a gesture ends so the most recently
  // deferred polled payload (if any) is re-evaluated against the freshly idle gate.
  useEffect(() => {
    return onInteractionEnd(getInteractionStateRef(), () => {
      setInteractionEndTick((tick) => tick + 1);
    });
  }, [getInteractionStateRef]);

  useEffect(() => {
    const polledData = deferredPolledDataRef.current ?? queries.timelineQuery.data;
    if (!polledData) {
      return;
    }

    const preflightRejectionReason = getPollRejectionReason(polledData);
    if (preflightRejectionReason) {
      if (preflightRejectionReason === 'interaction active') {
        // Defer the conflict reload until the gesture ends; keep the newest payload.
        deferredPolledDataRef.current = polledData;
      }
      logPollRejection('preflight', polledData, preflightRejectionReason);
      return;
    }
    // We accepted this payload — clear any stale deferred reference.
    deferredPolledDataRef.current = null;

    const syncHandle = window.setTimeout(() => {
      const timeoutRejectionReason = getPollRejectionReason(polledData);
      if (timeoutRejectionReason) {
        logPollRejection('timeout', polledData, timeoutRejectionReason);
        return;
      }

      if (configVersionRef.current !== polledData.configVersion) {
        logTimelineSync('poll accepted', {
          fromConfigVersion: configVersionRef.current,
          toConfigVersion: polledData.configVersion,
          latestObservedRemoteConfigVersion: latestObservedRemoteConfigVersionRef.current,
        });
      }
      latestObservedRemoteConfigVersionRef.current = polledData.configVersion;
      logConfigVersionUpdate('poll', polledData.configVersion);
      configVersionRef.current = polledData.configVersion;
      commitDataRef.current(
        getDataRef().current ? preserveUploadingClips(getDataRef().current, polledData) : polledData,
        { save: false, skipHistory: true, updateLastSavedSignature: true },
      );
    }, 0);

    return () => window.clearTimeout(syncHandle);
  }, [
    configVersionRef,
    dataRef,
    getPollRejectionReason,
    interactionEndTick,
    logConfigVersionUpdate,
    logPollRejection,
    logTimelineSync,
    getDataRef,
    queries.timelineQuery.data,
  ]);

  useEffect(() => {
    const current = getDataRef().current;
    const registry = queries.assetRegistryQuery.data;

    if (
      !current
      || !registry
      || !isTimelinePollIdle({
        editSeq: editSeqRef.current,
        savedSeq: savedSeqRef.current,
        pendingOps: getPendingOpsRef().current,
        isSaving: isSavingRef.current,
        interactionActive: isInteractionActive(getInteractionStateRef()),
      })
      || registry === lastRegistryDataRef.current
    ) {
      return;
    }

    lastRegistryDataRef.current = registry;

    void buildTimelineData(
      current.config,
      registry,
      resolveAssetUrl ?? ((file) => provider.resolveAssetUrl(file)),
      current.configVersion,
    ).then((nextData) => {
      if (
        nextData.stableSignature === current.stableSignature
        && Object.keys(nextData.assetMap).length === Object.keys(current.assetMap).length
      ) {
        return;
      }

      const syncHandle = window.setTimeout(() => {
        if (!isTimelinePollIdle({
          editSeq: editSeqRef.current,
          savedSeq: savedSeqRef.current,
          pendingOps: getPendingOpsRef().current,
          isSaving: isSavingRef.current,
          interactionActive: isInteractionActive(getInteractionStateRef()),
        })) {
          return;
        }

        commitDataRef.current(nextData, {
          save: false,
          skipHistory: true,
          updateLastSavedSignature: true,
          selectedClipId: selectedClipIdRef.current,
          selectedTrackId: selectedTrackIdRef.current,
        });
      }, 0);

      return () => window.clearTimeout(syncHandle);
    });
  }, [
    editSeqRef,
    isSavingRef,
    provider,
    resolveAssetUrl,
    queries.assetRegistryQuery.data,
    savedSeqRef,
    selectedClipIdRef,
    selectedTrackIdRef,
    getDataRef,
    getInteractionStateRef,
    getPendingOpsRef,
  ]);
}
