/**
 * SchemaForm — Controlled form component for parameter editing.
 *
 * Accepts both the existing `ParameterSchema` (array of
 * {@link ParameterDefinition}) and the minimal StandardSchema
 * object/property subset.  Resolves widget rendering through the
 * host schema capability registry; unsupported types render as
 * diagnostic placeholders and publish via `onDiagnostics`.
 *
 * This is the canonical parameter form for M2+.  `ParameterControls`
 * is a thin adapter wrapper over this component.
 *
 * @module SchemaForm
 */

import { useMemo, useEffect } from 'react';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { Switch } from '@/shared/components/ui/switch.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import type { AudioBindingValue, ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { ShaderUniformSchema } from '@reigh/editor-sdk';
import {
  createSchemaCapabilityRegistry,
  type SchemaCapabilityRegistry,
  type SchemaCapabilityEntry,
} from '@/tools/video-editor/runtime/schemaCapabilityRegistry';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Minimal StandardSchema subset
// ---------------------------------------------------------------------------

/** A single property definition in the minimal StandardSchema subset. */
export interface StandardSchemaProperty {
  type: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: Array<string | number>;
  minimum?: number;
  maximum?: number;
  multipleOf?: number;
}

/** Minimal StandardSchema object schema — only `object` with `properties`. */
export interface StandardSchema {
  type: 'object';
  properties: Record<string, StandardSchemaProperty>;
  required?: string[];
}

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** Union of schema formats accepted by SchemaForm. */
export type SchemaFormSchema = ParameterSchema | StandardSchema | ShaderUniformSchema;

