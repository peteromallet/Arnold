/*
 * Keep `<Dialog open={...}>` mounted until `open` flips false.
 * Base UI releases focus scope and body pointer-events during close, not on unmount.
 * Returning `null` above an open dialog can strand the page in a blocked state.
 * If closed-state children are expensive, gate `<DialogContent>` instead.
 */

import * as React from 'react';
import { Dialog as DialogPrimitive } from '@base-ui/react/dialog';
import { X } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle } from './shared';

const Dialog = DialogPrimitive.Root;

const DialogTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Trigger> & { asChild?: boolean }
>(({ asChild, children, ...props }, ref) => {
  if (asChild) {
    return (
      <DialogPrimitive.Trigger
        ref={ref}
        render={React.Children.only(children) as React.ReactElement}
        {...props}
      />
    );
  }
  return (
    <DialogPrimitive.Trigger ref={ref} {...props}>
      {children}
    </DialogPrimitive.Trigger>
  );
});
DialogTrigger.displayName = 'DialogTrigger';

const DialogPortal = DialogPrimitive.Portal;

const DialogOverlay = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Backdrop> & {
    layer?: number | null;
  }
>(({ className, onClick, style, layer, ...props }, ref) => (
  <DialogPrimitive.Backdrop
    ref={ref}
    data-dialog-backdrop
    className={cn(
      'fixed inset-0 bg-black/80 cursor-pointer data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0',
      className,
    )}
    onClick={onClick}
    style={getOverlayLayerStyle(layer ?? null, 'backdrop', style)}
    {...props}
  />
));
DialogOverlay.displayName = 'DialogOverlay';

interface DialogContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Popup> {
  container?: HTMLElement | null;
}

const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, container, style, ...props }, ref) => {
    const bridge = useOverlayBridge({ type: 'dialog', modal: true });
    const layer = useOverlayLayer(bridge.handle.id);
    const popupRef = React.useMemo(
      () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
      [bridge, ref],
    );
    const backdropRef = React.useMemo(
      () => composeRefs((node: HTMLDivElement | null) => bridge.registerElement('backdrop', node)),
      [bridge],
    );

    return (
      <DialogPortal container={container ?? undefined}>
        <OverlayInstanceProvider value={bridge}>
          <DialogOverlay ref={backdropRef} layer={layer} />
          <DialogPrimitive.Popup
            data-pane-control
            data-dialog-content
            ref={popupRef}
            className={cn(
              'fixed left-[50%] top-[50%] grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95 data-[ending-style]:slide-out-to-left-1/2 data-[ending-style]:slide-out-to-top-[48%] data-[open]:slide-in-from-left-1/2 data-[open]:slide-in-from-top-[48%] sm:rounded-lg',
              className,
            )}
            style={getOverlayLayerStyle(layer, 'popup', style)}
            {...props}
          >
            {children}
            <DialogPrimitive.Close
              data-dialog-close
              className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[open]:bg-accent data-[open]:text-muted-foreground"
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </DialogPrimitive.Close>
          </DialogPrimitive.Popup>
        </OverlayInstanceProvider>
      </DialogPortal>
    );
  },
);
DialogContent.displayName = 'DialogContent';

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-y-1.5 text-center sm:text-left', className)} {...props} />
);
DialogHeader.displayName = 'DialogHeader';

const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:gap-x-2', className)}
    {...props}
  />
);
DialogFooter.displayName = 'DialogFooter';

const DialogTitle = React.forwardRef<
  HTMLHeadingElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-lg font-light leading-none tracking-tight', className)}
    {...props}
  />
));
DialogTitle.displayName = 'DialogTitle';

const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
));
DialogDescription.displayName = 'DialogDescription';

export {
  Dialog,
  DialogPortal,
  DialogTrigger,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
