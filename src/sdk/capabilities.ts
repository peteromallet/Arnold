/**
 * Capability, sampling, and process-roundtrip contracts for the Reigh Editor SDK.
 *
 * M12 core contracts: capability requirements, source references, route-fit
 * metadata, versioning, integration capabilities, sampling descriptors,
 * process-roundtrip vocabulary, and the provider-free getCapabilityRequirements()
 * derivation function.
 *
 * This module carries data-only types that reference video-editor rendering
 * and timeline contracts via type-only imports.  It does not import provider
 * stores, raw timeline rows, mutation APIs, DOM, or host wiring.
 *
 * @publicContract
 */

import type { TimelineSnapshot } from '@/sdk/video/timeline/reader.ts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderBlockerReason,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';
import type {
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderArtifactSidecarKind,
  RenderMaterial,
  RenderMaterialRef,
} from '@/sdk/video/rendering/artifacts.ts';
import { shaderMissingMaterializerBlockerMessage } from '@/sdk/video/rendering/capabilities.ts';

// ---------------------------------------------------------------------------
// Process event / log vocabulary (used by ProcessRoundtripResult)
// ---------------------------------------------------------------------------

export interface ProcessProgressEvent {
  readonly operationId: string;
  readonly percent?: number;
  readonly message?: string;
  readonly currentStep?: string;
  readonly totalSteps?: number;
}

