import React from "react";
import { AlertTriangle } from "lucide-react";
import { cn } from '@/shared/components/ui/contracts/cn';
import type { GeneratedImageWithMetadata } from "../../MediaGallery/types";

interface ImageContentProps {
  image: GeneratedImageWithMetadata;
  index: number;
  actualSrc: string | null;
  imageLoaded: boolean;
  imageLoadError: boolean;
  progressiveEnabled: boolean;
  isThumbShowing: boolean;
  isFullLoaded: boolean;
  progressiveRef: React.Ref<HTMLImageElement>;
  isMobile: boolean;
  enableSingleClick?: boolean;
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onOpenLightbox: (image: GeneratedImageWithMetadata) => void;
  onImageLoad: () => void;
  onImageError: (e?: React.SyntheticEvent) => void;
  onRetry: () => void;
  setImageLoading: (loading: boolean) => void;
}

export const ImageContent: React.FC<ImageContentProps> = ({
  image,
  index,
  actualSrc,
  imageLoaded,
  imageLoadError,
  progressiveEnabled,
  isThumbShowing,
  isFullLoaded,
  progressiveRef,
  isMobile,
  onOpenLightbox,
  onImageLoad,
  onImageError,
  onRetry,
  setImageLoading,
}) => {
  if (imageLoadError) {
    return (
      <div className="absolute inset-0 w-full h-full flex items-center justify-center bg-gray-100 text-gray-500">
        <div className="text-center">
          <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p className="text-xs">Failed to load image</p>
          <button
            onClick={onRetry}
            className="text-xs underline hover:no-underline mt-1"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Show image once it's loaded, regardless of shouldLoad state */}
      {actualSrc && imageLoaded && (
        <img
          ref={progressiveRef}
          src={actualSrc}
          alt={image.prompt || `Generated image ${index + 1}`}
          className={cn(
            "absolute inset-0 w-full h-full object-cover group-hover:opacity-80 transition-all duration-300",
            progressiveEnabled && isThumbShowing && "opacity-90",
            progressiveEnabled && isFullLoaded && "opacity-100"
          )}
          // Single-click selection is handled at the MediaGalleryItem wrapper
          // via pointerdown/pointerup with manual movement tracking — the
          // wrapper is `draggable` and the browser eats native clicks at small
          // movement thresholds. Only `onDoubleClick` stays here.
          onDoubleClick={isMobile ? undefined : () => onOpenLightbox(image)}
          draggable={false}
          style={{ cursor: 'pointer' }}
        />
      )}

      {/* Hidden image for background loading - only when image hasn't loaded yet */}
      {actualSrc && !imageLoaded && (
        <img
          src={actualSrc}
          alt={image.prompt || `Generated image ${index + 1}`}
          style={{ display: 'none' }}
          onError={onImageError}
          onLoad={onImageLoad}
          onLoadStart={() => setImageLoading(true)}
          onAbort={() => setImageLoading(false)}
        />
      )}

      {/* Show skeleton only while the media is still loading */}
      {!imageLoaded && (
        <div className="absolute inset-0 w-full h-full flex items-center justify-center bg-muted/30 animate-pulse pointer-events-none">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-gray-400"></div>
        </div>
      )}
    </>
  );
};
