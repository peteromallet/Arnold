/**
 * StagePanelCanary — Host-contained canary for the stagePanel surface.
 *
 * Demonstrates the stage panel slot by:
 * - Showing empty state (no timeline binding)
 * - Showing error state (render failure simulation)
 * - Showing disabled state (explicit disable flag)
 * - Coordinate vocabulary (stage-local coordinate system)
 * - Containment metadata (bounds, clipping region)
 * - Gesture policy (which gestures are claimed/allowed)
 * - Optional timeline binding metadata (time range, fps)
 *
 * No direct manipulation tooling — display-only proof-of-life for the
 * stagePanel surface slot infrastructure.
 */

import { useState, useCallback } from 'react';
import { MonitorPlay, AlertTriangle, Ban, Square, Maximize2, MousePointer2, Hand } from 'lucide-react';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StageCanaryState = 'empty' | 'error' | 'disabled';

interface StageCoordinateVocabulary {
  origin: { x: number; y: number };
  scale: { x: number; y: number };
  unit: 'px' | 'percent' | 'normalized';
}

interface StageContainment {
  bounds: { width: number; height: number };
  clipOverflow: boolean;
  viewport: { x: number; y: number; width: number; height: number };
}

interface GesturePolicy {
  claimedGestures: string[];
  allowPassthrough: boolean;
  gestureOwner: string | null;
}

