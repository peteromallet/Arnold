import type { ShaderUniformSchema } from '@reigh/editor-sdk';
import { canonicalizeShaderUniformPath } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import type {
  TimelineShaderKeyframe,
  TimelineShaderUniformKeyframes,
  TimelineShaderUniformValues,
} from '@/tools/video-editor/types/index.ts';

type ShaderKeyframeValue = TimelineShaderKeyframe['value'];

function interpolateScalar(
  from: number | string | boolean,
  to: number | string | boolean,
  factor: number,
  interpolation: TimelineShaderKeyframe['interpolation'],
): number | string | boolean {
  if (interpolation === 'hold') {
    return factor < 1 ? from : to;
  }
  if (typeof from === 'number' && typeof to === 'number') {
    return from + (to - from) * factor;
  }
  return factor < 1 ? from : to;
}

function interpolateVector(
  from: readonly number[],
  to: readonly number[],
  factor: number,
  interpolation: TimelineShaderKeyframe['interpolation'],
): readonly number[] {
  if (interpolation === 'hold') {
    return [...from];
  }
  const size = Math.min(from.length, to.length);
  const next: number[] = [];
  for (let index = 0; index < size; index++) {
    next.push(from[index]! + (to[index]! - from[index]!) * factor);
  }
  return next;
}

function isFiniteNumberArray(value: unknown): value is readonly number[] {
  return Array.isArray(value)
    && value.every((item) => typeof item === 'number' && Number.isFinite(item));
}

function resolveKeyframedValue(
  keyframes: readonly TimelineShaderKeyframe[],
  fallbackValue: unknown,
  timeSeconds: number,
): ShaderKeyframeValue | undefined {
  const valid = keyframes
    .filter((entry) => typeof entry.time === 'number' && Number.isFinite(entry.time))
    .sort((left, right) => left.time - right.time);

  if (valid.length === 0) {
    return fallbackValue as ShaderKeyframeValue | undefined;
  }

  const clampedTime = Math.max(0, timeSeconds);
  const first = valid[0]!;
  const last = valid[valid.length - 1]!;
  if (clampedTime <= first.time) {
    return Array.isArray(first.value) ? [...first.value] : first.value;
  }
  if (clampedTime >= last.time) {
    return Array.isArray(last.value) ? [...last.value] : last.value;
  }

  for (let index = 0; index < valid.length - 1; index++) {
    const from = valid[index]!;
    const to = valid[index + 1]!;
    if (clampedTime < from.time || clampedTime >= to.time) {
      continue;
    }

    const range = to.time - from.time;
    const factor = range > 0 ? (clampedTime - from.time) / range : 0;

    if (isFiniteNumberArray(from.value) && isFiniteNumberArray(to.value)) {
      return interpolateVector(from.value, to.value, factor, from.interpolation);
    }
    if (!Array.isArray(from.value) && !Array.isArray(to.value)) {
      return interpolateScalar(from.value, to.value, factor, from.interpolation);
    }
    return Array.isArray(from.value) ? [...from.value] : from.value;
  }

  return Array.isArray(last.value) ? [...last.value] : last.value;
}

function keyframesForUniform(
  keyframes: TimelineShaderUniformKeyframes | undefined,
  uniformName: string,
): readonly TimelineShaderKeyframe[] | undefined {
  if (!keyframes) {
    return undefined;
  }

  return keyframes[canonicalizeShaderUniformPath(uniformName) ?? uniformName]
    ?? keyframes[`uniforms.${uniformName}`]
    ?? keyframes[uniformName];
}

export function resolveShaderPreviewUniformValues(options: {
  readonly uniforms?: ShaderUniformSchema;
  readonly uniformValues?: TimelineShaderUniformValues;
  readonly keyframes?: TimelineShaderUniformKeyframes;
  readonly timeSeconds: number;
}): Record<string, unknown> {
  const resolved: Record<string, unknown> = { ...(options.uniformValues ?? {}) };

  for (const uniform of options.uniforms ?? []) {
    if (uniform.type === 'textureRef') {
      continue;
    }

    const entries = keyframesForUniform(options.keyframes, uniform.name);
    if (!entries?.length) {
      continue;
    }

    const value = resolveKeyframedValue(entries, resolved[uniform.name], options.timeSeconds);
    if (value !== undefined) {
      resolved[uniform.name] = Array.isArray(value) ? [...value] : value;
    }
  }

  return resolved;
}
