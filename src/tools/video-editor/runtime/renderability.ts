/**
 * Shared renderability and artifact vocabulary for provider-scoped
 * registries and export-readiness planning.
 *
 * These contracts are intentionally data-only. Registries own lifecycle and
 * snapshots, export guards produce findings/blockers, and later planners can
 * aggregate the same records without renaming fields.
 */

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

export type RenderMaterialMediaKind =
  | 'image'
  | 'video'
  | 'audio'
  | 'text'
  | 'json'
  | 'binary'
  | 'sidecar'
  | 'unknown';

export type RenderLocatorKind =
  | 'asset-registry'
  | 'artifact-store'
  | 'url'
  | 'local-file'
  | 'inline'
  | 'provider';

/** Storage locator for material bytes or generated artifact outputs. */
export interface RenderStorageLocator {
  readonly kind: RenderLocatorKind;
  readonly uri: string;
  readonly mimeType?: string;
  readonly contentSha256?: string;
  readonly expiresAt?: string;
}

/**
 * Stable timeline-facing reference to deterministic composition input.
 *
 * A RenderMaterialRef points at source material used to compose or bake a
 * timeline object. It is not the final export output; final outputs use
 * RenderArtifact so planners can distinguish consumed inputs from produced
 * files and sidecars.
 */
export interface RenderMaterialRef {
  readonly id: string;
  readonly mediaKind: RenderMaterialMediaKind;
  readonly locator: RenderStorageLocator;
  readonly producerExtensionId?: string;
  readonly producerVersion?: string;
  readonly determinism: DeterminismStatus;
  readonly replacementPolicy: 'replace-live-ref' | 'preserve-live-ref' | 'materialize-on-export';
}

/** Concrete material metadata plus optional duration/range constraints. */
export interface RenderMaterial extends RenderMaterialRef {
  readonly durationSeconds?: number;
  readonly frameRange?: readonly [startFrame: number, endFrame: number];
  readonly sampleRange?: readonly [startSample: number, endSample: number];
  readonly inputHash?: string;
  readonly metadata?: Record<string, unknown>;
}

/** Boundary where a material or artifact may cross provider/process/storage. */
export interface ArtifactBoundary {
  readonly source: 'provider' | 'browser' | 'worker' | 'sidecar-process' | 'artifact-store';
  readonly target: 'provider' | 'browser' | 'worker' | 'sidecar-process' | 'artifact-store' | 'export-output';
  readonly route: RenderRoute;
  readonly failureBehavior: 'block-export' | 'fallback-to-preview' | 'emit-diagnostic';
}

/** Final output or sidecar produced by a render/bake route. */
export interface RenderArtifact {
  readonly id: string;
  readonly route: RenderRoute;
  readonly locator: RenderStorageLocator;
  readonly mediaKind: RenderMaterialMediaKind;
  readonly producerExtensionId?: string;
  readonly producerVersion?: string;
  readonly consumedMaterialRefs: readonly RenderMaterialRef[];
  readonly determinism: DeterminismStatus;
  readonly boundary: ArtifactBoundary;
  readonly findings?: readonly CapabilityFinding[];
}

/** Contract a contribution declares for replacing live/runtime refs with artifacts. */
export interface BakeContract {
  readonly id: string;
  readonly route: RenderRoute;
  readonly inputMaterialRefs: readonly RenderMaterialRef[];
  readonly outputArtifactKind: RenderMaterialMediaKind;
  readonly determinism: DeterminismStatus;
  readonly boundary: ArtifactBoundary;
  readonly replacementPolicy: RenderMaterialRef['replacementPolicy'];
  readonly blockers?: readonly RenderBlocker[];
}
