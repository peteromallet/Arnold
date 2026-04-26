import * as React from 'react';
import { Select as SelectPrimitive } from '@base-ui/react/select';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/shared/components/ui/contracts/cn';
import { OverlayInstanceProvider, useOverlayBridge } from '@/shared/components/ui/overlay/overlayBridge';
import { useOverlayLayer } from '@/shared/state/overlayStack';
import { composeRefs, getOverlayLayerStyle } from './shared';

const SelectModalContext = React.createContext(true);

type SelectRootProps = Omit<
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Root>,
  'onValueChange'
> & {
  onValueChange?: (value: string) => void;
};

const Select = ({ onValueChange, modal = true, ...props }: SelectRootProps) => (
  <SelectModalContext.Provider value={modal}>
    <SelectPrimitive.Root
      {...props}
      modal={modal}
      onValueChange={(value) => {
        onValueChange?.(value);
      }}
    />
  </SelectModalContext.Provider>
);

const SelectValue = React.forwardRef<
  HTMLSpanElement,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Value> & {
    placeholder?: string;
  }
>(({ placeholder, children, ...props }, ref) => (
  <SelectPrimitive.Value ref={ref} {...props}>
    {children !== undefined
      ? children
      : placeholder !== undefined
        ? ((value: string | null) => value ?? placeholder)
        : undefined}
  </SelectPrimitive.Value>
));
SelectValue.displayName = 'SelectValue';

const selectTriggerVariants = cva(
  'flex w-full items-center justify-between rounded-md px-3 py-2 text-base lg:text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 relative preserve-case',
  {
    variants: {
      variant: {
        default:
          'border border-input bg-background focus:ring-2 focus:ring-ring focus:ring-offset-2 [&>span]:line-clamp-1',
        retro:
          'justify-start [&>span]:w-full [&>span]:text-left [&>span]:truncate bg-background hover:bg-[#6a8a8a]/10 rounded-sm border-2 border-[#6a8a8a]/30 hover:border-[#6a8a8a]/45 dark:border-[#6a7a7a] dark:hover:bg-transparent text-[#5a7a7a] dark:text-[#c8c4bb] font-heading font-light tracking-wide transition-all duration-200 shadow-[0_1px_2px_0_rgba(106,138,138,0.06)] hover:shadow-[0_2px_4px_-1px_rgba(106,138,138,0.1)] dark:shadow-[-2px_2px_0_0_rgba(20,30,30,0.4)] dark:hover:shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] dark:hover:translate-x-[-0.5px] dark:hover:translate-y-[0.5px] focus:ring-2 focus:ring-[#6a8a8a]/30 focus:ring-offset-0',
        'retro-dark':
          'justify-start [&>span]:w-full [&>span]:min-w-0 [&>span]:text-left [&>span]:truncate !text-xs bg-[#3a4a4a] hover:bg-[#4a5a5a] rounded-sm border-2 border-[#6a7a7a] text-[#d8d4cb] font-heading font-light tracking-wide transition-all duration-200 shadow-[-2px_2px_0_0_rgba(20,30,30,0.3)] hover:shadow-[-1px_1px_0_0_rgba(20,30,30,0.3)] hover:translate-x-[-0.5px] hover:translate-y-[0.5px] focus:ring-2 focus:ring-[#6a7a7a]/30 focus:ring-offset-0',
      },
      size: {
        default: 'h-10',
        sm: 'h-9 text-sm px-2',
        lg: 'h-11 text-base px-4',
      },
      colorScheme: {
        default: '',
        blue:
          '!border-blue-400/60 hover:!border-blue-500 hover:!bg-blue-400/15 dark:!border-blue-500 dark:hover:!bg-blue-500/20 !text-blue-600 dark:!text-blue-400 hover:!shadow-[0_2px_6px_-2px_rgba(59,130,246,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-blue-400/30',
        violet:
          '!border-violet-400/60 hover:!border-violet-500 hover:!bg-violet-400/15 dark:!border-violet-500 dark:hover:!bg-violet-500/20 !text-violet-600 dark:!text-violet-400 hover:!shadow-[0_2px_6px_-2px_rgba(139,92,246,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-violet-400/30',
        emerald:
          '!border-emerald-400/60 hover:!border-emerald-500 hover:!bg-emerald-400/15 dark:!border-emerald-500 dark:hover:!bg-emerald-500/20 !text-emerald-600 dark:!text-emerald-400 hover:!shadow-[0_2px_6px_-2px_rgba(16,185,129,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-emerald-400/30',
        amber:
          '!border-amber-400/60 hover:!border-amber-500 hover:!bg-amber-400/15 dark:!border-amber-500 dark:hover:!bg-amber-500/20 !text-amber-600 dark:!text-amber-400 hover:!shadow-[0_2px_6px_-2px_rgba(245,158,11,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-amber-400/30',
        rose:
          '!border-rose-400/60 hover:!border-rose-500 hover:!bg-rose-400/15 dark:!border-rose-500 dark:hover:!bg-rose-500/20 !text-rose-600 dark:!text-rose-400 hover:!shadow-[0_2px_6px_-2px_rgba(244,63,94,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-rose-400/30',
        cyan:
          '!border-cyan-400/60 hover:!border-cyan-500 hover:!bg-cyan-400/15 dark:!border-cyan-500 dark:hover:!bg-cyan-500/20 !text-cyan-600 dark:!text-cyan-400 hover:!shadow-[0_2px_6px_-2px_rgba(6,182,212,0.15)] dark:hover:!shadow-[-1px_1px_0_0_rgba(20,30,30,0.4)] focus:!ring-cyan-400/30',
        zinc:
          '!bg-zinc-800/70 !border-zinc-700 !text-zinc-400 hover:!bg-zinc-700/70 hover:!text-zinc-300 focus:!ring-zinc-600/30',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
      colorScheme: 'default',
    },
  },
);

interface SelectTriggerProps
  extends Omit<React.ComponentPropsWithoutRef<'button'>, 'className'>,
    VariantProps<typeof selectTriggerVariants> {
  hideIcon?: boolean;
  className?: string;
}

const SelectTrigger = React.forwardRef<HTMLButtonElement, SelectTriggerProps>(
  ({ className, children, variant, size, colorScheme, hideIcon, ...props }, ref) => (
    <SelectPrimitive.Trigger
      ref={ref}
      data-select-trigger
      className={cn(selectTriggerVariants({ variant, size, colorScheme, className }))}
      {...props}
    >
      {children}
      {!hideIcon && !(variant === 'retro' || variant === 'retro-dark') && (
        <SelectPrimitive.Icon>
          <ChevronDown className={cn('h-4 w-4 opacity-50')} />
        </SelectPrimitive.Icon>
      )}
    </SelectPrimitive.Trigger>
  ),
);
SelectTrigger.displayName = 'SelectTrigger';

const SelectScrollUpButton = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpArrow>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollUpArrow
    ref={ref}
    className={cn('flex cursor-default items-center justify-center py-2', className)}
    data-select-scroll-button="up"
    onClick={(e: React.MouseEvent) => e.stopPropagation()}
    {...props}
  >
    <ChevronUp className="h-4 w-4" />
  </SelectPrimitive.ScrollUpArrow>
));
SelectScrollUpButton.displayName = 'SelectScrollUpButton';

