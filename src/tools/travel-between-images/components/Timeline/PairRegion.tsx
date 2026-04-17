import React from "react";
import { MessageSquare } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/shared/components/ui/tooltip";
import { PairPromptTooltipContent } from '@/shared/components/ShotImageManager/components/PairPromptTooltipContent';
import { framesToSeconds } from '@/shared/lib/media/videoUtils';
import { useTimelineFps } from './TimelineMediaContext';

interface PairRegionProps {
  index: number;
  startPercent: number;
  endPercent: number;
  contextStartPercent: number;
  generationStartPercent: number;
  actualFrames: number;
  visibleContextFrames: number;
  isDragging: boolean;
  numPairs: number;
  startFrame: number;
  endFrame: number;
  onPairClick?: (pairIndex: number) => void;
  pairPrompt?: string;
  pairNegativePrompt?: string;
  enhancedPrompt?: string;
  defaultPrompt?: string;
  defaultNegativePrompt?: string;
  showLabel: boolean;
  onClearEnhancedPrompt?: (pairIndex: number) => void;
  /** Hide the pair label (used during tap-to-move selection on tablets) */
  hidePairLabel?: boolean;
  /** Read-only mode - disables click interactions */
  readOnly?: boolean;
}

const PairRegion: React.FC<PairRegionProps> = ({
  index,
  startPercent,
  endPercent,
  actualFrames,
  startFrame,
  endFrame,
  onPairClick,
  pairPrompt,
  pairNegativePrompt,
  enhancedPrompt,
  showLabel,
  onClearEnhancedPrompt,
  hidePairLabel = false,
  readOnly = false,
}) => {
  const timelineFps = useTimelineFps();
  const pairColorSchemes = [
    { bg: 'bg-blue-50 dark:bg-blue-950/40', border: 'border-blue-300 dark:border-blue-700', context: 'bg-blue-200/60 dark:bg-blue-800/40', text: 'text-blue-700 dark:text-gray-300', line: 'bg-blue-400 dark:bg-blue-600' },
    { bg: 'bg-emerald-50 dark:bg-emerald-950/40', border: 'border-emerald-300 dark:border-emerald-700', context: 'bg-emerald-200/60 dark:bg-emerald-800/40', text: 'text-emerald-700 dark:text-gray-300', line: 'bg-emerald-400 dark:bg-emerald-600' },
    { bg: 'bg-purple-50 dark:bg-purple-950/40', border: 'border-purple-300 dark:border-purple-700', context: 'bg-purple-200/60 dark:bg-purple-800/40', text: 'text-purple-700 dark:text-gray-300', line: 'bg-purple-400 dark:bg-purple-600' },
    { bg: 'bg-orange-50 dark:bg-orange-950/40', border: 'border-orange-300 dark:border-orange-700', context: 'bg-orange-200/60 dark:bg-orange-800/40', text: 'text-orange-700 dark:text-gray-300', line: 'bg-orange-400 dark:bg-orange-600' },
    { bg: 'bg-rose-50 dark:bg-rose-950/40', border: 'border-rose-300 dark:border-rose-700', context: 'bg-rose-200/60 dark:bg-rose-800/40', text: 'text-rose-700 dark:text-gray-300', line: 'bg-rose-400 dark:bg-rose-600' },
    { bg: 'bg-teal-50 dark:bg-teal-950/40', border: 'border-teal-300 dark:border-teal-700', context: 'bg-teal-200/60 dark:bg-teal-800/40', text: 'text-teal-700 dark:text-gray-300', line: 'bg-teal-400 dark:bg-teal-600' },
  ];
  const colorScheme = pairColorSchemes[index % pairColorSchemes.length];

  // Check if there's a custom prompt OR enhanced prompt for this pair
  const hasCustomPrompt = (pairPrompt && pairPrompt.trim()) || (pairNegativePrompt && pairNegativePrompt.trim()) || (enhancedPrompt && enhancedPrompt.trim());

  return (
    <React.Fragment key={`pair-${index}`}>
      {/* Main pair region */}
      <div
        className={`absolute top-0 bottom-0 ${colorScheme.bg} ${colorScheme.border} border-l-2 border-r-2 border-solid pointer-events-none`}
        style={{
          left: `${startPercent}%`,
          width: `${endPercent - startPercent}%`,
          transition: 'none', // Prevent jitter when coordinate system changes
        }}
      />

      {/* Context frames region - COMMENTED OUT */}
      {/* {contextFrames > 0 && visibleContextFrames > 0 && index < numPairs - 1 && (
        <div
          className={`absolute top-0 bottom-0 ${colorScheme.context} border-r border-dashed ${colorScheme.border.replace('border-', 'border-r-').replace('-300', '-400')} pointer-events-none`}
          style={{
            left: `${contextStartPercent}%`,
            width: `${endPercent - contextStartPercent}%`,
            transition: 'none', // Prevent jitter when coordinate system changes
          }}
        >
          <div className={`absolute bottom-2 left-1/2 transform -translate-x-1/2 text-xs font-light ${colorScheme.text} bg-card/80 dark:bg-gray-800/80 px-2 py-0.5 rounded`}>
            Context ({visibleContextFrames}f)
          </div>
        </div>
      )} */}

      {/* Connecting lines from pill to timeline items */}
      {/* Left connecting line - from left timeline item to pill */}
      <div
        className={`absolute top-1/2 h-[2px] ${colorScheme.line} pointer-events-none z-5`}
        style={{
          left: `${startPercent}%`,
          width: `${((startPercent + endPercent) / 2) - startPercent}%`,
          transform: 'translateY(-50%)',
          transition: 'none', // Prevent jitter when coordinate system changes
        }}
      />

      {/* Right connecting line - from pill to right timeline item */}
      <div
        className={`absolute top-1/2 h-[2px] ${colorScheme.line} pointer-events-none z-5`}
        style={{
          left: `${(startPercent + endPercent) / 2}%`,
          width: `${endPercent - ((startPercent + endPercent) / 2)}%`,
          transform: 'translateY(-50%)',
          transition: 'none', // Prevent jitter when coordinate system changes
        }}
      />

      {/* Pair label - only show if there's enough space and not hidden */}
      {showLabel && !hidePairLabel && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className={`absolute top-1/2 text-[11px] font-light ${colorScheme.text} bg-card/90 dark:bg-gray-800/90 px-2.5 py-1 rounded-full border ${colorScheme.border} z-20 shadow-sm ${
                  readOnly
                    ? 'cursor-default'
                    : 'cursor-pointer hover:bg-card dark:hover:bg-gray-800 hover:shadow-md'
                } transition-all duration-200`}
                style={{
                  left: `${(startPercent + endPercent) / 2}%`,
                  transform: 'translate(-50%, -50%)',
                  // Only animate hover effects, NOT position (left) to prevent jitter
                  transition: 'background-color 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out, color 0.2s ease-out',
                }}
                onClick={readOnly ? undefined : (e) => {
                  e.stopPropagation();
                  onPairClick?.(index);
                }}
                onTouchEnd={readOnly ? undefined : (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onPairClick?.(index);
                }}
              >
                <div className="flex items-center gap-1">
                  <span className="whitespace-nowrap">Pair {index + 1} • {framesToSeconds(actualFrames, timelineFps)}</span>
                  <MessageSquare
                    className={`h-2.5 w-2.5 ${hasCustomPrompt ? 'opacity-100' : 'text-gray-400 dark:text-gray-500 opacity-60'}`}
                  />
                </div>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <PairPromptTooltipContent
                pairPrompt={pairPrompt}
                pairNegativePrompt={pairNegativePrompt}
                enhancedPrompt={enhancedPrompt}
                onClearEnhancedPrompt={
                  onClearEnhancedPrompt ? () => onClearEnhancedPrompt(index) : undefined
                }
              />
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}

      {/* Generation boundary lines - COMMENTED OUT */}
      {/* <div
        className={`absolute top-0 bottom-0 w-[2px] ${colorScheme.line} pointer-events-none z-5`}
        style={{
          left: `${generationStartPercent}%`,
          transform: 'translateX(-50%)',
          transition: isDragging ? 'none' : 'left 0.2s ease-out',
        }}
      />
      <div
        className={`absolute top-0 bottom-0 w-[2px] ${colorScheme.line} pointer-events-none z-5`}
        style={{
          left: `${endPercent}%`,
          transform: 'translateX(-50%)',
          transition: isDragging ? 'none' : 'left 0.2s ease-out',
        }}
      /> */}
    </React.Fragment>
  );
};

const MemoizedPairRegion = React.memo(PairRegion);

export { MemoizedPairRegion as PairRegion };
