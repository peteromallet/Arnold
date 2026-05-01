import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type UIEvent,
} from 'react';
import { type DragEndEvent, useSensors } from '@dnd-kit/core';
import { Layers, Sparkles } from 'lucide-react';
import { usePortalMousedownGuard } from '@/shared/hooks/usePortalMousedownGuard';
import {
  ShotGroupBorders,
  ShotGroupLabels,
  type PositionedShotGroup,
} from '@/tools/video-editor/components/TimelineEditor/ShotGroupOverlay';
import {
  ShotGroupContextMenu,
  type ShotGroupMenuState,
} from '@/tools/video-editor/components/TimelineEditor/ShotGroupContextMenu';
import {
  buildGridBackground,
  TimelineRulerAndGrid,
} from '@/tools/video-editor/components/TimelineEditor/TimelineRulerAndGrid';
import { TrackListRenderer } from '@/tools/video-editor/components/TimelineEditor/TrackListRenderer';
import { useClipResizeGesture } from '@/tools/video-editor/hooks/useClipResizeGesture';
import type { ShotGroup } from '@/tools/video-editor/hooks/useShotGroups';
import { useTimelineMutableAdapters } from '@/tools/video-editor/hooks/timelineStore';
import { LABEL_WIDTH } from '@/tools/video-editor/lib/coordinate-utils';
import {
  shouldExpandTouchTrimHandles,
  type TimelineDeviceClass,
  type TimelineGestureOwner,
  type TimelineInputModality,
  type TimelineInteractionMode,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import {
  type ResizeDir,
} from '@/tools/video-editor/lib/resize-math';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { useTimelineScale } from '@/tools/video-editor/hooks/useTimelineScale';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import type { TrackDefinition } from '@/tools/video-editor/types';
import type { TimelineAction, TimelineCanvasHandle, TimelineRow } from '@/tools/video-editor/types/timeline-canvas';
import type { DragSession } from '@/tools/video-editor/hooks/useClipDrag';
import type { ClipEdgeResizeEndTarget } from '@/tools/video-editor/hooks/useClipResize';
import type { MarqueeRect } from '@/tools/video-editor/hooks/useMarqueeSelect';
import {
  ACTION_VERTICAL_MARGIN,
  CURSOR_WIDTH,
  EMPTY_RESIZE_PREVIEW_SNAPSHOT,
  MIN_ACTION_WIDTH_PX,
  RESIZE_HANDLE_WIDTH,
  TOUCH_RESIZE_HANDLE_WIDTH,
  type ResizeOverride,
} from './timeline-canvas-constants';

interface ScrollMetrics {
  scrollLeft: number;
  scrollTop: number;
}

export interface TimelineCanvasProps {
  rows: TimelineRow[];
  tracks: TrackDefinition[];
  deviceClass: TimelineDeviceClass;
  inputModality: TimelineInputModality;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  scale: number;
  scaleWidth: number;
  scaleSplitCount: number;
  startLeft: number;
  rowHeight: number;
  minScaleCount: number;
  maxScaleCount: number;
  selectedTrackId: string | null;
  getActionRender?: (action: TimelineAction, row: TimelineRow, width: number) => ReactNode;
  onSelectTrack: (trackId: string) => void;
  onTrackChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  onRemoveTrack: (trackId: string) => void;
  onTrackDragEnd: (event: DragEndEvent) => void;
  trackSensors: ReturnType<typeof useSensors>;
  onCursorDrag: (time: number) => void;
  onClickTimeArea: (time: number) => void;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => TimelineInputModality;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  onActionResizeStart?: (params: {
    action: TimelineAction;
    row: TimelineRow;
    dir: ResizeDir;
  }) => void;
  onActionResizing?: (params: { action: TimelineAction; row: TimelineRow; start: number; end: number; dir: ResizeDir }) => void;
  onClipEdgeResizeEnd?: (params: ClipEdgeResizeEndTarget) => void;
  shotGroups?: ShotGroup[];
  finalVideoMap?: Map<string, unknown>;
  staleShotGroupIds?: Set<string>;
  activeTaskClipIds?: Set<string>;
  onShotGroupNavigate?: (shotId: string) => void;
  onShotGroupGenerateVideo?: (shotId: string) => void;
  onShotGroupSwitchToFinalVideo?: (group: { shotId: string; clipIds: string[]; rowId: string }) => void;
  onShotGroupSwitchToImages?: (group: { shotId: string; rowId: string }) => void;
  onShotGroupUpdateToLatestVideo?: (group: { shotId: string; rowId: string }) => void;
  onShotGroupUnpin?: (group: { shotId: string; trackId: string }) => void;
  onShotGroupDelete?: (group: { shotId: string; trackId: string; clipIds: string[] }) => void;
  onSelectClips?: (clipIds: string[]) => void;
  dragSessionRef?: MutableRefObject<DragSession | null>;
  interactionStateRef?: import('@/tools/video-editor/lib/interaction-state').InteractionStateRef;
  onScroll?: (metrics: ScrollMetrics) => void;
  marqueeRect?: MarqueeRect | null;
  onEditAreaPointerDown?: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onAddTrack?: (kind: 'visual' | 'audio') => void;
  onAddTextAt?: (trackId: string, time: number) => void;
  onOpenSequenceCreator?: () => void;
  unusedTrackCount?: number;
  onClearUnusedTracks?: () => void;
  newTrackDropLabel?: string | null;
}

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

export const TimelineCanvas = forwardRef<TimelineCanvasHandle, TimelineCanvasProps>(function TimelineCanvas({
  rows,
  tracks,
  deviceClass,
  inputModality,
  interactionMode,
  gestureOwner,
  scale,
  scaleWidth,
  scaleSplitCount,
  startLeft,
  rowHeight,
  minScaleCount,
  maxScaleCount,
  selectedTrackId,
  getActionRender,
  onSelectTrack,
  onTrackChange,
  onRemoveTrack,
  onTrackDragEnd,
  trackSensors,
  onCursorDrag,
  onClickTimeArea,
  setInputModalityFromPointerType,
  setGestureOwner,
  onActionResizeStart,
  onActionResizing,
  onClipEdgeResizeEnd,
  shotGroups = [],
  finalVideoMap,
  staleShotGroupIds,
  activeTaskClipIds,
  onShotGroupNavigate,
  onShotGroupGenerateVideo,
  onShotGroupSwitchToFinalVideo,
  onShotGroupSwitchToImages,
  onShotGroupUpdateToLatestVideo,
  onShotGroupUnpin,
  onShotGroupDelete,
  onSelectClips,
  dragSessionRef,
  interactionStateRef,
  onScroll,
  marqueeRect,
  onEditAreaPointerDown,
  onAddTrack,
  onAddTextAt,
  onOpenSequenceCreator,
  unusedTrackCount = 0,
  onClearUnusedTracks,
  newTrackDropLabel,
}: TimelineCanvasProps, ref) {
  useRenderBudget('TimelineCanvas', 3);
  const { dataRef } = useTimelineMutableAdapters();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  const timeRef = useRef(0);
  const playRateRef = useRef(1);
  const scrollMetricsRef = useRef<ScrollMetrics>({ scrollLeft: 0, scrollTop: 0 });
  const [scrollLeft, setScrollLeft] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);
  const [shotGroupMenu, setShotGroupMenu] = useState<ShotGroupMenuState>(null);
  const shotGroupMenuRef = useRef<HTMLDivElement>(null);
  useRenderDiagnostic('TimelineCanvas');

  usePortalMousedownGuard(shotGroupMenuRef, Boolean(shotGroupMenu));

  useEffect(() => {
    if (!shotGroupMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (shotGroupMenuRef.current && !shotGroupMenuRef.current.contains(e.target as Node)) {
        setShotGroupMenu(null);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShotGroupMenu(null);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [shotGroupMenu]);

  const { pixelsPerSecond, pixelToTime, timeToPixel } = useTimelineScale({ scale, scaleWidth, startLeft });
  const resizeHandleWidth = shouldExpandTouchTrimHandles(deviceClass, inputModality, interactionMode)
    ? TOUCH_RESIZE_HANDLE_WIDTH
    : RESIZE_HANDLE_WIDTH;
  const minDuration = MIN_ACTION_WIDTH_PX / pixelsPerSecond;
  const { resizePreviewSnapshot, resizeClampedActionId } = useClipResizeGesture({
    timelineWrapperRef: scrollContainerRef,
    dataRef,
    rows,
    shotGroups,
    gestureOwner,
    setGestureOwner,
    onActionResizeStart,
    onActionResizing,
    onClipEdgeResizeEnd,
    interactionStateRef,
    setInputModalityFromPointerType,
    timeToPixel,
    pixelToTime,
    pixelsPerSecond,
    minDuration,
  });
  const actionHeight = Math.max(12, rowHeight - ACTION_VERTICAL_MARGIN * 2);
  const scrollContentHeight = (rows.length + 1) * rowHeight;
  const maxEnd = useMemo(() => rows.reduce(
    (currentMax, row) => row.actions.reduce((rowMax, action) => Math.max(rowMax, action.end), currentMax),
    0,
  ), [rows]);
  const derivedScaleCount = Math.ceil(maxEnd / Math.max(scale, Number.EPSILON)) + 1;
  const scaleCount = clamp(derivedScaleCount, minScaleCount, maxScaleCount);
  const totalWidth = startLeft + scaleCount * scaleWidth;
  const rowResizePreview = useMemo(
    () => rows.map<Readonly<Record<string, ResizeOverride>>>((row) => {
      let previewForRow: Record<string, ResizeOverride> | null = null;
      for (const action of row.actions) {
        const override = resizePreviewSnapshot[action.id];
        if (!override) {
          continue;
        }

        if (!previewForRow) {
          previewForRow = {};
        }
        previewForRow[action.id] = override;
      }

      return previewForRow ?? EMPTY_RESIZE_PREVIEW_SNAPSHOT;
    }),
    [resizePreviewSnapshot, rows],
  );
  const positionedShotGroups = useMemo(() => {
    return shotGroups.flatMap<PositionedShotGroup>((group) => {
      const row = rows[group.rowIndex];
      if (!row || row.id !== group.rowId) {
        return [];
      }

      const lastChild = group.children[group.children.length - 1];
      if (!lastChild) {
        return [];
      }

      const groupKey = `${group.shotId}:${group.rowId}`;
      const preview = resizePreviewSnapshot[groupKey];
      const start = preview?.start ?? group.start;
      const end = preview?.end ?? (group.start + lastChild.offset + lastChild.duration);

      return [{
        key: `${group.shotId}:${group.rowId}:${group.clipIds.join(',')}`,
        shotId: group.shotId,
        shotName: group.shotName,
        clipIds: group.clipIds,
        start,
        end,
        rowId: group.rowId,
        color: group.color,
        mode: group.mode,
        hasFinalVideo: finalVideoMap?.has(group.shotId) ?? false,
        hasStaleVideo: staleShotGroupIds?.has(`${group.shotId}:${group.rowId}`) ?? false,
        hasActiveTask: activeTaskClipIds ? group.clipIds.some((id) => activeTaskClipIds.has(id)) : false,
        left: timeToPixel(start),
        top: group.rowIndex * rowHeight + ACTION_VERTICAL_MARGIN,
        width: Math.max((end - start) * pixelsPerSecond, 1),
        height: actionHeight,
      }];
    });
  }, [actionHeight, activeTaskClipIds, finalVideoMap, pixelsPerSecond, resizePreviewSnapshot, rowHeight, rows, shotGroups, staleShotGroupIds, timeToPixel]);
  const hideShotGroups = dragSessionRef?.current !== null;
  const showTouchShotGroupActions = deviceClass !== 'desktop';
  const openShotGroupMenu = useCallback((
    x: number,
    y: number,
    group: Pick<PositionedShotGroup, 'shotId' | 'shotName' | 'clipIds' | 'rowId' | 'hasFinalVideo' | 'hasStaleVideo' | 'mode'>,
  ) => {
    setShotGroupMenu({ x, y, ...group, trackId: group.rowId });
  }, []);

  const syncCursor = useCallback((time = timeRef.current) => {
    const cursor = cursorRef.current;
    if (!cursor) {
      return;
    }

    const left = timeToPixel(time);
    cursor.style.transform = `translateX(${left}px)`;
  }, [timeToPixel]);

  const handleSetTime = useCallback((time: number) => {
    timeRef.current = Math.max(0, time);
    syncCursor(timeRef.current);
  }, [syncCursor]);

  useEffect(() => {
    syncCursor();
  }, [syncCursor]);

  useImperativeHandle(ref, () => ({
    get target() {
      return scrollContainerRef.current;
    },
    listener: null,
    isPlaying: false,
    isPaused: true,
    setTime: handleSetTime,
    getTime: () => timeRef.current,
    setPlayRate: (rate: number) => {
      playRateRef.current = rate;
    },
    getPlayRate: () => playRateRef.current,
    reRender: () => syncCursor(),
    play: ({ toTime }) => {
      if (typeof toTime === 'number') {
        handleSetTime(toTime);
      }
      return false;
    },
    pause: () => {},
    setScrollLeft: (value: number) => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollLeft = Math.max(0, value);
      }
    },
  }), [handleSetTime, syncCursor]);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    const nextMetrics = {
      scrollLeft: event.currentTarget.scrollLeft,
      scrollTop: event.currentTarget.scrollTop,
    };

    scrollMetricsRef.current = nextMetrics;
    if (nextMetrics.scrollLeft !== scrollLeft) {
      setScrollLeft(nextMetrics.scrollLeft);
    }
    if (nextMetrics.scrollTop !== scrollTop) {
      setScrollTop(nextMetrics.scrollTop);
    }
    syncCursor();
    onScroll?.(nextMetrics);
  };

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-background/70">
      <TimelineRulerAndGrid
        scale={scale}
        scaleWidth={scaleWidth}
        scaleSplitCount={scaleSplitCount}
        startLeft={startLeft}
        scrollLeft={scrollLeft}
        totalWidth={totalWidth}
        gestureOwner={gestureOwner}
        onClickTimeArea={onClickTimeArea}
        onCursorDrag={onCursorDrag}
        setGestureOwner={setGestureOwner}
        setInputModalityFromPointerType={setInputModalityFromPointerType}
        unusedTrackCount={unusedTrackCount}
        onClearUnusedTracks={onClearUnusedTracks}
      />
      <ShotGroupLabels
        positionedShotGroups={positionedShotGroups}
        hidden={hideShotGroups}
        showTouchActions={showTouchShotGroupActions}
        scrollLeft={scrollLeft}
        scrollTop={scrollTop}
        openShotGroupMenu={openShotGroupMenu}
        onSelectClips={onSelectClips}
        onShotGroupNavigate={onShotGroupNavigate}
      />
      <div
        ref={scrollContainerRef}
        className="timeline-canvas-edit-area timeline-scroll relative min-h-0 flex-1 overflow-auto overscroll-contain bg-background/70"
        style={{ '--label-width': `${LABEL_WIDTH}px` } as React.CSSProperties}
        onPointerDown={onEditAreaPointerDown}
        onScroll={handleScroll}
      >
        <div
          className="relative"
          style={{
            width: totalWidth,
            backgroundImage: buildGridBackground(startLeft, scaleWidth, scaleSplitCount),
            backgroundPosition: `${startLeft}px 0, ${startLeft}px 0`,
          }}
        >
          {marqueeRect && (
            <div
              className="pointer-events-none absolute z-30 border border-sky-400 bg-sky-400/10"
              style={{
                left: marqueeRect.x,
                top: marqueeRect.y,
                width: marqueeRect.width,
                height: marqueeRect.height,
              }}
            />
          )}
          {newTrackDropLabel?.includes('at top') && (
            <div className="pointer-events-none absolute left-0 right-0 top-0 z-10 h-1 bg-sky-400/60" style={{ marginLeft: LABEL_WIDTH }} />
          )}
          <ShotGroupBorders
            positionedShotGroups={positionedShotGroups}
            hidden={hideShotGroups}
          />
          <ShotGroupContextMenu
            menu={shotGroupMenu}
            menuRef={shotGroupMenuRef}
            closeMenu={() => setShotGroupMenu(null)}
            onNavigate={onShotGroupNavigate}
            onGenerateVideo={onShotGroupGenerateVideo}
            onSwitchToFinalVideo={onShotGroupSwitchToFinalVideo}
            onSwitchToImages={onShotGroupSwitchToImages}
            onUpdateToLatestVideo={onShotGroupUpdateToLatestVideo}
            onUnpinGroup={onShotGroupUnpin}
            onDeleteShot={onShotGroupDelete}
          />
          <TrackListRenderer
            rows={rows}
            tracks={tracks}
            rowHeight={rowHeight}
            startLeft={startLeft}
            pixelsPerSecond={pixelsPerSecond}
            selectedTrackId={selectedTrackId}
            resizeClampedActionId={resizeClampedActionId}
            rowResizePreview={rowResizePreview}
            resizeHandleWidth={resizeHandleWidth}
            getActionRender={getActionRender}
            onSelectTrack={onSelectTrack}
            onTrackChange={onTrackChange}
            onRemoveTrack={onRemoveTrack}
            onTrackDragEnd={onTrackDragEnd}
            trackSensors={trackSensors}
          />
        </div>
        {/* Footer: + Video / + Audio split buttons and draggable text tool — outside the grid background div */}
        <div className="relative flex border-t border-border bg-background/70" style={{ height: rowHeight, width: totalWidth }}>
          <div
            className="z-20 flex bg-card"
            style={{ width: LABEL_WIDTH, position: 'sticky', left: 0 }}
            onPointerDown={(event) => event.stopPropagation()}
          >
            {onAddTrack && (
              <>
                <button
                  type="button"
                  className="flex flex-1 items-center justify-center gap-0.5 border-r border-border/50 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  onClick={() => onAddTrack('visual')}
                >
                  + Video
                </button>
                <button
                  type="button"
                  className="flex flex-1 items-center justify-center gap-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  onClick={() => onAddTrack('audio')}
                >
                  + Audio
                </button>
              </>
            )}
          </div>
          <div className="flex flex-1 items-center gap-2 px-2" style={{ position: 'sticky', left: LABEL_WIDTH }}>
            {newTrackDropLabel && newTrackDropLabel.includes('at bottom') ? (
              <div className="flex-1 h-1 rounded-full bg-sky-400/60 pointer-events-none" />
            ) : null}
          </div>
        </div>
        <div
          ref={cursorRef}
          data-testid="timeline-playhead"
          className="pointer-events-none absolute left-0 top-0 z-[5] bg-sky-400/95 shadow-[0_0_10px_rgba(56,189,248,0.5)]"
          style={{
            width: CURSOR_WIDTH,
            height: scrollContentHeight,
            transform: `translateX(${startLeft}px)`,
          }}
        />
      </div>
      {/* Floating tool buttons — bottom-left of timeline viewport */}
      {(onAddTextAt || onOpenSequenceCreator) && (
        <div className="pointer-events-none absolute bottom-4 z-30 flex gap-1.5" style={{ left: LABEL_WIDTH + 8 }}>
          {onAddTextAt && (
            <>
              <div
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData('text-tool', 'true');
                  event.dataTransfer.effectAllowed = 'copy';
                }}
                className="pointer-events-auto flex h-6 w-6 cursor-grab items-center justify-center rounded-full bg-sky-500/15 text-sky-400 ring-1 ring-sky-400/30 transition-all duration-150 hover:-translate-y-0.5 hover:scale-105 hover:bg-sky-500/25 hover:shadow-[0_6px_18px_rgba(56,189,248,0.28)] hover:ring-sky-400/60 active:translate-y-0 active:scale-100 active:cursor-grabbing"
                title="Drag onto timeline to add text"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>
              </div>
              <div
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData('effect-layer', 'true');
                  event.dataTransfer.effectAllowed = 'copy';
                }}
                className="pointer-events-auto flex h-6 w-6 cursor-grab items-center justify-center rounded-full bg-violet-500/15 text-violet-400 ring-1 ring-violet-400/30 transition-all duration-150 hover:-translate-y-0.5 hover:scale-105 hover:bg-violet-500/25 hover:shadow-[0_6px_18px_rgba(167,139,250,0.28)] hover:ring-violet-400/60 active:translate-y-0 active:scale-100 active:cursor-grabbing"
                title="Drag onto timeline to add an effect layer"
              >
                <Layers className="h-3 w-3" />
              </div>
            </>
          )}
          {onOpenSequenceCreator && (
            <button
              type="button"
              className="pointer-events-auto flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-400/30 transition-all duration-150 hover:-translate-y-0.5 hover:scale-105 hover:bg-emerald-500/25 hover:shadow-[0_6px_18px_rgba(52,211,153,0.28)] hover:ring-emerald-400/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/70 active:translate-y-0 active:scale-100"
              title="Open Sequence creator"
              aria-label="Open Sequence creator"
              onClick={onOpenSequenceCreator}
            >
              <Sparkles className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
});
