import { Input } from '@/shared/components/ui/input.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { Switch } from '@/shared/components/ui/switch.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import type { AudioBindingValue, ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types/index.ts';

export interface ParameterControlsProps {
  schema: ParameterSchema;
  values: Record<string, unknown>;
  onChange: (name: string, value: unknown) => void;
  disabled?: boolean;
  className?: string;
}

type ParameterValue = number | string | boolean | AudioBindingValue;

const AUDIO_SOURCES: Array<AudioBindingValue['source']> = ['bass', 'mid', 'treble', 'amplitude'];

const isAudioBindingValue = (value: unknown): value is AudioBindingValue => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.source === 'string'
    && AUDIO_SOURCES.includes(candidate.source as AudioBindingValue['source'])
    && typeof candidate.min === 'number'
    && typeof candidate.max === 'number'
  );
};

const getFallbackValue = (parameter: ParameterDefinition): ParameterValue => {
  if (parameter.default !== undefined) {
    return parameter.default as ParameterValue;
  }

  switch (parameter.type) {
    case 'number':
      return parameter.min ?? 0;
    case 'select':
      return parameter.options?.[0]?.value ?? '';
    case 'boolean':
      return false;
    case 'audio-binding':
      return { source: 'amplitude', min: 0, max: 1 };
    case 'color':
      return '#000000';
    default:
      return '';
  }
};

export function getDefaultValues(schema: ParameterSchema): Record<string, unknown> {
  return schema.reduce<Record<string, unknown>>((defaults, parameter) => {
    defaults[parameter.name] = getFallbackValue(parameter);
    return defaults;
  }, {});
}

function getDisplayValue(parameter: ParameterDefinition, value: unknown): ParameterValue {
  if (value !== undefined) {
    if (parameter.type === 'audio-binding') {
      return isAudioBindingValue(value) ? value : getFallbackValue(parameter);
    }

    return value as Exclude<ParameterValue, AudioBindingValue>;
  }

  return getFallbackValue(parameter);
}

export function ParameterControls({
  schema,
  values,
  onChange,
  disabled = false,
  className,
}: ParameterControlsProps) {
  if (schema.length === 0) {
    return null;
  }

  return (
    <div className={cn('space-y-3 rounded-xl border border-border bg-card/60 p-3', className)}>
      {schema.map((parameter) => {
        const value = getDisplayValue(parameter, values[parameter.name]);

        return (
          <div key={parameter.name} className="space-y-2 rounded-lg border border-border/70 bg-background/60 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground">{parameter.label}</div>
                <div className="text-xs text-muted-foreground">{parameter.description}</div>
              </div>
              {parameter.type === 'number' && (
                <div className="shrink-0 text-xs font-medium text-muted-foreground">{String(value)}</div>
              )}
              {parameter.type === 'audio-binding' && isAudioBindingValue(value) && (
                <div className="shrink-0 text-right text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {value.source} {value.min}→{value.max}
                </div>
              )}
            </div>

            {parameter.type === 'number' && (
              <Slider
                min={parameter.min ?? 0}
                max={parameter.max ?? 100}
                step={parameter.step ?? 1}
                value={typeof value === 'number' ? value : Number(value) || 0}
                onValueChange={(nextValue) => onChange(parameter.name, nextValue)}
                disabled={disabled}
              />
            )}

            {parameter.type === 'select' && (
              <Select
                value={typeof value === 'string' ? value : String(value)}
                onValueChange={(nextValue) => onChange(parameter.name, nextValue)}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an option" />
                </SelectTrigger>
                <SelectContent>
                  {(parameter.options ?? []).map((option) => (
                    <SelectItem key={`${parameter.name}:${option.value}`} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {parameter.type === 'boolean' && (
              <div className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2">
                <div className="text-sm text-foreground">{(value as boolean) ? 'Enabled' : 'Disabled'}</div>
                <Switch
                  checked={Boolean(value)}
                  onCheckedChange={(nextValue) => onChange(parameter.name, nextValue)}
                  disabled={disabled}
                />
              </div>
            )}

            {parameter.type === 'color' && (
              <div className="flex items-center gap-3">
                <Input
                  type="color"
                  value={typeof value === 'string' ? value : String(value)}
                  onChange={(event) => onChange(parameter.name, event.target.value)}
                  disabled={disabled}
                  className="h-10 w-16 cursor-pointer p-1"
                />
                <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {String(value)}
                </div>
              </div>
            )}

            {parameter.type === 'audio-binding' && isAudioBindingValue(value) && (
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Source</div>
                  <Select
                    value={value.source}
                    onValueChange={(nextValue) => {
                      if (AUDIO_SOURCES.includes(nextValue as AudioBindingValue['source'])) {
                        onChange(parameter.name, {
                          ...value,
                          source: nextValue as AudioBindingValue['source'],
                        });
                      }
                    }}
                    disabled={disabled}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select audio source" />
                    </SelectTrigger>
                    <SelectContent>
                      {AUDIO_SOURCES.map((source) => (
                        <SelectItem key={`${parameter.name}:${source}`} value={source}>
                          {source}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Min</div>
                  <NumberInput
                    value={value.min}
                    step={0.1}
                    onChange={(nextValue) => {
                      if (nextValue !== null) {
                        onChange(parameter.name, { ...value, min: nextValue });
                      }
                    }}
                    disabled={disabled}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Max</div>
                  <NumberInput
                    value={value.max}
                    step={0.1}
                    onChange={(nextValue) => {
                      if (nextValue !== null) {
                        onChange(parameter.name, { ...value, max: nextValue });
                      }
                    }}
                    disabled={disabled}
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
