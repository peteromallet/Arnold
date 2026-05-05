import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { MutableRefObject } from 'react';
import type {
  DropIndicatorHandle,
  DropIndicatorPosition,
} from '@/tools/video-editor/components/TimelineEditor/DropIndicator.tsx';
import {
  computeDropPosition,
  type DropPosition,
} from '@/tools/video-editor/lib/drop-position.ts';
import type { GhostRect } from '@/tools/video-editor/lib/multi-drag-utils.ts';
import { RafLoopDetector } from '@/tools/video-editor/lib/perf-diagnostics.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TrackKind } from '@/tools/video-editor/types/index.ts';

export interface DragCoordinator {
  update(params: {
    clientX: number;
    clientY: number;
    sourceKind: TrackKind | null;
    clipDuration?: number;
    clipOffsetX?: number;
    excludeClipIds?: Set<string>;
  }): DropPosition;
  /** Show ghost outlines for secondary clips (non-anchor) during multi-drag. */
  showSecondaryGhosts(ghosts: GhostRect[]): void;
  end(): void;
  lastPosition: DropPosition | null;
  editAreaRef: MutableRefObject<HTMLElement | null>;
}

interface UseDragCoordinatorArgs {
  dataRef: MutableRefObject<TimelineData | null>;
  scale: number;
  scaleWidth: number;
  startLeft: number;
  rowHeight: number;
}

interface UseDragCoordinatorResult {
  coordinator: DragCoordinator;
  indicatorRef: MutableRefObject<DropIndicatorHandle | null>;
  editAreaRef: MutableRefObject<HTMLElement | null>;
}

const buildFallbackPosition = (rowHeight: number, sourceKind: TrackKind | null): DropPosition => ({
  time: 0,
  rowIndex: 0,
  trackId: undefined,
  trackKind: sourceKind,
  trackName: '',
  isNewTrack: false,
  isReject: false,
  newTrackKind: null,
  screenCoords: {
    rowTop: 0,
    rowLeft: 0,
    rowWidth: 0,
    rowHeight,
    clipLeft: 0,
    clipWidth: 0,
    ghostCenter: 0,
  },
});

const toIndicatorPosition = (position: DropPosition): DropIndicatorPosition => {
  const timeLabel = `${position.time.toFixed(1)}s`;
  return {
    rowTop: position.screenCoords.rowTop,
    rowHeight: position.screenCoords.rowHeight,
    rowLeft: position.screenCoords.rowLeft,
    rowWidth: position.screenCoords.rowWidth,
    lineLeft: position.screenCoords.ghostCenter,
    ghostLeft: position.screenCoords.clipLeft,
    ghostTop: position.screenCoords.rowTop + 2,
    ghostWidth: position.screenCoords.clipWidth,
    ghostHeight: Math.max(0, position.screenCoords.rowHeight - 4),
    ghostLabel: timeLabel,
    label: position.trackName ? `${position.trackName} · ${timeLabel}` : timeLabel,
    isNewTrack: position.isNewTrack,
    isNewTrackTop: position.isNewTrackTop,
    trackId: position.trackId,
    newTrackKind: position.newTrackKind,
    reject: position.isReject,
  };
};

export function useDragCoordinator({
  dataRef,
  scale,
  scaleWidth,
  startLeft,
  rowHeight,
}: UseDragCoordinatorArgs): UseDragCoordinatorResult {
  const indicatorRef = useRef<DropIndicatorHandle | null>(null);
  const editAreaRef = useRef<HTMLElement | null>(null);
  const lastPositionRef = useRef<DropPosition | null>(null);
  const pendingIndicatorRef = useRef<DropIndicatorPosition | null>(null);
  const frameRef = useRef<number | null>(null);

  const flushIndicator = useCallback(() => {
    frameRef.current = null;
    const pending = pendingIndicatorRef.current;
    if (!pending) {
      return;
    }

    indicatorRef.current?.show(pending);
  }, []);

  const end = useCallback(() => {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    pendingIndicatorRef.current = null;
    lastPositionRef.current = null;
    indicatorRef.current?.hide();
  }, []);

  const update = useCallback((params: {
    clientX: number;
    clientY: number;
    sourceKind: TrackKind | null;
    clipDuration?: number;
    clipOffsetX?: number;
    excludeClipIds?: Set<string>;
  }): DropPosition => {
    const wrapper = editAreaRef.current?.closest<HTMLDivElement>('.timeline-wrapper');
    if (!wrapper) {
      const fallback = lastPositionRef.current ?? buildFallbackPosition(rowHeight, params.sourceKind);
      lastPositionRef.current = fallback;
      return fallback;
    }

    const nextPosition = computeDropPosition({
      clientX: params.clientX,
      clientY: params.clientY,
      wrapper,
      dataRef,
      scale,
      scaleWidth,
      startLeft,
      rowHeight,
      sourceKind: params.sourceKind,
      clipDuration: params.clipDuration,
      clipOffsetX: params.clipOffsetX,
      excludeClipIds: params.excludeClipIds,
    });

    lastPositionRef.current = nextPosition;
    pendingIndicatorRef.current = toIndicatorPosition(nextPosition);

    if (frameRef.current === null) {
      RafLoopDetector.track('dragCoordinator');
      frameRef.current = window.requestAnimationFrame(flushIndicator);
    }

    return nextPosition;
  }, [dataRef, flushIndicator, rowHeight, scale, scaleWidth, startLeft]);

  const showSecondaryGhosts = useCallback((ghosts: GhostRect[]) => {
    indicatorRef.current?.showSecondaryGhosts(ghosts);
  }, []);

  useEffect(() => {
    return () => {
      end();
    };
  }, [end]);

  const coordinator = useMemo<DragCoordinator>(() => ({
    update,
    showSecondaryGhosts,
    end,
    editAreaRef,
    get lastPosition() {
      return lastPositionRef.current;
    },
  }), [editAreaRef, end, showSecondaryGhosts, update]);

  return {
    coordinator,
    indicatorRef,
    editAreaRef,
  };
}
