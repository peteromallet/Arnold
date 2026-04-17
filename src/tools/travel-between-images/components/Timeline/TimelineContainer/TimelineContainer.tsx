import React, { useCallback, useLayoutEffect, useMemo, useState } from 'react';

import {
  TRAILING_ENDPOINT_KEY,
  PENDING_POSITION_KEY,
  findTrailingVideoInfo,
  getPairInfo,
  sortPositionEntries,
} from '../utils/timeline-utils';
import { ResourceBrowserModalBase } from '@/features/resources/components/ResourceBrowserModalBase';
import { SelectionActionBar } from '@/shared/components/ShotImageManager/components/SelectionActionBar';

import { TimelineControls } from './components/TimelineControls';
import { TimelineTrackContent } from './components/TimelineTrackContent';

import { useTimelineOrchestrator } from '../hooks/timeline-core/useTimelineOrchestrator';
import { useTrailingEndpoint } from '../hooks/segment/useTrailingEndpoint';

import type { TimelineContainerProps } from './types';
import { useTimelineAudioMedia, useTimelineGuidanceMedia } from '../TimelineMediaContext';

const TimelineContainer: React.FC<TimelineContainerProps> = ({
  shotId,
  projectId,
  images,
  isUploadingImage = false,
  uploadProgress = 0,
  framePositions,
  setFramePositions,
  onImageReorder,
  onFileDrop,
  onGenerationDrop,
  setIsDragInProgress,
  onResetFrames,
  onPairClick,
  pairPrompts,
  defaultPrompt,
  defaultNegativePrompt,
  onClearEnhancedPrompt,
  onImageDelete,
  onImageDuplicate,
  onVariantDrop,
  readOnly = false,
  duplicatingImageId,
  duplicateSuccessImageId,
  projectAspectRatio,
  handleDesktopDoubleClick,
  handleMobileTap,
  handleInpaintClick,
  hasNoImages = false,
  maxFrameLimit = 81,
  selectedOutputId,
  onSegmentFrameCountChange,
  segmentSlots: parentSegmentSlots,
  isSegmentsLoading,
  hasPendingTask: parentHasPendingTask,
  videoOutputs,
  onNewShotFromSelection,
  onShotChange,
  onRegisterTrailingUpdater,
}) => {
  const {
    primaryStructureVideo,
    onPrimaryStructureVideoInputChange,
    structureVideos,
    isStructureVideoLoading,
    cachedHasStructureVideo,
    onAddStructureVideo,
    onUpdateStructureVideo,
    onRemoveStructureVideo,
  } = useTimelineGuidanceMedia();
  const { audioUrl, audioMetadata, onAudioChange } = useTimelineAudioMedia();

  const trailingEndFrame = framePositions.get(TRAILING_ENDPOINT_KEY);

  const handleTrailingEndFrameChange = useCallback((endFrame: number | undefined) => {
    const next = new Map(framePositions);
    if (endFrame === undefined) {
      next.delete(TRAILING_ENDPOINT_KEY);
    } else {
      next.set(TRAILING_ENDPOINT_KEY, endFrame);
    }
    setFramePositions(next);
  }, [framePositions, setFramePositions]);

  useLayoutEffect(() => {
    onRegisterTrailingUpdater?.(handleTrailingEndFrameChange);
  }, [onRegisterTrailingUpdater, handleTrailingEndFrameChange]);

  const { hasTrailing: hasExistingTrailingVideo, videoUrl: computedTrailingVideoUrl } = useMemo(() => {
    if (!videoOutputs || videoOutputs.length === 0 || images.length === 0) {
      return { hasTrailing: false, videoUrl: null };
    }

    const sortedEntries = [...framePositions.entries()]
      .filter(([id]) => id !== TRAILING_ENDPOINT_KEY)
      .sort((a, b) => a[1] - b[1]);
    const lastImageShotGenId = sortedEntries[sortedEntries.length - 1]?.[0] || null;
    return findTrailingVideoInfo(videoOutputs as Array<{
      type?: string | null;
      location?: string | null;
      pair_shot_generation_id?: string | null;
      params?: Record<string, unknown> | null;
    }>, lastImageShotGenId);
  }, [videoOutputs, framePositions, images.length]);

  const [callbackTrailingVideoUrl, setCallbackTrailingVideoUrl] = useState<string | null>(null);
  const hasCallbackTrailingVideo = hasExistingTrailingVideo || !!callbackTrailingVideoUrl;

  const anyImageHasVideo = useMemo(() => {
    if (parentSegmentSlots?.length) {
      return parentSegmentSlots.some((slot) => (
        slot.type === 'child'
        && slot.child.type?.includes('video')
        && slot.child.location
      ));
    }
    return false;
  }, [parentSegmentSlots]);

  const orchestrator = useTimelineOrchestrator({
    shotId,
    images,
    framePositions,
    setFramePositions,
    onImageReorder,
    onFileDrop,
    onGenerationDrop,
    setIsDragInProgress,
    onImageDuplicate,
    readOnly,
    isUploadingImage,
    maxFrameLimit,
    structureVideo: {
      structureVideos,
      primaryStructureVideo,
      onAddStructureVideo,
      onUpdateStructureVideo,
      onPrimaryStructureVideoInputChange,
    },
    hasExistingTrailingVideo: hasCallbackTrailingVideo || anyImageHasVideo,
  });

  const { timelineRef, containerRef } = orchestrator.refs;
  const {
    fullMin,
    fullMax,
    fullRange,
    containerWidth,
    zoomLevel,
    handleZoomInToCenter,
    handleZoomOutFromCenter,
    handleZoomReset,
    handleZoomToStart,
    handleTimelineDoubleClick,
  } = orchestrator.viewport;
  const {
    state: dragState,
    dragOffset,
    currentDragFrame,
    swapTargetId,
    pushMode,
    handleMouseDown,
  } = orchestrator.drag;
  const { selectedIds, showSelectionBar, isSelected, toggleSelection, clearSelection } = orchestrator.selection;
  const {
    pendingDropFrame,
    pendingDuplicateFrame,
    pendingExternalAddFrame,
    activePendingFrame,
    isInternalDropProcessing,
  } = orchestrator.pending;
  const {
    isFileOver,
    dropTargetFrame,
    dragType,
    handleDragEnter,
    handleDragOver,
    handleDragLeave,
    handleDrop,
  } = orchestrator.drop;
  const {
    currentPositions,
    pairInfo,
    pairDataByIndex,
    localShotGenPositions,
    showPairLabels,
  } = orchestrator.computed;
  const {
    handleDuplicateInterceptor,
    handleTimelineTapToMove,
    handleVideoBrowserSelect,
    handleEndpointMouseDown,
  } = orchestrator.actions;
  const { endpointDragFrame, isEndpointDragging: isEndpointDraggingState } = orchestrator.endpoint;
  const {
    resetGap,
    setResetGap,
    maxGap,
    showVideoBrowser,
    setShowVideoBrowser,
    isUploadingStructureVideo,
    setIsUploadingStructureVideo,
  } = orchestrator.uiState;
  const { isMobile, isTablet, enableTapToMove, prefetchTaskData } = orchestrator.device;

  const {
    trailingVideoUrl,
    handleExtractFinalFrame,
    imagePositions,
  } = useTrailingEndpoint({
    currentPositions,
    trailingEndFrame,
    computedTrailingVideoUrl,
    callbackTrailingVideoUrl,
    setCallbackTrailingVideoUrl,
    onFileDrop,
  });

  const liveLastImageShotGenId = useMemo(() => {
    const sorted = sortPositionEntries(imagePositions);
    return sorted[sorted.length - 1]?.[0] ?? null;
  }, [imagePositions]);

  const hasLiveTrailingVideo = useMemo(() => {
    if (!liveLastImageShotGenId) {
      return false;
    }

    if (parentSegmentSlots?.length) {
      return parentSegmentSlots.some((slot) => (
        slot.type === 'child'
        && slot.pairShotGenerationId === liveLastImageShotGenId
        && slot.child.type?.includes('video')
        && slot.child.location
      ));
    }

    if (videoOutputs) {
      return findTrailingVideoInfo(videoOutputs as Array<{
        type?: string | null;
        location?: string | null;
        pair_shot_generation_id?: string | null;
        params?: Record<string, unknown> | null;
      }>, liveLastImageShotGenId).hasTrailing;
    }

    return false;
  }, [liveLastImageShotGenId, parentSegmentSlots, videoOutputs]);

  const imagePositionsWithPending = useMemo(() => {
    if (activePendingFrame === null) {
      return imagePositions;
    }
    const realItemAtFrame = [...imagePositions.values()].some((pos) => pos === activePendingFrame);
    if (realItemAtFrame) {
      return imagePositions;
    }
    const augmented = new Map(imagePositions);
    augmented.set(PENDING_POSITION_KEY, activePendingFrame);
    return augmented;
  }, [imagePositions, activePendingFrame]);

  const pairInfoWithPending = useMemo(() => {
    if (activePendingFrame === null) {
      return pairInfo;
    }
    return getPairInfo(imagePositionsWithPending);
  }, [pairInfo, activePendingFrame, imagePositionsWithPending]);

  const handleOpenPairSettings = useCallback((pairIndex: number) => {
    onPairClick?.(pairIndex);
  }, [onPairClick]);

  const handleReset = useCallback(() => {
    if (images.length === 1) {
      const newPositions = new Map<string, number>();
      newPositions.set(images[0].id, 0);
      newPositions.set(TRAILING_ENDPOINT_KEY, resetGap);
      setFramePositions(newPositions);
      return;
    }

    onResetFrames(resetGap);
  }, [onResetFrames, resetGap, images, setFramePositions]);

  const handleDeleteSelected = useCallback(() => {
    selectedIds.forEach((id) => onImageDelete(id));
    clearSelection();
  }, [selectedIds, onImageDelete, clearSelection]);

  const handleNewShotFromSelection = useCallback(async () => {
    if (!onNewShotFromSelection) {
      return;
    }
    return onNewShotFromSelection(selectedIds);
  }, [onNewShotFromSelection, selectedIds]);

  return (
    <div className="w-full overflow-x-hidden relative">
      <div className="relative">
        <TimelineControls
          timeline={{
            shotId,
            projectId: projectId ?? null,
            readOnly,
            hasNoImages,
            zoomLevel,
            fullMax,
            showDragHint: !!(dragState.isDragging && dragState.activeId && !isMobile),
          }}
          audio={{
            audioUrl,
            onAudioChange,
          }}
          guidance={{
            primaryStructureVideo,
            structureVideos,
            onAddStructureVideo,
            onUpdateStructureVideo,
            onPrimaryStructureVideoInputChange,
            onShowVideoBrowser: () => setShowVideoBrowser(true),
            isUploadingStructureVideo,
            setIsUploadingStructureVideo,
          }}
          zoom={{
            onZoomIn: handleZoomInToCenter,
            onZoomOut: handleZoomOutFromCenter,
            onZoomReset: handleZoomReset,
            onZoomToStart: handleZoomToStart,
          }}
          bottom={{
            resetGap,
            setResetGap,
            maxGap,
            onReset: handleReset,
            onFileDrop,
            isUploadingImage,
            uploadProgress,
            pushMode,
          }}
        />

        <TimelineTrackContent
          data={{
            timelineRef,
            containerRef,
            zoomLevel,
            isFileOver,
            hasNoImages,
            enableTapToMove,
            selectedIds,
            handleDragEnter,
            handleDragOver,
            handleDragLeave,
            handleDrop,
            handleTimelineDoubleClick,
            handleTimelineTapToMove,
            clearSelection,
            containerWidth,
            shotId,
            projectId,
            readOnly,
            images,
            imagePositions,
            imagePositionsWithPending,
            activePendingFrame,
            trailingEndFrame,
            hasCallbackTrailingVideo,
            hasLiveTrailingVideo,
            projectAspectRatio,
            pairInfoWithPending,
            pairDataByIndex,
            localShotGenPositions,
            parentSegmentSlots,
            isSegmentsLoading,
            parentHasPendingTask,
            selectedOutputId,
            onPairClick,
            handleOpenPairSettings,
            onSegmentFrameCountChange,
            handleTrailingEndFrameChange,
            setCallbackTrailingVideoUrl,
            onFileDrop,
            videoOutputs,
            structureVideos,
            isStructureVideoLoading,
            cachedHasStructureVideo,
            onAddStructureVideo,
            onUpdateStructureVideo,
            onRemoveStructureVideo,
            primaryStructureVideo,
            onPrimaryStructureVideoInputChange,
            isUploadingStructureVideo,
            setIsUploadingStructureVideo,
            audioUrl,
            audioMetadata,
            onAudioChange,
            fullMin,
            fullMax,
            fullRange,
            handleZoomInToCenter,
            handleZoomOutFromCenter,
            handleZoomReset,
            handleZoomToStart,
            dragState,
            dragType,
            dropTargetFrame,
            pendingDropFrame,
            pendingDuplicateFrame,
            pendingExternalAddFrame,
            isUploadingImage,
            isInternalDropProcessing,
            currentDragFrame,
            swapTargetId,
            endpointDragFrame,
            isEndpointDraggingState,
            handleEndpointMouseDown,
            trailingVideoUrl,
            handleExtractFinalFrame,
            framePositions,
            dragOffset,
            isMobile,
            isTablet,
            handleMouseDown,
            handleDesktopDoubleClick,
            handleMobileTap,
            prefetchTaskData,
            onImageDelete,
            handleDuplicateInterceptor,
            onVariantDrop,
            handleInpaintClick,
            duplicatingImageId,
            duplicateSuccessImageId,
            isSelected,
            toggleSelection,
            pairPrompts,
            defaultPrompt,
            defaultNegativePrompt,
            showPairLabels,
            onClearEnhancedPrompt,
            currentPositions,
          }}
        />
      </div>

      <ResourceBrowserModalBase
        isOpen={showVideoBrowser}
        onOpenChange={setShowVideoBrowser}
        resourceType="structure-video"
        title="Browse Guidance Videos"
        onResourceSelect={handleVideoBrowserSelect}
      />

      {showSelectionBar && selectedIds.length > 0 && !readOnly && (
        <SelectionActionBar
          selectedCount={selectedIds.length}
          onDeselect={clearSelection}
          onDelete={handleDeleteSelected}
          onNewShot={onNewShotFromSelection ? handleNewShotFromSelection : undefined}
          onJumpToShot={onShotChange}
        />
      )}
    </div>
  );
};

const MemoizedTimelineContainer = React.memo(TimelineContainer);

export { MemoizedTimelineContainer as TimelineContainer };
