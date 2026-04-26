/**
 * LightboxLayout - Unified layout for all lightbox configurations.
 *
 * Sub-components call context hooks directly instead of receiving a bundled model object.
 * Layout-derived values (computed from props + context) use the small useLightboxLayoutComputed hook.
 */

import React from 'react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { Eraser, Square, Undo2, X } from 'lucide-react';
import type { LightboxLayoutProps } from './types';
import {
  useLightboxCoreSafe,
  useLightboxMediaSafe,
  useLightboxVariantsSafe,
  useLightboxNavigationSafe,
} from '../../contexts/LightboxStateContext';
import { useImageEditCanvasSafe } from '../../contexts/ImageEditCanvasContext';
import { useVideoEditSafe } from '../../contexts/VideoEditContext';
import { VariantOverlayBadge } from './VariantOverlayBadge';
import { NewImageOverlayButton } from './NewImageOverlayButton';
import { AdjacentSegmentNavigation } from './AdjacentSegmentNavigation';
import { PreviewSequencePill } from './PreviewSequencePill';
import { ConstituentImageNavigation } from './ConstituentImageNavigation';
import { NavigationArrows } from '../NavigationArrows';
import { FloatingToolControls } from '../FloatingToolControls';
import { AnnotationFloatingControls } from '../AnnotationFloatingControls';
import {
  TopRightControls,
  BottomLeftControls,
  BottomRightControls,
} from '../ButtonGroups';
import { MediaDisplayWithCanvas } from '../MediaDisplayWithCanvas';
import { VideoEditModeDisplay } from '../VideoEditModeDisplay';
import { VideoTrimModeDisplay } from '../VideoTrimModeDisplay';
import { WorkflowControlsBar } from '../WorkflowControlsBar';

/** Derives layout flags from props + core context. Used by components that need layout-aware rendering. */
function useLightboxLayoutComputed(props: Pick<LightboxLayoutProps, 'showPanel' | 'shouldShowSidePanel'>) {
  const core = useLightboxCoreSafe();

  const isSidePanelLayout = props.showPanel && props.shouldShowSidePanel;
  const isStackedLayout = props.showPanel && !props.shouldShowSidePanel;
  const floatingToolVariant: 'mobile' | 'tablet' = core.isMobile ? 'mobile' : 'tablet';
  const mediaDisplayVariant: 'desktop-side-panel' | 'mobile-stacked' | 'regular-centered' = props.showPanel
    ? (isSidePanelLayout ? 'desktop-side-panel' : 'mobile-stacked')
    : 'regular-centered';
  const mediaDisplayContainerClassName = isSidePanelLayout
    ? 'max-w-full max-h-full'
    : 'w-full h-full';
  const mediaDisplayDebugContext = props.showPanel
    ? (isSidePanelLayout ? 'Desktop' : 'Mobile Stacked')
    : 'Regular Centered';
  const topCenterClassName = isStackedLayout
    ? 'absolute top-4 md:top-16 left-1/2 transform -translate-x-1/2 z-[60] flex flex-col items-center gap-2'
    : 'absolute top-4 left-1/2 transform -translate-x-1/2 z-[60] flex flex-col items-center gap-2';

  return {
    isSidePanelLayout,
    isStackedLayout,
    floatingToolVariant,
    mediaDisplayVariant,
    mediaDisplayContainerClassName,
    mediaDisplayDebugContext,
    topCenterClassName,
  };
}

