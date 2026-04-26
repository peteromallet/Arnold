import React, { useCallback, useMemo } from "react";
import { Eye } from "lucide-react";
import { DraggableImage } from "@/shared/components/DraggableImage";
import { TimeStamp } from "@/shared/components/TimeStamp";
import type { Shot } from "@/domains/generation/types";
import type { MediaGalleryItemProps } from "./MediaGalleryItem/types";
import { VideoContent } from "./MediaGalleryItem/components/VideoContent";
import { ImageContent } from "./MediaGalleryItem/components/ImageContent";
import { ShotActions } from "./MediaGalleryItem/components/ShotActions";
import { ActionButtons } from "./MediaGalleryItem/components/ActionButtons";
import { ItemShotBadges } from "./MediaGalleryItem/components/ItemShotBadges";
import { ItemMetadataBar } from "./MediaGalleryItem/components/ItemMetadataBar";
import { useMediaGalleryItemShotActions } from "./MediaGalleryItem/hooks/useShotActions";
import { useImageLoading } from "./MediaGalleryItem/hooks/useImageLoading";
import { useMediaGalleryItemState } from "./MediaGalleryItem/hooks/useMediaGalleryItemState";
import { useStableMediaUrls } from "./MediaGalleryItem/hooks/useStableMediaUrls";
import { useShotPositionChecks } from "./MediaGalleryItem/hooks/useShotPositionChecks";
import { useItemInteraction } from "./MediaGalleryItem/hooks/useItemInteraction";
import {
  setGenerationDragData,
  setMultiGenerationDragData,
  createDragPreview,
  type GenerationDropData,
} from '@/shared/lib/dnd/dragDrop';
import type { GeneratedImageWithMetadata } from '@/shared/components/MediaGallery/types';
import { parseRatio } from '@/shared/lib/media/aspectRatios';
import { CreateShotModal } from "@/features/shots/components/CreateShotModal";
import { useProjectSelectionContext } from "@/shared/contexts/ProjectContext";
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { useShotNavigation } from "@/shared/hooks/shots/useShotNavigation";
import { useLastAffectedShot } from "@/shared/hooks/shots/useLastAffectedShot";
import { useQuickShotCreate } from "@/shared/hooks/useQuickShotCreate";
import { usePrefetchTaskData } from "@/shared/hooks/tasks/useTaskPrefetch";
import { useGenerationTaskMapping } from "@/domains/generation/hooks/tasks/useGenerationTaskMapping";
import { useTaskType } from "@/shared/hooks/tasks/useTaskType";
import { useGetTask } from "@/shared/hooks/tasks/useTasks";
import { useShareGeneration } from "@/shared/hooks/useShareGeneration";
import { deriveGalleryInputImages } from "./MediaGallery/utils";
import { isImageEditTaskType } from "@/shared/lib/taskParamsUtils";
import { useMarkVariantViewed } from "@/shared/hooks/variants/useMarkVariantViewed";
import { getGenerationId, getMediaUrl, getThumbnailUrl } from '@/shared/lib/media/mediaTypeHelpers';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import { isAdditiveSelectionEvent, isClickLikePointerGesture, isPrimaryPointer } from '@/shared/lib/interactions/selectionGesture';

const MIN_PADDING = 60;
const MAX_PADDING = 200;

function clampPadding(value: number): number {
  return Math.min(Math.max(value, MIN_PADDING), MAX_PADDING);
}

function extractResolutionFromMetadata(image: GeneratedImageWithMetadata): { width?: number; height?: number } {
  let width = image.metadata?.width;
  let height = image.metadata?.height;

  if (width && height) {
    return { width, height };
  }

  const resolution = image.metadata?.originalParams?.orchestrator_details?.resolution;
  if (resolution && typeof resolution === 'string' && resolution.includes('x')) {
    const [parsedWidth, parsedHeight] = resolution.split('x').map(Number);
    if (!isNaN(parsedWidth) && !isNaN(parsedHeight)) {
      width = parsedWidth;
      height = parsedHeight;
    }
  }

  return { width, height };
}

function resolveAspectRatioPadding(
  image: GeneratedImageWithMetadata,
  projectAspectRatio?: string,
): string {
  if (projectAspectRatio) {
    const ratio = parseRatio(projectAspectRatio);
    if (!isNaN(ratio)) {
      const calculatedPadding = (1 / ratio) * 100;
      return `${clampPadding(calculatedPadding)}%`;
    }
  }

  const { width, height } = extractResolutionFromMetadata(image);
  if (width && height) {
    return `${clampPadding((height / width) * 100)}%`;
  }

  return '100%';
}

