import { useMediaGalleryHandlers } from './useMediaGalleryHandlers';
import { useMobileInteractions } from './useMobileInteractions';
import { useMediaGalleryItemProps } from './useMediaGalleryItemProps';
import type {
  DisplayableMetadata,
  GeneratedImageWithMetadata,
  NavigableShot,
  SimplifiedShotOption,
} from '../types';
import type { AddToShotHandler } from '@/shared/types/imageHandlers';
import type { MouseEvent } from 'react';

interface MediaGalleryViewActionsHook {
  handleCloseLightbox: () => void;
  handleOpenLightbox: (image: GeneratedImageWithMetadata, autoEnterEditMode?: boolean) => void;
  handleShotChange: (shotId: string) => void;
  handleShowTick: (imageId: string) => void;
  handleShowSecondaryTick: (imageId: string) => void;
  handleOptimisticDelete: (imageId: string) => Promise<void>;
  handleDownloadImage: (
    rawUrl: string,
    filename: string,
    imageId?: string,
    isVideo?: boolean,
    originalContentType?: string,
  ) => Promise<void>;
}

interface MediaGalleryViewFiltersHook {
  setShotFilter: (value: string) => void;
}

interface MediaGalleryViewStateHook {
  state: {
    activeLightboxMedia: GeneratedImageWithMetadata | null;
    mobilePopoverOpenImageId: string | null;
    selectedShotIdLocal: string;
    showTickForImageId: string | null;
    showTickForSecondaryImageId: string | null;
    optimisticUnpositionedIds: Set<string>;
    optimisticPositionedIds: Set<string>;
    optimisticDeletedIds: Set<string>;
    addingToShotImageId: string | null;
    addingToShotWithoutPositionImageId: string | null;
    mobileActiveImageId: string | null;
  };
  setSelectedImageForDetails: (image: GeneratedImageWithMetadata | null) => void;
  setShowTaskDetailsModal: (show: boolean) => void;
  setActiveLightboxMedia: (media: GeneratedImageWithMetadata | null) => void;
  setMobileActiveImageId: (id: string | null) => void;
  setMobilePopoverOpenImageId: (id: string | null) => void;
  setSelectedShotIdLocal: (id: string) => void;
  markOptimisticUnpositioned: (mediaId: string, shotId: string) => void;
  markOptimisticPositioned: (mediaId: string, shotId: string) => void;
  setAddingToShotImageId: (id: string | null) => void;
  setAddingToShotWithoutPositionImageId: (id: string | null) => void;
}

