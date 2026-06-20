import { useCallback, useMemo } from 'react';
import { arrayMove } from '@dnd-kit/sortable';
import { addTrack, getTrackIndex } from '@/tools/video-editor/lib/editor-utils.ts';
import { DEFAULT_VIDEO_TRACKS } from '@/tools/video-editor/lib/defaults.ts';
import type { PinnedShotGroup, TrackDefinition, TrackKind } from '@/tools/video-editor/types/index.ts';
import { findNearestFreeTrack, moveClipBetweenTracks, trySnapToEdge } from '@/tools/video-editor/lib/coordinate-utils.ts';
import type { ClipMeta, TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import {
  categorizeSelection,
  findEnclosingPinnedGroup,
  findGroupForTrack,
  orderClipIdsByAt,
  resolveGroupTrackId,
  type PinnedGroupKey,
} from '@/tools/video-editor/lib/pinned-group-projection.ts';
import type { TimelineApplyEdit } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

export interface UseTimelineTrackManagementArgs {
  dataRef: React.MutableRefObject<TimelineData | null>;
  resolvedConfig: TimelineData['resolvedConfig'] | null;
  selectedClipId: string | null;
  setSelectedTrackId: React.Dispatch<React.SetStateAction<string | null>>;
  applyEdit: TimelineApplyEdit;
}

export interface UseTimelineTrackManagementResult {
  handleAddTrack: (kind: TrackKind) => void;
  handleTrackPopoverChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  handleMoveTrack: (activeId: string, overId: string) => void;
  handleRemoveTrack: (trackId: string) => void;
  handleClearUnusedTracks: () => void;
  unusedTrackCount: number;
  moveClipToRow: (clipId: string, targetRowId: string, newStartTime?: number, transactionId?: string) => void;
  createTrackAndMoveClip: (clipId: string, kind: TrackKind, newStartTime?: number, insertAtTop?: boolean) => void;
  moveSelectedClipToTrack: (direction: 'up' | 'down') => void;
  moveSelectedClipsToTrack: (direction: 'up' | 'down', selectedClipIds: ReadonlySet<string>) => void;
}

export function reorderTracksByDirection(
  tracks: TrackDefinition[],
  trackId: string,
  direction: -1 | 1,
): TrackDefinition[] {
  const index = tracks.findIndex((track) => track.id === trackId);
  if (index < 0) {
    return tracks;
  }

  const trackKind = tracks[index]?.kind;
  let targetIndex = index + direction;
  while (
    targetIndex >= 0 &&
    targetIndex < tracks.length &&
    tracks[targetIndex]?.kind !== trackKind
  ) {
    targetIndex += direction;
  }

  if (targetIndex < 0 || targetIndex >= tracks.length) {
    return tracks;
  }

  const nextTracks = [...tracks];
  [nextTracks[index], nextTracks[targetIndex]] = [nextTracks[targetIndex], nextTracks[index]];
  return nextTracks;
}

export function moveTrackWithinKind(
  tracks: TrackDefinition[],
  activeId: string,
  overId: string,
): TrackDefinition[] {
  const activeIndex = tracks.findIndex((track) => track.id === activeId);
  const overIndex = tracks.findIndex((track) => track.id === overId);
  if (activeIndex < 0 || overIndex < 0 || activeIndex === overIndex) {
    return tracks;
  }

  return arrayMove(tracks, activeIndex, overIndex);
}

/**
 * Compute the effect of translating every member of a pinned shot group by
 * (deltaTime, targetRowId). Returns next rows + per-clip metaUpdates (including
 * track patches) + clipOrderOverride + a soft-tag override for the dragged
 * group. Shared by moveClipToRow, createTrackAndMoveClip, and the batch move
 * path in moveSelectedClipsToTrack. Pure; does not touch dataRef.
 */
function translateGroupMembers({
  current,
  group,
  targetRowId,
  deltaTime,
}: {
  current: TimelineData;
  group: PinnedShotGroup;
  targetRowId: string;
  deltaTime: number;
}): {
  nextRows: TimelineRow[];
  metaUpdates: Record<string, Partial<TimelineData['meta'][string]>>;
  nextClipOrder: TimelineData['clipOrder'];
  pinnedShotGroupsOverride: PinnedShotGroup[];
} {
  const memberSet = new Set(group.clipIds);
  const sourceTrackId = group.trackId;
  const storedGroup = findGroupForTrack(
    current.config.pinnedShotGroups ?? [],
    group.shotId,
    sourceTrackId,
    current.rows,
  );
  const storedTrackId = storedGroup?.trackId ?? sourceTrackId;

  // Capture each member's current action so we can translate it.
  const memberActions = new Map<string, { start: number; end: number; effectId: string }>();
  for (const row of current.rows) {
    for (const action of row.actions) {
      if (memberSet.has(action.id)) {
        memberActions.set(action.id, { start: action.start, end: action.end, effectId: action.effectId });
      }
    }
  }

  // Remove members from their current rows, then add them (translated) to the target row.
  let nextRows = current.rows.map((row) => ({
    ...row,
    actions: row.actions.filter((a) => !memberSet.has(a.id)),
  }));
  const translatedActions = group.clipIds
    .map((clipId) => {
      const original = memberActions.get(clipId);
      if (!original) return null;
      return {
        id: clipId,
        start: original.start + deltaTime,
        end: original.end + deltaTime,
        effectId: original.effectId,
      };
    })
    .filter((a): a is NonNullable<typeof a> => a !== null);

  nextRows = nextRows.map((row) => (
    row.id === targetRowId
      ? { ...row, actions: [...row.actions, ...translatedActions] }
      : row
  ));

  // Cross-track move: update each member's `track` meta patch and clip order.
  const metaUpdates: Record<string, Partial<TimelineData['meta'][string]>> = {};
  let nextClipOrder = current.clipOrder;
  if (sourceTrackId !== targetRowId) {
    for (const clipId of group.clipIds) {
      metaUpdates[clipId] = { track: targetRowId };
      nextClipOrder = moveClipBetweenTracks(nextClipOrder, clipId, sourceTrackId, targetRowId);
    }
  }

  // Soft-tag override: trackId updated, clipIds re-derived from the translated
  // positions (order preserved for the trivial same-delta case, but reads from
  // nextRows so any future resolveOverlaps shuffles are honored).
  const orderedClipIds = orderClipIdsByAt(group.clipIds, { rows: nextRows });
  const pinnedShotGroupsOverride = (current.config.pinnedShotGroups ?? []).map((g) => (
    g.shotId === group.shotId && g.trackId === storedTrackId
      ? { ...g, trackId: targetRowId, clipIds: orderedClipIds }
      : g
  ));

  return { nextRows, metaUpdates, nextClipOrder, pinnedShotGroupsOverride };
}

function getLiveGroupStart(current: Pick<TimelineData, 'rows'>, group: PinnedShotGroup): number | null {
  const actionStarts = current.rows
    .flatMap((row) => row.actions)
    .filter((action) => group.clipIds.includes(action.id))
    .map((action) => action.start);

  if (actionStarts.length === 0) {
    return null;
  }

  return Math.min(...actionStarts);
}

function getLiveGroupEnd(current: Pick<TimelineData, 'rows'>, group: PinnedShotGroup): number | null {
  const actionEnds = current.rows
    .flatMap((row) => row.actions)
    .filter((action) => group.clipIds.includes(action.id))
    .map((action) => action.end);

  if (actionEnds.length === 0) {
    return null;
  }

  return Math.max(...actionEnds);
}

export function useTimelineTrackManagement({
  dataRef,
  resolvedConfig,
  selectedClipId,
  setSelectedTrackId,
  applyEdit,
}: UseTimelineTrackManagementArgs): UseTimelineTrackManagementResult {
  const moveClipToRow = useCallback((
    clipId: string,
    targetRowId: string,
    newStartTime?: number,
    transactionId?: string,
  ) => {
    let current = dataRef.current;
    if (!current) {
      return;
    }

    const enclosingGroup = findEnclosingPinnedGroup(current.config, clipId);
    if (enclosingGroup) {
      const resolvedTrackId = resolveGroupTrackId(enclosingGroup.group, current.rows);
      const resolvedGroup = resolvedTrackId === enclosingGroup.group.trackId
        ? enclosingGroup.group
        : { ...enclosingGroup.group, trackId: resolvedTrackId };
      const sourceTrack = current.tracks.find((track) => track.id === resolvedTrackId);
      const targetTrack = current.tracks.find((track) => track.id === targetRowId);
      if (!sourceTrack || !targetTrack || sourceTrack.kind !== targetTrack.kind) {
        return;
      }

      const groupStart = getLiveGroupStart(current, resolvedGroup);
      const groupEnd = getLiveGroupEnd(current, resolvedGroup);
      if (groupStart == null || groupEnd == null) {
        return;
      }
      const nextStart = typeof newStartTime === 'number' ? Math.max(0, newStartTime) : groupStart;
      const groupDuration = groupEnd - groupStart;

      // Find a free track for the group's bounding box, excluding the group's own clips
      const memberSet = new Set(resolvedGroup.clipIds);
      const rowsWithoutGroup = current.rows.map((row) => ({
        ...row,
        actions: row.actions.filter((a) => !memberSet.has(a.id)),
      }));
      const snapResult = trySnapToEdge(
        rowsWithoutGroup,
        targetRowId,
        nextStart,
        groupDuration,
      );
      const effectiveGroupStart = snapResult.snapped ? snapResult.time : nextStart;
      let finalTargetId = snapResult.snapped
        ? targetRowId
        : findNearestFreeTrack(
            current.tracks,
            rowsWithoutGroup,
            targetRowId,
            sourceTrack.kind,
            effectiveGroupStart,
            groupDuration,
          );

      if (!finalTargetId) {
        const prefix = sourceTrack.kind === 'audio' ? 'A' : 'V';
        const nextNumber = getTrackIndex(current.tracks, prefix) + 1;
        finalTargetId = `${prefix}${nextNumber}`;
        current = {
          ...current,
          tracks: [...current.tracks, { id: finalTargetId, kind: sourceTrack.kind, label: finalTargetId }],
          rows: [...current.rows, { id: finalTargetId, actions: [] }],
        };
        dataRef.current = current;
      }

      const translatedGroup = translateGroupMembers({
        current,
        group: resolvedGroup,
        targetRowId: finalTargetId,
        deltaTime: effectiveGroupStart - groupStart,
      });
      applyEdit({
        type: 'rows',
        rows: translatedGroup.nextRows,
        metaUpdates: Object.keys(translatedGroup.metaUpdates).length > 0 ? translatedGroup.metaUpdates : undefined,
        clipOrderOverride: translatedGroup.nextClipOrder,
        pinnedShotGroupsOverride: translatedGroup.pinnedShotGroupsOverride,
      }, { transactionId });
      return;
    }

    const sourceRow = current.rows.find((row) => row.actions.some((action) => action.id === clipId));
    const targetRow = current.rows.find((row) => row.id === targetRowId);
    if (!sourceRow || !targetRow) {
      return;
    }

    const sourceTrack = current.tracks.find((track) => track.id === sourceRow.id);
    const targetTrack = current.tracks.find((track) => track.id === targetRow.id);
    const action = sourceRow.actions.find((candidate) => candidate.id === clipId);
    if (!sourceTrack || !targetTrack || !action || sourceTrack.kind !== targetTrack.kind) {
      return;
    }

    const duration = action.end - action.start;
    const nextStart = typeof newStartTime === 'number' ? Math.max(0, newStartTime) : action.start;

    // Find a free track (target first, then nearest above/below), or create one
    const snapResult = trySnapToEdge(
      current.rows,
      targetRow.id,
      nextStart,
      duration,
      clipId,
    );
    const effectiveStart = snapResult.snapped ? snapResult.time : nextStart;
    let finalTrackId = snapResult.snapped
      ? targetRow.id
      : findNearestFreeTrack(
          current.tracks,
          current.rows,
          targetRow.id,
          sourceTrack.kind,
          effectiveStart,
          duration,
          clipId,
        );

    if (!finalTrackId) {
      const prefix = sourceTrack.kind === 'audio' ? 'A' : 'V';
      const nextNumber = getTrackIndex(current.tracks, prefix) + 1;
      finalTrackId = `${prefix}${nextNumber}`;
      current = {
        ...current,
        tracks: [...current.tracks, { id: finalTrackId, kind: sourceTrack.kind, label: finalTrackId }],
        rows: [...current.rows, { id: finalTrackId, actions: [] }],
      };
      dataRef.current = current;
    }

    const nextAction = { ...action, start: effectiveStart, end: effectiveStart + duration };
    const nextRows = current.rows.map((row) => {
      if (row.id === sourceRow.id && row.id === finalTrackId) {
        return {
          ...row,
          actions: row.actions.map((candidate) => (candidate.id === clipId ? nextAction : candidate)),
        };
      }

      if (row.id === sourceRow.id) {
        return { ...row, actions: row.actions.filter((candidate) => candidate.id !== clipId) };
      }

      if (row.id === finalTrackId) {
        return { ...row, actions: [...row.actions, nextAction] };
      }

      return row;
    });

    const nextClipOrder = moveClipBetweenTracks(current.clipOrder, clipId, sourceRow.id, finalTrackId);
    applyEdit({
      type: 'rows',
      rows: nextRows,
      metaUpdates: {
        [clipId]: { track: finalTrackId },
      },
      clipOrderOverride: nextClipOrder,
    }, { transactionId });
  }, [applyEdit, dataRef]);

  const createTrackAndMoveClip = useCallback((clipId: string, kind: TrackKind, newStartTime?: number, insertAtTop = false) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const enclosingGroup = findEnclosingPinnedGroup(current.config, clipId);
    const sourceClip = current.resolvedConfig.clips.find((clip) => clip.id === clipId);
    const sourceTrackId = enclosingGroup
      ? resolveGroupTrackId(enclosingGroup.group, current.rows)
      : sourceClip?.track;
    const sourceTrack = sourceTrackId
      ? current.resolvedConfig.tracks.find((track) => track.id === sourceTrackId)
      : null;
    if ((!sourceClip && !enclosingGroup) || !sourceTrack || sourceTrack.kind !== kind) {
      return;
    }

    const nextResolvedConfigBase = addTrack(current.resolvedConfig, kind, insertAtTop ? 0 : undefined);
    const newTrack = nextResolvedConfigBase.tracks.find((track) => {
      return !current.resolvedConfig.tracks.some((existingTrack) => existingTrack.id === track.id);
    }) ?? nextResolvedConfigBase.tracks[nextResolvedConfigBase.tracks.length - 1];
    if (!newTrack) {
      return;
    }

    if (enclosingGroup) {
      const previewCurrent: TimelineData = {
        ...current,
        tracks: nextResolvedConfigBase.tracks.map((track) => ({ ...track })),
        rows: nextResolvedConfigBase.tracks.map((track) => (
          current.rows.find((row) => row.id === track.id) ?? { id: track.id, actions: [] }
        )),
        config: {
          ...current.config,
          tracks: nextResolvedConfigBase.tracks.map((track) => ({ ...track })),
        },
      };
      const resolvedGroup = sourceTrackId === enclosingGroup.group.trackId
        ? enclosingGroup.group
        : { ...enclosingGroup.group, trackId: sourceTrackId };
      const groupStart = getLiveGroupStart(current, resolvedGroup);
      if (groupStart == null) {
        return;
      }
      const nextStart = typeof newStartTime === 'number' ? Math.max(0, newStartTime) : groupStart;
      const deltaTime = nextStart - groupStart;
      const translatedGroup = translateGroupMembers({
        current: previewCurrent,
        group: resolvedGroup,
        targetRowId: newTrack.id,
        deltaTime,
      });
      const nextResolvedConfig = {
        ...nextResolvedConfigBase,
        clips: nextResolvedConfigBase.clips.map((clip) => (
          enclosingGroup.group.clipIds.includes(clip.id)
            ? {
                ...clip,
                at: clip.at + deltaTime,
                track: newTrack.id,
              }
            : clip
        )),
      };

      applyEdit({
        type: 'config',
        resolvedConfig: nextResolvedConfig,
        pinnedShotGroupsOverride: translatedGroup.pinnedShotGroupsOverride,
      }, {
        selectedClipId: clipId,
        selectedTrackId: newTrack.id,
      });
      return;
    }

    const nextResolvedConfig = {
      ...nextResolvedConfigBase,
      clips: nextResolvedConfigBase.clips.map((clip) => {
        if (clip.id !== clipId) {
          return clip;
        }

        return {
          ...clip,
          at: typeof newStartTime === 'number' ? Math.max(0, newStartTime) : clip.at,
          track: newTrack.id,
        };
      }),
    };

    applyEdit({
      type: 'config',
      resolvedConfig: nextResolvedConfig,
    }, {
      selectedClipId: clipId,
      selectedTrackId: newTrack.id,
    });
  }, [applyEdit, dataRef]);

  const moveSelectedClipToTrack = useCallback((direction: 'up' | 'down') => {
    const current = dataRef.current;
    if (!current || !selectedClipId) {
      return;
    }

    const currentRowIndex = current.rows.findIndex((row) => row.actions.some((action) => action.id === selectedClipId));
    if (currentRowIndex < 0) {
      return;
    }

    const sourceTrack = current.tracks.find((track) => track.id === current.rows[currentRowIndex]?.id);
    if (!sourceTrack) {
      return;
    }

    let targetRowIndex = currentRowIndex;
    while (true) {
      targetRowIndex += direction === 'up' ? -1 : 1;
      if (targetRowIndex < 0 || targetRowIndex >= current.rows.length) {
        return;
      }

      const targetTrack = current.tracks.find((track) => track.id === current.rows[targetRowIndex]?.id);
      if (targetTrack?.kind === sourceTrack.kind) {
        moveClipToRow(selectedClipId, targetTrack.id);
        setSelectedTrackId(targetTrack.id);
        return;
      }
    }
  }, [dataRef, moveClipToRow, selectedClipId, setSelectedTrackId]);

  const moveSelectedClipsToTrack = useCallback((
    direction: 'up' | 'down',
    selectedClipIds: ReadonlySet<string>,
  ) => {
    const current = dataRef.current;
    if (!current || selectedClipIds.size === 0) {
      return;
    }

    const trackById = new Map(current.tracks.map((track) => [track.id, track]));
    const selection = categorizeSelection([...selectedClipIds], current.config);
    const freeClipIdSet = new Set(selection.freeClipIds);
    const groupsByRow = new Map<string, { clipIds: string[]; rowIndex: number; kind: TrackKind }>();
    const groupedUnits = selection.groups.flatMap((groupEntry) => {
      const group = findGroupForTrack(
        current.config.pinnedShotGroups ?? [],
        groupEntry.groupKey.shotId,
        groupEntry.groupKey.trackId,
        current.rows,
      );
      if (!group) {
        return [];
      }

      const resolvedTrackId = resolveGroupTrackId(group, current.rows);
      const rowIndex = current.rows.findIndex((row) => row.id === resolvedTrackId);
      const track = trackById.get(resolvedTrackId);
      if (rowIndex < 0 || !track) {
        return [];
      }

      return [{
        kind: 'group' as const,
        groupKey: groupEntry.groupKey,
        rowIndex,
        rowId: resolvedTrackId,
        trackKind: track.kind,
      }];
    });

    current.rows.forEach((row, rowIndex) => {
      const sourceTrack = trackById.get(row.id);
      if (!sourceTrack) {
        return;
      }

      const rowClipIds = row.actions
        .map((action) => action.id)
        .filter((clipId) => freeClipIdSet.has(clipId));
      if (rowClipIds.length === 0) {
        return;
      }

      groupsByRow.set(row.id, {
        clipIds: rowClipIds,
        rowIndex,
        kind: sourceTrack.kind,
      });
    });

    if (groupsByRow.size === 0 && groupedUnits.length === 0) {
      return;
    }

    const freeUnits = [...groupsByRow.entries()].map(([rowId, group]) => ({
      kind: 'free' as const,
      rowId,
      rowIndex: group.rowIndex,
      trackKind: group.kind,
      clipIds: group.clipIds,
    }));
    const plannedClipMoves: Array<{ clipId: string; targetRowId: string }> = [];
    const plannedGroupMoves: Array<{ groupKey: PinnedGroupKey; targetRowId: string }> = [];

    for (const kind of ['visual', 'audio'] as const) {
      const kindUnits = [
        ...freeUnits.filter((unit) => unit.trackKind === kind),
        ...groupedUnits.filter((unit) => unit.trackKind === kind),
      ];
      if (kindUnits.length === 0) {
        continue;
      }

      const kindClipMoves: Array<{ clipId: string; targetRowId: string }> = [];
      const kindGroupMoves: Array<{ groupKey: PinnedGroupKey; targetRowId: string }> = [];
      let isBlocked = false;

      for (const unit of kindUnits) {
        let targetRowIndex = unit.rowIndex;
        let targetRowId: string | null = null;

        while (true) {
          targetRowIndex += direction === 'up' ? -1 : 1;
          if (targetRowIndex < 0 || targetRowIndex >= current.rows.length) {
            isBlocked = true;
            break;
          }

          const targetTrack = trackById.get(current.rows[targetRowIndex]?.id ?? '');
          if (targetTrack?.kind === kind) {
            targetRowId = targetTrack.id;
            break;
          }
        }

        if (isBlocked || !targetRowId) {
          isBlocked = true;
          break;
        }

        if (unit.kind === 'group') {
          kindGroupMoves.push({ groupKey: unit.groupKey, targetRowId });
          continue;
        }

        for (const clipId of unit.clipIds) {
          kindClipMoves.push({ clipId, targetRowId });
        }
      }

      if (!isBlocked) {
        plannedClipMoves.push(...kindClipMoves);
        plannedGroupMoves.push(...kindGroupMoves);
      }
    }

    if (plannedClipMoves.length === 0 && plannedGroupMoves.length === 0) {
      return;
    }

    const transactionId = crypto.randomUUID();
    if (plannedGroupMoves.length > 0) {
      let workingState: TimelineData = current;
      const accumulatedMetaUpdates: Record<string, Partial<TimelineData['meta'][string]>> = {};
      let appliedGroupMove = false;

      for (const move of plannedGroupMoves) {
        const existingGroup = findGroupForTrack(
          workingState.config.pinnedShotGroups ?? [],
          move.groupKey.shotId,
          move.groupKey.trackId,
          workingState.rows,
        );
        if (!existingGroup) {
          continue;
        }

        const resolvedTrackId = resolveGroupTrackId(existingGroup, workingState.rows);
        const resolvedGroup = resolvedTrackId === existingGroup.trackId
          ? existingGroup
          : { ...existingGroup, trackId: resolvedTrackId };

        const translatedGroup = translateGroupMembers({
          current: workingState,
          group: resolvedGroup,
          targetRowId: move.targetRowId,
          deltaTime: 0,
        });
        Object.assign(accumulatedMetaUpdates, translatedGroup.metaUpdates);
        const nextMeta: Record<string, ClipMeta> = {
          ...workingState.meta,
          ...translatedGroup.metaUpdates,
        } as Record<string, ClipMeta>;
        workingState = {
          ...workingState,
          rows: translatedGroup.nextRows,
          meta: nextMeta,
          clipOrder: translatedGroup.nextClipOrder,
          config: {
            ...workingState.config,
            pinnedShotGroups: translatedGroup.pinnedShotGroupsOverride,
          },
        };
        appliedGroupMove = true;
      }

      if (appliedGroupMove) {
        applyEdit({
          type: 'rows',
          rows: workingState.rows,
          metaUpdates: Object.keys(accumulatedMetaUpdates).length > 0 ? accumulatedMetaUpdates : undefined,
          clipOrderOverride: workingState.clipOrder,
          pinnedShotGroupsOverride: workingState.config.pinnedShotGroups,
        }, { transactionId });
      }
    }

    for (const move of plannedClipMoves) {
      moveClipToRow(move.clipId, move.targetRowId, undefined, transactionId);
    }

    const primaryGroupMove = selectedClipId
      ? findEnclosingPinnedGroup(current.config, selectedClipId)
      : null;
    const primaryMove = primaryGroupMove
      ? plannedGroupMoves.find((move) => (
          move.groupKey.shotId === primaryGroupMove.groupKey.shotId
          && move.groupKey.trackId === primaryGroupMove.groupKey.trackId
        ))
      : (selectedClipId
          ? plannedClipMoves.find((move) => move.clipId === selectedClipId)
          : undefined)
        ?? plannedGroupMoves[0]
        ?? plannedClipMoves[0];
    if (primaryMove) {
      setSelectedTrackId(primaryMove.targetRowId);
    }
  }, [applyEdit, dataRef, moveClipToRow, selectedClipId, setSelectedTrackId]);

  const handleAddTrack = useCallback((kind: TrackKind) => {
    if (!resolvedConfig) {
      return;
    }

    const nextResolvedConfig = addTrack(resolvedConfig, kind);
    const nextTrack = nextResolvedConfig.tracks[nextResolvedConfig.tracks.length - 1] ?? null;
    applyEdit({ type: 'config', resolvedConfig: nextResolvedConfig }, { selectedTrackId: nextTrack?.id ?? null });
  }, [applyEdit, resolvedConfig]);

  const handleTrackPopoverChange = useCallback((trackId: string, patch: Partial<TrackDefinition>) => {
    if (!resolvedConfig) {
      return;
    }

    const nextConfig = {
      ...resolvedConfig,
      tracks: resolvedConfig.tracks.map((track) => (track.id === trackId ? { ...track, ...patch } : track)),
    };
    applyEdit({ type: 'config', resolvedConfig: nextConfig }, { selectedTrackId: trackId });
  }, [applyEdit, resolvedConfig]);

  const handleMoveTrack = useCallback((activeId: string, overId: string) => {
    if (!resolvedConfig) {
      return;
    }

    const nextTracks = moveTrackWithinKind(resolvedConfig.tracks, activeId, overId);
    if (nextTracks === resolvedConfig.tracks) {
      return;
    }

    applyEdit({ type: 'config', resolvedConfig: { ...resolvedConfig, tracks: nextTracks } }, { selectedTrackId: activeId });
  }, [applyEdit, resolvedConfig]);

  const handleRemoveTrack = useCallback((trackId: string) => {
    if (!resolvedConfig) {
      return;
    }

    const track = resolvedConfig.tracks.find((entry) => entry.id === trackId);
    if (!track) {
      return;
    }

    const sameKind = resolvedConfig.tracks.filter((entry) => entry.kind === track.kind);
    if (sameKind.length <= 1) {
      return;
    }

    const nextConfig = {
      ...resolvedConfig,
      tracks: resolvedConfig.tracks.filter((entry) => entry.id !== trackId),
      clips: resolvedConfig.clips.filter((clip) => clip.track !== trackId),
    };
    applyEdit({ type: 'config', resolvedConfig: nextConfig }, { selectedTrackId: null, semantic: true });
  }, [applyEdit, resolvedConfig]);

  const unusedTrackCount = useMemo(() => {
    if (!resolvedConfig) {
      return 0;
    }

    const tracksWithClips = new Set(resolvedConfig.clips.map((clip) => clip.track));
    const defaultTrackIds = new Set(DEFAULT_VIDEO_TRACKS.map((track) => track.id));

    // Count how many tracks would actually be removed (matching handleClearUnusedTracks logic).
    // We always keep at least one track per kind, even if it's empty.
    let keptEmptyVisual = false;
    let keptEmptyAudio = false;
    let removable = 0;

    for (const track of resolvedConfig.tracks) {
      if (defaultTrackIds.has(track.id) || tracksWithClips.has(track.id)) {
        continue;
      }

      if (track.kind === 'visual' && !keptEmptyVisual) {
        const hasVisualWithClips = resolvedConfig.tracks.some((t) => t.kind === 'visual' && tracksWithClips.has(t.id));
        if (!hasVisualWithClips) {
          keptEmptyVisual = true;
          continue;
        }
      }

      if (track.kind === 'audio' && !keptEmptyAudio) {
        const hasAudioWithClips = resolvedConfig.tracks.some((t) => t.kind === 'audio' && tracksWithClips.has(t.id));
        if (!hasAudioWithClips) {
          keptEmptyAudio = true;
          continue;
        }
      }

      removable++;
    }

    return removable;
  }, [resolvedConfig]);

  const handleClearUnusedTracks = useCallback(() => {
    if (!resolvedConfig || unusedTrackCount === 0) {
      return;
    }

    const tracksWithClips = new Set(resolvedConfig.clips.map((clip) => clip.track));
    const defaultTrackIds = new Set(DEFAULT_VIDEO_TRACKS.map((track) => track.id));
    const visualWithClips = resolvedConfig.tracks.filter((track) => track.kind === 'visual' && tracksWithClips.has(track.id));
    const audioWithClips = resolvedConfig.tracks.filter((track) => track.kind === 'audio' && tracksWithClips.has(track.id));

    const nextTracks = resolvedConfig.tracks.filter((track) => {
      if (defaultTrackIds.has(track.id)) {
        return true;
      }

      if (tracksWithClips.has(track.id)) {
        return true;
      }

      if (track.kind === 'visual' && visualWithClips.length === 0) {
        visualWithClips.push(track);
        return true;
      }

      if (track.kind === 'audio' && audioWithClips.length === 0) {
        audioWithClips.push(track);
        return true;
      }

      return false;
    });

    applyEdit({ type: 'config', resolvedConfig: { ...resolvedConfig, tracks: nextTracks } }, { selectedTrackId: null, semantic: true });
  }, [applyEdit, resolvedConfig, unusedTrackCount]);

  return {
    handleAddTrack,
    handleTrackPopoverChange,
    handleMoveTrack,
    handleRemoveTrack,
    handleClearUnusedTracks,
    unusedTrackCount,
    moveClipToRow,
    createTrackAndMoveClip,
    moveSelectedClipToTrack,
    moveSelectedClipsToTrack,
  };
}
