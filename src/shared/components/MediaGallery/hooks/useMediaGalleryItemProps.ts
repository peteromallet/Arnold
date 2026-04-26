import { useMemo } from 'react';
import type {
  ItemActions,
  ItemFeatures,
  ItemLoading,
  ItemMobileInteraction,
  ItemShotWorkflow,
} from '@/shared/components/MediaGalleryItem/types';
import type { DisplayableMetadata, GeneratedImageWithMetadata, SimplifiedShotOption } from '../types';
import type { AddToShotHandler } from '@/shared/types/imageHandlers';
import type { MouseEvent } from 'react';

function resolveLightboxDeletingId(
  isDeleting: string | boolean | null | undefined,
  activeMediaId: string | undefined,
): string | null {
  if (typeof isDeleting === 'string') {
    return isDeleting;
  }
  if (isDeleting && activeMediaId) {
    return activeMediaId;
  }
  return null;
}

interface UseMediaGalleryItemShotOptionsProps {
  simplifiedShotOptions: SimplifiedShotOption[];
  currentViewingShotId?: string;
  onCreateShot?: (shotName: string, files: File[]) => Promise<void>;
  onAddToLastShot?: AddToShotHandler;
  onAddToLastShotWithoutPosition?: AddToShotHandler;
}

interface UseMediaGalleryItemFeaturesProps {
  showDelete: boolean;
  showDownload: boolean;
  showShare: boolean;
  showEdit: boolean;
  showStar: boolean;
  showAddToShot: boolean;
  enableSingleClick: boolean;
  videosAsThumbnails: boolean;
  onToggleStar?: (id: string, starred: boolean) => void;
  onApplySettings?: (metadata: DisplayableMetadata | undefined) => void;
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onContextMenu?: (event: MouseEvent, image: GeneratedImageWithMetadata) => void;
  isDeleting?: string | boolean | null;
}

interface UseMediaGalleryItemShotWorkflowProps {
  selectedShotIdLocal: string;
  setSelectedShotIdLocal: (id: string) => void;
  onShotChange: (shotId: string) => void;
  showTickForImageId: string | null;
  onShowTick: (imageId: string) => void;
  showTickForSecondaryImageId: string | null;
  onShowSecondaryTick: (imageId: string) => void;
  optimisticUnpositionedIds: Set<string>;
  optimisticPositionedIds: Set<string>;
  optimisticDeletedIds: Set<string>;
  onOptimisticUnpositioned: (imageId: string, shotId: string) => void;
  onOptimisticPositioned: (imageId: string, shotId: string) => void;
  addingToShotImageId: string | null;
  setAddingToShotImageId: (id: string | null) => void;
  addingToShotWithoutPositionImageId: string | null;
  setAddingToShotWithoutPositionImageId: (id: string | null) => void;
}

interface UseMediaGalleryItemMobileProps {
  mobileActiveImageId: string | null;
  mobilePopoverOpenImageId: string | null;
  onMobileTap: (image: GeneratedImageWithMetadata) => void;
  setMobilePopoverOpenImageId: (id: string | null) => void;
}

interface UseMediaGalleryItemActionsProps {
  onOpenLightbox: (image: GeneratedImageWithMetadata, autoEnterEditMode?: boolean) => void;
  onDelete?: (id: string) => void;
  onDownloadImage: (
    rawUrl: string,
    filename: string,
    imageId?: string,
    isVideo?: boolean,
    originalContentType?: string,
  ) => void;
}

interface UseMediaGalleryItemLoadingProps {
  activeLightboxMediaId?: string;
  downloadingImageId: string | null;
}

type UseMediaGalleryItemPropsParams = UseMediaGalleryItemShotOptionsProps &
  UseMediaGalleryItemFeaturesProps &
  UseMediaGalleryItemShotWorkflowProps &
  UseMediaGalleryItemMobileProps &
  UseMediaGalleryItemActionsProps &
  UseMediaGalleryItemLoadingProps;