export interface ProcessLogSummary {
  readonly level: 'debug' | 'info' | 'warning' | 'error';
  readonly message: string;
  readonly at?: string;
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M12: Planner requirement contracts — capability requirements, source refs,
// route-fit metadata, capability versioning, and integration capabilities
// ---------------------------------------------------------------------------

/**
 * M12: Version descriptor for a capability or contribution declaration.
 *
 * Carries a semver version and declaration provenance so planners can
 * detect version conflicts and stale registrations without importing
 * registry internals.
 */
export interface CapabilityVersion {
  /** Semantic version string (e.g. "1.0.0"). */
  readonly semver: string;
  /** Extension that declared this version, when applicable. */
  readonly declaredBy?: string;
  /** Contribution that declared this version, when applicable. */
  readonly contributionId?: string;
}

/**
 * M12: Source reference for a capability requirement.
 *
 * Identifies where a capability requirement originates so planners
 * can attribute blockers and findings to the right extension,
 * registry, or built-in source.
 */
export interface CapabilitySourceRef {
  /** The kind of source that produced this capability. */
  readonly source: 'extension' | 'built-in' | 'registry' | 'manifest' | 'provider';
  /** Extension ID, when the source is an extension. */
  readonly extensionId?: string;
  /** Contribution ID, when the source is a specific contribution. */
  readonly contributionId?: string;
  /** Version of the capability declaration, when known. */
  readonly version?: CapabilityVersion;
}

/**
 * M12: Route-fit metadata describing how well a capability maps to a route.
 *
 * Planners use route-fit metadata to decide whether a contribution can
 * authoritatively execute on a given route, or whether it must fall back
 * or block.
 */
export interface RouteFitMetadata {
  /** The route this fit metadata applies to. */
  readonly route: RenderRoute;
  /** Whether the capability supports, blocks, degrades, or is unknown for this route. */
  readonly fit: 'supported' | 'blocked' | 'degraded' | 'unknown';
  /** Reason for the fit, when not 'supported'. */
  readonly reason?: RenderBlockerReason;
  /** Human-readable message explaining the fit. */
  readonly message?: string;
}

/**
 * M12: A single capability requirement produced by the planner.
 *
 * Each CapabilityRequirement describes what a contribution needs for a
 * specific route, its determinism posture, version, source provenance,
 * and any findings discovered during planning. This is the primary
 * record consumed by TimelineReader capability inspection and
 * renderPlanner aggregation.
 */
export interface CapabilityRequirement {
  /** Stable, unique identifier for this requirement. */
  readonly id: string;
  /** Where this requirement originates from. */
  readonly sourceRef: CapabilitySourceRef;
  /** The route this requirement applies to. */
  readonly route: RenderRoute;
  /** Required capabilities for this route (e.g. 'browser-export', 'worker-export'). */
  readonly requiredCapabilities: readonly string[];
  /** Determinism posture for this requirement. */
  readonly determinism: DeterminismStatus;
  /** Route-fit metadata describing how well this requirement fits the route. */
  readonly routeFit?: RouteFitMetadata;
  /** Version of the capability declaration, when known. */
  readonly version?: CapabilityVersion;
  /** Capability findings produced during planning. */
  readonly findings?: readonly CapabilityFinding[];
  /** Whether this requirement is a blocker for its route. */
  readonly blocking?: boolean;
}

/**
 * M12: Minimal integration capabilities consumed by TimelineReader and
 * renderPlanner.
 *
 * Aggregates capability requirements, source references, and route
 * summaries so planners can consume a single normalized capabilities
 * record without importing registry internals or provider state.
 */
export interface IntegrationCapabilities {
  /** Extension that owns these capabilities, when scoped to a single extension. */
  readonly extensionId?: string;
  /** Contribution that owns these capabilities, when scoped to a single contribution. */
  readonly contributionId?: string;
  /** Routes covered by these capabilities. */
  readonly routes: readonly RenderRoute[];
  /** Aggregate determinism posture across all capabilities. */
  readonly determinism: DeterminismStatus;
  /** Individual capability requirements collected during planning. */
  readonly capabilityRequirements: readonly CapabilityRequirement[];
  /** Source references for all capabilities in this integration record. */
  readonly sourceRefs: readonly CapabilitySourceRef[];
  /** Whether all routes are fully supported (no blockers). */
  readonly fullySupported: boolean;
  /** Whether any route is blocked. */
  readonly anyBlocked: boolean;
}

// ---------------------------------------------------------------------------
// M12: Artifact manifest, sidecar, sampling, and process roundtrip contracts
// ---------------------------------------------------------------------------

export type SamplingStrategy =
  | 'whole-timeline'
  | 'clip-slices'
  | 'frame-extracts'
  | 'thumbnail-grid'
  | 'audio-windows'
  | 'render-groups';

export interface SamplingSourceRef {
  readonly kind: 'timeline' | 'clip' | 'track' | 'asset' | 'material' | 'render-group';
  readonly id: string;
  readonly clipId?: string;
  readonly trackId?: string;
  readonly assetKey?: string;
  readonly materialRefId?: string;
  readonly renderGroupId?: string;
}

export interface SamplingRange {
  readonly startFrame?: number;
  readonly endFrame?: number;
  readonly startSeconds?: number;
  readonly endSeconds?: number;
  readonly startSample?: number;
  readonly endSample?: number;
}

export type SamplingAttachmentKind = 'label' | 'caption' | 'cue' | 'provenance' | 'metadata';

export interface SamplingAttachmentRule {
  readonly kind: SamplingAttachmentKind;
  readonly fieldPath?: string;
  readonly sidecarKind?: RenderArtifactSidecarKind;
  readonly required?: boolean;
}

/** M12: Declarative sampling request consumed by planners and export shells. */
export interface SamplingConfig {
  readonly id?: string;
  readonly strategy: SamplingStrategy;
  readonly sources: readonly SamplingSourceRef[];
  readonly range?: SamplingRange;
  readonly fps?: number;
  readonly sampleRate?: number;
  readonly resolution?: string;
  readonly sliceClips?: boolean;
  readonly attachments?: readonly SamplingAttachmentRule[];
  readonly includeLabels?: boolean;
  readonly includeCaptions?: boolean;
  readonly includeProvenance?: boolean;
}

export interface SamplingResultItem {
  readonly id: string;
  readonly sourceRef: SamplingSourceRef;
  readonly range?: SamplingRange;
  readonly frame?: number;
  readonly timestampSeconds?: number;
  readonly artifactId?: string;
  readonly manifestEntryId?: string;
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
}

/** M12: Result vocabulary for dry-runs and dataset/show-control exports. */
export interface SamplingResult {
  readonly configId?: string;
  readonly items: readonly SamplingResultItem[];
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly manifestRefs?: readonly string[];
  readonly diagnostics?: readonly CapabilityFinding[];
}

export interface ProcessRoundtripRequest {
  readonly id: string;
  readonly processId: string;
  readonly operationId: string;
  readonly inputMaterialRefs?: readonly RenderMaterialRef[];
  readonly inputArtifactRefs?: readonly RenderArtifact[];
  readonly params?: Record<string, unknown>;
  readonly frameRange?: SamplingRange;
  readonly renderGroupId?: string;
  readonly passNames?: readonly string[];
  readonly sampling?: SamplingConfig;
}

export type ProcessRoundtripAction =
  | 'insert-as-clip'
  | 'replace-clip'
  | 'attach-to-clip'
  | 'download-sidecar'
  | 'discard'
  | 'create-proposal';

export interface ProcessRoundtripResult {
  readonly requestId: string;
  readonly processId: string;
  readonly operationId: string;
  readonly status: 'completed' | 'failed' | 'cancelled';
  readonly returnedMaterials: readonly RenderMaterial[];
  readonly artifacts?: readonly RenderArtifact[];
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
  readonly logs?: readonly ProcessLogSummary[];
  readonly progress?: ProcessProgressEvent;
  readonly availableActions?: readonly ProcessRoundtripAction[];
  readonly metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M12: getCapabilityRequirements — provider-free capability inspection
// ---------------------------------------------------------------------------

/**
 * M12: Derive capability requirements from a TimelineSnapshot.
 *
 * Inspects clip types, effects, transitions, live bindings, and material
 * refs present in the snapshot and emits {@link CapabilityRequirement}
 * records without importing provider stores, raw timeline rows, or
 * mutation APIs.
 *
 * The returned requirements are data-only; they carry route-fit metadata
 * and determinism posture so planners can aggregate them without
 * re-deriving the same information from raw timeline data.
 *
 * @param snapshot - A TimelineSnapshot produced by a TimelineReader.
 * @returns Ordered array of CapabilityRequirement records.
 */
export function getCapabilityRequirements(
  snapshot: TimelineSnapshot,
): CapabilityRequirement[] {
  const requirements: CapabilityRequirement[] = [];
  let reqCounter = 0;

  const nextId = (prefix: string): string => {
    reqCounter += 1;
    return `snapshot.${prefix}.${reqCounter}`;
  };

  // Guard: if snapshot has no clips, return empty.
  if (!snapshot.clips || snapshot.clips.length === 0) {
    return requirements;
  }

  // ── Clip-type requirements ──────────────────────────────────────────
  const seenClipTypes = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.clipType || seenClipTypes.has(clip.clipType)) continue;
    seenClipTypes.add(clip.clipType);

