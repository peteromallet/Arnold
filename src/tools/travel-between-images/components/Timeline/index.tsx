/**
 * Timeline - orchestrates timeline hooks and renders TimelineContainer + MediaLightbox.
 * Modular sub-components live in ./Timeline/hooks/, ./Timeline/utils/, ./Timeline/ (components).
 */

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useAppEventListener } from "@/shared/lib/typedEvents";
import { GenerationRow } from "@/domains/generation/types";
import { toast } from "@/shared/components/ui/runtime/sonner";
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { MediaLightbox, type MediaLightboxProps } from "@/domains/media-lightbox/MediaLightbox";
import type { LightboxActionHandlers } from '@/domains/media-lightbox/types';
import { TimelineEmptyState } from "./TimelineEmptyState";
import type { SegmentSlot } from "@/shared/hooks/segments";


import { useTimelineDomainService } from "./hooks/timeline-core/useTimelineDomainService";
import { quantizeGap } from '@/shared/lib/media/videoUtils';
import { useTimelineLightboxOrchestrator } from "./hooks/useTimelineLightboxOrchestrator";

import { TimelineContainer } from "./TimelineContainer/TimelineContainer";
import { useEmptyStateDrop } from "./hooks/drag/useEmptyStateDrop";
import type { VariantDropParams } from '@/shared/hooks/dnd/useImageVariantDrop';

interface TimelineCoreAdapter {
  shotId: string;
  projectId?: string;
  frameSpacing: number;
  readOnly?: boolean;
  shotGenerations?: GenerationRow[];
  images?: GenerationRow[];
  allGenerations?: GenerationRow[];
}

interface TimelineInteractionAdapter {
  onImageReorder: (orderedIds: string[], draggedItemId?: string) => void;
  onFramePositionsChange?: (framePositions: Map<string, number>) => void;
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  onGenerationDrop?: (generationId: string, imageUrl: string, thumbUrl: string | undefined, targetFrame?: number) => Promise<void>;
  onVariantDrop?: (params: VariantDropParams) => Promise<void>;
  onImageDelete: NonNullable<LightboxActionHandlers['onDelete']>;
  onImageDuplicate?: (imageId: string, timelineFrame: number, nextTimelineFrame?: number) => void;
  duplicatingImageId?: string | null;
  duplicateSuccessImageId?: string | null;
  onPairClick?: (pairIndex: number) => void;
  onClearEnhancedPrompt?: (pairIndex: number) => void;
  onDragStateChange?: (isDragging: boolean) => void;
  onNewShotFromSelection?: (selectedIds: string[]) => Promise<string | void>;
  onSegmentFrameCountChange?: (pairShotGenerationId: string, frameCount: number) => void;
  onRegisterTrailingUpdater?: (fn: (endFrame: number) => void) => void;
}

interface TimelineDisplayAdapter {
  defaultPrompt?: string;
  defaultNegativePrompt?: string;
  projectAspectRatio?: string;
  maxFrameLimit?: number;
  selectedOutputId?: string | null;
}

interface TimelineUploadAdapter {
  onImageUpload?: (files: File[]) => Promise<void>;
  isUploadingImage?: boolean;
  uploadProgress?: number;
}

interface TimelineShotWorkflowAdapter {
  allShots?: Array<{ id: string; name: string }>;
  selectedShotId?: string;
  onShotChange?: (shotId: string) => void;
  onAddToShot?: (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string) => Promise<boolean>;
  onAddToShotWithoutPosition?: (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string) => Promise<boolean>;
  onCreateShot?: (shotName: string, files: File[]) => Promise<{ shotId?: string; shotName?: string } | void>;
}

interface TimelineSegmentNavigationAdapter {
  segmentSlots?: SegmentSlot[];
  isSegmentsLoading?: boolean;
  hasPendingTask?: (pairShotGenerationId: string | null | undefined) => boolean;
  onOpenSegmentSlot?: (pairIndex: number) => void;
  pendingImageToOpen?: string | null;
  pendingImageVariantId?: string | null;
  onClearPendingImageToOpen?: () => void;
  navigateWithTransition?: (doNavigation: () => void) => void;
}

