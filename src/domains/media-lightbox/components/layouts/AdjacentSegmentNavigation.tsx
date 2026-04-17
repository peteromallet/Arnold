/**
 * AdjacentSegmentNavigation - Navigation buttons to jump to adjacent segment videos
 *
 * Shows above the media display when viewing an image that has adjacent segments:
 * - Left button: Jump to video that ENDS with this image (previous segment)
 * - Right button: Jump to video that STARTS with this image (next segment)
 *
 * Each button shows the segment's start/end image thumbnails with a video icon overlay.
 * Hovering shows a larger preview with both start and end images.
 */

import React from 'react';
import { Video, ArrowRight } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/shared/components/ui/hover-card';
import type { AdjacentSegmentsData } from '../../types';

interface AdjacentSegmentNavigationProps {
  adjacentSegments: AdjacentSegmentsData;
}

export const AdjacentSegmentNavigation: React.FC<AdjacentSegmentNavigationProps> = ({
  adjacentSegments,
}) => {
  const { prev, next, onNavigateToSegment } = adjacentSegments;

  // Don't render if no adjacent segments
  if (!prev && !next) {
    return null;
  }

  const handlePrevClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (prev) {
      onNavigateToSegment(prev.pairIndex);
    }
  };

  const handleNextClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (next) {
      onNavigateToSegment(next.pairIndex);
    }
  };

  // Check if we should show placeholders (when one segment exists but not the other)
  const showPrevPlaceholder = !prev && !!next;
  const showNextPlaceholder = !!prev && !next;

  // Shared segment button component
  const SegmentButton = ({
    segment,
    label,
    onClick,
    showPlaceholder = false,
    highlightStart = false,
    highlightEnd = false,
  }: {
    segment: typeof prev | typeof next;
    label: string;
    onClick: (e: React.MouseEvent) => void;
    showPlaceholder?: boolean;
    highlightStart?: boolean;
    highlightEnd?: boolean;
  }) => {
    // Show a subtle placeholder when segment is missing but the other exists
    if (!segment && showPlaceholder) {
      return (
        <div
          className={cn(
            'relative w-9 h-9 md:w-10 md:h-10 rounded-md overflow-hidden shadow-md',
            'bg-black/40 border border-white/30'
          )}
        >
          <div className="absolute inset-0 flex items-center justify-center">
            <Video className="w-4 h-4 text-white/40" />
          </div>
        </div>
      );
    }

    const button = (
      <button
        onClick={onClick}
        disabled={!segment}
        className={cn(
          'relative w-9 h-9 md:w-10 md:h-10 rounded-md overflow-hidden shadow-md transition-all',
          segment && 'hover:scale-105 hover:shadow-lg hover:ring-2 hover:ring-white/40',
          'focus:outline-none focus:ring-2 focus:ring-white/50',
          !segment && 'opacity-30 cursor-not-allowed pointer-events-none'
        )}
      >
        {/* Two images side by side in square container */}
        <div className="absolute inset-0 flex">
          {segment?.startImageUrl && (
            <div className="w-1/2 h-full overflow-hidden">
              <img
                src={segment.startImageUrl}
                alt="Start"
                className="w-full h-full object-cover"
              />
            </div>
          )}
          {segment?.endImageUrl && (
            <div className="w-1/2 h-full overflow-hidden">
              <img
                src={segment.endImageUrl}
                alt="End"
                className="w-full h-full object-cover"
              />
            </div>
          )}
        </div>
        {/* Video icon overlay */}
        {segment && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20">
            <Video className="w-4 h-4 text-white/50" />
          </div>
        )}
      </button>
    );

    // Don't show hover card if no segment
    if (!segment) {
      return button;
    }

    return (
      <HoverCard>
        <HoverCardTrigger asChild>
          {button}
        </HoverCardTrigger>
        <HoverCardContent
          side="bottom"
          sideOffset={8}
          className="p-2 w-auto border-0 bg-background/95 backdrop-blur-sm"
        >
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center gap-2">
              {segment.startImageUrl && (
                <div className="flex flex-col items-center gap-1">
                  <img
                    src={segment.startImageUrl}
                    alt="Start"
                    className={cn(
                      "w-24 h-24 object-cover rounded-md",
                      highlightStart && "ring-2 ring-primary ring-offset-2 ring-offset-background"
                    )}
                  />
                  <span className={cn(
                    "text-[10px]",
                    highlightStart ? "text-primary font-medium" : "text-muted-foreground"
                  )}>
                    {highlightStart ? "Current" : "Start"}
                  </span>
                </div>
              )}
              <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
              {segment.endImageUrl && (
                <div className="flex flex-col items-center gap-1">
                  <img
                    src={segment.endImageUrl}
                    alt="End"
                    className={cn(
                      "w-24 h-24 object-cover rounded-md",
                      highlightEnd && "ring-2 ring-primary ring-offset-2 ring-offset-background"
                    )}
                  />
                  <span className={cn(
                    "text-[10px]",
                    highlightEnd ? "text-primary font-medium" : "text-muted-foreground"
                  )}>
                    {highlightEnd ? "Current" : "End"}
                  </span>
                </div>
              )}
            </div>
            <span className="text-xs text-muted-foreground">{label}</span>
          </div>
        </HoverCardContent>
      </HoverCard>
    );
  };

  return (
    <div
      className="flex items-center gap-3 select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <SegmentButton
        segment={prev}
        label="Previous video segment"
        onClick={handlePrevClick}
        showPlaceholder={showPrevPlaceholder}
        highlightEnd={true}
      />
      <SegmentButton
        segment={next}
        label="Next video segment"
        onClick={handleNextClick}
        showPlaceholder={showNextPlaceholder}
        highlightStart={true}
      />
    </div>
  );
};
