import type { DragEvent as ReactDragEvent, MutableRefObject } from 'react';
import { getDragType } from '@/shared/lib/dnd/dragDrop.ts';
import { findNearestFreeTrack, rawRowIndexFromY, trySnapToEdge } from '@/tools/video-editor/lib/coordinate-utils.ts';
import { createTimelineScale } from '@/tools/video-editor/lib/timeline-scale.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TrackKind } from '@/tools/video-editor/types/index.ts';

interface TimelineDomNodes {
  wrapper: HTMLDivElement;
  editArea: HTMLElement | null;
  grid: HTMLElement | null;
}

interface DropScreenCoords {
  rowTop: number;
  rowLeft: number;
  rowWidth: number;
  rowHeight: number;
  clipLeft: number;
  clipWidth: number;
  ghostCenter: number;
}

export interface DropPosition {
  time: number;
  rowIndex: number;
  trackId: string | undefined;
  trackKind: TrackKind | null;
  trackName: string;
  isNewTrack: boolean;
  /** Whether the new track should be inserted at the top (true) or bottom (false/undefined). */
  isNewTrackTop?: boolean;
  isReject: boolean;
  /** When non-null, dropping here will create a new track of this kind. */
  newTrackKind: TrackKind | null;
  screenCoords: DropScreenCoords;
}

export interface ComputeDropPositionParams {
  clientX: number;
  clientY: number;
  wrapper: HTMLDivElement;
  dataRef: MutableRefObject<TimelineData | null>;
  scale: number;
  scaleWidth: number;
  startLeft: number;
  rowHeight: number;
  sourceKind?: TrackKind | null;
  clipDuration?: number;
  clipOffsetX?: number;
  excludeClipIds?: Set<string>;
}

const timelineDomNodeCache = new WeakMap<HTMLDivElement, Omit<TimelineDomNodes, 'wrapper'>>();
const isValidNode = (wrapper: HTMLDivElement, node: HTMLElement | null): boolean => {
  return node === null || (node.isConnected && wrapper.contains(node));
};

export const getTimelineDomNodes = (wrapper: HTMLDivElement): TimelineDomNodes => {
  const cached = timelineDomNodeCache.get(wrapper);
  if (
    cached
    && isValidNode(wrapper, cached.editArea)
    && isValidNode(wrapper, cached.grid)
  ) {
    return { wrapper, ...cached };
  }

  const editArea = wrapper.querySelector<HTMLElement>('.timeline-canvas-edit-area');
  // In TimelineCanvas the edit area IS the scroll container (grid).
  const grid = editArea;
  const nextNodes = { editArea, grid };
  timelineDomNodeCache.set(wrapper, nextNodes);
  return { wrapper, ...nextNodes };
};

