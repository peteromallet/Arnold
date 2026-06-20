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
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly manifest?: RenderArtifactManifest;
}

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
