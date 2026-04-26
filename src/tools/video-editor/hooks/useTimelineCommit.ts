import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { useTimelineSelectionStore, useSelectionStoreApi } from '@/shared/state/selectionStore';
import { TimelineEventBus } from '@/tools/video-editor/hooks/useTimelineEventBus';
import { buildTrackClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { migrateToFlatTracks } from '@/tools/video-editor/lib/migrate';
import { serializeForDisk } from '@/tools/video-editor/lib/serialize';
import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils';
import {
  assembleTimelineData,
  preserveUploadingClips,
  rowsToConfig,
  type ClipMeta,
  type ClipOrderMap,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';
import type { AssetRegistryEntry } from '@/tools/video-editor/types';

export type CommitHistoryOptions = {
  transactionId?: string;
  semantic?: boolean;
};

export type CommitDataOptions = {
  save?: boolean;
  selectedClipId?: string | null;
  selectedTrackId?: string | null;
  updateLastSavedSignature?: boolean;
  transactionId?: string;
  semantic?: boolean;
  skipHistory?: boolean;
};

export type ScheduleSaveFn = (
  nextData: TimelineData,
  options?: { preserveStatus?: boolean },
) => void;

export type TimelineEditMutation =
  | {
      type: 'rows';
      rows: TimelineRow[];
      metaUpdates?: Record<string, Partial<ClipMeta>>;
      metaDeletes?: string[];
      clipOrderOverride?: ClipOrderMap;
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'config';
      resolvedConfig: TimelineData['resolvedConfig'];
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'pinnedShotGroups';
      pinnedShotGroups: NonNullable<TimelineData['config']['pinnedShotGroups']>;
    };

export type ApplyEditOptions = {
  save?: boolean;
  selectedClipId?: string | null;
  selectedTrackId?: string | null;
  transactionId?: string;
  semantic?: boolean;
};

interface UseTimelineCommitOptions {
  eventBus: TimelineEventBus;
  lastSavedSignatureRef: MutableRefObject<string>;
}

export interface UseTimelineCommitResult {
  data: TimelineData | null;
  dataRef: MutableRefObject<TimelineData | null>;
  selectedClipId: string | null;
  selectedTrackId: string | null;
  setSelectedTrackId: Dispatch<SetStateAction<string | null>>;
  applyEdit: (mutation: TimelineEditMutation, options?: ApplyEditOptions) => void;
  patchRegistry: (assetId: string, entry: AssetRegistryEntry, src?: string) => void;
  unpatchRegistry: (assetId: string) => void;
  commitData: (nextData: TimelineData, options?: CommitDataOptions) => void;
  materializeData: (
    current: TimelineData,
    rows: TimelineRow[],
    meta: Record<string, ClipMeta>,
    clipOrder: ClipOrderMap,
  ) => TimelineData;
  editSeqRef: MutableRefObject<number>;
  pendingOpsRef: MutableRefObject<number>;
  selectedClipIdRef: MutableRefObject<string | null>;
  selectedTrackIdRef: MutableRefObject<string | null>;
}

export function useTimelineCommit({
  eventBus,
  lastSavedSignatureRef,
}: UseTimelineCommitOptions): UseTimelineCommitResult {
  const editSeqRef = useRef(0);
  const pendingOpsRef = useRef(0);
  const dataRef = useRef<TimelineData | null>(null);
  const selectedClipIdRef = useRef<string | null>(null);
  const selectedTrackIdRef = useRef<string | null>(null);
  const [data, setData] = useState<TimelineData | null>(null);
  const selectionStore = useSelectionStoreApi();
  const {
    selectedClipId,
    selectedTrackId,
  } = useTimelineSelectionStore();
  const setSelectedTrackId = useCallback<Dispatch<SetStateAction<string | null>>>((updater) => {
    const nextTrackId = typeof updater === 'function'
      ? updater(selectionStore.getState().timeline.selectedTrackId)
      : updater;
    selectionStore.getState().setTimelineSelectedTrackId(nextTrackId);
  }, [selectionStore]);

  useLayoutEffect(() => {
    dataRef.current = data;
    selectedClipIdRef.current = selectedClipId;
    selectedTrackIdRef.current = selectedTrackId;
  }, [data, selectedClipId, selectedTrackId]);

  const withPinnedShotGroups = useCallback((
    config: TimelineData['config'],
    pinnedShotGroups: TimelineData['config']['pinnedShotGroups'],
  ): TimelineData['config'] => ({
    ...config,
    pinnedShotGroups: pinnedShotGroups && pinnedShotGroups.length > 0
      ? pinnedShotGroups
      : undefined,
  }), []);

  const materializeData = useCallback((
    current: TimelineData,
    rows: TimelineRow[],
    meta: Record<string, ClipMeta>,
    clipOrder: ClipOrderMap,
  ) => {
    // Soft-tag model: cohesion is a property of edit operations, not data shape.
    // rowsToConfig receives the untouched pinnedShotGroups from the current config;
    // callers that need to update group membership must pass `pinnedShotGroupsOverride`
    // explicitly on the mutation, which `applyEdit` handles below.
    const config = rowsToConfig(
      rows,
      meta,
      current.output,
      clipOrder,
      current.tracks,
      current.config.pinnedShotGroups,
    );

    return preserveUploadingClips(
      { ...current, rows, meta } as TimelineData,
      buildDataFromCurrentRegistry(config, current),
    );
  }, []);

  const commitData = useCallback((
    nextData: TimelineData,
    options?: CommitDataOptions,
  ) => {
    const shouldSave = options?.save ?? true;
    const currentData = dataRef.current;

    if (shouldSave && !options?.skipHistory && currentData) {
      eventBus.emit('beforeCommit', currentData, {
        transactionId: options?.transactionId,
        semantic: options?.semantic,
      });
    }

    dataRef.current = nextData;
    setData(nextData);

    if (options?.selectedClipId !== undefined) {
      selectedClipIdRef.current = options.selectedClipId;
      if (options.selectedClipId === null) {
        selectionStore.getState().clearTimelineSelection({ clearGallery: false });
      } else {
        selectionStore.getState().selectTimelineClip(
          options.selectedClipId,
          undefined,
          { clearGallery: false },
        );
      }
    } else if (selectedClipIdRef.current && !nextData.meta[selectedClipIdRef.current]) {
      selectedClipIdRef.current = null;
      selectionStore.getState().clearTimelineSelection({ clearGallery: false });
    }

    eventBus.emit('pruneSelection', new Set(Object.keys(nextData.meta)));

    if (options?.selectedTrackId !== undefined) {
      selectedTrackIdRef.current = options.selectedTrackId;
      selectionStore.getState().setTimelineSelectedTrackId(options.selectedTrackId);
    } else {
      const fallbackTrackId = selectedTrackIdRef.current
        && nextData.tracks.some((track) => track.id === selectedTrackIdRef.current)
        ? selectedTrackIdRef.current
        : nextData.tracks[0]?.id ?? null;
      selectedTrackIdRef.current = fallbackTrackId;
      selectionStore.getState().setTimelineSelectedTrackId(fallbackTrackId);
    }

    if (options?.updateLastSavedSignature) {
      lastSavedSignatureRef.current = nextData.stableSignature;
    }

    if (shouldSave) {
      editSeqRef.current += 1;
      eventBus.emit('scheduleSave', nextData);
    }
  }, [eventBus, lastSavedSignatureRef, selectionStore]);

  const applyEdit = useCallback((
    mutation: TimelineEditMutation,
    options?: ApplyEditOptions,
  ) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    if (mutation.type === 'pinnedShotGroups') {
      // Membership/metadata-only mutation. Soft-tag model: no projection; the
      // clips are unchanged, only the group entries' clipIds/mode/etc. update.
      commitData(
        preserveUploadingClips(
          current,
          buildDataFromCurrentRegistry(
            withPinnedShotGroups(current.config, mutation.pinnedShotGroups),
            current,
          ),
        ),
        {
          save: options?.save,
          selectedClipId: options?.selectedClipId,
          selectedTrackId: options?.selectedTrackId,
          transactionId: options?.transactionId,
          semantic: options?.semantic,
        },
      );
      return;
    }

    if (mutation.type === 'rows') {
      const nextMeta: Record<string, ClipMeta> = { ...current.meta };

      if (mutation.metaUpdates) {
        for (const [clipId, patch] of Object.entries(mutation.metaUpdates)) {
          nextMeta[clipId] = nextMeta[clipId]
            ? { ...nextMeta[clipId], ...patch }
            : (patch as ClipMeta);
        }
      }

      if (mutation.metaDeletes) {
        for (const clipId of mutation.metaDeletes) {
          delete nextMeta[clipId];
        }
      }

      const baseNextData = materializeData(
        current,
        mutation.rows,
        nextMeta,
        mutation.clipOrderOverride ?? buildTrackClipOrder(current.tracks, current.clipOrder, mutation.metaDeletes),
      );
      const nextData = mutation.pinnedShotGroupsOverride === undefined
        ? baseNextData
        : preserveUploadingClips(
            { ...current, rows: mutation.rows, meta: nextMeta } as TimelineData,
            buildDataFromCurrentRegistry(
              withPinnedShotGroups(baseNextData.config, mutation.pinnedShotGroupsOverride),
              current,
            ),
          );

      commitData(
        nextData,
        {
          save: options?.save,
          transactionId: options?.transactionId,
          semantic: options?.semantic,
        },
      );
      return;
    }

    commitData(
      preserveUploadingClips(
        current,
        buildDataFromCurrentRegistry(
          serializeForDisk(
            mutation.resolvedConfig,
            mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
          ),
          current,
        ),
      ),
      {
        save: options?.save,
        selectedClipId: options?.selectedClipId,
        selectedTrackId: options?.selectedTrackId,
        transactionId: options?.transactionId,
        semantic: options?.semantic,
      },
    );
  }, [commitData, materializeData, withPinnedShotGroups]);

  const patchRegistry = useCallback((assetId: string, entry: AssetRegistryEntry, src?: string) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const nextRegistry = {
      ...current.registry,
      assets: {
        ...current.registry.assets,
        [assetId]: entry,
      },
    };
    const nextResolvedRegistry = {
      ...current.resolvedConfig.registry,
      [assetId]: {
        ...entry,
        src: src ?? current.resolvedConfig.registry[assetId]?.src ?? entry.file,
      },
    };
    const nextConfig = { ...current.config };
    const migratedConfig = migrateToFlatTracks(nextConfig);
    migratedConfig.tracks = migratedConfig.tracks ?? [];

    const nextData = assembleTimelineData({
      config: migratedConfig,
      configVersion: current.configVersion,
      registry: nextRegistry,
      resolvedConfig: {
        output: { ...migratedConfig.output },
        tracks: migratedConfig.tracks,
        clips: migratedConfig.clips.map((clip) => ({
          ...clip,
          assetEntry: clip.asset ? nextResolvedRegistry[clip.asset] : undefined,
        })),
        // Reuse resolved entries for unchanged assets and patch the current asset in-place.
        registry: nextResolvedRegistry,
      },
      assetMap: Object.fromEntries(
        Object.entries(nextRegistry.assets ?? {}).map(([nextAssetId, nextEntry]) => [nextAssetId, nextEntry.file]),
      ),
      output: { ...migratedConfig.output },
    });

    commitData(nextData, {
      save: false,
      selectedClipId: selectedClipIdRef.current,
      selectedTrackId: selectedTrackIdRef.current,
    });
  }, [commitData]);

  const unpatchRegistry = useCallback((assetId: string) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const { [assetId]: removedAsset, ...remainingAssets } = current.registry.assets ?? {};
    void removedAsset;
    const nextRegistry = {
      ...current.registry,
      assets: remainingAssets,
    };
    const { [assetId]: removedResolvedAsset, ...remainingResolvedRegistry } = current.resolvedConfig.registry;
    void removedResolvedAsset;
    const nextConfig = { ...current.config };
    const migratedConfig = migrateToFlatTracks(nextConfig);
    migratedConfig.tracks = migratedConfig.tracks ?? [];

    const nextData = assembleTimelineData({
      config: migratedConfig,
      configVersion: current.configVersion,
      registry: nextRegistry,
      resolvedConfig: {
        output: { ...migratedConfig.output },
        tracks: migratedConfig.tracks,
        clips: migratedConfig.clips.map((clip) => ({
          ...clip,
          assetEntry: clip.asset ? remainingResolvedRegistry[clip.asset] : undefined,
        })),
        registry: remainingResolvedRegistry,
      },
      assetMap: Object.fromEntries(
        Object.entries(remainingAssets).map(([nextAssetId, nextEntry]) => [nextAssetId, nextEntry.file]),
      ),
      output: { ...migratedConfig.output },
    });

    commitData(nextData, {
      save: false,
      selectedClipId: selectedClipIdRef.current,
      selectedTrackId: selectedTrackIdRef.current,
    });
  }, [commitData]);

  return {
    data,
    dataRef,
    selectedClipId,
    selectedTrackId,
    setSelectedTrackId,
    applyEdit,
    patchRegistry,
    unpatchRegistry,
    commitData,
    materializeData,
    editSeqRef,
    pendingOpsRef,
    selectedClipIdRef,
    selectedTrackIdRef,
  };
}
