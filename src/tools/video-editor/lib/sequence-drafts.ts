import type { TimelineEditMutation } from '@/tools/video-editor/hooks/useTimelineCommit.ts';
import { createClipMetaFromDescriptor } from '@/tools/video-editor/clip-types/runtime.ts';
import {
  findNearestFreeTrack,
  getCompatibleTrackId,
  trySnapToEdge,
  updateClipOrder,
} from '@/tools/video-editor/lib/coordinate-utils.ts';
import { resolveOverlaps } from '@/tools/video-editor/lib/resolve-overlaps.ts';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { ValidatedSequenceDraft } from '@/tools/video-editor/sequences/validation.ts';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

export type SequenceDraftEditError =
  | 'no_visual_track'
  | 'replace_target_missing'
  | 'replace_target_not_visual';

export type SequenceDraftEditResult =
  | {
      ok: true;
      clipId: string;
      mutation: Extract<TimelineEditMutation, { type: 'rows' }>;
      selectedClipId: string;
      selectedTrackId: string;
    }
  | {
      ok: false;
      error: SequenceDraftEditError;
    };

export type BuildInsertSequenceDraftOptions = {
  at?: number;
  selectedTrackId?: string | null;
  preferredTrackId?: string | null;
};

export type BuildReplaceSequenceDraftOptions = {
  selectedClipId: string | null | undefined;
  selectedClipIds?: Iterable<string> | null;
};

const cloneParams = (
  params: ValidatedSequenceDraft['params'],
): Record<string, unknown> => ({ ...params });

const createSequenceClipMeta = (
  trackId: string,
  draft: ValidatedSequenceDraft,
): ClipMeta => {
  // Try the descriptor-driven path first (handles built-in/trusted clip
  // types and applies their defaults). For brand-new code-path components
  // whose unique clipType isn't yet in the static registry, fall back to a
  // minimal meta so the inserted clip preserves its clipType + params
  // instead of silently downgrading to the 'hold' fallback.
  const descriptorMeta = createClipMetaFromDescriptor({
    clipType: draft.clipType,
    trackId,
    clipOverrides: { hold: draft.hold },
    params: cloneParams(draft.params),
  }) as ClipMeta | null;
  if (descriptorMeta) return descriptorMeta;
  return {
    clipType: draft.clipType,
    track: trackId,
    hold: draft.hold,
    params: cloneParams(draft.params),
  } as unknown as ClipMeta;
};

const addActionToRow = (
  rows: TimelineRow[],
  trackId: string,
  action: TimelineAction,
): TimelineRow[] => rows.map((row) => (
  row.id === trackId
    ? { ...row, actions: [...row.actions, action] }
    : row
));

const findAction = (
  rows: TimelineRow[],
  clipId: string,
): { row: TimelineRow; action: TimelineAction } | null => {
  for (const row of rows) {
    const action = row.actions.find((candidate) => candidate.id === clipId);
    if (action) {
      return { row, action };
    }
  }
  return null;
};

const uniqueSelectedClipIds = (
  primaryClipId: string | null | undefined,
  clipIds: Iterable<string> | null | undefined,
): string[] => {
  const selected = new Set<string>();
  if (clipIds) {
    for (const clipId of clipIds) {
      if (clipId) selected.add(clipId);
    }
  }
  if (primaryClipId) selected.add(primaryClipId);
  return [...selected];
};

const resolveInsertedRows = (
  rows: TimelineRow[],
  trackId: string,
  clipId: string,
  meta: Record<string, ClipMeta>,
): { rows: TimelineRow[]; metaPatches: Record<string, Partial<ClipMeta>>; action: TimelineAction | undefined } => {
  const { rows: nextRows, metaPatches } = resolveOverlaps(rows, trackId, clipId, meta);
  const action = nextRows
    .find((row) => row.id === trackId)
    ?.actions.find((candidate) => candidate.id === clipId);
  return { rows: nextRows, metaPatches, action };
};

