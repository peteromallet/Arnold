import { useCallback, useEffect, useRef, useMemo } from 'react';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { TRAILING_ENDPOINT_KEY, sortPositionEntries } from '../../utils/timeline-utils';

interface UseTrailingEndpointProps {
  /** Drag-aware positions from the orchestrator */
  currentPositions: Map<string, number>;
  /** Source-of-truth trailing end frame (derived from framePositions before orchestrator) */
  trailingEndFrame: number | undefined;
  /** Computed trailing video URL (from synchronous computation before orchestrator) */
  computedTrailingVideoUrl: string | null;
  /** Callback-detected trailing video URL (owned by caller, lifted before orchestrator) */
  callbackTrailingVideoUrl: string | null;
  /** Setter for callbackTrailingVideoUrl — caller clears it when last image changes */
  setCallbackTrailingVideoUrl: (url: string | null) => void;
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
}

interface UseTrailingEndpointReturn {
  /** URL of the trailing video (computed or callback) */
  trailingVideoUrl: string | null;
  /** Extract the final frame from a trailing video and add as next image */
  handleExtractFinalFrame: () => Promise<void>;
  /** Image-only positions from currentPositions (excluding trailing endpoint) */
  imagePositions: Map<string, number>;
}

/**
 * useTrailingEndpoint - Manages trailing endpoint runtime state:
 * video URL tracking, frame extraction, and image-only positions.
 *
 * Pre-orchestrator values (trailingEndFrame, hasExistingTrailingVideo,
 * handleTrailingEndFrameChange) are computed inline in TimelineContainer
 * since they only depend on framePositions and must be available before
 * the orchestrator hook runs.
 *
 * callbackTrailingVideoUrl is also owned by the caller (before the orchestrator)
 * so it can influence fullMax via hasCallbackTrailingVideo. This hook receives it as
 * a prop and handles the clear-on-last-image-change effect.
 *
 * This hook handles post-orchestrator logic that needs currentPositions:
 * - Image-only positions (excluding trailing endpoint key)
 * - Last-image tracking to clear stale trailing video URLs
 * - Frame extraction from trailing videos
 */
export function useTrailingEndpoint({
  currentPositions,
  trailingEndFrame,
  computedTrailingVideoUrl,
  callbackTrailingVideoUrl,
  setCallbackTrailingVideoUrl,
  onFileDrop,
}: UseTrailingEndpointProps): UseTrailingEndpointReturn {
  const trailingVideoUrl = computedTrailingVideoUrl || callbackTrailingVideoUrl;

  // Image-only positions (excluding trailing endpoint) for sorts that need the "last image"
  const imagePositions = useMemo(() => {
    const filtered = new Map(currentPositions);
    filtered.delete(TRAILING_ENDPOINT_KEY);
    return filtered;
  }, [currentPositions]);

  // Track the last image ID to detect when it changes (new image added at end)
  // When the last image changes, clear trailingVideoUrl to prevent showing stale video
  // Note: trailingEndFrame is handled by derivedEndFrame validation (end_frame > lastImageFrame)
  const lastImageIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (imagePositions.size === 0) return;

    // Find the current last image (highest frame position)
    const sortedEntries = sortPositionEntries(imagePositions);
    const currentLastImageId = sortedEntries[sortedEntries.length - 1]?.[0] || null;

    // If the last image changed, clear trailing video URL
    if (lastImageIdRef.current !== null &&
        currentLastImageId !== lastImageIdRef.current) {
      if (trailingVideoUrl) {
        setCallbackTrailingVideoUrl(null);
      }
    }

    lastImageIdRef.current = currentLastImageId;
  }, [imagePositions, trailingVideoUrl, setCallbackTrailingVideoUrl]);

  // Handler to extract final frame from trailing video and add as next image
  const handleExtractFinalFrame = useCallback(async () => {
    if (!trailingVideoUrl || !onFileDrop) return;

    try {
      // Create video element to extract frame
      const video = document.createElement('video');
      video.crossOrigin = 'anonymous';
      video.muted = true;
      video.playsInline = true;
      video.preload = 'auto';
      video.src = trailingVideoUrl;

      await new Promise<void>((resolve, reject) => {
        video.onloadedmetadata = () => resolve();
        video.onerror = () => reject(new Error('Failed to load video'));
        setTimeout(() => reject(new Error('Video load timeout')), 10000);
      });

      // Seek to the last frame (duration - small epsilon)
      video.currentTime = Math.max(0, video.duration - 0.01);

      await new Promise<void>((resolve) => {
        video.onseeked = () => resolve();
        setTimeout(resolve, 2000);
      });

      // Extract frame to canvas
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Failed to get canvas context');

      ctx.drawImage(video, 0, 0);

      // Convert to blob
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error('Failed to create blob'))),
          'image/png',
          1.0
        );
      });

      // Create File object
      const file = new File([blob], `extracted-frame-${Date.now()}.png`, { type: 'image/png' });

      // Calculate target frame (after the trailing endpoint)
      const sortedPositions = [...currentPositions.values()].sort((a, b) => a - b);
      const lastImageFrame = sortedPositions[sortedPositions.length - 1] ?? 0;
      const effectiveEndFrame = trailingEndFrame ?? (lastImageFrame + 17);
      const targetFrame = effectiveEndFrame + 5; // Add small gap after endpoint

      // Drop the file at the target position
      await onFileDrop([file], targetFrame);

      // Note: The trailing segment state will be automatically cleared by the useEffect
      // that watches for last image changes

      // Clean up
      video.src = '';
    } catch (error) {
      normalizeAndPresentError(error, { context: 'extractAndDropFinalFrame' });
      toast.error('Failed to extract frame from video');
    }
  }, [trailingVideoUrl, onFileDrop, currentPositions, trailingEndFrame]);

  return {
    trailingVideoUrl,
    handleExtractFinalFrame,
    imagePositions,
  };
}
