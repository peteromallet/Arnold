import type { AudioBindingValue, ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types/index.ts';

const COLOR_RE = /^#[0-9a-f]{3,8}$/i;
const AUDIO_SOURCES = new Set<AudioBindingValue['source']>(['bass', 'mid', 'treble', 'amplitude']);

const getFallbackValue = (parameter: ParameterDefinition): number | string | boolean | AudioBindingValue => {
  if (parameter.default !== undefined) return parameter.default;
  if (parameter.type === 'number') return parameter.min ?? 0;
  if (parameter.type === 'select') return parameter.options?.[0]?.value ?? '';
  if (parameter.type === 'boolean') return false;
  if (parameter.type === 'audio-binding') return { source: 'amplitude', min: 0, max: 1 };
  if (parameter.type === 'color') return '#000000';
  return '';
};

export function validateAndCoerceParams(
  params: Record<string, unknown> | undefined,
  schema: ParameterSchema | undefined,
): Record<string, unknown> {
  if (!schema?.length) return params ?? {};
  return schema.reduce<Record<string, unknown>>((result, parameter) => {
    const fallback = getFallbackValue(parameter);
    const value = params?.[parameter.name];
    if (parameter.type === 'number') {
      result[parameter.name] = typeof value === 'number' && Number.isFinite(value)
        ? Math.max(parameter.min ?? -Number.MAX_VALUE, Math.min(parameter.max ?? Number.MAX_VALUE, value))
        : fallback;
    } else if (parameter.type === 'boolean') {
      result[parameter.name] = typeof value === 'boolean' ? value : fallback;
    } else if (parameter.type === 'select') {
      result[parameter.name] = typeof value === 'string' && (parameter.options ?? []).some((option) => option.value === value) ? value : fallback;
    } else if (parameter.type === 'audio-binding') {
      const source = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).source : undefined;
      const min = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).min : undefined;
      const max = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).max : undefined;
      result[parameter.name] = (
        typeof source === 'string'
        && AUDIO_SOURCES.has(source as AudioBindingValue['source'])
        && typeof min === 'number'
        && Number.isFinite(min)
        && typeof max === 'number'
        && Number.isFinite(max)
      )
        ? { source, min, max }
        : fallback;
    } else {
      result[parameter.name] = typeof value === 'string' && COLOR_RE.test(value) ? value : fallback;
    }
    return result;
  }, { ...(params ?? {}) });
}