export const buildInsertSequenceDraftEdit = (
  current: TimelineData,
  draft: ValidatedSequenceDraft,
  options: BuildInsertSequenceDraftOptions = {},
): SequenceDraftEditResult => {
  let trackId = getCompatibleTrackId(
    current.tracks,
    options.preferredTrackId ?? undefined,
    'visual',
    options.selectedTrackId ?? null,
  );
  if (!trackId) {
    return { ok: false, error: 'no_visual_track' };
  }

  const clipId = getNextClipId(current.meta);
  const requestedStart = Math.max(0, options.at ?? 0);
  const snapResult = trySnapToEdge(current.rows, trackId, requestedStart, draft.hold);
  const start = snapResult.time;
  if (!snapResult.snapped) {
    trackId = findNearestFreeTrack(
      current.tracks,
      current.rows,
      trackId,
      'visual',
      start,
      draft.hold,
    ) ?? trackId;
  }
  const action: TimelineAction = {
    id: clipId,
    start,
    end: start + draft.hold,
    effectId: `effect-${clipId}`,
  };
  const clipMeta = createSequenceClipMeta(trackId, draft);
  const metaForResolve = {
    ...current.meta,
    [clipId]: clipMeta,
  };
  const rowsWithClip = addActionToRow(current.rows, trackId, action);
  const { rows, metaPatches, action: resolvedAction } = resolveInsertedRows(
    rowsWithClip,
    trackId,
    clipId,
    metaForResolve,
  );
  const resolvedHold = resolvedAction
    ? Math.max(0.05, resolvedAction.end - resolvedAction.start)
    : draft.hold;
  const clipOrderOverride = updateClipOrder(
    current.clipOrder,
    trackId,
    (ids) => [...ids.filter((id) => id !== clipId), clipId],
  );

  return {
    ok: true,
    clipId,
    selectedClipId: clipId,
    selectedTrackId: trackId,
    mutation: {
      type: 'rows',
      rows,
      metaUpdates: {
        ...metaPatches,
        [clipId]: {
          ...clipMeta,
          hold: resolvedHold,
        },
      },
      clipOrderOverride,
    },
  };
};

export const buildReplaceSequenceDraftEdit = (
  current: TimelineData,
  draft: ValidatedSequenceDraft,
  options: BuildReplaceSequenceDraftOptions,
): SequenceDraftEditResult => {
  const selectedClipIds = uniqueSelectedClipIds(options.selectedClipId, options.selectedClipIds);
  if (selectedClipIds.length === 0) {
    return { ok: false, error: 'replace_target_missing' };
  }

  const targets = selectedClipIds.map((clipId) => {
    const found = findAction(current.rows, clipId);
    const meta = current.meta[clipId];
    return found && meta ? { clipId, ...found, meta } : null;
  });
  if (targets.some((target) => target === null)) {
    return { ok: false, error: 'replace_target_missing' };
  }
  const concreteTargets = targets.filter((target): target is NonNullable<typeof target> => target !== null);
  const hasNonVisualTarget = concreteTargets.some((target) => (
    current.tracks.find((track) => track.id === target.row.id)?.kind !== 'visual'
  ));
  if (hasNonVisualTarget) {
    return { ok: false, error: 'replace_target_not_visual' };
  }

  const primaryTarget = concreteTargets.find((target) => target.clipId === options.selectedClipId)
    ?? concreteTargets[0];
  const earliestStart = Math.min(...concreteTargets.map((target) => target.action.start));
  const removedClipIds = new Set(concreteTargets.map((target) => target.clipId));
  const clipId = getNextClipId(current.meta);
  const action: TimelineAction = {
    id: clipId,
    start: earliestStart,
    end: earliestStart + draft.hold,
    effectId: `effect-${clipId}`,
  };
  const clipMeta = createSequenceClipMeta(primaryTarget.row.id, draft);
  const nextMetaBase = {
    ...current.meta,
    [clipId]: clipMeta,
  };
  removedClipIds.forEach((removedClipId) => {
    delete nextMetaBase[removedClipId];
  });
  const rowsWithReplacement = current.rows.map((row) => ({
    ...row,
    actions: [
      ...row.actions.filter((candidate) => !removedClipIds.has(candidate.id)),
      ...(row.id === primaryTarget.row.id ? [action] : []),
    ],
  }));
  const { rows, metaPatches, action: resolvedAction } = resolveInsertedRows(
    rowsWithReplacement,
    primaryTarget.row.id,
    clipId,
    nextMetaBase,
  );
  const resolvedHold = resolvedAction
    ? Math.max(0.05, resolvedAction.end - resolvedAction.start)
    : draft.hold;
  const clipOrderOverride = current.tracks.reduce((order, track) => (
    updateClipOrder(
      order,
      track.id,
      (ids) => [
        ...ids.filter((id) => !removedClipIds.has(id) && id !== clipId),
        ...(track.id === primaryTarget.row.id ? [clipId] : []),
      ],
    )
  ), current.clipOrder);

  return {
    ok: true,
    clipId,
    selectedClipId: clipId,
    selectedTrackId: primaryTarget.row.id,
    mutation: {
      type: 'rows',
      rows,
      metaDeletes: [...removedClipIds],
      metaUpdates: {
        ...metaPatches,
        [clipId]: {
          ...clipMeta,
          hold: resolvedHold,
        },
      },
      clipOrderOverride,
    },
  };
};
