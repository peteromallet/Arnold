/**
 * Effect family module.
 *
 * Houses the effect family contracts extracted from the public barrel
 * (src/sdk/index.ts): EffectContribution manifest interface plus the
 * associated service/component types (EffectComponent, EffectParameterDefinition,
 * EffectParameterSchema, EffectRegistrationOptions, EffectRegistrationService).
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { DisposeHandle } from '../../dispose';

/**
 * M7: An effect contribution declared in an extension manifest.
 *
 * Trusted component effects render in the browser preview and are blocked
 * from browser-export and worker-export unless the contribution declares
 * stronger capability.
 */
export interface EffectContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'effect';
  /** The effect identifier used in registerComponent calls. */
  effectId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the effect to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the effect to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/**
 * A trusted local component registered by an extension as an effect.
 *
 * Component effects execute in the browser preview and are blocked from
 * export contexts unless the owning contribution declares stronger capability.
 */
export type EffectComponent = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * A parameter definition for effect parameter schemas.
 *
 * This lightweight SDK type mirrors the video-editor internal ParameterDefinition
 * shape so extensions can declare parameter contracts at registration time.
 * The video-editor runtime validates these at registration time and coerces
 * parameter values at render time.
 */
export interface EffectParameterDefinition {
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

/** Ordered array of parameter definitions. */
export type EffectParameterSchema = readonly EffectParameterDefinition[];

/** Options for imperative effect registration via ctx.effects.registerComponent(). */
export interface EffectRegistrationOptions {
  /** Override label for the effect picker / UI. */
  label?: string;
  /**
   * Parameter schema for this effect.
   *
   * When provided, the schema is validated at registration time. An invalid
   * schema produces `status: 'error'` on the registry record with diagnostics
   * but does not prevent the component from rendering (render-time parameter
   * coercion continues to work for already-applied legacy data).
   */
  parameterSchema?: EffectParameterSchema;
}

/**
 * Effect registration service available as `ctx.effects` during activate().
 *
 * Trusted component effects must have a matching {@link EffectContribution}
 * in the extension manifest.  Components are registered imperatively via
 * `registerComponent()` and the returned DisposeHandle unregisters them on
 * dispose.
 */
export interface EffectRegistrationService {
  /**
   * Register a trusted local component as an effect.
   *
   * The `effectId` must match the `effectId` field of an `EffectContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the component when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerComponent(
    effectId: string,
    component: EffectComponent,
    options?: EffectRegistrationOptions,
  ): DisposeHandle;
}
