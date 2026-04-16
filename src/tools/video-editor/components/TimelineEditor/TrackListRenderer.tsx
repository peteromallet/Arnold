import React, { type ReactNode } from 'react';
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import { TrackLabelContent } from '@/tools/video-editor/components/TimelineEditor/TrackLabel';
import { LABEL_WIDTH } from '@/tools/video-editor/lib/coordinate-utils';
import type { TrackDefinition } from '@/tools/video-editor/types';
import type {
  TimelineAction,
  TimelineRow,
} from '@/tools/video-editor/types/timeline-canvas';
import {
  ACTION_VERTICAL_MARGIN,
  EMPTY_RESIZE_PREVIEW_SNAPSHOT,
  type ResizeOverride,
} from './timeline-canvas-constants';

interface SortableRowProps {
  row: TimelineRow;
  track: TrackDefinition;
  rowHeight: number;
  startLeft: number;
  pixelsPerSecond: number;
  selectedTrackId: string | null;
  resizeClampedActionId: string | null;
  resizePreviewSnapshot: Readonly<Record<string, ResizeOverride>>;
  resizeHandleWidth: number;
  getActionRender?: (action: TimelineAction, row: TimelineRow, width: number) => ReactNode;
  onSelectTrack: (trackId: string) => void;
  onTrackChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  onRemoveTrack: (trackId: string) => void;
}

interface TrackListRendererProps {
  rows: TimelineRow[];
  tracks: TrackDefinition[];
  rowHeight: number;
  startLeft: number;
  pixelsPerSecond: number;
  selectedTrackId: string | null;
  resizeClampedActionId: string | null;
  rowResizePreview: Readonly<Record<string, ResizeOverride>>[];
  resizeHandleWidth: number;
  getActionRender?: (action: TimelineAction, row: TimelineRow, width: number) => ReactNode;
  onSelectTrack: (trackId: string) => void;
  onTrackChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  onRemoveTrack: (trackId: string) => void;
  onTrackDragEnd: (event: DragEndEvent) => void;
  trackSensors: ReturnType<typeof useSensors>;
}

const SortableRow = React.memo(function SortableRow({
  row,
  track,
  rowHeight,
  startLeft,
  pixelsPerSecond,
  selectedTrackId,
  resizeClampedActionId,
  resizePreviewSnapshot,
  resizeHandleWidth,
  getActionRender,
  onSelectTrack,
  onTrackChange,
  onRemoveTrack,
}: SortableRowProps) {
  useRenderBudget('SortableRow', 4);
  const sortable = useSortable({ id: `track-${track.id}` });
  const actionHeight = Math.max(12, rowHeight - ACTION_VERTICAL_MARGIN * 2);
  const style = {
    height: rowHeight,
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.5 : 1,
    zIndex: sortable.isDragging ? 20 : undefined,
  };

  return (
    <div
      ref={sortable.setNodeRef}
      className="relative border-b border-border/30"
      data-row-id={row.id}
      style={style}
    >
      <div
        className="absolute left-0 top-0 z-20 h-full border-r border-border bg-card"
        style={{ width: LABEL_WIDTH, position: 'sticky', left: 0 }}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <TrackLabelContent
          track={track}
          isSelected={selectedTrackId === track.id}
          hasClips={row.actions.length > 0}
          onSelect={onSelectTrack}
          onChange={onTrackChange}
          onRemove={onRemoveTrack}
          dragListeners={sortable.listeners}
          dragAttributes={sortable.attributes}
        />
      </div>
      {row.actions.map((action) => {
        // Render both handles on every clip — including grouped children.
        // The document-level resize gesture hook resolves whether a handle
        // starts a free or group resize session.
        const override = resizePreviewSnapshot[action.id];
        const renderedAction = override ? { ...action, ...override } : action;
        const left = startLeft + renderedAction.start * pixelsPerSecond;
        const width = Math.max((renderedAction.end - renderedAction.start) * pixelsPerSecond, resizeHandleWidth * 2);

        return (
          <div
            key={action.id}
            className={cn(
              'group absolute',
              resizeClampedActionId === action.id && 'rounded-md ring-2 ring-amber-400/80 ring-offset-1 ring-offset-background',
            )}
            data-action-id={action.id}
            data-row-id={row.id}
            style={{
              left,
              top: ACTION_VERTICAL_MARGIN,
              width,
              height: actionHeight,
            }}
          >
            {getActionRender?.(renderedAction, row, width)}
            <div
              className="absolute inset-y-0 left-0 z-10 cursor-ew-resize rounded-l-sm border-l border-sky-300/10 bg-sky-300/0 transition-colors group-hover:bg-sky-300/10"
              style={{ width: resizeHandleWidth }}
              data-resize-edge="left"
              data-clip-id={action.id}
              data-row-id={row.id}
            />
            <div
              className="absolute inset-y-0 right-0 z-10 cursor-ew-resize rounded-r-sm border-r border-sky-300/10 bg-sky-300/0 transition-colors group-hover:bg-sky-300/10"
              style={{ width: resizeHandleWidth }}
              data-resize-edge="right"
              data-clip-id={action.id}
              data-row-id={row.id}
            />
          </div>
        );
      })}
    </div>
  );
});

SortableRow.displayName = 'SortableRow';

export function TrackListRenderer({
  rows,
  tracks,
  rowHeight,
  startLeft,
  pixelsPerSecond,
  selectedTrackId,
  resizeClampedActionId,
  rowResizePreview,
  resizeHandleWidth,
  getActionRender,
  onSelectTrack,
  onTrackChange,
  onRemoveTrack,
  onTrackDragEnd,
  trackSensors,
}: TrackListRendererProps) {
  return (
    <DndContext
      sensors={trackSensors}
      collisionDetection={closestCenter}
      onDragEnd={onTrackDragEnd}
    >
      <SortableContext
        items={tracks.map((track) => `track-${track.id}`)}
        strategy={verticalListSortingStrategy}
      >
        {tracks.map((track, index) => {
          const row = rows[index];
          if (!row) {
            return null;
          }

          return (
            <SortableRow
              key={track.id}
              row={row}
              track={track}
              rowHeight={rowHeight}
              startLeft={startLeft}
              pixelsPerSecond={pixelsPerSecond}
              selectedTrackId={selectedTrackId}
              resizeClampedActionId={resizeClampedActionId}
              resizePreviewSnapshot={rowResizePreview[index] ?? EMPTY_RESIZE_PREVIEW_SNAPSHOT}
              resizeHandleWidth={resizeHandleWidth}
              getActionRender={getActionRender}
              onSelectTrack={onSelectTrack}
              onTrackChange={onTrackChange}
              onRemoveTrack={onRemoveTrack}
            />
          );
        })}
      </SortableContext>
    </DndContext>
  );
}
