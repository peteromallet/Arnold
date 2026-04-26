import { useCallback, useRef } from 'react';
import type { GeneratedImageWithMetadata } from '@/shared/components/MediaGallery/types';
import { isAdditiveSelectionEvent } from '@/shared/lib/interactions/selectionGesture';
import { captureTouchStartPoint, isTouchTapWithinThreshold } from '@/shared/lib/touch/touchGestureUtils';

interface UseItemInteractionParams {
  image: GeneratedImageWithMetadata;
  isMobile: boolean;
  mobileActiveImageId: string | null;
  enableSingleClick: boolean;
  // `modifiers` is derived from the synthetic event so callers know whether
  // the user held a multi-select modifier (Cmd / Ctrl / Shift) at click time.
  // Reading it here is race-free; reading global key state separately is not.
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onMobileTap: (image: GeneratedImageWithMetadata) => void;
}

export function useItemInteraction({
  image,
  isMobile,
  mobileActiveImageId,
  enableSingleClick,
  onImageClick,
  onMobileTap,
}: UseItemInteractionParams) {
  const touchStartPosRef = useRef<{ x: number; y: number } | null>(null);

  const handleTouchStart = useCallback((event: React.TouchEvent) => {
    captureTouchStartPoint(touchStartPosRef, event);
  }, []);

  const handleInteraction = useCallback((event: React.TouchEvent | React.MouseEvent) => {
    const path = (event.nativeEvent as Event)?.composedPath?.() as HTMLElement[] | undefined;
    const isInsideButton = path
      ? path.some((element) => (element as HTMLElement)?.tagName === 'BUTTON' || (element as HTMLElement)?.closest?.('button'))
      : Boolean((event.target as HTMLElement).closest('button'));

    const isItemActive = mobileActiveImageId === image.id;
    if (isInsideButton && isItemActive) {
      return;
    }

    if (event.type === 'touchend') {
      const isTap = isTouchTapWithinThreshold(
        touchStartPosRef,
        event as React.TouchEvent,
        10,
      );
      if (!isTap) {
        return;
      }
    }

    event.preventDefault();

    if (enableSingleClick && onImageClick) {
      // Touch events don't carry modifier keys, so multi-select is always false
      // for touch. Mouse events do — read directly from this event so the
      // handler isn't subject to the React-state race that bites global key listeners.
      const multiSelect = event.type !== 'touchend'
        && isAdditiveSelectionEvent(event as React.MouseEvent);
      onImageClick(image, { multiSelect });
      return;
    }

    if (isMobile) {
      onMobileTap(image);
    }
  }, [mobileActiveImageId, image, enableSingleClick, onImageClick, isMobile, onMobileTap]);

  return {
    handleTouchStart,
    handleInteraction,
  };
}
