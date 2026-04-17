import * as React from 'react';
import {
  useIsOverlayTopmost,
  useOverlayStackApi,
  useTopmostOverlayContainingElement,
} from '@/shared/state/overlayStack';

export type OverlayElementKind = 'popup' | 'backdrop';

interface OverlayElements {
  popup: HTMLElement | null;
  backdrop: HTMLElement | null;
}

export interface OverlayHandle {
  id: string;
  getType: () => string;
  isModal: () => boolean;
  getElement: (kind: OverlayElementKind) => HTMLElement | null;
  getElements: () => readonly HTMLElement[];
  isRegistered: () => boolean;
  containsElement: (element: Element | null) => boolean;
}

export interface UseOverlayBridgeOptions {
  id?: string;
  type: string;
  modal?: boolean;
  restoreFocusTo?: HTMLElement | null;
}

interface OverlayBridgeContextValue {
  handle: OverlayHandle;
  registerElement: (kind: OverlayElementKind, element: HTMLElement | null) => void;
}

const OverlayBridgeContext = React.createContext<OverlayBridgeContextValue | null>(null);

const OVERLAY_ID_PREFIX = 'overlay';

function isHTMLElement(value: unknown): value is HTMLElement {
  return value instanceof HTMLElement;
}

function sanitizeOverlayId(id: string): string {
  return id.replace(/[^a-zA-Z0-9_-]/g, '-');
}

function setOverlayMetadata(
  element: HTMLElement,
  handle: OverlayHandle,
  kind: OverlayElementKind,
): void {
  element.dataset.overlayStackId = handle.id;
  element.dataset.overlayStackType = handle.getType();
  element.dataset.overlayStackKind = kind;
}

function clearOverlayMetadata(element: HTMLElement): void {
  delete element.dataset.overlayStackId;
  delete element.dataset.overlayStackType;
  delete element.dataset.overlayStackKind;
}

function getTrackedElements(elements: OverlayElements): readonly HTMLElement[] {
  return [elements.popup, elements.backdrop].filter(isHTMLElement);
}

function getRestoreFocusTarget(
  explicitTarget: HTMLElement | null | undefined,
  elements: readonly HTMLElement[],
): HTMLElement | null {
  if (explicitTarget !== undefined) {
    return explicitTarget;
  }

  const activeElement = document.activeElement;
  if (!(activeElement instanceof HTMLElement)) {
    return null;
  }

  if (elements.some((element) => element === activeElement || element.contains(activeElement))) {
    return null;
  }

  return activeElement;
}

function useOverlayBridgeContextValue(): OverlayBridgeContextValue {
  const context = React.useContext(OverlayBridgeContext);
  if (!context) {
    throw new Error('Overlay bridge hooks must be used within an OverlayInstanceProvider.');
  }

  return context;
}

/**
 * Creates a stable overlay bridge that registers the overlay only while popup/backdrop
 * DOM is actually present and keeps the stack entry updated as refs change.
 */
export function useOverlayBridge(options: UseOverlayBridgeOptions): OverlayBridgeContextValue {
  const stackApi = useOverlayStackApi();
  const reactId = React.useId();
  const overlayId = React.useMemo(
    () => sanitizeOverlayId(options.id ?? `${OVERLAY_ID_PREFIX}-${reactId}`),
    [options.id, reactId],
  );
  const elementsRef = React.useRef<OverlayElements>({ popup: null, backdrop: null });
  const registeredRef = React.useRef(false);
  const typeRef = React.useRef(options.type);
  const modalRef = React.useRef(options.modal ?? false);
  const restoreFocusToRef = React.useRef<HTMLElement | null | undefined>(options.restoreFocusTo);

  typeRef.current = options.type;
  modalRef.current = options.modal ?? false;
  restoreFocusToRef.current = options.restoreFocusTo;

  const handleRef = React.useRef<OverlayHandle | null>(null);
  if (!handleRef.current) {
    handleRef.current = {
      id: overlayId,
      getType: () => typeRef.current,
      isModal: () => modalRef.current,
      getElement: (kind) => elementsRef.current[kind],
      getElements: () => getTrackedElements(elementsRef.current),
      isRegistered: () => registeredRef.current,
      containsElement: (element) =>
        getTrackedElements(elementsRef.current).some(
          (candidate) => candidate === element || candidate.contains(element),
        ),
    };
  }
  const handle = handleRef.current;

  const syncRegistration = React.useCallback(() => {
    const elements = getTrackedElements(elementsRef.current);

    if (elements.length === 0) {
      if (registeredRef.current) {
        stackApi.getState().popOverlay(handle.id);
        registeredRef.current = false;
      }
      return;
    }

    const payload = {
      type: handle.getType(),
      modal: handle.isModal(),
      restoreFocusTo: getRestoreFocusTarget(restoreFocusToRef.current, elements),
      elements,
    };

    if (!registeredRef.current) {
      stackApi.getState().pushOverlay({ id: handle.id, ...payload });
      registeredRef.current = true;
      return;
    }

    stackApi.getState().updateOverlay(handle.id, payload);
  }, [handle, stackApi]);

  const registerElement = React.useCallback(
    (kind: OverlayElementKind, element: HTMLElement | null) => {
      const previous = elementsRef.current[kind];
      if (previous === element) {
        syncRegistration();
        return;
      }

      if (previous) {
        clearOverlayMetadata(previous);
      }

      elementsRef.current[kind] = element;

      if (element) {
        setOverlayMetadata(element, handle, kind);
      }

      syncRegistration();
    },
    [handle, syncRegistration],
  );

  React.useEffect(() => {
    syncRegistration();
  }, [syncRegistration, options.modal, options.restoreFocusTo, options.type]);

  React.useEffect(() => {
    return () => {
      const elements = elementsRef.current;
      if (elements.popup) {
        clearOverlayMetadata(elements.popup);
      }
      if (elements.backdrop) {
        clearOverlayMetadata(elements.backdrop);
      }
      if (registeredRef.current) {
        stackApi.getState().popOverlay(handle.id);
        registeredRef.current = false;
      }
    };
  }, [handle, stackApi]);

  return React.useMemo(
    () => ({
      handle,
      registerElement,
    }),
    [handle, registerElement],
  );
}

/** Provides the current overlay bridge to popup/backdrop descendants. */
export function OverlayInstanceProvider({
  value,
  children,
}: React.PropsWithChildren<{ value: OverlayBridgeContextValue }>) {
  return (
    <OverlayBridgeContext.Provider value={value}>{children}</OverlayBridgeContext.Provider>
  );
}

/** Returns the current overlay handle for bridge-aware descendants. */
export function useCurrentOverlayHandle(): OverlayHandle {
  return useOverlayBridgeContextValue().handle;
}

/** Returns a ref callback that registers the popup or backdrop with the overlay stack. */
export function useOverlayElementRegistration(
  kind: OverlayElementKind,
): React.RefCallback<HTMLElement> {
  const { registerElement } = useOverlayBridgeContextValue();

  return React.useCallback(
    (element: HTMLElement | null) => {
      registerElement(kind, element);
    },
    [kind, registerElement],
  );
}

/** Subscribes to whether the current overlay is the topmost stack entry. */
export function useCurrentOverlayTopmost(): boolean {
  const handle = useCurrentOverlayHandle();
  return useIsOverlayTopmost(handle.id);
}

/** Subscribes to whether the given element belongs to the current topmost overlay. */
export function useCurrentOverlayTopmostForElement(element: Element | null): boolean {
  const handle = useCurrentOverlayHandle();
  const topmostOverlay = useTopmostOverlayContainingElement(element);
  return topmostOverlay?.id === handle.id;
}
