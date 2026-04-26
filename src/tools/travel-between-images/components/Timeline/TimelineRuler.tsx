import React from "react";
import { TIMELINE_PADDING_OFFSET } from "./constants";
import { framesToSeconds } from '@/shared/lib/media/videoUtils';
import { useTimelineFps } from './TimelineMediaContext';

interface TimelineRulerProps {
  fullMin: number;
  fullMax: number;
  fullRange: number;
  zoomLevel: number;
  containerWidth: number;
  hasNoImages?: boolean;
}

const TimelineRuler: React.FC<TimelineRulerProps> = ({
  fullMin,
  fullMax,
  fullRange,
  zoomLevel,
  containerWidth,
  hasNoImages = false,
}) => {
  const timelineFps = useTimelineFps();
  // Match TimelineItem's exact positioning logic
  // Items use: effectiveWidth = timelineWidth - (TIMELINE_PADDING_OFFSET * 2)
  // And position at: TIMELINE_PADDING_OFFSET + ((frame - fullMin) / fullRange) * effectiveWidth
  const effectiveWidth = containerWidth - (TIMELINE_PADDING_OFFSET * 2);
  const rulerWidth = effectiveWidth; // Ruler matches item coordinate space

  // Calculate how many markers we can fit based on pixel spacing
  const calculateMarkerCount = () => {
    const effectiveZoomedWidth = effectiveWidth * zoomLevel;
    const minPixelSpacing = 60; // Minimum pixels between markers (enough space for labels)
    const maxMarkers = Math.floor(effectiveZoomedWidth / minPixelSpacing);
    
    // At least 2 markers (start and end), at most what fits comfortably
    return Math.max(2, Math.min(maxMarkers, 20));
  };

  // Generate evenly spaced markers from fullMin to fullMax
  const markers: number[] = [];
  if (fullRange > 0) {
    const markerCount = calculateMarkerCount();
    
    // Always include start and end
    markers.push(fullMin);
    
    // Add evenly spaced markers in between
    if (markerCount > 2) {
      for (let i = 1; i < markerCount - 1; i++) {
        const fraction = i / (markerCount - 1);
        const markerFrame = fullMin + (fraction * fullRange);
        markers.push(markerFrame);
      }
    }
    
    // Always include end
    if (markerCount > 1 && fullMax > fullMin) {
      markers.push(fullMax);
    }
  }

  return (
    <div
      className={`absolute h-8 border-t transition-all duration-200 ${hasNoImages ? 'blur-[0.5px] opacity-50' : ''}`}
      style={{
        bottom: "-3rem", // Position below the timeline items
        // Position at TIMELINE_PADDING_OFFSET from container's edge (0,0)
        // containerWidth includes padding, and items position from this same origin
        left: `${TIMELINE_PADDING_OFFSET}px`,
        width: `${rulerWidth}px`,
      }}
    >
      <div className="relative h-full">
        {markers.map((frame, index) => {
          // Use exact same calculation as TimelineItem
          const pixelPosition = TIMELINE_PADDING_OFFSET + ((frame - fullMin) / fullRange) * effectiveWidth;
          // Convert to position within ruler (which starts at TIMELINE_PADDING_OFFSET)
          const rulerPixelPosition = pixelPosition - TIMELINE_PADDING_OFFSET;
          const leftPercent = (rulerPixelPosition / rulerWidth) * 100;

          return (
            <div
              key={`marker-${index}-${frame}`}
              className="absolute flex flex-col items-center"
              style={{ left: `${leftPercent}%`, transform: 'translateX(-50%)' }}
            >
              <div className="w-px h-4 bg-border"></div>
              <span className="text-xs text-muted-foreground mt-1 whitespace-nowrap">{framesToSeconds(frame, timelineFps)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export { TimelineRuler };