export const computeDropPosition = ({
  clientX,
  clientY,
  wrapper,
  dataRef,
  scale,
  scaleWidth,
  startLeft,
  rowHeight,
  sourceKind = null,
  clipDuration = 5,
  clipOffsetX,
  excludeClipIds,
}: ComputeDropPositionParams): DropPosition => {
  const current = dataRef.current;
  const { editArea, grid } = getTimelineDomNodes(wrapper);
  const wrapperRect = wrapper.getBoundingClientRect();
  const editRect = (editArea ?? wrapper).getBoundingClientRect();
  const scrollLeft = grid?.scrollLeft ?? 0;
  const scrollTop = grid?.scrollTop ?? 0;
  const { pixelsPerSecond, pixelToTime, timeToPixel } = createTimelineScale({ scale, scaleWidth, startLeft });
  const effectiveOffsetX = clipOffsetX ?? (clipDuration * pixelsPerSecond) / 2;
  const leftInGrid = clientX - editRect.left + scrollLeft - effectiveOffsetX;
  const time = Math.max(0, pixelToTime(leftInGrid));

  const rowCount = current?.rows.length ?? 0;
  const rawRowIndex = rawRowIndexFromY(clientY, editRect.top, scrollTop, rowHeight);
  const isNewTrackBottom = rowCount === 0 || rawRowIndex >= rowCount;
  // Only show top drop zone when fully scrolled up — otherwise auto-scroll handles it
  const isNewTrackTop = rawRowIndex < 0 && rowCount > 0 && scrollTop < 2;
  const isNewTrack = isNewTrackBottom || isNewTrackTop;
  const rowIndex = rowCount === 0
    ? 0
    : isNewTrackBottom
      ? rowCount
      : isNewTrackTop
        ? 0
        : Math.min(Math.max(rawRowIndex, 0), rowCount - 1);
  const visualRowIndex = rowCount > 0 ? Math.min(rowIndex, rowCount - 1) : -1;
  const targetRow = visualRowIndex >= 0 ? current?.rows[visualRowIndex] : undefined;
  const targetTrack = visualRowIndex >= 0 ? current?.tracks[visualRowIndex] : undefined;
  const rowTop = visualRowIndex >= 0
    ? editRect.top + visualRowIndex * rowHeight - scrollTop
    : editRect.top;
  const clipLeft = editRect.left + timeToPixel(time) - scrollLeft;
  const clipWidth = Math.max(0, Math.min(clipDuration * pixelsPerSecond, editRect.right - clipLeft));
  const ghostCenter = clipLeft + clipWidth / 2;
  const kindMismatch = !isNewTrack && sourceKind !== null && targetTrack?.kind !== undefined && sourceKind !== targetTrack.kind;

  // When kind doesn't match, silently resolve to the first compatible track.
  // Only create a new track if no compatible one exists at all.
  let resolvedTrackId = targetRow?.id;
  let resolvedTrackName = targetTrack?.label ?? targetTrack?.id ?? '';
  let resolvedTrackKind = targetTrack?.kind ?? null;
  let needsNewTrack = isNewTrack;
  let newTrackKind: TrackKind | null = isNewTrack ? sourceKind : null;

  if (kindMismatch && current && sourceKind) {
    // Find the nearest compatible track to the hovered row
    const compatibleTracks = current.tracks
      .map((t, i) => ({ track: t, index: i }))
      .filter(({ track }) => track.kind === sourceKind);
    const nearest = compatibleTracks.length > 0
      ? compatibleTracks.reduce((best, candidate) =>
          Math.abs(candidate.index - rowIndex) < Math.abs(best.index - rowIndex) ? candidate : best)
      : null;
    if (nearest) {
      const compatible = nearest.track;
      resolvedTrackId = compatible.id;
      resolvedTrackName = compatible.label ?? compatible.id;
      resolvedTrackKind = compatible.kind;
      const compatibleIndex = nearest.index;
      const compatibleRowTop = compatibleIndex >= 0
        ? editRect.top + compatibleIndex * rowHeight - scrollTop
        : rowTop;
      return {
        time,
        rowIndex: compatibleIndex,
        trackId: resolvedTrackId,
        trackKind: resolvedTrackKind,
        trackName: resolvedTrackName,
        isNewTrack: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: compatibleRowTop,
          rowLeft: wrapperRect.left,
          rowWidth: wrapperRect.width,
          rowHeight,
          clipLeft,
          clipWidth,
          ghostCenter,
        },
      };
    }
    // No compatible track exists — will create one silently on drop
    needsNewTrack = true;
    newTrackKind = sourceKind;
    resolvedTrackId = undefined;
    resolvedTrackKind = sourceKind;
    resolvedTrackName = '';
  }

  // Overlap resolution: prefer snapping to a sibling edge on the same track
  // before falling back to another track.
  let resolvedTime = time;
  let finalRowTop = rowTop;
  if (!needsNewTrack && current && resolvedTrackId && resolvedTrackKind) {
    const snapResult = trySnapToEdge(
      current.rows,
      resolvedTrackId,
      time,
      clipDuration,
      excludeClipIds,
    );
    if (snapResult.snapped) {
      resolvedTime = snapResult.time;
    } else {
      const freeTrackId = findNearestFreeTrack(
        current.tracks, current.rows, resolvedTrackId, resolvedTrackKind,
        time, clipDuration, excludeClipIds,
      );
      if (freeTrackId && freeTrackId !== resolvedTrackId) {
        const freeIndex = current.tracks.findIndex((t) => t.id === freeTrackId);
        const freeTrack = current.tracks[freeIndex];
        if (freeTrack) {
          resolvedTrackId = freeTrackId;
          resolvedTrackName = freeTrack.label ?? freeTrack.id;
          resolvedTrackKind = freeTrack.kind;
          finalRowTop = editRect.top + freeIndex * rowHeight - scrollTop;
        }
      } else if (!freeTrackId) {
        needsNewTrack = true;
        newTrackKind = resolvedTrackKind;
        resolvedTrackId = undefined;
        resolvedTrackName = '';
      }
    }
  }

  const finalClipLeft = editRect.left + timeToPixel(resolvedTime) - scrollLeft;
  const finalClipWidth = Math.max(0, Math.min(clipDuration * pixelsPerSecond, editRect.right - finalClipLeft));
  const finalGhostCenter = finalClipLeft + finalClipWidth / 2;

  return {
    time: resolvedTime,
    rowIndex,
    trackId: needsNewTrack ? undefined : resolvedTrackId,
    trackKind: needsNewTrack ? sourceKind : resolvedTrackKind,
    trackName: resolvedTrackName,
    isNewTrack: needsNewTrack,
    isNewTrackTop: needsNewTrack && isNewTrackTop,
    isReject: false,
    newTrackKind,
    screenCoords: {
      rowTop: finalRowTop,
      rowLeft: wrapperRect.left,
      rowWidth: wrapperRect.width,
      rowHeight,
      clipLeft: finalClipLeft,
      clipWidth: finalClipWidth,
      ghostCenter: finalGhostCenter,
    },
  };
};

export const inferDragKind = (event: ReactDragEvent<HTMLDivElement>): TrackKind | null => {
  const types = Array.from(event.dataTransfer.types);
  if (types.includes('asset-kind:audio')) return 'audio';
  if (types.includes('asset-kind:visual')) return 'visual';
  if (types.includes('asset-key')) return null;
  if (getDragType(event) === 'generation') return 'visual';
  if (event.dataTransfer.items.length > 0) {
    for (const item of Array.from(event.dataTransfer.items)) {
      if (item.type.startsWith('audio/')) {
        return 'audio';
      }
    }
    return 'visual';
  }
  return null;
};
