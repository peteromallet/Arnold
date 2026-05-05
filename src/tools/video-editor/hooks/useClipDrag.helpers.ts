import type { TimelineApplyEdit } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import { userSelectTimelineClip, userSelectTimelineClips } from '@/shared/state/selectionStore.ts';
import type { DropPosition } from '@/tools/video-editor/lib/drop-position.ts';
import type { TimelineInputModality } from '@/tools/video-editor/lib/mobile-interaction-model.ts';
import {
  type ClipOffset,
  applyMultiDragMoves,
  buildAugmentedData,
  buildConfigFromDragResult,
  planMultiDragMoves,
} from '@/tools/video-editor/lib/multi-drag-utils.ts';
import {
  findEnclosingPinnedGroup,
  orderClipIdsByAt,
  resolveGroupTrackId,
} from '@/tools/video-editor/lib/pinned-group-projection.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { PinnedShotGroup, TrackKind } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

export interface ActionDragState {
  rowId: string;
  initialStart: number;
  initialEnd: number;
  latestStart: number;
  latestEnd: number;
}

export interface GroupDragEntry {
  groupKey: { shotId: string; trackId: string };
  originStart: number;
  originTrackId: string;
}

export interface DragSession {
  clipId: string;
  draggedClipIds: string[];
  groupDragEntry: GroupDragEntry | null;
}

export interface InternalDragSession extends DragSession {
  pointerId: number;
  sourceRowId: string;
  sourceKind: TrackKind;
  clipOffsets: ClipOffset[];
  ctrlKey: boolean;
  metaKey: boolean;
  wasSelectedOnPointerDown: boolean;
  startClientX: number;
  startClientY: number;
  pointerOffsetX: number;
  pointerOffsetY: number;
  pointerCoordinateYOffset: number;
  clipDuration: number;
  clipEl: HTMLElement;
  inputModality: TimelineInputModality;
  floatingGhostEl: HTMLElement | null;
  countBadgeEl: HTMLSpanElement | null;
  dragAllowed: boolean;
  hasMoved: boolean;
  claimedGestureOwner: boolean;
  transactionId: string;
}

export interface DragIntent {
  readonly pointerId: number;
  readonly clipId: string;
  readonly sourceRowId: string;
  readonly sourceKind: TrackKind;
  readonly draggedClipIds: readonly string[];
  readonly clipOffsets: readonly ClipOffset[];
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly wasSelectedOnPointerDown: boolean;
  readonly startClientX: number;
  readonly startClientY: number;
  readonly pointerOffsetX: number;
  readonly pointerOffsetY: number;
  readonly pointerCoordinateYOffset: number;
  readonly clipDuration: number;
  readonly inputModality: TimelineInputModality;
  readonly dragAllowed: boolean;
  readonly transactionId: string;
  readonly groupDragEntry: GroupDragEntry | null;
}

export type DragMachineState =
  | { phase: 'idle' }
  | { phase: 'pending'; controller: AbortController; intent: DragIntent; session: InternalDragSession }
  | { phase: 'dragging'; controller: AbortController; intent: DragIntent; session: InternalDragSession };

interface BuildPendingDragSessionArgs {
  clipId: string;
  rowId: string;
  sourceKind: TrackKind;
  sourceAction: TimelineAction;
  current: TimelineData;
  clipTarget: HTMLElement;
  labelTarget: HTMLElement | null;
  event: PointerEvent;
  selectedClipIds: Set<string>;
  additiveSelection: boolean;
  dragAllowed: boolean;
  inputModality: TimelineInputModality;
  pixelsPerSecond: number;
}

interface BuildPendingDragSessionResult {
  actionDragState: ActionDragState;
  intent: DragIntent;
  session: InternalDragSession;
}

interface DragCommitCallbacks {
  moveClipToRow: (clipId: string, targetRowId: string, newStartTime?: number, transactionId?: string) => void;
  createTrackAndMoveClip: (clipId: string, kind: TrackKind, newStartTime?: number, insertAtTop?: boolean) => void;
  selectClip: (clipId: string) => void;
  selectClips: (clipIds: Iterable<string>) => void;
  applyEdit: TimelineApplyEdit;
}