function MediaContent({ layout, effectiveTasksPaneOpen, effectiveTasksPaneWidth }: {
  layout: ReturnType<typeof useLightboxLayoutComputed>;
  effectiveTasksPaneOpen: boolean;
  effectiveTasksPaneWidth: number;
}) {
  const mediaState = useLightboxMediaSafe();
  const variantsState = useLightboxVariantsSafe();
  const videoEdit = useVideoEditSafe();

  if (mediaState.isVideo && videoEdit.isVideoEditModeActive && videoEdit.videoEditing) {
    return (
      <VideoEditModeDisplay
        videoRef={videoEdit.videoEditing.videoRef}
        videoUrl={mediaState.effectiveVideoUrl}
        posterUrl={variantsState.activeVariant?.thumbnail_url || mediaState.media.thumbUrl}
        videoDuration={videoEdit.videoDuration}
        onLoadedMetadata={videoEdit.setVideoDuration}
        selections={videoEdit.videoEditing.selections}
        activeSelectionId={videoEdit.videoEditing.activeSelectionId}
        onSelectionChange={videoEdit.videoEditing.handleUpdateSelection}
        onSelectionClick={videoEdit.videoEditing.setActiveSelectionId}
        onRemoveSelection={videoEdit.videoEditing.handleRemoveSelection}
        onAddSelection={videoEdit.videoEditing.handleAddSelection}
      />
    );
  }

  if (mediaState.isVideo && videoEdit.isVideoTrimModeActive) {
    return (
      <VideoTrimModeDisplay
        videoRef={videoEdit.trimVideoRef}
        videoUrl={mediaState.effectiveVideoUrl}
        posterUrl={variantsState.activeVariant?.thumbnail_url || mediaState.media.thumbUrl}
        trimState={videoEdit.trimState}
        onLoadedMetadata={videoEdit.setVideoDuration}
        onTimeUpdate={videoEdit.setTrimCurrentTime}
      />
    );
  }

  return (
    <MediaDisplayWithCanvas
      effectiveImageUrl={mediaState.isVideo ? mediaState.effectiveVideoUrl : mediaState.effectiveMediaUrl}
      thumbUrl={variantsState.activeVariant?.thumbnail_url || mediaState.media.thumbUrl}
      isVideo={mediaState.isVideo}
      onImageLoad={mediaState.setImageDimensions}
      onVideoLoadedMetadata={(event) => {
        const video = event.currentTarget;
        if (Number.isFinite(video.duration) && video.duration > 0) {
          videoEdit.setVideoDuration(video.duration);
        }
      }}
      variant={layout.mediaDisplayVariant}
      containerClassName={layout.mediaDisplayContainerClassName}
      tasksPaneWidth={layout.isSidePanelLayout && effectiveTasksPaneOpen ? effectiveTasksPaneWidth : 0}
      debugContext={layout.mediaDisplayDebugContext}
      imageDimensions={mediaState.effectiveImageDimensions}
    />
  );
}

function TopCenterOverlay({ className, adjacentSegments, segmentSlotMode }: {
  className: string;
  adjacentSegments?: LightboxLayoutProps['adjacentSegments'];
  segmentSlotMode?: LightboxLayoutProps['segmentSlotMode'];
}) {
  const core = useLightboxCoreSafe();
  const mediaState = useLightboxMediaSafe();
  const variantsState = useLightboxVariantsSafe();

  return (
    <div className={className}>
      {adjacentSegments && !mediaState.isVideo && (
        <AdjacentSegmentNavigation adjacentSegments={adjacentSegments} />
      )}
      {mediaState.isVideo && segmentSlotMode?.adjacentVideoThumbnails && segmentSlotMode?.onOpenPreviewDialog && (
        <PreviewSequencePill
          adjacentVideoThumbnails={segmentSlotMode.adjacentVideoThumbnails}
          onOpenPreviewDialog={segmentSlotMode.onOpenPreviewDialog}
        />
      )}
      <VariantOverlayBadge
        activeVariant={variantsState.activeVariant ?? undefined}
        variants={variantsState.variants}
        readOnly={core.readOnly}
        isMakingMainVariant={variantsState.isMakingMainVariant}
        canMakeMainVariant={variantsState.canMakeMainVariant}
        onMakeMainVariant={variantsState.handleMakeMainVariant}
      />
    </div>
  );
}

function OverlayElements({ topCenterClassName, showFloatingTools, props }: {
  topCenterClassName: string;
  showFloatingTools: boolean;
  props: LightboxLayoutProps;
}) {
  const core = useLightboxCoreSafe();
  const mediaState = useLightboxMediaSafe();
  const variantsState = useLightboxVariantsSafe();
  const imageEdit = useImageEditCanvasSafe();
  const floatingToolVariant: 'mobile' | 'tablet' = core.isMobile ? 'mobile' : 'tablet';
  const buttonGroups = props.buttonGroups;

  return (
    <>
      <TopCenterOverlay
        className={topCenterClassName}
        adjacentSegments={props.adjacentSegments}
        segmentSlotMode={props.segmentSlotMode}
      />

      <NewImageOverlayButton
        isVideo={mediaState.isVideo}
        readOnly={core.readOnly}
        activeVariantId={variantsState.activeVariant?.id}
        primaryVariantId={variantsState.primaryVariant?.id}
        selectedProjectId={core.selectedProjectId}
        isPromoting={variantsState.isPromoting}
        promoteSuccess={variantsState.promoteSuccess}
        onPromote={variantsState.handlePromoteToGeneration}
      />

      {showFloatingTools && imageEdit.isSpecialEditMode && (
        <FloatingToolControls variant={floatingToolVariant} />
      )}

      <BottomLeftControls {...buttonGroups.bottomLeft} />
      <BottomRightControls {...buttonGroups.bottomRight} />
      <TopRightControls {...buttonGroups.topRight} />

      {props.segmentSlotMode?.onNavigateToImage && (
        <ConstituentImageNavigation
          startImageId={props.segmentSlotMode.pairData.startImage?.id}
          endImageId={props.segmentSlotMode.pairData.endImage?.id}
          startImageUrl={props.segmentSlotMode.pairData.startImage?.thumbUrl || props.segmentSlotMode.pairData.startImage?.url}
          endImageUrl={props.segmentSlotMode.pairData.endImage?.thumbUrl || props.segmentSlotMode.pairData.endImage?.url}
          onNavigateToImage={props.segmentSlotMode.onNavigateToImage}
          variant="overlay"
        />
      )}

      {props.customOverlay}

      <WorkflowControlsBar {...props.workflowBar} />
    </>
  );
}

