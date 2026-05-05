import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { SelectClipOptions } from '@/shared/state/selectionStore.ts';
import type {
  ClipMeta,
  TimelineData,
} from '@/tools/video-editor/lib/timeline-data.ts';
import type { ApplyEditOptions } from '@/tools/video-editor/hooks/useTimelineCommit.ts';
import type { TimelineSelectedTrack } from '@/tools/video-editor/hooks/timeline-state-types.ts';

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
  selectClip: (clipId: string, opts?: SelectClipOptions) => void;
  setSelectedTrackId: Dispatch<SetStateAction<string | null>>;
}