interface TimelineBindingMetadata {
  timelineId: string | null;
  timeRange: { start: number; end: number } | null;
  fps: number | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEMO_COORDINATE: StageCoordinateVocabulary = {
  origin: { x: 0, y: 0 },
  scale: { x: 1, y: 1 },
  unit: 'px',
};

const DEMO_CONTAINMENT: StageContainment = {
  bounds: { width: 1920, height: 1080 },
  clipOverflow: true,
  viewport: { x: 0, y: 0, width: 1920, height: 1080 },
};

const DEMO_GESTURE_POLICY: GesturePolicy = {
  claimedGestures: ['none'],
  allowPassthrough: true,
  gestureOwner: null,
};

const STATE_LABEL: Record<StageCanaryState, string> = {
  empty: 'Empty — no timeline bound',
  error: 'Error — render failure',
  disabled: 'Disabled — stage not available',
};

const STATE_ICON = {
  empty: Square,
  error: AlertTriangle,
  disabled: Ban,
} as const;

const STATE_COLOR = {
  empty: 'text-muted-foreground',
  error: 'text-red-400',
  disabled: 'text-muted-foreground/50',
} as const;

const STATE_BORDER = {
  empty: 'border-border/40',
  error: 'border-red-500/40',
  disabled: 'border-border/20',
} as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface StagePanelCanaryProps {
  context: VideoEditorRenderContext;
}

export function StagePanelCanary({ context }: StagePanelCanaryProps) {
  const { timelineId, timelineName, data } = context;
  const [canaryState, setCanaryState] = useState<StageCanaryState>('empty');

  const toggleState = useCallback(() => {
    setCanaryState((prev) => {
      if (prev === 'empty') return 'error';
      if (prev === 'error') return 'disabled';
      return 'empty';
    });
  }, []);

  const timelineBinding: TimelineBindingMetadata = {
    timelineId: canaryState === 'empty' ? null : timelineId,
    timeRange: canaryState === 'empty' ? null : { start: 0, end: 300 },
    fps: canaryState === 'empty' ? null : 30,
  };

  const StateIcon = STATE_ICON[canaryState];
  const stateColor = STATE_COLOR[canaryState];
  const stateBorder = STATE_BORDER[canaryState];

  return (
    <div
      data-video-editor-slot="stagePanel"
      data-video-editor-canary="true"
      data-video-editor-stage-state={canaryState}
      className={`flex flex-col gap-3 rounded-md border bg-card/80 p-3 ${stateBorder}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MonitorPlay className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Stage panel canary
          </span>
        </div>
        <button
          type="button"
          className="rounded border border-border/50 bg-muted/30 px-2 py-0.5 text-[9px] text-muted-foreground hover:bg-muted/50"
          onClick={toggleState}
          aria-label={`Cycle stage state (current: ${canaryState})`}
        >
          Toggle state
        </button>
      </div>

      {/* State indicator */}
      <div
        data-video-editor-canary-section="state"
        className={`flex items-center gap-2 rounded border px-2 py-1.5 text-[10px] ${stateBorder} bg-muted/20`}
      >
        <StateIcon className={`h-3 w-3 ${stateColor}`} />
        <span className={stateColor}>{STATE_LABEL[canaryState]}</span>
      </div>

      {/* Coordinate vocabulary */}
      <div
        data-video-editor-canary-section="coordinates"
        className="space-y-1 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <div className="font-semibold text-foreground/70">Coordinate vocabulary</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-muted-foreground/70">
          <span>Origin:</span>
          <span>
            ({DEMO_COORDINATE.origin.x}, {DEMO_COORDINATE.origin.y})
          </span>
          <span>Scale:</span>
          <span>
            ({DEMO_COORDINATE.scale.x}, {DEMO_COORDINATE.scale.y})
          </span>
          <span>Unit:</span>
          <span>{DEMO_COORDINATE.unit}</span>
        </div>
      </div>

      {/* Containment */}
      <div
        data-video-editor-canary-section="containment"
        className="space-y-1 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <div className="flex items-center gap-1.5">
          <Maximize2 className="h-3 w-3 text-muted-foreground/60" />
          <span className="font-semibold text-foreground/70">Containment</span>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-muted-foreground/70">
          <span>Bounds:</span>
          <span>
            {DEMO_CONTAINMENT.bounds.width}×{DEMO_CONTAINMENT.bounds.height}
          </span>
          <span>Clip overflow:</span>
          <span>{DEMO_CONTAINMENT.clipOverflow ? 'Yes' : 'No'}</span>
          <span>Viewport:</span>
          <span>
            ({DEMO_CONTAINMENT.viewport.x}, {DEMO_CONTAINMENT.viewport.y},{' '}
            {DEMO_CONTAINMENT.viewport.width}×{DEMO_CONTAINMENT.viewport.height})
          </span>
        </div>
      </div>

      {/* Gesture policy */}
      <div
        data-video-editor-canary-section="gesture-policy"
        className="space-y-1 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <div className="flex items-center gap-1.5">
          <MousePointer2 className="h-3 w-3 text-muted-foreground/60" />
          <span className="font-semibold text-foreground/70">Gesture policy</span>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-muted-foreground/70">
          <span>Claimed:</span>
          <span>{DEMO_GESTURE_POLICY.claimedGestures.join(', ') || 'none'}</span>
          <span>Passthrough:</span>
          <span>{DEMO_GESTURE_POLICY.allowPassthrough ? 'Yes' : 'No'}</span>
          <span>Owner:</span>
          <span>{DEMO_GESTURE_POLICY.gestureOwner ?? '—'}</span>
        </div>
        <div className="flex items-center gap-1.5 mt-1 text-muted-foreground/50">
          <Hand className="h-3 w-3" />
          <span>No direct manipulation tooling</span>
        </div>
      </div>

      {/* Timeline binding metadata (optional) */}
      <div
        data-video-editor-canary-section="timeline-binding"
        className="space-y-1 rounded border border-border/40 bg-muted/30 p-2 text-[10px]"
      >
        <div className="font-semibold text-foreground/70">Timeline binding metadata</div>
        {timelineBinding.timelineId ? (
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-muted-foreground/70">
            <span>Timeline:</span>
            <span>{timelineName ?? timelineBinding.timelineId.slice(0, 16)}</span>
            <span>Time range:</span>
            <span>
              {timelineBinding.timeRange!.start}s – {timelineBinding.timeRange!.end}s
            </span>
            <span>FPS:</span>
            <span>{timelineBinding.fps}</span>
          </div>
        ) : (
          <div className="text-muted-foreground/40 italic">
            No timeline bound (empty/disabled state)
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="text-[10px] text-muted-foreground/60">
        Canary — not available for production authoring (M3)
      </div>
    </div>
  );
}
