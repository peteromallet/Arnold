import React, { useMemo } from 'react';
import { useRenderBudget } from '@/shared/dev/useRenderBudget.ts';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { LABEL_WIDTH } from '@/tools/video-editor/lib/coordinate-utils.ts';
import {
  ACTION_VERTICAL_MARGIN,
} from '@/tools/video-editor/components/TimelineEditor/timeline-canvas-constants.ts';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';
import type { TimelineGhostEntry } from '@/tools/video-editor/types/timeline-canvas.ts';

// ── Types ────────────────────────────────────────────────────────────────

export interface TimelineGhostLayerProps {
  /** Ghost entries to render. */
  ghosts: readonly TimelineGhostEntry[];
  /** Row data for track-to-row-index mapping. */
  rows: readonly TimelineRow[];
  /** Height of each row in pixels. */
  rowHeight: number;
  /** Left offset for the timeline (label width). */
  startLeft: number;
  /** Pixels per second scale factor. */
  pixelsPerSecond: number;
}

// ── Style helpers ────────────────────────────────────────────────────────

const GHOST_KIND_BORDER_VAR: Record<TimelineGhostEntry['kind'], string> = {
  added: '--video-editor-ghost-added-border',
  removed: '--video-editor-ghost-removed-border',
  modified: '--video-editor-ghost-modified-border',
  reordered: '--video-editor-ghost-reordered-border',
};

const GHOST_KIND_BG_VAR: Record<TimelineGhostEntry['kind'], string> = {
  added: '--video-editor-ghost-added-bg',
  removed: '--video-editor-ghost-removed-bg',
  modified: '--video-editor-ghost-modified-bg',
  reordered: '--video-editor-ghost-reordered-bg',
};

const GHOST_KIND_LABEL: Record<TimelineGhostEntry['kind'], string> = {
  added: 'Added',
  removed: 'Removed',
  modified: 'Modified',
  reordered: 'Reordered',
};

// ── Component ────────────────────────────────────────────────────────────

/**
 * TimelineGhostLayer renders ghost preview clips over the timeline grid.
 *
 * - Shares canonical coordinate math (startLeft, pixelsPerSecond, rowHeight).
 * - Uses `pointer-events: none` to avoid interfering with user interaction.
 * - Uses stable `data-testid` attributes (never `data-action-id`).
 * - Distinct styling per kind (added/removed/modified/reordered).
 */
export function TimelineGhostLayer({
  ghosts,
  rows,
  rowHeight,
  startLeft,
  pixelsPerSecond,
}: TimelineGhostLayerProps) {
  useRenderBudget('TimelineGhostLayer', 4);

  const actionHeight = Math.max(12, rowHeight - ACTION_VERTICAL_MARGIN * 2);

  // Build a track-id → row-index lookup for positioning.
  const trackIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 0; i < rows.length; i++) {
      map.set(rows[i].id, i);
    }
    return map;
  }, [rows]);

  if (ghosts.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="timeline-ghost-layer"
      className="pointer-events-none absolute inset-0 z-[4]"
      aria-hidden="true"
    >
      {ghosts.map((ghost) => {
        const rowIndex = trackIndexMap.get(ghost.trackId);
        if (rowIndex === undefined) {
          // Track not found — skip rendering this ghost.
          return null;
        }

        const left = startLeft + ghost.start * pixelsPerSecond;
        const width = Math.max((ghost.end - ghost.start) * pixelsPerSecond, 2);
        const top = rowIndex * rowHeight + ACTION_VERTICAL_MARGIN;

        const borderVar = GHOST_KIND_BORDER_VAR[ghost.kind];
        const bgVar = GHOST_KIND_BG_VAR[ghost.kind];
        const label = GHOST_KIND_LABEL[ghost.kind];

        return (
          <div
            key={ghost.id}
            data-testid="timeline-ghost-clip"
            data-ghost-kind={ghost.kind}
            data-ghost-track={ghost.trackId}
            title={`${label} ${ghost.clipType ? `(${ghost.clipType}) ` : ''}— proposal preview`}
            className={cn(
              'absolute rounded-sm border-2 border-dashed',
              ghost.kind === 'removed' && 'bg-[var(--video-editor-ghost-removed-bg)] border-[var(--video-editor-ghost-removed-border)]',
              ghost.kind === 'added' && 'bg-[var(--video-editor-ghost-added-bg)] border-[var(--video-editor-ghost-added-border)]',
              ghost.kind === 'modified' && 'bg-[var(--video-editor-ghost-modified-bg)] border-[var(--video-editor-ghost-modified-border)]',
              ghost.kind === 'reordered' && 'bg-[var(--video-editor-ghost-reordered-bg)] border-[var(--video-editor-ghost-reordered-border)]',
            )}
            style={{
              left,
              top,
              width,
              height: actionHeight,
              borderColor: `var(${borderVar})`,
              backgroundColor: `var(${bgVar})`,
            }}
          />
        );
      })}
    </div>
  );
}
