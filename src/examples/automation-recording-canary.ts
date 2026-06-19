/**
 * automation-recording-canary — M9 automation-recording canary example.
 *
 * Demonstrates the deterministic automation-recording flow using the
 * M9 SDK contracts:
 *
 *   1. Define a parameter schema for a clip type (the target).
 *   2. Capture sample points (simulating live slider drags during playback).
 *   3. Quantize and downsample samples into deterministic keyframes using
 *      the host's `recordAutomation`-equivalent logic.
 *   4. Construct valid `AutomationClipParams` from the keyframes.
 *   5. Construct an `AutomationClipShape` (the host-side representation of
 *      an automation clip on the timeline).
 *   6. Apply automation overrides to a target clip's params at a given time
 *      using interpolation semantics.
 *
 * This example is a CANARY — it validates at compile-time that the SDK
 * contracts for keyframes and automation are sound and usable by extensions.
 * The actual interpolation and recording logic is host-owned (extensions
 * never reimplement timeline interpolation), but this example demonstrates
 * the contract shapes and data flow.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  Keyframe,
  KeyframeInterpolation,
  InterpolatedParam,
  AutomationClipTarget,
  AutomationClipParams,
  ClipParameterDefinition,
  ClipParameterSchema,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Parameter schema — the target parameters that can be automated
// ---------------------------------------------------------------------------

const TARGET_PARAM_SCHEMA: ClipParameterSchema = [
  {
    name: 'intensity',
    label: 'Intensity',
    description: 'Effect intensity (0–1).',
    type: 'number',
    default: 0.5,
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    name: 'speed',
    label: 'Speed',
    description: 'Animation speed multiplier (0.25–4).',
    type: 'number',
    default: 1,
    min: 0.25,
    max: 4,
    step: 0.25,
  },
  {
    name: 'mode',
    label: 'Mode',
    description: 'Operating mode.',
    type: 'select',
    default: 'auto',
    options: [
      { label: 'Auto', value: 'auto' },
      { label: 'Manual', value: 'manual' },
      { label: 'Bypass', value: 'bypass' },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sample points — simulated live recording data
// ---------------------------------------------------------------------------

/**
 * A sample point captured during automation recording.
 *
 * This is the extension-side representation of a single captured value.
 * The host-side implementation (keyframes/index.ts) uses `SamplePoint`,
 * but extensions import `Keyframe` for the serialized result.
 */
interface SamplePoint {
  time: number;
  value: number | string | boolean;
}

/**
 * Simulated sample points captured during a 4-second recording session
 * for the 'intensity' parameter. In real usage, these would come from
 * live slider drag events during timeline playback.
 */
const INTENSITY_SAMPLES: SamplePoint[] = [
  { time: 0.0, value: 0.5 },
  { time: 0.2, value: 0.52 },
  { time: 0.4, value: 0.55 },
  { time: 0.5, value: 0.55 }, // duplicate time → first occurrence wins
  { time: 0.6, value: 0.6 },
  { time: 0.8, value: 0.7 },
  { time: 1.0, value: 0.8 },
  { time: 1.2, value: 0.85 },
  { time: 1.4, value: 0.9 },
  { time: 1.6, value: 0.95 },
  { time: 2.0, value: 1.0 },
  { time: 2.5, value: 0.8 },
  { time: 3.0, value: 0.5 },
  { time: 3.5, value: 0.3 },
  { time: 4.0, value: 0.2 },
];

// ---------------------------------------------------------------------------
// Quantization and downsampling helpers
// ---------------------------------------------------------------------------

/**
 * Quantize a numeric value to the nearest multiple of step.
 *
 * This mirrors the host-side `quantizeValue` for demonstration purposes.
 * Extensions do not need to reimplement this — the host handles it.
 */
function quantizeValue(value: number, step: number): number {
  if (step <= 0 || !Number.isFinite(step)) return value;
  return Math.round(value / step) * step;
}

