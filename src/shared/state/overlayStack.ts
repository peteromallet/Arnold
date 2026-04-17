import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore } from 'zustand/vanilla';

export interface OverlayStackOpenInput {
  id: string;
  type: string;
  modal?: boolean;
  restoreFocusTo?: HTMLElement | null;
  elements?: Iterable<Element | null | undefined>;
}

export interface OverlayStackUpdateInput {
  type?: string;
  modal?: boolean;
  restoreFocusTo?: HTMLElement | null;
  elements?: Iterable<Element | null | undefined>;
}

export interface OverlayStackEntry {
  id: string;
  type: string;
  modal: boolean;
  restoreFocusTo: HTMLElement | null;
  elements: readonly HTMLElement[];
}

export interface OverlayStackState {
  overlays: OverlayStackEntry[];
  /** Registers or re-registers an overlay at the top of the ordering stack. */
  pushOverlay: (input: OverlayStackOpenInput) => void;
  /** Updates a registered overlay without changing its ordering position. */
  updateOverlay: (id: string, patch: OverlayStackUpdateInput) => void;
  /** Unregisters an overlay and applies any pending cleanup side effects. */
  popOverlay: (id: string) => void;
  /** Returns the current topmost overlay, regardless of modality. */
  getTopOverlay: () => OverlayStackEntry | null;
  /** Returns the current topmost modal overlay, if one is registered. */
  getTopModalOverlay: () => OverlayStackEntry | null;
  /** Returns true when the given overlay is the topmost registered overlay. */
  isOverlayTopmost: (id: string) => boolean;
  /** Returns true when the given overlay is the topmost modal overlay. */
  isTopmostModalOverlay: (id: string) => boolean;
  /** Returns the overlay's 1-based stack layer, or null when not registered. */
  getOverlayLayer: (id: string) => number | null;
  /** Returns true when the element is the overlay or a descendant of any tracked overlay element. */
  overlayContainsElement: (id: string, element: Element | null) => boolean;
  /** Returns true when any overlay contains the given element. */
  isElementWithinAnyOverlay: (element: Element | null) => boolean;
  /** Returns the topmost overlay containing the given element, if one exists. */
  getTopmostOverlayContainingElement: (element: Element | null) => OverlayStackEntry | null;
}

type OverlayStackSnapshot = Pick<OverlayStackState, 'overlays'>;

let bodyPointerEventsSnapshot: string | null = null;

function isBrowser(): boolean {
  return typeof document !== 'undefined';
}

function isHTMLElement(value: unknown): value is HTMLElement {
  return value instanceof HTMLElement;
}

function normalizeElements(
  elements?: Iterable<Element | null | undefined>,
): readonly HTMLElement[] {
  if (!elements) {
    return [];
  }

  const nextElements: HTMLElement[] = [];
  for (const element of elements) {
    if (!isHTMLElement(element) || nextElements.includes(element)) {
      continue;
    }
    nextElements.push(element);
  }

  return nextElements;
}

function getTopOverlay(overlays: readonly OverlayStackEntry[]): OverlayStackEntry | null {
  return overlays.at(-1) ?? null;
}

function isOverlayActuallyOpen(overlay: OverlayStackEntry): boolean {
  if (overlay.elements.length === 0) {
    return false;
  }
  return overlay.elements.some((element) => {
    const state = element.getAttribute('data-state');
    if (state === 'closed') return false;
    if (element.hasAttribute('data-open')) return true;
    if (state === 'open') return true;
    // Fallback for overlays without base-ui open/close state markers:
    // treat as open only when rendered with non-zero box.
    return element.offsetParent !== null || element.getClientRects().length > 0;
  });
}

function getTopModalOverlay(overlays: readonly OverlayStackEntry[]): OverlayStackEntry | null {
  for (let index = overlays.length - 1; index >= 0; index -= 1) {
    const overlay = overlays[index];
    if (overlay.modal && isOverlayActuallyOpen(overlay)) {
      return overlay;
    }
  }

  return null;
}

