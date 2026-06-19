/**
 * M9: KeyframeInspector — Host-owned keyframe inspector controls.
 *
 * Provides UI for adding/removing keyframes at the playhead, editing
 * keyframe values, choosing linear/hold interpolation, and showing the
 * current interpolated value for each parameter.
 *
 * Persists through existing clip patching via the `onChange` callback
 * which receives an updated `Record<string, ClipKeyframe[]>`.
 */

import { useMemo, useCallback } from 'react';
import { Button } from '@/shared/components/ui/button.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Input } from '@/shared/components/ui/input.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { Plus, Trash2, GripVertical } from 'lucide-react';
import type {
  ClipKeyframe,
  KeyframeInterpolation,
  ParameterDefinition,
  ParameterSchema,
} from '@/tools/video-editor/types/index.ts';
import {
  resolveAnimatedParams,
  validateKeyframes,
  type InterpolatedParam,
  type KeyframeValidationDiagnostic,
} from '@/tools/video-editor/keyframes/index.ts';

// ---------------------------------------------------------------------------
// Public props
// ---------------------------------------------------------------------------

export interface KeyframeInspectorProps {
  /** Parameter schema defining the keyframe-able parameters. */
  schema: ParameterSchema;
  /** Current keyframe data keyed by parameter name. */
  keyframes: Record<string, ClipKeyframe[]>;
  /** Current playhead time in seconds. */
  currentTime: number;
  /** Called with updated keyframes record when user edits keyframes. */
  onChange: (keyframes: Record<string, ClipKeyframe[]>) => void;
  /** Disable all controls. */
  disabled?: boolean;
  /** Additional CSS class on the root wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Keyframe value editor helpers
// ---------------------------------------------------------------------------

interface KeyframeRowProps {
  kf: ClipKeyframe;
  definition: ParameterDefinition;
  index: number;
  onChange: (index: number, patch: Partial<ClipKeyframe>) => void;
  onRemove: (index: number) => void;
  disabled?: boolean;
}

function KeyframeRow({
  kf,
  definition,
  index,
  onChange,
  onRemove,
  disabled,
}: KeyframeRowProps) {
  const handleValueChange = useCallback(
    (nextValue: unknown) => {
      onChange(index, { value: nextValue as ClipKeyframe['value'] });
    },
    [index, onChange],
  );

  const handleInterpolationChange = useCallback(
    (nextInterp: string) => {
      onChange(index, { interpolation: nextInterp as KeyframeInterpolation });
    },
    [index, onChange],
  );

  const handleTimeChange = useCallback(
    (nextTime: number | null) => {
      if (nextTime !== null && Number.isFinite(nextTime)) {
        onChange(index, { time: nextTime });
      }
    },
    [index, onChange],
  );

  const valueEditor = useMemo(() => {
    switch (definition.type) {
      case 'number':
        return (
          <NumberInput
            value={typeof kf.value === 'number' ? kf.value : 0}
            min={definition.min}
            max={definition.max}
            step={definition.step ?? 0.1}
            onChange={(value) => {
              if (value !== null) handleValueChange(value);
            }}
            disabled={disabled}
          />
        );
      case 'boolean':
        return (
          <Select
            value={String(kf.value)}
            onValueChange={(v) => handleValueChange(v === 'true')}
            disabled={disabled}
          >
            <SelectTrigger className="h-8 w-[120px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">true</SelectItem>
              <SelectItem value="false">false</SelectItem>
            </SelectContent>
          </Select>
        );
      case 'color':
        return (
          <div className="flex items-center gap-1">
            <Input
              type="color"
              value={typeof kf.value === 'string' ? kf.value : '#000000'}
              onChange={(e) => handleValueChange(e.target.value)}
              className="h-8 w-8 p-0.5"
              disabled={disabled}
            />
            <Input
              value={typeof kf.value === 'string' ? kf.value : ''}
              onChange={(e) => handleValueChange(e.target.value)}
              className="h-8 w-[80px] text-xs font-mono"
              disabled={disabled}
            />
          </div>
        );
      case 'select':
        return (
          <Select
            value={typeof kf.value === 'string' ? kf.value : ''}
            onValueChange={handleValueChange}
            disabled={disabled}
          >
            <SelectTrigger className="h-8 min-w-[100px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(definition.options ?? []).map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      default:
        return (
          <Input
            value={String(kf.value ?? '')}
            onChange={(e) => {
              const str = e.target.value;
              // Try to parse as number if the definition expects a number-like string
              if (definition.type === 'number') {
                const num = Number(str);
                if (!Number.isNaN(num)) handleValueChange(num);
              } else {
                handleValueChange(str);
              }
            }}
            className="h-8 text-xs"
            disabled={disabled}
          />
        );
    }
  }, [definition, kf.value, disabled, handleValueChange]);

  return (
    <div
      className="flex items-center gap-2 rounded-md border border-border/50 bg-background/50 px-2 py-1.5"
      data-testid="keyframe-row"
    >
      <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
      <span className="text-[10px] text-muted-foreground w-6 shrink-0">#{index}</span>
      <div className="w-[70px] shrink-0">
        <NumberInput
          value={kf.time}
          min={0}
          step={0.05}
          onChange={handleTimeChange}
          disabled={disabled}
        />
      </div>
      <span className="text-[10px] text-muted-foreground shrink-0">s</span>
      <div className="flex-1 min-w-0">{valueEditor}</div>
      <Select
        value={kf.interpolation}
        onValueChange={handleInterpolationChange}
        disabled={disabled}
      >
        <SelectTrigger className="h-8 w-[80px] text-xs shrink-0">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="linear">linear</SelectItem>
          <SelectItem value="hold">hold</SelectItem>
        </SelectContent>
      </Select>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-7 w-7 shrink-0 text-destructive hover:text-destructive"
        onClick={() => onRemove(index)}
        disabled={disabled}
        aria-label={`Remove keyframe at index ${index}`}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Parameter section (one per schema entry)
// ---------------------------------------------------------------------------

interface ParameterKeyframeSectionProps {
  definition: ParameterDefinition;
  keyframes: ClipKeyframe[];
  interpolatedValue: number | string | boolean;
  currentTime: number;
  onChange: (keyframes: ClipKeyframe[]) => void;
  disabled?: boolean;
}

function ParameterKeyframeSection({
  definition,
  keyframes,
  interpolatedValue,
  currentTime,
  onChange,
  disabled,
}: ParameterKeyframeSectionProps) {
  const validation = useMemo(
    () => validateKeyframes(keyframes, definition),
    [keyframes, definition],
  );

  const hasError = validation.some((d) => d.severity === 'error');
  const warnings = validation.filter((d) => d.severity === 'warning');

  const handleAddAtPlayhead = useCallback(() => {
    // Use the current interpolated value as the default for the new keyframe
    onChange([
      ...keyframes,
      {
        time: currentTime,
        value: interpolatedValue,
        interpolation: 'linear' as KeyframeInterpolation,
      },
    ]);
  }, [keyframes, currentTime, interpolatedValue, onChange]);

  const handleRowChange = useCallback(
    (index: number, patch: Partial<ClipKeyframe>) => {
      const next = [...keyframes];
      next[index] = { ...next[index], ...patch };
      // Sort by time after change
      next.sort((a, b) => a.time - b.time);
      onChange(next);
    },
    [keyframes, onChange],
  );

  const handleRemove = useCallback(
    (index: number) => {
      const next = keyframes.filter((_, i) => i !== index);
      onChange(next);
    },
    [keyframes, onChange],
  );

  const interpolatedDisplay = useMemo(() => {
    if (definition.type === 'color' && typeof interpolatedValue === 'string') {
      return (
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-3.5 w-3.5 rounded border border-border"
            style={{ backgroundColor: interpolatedValue }}
          />
          <span className="font-mono text-[11px]">{interpolatedValue}</span>
        </span>
      );
    }
    return <span className="font-mono text-[11px]">{String(interpolatedValue)}</span>;
  }, [definition.type, interpolatedValue]);

  return (
    <div
      className="space-y-2 rounded-lg border border-border/70 bg-background/60 p-3"
      data-testid="keyframe-parameter-section"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">
            {definition.label || definition.name}
          </div>
          <div className="text-xs text-muted-foreground">
            {definition.description}
          </div>
        </div>
        <div className="shrink-0 text-right text-xs text-muted-foreground">
          <div>At playhead: {interpolatedDisplay}</div>
          <div className="text-[10px]">
            {keyframes.length} keyframe{keyframes.length === 1 ? '' : 's'}
          </div>
        </div>
      </div>

      {/* Validation warnings */}
      {hasError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1 text-xs text-destructive">
          {validation
            .filter((d) => d.severity === 'error')
            .map((d, i) => (
              <div key={i}>{d.message}</div>
            ))}
        </div>
      )}
      {warnings.length > 0 && !hasError && (
        <div className="rounded-md border border-amber-400/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-200">
          {warnings.map((d, i) => (
            <div key={i}>{d.message}</div>
          ))}
        </div>
      )}

      {/* Keyframe rows */}
      {keyframes.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 px-2 text-[10px] text-muted-foreground uppercase tracking-wider">
            <span className="w-[88px] shrink-0">Time</span>
            <span className="flex-1">Value</span>
            <span className="w-[80px] shrink-0">Interp</span>
            <span className="w-7" />
          </div>
          {keyframes.map((kf, i) => (
            <KeyframeRow
              key={`${kf.time}-${i}`}
              kf={kf}
              definition={definition}
              index={i}
              onChange={handleRowChange}
              onRemove={handleRemove}
              disabled={disabled}
            />
          ))}
        </div>
      )}

      {/* Add keyframe button */}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1.5 text-xs"
        onClick={handleAddAtPlayhead}
        disabled={disabled}
      >
        <Plus className="h-3.5 w-3.5" />
        Add keyframe at {currentTime.toFixed(2)}s
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KeyframeInspector
// ---------------------------------------------------------------------------