interface TimelineProps {
  core: TimelineCoreAdapter;
  interactions: TimelineInteractionAdapter;
  display?: TimelineDisplayAdapter;
  uploads?: TimelineUploadAdapter;
  shotWorkflow?: TimelineShotWorkflowAdapter;
  segmentNavigation?: TimelineSegmentNavigationAdapter;
}

const Timeline: React.FC<TimelineProps> = ({
  core,
  interactions,
  display,
  uploads,
  shotWorkflow,
  segmentNavigation,
}) => {
  const {
    shotId,
    projectId,
    frameSpacing,
    readOnly = false,
    shotGenerations: propShotGenerations,
    images: propImages,
    allGenerations: propAllGenerations,
  } = core;
  const {
    onImageReorder,
    onFramePositionsChange,
    onFileDrop,
    onGenerationDrop,
    onVariantDrop,
    onImageDelete,
    onImageDuplicate,
    duplicatingImageId,
    duplicateSuccessImageId,
    onPairClick,
    onClearEnhancedPrompt,
    onDragStateChange,
    onNewShotFromSelection,
    onSegmentFrameCountChange,
    onRegisterTrailingUpdater,
  } = interactions;
  const {
    defaultPrompt,
    defaultNegativePrompt,
    projectAspectRatio,
    maxFrameLimit = 81,
    selectedOutputId,
  } = display ?? {};
  const {
    onImageUpload,
    isUploadingImage,
    uploadProgress = 0,
  } = uploads ?? {};
  const {
    allShots,
    selectedShotId,
    onShotChange,
    onAddToShot,
    onAddToShotWithoutPosition,
    onCreateShot,
  } = shotWorkflow ?? {};
  const {
    segmentSlots,
    isSegmentsLoading,
    hasPendingTask,
    onOpenSegmentSlot,
    pendingImageToOpen,
    pendingImageVariantId,
    onClearPendingImageToOpen,
    navigateWithTransition,
  } = segmentNavigation ?? {};

  const [isDragInProgress, setIsDragInProgress] = useState<boolean>(false);

  // Notify parent when drag state changes - used to suppress query refetches
  useEffect(() => {
    onDragStateChange?.(isDragInProgress);
  }, [isDragInProgress, onDragStateChange]);

  // Keep data/query orchestration out of the view layer.
  const {
    images,
    readOnlyGenerations,
    positions,
    updatePositions,
    actualPairPrompts,
    loadPositions,
  } = useTimelineDomainService({
    shotId,
    projectId,
    frameSpacing,
    isDragInProgress,
    onFramePositionsChange,
    propShotGenerations,
    propImages,
    propAllGenerations,
    readOnly,
  });

  const {
    lightbox,
    media,
    external,
    shotSelection,
    taskDetails,
  } = useTimelineLightboxOrchestrator({
    shotId,
    projectId,
    images,
    selectedShotId,
    onAddToShot,
    onAddToShotWithoutPosition,
    segmentSlots,
    onOpenSegmentSlot,
    pendingImageToOpen,
    pendingImageVariantId,
    onClearPendingImageToOpen,
    navigateWithTransition,
  });

  // Listen for star updates and refetch shot data
  useAppEventListener('generation-star-updated', useCallback(({ shotId: updatedShotId }) => {
    // Only refetch if this event is for our current shot
    if (updatedShotId === shotId) {
      loadPositions?.({ silent: true, reason: 'shot_change' });
    }
  }, [shotId, loadPositions]));

  // Handle resetting frames to evenly spaced intervals
  // Gap values are quantized to 4N+1 format for Wan model compatibility
  const handleResetFrames = useCallback(async (gap: number) => {
    // Quantize the gap to 4N+1 format (5, 9, 13, 17, 21, 25, 29, 33, ...)
    const quantizedGap = quantizeGap(gap, 5);
    
    // Then set the positions with the specified quantized gap
    const newPositions = new Map<string, number>();
    images.forEach((image, index) => {
      // Use id (shot_generations.id) for position mapping - unique per entry
      // First image at 0, subsequent images at quantized intervals
      newPositions.set(image.id, index * quantizedGap);
    });

    await updatePositions(newPositions);
  }, [images, updatePositions]);

  // Check if timeline is empty
  const hasNoImages = images.length === 0;

  // Empty-state drag and drop (supports both files and internal generations)
  const {
    isDragOver,
    dragType,
    handleEmptyStateDragEnter,
    handleEmptyStateDragOver,
    handleEmptyStateDragLeave,
    handleEmptyStateDrop,
  } = useEmptyStateDrop({
    onFileDrop,
    onGenerationDrop,
    onImageUpload,
  });

  // The orchestrator return objects are stable enough for this memoized view model;
  // exhaustive-deps over-reports on the nested controller references here.
  /* eslint-disable react-hooks/exhaustive-deps */
  const timelineLightboxProps = useMemo<MediaLightboxProps | null>(() => {
    if (!shotSelection.lightboxShotState || !media.currentLightboxImage) {
      return null;
    }

    const selectedLightboxShotId = shotSelection.lightboxShotState.isExternalGen
      ? external.externalGenLightboxSelectedShot
      : shotSelection.lightboxSelectedShotId;

    return {
      media: media.currentLightboxImage,
      shotId,
      onClose: () => {
        lightbox.capturedVariantIdRef.current = null;
        lightbox.closeLightbox();
        shotSelection.setLightboxSelectedShotId(selectedShotId || shotId);
      },
      readOnly,
      toolTypeOverride: TOOL_IDS.TRAVEL_BETWEEN_IMAGES,
      initialVariantId: lightbox.capturedVariantIdRef.current ?? undefined,
      adjacentSegments: !shotSelection.lightboxShotState.isExternalGen
        ? shotSelection.adjacentSegmentsData
        : undefined,
      navigation: {
        onNext: images.length > 1 ? lightbox.goNext : undefined,
        onPrevious: images.length > 1 ? lightbox.goPrev : undefined,
        showNavigation: lightbox.showNavigation,
        hasNext: lightbox.hasNext,
        hasPrevious: lightbox.hasPrevious,
      },
      onNavigateToGeneration: (generationId: string) => {
        const index = media.currentImages.findIndex((img) => img.id === generationId);
        if (index !== -1) {
          lightbox.openLightbox(index);
        } else {
          toast.info('This generation is not currently loaded');
        }
      },
      onOpenExternalGeneration: external.handleOpenExternalGeneration,
      shotWorkflow: {
        allShots,
        selectedShotId: selectedLightboxShotId,
        onShotChange: shotSelection.lightboxShotState.isExternalGen
          ? (shotId) => {
              external.setExternalGenLightboxSelectedShot(shotId);
            }
          : (shotId) => {
              shotSelection.setLightboxSelectedShotId(shotId);
              onShotChange?.(shotId);
            },
        onAddToShot: shotSelection.lightboxShotState.isExternalGen
          ? external.handleExternalGenAddToShot
          : shotSelection.addToShot,
        onAddToShotWithoutPosition: shotSelection.lightboxShotState.isExternalGen
          ? external.handleExternalGenAddToShotWithoutPosition
          : shotSelection.addToShotWithoutPosition,
        onCreateShot,
        positionedInSelectedShot: shotSelection.lightboxShotState.positionedInSelectedShot,
        associatedWithoutPositionInSelectedShot: shotSelection.lightboxShotState.associatedWithoutPositionInSelectedShot,
      },
      actions: {
        onDelete: !readOnly
          ? (mediaId: string) => onImageDelete(mediaId)
          : undefined,
        starred: media.currentLightboxImage.starred ?? false,
      },
      features: {
        showTaskDetails: true,
        showMagicEdit: true,
        showDownload: true,
        initialEditActive: lightbox.initialEditActive,
      },
      taskDetailsData: {
        task: taskDetails.task ?? null,
        isLoading: taskDetails.isLoadingTask,
        status: taskDetails.taskError ? 'error' : taskDetails.task ? 'ok' : 'missing',
        error: taskDetails.taskError,
        inputImages: taskDetails.inputImages,
        taskId: taskDetails.task?.id || null,
        onClose: lightbox.closeLightbox,
      },
    };
  }, [
    allShots,
    external.externalGenLightboxSelectedShot,
    external.handleExternalGenAddToShot,
    external.handleExternalGenAddToShotWithoutPosition,
    external.handleOpenExternalGeneration,
    external.setExternalGenLightboxSelectedShot,
    images.length,
    lightbox.initialEditActive,
    lightbox.capturedVariantIdRef,
    lightbox.closeLightbox,
    lightbox.goNext,
    lightbox.goPrev,
    lightbox.hasNext,
    lightbox.hasPrevious,
    lightbox.openLightbox,
    lightbox.showNavigation,
    media.currentImages,
    media.currentLightboxImage,
    onCreateShot,
    onImageDelete,
    onShotChange,
    readOnly,
    selectedShotId,
    shotId,
    shotSelection.addToShot,
    shotSelection.addToShotWithoutPosition,
    shotSelection.adjacentSegmentsData,
    shotSelection.lightboxSelectedShotId,
    shotSelection.lightboxShotState,
    shotSelection.setLightboxSelectedShotId,
    taskDetails.inputImages,
    taskDetails.isLoadingTask,
    taskDetails.task,
    taskDetails.taskError,
  ]);
  /* eslint-enable react-hooks/exhaustive-deps */

  return (
    <div className="w-full overflow-x-hidden relative" data-tour="timeline">
      {/* Blur and overlay when no images */}
      {hasNoImages && (
        <TimelineEmptyState
          isDragOver={isDragOver}
          dragType={dragType}
          shotId={shotId}
          onImageUpload={onImageUpload}
          isUploadingImage={isUploadingImage}
          onDragEnter={handleEmptyStateDragEnter}
          onDragOver={handleEmptyStateDragOver}
          onDragLeave={handleEmptyStateDragLeave}
          onDrop={handleEmptyStateDrop}
          hasDropHandler={!!(onFileDrop || onGenerationDrop)}
        />
      )}
      
      {/* Timeline Container - includes both controls and timeline */}
      <TimelineContainer
        shotId={shotId}
        projectId={projectId}
        images={images}
        framePositions={positions}
        onResetFrames={handleResetFrames}
        setFramePositions={updatePositions}
        onImageReorder={onImageReorder}
        onFileDrop={onFileDrop}
        onGenerationDrop={onGenerationDrop}
        onVariantDrop={onVariantDrop}
        setIsDragInProgress={setIsDragInProgress}
        onPairClick={onPairClick}
        pairPrompts={actualPairPrompts}
        defaultPrompt={defaultPrompt}
        defaultNegativePrompt={defaultNegativePrompt}
        onClearEnhancedPrompt={readOnly ? undefined : onClearEnhancedPrompt}
        onImageDelete={onImageDelete}
        onImageDuplicate={onImageDuplicate || (() => {})}
        duplicatingImageId={duplicatingImageId}
        duplicateSuccessImageId={duplicateSuccessImageId}
        projectAspectRatio={projectAspectRatio}
        handleDesktopDoubleClick={lightbox.handleDesktopDoubleClick}
        handleMobileTap={lightbox.handleMobileTap}
        handleInpaintClick={lightbox.openLightboxWithInpaint}
        hasNoImages={hasNoImages}
        readOnly={readOnly}
        isUploadingImage={isUploadingImage}
        uploadProgress={uploadProgress}
        maxFrameLimit={maxFrameLimit}
        selectedOutputId={selectedOutputId}
        onSegmentFrameCountChange={onSegmentFrameCountChange}
        segmentSlots={segmentSlots}
        isSegmentsLoading={isSegmentsLoading}
        hasPendingTask={hasPendingTask}
        videoOutputs={readOnlyGenerations}
        onNewShotFromSelection={onNewShotFromSelection}
        onShotChange={onShotChange}
        onRegisterTrailingUpdater={onRegisterTrailingUpdater}
      />

      {/* Lightbox */}
      {timelineLightboxProps && (
        <MediaLightbox {...timelineLightboxProps} />
      )}
    </div>
  );
};

const MemoizedTimeline = React.memo(Timeline);

export { MemoizedTimeline as Timeline };
