import * as React from "react"
import { NumberField } from "@base-ui/react/number-field"
import { ChevronUp, ChevronDown } from "lucide-react"
import { cn } from "@/shared/components/ui/contracts/cn"

interface NumberInputProps {
  value: number | null
  onChange: (value: number | null) => void
  onValueCommitted?: (value: number | null) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  className?: string
  id?: string
  placeholder?: string
  prefix?: string
  tabIndex?: number
  'aria-labelledby'?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
  'aria-required'?: boolean
  'data-testid'?: string
}

const NumberInput = React.forwardRef<HTMLDivElement, NumberInputProps>(
  ({ value, onChange, onValueCommitted, min, max, step = 1, disabled, className, id, placeholder, prefix, tabIndex, 'aria-labelledby': ariaLabelledby, 'aria-describedby': ariaDescribedby, 'aria-invalid': ariaInvalid, 'aria-required': ariaRequired, 'data-testid': dataTestid }, ref) => {
    return (
      <NumberField.Root
        ref={ref}
        tabIndex={tabIndex}
        value={value}
        onValueChange={(val) => {
          onChange(val)
        }}
        onValueCommitted={onValueCommitted}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
        aria-invalid={ariaInvalid}
        aria-required={ariaRequired}
        data-testid={dataTestid}
      >
        <NumberField.Group
          className={cn(
            "flex items-center h-10 w-full rounded-md border border-input bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
            disabled && "cursor-not-allowed opacity-50",
            className
          )}
        >
          {prefix && (
            <span className="pl-2.5 text-muted-foreground select-none shrink-0">{prefix}</span>
          )}
          <NumberField.Input
            id={id}
            placeholder={placeholder}
            className={cn(
              "flex-1 min-w-0 h-full bg-transparent text-base lg:text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none focus:outline-none placeholder:text-muted-foreground",
              prefix ? "pl-1 pr-3" : "px-3"
            )}
          />
          <div className="flex flex-col h-full border-l border-input shrink-0">
            <NumberField.Increment
              className="flex-1 px-1.5 flex items-center justify-center hover:bg-muted/50 active:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              tabIndex={-1}
            >
              <ChevronUp className="h-3 w-3 text-muted-foreground" />
            </NumberField.Increment>
            <NumberField.Decrement
              className="flex-1 px-1.5 flex items-center justify-center hover:bg-muted/50 active:bg-muted transition-colors border-t border-input disabled:opacity-50 disabled:cursor-not-allowed"
              tabIndex={-1}
            >
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </NumberField.Decrement>
          </div>
        </NumberField.Group>
      </NumberField.Root>
    )
  }
)
NumberInput.displayName = "NumberInput"

export { NumberInput }
export type { NumberInputProps }