export function KeyframeInspector({
  schema,
  keyframes,
  currentTime,
  onChange,
  disabled = false,
  className,
}: KeyframeInspectorProps) {
  const interpolatedParams = useMemo(
    () => resolveAnimatedParams(keyframes, schema, currentTime),
    [keyframes, schema, currentTime],
  );

  const interpolatedByParam = useMemo(() => {
    const map = new Map<string, number | string | boolean>();
    for (const param of interpolatedParams) {
      map.set(param.name, param.value);
    }
    return map;
  }, [interpolatedParams]);

  const handleParamChange = useCallback(
    (paramName: string, nextKeyframes: ClipKeyframe[]) => {
      const next = { ...keyframes };
      if (nextKeyframes.length === 0) {
        delete next[paramName];
      } else {
        next[paramName] = nextKeyframes;
      }
      onChange(next);
    },
    [keyframes, onChange],
  );

  if (schema.length === 0) {
    return (
      <div className={cn('rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground', className)}>
        No keyframe-able parameters defined for this clip type.
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-foreground">Keyframes</div>
        <div className="text-[11px] text-muted-foreground">
          Playhead: {currentTime.toFixed(2)}s
        </div>
      </div>
      {schema.map((definition) => (
        <ParameterKeyframeSection
          key={definition.name}
          definition={definition}
          keyframes={keyframes[definition.name] ?? []}
          interpolatedValue={
            interpolatedByParam.get(definition.name) ??
            definition.default ??
            (definition.type === 'number' ? 0 : definition.type === 'boolean' ? false : '')
          }
          currentTime={currentTime}
          onChange={(nextKeyframes) => handleParamChange(definition.name, nextKeyframes)}
          disabled={disabled}
        />
      ))}
    </div>
  );
}
