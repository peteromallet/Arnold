import type { TimelineEditMutation } from '@/tools/video-editor/hooks/useTimelineCommit';
import { getCompatibleTrackId, updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { resolveOverlaps } from '@/tools/video-editor/lib/resolve-overlaps';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { ValidatedSequenceDraft } from '@/tools/video-editor/sequences/validation';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

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
};

const cloneParams = (
  params: ValidatedSequenceDraft['params'],
): Record<string, unknown> => ({ ...params });

const createSequenceClipMeta = (
  trackId: string,
  draft: ValidatedSequenceDraft,
): ClipMeta => ({
  track: trackId,
  clipType: draft.clipType,
  hold: draft.hold,
  params: cloneParams(draft.params),
});

const addActionToRow = (
  rows: TimelineRow[],
  trackId: string,
  action: TimelineAction,
): TimelineRow[] => rows.map((row) => (
  row.id === trackId
    ? { ...row, actions: [...row.actions, action] }
    : row
));

const replaceActionInRows = (
  rows: TimelineRow[],
  trackId: string,
  action: TimelineAction,
  removedClipId: string,
): TimelineRow[] => rows.map((row) => {
  if (row.id !== trackId) return row;
  return {
    ...row,
    actions: [
      ...row.actions.filter((candidate) => candidate.id !== removedClipId),
      action,
    ],
  };
});

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
  const trackId = getCompatibleTrackId(
    current.tracks,
    options.preferredTrackId ?? undefined,
    'visual',
    options.selectedTrackId ?? null,
  );
  if (!trackId) {
    return { ok: false, error: 'no_visual_track' };
  }

  const clipId = getNextClipId(current.meta);
  const start = Math.max(0, options.at ?? 0);
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
  const selectedClipId = options.selectedClipId;
  if (!selectedClipId) {
    return { ok: false, error: 'replace_target_missing' };
  }
  const target = findAction(current.rows, selectedClipId);
  const targetMeta = current.meta[selectedClipId];
  if (!target || !targetMeta) {
    return { ok: false, error: 'replace_target_missing' };
  }
  const targetTrack = current.tracks.find((track) => track.id === target.row.id);
  if (targetTrack?.kind !== 'visual') {
    return { ok: false, error: 'replace_target_not_visual' };
  }

  const clipId = getNextClipId(current.meta);
  const action: TimelineAction = {
    id: clipId,
    start: target.action.start,
    end: target.action.start + draft.hold,
    effectId: `effect-${clipId}`,
  };
  const clipMeta = createSequenceClipMeta(target.row.id, draft);
  const nextMetaBase = {
    ...current.meta,
    [clipId]: clipMeta,
  };
  delete nextMetaBase[selectedClipId];
  const rowsWithReplacement = replaceActionInRows(
    current.rows,
    target.row.id,
    action,
    selectedClipId,
  );
  const { rows, metaPatches, action: resolvedAction } = resolveInsertedRows(
    rowsWithReplacement,
    target.row.id,
    clipId,
    nextMetaBase,
  );
  const resolvedHold = resolvedAction
    ? Math.max(0.05, resolvedAction.end - resolvedAction.start)
    : draft.hold;
  const clipOrderOverride = updateClipOrder(
    current.clipOrder,
    target.row.id,
    (ids) => [...ids.filter((id) => id !== selectedClipId && id !== clipId), clipId],
  );

  return {
    ok: true,
    clipId,
    selectedClipId: clipId,
    selectedTrackId: target.row.id,
    mutation: {
      type: 'rows',
      rows,
      metaDeletes: [selectedClipId],
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
