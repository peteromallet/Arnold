import type { AudioBindingValue, ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';

export interface ParameterControlsProps {
  schema: ParameterSchema;
  values: Record<string, unknown>;
  onChange: (name: string, value: unknown) => void;
  disabled?: boolean;
  className?: string;
  /** Registry-level diagnostics to display above the parameter fields. */
  diagnostics?: readonly ExtensionDiagnostic[];
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

/**
 * Thin adapter over {@link SchemaForm} that preserves the existing
 * {@link ParameterControlsProps} contract.
 *
 * Delegates all rendering to SchemaForm while keeping the same
 * controlled `values` / `onChange(name, value)` / `disabled` /
 * `className` semantics.
 */
export function ParameterControls({
  schema,
  values,
  onChange,
  disabled = false,
  className,
  diagnostics,
}: ParameterControlsProps) {
  return (
    <SchemaForm
      schema={schema}
      values={values}
      onChange={onChange}
      disabled={disabled}
      className={className}
      diagnostics={diagnostics}
    />
  );
}
