/**
 * M9: Deterministic keyframe utilities.
 *
 * Provides linear/hold interpolation, ParameterDefinition validation
 * diagnostics for keyframe values, resolveAnimatedParams() which
 * computes interpolated parameter values at a given time from
 * host-owned keyframe data, and automation recorder utilities that
 * quantize sampled control values into deterministic keyframes,
 * downsample by tolerance, preserve hold semantics, and reject
 * non-serializable or schema-invalid values.
 *
 * All functions are deterministic — same inputs always produce same outputs.
 */

import type {
  ClipKeyframe,
  KeyframeInterpolation,
  ParameterDefinition,
  ParameterSchema,
} from '../types/index.ts';

// ---------------------------------------------------------------------------
// InterpolatedParam (host-internal shape)
// ---------------------------------------------------------------------------

export interface InterpolatedParam {
  /** The parameter name. */
  name: string;
  /** The interpolated value at the requested time. */
  value: number | string | boolean;
}

// ---------------------------------------------------------------------------
// Validation diagnostics
// ---------------------------------------------------------------------------

export interface KeyframeValidationDiagnostic {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Interpolation helpers
// ---------------------------------------------------------------------------

/**
 * Linearly interpolate between two values.
 *
 * For numbers: standard lerp: a + (b - a) * t.
 * For strings/booleans: behaves like hold — returns `a` when t < 1, `b` when t >= 1.
 * This is deterministic and matches the host's guarantee that non-numeric
 * parameters only meaningfully animate with hold interpolation.
 */
export function interpolateLinear(
  a: number | string | boolean,
  b: number | string | boolean,
  t: number,
): number | string | boolean {
  if (typeof a === 'number' && typeof b === 'number') {
    return a + (b - a) * t;
  }
  // Non-numeric values: discrete step at t=1 boundary
  return t < 1 ? a : b;
}

/**
 * Hold (step) interpolation.
 *
 * Returns `a` for any t < 1, returns `b` when t >= 1.
 */
export function interpolateHold(
  a: number | string | boolean,
  b: number | string | boolean,
  t: number,
): number | string | boolean {
  return t < 1 ? a : b;
}

/**
 * Interpolate between two keyframe values given an interpolation mode.
 */
export function interpolatePair(
  a: number | string | boolean,
  b: number | string | boolean,
  t: number,
  mode: KeyframeInterpolation,
): number | string | boolean {
  if (mode === 'hold') {
    return interpolateHold(a, b, t);
  }
  return interpolateLinear(a, b, t);
}

// ---------------------------------------------------------------------------
// Value coercion / validation
// ---------------------------------------------------------------------------

const isHexColor = (value: string): boolean => /^#[0-9a-fA-F]{3,8}$/.test(value);

/**
 * Validate a single keyframe value against a parameter definition.
 *
 * Returns diagnostics for type mismatches, out-of-range values,
 * invalid colors, invalid select options, and invalid audio-binding shapes.
 * An empty array means the value is valid.
 */
export function validateKeyframeValue(
  value: unknown,
  definition: ParameterDefinition,
): KeyframeValidationDiagnostic[] {
  const diags: KeyframeValidationDiagnostic[] = [];
  const ctx = `parameter "${definition.name}"`;

  // Null / undefined values are invalid for all types
  if (value === null || value === undefined) {
    diags.push({
      severity: 'error',
      code: 'keyframes/invalid-null-value',
      message: `${ctx}: keyframe value must not be null or undefined.`,
      detail: { parameterName: definition.name, value },
    });
    return diags;
  }

  // Type-specific validation
  switch (definition.type) {
    case 'number': {
      if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-number-value',
          message: `${ctx}: expected finite number, got ${typeof value === 'number' ? (Number.isNaN(value) ? 'NaN' : 'Infinity') : typeof value}.`,
          detail: { parameterName: definition.name, value, expectedType: 'number' },
        });
        return diags;
      }
      // Range validation
      if (definition.min !== undefined && value < definition.min) {
        diags.push({
          severity: 'warning',
          code: 'keyframes/value-below-min',
          message: `${ctx}: value ${value} is below min ${definition.min}.`,
          detail: { parameterName: definition.name, value, min: definition.min },
        });
      }
      if (definition.max !== undefined && value > definition.max) {
        diags.push({
          severity: 'warning',
          code: 'keyframes/value-above-max',
          message: `${ctx}: value ${value} is above max ${definition.max}.`,
          detail: { parameterName: definition.name, value, max: definition.max },
        });
      }
      break;
    }

    case 'boolean': {
      if (typeof value !== 'boolean') {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-boolean-value',
          message: `${ctx}: expected boolean, got ${typeof value}.`,
          detail: { parameterName: definition.name, value, expectedType: 'boolean' },
        });
      }
      break;
    }

    case 'select': {
      if (typeof value !== 'string') {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-select-value',
          message: `${ctx}: expected string for select, got ${typeof value}.`,
          detail: { parameterName: definition.name, value, expectedType: 'string' },
        });
        return diags;
      }
      // Check against allowed options
      if (definition.options && definition.options.length > 0) {
        const allowedValues = new Set(definition.options.map((o) => o.value));
        if (!allowedValues.has(value)) {
          diags.push({
            severity: 'warning',
            code: 'keyframes/unknown-select-option',
            message: `${ctx}: value "${value}" is not one of the defined options.`,
            detail: {
              parameterName: definition.name,
              value,
              allowedOptions: Array.from(allowedValues),
            },
          });
        }
      }
      break;
    }

    case 'color': {
      if (typeof value !== 'string') {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-color-value',
          message: `${ctx}: expected hex color string, got ${typeof value}.`,
          detail: { parameterName: definition.name, value, expectedType: 'string (hex color)' },
        });
        return diags;
      }
      if (!isHexColor(value)) {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-color-format',
          message: `${ctx}: "${value}" is not a valid hex color.`,
          detail: { parameterName: definition.name, value },
        });
      }
      break;
    }

    case 'audio-binding': {
      if (typeof value !== 'object' || value === null) {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-audio-binding-value',
          message: `${ctx}: expected AudioBindingValue object, got ${typeof value}.`,
          detail: { parameterName: definition.name, value, expectedType: 'AudioBindingValue' },
        });
        return diags;
      }
      const binding = value as Record<string, unknown>;
      const validSources = ['bass', 'mid', 'treble', 'amplitude'] as const;
      if (!validSources.includes(binding.source as (typeof validSources)[number])) {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-audio-binding-source',
          message: `${ctx}: source must be one of [bass, mid, treble, amplitude].`,
          detail: { parameterName: definition.name, source: binding.source },
        });
      }
      if (typeof binding.min !== 'number') {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-audio-binding-min',
          message: `${ctx}: min must be a number.`,
          detail: { parameterName: definition.name, min: binding.min },
        });
      }
      if (typeof binding.max !== 'number') {
        diags.push({
          severity: 'error',
          code: 'keyframes/invalid-audio-binding-max',
          message: `${ctx}: max must be a number.`,
          detail: { parameterName: definition.name, max: binding.max },
        });
      }
      break;
    }

    default:
      // Unknown type — no validation
      break;
  }

  return diags;
}

