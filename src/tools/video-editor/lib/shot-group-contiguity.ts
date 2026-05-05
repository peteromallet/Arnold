import type { PinnedShotGroup } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

const CONTIGUITY_EPSILON = 0.001;

/**
 * Snap clips within each pinned shot group so they are contiguous.
 * For each group, orders its actions by start time and snaps each
 * subsequent action's start to the previous action's end.
 * Returns the rows array unchanged when no repairs are needed.
 */
export function ensureGroupContiguity(
  rows: TimelineRow[],
  pinnedShotGroups: PinnedShotGroup[] | undefined,
): TimelineRow[] {
  if (!pinnedShotGroups?.length) return rows;

  // Build a lookup: actionId -> { rowIndex, actionIndex }
  const actionLookup = new Map<string, { rowIndex: number; actionIndex: number }>();
  for (let ri = 0; ri < rows.length; ri++) {
    const actions = rows[ri].actions;
    for (let ai = 0; ai < actions.length; ai++) {
      actionLookup.set(actions[ai].id, { rowIndex: ri, actionIndex: ai });
    }
  }

  // Collect all overrides: actionId -> new start/end
  const overrides = new Map<string, { start: number; end: number }>();

  for (const group of pinnedShotGroups) {
    if (group.clipIds.length < 2) continue;

    // Resolve actions in the group
    const groupActions: { action: TimelineAction; loc: { rowIndex: number; actionIndex: number } }[] = [];
    for (const clipId of group.clipIds) {
      const loc = actionLookup.get(clipId);
      if (loc) {
        const action = rows[loc.rowIndex].actions[loc.actionIndex];
        groupActions.push({ action, loc });
      }
    }
    if (groupActions.length < 2) continue;

    // Sort by current start position
    groupActions.sort((a, b) => a.action.start - b.action.start);

    let cursor = groupActions[0].action.end;
    for (let i = 1; i < groupActions.length; i++) {
      const { action } = groupActions[i];
      const gap = Math.abs(action.start - cursor);
      const duration = action.end - action.start;

      if (gap > CONTIGUITY_EPSILON) {
        overrides.set(action.id, { start: cursor, end: cursor + duration });
      }

      // Advance cursor using the (possibly overridden) position
      const effectiveStart = overrides.get(action.id)?.start ?? action.start;
      cursor = effectiveStart + duration;
    }
  }

  if (overrides.size === 0) return rows;

  return rows.map((row) => {
    const hasOverride = row.actions.some((action) => overrides.has(action.id));
    if (!hasOverride) return row;

    return {
      ...row,
      actions: row.actions.map((action) => {
        const override = overrides.get(action.id);
        return override ? { ...action, start: override.start, end: override.end } : action;
      }),
    };
  });
}
