/**
 * Hook for managing lightbox transition overlay state.
 * Prevents flash when navigating between different lightbox types (image ↔ segment).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { hasKnownModalOverlay } from '@/shared/components/ui/overlay';

interface UseLightboxTransitionReturn {
  /** Whether a transition is currently in progress */
  isLightboxTransitioning: boolean;
  /** Ref for the transition overlay element */
  transitionOverlayRef: React.RefObject<HTMLDivElement>;
  /** Complete a transition and clean up shared document state. */
  completeTransition: (delayMs?: number) => void;
  /** Execute navigation with transition overlay to prevent flash */
  navigateWithTransition: (doNavigation: () => void) => void;
}

export function useLightboxTransition(): UseLightboxTransitionReturn {
  // Track lightbox transitions to keep overlay visible during navigation
  const [isLightboxTransitioning, setIsLightboxTransitioning] = useState(false);

  // Ref for synchronous overlay control (React state updates are async, causing flash)
  const transitionOverlayRef = useRef<HTMLDivElement>(null);

  // Show overlay synchronously via ref (bypasses React's async state batching)
  const showTransitionOverlay = useCallback(() => {
    if (transitionOverlayRef.current) {
      transitionOverlayRef.current.style.display = 'block';
      transitionOverlayRef.current.style.opacity = '1';
    }
    setIsLightboxTransitioning(true);
  }, []);

  const hideTransitionOverlay = useCallback(() => {
    if (transitionOverlayRef.current) {
      // Fade out smoothly over 150ms
      transitionOverlayRef.current.style.transition = 'opacity 150ms ease-out';
      transitionOverlayRef.current.style.opacity = '0';
      // Hide after fade completes
      setTimeout(() => {
        if (transitionOverlayRef.current) {
          transitionOverlayRef.current.style.display = 'none';
          transitionOverlayRef.current.style.transition = '';
        }
      }, 150);
    }
    setIsLightboxTransitioning(false);
  }, []);

  const cleanupTransitionArtifacts = useCallback(() => {
    document.body.classList.remove('lightbox-transitioning');
    if (
      document.body.style.overflow === 'hidden'
      && !hasKnownModalOverlay()
    ) {
      document.body.style.overflow = '';
    }
  }, []);

  const completeTransition = useCallback((delayMs = 0) => {
    const run = () => {
      hideTransitionOverlay();
      cleanupTransitionArtifacts();
    };

    if (delayMs > 0) {
      setTimeout(run, delayMs);
      return;
    }

    run();
  }, [cleanupTransitionArtifacts, hideTransitionOverlay]);

  // Helper to navigate with transition overlay - prevents flash when component type changes
  // Shows overlay synchronously, waits for paint via double-rAF, then executes navigation
  const navigateWithTransition = useCallback((doNavigation: () => void) => {
    showTransitionOverlay();
    document.body.classList.add('lightbox-transitioning');
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        doNavigation();
      });
    });
  }, [showTransitionOverlay]);

  // Safety cleanup: always remove the class when transition state is cleared
  useEffect(() => {
    if (!isLightboxTransitioning) {
      cleanupTransitionArtifacts();
    }
  }, [cleanupTransitionArtifacts, isLightboxTransitioning]);

  // Safety timeout: remove overlay after 500ms max to prevent it getting stuck
  useEffect(() => {
    if (isLightboxTransitioning) {
      const safetyTimer = setTimeout(() => {
        completeTransition();
      }, 500);
      return () => clearTimeout(safetyTimer);
    }
  }, [completeTransition, isLightboxTransitioning]);

  return {
    isLightboxTransitioning,
    transitionOverlayRef,
    completeTransition,
    navigateWithTransition,
  };
}