/**
 * Validate an entire keyframe array against a parameter definition.
 *
 * In addition to per-value checks, this validates that:
 * - The array is sorted by time
 * - No NaN or infinite times
 * - No NaN or infinite number values
 */
export function validateKeyframes(
  keyframes: ClipKeyframe[],
  definition: ParameterDefinition,
): KeyframeValidationDiagnostic[] {
  const diags: KeyframeValidationDiagnostic[] = [];
  const ctx = `parameter "${definition.name}"`;

  if (!Array.isArray(keyframes)) {
    diags.push({
      severity: 'error',
      code: 'keyframes/invalid-keyframes-array',
      message: `${ctx}: keyframes must be an array.`,
      detail: { parameterName: definition.name, received: typeof keyframes },
    });
    return diags;
  }

  if (keyframes.length === 0) {
    return diags; // Empty array is valid (no animation)
  }

  // Check each keyframe's structure
  for (let i = 0; i < keyframes.length; i++) {
    const kf = keyframes[i];
    const kfCtx = `${ctx}[${i}]`;

    // Required fields
    if (kf === null || kf === undefined || typeof kf !== 'object') {
      diags.push({
        severity: 'error',
        code: 'keyframes/invalid-keyframe-entry',
        message: `${kfCtx}: keyframe entry must be an object.`,
        detail: { parameterName: definition.name, index: i, received: typeof kf },
      });
      continue;
    }

    // time validation
    if (typeof kf.time !== 'number' || Number.isNaN(kf.time) || !Number.isFinite(kf.time)) {
      diags.push({
        severity: 'error',
        code: 'keyframes/invalid-keyframe-time',
        message: `${kfCtx}: time must be a finite number, got ${JSON.stringify(kf.time)}.`,
        detail: { parameterName: definition.name, index: i, time: kf.time },
      });
    }

    // value validation
    if (typeof kf.value === 'number' && (Number.isNaN(kf.value) || !Number.isFinite(kf.value))) {
      diags.push({
        severity: 'error',
        code: 'keyframes/invalid-keyframe-value-nan',
        message: `${kfCtx}: number value must be finite.`,
        detail: { parameterName: definition.name, index: i, value: kf.value },
      });
    }

    // interpolation validation
    const validInterps: KeyframeInterpolation[] = ['linear', 'hold'];
    if (!validInterps.includes(kf.interpolation as KeyframeInterpolation)) {
      diags.push({
        severity: 'error',
        code: 'keyframes/invalid-interpolation',
        message: `${kfCtx}: interpolation must be "linear" or "hold", got "${kf.interpolation}".`,
        detail: { parameterName: definition.name, index: i, interpolation: kf.interpolation },
      });
    }

    // Type-specific value validation
    diags.push(...validateKeyframeValue(kf.value, definition));
  }

  // Check sort order and duplicate times
  const times: number[] = [];
  for (let i = 0; i < keyframes.length; i++) {
    const kf = keyframes[i];
    if (typeof kf?.time !== 'number' || Number.isNaN(kf.time) || !Number.isFinite(kf.time)) {
      continue; // Already reported above
    }
    times.push(kf.time);
  }

  for (let i = 1; i < times.length; i++) {
    if (times[i] < times[i - 1]) {
      diags.push({
        severity: 'warning',
        code: 'keyframes/unsorted-times',
        message: `${ctx}: keyframes are not sorted by time. Index ${i} (time=${times[i]}) is after index ${i - 1} (time=${times[i - 1]}).`,
        detail: {
          parameterName: definition.name,
          index: i,
          currentTime: times[i],
          previousTime: times[i - 1],
        },
      });
    }
    if (times[i] === times[i - 1]) {
      diags.push({
        severity: 'warning',
        code: 'keyframes/duplicate-time',
        message: `${ctx}: duplicate keyframe time ${times[i]} at indices ${i - 1} and ${i}. The first occurrence is used.`,
        detail: {
          parameterName: definition.name,
          time: times[i],
          firstIndex: i - 1,
          duplicateIndex: i,
        },
      });
    }
  }

  return diags;
}