function CompactEditControls() {
  const core = useLightboxCoreSafe();
  const imageEdit = useImageEditCanvasSafe();

  if (core.readOnly || !imageEdit.isSpecialEditMode || imageEdit.editMode === 'text') return null;

  return (
    <div className="absolute top-20 left-4 z-[70] select-none" onClick={(event) => event.stopPropagation()}>
      <div className="mb-2 bg-background backdrop-blur-md rounded-lg p-2 space-y-1.5 w-40 border border-border shadow-xl">
        {imageEdit.editMode === 'inpaint' && (
          <div className="space-y-0.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-foreground">Size:</label>
              <span className="text-xs text-muted-foreground">{imageEdit.brushSize}px</span>
            </div>
            <input
              type="range"
              min={5}
              max={100}
              value={imageEdit.brushSize}
              onChange={(event) => imageEdit.setBrushSize(parseInt(event.target.value, 10))}
              className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>
        )}

        {imageEdit.editMode === 'inpaint' && (
          <Button
            variant={imageEdit.isEraseMode ? 'default' : 'secondary'}
            size="sm"
            onClick={() => imageEdit.setIsEraseMode(!imageEdit.isEraseMode)}
            className={cn('w-full text-xs h-7', imageEdit.isEraseMode && 'bg-purple-600 hover:bg-purple-700')}
          >
            <Eraser className="h-3 w-3 mr-1" />
            {imageEdit.isEraseMode ? 'Erase' : 'Paint'}
          </Button>
        )}

        {imageEdit.editMode === 'annotate' && (
          <div className="flex gap-1">
            <Button variant="default" size="sm" className="flex-1 text-xs h-7" disabled>
              <Square className="h-3 w-3" />
            </Button>
          </div>
        )}

        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                size="sm"
                onClick={imageEdit.handleUndo}
                disabled={imageEdit.brushStrokes.length === 0}
                className="flex-1 text-xs h-7"
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
                onClick={imageEdit.handleClearMask}
                disabled={imageEdit.brushStrokes.length === 0}
                className="flex-1 text-xs h-7"
              >
                <X className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Clear all</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </div>
  );
}

function PanelLayoutView({ props }: { props: LightboxLayoutProps }) {
  const core = useLightboxCoreSafe();
  const navigation = useLightboxNavigationSafe();
  const imageEdit = useImageEditCanvasSafe();
  const layout = useLightboxLayoutComputed(props);

  const isDesktopPanel = layout.isSidePanelLayout;
  const showAnnotationControls = imageEdit.isSpecialEditMode && imageEdit.editMode === 'annotate';

  return (
    <div
      data-lightbox-bg
      className={cn('w-full h-full bg-black/90', isDesktopPanel ? 'flex' : 'flex flex-col')}
      onClick={(event) => event.stopPropagation()}
    >
      <div
        data-lightbox-bg
        className={cn('flex items-center justify-center relative overflow-hidden', isDesktopPanel ? 'flex-1 touch-none' : 'flex-none touch-none z-10')}
        style={isDesktopPanel
          ? { width: '60%' }
          : {
              height: '50%',
              transform: navigation.swipeNavigation.isSwiping
                ? `translateX(${navigation.swipeNavigation.swipeOffset}px)`
                : undefined,
              transition: navigation.swipeNavigation.isSwiping ? 'none' : 'transform 0.2s ease-out',
            }}
        onClick={(event) => event.stopPropagation()}
        {...(!isDesktopPanel ? navigation.swipeNavigation.swipeHandlers : {})}
      >
        {isDesktopPanel && (
          <NavigationArrows
            showNavigation={navigation.showNavigation}
            readOnly={core.readOnly}
            onPrevious={navigation.handleSlotNavPrev}
            onNext={navigation.handleSlotNavNext}
            hasPrevious={navigation.hasPrevious}
            hasNext={navigation.hasNext}
            variant="desktop"
          />
        )}

        <MediaContent
          layout={layout}
          effectiveTasksPaneOpen={props.effectiveTasksPaneOpen}
          effectiveTasksPaneWidth={props.effectiveTasksPaneWidth}
        />
        {showAnnotationControls && (
          <AnnotationFloatingControls
            selectedShapeId={imageEdit.selectedShapeId}
            isAnnotateMode={imageEdit.isAnnotateMode}
            brushStrokes={imageEdit.brushStrokes}
            getDeleteButtonPosition={imageEdit.getDeleteButtonPosition}
            onToggleFreeForm={imageEdit.handleToggleFreeForm}
            onDeleteSelected={imageEdit.handleDeleteSelected}
            positionStrategy="fixed"
            freeFormActiveClassName="bg-purple-600 hover:bg-purple-700 text-white"
            freeFormInactiveClassName="bg-gray-700 hover:bg-gray-600 text-white"
            deleteButtonClassName="bg-red-600 hover:bg-red-700 text-white"
          />
        )}
        <OverlayElements props={props} topCenterClassName={layout.topCenterClassName} showFloatingTools={true} />

        {!isDesktopPanel && (
          <NavigationArrows
            showNavigation={navigation.showNavigation}
            readOnly={core.readOnly}
            onPrevious={navigation.handleSlotNavPrev}
            onNext={navigation.handleSlotNavNext}
            hasPrevious={navigation.hasPrevious}
            hasNext={navigation.hasNext}
            variant="mobile"
          />
        )}
      </div>

      <div
        data-task-details-panel
        className={cn('bg-background overflow-hidden relative z-[60] overscroll-none', isDesktopPanel ? 'border-l border-border h-full' : 'border-t border-border overflow-y-auto')}
        style={isDesktopPanel ? { width: '40%' } : { height: '50%' }}
      >
        {props.controlsPanelContent}
      </div>
    </div>
  );
}

