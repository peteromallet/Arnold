import * as React from 'react';
import { Popover as PopoverPrimitive } from '@base-ui/react/popover';
import { cn } from '@/shared/components/ui/contracts/cn';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle } from './shared';

const PopoverModalContext = React.createContext<boolean>(false);

const Popover = ({
  modal = false,
  ...props
}: React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Root>) => (
  <PopoverModalContext.Provider value={modal === true}>
    <PopoverPrimitive.Root modal={modal} {...props} />
  </PopoverModalContext.Provider>
);

const PopoverTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Trigger> & { asChild?: boolean }
>(({ asChild, children, ...props }, ref) => {
  if (asChild) {
    return (
      <PopoverPrimitive.Trigger
        ref={ref}
        render={React.Children.only(children) as React.ReactElement}
        {...props}
      />
    );
  }
  return (
    <PopoverPrimitive.Trigger ref={ref} {...props}>
      {children}
    </PopoverPrimitive.Trigger>
  );
});
PopoverTrigger.displayName = 'PopoverTrigger';

const PopoverContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Popup> & {
    align?: 'start' | 'center' | 'end';
    side?: 'top' | 'bottom' | 'left' | 'right';
    sideOffset?: number;
    collisionPadding?: number | Partial<Record<'top' | 'right' | 'bottom' | 'left', number>>;
    container?: HTMLElement | null;
  }
>(({ className, align = 'center', side, sideOffset = 4, collisionPadding, container, style, ...props }, ref) => {
  const modal = React.useContext(PopoverModalContext);
  const bridge = useOverlayBridge({ type: 'popover', modal });
  const layer = useOverlayLayer(bridge.handle.id);
  const popupRef = React.useMemo(
    () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
    [bridge, ref],
  );

  return (
    <PopoverPrimitive.Portal container={container}>
      <OverlayInstanceProvider value={bridge}>
        <PopoverPrimitive.Positioner
          side={side}
          align={align}
          sideOffset={sideOffset}
          collisionPadding={collisionPadding}
          style={getOverlayLayerStyle(layer, 'positioner')}
        >
          <PopoverPrimitive.Popup
            ref={popupRef}
            className={cn(
              'w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
              className,
            )}
            style={style}
            {...props}
          />
        </PopoverPrimitive.Positioner>
      </OverlayInstanceProvider>
    </PopoverPrimitive.Portal>
  );
});
PopoverContent.displayName = 'PopoverContent';

export { Popover, PopoverTrigger, PopoverContent };
