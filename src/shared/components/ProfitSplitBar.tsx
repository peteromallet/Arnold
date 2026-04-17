import React, { useState } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useIsMobile } from '@/shared/hooks/mobile';

interface ProfitSplitBarProps {
  className?: string;
}

export const ProfitSplitBar: React.FC<ProfitSplitBarProps> = ({ className }) => {
  const isMobile = useIsMobile();

  // Controlled tooltip states to mirror HomePage behavior exactly
  const [engineersOpen, setEngineersOpen] = useState(false);
  const [artistsOpen, setArtistsOpen] = useState(false);
  const [banoOpen, setBanoOpen] = useState(false);

  return (
    <div className={className}>
      {/* Labels */}
      <div className="grid grid-cols-3 text-center text-sm font-theme-light text-primary">
        <div>Engineers</div>
        <div>Artists</div>
        <div>Banodoco</div>
      </div>
      {/* Thin split bar */}
      <div className="flex h-4 overflow-visible rounded-full">
        {/* Engineers (1/3) */}
        <div className="relative flex-1 cursor-default select-none rounded-l-full bg-transparent">
          <TooltipProvider>
            <Tooltip open={engineersOpen} onOpenChange={setEngineersOpen}>
              <TooltipTrigger asChild>
                <div
                  className="h-full w-full bg-wes-yellow dark:bg-amber-500 transition-all duration-200 hover:brightness-95"
                  aria-label="Engineers"
                  onClick={() => { if (isMobile) setEngineersOpen((v) => !v); }}
                />
              </TooltipTrigger>
              <TooltipContent side="bottom" align="center" className="px-2 py-1 text-center text-[11px] leading-tight max-w-[240px]">
                supporting developers whose LoRAs/workflows are used in Reigh, and funding open source projects (model training, extensions, etc.).
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Artists (1/3) */}
        <div className="relative flex-1 cursor-default select-none bg-transparent">
          <TooltipProvider>
            <Tooltip open={artistsOpen} onOpenChange={setArtistsOpen}>
              <TooltipTrigger asChild>
                <div
                  className="h-full w-full bg-wes-mint dark:bg-emerald-500 transition-all duration-200 hover:brightness-110"
                  aria-label="Artists"
                  onClick={() => { if (isMobile) setArtistsOpen((v) => !v); }}
                />
              </TooltipTrigger>
              <TooltipContent side="bottom" align="center" className="px-2 py-1 text-center text-[11px] leading-tight max-w-[240px]">
                supporting artists who refer others to Reigh, and funding art competitions and arts support.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Banodoco (1/3) */}
        <div className="relative flex-1 cursor-default select-none rounded-r-full bg-transparent">
          <TooltipProvider>
            <Tooltip open={banoOpen} onOpenChange={setBanoOpen}>
              <TooltipTrigger asChild>
                <div
                  className="h-full w-full bg-wes-pink dark:bg-orange-400 hover:bg-wes-pink-dark dark:hover:bg-orange-500 transition-all duration-200"
                  aria-label="Banodoco"
                  onClick={() => { if (isMobile) setBanoOpen((v) => !v); }}
                />
              </TooltipTrigger>
              <TooltipContent side="bottom" align="center" className="px-2 py-1 text-center text-[11px] leading-tight max-w-[240px]">
                funding Reigh and future projects.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </div>
  );
};
