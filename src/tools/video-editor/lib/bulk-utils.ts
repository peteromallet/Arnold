import type { ClipTab } from '@/tools/video-editor/hooks/useEditorPreferences';
import { getBulkVisibleTabs as getRegistryBackedBulkVisibleTabs } from '@/tools/video-editor/lib/clip-inspector';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types';

export const getSharedValue = <T,>(values: T[]): T | null => {
  if (values.length === 0) {
    return null;
  }

  const [firstValue, ...rest] = values;
  return rest.every((value) => value === firstValue) ? firstValue : null;
};

const getNestedComparisonKey = (value: unknown): string => {
  if (value === undefined) {
    return '__undefined__';
  }

  if (value === null) {
    return '__null__';
  }

  if (
    typeof value === 'object'
    && value !== null
    && 'type' in value
    && typeof value.type === 'string'
  ) {
    return `type:${value.type}`;
  }

  return `json:${JSON.stringify(value)}`;
};

export const getSharedNestedValue = <T,>(
  clips: ResolvedTimelineClip[],
  accessor: (clip: ResolvedTimelineClip) => T | undefined,
): T | null => {
  if (clips.length === 0) {
    return null;
  }

  const [firstClip, ...rest] = clips;
  const firstValue = accessor(firstClip);
  const firstKey = getNestedComparisonKey(firstValue);

  return rest.every((clip) => getNestedComparisonKey(accessor(clip)) === firstKey)
    ? (firstValue ?? null)
    : null;
};

export const getBulkVisibleTabs = (
  clips: ResolvedTimelineClip[],
  tracks: TrackDefinition[],
): ClipTab[] => {
  return getRegistryBackedBulkVisibleTabs(clips, tracks);
};
