import { TimeRuler } from '@/tools/video-editor/components/TimelineEditor/TimeRuler.tsx';
import { LABEL_WIDTH } from '@/tools/video-editor/lib/coordinate-utils.ts';
import type {
  TimelineGestureOwner,
  TimelineInputModality,
} from '@/tools/video-editor/lib/mobile-interaction-model.ts';

interface TimelineRulerAndGridProps {
  scale: number;
  scaleWidth: number;
  scaleSplitCount: number;
  startLeft: number;
  scrollLeft: number;
  totalWidth: number;
  gestureOwner: TimelineGestureOwner;
  onClickTimeArea: (time: number) => void;
  onCursorDrag: (time: number) => void;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => TimelineInputModality;
  unusedTrackCount?: number;
  onClearUnusedTracks?: () => void;
}

export const buildGridBackground = (
  startLeft: number,
  scaleWidth: number,
  scaleSplitCount: number,
): string => {
  const splitWidth = scaleWidth / Math.max(scaleSplitCount, 1);
  // Vertical grid lines only — horizontal lines come from row borders
  return [
    `repeating-linear-gradient(to right, hsl(var(--border) / 0.55) 0, hsl(var(--border) / 0.55) 1px, transparent 1px, transparent ${scaleWidth}px)`,
    `repeating-linear-gradient(to right, hsl(var(--border) / 0.25) 0, hsl(var(--border) / 0.25) 1px, transparent 1px, transparent ${splitWidth}px)`,
  ].join(',');
};

export function TimelineRulerAndGrid({
  scale,
  scaleWidth,
  scaleSplitCount,
  startLeft,
  scrollLeft,
  totalWidth,
  gestureOwner,
  onClickTimeArea,
  onCursorDrag,
  setGestureOwner,
  setInputModalityFromPointerType,
  unusedTrackCount,
  onClearUnusedTracks,
}: TimelineRulerAndGridProps) {
  return (
    <>
      {unusedTrackCount > 0 && onClearUnusedTracks && (
        <button
          type="button"
          className="absolute left-0 top-0 z-20 flex h-[30px] items-center justify-center border-b border-r border-border bg-card/90 text-[9px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          style={{ width: LABEL_WIDTH }}
          onClick={onClearUnusedTracks}
        >
          Clear {unusedTrackCount} unused
        </button>
      )}
      <TimeRuler
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
      />
    </>
  );
}
