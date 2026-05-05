import { updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils.ts';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';

function cloneClipMeta(meta: ClipMeta, assetKey: string, trackId: string): ClipMeta {
  return {
    ...meta,
    asset: assetKey,
    track: trackId,
    ...(meta.text ? { text: { ...meta.text } } : {}),
    ...(meta.entrance ? { entrance: { ...meta.entrance } } : {}),
    ...(meta.exit ? { exit: { ...meta.exit } } : {}),
    ...(meta.continuous ? { continuous: { ...meta.continuous } } : {}),
    ...(meta.transition ? { transition: { ...meta.transition } } : {}),
    ...(meta.effects
      ? {
          effects: Array.isArray(meta.effects)
            ? meta.effects.map((effect) => ({ ...effect }))
            : { ...meta.effects },
        }
      : {}),
  };
}

export interface DuplicateClipEditResult {
  clipId: string;
  trackId: string;
  rows: TimelineData['rows'];
  metaUpdates: Record<string, Partial<ClipMeta>>;
  clipOrderOverride: TimelineData['clipOrder'];
}

export function buildDuplicateClipEdit(
  current: TimelineData,
  sourceClipId: string,
  assetKey: string,
): DuplicateClipEditResult | null {
  const sourceMeta = current.meta[sourceClipId];
  if (!sourceMeta) {
    return null;
  }

  const sourceRow = current.rows.find((row) => row.actions.some((action) => action.id === sourceClipId));
  if (!sourceRow) {
    return null;
  }

  const sourceIndex = sourceRow.actions.findIndex((action) => action.id === sourceClipId);
  if (sourceIndex < 0) {
    return null;
  }

  const sourceAction = sourceRow.actions[sourceIndex];
  const duration = Math.max(0.05, sourceAction.end - sourceAction.start);
  const clipId = getNextClipId(current.meta);
  const duplicateAction = {
    ...sourceAction,
    id: clipId,
    start: sourceAction.end,
    end: sourceAction.end + duration,
    effectId: `effect-${clipId}`,
  };

  const rows = current.rows.map((row) => {
    if (row.id !== sourceRow.id) {
      return row;
    }

    const actions = row.actions.flatMap((action, index) => {
      if (index < sourceIndex) {
        return [action];
      }
      if (index === sourceIndex) {
        return [action, duplicateAction];
      }

      return [{
        ...action,
        start: action.start + duration,
        end: action.end + duration,
      }];
    });

    return { ...row, actions };
  });

  const clipOrderOverride = updateClipOrder(current.clipOrder, sourceRow.id, (ids) => {
    const insertionIndex = ids.indexOf(sourceClipId);
    if (insertionIndex < 0) {
      return [...ids, clipId];
    }

    return [...ids.slice(0, insertionIndex + 1), clipId, ...ids.slice(insertionIndex + 1)];
  });

  return {
    clipId,
    trackId: sourceRow.id,
    rows,
    metaUpdates: {
      [clipId]: cloneClipMeta(sourceMeta, assetKey, sourceRow.id),
    },
    clipOrderOverride,
  };
}
