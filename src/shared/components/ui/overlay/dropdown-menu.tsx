import * as React from 'react';
import { Menu as MenuPrimitive } from '@base-ui/react/menu';
import { Separator as SeparatorPrimitive } from '@base-ui/react/separator';
import { Check, ChevronRight, Circle } from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/shared/components/ui/contracts/cn';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle } from './shared';

const DropdownMenuModalContext = React.createContext(true);

const DropdownMenu = ({
  modal = true,
  ...props
}: React.ComponentPropsWithoutRef<typeof MenuPrimitive.Root>) => (
  <DropdownMenuModalContext.Provider value={modal}>
    <MenuPrimitive.Root modal={modal} {...props} />
  </DropdownMenuModalContext.Provider>
);

const DropdownMenuTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof MenuPrimitive.Trigger> & { asChild?: boolean }
>(({ asChild, children, ...props }, ref) => {
  if (asChild) {
    return (
      <MenuPrimitive.Trigger
        ref={ref}
        render={React.Children.only(children) as React.ReactElement}
        {...props}
      />
    );
  }
  return (
    <MenuPrimitive.Trigger ref={ref} {...props}>
      {children}
    </MenuPrimitive.Trigger>
  );
});
DropdownMenuTrigger.displayName = 'DropdownMenuTrigger';

const DropdownMenuGroup = MenuPrimitive.Group;

const DropdownMenuPortal = MenuPrimitive.Portal;

const DropdownMenuSub = MenuPrimitive.SubmenuRoot;

const DropdownMenuRadioGroup = MenuPrimitive.RadioGroup;

const DropdownMenuSubTrigger = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof MenuPrimitive.SubmenuTrigger> & {
    inset?: boolean;
  }
>(({ className, inset, children, ...props }, ref) => (
  <MenuPrimitive.SubmenuTrigger
    ref={ref}
    className={cn(
      'flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent data-[open]:bg-accent',
      inset && 'pl-8',
      className,
    )}
    {...props}
  >
    {children}
    <ChevronRight className="ml-auto h-4 w-4" />
  </MenuPrimitive.SubmenuTrigger>
));
DropdownMenuSubTrigger.displayName = 'DropdownMenuSubTrigger';

interface DropdownMenuPositionerProps {
  sideOffset?: number;
  side?: 'top' | 'bottom' | 'left' | 'right';
  align?: 'start' | 'center' | 'end';
  collisionPadding?: number | Partial<Record<'top' | 'right' | 'bottom' | 'left', number>>;
}

const DropdownMenuSubContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof MenuPrimitive.Popup> & DropdownMenuPositionerProps
>(({ className, sideOffset = 0, side, align, collisionPadding, style, ...props }, ref) => {
  const bridge = useOverlayBridge({ type: 'menu-submenu', modal: false });
  const layer = useOverlayLayer(bridge.handle.id);
  const popupRef = React.useMemo(
    () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
    [bridge, ref],
  );

  return (
    <MenuPrimitive.Portal>
      <OverlayInstanceProvider value={bridge}>
        <MenuPrimitive.Positioner
          side={side}
          align={align}
          sideOffset={sideOffset}
          collisionPadding={collisionPadding}
          style={getOverlayLayerStyle(layer, 'positioner')}
        >
          <MenuPrimitive.Popup
            ref={popupRef}
            className={cn(
              'min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-lg data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
              className,
            )}
            style={style}
            {...props}
          />
        </MenuPrimitive.Positioner>
      </OverlayInstanceProvider>
    </MenuPrimitive.Portal>
  );
});
DropdownMenuSubContent.displayName = 'DropdownMenuSubContent';

