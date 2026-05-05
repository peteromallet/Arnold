import { useMemo, useRef } from 'react';
import {
  createTimelineScale,
  type TimelineScaleOptions,
} from '@/tools/video-editor/lib/timeline-scale.ts';

export function useTimelineScale(options: TimelineScaleOptions) {
  const timelineScale = useMemo(
    () => createTimelineScale(options),
    [options.scale, options.scaleWidth, options.startLeft],
  );
  const pixelsPerSecondRef = useRef(timelineScale.pixelsPerSecond);
  pixelsPerSecondRef.current = timelineScale.pixelsPerSecond;

  return {
    ...timelineScale,
    pixelsPerSecondRef,
  };
}
