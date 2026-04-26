/**
 * Mobile-optimized ShotImageManager component
 * Handles selection-based reordering with arrow buttons
 */

import React, { useState, useCallback, useRef } from 'react';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { ConfirmDialog } from '@/shared/components/dialogs/ConfirmDialog';
import { BaseShotImageManagerProps } from './types';
import { useMarkVariantViewed } from '@/shared/hooks/variants/useMarkVariantViewed';
import { MobileImageGrid } from './components/MobileImageGrid';
import { MobileSelectionActionBar } from './components/MobileSelectionActionBar';
import { useMobileImageSelection } from './hooks/useMobileImageSelection';
import { useMobileOptimisticOrder } from './hooks/useMobileOptimisticOrder';
import { getMobileGridColsClass } from './constants';
import { usePanesStore } from '@/shared/state/panesStore';

export const ShotImageManagerMobile: React.FC<BaseShotImageManagerProps> = ({
  images,
  onImageDelete,
  onBatchImageDelete,
  onImageDuplicate,
  onImageReorder,
  onOpenLightbox,
  onInpaintClick,
  columns = 4,
  duplicatingImageId,
  duplicateSuccessImageId,
  projectAspectRatio,
  batchVideoFrames = 60,
  onImageUpload,
  isUploadingImage,
  onSelectionChange,
  readOnly = false,
  onPairClick,
  pairPrompts,
  enhancedPrompts,
  defaultPrompt,
  defaultNegativePrompt,
  onClearEnhancedPrompt,
  pairOverrides,
  segmentSlots,
  onSegmentClick,
  hasPendingTask,
  onNewShotFromSelection,
  onShotChange,
}) => {
  const {
    mobileSelectedIds,
    showSelectionBar,
    isInMoveMode,
    handleMobileTap,
    clearSelection,
  } = useMobileImageSelection({
    readOnly,
    onSelectionChange,
  });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[]>([]);
  const openConfirm = useCallback((ids: string[]) => {
    setPendingDeleteIds(ids);
    setConfirmOpen(true);
  }, []);
  const closeConfirm = useCallback(() => {
    setConfirmOpen(false);
    setPendingDeleteIds([]);
  }, []);
  const {
    currentImages,
    setOptimisticOrder,
    isOptimisticUpdate,
    setIsOptimisticUpdate,
  } = useMobileOptimisticOrder(images);

  const [newShotState, setNewShotState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [createdShotId, setCreatedShotId] = useState<string | null>(null);
  const newShotResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { markAllViewed } = useMarkVariantViewed();
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);

  // Use columns from useDeviceInfo (phones=2, tablet portrait=3, tablet landscape=4)
  const effectiveColumns = columns;
  const mobileGridColsClass = getMobileGridColsClass(effectiveColumns);

  // Cleanup newShotResetTimeout on unmount
  React.useEffect(() => {
    return () => {
      if (newShotResetTimeoutRef.current) {
        clearTimeout(newShotResetTimeoutRef.current);
      }
    };
  }, []);

  // Handler for creating a new shot from selected images
  const handleNewShot = useCallback(async () => {
    if (!onNewShotFromSelection || newShotState !== 'idle') return;
    setNewShotState('loading');
    setCreatedShotId(null);
    // Clear any existing reset timeout
    if (newShotResetTimeoutRef.current) {
      clearTimeout(newShotResetTimeoutRef.current);
      newShotResetTimeoutRef.current = null;
    }
    try {
      const shotId = await onNewShotFromSelection(mobileSelectedIds);
      if (shotId) {
        setCreatedShotId(shotId);
      }
      setNewShotState('success');
      // Auto-reset after 5 seconds if user doesn't click
      newShotResetTimeoutRef.current = setTimeout(() => {
        setNewShotState('idle');
        setCreatedShotId(null);
        newShotResetTimeoutRef.current = null;
      }, 5000);
    } catch {
      setNewShotState('idle');
      setCreatedShotId(null);
    }
  }, [onNewShotFromSelection, mobileSelectedIds, newShotState]);

  // Handler for jumping to the created shot
  const handleJumpToShot = useCallback(() => {
    if (createdShotId && onShotChange) {
      onShotChange(createdShotId);
      setNewShotState('idle');
      setCreatedShotId(null);
      clearSelection();
    }
  }, [clearSelection, createdShotId, onShotChange]);

  // Mobile reordering function
  const handleMobileMoveHere = useCallback(async (targetIndex: number) => {
    if (mobileSelectedIds.length === 0) {
      return;
    }

    try {
      // Get the selected images and their current indices
      // img.id is shot_generations.id - unique per entry
      const selectedItems = mobileSelectedIds.map(id => {
        const image = currentImages.find(img => img.id === id);
        const index = currentImages.findIndex(img => img.id === id);
        return { id, image, currentIndex: index };
      }).filter(item => item.image && item.currentIndex !== -1);

      if (selectedItems.length === 0) {
        return;
      }

      // Safety check: Ensure all images have id
      const hasMissingIds = currentImages.some(img => !img.id);
      if (hasMissingIds) {
        toast.error('Loading image metadata... please wait a moment and try again.');
        return;
      }

      // Sort by current index to maintain relative order
      selectedItems.sort((a, b) => a.currentIndex - b.currentIndex);

      // Create new order by moving selected items to target position
      const newOrder = [...currentImages];
      
      // Remove selected items from their current positions (in reverse order to maintain indices)
      selectedItems.reverse().forEach(item => {
        newOrder.splice(item.currentIndex, 1);
      });
      
      // Insert selected items at target position (maintaining their relative order)
      selectedItems.reverse().forEach((item, i) => {
        newOrder.splice(targetIndex + i, 0, item.image!);
      });

      // Create ordered IDs array for the unified system (safe now - checked above)
      const orderedIds = newOrder.map(img => img.id);
      
      // For single item moves, pass the dragged item ID for midpoint insertion
      const draggedItemId = selectedItems.length === 1 ? selectedItems[0].id : undefined;

      // 1. Apply optimistic update immediately for instant visual feedback
      setIsOptimisticUpdate(true);
      setOptimisticOrder(newOrder);

      // 2. Clear selection immediately for better UX
      clearSelection();

      // 3. Call server update
      await onImageReorder(orderedIds, draggedItemId);
      
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotImageManagerMobile', showToast: false });
      // Don't clear selection on error so user can retry
    }
  }, [clearSelection, mobileSelectedIds, currentImages, onImageReorder]);

  // Individual delete handler
  const handleIndividualDelete = useCallback((shotImageEntryId: string) => {
    onImageDelete(shotImageEntryId);
  }, [onImageDelete]);

  // Batch delete handler
  const performBatchDelete = useCallback(async (idsToDelete: string[]) => {
    // Filter out IDs that don't correspond to actual shotImageEntryIds
    // Filter to valid IDs only
    const validIds = idsToDelete.filter(id => {
      const img = currentImages.find(i => i.id === id);
      return img && img.id;
    });
    
    if (validIds.length < idsToDelete.length) {
      toast.warning(`Could only delete ${validIds.length} of ${idsToDelete.length} images. Some are still loading metadata.`);
    }

    if (validIds.length === 0) {
      toast.error('Unable to delete images. Metadata still loading, please wait a moment and try again.');
      closeConfirm();
      return;
    }
    
    if (onBatchImageDelete) {
      await onBatchImageDelete(validIds);
    } else {
      // Fallback to individual deletes
      for (const id of validIds) {
        await onImageDelete(id);
      }
    }
    
    // Clear selections and close dialog
    clearSelection();
    closeConfirm();
  }, [clearSelection, closeConfirm, currentImages, onImageDelete, onBatchImageDelete]);

  // Check if item would actually move
  const wouldActuallyMove = useCallback((insertIndex: number) => {
    if (mobileSelectedIds.length === 0) return false;
    
    const selectedIndices = mobileSelectedIds
      .map(id => currentImages.findIndex(img => img.id === id))
      .filter(idx => idx !== -1)
      .sort((a, b) => a - b);
    
    const minSelected = selectedIndices[0];
    const maxSelected = selectedIndices[selectedIndices.length - 1];
    
    return insertIndex < minSelected || insertIndex > maxSelected + 1;
  }, [mobileSelectedIds, currentImages]);

  if (!currentImages || currentImages.length === 0) {
    return (
      <p className="text-center text-gray-500 dark:text-gray-400 py-8">
        No images to display. 
        <span className="block text-sm mt-1 opacity-75">Upload images or 
          <span className="font-medium text-blue-600 dark:text-blue-400 ml-1">
            generate images
          </span>
        </span>
      </p>
    );
  }

  // Determine grid columns for positioning logic (same as effectiveColumns)
  const gridColumns = columns;

  // Always use grid view - no mode switching to prevent component unmount/remount flashing
  return (
    <>
      <MobileImageGrid
        images={currentImages}
        layout={{
          mobileGridColsClass,
          gridColumns,
          projectAspectRatio,
          batchVideoFrames,
        }}
        selection={{
          selectedIds: mobileSelectedIds,
          isInMoveMode,
          wouldActuallyMove,
        }}
        actions={{
          readOnly,
          onMobileTap: handleMobileTap,
          onDeleteImage: handleIndividualDelete,
          onMoveHere: handleMobileMoveHere,
          onOpenLightbox,
          onInpaintClick,
          onImageDuplicate,
          duplicatingImageId,
          duplicateSuccessImageId,
          onMarkAllViewed: markAllViewed,
        }}
        pairing={{
          onPairClick,
          pairPrompts,
          enhancedPrompts,
          defaultPrompt,
          defaultNegativePrompt,
          onClearEnhancedPrompt,
          pairOverrides,
          segmentSlots,
          onSegmentClick,
          hasPendingTask,
        }}
        upload={{
          enabled: Boolean(onImageUpload),
          isUploadingImage: Boolean(isUploadingImage),
          onUpload: onImageUpload,
        }}
      />

      <MobileSelectionActionBar
        visible={!readOnly && showSelectionBar}
        selectedCount={mobileSelectedIds.length}
        isShotsPaneLocked={isShotsPaneLocked}
        isTasksPaneLocked={isTasksPaneLocked}
        shotsPaneWidth={shotsPaneWidth}
        tasksPaneWidth={tasksPaneWidth}
        onDeselect={() => {
          clearSelection();
        }}
        onDelete={() => {
          openConfirm([...mobileSelectedIds]);
        }}
        canCreateShot={Boolean(onNewShotFromSelection)}
        newShotState={newShotState}
        createdShotId={createdShotId}
        onCreateShot={handleNewShot}
        onJumpToShot={handleJumpToShot}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeConfirm();
          } else {
            setConfirmOpen(true);
          }
        }}
        title="Delete Images"
        description={`Are you sure you want to delete ${pendingDeleteIds.length} selected image${pendingDeleteIds.length > 1 ? 's' : ''}? This action cannot be undone.`}
        confirmText={`Delete ${pendingDeleteIds.length} Image${pendingDeleteIds.length > 1 ? 's' : ''}`}
        cancelText="Cancel"
        destructive
        onConfirm={() => performBatchDelete(pendingDeleteIds)}
      />
    </>
  );
};