function toGenerationDragData(image: GeneratedImageWithMetadata): GenerationDropData | null {
  const generationId = getGenerationId(image) ?? image.id;
  const imageUrl = getMediaUrl(image);
  if (!imageUrl) {
    return null;
  }
  const variantId = image.primary_variant_id
    ?? (typeof image.metadata?.variant_id === 'string' ? image.metadata.variant_id : undefined)
    ?? (image.generation_id ? image.id : undefined);

  return {
    generationId,
    variantId,
    variantType: image.type?.includes('video') || image.isVideo ? 'video' : 'image',
    imageUrl,
    thumbUrl: getThumbnailUrl(image),
    metadata: image.metadata,
  };
}
export const MediaGalleryItem: React.FC<MediaGalleryItemProps> = ({
  image,
  index,
  shotWorkflow,
  mobileInteraction,
  features,
  actions,
  loading,
  isSelected = false,
  selectedItems = [],
  projectAspectRatio,
  dataTour,
}) => {
  useRenderBudget('MediaGalleryItem', 5);
  const {
    selectedShotIdLocal,
    simplifiedShotOptions,
    setSelectedShotIdLocal,
    setLastAffectedShotId,
    showTickForImageId,
    onShowTick,
    onShowSecondaryTick,
    optimisticUnpositionedIds,
    optimisticPositionedIds,
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
  } = shotWorkflow;
  const {
    isMobile,
    mobileActiveImageId,
    mobilePopoverOpenImageId,
    onMobileTap,
  } = mobileInteraction;
  const {
    showShare = true,
    showDelete = true,
    showEdit = true,
    showStar = true,
    showAddToShot = true,
    enableSingleClick = false,
    videosAsThumbnails = false,
  } = features;
  const {
    onOpenLightbox,
    onDelete,
    onToggleStar,
    onImageClick,
    onContextMenu,
    onImageLoaded,
  } = actions;
  const {
    shouldLoad = true,
    isPriority = false,
    isDeleting,
  } = loading;
  const {
    localStarred,
    setLocalStarred,
    isTogglingStar,
    setIsTogglingStar,
    isInfoOpen,
    setIsInfoOpen,
    isShotSelectorOpen,
    setIsShotSelectorOpen,
    isDragging,
    setIsDragging,
    isCreateShotModalOpen,
    setIsCreateShotModalOpen,
    isCreatingShot,
    handleCreateShot,
  } = useMediaGalleryItemState({ image, onCreateShot });
  const prefetchTaskData = usePrefetchTaskData();
  const taskIdFromMetadata = image.metadata?.taskId as string | undefined;
  const actualGenerationId = getGenerationId(image);
  const generationIdForActions = actualGenerationId || image.id;
  const { selectedProjectId } = useProjectSelectionContext();
  const { data: taskIdMapping } = useGenerationTaskMapping(actualGenerationId ?? '');
  const taskIdFromCache = typeof taskIdMapping?.taskId === 'string' ? taskIdMapping.taskId : null;
  const taskId: string | null = taskIdFromMetadata || taskIdFromCache;
  const { data: taskData } = useGetTask(taskId ?? '', selectedProjectId ?? null);
  const handleMouseEnter = useCallback(() => {
    if (!isMobile && actualGenerationId) {
      prefetchTaskData(actualGenerationId);
    }
  }, [isMobile, actualGenerationId, prefetchTaskData]);
  const inputImages = useMemo(() => deriveGalleryInputImages(taskData), [taskData]);
  const taskType = taskData?.taskType;
  const { data: taskTypeInfo } = useTaskType(taskType || '');
  const isVideoTask = taskTypeInfo?.content_type === 'video' ||
    (!taskTypeInfo && image.metadata?.tool_type === TOOL_IDS.TRAVEL_BETWEEN_IMAGES);
  const isImageEditTask = isImageEditTaskType(taskType || undefined);
  const shouldShowTaskDetails = (!!taskData) && (isVideoTask || isImageEditTask);
  const { handleShare, isCreatingShare, shareCopied, shareSlug } = useShareGeneration(image.id, taskId);
  const { markAllViewed } = useMarkVariantViewed();
  const handleMarkAllVariantsViewed = useCallback(() => {
    if (actualGenerationId) {
      markAllViewed(actualGenerationId);
    }
  }, [actualGenerationId, markAllViewed]);
  const { navigateToShot } = useShotNavigation();
  const { setLastAffectedShotId: updateLastAffectedShotId } = useLastAffectedShot();
  const {
    quickCreateSuccess,
    handleQuickCreateAndAdd,
    handleVisitCreatedShot,
  } = useQuickShotCreate({
    generationId: generationIdForActions,
    generationPreview: {
      imageUrl: image.url,
      thumbUrl: image.thumbUrl,
      type: image.type,
      location: image.location,
    },
    shots: simplifiedShotOptions,
    onShotChange: (shotId) => {
      updateLastAffectedShotId(shotId);
      setSelectedShotIdLocal(shotId);
    },
    onLoadingStart: () => setAddingToShotImageId(image.id),
    onLoadingEnd: () => setAddingToShotImageId(null),
  });
  const {
    isVideoContent,
    displayUrl,
    stableDisplayUrl,
    stableVideoUrl,
    progressiveEnabled,
    isThumbShowing,
    isFullLoaded,
    progressiveRef,
  } = useStableMediaUrls({ image, isPriority });
  const {
    actualSrc,
    actualDisplayUrl,
    imageLoaded,
    imageLoadError,
    handleImageLoad,
    handleImageError,
    retryImageLoad,
    setImageLoading,
  } = useImageLoading({
    image,
    displayUrl,
    shouldLoad,
    onImageLoaded,
  });
  const { addToShot, addToShotWithoutPosition } = useMediaGalleryItemShotActions({
    imageId: image.id,
    generationId: generationIdForActions,
    imageUrl: image.url,
    thumbUrl: image.thumbUrl ?? image.url,
    displayUrl: displayUrl || image.url,
    selectedShotId: selectedShotIdLocal,
    isMobile,
    onAddToLastShot,
    onAddToLastShotWithoutPosition,
    onShowTick,
    onShowSecondaryTick,
    onOptimisticPositioned,
    onOptimisticUnpositioned,
    setAddingToShotImageId,
    setAddingToShotWithoutPositionImageId,
  });
  const shouldShowMetadata = useMemo(() => {
    if (!image.metadata) return false;
    return isMobile
      ? (mobilePopoverOpenImageId === image.id)
      : isInfoOpen;
  }, [image.metadata, isMobile, mobilePopoverOpenImageId, image.id, isInfoOpen]);
  const isCurrentDeleting = isDeleting === true || isDeleting === image.id;
  const imageKey = image.id || `image-${actualDisplayUrl}-${index}`;
  const isPlaceholder = !image.id && actualDisplayUrl === "/placeholder.svg";
  const currentTargetShotName = selectedShotIdLocal ? simplifiedShotOptions.find(s => s.id === selectedShotIdLocal)?.name : undefined;
  const handleDragStart = useCallback((e: React.DragEvent) => {
    if (isMobile) {
      e.preventDefault();
      return;
    }
    const selectedDragItems = isSelected && selectedItems.some((item) => item.id === image.id)
      ? selectedItems
      : [];
    const selectedDragPayloads = selectedDragItems
      .map(toGenerationDragData)
      .filter((payload): payload is GenerationDropData => payload !== null);
    const singleDragPayload = toGenerationDragData(image);

    if (selectedDragItems.length > 1 && selectedDragPayloads.length === 0) {
      e.preventDefault();
      return;
    }

    if (selectedDragItems.length <= 1 && !singleDragPayload) {
      e.preventDefault();
      return;
    }

    setIsDragging(true);
    if (selectedDragPayloads.length > 1) {
      setMultiGenerationDragData(e, selectedDragPayloads);
    } else {
      setGenerationDragData(e, selectedDragPayloads[0] ?? singleDragPayload!);
    }

    const cleanup = createDragPreview(
      e,
      selectedDragPayloads.length > 1 ? { badgeText: String(selectedDragPayloads.length) } : undefined,
    );
    if (cleanup) {
      setTimeout(cleanup, 0);
    }
  }, [image, isMobile, isSelected, selectedItems, setIsDragging]);
  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
  }, [setIsDragging]);
  // Wrapper-level click detection for desktop. The native click on the inner
  // <img> is intermittently swallowed by the wrapper's HTML5 `draggable=true`
  // (any sub-pixel-or-two mousemove between mousedown and mouseup makes the
  // browser fire dragstart instead of click). We track pointerdown position and
  // treat sub-threshold pointerup gestures as clicks ourselves, regardless of
  // whether the browser would have synthesised a click. Real drags skip the
  // click and let the drag pipeline run.
  const pointerDownRef = React.useRef<{ x: number; y: number; pointerId: number; targetIsButton: boolean } | null>(null);

  const handleWrapperPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'mouse') return;
    if (!isPrimaryPointer(event.nativeEvent)) return;
    if (isMobile) return;
    const target = event.target as HTMLElement | null;
    const targetIsButton = Boolean(target?.closest('button'));
    pointerDownRef.current = {
      x: event.clientX,
      y: event.clientY,
      pointerId: event.pointerId,
      targetIsButton,
    };
  }, [isMobile]);

  const handleWrapperPointerUp = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const start = pointerDownRef.current;
    pointerDownRef.current = null;
    if (!start || start.pointerId !== event.pointerId) return;
    if (start.targetIsButton) return; // Don't hijack clicks on internal action buttons.
    if (!enableSingleClick || !onImageClick) return;
    if (!isClickLikePointerGesture(start, { x: event.clientX, y: event.clientY })) return;
    onImageClick(image, {
      multiSelect: isAdditiveSelectionEvent(event),
    });
  }, [enableSingleClick, onImageClick, image]);

  const { handleTouchStart, handleInteraction } = useItemInteraction({
    image,
    isMobile,
    mobileActiveImageId,
    enableSingleClick,
    onImageClick,
    onMobileTap,
  });
  const {
    isAlreadyPositionedInSelectedShot,
    isAlreadyAssociatedWithoutPosition,
    shouldShowAddWithoutPositionButton,
  } = useShotPositionChecks({
    image,
    selectedShotIdLocal,
    currentViewingShotId,
    optimisticPositionedIds,
    optimisticUnpositionedIds,
    onAddToLastShotWithoutPosition,
    showTickForImageId,
    addingToShotImageId,
  });
  const aspectRatioPadding = resolveAspectRatioPadding(image, projectAspectRatio);
  const minHeight = '120px'; // Minimum height for very small images
  if (isPlaceholder) {
    return (
      <div
        key={imageKey}
        className="border rounded-lg overflow-hidden bg-muted animate-pulse"
      >
        <div style={{ paddingBottom: aspectRatioPadding }} className="relative">
          <div className="absolute inset-0 flex items-center justify-center">
            <Eye className="h-12 w-12 text-muted-foreground opacity-30" />
          </div>
        </div>
      </div>
    );
  }
  const imageContent = (
    <div
        data-gallery-item-id={image.id}
        className={`border rounded-lg overflow-hidden hover:shadow-md transition-[opacity,transform] duration-200 relative group bg-card ${
          isSelected ? 'outline outline-2 outline-sky-400 -outline-offset-2 ' : ''
        }${
          isDragging ? 'opacity-50 scale-75' : ''
        } ${!isMobile ? 'cursor-grab active:cursor-grabbing' : ''}`}
        draggable={!isMobile}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onMouseEnter={handleMouseEnter}
        data-tour={dataTour}
        onContextMenu={(event) => onContextMenu?.(event, image)}
        onTouchStart={isMobile && !enableSingleClick && !isVideoContent ? handleTouchStart : undefined}
        onTouchEnd={isMobile && !enableSingleClick && !isVideoContent ? handleInteraction : undefined}
        onPointerDown={handleWrapperPointerDown}
        onPointerUp={handleWrapperPointerUp}
    >
      {/* Image layer */}
      <div
        style={{
          paddingBottom: aspectRatioPadding,
          minHeight: minHeight
        }}
        className="relative bg-muted/50"
      >
          {isVideoContent ? (
            <VideoContent
              image={image}
              stableDisplayUrl={stableDisplayUrl}
              stableVideoUrl={stableVideoUrl}
              actualSrc={actualSrc}
              shouldLoad={shouldLoad}
              imageLoaded={imageLoaded}
              videosAsThumbnails={videosAsThumbnails}
              isMobile={isMobile}
              enableSingleClick={enableSingleClick}
              onImageClick={onImageClick}
              onOpenLightbox={onOpenLightbox}
              onTouchStart={handleTouchStart}
              onTouchEnd={handleInteraction}
              onVideoError={handleImageError}
              onLoadStart={() => setImageLoading(true)}
              onLoadedData={handleImageLoad}
            />
          ) : (
            <ImageContent
              image={image}
              index={index}
              actualSrc={actualSrc}
              imageLoaded={imageLoaded}
              imageLoadError={imageLoadError}
              progressiveEnabled={progressiveEnabled}
              isThumbShowing={isThumbShowing}
              isFullLoaded={isFullLoaded}
              progressiveRef={progressiveRef}
              isMobile={isMobile}
              enableSingleClick={enableSingleClick}
              onImageClick={onImageClick}
              onOpenLightbox={onOpenLightbox}
              onImageLoad={handleImageLoad}
              onImageError={handleImageError}
              onRetry={retryImageLoad}
              setImageLoading={setImageLoading}
            />
          )}
      </div>
      {/* Overlay layer — single container above the image for all UI controls */}
      {image.id && (
      <div className="absolute inset-0 z-10 pointer-events-none [&>*]:pointer-events-auto">
          <ItemShotBadges
            image={image}
            isVideoContent={isVideoContent}
            simplifiedShotOptions={simplifiedShotOptions}
            onMarkAllVariantsViewed={handleMarkAllVariantsViewed}
            onNavigateToShot={(shotId) => {
              const targetShot = simplifiedShotOptions.find((shot) => shot.id === shotId);
              if (targetShot) {
                navigateToShot(targetShot as Shot, { scrollToTop: true });
              }
            }}
          />
          {/* Add to Shot UI - Top Left (for non-video content) */}
          {showAddToShot && simplifiedShotOptions.length > 0 && onAddToLastShot && (
            <ShotActions
              image={image}
              selector={{
                selectedShotId: selectedShotIdLocal,
                simplifiedShotOptions,
                isShotSelectorOpen,
                setIsShotSelectorOpen,
                setSelectedShotIdLocal,
                setLastAffectedShotId,
              }}
              status={{
                isMobile,
                isVideoContent,
                addingToShotImageId,
                addingToShotWithoutPositionImageId: addingToShotWithoutPositionImageId ?? null,
                showTickForImageId,
                isAlreadyPositionedInSelectedShot,
                isAlreadyAssociatedWithoutPosition,
                shouldShowAddWithoutPositionButton,
                currentTargetShotName,
              }}
              quickCreate={{
                quickCreateSuccess,
                handleQuickCreateAndAdd,
                handleVisitCreatedShot,
              }}
              actions={{
                onCreateShot,
                onNavigateToShot: (shot) => navigateToShot(shot, { scrollToTop: true }),
                onAddToShot: addToShot,
                onAddToShotWithoutPosition: addToShotWithoutPosition,
              }}
            />
          )}
          {/* Timestamp - Top Right (hides on hover for images, stays visible for videos) */}
          <TimeStamp
            createdAt={image.createdAt}
            position="top-right"
            showOnHover={false}
            hideOnHover={!isVideoContent}
            className=""
          />
          <ItemMetadataBar
            image={image}
            isVideoContent={isVideoContent}
            isMobile={isMobile}
            taskData={taskData}
            inputImages={inputImages}
            shouldShowMetadata={shouldShowMetadata}
            shouldShowTaskDetails={shouldShowTaskDetails}
            setIsInfoOpen={setIsInfoOpen}
            showShare={showShare}
            taskId={taskId}
            handleShare={handleShare}
            isCreatingShare={isCreatingShare}
            shareCopied={shareCopied}
            shareSlug={shareSlug}
            onMarkAllVariantsViewed={handleMarkAllVariantsViewed}
          />
          <ActionButtons
            image={image}
            localStarred={localStarred}
            isTogglingStar={isTogglingStar}
            isDeleting={isCurrentDeleting}
            showStar={showStar}
            showEdit={showEdit}
            showDelete={showDelete}
            onToggleStar={onToggleStar}
            setIsTogglingStar={setIsTogglingStar}
            setLocalStarred={setLocalStarred}
            onOpenLightbox={onOpenLightbox}
            onDelete={onDelete}
          />
      </div>)
      }
    </div>
  );
  return isMobile ? (
    <React.Fragment key={imageKey}>
      {imageContent}
      {onCreateShot && (
        <CreateShotModal
          isOpen={isCreateShotModalOpen}
          onClose={() => setIsCreateShotModalOpen(false)}
          onSubmit={handleCreateShot}
          isLoading={isCreatingShot}
          projectId={selectedProjectId ?? undefined}
        />
      )}
    </React.Fragment>
  ) : (
    <DraggableImage key={`draggable-${imageKey}`} image={image} onDoubleClick={() => onOpenLightbox(image)}>
      {imageContent}
      {onCreateShot && (
        <CreateShotModal
          isOpen={isCreateShotModalOpen}
          onClose={() => setIsCreateShotModalOpen(false)}
          onSubmit={handleCreateShot}
          isLoading={isCreatingShot}
          projectId={selectedProjectId ?? undefined}
        />
      )}
    </DraggableImage>
  );
};
