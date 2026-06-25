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