const dropdownMenuContentVariants = cva(
  'min-w-[8rem] overflow-hidden p-1 data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
  {
    variants: {
      variant: {
        default: 'rounded-md border bg-popover text-popover-foreground shadow-md',
        retro:
          'rounded-sm border-2 border-[#6a8a8a] dark:border-[#8a9a9a] bg-[#f5f3ed] dark:bg-[#3a4a4a] text-[#5a7a7a] dark:text-[#d8d4cb] shadow-[-3px_3px_0_0_rgba(106,138,138,0.15)] dark:shadow-[-3px_3px_0_0_rgba(20,30,30,0.3)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface DropdownMenuContentProps
  extends React.ComponentPropsWithoutRef<typeof MenuPrimitive.Popup>,
    VariantProps<typeof dropdownMenuContentVariants>,
    DropdownMenuPositionerProps {}

const DropdownMenuContent = React.forwardRef<HTMLDivElement, DropdownMenuContentProps>(
  ({ className, sideOffset = 4, side, align, collisionPadding, variant, style, ...props }, ref) => {
    const modal = React.useContext(DropdownMenuModalContext);
    const bridge = useOverlayBridge({ type: 'menu', modal });
    const layer = useOverlayLayer(bridge.handle.id);
    const popupRef = React.useMemo(
      () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
      [bridge, ref],
    );

    return (
      <MenuPrimitive.Portal>
        <OverlayInstanceProvider value={bridge}>
          <MenuPrimitive.Positioner
            side={side}
            align={align}
            sideOffset={sideOffset}
            collisionPadding={collisionPadding}
            style={getOverlayLayerStyle(layer, 'positioner')}
          >
            <MenuPrimitive.Popup
              ref={popupRef}
              className={cn(dropdownMenuContentVariants({ variant, className }))}
              style={style}
              {...props}
            />
          </MenuPrimitive.Positioner>
        </OverlayInstanceProvider>
      </MenuPrimitive.Portal>
    );
  },
);
DropdownMenuContent.displayName = 'DropdownMenuContent';

const dropdownMenuItemVariants = cva(
  'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors data-[disabled]:pointer-events-none data-[disabled]:opacity-50 preserve-case',
  {
    variants: {
      variant: {
        default: 'focus:bg-accent focus:text-accent-foreground',
        retro:
          'focus:bg-[#e8e4db] dark:focus:bg-[#4a5a5a] focus:text-[#4a6a6a] dark:focus:text-[#e8e4db] font-heading',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface DropdownMenuItemProps
  extends React.ComponentPropsWithoutRef<typeof MenuPrimitive.Item>,
    VariantProps<typeof dropdownMenuItemVariants> {
  inset?: boolean;
}

const DropdownMenuItem = React.forwardRef<HTMLDivElement, DropdownMenuItemProps>(
  ({ className, inset, variant, ...props }, ref) => (
    <MenuPrimitive.Item
      ref={ref}
      className={cn(dropdownMenuItemVariants({ variant }), inset && 'pl-8', className)}
      {...props}
    />
  ),
);
DropdownMenuItem.displayName = 'DropdownMenuItem';

const DropdownMenuCheckboxItem = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof MenuPrimitive.CheckboxItem>
>(({ className, children, checked, ...props }, ref) => (
  <MenuPrimitive.CheckboxItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className,
    )}
    checked={checked}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <MenuPrimitive.CheckboxItemIndicator>
        <Check className="h-4 w-4" />
      </MenuPrimitive.CheckboxItemIndicator>
    </span>
    {children}
  </MenuPrimitive.CheckboxItem>
));
DropdownMenuCheckboxItem.displayName = 'DropdownMenuCheckboxItem';

const DropdownMenuRadioItem = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof MenuPrimitive.RadioItem>
>(({ className, children, ...props }, ref) => (
  <MenuPrimitive.RadioItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className,
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <MenuPrimitive.RadioItemIndicator>
        <Circle className="h-2 w-2 fill-current" />
      </MenuPrimitive.RadioItemIndicator>
    </span>
    {children}
  </MenuPrimitive.RadioItem>
));
DropdownMenuRadioItem.displayName = 'DropdownMenuRadioItem';

const DropdownMenuLabel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    inset?: boolean;
  }
>(({ className, inset, ...props }, ref) => (
  <div ref={ref} className={cn('px-2 py-1.5 text-sm font-light', inset && 'pl-8', className)} {...props} />
));
DropdownMenuLabel.displayName = 'DropdownMenuLabel';

const DropdownMenuSeparator = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive>
>(({ className, ...props }, ref) => (
  <SeparatorPrimitive ref={ref} className={cn('-mx-1 my-1 h-px bg-muted', className)} {...props} />
));
DropdownMenuSeparator.displayName = 'DropdownMenuSeparator';

const DropdownMenuShortcut = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) => (
  <span className={cn('ml-auto text-xs tracking-widest opacity-60', className)} {...props} />
);
DropdownMenuShortcut.displayName = 'DropdownMenuShortcut';

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
  dropdownMenuContentVariants,
  dropdownMenuItemVariants,
};
