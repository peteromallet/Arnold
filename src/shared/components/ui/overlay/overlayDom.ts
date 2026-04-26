import { useOverlayStackApi } from '@/shared/state/overlayStack';

export const REGISTERED_OVERLAY_SELECTOR = '[data-overlay-stack-id]';

export const OVERLAY_POPUP_SELECTOR = [
  '[data-overlay-stack-kind="popup"]',
  '[data-lightbox-popup]',
  '[data-dialog-content]',
  '[data-popup]',
  '[role="listbox"]',
  '[role="menu"]',
].join(', ');

export const OVERLAY_SURFACE_SELECTOR = [
  REGISTERED_OVERLAY_SELECTOR,
  '[data-lightbox-popup]',
  '[data-dialog-content]',
  '[data-dialog-backdrop]',
  '[data-popup]',
  '[role="listbox"]',
  '[role="menu"]',
  '[data-side]',
].join(', ');

function isBrowser(): boolean {
  return typeof document !== 'undefined' && typeof window !== 'undefined';
}

function isHTMLElement(value: unknown): value is HTMLElement {
  return value instanceof HTMLElement;
}

function isVisible(element: HTMLElement): boolean {
  const style = window.getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden';
}

function getComputedZIndex(element: HTMLElement): number {
  const zIndex = Number.parseInt(window.getComputedStyle(element).zIndex || '0', 10);
  return Number.isFinite(zIndex) ? zIndex : 0;
}

function getBestOverlayElement(
  popup: HTMLElement | null,
  fallbackElements: readonly HTMLElement[],
): HTMLElement | null {
  if (popup) {
    return popup;
  }

  return fallbackElements.find(isHTMLElement) ?? null;
}

/** Returns the closest known overlay popup/container ancestor for portal attachment. */
export function getClosestOverlayContainer(element: Element | null): HTMLElement | null {
  if (!element || !(element instanceof HTMLElement)) {
    return null;
  }

  const markerMatch = element.closest<HTMLElement>(OVERLAY_POPUP_SELECTOR);
  if (markerMatch) {
    return markerMatch;
  }

  const overlay = useOverlayStackApi().getState().getTopmostOverlayContainingElement(element);
  if (!overlay) {
    return null;
  }

  const popup = overlay.elements.find(
    (candidate) => candidate.dataset.overlayStackKind === 'popup',
  ) ?? null;
  return getBestOverlayElement(popup, overlay.elements);
}

/** Returns the topmost registered overlay type, or null when no overlay is active. */
export function getTopmostKnownOverlayType(): string | null {
  return useOverlayStackApi().getState().getTopOverlay()?.type ?? null;
}

/**
 * Returns the topmost *actually-open modal* overlay type, or null when no modal overlay is open.
 * Use this (not `getTopmostKnownOverlayType`) for keyboard/focus gating: non-modal overlays
 * (tooltips, hover-cards) and stale/unopened modal entries should never suppress key handling
 * on the underlying surface.
 */
export function getTopmostKnownModalOverlayType(): string | null {
  return useOverlayStackApi().getState().getTopModalOverlay()?.type ?? null;
}

/** Returns true when a registered modal overlay is currently active. */
export function hasKnownModalOverlay(): boolean {
  return useOverlayStackApi().getState().getTopModalOverlay() !== null;
}

/** Returns true when the target is inside any known overlay surface or popup marker. */
export function isElementWithinKnownOverlay(element: Element | null): boolean {
  if (!element) {
    return false;
  }

  if (useOverlayStackApi().getState().isElementWithinAnyOverlay(element)) {
    return true;
  }

  return element instanceof HTMLElement && element.closest(OVERLAY_SURFACE_SELECTOR) !== null;
}

/** Returns the current topmost known overlay surface, preferring registered stack entries. */
export function getTopmostKnownOverlaySurface(): HTMLElement | null {
  if (!isBrowser()) {
    return null;
  }

  const topOverlay = useOverlayStackApi().getState().getTopOverlay();
  if (topOverlay) {
    const popup = topOverlay.elements.find(
      (candidate) => candidate.dataset.overlayStackKind === 'popup',
    ) ?? null;
    const bestRegistered = getBestOverlayElement(popup, topOverlay.elements);
    if (bestRegistered) {
      return bestRegistered;
    }
  }

  const elements = Array.from(document.querySelectorAll<HTMLElement>(OVERLAY_SURFACE_SELECTOR))
    .filter(isVisible);

  if (elements.length === 0) {
    return null;
  }

  return elements.reduce<HTMLElement | null>((top, element) => {
    if (!top) {
      return element;
    }

    return getComputedZIndex(element) >= getComputedZIndex(top) ? element : top;
  }, null);
}

/** Returns true when the given element belongs to the current topmost known overlay. */
export function isElementWithinTopmostOverlay(element: Element | null): boolean {
  if (!element) {
    return false;
  }

  const stackApi = useOverlayStackApi();
  const topOverlay = stackApi.getState().getTopOverlay();
  const containingOverlay = stackApi.getState().getTopmostOverlayContainingElement(element);
  if (topOverlay && containingOverlay) {
    return topOverlay.id === containingOverlay.id;
  }

  const topmostSurface = getTopmostKnownOverlaySurface();
  if (!topmostSurface || !(element instanceof HTMLElement)) {
    return false;
  }

  return topmostSurface === element || topmostSurface.contains(element);
}

/** Returns true for floating overlay elements used by current marker-based callers during M2. */
export function isFloatingOverlayElement(target: Element | null): boolean {
  return target instanceof HTMLElement && target.closest(OVERLAY_SURFACE_SELECTOR) !== null;
}
