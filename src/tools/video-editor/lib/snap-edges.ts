import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

/** Default snap threshold in seconds — overridden at call site based on zoom. */
const DEFAULT_THRESHOLD_S = 0.15;

/**
 * Collect all edge times (start and end) from actions on a row,
 * excluding the action being moved/resized.
 */
const collectEdges = (siblings: TimelineAction[], excludeIds: readonly string[]): number[] => {
  const edges: number[] = [0]; // always snap to timeline start
  for (const action of siblings) {
    if (excludeIds.includes(action.id)) continue;
    edges.push(action.start, action.end);
  }
  return edges;
};

/**
 * Find the nearest edge within the threshold.
 * Returns the edge time if within threshold, otherwise returns the original value.
 */
const snapValue = (value: number, edges: number[], threshold: number): number => {
  let best = value;
  let bestDist = threshold;
  for (const edge of edges) {
    const dist = Math.abs(value - edge);
    if (dist < bestDist) {
      bestDist = dist;
      best = edge;
    }
  }
  return best;
};

export interface SnapDragResult {
  start: number;
  snapped: boolean;
}

/**
 * Snap a dragged clip's start time so that its start or end aligns
 * with a sibling clip's start or end edge.
 */
export const snapDrag = (
  proposedStart: number,
  clipDuration: number,
  siblings: TimelineAction[],
  excludeId: string,
  thresholdSeconds = DEFAULT_THRESHOLD_S,
  excludeClipIds: string[] = [excludeId],
): SnapDragResult => {
  const edges = collectEdges(siblings, excludeClipIds);
  const proposedEnd = proposedStart + clipDuration;

  // Try snapping start edge
  const snappedStart = snapValue(proposedStart, edges, thresholdSeconds);
  if (snappedStart !== proposedStart) {
    return { start: snappedStart, snapped: true };
  }

  // Try snapping end edge
  const snappedEnd = snapValue(proposedEnd, edges, thresholdSeconds);
  if (snappedEnd !== proposedEnd) {
    return { start: snappedEnd - clipDuration, snapped: true };
  }

  return { start: proposedStart, snapped: false };
};

export interface SnapResizeResult {
  start: number;
  end: number;
  snapped: boolean;
}

/**
 * Snap a resize edge so it aligns with a sibling clip's start or end.
 */
export const snapResize = (
  proposedStart: number,
  proposedEnd: number,
  dir: 'left' | 'right',
  siblings: TimelineAction[],
  excludeId: string,
  thresholdSeconds = DEFAULT_THRESHOLD_S,
): SnapResizeResult => {
  const edges = collectEdges(siblings, [excludeId]);

  if (dir === 'left') {
    const snapped = snapValue(proposedStart, edges, thresholdSeconds);
    return { start: snapped, end: proposedEnd, snapped: snapped !== proposedStart };
  }

  const snapped = snapValue(proposedEnd, edges, thresholdSeconds);
  return { start: proposedStart, end: snapped, snapped: snapped !== proposedEnd };
};