interface CommitDraggingSessionArgs {
  session: InternalDragSession;
  nextStart: number;
  dropPosition: DropPosition | null;
  crossTrackActive: boolean;
  liveData: TimelineData | null;
  callbacks: DragCommitCallbacks;
}

export function findClipElement(
  wrapper: HTMLDivElement,
  clipId: string,
  rowId: string,
): HTMLElement | null {
  const candidates = wrapper.querySelectorAll<HTMLElement>('.clip-action');
  for (const candidate of candidates) {
    if (candidate.dataset.clipId === clipId && candidate.dataset.rowId === rowId) {
      return candidate;
    }
  }
  return null;
}

export function updateFloatingGhostPosition(
  session: InternalDragSession,
  clientX: number,
  clientY: number,
): void {
  if (!session.floatingGhostEl) return;
  const adjustedClientY = clientY + session.pointerCoordinateYOffset;
  session.floatingGhostEl.style.left = `${clientX - session.pointerOffsetX}px`;
  session.floatingGhostEl.style.top = `${adjustedClientY - session.pointerOffsetY}px`;
}

export function createFloatingGhost(clipEl: HTMLElement): HTMLElement {
  const rect = clipEl.getBoundingClientRect();
  const el = clipEl.cloneNode(true) as HTMLElement;
  el.classList.add('cross-track-ghost');
  el.style.width = `${rect.width}px`;
  el.style.height = `${rect.height}px`;
  document.body.appendChild(el);
  return el;
}

export function ensureCountBadge(session: InternalDragSession): void {
  if (session.draggedClipIds.length <= 1 || session.countBadgeEl) {
    return;
  }

  const badge = document.createElement('span');
  badge.className = 'pointer-events-none absolute right-1 top-1 rounded-full bg-sky-400 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-sky-950 shadow-sm';
  badge.textContent = `${session.draggedClipIds.length} clips`;
  session.clipEl.appendChild(badge);
  session.countBadgeEl = badge;
}

export function buildClipOffsets(
  current: TimelineData,
  draggedClipIds: readonly string[],
  anchorInitialStart: number,
): ClipOffset[] {
  return draggedClipIds.flatMap((draggedClipId) => {
    for (const row of current.rows) {
      const action = row.actions.find((candidate) => candidate.id === draggedClipId);
      if (action) {
        return [{
          clipId: draggedClipId,
          rowId: row.id,
          deltaTime: action.start - anchorInitialStart,
          initialStart: action.start,
          initialEnd: action.end,
        }];
      }
    }

    return [];
  });
}

export function getAnchorTimeDelta(session: InternalDragSession, snappedStart: number): number {
  if (session.groupDragEntry) {
    return snappedStart - session.groupDragEntry.originStart;
  }

  const anchorClip = session.clipOffsets.find((clip) => clip.clipId === session.clipId);
  return anchorClip ? snappedStart - anchorClip.initialStart : 0;
}

export function rebuildGroupAfterDrag(
  currentGroups: PinnedShotGroup[] | undefined,
  draggedGroupKey: { shotId: string; trackId: string },
  newTrackId: string,
  nextRows: TimelineRow[],
): PinnedShotGroup[] | undefined {
  if (!currentGroups || currentGroups.length === 0) return undefined;
  return currentGroups.map((group) => {
    if (group.shotId !== draggedGroupKey.shotId || group.trackId !== draggedGroupKey.trackId) {
      return group;
    }
    const orderedClipIds = orderClipIdsByAt(group.clipIds, { rows: nextRows });
    return {
      ...group,
      trackId: newTrackId,
      clipIds: orderedClipIds,
    };
  });
}

