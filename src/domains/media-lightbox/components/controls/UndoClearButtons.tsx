import React from 'react';
import { X, Undo2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

interface UndoClearButtonsProps {
  onUndo: () => void;
  onClear: () => void;
  disabled: boolean;
  variant: 'tablet' | 'mobile';
}

export const UndoClearButtons: React.FC<UndoClearButtonsProps> = ({
  onUndo,
  onClear,
  disabled,
  variant,
}) => {
  const buttonHeight = variant === 'tablet' ? 'h-7' : 'h-6';
  
  return (
    <div className="flex items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="secondary"
            size="sm"
            onClick={onUndo}
            disabled={disabled}
            className={`flex-1 text-xs ${buttonHeight}`}
          >
            <Undo2 className="h-3 w-3" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Undo</TooltipContent>
      </Tooltip>
      
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            onClick={onClear}
            disabled={disabled}
            className={`flex-1 text-xs ${buttonHeight}`}
          >
            <X className="h-3 w-3" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Clear all</TooltipContent>
      </Tooltip>
    </div>
  );
};
