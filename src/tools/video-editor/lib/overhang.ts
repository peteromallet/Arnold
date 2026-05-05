import { updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils.ts';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

const MIN_TIMELINE_DURATION_SECONDS = 0.05;
const DEFAULT_HOLD_FRAME_RATE = 30;
const OVERHANG_EPSILON = 0.0001;

export interface ClipOverhang {
  sourceDurationSeconds: number;
  totalTimelineDurationSeconds: number;
  playableTimelineDurationSeconds: number;
  overhangTimelineDurationSeconds: number;
  overhangSourceDurationSeconds: number;
  mediaEndFraction: number;
}

export interface ClampClipToMediaDurationResult {
  nextAction: TimelineAction;
  metaPatch: Partial<ClipMeta>;
  overhang: ClipOverhang;
}

export interface ConvertOverhangToHoldResult {
  clipId: string;
  holdClipId: string;
  trackId: string;
  rows: TimelineData['rows'];
  metaUpdates: Record<string, Partial<ClipMeta>>;
  clipOrderOverride: TimelineData['clipOrder'];
  overhang: ClipOverhang;
}

function getSafePositiveNumber(value: number | undefined, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback;
}

function getSafeStart(value: number | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, value) : 0;
}

export function getMediaEndFraction({
  playableTimelineDurationSeconds,
  totalTimelineDurationSeconds,
}: {
  playableTimelineDurationSeconds: number;
  totalTimelineDurationSeconds: number;
}): number {
  if (!Number.isFinite(playableTimelineDurationSeconds) || !Number.isFinite(totalTimelineDurationSeconds) || totalTimelineDurationSeconds <= 0) {
    return 1;
  }

  return Math.min(1, Math.max(0, playableTimelineDurationSeconds / totalTimelineDurationSeconds));
}

export function detectClipOverhang({
  clipMeta,
  timelineDurationSeconds,
  sourceDurationSeconds,
}: {
  clipMeta: Pick<ClipMeta, 'from' | 'speed'>;
  timelineDurationSeconds: number;
  sourceDurationSeconds?: number | null;
}): ClipOverhang | null {
  const safeSourceDuration = getSafePositiveNumber(sourceDurationSeconds ?? undefined, 0);
  if (safeSourceDuration <= 0) {
    return null;
  }

  const totalTimelineDurationSeconds = Math.max(
    MIN_TIMELINE_DURATION_SECONDS,
    Number.isFinite(timelineDurationSeconds) ? timelineDurationSeconds : 0,
  );
  const safeFrom = getSafeStart(clipMeta.from);
  const safeSpeed = getSafePositiveNumber(clipMeta.speed, 1);
  const remainingSourceDurationSeconds = Math.max(0, safeSourceDuration - safeFrom);
  const playableTimelineDurationSeconds = Math.max(
    MIN_TIMELINE_DURATION_SECONDS,
    remainingSourceDurationSeconds / safeSpeed,
  );
  const overhangTimelineDurationSeconds = totalTimelineDurationSeconds - playableTimelineDurationSeconds;
  if (overhangTimelineDurationSeconds <= OVERHANG_EPSILON) {
    return null;
  }

  return {
    sourceDurationSeconds: safeSourceDuration,
    totalTimelineDurationSeconds,
    playableTimelineDurationSeconds,
    overhangTimelineDurationSeconds,
    overhangSourceDurationSeconds: overhangTimelineDurationSeconds * safeSpeed,
    mediaEndFraction: getMediaEndFraction({
      playableTimelineDurationSeconds,
      totalTimelineDurationSeconds,
    }),
  };
}

export function clampClipToMediaDuration({
  action,
  clipMeta,
  sourceDurationSeconds,
}: {
  action: TimelineAction;
  clipMeta: Pick<ClipMeta, 'from' | 'speed'>;
  sourceDurationSeconds?: number | null;
}): ClampClipToMediaDurationResult | null {
  const overhang = detectClipOverhang({
    clipMeta,
    timelineDurationSeconds: action.end - action.start,
    sourceDurationSeconds,
  });
  if (!overhang) {
    return null;
  }

  const safeFrom = getSafeStart(clipMeta.from);
  const safeSpeed = getSafePositiveNumber(clipMeta.speed, 1);

  return {
    nextAction: {
      ...action,
      end: action.start + overhang.playableTimelineDurationSeconds,
    },
    metaPatch: {
      to: Math.max(safeFrom, safeFrom + overhang.playableTimelineDurationSeconds * safeSpeed),
    },
    overhang,
  };
}

export function convertOverhangToHold({
  current,
  clipId,
  sourceDurationSeconds,
  frameRate,
}: {
  current: TimelineData;
  clipId: string;
  sourceDurationSeconds?: number | null;
  frameRate?: number | null;
}): ConvertOverhangToHoldResult | null {
  const clipMeta = current.meta[clipId];
  if (!clipMeta?.asset) {
    return null;
  }

  const sourceRow = current.rows.find((row) => row.actions.some((action) => action.id === clipId));
  if (!sourceRow) {
    return null;
  }

  const sourceIndex = sourceRow.actions.findIndex((action) => action.id === clipId);
  if (sourceIndex < 0) {
    return null;
  }

  const sourceAction = sourceRow.actions[sourceIndex];
  const clamped = clampClipToMediaDuration({
    action: sourceAction,
    clipMeta,
    sourceDurationSeconds,
  });
  if (!clamped) {
    return null;
  }

  const holdClipId = getNextClipId(current.meta);
  const safeFrameRate = getSafePositiveNumber(frameRate ?? undefined, DEFAULT_HOLD_FRAME_RATE);
  const frameDurationSeconds = 1 / safeFrameRate;
  const holdSourceStart = Math.max(0, clamped.overhang.sourceDurationSeconds - frameDurationSeconds);
  const holdAction: TimelineAction = {
    id: holdClipId,
    start: clamped.nextAction.end,
    end: sourceAction.end,
    effectId: `effect-${holdClipId}`,
  };
  const holdMeta: ClipMeta = {
    asset: clipMeta.asset,
    track: clipMeta.track,
    clipType: 'hold',
    hold: clamped.overhang.overhangTimelineDurationSeconds,
    from: holdSourceStart,
    to: clamped.overhang.sourceDurationSeconds,
    speed: 1,
    volume: 0,
    opacity: clipMeta.opacity,
    x: clipMeta.x,
    y: clipMeta.y,
    width: clipMeta.width,
    height: clipMeta.height,
    cropTop: clipMeta.cropTop,
    cropBottom: clipMeta.cropBottom,
    cropLeft: clipMeta.cropLeft,
    cropRight: clipMeta.cropRight,
  };

  const rows = current.rows.map((row) => {
    if (row.id !== sourceRow.id) {
      return row;
    }

    const actions = row.actions.flatMap((action, index) => {
      if (index !== sourceIndex) {
        return [action];
      }

      return [clamped.nextAction, holdAction];
    });

    return { ...row, actions };
  });

  const clipOrderOverride = updateClipOrder(current.clipOrder, sourceRow.id, (ids) => {
    const insertionIndex = ids.indexOf(clipId);
    if (insertionIndex < 0) {
      return [...ids, holdClipId];
    }

    return [...ids.slice(0, insertionIndex + 1), holdClipId, ...ids.slice(insertionIndex + 1)];
  });

  return {
    clipId,
    holdClipId,
    trackId: sourceRow.id,
    rows,
    metaUpdates: {
      [clipId]: clamped.metaPatch,
      [holdClipId]: holdMeta,
    },
    clipOrderOverride,
    overhang: clamped.overhang,
  };
}