function canRestoreFocusTo(element: HTMLElement | null): element is HTMLElement {
  return isHTMLElement(element) && element.isConnected && typeof element.focus === 'function';
}

function restoreFocus(element: HTMLElement | null): void {
  if (!canRestoreFocusTo(element)) {
    return;
  }

  queueMicrotask(() => {
    if (!canRestoreFocusTo(element)) {
      return;
    }

    try {
      element.focus({ preventScroll: true });
    } catch {
      element.focus();
    }
  });
}

function syncBodyPointerEvents(
  previousOverlays: readonly OverlayStackEntry[],
  nextOverlays: readonly OverlayStackEntry[],
): void {
  if (!isBrowser()) {
    return;
  }

  const previousTopModal = getTopModalOverlay(previousOverlays);
  const nextTopModal = getTopModalOverlay(nextOverlays);

  if (!previousTopModal && nextTopModal) {
    bodyPointerEventsSnapshot = document.body.style.pointerEvents;
    document.body.style.pointerEvents = 'none';
    console.warn('[OverlayStack] body pointer-events LOCKED (none)', {
      modalId: nextTopModal.id,
      modalType: nextTopModal.type,
      totalOverlays: nextOverlays.length,
      snapshot: bodyPointerEventsSnapshot,
    });
    return;
  }

  if (previousTopModal && !nextTopModal) {
    document.body.style.pointerEvents = bodyPointerEventsSnapshot ?? '';
    console.log('[OverlayStack] body pointer-events RELEASED', {
      prevModalId: previousTopModal.id,
      restoredTo: bodyPointerEventsSnapshot ?? '(empty)',
      totalOverlays: nextOverlays.length,
    });
    bodyPointerEventsSnapshot = null;
    return;
  }

  if (nextTopModal) {
    document.body.style.pointerEvents = 'none';
    console.log('[OverlayStack] body stays LOCKED (modal swap)', {
      modalId: nextTopModal.id,
      modalType: nextTopModal.type,
    });
  }
}

function createOverlayEntry(input: OverlayStackOpenInput): OverlayStackEntry {
  return {
    id: input.id,
    type: input.type,
    modal: input.modal ?? false,
    restoreFocusTo: input.restoreFocusTo ?? null,
    elements: normalizeElements(input.elements),
  };
}

function containsElement(
  overlay: OverlayStackEntry | undefined,
  element: Element | null,
): boolean {
  if (!overlay || !element) {
    return false;
  }

  return overlay.elements.some((candidate) => candidate === element || candidate.contains(element));
}

