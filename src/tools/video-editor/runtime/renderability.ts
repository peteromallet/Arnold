/**
 * Shared renderability and artifact vocabulary for provider-scoped
 * registries and export-readiness planning.
 *
 * These contracts are intentionally data-only. Registries own lifecycle and
 * snapshots, export guards produce findings/blockers, and later planners can
 * aggregate the same records without renaming fields.
 */

export {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@/sdk/video/rendering/renderability.ts';
export type {
  CapabilityFinding,
  CapabilityFindingSeverity,
  ContributionRenderability,
  DeterminismStatus,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderCapabilityStatus,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';
export {
  describeShaderMaterializerRequirementScope,
  shaderMissingMaterializerBlockerMessage,
} from '@/sdk/video/rendering/capabilities.ts';
export type { ShaderMaterializerRequirementScope } from '@/sdk/video/rendering/capabilities.ts';
export type {
  ArtifactBoundary,
  BakeContract,
  RenderArtifact,
  RenderArtifactManifest,
  RenderArtifactSidecarDescriptor,
  RenderArtifactSidecarKind,
  RenderLocatorKind,
  RenderMaterial,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts.ts';

import type {
  RenderArtifact,
  RenderArtifactManifest,
  RenderArtifactSidecarDescriptor,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts.ts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';

export type ManifestedRenderArtifact = RenderArtifact & {
  readonly manifest: RenderArtifactManifest;
};

export function assertFinalArtifactHasManifest(
  artifact: RenderArtifact,
  producer: string,
): asserts artifact is ManifestedRenderArtifact {
  if (!artifact.manifest) {
    throw new Error(
      `Final render artifact "${artifact.id}" from ${producer} is missing a render artifact manifest. ` +
      'Route final artifact creation through createRenderArtifactManifest().',
    );
  }
  if (artifact.manifest.artifactId !== artifact.id) {
    throw new Error(
      `Final render artifact "${artifact.id}" from ${producer} has manifest artifactId ` +
      `"${artifact.manifest.artifactId}".`,
    );
  }
  if (artifact.manifest.route !== artifact.route) {
    throw new Error(
      `Final render artifact "${artifact.id}" from ${producer} has manifest route ` +
      `"${artifact.manifest.route}" but artifact route "${artifact.route}".`,
    );
  }
  if (artifact.manifest.determinism !== artifact.determinism) {
    throw new Error(
      `Final render artifact "${artifact.id}" from ${producer} has manifest determinism ` +
      `"${artifact.manifest.determinism}" but artifact determinism "${artifact.determinism}".`,
    );
  }
}

export interface CreateRenderArtifactManifestParams {
  readonly id?: string;
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
  readonly consumedMaterialRefs?: readonly RenderMaterialRef[];
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
  readonly provenance?: Record<string, unknown>;
  readonly inputHashes?: Record<string, string>;
  readonly renderGroupId?: string;
  readonly passName?: string;
  readonly createdAt?: string;
  readonly metadata?: Record<string, unknown>;
}

/**
 * Return a stable, frozen sidecar list. Missing sidecar IDs are derived from
 * stable visible fields so manifests can reference sidecars consistently.
 */
export function normalizeRenderArtifactSidecars(
  sidecars: readonly RenderArtifactSidecarDescriptor[] = [],
): readonly RenderArtifactSidecarDescriptor[] {
  return Object.freeze(
    sidecars
      .map((sidecar) => Object.freeze({
        ...sidecar,
        id: sidecar.id ?? `sidecar.${sidecar.kind}.${sidecar.filename}`,
        byteSize: sidecar.byteSize ?? sidecar.data?.byteLength,
      }))
      .sort(compareSidecars),
  );
}

/** Create a stable, frozen artifact manifest from render/export metadata. */
export function createRenderArtifactManifest(
  params: CreateRenderArtifactManifestParams,
): RenderArtifactManifest {
  const consumedMaterialRefs = Object.freeze(
    [...(params.consumedMaterialRefs ?? [])].sort(compareMaterialRefs),
  );
  const sidecars = normalizeRenderArtifactSidecars(params.sidecars);
  const diagnostics = params.diagnostics?.length
    ? Object.freeze([...params.diagnostics].sort(compareFindings))
    : undefined;

  const manifest: RenderArtifactManifest = {
    id: params.id ?? `manifest.${params.artifactId}`,
    schemaVersion: 1,
    artifactId: params.artifactId,
    route: params.route,
    determinism: params.determinism,
    producerExtensionId: params.producerExtensionId,
    producerVersion: params.producerVersion,
    outputFormatId: params.outputFormatId,
    processId: params.processId,
    processVersion: params.processVersion,
    operationId: params.operationId,
    locator: params.locator,
    mediaKind: params.mediaKind,
    consumedMaterialRefs,
    sidecars,
    diagnostics,
    provenance: params.provenance,
    inputHashes: params.inputHashes ? Object.freeze({ ...params.inputHashes }) : undefined,
    renderGroupId: params.renderGroupId,
    passName: params.passName,
    createdAt: params.createdAt,
    metadata: params.metadata,
  };

  return Object.freeze(manifest);
}

/** Serialize a manifest with sorted object keys for byte-stable JSON output. */
export function serializeRenderArtifactManifest(manifest: RenderArtifactManifest): string {
  return JSON.stringify(toStableJsonValue(manifest));
}

/**
 * Build the downloadable manifest sidecar for an already-created manifest.
 * The sidecar bytes are exactly the stable serialized manifest payload.
 */
export function createRenderArtifactManifestSidecar(
  manifest: RenderArtifactManifest,
  filename = 'render-manifest.json',
): RenderArtifactSidecarDescriptor {
  const data = new TextEncoder().encode(serializeRenderArtifactManifest(manifest));
  return Object.freeze({
    id: `sidecar.manifest.${manifest.id}`,
    filename,
    mimeType: 'application/json',
    kind: 'manifest',
    data,
    byteSize: data.byteLength,
    provenance: Object.freeze({
      manifestId: manifest.id,
      artifactId: manifest.artifactId,
    }),
  });
}

// ---------------------------------------------------------------------------
// Compile-only output artifact helpers
// ---------------------------------------------------------------------------

/**
 * Route used for compile-only output artifacts.
 * Compile-only outputs never invoke render providers, render planning,
 * or media render routes.
 */
export const COMPILE_ONLY_ARTIFACT_ROUTE: RenderRoute = 'browser-export';

/**
 * Parameters for constructing a {@link RenderArtifact} from a compile-only
 * output execution.
 */
export interface CompileOnlyArtifactParams {
  /** Unique artifact ID. */
  readonly artifactId: string;
  /** The output bytes from the compile-only handler. */
  readonly data: Uint8Array;
  /** MIME type of the output. */
  readonly mimeType: string;
  /** Suggested filename for the output. */
  readonly filename: string;
  /** Output format contribution ID, when the artifact came from a format handler. */
  readonly outputFormatId?: string;
  /** Extension that produced the output. */
  readonly producerExtensionId?: string;
  /** Extension version, if available. */
  readonly producerVersion?: string;
  /** Sidecars emitted by the output handler or producer. */
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  /** Optional provenance carried into the artifact manifest. */
  readonly provenance?: Record<string, unknown>;
  /** Optional input hash map carried into the artifact manifest. */
  readonly inputHashes?: Record<string, string>;
  /** Optional stable metadata carried into the artifact manifest. */
  readonly metadata?: Record<string, unknown>;
  /** Asset keys consumed from the registry during compilation. */
  readonly consumedAssetKeys?: readonly string[];
  /**
   * Diagnostics produced during compilation.
   * Error-severity diagnostics that are blocking will be surfaced in findings.
   */
  readonly diagnostics?: readonly {
    severity: 'error' | 'warning' | 'info';
    code: string;
    message: string;
    assetKey?: string;
    extensionId?: string;
    contributionId?: string;
    detail?: Record<string, unknown>;
  }[];
  /** Whether the compilation produced blocking errors. */
  readonly hasBlockingErrors?: boolean;
}

/**
 * Create a deterministic {@link RenderArtifact} from a compile-only output
 * execution result.
 *
 * Compile-only artifacts are always marked `deterministic` because they
 * are produced from read-only timeline + asset data without external
 * processes, render providers, or media render routes.
 */
export function createCompileOnlyArtifact(params: CompileOnlyArtifactParams): RenderArtifact {
  const findings: CapabilityFinding[] = [];

  // Convert diagnostics to findings
  for (const diag of params.diagnostics ?? []) {
    findings.push({
      id: `compile-only.${params.artifactId}.${diag.code}`,
      severity: diag.severity === 'error' ? 'error' : diag.severity === 'warning' ? 'warning' : 'info',
      route: COMPILE_ONLY_ARTIFACT_ROUTE,
      reason: diag.severity === 'error' ? 'unknown' : undefined,
      message: diag.message,
      extensionId: diag.extensionId ?? params.producerExtensionId,
      contributionId: diag.contributionId,
      detail: diag.detail,
    });
  }

  // Build consumed material refs from asset keys
  const consumedMaterialRefs: RenderMaterialRef[] = (params.consumedAssetKeys ?? []).map((key) => ({
    id: `material.asset.${key}`,
    mediaKind: 'unknown',
    locator: {
      kind: 'asset-registry',
      uri: `asset://${key}`,
    },
    determinism: 'deterministic',
    replacementPolicy: 'preserve-live-ref',
  }));
  const frozenConsumedMaterialRefs = Object.freeze(consumedMaterialRefs);
  const sidecars = normalizeRenderArtifactSidecars(params.sidecars);
  const locator: RenderStorageLocator = Object.freeze({
    kind: 'inline',
    uri: params.filename,
    mimeType: params.mimeType,
  });
  const mediaKind = mimeTypeToMediaKind(params.mimeType);
  const boundary: ArtifactBoundary = Object.freeze({
    source: 'browser',
    target: 'export-output',
    route: COMPILE_ONLY_ARTIFACT_ROUTE,
    failureBehavior: 'emit-diagnostic',
  });
  const frozenFindings = findings.length > 0 ? Object.freeze(findings) : undefined;
  const manifest = createRenderArtifactManifest({
    artifactId: params.artifactId,
    route: COMPILE_ONLY_ARTIFACT_ROUTE,
    determinism: 'deterministic',
    producerExtensionId: params.producerExtensionId,
    producerVersion: params.producerVersion,
    outputFormatId: params.outputFormatId,
    locator,
    mediaKind,
    consumedMaterialRefs: frozenConsumedMaterialRefs,
    sidecars,
    diagnostics: frozenFindings,
    provenance: params.provenance,
    inputHashes: params.inputHashes,
    metadata: params.metadata,
  });

  const artifact: RenderArtifact = {
    id: params.artifactId,
    route: COMPILE_ONLY_ARTIFACT_ROUTE,
    locator,
    mediaKind,
    producerExtensionId: params.producerExtensionId,
    producerVersion: params.producerVersion,
    consumedMaterialRefs: frozenConsumedMaterialRefs,
    determinism: 'deterministic',
    boundary,
    findings: frozenFindings,
    sidecars,
    manifest,
  };

  assertFinalArtifactHasManifest(artifact, 'createCompileOnlyArtifact');

  return Object.freeze(artifact);
}

/**
 * Map a MIME type string to a {@link RenderMaterialMediaKind}.
 */
function mimeTypeToMediaKind(mimeType: string): RenderMaterialMediaKind {
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (mimeType === 'application/json' || mimeType.endsWith('+json')) return 'json';
  if (mimeType.startsWith('text/')) return 'text';
  if (mimeType === 'application/octet-stream') return 'binary';
  return 'unknown';
}

function compareSidecars(a: RenderArtifactSidecarDescriptor, b: RenderArtifactSidecarDescriptor): number {
  return compareStrings(a.id ?? '', b.id ?? '')
    || compareStrings(a.kind, b.kind)
    || compareStrings(a.filename, b.filename);
}

function compareMaterialRefs(a: RenderMaterialRef, b: RenderMaterialRef): number {
  return compareStrings(a.id, b.id)
    || compareStrings(a.locator.uri, b.locator.uri)
    || compareStrings(a.mediaKind, b.mediaKind);
}

function compareFindings(a: CapabilityFinding, b: CapabilityFinding): number {
  return compareStrings(a.id, b.id)
    || compareStrings(a.severity, b.severity)
    || compareStrings(a.message, b.message);
}

function compareStrings(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function toStableJsonValue(value: unknown): unknown {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (value instanceof Uint8Array) return Array.from(value);
  if (Array.isArray(value)) return value.map((item) => toStableJsonValue(item));
  if (typeof value !== 'object') return value;

  const record = value as Record<string, unknown>;
  const stableRecord: Record<string, unknown> = {};
  for (const key of Object.keys(record).sort()) {
    const stableValue = toStableJsonValue(record[key]);
    if (stableValue !== undefined) {
      stableRecord[key] = stableValue;
    }
  }
  return stableRecord;
}