/**
 * Convert sample points into `Keyframe[]` using deterministic quantization
 * and tolerance-based downsampling.
 *
 * Rules (matching the host `recordAutomation` semantics):
 * - Filter out non-serializable values.
 * - Sort by time; keep first occurrence at duplicate times.
 * - Quantize numeric values.
 * - Downsample by tolerance: only emit a new keyframe when the value
 *   change exceeds the tolerance.
 * - Preserve hold semantics for non-numeric / step changes.
 *
 * This function is exported so the governance test can exercise it
 * and prove it follows the SDK keyframe contract.
 */
export function canaryRecordAutomation(
  samples: SamplePoint[],
  definition: ClipParameterDefinition,
  options?: {
    tolerance?: number;
    quantizationStep?: number;
    defaultInterpolation?: KeyframeInterpolation;
  },
): { keyframes: Keyframe[]; diagnostics: string[] } {
  const tolerance = options?.tolerance ?? 0.01;
  const quantizationStep = options?.quantizationStep ?? 0;
  const defaultInterpolation: KeyframeInterpolation =
    options?.defaultInterpolation ?? 'linear';

  const diagnostics: string[] = [];
  const inputCount = samples.length;

  // ── 1. Filter non-serializable and schema-invalid samples ──────────────
  const validSamples: SamplePoint[] = [];

  for (let i = 0; i < samples.length; i++) {
    const s = samples[i];

    // Non-serializable check
    if (s.value === null || s.value === undefined) {
      diagnostics.push(`Sample at index ${i}: value is null/undefined — rejected.`);
      continue;
    }
    const t = typeof s.value;
    if (t !== 'number' && t !== 'string' && t !== 'boolean') {
      diagnostics.push(`Sample at index ${i}: value type "${t}" is not serializable — rejected.`);
      continue;
    }

    // Invalid time check
    if (typeof s.time !== 'number' || !Number.isFinite(s.time)) {
      diagnostics.push(`Sample at index ${i}: invalid time — rejected.`);
      continue;
    }

    // Type-specific validation against the definition
    if (definition.type === 'number' && typeof s.value !== 'number') {
      diagnostics.push(`Sample at index ${i}: expected number, got ${typeof s.value} — rejected.`);
      continue;
    }
    if (definition.type === 'boolean' && typeof s.value !== 'boolean') {
      diagnostics.push(`Sample at index ${i}: expected boolean, got ${typeof s.value} — rejected.`);
      continue;
    }
    if (definition.type === 'select' && typeof s.value !== 'string') {
      diagnostics.push(`Sample at index ${i}: expected string, got ${typeof s.value} — rejected.`);
      continue;
    }
    if (definition.type === 'color' && typeof s.value !== 'string') {
      diagnostics.push(`Sample at index ${i}: expected color string, got ${typeof s.value} — rejected.`);
      continue;
    }

    validSamples.push(s);
  }

  // ── 2. Sort by time; keep first at duplicate times ────────────────────
  validSamples.sort((a, b) => a.time - b.time);

  const deduped: SamplePoint[] = [];
  const seenTimes = new Set<number>();
  for (const s of validSamples) {
    if (!seenTimes.has(s.time)) {
      deduped.push(s);
      seenTimes.add(s.time);
    }
  }

  // ── 3. Quantize numeric values ────────────────────────────────────────
  const quantized: SamplePoint[] = deduped.map((s) => {
    if (typeof s.value === 'number' && quantizationStep > 0) {
      return { time: s.time, value: quantizeValue(s.value as number, quantizationStep) };
    }
    return s;
  });

  if (quantized.length === 0) {
    return { keyframes: [], diagnostics };
  }

  // ── 4. Downsample by tolerance ────────────────────────────────────────
  const keyframes: Keyframe[] = [];

  // Always emit the first sample
  keyframes.push({
    time: quantized[0].time,
    value: quantized[0].value,
    interpolation: defaultInterpolation,
  });

  for (let i = 1; i < quantized.length; i++) {
    const current = quantized[i];
    const lastKf = keyframes[keyframes.length - 1];

    let shouldEmit = false;

    if (typeof current.value !== typeof lastKf.value) {
      // Type change → emit
      shouldEmit = true;
    } else if (typeof current.value === 'number' && typeof lastKf.value === 'number') {
      const diff = Math.abs(current.value - lastKf.value);
      shouldEmit = diff >= tolerance;
      if (shouldEmit) {
        // Hold semantics for large step changes
        if (diff >= tolerance * 10) {
          lastKf.interpolation = 'hold';
        }
      }
    } else {
      shouldEmit = current.value !== lastKf.value;
      if (shouldEmit) {
        // Non-numeric changes → hold
        lastKf.interpolation = 'hold';
      }
    }

    if (shouldEmit) {
      keyframes.push({
        time: current.time,
        value: current.value,
        interpolation: defaultInterpolation,
      });
    }
  }

  return {
    keyframes,
    diagnostics,
  };
}

