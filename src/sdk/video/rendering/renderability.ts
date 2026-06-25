/** Routes that a contribution may support when previewing or exporting. */
export type RenderRoute = 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';

/** Locked render route vocabulary shared by registries, guards, and planners. */
export const RENDER_ROUTES = [
  'preview',
  'browser-export',
  'worker-export',
  'sidecar-export',
] as const satisfies readonly RenderRoute[];
Object.freeze(RENDER_ROUTES);

/**
 * Determinism posture for a contribution, material, artifact, or bake.
 *
 * - `deterministic`: same inputs are expected to produce equivalent outputs.
 * - `preview-only`: usable only for interactive preview, not authoritative export.
 * - `live-unbaked`: depends on live provider/runtime state until materialized.
 * - `process-dependent`: depends on external process/tool versions or sidecars.
 * - `unknown`: insufficient metadata; guards should stay conservative.
 */
export type DeterminismStatus =
  | 'deterministic'
  | 'preview-only'
  | 'live-unbaked'
  | 'process-dependent'
  | 'unknown';

/** Locked determinism vocabulary shared across registry records and artifacts. */
export const DETERMINISM_STATUSES = [
  'deterministic',
  'preview-only',
  'live-unbaked',
  'process-dependent',
  'unknown',
] as const satisfies readonly DeterminismStatus[];
Object.freeze(DETERMINISM_STATUSES);

/** Stable blocker reasons emitted by early guards and later planner aggregation. */
export type RenderBlockerReason =
  | 'missing-contribution'
  | 'route-unsupported'
  | 'preview-only'
  | 'live-unbaked'
  | 'process-dependent'
  | 'missing-material'
  | 'materialization-failed'
  | 'inactive-extension'
  | 'unknown';

/** Locked blocker reason vocabulary for planner-compatible records. */
export const RENDER_BLOCKER_REASONS = [
  'missing-contribution',
  'route-unsupported',
  'preview-only',
  'live-unbaked',
  'process-dependent',
  'missing-material',
  'materialization-failed',
  'inactive-extension',
  'unknown',
] as const satisfies readonly RenderBlockerReason[];
Object.freeze(RENDER_BLOCKER_REASONS);

export type RenderCapabilityStatus = 'supported' | 'blocked' | 'unknown';

/** Per-route capability advertised by a registry record or derived guard scan. */
export interface RenderCapability {
  readonly route: RenderRoute;
  readonly status: RenderCapabilityStatus;
  readonly determinism: DeterminismStatus;
  readonly blockerReason?: RenderBlockerReason;
  readonly message?: string;
}

/** Renderability summary carried by provider-scoped registry records. */
export interface ContributionRenderability {
  readonly capabilities: readonly RenderCapability[];
  readonly defaultRoute?: RenderRoute;
  readonly determinism: DeterminismStatus;
  readonly blockers?: readonly RenderBlocker[];
}

export type CapabilityFindingSeverity = 'error' | 'warning' | 'info';

/** Planner-compatible finding record emitted by guards, registries, or loaders. */
export interface CapabilityFinding {
  readonly id: string;
  readonly severity: CapabilityFindingSeverity;
  readonly route?: RenderRoute;
  readonly reason?: RenderBlockerReason;
  readonly message: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
  readonly clipId?: string;
  readonly materialRefId?: string;
  readonly detail?: Record<string, unknown>;
}

/** Blocking subset of a finding that prevents a route from being authoritative. */
export interface RenderBlocker extends CapabilityFinding {
  readonly severity: 'error';
  readonly route: RenderRoute;
  readonly reason: RenderBlockerReason;
}
