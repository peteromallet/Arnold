import { useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useIsMobile } from '@/shared/hooks/mobile';
import { Shot } from '@/domains/generation/types';
import { TOOL_ROUTES, travelShotUrl } from '@/shared/lib/tooling/toolRoutes';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';

interface ShotNavigationOptions {
  /** Whether to scroll to top after navigation */
  scrollToTop?: boolean;
  /** Whether to close mobile panes after navigation */
  closeMobilePanes?: boolean;
  /** Whether to replace the current history entry instead of pushing */
  replace?: boolean;
  /** Custom scroll behavior */
  scrollBehavior?: 'auto' | 'smooth';
  /** Delay before scrolling (useful for waiting for navigation to complete) */
  scrollDelay?: number;
  /** Whether this shot was just created (show loading instead of "not found" while cache syncs) */
  isNewlyCreated?: boolean;
}

interface ShotNavigationResult {
  /** Navigate to a specific shot */
  navigateToShot: (shot: Shot, options?: ShotNavigationOptions) => void;
  /** Navigate to the shot editor without a specific shot (shows shot list) */
  navigateToShotEditor: (options?: ShotNavigationOptions) => void;
  /** Navigate to the next shot in a list */
  navigateToNextShot: (shots: Shot[], currentShot: Shot, options?: ShotNavigationOptions) => boolean;
  /** Navigate to the previous shot in a list */
  navigateToPreviousShot: (shots: Shot[], currentShot: Shot, options?: ShotNavigationOptions) => boolean;
}

const DEFAULT_OPTIONS: Required<ShotNavigationOptions> = {
  scrollToTop: true,
  closeMobilePanes: true,
  replace: false,
  scrollBehavior: 'smooth',
  scrollDelay: 200,
  isNewlyCreated: false,
};

function performScroll(options: Required<ShotNavigationOptions>) {
  if (options.scrollToTop) {
    const scrollFn = () => {
      const scheduleScroll =
        typeof window.requestAnimationFrame === 'function'
          ? window.requestAnimationFrame.bind(window)
          : (callback: FrameRequestCallback) => window.setTimeout(callback, 0);

      scheduleScroll(() => {
        window.scrollTo({ top: 0, behavior: options.scrollBehavior });
        dispatchAppEvent('app:scrollToTop', { behavior: options.scrollBehavior });
      });
    };

    if (options.scrollDelay > 0) {
      setTimeout(scrollFn, options.scrollDelay);
    } else {
      scrollFn();
    }
  }
}

function closeMobilePanes(options: Required<ShotNavigationOptions>, isMobile: boolean) {
  if (options.closeMobilePanes && isMobile) {
    dispatchAppEvent('mobilePaneOpen', { side: null });
  }
}

export const useShotNavigation = (): ShotNavigationResult => {
  const navigate = useNavigate();
  const { setCurrentShotId } = useCurrentShot();
  const isMobile = useIsMobile();

  // Refs for all dependencies so callbacks are stable (empty deps).
  // Without this, every consumer gets new function references on every render,
  // breaking React.memo on downstream components and cascading re-renders.
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  const setCurrentShotIdRef = useRef(setCurrentShotId);
  setCurrentShotIdRef.current = setCurrentShotId;
  const isMobileRef = useRef(isMobile);
  isMobileRef.current = isMobile;

  const navigateToShot = useCallback((shot: Shot, options: ShotNavigationOptions = {}) => {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // NOTE: We intentionally do NOT call setCurrentShotId() here.
    // navigate() and setCurrentShotId() are not batched by React — the context
    // update renders before the router update, creating an intermediate frame
    // where currentShotId is set but location.hash is empty. useUrlSync then
    // clears currentShotId, causing a visible EDITOR → shot-list → EDITOR jolt.
    // Instead, we let the hash drive everything: useSelectedShotResolution
    // resolves shotToEdit from hashShotId + shotFromState, and useUrlSync/
    // useSyncCurrentShotId set currentShotId from the hash after navigation.
    const targetUrl = travelShotUrl(shot.id);
    navigateRef.current(targetUrl, {
      state: {
        fromShotClick: true,
        shotData: shot,
        isNewlyCreated: opts.isNewlyCreated
      },
      replace: opts.replace,
    });

    performScroll(opts);
    closeMobilePanes(opts, isMobileRef.current);
  }, []);

  const navigateToShotEditor = useCallback((options: ShotNavigationOptions = {}) => {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    setCurrentShotIdRef.current(null);

    navigateRef.current(TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES, {
      state: { fromShotClick: false },
      replace: opts.replace,
    });

    performScroll(opts);
    closeMobilePanes(opts, isMobileRef.current);
  }, []);

  const navigateToNextShot = useCallback((shots: Shot[], currentShot: Shot, options: ShotNavigationOptions = {}): boolean => {
    const currentIndex = shots.findIndex(shot => shot.id === currentShot.id);
    if (currentIndex >= 0 && currentIndex < shots.length - 1) {
      const nextShot = shots[currentIndex + 1];
      navigateToShot(nextShot, { ...options, replace: true });
      return true;
    }
    return false;
  }, [navigateToShot]);

  const navigateToPreviousShot = useCallback((shots: Shot[], currentShot: Shot, options: ShotNavigationOptions = {}): boolean => {
    const currentIndex = shots.findIndex(shot => shot.id === currentShot.id);
    if (currentIndex > 0) {
      const previousShot = shots[currentIndex - 1];
      navigateToShot(previousShot, { ...options, replace: true });
      return true;
    }
    return false;
  }, [navigateToShot]);

  return useMemo(() => ({
    navigateToShot,
    navigateToShotEditor,
    navigateToNextShot,
    navigateToPreviousShot,
  }), [navigateToShot, navigateToShotEditor, navigateToNextShot, navigateToPreviousShot]);
};
