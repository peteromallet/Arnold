import { useCallback, useRef } from 'react';
import { buildRowTrackPatches } from '@/tools/video-editor/lib/coordinate-utils.ts';
import type {
  ClipEdgeResizeContext,
  ClipEdgeResizeUpdate,
  ResizeDir,
} from '@/tools/video-editor/lib/resize-math.ts';
import { getSourceTime, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import { resolveOverlaps } from '@/tools/video-editor/lib/resolve-overlaps.ts';
import { ensureGroupContiguity } from '@/tools/video-editor/lib/shot-group-contiguity.ts';
import type { TimelineApplyEdit } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import type { TrackKind } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

interface ResizeStartTarget {
  action: TimelineAction;
  row: TimelineRow;
  dir: ResizeDir;
}

export interface ClipEdgeResizeSession {
  pointerId: number;
  rowId: string;
  clipId: string;
  edge: ResizeDir;
  cursorOffsetPx: number;
  initialBoundaryTime: number;
  context: ClipEdgeResizeContext;
  siblingTimes: number[];
}

export interface ClipEdgeResizeEndTarget {
  session: ClipEdgeResizeSession;
  updates: ClipEdgeResizeUpdate[];
  cancelled: boolean;
}

interface ResizeStartState {
  start: number;
  from: number;
  to: number;
  speed: number;
  trackKind: TrackKind;
  assetDuration?: number;
}

export interface UseClipResizeArgs {
  dataRef: React.MutableRefObject<TimelineData | null>;
  applyEdit: TimelineApplyEdit;
}

export interface UseClipResizeResult {
  onActionResizeStart: (params: ResizeStartTarget) => void;
  onClipEdgeResizeEnd: (params: ClipEdgeResizeEndTarget) => void;
}

const getTrackKind = (
  current: TimelineData,
  rowId: string,
  fallbackTrackId?: string,
): TrackKind => {
  return current.tracks.find((track) => track.id === rowId)?.kind
    ?? current.tracks.find((track) => track.id === fallbackTrackId)?.kind
    ?? 'visual';
};

const getAssetDuration = (
  current: TimelineData,
  clipMeta: ClipMeta,
): number | undefined => {
  if (!clipMeta.asset) return undefined;
  return current.resolvedConfig.registry[clipMeta.asset]?.duration
    ?? current.registry.assets[clipMeta.asset]?.duration;
};

const getResolvedAction = (
  rows: TimelineRow[],
  rowId: string,
  actionId: string,
): TimelineAction | undefined => {
  return rows
    .find((candidate) => candidate.id === rowId)
    ?.actions.find((candidate) => candidate.id === actionId);
};

const getResizeStartState = (
  current: TimelineData,
  action: TimelineAction,
  rowId: string,
  clipMeta: ClipMeta,
): ResizeStartState => {
  const from = clipMeta.from ?? 0;
  const speed = clipMeta.speed ?? 1;
  return {
    start: action.start,
    from,
    to: getSourceTime({ from, start: action.start, speed }, action.end),
    speed,
    trackKind: getTrackKind(current, rowId, clipMeta.track),
    assetDuration: getAssetDuration(current, clipMeta),
  };
};

const mergeMetaUpdates = (
  ...patchSets: Array<Record<string, Partial<ClipMeta>>>
): Record<string, Partial<ClipMeta>> => {
  const merged: Record<string, Partial<ClipMeta>> = {};
  for (const patchSet of patchSets) {
    for (const [clipId, patch] of Object.entries(patchSet)) {
      merged[clipId] = { ...merged[clipId], ...patch };
    }
  }
  return merged;
};

function computeClipResizeMetaPatch(
  clipMeta: ClipMeta,
  origin: ResizeStartState,
  newStart: number,
  newEnd: number,
  dir: ResizeDir,
): Partial<ClipMeta> {
  const resolvedDuration = newEnd - newStart;
  if (resolvedDuration <= 0) return {};

  if (typeof clipMeta.hold === 'number') {
    return { hold: resolvedDuration };
  }

  if (origin.trackKind === 'visual') {
    if (dir === 'left') {
      const from = Math.max(0, origin.from + (newStart - origin.start) * origin.speed);
      return {
        from,
        to: origin.to,
        speed: (origin.to - from) / resolvedDuration,
      };
    }
    return {
      from: origin.from,
      to: origin.to,
      speed: (origin.to - origin.from) / resolvedDuration,
    };
  }

  const from = Math.max(0, origin.from + (newStart - origin.start) * origin.speed);
  const unclampedTo = from + resolvedDuration * origin.speed;
  return {
    from,
    to: typeof origin.assetDuration === 'number'
      ? Math.min(origin.assetDuration, unclampedTo)
      : unclampedTo,
  };
}

const applyActionUpdates = (
  rows: TimelineRow[],
  rowId: string,
  updates: ClipEdgeResizeUpdate[],
): TimelineRow[] => {
  const updatesByClipId = new Map(updates.map((update) => [update.clipId, update]));
  return rows.map((row) => {
    if (row.id !== rowId) return row;
    return {
      ...row,
      actions: row.actions.map((action) => {
        const update = updatesByClipId.get(action.id);
        return update ? { ...action, start: update.start, end: update.end } : action;
      }),
    };
  });
};

const getUpdateByClipId = (
  updates: ClipEdgeResizeUpdate[],
  clipId: string,
): ClipEdgeResizeUpdate | undefined => updates.find((update) => update.clipId === clipId);

const getResizeOrigin = (
  current: TimelineData,
  resizeStartRef: Record<string, ResizeStartState>,
  rowId: string,
  clipId: string,
): { action: TimelineAction; clipMeta: ClipMeta; origin: ResizeStartState } | null => {
  const action = getResolvedAction(current.rows, rowId, clipId);
  const clipMeta = current.meta[clipId];
  if (!action || !clipMeta) {
    return null;
  }

  return {
    action,
    clipMeta,
    origin: resizeStartRef[clipId] ?? getResizeStartState(current, action, rowId, clipMeta),
  };
};

export function useClipResize({
  dataRef,
  applyEdit,
}: UseClipResizeArgs): UseClipResizeResult {
  const resizeStartRef = useRef<Record<string, ResizeStartState>>({});
  const resizeTransactionIdRef = useRef<Record<string, string>>({});

  const clearResizeTracking = useCallback((clipId: string) => {
    delete resizeStartRef.current[clipId];
    delete resizeTransactionIdRef.current[clipId];
  }, []);

  const onActionResizeStart = useCallback(({ action, row, dir }: ResizeStartTarget) => {
    if (action.id.startsWith('uploading-')) return;
    const current = dataRef.current;
    const clipMeta = current?.meta[action.id];
    if (!current || !clipMeta || typeof clipMeta.hold === 'number') {
      resizeTransactionIdRef.current[action.id] = crypto.randomUUID();
      if (current && clipMeta) {
        resizeStartRef.current[action.id] = {
          start: action.start,
          from: 0,
          to: action.end - action.start,
          speed: 1,
          trackKind: getTrackKind(current, row.id, clipMeta.track),
        };
      }
      return;
    }

    resizeStartRef.current[action.id] = getResizeStartState(current, action, row.id, clipMeta);
    resizeTransactionIdRef.current[action.id] = crypto.randomUUID();
    void dir;
  }, [dataRef]);

  const onClipEdgeResizeEnd = useCallback(({
    session,
    updates,
    cancelled,
  }: ClipEdgeResizeEndTarget) => {
    if (session.clipId.startsWith('uploading-')) {
      clearResizeTracking(session.clipId);
      return;
    }
    const current = dataRef.current;
    if (!current) {
      clearResizeTracking(session.clipId);
      return;
    }

    const transactionId = resizeTransactionIdRef.current[session.clipId] ?? crypto.randomUUID();
    if (cancelled) {
      clearResizeTracking(session.clipId);
      return;
    }

    const primaryUpdate = getUpdateByClipId(updates, session.clipId);
    const primary = getResizeOrigin(current, resizeStartRef.current, session.rowId, session.clipId);
    if (!primaryUpdate || !primary) {
      clearResizeTracking(session.clipId);
      return;
    }

    if (session.context.kind === 'group') {
      const updatedRows = applyActionUpdates(current.rows, session.rowId, updates);
      let nextRows = ensureGroupContiguity(updatedRows, current.config.pinnedShotGroups);

      // Resolve overlaps between group clips and non-group siblings on the same row.
      // The resized group clip may extend into non-group clips; resolveOverlaps trims it to fit.
      const groupClipIds = new Set(session.context.groupClipIds);
      let overlapMetaPatches: Record<string, Partial<ClipMeta>> = {};
      for (const update of updates) {
        if (!groupClipIds.has(update.clipId)) continue;
        const { rows: resolved, metaPatches } = resolveOverlaps(
          nextRows,
          session.rowId,
          update.clipId,
          current.meta,
        );
        nextRows = resolved;
        overlapMetaPatches = { ...overlapMetaPatches, ...metaPatches };
      }

      const perClipMetaUpdates: Record<string, Partial<ClipMeta>> = {};
      for (const update of updates) {
        const clip = getResizeOrigin(current, resizeStartRef.current, session.rowId, update.clipId);
        if (!clip) {
          continue;
        }
        // Use resolved positions for meta calculation
        const resolvedAction = getResolvedAction(nextRows, session.rowId, update.clipId);
        const effectiveStart = resolvedAction?.start ?? update.start;
        const effectiveEnd = resolvedAction?.end ?? update.end;
        // The dragged clip is actually resized; other clips are just shifted
        const clipEdge = update.clipId === session.clipId ? session.edge : session.edge;
        perClipMetaUpdates[update.clipId] = {
          track: session.rowId,
          ...computeClipResizeMetaPatch(
            clip.clipMeta,
            clip.origin,
            effectiveStart,
            effectiveEnd,
            clipEdge,
          ),
        };
      }

      applyEdit({
        type: 'rows',
        rows: nextRows,
        metaUpdates: mergeMetaUpdates(
          {
            ...buildRowTrackPatches(nextRows),
          },
          overlapMetaPatches,
          perClipMetaUpdates,
        ),
      }, { transactionId });

      clearResizeTracking(session.clipId);
      return;
    }

    const nextRows = applyActionUpdates(current.rows, session.rowId, [primaryUpdate]);
    const { rows: resolvedRows, metaPatches: overlapPatches } = resolveOverlaps(
      nextRows,
      session.rowId,
      session.clipId,
      current.meta,
    );
    const resolvedAction = getResolvedAction(resolvedRows, session.rowId, session.clipId);
    const effectiveStart = resolvedAction?.start ?? primaryUpdate.start;
    const effectiveEnd = resolvedAction?.end ?? primaryUpdate.end;
    const primaryPatch = computeClipResizeMetaPatch(
      primary.clipMeta,
      primary.origin,
      effectiveStart,
      effectiveEnd,
      session.edge,
    );

    applyEdit({
      type: 'rows',
      rows: resolvedRows,
      metaUpdates: mergeMetaUpdates(
        {
          ...buildRowTrackPatches(resolvedRows),
          [session.clipId]: { track: session.rowId, ...primaryPatch },
        },
        overlapPatches,
      ),
    }, { transactionId });

    clearResizeTracking(session.clipId);
  }, [applyEdit, clearResizeTracking, dataRef]);

  return {
    onActionResizeStart,
    onClipEdgeResizeEnd,
  };
}
