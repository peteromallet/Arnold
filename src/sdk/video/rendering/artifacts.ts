import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderBlocker,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';

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

export type RenderMaterialStatusState =
  | 'missing'
  | 'pending'
  | 'resolved'
  | 'stale'
  | 'failed';

export const RENDER_MATERIAL_STATUSES = [
  'missing',
  'pending',
  'resolved',
  'stale',
  'failed',
] as const satisfies readonly RenderMaterialStatusState[];
Object.freeze(RENDER_MATERIAL_STATUSES);

export type RenderMaterialStatusPhase = 'queued' | 'active' | 'live-only';

export const RENDER_MATERIAL_STATUS_PHASES = [
  'queued',
  'active',
  'live-only',
] as const satisfies readonly RenderMaterialStatusPhase[];
Object.freeze(RENDER_MATERIAL_STATUS_PHASES);

export type RenderMaterialStatusQuality = 'weaker-provenance' | 'route-incompatible';

export const RENDER_MATERIAL_STATUS_QUALITIES = [
  'weaker-provenance',
  'route-incompatible',
] as const satisfies readonly RenderMaterialStatusQuality[];
Object.freeze(RENDER_MATERIAL_STATUS_QUALITIES);

export interface RenderMaterialStatusDetail {
  readonly phase?: RenderMaterialStatusPhase;
  readonly quality?: RenderMaterialStatusQuality;
}

export interface RenderMaterialStatus {
  readonly materialRefId: string;
  readonly state: RenderMaterialStatusState;
  readonly message?: string;
  readonly updatedAt?: string;
  readonly detail?: RenderMaterialStatusDetail;
}

type RenderMaterialStatusLike = Pick<RenderMaterialStatus, 'state' | 'detail'> | null | undefined;

export function isActiveBake(status: RenderMaterialStatusLike): boolean {
  return status?.state === 'pending' && status.detail?.phase === 'active';
}

export function isLiveOnly(status: RenderMaterialStatusLike): boolean {
  return status?.state === 'missing' && status.detail?.phase === 'live-only';
}

export function isWeakerProvenance(status: RenderMaterialStatusLike): boolean {
  return status?.detail?.quality === 'weaker-provenance';
}

export function isRouteIncompatible(status: RenderMaterialStatusLike): boolean {
  return status?.detail?.quality === 'route-incompatible';
}

// ---------------------------------------------------------------------------
// Provenance helpers (M3a)
// ---------------------------------------------------------------------------

/**
 * Structured description of a provenance gap when validation fails.
 *
 * Produced by {@link describeProvenanceGap} and attached to
 * `composition/material-missing-provenance` diagnostics so consumers
 * can render actionable messaging without inspecting raw material refs.
 */
export interface ProvenanceGap {
  /** Why provenance is considered insufficient. */
  readonly reason: 'absent' | 'empty' | 'no-producer-metadata';
  /** Human-readable summary of what is missing. */
  readonly message: string;
}

/**
 * Returns `true` when the provenance record has one or more own keys.
 * Treats `undefined`, `null`, and empty objects consistently as absent.
 */
export function hasProvenance(
  provenance: Record<string, unknown> | undefined | null,
): boolean {
  return !!provenance && Object.keys(provenance).length > 0;
}

/**
 * Describe the provenance gap for a material that has no recorded or
 * derivable provenance.  The result is suitable for the `provenanceGap`
 * field of a {@link CompositionDiagnosticDetail}.
 *
 * Derivation of material origin should only consider existing producer
 * metadata (`producerExtensionId`, `producerVersion`) plus determinism
 * where available.  This function does NOT inspect bake/capture/agent
 * or process execution state.
 */
export function describeProvenanceGap(
  provenance: Record<string, unknown> | undefined | null,
  producerExtensionId: string | undefined,
  producerVersion: string | undefined,
): ProvenanceGap {
  if (!provenance || Object.keys(provenance).length === 0) {
    if (!producerExtensionId && !producerVersion) {
      return {
        reason: 'no-producer-metadata',
        message:
          'No provenance record or producer metadata; material origin cannot be verified.',
      };
    }
    return {
      reason: 'empty',
      message:
        'Provenance record is empty; material origin derived from producer metadata only.',
    };
  }

  return {
    reason: 'absent',
    message:
      'No provenance record available; material origin cannot be independently verified.',
  };
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
  readonly provenance?: Record<string, unknown>;
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

export type RenderArtifactSidecarKind =
  | 'metadata'
  | 'thumbnail'
  | 'scene-report'
  | 'log'
  | 'provenance'
  | 'rendered-pass'
  | 'cue'
  | 'label'
  | 'caption'
  | 'diagnostics'
  | 'manifest'
  | 'other';

/** Data-only descriptor for a downloadable or previewable sidecar artifact. */
export interface RenderArtifactSidecarDescriptor {
  readonly id?: string;
  readonly filename: string;
  readonly mimeType: string;
  readonly kind: RenderArtifactSidecarKind;
  readonly data?: Uint8Array;
  readonly locator?: RenderStorageLocator;
  readonly byteSize?: number;
  readonly renderGroupId?: string;
  readonly passName?: string;
  readonly diagnostics?: readonly CapabilityFinding[];
  readonly provenance?: Record<string, unknown>;
}

/** Stable manifest entry for a final render/export artifact. */
export interface RenderArtifactManifest {
  readonly id: string;
  readonly schemaVersion: 1;
  readonly artifactId: string;
  readonly route: RenderRoute;
  readonly determinism: DeterminismStatus;
  readonly producerExtensionId?: string;
  readonly producerVersion?: string;
  readonly outputFormatId?: string;
  readonly processId?: string;
  readonly processVersion?: {
    readonly semver: string;
    readonly declaredBy?: string;
    readonly contributionId?: string;
  };
  readonly operationId?: string;
  readonly locator?: RenderStorageLocator;
  readonly mediaKind?: RenderMaterialMediaKind;
  readonly consumedMaterialRefs: readonly RenderMaterialRef[];
  readonly sidecars: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
  readonly provenance?: Record<string, unknown>;
  readonly inputHashes?: Record<string, string>;
  readonly renderGroupId?: string;
  readonly passName?: string;
  readonly createdAt?: string;
  readonly metadata?: Record<string, unknown>;
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
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly manifest?: RenderArtifactManifest;
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