export function useMediaGalleryItemProps({
  simplifiedShotOptions,
  currentViewingShotId,
  onCreateShot,
  onAddToLastShot,
  onAddToLastShotWithoutPosition,
  showDelete,
  showDownload,
  showShare,
  showEdit,
  showStar,
  showAddToShot,
  enableSingleClick,
  videosAsThumbnails,
  onToggleStar,
  onApplySettings,
  onImageClick,
  onContextMenu,
  isDeleting,
  selectedShotIdLocal,
  setSelectedShotIdLocal,
  onShotChange,
  showTickForImageId,
  onShowTick,
  showTickForSecondaryImageId,
  onShowSecondaryTick,
  optimisticUnpositionedIds,
  optimisticPositionedIds,
  optimisticDeletedIds,
  onOptimisticUnpositioned,
  onOptimisticPositioned,
  addingToShotImageId,
  setAddingToShotImageId,
  addingToShotWithoutPositionImageId,
  setAddingToShotWithoutPositionImageId,
  mobileActiveImageId,
  mobilePopoverOpenImageId,
  onMobileTap,
  setMobilePopoverOpenImageId,
  onOpenLightbox,
  onDelete,
  onDownloadImage,
  activeLightboxMediaId,
  downloadingImageId,
}: UseMediaGalleryItemPropsParams) {
  const itemShotWorkflow = useMemo<ItemShotWorkflow>(
    () => ({
      selectedShotIdLocal,
      simplifiedShotOptions,
      setSelectedShotIdLocal,
      setLastAffectedShotId: onShotChange,
      showTickForImageId,
      onShowTick,
      showTickForSecondaryImageId,
      onShowSecondaryTick,
      optimisticUnpositionedIds,
      optimisticPositionedIds,
      optimisticDeletedIds,
      onOptimisticUnpositioned,
      onOptimisticPositioned,
      addingToShotImageId,
      setAddingToShotImageId,
      addingToShotWithoutPositionImageId,
      setAddingToShotWithoutPositionImageId,
      currentViewingShotId,
      onCreateShot,
      onAddToLastShot,
      onAddToLastShotWithoutPosition,
    }),
    [
      selectedShotIdLocal,
      simplifiedShotOptions,
      setSelectedShotIdLocal,
      onShotChange,
      showTickForImageId,
      onShowTick,
      showTickForSecondaryImageId,
      onShowSecondaryTick,
      optimisticUnpositionedIds,
      optimisticPositionedIds,
      optimisticDeletedIds,
      onOptimisticUnpositioned,
      onOptimisticPositioned,
      addingToShotImageId,
      setAddingToShotImageId,
      addingToShotWithoutPositionImageId,
      setAddingToShotWithoutPositionImageId,
      currentViewingShotId,
      onCreateShot,
      onAddToLastShot,
      onAddToLastShotWithoutPosition,
    ],
  );

  const itemMobileInteraction = useMemo<Omit<ItemMobileInteraction, 'isMobile'>>(
    () => ({
      mobileActiveImageId,
      mobilePopoverOpenImageId,
      onMobileTap,
      setMobilePopoverOpenImageId,
    }),
    [mobileActiveImageId, mobilePopoverOpenImageId, onMobileTap, setMobilePopoverOpenImageId],
  );

  const itemFeatures = useMemo<ItemFeatures>(
    () => ({
      showDelete,
      showDownload,
      showShare,
      showEdit,
      showStar: showStar && typeof onToggleStar === 'function',
      showAddToShot,
      enableSingleClick,
      videosAsThumbnails,
    }),
    [
      showDelete,
      showDownload,
      showShare,
      showEdit,
      showStar,
      onToggleStar,
      showAddToShot,
      enableSingleClick,
      videosAsThumbnails,
    ],
  );

  const itemActions = useMemo<ItemActions>(
    () => ({
      onOpenLightbox,
      onDelete,
      onApplySettings,
      onDownloadImage,
      onToggleStar,
      onImageClick,
      onContextMenu,
    }),
    [onOpenLightbox, onDelete, onApplySettings, onDownloadImage, onToggleStar, onImageClick, onContextMenu],
  );

  const itemLoading = useMemo<Omit<ItemLoading, 'shouldLoad' | 'isPriority' | 'isGalleryLoading'>>(
    () => ({
      isDeleting,
      downloadingImageId,
    }),
    [isDeleting, downloadingImageId],
  );

  const lightboxDeletingId = useMemo(
    () => resolveLightboxDeletingId(isDeleting, activeLightboxMediaId),
    [isDeleting, activeLightboxMediaId],
  );

  return {
    itemShotWorkflow,
    itemMobileInteraction,
    itemFeatures,
    itemActions,
    itemLoading,
    lightboxDeletingId,
  };
}