const overlayStackStore = createStore<OverlayStackState>((set, get) => ({
  overlays: [],

  pushOverlay: (input) => {
    console.log('[OverlayStack] PUSH', { id: input.id, type: input.type, modal: input.modal, stackSizeBefore: get().overlays.length });
    const nextEntry = createOverlayEntry(input);
    set((state) => {
      const nextOverlays = [
        ...state.overlays.filter((overlay) => overlay.id !== input.id),
        nextEntry,
      ];
      syncBodyPointerEvents(state.overlays, nextOverlays);
      return { overlays: nextOverlays };
    });
  },

  updateOverlay: (id, patch) => {
    set((state) => {
      const index = state.overlays.findIndex((overlay) => overlay.id === id);
      if (index === -1) {
        return state;
      }

      const current = state.overlays[index];
      const nextOverlay: OverlayStackEntry = {
        ...current,
        ...(patch.type === undefined ? null : { type: patch.type }),
        ...(patch.modal === undefined ? null : { modal: patch.modal }),
        ...(patch.restoreFocusTo === undefined
          ? null
          : { restoreFocusTo: patch.restoreFocusTo }),
        ...(patch.elements === undefined
          ? null
          : { elements: normalizeElements(patch.elements) }),
      };
      const nextOverlays = [...state.overlays];
      nextOverlays[index] = nextOverlay;
      syncBodyPointerEvents(state.overlays, nextOverlays);
      return { overlays: nextOverlays };
    });
  },

  popOverlay: (id) => {
    const previousOverlays = get().overlays;
    const removedOverlay = previousOverlays.find((overlay) => overlay.id === id);
    if (!removedOverlay) {
      console.log('[OverlayStack] POP skipped (id not found)', { id });
      return;
    }
    console.log('[OverlayStack] POP', { id, type: removedOverlay.type, modal: removedOverlay.modal, stackSizeBefore: previousOverlays.length });

    const previousTopModal = getTopModalOverlay(previousOverlays);
    const nextOverlays = previousOverlays.filter((overlay) => overlay.id !== id);

    set(() => {
      syncBodyPointerEvents(previousOverlays, nextOverlays);
      return { overlays: nextOverlays };
    });

    if (previousTopModal?.id === id && removedOverlay.modal) {
      restoreFocus(removedOverlay.restoreFocusTo);
    }
  },

  getTopOverlay: () => getTopOverlay(get().overlays),

  getTopModalOverlay: () => getTopModalOverlay(get().overlays),

  isOverlayTopmost: (id) => getTopOverlay(get().overlays)?.id === id,

  isTopmostModalOverlay: (id) => getTopModalOverlay(get().overlays)?.id === id,

  getOverlayLayer: (id) => {
    const index = get().overlays.findIndex((overlay) => overlay.id === id);
    return index === -1 ? null : index + 1;
  },

  overlayContainsElement: (id, element) => {
    return containsElement(
      get().overlays.find((overlay) => overlay.id === id),
      element,
    );
  },

  isElementWithinAnyOverlay: (element) => {
    return get().overlays.some((overlay) => containsElement(overlay, element));
  },

  getTopmostOverlayContainingElement: (element) => {
    const { overlays } = get();
    for (let index = overlays.length - 1; index >= 0; index -= 1) {
      const overlay = overlays[index];
      if (containsElement(overlay, element)) {
        return overlay;
      }
    }

    return null;
  },
}));

/** Returns the vanilla store API for imperative overlay registration and queries. */
export function useOverlayStackApi() {
  return overlayStackStore;
}

function useOverlayStack<T>(
  selector: (state: OverlayStackState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(overlayStackStore, selector, equalityFn);
}

/** Subscribes to the current ordered overlay snapshot. */
export function useOverlayStackState(): OverlayStackSnapshot {
  return useOverlayStack((state) => ({ overlays: state.overlays }), shallow);
}

/** Subscribes to the current topmost overlay, regardless of modality. */
export function useTopOverlay(): OverlayStackEntry | null {
  return useOverlayStack((state) => state.getTopOverlay());
}

/** Subscribes to the current topmost modal overlay. */
export function useTopModalOverlay(): OverlayStackEntry | null {
  return useOverlayStack((state) => state.getTopModalOverlay());
}

/** Subscribes to the overlay's 1-based stack layer. */
export function useOverlayLayer(id: string): number | null {
  return useOverlayStack((state) => state.getOverlayLayer(id));
}

/** Subscribes to whether the overlay is the current topmost entry. */
export function useIsOverlayTopmost(id: string): boolean {
  return useOverlayStack((state) => state.isOverlayTopmost(id));
}

/** Subscribes to whether the overlay is the current topmost modal entry. */
export function useIsTopmostModalOverlay(id: string): boolean {
  return useOverlayStack((state) => state.isTopmostModalOverlay(id));
}

/** Subscribes to the topmost overlay that currently owns the provided element. */
export function useTopmostOverlayContainingElement(
  element: Element | null,
): OverlayStackEntry | null {
  return useOverlayStack((state) => state.getTopmostOverlayContainingElement(element));
}

/** Resets overlay ordering and global side effects for isolated tests. */
export function __resetOverlayStackForTests(): void {
  overlayStackStore.setState({ overlays: [] });
  if (isBrowser()) {
    document.body.style.pointerEvents = '';
  }
  bodyPointerEventsSnapshot = null;
}
