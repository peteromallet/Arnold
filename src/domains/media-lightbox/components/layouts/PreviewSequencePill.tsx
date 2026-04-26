import React from 'react';
import { Play } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';

interface PreviewSequencePillProps {
  adjacentVideoThumbnails: {
    prev?: { thumbUrl: string; pairIndex: number };
    current?: { thumbUrl: string; pairIndex: number };
    next?: { thumbUrl: string; pairIndex: number };
  };
  onOpenPreviewDialog: (startAtPairIndex: number) => void;
}

const THUMB = 'h-full w-8 md:w-9 object-cover transition-all duration-200';

export const PreviewSequencePill: React.FC<PreviewSequencePillProps> = ({
  adjacentVideoThumbnails,
  onOpenPreviewDialog,
}) => {
  const { prev, current, next } = adjacentVideoThumbnails;

  return (
    <TooltipProvider delayDuration={300}>
      <div
        className="group/pill relative flex items-center rounded-full bg-black/50 backdrop-blur-sm border border-white/20 hover:border-white/40 hover:shadow-lg transition-all duration-300 overflow-hidden h-8 md:h-9 cursor-pointer"
      >
        {/* Thumbnails collapse via negative margin, expand on hover */}
        <div className="flex items-center h-full -space-x-4 group-hover/pill:space-x-0 transition-all duration-300">
          {/* Prev slot */}
          {prev ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onOpenPreviewDialog(prev.pairIndex); }}
                  className="relative z-10 h-full flex-shrink-0 hover:z-30"
                >
                  <img
                    src={prev.thumbUrl}
                    alt="Previous segment"
                    className={`${THUMB} brightness-[0.4] group-hover/pill:brightness-[0.6] hover:!brightness-90`}
                  />
                </button>
              </TooltipTrigger>
              <TooltipContent>Preview from previous</TooltipContent>
            </Tooltip>
          ) : (
            <div className="relative z-10 h-full w-8 md:w-9 flex-shrink-0 bg-white/5" />
          )}

          {/* Current slot — play icon overlay */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenPreviewDialog(current?.pairIndex ?? 0);
                }}
                className="group/current relative z-20 h-full flex-shrink-0"
              >
                {current && (
                  <img
                    src={current.thumbUrl}
                    alt="Current segment"
                    className={`${THUMB} brightness-75 group-hover/current:brightness-100`}
                  />
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="rounded-full bg-black/40 p-1 transition-colors">
                    <Play className="w-3 h-3 text-white fill-white ml-px" />
                  </div>
                </div>
              </button>
            </TooltipTrigger>
            <TooltipContent>Preview from current</TooltipContent>
          </Tooltip>

          {/* Next slot */}
          {next ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onOpenPreviewDialog(next.pairIndex); }}
                  className="relative z-10 h-full flex-shrink-0 hover:z-30"
                >
                  <img
                    src={next.thumbUrl}
                    alt="Next segment"
                    className={`${THUMB} brightness-[0.4] group-hover/pill:brightness-[0.6] hover:!brightness-90`}
                  />
                </button>
              </TooltipTrigger>
              <TooltipContent>Preview from next</TooltipContent>
            </Tooltip>
          ) : (
            <div className="relative z-10 h-full w-8 md:w-9 flex-shrink-0 bg-white/5" />
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};