// ---------------------------------------------------------------------------
// Automation clip construction helpers
// ---------------------------------------------------------------------------

/**
 * Build a valid `AutomationClipParams` record from keyframes and a target
 * descriptor.
 *
 * This mirrors the host-side `AutomationClipParams` shape that automation
 * clips store in their `params` field.
 */
export function buildAutomationClipParams(
  contributionId: string,
  parameterPath: string,
  keyframes: Keyframe[],
  enabled: boolean = true,
): AutomationClipParams {
  return {
    target: {
      contributionId,
      parameterPath,
    } satisfies AutomationClipTarget,
    keyframes,
    enabled,
  };
}

// ---------------------------------------------------------------------------
// Automation override application (canary)
// ---------------------------------------------------------------------------

/**
 * Shape of a clip on the timeline that may be an automation clip.
 * Extensions receive this shape when enumerating timeline clips.
 */
interface AutomationClipShape {
  readonly clipType: string;
  readonly params?: Record<string, unknown> | null;
}

/**
 * Apply automation overrides from a set of automation clip shapes
 * to a target clip's params at a given time.
 *
 * This is a canary implementation matching the host-side
 * `applyAutomationOverrides` semantics. Extensions should not need
 * to reimplement this — the host handles override resolution during
 * preview/export. This exists to validate the contract shapes.
 *
 * Rules:
 * - Only clips with `clipType === 'automation'` are considered.
 * - Only enabled automation clips with matching `contributionId` apply.
 * - Later clips in the array override earlier ones (last-write-wins).
 * - Returns a new params record (does not mutate input).
 */
export function canaryApplyAutomationOverrides(
  automationClips: readonly AutomationClipShape[],
  targetClipTypeId: string,
  currentParams: Record<string, unknown>,
  time: number,
): Record<string, unknown> {
  let result = { ...currentParams };

  for (const clip of automationClips) {
    if (clip.clipType !== 'automation') continue;

    const params = clip.params;
    if (!params || typeof params !== 'object') continue;

    const target = (params as Record<string, unknown>).target;
    if (!target || typeof target !== 'object') continue;

    const targetObj = target as Record<string, unknown>;
    if (targetObj.contributionId !== targetClipTypeId) continue;

    const enabled = (params as Record<string, unknown>).enabled;
    if (enabled === false) continue;

    const keyframes = (params as Record<string, unknown>).keyframes;
    if (!Array.isArray(keyframes) || keyframes.length === 0) continue;

    const parameterPath = targetObj.parameterPath as string;

    // Interpolate the curve at the requested time
    const value = interpolateKeyframeCurve(
      keyframes as Keyframe[],
      time,
    );
    if (value === undefined) continue;

    // Set the value at the parameter path
    result = setNestedParam(result, parameterPath, value);
  }

  return result;
}

/**
 * Interpolate a single keyframe curve at a given time.
 *
 * Uses clamping + linear/hold interpolation between bracketing keyframes.
 * Returns `undefined` if the curve is empty or all keyframes are invalid.
 */
