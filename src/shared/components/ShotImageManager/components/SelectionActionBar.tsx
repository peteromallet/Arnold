import React, { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useIsMobile } from '@/shared/hooks/mobile';
import { MOBILE_BOTTOM_OFFSET, DESKTOP_BOTTOM_OFFSET } from '../constants';
import { FolderPlus, ExternalLink, Loader2 } from 'lucide-react';
import { usePanesStore } from '@/shared/state/panesStore';

interface SelectionActionBarProps {
  selectedCount: number;
  onDeselect: () => void;
  onDelete: () => void;
  /** Returns the new shot ID on success */
  onNewShot?: () => Promise<string | void>;
  /** Called when user clicks "Jump to shot" after creation */
  onJumpToShot?: (shotId: string) => void;
}

export const SelectionActionBar: React.FC<SelectionActionBarProps> = ({
  selectedCount,
  onDeselect,
  onDelete,
  onNewShot,
  onJumpToShot
}) => {
  const [newShotState, setNewShotState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [createdShotId, setCreatedShotId] = useState<string | null>(null);

  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);
  const isMobile = useIsMobile();

  const handleNewShot = async () => {
    if (!onNewShot || newShotState !== 'idle') return;
    setNewShotState('loading');
    setCreatedShotId(null);
    try {
      const shotId = await onNewShot();
      if (shotId) {
        setCreatedShotId(shotId);
      }
      setNewShotState('success');
    } catch {
      setNewShotState('idle');
      setCreatedShotId(null);
    }
  };

  const handleJumpToShot = () => {
    if (createdShotId && onJumpToShot) {
      onJumpToShot(createdShotId);
      setNewShotState('idle');
      setCreatedShotId(null);
      onDeselect();
    }
  };

  const leftOffset = isShotsPaneLocked ? shotsPaneWidth : 0;
  const rightOffset = isTasksPaneLocked ? tasksPaneWidth : 0;
  const bottomOffset = isMobile ? MOBILE_BOTTOM_OFFSET : DESKTOP_BOTTOM_OFFSET;

  return (
    <div
      className="fixed z-50 flex justify-center animate-in fade-in slide-in-from-bottom-4 duration-300 pointer-events-none"
      style={{
        left: `${leftOffset}px`,
        right: `${rightOffset}px`,
        paddingLeft: '16px',
        paddingRight: '16px',
        bottom: `${bottomOffset}px`,
      }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center gap-3 pointer-events-auto">
        <span className="text-sm font-light text-gray-700 dark:text-gray-300">
          {selectedCount} selected
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onDeselect}
            className="text-sm"
          >
            {selectedCount === 1 ? 'Deselect' : 'Deselect All'}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onDelete}
            className="text-sm"
          >
            {selectedCount === 1 ? 'Delete' : 'Delete All'}
          </Button>
          {onNewShot && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  {newShotState === 'success' && createdShotId && onJumpToShot ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleJumpToShot}
                      className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-950"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleNewShot}
                      disabled={newShotState === 'loading'}
                      className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    >
                      {newShotState === 'loading' ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <FolderPlus className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </TooltipTrigger>
                <TooltipContent>
                  <p>{newShotState === 'success' && createdShotId ? 'Go to new shot' : 'Create a new shot with the selected images'}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>
    </div>
  );
};