// ---------------------------------------------------------------------------
// Core interpolation: resolve animated params at a given time
// ---------------------------------------------------------------------------

/**
 * Resolve all animated parameters at a given point in time.
 *
 * For each parameter definition in the schema, this function:
 * 1. Looks up the keyframes array from the `keyframes` record (keyed by parameter name).
 * 2. If no keyframes exist, falls back to the parameter's default value.
 * 3. Sorts keyframes by time (handling duplicate times by taking the first occurrence).
 * 4. Clamps the requested time to the keyframe range.
 * 5. Applies the appropriate interpolation mode (linear or hold) between adjacent keyframes.
 *
 * This is deterministic: identical inputs always produce identical outputs.
 *
 * @param keyframes - Host-owned keyframes keyed by parameter name.
 * @param schema - Parameter definitions that describe valid keyframe values.
 * @param time - The time (in seconds) at which to evaluate animated params.
 * @returns Array of interpolated parameters, one per schema entry.
 */
export function resolveAnimatedParams(
  keyframes: Record<string, ClipKeyframe[]>,
  schema: ParameterSchema,
  time: number,
): InterpolatedParam[] {
  const results: InterpolatedParam[] = [];

  // Clamp time to non-negative for safety
  const t = Math.max(0, time);

  for (const definition of schema) {
    const entry = keyframes[definition.name];

    // No keyframes: use default value
    if (!entry || entry.length === 0) {
      const defaultValue = resolveDefaultValue(definition);
      results.push({ name: definition.name, value: defaultValue });
      continue;
    }

    // Filter out invalid entries and sort by time
    // NaN/Infinity times are filtered out (they'd never match)
    const validKeyframes = entry
      .filter(
        (kf) =>
          kf !== null &&
          kf !== undefined &&
          typeof kf === 'object' &&
          typeof kf.time === 'number' &&
          !Number.isNaN(kf.time) &&
          Number.isFinite(kf.time),
      )
      .sort((a, b) => a.time - b.time);

    // If all keyframes were invalid, fall back to default
    if (validKeyframes.length === 0) {
      const defaultValue = resolveDefaultValue(definition);
      results.push({ name: definition.name, value: defaultValue });
      continue;
    }

    // Handle duplicate times: when multiple keyframes share the same time,
    // keep the first occurrence (stable sort preserves insertion order).
    const deduped: ClipKeyframe[] = [];
    const seenTimes = new Set<number>();
    for (const kf of validKeyframes) {
      if (!seenTimes.has(kf.time)) {
        deduped.push(kf);
        seenTimes.add(kf.time);
      }
    }

    const first = deduped[0];
    const last = deduped[deduped.length - 1];

    // Clamp: time before first keyframe
    if (t <= first.time) {
      results.push({ name: definition.name, value: first.value });
      continue;
    }

    // Clamp: time at or after last keyframe
    if (t >= last.time) {
      results.push({ name: definition.name, value: last.value });
      continue;
    }

    // Find the two keyframes that bracket `t`
    let segmentA: ClipKeyframe | null = null;
    let segmentB: ClipKeyframe | null = null;

    for (let i = 0; i < deduped.length - 1; i++) {
      if (t >= deduped[i].time && t < deduped[i + 1].time) {
        segmentA = deduped[i];
        segmentB = deduped[i + 1];
        break;
      }
    }

    // Exact match at a keyframe boundary (already handled above, but belt-and-suspenders)
    if (segmentA === null || segmentB === null) {
      // Fallback: find closest keyframe
      let closest = deduped[0];
      let minDist = Math.abs(t - closest.time);
      for (let i = 1; i < deduped.length; i++) {
        const dist = Math.abs(t - deduped[i].time);
        if (dist < minDist) {
          minDist = dist;
          closest = deduped[i];
        }
      }
      results.push({ name: definition.name, value: closest.value });
      continue;
    }

    // Compute interpolation factor
    const range = segmentB.time - segmentA.time;
    const factor = range > 0 ? (t - segmentA.time) / range : 0;

    // Use the interpolation mode of segmentA (the "from" keyframe)
    const interpolatedValue = interpolatePair(
      segmentA.value,
      segmentB.value,
      factor,
      segmentA.interpolation,
    );

    results.push({ name: definition.name, value: interpolatedValue });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Default value resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a sensible default value for a parameter when no keyframes are provided.
 *
 * Falls back through: definition.default → type-based sensible default.
 */
function resolveDefaultValue(
  definition: ParameterDefinition,
): number | string | boolean {
  if (definition.default !== undefined && definition.default !== null) {
    // Type-check the default value
    switch (definition.type) {
      case 'number':
        if (typeof definition.default === 'number') return definition.default;
        break;
      case 'boolean':
        if (typeof definition.default === 'boolean') return definition.default;
        break;
      case 'select':
      case 'color':
        if (typeof definition.default === 'string') return definition.default;
        break;
      case 'audio-binding':
        if (
          typeof definition.default === 'object' &&
          definition.default !== null
        ) {
          return true; // AudioBindingValue is complex; return true as sentinel
        }
        break;
    }
  }

  // Type-based sensible defaults
  switch (definition.type) {
    case 'number':
      // If min is defined, default to min; otherwise 0
      return definition.min ?? 0;
    case 'boolean':
      return false;
    case 'select':
      // First option value, or empty string
      if (definition.options && definition.options.length > 0) {
        return definition.options[0].value;
      }
      return '';
    case 'color':
      return '#ffffff';
    case 'audio-binding':
      return false; // No meaningful default for audio-binding
    default:
      return false;
  }
}

// ---------------------------------------------------------------------------
// Automation recorder
// ---------------------------------------------------------------------------

/**
 * A single sample point captured during automation recording.
 *
 * Represents a control value at a specific time (e.g. a slider position
 * recorded while the user drags it during playback).
 */
export interface SamplePoint {
  /** Time in seconds. */
  time: number;
  /** The sampled control value. Must be JSON-serializable. */
  value: number | string | boolean;
}

/**
 * Options that control how sampled values are converted into keyframes.
 */
export interface AutomationRecorderOptions {
  /**
   * Minimum numerical difference required to emit a new keyframe.
   *
   * A sample whose quantized value differs from the last emitted keyframe's
   * value by less than tolerance is discarded (downsampled away).
   *
   * Default: 0 (never discard — every change creates a keyframe).
   */
  tolerance?: number;

  /**
   * Quantize numeric values to the nearest multiple of this step before
   * comparison and emission.
   *
   * Example: step=0.01 rounds values like 0.123 → 0.12.
   *
   * Default: 0 (no quantization).
   */
  quantizationStep?: number;

  /**
   * Default interpolation mode assigned to emitted keyframes.
   *
   * Note: the recorder preserves hold semantics automatically — when a
   * non-numeric value (string/boolean) changes, the preceding keyframe
   * is tagged with 'hold' interpolation regardless of this default.
   *
   * Default: 'linear'.
   */
  defaultInterpolation?: KeyframeInterpolation;
}

/**
 * Result of converting sampled values into keyframes.
 */
export interface AutomationRecorderResult {
  /** The deterministically produced keyframes. */
  keyframes: ClipKeyframe[];

  /** Validation diagnostics for rejected samples. */
  diagnostics: KeyframeValidationDiagnostic[];

  /** Total number of input samples (before filtering). */
  sampleCount: number;

  /** Number of output keyframes (after downsampling). */
  keyframeCount: number;
}

/**
 * Check whether a value is JSON-serializable (null-safe primitive).
 *
 * We reject functions, symbols, BigInts, and deeply-nested objects
 * because they cannot round-trip through JSON serialization.
 */
function isSerializable(value: unknown): value is number | string | boolean {
  if (value === null || value === undefined) return false;
  const t = typeof value;
  return t === 'number' || t === 'string' || t === 'boolean';
}

/**
 * Quantize a numeric value to the nearest multiple of `step`.
 *
 * When `step` is 0 or negative, no quantization is applied.
 *
 * Example: quantize(0.123, 0.01) → 0.12
 *          quantize(0.126, 0.01) → 0.13
 */
export function quantizeValue(value: number, step: number): number {
  if (step <= 0 || !Number.isFinite(step)) return value;
  return Math.round(value / step) * step;
}

/**
 * Convert a stream of sampled control values into deterministic keyframes.
 *
 * The recorder:
 * 1. Filters out non-serializable and schema-invalid samples (logs diagnostics).
 * 2. Sorts remaining samples by time; keeps the first occurrence at duplicate times.
 * 3. Quantizes numeric values according to `quantizationStep`.
 * 4. Downsamples by `tolerance`: only emits a new keyframe when the value
 *    changes enough from the last emitted keyframe.
 * 5. Preserves hold semantics: when a non-numeric value changes, or when
 *    a numeric value experiences a step change (difference >= tolerance),
 *    the preceding keyframe uses 'hold' interpolation.
 *
 * This function is fully deterministic — identical inputs always produce
 * identical outputs.
 *
 * @param samples - The raw sampled control values (time-ordered is preferred but not required).
 * @param definition - The parameter definition that describes valid values.
 * @param options - Optional quantization, tolerance, and interpolation defaults.
 * @returns Keyframes and diagnostics.
 */
export function recordAutomation(
  samples: SamplePoint[],
  definition: ParameterDefinition,
  options: AutomationRecorderOptions = {},
): AutomationRecorderResult {
  const {
    tolerance = 0,
    quantizationStep = 0,
    defaultInterpolation = 'linear',
  } = options;

  const diagnostics: KeyframeValidationDiagnostic[] = [];
  const inputCount = samples.length;

  // ── 1. Filter out non-serializable and schema-invalid samples ──────────
  const validSamples: SamplePoint[] = [];

  for (let i = 0; i < samples.length; i++) {
    const s = samples[i];

    // Reject non-serializable values (check the .value property, not the whole sample)
    if (!isSerializable(s.value)) {
      diagnostics.push({
        severity: 'error',
        code: 'automation-recorder/non-serializable-value',
        message: `Sample at index ${i}: value is not JSON-serializable (type: ${typeof s.value}).`,
        detail: { index: i, value: s.value },
      });
      continue;
    }

    // Reject samples with invalid times
    if (typeof s.time !== 'number' || Number.isNaN(s.time) || !Number.isFinite(s.time)) {
      diagnostics.push({
        severity: 'error',
        code: 'automation-recorder/invalid-time',
        message: `Sample at index ${i}: time must be a finite number, got ${JSON.stringify(s.time)}.`,
        detail: { index: i, time: s.time },
      });
      continue;
    }

    // Validate the value against the parameter schema
    const valueDiags = validateKeyframeValue(s.value, definition);
    if (valueDiags.some((d) => d.severity === 'error')) {
      for (const d of valueDiags) {
        diagnostics.push({
          ...d,
          message: `Sample at index ${i}: ${d.message}`,
          detail: { ...d.detail, index: i },
        });
      }
      continue; // Skip schema-invalid values
    }

    // Collect warnings but don't discard
    for (const d of valueDiags) {
      diagnostics.push({
        ...d,
        message: `Sample at index ${i}: ${d.message}`,
        detail: { ...d.detail, index: i },
      });
    }

    validSamples.push(s);
  }

  // ── 2. Sort by time; keep first occurrence at duplicate times ──────────
  validSamples.sort((a, b) => a.time - b.time);

  const deduped: SamplePoint[] = [];
  const seenTimes = new Set<number>();
  for (const s of validSamples) {
    if (!seenTimes.has(s.time)) {
      deduped.push(s);
      seenTimes.add(s.time);
    } else {
      diagnostics.push({
        severity: 'warning',
        code: 'automation-recorder/duplicate-sample-time',
        message: `Sample at time ${s.time} is a duplicate; using the first occurrence.`,
        detail: { time: s.time },
      });
    }
  }

  // ── 3. Quantize numeric values ────────────────────────────────────────
  const effectiveStep = quantizationStep > 0 && Number.isFinite(quantizationStep)
    ? quantizationStep
    : 0;

  const quantized: SamplePoint[] = deduped.map((s) => {
    if (typeof s.value === 'number' && effectiveStep > 0) {
      return { time: s.time, value: quantizeValue(s.value, effectiveStep) };
    }
    return s;
  });

  // ── 4. Empty set → bail early ─────────────────────────────────────────
  if (quantized.length === 0) {
    return {
      keyframes: [],
      diagnostics,
      sampleCount: inputCount,
      keyframeCount: 0,
    };
  }

  // ── 5. Downsample by tolerance ────────────────────────────────────────
  const keyframes: ClipKeyframe[] = [];

  // Always emit the first sample as a keyframe
  const first = quantized[0];
  keyframes.push({
    time: first.time,
    value: first.value,
    interpolation: defaultInterpolation,
  });

  for (let i = 1; i < quantized.length; i++) {
    const current = quantized[i];
    const lastKf = keyframes[keyframes.length - 1];

    const shouldEmit = shouldEmitKeyframe(current, lastKf, tolerance);

    if (shouldEmit) {
      // Before emitting, fix up the interpolation of the *previous* keyframe
      // to reflect hold semantics when appropriate.
      const prevKf = keyframes[keyframes.length - 1];
      prevKf.interpolation = resolveInterpolationMode(
        prevKf,
        current,
        tolerance,
        defaultInterpolation,
      );

      keyframes.push({
        time: current.time,
        value: current.value,
        interpolation: defaultInterpolation,
      });
    }
    // else: downsampled away
  }

  // The last keyframe's interpolation doesn't matter (no next keyframe to
  // interpolate towards), but we keep it as defaultInterpolation for
  // consistency.

  return {
    keyframes,
    diagnostics,
    sampleCount: inputCount,
    keyframeCount: keyframes.length,
  };
}

// ---------------------------------------------------------------------------
// Automation recorder helpers
// ---------------------------------------------------------------------------

/**
 * Determine whether a new keyframe should be emitted for `current` given the
 * last emitted keyframe `lastKf`.
 *
 * Rules:
 * - Numeric values: emit when |current - lastKf| >= tolerance
 * - Non-numeric values: emit when the value changes (strict inequality)
 * - Mixed types: always emit (type change)
 */
function shouldEmitKeyframe(
  current: SamplePoint,
  lastKf: ClipKeyframe,
  tolerance: number,
): boolean {
  // Type mismatch → always emit
  if (typeof current.value !== typeof lastKf.value) {
    return true;
  }

  // Both numeric: tolerance-based check
  if (typeof current.value === 'number' && typeof lastKf.value === 'number') {
    const diff = Math.abs(current.value - lastKf.value);
    return diff >= tolerance;
  }

  // Both non-numeric (string/boolean): emit on change
  return current.value !== lastKf.value;
}

/**
 * Resolve the appropriate interpolation mode for a keyframe that transitions
 * to the next sample.
 *
 * Hold semantics:
 * - When transitioning to/from a non-numeric value → 'hold'
 * - When the numeric step exceeds tolerance (instant jump) → 'hold'
 * - Otherwise → use the default
 */
function resolveInterpolationMode(
  from: ClipKeyframe,
  to: SamplePoint,
  tolerance: number,
  defaultMode: KeyframeInterpolation,
): KeyframeInterpolation {
  // Non-numeric values can only interpolate with hold
  if (typeof from.value !== 'number' || typeof to.value !== 'number') {
    return 'hold';
  }

  // Numeric values: if tolerance is configured and the jump exceeds it,
  // treat as a step change (hold). Otherwise, keep the default.
  if (tolerance > 0) {
    const diff = Math.abs(to.value - (from.value as number));
    if (diff >= tolerance * 10) {
      // Significant jump → hold
      return 'hold';
    }
  }

  return defaultMode;
}

// ---------------------------------------------------------------------------
// Automation clip target reference and overrides
// ---------------------------------------------------------------------------

/**
 * Stable target reference for an automation clip.
 *
 * Identifies a specific extension clip contribution and parameter path
 * that this automation clip overrides. The contribution ID is the
 * extension-contributed clip type identifier, and the parameter path
 * is a dot-separated path into the clip's params object (e.g. "intensity"
 * or "blur.radius").
 */
export interface AutomationTarget {
  /** The extension contribution ID (clipTypeId) this automation targets. */
  readonly contributionId: string;
  /** Dot-separated parameter path within the target clip's params. */
  readonly parameterPath: string;
}

/**
 * Parameters stored on an automation clip (clipType: 'automation').
 *
 * These are serialized into the clip's `params` field and validated
 * through the standard params round-trip.
 */
export interface AutomationClipParams {
  /** The target clip and parameter this automation overrides. */
  readonly target: AutomationTarget;
  /** Keyframe curve that defines the parameter value over time. */
  readonly keyframes: ClipKeyframe[];
  /** Whether this automation is enabled. */
  readonly enabled: boolean;
}

/**
 * Shape of an automation clip for override resolution.
 *
 * Consumers (e.g. TimelineRenderer) pass a subset of the resolved
 * timeline clip containing the fields needed to apply overrides.
 */
export interface AutomationClipShape {
  readonly clipType: string;
  readonly params?: Record<string, unknown> | null;
}

/**
 * Extract automation clip params from a clip's params, with validation.
 *
 * Returns undefined if the clip is not an automation clip or its params
 * are not well-formed.
 */
function extractAutomationParams(
  clip: AutomationClipShape,
): AutomationClipParams | undefined {
  if (clip.clipType !== 'automation') return undefined;

  const params = clip.params;
  if (!params || typeof params !== 'object') return undefined;

  const target = (params as Record<string, unknown>).target;
  if (!target || typeof target !== 'object') return undefined;

  const targetObj = target as Record<string, unknown>;
  if (
    typeof targetObj.contributionId !== 'string' ||
    typeof targetObj.parameterPath !== 'string'
  ) {
    return undefined;
  }

  const keyframes = (params as Record<string, unknown>).keyframes;
  if (!Array.isArray(keyframes)) return undefined;

  const enabled = (params as Record<string, unknown>).enabled;
  if (enabled !== undefined && typeof enabled !== 'boolean') return undefined;

  // Validate keyframes have required shape
  for (const kf of keyframes) {
    if (
      typeof kf !== 'object' ||
      kf === null ||
      typeof (kf as Record<string, unknown>).time !== 'number' ||
      (kf as Record<string, unknown>).value === undefined ||
      typeof (kf as Record<string, unknown>).interpolation !== 'string'
    ) {
      return undefined;
    }
  }

  return {
    target: {
      contributionId: targetObj.contributionId as string,
      parameterPath: targetObj.parameterPath as string,
    },
    keyframes: keyframes as ClipKeyframe[],
    enabled: enabled !== false, // default enabled=true
  };
}

/**
 * Interpolate a single automation curve at a given time.
 *
 * Uses the same `resolveAnimatedParams`-style clamping and
 * interpolation logic but operates on a single keyframe array and
 * returns a single value.
 */
function interpolateAutomationCurve(
  keyframes: ClipKeyframe[],
  time: number,
): number | string | boolean | undefined {
  if (keyframes.length === 0) return undefined;

  // Filter invalid entries and sort by time
  const valid = keyframes
    .filter(
      (kf) =>
        kf !== null &&
        kf !== undefined &&
        typeof kf === 'object' &&
        typeof kf.time === 'number' &&
        !Number.isNaN(kf.time) &&
        Number.isFinite(kf.time),
    )
    .sort((a, b) => a.time - b.time);

  if (valid.length === 0) return undefined;

  // Deduplicate times (first occurrence wins)
  const deduped: ClipKeyframe[] = [];
  const seenTimes = new Set<number>();
  for (const kf of valid) {
    if (!seenTimes.has(kf.time)) {
      deduped.push(kf);
      seenTimes.add(kf.time);
    }
  }

  const t = Math.max(0, time);
  const first = deduped[0];
  const last = deduped[deduped.length - 1];

  // Clamp: before first keyframe → first value
  if (t <= first.time) return first.value;

  // Clamp: at or after last keyframe → last value
  if (t >= last.time) return last.value;

  // Find bracketing keyframes
  for (let i = 0; i < deduped.length - 1; i++) {
    if (t >= deduped[i].time && t < deduped[i + 1].time) {
      const range = deduped[i + 1].time - deduped[i].time;
      const factor = range > 0 ? (t - deduped[i].time) / range : 0;
      return interpolatePair(
        deduped[i].value,
        deduped[i + 1].value,
        factor,
        deduped[i].interpolation,
      );
    }
  }

  // Fallback: closest keyframe
  let closest = deduped[0];
  let minDist = Math.abs(t - closest.time);
  for (let i = 1; i < deduped.length; i++) {
    const dist = Math.abs(t - deduped[i].time);
    if (dist < minDist) {
      minDist = dist;
      closest = deduped[i];
    }
  }
  return closest.value;
}

/**
 * Set a nested value at a dot-separated path within a params record.
 *
 * Creates intermediate objects as needed. Returns a new record
 * (shallow copy at each level).
 */
function setNestedParam(
  params: Record<string, unknown>,
  path: string,
  value: number | string | boolean,
): Record<string, unknown> {
  const segments = path.split('.');
  if (segments.length === 0) return params;

  const result = { ...params };

  if (segments.length === 1) {
    result[segments[0]] = value;
    return result;
  }

  // Multi-segment path: walk/create nested objects
  let current: Record<string, unknown> = result;
  for (let i = 0; i < segments.length - 1; i++) {
    const segment = segments[i];
    const existing = current[segment];
    if (typeof existing === 'object' && existing !== null && !Array.isArray(existing)) {
      current[segment] = { ...(existing as Record<string, unknown>) };
    } else {
      current[segment] = {};
    }
    current = current[segment] as Record<string, unknown>;
  }

  current[segments[segments.length - 1]] = value;
  return result;
}

/**
 * Apply automation overrides from a set of automation clips to a target
 * extension clip's parameters at a given time.
 *
 * This is the host-side integration point called during preview/export
 * param resolution. It:
 *
 * 1. Scans `automationClips` for enabled automation clips whose
 *    `target.contributionId` matches `targetClipTypeId`.
 * 2. For each matching automation clip, interpolates its keyframe curve
 *    at `time` to produce an override value.
 * 3. Merges the override value into the `currentParams` at the
 *    parameter path.
 * 4. Returns the combined params record.
 *
 * Later automation clips in the array override earlier ones when they
 * target the same parameter path (last-write-wins).
 *
 * @param automationClips - All automation clips from the timeline.
 * @param targetClipTypeId - The clipTypeId of the extension clip being rendered.
 * @param currentParams - The clip's current params (host-interpolated).
 * @param time - The time (in seconds) at which to resolve automation values.
 * @returns A new params record with automation overrides applied.
 */
export function applyAutomationOverrides(
  automationClips: readonly AutomationClipShape[],
  targetClipTypeId: string,
  currentParams: Record<string, unknown>,
  time: number,
): Record<string, unknown> {
  let result = currentParams;

  for (const clip of automationClips) {
    const params = extractAutomationParams(clip);
    if (!params) continue;
    if (!params.enabled) continue;
    if (params.target.contributionId !== targetClipTypeId) continue;

    const value = interpolateAutomationCurve(params.keyframes, time);
    if (value === undefined) continue;

    result = setNestedParam(result, params.target.parameterPath, value);
  }

  return result;
}
