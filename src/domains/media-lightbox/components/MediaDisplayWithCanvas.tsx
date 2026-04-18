import React from 'react';
import { StyledVideoPlayer } from '@/shared/components/media/StyledVideoPlayer';
import { StrokeOverlay } from './StrokeOverlay';
import { RepositionOverlay } from './RepositionOverlay';
import { useImageEditCanvasSafe } from '../contexts/ImageEditCanvasContext';
import { useRepositionGestureHandlers } from '../hooks/useRepositionGestureHandlers';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';

interface MediaDisplayWithCanvasProps {
  // Media info
  effectiveImageUrl: string;
  thumbUrl?: string;
  isVideo: boolean;

  // Handlers
  onImageLoad?: (dimensions: { width: number; height: number }) => void;
  onVideoLoadedMetadata?: (e: React.SyntheticEvent<HTMLVideoElement>) => void;

  // Styling variants
  variant?: 'desktop-side-panel' | 'mobile-stacked' | 'regular-centered';
  className?: string;
  containerClassName?: string;

  // Layout adjustments
  tasksPaneWidth?: number; // Width of tasks pane to adjust for (desktop only)

  // Playback constraints (for trim preview)
  playbackStart?: number;
  playbackEnd?: number;

  // Debug
  debugContext?: string;

  // Konva stroke overlay
  imageDimensions?: { width: number; height: number } | null;
}

