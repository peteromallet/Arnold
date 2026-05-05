import { splitClipAtPlayhead } from '@/tools/video-editor/lib/editor-utils.ts';
import type { ClipMeta, TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

export const DURATION_KEYS = ['speed', 'from', 'to', 'hold'] as const;

export function patchAffectsDuration(patch: Partial<ClipMeta>): boolean {
  return DURATION_KEYS.some((key) => key in patch);
}

export function recalcActionEnd(action: TimelineAction, merged: Partial<ClipMeta>): number {
  const speed = merged.speed ?? 1;
  const fallbackSourceDuration = Math.max(0, (action.end - action.start) * speed);
  const sourceDuration = typeof merged.hold === 'number'
    ? merged.hold
    : Math.max(
      0,
      (merged.to ?? fallbackSourceDuration + (merged.from ?? 0)) - (merged.from ?? 0),
    );

  return action.start + sourceDuration / speed;
}

export function splitIntersectingClipsAtPlayhead(
  resolvedConfig: NonNullable<TimelineData['resolvedConfig']>,
  rows: TimelineData['rows'],
  clipIds: string[],
  currentTime: number,
): {
  config: NonNullable<TimelineData['resolvedConfig']>;
  didSplit: boolean;
} {
  const intersectingClipIds = new Set<string>();

  for (const row of rows) {
    for (const action of row.actions) {
      if (
        clipIds.includes(action.id)
        && action.start <= currentTime
        && currentTime < action.end
      ) {
        intersectingClipIds.add(action.id);
      }
    }
  }

  if (intersectingClipIds.size === 0) {
    return { config: resolvedConfig, didSplit: false };
  }

  let nextResolvedConfig = resolvedConfig;
  let didSplit = false;

  for (const clipId of clipIds) {
    if (!intersectingClipIds.has(clipId)) {
      continue;
    }

    const splitResult = splitClipAtPlayhead(nextResolvedConfig, clipId, currentTime);
    if (!splitResult.nextSelectedClipId) {
      continue;
    }

    nextResolvedConfig = splitResult.config;
    didSplit = true;
  }

  return {
    config: nextResolvedConfig,
    didSplit,
  };
}
