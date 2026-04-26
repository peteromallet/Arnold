import React, { useCallback, useMemo } from "react";
import { ShotPrimaryActionButton } from '@/shared/components/shots/ShotPrimaryActionButton';
import { ShotSelector, ShotOption } from "@/shared/components/selectors/ShotSelector";
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useShotNavigation } from "@/shared/hooks/shots/useShotNavigation";
import { useLastAffectedShot } from "@/shared/hooks/shots/useLastAffectedShot";
import { useQuickShotCreate } from "@/shared/hooks/useQuickShotCreate";
import { cn } from '@/shared/components/ui/contracts/cn';
import type { Shot } from "@/domains/generation/types";
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';

interface ShotSelectorWithAddProps {
  // Image data
  imageId: string;
  imageUrl?: string;
  thumbUrl?: string;

  // Shot options
  shots: ShotOption[];
  selectedShotId: string;
  onShotChange: (shotId: string) => void;

  // Add to shot functionality
  // CRITICAL: targetShotId is the shot selected in the DROPDOWN, not the shot being viewed
  onAddToShot: (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string) => Promise<boolean>;

  // Whether to show the "create shot" option in the dropdown
  showCreateShot?: boolean;

  // State tracking
  isAlreadyPositionedInSelectedShot?: boolean;
  showTick?: boolean;
  isAdding?: boolean;

  // Callbacks
  onShowTick?: (imageId: string) => void;
  onOptimisticPositioned?: (imageId: string, shotId: string) => void;
  onClose?: () => void; // Close lightbox when navigating to shot

  // Layout
  layout?: 'vertical' | 'horizontal';

  // Styling
  className?: string;
  selectorClassName?: string;
  buttonClassName?: string;

  // Portal container for select dropdown
  container?: HTMLElement | null;

  // Mobile mode
  isMobile?: boolean;
}

export const ShotSelectorWithAdd: React.FC<ShotSelectorWithAddProps> = ({
  imageId,
  imageUrl,
  thumbUrl,
  shots,
  selectedShotId,
  onShotChange,
  onAddToShot,
  showCreateShot = false,
  isAlreadyPositionedInSelectedShot = false,
  showTick = false,
  isAdding = false,
  onShowTick,
  onOptimisticPositioned,
  onClose,
  layout = 'vertical',
  className,
  selectorClassName,
  buttonClassName,
  container,
}) => {
  const { navigateToShot } = useShotNavigation();
  const { setLastAffectedShotId } = useLastAffectedShot();
  
  // Use consolidated hook for quick shot creation
  const {
    isCreatingShot,
    quickCreateSuccess,
    handleQuickCreateAndAdd,
    handleVisitCreatedShot,
  } = useQuickShotCreate({
    generationId: imageId,
    generationPreview: {
      imageUrl,
      thumbUrl,
    },
    shots,
    onShotChange,
    onClose,
  });
  
  // Get current target shot name for tooltips
  const currentTargetShotName = useMemo(() => {
    return selectedShotId ? shots.find(s => s.id === selectedShotId)?.name : undefined;
  }, [selectedShotId, shots]);
  
  // Handle add to shot click
  const handleAddClick = useCallback(async () => {
    // If in transient success or already positioned, navigate to shot
    if ((showTick || isAlreadyPositionedInSelectedShot) && selectedShotId && shots) {
      const targetShot = shots.find(s => s.id === selectedShotId);
      if (targetShot) {
        // Close lightbox before navigating
        onClose?.();
        const minimalShot: Shot = { id: targetShot.id, name: targetShot.name, images: [], position: 0 };
        navigateToShot(minimalShot, { scrollToTop: true });
        return;
      }
    }
    
    // If already positioned in shot, nothing else to do
    if (isAlreadyPositionedInSelectedShot) {
      return;
    }

    if (!selectedShotId) {
      toast({ title: "Select a Shot", description: "Please select a shot first to add this image.", variant: "destructive" });
      return;
    }
    
    try {
      // CRITICAL: Pass selectedShotId (the dropdown value) as targetShotId
      // This ensures the image is added to the shot the user SELECTED, not the shot being viewed
      const success = await onAddToShot(selectedShotId, imageId, imageUrl, thumbUrl);
      
      if (success) {
        onShowTick?.(imageId);
        onOptimisticPositioned?.(imageId, selectedShotId);
      }
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotSelectorWithAdd', toastTitle: 'Could not add image to shot' });
    }
  }, [showTick, isAlreadyPositionedInSelectedShot, selectedShotId, shots, navigateToShot, onAddToShot, imageId, imageUrl, thumbUrl, onShowTick, onOptimisticPositioned, onClose]);
  
  // Handle shot change
  const handleShotChange = useCallback((value: string) => {
    onShotChange(value);
    setLastAffectedShotId(value);
  }, [onShotChange, setLastAffectedShotId]);
  
  const isHorizontal = layout === 'horizontal';
  
  return (
    <div className={cn(
      "flex gap-1.5",
      isHorizontal ? "flex-row items-center" : "flex-col items-start",
      className
    )}>
      <ShotSelector
        value={selectedShotId}
        onValueChange={handleShotChange}
        shots={shots}
        placeholder="Shot..."
        triggerClassName={cn(
          "h-7 px-2 py-1 rounded-md bg-black/50 hover:bg-black/70 text-white text-xs min-w-[70px] max-w-[90px] truncate focus:ring-0 focus:ring-offset-0",
          selectorClassName
        )}
        contentClassName="w-[var(--anchor-width)]"
        showAddShot={showCreateShot}
        onCreateShot={handleQuickCreateAndAdd}
        isCreatingShot={isCreatingShot}
        quickCreateSuccess={quickCreateSuccess}
        onVisitCreatedShot={handleVisitCreatedShot}
        side="top"
        align="start"
        sideOffset={4}
        container={container}
        onNavigateToShot={(shot) => {
          onClose?.();
          const minimalShot: Shot = { id: shot.id, name: shot.name, images: [], position: 0 };
          navigateToShot(minimalShot, { scrollToTop: true });
        }}
      />

      <ShotPrimaryActionButton
        selectedShotId={selectedShotId}
        currentTargetShotName={currentTargetShotName}
        isLoading={isAdding}
        showTick={showTick}
        isAlreadyPositionedInSelectedShot={isAlreadyPositionedInSelectedShot}
        onClick={handleAddClick}
        className={cn(
          "h-7 w-7 p-0 rounded-full bg-black/50 hover:bg-black/70 text-white",
          showTick && 'bg-green-500 hover:bg-green-600 !text-white',
          isAlreadyPositionedInSelectedShot && !showTick && 'bg-gray-500/60 hover:bg-gray-600/70 !text-white',
          buttonClassName
        )}
      />
    </div>
  );
};
