import * as React from 'react';
import { Tooltip as TooltipPrimitive } from '@base-ui/react/tooltip';
import { cn } from '@/shared/components/ui/contracts/cn';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle } from './shared';

const TooltipProvider: React.FC<{
  delayDuration?: number;
  children: React.ReactNode;
}> = ({ delayDuration = 0, children }) => (
  <TooltipPrimitive.Provider delay={delayDuration}>{children}</TooltipPrimitive.Provider>
);

const Tooltip = TooltipPrimitive.Root;

const TooltipTrigger = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Trigger> & {
    asChild?: boolean;
  }
>(({ asChild, children, ...props }, ref) => {
  if (asChild) {
    return (
      <TooltipPrimitive.Trigger
        ref={ref}
        render={React.Children.only(children) as React.ReactElement}
        {...props}
      />
    );
  }
  return (
    <TooltipPrimitive.Trigger ref={ref} {...props}>
      {children}
    </TooltipPrimitive.Trigger>
  );
});
TooltipTrigger.displayName = 'TooltipTrigger';

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Popup> & {
    sideOffset?: number;
    side?: 'top' | 'bottom' | 'left' | 'right';
    align?: 'start' | 'center' | 'end';
    collisionPadding?: number;
  }
>(({ className, sideOffset = 4, side, align, collisionPadding, style, ...props }, ref) => {
  const bridge = useOverlayBridge({ type: 'tooltip', modal: false });
  const layer = useOverlayLayer(bridge.handle.id);
  const popupRef = React.useMemo(
    () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
    [bridge, ref],
  );

  return (
    <TooltipPrimitive.Portal>
      <OverlayInstanceProvider value={bridge}>
        <TooltipPrimitive.Positioner
          side={side}
          sideOffset={sideOffset}
          align={align}
          collisionPadding={collisionPadding}
          style={getOverlayLayerStyle(layer, 'positioner')}
        >
          <TooltipPrimitive.Popup
            ref={popupRef}
            className={cn(
              'overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md',
              'animate-in fade-in-0 zoom-in-95 duration-200 ease-out',
              'data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[ending-style]:zoom-out-95 data-[ending-style]:duration-150 data-[ending-style]:ease-in',
              'data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
              className,
            )}
            style={style}
            {...props}
          />
        </TooltipPrimitive.Positioner>
      </OverlayInstanceProvider>
    </TooltipPrimitive.Portal>
  );
});
TooltipContent.displayName = 'TooltipContent';

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger };
