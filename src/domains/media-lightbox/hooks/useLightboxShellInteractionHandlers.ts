import { useRef } from 'react';
import {
  isFloatingOverlayElement,
  shouldAllowTouchThrough,
} from '@/shared/lib/interactions/elementPolicy';
import { isElementWithinTopmostOverlay } from '@/shared/components/ui/overlay';

interface UseLightboxShellInteractionHandlersArgs {
  hasCanvasOverlay: boolean;
  isRepositionMode: boolean;
  isMobile: boolean;
  onClose: () => void;
  popupRef: React.RefObject<HTMLElement | null>;
}

export function useLightboxShellInteractionHandlers({
  hasCanvasOverlay,
  isRepositionMode,
  isMobile,
  onClose,
  popupRef,
}: UseLightboxShellInteractionHandlersArgs) {
  const pointerDownTargetRef = useRef<EventTarget | null>(null);
  const bgPointerDownTargetRef = useRef<EventTarget | null>(null);
  const isCurrentLightboxTopmost = () => {
    const popup = popupRef.current;
    return !popup || isElementWithinTopmostOverlay(popup);
  };

  const handleOverlayPointerDown = (e: React.PointerEvent) => {
    pointerDownTargetRef.current = e.target;

    if (!isCurrentLightboxTopmost()) {
      return;
    }

    e.preventDefault();
    e.stopPropagation();
    if (e.nativeEvent && typeof e.nativeEvent.stopImmediatePropagation === 'function') {
      e.nativeEvent.stopImmediatePropagation();
    }
  };

  const handleOverlayPointerUp = (e: React.PointerEvent) => {
    if (!isCurrentLightboxTopmost()) {
      return;
    }

    if (!isRepositionMode) {
      const clickStartedOnOverlay = pointerDownTargetRef.current === e.currentTarget;
      const clickEndedOnOverlay = e.target === e.currentTarget;

      if (clickStartedOnOverlay && clickEndedOnOverlay) {
        onClose();
      }
    }

    pointerDownTargetRef.current = null;

    e.preventDefault();
    e.stopPropagation();
    if (e.nativeEvent && typeof e.nativeEvent.stopImmediatePropagation === 'function') {
      e.nativeEvent.stopImmediatePropagation();
    }
  };

  const handleBgPointerDownCapture = (e: React.PointerEvent) => {
    bgPointerDownTargetRef.current = e.target;
  };

  const handleBgClickCapture = (e: React.MouseEvent) => {
    const downTarget = bgPointerDownTargetRef.current as HTMLElement | null;
    const upTarget = e.target as HTMLElement;
    bgPointerDownTargetRef.current = null;

    if (!isCurrentLightboxTopmost()) return;
    if (isRepositionMode) return;

    if (
      downTarget?.hasAttribute?.('data-lightbox-bg') &&
      upTarget.hasAttribute?.('data-lightbox-bg')
    ) {
      e.stopPropagation();
      onClose();
    }
  };

  const handleContentPointerDown = (e: React.PointerEvent) => {
    const target = e.target as Element;
    if (isFloatingOverlayElement(target)) {
      return;
    }
    e.stopPropagation();
  };

  const handleContentClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleTouchEvent = (e: React.TouchEvent) => {
    if (shouldAllowTouchThrough(e.target as HTMLElement, { hasCanvasOverlay })) return;
    if (isMobile) e.stopPropagation();
  };

  const handleTouchCancel = (e: React.TouchEvent) => {
    if (!isCurrentLightboxTopmost()) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.nativeEvent && typeof e.nativeEvent.stopImmediatePropagation === 'function') {
      e.nativeEvent.stopImmediatePropagation();
    }
  };

  return {
    handleOverlayPointerDown,
    handleOverlayPointerUp,
    handleBgPointerDownCapture,
    handleBgClickCapture,
    handleContentPointerDown,
    handleContentClick,
    handleTouchEvent,
    handleTouchCancel,
  };
}