function interpolateKeyframeCurve(
  keyframes: Keyframe[],
  time: number,
): number | string | boolean | undefined {
  // Filter and sort valid keyframes
  const valid = keyframes
    .filter(
      (kf) =>
        kf !== null &&
        kf !== undefined &&
        typeof kf === 'object' &&
        typeof kf.time === 'number' &&
        Number.isFinite(kf.time),
    )
    .sort((a, b) => a.time - b.time);

  if (valid.length === 0) return undefined;

  // Deduplicate times
  const deduped: Keyframe[] = [];
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

  if (t <= first.time) return first.value;
  if (t >= last.time) return last.value;

  // Find bracketing keyframes
  for (let i = 0; i < deduped.length - 1; i++) {
    if (t >= deduped[i].time && t < deduped[i + 1].time) {
      const range = deduped[i + 1].time - deduped[i].time;
      const factor = range > 0 ? (t - deduped[i].time) / range : 0;
      const mode = deduped[i].interpolation;

      // Linear interpolation for numbers; hold for everything else
      if (typeof deduped[i].value === 'number' && typeof deduped[i + 1].value === 'number') {
        if (mode === 'hold') {
          return factor < 1 ? deduped[i].value : deduped[i + 1].value;
        }
        return (deduped[i].value as number) +
          ((deduped[i + 1].value as number) - (deduped[i].value as number)) * factor;
      }

      // Non-numeric: hold semantics
      return factor < 1 ? deduped[i].value : deduped[i + 1].value;
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
 * Creates intermediate objects as needed.
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

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const automationRecordingCanaryExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.automation-recording-canary' as any,
    version: '1.0.0',
    label: 'Automation Recording Canary',
    description:
      'Demonstrates the M9 automation-recording flow using SDK keyframe and automation contracts.',
    apiVersion: 1,

    messages: {
      'activated':
        'Automation recording canary v{{version}} activated — recording flow demonstrated.',
      'disposed': 'Automation recording canary disposed.',
      'recording.done':
        'Recording complete: {{sampleCount}} samples → {{keyframeCount}} keyframes (tolerance={{tolerance}}).',
      'override.applied':
        'Automation override "{{contributionId}}/{{parameterPath}}" applied at t={{time}}.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'automation-canary/activated',
      message: ctx.services.i18n.t('activated', {
        version: ctx.extension.version,
      }),
    });

    // Demonstrate the recording flow using the exported canary helpers
    const result = canaryRecordAutomation(
      INTENSITY_SAMPLES,
      TARGET_PARAM_SCHEMA[0],
      { tolerance: 0.05, quantizationStep: 0.01, defaultInterpolation: 'linear' },
    );

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'automation-canary/recording-done',
      message: ctx.services.i18n.t('recording.done', {
        sampleCount: INTENSITY_SAMPLES.length,
        keyframeCount: result.keyframes.length,
        tolerance: '0.05',
      }),
    });

    // Validate the result shape
    if (result.keyframes.length > 0) {
      const firstKf = result.keyframes[0];
      ctx.services.diagnostics.report({
        severity: 'info',
        code: 'automation-canary/first-keyframe',
        message: `First keyframe: t=${firstKf.time.toFixed(2)} value=${firstKf.value} interp=${firstKf.interpolation}`,
      });
    }

    // Build automation clip params from the recorded keyframes
    const automationParams = buildAutomationClipParams(
      'com.reigh.examples.clipType.keyframed',
      'intensity',
      result.keyframes,
      true,
    );

    // Demonstrate the shape is valid
    const automationClipShape: AutomationClipShape = {
      clipType: 'automation',
      params: automationParams as unknown as Record<string, unknown>,
    };

    // Apply the automation override to target params at t=1.0
    const targetParams = { intensity: 0.5, speed: 1, mode: 'auto' };
    const overriddenParams = canaryApplyAutomationOverrides(
      [automationClipShape],
      'com.reigh.examples.clipType.keyframed',
      targetParams,
      1.0,
    );

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'automation-canary/override-applied',
      message: ctx.services.i18n.t('override.applied', {
        contributionId: 'com.reigh.examples.clipType.keyframed',
        parameterPath: 'intensity',
        time: '1.0',
      }),
      detail: {
        originalIntensity: targetParams.intensity,
        overriddenIntensity: overriddenParams.intensity,
        overriddenParams,
      },
    });

    return {
      dispose(): void {
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'automation-canary/disposed',
          message: ctx.services.i18n.t('disposed'),
        });
      },
    };
  },
});
