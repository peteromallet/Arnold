import React from "react";
import { HoverScrubVideo } from "@/shared/components/media/HoverScrubVideo";
import type { GeneratedImageWithMetadata } from "../../MediaGallery/types";

interface VideoContentProps {
  image: GeneratedImageWithMetadata;
  stableDisplayUrl: string;
  stableVideoUrl: string | null;
  actualSrc: string | null;
  shouldLoad: boolean;
  imageLoaded: boolean;
  videosAsThumbnails: boolean;
  isMobile: boolean;
  enableSingleClick: boolean;
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onOpenLightbox: (image: GeneratedImageWithMetadata) => void;
  onTouchStart?: (e: React.TouchEvent) => void;
  onTouchEnd?: (e: React.TouchEvent) => void;
  onVideoError: (e?: React.SyntheticEvent) => void;
  onLoadStart: () => void;
  onLoadedData: () => void;
}

export const VideoContent: React.FC<VideoContentProps> = ({
  image,
  stableDisplayUrl,
  stableVideoUrl,
  actualSrc,
  shouldLoad,
  imageLoaded,
  videosAsThumbnails,
  isMobile,
  enableSingleClick,
  onOpenLightbox,
  onTouchStart,
  onTouchEnd,
  onVideoError,
  onLoadStart,
  onLoadedData,
}) => {
  if (videosAsThumbnails) {
    // Lightweight thumbnail mode - just show a static image for video selection panels
    return (
      <div className="absolute inset-0 w-full h-full">
        <img
          src={stableDisplayUrl || ''}
          alt={image.prompt || ''}
          className="w-full h-full object-cover cursor-pointer"
          loading="lazy"
          // Selection click is handled at the MediaGalleryItem wrapper.
          onDoubleClick={isMobile ? undefined : () => onOpenLightbox(image)}
        />
        {/* Video indicator overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/10 pointer-events-none">
          <div className="w-10 h-10 rounded-full bg-black/50 flex items-center justify-center">
            <svg className="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
      </div>
    );
  }

  // Full HoverScrubVideo mode for galleries that need scrubbing
  return (
    <>
      {/* Thumbnail overlay - stays visible until video is loaded to prevent flash */}
      {stableDisplayUrl && !imageLoaded && (
        <img
          src={stableDisplayUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover z-[1] pointer-events-none"
          loading="eager"
        />
      )}
      <HoverScrubVideo
        src={stableVideoUrl || actualSrc || ''}
        poster={stableDisplayUrl || undefined}
        preload={shouldLoad ? "auto" : "none"}
        className="absolute inset-0 w-full h-full"
        videoClassName="object-cover cursor-pointer w-full h-full"
        muted
        loop
        // Selection click is handled at the MediaGalleryItem wrapper.
        onDoubleClick={isMobile ? undefined : () => onOpenLightbox(image)}
        onTouchStart={isMobile && !enableSingleClick ? onTouchStart : undefined}
        onTouchEnd={isMobile && !enableSingleClick ? onTouchEnd : undefined}
        onVideoError={onVideoError}
        onLoadStart={onLoadStart}
        onLoadedData={onLoadedData}
      />
    </>
  );
};
