import { useState, useEffect, useRef, useCallback } from 'react';
import { useIsMobile, useIsTablet } from '@/shared/hooks/mobile';
import { useLocation } from 'react-router-dom';
import { PANE_CONFIG } from '@/shared/config/panes';
import { dispatchAppEvent, useAppEventListener } from '@/shared/lib/typedEvents';
import { isElementWithinKnownOverlay } from '@/shared/components/ui/overlay';

interface UseSlidingPaneOptions {
  side: 'left' | 'right' | 'bottom' | 'top';
  isLocked: boolean;
  onToggleLock: () => void;
  additionalRefs?: React.RefObject<HTMLElement>[];
  /** External programmatic open state - when true, pane opens even if not locked */
  programmaticOpen?: boolean;
  /** Callback when pane open state changes (e.g., from hover timeout) */
  onOpenChange?: (isOpen: boolean) => void;
}

export const useSlidingPane = ({ side, isLocked, onToggleLock, additionalRefs, programmaticOpen, onOpenChange }: UseSlidingPaneOptions) => {
  const [hoverOpen, setHoverOpen] = useState(false);
  // Derive isOpen from all three sources — no competing write paths
  const isOpen = isLocked || (programmaticOpen ?? false) || hoverOpen;

  const leaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const openGracePeriodRef = useRef(false);
  const paneRef = useRef<HTMLDivElement | null>(null);
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  // On tablets, use desktop-like behavior with pane locking
  // On phones (small mobile), use simplified mobile behavior without locking
  const isSmallMobile = isMobile && !isTablet;
  const location = useLocation();

  // When locked, clear hover state so unlocking doesn't leave pane stuck open
  useEffect(() => {
    if (isLocked) {
      setHoverOpen(false);
    }
  }, [isLocked]);

  // Fire onOpenChange when derived isOpen transitions
  const prevOpenRef = useRef(isOpen);
  useEffect(() => {
    if (prevOpenRef.current !== isOpen) {
      prevOpenRef.current = isOpen;
      onOpenChange?.(isOpen);
    }
  }, [isOpen, onOpenChange]);

  const setOpen = useCallback((open: boolean) => {
    // On small phones (not tablets), don't use locks at all - just manage open state
    if (isSmallMobile) {
      setHoverOpen(open);
      return;
    }

    // Desktop and tablet behavior
    if (!open && (isLocked || programmaticOpen)) {
      // Don't allow hover-close when locked or programmatically open
      return;
    }

    setHoverOpen(open);
  }, [isLocked, programmaticOpen, isSmallMobile]);

  // Close pane on route change (small phones only)
  useEffect(() => {
    if (isSmallMobile) {
      setHoverOpen(false);
    }

  }, [location.pathname, isSmallMobile]);

  // Lock body scroll when pane is open on small phones (both temporary and locked states)
  // When locked, Layout.tsx handles creating a scrollable main content area instead
  useEffect(() => {
    if (!isSmallMobile) return;
    
    if (isOpen) {
      // Store original overflow style
      const originalOverflow = document.body.style.overflow;
      const originalTouchAction = document.body.style.touchAction;
      
      // Lock body scroll - Layout.tsx creates separate scroll containers for split view
      document.body.style.overflow = 'hidden';
      document.body.style.touchAction = 'none';
      
      return () => {
        // Restore original styles
        document.body.style.overflow = originalOverflow;
        document.body.style.touchAction = originalTouchAction;
      };
    }
  }, [isSmallMobile, isOpen]);

  // Click outside handler for small phones (only when not locked)
  // We now use BOTH touchstart and pointerdown to ensure we capture
  // all touch events BEFORE they can reach underlying elements
  useEffect(() => {
    // Don't close on click outside if pane is locked
    if (!isSmallMobile || !isOpen || isLocked) return;

    const handleClickOutside = (event: TouchEvent | MouseEvent | PointerEvent) => {
      const targetEl = event.target as HTMLElement;

      // Ignore if click is on any pane-control opener/closer
      if (targetEl.closest('[data-pane-control]')) {
        return; // allow event to proceed
      }

      // Ignore clicks on floating UI portal elements (Select, Popover, Dialog, etc.)
      // These are rendered outside the pane but should be considered "inside" for interaction purposes
      if (isElementWithinKnownOverlay(targetEl)) {
        return; // allow event to proceed, don't close pane
      }

      if (paneRef.current && !paneRef.current.contains(targetEl) && !additionalRefs?.some(ref => ref.current?.contains(targetEl))) {
        // Prevent the click from triggering underlying UI actions
        event.preventDefault();
        event.stopPropagation();
        setHoverOpen(false);
      }
    };

    // Delay subscribing to click-outside events to prevent catching stray events from open tap
    const subscribeTimeout = setTimeout(() => {
      document.addEventListener('touchstart', handleClickOutside, { capture: true, passive: false });
      document.addEventListener('pointerdown', handleClickOutside, true);
    }, 100);

    return () => {
      clearTimeout(subscribeTimeout);
      document.removeEventListener('touchstart', handleClickOutside, true);
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [isSmallMobile, isOpen, isLocked, additionalRefs]);

  // Close on dragstart anywhere (small phones)
  useEffect(() => {
    if (!isSmallMobile) return;

    const handleDragStart = () => {
      if (isOpen) {
        setHoverOpen(false);
      }
    };

    document.addEventListener('dragstart', handleDragStart);
    return () => document.removeEventListener('dragstart', handleDragStart);
  }, [isSmallMobile, isOpen]);

  // Exclusive pane coordination on small phones
  // When another pane opens, this one should close; the panes store bootstrap keeps the lock policy in sync.
  const handleMobilePaneOpen = useCallback((detail: { side: string | null }) => {
    if (!isSmallMobile) return;
    const openedSide = detail?.side ?? null;
    if (openedSide !== side && !isLocked) {
      // Another pane (or null) requested and we're not locked - close this one
      setHoverOpen(false);
    }
    // If this pane is locked, the panes store lock policy will unlock it
    // when the other pane gets locked (only one can be locked at a time on mobile).
  }, [isSmallMobile, side, isLocked]);

  useAppEventListener('mobilePaneOpen', handleMobilePaneOpen);

  const openPane = () => {
    if (leaveTimeoutRef.current) {
        clearTimeout(leaveTimeoutRef.current);
        leaveTimeoutRef.current = null;
    }

    // Suppress mouseLeave-triggered close during the open animation.
    // The tab CSS-transitions to a new position, which moves it away from
    // the cursor and fires mouseLeave before the user can hover the surface.
    openGracePeriodRef.current = true;
    setTimeout(() => { openGracePeriodRef.current = false; }, PANE_CONFIG.timing.ANIMATION_DURATION);

    if (isSmallMobile) {
      // Dispatch global event so other panes close immediately
      dispatchAppEvent('mobilePaneOpen', { side });
    }
    setOpen(true);
  }

  const handlePaneLeave = () => {
    // No hover behavior on small phones
    if (isSmallMobile) return;

    if (isLocked) return;
    // Ignore leaves during the open animation grace period — the tab
    // CSS-transitions away from the cursor which fires a spurious mouseLeave.
    if (openGracePeriodRef.current) return;
    leaveTimeoutRef.current = setTimeout(() => {
      setOpen(false);
    }, PANE_CONFIG.timing.HOVER_DELAY);
  };

  const handlePaneEnter = () => {
    // No hover behavior on small phones
    if (isSmallMobile) return;

    if (isLocked) return;
    if (leaveTimeoutRef.current) {
      clearTimeout(leaveTimeoutRef.current);
      leaveTimeoutRef.current = null;
    }
  };

  const toggleLock = (force?: boolean) => {
    // Clear any pending leave timeout so it can't race with the lock state change
    if (leaveTimeoutRef.current) {
      clearTimeout(leaveTimeoutRef.current);
      leaveTimeoutRef.current = null;
    }

    // Allow locking on all devices including mobile
    if (force !== undefined) {
      // Force to specific state - used by UI buttons
      if (force !== isLocked) {
        onToggleLock();
      }
    } else {
      // Toggle current state
      onToggleLock();
    }
  };
  
  useEffect(() => {
    // Cleanup timeout on unmount
    return () => {
      if (leaveTimeoutRef.current) {
        clearTimeout(leaveTimeoutRef.current);
      }
    };
  }, []);

  const getTransformClass = () => {
    const isVisible = isOpen;

    const transformClass = (() => {
      switch (side) {
        case 'left':
          return isVisible ? 'translate-x-0' : '-translate-x-full';
        case 'right':
          return isVisible ? 'translate-x-0' : 'translate-x-full';
        case 'bottom':
          return isVisible ? 'translate-y-0' : 'translate-y-full';
        case 'top':
          return isVisible ? 'translate-y-0' : '-translate-y-full';
        default:
          return '';
      }
    })();

    return transformClass;
  };

  const paneProps = {
    ref: paneRef,
    onMouseEnter: handlePaneEnter,
    onMouseLeave: handlePaneLeave,
  };

  // Should show a backdrop overlay that captures all touches
  // Only on small phones when pane is open but NOT locked
  const showBackdrop = isSmallMobile && isOpen && !isLocked;

  return {
    isLocked, // Return actual lock state on all devices
    isOpen,
    toggleLock,
    openPane,
    paneProps,
    transformClass: getTransformClass(),
    handlePaneEnter,
    handlePaneLeave,
    isMobile, // Still return isMobile for backward compatibility
    showBackdrop, // Whether to show backdrop overlay for tap-outside-to-close
    closePane: () => setHoverOpen(false), // Function to close the pane (for backdrop onClick)
  };
}; 
