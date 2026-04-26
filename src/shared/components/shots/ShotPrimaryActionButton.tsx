import React from 'react';
import { Check, PlusCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

interface ShotPrimaryActionButtonProps {
  selectedShotId?: string | null;
  currentTargetShotName?: string;
  isLoading: boolean;
  showTick: boolean;
  isAlreadyPositionedInSelectedShot: boolean;
  onClick: () => void;
  className?: string;
}

function getAriaLabel(
  isAlreadyPositionedInSelectedShot: boolean,
  showTick: boolean,
  currentTargetShotName?: string,
): string {
  if (isAlreadyPositionedInSelectedShot || showTick) {
    return `Jump to ${currentTargetShotName}`;
  }

  return currentTargetShotName
    ? `Add to '${currentTargetShotName}' at final position`
    : 'Add to selected shot';
}

function getTooltipLabel(
  isAlreadyPositionedInSelectedShot: boolean,
  showTick: boolean,
  selectedShotId?: string | null,
  currentTargetShotName?: string,
): string {
  if (isAlreadyPositionedInSelectedShot || showTick) {
    return `Jump to ${currentTargetShotName || 'shot'}`;
  }

  return selectedShotId && currentTargetShotName
    ? `Add to '${currentTargetShotName}' at final position`
    : 'Select a shot then click to add';
}

export const ShotPrimaryActionButton: React.FC<ShotPrimaryActionButtonProps> = ({
  selectedShotId,
  currentTargetShotName,
  isLoading,
  showTick,
  isAlreadyPositionedInSelectedShot,
  onClick,
  className,
}) => {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="icon"
          className={className}
          onClick={onClick}
          disabled={!selectedShotId || isLoading}
          aria-label={getAriaLabel(
            isAlreadyPositionedInSelectedShot,
            showTick,
            currentTargetShotName,
          )}
          onPointerDown={(event) => event.stopPropagation()}
        >
          {isLoading ? (
            <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
          ) : showTick || isAlreadyPositionedInSelectedShot ? (
            <Check className="h-4 w-4" />
          ) : (
            <PlusCircle className="h-4 w-4" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        {getTooltipLabel(
          isAlreadyPositionedInSelectedShot,
          showTick,
          selectedShotId,
          currentTargetShotName,
        )}
      </TooltipContent>
    </Tooltip>
  );
};
