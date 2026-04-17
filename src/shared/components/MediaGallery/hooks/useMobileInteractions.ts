import { useCallback, useEffect, useRef } from 'react';
import { isElementWithinKnownOverlay } from '@/shared/components/ui/overlay';
import type { GeneratedImageWithMetadata } from '../types';

interface UseMobileInteractionsProps {
  isMobile: boolean;
  setMobileActiveImageId: (id: string | null) => void;
  mobilePopoverOpenImageId: string | null;
  setMobilePopoverOpenImageId: (id: string | null) => void;
  onOpenLightbox: (image: GeneratedImageWithMetadata) => void;
}

interface UseMobileInteractionsReturn {
  handleMobileTap: (image: GeneratedImageWithMetadata) => void;
}

export const useMobileInteractions = ({
  isMobile,
  setMobileActiveImageId,
  mobilePopoverOpenImageId,
  setMobilePopoverOpenImageId,
  onOpenLightbox,
}: UseMobileInteractionsProps): UseMobileInteractionsReturn => {
  const lastTouchTimeRef = useRef<number>(0);
  const lastTappedImageIdRef = useRef<string | null>(null);
  const doubleTapTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Handle mobile double-tap detection
  // Using 400ms window for snappier, more reliable double-tap detection
  const DOUBLE_TAP_WINDOW_MS = 400;
  const MIN_TAP_INTERVAL_MS = 50; // Minimum time between taps to filter out accidental multi-touch
  
  const handleMobileTap = useCallback((image: GeneratedImageWithMetadata) => {
    const currentTime = Date.now();
    const timeSinceLastTap = currentTime - lastTouchTimeRef.current;
    const lastTappedImageId = lastTappedImageIdRef.current;
    const isSameImage = lastTappedImageId === image.id;
    
    if (timeSinceLastTap < DOUBLE_TAP_WINDOW_MS && timeSinceLastTap > MIN_TAP_INTERVAL_MS && lastTouchTimeRef.current > 0 && isSameImage) {
      // This is a double-tap on the same image, clear any pending timeout and open lightbox
      if (doubleTapTimeoutRef.current) {
        clearTimeout(doubleTapTimeoutRef.current);
        doubleTapTimeoutRef.current = null;
      }
      onOpenLightbox(image);
      // Reset tap tracking to prevent triple-tap issues
      lastTouchTimeRef.current = 0;
      lastTappedImageIdRef.current = null;
    } else {
      // This is a single tap or tap on different image, set a timeout to handle it if no second tap comes
      if (doubleTapTimeoutRef.current) {
        clearTimeout(doubleTapTimeoutRef.current);
      }
      doubleTapTimeoutRef.current = setTimeout(() => {
        // Single tap (mobile): reveal action controls for this image
        // Close any existing popover if tapping a different image
        if (mobilePopoverOpenImageId && mobilePopoverOpenImageId !== image.id) {
          setMobilePopoverOpenImageId(null);
        }
        setMobileActiveImageId(image.id);
        doubleTapTimeoutRef.current = null;
      }, DOUBLE_TAP_WINDOW_MS);
      
      // Update the last tapped image and time
      lastTappedImageIdRef.current = image.id;
      lastTouchTimeRef.current = currentTime;
    }
  }, [onOpenLightbox, mobilePopoverOpenImageId, setMobilePopoverOpenImageId, setMobileActiveImageId]);

  // Close mobile popover on scroll or when clicking outside
  useEffect(() => {
    if (!isMobile || !mobilePopoverOpenImageId) return;

    const handleScroll = () => {
      setMobilePopoverOpenImageId(null);
    };

    const handleClickOutside = (event: MouseEvent) => {
      // Close if clicking outside any popover content
      const target = event.target as Element;
      if (!isElementWithinKnownOverlay(target)) {
        setMobilePopoverOpenImageId(null);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      window.removeEventListener('scroll', handleScroll);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMobile, mobilePopoverOpenImageId, setMobilePopoverOpenImageId]);

  useEffect(() => {
    return () => {
      if (doubleTapTimeoutRef.current) {
        clearTimeout(doubleTapTimeoutRef.current);
        doubleTapTimeoutRef.current = null;
      }
    };
  }, []);

  return {
    handleMobileTap,
  };
};