    const sourceRef: CapabilitySourceRef = clip.managedBy
      ? {
          source: 'extension',
          extensionId: clip.managedBy,
        }
      : { source: 'built-in' };

    requirements.push({
      id: nextId('clipType'),
      sourceRef,
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: clip.managedBy ? 'preview-only' : 'deterministic',
    });
  }

  // ── Effect requirements ─────────────────────────────────────────────
  const seenEffects = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.effects) continue;
    for (const effect of clip.effects) {
      const effectKey = `${clip.id}.${effect.effectType ?? 'unknown'}`;
      if (seenEffects.has(effectKey)) continue;
      seenEffects.add(effectKey);

      const sourceRef: CapabilitySourceRef = effect.managedBy
        ? {
            source: 'extension',
            extensionId: effect.managedBy,
          }
        : { source: 'built-in' };

      requirements.push({
        id: nextId('effect'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export'],
        determinism: effect.managedBy ? 'preview-only' : 'deterministic',
        findings: effect.managedBy
          ? undefined
          : [
              {
                id: `builtin.effect.${effect.effectType ?? 'unknown'}.${clip.id}`,
                severity: 'info',
                route: 'browser-export',
                message: `Built-in effect "${effect.effectType ?? 'unknown'}" on clip "${clip.id}" is deterministic for browser export.`,
                clipId: clip.id,
              },
            ],
      });
    }
  }

  // ── Transition requirements ─────────────────────────────────────────
  const seenTransitions = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.transition) continue;
    const tKey = `${clip.id}.${clip.transition.transitionType ?? 'unknown'}`;
    if (seenTransitions.has(tKey)) continue;
    seenTransitions.add(tKey);

    const sourceRef: CapabilitySourceRef = clip.transition.managedBy
      ? {
          source: 'extension',
          extensionId: clip.transition.managedBy,
        }
      : { source: 'built-in' };

    requirements.push({
      id: nextId('transition'),
      sourceRef,
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: clip.transition.managedBy ? 'preview-only' : 'deterministic',
    });
  }

  // ── Live-binding requirements ───────────────────────────────────────
  if (snapshot.liveBindings) {
    const seenBindings = new Set<string>();
    for (const binding of snapshot.liveBindings) {
      if (seenBindings.has(binding.bindingId)) continue;
      seenBindings.add(binding.bindingId);

      const sourceRef: CapabilitySourceRef = {
        source: 'provider',
      };

      const isBlocking = binding.status !== 'resolved';

      requirements.push({
        id: nextId('liveBinding'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export', 'sidecar-export'],
        determinism: 'live-unbaked',
        blocking: isBlocking,
        routeFit: isBlocking
          ? {
              route: 'browser-export',
              fit: 'blocked',
              reason: 'live-unbaked',
              message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is not resolved.`,
            }
          : {
              route: 'browser-export',
              fit: 'supported',
            },
        findings: [
          isBlocking
            ? {
                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
                severity: 'warning',
                route: 'browser-export',
                reason: 'live-unbaked',
                message: `Live binding "${binding.bindingId}" (source: ${binding.sourceKind}) on clip "${binding.clipId}" has status "${binding.status ?? 'unknown'}".`,
                clipId: binding.clipId,
              }
            : {
                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
                severity: 'info',
                route: 'browser-export',
                message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is resolved.`,
                clipId: binding.clipId,
              },
        ],
      });
    }
  }

  // ── Material-ref requirements ───────────────────────────────────────
  if (snapshot.materialRefs) {
    for (const ref of snapshot.materialRefs) {
      const sourceRef: CapabilitySourceRef = {
        source: 'registry',
      };

      requirements.push({
        id: nextId('materialRef'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export'],
        determinism: ref.determinism ?? 'unknown',
      });
    }
  }

  // ── Source-ref requirements ────────────────────────────────────────
  if (snapshot.sourceRefs) {
    for (const ref of snapshot.sourceRefs) {
      const sourceRef: CapabilitySourceRef = ref.extensionId
        ? {
            source: 'extension',
            extensionId: ref.extensionId,
          }
        : {
            source: ref.sourceKind === 'generation' ? 'provider' : 'registry',
          };

      const determinism = ref.determinism ?? 'unknown';
      const blocksBrowserExport =
        determinism === 'process-dependent' || determinism === 'live-unbaked';

      requirements.push({
        id: nextId('sourceRef'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: blocksBrowserExport
          ? ['browser-export', 'sidecar-export']
          : ['browser-export'],
        determinism,
        ...(blocksBrowserExport
          ? {
              blocking: true,
              routeFit: {
                route: 'browser-export',
                fit: 'blocked',
                reason: determinism,
                message: `Source ref "${ref.id}" on clip "${ref.clipId}" requires materialization before browser export.`,
              },
            }
          : {}),
      });
    }
  }

  // ── Shader materializer requirements ───────────────────────────────
  if (snapshot.shaders) {
    for (const shader of snapshot.shaders) {
      if (shader.enabled === false) continue;

      const sourceRef: CapabilitySourceRef = {
        source: 'extension',
        extensionId: shader.extensionId,
        contributionId: shader.contributionId,
      };
      const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];

      for (const route of routes) {
        const message = shaderMissingMaterializerBlockerMessage(
          shader.shaderId,
          shader.scope,
          shader.clipId,
        );
        requirements.push({
          id: nextId('shader'),
          sourceRef,
          route,
          requiredCapabilities: ['render-material', 'shader-materializer'],
          determinism: 'preview-only',
          blocking: true,
          routeFit: {
            route,
            fit: 'blocked',
            reason: 'missing-material',
            message,
          },
        });
      }
    }
  }

  return requirements;
}