function CenteredLayoutView({ props }: { props: LightboxLayoutProps }) {
  const core = useLightboxCoreSafe();
  const navigation = useLightboxNavigationSafe();
  const imageEdit = useImageEditCanvasSafe();
  const layout = useLightboxLayoutComputed(props);

  const showAnnotationControls = imageEdit.isSpecialEditMode && imageEdit.editMode === 'annotate';

  return (
    <div
      data-lightbox-bg
      className="relative flex flex-col items-center gap-3 sm:gap-4 md:gap-6 px-3 py-4 sm:px-4 sm:py-6 md:px-6 md:py-8 w-full h-full touch-none"
      onClick={(event) => event.stopPropagation()}
    >
      <div
        data-lightbox-bg
        className={cn(
          'relative flex items-center justify-center max-w-full my-auto',
          'touch-none'
        )}
        style={{
          height: 'calc(100vh - 220px)',
          maxHeight: 'calc(100vh - 220px)',
          transform: navigation.swipeNavigation.isSwiping
            ? `translateX(${navigation.swipeNavigation.swipeOffset}px)`
            : undefined,
          transition: navigation.swipeNavigation.isSwiping ? 'none' : 'transform 0.2s ease-out',
        }}
        onClick={(event) => event.stopPropagation()}
        {...navigation.swipeNavigation.swipeHandlers}
      >
        <MediaContent
          layout={layout}
          effectiveTasksPaneOpen={props.effectiveTasksPaneOpen}
          effectiveTasksPaneWidth={props.effectiveTasksPaneWidth}
        />
        {showAnnotationControls && (
          <AnnotationFloatingControls
            selectedShapeId={imageEdit.selectedShapeId}
            isAnnotateMode={imageEdit.isAnnotateMode}
            brushStrokes={imageEdit.brushStrokes}
            getDeleteButtonPosition={imageEdit.getDeleteButtonPosition}
            onToggleFreeForm={imageEdit.handleToggleFreeForm}
            onDeleteSelected={imageEdit.handleDeleteSelected}
            positionStrategy="fixed"
            freeFormActiveClassName="bg-purple-600 hover:bg-purple-700 text-white"
            freeFormInactiveClassName="bg-gray-700 hover:bg-gray-600 text-white"
            deleteButtonClassName="bg-red-600 hover:bg-red-700 text-white"
          />
        )}
        <OverlayElements
          props={props}
          topCenterClassName="absolute top-4 left-1/2 transform -translate-x-1/2 z-[60] flex flex-col items-center gap-2"
          showFloatingTools={false}
        />
        <CompactEditControls />

        <NavigationArrows
          showNavigation={navigation.showNavigation}
          readOnly={core.readOnly}
          onPrevious={navigation.handleSlotNavPrev}
          onNext={navigation.handleSlotNavNext}
          hasPrevious={navigation.hasPrevious}
          hasNext={navigation.hasNext}
          variant="mobile"
        />
      </div>

    </div>
  );
}

export const LightboxLayout: React.FC<LightboxLayoutProps> = (props) => {
  return props.showPanel
    ? <PanelLayoutView props={props} />
    : <CenteredLayoutView props={props} />;
};
