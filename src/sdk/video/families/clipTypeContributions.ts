/**
 * Clip-type family module.
 *
 * Houses the clip-type family contracts extracted from the public barrel
 * (src/sdk/index.ts): ClipTypeContribution manifest interface plus the
 * associated service/component types (ClipRenderer, ClipInspector,
 * ClipParameterDefinition, ClipParameterSchema, ClipTypeRegistrationOptions,
 * ClipTypeRegistrationService).
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { DisposeHandle } from '../../dispose';

/**
 * M9: A clip-type contribution declared in an extension manifest.
 *
 * Contributed clip types are trusted local browser-preview components
 * analogous to M7 effects and M8 transitions. Worker execution of
 * contributed clip code stays out of scope for M9.
 */
export interface ClipTypeContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'clipType';
  /** The clip-type identifier used in registerClipType calls. */
  clipTypeId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the clip type to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the clip type to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/**
 * M9: A trusted local component registered by an extension as a clip renderer.
 *
 * Clip renderers execute in the browser preview and receive host-interpolated
 * params through ClipRendererProps.
 */
export type ClipRenderer = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * M9: A trusted local component registered by an extension as a clip inspector.
 *
 * Clip inspectors render in the inspector panel when a clip of the
 * owning type is selected.
 */
export type ClipInspector = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * M9: A parameter definition for clip-type parameter schemas.
 *
 * Mirrors the effect/transition parameter definition shape so extensions
 * can declare parameter contracts at registration time.
 */
export interface ClipParameterDefinition {
  /** Unique parameter name (used as the key in params). */
  name: string;
  /** Human-readable label for UI controls. */
  label: string;
  /** Description shown in tooltips / inspector. */
  description: string;
  /** Parameter type determining the control and coercion rules. */
  type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
  /** Default value when no override is provided. */
  default?: number | string | boolean | Record<string, unknown>;
  /** Minimum value (number type only). */
  min?: number;
  /** Maximum value (number type only). */
  max?: number;
  /** Step increment (number type only). */
  step?: number;
  /** Options for select-type parameters. */
  options?: readonly { label: string; value: string }[];
}

/** M9: Ordered array of clip parameter definitions. */
export type ClipParameterSchema = readonly ClipParameterDefinition[];

/** M9: Options for imperative clip-type registration via ctx.clipTypes.registerClipType(). */
export interface ClipTypeRegistrationOptions {
  /** Override label for picker / UI. */
  label?: string;
  /**
   * Parameter schema for this clip type.
   * Validated at registration time.
   */
  parameterSchema?: ClipParameterSchema;
}

/**
 * M9: Clip-type registration service available as `ctx.clipTypes` during activate().
 */
export interface ClipTypeRegistrationService {
  /**
   * Register a trusted local renderer and optional inspector for a clip type.
   *
   * The `clipTypeId` must match the `clipTypeId` field of a `ClipTypeContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the clip type when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerClipType(
    clipTypeId: string,
    renderer: ClipRenderer,
    inspector?: ClipInspector,
    options?: ClipTypeRegistrationOptions,
  ): DisposeHandle;
}
