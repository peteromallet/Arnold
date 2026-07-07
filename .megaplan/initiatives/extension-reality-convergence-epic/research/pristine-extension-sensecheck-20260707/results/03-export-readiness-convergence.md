Reading additional input from stdin...
OpenAI Codex v0.137.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/reigh-app
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f3a0c-4ca2-7941-8c23-0e549713805b
--------
user
# Codex Sense-Check: Export Readiness Convergence

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for export readiness convergence.

The criticism to evaluate:

> Make render-planner blockers the only thing that decides export readiness, so the user-facing story stops being "supported here, mysterious blocker there."

## What To Inspect

Prioritize current code:

- `src/tools/video-editor/runtime/renderPlanner.ts`
- `src/tools/video-editor/runtime/renderPlanner.test.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- `src/tools/video-editor/runtime/exportGuard.ts`
- `src/tools/video-editor/runtime/exportGuard.test.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/render/**`
- `src/tools/video-editor/compositions/**`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/outputFormatRegistry.ts`
- `src/tools/video-editor/runtime/processCommandRegistration.ts`
- `src/tools/video-editor/shaders/**`
- docs under `docs/extensions/**`, `docs/video-editor/shader-execution-model.md`, `docs/video-editor/provider-compatibility-matrix.md`
- examples/canaries related to output formats, shaders, live data, effects, transitions, clip types

## Questions

1. What currently decides export readiness?
2. Are render planner blockers already authoritative anywhere?
3. What legacy/export guard paths can produce user-visible blockers outside planner vocabulary?
4. Is it feasible to make render-planner blockers the sole export readiness gate now, or should this be a staged convergence?
5. What would a pristine export-readiness model look like?

## Output

Markdown under 1800 words:

# Export Readiness Convergence
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What export readiness should become.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests/scripts/docs checks needed.
## Biggest Trap
The tempting but wrong thing to do.
codex
I’ll use the repo’s context-mining posture here: keep this read-only and gather facts with targeted searches, then return only the conclusion. I’m going to inspect the named runtime files first, then fan out into render/composition/docs/canaries where the readiness vocabulary leaks.
exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/runtime/renderPlanner.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import {
  getCapabilityRequirements,
  type CapabilityFinding,
  type CapabilityRequirement,
  type DeterminismStatus,
  type ProcessStatus,
  type RenderBlocker,
  type RenderBlockerReason,
  type RenderMaterialRef,
  type RenderRoute,
  RENDER_ROUTES,
  type TimelineSnapshot,
  type TimelineShaderSummary,
} from '@reigh/editor-sdk';
import type {
  ExtensionRuntime,
  VideoEditorOutputFormatDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorProcessRequirementDescriptor,
  VideoEditorRouteRequirementDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface RenderPlannerRequest {
  readonly route?: RenderRoute;
  readonly routes?: readonly RenderRoute[];
  readonly outputFormatId?: string;
  readonly requiredCapabilities?: readonly string[];
}

export type RenderPlannerMaterialState = 'missing' | 'stale' | 'resolved' | 'unbaked';

export interface RenderPlannerMaterialStatus {
  readonly materialRefId: string;
  readonly state: RenderPlannerMaterialState;
  readonly message?: string;
  readonly updatedAt?: string;
}

export interface RenderPlannerInput {
  readonly snapshot?: TimelineSnapshot | null;
  readonly requirements?: readonly CapabilityRequirement[];
  readonly extensionRuntime?: Pick<ExtensionRuntime, 'outputFormats' | 'processes' | 'shaders'>;
  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
  readonly processes?: readonly VideoEditorProcessDescriptor[];
  readonly shaders?: readonly VideoEditorShaderDescriptor[];
  readonly processStatuses?: readonly ProcessStatus[];
  readonly materialRefs?: readonly RenderMaterialRef[];
  readonly materialStatuses?: readonly RenderPlannerMaterialStatus[];
  readonly request?: RenderPlannerRequest;
  readonly diagnostics?: readonly CapabilityFinding[];
}

export interface RenderRouteSummary {
  readonly route: RenderRoute;
  readonly blockerCount: number;
  readonly findingCount: number;
  readonly blocked: boolean;
}

export interface RenderRoutePlan extends RenderRouteSummary {
  readonly requiredCapabilities: readonly string[];
  readonly determinism: DeterminismStatus;
  readonly blockers: readonly RenderBlocker[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly outputFormatIds: readonly string[];
  readonly processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
}

export interface RenderPlannerGuardCompatibility {
  readonly diagnostics: readonly CapabilityFinding[];
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly unknownClipTypes: readonly string[];
  readonly unknownEffects: readonly string[];
  readonly unknownTransitions: readonly string[];
  readonly inactiveExtensionIds: {
    readonly effectIds: ReadonlySet<string>;
    readonly transitionIds: ReadonlySet<string>;
    readonly clipTypeIds: ReadonlySet<string>;
  };
  readonly hasBlockingErrors: boolean;
}

export interface RenderPlannerResult {
  readonly guard: RenderPlannerGuardCompatibility;
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly routes: readonly RenderRouteSummary[];
  readonly routePlans: readonly RenderRoutePlan[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
  readonly canBrowserExport: boolean;
  readonly canWorkerExport: boolean;
}

interface PlanAccumulator {
  findings: CapabilityFinding[];
  blockers: RenderBlocker[];
  nextActions: VideoEditorPlannerNextActionDescriptor[];
  routeCapabilities: Map<RenderRoute, Set<string>>;
  routeOutputFormatIds: Map<RenderRoute, Set<string>>;
  routeProcessRequirements: Map<RenderRoute, VideoEditorProcessRequirementDescriptor[]>;
  routeDeterminism: Map<RenderRoute, DeterminismStatus[]>;
}

const EMPTY_IDS = Object.freeze({
  effectIds: Object.freeze(new Set<string>()),
  transitionIds: Object.freeze(new Set<string>()),
  clipTypeIds: Object.freeze(new Set<string>()),
});

const DETERMINISM_RANK: Record<DeterminismStatus, number> = {
  deterministic: 0,
  'preview-only': 1,
  'live-unbaked': 2,
  'process-dependent': 3,
  unknown: 4,
};

function createAccumulator(): PlanAccumulator {
  return {
    findings: [],
    blockers: [],
    nextActions: [],
    routeCapabilities: new Map(),
    routeOutputFormatIds: new Map(),
    routeProcessRequirements: new Map(),
    routeDeterminism: new Map(),
  };
}

function addRouteValue<T>(map: Map<RenderRoute, T[]>, route: RenderRoute, value: T): void {
  const values = map.get(route);
  if (values) {
    values.push(value);
    return;
  }
  map.set(route, [value]);
}

function addRouteSetValue(map: Map<RenderRoute, Set<string>>, route: RenderRoute, value: string): void {
  const values = map.get(route);
  if (values) {
    values.add(value);
    return;
  }
  map.set(route, new Set([value]));
}

function freezeFinding(finding: CapabilityFinding): CapabilityFinding {
  return Object.freeze({
    ...finding,
    ...(finding.detail ? { detail: Object.freeze({ ...finding.detail }) } : {}),
  });
}

function freezeBlocker(blocker: RenderBlocker): RenderBlocker {
  return Object.freeze({
    ...blocker,
    ...(blocker.detail ? { detail: Object.freeze({ ...blocker.detail }) } : {}),
  });
}

function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
  const seen = new Set<string>();
  const deduped: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    deduped.push(item);
  }
  return deduped;
}

function sortedFindings(findings: readonly CapabilityFinding[]): readonly CapabilityFinding[] {
  return Object.freeze(
    dedupeById(findings.map(freezeFinding)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function sortedBlockers(blockers: readonly RenderBlocker[]): readonly RenderBlocker[] {
  return Object.freeze(
    dedupeById(blockers.map(freezeBlocker)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function blockerForFinding(finding: CapabilityFinding): RenderBlocker | undefined {
  if (finding.severity !== 'error' || !finding.route || !finding.reason) return undefined;
  return {
    ...finding,
    severity: 'error',
    route: finding.route,
    reason: finding.reason,
  };
}

function routeFitFinding(requirement: CapabilityRequirement): CapabilityFinding | undefined {
  const routeFit = requirement.routeFit;
  if (!routeFit && !requirement.blocking) return undefined;
  if (routeFit?.fit === 'supported' && !requirement.blocking) return undefined;

  const reason = routeFit?.reason ?? blockerReasonForDeterminism(requirement.determinism);
  const severity = requirement.blocking || routeFit?.fit === 'blocked' ? 'error' : 'warning';
  return {
    id: `${requirement.id}.${requirement.route}.${reason}`,
    severity,
    route: requirement.route,
    reason,
    message: routeFit?.message
      ?? `Capability requirement "${requirement.id}" is ${routeFit?.fit ?? 'blocked'} for ${requirement.route}.`,
    extensionId: requirement.sourceRef.extensionId,
    contributionId: requirement.sourceRef.contributionId,
    detail: {
      source: 'capability-requirement',
      sourceRef: requirement.sourceRef,
      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
      determinism: requirement.determinism,
      routeFit: routeFit ? { ...routeFit } : undefined,
    },
  };
}

function blockerReasonForDeterminism(determinism: DeterminismStatus): RenderBlockerReason {
  switch (determinism) {
    case 'preview-only':
    case 'live-unbaked':
    case 'process-dependent':
    case 'unknown':
      return determinism;
    case 'deterministic':
      return 'unknown';
  }
}

function collectRequirement(acc: PlanAccumulator, requirement: CapabilityRequirement): void {
  addRouteValue(acc.routeDeterminism, requirement.route, requirement.determinism);
  for (const capability of requirement.requiredCapabilities) {
    addRouteSetValue(acc.routeCapabilities, requirement.route, capability);
  }

  for (const finding of requirement.findings ?? []) {
    acc.findings.push(finding);
    const blocker = blockerForFinding(finding);
    if (blocker) acc.blockers.push(blocker);
  }

  const routeFit = routeFitFinding(requirement);
  if (!routeFit) return;
  acc.findings.push(routeFit);
  const blocker = blockerForFinding(routeFit);
  if (blocker) acc.blockers.push(blocker);
}

function shaderDescriptorKey(extensionId: string | undefined, contributionId: string | undefined): string {
  return `${extensionId ?? ''}:${contributionId ?? ''}`;
}

exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/runtime/renderability.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/runtime/exportGuard.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * Export diagnostics model: pre-render scan that collects built-in known IDs
 * from clip registries, effect type arrays, the dynamic effect registry, and
 * transition types, then compares the resolved timeline config against those
 * known IDs to produce structured {@link ExportDiagnostic} entries.
 *
 * Extension-declared known IDs (from inactive reserved contributions) are
 * collected as metadata only — no extension render dispatch is added.
 *
 * @module exportGuard
 */

import type {
  ExportDiagnostic,
  ContributionKind,
  ExtensionContribution,
} from '@reigh/editor-sdk';
import { contributionKindNotYetBridged } from '@reigh/editor-sdk';
import { BUILTIN_CLIP_TYPES } from '@/tools/video-editor/types/index.ts';
import type { ResolvedTimelineClip, ResolvedTimelineConfig, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import {
  scanTimelineLiveBindings,
  type TimelineLiveBindingRecord,
} from '@/tools/video-editor/lib/timeline-domain.ts';
import { TRUSTED_CLIP_TYPES } from '@/tools/video-editor/clip-types/registry.ts';
import {
  entranceEffectTypes,
  exitEffectTypes,
  continuousEffectTypes,
  getEffectRegistry,
} from '@/tools/video-editor/effects/index.tsx';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import { transitionTypes as builtInTransitionTypes } from '@/tools/video-editor/effects/transitions.ts';
import type {
  CapabilityFinding,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderRoute,
} from '@/tools/video-editor/runtime/renderability.ts';
import {
  shaderMissingMaterializerBlockerMessage,
  type ShaderMaterializerRequirementScope,
} from '@/tools/video-editor/runtime/renderability.ts';
import type { TransitionRegistryRecord, TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';

// ---------------------------------------------------------------------------
// Known ID collections
// ---------------------------------------------------------------------------

/**
 * Immutable snapshot of all built-in (host-owned) known IDs used during
 * export validation.
 */
export interface KnownIdCollection {
  /** All known clip type IDs (built-in + trusted sequence). */
  readonly clipTypes: ReadonlySet<string>;
  /** All known effect IDs (entrance + exit + continuous built-ins). */
  readonly effectTypes: ReadonlySet<string>;
  /** All known transition type IDs. */
  readonly transitionTypes: ReadonlySet<string>;
}

/**
 * Extension-declared known IDs collected from inactive reserved contributions.
 * These are treated as metadata only — no render dispatch is triggered.
 */
export interface InactiveKnownIds {
  /** Effect IDs declared by inactive extension contributions. */
  readonly effectIds: ReadonlySet<string>;
  /** Transition IDs declared by inactive extension contributions. */
  readonly transitionIds: ReadonlySet<string>;
  /** Clip-type IDs declared by inactive extension contributions. */
  readonly clipTypeIds: ReadonlySet<string>;
}

// ---------------------------------------------------------------------------
// Export guard result
// ---------------------------------------------------------------------------

/**
 * The result of an export guard scan over a resolved timeline config.
 */
export interface ExportGuardResult {
  /** Structured diagnostics for every unknown/unavailable ID found. */
  readonly diagnostics: readonly ExportDiagnostic[];
  /** Shared planner-compatible findings for export readiness. */
  readonly findings: readonly CapabilityFinding[];
  /** Shared planner-compatible blockers that prevent browser export. */
  readonly blockers: readonly RenderBlocker[];
  /** Clip types used in the timeline that are not in any known set. */
  readonly unknownClipTypes: readonly string[];
  /** Effect types used in the timeline that are not in any known set. */
  readonly unknownEffects: readonly string[];
  /** Transition types used in the timeline that are not in any known set. */
  readonly unknownTransitions: readonly string[];
  /** Extension-declared known IDs collected as inactive metadata. */
  readonly inactiveExtensionIds: InactiveKnownIds;
  /** Whether any blocking error diagnostics were emitted. */
  readonly hasBlockingErrors: boolean;
}

// ---------------------------------------------------------------------------
// Built-in ID collection
// ---------------------------------------------------------------------------

/**
 * Collect every built-in known ID from the host-owned registries:
 * - `BUILTIN_CLIP_TYPES` (media, hold, text, effect-layer)
 * - `TRUSTED_CLIP_TYPES` (image-jump, title-card, section-hook, etc.)
 * - `entranceEffectTypes` / `exitEffectTypes` / `continuousEffectTypes`
 * - The current dynamic effect registry's `listAll()` set
 * - `transitionTypes` from `effects/transitions.ts`
 */
export function collectBuiltInKnownIds(): KnownIdCollection {
  // ---- clip types -----------------------------------------------------------
  const clipTypes = new Set<string>([
    ...BUILTIN_CLIP_TYPES,
    ...TRUSTED_CLIP_TYPES,
  ]);

  // ---- effect types ---------------------------------------------------------
  const effectTypes = new Set<string>([
    ...entranceEffectTypes,
    ...exitEffectTypes,
    ...continuousEffectTypes,
  ]);

  // Dynamic effect registry — merge any dynamically registered effects
  try {
    const registry = getEffectRegistry();
    for (const id of registry.listAll()) {
      effectTypes.add(id);
    }
  } catch {
    // Effect registry not yet initialised — built-in set is sufficient
  }

  // ---- transition types -----------------------------------------------------
  const transitionTypes = new Set(builtInTransitionTypes);

  return Object.freeze({
    clipTypes: Object.freeze(clipTypes),
    effectTypes: Object.freeze(effectTypes),
    transitionTypes: Object.freeze(transitionTypes),
  });
}

// ---------------------------------------------------------------------------
// Extension-declared known IDs (inactive metadata only)
// ---------------------------------------------------------------------------

/**
 * Collect extension-declared known IDs from contributions whose kind should
 * remain visible as inactive metadata to the export guard.
 *
 * The IDs are returned as metadata only — no extension render dispatch is
 * triggered.  Callers should pass the full list of contributions and this
 * function will filter to only those that are inactive (not-yet-bridged).
 *
 * @param contributions - All extension contributions (from active extensions).
 */
export function collectExtensionDeclaredIds(
  contributions: readonly ExtensionContribution[],
): InactiveKnownIds {
  const effectIds = new Set<string>();
  const transitionIds = new Set<string>();
  const clipTypeIds = new Set<string>();

  for (const contrib of contributions) {
    // Clip type declarations still act as inactive export metadata even though
    // clipType is now bridged. Other bridged render kinds are skipped.
    if (contrib.kind === 'clipType') {
      if (contrib.clipTypeId) {
        clipTypeIds.add(contrib.clipTypeId);
      }
      continue;
    }

    const notBridged = contributionKindNotYetBridged(contrib.kind);
    if (notBridged === null) continue; // Already bridged — skip

    switch (contrib.kind) {
      case 'effect':
        if (contrib.effectId) {
          effectIds.add(contrib.effectId);
        }
        break;
      case 'transition':
        if (contrib.transitionId) {
          transitionIds.add(contrib.transitionId);
        }
        break;
    }
  }

  return Object.freeze({
    effectIds: Object.freeze(effectIds),
    transitionIds: Object.freeze(transitionIds),
    clipTypeIds: Object.freeze(clipTypeIds),
  });
}

// ---------------------------------------------------------------------------
// Timeline scan
// ---------------------------------------------------------------------------

/**
 * The all-known union used during export validation.  Built-in IDs are
 * authoritative; extension-declared IDs are collected but NOT treated as
 * "known" for the purpose of render dispatch — they are surfaced as metadata
 * only so the host can decide whether to warn or block.
 */
interface AllKnownIds {
  clipTypes: ReadonlySet<string>;
  effectTypes: ReadonlySet<string>;
  transitionTypes: ReadonlySet<string>;
  effectRegistrySnapshot?: EffectRegistrySnapshot;
  transitionRegistrySnapshot?: TransitionRegistrySnapshot;
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot;
  /** Extension-declared IDs (metadata only, not used for dispatch). */
  extensionEffectIds: ReadonlySet<string>;
  extensionTransitionIds: ReadonlySet<string>;
  extensionClipTypeIds: ReadonlySet<string>;
}

function buildAllKnown(
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
  effectRegistrySnapshot?: EffectRegistrySnapshot,
  transitionRegistrySnapshot?: TransitionRegistrySnapshot,
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot,
): AllKnownIds {
  return {
    clipTypes: builtIn.clipTypes,
    effectTypes: builtIn.effectTypes,
    transitionTypes: builtIn.transitionTypes,
    ...(effectRegistrySnapshot ? { effectRegistrySnapshot } : {}),
    ...(transitionRegistrySnapshot ? { transitionRegistrySnapshot } : {}),
    ...(clipTypeRegistrySnapshot ? { clipTypeRegistrySnapshot } : {}),
    extensionEffectIds: extIds.effectIds,
    extensionTransitionIds: extIds.transitionIds,
    extensionClipTypeIds: extIds.clipTypeIds,
  };
}

/**
 * Scan a resolved timeline config against built-in known IDs and collect
 * structured {@link ExportDiagnostic} entries for every unknown clip type,
 * effect, or transition.
 *
 * Extension-declared IDs are included as inactive metadata in the result but
 * do **not** gate render dispatch — the host receives them so it can surface

 succeeded in 0ms:
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

export type ShaderMaterializerRequirementScope = 'clip' | 'postprocess';

export function describeShaderMaterializerRequirementScope(
  scope: ShaderMaterializerRequirementScope,
  ownerId?: string,
): string {
  if (scope === 'clip') {
    return ownerId ? `clip "${ownerId}"` : 'clip scope';
  }
  return 'timeline postprocess';
}

export function shaderMissingMaterializerBlockerMessage(
  shaderId: string,
  scope: ShaderMaterializerRequirementScope,
  ownerId?: string,
): string {
  return `Shader "${shaderId}" cannot export because no shader materializer produced RenderMaterial for ${
    describeShaderMaterializerRequirementScope(scope, ownerId)
  }.`;
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

exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/lib/renderRouter.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
// Sprint 8 (SD-027 + SD-034): render-button routing.
//
// Decides whether the user's "Render" click should:
//   * stay in the existing client-side WebCodecs path (`useClientRender`),
//     which handles pure-media + Reigh-native clipTypes ("text",
//     "effect-layer", "media", "hold").
//   * delegate to the new orchestrator `banodoco_render_timeline` task,
//     which the banodoco-worker pool services with Node + Chromium +
//     Remotion + the @banodoco/timeline-theme-* packages.
//
// Decision rule (per sprint brief):
//   * If ANY clip's clipType is in THEME_PACKAGE_REGISTRY → orchestrator.
//   * Mixed timelines (themed + media) → orchestrator (option (a)
//     in the architecture doc; uniform composition end-to-end inside
//     the worker, no cross-task ffmpeg-join).
//   * Pure-Reigh-native timelines → client-side render (untouched).
//
// The router is shape-driven — it inspects the resolved TimelineConfig
// and returns a tagged decision. The caller (UI hook) translates that
// decision into either a `useClientRender` invocation or an
// `enqueueBanodocoRenderTimeline` POST.
//
// We intentionally do NOT inspect `timeline.theme` — a timeline can
// declare a theme but only contain pure-media clips, and the existing
// client renderer can still handle that. The trigger is the clipType
// dispatch, not theme presence.

import type { TimelineRenderRequest } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import { getRegisteredClipTypeDescriptor } from '@/tools/video-editor/clip-types/runtime.ts';
import {
  getGeneratedRemotionModuleStatus,
  type GeneratedRemotionModuleBlockReason,
  type GeneratedLaneClipShape,
} from '@/tools/video-editor/lib/generated-lanes.ts';
import { materializeSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
import {
  planRender,
  type RenderPlannerResult,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  CapabilityRequirement,
  RenderBlockerReason,
} from '@reigh/editor-sdk';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';

/** Minimal clip shape we need from the resolved timeline. */
export interface RouterClipShape extends GeneratedLaneClipShape {
  clipType?: string;
}

/** Minimal timeline shape we need from the resolved config. */
export interface RouterTimelineShape {
  clips?: ReadonlyArray<RouterClipShape> | null;
}

/**
 * Minimal contributed clip record the router needs to check dynamic
 * capability declarations. Consumers pass a subset of
 * ClipTypeRegistryRecord or an equivalent shape extracted from the
 * provider-scoped registry snapshot.
 */
export interface ContributedClipRecord {
  readonly clipTypeId: string;
  readonly renderability: ContributionRenderability;
}

/**
 * Sprint 8 (final): provider-id taxonomy used by the render pipeline +
 * `renderPipeline.ts`. Each route maps 1:1 onto a provider id so middleware
 * can dispatch on the route without a separate lookup table.
 *
 *   * `browser-remotion`  — client-side WebCodecs / Remotion path
 *                          (`useClientRender`, native + media clips).
 *   * `worker-banodoco`   — orchestrator `banodoco_render_timeline`
 *                          (themed + generated-remotion-module clips).
 *   * `preview-only`      — generated remotion_module clips with invalid /
 *                          missing artifact metadata. Cannot be rendered;
 *                          surfaces a hard "render blocked" message.
 *   * `external`          — reserved for future external render providers.
 *                          Currently unreachable from `decideRenderRoute`.
 */
export type RenderRoute =
  | 'browser-remotion'
  | 'worker-banodoco'
  | 'preview-only'
  | 'external';

export type RenderProviderId = RenderRoute;

export const RENDER_PROVIDER_REGISTRY: Readonly<Record<RenderRoute, RenderProviderId>> = {
  'browser-remotion': 'browser-remotion',
  'worker-banodoco': 'worker-banodoco',
  'preview-only': 'preview-only',
  external: 'external',
};

export interface RenderRouteDecision {
  route: RenderRoute;
  /** True iff at least one clip is themed (i.e. uses the registry). */
  hasThemedClip: boolean;
  /** True iff at least one clip is pure-media / Reigh-native. */
  hasMediaClip: boolean;
  /** True iff at least one clip is a contributed extension clip. */
  hasContributedClip: boolean;
  reason:
    | 'no_clips'
    | 'pure_native_clips'
    | 'themed_only'
    | 'mixed_themed_and_media'
    | 'generated_remotion_module'
    | 'mixed_generated_module_and_other'
    | 'browser_capable_contributed'
    | 'mixed_browser_capable_contributed_and_native'
    | 'contributed_blocked_no_browser_capability'
    | 'contributed_blocked_worker_route_conflict'
    | GeneratedRemotionModuleBlockReason;
}

interface PlannerRouteDecisionContext {
  readonly plannerResult: RenderPlannerResult;
  readonly selectedPlannerRoute: 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';
}

export interface PlannerBackedRenderRouteDecision extends RenderRouteDecision {
  readonly planner: PlannerRouteDecisionContext;
}

const NATIVE_BUILTIN_CLIP_TYPES: ReadonlySet<string> = new Set([
  'media',
  'text',
  'effect-layer',
  'hold',
  'automation',
]);

const isNativeBuiltinClipType = (value: unknown): boolean => {
  // Treat undefined/null clipType as media-equivalent (pre-clipType
  // legacy clips). They route to the client renderer.
  if (typeof value !== 'string') return true;
  return NATIVE_BUILTIN_CLIP_TYPES.has(value);
};

const isCustomRenderClipType = (value: unknown): boolean => {
  if (typeof value !== 'string') {
    return false;
  }
  const descriptor = getRegisteredClipTypeDescriptor(value);
  return descriptor?.renderCapabilities.exportRoute === 'custom';
};

/**
 * Map contributed clip records by clipTypeId for O(1) lookup during the
 * routing loop.
 */
function indexContributedRecords(
  records: ReadonlyArray<ContributedClipRecord> | undefined,
): ReadonlyMap<string, ContributedClipRecord> {
  if (!records || records.length === 0) return new Map();
  const map = new Map<string, ContributedClipRecord>();
  for (const record of records) {
    if (!map.has(record.clipTypeId)) {
      map.set(record.clipTypeId, record);
    }
  }
  return map;
}

/**
 * Check whether a contributed clip record explicitly declares a supported
 * browser-export capability.
 */
function hasBrowserExportCapability(
  record: ContributedClipRecord,
): boolean {
  return record.renderability.capabilities.some(
    (c) => c.route === 'browser-export' && c.status === 'supported',
  );
}

function sourceRefForClip(clipType: string | undefined): CapabilityRequirement['sourceRef'] {
  return typeof clipType === 'string' && clipType.length > 0
    ? { source: 'registry', contributionId: clipType }
    : { source: 'built-in' };
}

function routeRequirement(
  id: string,
  route: CapabilityRequirement['route'],
  clipType: string | undefined,
  options?: {
    readonly blocking?: boolean;
    readonly reason?: RenderBlockerReason;
    readonly message?: string;
    readonly legacyReason?: RenderRouteDecision['reason'];
    readonly requiredCapabilities?: readonly string[];
  },
): CapabilityRequirement {
  const blocking = options?.blocking === true;
  return {
    id,
    sourceRef: sourceRefForClip(clipType),
    route,
    requiredCapabilities: options?.requiredCapabilities ?? [route],
    determinism: route === 'worker-export' ? 'process-dependent' : 'deterministic',
    blocking,
    routeFit: blocking
      ? {
          route,
          fit: 'blocked',
          reason: options?.reason ?? 'route-unsupported',
          message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
        }
      : {
          route,
          fit: 'supported',
        },
    findings: blocking
      ? [
          {
            id: `${id}.${route}.${options?.reason ?? 'route-unsupported'}`,
            severity: 'error',
            route,
            reason: options?.reason ?? 'route-unsupported',
            message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
            detail: {
              source: 'render-router',
              clipType,
              legacyReason: options?.legacyReason,
            },
          },
        ]
      : undefined,
  };
}

function requirementsForWorkerOnlyClip(
  clipType: string | undefined,
  id: string,
  reason: RenderRouteDecision['reason'],
): CapabilityRequirement[] {
  return [
    routeRequirement(`${id}.browser-export`, 'browser-export', clipType, {
      blocking: true,
      reason: 'route-unsupported',
      legacyReason: reason,
      message: `Clip type "${clipType ?? 'generated'}" requires worker export.`,
    }),
    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
      requiredCapabilities: ['worker-export'],
    }),
  ];
}

function requirementsForBrowserOnlyClip(
  clipType: string | undefined,
  id: string,
  reason: RenderRouteDecision['reason'],
): CapabilityRequirement[] {
  return [
    routeRequirement(`${id}.browser-export`, 'browser-export', clipType),

codex
The first pass shows two route vocabularies already: planner routes like `browser-export`/`worker-export`, and router provider routes like `browser-remotion`/`preview-only`. I’m reading the decision points now to separate true blockers from legacy routing reasons.
exec
/bin/zsh -lc "sed -n '260,620p' src/tools/video-editor/runtime/exportGuard.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
 * do **not** gate render dispatch — the host receives them so it can surface
 * appropriate warnings (e.g. "effect X is declared by an inactive extension").
 *
 * @param config - The resolved timeline config to scan (null/empty = no diagnostics).
 * @param builtIn - Built-in known IDs from {@link collectBuiltInKnownIds}.
 * @param extIds - Extension-declared known IDs from {@link collectExtensionDeclaredIds}.
 */
export function scanExportConfig(
  config: ResolvedTimelineConfig | null,
  builtIn: KnownIdCollection,
  extIds: InactiveKnownIds,
  effectRegistrySnapshot?: EffectRegistrySnapshot,
  transitionRegistrySnapshot?: TransitionRegistrySnapshot,
  clipTypeRegistrySnapshot?: ClipTypeRegistrySnapshot,
): ExportGuardResult {
  const diagnostics: ExportDiagnostic[] = [];
  const findings: CapabilityFinding[] = [];
  const blockers: RenderBlocker[] = [];
  const unknownClipTypes = new Set<string>();
  const unknownEffects = new Set<string>();
  const unknownTransitions = new Set<string>();

  if (config && config.clips.length > 0) {
    scanLiveBindingExportBlockers(config, diagnostics, findings, blockers);
    scanTimelineShaderExportBlockers(config, diagnostics, findings, blockers);

    const allKnown = buildAllKnown(builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);

    for (const clip of config.clips) {
      scanClip(clip, allKnown, diagnostics, findings, blockers, unknownClipTypes, unknownEffects, unknownTransitions);
    }
  }

  // Sort diagnostics for determinism
  diagnostics.sort((a, b) => a.code.localeCompare(b.code) || a.message.localeCompare(b.message));
  findings.sort((a, b) => a.id.localeCompare(b.id));
  blockers.sort((a, b) => a.id.localeCompare(b.id));

  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');

  return Object.freeze({
    diagnostics: Object.freeze(diagnostics),
    findings: Object.freeze(findings),
    blockers: Object.freeze(blockers),
    unknownClipTypes: Object.freeze([...unknownClipTypes].sort()),
    unknownEffects: Object.freeze([...unknownEffects].sort()),
    unknownTransitions: Object.freeze([...unknownTransitions].sort()),
    inactiveExtensionIds: extIds,
    hasBlockingErrors,
  });
}

function scanLiveBindingExportBlockers(
  config: ResolvedTimelineConfig,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  const liveScan = scanTimelineLiveBindings(config as TimelineConfig);

  for (const record of liveScan.bindings) {
    if (!record.blocksExport) {
      continue;
    }
    pushLiveBindingFindingAndBlocker(diagnostics, findings, blockers, record);
  }
}

function hasTimelineShaderMetadata(config: ResolvedTimelineConfig | null | undefined): boolean {
  if (!config) return false;
  if (isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')) return true;
  return config.clips.some((clip) => isTimelineShaderMetadata(clip.app?.shader, 'clip'));
}

export { hasTimelineShaderMetadata };

function isTimelineShaderMetadata(
  value: unknown,
  scope: ShaderMaterializerRequirementScope,
): value is {
  readonly scope: ShaderMaterializerRequirementScope;
  readonly shaderId: string;
  readonly extensionId: string;
  readonly contributionId: string;
  readonly enabled?: boolean;
} {
  return Boolean(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && (value as Record<string, unknown>).scope === scope
    && typeof (value as Record<string, unknown>).shaderId === 'string'
    && typeof (value as Record<string, unknown>).extensionId === 'string'
    && typeof (value as Record<string, unknown>).contributionId === 'string',
  );
}

function scanTimelineShaderExportBlockers(
  config: ResolvedTimelineConfig,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  for (const clip of config.clips) {
    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
    if (!shader || shader.enabled === false) continue;
    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
      shaderId: shader.shaderId,
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
      scope: 'clip',
      clipId: clip.id,
    });
  }

  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
    ? config.app.shaderPostprocess
    : undefined;
  if (postprocessShader && postprocessShader.enabled !== false) {
    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
      shaderId: postprocessShader.shaderId,
      extensionId: postprocessShader.extensionId,
      contributionId: postprocessShader.contributionId,
      scope: 'postprocess',
    });
  }
}

function pushShaderMaterializerFindingAndBlocker(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    readonly shaderId: string;
    readonly extensionId: string;
    readonly contributionId: string;
    readonly scope: ShaderMaterializerRequirementScope;
    readonly clipId?: string;
  },
): void {
  const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];

  for (const route of routes) {
    const message = shaderMissingMaterializerBlockerMessage(input.shaderId, input.scope, input.clipId);
    const id = `export.shader.${input.scope}.${input.clipId ?? 'timeline'}.${input.shaderId}.${route}.missing-materializer`;
    const detail = {
      shaderId: input.shaderId,
      shaderScope: input.scope,
      renderRoute: route,
      ...(input.clipId ? { clipId: input.clipId } : {}),
    };

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-shader',
      message,
      extensionId: input.extensionId,
      contributionId: input.contributionId,
      detail,
    });

    const finding: CapabilityFinding = {
      id,
      severity: 'error',
      route,
      reason: 'missing-material',
      message,
      ...(input.clipId ? { clipId: input.clipId } : {}),
      extensionId: input.extensionId,
      contributionId: input.contributionId,
      detail: {
        shaderId: input.shaderId,
        shaderScope: input.scope,
        source: 'timeline-shader-metadata',
      },
    };
    findings.push(finding);
    blockers.push({
      ...finding,
      severity: 'error',
      route,
      reason: 'missing-material',
    });
  }
}

function liveBindingStatusMessage(record: TimelineLiveBindingRecord): string {
  const bindingId = record.binding.bindingId;
  switch (record.status) {
    case 'active':
      return `Live binding "${bindingId}" is active and must be baked or removed before export.`;
    case 'inactive':
      return `Live binding "${bindingId}" references an inactive source and must be baked or removed before export.`;
    case 'missing':
      return `Live binding "${bindingId}" references a missing source and must be baked or removed before export.`;
    case 'disposed':
      return `Live binding "${bindingId}" references a disposed source and must be baked or removed before export.`;
    case 'orphaned':
      return `Live binding "${bindingId}" references an orphaned source and must be baked or removed before export.`;
    case 'partiallyBaked':
      return `Live binding "${bindingId}" is partially baked; unresolved ranges must be baked or removed before export.`;
    case 'malformed':
      return `Live binding metadata on clip "${record.clipId}" is malformed and blocks export until fixed or removed.`;
    case 'resolved':
      return `Live binding "${bindingId}" has deterministic replacement metadata.`;
  }
}

function pushLiveBindingFindingAndBlocker(
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  record: TimelineLiveBindingRecord,
): void {
  const message = liveBindingStatusMessage(record);
  const id = `export.liveBinding.${record.clipId}.${record.binding.bindingId}.${record.status}`;
  const detail = {
    bindingId: record.binding.bindingId,
    sourceId: record.binding.sourceId,
    sourceKind: record.binding.sourceKind,
    resolutionStatus: record.status,
    path: record.path,
    diagnostics: record.diagnostics.map((diagnostic) => ({
      code: diagnostic.code,
      message: diagnostic.message,
      severity: diagnostic.severity,
    })),
  };

  diagnostics.push({
    severity: 'error',
    code: 'export/live-binding-unresolved',
    message,
    detail: {
      clipId: record.clipId,
      ...detail,
    },
  });

  const finding: CapabilityFinding = {
    id,
    severity: 'error',
    route: 'browser-export',
    reason: 'live-unbaked',
    message,
    clipId: record.clipId,
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: 'browser-export',
    reason: 'live-unbaked',
  });
}

// ---------------------------------------------------------------------------
// Per-clip scan
// ---------------------------------------------------------------------------

function scanClip(
  clip: ResolvedTimelineClip,
  known: AllKnownIds,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  unknownClipTypes: Set<string>,
  unknownEffects: Set<string>,
  unknownTransitions: Set<string>,
): void {
  // ---- clip type -----------------------------------------------------------
  if (clip.clipType) {
    // 1) Built-in / trusted clip types — fast path, no registry scan needed.
    if (known.clipTypes.has(clip.clipType)) {
      // Known built-in — pass through to effect/transition scanning.
    }
    // 2) Check the clip-type registry snapshot for contributed clip types.
    else {
      const snapshotRecord = known.clipTypeRegistrySnapshot?.get(clip.clipType);

      if (snapshotRecord) {
        // Clip type is registered — scan its status and capabilities.
        scanClipTypeRecordRenderability(clip, clip.clipType, snapshotRecord, diagnostics, findings, blockers);
      } else {
        // Clip type is NOT in the registry snapshot — check extension-declared fallback.
        const isExtDeclared = known.extensionClipTypeIds.has(clip.clipType);

        diagnostics.push({
          severity: isExtDeclared ? 'warning' : 'error',
          code: 'export/unknown-clip-type',
          message: isExtDeclared
            ? `Clip type "${clip.clipType}" is declared by an inactive extension and may not be available at export time.`
            : `Clip type "${clip.clipType}" is not recognised. Ensure the required extension or registry is installed.`,
          detail: { clipId: clip.id, clipType: clip.clipType },
        });

        if (!isExtDeclared) {
          unknownClipTypes.add(clip.clipType);

          // Emit shared blocker vocabulary for truly unknown clip types.
          pushClipTypeFindingAndBlocker(findings, blockers, {
            id: `export.clipType.${clip.id}.${clip.clipType}.missing`,
            reason: 'missing-contribution',
            message: `Clip type "${clip.clipType}" is not recognised. Ensure the required extension or registry is installed.`,
            clipId: clip.id,
            clipType: clip.clipType,
            route: 'browser-export',
          });
        }
      }
    }
  }

  // ---- entrance effect -----------------------------------------------------
  scanEffect(clip, 'entrance', known, diagnostics, findings, blockers, unknownEffects);

  // ---- exit effect ---------------------------------------------------------
  scanEffect(clip, 'exit', known, diagnostics, findings, blockers, unknownEffects);

  // ---- continuous effect ---------------------------------------------------
  scanEffect(clip, 'continuous', known, diagnostics, findings, blockers, unknownEffects);

  // ---- transition ----------------------------------------------------------
  if (clip.transition?.type) {
    const tType = clip.transition.type;
    const snapshotRecord = known.transitionRegistrySnapshot?.get(tType);

    // Check built-in + registry
    if (!known.transitionTypes.has(tType) && !snapshotRecord) {
      const isExtDeclared = known.extensionTransitionIds.has(tType);

      diagnostics.push({
        severity: isExtDeclared ? 'warning' : 'error',
        code: 'export/unknown-transition-type',
        message: isExtDeclared
          ? `Transition "${tType}" is declared by an inactive extension and may not be available at export time.`
          : `Transition "${tType}" is not recognised. Ensure the required extension or registry is installed.`,
        detail: { clipId: clip.id, transitionType: tType },
      });

      if (!isExtDeclared) {
        unknownTransitions.add(tType);
        pushTransitionFindingAndBlocker(findings, blockers, {
          id: `export.transition.${clip.id}.${tType}.missing`,
          reason: 'missing-contribution',
          message: `Transition "${tType}" is not recognised. Ensure the required extension or registry is installed.`,
          clipId: clip.id,
          transitionType: tType,
          route: 'browser-export',
        });
      }
      return;
    }

    // Registry-based scanning
    if (snapshotRecord) {
      scanTransitionRecordRenderability(clip, tType, snapshotRecord, diagnostics, findings, blockers);
    }
  }
}

exec
/bin/zsh -lc "sed -n '260,620p' src/tools/video-editor/runtime/renderPlanner.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
}

function createShaderDescriptorMap(
  descriptors: readonly VideoEditorShaderDescriptor[],
): ReadonlyMap<string, VideoEditorShaderDescriptor> {
  return new Map(descriptors.map((descriptor) => [
    shaderDescriptorKey(descriptor.extensionId, descriptor.id),
    descriptor,
  ]));
}

function createProcessDescriptorMap(
  descriptors: readonly VideoEditorProcessDescriptor[],
): ReadonlyMap<string, VideoEditorProcessDescriptor> {
  return new Map(descriptors.map((descriptor) => [descriptor.processId, descriptor]));
}

function isShaderMaterializerRequirement(requirement: CapabilityRequirement): boolean {
  return requirement.sourceRef.source === 'extension'
    && requirement.requiredCapabilities.includes('shader-materializer')
    && requirement.requiredCapabilities.includes('render-material');
}

function processOperationSupportsMaterializerRoute(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
  route: RenderRoute,
): boolean {
  if (!process) return false;
  return process.operations.some((operation) => {
    if (operationId && operation.id !== operationId) return false;
    if (!operation.routes?.includes(route)) return false;
    return !operation.outputKinds || operation.outputKinds.includes('material');
  });
}

function shaderMaterializerSupportsRoute(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  processById: ReadonlyMap<string, VideoEditorProcessDescriptor>,
): boolean {
  const materializer = descriptor.materializer;
  if (!materializer) return false;
  if (materializer.routes?.includes(requirement.route)) return true;
  if (!materializer.processId) return false;
  return processOperationSupportsMaterializerRoute(
    processById.get(materializer.processId),
    materializer.operationId,
    requirement.route,
  );
}

function shaderMaterializationMessage(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
): string {
  if (descriptor.materializer?.unavailableMessage) return descriptor.materializer.unavailableMessage;
  if (descriptor.materializer?.processId) {
    return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
      `run process "${descriptor.materializer.processId}" to produce RenderMaterial.`;
  }
  return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
    'materialize it to produce RenderMaterial.';
}

function shaderMaterializationAction(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  message: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'resolve-blocker',
    label: `Materialize shader ${descriptor.shaderId}`,
    route: requirement.route,
    processId: descriptor.materializer?.processId,
    operationId: descriptor.materializer?.operationId,
    message,
  };
}

function shaderMaterializerFinding(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  action: VideoEditorPlannerNextActionDescriptor,
  processStatus: ProcessStatus | undefined,
): CapabilityFinding {
  return {
    id: `${requirement.id}.${requirement.route}.shader-materializer.discovered`,
    severity: 'info',
    route: requirement.route,
    message: `Shader materializer route discovered for "${descriptor.shaderId}" on ${requirement.route}.`,
    extensionId: descriptor.extensionId,
    contributionId: descriptor.id,
    detail: {
      source: 'shader-materializer',
      shaderId: descriptor.shaderId,
      processId: descriptor.materializer?.processId,
      operationId: descriptor.materializer?.operationId,
      processState: processStatus?.state ?? 'unknown',
      materializationState: processStatus?.state === 'busy' ? 'in-progress' : 'pending',
      nextAction: action,
    },
  };
}

function collectShaderMaterializerRequirement(
  acc: PlanAccumulator,
  requirement: CapabilityRequirement,
  descriptor: VideoEditorShaderDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
): void {
  const processStatus = descriptor.materializer?.processId
    ? processStatusById.get(descriptor.materializer.processId)
    : undefined;
  const message = shaderMaterializationMessage(descriptor, requirement);
  const action = shaderMaterializationAction(descriptor, requirement, message);

  collectRequirement(acc, {
    ...requirement,
    determinism: 'process-dependent',
    blocking: true,
    routeFit: {
      route: requirement.route,
      fit: 'supported',
      reason: 'process-dependent',
      message,
    },
    findings: [
      ...(requirement.findings ?? []),
      shaderMaterializerFinding(descriptor, requirement, action, processStatus),
    ],
  });
  acc.nextActions.push(action);
}

function shaderCompositionKey(shader: TimelineShaderSummary): string | undefined {
  if (shader.enabled === false) return undefined;
  if (shader.scope === 'clip') return `clip:${shader.clipId ?? ''}`;
  return 'postprocess';
}

function shaderCompositionScopeMessage(
  existing: TimelineShaderSummary,
  incoming: TimelineShaderSummary,
): string {
  if (incoming.scope === 'clip') {
    const target = incoming.clipId ? `clip "${incoming.clipId}"` : 'the clip scope';
    return `Cannot add shader "${incoming.shaderId}" to ${target} because shader "${existing.shaderId}" is already assigned. ` +
      'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
  }

  return `Cannot add postprocess shader "${incoming.shaderId}" because postprocess shader "${existing.shaderId}" is already assigned. ` +
    'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
}

function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
}

function diagnoseSnapshotShaderComposition(
  snapshot: TimelineSnapshot | null | undefined,
): { snapshot: TimelineSnapshot | null | undefined; findings: CapabilityFinding[] } {
  if (!snapshot?.shaders || snapshot.shaders.length === 0) {
    return { snapshot, findings: [] };
  }

  const firstByScope = new Map<string, TimelineShaderSummary>();
  const findings: CapabilityFinding[] = [];
  const filteredShaders: TimelineShaderSummary[] = [];

  for (const shader of snapshot.shaders) {
    const scopeKey = shaderCompositionKey(shader);
    if (!scopeKey) {
      filteredShaders.push(shader);
      continue;
    }

    const existing = firstByScope.get(scopeKey);
    if (!existing) {
      firstByScope.set(scopeKey, shader);
      filteredShaders.push(shader);
      continue;
    }

    const message = shaderCompositionScopeMessage(existing, shader);
    for (const route of ['browser-export', 'worker-export'] as const satisfies readonly RenderRoute[]) {
      findings.push({
        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
        severity: 'error',
        route,
        reason: 'unknown',
        message,
        extensionId: shader.extensionId,
        contributionId: shader.contributionId,
        detail: {
          source: 'shader-composition-limit',
          scope: shader.scope,
          clipId: shader.clipId,
          existingShaderId: existing.shaderId,
          incomingShaderId: shader.shaderId,
        },
      });
    }
  }

  if (findings.length === 0) {
    return { snapshot, findings };
  }

  return {
    snapshot: {
      ...snapshot,
      shaders: filteredShaders.length > 0 ? filteredShaders : undefined,
    },
    findings,
  };
}

function sortedRoutes(routes: readonly RenderRoute[]): readonly RenderRoute[] {
  const requested = new Set(routes);
  return Object.freeze(RENDER_ROUTES.filter((route) => requested.has(route)));
}

function requestedRoutes(request: RenderPlannerRequest | undefined): readonly RenderRoute[] {
  if (!request) return Object.freeze([]);
  if (request.routes && request.routes.length > 0) return sortedRoutes(request.routes);
  if (request.route) return Object.freeze([request.route]);
  return Object.freeze([]);
}

function collectRequestCapabilities(acc: PlanAccumulator, request: RenderPlannerRequest | undefined): void {
  if (!request?.requiredCapabilities || request.requiredCapabilities.length === 0) return;
  const routes = requestedRoutes(request);
  const targetRoutes = routes.length > 0 ? routes : RENDER_ROUTES;

  for (const route of targetRoutes) {
    for (const capability of request.requiredCapabilities) {
      addRouteSetValue(acc.routeCapabilities, route, capability);
    }
  }
}

function descriptorBlockerToFinding(
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): CapabilityFinding {
  return {
    id: blocker.id,
    severity: 'error',
    route: blocker.route ?? fallbackRoute,
    reason: blocker.reason,
    message: blocker.message,
    extensionId: blocker.extensionId,
    contributionId: blocker.contributionId,
    detail: {
      source,
      nextAction: blocker.nextAction,
    },
  };
}

function collectDescriptorBlocker(
  acc: PlanAccumulator,
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): void {
  const finding = descriptorBlockerToFinding(blocker, fallbackRoute, source);
  acc.findings.push(finding);
  const routeBlocker = blockerForFinding(finding);
  if (routeBlocker) acc.blockers.push(routeBlocker);
  if (blocker.nextAction) acc.nextActions.push(blocker.nextAction);
}

function processRequirementBlocker(
  outputFormat: VideoEditorOutputFormatDescriptor,
  route: RenderRoute,
  requirement: VideoEditorProcessRequirementDescriptor,
  status?: ProcessStatus,
): RenderBlocker {
  const operationSuffix = requirement.operationId ? `.${requirement.operationId}` : '';
  return {
    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${requirement.processId}${operationSuffix}.process-dependent`,
    severity: 'error',
    route,
    reason: 'process-dependent',
    message: processStatusMessage(outputFormat.label, requirement.processId, route, status),
    extensionId: outputFormat.extensionId,
    contributionId: outputFormat.id,
    detail: {
      source: 'output-format',
      outputFormatId: outputFormat.id,
      outputLabel: outputFormat.label,
      processId: requirement.processId,
      operationId: requirement.operationId,
      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
      processState: status?.state ?? 'unknown',
    },
  };
}

function routeRequirementBlocker(
  outputFormat: VideoEditorOutputFormatDescriptor,
  routeRequirement: VideoEditorRouteRequirementDescriptor,
  route: RenderRoute,
  status?: ProcessStatus,
): RenderBlocker | undefined {
  if (!routeRequirement.processId && routeRequirement.requiredCapabilities.length === 0) return undefined;
  if (!routeRequirement.processId) return undefined;

  return {
    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${routeRequirement.processId}.route-process-dependent`,
    severity: 'error',
    route,
    reason: 'process-dependent',
    message: routeRequirement.unavailableMessage
      ?? processStatusMessage(outputFormat.label, routeRequirement.processId, route, status),
    extensionId: outputFormat.extensionId,
    contributionId: outputFormat.id,
    detail: {
      source: 'output-format',
      outputFormatId: outputFormat.id,
      outputLabel: outputFormat.label,
      processId: routeRequirement.processId,
      operationId: routeRequirement.operationId,
      requiredCapabilities: [...routeRequirement.requiredCapabilities].sort(),
      determinism: routeRequirement.determinism,
      processState: status?.state ?? 'unknown',
    },
  };
}

function processStatusMessage(
  outputLabel: string,
  processId: string,
  route: RenderRoute,
  status?: ProcessStatus,
): string {
  if (!status) return `Output format "${outputLabel}" requires process "${processId}" before ${route} can run.`;
  if (status.message) return status.message;
  return `Process "${processId}" is ${status.state} for ${route}.`;
}

function processStatusBlocks(status: ProcessStatus | undefined): boolean {
  if (!status) return true;
  return status.state !== 'ready' && status.state !== 'degraded';
}

function processStatusDegraded(status: ProcessStatus | undefined): boolean {
  return status?.state === 'degraded';
}

function processStatusWarning(
  blocker: RenderBlocker,
  status: ProcessStatus,
): CapabilityFinding {
  return {
    ...blocker,
    id: `${blocker.id}.degraded`,
    severity: 'warning',

exec
/bin/zsh -lc "sed -n '260,620p' src/tools/video-editor/lib/renderRouter.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    routeRequirement(`${id}.browser-export`, 'browser-export', clipType),
    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
      blocking: true,
      reason: 'route-unsupported',
      legacyReason: reason,
      message: `Clip type "${clipType ?? 'contributed'}" cannot run on worker export.`,
    }),
  ];
}

function requirementsForBlockedClip(
  clipType: string | undefined,
  id: string,
  reason: RenderRouteDecision['reason'],
  blockerReason: RenderBlockerReason,
): CapabilityRequirement[] {
  return [
    routeRequirement(`${id}.browser-export`, 'browser-export', clipType, {
      blocking: true,
      reason: blockerReason,
      legacyReason: reason,
      message: `Clip type "${clipType ?? 'generated'}" cannot be rendered until ${reason} is resolved.`,
    }),
    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
      blocking: true,
      reason: blockerReason,
      legacyReason: reason,
      message: `Clip type "${clipType ?? 'generated'}" cannot be rendered until ${reason} is resolved.`,
    }),
  ];
}

function selectPlannerRoute(result: RenderPlannerResult): PlannerRouteDecisionContext {
  if (result.canBrowserExport) {
    return { plannerResult: result, selectedPlannerRoute: 'browser-export' };
  }
  if (result.canWorkerExport) {
    return { plannerResult: result, selectedPlannerRoute: 'worker-export' };
  }
  return { plannerResult: result, selectedPlannerRoute: 'preview' };
}

/** Pure-decision routing — call this from a hook or test. */
export function decideRenderRoute(
  timeline: RouterTimelineShape | null | undefined,
  contributedClipRecords?: ReadonlyArray<ContributedClipRecord>,
): PlannerBackedRenderRouteDecision {
  const clips = (timeline?.clips ?? []) as ReadonlyArray<RouterClipShape>;
  const contributedIndex = indexContributedRecords(contributedClipRecords);

  if (clips.length === 0) {
    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: false,
      reason: 'no_clips',
      planner: selectPlannerRoute(planRender({ requirements: [] })),
    };
  }

  const requirements: CapabilityRequirement[] = [];
  let hasThemedClip = false;
  let hasMediaClip = false;
  let hasContributedClip = false;
  let hasBrowserCapableContributedClip = false;
  let hasNativeOrMediaClip = false;
  let hasGeneratedModuleClip = false;
  let hasOtherClip = false;
  let blockedReason: RenderRouteDecision['reason'] | null = null;
  let blockedHasThemedClip = false;
  let blockedHasMediaClip = false;
  let blockedHasContributedClip = false;

  clips.forEach((clip, index) => {
    if (blockedReason) return;
    const requirementId = `router.clip.${index}.${clip.clipType ?? 'legacy'}`;
    const moduleStatus = getGeneratedRemotionModuleStatus(clip);
    if (moduleStatus.kind === 'blocked_module') {
      requirements.push(...requirementsForBlockedClip(
        clip.clipType,
        requirementId,
        moduleStatus.reason,
        moduleStatus.reason === 'remotion_module_missing_artifact'
          ? 'missing-material'
          : 'materialization-failed',
      ));
      blockedReason = moduleStatus.reason;
      return;
    }
    if (moduleStatus.kind === 'valid_module') {
      hasGeneratedModuleClip = true;
      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'generated_remotion_module'));
      return;
    }

    hasOtherClip = true;

    // M9 T11: Check contributed clip records first. Contributed clip
    // code is only allowed in browser-remotion when it explicitly
    // declares browser-export capability. Worker routes are always
    // blocked for contributed code (SD1).
    const clipType = clip?.clipType;
    if (typeof clipType === 'string') {
      const contributedRecord = contributedIndex.get(clipType);
      if (contributedRecord) {
        hasContributedClip = true;
        if (hasBrowserExportCapability(contributedRecord)) {
          hasBrowserCapableContributedClip = true;
          requirements.push(...requirementsForBrowserOnlyClip(clipType, requirementId, 'browser_capable_contributed'));
        } else {
          // Contributed clip without browser-export capability is
          // immediately blocked — worker routes are out of scope
          // for contributed code and no other route is available.
          requirements.push(...requirementsForBlockedClip(
            clipType,
            requirementId,
            'contributed_blocked_no_browser_capability',
            'route-unsupported',
          ));
          blockedReason = 'contributed_blocked_no_browser_capability';
          blockedHasContributedClip = true;
          return;
        }
        return;
      }
    }

    // Non-contributed clips follow existing routing.
    if (isCustomRenderClipType(clip?.clipType)) {
      hasThemedClip = true;
      // A themed clip mixed with browser-capable contributed clips
      // creates a conflict: themed clips need worker, contributed
      // clips can't go to worker.
      if (hasBrowserCapableContributedClip) {
        requirements.push(...requirementsForBlockedClip(
          clip.clipType,
          requirementId,
          'contributed_blocked_worker_route_conflict',
          'route-unsupported',
        ));
        blockedReason = 'contributed_blocked_worker_route_conflict';
        blockedHasThemedClip = true;
        blockedHasMediaClip = true;
        blockedHasContributedClip = true;
        return;
      }
      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'themed_only'));
    } else if (isNativeBuiltinClipType(clip?.clipType)) {
      hasMediaClip = true;
      hasNativeOrMediaClip = true;
      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
    } else {
      // Unknown clipType (theme package not installed, typo). Treat as
      // media so the existing render path's loud-placeholder fallback
      // surfaces — orchestrator wouldn't be able to render it either
      // without the theme package, and the sprint scopes us to
      // registered themes.
      hasMediaClip = true;
      hasNativeOrMediaClip = true;
      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
    }
  });

  const planner = selectPlannerRoute(planRender({ requirements }));

  if (blockedReason) {
    return {
      route: 'preview-only',
      hasThemedClip: blockedHasThemedClip,
      hasMediaClip: blockedHasMediaClip,
      hasContributedClip: blockedHasContributedClip,
      reason: blockedReason,
      planner,
    };
  }

  // Generated Remotion module clips always go to the worker pool if
  // they survived the blocked_module short-circuit above. Mixed
  // generated + browser-capable contributed clips create an
  // unresolvable conflict because contributed code cannot execute in
  // the worker.
  if (hasGeneratedModuleClip) {
    if (hasBrowserCapableContributedClip) {
      const conflictPlanner = selectPlannerRoute(planRender({
        requirements: [
          ...requirements,
          ...requirementsForBlockedClip(
            'generated-remotion-module',
            'router.generated.contributed-conflict',
            'contributed_blocked_worker_route_conflict',
            'route-unsupported',
          ),
        ],
      }));
      return {
        route: 'preview-only',
        hasThemedClip,
        hasMediaClip,
        hasContributedClip: true,
        reason: 'contributed_blocked_worker_route_conflict',
        planner: conflictPlanner,
      };
    }
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
      planner,
    };
  }

  // Browser-capable contributed clips mixed with themed clips already
  // short-circuit above (contributed_blocked_worker_route_conflict).
  // Here we handle the remaining combinations.

  if (hasBrowserCapableContributedClip) {
    if (hasThemedClip) {
      // Should not reach here (caught above), but defensive.
      return {
        route: 'preview-only',
        hasThemedClip: true,
        hasMediaClip: true,
        hasContributedClip: true,
        reason: 'contributed_blocked_worker_route_conflict',
        planner,
      };
    }
    if (hasNativeOrMediaClip) {
      // Mixed browser-capable contributed + native → browser-remotion
      // handles both.
      return {
        route: 'browser-remotion',
        hasThemedClip: false,
        hasMediaClip: true,
        hasContributedClip: true,
        reason: 'mixed_browser_capable_contributed_and_native',
        planner,
      };
    }
    // Pure browser-capable contributed clips
    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: true,
      reason: 'browser_capable_contributed',
      planner,
    };
  }

  if (hasThemedClip && hasMediaClip) {
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: 'mixed_themed_and_media',
      planner,
    };
  }
  if (hasThemedClip) {
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: 'themed_only',
      planner,
    };
  }
  return {
    route: 'browser-remotion',
    hasThemedClip,
    hasMediaClip,
    hasContributedClip: false,
    reason: 'pure_native_clips',
    planner,
  };
}

// ---------------------------------------------------------------------------
// Orchestrator dispatch (banodoco_render_timeline)
// ---------------------------------------------------------------------------

export interface BanodocoRenderTimelinePayload {
  timeline_id: string;
  timeline: unknown;
  assets: unknown;
  theme_id: string;
  output_filename: string;
  user_jwt: string;
  project_id: string;
  correlation_id: string;
}

export interface BuildRenderPayloadInput {
  /**
   * The TimelineRenderRequest the UI/hook composed for this render.
   * `renderRuntime.projectId` and `assetRegistry` are read from here,
   * keeping caller call-sites aligned with the rest of the pipeline.
   */
  request: Pick<TimelineRenderRequest, 'timelineId' | 'assetRegistry' | 'resolvedConfig' | 'renderRuntime'> & {
    outputFilename?: string;
  };
  userJwt: string;
  /** Tests inject a deterministic UUID; production uses crypto.randomUUID. */
  correlationId?: string;
}

const FALLBACK_THEME_ID = '2rp';

function defaultThemeId(config: { theme?: string } | null | undefined): string {
  const value = config?.theme;
  return typeof value === 'string' && value.trim() ? value : FALLBACK_THEME_ID;
}

function defaultOutputFilename(timelineId: string): string {
  // Suggested filename — the worker may suffix with task_id.
  return `timeline-${timelineId}.mp4`;
}

function newCorrelationId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  // Defensive non-prod fallback (e.g. test envs without the crypto API);
  // the sprint's prod path has crypto everywhere.
  return `corr-${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
}

export function buildRenderTimelinePayload(
  input: BuildRenderPayloadInput,
): { payload?: BanodocoRenderTimelinePayload; error?: string } {
  const { request } = input;
  if (!request?.timelineId) return { error: 'timelineId is required' };
  if (!request?.renderRuntime?.projectId) return { error: 'projectId is required' };
  if (!input.userJwt) return { error: 'user JWT is required (SD-022)' };
  if (!request.resolvedConfig) return { error: 'resolved timeline config is required' };

  return {
    payload: {
      timeline_id: request.timelineId,
      timeline: materializeSequenceConfig(request.resolvedConfig as Parameters<typeof materializeSequenceConfig>[0]),
      assets: request.assetRegistry ?? { assets: {} },
      theme_id: defaultThemeId(request.resolvedConfig),
      output_filename: request.outputFilename ?? defaultOutputFilename(request.timelineId),
      user_jwt: input.userJwt,
      project_id: request.renderRuntime.projectId,
      correlation_id: input.correlationId ?? newCorrelationId(),
    },
  };
}

export interface EnqueueRenderResult {
  status: 'queued' | 'error';
  task_id?: string;
  correlation_id?: string;
  message: string;

exec
/bin/zsh -lc "rg -n \"hasBlockingErrors|canBrowserExport|canWorkerExport|blockers|ExportGuard|planRender|decideRenderRoute|preview-only|contributed_blocked|unsupported|unknown\" src/tools/video-editor -g '*.ts' -g '*.tsx' docs/video-editor docs/extensions examples 2>/dev/null" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
examples/embed-demo/stubs/timeline-composition/registry.generated.ts:2:  component: unknown;
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx:87:  function loadSavedValues(): Record<string, unknown> {
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx:88:    const merged: Record<string, unknown> = {};
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx:97:  const [savedValues, setSavedValues] = useState<Record<string, unknown>>(
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx:100:  const [editValues, setEditValues] = useState<Record<string, unknown>>(
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx:123:  const handleChange = useCallback((name: string, value: unknown) => {
src/tools/video-editor/components/SidecarPreview.tsx:20:function safeJson(raw: string): unknown {
src/tools/video-editor/components/EffectCreatorPanel.test.tsx:92:  getDefaultValues: (schema: Array<{ name: string; default?: unknown }>) =>
src/tools/video-editor/components/EffectCreatorPanel.test.tsx:93:    schema.reduce<Record<string, unknown>>((defaults, parameter) => {
src/tools/video-editor/hooks/useAddVariantAsGeneration.test.tsx:21:    toast: { error: (...args: unknown[]) => mocks.toastError(...args) },
src/tools/video-editor/hooks/useAddVariantAsGeneration.test.tsx:54:  loadPrimaryVariantForGeneration: (...args: unknown[]) => mocks.loadPrimaryVariantForGeneration(...args),
src/tools/video-editor/hooks/useAddVariantAsGeneration.test.tsx:90:  it('does not register an asset or insert a clip when variant promotion is unsupported', async () => {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:27:    const entries = Object.entries(value as Record<string, unknown>).map(([key, entry]) => [
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:44:  detail?: Record<string, unknown>,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:75:  readonly uniformValues: Map<string, unknown>;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:76:  readonly textureUploads: unknown[];
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:108:  } as unknown as MockCanvas;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:124:    uniformValues: new Map<string, unknown>(),
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:189:      source: unknown,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:236:  return gl as unknown as WebGLRenderingContext & { readonly __state: MockWebGLState };
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:265:    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:320:    const staticSource = { src: 'static.png' } as unknown as TexImageSource;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:321:    const liveSource = { src: 'live.png' } as unknown as TexImageSource;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:365:  it('reports unsupported texture source kinds and skips rendering', () => {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:384:        code: 'shader/texture-unsupported',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:440:    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:464:    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:484:    expect(surface.status).toBe('unsupported');
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:499:  it('returns unsupported status when no canvas can be created', () => {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:506:    expect(surface.status).toBe('unsupported');
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:18:export type WebGLShaderPreviewSurfaceStatus = 'ready' | 'failed' | 'unsupported' | 'disposed';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:39:  readonly uniformValues?: Record<string, unknown>;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:41:  readonly textureValues?: Record<string, unknown>;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:71:  readonly sourceKind: unknown;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:101:  detail: Record<string, unknown> = {},
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:136:function defaultUniformValue(uniform: ShaderUniformDefinition, frame: WebGLShaderPreviewFrame): unknown {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:142:function toFiniteNumber(value: unknown): number | undefined {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:146:function toFiniteVector(value: unknown, size: number): readonly number[] | undefined {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:154:function enumIndexFor(uniform: ShaderUniformDefinition, value: unknown): number | undefined {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:160:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:164:function isShaderTextureRef(value: unknown): value is ShaderTextureRef {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:168:function isSupportedTextureSourceKind(value: unknown): value is ShaderTextureSourceKind {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:201:  value: unknown,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:261:  #uniformValues: Record<string, unknown>;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:263:  #textureValues: Record<string, unknown>;
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:309:    this.#status = 'unsupported';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:332:  setUniformValues(values: Record<string, unknown>): void {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:337:  updateUniformValues(values: Record<string, unknown>): void {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:342:  setTextureValues(values: Record<string, unknown>): void {
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:431:      this.#status = 'unsupported';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:436:          'unsupported',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:632:          'shader/texture-unsupported',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:633:          `Shader texture "${binding.name}" uses unsupported source kind "${String(binding.sourceKind)}".`,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:665:      diagnostic.code !== 'shader/texture-unsupported'
src/tools/video-editor/adapters/reigh/generationLookup.ts:5:function toRecord(value: unknown): Record<string, unknown> {
src/tools/video-editor/adapters/reigh/generationLookup.ts:7:    return value as Record<string, unknown>;
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:10:  input: Record<string, unknown>;
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:22:  createWebGLShaderPreviewSurface: vi.fn((input: Record<string, unknown>) => {
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:70:      determinism: 'preview-only',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:75:          determinism: 'preview-only',
src/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel.tsx:19:  steeringValues?: Record<string, unknown>;
src/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel.tsx:20:  onSteeringChange?: (name: string, value: unknown) => void;
src/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel.tsx:29:  detail?: Record<string, unknown>;
src/tools/video-editor/transitions/catalog.ts:41:    // type is intentionally broad (Record<string,unknown> | function) so
src/tools/video-editor/transitions/catalog.ts:42:    // safe coercion through `unknown` is acceptable here.
src/tools/video-editor/transitions/catalog.ts:43:    renderer: renderer as unknown as TransitionRegistryRecord['renderer'],
src/tools/video-editor/transitions/catalog.ts:63:          blockerReason: 'route-unsupported',
src/tools/video-editor/transitions/catalog.ts:122: * @returns The resolved record, or `undefined` if the ID is unknown.
src/tools/video-editor/transitions/catalog.ts:218:type ParameterValue = number | string | boolean | Record<string, unknown>;
src/tools/video-editor/transitions/catalog.ts:260:): Readonly<Record<string, unknown>> {
src/tools/video-editor/transitions/catalog.ts:265:  const defaults: Record<string, unknown> = {};
src/tools/video-editor/transitions/catalog.ts:309:  const merged: Record<string, unknown> = { ...defaults };
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:52:      determinism: 'preview-only',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:57:          determinism: 'preview-only',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:62:          determinism: 'preview-only',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:67:      blockers: [
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:83:  it('registers provider-owner scoped records and resolves unknown IDs as undefined', () => {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:135:    expect(Object.isFrozen(snapshotA.records[0].renderability.blockers)).toBe(true);
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:329:        determinism: 'preview-only',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:334:            determinism: 'preview-only',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:335:            blockerReason: 'unknown',
src/tools/video-editor/hooks/useRenderState.ts:23:  planRender,
src/tools/video-editor/hooks/useRenderState.ts:56:        return { route: 'preview-only' as const, reason: 'remotion_module_missing_artifact' };
src/tools/video-editor/hooks/useRenderState.ts:100:function formatExportGuardLog(
src/tools/video-editor/hooks/useRenderState.ts:157:    lines.push('Route blockers:');
src/tools/video-editor/hooks/useRenderState.ts:165:          : 'unknown';
src/tools/video-editor/hooks/useRenderState.ts:166:      const route = finding.route ?? 'unknown-route';
src/tools/video-editor/hooks/useRenderState.ts:187:  if (diagnostic.code.includes('unknown') || diagnostic.code.includes('missing')) {
src/tools/video-editor/hooks/useRenderState.ts:199:  return 'route-unsupported';
src/tools/video-editor/hooks/useRenderState.ts:226:function planFromExportGuardResult(
src/tools/video-editor/hooks/useRenderState.ts:231:    ...(guardResult.blockers ?? []),
src/tools/video-editor/hooks/useRenderState.ts:234:  return planRender({ diagnostics });
src/tools/video-editor/hooks/useRenderState.ts:246:    blockers: format.blockers ?? [],
src/tools/video-editor/hooks/useRenderState.ts:354:  const runExportGuard = useCallback((): boolean => {
src/tools/video-editor/hooks/useRenderState.ts:377:    const plannerResult = planFromExportGuardResult(guardResult);
src/tools/video-editor/hooks/useRenderState.ts:382:    syncPlannerDiagnosticsToCollection(diagnosticCollection, plannerResult.blockers);
src/tools/video-editor/hooks/useRenderState.ts:385:    const log = formatExportGuardLog(guardResult);
src/tools/video-editor/hooks/useRenderState.ts:388:    if (plannerResult.blockers.length > 0) {
src/tools/video-editor/hooks/useRenderState.ts:389:      // Planner-owned blockers are the canonical readiness decision.
src/tools/video-editor/hooks/useRenderState.ts:401:    // ---- export guard: scan for unknown IDs before routing ------------------
src/tools/video-editor/hooks/useRenderState.ts:402:    if (!runExportGuard()) {
src/tools/video-editor/hooks/useRenderState.ts:409:      route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
src/tools/video-editor/hooks/useRenderState.ts:414:        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
src/tools/video-editor/hooks/useRenderState.ts:426:    if (decision.route === 'preview-only') {
src/tools/video-editor/hooks/useRenderState.ts:501:  }, [exporter, renderMetadata?.durationInFrames, resolvedConfig, startClientRender, runExportGuard]);
src/tools/video-editor/hooks/useRenderState.ts:515:    const outputPlan = planRender({
src/tools/video-editor/hooks/useRenderState.ts:539:      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
src/tools/video-editor/hooks/useRenderState.ts:540:        ?? browserOutputPlan?.blockers[0]
src/tools/video-editor/hooks/useRenderState.ts:541:        ?? outputPlan.blockers[0];
src/tools/video-editor/hooks/useRenderState.ts:557:    // blockers (browser-export blocked, worker-export blocked) are surfaced
src/tools/video-editor/hooks/useRenderState.ts:559:    const guardPassed = runExportGuard();
src/tools/video-editor/hooks/useRenderState.ts:561:      // Export guard found blocking errors (e.g. truly unknown effects).
src/tools/video-editor/hooks/useRenderState.ts:629:        (result.hasBlockingErrors ? ' (with blocking errors)' : '') +
src/tools/video-editor/hooks/useRenderState.ts:632:    } catch (err: unknown) {
src/tools/video-editor/hooks/useRenderState.ts:637:  }, [resolvedConfig, extensionRuntime, runExportGuard]);
src/tools/video-editor/components/ParameterControls.tsx:7:  values: Record<string, unknown>;
src/tools/video-editor/components/ParameterControls.tsx:8:  onChange: (name: string, value: unknown) => void;
src/tools/video-editor/components/ParameterControls.tsx:19:const isAudioBindingValue = (value: unknown): value is AudioBindingValue => {
src/tools/video-editor/components/ParameterControls.tsx:24:  const candidate = value as Record<string, unknown>;
src/tools/video-editor/components/ParameterControls.tsx:54:export function getDefaultValues(schema: ParameterSchema): Record<string, unknown> {
src/tools/video-editor/components/ParameterControls.tsx:55:  return schema.reduce<Record<string, unknown>>((defaults, parameter) => {
src/tools/video-editor/pages/VideoEditorPage.test.tsx:34:  supabaseCtor: vi.fn(function MockSupabaseProvider(this: Record<string, unknown>, options: unknown) {
src/tools/video-editor/pages/VideoEditorPage.test.tsx:42:  bridgeCtor: vi.fn(function MockBridgeProvider(this: Record<string, unknown>, options: unknown) {
src/tools/video-editor/pages/VideoEditorPage.test.tsx:120:          data-kind={dataProvider.kind ?? 'unknown'}
src/tools/video-editor/pages/VideoEditorPage.test.tsx:166:    (import.meta.env as Record<string, unknown>).DEV = true;
src/tools/video-editor/pages/VideoEditorPage.test.tsx:192:    (import.meta.env as Record<string, unknown>).DEV = originalDEV;
src/tools/video-editor/adapters/reigh/useReighTimelinesList.test.ts:15:let timelineResponse: { data: unknown; error: { message: string } | null } = { data: [], error: null };
src/tools/video-editor/adapters/reigh/useReighTimelinesList.test.ts:22:    then(resolve: (value: unknown) => void) {
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:31:  const [Component, setComponent] = useState<FC<unknown> | null>(null);
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:41:        setComponent(() => compiled as unknown as FC<unknown>);
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:43:      .catch((err: unknown) => {
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:65:    const baseParams = (defaultsJson ?? {}) as Record<string, unknown>;
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:66:    const isStringArray = (v: unknown): v is string[] =>
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:68:    const resolveKeysToUrls = (raw: unknown): string[] | undefined => {
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:75:    const hasNonEmptyArray = (v: unknown) => Array.isArray(v) && v.length > 0;
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:105:    } as unknown as ResolvedTimelineClip;
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:131:      component={Component as unknown as FC<Record<string, unknown>>}
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:132:      inputProps={inputProps as unknown as Record<string, unknown>}
src/tools/video-editor/clip-types/defineClipType.ts:21:  | { kind: 'unsupported' }
src/tools/video-editor/clip-types/defineClipType.ts:151:export type ClipTypeRenderAdapter<Props extends Record<string, unknown> = Record<string, unknown>> =
src/tools/video-editor/clip-types/defineClipType.ts:154:export type ClipTypeInspectorAdapter<Props extends Record<string, unknown> = Record<string, unknown>> =
src/tools/video-editor/clip-types/defineClipType.ts:243:  return hold ?? { kind: 'unsupported' };
src/tools/video-editor/clip-types/defineClipType.ts:256:  if (hold.kind !== 'unsupported' && clipDefaults.hold === undefined) {
src/tools/video-editor/transitions/validation.test.ts:506:    const corruptedTransition = { type: 42 as unknown as string, duration: 'bad' as unknown as number };
src/tools/video-editor/transitions/validation.test.ts:533:      makeClipTransition({ type: 'unknown-transition' }),
src/tools/video-editor/transitions/validation.test.ts:547:      makeClipTransition({ type: 'unknown' }),
src/tools/video-editor/adapters/reigh/useReighTimelinesList.ts:41:          config: createDefaultTimelineConfig() as unknown as Json,
src/tools/video-editor/adapters/reigh/useReighTimelinesList.ts:42:          asset_registry: { assets: {} } as unknown as Json,
src/tools/video-editor/shaders/compile/diagnostics.test.ts:47:  it('reports stable diagnostics for unsupported uniform schema entries', () => {
src/tools/video-editor/shaders/compile/diagnostics.test.ts:115:  it('reports stable diagnostics for unsupported texture schema entries', () => {
src/tools/video-editor/hooks/useExternalDrop.ts:101:  onAssetDropError?: (error: unknown) => void;
src/tools/video-editor/data/DataProvider.ts:25:export function isTimelineVersionConflictError(error: unknown): error is TimelineVersionConflictError {
src/tools/video-editor/data/DataProvider.ts:39:export function isTimelineNotFoundError(error: unknown): error is TimelineNotFoundError {
src/tools/video-editor/data/DataProvider.ts:56:// Stable diagnostic codes for unsupported extension persistence capabilities
src/tools/video-editor/data/DataProvider.ts:65:  'provider_capability_extension_state_unsupported' as const;
src/tools/video-editor/data/DataProvider.ts:72:  'provider_capability_extension_settings_unsupported' as const;
src/tools/video-editor/data/DataProvider.ts:79:  'provider_capability_extension_proposals_unsupported' as const;
src/tools/video-editor/data/DataProvider.ts:124:  readonly payload: Record<string, unknown>;
src/tools/video-editor/data/DataProvider.ts:130:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/data/DataProvider.ts:214: * callers receive normalized unsupported diagnostics.
src/tools/video-editor/data/DataProvider.ts:276:   * Returns `null` when no snapshot exists or settings are unsupported.
src/tools/video-editor/data/DataProvider.ts:314:  updateProposalStatus?(id: string, status: ExtensionProposalStatus, detail?: Record<string, unknown>): Promise<ExtensionProposalRecord | void>;
src/tools/video-editor/data/DataProvider.ts:345:   * this method absent. When absent, callers receive normalized unsupported
src/tools/video-editor/data/DataProvider.ts:355:   *   {@link ExtensionDiagnostic} entries to (unsupported notices,
src/tools/video-editor/data/DataProvider.ts:382: * `provider_capability_extension_*_unsupported` codes. Callers that
src/tools/video-editor/data/DataProvider.ts:391: *   is absent, that capability is treated as **unsupported** and a diagnostic
src/tools/video-editor/data/DataProvider.ts:394: *   `false`, the diagnostic is emitted (explicit unsupported).
src/tools/video-editor/clip-types/runtime.test.ts:14:  it('resolves builtin, available sequence, unavailable sequence, and unknown clip types distinctly', () => {
src/tools/video-editor/clip-types/runtime.test.ts:37:      status: 'unknown',
src/tools/video-editor/clip-types/runtime.test.ts:56:  it('returns unknown for extension-only clip types (no built-in or trusted descriptor)', () => {
src/tools/video-editor/clip-types/runtime.test.ts:63:    // returns 'unknown' from this legacy path. Consumers should use
src/tools/video-editor/clip-types/runtime.test.ts:66:      status: 'unknown',
src/tools/video-editor/clip-types/runtime.test.ts:79:    expect(view.resolveRegistration('missing-type').status).toBe('unknown');
src/tools/video-editor/clip-types/runtime.test.ts:354:  it('returns undefined for unknown clipType without records', () => {
src/tools/video-editor/clip-types/runtime.test.ts:379:    expect((meta as Record<string, unknown>)?.params).toMatchObject({ intensity: 0.8 });
src/tools/video-editor/clip-types/runtime.test.ts:382:  it('returns null for unknown clip type even with extension records', () => {
src/tools/video-editor/clip-types/runtime.test.ts:398:    expect((meta as Record<string, unknown>)?.params).toMatchObject({
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:1:type RecordShape = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:3:export type TimelineConfigT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:4:export type TimelineClipT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:5:export type ThemeOverridesT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:6:export type TimelineOutputT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:7:export type AssetEntryT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:8:export type ThemeT = Record<string, unknown>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:9:export type ThemeRegistry = Record<string, Record<string, unknown>>;
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:11:const isRecord = (value: unknown): value is RecordShape => {
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts:31:    theme_overrides?: Record<string, unknown> | null;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:18:  values: Record<string, unknown>;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:19:  onChange: (next: Record<string, unknown>) => void;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:30:  value: unknown;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:31:  onChange: (next: unknown) => void;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:120:  value: unknown;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:121:  onChange: (next: unknown) => void;
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx:136:    (name: string, next: unknown) => onChange({ ...values, [name]: next }),
src/tools/video-editor/testing/banodoco-stubs/theme-api.tsx:18:    motion?: Record<string, unknown>;
src/tools/video-editor/shaders/compile/diagnostics.ts:12:  UNIFORM_UNSUPPORTED: 'shader/uniform-unsupported',
src/tools/video-editor/shaders/compile/diagnostics.ts:13:  TEXTURE_UNSUPPORTED: 'shader/texture-unsupported',
src/tools/video-editor/shaders/compile/diagnostics.ts:31:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/shaders/compile/diagnostics.ts:79:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/shaders/compile/diagnostics.ts:83:function isNonEmptyString(value: unknown): value is string {
src/tools/video-editor/shaders/compile/diagnostics.ts:87:function isFiniteNumber(value: unknown): value is number {
src/tools/video-editor/shaders/compile/diagnostics.ts:91:function isFiniteNumberVector(value: unknown, length: number): value is readonly number[] {
src/tools/video-editor/shaders/compile/diagnostics.ts:108:  detail: Record<string, unknown>,
src/tools/video-editor/shaders/compile/diagnostics.ts:109:  idParts: readonly unknown[],
src/tools/video-editor/shaders/compile/diagnostics.ts:138:  detail: Record<string, unknown> = {},
src/tools/video-editor/shaders/compile/diagnostics.ts:159:  detail: Record<string, unknown> = {},
src/tools/video-editor/shaders/compile/diagnostics.ts:176:  value: unknown,
src/tools/video-editor/shaders/compile/diagnostics.ts:191:  uniform: Record<string, unknown>,
src/tools/video-editor/shaders/compile/diagnostics.ts:256:  uniform: Record<string, unknown>,
src/tools/video-editor/shaders/compile/diagnostics.ts:281:  uniforms: unknown,
src/tools/video-editor/shaders/compile/diagnostics.ts:334:  textures: unknown,
src/tools/video-editor/shaders/compile/diagnostics.ts:524:  input: { readonly uniforms?: unknown; readonly textures?: unknown },
src/tools/video-editor/components/KeyframeInspector/KeyframeInspector.test.tsx:227:        { time: 0, value: 'not-a-number' as unknown as number, interpolation: 'linear' },
src/tools/video-editor/clip-types/manifest.ts:48:  sequenceRegistry: Partial<Record<string, unknown>>,
src/tools/video-editor/clip-types/manifest.ts:70:  sequenceRegistry: Partial<Record<string, unknown>>,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:8:export type WebGLShaderCompileStatus = 'compiled' | 'failed' | 'unsupported';
src/tools/video-editor/shaders/compile/webgl-adapter.ts:60:  detail: Record<string, unknown> = {},
src/tools/video-editor/shaders/compile/webgl-adapter.ts:212:      status: 'unsupported',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:216:          'unsupported',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:228:      status: 'unsupported',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:232:          'unsupported',
src/tools/video-editor/hooks/useTimelineState.ts:715:    const validate = (input: TimelineEditorCommandInput | unknown, options?: Parameters<typeof editorCommandRunner.validate>[2]) => {
src/tools/video-editor/hooks/useTimelineState.ts:719:    const dryRun = (input: TimelineEditorCommandInput | unknown, options?: Parameters<typeof editorCommandRunner.dryRun>[2]) => {
src/tools/video-editor/hooks/useTimelineState.ts:723:    const apply = (input: TimelineEditorCommandInput | unknown, options?: Parameters<TimelineEditorCommands['apply']>[1]): TimelineEditorCommandResult => {
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.test.tsx:287:  mocks.useTimelinePlaybackSelector.mockImplementation((selector: (value: { currentTime: number }) => unknown) => selector({ currentTime: 2 }));
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.test.tsx:770:      drafts: Array<{ clipType: string; hold: number; params: Record<string, unknown> }>;
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:42:  } as unknown as HTMLCanvasElement;
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:90:  return gl as unknown as WebGLRenderingContext;
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:184:  it('reports unavailable WebGL as an unsupported diagnostic in jsdom-safe tests', () => {
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:191:    expect(result.status).toBe('unsupported');
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:200:          status: 'unsupported',
src/tools/video-editor/components/SequenceCreator/sequenceGenerationService.ts:27:  editContext?: unknown;
src/tools/video-editor/components/SequenceCreator/sequenceGenerationService.ts:201:  controls?: unknown[];
src/tools/video-editor/components/SequenceCreator/sequenceGenerationService.ts:223:  controlsManifest?: unknown[];
src/tools/video-editor/clip-types/registry.ts:22:  hold: Exclude<ClipTypeHoldSupport, { kind: 'unsupported' }>;
src/tools/video-editor/clip-types/registry.ts:37:  componentEntry: unknown;
src/tools/video-editor/clip-types/registry.ts:43:  | { status: 'unknown'; clipType: string | undefined };
src/tools/video-editor/clip-types/registry.ts:48:  | { status: 'unknown'; clipType: string | undefined };
src/tools/video-editor/clip-types/registry.ts:55:  isAvailableClipType: (value: unknown) => value is string;
src/tools/video-editor/clip-types/registry.ts:63:  registry: Partial<Record<string, unknown>>,
src/tools/video-editor/clip-types/registry.ts:149:  value: unknown,
src/tools/video-editor/clip-types/registry.ts:176:    return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:181:    : { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:185:  registry: Partial<Record<string, unknown>>,
src/tools/video-editor/clip-types/registry.ts:208:  registry: Partial<Record<string, unknown>>,
src/tools/video-editor/clip-types/registry.ts:225:      return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:235:    return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:243:    isAvailableClipType: (value: unknown): value is string => (
src/tools/video-editor/clip-types/registry.ts:279:  | { status: 'available'; clipType: string; source: 'extension'; extensionRecord: Record<string, unknown> }
src/tools/video-editor/clip-types/registry.ts:282:  | { status: 'unknown'; clipType: string | undefined };
src/tools/video-editor/clip-types/registry.ts:291:  readonly [key: string]: unknown;
src/tools/video-editor/clip-types/registry.ts:308: * Unknown clip types (not in any source) return `unknown` status.
src/tools/video-editor/clip-types/registry.ts:316:    return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:341:        (record) => record.ownerExtensionId ?? '(unknown)',
src/tools/video-editor/clip-types/registry.ts:370:      extensionRecord: matchingExtensions[0]! as Record<string, unknown>,
src/tools/video-editor/clip-types/registry.ts:375:  return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/registry.ts:382: * and unknowns.
src/tools/video-editor/clip-types/registry.test.ts:54:  it('surfaces available, unavailable, and unknown clip-type resolutions loudly', () => {
src/tools/video-editor/clip-types/registry.test.ts:66:      status: 'unknown',
src/tools/video-editor/clip-types/registry.test.ts:83:      status: 'unknown',
src/tools/video-editor/clip-types/registry.test.ts:168:  it('returns unknown for clip types not in any source', () => {
src/tools/video-editor/clip-types/registry.test.ts:170:      status: 'unknown',
src/tools/video-editor/clip-types/registry.test.ts:174:      status: 'unknown',
src/tools/video-editor/clip-types/registry.test.ts:179:  it('returns unknown for undefined clipType', () => {
src/tools/video-editor/clip-types/registry.test.ts:181:      status: 'unknown',
src/tools/video-editor/clip-types/registry.test.ts:237:  it('returns undefined for unknown types', () => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:23:  values: Record<string, unknown>;
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:26:  onChange: (next: Record<string, unknown>) => void;
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:33:  enum?: unknown[];
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:77:  value: unknown,
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:85:const toNumber = (value: unknown): number | null => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:94:const toString = (value: unknown): string => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:100:const toBoolean = (value: unknown): boolean => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:106:const toStringArray = (value: unknown): string[] => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:132:    (name: string, nextValue: unknown) => {
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx:296:                  const parsed: unknown = JSON.parse(event.target.value);
src/tools/video-editor/components/KeyframeInspector/KeyframeInspector.tsx:73:    (nextValue: unknown) => {
src/tools/video-editor/clip-types/runtime.ts:20:export type ClipAssetMediaType = 'image' | 'video' | 'audio' | 'unknown';
src/tools/video-editor/clip-types/runtime.ts:48:  | { status: 'unknown'; clipType: string | undefined };
src/tools/video-editor/clip-types/runtime.ts:378:  return 'unknown';
src/tools/video-editor/clip-types/runtime.ts:401:  return 'unknown';
src/tools/video-editor/clip-types/runtime.ts:448:    default?: number | string | boolean | Record<string, unknown>;
src/tools/video-editor/clip-types/runtime.ts:542:  registry: Partial<Record<string, unknown>>,
src/tools/video-editor/clip-types/runtime.ts:543:  extensionRecords?: readonly { clipTypeId: string; ownerExtensionId?: string; [key: string]: unknown }[],
src/tools/video-editor/clip-types/runtime.ts:576:        : { status: 'unknown', clipType };
src/tools/video-editor/clip-types/runtime.ts:602:          (ext) => ext.ownerExtensionId ?? '(unknown)',
src/tools/video-editor/clip-types/runtime.ts:631:      return { status: 'unknown', clipType };
src/tools/video-editor/clip-types/runtime.ts:663:  clipOverrides?: Record<string, unknown>;
src/tools/video-editor/clip-types/runtime.ts:664:  params?: Record<string, unknown>;
src/tools/video-editor/clip-types/runtime.ts:667:}): Record<string, unknown> | null => {
src/tools/video-editor/clip-types/runtime.ts:692:  return Boolean(descriptor && descriptor.hold.kind !== 'unsupported');
src/tools/video-editor/clip-types/runtime.ts:758:): unknown => {
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:300:    editContext?: unknown;
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:354:          controlsManifest: codeResult.controlsManifest as unknown[],
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:437:          controlsManifest: codeResult.controlsManifest as unknown[],
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:540:        controlsManifest: codeResult.controlsManifest as unknown[],
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:806:      controlsManifest: resource.controlsManifest as unknown[] | undefined,
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1200:                                  min={selectedMetadata?.hold.minSeconds ?? resolvedDescriptor?.hold?.kind !== 'unsupported' ? (resolvedDescriptor?.hold as { defaultSeconds: number; minSeconds: number; maxSeconds: number; stepSeconds: number })?.minSeconds ?? 0.05 : 0.05}
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1201:                                  max={selectedMetadata?.hold.maxSeconds ?? (resolvedDescriptor?.hold?.kind !== 'unsupported' ? (resolvedDescriptor?.hold as { defaultSeconds: number; minSeconds: number; maxSeconds: number; stepSeconds: number })?.maxSeconds ?? 120 : 120)}
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1202:                                  step={selectedMetadata?.hold.stepSeconds ?? (resolvedDescriptor?.hold?.kind !== 'unsupported' ? (resolvedDescriptor?.hold as { defaultSeconds: number; minSeconds: number; maxSeconds: number; stepSeconds: number })?.stepSeconds ?? 0.1 : 0.1)}
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1224:                                  hold: resolvedDescriptor.hold?.kind !== 'unsupported'
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1284:                                    values={generatedComponent.defaultsJson as Record<string, unknown>}
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:1294:                                  values={generatedComponent.defaultsJson as Record<string, unknown>}
src/tools/video-editor/testing/InMemoryDataProvider.extensionPersistence.test.ts:26:describe('unsupported extension persistence conformance helper', () => {
src/tools/video-editor/testing/InMemoryDataProvider.extensionPersistence.test.ts:27:  it('emits normalized unsupported diagnostics for providers without a factory', () => {
src/tools/video-editor/testing/InMemoryDataProvider.extensionPersistence.test.ts:29:    expectUnsupportedExtensionPersistenceDiagnostics({}, diagnostics, 'unsupported provider');
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:22:  detail?: Record<string, unknown>,
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:65:    ...(renderability.blockers
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:67:          blockers: Object.freeze(
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:68:            renderability.blockers.map((blocker) => Object.freeze({ ...blocker })),
src/tools/video-editor/data/AstridBridgeDataProvider.ts:32:  timeline_id?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:33:  timeline_ulid?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:34:  slug?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:35:  name?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:36:  config?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:37:  config_version?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:38:  registry?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.ts:131:const normalizeRegistry = (value: unknown): AssetRegistry => {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:138:const normalizeConfig = (value: unknown): TimelineConfig => {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:145:const normalizeConfigVersion = (value: unknown): number => {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:488:      const payload = await response.json() as { error?: unknown; detail?: unknown };
src/tools/video-editor/data/AstridBridgeDataProvider.ts:736:  ): Promise<unknown> {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:749:  ): Promise<unknown | null> {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:760:    value: unknown,
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:32:  it('registers provider-local records and resolves unknown IDs as undefined', () => {
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:219:    registry.register(record('transition.preview-only', {
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:222:        code: 'transition/preview-only',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:227:        determinism: 'preview-only',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:232:            determinism: 'preview-only',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:233:            blockerReason: 'preview-only',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:236:        blockers: [
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:238:            id: 'transition.preview-only.browser-export',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:241:            reason: 'preview-only',
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:248:    const entry = registry.getSnapshot().get('transition.preview-only');
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:251:    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:252:    expect(entry?.diagnostics?.[0].code).toBe('transition/preview-only');
src/tools/video-editor/transitions/catalog.test.ts:54:    const result = materializeTransitionDefaults(null as unknown as ParameterSchema);
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:17:  useRenderDiagnostic: (...args: unknown[]) => useRenderDiagnosticMock(...args),
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:87:function createOverlayTestStore(options: { resolvedConfig?: typeof defaultResolvedConfig & { app?: Record<string, unknown> } } = {}) {
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:195:function renderWithStore(ui: React.ReactElement, options: { resolvedConfig?: typeof defaultResolvedConfig & { app?: Record<string, unknown> } } = {}) {
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:296:      } as typeof defaultResolvedConfig & { app: Record<string, unknown> };
src/tools/video-editor/sequences/validation.test.ts:6:const expectErrorCode = (input: unknown, code: string): void => {
src/tools/video-editor/sequences/validation.test.ts:75:  it('rejects unsupported image-jump modes', () => {
src/tools/video-editor/sequences/validation.test.ts:96:  it('rejects unknown clip types', () => {
src/tools/video-editor/sequences/validation.test.ts:101:    }, 'unknown_clip_type');
src/tools/video-editor/sequences/validation.test.ts:130:  it('rejects unknown params', () => {
src/tools/video-editor/sequences/validation.test.ts:138:    }, 'unknown_param');
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:5:(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:6:(globalThis as Record<string, unknown>).IDBKeyRange = IDBKeyRange;
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:50:    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:79:    it('loadSyncBookmark returns null for unknown key', async () => {
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:84:    it('loadKeepBothArtifact returns null for unknown key', async () => {
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:89:    it('listKeepBothArtifacts returns empty array for unknown timeline', async () => {
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:451:      (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:509:      const original = (globalThis as Record<string, unknown>).indexedDB;
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:510:      delete (globalThis as Record<string, unknown>).indexedDB;
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:521:      (globalThis as Record<string, unknown>).indexedDB = original;
src/tools/video-editor/transitions/validation.ts:85:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/transitions/validation.ts:118:  detail?: Record<string, unknown>,
src/tools/video-editor/transitions/validation.ts:157:  raw: unknown,
src/tools/video-editor/transitions/validation.ts:193:  const obj = raw as Record<string, unknown>;
src/tools/video-editor/sequences/controlsManifest.ts:102:const isFiniteNumber = (value: unknown): value is number =>
src/tools/video-editor/sequences/controlsManifest.ts:105:const isPlainObject = (value: unknown): value is Record<string, unknown> =>
src/tools/video-editor/sequences/controlsManifest.ts:109:  entry: unknown,
src/tools/video-editor/sequences/controlsManifest.ts:260:  manifest: unknown,
src/tools/video-editor/sequences/controlsManifest.ts:305:export function buildDefaultsFromManifest(manifest: ControlsManifest): Record<string, unknown> {
src/tools/video-editor/sequences/controlsManifest.ts:306:  const defaults: Record<string, unknown> = {};
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:27:  useAgentChatBridge: (...args: unknown[]) => mocks.useAgentChatBridge(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:28:  useAgentChatActionsRegistry: (...args: unknown[]) => mocks.useAgentChatActionsRegistry(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:32:  useVideoEditorRuntime: (...args: unknown[]) => mocks.useVideoEditorRuntime(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:36:  useAgentSessions: (...args: unknown[]) => mocks.useAgentSessions(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:37:  useCreateSession: (...args: unknown[]) => mocks.useCreateSession(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:38:  useAgentSession: (...args: unknown[]) => mocks.useAgentSession(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:39:  useSendMessage: (...args: unknown[]) => mocks.useSendMessage(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:40:  useCancelSession: (...args: unknown[]) => mocks.useCancelSession(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:44:  composerRemoveAttachment: (...args: unknown[]) => mocks.composerRemoveAttachment(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:45:  composerClearAttachments: (...args: unknown[]) => mocks.composerClearAttachments(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:49:  useCurrentAttachmentSet: (...args: unknown[]) => mocks.useCurrentAttachmentSet(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:54:  usePanesStore: (selector: (state: { isTasksPaneLocked: boolean }) => unknown) =>
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:59:  useAgentVoice: (...args: unknown[]) => mocks.useAgentVoice(...args),
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx:63:  loadGenerationForLightbox: (...args: unknown[]) => mocks.loadGenerationForLightbox(...args),
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:92:  readonly params: Record<string, unknown>;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:104:  readonly params: Record<string, unknown>;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:105:  readonly onParamsChange: (params: Record<string, unknown>) => void;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:112:  readonly renderer: Record<string, unknown> | ((...args: unknown[]) => unknown);
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:113:  readonly inspector?: Record<string, unknown> | ((...args: unknown[]) => unknown);
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:119:    readonly default?: number | string | boolean | Record<string, unknown>;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:175:  detail?: Record<string, unknown>,
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:220:    ...(renderability.blockers
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:222:          blockers: Object.freeze(
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:223:            renderability.blockers.map((b) => Object.freeze({ ...b })),
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:536:    default?: unknown;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:537:    min?: unknown;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:538:    max?: unknown;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:539:    step?: unknown;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:540:    options?: unknown;
src/tools/video-editor/commands/media.ts:340:        code: 'unsupported_clip_type',
src/tools/video-editor/sequences/metadata.ts:17:  previewFallbackReason?: 'worker_only' | 'unsupported';
src/tools/video-editor/sequences/metadata.ts:257:export const isTrustedSequenceClipType = (value: unknown): value is TrustedSequenceClipType => {
src/tools/video-editor/sequences/generation.ts:25:  params: Record<string, unknown>;
src/tools/video-editor/sequences/generation.ts:48:  drafts?: unknown[];
src/tools/video-editor/sequences/generation.ts:49:  invalid_drafts?: Array<{ index: number; errors: unknown[] }>;
src/tools/video-editor/sequences/generation.ts:75:export type SequenceMetadataPatch = Record<string, unknown>;
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:302:  dataRef?: { current: unknown };
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:1545:      expect((handledEvent!.detail as Record<string, unknown>).handled).toBe(true);
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:1546:      expect((handledEvent!.detail as Record<string, unknown>).extensionId).toBe('ext.test');
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:1603:      expect((handledEvent!.detail as Record<string, unknown>).handled).toBe(true);
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:1604:      expect((handledEvent!.detail as Record<string, unknown>).targetId).toBeUndefined();
src/tools/video-editor/data/SupabaseDataProvider.test.ts:52:function mockTimelinesSelect(response: unknown) {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:59:function mockTimelineHeadSelect(response: unknown) {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:68:function mockTimelineHeadSelectSequence(...responses: unknown[]) {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:80:function mockSyncBookmarkSelect(response: unknown) {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:125:  const matches = (row: Record<string, any>, filters: Record<string, unknown>) =>
src/tools/video-editor/data/SupabaseDataProvider.test.ts:129:    const filters: Record<string, unknown> = {};
src/tools/video-editor/data/SupabaseDataProvider.test.ts:143:      eq: vi.fn((key: string, value: unknown) => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:810:      let caught: unknown;
src/tools/video-editor/data/SupabaseDataProvider.test.ts:917:      const allEqCalls: Array<{ table: string; col: string; val: unknown }> = [];
src/tools/video-editor/data/SupabaseDataProvider.test.ts:930:            eq: vi.fn((col: string, val: unknown) => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:994:      const upsertedRows: Array<Record<string, unknown>> = [];
src/tools/video-editor/data/SupabaseDataProvider.test.ts:1005:            upsert: vi.fn(async (row: Record<string, unknown>) => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:1009:            insert: vi.fn(async (row: Record<string, unknown>) => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:1047:      const deleteFilters: Array<Record<string, unknown>> = [];
src/tools/video-editor/data/SupabaseDataProvider.test.ts:1070:          eq: vi.fn((col: string, val: unknown) => {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:23:        { route: 'preview', status: 'supported', determinism: 'preview-only' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:24:        { route: 'browser-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported', message: 'Browser export is not declared.' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:25:        { route: 'worker-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported', message: 'Worker export is not declared.' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:28:      determinism: 'preview-only',
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:69:  it('resolve() returns undefined for unknown clip types', () => {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:157:  it('unregister() is a no-op for unknown clip types', () => {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:176:  it('unregisterOwner() is a no-op for unknown owners', () => {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:178:    expect(() => registry.unregisterOwner('unknown-ext')).not.toThrow();
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:329:          { route: 'preview', status: 'supported', determinism: 'preview-only' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:330:          { route: 'browser-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:331:          { route: 'worker-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported' },
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:334:        determinism: 'preview-only',
src/tools/video-editor/commands/runner.ts:34:const isRecord = (value: unknown): value is Record<string, unknown> => {
src/tools/video-editor/commands/runner.ts:38:const isJsonValue = (value: unknown): value is JsonValue => {
src/tools/video-editor/commands/runner.ts:62:const normalizeJsonObject = (value: unknown): JsonObject | null => {
src/tools/video-editor/commands/runner.ts:75:  input: unknown,
src/tools/video-editor/commands/runner.ts:141:  input: TimelineCommandInput | unknown,
src/tools/video-editor/commands/runner.ts:208:const asErrorMessage = (error: unknown): string => {
src/tools/video-editor/commands/runner.ts:344:        code: 'unknown_command',
src/tools/video-editor/commands/runner.ts:539:  input: TimelineCommandInput<TCommand> | unknown,
src/tools/video-editor/sequences/headlessRender.ts:109:} as unknown as ResolvedTimelineClip;
src/tools/video-editor/sequences/headlessRender.ts:135:  const smokeGlobals: Record<string, unknown> = {
src/tools/video-editor/sequences/headlessRender.ts:151:  let Component: FC<unknown>;
src/tools/video-editor/sequences/headlessRender.ts:153:    const result = await compileWithGlobalsAsync<unknown>(input.code, smokeGlobals, {
src/tools/video-editor/sequences/headlessRender.ts:160:    Component = result.component as unknown as FC<unknown>;
src/tools/video-editor/sequences/headlessRender.ts:177:        // Cast through Record<string, unknown> because component accepts a
src/tools/video-editor/sequences/headlessRender.ts:180:        createElement(Component as FC<Record<string, unknown>>, componentProps as Record<string, unknown>),
src/tools/video-editor/sequences/registry.ts:20:  component?: unknown;
src/tools/video-editor/sequences/registry.ts:42:    previewFallbackReason?: 'worker_only' | 'unsupported';
src/tools/video-editor/sequences/registry.ts:118:  registry: Partial<Record<string, unknown>>,
src/tools/video-editor/sequences/registry.ts:119:  themeRegistry: Partial<Record<string, unknown>> = INSTALLED_TIMELINE_THEMES,
src/tools/video-editor/sequences/registry.ts:201:export const isAvailableSequenceClipType = (value: unknown): value is AvailableSequenceMetadata['clipType'] => {
src/tools/video-editor/sequences/registry.ts:220:  | { status: 'unknown'; clipType: string | undefined } => {
src/tools/video-editor/sequences/registry.ts:222:    return { status: 'unknown', clipType };
src/tools/video-editor/sequences/registry.ts:235:  return { status: 'unknown', clipType };
src/tools/video-editor/sequences/registry.ts:288:    params?: Record<string, unknown>;
src/tools/video-editor/sequences/registry.ts:289:    theme?: unknown;
src/tools/video-editor/sequences/registry.ts:300:  params?: Record<string, unknown>;
src/tools/video-editor/sequences/registry.ts:301:} & Record<string, unknown>;
src/tools/video-editor/data/generationAssetResolver.test.ts:54:function makeGenerationRecord(overrides: Record<string, unknown> = {}): Record<string, unknown> {
src/tools/video-editor/data/generationAssetResolver.test.ts:210:    } as unknown as ReturnType<typeof getSupabaseClient>);
src/tools/video-editor/data/generationAssetResolver.test.ts:276:    } as unknown as ReturnType<typeof getSupabaseClient>);
src/tools/video-editor/data/generationAssetResolver.test.ts:507:      assetId: 'asset-unsupported',
src/tools/video-editor/data/generationAssetResolver.test.ts:581:    } as unknown as ReturnType<typeof getSupabaseClient>);
src/tools/video-editor/data/generationAssetResolver.test.ts:648:    } as unknown as ReturnType<typeof getSupabaseClient>);
src/tools/video-editor/data/generationAssetResolver.test.ts:680:    } as unknown as ReturnType<typeof getSupabaseClient>);
src/tools/video-editor/commands/types.ts:40:  | 'unknown_command'
src/tools/video-editor/commands/types.ts:183:    input: TimelineCommandInput<TCommand> | unknown,
src/tools/video-editor/commands/types.ts:188:    input: TimelineCommandInput<TCommand> | unknown,
src/tools/video-editor/commands/types.ts:193:    input: TimelineCommandInput<TCommand> | unknown,
src/tools/video-editor/data/generationAssetResolver.ts:20:interface RawGenerationRecord extends Record<string, unknown> {
src/tools/video-editor/data/generationAssetResolver.ts:25:  params?: Record<string, unknown> | null;
src/tools/video-editor/data/generationAssetResolver.ts:79:function trimToUndefined(value: unknown): string | undefined {
src/tools/video-editor/data/generationAssetResolver.ts:88:function normalizeGenerationRecord(value: Record<string, unknown> | null): RawGenerationRecord | null {
src/tools/video-editor/data/generationAssetResolver.ts:170:function parseResolution(params: Record<string, unknown>, entry: AssetRegistryEntry | null | undefined): string | undefined {
src/tools/video-editor/data/generationAssetResolver.ts:189:function firstFiniteNumber(...values: unknown[]): number | undefined {
src/tools/video-editor/data/generationAssetResolver.ts:285:    await fetchGenerationRecordById(options.generationId) as Record<string, unknown> | null,
src/tools/video-editor/data/generationAssetResolver.ts:327:      message: `Asset ${options.assetId ?? '(unknown)'} is marked opaque-foreign and cannot be refreshed from generation metadata.`,
src/tools/video-editor/data/AssetResolver.ts:15:  [key: string]: unknown;
src/tools/video-editor/state/sequenceCreatorStore.ts:55:  controlsManifest?: unknown[];
src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx:328:                code: 'timeline-patch/unknown-op' as const,
src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx:344:      expect(screen.getByText('[timeline-patch/unknown-op]')).toBeDefined();
src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx:361:                code: 'timeline-patch/unknown-op' as const,
src/tools/video-editor/data/DataProvider.test.ts:46:  it('emits state, settings, and proposals diagnostics when all capabilities are unsupported (undefined)', () => {
src/tools/video-editor/data/DataProvider.test.ts:177:  // -- Empty capabilities object (all keys omitted = all unsupported) --------
src/tools/video-editor/data/DataProvider.test.ts:179:  it('treats an empty capabilities object as all-unsupported', () => {
src/tools/video-editor/data/DataProvider.test.ts:209:      'provider_capability_extension_state_unsupported',
src/tools/video-editor/data/DataProvider.test.ts:215:      'provider_capability_extension_settings_unsupported',
src/tools/video-editor/data/DataProvider.test.ts:221:      'provider_capability_extension_proposals_unsupported',
src/tools/video-editor/data/DataProvider.test.ts:252:  it('simulates the unsupported-path: pushing diagnostics and returning null', () => {
src/tools/video-editor/data/DataProvider.test.ts:266:    // Each normalized unsupported code must be emitted exactly once
src/tools/video-editor/data/DataProvider.test.ts:277:    // Severity is always 'info' for unsupported capability notifications
src/tools/video-editor/data/DataProvider.test.ts:283:  it('unsupported diagnostic codes follow the stable naming convention', () => {
src/tools/video-editor/data/DataProvider.test.ts:284:    // All three codes share the provider_capability_ prefix and _unsupported suffix
src/tools/video-editor/data/DataProvider.test.ts:293:    expect(stateDiag.code.endsWith('_unsupported')).toBe(true);
src/tools/video-editor/hooks/useEffectResources.ts:141:  UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>,
src/tools/video-editor/hooks/useEffectResources.ts:144:  mutate: UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>['mutate'];
src/tools/video-editor/hooks/useEffectResources.ts:145:  mutateAsync: (variables: { metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { metadata: EffectMetadata }, unknown>) => Promise<Resource>;
src/tools/video-editor/hooks/useEffectResources.ts:148:  const base = mutation as unknown as Omit<
src/tools/video-editor/hooks/useEffectResources.ts:149:    UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>,
src/tools/video-editor/hooks/useEffectResources.ts:158:    )) as UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>['mutate'],
src/tools/video-editor/hooks/useEffectResources.ts:162:    )) as (variables: { metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { metadata: EffectMetadata }, unknown>) => Promise<Resource>,
src/tools/video-editor/hooks/useEffectResources.ts:167:  UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>,
src/tools/video-editor/hooks/useEffectResources.ts:170:  mutate: UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>['mutate'];
src/tools/video-editor/hooks/useEffectResources.ts:171:  mutateAsync: (variables: { id: string; metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>) => Promise<Resource>;
src/tools/video-editor/hooks/useEffectResources.ts:174:  const base = mutation as unknown as Omit<
src/tools/video-editor/hooks/useEffectResources.ts:175:    UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>,
src/tools/video-editor/hooks/useEffectResources.ts:184:    )) as UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>['mutate'],
src/tools/video-editor/hooks/useEffectResources.ts:188:    )) as (variables: { id: string; metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>) => Promise<Resource>,
src/tools/video-editor/hooks/useEffectResources.ts:193:  UseMutationResult<void, Error, { id: string }, unknown>,
src/tools/video-editor/hooks/useEffectResources.ts:196:  mutate: UseMutationResult<void, Error, { id: string }, unknown>['mutate'];
src/tools/video-editor/hooks/useEffectResources.ts:197:  mutateAsync: (variables: { id: string }, options?: UseMutationOptions<void, Error, { id: string }, unknown>) => Promise<void>;
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:117:  it('uses deterministic preview and browser-export defaults with explicit unsupported export routes', () => {
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:129:        determinism: 'unknown',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:130:        blockerReason: 'route-unsupported',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:135:        determinism: 'unknown',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:136:        blockerReason: 'route-unsupported',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:258:    const originalWindow = (globalThis as { window?: unknown }).window;
src/tools/video-editor/sequences/compileSequenceComponent.tsx:25:  params?: Record<string, unknown>;
src/tools/video-editor/sequences/compileSequenceComponent.tsx:35:function getSequenceGlobals(): Record<string, unknown> {
src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx:112:    return 'unknown';
src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx:121:function sparseSummary(record: Record<string, unknown> | undefined): string | null {
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:82:        determinism: 'unknown',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:83:        blockerReason: 'route-unsupported',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:89:        determinism: 'unknown',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:90:        blockerReason: 'route-unsupported',
src/tools/video-editor/render/renderPipeline.ts:141:    case 'preview-only':
src/tools/video-editor/render/renderPipeline.ts:144:        providerId: 'preview-only',
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:71:    showDirectoryPicker?: unknown;
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:92:      delete (globalThis as typeof globalThis & { showDirectoryPicker?: unknown }).showDirectoryPicker;
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:94:      (globalThis as typeof globalThis & { showDirectoryPicker?: unknown }).showDirectoryPicker = originalShowDirectoryPicker;
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:224:  it('keeps extension persistence unsupported for M2 and emits normalized diagnostics', () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:659:  it('reports unsupported browsers when File System Access is unavailable', async () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2251:        const assetsObj: Record<string, unknown> = {};
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2284:          hasBlockingErrors: false,
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2333:      expect(exportResult!.hasBlockingErrors).toBe(false);
src/tools/video-editor/lib/timeline-save-utils.test.ts:692:      }] as unknown as TimelineConfig['pinnedShotGroups'],
src/tools/video-editor/effects/registry/EffectRegistry.ts:22:  detail?: Record<string, unknown>,
src/tools/video-editor/effects/registry/EffectRegistry.ts:65:    ...(renderability.blockers
src/tools/video-editor/effects/registry/EffectRegistry.ts:67:          blockers: Object.freeze(
src/tools/video-editor/effects/registry/EffectRegistry.ts:68:            renderability.blockers.map((blocker) => Object.freeze({ ...blocker })),
src/tools/video-editor/lib/compiler-canary.ts:190:    const entry: Record<string, unknown> = {
src/tools/video-editor/sequences/materialize.ts:25:  value: unknown,
src/tools/video-editor/sequences/materialize.ts:58:  params: Record<string, unknown> | undefined,
src/tools/video-editor/sequences/materialize.ts:60:): Record<string, unknown> | undefined => {
src/tools/video-editor/sequences/materialize.ts:64:  let nextParams: Record<string, unknown> = params;
src/tools/video-editor/sequences/materialize.ts:88:      && (nextParams[urlsParam] as unknown[]).length > 0) {
src/tools/video-editor/runtime/liveSteering.ts:205:        'live/steering-unsupported-param',
src/tools/video-editor/runtime/liveSteering.ts:526:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/liveSteering.ts:531:function isNonEmptyString(value: unknown): value is string {
src/tools/video-editor/runtime/liveSteering.ts:535:function isValidSeed(value: unknown): value is string | number {
src/tools/video-editor/runtime/liveSteering.ts:540:function stableHash(value: unknown): string {
src/tools/video-editor/runtime/liveSteering.ts:550:function sortObject(value: unknown): unknown {
src/tools/video-editor/runtime/liveSteering.ts:555:    const record = value as Record<string, unknown>;
src/tools/video-editor/runtime/liveSteering.ts:556:    return Object.keys(record).sort().reduce<Record<string, unknown>>((acc, key) => {
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:119:  finalVideoMap?: Map<string, unknown>;
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:36:  it('registers provider-local records and resolves unknown IDs as undefined', () => {
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:223:    registry.register(record('fx.preview-only', {
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:226:        code: 'effect/preview-only',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:231:        determinism: 'preview-only',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:236:            determinism: 'preview-only',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:237:            blockerReason: 'preview-only',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:240:        blockers: [
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:242:            id: 'fx.preview-only.browser-export',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:245:            reason: 'preview-only',
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:252:    const entry = registry.getSnapshot().get('fx.preview-only');
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:255:    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:256:    expect(entry?.diagnostics?.[0].code).toBe('effect/preview-only');
src/tools/video-editor/data/SupabaseDataProvider.ts:44:  payload: Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:49:  detail?: Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:62:  config_version?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:64:    version?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:65:    hash?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:66:    event_id?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:71:  error?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:72:  detail?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:73:  details?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:132:  timeline_id?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:133:  spoke?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:134:  spoke_version?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:135:  spoke_hash?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:136:  spoke_event_id?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:137:  hub_version?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:138:  hub_hash?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:139:  hub_event_id?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:140:  synced_at?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:144:  bookmark?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:149:    id?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:150:    created_at?: unknown;
src/tools/video-editor/data/SupabaseDataProvider.ts:174:async function parseJsonIfPresent(response: Response): Promise<unknown> {
src/tools/video-editor/data/SupabaseDataProvider.ts:204:function getAppendServiceErrorDetail(payload: unknown): string | null {
src/tools/video-editor/data/SupabaseDataProvider.ts:224:function parseDbHead(value: unknown, label: string): DbHeadSnapshot {
src/tools/video-editor/data/SupabaseDataProvider.ts:228:  const head = value as { version?: unknown; hash?: unknown; event_id?: unknown };
src/tools/video-editor/data/SupabaseDataProvider.ts:249:function normalizeSyncBookmark(value: unknown): SyncBookmarkRecord | null {
src/tools/video-editor/data/SupabaseDataProvider.ts:321:  values: Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:375:    const base = sentinel.metadata as Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:388:    const settings: Record<string, unknown> = {};
src/tools/video-editor/data/SupabaseDataProvider.ts:410:    const proposals: Record<string, unknown> = {};
src/tools/video-editor/data/SupabaseDataProvider.ts:415:      payload: Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:424:      const proposal: Record<string, unknown> = {
src/tools/video-editor/data/SupabaseDataProvider.ts:456:    let parsed: Record<string, unknown>;
src/tools/video-editor/data/SupabaseDataProvider.ts:465:      (parsed.settings as Record<string, Record<string, unknown>>) ?? {};
src/tools/video-editor/data/SupabaseDataProvider.ts:500:              (snapshot as Record<string, unknown>).schemaVersion as number ?? 1,
src/tools/video-editor/data/SupabaseDataProvider.ts:502:              ((snapshot as Record<string, unknown>).values as Record<string, unknown>) ?? {},
src/tools/video-editor/data/SupabaseDataProvider.ts:504:              ((snapshot as Record<string, unknown>).lastWrittenAt as string) ??
src/tools/video-editor/data/SupabaseDataProvider.ts:693:    const remoteConfigVersion = typeof (data as { config_version?: unknown } | null)?.config_version === 'number'
src/tools/video-editor/data/SupabaseDataProvider.ts:787:      configVersion: typeof (data as { config_version?: unknown } | null)?.config_version === 'number'
src/tools/video-editor/data/SupabaseDataProvider.ts:1003:      .map((row: { id?: unknown }) => row.id)
src/tools/video-editor/data/SupabaseDataProvider.ts:1004:      .filter((id: unknown): id is string => typeof id === 'string');
src/tools/video-editor/data/SupabaseDataProvider.ts:1045:    return (data ?? []).map((row: unknown) => mapCheckpointRow(row as TimelineCheckpointRow));
src/tools/video-editor/runtime/extensionPersistenceCache.test.ts:36:  overrides: Record<string, unknown> = {},
src/tools/video-editor/runtime/extensionPersistenceCache.test.ts:60:  values: Record<string, unknown>,
src/tools/video-editor/effects/validateParams.ts:17:  params: Record<string, unknown> | undefined,
src/tools/video-editor/effects/validateParams.ts:19:): Record<string, unknown> {
src/tools/video-editor/effects/validateParams.ts:21:  return schema.reduce<Record<string, unknown>>((result, parameter) => {
src/tools/video-editor/effects/validateParams.ts:33:      const source = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).source : undefined;
src/tools/video-editor/effects/validateParams.ts:34:      const min = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).min : undefined;
src/tools/video-editor/effects/validateParams.ts:35:      const max = typeof value === 'object' && value !== null ? (value as Record<string, unknown>).max : undefined;
src/tools/video-editor/sequences/controlsManifest.test.ts:63:  it('rejects an unknown widget type', () => {
src/tools/video-editor/data/syncLedgerIndexedDb.ts:25:  artifact: Record<string, unknown>;
src/tools/video-editor/data/syncLedgerIndexedDb.ts:92:function shouldRecover(error: unknown): boolean {
src/tools/video-editor/data/syncLedgerIndexedDb.ts:113:      const fail = (error: unknown) => {
src/tools/video-editor/sequences/getBundledComponentSource.ts:41:  properties: {} as Record<string, unknown>,
src/tools/video-editor/sequences/getBundledComponentSource.ts:43:const PLACEHOLDER_DEFAULTS: Record<string, unknown> = {};
src/tools/video-editor/sequences/getBundledComponentSource.ts:46:  'image-jump': imageJumpSource as unknown as string,
src/tools/video-editor/sequences/getBundledComponentSource.ts:47:  'title-card': titleCardSource as unknown as string,
src/tools/video-editor/components/PreviewPanel/RemotionPreview.test.tsx:44:function emitPlayerEvent(name: string, detail: unknown = undefined) {
src/tools/video-editor/runtime/liveMapping.ts:36:  readonly schema?: Record<string, unknown>;
src/tools/video-editor/runtime/liveMapping.ts:49:  readonly frameMetadata?: Record<string, unknown>;
src/tools/video-editor/runtime/liveMapping.ts:61:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/liveMapping.ts:107:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/liveMapping.ts:488:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/processCommandRegistration.ts:6:  invokeProcess: (request: ProcessRoundtripRequest) => Promise<unknown>;
src/tools/video-editor/runtime/processCommandRegistration.ts:20:function validateParams(schema: { required?: readonly string[] } | undefined, params: Record<string, unknown> | undefined): void {
src/tools/video-editor/sequences/validation.ts:58:const isRecord = (value: unknown): value is Record<string, unknown> => {
src/tools/video-editor/sequences/validation.ts:78:const isJsonSerializable = (value: unknown): boolean => {
src/tools/video-editor/sequences/validation.ts:99:  value: unknown,
src/tools/video-editor/sequences/validation.ts:124:  value: unknown,
src/tools/video-editor/sequences/validation.ts:161:  input: unknown,
src/tools/video-editor/sequences/validation.ts:182:      addError(errors, `$.${key}`, 'unknown_field', 'Unknown top-level fields are not accepted.');
src/tools/video-editor/sequences/validation.ts:201:    addError(errors, '$.clipType', 'unknown_clip_type', 'clipType is not a trusted sequence type.');
src/tools/video-editor/sequences/validation.ts:245:        addError(errors, path, 'unknown_param', 'Unknown params are not accepted.');
src/tools/video-editor/sequences/validation.ts:287:  inputs: readonly unknown[],
src/tools/video-editor/effects/effectPromptTemplate.ts:15:  params?: Record<string, unknown>;
src/tools/video-editor/lib/perf-diagnostics.ts:10:    [PERF_DIAGNOSTICS_GLOBAL_FLAG]?: unknown;
src/tools/video-editor/lib/perf-diagnostics.ts:28:const logPerf = (message: string, ...args: unknown[]) => {
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.ts:52:function shouldRecover(error: unknown): boolean {
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.ts:108:      const fail = (error: unknown) => {
src/tools/video-editor/sequences/headlessRender.test.ts:16:      .mockResolvedValue(GoodComponent as unknown as Awaited<ReturnType<typeof compileSequenceModule.compileSequenceComponentAsync>>);
src/tools/video-editor/sequences/headlessRender.test.ts:36:      .mockResolvedValue(BrokenComponent as unknown as Awaited<ReturnType<typeof compileSequenceModule.compileSequenceComponentAsync>>);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:90:function makeJsonResult(data: unknown): CompileOnlyOutputResult {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:97:    hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:173:    expect(exec.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:213:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:249:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:269:  it('returns null for unknown formatId', () => {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:338:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:398:        (ctx as Record<string, unknown>).extensionId = 'hacked';
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:420:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:465:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:491:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:497:  it('returns null for unknown formatId', async () => {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:546:      ['application/x-custom', 'unknown'],
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:582:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:589:    expect(artifact.findings![1].reason).toBe('unknown'); // error → unknown blocker reason
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:732:    expect(result1!.hasBlockingErrors).toBe(result2!.hasBlockingErrors);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:770:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:808:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:843:      { data: new Uint8Array([0]), mimeType: 'application/octet-stream', filename: 'a.bin', hasBlockingErrors: true },
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:844:      { data: new TextEncoder().encode('hello'), mimeType: 'text/plain', filename: 'a.txt', hasBlockingErrors: false },
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1007:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1017:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1072:        handler: makeSyncHandler({ data: encoder.encode('co1'), mimeType: 'text/plain', filename: 'co1.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1077:        handler: makeSyncHandler({ data: encoder.encode('rd1'), mimeType: 'text/plain', filename: 'rd1.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1082:        handler: makeSyncHandler({ data: encoder.encode('co2'), mimeType: 'text/plain', filename: 'co2.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1248:        (ctx as Record<string, unknown>).timeline = null;
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1295:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1336:          hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1357:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1482:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1497:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/effects/compileEffect.tsx:19:function getEffectGlobals(): Record<string, unknown> {
src/tools/video-editor/lib/bulk-utils.ts:14:const getNestedComparisonKey = (value: unknown): string => {
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts:17:(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts:18:(globalThis as Record<string, unknown>).IDBKeyRange = IDBKeyRange;
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts:98:function makeSettingsSnapshot(extId: string, schemaVersion: number = 1, values: Record<string, unknown> = {}): ExtensionSettingsSnapshot {
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts:125:    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:70:  payload: Record<string, unknown>;
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:75:  detail?: Record<string, unknown>;
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:93:function shouldRecover(error: unknown): boolean {
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:156:      const fail = (error: unknown) => {
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:218:        const proposal: Record<string, unknown> = {
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:241:        result[record.proposalId] = proposal as unknown as ExtensionProposal;
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:384:    let base: Record<string, unknown>;
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:393:    } catch (error: unknown) {
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:410:    let parsed: Record<string, unknown>;
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:57:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:67:  detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:94:  assets?: readonly { key: string; metadata?: Record<string, unknown> }[],
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:101:    hasBlockers: !!(exportCtx?.blockers && exportCtx.blockers.length > 0),
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:114:    if (!exportCtx.blockers || exportCtx.blockers.length === 0) {
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:115:      analysis.missingFields.push('blockers list (empty or missing)');
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:176:        'Export tool invoked without export context. Provide outputFormatId, blockers, and contributionIds for complete planning.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:207:        `${toolId}.blockers-present`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:209:        'Render blockers are reported in the export context. These will be included in the plan.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:216:        `${toolId}.blockers-missing`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:218:        'No render blockers reported. If blockers exist, include them in the export context for accurate planning.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:367:  const findingsRecords: readonly Record<string, unknown>[] = findings.map(
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:390:      `assets=${analysis.hasAssets}, blockers=${analysis.hasBlockers}, ` +
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:399: * This tool focuses on identifying blockers and missing contributions
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:415:  if (exportCtx?.blockers && exportCtx.blockers.length > 0) {
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:416:    // Report existing blockers as error findings
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:417:    for (const blocker of exportCtx.blockers) {
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:418:      const blockerId = (blocker as Record<string, unknown>).id as string | undefined;
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:420:        (blocker as Record<string, unknown>).message as string | undefined;
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:440:      code: 'agent-tool/export-blockers-detected',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:441:      message: `${exportCtx.blockers.length} render blocker(s) detected in export context.`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:443:        blockerCount: exportCtx.blockers.length,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:444:        blockerIds: exportCtx.blockers.map(
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:445:          (b) => (b as Record<string, unknown>).id,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:452:        `${request.toolId}.no-blockers`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:454:        'No render blockers detected in export context.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:508:      (c) => !c.clipType || c.clipType === 'unknown',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:516:          `${emptyClips.length} clip(s) have unknown or missing clip types — these may cause export errors.`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:580:      hasBlockers: !!(exportCtx?.blockers && exportCtx.blockers.length > 0),
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:590:  const findingsRecords: readonly Record<string, unknown>[] = findings.map(
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:611:      `${findingsRecords.length} findings covering blockers, contributions, timeline, and assets.`,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:650:          'Reads explicit export context (blockers, contributions, timeline, assets) ' +
src/tools/video-editor/runtime/extensionMigration.ts:113:  readonly localSettings: Record<string, unknown>;
src/tools/video-editor/runtime/extensionMigration.ts:220: * Detect unsupported metadata gaps between a local source manifest and
src/tools/video-editor/runtime/extensionMigration.ts:495:export function readLocalSettings(extensionId: string): Record<string, unknown> {
src/tools/video-editor/runtime/extensionMigration.ts:497:  const settings: Record<string, unknown> = {};
src/tools/video-editor/runtime/extensionMigration.ts:569:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/extensionMigration.ts:806:      const manifestDefaults: Record<string, unknown> =
src/tools/video-editor/runtime/extensionPersistenceCache.ts:239: * Parse snapshot meta from an unknown value, returning `null` when the
src/tools/video-editor/runtime/extensionPersistenceCache.ts:242:function parseSnapshotMeta(raw: unknown): SnapshotMeta | null {
src/tools/video-editor/runtime/extensionPersistenceCache.ts:246:  const obj = raw as Record<string, unknown>;
src/tools/video-editor/runtime/extensionPersistenceCache.ts:377:        let parsed: unknown;
src/tools/video-editor/runtime/extensionPersistenceCache.ts:380:        } catch (parseError: unknown) {
src/tools/video-editor/runtime/extensionPersistenceCache.ts:413:        const obj = parsed as Record<string, unknown>;
src/tools/video-editor/runtime/extensionPersistenceCache.ts:472:            typeof (obj.lock as Record<string, unknown>).entries === 'object'
src/tools/video-editor/runtime/extensionPersistenceCache.ts:487:          } catch (migrationError: unknown) {
src/tools/video-editor/runtime/extensionPersistenceCache.ts:517:    } catch (error: unknown) {
src/tools/video-editor/runtime/extensionPersistenceCache.ts:692:    } catch (error: unknown) {
src/tools/video-editor/runtime/extensionPersistenceCache.ts:991:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/extensionPersistenceCache.ts:1102:    scope: ExtensionPersistenceScope = { userId: 'unknown', timelineId: 'unknown' },
src/tools/video-editor/runtime/extensionPersistenceCache.ts:1173:    detail?: Record<string, unknown>,
src/tools/video-editor/lib/managed-object-guard.test.ts:210:            app: { 'ext.unknown': { data: true } } as any,
src/tools/video-editor/lib/managed-object-guard.test.ts:214:      // extension not in requirements, so 'ext.unknown' is not a known extension
src/tools/video-editor/runtime/liveSteering.test.ts:104:  it('rejects unsupported params with explicit diagnostics instead of fallback hotness', () => {
src/tools/video-editor/runtime/liveSteering.test.ts:109:          path: 'params.unknown',
src/tools/video-editor/runtime/liveSteering.test.ts:118:    expect(result.diagnostics.some((d) => d.code === 'live/steering-unsupported-param')).toBe(true);
src/tools/video-editor/examples/extensions/flagship-local/index.ts:144:  params?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/flagship-local/index.ts:145:): Record<string, unknown> {
src/tools/video-editor/examples/extensions/flagship-local/index.ts:157:  const style: Record<string, unknown> = { clipPath };
src/tools/video-editor/examples/extensions/flagship-local/index.ts:448:      'Flagship Glow component effect registered (preview-only).',
src/tools/video-editor/examples/extensions/flagship-local/index.ts:464:      'Flagship Wipe transition renderer registered (preview-only).',
src/tools/video-editor/effects/entrances.tsx:9:  params?: Record<string, unknown>;
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:54: * Per SD2: trusted component clip types default to preview-only. Browser-export
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:66:    determinism: 'preview-only',
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:73:    determinism: contrib.allowBrowserExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:77:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:87:    determinism: contrib.allowWorkerExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:91:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:97:  const determinism: DeterminismStatus = 'preview-only';
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:114:  default?: number | string | boolean | Record<string, unknown>;
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:167:    detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:50:  params?: Record<string, unknown>;
src/tools/video-editor/runtime/commandPredicates.test.ts:305:  it('unknown target field resolves to null', () => {
src/tools/video-editor/runtime/commandPredicates.test.ts:321:  it('unprefixed unknown identifiers resolve to null', () => {
src/tools/video-editor/runtime/commandPredicates.test.ts:322:    expect(evaluatePredicate('unknownThing == null', baseContext())).toBe(true);
src/tools/video-editor/runtime/commandPredicates.test.ts:326:    expect(evaluatePredicate('unknownThing', baseContext())).toBe(false);
src/tools/video-editor/runtime/commandPredicates.test.ts:514:    // unknown identifier on the right, it'd still resolve to null (falsy).
src/tools/video-editor/runtime/commandPredicates.test.ts:516:    expect(evaluatePredicate('false && unknownThing', baseContext())).toBe(false);
src/tools/video-editor/runtime/commandPredicates.test.ts:547:    expect(evaluatePredicate('true || unknownThing', baseContext())).toBe(true);
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:21:(globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:22:(globalThis as Record<string, unknown>).IDBKeyRange = IDBKeyRange;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:51:function makeSnapshotBase(overrides: Record<string, unknown> = {}): Record<string, unknown> {
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:75:  baseOverrides: Record<string, unknown> = {},
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:76:  proposals: Record<string, unknown> = {},
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:105:    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:119:      (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:247:      const proposals: Record<string, unknown> = {};
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:603:    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1069:    const originalIndexedDB = (globalThis as Record<string, unknown>).indexedDB;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1070:    (globalThis as Record<string, unknown>).indexedDB = undefined;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1094:      (globalThis as Record<string, unknown>).indexedDB = originalIndexedDB;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1101:    const originalIndexedDB = (globalThis as Record<string, unknown>).indexedDB;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1102:    (globalThis as Record<string, unknown>).indexedDB = undefined;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1126:      (globalThis as Record<string, unknown>).indexedDB = originalIndexedDB;
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1130:    (globalThis as Record<string, unknown>).indexedDB = createFakeIndexedDB();
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:84:  createPreviewClip(channelId?: LiveChannelDescriptor): Record<string, unknown>;
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:92:  detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:98:function readString(input: unknown, fallback: string): string {
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:102:function readNumber(input: unknown, fallback: number): number {
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:180:}): Record<string, unknown> {
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:222:): Record<string, unknown> {
src/tools/video-editor/runtime/extensionRendererRegistry.ts:23:  readonly renderer: (...args: unknown[]) => DisposeHandle | void;
src/tools/video-editor/runtime/extensionRendererRegistry.ts:34:    ((...args: unknown[]) => DisposeHandle | void) | undefined;
src/tools/video-editor/runtime/extensionRendererRegistry.ts:56:    renderer: (...args: unknown[]) => DisposeHandle | void,
src/tools/video-editor/runtime/extensionRendererRegistry.ts:66:  ): ((...args: unknown[]) => DisposeHandle | void) | undefined;
src/tools/video-editor/runtime/extensionRendererRegistry.ts:88:  renderer: (...args: unknown[]) => DisposeHandle | void;
src/tools/video-editor/runtime/extensionRendererRegistry.ts:126:  const map = new Map<string, Map<string, (...args: unknown[]) => DisposeHandle | void>>();
src/tools/video-editor/runtime/extensionRendererRegistry.ts:143:  function ensureExtMap(extensionId: string): Map<string, (...args: unknown[]) => DisposeHandle | void> {
src/tools/video-editor/runtime/extensionRendererRegistry.ts:167:    renderer: (...args: unknown[]) => DisposeHandle | void,
src/tools/video-editor/runtime/extensionRendererRegistry.ts:214:  ): ((...args: unknown[]) => DisposeHandle | void) | undefined {
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:90:  /** Route names that have unknown support. */
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:91:  readonly unknownRoutes: readonly string[];
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:335:    // ---- Compute blockers --------------------------------------------------
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:381:    const effectUnknownRoutes = effectCapabilities.filter((capability) => capability.status === 'unknown').length;
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:387:      const unknownRoutes: string[] = [];
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:391:        } else if (cap.status === 'unknown') {
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:392:          unknownRoutes.push(cap.route);
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:395:      // Include records that have any blocked/unknown routes, or inactive/error status.
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:396:      if (blockedRoutes.length > 0 || unknownRoutes.length > 0 || record.status !== 'active') {
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:402:          unknownRoutes: Object.freeze(unknownRoutes),
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:581:            <span className="text-[10px] text-zinc-600">Export blockers</span>
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:588:          <div className="flex items-center gap-0.5" data-video-editor-planner-summary="blockers">
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:590:            <span className="text-[10px] text-zinc-600">Planner blockers</span>
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:599:            <span className="text-[10px] text-zinc-600">Render blockers</span>
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:645:          <div className="flex items-center gap-1" data-video-editor-effect-registry-summary="browser-export-blockers">
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:649:            <span className="text-[10px] text-zinc-600">Effect export blockers</span>
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:664:            <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="unknown">
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:668:              <span className="text-[10px] text-zinc-600">unknown routes</span>
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:703:                {detail.unknownRoutes.length > 0 && (
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:705:                    unknown: {detail.unknownRoutes.join(', ')}
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:136:    return 'unknown';
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:145:  const r = result as unknown as Record<string, unknown>;
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:276:  const [invokeInputs, setInvokeInputs] = useState<Record<string, Record<string, unknown>>>({});
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:307:    (toolId: string) => (name: string, value: unknown) => {
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:730:                                typeof (result as unknown as Record<string, unknown>).rationale === 'string' && (
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:733:                                      (result as unknown as Record<string, unknown>).rationale,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:736:                                          (result as unknown as Record<string, unknown>).rationale,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:739:                                          (result as unknown as Record<string, unknown>).rationale,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:746:                                  (result as unknown as Record<string, unknown>).affectedObjectIds,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:751:                                      (result as unknown as Record<string, unknown>)
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:759:                                  (result as unknown as Record<string, unknown>).sourceRefs,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:764:                                      (result as unknown as Record<string, unknown>)
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:765:                                        .sourceRefs as Array<Record<string, unknown>>
src/tools/video-editor/lib/effect-catalog.test.ts:20:function makeCapability(route: RenderRoute, status: 'supported' | 'blocked' | 'unknown' = 'supported'): RenderCapability {
src/tools/video-editor/lib/effect-catalog.test.ts:354:  it('preserves renderability for preview-only effects', () => {
src/tools/video-editor/lib/effect-catalog.test.ts:362:    const record = makeRegistryRecord({ effectId: 'preview-only', renderability });
src/tools/video-editor/runtime/exportGuard.ts:91:export interface ExportGuardResult {
src/tools/video-editor/runtime/exportGuard.ts:92:  /** Structured diagnostics for every unknown/unavailable ID found. */
src/tools/video-editor/runtime/exportGuard.ts:96:  /** Shared planner-compatible blockers that prevent browser export. */
src/tools/video-editor/runtime/exportGuard.ts:97:  readonly blockers: readonly RenderBlocker[];
src/tools/video-editor/runtime/exportGuard.ts:99:  readonly unknownClipTypes: readonly string[];
src/tools/video-editor/runtime/exportGuard.ts:101:  readonly unknownEffects: readonly string[];
src/tools/video-editor/runtime/exportGuard.ts:103:  readonly unknownTransitions: readonly string[];
src/tools/video-editor/runtime/exportGuard.ts:107:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/exportGuard.ts:256: * structured {@link ExportDiagnostic} entries for every unknown clip type,
src/tools/video-editor/runtime/exportGuard.ts:274:): ExportGuardResult {
src/tools/video-editor/runtime/exportGuard.ts:277:  const blockers: RenderBlocker[] = [];
src/tools/video-editor/runtime/exportGuard.ts:278:  const unknownClipTypes = new Set<string>();
src/tools/video-editor/runtime/exportGuard.ts:279:  const unknownEffects = new Set<string>();
src/tools/video-editor/runtime/exportGuard.ts:280:  const unknownTransitions = new Set<string>();
src/tools/video-editor/runtime/exportGuard.ts:283:    scanLiveBindingExportBlockers(config, diagnostics, findings, blockers);
src/tools/video-editor/runtime/exportGuard.ts:284:    scanTimelineShaderExportBlockers(config, diagnostics, findings, blockers);
src/tools/video-editor/runtime/exportGuard.ts:289:      scanClip(clip, allKnown, diagnostics, findings, blockers, unknownClipTypes, unknownEffects, unknownTransitions);
src/tools/video-editor/runtime/exportGuard.ts:296:  blockers.sort((a, b) => a.id.localeCompare(b.id));
src/tools/video-editor/runtime/exportGuard.ts:298:  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');
src/tools/video-editor/runtime/exportGuard.ts:303:    blockers: Object.freeze(blockers),
src/tools/video-editor/runtime/exportGuard.ts:304:    unknownClipTypes: Object.freeze([...unknownClipTypes].sort()),
src/tools/video-editor/runtime/exportGuard.ts:305:    unknownEffects: Object.freeze([...unknownEffects].sort()),
src/tools/video-editor/runtime/exportGuard.ts:306:    unknownTransitions: Object.freeze([...unknownTransitions].sort()),
src/tools/video-editor/runtime/exportGuard.ts:308:    hasBlockingErrors,
src/tools/video-editor/runtime/exportGuard.ts:316:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:324:    pushLiveBindingFindingAndBlocker(diagnostics, findings, blockers, record);
src/tools/video-editor/runtime/exportGuard.ts:337:  value: unknown,
src/tools/video-editor/runtime/exportGuard.ts:350:    && (value as Record<string, unknown>).scope === scope
src/tools/video-editor/runtime/exportGuard.ts:351:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/runtime/exportGuard.ts:352:    && typeof (value as Record<string, unknown>).extensionId === 'string'
src/tools/video-editor/runtime/exportGuard.ts:353:    && typeof (value as Record<string, unknown>).contributionId === 'string',
src/tools/video-editor/runtime/exportGuard.ts:361:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:366:    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:379:    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:391:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:437:    blockers.push({
src/tools/video-editor/runtime/exportGuard.ts:471:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:509:  blockers.push({
src/tools/video-editor/runtime/exportGuard.ts:526:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:527:  unknownClipTypes: Set<string>,
src/tools/video-editor/runtime/exportGuard.ts:528:  unknownEffects: Set<string>,
src/tools/video-editor/runtime/exportGuard.ts:529:  unknownTransitions: Set<string>,
src/tools/video-editor/runtime/exportGuard.ts:543:        scanClipTypeRecordRenderability(clip, clip.clipType, snapshotRecord, diagnostics, findings, blockers);
src/tools/video-editor/runtime/exportGuard.ts:550:          code: 'export/unknown-clip-type',
src/tools/video-editor/runtime/exportGuard.ts:558:          unknownClipTypes.add(clip.clipType);
src/tools/video-editor/runtime/exportGuard.ts:560:          // Emit shared blocker vocabulary for truly unknown clip types.
src/tools/video-editor/runtime/exportGuard.ts:561:          pushClipTypeFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:575:  scanEffect(clip, 'entrance', known, diagnostics, findings, blockers, unknownEffects);
src/tools/video-editor/runtime/exportGuard.ts:578:  scanEffect(clip, 'exit', known, diagnostics, findings, blockers, unknownEffects);
src/tools/video-editor/runtime/exportGuard.ts:581:  scanEffect(clip, 'continuous', known, diagnostics, findings, blockers, unknownEffects);
src/tools/video-editor/runtime/exportGuard.ts:594:        code: 'export/unknown-transition-type',
src/tools/video-editor/runtime/exportGuard.ts:602:        unknownTransitions.add(tType);
src/tools/video-editor/runtime/exportGuard.ts:603:        pushTransitionFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:617:      scanTransitionRecordRenderability(clip, tType, snapshotRecord, diagnostics, findings, blockers);
src/tools/video-editor/runtime/exportGuard.ts:637:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:638:  unknownEffects: Set<string>,
src/tools/video-editor/runtime/exportGuard.ts:647:  if (typeof effect === 'object' && 'type' in effect && typeof (effect as Record<string, unknown>).type === 'string') {
src/tools/video-editor/runtime/exportGuard.ts:648:    effectType = (effect as Record<string, unknown>).type as string;
src/tools/video-editor/runtime/exportGuard.ts:662:      code: 'export/unknown-effect-type',
src/tools/video-editor/runtime/exportGuard.ts:668:      unknownEffects.add(effectType);
src/tools/video-editor/runtime/exportGuard.ts:669:      pushEffectFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:683:    scanEffectRecordRenderability(clip, slot, effectType, snapshotRecord, diagnostics, findings, blockers);
src/tools/video-editor/runtime/exportGuard.ts:694:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:714:      pushEffectFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:742:    if (capability.status === 'unknown') {
src/tools/video-editor/runtime/exportGuard.ts:745:        ?? `${capitalise(slot)} effect "${effectType}" has unknown support for ${route}.`;
src/tools/video-editor/runtime/exportGuard.ts:748:        code: 'export/unknown-route-support',
src/tools/video-editor/runtime/exportGuard.ts:761:        id: `export.effect.${clip.id}.${slot}.${effectType}.${route}.unknown`,
src/tools/video-editor/runtime/exportGuard.ts:764:        reason: 'unknown',
src/tools/video-editor/runtime/exportGuard.ts:780:    const reason = capability.blockerReason ?? firstRouteBlockerReason(record, route) ?? 'route-unsupported';
src/tools/video-editor/runtime/exportGuard.ts:798:    pushEffectFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:812:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/runtime/exportGuard.ts:817:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:829:  const detail: Record<string, unknown> = {
src/tools/video-editor/runtime/exportGuard.ts:848:  blockers.push({
src/tools/video-editor/runtime/exportGuard.ts:869:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:888:      pushTransitionFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:918:            blockerReason: 'route-unsupported',
src/tools/video-editor/runtime/exportGuard.ts:922:        pushTransitionFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:923:          id: `export.transition.${clip.id}.${transitionType}.${route}.route-unsupported`,
src/tools/video-editor/runtime/exportGuard.ts:924:          reason: 'route-unsupported',
src/tools/video-editor/runtime/exportGuard.ts:937:    if (capability.status === 'unknown') {
src/tools/video-editor/runtime/exportGuard.ts:939:        ?? `Transition "${transitionType}" has unknown support for ${route}.`;
src/tools/video-editor/runtime/exportGuard.ts:942:        code: 'export/unknown-route-support',
src/tools/video-editor/runtime/exportGuard.ts:955:        id: `export.transition.${clip.id}.${transitionType}.${route}.unknown`,
src/tools/video-editor/runtime/exportGuard.ts:958:        reason: 'unknown',
src/tools/video-editor/runtime/exportGuard.ts:973:    const reason = capability.blockerReason ?? firstTransitionRouteBlockerReason(record, route) ?? 'route-unsupported';
src/tools/video-editor/runtime/exportGuard.ts:991:    pushTransitionFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:1004:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/runtime/exportGuard.ts:1009:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:1020:  const detail: Record<string, unknown> = {
src/tools/video-editor/runtime/exportGuard.ts:1038:  blockers.push({
src/tools/video-editor/runtime/exportGuard.ts:1059:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:1079:      pushClipTypeFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:1106:    if (capability.status === 'unknown') {
src/tools/video-editor/runtime/exportGuard.ts:1109:        ?? `Clip type "${clipType}" has unknown support for ${route}.`;
src/tools/video-editor/runtime/exportGuard.ts:1112:        code: 'export/unknown-route-support',
src/tools/video-editor/runtime/exportGuard.ts:1125:        id: `export.clipType.${clip.id}.${clipType}.${route}.unknown`,
src/tools/video-editor/runtime/exportGuard.ts:1128:        reason: 'unknown',
src/tools/video-editor/runtime/exportGuard.ts:1143:    const reason = capability.blockerReason ?? firstClipTypeRouteBlockerReason(record, route) ?? 'route-unsupported';
src/tools/video-editor/runtime/exportGuard.ts:1161:    pushClipTypeFindingAndBlocker(findings, blockers, {
src/tools/video-editor/runtime/exportGuard.ts:1174:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/runtime/exportGuard.ts:1179:  blockers: RenderBlocker[],
src/tools/video-editor/runtime/exportGuard.ts:1190:  const detail: Record<string, unknown> = {
src/tools/video-editor/runtime/exportGuard.ts:1208:  blockers.push({
src/tools/video-editor/effects/index.tsx:153:  params?: Record<string, unknown>;
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:113:function makeRequest(input: Record<string, unknown> = {}): AgentToolInvocationRequest {
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:134:  return (result as unknown as { replacements: any[] }).replacements;
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:183:  input: Record<string, unknown> = {},
src/tools/video-editor/lib/timeline-mutation-engine.ts:48:    cause: unknown;
src/tools/video-editor/lib/timeline-mutation-engine.ts:64:const normalizeMutationError = (error: unknown): TimelineMutationFailure['error'] => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:81:  resolveAvailableClipType: () => ({ status: 'unknown' }),
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:34:    provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:47:      Lightbox: (() => null) as unknown as VideoEditorRuntimeContextValue['mediaLightbox']['Lightbox'],
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:93:      effectId: 'preview-only-status-effect',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:101:        determinism: 'preview-only',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:103:          { route: 'preview', status: 'supported', determinism: 'preview-only' },
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:107:            determinism: 'preview-only',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:108:            blockerReason: 'preview-only',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:353:      code: 'export/unknown-clip-type',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:374:    expect(inventory!.exportBlockers[0].code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:907:      code: 'export/unknown-clip-type',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:920:    expect(screen.getByText('Export blockers')).toBeDefined();
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:946:    expect(screen.getByText('Render blockers')).toBeDefined();
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:949:  it('shows provider effect registry counts, renderability summaries, and planner/export blockers', async () => {
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:955:      code: 'export/effect-preview-only',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:963:      code: 'planner/browser-export/preview-only',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:983:      expect(screen.getByText('Effect export blockers')).toBeDefined();
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:986:      expect(screen.getByText('Export blockers')).toBeDefined();
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:987:      expect(screen.getByText('Planner blockers')).toBeDefined();
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:991:    expect(document.querySelector('[data-video-editor-effect-registry-summary="browser-export-blockers"]')?.textContent).toContain('1');
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:994:    expect(document.querySelector('[data-video-editor-planner-summary="blockers"]')?.textContent).toContain('1');
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:168:        ((progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:238:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:254:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:270:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:286:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:302:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:307:        const style: Record<string, unknown> = {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:325:      const renderer = (progress: number, params?: Record<string, unknown>) => {
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:330:        const style: Record<string, unknown> = {
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.test.tsx:309:        badField: { type: 'unsupported' as any, title: 'Bad' },
src/tools/video-editor/runtime/liveBake.ts:341:function numberFromUnknown(value: unknown): number | undefined {
src/tools/video-editor/runtime/liveBake.ts:468:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/liveBake.ts:479:function serializeSampleForHash(sample: LiveSample): unknown {
src/tools/video-editor/runtime/liveBake.ts:490:function serializeDataForHash(data: LiveSample['frame']['data']): unknown {
src/tools/video-editor/runtime/liveBake.ts:500:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/runtime/liveBake.ts:504:function stableHash(value: unknown): string {
src/tools/video-editor/runtime/liveBake.ts:514:function sortObject(value: unknown): unknown {
src/tools/video-editor/runtime/liveBake.ts:519:    const record = value as Record<string, unknown>;
src/tools/video-editor/runtime/liveBake.ts:520:    return Object.keys(record).sort().reduce<Record<string, unknown>>((acc, key) => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:81:  resolveAvailableClipType: () => ({ status: 'unknown' }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:118:      : 'preview-only',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:124:        determinism: browserExport === 'supported' ? 'deterministic' : 'preview-only',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:125:        ...(browserExport === 'blocked' ? { blockerReason: 'preview-only' } : {}),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:130:        determinism: workerExport === 'supported' ? 'deterministic' : 'preview-only',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:131:        ...(workerExport === 'blocked' ? { blockerReason: 'preview-only' } : {}),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:320:  it('labels selected preview-only shader entries with a Preview only badge', () => {
src/tools/video-editor/components/CueListEditor.tsx:10:  readonly fields?: Record<string, unknown>;
src/tools/video-editor/components/CueListEditor.tsx:20:function createCue(id: string, fields: Record<string, unknown>): EditableCue {
src/tools/video-editor/components/CueListEditor.tsx:31:  const updateCueField = (index: number, name: string, value: unknown) => {
src/tools/video-editor/runtime/renderPlanner.test.ts:2:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/runtime/renderPlanner.test.ts:149:    blockers: [],
src/tools/video-editor/runtime/renderPlanner.test.ts:219:    blockers: [],
src/tools/video-editor/runtime/renderPlanner.test.ts:282:    blockers: [],
src/tools/video-editor/runtime/renderPlanner.test.ts:302:describe('planRender', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:303:  it('derives route blockers from a public TimelineSnapshot without registry inputs', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:304:    const result = planRender({ snapshot: snapshotWithLiveBinding() });
src/tools/video-editor/runtime/renderPlanner.test.ts:306:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:307:    expect(result.canWorkerExport).toBe(true);
src/tools/video-editor/runtime/renderPlanner.test.ts:314:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:324:  it('keeps findings, blockers, next actions, and route plans deterministic', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:329:      reason: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:332:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:338:          determinism: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:341:            fit: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:342:            reason: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:358:      'b-requirement.worker-export.unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:361:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/renderPlanner.test.ts:370:      determinism: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:377:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:399:    expect(result.canWorkerExport).toBe(true);
src/tools/video-editor/runtime/renderPlanner.test.ts:400:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/renderPlanner.test.ts:438:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:476:    expect(result.canBrowserExport).toBe(true);
src/tools/video-editor/runtime/renderPlanner.test.ts:477:    expect(result.canWorkerExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:488:      blockers: [
src/tools/video-editor/runtime/renderPlanner.test.ts:519:    const result = planRender({ snapshot: snapshotWithShaders() });
src/tools/video-editor/runtime/renderPlanner.test.ts:521:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:522:    expect(result.canWorkerExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:523:    expect(result.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/renderPlanner.test.ts:548:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:574:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:575:    expect(result.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/renderPlanner.test.ts:578:        reason: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:585:        reason: 'unknown',
src/tools/video-editor/runtime/renderPlanner.test.ts:591:    expect(result.blockers).not.toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/renderPlanner.test.ts:602:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:615:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:616:    expect(result.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/renderPlanner.test.ts:626:    expect(result.blockers).not.toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/renderPlanner.test.ts:670:  it('plans normalized render-dependent output formats as process-dependent route blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:671:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:677:    expect(result.canBrowserExport).toBe(true);
src/tools/video-editor/runtime/renderPlanner.test.ts:698:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:712:  it('surfaces missing requested output formats as structured request blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:713:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:718:    expect(result.canBrowserExport).toBe(true);
src/tools/video-editor/runtime/renderPlanner.test.ts:723:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:734:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:746:      blockers: [
src/tools/video-editor/runtime/renderPlanner.test.ts:748:          id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.route-unsupported',
src/tools/video-editor/runtime/renderPlanner.test.ts:749:          reason: 'route-unsupported',
src/tools/video-editor/runtime/renderPlanner.test.ts:759:  it('converts materialize-on-export live material refs into browser-export blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:768:    const result = planRender({ materialRefs: [materialRef] });
src/tools/video-editor/runtime/renderPlanner.test.ts:770:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:771:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:782:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:795:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:796:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:808:    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-resolved')).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:836:    const ready = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:842:    const degraded = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:860:    expect(ready.blockers).toEqual([]);
src/tools/video-editor/runtime/renderPlanner.test.ts:886:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:940:    expect(result.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:941:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/renderPlanner.test.ts:953:    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-beauty')).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:954:    expect(result.blockers.some((blocker) => blocker.id.includes('thumbnail-pass'))).toBe(false);
src/tools/video-editor/runtime/extensionLoader.test.ts:114:function rawExtension(manifest: Record<string, unknown>): ReighExtension {
src/tools/video-editor/runtime/extensionLoader.test.ts:115:  return { manifest: manifest as unknown as ExtensionManifest } as ReighExtension;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:31:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:77:  readonly uniformValues: Map<string, unknown>;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:103:    uniformValues: new Map<string, unknown>(),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:203:  return gl as unknown as WebGLRenderingContext & { readonly __state: MockWebGLState };
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:366:          code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:378:        code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:386:  it('materializes timeline metadata, inspector edits, deterministic browser preview output, and planner export blockers', () => {
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:489:    const planner = planRender({ snapshot: makeShaderSnapshot(config) });
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:490:    expect(planner.canBrowserExport).toBe(false);
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:491:    expect(planner.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/lib/timeline-data.test.ts:10:import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';
src/tools/video-editor/lib/timeline-data.test.ts:254:    expect(decideRenderRoute(serialized)).toMatchObject({
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:34:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:240:          code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:252:        code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:269:        errorDiagnostics: [expect.objectContaining({ code: 'shader/uniform-unsupported' })],
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:276:  it('materializes timeline metadata defaults, inspector edits, preview input, and planner export blockers for the canary shader', () => {
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:357:    const planner = planRender({ snapshot: makeShaderSnapshot(clip) });
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:358:    expect(planner.canBrowserExport).toBe(false);
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:359:    expect(planner.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:97:    // between available/unavailable/unknown render-component states.
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:106:      return { status: 'unknown' as const, clipType };
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:445:      id: 'preview-only-b',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:459:      continuous: { type: 'custom:preview-only-b', intensity: 0.5 },
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:524:  it('shows after-apply "Preview only" banner for preview-only effects', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:526:      id: 'preview-only',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:540:      continuous: { type: 'custom:preview-only', intensity: 0.5 },
src/tools/video-editor/runtime/renderability.ts:6: * snapshots, export guards produce findings/blockers, and later planners can
src/tools/video-editor/runtime/renderability.ts:26: * - `preview-only`: usable only for interactive preview, not authoritative export.
src/tools/video-editor/runtime/renderability.ts:29: * - `unknown`: insufficient metadata; guards should stay conservative.
src/tools/video-editor/runtime/renderability.ts:33:  | 'preview-only'
src/tools/video-editor/runtime/renderability.ts:36:  | 'unknown';
src/tools/video-editor/runtime/renderability.ts:41:  'preview-only',
src/tools/video-editor/runtime/renderability.ts:44:  'unknown',
src/tools/video-editor/runtime/renderability.ts:51:  | 'route-unsupported'
src/tools/video-editor/runtime/renderability.ts:52:  | 'preview-only'
src/tools/video-editor/runtime/renderability.ts:58:  | 'unknown';
src/tools/video-editor/runtime/renderability.ts:63:  'route-unsupported',
src/tools/video-editor/runtime/renderability.ts:64:  'preview-only',
src/tools/video-editor/runtime/renderability.ts:70:  'unknown',
src/tools/video-editor/runtime/renderability.ts:74:export type RenderCapabilityStatus = 'supported' | 'blocked' | 'unknown';
src/tools/video-editor/runtime/renderability.ts:90:  readonly blockers?: readonly RenderBlocker[];
src/tools/video-editor/runtime/renderability.ts:106:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:146:  | 'unknown';
src/tools/video-editor/runtime/renderability.ts:189:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:259:  readonly blockers?: readonly RenderBlocker[];
src/tools/video-editor/runtime/renderability.ts:288:  readonly provenance?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:313:  readonly provenance?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:318:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:341:  readonly provenance?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:346:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:468:  readonly provenance?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:472:  readonly metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:486:    detail?: Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:489:  readonly hasBlockingErrors?: boolean;
src/tools/video-editor/runtime/renderability.ts:509:      reason: diag.severity === 'error' ? 'unknown' : undefined,
src/tools/video-editor/runtime/renderability.ts:520:    mediaKind: 'unknown',
src/tools/video-editor/runtime/renderability.ts:590:  return 'unknown';
src/tools/video-editor/runtime/renderability.ts:615:function toStableJsonValue(value: unknown): unknown {
src/tools/video-editor/runtime/renderability.ts:622:  const record = value as Record<string, unknown>;
src/tools/video-editor/runtime/renderability.ts:623:  const stableRecord: Record<string, unknown> = {};
src/tools/video-editor/runtime/liveDataRegistry.ts:128:  metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/liveDataRegistry.ts:149:  metadata?: Record<string, unknown>;
src/tools/video-editor/runtime/liveDataRegistry.ts:310:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/liveDataRegistry.ts:530:    metadata?: Record<string, unknown>,
src/tools/video-editor/runtime/renderPlanner.ts:66:  readonly blockers: readonly RenderBlocker[];
src/tools/video-editor/runtime/renderPlanner.ts:76:  readonly blockers: readonly RenderBlocker[];
src/tools/video-editor/runtime/renderPlanner.ts:77:  readonly unknownClipTypes: readonly string[];
src/tools/video-editor/runtime/renderPlanner.ts:78:  readonly unknownEffects: readonly string[];
src/tools/video-editor/runtime/renderPlanner.ts:79:  readonly unknownTransitions: readonly string[];
src/tools/video-editor/runtime/renderPlanner.ts:85:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/renderPlanner.ts:91:  readonly blockers: readonly RenderBlocker[];
src/tools/video-editor/runtime/renderPlanner.ts:96:  readonly canBrowserExport: boolean;
src/tools/video-editor/runtime/renderPlanner.ts:97:  readonly canWorkerExport: boolean;
src/tools/video-editor/runtime/renderPlanner.ts:102:  blockers: RenderBlocker[];
src/tools/video-editor/runtime/renderPlanner.ts:118:  'preview-only': 1,
src/tools/video-editor/runtime/renderPlanner.ts:121:  unknown: 4,
src/tools/video-editor/runtime/renderPlanner.ts:127:    blockers: [],
src/tools/video-editor/runtime/renderPlanner.ts:185:function sortedBlockers(blockers: readonly RenderBlocker[]): readonly RenderBlocker[] {
src/tools/video-editor/runtime/renderPlanner.ts:187:    dedupeById(blockers.map(freezeBlocker)).sort((a, b) => a.id.localeCompare(b.id)),
src/tools/video-editor/runtime/renderPlanner.ts:229:    case 'preview-only':
src/tools/video-editor/runtime/renderPlanner.ts:232:    case 'unknown':
src/tools/video-editor/runtime/renderPlanner.ts:235:      return 'unknown';
src/tools/video-editor/runtime/renderPlanner.ts:248:    if (blocker) acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:255:  if (blocker) acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:358:      processState: processStatus?.state ?? 'unknown',
src/tools/video-editor/runtime/renderPlanner.ts:416:  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
src/tools/video-editor/runtime/renderPlanner.ts:450:        reason: 'unknown',
src/tools/video-editor/runtime/renderPlanner.ts:531:  if (routeBlocker) acc.blockers.push(routeBlocker);
src/tools/video-editor/runtime/renderPlanner.ts:557:      processState: status?.state ?? 'unknown',
src/tools/video-editor/runtime/renderPlanner.ts:588:      processState: status?.state ?? 'unknown',
src/tools/video-editor/runtime/renderPlanner.ts:662:        acc.blockers.push(routeBlocker);
src/tools/video-editor/runtime/renderPlanner.ts:677:        acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:684:  for (const blocker of outputFormat.blockers) {
src/tools/video-editor/runtime/renderPlanner.ts:707:      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
src/tools/video-editor/runtime/renderPlanner.ts:710:      reason: 'route-unsupported',
src/tools/video-editor/runtime/renderPlanner.ts:722:    acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:733:  for (const blocker of process.blockers) {
src/tools/video-editor/runtime/renderPlanner.ts:805:  acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:839:      acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:870:  blockers: readonly RenderBlocker[],
src/tools/video-editor/runtime/renderPlanner.ts:873:  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
src/tools/video-editor/runtime/renderPlanner.ts:894:    blockers: Object.freeze(routeBlockers),
src/tools/video-editor/runtime/renderPlanner.ts:904:  blockers: readonly RenderBlocker[],
src/tools/video-editor/runtime/renderPlanner.ts:909:    blockers,
src/tools/video-editor/runtime/renderPlanner.ts:910:    unknownClipTypes: Object.freeze([]),
src/tools/video-editor/runtime/renderPlanner.ts:911:    unknownEffects: Object.freeze([]),
src/tools/video-editor/runtime/renderPlanner.ts:912:    unknownTransitions: Object.freeze([]),
src/tools/video-editor/runtime/renderPlanner.ts:914:    hasBlockingErrors: blockers.length > 0,
src/tools/video-editor/runtime/renderPlanner.ts:918:export function planRender(input: RenderPlannerInput): RenderPlannerResult {
src/tools/video-editor/runtime/renderPlanner.ts:981:    acc.blockers.push(blocker);
src/tools/video-editor/runtime/renderPlanner.ts:985:  const blockers = sortedBlockers([
src/tools/video-editor/runtime/renderPlanner.ts:986:    ...acc.blockers,
src/tools/video-editor/runtime/renderPlanner.ts:989:  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
src/tools/video-editor/runtime/renderPlanner.ts:1000:    guard: emptyGuard(findings, blockers),
src/tools/video-editor/runtime/renderPlanner.ts:1002:    blockers,
src/tools/video-editor/runtime/renderPlanner.ts:1007:    canBrowserExport: !browserRoute?.blocked,
src/tools/video-editor/runtime/renderPlanner.ts:1008:    canWorkerExport: !workerRoute?.blocked,
src/tools/video-editor/runtime/extensionRendererRegistry.test.ts:50:  it('resolve returns undefined for unknown extension or render ID', () => {
src/tools/video-editor/runtime/extensionRendererRegistry.test.ts:134:  it('unregister is a no-op for unknown bindings', () => {
src/tools/video-editor/runtime/extensionRendererRegistry.test.ts:184:  it('unregisterAll for unknown extension is a no-op', () => {
src/tools/video-editor/runtime/shaderRegistrationService.ts:60:      determinism: 'preview-only',
src/tools/video-editor/runtime/shaderRegistrationService.ts:69:      determinism: materializerSupportsRoute ? 'process-dependent' : 'preview-only',
src/tools/video-editor/runtime/shaderRegistrationService.ts:75:              `Shader "${contribution.shaderId}" is preview-only until extension "${extensionId}" ` +
src/tools/video-editor/runtime/shaderRegistrationService.ts:84:    determinism: routes.size > 0 ? 'process-dependent' : 'preview-only',
src/tools/video-editor/runtime/shaderRegistrationService.ts:110:    detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:59:  AbsoluteFill: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:62:  Sequence: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:85:    ThemeProvider: ({ children }: React.PropsWithChildren<{ value: unknown }>) => (
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:128:  const stream = { getTracks: vi.fn(() => [track]) } as unknown as MediaStream;
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:138:    .mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:249:  } as unknown as VideoEditorRuntimeContextValue;
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:252:function makeConfig(clip: Record<string, unknown>): ResolvedTimelineConfig {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:261:function makeLiveMediaConfig(binding: Record<string, unknown>): ResolvedTimelineConfig {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:285:  return (result as unknown as { replacements: any[] }).replacements;
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:350:function makeRequest(input: Record<string, unknown>): AgentToolInvocationRequest {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:362:  input: Record<string, unknown>,
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:444:    expect(blocked.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:460:    expect(cleared.hasBlockingErrors).toBe(false);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:542:    expect(liveGuard.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:565:    expect(partialGuard.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:594:    expect(fullGuard.hasBlockingErrors).toBe(false);
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:39:      registry: unknown,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:40:      context: unknown,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:41:      selection: unknown,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:219:    render: (_ctx: unknown, _sel: unknown) => <div data-testid={`section-${id}`}>{id}</div>,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:249:      (_registry: unknown, _context: unknown, _selection: unknown) => createInspectorContributions(),
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:330:      (_registry: unknown, _context: unknown, selection: unknown) => {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:337:            render: (_ctx: unknown, _sel: unknown) => (
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:346:            render: (_ctx: unknown, _sel: unknown) => (
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:478:    getInspectorContributionsMock.mockImplementation((_r: unknown, _c: unknown, sel: unknown) => {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:484:        render: (_ctx: unknown, _sel: unknown) => (
src/tools/video-editor/runtime/agentToolContracts.ts:61:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolContracts.ts:71:    (diagnostic as unknown as Record<string, unknown>).detail = detail;
src/tools/video-editor/runtime/agentToolContracts.ts:82:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolContracts.ts:93:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolContracts.ts:104:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolContracts.ts:116:export function isToolResultFamily(value: unknown): value is ToolResultFamily {
src/tools/video-editor/runtime/agentToolContracts.ts:134:  property: unknown,
src/tools/video-editor/runtime/agentToolContracts.ts:151:  const prop = property as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:267:        const nestedProps = prop.properties as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:326:  schema: unknown,
src/tools/video-editor/runtime/agentToolContracts.ts:346:  const s = schema as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:394:      const props = s.properties as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:413:      const requiredArray = s.required as unknown[];
src/tools/video-editor/runtime/agentToolContracts.ts:454:export function validateToolResult(result: unknown): ToolResultDiagnostic[] {
src/tools/video-editor/runtime/agentToolContracts.ts:468:  const r = result as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:485:        'unsupported-result-family',
src/tools/video-editor/runtime/agentToolContracts.ts:519:          const patch = (r.patches as unknown[])[i];
src/tools/video-editor/runtime/agentToolContracts.ts:529:            const p = patch as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:602:        const session = r.session as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:794:      for (let i = 0; i < (r.diagnostics as unknown[]).length; i++) {
src/tools/video-editor/runtime/agentToolContracts.ts:795:        const d = (r.diagnostics as unknown[])[i];
src/tools/video-editor/runtime/agentToolContracts.ts:805:          const diag = d as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:851:  result: unknown,
src/tools/video-editor/runtime/agentToolContracts.ts:854:  const r = result as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.ts:866:  result: unknown,
src/tools/video-editor/hooks/useRenderState.test.tsx:31:  decideRenderRoute: (timeline: ResolvedTimelineConfig | null | undefined) => {
src/tools/video-editor/hooks/useRenderState.test.tsx:35:        route: 'preview-only',
src/tools/video-editor/hooks/useRenderState.test.tsx:156:                blockerReason: 'route-unsupported',
src/tools/video-editor/hooks/useRenderState.test.tsx:199:    blockers: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:200:    unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:201:    unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:202:    unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:208:    hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:225:    _builtIn: unknown,
src/tools/video-editor/hooks/useRenderState.test.tsx:226:    _extIds: unknown,
src/tools/video-editor/hooks/useRenderState.test.tsx:238:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:239:            message: `Continuous effect "${effectId ?? 'unknown'}" is not recognised. Ensure the required extension or registry is installed.`,
src/tools/video-editor/hooks/useRenderState.test.tsx:243:        unknownEffects: effectId ? [effectId] : [],
src/tools/video-editor/hooks/useRenderState.test.tsx:244:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:264:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:292:      unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:293:      unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:294:      unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:300:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:504:        blockers: [
src/tools/video-editor/hooks/useRenderState.test.tsx:520:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:619:    it('blocks render when export guard finds blocking errors (truly unknown clip type)', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:637:            code: 'export/unknown-clip-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:642:        unknownClipTypes: ['alien-format'],
src/tools/video-editor/hooks/useRenderState.test.tsx:643:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:644:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:650:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:699:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:704:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:705:        unknownEffects: ['crazy-spin'],
src/tools/video-editor/hooks/useRenderState.test.tsx:706:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:712:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:754:            code: 'export/unknown-clip-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:760:            code: 'export/unknown-transition-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:766:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:771:        unknownClipTypes: ['alien-format'],
src/tools/video-editor/hooks/useRenderState.test.tsx:772:        unknownEffects: ['hyperspace'],
src/tools/video-editor/hooks/useRenderState.test.tsx:773:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:779:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:804:      expect(log).toContain('[export/unknown-clip-type]');
src/tools/video-editor/hooks/useRenderState.test.tsx:805:      expect(log).toContain('[export/unknown-effect-type]');
src/tools/video-editor/hooks/useRenderState.test.tsx:807:      expect(log).toContain('[export/unknown-transition-type]');
src/tools/video-editor/hooks/useRenderState.test.tsx:825:      } as unknown as VideoEditorRuntimeContextValue;
src/tools/video-editor/hooks/useRenderState.test.tsx:837:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:842:        blockers: [
src/tools/video-editor/hooks/useRenderState.test.tsx:853:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:878:    it('uses planner blockers as the canonical render readiness decision', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:894:        blockers: [
src/tools/video-editor/hooks/useRenderState.test.tsx:903:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:952:            code: 'export/unknown-transition-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:957:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:958:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:959:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:965:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1008:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1009:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1010:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1016:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1042:    it('preserves existing preview-only block when guard passes', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:1058:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1059:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1060:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1066:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1089:      // Guard passed but preview-only blocked it — native routing preserved
src/tools/video-editor/hooks/useRenderState.test.tsx:1122:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1123:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1124:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1130:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1167:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1168:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1169:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1175:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1329:    it('preserves preview-only routing with no extension runtime (identical to pre-extension behavior)', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:1350:      // Guard skipped, preview-only block preserved
src/tools/video-editor/hooks/useRenderState.test.tsx:1383:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1384:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1385:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1391:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1455:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:1460:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1461:        unknownEffects: ['missing-effect'],
src/tools/video-editor/hooks/useRenderState.test.tsx:1462:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1468:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:1524:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:1529:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1530:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1531:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1537:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1603:            code: 'export/unknown-effect-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:1609:            code: 'export/unknown-transition-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:1614:        unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1615:        unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1616:        unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1622:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1684:        makeTimelineWithEffect('preview-only-provider-effect'),
src/tools/video-editor/hooks/useRenderState.test.tsx:1691:        capturedRegistry!.register(makeEffectRecord('preview-only-provider-effect', 'blocked'));
src/tools/video-editor/hooks/useRenderState.test.tsx:1700:      expect(snapshot.get('preview-only-provider-effect')?.renderability.capabilities).toEqual(
src/tools/video-editor/hooks/useRenderState.test.tsx:1780:      unknownClipTypes: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1781:      unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1782:      unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1788:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1862:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1902:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2048:  it('rejects unknown format ID with planner missing-contribution error', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:2142:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2217:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2246:  it('includes blocking errors note in export log when hasBlockingErrors is true', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:2256:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2394:          code: 'export/unknown-clip-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:2399:      unknownClipTypes: ['alien-format'],
src/tools/video-editor/hooks/useRenderState.test.tsx:2400:      unknownEffects: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:2401:      unknownTransitions: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:2403:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2517:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2563:          code: 'export/unknown-clip-type',
src/tools/video-editor/hooks/useRenderState.test.tsx:2568:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2610:    } as unknown as VideoEditorRuntimeContextValue;
src/tools/video-editor/hooks/useRenderState.test.tsx:2629:      blockers: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2640:      hasBlockingErrors: true,
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:44:  } as unknown as MediaStream;
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:55:    .mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:147:function makeConfig(clip: Record<string, unknown>): ResolvedTimelineConfig {
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:172:  it('publishes unsupported diagnostics and cleans the source when getUserMedia is unavailable', async () => {
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:187:        code: 'live-webcam/unsupported',
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:329:    expect(exportScan.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime-components/compileWithGlobals.ts:29:  globals: Record<string, unknown>,
src/tools/video-editor/runtime-components/compileWithGlobals.ts:51:      ...args: unknown[]
src/tools/video-editor/runtime-components/compileWithGlobals.ts:52:    ) => unknown;
src/tools/video-editor/runtime-components/compileWithGlobals.ts:76:  globals: Record<string, unknown>,
src/tools/video-editor/runtime-components/compileWithGlobals.ts:87:  globals: Record<string, unknown>,
src/tools/video-editor/runtime/extensionLifecycle.ts:172:    detail?: Record<string, unknown>,
src/tools/video-editor/browser/hooks.test.tsx:85:  useTimelineDataSelector: (selector: (state: typeof timelineState) => unknown) => selector(timelineState),
src/tools/video-editor/browser/hooks.test.tsx:86:  useTimelineOpsSelector: (selector: (state: typeof opsState) => unknown) => selector(opsState),
src/tools/video-editor/browser/hooks.test.tsx:87:  useTimelineChromeSelector: (selector: (state: typeof chromeState) => unknown) => selector(chromeState),
src/tools/video-editor/browser/hooks.test.tsx:88:  useTimelinePlaybackSelector: (selector: (state: { currentTime: number; previewRef: typeof previewRef }) => unknown) => (
src/tools/video-editor/runtime/extensionLoader.ts:856:    for (const key of Object.keys(value as Record<string, unknown>)) {
src/tools/video-editor/runtime/extensionLoader.ts:857:      const v = (value as Record<string, unknown>)[key];
src/tools/video-editor/runtime/extensionLoader.ts:1080:        const extId = (ext.manifest.id as string) || '(unknown)';
src/tools/video-editor/runtime/extensionLoader.ts:1083:        const raw: Record<string, unknown> = {
src/tools/video-editor/runtime/extensionLoader.ts:1084:          manifest: ext.manifest as unknown as Record<string, unknown>,
src/tools/video-editor/runtime/extensionLoader.ts:1171:      label: (manifest.label as string) || (manifest.id as string) || '(unknown)',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:6: * metadata, registry diagnostics, preview-only renderability, picker metadata,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:7: * and M12 planner blockers.
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:159:} as unknown as ShaderUniformDefinition;
src/tools/video-editor/runtime/extensionStateRepositoryProvider.test.ts:93:function makeSettingsSnapshot(extId: string, schemaVersion: number = 1, values: Record<string, unknown> = {}): ExtensionSettingsSnapshot {
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:139:): Record<string, unknown> | undefined {
src/tools/video-editor/lib/source-map-runtime.ts:99:  function getExtensionApp(extensionId: string): Record<string, unknown> {
src/tools/video-editor/lib/source-map-runtime.ts:105:    return extData as Record<string, unknown>;
src/tools/video-editor/lib/source-map-runtime.ts:109:  function parseEntry(raw: unknown): SourceMapEntry | null {
src/tools/video-editor/lib/source-map-runtime.ts:111:    const r = raw as Record<string, unknown>;
src/tools/video-editor/lib/source-map-runtime.ts:127:        ? { meta: r.meta as Record<string, unknown> }
src/tools/video-editor/lib/source-map-runtime.ts:133:  function serializeEntry(entry: SourceMapEntry): Record<string, unknown> {
src/tools/video-editor/lib/source-map-runtime.ts:153:    value: unknown,
src/tools/video-editor/lib/source-map-runtime.ts:204:      meta?: Record<string, unknown>,
src/tools/video-editor/runtime/liveRecording.test.ts:38:  data: Record<string, unknown>,
src/tools/video-editor/runtime/liveRecording.test.ts:39:  metadata?: Record<string, unknown>,
src/tools/video-editor/runtime-components/DynamicComponentRegistry.ts:20:export class DynamicComponentRegistry<TProps, TSchema = unknown> {
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:79:  unknown: 'bg-muted text-muted-foreground',
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:382:                sourceBadge.kind !== 'unknown' ||
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:411:                        {sourceBadge.kind !== 'unknown' && (
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:415:                              SOURCE_BADGE_STYLES[sourceBadge.kind] ?? SOURCE_BADGE_STYLES.unknown,
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:69:    expect(reg.entries.size).toBe(16); // supported controls + audio-binding + unsupported textureRef
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:75:  it('resolves textureRef as a built-in unsupported diagnostic placeholder', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:81:    expect(entry.status).toBe('unsupported');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:83:    expect(entry.diagnostic?.code).toBe('schema/texture-ref-unsupported');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:161:describe('unsupported type diagnostics', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:162:  it('resolves unknown types as unsupported with a diagnostic', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:168:    expect(entry.status).toBe('unsupported');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:172:    expect(entry.diagnostic!.code).toBe('schema/unsupported-type');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:175:    expect(entry.diagnostic!.detail).toEqual({ unsupportedType: 'made-up-type' });
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:178:  it('getDiagnostic returns a valid diagnostic for unknown types', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:182:    expect(d!.code).toBe('schema/unsupported-type');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:187:  it('unsupported types are NOT added to the entries map (they are ephemeral)', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:189:    reg.resolve('unknown');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:190:    expect(reg.entries.has('unknown')).toBe(false);
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:193:  it('unsupported diagnostic includes extensionId when owner is provided', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:199:  it('resolve returns a fresh unsupported entry each call for unknown types', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:209:  it('resolve returns consistent label for unknown types', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:213:    expect(entry.status).toBe('unsupported');
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:460:  it('ownerExtensionId is reflected in unsupported diagnostics', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:462:    const diag = reg.getDiagnostic('unknown-type')!;
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:466:  it('ownerExtensionId is reflected in built-in unsupported textureRef diagnostics', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:475:    const diag = reg.getDiagnostic('unknown-type')!;
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:75:      description: `Copilot trace: clip ${clip.id} (${clip.clipType ?? 'unknown'}) → analysis output`,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:95:  detail: Record<string, unknown>;
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:104:  const clipTypes = new Set(snapshot.clips.map((c) => c.clipType ?? 'unknown'));
src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx:143:        typeof (repo as Record<string, unknown>).getBundleContent === "function"
src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx:145:        setEffectiveBundleStore(repo as unknown as BundleContentStore);
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:10:  params: Record<string, unknown> | undefined;
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:12:  onChange: (params: Record<string, unknown>) => void;
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:17:const asAssetKeys = (value: unknown): string[] => {
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:41:  current: Record<string, unknown> | undefined,
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:43:  value: unknown,
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx:44:): Record<string, unknown> => ({
src/tools/video-editor/runtime/liveBake.test.ts:21:  data: Record<string, unknown> | Uint8Array = { value: sequenceNumber },
src/tools/video-editor/runtime/liveBake.test.ts:22:  metadata?: Record<string, unknown>,
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:25:  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/hooks/useTimelineOps.test.ts:282:    it('rejects a batch with an unknown operation family', () => {
src/tools/video-editor/hooks/useTimelineOps.test.ts:1023:      let caught: unknown;
src/tools/video-editor/runtime/extensionSettings.test.ts:23:function makeManifest(overrides: Partial<Record<string, unknown>> = {}): ExtensionManifest {
src/tools/video-editor/runtime/extensionSettings.test.ts:155:  it('passes unknown types through unchanged', () => {
src/tools/video-editor/runtime/extensionSettings.test.ts:172:    // may treat it as unsupported — that's expected.
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:57: * - Provides a preview-only sample channel placeholder.
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:76:  let _completeResult: Record<string, unknown> | undefined;
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:174:      return `sample-channel:${sessionId}:preview-only`;
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:177:    complete(result?: Record<string, unknown>): void {
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:198: * cancellation, and a preview-only sample channel.
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:228:      `generation with progress, cancellation, and a preview-only sample channel.`,
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:332:              clipType: firstClip.clipType ?? 'unknown',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:411:      'progress reporting, cancellation, preview-only GenerationSession, placeholder ' +
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:423:          'cancellation, and preview-only sample channels through GenerationSession.',
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:81:  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:459:  it('does not show a badge for asset entries that produce unknown source kind', () => {
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:461:    // → getSourceBadge returns { kind: 'unknown', label: 'Unknown' }
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:475:    // The "Unknown" badge is never rendered (kind !== 'unknown' check in component)
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:504:          origin: 'opaque-foreign', // opaque-foreign without sourceUrl → unknown badge → no expand button
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:691:    // Use opaque-foreign without sourceUrl/sourceProvider → unknown badge
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:882:    // No badge (opaque-foreign without sourceUrl → unknown),
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:116:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:120:function isEmptyRecord(value: Record<string, unknown>): boolean {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:124:function filterBindingValue(value: unknown, sourceId: string): { value?: unknown; changed: boolean } {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:136:    const next: Record<string, unknown> = { ...value };
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:285:function readPath(data: unknown, path: string): unknown {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:287:  return path.split('.').reduce<unknown>((current, key) => (
src/tools/video-editor/runtime/extensionReferenceReport.ts:6: * and diagnostics/export blockers when references remain after uninstall.
src/tools/video-editor/runtime/extensionReferenceReport.ts:134:  /** Blocking diagnostics (export blockers). */
src/tools/video-editor/runtime/extensionReferenceReport.ts:378: * When references exist, they become export blockers — the user must
src/tools/video-editor/runtime/extensionReferenceReport.ts:499:      readonly detail?: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.test.ts:815:    it('returns undefined for unknown ID', async () => {
src/tools/video-editor/lib/proposal-runtime.test.ts:900:          return { ...data1, configVersion: version } as unknown as TimelineData;
src/tools/video-editor/lib/proposal-runtime.test.ts:1296:  describe('unsupported-provider diagnostics', () => {
src/tools/video-editor/lib/proposal-runtime.test.ts:1301:      // `persistenceProvider` and emit diagnostics when it's unsupported.
src/tools/video-editor/lib/proposal-runtime.test.ts:1306:      // throwing.  When `persistenceProvider: null` or `'unsupported'`
src/tools/video-editor/lib/proposal-runtime.test.ts:1315:      // Should not throw — unsupported is a valid configuration
src/tools/video-editor/lib/proposal-runtime.test.ts:1321:      // When persistence is unsupported, a diagnostic should be available.
src/tools/video-editor/lib/proposal-runtime.test.ts:1327:          (d: any) => d.code === 'proposal/persistence-unsupported',
src/tools/video-editor/lib/proposal-runtime.test.ts:1347:          (d: any) => d.code === 'proposal/persistence-unsupported',
src/tools/video-editor/lib/proposal-runtime.test.ts:1353:    it('explicitly warns that proposals will be lost on page refresh when persistence is unsupported', () => {
src/tools/video-editor/lib/proposal-runtime.test.ts:1369:        (d: any) => d.code === 'proposal/persistence-unsupported',
src/tools/video-editor/lib/proposal-runtime.test.ts:1405:      // The unsupported diagnostic must be present.
src/tools/video-editor/lib/proposal-runtime.test.ts:1407:      expect(diags.some((d) => d.code === 'proposal/persistence-unsupported')).toBe(true);
src/tools/video-editor/lib/proposal-runtime.test.ts:1412:  // M3: Negative-path — provider_capability_extension_proposals_unsupported bridge
src/tools/video-editor/lib/proposal-runtime.test.ts:1415:  describe('negative-path: unsupported-provider bridge to DataProvider diagnostics', () => {
src/tools/video-editor/lib/proposal-runtime.test.ts:1418:      // proposals as unsupported (similar to what a DataProvider that lacks
src/tools/video-editor/lib/proposal-runtime.test.ts:1423:      // persistenceProvider: null is the canonical "unsupported" sentinel.
src/tools/video-editor/lib/proposal-runtime.test.ts:1433:      const unsupportedDiag = diags.find(
src/tools/video-editor/lib/proposal-runtime.test.ts:1434:        (d) => d.code === 'proposal/persistence-unsupported',
src/tools/video-editor/lib/proposal-runtime.test.ts:1436:      expect(unsupportedDiag).toBeDefined();
src/tools/video-editor/lib/proposal-runtime.test.ts:1437:      expect(unsupportedDiag!.severity).toBe('warning');
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:100:  it('renders live source status, permission, recording, preview health, diagnostics, and export blockers', () => {
src/tools/video-editor/compositions/installed-themes.ts:56:export const isInstalledTimelineThemeId = (value: unknown): value is (typeof AVAILABLE_TIMELINE_THEME_IDS)[number] => {
src/tools/video-editor/compositions/installed-themes.ts:60:const isRecord = (value: unknown): value is Record<string, unknown> => {
src/tools/video-editor/compositions/installed-themes.ts:64:const deepMerge = <T extends Record<string, unknown>>(base: T, overlay: Record<string, unknown>): T => {
src/tools/video-editor/compositions/installed-themes.ts:65:  const result: Record<string, unknown> = { ...base };
src/tools/video-editor/compositions/installed-themes.ts:79:    DEFAULT_THEME as unknown as Record<string, unknown>,
src/tools/video-editor/compositions/installed-themes.ts:80:    theme as unknown as Record<string, unknown>,
src/tools/video-editor/compositions/installed-themes.ts:81:  ) as unknown as Theme;
src/tools/video-editor/compositions/installed-themes.ts:96:    baseTheme as unknown as Record<string, unknown>,
src/tools/video-editor/compositions/installed-themes.ts:98:  ) as unknown as Theme;
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:8: * `clipType` is unknown to the editor (Phase 4 will enable), or because a
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:13: *   - "unsupported": yellow/amber band — the clipType is an unknown id that
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:19:export type UnknownClipReason = 'unsupported' | 'missing-asset';
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:22:  unsupported: {
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:38:    case 'unsupported':
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:53:      data-testid="unknown-clip-placeholder"
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx:98:      <Body reason={reason} clipType={clip.clipType ?? 'unknown'} clipId={clip.id} />
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:29:  toDataURL(type?: string, quality?: unknown): string;
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:36:  readonly previewClip: Record<string, unknown>;
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:42:  readonly previewClip: Record<string, unknown>;
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:68:  detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:104:}): Record<string, unknown> {
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:146:): Record<string, unknown> {
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:227:    detail?: Record<string, unknown>,
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:305:        'live-webcam/unsupported',
src/tools/video-editor/runtime/extensionLifecycle.test.ts:1895:    const creative = ctx.creative as Record<string, unknown>;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:1915:    const timeline = ctx.creative.timeline as Record<string, unknown>;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:1939:    function collectKeys(obj: unknown, depth: number) {
src/tools/video-editor/runtime/extensionLifecycle.test.ts:1944:          collectKeys((obj as Record<string, unknown>)[key], depth + 1);
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2135:    const ctxAny = ctx as Record<string, unknown>;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2151:    const ctxAny = ctx as Record<string, unknown>;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2416:    } as unknown as LiveDataRegistry;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2441:    } as unknown as LiveDataRegistry;
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2462:    } as unknown as LiveDataRegistry;
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:168:  it('maps unknown contribution kinds to "other"', () => {
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:171:        unknownKind: {
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:6: * uniform defaults, textureRef metadata, registry diagnostics, preview-only
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:8: * blockers.
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:167:} as unknown as ShaderUniformDefinition;
src/tools/video-editor/lib/renderRouter.test.ts:8:  decideRenderRoute,
src/tools/video-editor/lib/renderRouter.test.ts:13:describe('Sprint 8 render-button router (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:15:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:29:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:37:    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
src/tools/video-editor/lib/renderRouter.test.ts:38:    expect(decision.planner.plannerResult.canWorkerExport).toBe(true);
src/tools/video-editor/lib/renderRouter.test.ts:42:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:52:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:65:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:78:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:86:  it('treats unknown clipTypes as media (loud-placeholder fallback path)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:87:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:95:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:110:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:125:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:144:    const missingArtifact = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:148:      route: 'preview-only',
src/tools/video-editor/lib/renderRouter.test.ts:152:    expect(missingArtifact.planner.plannerResult.canBrowserExport).toBe(false);
src/tools/video-editor/lib/renderRouter.test.ts:153:    expect(missingArtifact.planner.plannerResult.canWorkerExport).toBe(false);
src/tools/video-editor/lib/renderRouter.test.ts:155:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:158:      route: 'preview-only',
src/tools/video-editor/lib/renderRouter.test.ts:162:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:163:      clips: [{ clipType: 'unknown', generation: { sequence_lane: 'remotion_module', artifact_id: 42 } }],
src/tools/video-editor/lib/renderRouter.test.ts:165:      route: 'preview-only',
src/tools/video-editor/lib/renderRouter.test.ts:171:    for (const sequence_lane of ['trusted_v1', 'schema_sequence', 'unknown_lane', null, undefined]) {
src/tools/video-editor/lib/renderRouter.test.ts:172:      expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:185:    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:186:    expect(decideRenderRoute(null).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:187:    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:217:const previewOnlyRecord = makeContributedRecord('ext-preview-only', [
src/tools/video-editor/lib/renderRouter.test.ts:229:describe('M9 T11 contributed clip routing (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:231:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:242:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:257:  it('blocks a contributed clip without browser-export capability (preview-only route)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:258:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:259:      { clips: [{ clipType: 'ext-preview-only' }] },
src/tools/video-editor/lib/renderRouter.test.ts:262:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:264:    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
src/tools/video-editor/lib/renderRouter.test.ts:268:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:272:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:274:    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
src/tools/video-editor/lib/renderRouter.test.ts:278:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:282:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:284:    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
src/tools/video-editor/lib/renderRouter.test.ts:288:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:297:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:300:    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
src/tools/video-editor/lib/renderRouter.test.ts:304:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:319:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:321:    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
src/tools/video-editor/lib/renderRouter.test.ts:328:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:343:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:354:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:364:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:374:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:385:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:389:          { clipType: 'ext-preview-only' },
src/tools/video-editor/lib/renderRouter.test.ts:394:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:396:    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
src/tools/video-editor/lib/renderRouter.test.ts:400:    const decision = decideRenderRoute({ clips: [] }, [browserCapableRecord]);
src/tools/video-editor/lib/renderRouter.test.ts:407:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:416:    expect(decision.route).toBe('preview-only');
src/tools/video-editor/lib/renderRouter.test.ts:597:      fetchImpl: fetchImpl as unknown as typeof fetch,
src/tools/video-editor/lib/renderRouter.test.ts:620:      fetchImpl: fetchImpl as unknown as typeof fetch,
src/tools/video-editor/lib/renderRouter.test.ts:630:      fetchImpl: fetchImpl as unknown as typeof fetch,
src/tools/video-editor/lib/renderRouter.test.ts:646:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:672:      fetchImpl: fetchImpl as unknown as typeof fetch,
src/tools/video-editor/lib/renderRouter.test.ts:685:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:703:    const events: Array<{ type: string; request?: unknown; assetCount?: number; providerId?: string }> = [];
src/tools/video-editor/lib/renderRouter.test.ts:741:      decision: decideRenderRoute(request.resolvedConfig),
src/tools/video-editor/lib/renderRouter.test.ts:774:      decision: decideRenderRoute({ clips: [{ clipType: 'media' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:799:  it('emits renderFailed for preview-only routes without falling back to the browser renderer', async () => {
src/tools/video-editor/lib/renderRouter.test.ts:802:      decision: decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:820:      providerId: 'preview-only',
src/tools/video-editor/lib/renderRouter.test.ts:869:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:900:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
src/tools/video-editor/compositions/VisualClip.test.tsx:29:  input: Record<string, unknown>;
src/tools/video-editor/compositions/VisualClip.test.tsx:41:  AbsoluteFill: ({ children, style, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/VisualClip.test.tsx:44:  Img: ({ src, ...props }: Record<string, unknown>) => (
src/tools/video-editor/compositions/VisualClip.test.tsx:47:  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/VisualClip.test.tsx:57:  createWebGLShaderPreviewSurface: vi.fn((input: Record<string, unknown>) => {
src/tools/video-editor/compositions/VisualClip.test.tsx:72:  Video: ({ src, ...props }: Record<string, unknown>) => (
src/tools/video-editor/compositions/VisualClip.test.tsx:158:      determinism: 'preview-only',
src/tools/video-editor/compositions/VisualClip.test.tsx:163:          determinism: 'preview-only',
src/tools/video-editor/compositions/VisualClip.test.tsx:272:  it('keeps Remotion export honest by showing clip shaders as unsupported instead of running WebGL preview', () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:298:    expect(screen.getByTestId('unsupported-clip-shader-export')).toHaveTextContent(
src/tools/video-editor/compositions/VisualClip.test.tsx:649:  it('renders diagnostic placeholder for unknown transition without provider', async () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:652:        clip={mediaClip({ transition: { type: 'unknown-transition', duration: 0.5 } })}
src/tools/video-editor/runtime/livePermissions.ts:187:        typeof (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices === 'object' &&
src/tools/video-editor/runtime/livePermissions.ts:188:        (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices !== null &&
src/tools/video-editor/runtime/livePermissions.ts:189:        'getUserMedia' in (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices!
src/tools/video-editor/runtime/livePermissions.ts:194:        typeof (navigator as Navigator & { requestMIDIAccess?: unknown }).requestMIDIAccess === 'function'
src/tools/video-editor/runtime/livePermissions.ts:199:        typeof (navigator as Navigator & { serial?: unknown }).serial === 'object' &&
src/tools/video-editor/runtime/livePermissions.ts:200:        (navigator as Navigator & { serial?: unknown }).serial !== null
src/tools/video-editor/runtime/livePermissions.ts:205:        typeof (navigator as Navigator & { bluetooth?: unknown }).bluetooth === 'object' &&
src/tools/video-editor/runtime/livePermissions.ts:206:        (navigator as Navigator & { bluetooth?: unknown }).bluetooth !== null
src/tools/video-editor/runtime/livePermissions.ts:218:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/livePermissions.ts:229:  if (reason !== undefined) (perm as Record<string, unknown>).reason = reason;
src/tools/video-editor/runtime/livePermissions.ts:230:  if (deviceLabel !== undefined) (perm as Record<string, unknown>).deviceLabel = deviceLabel;
src/tools/video-editor/runtime/livePermissions.ts:232:    (perm as Record<string, unknown>).requestedAt = new Date().toISOString();
src/tools/video-editor/runtime/livePermissions.ts:393:            serial?: { requestPort?: (opts?: SerialPortRequestOptions) => Promise<unknown> };
src/tools/video-editor/runtime/livePermissions.ts:409:            bluetooth?: { requestDevice?: (opts?: RequestDeviceOptions) => Promise<unknown> };
src/tools/video-editor/runtime/livePermissions.ts:433:    } catch (err: unknown) {
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:76:    useTimelineDataSelector: (selector: (value: any) => unknown) => selector(useTimelineEditorDataMock()),
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:77:    useTimelineOpsSelector: (selector: (value: any) => unknown) => selector(useTimelineEditorOpsMock()),
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:78:    useTimelinePlaybackSelector: (selector: (value: any) => unknown) => selector(useTimelinePlaybackContextMock()),
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:79:    useTimelineChromeSelector: (selector: (value: any) => unknown) => selector(useTimelineChromeContextMock()),
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:84:  usePanesStore: (selector: (value: any) => unknown) => selector(usePanesStoreMock()),
src/tools/video-editor/runtime/extensionSurface.ts:209:  /** Declaration-time blockers that the planner should surface before execution. */
src/tools/video-editor/runtime/extensionSurface.ts:210:  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:249:/** Planner next-action metadata for resolving route/process/material blockers. */
src/tools/video-editor/runtime/extensionSurface.ts:273:  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:427:  readonly settingsDefaults: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
src/tools/video-editor/runtime/extensionSurface.ts:590:  const settingsDefaults: Record<string, Record<string, unknown>> = {};
src/tools/video-editor/runtime/extensionSurface.ts:635:        const effectContrib = contrib as unknown as EffectContribution;
src/tools/video-editor/runtime/extensionSurface.ts:648:            milestone: notYetBridged ?? 'unknown',
src/tools/video-editor/runtime/extensionSurface.ts:670:        const transitionContrib = contrib as unknown as TransitionContribution;
src/tools/video-editor/runtime/extensionSurface.ts:683:            milestone: notYetBridged ?? 'unknown',
src/tools/video-editor/runtime/extensionSurface.ts:827:          slots[contribution.slot] = slots[contribution.slot] ?? (null as unknown as VideoEditorSlotRenderer);
src/tools/video-editor/runtime/extensionSurface.ts:836:          render: null as unknown as VideoEditorSlotRenderer, // placeholder
src/tools/video-editor/runtime/extensionSurface.ts:845:          render: null as unknown as VideoEditorSlotRenderer, // placeholder
src/tools/video-editor/runtime/extensionSurface.ts:854:          render: null as unknown as VideoEditorSlotRenderer, // placeholder
src/tools/video-editor/runtime/extensionSurface.ts:862:          render: null as unknown as VideoEditorSlotRenderer, // placeholder
src/tools/video-editor/runtime/extensionSurface.ts:868:        const parserContrib = contribution as unknown as ParserContribution;
src/tools/video-editor/runtime/extensionSurface.ts:883:        const facetContrib = contribution as unknown as MetadataFacetContribution;
src/tools/video-editor/runtime/extensionSurface.ts:898:        const sectionContrib = contribution as unknown as AssetDetailSectionContribution;
src/tools/video-editor/runtime/extensionSurface.ts:912:        const effectContrib = contribution as unknown as EffectContribution;
src/tools/video-editor/runtime/extensionSurface.ts:930:        const transitionContrib = contribution as unknown as TransitionContribution;
src/tools/video-editor/runtime/extensionSurface.ts:948:        const shaderContrib = contribution as unknown as ShaderContribution;
src/tools/video-editor/runtime/extensionSurface.ts:980:        const at = contribution as unknown as AgentToolContribution;
src/tools/video-editor/runtime/extensionSurface.ts:1003:    const of = contribution as unknown as OutputFormatContribution;
src/tools/video-editor/runtime/extensionSurface.ts:1008:    const blockers = buildOutputFormatBlockers(extensionId, contribution.id as string, of, renderDescriptor);
src/tools/video-editor/runtime/extensionSurface.ts:1009:    const nextActions = buildOutputFormatNextActions(of, renderDescriptor, blockers);
src/tools/video-editor/runtime/extensionSurface.ts:1010:    const capabilities = buildOutputFormatCapabilities(extensionId, contribution.id as string, of, renderDescriptor, blockers);
src/tools/video-editor/runtime/extensionSurface.ts:1025:      blockers,
src/tools/video-editor/runtime/extensionSurface.ts:1047:    const processContrib = contribution as unknown as ProcessContribution;
src/tools/video-editor/runtime/extensionSurface.ts:1066:      blockers: Object.freeze([]),
src/tools/video-editor/runtime/extensionSurface.ts:1091:    const sp = contribution as unknown as SearchProviderContribution;
src/tools/video-editor/runtime/extensionSurface.ts:1197:      determinism: renderDescriptor.determinism ?? 'unknown',
src/tools/video-editor/runtime/extensionSurface.ts:1236:      reason: 'route-unsupported',
src/tools/video-editor/runtime/extensionSurface.ts:1246:  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
src/tools/video-editor/runtime/extensionSurface.ts:1249:  if (blockers[0]?.nextAction) return Object.freeze([blockers[0].nextAction]);
src/tools/video-editor/runtime/extensionSurface.ts:1281:  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
src/tools/video-editor/runtime/extensionSurface.ts:1303:  const determinism = renderDescriptor?.determinism ?? 'unknown';
src/tools/video-editor/runtime/extensionSurface.ts:1310:        reason: 'route-unsupported' as const,
src/tools/video-editor/runtime/extensionSurface.ts:1311:        message: blockers[0]?.message,
src/tools/video-editor/runtime/extensionSurface.ts:1334:      determinism: 'unknown',
src/tools/video-editor/runtime/extensionSurface.ts:1336:      findings: Object.freeze(blockers.map((blocker) => Object.freeze({
src/tools/video-editor/runtime/extensionSurface.ts:1356:    fullySupported: blockers.length === 0,
src/tools/video-editor/runtime/extensionSurface.ts:1357:    anyBlocked: blockers.length > 0,
src/tools/video-editor/runtime/extensionSurface.ts:1406:    return EMPTY_PANELS as unknown as readonly T[];
src/tools/video-editor/runtime/extensionSurface.ts:1615:      render: () => (descriptor.render ? descriptor.render(null as unknown as VideoEditorRenderContext) : null),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:133:): Record<string, unknown> | undefined {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:140:  storedParams: Record<string, unknown> | undefined,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:141:): Record<string, unknown> {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:245:/** Check if an effect is preview-only (browser-export and worker-export both blocked). */
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:267:  storedParams: Record<string, unknown> | undefined,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:315:/** Check if a transition is preview-only (browser-export and worker-export both blocked). */
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:333:  storedParams: Record<string, unknown> | undefined,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:350:  storedParams: Record<string, unknown> | undefined,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:351:): Record<string, unknown> {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1541:                    value={clip.hold ?? (clipDescriptor && clipDescriptor.hold.kind !== 'unsupported' ? clipDescriptor.hold.defaultSeconds : 5)}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1542:                    min={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.minSeconds : 0.1}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1543:                    max={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.maxSeconds : undefined}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1544:                    step={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.stepSeconds : 0.1}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1684:          params: Record<string, unknown>;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1685:          onParamsChange: (params: Record<string, unknown>) => void;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1715:                clipTypeId={clip.clipType ?? 'unknown'}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1717:                onParamsChange={(params: Record<string, unknown>) =>
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:30:  AbsoluteFill: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:33:  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:49:    ThemeProvider: ({ children, value }: PropsWithChildren<{ value?: unknown }>) => (
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:105:      FakeDynamicSeq as unknown as ReturnType<typeof compileSequenceModule.compileSequenceComponentAsync> extends Promise<infer C> ? C : never,
src/tools/video-editor/hooks/useExternalDrop.test.tsx:45:  extractVideoMetadataFromUrl: (...args: unknown[]) => mockExtractVideoMetadataFromUrl(...args),
src/tools/video-editor/hooks/useExternalDrop.test.tsx:61:  } as unknown as React.DragEvent;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:76:  } as unknown as React.DragEvent;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:96:  } as unknown as React.DragEvent<HTMLDivElement>;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:113:  } as unknown as React.DragEvent<HTMLDivElement>;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:118:  let reject!: (reason?: unknown) => void;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:288:    } as unknown as React.DragEvent<HTMLDivElement>;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:337:    } as unknown as React.DragEvent<HTMLDivElement>;
src/tools/video-editor/hooks/useExternalDrop.test.tsx:737:  it('shows a toast and leaves timeline state unchanged when local asset drop is unsupported', async () => {
src/tools/video-editor/hooks/useExternalDrop.test.tsx:1374:      ([_mutation, opts]: [unknown, unknown]) =>
src/tools/video-editor/hooks/useExternalDrop.test.tsx:1375:        opts && typeof opts === 'object' && (opts as Record<string, unknown>).save === false,
src/tools/video-editor/lib/timeline-reader.ts:56:  obj: Record<string, unknown>,
src/tools/video-editor/lib/timeline-reader.ts:78:    const appObj = app as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:155:  app: Record<string, unknown> | undefined,
src/tools/video-editor/lib/timeline-reader.ts:160:  const g = raw as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:167:    meta.provenance = g.provenance as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:175:  value: Record<string, unknown> | undefined,
src/tools/video-editor/lib/timeline-reader.ts:198:      const binding = rawBinding as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:248:function isClipShaderMetadata(value: unknown): value is TimelineClipShaderMetadata {
src/tools/video-editor/lib/timeline-reader.ts:253:    && (value as Record<string, unknown>).scope === 'clip'
src/tools/video-editor/lib/timeline-reader.ts:254:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:255:    && typeof (value as Record<string, unknown>).extensionId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:256:    && typeof (value as Record<string, unknown>).contributionId === 'string',
src/tools/video-editor/lib/timeline-reader.ts:260:function isPostprocessShaderMetadata(value: unknown): value is TimelinePostprocessShaderMetadata {
src/tools/video-editor/lib/timeline-reader.ts:265:    && (value as Record<string, unknown>).scope === 'postprocess'
src/tools/video-editor/lib/timeline-reader.ts:266:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:267:    && typeof (value as Record<string, unknown>).extensionId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:268:    && typeof (value as Record<string, unknown>).contributionId === 'string',
src/tools/video-editor/lib/timeline-reader.ts:371:              const effectObj = eff as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:391:                    ? (effectObj.params as Record<string, unknown>)
src/tools/video-editor/lib/timeline-reader.ts:402:              rawEffects as Record<string, unknown>,
src/tools/video-editor/lib/timeline-reader.ts:422:          const tObj = rawTransition as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:434:            id: `${clip.id}.transition.${transitionType ?? 'unknown'}`,
src/tools/video-editor/lib/timeline-reader.ts:442:                ? (tObj.params as Record<string, unknown>)
src/tools/video-editor/lib/timeline-reader.ts:475:            mediaKind: 'unknown',
src/tools/video-editor/lib/timeline-reader.ts:485:            mediaKind: 'unknown',
src/tools/video-editor/lib/timeline-reader.ts:499:              : 'unknown',
src/tools/video-editor/lib/timeline-reader.ts:505:              ? 'preview-only'
src/tools/video-editor/lib/timeline-reader.ts:506:              : 'unknown',
src/tools/video-editor/lib/timeline-reader.ts:512:          const generation = clipMeta.generation as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:570:      const app: Record<string, unknown> = config.app !== undefined
src/tools/video-editor/lib/timeline-reader.ts:591:        const extObj = extData as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:594:          const entry = value as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.ts:607:            ...(entry.meta !== undefined && typeof entry.meta === 'object' ? { meta: entry.meta as Record<string, unknown> } : {}),
src/tools/video-editor/components/ProcessSettingsForm.test.tsx:35:    blockers: [],
src/tools/video-editor/lib/managed-object-guard.ts:47:  provenance?: Record<string, unknown>;
src/tools/video-editor/lib/managed-object-guard.ts:145:): Record<string, unknown> {
src/tools/video-editor/lib/managed-object-guard.ts:146:  const patch: Record<string, unknown> = {};
src/tools/video-editor/lib/managed-object-guard.ts:167:  app: Record<string, unknown> | undefined,
src/tools/video-editor/lib/managed-object-guard.ts:169:): Record<string, unknown> | undefined {
src/tools/video-editor/lib/managed-object-guard.ts:171:  const next: Record<string, unknown> = {};
src/tools/video-editor/runtime/agentToolRegistry.test.ts:130:  input?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolRegistry.test.ts:614:  it('cancelSessions returns 0 for unknown tool', () => {
src/tools/video-editor/runtime/agentToolRegistry.test.ts:616:    expect(registry.cancelSessions('unknown')).toBe(0);
src/tools/video-editor/runtime/agentToolRegistry.test.ts:837:    const badResult = { family: 'bad/family', data: 'x' } as unknown as ToolResult;
src/tools/video-editor/runtime/agentToolRegistry.test.ts:843:      (d) => d.code === 'agent-tool/unsupported-result-family',
src/tools/video-editor/runtime/agentToolRegistry.test.ts:852:    const badResult = { data: 'no-family' } as unknown as ToolResult;
src/tools/video-editor/runtime/agentToolRegistry.test.ts:1204:  it('getTool returns undefined for unknown tool', () => {
src/tools/video-editor/runtime/agentToolRegistry.test.ts:1209:  it('getStatus returns zero-status for unknown tool', () => {
src/tools/video-editor/runtime/agentToolRegistry.test.ts:1211:    const status = registry.getSnapshot().getStatus('unknown');
src/tools/video-editor/components/MaterialBrowser.tsx:23:  plannerResult?: Pick<RenderPlannerResult, 'nextActions' | 'blockers' | 'diagnostics'>;
src/tools/video-editor/components/MaterialBrowser.tsx:27:function text(value: unknown): string {
src/tools/video-editor/components/MaterialBrowser.tsx:39:  const record = material as unknown as Record<string, unknown>;
src/tools/video-editor/components/MaterialBrowser.tsx:40:  return text(record[key] ?? (material.locator as unknown as Record<string, unknown>)[key]);
src/tools/video-editor/components/MaterialBrowser.tsx:60:  if (filters.provenance && !text((material as unknown as Record<string, unknown>).provenance).includes(filters.provenance)) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:93:  const findings = [...(plannerResult?.blockers ?? []), ...(plannerResult?.diagnostics ?? [])];
src/tools/video-editor/components/MaterialBrowser.tsx:129:                <dt>Producer</dt><dd>{selected.material.producerExtensionId ?? 'unknown'}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:134:                <dt>Provenance</dt><dd>{text((selected.material as unknown as Record<string, unknown>).provenance) || 'none'}</dd>
src/tools/video-editor/lib/timeline-schema.fallback.ts:1:export type ThemeRegistry = Record<string, Record<string, unknown>>;
src/tools/video-editor/lib/timeline-schema.fallback.ts:5:  theme_overrides?: Record<string, unknown>;
src/tools/video-editor/lib/timeline-schema.fallback.ts:11:): Record<string, unknown> {
src/tools/video-editor/compositions/AudioTrack.test.tsx:8:const sequenceProps: Array<Record<string, unknown>> = [];
src/tools/video-editor/compositions/AudioTrack.test.tsx:9:const html5AudioProps: Array<Record<string, unknown>> = [];
src/tools/video-editor/compositions/AudioTrack.test.tsx:10:const mediaAudioProps: Array<Record<string, unknown>> = [];
src/tools/video-editor/compositions/AudioTrack.test.tsx:21:    Sequence: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
src/tools/video-editor/compositions/AudioTrack.test.tsx:25:    Audio: (props: Record<string, unknown>) => {
src/tools/video-editor/compositions/AudioTrack.test.tsx:34:  Audio: (props: Record<string, unknown>) => {
src/tools/video-editor/components/MaterialBrowser.test.tsx:6:function material(id: string, overrides: Partial<RenderMaterialRef> & Record<string, unknown> = {}): RenderMaterialRef {
src/tools/video-editor/components/MaterialBrowser.test.tsx:65:          blockers: [{
src/tools/video-editor/components/EffectCreatorPanel.tsx:48:  onSaved?: (resourceId: string, category: EffectCategory, defaultParams: Record<string, unknown>) => void;
src/tools/video-editor/components/EffectCreatorPanel.tsx:145:  effectParams: Record<string, unknown>,
src/tools/video-editor/components/EffectCreatorPanel.tsx:204:  const [previewParamValues, setPreviewParamValues] = useState<Record<string, unknown>>(
src/tools/video-editor/runtime/transitionRegistrationService.ts:226:          typeof (d as Record<string, unknown>).source === 'string' &&
src/tools/video-editor/runtime/transitionRegistrationService.ts:227:          AUDIO_SOURCES.has((d as Record<string, unknown>).source as string) &&
src/tools/video-editor/runtime/transitionRegistrationService.ts:228:          typeof (d as Record<string, unknown>).min === 'number' &&
src/tools/video-editor/runtime/transitionRegistrationService.ts:229:          Number.isFinite((d as Record<string, unknown>).min as number) &&
src/tools/video-editor/runtime/transitionRegistrationService.ts:230:          typeof (d as Record<string, unknown>).max === 'number' &&
src/tools/video-editor/runtime/transitionRegistrationService.ts:231:          Number.isFinite((d as Record<string, unknown>).max as number);
src/tools/video-editor/runtime/transitionRegistrationService.ts:308:  return sdkSchema.map((def) => ({ ...def })) as unknown as ParameterSchema;
src/tools/video-editor/runtime/transitionRegistrationService.ts:315: * Per SD3: trusted component transitions default to preview-only. Browser-export
src/tools/video-editor/runtime/transitionRegistrationService.ts:327:    determinism: 'preview-only',
src/tools/video-editor/runtime/transitionRegistrationService.ts:334:    determinism: contrib.allowBrowserExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/transitionRegistrationService.ts:338:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/transitionRegistrationService.ts:348:    determinism: contrib.allowWorkerExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/transitionRegistrationService.ts:352:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/transitionRegistrationService.ts:358:  const determinism: DeterminismStatus = 'preview-only';
src/tools/video-editor/runtime/transitionRegistrationService.ts:410:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/outputFormatRegistry.ts:107:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/outputFormatRegistry.ts:153:  } catch (err: unknown) {
src/tools/video-editor/runtime/outputFormatRegistry.ts:173:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:179:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:204:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:211:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:242:  } catch (err: unknown) {
src/tools/video-editor/runtime/outputFormatRegistry.ts:261:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:267:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:300:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:307:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:34:function getUniformDefault(uniform: ShaderUniformDefinition): unknown {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:89:function isTimelineTextureRef(value: unknown): value is TimelineShaderTextureRef {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:94:  const kind = (value as { kind?: unknown }).kind;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:153:        unsupportedType: 'textureRef',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:166:      const detail = diagnostic.detail as Record<string, unknown> | undefined;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:174:function sameJson(left: unknown, right: unknown): boolean {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:212:  const [values, setValues] = useState<Record<string, unknown>>(initialUniforms);
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:248:    nextUniforms: Record<string, unknown>,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:409:            setSchemaDiagnostics(nextDiagnostics.filter((diagnostic) => diagnostic.code !== 'schema/texture-ref-unsupported'));
src/tools/video-editor/hooks/useTimelineState.types.ts:76:    input: TimelineEditorCommandInput | unknown,
src/tools/video-editor/hooks/useTimelineState.types.ts:80:    input: TimelineEditorCommandInput | unknown,
src/tools/video-editor/hooks/useTimelineState.types.ts:84:    input: TimelineEditorCommandInput | unknown,
src/tools/video-editor/lib/timeline-patch.ts:612:        diag('error', 'timeline-patch/unknown-op', `Unknown operation family "${op.op}"`, {
src/tools/video-editor/lib/timeline-patch.ts:765:            diag('error', 'timeline-patch/unknown-op', `Unhandled operation family "${op.op}"`, {
src/tools/video-editor/lib/timeline-patch.ts:808:  target: Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:809:  source: Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:810:): Record<string, unknown> {
src/tools/video-editor/lib/timeline-patch.ts:823:        tgtVal as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:824:        srcVal as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:843:const getIncomingClipShader = (payload: Record<string, unknown>): TimelineClipShaderMetadata | undefined => {
src/tools/video-editor/lib/timeline-patch.ts:848:  const shader = (app as { shader?: unknown }).shader;
src/tools/video-editor/lib/timeline-patch.ts:856:  payload: Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:946:  const configApp: Record<string, unknown> = data.config.app
src/tools/video-editor/lib/timeline-patch.ts:951:  const trackAppSnapshots = new Map<string, Record<string, unknown> | undefined>();
src/tools/video-editor/lib/timeline-patch.ts:1069:        const beforeSummary: Record<string, unknown> = {
src/tools/video-editor/lib/timeline-patch.ts:1110:        const beforeSummary: Record<string, unknown> = {
src/tools/video-editor/lib/timeline-patch.ts:1143:              delete (existingClip as Record<string, unknown>)[key];
src/tools/video-editor/lib/timeline-patch.ts:1148:            (existingClip as Record<string, unknown>)[key] = value;
src/tools/video-editor/lib/timeline-patch.ts:1154:            (existingClip as Record<string, unknown>)[key] = value;
src/tools/video-editor/lib/timeline-patch.ts:1179:              (existingMeta as unknown as Record<string, unknown>)[key] = value;
src/tools/video-editor/lib/timeline-patch.ts:1212:        const beforeSummary: Record<string, unknown> = { id: op.target, track: oldTrack, at: oldAt };
src/tools/video-editor/lib/timeline-patch.ts:1366:        const beforeSummary: Record<string, unknown> = { id: before.id, kind: before.kind, label: before.label };
src/tools/video-editor/lib/timeline-patch.ts:1380:              (updatedTrack as Record<string, unknown>)[key] = payload[key];
src/tools/video-editor/lib/timeline-patch.ts:1385:            updatedTrack.app = { ...(payload.app as Record<string, unknown>) };
src/tools/video-editor/lib/timeline-patch.ts:1410:            updatedTrack.app = { ...updatedTrack.app, ...(payload.app as Record<string, unknown>) };
src/tools/video-editor/lib/timeline-patch.ts:1495:        const beforeSummary: Record<string, unknown> | undefined = existing
src/tools/video-editor/lib/timeline-patch.ts:1554:        const beforeSummary: Record<string, unknown> | undefined = beforeApp !== undefined
src/tools/video-editor/lib/timeline-patch.ts:1559:        const updateData: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.ts:1592:          const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
src/tools/video-editor/lib/timeline-patch.ts:1615:        const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
src/tools/video-editor/lib/timeline-patch.ts:1617:        const beforeSummary: Record<string, unknown> = {
src/tools/video-editor/lib/timeline-patch.ts:1629:            { ...(beforeValue as Record<string, unknown>) },
src/tools/video-editor/lib/timeline-patch.ts:1630:            value as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.ts:1708:        const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts:82:  input?: Record<string, unknown>;
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts:119:  input?: Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:35:  values?: Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:36:  onChange?: (name: string, value: unknown) => void;
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:278:  it('renders textureRef uniforms as unsupported diagnostics without crashing', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:291:    expect(screen.getByTestId('schema-form-unsupported-u_texture')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:294:    expect(diagnostics[0].code).toBe('schema/texture-ref-unsupported');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:295:    expect(diagnostics[0].detail).toMatchObject({ fieldName: 'u_texture', unsupportedType: 'textureRef' });
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:435:describe('unsupported types', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:436:  it('renders diagnostic placeholder for unknown type', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:438:      schema: [parameterDef({ name: 'custom', type: 'unknown-gizmo' as any, label: 'Gizmo' })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:442:    const placeholder = screen.getByTestId('schema-form-unsupported-custom');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:444:    expect(placeholder.getAttribute('data-field-type')).toBe('unknown-gizmo');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:451:      schema: [parameterDef({ name: 'custom', type: 'unknown-gizmo' as any, label: 'Gizmo' })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:460:  it('fires onDiagnostics for unsupported types', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:463:      schema: [parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:471:    expect(diagnostics[0].code).toBe('schema/unsupported-type');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:491:describe('unsupported schema shapes', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:494:  it('renders read-only unsupported placeholder for array property (type:"array")', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:506:    const placeholder = screen.getByTestId('schema-form-unsupported-tags');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:516:  it('renders read-only unsupported placeholder for array property (items without explicit type)', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:528:    const placeholder = screen.getByTestId('schema-form-unsupported-items');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:535:  it('renders read-only unsupported placeholder for nested object property (type:"object")', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:553:    const placeholder = screen.getByTestId('schema-form-unsupported-config');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:561:  it('renders read-only unsupported placeholder for nested object (properties without type)', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:576:    const placeholder = screen.getByTestId('schema-form-unsupported-metadata');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:583:  it('renders read-only unsupported placeholder for $ref property', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:595:    const placeholder = screen.getByTestId('schema-form-unsupported-reference');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:604:  it('renders read-only unsupported placeholder for oneOf property', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:619:    const placeholder = screen.getByTestId('schema-form-unsupported-value');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:628:  it('renders read-only unsupported placeholder for anyOf property', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:643:    const placeholder = screen.getByTestId('schema-form-unsupported-mixed');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:652:  it('renders read-only unsupported placeholder for allOf property', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:667:    const placeholder = screen.getByTestId('schema-form-unsupported-combined');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:676:  it('renders read-only unsupported placeholder for conditional (if/then/else) property', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:693:    const placeholder = screen.getByTestId('schema-form-unsupported-dynamic');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:700:  it('renders read-only unsupported placeholder for conditional (if/then only)', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:716:    const placeholder = screen.getByTestId('schema-form-unsupported-partial');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:723:  it('does not fire onChange for any unsupported shape interaction', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:752:    // (unsupported shapes have no interactive widgets)
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:756:    const placeholder = screen.getByTestId('schema-form-unsupported-arr');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:763:  it('emits onDiagnostics for unsupported shapes', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:783:    expect(codes).toContain('schema/unsupported-array');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:784:    expect(codes).toContain('schema/unsupported-nested-object');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:787:    const arrDiag = diagnostics.find((d) => d.code === 'schema/unsupported-array');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:809:  // -- Mixed supported + unsupported form -------------------------------------
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:811:  it('renders supported fields normally alongside unsupported shape placeholders', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:833:    expect(screen.getByTestId('schema-form-unsupported-tags')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:834:    expect(screen.getByTestId('schema-form-unsupported-config')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:835:    expect(screen.getByTestId('schema-form-unsupported-ref')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:837:    // All unsupported shapes have the Unsupported badge
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:838:    const unsupportedBadges = screen.getAllByText('Unsupported');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:839:    expect(unsupportedBadges).toHaveLength(3);
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:844:  it('does not crash when unsupported shape has null value', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:858:    expect(screen.getByTestId('schema-form-unsupported-arr')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:861:  it('does not crash when unsupported shape has undefined value', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:874:    expect(screen.getByTestId('schema-form-unsupported-nested')).toBeTruthy();
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:877:  // -- Verification that unsupported shapes are non-mutating (save path) ------
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:879:  it('validateAndFocus treats unsupported shapes as errors but does not mutate', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:898:    // validateAndFocus should return false (unsupported shapes block save)
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1904:    values?: Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1905:    onChange?: (name: string, value: unknown) => void;
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2100:  // -- Falls back to error summary for unsupported type ----------------------
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2105:        parameterDef({ name: 'gizmo', type: 'unknown-gizmo' as any, label: 'Gizmo' }),
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2118:  // -- Focuses widget even when unsupported field precedes it ----------------
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2120:  it('skips unsupported fields and focuses the first focusable invalid widget', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2123:        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2139:        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2159:        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2174:        schema: [parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' })],
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:57:      determinism: 'preview-only',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:303:    expect(screen.getByTestId('schema-form-unsupported-u_texture')).toHaveTextContent('Texture');
src/tools/video-editor/hooks/useAgentSession.ts:22:    patch: { version: number; operations: Array<{ op: string; target: string; payload?: Record<string, unknown> }> };
src/tools/video-editor/hooks/useAgentSession.ts:34:function toErrorMessage(error: unknown) {
src/tools/video-editor/hooks/useAgentSession.ts:42:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/hooks/useAgentSession.ts:46:function isAgentSessionStatus(value: unknown): value is AgentSessionStatus {
src/tools/video-editor/hooks/useAgentSession.ts:55:function normalizeTurns(value: unknown): AgentTurn[] {
src/tools/video-editor/hooks/useAgentSession.ts:81:function normalizeSession(row: unknown): AgentSession {
src/tools/video-editor/hooks/useAgentSession.ts:101:function normalizeInvokeResponse(value: unknown): AgentInvocationResponse {
src/tools/video-editor/hooks/useAgentSession.ts:113:      (p: unknown): p is AgentInvocationResponse['proposals'][number] =>
src/tools/video-editor/hooks/useAgentSession.ts:330:              const record = data as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolContracts.test.ts:5: *  - validateAgentToolInputSchema: supported/unsupported StandardSchema subsets
src/tools/video-editor/runtime/agentToolContracts.test.ts:178:// validateAgentToolInputSchema — unsupported / invalid subsets
src/tools/video-editor/runtime/agentToolContracts.test.ts:198:      title: 123 as unknown as string,
src/tools/video-editor/runtime/agentToolContracts.test.ts:207:      description: true as unknown as string,
src/tools/video-editor/runtime/agentToolContracts.test.ts:216:      properties: 'bad' as unknown as Record<string, unknown>,
src/tools/video-editor/runtime/agentToolContracts.test.ts:269:          enum: [1, 2, 3] as unknown as string[],
src/tools/video-editor/runtime/agentToolContracts.test.ts:283:          enum: [1, 2, 3] as unknown as string[],
src/tools/video-editor/runtime/agentToolContracts.test.ts:295:        name: { type: 'string', default: 42 as unknown as string },
src/tools/video-editor/runtime/agentToolContracts.test.ts:307:        count: { type: 'number', default: 'zero' as unknown as number },
src/tools/video-editor/runtime/agentToolContracts.test.ts:318:        flag: { type: 'boolean', default: 'yes' as unknown as boolean },
src/tools/video-editor/runtime/agentToolContracts.test.ts:329:      required: 'name' as unknown as string[],
src/tools/video-editor/runtime/agentToolContracts.test.ts:338:      required: [123] as unknown as string[],
src/tools/video-editor/runtime/agentToolContracts.test.ts:384:          title: 42 as unknown as string,
src/tools/video-editor/runtime/agentToolContracts.test.ts:385:          description: true as unknown as string,
src/tools/video-editor/runtime/agentToolContracts.test.ts:492:  it('returns false for unknown family strings', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:493:    expect(isToolResultFamily('custom/unknown')).toBe(false);
src/tools/video-editor/runtime/agentToolContracts.test.ts:612:  it('rejects result with unsupported family', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:617:    expect(codes(diags)).toContain('agent-tool/unsupported-result-family');
src/tools/video-editor/runtime/agentToolContracts.test.ts:625:    expect(codes(diags)).toContain('agent-tool/unsupported-result-family');
src/tools/video-editor/runtime/agentToolContracts.test.ts:863:    expect((d as Record<string, unknown>).detail).toEqual({
src/tools/video-editor/runtime/agentToolContracts.test.ts:871:    expect((d as Record<string, unknown>).detail).toBeUndefined();
src/tools/video-editor/runtime/agentToolContracts.test.ts:885:    expect((d as Record<string, unknown>).detail).toEqual({ a: 1 });
src/tools/video-editor/runtime/agentToolContracts.test.ts:1020:    delete (result as Record<string, unknown>).rationale;
src/tools/video-editor/runtime/agentToolContracts.test.ts:1201:    delete (result as Record<string, unknown>).rationale;
src/tools/video-editor/runtime/liveMapping.test.ts:19:  data: Record<string, unknown> = { value: 0.5 },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:17:const sequenceProps = vi.hoisted((): Array<Record<string, unknown>> => []);
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:34:    }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:40:    }: PropsWithChildren<Record<string, unknown>>) => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:89:  const toRuntimeTheme = (value: unknown) => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:142:  VisualClipSequence: (props: Record<string, unknown>) => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:149:  TextClipSequence: (props: Record<string, unknown>) => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:156:  PostprocessShaderPreviewCanvas: (props: Record<string, unknown>) => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:212:    }: PropsWithChildren<{ value: unknown }>) => (
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:318:    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:437:  it('renders remotion_module clips as safe placeholders before registered, native, or unknown clipType dispatch', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:465:          id: 'clip-module-unknown',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:466:          clipType: 'generated-unknown',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:472:            artifact_id: 'artifact-unknown',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:483:      'artifact-unknown',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:486:    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:546:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:581:      determinism: 'preview-only',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:586:          determinism: 'preview-only',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:614:    expect(screen.queryByTestId('unsupported-postprocess-shader-export')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:617:  it('keeps postprocess shaders preview-only during Remotion export rendering', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:631:    expect(screen.getByTestId('unsupported-postprocess-shader-export')).toHaveTextContent(
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:664:    renderer: unknown;
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:671:      default?: unknown;
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:678:): Record<string, unknown> {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:689:    renderer: renderer ?? ((() => null) as unknown),
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:718:  } as unknown as VideoEditorRuntimeContextValue;
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:741:    params?: Record<string, unknown>,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:793:    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:915:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:930:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:945:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:965:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:973:    render(<TimelineRenderer config={extBuildConfig('ext.unknown-clip')} />);
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:976:    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1002:    liveBindings: unknown,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1028:      const isPromise = Boolean(latestReturn && typeof (latestReturn as unknown as Promise<unknown>).then === 'function');
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1032:          data-sample-value={String((sample?.frame.data as Record<string, unknown> | undefined)?.value)}
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1033:          data-sample-at-value={String((sampleAt?.frame.data as Record<string, unknown> | undefined)?.value)}
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1174:    binding: Record<string, unknown>,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1239:    expect(Boolean(latestReturn && typeof (latestReturn as Promise<unknown>).then === 'function')).toBe(false);
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1240:    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1375:      result.value && typeof (result.value as Promise<unknown>).then === 'function',
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:24:  AbsoluteFill: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:27:  Img: ({ src, ...props }: Record<string, unknown>) => (
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:30:  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:40:  Video: ({ src, ...props }: Record<string, unknown>) => (
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:7: * host schema capability registry; unsupported types render as
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:40:  default?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:49:  items?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:50:  properties?: Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:52:  oneOf?: unknown[];
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:53:  anyOf?: unknown[];
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:54:  allOf?: unknown[];
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:55:  if?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:56:  then?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:57:  else?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:79:  values: Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:81:  onChange: (name: string, value: unknown) => void;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:92:   * Callback invoked with diagnostics for unsupported / blocked types.
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:125:  default?: unknown;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:144:function isAudioBindingValue(value: unknown): value is AudioBindingValue {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:146:  const candidate = value as Record<string, unknown>;
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:155:function isFiniteNumber(value: unknown): value is number {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:174:function isNumberVector(value: unknown, length: number): value is number[] {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:189:function isShaderColorValue(field: NormalizedField, value: unknown): value is number[] {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:197:function getFallbackValue(field: NormalizedField): unknown {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:231:function getDisplayValue(field: NormalizedField, value: unknown): unknown {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:249:function validateField(field: NormalizedField, value: unknown, registry: SchemaCapabilityRegistry): string | null {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:275:/** Shape labels and diagnostic messages for unsupported schema constructs. */
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:308: * Inspect a StandardSchema property for unsupported JSON Schema shapes
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:311: * @returns The shape key if unsupported, or `null` if the property is a
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:312: * supported flat primitive or unknown type.
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:347: * Build an unsupported capability entry for a schema shape that is known but
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:358:    status: 'unsupported',
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:362:      code: `schema/unsupported-${shape}`,
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:364:      detail: { unsupportedShape: shape },
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:419:    // Detect unsupported schema shapes before resolving the type
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:420:    const unsupportedShape = detectUnsupportedShape(prop);
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:421:    if (unsupportedShape !== null) {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:426:        type: unsupportedShape,
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:430:        _capability: buildUnsupportedShapeCapability(unsupportedShape),
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:464: * renders unsupported types as accessible diagnostic placeholders.
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:496:  const setWidgetRef = useCallback((name: string) => (el: unknown) => {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:521:        // Fields with unsupported or custom status cannot be saved
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:522:        if (field._capability.status === 'unsupported' || field._capability.status === 'custom') {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:550:  // Emit diagnostics for unsupported types
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:555:      if (field._capability.status === 'unsupported' && field._capability.diagnostic) {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:654:        if (field._capability.status === 'unsupported') {
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:659:              data-testid={`schema-form-unsupported-${field.name}`}
src/tools/video-editor/hooks/useClientRender.ts:38:  canRenderMediaOnWeb: (options: Record<string, unknown>) => Promise<{
src/tools/video-editor/hooks/useClientRender.ts:44:  renderMediaOnWeb: (options: Record<string, unknown>) => Promise<unknown>;
src/tools/video-editor/hooks/useClientRender.ts:55:    const mod = await import('@remotion/web-renderer') as unknown as WebRendererModule;
src/tools/video-editor/hooks/useClientRender.ts:85:  result: unknown,
src/tools/video-editor/hooks/useClientRender.ts:106:  const record = result as Record<string, unknown>;
src/tools/video-editor/hooks/useClientRender.ts:124:    const saveResult = await (record.save as () => Promise<unknown>)();
src/tools/video-editor/hooks/useClientRender.ts:132:  value: unknown,
src/tools/video-editor/hooks/useClientRender.ts:154:  const record = value as Record<string, unknown>;
src/tools/video-editor/hooks/useClientRender.ts:237:      } satisfies Record<string, unknown>;
src/tools/video-editor/hooks/useClientRender.ts:267:        onProgress: (progress: unknown) => {
src/tools/video-editor/hooks/useClientRender.ts:270:      } satisfies Record<string, unknown>);
src/tools/video-editor/runtime/extensionSurface.test.ts:988:    expect(of.blockers).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1119:    expect(rt.config.outputFormats[0].blockers).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1135:    expect(of.blockers).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:1136:    expect(of.blockers[0]).toMatchObject({
src/tools/video-editor/runtime/extensionSurface.test.ts:1140:      reason: 'route-unsupported',
src/tools/video-editor/runtime/extensionSurface.test.ts:1142:    expect(of.nextActions).toEqual([of.blockers[0].nextAction]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1220:    expect(process.blockers).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1636:    expect(rt.config.outputFormats[1].blockers).toHaveLength(1);
src/tools/video-editor/hooks/useAssetOperations.test.tsx:301:          code: 'parser/unsupported-type' as const,
src/tools/video-editor/lib/mobile-interaction-model.ts:3:export type TimelineInputModality = 'mouse' | 'touch' | 'pen' | 'keyboard' | 'unknown';
src/tools/video-editor/lib/mobile-interaction-model.ts:76:      return 'unknown';
src/tools/video-editor/lib/mobile-interaction-model.ts:91:    inputModality: 'unknown',
src/tools/video-editor/runtime/commandRegistry.ts:320:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/commandRegistry.ts:506:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/commandRegistry.ts:650:        `Context menu target "${contribution.target}" from extension "${extensionId}" is reserved or unsupported.`,
src/tools/video-editor/runtime/commandRegistry.ts:786:        'command-registry/invoke-unknown-command',
src/tools/video-editor/runtime/commandRegistry.ts:787:        `Cannot execute unknown command "${commandId}".`,
src/tools/video-editor/runtime/effectRegistrationService.ts:228:          typeof (d as Record<string, unknown>).source === 'string' &&
src/tools/video-editor/runtime/effectRegistrationService.ts:229:          AUDIO_SOURCES.has((d as Record<string, unknown>).source as string) &&
src/tools/video-editor/runtime/effectRegistrationService.ts:230:          typeof (d as Record<string, unknown>).min === 'number' &&
src/tools/video-editor/runtime/effectRegistrationService.ts:231:          Number.isFinite((d as Record<string, unknown>).min as number) &&
src/tools/video-editor/runtime/effectRegistrationService.ts:232:          typeof (d as Record<string, unknown>).max === 'number' &&
src/tools/video-editor/runtime/effectRegistrationService.ts:233:          Number.isFinite((d as Record<string, unknown>).max as number);
src/tools/video-editor/runtime/effectRegistrationService.ts:310:  return sdkSchema.map((def) => ({ ...def })) as unknown as ParameterSchema;
src/tools/video-editor/runtime/effectRegistrationService.ts:317: * Per SD2: trusted component effects default to preview-only. Browser-export
src/tools/video-editor/runtime/effectRegistrationService.ts:329:    determinism: 'preview-only',
src/tools/video-editor/runtime/effectRegistrationService.ts:336:    determinism: contrib.allowBrowserExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/effectRegistrationService.ts:340:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/effectRegistrationService.ts:350:    determinism: contrib.allowWorkerExport ? 'preview-only' : 'preview-only',
src/tools/video-editor/runtime/effectRegistrationService.ts:354:          blockerReason: 'route-unsupported' as const,
src/tools/video-editor/runtime/effectRegistrationService.ts:360:  const determinism: DeterminismStatus = 'preview-only';
src/tools/video-editor/runtime/effectRegistrationService.ts:412:    detail?: Record<string, unknown>,
src/tools/video-editor/hooks/useWaveformData.test.tsx:14:  } as unknown as MockAudioBuffer;
src/tools/video-editor/compositions/AudioAnalysisProvider.test.tsx:34:  } as unknown as MockAudioBuffer;
src/tools/video-editor/hooks/useEffectResources.test.tsx:33:    useListResources: (...args: unknown[]) => mocks.useListResources(...args),
src/tools/video-editor/hooks/useEffectResources.test.tsx:34:    useListPublicResources: (...args: unknown[]) => mocks.useListPublicResources(...args),
src/tools/video-editor/hooks/useEffectResources.test.tsx:35:    useCreateResource: (...args: unknown[]) => mocks.useCreateResource(...args),
src/tools/video-editor/hooks/useEffectResources.test.tsx:36:    useUpdateResource: (...args: unknown[]) => mocks.useUpdateResource(...args),
src/tools/video-editor/hooks/useEffectResources.test.tsx:37:    useDeleteResource: (...args: unknown[]) => mocks.useDeleteResource(...args),
src/tools/video-editor/hooks/useEffectResources.test.tsx:437:        { route: 'browser-export' as const, status: 'blocked' as const, determinism: 'preview-only' as const },
src/tools/video-editor/hooks/useEffectResources.test.tsx:439:      determinism: 'preview-only' as const,
src/tools/video-editor/lib/external-drop-utils.ts:246:  onAssetDropError?: (error: unknown) => void;
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:50:  | 'unsupported';  // No widget — diagnostic placeholder fallback
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:60:  /** Host widget category, if any (undefined for unsupported). */
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:66:  /** Diagnostic emitted when this type is unsupported (null for supported/custom). */
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:88:  readonly validate: (value: unknown, definition: ParameterDefinition) => string | null;
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:131:/** Severity used for unsupported-type diagnostics. */
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:134:function unsupportedDiagnostic(type: string, message?: string, detail?: Record<string, unknown>): ExtensionDiagnostic {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:137:    code: 'schema/unsupported-type',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:140:    detail: detail ?? { unsupportedType: type },
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:144:function unsupportedTextureRefDiagnostic(): ExtensionDiagnostic {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:147:    code: 'schema/texture-ref-unsupported',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:150:    detail: { unsupportedType: 'textureRef' },
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:154:function isFiniteNumber(value: unknown): value is number {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:158:function isFiniteNumberVector(value: unknown, length: number): value is readonly number[] {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:290:    status: 'unsupported',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:292:    diagnostic: unsupportedTextureRefDiagnostic(),
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:322:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:341:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:365:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:383:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:394:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:407:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:428:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:443:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:472:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:476:        const isRequired = (def as Record<string, unknown>).isRequired;
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:487:      validate(value: unknown, def: ParameterDefinition): string | null {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:493:        const v = value as Record<string, unknown>;
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:541:    const d = type === 'textureRef' ? unsupportedTextureRefDiagnostic() : unsupportedDiagnostic(type);
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:551:    status: 'unsupported',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:561:        if (entry.status === 'unsupported' && entry.diagnostic) {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:570:      // Return an ephemeral unsupported entry with diagnostic
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:598:        if (entry.status === 'unsupported' && entry.diagnostic) {
src/tools/video-editor/runtime/liveRecording.ts:658:function inferDefaultSampleValue(data: Record<string, unknown>, parameterType: ParameterDefinition['type']): unknown {
src/tools/video-editor/runtime/liveRecording.ts:783:function readPath(value: Record<string, unknown>, path: string): unknown {
src/tools/video-editor/runtime/liveRecording.ts:784:  return path.split('.').reduce<unknown>((acc, segment) => {
src/tools/video-editor/runtime/liveRecording.ts:796:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/liveRecording.ts:808:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/runtime/liveRecording.ts:812:function stableHash(value: unknown): string {
src/tools/video-editor/runtime/liveRecording.ts:822:function sortObject(value: unknown): unknown {
src/tools/video-editor/runtime/liveRecording.ts:833:    const record = value as Record<string, unknown>;
src/tools/video-editor/runtime/liveRecording.ts:834:    return Object.keys(record).sort().reduce<Record<string, unknown>>((acc, key) => {
src/tools/video-editor/components/DiagnosticPanel/DiagnosticPanel.test.tsx:38:    code: 'schema/unknown-type',
src/tools/video-editor/runtime/extensionPackageManifest.ts:12: *   - Installed-pack blockers (strict errors that prevent activation).
src/tools/video-editor/runtime/extensionPackageManifest.ts:105:  input: Record<string, unknown>,
src/tools/video-editor/runtime/extensionPackageManifest.ts:106:): input is Record<string, unknown> & {
src/tools/video-editor/runtime/extensionPackageManifest.ts:107:  metadata: Record<string, unknown>;
src/tools/video-editor/runtime/extensionPackageManifest.ts:108:  manifest: Record<string, unknown>;
src/tools/video-editor/runtime/extensionPackageManifest.ts:127:function isWorkspaceSourceShape(input: Record<string, unknown>): boolean {
src/tools/video-editor/runtime/extensionPackageManifest.ts:212:  raw: Record<string, unknown>,
src/tools/video-editor/runtime/extensionPackageManifest.ts:222:        '(unknown)',
src/tools/video-editor/runtime/extensionPackageManifest.ts:235:  const manifest = raw.manifest as Record<string, unknown>;
src/tools/video-editor/runtime/extensionPackageManifest.ts:236:  const extId = (typeof manifest.id === 'string' ? manifest.id : '(unknown)') as string;
src/tools/video-editor/runtime/extensionPackageManifest.ts:335:  input: Record<string, unknown>,
src/tools/video-editor/runtime/extensionPackageManifest.ts:340:    return validateInstalledBundlePackage(input as unknown as InstalledExtensionPackage);
src/tools/video-editor/runtime/extensionPackageManifest.ts:354:        '(unknown)',
src/tools/video-editor/runtime/extensionPackageManifest.ts:466:  input: Record<string, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:125:  UseMutationResult<Resource, Error, CreateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:128:  mutate: UseMutationResult<Resource, Error, CreateVars, unknown>['mutate'];
src/tools/video-editor/hooks/useSequenceResources.ts:131:    options?: UseMutationOptions<Resource, Error, CreateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:135:  const base = mutation as unknown as Omit<
src/tools/video-editor/hooks/useSequenceResources.ts:136:    UseMutationResult<Resource, Error, CreateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:145:    )) as UseMutationResult<Resource, Error, CreateVars, unknown>['mutate'],
src/tools/video-editor/hooks/useSequenceResources.ts:151:      options?: UseMutationOptions<Resource, Error, CreateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:157:  UseMutationResult<Resource, Error, UpdateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:160:  mutate: UseMutationResult<Resource, Error, UpdateVars, unknown>['mutate'];
src/tools/video-editor/hooks/useSequenceResources.ts:163:    options?: UseMutationOptions<Resource, Error, UpdateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:167:  const base = mutation as unknown as Omit<
src/tools/video-editor/hooks/useSequenceResources.ts:168:    UseMutationResult<Resource, Error, UpdateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:177:    )) as UseMutationResult<Resource, Error, UpdateVars, unknown>['mutate'],
src/tools/video-editor/hooks/useSequenceResources.ts:183:      options?: UseMutationOptions<Resource, Error, UpdateVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:189:  UseMutationResult<void, Error, DeleteVars, unknown>,
src/tools/video-editor/hooks/useSequenceResources.ts:192:  mutate: UseMutationResult<void, Error, DeleteVars, unknown>['mutate'];
src/tools/video-editor/hooks/useSequenceResources.ts:195:    options?: UseMutationOptions<void, Error, DeleteVars, unknown>,
src/tools/video-editor/runtime/effectRegistrationService.test.ts:40:const TestComponent: FC<Record<string, unknown>> = () => null;
src/tools/video-editor/runtime/effectRegistrationService.test.ts:41:const ReplacementComponent: FC<Record<string, unknown>> = () => null;
src/tools/video-editor/runtime/effectRegistrationService.test.ts:81:  } as unknown as ReighExtension;
src/tools/video-editor/runtime/effectRegistrationService.test.ts:114:    const diags = validateEffectParameterSchema('not-an-array' as unknown as EffectParameterSchema);
src/tools/video-editor/runtime/effectRegistrationService.test.ts:226:      { name: 123 as unknown as string, label: 'Test', description: 'Desc', type: 'number' },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:256:      { name: 'x', label: 'X', description: 'D', type: 'number', min: 'abc' as unknown as number },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:264:      { name: 'x', label: 'X', description: 'D', type: 'number', max: 'abc' as unknown as number },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:288:      { name: 'x', label: 'X', description: 'D', type: 'number', step: 'abc' as unknown as number },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:296:      { name: 'x', label: 'X', description: 'D', type: 'number', default: 'abc' as unknown as number },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:333:      { name: 's', label: 'S', description: 'D', type: 'select', default: 123 as unknown as string },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:344:      { name: 'b', label: 'B', description: 'D', type: 'boolean', default: 'yes' as unknown as boolean },
src/tools/video-editor/runtime/effectRegistrationService.test.ts:374:      { name: 'a', label: 'A', description: 'D', type: 'audio-binding', default: 'bass' as unknown as Record<string, unknown> },
src/tools/video-editor/components/BatchLabelPanel.tsx:9:  readonly fields?: Record<string, unknown>;
src/tools/video-editor/components/BatchLabelPanel.tsx:21:  const [batchValues, setBatchValues] = useState<Record<string, unknown>>(defaults);
src/tools/video-editor/compositions/fallback/registry.generated.tsx:8:  params: unknown;
src/tools/video-editor/compositions/fallback/registry.generated.tsx:27:      {clip.clipType ?? 'unknown-sequence'}
src/tools/video-editor/lib/timeline-patch.test.ts:43:  payload?: Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.test.ts:82:      { version: 1, operations: null as unknown as TimelinePatchOperation[] },
src/tools/video-editor/lib/timeline-patch.test.ts:116:describe('validateTimelinePatch — unknown / malformed ops', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:117:  it('rejects unknown operation family with stable diagnostic code', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:124:    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
src/tools/video-editor/lib/timeline-patch.test.ts:143:        operations: [null as unknown as TimelinePatchOperation],
src/tools/video-editor/lib/timeline-patch.test.ts:163:        operations: [{ op: 'clip.remove', target: 42 as unknown as string }],
src/tools/video-editor/lib/timeline-patch.test.ts:733:          { op: 'unknown.op' as TimelinePatchAnyOpFamily, target: 'x' },
src/tools/video-editor/lib/timeline-patch.test.ts:737:    const unknownDiag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
src/tools/video-editor/lib/timeline-patch.test.ts:738:    expect(unknownDiag).toBeDefined();
src/tools/video-editor/lib/timeline-patch.test.ts:739:    expect(unknownDiag!.operationIndex).toBe(1);
src/tools/video-editor/lib/timeline-patch.test.ts:820:        operations: [{ op: 'clip.remove', target: 'c1', payload: 'bad' as unknown as Record<string, unknown> }],
src/tools/video-editor/lib/timeline-patch.test.ts:830:        operations: [{ op: 'clip.remove', target: 'c1', payload: [] as unknown as Record<string, unknown> }],
src/tools/video-editor/lib/timeline-patch.test.ts:839:        operations: [{ op: 'clip.remove', target: 'c1', payload: null as unknown as Record<string, unknown> }],
src/tools/video-editor/lib/timeline-patch.test.ts:869:// T4: Focused validation tests (unknown ops, malformed payloads,
src/tools/video-editor/lib/timeline-patch.test.ts:870://     unsupported mutations, overflow diagnostics, reserved ops, namespace ops)
src/tools/video-editor/lib/timeline-patch.test.ts:877:describe('validateTimelinePatch — unsupported asset/project mutations', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:878:  it('rejects asset.add as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:885:    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
src/tools/video-editor/lib/timeline-patch.test.ts:890:  it('rejects asset.create as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:897:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:900:  it('rejects asset.rename as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:907:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:910:  it('rejects project.update as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:919:    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
src/tools/video-editor/lib/timeline-patch.test.ts:924:  it('rejects project.remove as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:933:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:936:  it('rejects project.create as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:945:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:948:  it('rejects clip.rename as unknown operation (not in active or reserved sets)', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:955:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:958:  it('rejects track.move as unknown operation', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:965:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:1221:            payload: null as unknown as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.test.ts:1234:            key: 42 as unknown as string,
src/tools/video-editor/lib/timeline-patch.test.ts:1267:            key: true as unknown as string,
src/tools/video-editor/lib/timeline-patch.test.ts:1298:            payload: ['not', 'an', 'object'] as unknown as Record<
src/tools/video-editor/lib/timeline-patch.test.ts:1300:              unknown
src/tools/video-editor/lib/timeline-patch.test.ts:1319:            op: 'extension.unsupported.command' as TimelinePatchAnyOpFamily,
src/tools/video-editor/lib/timeline-patch.test.ts:1326:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:1338:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:1350:    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:1362:      operations: 'not-an-array' as unknown as TimelinePatchOperation[],
src/tools/video-editor/lib/timeline-patch.test.ts:1373:      operations: undefined as unknown as TimelinePatchOperation[],
src/tools/video-editor/lib/timeline-patch.test.ts:1382:          { op: true as unknown as string, target: 'x' } as TimelinePatchOperation,
src/tools/video-editor/lib/timeline-patch.test.ts:1396:          { op: 123 as unknown as string, target: 'x' } as TimelinePatchOperation,
src/tools/video-editor/lib/timeline-patch.test.ts:1410:            payload: (() => {}) as unknown as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.test.ts:1428:            payload: 42 as unknown as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.test.ts:1446:            payload: true as unknown as Record<string, unknown>,
src/tools/video-editor/lib/timeline-patch.test.ts:1462:            key: null as unknown as string,
src/tools/video-editor/lib/timeline-patch.test.ts:1482:    const unknownDiags = result.diagnostics.filter(
src/tools/video-editor/lib/timeline-patch.test.ts:1483:      (d) => d.code === 'timeline-patch/unknown-op',
src/tools/video-editor/lib/timeline-patch.test.ts:1485:    expect(unknownDiags).toHaveLength(3);
src/tools/video-editor/lib/timeline-patch.test.ts:1486:    expect(unknownDiags[0].operationIndex).toBe(0);
src/tools/video-editor/lib/timeline-patch.test.ts:1487:    expect(unknownDiags[1].operationIndex).toBe(1);
src/tools/video-editor/lib/timeline-patch.test.ts:1488:    expect(unknownDiags[2].operationIndex).toBe(2);
src/tools/video-editor/lib/timeline-patch.test.ts:1495:          { op: 'unknown.op' as TimelinePatchAnyOpFamily, target: '' },
src/tools/video-editor/lib/timeline-patch.test.ts:1497:          { op: 'clip.split' as TimelinePatchAnyOpFamily, target: 'c1', payload: null as unknown as Record<string, unknown> },
src/tools/video-editor/lib/timeline-patch.test.ts:1778:function makeMinimalTimelineData(overrides: Record<string, unknown> = {}) {
src/tools/video-editor/lib/timeline-patch.test.ts:1783:    clips: (overrides.clips as Array<Record<string, unknown>>) ?? [],
src/tools/video-editor/lib/timeline-patch.test.ts:1784:    tracks: (overrides.tracks as Array<Record<string, unknown>>) ?? [],
src/tools/video-editor/lib/timeline-patch.test.ts:1789:    app: (overrides.app as Record<string, unknown>) ?? {},
src/tools/video-editor/lib/timeline-patch.test.ts:1791:  const clipsData = (config.clips ?? []) as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-patch.test.ts:1792:  const tracksData = (config.tracks ?? []) as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-patch.test.ts:1800:  const assets = (overrides.assets as Record<string, unknown>) ?? {};
src/tools/video-editor/lib/timeline-patch.test.ts:1807:    meta: {} as Record<string, Record<string, unknown>>,
src/tools/video-editor/lib/timeline-patch.test.ts:2063:    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2082:    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2118:    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2119:    const settings = extConfig.settings as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2139:    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2140:    const settings = extConfig.settings as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2165:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2206:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2304:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2343:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2376:      const detail = overflowDiag.detail as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:2386:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2421:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2464:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2495:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2528:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2563:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2596:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2630:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2671:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2706:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2741:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:2754:    const extBefore = { ...(appBefore['com.example.ext'] as Record<string, unknown>) };
src/tools/video-editor/lib/timeline-patch.test.ts:2771:    const extAfter = { ...(appAfter['com.example.ext'] as Record<string, unknown>) };
src/tools/video-editor/lib/timeline-patch.test.ts:2779:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:3644:  it('asset.remove for unknown asset still produces diff entry', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:3652:        operations: [makeOp('asset.remove', 'unknown-asset')],
src/tools/video-editor/lib/timeline-patch.test.ts:3657:    const entry = result.diff.entries.find((e: any) => e.target === 'unknown-asset');
src/tools/video-editor/lib/timeline-patch.test.ts:3683:    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:3797:    const extConfig = appConfig['com.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:3882:    const extConfig = appConfig['com.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:3969:    const extConfig = result.nextData!.config.app['com.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:4101:        operations: [{ op: 'unknown.op' as TimelinePatchAnyOpFamily, target: 'x' }],
src/tools/video-editor/lib/timeline-patch.test.ts:4109:    expect(result.diagnostics.some((d: any) => d.code === 'timeline-patch/unknown-op')).toBe(true);
src/tools/video-editor/lib/timeline-patch.test.ts:4203:    expect((nextApp['com.annotations.ext'] as Record<string, unknown>).ann_001).toEqual(annotation);
src/tools/video-editor/lib/timeline-patch.test.ts:4235:    const stored1 = (result1.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
src/tools/video-editor/lib/timeline-patch.test.ts:4241:    const stored2 = (result2.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
src/tools/video-editor/lib/timeline-patch.test.ts:4277:    const finalApp = currentData.config.app['com.annotations.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:4338:    expect((r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(materialRef);
src/tools/video-editor/lib/timeline-patch.test.ts:4341:    const stored = (r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy;
src/tools/video-editor/lib/timeline-patch.test.ts:4371:    expect((r3.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(updatedRef);
src/tools/video-editor/lib/timeline-patch.test.ts:4411:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4444:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4478:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4502:    const nextTracks = result.nextData!.config.tracks as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-patch.test.ts:4504:    const nextClips = result.nextData!.config.clips as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-patch.test.ts:4523:    // An invalid patch (unknown operation)
src/tools/video-editor/lib/timeline-patch.test.ts:4527:          makeOp('unknown.op' as any, 'target', {}),
src/tools/video-editor/lib/timeline-patch.test.ts:4572:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4609:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4653:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4680:    const detail = diag!.detail as Record<string, unknown>;
src/tools/video-editor/lib/timeline-patch.test.ts:4695:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4733:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4820:    const existingEntries: Record<string, unknown> = {};
src/tools/video-editor/lib/timeline-patch.test.ts:4888:    const finalApp = rw1.nextData!.config.app['com.example.ext'] as Record<string, unknown>;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:49:function makeRuntime(entries: PackageEntryInput[], extensions: unknown[] = []) {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:87:function makeRepository(overrides?: Partial<Record<string, unknown>>) {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:838:      let resolveLoad: (value: unknown) => void = () => {};
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:971:      let resolveSave: (value: unknown) => void = () => {};
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:1447:    } as unknown as DiagnosticCollection,
src/tools/video-editor/runtime/agentToolRegistry.ts:201:  detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolRegistry.ts:392:    detail?: Record<string, unknown>,
src/tools/video-editor/runtime/agentToolRegistry.ts:446:            `Tool "${toolId}" (extension "${extensionId}") declares unsupported result family "${String(family)}".`,
src/tools/video-editor/runtime/agentToolRegistry.ts:618:        const resultDiags = (result as unknown as Record<string, unknown>).diagnostics;
src/tools/video-editor/runtime/agentToolRegistry.ts:622:              const d = diag as Record<string, unknown>;
src/tools/video-editor/runtime/agentToolRegistry.ts:629:                d.detail as Record<string, unknown> | undefined,
src/tools/video-editor/runtime/agentToolRegistry.ts:642:        (result as unknown as Record<string, unknown>).family === 'generation/session'
src/tools/video-editor/runtime/agentToolRegistry.ts:748:    session.complete = (result?: Record<string, unknown>) => {
src/tools/video-editor/runtime/agentToolRegistry.ts:942:    error: unknown,
src/tools/video-editor/runtime/agentToolRegistry.ts:973:  function readStringArray(value: unknown): readonly string[] | undefined {
src/tools/video-editor/runtime/agentToolRegistry.ts:979:  function isNonEmptyString(value: unknown): value is string {
src/tools/video-editor/lib/source-map-runtime.test.ts:24:  value: unknown;
src/tools/video-editor/lib/source-map-runtime.test.ts:29:  const store: Record<string, Record<string, unknown>> = {};
src/tools/video-editor/lib/source-map-runtime.test.ts:32:    getApp(extId: string): Record<string, unknown> {
src/tools/video-editor/lib/source-map-runtime.test.ts:35:    setApp(extId: string, data: Record<string, unknown>): void {
src/tools/video-editor/lib/source-map-runtime.test.ts:38:    getRaw(extId: string, key: string): unknown {
src/tools/video-editor/lib/source-map-runtime.test.ts:41:    setRaw(extId: string, key: string, value: unknown): void {
src/tools/video-editor/lib/source-map-runtime.test.ts:53:    getAll(): Record<string, Record<string, unknown>> {
src/tools/video-editor/lib/source-map-runtime.test.ts:93:      app: store.getAll() as Record<string, unknown>,
src/tools/video-editor/lib/source-map-runtime.test.ts:156:      expect((raw as Record<string, unknown>).id).toBe(entry.id);
src/tools/video-editor/lib/source-map-runtime.test.ts:175:      expect((raw as Record<string, unknown>).meta).toEqual({ priority: 'high', tags: ['foo'] });
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:28:function workspaceSource(overrides?: Partial<ExtensionManifest>): Record<string, unknown> {
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:382:    const result = validatePackage(pack as unknown as Record<string, unknown>);
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:394:  it('distinguishes workspace source warnings from installed blockers', () => {
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:447:    expect(detectPackageForm(pack as unknown as Record<string, unknown>)).toBe('installed-bundle');
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:505:      code: 'unknown/code',
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:506:      message: 'unknown',
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:630:// Cross-cutting: distinguishing workspace source warnings from installed-pack blockers
src/tools/video-editor/runtime/extensionPackageManifest.test.ts:633:describe('distinction between workspace source warnings and installed-pack blockers', () => {
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:211:  it('diagnoses malformed metadata and unsupported source kinds', () => {
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:231:        'live-binding/unsupported-source-kind',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:239:        'live_binding_unsupported_source_kind',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:415:        'live-uniform-binding/unsupported-source-kind',
src/tools/video-editor/runtime/exportGuard.test.ts:8:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/runtime/exportGuard.test.ts:12:  ExportGuardResult,
src/tools/video-editor/runtime/exportGuard.test.ts:288:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:289:    expect(result.unknownEffects).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:290:    expect(result.unknownTransitions).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:291:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:298:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:299:    expect(result.unknownEffects).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:300:    expect(result.unknownTransitions).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:301:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:317:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:318:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:341:// Export config scan — live binding blockers
src/tools/video-editor/runtime/exportGuard.test.ts:344:describe('scanExportConfig — live binding blockers', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:350:    binding: Record<string, unknown>,
src/tools/video-editor/runtime/exportGuard.test.ts:403:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:405:    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toHaveLength(6);
src/tools/video-editor/runtime/exportGuard.test.ts:439:    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:440:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:445:// Export config scan — unknown clip type
src/tools/video-editor/runtime/exportGuard.test.ts:448:describe('scanExportConfig — unknown clip type', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:452:  it('emits error diagnostic for truly unknown clip type', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:459:    expect(diag.code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/exportGuard.test.ts:462:    expect(result.unknownClipTypes).toEqual(['alien-format']);
src/tools/video-editor/runtime/exportGuard.test.ts:463:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:481:    expect(diag.code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/exportGuard.test.ts:483:    // Extension-declared clip types do NOT appear in unknownClipTypes
src/tools/video-editor/runtime/exportGuard.test.ts:484:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:485:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:535:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:536:    expect(result.unknownEffects).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:537:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:542:// Export config scan — unknown effects
src/tools/video-editor/runtime/exportGuard.test.ts:545:describe('scanExportConfig — unknown effects', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:549:  it('emits error for unknown entrance effect', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:558:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:561:    expect(result.unknownEffects).toEqual(['crazy-spin']);
src/tools/video-editor/runtime/exportGuard.test.ts:562:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:573:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:590:    const planned = planRender({ diagnostics: [...scan.findings, ...scan.blockers] });
src/tools/video-editor/runtime/exportGuard.test.ts:592:    expect(planned.canBrowserExport).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:595:      blockers: [
src/tools/video-editor/runtime/exportGuard.test.ts:604:  it('emits error for unknown continuous effect', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:610:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:611:    expect(result.unknownEffects).toEqual(['hyperspace']);
src/tools/video-editor/runtime/exportGuard.test.ts:614:  it('emits error for unknown exit effect', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:620:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:621:    expect(result.unknownEffects).toEqual(['explode-out']);
src/tools/video-editor/runtime/exportGuard.test.ts:624:  it('emits warning for extension-declared (inactive) clipType with unknown effect', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:641:    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/exportGuard.test.ts:643:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:644:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:658:          determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:663:              determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:668:              determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:669:              blockerReason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:690:          blockerReason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:696:        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:699:        reason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:707:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:709:        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:712:        reason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:715:    expect(result.unknownEffects).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:716:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:783:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:791:    expect(result.unknownEffects).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:792:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:795:  it('emits per-route blockers for inactive provider records across all GUARD_ROUTES', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:829:    expect(result.blockers).toHaveLength(3);
src/tools/video-editor/runtime/exportGuard.test.ts:830:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:833:  it('emits unknown-route-support warnings for provider effects with unknown worker-export capability', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:844:          determinism: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:858:              status: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:859:              determinism: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:869:    // One warning for unknown worker-export
src/tools/video-editor/runtime/exportGuard.test.ts:873:        code: 'export/unknown-route-support',
src/tools/video-editor/runtime/exportGuard.test.ts:885:        id: 'export.effect.c1.exit.unclassified-effect.worker-export.unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:888:        reason: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:892:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:893:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:925:// Export config scan — unknown transitions
src/tools/video-editor/runtime/exportGuard.test.ts:928:describe('scanExportConfig — unknown transitions', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:932:  it('emits error for unknown transition', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:941:    expect(result.diagnostics[0].code).toBe('export/unknown-transition-type');
src/tools/video-editor/runtime/exportGuard.test.ts:943:    expect(result.unknownTransitions).toEqual(['star-wipe']);
src/tools/video-editor/runtime/exportGuard.test.ts:944:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:947:  it('emits warning for extension-declared (inactive) clipType with unknown transition', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:964:    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/exportGuard.test.ts:966:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:967:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:979:  it('collects multiple unknown types in one scan', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:993:    // 4 diagnostics: unknown clip type + unknown entrance + unknown transition + unknown continuous
src/tools/video-editor/runtime/exportGuard.test.ts:995:    expect(result.unknownClipTypes).toEqual(['alien-format']);
src/tools/video-editor/runtime/exportGuard.test.ts:996:    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
src/tools/video-editor/runtime/exportGuard.test.ts:997:    expect(result.unknownTransitions).toEqual(['star-wipe']);
src/tools/video-editor/runtime/exportGuard.test.ts:998:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1001:  it('handles multiple clips with same unknown types without duplication', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1008:    // 2 diagnostics (one per clip) but only one entry in unknownClipTypes
src/tools/video-editor/runtime/exportGuard.test.ts:1010:    expect(result.unknownClipTypes).toEqual(['alien-format']);
src/tools/video-editor/runtime/exportGuard.test.ts:1029:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1039:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1049:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1052:  it('emits error for unknown continuous effect on effect-layer clip', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1061:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:1064:    expect(result.unknownEffects).toEqual(['hyperspace']);
src/tools/video-editor/runtime/exportGuard.test.ts:1065:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1068:  it('emits error for unknown entrance effect on effect-layer clip', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1077:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:1079:    expect(result.unknownEffects).toEqual(['crazy-spin']);
src/tools/video-editor/runtime/exportGuard.test.ts:1080:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1083:  it('emits error for unknown exit effect on effect-layer clip', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1092:    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
src/tools/video-editor/runtime/exportGuard.test.ts:1094:    expect(result.unknownEffects).toEqual(['explode-out']);
src/tools/video-editor/runtime/exportGuard.test.ts:1095:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1116:    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
src/tools/video-editor/runtime/exportGuard.test.ts:1120:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1121:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1126:// Effect-layer clip with unknown clip type + unknown effects combined
src/tools/video-editor/runtime/exportGuard.test.ts:1130:  it('collects both unknown clip type and unknown effect for effect-layer style clips', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1143:    // 3 diagnostics: unknown clip type + unknown continuous + unknown entrance
src/tools/video-editor/runtime/exportGuard.test.ts:1145:    expect(result.unknownClipTypes).toEqual(['custom-effect-layer']);
src/tools/video-editor/runtime/exportGuard.test.ts:1146:    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
src/tools/video-editor/runtime/exportGuard.test.ts:1147:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1167:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1168:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1169:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1202:    expect(result.blockers).toHaveLength(3);
src/tools/video-editor/runtime/exportGuard.test.ts:1203:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1207:    const clip = makeClip('c1', { clipType: 'preview-only-clip' });
src/tools/video-editor/runtime/exportGuard.test.ts:1209:      clipTypeRecord('preview-only-clip', {
src/tools/video-editor/runtime/exportGuard.test.ts:1211:        contributionId: 'ext.preview:clipType:preview-only-clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1214:          determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1219:              determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1224:              determinism: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1225:              blockerReason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1241:        contributionId: 'ext.preview:clipType:preview-only-clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1244:          clipType: 'preview-only-clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1246:          blockerReason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1252:        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1255:        reason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1259:        contributionId: 'ext.preview:clipType:preview-only-clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1260:        detail: { clipType: 'preview-only-clip', provenance: 'trusted-loader' },
src/tools/video-editor/runtime/exportGuard.test.ts:1263:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:1265:        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1268:        reason: 'preview-only',
src/tools/video-editor/runtime/exportGuard.test.ts:1271:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1274:  it('emits warning for unknown route support on a clip type', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1282:          determinism: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:1296:              status: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:1297:              determinism: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:1310:        code: 'export/unknown-route-support',
src/tools/video-editor/runtime/exportGuard.test.ts:1322:        id: 'export.clipType.c1.unclassified-clip.worker-export.unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:1325:        reason: 'unknown',
src/tools/video-editor/runtime/exportGuard.test.ts:1328:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1329:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1332:  it('still blocks truly unknown clip types not in registry, not in built-in, not extension-declared', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1341:        code: 'export/unknown-clip-type',
src/tools/video-editor/runtime/exportGuard.test.ts:1346:    expect(result.unknownClipTypes).toEqual(['alien-format']);
src/tools/video-editor/runtime/exportGuard.test.ts:1357:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:1365:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1377:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1378:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1381:  it('emits exact missing materializer blockers for clip and postprocess shader metadata', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1435:    expect(result.blockers).toEqual(expect.arrayContaining([
src/tools/video-editor/runtime/exportGuard.test.ts:1447:    expect(planRender({ diagnostics: result.findings }).canBrowserExport).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1481:    expect(result.blockers).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1482:    expect(result.unknownClipTypes).toEqual([]);
src/tools/video-editor/runtime/exportGuard.test.ts:1483:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1486:  it('emits per-route blockers for active clip types with blocked worker-export', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1548:    expect(result.blockers).toEqual([
src/tools/video-editor/runtime/exportGuard.test.ts:1556:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1572:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1585:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1591:      (result as { diagnostics: unknown[] }).diagnostics = [];
src/tools/video-editor/lib/serialize.test.ts:52:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:90:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:151:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:193:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:222:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:284:        } as unknown as object),
src/tools/video-editor/lib/serialize.test.ts:309:    } as unknown as ResolvedTimelineConfig, repaired.pinnedShotGroups);
src/tools/video-editor/lib/serialize.test.ts:398:  it('still rejects unknown sibling keys outside the app extension namespace', () => {
src/tools/video-editor/lib/serialize.test.ts:404:    } as unknown as TimelineConfig);
src/tools/video-editor/lib/serialize.test.ts:471:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:564:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:590:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:633:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:671:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:766:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:803:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/lib/serialize.test.ts:875:    } as unknown as ResolvedTimelineConfig;
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.tsx:308:    return 'unknown';
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.tsx:348:      const e = result as { matches?: unknown[] };
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.tsx:352:      const e = result as { findings?: unknown[] };
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.tsx:364:  const r = result as unknown as Record<string, unknown>;
src/tools/video-editor/lib/sequence-drafts.ts:48:): Record<string, unknown> => ({ ...params });
src/tools/video-editor/lib/sequence-drafts.ts:73:  } as unknown as ClipMeta;
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:27:function isRecord(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:41:  return diagnostics.find((diagnostic) => diagnostic.extensionId)?.extensionId ?? '(unknown)';
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:53:    label: label ?? id ?? '(unknown)',
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:84:function settingValueMatchesType(value: unknown, rawType: unknown): boolean {
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:115:  values: Record<string, unknown>,
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:116:  rawSchema: unknown,
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:138:    const unknownKey = Object.keys(values).find((key) => !knownKeys.has(key));
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:139:    if (unknownKey) {
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:140:      return `Unknown setting "${unknownKey}" is not allowed by the manifest schema.`;
src/tools/video-editor/lib/timeline-data.ts:419:function isAssetResolverArg(value: unknown): value is AssetResolver {
src/tools/video-editor/lib/timeline-data.ts:423:    && typeof (value as { resolveAssetUrl?: unknown }).resolveAssetUrl === 'function'
src/tools/video-editor/compositions/TimelineRenderer.tsx:69://      package isn't installed OR the clipType is unknown.
src/tools/video-editor/compositions/TimelineRenderer.tsx:105:    params: unknown;
src/tools/video-editor/compositions/TimelineRenderer.tsx:122:    | FC<{ clip: ResolvedTimelineClip; params: unknown; theme: RuntimeTheme; fps: number }>
src/tools/video-editor/compositions/TimelineRenderer.tsx:129:    return <UnknownClipPlaceholderSequence clip={clip} fps={fps} reason="unsupported" />;
src/tools/video-editor/compositions/TimelineRenderer.tsx:212:): Record<string, unknown> {
src/tools/video-editor/compositions/TimelineRenderer.tsx:213:  const record: Record<string, unknown> = {};
src/tools/video-editor/compositions/TimelineRenderer.tsx:315:const isRecord = (value: unknown): value is Record<string, unknown> => (
src/tools/video-editor/compositions/TimelineRenderer.tsx:319:function numericValue(value: unknown): number | undefined {
src/tools/video-editor/compositions/TimelineRenderer.tsx:328:function normalizedProgress(value: unknown): number | undefined {
src/tools/video-editor/compositions/TimelineRenderer.tsx:335:function firstString(...values: unknown[]): string | undefined {
src/tools/video-editor/compositions/TimelineRenderer.tsx:342:function sampleDataRecord(sample: LiveSample | undefined): Record<string, unknown> | undefined {
src/tools/video-editor/compositions/TimelineRenderer.tsx:347:function sampleMetadataRecord(sample: LiveSample | undefined): Record<string, unknown> | undefined {
src/tools/video-editor/compositions/TimelineRenderer.tsx:692:          Live binding unresolved: {statuses || 'unknown'}
src/tools/video-editor/compositions/TimelineRenderer.tsx:785:    data-testid="unsupported-postprocess-shader-export"
src/tools/video-editor/compositions/TimelineRenderer.tsx:887:    let baseParams: Record<string, unknown>;
src/tools/video-editor/compositions/TimelineRenderer.tsx:890:      baseParams = (clip.params as Record<string, unknown>) ?? {};
src/tools/video-editor/compositions/TimelineRenderer.tsx:918:  // Extension renderers are stored as `Record<string, unknown> | Function`.
src/tools/video-editor/compositions/TimelineRenderer.tsx:927:      reason="unsupported"
src/tools/video-editor/compositions/TimelineRenderer.tsx:1070:                    reason="unsupported"
src/tools/video-editor/compositions/TimelineRenderer.tsx:1093:                reason="unsupported"
src/tools/video-editor/compositions/TimelineRenderer.tsx:1105:              reason="unsupported"
src/tools/video-editor/compositions/TimelineRenderer.tsx:1110:        // SD-025 (Sprint 3): loud placeholder for unknown clipTypes that
src/tools/video-editor/compositions/TimelineRenderer.tsx:1121:              reason="unsupported"
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:294:function isJsonObject(value: unknown): value is Record<string, unknown> {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:298:function valueMatchesJsonSchemaType(value: unknown, rawType: unknown): boolean {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:329:  values: Record<string, unknown>,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:330:  rawSchema: unknown,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:352:    const unknownKey = Object.keys(values).find((key) => !knownKeys.has(key));
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:353:    if (unknownKey) {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:354:      return `Unknown setting "${unknownKey}" is not allowed by the manifest schema.`;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:418:  const [editValues, setEditValues] = useState<Record<string, unknown>>({});
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:447:    // Route unsupported schemas to raw JSON mode.
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:514:  const handleFieldChange = useCallback((key: string, value: unknown) => {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:596:    let parsed: unknown;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:615:      parsed as Record<string, unknown>,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:631:      values: parsed as Record<string, unknown>,
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:715:      return Object.keys(parsed as Record<string, unknown>).length > 0;
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:721:  // Schema diagnostic message for unsupported schemas
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:909:      {/* Raw JSON mode — unsupported schemas */}
src/tools/video-editor/runtime/commandRegistry.test.ts:524:  it('unregistering an unknown extension does nothing', () => {
src/tools/video-editor/runtime/commandRegistry.test.ts:731:  it('emits diagnostic for unknown command invocation', async () => {
src/tools/video-editor/runtime/commandRegistry.test.ts:736:    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-unknown-command');
src/tools/video-editor/runtime/commandRegistry.test.ts:1128:  it('getCommand returns undefined for unknown commands', () => {
src/tools/video-editor/runtime/commandRegistry.test.ts:1133:  it('getKeybinding returns undefined for unknown keys', () => {
src/tools/video-editor/runtime/extensionSettings.ts:94:function adaptProperty(raw: Record<string, unknown>): StandardSchemaProperty {
src/tools/video-editor/runtime/extensionSettings.ts:159:  const schemaObj = raw as Record<string, unknown>;
src/tools/video-editor/runtime/extensionSettings.ts:188:  const props = rawProperties as Record<string, unknown>;
src/tools/video-editor/runtime/extensionSettings.ts:208:      adaptedProperties[key] = adaptProperty(rawProp as Record<string, unknown>);
src/tools/video-editor/components/sidecar-editing.ts:8:  readonly default?: unknown;
src/tools/video-editor/components/sidecar-editing.ts:11:export function createSchemaDefaults(schema: SidecarWidgetSchema): Record<string, unknown> {
src/tools/video-editor/components/sidecar-editing.ts:13:    return schema.reduce<Record<string, unknown>>((defaults, field: ParameterDefinition) => {
src/tools/video-editor/components/sidecar-editing.ts:19:  return Object.entries((schema as StandardSchema).properties).reduce<Record<string, unknown>>(
src/tools/video-editor/components/sidecar-editing.ts:36:function fallbackForType(type: string): unknown {
src/tools/video-editor/compositions/VisualClip.tsx:120:    data-testid="unsupported-asset-placeholder"
src/tools/video-editor/compositions/VisualClip.tsx:149:      {`clipType '${clipType}' references unsupported asset type '${assetType ?? 'unknown'}' — clip will not appear in render`}
src/tools/video-editor/compositions/VisualClip.tsx:156:    data-testid="unsupported-clip-shader-export"
src/tools/video-editor/compositions/VisualClip.tsx:264:const isRecord = (value: unknown): value is Record<string, unknown> => (
src/tools/video-editor/compositions/VisualClip.tsx:275:  return Array.isArray(refs) ? refs.filter(isRecord) as unknown as readonly RenderMaterialRef[] : [];
src/tools/video-editor/compositions/VisualClip.tsx:517:        transitionStyle = (renderer as (progress: number, params: Record<string, unknown>) => CSSProperties)(
src/tools/video-editor/components/SegmentCaptionEditor.tsx:10:  readonly fields?: Record<string, unknown>;
src/tools/video-editor/components/SegmentCaptionEditor.tsx:20:function createSegment(id: string, fields: Record<string, unknown>): EditableCaptionSegment {
src/tools/video-editor/components/SegmentCaptionEditor.tsx:38:  const updateSegmentField = (index: number, name: string, value: unknown) => {
src/tools/video-editor/lib/sha256.test.ts:103:    } as unknown as Response;
src/tools/video-editor/lib/sha256.test.ts:439:    } as unknown as Response;
src/tools/video-editor/runtime/processCommandRegistration.test.ts:29:    blockers: [],
src/tools/video-editor/hooks/useActiveTaskClips.ts:22:  params: Record<string, unknown> | null;
src/tools/video-editor/hooks/useActiveTaskClips.ts:142:    params: task.params as Record<string, unknown> | null,
src/tools/video-editor/runtime/extensionStateRepository.ts:121:  readonly values: Record<string, unknown>;
src/tools/video-editor/runtime/extensionStateRepository.ts:169:  readonly detail?: Record<string, unknown>;
src/tools/video-editor/runtime/extensionStateRepository.ts:564:  values: Record<string, unknown>,
src/tools/video-editor/runtime/extensionStateRepository.ts:581:  detail?: Record<string, unknown>,
src/tools/video-editor/lib/assetParserRuntime.ts:23:  UNSUPPORTED_TYPE: 'parser/unsupported-type' as const,
src/tools/video-editor/lib/assetParserRuntime.ts:30:  /** The parser returned unknown top-level registry fields that were rejected. */
src/tools/video-editor/lib/assetParserRuntime.ts:290: * Any top-level metadata key not in this set is treated as an unknown
src/tools/video-editor/lib/assetParserRuntime.ts:310: * Returns a diagnostic when unknown fields are present (the fields are
src/tools/video-editor/lib/assetParserRuntime.ts:314:  metadata: Record<string, unknown> | undefined,
src/tools/video-editor/lib/assetParserRuntime.ts:320:  const unknownFields: string[] = [];
src/tools/video-editor/lib/assetParserRuntime.ts:325:      unknownFields.push(key);
src/tools/video-editor/lib/assetParserRuntime.ts:329:  if (unknownFields.length === 0) return null;
src/tools/video-editor/lib/assetParserRuntime.ts:335:      `Parser "${parserId}" returned unknown metadata fields ` +
src/tools/video-editor/lib/assetParserRuntime.ts:336:      `[${unknownFields.join(', ')}] — these will be stripped.`,
src/tools/video-editor/lib/assetParserRuntime.ts:340:      rejectedFields: unknownFields,
src/tools/video-editor/lib/assetParserRuntime.ts:356:  record: Record<string, unknown>,
src/tools/video-editor/lib/assetParserRuntime.ts:383:  incoming: Record<string, unknown>,
src/tools/video-editor/lib/assetParserRuntime.ts:384:): Record<string, unknown> => {
src/tools/video-editor/lib/assetParserRuntime.ts:385:  const normalized: Record<string, unknown> = {};
src/tools/video-editor/lib/assetParserRuntime.ts:399:    const records = incoming.enrichment as Record<string, unknown>[];
src/tools/video-editor/lib/assetParserRuntime.ts:418:    const extObj = normalized.extensions as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:419:    const cleaned: Record<string, unknown> = {};
src/tools/video-editor/lib/assetParserRuntime.ts:466:  const mergedEntry: Record<string, unknown> = {};
src/tools/video-editor/lib/assetParserRuntime.ts:471:      mergedEntry[field] = (existingEntry as Record<string, unknown>)[field];
src/tools/video-editor/lib/assetParserRuntime.ts:476:  const existingMetadata: Record<string, unknown> =
src/tools/video-editor/lib/assetParserRuntime.ts:478:      ? { ...(existingEntry.metadata as Record<string, unknown>) }
src/tools/video-editor/lib/assetParserRuntime.ts:489:    const rawMetadata = result.metadata as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:491:    // Reject unknown output fields
src/tools/video-editor/lib/assetParserRuntime.ts:510:        const incObj = incoming[hostKey] as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:513:            ...(existing as Record<string, unknown>),
src/tools/video-editor/lib/assetParserRuntime.ts:524:      const incEnrichment = incoming.enrichment as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:528:          ? (existingMetadata.enrichment as Record<string, unknown>)
src/tools/video-editor/lib/assetParserRuntime.ts:532:      const mergedEnrichment: Record<string, unknown> = {
src/tools/video-editor/lib/assetParserRuntime.ts:539:          ? (existingEnrichment.claims as unknown[])
src/tools/video-editor/lib/assetParserRuntime.ts:554:      const existingExts = existingMetadata.extensions as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:555:      const incomingExts = incoming.extensions as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:571:              ? (existingExts[nsKey] as Record<string, unknown>)
src/tools/video-editor/lib/assetParserRuntime.ts:575:            ...(nsValue as Record<string, unknown>),
src/tools/video-editor/lib/assetParserRuntime.ts:589:    entry: mergedEntry as unknown as AssetRegistryEntry,
src/tools/video-editor/lib/assetParserRuntime.ts:615: *     `parser/unsupported-type` diagnostics and are skipped.
src/tools/video-editor/lib/assetParserRuntime.ts:641:  let accumulatedMetadata: Record<string, unknown> | undefined =
src/tools/video-editor/lib/assetParserRuntime.ts:643:      ? { ...(existingEntry.metadata as Record<string, unknown>) }
src/tools/video-editor/lib/assetParserRuntime.ts:694:            `cannot process this file — unsupported type.`,
src/tools/video-editor/lib/assetParserRuntime.ts:699:            reason: 'unsupported-type',
src/tools/video-editor/lib/assetParserRuntime.ts:716:        ? (Object.freeze({ ...accumulatedMetadata }) as unknown as import('@reigh/editor-sdk').AssetMetadata)
src/tools/video-editor/lib/assetParserRuntime.ts:776:        const rawMeta = result.metadata as Record<string, unknown>;
src/tools/video-editor/lib/assetParserRuntime.ts:782:    } catch (error: unknown) {
src/tools/video-editor/lib/assetParserRuntime.ts:857: * diagnostics (unsupported-type and oversized-input).
src/tools/video-editor/hooks/useAgentSession.test.tsx:326:    // drops unknown fields, so proposals would be lost.
src/tools/video-editor/runtime/ports.ts:46:  Lightbox: ComponentType<Record<string, unknown>>;
src/tools/video-editor/runtime/ports.ts:63:  log: (...args: unknown[]) => void;
src/tools/video-editor/runtime/ports.ts:64:  warn: (...args: unknown[]) => void;
src/tools/video-editor/runtime/ports.ts:65:  error: (...args: unknown[]) => void;
src/tools/video-editor/lib/generated-lanes.ts:11:    sequence_lane?: unknown;
src/tools/video-editor/lib/generated-lanes.ts:12:    artifact_id?: unknown;
src/tools/video-editor/lib/generated-lanes.ts:27:): unknown => clip?.generation?.sequence_lane;
src/tools/video-editor/hooks/useClipResize.test.tsx:328:  it('does not clamp visual-track video resize when asset duration is unknown', () => {
src/tools/video-editor/runtime/renderability.test.ts:105:      'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:108:      'unknown',
src/tools/video-editor/runtime/renderability.test.ts:119:      'route-unsupported',
src/tools/video-editor/runtime/renderability.test.ts:120:      'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:126:      'unknown',
src/tools/video-editor/runtime/renderability.test.ts:131:  it('models capabilities, findings, and blockers with shared route vocabulary', () => {
src/tools/video-editor/runtime/renderability.test.ts:135:      determinism: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:136:      blockerReason: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:141:      id: 'blocker.effect.preview-only',
src/tools/video-editor/runtime/renderability.test.ts:144:      reason: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:152:      id: 'finding.effect.preview-only',
src/tools/video-editor/runtime/renderability.test.ts:155:      reason: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:163:      determinism: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:164:      blockers: [blocker],
src/tools/video-editor/runtime/renderability.test.ts:169:      determinism: 'preview-only',
src/tools/video-editor/runtime/renderability.test.ts:171:      blockers: [{ severity: 'error', route: 'browser-export', reason: 'preview-only' }],
src/tools/video-editor/runtime/renderability.test.ts:232:      blockers: [],
src/tools/video-editor/runtime/extensionIntegrity.test.ts:11:  unsupportedAlgorithmDiagnostic,
src/tools/video-editor/runtime/extensionIntegrity.test.ts:266:  it('returns null for unsupported algorithm', () => {
src/tools/video-editor/runtime/extensionIntegrity.test.ts:325:describe('unsupportedAlgorithmDiagnostic', () => {
src/tools/video-editor/runtime/extensionIntegrity.test.ts:327:    const diag = unsupportedAlgorithmDiagnostic('md5');
src/tools/video-editor/runtime/extensionIntegrity.test.ts:329:    expect(diag.code).toBe('integrity/unsupported-algorithm');
src/tools/video-editor/runtime/extensionIntegrity.test.ts:335:    const diag = unsupportedAlgorithmDiagnostic('sha512');
src/tools/video-editor/runtime/extensionIntegrity.test.ts:376:  it('returns diagnostic for unsupported algorithm', () => {
src/tools/video-editor/runtime/extensionIntegrity.test.ts:379:    expect(diags.some((d) => d.code === 'integrity/unsupported-algorithm')).toBe(true);
src/tools/video-editor/hooks/usePollSync.ts:164:  const logTimelineSync = useCallback((message: string, details?: Record<string, unknown>) => {
src/tools/video-editor/lib/assetMetadata.test.ts:472:  describe('unknown top-level key rejection', () => {
src/tools/video-editor/lib/assetMetadata.test.ts:473:    it('silently strips unknown top-level keys', () => {
src/tools/video-editor/lib/assetMetadata.test.ts:476:        unknownField: 'should be stripped',
src/tools/video-editor/lib/assetMetadata.test.ts:481:      expect(Object.keys(result!)).not.toContain('unknownField');
src/tools/video-editor/lib/assetMetadata.test.ts:486:    it('rejects an object with only unknown keys', () => {
src/tools/video-editor/lib/assetMetadata.test.ts:494:    it('rejects unknown keys even when a known key is also present but empty', () => {
src/tools/video-editor/lib/assetMetadata.test.ts:620:        unknownTopLevel: 'should-be-stripped',
src/tools/video-editor/lib/assetMetadata.test.ts:627:    expect(Object.keys(result.metadata!)).not.toContain('unknownTopLevel');
src/tools/video-editor/lib/assetMetadata.test.ts:633:      metadata: { unknownField: 'value' } as any,
src/tools/video-editor/hooks/useTimelineEventBus.ts:14:  private listeners = new Map<TimelineEventName, Set<(...args: unknown[]) => void>>();
src/tools/video-editor/hooks/useTimelineEventBus.ts:18:    listeners.add(listener as (...args: unknown[]) => void);
src/tools/video-editor/hooks/useTimelineEventBus.ts:32:    listeners.delete(listener as (...args: unknown[]) => void);
src/tools/video-editor/runtime/extensionMigration.test.ts:160:  } as unknown as ExtensionStateRepository;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:47:  payload?: Record<string, unknown>,
src/tools/video-editor/lib/timeline-golden-replay.test.ts:56:function makeMinimalTimelineData(overrides: Record<string, unknown> = {}) {
src/tools/video-editor/lib/timeline-golden-replay.test.ts:59:    clips: (overrides.clips as Array<Record<string, unknown>>) ?? [],
src/tools/video-editor/lib/timeline-golden-replay.test.ts:60:    tracks: (overrides.tracks as Array<Record<string, unknown>>) ?? [],
src/tools/video-editor/lib/timeline-golden-replay.test.ts:65:    app: (overrides.app as Record<string, unknown>) ?? {},
src/tools/video-editor/lib/timeline-golden-replay.test.ts:67:  const clipsData = (config.clips ?? []) as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:68:  const tracksData = (config.tracks ?? []) as Array<Record<string, unknown>>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:76:  const assets = (overrides.assets as Record<string, unknown>) ?? {};
src/tools/video-editor/lib/timeline-golden-replay.test.ts:83:    meta: {} as Record<string, Record<string, unknown>>,
src/tools/video-editor/lib/timeline-golden-replay.test.ts:577:    const extApp = c.nextData!.config.app['com.example'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:617:    const extApp = c.nextData!.config.app['com.example'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:657:    const extApp = c.nextData!.config.app['com.example'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:785:    const extApp = c.nextData!.config.app['com.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:1211:    const extApp = r1.nextData!.config.app['com.dsl.ext'] as Record<string, unknown>;
src/tools/video-editor/lib/timeline-golden-replay.test.ts:1239:    const app = r1.nextData!.config.app as Record<string, unknown>;
src/tools/video-editor/runtime/commandPredicates.ts:316:    if (!left) return null as unknown as AstNode; // errors already emitted
src/tools/video-editor/runtime/commandPredicates.ts:321:      if (!right) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:332:    if (!left) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:337:      if (!right) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:350:      if (!operand) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:361:    if (!left) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:367:      if (!right) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:382:      if (!expr) return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:384:        return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:408:    return null as unknown as AstNode;
src/tools/video-editor/runtime/commandPredicates.ts:420: * Returns the resolved value, or `null` for unknown/missing facts.
src/tools/video-editor/runtime/commandPredicates.ts:443:    return null; // unknown target field
src/tools/video-editor/lib/pinned-group-projection.test.ts:124:  it('falls back to original order for unknown ids', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:56:  data: ArrayBuffer | Uint8Array | Record<string, unknown> = new Uint8Array([1, 2, 3]),
src/tools/video-editor/runtime/liveDataRegistry.test.ts:145:  it('getSource returns undefined for unknown source', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:217:  it('openChannel returns dead-channel descriptor for unknown source', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:238:  it('getChannelMetadata returns undefined for unknown channel', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:308:  it('synchronous read: getSampleAt returns undefined for unknown sequence', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:378:    expect((samples[0].frame.data as Record<string, unknown>).value).toBe('second');
src/tools/video-editor/runtime/liveDataRegistry.test.ts:392:  it('pushSample on unknown channel emits diagnostic', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:393:    registry.pushSample('unknown-ch' as LiveChannelDescriptor, makeFrame(0));
src/tools/video-editor/runtime/liveDataRegistry.test.ts:436:  it('subscribeSamples on unknown channel returns no-op handle', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:438:    const handle = registry.subscribeSamples('unknown' as LiveChannelDescriptor, listener);
src/tools/video-editor/runtime/liveDataRegistry.test.ts:507:  it('transitionSource on unknown source emits diagnostic', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:718:  it('resolveBinding returns missing for unknown binding', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:719:    const resolution = registry.resolveBinding('unknown-binding');
src/tools/video-editor/runtime/liveDataRegistry.test.ts:720:    expect(resolution.bindingId).toBe('unknown-binding');
src/tools/video-editor/runtime/liveDataRegistry.test.ts:863:        input: { sampleCount: number; range?: Record<string, unknown> };
src/tools/video-editor/runtime/liveDataRegistry.test.ts:864:        deterministicRef: { range?: Record<string, unknown>; metadata?: Record<string, unknown> };
src/tools/video-editor/runtime/liveDataRegistry.test.ts:888:  it('bake for unknown source returns error', () => {
src/tools/video-editor/runtime/liveDataRegistry.test.ts:1301:      let data: ArrayBuffer | Uint8Array | Record<string, unknown>;
src/tools/video-editor/lib/timeline-asset-durations.ts:19:export function readPositiveDurationSeconds(value: unknown): number | null {
src/tools/video-editor/hooks/useTimelineCommands.ts:45:  | 'unsupported_asset_type'
src/tools/video-editor/hooks/useTimelineCommands.ts:56:  issues?: unknown[];
src/tools/video-editor/hooks/useTimelineCommands.ts:57:  cause?: unknown;
src/tools/video-editor/hooks/useTimelineCommands.ts:126:      metadata?: Record<string, unknown> | null | undefined;
src/tools/video-editor/hooks/useTimelineCommands.ts:132:  params: Record<string, unknown> | undefined;
src/tools/video-editor/hooks/useTimelineCommands.ts:396:    const nextApp = detachManagedApp(clip.app as Record<string, unknown> | undefined, knownExtIds);
src/tools/video-editor/hooks/useTimelineCommands.ts:428:        return failure('unsupported_asset_type', 'Only image, video, and audio assets can be added to the timeline.');
src/tools/video-editor/contexts/VideoEditorProvider.tsx:996:      log: (...args: unknown[]) => console.log(...args),
src/tools/video-editor/contexts/VideoEditorProvider.tsx:997:      warn: (...args: unknown[]) => console.warn(...args),
src/tools/video-editor/contexts/VideoEditorProvider.tsx:998:      error: (...args: unknown[]) => console.error(...args),
src/tools/video-editor/hooks/usePollSync.test.ts:178:    } as unknown as TimelineData;
src/tools/video-editor/runtime/livePermissions.test.ts:75:  } as unknown as MediaStreamTrack;
src/tools/video-editor/runtime/livePermissions.test.ts:96:  } as unknown as MediaStream;
src/tools/video-editor/runtime/livePermissions.test.ts:122:  const nav = navigator as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:126:  const md = nav.mediaDevices as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:143:  const nav = navigator as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:160:  const nav = navigator as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:177:  const nav = navigator as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:194:  const nav = navigator as Record<string, unknown>;
src/tools/video-editor/runtime/livePermissions.test.ts:408:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:421:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:450:    (navigator as Record<string, unknown>).requestMIDIAccess = vi.fn().mockResolvedValue(mockMidiAccess);
src/tools/video-editor/runtime/livePermissions.test.ts:459:    ((navigator as Record<string, unknown>).serial as Record<string, unknown>).requestPort = vi.fn().mockResolvedValue(mockPort);
src/tools/video-editor/runtime/livePermissions.test.ts:468:    ((navigator as Record<string, unknown>).bluetooth as Record<string, unknown>).requestDevice = vi.fn().mockResolvedValue(mockDevice);
src/tools/video-editor/runtime/livePermissions.test.ts:477:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:513:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:527:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:538:    (navigator as Record<string, unknown>).requestMIDIAccess = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:548:    ((navigator as Record<string, unknown>).serial as Record<string, unknown>).requestPort = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:558:    ((navigator as Record<string, unknown>).bluetooth as Record<string, unknown>).requestDevice = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:568:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:584:describe('LivePermissionService: request — unsupported API', () => {
src/tools/video-editor/runtime/livePermissions.test.ts:655:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:668:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:682:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn()
src/tools/video-editor/runtime/livePermissions.test.ts:696:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:709:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:759:  it('request for unsupported source kind that has no API gives available + granted', async () => {
src/tools/video-editor/runtime/livePermissions.test.ts:778:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn()
src/tools/video-editor/runtime/livePermissions.test.ts:791:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
src/tools/video-editor/runtime/livePermissions.test.ts:802:    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
src/tools/video-editor/hooks/useTimelineHistory.test.ts:28:    commandHistory?: unknown;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:237:      userId: videoEditorRuntime.auth.userId ?? 'unknown',
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:814:    Lightbox: (() => null) as unknown as VideoEditorMediaLightboxHost['Lightbox'],
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:831:    log: (..._args: unknown[]) => {},
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:832:    warn: (..._args: unknown[]) => {},
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:833:    error: (..._args: unknown[]) => {},
src/tools/video-editor/lib/migrate.test.ts:32:        // `as unknown as ...` escape hatch — the runtime file has extra legacy fields
src/tools/video-editor/lib/migrate.test.ts:41:        } as unknown as object),
src/tools/video-editor/lib/migrate.test.ts:78:      ...({ start: 0 } as unknown as object),
src/tools/video-editor/lib/overhang.test.ts:103:    } as unknown as TimelineData;
src/tools/video-editor/hooks/useEditorSync.test.ts:109:    provider: createMockSupabaseProvider() as unknown as DataProvider,
src/tools/video-editor/hooks/useEditorSync.test.ts:135:    } as unknown as DataProvider,
src/tools/video-editor/lib/timeline-asset-plans.ts:84:  metadata?: Record<string, unknown> | null | undefined;
src/tools/video-editor/lib/timeline-asset-plans.ts:193:  registerAsset: (assetId: string, entry: AssetRegistryEntry) => Promise<unknown>;
src/tools/video-editor/lib/timeline-asset-plans.ts:194:}): { assetKey: string; persistPromise: Promise<unknown> } {
src/tools/video-editor/lib/timeline-domain.ts:54:  | 'live_binding_unsupported_source_kind'
src/tools/video-editor/lib/timeline-domain.ts:68:  details?: Record<string, unknown>;
src/tools/video-editor/lib/timeline-domain.ts:231:const cloneAppValue = (value: unknown): unknown => {
src/tools/video-editor/lib/timeline-domain.ts:238:      Object.entries(value as Record<string, unknown>).map(([key, childValue]) => [key, cloneAppValue(childValue)]),
src/tools/video-editor/lib/timeline-domain.ts:245:export const cloneAppExtension = (app: Record<string, unknown>): Record<string, unknown> => {
src/tools/video-editor/lib/timeline-domain.ts:248:      return structuredClone(app) as Record<string, unknown>;
src/tools/video-editor/lib/timeline-domain.ts:254:  return cloneAppValue(app) as Record<string, unknown>;
src/tools/video-editor/lib/timeline-domain.ts:301:const isRecord = (value: unknown): value is Record<string, unknown> => (
src/tools/video-editor/lib/timeline-domain.ts:306:  value: unknown,
src/tools/video-editor/lib/timeline-domain.ts:429:const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
src/tools/video-editor/lib/timeline-domain.ts:431:const isPositiveNumber = (value: unknown): value is number => isFiniteNumber(value) && value > 0;
src/tools/video-editor/lib/timeline-domain.ts:972:  | 'live-binding/unsupported-source-kind'
src/tools/video-editor/lib/timeline-domain.ts:989:  details?: Record<string, unknown>;
src/tools/video-editor/lib/timeline-domain.ts:1024:  | 'live-uniform-binding/unsupported-source-kind'
src/tools/video-editor/lib/timeline-domain.ts:1027:  | 'live-uniform-binding/unsupported-mapping-kind'
src/tools/video-editor/lib/timeline-domain.ts:1041:  details?: Record<string, unknown>;
src/tools/video-editor/lib/timeline-domain.ts:1129:const isTimelineLiveSourceKind = (value: unknown): value is TimelineLiveSourceKind => {
src/tools/video-editor/lib/timeline-domain.ts:1134:  value: unknown,
src/tools/video-editor/lib/timeline-domain.ts:1148:const hasForbiddenSamplePayload = (value: unknown): boolean => {
src/tools/video-editor/lib/timeline-domain.ts:1170:  value: unknown,
src/tools/video-editor/lib/timeline-domain.ts:1171:): readonly { value: unknown; pathSuffix: string }[] => {
src/tools/video-editor/lib/timeline-domain.ts:1197:): readonly { value: unknown; path: string }[] => {
src/tools/video-editor/lib/timeline-domain.ts:1198:  const candidates: { value: unknown; path: string }[] = [];
src/tools/video-editor/lib/timeline-domain.ts:1222:  rawBinding: unknown,
src/tools/video-editor/lib/timeline-domain.ts:1287:      'live-binding/unsupported-source-kind',
src/tools/video-editor/lib/timeline-domain.ts:1288:      `Live binding '${typeof bindingId === 'string' ? bindingId : path}' references unsupported source kind '${sourceKind}'.`,
src/tools/video-editor/lib/timeline-domain.ts:1543:  value: unknown,
src/tools/video-editor/lib/timeline-domain.ts:1544:): readonly { value: unknown; pathSuffix: string }[] => {
src/tools/video-editor/lib/timeline-domain.ts:1558:): readonly { value: unknown; path: string }[] => {
src/tools/video-editor/lib/timeline-domain.ts:1559:  const candidates: { value: unknown; path: string }[] = [];
src/tools/video-editor/lib/timeline-domain.ts:1582:  rawBinding: unknown,
src/tools/video-editor/lib/timeline-domain.ts:1647:      'live-uniform-binding/unsupported-source-kind',
src/tools/video-editor/lib/timeline-domain.ts:1648:      `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' references unsupported source kind '${sourceKind}'.`,
src/tools/video-editor/lib/timeline-domain.ts:1677:        'live-uniform-binding/unsupported-mapping-kind',
src/tools/video-editor/lib/timeline-domain.ts:1678:        `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' has unsupported mapping kind '${String(kind)}'.`,
src/tools/video-editor/lib/timeline-domain.ts:2067:    const clipApp = clip.app as Record<string, unknown> | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2070:      const existing = shaderStack[0] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2071:      const incoming = shaderStack[1] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2078:          typeof existing?.shaderId === 'string' ? existing.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2079:          typeof incoming?.shaderId === 'string' ? incoming.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2125:            : diagnostic.code === 'live-binding/unsupported-source-kind'
src/tools/video-editor/lib/timeline-domain.ts:2126:              ? 'live_binding_unsupported_source_kind'
src/tools/video-editor/lib/timeline-domain.ts:2149:  const postprocessShaderValue = (config.app as Record<string, unknown> | undefined)?.[TIMELINE_POSTPROCESS_SHADER_APP_KEY];
src/tools/video-editor/lib/timeline-domain.ts:2151:    const existing = postprocessShaderValue[0] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2152:    const incoming = postprocessShaderValue[1] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2159:        typeof existing?.shaderId === 'string' ? existing.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2160:        typeof incoming?.shaderId === 'string' ? incoming.shaderId : 'unknown',
src/tools/video-editor/runtime/extensionIntegrity.ts:177: * malformed or unsupported SRI strings.
src/tools/video-editor/runtime/extensionIntegrity.ts:227: * Build a blocking diagnostic for an unsupported integrity algorithm.
src/tools/video-editor/runtime/extensionIntegrity.ts:231:export function unsupportedAlgorithmDiagnostic(
src/tools/video-editor/runtime/extensionIntegrity.ts:237:    code: 'integrity/unsupported-algorithm' as const,
src/tools/video-editor/runtime/extensionIntegrity.ts:272:  hash: unknown,
src/tools/video-editor/runtime/extensionIntegrity.ts:282:  const h = hash as Record<string, unknown>;
src/tools/video-editor/runtime/extensionIntegrity.ts:287:      unsupportedAlgorithmDiagnostic(
src/tools/video-editor/lib/sequence-component-catalog.ts:32:  refetch?: () => Promise<unknown>;
src/tools/video-editor/lib/sequence-component-catalog.ts:44:  refetch: () => Promise<unknown>;
src/tools/video-editor/keyframes/index.ts:41:  detail?: Record<string, unknown>;
src/tools/video-editor/keyframes/index.ts:110:  value: unknown,
src/tools/video-editor/keyframes/index.ts:187:            code: 'keyframes/unknown-select-option',
src/tools/video-editor/keyframes/index.ts:231:      const binding = value as Record<string, unknown>;
src/tools/video-editor/keyframes/index.ts:658:function isSerializable(value: unknown): value is number | string | boolean {
src/tools/video-editor/keyframes/index.ts:964:  readonly params?: Record<string, unknown> | null;
src/tools/video-editor/keyframes/index.ts:981:  const target = (params as Record<string, unknown>).target;
src/tools/video-editor/keyframes/index.ts:984:  const targetObj = target as Record<string, unknown>;
src/tools/video-editor/keyframes/index.ts:992:  const keyframes = (params as Record<string, unknown>).keyframes;
src/tools/video-editor/keyframes/index.ts:995:  const enabled = (params as Record<string, unknown>).enabled;
src/tools/video-editor/keyframes/index.ts:1003:      typeof (kf as Record<string, unknown>).time !== 'number' ||
src/tools/video-editor/keyframes/index.ts:1004:      (kf as Record<string, unknown>).value === undefined ||
src/tools/video-editor/keyframes/index.ts:1005:      typeof (kf as Record<string, unknown>).interpolation !== 'string'
src/tools/video-editor/keyframes/index.ts:1103:  params: Record<string, unknown>,
src/tools/video-editor/keyframes/index.ts:1106:): Record<string, unknown> {
src/tools/video-editor/keyframes/index.ts:1118:  let current: Record<string, unknown> = result;
src/tools/video-editor/keyframes/index.ts:1123:      current[segment] = { ...(existing as Record<string, unknown>) };
src/tools/video-editor/keyframes/index.ts:1127:    current = current[segment] as Record<string, unknown>;
src/tools/video-editor/keyframes/index.ts:1161:  currentParams: Record<string, unknown>,
src/tools/video-editor/keyframes/index.ts:1163:): Record<string, unknown> {
src/tools/video-editor/lib/assetParserRuntime.test.ts:248:  it('returns diagnostic when metadata has unknown keys', () => {
src/tools/video-editor/lib/assetParserRuntime.test.ts:250:      { unknownField: 'value', integrity: { sha256: 'abc' } },
src/tools/video-editor/lib/assetParserRuntime.test.ts:257:    expect(result!.detail?.rejectedFields).toContain('unknownField');
src/tools/video-editor/lib/assetParserRuntime.test.ts:348:    const p2 = makeParser({ id: 'p2', extensionId: 'ext-unknown' });
src/tools/video-editor/lib/assetParserRuntime.test.ts:383:  it('strips unknown registry entry fields not in the blessed allowlist', () => {
src/tools/video-editor/lib/assetParserRuntime.test.ts:386:      unknownField: 'should-be-stripped',
src/tools/video-editor/lib/assetParserRuntime.test.ts:387:    } as unknown as AssetRegistryEntry;
src/tools/video-editor/lib/assetParserRuntime.test.ts:392:    // @ts-expect-error verify unknown field is stripped
src/tools/video-editor/lib/assetParserRuntime.test.ts:393:    expect(merged.entry.unknownField).toBeUndefined();
src/tools/video-editor/lib/assetParserRuntime.test.ts:462:  it('produces rejected output fields diagnostic for unknown metadata keys', () => {
src/tools/video-editor/lib/assetParserRuntime.test.ts:549:          } as unknown as ParserResult['metadata'],
src/tools/video-editor/lib/assetParserRuntime.test.ts:770:    let receivedGps: unknown;
src/tools/video-editor/lib/assetParserRuntime.test.ts:772:      receivedGps = (input.existingMetadata as Record<string, unknown>)?.gps;
src/tools/video-editor/lib/assetParserRuntime.test.ts:789:    expect((receivedGps as Record<string, unknown>)?.latitude).toBe(10);
src/tools/video-editor/lib/assetParserRuntime.test.ts:792:  it('blocks when required parser fails preflight with unsupported type', async () => {
src/tools/video-editor/lib/assetParserRuntime.test.ts:867:      } as unknown as ParserResult['metadata'],
src/tools/video-editor/lib/assetParserRuntime.test.ts:952:    expect(codes).toContain('parser/unsupported-type');
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:24:  obj: Record<string, unknown> | undefined,
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:26:): unknown {
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:30:  let current: unknown = obj;
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:34:    current = (current as Record<string, unknown>)[segments[i]];
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:72:  const metadata = entry.metadata as Record<string, unknown>;
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:79:        if (Object.keys(value as Record<string, unknown>).length > 0) {
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:133:  obj: unknown,
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:145:  const record = obj as Record<string, unknown>;
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:177:  const hostMetadata: Record<string, unknown> = {};
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:178:  const rawMetadata = entry.metadata as Record<string, unknown>;
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:247:): unknown {
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:251:    entry.metadata as Record<string, unknown>,
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:283:): ReadonlyMap<string, unknown> {
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:284:  const result = new Map<string, unknown>();
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:321:  /** Machine-readable provider key (e.g. 'generation', 'upload', 'unknown'). */
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:322:  kind: 'generation' | 'upload' | 'external-url' | 'unknown';
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:338: *   5. Otherwise → unknown badge
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:344:    return { kind: 'unknown', label: 'Unknown' };
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:393:  return { kind: 'unknown', label: 'Unknown' };
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:586:        const metadata = entry.metadata as Record<string, unknown>;
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:635:    entry.metadata as Record<string, unknown>,
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:903:      } catch (error: unknown) {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:99:  useEffects: (...args: unknown[]) => useEffectsMock(...args),
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:111:    useResolvedEffectCatalog: (...args: unknown[]) => useResolvedEffectCatalogMock(...args),
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:453:  applyEdit?: (...args: unknown[]) => void;
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:454:  registerAsset?: (...args: unknown[]) => Promise<unknown>;
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:455:  patchRegistry?: (...args: unknown[]) => void;
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:456:  unpatchRegistry?: (...args: unknown[]) => void;
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:543:      determinism: 'preview-only',
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:548:          determinism: 'preview-only',
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:569:      determinism: 'preview-only',
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:574:          determinism: 'preview-only',
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:1163:    const patchRegistry = vi.fn((assetId: string, entry: Record<string, unknown>) => {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:1571:    } as unknown as ReighExtension;
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:1828:        initialProps: { repo: repo as unknown as ExtensionStateRepository, bs: bundleStore },
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:2986:    } as unknown as DataProvider;
src/tools/video-editor/lib/timeline-reader.test.ts:273:  it('does not mark clip as managed for unknown extension IDs in app', async () => {
src/tools/video-editor/lib/timeline-reader.test.ts:278:          id: 'clip-unknown',
src/tools/video-editor/lib/timeline-reader.test.ts:293:    const clip = reader.snapshot().clips.find((c) => c.id === 'clip-unknown');
src/tools/video-editor/lib/timeline-reader.test.ts:479:    const snap = reader.snapshot() as Record<string, unknown>;
src/tools/video-editor/lib/timeline-reader.test.ts:498:      const c = clip as Record<string, unknown>;
src/tools/video-editor/lib/assetMetadata.ts:24:const isValidString = (value: unknown): value is string =>
src/tools/video-editor/lib/assetMetadata.ts:27:const isOptionalString = (value: unknown): value is string | undefined =>
src/tools/video-editor/lib/assetMetadata.ts:30:const isFiniteNumber = (value: unknown): value is number =>
src/tools/video-editor/lib/assetMetadata.ts:33:const isOptionalFiniteNumber = (value: unknown): value is number | undefined =>
src/tools/video-editor/lib/assetMetadata.ts:36:const isOptionalBoolean = (value: unknown): value is boolean | undefined =>
src/tools/video-editor/lib/assetMetadata.ts:39:const isPlainObject = (value: unknown): value is Record<string, unknown> =>
src/tools/video-editor/lib/assetMetadata.ts:42:const validateIntegrity = (input: unknown): AssetMetadataIntegrity | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:71:const validateGPS = (input: unknown): AssetMetadataGPS | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:112:const validateConsent = (input: unknown): AssetMetadataConsent | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:151:const validateProvenance = (input: unknown): AssetMetadataProvenance | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:192:const validateEnrichmentClaim = (input: unknown): AssetMetadataEnrichmentClaim | null => {
src/tools/video-editor/lib/assetMetadata.ts:220:const validateEnrichment = (input: unknown): AssetMetadataEnrichment | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:254:const validateExtensions = (input: unknown): Record<string, unknown> | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:256:    const filtered: Record<string, unknown> = {};
src/tools/video-editor/lib/assetMetadata.ts:277: * `provenance`, `enrichment`, `extensions`) are preserved; any unknown keys
src/tools/video-editor/lib/assetMetadata.ts:284:export const validateAssetMetadata = (input: unknown): AssetMetadata | undefined => {
src/tools/video-editor/lib/assetMetadata.ts:328:  // Reject any unknown top-level metadata keys (they are silently stripped).
src/tools/video-editor/lib/finalVideoAssets.ts:12:function readPositiveNumber(value: unknown): number | null {
src/tools/video-editor/lib/finalVideoAssets.ts:27:function readPositiveNumberFromFirstArrayItem(value: unknown): number | null {
src/tools/video-editor/lib/finalVideoAssets.ts:35:function readDurationFromRecord(record: Record<string, unknown> | null | undefined): number | null {
src/tools/video-editor/lib/finalVideoAssets.ts:63:export function getDurationSecondsFromFinalVideoParams(params: unknown): number | null {
src/tools/video-editor/lib/proposal-runtime.ts:41:  readonly patch: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:42:  readonly diagnostics?: readonly Record<string, unknown>[];
src/tools/video-editor/lib/proposal-runtime.ts:43:  readonly expiryDetail?: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:55:    detail?: Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:75:    payload: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:77:    detail?: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:86:    detail?: Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:95:    payload: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:96:    detail?: Record<string, unknown>;
src/tools/video-editor/lib/proposal-runtime.ts:149:      detail?: Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:187:            : {}) as Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:189:            ? (p.diagnostics as readonly Record<string, unknown>[])
src/tools/video-editor/lib/proposal-runtime.ts:193:              ? (p.expiryDetail as Record<string, unknown>)
src/tools/video-editor/lib/proposal-runtime.ts:278:  /** Accumulated diagnostics (unsupported-provider, etc.). */
src/tools/video-editor/lib/proposal-runtime.ts:284:      code: 'proposal/persistence-unsupported',
src/tools/video-editor/lib/proposal-runtime.ts:304:        patch: proposal.patch as unknown as Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:305:        diagnostics: proposal.diagnostics as readonly Record<string, unknown>[] | undefined,
src/tools/video-editor/lib/proposal-runtime.ts:316:    detail?: Record<string, unknown>,
src/tools/video-editor/lib/proposal-runtime.ts:359:        ? (updated.expiryDetail as unknown as Record<string, unknown>)
src/tools/video-editor/lib/proposal-runtime.ts:636:          patch: record.patch as unknown as TimelineProposal['patch'],
src/tools/video-editor/keyframes/index.test.ts:169:    const result = interpolateLinear(0 as unknown as string, 'final', 0.5);
src/tools/video-editor/keyframes/index.test.ts:324:  it('warns for unknown select option', () => {
src/tools/video-editor/keyframes/index.test.ts:325:    const diags = validateKeyframeValue('unknown', makeSelectParam());
src/tools/video-editor/keyframes/index.test.ts:328:    expect(diags[0].code).toBe('keyframes/unknown-select-option');
src/tools/video-editor/keyframes/index.test.ts:429:    const diags = validateKeyframes('not-an-array' as unknown as ClipKeyframe[], makeNumberParam());
src/tools/video-editor/keyframes/index.test.ts:435:    const kfs = [null as unknown as ClipKeyframe];
src/tools/video-editor/keyframes/index.test.ts:465:    const kfs = [{ time: 0, value: 0.5, interpolation: 'bezier' }] as unknown as ClipKeyframe[];
src/tools/video-editor/keyframes/index.test.ts:768:  // --- JSON values / unsupported types ---
src/tools/video-editor/keyframes/index.test.ts:774:        makeKeyframe(0, { source: 'bass', min: -50, max: 50 } as unknown as boolean, 'hold'),
src/tools/video-editor/keyframes/index.test.ts:1210:      { time: 1, value: () => {} } as unknown as SamplePoint,
src/tools/video-editor/keyframes/index.test.ts:1222:      { time: 0, value: Symbol('test') } as unknown as SamplePoint,
src/tools/video-editor/keyframes/index.test.ts:1231:      { time: 0, value: { nested: true } } as unknown as SamplePoint,
src/tools/video-editor/keyframes/index.test.ts:1240:      { time: 0, value: null } as unknown as SamplePoint,
src/tools/video-editor/keyframes/index.test.ts:1250:      { time: 0, value: undefined } as unknown as SamplePoint,
src/tools/video-editor/keyframes/index.test.ts:1270:      s(0, 'not-a-number' as unknown as number),
src/tools/video-editor/keyframes/index.test.ts:1279:      s(0, 1 as unknown as boolean),
src/tools/video-editor/keyframes/index.test.ts:1321:      s(2, 'bad' as unknown as number),
src/tools/video-editor/keyframes/index.test.ts:1431:        ]) as unknown as Record<string, unknown>[],
src/tools/video-editor/keyframes/index.test.ts:1692:      original as unknown as Record<string, unknown>,
src/tools/video-editor/lib/sequence-drafts.test.ts:322:      (result.mutation.metaUpdates?.[result.clipId] as Record<string, unknown>)?.params,
src/tools/video-editor/lib/effect-catalog.ts:57:  refetch?: () => Promise<unknown>;
src/tools/video-editor/lib/effect-catalog.ts:72:  refetch: () => Promise<unknown>;
src/tools/video-editor/lib/config-utils.ts:123:const normalizeForStableJson = (value: unknown): unknown => {
src/tools/video-editor/lib/config-utils.ts:134:      .reduce<Record<string, unknown>>((acc, key) => {
src/tools/video-editor/lib/config-utils.ts:135:        const normalized = normalizeForStableJson((value as Record<string, unknown>)[key]);
src/tools/video-editor/lib/shader-catalog.ts:78:function getUniformDefault(uniform: ShaderUniformDefinition): unknown {
src/tools/video-editor/lib/shader-catalog.ts:108:function isTimelineTextureRef(value: unknown): value is TimelineShaderTextureRef {
src/tools/video-editor/lib/shader-catalog.ts:113:  const kind = (value as { kind?: unknown }).kind;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:74:  useEffectRegistry: (...args: unknown[]) => mocks.useEffectRegistry(...args),
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:159:      determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:164:          determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:186:      determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:191:          determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:212:      determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:217:          determinism: 'preview-only',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:580:          code: 'planner/browser-export/route-unsupported',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:667:          && diagnostic.code === 'planner/browser-export/route-unsupported',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:739:    let capturedSessions: unknown = null;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:854:    (mocks.timelineData.config as Record<string, unknown>).liveBindings = persistedLiveBindings;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:918:    expect(JSON.stringify((mocks.timelineData.config as Record<string, unknown>).liveBindings)).toBe(persistedBefore);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:747:    // Managed clips are preview-only until explicitly declared
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:748:    expect(clipTypeReq!.determinism).toBe('preview-only');
src/tools/video-editor/lib/pinned-group-projection.ts:174:  const unknown: string[] = [];
src/tools/video-editor/lib/pinned-group-projection.ts:180:      unknown.push(id);
src/tools/video-editor/lib/pinned-group-projection.ts:189:  return [...known.map((entry) => entry.id), ...unknown];
src/tools/video-editor/lib/assetRegistryContract.test.ts:31:      // @ts-expect-error verifying unknown fields are stripped.
src/tools/video-editor/lib/assetRegistryContract.test.ts:150:  it('strips unknown fields during sanitization', () => {
src/tools/video-editor/lib/assetRegistryContract.test.ts:153:      // @ts-expect-error verifying unknown fields are stripped.
src/tools/video-editor/lib/assetRegistryContract.test.ts:155:      // @ts-expect-error verifying unknown fields are stripped.
src/tools/video-editor/lib/renderRouter.ts:37:  planRender,
src/tools/video-editor/lib/renderRouter.ts:76: *   * `preview-only`      — generated remotion_module clips with invalid /
src/tools/video-editor/lib/renderRouter.ts:80: *                          Currently unreachable from `decideRenderRoute`.
src/tools/video-editor/lib/renderRouter.ts:85:  | 'preview-only'
src/tools/video-editor/lib/renderRouter.ts:93:  'preview-only': 'preview-only',
src/tools/video-editor/lib/renderRouter.ts:114:    | 'contributed_blocked_no_browser_capability'
src/tools/video-editor/lib/renderRouter.ts:115:    | 'contributed_blocked_worker_route_conflict'
src/tools/video-editor/lib/renderRouter.ts:136:const isNativeBuiltinClipType = (value: unknown): boolean => {
src/tools/video-editor/lib/renderRouter.ts:143:const isCustomRenderClipType = (value: unknown): boolean => {
src/tools/video-editor/lib/renderRouter.ts:210:          reason: options?.reason ?? 'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:220:            id: `${id}.${route}.${options?.reason ?? 'route-unsupported'}`,
src/tools/video-editor/lib/renderRouter.ts:223:            reason: options?.reason ?? 'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:244:      reason: 'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:263:      reason: 'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:293:  if (result.canBrowserExport) {
src/tools/video-editor/lib/renderRouter.ts:296:  if (result.canWorkerExport) {
src/tools/video-editor/lib/renderRouter.ts:303:export function decideRenderRoute(
src/tools/video-editor/lib/renderRouter.ts:317:      planner: selectPlannerRoute(planRender({ requirements: [] })),
src/tools/video-editor/lib/renderRouter.ts:377:            'contributed_blocked_no_browser_capability',
src/tools/video-editor/lib/renderRouter.ts:378:            'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:380:          blockedReason = 'contributed_blocked_no_browser_capability';
src/tools/video-editor/lib/renderRouter.ts:398:          'contributed_blocked_worker_route_conflict',
src/tools/video-editor/lib/renderRouter.ts:399:          'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:401:        blockedReason = 'contributed_blocked_worker_route_conflict';
src/tools/video-editor/lib/renderRouter.ts:424:  const planner = selectPlannerRoute(planRender({ requirements }));
src/tools/video-editor/lib/renderRouter.ts:428:      route: 'preview-only',
src/tools/video-editor/lib/renderRouter.ts:444:      const conflictPlanner = selectPlannerRoute(planRender({
src/tools/video-editor/lib/renderRouter.ts:450:            'contributed_blocked_worker_route_conflict',
src/tools/video-editor/lib/renderRouter.ts:451:            'route-unsupported',
src/tools/video-editor/lib/renderRouter.ts:456:        route: 'preview-only',
src/tools/video-editor/lib/renderRouter.ts:460:        reason: 'contributed_blocked_worker_route_conflict',
src/tools/video-editor/lib/renderRouter.ts:475:  // short-circuit above (contributed_blocked_worker_route_conflict).
src/tools/video-editor/lib/renderRouter.ts:482:        route: 'preview-only',
src/tools/video-editor/lib/renderRouter.ts:486:        reason: 'contributed_blocked_worker_route_conflict',
src/tools/video-editor/lib/renderRouter.ts:549:  timeline: unknown;
src/tools/video-editor/lib/renderRouter.ts:550:  assets: unknown;
src/tools/video-editor/lib/compiler-canary.test.ts:150:          const key = (op.payload as Record<string, unknown>)?.key as string;
src/tools/video-editor/lib/compiler-canary.test.ts:151:          const value = (op.payload as Record<string, unknown>)?.value;
src/tools/video-editor/lib/compiler-canary.test.ts:153:            (baseSnapshot.app as Record<string, unknown>)[extId] = {};
src/tools/video-editor/lib/compiler-canary.test.ts:155:          ((baseSnapshot.app as Record<string, unknown>)[extId] as Record<string, unknown>)[key] = value;
src/tools/video-editor/lib/compiler-canary.test.ts:158:          const key = (op.payload as Record<string, unknown>)?.key as string;
src/tools/video-editor/lib/compiler-canary.test.ts:160:            delete (baseSnapshot.app[extId] as Record<string, unknown>)[key];
src/tools/video-editor/lib/compiler-canary.test.ts:365:        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary-data',
src/tools/video-editor/lib/compiler-canary.test.ts:390:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__dsl__'),
src/tools/video-editor/lib/compiler-canary.test.ts:395:      const value = JSON.parse((dslWrite!.payload as Record<string, unknown>).value as string);
src/tools/video-editor/lib/compiler-canary.test.ts:408:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
src/tools/video-editor/lib/compiler-canary.test.ts:414:        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:437:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
src/tools/video-editor/lib/compiler-canary.test.ts:441:        (op) => ((op.payload as Record<string, unknown>).value as Record<string, unknown>).sourceStartLine,
src/tools/video-editor/lib/compiler-canary.test.ts:510:        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary',
src/tools/video-editor/lib/compiler-canary.test.ts:527:        (p) => p.meta && (p.meta as Record<string, unknown>).kind === 'compiler-canary',
src/tools/video-editor/lib/compiler-canary.test.ts:533:          const payload = op.payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:534:          const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:536:          const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:546:          (p) => p.meta && (p as Record<string, unknown>).kind === 'compiler-canary' ||
src/tools/video-editor/lib/compiler-canary.test.ts:547:            p.patch.meta && (p.patch.meta as Record<string, unknown>).kind === 'compiler-canary',
src/tools/video-editor/lib/compiler-canary.test.ts:556:          const payload = op.payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:557:          const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:559:          const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:576:        const payload = op.payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:577:        const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:578:        const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:591:        const payload = op.payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:592:        const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:594:        expect((app['com.example.canary'] as Record<string, unknown>).source).toBe('compiler-canary');
src/tools/video-editor/lib/compiler-canary.test.ts:622:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__dsl__'),
src/tools/video-editor/lib/compiler-canary.test.ts:624:      const dslValue = JSON.parse((dslWrite!.payload as Record<string, unknown>).value as string);
src/tools/video-editor/lib/compiler-canary.test.ts:1084:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
src/tools/video-editor/lib/compiler-canary.test.ts:1088:        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1095:      delete (dsl as Record<string, unknown>).sourceUri;
src/tools/video-editor/lib/compiler-canary.test.ts:1102:          (op.payload as Record<string, unknown>)?.key?.toString().startsWith('__sm__'),
src/tools/video-editor/lib/compiler-canary.test.ts:1106:        const value = (smWrite.payload as Record<string, unknown>).value as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1297:      const payload = updateOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1298:      const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1299:      const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1330:      const payload = updateOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1331:      const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1333:      expect((app['com.example.canary'] as Record<string, unknown>).source).toBe('compiler-canary');
src/tools/video-editor/lib/compiler-canary.test.ts:1397:      const payload = updateOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1398:      const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1399:      const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1431:        const payload = updateOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1432:        const app = payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1433:        const generatedMeta = app.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1448:      const pass1Payload = pass1AddOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1449:      const pass1App = pass1Payload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1450:      const pass1Meta = pass1App.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1485:      const updatePayload = pass2UpdateOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1486:      const updateApp = updatePayload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1487:      const updateMeta = updateApp.__generated__ as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1490:      const addPayload = pass2AddOps[0].payload as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1491:      const addApp = addPayload.app as Record<string, unknown>;
src/tools/video-editor/lib/compiler-canary.test.ts:1492:      const addMeta = addApp.__generated__ as Record<string, unknown>;
src/tools/video-editor/types/agent-session.ts:33:  tool_args?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:72:// for unknown clipTypes is Sprint 3.
src/tools/video-editor/types/index.ts:87:  app?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:94:  params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:101:  params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:107:  params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:113:  params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:197:  metadata?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:224:  placeholder?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:225:  metadata?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:295:  metadata?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:303:export type TimelineShaderUniformValues = Record<string, unknown>;
src/tools/video-editor/types/index.ts:321:  metadata?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:332:export type TimelineClipAppMetadata = Record<string, unknown> & {
src/tools/video-editor/types/index.ts:336:export type TimelineConfigAppMetadata = Record<string, unknown> & {
src/tools/video-editor/types/index.ts:369:  params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:373:  generation?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:420:    params?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:424:    generation?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:442:  visual?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:443:  generation?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:444:  voice?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:445:  audio?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:446:  pacing?: Record<string, unknown>;
src/tools/video-editor/types/index.ts:449:export type GenerationDefaults = Record<string, unknown>;
src/tools/video-editor/types/index.ts:520:  extensions?: Record<string, unknown>;

codex
The key UI hook is `useRenderState`: it already has a comment saying planner blockers are canonical, but it still computes them from an export-guard compatibility shim and separately routes through legacy provider decisions. I’m checking exact control flow and tests before judging whether this can be flipped in one step.
exec
/bin/zsh -lc "sed -n '620,980p' src/tools/video-editor/runtime/renderPlanner.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    severity: 'warning',
    message: processStatusMessage(
      String(blocker.detail?.outputLabel ?? blocker.contributionId ?? 'output'),
      status.processId,
      blocker.route,
      status,
    ),
    detail: {
      ...blocker.detail,
      processState: status.state,
      diagnostics: status.diagnostics,
    },
  };
}

function collectOutputFormat(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
): void {
  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? (['sidecar-export'] as const) : ([] as const));

  for (const route of availableRoutes) {
    addRouteSetValue(acc.routeOutputFormatIds, route, outputFormat.id);
  }

  for (const requirement of outputFormat.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }

  for (const routeRequirement of outputFormat.routeRequirements) {
    for (const route of routeRequirement.routes) {
      addRouteValue(acc.routeDeterminism, route, routeRequirement.determinism);
      for (const capability of routeRequirement.requiredCapabilities) {
        addRouteSetValue(acc.routeCapabilities, route, capability);
      }
      const status = routeRequirement.processId ? processStatusById.get(routeRequirement.processId) : undefined;
      const routeBlocker = routeRequirementBlocker(outputFormat, routeRequirement, route, status);
      if (routeBlocker && processStatusBlocks(status)) {
        acc.findings.push(routeBlocker);
        acc.blockers.push(routeBlocker);
      } else if (routeBlocker && status && processStatusDegraded(status)) {
        acc.findings.push(processStatusWarning(routeBlocker, status));
      }
    }
  }

  for (const requirement of outputFormat.processRequirements) {
    const routes = availableRoutes.length > 0 ? availableRoutes : RENDER_ROUTES;
    for (const route of routes) {
      addRouteValue(acc.routeProcessRequirements, route, requirement);
      const status = processStatusById.get(requirement.processId);
      const blocker = processRequirementBlocker(outputFormat, route, requirement, status);
      if (processStatusBlocks(status)) {
        acc.findings.push(blocker);
        acc.blockers.push(blocker);
      } else if (status && processStatusDegraded(status)) {
        acc.findings.push(processStatusWarning(blocker, status));
      }
    }
  }

  for (const blocker of outputFormat.blockers) {
    collectDescriptorBlocker(acc, blocker, availableRoutes[0] ?? 'sidecar-export', 'output-format');
  }
  acc.nextActions.push(...outputFormat.nextActions);
}

function collectRequestedOutputRouteSupport(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor | undefined,
  request: RenderPlannerRequest | undefined,
): void {
  if (!outputFormat) return;
  const routes = requestedRoutes(request);
  if (routes.length === 0) return;

  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? ([] as const) : (['browser-export'] as const));
  const available = new Set(availableRoutes);

  for (const route of routes) {
    if (available.has(route)) continue;
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
      severity: 'error',
      route,
      reason: 'route-unsupported',
      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
      extensionId: outputFormat.extensionId,
      contributionId: outputFormat.id,
      detail: {
        source: 'render-request',
        outputFormatId: outputFormat.id,
        requestedRoute: route,
        availableRoutes: [...availableRoutes].sort(),
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }
}

function collectProcess(acc: PlanAccumulator, process: VideoEditorProcessDescriptor): void {
  for (const route of process.availableRoutes) {
    addRouteSetValue(acc.routeCapabilities, route, process.processId);
  }
  for (const requirement of process.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }
  for (const blocker of process.blockers) {
    collectDescriptorBlocker(acc, blocker, process.availableRoutes[0] ?? 'sidecar-export', 'process');
  }
  acc.nextActions.push(...process.nextActions);
}

function createProcessStatusMap(statuses: readonly ProcessStatus[] | undefined): ReadonlyMap<string, ProcessStatus> {
  return new Map((statuses ?? []).map((status) => [status.processId, status]));
}

function createMaterialStatusMap(
  statuses: readonly RenderPlannerMaterialStatus[] | undefined,
): ReadonlyMap<string, RenderPlannerMaterialStatus> {
  return new Map((statuses ?? []).map((status) => [status.materialRefId, status]));
}

function materializeAction(
  label: string,
  message: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'resolve-blocker',
    label,
    route: 'browser-export',
    message,
  };
}

function materialBlockerReason(
  materialRef: RenderMaterialRef,
  status: RenderPlannerMaterialStatus | undefined,
): RenderBlockerReason | undefined {
  if (status?.state === 'missing') return 'missing-material';
  if (status?.state === 'stale') return 'materialization-failed';
  if (status?.state === 'resolved') return undefined;
  if (status?.state === 'unbaked') return materialRef.determinism;
  if (materialRef.determinism === 'live-unbaked' || materialRef.determinism === 'process-dependent') {
    return materialRef.determinism;
  }
  return undefined;
}

function collectMaterialRef(
  acc: PlanAccumulator,
  materialRef: RenderMaterialRef,
  materialStatusById: ReadonlyMap<string, RenderPlannerMaterialStatus>,
): void {
  addRouteValue(acc.routeDeterminism, 'browser-export', materialRef.determinism);
  if (materialRef.replacementPolicy !== 'materialize-on-export') return;

  const status = materialStatusById.get(materialRef.id);
  const reason = materialBlockerReason(materialRef, status);
  if (!reason) return;
  const message = status?.message ?? `Material "${materialRef.id}" must be materialized before browser export.`;
  const blocker: RenderBlocker = {
    id: `planner.material.${materialRef.id}.browser-export.${reason}`,
    severity: 'error',
    route: 'browser-export',
    reason,
    message,
    materialRefId: materialRef.id,
    extensionId: materialRef.producerExtensionId,
    detail: {
      source: 'material-ref',
      mediaKind: materialRef.mediaKind,
      locatorKind: materialRef.locator.kind,
      replacementPolicy: materialRef.replacementPolicy,
      determinism: materialRef.determinism,
      materialState: status?.state ?? 'unbaked',
    },
  };
  acc.findings.push(blocker);
  acc.blockers.push(blocker);
  acc.nextActions.push(materializeAction(`Materialize ${materialRef.id}`, message));
}

function collectRenderGroups(acc: PlanAccumulator, snapshot: TimelineSnapshot | null | undefined): void {
  for (const group of snapshot?.renderGroups ?? []) {
    for (const pass of group.passes ?? []) {
      if (!pass.required) continue;
      if (pass.status !== 'missing' && pass.status !== 'stale') continue;

      const reason: RenderBlockerReason = pass.status === 'missing'
        ? 'missing-material'
        : 'materialization-failed';
      const message = `Render group "${group.id}" pass "${pass.passName}" is ${pass.status}.`;
      const blocker: RenderBlocker = {
        id: `planner.renderGroup.${group.id}.${pass.id}.browser-export.${reason}`,
        severity: 'error',
        route: 'browser-export',
        reason,
        message,
        materialRefId: pass.materialRefId,
        detail: {
          source: 'render-group',
          renderGroupId: group.id,
          passId: pass.id,
          passName: pass.passName,
          passStatus: pass.status,
          composable: pass.composable,
          required: pass.required,
        },
      };
      addRouteSetValue(acc.routeCapabilities, 'browser-export', 'render-groups');
      addRouteValue(acc.routeDeterminism, 'browser-export', 'process-dependent');
      acc.findings.push(blocker);
      acc.blockers.push(blocker);
      acc.nextActions.push(materializeAction(`Materialize ${group.id}:${pass.passName}`, message));
    }
  }
}

function mostConservativeDeterminism(statuses: readonly DeterminismStatus[]): DeterminismStatus {
  if (statuses.length === 0) return 'deterministic';
  return [...statuses].sort((a, b) => DETERMINISM_RANK[b] - DETERMINISM_RANK[a])[0];
}

function sortedActions(
  actions: readonly VideoEditorPlannerNextActionDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  const seen = new Set<string>();
  return Object.freeze([...actions]
    .sort((a, b) =>
      `${a.kind}:${a.route ?? ''}:${a.processId ?? ''}:${a.operationId ?? ''}:${a.label}`
        .localeCompare(`${b.kind}:${b.route ?? ''}:${b.processId ?? ''}:${b.operationId ?? ''}:${b.label}`))
    .filter((action) => {
      const key = `${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((action) => Object.freeze({ ...action })));
}

function buildRoutePlan(
  route: RenderRoute,
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
  acc: PlanAccumulator,
): RenderRoutePlan {
  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
  const routeFindings = findings.filter((finding) => !finding.route || finding.route === route);
  const requiredCapabilities = Object.freeze([...(acc.routeCapabilities.get(route) ?? new Set())].sort());
  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
  const processRequirements = Object.freeze([...(acc.routeProcessRequirements.get(route) ?? [])]
    .sort((a, b) =>
      `${a.processId}:${a.operationId ?? ''}:${a.requiredCapabilities.join(',')}`
        .localeCompare(`${b.processId}:${b.operationId ?? ''}:${b.requiredCapabilities.join(',')}`))
    .map((requirement) => Object.freeze({
      ...requirement,
      requiredCapabilities: Object.freeze([...requirement.requiredCapabilities].sort()),
    })));

  const actions = sortedActions(acc.nextActions.filter((action) => !action.route || action.route === route));
  return Object.freeze({
    route,
    blockerCount: routeBlockers.length,
    findingCount: routeFindings.length,
    blocked: routeBlockers.length > 0,
    requiredCapabilities,
    determinism: mostConservativeDeterminism(acc.routeDeterminism.get(route) ?? []),
    blockers: Object.freeze(routeBlockers),
    diagnostics: Object.freeze(routeFindings),
    outputFormatIds,
    processRequirements,
    nextActions: actions,
  });
}

function emptyGuard(
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
): RenderPlannerGuardCompatibility {
  return Object.freeze({
    diagnostics: findings,
    findings,
    blockers,
    unknownClipTypes: Object.freeze([]),
    unknownEffects: Object.freeze([]),
    unknownTransitions: Object.freeze([]),
    inactiveExtensionIds: EMPTY_IDS,
    hasBlockingErrors: blockers.length > 0,
  });
}

export function planRender(input: RenderPlannerInput): RenderPlannerResult {
  const acc = createAccumulator();
  const shaderComposition = diagnoseSnapshotShaderComposition(input.snapshot);
  const requirements = input.requirements ?? (shaderComposition.snapshot
    ? getCapabilityRequirements(shaderComposition.snapshot)
    : []);
  const outputFormats = input.outputFormats ?? input.extensionRuntime?.outputFormats ?? [];
  const processes = input.processes ?? input.extensionRuntime?.processes ?? [];
  const shaders = input.shaders ?? input.extensionRuntime?.shaders ?? [];
  const processStatusById = createProcessStatusMap(input.processStatuses);
  const processById = createProcessDescriptorMap(processes);
  const shaderBySourceRef = createShaderDescriptorMap(shaders);
  const materialStatusById = createMaterialStatusMap(input.materialStatuses);
  const requestedOutputFormat = input.request?.outputFormatId
    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
    : undefined;

  for (const requirement of requirements) {
    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
      ? shaderBySourceRef.get(shaderDescriptorKey(
        requirement.sourceRef.extensionId,
        requirement.sourceRef.contributionId,
      ))
      : undefined;
    if (
      shaderDescriptor
      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
    ) {
      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
      continue;
    }
    collectRequirement(acc, requirement);
  }
  collectRequestCapabilities(acc, input.request);
  for (const outputFormat of outputFormats) {
    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
    collectOutputFormat(acc, outputFormat, processStatusById);
  }
  collectRequestedOutputRouteSupport(acc, requestedOutputFormat, input.request);
  for (const process of processes) {
    collectProcess(acc, process);
  }
  for (const materialRef of input.materialRefs ?? []) {
    collectMaterialRef(acc, materialRef, materialStatusById);
  }
  collectRenderGroups(acc, input.snapshot);
  acc.findings.push(...shaderComposition.findings);
  acc.findings.push(...(input.diagnostics ?? []));

  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
      severity: 'error',
      route: input.request.route ?? input.request.routes?.[0] ?? 'sidecar-export',
      reason: 'missing-contribution',
      message: `Output format "${input.request.outputFormatId}" is not registered.`,
      contributionId: input.request.outputFormatId,
      detail: {
        source: 'render-request',
        outputFormatId: input.request.outputFormatId,
      },
    };
    acc.findings.push(blocker);

exec
/bin/zsh -lc "sed -n '1,720p' src/tools/video-editor/hooks/useRenderState.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useClientRender } from '@/tools/video-editor/hooks/useClientRender.ts';
import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
import type { VideoEditorExporter } from '@/tools/video-editor/lib/browser-runtime.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { ExtensionRuntime, VideoEditorOutputFormatDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createCompileOnlyOutputFormatRegistry,
  executeCompileOnlyOutput,
  type CompileOnlyOutputFormatEntry,
  type CompileOnlyOutputFormatRegistry,
} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
import { useEffectRegistrySnapshot } from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import { useTransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/TransitionRegistryContext.tsx';
import { useClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  hasTimelineShaderMetadata,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import {
  planRender,
  type RenderPlannerResult,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { syncPlannerDiagnosticsToCollection } from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';
import type {
  CapabilityFinding,
  Diagnostic,
  ExportDiagnostic,
  RenderBlockerReason,
} from '@reigh/editor-sdk';

export type RenderStatus = 'idle' | 'rendering' | 'done' | 'error';

/** M6: Export status for compile-only and render-dependent export operations. */
export type ExportStatus = 'idle' | 'exporting' | 'done' | 'error';

type RenderProgress = { current: number; total: number; percent: number; phase: string } | null;

const CLIENT_CLIP_TYPES = new Set(['media', 'text', 'effect-layer', 'hold']);

function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
  const clips = resolvedConfig?.clips ?? [];

  if (clips.length === 0) {
    return { route: 'browser-remotion' as const, reason: 'no_clips' };
  }

  let hasGeneratedModuleClip = false;
  let hasOtherClip = false;
  for (const clip of clips) {
    if (clip.generation?.sequence_lane === 'remotion_module') {
      if (!clip.generation?.artifact_id) {
        return { route: 'preview-only' as const, reason: 'remotion_module_missing_artifact' };
      }
      hasGeneratedModuleClip = true;
      continue;
    }

    if (!clip.clipType || CLIENT_CLIP_TYPES.has(clip.clipType)) {
      hasOtherClip = true;
      continue;
    }

    return null;
  }

  if (hasGeneratedModuleClip) {
    return {
      route: 'worker-banodoco' as const,
      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
    };
  }

  return { route: 'browser-remotion' as const, reason: 'pure_native_clips' };
}

function isExtensionRuntimeEmpty(extRuntime: ExtensionRuntime | undefined): boolean {
  if (!extRuntime) return true;
  return extRuntime.extensions.length === 0 && extRuntime.inactiveReserved.length === 0;
}

function buildExtensionContributions(extRuntime: ExtensionRuntime) {
  const allContributions: import('@reigh/editor-sdk').ExtensionContribution[] = [];
  for (const ext of extRuntime.extensions) {
    const contribs = ext.manifest.contributions ?? [];
    for (const c of contribs) {
      allContributions.push(c);
    }
  }
  return allContributions;
}

/**
 * Create a concise render log line from export guard diagnostics.
 * Emits a single summary line plus per-diagnostic error lines for blocking issues.
 */
function formatExportGuardLog(
  guardResult: ReturnType<typeof scanExportConfig>,
): string {
  const lines: string[] = [];

  const totalDiags = guardResult.diagnostics.length;
  const errorCount = guardResult.diagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = guardResult.diagnostics.filter((d) => d.severity === 'warning').length;
  const infoCount = totalDiags - errorCount - warningCount;

  if (totalDiags === 0) {
    lines.push('Export guard: no issues found.');
    return lines.join('\n');
  }

  lines.push(
    `Export guard: ${totalDiags} issue(s) — ${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info(s).`,
  );

  // Show blocking errors first, naming the effect/transition and route when available
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'error') {
      const name = diag.detail?.effectType
        ? ` effect "${diag.detail.effectType}"`
        : diag.detail?.transitionType
          ? ` transition "${diag.detail.transitionType}"`
          : diag.detail?.clipType
            ? ` clip type "${diag.detail.clipType}"`
            : diag.detail?.shaderId
              ? ` shader "${diag.detail.shaderId}"`
            : '';
      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
    }
  }

  // Then warnings — also name effects/transitions/clip types
  for (const diag of guardResult.diagnostics) {
    if (diag.severity === 'warning') {
      const name = diag.detail?.effectType
        ? ` effect "${diag.detail.effectType}"`
        : diag.detail?.transitionType
          ? ` transition "${diag.detail.transitionType}"`
          : diag.detail?.clipType
            ? ` clip type "${diag.detail.clipType}"`
            : diag.detail?.shaderId
              ? ` shader "${diag.detail.shaderId}"`
            : '';
      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
    }
  }

  // Append per-route blocker summaries from findings (when available)
  const blockerFindings = (guardResult.findings ?? []).filter((f) => f.severity === 'error');
  if (blockerFindings.length > 0) {
    lines.push('');
    lines.push('Route blockers:');
    for (const finding of blockerFindings) {
      const name = finding.detail?.effectType
        ? `"${finding.detail.effectType}"`
        : finding.detail?.transitionType
          ? `"${finding.detail.transitionType}"`
          : finding.detail?.shaderId
            ? `"${finding.detail.shaderId}"`
          : 'unknown';
      const route = finding.route ?? 'unknown-route';
      lines.push(`  ${name} blocked on ${route}: ${finding.message}`);
    }
  }

  return lines.join('\n');
}

function exportDiagnosticId(diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number], index: number): string {
  const detail = diagnostic.detail ?? {};
  return [
    'export-guard',
    diagnostic.code,
    diagnostic.extensionId ?? 'host',
    diagnostic.contributionId ?? 'timeline',
    detail.clipId ?? 'no-clip',
    detail.effectType ?? detail.transitionType ?? detail.clipType ?? detail.shaderId ?? index,
  ].join(':');
}

function blockerReasonForExportDiagnostic(diagnostic: ExportDiagnostic): RenderBlockerReason {
  if (diagnostic.code.includes('unknown') || diagnostic.code.includes('missing')) {
    return 'missing-contribution';
  }
  if (diagnostic.code.includes('inactive')) {
    return 'inactive-extension';
  }
  if (diagnostic.code.includes('live-binding')) {
    return 'live-unbaked';
  }
  if (diagnostic.code.includes('shader')) {
    return 'missing-material';
  }
  return 'route-unsupported';
}

function exportDiagnosticToPlannerFinding(diagnostic: ExportDiagnostic, index: number): CapabilityFinding {
  const route = diagnostic.detail?.renderRoute === 'worker-export' || diagnostic.detail?.renderRoute === 'preview'
    ? diagnostic.detail.renderRoute
    : 'browser-export';
  const reason = diagnostic.severity === 'error'
    ? blockerReasonForExportDiagnostic(diagnostic)
    : undefined;

  return {
    id: exportDiagnosticId(diagnostic, index),
    severity: diagnostic.severity,
    route,
    ...(reason ? { reason } : {}),
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    detail: {
      ...(diagnostic.detail ?? {}),
      source: 'export-guard-compat',
      code: diagnostic.code,
    },
  };
}

function planFromExportGuardResult(
  guardResult: ReturnType<typeof scanExportConfig>,
): RenderPlannerResult {
  const diagnostics: CapabilityFinding[] = [
    ...(guardResult.findings ?? []),
    ...(guardResult.blockers ?? []),
    ...guardResult.diagnostics.map(exportDiagnosticToPlannerFinding),
  ];
  return planRender({ diagnostics });
}

function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
  const outputFormats = extensionRuntime?.outputFormats
    ?? extensionRuntime?.config?.outputFormats
    ?? [];
  return outputFormats.map((format) => ({
    ...format,
    availableRoutes: format.availableRoutes ?? [],
    routeRequirements: format.routeRequirements ?? [],
    processRequirements: format.processRequirements ?? [],
    blockers: format.blockers ?? [],
    nextActions: format.nextActions ?? [],
    sidecars: format.sidecars ?? [],
  }));
}

function toCollectionDiagnostic(
  diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number],
  index: number,
): Diagnostic {
  return {
    id: exportDiagnosticId(diagnostic, index),
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
    ...(diagnostic.detail ? { detail: { ...diagnostic.detail, source: 'export-guard' } } : { detail: { source: 'export-guard' } }),
  };
}

// ---------------------------------------------------------------------------
// M6: Export format categorization
// ---------------------------------------------------------------------------

/** Categorize output format descriptors into compile-only and render-dependent groups. */
function categorizeExportFormats(
  outputFormats: readonly VideoEditorOutputFormatDescriptor[],
): {
  compileOnly: VideoEditorOutputFormatDescriptor[];
  renderDependent: VideoEditorOutputFormatDescriptor[];
} {
  const compileOnly: VideoEditorOutputFormatDescriptor[] = [];
  const renderDependent: VideoEditorOutputFormatDescriptor[] = [];
  for (const fmt of outputFormats) {
    if (fmt.requiresRender || fmt.disabled) {
      renderDependent.push(fmt);
    } else {
      compileOnly.push(fmt);
    }
  }
  return { compileOnly, renderDependent };
}

export function useRenderState(
  resolvedConfig: ResolvedTimelineConfig | null,
  renderMetadata: CompositionMetadata | null,
  exporter?: VideoEditorExporter | null,
  extensionRuntime?: ExtensionRuntime,
) {
  const [renderStatus, setRenderStatus] = useState<RenderStatus>('idle');
  const [renderLog, setRenderLog] = useState('');
  const [renderDirty, setRenderDirty] = useState(false);
  const [renderProgress, setRenderProgress] = useState<RenderProgress>(null);
  const [renderResultUrl, setRenderResultUrl] = useState<string | null>(null);
  const [renderResultFilename, setRenderResultFilename] = useState<string | null>(null);
  // M6: Export state
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle');
  const [exportLog, setExportLogState] = useState('');
  const [exportResultUrl, setExportResultUrl] = useState<string | null>(null);
  const [exportResultFilename, setExportResultFilename] = useState<string | null>(null);
  const effectRegistrySnapshot = useEffectRegistrySnapshot();
  const transitionRegistrySnapshot = useTransitionRegistrySnapshot();
  const clipTypeRegistrySnapshot = useClipTypeRegistrySnapshot();
  // M6: Derive export format categories from extension runtime
  const exportFormats = useMemo(() => {
    const outputFormats = outputFormatsForPlanning(extensionRuntime);
    return categorizeExportFormats(outputFormats);
  }, [extensionRuntime]);
  const diagnosticCollection = useContext(DataProviderContext)?.diagnosticCollection;

  useEffect(() => {
    return () => {
      if (renderResultUrl) {
        URL.revokeObjectURL(renderResultUrl);
      }
    };
  }, [renderResultUrl]);
  // M6: Cleanup export result URL on unmount
  useEffect(() => {
    return () => {
      if (exportResultUrl) {
        URL.revokeObjectURL(exportResultUrl);
      }
    };
  }, [exportResultUrl]);

  const startClientRender = useClientRender({
    resolvedConfig,
    metadata: renderMetadata,
    setRenderStatus,
    setRenderProgress,
    setRenderLog,
    setRenderDirty,
    setRenderResult: (updater) => {
      const nextValue = typeof updater === 'function'
        ? updater({ url: renderResultUrl, filename: renderResultFilename })
        : updater;

      if (renderResultUrl && renderResultUrl !== nextValue.url) {
        URL.revokeObjectURL(renderResultUrl);
      }

      setRenderResultUrl(nextValue.url);
      setRenderResultFilename(nextValue.filename);
    },
  });

  const runExportGuard = useCallback((): boolean => {
    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'export-guard');
    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'render-planner');

    // Skip guard work only when there is no active extension/provider registry input.
    if (
      isExtensionRuntimeEmpty(extensionRuntime)
      && effectRegistrySnapshot.records.length === 0
      && transitionRegistrySnapshot.records.length === 0
      && clipTypeRegistrySnapshot.records.length === 0
      && !hasTimelineShaderMetadata(resolvedConfig)
    ) {
      return true; // no blocker
    }

    if (!resolvedConfig || resolvedConfig.clips.length === 0) {
      return true; // nothing to scan
    }

    const builtIn = collectBuiltInKnownIds();
    const allContributions = extensionRuntime ? buildExtensionContributions(extensionRuntime) : [];
    const extIds = collectExtensionDeclaredIds(allContributions);
    const guardResult = scanExportConfig(resolvedConfig, builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);
    const plannerResult = planFromExportGuardResult(guardResult);

    guardResult.diagnostics.forEach((diagnostic, index) => {
      diagnosticCollection?.publish(toCollectionDiagnostic(diagnostic, index));
    });
    syncPlannerDiagnosticsToCollection(diagnosticCollection, plannerResult.blockers);

    // Emit structured diagnostics as concise render log output
    const log = formatExportGuardLog(guardResult);
    setRenderLog(log);

    if (plannerResult.blockers.length > 0) {
      // Planner-owned blockers are the canonical readiness decision.
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      return false; // blocker
    }

    // Extension-declared warnings only — preserve native routing
    return true; // no blocker
  }, [diagnosticCollection, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot, extensionRuntime, resolvedConfig]);

  const startRender = useCallback(async () => {
    // ---- export guard: scan for unknown IDs before routing ------------------
    if (!runExportGuard()) {
      return; // blocked by export guard
    }

    let decision = getFastRenderRouteDecision(resolvedConfig);
    if (!decision) {
      let importedDecision: {
      route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
      reason: string;
      };
      try {
        const renderRouter = await import('@/tools/video-editor/lib/renderRouter');
        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
      } catch (error) {
        setRenderStatus('error');
        setRenderProgress(null);
        setRenderDirty(false);
        setRenderLog(error instanceof Error
          ? `Render routing unavailable: ${error.message}`
          : 'Render routing unavailable.');
        return;
      }
      decision = importedDecision;
    }
    if (decision.route === 'preview-only') {
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(`Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`);
      return;
    }

    if (decision.route === 'worker-banodoco' || decision.route === 'external') {
      setRenderStatus('error');
      setRenderProgress(null);
      setRenderDirty(false);
      setRenderLog(`Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`);
      return;
    }

    if (exporter && resolvedConfig) {
      setRenderStatus('rendering');
      setRenderProgress({
        current: 0,
        total: renderMetadata?.durationInFrames ?? 1,
        percent: 0,
        phase: 'validating',
      });
      setRenderResultUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return null;
      });
      setRenderResultFilename(null);
      setRenderLog('');

      const job = await exporter.render({
        timeline: resolvedConfig,
        registry: resolvedConfig.registry,
        output: {
          file: resolvedConfig.output.file,
          fps: resolvedConfig.output.fps,
        },
      });

      job.subscribe((progress) => {
        setRenderLog(progress.log ?? '');
        setRenderProgress(progress.progress == null
          ? null
          : {
            current: Math.round((renderMetadata?.durationInFrames ?? 1) * progress.progress),
            total: renderMetadata?.durationInFrames ?? 1,
            percent: Math.round(progress.progress * 100),
            phase: progress.phase,
          });

        if (progress.phase === 'complete') {
          setRenderStatus('done');
          setRenderDirty(false);
          if (progress.resultUrl) {
            setRenderResultUrl(progress.resultUrl);
            setRenderResultFilename(resolvedConfig.output.file);
          }
          return;
        }

        if (progress.phase === 'failed') {
          setRenderStatus('error');
          setRenderDirty(false);
          return;
        }

        setRenderStatus('rendering');
      });
      return;
    }

    await startClientRender();
  }, [exporter, renderMetadata?.durationInFrames, resolvedConfig, startClientRender, runExportGuard]);

  // ---- M6: compile-only export ------------------------------------------------
  const startExport = useCallback(async (
    formatId: string,
    compileOnlyRegistry?: CompileOnlyOutputFormatRegistry,
  ) => {
    if (!resolvedConfig) {
      setExportStatus('error');
      setExportLogState('Export unavailable: no timeline configuration.');
      return;
    }

    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
    const outputPlan = planRender({
      outputFormats: plannerOutputFormats,
      processes: extensionRuntime?.processes ?? [],
      request: {
        outputFormatId: formatId,
        routes: ['browser-export'],
      },
      diagnostics: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabled
        ? [{
            id: `planner.outputFormat.${formatId}.disabled`,
            severity: 'error',
            route: 'browser-export',
            reason: 'inactive-extension',
            message: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabledReason
              ?? `Export format "${formatId}" is disabled.`,
            contributionId: formatId,
            detail: { source: 'output-format', outputFormatId: formatId },
          }]
        : [],
    });
    const browserOutputPlan = outputPlan.routePlans.find((routePlan) => routePlan.route === 'browser-export');
    const fmt = plannerOutputFormats.find((f) => f.id === formatId && !f.requiresRender && !f.disabled);
    if (!fmt || browserOutputPlan?.blocked) {
      const requestedFormat = plannerOutputFormats.find((f) => f.id === formatId);
      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
        ?? browserOutputPlan?.blockers[0]
        ?? outputPlan.blockers[0];
      setExportStatus('error');
      if (blocker) {
        setExportLogState(`Export blocked: ${blocker.message}`);
      } else if (requestedFormat) {
        setExportLogState(`Export blocked: "${requestedFormat.label}" is not available for browser export.`);
      } else {
        setExportLogState(`Export format "${formatId}" not found.`);
      }
      return;
    }

    // ---- M7: Run export guard before compile-only export --------------------
    // Compile-only exports don't need rendered pixels, but they still process
    // timeline data.  Unknown / missing-contribution effects should block
    // because the exported data would be invalid.  Route-specific capability
    // blockers (browser-export blocked, worker-export blocked) are surfaced
    // as warnings but do not prevent compile-only export.
    const guardPassed = runExportGuard();
    if (!guardPassed) {
      // Export guard found blocking errors (e.g. truly unknown effects).
      // Surface the guard log as the export error.
      setExportStatus('error');
      setExportLogState(
        `Export blocked by readiness scan. See render log for details.`,
      );
      return;
    }

    if (!compileOnlyRegistry || compileOnlyRegistry.size === 0) {
      setExportStatus('error');
      setExportLogState(`Export unavailable: no compile-only output handlers registered. Format "${fmt.label}" (${fmt.id}) requires a handler registered via ctx.export.registerOutputFormat().`);
      return;
    }

    setExportStatus('exporting');
    setExportLogState(`Exporting "${fmt.label}"...`);
    setExportResultUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setExportResultFilename(null);

    try {
      // Build timeline snapshot from resolved config
      const timeline = Object.freeze({
        id: resolvedConfig.output?.file ?? 'timeline',
        assetKeys: Object.freeze(Object.keys(resolvedConfig.registry ?? {})),
        clipCount: resolvedConfig.clips?.length ?? 0,
        trackCount: resolvedConfig.tracks?.length ?? 0,
        fps: resolvedConfig.output?.fps ?? 30,
        resolution: resolvedConfig.output?.resolution ?? '1920x1080',
      });

      // Build assets map from registry
      const assetsMap = new Map<string, any>();
      if (resolvedConfig.registry) {
        for (const [key, entry] of Object.entries(resolvedConfig.registry)) {
          assetsMap.set(key, Object.freeze(entry));
        }
      }
      const assets: ReadonlyMap<string, Readonly<any>> = Object.freeze(assetsMap);

      const result = await executeCompileOnlyOutput(compileOnlyRegistry, {
        formatId,
        timeline: timeline as any,
        assets: assets as any,
        extensionId: fmt.extensionId,
      });

      if (!result) {
        setExportStatus('error');
        setExportLogState(`Export failed: format "${fmt.label}" is not available in the compile-only registry.`);
        return;
      }

      // Create a downloadable blob from the artifact data
      const mimeType = fmt.outputMimeType ?? 'application/octet-stream';
      const blob = new Blob([result.data], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const filename = `export.${fmt.outputExtension}`;

      setExportResultUrl(url);
      setExportResultFilename(filename);
      setExportStatus('done');
      const diagCount = result.artifact.diagnostics?.length ?? 0;
      setExportLogState(
        `Export complete: "${fmt.label}" → ${filename}` +
        (result.hasBlockingErrors ? ' (with blocking errors)' : '') +
        (diagCount > 0 ? ` [${diagCount} diagnostic(s)]` : ''),
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setExportStatus('error');
      setExportLogState(`Export failed: ${message}`);
    }
  }, [resolvedConfig, extensionRuntime, runExportGuard]);

  return {
    renderStatus,
    renderLog,
    renderDirty,
    renderProgress,
    renderResultUrl,
    renderResultFilename,
    setRenderStatus,
    setRenderLog,
    setRenderDirty,
    setRenderProgress,
    startRender,
    // M6: Export state
    exportStatus,
    exportLog,
    exportResultUrl,
    exportResultFilename,
    exportFormats,
    startExport,
  };
}

exec
/bin/zsh -lc "sed -n '620,980p' src/tools/video-editor/runtime/exportGuard.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
}

// ---------------------------------------------------------------------------
// Effect scan helper
// ---------------------------------------------------------------------------

type EffectSlot = 'entrance' | 'exit' | 'continuous';

/** Routes that the export guard checks independently for each registered effect. */
const GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanEffect(
  clip: ResolvedTimelineClip,
  slot: EffectSlot,
  known: AllKnownIds,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  unknownEffects: Set<string>,
): void {
  // The effect can be stored as `ClipEntrance | ClipExit | ClipContinuous`
  // or as `TimelineEffect[] | Record<string, number>` in `effects`.
  const effect = clip[slot];
  if (!effect) return;

  let effectType: string | undefined;

  if (typeof effect === 'object' && 'type' in effect && typeof (effect as Record<string, unknown>).type === 'string') {
    effectType = (effect as Record<string, unknown>).type as string;
  }

  if (!effectType) return;

  const snapshotRecord = known.effectRegistrySnapshot?.get(effectType);
  if (!known.effectTypes.has(effectType) && !snapshotRecord) {
    const isExtDeclared = known.extensionEffectIds.has(effectType);
    const message = isExtDeclared
      ? `${capitalise(slot)} effect "${effectType}" is declared by an inactive extension and may not be available at export time.`
      : `${capitalise(slot)} effect "${effectType}" is not recognised. Ensure the required extension or registry is installed.`;

    diagnostics.push({
      severity: isExtDeclared ? 'warning' : 'error',
      code: 'export/unknown-effect-type',
      message,
      detail: { clipId: clip.id, effectType },
    });

    if (!isExtDeclared) {
      unknownEffects.add(effectType);
      pushEffectFindingAndBlocker(findings, blockers, {
        id: `export.effect.${clip.id}.${slot}.${effectType}.missing`,
        reason: 'missing-contribution',
        message,
        clipId: clip.id,
        effectType,
        slot,
        route: 'browser-export',
      });
    }
    return;
  }

  if (snapshotRecord) {
    scanEffectRecordRenderability(clip, slot, effectType, snapshotRecord, diagnostics, findings, blockers);
  }
}

function scanEffectRecordRenderability(
  clip: ResolvedTimelineClip,
  slot: EffectSlot,
  effectType: string,
  record: EffectRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `${capitalise(slot)} effect "${effectType}" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-effect',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        effectType,
        effectStatus: record.status,
        provenance: record.provenance,
      },
    });

    // Emit a blocker for every guarded route — an inactive effect can't be used anywhere.
    for (const route of GUARD_ROUTES) {
      pushEffectFindingAndBlocker(findings, blockers, {
        id: `export.effect.${clip.id}.${slot}.${effectType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `${capitalise(slot)} effect "${effectType}" on route "${route}" is registered but inactive.`,
        clipId: clip.id,
        effectType,
        slot,
        route,
        record,
      });
    }
    return;
  }

  // Check each guarded route independently.
  for (const route of GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — pass silently.
      continue;
    }

    if (capability.status === 'supported') {
      // Route is supported — pass silently.
      continue;
    }

    if (capability.status === 'unknown') {
      // Unknown support — emit a warning finding (non-blocking).
      const message = capability.message
        ?? `${capitalise(slot)} effect "${effectType}" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          effectType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.effect.${clip.id}.${slot}.${effectType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          effectType,
          slot,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked' — emit error diagnostic, finding, and blocker.
    const reason = capability.blockerReason ?? firstRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `${capitalise(slot)} effect "${effectType}" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-effect',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        effectType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushEffectFindingAndBlocker(findings, blockers, {
      id: `export.effect.${clip.id}.${slot}.${effectType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      effectType,
      slot,
      route,
      record,
    });
  }
}

function firstRouteBlockerReason(record: EffectRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushEffectFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    effectType: string;
    slot: EffectSlot;
    route: RenderRoute;
    record?: EffectRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    effectType: input.effectType,
    slot: input.slot,
  };
  if (input.record?.provenance) {
    detail.provenance = input.record.provenance;
  }
  const finding: CapabilityFinding = {
    id: input.id,
    severity: 'error',
    route: input.route,
    reason: input.reason,
    message: input.message,
    clipId: input.clipId,
    ...(input.record?.ownerExtensionId ? { extensionId: input.record.ownerExtensionId } : {}),
    ...(input.record?.contributionId ? { contributionId: input.record.contributionId } : {}),
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: input.route,
    reason: input.reason,
  });
}

// ---------------------------------------------------------------------------
// Transition scan helpers (T15)
// ---------------------------------------------------------------------------

/** Routes that the export guard checks independently for each registered transition. */
const TRANSITION_GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanTransitionRecordRenderability(
  clip: ResolvedTimelineClip,
  transitionType: string,
  record: TransitionRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `Transition "${transitionType}" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-transition',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        transitionType,
        transitionStatus: record.status,
        provenance: record.provenance,
      },
    });

    for (const route of TRANSITION_GUARD_ROUTES) {
      pushTransitionFindingAndBlocker(findings, blockers, {
        id: `export.transition.${clip.id}.${transitionType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `Transition "${transitionType}" on route "${route}" is registered but inactive.`,
        clipId: clip.id,
        transitionType,
        route,
        record,
      });
    }
    return;
  }

  for (const route of TRANSITION_GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — this is a blocker for worker-export by default
      if (route === 'worker-export') {
        const message = `Transition "${transitionType}" does not declare ${route} support. Worker export is blocked by default.`;
        diagnostics.push({
          severity: 'error',
          code: 'export/unrenderable-transition',
          message,
          extensionId: record.ownerExtensionId,
          contributionId: record.contributionId,
          detail: {
            clipId: clip.id,
            transitionType,
            renderRoute: route,
            blockerReason: 'route-unsupported',
            provenance: record.provenance,
          },
        });
        pushTransitionFindingAndBlocker(findings, blockers, {
          id: `export.transition.${clip.id}.${transitionType}.${route}.route-unsupported`,
          reason: 'route-unsupported',
          message,
          clipId: clip.id,
          transitionType,
          route,
          record,
        });
      }
      continue;
    }

    if (capability.status === 'supported') continue;

    if (capability.status === 'unknown') {
      const message = capability.message
        ?? `Transition "${transitionType}" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          transitionType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.transition.${clip.id}.${transitionType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          transitionType,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked'
    const reason = capability.blockerReason ?? firstTransitionRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `Transition "${transitionType}" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-transition',
      message,

exec
/bin/zsh -lc "sed -n '1,280p' src/tools/video-editor/runtime/renderPlanner.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import { describe, expect, it } from 'vitest';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  CapabilityFinding,
  CapabilityRequirement,
  ProcessStatus,
  RenderMaterialRef,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import type {
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

function snapshotWithLiveBinding(): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      {
        id: 'clip-1',
        track: 'V1',
        at: 0,
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'V1',
        kind: 'visual',
        label: 'V1',
        muted: false,
      },
    ],
    assetKeys: [],
    app: {},
    liveBindings: [
      {
        bindingId: 'binding-1',
        clipId: 'clip-1',
        sourceId: 'webcam-1',
        sourceKind: 'webcam',
        status: 'active',
      },
    ],
    outputMetadata: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
  };
}

function snapshotWithShaders(): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      {
        id: 'clip-1',
        track: 'V1',
        at: 0,
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'V1',
        kind: 'visual',
        label: 'V1',
        muted: false,
      },
    ],
    assetKeys: [],
    app: {},
    shaders: [
      {
        id: 'clip-1:shader:shader.preview.clip',
        shaderId: 'shader.preview.clip',
        scope: 'clip',
        clipId: 'clip-1',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
        enabled: true,
      },
      {
        id: 'postprocess:shader:shader.preview.post',
        shaderId: 'shader.preview.post',
        scope: 'postprocess',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
        enabled: true,
      },
    ],
    outputMetadata: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
  };
}

function requirement(input: Partial<CapabilityRequirement> & Pick<CapabilityRequirement, 'id' | 'route'>): CapabilityRequirement {
  return {
    sourceRef: { source: 'extension', extensionId: 'ext.requirements', contributionId: 'reqs' },
    requiredCapabilities: ['browser-export'],
    determinism: 'deterministic',
    ...input,
  };
}

function renderDependentOutput(): VideoEditorOutputFormatDescriptor {
  return {
    id: 'dataset.zip',
    extensionId: 'ext.dataset',
    order: 2,
    label: 'Dataset bundle',
    requiresRender: true,
    outputExtension: '.zip',
    outputMimeType: 'application/zip',
    disabled: false,
    availableRoutes: ['sidecar-export'],
    routeRequirements: [
      {
        routes: ['sidecar-export'],
        requiredCapabilities: ['sidecar-export', 'json-rpc'],
        processId: 'dataset-process',
        operationId: 'exportDataset',
        determinism: 'process-dependent',
        unavailableMessage: 'Start the dataset process before exporting the bundle.',
      },
    ],
    processRequirements: [
      {
        processId: 'dataset-process',
        operationId: 'exportDataset',
        requiredCapabilities: ['json-rpc'],
      },
    ],
    blockers: [],
    nextActions: [
      {
        kind: 'start-process',
        label: 'Start dataset process',
        route: 'sidecar-export',
        processId: 'dataset-process',
        operationId: 'exportDataset',
      },
    ],
    capabilities: {
      extensionId: 'ext.dataset',
      contributionId: 'dataset.zip',
      routes: ['sidecar-export'],
      determinism: 'process-dependent',
      fullySupported: true,
      anyBlocked: false,
      sourceRefs: [
        { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
      ],
      capabilityRequirements: [
        {
          id: 'ext.dataset.dataset.zip.sidecar-export',
          sourceRef: { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
          route: 'sidecar-export',
          requiredCapabilities: ['sidecar-export'],
          determinism: 'process-dependent',
          routeFit: { route: 'sidecar-export', fit: 'supported' },
          blocking: false,
        },
      ],
    },
    sidecars: [],
  };
}

function processDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'process-contribution',
    extensionId: 'ext.dataset',
    processId: 'dataset-process',
    label: 'Dataset process',
    spec: {
      id: 'dataset-process',
      label: 'Dataset process',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'node',
        args: ['dataset-process.js'],
      },
      operations: [
        {
          id: 'exportDataset',
          label: 'Export dataset',
          routes: ['sidecar-export'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'exportDataset',
        label: 'Export dataset',
        routes: ['sidecar-export'],
      },
    ],
    availableRoutes: ['sidecar-export'],
    requiredBy: [
      { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
    ],
    blockers: [],
    nextActions: [
      {
        kind: 'start-process',
        label: 'Start Dataset process',
        processId: 'dataset-process',
      },
    ],
  };
}

function shaderMaterializerDescriptor(): VideoEditorShaderDescriptor {
  return {
    id: 'ext.shader.clip',
    extensionId: 'ext.shader',
    shaderId: 'shader.preview.clip',
    label: 'Preview clip shader',
    pass: 'clip',
    materializer: {
      processId: 'shader-materializer',
      operationId: 'materializeClipShader',
      requiredCapabilities: ['render-material', 'shader-materializer'],
    },
    hasSourceMetadata: false,
  };
}

function shaderMaterializerProcess(): VideoEditorProcessDescriptor {
  return {
    id: 'shader-materializer-process',
    extensionId: 'ext.shader',
    processId: 'shader-materializer',
    label: 'Shader materializer',
    spec: {
      id: 'shader-materializer',
      label: 'Shader materializer',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'node',
        args: ['shader-materializer.js'],
      },
      operations: [
        {
          id: 'materializeClipShader',
          label: 'Materialize clip shader',
          routes: ['browser-export'],
          outputKinds: ['material'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'materializeClipShader',
        label: 'Materialize clip shader',
        routes: ['browser-export'],
        outputKinds: ['material'],
      },
    ],
    availableRoutes: ['browser-export'],
    requiredBy: [
      { source: 'extension', extensionId: 'ext.shader', contributionId: 'ext.shader.clip' },

codex
A concrete split is emerging: render starts are blocked by `runExportGuard()` then by router decisions, while compile-only exports first run an output-format planner pass, then reuse the same guard. That means planner blockers are central but not yet the only source of user-visible “blocked” strings.
exec
/bin/zsh -lc "sed -n '980,1220p' src/tools/video-editor/runtime/renderPlanner.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '980,1260p' src/tools/video-editor/runtime/exportGuard.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }

  const findings = sortedFindings(acc.findings);
  const blockers = sortedBlockers([
    ...acc.blockers,
    ...findings.map(blockerForFinding).filter((blocker): blocker is RenderBlocker => Boolean(blocker)),
  ]);
  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
  const routes = Object.freeze(routePlans.map((routePlan) => Object.freeze({
    route: routePlan.route,
    blockerCount: routePlan.blockerCount,
    findingCount: routePlan.findingCount,
    blocked: routePlan.blocked,
  })));
  const browserRoute = routePlans.find((route) => route.route === 'browser-export');
  const workerRoute = routePlans.find((route) => route.route === 'worker-export');

  return Object.freeze({
    guard: emptyGuard(findings, blockers),
    findings,
    blockers,
    routes,
    routePlans,
    diagnostics: findings,
    nextActions: sortedActions(acc.nextActions),
    canBrowserExport: !browserRoute?.blocked,
    canWorkerExport: !workerRoute?.blocked,
  });
}

 succeeded in 0ms:
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        transitionType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushTransitionFindingAndBlocker(findings, blockers, {
      id: `export.transition.${clip.id}.${transitionType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      transitionType,
      route,
      record,
    });
  }
}

function firstTransitionRouteBlockerReason(record: TransitionRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushTransitionFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    transitionType: string;
    route: RenderRoute;
    record?: TransitionRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    transitionType: input.transitionType,
  };
  if (input.record?.provenance) {
    detail.provenance = input.record.provenance;
  }
  const finding: CapabilityFinding = {
    id: input.id,
    severity: 'error',
    route: input.route,
    reason: input.reason,
    message: input.message,
    clipId: input.clipId,
    ...(input.record?.ownerExtensionId ? { extensionId: input.record.ownerExtensionId } : {}),
    ...(input.record?.contributionId ? { contributionId: input.record.contributionId } : {}),
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: input.route,
    reason: input.reason,
  });
}

// ---------------------------------------------------------------------------
// Clip-type registry scan helpers
// ---------------------------------------------------------------------------

/** Routes that the export guard checks independently for each registered clip type. */
const CLIP_TYPE_GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;

function scanClipTypeRecordRenderability(
  clip: ResolvedTimelineClip,
  clipType: string,
  record: ClipTypeRegistryRecord,
  diagnostics: ExportDiagnostic[],
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
): void {
  if (record.status !== 'active') {
    const message = `Clip type "${clipType}" is registered but inactive and cannot be used for export or preview.`;
    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-clip-type',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        clipType,
        clipTypeStatus: record.status,
        provenance: record.provenance,
      },
    });

    // Emit a blocker for every guarded route — an inactive clip type can't be used anywhere.
    for (const route of CLIP_TYPE_GUARD_ROUTES) {
      pushClipTypeFindingAndBlocker(findings, blockers, {
        id: `export.clipType.${clip.id}.${clipType}.inactive.${route}`,
        reason: 'inactive-extension',
        message: `Clip type "${clipType}" on route "${route}" is registered but inactive.`,
        clipId: clip.id,
        clipType,
        route,
        record,
      });
    }
    return;
  }

  // Active record — check each guarded route independently.
  for (const route of CLIP_TYPE_GUARD_ROUTES) {
    const capability = record.renderability.capabilities.find((cap) => cap.route === route);

    if (!capability) {
      // No capability declared for this route — pass silently (like effects).
      continue;
    }

    if (capability.status === 'supported') {
      // Route is supported — pass silently.
      continue;
    }

    if (capability.status === 'unknown') {
      // Unknown support — emit a warning finding (non-blocking).
      const message = capability.message
        ?? `Clip type "${clipType}" has unknown support for ${route}.`;
      diagnostics.push({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message,
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
        detail: {
          clipId: clip.id,
          clipType,
          renderRoute: route,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      findings.push({
        id: `export.clipType.${clip.id}.${clipType}.${route}.unknown`,
        severity: 'warning',
        route,
        reason: 'unknown',
        message,
        clipId: clip.id,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        ...(record.contributionId ? { contributionId: record.contributionId } : {}),
        detail: {
          clipType,
          provenance: record.provenance,
          determinism: capability.determinism,
        },
      });
      continue;
    }

    // status === 'blocked' — emit error diagnostic, finding, and blocker.
    const reason = capability.blockerReason ?? firstClipTypeRouteBlockerReason(record, route) ?? 'route-unsupported';
    const message = capability.message
      ?? `Clip type "${clipType}" does not support ${route}.`;

    diagnostics.push({
      severity: 'error',
      code: 'export/unrenderable-clip-type',
      message,
      extensionId: record.ownerExtensionId,
      contributionId: record.contributionId,
      detail: {
        clipId: clip.id,
        clipType,
        renderRoute: route,
        blockerReason: reason,
        provenance: record.provenance,
      },
    });
    pushClipTypeFindingAndBlocker(findings, blockers, {
      id: `export.clipType.${clip.id}.${clipType}.${route}.${reason}`,
      reason,
      message,
      clipId: clip.id,
      clipType,
      route,
      record,
    });
  }
}

function firstClipTypeRouteBlockerReason(record: ClipTypeRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
}

function pushClipTypeFindingAndBlocker(
  findings: CapabilityFinding[],
  blockers: RenderBlocker[],
  input: {
    id: string;
    reason: RenderBlockerReason;
    message: string;
    clipId: string;
    clipType: string;
    route: RenderRoute;
    record?: ClipTypeRegistryRecord;
  },
): void {
  const detail: Record<string, unknown> = {
    clipType: input.clipType,
  };
  if (input.record?.provenance) {
    detail.provenance = input.record.provenance;
  }
  const finding: CapabilityFinding = {
    id: input.id,
    severity: 'error',
    route: input.route,
    reason: input.reason,
    message: input.message,
    clipId: input.clipId,
    ...(input.record?.ownerExtensionId ? { extensionId: input.record.ownerExtensionId } : {}),
    ...(input.record?.contributionId ? { contributionId: input.record.contributionId } : {}),
    detail,
  };
  findings.push(finding);
  blockers.push({
    ...finding,
    severity: 'error',
    route: input.route,
    reason: input.reason,
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function capitalise(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

exec
/bin/zsh -lc "sed -n '280,760p' src/tools/video-editor/runtime/renderPlanner.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
      { source: 'extension', extensionId: 'ext.shader', contributionId: 'ext.shader.clip' },
    ],
    blockers: [],
    nextActions: [],
  };
}

function materialRef(
  id: string,
  overrides: Partial<RenderMaterialRef> = {},
): RenderMaterialRef {
  return {
    id,
    mediaKind: 'video',
    locator: { kind: 'provider', uri: `provider://materials/${id}` },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    producerExtensionId: 'ext.materials',
    ...overrides,
  };
}

describe('planRender', () => {
  it('derives route blockers from a public TimelineSnapshot without registry inputs', () => {
    const result = planRender({ snapshot: snapshotWithLiveBinding() });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(true);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 1, findingCount: 2, blocked: true },
      { route: 'worker-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'sidecar-export', blockerCount: 0, findingCount: 0, blocked: false },
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'snapshot.liveBinding.2.browser-export.live-unbaked',
        route: 'browser-export',
        reason: 'live-unbaked',
        severity: 'error',
      }),
    ]);
  });

  it('keeps findings, blockers, next actions, and route plans deterministic', () => {
    const warning: CapabilityFinding = {
      id: 'z-warning',
      severity: 'warning',
      route: 'worker-export',
      reason: 'unknown',
      message: 'Worker route has not been classified.',
    };
    const result = planRender({
      requirements: [
        requirement({
          id: 'b-requirement',
          route: 'worker-export',
          requiredCapabilities: ['worker-export'],
          determinism: 'unknown',
          routeFit: {
            route: 'worker-export',
            fit: 'unknown',
            reason: 'unknown',
            message: 'Worker route has not been classified.',
          },
          findings: [warning],
        }),
        requirement({
          id: 'a-requirement',
          route: 'browser-export',
          requiredCapabilities: ['browser-export'],
          determinism: 'deterministic',
          routeFit: { route: 'browser-export', fit: 'supported' },
        }),
      ],
    });

    expect(result.findings.map((finding) => finding.id)).toEqual([
      'b-requirement.worker-export.unknown',
      'z-warning',
    ]);
    expect(result.blockers).toEqual([]);
    expect(result.routePlans.map((routePlan) => routePlan.route)).toEqual([
      'preview',
      'browser-export',
      'worker-export',
      'sidecar-export',
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: false,
      determinism: 'unknown',
      findingCount: 2,
      requiredCapabilities: ['worker-export'],
    });
  });

  it('records worker route downgrades as route warnings without blocking worker export', () => {
    const result = planRender({
      requirements: [
        requirement({
          id: 'shader-transition-worker-downgrade',
          route: 'worker-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['worker-export', 'shader-fallback'],
          determinism: 'process-dependent',
          routeFit: {
            route: 'worker-export',
            fit: 'degraded',
            reason: 'process-dependent',
            message: 'Worker export will use a deterministic shader fallback.',
          },
        }),
      ],
    });

    expect(result.canWorkerExport).toBe(true);
    expect(result.blockers).toEqual([]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'shader-transition-worker-downgrade.worker-export.process-dependent',
        severity: 'warning',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Worker export will use a deterministic shader fallback.',
        extensionId: 'ext.shader',
        contributionId: 'transition.shader-wipe',
        detail: {
          source: 'capability-requirement',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['shader-fallback', 'worker-export'],
          determinism: 'process-dependent',
          routeFit: {
            route: 'worker-export',
            fit: 'degraded',
            reason: 'process-dependent',
            message: 'Worker export will use a deterministic shader fallback.',
          },
        },
      }),
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      findingCount: 1,
      determinism: 'process-dependent',
      requiredCapabilities: ['shader-fallback', 'worker-export'],
    });
  });

  it('blocks worker export for browser-only shader transitions with complete route metadata', () => {
    const result = planRender({
      requirements: [
        requirement({
          id: 'shader-transition-browser-route',
          route: 'browser-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['browser-export', 'webgl-shader'],
          determinism: 'deterministic',
          routeFit: {
            route: 'browser-export',
            fit: 'supported',
          },
        }),
        requirement({
          id: 'shader-transition-worker-route',
          route: 'worker-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['worker-export', 'webgl-shader'],
          determinism: 'process-dependent',
          blocking: true,
          routeFit: {
            route: 'worker-export',
            fit: 'blocked',
            reason: 'process-dependent',
            message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
          },
        }),
      ],
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(false);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      requiredCapabilities: ['browser-export', 'webgl-shader'],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: true,
      blockerCount: 1,
      findingCount: 1,
      determinism: 'process-dependent',
      requiredCapabilities: ['webgl-shader', 'worker-export'],
      blockers: [
        expect.objectContaining({
          id: 'shader-transition-worker-route.worker-export.process-dependent',
          severity: 'error',
          route: 'worker-export',
          reason: 'process-dependent',
          message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
          extensionId: 'ext.shader',
          contributionId: 'transition.shader-wipe',
          detail: {
            source: 'capability-requirement',
            sourceRef: {
              source: 'extension',
              extensionId: 'ext.shader',
              contributionId: 'transition.shader-wipe',
            },
            requiredCapabilities: ['webgl-shader', 'worker-export'],
            determinism: 'process-dependent',
            routeFit: {
              route: 'worker-export',
              fit: 'blocked',
              reason: 'process-dependent',
              message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
            },
          },
        }),
      ],
    });
  });

  it('blocks export for timeline shader metadata until a materializer produces RenderMaterial', () => {
    const result = planRender({ snapshot: snapshotWithShaders() });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      }),
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
      }),
    ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')?.requiredCapabilities)
      .toEqual(expect.arrayContaining(['render-material', 'shader-materializer']));
  });

  it('diagnoses duplicate clip and postprocess shaders instead of stacking planner requirements', () => {
    const snapshot = snapshotWithShaders();
    const result = planRender({
      snapshot: {
        ...snapshot,
        shaders: [
          ...(snapshot.shaders ?? []),
          {
            id: 'clip-1:shader:shader.preview.clip.second',
            shaderId: 'shader.preview.clip.second',
            scope: 'clip',
            clipId: 'clip-1',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip.second',
            enabled: true,
          },
          {
            id: 'postprocess:shader:shader.preview.post.second',
            shaderId: 'shader.preview.post.second',
            scope: 'postprocess',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.post.second',
            enabled: true,
          },
        ],
      },
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'unknown',
        message: 'Cannot add shader "shader.preview.clip.second" to clip "clip-1" because shader "shader.preview.clip" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip.second',
      }),
      expect.objectContaining({
        route: 'browser-export',
        reason: 'unknown',
        message: 'Cannot add postprocess shader "shader.preview.post.second" because postprocess shader "shader.preview.post" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post.second',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        message: 'Shader "shader.preview.clip.second" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
      expect.objectContaining({
        message: 'Shader "shader.preview.post.second" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
      }),
    ]));
  });

  it('uses registered shader materializer process routes for materialization next actions', () => {
    const result = planRender({
      snapshot: snapshotWithShaders(),
      shaders: [shaderMaterializerDescriptor()],
      processes: [shaderMaterializerProcess()],
      processStatuses: [
        {
          processId: 'shader-materializer',
          state: 'busy',
          message: 'Materializing clip shader.',
        },
      ],
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'snapshot.shader.2.browser-export.process-dependent',
        route: 'browser-export',
        reason: 'process-dependent',
        message: 'Shader "shader.preview.clip" has a materializer route for browser-export; run process "shader-materializer" to produce RenderMaterial.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
    ]));
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'snapshot.shader.2.browser-export.shader-materializer.discovered',
        severity: 'info',
        route: 'browser-export',
        detail: expect.objectContaining({
          source: 'shader-materializer',
          shaderId: 'shader.preview.clip',
          processId: 'shader-materializer',
          operationId: 'materializeClipShader',
          processState: 'busy',
          materializationState: 'in-progress',
        }),
      }),
    ]));
    expect(result.nextActions).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'resolve-blocker',
        route: 'browser-export',
        label: 'Materialize shader shader.preview.clip',
        processId: 'shader-materializer',
        operationId: 'materializeClipShader',
      }),
    ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')?.nextActions)
      .toEqual(expect.arrayContaining([
        expect.objectContaining({
          kind: 'resolve-blocker',
          route: 'browser-export',
          processId: 'shader-materializer',
          operationId: 'materializeClipShader',
        }),
      ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')?.nextActions)
      .toEqual([]);
  });

  it('plans normalized render-dependent output formats as process-dependent route blockers', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'worker-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'sidecar-export', blockerCount: 2, findingCount: 2, blocked: true },
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      outputFormatIds: ['dataset.zip'],
      processRequirements: [
        {
          processId: 'dataset-process',
          operationId: 'exportDataset',
          requiredCapabilities: ['json-rpc'],
        },
      ],
      nextActions: [
        expect.objectContaining({ kind: 'start-process', processId: 'dataset-process' }),
        expect.objectContaining({ kind: 'start-process', processId: 'dataset-process', route: 'sidecar-export' }),
      ],
    });
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
      }),
    ]);
  });

  it('surfaces missing requested output formats as structured request blockers', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      request: { outputFormatId: 'missing.format', route: 'sidecar-export' },
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: true,
      blockerCount: 1,
    });
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.missing.format.missing',
        route: 'sidecar-export',
        reason: 'missing-contribution',
        contributionId: 'missing.format',
      }),
    ]);
  });

  it('surfaces requested route support and request-level capabilities in route plans', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      request: {
        outputFormatId: 'dataset.zip',
        routes: ['browser-export', 'sidecar-export'],
        requiredCapabilities: ['timeline-render'],
      },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      requiredCapabilities: ['timeline-render'],
      blockers: [
        expect.objectContaining({
          id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.route-unsupported',
          reason: 'route-unsupported',
        }),
      ],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      requiredCapabilities: ['json-rpc', 'sidecar-export', 'timeline-render'],
      outputFormatIds: ['dataset.zip'],
    });
  });

  it('converts materialize-on-export live material refs into browser-export blockers', () => {
    const materialRef: RenderMaterialRef = {

exec
/bin/zsh -lc "sed -n '1,760p' src/tools/video-editor/runtime/exportGuard.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  KnownIdCollection,
  InactiveKnownIds,
  ExportGuardResult,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import type { ExtensionContribution } from '@reigh/editor-sdk';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClip(
  id: string,
  overrides?: Partial<ResolvedTimelineConfig['clips'][number]>,
): ResolvedTimelineConfig['clips'][number] {
  return {
    id,
    at: 0,
    track: 'V1',
    clipType: 'media',
    ...overrides,
  };
}

function makeConfig(
  clips: ResolvedTimelineConfig['clips'],
): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips,
    registry: {},
  };
}

const RegistryEffect: FC<EffectComponentProps> = ({ children }) => children;

function effectRecord(
  effectId: string,
  overrides: Partial<EffectRegistryRecord> = {},
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `test:effect:${effectId}`,
    component: RegistryEffect,
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function snapshotWith(records: readonly EffectRegistryRecord[]): EffectRegistrySnapshot {
  const byId = new Map(records.map((record) => [record.effectId, record]));
  return Object.freeze({
    records: Object.freeze([...records]),
    diagnostics: Object.freeze([]),
    get: (effectId: string) => byId.get(effectId),
    has: (effectId: string) => byId.has(effectId),
  });
}

function clipTypeRecord(
  clipTypeId: string,
  overrides: Partial<ClipTypeRegistryRecord> = {},
): ClipTypeRegistryRecord {
  return {
    clipTypeId,
    contributionId: `test:clipType:${clipTypeId}`,
    renderer: { render: () => null },
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function clipTypeSnapshotWith(records: readonly ClipTypeRegistryRecord[]): ClipTypeRegistrySnapshot {
  const byId = new Map(records.map((record) => [record.clipTypeId, record]));
  return Object.freeze({
    records: Object.freeze([...records]),
    diagnostics: Object.freeze([]),
    get: (clipTypeId: string) => byId.get(clipTypeId),
    has: (clipTypeId: string) => byId.has(clipTypeId),
  });
}

// ---------------------------------------------------------------------------
// Built-in ID collection
// ---------------------------------------------------------------------------

describe('collectBuiltInKnownIds', () => {
  it('returns a frozen KnownIdCollection', () => {
    const ids = collectBuiltInKnownIds();
    expect(Object.isFrozen(ids)).toBe(true);
  });

  it('includes BUILTIN_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('media')).toBe(true);
    expect(ids.clipTypes.has('hold')).toBe(true);
    expect(ids.clipTypes.has('text')).toBe(true);
    expect(ids.clipTypes.has('effect-layer')).toBe(true);
  });

  it('includes TRUSTED_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('image-jump')).toBe(true);
    expect(ids.clipTypes.has('title-card')).toBe(true);
    expect(ids.clipTypes.has('section-hook')).toBe(true);
    expect(ids.clipTypes.has('art-card')).toBe(true);
    expect(ids.clipTypes.has('resource-card')).toBe(true);
    expect(ids.clipTypes.has('cta-card')).toBe(true);
  });

  it('includes built-in entrance effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('slide-up')).toBe(true);
    expect(ids.effectTypes.has('fade')).toBe(true);
    expect(ids.effectTypes.has('zoom-in')).toBe(true);
    expect(ids.effectTypes.has('bounce')).toBe(true);
  });

  it('includes built-in exit effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('fade-out')).toBe(true);
    expect(ids.effectTypes.has('dissolve')).toBe(true);
    expect(ids.effectTypes.has('shrink')).toBe(true);
  });

  it('includes built-in continuous effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('ken-burns')).toBe(true);
    expect(ids.effectTypes.has('float')).toBe(true);
    expect(ids.effectTypes.has('glitch')).toBe(true);
    expect(ids.effectTypes.has('slow-zoom')).toBe(true);
    expect(ids.effectTypes.has('drift')).toBe(true);
  });

  it('includes built-in transition types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.transitionTypes.has('crossfade')).toBe(true);
    expect(ids.transitionTypes.has('wipe')).toBe(true);
    expect(ids.transitionTypes.has('slide-push')).toBe(true);
    expect(ids.transitionTypes.has('zoom-through')).toBe(true);
  });

  it('has no effect/transition overlap with clip types', () => {
    const ids = collectBuiltInKnownIds();
    // Clip types and effect types are separate namespaces
    for (const ct of ids.clipTypes) {
      expect(ids.effectTypes.has(ct)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// Extension-declared ID collection
// ---------------------------------------------------------------------------

describe('collectExtensionDeclaredIds', () => {
  it('returns frozen empty sets for empty input', () => {
    const result = collectExtensionDeclaredIds([]);
    expect(Object.isFrozen(result)).toBe(true);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores bridged contribution kinds (slot, dialog, panel, inspectorSection)', () => {
    // M1-bridged kinds are skipped — they are active, not inactive
    const contributions: ExtensionContribution[] = [
      { id: 'c1' as any, kind: 'slot', slot: 'toolbar' },
      { id: 'c2' as any, kind: 'dialog' },
      { id: 'c3' as any, kind: 'panel' },
      { id: 'c4' as any, kind: 'inspectorSection' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores inactive contributions without effectId/transitionId/clipTypeId', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
  });

  it('skips bridged effect-kind contributions (M7 bridged)', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect', effectId: 'my-custom-effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    // Effect is M7-bridged, so it is NOT collected as inactive
    expect(result.effectIds.has('my-custom-effect')).toBe(false);
  });

  it('skips bridged transition-kind contributions (M8 bridged)', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.2' as any, kind: 'transition', transitionId: 'my-custom-transition' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    // Transition is M8-bridged, so it is NOT collected as inactive
    expect(result.transitionIds.has('my-custom-transition')).toBe(false);
  });

  it('collects clipTypeId from clipType-kind inactive contributions', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.3' as any, kind: 'clipType', clipTypeId: 'my-custom-clip' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.clipTypeIds.has('my-custom-clip')).toBe(true);
  });

  it('deduplicates across multiple contributions (clipType, not bridged)', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'clipType', clipTypeId: 'shared-clip' },
      { id: 'contrib.2' as any, kind: 'clipType', clipTypeId: 'shared-clip' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.clipTypeIds.size).toBe(1);
    expect(result.clipTypeIds.has('shared-clip')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — empty / null config
// ---------------------------------------------------------------------------

describe('scanExportConfig — empty config', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('returns empty result for null config', () => {
    const result = scanExportConfig(null, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns empty result for config with no clips', () => {
    const result = scanExportConfig(makeConfig([]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known clip types pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known clip types', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes built-in clip type "media"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'media' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes built-in clip type "text"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'text' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "title-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'title-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "art-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'art-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — live binding blockers
// ---------------------------------------------------------------------------

describe('scanExportConfig — live binding blockers', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  function liveClip(
    id: string,
    binding: Record<string, unknown>,
  ): ResolvedTimelineConfig['clips'][number] {
    return makeClip(id, {
      app: {
        live: {
          bindings: [binding],
        },
      },
    } as Partial<ResolvedTimelineConfig['clips'][number]>);
  }

  it('blocks active, missing, disposed, orphaned, malformed, and partially baked live bindings', () => {
    const config = makeConfig([
      liveClip('active-clip', {
        bindingId: 'active-binding',
        sourceId: 'src-active',
        sourceKind: 'generated',
        resolutionStatus: 'active',
      }),
      liveClip('missing-clip', {
        bindingId: 'missing-binding',
        sourceId: 'src-missing',
        sourceKind: 'generated',
      }),
      liveClip('disposed-clip', {
        bindingId: 'disposed-binding',
        sourceId: 'src-disposed',
        sourceKind: 'generated',
        sourceStatus: 'disposed',
      }),
      liveClip('orphaned-clip', {
        bindingId: 'orphaned-binding',
        sourceId: 'src-orphaned',
        sourceKind: 'generated',
        sourceStatus: 'orphaned',
      }),
      liveClip('partial-clip', {
        bindingId: 'partial-binding',
        sourceId: 'src-partial',
        sourceKind: 'generated',
        bake: {
          status: 'partial',
          unresolvedRanges: [{ startFrame: 10, endFrame: 20 }],
        },
      }),
      liveClip('malformed-clip', {
        sourceId: 'src-malformed',
        sourceKind: 'generated',
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.hasBlockingErrors).toBe(true);
    expect(result.diagnostics.filter((diag) => diag.code === 'export/live-binding-unresolved')).toHaveLength(6);
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toHaveLength(6);
    expect(result.findings.map((finding) => finding.detail?.resolutionStatus).sort()).toEqual([
      'active',
      'disposed',
      'malformed',
      'missing',
      'orphaned',
      'partiallyBaked',
    ]);
  });

  it('does not block fully baked deterministic live bindings', () => {
    const config = makeConfig([
      liveClip('baked-clip', {
        bindingId: 'baked-binding',
        sourceId: 'src-baked',
        sourceKind: 'generated',
        bake: {
          status: 'complete',
          deterministicRefs: [
            {
              kind: 'asset',
              ref: 'asset:baked',
              producerId: 'test-producer',
              inputHash: 'sha256:baked',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.filter((diag) => diag.code === 'export/live-binding-unresolved')).toEqual([]);
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown clip type
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown clip type', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error diagnostic for truly unknown clip type', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'alien-format' })]);
    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.detail?.clipId).toBe('c1');
    expect(diag.detail?.clipType).toBe('alien-format');
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning diagnostic for extension-declared (inactive) clip type', () => {
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.c' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const config = makeConfig([makeClip('c1', { clipType: 'future-clip' })]);
    const result = scanExportConfig(config, builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('warning');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.message).toContain('inactive extension');
    // Extension-declared clip types do NOT appear in unknownClipTypes
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known effects pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes provider snapshot effect IDs that are absent from legacy known IDs', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'provider-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([effectRecord('provider-glow')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown effects
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
        detail: { effectType: 'crazy-spin', slot: 'entrance' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
      }),
    ]);
  });

  it('keeps scan output as planner-compatible compatibility input', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const scan = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    const planned = planRender({ diagnostics: [...scan.findings, ...scan.blockers] });

    expect(planned.canBrowserExport).toBe(false);
    expect(planned.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      blockers: [
        expect.objectContaining({
          id: 'export.effect.c1.entrance.crazy-spin.missing',
          reason: 'missing-contribution',
        }),
      ],
    });
  });

  it('emits error for unknown continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['hyperspace']);
  });

  it('emits error for unknown exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['explode-out']);
  });

  it('emits warning for extension-declared (inactive) clipType with unknown effect', () => {
    // Effect is M7-bridged, so we test with clipType (M3, not bridged)
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.e' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-clip',
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits shared export blocker vocabulary for provider snapshot effects that cannot browser-export', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'preview-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('preview-glow', {
        ownerExtensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'preview-only',
            },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview Glow only supports interactive preview.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'preview-glow',
          renderRoute: 'browser-export',
          blockerReason: 'preview-only',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        clipId: 'c1',
        detail: { effectType: 'preview-glow', slot: 'continuous', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
      }),
    ]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('blocks worker-export independently of browser-export for provider effects that lack worker capability', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'browser-only-effect', duration: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('browser-only-effect', {
        ownerExtensionId: 'ext.browser',
        contributionId: 'ext.browser:effect:browser-only-effect',
        renderability: {
          defaultRoute: 'browser-export',
          determinism: 'deterministic',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'blocked',
              determinism: 'process-dependent',
              blockerReason: 'process-dependent',
              message: 'Browser-only effect requires DOM APIs unavailable in worker.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    // Browser-export is supported, worker-export is blocked — one error diagnostic
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',

codex
The tests confirm the bridge is intentional: `exportGuard.test.ts` has a compatibility test that feeds guard findings/blockers into `planRender`, and planner tests cover live bindings, shader materializers, output formats, material refs, and render groups. I’m checking docs and examples now for what behavior users or extension authors have been told to expect.
exec
/bin/zsh -lc "sed -n '760,1240p' src/tools/video-editor/runtime/renderPlanner.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "sed -n '760,1400p' src/tools/video-editor/runtime/exportGuard.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    const materialRef: RenderMaterialRef = {
      id: 'mat-live-1',
      mediaKind: 'video',
      locator: { kind: 'provider', uri: 'provider://live/mat-live-1' },
      determinism: 'live-unbaked',
      replacementPolicy: 'materialize-on-export',
    };

    const result = planRender({ materialRefs: [materialRef] });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-live-1.browser-export.live-unbaked',
        route: 'browser-export',
        reason: 'live-unbaked',
        materialRefId: 'mat-live-1',
      }),
    ]);
  });

  it('materializes missing and stale material next actions while resolved material refs do not block', () => {
    const result = planRender({
      materialRefs: [
        materialRef('mat-missing'),
        materialRef('mat-stale'),
        materialRef('mat-resolved'),
      ],
      materialStatuses: [
        { materialRefId: 'mat-missing', state: 'missing', message: 'Material bytes are unavailable.' },
        { materialRefId: 'mat-stale', state: 'stale', message: 'Material was produced from an older source hash.' },
        { materialRefId: 'mat-resolved', state: 'resolved' },
      ],
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-missing.browser-export.missing-material',
        reason: 'missing-material',
        materialRefId: 'mat-missing',
      }),
      expect.objectContaining({
        id: 'planner.material.mat-stale.browser-export.materialization-failed',
        reason: 'materialization-failed',
        materialRefId: 'mat-stale',
      }),
    ]);
    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-resolved')).toBe(false);
    expect(result.nextActions).toEqual([
      expect.objectContaining({
        kind: 'resolve-blocker',
        label: 'Materialize mat-missing',
        message: 'Material bytes are unavailable.',
      }),
      expect.objectContaining({
        kind: 'resolve-blocker',
        label: 'Materialize mat-stale',
        message: 'Material was produced from an older source hash.',
      }),
    ]);
  });

  it('treats ready processes as resolved and degraded processes as warnings without subprocess work', () => {
    const readyStatus: ProcessStatus = {
      processId: 'dataset-process',
      state: 'ready',
      pid: 1234,
    };
    const degradedStatus: ProcessStatus = {
      processId: 'dataset-process',
      state: 'degraded',
      message: 'Dataset process is running with a fallback encoder.',
      healthCheck: 'encoder',
    };

    const ready = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [readyStatus],
      request: { outputFormatId: 'dataset.zip' },
    });
    const degraded = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [degradedStatus],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(ready.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      processRequirements: [
        {
          processId: 'dataset-process',
          operationId: 'exportDataset',
          requiredCapabilities: ['json-rpc'],
        },
      ],
    });
    expect(ready.blockers).toEqual([]);

    expect(degraded.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      findingCount: 2,
    });
    expect(degraded.findings).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent.degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-dependent',
        message: 'Dataset process is running with a fallback encoder.',
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent.degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-dependent',
        message: 'Dataset process is running with a fallback encoder.',
      }),
    ]);
  });

  it('blocks required missing and stale render-group passes and ignores resolved or optional passes', () => {
    const result = planRender({
      snapshot: {
        projectId: 'project-render-groups',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: [],
        app: {},
        renderGroups: [
          {
            id: 'hero-shot',
            clipIds: ['clip-a', 'clip-b'],
            groupType: 'multi-pass',
            requiredPasses: ['beauty', 'depth', 'normal'],
            passes: [
              {
                id: 'beauty-pass',
                passName: 'beauty',
                required: true,
                composable: true,
                materialRefId: 'mat-beauty',
                status: 'resolved',
              },
              {
                id: 'depth-pass',
                passName: 'depth',
                required: true,
                composable: true,
                materialRefId: 'mat-depth',
                status: 'missing',
              },
              {
                id: 'normal-pass',
                passName: 'normal',
                required: true,
                composable: true,
                materialRefId: 'mat-normal',
                status: 'stale',
              },
              {
                id: 'thumbnail-pass',
                passName: 'thumbnail',
                required: false,
                composable: false,
                status: 'missing',
              },
            ],
          },
        ],
      },
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.renderGroup.hero-shot.depth-pass.browser-export.missing-material',
        reason: 'missing-material',
        materialRefId: 'mat-depth',
      }),
      expect.objectContaining({
        id: 'planner.renderGroup.hero-shot.normal-pass.browser-export.materialization-failed',
        reason: 'materialization-failed',
        materialRefId: 'mat-normal',
      }),
    ]);
    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-beauty')).toBe(false);
    expect(result.blockers.some((blocker) => blocker.id.includes('thumbnail-pass'))).toBe(false);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      requiredCapabilities: ['render-groups'],
      determinism: 'process-dependent',
      nextActions: [
        expect.objectContaining({ label: 'Materialize hero-shot:depth' }),
        expect.objectContaining({ label: 'Materialize hero-shot:normal' }),
      ],
    });
  });
});

 succeeded in 0ms:
        code: 'export/unrenderable-effect',
        message: 'Browser-only effect requires DOM APIs unavailable in worker.',
        extensionId: 'ext.browser',
        contributionId: 'ext.browser:effect:browser-only-effect',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'browser-only-effect',
          renderRoute: 'worker-export',
          blockerReason: 'process-dependent',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.browser-only-effect.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Browser-only effect requires DOM APIs unavailable in worker.',
        clipId: 'c1',
        detail: { effectType: 'browser-only-effect', slot: 'entrance', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.browser-only-effect.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
      }),
    ]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits per-route blockers for inactive provider records across all GUARD_ROUTES', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'stale-effect', intensity: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('stale-effect', {
        ownerExtensionId: 'ext.stale',
        contributionId: 'ext.stale:effect:stale-effect',
        status: 'inactive',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: expect.stringContaining('inactive'),
        extensionId: 'ext.stale',
        contributionId: 'ext.stale:effect:stale-effect',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'stale-effect',
          effectStatus: 'inactive',
          provenance: 'bundled-extension',
        }),
      }),
    ]);
    // One finding+blocker per GUARD_ROUTE
    expect(result.findings).toHaveLength(3);
    expect(result.findings.map((f) => f.route).sort()).toEqual(['browser-export', 'preview', 'worker-export']);
    expect(result.blockers).toHaveLength(3);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits unknown-route-support warnings for provider effects with unknown worker-export capability', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'unclassified-effect', duration: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('unclassified-effect', {
        ownerExtensionId: 'ext.unclass',
        contributionId: 'ext.unclass:effect:unclassified-effect',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'unknown',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'unknown',
              determinism: 'unknown',
              message: 'Worker-export support has not been classified for this effect.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    // One warning for unknown worker-export
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message: 'Worker-export support has not been classified for this effect.',
        extensionId: 'ext.unclass',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'unclassified-effect',
          renderRoute: 'worker-export',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.exit.unclassified-effect.worker-export.unknown',
        severity: 'warning',
        route: 'worker-export',
        reason: 'unknown',
      }),
    ]);
    // Unknown support is non-blocking
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known transitions pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known transition "crossfade"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'crossfade', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known transition "wipe"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown transitions
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown transition', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'star-wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-transition-type');
    expect(result.diagnostics[0].detail?.transitionType).toBe('star-wipe');
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared (inactive) clipType with unknown transition', () => {
    // Transition is M8-bridged, so we test with clipType (M3, not bridged)
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.t' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-clip',
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Multiple diagnostics
// ---------------------------------------------------------------------------

describe('scanExportConfig — multiple diagnostics', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('collects multiple unknown types in one scan', () => {
    const clips = [
      makeClip('c1', {
        clipType: 'alien-format',
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
      makeClip('c2', {
        clipType: 'media',
        transition: { type: 'star-wipe', duration: 1 },
        continuous: { type: 'hyperspace', intensity: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 4 diagnostics: unknown clip type + unknown entrance + unknown transition + unknown continuous
    expect(result.diagnostics.length).toBe(4);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('handles multiple clips with same unknown types without duplication', () => {
    const clips = [
      makeClip('c1', { clipType: 'alien-format' }),
      makeClip('c2', { clipType: 'alien-format' }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 2 diagnostics (one per clip) but only one entry in unknownClipTypes
    expect(result.diagnostics.length).toBe(2);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clips (built-in clip type with effects)
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer clips', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits error for unknown continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('hyperspace');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('explode-out');
    expect(result.unknownEffects).toEqual(['explode-out']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared clipType on effect-layer clip', () => {
    // Effect is M7-bridged, so we test with clipType (M3, not bridged)
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.el' as any,
        kind: 'clipType',
        clipTypeId: 'future-effect-layer',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-effect-layer',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].detail?.clipType).toBe('future-effect-layer');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clip with unknown clip type + unknown effects combined
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer combined diagnostics', () => {
  it('collects both unknown clip type and unknown effect for effect-layer style clips', () => {
    const builtIn = collectBuiltInKnownIds();
    const extIds = collectExtensionDeclaredIds([]);

    const clips = [
      makeClip('c1', {
        clipType: 'custom-effect-layer',
        continuous: { type: 'hyperspace', intensity: 0.5 },
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 3 diagnostics: unknown clip type + unknown continuous + unknown entrance
    expect(result.diagnostics.length).toBe(3);
    expect(result.unknownClipTypes).toEqual(['custom-effect-layer']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — clip-type registry snapshot
// ---------------------------------------------------------------------------

describe('scanExportConfig — clip-type registry snapshot', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes a clip type registered in the snapshot with active status and supported browser-export', () => {
    const clip = makeClip('c1', { clipType: 'provider-slideshow' });
    const snapshot = clipTypeSnapshotWith([clipTypeRecord('provider-slideshow')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits error for an inactive clip type in the registry snapshot', () => {
    const clip = makeClip('c1', { clipType: 'stale-clip-type' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('stale-clip-type', {
        ownerExtensionId: 'ext.stale',
        status: 'inactive',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-clip-type',
        message: expect.stringContaining('inactive'),
        extensionId: 'ext.stale',
        contributionId: 'test:clipType:stale-clip-type',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'stale-clip-type',
          clipTypeStatus: 'inactive',
          provenance: 'bundled-extension',
        }),
      }),
    ]);
    // One finding+blocker per CLIP_TYPE_GUARD_ROUTE
    expect(result.findings).toHaveLength(3);
    expect(result.findings.map((f) => f.route).sort()).toEqual(['browser-export', 'preview', 'worker-export']);
    expect(result.blockers).toHaveLength(3);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for a clip type registered but blocked on browser-export', () => {
    const clip = makeClip('c1', { clipType: 'preview-only-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('preview-only-clip', {
        ownerExtensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'preview-only',
            },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview-only clip type cannot browser-export.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-clip-type',
        message: 'Preview-only clip type cannot browser-export.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'preview-only-clip',
          renderRoute: 'browser-export',
          blockerReason: 'preview-only',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
        message: 'Preview-only clip type cannot browser-export.',
        clipId: 'c1',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        detail: { clipType: 'preview-only-clip', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
      }),
    ]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for unknown route support on a clip type', () => {
    const clip = makeClip('c1', { clipType: 'unclassified-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('unclassified-clip', {
        ownerExtensionId: 'ext.unclass',
        contributionId: 'ext.unclass:clipType:unclassified-clip',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'unknown',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'unknown',
              determinism: 'unknown',
              message: 'Worker-export support has not been classified for this clip type.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message: 'Worker-export support has not been classified for this clip type.',
        extensionId: 'ext.unclass',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'unclassified-clip',
          renderRoute: 'worker-export',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.unclassified-clip.worker-export.unknown',
        severity: 'warning',
        route: 'worker-export',
        reason: 'unknown',
      }),
    ]);
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('still blocks truly unknown clip types not in registry, not in built-in, not extension-declared', () => {
    const clip = makeClip('c1', { clipType: 'alien-format' });
    const snapshot = clipTypeSnapshotWith([]); // empty registry

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unknown-clip-type',
        message: expect.stringContaining('not recognised'),
        detail: { clipId: 'c1', clipType: 'alien-format' },
      }),
    ]);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.alien-format.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
        detail: { clipType: 'alien-format' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.alien-format.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
      }),
    ]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('prioritises registry snapshot over built-in for non-built-in clip types (does not collide)', () => {
    // 'media' is built-in — registry snapshot is irrelevant
    // 'provider-hero' is only in registry — should pass
    const clip = makeClip('c1', { clipType: 'provider-hero' });
    const snapshot = clipTypeSnapshotWith([clipTypeRecord('provider-hero')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits exact missing materializer blockers for clip and postprocess shader metadata', () => {
    const clipShaderMessage = 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".';
    const postprocessShaderMessage = 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.';
    const clip = makeClip('c1', {
      app: {
        shader: {
          scope: 'clip',
          extensionId: 'ext.shader',
          contributionId: 'ext.shader.clip',
          shaderId: 'shader.preview.clip',
        },
      },
    });
    const config = {
      ...makeConfig([clip]),
      app: {
        shaderPostprocess: {
          scope: 'postprocess',
          extensionId: 'ext.shader',
          contributionId: 'ext.shader.post',

exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/runtime/extensionSurface.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import type { ReactNode } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type {
  ReighExtension,
  ExtensionContribution,
  ExtensionDiagnostic,
  ContributionKind,
  ParserContribution,
  OutputFormatContribution,
  SearchProviderContribution,
  MetadataFacetContribution,
  AssetDetailSectionContribution,
  MetadataFacetValueKind,
  EffectContribution,
  TransitionContribution,
  ShaderContribution,
  ShaderFallbackBehavior,
  ShaderMaterializerDescriptor,
  ShaderPassDescriptor,
  ShaderPassKind,
  ShaderSourceDescriptor,
  ShaderTextureSchema,
  ShaderUniformSchema,
  AgentToolContribution,
  ToolResultFamily,
  RenderRoute,
  DeterminismStatus,
  RenderBlockerReason,
  RenderDependentOutputDescriptor,
  SamplingConfig,
  RenderArtifactSidecarDescriptor,
  IntegrationCapabilities,
  CapabilityRequirement,
  CapabilitySourceRef,
  ProcessContribution,
  ProcessSpec,
  ProcessOperationSpec,
  ProjectExtensionRequirement,
} from '@reigh/editor-sdk';
import { contributionKindNotYetBridged } from '@reigh/editor-sdk';
import type { TimelineGestureOwner } from '@/tools/video-editor/lib/mobile-interaction-model';
import type {
  PackageState,
  PackageMetadata,
} from '@/tools/video-editor/runtime/extensionLoader';

export type VideoEditorSlotName =
  | 'header'
  | 'toolbar'
  | 'leftPanel'
  | 'rightPanel'
  | 'codePanel'
  | 'writingPanel'
  | 'stagePanel'
  | 'timelineFooter'
  | 'statusBar'
  | 'dialogs'
  | 'assetPanel'
  | 'inspectorPanel';

export interface VideoEditorRuntimeSlices {
  data: TimelineEditorDataContextValue;
  ops: TimelineEditorOpsContextValue;
  chrome: TimelineChromeContextValue;
  playback: TimelinePlaybackContextValue;
}

export interface VideoEditorRenderContext extends VideoEditorRuntimeSlices {
  provider: DataProvider;
  timelineId: string;
  timelineName: string | null;
  userId: string;
  extensions: VideoEditorExtensionRuntimeConfig;
}

export type VideoEditorVisibilityPredicate = (context: VideoEditorRenderContext) => boolean;
export type VideoEditorSlotRenderer = (context: VideoEditorRenderContext) => ReactNode;

export interface VideoEditorDialogDescriptor {
  id: string;
  order?: number;
  layer?: 'modal' | 'overlay';
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelDescriptor {
  id: string;
  placement: 'asset-panel';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorInspectorSectionDescriptor {
  id: string;
  placement: 'before-default' | 'after-default';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorOverlayDescriptor {
  id: string;
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelRegistryConfig {
  panels?: readonly VideoEditorPanelDescriptor[];
  inspectorSections?: readonly VideoEditorInspectorSectionDescriptor[];
}

export interface VideoEditorDialogHostConfig {
  dialogs?: readonly VideoEditorDialogDescriptor[];
}

export interface VideoEditorExtensionConfig {
  slots?: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost?: VideoEditorDialogHostConfig;
  registry?: VideoEditorPanelRegistryConfig;
  overlays?: readonly VideoEditorOverlayDescriptor[];
}

export interface VideoEditorExtensionRuntimeConfig {
  slots: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost: {
    dialogs: readonly VideoEditorDialogDescriptor[];
  };
  registry: {
    panels: readonly VideoEditorPanelDescriptor[];
    inspectorSections: readonly VideoEditorInspectorSectionDescriptor[];
  };
  overlays: readonly VideoEditorOverlayDescriptor[];
  /** M6: Normalized asset parser descriptors, provider-scoped and deterministically ordered. */
  assetParsers: readonly VideoEditorAssetParserDescriptor[];
  /** M6: Normalized output format descriptors (disabled diagnostics for render-dependent). */
  outputFormats: readonly VideoEditorOutputFormatDescriptor[];
  /** M12: Normalized process descriptors, declaration-only until host runtime activation. */
  processes: readonly VideoEditorProcessDescriptor[];
  /** M6: Normalized search provider descriptors, declaration-only until execution is bridged. */
  searchProviders: readonly VideoEditorSearchProviderDescriptor[];
  /** M6: Normalized metadata facet descriptors for the asset panel. */
  metadataFacets: readonly VideoEditorMetadataFacetDescriptor[];
  /** M6: Normalized asset detail section descriptors for the asset detail panel. */
  assetDetailSections: readonly VideoEditorAssetDetailSectionDescriptor[];
  /** M7: Normalized component-backed effect descriptors, provider-scoped and deterministically ordered. */
  effects: readonly VideoEditorEffectDescriptor[];
  /** M8: Normalized component-backed transition descriptors, provider-scoped and deterministically ordered. */
  transitions: readonly VideoEditorTransitionDescriptor[];
  /** M13: Normalized WebGL shader descriptors, provider-scoped and deterministically ordered. */
  shaders: readonly VideoEditorShaderDescriptor[];
  /** M10: Normalized agent tool descriptors, provider-scoped and deterministically ordered. */
  agentTools: readonly VideoEditorAgentToolDescriptor[];
}

export interface ResolvedVideoEditorPanelRegistry {
  assetPanels: readonly VideoEditorPanelDescriptor[];
  inspectorSections: {
    all: readonly VideoEditorInspectorSectionDescriptor[];
    beforeDefault: readonly VideoEditorInspectorSectionDescriptor[];
    afterDefault: readonly VideoEditorInspectorSectionDescriptor[];
  };
}

// ---------------------------------------------------------------------------
// M6: Asset parser / output format / search provider descriptors
// ---------------------------------------------------------------------------

/** A normalized asset parser descriptor produced by runtime normalization. */
export interface VideoEditorAssetParserDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  label: string;
  acceptMimeTypes?: readonly string[];
  acceptExtensions?: readonly string[];
  maxBytes?: number;
  required?: boolean;
}

/** A normalized output format descriptor produced by runtime normalization. */
export interface VideoEditorOutputFormatDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  label: string;
  requiresRender: boolean;
  outputExtension: string;
  outputMimeType?: string;
  description?: string;
  /** When true, direct compile-only execution is unavailable. */
  disabled: boolean;
  /** Reason for disabled state, surfaced in the export UI. */
  disabledReason?: string;
  /** Planner-visible routes declared by render-dependent output formats. */
  availableRoutes: readonly RenderRoute[];
  /** Render route/process requirements for planner-owned execution. */
  routeRequirements: readonly VideoEditorRouteRequirementDescriptor[];
  /** Process requirements referenced by this output format. */
  processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
  /** Declaration-time blockers that the planner should surface before execution. */
  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
  /** Suggested planner actions for making this output executable. */
  nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
  /** Aggregated capability metadata derived from the output declaration. */
  capabilities?: IntegrationCapabilities;
  /** Optional declarative sampling defaults for export configuration. */
  sampling?: SamplingConfig;
  /** Sidecar descriptors the output may produce. */
  sidecars: readonly RenderArtifactSidecarDescriptor[];
}

/** A normalized route requirement record consumed by render planning. */
export interface VideoEditorRouteRequirementDescriptor {
  routes: readonly RenderRoute[];
  requiredCapabilities: readonly string[];
  processId?: string;
  operationId?: string;
  determinism: DeterminismStatus;
  unavailableMessage?: string;
}

/** A normalized process dependency declared by an output or route. */
export interface VideoEditorProcessRequirementDescriptor {
  processId: string;
  operationId?: string;
  requiredCapabilities: readonly string[];
}

/** Declaration-time blocker metadata surfaced to the planner and UI. */
export interface VideoEditorPlannerBlockerDescriptor {
  id: string;
  extensionId: string;
  contributionId: string;
  route?: RenderRoute;
  reason: RenderBlockerReason;
  message: string;
  nextAction?: VideoEditorPlannerNextActionDescriptor;
}

/** Planner next-action metadata for resolving route/process/material blockers. */
export interface VideoEditorPlannerNextActionDescriptor {
  kind: 'select-route' | 'start-process' | 'resolve-blocker';
  label: string;
  route?: RenderRoute;
  processId?: string;
  operationId?: string;
  message?: string;
}

/** A normalized trusted-local process descriptor produced by runtime normalization. */
export interface VideoEditorProcessDescriptor {

exec
/bin/zsh -lc "sed -n '1,300p' src/tools/video-editor/runtime/outputFormatRegistry.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * Compile-only output format registry and execution.
 *
 * Manages registered compile-only output format handlers and executes them
 * against timeline snapshots and asset registries to produce deterministic
 * {@link RenderArtifact}-compatible artifacts.
 *
 * This module never calls render providers, render planner execution, or
 * media render routes.  Only `requiresRender: false` handlers are executed.
 *
 * @module outputFormatRegistry
 */

import type {
  CompileOnlyOutputResult,
  OutputFormatContribution,
  OutputFormatHandler,
  OutputFormatContext,
  TimelineSnapshot,
  AssetMetadata,
} from '@reigh/editor-sdk';
import {
  assertFinalArtifactHasManifest,
  createCompileOnlyArtifact,
  type RenderArtifact,
} from '@/tools/video-editor/runtime/renderability.ts';

// ---------------------------------------------------------------------------
// Registry types
// ---------------------------------------------------------------------------

/**
 * A registered compile-only output format entry.
 *
 * Associates a handler with its contribution metadata and the extension
 * that registered it.
 */
export interface CompileOnlyOutputFormatEntry {
  /** The contribution descriptor from the extension manifest. */
  readonly contribution: OutputFormatContribution;
  /** The handler registered by the extension. */
  readonly handler: OutputFormatHandler;
  /** The extension ID that owns this format. */
  readonly extensionId: string;
  /** Extension version, if available. */
  readonly extensionVersion?: string;
}

/**
 * Immutable registry of compile-only output format entries keyed by format ID.
 */
export type CompileOnlyOutputFormatRegistry = ReadonlyMap<string, CompileOnlyOutputFormatEntry>;

// ---------------------------------------------------------------------------
// Registry creation
// ---------------------------------------------------------------------------

/**
 * Create a compile-only output format registry from a list of entries.
 *
 * Only entries whose contribution has `requiresRender: false` are admitted.
 * Render-dependent formats (requiresRender: true) are silently skipped
 * because they require the render pipeline, which is not available here.
 *
 * Returns a frozen map keyed by contribution ID.
 */
export function createCompileOnlyOutputFormatRegistry(
  entries: readonly CompileOnlyOutputFormatEntry[],
): CompileOnlyOutputFormatRegistry {
  const map = new Map<string, CompileOnlyOutputFormatEntry>();
  for (const entry of entries) {
    if (entry.contribution.requiresRender) continue;
    map.set(entry.contribution.id as string, entry);
  }
  return Object.freeze(map);
}

// ---------------------------------------------------------------------------
// Execution input types
// ---------------------------------------------------------------------------

/**
 * Options for executing a compile-only output format.
 */
export interface CompileOnlyOutputExecutionOptions {
  /** The output format contribution ID to execute. */
  readonly formatId: string;
  /** Read-only snapshot of the current timeline state. */
  readonly timeline: TimelineSnapshot;
  /** Read-only map of asset key to asset metadata from the registry. */
  readonly assets: ReadonlyMap<string, Readonly<AssetMetadata>>;
  /** The extension that registered the handler (must match the entry). */
  readonly extensionId: string;
  /** Extension version, if available. */
  readonly extensionVersion?: string;
}

/**
 * The result of executing a compile-only output format.
 */
export interface CompileOnlyOutputExecutionResult {
  /** The deterministic artifact produced by the execution. */
  readonly artifact: RenderArtifact;
  /** The raw output data bytes. */
  readonly data: Uint8Array;
  /** Whether the execution had blocking errors. */
  readonly hasBlockingErrors: boolean;
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

/**
 * Execute a compile-only output format handler.
 *
 * Looks up the handler by formatId in the registry, builds an
 * {@link OutputFormatContext} from the timeline snapshot and asset map,
 * calls the handler, and wraps the result in a deterministic
 * {@link RenderArtifact}.
 *
 * This function never calls render providers, render planner execution,
 * or media render routes.  It only executes `requiresRender: false` handlers
 * that were admitted to the registry.
 *
 * @param registry - The compile-only output format registry.
 * @param options - Execution options (formatId, timeline, assets, etc.).
 * @returns The execution result, or `null` if the format is not in the registry
 *          or is render-dependent.
 */
export async function executeCompileOnlyOutput(
  registry: CompileOnlyOutputFormatRegistry,
  options: CompileOnlyOutputExecutionOptions,
): Promise<CompileOnlyOutputExecutionResult | null> {
  const entry = registry.get(options.formatId);
  if (!entry) return null;

  // Safety: render-dependent formats are excluded at registry creation time.
  if (entry.contribution.requiresRender) return null;

  const context: OutputFormatContext = Object.freeze({
    timeline: options.timeline,
    assets: options.assets,
    extensionId: options.extensionId,
    contributionId: options.formatId,
  });

  let result: CompileOnlyOutputResult;

  try {
    const handlerResult = entry.handler(context);
    result = handlerResult instanceof Promise ? await handlerResult : handlerResult;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    // Produce an artifact with a blocking diagnostic
    const artifact = createCompileOnlyArtifact({
      artifactId: `compile-only.${options.formatId}`,
      data: new Uint8Array(0),
      mimeType: entry.contribution.outputMimeType ?? 'application/octet-stream',
      filename: `error.${entry.contribution.outputExtension}`,
      outputFormatId: options.formatId,
      producerExtensionId: options.extensionId,
      producerVersion: options.extensionVersion,
      consumedAssetKeys: options.timeline.assetKeys as readonly string[],
      diagnostics: [{
        severity: 'error',
        code: 'compile-only/handler-exception',
        message: `Output format handler threw: ${message}`,
        extensionId: options.extensionId,
        contributionId: options.formatId,
        detail: { exception: message },
      }],
      hasBlockingErrors: true,
    });
    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');
    return Object.freeze({
      artifact,
      data: new Uint8Array(0),
      hasBlockingErrors: true,
    });
  }

  // Collect consumed asset keys from the timeline
  const consumedAssetKeys: readonly string[] = options.timeline.assetKeys as readonly string[];

  const artifact = createCompileOnlyArtifact({
    artifactId: `compile-only.${options.formatId}`,
    data: result.data,
    mimeType: result.mimeType,
    filename: result.filename,
    outputFormatId: options.formatId,
    producerExtensionId: options.extensionId,
    producerVersion: options.extensionVersion,
    consumedAssetKeys,
    diagnostics: result.diagnostics?.map((d) => ({
      severity: d.severity,
      code: d.code,
      message: d.message,
      assetKey: d.assetKey,
      extensionId: d.extensionId,
      contributionId: d.contributionId,
      detail: d.detail,
    })),
    hasBlockingErrors: result.hasBlockingErrors,
  });
  assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');

  return Object.freeze({
    artifact,
    data: result.data,
    hasBlockingErrors: result.hasBlockingErrors,
  });
}

/**
 * Execute a compile-only output format synchronously.
 *
 * Same as {@link executeCompileOnlyOutput} but only supports synchronous
 * handlers.  Handlers that return a Promise will throw.
 *
 * @throws If the handler returns a Promise (use executeCompileOnlyOutput instead).
 */
export function executeCompileOnlyOutputSync(
  registry: CompileOnlyOutputFormatRegistry,
  options: CompileOnlyOutputExecutionOptions,
): CompileOnlyOutputExecutionResult | null {
  const entry = registry.get(options.formatId);
  if (!entry) return null;

  if (entry.contribution.requiresRender) return null;

  const context: OutputFormatContext = Object.freeze({
    timeline: options.timeline,
    assets: options.assets,
    extensionId: options.extensionId,
    contributionId: options.formatId,
  });

  let handlerResult: CompileOnlyOutputResult | Promise<CompileOnlyOutputResult>;
  try {
    handlerResult = entry.handler(context);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    const artifact = createCompileOnlyArtifact({
      artifactId: `compile-only.${options.formatId}`,
      data: new Uint8Array(0),
      mimeType: entry.contribution.outputMimeType ?? 'application/octet-stream',
      filename: `error.${entry.contribution.outputExtension}`,
      outputFormatId: options.formatId,
      producerExtensionId: options.extensionId,
      producerVersion: options.extensionVersion,
      consumedAssetKeys: options.timeline.assetKeys as readonly string[],
      diagnostics: [{
        severity: 'error',
        code: 'compile-only/handler-exception',
        message: `Output format handler threw: ${message}`,
        extensionId: options.extensionId,
        contributionId: options.formatId,
        detail: { exception: message },
      }],
      hasBlockingErrors: true,
    });
    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutputSync');
    return Object.freeze({
      artifact,
      data: new Uint8Array(0),
      hasBlockingErrors: true,
    });
  }

  if (handlerResult instanceof Promise || (handlerResult && typeof (handlerResult as any).then === 'function')) {
    throw new Error(
      `Output format handler for "${options.formatId}" returned a Promise. ` +
      `Use executeCompileOnlyOutput() for async handlers.`,
    );
  }

  const result: CompileOnlyOutputResult = handlerResult as CompileOnlyOutputResult;

  const consumedAssetKeys: readonly string[] = options.timeline.assetKeys as readonly string[];

  const artifact = createCompileOnlyArtifact({
    artifactId: `compile-only.${options.formatId}`,
    data: result.data,
    mimeType: result.mimeType,
    filename: result.filename,
    outputFormatId: options.formatId,
    producerExtensionId: options.extensionId,
    producerVersion: options.extensionVersion,
    consumedAssetKeys,
    diagnostics: result.diagnostics?.map((d) => ({
      severity: d.severity,
      code: d.code,
      message: d.message,
      assetKey: d.assetKey,
      extensionId: d.extensionId,
      contributionId: d.contributionId,
      detail: d.detail,
    })),
    hasBlockingErrors: result.hasBlockingErrors,

codex
Docs appear to describe planner concepts and provider matrices, but implementation still has old diagnostic names (`export/unrenderable-*`) next to planner reasons. I’m narrowing to the docs and canaries that would need to move with a convergence patch.
exec
/bin/zsh -lc 'find docs/extensions docs/video-editor -maxdepth 3 -type f | sort' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
docs/extensions/authoring.md
docs/extensions/compatibility.md
docs/extensions/loading.md
docs/extensions/phase4-readiness.md
docs/extensions/reigh-extension-layer-foundation-plan.md
docs/extensions/reigh-extension-layer-roadmap-v2.md
docs/extensions/reigh-extension-layer-tickets.md
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md
docs/video-editor/extension-author-contract.md
docs/video-editor/extension-platform-contract-recheck.md
docs/video-editor/extension-platform-release-checklist.md
docs/video-editor/extension-platform-supported-deferred.md
docs/video-editor/extensions-debugging.md
docs/video-editor/extensions-migration-local-to-pack.md
docs/video-editor/extensions-quickstart.md
docs/video-editor/extensions-trust-envelope.md
docs/video-editor/frontend-closure-checklist.md
docs/video-editor/frontend-closure-matrix.md
docs/video-editor/live-data-bridge-manual-smoke-checklist.txt
docs/video-editor/provider-compatibility-matrix.md
docs/video-editor/shader-execution-model.md
docs/video-editor/timeline-patch-operations.md

exec
/bin/zsh -lc "rg --files src/tools/video-editor/render src/tools/video-editor/compositions examples | rg '(canary|output|shader|live|effect|transition|clip|render|export)'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/render/renderPipeline.ts
src/tools/video-editor/render/renderRuntime.ts

exec
/bin/zsh -lc "rg -n \"render planner|render-planner|export readiness|readiness|Export guard|export guard|RenderBlocker|blocker|browser-export|worker-export|preview-only|output format|shader materializer|live binding|unknown-effect|unrenderable\" docs/extensions docs/video-editor src/tools/video-editor/render src/tools/video-editor/compositions examples -g '*.md' -g '*.ts' -g '*.tsx' 2>/dev/null" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/render/renderPipeline.ts:141:    case 'preview-only':
src/tools/video-editor/render/renderPipeline.ts:144:        providerId: 'preview-only',
docs/video-editor/frontend-closure-matrix.md:21:- **Disposition** — `supported` (V1-supported with evidence), `deferred` (explicitly deferred with absence-check or blocker evidence), `unsupported` (no V1 plan), `release-blocking` (blocks V1 release).
docs/video-editor/frontend-closure-matrix.md:373:  - **Error:** ■ Missing clip-type IDs produce diagnostics; export guard blocks unsupported clips.
docs/video-editor/frontend-closure-matrix.md:437:  - **Error:** ■ Render errors caught by preview error boundaries; export guard blocks unsupported render paths.
docs/video-editor/frontend-closure-matrix.md:447:- **Host affordance:** Not a visible component — a cross-cutting guard invoked before render dispatch. Surfaces export blockers via structured diagnostics and the diagnostic panel.
docs/video-editor/frontend-closure-matrix.md:451:  - **Error:** ■ Export blockers render as `Diagnostic` entries with `code` starting `'export/'`. Rendered in diagnostic panel and inline banners.
docs/video-editor/frontend-closure-matrix.md:453:- **Accessibility:** Export blocker diagnostics use severity-colored badges in the diagnostic panel. "View diagnostics" action links to filtered diagnostic panel.
docs/video-editor/frontend-closure-matrix.md:470:| **LiveSourcesPanel** | Host-owned panel for live data source management, bake, and export readiness | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-030, D-031; `src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts`, `src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts` | `gap` | `deferred` | CR:M11-006 (D-030), CR:M11-007 (D-031) |
docs/video-editor/extensions-migration-local-to-pack.md:274:When M14 lands, installed packs will follow the same export guard path as source-local extensions. The export guard (`runExportGuard()`) is provider-agnostic and contribution-kind-agnostic — it scans for unknown IDs regardless of how the extension was loaded.
docs/video-editor/extensions-migration-local-to-pack.md:292:### 8.1 Manifest readiness
docs/video-editor/extensions-migration-local-to-pack.md:302:### 8.2 Settings migration readiness
docs/video-editor/extensions-migration-local-to-pack.md:311:### 8.3 Reference continuity readiness
docs/video-editor/extensions-migration-local-to-pack.md:354:### 10.1 Example readiness gate
docs/video-editor/extensions-migration-local-to-pack.md:357:node scripts/quality/check-extension-example-readiness.mjs --audit
docs/video-editor/extensions-migration-local-to-pack.md:362:**Evidence:** [Quickstart §7](./extensions-quickstart.md#7-running-the-pre-doc-example-readiness-gate).
docs/video-editor/extensions-migration-local-to-pack.md:370:Verifies that every deferred classification (D-001–D-010 for M14 packaging) is backed by an absence check or blocker entry (B-001).
docs/video-editor/extensions-migration-local-to-pack.md:396:| [extensions-debugging.md](./extensions-debugging.md) | Debugging activation, disposal, and export guard failures |
docs/video-editor/extensions-migration-local-to-pack.md:411:| 2026-06-20 | Initial migration guide for M15. Covers V1 source-local posture, settings migration infrastructure (T10), manifest format continuity, reference continuity, deferred M14 packaging pieces (D-001–D-010, B-001), unsupported cloud/export/marketplace paths, provider compatibility for migration, pre-M14 preparation checklist, and automated quality checks. All workflows linked to tests, examples, matrix rows, absence checks, and blockers. |
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:581:      determinism: 'preview-only',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:586:          determinism: 'preview-only',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:617:  it('keeps postprocess shaders preview-only during Remotion export rendering', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:632:      'export requires a shader materializer that produces RenderMaterial',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:982:describe('TimelineRenderer — live binding renderer facade (M11 T6)', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1071:  it('renders live diagnostics placeholders for unresolved live binding states', () => {
docs/video-editor/extension-platform-contract-recheck.md:11:This matrix maps every Done Criteria claim from prior milestone briefs to concrete implementation evidence discoverable in the repository. Each row receives a **status** (`pass`, `gap`, `blocked`) and a **disposition** (`supported`, `deferred`, `unsupported`, `release-blocking`). Rows that cannot honestly pass are listed in the blocker section (§ 3).
docs/video-editor/extension-platform-contract-recheck.md:20:- **deferred** — The behavior is explicitly documented as deferred with absence-check or blocker evidence.
docs/video-editor/extension-platform-contract-recheck.md:36:| M0-005 | M1 can focus on runtime/provider work rather than package scaffolding | pass | supported | M1–M14 briefs all reference stable SDK entrypoint; no scaffolding blockers remain | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:44:| M1-003 | Pure-native export routing remains unchanged | pass | supported | `src/tools/video-editor/runtime/renderability.ts` — export guards, capabilitiy planning; `runExportGuard()` paths | `src/tools/video-editor/runtime/renderability.ts` |
docs/video-editor/extension-platform-contract-recheck.md:52:| M1-011 | Tests prove synthetic unknown render IDs trigger structured export diagnostics | pass | supported | `src/tools/video-editor/runtime/renderability.ts` — export guard diagnostics; `runExportGuard()` | `src/tools/video-editor/runtime/renderability.ts` |
docs/video-editor/extension-platform-contract-recheck.md:71:| M2-009 | Extension status drawer shows active extension IDs, contribution inventory, diagnostics, and current blockers without becoming an install/settings manager | gap | supported | Skeletal status drawer concept referenced; M14 owns full manager UI; standalone status drawer tests not identified | `docs/video-editor/frontend-closure-checklist.md` |
docs/video-editor/extension-platform-contract-recheck.md:72:| M2-010 | Code panel example publishes syntax error diagnostic and shows it in diagnostic panel | pass | supported | `src/examples/code-panel-diagnostics-example.ts` — publishes 3 structured diagnostics + export-blocker; `Canary.test.tsx` tests diagnostic banner | `src/examples/code-panel-diagnostics-example.ts` |
docs/video-editor/extension-platform-contract-recheck.md:117:| M5-005 | Missing effect IDs produce clear diagnostics and export blockers | pass | supported | `runExportGuard()` — unknown effect/transition/clip-type IDs → structured diagnostics | `src/tools/video-editor/runtime/renderability.ts` |
docs/video-editor/extension-platform-contract-recheck.md:118:| M5-006 | Renderability metadata available to export guards | pass | supported | `RenderCapability`, `ContributionRenderability`, `RenderBlocker` exported from SDK; consumed by export guards | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:120:| M5-008 | Host-visible canary shows registry record, renderability status, planner-compatible blocker/finding | gap | supported | Registry canary concept exists; explicit canary test/component not identified | `src/tools/video-editor/runtime/` |
docs/video-editor/extension-platform-contract-recheck.md:121:| M5-009 | Minimal planner skeleton aggregates at least one registry blocker into status/diagnostics surfaces | gap | supported | Planner vocabulary (`CapabilityFinding`, `RenderBlocker`) exported; skeleton integration not confirmed | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:134:| M6-005 | Compile-only export appears in export UI/command surface and produces deterministic artifact | pass | supported | `src/examples/metadata-json-output-example.ts` — compile-only output format; `OutputFormatContribution` with `requiresRender: false` | `src/examples/metadata-json-output-example.ts` |
docs/video-editor/extension-platform-contract-recheck.md:135:| M6-006 | Render-dependent output formats declared early appear disabled with planner-compatible diagnostics | pass | supported | `outputFormat` contribution with `requiresRender: true` → disabled/reserved in M6; planner-compatible unavailable message | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:150:| M7-004 | Export guard blocks unsupported worker export with clear reason | pass | supported | `EffectContribution.allowBrowserExport`/`allowWorkerExport`; export guard surfaces limitations | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:154:| M7-008 | Unapply/reset flows and pre-render export-readiness diagnostics for unsupported component effects | gap | supported | Export readiness scan concept; dedicated tests not identified | `src/tools/video-editor/runtime/` |
docs/video-editor/extension-platform-contract-recheck.md:162:| M8-003 | Missing transition IDs produce diagnostics and export blockers | pass | supported | Export guard integration for missing transition IDs; consistent with effect/clip-type handling | `src/tools/video-editor/runtime/renderability.ts` |
docs/video-editor/extension-platform-contract-recheck.md:163:| M8-004 | Registry lifecycle, picker integration, params defaults, repair, bulk edit behavior, renderability, and export blockers tests | gap | supported | `TransitionContribution` types in SDK; dedicated comprehensive tests not identified as standalone | SDK types |
docs/video-editor/extension-platform-contract-recheck.md:172:| M9-003 | Missing IDs, defaults, renderer dispatch, keyframe interpolation, insertion/selection/editing, export blockers tests | pass | supported | `ClipTypeRegistry.test.ts`, `clip-types/registry.test.ts`, `clip-types/runtime.test.ts`, `clip-types/defineClipType.test.ts`, `clip-types/manifest.test.ts` | clip-types test files |
docs/video-editor/extension-platform-contract-recheck.md:186:| M10-004 | Live-channel handle typed and diagnosed as preview-only until M11 implements full streaming/bake | gap | deferred | `GenerationSession` handle shape with placeholder sample channels; live-data bridge in M11 | `src/tools/video-editor/runtime/` |
docs/video-editor/extension-platform-contract-recheck.md:193:| M10-011 | Export-adjacent snapshot canary: missing contribution/export blocker context in explicit request payload | gap | supported | `agent-tools-export/` extension exists; dedicated export-blocker context tests not identified | `agent-tools-export/` |
docs/video-editor/extension-platform-contract-recheck.md:202:| M11-004 | Export blocked before bake, follows normal route after bake with standard asset or resolved `RenderMaterial` | pass | supported | Export guard detects active live sources and surfaces bake/remove actions | `src/tools/video-editor/runtime/` |
docs/video-editor/extension-platform-contract-recheck.md:216:| M12-001 | Render planner reports capabilities and blockers for native, component-effect, extension-transition, extension-clip, live-source, process-dependent, and output-format scenarios | gap | supported | Planner vocabulary (`CapabilityFinding`, `RenderBlocker`, `RenderRoute`) exported; full planner implementation not confirmed | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:217:| M12-002 | Export UI surfaces clear reasons and next actions | gap | supported | Export guard integration exists; UI surfacing completeness not confirmed | `src/tools/video-editor/` |
docs/video-editor/extension-platform-contract-recheck.md:219:| M12-004 | Artifact model compatibility, render-dependent output formats, mock process invocation, health failure, shutdown, sidecar download UI | gap | supported | `RenderArtifact`, `RenderDependentOutputFormatContribution`, `ProcessContribution` in SDK; comprehensive tests not identified | `src/sdk/index.ts` |
docs/video-editor/extension-platform-contract-recheck.md:222:| M12-007 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` contract, contribution requirements, missing-extension blockers, no raw provider reads | gap | supported | `TimelineReader` and `TimelineSnapshot` contracts defined; planner consuming them not confirmed | `src/tools/video-editor/runtime/` |
docs/video-editor/extension-platform-contract-recheck.md:278:The following gaps are significant enough to warrant explicit blocker documentation. They are classified as `release-blocking` only when the absence of evidence makes a supported-deferred-matrix claim impossible to verify.
docs/video-editor/extension-platform-contract-recheck.md:285:| B-002 | M12-001, M12-002, M12-007 | The render planner is named as the canonical export blocker surface, but its full implementation against current `main` is not confirmed. Without it, export guard behavior relies on ad hoc checks rather than the planner. | Confirm planner implementation or document it as deferred with ad hoc guards as acceptable V1 behavior |
docs/video-editor/shader-execution-model.md:8:uniform controls, and explicit export blockers. It does not introduce a render
docs/video-editor/shader-execution-model.md:138:Timeline shader metadata emits shader materializer requirements for export
docs/video-editor/shader-execution-model.md:140:guard block export with this exact blocker text:
docs/video-editor/shader-execution-model.md:142:`Shader "<id>" cannot export because no shader materializer produced RenderMaterial for <scope>.`
docs/video-editor/shader-execution-model.md:188:M13 includes two browser-preview-only canaries:
docs/video-editor/shader-execution-model.md:195:surface, picker/selection contracts, and planner blocker/materializer posture.
docs/video-editor/extension-platform-supported-deferred.md:5:**Scope:** Every V1 extension-platform behavior classified as `supported` or `deferred`, with concrete evidence links to tests, examples, absence checks, blockers, or contract-recheck row IDs.
docs/video-editor/extension-platform-supported-deferred.md:11:This matrix is the canonical reference for what the Reigh extension platform **supports in V1** and what is **explicitly deferred**. Every row links to concrete implementation evidence discoverable in the repository — tests, compiled examples, absence checks, blocker entries, or contract-recheck row IDs. No row relies on aspirational prose.
docs/video-editor/extension-platform-supported-deferred.md:13:This document is the downstream consumer of the [M15 Contract-Recheck Matrix](./extension-platform-contract-recheck.md). The gate semantics are governed by the shared matrix helper (SD1) and the rule that deferred behavior is a valid terminal classification only when backed by absence checks or an explicit release blocker (SD2).
docs/video-editor/extension-platform-supported-deferred.md:20:| **deferred** | The behavior is explicitly documented as out-of-scope for V1, backed by an absence check, a blocker entry, or a contract-recheck row. |
docs/video-editor/extension-platform-supported-deferred.md:109:| S-062 | Missing effect/transition/clip-type IDs produce clear diagnostics and export blockers | **supported** | CR:M5-005; `runExportGuard()` in `src/tools/video-editor/runtime/renderability.ts` |
docs/video-editor/extension-platform-supported-deferred.md:110:| S-063 | Renderability metadata available to export guards | **supported** | CR:M5-006; `RenderCapability`, `ContributionRenderability`, `RenderBlocker` in `src/sdk/index.ts` |
docs/video-editor/extension-platform-supported-deferred.md:123:| S-075 | Render-dependent output formats declared early appear disabled with diagnostics | **supported** | CR:M6-006; `requiresRender: true` → disabled/reserved |
docs/video-editor/extension-platform-supported-deferred.md:133:| S-083 | Export guard blocks unsupported worker export with clear reason | **supported** | CR:M7-004; `allowBrowserExport`/`allowWorkerExport` in SDK |
docs/video-editor/extension-platform-supported-deferred.md:142:| S-091 | Missing transition IDs produce diagnostics and export blockers | **supported** | CR:M8-003; export guard integration |
docs/video-editor/extension-platform-supported-deferred.md:173:| S-123 | Export blocked before bake, follows normal route after bake | **supported** | CR:M11-004; export guard detects active live sources |
docs/video-editor/extension-platform-supported-deferred.md:230:| D-020 | Full render planner implementation with capability/blocker reports | **deferred** | CR:M12-001; BLOCKER:B-002 |
docs/video-editor/extension-platform-supported-deferred.md:262:| D-046 | Export-adjacent snapshot canary: export-blocker context in request payload | **deferred** | CR:M10-011; DEFER:D-003 |
docs/video-editor/extension-platform-supported-deferred.md:263:| D-047 | Live-channel handle typed and diagnosed as preview-only (pre-M11) | **deferred** | CR:M10-004; `GenerationSession` handle shape with placeholder channels |
docs/video-editor/extension-platform-supported-deferred.md:288:| D-071 | Host-visible canary: registry record, renderability status, planner-compatible blocker/finding | **deferred** | CR:M5-008; DEFER:D-005 |
docs/video-editor/extension-platform-supported-deferred.md:289:| D-072 | Minimal planner skeleton aggregating registry blockers into status/diagnostics surfaces | **deferred** | CR:M5-009; DEFER:D-005 |
docs/video-editor/extension-platform-supported-deferred.md:298:| D-082 | Unapply/reset flows and pre-render export-readiness diagnostics tests | **deferred** | CR:M7-008; gap in identified dedicated tests |
docs/video-editor/extension-platform-supported-deferred.md:300:| D-084 | Registry lifecycle, picker integration, params defaults, repair, bulk edit, renderability, export blockers tests | **deferred** | CR:M8-004; gap in identified dedicated tests |
docs/video-editor/extension-platform-supported-deferred.md:342:| D-134 | Extension status drawer: active extension IDs, contribution inventory, diagnostics, current blockers | **deferred** | CR:M2-009; skeletal concept; M14 owns full manager UI |
docs/video-editor/extension-platform-supported-deferred.md:368:| Lifecycle visibility | Console groups + structured diagnostics + export guard | DOC:extensions-trust-envelope.md§7 |
docs/video-editor/extension-platform-supported-deferred.md:420:The following blocker entries (from the contract-recheck matrix § 3.1) track gaps that are significant enough to be documented as release-blocking until resolved or deferred:
docs/video-editor/extension-platform-supported-deferred.md:425:| B-002 | D-020 through D-022 (M12) | Render planner implementation not confirmed; export guard relies on ad hoc checks |
docs/video-editor/extension-platform-supported-deferred.md:438:Each deferred row maps to the contract-recheck row(s) where the gap was identified, plus any relevant blocker (B-*) or deferral (D-*) entry.
docs/extensions/reigh-extension-layer-roadmap-v2.md:31:- Render explainability: `renderRouter.ts` exposes `RenderPlan`, `RenderBlocker`, `RenderMaterial`, `RenderArtifactManifest`, and provider/blocker vocabulary for existing browser/worker routes.
docs/extensions/reigh-extension-layer-roadmap-v2.md:39:- Agent tools, live data providers, asset parser contributions, output format contributions, render material contributions, sidecars/processes, and shader/WebGL are not public contribution families.
docs/extensions/reigh-extension-layer-roadmap-v2.md:52:5. Render/export readiness is explainable: extension content either declares supported render capabilities or blocks export with actionable `RenderBlocker` messages.
docs/extensions/reigh-extension-layer-roadmap-v2.md:93:Goal: remove the main production blocker: extension state, settings, and proposals must survive reload and behave consistently across providers that claim support.
docs/extensions/reigh-extension-layer-roadmap-v2.md:191:- `EffectContribution` and `TransitionContribution` with parameter schemas, provenance, picker/inspector integration, lifecycle cleanup, preview/export capability metadata, and render blockers for preview-only content.
docs/extensions/reigh-extension-layer-roadmap-v2.md:192:- `ClipTypeContribution` subset with insertion, inspection, rendering, serialization, reload, render planner participation, and public fixtures.
docs/extensions/reigh-extension-layer-roadmap-v2.md:195:- `DataSourceContribution`/live channel with ring buffer, status lifecycle, permission helpers, bake-to-asset/material workflow, and export blockers for unbaked sources.
docs/extensions/reigh-extension-layer-roadmap-v2.md:198:- Optional `ShaderEffectRegistry` with GLSL compile diagnostics, WebGL preview surface, uniform SchemaForm binding, deterministic pixel tests, context-loss recovery, and honest export blockers.
docs/extensions/reigh-extension-layer-roadmap-v2.md:213:- Preview-only or unsupported extension content blocks export with actionable `RenderBlocker` entries.
docs/extensions/reigh-extension-layer-roadmap-v2.md:231:Key blockers:
docs/extensions/reigh-extension-layer-roadmap-v2.md:251:| Live data adds browser permissions and nondeterministic export paths | High | Require ring-buffer/bake semantics and export blockers before public support. |
docs/extensions/reigh-extension-layer-roadmap-v2.md:258:This should happen before new feature work. It gives the team a stable baseline for the preview layer and closes the accepted Docker blocker in `docs/extensions/validation/post-epic-validation-report.md`.
docs/extensions/reigh-extension-layer-roadmap-v2.md:266:- Update the validation report with exact commit, date, gate statuses, and any remaining blockers.
src/tools/video-editor/compositions/TimelineRenderer.tsx:813:      {`postprocess shader '${shaderId}' is browser-preview only; export requires a shader materializer that produces RenderMaterial`}
docs/video-editor/extensions-trust-envelope.md:40:| **Diagnostics (structured)** | Extension code can emit structured `ExtensionDiagnostic` records (severity + code + message) via `ctx.services.diagnostics.report()`. The host collects and surfaces these in the `ExtensionRuntime.diagnostics` array. Export guard diagnostics use the same shape but with export-prefixed codes. | Diagnostics are frozen, collected per-extension, and readable via `ctx.services.diagnostics.diagnostics`. Lifecycle errors (activation/teardown throws) are captured as diagnostics automatically. | N/A (already visible) |
docs/video-editor/extensions-trust-envelope.md:43:| **Export guard diagnostics** | **Supported in V1.** `runExportGuard()` scans the timeline before render/export for unknown clip types, effects, and transitions, missing transition IDs, and active live sources. Active extension-declared IDs are recognized. Errors block export; warnings are surfaced but non-blocking. | Diagnostics are emitted into `ExportGuardResult.diagnostics` / `ExportGuardResult.findings` and surfaced via the render log/status. The empty-extension-runtime fast path skips the guard entirely. | M3 (originally); fully wired in M7/M11 |
docs/video-editor/extensions-trust-envelope.md:138:| Lifecycle visibility | Console groups + structured diagnostics + export guard |
docs/video-editor/extension-author-contract.md:6:**Prerequisite gate:** [Example readiness](./extension-platform-supported-deferred.md) (M15 pre-doc gate, passed 2026-06-20).
docs/video-editor/extension-author-contract.md:34:**Author obligation:** Import exclusively from `@reigh/editor-sdk`. Internal imports (`src/tools/video-editor/`, `@/tools/`, etc.) are violations. The pre-doc example readiness gate enforces this mechanically.
docs/video-editor/extension-author-contract.md:223:The platform exports renderability metadata available to export guards:
docs/video-editor/extension-author-contract.md:234:interface RenderBlocker {
docs/video-editor/extension-author-contract.md:239:### 6.2 Export guard integration
docs/video-editor/extension-author-contract.md:251:4. Do not rely on the render planner (deferred, M12) — V1 export uses the ad hoc guard.
docs/video-editor/extension-author-contract.md:319:These behaviours are documented as deferred in the supported/deferred matrix. Authors must not document them as available, and the pre-doc example readiness gate flags examples that demonstrate deferred behaviour as unsupported docs candidates.
docs/video-editor/extension-author-contract.md:351:## 10. Pre-doc example readiness gate
docs/video-editor/extension-author-contract.md:356:node scripts/quality/check-extension-example-readiness.mjs --audit
docs/video-editor/extension-author-contract.md:396:| 2026-06-20 | Initial author contract for M15. Written after pre-doc example readiness gate passed. All referenced examples are docs-safe. Deferred and unsupported classifications match the supported/deferred matrix. Trust envelope obligations included. Renderability, packaging, and compatibility promises codified. |
src/tools/video-editor/compositions/VisualClip.test.tsx:158:      determinism: 'preview-only',
src/tools/video-editor/compositions/VisualClip.test.tsx:163:          determinism: 'preview-only',
src/tools/video-editor/compositions/VisualClip.test.tsx:299:      'export requires a shader materializer that produces RenderMaterial',
src/tools/video-editor/compositions/VisualClip.test.tsx:539:  // -- Missing / unrenderable transitions (no crossfade fallback!) -----------
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:148:- Render vocabulary exists in `src/tools/video-editor/lib/renderRouter.ts`: `RenderCapability`, `CapabilityFinding`, `RenderBlocker`, `RenderMaterial`, `RenderArtifactManifest`, `RenderPlan`.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:188:- No extension effect provenance/renderability badges, public effect contribution loader validation, provider-scoped contribution lifecycle, export guard for contributed effects, or local extension effect example.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:203:- No provider-scoped transition lookup, params/schema support, repair/defaulting, picker integration for contributed transitions, provenance/renderability badges, export guards for missing/unsupported transition IDs, or local transition example.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:254:- Diagnostics include render blocker codes in `src/tools/video-editor/runtime/diagnostics.ts`.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:260:- No extension-aware inspection for component effects, shader effects, transitions, live sources, output formats, or processes.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:274:- No `ShaderEffectRegistry`, shader/WebGL contribution shape, shader compile diagnostics, uniform schema, texture binding, WebGL preview surface, shader picker/inspector integration, shader examples/canaries, pixel tests, shader materialization posture, or shader export blocker integration beyond generic deferral.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:360:- E2E: `tests/e2e/video-editor-diagnostics.spec.ts` covers invalid package, incompatible API, duplicate package, conflicting contribution, duplicate runtime, runtime exception/fallback, provider diagnostics, render blocker, aggregation, direct store inspection, and empty state.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:407:- Render blocker diagnostics documented in `src/tools/video-editor/runtime/diagnostics.ts`.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:408:- Export blocker appears in E2E diagnostics fixture.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:415:- Planner does not inspect extension effects, transitions, live sources, process dependencies, output formats, shader effects, or public render materials.
docs/extensions/validation/reigh-extension-layer-fulfillment-audit.md:469:- `render-sidecars-shader.md` -> `render-sidecars-shader.txt`: confirmed render planner vocabulary exists; sidecars/process/output formats are absent; shader/WebGL is not started.
docs/video-editor/extensions-debugging.md:5:**Audience:** Extension authors diagnosing activation failures, disposal errors, export guard warnings, and provider-specific behaviour.
docs/video-editor/extensions-debugging.md:12:This document is a practical debugging reference for Reigh extension authors. Every workflow or limitation is linked to concrete repository evidence — tests, examples, matrix rows, absence checks, or blocker entries. No advice relies on aspirational prose.
docs/video-editor/extensions-debugging.md:77:**Example reference:** [code-panel-diagnostics-example.ts](../../src/examples/code-panel-diagnostics-example.ts) (docs-safe, EX) — publishes 3 structured diagnostics with source ranges and an export-blocker diagnostic.
docs/video-editor/extensions-debugging.md:96:| **Export guard result** | `export/`-prefixed diagnostics from pre-render scan | Understand why export is blocked |
docs/video-editor/extensions-debugging.md:125:- Importing from an internal path (`src/tools/video-editor/`) instead of `@reigh/editor-sdk`. Run `node scripts/quality/check-extension-example-readiness.mjs --audit` to verify.
docs/video-editor/extensions-debugging.md:150:## 5. Export guard diagnostics
docs/video-editor/extensions-debugging.md:159:| Unknown effect (no declaring extension) | `error` | `export/unknown-effect` | Yes |
docs/video-editor/extensions-debugging.md:168:When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does **not** block render. Unknown clip types from missing extensions produce `export/unknown-clip-type` separately.
docs/video-editor/extensions-debugging.md:174:1. Check the export guard diagnostics in the DiagnosticPanel.
docs/video-editor/extensions-debugging.md:280:node scripts/quality/check-extension-example-readiness.mjs --audit
docs/video-editor/extensions-debugging.md:285:**Evidence:** [Quickstart §7](./extensions-quickstart.md#7-running-the-pre-doc-example-readiness-gate); [Contract-Recheck CR:X-001, CR:X-002](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims).
docs/video-editor/extensions-debugging.md:303:Verifies that every deferred classification is backed by an absence check or blocker entry (SD2). If you're debugging a deferred feature, this confirms the deferral is documented.
docs/video-editor/extensions-debugging.md:348:| 2026-06-20 | Initial debugging guide for M15. Covers console visibility, diagnostic system, activation/disposal failures, export guard, provider-specific limitations, TimelinePatch debugging, common failure modes, automated quality checks, and deferred/unsupported escalation paths. All workflows linked to tests, examples, matrix rows, and blockers. |
src/tools/video-editor/compositions/VisualClip.tsx:183:      {`shader '${shaderId}' is browser-preview only — export requires a shader materializer that produces RenderMaterial`}
src/tools/video-editor/compositions/VisualClip.tsx:455:  // for missing or unrenderable IDs.
docs/video-editor/provider-compatibility-matrix.md:41:| **InMemory** | Full — requirements are inlined in TimelineConfig and surfaced via `TimelineReader.snapshot().extensionRequirements` | `warning` (export guard) | Contribution IDs stored in `referencedContributionIds` are validated structurally but not resolved at runtime |
docs/video-editor/provider-compatibility-matrix.md:45:Extension requirements are a property of the timeline config, not the provider. The `TimelineReader` extracts `extensionRequirements` from the config shape and returns them in every snapshot. When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does not block render.
docs/video-editor/provider-compatibility-matrix.md:290:| **deferred** | The shared suite section was skipped via a documented flag (`skipCheckpoints`, `skipMissingTimelineTests`, `versionConflictIsSoft`) and the skip reason is linked to a contract-recheck row or blocker entry | Astrid: checkpoints deferred (no persistence), missing-timeline deferred (single-timeline bridge) |
docs/video-editor/provider-compatibility-matrix.md:293:| **release-blocking** | A gap without documented resolution that affects V1 supported claims | None — see [contract-recheck blocker section](./extension-platform-contract-recheck.md#3-blocker-section) for M14/M12/M11 blockers that are independent of provider compatibility |
docs/video-editor/provider-compatibility-matrix.md:295:**Cross-validation rule:** Every `skip*` flag or `versionConflictIsSoft` usage in a provider compatibility test file must have a corresponding row in this section (§10) linking to contract-recheck rows. The deferred-claims checker (SD2) enforces this: a deferred classification is valid only when backed by an absence check or explicit blocker entry. This section serves as the absence-check evidence for environment-impossible provider skips.
docs/video-editor/extension-platform-release-checklist.md:51:| 9 | Contract | Every deferred/unsupported row has evidence or a release blocker | `docs/video-editor/extension-platform-contract-recheck.md`; `docs/video-editor/extension-platform-supported-deferred.md` | yes |
docs/video-editor/extension-platform-release-checklist.md:58:| 11 | Deferred | Every deferred row has absence-check evidence or a blocker link | `docs/video-editor/extension-platform-supported-deferred.md`; `scripts/quality/check-extension-deferred-claims.mjs` | yes |
docs/video-editor/extension-platform-release-checklist.md:67:| 15 | Diagnostics | Export guard diagnostics for missing/unsupported extensions | `src/tools/video-editor/runtime/renderability.ts`; `docs/video-editor/provider-compatibility-matrix.md` § 3.2 | yes |
docs/video-editor/extension-platform-release-checklist.md:84:| 22 | Docs | Pre-doc example readiness gate passes (all EX:/EXT: refs resolve) | `scripts/quality/check-extension-example-readiness.mjs`; `src/examples/` | yes |
docs/video-editor/extension-platform-release-checklist.md:88:| 26 | Docs | Migration guide (local → pack) honesty: no aspirational prose, every deferred item linked to a blocker or matrix row | `docs/video-editor/extensions-migration-local-to-pack.md`; `docs/video-editor/extension-platform-supported-deferred.md` | yes |
docs/video-editor/extension-platform-release-checklist.md:149:- `npm run check:extension-example-readiness:release` exits 0
docs/video-editor/extensions-quickstart.md:6:**Prerequisite gate:** [Example readiness](./extension-platform-supported-deferred.md) (M15 pre-doc gate, passed 2026-06-20).
docs/video-editor/extensions-quickstart.md:284:Diagnostics surfaces include: the diagnostic panel (code panel), status surface, and export guard results. The host provides `DiagnosticPanel` with diagnostic fallback links filtered to the failing extension.
docs/video-editor/extensions-quickstart.md:369:## 7. Running the pre-doc example readiness gate
docs/video-editor/extensions-quickstart.md:374:node scripts/quality/check-extension-example-readiness.mjs --audit
docs/video-editor/extensions-quickstart.md:389:The following examples passed the M15 pre-doc readiness gate and are safe to reference:
docs/video-editor/extensions-quickstart.md:403:| `metadata-json-output-example.ts` | Compile-only output format contribution |
docs/video-editor/extensions-quickstart.md:471:| 2026-06-20 | Initial quickstart for M15. Written after pre-doc example readiness gate passed (22 docs-safe examples, 0 failures). All referenced examples are docs-safe. Missing workflows classified as deferred or unsupported per the supported/deferred matrix. |
docs/extensions/phase4-readiness.md:4:Scope: readiness review before public contribution-family promotion.
docs/extensions/phase4-readiness.md:22:  surfaces reserved descriptors for output formats, processes, shaders, and
docs/extensions/phase4-readiness.md:24:  requirements, process requirements, blockers, next actions, sidecars, and
docs/extensions/phase4-readiness.md:32:  readiness reducer. It consumes timeline snapshot requirements, explicit
docs/extensions/phase4-readiness.md:33:  requirements, output format descriptors, process descriptors, shader
docs/extensions/phase4-readiness.md:35:  diagnostics, then returns route plans, blockers, diagnostics, next actions,
docs/extensions/phase4-readiness.md:52:3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
docs/extensions/phase4-readiness.md:54:   produce actionable `RenderBlocker` records rather than silent fallback.
docs/extensions/phase4-readiness.md:58:   supported browser-export capability, and blocks worker conflicts for
docs/extensions/phase4-readiness.md:63:   requirements, process requirements, blockers, next actions, sidecars, and
docs/extensions/phase4-readiness.md:66:   Current `renderPlanner.ts` shader materializer handling discovers
docs/extensions/phase4-readiness.md:67:   materializer routes, emits process-dependent blockers/next actions, and
docs/extensions/phase4-readiness.md:70:   Extension Manager and diagnostics surfaces can show package/family blockers
docs/extensions/phase4-readiness.md:110:| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
docs/extensions/phase4-readiness.md:112:| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
docs/extensions/phase4-readiness.md:115:Family-specific readiness:
docs/extensions/phase4-readiness.md:117:| Family | Minimum readiness before support |
docs/extensions/phase4-readiness.md:120:| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
docs/extensions/phase4-readiness.md:121:| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
docs/extensions/phase4-readiness.md:125:| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
docs/extensions/phase4-readiness.md:126:| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
docs/extensions/phase4-readiness.md:128:| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |
docs/extensions/phase4-readiness.md:141:| EXT-031 EffectContribution | Planned as trusted/signed packages. | Preserve trusted/signed wording, add manager trust warning coverage, and require planner blockers for preview-only effects. |
docs/extensions/phase4-readiness.md:143:| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
docs/extensions/phase4-readiness.md:147:| EXT-037 Live data | Planned. | Block until bake/export semantics are accepted; unbaked live bindings must block export. |
docs/extensions/phase4-readiness.md:150:| EXT-040 Shader/WebGL bridge | Planned. | Keep behind render materialization posture and deterministic preview/export blocker tests. |
docs/extensions/phase4-readiness.md:151:| EXT-041 Final docs/examples/validation | Planned. | Must include this readiness checklist as a closure matrix input, plus compatibility drift checks across schema, SDK, runtime, docs, examples, and tests. |
docs/extensions/phase4-readiness.md:160:2. Begin EXT-035-style render planner integration as a prerequisite slice for
docs/extensions/phase4-readiness.md:163:Until one of those paths is accepted, the readiness decision is: Phase 4 is
docs/extensions/reigh-extension-layer-foundation-plan.md:8:This plan turns the current extension-author preview into a durable foundation for deeper contribution families. It intentionally stops before public effects, transitions, clip types, keyframes, agent tools, live data, sidecars, and shaders. Those families should only be promoted after the host can persist extension state, inspect installed packages, edit settings, report diagnostics, clean up lifecycle state, and explain render/export readiness.
docs/extensions/reigh-extension-layer-foundation-plan.md:46:  - `make release-check` in Docker-capable CI, or a clear non-production blocker
docs/extensions/reigh-extension-layer-foundation-plan.md:77:Goal: remove the biggest production blocker: extension enablement, settings, and command proposals must survive reload and behave consistently across providers.
docs/extensions/reigh-extension-layer-foundation-plan.md:210:- Do not claim production readiness without provider-backed persistence and Docker-capable release validation.
docs/extensions/reigh-extension-layer-foundation-plan.md:217:- Do not start Phase 4 family implementation until a Phase 4 readiness gate is passed.
docs/extensions/reigh-extension-layer-foundation-plan.md:243:23. Phase 4 readiness gate: render planner extension contract, trust/sandbox decision, family promotion checklist, and roadmap/ticket reconciliation.
docs/extensions/reigh-extension-layer-foundation-plan.md:293:- Add a Phase 4 readiness gate before deeper contribution families: render planner extension contract, trust/sandbox decision, and a formal family promotion checklist.
docs/extensions/reigh-extension-layer-foundation-plan.md:300:- Do not start public Phase 4 creative families merely because Phases 1-3 pass; require the readiness gate.
docs/extensions/reigh-extension-layer-foundation-plan.md:325:- Do not pull Phase 4 families into the foundation. The foundation should define readiness gates, not implement asset/effects/transition/clip/agent/live-data contribution families.
docs/extensions/reigh-extension-layer-foundation-plan.md:332:Phases 1-3 are done when a developer can load an extension package, see it in a manager, enable/disable it, edit settings, inspect diagnostics, execute command-backed proposals, reload without losing extension state or pending proposals, see honest trust/permission warnings, and trust the docs/schema/runtime matrix to reject everything not yet supported. Before Phase 4 starts, the Phase 4 readiness gate must also define render planner extension participation, trust/sandbox posture, and the per-family promotion checklist.
docs/extensions/reigh-extension-layer-tickets.md:18:- Validation artifacts record commit, date, git status, command output, and blocker table.
docs/extensions/reigh-extension-layer-tickets.md:357:- Invalid params, render exceptions, duplicates, disabled packages, and preview-only export routes produce diagnostics/blockers.
docs/extensions/reigh-extension-layer-tickets.md:358:- Tests cover apply, preview, serialize, reload, and export readiness.
docs/extensions/reigh-extension-layer-tickets.md:377:- Missing or disabled transition IDs repair to placeholders/blockers rather than silent fallback.
docs/extensions/reigh-extension-layer-tickets.md:378:- Tests cover select, configure, persist, render, repair, and preview-only export blocker.
docs/extensions/reigh-extension-layer-tickets.md:433:- Preview-only or unsupported extension content yields actionable `RenderBlocker` entries.
docs/extensions/reigh-extension-layer-tickets.md:435:- Export/readiness UI surfaces blockers with remedy text.
docs/extensions/reigh-extension-layer-tickets.md:442:- tests/e2e render blocker specs
docs/extensions/reigh-extension-layer-tickets.md:482:- render planner/export UI
docs/extensions/reigh-extension-layer-tickets.md:492:- Planner consumes declarations and emits artifact manifests/blockers.
docs/extensions/reigh-extension-layer-tickets.md:518:- render planner integration

exec
/bin/zsh -lc "rg -n \"runExportGuard|startRender\\(|startExport\\(|Render blocked|Export blocked|Worker render unavailable|Export unavailable|not available|hasBlockingErrors|planFromExportGuardResult|exportDiagnosticToPlannerFinding|getFastRenderRouteDecision|decideRenderRoute\" src/tools/video-editor -g '*.test.ts' -g '*.test.tsx' -g '*.ts' -g '*.tsx'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:649:          `Shader texture "${binding.name}" requires a ${binding.sourceKind} source that is not available.`,
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:507:    it('throws when IndexedDB is not available', async () => {
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts:517:        'IndexedDB is not available',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:84:        message: 'Effect rendering is not available in worker export by default.',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:91:        message: 'Effect rendering is not available in sidecar export by default.',
src/tools/video-editor/data/syncLedgerIndexedDb.ts:45:    throw new Error('IndexedDB is not available in this environment');
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2284:          hasBlockingErrors: false,
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2333:      expect(exportResult!.hasBlockingErrors).toBe(false);
src/tools/video-editor/lib/timeline-data.test.ts:10:import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';
src/tools/video-editor/lib/timeline-data.test.ts:254:    expect(decideRenderRoute(serialized)).toMatchObject({
src/tools/video-editor/render/renderPipeline.ts:145:        message: `Render blocked: ${decision.reason}. Preview-only clips require a valid non-browser render provider.`,
src/tools/video-editor/contexts/VideoEditorProvider.tsx:395:                    message: `Process invocation is not available until M12.`,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:97:    hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:173:    expect(exec.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:213:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:249:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:338:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:420:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:465:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:491:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:582:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:732:    expect(result1!.hasBlockingErrors).toBe(result2!.hasBlockingErrors);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:770:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:808:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:843:      { data: new Uint8Array([0]), mimeType: 'application/octet-stream', filename: 'a.bin', hasBlockingErrors: true },
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:844:      { data: new TextEncoder().encode('hello'), mimeType: 'text/plain', filename: 'a.txt', hasBlockingErrors: false },
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1007:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1017:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1072:        handler: makeSyncHandler({ data: encoder.encode('co1'), mimeType: 'text/plain', filename: 'co1.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1077:        handler: makeSyncHandler({ data: encoder.encode('rd1'), mimeType: 'text/plain', filename: 'rd1.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1082:        handler: makeSyncHandler({ data: encoder.encode('co2'), mimeType: 'text/plain', filename: 'co2.txt', hasBlockingErrors: false }),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1295:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1336:          hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1357:    expect(result!.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1482:        hasBlockingErrors: false,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1497:    expect(result!.hasBlockingErrors).toBe(false);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:381:                    message: `Process invocation is not available until M12.`,
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:597:            Export blocked
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:88:    throw new Error('IndexedDB is not available in this environment');
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:130:    expect(screen.getByText('Export blocked')).toBeTruthy();
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:347:    expect(screen.getByText('Export blocked')).toBeTruthy();
src/tools/video-editor/lib/renderRouter.test.ts:8:  decideRenderRoute,
src/tools/video-editor/lib/renderRouter.test.ts:13:describe('Sprint 8 render-button router (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:15:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:29:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:42:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:52:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:65:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:78:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:87:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:95:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:110:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:125:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:144:    const missingArtifact = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:155:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:162:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:172:      expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:185:    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:186:    expect(decideRenderRoute(null).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:187:    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:229:describe('M9 T11 contributed clip routing (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:231:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:242:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:258:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:268:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:278:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:288:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:304:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:328:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:343:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:354:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:364:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:374:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:385:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:400:    const decision = decideRenderRoute({ clips: [] }, [browserCapableRecord]);
src/tools/video-editor/lib/renderRouter.test.ts:407:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:646:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:685:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:741:      decision: decideRenderRoute(request.resolvedConfig),
src/tools/video-editor/lib/renderRouter.test.ts:774:      decision: decideRenderRoute({ clips: [{ clipType: 'media' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:802:      decision: decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:869:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:900:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
src/tools/video-editor/runtime/renderPlanner.ts:85:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/renderPlanner.ts:711:      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
src/tools/video-editor/runtime/renderPlanner.ts:914:    hasBlockingErrors: blockers.length > 0,
src/tools/video-editor/runtime/exportGuard.test.ts:291:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:301:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:318:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:403:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:440:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:463:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:485:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:537:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:562:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:644:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:716:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:792:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:830:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:893:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:944:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:967:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:998:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1029:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1039:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1049:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1065:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1080:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1095:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1121:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1147:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1169:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1203:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1271:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1329:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1365:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1378:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1483:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1556:    expect(result.hasBlockingErrors).toBe(true);
src/tools/video-editor/runtime/exportGuard.test.ts:1572:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/exportGuard.test.ts:1585:    expect(result.hasBlockingErrors).toBe(false);
src/tools/video-editor/runtime/livePermissions.test.ts:593:    expect(result.error).toBe('API not available');
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.ts:47:    throw new Error('IndexedDB is not available in this environment');
src/tools/video-editor/runtime/renderability.ts:489:  readonly hasBlockingErrors?: boolean;
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:90:          message: 'Process invocation is not available in the generated-frame canary test.',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:348:    expect(within(section).getByText(/not available/)).toBeInTheDocument();
src/tools/video-editor/runtime/extensionLifecycle.test.ts:979:  it('uses console.group during activation when groupCollapsed is not available', () => {
src/tools/video-editor/runtime/exportGuard.ts:107:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/exportGuard.ts:298:  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');
src/tools/video-editor/runtime/exportGuard.ts:308:    hasBlockingErrors,
src/tools/video-editor/runtime/livePermissions.ts:285:        permission: makePermission('unavailable', `Browser API not available: ${apiNames[apiKind]}`),
src/tools/video-editor/runtime/livePermissions.ts:289:          `The ${apiNames[apiKind]} API is not available in this browser or environment.`,
src/tools/video-editor/runtime/livePermissions.ts:339:        error: 'API not available',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:211:          message: 'Process invocation is not available in integration tests.',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:444:    expect(blocked.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:460:    expect(cleared.hasBlockingErrors).toBe(false);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:542:    expect(liveGuard.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:565:    expect(partialGuard.hasBlockingErrors).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:594:    expect(fullGuard.hasBlockingErrors).toBe(false);
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:329:    expect(exportScan.hasBlockingErrors).toBe(true);
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:628:                    <span>Transition "{sharedTransitionType}" is not available. The extension may have been removed.</span>
src/tools/video-editor/runtime/outputFormatRegistry.ts:63: * because they require the render pipeline, which is not available here.
src/tools/video-editor/runtime/outputFormatRegistry.ts:107:  readonly hasBlockingErrors: boolean;
src/tools/video-editor/runtime/outputFormatRegistry.ts:173:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:179:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:204:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:211:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:261:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:267:      hasBlockingErrors: true,
src/tools/video-editor/runtime/outputFormatRegistry.ts:300:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/outputFormatRegistry.ts:307:    hasBlockingErrors: result.hasBlockingErrors,
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts:35:export const PROCESS_INVOCATION_PENDING_MESSAGE = 'Process invocation is not available until M12.';
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts:50:    message: `Process invocation for tool "${toolId}" is not available until M12.`,
src/tools/video-editor/components/Canary/CodePanelCanary.tsx:160:        Canary — not available for production authoring (M4)
src/tools/video-editor/components/Canary/StagePanelCanary.tsx:76:  disabled: 'Disabled — stage not available',
src/tools/video-editor/components/Canary/StagePanelCanary.tsx:254:        Canary — not available for production authoring (M3)
src/tools/video-editor/components/Canary/Canary.test.tsx:217:    expect(screen.getByText(/Disabled — stage not available/)).toBeDefined();
src/tools/video-editor/components/Canary/WritingPanelCanary.tsx:212:        Canary — not available for production authoring (M4)
src/tools/video-editor/hooks/useRenderState.ts:44:function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
src/tools/video-editor/hooks/useRenderState.ts:202:function exportDiagnosticToPlannerFinding(diagnostic: ExportDiagnostic, index: number): CapabilityFinding {
src/tools/video-editor/hooks/useRenderState.ts:226:function planFromExportGuardResult(
src/tools/video-editor/hooks/useRenderState.ts:232:    ...guardResult.diagnostics.map(exportDiagnosticToPlannerFinding),
src/tools/video-editor/hooks/useRenderState.ts:354:  const runExportGuard = useCallback((): boolean => {
src/tools/video-editor/hooks/useRenderState.ts:377:    const plannerResult = planFromExportGuardResult(guardResult);
src/tools/video-editor/hooks/useRenderState.ts:402:    if (!runExportGuard()) {
src/tools/video-editor/hooks/useRenderState.ts:406:    let decision = getFastRenderRouteDecision(resolvedConfig);
src/tools/video-editor/hooks/useRenderState.ts:414:        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
src/tools/video-editor/hooks/useRenderState.ts:430:      setRenderLog(`Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`);
src/tools/video-editor/hooks/useRenderState.ts:438:      setRenderLog(`Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`);
src/tools/video-editor/hooks/useRenderState.ts:501:  }, [exporter, renderMetadata?.durationInFrames, resolvedConfig, startClientRender, runExportGuard]);
src/tools/video-editor/hooks/useRenderState.ts:510:      setExportLogState('Export unavailable: no timeline configuration.');
src/tools/video-editor/hooks/useRenderState.ts:544:        setExportLogState(`Export blocked: ${blocker.message}`);
src/tools/video-editor/hooks/useRenderState.ts:546:        setExportLogState(`Export blocked: "${requestedFormat.label}" is not available for browser export.`);
src/tools/video-editor/hooks/useRenderState.ts:559:    const guardPassed = runExportGuard();
src/tools/video-editor/hooks/useRenderState.ts:565:        `Export blocked by readiness scan. See render log for details.`,
src/tools/video-editor/hooks/useRenderState.ts:572:      setExportLogState(`Export unavailable: no compile-only output handlers registered. Format "${fmt.label}" (${fmt.id}) requires a handler registered via ctx.export.registerOutputFormat().`);
src/tools/video-editor/hooks/useRenderState.ts:613:        setExportLogState(`Export failed: format "${fmt.label}" is not available in the compile-only registry.`);
src/tools/video-editor/hooks/useRenderState.ts:629:        (result.hasBlockingErrors ? ' (with blocking errors)' : '') +
src/tools/video-editor/hooks/useRenderState.ts:637:  }, [resolvedConfig, extensionRuntime, runExportGuard]);
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:616:                {clip.clipType} is trusted in the clip-type registry, but its render component is not available in this editor build.
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1257:                    <span>Shader "{clipShader.shaderId}" is not available. The extension may have been removed.</span>
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1384:                    <span>Transition "{clip.transition.type}" is not available. The extension may have been removed.</span>
src/tools/video-editor/lib/renderRouter.ts:80: *                          Currently unreachable from `decideRenderRoute`.
src/tools/video-editor/lib/renderRouter.ts:303:export function decideRenderRoute(
src/tools/video-editor/components/TimelineEditorShellCore.tsx:948:          onClick={() => void chrome.startRender()}
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.test.tsx:573:        message: 'Process execution is not available until M12.',
src/tools/video-editor/hooks/useRenderState.test.tsx:31:  decideRenderRoute: (timeline: ResolvedTimelineConfig | null | undefined) => {
src/tools/video-editor/hooks/useRenderState.test.tsx:208:    hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:244:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:264:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:300:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:317:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:358:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:384:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:389:    expect(result.current.renderLog).toContain('Render blocked');
src/tools/video-editor/hooks/useRenderState.test.tsx:410:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:415:    expect(result.current.renderLog).toContain('Worker render unavailable');
src/tools/video-editor/hooks/useRenderState.test.tsx:446:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:473:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:520:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:545:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:575:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:611:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:650:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:667:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:712:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:729:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:779:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:796:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:853:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:870:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:903:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:920:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:965:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:982:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1016:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1033:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1066:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1086:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1091:      expect(result.current.renderLog).toContain('Render blocked');
src/tools/video-editor/hooks/useRenderState.test.tsx:1130:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1147:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1175:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1204:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1228:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1272:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1318:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1347:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1354:      expect(result.current.renderLog).toContain('Render blocked');
src/tools/video-editor/hooks/useRenderState.test.tsx:1391:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1418:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1468:        hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:1485:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1537:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1554:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1622:        hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1639:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1670:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1695:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1722:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1733:        await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:1788:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1862:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1884:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:1902:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:1924:      await result.current.startExport('fmt-csv', new Map([['fmt-csv', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:1953:      await result.current.startExport('fmt-json', new Map()); // empty Map = no handlers registered
src/tools/video-editor/hooks/useRenderState.test.tsx:1981:      await result.current.startExport('fmt-json', new Map());
src/tools/video-editor/hooks/useRenderState.test.tsx:2011:      await result.current.startExport('fmt-mp4', new Map());
src/tools/video-editor/hooks/useRenderState.test.tsx:2015:    expect(result.current.exportLog).toContain('not available on browser-export');
src/tools/video-editor/hooks/useRenderState.test.tsx:2040:      await result.current.startExport('fmt-future', new Map());
src/tools/video-editor/hooks/useRenderState.test.tsx:2068:      await result.current.startExport('non-existent-format', new Map());
src/tools/video-editor/hooks/useRenderState.test.tsx:2100:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2104:    expect(result.current.exportLog).toContain('not available in the compile-only registry');
src/tools/video-editor/hooks/useRenderState.test.tsx:2129:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2142:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2164:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2196:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2217:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2239:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2246:  it('includes blocking errors note in export log when hasBlockingErrors is true', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:2256:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2278:      await result.current.startExport('fmt-json', new Map([['fmt-json', {}]]));
src/tools/video-editor/hooks/useRenderState.test.tsx:2316:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2360:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2403:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2414:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2476:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2517:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2534:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2568:      hasBlockingErrors: false,
src/tools/video-editor/hooks/useRenderState.test.tsx:2585:      await result.current.startRender();
src/tools/video-editor/hooks/useRenderState.test.tsx:2640:      hasBlockingErrors: true,
src/tools/video-editor/hooks/useRenderState.test.tsx:2657:      await result.current.startRender();

exec
/bin/zsh -lc "sed -n '1,220p' src/tools/video-editor/render/renderPipeline.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import type { TimelineRenderRequest } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import {
  RENDER_PROVIDER_REGISTRY,
  buildRenderTimelinePayload,
  enqueueBanodocoRenderTimeline,
  type RenderProviderId,
  type RenderRouteDecision,
} from '@/tools/video-editor/lib/renderRouter.ts';

export type RenderPipelineEvent =
  | {
      type: 'beforeRender';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
    }
  | {
      type: 'assetMaterialized';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      assetCount: number;
    }
  | {
      type: 'afterRender';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      providerId: RenderProviderId;
      message: string;
    }
  | {
      type: 'renderFailed';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      providerId: RenderProviderId;
      error: string;
    };

export type RenderPipelineMiddleware = (event: RenderPipelineEvent) => void | Promise<void>;

export interface BrowserRenderResult {
  status: 'done' | 'error';
  message: string;
}

export interface ExecuteRenderPipelineOptions {
  decision: RenderRouteDecision;
  request: TimelineRenderRequest;
  startBrowserRender: () => Promise<BrowserRenderResult>;
  middlewares?: readonly RenderPipelineMiddleware[];
}

export interface ExecuteRenderPipelineResult {
  status: 'done' | 'queued' | 'error';
  providerId: RenderProviderId;
  message: string;
  taskId?: string;
  correlationId?: string;
}

async function emitRenderPipelineEvent(
  middlewares: readonly RenderPipelineMiddleware[],
  event: RenderPipelineEvent,
): Promise<void> {
  for (const middleware of middlewares) {
    await middleware(event);
  }
}

async function executeProviderRoute({
  decision,
  request,
  startBrowserRender,
}: Pick<ExecuteRenderPipelineOptions, 'decision' | 'request' | 'startBrowserRender'>): Promise<ExecuteRenderPipelineResult> {
  switch (decision.route) {
    case 'browser-remotion': {
      const result = await startBrowserRender();
      return {
        status: result.status,
        providerId: 'browser-remotion',
        message: result.message,
      };
    }
    case 'worker-banodoco': {
      let workerJwt: string | null = null;
      try {
        workerJwt = await request.renderRuntime.getWorkerJwt();
      } catch (error) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: `Worker render dispatch failed for route "${decision.reason}": ${error instanceof Error ? error.message : String(error)}`,
        };
      }

      if (!workerJwt) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: `Worker render dispatch failed for route "${decision.reason}": missing worker session token.`,
        };
      }

      const { payload, error } = buildRenderTimelinePayload({
        request,
        userJwt: workerJwt,
      });

      if (!payload) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: error ?? `Worker render dispatch failed for route "${decision.reason}".`,
        };
      }

      const enqueueResult = await enqueueBanodocoRenderTimeline(payload, {
        orchestratorBaseUrl: request.renderRuntime.orchestratorBaseUrl,
      });

      if (enqueueResult.status === 'error') {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: enqueueResult.message,
        };
      }

      return {
        status: 'queued',
        providerId: 'worker-banodoco',
        taskId: enqueueResult.task_id,
        correlationId: enqueueResult.correlation_id,
        message: enqueueResult.message,
      };
    }
    case 'external':
      return {
        status: 'error',
        providerId: 'external',
        message: `No external render provider is registered for route "${decision.reason}".`,
      };
    case 'preview-only':
      return {
        status: 'error',
        providerId: 'preview-only',
        message: `Render blocked: ${decision.reason}. Preview-only clips require a valid non-browser render provider.`,
      };
    default: {
      const unreachableRoute: never = decision.route;
      throw new Error(`Unknown render route: ${String(unreachableRoute)}`);
    }
  }
}

export async function executeRenderPipeline({
  decision,
  request,
  startBrowserRender,
  middlewares = [],
}: ExecuteRenderPipelineOptions): Promise<ExecuteRenderPipelineResult> {
  const provider = RENDER_PROVIDER_REGISTRY[decision.route];
  const baseEvent = {
    decision,
    request,
  } as const;

  await emitRenderPipelineEvent(middlewares, {
    type: 'beforeRender',
    ...baseEvent,
  });
  await emitRenderPipelineEvent(middlewares, {
    type: 'assetMaterialized',
    ...baseEvent,
    assetCount: Object.keys(request.assetRegistry?.assets ?? {}).length,
  });

  const result = await executeProviderRoute({
    decision: { ...decision, provider },
    request,
    startBrowserRender,
  });

  if (result.status === 'done' || result.status === 'queued') {
    await emitRenderPipelineEvent(middlewares, {
      type: 'afterRender',
      ...baseEvent,
      providerId: result.providerId,
      message: result.message,
    });
  } else {
    await emitRenderPipelineEvent(middlewares, {
      type: 'renderFailed',
      ...baseEvent,
      providerId: result.providerId,
      error: result.message,
    });
  }

  return result;
}

exec
/bin/zsh -lc "sed -n '1,460p' src/tools/video-editor/lib/renderRouter.test.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
// Sprint 8: render-button router tests.
// Mirrors the sprint brief's three cases (pure media, themed, mixed) +
// the orchestrator dispatch shape.

import { describe, expect, it, vi } from 'vitest';
import {
  buildRenderTimelinePayload,
  decideRenderRoute,
  enqueueBanodocoRenderTimeline,
} from '@/tools/video-editor/lib/renderRouter';
import { executeRenderPipeline } from '@/tools/video-editor/render/renderPipeline';

describe('Sprint 8 render-button router (decideRenderRoute)', () => {
  it('routes a pure-media timeline to the client renderer', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'text' },
        { clipType: 'effect-layer' },
      ],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('routes a themed-only timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'image-jump' }],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
    expect(decision.planner.selectedPlannerRoute).toBe('worker-export');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(true);
  });

  it('routes locally-registered title-card timelines to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'title-card' }],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
  });

  it('routes a mixed themed+media timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'image-jump' },
      ],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_themed_and_media');
  });

  it('routes mixed local-sequence and media timelines to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'title-card' },
      ],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_themed_and_media');
  });

  it('treats legacy clips with undefined clipType as native media', () => {
    const decision = decideRenderRoute({
      clips: [{}, { clipType: undefined }],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
  });

  it('treats unknown clipTypes as media (loud-placeholder fallback path)', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'theme-package-not-yet-installed' }],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
  });

  it('routes valid remotion_module clips by lane metadata before clipType fallback', () => {
    const decision = decideRenderRoute({
      clips: [{
        clipType: 'generated-clip-type-not-installed',
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('generated_remotion_module');
  });

  it('routes registered theme clipTypes as generated modules when the module lane is present', () => {
    const decision = decideRenderRoute({
      clips: [{
        clipType: 'art-card',
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('generated_remotion_module');
  });

  it('routes mixed valid remotion_module timelines to the worker route with a generated reason', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        {
          clipType: 'image-jump',
          generation: {
            sequence_lane: 'remotion_module',
            artifact_id: 'artifact-1',
          },
        },
      ],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('mixed_generated_module_and_other');
    expect(decision.hasMediaClip).toBe(true);
  });

  it('blocks remotion_module clips with missing, empty, or non-string artifact ids', () => {
    const missingArtifact = decideRenderRoute({
      clips: [{ clipType: 'media', generation: { sequence_lane: 'remotion_module' } }],
    });
    expect(missingArtifact).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_missing_artifact',
    });
    expect(missingArtifact.planner.selectedPlannerRoute).toBe('preview');
    expect(missingArtifact.planner.plannerResult.canBrowserExport).toBe(false);
    expect(missingArtifact.planner.plannerResult.canWorkerExport).toBe(false);

    expect(decideRenderRoute({
      clips: [{ clipType: 'image-jump', generation: { sequence_lane: 'remotion_module', artifact_id: '' } }],
    })).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_invalid_artifact',
    });

    expect(decideRenderRoute({
      clips: [{ clipType: 'unknown', generation: { sequence_lane: 'remotion_module', artifact_id: 42 } }],
    })).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_invalid_artifact',
    });
  });

  it('does not treat non-module generation lanes as generated Remotion modules', () => {
    for (const sequence_lane of ['trusted_v1', 'schema_sequence', 'unknown_lane', null, undefined]) {
      expect(decideRenderRoute({
        clips: [{
          clipType: 'media',
          generation: { sequence_lane, artifact_id: 'artifact-1' },
        }],
      })).toMatchObject({
        route: 'browser-remotion',
        reason: 'pure_native_clips',
      });
    }
  });

  it('returns no_clips for an empty timeline', () => {
    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
    expect(decideRenderRoute(null).reason).toBe('no_clips');
    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
  });
});

// ---------------------------------------------------------------------------
// M9 T11: Contributed clip routing via dynamic capability records
// ---------------------------------------------------------------------------

function makeContributedRecord(
  clipTypeId: string,
  capabilities: Array<{ route: string; status: string }>,
) {
  return {
    clipTypeId,
    renderability: {
      capabilities: capabilities.map((c) => ({
        route: c.route,
        status: c.status,
        determinism: 'deterministic' as const,
      })),
      determinism: 'deterministic' as const,
    },
  };
}

const browserCapableRecord = makeContributedRecord('ext-glow', [
  { route: 'browser-export', status: 'supported' },
  { route: 'preview', status: 'supported' },
]);

const previewOnlyRecord = makeContributedRecord('ext-preview-only', [
  { route: 'preview', status: 'supported' },
  { route: 'browser-export', status: 'blocked' },
]);

const workerOnlyRecord = makeContributedRecord('ext-worker-only', [
  { route: 'worker-export', status: 'supported' },
  { route: 'preview', status: 'supported' },
]);

const noCapabilitiesRecord = makeContributedRecord('ext-no-caps', []);

describe('M9 T11 contributed clip routing (decideRenderRoute)', () => {
  it('routes a browser-capable contributed clip to browser-remotion', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-glow' }] },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.reason).toBe('browser_capable_contributed');
  });

  it('routes mixed browser-capable contributed + native clips to browser-remotion', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'media' },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_browser_capable_contributed_and_native');
  });

  it('blocks a contributed clip without browser-export capability (preview-only route)', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-preview-only' }] },
      [previewOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
  });

  it('blocks a contributed clip with only worker-export capability (worker routes blocked for contributed code)', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-worker-only' }] },
      [workerOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
  });

  it('blocks a contributed clip with no capabilities at all', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-no-caps' }] },
      [noCapabilitiesRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
  });

  it('blocks mixed contributed (browser-capable) + themed clips due to worker route conflict', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'image-jump' },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
  });

  it('blocks contributed clip mixed with generated remotion module due to worker route conflict', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          {
            clipType: 'image-jump',
            generation: {
              sequence_lane: 'remotion_module',
              artifact_id: 'artifact-1',
            },
          },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
  });

  it('multiple browser-capable contributed clips all route to browser-remotion', () => {
    const record2 = makeContributedRecord('ext-glow-2', [
      { route: 'browser-export', status: 'supported' },
    ]);
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'ext-glow-2' },
        ],
      },
      [browserCapableRecord, record2],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('browser_capable_contributed');
  });

  it('existing themed routing is unchanged when contributed records are empty', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'image-jump' }] },
      [],
    );
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
  });

  it('existing native routing is unchanged when contributed records are empty', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      [],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('existing native routing is unchanged when contributed records are undefined', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      undefined,
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('a contributed record for an unrelated clipType does not affect themed routing', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'title-card' }] },
      [browserCapableRecord], // ext-glow record, not title-card
    );
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.reason).toBe('themed_only');
  });

  it('blocks the first contributed clip without browser capability even when mixed with native clips', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'media' },
          { clipType: 'ext-preview-only' },
        ],
      },
      [previewOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
  });

  it('no_clips decision reports hasContributedClip false', () => {
    const decision = decideRenderRoute({ clips: [] }, [browserCapableRecord]);
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('no_clips');
  });

  it('blocked remotion_module short-circuits before contributed record lookup', () => {
    const decision = decideRenderRoute(
      {
        clips: [{
          clipType: 'ext-glow',
          generation: { sequence_lane: 'remotion_module' },
        }],
      },
      [browserCapableRecord], // ext-glow is browser-capable but the module is blocked
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.reason).toBe('remotion_module_missing_artifact');
  });
});

describe('Sprint 8 buildRenderTimelinePayload', () => {
  const baseInput = {
    request: {
      timelineId: '11111111-1111-1111-1111-111111111111',
      assetRegistry: { assets: { a: { url: 'https://cdn/a.mp4' } } },
      resolvedConfig: {
        theme: '2rp',
        clips: [{ clipType: 'art-card' }],
      },
      renderMetadata: null,
      renderRuntime: {
        projectId: '22222222-2222-2222-2222-222222222222',
        orchestratorBaseUrl: 'https://orchestrator.example.com',
        getSupabaseSession: vi.fn(async () => null),
        getWorkerJwt: vi.fn(async () => null),
      },
    },
    userJwt: 'user.jwt.token',
    correlationId: '33333333-3333-3333-3333-333333333333',
  };

  it('produces the SD-034-shaped payload from valid input', () => {
    const { payload, error } = buildRenderTimelinePayload(baseInput);
    expect(error).toBeUndefined();
    expect(payload).toBeDefined();
    expect(payload!.timeline_id).toBe(baseInput.request.timelineId);
    expect(payload!.project_id).toBe(baseInput.request.renderRuntime.projectId);
    expect(payload!.user_jwt).toBe(baseInput.userJwt);
    expect(payload!.correlation_id).toBe(baseInput.correlationId);
    expect(payload!.theme_id).toBe('2rp');
    expect(payload!.output_filename).toContain(baseInput.request.timelineId);
  });

  it('keeps explicit caller-owned request inputs for local fixture renders', () => {
    const request = {
      ...baseInput.request,
      timelineId: 'fixture-local-timeline',
      assetRegistry: {
        assets: {
          'fixture-video': {

exec
/bin/zsh -lc "sed -n '1,220p' src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import type { FC } from 'react';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type {
  EffectRegistryProvenance,
  EffectRegistryRecord,
  EffectRegistryRecordStatus,
} from '@/tools/video-editor/effects/registry/types.ts';
import type {
  EffectResource,
  VideoEditorEffectCatalog,
} from '@/tools/video-editor/lib/effect-catalog.ts';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

export type EffectComponentMap = Readonly<Record<string, FC<EffectComponentProps>>>;
export type EffectSchemaMap = Readonly<Record<string, ParameterSchema | undefined>>;
export type EffectCodeCompiler = (code: string, effectId: string) => FC<EffectComponentProps>;

export interface EffectAdapterOptions {
  readonly ownerExtensionId?: string;
  readonly renderability?: ContributionRenderability;
  readonly status?: EffectRegistryRecordStatus;
  readonly schemaByEffectId?: EffectSchemaMap;
}

export interface BuiltInEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export interface LocalDraftEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export interface LegacyDbEffectRow {
  readonly id?: string;
  readonly slug: string;
  readonly code: string;
  readonly parameterSchema?: ParameterSchema;
}

export interface LegacyDbEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export type EffectResourceWithGenerationMetadata = EffectResource & {
  readonly generation_id?: string | null;
  readonly generationId?: string | null;
  readonly generatedAt?: string;
  readonly generated_at?: string;
  readonly provenance?: string;
};

export interface EffectResourceAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
  readonly provenance?: EffectRegistryProvenance;
}

export type EffectCatalogAdapterOptions = EffectResourceAdapterOptions;

export function normalizeEffectRegistryId(effectId: string): string {
  return effectId.startsWith('custom:') ? effectId.slice('custom:'.length) : effectId;
}

export function createDefaultEffectRenderability(): ContributionRenderability {
  return {
    defaultRoute: 'preview',
    determinism: 'deterministic',
    capabilities: [
      {
        route: 'preview',
        status: 'supported',
        determinism: 'deterministic',
      },
      {
        route: 'browser-export',
        status: 'supported',
        determinism: 'deterministic',
      },
      {
        route: 'worker-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
        message: 'Effect rendering is not available in worker export by default.',
      },
      {
        route: 'sidecar-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
        message: 'Effect rendering is not available in sidecar export by default.',
      },
    ],
  };
}

function schemaFor(
  schemaByEffectId: EffectSchemaMap | undefined,
  rawEffectId: string,
  effectId: string,
): ParameterSchema | undefined {
  return schemaByEffectId?.[rawEffectId] ?? schemaByEffectId?.[effectId];
}

function createEffectRecord({
  effectId,
  contributionId,
  component,
  provenance,
  code,
  schema,
  options,
}: {
  effectId: string;
  contributionId: string;
  component: FC<EffectComponentProps>;
  provenance: EffectRegistryProvenance;
  code?: string;
  schema?: ParameterSchema;
  options: EffectAdapterOptions;
}): EffectRegistryRecord {
  return {
    effectId,
    contributionId,
    component,
    ...(schema !== undefined ? { schema } : {}),
    ...(code !== undefined ? { code } : {}),
    provenance,
    ...(options.ownerExtensionId ? { ownerExtensionId: options.ownerExtensionId } : {}),
    renderability: options.renderability ?? createDefaultEffectRenderability(),
    status: options.status ?? 'active',
  };
}

export function builtInEffectsToRegistryRecords(
  effects: EffectComponentMap,
  options: BuiltInEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'built-in:effect';

  return Object.entries(effects).map(([rawEffectId, component]) => {
    const effectId = normalizeEffectRegistryId(rawEffectId);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component,
      provenance: 'built-in',
      schema: schemaFor(options.schemaByEffectId, rawEffectId, effectId),
      options,
    });
  });
}

export function localDraftEffectsToRegistryRecords(
  drafts: Readonly<Record<string, string>>,
  compile: EffectCodeCompiler,
  options: LocalDraftEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'local-draft:effect';

  return Object.entries(drafts).map(([rawEffectId, code]) => {
    const effectId = normalizeEffectRegistryId(rawEffectId);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component: compile(code, effectId),
      provenance: 'local-storage-draft',
      code,
      schema: schemaFor(options.schemaByEffectId, rawEffectId, effectId),
      options,
    });
  });
}

function provenanceForEffectResource(
  resource: EffectResourceWithGenerationMetadata,
  fallback: EffectRegistryProvenance,
): EffectRegistryProvenance {
  if (
    resource.provenance === 'ai-generated'
    || resource.generation_id
    || resource.generationId
    || resource.generatedAt
    || resource.generated_at
  ) {
    return 'ai-generated';
  }

  return fallback;
}

export function legacyDbEffectsToRegistryRecords(
  effects: readonly LegacyDbEffectRow[] | undefined,
  compile: EffectCodeCompiler,
  options: LegacyDbEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'legacy-db:effect';

  return (effects ?? []).map((effect) => {
    const effectId = normalizeEffectRegistryId(effect.slug);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component: compile(effect.code, effectId),
      provenance: 'legacy-db-effect',
      code: effect.code,
      schema: effect.parameterSchema ?? schemaFor(options.schemaByEffectId, effect.slug, effectId),
      options,
    });
  });
}

export function effectResourcesToRegistryRecords(
  resources: readonly EffectResourceWithGenerationMetadata[] | undefined,
  compile: EffectCodeCompiler,
  options: EffectResourceAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'db-resource:effect';
  const fallbackProvenance = options.provenance ?? 'db-resource';


exec
/bin/zsh -lc "sed -n '1,260p' src/tools/video-editor/transitions/catalog.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/**
 * Transition catalog: host-owned built-in transition registry records,
 * resolver, and list helpers that prevent silent extension override of
 * built-in transitions.
 *
 * Built-in transitions are exposed as registry-compatible
 * {@link TransitionRegistryRecord} entries with provenance `'built-in'`
 * and deterministic renderability metadata. The resolver always prefers
 * built-in records over extension-contributed records with the same ID.
 *
 * The existing `transitions` record and `transitionTypes` array in
 * `effects/transitions.ts` remain compatible for unmigrated callers.
 */

import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  TransitionRegistryRecord,
  TransitionRegistrySnapshot,
} from '@/tools/video-editor/transitions/registry/types.ts';
import { transitions as builtInRenderers } from '@/tools/video-editor/effects/transitions.ts';
import type { TransitionRenderer } from '@/tools/video-editor/effects/transitions.ts';
import type { ClipTransition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { ParameterDefinition } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Built-in transition records
// ---------------------------------------------------------------------------

const BUILT_IN_CONTRIBUTION_ID_PREFIX = 'host.built-in.transition.';

function makeBuiltInRecord(
  transitionId: string,
  renderer: TransitionRenderer,
): TransitionRegistryRecord {
  return Object.freeze({
    transitionId,
    contributionId: `${BUILT_IN_CONTRIBUTION_ID_PREFIX}${transitionId}`,
    // Cast the built-in renderer to the SDK-compatible TransitionRenderer
    // union. Built-in renderers are (progress: number) => CSSProperties,
    // which at runtime are called with a single number argument.  The SDK
    // type is intentionally broad (Record<string,unknown> | function) so
    // safe coercion through `unknown` is acceptable here.
    renderer: renderer as unknown as TransitionRegistryRecord['renderer'],
    provenance: 'built-in' as const,
    renderability: Object.freeze({
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: Object.freeze([
        Object.freeze({
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        }),
        Object.freeze({
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        }),
        Object.freeze({
          route: 'worker-export',
          status: 'blocked',
          determinism: 'deterministic',
          blockerReason: 'route-unsupported',
        }),
      ]),
    }),
    status: 'active' as const,
  });
}

/** Frozen array of all built-in transition registry records. */
export const BUILT_IN_TRANSITION_RECORDS: readonly TransitionRegistryRecord[] =
  Object.freeze(
    Object.entries(builtInRenderers).map(([id, renderer]) =>
      makeBuiltInRecord(id, renderer),
    ),
  );

// ---------------------------------------------------------------------------
// Built-in ID set for fast O(1) lookup
// ---------------------------------------------------------------------------

const BUILT_IN_IDS: ReadonlySet<string> = new Set(
  BUILT_IN_TRANSITION_RECORDS.map((r) => r.transitionId),
);

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

/** Check whether a transition ID belongs to a host-owned built-in transition. */
export function isBuiltInTransition(transitionId: string): boolean {
  return BUILT_IN_IDS.has(transitionId);
}

/** Get a frozen set of all built-in transition IDs. */
export function getBuiltInTransitionIds(): ReadonlySet<string> {
  return BUILT_IN_IDS;
}

/** Get the frozen array of all built-in transition registry records. */
export function getBuiltInTransitionRecords(): readonly TransitionRegistryRecord[] {
  return BUILT_IN_TRANSITION_RECORDS;
}

/**
 * Resolve a transition by ID against built-in records and an optional
 * provider-scoped registry snapshot.
 *
 * Resolution order:
 * 1. Built-in records (host-owned, provenance `'built-in'`)
 * 2. Registry snapshot records (extension-contributed)
 *
 * Built-in transitions are never silently overridden by registry records
 * with the same ID. When a registry record clashes with a built-in, the
 * built-in is returned and a diagnostic is emitted into the optional
 * `diagnostics` array so the consumer can surface the conflict.
 *
 * @param transitionId - The transition ID to resolve.
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @param diagnostics - Optional mutable array for conflict diagnostics.
 * @returns The resolved record, or `undefined` if the ID is unknown.
 */
export function resolveTransition(
  transitionId: string,
  registrySnapshot?: TransitionRegistrySnapshot,
  diagnostics?: ExtensionDiagnostic[],
): TransitionRegistryRecord | undefined {
  // Built-ins always take priority
  const builtIn = BUILT_IN_TRANSITION_RECORDS.find(
    (r) => r.transitionId === transitionId,
  );
  if (builtIn) {
    // If the registry also has a record for this built-in ID, surface a
    // diagnostic so the override is not silent.
    if (registrySnapshot?.has(transitionId) && diagnostics) {
      const registryRecord = registrySnapshot.get(transitionId);
      if (registryRecord) {
        diagnostics.push({
          severity: 'warning',
          code: 'transition-catalog/built-in-override-blocked',
          message:
            `Extension transition "${transitionId}" ` +
            `(contribution: ${registryRecord.contributionId}) conflicts ` +
            `with a built-in transition. The built-in will be used.`,
          extensionId: registryRecord.ownerExtensionId,
          contributionId: registryRecord.contributionId,
          detail: { transitionId },
        });
      }
    }
    return builtIn;
  }

  // Fall back to registry snapshot
  return registrySnapshot?.get(transitionId);
}

/**
 * List all available transitions by merging built-in records with an
 * optional registry snapshot. Built-in records take precedence when IDs
 * conflict, so extension contributions can never silently displace a
 * built-in transition in the list.
 *
 * The returned array is NOT frozen — callers that need immutability should
 * freeze it themselves.
 *
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @returns Array of unique transition records (built-ins + contributed).
 */
export function listTransitions(
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionRegistryRecord[] {
  const merged = new Map<string, TransitionRegistryRecord>();

  // Registry records go in first (lower priority)
  for (const record of registrySnapshot?.records ?? []) {
    merged.set(record.transitionId, record);
  }

  // Built-in records overwrite any conflicting registry records
  for (const record of BUILT_IN_TRANSITION_RECORDS) {
    merged.set(record.transitionId, record);
  }

  return [...merged.values()];
}

/**
 * Create a complete registry-compatible snapshot that merges built-in
 * transitions with an optional provider-scoped registry snapshot.
 *
 * Built-in records take precedence over registry records with the same ID.
 * The returned snapshot is frozen and safe for use in React render
 * comparisons.
 *
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @returns Frozen snapshot with built-ins merged in.
 */
export function createTransitionSnapshot(
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionRegistrySnapshot {
  const allRecords = listTransitions(registrySnapshot);
  const recordMap = new Map(allRecords.map((r) => [r.transitionId, r]));

  return Object.freeze({
    records: Object.freeze(allRecords),
    diagnostics: Object.freeze([...(registrySnapshot?.diagnostics ?? [])]),
    get: (transitionId: string) => recordMap.get(transitionId),
    has: (transitionId: string) => recordMap.has(transitionId),
  });
}

// ---------------------------------------------------------------------------
// Transition parameter schema defaults
// ---------------------------------------------------------------------------

type ParameterValue = number | string | boolean | Record<string, unknown>;

const AUDIO_SOURCES: ReadonlyArray<string> = ['bass', 'mid', 'treble', 'amplitude'];

/**
 * Compute the fallback value for a single parameter definition.
 *
 * Mirrors the logic in `ParameterControls.getFallbackValue` so transition
 * defaults are consistent with effect defaults without importing the UI module.
 */
function getFallbackValue(parameter: ParameterDefinition): ParameterValue {
  if (parameter.default !== undefined) {
    return parameter.default as ParameterValue;
  }

  switch (parameter.type) {
    case 'number':
      return parameter.min ?? 0;
    case 'select':
      return parameter.options?.[0]?.value ?? '';
    case 'boolean':
      return false;
    case 'audio-binding':
      return { source: 'amplitude', min: 0, max: 1 };
    case 'color':
      return '#000000';
    default:
      return '';
  }
}

/**
 * Materialize default parameter values from a {@link ParameterSchema}.
 *
 * Returns a frozen record of parameter-name → default-value. If no schema is
 * provided, returns an empty frozen record.
 *
 * The returned record is a new object every call — callers that need reference
 * stability should memoize.
 */
export function materializeTransitionDefaults(
  schema: ParameterSchema | readonly ParameterDefinition[] | undefined,
): Readonly<Record<string, unknown>> {

exec
/bin/zsh -lc "sed -n '1,320p' src/tools/video-editor/runtime/processCommandRegistration.ts" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
import type { CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ProcessRoundtripRequest, ProcessStatus } from '@reigh/editor-sdk';

export interface ProcessCommandServices {
  invokeProcess: (request: ProcessRoundtripRequest) => Promise<unknown>;
}

export interface RegisterProcessCommandsOptions {
  commandRegistry: CommandRegistry;
  processes: readonly VideoEditorProcessDescriptor[];
  processStatuses?: readonly ProcessStatus[];
  services: ProcessCommandServices;
}

function processCommandId(processId: string, operationId: string): string {
  return `host.process.${processId}.${operationId}`;
}

function validateParams(schema: { required?: readonly string[] } | undefined, params: Record<string, unknown> | undefined): void {
  for (const key of schema?.required ?? []) {
    if (!params || !(key in params)) throw new Error(`Missing required process parameter "${key}".`);
  }
}

function statusBlocks(status: ProcessStatus | undefined): string | null {
  if (!status) return 'Process status is unavailable.';
  if (status.state === 'ready' || status.state === 'busy' || status.state === 'degraded') return null;
  return `Process is ${status.state}.`;
}

export function registerProcessOperationCommands({
  commandRegistry,
  processes,
  processStatuses = [],
  services,
}: RegisterProcessCommandsOptions) {
  const statuses = new Map(processStatuses.map((status) => [status.processId, status]));
  const handles = [];
  for (const process of processes) {
    for (const operation of process.operations) {
      const commandId = processCommandId(process.processId, operation.id);
      const status = statuses.get(process.processId);
      const unavailable = statusBlocks(status);
      commandRegistry.ingestCommandContribution('host.processes', {
        id: commandId as never,
        kind: 'command',
        command: commandId,
        label: operation.label,
        category: unavailable ? `Processes (${unavailable})` : 'Processes',
      });
      handles.push(commandRegistry.registerCommand('host.processes', commandId, async () => {
        const currentUnavailable = statusBlocks(statuses.get(process.processId));
        if (currentUnavailable) throw new Error(currentUnavailable);
        validateParams(operation.inputSchema as { required?: readonly string[] } | undefined, undefined);
        await services.invokeProcess({
          id: `${process.processId}:${operation.id}`,
          processId: process.processId,
          operationId: operation.id,
        });
      }, { label: operation.label, category: unavailable ? `Processes (${unavailable})` : 'Processes' }));
    }
  }
  return { dispose: () => handles.forEach((handle) => handle.dispose()) };
}

exec
/bin/zsh -lc "sed -n '1,260p' docs/extensions/phase4-readiness.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
# Phase 4 Extension Readiness Gate

Date: 2026-06-23
Scope: readiness review before public contribution-family promotion.

This artifact is the Phase 4 gate requested by the extension manager milestone.
It reconciles current runtime behavior, render/export planning, trust posture,
and the roadmap/ticket backlog without editing the roadmap or ticket source
documents.

## Current Code Anchors

- The roadmap and ticket backlog still name
  `src/tools/video-editor/runtime/contributionFamilies.ts` as the contribution
  family matrix. That file is not present in this checkout. The current
  runtime family sources are `src/sdk/index.ts`, which defines
  `ContributionKind`, `KNOWN_CONTRIBUTION_KINDS`,
  `CONTRIBUTION_KIND_MILESTONE`, and `contributionKindNotYetBridged()`, and
  `src/tools/video-editor/runtime/extensionSurface.ts`, which normalizes active
  or reserved contributions into provider/runtime descriptors.
- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
  surfaces reserved descriptors for output formats, processes, shaders, and
  agent tools. Output formats are turned into planner metadata with route
  requirements, process requirements, blockers, next actions, sidecars, and
  capability metadata. Process descriptors are surfaced as planner-visible
  declarations without starting a runtime process.
- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
  adapter for user render clicks. It converts native, themed, generated
  Remotion module, and contributed clip content into `CapabilityRequirement`
  entries, calls `planRender()`, and returns a planner-backed route decision.
- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
  readiness reducer. It consumes timeline snapshot requirements, explicit
  requirements, output format descriptors, process descriptors, shader
  descriptors, material refs/statuses, render groups, request constraints, and
  diagnostics, then returns route plans, blockers, diagnostics, next actions,
  and `canBrowserExport`/`canWorkerExport`.

## Render Planner Participation Contract

Any Phase 4 family that can affect preview, export, generated artifacts, or
determinism must participate in planning through stable capability metadata
before it can be promoted to public support.

Required contract:

1. Each promoted family must expose provider-free planner inspection data. The
   planner must not import live registries, component implementations, provider
   stores, or extension package handles.
2. Each render-relevant contribution must declare one or more route-level
   `CapabilityRequirement` records or a descriptor that `planRender()` can
   convert into equivalent requirements.
3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
   process-dependent, missing-contribution, and route-unsupported states must
   produce actionable `RenderBlocker` records rather than silent fallback.
4. Route decisions must remain planner-backed. For clip routing,
   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
   allows browser export only when the contribution explicitly declares a
   supported browser-export capability, and blocks worker conflicts for
   contributed code.
5. Output-format and process families must keep using planner descriptors
   rather than invoking providers directly from the planner. Current
   `extensionSurface.ts` output-format descriptors are the model: route
   requirements, process requirements, blockers, next actions, sidecars, and
   capability metadata are data, not execution.
6. Shader and render-material families must distinguish preview from export.
   Current `renderPlanner.ts` shader materializer handling discovers
   materializer routes, emits process-dependent blockers/next actions, and
   keeps unresolved material refs from silently exporting.
7. Diagnostics published from planner findings must remain source-scoped so
   Extension Manager and diagnostics surfaces can show package/family blockers
   without confusing them with extension-authored runtime diagnostics.

Promotion is blocked for any family whose content can render, mutate timeline
state, invoke processes, consume live data, or produce export artifacts without
planner-visible requirements and failure states.

## Trust And Sandbox Posture

Phase 4 must continue the current explicit trust posture:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime
  enforcement, sandbox isolation, code signing, or a permission broker.
- The Extension Manager warning introduced in Phase 3 is therefore a product
  requirement, not just documentation. It must stay visible during loading,
  empty, populated, selected-package, and error states.
- Public promotion of arbitrary code families such as effects, transitions,
  clip types, agent tools, local processes, shaders, and sidecars is blocked
  until the accepted posture is either "trusted/signed local packages only" or
  a real sandbox/permission broker exists.
- If Phase 4 proceeds under trusted-local assumptions, every affected doc,
  manager surface, example, and compatibility table must avoid implying iframe
  isolation, runtime permission enforcement, marketplace review, or safe
  third-party execution.

## Per-Family Promotion Checklist

Apply this checklist to each family before changing compatibility status to
supported.

| Gate | Requirement |
| --- | --- |
| Manifest/schema | `config/contracts/reigh-extension.schema.json` accepts exactly the supported shape and rejects unknown or deferred fields. |
| Public SDK | `src/sdk/index.ts` exports stable types and public helpers only; examples do not import internals. |
| Runtime normalization | `extensionSurface.ts` or the owning runtime module converts manifest declarations into immutable provider-scoped descriptors with extension ID, contribution ID, order, disabled state, and diagnostics. |
| Lifecycle cleanup | Disable/unload unregisters renderers, commands, keybindings, diagnostics, settings-derived UI state, live channels, process handles, or shader resources owned by the extension. |
| Persistence posture | Any persisted state has provider-backed semantics or an explicit unsupported diagnostic. Settings/proposals must survive reload only where providers claim conformance. |
| Settings/parameters | Parameter schemas render through SchemaForm or an equivalent host-owned primitive, with unsupported shapes diagnosed and non-corrupting. |
| Diagnostics | Loader, runtime, planner, and extension-authored diagnostics are scoped by extension ID and contribution ID where applicable, bounded, and cleaned up. |
| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
| UI integration | Picker, inspector, manager, diagnostics, empty/loading/error/disabled states, and provenance labels are present where the family is visible. |
| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
| Docs/examples | Authoring, loading, compatibility, examples, and release gates agree on support status and trust posture. |

Family-specific readiness:

| Family | Minimum readiness before support |
| --- | --- |
| Asset parser | Permission/declaration checks, parser failure diagnostics, safe asset metadata enrichment, query/filter API boundaries, and export/bake posture. |
| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
| Keyframes | Minimal model, commands/proposals, migration, interpolation tests, and deterministic preview/export delivery. |
| Agent tool | Proposal-first destructive behavior, backend dispatch registry, permission declarations, result-family validation, persisted proposals, and disabled/failure diagnostics. |
| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
| Process/sidecar | Trusted local process model, command/env/cwd policy, JSON-RPC protocol, health/log/cancel/shutdown behavior, manager health UI, and explicit trust warnings. |
| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |

## Roadmap And Ticket Reconciliation

This table records what must be reconciled after review. It intentionally does
not edit `docs/extensions/reigh-extension-layer-roadmap-v2.md` or
`docs/extensions/reigh-extension-layer-tickets.md`.

| Source item | Current status | Reconciliation needed before Phase 4 |
| --- | --- | --- |
| Roadmap Phase 1 acceptance cites `runtime/contributionFamilies.ts` | Stale path in this checkout; contribution kind data currently lives in `src/sdk/index.ts`, and runtime descriptor normalization lives in `extensionSurface.ts`. | Update roadmap/ticket references after review, or restore a generated/owned contribution-family matrix file if that remains the intended gate. |
| Roadmap Phase 4 "Contribution Families And Render Hardening" | Correctly identifies asset parsers, effects, transitions, clip types, keyframes, agent tools, live data, render materials, sidecars/processes, and shaders as the next higher-power families. | Keep this sequencing, but require the checklist above and planner participation before any family moves to supported. |
| EXT-030 AssetParserContribution | Planned. | Add explicit render/export/bake posture and diagnostics requirements to the ticket if asset parser output can affect timeline materialization. |
| EXT-031 EffectContribution | Planned as trusted/signed packages. | Preserve trusted/signed wording, add manager trust warning coverage, and require planner blockers for preview-only effects. |
| EXT-032 TransitionContribution | Planned. | Add route capability metadata and fallback/repair behavior to prevent silent export differences. |
| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
| EXT-034 Keyframes | Planned. | Treat as timeline data/model work first, not an extension family shortcut; require proposal/migration/render interpolation gates. |
| EXT-035 Render planner integration | Planned. | Promote this from a later hardening ticket to a prerequisite for every render-relevant family. |
| EXT-036 AgentToolContribution | Planned. | Block until proposal persistence and backend dispatch registry are stable; no direct destructive mutation by default. |
| EXT-037 Live data | Planned. | Block until bake/export semantics are accepted; unbaked live bindings must block export. |
| EXT-038 RenderMaterialContribution | Planned. | Tie directly to planner material refs/statuses, artifact manifests, and next actions. |
| EXT-039 Process/sidecar runtime | Planned as trusted local runtime. | Require separate trust approval, process policy, health UI, cancellation, and shutdown tests before public exposure. |
| EXT-040 Shader/WebGL bridge | Planned. | Keep behind render materialization posture and deterministic preview/export blocker tests. |
| EXT-041 Final docs/examples/validation | Planned. | Must include this readiness checklist as a closure matrix input, plus compatibility drift checks across schema, SDK, runtime, docs, examples, and tests. |

## Phase 4 Entry Decision

Phase 4 should not start as broad parallel family implementation. The next
accepted action should be either:

1. Fix the stale `contributionFamilies.ts` reference by restoring or replacing
   the family matrix gate, then update roadmap/ticket docs after review; or
2. Begin EXT-035-style render planner integration as a prerequisite slice for
   the first selected family, with this document as the acceptance checklist.

Until one of those paths is accepted, the readiness decision is: Phase 4 is
prepared but not cleared for public family promotion.

exec
/bin/zsh -lc "sed -n '130,210p' docs/video-editor/shader-execution-model.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:

Ordered shader stacks, multipass composition, temporal feedback, previous-frame
inputs, transition shaders, and render-graph scheduling are deferred.

## Export And Materialization

Browser preview is not export support.

Timeline shader metadata emits shader materializer requirements for export
routes. If no materializer has produced `RenderMaterial`, the planner and export
guard block export with this exact blocker text:

`Shader "<id>" cannot export because no shader materializer produced RenderMaterial for <scope>.`

The concrete `<scope>` text is produced by the host:

- Clip shader example: `clip "clip-1"`.
- Postprocess shader example: `timeline postprocess`.

A shader contribution may declare materializer metadata so the planner can
discover a process route. Discovery changes the planner posture to a
materialization next action/progress state, but it still does not mean export is
ready. Export becomes available only after a supported renderer route or
materializer produces the required `RenderMaterial`.

## Non-Render-Graph V1 Posture

The V1 bridge is a narrow preview execution path:

- One fullscreen WebGL program per assigned scope.
- Host-owned canvas/context creation, resize, draw, `readPixels`-friendly
  deterministic rendering, and disposal.
- Context-loss handling that pauses preview, preserves shader source/uniform
  state, recompiles on restore, and resumes rendering.

It is not a render graph. There is no pass scheduler, no graph edge model, no
ordered dependency chain, no multipass FBO ownership, and no implicit export
capture.

## Diagnostics

Shader diagnostics use the existing host diagnostic surfaces. Important codes
include:

- `shader/compile-error`
- `shader/link-error`
- `shader/uniform-unsupported`
- `shader/texture-unsupported`
- `shader/texture-unavailable`
- `shader/webgl-unavailable`
- `shader/webgl-context-lost`

Invalid shader records can stay registered with error status so the picker,
inspector, diagnostics panel, and planner can explain the problem without
crashing the preview.

## Canary Coverage

M13 includes two browser-preview-only canaries:

- A clip-local shader canary.
- A timeline postprocess shader canary.

Both canaries use the same SDK contribution kind, `ctx.shaders` registration,
uniform schema subset, diagnostics path, renderability metadata, preview
surface, picker/selection contracts, and planner blocker/materializer posture.

exec
/bin/zsh -lc "sed -n '30,55p' docs/video-editor/provider-compatibility-matrix.md && sed -n '150,180p' docs/video-editor/extensions-debugging.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
|---|---|---|---|
| **InMemory** | N/A — no persistent storage | Yes (`reigh.ext.<id>.*` prefix convention) | Yes (via `disposeHostServices`) |
| **Supabase** | N/A — no persistent settings table | Yes | Yes |
| **Astrid Bridge** | N/A — no persistent settings table | Yes | Yes |

Settings are always scoped to browser `localStorage` under the `reigh.ext.<id>.` key prefix, regardless of provider. No provider currently offers a server-side settings store. Settings cleanup is provider-agnostic and handled by the extension lifecycle's `disposeHostServices()`.

### 3.2 Extension requirements

| Provider | `ProjectExtensionRequirement` read support | Missing-extension diagnostic severity | Referenced contribution ID validation |
|---|---|---|---|
| **InMemory** | Full — requirements are inlined in TimelineConfig and surfaced via `TimelineReader.snapshot().extensionRequirements` | `warning` (export guard) | Contribution IDs stored in `referencedContributionIds` are validated structurally but not resolved at runtime |
| **Supabase** | Full — same shape, loaded from DB `timelines.config` | `warning` | Same as InMemory |
| **Astrid Bridge** | Full — same shape, loaded from local `assembly.json` or bridge API | `warning` | Same as InMemory |

Extension requirements are a property of the timeline config, not the provider. The `TimelineReader` extracts `extensionRequirements` from the config shape and returns them in every snapshot. When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does not block render.

### 3.3 Proposal base versions

| Provider | `configVersion` semantics | Strict CAS enforcement | Local monotonic invalidation | Stale proposal detection |
|---|---|---|---|---|
| **InMemory** | Monotonic integer, incremented on every `saveTimeline` | **Yes** — `TimelineVersionConflictError` thrown on mismatch | **Yes** — `useTimelineOps.apply()` compares `patch.version` against current `configVersion` before any mutation | **Yes** — `ProposalRuntime.accept()` revalidates `baseVersion` against `reader.snapshot().baseVersion` |
| **Supabase** | Monotonic integer from append service `config_version` | **Yes** — 409 Conflict from append service → `TimelineVersionConflictError` | **Yes** — same local guard as InMemory (catches stale patches before network round-trip) | **Yes** — same revalidation path |
| **Astrid Bridge** | Monotonic integer from bridge payload `config_version` | **Partial** — no server-side CAS; version is incremented locally after save but concurrent writes from another bridge instance would silently overwrite | **Yes** — same local guard | **Yes** — revalidation against current snapshot version works, but the snapshot version may not reflect external concurrent writes |

**Key invariant:** When `patch.version === 0`, the base-version check is bypassed (treated as "no expectation"). This is intended for initial state seeding.
## 5. Export guard diagnostics

### 5.1 Pre-render scan

Before render, `runExportGuard()` scans the timeline config for:

| Condition | Severity | Code | Blocks export? |
|---|---|---|---|
| Unknown clip type (no declaring extension) | `error` | `export/unknown-clip-type` | Yes |
| Unknown effect (no declaring extension) | `error` | `export/unknown-effect` | Yes |
| Unknown transition (no declaring extension) | `error` | `export/unknown-transition` | Yes |
| Extension-declared ID from **inactive** contribution | `warning` | `export/missing-extension` | No (render proceeds) |
| Missing render materializer for shader | `error` | `export/shader-no-materializer` | Yes |

**Evidence:** [Author Contract §6.2](./extension-author-contract.md#62-export-guard-integration) (S-062); `runExportGuard()` in `src/tools/video-editor/runtime/renderability.ts` (CR:M5-005).

### 5.2 Missing extension references

When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does **not** block render. Unknown clip types from missing extensions produce `export/unknown-clip-type` separately.

**Evidence:** [Provider Compatibility Matrix §3.5](./provider-compatibility-matrix.md#35-missing-extension-references) — all three providers handle this identically.

### 5.3 Debugging export blockages

1. Check the export guard diagnostics in the DiagnosticPanel.
2. Verify that all clip types, effects, and transitions used in the timeline are declared in an active extension's manifest `contributions`.
3. If a contribution is declared but the extension is inactive, you'll see `export/missing-extension` (warning). Activate the extension to clear it.
4. For shader exports, verify that a materializer route exists (deferred in V1 — see D-100).

---


codex
The docs are ahead in one place (`phase4-readiness.md` calls `renderPlanner.ts` canonical) and behind in another (`extensions-debugging.md` still points users at export-guard diagnostic codes, some stale). I’m pulling line numbers for the high-signal references so the final answer stays concrete.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderPlanner.ts | sed -n '52,90p;132,184p;930,1016p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/exportGuard.ts | sed -n '72,112p;278,310p;356,470p;623,760p;983,1110p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    52	  readonly request?: RenderPlannerRequest;
    53	  readonly diagnostics?: readonly CapabilityFinding[];
    54	}
    55	
    56	export interface RenderRouteSummary {
    57	  readonly route: RenderRoute;
    58	  readonly blockerCount: number;
    59	  readonly findingCount: number;
    60	  readonly blocked: boolean;
    61	}
    62	
    63	export interface RenderRoutePlan extends RenderRouteSummary {
    64	  readonly requiredCapabilities: readonly string[];
    65	  readonly determinism: DeterminismStatus;
    66	  readonly blockers: readonly RenderBlocker[];
    67	  readonly diagnostics: readonly CapabilityFinding[];
    68	  readonly outputFormatIds: readonly string[];
    69	  readonly processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
    70	  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
    71	}
    72	
    73	export interface RenderPlannerGuardCompatibility {
    74	  readonly diagnostics: readonly CapabilityFinding[];
    75	  readonly findings: readonly CapabilityFinding[];
    76	  readonly blockers: readonly RenderBlocker[];
    77	  readonly unknownClipTypes: readonly string[];
    78	  readonly unknownEffects: readonly string[];
    79	  readonly unknownTransitions: readonly string[];
    80	  readonly inactiveExtensionIds: {
    81	    readonly effectIds: ReadonlySet<string>;
    82	    readonly transitionIds: ReadonlySet<string>;
    83	    readonly clipTypeIds: ReadonlySet<string>;
    84	  };
    85	  readonly hasBlockingErrors: boolean;
    86	}
    87	
    88	export interface RenderPlannerResult {
    89	  readonly guard: RenderPlannerGuardCompatibility;
    90	  readonly findings: readonly CapabilityFinding[];
   132	    routeDeterminism: new Map(),
   133	  };
   134	}
   135	
   136	function addRouteValue<T>(map: Map<RenderRoute, T[]>, route: RenderRoute, value: T): void {
   137	  const values = map.get(route);
   138	  if (values) {
   139	    values.push(value);
   140	    return;
   141	  }
   142	  map.set(route, [value]);
   143	}
   144	
   145	function addRouteSetValue(map: Map<RenderRoute, Set<string>>, route: RenderRoute, value: string): void {
   146	  const values = map.get(route);
   147	  if (values) {
   148	    values.add(value);
   149	    return;
   150	  }
   151	  map.set(route, new Set([value]));
   152	}
   153	
   154	function freezeFinding(finding: CapabilityFinding): CapabilityFinding {
   155	  return Object.freeze({
   156	    ...finding,
   157	    ...(finding.detail ? { detail: Object.freeze({ ...finding.detail }) } : {}),
   158	  });
   159	}
   160	
   161	function freezeBlocker(blocker: RenderBlocker): RenderBlocker {
   162	  return Object.freeze({
   163	    ...blocker,
   164	    ...(blocker.detail ? { detail: Object.freeze({ ...blocker.detail }) } : {}),
   165	  });
   166	}
   167	
   168	function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
   169	  const seen = new Set<string>();
   170	  const deduped: T[] = [];
   171	  for (const item of items) {
   172	    if (seen.has(item.id)) continue;
   173	    seen.add(item.id);
   174	    deduped.push(item);
   175	  }
   176	  return deduped;
   177	}
   178	
   179	function sortedFindings(findings: readonly CapabilityFinding[]): readonly CapabilityFinding[] {
   180	  return Object.freeze(
   181	    dedupeById(findings.map(freezeFinding)).sort((a, b) => a.id.localeCompare(b.id)),
   182	  );
   183	}
   184	
   930	  const materialStatusById = createMaterialStatusMap(input.materialStatuses);
   931	  const requestedOutputFormat = input.request?.outputFormatId
   932	    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
   933	    : undefined;
   934	
   935	  for (const requirement of requirements) {
   936	    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
   937	      ? shaderBySourceRef.get(shaderDescriptorKey(
   938	        requirement.sourceRef.extensionId,
   939	        requirement.sourceRef.contributionId,
   940	      ))
   941	      : undefined;
   942	    if (
   943	      shaderDescriptor
   944	      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
   945	    ) {
   946	      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
   947	      continue;
   948	    }
   949	    collectRequirement(acc, requirement);
   950	  }
   951	  collectRequestCapabilities(acc, input.request);
   952	  for (const outputFormat of outputFormats) {
   953	    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
   954	    collectOutputFormat(acc, outputFormat, processStatusById);
   955	  }
   956	  collectRequestedOutputRouteSupport(acc, requestedOutputFormat, input.request);
   957	  for (const process of processes) {
   958	    collectProcess(acc, process);
   959	  }
   960	  for (const materialRef of input.materialRefs ?? []) {
   961	    collectMaterialRef(acc, materialRef, materialStatusById);
   962	  }
   963	  collectRenderGroups(acc, input.snapshot);
   964	  acc.findings.push(...shaderComposition.findings);
   965	  acc.findings.push(...(input.diagnostics ?? []));
   966	
   967	  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
   968	    const blocker: RenderBlocker = {
   969	      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
   970	      severity: 'error',
   971	      route: input.request.route ?? input.request.routes?.[0] ?? 'sidecar-export',
   972	      reason: 'missing-contribution',
   973	      message: `Output format "${input.request.outputFormatId}" is not registered.`,
   974	      contributionId: input.request.outputFormatId,
   975	      detail: {
   976	        source: 'render-request',
   977	        outputFormatId: input.request.outputFormatId,
   978	      },
   979	    };
   980	    acc.findings.push(blocker);
   981	    acc.blockers.push(blocker);
   982	  }
   983	
   984	  const findings = sortedFindings(acc.findings);
   985	  const blockers = sortedBlockers([
   986	    ...acc.blockers,
   987	    ...findings.map(blockerForFinding).filter((blocker): blocker is RenderBlocker => Boolean(blocker)),
   988	  ]);
   989	  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
   990	  const routes = Object.freeze(routePlans.map((routePlan) => Object.freeze({
   991	    route: routePlan.route,
   992	    blockerCount: routePlan.blockerCount,
   993	    findingCount: routePlan.findingCount,
   994	    blocked: routePlan.blocked,
   995	  })));
   996	  const browserRoute = routePlans.find((route) => route.route === 'browser-export');
   997	  const workerRoute = routePlans.find((route) => route.route === 'worker-export');
   998	
   999	  return Object.freeze({
  1000	    guard: emptyGuard(findings, blockers),
  1001	    findings,
  1002	    blockers,
  1003	    routes,
  1004	    routePlans,
  1005	    diagnostics: findings,
  1006	    nextActions: sortedActions(acc.nextActions),
  1007	    canBrowserExport: !browserRoute?.blocked,
  1008	    canWorkerExport: !workerRoute?.blocked,
  1009	  });
  1010	}

 succeeded in 0ms:
    72	 * Extension-declared known IDs collected from inactive reserved contributions.
    73	 * These are treated as metadata only — no render dispatch is triggered.
    74	 */
    75	export interface InactiveKnownIds {
    76	  /** Effect IDs declared by inactive extension contributions. */
    77	  readonly effectIds: ReadonlySet<string>;
    78	  /** Transition IDs declared by inactive extension contributions. */
    79	  readonly transitionIds: ReadonlySet<string>;
    80	  /** Clip-type IDs declared by inactive extension contributions. */
    81	  readonly clipTypeIds: ReadonlySet<string>;
    82	}
    83	
    84	// ---------------------------------------------------------------------------
    85	// Export guard result
    86	// ---------------------------------------------------------------------------
    87	
    88	/**
    89	 * The result of an export guard scan over a resolved timeline config.
    90	 */
    91	export interface ExportGuardResult {
    92	  /** Structured diagnostics for every unknown/unavailable ID found. */
    93	  readonly diagnostics: readonly ExportDiagnostic[];
    94	  /** Shared planner-compatible findings for export readiness. */
    95	  readonly findings: readonly CapabilityFinding[];
    96	  /** Shared planner-compatible blockers that prevent browser export. */
    97	  readonly blockers: readonly RenderBlocker[];
    98	  /** Clip types used in the timeline that are not in any known set. */
    99	  readonly unknownClipTypes: readonly string[];
   100	  /** Effect types used in the timeline that are not in any known set. */
   101	  readonly unknownEffects: readonly string[];
   102	  /** Transition types used in the timeline that are not in any known set. */
   103	  readonly unknownTransitions: readonly string[];
   104	  /** Extension-declared known IDs collected as inactive metadata. */
   105	  readonly inactiveExtensionIds: InactiveKnownIds;
   106	  /** Whether any blocking error diagnostics were emitted. */
   107	  readonly hasBlockingErrors: boolean;
   108	}
   109	
   110	// ---------------------------------------------------------------------------
   111	// Built-in ID collection
   112	// ---------------------------------------------------------------------------
   278	  const unknownClipTypes = new Set<string>();
   279	  const unknownEffects = new Set<string>();
   280	  const unknownTransitions = new Set<string>();
   281	
   282	  if (config && config.clips.length > 0) {
   283	    scanLiveBindingExportBlockers(config, diagnostics, findings, blockers);
   284	    scanTimelineShaderExportBlockers(config, diagnostics, findings, blockers);
   285	
   286	    const allKnown = buildAllKnown(builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);
   287	
   288	    for (const clip of config.clips) {
   289	      scanClip(clip, allKnown, diagnostics, findings, blockers, unknownClipTypes, unknownEffects, unknownTransitions);
   290	    }
   291	  }
   292	
   293	  // Sort diagnostics for determinism
   294	  diagnostics.sort((a, b) => a.code.localeCompare(b.code) || a.message.localeCompare(b.message));
   295	  findings.sort((a, b) => a.id.localeCompare(b.id));
   296	  blockers.sort((a, b) => a.id.localeCompare(b.id));
   297	
   298	  const hasBlockingErrors = diagnostics.some((d) => d.severity === 'error');
   299	
   300	  return Object.freeze({
   301	    diagnostics: Object.freeze(diagnostics),
   302	    findings: Object.freeze(findings),
   303	    blockers: Object.freeze(blockers),
   304	    unknownClipTypes: Object.freeze([...unknownClipTypes].sort()),
   305	    unknownEffects: Object.freeze([...unknownEffects].sort()),
   306	    unknownTransitions: Object.freeze([...unknownTransitions].sort()),
   307	    inactiveExtensionIds: extIds,
   308	    hasBlockingErrors,
   309	  });
   310	}
   356	
   357	function scanTimelineShaderExportBlockers(
   358	  config: ResolvedTimelineConfig,
   359	  diagnostics: ExportDiagnostic[],
   360	  findings: CapabilityFinding[],
   361	  blockers: RenderBlocker[],
   362	): void {
   363	  for (const clip of config.clips) {
   364	    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
   365	    if (!shader || shader.enabled === false) continue;
   366	    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
   367	      shaderId: shader.shaderId,
   368	      extensionId: shader.extensionId,
   369	      contributionId: shader.contributionId,
   370	      scope: 'clip',
   371	      clipId: clip.id,
   372	    });
   373	  }
   374	
   375	  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
   376	    ? config.app.shaderPostprocess
   377	    : undefined;
   378	  if (postprocessShader && postprocessShader.enabled !== false) {
   379	    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
   380	      shaderId: postprocessShader.shaderId,
   381	      extensionId: postprocessShader.extensionId,
   382	      contributionId: postprocessShader.contributionId,
   383	      scope: 'postprocess',
   384	    });
   385	  }
   386	}
   387	
   388	function pushShaderMaterializerFindingAndBlocker(
   389	  diagnostics: ExportDiagnostic[],
   390	  findings: CapabilityFinding[],
   391	  blockers: RenderBlocker[],
   392	  input: {
   393	    readonly shaderId: string;
   394	    readonly extensionId: string;
   395	    readonly contributionId: string;
   396	    readonly scope: ShaderMaterializerRequirementScope;
   397	    readonly clipId?: string;
   398	  },
   399	): void {
   400	  const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];
   401	
   402	  for (const route of routes) {
   403	    const message = shaderMissingMaterializerBlockerMessage(input.shaderId, input.scope, input.clipId);
   404	    const id = `export.shader.${input.scope}.${input.clipId ?? 'timeline'}.${input.shaderId}.${route}.missing-materializer`;
   405	    const detail = {
   406	      shaderId: input.shaderId,
   407	      shaderScope: input.scope,
   408	      renderRoute: route,
   409	      ...(input.clipId ? { clipId: input.clipId } : {}),
   410	    };
   411	
   412	    diagnostics.push({
   413	      severity: 'error',
   414	      code: 'export/unrenderable-shader',
   415	      message,
   416	      extensionId: input.extensionId,
   417	      contributionId: input.contributionId,
   418	      detail,
   419	    });
   420	
   421	    const finding: CapabilityFinding = {
   422	      id,
   423	      severity: 'error',
   424	      route,
   425	      reason: 'missing-material',
   426	      message,
   427	      ...(input.clipId ? { clipId: input.clipId } : {}),
   428	      extensionId: input.extensionId,
   429	      contributionId: input.contributionId,
   430	      detail: {
   431	        shaderId: input.shaderId,
   432	        shaderScope: input.scope,
   433	        source: 'timeline-shader-metadata',
   434	      },
   435	    };
   436	    findings.push(finding);
   437	    blockers.push({
   438	      ...finding,
   439	      severity: 'error',
   440	      route,
   441	      reason: 'missing-material',
   442	    });
   443	  }
   444	}
   445	
   446	function liveBindingStatusMessage(record: TimelineLiveBindingRecord): string {
   447	  const bindingId = record.binding.bindingId;
   448	  switch (record.status) {
   449	    case 'active':
   450	      return `Live binding "${bindingId}" is active and must be baked or removed before export.`;
   451	    case 'inactive':
   452	      return `Live binding "${bindingId}" references an inactive source and must be baked or removed before export.`;
   453	    case 'missing':
   454	      return `Live binding "${bindingId}" references a missing source and must be baked or removed before export.`;
   455	    case 'disposed':
   456	      return `Live binding "${bindingId}" references a disposed source and must be baked or removed before export.`;
   457	    case 'orphaned':
   458	      return `Live binding "${bindingId}" references an orphaned source and must be baked or removed before export.`;
   459	    case 'partiallyBaked':
   460	      return `Live binding "${bindingId}" is partially baked; unresolved ranges must be baked or removed before export.`;
   461	    case 'malformed':
   462	      return `Live binding metadata on clip "${record.clipId}" is malformed and blocks export until fixed or removed.`;
   463	    case 'resolved':
   464	      return `Live binding "${bindingId}" has deterministic replacement metadata.`;
   465	  }
   466	}
   467	
   468	function pushLiveBindingFindingAndBlocker(
   469	  diagnostics: ExportDiagnostic[],
   470	  findings: CapabilityFinding[],
   623	// Effect scan helper
   624	// ---------------------------------------------------------------------------
   625	
   626	type EffectSlot = 'entrance' | 'exit' | 'continuous';
   627	
   628	/** Routes that the export guard checks independently for each registered effect. */
   629	const GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;
   630	
   631	function scanEffect(
   632	  clip: ResolvedTimelineClip,
   633	  slot: EffectSlot,
   634	  known: AllKnownIds,
   635	  diagnostics: ExportDiagnostic[],
   636	  findings: CapabilityFinding[],
   637	  blockers: RenderBlocker[],
   638	  unknownEffects: Set<string>,
   639	): void {
   640	  // The effect can be stored as `ClipEntrance | ClipExit | ClipContinuous`
   641	  // or as `TimelineEffect[] | Record<string, number>` in `effects`.
   642	  const effect = clip[slot];
   643	  if (!effect) return;
   644	
   645	  let effectType: string | undefined;
   646	
   647	  if (typeof effect === 'object' && 'type' in effect && typeof (effect as Record<string, unknown>).type === 'string') {
   648	    effectType = (effect as Record<string, unknown>).type as string;
   649	  }
   650	
   651	  if (!effectType) return;
   652	
   653	  const snapshotRecord = known.effectRegistrySnapshot?.get(effectType);
   654	  if (!known.effectTypes.has(effectType) && !snapshotRecord) {
   655	    const isExtDeclared = known.extensionEffectIds.has(effectType);
   656	    const message = isExtDeclared
   657	      ? `${capitalise(slot)} effect "${effectType}" is declared by an inactive extension and may not be available at export time.`
   658	      : `${capitalise(slot)} effect "${effectType}" is not recognised. Ensure the required extension or registry is installed.`;
   659	
   660	    diagnostics.push({
   661	      severity: isExtDeclared ? 'warning' : 'error',
   662	      code: 'export/unknown-effect-type',
   663	      message,
   664	      detail: { clipId: clip.id, effectType },
   665	    });
   666	
   667	    if (!isExtDeclared) {
   668	      unknownEffects.add(effectType);
   669	      pushEffectFindingAndBlocker(findings, blockers, {
   670	        id: `export.effect.${clip.id}.${slot}.${effectType}.missing`,
   671	        reason: 'missing-contribution',
   672	        message,
   673	        clipId: clip.id,
   674	        effectType,
   675	        slot,
   676	        route: 'browser-export',
   677	      });
   678	    }
   679	    return;
   680	  }
   681	
   682	  if (snapshotRecord) {
   683	    scanEffectRecordRenderability(clip, slot, effectType, snapshotRecord, diagnostics, findings, blockers);
   684	  }
   685	}
   686	
   687	function scanEffectRecordRenderability(
   688	  clip: ResolvedTimelineClip,
   689	  slot: EffectSlot,
   690	  effectType: string,
   691	  record: EffectRegistryRecord,
   692	  diagnostics: ExportDiagnostic[],
   693	  findings: CapabilityFinding[],
   694	  blockers: RenderBlocker[],
   695	): void {
   696	  if (record.status !== 'active') {
   697	    const message = `${capitalise(slot)} effect "${effectType}" is registered but inactive and cannot be used for export or preview.`;
   698	    diagnostics.push({
   699	      severity: 'error',
   700	      code: 'export/unrenderable-effect',
   701	      message,
   702	      extensionId: record.ownerExtensionId,
   703	      contributionId: record.contributionId,
   704	      detail: {
   705	        clipId: clip.id,
   706	        effectType,
   707	        effectStatus: record.status,
   708	        provenance: record.provenance,
   709	      },
   710	    });
   711	
   712	    // Emit a blocker for every guarded route — an inactive effect can't be used anywhere.
   713	    for (const route of GUARD_ROUTES) {
   714	      pushEffectFindingAndBlocker(findings, blockers, {
   715	        id: `export.effect.${clip.id}.${slot}.${effectType}.inactive.${route}`,
   716	        reason: 'inactive-extension',
   717	        message: `${capitalise(slot)} effect "${effectType}" on route "${route}" is registered but inactive.`,
   718	        clipId: clip.id,
   719	        effectType,
   720	        slot,
   721	        route,
   722	        record,
   723	      });
   724	    }
   725	    return;
   726	  }
   727	
   728	  // Check each guarded route independently.
   729	  for (const route of GUARD_ROUTES) {
   730	    const capability = record.renderability.capabilities.find((cap) => cap.route === route);
   731	
   732	    if (!capability) {
   733	      // No capability declared for this route — pass silently.
   734	      continue;
   735	    }
   736	
   737	    if (capability.status === 'supported') {
   738	      // Route is supported — pass silently.
   739	      continue;
   740	    }
   741	
   742	    if (capability.status === 'unknown') {
   743	      // Unknown support — emit a warning finding (non-blocking).
   744	      const message = capability.message
   745	        ?? `${capitalise(slot)} effect "${effectType}" has unknown support for ${route}.`;
   746	      diagnostics.push({
   747	        severity: 'warning',
   748	        code: 'export/unknown-route-support',
   749	        message,
   750	        extensionId: record.ownerExtensionId,
   751	        contributionId: record.contributionId,
   752	        detail: {
   753	          clipId: clip.id,
   754	          effectType,
   755	          renderRoute: route,
   756	          provenance: record.provenance,
   757	          determinism: capability.determinism,
   758	        },
   759	      });
   760	      findings.push({
   983	      detail: {
   984	        clipId: clip.id,
   985	        transitionType,
   986	        renderRoute: route,
   987	        blockerReason: reason,
   988	        provenance: record.provenance,
   989	      },
   990	    });
   991	    pushTransitionFindingAndBlocker(findings, blockers, {
   992	      id: `export.transition.${clip.id}.${transitionType}.${route}.${reason}`,
   993	      reason,
   994	      message,
   995	      clipId: clip.id,
   996	      transitionType,
   997	      route,
   998	      record,
   999	    });
  1000	  }
  1001	}
  1002	
  1003	function firstTransitionRouteBlockerReason(record: TransitionRegistryRecord, route: RenderRoute): RenderBlockerReason | undefined {
  1004	  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
  1005	}
  1006	
  1007	function pushTransitionFindingAndBlocker(
  1008	  findings: CapabilityFinding[],
  1009	  blockers: RenderBlocker[],
  1010	  input: {
  1011	    id: string;
  1012	    reason: RenderBlockerReason;
  1013	    message: string;
  1014	    clipId: string;
  1015	    transitionType: string;
  1016	    route: RenderRoute;
  1017	    record?: TransitionRegistryRecord;
  1018	  },
  1019	): void {
  1020	  const detail: Record<string, unknown> = {
  1021	    transitionType: input.transitionType,
  1022	  };
  1023	  if (input.record?.provenance) {
  1024	    detail.provenance = input.record.provenance;
  1025	  }
  1026	  const finding: CapabilityFinding = {
  1027	    id: input.id,
  1028	    severity: 'error',
  1029	    route: input.route,
  1030	    reason: input.reason,
  1031	    message: input.message,
  1032	    clipId: input.clipId,
  1033	    ...(input.record?.ownerExtensionId ? { extensionId: input.record.ownerExtensionId } : {}),
  1034	    ...(input.record?.contributionId ? { contributionId: input.record.contributionId } : {}),
  1035	    detail,
  1036	  };
  1037	  findings.push(finding);
  1038	  blockers.push({
  1039	    ...finding,
  1040	    severity: 'error',
  1041	    route: input.route,
  1042	    reason: input.reason,
  1043	  });
  1044	}
  1045	
  1046	// ---------------------------------------------------------------------------
  1047	// Clip-type registry scan helpers
  1048	// ---------------------------------------------------------------------------
  1049	
  1050	/** Routes that the export guard checks independently for each registered clip type. */
  1051	const CLIP_TYPE_GUARD_ROUTES: readonly RenderRoute[] = ['preview', 'browser-export', 'worker-export'] as const;
  1052	
  1053	function scanClipTypeRecordRenderability(
  1054	  clip: ResolvedTimelineClip,
  1055	  clipType: string,
  1056	  record: ClipTypeRegistryRecord,
  1057	  diagnostics: ExportDiagnostic[],
  1058	  findings: CapabilityFinding[],
  1059	  blockers: RenderBlocker[],
  1060	): void {
  1061	  if (record.status !== 'active') {
  1062	    const message = `Clip type "${clipType}" is registered but inactive and cannot be used for export or preview.`;
  1063	    diagnostics.push({
  1064	      severity: 'error',
  1065	      code: 'export/unrenderable-clip-type',
  1066	      message,
  1067	      extensionId: record.ownerExtensionId,
  1068	      contributionId: record.contributionId,
  1069	      detail: {
  1070	        clipId: clip.id,
  1071	        clipType,
  1072	        clipTypeStatus: record.status,
  1073	        provenance: record.provenance,
  1074	      },
  1075	    });
  1076	
  1077	    // Emit a blocker for every guarded route — an inactive clip type can't be used anywhere.
  1078	    for (const route of CLIP_TYPE_GUARD_ROUTES) {
  1079	      pushClipTypeFindingAndBlocker(findings, blockers, {
  1080	        id: `export.clipType.${clip.id}.${clipType}.inactive.${route}`,
  1081	        reason: 'inactive-extension',
  1082	        message: `Clip type "${clipType}" on route "${route}" is registered but inactive.`,
  1083	        clipId: clip.id,
  1084	        clipType,
  1085	        route,
  1086	        record,
  1087	      });
  1088	    }
  1089	    return;
  1090	  }
  1091	
  1092	  // Active record — check each guarded route independently.
  1093	  for (const route of CLIP_TYPE_GUARD_ROUTES) {
  1094	    const capability = record.renderability.capabilities.find((cap) => cap.route === route);
  1095	
  1096	    if (!capability) {
  1097	      // No capability declared for this route — pass silently (like effects).
  1098	      continue;
  1099	    }
  1100	
  1101	    if (capability.status === 'supported') {
  1102	      // Route is supported — pass silently.
  1103	      continue;
  1104	    }
  1105	
  1106	    if (capability.status === 'unknown') {
  1107	      // Unknown support — emit a warning finding (non-blocking).
  1108	      const message = capability.message
  1109	        ?? `Clip type "${clipType}" has unknown support for ${route}.`;
  1110	      diagnostics.push({

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/hooks/useRenderState.ts | sed -n '44,78p;184,238p;354,440p;506,566p;572,616p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    44	function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
    45	  const clips = resolvedConfig?.clips ?? [];
    46	
    47	  if (clips.length === 0) {
    48	    return { route: 'browser-remotion' as const, reason: 'no_clips' };
    49	  }
    50	
    51	  let hasGeneratedModuleClip = false;
    52	  let hasOtherClip = false;
    53	  for (const clip of clips) {
    54	    if (clip.generation?.sequence_lane === 'remotion_module') {
    55	      if (!clip.generation?.artifact_id) {
    56	        return { route: 'preview-only' as const, reason: 'remotion_module_missing_artifact' };
    57	      }
    58	      hasGeneratedModuleClip = true;
    59	      continue;
    60	    }
    61	
    62	    if (!clip.clipType || CLIENT_CLIP_TYPES.has(clip.clipType)) {
    63	      hasOtherClip = true;
    64	      continue;
    65	    }
    66	
    67	    return null;
    68	  }
    69	
    70	  if (hasGeneratedModuleClip) {
    71	    return {
    72	      route: 'worker-banodoco' as const,
    73	      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
    74	    };
    75	  }
    76	
    77	  return { route: 'browser-remotion' as const, reason: 'pure_native_clips' };
    78	}
   184	}
   185	
   186	function blockerReasonForExportDiagnostic(diagnostic: ExportDiagnostic): RenderBlockerReason {
   187	  if (diagnostic.code.includes('unknown') || diagnostic.code.includes('missing')) {
   188	    return 'missing-contribution';
   189	  }
   190	  if (diagnostic.code.includes('inactive')) {
   191	    return 'inactive-extension';
   192	  }
   193	  if (diagnostic.code.includes('live-binding')) {
   194	    return 'live-unbaked';
   195	  }
   196	  if (diagnostic.code.includes('shader')) {
   197	    return 'missing-material';
   198	  }
   199	  return 'route-unsupported';
   200	}
   201	
   202	function exportDiagnosticToPlannerFinding(diagnostic: ExportDiagnostic, index: number): CapabilityFinding {
   203	  const route = diagnostic.detail?.renderRoute === 'worker-export' || diagnostic.detail?.renderRoute === 'preview'
   204	    ? diagnostic.detail.renderRoute
   205	    : 'browser-export';
   206	  const reason = diagnostic.severity === 'error'
   207	    ? blockerReasonForExportDiagnostic(diagnostic)
   208	    : undefined;
   209	
   210	  return {
   211	    id: exportDiagnosticId(diagnostic, index),
   212	    severity: diagnostic.severity,
   213	    route,
   214	    ...(reason ? { reason } : {}),
   215	    message: diagnostic.message,
   216	    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
   217	    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
   218	    detail: {
   219	      ...(diagnostic.detail ?? {}),
   220	      source: 'export-guard-compat',
   221	      code: diagnostic.code,
   222	    },
   223	  };
   224	}
   225	
   226	function planFromExportGuardResult(
   227	  guardResult: ReturnType<typeof scanExportConfig>,
   228	): RenderPlannerResult {
   229	  const diagnostics: CapabilityFinding[] = [
   230	    ...(guardResult.findings ?? []),
   231	    ...(guardResult.blockers ?? []),
   232	    ...guardResult.diagnostics.map(exportDiagnosticToPlannerFinding),
   233	  ];
   234	  return planRender({ diagnostics });
   235	}
   236	
   237	function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
   238	  const outputFormats = extensionRuntime?.outputFormats
   354	  const runExportGuard = useCallback((): boolean => {
   355	    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'export-guard');
   356	    diagnosticCollection?.remove((diagnostic) => diagnostic.detail?.source === 'render-planner');
   357	
   358	    // Skip guard work only when there is no active extension/provider registry input.
   359	    if (
   360	      isExtensionRuntimeEmpty(extensionRuntime)
   361	      && effectRegistrySnapshot.records.length === 0
   362	      && transitionRegistrySnapshot.records.length === 0
   363	      && clipTypeRegistrySnapshot.records.length === 0
   364	      && !hasTimelineShaderMetadata(resolvedConfig)
   365	    ) {
   366	      return true; // no blocker
   367	    }
   368	
   369	    if (!resolvedConfig || resolvedConfig.clips.length === 0) {
   370	      return true; // nothing to scan
   371	    }
   372	
   373	    const builtIn = collectBuiltInKnownIds();
   374	    const allContributions = extensionRuntime ? buildExtensionContributions(extensionRuntime) : [];
   375	    const extIds = collectExtensionDeclaredIds(allContributions);
   376	    const guardResult = scanExportConfig(resolvedConfig, builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);
   377	    const plannerResult = planFromExportGuardResult(guardResult);
   378	
   379	    guardResult.diagnostics.forEach((diagnostic, index) => {
   380	      diagnosticCollection?.publish(toCollectionDiagnostic(diagnostic, index));
   381	    });
   382	    syncPlannerDiagnosticsToCollection(diagnosticCollection, plannerResult.blockers);
   383	
   384	    // Emit structured diagnostics as concise render log output
   385	    const log = formatExportGuardLog(guardResult);
   386	    setRenderLog(log);
   387	
   388	    if (plannerResult.blockers.length > 0) {
   389	      // Planner-owned blockers are the canonical readiness decision.
   390	      setRenderStatus('error');
   391	      setRenderProgress(null);
   392	      setRenderDirty(false);
   393	      return false; // blocker
   394	    }
   395	
   396	    // Extension-declared warnings only — preserve native routing
   397	    return true; // no blocker
   398	  }, [diagnosticCollection, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot, extensionRuntime, resolvedConfig]);
   399	
   400	  const startRender = useCallback(async () => {
   401	    // ---- export guard: scan for unknown IDs before routing ------------------
   402	    if (!runExportGuard()) {
   403	      return; // blocked by export guard
   404	    }
   405	
   406	    let decision = getFastRenderRouteDecision(resolvedConfig);
   407	    if (!decision) {
   408	      let importedDecision: {
   409	      route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
   410	      reason: string;
   411	      };
   412	      try {
   413	        const renderRouter = await import('@/tools/video-editor/lib/renderRouter');
   414	        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
   415	      } catch (error) {
   416	        setRenderStatus('error');
   417	        setRenderProgress(null);
   418	        setRenderDirty(false);
   419	        setRenderLog(error instanceof Error
   420	          ? `Render routing unavailable: ${error.message}`
   421	          : 'Render routing unavailable.');
   422	        return;
   423	      }
   424	      decision = importedDecision;
   425	    }
   426	    if (decision.route === 'preview-only') {
   427	      setRenderStatus('error');
   428	      setRenderProgress(null);
   429	      setRenderDirty(false);
   430	      setRenderLog(`Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`);
   431	      return;
   432	    }
   433	
   434	    if (decision.route === 'worker-banodoco' || decision.route === 'external') {
   435	      setRenderStatus('error');
   436	      setRenderProgress(null);
   437	      setRenderDirty(false);
   438	      setRenderLog(`Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`);
   439	      return;
   440	    }
   506	    compileOnlyRegistry?: CompileOnlyOutputFormatRegistry,
   507	  ) => {
   508	    if (!resolvedConfig) {
   509	      setExportStatus('error');
   510	      setExportLogState('Export unavailable: no timeline configuration.');
   511	      return;
   512	    }
   513	
   514	    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
   515	    const outputPlan = planRender({
   516	      outputFormats: plannerOutputFormats,
   517	      processes: extensionRuntime?.processes ?? [],
   518	      request: {
   519	        outputFormatId: formatId,
   520	        routes: ['browser-export'],
   521	      },
   522	      diagnostics: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabled
   523	        ? [{
   524	            id: `planner.outputFormat.${formatId}.disabled`,
   525	            severity: 'error',
   526	            route: 'browser-export',
   527	            reason: 'inactive-extension',
   528	            message: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabledReason
   529	              ?? `Export format "${formatId}" is disabled.`,
   530	            contributionId: formatId,
   531	            detail: { source: 'output-format', outputFormatId: formatId },
   532	          }]
   533	        : [],
   534	    });
   535	    const browserOutputPlan = outputPlan.routePlans.find((routePlan) => routePlan.route === 'browser-export');
   536	    const fmt = plannerOutputFormats.find((f) => f.id === formatId && !f.requiresRender && !f.disabled);
   537	    if (!fmt || browserOutputPlan?.blocked) {
   538	      const requestedFormat = plannerOutputFormats.find((f) => f.id === formatId);
   539	      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
   540	        ?? browserOutputPlan?.blockers[0]
   541	        ?? outputPlan.blockers[0];
   542	      setExportStatus('error');
   543	      if (blocker) {
   544	        setExportLogState(`Export blocked: ${blocker.message}`);
   545	      } else if (requestedFormat) {
   546	        setExportLogState(`Export blocked: "${requestedFormat.label}" is not available for browser export.`);
   547	      } else {
   548	        setExportLogState(`Export format "${formatId}" not found.`);
   549	      }
   550	      return;
   551	    }
   552	
   553	    // ---- M7: Run export guard before compile-only export --------------------
   554	    // Compile-only exports don't need rendered pixels, but they still process
   555	    // timeline data.  Unknown / missing-contribution effects should block
   556	    // because the exported data would be invalid.  Route-specific capability
   557	    // blockers (browser-export blocked, worker-export blocked) are surfaced
   558	    // as warnings but do not prevent compile-only export.
   559	    const guardPassed = runExportGuard();
   560	    if (!guardPassed) {
   561	      // Export guard found blocking errors (e.g. truly unknown effects).
   562	      // Surface the guard log as the export error.
   563	      setExportStatus('error');
   564	      setExportLogState(
   565	        `Export blocked by readiness scan. See render log for details.`,
   566	      );
   572	      setExportLogState(`Export unavailable: no compile-only output handlers registered. Format "${fmt.label}" (${fmt.id}) requires a handler registered via ctx.export.registerOutputFormat().`);
   573	      return;
   574	    }
   575	
   576	    setExportStatus('exporting');
   577	    setExportLogState(`Exporting "${fmt.label}"...`);
   578	    setExportResultUrl((current) => {
   579	      if (current) URL.revokeObjectURL(current);
   580	      return null;
   581	    });
   582	    setExportResultFilename(null);
   583	
   584	    try {
   585	      // Build timeline snapshot from resolved config
   586	      const timeline = Object.freeze({
   587	        id: resolvedConfig.output?.file ?? 'timeline',
   588	        assetKeys: Object.freeze(Object.keys(resolvedConfig.registry ?? {})),
   589	        clipCount: resolvedConfig.clips?.length ?? 0,
   590	        trackCount: resolvedConfig.tracks?.length ?? 0,
   591	        fps: resolvedConfig.output?.fps ?? 30,
   592	        resolution: resolvedConfig.output?.resolution ?? '1920x1080',
   593	      });
   594	
   595	      // Build assets map from registry
   596	      const assetsMap = new Map<string, any>();
   597	      if (resolvedConfig.registry) {
   598	        for (const [key, entry] of Object.entries(resolvedConfig.registry)) {
   599	          assetsMap.set(key, Object.freeze(entry));
   600	        }
   601	      }
   602	      const assets: ReadonlyMap<string, Readonly<any>> = Object.freeze(assetsMap);
   603	
   604	      const result = await executeCompileOnlyOutput(compileOnlyRegistry, {
   605	        formatId,
   606	        timeline: timeline as any,
   607	        assets: assets as any,
   608	        extensionId: fmt.extensionId,
   609	      });
   610	
   611	      if (!result) {
   612	        setExportStatus('error');
   613	        setExportLogState(`Export failed: format "${fmt.label}" is not available in the compile-only registry.`);
   614	        return;
   615	      }
   616	

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/renderRouter.ts | sed -n '66,126p;293,460p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
    66	
    67	/**
    68	 * Sprint 8 (final): provider-id taxonomy used by the render pipeline +
    69	 * `renderPipeline.ts`. Each route maps 1:1 onto a provider id so middleware
    70	 * can dispatch on the route without a separate lookup table.
    71	 *
    72	 *   * `browser-remotion`  — client-side WebCodecs / Remotion path
    73	 *                          (`useClientRender`, native + media clips).
    74	 *   * `worker-banodoco`   — orchestrator `banodoco_render_timeline`
    75	 *                          (themed + generated-remotion-module clips).
    76	 *   * `preview-only`      — generated remotion_module clips with invalid /
    77	 *                          missing artifact metadata. Cannot be rendered;
    78	 *                          surfaces a hard "render blocked" message.
    79	 *   * `external`          — reserved for future external render providers.
    80	 *                          Currently unreachable from `decideRenderRoute`.
    81	 */
    82	export type RenderRoute =
    83	  | 'browser-remotion'
    84	  | 'worker-banodoco'
    85	  | 'preview-only'
    86	  | 'external';
    87	
    88	export type RenderProviderId = RenderRoute;
    89	
    90	export const RENDER_PROVIDER_REGISTRY: Readonly<Record<RenderRoute, RenderProviderId>> = {
    91	  'browser-remotion': 'browser-remotion',
    92	  'worker-banodoco': 'worker-banodoco',
    93	  'preview-only': 'preview-only',
    94	  external: 'external',
    95	};
    96	
    97	export interface RenderRouteDecision {
    98	  route: RenderRoute;
    99	  /** True iff at least one clip is themed (i.e. uses the registry). */
   100	  hasThemedClip: boolean;
   101	  /** True iff at least one clip is pure-media / Reigh-native. */
   102	  hasMediaClip: boolean;
   103	  /** True iff at least one clip is a contributed extension clip. */
   104	  hasContributedClip: boolean;
   105	  reason:
   106	    | 'no_clips'
   107	    | 'pure_native_clips'
   108	    | 'themed_only'
   109	    | 'mixed_themed_and_media'
   110	    | 'generated_remotion_module'
   111	    | 'mixed_generated_module_and_other'
   112	    | 'browser_capable_contributed'
   113	    | 'mixed_browser_capable_contributed_and_native'
   114	    | 'contributed_blocked_no_browser_capability'
   115	    | 'contributed_blocked_worker_route_conflict'
   116	    | GeneratedRemotionModuleBlockReason;
   117	}
   118	
   119	interface PlannerRouteDecisionContext {
   120	  readonly plannerResult: RenderPlannerResult;
   121	  readonly selectedPlannerRoute: 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';
   122	}
   123	
   124	export interface PlannerBackedRenderRouteDecision extends RenderRouteDecision {
   125	  readonly planner: PlannerRouteDecisionContext;
   126	}
   293	  if (result.canBrowserExport) {
   294	    return { plannerResult: result, selectedPlannerRoute: 'browser-export' };
   295	  }
   296	  if (result.canWorkerExport) {
   297	    return { plannerResult: result, selectedPlannerRoute: 'worker-export' };
   298	  }
   299	  return { plannerResult: result, selectedPlannerRoute: 'preview' };
   300	}
   301	
   302	/** Pure-decision routing — call this from a hook or test. */
   303	export function decideRenderRoute(
   304	  timeline: RouterTimelineShape | null | undefined,
   305	  contributedClipRecords?: ReadonlyArray<ContributedClipRecord>,
   306	): PlannerBackedRenderRouteDecision {
   307	  const clips = (timeline?.clips ?? []) as ReadonlyArray<RouterClipShape>;
   308	  const contributedIndex = indexContributedRecords(contributedClipRecords);
   309	
   310	  if (clips.length === 0) {
   311	    return {
   312	      route: 'browser-remotion',
   313	      hasThemedClip: false,
   314	      hasMediaClip: false,
   315	      hasContributedClip: false,
   316	      reason: 'no_clips',
   317	      planner: selectPlannerRoute(planRender({ requirements: [] })),
   318	    };
   319	  }
   320	
   321	  const requirements: CapabilityRequirement[] = [];
   322	  let hasThemedClip = false;
   323	  let hasMediaClip = false;
   324	  let hasContributedClip = false;
   325	  let hasBrowserCapableContributedClip = false;
   326	  let hasNativeOrMediaClip = false;
   327	  let hasGeneratedModuleClip = false;
   328	  let hasOtherClip = false;
   329	  let blockedReason: RenderRouteDecision['reason'] | null = null;
   330	  let blockedHasThemedClip = false;
   331	  let blockedHasMediaClip = false;
   332	  let blockedHasContributedClip = false;
   333	
   334	  clips.forEach((clip, index) => {
   335	    if (blockedReason) return;
   336	    const requirementId = `router.clip.${index}.${clip.clipType ?? 'legacy'}`;
   337	    const moduleStatus = getGeneratedRemotionModuleStatus(clip);
   338	    if (moduleStatus.kind === 'blocked_module') {
   339	      requirements.push(...requirementsForBlockedClip(
   340	        clip.clipType,
   341	        requirementId,
   342	        moduleStatus.reason,
   343	        moduleStatus.reason === 'remotion_module_missing_artifact'
   344	          ? 'missing-material'
   345	          : 'materialization-failed',
   346	      ));
   347	      blockedReason = moduleStatus.reason;
   348	      return;
   349	    }
   350	    if (moduleStatus.kind === 'valid_module') {
   351	      hasGeneratedModuleClip = true;
   352	      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'generated_remotion_module'));
   353	      return;
   354	    }
   355	
   356	    hasOtherClip = true;
   357	
   358	    // M9 T11: Check contributed clip records first. Contributed clip
   359	    // code is only allowed in browser-remotion when it explicitly
   360	    // declares browser-export capability. Worker routes are always
   361	    // blocked for contributed code (SD1).
   362	    const clipType = clip?.clipType;
   363	    if (typeof clipType === 'string') {
   364	      const contributedRecord = contributedIndex.get(clipType);
   365	      if (contributedRecord) {
   366	        hasContributedClip = true;
   367	        if (hasBrowserExportCapability(contributedRecord)) {
   368	          hasBrowserCapableContributedClip = true;
   369	          requirements.push(...requirementsForBrowserOnlyClip(clipType, requirementId, 'browser_capable_contributed'));
   370	        } else {
   371	          // Contributed clip without browser-export capability is
   372	          // immediately blocked — worker routes are out of scope
   373	          // for contributed code and no other route is available.
   374	          requirements.push(...requirementsForBlockedClip(
   375	            clipType,
   376	            requirementId,
   377	            'contributed_blocked_no_browser_capability',
   378	            'route-unsupported',
   379	          ));
   380	          blockedReason = 'contributed_blocked_no_browser_capability';
   381	          blockedHasContributedClip = true;
   382	          return;
   383	        }
   384	        return;
   385	      }
   386	    }
   387	
   388	    // Non-contributed clips follow existing routing.
   389	    if (isCustomRenderClipType(clip?.clipType)) {
   390	      hasThemedClip = true;
   391	      // A themed clip mixed with browser-capable contributed clips
   392	      // creates a conflict: themed clips need worker, contributed
   393	      // clips can't go to worker.
   394	      if (hasBrowserCapableContributedClip) {
   395	        requirements.push(...requirementsForBlockedClip(
   396	          clip.clipType,
   397	          requirementId,
   398	          'contributed_blocked_worker_route_conflict',
   399	          'route-unsupported',
   400	        ));
   401	        blockedReason = 'contributed_blocked_worker_route_conflict';
   402	        blockedHasThemedClip = true;
   403	        blockedHasMediaClip = true;
   404	        blockedHasContributedClip = true;
   405	        return;
   406	      }
   407	      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'themed_only'));
   408	    } else if (isNativeBuiltinClipType(clip?.clipType)) {
   409	      hasMediaClip = true;
   410	      hasNativeOrMediaClip = true;
   411	      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
   412	    } else {
   413	      // Unknown clipType (theme package not installed, typo). Treat as
   414	      // media so the existing render path's loud-placeholder fallback
   415	      // surfaces — orchestrator wouldn't be able to render it either
   416	      // without the theme package, and the sprint scopes us to
   417	      // registered themes.
   418	      hasMediaClip = true;
   419	      hasNativeOrMediaClip = true;
   420	      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
   421	    }
   422	  });
   423	
   424	  const planner = selectPlannerRoute(planRender({ requirements }));
   425	
   426	  if (blockedReason) {
   427	    return {
   428	      route: 'preview-only',
   429	      hasThemedClip: blockedHasThemedClip,
   430	      hasMediaClip: blockedHasMediaClip,
   431	      hasContributedClip: blockedHasContributedClip,
   432	      reason: blockedReason,
   433	      planner,
   434	    };
   435	  }
   436	
   437	  // Generated Remotion module clips always go to the worker pool if
   438	  // they survived the blocked_module short-circuit above. Mixed
   439	  // generated + browser-capable contributed clips create an
   440	  // unresolvable conflict because contributed code cannot execute in
   441	  // the worker.
   442	  if (hasGeneratedModuleClip) {
   443	    if (hasBrowserCapableContributedClip) {
   444	      const conflictPlanner = selectPlannerRoute(planRender({
   445	        requirements: [
   446	          ...requirements,
   447	          ...requirementsForBlockedClip(
   448	            'generated-remotion-module',
   449	            'router.generated.contributed-conflict',
   450	            'contributed_blocked_worker_route_conflict',
   451	            'route-unsupported',
   452	          ),
   453	        ],
   454	      }));
   455	      return {
   456	        route: 'preview-only',
   457	        hasThemedClip,
   458	        hasMediaClip,
   459	        hasContributedClip: true,
   460	        reason: 'contributed_blocked_worker_route_conflict',

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/extensionSurface.ts | sed -n '130,210p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "nl -ba docs/extensions/phase4-readiness.md | sed -n '18,75p;105,130p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderability.ts | sed -n '1,105p;455,525p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   130	}
   131	
   132	export interface VideoEditorExtensionRuntimeConfig {
   133	  slots: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
   134	  dialogHost: {
   135	    dialogs: readonly VideoEditorDialogDescriptor[];
   136	  };
   137	  registry: {
   138	    panels: readonly VideoEditorPanelDescriptor[];
   139	    inspectorSections: readonly VideoEditorInspectorSectionDescriptor[];
   140	  };
   141	  overlays: readonly VideoEditorOverlayDescriptor[];
   142	  /** M6: Normalized asset parser descriptors, provider-scoped and deterministically ordered. */
   143	  assetParsers: readonly VideoEditorAssetParserDescriptor[];
   144	  /** M6: Normalized output format descriptors (disabled diagnostics for render-dependent). */
   145	  outputFormats: readonly VideoEditorOutputFormatDescriptor[];
   146	  /** M12: Normalized process descriptors, declaration-only until host runtime activation. */
   147	  processes: readonly VideoEditorProcessDescriptor[];
   148	  /** M6: Normalized search provider descriptors, declaration-only until execution is bridged. */
   149	  searchProviders: readonly VideoEditorSearchProviderDescriptor[];
   150	  /** M6: Normalized metadata facet descriptors for the asset panel. */
   151	  metadataFacets: readonly VideoEditorMetadataFacetDescriptor[];
   152	  /** M6: Normalized asset detail section descriptors for the asset detail panel. */
   153	  assetDetailSections: readonly VideoEditorAssetDetailSectionDescriptor[];
   154	  /** M7: Normalized component-backed effect descriptors, provider-scoped and deterministically ordered. */
   155	  effects: readonly VideoEditorEffectDescriptor[];
   156	  /** M8: Normalized component-backed transition descriptors, provider-scoped and deterministically ordered. */
   157	  transitions: readonly VideoEditorTransitionDescriptor[];
   158	  /** M13: Normalized WebGL shader descriptors, provider-scoped and deterministically ordered. */
   159	  shaders: readonly VideoEditorShaderDescriptor[];
   160	  /** M10: Normalized agent tool descriptors, provider-scoped and deterministically ordered. */
   161	  agentTools: readonly VideoEditorAgentToolDescriptor[];
   162	}
   163	
   164	export interface ResolvedVideoEditorPanelRegistry {
   165	  assetPanels: readonly VideoEditorPanelDescriptor[];
   166	  inspectorSections: {
   167	    all: readonly VideoEditorInspectorSectionDescriptor[];
   168	    beforeDefault: readonly VideoEditorInspectorSectionDescriptor[];
   169	    afterDefault: readonly VideoEditorInspectorSectionDescriptor[];
   170	  };
   171	}
   172	
   173	// ---------------------------------------------------------------------------
   174	// M6: Asset parser / output format / search provider descriptors
   175	// ---------------------------------------------------------------------------
   176	
   177	/** A normalized asset parser descriptor produced by runtime normalization. */
   178	export interface VideoEditorAssetParserDescriptor {
   179	  id: string;
   180	  extensionId: string;
   181	  order?: number;
   182	  label: string;
   183	  acceptMimeTypes?: readonly string[];
   184	  acceptExtensions?: readonly string[];
   185	  maxBytes?: number;
   186	  required?: boolean;
   187	}
   188	
   189	/** A normalized output format descriptor produced by runtime normalization. */
   190	export interface VideoEditorOutputFormatDescriptor {
   191	  id: string;
   192	  extensionId: string;
   193	  order?: number;
   194	  label: string;
   195	  requiresRender: boolean;
   196	  outputExtension: string;
   197	  outputMimeType?: string;
   198	  description?: string;
   199	  /** When true, direct compile-only execution is unavailable. */
   200	  disabled: boolean;
   201	  /** Reason for disabled state, surfaced in the export UI. */
   202	  disabledReason?: string;
   203	  /** Planner-visible routes declared by render-dependent output formats. */
   204	  availableRoutes: readonly RenderRoute[];
   205	  /** Render route/process requirements for planner-owned execution. */
   206	  routeRequirements: readonly VideoEditorRouteRequirementDescriptor[];
   207	  /** Process requirements referenced by this output format. */
   208	  processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
   209	  /** Declaration-time blockers that the planner should surface before execution. */
   210	  blockers: readonly VideoEditorPlannerBlockerDescriptor[];

 succeeded in 0ms:
    18	  `CONTRIBUTION_KIND_MILESTONE`, and `contributionKindNotYetBridged()`, and
    19	  `src/tools/video-editor/runtime/extensionSurface.ts`, which normalizes active
    20	  or reserved contributions into provider/runtime descriptors.
    21	- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
    22	  surfaces reserved descriptors for output formats, processes, shaders, and
    23	  agent tools. Output formats are turned into planner metadata with route
    24	  requirements, process requirements, blockers, next actions, sidecars, and
    25	  capability metadata. Process descriptors are surfaced as planner-visible
    26	  declarations without starting a runtime process.
    27	- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
    28	  adapter for user render clicks. It converts native, themed, generated
    29	  Remotion module, and contributed clip content into `CapabilityRequirement`
    30	  entries, calls `planRender()`, and returns a planner-backed route decision.
    31	- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
    32	  readiness reducer. It consumes timeline snapshot requirements, explicit
    33	  requirements, output format descriptors, process descriptors, shader
    34	  descriptors, material refs/statuses, render groups, request constraints, and
    35	  diagnostics, then returns route plans, blockers, diagnostics, next actions,
    36	  and `canBrowserExport`/`canWorkerExport`.
    37	
    38	## Render Planner Participation Contract
    39	
    40	Any Phase 4 family that can affect preview, export, generated artifacts, or
    41	determinism must participate in planning through stable capability metadata
    42	before it can be promoted to public support.
    43	
    44	Required contract:
    45	
    46	1. Each promoted family must expose provider-free planner inspection data. The
    47	   planner must not import live registries, component implementations, provider
    48	   stores, or extension package handles.
    49	2. Each render-relevant contribution must declare one or more route-level
    50	   `CapabilityRequirement` records or a descriptor that `planRender()` can
    51	   convert into equivalent requirements.
    52	3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
    53	   process-dependent, missing-contribution, and route-unsupported states must
    54	   produce actionable `RenderBlocker` records rather than silent fallback.
    55	4. Route decisions must remain planner-backed. For clip routing,
    56	   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
    57	   allows browser export only when the contribution explicitly declares a
    58	   supported browser-export capability, and blocks worker conflicts for
    59	   contributed code.
    60	5. Output-format and process families must keep using planner descriptors
    61	   rather than invoking providers directly from the planner. Current
    62	   `extensionSurface.ts` output-format descriptors are the model: route
    63	   requirements, process requirements, blockers, next actions, sidecars, and
    64	   capability metadata are data, not execution.
    65	6. Shader and render-material families must distinguish preview from export.
    66	   Current `renderPlanner.ts` shader materializer handling discovers
    67	   materializer routes, emits process-dependent blockers/next actions, and
    68	   keeps unresolved material refs from silently exporting.
    69	7. Diagnostics published from planner findings must remain source-scoped so
    70	   Extension Manager and diagnostics surfaces can show package/family blockers
    71	   without confusing them with extension-authored runtime diagnostics.
    72	
    73	Promotion is blocked for any family whose content can render, mutate timeline
    74	state, invoke processes, consume live data, or produce export artifacts without
    75	planner-visible requirements and failure states.
   105	| Runtime normalization | `extensionSurface.ts` or the owning runtime module converts manifest declarations into immutable provider-scoped descriptors with extension ID, contribution ID, order, disabled state, and diagnostics. |
   106	| Lifecycle cleanup | Disable/unload unregisters renderers, commands, keybindings, diagnostics, settings-derived UI state, live channels, process handles, or shader resources owned by the extension. |
   107	| Persistence posture | Any persisted state has provider-backed semantics or an explicit unsupported diagnostic. Settings/proposals must survive reload only where providers claim conformance. |
   108	| Settings/parameters | Parameter schemas render through SchemaForm or an equivalent host-owned primitive, with unsupported shapes diagnosed and non-corrupting. |
   109	| Diagnostics | Loader, runtime, planner, and extension-authored diagnostics are scoped by extension ID and contribution ID where applicable, bounded, and cleaned up. |
   110	| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
   111	| UI integration | Picker, inspector, manager, diagnostics, empty/loading/error/disabled states, and provenance labels are present where the family is visible. |
   112	| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
   113	| Docs/examples | Authoring, loading, compatibility, examples, and release gates agree on support status and trust posture. |
   114	
   115	Family-specific readiness:
   116	
   117	| Family | Minimum readiness before support |
   118	| --- | --- |
   119	| Asset parser | Permission/declaration checks, parser failure diagnostics, safe asset metadata enrichment, query/filter API boundaries, and export/bake posture. |
   120	| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
   121	| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
   122	| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
   123	| Keyframes | Minimal model, commands/proposals, migration, interpolation tests, and deterministic preview/export delivery. |
   124	| Agent tool | Proposal-first destructive behavior, backend dispatch registry, permission declarations, result-family validation, persisted proposals, and disabled/failure diagnostics. |
   125	| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
   126	| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
   127	| Process/sidecar | Trusted local process model, command/env/cwd policy, JSON-RPC protocol, health/log/cancel/shutdown behavior, manager health UI, and explicit trust warnings. |
   128	| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |
   129	
   130	## Roadmap And Ticket Reconciliation

 succeeded in 0ms:
     1	/**
     2	 * Shared renderability and artifact vocabulary for provider-scoped
     3	 * registries and export-readiness planning.
     4	 *
     5	 * These contracts are intentionally data-only. Registries own lifecycle and
     6	 * snapshots, export guards produce findings/blockers, and later planners can
     7	 * aggregate the same records without renaming fields.
     8	 */
     9	
    10	/** Routes that a contribution may support when previewing or exporting. */
    11	export type RenderRoute = 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';
    12	
    13	/** Locked render route vocabulary shared by registries, guards, and planners. */
    14	export const RENDER_ROUTES = [
    15	  'preview',
    16	  'browser-export',
    17	  'worker-export',
    18	  'sidecar-export',
    19	] as const satisfies readonly RenderRoute[];
    20	Object.freeze(RENDER_ROUTES);
    21	
    22	/**
    23	 * Determinism posture for a contribution, material, artifact, or bake.
    24	 *
    25	 * - `deterministic`: same inputs are expected to produce equivalent outputs.
    26	 * - `preview-only`: usable only for interactive preview, not authoritative export.
    27	 * - `live-unbaked`: depends on live provider/runtime state until materialized.
    28	 * - `process-dependent`: depends on external process/tool versions or sidecars.
    29	 * - `unknown`: insufficient metadata; guards should stay conservative.
    30	 */
    31	export type DeterminismStatus =
    32	  | 'deterministic'
    33	  | 'preview-only'
    34	  | 'live-unbaked'
    35	  | 'process-dependent'
    36	  | 'unknown';
    37	
    38	/** Locked determinism vocabulary shared across registry records and artifacts. */
    39	export const DETERMINISM_STATUSES = [
    40	  'deterministic',
    41	  'preview-only',
    42	  'live-unbaked',
    43	  'process-dependent',
    44	  'unknown',
    45	] as const satisfies readonly DeterminismStatus[];
    46	Object.freeze(DETERMINISM_STATUSES);
    47	
    48	/** Stable blocker reasons emitted by early guards and later planner aggregation. */
    49	export type RenderBlockerReason =
    50	  | 'missing-contribution'
    51	  | 'route-unsupported'
    52	  | 'preview-only'
    53	  | 'live-unbaked'
    54	  | 'process-dependent'
    55	  | 'missing-material'
    56	  | 'materialization-failed'
    57	  | 'inactive-extension'
    58	  | 'unknown';
    59	
    60	/** Locked blocker reason vocabulary for planner-compatible records. */
    61	export const RENDER_BLOCKER_REASONS = [
    62	  'missing-contribution',
    63	  'route-unsupported',
    64	  'preview-only',
    65	  'live-unbaked',
    66	  'process-dependent',
    67	  'missing-material',
    68	  'materialization-failed',
    69	  'inactive-extension',
    70	  'unknown',
    71	] as const satisfies readonly RenderBlockerReason[];
    72	Object.freeze(RENDER_BLOCKER_REASONS);
    73	
    74	export type RenderCapabilityStatus = 'supported' | 'blocked' | 'unknown';
    75	
    76	/** Per-route capability advertised by a registry record or derived guard scan. */
    77	export interface RenderCapability {
    78	  readonly route: RenderRoute;
    79	  readonly status: RenderCapabilityStatus;
    80	  readonly determinism: DeterminismStatus;
    81	  readonly blockerReason?: RenderBlockerReason;
    82	  readonly message?: string;
    83	}
    84	
    85	/** Renderability summary carried by provider-scoped registry records. */
    86	export interface ContributionRenderability {
    87	  readonly capabilities: readonly RenderCapability[];
    88	  readonly defaultRoute?: RenderRoute;
    89	  readonly determinism: DeterminismStatus;
    90	  readonly blockers?: readonly RenderBlocker[];
    91	}
    92	
    93	export type CapabilityFindingSeverity = 'error' | 'warning' | 'info';
    94	
    95	/** Planner-compatible finding record emitted by guards, registries, or loaders. */
    96	export interface CapabilityFinding {
    97	  readonly id: string;
    98	  readonly severity: CapabilityFindingSeverity;
    99	  readonly route?: RenderRoute;
   100	  readonly reason?: RenderBlockerReason;
   101	  readonly message: string;
   102	  readonly extensionId?: string;
   103	  readonly contributionId?: string;
   104	  readonly clipId?: string;
   105	  readonly materialRefId?: string;
   455	  /** MIME type of the output. */
   456	  readonly mimeType: string;
   457	  /** Suggested filename for the output. */
   458	  readonly filename: string;
   459	  /** Output format contribution ID, when the artifact came from a format handler. */
   460	  readonly outputFormatId?: string;
   461	  /** Extension that produced the output. */
   462	  readonly producerExtensionId?: string;
   463	  /** Extension version, if available. */
   464	  readonly producerVersion?: string;
   465	  /** Sidecars emitted by the output handler or producer. */
   466	  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
   467	  /** Optional provenance carried into the artifact manifest. */
   468	  readonly provenance?: Record<string, unknown>;
   469	  /** Optional input hash map carried into the artifact manifest. */
   470	  readonly inputHashes?: Record<string, string>;
   471	  /** Optional stable metadata carried into the artifact manifest. */
   472	  readonly metadata?: Record<string, unknown>;
   473	  /** Asset keys consumed from the registry during compilation. */
   474	  readonly consumedAssetKeys?: readonly string[];
   475	  /**
   476	   * Diagnostics produced during compilation.
   477	   * Error-severity diagnostics that are blocking will be surfaced in findings.
   478	   */
   479	  readonly diagnostics?: readonly {
   480	    severity: 'error' | 'warning' | 'info';
   481	    code: string;
   482	    message: string;
   483	    assetKey?: string;
   484	    extensionId?: string;
   485	    contributionId?: string;
   486	    detail?: Record<string, unknown>;
   487	  }[];
   488	  /** Whether the compilation produced blocking errors. */
   489	  readonly hasBlockingErrors?: boolean;
   490	}
   491	
   492	/**
   493	 * Create a deterministic {@link RenderArtifact} from a compile-only output
   494	 * execution result.
   495	 *
   496	 * Compile-only artifacts are always marked `deterministic` because they
   497	 * are produced from read-only timeline + asset data without external
   498	 * processes, render providers, or media render routes.
   499	 */
   500	export function createCompileOnlyArtifact(params: CompileOnlyArtifactParams): RenderArtifact {
   501	  const findings: CapabilityFinding[] = [];
   502	
   503	  // Convert diagnostics to findings
   504	  for (const diag of params.diagnostics ?? []) {
   505	    findings.push({
   506	      id: `compile-only.${params.artifactId}.${diag.code}`,
   507	      severity: diag.severity === 'error' ? 'error' : diag.severity === 'warning' ? 'warning' : 'info',
   508	      route: COMPILE_ONLY_ARTIFACT_ROUTE,
   509	      reason: diag.severity === 'error' ? 'unknown' : undefined,
   510	      message: diag.message,
   511	      extensionId: diag.extensionId ?? params.producerExtensionId,
   512	      contributionId: diag.contributionId,
   513	      detail: diag.detail,
   514	    });
   515	  }
   516	
   517	  // Build consumed material refs from asset keys
   518	  const consumedMaterialRefs: RenderMaterialRef[] = (params.consumedAssetKeys ?? []).map((key) => ({
   519	    id: `material.asset.${key}`,
   520	    mediaKind: 'unknown',
   521	    locator: {
   522	      kind: 'asset-registry',
   523	      uri: `asset://${key}`,
   524	    },
   525	    determinism: 'deterministic',

exec
/bin/zsh -lc "nl -ba docs/video-editor/extensions-debugging.md | sed -n '150,176p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   150	## 5. Export guard diagnostics
   151	
   152	### 5.1 Pre-render scan
   153	
   154	Before render, `runExportGuard()` scans the timeline config for:
   155	
   156	| Condition | Severity | Code | Blocks export? |
   157	|---|---|---|---|
   158	| Unknown clip type (no declaring extension) | `error` | `export/unknown-clip-type` | Yes |
   159	| Unknown effect (no declaring extension) | `error` | `export/unknown-effect` | Yes |
   160	| Unknown transition (no declaring extension) | `error` | `export/unknown-transition` | Yes |
   161	| Extension-declared ID from **inactive** contribution | `warning` | `export/missing-extension` | No (render proceeds) |
   162	| Missing render materializer for shader | `error` | `export/shader-no-materializer` | Yes |
   163	
   164	**Evidence:** [Author Contract §6.2](./extension-author-contract.md#62-export-guard-integration) (S-062); `runExportGuard()` in `src/tools/video-editor/runtime/renderability.ts` (CR:M5-005).
   165	
   166	### 5.2 Missing extension references
   167	
   168	When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does **not** block render. Unknown clip types from missing extensions produce `export/unknown-clip-type` separately.
   169	
   170	**Evidence:** [Provider Compatibility Matrix §3.5](./provider-compatibility-matrix.md#35-missing-extension-references) — all three providers handle this identically.
   171	
   172	### 5.3 Debugging export blockages
   173	
   174	1. Check the export guard diagnostics in the DiagnosticPanel.
   175	2. Verify that all clip types, effects, and transitions used in the timeline are declared in an active extension's manifest `contributions`.
   176	3. If a contribution is declared but the extension is inactive, you'll see `export/missing-extension` (warning). Activate the extension to clear it.

exec
/bin/zsh -lc "sed -n '1,220p' /Users/peteromalley/Documents/poms_skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
---
name: contextminning-subagentmaxxing
description: >
  Keep the main-thread context as lean as possible while working. Two moves: (1)
  context minning — after each turn, look for a natural break-off point to condense,
  save state to markdown, and compact - write .md docs to make sure you don't lose 
  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
  a subagent (especially the DeepSeek/Kimi agents via subagent-launcher) should research,
  validate, or execute it so the verbose work never lands in your context. Use on 
  any long, multi-step, or research-heavy task.
---

# Context Minning & Subagent Maxxing

The goal of this skill is singular: **keep the actual work in the main thread's
context as small as possible.** Long contexts get slow, expensive, and forgetful.
Every turn, the most useful tokens should be present and the rest should be
elsewhere — in a file, in a summary, or in a subagent that already finished.

It runs as two continuous moves — a posture, not a one-time cleanup. This file is the
philosophy and the high level; each move has a standalone skill with the mechanics,
syntax, and anti-patterns. **Invoke those for the how.**

---

## Move 1 — Context minning: condense at the seams

When a chunk of work becomes *done and durable* — a plan spec'd out, a bug
root-caused, a long read distilled to one answer — the path to that conclusion is dead
weight. At those seams: **write the conclusion to a durable artifact, then compact from
there.** Prefer landing real work as a megaplan asset (plan file or ticket) over a loose
note, so what you shed becomes trackable work rather than vanishing.

The discipline is *write it down first* — you can only safely forget what you can
re-read. And don't over-do it: compact at seams, never on a timer; a slightly long
context costs less than a lost decision.

→ **`minimize-context`** for the seam catalogue, the `/compact` · `/clear` · `/context`
mechanics, megaplan-asset detail, and the over-minning failure mode.

→ **`context-usage`** to *see* the context filling: a turn-by-turn token-growth chart
read from the session transcript, with every compaction boundary marked. Use it to
check whether you're minning at the right seams or letting context balloon to
auto-compaction. (`/context` is the live snapshot; `context-usage` is the trajectory.)

## Move 2 — Subagent maxxing: do the work elsewhere

**Default to doing work in a subagent, not the thread.** Flip the question from "should
a subagent do this?" to "is there any reason this *can't*?" Its tool calls, file reads,
and reasoning stay in *its* context; only the conclusion returns to you. **Execution is
the headline case** — implementing, investigating, building is where byproduct piles up,
so it's the first thing to hand off, not the last. Be willing to launch **many**, even
in parallel, until you have clarity — that's cheaper than carrying the trail inline.

Two principles carry most of the value: spend the subagent on the *byproduct-heavy*
part and ask it to **return the conclusion, not the trail**; and **use the cheapest
model that can do the job** (cheap scan-work → reasoning → frontier only for real
complexity), preparing the context well enough that a cheaper tier can win. Don't
dispatch if you already have the answer.

**Match the venue to the scale.** A one-shot subagent dispatch is for ad-hoc work —
research, a sense-check, a contained fix. Once something is more than ~a day or two of
work it's a *deliverable*: run it as a **megaplan** (itself launched in a subagent) and
use **`megaplan-decision`** to size the tier/robustness/depth. Past ~2 weeks → an epic.

→ **`subagent-launcher`** for the pathways, the cost-escalation ladder with model
identifiers, and how to shape a self-contained subagent prompt.

---

## The loop, in one line

Every turn: *Did I just hit a seam? → write it down, compact. Am I about to do real
work? → hand it to a subagent.* Keep the main thread holding only what the next
decision needs.

codex
I read the context-mining skill after the initial targeted pass. I’m not dispatching a subagent now because the requested scope is narrow, read-only, and the relevant facts are already localized; the remaining work is synthesis rather than another broad search.
codex
# Export Readiness Convergence

## Verdict

The criticism is valid. Severity: medium-high.

Planner blockers are now the intended canonical vocabulary, but export readiness is still assembled through a compatibility layer plus legacy route decisions. The user can still see “supported” from one layer and “blocked/unavailable” from another.

## Current Code Reality

The shared vocabulary is in [renderability.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderability.ts:10): planner routes are `preview`, `browser-export`, `worker-export`, `sidecar-export`; blocker reasons are stable values like `missing-contribution`, `route-unsupported`, `preview-only`, `live-unbaked`, `process-dependent`, `missing-material`.

`planRender()` is the real reducer. It consumes requirements, output formats, processes, shaders, materials, render groups, request constraints, and diagnostics, then returns route plans plus `canBrowserExport`/`canWorkerExport` from route blockers: [renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:930), [renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:984).

Render starts currently gate through `runExportGuard()`, which scans registry state and timeline config, then converts guard output into planner diagnostics. The hook explicitly says planner blockers are canonical: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:377), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:388).

But after that, render still uses legacy provider routing. `getFastRenderRouteDecision()` can return `preview-only` for missing generated-module artifacts before `decideRenderRoute()` runs: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:44). Then user-visible errors are produced from `decision.reason`, not planner blockers: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:426).

`renderRouter.ts` is planner-backed, but it has its own provider route taxonomy and reason strings: `browser-remotion`, `worker-banodoco`, `preview-only`, `external`; reasons like `contributed_blocked_no_browser_capability`: [renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:67), [renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:303).

Compile-only export is closer: it calls `planRender()` for output format availability and uses blocker messages: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:514). But it still runs `runExportGuard()` separately and can also fail on handler registry availability outside planner vocabulary: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:559), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:572).

## Pristine End State

One exported readiness API should answer: requested output, candidate routes, selected route, blockers, warnings, next actions.

Everything render-relevant should feed `planRender()` as data: timeline requirements, registry renderability, missing IDs, live bindings, shader materialization, output formats, process health, route/provider availability, generated-module artifact state, compile-only handler availability.

`ExportDiagnostic` should become a presentation artifact derived from planner findings, not an independent gate. Legacy `export/*` codes can remain for UI compatibility, but they should not decide readiness.

Provider routing should select from unblocked `routePlans`. If no actual provider exists for an otherwise supported route, that is a planner blocker, not `Worker render unavailable for route "themed_only"`.

## Recommended Work

Now:

1. Add a `buildExportReadinessPlan()` wrapper near `renderPlanner.ts` or `useRenderState.ts` that performs today’s guard scan but returns only `RenderPlannerResult` plus derived diagnostics. Replace `runExportGuard(): boolean` with “get plan, block on selected route blockers.”

2. Move `getFastRenderRouteDecision()` generated-module artifact failures into planner requirements/blockers. The hook should not invent `preview-only` user messages.

3. Change render blocking UI to display the first selected route planner blocker message, with `reason`, `route`, and next actions. Keep `decision.reason` for analytics/debug only.

4. Update docs that still tell users to debug “export guard diagnostics” first. [extensions-debugging.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/docs/video-editor/extensions-debugging.md:150) is stale and even names codes that differ from current code.

Later:

5. Collapse export guard into planner input builders, or rename it to a scanner/adapter so it no longer looks authoritative.

6. Make `renderRouter` return planner route IDs plus provider IDs separately. Provider ID is execution detail; route readiness is planner state.

7. Decide post-execution semantics for compile-only `hasBlockingErrors`; “Export complete (with blocking errors)” is not a clean readiness story.

## Tests / Gates

Add tests that fail if user-visible render/export blocked messages do not originate from a `RenderBlocker`.

Expand `useRenderState.test.tsx` around generated-module missing artifact, worker unavailable, contributed clip conflicts, unknown effect/transition/clip, shader materializer, live binding, output format disabled/missing, and missing compile-only handler.

Add `renderRouter.test.ts` assertions that every `preview-only` decision carries route blockers with stable planner reasons.

Add docs checks for stale `export/unknown-effect`, `export/unknown-transition`, `export/shader-no-materializer` references.

## Biggest Trap

The tempting wrong move is deleting `exportGuard` or making `hasBlockingErrors` the planner gate. The guard still owns important scans. The right move is to keep those scans, but demote them into planner input so only route-scoped `RenderBlocker`s decide readiness.
tokens used
134,575
# Export Readiness Convergence

## Verdict

The criticism is valid. Severity: medium-high.

Planner blockers are now the intended canonical vocabulary, but export readiness is still assembled through a compatibility layer plus legacy route decisions. The user can still see “supported” from one layer and “blocked/unavailable” from another.

## Current Code Reality

The shared vocabulary is in [renderability.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderability.ts:10): planner routes are `preview`, `browser-export`, `worker-export`, `sidecar-export`; blocker reasons are stable values like `missing-contribution`, `route-unsupported`, `preview-only`, `live-unbaked`, `process-dependent`, `missing-material`.

`planRender()` is the real reducer. It consumes requirements, output formats, processes, shaders, materials, render groups, request constraints, and diagnostics, then returns route plans plus `canBrowserExport`/`canWorkerExport` from route blockers: [renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:930), [renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:984).

Render starts currently gate through `runExportGuard()`, which scans registry state and timeline config, then converts guard output into planner diagnostics. The hook explicitly says planner blockers are canonical: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:377), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:388).

But after that, render still uses legacy provider routing. `getFastRenderRouteDecision()` can return `preview-only` for missing generated-module artifacts before `decideRenderRoute()` runs: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:44). Then user-visible errors are produced from `decision.reason`, not planner blockers: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:426).

`renderRouter.ts` is planner-backed, but it has its own provider route taxonomy and reason strings: `browser-remotion`, `worker-banodoco`, `preview-only`, `external`; reasons like `contributed_blocked_no_browser_capability`: [renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:67), [renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:303).

Compile-only export is closer: it calls `planRender()` for output format availability and uses blocker messages: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:514). But it still runs `runExportGuard()` separately and can also fail on handler registry availability outside planner vocabulary: [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:559), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:572).

## Pristine End State

One exported readiness API should answer: requested output, candidate routes, selected route, blockers, warnings, next actions.

Everything render-relevant should feed `planRender()` as data: timeline requirements, registry renderability, missing IDs, live bindings, shader materialization, output formats, process health, route/provider availability, generated-module artifact state, compile-only handler availability.

`ExportDiagnostic` should become a presentation artifact derived from planner findings, not an independent gate. Legacy `export/*` codes can remain for UI compatibility, but they should not decide readiness.

Provider routing should select from unblocked `routePlans`. If no actual provider exists for an otherwise supported route, that is a planner blocker, not `Worker render unavailable for route "themed_only"`.

## Recommended Work

Now:

1. Add a `buildExportReadinessPlan()` wrapper near `renderPlanner.ts` or `useRenderState.ts` that performs today’s guard scan but returns only `RenderPlannerResult` plus derived diagnostics. Replace `runExportGuard(): boolean` with “get plan, block on selected route blockers.”

2. Move `getFastRenderRouteDecision()` generated-module artifact failures into planner requirements/blockers. The hook should not invent `preview-only` user messages.

3. Change render blocking UI to display the first selected route planner blocker message, with `reason`, `route`, and next actions. Keep `decision.reason` for analytics/debug only.

4. Update docs that still tell users to debug “export guard diagnostics” first. [extensions-debugging.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/docs/video-editor/extensions-debugging.md:150) is stale and even names codes that differ from current code.

Later:

5. Collapse export guard into planner input builders, or rename it to a scanner/adapter so it no longer looks authoritative.

6. Make `renderRouter` return planner route IDs plus provider IDs separately. Provider ID is execution detail; route readiness is planner state.

7. Decide post-execution semantics for compile-only `hasBlockingErrors`; “Export complete (with blocking errors)” is not a clean readiness story.

## Tests / Gates

Add tests that fail if user-visible render/export blocked messages do not originate from a `RenderBlocker`.

Expand `useRenderState.test.tsx` around generated-module missing artifact, worker unavailable, contributed clip conflicts, unknown effect/transition/clip, shader materializer, live binding, output format disabled/missing, and missing compile-only handler.

Add `renderRouter.test.ts` assertions that every `preview-only` decision carries route blockers with stable planner reasons.

Add docs checks for stale `export/unknown-effect`, `export/unknown-transition`, `export/shader-no-materializer` references.

## Biggest Trap

The tempting wrong move is deleting `exportGuard` or making `hasBlockingErrors` the planner gate. The guard still owns important scans. The right move is to keep those scans, but demote them into planner input so only route-scoped `RenderBlocker`s decide readiness.
