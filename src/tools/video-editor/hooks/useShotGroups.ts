import { useMemo } from 'react';
import type { Shot } from '@/domains/generation/types/index.ts';
import { resolveGroupTrackId } from '@/tools/video-editor/lib/pinned-group-projection.ts';
import type { TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

const SHOT_COLORS = ['#a855f7', '#ef4444', '#22c55e', '#3b82f6', '#f59e0b', '#14b8a6', '#ec4899', '#84cc16'];

export interface ShotGroup {
  shotId: string;
  shotName: string;
  rowId: string;
  rowIndex: number;
  start: number;
  clipIds: string[];
  children: Array<{ clipId: string; offset: number; duration: number }>;
  color: string;
  mode?: 'images' | 'video';
}

export function getShotColor(shotId: string): string {
  let hash = 0;
  for (let index = 0; index < shotId.length; index += 1) {
    hash = ((hash * 31) + shotId.charCodeAt(index)) >>> 0;
  }
  return SHOT_COLORS[hash % SHOT_COLORS.length];
}

export function useShotGroups(
  rows: TimelineRow[],
  shots: Shot[] | undefined,
  pinnedShotGroups?: TimelineConfig['pinnedShotGroups'],
): ShotGroup[] {
  return useMemo(() => {
    const rowIndexById = new Map(rows.map((row, rowIndex) => [row.id, rowIndex]));
    const shotNameById = new Map((shots ?? []).map((shot) => [shot.id, shot.name]));

    const result: ShotGroup[] = [];
    for (const group of pinnedShotGroups ?? []) {
      const resolvedTrackId = resolveGroupTrackId(group, rows);
      const rowIndex = rowIndexById.get(resolvedTrackId);
      if (typeof rowIndex !== 'number') continue;

      // Soft-tag model: derive children (clipId/offset/duration) from
      // the live row actions, since the data no longer carries them.
      const row = rows[rowIndex];
      if (!row) continue;
      const actionsById = new Map(
        row.actions.map((action) => [action.id, action] as const),
      );
      const liveClipIds = group.clipIds.filter((clipId) => actionsById.has(clipId));
      if (liveClipIds.length === 0) continue;

      const liveActions = liveClipIds
        .map((clipId) => actionsById.get(clipId)!)
        .sort((a, b) => a.start - b.start);
      const firstAction = liveActions[0]!;
      const groupStart = firstAction.start;
      const children = liveActions.map((action) => ({
        clipId: action.id,
        offset: action.start - groupStart,
        duration: action.end - action.start,
      }));

      result.push({
        shotId: group.shotId,
        shotName: shotNameById.get(group.shotId) ?? group.shotId,
        rowId: resolvedTrackId,
        rowIndex,
        start: groupStart,
        clipIds: children.map((child) => child.clipId),
        children,
        color: getShotColor(group.shotId),
        mode: group.mode,
      });
    }
    return result;
  }, [rows, shots, pinnedShotGroups]);
}
