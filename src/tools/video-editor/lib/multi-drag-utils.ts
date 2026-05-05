import { getConfigSignature, getStableConfigSignature } from '@/tools/video-editor/lib/config-utils.ts';
import { addTrack } from '@/tools/video-editor/lib/editor-utils.ts';
import type { PinnedGroupKey } from '@/tools/video-editor/lib/pinned-group-projection.ts';
import { getSourceTime, type ClipMeta, type ClipOrderMap, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';
import type { PinnedShotGroup, ResolvedTimelineConfig, TrackKind } from '@/tools/video-editor/types/index.ts';
import { findNearestFreeTrack, moveClipBetweenTracks, trySnapToEdge } from '@/tools/video-editor/lib/coordinate-utils.ts';
import {
  findBestGroupStart,
  type GroupExtent,
} from '@/tools/video-editor/lib/resolve-overlaps.ts';

// ── Types ────────────────────────────────────────────────────────────

export interface ClipOffset {
  clipId: string;
  rowId: string;
  /** Time delta from anchor clip's initial start. */
  deltaTime: number;
  initialStart: number;
  initialEnd: number;
}

export interface PlannedMove {
  kind: 'clip';
  clipId: string;
  sourceRowId: string;
  targetRowId: string;
  newStart: number;
}

/**
 * Soft-tag model: grouped drag is expanded into per-clip PlannedMove entries at
 * planning time. There is no distinct group-move plan anymore — cohesion is an
 * emergent property of moving all members by the same delta.
 */
export type MultiDragMove = PlannedMove;

export interface MultiDragResult {
  canMove: boolean;
  moves: MultiDragMove[];
}

/** Lightweight rect for rendering secondary ghost indicators. */
export interface GhostRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

const roundConfigValue = (value: number): number => Math.round(value * 100) / 100;

export function buildAugmentedData(
  data: TimelineData,
  kind: TrackKind,
  insertAtTop: boolean,
): { augmented: TimelineData; newTrackId: string } | null {
  const augmentedResolvedConfig = addTrack(data.resolvedConfig, kind, insertAtTop ? 0 : undefined);
  const newTrack = augmentedResolvedConfig.tracks.find((track) => {
    return !data.resolvedConfig.tracks.some((existingTrack) => existingTrack.id === track.id);
  });

  if (!newTrack) {
    return null;
  }

  const nextConfig = {
    ...data.config,
    tracks: augmentedResolvedConfig.tracks.map((track) => ({ ...track })),
  };
  const nextRows = insertAtTop
    ? [{ id: newTrack.id, actions: [] }, ...data.rows]
    : [...data.rows, { id: newTrack.id, actions: [] }];

  return {
    augmented: {
      ...data,
      config: nextConfig,
      resolvedConfig: augmentedResolvedConfig,
      rows: nextRows,
      tracks: augmentedResolvedConfig.tracks,
      clipOrder: {
        ...data.clipOrder,
        [newTrack.id]: [],
      },
      signature: getConfigSignature(augmentedResolvedConfig),
      stableSignature: getStableConfigSignature(nextConfig, data.registry),
    },
    newTrackId: newTrack.id,
  };
}

export function buildConfigFromDragResult(
  baseConfig: ResolvedTimelineConfig,
  baseMeta: Record<string, ClipMeta>,
  nextRows: TimelineRow[],
  metaUpdates: Record<string, Partial<ClipMeta>>,
  pinnedShotGroups?: PinnedShotGroup[],
): ResolvedTimelineConfig & { pinnedShotGroups?: PinnedShotGroup[] } {
  const mergedMeta: Record<string, ClipMeta> = Object.fromEntries(
    Object.entries(baseMeta).map(([clipId, clipMeta]) => [
      clipId,
      {
        ...clipMeta,
        ...metaUpdates[clipId],
      },
    ]),
  );

  for (const [clipId, patch] of Object.entries(metaUpdates)) {
    if (!mergedMeta[clipId]) {
      mergedMeta[clipId] = patch as ClipMeta;
    }
  }

  const positions = new Map<string, { at: number; track: string; duration: number }>();
  for (const row of nextRows) {
    for (const action of row.actions) {
      positions.set(action.id, {
        at: action.start,
        track: row.id,
        duration: action.end - action.start,
      });
    }
  }

  const nextClips = baseConfig.clips.reduce<ResolvedTimelineConfig['clips']>((acc, clip) => {
      const position = positions.get(clip.id);
      const clipMeta = mergedMeta[clip.id];
      if (!position || !clipMeta) {
        return acc;
      }

      const nextClip = {
        ...clip,
        at: roundConfigValue(position.at),
        track: position.track,
      };

      if (typeof clipMeta.hold === 'number') {
        delete nextClip.from;
        delete nextClip.to;
        delete nextClip.speed;
        acc.push({
          ...nextClip,
          hold: roundConfigValue(position.duration),
        });
        return acc;
      }

      const speed = clipMeta.speed ?? 1;
      const from = clipMeta.from ?? 0;
      delete nextClip.hold;
      acc.push({
        ...nextClip,
        speed: clipMeta.speed,
        from: roundConfigValue(from),
        to: roundConfigValue(getSourceTime({ from, start: position.at, speed }, position.at + position.duration)),
      });
      return acc;
    }, []);

  return {
    ...baseConfig,
    clips: nextClips,
    ...(pinnedShotGroups && pinnedShotGroups.length > 0 ? { pinnedShotGroups } : {}),
  };
}

// ── Planning ─────────────────────────────────────────────────────────

/**
 * Given a set of dragged clips, an anchor target row, and a time delta,
 * compute where every clip should land. Returns `canMove: false` if any
 * clip would go out of bounds or land on an incompatible track kind.
 *
 * Works for both same-track and cross-track drags — the caller just
 * provides the anchor's resolved target row and time.
 */
export function planMultiDragMoves(
  data: TimelineData,
  clipOffsets: readonly ClipOffset[],
  anchorClipId: string,
  anchorTargetRowId: string,
  anchorSourceRowId: string,
  timeDelta: number,
  groupDragEntry?: {
    groupKey: PinnedGroupKey;
    originStart: number;
    originTrackId: string;
  },
): MultiDragResult {
  const rowIds = data.rows.map((r) => r.id);
  const trackById = new Map(data.tracks.map((t) => [t.id, t]));
  const anchorSourceIndex = rowIds.indexOf(anchorSourceRowId);
  const anchorTargetIndex = rowIds.indexOf(anchorTargetRowId);
  const trackDelta = anchorTargetIndex - anchorSourceIndex;

  if (trackDelta === 0 && timeDelta === 0) {
    return { canMove: false, moves: [] };
  }

  const moves: PlannedMove[] = [];
  const pinnedGroupClipIds = new Set<string>();

  if (groupDragEntry) {
    // Soft-tag grouped drag: validate that the target track is kind-compatible,
    // then emit per-clip moves for every group member so they all translate by
    // the same anchor delta. The group entry's trackId update happens at the
    // commit site (via pinnedShotGroupsOverride), not in multi-drag-utils.
    const sourceTrack = trackById.get(groupDragEntry.originTrackId);
    const targetTrack = trackById.get(anchorTargetRowId);
    if (!sourceTrack || !targetTrack || sourceTrack.kind !== targetTrack.kind) {
      return { canMove: false, moves: [] };
    }

    const group = data.config.pinnedShotGroups?.find((candidate) => (
      candidate.shotId === groupDragEntry.groupKey.shotId
      && candidate.trackId === groupDragEntry.groupKey.trackId
    ));

    // Collect member positions so we can compute the bounding box
    const memberPositions: Array<{ clipId: string; start: number; end: number; actualRowId: string }> = [];
    for (const memberClipId of group?.clipIds ?? []) {
      const memberOffset = clipOffsets.find((o) => o.clipId === memberClipId);
      let memberStart: number | null = null;
      let memberEnd: number | null = null;
      let actualRowId: string | null = null;
      if (memberOffset) {
        memberStart = memberOffset.initialStart;
        memberEnd = memberOffset.initialEnd;
        actualRowId = memberOffset.rowId;
      } else {
        for (const row of data.rows) {
          const action = row.actions.find((a) => a.id === memberClipId);
          if (action) {
            memberStart = action.start;
            memberEnd = action.end;
            actualRowId = row.id;
            break;
          }
        }
      }
      if (memberStart === null || memberEnd === null || actualRowId === null) continue;
      memberPositions.push({ clipId: memberClipId, start: memberStart, end: memberEnd, actualRowId });
    }

    // Compute the group's bounding box after the time delta
    const groupStart = Math.min(...memberPositions.map((m) => m.start + timeDelta));
    const groupEnd = Math.max(...memberPositions.map((m) => m.end + timeDelta));
    const groupDuration = groupEnd - groupStart;

    // Exclude group members from rows so they don't block themselves
    const memberClipIdSet = new Set(memberPositions.map((m) => m.clipId));
    const rowsWithoutGroup = data.rows.map((row) => ({
      ...row,
      actions: row.actions.filter((a) => !memberClipIdSet.has(a.id)),
    }));

    const snapResult = trySnapToEdge(
      rowsWithoutGroup,
      anchorTargetRowId,
      groupStart,
      groupDuration,
    );
    const effectiveGroupStart = snapResult.snapped ? snapResult.time : groupStart;

    // Find nearest free track for the group's bounding box.
    // Fall back to the requested target if every track is occupied — the
    // caller (commitDraggingSession) can create a new track if needed,
    // and applyMultiDragMoves will shift to the nearest gap as a last resort.
    const resolvedTargetRowId = snapResult.snapped
      ? anchorTargetRowId
      : findNearestFreeTrack(
          data.tracks,
          rowsWithoutGroup,
          anchorTargetRowId,
          sourceTrack.kind,
          effectiveGroupStart,
          groupDuration,
        ) ?? anchorTargetRowId;
    const snapDelta = effectiveGroupStart - groupStart;

    for (const member of memberPositions) {
      pinnedGroupClipIds.add(member.clipId);
      moves.push({
        kind: 'clip',
        clipId: member.clipId,
        sourceRowId: member.actualRowId,
        targetRowId: resolvedTargetRowId,
        newStart: member.start + timeDelta + snapDelta,
      });
    }
  }

  for (const offset of clipOffsets) {
    if (pinnedGroupClipIds.has(offset.clipId)) {
      continue;
    }

    const sourceIndex = rowIds.indexOf(offset.rowId);
    const targetIndex = sourceIndex + trackDelta;

    if (targetIndex < 0 || targetIndex >= rowIds.length) {
      return { canMove: false, moves: [] };
    }

    const targetRowId = rowIds[targetIndex];
    const sourceTrack = trackById.get(offset.rowId);
    const targetTrack = trackById.get(targetRowId);

    if (!sourceTrack || !targetTrack || sourceTrack.kind !== targetTrack.kind) {
      return { canMove: false, moves: [] };
    }

    moves.push({
      kind: 'clip',
      clipId: offset.clipId,
      sourceRowId: offset.rowId,
      targetRowId,
      newStart: offset.initialStart + timeDelta,
    });
  }

  return { canMove: true, moves };
}

// ── Applying ─────────────────────────────────────────────────────────

/**
 * Apply a set of planned moves to the timeline rows, resolve overlaps,
 * and update clip ordering. Returns the new rows, meta updates, and
 * clip order — ready to pass to `applyEdit`.
 */
export function applyMultiDragMoves(
  data: TimelineData,
  moves: MultiDragMove[],
): {
  nextRows: TimelineRow[];
  metaUpdates: Record<string, Partial<ClipMeta>>;
  nextClipOrder: ClipOrderMap;
} {
  const clipMoves = moves;
  const movedClipIds = new Set(clipMoves.map((m) => m.clipId));

  // Remove all moved clips from their source rows
  let nextRows = data.rows.map((row) => ({
    ...row,
    actions: row.actions.filter((a) => !movedClipIds.has(a.id)),
  }));

  // Build a map of actions to add per target row (single pass)
  const actionsToAdd = new Map<string, typeof data.rows[0]['actions']>();
  const metaUpdates: Record<string, Partial<ClipMeta>> = {};

  for (const move of clipMoves) {
    const originalRow = data.rows.find((r) => r.id === move.sourceRowId);
    const action = originalRow?.actions.find((a) => a.id === move.clipId);
    if (!action) continue;

    const duration = action.end - action.start;
    // Do NOT clamp newStart to >= 0 here — the resolver below clamps the
    // entire moved group as a unit. Per-clip clamping would collapse the
    // front of a multi-clip group (e.g. a pinned shot) onto a single point
    // when dragged toward the timeline start.
    const newStart = move.newStart;
    const movedAction = { ...action, start: newStart, end: newStart + duration };

    const existing = actionsToAdd.get(move.targetRowId) ?? [];
    existing.push(movedAction);
    actionsToAdd.set(move.targetRowId, existing);

    if (move.sourceRowId !== move.targetRowId) {
      metaUpdates[move.clipId] = { track: move.targetRowId };
    }
  }

  // Add moved actions to target rows (single pass over rows)
  nextRows = nextRows.map((row) => {
    const additions = actionsToAdd.get(row.id);
    return additions ? { ...row, actions: [...row.actions, ...additions] } : row;
  });

  // Resolve overlaps per target row
  const targetRowIds = new Set(clipMoves.map((m) => m.targetRowId));
  for (const targetRowId of targetRowIds) {
    const rowMoves = clipMoves.filter((m) => m.targetRowId === targetRowId);
    const movedClipIds = rowMoves.map((move) => move.clipId);
    const movedClipIdSet = new Set(movedClipIds);
    const movedExtent = rowMoves.reduce<GroupExtent>((range, move) => {
      const originalRow = data.rows.find((row) => row.id === move.sourceRowId);
      const action = originalRow?.actions.find((candidate) => candidate.id === move.clipId);
      const duration = action ? action.end - action.start : 0;
      const newStart = move.newStart;
      const newEnd = newStart + duration;
      return {
        start: Math.min(range.start, newStart),
        end: Math.max(range.end, newEnd),
      };
    }, {
      start: Infinity,
      end: -Infinity,
    });
    if (!Number.isFinite(movedExtent.start) || !Number.isFinite(movedExtent.end)) {
      continue;
    }
    const rowIndex = nextRows.findIndex((row) => row.id === targetRowId);
    if (rowIndex < 0) {
      continue;
    }

    const row = nextRows[rowIndex]!;
    const resolvedStart = findBestGroupStart(
      movedExtent,
      row.actions.filter((action) => !movedClipIdSet.has(action.id)),
    );
    if (resolvedStart === null) {
      continue;
    }

    const delta = resolvedStart - movedExtent.start;
    if (delta === 0) {
      continue;
    }

    const movedActionsById = new Map(
      row.actions
        .filter((action) => movedClipIdSet.has(action.id))
        .map((action) => [action.id, action]),
    );

    nextRows[rowIndex] = {
      ...row,
      actions: row.actions.map((action) => {
        if (!movedClipIdSet.has(action.id)) {
          return action;
        }

        return {
          ...action,
          start: action.start + delta,
          end: action.end + delta,
        };
      }),
    };

    for (const clipId of movedClipIds) {
      const clipMeta = data.meta[clipId];
      const movedAction = movedActionsById.get(clipId);
      if (!movedAction || !clipMeta || typeof clipMeta.hold === 'number') {
        continue;
      }

      const speed = clipMeta.speed ?? 1;
      const from = (clipMeta.from ?? 0) + delta * speed;
      metaUpdates[clipId] = {
        ...metaUpdates[clipId],
        from,
        to: from + (movedAction.end - movedAction.start) * speed,
      };
    }
  }

  // Update clip order for cross-track moves
  let nextClipOrder = data.clipOrder;
  for (const move of clipMoves) {
    if (move.sourceRowId !== move.targetRowId) {
      nextClipOrder = moveClipBetweenTracks(nextClipOrder, move.clipId, move.sourceRowId, move.targetRowId);
    }
  }

  return { nextRows, metaUpdates, nextClipOrder };
}

// ── Ghost indicators ─────────────────────────────────────────────────

/**
 * Compute ghost rectangles for secondary (non-anchor) clips during a
 * multi-drag, using the anchor's screen position as the reference point.
 */
export function computeSecondaryGhosts(
  clipOffsets: readonly ClipOffset[],
  anchorClipId: string,
  anchorSourceRowId: string,
  anchorTargetRowId: string,
  anchorGhostLeft: number,
  anchorRowTop: number,
  rowHeight: number,
  pixelsPerSecond: number,
  rowIds: readonly string[],
): GhostRect[] {
  const anchorSourceIndex = rowIds.indexOf(anchorSourceRowId);
  const anchorTargetIndex = rowIds.indexOf(anchorTargetRowId);
  const trackDelta = anchorTargetIndex - anchorSourceIndex;

  const ghosts: GhostRect[] = [];

  for (const offset of clipOffsets) {
    if (offset.clipId === anchorClipId) continue;

    const sourceIndex = rowIds.indexOf(offset.rowId);
    const targetIndex = sourceIndex + trackDelta;
    if (targetIndex < 0 || targetIndex >= rowIds.length) continue;

    const rowDelta = targetIndex - anchorTargetIndex;
    const clipDuration = offset.initialEnd - offset.initialStart;

    ghosts.push({
      left: anchorGhostLeft + (offset.deltaTime * pixelsPerSecond),
      top: anchorRowTop + (rowDelta * rowHeight) + 2,
      width: clipDuration * pixelsPerSecond,
      height: Math.max(0, rowHeight - 4),
    });
  }

  return ghosts;
}
