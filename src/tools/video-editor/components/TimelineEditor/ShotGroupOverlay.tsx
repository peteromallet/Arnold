import React from 'react';
import { Ellipsis, Loader2, RefreshCw, Video } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import {
  SHOT_GROUP_LABEL_HEIGHT,
  TIME_RULER_HEIGHT,
} from './timeline-canvas-constants.ts';

export interface PositionedShotGroup {
  key: string;
  shotId: string;
  shotName: string;
  clipIds: string[];
  start: number;
  end: number;
  rowId: string;
  color: string;
  mode?: 'images' | 'video';
  hasFinalVideo: boolean;
  hasStaleVideo: boolean;
  hasActiveTask: boolean;
  left: number;
  top: number;
  width: number;
  height: number;
}

interface ShotGroupLabelsProps {
  positionedShotGroups: PositionedShotGroup[];
  hidden: boolean;
  showTouchActions: boolean;
  scrollLeft: number;
  scrollTop: number;
  openShotGroupMenu: (clientX: number, clientY: number, group: PositionedShotGroup) => void;
  onSelectClips?: (clipIds: string[]) => void;
  onShotGroupNavigate?: (shotId: string) => void;
}

interface ShotGroupBordersProps {
  positionedShotGroups: PositionedShotGroup[];
  hidden: boolean;
}

export const ShotGroupLabels = React.memo(function ShotGroupLabels({
  positionedShotGroups,
  hidden,
  showTouchActions,
  scrollLeft,
  scrollTop,
  openShotGroupMenu,
  onSelectClips,
  onShotGroupNavigate,
}: ShotGroupLabelsProps) {
  if (hidden) {
    return null;
  }

  return (
    <>
      {positionedShotGroups.map((group) => (
        <div
          key={`${group.key}:label`}
          className={cn(
            'absolute cursor-pointer select-none rounded-t-sm transition-opacity',
            showTouchActions ? 'opacity-100' : 'opacity-0 hover:opacity-100',
          )}
          title={group.shotName}
          data-action-id="shot-group-label"
          data-shot-group-drag-anchor-clip-id={group.clipIds[0] ?? ''}
          data-shot-group-drag-anchor-row-id={group.rowId}
          onClick={(event) => {
            event.stopPropagation();
            onSelectClips?.(group.clipIds);
          }}
          onDoubleClick={(event) => {
            event.stopPropagation();
            if (onShotGroupNavigate) {
              onShotGroupNavigate(group.shotId);
              return;
            }
            onSelectClips?.(group.clipIds);
          }}
          onContextMenu={(event) => {
            event.preventDefault();
            event.stopPropagation();
            openShotGroupMenu(event.clientX, event.clientY, group);
          }}
          style={{
            left: group.left - scrollLeft,
            top: TIME_RULER_HEIGHT + group.top - SHOT_GROUP_LABEL_HEIGHT - scrollTop,
            width: group.width,
            height: SHOT_GROUP_LABEL_HEIGHT,
            zIndex: 25,
            pointerEvents: 'auto',
            background: `color-mix(in srgb, ${group.color} 78%, transparent)`,
          }}
        >
          <span
            className="pointer-events-none absolute inset-x-2 top-1/2 -translate-y-1/2 truncate text-[10px] font-medium"
            style={{ color: `color-mix(in srgb, white 92%, ${group.color})` }}
          >
            {group.shotName}
          </span>
          <div className="pointer-events-none absolute right-1 top-1/2 flex -translate-y-1/2 items-center gap-1">
            {showTouchActions && (
              <button
                type="button"
                className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full bg-card/90 text-foreground shadow-sm transition-colors hover:bg-accent"
                title="Open shot actions"
                aria-label={`Open actions for ${group.shotName}`}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  openShotGroupMenu(event.clientX, event.clientY, group);
                }}
              >
                <Ellipsis className="h-4 w-4" />
              </button>
            )}
            {group.hasFinalVideo && (
              <button
                type="button"
                className="pointer-events-auto flex h-4 w-4 items-center justify-center rounded-full bg-sky-500 text-white shadow-sm transition-transform hover:scale-110 hover:bg-sky-400"
                title="Final video available"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  openShotGroupMenu(event.clientX, event.clientY, { ...group, hasFinalVideo: true });
                }}
              >
                <Video className="h-2.5 w-2.5" />
              </button>
            )}
            {group.hasStaleVideo && !group.hasActiveTask && (
              <button
                type="button"
                className="pointer-events-auto flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-white shadow-sm transition-transform hover:scale-110 hover:bg-amber-400"
                title="New video available"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  openShotGroupMenu(event.clientX, event.clientY, group);
                }}
              >
                <RefreshCw className="h-2.5 w-2.5" />
              </button>
            )}
            {group.hasActiveTask && (
              <div
                className="flex h-4 w-4 items-center justify-center rounded-full shadow-sm"
                title="Task in progress"
                style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
              >
                <Loader2 className="h-2.5 w-2.5 animate-spin" style={{ color: group.color }} />
              </div>
            )}
          </div>
        </div>
      ))}
    </>
  );
});

export const ShotGroupBorders = React.memo(function ShotGroupBorders({
  positionedShotGroups,
  hidden,
}: ShotGroupBordersProps) {
  if (hidden) {
    return null;
  }

  return (
    <>
      {positionedShotGroups.map((group) => (
        <React.Fragment key={group.key}>
          <div
            className="pointer-events-none absolute rounded-md border-2 border-solid transition-colors"
            style={{
              left: group.left - 2,
              top: group.top - 2,
              width: group.width + 4,
              height: group.height + 4,
              zIndex: 1,
              borderColor: `color-mix(in srgb, ${group.color} 60%, transparent)`,
            }}
          />
          {/*
            The dedicated round overlay edge handles were removed: they
            visually overlapped (and z-index-blocked) the first/last
            child clip's outer-edge resize handles, intercepting pointer
            events. The clip handles now route those gestures through
            `handleResizePointerDown`, providing a single unified
            affordance.
          */}
        </React.Fragment>
      ))}
    </>
  );
});
