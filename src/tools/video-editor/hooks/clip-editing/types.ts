import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { UseTimelineMultiSelectResult } from '@/shared/state/selectionStore';
import type {
  ClipMeta,
  TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import type { ApplyEditOptions } from '@/tools/video-editor/hooks/useTimelineCommit';
import type { TimelineSelectedTrack } from '@/tools/video-editor/hooks/timeline-state-types';

export type DeleteClipOptions = {
  allowPinnedGroupDelete?: boolean;
};

export interface ClipEditingContext {
  dataRef: MutableRefObject<TimelineData | null>;
  resolvedConfig: TimelineData['resolvedConfig'] | null;
  selectedClipId: string | null;
  selectedTrack: TimelineSelectedTrack;
  currentTimeRef: MutableRefObject<number>;
  applyRowsEdit: (
    rows: TimelineData['rows'],
    metaUpdates?: Record<string, Partial<ClipMeta>>,
    metaDeletes?: string[],
    clipOrderOverride?: TimelineData['clipOrder'],
    options?: ApplyEditOptions,
  ) => void;
  applyConfigEdit: (
    resolvedConfig: TimelineData['resolvedConfig'],
    options?: ApplyEditOptions,
  ) => void;
  isPinnedGroupMember: (clipId: string) => boolean;
  notifyPinnedGroupEditBlocked: () => void;
  getValidClipIds: (clipIds: string[]) => string[];
  selectClip: UseTimelineMultiSelectResult['selectClip'];
  setSelectedTrackId: Dispatch<SetStateAction<string | null>>;
}
