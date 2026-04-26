import {
  useCallback,
  type Dispatch,
  type SetStateAction,
} from 'react';
import { useDerivedTimeline } from '@/tools/video-editor/hooks/useDerivedTimeline';
import {
  useTimelineMultiSelect,
  type SelectClipOptions,
  type UseTimelineMultiSelectResult,
} from '@/shared/state/selectionStore';
import type {
  TimelineResolvedConfig,
  TimelineSelectedClip,
  TimelineSelectedTrack,
  TimelineSetSelectedClipId,
} from '@/tools/video-editor/hooks/timeline-state-types';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';

export interface UseTimelineSelectionArgs {
  data: TimelineData | null;
  selectedTrackId: string | null;
  setSelectedClipId: TimelineSetSelectedClipId;
}

export interface UseTimelineSelectionResult {
  selectedClipIds: UseTimelineMultiSelectResult['selectedClipIds'];
  selectedClipIdsRef: UseTimelineMultiSelectResult['selectedClipIdsRef'];
  additiveSelectionRef: UseTimelineMultiSelectResult['additiveSelectionRef'];
  primaryClipId: UseTimelineMultiSelectResult['primaryClipId'];
  selectedClip: TimelineSelectedClip;
  selectedTrack: TimelineSelectedTrack;
  selectedClipHasPredecessor: boolean;
  resolvedConfig: TimelineResolvedConfig;
  addToSelection: UseTimelineMultiSelectResult['addToSelection'];
  clearSelection: UseTimelineMultiSelectResult['clearSelection'];
  replaceTimelineSelection: UseTimelineMultiSelectResult['selectClips'];
  isClipSelected: UseTimelineMultiSelectResult['isClipSelected'];
  pruneSelection: UseTimelineMultiSelectResult['pruneSelection'];
  selectClip: UseTimelineMultiSelectResult['selectClip'];
  selectClips: UseTimelineMultiSelectResult['selectClips'];
  setSelectedClipId: Dispatch<SetStateAction<string | null>>;
}

const getFirstSelectedClipId = (clipIds: ReadonlySet<string>): string | null => {
  for (const clipId of clipIds) {
    return clipId;
  }

  return null;
};

const getPrimaryClipId = (
  clipIds: ReadonlySet<string>,
  preferredClipId: string | null,
): string | null => {
  if (preferredClipId && clipIds.has(preferredClipId)) {
    return preferredClipId;
  }

  return getFirstSelectedClipId(clipIds);
};

export function useTimelineSelection({
  data,
  selectedTrackId,
  setSelectedClipId: setSelectionState,
}: UseTimelineSelectionArgs): UseTimelineSelectionResult {
  const multiSelect = useTimelineMultiSelect();
  const {
    addToSelection: addToSelectionState,
    clearSelection: clearSelectionState,
    isClipSelected,
    primaryClipId,
    pruneSelection,
    selectClip: selectClipState,
    selectClips: selectClipsState,
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
  } = multiSelect;
  const selectionDerived = useDerivedTimeline(data, primaryClipId, selectedTrackId);

  // The selectionStore actions below already derive primaryClipId via
  // buildTimelineState; do NOT also call setSelectionState here. setSelectionState
  // routes to setTimelineSelectedClipId → selectTimelineClip(id, undefined),
  // which resets selectedClipIds to a single-clip set and silently destroys
  // multi-selection committed by the action above.
  const selectClip = useCallback((clipId: string, opts?: SelectClipOptions) => {
    if (opts?.preserveSelection && selectedClipIdsRef.current.has(clipId)) {
      return;
    }

    selectClipState(clipId, opts);
  }, [selectClipState, selectedClipIdsRef]);

  const selectClips = useCallback((clipIds: Iterable<string>) => {
    selectClipsState(clipIds);
  }, [selectClipsState]);

  const addToSelection = useCallback((clipIds: Iterable<string>) => {
    addToSelectionState(clipIds);
  }, [addToSelectionState]);

  const clearSelection = useCallback(() => {
    clearSelectionState();
  }, [clearSelectionState]);

  const replaceTimelineSelection = useCallback((clipIds: Iterable<string>) => {
    selectClipsState(clipIds);
  }, [selectClipsState]);

  const setSelectedClipId = useCallback<Dispatch<SetStateAction<string | null>>>((updater) => {
    const nextClipId = typeof updater === 'function'
      ? updater(primaryClipId)
      : updater;

    if (nextClipId === null) {
      clearSelection();
      return;
    }

    selectClip(nextClipId);
  }, [clearSelection, primaryClipId, selectClip]);

  return {
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
    primaryClipId,
    selectedClip: selectionDerived.selectedClip,
    selectedTrack: selectionDerived.selectedTrack,
    selectedClipHasPredecessor: selectionDerived.selectedClipHasPredecessor,
    resolvedConfig: selectionDerived.resolvedConfig,
    addToSelection,
    clearSelection,
    replaceTimelineSelection,
    isClipSelected,
    pruneSelection,
    selectClip,
    selectClips,
    setSelectedClipId,
  };
}
