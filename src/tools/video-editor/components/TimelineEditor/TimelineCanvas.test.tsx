// @vitest-environment jsdom
import React, { useMemo, useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TimelineCanvas } from '@/tools/video-editor/components/TimelineEditor/TimelineCanvas';
import { createInteractionState, onInteractionEnd } from '@/tools/video-editor/lib/interaction-state';
import type { TrackDefinition } from '@/tools/video-editor/types';
import type { TimelineAction, TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

const useTimelineMutableAdaptersMock = vi.fn();

vi.mock('@/tools/video-editor/hooks/timelineStore', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/hooks/timelineStore')>(
    '@/tools/video-editor/hooks/timelineStore',
  );

  return {
    ...actual,
    useTimelineMutableAdapters: () => useTimelineMutableAdaptersMock(),
  };
});

const track: TrackDefinition = { id: 'V1', kind: 'visual', label: 'V1' };
const action: TimelineAction = { id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' };
const row: TimelineRow = { id: 'V1', actions: [action] };
const pinnedGroupRow: TimelineRow = {
  id: 'V1',
  actions: [
    { id: 'clip-1', start: 0, end: 1, effectId: 'effect-clip-1' },
    { id: 'clip-2', start: 1, end: 2, effectId: 'effect-clip-2' },
    { id: 'clip-3', start: 2, end: 3, effectId: 'effect-clip-3' },
  ],
};
const shiftedPinnedGroupRow: TimelineRow = {
  id: 'V1',
  actions: [
    { id: 'clip-1', start: 1, end: 2, effectId: 'effect-clip-1' },
    { id: 'clip-2', start: 2, end: 3, effectId: 'effect-clip-2' },
    { id: 'clip-3', start: 3, end: 4, effectId: 'effect-clip-3' },
  ],
};
const pinnedShotGroup: NonNullable<React.ComponentProps<typeof TimelineCanvas>['shotGroups']>[number] = {
  shotId: 'shot-1',
  shotName: 'Pinned Shot',
  rowId: 'V1',
  rowIndex: 0,
  start: 0,
  clipIds: ['clip-1', 'clip-2', 'clip-3'],
  children: [
    { clipId: 'clip-1', offset: 0, duration: 1 },
    { clipId: 'clip-2', offset: 1, duration: 1 },
    { clipId: 'clip-3', offset: 2, duration: 1 },
  ],
  color: '#22c55e',
};
const MIN_GROUP_RESIZE_DURATION = 0.05;
const setGestureOwner = vi.fn();
const setInputModalityFromPointerType = vi.fn(() => 'mouse');

function cloneRowState(source: TimelineRow): TimelineRow {
  return {
    ...source,
    actions: source.actions.map((timelineAction) => ({ ...timelineAction })),
  };
}

function materializeShotGroup(
  template: NonNullable<React.ComponentProps<typeof TimelineCanvas>['shotGroups']>[number],
  rows: TimelineRow[],
): NonNullable<React.ComponentProps<typeof TimelineCanvas>['shotGroups']>[number] {
  const targetRow = rows.find((candidate) => candidate.id === template.rowId);
  if (!targetRow) {
    throw new Error(`expected row ${template.rowId}`);
  }

  const groupActions = template.clipIds.map((clipId) => {
    const timelineAction = targetRow.actions.find((candidate) => candidate.id === clipId);
    if (!timelineAction) {
      throw new Error(`expected action ${clipId}`);
    }
    return timelineAction;
  });
  const start = Math.min(...groupActions.map((timelineAction) => timelineAction.start));

  return {
    ...template,
    start,
    children: template.clipIds.map((clipId) => {
      const timelineAction = groupActions.find((candidate) => candidate.id === clipId);
      if (!timelineAction) {
        throw new Error(`expected action ${clipId}`);
      }

      return {
        clipId,
        offset: timelineAction.start - start,
        duration: timelineAction.end - timelineAction.start,
      };
    }),
  };
}

function applyRowUpdates(
  rows: TimelineRow[],
  rowId: string,
  updates: Record<string, { start: number; end: number }>,
): TimelineRow[] {
  return rows.map((candidate) => {
    if (candidate.id !== rowId) {
      return candidate;
    }

    return {
      ...candidate,
      actions: candidate.actions.map((timelineAction) => {
        const update = updates[timelineAction.id];
        return update ? { ...timelineAction, ...update } : timelineAction;
      }),
    };
  });
}

function renderStatefulPinnedGroupCanvas(params: {
  initialRow?: TimelineRow;
  initialShotGroup?: NonNullable<React.ComponentProps<typeof TimelineCanvas>['shotGroups']>[number];
  actionId: string;
  startLeft?: number;
  scale?: number;
  scaleWidth?: number;
}) {
  const dataRef = { current: null };
  const onClipEdgeResizeEndSpy = vi.fn();
  const initialRow = params.initialRow ?? pinnedGroupRow;
  const initialShotGroup = params.initialShotGroup ?? pinnedShotGroup;

  useTimelineMutableAdaptersMock.mockReturnValue({
    dataRef,
    pendingOpsRef: { current: 0 },
    interactionStateRef: { current: createInteractionState() },
    selectedClipIdsRef: { current: new Set<string>() },
    additiveSelectionRef: { current: false },
  });

  function Harness() {
    const [rows, setRows] = useState<TimelineRow[]>([cloneRowState(initialRow)]);
    const shotGroups = useMemo(
      () => [materializeShotGroup(initialShotGroup, rows)],
      [rows],
    );

    return (
      <TimelineCanvas
        rows={rows}
        tracks={[track]}
        deviceClass="desktop"
        inputModality="mouse"
        interactionMode="select"
        gestureOwner="none"
        scale={params.scale ?? 1}
        scaleWidth={params.scaleWidth ?? 100}
        scaleSplitCount={1}
        startLeft={params.startLeft ?? 0}
        rowHeight={48}
        minScaleCount={1}
        maxScaleCount={10}
        selectedTrackId={null}
        getActionRender={() => <div>clip</div>}
        onSelectTrack={vi.fn()}
        onTrackChange={vi.fn()}
        onRemoveTrack={vi.fn()}
        onTrackDragEnd={vi.fn()}
        trackSensors={[] as never}
        onCursorDrag={vi.fn()}
        onClickTimeArea={vi.fn()}
        setInputModalityFromPointerType={setInputModalityFromPointerType}
        setGestureOwner={setGestureOwner}
        onActionResizeStart={vi.fn()}
        onClipEdgeResizeEnd={(resizeParams) => {
          onClipEdgeResizeEndSpy(resizeParams);
          if (resizeParams.cancelled) {
            return;
          }
          setRows((currentRows) => applyRowUpdates(
            currentRows,
            resizeParams.session.rowId,
            Object.fromEntries(
              resizeParams.updates.map((update) => [
                update.clipId,
                { start: update.start, end: update.end },
              ]),
            ),
          ));
        }}
        shotGroups={shotGroups}
        dragSessionRef={{ current: null }}
      />
    );
  }

  const renderResult = render(<Harness />);

  const getActionElement = (actionId: string) => {
    const element = renderResult.container.querySelector(`[data-action-id="${actionId}"]`);
    if (!(element instanceof HTMLElement)) {
      throw new Error(`expected action element for ${actionId}`);
    }
    return element;
  };

  return {
    ...renderResult,
    onClipEdgeResizeEndSpy,
    getActionElement,
    getHandle: (actionId: string, side: 'left' | 'right') => {
      const selector = `[data-resize-edge="${side}"]`;
      const handle = getActionElement(actionId).querySelector(selector);
      if (!(handle instanceof HTMLElement)) {
        throw new Error(`expected ${side} handle for ${actionId}`);
      }
      return handle;
    },
  };
}

function renderCanvas(params?: {
  interactionStateRef?: React.MutableRefObject<{ drag: boolean; resize: boolean }>;
  dataRef?: { current: any };
  onActionResizeStart?: ReturnType<typeof vi.fn>;
  onClipEdgeResizeEnd?: ReturnType<typeof vi.fn>;
  getActionRender?: ReturnType<typeof vi.fn>;
  track?: TrackDefinition;
  row?: TimelineRow;
  actionId?: string;
  shotGroups?: React.ComponentProps<typeof TimelineCanvas>['shotGroups'];
  finalVideoMap?: React.ComponentProps<typeof TimelineCanvas>['finalVideoMap'];
  onShotGroupNavigate?: React.ComponentProps<typeof TimelineCanvas>['onShotGroupNavigate'];
  onSelectClips?: React.ComponentProps<typeof TimelineCanvas>['onSelectClips'];
  onShotGroupUnpin?: React.ComponentProps<typeof TimelineCanvas>['onShotGroupUnpin'];
  onShotGroupDelete?: React.ComponentProps<typeof TimelineCanvas>['onShotGroupDelete'];
  onShotGroupSwitchToFinalVideo?: React.ComponentProps<typeof TimelineCanvas>['onShotGroupSwitchToFinalVideo'];
  onShotGroupSwitchToImages?: React.ComponentProps<typeof TimelineCanvas>['onShotGroupSwitchToImages'];
  allowMissingHandles?: boolean;
  deviceClass?: React.ComponentProps<typeof TimelineCanvas>['deviceClass'];
  inputModality?: React.ComponentProps<typeof TimelineCanvas>['inputModality'];
  interactionMode?: React.ComponentProps<typeof TimelineCanvas>['interactionMode'];
  gestureOwner?: React.ComponentProps<typeof TimelineCanvas>['gestureOwner'];
  startLeft?: number;
  scale?: number;
  scaleWidth?: number;
  tracks?: TrackDefinition[];
  rows?: TimelineRow[];
}) {
  const dataRef = params?.dataRef ?? { current: null };
  const trackDefinitions = params?.tracks ?? [params?.track ?? track];
  const timelineRows = params?.rows ?? [params?.row ?? row];
  useTimelineMutableAdaptersMock.mockReturnValue({
    dataRef,
    pendingOpsRef: { current: 0 },
    interactionStateRef: params?.interactionStateRef ?? { current: createInteractionState() },
    selectedClipIdsRef: { current: new Set<string>() },
    additiveSelectionRef: { current: false },
  });

  const onActionResizeStart = params?.onActionResizeStart ?? vi.fn();
  const onClipEdgeResizeEnd = params?.onClipEdgeResizeEnd ?? vi.fn();
  const getActionRender = params?.getActionRender ?? vi.fn(() => <div>clip</div>);

  const renderResult = render(
    <TimelineCanvas
      rows={timelineRows}
      tracks={trackDefinitions}
      deviceClass={params?.deviceClass ?? 'desktop'}
      inputModality={params?.inputModality ?? 'mouse'}
      interactionMode={params?.interactionMode ?? 'select'}
      gestureOwner={params?.gestureOwner ?? 'none'}
      scale={params?.scale ?? 1}
      scaleWidth={params?.scaleWidth ?? 100}
      scaleSplitCount={1}
      startLeft={params?.startLeft ?? 0}
      rowHeight={48}
      minScaleCount={1}
      maxScaleCount={10}
      selectedTrackId={null}
      getActionRender={getActionRender}
      onSelectTrack={vi.fn()}
      onTrackChange={vi.fn()}
      onRemoveTrack={vi.fn()}
      onTrackDragEnd={vi.fn()}
      trackSensors={[] as never}
      onCursorDrag={vi.fn()}
      onClickTimeArea={vi.fn()}
      setInputModalityFromPointerType={setInputModalityFromPointerType}
      setGestureOwner={setGestureOwner}
      onActionResizeStart={onActionResizeStart}
      onClipEdgeResizeEnd={onClipEdgeResizeEnd}
      shotGroups={params?.shotGroups}
      finalVideoMap={params?.finalVideoMap}
      onShotGroupNavigate={params?.onShotGroupNavigate}
      onSelectClips={params?.onSelectClips}
      onShotGroupUnpin={params?.onShotGroupUnpin}
      onShotGroupDelete={params?.onShotGroupDelete}
      onShotGroupSwitchToFinalVideo={params?.onShotGroupSwitchToFinalVideo}
      onShotGroupSwitchToImages={params?.onShotGroupSwitchToImages}
      interactionStateRef={params?.interactionStateRef}
      dragSessionRef={{ current: null }}
    />,
  );

  const targetRow = timelineRows.find((candidate) => candidate.actions.length > 0) ?? timelineRows[0];
  const targetActionId = params?.actionId ?? targetRow?.actions[0]?.id ?? 'clip-1';
  const actionElement = renderResult.container.querySelector(`[data-action-id="${targetActionId}"]`);
  if (!(actionElement instanceof HTMLElement)) {
    throw new Error('expected action element');
  }

  // Identify handles by their rounding class so we don't mis-label when
  // only one of the two is rendered (e.g. for first/last children of a
  // pinned shot group, where only one interior boundary exists).
  const leftHandle = actionElement.querySelector('[data-resize-edge="left"]');
  const rightHandle = actionElement.querySelector('[data-resize-edge="right"]');
  if (!params?.allowMissingHandles && (!(leftHandle instanceof HTMLElement) || !(rightHandle instanceof HTMLElement))) {
    throw new Error('expected resize handles');
  }

  return {
    ...renderResult,
    actionElement,
    leftHandle: leftHandle instanceof HTMLElement ? leftHandle : null,
    rightHandle: rightHandle instanceof HTMLElement ? rightHandle : null,
    getShotGroupHandle: (side: 'left' | 'right') => {
      const handle = renderResult.container.querySelector(`[data-shot-group-resize-handle="${side}"]`);
      if (!(handle instanceof HTMLElement)) {
        throw new Error(`expected ${side} shot group handle`);
      }
      return handle;
    },
    onActionResizeStart,
    onClipEdgeResizeEnd,
    getActionRender,
  };
}

afterEach(() => {
  useTimelineMutableAdaptersMock.mockReset();
  setGestureOwner.mockReset();
  setInputModalityFromPointerType.mockClear();
});

describe('TimelineCanvas resize pending ops', () => {
  it('sizes the playhead to the full scrollable timeline content height', () => {
    const secondTrack: TrackDefinition = { id: 'V2', kind: 'visual', label: 'V2' };
    const secondRow: TimelineRow = {
      id: 'V2',
      actions: [{ id: 'clip-2', start: 1, end: 3, effectId: 'effect-clip-2' }],
    };

    const { getByTestId } = renderCanvas({
      tracks: [track, secondTrack],
      rows: [row, secondRow],
    });

    expect(getByTestId('timeline-playhead')).toHaveStyle({ height: '144px' });
  });

  it('sets interactionStateRef.resize on resize start and clears on resize end', () => {
    const interactionStateRef = { current: createInteractionState() };
    const { leftHandle, onActionResizeStart, onClipEdgeResizeEnd } = renderCanvas({ interactionStateRef });
    if (!leftHandle) throw new Error('expected left handle');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 7,
      clientX: 120,
    });

    expect(interactionStateRef.current.resize).toBe(false);
    expect(onActionResizeStart).toHaveBeenCalledTimes(0);

    fireEvent.pointerMove(leftHandle, {
      pointerId: 7,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(true);
    expect(onActionResizeStart).toHaveBeenCalledTimes(1);

    fireEvent.pointerUp(leftHandle, {
      pointerId: 7,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(false);
    expect(onClipEdgeResizeEnd).toHaveBeenCalledTimes(1);
  });

  it('clears interactionStateRef.resize on pointercancel and reports a cancelled resize end', () => {
    const interactionStateRef = { current: createInteractionState() };
    const { leftHandle, onClipEdgeResizeEnd } = renderCanvas({ interactionStateRef });
    if (!leftHandle) throw new Error('expected left handle');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 8,
      clientX: 120,
    });

    expect(interactionStateRef.current.resize).toBe(false);

    fireEvent.pointerMove(leftHandle, {
      pointerId: 8,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(true);

    fireEvent.pointerCancel(leftHandle, {
      pointerId: 8,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(false);
    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: true,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'left', rowId: 'V1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0, end: 2 }),
      ]),
    }));
  });

  it('toggles interactionStateRef.resize with the resize lifecycle', () => {
    const interactionStateRef = { current: createInteractionState() };
    const { leftHandle } = renderCanvas({ interactionStateRef });
    if (!leftHandle) throw new Error('expected left handle');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 18,
      clientX: 120,
    });

    expect(interactionStateRef.current.resize).toBe(false);

    fireEvent.pointerMove(leftHandle, {
      pointerId: 18,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(true);

    fireEvent.pointerUp(leftHandle, {
      pointerId: 18,
      clientX: 112,
    });

    expect(interactionStateRef.current.resize).toBe(false);
  });

  it('gates touch trim ownership and resize state until the trim threshold is crossed', () => {
    setInputModalityFromPointerType.mockReturnValue('touch');
    const interactionStateRef = { current: createInteractionState() };
    const { leftHandle, onActionResizeStart, onClipEdgeResizeEnd } = renderCanvas({
      deviceClass: 'tablet',
      inputModality: 'touch',
      interactionMode: 'trim',
      interactionStateRef,
    });
    if (!leftHandle) throw new Error('expected left handle');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 27,
      pointerType: 'touch',
      clientX: 120,
    });

    expect(setGestureOwner).not.toHaveBeenCalled();
    expect(onActionResizeStart).not.toHaveBeenCalled();
    expect(interactionStateRef.current.resize).toBe(false);

    fireEvent.pointerMove(leftHandle, {
      pointerId: 27,
      pointerType: 'touch',
      clientX: 118,
    });

    expect(setGestureOwner).not.toHaveBeenCalled();
    expect(onActionResizeStart).not.toHaveBeenCalled();
    expect(interactionStateRef.current.resize).toBe(false);

    fireEvent.pointerMove(leftHandle, {
      pointerId: 27,
      pointerType: 'touch',
      clientX: 110,
    });

    expect(setGestureOwner).toHaveBeenNthCalledWith(1, 'trim');
    expect(onActionResizeStart).toHaveBeenCalledTimes(1);
    expect(interactionStateRef.current.resize).toBe(true);

    fireEvent.pointerUp(leftHandle, {
      pointerId: 27,
      pointerType: 'touch',
      clientX: 110,
    });

    expect(setGestureOwner).toHaveBeenLastCalledWith('none');
    expect(onClipEdgeResizeEnd).toHaveBeenCalledTimes(1);
    expect(interactionStateRef.current.resize).toBe(false);
  });

  it('clears resize preview and completes release on pointerup without pointer capture', () => {
    const interactionStateRef = { current: createInteractionState() };
    const onInteractionEndSpy = vi.fn();
    onInteractionEnd(interactionStateRef, onInteractionEndSpy);
    const { actionElement, rightHandle, onClipEdgeResizeEnd } = renderCanvas({ interactionStateRef });
    if (!rightHandle) throw new Error('expected right handle');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 19,
      clientX: 200,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 19,
      clientX: 300,
    });

    expect(actionElement.style.width).toBe('300px');
    expect(interactionStateRef.current.resize).toBe(true);

    fireEvent.pointerUp(rightHandle, {
      pointerId: 19,
      clientX: 300,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'right', rowId: 'V1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0, end: 3 }),
      ]),
    }));
    expect(actionElement.style.width).toBe('200px');
    expect(interactionStateRef.current.resize).toBe(false);
    expect(onInteractionEndSpy).toHaveBeenCalledTimes(1);
  });

  it('passes the rendered clip width into getActionRender', () => {
    const getActionRender = vi.fn(() => <div>clip</div>);
    renderCanvas({ getActionRender });

    expect(getActionRender).toHaveBeenCalledWith(action, row, 200);
  });

  it('clamps right-edge audio resize preview to the source duration and clears the ring on resize end', () => {
    const audioTrack: TrackDefinition = { id: 'A1', kind: 'audio', label: 'A1' };
    const audioAction: TimelineAction = { id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' };
    const audioRow: TimelineRow = { id: 'A1', actions: [audioAction] };
    const dataRef = {
      current: {
        meta: {
          'clip-1': { track: 'A1', clipType: 'media', asset: 'asset-1', from: 1, speed: 1 },
        },
        tracks: [audioTrack],
        resolvedConfig: {
          registry: {
            'asset-1': { duration: 3.5 },
          },
        },
        registry: {
          assets: {
            'asset-1': { duration: 3.5 },
          },
        },
      },
    };
    const { actionElement, rightHandle, onClipEdgeResizeEnd } = renderCanvas({
      track: audioTrack,
      row: audioRow,
      dataRef,
    });
    if (!rightHandle) throw new Error('expected right handle');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 9,
      clientX: 200,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 9,
      clientX: 400,
    });

    expect(actionElement.className).toContain('ring-amber-400/80');

    fireEvent.pointerUp(rightHandle, {
      pointerId: 9,
      clientX: 400,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'right', rowId: 'A1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0, end: 2.5 }),
      ]),
    }));
    expect(actionElement.className).not.toContain('ring-amber-400/80');
  });

  it('clamps left-edge audio resize preview before source time zero', () => {
    const audioTrack: TrackDefinition = { id: 'A1', kind: 'audio', label: 'A1' };
    const audioAction: TimelineAction = { id: 'clip-1', start: 2, end: 4, effectId: 'effect-clip-1' };
    const audioRow: TimelineRow = { id: 'A1', actions: [audioAction] };
    const dataRef = {
      current: {
        meta: {
          'clip-1': { track: 'A1', clipType: 'media', asset: 'asset-1', from: 1, speed: 1 },
        },
        tracks: [audioTrack],
        resolvedConfig: {
          registry: {
            'asset-1': { duration: 5 },
          },
        },
        registry: {
          assets: {
            'asset-1': { duration: 5 },
          },
        },
      },
    };
    const { actionElement, leftHandle, onClipEdgeResizeEnd } = renderCanvas({
      track: audioTrack,
      row: audioRow,
      dataRef,
    });
    if (!leftHandle) throw new Error('expected left handle');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 10,
      clientX: 200,
    });

    fireEvent.pointerMove(leftHandle, {
      pointerId: 10,
      clientX: -100,
    });

    expect(actionElement.className).toContain('ring-amber-400/80');

    fireEvent.pointerUp(leftHandle, {
      pointerId: 10,
      clientX: -100,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'left', rowId: 'A1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 1, end: 4 }),
      ]),
    }));
    expect(actionElement.className).not.toContain('ring-amber-400/80');
  });

  it('anchors free clip preview to the real boundary pixel when the handle is grabbed off-center', () => {
    const { actionElement, rightHandle, onClipEdgeResizeEnd } = renderCanvas({ startLeft: 25 });
    if (!rightHandle) throw new Error('expected right handle');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 30,
      clientX: 221,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 30,
      clientX: 271,
    });

    expect(actionElement.style.width).toBe('250px');

    fireEvent.pointerUp(rightHandle, {
      pointerId: 30,
      clientX: 271,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'right', rowId: 'V1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0, end: 2.5 }),
      ]),
    }));
  });

  it('snaps a free clip edge to sibling boundaries on release', () => {
    const snappingRow: TimelineRow = {
      id: 'V1',
      actions: [
        { id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' },
        { id: 'clip-2', start: 3, end: 4, effectId: 'effect-clip-2' },
      ],
    };
    const { actionElement, rightHandle, onClipEdgeResizeEnd } = renderCanvas({
      row: snappingRow,
      actionId: 'clip-1',
    });
    if (!rightHandle) throw new Error('expected right handle');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 34,
      clientX: 200,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 34,
      clientX: 295,
    });

    expect(actionElement.style.width).toBe('300px');

    fireEvent.pointerUp(rightHandle, {
      pointerId: 34,
      clientX: 295,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({ clipId: 'clip-1', edge: 'right', rowId: 'V1' }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0, end: 3 }),
      ]),
    }));
  });

  it('anchors interior pinned-group boundary preview to the real boundary pixel when grabbed off-center', () => {
    const { container, actionElement, rightHandle, onClipEdgeResizeEnd } = renderCanvas({
      row: pinnedGroupRow,
      actionId: 'clip-2',
      shotGroups: [pinnedShotGroup],
      allowMissingHandles: true,
      startLeft: 25,
    });
    if (!rightHandle) throw new Error('expected right handle');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 31,
      clientX: 221,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 31,
      clientX: 251,
    });

    const adjacentElement = container.querySelector('[data-action-id="clip-3"]');
    if (!(adjacentElement instanceof HTMLElement)) {
      throw new Error('expected adjacent action element');
    }

    expect(Number.parseFloat(actionElement.style.width)).toBeCloseTo(130, 5);
    expect(Number.parseFloat(adjacentElement.style.left)).toBeCloseTo(255, 5);

    fireEvent.pointerUp(rightHandle, {
      pointerId: 31,
      clientX: 251,
    });

    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({
        clipId: 'clip-2',
        edge: 'right',
        rowId: 'V1',
        context: expect.objectContaining({ kind: 'group' }),
      }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-2', start: 1, end: 2.3 }),
        expect.objectContaining({ clipId: 'clip-3', start: 2.3, end: 3.3 }),
      ]),
    }));
  });

  it('keeps the interior pinned-group boundary fixed on release after a pointer drag', () => {
    const { getActionElement, getHandle, onClipEdgeResizeEndSpy } = renderStatefulPinnedGroupCanvas({
      actionId: 'clip-2',
      startLeft: 25,
    });
    const rightHandle = getHandle('clip-2', 'right');

    fireEvent.pointerDown(rightHandle, {
      button: 0,
      pointerId: 32,
      clientX: 221,
    });

    fireEvent.pointerMove(rightHandle, {
      pointerId: 32,
      clientX: 251,
    });

    const previewBoundaryLeft = Number.parseFloat(getActionElement('clip-3').style.left);
    const previewDraggedWidth = Number.parseFloat(getActionElement('clip-2').style.width);
    expect(previewBoundaryLeft).toBeCloseTo(255, 5);
    expect(previewDraggedWidth).toBeCloseTo(130, 5);

    fireEvent.pointerUp(rightHandle, {
      pointerId: 32,
      clientX: 251,
    });

    expect(Number.parseFloat(getActionElement('clip-3').style.left)).toBeCloseTo(previewBoundaryLeft, 5);
    expect(Number.parseFloat(getActionElement('clip-2').style.width)).toBeCloseTo(previewDraggedWidth, 5);
    expect(onClipEdgeResizeEndSpy).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({
        clipId: 'clip-2',
        edge: 'right',
        context: expect.objectContaining({ kind: 'group' }),
      }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-2', start: 1, end: 2.3 }),
        expect.objectContaining({ clipId: 'clip-3', start: 2.3, end: 3.3 }),
      ]),
    }));
  });

  it('renders interior boundary resize handles for middle pinned-group children', () => {
    // The middle child has both interior boundaries (between clip-1/clip-2
    // on the left and clip-2/clip-3 on the right), so both handles render.
    const { leftHandle, rightHandle } = renderCanvas({
      row: pinnedGroupRow,
      actionId: 'clip-2',
      shotGroups: [pinnedShotGroup],
      allowMissingHandles: true,
    });

    expect(leftHandle).not.toBeNull();
    expect(rightHandle).not.toBeNull();
  });

  it('renders outer-edge resize handles on first/last pinned-group children (delegated to group edge resize)', () => {
    // First and last children render BOTH handles. Their outer edge handle
    // (left for first, right for last) is routed to the shot-group edge
    // resize so the user can grab the group's outer edge directly from the
    // clip handle in addition to the dedicated round overlay handle.
    const first = renderCanvas({
      row: pinnedGroupRow,
      actionId: 'clip-1',
      shotGroups: [pinnedShotGroup],
      allowMissingHandles: true,
    });
    expect(first.leftHandle).not.toBeNull();
    expect(first.rightHandle).not.toBeNull();

    const last = renderCanvas({
      row: pinnedGroupRow,
      actionId: 'clip-3',
      shotGroups: [pinnedShotGroup],
      allowMissingHandles: true,
    });
    expect(last.leftHandle).not.toBeNull();
    expect(last.rightHandle).not.toBeNull();
  });

  it('renders pinned shot groups from group.start and children rather than clip array order', () => {
    const unorderedRow: TimelineRow = {
      id: 'V1',
      actions: [
        { id: 'clip-3', start: 3, end: 4, effectId: 'effect-clip-3' },
        { id: 'clip-1', start: 1, end: 2, effectId: 'effect-clip-1' },
        { id: 'clip-2', start: 2, end: 3, effectId: 'effect-clip-2' },
      ],
    };
    const unorderedGroup: NonNullable<React.ComponentProps<typeof TimelineCanvas>['shotGroups']>[number] = {
      ...pinnedShotGroup,
      start: 1,
      clipIds: ['clip-3', 'clip-1', 'clip-2'],
      children: [
        { clipId: 'clip-1', offset: 0, duration: 1 },
        { clipId: 'clip-2', offset: 1, duration: 1 },
        { clipId: 'clip-3', offset: 2, duration: 1 },
      ],
    };

    const { getByText, getByTitle } = renderCanvas({
      row: unorderedRow,
      shotGroups: [unorderedGroup],
      allowMissingHandles: true,
    });

    expect(getByText('Pinned Shot')).toBeTruthy();
    const label = getByTitle('Pinned Shot') as HTMLElement;
    expect(label).toBeTruthy();
    expect(label.style.left).toBe('100px');
    expect(label.style.width).toBe('300px');
  });

  it('routes the first child clip\'s outer-left handle through the pinned-group outer resize session', () => {
    const onClipEdgeResizeEnd = vi.fn();
    const { actionElement, leftHandle, onActionResizeStart } = renderCanvas({
      row: shiftedPinnedGroupRow,
      actionId: 'clip-1',
      shotGroups: [{
        ...pinnedShotGroup,
        start: 1,
      }],
      dataRef: {
        current: {
          config: {
            output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
            tracks: [track],
            clips: [
              { id: 'clip-1', at: 1, track: 'V1', clipType: 'hold', hold: 1 },
              { id: 'clip-2', at: 2, track: 'V1', clipType: 'hold', hold: 1 },
              { id: 'clip-3', at: 3, track: 'V1', clipType: 'hold', hold: 1 },
            ],
            pinnedShotGroups: [{
              shotId: 'shot-1',
              trackId: 'V1',
              start: 1,
              clipIds: ['clip-1', 'clip-2', 'clip-3'],
              children: [
                { clipId: 'clip-1', offset: 0, duration: 1 },
                { clipId: 'clip-2', offset: 1, duration: 1 },
                { clipId: 'clip-3', offset: 2, duration: 1 },
              ],
              mode: 'images',
            }],
          },
        },
      },
      onClipEdgeResizeEnd,
      allowMissingHandles: true,
      startLeft: 25,
    });

    if (!leftHandle) throw new Error('expected outer-left clip handle on first child');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 12,
      clientX: 121,
    });

    fireEvent.pointerMove(leftHandle, {
      pointerId: 12,
      clientX: 71,
    });

    expect(actionElement.style.left).toBe('75px');

    fireEvent.pointerUp(leftHandle, {
      pointerId: 12,
      clientX: 71,
    });

    expect(onActionResizeStart).not.toHaveBeenCalled();
    expect(onClipEdgeResizeEnd).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({
        clipId: 'clip-1',
        edge: 'left',
        rowId: 'V1',
        context: expect.objectContaining({ kind: 'group', shotId: 'shot-1', trackId: 'V1' }),
      }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0.5, end: 2 }),
        expect.objectContaining({ clipId: 'clip-2', start: 2, end: 3 }),
        expect.objectContaining({ clipId: 'clip-3', start: 3, end: 4 }),
      ]),
    }));
  });

  it('keeps the outer-left preview boundary fixed on release after a pointer drag', () => {
    const { getActionElement, getHandle, onClipEdgeResizeEndSpy } = renderStatefulPinnedGroupCanvas({
      initialRow: shiftedPinnedGroupRow,
      initialShotGroup: {
        ...pinnedShotGroup,
        start: 1,
      },
      actionId: 'clip-1',
      startLeft: 25,
    });
    const leftHandle = getHandle('clip-1', 'left');

    fireEvent.pointerDown(leftHandle, {
      button: 0,
      pointerId: 33,
      clientX: 121,
    });

    fireEvent.pointerMove(leftHandle, {
      pointerId: 33,
      clientX: 71,
    });

    const previewLeft = Number.parseFloat(getActionElement('clip-1').style.left);
    expect(previewLeft).toBeCloseTo(75, 5);

    fireEvent.pointerUp(leftHandle, {
      pointerId: 33,
      clientX: 71,
    });

    expect(Number.parseFloat(getActionElement('clip-1').style.left)).toBeCloseTo(previewLeft, 5);
    expect(onClipEdgeResizeEndSpy).toHaveBeenCalledWith(expect.objectContaining({
      cancelled: false,
      session: expect.objectContaining({
        clipId: 'clip-1',
        edge: 'left',
        context: expect.objectContaining({ kind: 'group', shotId: 'shot-1', trackId: 'V1' }),
      }),
      updates: expect.arrayContaining([
        expect.objectContaining({ clipId: 'clip-1', start: 0.5, end: 2 }),
        expect.objectContaining({ clipId: 'clip-2', start: 2, end: 3 }),
        expect.objectContaining({ clipId: 'clip-3', start: 3, end: 4 }),
      ]),
    }));
  });

  it('renders all shot groups with solid borders and always shows the shot name label', () => {
    const { container, getByText, getAllByTitle } = renderCanvas({
      shotGroups: [
        {
          shotId: 'shot-a',
          shotName: 'Shot A',
          rowId: 'V1',
          rowIndex: 0,
          start: 0,
          clipIds: ['clip-1'],
          children: [{ clipId: 'clip-1', offset: 0, duration: 2 }],
          color: '#3b82f6',
        },
        {
          shotId: 'shot-b',
          shotName: 'Shot B',
          rowId: 'V1',
          rowIndex: 0,
          start: 0,
          clipIds: ['clip-1'],
          children: [{ clipId: 'clip-1', offset: 0, duration: 2 }],
          color: '#22c55e',
          mode: 'images',
        },
      ],
      allowMissingHandles: true,
    });

    expect(container.innerHTML).not.toContain('border-dashed');
    expect(container.innerHTML).toContain('border-solid');
    expect(getAllByTitle(/Shot [AB]/)).toHaveLength(2);
    expect(getByText('Shot A')).toBeTruthy();
    expect(getByText('Shot B')).toBeTruthy();
  });

  it('renders the first-row shot group label in an overlay above the tracks without adding layout headroom', () => {
    const { container, getByTitle } = renderCanvas({
      shotGroups: [pinnedShotGroup],
      allowMissingHandles: true,
    });

    const gridSurface = container.querySelector('.timeline-canvas-edit-area > .relative');
    if (!(gridSurface instanceof HTMLElement)) {
      throw new Error('expected timeline grid surface');
    }

    expect(gridSurface.style.paddingTop).toBe('');
    expect(getByTitle('Pinned Shot')).toHaveStyle({
      top: '16px',
      height: '18px',
    });
  });

  it('double-clicks a shot group label to jump to the shot', () => {
    const onShotGroupNavigate = vi.fn();
    const { getByTitle } = renderCanvas({
      shotGroups: [pinnedShotGroup],
      onShotGroupNavigate,
      allowMissingHandles: true,
    });

    fireEvent.doubleClick(getByTitle('Pinned Shot'));

    expect(onShotGroupNavigate).toHaveBeenCalledWith('shot-1');
  });

  it('single-clicks a shot group label to select the group clips', () => {
    const onSelectClips = vi.fn();
    const { getByTitle } = renderCanvas({
      shotGroups: [pinnedShotGroup],
      onSelectClips,
      allowMissingHandles: true,
    });

    fireEvent.click(getByTitle('Pinned Shot'));

    expect(onSelectClips).toHaveBeenCalledWith(['clip-1', 'clip-2', 'clip-3']);
  });

  it('shows deconstruct/delete and switch-to-video actions for pinned groups with a final video', () => {
    const onShotGroupSwitchToFinalVideo = vi.fn();
    const onShotGroupUnpin = vi.fn();
    const onShotGroupDelete = vi.fn();
    const { getByTitle } = renderCanvas({
      shotGroups: [{
        shotId: 'shot-1',
        shotName: 'Pinned Shot',
        rowId: 'V1',
        rowIndex: 0,
        start: 0,
        clipIds: ['clip-1'],
        children: [{ clipId: 'clip-1', offset: 0, duration: 2 }],
        color: '#22c55e',
        mode: 'images',
      }],
      finalVideoMap: new Map([['shot-1', {}]]),
      onShotGroupUnpin,
      onShotGroupDelete,
      onShotGroupSwitchToFinalVideo,
      allowMissingHandles: true,
    });

    fireEvent.contextMenu(getByTitle('Pinned Shot'));

    expect(screen.getByText('Deconstruct shot')).toBeTruthy();
    expect(screen.getByText('Delete shot')).toBeTruthy();
    expect(screen.getByText('Switch to Final Video')).toBeTruthy();
    expect(screen.queryByText('Pin as Shot Group')).toBeNull();
    expect(screen.queryByText('Switch to Images')).toBeNull();

    fireEvent.click(screen.getByText('Switch to Final Video'));

    expect(onShotGroupSwitchToFinalVideo).toHaveBeenCalledWith({
      shotId: 'shot-1',
      clipIds: ['clip-1'],
      rowId: 'V1',
    });
  });

  it('shows deconstruct/delete and switch-to-images actions for pinned video groups', () => {
    const onShotGroupUnpin = vi.fn();
    const onShotGroupDelete = vi.fn();
    const onShotGroupSwitchToImages = vi.fn();
    const { getByTitle } = renderCanvas({
      shotGroups: [{
        shotId: 'shot-1',
        shotName: 'Pinned Shot',
        rowId: 'V1',
        rowIndex: 0,
        start: 0,
        clipIds: ['clip-1'],
        children: [{ clipId: 'clip-1', offset: 0, duration: 2 }],
        color: '#3b82f6',
        mode: 'video',
      }],
      finalVideoMap: new Map([['shot-1', {}]]),
      onShotGroupUnpin,
      onShotGroupDelete,
      onShotGroupSwitchToImages,
      allowMissingHandles: true,
    });

    fireEvent.contextMenu(getByTitle('Pinned Shot'));

    expect(screen.getByText('Deconstruct shot')).toBeTruthy();
    expect(screen.getByText('Delete shot')).toBeTruthy();
    expect(screen.getByText('Switch to Images')).toBeTruthy();
    expect(screen.queryByText('Pin as Shot Group')).toBeNull();
    expect(screen.queryByText('Switch to Final Video')).toBeNull();

    fireEvent.click(screen.getByText('Switch to Images'));
    expect(onShotGroupSwitchToImages).toHaveBeenCalledWith({ shotId: 'shot-1', rowId: 'V1' });

    fireEvent.contextMenu(getByTitle('Pinned Shot'));
    fireEvent.click(screen.getByText('Deconstruct shot'));
    expect(onShotGroupUnpin).toHaveBeenCalledWith({ shotId: 'shot-1', trackId: 'V1' });

    fireEvent.contextMenu(getByTitle('Pinned Shot'));
    fireEvent.click(screen.getByText('Delete shot'));
    expect(onShotGroupDelete).toHaveBeenCalledWith({ shotId: 'shot-1', trackId: 'V1', clipIds: ['clip-1'] });
  });

  it('shows a visible shot-group actions trigger on touch layouts with reachable menu actions', () => {
    const onShotGroupNavigate = vi.fn();
    const onShotGroupSwitchToFinalVideo = vi.fn();
    renderCanvas({
      deviceClass: 'phone',
      shotGroups: [pinnedShotGroup],
      finalVideoMap: new Map([['shot-1', {}]]),
      onShotGroupNavigate,
      onShotGroupSwitchToFinalVideo,
      allowMissingHandles: true,
    });

    fireEvent.click(screen.getByLabelText('Open actions for Pinned Shot'));

    expect(screen.getByText('Jump to Shot')).toBeInTheDocument();
    expect(screen.getByText('Switch to Final Video')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Jump to Shot'));

    expect(onShotGroupNavigate).toHaveBeenCalledWith('shot-1');

    fireEvent.click(screen.getByLabelText('Open actions for Pinned Shot'));
    fireEvent.click(screen.getByText('Switch to Final Video'));

    expect(onShotGroupSwitchToFinalVideo).toHaveBeenCalledWith({
      shotId: 'shot-1',
      clipIds: ['clip-1', 'clip-2', 'clip-3'],
      rowId: 'V1',
    });
  });
});
