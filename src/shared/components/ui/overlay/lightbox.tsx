import * as React from 'react';
import { Dialog as DialogPrimitive } from '@base-ui/react/dialog';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle, LIGHTBOX_BASE_Z_INDEX } from './shared';

const LightboxDialogModalContext = React.createContext(true);

interface LightboxDialogLayerContextValue {
  layer: number | null;
  registerElement: ReturnType<typeof useOverlayBridge>['registerElement'];
}

const LightboxDialogLayerContext = React.createContext<LightboxDialogLayerContextValue | null>(null);

function useLightboxDialogLayerContext(): LightboxDialogLayerContextValue {
  const value = React.useContext(LightboxDialogLayerContext);
  if (!value) {
    throw new Error('Lightbox dialog overlay primitives must be used within LightboxDialogPortal.');
  }
  return value;
}

const LightboxDialog = ({
  modal = true,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Root>) => (
  <LightboxDialogModalContext.Provider value={modal}>
    <DialogPrimitive.Root modal={modal} {...props} />
  </LightboxDialogModalContext.Provider>
);

const LightboxDialogPortal = ({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Portal>) => {
  const modal = React.useContext(LightboxDialogModalContext);
  const bridge = useOverlayBridge({ type: 'lightbox', modal });
  const layer = useOverlayLayer(bridge.handle.id);
  const contextValue = React.useMemo(
    () => ({ layer, registerElement: bridge.registerElement }),
    [bridge.registerElement, layer],
  );

  return (
    <DialogPrimitive.Portal {...props}>
      <OverlayInstanceProvider value={bridge}>
        <LightboxDialogLayerContext.Provider value={contextValue}>
          {children}
        </LightboxDialogLayerContext.Provider>
      </OverlayInstanceProvider>
    </DialogPrimitive.Portal>
  );
};

const LightboxDialogBackdrop = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Backdrop>
>(({ style, ...props }, ref) => {
  const { layer, registerElement } = useLightboxDialogLayerContext();
  const backdropRef = React.useMemo(
    () => composeRefs(ref, (node: HTMLDivElement | null) => registerElement('backdrop', node)),
    [ref, registerElement],
  );

  return (
    <DialogPrimitive.Backdrop
      ref={backdropRef}
      style={getOverlayLayerStyle(layer, 'backdrop', style, { baseZIndex: LIGHTBOX_BASE_Z_INDEX })}
      {...props}
    />
  );
});
LightboxDialogBackdrop.displayName = 'LightboxDialogBackdrop';

const LightboxDialogPopup = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Popup>
>(({ style, ...props }, ref) => {
  const { layer, registerElement } = useLightboxDialogLayerContext();
  const popupRef = React.useMemo(
    () => composeRefs(ref, (node: HTMLDivElement | null) => registerElement('popup', node)),
    [ref, registerElement],
  );

  return (
    <DialogPrimitive.Popup
      ref={popupRef}
      style={getOverlayLayerStyle(layer, 'popup', style, { baseZIndex: LIGHTBOX_BASE_Z_INDEX })}
      {...props}
    />
  );
});
LightboxDialogPopup.displayName = 'LightboxDialogPopup';

const LightboxDialogTitle = DialogPrimitive.Title;
const LightboxDialogDescription = DialogPrimitive.Description;

export {
  LightboxDialog,
  LightboxDialogPortal,
  LightboxDialogBackdrop,
  LightboxDialogPopup,
  LightboxDialogTitle,
  LightboxDialogDescription,
};
