import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { useMutation } from '@tanstack/react-query';
import { isInteractionActive, onInteractionEnd, type InteractionStateRef } from '@/tools/video-editor/lib/interaction-state.ts';
import { TimelineEventBus } from '@/tools/video-editor/hooks/useTimelineEventBus.ts';
import type { TimelineStoreApi } from '@/tools/video-editor/hooks/timelineStore.ts';
import {
  isDataProviderPersistenceEnabled,
  isTimelineNotFoundError,
  isTimelineVersionConflictError,
  type DataProvider,
} from '@/tools/video-editor/data/DataProvider.ts';
import { buildTimelineData, buildTimelineDataWithResolver, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { AssetResolver } from '@/tools/video-editor/data/AssetResolver.ts';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { CommitDataOptions, ScheduleSaveFn } from '@/tools/video-editor/hooks/useTimelineCommit.ts';

export type SaveStatus = 'saved' | 'saving' | 'dirty' | 'error';

const MAX_CONFLICT_RETRIES = 3;
const TIMELINE_SYNC_LOG_TAG = '[TimelineSync]';

type ConfigVersionUpdateSource = 'save' | 'reload' | 'conflict-retry';

interface UseTimelinePersistenceOptions {
  store?: TimelineStoreApi;
  provider: DataProvider;
  timelineId: string;
  resolveAssetUrl?: (file: string) => Promise<string>;
  /**
   * Optional AssetResolver. When provided, reload paths route asset
   * lookups through `assetResolver.onResolve` (and surface missing
   * assets via `onMissing`) so the host's resolver lifecycle stays
   * authoritative on refresh.
   */
  assetResolver?: AssetResolver;
  eventBus: TimelineEventBus;
  dataRef: MutableRefObject<TimelineData | null>;
  commitData: (nextData: TimelineData, options?: CommitDataOptions) => void;
  selectedClipIdRef: MutableRefObject<string | null>;
  selectedTrackIdRef: MutableRefObject<string | null>;
  editSeqRef: MutableRefObject<number>;
  savedSeqRef: MutableRefObject<number>;
  configVersionRef: MutableRefObject<number>;
  lastSavedSignatureRef: MutableRefObject<string>;
  interactionStateRef: InteractionStateRef;
}

export interface UseTimelinePersistenceResult {
  scheduleSave: ScheduleSaveFn;
  saveStatus: SaveStatus;
  isConflictExhausted: boolean;
  reloadFromServer: () => Promise<void>;
  retrySaveAfterConflict: () => Promise<void>;
  isSavingRef: MutableRefObject<boolean>;
}

export function useTimelinePersistence({
  store,
  provider,
  timelineId,
  resolveAssetUrl,
  assetResolver,
  eventBus,
  dataRef,
  commitData,
  selectedClipIdRef,
  selectedTrackIdRef,
  editSeqRef,
  savedSeqRef,
  configVersionRef,
  lastSavedSignatureRef,
  interactionStateRef,
}: UseTimelinePersistenceOptions): UseTimelinePersistenceResult {
  const persistenceEnabled = isDataProviderPersistenceEnabled(provider);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const conflictRetryRef = useRef(0);
  const pendingSaveRef = useRef<{ data: TimelineData; seq: number } | null>(null);
  // Stash for scheduleSave() calls that arrive while a drag/resize is active.
  // Flushed on gesture end by the onInteractionEnd listener below.
  const deferredSaveRef = useRef<{ data: TimelineData; preserveStatus?: boolean } | null>(null);
  const isSavingRef = useRef(false);

  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved');
  const [isConflictExhausted, setIsConflictExhausted] = useState(false);
  const getDataRef = useCallback(() => {
    const storeDataRef = store?.getState().data.dataRef;
    return storeDataRef && storeDataRef.current !== null ? storeDataRef : dataRef;
  }, [dataRef, store]);
  const getInteractionStateRef = useCallback(() => {
    const storeInteractionStateRef = store?.getState().data.interactionStateRef;
    return storeInteractionStateRef ? storeInteractionStateRef : interactionStateRef;
  }, [interactionStateRef, store]);

  const logConfigVersionUpdate = useCallback((source: ConfigVersionUpdateSource, nextVersion: number) => {
    if (!import.meta.env.DEV) {
      return;
    }

    console.log(TIMELINE_SYNC_LOG_TAG, 'configVersionRef updated', {
      source,
      from: configVersionRef.current,
      to: nextVersion,
    });
  }, [configVersionRef]);

  const handleConflictExhausted = useCallback((details: {
    expectedVersion: number;
    actualVersion?: number;
    retries: number;
    reason: 'load_failed' | 'max_retries' | 'missing_local_data';
  }) => {
    console.log('[TimelineSave] conflict retries exhausted', details);
    setIsConflictExhausted(true);
    setSaveStatus('error');
  }, []);

  const saveMutation = useMutation({
    mutationFn: ({
      config,
      expectedVersion,
      registry,
    }: {
      config: TimelineConfig;
      expectedVersion: number;
      registry?: AssetRegistry;
    }) => {
      return provider.saveTimeline(timelineId, config, expectedVersion, registry);
    },
    retry: false,
  });

  const loadConflictRetryVersion = useCallback(async (): Promise<number> => {
    const [loaded, registry] = await Promise.all([
      provider.loadTimeline(timelineId),
      provider.loadAssetRegistry(timelineId),
    ]);
    logConfigVersionUpdate('conflict-retry', loaded.configVersion);
    configVersionRef.current = loaded.configVersion;
    const latestDataRef = getDataRef();
    if (latestDataRef.current) {
      latestDataRef.current = { ...latestDataRef.current, registry };
    }
    return loaded.configVersion;
  }, [configVersionRef, getDataRef, logConfigVersionUpdate, provider, timelineId]);

  const doSave = useCallback(async (
    nextData: TimelineData,
    seq: number,
    options?: {
      bypassQueue?: boolean;
      completedSeqRef?: { current: number | null };
    },
  ) => {
    if (isSavingRef.current && !options?.bypassQueue) {
      pendingSaveRef.current = { data: nextData, seq };
      return;
    }

    const completedSeqRef = options?.completedSeqRef ?? { current: null };

    if (!options?.bypassQueue) {
      isSavingRef.current = true;
    }
    setSaveStatus('saving');

    try {
      const expectedVersion = configVersionRef.current;
      await saveMutation.mutateAsync(
        {
          config: nextData.config,
          expectedVersion,
          registry: nextData.registry,
        },
        {
          onSuccess: (nextVersion) => {
            logConfigVersionUpdate('save', nextVersion);
            configVersionRef.current = nextVersion;
            completedSeqRef.current = seq;

            if (conflictRetryRef.current > 0) {
              console.log('[TimelineSave] conflict retry succeeded', {
                attempts: conflictRetryRef.current,
                finalVersion: nextVersion,
              });
            }

            conflictRetryRef.current = 0;
            setIsConflictExhausted(false);

            const latestDataRef = getDataRef();
            if (latestDataRef.current?.signature === nextData.signature) {
              commitData({
                ...latestDataRef.current,
                configVersion: nextVersion,
              }, {
                save: false,
                skipHistory: true,
                selectedClipId: selectedClipIdRef.current,
                selectedTrackId: selectedTrackIdRef.current,
              });
            }

            if (seq > savedSeqRef.current) {
              savedSeqRef.current = seq;
              lastSavedSignatureRef.current = nextData.stableSignature;
            }

            setSaveStatus(seq >= editSeqRef.current ? 'saved' : 'dirty');
            eventBus.emit('saveSuccess');
          },
        },
      );
    } catch (error) {
      if (isTimelineNotFoundError(error)) {
        console.log('[TimelineSave] timeline not found, cannot save');
        handleConflictExhausted({
          expectedVersion: configVersionRef.current,
          retries: conflictRetryRef.current,
          reason: 'missing_local_data',
        });
        return;
      }

      if (isTimelineVersionConflictError(error)) {
      const expectedVersion = configVersionRef.current;
        let actualVersion: number | undefined;

        try {
          actualVersion = await loadConflictRetryVersion();
          console.log('[TimelineSave] conflict detected', {
            expectedVersion,
            actualVersion,
          });
        } catch {
          handleConflictExhausted({
            expectedVersion,
            retries: conflictRetryRef.current,
            reason: 'load_failed',
          });
          return;
        }

        const latestDataRef = getDataRef();
        if (!latestDataRef.current) {
          handleConflictExhausted({
            expectedVersion,
            actualVersion,
            retries: conflictRetryRef.current,
            reason: 'missing_local_data',
          });
          return;
        }

        if (actualVersion === expectedVersion) {
          console.log('[TimelineSave] reloaded version matches expected — not a version race', {
            expectedVersion,
            actualVersion,
          });
          handleConflictExhausted({
            expectedVersion,
            actualVersion,
            retries: conflictRetryRef.current,
            reason: 'max_retries',
          });
          return;
        }

        if (conflictRetryRef.current >= MAX_CONFLICT_RETRIES) {
          handleConflictExhausted({
            expectedVersion,
            actualVersion,
            retries: conflictRetryRef.current,
            reason: 'max_retries',
          });
          return;
        }

        conflictRetryRef.current += 1;
        console.log('[TimelineSave] retrying save after conflict', {
          attempt: conflictRetryRef.current,
          expectedVersion,
          actualVersion,
        });
        return await doSave(latestDataRef.current, editSeqRef.current, {
          bypassQueue: true,
          completedSeqRef,
        });
      }

      setSaveStatus('error');
      if (dataRef.current) {
        scheduleSave(dataRef.current, { preserveStatus: true });
      }
    } finally {
      if (!options?.bypassQueue) {
        isSavingRef.current = false;

        const pendingSave = pendingSaveRef.current;
        if (pendingSave) {
          pendingSaveRef.current = null;
          if (completedSeqRef.current === null || pendingSave.seq > completedSeqRef.current) {
            void doSave(pendingSave.data, pendingSave.seq);
          }
        }
      }
    }
  }, [
    commitData,
    configVersionRef,
    editSeqRef,
    getDataRef,
    handleConflictExhausted,
    lastSavedSignatureRef,
    loadConflictRetryVersion,
    logConfigVersionUpdate,
    eventBus,
    saveMutation,
    savedSeqRef,
    selectedClipIdRef,
    selectedTrackIdRef,
  ]);

  const scheduleSave = useCallback<ScheduleSaveFn>((nextData, options) => {
    if (!persistenceEnabled) {
      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
        saveTimer.current = null;
      }
      pendingSaveRef.current = null;
      deferredSaveRef.current = null;
      if (!options?.preserveStatus) {
        setSaveStatus('saved');
      }
      return;
    }

    if (!options?.preserveStatus) {
      setSaveStatus('dirty');
    }

    // Gate on the shared interaction ref. If a drag or resize gesture is in
    // flight, stash the newest payload and defer scheduling the save timer
    // until the gesture ends. This prevents mid-gesture save round-trips from
    // triggering re-renders that drop pointer capture.
    if (isInteractionActive(getInteractionStateRef())) {
      deferredSaveRef.current = { data: nextData, preserveStatus: options?.preserveStatus };
      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
        saveTimer.current = null;
      }
      return;
    }

    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
    }

    if (isSavingRef.current) {
      pendingSaveRef.current = { data: nextData, seq: editSeqRef.current };
      return;
    }

    saveTimer.current = setTimeout(() => {
      saveTimer.current = null;
      conflictRetryRef.current = 0;
      void doSave(nextData, editSeqRef.current);
    }, 500);
  }, [doSave, editSeqRef, getInteractionStateRef, persistenceEnabled]);

  // When a gesture ends, flush the latest deferred payload (if any) through
  // the normal scheduleSave path, which will now proceed past the gate.
  useEffect(() => {
    return onInteractionEnd(getInteractionStateRef(), () => {
      const deferred = deferredSaveRef.current;
      if (!deferred) {
        return;
      }
      deferredSaveRef.current = null;
      scheduleSave(deferred.data, { preserveStatus: deferred.preserveStatus });
    });
  }, [getInteractionStateRef, scheduleSave]);

  const reloadFromServer = useCallback(async () => {
    const [loadedTimeline, registry] = await Promise.all([
      provider.loadTimeline(timelineId),
      provider.loadAssetRegistry(timelineId),
    ]);

    conflictRetryRef.current = 0;
    pendingSaveRef.current = null;
    setIsConflictExhausted(false);
    editSeqRef.current = savedSeqRef.current;
    logConfigVersionUpdate('reload', loadedTimeline.configVersion);
    configVersionRef.current = loadedTimeline.configVersion;

    const reloadedData = assetResolver
      ? await buildTimelineDataWithResolver(
          loadedTimeline.config,
          registry,
          assetResolver,
          loadedTimeline.configVersion,
          timelineId,
        )
      : await buildTimelineData(
          loadedTimeline.config,
          registry,
          resolveAssetUrl ?? ((file) => provider.resolveAssetUrl(file)),
          loadedTimeline.configVersion,
        );

    commitData(reloadedData, {
      save: false,
      skipHistory: true,
      updateLastSavedSignature: true,
      selectedClipId: selectedClipIdRef.current,
      selectedTrackId: selectedTrackIdRef.current,
    });
    setSaveStatus('saved');
  }, [
    assetResolver,
    commitData,
    configVersionRef,
    editSeqRef,
    logConfigVersionUpdate,
    provider,
    resolveAssetUrl,
    savedSeqRef,
    selectedClipIdRef,
    selectedTrackIdRef,
    timelineId,
  ]);

  const retrySaveAfterConflict = useCallback(async () => {
    const latestDataRef = getDataRef();
    if (!latestDataRef.current) {
      return;
    }

    setIsConflictExhausted(false);
    setSaveStatus('saving');
    conflictRetryRef.current = 0;

    try {
      await loadConflictRetryVersion();
      if (latestDataRef.current) {
        void doSave(latestDataRef.current, editSeqRef.current);
      }
    } catch {
      handleConflictExhausted({
        expectedVersion: configVersionRef.current,
        retries: conflictRetryRef.current,
        reason: 'load_failed',
      });
    }
  }, [configVersionRef, doSave, editSeqRef, getDataRef, handleConflictExhausted, loadConflictRetryVersion]);

  useEffect(() => {
    return () => {
      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
      }
    };
  }, []);

  return {
    scheduleSave,
    saveStatus,
    isConflictExhausted,
    reloadFromServer,
    retrySaveAfterConflict,
    isSavingRef,
  };
}
