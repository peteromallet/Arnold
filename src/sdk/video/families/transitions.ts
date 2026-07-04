/**
 * Transition family module.
 *
 * Houses the transition family contracts extracted from the public barrel
 * (src/sdk/index.ts): TransitionContribution manifest interface plus the
 * associated service/component types (TransitionRenderer, TransitionParameterDefinition,
 * TransitionParameterSchema, TransitionRegistrationOptions, TransitionRegistrationService).
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { DisposeHandle } from '../../dispose';

/**
 * A descriptor-declared named material slot for transitions.
 *
 * Transitions that consume material inputs (e.g. mask textures) declare
 * named slots here.  At runtime the host binds a {@link MaterialRef} /
 * {@link RenderMaterialRef} to each declared slot through the internal
 * {@code material.attach} graph preview operation.  No new material
 * identity types (such as {@code MaskMaterialRef}) are introduced —
 * bound materials use the existing {@link MaterialRef} / {@link RenderMaterialRef}
 * identity contract.
 *
 * @publicContract
 */
export interface TransitionMaterialSlotDeclaration {
  /** Unique slot name within the transition (used as the key in materialSlots). */
  name: string;
  /** Human-readable label for UI diagnostics / inspector. */
  label?: string;
}

/**
 * M8: A transition contribution declared in an extension manifest.
 *
 * Trusted component transitions render in the browser preview and are blocked
 * from browser-export and worker-export unless the contribution declares
 * stronger capability.
 */
export interface TransitionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'transition';
  /** The transition identifier used in registerRenderer calls. */
  transitionId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the transition to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the transition to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
  /**
   * M5-ready named material (mask) slot declarations.
   *
   * Each slot can receive a {@link MaterialRef} / {@link RenderMaterialRef}
   * binding at runtime via the internal {@code material.attach} graph
   * preview operation.  Omitted or empty means the transition accepts no
   * material inputs.
   */
  materialSlots?: readonly TransitionMaterialSlotDeclaration[];
}

/**
 * A trusted local renderer registered by an extension as a transition.
 *
 * Transition renderers execute in the browser preview and are blocked from
 * export contexts unless the owning contribution declares stronger capability.
 */
export type TransitionRenderer = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * A parameter definition for transition parameter schemas.
 *
 * This lightweight SDK type mirrors the video-editor internal ParameterDefinition
 * shape so extensions can declare parameter contracts at registration time.
 * The video-editor runtime validates these at registration time and coerces
 * parameter values at render time.
 */
export interface TransitionParameterDefinition {
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

/** Ordered array of transition parameter definitions. */
export type TransitionParameterSchema = readonly TransitionParameterDefinition[];

/** Options for imperative transition registration via ctx.transitions.registerRenderer(). */
export interface TransitionRegistrationOptions {
  /** Override label for the transition picker / UI. */
  label?: string;
  /**
   * Parameter schema for this transition.
   *
   * When provided, the schema is validated at registration time. An invalid
   * schema produces `status: 'error'` on the registry record with diagnostics
   * but does not prevent the renderer from rendering (render-time parameter
   * coercion continues to work for already-applied legacy data).
   */
  parameterSchema?: TransitionParameterSchema;
}

/**
 * Transition registration service available as `ctx.transitions` during activate().
 *
 * Trusted component transitions must have a matching {@link TransitionContribution}
 * in the extension manifest.  Renderers are registered imperatively via
 * `registerRenderer()` and the returned DisposeHandle unregisters them on
 * dispose.
 */
export interface TransitionRegistrationService {
  /**
   * Register a trusted local renderer as a transition.
   *
   * The `transitionId` must match the `transitionId` field of a `TransitionContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the renderer when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerRenderer(
    transitionId: string,
    renderer: TransitionRenderer,
    options?: TransitionRegistrationOptions,
  ): DisposeHandle;
}