const SelectScrollDownButton = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownArrow>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollDownArrow
    ref={ref}
    className={cn('flex cursor-default items-center justify-center py-2', className)}
    data-select-scroll-button="down"
    onClick={(e: React.MouseEvent) => e.stopPropagation()}
    {...props}
  >
    <ChevronDown className="h-4 w-4" />
  </SelectPrimitive.ScrollDownArrow>
));
SelectScrollDownButton.displayName = 'SelectScrollDownButton';

const selectContentVariants = cva(
  'relative max-h-96 min-w-[8rem] overflow-hidden data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
  {
    variants: {
      variant: {
        default: 'rounded-md border bg-popover text-popover-foreground shadow-md',
        retro:
          'rounded-sm border-2 border-[#6a8a8a] dark:border-[#6a7a7a] bg-background text-[#5a7a7a] dark:text-[#c8c4bb] shadow-[-3px_3px_0_0_rgba(106,138,138,0.15)] dark:shadow-[-3px_3px_0_0_rgba(20,30,30,0.4)]',
        'retro-dark':
          'rounded-sm border-2 border-[#6a7a7a] bg-[#3a4a4a] text-[#d8d4cb] shadow-[-3px_3px_0_0_rgba(20,30,30,0.3)]',
        zinc: 'rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-300 shadow-lg',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface SelectContentProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className'>,
    VariantProps<typeof selectContentVariants> {
  header?: React.ReactNode;
  container?: HTMLElement | null;
  onCloseAutoFocus?: (event: Event) => void;
  position?: 'popper' | 'item-aligned';
  side?: 'top' | 'bottom' | 'left' | 'right';
  sideOffset?: number;
  align?: 'start' | 'center' | 'end';
  className?: string;
}

const SelectContent = React.forwardRef<HTMLDivElement, SelectContentProps>(
  (
    {
      className,
      children,
      position = 'popper',
      header,
      container,
      variant,
      side = 'bottom',
      sideOffset = 0,
      align,
      style,
      ...props
    },
    ref,
  ) => {
    const modal = React.useContext(SelectModalContext);
    const bridge = useOverlayBridge({ type: 'select', modal });
    const layer = useOverlayLayer(bridge.handle.id);
    const popupRef = React.useMemo(
      () => composeRefs(ref, (node: HTMLDivElement | null) => bridge.registerElement('popup', node)),
      [bridge, ref],
    );
    const isCompact = variant === 'retro' || variant === 'retro-dark' || variant === 'zinc';
    const isPopper = position === 'popper';

    return (
      <SelectPrimitive.Portal container={container ?? undefined}>
        <OverlayInstanceProvider value={bridge}>
          <SelectPrimitive.Positioner
            side={side}
            sideOffset={sideOffset}
            align={align}
            alignItemWithTrigger={!isPopper}
            style={getOverlayLayerStyle(layer, 'positioner')}
          >
            <SelectPrimitive.Popup
              ref={popupRef}
              className={cn(
                selectContentVariants({ variant }),
                isPopper &&
                  'data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1',
                className,
              )}
              style={style}
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
              {...props}
            >
              {header}
              <SelectScrollUpButton />
              <SelectPrimitive.List
                className={cn(
                  isCompact ? 'py-1' : 'p-1',
                  isPopper &&
                    'h-full w-full min-w-[var(--anchor-width)] max-h-[var(--available-height)]',
                  'overflow-y-auto overscroll-contain',
                )}
                style={{
                  WebkitOverflowScrolling: 'touch',
                  touchAction: 'pan-y',
                }}
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
              >
                {children}
              </SelectPrimitive.List>
              <SelectScrollDownButton />
            </SelectPrimitive.Popup>
          </SelectPrimitive.Positioner>
        </OverlayInstanceProvider>
      </SelectPrimitive.Portal>
    );
  },
);
SelectContent.displayName = 'SelectContent';

const SelectLabel = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.GroupLabel>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.GroupLabel
    ref={ref}
    className={cn('py-1.5 pl-8 pr-2 text-sm font-light', className)}
    {...props}
  />
));
SelectLabel.displayName = 'SelectLabel';

const selectItemVariants = cva(
  'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 preserve-case',
  {
    variants: {
      variant: {
        default:
          'pl-8 pr-2 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[selected]:bg-accent/50 data-[selected]:font-medium',
        retro:
          'px-2 data-[highlighted]:bg-[#e8e4db] dark:data-[highlighted]:bg-[#3d4d4d] data-[highlighted]:text-[#4a6a6a] dark:data-[highlighted]:text-[#e8e4db] font-heading font-light data-[selected]:bg-[#d8d4cb] dark:data-[selected]:bg-[#4a5a5a] data-[selected]:font-normal',
        'retro-dark':
          'px-2 data-[highlighted]:bg-[#4a5a5a] data-[highlighted]:text-[#e8e4db] font-heading font-light text-[#d8d4cb] data-[selected]:bg-[#5a6a6a] data-[selected]:font-normal',
        zinc:
          'px-2 text-zinc-300 data-[highlighted]:bg-zinc-700 data-[highlighted]:text-zinc-100 data-[selected]:bg-zinc-600 data-[selected]:text-zinc-100',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface SelectItemProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'value'>,
    VariantProps<typeof selectItemVariants> {
  onTouchStart?: React.TouchEventHandler;
  onTouchEnd?: React.TouchEventHandler;
  value: string;
  disabled?: boolean;
  className?: string;
  label?: string;
}

const SelectItem = React.forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, children, onPointerDown, onClick, onTouchStart, onTouchEnd, variant, value, disabled, label, ...props }, ref) => {
    const isCompact = variant === 'retro' || variant === 'retro-dark' || variant === 'zinc';

    return (
      <SelectPrimitive.Item
        ref={ref}
        className={cn(selectItemVariants({ variant, className }))}
        value={value}
        disabled={disabled}
        label={label}
        onPointerDown={onPointerDown}
        onClick={(e: React.MouseEvent) => {
          e.stopPropagation();
          onClick?.(e as unknown as React.MouseEvent<HTMLDivElement>);
        }}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        {...props}
      >
        {!isCompact && (
          <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
            <SelectPrimitive.ItemIndicator>
              <Check className="h-4 w-4" />
            </SelectPrimitive.ItemIndicator>
          </span>
        )}

        <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      </SelectPrimitive.Item>
    );
  },
);
SelectItem.displayName = 'SelectItem';

const SelectSeparator = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<'div'>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('-mx-1 my-1 h-px bg-muted', className)} {...props} />
));
SelectSeparator.displayName = 'SelectSeparator';

export {
  Select,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectSeparator,
  selectTriggerVariants,
  selectContentVariants,
  selectItemVariants,
};