export const MediaDisplayWithCanvas: React.FC<MediaDisplayWithCanvasProps> = ({
  effectiveImageUrl,
  thumbUrl,
  isVideo,
  onImageLoad,
  onVideoLoadedMetadata,
  variant = 'regular-centered',
  className = '',
  containerClassName = '',
  tasksPaneWidth = 0,
  playbackStart,
  playbackEnd,
  debugContext = 'MediaDisplay',
  imageDimensions,
}) => {
  // Read canvas/tool state from ImageEditCanvasContext (safe defaults when outside provider)
  const {
    isFlippedHorizontally, isSaving, isInpaintMode, editMode: rawEditMode,
    isAnnotateMode, brushStrokes, isEraseMode, brushSize, annotationMode,
    onStrokeComplete, onStrokesChange, onSelectionChange, onTextModeHint, strokeOverlayRef,
    repositionDragHandlers, isRepositionDragging, repositionTransform, getTransformStyle,
    setScale: onRepositionScaleChange, setRotation: onRepositionRotationChange,
    imageContainerRef,
  } = useImageEditCanvasSafe();

  // Derive reposition values from context
  const editMode = rawEditMode ?? 'text';
  const repositionRotation = repositionTransform?.rotation ?? 0;
  const repositionScale = repositionTransform?.scale ?? 1;
  const repositionTransformStyle = editMode === 'reposition'
    ? getTransformStyle()
    : undefined;

  // Track the display size AND position of the image for Konva overlay
  const [displaySize, setDisplaySize] = React.useState({ width: 0, height: 0 });
  const [imageOffset, setImageOffset] = React.useState({ left: 0, top: 0 });
  const imageWrapperRef = React.useRef<HTMLDivElement>(null);
  const imageRef = React.useRef<HTMLImageElement>(null);
  const [imageLoadError, setImageLoadError] = React.useState(false);

  const {
    dragContainerRef,
    handlesOverlayRef,
    handleCornerRotateStart,
    handleCornerRotateMove,
    handleCornerRotateEnd,
  } = useRepositionGestureHandlers({
    isInpaintMode,
    editMode,
    repositionDragHandlers,
    onRepositionScaleChange,
    onRepositionRotationChange,
    repositionScale,
    repositionRotation,
    imageRef,
    imageWrapperRef,
  });

  // Progressive loading: show thumbnail first, then swap to full image when loaded
  const [fullImageLoaded, setFullImageLoaded] = React.useState(() => {
    // If there's no thumbnail (or thumb equals full), we can render full immediately.
    if (!thumbUrl || thumbUrl === effectiveImageUrl) return true;
    // If the full image is already in the browser cache, skip the thumb flash.
    try {
      const img = new Image();
      img.src = effectiveImageUrl;
      return img.complete;
    } catch {
      return false;
    }
  });

  // Reset error/loading state when URL changes, and try to skip the thumbnail
  // if the full image is already cached (prevents "small thumb then normal size" flash).
  React.useLayoutEffect(() => {
    setImageLoadError(false);

    let newFullImageLoaded = false;

    if (!thumbUrl || thumbUrl === effectiveImageUrl) {
      newFullImageLoaded = true;
    } else {
      try {
        const img = new Image();
        img.src = effectiveImageUrl;
        if (img.complete) {
          newFullImageLoaded = true;
          onImageLoad?.({ width: img.naturalWidth, height: img.naturalHeight });
        }
      } catch {
        // Keep false
      }
    }

    setFullImageLoaded(newFullImageLoaded);

    // NOTE: imageDimensions is intentionally NOT in deps to avoid infinite loop:
    // This effect calls onImageLoad which updates imageDimensions in parent,
    // which would trigger this effect again if imageDimensions was a dependency.
     
  }, [effectiveImageUrl, thumbUrl, debugContext, onImageLoad]);

  // Measure the actual image element for Konva Stage size and position
  // This is more accurate than measuring the wrapper because the image has the
  // actual constrained dimensions applied via max-w-full max-h-full
  React.useEffect(() => {
    const img = imageRef.current;
    const wrapper = imageWrapperRef.current;
    if (!img || !wrapper) return;

    const updateSize = () => {
      const { clientWidth, clientHeight, offsetLeft, offsetTop } = img;
      if (clientWidth > 0 && clientHeight > 0) {
        setDisplaySize({ width: clientWidth, height: clientHeight });
        setImageOffset({ left: offsetLeft, top: offsetTop });
      }
    };

    // Update on load and resize
    updateSize();
    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(img);
    resizeObserver.observe(wrapper);

    return () => resizeObserver.disconnect();
  }, []);

  // Variant-specific styling
  const getMediaStyle = (): React.CSSProperties => {
    switch (variant) {
      case 'desktop-side-panel': {
        // Adjust max-width to account for tasks pane if present
        const adjustedMaxWidth = tasksPaneWidth > 0 
          ? `calc(55vw - ${tasksPaneWidth * 0.55}px)` // 55% of remaining space after tasks pane
          : '55vw';
        return { 
          maxWidth: adjustedMaxWidth, 
          maxHeight: '98vh',
          transition: 'max-width 300ms ease', // Smooth resize when tasks pane opens/closes
        };
      }
      case 'mobile-stacked':
        // Use 100% to fit within the container (which is 45dvh in InlineEditView)
        // instead of fixed vh/vw which might overflow
        return { maxWidth: '100%', maxHeight: '100%' };
      case 'regular-centered':
        return {}; // Use natural sizing with max-w-full max-h-full
      default:
        return {};
    }
  };

  const mediaStyle = getMediaStyle();

  // Check if URL is missing
  if (!effectiveImageUrl) {
    return (
      <div className={`relative flex items-center justify-center ${containerClassName}`}>
        <div className="text-center text-white bg-red-900/80 rounded-lg p-6 backdrop-blur-sm border border-red-500/50">
          <p className="font-medium text-lg mb-2">⚠️ Media URL Missing</p>
          <p className="text-white/70 text-sm">The media URL is not available.</p>
          <p className="text-white/50 text-xs mt-2">Check console for details.</p>
        </div>
      </div>
    );
  }
  
  // Show error state if image failed to load
  if (imageLoadError && !isVideo) {
    return (
      <div className={`relative flex items-center justify-center ${containerClassName}`}>
        <div className="text-center text-white bg-red-900/80 rounded-lg p-6 backdrop-blur-sm border border-red-500/50 max-w-md">
          <p className="font-medium text-lg mb-2">⚠️ Failed to Load Image</p>
          <p className="text-white/70 text-sm mb-3">The image could not be loaded (HTTP 400 error).</p>
          <p className="text-white/50 text-xs break-all mb-3">{effectiveImageUrl}</p>
          <button
            onClick={() => setImageLoadError(false)}
            className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded text-sm transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show checkered background pattern for reposition mode to indicate transparent/dead areas
  const isRepositionMode = editMode === 'reposition' && isInpaintMode;
  
  return (
    <div
      data-lightbox-bg
      ref={imageContainerRef as React.RefObject<HTMLDivElement>}
      className={`relative flex items-center justify-center w-full h-full ${containerClassName}`}
      style={{
        touchAction: 'none',
        // Checkered pattern background for reposition mode
        ...(isRepositionMode ? {
          backgroundImage: `
            linear-gradient(45deg, #1a1a2e 25%, transparent 25%),
            linear-gradient(-45deg, #1a1a2e 25%, transparent 25%),
            linear-gradient(45deg, transparent 75%, #1a1a2e 75%),
            linear-gradient(-45deg, transparent 75%, #1a1a2e 75%)
          `,
          backgroundSize: '20px 20px',
          backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          backgroundColor: '#252540',
          // Clip transformed image to prevent it from appearing over other UI elements
          overflow: 'hidden',
        } : {})
      }}
    >
      {isVideo ? (
        // Video Player - StyledVideoPlayer handles its own centering
        <StyledVideoPlayer
          src={effectiveImageUrl}
          poster={thumbUrl}
          loop
          muted
          autoPlay
          playsInline
          preload="auto"
          className={`max-w-full max-h-full shadow-wes border border-border/20 ${variant === 'regular-centered' ? 'rounded' : ''}`}
          style={mediaStyle}
          videoDimensions={imageDimensions ?? undefined}
          onLoadedMetadata={onVideoLoadedMetadata}
          playbackStart={playbackStart}
          playbackEnd={playbackEnd}
        />
      ) : (
        // Image with Canvas Overlays
        // Use a single relative container with the image and canvas both using same centering/constraints
        <div
          ref={dragContainerRef}
          className={`relative w-full h-full flex items-center justify-center ${!isRepositionMode ? 'pointer-events-none' : ''}`}
          style={{
            // Black background for reposition mode (shows where empty areas will be)
            ...(isRepositionMode ? {
              backgroundColor: '#000000',
            } : {}),
            // Enable drag-to-move cursor in reposition mode
            cursor: isRepositionMode
              ? (isRepositionDragging ? 'grabbing' : 'grab')
              : undefined,
            // Prevent text selection during drag
            userSelect: isRepositionMode ? 'none' : undefined,
            WebkitUserSelect: isRepositionMode ? 'none' : undefined,
            touchAction: isRepositionMode ? 'none' : undefined,
          }}
          // Apply drag handlers in reposition mode (wheel is native via useEffect)
          {...(isRepositionMode && repositionDragHandlers ? {
            onPointerDown: repositionDragHandlers.onPointerDown,
            onPointerMove: repositionDragHandlers.onPointerMove,
            onPointerUp: repositionDragHandlers.onPointerUp,
            onPointerCancel: repositionDragHandlers.onPointerCancel,
          } : {})}
        >
          {/*
            Wrapper fills available space. Image is constrained within via max-w/h.
            Konva overlay is positioned absolutely at the image's exact location.
          */}
          <div
            ref={imageWrapperRef}
            className={`relative w-full h-full flex items-center justify-center overflow-hidden ${!isRepositionMode ? 'pointer-events-none' : ''}`}
          >
            {/* Use thumbnail or full image based on loading state */}
            <img
              ref={imageRef}
              src={thumbUrl && thumbUrl !== effectiveImageUrl && !fullImageLoaded ? thumbUrl : effectiveImageUrl}
              alt="Media content"
              draggable={false}
              className={`
                block max-w-full max-h-full select-none
                ${variant === 'regular-centered' ? 'rounded' : ''}
                ${isFlippedHorizontally ? 'scale-x-[-1]' : ''}
                ${isSaving ? 'opacity-30' : 'opacity-100'}
                ${isInpaintMode ? 'pointer-events-none' : ''}
                ${editMode !== 'reposition' ? 'transition-opacity duration-300' : ''}
                ${className}
              `.trim()}
              style={{
                ...mediaStyle,
                ...(editMode === 'reposition' && repositionTransformStyle ? repositionTransformStyle : {}),
                transform: editMode === 'reposition' && repositionTransformStyle?.transform
                  ? repositionTransformStyle.transform
                  : (isFlippedHorizontally ? 'scaleX(-1)' : 'none'),
                transformOrigin: editMode === 'reposition' ? 'center center' : undefined,
                // Required because MediaDisplayWithCanvas.tsx:272, :301, and :314 disable pointer events in this branch.
                pointerEvents: isInpaintMode ? 'none' : 'auto',
                // Keep image below settings panel during reposition (z-80 is the panel)
                zIndex: editMode === 'reposition' ? 40 : undefined,
                position: editMode === 'reposition' ? 'relative' : undefined,
                // STABILITY FIX: Prevent small thumbnail display
                // When showing thumbnail (not full image), force it to fill the container
                // This prevents the jarring size jump when the full image loads
                // NOTE: Only do this for thumbnails - full images need natural sizing for Konva overlay accuracy
                ...((imageDimensions && !fullImageLoaded && thumbUrl && thumbUrl !== effectiveImageUrl) ? {
                  // Thumbnail mode: force full size display
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain' as const,
                } : {}),
                // Always set aspectRatio when we have dimensions (helps with sizing calculations)
                aspectRatio: imageDimensions
                  ? `${imageDimensions.width} / ${imageDimensions.height}`
                  : undefined,
              }}
              onLoad={(e) => {
                const img = e.target as HTMLImageElement;
                // Call onImageLoad for both thumbnail and full image to set dimensions immediately
                // This prevents size jump by setting CSS aspectRatio from thumbnail dimensions
                if (img.src === effectiveImageUrl || !thumbUrl || thumbUrl === effectiveImageUrl) {
                  setFullImageLoaded(true);
                  onImageLoad?.({
                    width: img.naturalWidth,
                    height: img.naturalHeight
                  });
                } else {
                  // Thumbnail loaded - still call onImageLoad to set aspect ratio immediately
                  // This prevents the thumbnail from displaying smaller than the final image
                  onImageLoad?.({
                    width: img.naturalWidth,
                    height: img.naturalHeight
                  });
                }
              }}
              onError={() => {
                normalizeAndPresentError(new Error(`Image load failed: ${effectiveImageUrl}`), {
                  context: `${debugContext}.onImageError`,
                  showToast: false,
                  logData: { url: effectiveImageUrl },
                });
                setImageLoadError(true);
              }}
            />

            {/* Overlay container - positioned exactly over the image */}
            {isInpaintMode && (editMode === 'inpaint' || editMode === 'annotate') &&
             imageDimensions && onStrokeComplete && onStrokesChange && onSelectionChange && displaySize.width > 0 && displaySize.height > 0 && (
              <div
                className="absolute overflow-hidden"
                style={{
                  zIndex: 50,
                  // Position exactly over the image element
                  left: imageOffset.left,
                  top: imageOffset.top,
                  width: displaySize.width,
                  height: displaySize.height,
                  // CRITICAL: Override parent's pointer-events:none to allow touch/pointer events on canvas
                  pointerEvents: 'auto',
                }}
              >
                <StrokeOverlay
                  ref={strokeOverlayRef}
                  imageWidth={imageDimensions.width}
                  imageHeight={imageDimensions.height}
                  displayWidth={displaySize.width}
                  displayHeight={displaySize.height}
                  strokes={brushStrokes}
                  isEraseMode={isEraseMode}
                  brushSize={brushSize}
                  annotationMode={annotationMode}
                  isInpaintMode={isInpaintMode}
                  isAnnotateMode={isAnnotateMode}
                  editMode={editMode}
                  onStrokeComplete={onStrokeComplete}
                  onStrokesChange={onStrokesChange}
                  onSelectionChange={onSelectionChange}
                  onTextModeHint={onTextModeHint}
                />
              </div>
            )}
          </div>

          {/* Preload full image in background when showing thumbnail */}
          {thumbUrl && thumbUrl !== effectiveImageUrl && !fullImageLoaded && (
            <img
              src={effectiveImageUrl}
              alt=""
              className="hidden"
              onLoad={(e) => {
                const img = e.target as HTMLImageElement;
                setFullImageLoaded(true);
                onImageLoad?.({
                  width: img.naturalWidth,
                  height: img.naturalHeight
                });
              }}
              onError={() => {
                normalizeAndPresentError(new Error(`Full image preload failed: ${effectiveImageUrl}`), {
                  context: `${debugContext}.onPreloadError`,
                  showToast: false,
                  logData: { url: effectiveImageUrl },
                });
                // Still try to show thumbnail
              }}
            />
          )}

          {/* Reposition mode overlays (bounds outline, zoom buttons, rotation handles) */}
          {isRepositionMode && (
            <RepositionOverlay
              displaySize={displaySize}
              imageOffset={imageOffset}
              repositionTransformStyle={repositionTransformStyle}
              repositionScale={repositionScale}
              variant={variant}
              handlesOverlayRef={handlesOverlayRef}
              onRepositionScaleChange={onRepositionScaleChange}
              onRepositionRotationChange={onRepositionRotationChange}
              handleCornerRotateStart={handleCornerRotateStart}
              handleCornerRotateMove={handleCornerRotateMove}
              handleCornerRotateEnd={handleCornerRotateEnd}
            />
          )}

          {/* Saving State Overlay */}
          {isSaving && (
            <div className={`absolute inset-0 flex items-center justify-center z-10 bg-black/50 backdrop-blur-sm ${variant === 'regular-centered' ? 'rounded' : ''}`}>
              <div className="text-center text-white bg-black/80 rounded-lg p-4 backdrop-blur-sm border border-white/20">
                <div className={`animate-spin rounded-full border-b-2 border-white mx-auto ${variant === 'mobile-stacked' ? 'h-10 w-10 mb-2' : 'h-12 w-12 mb-3'}`}></div>
                <p className={`font-medium ${variant === 'mobile-stacked' ? 'text-base' : 'text-lg'}`}>Saving flipped image...</p>
                <p className={`text-white/70 mt-1 ${variant === 'mobile-stacked' ? 'text-xs' : 'text-sm'}`}>Please wait</p>
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
};
