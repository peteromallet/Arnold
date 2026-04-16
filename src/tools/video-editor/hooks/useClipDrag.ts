import { useEffect, useRef } from 'react';
import type { MutableRefObject, RefObject } from 'react';
import type { SelectClipOptions } from '@/shared/state/selectionStore';
import type { DragCoordinator } from '@/tools/video-editor/hooks/useDragCoordinator';
import type { TimelineApplyEdit } from '@/tools/video-editor/hooks/timeline-state-types';
import type { TrackKind } from '@/tools/video-editor/types';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { computeSecondaryGhosts } from '@/tools/video-editor/lib/multi-drag-utils';
import { createAutoScroller } from '@/tools/video-editor/lib/auto-scroll';
import { notifyInteractionEndIfIdle } from '@/tools/video-editor/lib/interaction-state';
import {
  shouldPreserveTouchSelectionForMove,
  shouldAllowTouchClipDrag,
  shouldToggleTouchSelection,
  type TimelineDeviceClass,
  type TimelineGestureOwner,
  type TimelineInputModality,
  type TimelineInteractionMode,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import { snapDrag } from '@/tools/video-editor/lib/snap-edges';
import { useTimelineScale } from '@/tools/video-editor/hooks/useTimelineScale';
import {
  useTimelineDataSliceSafe,
  useTimelineMutableAdaptersSafe,
  useTimelineOpsSliceSafe,
} from '@/tools/video-editor/hooks/timelineStore';
import type { ActionDragState, DragMachineState, DragSession, InternalDragSession } from '@/tools/video-editor/hooks/useClipDrag.helpers';
import { buildPendingDragSession, commitDraggingSession, createFloatingGhost, ensureCountBadge, findClipElement, updateFloatingGhostPosition } from '@/tools/video-editor/hooks/useClipDrag.helpers';

const DRAG_THRESHOLD_PX = 4;
/** Snap threshold in pixels — converted to seconds based on current zoom. */
const SNAP_THRESHOLD_PX = 8;
/** Vertical pixel threshold before activating cross-track mode. */
const CROSS_TRACK_THRESHOLD_PX = 10;

interface UseCrossTrackDragOptions {
  timelineWrapperRef: RefObject<HTMLDivElement | null>;
  dataRef: MutableRefObject<TimelineData | null>;
  interactionStateRef?: import('@/tools/video-editor/lib/interaction-state').InteractionStateRef;
  deviceClass: TimelineDeviceClass;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => TimelineInputModality;
  moveClipToRow: (clipId: string, targetRowId: string, newStartTime?: number, transactionId?: string) => void;
  createTrackAndMoveClip: (clipId: string, kind: TrackKind, newStartTime?: number, insertAtTop?: boolean) => void;
  selectClip: (clipId: string, opts?: SelectClipOptions) => void;
  selectClips: (clipIds: Iterable<string>) => void;
  selectedClipIdsRef: MutableRefObject<Set<string>>;
  applyEdit: TimelineApplyEdit;
  coordinator: DragCoordinator;
  additiveSelectionRef: MutableRefObject<boolean>;
  rowHeight: number;
  scale: number;
  scaleWidth: number;
  startLeft: number;
}

interface UseClipDragLatest {
  coordinator: DragCoordinator;
  moveClipToRow: UseCrossTrackDragOptions['moveClipToRow'];
  createTrackAndMoveClip: UseCrossTrackDragOptions['createTrackAndMoveClip'];
  selectClip: UseCrossTrackDragOptions['selectClip'];
  selectClips: UseCrossTrackDragOptions['selectClips'];
  selectedClipIdsRef: MutableRefObject<Set<string>>;
  applyEdit: TimelineApplyEdit;
  additiveSelectionRef: MutableRefObject<boolean>;
  deviceClass: TimelineDeviceClass;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  setInputModalityFromPointerType: (
    pointerType: string | null | undefined,
  ) => TimelineInputModality;
  interactionStateRef?: import('@/tools/video-editor/lib/interaction-state').InteractionStateRef;
}

export interface UseClipDragResult {
  dragSessionRef: MutableRefObject<DragSession | null>;
}

export type { ActionDragState, DragSession } from '@/tools/video-editor/hooks/useClipDrag.helpers';

export const useClipDrag = ({
  timelineWrapperRef,
  dataRef,
  interactionStateRef,
  deviceClass,
  interactionMode,
  gestureOwner,
  setGestureOwner,
  setInputModalityFromPointerType,
  moveClipToRow,
  createTrackAndMoveClip,
  selectClip,
  selectClips,
  selectedClipIdsRef,
  applyEdit,
  coordinator,
  additiveSelectionRef,
  rowHeight: _rowHeight,
  scale,
  scaleWidth,
  startLeft: _startLeft,
}: UseCrossTrackDragOptions): UseClipDragResult => {
  const storeData = useTimelineDataSliceSafe();
  const storeOps = useTimelineOpsSliceSafe();
  const storeAdapters = useTimelineMutableAdaptersSafe();
  const effectiveTimelineWrapperRef = storeData?.timelineWrapperRef ?? timelineWrapperRef;
  const effectiveDataRef = storeAdapters?.dataRef ?? dataRef;
  const effectiveInteractionStateRef = storeAdapters?.interactionStateRef ?? interactionStateRef;
  const effectiveDeviceClass = storeData?.deviceClass ?? deviceClass;
  const effectiveInteractionMode = storeData?.interactionMode ?? interactionMode;
  const effectiveGestureOwner = storeData?.gestureOwner ?? gestureOwner;
  const effectiveSetGestureOwner = storeOps?.setGestureOwner ?? setGestureOwner;
  const effectiveSetInputModalityFromPointerType = storeOps?.setInputModalityFromPointerType ?? setInputModalityFromPointerType;
  const effectiveMoveClipToRow = storeOps?.moveClipToRow ?? moveClipToRow;
  const effectiveCreateTrackAndMoveClip = storeOps?.createTrackAndMoveClip ?? createTrackAndMoveClip;
  const effectiveSelectClip = storeOps?.selectClip ?? selectClip;
  const effectiveSelectClips = storeOps?.selectClips ?? selectClips;
  const effectiveSelectedClipIdsRef = storeAdapters?.selectedClipIdsRef ?? selectedClipIdsRef;
  const effectiveApplyEdit = storeOps?.applyEdit ?? applyEdit;
  const effectiveCoordinator = storeData?.coordinator ?? coordinator;
  const effectiveAdditiveSelectionRef = storeAdapters?.additiveSelectionRef ?? additiveSelectionRef;
  const effectiveScale = storeData?.scale ?? scale;
  const effectiveScaleWidth = storeData?.scaleWidth ?? scaleWidth;
  const dragSessionRef = useRef<DragSession | null>(null);
  const stateRef = useRef<DragMachineState>({ phase: 'idle' });
  const actionDragStateRef = useRef<ActionDragState | null>(null);
  const crossTrackActiveRef = useRef(false);
  const autoScrollerRef = useRef<ReturnType<typeof createAutoScroller> | null>(null);
  const { pixelsPerSecondRef } = useTimelineScale({
    scale: effectiveScale,
    scaleWidth: effectiveScaleWidth,
    startLeft: _startLeft,
  });

  // Keep volatile values in refs so the effect doesn't re-run mid-drag
  // when zoom/scale changes.
  const latestRef = useRef<UseClipDragLatest>({
    coordinator: effectiveCoordinator,
    moveClipToRow: effectiveMoveClipToRow,
    createTrackAndMoveClip: effectiveCreateTrackAndMoveClip,
    selectClip: effectiveSelectClip,
    selectClips: effectiveSelectClips,
    selectedClipIdsRef: effectiveSelectedClipIdsRef,
    applyEdit: effectiveApplyEdit,
    additiveSelectionRef: effectiveAdditiveSelectionRef,
    deviceClass: effectiveDeviceClass,
    interactionMode: effectiveInteractionMode,
    gestureOwner: effectiveGestureOwner,
    setGestureOwner: effectiveSetGestureOwner,
    setInputModalityFromPointerType: effectiveSetInputModalityFromPointerType,
    interactionStateRef: effectiveInteractionStateRef,
  });
  latestRef.current = {
    coordinator: effectiveCoordinator,
    moveClipToRow: effectiveMoveClipToRow,
    createTrackAndMoveClip: effectiveCreateTrackAndMoveClip,
    selectClip: effectiveSelectClip,
    selectClips: effectiveSelectClips,
    selectedClipIdsRef: effectiveSelectedClipIdsRef,
    applyEdit: effectiveApplyEdit,
    additiveSelectionRef: effectiveAdditiveSelectionRef,
    deviceClass: effectiveDeviceClass,
    interactionMode: effectiveInteractionMode,
    gestureOwner: effectiveGestureOwner,
    setGestureOwner: effectiveSetGestureOwner,
    setInputModalityFromPointerType: effectiveSetInputModalityFromPointerType,
    interactionStateRef: effectiveInteractionStateRef,
  };

  useEffect(() => {
    const setCompatSession = (session: DragSession | null) => {
      dragSessionRef.current = session;
    };

    const setState = (nextState: DragMachineState) => {
      stateRef.current = nextState;
      setCompatSession(nextState.phase === 'idle' ? null : nextState.session);
    };

    const getActiveState = (): Extract<DragMachineState, { phase: 'pending' | 'dragging' }> | null => {
      const currentState = stateRef.current;
      return currentState.phase === 'idle' ? null : currentState;
    };

    const endSession = ({ deferDeactivate = false }: { deferDeactivate?: boolean } = {}) => {
      autoScrollerRef.current?.stop();
      autoScrollerRef.current = null;
      latestRef.current.coordinator.end();

      const currentState = getActiveState();
      if (!currentState) {
        actionDragStateRef.current = null;
        if (!deferDeactivate) {
          crossTrackActiveRef.current = false;
        }
        return;
      }

      currentState.controller.abort();
      currentState.session.floatingGhostEl?.remove();
      currentState.session.countBadgeEl?.remove();
      if (latestRef.current.interactionStateRef) {
        latestRef.current.interactionStateRef.current.drag = false;
        notifyInteractionEndIfIdle(latestRef.current.interactionStateRef);
      }
      if (currentState.session.claimedGestureOwner) {
        latestRef.current.setGestureOwner('none');
      }

      actionDragStateRef.current = null;
      setState({ phase: 'idle' });
      if (deferDeactivate) {
        window.requestAnimationFrame(() => {
          if (stateRef.current.phase === 'idle') {
            crossTrackActiveRef.current = false;
          }
        });
      } else {
        crossTrackActiveRef.current = false;
      }
    };

    const updateDragState = (session: InternalDragSession, clientX: number, clientY: number) => {
      const adjustedClientY = clientY + session.pointerCoordinateYOffset;
      const nextPosition = latestRef.current.coordinator.update({
        clientX,
        clientY: adjustedClientY,
        sourceKind: session.sourceKind,
        clipDuration: session.clipDuration,
        clipOffsetX: session.pointerOffsetX,
        excludeClipIds: new Set(session.draggedClipIds),
      });

      const pixelsPerSecond = pixelsPerSecondRef.current;
      const snapThresholdS = SNAP_THRESHOLD_PX / pixelsPerSecond;
      const targetRowId = nextPosition.trackId ?? session.sourceRowId;
      const targetRow = effectiveDataRef.current?.rows.find((row) => row.id === targetRowId);
      const siblings = targetRow?.actions ?? [];
      const { start: snappedStart } = snapDrag(
        nextPosition.time,
        session.clipDuration,
        siblings,
        session.clipId,
        snapThresholdS,
        session.draggedClipIds,
      );

      const dragState = actionDragStateRef.current;
      if (dragState) {
        const duration = dragState.initialEnd - dragState.initialStart;
        dragState.latestStart = snappedStart;
        dragState.latestEnd = snappedStart + duration;
      }

      const dy = adjustedClientY - session.startClientY;
      if (!crossTrackActiveRef.current && Math.abs(dy) >= CROSS_TRACK_THRESHOLD_PX) {
        crossTrackActiveRef.current = true;
        session.floatingGhostEl = createFloatingGhost(session.clipEl);
        updateFloatingGhostPosition(session, clientX, clientY);
      }

      if (crossTrackActiveRef.current) {
        updateFloatingGhostPosition(session, clientX, clientY);
      }

      if (session.floatingGhostEl) {
        session.floatingGhostEl.style.cursor = nextPosition.isReject ? 'not-allowed' : '';
      }

      if (session.draggedClipIds.length > 1) {
        const latest = effectiveDataRef.current;
        if (latest) {
          const anchorTargetRowId = nextPosition.trackId ?? session.sourceRowId;
          const ghosts = computeSecondaryGhosts(
            session.clipOffsets,
            session.clipId,
            session.sourceRowId,
            anchorTargetRowId,
            nextPosition.screenCoords.clipLeft,
            nextPosition.screenCoords.rowTop,
            nextPosition.screenCoords.rowHeight,
            pixelsPerSecond,
            latest.rows.map((row) => row.id),
          );
          latestRef.current.coordinator.showSecondaryGhosts(ghosts);
        }
      }
    };

    const enterDragging = (pendingState: Extract<DragMachineState, { phase: 'pending' }>) => {
      const session = pendingState.session;
      if (session.hasMoved) {
        return;
      }

      session.hasMoved = true;
      session.claimedGestureOwner = true;
      if (latestRef.current.interactionStateRef) {
        latestRef.current.interactionStateRef.current.drag = true;
      }
      latestRef.current.setGestureOwner('clip');
      ensureCountBadge(session);
      setState({
        ...pendingState,
        phase: 'dragging',
      });
    };

    // ── Pointer handlers ─────────────────────────────────────────────

    const handlePointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;

      const wrapper = effectiveTimelineWrapperRef.current;
      if (!wrapper || !wrapper.contains(event.target as Node)) return;

      const eventTarget = event.target instanceof HTMLElement ? event.target : null;
      const labelTarget = eventTarget?.closest<HTMLElement>('[data-shot-group-drag-anchor-clip-id]') ?? null;
      if (labelTarget && eventTarget?.closest('button')) {
        return;
      }

      const clipTarget = eventTarget?.closest<HTMLElement>('.clip-action')
        ?? (
          labelTarget?.dataset.shotGroupDragAnchorClipId && labelTarget.dataset.shotGroupDragAnchorRowId
            ? findClipElement(
                wrapper,
                labelTarget.dataset.shotGroupDragAnchorClipId,
                labelTarget.dataset.shotGroupDragAnchorRowId,
              )
            : null
        );
      if (
        !clipTarget
        || (eventTarget && eventTarget.closest("[data-delete-clip='true'], [data-no-clip-drag]"))
      ) return;

      const clipId = clipTarget.dataset.clipId;
      const rowId = clipTarget.dataset.rowId;
      if (!clipId || !rowId) return;
      if (latestRef.current.gestureOwner !== 'none' && latestRef.current.gestureOwner !== 'clip') return;

      const inputModality = latestRef.current.setInputModalityFromPointerType(event.pointerType);
      const dragAllowed = shouldAllowTouchClipDrag(
        latestRef.current.deviceClass,
        inputModality,
        latestRef.current.interactionMode,
      );

      const current = effectiveDataRef.current;
      const sourceTrack = current?.tracks.find((track) => track.id === rowId);
      const sourceRow = current?.rows.find((row) => row.id === rowId);
      const sourceAction = sourceRow?.actions.find((action) => action.id === clipId);
      if (!current || !sourceTrack || !sourceAction) return;

      endSession();
      const editArea = wrapper.querySelector<HTMLElement>('.timeline-canvas-edit-area');
      const { actionDragState, intent, session } = buildPendingDragSession({
        clipId,
        rowId,
        sourceKind: sourceTrack.kind,
        sourceAction,
        current,
        clipTarget,
        labelTarget,
        event,
        selectedClipIds: latestRef.current.selectedClipIdsRef.current,
        additiveSelection: latestRef.current.additiveSelectionRef.current,
        dragAllowed,
        inputModality,
        pixelsPerSecond: pixelsPerSecondRef.current,
      });
      actionDragStateRef.current = actionDragState;

      const controller = new AbortController();
      const signal = controller.signal;

      const handlePointerMove = (moveEvent: PointerEvent) => {
        const currentState = getActiveState();
        if (!currentState || moveEvent.pointerId !== currentState.session.pointerId) {
          return;
        }

        const session = currentState.session;
        if (currentState.phase === 'pending') {
          const dx = moveEvent.clientX - session.startClientX;
          const dy = moveEvent.clientY - session.startClientY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance < DRAG_THRESHOLD_PX) {
            return;
          }
          if (!session.dragAllowed) {
            return;
          }
          enterDragging(currentState);
        }

        const draggingState = getActiveState();
        if (!draggingState || draggingState.phase !== 'dragging' || moveEvent.pointerId !== draggingState.session.pointerId) {
          return;
        }

        moveEvent.preventDefault();
        autoScrollerRef.current?.update(moveEvent.clientX, moveEvent.clientY);
        updateDragState(draggingState.session, moveEvent.clientX, moveEvent.clientY);
      };

      const handlePointerUp = (upEvent: PointerEvent) => {
        const currentState = getActiveState();
        if (!currentState || upEvent.pointerId !== currentState.session.pointerId) {
          return;
        }

        const session = currentState.session;
        if (currentState.phase === 'dragging') {
          const dropPosition = latestRef.current.coordinator.lastPosition;
          const nextStart = actionDragStateRef.current?.latestStart
            ?? currentState.intent.clipOffsets.find((clip) => clip.clipId === session.clipId)?.initialStart
            ?? 0;
          if (!session.groupDragEntry && crossTrackActiveRef.current && session.draggedClipIds.length === 1) {
            upEvent.preventDefault();
          }
          const { deferDeactivate } = commitDraggingSession({
            session,
            nextStart,
            dropPosition,
            crossTrackActive: crossTrackActiveRef.current,
            liveData: effectiveDataRef.current,
            callbacks: {
              moveClipToRow: latestRef.current.moveClipToRow,
              createTrackAndMoveClip: latestRef.current.createTrackAndMoveClip,
              selectClip: latestRef.current.selectClip,
              selectClips: latestRef.current.selectClips,
              applyEdit: latestRef.current.applyEdit,
            },
          });
          endSession({ deferDeactivate });
          return;
        }

        if (shouldToggleTouchSelection(
          latestRef.current.deviceClass,
          session.inputModality,
          latestRef.current.interactionMode,
        )) {
          latestRef.current.selectClip(session.clipId, { toggle: true });
        } else if (
          shouldPreserveTouchSelectionForMove(
            latestRef.current.deviceClass,
            session.inputModality,
            latestRef.current.interactionMode,
          )
          && session.wasSelectedOnPointerDown
          && latestRef.current.selectedClipIdsRef.current.size > 1
        ) {
          latestRef.current.selectClip(session.clipId, { preserveSelection: true });
        } else if (session.metaKey || session.ctrlKey) {
          latestRef.current.selectClip(session.clipId, { toggle: true });
        } else {
          latestRef.current.selectClip(session.clipId);
        }
        endSession();
      };

      const handlePointerCancel = (cancelEvent: PointerEvent) => {
        const currentState = getActiveState();
        if (!currentState || cancelEvent.pointerId !== currentState.session.pointerId) {
          return;
        }
        endSession();
      };

      autoScrollerRef.current = editArea
        ? createAutoScroller(editArea, (clientX, clientY) => {
            const currentState = getActiveState();
            if (!currentState || currentState.phase !== 'dragging') {
              return;
            }
            updateDragState(currentState.session, clientX, clientY);
          })
        : null;

      setState({
        phase: 'pending',
        controller,
        intent,
        session,
      });

      window.addEventListener('pointermove', handlePointerMove, { signal });
      window.addEventListener('pointerup', handlePointerUp, { signal });
      window.addEventListener('pointercancel', handlePointerCancel, { signal });
    };

    const handleBlur = () => {
      endSession();
    };

    const effectController = new AbortController();
    document.addEventListener('pointerdown', handlePointerDown, { signal: effectController.signal });
    window.addEventListener('blur', handleBlur, { signal: effectController.signal });
    return () => {
      endSession();
      effectController.abort();
    };
  // Stable refs only — volatile values (scale, coordinator, etc.) are read via refs
  // so the effect never re-runs mid-drag.
  }, [effectiveDataRef, effectiveTimelineWrapperRef]);

  return {
    dragSessionRef,
  };
};
