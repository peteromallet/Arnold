import React, { useEffect, useCallback, useRef, useMemo } from "react";
import {
  useProjectCrudContext,
  useProjectSelectionContext,
} from '@/shared/contexts/ProjectContext';
import { useIsMobile, useIsTablet } from "@/shared/hooks/mobile";
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { useTaskDetails } from '@/shared/components/ShotImageManager/hooks/useTaskDetails';
import { useBackgroundThumbnailGenerator } from '@/shared/hooks/media/useBackgroundThumbnailGenerator';
import { TooltipProvider } from "@/shared/components/ui/tooltip";
import { cn } from '@/shared/components/ui/contracts/cn';
import { useMediaGalleryState } from '@/shared/components/MediaGallery/hooks/useMediaGalleryState';
import { useMediaGalleryFilters } from '@/shared/components/MediaGallery/hooks/useMediaGalleryFilters';
import { useMediaGalleryPagination } from '@/shared/components/MediaGallery/hooks/useMediaGalleryPagination';
import { useMediaGalleryActions } from '@/shared/components/MediaGallery/hooks/useMediaGalleryActions';
import { useContainerWidth } from '@/shared/components/MediaGallery/hooks/useContainerWidth';
import { useLightboxNavigation } from '@/shared/components/MediaGallery/hooks/useLightboxNavigation';
import { MediaGalleryHeader } from '@/shared/components/MediaGallery/components/MediaGalleryHeader';
import { ShotNotifier } from '@/shared/components/MediaGallery/components/ShotNotifier';
import { MediaGalleryGrid } from '@/shared/components/MediaGallery/components/MediaGalleryGrid';
import { MediaGalleryLightbox } from '@/shared/components/MediaGallery/components/MediaGalleryLightbox';
import { MobileBottomBar } from '@/shared/components/MediaGallery/components/MobileBottomBar';
import { useMediaGalleryDebugTools } from '@/shared/components/MediaGallery/hooks/useMediaGalleryDebugTools';
import { usePaginatedImagesWithBadges } from '@/shared/components/MediaGallery/hooks/usePaginatedImagesWithBadges';
import { useMediaGalleryLightboxSession } from '@/shared/components/MediaGallery/hooks/useMediaGalleryLightboxSession';
import { useMediaGalleryViewInteractions } from '@/shared/components/MediaGallery/hooks/useMediaGalleryViewInteractions';
import type {
  MediaGalleryProps,
  GalleryConfig,
} from '@/shared/components/MediaGallery/types';
import { DEFAULT_GALLERY_CONFIG } from '@/shared/components/MediaGallery/types';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { GRID_COLUMN_CLASSES, calculateGalleryLayout } from '@/shared/components/MediaGallery/utils';
import { useCurrentShot, useShotAdditionSelectionOptional } from '@/shared/state/selectionStore';

interface UseAspectRatioLayoutParams {
  projectAspectRatio?: string;
  isMobile: boolean;
  containerWidth: number;
  reducedSpacing: boolean;
  columnsPerRow: 'auto' | number;
  itemsPerPage?: number;
}

function useAspectRatioLayout({
  projectAspectRatio,
  isMobile,
  containerWidth,
  reducedSpacing,
  columnsPerRow,
  itemsPerPage,
}: UseAspectRatioLayoutParams) {
  const aspectRatioLayout = useMemo(
    () => calculateGalleryLayout(projectAspectRatio, isMobile, containerWidth, undefined, reducedSpacing),
    [projectAspectRatio, isMobile, containerWidth, reducedSpacing],
  );

  const effectiveColumnsPerRow = columnsPerRow === 'auto' ? aspectRatioLayout.columns : columnsPerRow;
  const defaultItemsPerPage = aspectRatioLayout.itemsPerPage;

  const rawItemsPerPage = itemsPerPage ?? defaultItemsPerPage;
  const actualItemsPerPage =
    Math.floor(rawItemsPerPage / effectiveColumnsPerRow) * effectiveColumnsPerRow || effectiveColumnsPerRow;

  const gridColumnClasses = useMemo(
    () =>
      GRID_COLUMN_CLASSES[effectiveColumnsPerRow as keyof typeof GRID_COLUMN_CLASSES] ||
      aspectRatioLayout.gridColumnClasses,
    [effectiveColumnsPerRow, aspectRatioLayout.gridColumnClasses],
  );

  return {
    aspectRatioLayout,
    effectiveColumnsPerRow,
    actualItemsPerPage,
    gridColumnClasses,
  };
}

