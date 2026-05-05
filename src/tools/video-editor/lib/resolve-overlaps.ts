import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';

/** Minimum clip duration in seconds — below this the move is rejected. */
const MIN_CLIP_DURATION = 0.05;

export interface OverlapResult {
  /** Updated rows with the moved clip trimmed to fit. */
  rows: TimelineRow[];
  /** Metadata patch for the moved clip if its source-time `from`/`to` changed. */
  metaPatches: Record<string, Partial<ClipMeta>>;
  /** Requested vs actual start positions when overlap resolution moves the clip. */
  adjustments: Array<{ clipId: string; requestedStart: number; actualStart: number }>;
}

export interface GroupExtent {
  start: number;
  end: number;
}

/**
 * Find the largest gap that contains or is nearest to `preferred` within the
 * range [0, ∞). Siblings are treated as immovable obstacles.
 */
function findBestGap(
  preferred: number,
  duration: number,
  siblings: TimelineAction[],
): { start: number; end: number } | null {
  // Build sorted list of occupied intervals
  const occupied = siblings
    .map((s) => ({ start: s.start, end: s.end }))
    .sort((a, b) => a.start - b.start);

  // Build gaps between occupied intervals (including 0..first and last..∞)
  const gaps: Array<{ start: number; end: number }> = [];
  let cursor = 0;
  for (const occ of occupied) {
    if (occ.start > cursor) {
      gaps.push({ start: cursor, end: occ.start });
    }
    cursor = Math.max(cursor, occ.end);
  }
  // Gap from last sibling to infinity
  gaps.push({ start: cursor, end: Infinity });

  if (gaps.length === 0) return null;

  // Find the gap that contains the preferred start, or the nearest one
  let bestGap = gaps[0];
  let bestDistance = Infinity;

  for (const gap of gaps) {
    // If preferred start falls in this gap
    if (preferred >= gap.start && preferred < gap.end) {
      bestGap = gap;
      bestDistance = 0;
      break;
    }

    // Distance from preferred to gap
    const dist = preferred < gap.start
      ? gap.start - preferred
      : preferred - gap.end;
    if (dist < bestDistance) {
      bestDistance = dist;
      bestGap = gap;
    }
  }

  return bestGap;
}

export function findBestGroupStart(
  preferredExtent: GroupExtent,
  siblings: TimelineAction[],
): number | null {
  const preferred = preferredExtent.start;
  const duration = preferredExtent.end - preferredExtent.start;
  const occupied = siblings
    .map((sibling) => ({ start: sibling.start, end: sibling.end }))
    .sort((left, right) => left.start - right.start);

  const gaps: Array<{ start: number; end: number }> = [];
  let cursor = 0;
  for (const interval of occupied) {
    if (interval.start > cursor) {
      gaps.push({ start: cursor, end: interval.start });
    }
    cursor = Math.max(cursor, interval.end);
  }
  gaps.push({ start: cursor, end: Infinity });

  let bestStart: number | null = null;
  let bestDistance = Infinity;

  for (const gap of gaps) {
    if (gap.end !== Infinity && gap.end - gap.start < duration) {
      continue;
    }

    const maxStart = gap.end === Infinity ? Infinity : gap.end - duration;
    const candidateStart = preferred < gap.start
      ? gap.start
      : preferred > maxStart
        ? maxStart
        : preferred;
    const distance = Math.abs(candidateStart - preferred);

    if (distance < bestDistance) {
      bestDistance = distance;
      bestStart = candidateStart;
    }
  }

  return bestStart;
}

/**
 * Trim the **moved/resized clip** so it doesn't overlap any existing siblings
 * on the same row. Existing clips are treated as immovable; the moved clip is
 * the one that gives way.
 *
 * Strategy: find the gap (between siblings) that the clip's requested start
 * falls into, then clamp the clip to fit within that gap.
 */
export function resolveOverlaps(
  rows: TimelineRow[],
  rowId: string,
  clipId: string,
  meta: Record<string, ClipMeta>,
): OverlapResult {
  const metaPatches: Record<string, Partial<ClipMeta>> = {};
  const adjustments: Array<{ clipId: string; requestedStart: number; actualStart: number }> = [];

  const nextRows = rows.map((row) => {
    if (row.id !== rowId) return row;

    const movedAction = row.actions.find((a) => a.id === clipId);
    if (!movedAction) return row;

    const siblings = row.actions.filter((a) => a.id !== clipId);

    // Check if there's actually any overlap
    const hasOverlap = siblings.some(
      (sib) => movedAction.start < sib.end && movedAction.end > sib.start,
    );
    if (!hasOverlap) return row;

    const clipMeta = meta[clipId];
    const speed = clipMeta?.speed ?? 1;
    const duration = movedAction.end - movedAction.start;

    const gap = findBestGap(movedAction.start, duration, siblings);
    if (!gap) return row;

    // Clamp clip to fit within the gap
    let start = Math.max(movedAction.start, gap.start);
    let end = gap.end === Infinity
      ? start + duration
      : Math.min(start + duration, gap.end);

    // If clamping end pushed duration below threshold, try starting at gap.start
    if (end - start < MIN_CLIP_DURATION && gap.end !== Infinity) {
      start = gap.start;
      end = Math.min(gap.start + duration, gap.end);
    }

    // Still too small — reject the move (return row unchanged)
    if (end - start < MIN_CLIP_DURATION) {
      return row;
    }

    // Update source-time metadata if start changed (for timed clips)
    if (start !== movedAction.start && clipMeta && typeof clipMeta.hold !== 'number') {
      const trimmedSeconds = start - movedAction.start;
      metaPatches[clipId] = {
        ...metaPatches[clipId],
        from: (clipMeta.from ?? 0) + trimmedSeconds * speed,
      };
    }

    // Update source-time metadata if end changed
    if (end !== movedAction.end && clipMeta && typeof clipMeta.hold !== 'number') {
      const from = metaPatches[clipId]?.from ?? clipMeta.from ?? 0;
      metaPatches[clipId] = {
        ...metaPatches[clipId],
        to: from + (end - start) * speed,
      };
    }

    if (start !== movedAction.start) {
      adjustments.push({
        clipId,
        requestedStart: movedAction.start,
        actualStart: start,
      });
    }

    const trimmedAction = { ...movedAction, start, end };
    return {
      ...row,
      actions: row.actions.map((a) => (a.id === clipId ? trimmedAction : a)),
    };
  });

  return { rows: nextRows, metaPatches, adjustments };
}
