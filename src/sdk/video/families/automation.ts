/**
 * Automation / keyframe family module.
 *
 * Houses the automation/keyframe data contracts extracted from the public barrel
 * (src/sdk/index.ts): KeyframeInterpolation, Keyframe, InterpolatedParam,
 * AutomationClipTarget, and AutomationClipParams.
 *
 * Automation clips are host-owned timeline clips (built-in clip type) with
 * baked keyframe curves that override target extension parameter values during
 * preview and export.  The host owns interpolation and keyframe validation;
 * this module defines only the shape contracts.
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * @publicContract
 */

// ---------------------------------------------------------------------------
// M9: Keyframe contracts
// ---------------------------------------------------------------------------

/**
 * M9: Interpolation mode for keyframe curves.
 *
 * - `linear` — lerp between adjacent keyframe values.
 * - `hold` — step function; value holds until the next keyframe.
 */
export type KeyframeInterpolation = 'linear' | 'hold';

/**
 * M9: A single keyframe stored as JSON-serializable timeline data on a clip.
 *
 * Keyframes are host-owned timeline data validated against the owning
 * parameter schema, with interpolation performed by the host before
 * passing computed params to renderers.
 */
export interface Keyframe {
  /** Time in seconds. */
  time: number;
  /** JSON-serializable value (number | string | boolean). */
  value: number | string | boolean;
  /** Interpolation mode from this keyframe to the next. */
  interpolation: KeyframeInterpolation;
}

/**
 * M9: Interpolated parameter value at a specific time.
 *
 * Produced by the host keyframe interpolator and passed to clip renderers
 * so extension code never needs to implement timeline interpolation.
 */
export interface InterpolatedParam {
  /** The parameter name. */
  name: string;
  /** The interpolated value at the requested time. */
  value: number | string | boolean;
}

// ---------------------------------------------------------------------------
// M9: Automation clip contracts
// ---------------------------------------------------------------------------

/**
 * M9: Target descriptor for an automation clip.
 *
 * Automation clips are host-owned timeline clips (clipType: 'automation')
 * that reference target parameters by contribution ID and parameter path.
 */
export interface AutomationClipTarget {
  /** The contribution ID that owns the target parameter. */
  contributionId: string;
  /** Dot-separated path to the target parameter within the contribution. */
  parameterPath: string;
}

/**
 * M9: Params stored on an automation clip.
 *
 * Automation clips apply baked keyframe curves to override target
 * extension parameter values during preview and export.
 */
export interface AutomationClipParams {
  /** The target parameter this automation clip controls. */
  target: AutomationClipTarget;
  /** Ordered keyframes defining the automation curve. */
  keyframes: readonly Keyframe[];
  /** Whether this automation clip is active. */
  enabled: boolean;
}
