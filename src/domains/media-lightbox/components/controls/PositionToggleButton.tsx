import React from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

interface PositionToggleButtonProps {
  direction: 'up' | 'down';
  onClick: () => void;
}

export const PositionToggleButton: React.FC<PositionToggleButtonProps> = ({
  direction,
  onClick,
}) => {
  const isUp = direction === 'up';
  const Icon = isUp ? ArrowUp : ArrowDown;
  const roundedClass = isUp ? 'rounded-t-md border-b-0' : 'rounded-b-md border-t-0';
  const marginClass = isUp ? '' : 'relative z-10';
  const tooltipText = isUp ? 'Move controls to top' : 'Move controls to bottom';
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          className={`mx-auto w-fit px-2 py-1 bg-background hover:bg-muted text-muted-foreground hover:text-foreground flex items-center justify-center transition-colors border border-border shadow-lg ${roundedClass} ${marginClass}`}
        >
          <Icon className={`h-3 w-3 ${isUp ? 'mt-0.5' : '-mt-0.5'}`} />
        </button>
      </TooltipTrigger>
      <TooltipContent>{tooltipText}</TooltipContent>
    </Tooltip>
  );
};