export function buildPendingDragSession({
  clipId,
  rowId,
  sourceKind,
  sourceAction,
  current,
  clipTarget,
  labelTarget,
  event,
  selectedClipIds,
  additiveSelection,
  dragAllowed,
  inputModality,
  pixelsPerSecond,
}: BuildPendingDragSessionArgs): BuildPendingDragSessionResult {
  const enclosingGroup = findEnclosingPinnedGroup(current.config, clipId);
  const clipRect = clipTarget.getBoundingClientRect();
  const pointerCoordinateYOffset = labelTarget
    ? clipRect.top - labelTarget.getBoundingClientRect().top
    : 0;
  const adjustedStartClientY = event.clientY + pointerCoordinateYOffset;

  let groupLiveStart = sourceAction.start;
  let groupLiveEnd = sourceAction.end;
  if (enclosingGroup) {
    const memberActions: { start: number; end: number }[] = [];
    for (const row of current.rows) {
      for (const action of row.actions) {
        if (enclosingGroup.group.clipIds.includes(action.id)) {
          memberActions.push({ start: action.start, end: action.end });
        }
      }
    }
    if (memberActions.length > 0) {
      groupLiveStart = Math.min(...memberActions.map((action) => action.start));
      groupLiveEnd = Math.max(...memberActions.map((action) => action.end));
    }
  }

  const initialStart = enclosingGroup ? groupLiveStart : sourceAction.start;
  const clipDuration = enclosingGroup
    ? (groupLiveEnd - groupLiveStart)
    : (sourceAction.end - sourceAction.start);
  const shouldDragSelectedSet = additiveSelection && selectedClipIds.has(clipId);
  const draggedClipIds = enclosingGroup
    ? shouldDragSelectedSet
      ? [
          ...enclosingGroup.group.clipIds,
          ...[...selectedClipIds].filter((selectedClipId) => !enclosingGroup.group.clipIds.includes(selectedClipId)),
        ]
      : [...enclosingGroup.group.clipIds]
    : shouldDragSelectedSet
      ? [clipId, ...[...selectedClipIds].filter((selectedClipId) => selectedClipId !== clipId)]
      : [clipId];
  const clipOffsets = buildClipOffsets(current, draggedClipIds, initialStart);
  const validDraggedClipIds = clipOffsets.map(({ clipId: draggedClipId }) => draggedClipId);
  const groupDragEntry = enclosingGroup
    ? {
        groupKey: enclosingGroup.groupKey,
        originStart: groupLiveStart,
        originTrackId: resolveGroupTrackId(enclosingGroup.group, current.rows),
      }
    : null;
  const transactionId = crypto.randomUUID();

  const intent: DragIntent = {
    pointerId: event.pointerId,
    clipId,
    sourceRowId: rowId,
    sourceKind,
    draggedClipIds: validDraggedClipIds,
    clipOffsets,
    ctrlKey: event.ctrlKey,
    metaKey: event.metaKey,
    wasSelectedOnPointerDown: selectedClipIds.has(clipId),
    startClientX: event.clientX,
    startClientY: adjustedStartClientY,
    pointerOffsetX: groupDragEntry
      ? event.clientX - (clipRect.left - ((sourceAction.start - initialStart) * pixelsPerSecond))
      : event.clientX - clipRect.left,
    pointerOffsetY: adjustedStartClientY - clipRect.top,
    pointerCoordinateYOffset,
    clipDuration,
    inputModality,
    dragAllowed,
    transactionId,
    groupDragEntry,
  };

  return {
    actionDragState: {
      rowId,
      initialStart,
      initialEnd: initialStart + clipDuration,
      latestStart: initialStart,
      latestEnd: initialStart + clipDuration,
    },
    intent,
    session: {
      ...intent,
      draggedClipIds: [...intent.draggedClipIds],
      clipOffsets: [...clipOffsets],
      clipEl: clipTarget,
      floatingGhostEl: null,
      countBadgeEl: null,
      hasMoved: false,
      claimedGestureOwner: false,
    },
  };
}