const MediaGallery: React.FC<MediaGalleryProps> = React.memo((props) => {
  const {
    images,
    onDelete,
    isDeleting,
    onApplySettings,
    allShots,
    lastShotId,
    onAddToLastShot,
    onAddToLastShotWithoutPosition,
    currentToolType,
    initialFilterState = true,
    currentViewingShotId,
    columnsPerRow = 'auto',
    pagination,
    filters,
    onFiltersChange,
    defaultFilters,
    onToggleStar,
    currentToolTypeName: _currentToolTypeName,
    formAssociatedShotId,
    onSwitchToAssociatedShot,
    className,
    selectedIds,
    generationFilters,
    onCreateShot,
    lastShotNameForTooltip: _lastShotNameForTooltip,
    onBackfillRequest,
    onImageClick,
    onContextMenu,
    config: configOverrides,
  } = props;
  const config: GalleryConfig = React.useMemo(() => ({
    ...DEFAULT_GALLERY_CONFIG,
    ...configOverrides,
  }), [configOverrides]);
  const {
    offset = 0,
    totalCount,
    itemsPerPage,
    onServerPageChange,
    serverPage,
    enableAdjacentPagePreloading = true,
  } = pagination ?? {};
  const {
    showDelete, showDownload, showShare, showEdit, showStar, showAddToShot,
    enableSingleClick, videosAsThumbnails, darkSurface, reducedSpacing,
    showShotFilter, showSearch,
    hidePagination, hideTopFilters, hideMediaTypeFilter, hideBottomPagination, hideShotNotifier,
  } = config;
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const { currentShotId } = useCurrentShot();
  const currentProject = projects.find(p => p.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio;
  const rawIsMobile = useIsMobile();
  const isTablet = useIsTablet();
  const [galleryContainerRef, containerWidth] = useContainerWidth();
  const isMobile = rawIsMobile ?? (typeof window !== 'undefined' && window.innerWidth < 768);
  const isPhoneOnly = isMobile && !isTablet;
  useMediaGalleryDebugTools({
    currentToolType,
    filtersMediaType: filters?.mediaType,
    defaultFiltersMediaType: defaultFilters?.mediaType,
    imagesLength: images?.length ?? 0,
    isMobile,
  });
  const { navigateToShot } = useShotNavigation();
  const {
    effectiveColumnsPerRow,
    actualItemsPerPage,
    gridColumnClasses,
  } = useAspectRatioLayout({
    projectAspectRatio,
    isMobile,
    containerWidth,
    reducedSpacing,
    columnsPerRow,
    itemsPerPage,
  });
  const simplifiedShotOptions = React.useMemo(() =>
    [...allShots]
      .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
      .map(s => ({
        id: s.id,
        name: s.name,
        settings: s.settings,
        created_at: s.created_at
      })),
    [allShots]
  );
  const stateHook = useMediaGalleryState({
    images,
    currentShotId: currentShotId ?? undefined,
    lastShotId,
    simplifiedShotOptions,
    isServerPagination: !!(onServerPageChange && serverPage),
    serverPage,
  });
  const filtersHook = useMediaGalleryFilters({
    images,
    optimisticDeletedIds: stateHook.state.optimisticDeletedIds,
    currentToolType,
    initialFilterState,
    onServerPageChange,
    serverPage,
    filters,
    onFiltersChange,
    defaultFilters,
  });
  const hasFilters = filtersHook.filterByToolType || filtersHook.mediaTypeFilter !== 'all' || !!filtersHook.searchTerm.trim() || filtersHook.showStarredOnly || !filtersHook.toolTypeFilterEnabled;
  const paginationHook = useMediaGalleryPagination({
    filteredImages: filtersHook.filteredImages,
    itemsPerPage: actualItemsPerPage,
    onServerPageChange,
    serverPage,
    offset,
    totalCount,
    enableAdjacentPagePreloading,
    isMobile,
    galleryTopRef: stateHook.galleryTopRef,
  });
  const withPaginationReset = useCallback(<T,>(fn: () => T): T => {
    const result = fn();
    paginationHook.goToFirstPage();
    if (paginationHook.isServerPagination) {
      paginationHook.startNavigation();
    }
    return result;
  }, [paginationHook]);
  const handlePageBoundsExceeded = useCallback((newLastPage: number) => {
    if (onServerPageChange) {
      onServerPageChange(newLastPage);
    }
  }, [onServerPageChange]);
  const actionsHook = useMediaGalleryActions({
    onDelete,
    onApplySettings,
    onAddToLastShot,
    onAddToLastShotWithoutPosition,
    onToggleStar,
    activeLightboxMedia: stateHook.state.activeLightboxMedia,
    setActiveLightboxMedia: stateHook.setActiveLightboxMedia,
    setAutoEnterEditMode: stateHook.setAutoEnterEditMode,
    markOptimisticDeleted: stateHook.markOptimisticDeleted,
    markOptimisticDeletedWithBackfill: stateHook.markOptimisticDeletedWithBackfill,
    removeOptimisticDeleted: stateHook.removeOptimisticDeleted,
    setDownloadingImageId: stateHook.setDownloadingImageId,
    setShowTickForImageId: stateHook.setShowTickForImageId,
    setShowTickForSecondaryImageId: stateHook.setShowTickForSecondaryImageId,
    mainTickTimeoutRef: stateHook.mainTickTimeoutRef,
    secondaryTickTimeoutRef: stateHook.secondaryTickTimeoutRef,
    onBackfillRequest,
    serverPage,
    itemsPerPage: actualItemsPerPage,
    isServerPagination: paginationHook.isServerPagination,
    setIsBackfillLoading: stateHook.setIsBackfillLoading,
    filteredImages: filtersHook.filteredImages,
    setIsDownloadingStarred: stateHook.setIsDownloadingStarred,
    setSelectedShotIdLocal: stateHook.setSelectedShotIdLocal,
    totalCount,
    optimisticDeletedCount: stateHook.state.optimisticDeletedIds.size,
    onPageBoundsExceeded: handlePageBoundsExceeded,
  });
  const shotAdditionSelection = useShotAdditionSelectionOptional();
  useEffect(() => {
    const selectedShotId = shotAdditionSelection?.selectedShotId;
    if (!selectedShotId) {
      return;
    }
    actionsHook.handleShotChange(selectedShotId);
    shotAdditionSelection.clearSelectedShotForAddition();
  }, [actionsHook, shotAdditionSelection]);
  const lightboxImageId = getGenerationId(stateHook.state.activeLightboxMedia);
  const {
    taskDetailsData,
    taskMapping: lightboxTaskMapping,
    task,
    taskError,
  } = useTaskDetails({
    generationId: lightboxImageId,
    projectId: selectedProjectId ?? null,
    onClose: actionsHook.handleCloseLightbox,
  });
  const inputImages = taskDetailsData?.inputImages || [];
  useBackgroundThumbnailGenerator({
    videos: paginationHook.paginatedImages || [],
    projectId: selectedProjectId,
    enabled: !!selectedProjectId && (paginationHook.paginatedImages?.length || 0) > 0,
  });
  const { paginatedImagesWithBadges } = usePaginatedImagesWithBadges({
    paginatedImages: paginationHook.paginatedImages,
  });
  const effectivePage = paginationHook.isServerPagination
    ? Math.max(0, (serverPage ?? 1) - 1)
    : paginationHook.page;
  const {
    handleNextImage,
    handlePreviousImage,
    handleSetActiveLightboxIndex,
    pendingTargetSetTimeRef,
  } = useLightboxNavigation({
    activeLightboxMedia: stateHook.state.activeLightboxMedia,
    filteredImages: filtersHook.filteredImages,
    isServerPagination: paginationHook.isServerPagination,
    serverPage,
    totalPages: paginationHook.totalPages,
    onServerPageChange,
    handleOpenLightbox: actionsHook.handleOpenLightbox,
    setPendingLightboxTarget: stateHook.setPendingLightboxTarget,
  });
  const prevFilteredImagesRef = useRef<string>('');
  useEffect(() => {
    const currentSignature = `${filtersHook.filteredImages.length}-${filtersHook.filteredImages[0]?.id?.substring(0,8) ?? 'none'}-${filtersHook.filteredImages[filtersHook.filteredImages.length-1]?.id?.substring(0,8) ?? 'none'}`;
    prevFilteredImagesRef.current = currentSignature;
    if (stateHook.state.pendingLightboxTarget && filtersHook.filteredImages.length > 0) {
      const targetIndex = stateHook.state.pendingLightboxTarget === 'first' ? 0 : filtersHook.filteredImages.length - 1;
      const targetImage = filtersHook.filteredImages[targetIndex];
      if (targetImage) {
        actionsHook.handleOpenLightbox(targetImage);
        stateHook.setPendingLightboxTarget(null);
        pendingTargetSetTimeRef.current = null;
      }
    }
  }, [actionsHook, filtersHook.filteredImages, pendingTargetSetTimeRef, serverPage, stateHook]);
  const {
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
  } = useMediaGalleryViewInteractions({
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
    activeLightboxMediaId: stateHook.state.activeLightboxMedia?.id,
    downloadingImageId: stateHook.state.downloadingImageId,
  });
  const lightboxSession = useMediaGalleryLightboxSession({
    stateHook,
    actionsHook,
    filtersHook,
    paginationHook,
    serverPage,
    handleNextImage,
    handlePreviousImage,
    handleSetActiveLightboxIndex,
    lightboxDeletingId,
    onApplySettings,
    simplifiedShotOptions,
    onAddToLastShot,
    onAddToLastShotWithoutPosition,
    isMobile,
    task,
    taskDetailsLoading: taskDetailsData?.isLoading ?? false,
    taskError,
    inputImages,
    lightboxTaskMapping,
    onCreateShot,
    handleNavigateToShot,
    handleShowTaskDetails,
    currentToolType,
    showDelete,
  });
  return (
    <TooltipProvider>
      <div
        ref={galleryContainerRef as React.RefObject<HTMLDivElement>}
        className={cn(
          'space-y-6',
          isMobile && !hidePagination ? 'pb-16' : (reducedSpacing ? 'pb-0' : ((!hidePagination && !hideBottomPagination) ? 'pb-[62px]' : 'pb-0')),
          className
        )}
      >
        {/* Header section with pagination and filters */}
        <div ref={stateHook.galleryTopRef}>
          <MediaGalleryHeader
            totalPages={paginationHook.totalPages}
            page={paginationHook.page}
            isServerPagination={paginationHook.isServerPagination}
            serverPage={serverPage}
            rangeStart={paginationHook.rangeStart}
            rangeEnd={paginationHook.rangeEnd}
            totalFilteredItems={paginationHook.totalFilteredItems}
            loadingButton={paginationHook.loadingButton}
            darkSurface={darkSurface}
            reducedSpacing={reducedSpacing}
            hidePagination={hidePagination}
            onPageChange={paginationHook.handlePageChange}
            isPhoneOnly={isPhoneOnly}
            hideTopFilters={hideTopFilters}
            hideMediaTypeFilter={hideMediaTypeFilter}
            showStarredOnly={filtersHook.showStarredOnly}
            onStarredFilterChange={(val) => withPaginationReset(() => filtersHook.setShowStarredOnly(Boolean(val)))}
            showShotFilter={showShotFilter}
            allShots={simplifiedShotOptions}
            shotFilter={filtersHook.shotFilter}
            onShotFilterChange={(shotId) => withPaginationReset(() => filtersHook.setShotFilter(shotId))}
            excludePositioned={filtersHook.excludePositioned}
            onExcludePositionedChange={(v) => withPaginationReset(() => filtersHook.setExcludePositioned(v))}
            showSearch={showSearch}
            isSearchOpen={filtersHook.isSearchOpen}
            searchTerm={filtersHook.searchTerm}
            searchInputRef={filtersHook.searchInputRef}
            toggleSearch={filtersHook.toggleSearch}
            clearSearch={filtersHook.clearSearch}
            handleSearchChange={(value) => withPaginationReset(() => filtersHook.setSearchTerm(value))}
            mediaTypeFilter={filtersHook.mediaTypeFilter}
            onMediaTypeFilterChange={(value) => withPaginationReset(() => filtersHook.setMediaTypeFilter(value))}
          />
        </div>
        {/* Shot Filter Notifier */}
        {!hideShotNotifier && (
          <ShotNotifier
            formAssociatedShotId={formAssociatedShotId}
            shotFilter={filtersHook.shotFilter}
            showShotFilter={showShotFilter}
            allShots={simplifiedShotOptions}
            onSwitchToAssociatedShot={handleSwitchToAssociatedShot}
            onShowAllShots={handleShowAllShots}
            onVisitShot={handleVisitShotFromNotifier}
          />
        )}
        {/* Main Gallery Grid */}
        <MediaGalleryGrid
          images={images}
          paginatedImages={paginatedImagesWithBadges}
          filteredImages={filtersHook.filteredImages}
          reducedSpacing={reducedSpacing}
          darkSurface={darkSurface}
          gridColumnClasses={gridColumnClasses}
          columnsPerRow={effectiveColumnsPerRow}
          projectAspectRatio={projectAspectRatio}
          isGalleryLoading={paginationHook.isGalleryLoading}
          isServerPagination={paginationHook.isServerPagination}
          clearNavigation={paginationHook.clearNavigation}
          effectivePage={effectivePage}
          isMobile={isMobile}
          isLightboxOpen={!!stateHook.state.activeLightboxMedia}
          enableAdjacentPagePreloading={enableAdjacentPagePreloading}
          page={paginationHook.page}
          serverPage={serverPage}
          totalFilteredItems={paginationHook.totalFilteredItems}
          itemsPerPage={actualItemsPerPage}
          selectedProjectId={selectedProjectId ?? undefined}
          generationFilters={generationFilters}
          hasFilters={hasFilters}
          isBackfillLoading={stateHook.state.isBackfillLoading}
          setIsBackfillLoading={stateHook.setIsBackfillLoading}
          totalCount={totalCount}
          offset={offset}
          optimisticDeletedCount={stateHook.state.optimisticDeletedIds.size}
          itemShotWorkflow={itemShotWorkflow}
          itemMobileInteraction={itemMobileInteraction}
          itemFeatures={itemFeatures}
          itemActions={itemActions}
          itemLoading={itemLoading}
          selectedIds={selectedIds}
          hideBottomPagination={hideBottomPagination}
        />
      </div>
      {/* Lightbox and Task Details */}
      <MediaGalleryLightbox session={lightboxSession} />
      {/* Mobile floating bottom bar with pagination and star filter - phones only, not iPad */}
      {isPhoneOnly && !hidePagination && !stateHook.state.activeLightboxMedia && paginationHook.totalPages > 1 && (
        <MobileBottomBar
          isServerPagination={paginationHook.isServerPagination}
          serverPage={serverPage}
          page={paginationHook.page}
          totalPages={paginationHook.totalPages}
          loadingButton={paginationHook.loadingButton}
          onPageChange={paginationHook.handlePageChange}
          hideTopFilters={hideTopFilters}
          showStarredOnly={filtersHook.showStarredOnly}
          onToggleStarred={() => withPaginationReset(() => filtersHook.setShowStarredOnly(!filtersHook.showStarredOnly))}
        />
      )}
    </TooltipProvider>
  );
});
MediaGallery.displayName = 'MediaGallery';
export { MediaGallery };
