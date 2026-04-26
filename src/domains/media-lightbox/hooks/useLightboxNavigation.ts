import { useEffect, useCallback, useRef } from 'react';
import { getTopmostKnownModalOverlayType } from '@/shared/components/ui/overlay';

interface UseLightboxNavigationProps {
  onNext?: () => void;
  onPrevious?: () => void;
  onClose: () => void;
}

interface UseLightboxNavigationReturn {
  safeClose: () => void;
  activateClickShield: () => void;
}

/**
 * Hook for managing lightbox navigation
 * Handles keyboard controls (arrow keys, escape) and safe closing with click shield
 */
export const useLightboxNavigation = ({
  onNext,
  onPrevious,
  onClose,
}: UseLightboxNavigationProps): UseLightboxNavigationReturn => {
  
  // Short-lived global click shield to absorb iOS synthetic clicks after touchend
  const activateClickShield = useCallback(() => {
    try {
      const shield = document.createElement('div');
      shield.setAttribute('data-mobile-click-shield', 'true');
      shield.style.position = 'fixed';
      shield.style.top = '0';
      shield.style.left = '0';
      shield.style.right = '0';
      shield.style.bottom = '0';
      shield.style.background = 'transparent';
      shield.style.pointerEvents = 'all';
      shield.style.zIndex = '2147483647';
      shield.style.touchAction = 'none';

      const block = (ev: Event) => {
        try { ev.preventDefault(); } catch { /* intentionally ignored */ }
        try { ev.stopPropagation(); } catch { /* intentionally ignored */ }
        try { ev.stopImmediatePropagation?.(); } catch { /* intentionally ignored */ }
      };

      shield.addEventListener('click', block, true);
      shield.addEventListener('pointerdown', block, true);
      shield.addEventListener('pointerup', block, true);
      shield.addEventListener('touchstart', block, { capture: true, passive: false } as AddEventListenerOptions);
      shield.addEventListener('touchend', block, { capture: true, passive: false } as AddEventListenerOptions);

      document.body.appendChild(shield);

      window.setTimeout(() => {
        try { shield.remove(); } catch { /* intentionally ignored */ }
      }, 350);
    } catch { /* intentionally ignored */ }
  }, []);

  const safeClose = useCallback(() => {
    activateClickShield();
    onClose();
  }, [activateClickShield, onClose]);

  /**
   * Global key handler (capture phase)
   * --------------------------------------------------
   * Registered on the capture phase so it fires before any intermediate
   * stopPropagation calls (Base-UI dialog internals swallow keydown
   * during bubble phase in edit mode).
   *
   * Callbacks are stored in refs so the listener is registered once
   * and never re-attached (avoids effect thrashing when parent re-renders).
   */
  const onNextRef = useRef(onNext);
  const onPreviousRef = useRef(onPrevious);
  const onCloseRef = useRef(onClose);
  onNextRef.current = onNext;
  onPreviousRef.current = onPrevious;
  onCloseRef.current = onClose;

  useEffect(() => {
    /**
     * CAPTURE-phase handler so arrow navigation works even when something
     * in the DOM tree (e.g. Base-UI internals) calls stopPropagation on
     * the keydown event during the bubble phase.
     */
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only bail when an *actually-open modal* overlay above the lightbox wants the keys.
      // Non-modal overlays (tooltip, hover-card) must never suppress arrow/Escape here,
      // and stale modal entries that registered but haven't opened (e.g. Base-UI Select
      // mounting without data-state="open") must not either — those leave `getTopOverlay`
      // pointing at them and previously dead-locked the lightbox.
      const topModalOverlayType = getTopmostKnownModalOverlayType();
      if (topModalOverlayType && topModalOverlayType !== 'lightbox') return;

      // Don't intercept arrow keys when user is in a text field
      const active = document.activeElement;
      const isTextInput = active instanceof HTMLInputElement
        || active instanceof HTMLTextAreaElement
        || (active as HTMLElement)?.isContentEditable;

      if (e.key === 'ArrowLeft' && onPreviousRef.current && !isTextInput) {
        e.preventDefault();
        onPreviousRef.current();
      } else if (e.key === 'ArrowRight' && onNextRef.current && !isTextInput) {
        e.preventDefault();
        onNextRef.current();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
      }
    };

    document.addEventListener('keydown', handleKeyDown, true); // capture phase
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, []); // stable — callbacks read from refs

  return {
    safeClose,
    activateClickShield,
  };
};