export function commitDraggingSession({
  session,
  nextStart,
  dropPosition,
  crossTrackActive,
  liveData,
  callbacks,
}: CommitDraggingSessionArgs): { deferDeactivate: boolean } {
  const isGroupDrag = session.groupDragEntry !== null;

  if (!isGroupDrag && crossTrackActive && session.draggedClipIds.length === 1) {
    if (dropPosition?.isNewTrack) {
      callbacks.createTrackAndMoveClip(
        session.clipId,
        session.sourceKind,
        nextStart,
        dropPosition.isNewTrackTop,
      );
    } else if (dropPosition?.trackId && !dropPosition.isReject) {
      callbacks.moveClipToRow(session.clipId, dropPosition.trackId, nextStart, session.transactionId);
    } else {
      callbacks.moveClipToRow(session.clipId, session.sourceRowId, nextStart, session.transactionId);
    }
    userSelectTimelineClip(session.clipId, { additive: false });
    return { deferDeactivate: true };
  }

  if (session.draggedClipIds.length > 1 || isGroupDrag) {
    if (liveData) {
      const timeDelta = getAnchorTimeDelta(session, nextStart);
      let handledNewTrackMove = false;

      if (crossTrackActive && dropPosition?.isNewTrack) {
        const augmentedData = buildAugmentedData(
          liveData,
          session.sourceKind,
          dropPosition.isNewTrackTop ?? false,
        );
        if (augmentedData) {
          const { augmented, newTrackId } = augmentedData;
          const { canMove, moves } = planMultiDragMoves(
            augmented,
            session.clipOffsets,
            session.clipId,
            newTrackId,
            session.sourceRowId,
            timeDelta,
            session.groupDragEntry ?? undefined,
          );

          if (canMove && moves.length > 0) {
            const { nextRows, metaUpdates } = applyMultiDragMoves(augmented, moves);
            const finalConfig = buildConfigFromDragResult(
              augmented.resolvedConfig,
              augmented.meta,
              nextRows,
              metaUpdates,
            );
            const pinnedShotGroupsOverride = session.groupDragEntry
              ? rebuildGroupAfterDrag(
                  liveData.config.pinnedShotGroups,
                  session.groupDragEntry.groupKey,
                  newTrackId,
                  nextRows,
                )
              : undefined;
            callbacks.applyEdit({
              type: 'config',
              resolvedConfig: finalConfig,
              pinnedShotGroupsOverride,
            }, {
              transactionId: session.transactionId,
            });
            handledNewTrackMove = true;
          }
        }
      }

      if (!handledNewTrackMove) {
        const anchorTargetRowId = crossTrackActive
          ? (dropPosition?.trackId && !dropPosition.isReject && !dropPosition.isNewTrack
              ? dropPosition.trackId
              : session.sourceRowId)
          : session.sourceRowId;
        const { canMove, moves } = planMultiDragMoves(
          liveData,
          session.clipOffsets,
          session.clipId,
          anchorTargetRowId,
          session.sourceRowId,
          timeDelta,
          session.groupDragEntry ?? undefined,
        );

        if (canMove && moves.length > 0) {
          const { nextRows, metaUpdates, nextClipOrder } = applyMultiDragMoves(liveData, moves);
          const pinnedShotGroupsOverride = session.groupDragEntry
            ? rebuildGroupAfterDrag(
                liveData.config.pinnedShotGroups,
                session.groupDragEntry.groupKey,
                anchorTargetRowId,
                nextRows,
              )
            : undefined;
          callbacks.applyEdit({
            type: 'rows',
            rows: nextRows,
            metaUpdates,
            clipOrderOverride: nextClipOrder,
            pinnedShotGroupsOverride,
          }, {
            transactionId: session.transactionId,
          });
        }
      }
    }

    userSelectTimelineClips(session.draggedClipIds, { additive: false });
    return { deferDeactivate: crossTrackActive };
  }

  callbacks.moveClipToRow(session.clipId, session.sourceRowId, nextStart, session.transactionId);
  userSelectTimelineClip(session.clipId, { additive: false });
  return { deferDeactivate: false };
}