/** Props for SchemaForm.  Mirrors ParameterControlsProps + extensions. */
export interface SchemaFormProps {
  /** Parameter schema (array) or minimal StandardSchema object. */
  schema: SchemaFormSchema;
  /** Current parameter values keyed by name. */
  values: Record<string, unknown>;
  /** Called when any parameter value changes.  Signature: (name, value). */
  onChange: (name: string, value: unknown) => void;
  /** Disable all form controls. */
  disabled?: boolean;
  /** Additional CSS class on the root wrapper. */
  className?: string;
  /**
   * Schema capability registry for widget resolution.
   * Defaults to a fresh built-in registry if not provided.
   */
  capabilityRegistry?: SchemaCapabilityRegistry;
  /**
   * Callback invoked with diagnostics for unsupported / blocked types.
   * Called once on mount and whenever schema or registry changes.
   */
  onDiagnostics?: (diagnostics: ExtensionDiagnostic[]) => void;
  /**
   * Pre-existing diagnostics to display at the top of the form (e.g. from
   * registry-level schema validation). Each diagnostic is rendered as an
   * alert row showing the diagnostic message.
   */
  diagnostics?: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Internal normalised field
// ---------------------------------------------------------------------------

interface NormalizedField {
  name: string;
  label: string;
  description: string;
  type: string;
  default?: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: Array<{ label: string; value: string }>;
  isRequired: boolean;
  _source: 'parameter' | 'standardschema' | 'shader';
  _capability: SchemaCapabilityEntry;
}

// ---------------------------------------------------------------------------
// Audio-binding helpers (mirrors ParameterControls)
// ---------------------------------------------------------------------------

const AUDIO_SOURCES: Array<AudioBindingValue['source']> = ['bass', 'mid', 'treble', 'amplitude'];

function isAudioBindingValue(value: unknown): value is AudioBindingValue {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.source === 'string'
    && AUDIO_SOURCES.includes(candidate.source as AudioBindingValue['source'])
    && typeof candidate.min === 'number'
    && typeof candidate.max === 'number'
  );
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function getVectorLength(type: string): number | null {
  switch (type) {
    case 'vec2':
      return 2;
    case 'vec3':
      return 3;
    case 'vec4':
      return 4;
    case 'color':
      return 4;
    default:
      return null;
  }
}

function isNumberVector(value: unknown, length: number): value is number[] {
  return Array.isArray(value) && value.length === length && value.every(isFiniteNumber);
}

function getVectorFallback(field: NormalizedField): number[] {
  const length = getVectorLength(field.type) ?? 0;
  if (isNumberVector(field.default, length)) {
    return [...field.default];
  }
  if (field.type === 'color') {
    return [1, 1, 1, 1];
  }
  return Array.from({ length }, () => 0);
}

function isShaderColorValue(field: NormalizedField, value: unknown): value is number[] {
  return field.type === 'color' && Array.isArray(value);
}

// ---------------------------------------------------------------------------
// Fallback values (mirrors ParameterControls)
// ---------------------------------------------------------------------------

function getFallbackValue(field: NormalizedField): unknown {
  if (field.default !== undefined) return field.default;
  switch (field.type) {
    case 'float':
    case 'frame':
    case 'time':
      return field.min ?? 0;
    case 'int':
      return Math.trunc(field.min ?? 0);
    case 'vec2':
    case 'vec3':
    case 'vec4':
      return getVectorFallback(field);
    case 'enum':
      return field.options?.[0]?.value ?? '';
    case 'bool':
      return false;
    case 'number':
      return field.min ?? 0;
    case 'select':
      return field.options?.[0]?.value ?? '';
    case 'boolean':
      return false;
    case 'audio-binding':
      return { source: 'amplitude', min: 0, max: 1 };
    case 'color':
      return '#000000';
    case 'string':
      return '';
    default:
      return '';
  }
}

function getDisplayValue(field: NormalizedField, value: unknown): unknown {
  if (value !== undefined) {
    if (field.type === 'audio-binding') {
      return isAudioBindingValue(value) ? value : getFallbackValue(field);
    }
    const vectorLength = getVectorLength(field.type);
    if (vectorLength !== null && Array.isArray(value)) {
      return isNumberVector(value, vectorLength) ? value : getVectorFallback(field);
    }
    return value;
  }
  return getFallbackValue(field);
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validateField(field: NormalizedField, value: unknown, registry: SchemaCapabilityRegistry): string | null {
  for (const [, entry] of registry.validationPaths) {
    const result = entry.validate(value, {
      name: field.name,
      label: field.label,
      description: field.description,
      type: field.type as ParameterDefinition['type'],
      default: field.default as ParameterDefinition['default'],
      min: field.min,
      max: field.max,
      step: field.step,
      options: field.options,
    });
    if (result !== null) return result;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Schema normalization
// ---------------------------------------------------------------------------

function normalizeSchema(
  schema: SchemaFormSchema,
  registry: SchemaCapabilityRegistry,
): NormalizedField[] {
  if (Array.isArray(schema)) {
    // ParameterSchema / ShaderUniformSchema — arrays of field definitions
    return schema.map((param) => {
      const capability = registry.resolve(param.type);
      const type = param.type;
      const isShader = (
        type === 'float'
        || type === 'int'
        || type === 'bool'
        || type === 'vec2'
        || type === 'vec3'
        || type === 'vec4'
        || type === 'enum'
        || type === 'textureRef'
        || type === 'frame'
        || type === 'time'
        || (type === 'color' && Array.isArray(param.default))
      );
      return {
        name: param.name,
        label: param.label,
        description: param.description ?? '',
        type,
        default: param.default,
        min: param.min,
        max: param.max,
        step: param.step,
        options: param.options ? Array.from(param.options) : undefined,
        isRequired: true,
        _source: isShader ? 'shader' as const : 'parameter' as const,
        _capability: capability,
      };
    });
  }

  // StandardSchema — object with properties
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties).map(([name, prop]) => {
    const capability = registry.resolve(prop.type);
    return {
      name,
      label: prop.title ?? name,
      description: prop.description ?? '',
      type: prop.type,
      default: prop.default,
      min: prop.minimum,
      max: prop.maximum,
      step: prop.multipleOf,
      options: prop.enum?.map((v) => ({ label: String(v), value: String(v) })),
      isRequired: required.has(name),
      _source: 'standardschema' as const,
      _capability: capability,
    };
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Controlled schema-driven form.
 *
 * Accepts {@link ParameterSchema} or minimal {@link StandardSchema},
 * resolves each field's widget via the schema capability registry, and
 * renders unsupported types as accessible diagnostic placeholders.
 *
 * `onChange(name, value)` fires for every value change, matching the
 * {@link ParameterControls} contract exactly.
 */
export function SchemaForm({
  schema,
  values,
  onChange,
  disabled = false,
  className,
  capabilityRegistry,
  onDiagnostics,
  diagnostics,
}: SchemaFormProps) {
  const registry = useMemo(
    () => capabilityRegistry ?? createSchemaCapabilityRegistry(),
    [capabilityRegistry],
  );

  const fields = useMemo(() => normalizeSchema(schema, registry), [schema, registry]);

  // Emit diagnostics for unsupported types
  useEffect(() => {
    if (!onDiagnostics) return;
    const diagnostics: ExtensionDiagnostic[] = [];
    for (const field of fields) {
      if (field._capability.status === 'unsupported' && field._capability.diagnostic) {
        diagnostics.push({ ...field._capability.diagnostic, detail: { ...field._capability.diagnostic.detail, fieldName: field.name } });
      }
    }
    if (diagnostics.length > 0) {
      onDiagnostics(diagnostics);
    }
  }, [fields, onDiagnostics]);

  // Render diagnostics even when there are no fields (pure schema-level errors)
  const hasDiagnostics = diagnostics && diagnostics.length > 0;

  if (fields.length === 0) {
    if (hasDiagnostics) {
      return (
        <div
          className={cn('space-y-3 rounded-xl border border-border bg-card/60 p-3', className)}
          data-testid="schema-form"
        >
          {diagnostics!.map((diag, idx) => (
            <div
              key={`schema-diag-${idx}`}
              className="rounded-lg border border-destructive/40 bg-destructive/5 p-3"
              data-testid={`schema-form-diagnostic-${idx}`}
              role="alert"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-destructive">
                    Schema validation error
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {diag.message}
                  </div>
                </div>
                <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-destructive">
                  Error
                </span>
              </div>
            </div>
          ))}
        </div>
      );
    }
    return null;
  }

  return (
    <div
      className={cn('space-y-3 rounded-xl border border-border bg-card/60 p-3', className)}
      data-testid="schema-form"
    >
      {/* Render registry-level diagnostics above the parameter fields */}
      {hasDiagnostics && diagnostics!.map((diag, idx) => (
        <div
          key={`schema-diag-${idx}`}
          className="rounded-lg border border-destructive/40 bg-destructive/5 p-3"
          data-testid={`schema-form-diagnostic-${idx}`}
          role="alert"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium text-destructive">
                Schema validation error
              </div>
              <div className="text-xs text-muted-foreground">
                {diag.message}
              </div>
            </div>
            <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-destructive">
              Error
            </span>
          </div>
        </div>
      ))}

      {fields.map((field) => {
        const rawValue = values[field.name];
        const value = getDisplayValue(field, rawValue);
        const errorMessage = validateField(field, rawValue, registry);

        // ---- Unsupported type: diagnostic placeholder ----
        if (field._capability.status === 'unsupported') {
          return (
            <div
              key={field.name}
              className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3"
              data-testid={`schema-form-unsupported-${field.name}`}
              data-field-type={field.type}
              role="alert"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-destructive">
                    {field.label}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {field.description || `Unsupported type: ${field.type}`}
                  </div>
                </div>
                <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-destructive">
                  Unsupported
                </span>
              </div>
              {field._capability.diagnostic && (
                <div
                  className="rounded-md bg-background/60 px-3 py-2 text-xs text-muted-foreground"
                  data-testid={`schema-form-diagnostic-${field.name}`}
                >
                  {field._capability.diagnostic.message}
                </div>
              )}
            </div>
          );
        }

        // ---- Custom placeholder (e.g. audio-binding) ----
        const isCustom = field._capability.status === 'custom';

        return (
          <div
            key={field.name}
            className={cn(
              'space-y-2 rounded-lg border border-border/70 bg-background/60 p-3',
              isCustom && 'ring-1 ring-amber-500/20',
            )}
            data-testid={`schema-form-field-${field.name}`}
            data-field-type={field.type}
            data-field-status={field._capability.status}
          >
            {/* Label row */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground">
                  {field.label}
                  {isCustom && (
                    <span className="ml-2 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-600">
                      Custom
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">{field.description}</div>
              </div>
              {/* Value badge for certain types */}
              {field._capability.widgetType === 'slider' && typeof value === 'number' && (
                <div className="shrink-0 text-xs font-medium text-muted-foreground">{String(value)}</div>
              )}
              {field.type === 'audio-binding' && isAudioBindingValue(value) && (
                <div className="shrink-0 text-right text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {value.source} {value.min}→{value.max}
                </div>
              )}
            </div>

            {/* Validation error */}
            {errorMessage && (
              <div
                className="rounded-md bg-destructive/10 px-3 py-1.5 text-xs text-destructive"
                data-testid={`schema-form-error-${field.name}`}
                role="alert"
              >
                {errorMessage}
              </div>
            )}

            {/* ---- Widgets ---- */}

            {/* Text widget (string) */}
            {field._capability.widgetType === 'text' && (
              <input
                type="text"
                value={typeof value === 'string' ? value : String(value ?? '')}
                onChange={(event) => onChange(field.name, event.target.value)}
                disabled={disabled}
                data-testid={`schema-form-widget-${field.name}`}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            )}

            {/* Slider widget (number) */}
            {field._capability.widgetType === 'slider' && (
              <Slider
                min={field.min ?? 0}
                max={field.max ?? 100}
                step={field.step ?? 1}
                value={typeof value === 'number' ? value : Number(value) || 0}
                onValueChange={(nextValue) => onChange(field.name, nextValue)}
                disabled={disabled}
                data-testid={`schema-form-widget-${field.name}`}
              />
            )}

            {/* Compact shader scalar widget */}
            {field._capability.widgetType === 'shader-number' && (
              <input
                type="number"
                inputMode={field.type === 'int' || field.type === 'frame' ? 'numeric' : 'decimal'}
                value={typeof value === 'number' ? value : Number(value) || 0}
                min={field.min}
                max={field.max}
                step={field.step ?? (field.type === 'int' || field.type === 'frame' ? 1 : 0.01)}
                onChange={(event) => {
                  const nextValue = Number(event.target.value);
                  if (Number.isFinite(nextValue)) {
                    onChange(field.name, field.type === 'int' ? Math.trunc(nextValue) : nextValue);
                  }
                }}
                disabled={disabled}
                data-testid={`schema-form-widget-${field.name}`}
                className="flex h-9 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm tabular-nums ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            )}

            {/* Number widget (fallback for number without slider — StandardSchema number with widgetType 'number') */}
            {field._capability.widgetType === 'number' && (
              <NumberInput
                value={typeof value === 'number' ? value : 0}
                min={field.min}
                max={field.max}
                step={field.step ?? 1}
                onChange={(nextValue) => {
                  if (nextValue !== null) onChange(field.name, nextValue);
                }}
                disabled={disabled}
                data-testid={`schema-form-widget-${field.name}`}
              />
            )}

            {/* Boolean widget */}
            {field._capability.widgetType === 'boolean' && (
              <div className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2">
                <div className="text-sm text-foreground">
                  {value ? 'Enabled' : 'Disabled'}
                </div>
                <Switch
                  checked={Boolean(value)}
                  onCheckedChange={(nextValue) => onChange(field.name, nextValue)}
                  disabled={disabled}
                  data-testid={`schema-form-widget-${field.name}`}
                />
              </div>
            )}

            {/* Compact shader vector widget */}
            {(field._capability.widgetType === 'vector' || isShaderColorValue(field, value)) && (() => {
              const vectorLength = getVectorLength(field.type) ?? 0;
              const vectorValue = isNumberVector(value, vectorLength) ? value : getVectorFallback(field);
              const labels = field.type === 'color'
                ? ['r', 'g', 'b', 'a']
                : ['x', 'y', 'z', 'w'].slice(0, vectorLength);

              return (
                <div
                  className="grid gap-2"
                  style={{ gridTemplateColumns: `repeat(${Math.max(vectorLength, 1)}, minmax(0, 1fr))` }}
                >
                  {labels.map((label, index) => (
                    <label key={`${field.name}:${label}`} className="min-w-0 space-y-1">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        {label}
                      </span>
                      <input
                        type="number"
                        inputMode="decimal"
                        value={vectorValue[index] ?? 0}
                        step={field.step ?? 0.01}
                        min={field.min}
                        max={field.max}
                        onChange={(event) => {
                          const nextComponent = Number(event.target.value);
                          if (!Number.isFinite(nextComponent)) return;
                          const nextValue = [...vectorValue];
                          nextValue[index] = nextComponent;
                          onChange(field.name, nextValue);
                        }}
                        disabled={disabled}
                        data-testid={`schema-form-widget-${field.name}-${label}`}
                        className="h-9 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm tabular-nums ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                  ))}
                </div>
              );
            })()}

            {/* Select widget */}
            {field._capability.widgetType === 'select' && (
              <Select
                value={typeof value === 'string' ? value : String(value)}
                onValueChange={(nextValue) => onChange(field.name, nextValue)}
                disabled={disabled}
              >
                <SelectTrigger data-testid={`schema-form-widget-${field.name}`}>
                  <SelectValue placeholder="Select an option" />
                </SelectTrigger>
                <SelectContent>
                  {(field.options ?? []).map((option) => (
                    <SelectItem key={`${field.name}:${option.value}`} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Color widget */}
            {field._capability.widgetType === 'color' && !isShaderColorValue(field, value) && (
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={typeof value === 'string' ? value : String(value)}
                  onChange={(event) => onChange(field.name, event.target.value)}
                  disabled={disabled}
                  data-testid={`schema-form-widget-${field.name}`}
                  className="h-10 w-16 cursor-pointer p-1"
                />
                <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {String(value)}
                </div>
              </div>
            )}

            {/* Audio-binding custom widget (mirrors ParameterControls) */}
            {field.type === 'audio-binding' && isAudioBindingValue(value) && (
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Source</div>
                  <Select
                    value={value.source}
                    onValueChange={(nextValue) => {
                      if (AUDIO_SOURCES.includes(nextValue as AudioBindingValue['source'])) {
                        onChange(field.name, {
                          ...value,
                          source: nextValue as AudioBindingValue['source'],
                        });
                      }
                    }}
                    disabled={disabled}
                  >
                    <SelectTrigger data-testid={`schema-form-widget-${field.name}-source`}>
                      <SelectValue placeholder="Select audio source" />
                    </SelectTrigger>
                    <SelectContent>
                      {AUDIO_SOURCES.map((source) => (
                        <SelectItem key={`${field.name}:${source}`} value={source}>
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
                        onChange(field.name, { ...value, min: nextValue });
                      }
                    }}
                    disabled={disabled}
                    data-testid={`schema-form-widget-${field.name}-min`}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Max</div>
                  <NumberInput
                    value={value.max}
                    step={0.1}
                    onChange={(nextValue) => {
                      if (nextValue !== null) {
                        onChange(field.name, { ...value, max: nextValue });
                      }
                    }}
                    disabled={disabled}
                    data-testid={`schema-form-widget-${field.name}-max`}
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
