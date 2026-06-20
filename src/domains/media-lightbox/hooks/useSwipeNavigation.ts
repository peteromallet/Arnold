import { useState, useRef, useCallback } from 'react';
import type { BasicPointerHandlers } from '@/shared/types/pointerHandlers';

/**
 * Horizontal pointer-swipe navigation with edge resistance and scroll-safe gesture locking.
 */

interface UseSwipeNavigationProps {
  /** Called when user swipes left (navigate to next) */
  onSwipeLeft?: () => void;
  /** Called when user swipes right (navigate to previous) */
  onSwipeRight?: () => void;
  /** Disable swipe gestures entirely */
  disabled?: boolean;
  /** Minimum distance in pixels to trigger navigation (default: 50) */
  threshold?: number;
  /** Minimum velocity (px/ms) for quick flick gestures (default: 0.3) */
  velocityThreshold?: number;
  /** Whether there's a next item (affects elastic resistance) */
  hasNext?: boolean;
  /** Whether there's a previous item (affects elastic resistance) */
  hasPrevious?: boolean;
  /** Maximum offset for elastic resistance when at edge (default: 80) */
  maxElasticOffset?: number;
}

interface UseSwipeNavigationReturn {
  /** Handlers to spread on the swipeable element */
  swipeHandlers: BasicPointerHandlers;
  /** Current horizontal offset for visual feedback (in pixels) */
  swipeOffset: number;
  /** Whether the user is actively swiping */
  isSwiping: boolean;
}

interface SwipeState {
  startX: number;
  startY: number;
  startTime: number;
  currentX: number;
  pointerId: number;
  isLocked: boolean; // Once we determine direction, lock it
  isHorizontal: boolean | null; // null = undetermined, true = horizontal, false = vertical
}

function isInteractiveElement(el: HTMLElement | null): boolean {
  const interactiveTags = ['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'A', 'VIDEO', 'CANVAS'];
  const interactiveRoles = ['button', 'slider', 'textbox', 'link', 'scrollbar'];
  
  let current: HTMLElement | null = el;
  while (current) {
    if (interactiveTags.includes(current.tagName)) {
      return true;
    }

    const role = current.getAttribute('role');
    if (role && interactiveRoles.includes(role)) {
      return true;
    }

    if (current.getAttribute('data-no-swipe') === 'true') {
      return true;
    }

    if (current.getAttribute('data-scrollable') === 'true') {
      return true;
    }

    const style = window.getComputedStyle(current);
    if (
      (style.overflowY === 'scroll' || style.overflowY === 'auto') &&
      current.scrollHeight > current.clientHeight
    ) {
      return true;
    }

    if (current.tagName === 'CANVAS') {
      return true;
    }

    if (current.getAttribute('data-scroll-area-viewport')) {
      return true;
    }

    current = current.parentElement;
  }

  return false;
}

export function useSwipeNavigation({
  onSwipeLeft,
  onSwipeRight,
  disabled = false,
  threshold = 50,
  velocityThreshold = 0.3,
  hasNext = true,
  hasPrevious = true,
  maxElasticOffset = 80,
}: UseSwipeNavigationProps): UseSwipeNavigationReturn {
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const swipeStateRef = useRef<SwipeState | null>(null);

  const applyElasticResistance = useCallback((deltaX: number): number => {
    if (deltaX > 0 && !hasPrevious) {
      return Math.sign(deltaX) * Math.min(maxElasticOffset, Math.abs(deltaX) * 0.3);
    }

    if (deltaX < 0 && !hasNext) {
      return Math.sign(deltaX) * Math.min(maxElasticOffset, Math.abs(deltaX) * 0.3);
    }

    const maxNormalOffset = 150;
    if (Math.abs(deltaX) > maxNormalOffset) {
      const excess = Math.abs(deltaX) - maxNormalOffset;
      return Math.sign(deltaX) * (maxNormalOffset + excess * 0.2);
    }
    
    return deltaX;
  }, [hasNext, hasPrevious, maxElasticOffset]);
  
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (disabled) return;
    if (!e.isPrimary) return;

    const target = e.target as HTMLElement;
    if (isInteractiveElement(target)) {
      return;
    }
    
    swipeStateRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startTime: Date.now(),
      currentX: e.clientX,
      pointerId: e.pointerId,
      isLocked: false,
      isHorizontal: null,
    };

    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      // Pointer capture can fail if the element is no longer active.
    }
  }, [disabled]);
  
  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    const state = swipeStateRef.current;
    if (!state || !e.isPrimary || state.pointerId !== e.pointerId) return;
    
    const deltaX = e.clientX - state.startX;
    const deltaY = e.clientY - state.startY;
    const absDeltaX = Math.abs(deltaX);
    const absDeltaY = Math.abs(deltaY);

    if (!state.isLocked && (absDeltaX > 10 || absDeltaY > 10)) {
      state.isHorizontal = absDeltaX > absDeltaY * 0.8;
      state.isLocked = true;

      if (!state.isHorizontal) {
        swipeStateRef.current = null;
        setSwipeOffset(0);
        setIsSwiping(false);
        try {
          (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
        } catch { /* intentionally ignored */ }
        return;
      }
    }

    if (state.isLocked && state.isHorizontal) {
      e.preventDefault();
      state.currentX = e.clientX;
      const resistedOffset = applyElasticResistance(deltaX);
      setSwipeOffset(resistedOffset);
      setIsSwiping(true);
    }
  }, [applyElasticResistance]);
  
  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    const state = swipeStateRef.current;
    if (!state || !e.isPrimary || state.pointerId !== e.pointerId) return;
    
    const deltaX = e.clientX - state.startX;
    const duration = Math.max(Date.now() - state.startTime, 1);
    const velocity = Math.abs(deltaX) / duration;
    const absDeltaX = Math.abs(deltaX);

    if (state.isLocked && state.isHorizontal) {
      const metDistanceThreshold = absDeltaX >= threshold;
      const metVelocityThreshold = velocity >= velocityThreshold && absDeltaX > 20;

      if (metDistanceThreshold || metVelocityThreshold) {
        if (deltaX < 0 && hasNext) {
          onSwipeLeft?.();
        } else if (deltaX > 0 && hasPrevious) {
          onSwipeRight?.();
        }
      }
    }

    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch { /* intentionally ignored */ }

    swipeStateRef.current = null;
    setSwipeOffset(0);
    setIsSwiping(false);
  }, [threshold, velocityThreshold, hasNext, hasPrevious, onSwipeLeft, onSwipeRight]);
  
  const handlePointerCancel = useCallback((e: React.PointerEvent) => {
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch { /* intentionally ignored */ }

    swipeStateRef.current = null;
    setSwipeOffset(0);
    setIsSwiping(false);
  }, []);
  
  return {
    swipeHandlers: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMove,
      onPointerUp: handlePointerUp,
      onPointerCancel: handlePointerCancel,
    },
    swipeOffset,
    isSwiping,
  };
}
