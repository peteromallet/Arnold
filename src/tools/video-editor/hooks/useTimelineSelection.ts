import { useDerivedTimeline } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
import {
  useTimelineMultiSelect,
  type UseTimelineMultiSelectResult,
} from '@/shared/state/selectionStore.ts';
import type {
  TimelineResolvedConfig,
  TimelineSelectedClip,
  TimelineSelectedTrack,
} from '@/tools/video-editor/hooks/timeline-state-types.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';

export interface UseTimelineSelectionArgs {
  data: TimelineData | null;
  selectedTrackId: string | null;
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
  isClipSelected: UseTimelineMultiSelectResult['isClipSelected'];
  pruneSelection: UseTimelineMultiSelectResult['pruneSelection'];
}

export function useTimelineSelection({
  data,
  selectedTrackId,
}: UseTimelineSelectionArgs): UseTimelineSelectionResult {
  const multiSelect = useTimelineMultiSelect();
  const {
    isClipSelected,
    primaryClipId,
    pruneSelection,
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
  } = multiSelect;
  const selectionDerived = useDerivedTimeline(data, primaryClipId, selectedTrackId);

  return {
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
    primaryClipId,
    selectedClip: selectionDerived.selectedClip,
    selectedTrack: selectionDerived.selectedTrack,
    selectedClipHasPredecessor: selectionDerived.selectedClipHasPredecessor,
    resolvedConfig: selectionDerived.resolvedConfig,
    isClipSelected,
    pruneSelection,
  };
}