interface UseMediaGalleryViewInteractionsParams {
  allShots: NavigableShot[];
  simplifiedShotOptions: SimplifiedShotOption[];
  navigateToShot: (shot: NavigableShot) => void;
  actionsHook: MediaGalleryViewActionsHook;
  formAssociatedShotId?: string;
  onSwitchToAssociatedShot?: ((shotId: string) => void) | undefined;
  filtersHook: MediaGalleryViewFiltersHook;
  stateHook: MediaGalleryViewStateHook;
  isMobile: boolean;
  onCreateShot?: ((shotName: string, files: File[]) => Promise<void>) | undefined;
  onAddToLastShot?: AddToShotHandler | undefined;
  onAddToLastShotWithoutPosition?: AddToShotHandler | undefined;
  showDelete: boolean;
  showDownload: boolean;
  showShare: boolean;
  showEdit: boolean;
  showStar: boolean;
  showAddToShot: boolean;
  enableSingleClick: boolean;
  videosAsThumbnails: boolean;
  onToggleStar?: ((id: string, starred: boolean) => void) | undefined;
  onApplySettings?: ((metadata: DisplayableMetadata | undefined) => Promise<void> | void) | undefined;
  onImageClick?: ((image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void) | undefined;
  onContextMenu?: ((event: MouseEvent, image: GeneratedImageWithMetadata) => void) | undefined;
  isDeleting?: string | boolean | null;
  currentViewingShotId?: string;
  activeLightboxMediaId?: string;
  downloadingImageId?: string | null;
}

export function useMediaGalleryViewInteractions(params: UseMediaGalleryViewInteractionsParams) {
  const {
    allShots,
    simplifiedShotOptions,
    navigateToShot,
    actionsHook,
    formAssociatedShotId,
    onSwitchToAssociatedShot,
    filtersHook,
    stateHook,
    isMobile,
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
    currentViewingShotId,
    activeLightboxMediaId,
    downloadingImageId,
  } = params;

  const galleryHandlers = useMediaGalleryHandlers({
    allShots,
    simplifiedShotOptions,
    navigateToShot,
    closeLightbox: actionsHook.handleCloseLightbox,
    formAssociatedShotId,
    onSwitchToAssociatedShot,
    setShotFilter: filtersHook.setShotFilter,
    activeLightboxMedia: stateHook.state.activeLightboxMedia,
    setSelectedImageForDetails: stateHook.setSelectedImageForDetails,
    setShowTaskDetailsModal: stateHook.setShowTaskDetailsModal,
    setActiveLightboxMedia: stateHook.setActiveLightboxMedia,
  });

  const mobileInteractions = useMobileInteractions({
    isMobile,
    setMobileActiveImageId: stateHook.setMobileActiveImageId,
    mobilePopoverOpenImageId: stateHook.state.mobilePopoverOpenImageId,
    setMobilePopoverOpenImageId: stateHook.setMobilePopoverOpenImageId,
    onOpenLightbox: actionsHook.handleOpenLightbox,
  });

  const {
    handleNavigateToShot,
    handleVisitShotFromNotifier,
    handleSwitchToAssociatedShot,
    handleShowAllShots,
    handleShowTaskDetails,
  } = galleryHandlers;

  const {
    itemShotWorkflow,
    itemMobileInteraction,
    itemFeatures,
    itemActions,
    itemLoading,
    lightboxDeletingId,
  } = useMediaGalleryItemProps({
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
    selectedShotIdLocal: stateHook.state.selectedShotIdLocal,
    setSelectedShotIdLocal: stateHook.setSelectedShotIdLocal,
    onShotChange: actionsHook.handleShotChange,
    showTickForImageId: stateHook.state.showTickForImageId,
    onShowTick: actionsHook.handleShowTick,
    showTickForSecondaryImageId: stateHook.state.showTickForSecondaryImageId,
    onShowSecondaryTick: actionsHook.handleShowSecondaryTick,
    optimisticUnpositionedIds: stateHook.state.optimisticUnpositionedIds,
    optimisticPositionedIds: stateHook.state.optimisticPositionedIds,
    optimisticDeletedIds: stateHook.state.optimisticDeletedIds,
    onOptimisticUnpositioned: stateHook.markOptimisticUnpositioned,
    onOptimisticPositioned: stateHook.markOptimisticPositioned,
    addingToShotImageId: stateHook.state.addingToShotImageId,
    setAddingToShotImageId: stateHook.setAddingToShotImageId,
    addingToShotWithoutPositionImageId: stateHook.state.addingToShotWithoutPositionImageId,
    setAddingToShotWithoutPositionImageId: stateHook.setAddingToShotWithoutPositionImageId,
    mobileActiveImageId: stateHook.state.mobileActiveImageId,
    mobilePopoverOpenImageId: stateHook.state.mobilePopoverOpenImageId,
    onMobileTap: mobileInteractions.handleMobileTap,
    setMobilePopoverOpenImageId: stateHook.setMobilePopoverOpenImageId,
    onOpenLightbox: actionsHook.handleOpenLightbox,
    onDelete: actionsHook.handleOptimisticDelete,
    onDownloadImage: actionsHook.handleDownloadImage,
    activeLightboxMediaId,
    downloadingImageId,
  });

  return {
    handleNavigateToShot,
    handleVisitShotFromNotifier,
    handleSwitchToAssociatedShot,
    handleShowAllShots,
    handleShowTaskDetails,
    itemShotWorkflow,
    itemMobileInteraction,
    itemFeatures,
    itemActions,
    itemLoading,
    lightboxDeletingId,
  };
}
