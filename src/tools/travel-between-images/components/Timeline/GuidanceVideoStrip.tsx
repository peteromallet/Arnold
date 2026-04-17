import React, { useRef, useState, useCallback, useEffect } from 'react';
import { TIMELINE_HORIZONTAL_PADDING, TIMELINE_PADDING_OFFSET } from './constants';
import { TimelineResizeHandle } from './TimelineResizeHandle';
import { Button } from '@/shared/components/ui/button';
import { X } from 'lucide-react';
import { useIsTablet } from '@/shared/hooks/mobile';
import { useTemporaryVisibility } from '../../hooks/video/useTemporaryVisibility';
import { useVideoMetadata } from '../../hooks/video/useVideoMetadata';
import { useVideoFrameExtraction } from '@/shared/hooks/videoFrameExtraction/useVideoFrameExtraction';
import { useClickOutside } from '../../hooks/useClickOutside';
import { useTimelineStripDrag } from './hooks/drag/useTimelineStripDrag';
import { useTabletEndpointSelection } from './hooks/useTabletEndpointSelection';
import { useVideoHoverPreview } from '@/shared/hooks/videoHoverPreview/useVideoHoverPreview';
import { GuidanceVideoStripPreviewPortal } from './GuidanceVideoStripPreviewPortal';
import { GuidanceVideoStripRangeControls } from './GuidanceVideoStripRangeControls';
import { calculateVideoFrameFromPosition, type GuidanceVideoStripProps } from './GuidanceVideoStrip.types';
import { isElementWithinKnownOverlay } from '@/shared/components/ui/overlay';

export const GuidanceVideoStrip: React.FC<GuidanceVideoStripProps> = ({
  videoUrl,
  videoMetadata,
  treatment,
  onTreatmentChange,
  onRemove,
  onMetadataExtracted,
  fullMin,
  fullMax,
  fullRange,
  containerWidth,
  zoomLevel,
  readOnly = false,
  outputStartFrame,
  outputEndFrame,
  sourceStartFrame,
  sourceEndFrame,
  onRangeChange,
  useAbsolutePosition = false,
  siblingRanges = [],
}) => {
  // Output range — where in timeline this video is positioned
  const effectiveOutputStart = outputStartFrame ?? fullMin;
  const effectiveOutputEnd = outputEndFrame ?? fullMax;
  const outputFrameCount = effectiveOutputEnd - effectiveOutputStart;

  const stripContainerRef = useRef<HTMLDivElement>(null);
  const outerContainerRef = useRef<HTMLDivElement>(null);
  const [currentVideoFrame, setCurrentVideoFrame] = useState(0);

  // Device detection and active state
  const isTablet = useIsTablet();
  const [isStripActive, setIsStripActive] = useState(false);

  // Temporary visibility for tap frame preview
  const tapPreview = useTemporaryVisibility(2000);

  const { metadata: effectiveMetadata } = useVideoMetadata(videoUrl, videoMetadata, {
    onExtracted: onMetadataExtracted,
  });

  // Source range — which frames from source video to use
  const totalVideoFrames = effectiveMetadata?.total_frames || 0;
  const effectiveSourceStart = sourceStartFrame ?? 0;
  const effectiveSourceEnd = sourceEndFrame ?? totalVideoFrames;
  const sourceFrameCount = Math.max(0, effectiveSourceEnd - effectiveSourceStart);

  const {
    isDragging,
    displayStart: displayOutputStart,
    displayEnd: displayOutputEnd,
    handleDragStart,
  } = useTimelineStripDrag({
    startFrame: effectiveOutputStart,
    endFrame: effectiveOutputEnd,
    fullRange,
    fullMin,
    fullMax,
    containerWidth,
    zoomLevel,
    siblingRanges,
    disabled: readOnly || !onRangeChange,
    onRangeChange,
    onTreatmentChange,
    treatment,
    videoTotalFrames: totalVideoFrames,
  });

  const displayOutputFrameCount = displayOutputEnd - displayOutputStart;

  const hoverPreview = useVideoHoverPreview({
    videoUrl,
    frameRate: effectiveMetadata?.frame_rate || 30,
    enabled: !isDragging && !!effectiveMetadata,
  });
  const { updateHoverPosition, reset: resetHoverPreview } = hoverPreview;

  const { frames: displayFrameImages } = useVideoFrameExtraction(videoUrl, {
    metadata: effectiveMetadata,
    treatment,
    sourceRange: { start: effectiveSourceStart, end: effectiveSourceEnd },
    outputFrameCount,
    skip: !!isDragging,
  });

  // Calculate video coverage for clip mode
  const videoCoversFrames = treatment === 'clip'
    ? Math.min(sourceFrameCount, outputFrameCount)
    : outputFrameCount;
  const videoCoverageRatio = outputFrameCount > 0 ? videoCoversFrames / outputFrameCount : 1;

  // Calculate position on timeline
  const stripEffectiveWidth = containerWidth - (TIMELINE_PADDING_OFFSET * 2);
  const clampedDisplayStart = Math.max(fullMin, displayOutputStart);
  const clampedDisplayEnd = Math.min(fullMax, displayOutputEnd);
  const startPixel = fullRange > 0
    ? TIMELINE_PADDING_OFFSET + ((clampedDisplayStart - fullMin) / fullRange) * stripEffectiveWidth
    : TIMELINE_PADDING_OFFSET;
  const endPixel = fullRange > 0
    ? TIMELINE_PADDING_OFFSET + ((clampedDisplayEnd - fullMin) / fullRange) * stripEffectiveWidth
    : TIMELINE_PADDING_OFFSET + stripEffectiveWidth;
  const widthPixel = Math.max(0, endPixel - startPixel);

  const stripLeftPercent = (startPixel / containerWidth) * 100;
  const stripWidthPercent = (widthPixel / containerWidth) * 100;

  // Sample one frame per N pixels, evenly distributed from extracted frames
  const PIXELS_PER_FRAME = 20;
  const targetFrameCount = Math.max(1, Math.floor(widthPixel / PIXELS_PER_FRAME));
  const framesToRender = displayFrameImages.length <= targetFrameCount
    ? displayFrameImages
    : targetFrameCount === 1
      ? [displayFrameImages[Math.floor(displayFrameImages.length / 2)]]
      : Array.from({ length: targetFrameCount }, (_, i) => (
        displayFrameImages[Math.round(i * (displayFrameImages.length - 1) / (targetFrameCount - 1))]
      ));
  const isCollapsed = targetFrameCount <= 1;

  const legacyPositionPercent = fullRange > 0 ? ((displayOutputStart - fullMin) / fullRange) * 100 : 0;
  const legacyWidthPercent = fullRange > 0 ? (displayOutputFrameCount / fullRange) * 100 : 100;

  // Tablet touch gesture handling (endpoint selection, tap-to-place, double-tap)
  const enableTapToSelect = isTablet && !readOnly && onRangeChange;

  const {
    selectedEndpoint,
    clearSelection,
    tapToPlaceHintVisible,
    handleEndpointTouchStart,
    handleEndpointTouchEnd,
    handleStripTouchStart,
    handleStripTouchEnd,
  } = useTabletEndpointSelection({
    enabled: !!enableTapToSelect,
    isStripActive,
    isTablet,
    stripLeftPercent,
    stripWidthPercent,
    fullMin,
    fullMax,
    fullRange,
    effectiveOutputStart,
    effectiveOutputEnd,
    siblingRanges,
    outerContainerRef,
    onRangeChange,
    onDoubleTap: useCallback(() => {
      setIsStripActive((prev) => !prev);
      tapPreview.hide();
    }, [tapPreview]),
    onSingleTap: useCallback((touch: Touch) => {
      const rect = stripContainerRef.current?.getBoundingClientRect();
      if (rect && effectiveMetadata) {
        const cursorX = touch.clientX - rect.left;
        const stripWidth = rect.width;
        const normalizedPosition = Math.max(0, Math.min(1, cursorX / stripWidth));

        const videoFrame = calculateVideoFrameFromPosition(
          normalizedPosition,
          treatment,
          effectiveMetadata.total_frames,
          displayOutputFrameCount,
          effectiveSourceStart,
          effectiveSourceEnd,
        );

        setCurrentVideoFrame(videoFrame);
        updateHoverPosition(touch.clientX, touch.clientY - 140, videoFrame);
        tapPreview.show();
      }
    }, [
      treatment,
      effectiveMetadata,
      displayOutputFrameCount,
      effectiveSourceStart,
      effectiveSourceEnd,
      updateHoverPosition,
      tapPreview,
    ]),
  });

  // Desktop: click outside to deactivate strip
  useClickOutside(
    () => {
      setIsStripActive(false);
      clearSelection();
    },
    { enabled: isStripActive && !isTablet, delay: 0 },
    outerContainerRef as React.RefObject<HTMLDivElement>,
  );

  // Handle mouse move for hover preview
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging || !effectiveMetadata) {
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const cursorX = e.clientX - rect.left;
    const stripWidth = rect.width;
    const normalizedPosition = Math.max(0, Math.min(1, cursorX / stripWidth));

    const videoFrame = calculateVideoFrameFromPosition(
      normalizedPosition,
      treatment,
      effectiveMetadata.total_frames,
      displayOutputFrameCount,
      effectiveSourceStart,
      effectiveSourceEnd,
    );

    setCurrentVideoFrame(videoFrame);
    updateHoverPosition(e.clientX, e.clientY - 140, videoFrame);
  }, [
    treatment,
    effectiveMetadata,
    displayOutputFrameCount,
    effectiveSourceStart,
    effectiveSourceEnd,
    updateHoverPosition,
    isDragging,
  ]);

  // Desktop: click on strip to toggle handles visibility
  const handleStripClick = useCallback((e: React.MouseEvent) => {
    if (isTablet) {
      return;
    }
    if (
      (e.target as HTMLElement).closest('button, select, [data-resize-handle]')
      || isElementWithinKnownOverlay(e.target as Element)
    ) {
      return;
    }
    setIsStripActive((prev) => !prev);
  }, [isTablet]);

  // Close hover state when treatment changes
  useEffect(() => {
    resetHoverPreview();
  }, [treatment, resetHoverPreview]);

  return (
    <div className={useAbsolutePosition ? 'contents' : 'w-full relative'}>
      <GuidanceVideoStripPreviewPortal
        hoverPosition={hoverPreview.hoverPosition}
        isVisible={(hoverPreview.isHovering || tapPreview.isVisible) && hoverPreview.isVideoReady && !isDragging}
        canvasRef={hoverPreview.canvasRef}
        currentVideoFrame={currentVideoFrame}
      />

      <div
        ref={outerContainerRef}
        className={`${useAbsolutePosition ? 'absolute' : 'relative'} h-20 ${useAbsolutePosition ? '' : '-mt-1 mb-3'} group ${isDragging ? 'select-none' : ''}`}
        data-tour="structure-video"
        style={{
          ...(useAbsolutePosition ? {
            left: `${stripLeftPercent}%`,
            width: `${stripWidthPercent}%`,
            top: 0,
            bottom: 0,
          } : {
            width: outputStartFrame !== undefined
              ? `${legacyWidthPercent * (zoomLevel > 1 ? zoomLevel : 1)}%`
              : (zoomLevel > 1 ? `${zoomLevel * 100}%` : '100%'),
            marginLeft: outputStartFrame !== undefined
              ? `${legacyPositionPercent}%`
              : 0,
            minWidth: outputStartFrame !== undefined ? 0 : '100%',
            paddingLeft: `${TIMELINE_HORIZONTAL_PADDING}px`,
            paddingRight: `${TIMELINE_HORIZONTAL_PADDING}px`,
          }),
          overflow: 'visible',
          cursor: isDragging === 'move' ? 'grabbing' : undefined,
        }}
      >
        {selectedEndpoint && enableTapToSelect && useAbsolutePosition && isStripActive && (
          <div
            className="absolute top-0 bottom-0 z-20 cursor-crosshair"
            style={{
              left: `${(-stripLeftPercent / stripWidthPercent) * 100}%`,
              right: `${(-(100 - stripLeftPercent - stripWidthPercent) / stripWidthPercent) * 100}%`,
            }}
            onTouchStart={handleStripTouchStart}
            onTouchEnd={handleStripTouchEnd}
          />
        )}

        {!readOnly && onRangeChange && (
          <>
            <TimelineResizeHandle
              side="left"
              isActive={isStripActive || selectedEndpoint === 'left'}
              isSelected={selectedEndpoint === 'left'}
              showHint={!!enableTapToSelect && tapToPlaceHintVisible}
              margin={useAbsolutePosition ? '0px' : `${TIMELINE_HORIZONTAL_PADDING}px`}
              onMouseDown={(e) => handleDragStart('left', e)}
              onTouchStart={(e) => handleEndpointTouchStart('left', e)}
              onTouchEnd={(e) => handleEndpointTouchEnd('left', e)}
            />
            <TimelineResizeHandle
              side="right"
              isActive={isStripActive || selectedEndpoint === 'right'}
              isSelected={selectedEndpoint === 'right'}
              showHint={!!enableTapToSelect && tapToPlaceHintVisible}
              margin={useAbsolutePosition ? '0px' : `${TIMELINE_HORIZONTAL_PADDING}px`}
              onMouseDown={(e) => handleDragStart('right', e)}
              onTouchStart={(e) => handleEndpointTouchStart('right', e)}
              onTouchEnd={(e) => handleEndpointTouchEnd('right', e)}
            />
          </>
        )}

        <div
          ref={stripContainerRef}
          className="absolute left-0 top-0 bottom-0"
          style={{
            width: treatment === 'clip' && sourceFrameCount < outputFrameCount
              ? `${videoCoverageRatio * 100}%`
              : '100%',
            paddingLeft: useAbsolutePosition ? '0px' : `${TIMELINE_HORIZONTAL_PADDING}px`,
            paddingRight: useAbsolutePosition ? '0px' : `${TIMELINE_HORIZONTAL_PADDING}px`,
          }}
          onMouseMove={handleMouseMove}
          onMouseEnter={hoverPreview.handleMouseEnter}
          onMouseLeave={hoverPreview.handleMouseLeave}
        >
          <video
            ref={hoverPreview.videoRef}
            src={videoUrl}
            preload="auto"
            className="hidden"
            crossOrigin="anonymous"
            muted
            playsInline
          />

          {!readOnly && !isCollapsed && (
            <Button
              variant="destructive"
              size="sm"
              className="absolute top-1 right-3 z-30 h-6 w-6 p-0 opacity-90 hover:opacity-100 shadow-lg rounded-full"
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              onTouchEnd={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onRemove();
              }}
              title="Remove guidance video"
            >
              <X className="h-4 w-4" />
            </Button>
          )}

          {framesToRender.length > 0 ? (
            <div
              className={`absolute top-5 bottom-1 flex border-2 rounded overflow-hidden shadow-md ${
                isDragging === 'move'
                  ? 'border-primary cursor-grabbing'
                  : isStripActive
                    ? 'border-primary cursor-grab'
                    : 'border-primary/40 cursor-pointer'
              } ${!readOnly && onRangeChange && !isStripActive ? 'hover:border-primary/60' : ''} ${selectedEndpoint ? 'cursor-crosshair' : ''}`}
              style={{
                left: useAbsolutePosition ? '2px' : '16px',
                right: useAbsolutePosition ? '2px' : '16px',
              }}
              onClick={handleStripClick}
              onMouseDown={(e) => {
                if (
                  (e.target as HTMLElement).closest('button, select')
                  || isElementWithinKnownOverlay(e.target as Element)
                ) {
                  return;
                }
                if (!isStripActive) {
                  return;
                }
                handleDragStart('move', e);
              }}
              onTouchStart={handleStripTouchStart}
              onTouchEnd={handleStripTouchEnd}
            >
              {framesToRender.map((frameUrl, index) => (
                <img
                  key={index}
                  src={frameUrl}
                  alt={`Frame ${index}`}
                  className="h-full object-cover flex-1"
                  style={{ minWidth: 0 }}
                />
              ))}
            </div>
          ) : (
            <div
              className={`absolute top-5 bottom-1 flex items-center justify-center bg-muted/50 dark:bg-muted-foreground/15 border rounded-sm ${
                !readOnly && onRangeChange
                  ? (isStripActive ? 'cursor-grab border-primary/50' : 'cursor-pointer hover:border-primary/40')
                  : 'border-border/30'
              } ${selectedEndpoint ? 'cursor-crosshair' : ''}`}
              style={{
                left: useAbsolutePosition ? '2px' : '16px',
                right: useAbsolutePosition ? '2px' : '16px',
              }}
              onClick={handleStripClick}
              onMouseDown={(e) => {
                if (!isStripActive) {
                  return;
                }
                handleDragStart('move', e);
              }}
              onTouchStart={handleStripTouchStart}
              onTouchEnd={handleStripTouchEnd}
            >
              <span className="text-xs text-muted-foreground font-medium">
                {displayFrameImages.length > 0 ? 'Loading frames...' : 'Loading video...'}
              </span>
            </div>
          )}
        </div>

        {outputStartFrame !== undefined && !readOnly && !isCollapsed && (
          <GuidanceVideoStripRangeControls
            displayOutputStart={displayOutputStart}
            displayOutputEnd={displayOutputEnd}
            isDragging={isDragging}
            treatment={treatment}
            onTreatmentChange={onTreatmentChange}
            onRangeChange={onRangeChange}
            effectiveMetadataTotalFrames={effectiveMetadata?.total_frames || 0}
            useAbsolutePosition={useAbsolutePosition}
          />
        )}
      </div>
    </div>
  );
};
