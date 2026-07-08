import type {
  CompositionGraph,
  CompositionGraphEdge,
  CompositionGraphNode,
  CompositionReferenceStateEntry,
  ContributionRef,
  ExtensionDiagnostic,
  RenderArtifact,
  ReferenceState,
  TimelineEffectSummary,
  TimelineShaderSummary,
  TimelineSnapshot,
  TimelineTransitionSummary,
} from '@reigh/editor-sdk';
import { contributionRefKey } from '@reigh/editor-sdk';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type { HostMaterialRuntimeProjection } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  buildCompositionDiagnostic,
  COMPOSITION_DIAGNOSTIC_CODE,
  type CompositionDiagnosticCode,
  referenceStateToEffectDiagnosticCode,
  referenceStateToTransitionDiagnosticCode,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import {
  resolveCompositionReferences,
  resolveReferenceStateFromEntries,
  type CompositionReferenceUsage,
} from '@/tools/video-editor/runtime/composition/referenceResolver.ts';
import { validateShaderComposition } from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorRouteRequirementDescriptor,
  VideoEditorProcessRequirementDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export const TIMELINE_POSTPROCESS_NODE_ID = 'timeline-postprocess';

export interface CompositionGraphRuntimeOverlay {
  readonly shaders?: readonly TimelineShaderSummary[];
}

export interface CompositionGraphPatchOverlay {
  readonly shaders?: readonly TimelineShaderSummary[];
}

export interface CompositionGraphMaterialSlotOwnerIdentity {
  readonly kind: 'effect' | 'transition';
  readonly clipId: string;
  readonly ownerId: string;
}

export interface CompositionGraphMaterialSlotDeclaration {
  readonly owner: CompositionGraphMaterialSlotOwnerIdentity;
  readonly slotName: string;
}

export interface CompositionGraphMaterialSlotBinding {
  readonly owner: CompositionGraphMaterialSlotOwnerIdentity;
  readonly slotName: string;
  readonly materialRefId: string;
}

export interface CompositionGraphMediaTrackOwnerIdentity {
  readonly kind: 'track';
  readonly trackId: string;
  readonly clipId?: string;
}

export interface CompositionGraphMediaTrackBinding {
  readonly owner: CompositionGraphMediaTrackOwnerIdentity;
  readonly artifactId: string;
}

// ---------------------------------------------------------------------------
// M5: Effect / transition contribution lookup helpers
// ---------------------------------------------------------------------------

/** Resolved effect or transition contribution lookup result. */
export interface EffectTransitionContributionLookup {
  readonly ref: ContributionRef;
  readonly refKey: string;
  readonly entry: ContributionIndexEntry;
}

/**
 * Resolve an effect or transition timeline summary against the contribution
 * index using a tiered lookup strategy.
 *
 * Primary: match by `(kind, managedBy?, renderId?)`.
 *   - Filters index entries where `entry.kind === kind`.
 *   - If `managedBy` is set, requires `entry.extensionId === managedBy`.
 *   - If `renderId` is set, requires `entry.renderId === renderId`.
 *   - Returns the entry when exactly one matches.
 *
 * Fallback: match by contribution ID only (unambiguous).
 *   - Filters index entries where `entry.kind === kind` AND
 *     `entry.contributionId === contributionId`.
 *   - Returns the entry only when exactly one matches; ambiguous or
 *     zero matches return `undefined`.
 *
 * Graph node IDs remain keyed by {@link ContributionRef} identity
 * (`contribution:<refKey>`).
 */
export function resolveEffectTransitionContributionEntry(
  kind: 'effect' | 'transition',
  managedBy: string | undefined,
  renderId: string | undefined,
  contributionId: string | undefined,
  contributionIndex: ContributionIndex | undefined,
): EffectTransitionContributionLookup | undefined {
  if (!contributionIndex) {
    return undefined;
  }

  const allEntries: readonly ContributionIndexEntry[] = Object.values(
    contributionIndex as Record<string, readonly ContributionIndexEntry[]>,
  ).flat();

  // ---- Primary: (kind, managedBy?, renderId?) -----------------------
  // Primary only activates when at least one identity-bearing filter
  // (managedBy or renderId) is supplied.  A bare kind match is too broad
  // and would incorrectly grab the sole entry of that kind regardless of
  // whether the contribution ID aligns with the timeline summary.
  const hasPrimaryCriteria = managedBy !== undefined || renderId !== undefined;

  let primaryMatches: readonly ContributionIndexEntry[] = [];
  if (hasPrimaryCriteria) {
    primaryMatches = allEntries.filter((entry) => {
      if (entry.kind !== kind) return false;
      if (managedBy !== undefined && entry.extensionId !== managedBy) return false;
      if (renderId !== undefined && entry.renderId !== renderId) return false;
      return true;
    });
  }

  if (primaryMatches.length === 1) {
    const entry = primaryMatches[0]!;
    const ref = createContributionRef(entry);
    return { ref, refKey: contributionRefKey(ref), entry };
  }

  // ---- Fallback: contribution ID only (unambiguous) -----------------
  if (contributionId !== undefined) {
    const fallbackMatches = allEntries.filter((entry) => {
      if (entry.kind !== kind) return false;
      if (entry.contributionId !== contributionId) return false;
      return true;
    });

    if (fallbackMatches.length === 1) {
      const entry = fallbackMatches[0]!;
      const ref = createContributionRef(entry);
      return { ref, refKey: contributionRefKey(ref), entry };
    }
  }

  return undefined;
}

/**
 * Convenience wrapper that resolves a {@link TimelineEffectSummary}
 * through {@link resolveEffectTransitionContributionEntry}.
 */
export function resolveEffectContributionEntry(
  effect: TimelineEffectSummary,
  contributionIndex: ContributionIndex | undefined,
  renderId?: string,
): EffectTransitionContributionLookup | undefined {
  const resolvedRenderId = renderId ?? effect.effectType;
  return resolveEffectTransitionContributionEntry(
    'effect',
    effect.managedBy,
    resolvedRenderId,
    effect.effectType,
    contributionIndex,
  );
}

/**
 * Convenience wrapper that resolves a {@link TimelineTransitionSummary}
 * through {@link resolveEffectTransitionContributionEntry}.
 */
export function resolveTransitionContributionEntry(
  transition: TimelineTransitionSummary,
  contributionIndex: ContributionIndex | undefined,
  renderId?: string,
): EffectTransitionContributionLookup | undefined {
  const resolvedRenderId = renderId ?? transition.transitionType;
  return resolveEffectTransitionContributionEntry(
    'transition',
    transition.managedBy,
    resolvedRenderId,
    transition.transitionType,
    contributionIndex,
  );
}

export interface CompositionGraphInput {
  readonly snapshot: TimelineSnapshot;
  readonly contributionIndex: ContributionIndex | undefined;
  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
  readonly processes?: readonly VideoEditorProcessDescriptor[];
  readonly artifacts?: readonly RenderArtifact[];
  readonly clipTypeRegistry?: ClipTypeRegistrySnapshot;
  readonly runtimeOverlay?: CompositionGraphRuntimeOverlay;
  readonly patchOverlay?: CompositionGraphPatchOverlay;
  readonly materialRuntime?: HostMaterialRuntimeProjection;
  readonly materialSlotDeclarations?: readonly CompositionGraphMaterialSlotDeclaration[];
  readonly materialSlotBindings?: readonly CompositionGraphMaterialSlotBinding[];
  readonly mediaTrackBindings?: readonly CompositionGraphMediaTrackBinding[];
}

const EMPTY_NODES: readonly CompositionGraphNode[] = Object.freeze([]);
const EMPTY_EDGES: readonly CompositionGraphEdge[] = Object.freeze([]);
const EMPTY_DIAGNOSTICS: readonly ExtensionDiagnostic[] = Object.freeze([]);
const EMPTY_SHADERS: readonly TimelineShaderSummary[] = Object.freeze([]);
const EMPTY_REFERENCE_STATES: readonly CompositionReferenceStateEntry[] = Object.freeze([]);
const EMPTY_CONTRIBUTION_INDEX_ENTRIES: readonly ContributionIndexEntry[] = Object.freeze([]);

interface EffectTransitionReferenceUsage {
  readonly kind: 'effect' | 'transition';
  readonly nodeId: string;
  readonly clipId: string;
  readonly scope: 'clip';
  readonly contributionId?: string;
  readonly managedBy?: string;
  readonly ownerKind: 'effect' | 'transition';
  readonly ownerId: string;
  readonly materialSlot?: string;
  readonly materialRefId?: string;
  readonly targetPath?: string;
}

interface ResolvedEffectTransitionReferenceUsage {
  readonly ref?: ContributionRef;
  readonly refKey?: string;
  readonly state: ReferenceState;
  readonly packageState?: string;
}

function clipNodeId(clipId: string): string {
  return `clip:${clipId}`;
}

function contributionNodeId(ref: ContributionRef): string {
  return `contribution:${contributionRefKey(ref)}`;
}

function createContributionRef(
  entry: Pick<ContributionIndexEntry, 'kind' | 'extensionId' | 'contributionId'>,
): ContributionRef {
  return {
    kind: entry.kind,
    extensionId: entry.extensionId,
    contributionId: entry.contributionId,
  };
}

function ensureContributionNode(
  nodes: CompositionGraphNode[],
  contributionNodeByRefKey: Map<string, CompositionGraphNode>,
  ref: ContributionRef,
  refKey: string,
): CompositionGraphNode {
  let contributionNode = contributionNodeByRefKey.get(refKey);
  if (!contributionNode) {
    contributionNode = Object.freeze({
      id: contributionNodeId(ref),
      kind: 'contribution' as const,
      ref,
    });
    contributionNodeByRefKey.set(refKey, contributionNode);
    nodes.push(contributionNode);
  }

  return contributionNode;
}

function resolveContributionEntryByKindAndPredicate(
  kind: string,
  contributionEntries: readonly (readonly [string, readonly ContributionIndexEntry[]])[],
  predicate: (entry: ContributionIndexEntry) => boolean,
): ContributionIndexEntry | undefined {
  let matched: ContributionIndexEntry | undefined;

  for (const [, entries] of contributionEntries) {
    for (const entry of entries) {
      if (entry.kind !== kind || !predicate(entry)) {
        continue;
      }

      if (matched && matched.scopedKey !== entry.scopedKey) {
        return undefined;
      }

      matched = entry;
    }
  }

  return matched;
}

function processContributionRef(
  processRequirement: Readonly<{
    processId: string;
  }>,
  processes: readonly VideoEditorProcessDescriptor[] | undefined,
  contributionEntries: readonly (readonly [string, readonly ContributionIndexEntry[]])[],
): ContributionRef | undefined {
  const descriptor = processes?.find((candidate) => candidate.processId === processRequirement.processId);
  if (descriptor) {
    return {
      kind: 'process',
      extensionId: descriptor.extensionId,
      contributionId: descriptor.id,
    };
  }

  const entry = resolveContributionEntryByKindAndPredicate(
    'process',
    contributionEntries,
    (candidate) =>
      candidate.renderId === processRequirement.processId
      || candidate.contributionId === processRequirement.processId,
  );
  return entry ? createContributionRef(entry) : undefined;
}

function routeRequirementDetail(
  outputFormat: VideoEditorOutputFormatDescriptor,
  refKey: string,
  requirement: VideoEditorRouteRequirementDescriptor,
  requirementKind: 'route' | 'shader' | 'clip' | 'timeline-postprocess',
): Record<string, unknown> {
  return Object.freeze({
    outputFormatId: outputFormat.id,
    outputLabel: outputFormat.label,
    refKey,
    requirementKind,
    routes: Object.freeze([...requirement.routes]),
    routeScope: Object.freeze({
      source: requirement.routeScope.source,
      mode: requirement.routeScope.mode,
      routes: Object.freeze([...requirement.routeScope.routes]),
    }),
    requiredCapabilities: Object.freeze([...requirement.requiredCapabilities]),
    determinism: requirement.determinism,
    ...(requirement.processId ? { processId: requirement.processId } : {}),
    ...(requirement.operationId ? { operationId: requirement.operationId } : {}),
    ...(requirement.unavailableMessage ? { unavailableMessage: requirement.unavailableMessage } : {}),
  });
}

function processRequirementDetail(
  outputFormat: VideoEditorOutputFormatDescriptor,
  refKey: string,
  requirement: VideoEditorProcessRequirementDescriptor,
): Record<string, unknown> {
  return Object.freeze({
    outputFormatId: outputFormat.id,
    outputLabel: outputFormat.label,
    refKey,
    requirementKind: 'process',
    processId: requirement.processId,
    ...(requirement.operationId ? { operationId: requirement.operationId } : {}),
    routeScope: Object.freeze({
      source: requirement.routeScope.source,
      mode: requirement.routeScope.mode,
      routes: Object.freeze([...requirement.routeScope.routes]),
    }),
    requiredCapabilities: Object.freeze([...requirement.requiredCapabilities]),
  });
}

function materialDependencyDetail(
  outputFormat: VideoEditorOutputFormatDescriptor,
  refKey: string,
  material: HostMaterialRuntimeProjection['materials'][number],
  producerRefKey: string | undefined,
): Record<string, unknown> {
  return Object.freeze({
    outputFormatId: outputFormat.id,
    outputLabel: outputFormat.label,
    refKey,
    consumedKind: 'material',
    materialRefId: material.materialRef.id,
    materialMediaKind: material.materialRef.mediaKind,
    determinism: material.materialRef.determinism,
    routeScopes: Object.freeze(material.routeScopes.map((scope) => Object.freeze({
      route: scope.route,
      fit: scope.fit,
      sensitivity: scope.sensitivity,
    }))),
    ...(producerRefKey ? { producerRefKey } : {}),
    ...(material.descriptorFacts.process?.processId
      ? { processId: material.descriptorFacts.process.processId }
      : {}),
    ...(material.descriptorFacts.process?.operationId
      ? { operationId: material.descriptorFacts.process.operationId }
      : {}),
  });
}

function resolveMaterialDependencyTargetRef(
  material: HostMaterialRuntimeProjection['materials'][number],
  processes: readonly VideoEditorProcessDescriptor[] | undefined,
  contributionEntries: readonly (readonly [string, readonly ContributionIndexEntry[]])[],
): ContributionRef | undefined {
  const contributionScopedKey = material.descriptorFacts.contribution?.scopedKey;
  if (contributionScopedKey) {
    const [kind, extensionId, contributionId] = contributionScopedKey.split(':');
    if (kind && extensionId && contributionId) {
      return {
        kind,
        extensionId,
        contributionId,
      };
    }
  }

  if (material.descriptorFacts.shader) {
    return {
      kind: 'shader',
      extensionId: material.descriptorFacts.shader.extensionId,
      contributionId: material.descriptorFacts.shader.contributionId,
    };
  }

  if (material.descriptorFacts.process?.processId) {
    return processContributionRef(material.descriptorFacts.process, processes, contributionEntries);
  }

  return undefined;
}

function projectOutputFormatEdges(
  input: CompositionGraphInput,
  nodes: CompositionGraphNode[],
  edges: CompositionGraphEdge[],
  contributionNodeByRefKey: Map<string, CompositionGraphNode>,
  contributionEntries: readonly (readonly [string, readonly ContributionIndexEntry[]])[],
): void {
  if (!input.outputFormats?.length) {
    return;
  }

  const edgeIds = new Set(edges.map((edge) => edge.id));
  const clipNodes = nodes.filter((node) => node.kind === 'clip');
  const shaderNodes = nodes.filter(
    (node) => node.kind === 'contribution' && node.ref?.kind === 'shader',
  );
  const timelinePostprocessNode = nodes.find(
    (node) => node.id === TIMELINE_POSTPROCESS_NODE_ID,
  );

  const pushEdge = (edge: CompositionGraphEdge) => {
    if (edgeIds.has(edge.id)) {
      return;
    }
    edgeIds.add(edge.id);
    edges.push(edge);
  };

  for (const outputFormat of input.outputFormats) {
    const ref: ContributionRef = {
      kind: 'outputFormat',
      extensionId: outputFormat.extensionId,
      contributionId: outputFormat.id,
    };
    const refKey = contributionRefKey(ref);
    const sourceNode = ensureContributionNode(
      nodes,
      contributionNodeByRefKey,
      ref,
      refKey,
    );

    for (const [requirementIndex, requirement] of outputFormat.routeRequirements.entries()) {
      const routeKey = requirement.routes.join('+') || requirement.routeScope.mode;
      const routeDetail = routeRequirementDetail(outputFormat, refKey, requirement, 'route');
      pushEdge(Object.freeze({
        id: `requires:${sourceNode.id}:${sourceNode.id}:route:${routeKey}:${requirementIndex}`,
        kind: 'requires',
        sourceNodeId: sourceNode.id,
        targetNodeId: sourceNode.id,
        detail: routeDetail,
      }));

      for (const clipNode of clipNodes) {
        pushEdge(Object.freeze({
          id: `requires:${sourceNode.id}:${clipNode.id}:clip:${routeKey}:${requirementIndex}`,
          kind: 'requires',
          sourceNodeId: sourceNode.id,
          targetNodeId: clipNode.id,
          detail: routeRequirementDetail(outputFormat, refKey, requirement, 'clip'),
        }));
      }

      if (timelinePostprocessNode) {
        pushEdge(Object.freeze({
          id: `requires:${sourceNode.id}:${timelinePostprocessNode.id}:timeline-postprocess:${routeKey}:${requirementIndex}`,
          kind: 'requires',
          sourceNodeId: sourceNode.id,
          targetNodeId: timelinePostprocessNode.id,
          detail: routeRequirementDetail(
            outputFormat,
            refKey,
            requirement,
            'timeline-postprocess',
          ),
        }));
      }

      for (const shaderNode of shaderNodes) {
        pushEdge(Object.freeze({
          id: `requires:${sourceNode.id}:${shaderNode.id}:shader:${routeKey}:${requirementIndex}`,
          kind: 'requires',
          sourceNodeId: sourceNode.id,
          targetNodeId: shaderNode.id,
          detail: routeRequirementDetail(outputFormat, refKey, requirement, 'shader'),
        }));
      }
    }

    for (const requirement of outputFormat.processRequirements) {
      const processRef = processContributionRef(requirement, input.processes, contributionEntries);
      if (!processRef) {
        continue;
      }

      const processRefKey = contributionRefKey(processRef);
      const targetNode = ensureContributionNode(
        nodes,
        contributionNodeByRefKey,
        processRef,
        processRefKey,
      );
      const routeKey = requirement.routeScope.routes.join('+') || requirement.routeScope.mode;
      pushEdge(Object.freeze({
        id: `requires:${sourceNode.id}:${targetNode.id}:process:${requirement.processId}:${requirement.operationId ?? 'none'}:${routeKey}`,
        kind: 'requires',
        sourceNodeId: sourceNode.id,
        targetNodeId: targetNode.id,
        detail: Object.freeze({
          ...processRequirementDetail(outputFormat, refKey, requirement),
          targetRefKey: processRefKey,
        }),
      }));
    }

    for (const material of input.materialRuntime?.materials ?? []) {
      const targetRef = resolveMaterialDependencyTargetRef(
        material,
        input.processes,
        contributionEntries,
      );
      if (!targetRef) {
        continue;
      }

      const producerRefKey = contributionRefKey(targetRef);
      const targetNode = ensureContributionNode(
        nodes,
        contributionNodeByRefKey,
        targetRef,
        producerRefKey,
      );

      pushEdge(Object.freeze({
        id: `consumes:${sourceNode.id}:${targetNode.id}:material:${material.materialRef.id}`,
        kind: 'consumes',
        sourceNodeId: sourceNode.id,
        targetNodeId: targetNode.id,
        detail: materialDependencyDetail(outputFormat, refKey, material, producerRefKey),
      }));
    }
  }
}

function buildContributionNodeDetail(
  entries: readonly ContributionIndexEntry[] | undefined,
): Record<string, unknown> | undefined {
  if (!entries?.length) {
    return undefined;
  }

  return Object.freeze({
    projected: entries.some((entry) => entry.projection.projected),
    renderId: entries.find((entry) => typeof entry.renderId === 'string')?.renderId,
  });
}

function buildContributionEntryByContributionId(
  contributionEntries: readonly (readonly [string, readonly ContributionIndexEntry[]])[],
): ReadonlyMap<string, ContributionIndexEntry | null> {
  const byContributionId = new Map<string, ContributionIndexEntry | null>();

  for (const [, entries] of contributionEntries) {
    const firstEntry = entries[0];
    if (!firstEntry) {
      continue;
    }

    const existing = byContributionId.get(firstEntry.contributionId);
    if (existing === undefined) {
      byContributionId.set(firstEntry.contributionId, firstEntry);
      continue;
    }

    if (existing && existing.scopedKey === firstEntry.scopedKey) {
      continue;
    }

    byContributionId.set(firstEntry.contributionId, null);
  }

  return byContributionId;
}

function packageStateForReferenceState(
  entries: readonly ContributionIndexEntry[] | undefined,
  state: ReferenceState,
): string | undefined {
  if (!entries?.length) {
    return undefined;
  }

  switch (state) {
    case 'invalid-package':
      return entries.find((entry) => entry.packageState === 'invalid')?.packageState ?? 'invalid';
    case 'settings-error':
      return entries.find((entry) => entry.packageState === 'settings-error')?.packageState ?? 'settings-error';
    case 'runtime-error':
      return entries.find((entry) => entry.packageState === 'runtime-error')?.packageState ?? 'runtime-error';
    case 'version-incompatible':
      return entries.find((entry) => entry.packageState === 'incompatible')?.packageState ?? 'incompatible';
    case 'disabled':
      return entries.find((entry) => entry.packageState === 'disabled-by-user')?.packageState
        ?? entries.find((entry) => entry.status === 'disabled')?.packageState
        ?? 'disabled-by-user';
    case 'duplicate':
      return entries.find((entry) => entry.packageState === 'duplicate')?.packageState
        ?? entries.find((entry) => entry.resolutionPolicy?.kind === 'exact-duplicate')?.packageState
        ?? 'duplicate';
    case 'inactive-reserved':
    case 'resolved':
    case 'unknown':
    case 'missing':
      return entries.find((entry) => entry.packageState !== undefined)?.packageState;
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

function resolveEffectTransitionReferenceUsage(
  usage: EffectTransitionReferenceUsage,
  contributionIndex: ContributionIndex | undefined,
): ResolvedEffectTransitionReferenceUsage {
  const contributionId = usage.contributionId?.trim();
  const managedBy = usage.managedBy?.trim();
  const allEntries: readonly ContributionIndexEntry[] = contributionIndex
    ? Object.values(contributionIndex as Record<string, readonly ContributionIndexEntry[]>).flat()
    : EMPTY_CONTRIBUTION_INDEX_ENTRIES;

  const lookup = resolveEffectTransitionContributionEntry(
    usage.kind,
    managedBy,
    undefined,
    contributionId,
    contributionIndex,
  );
  if (lookup) {
    const entries = contributionIndex?.[lookup.refKey];
    const state = resolveReferenceStateFromEntries(entries);
    const packageState = packageStateForReferenceState(entries, state);
    return {
      ref: lookup.ref,
      refKey: lookup.refKey,
      state,
      ...(packageState ? { packageState } : {}),
    };
  }

  let ref: ContributionRef | undefined;
  let entries: readonly ContributionIndexEntry[] | undefined;

  if (managedBy && contributionId) {
    ref = {
      kind: usage.kind,
      extensionId: managedBy,
      contributionId,
    };
    entries = contributionIndex?.[contributionRefKey(ref)];
  } else if (contributionId) {
    const matches = allEntries.filter(
      (entry) => entry.kind === usage.kind && entry.contributionId === contributionId,
    );
    const matchedScopedKeys = new Set(matches.map((entry) => entry.scopedKey));

    if (matchedScopedKeys.size === 1) {
      const entry = matches[0]!;
      ref = createContributionRef(entry);
      entries = contributionIndex?.[contributionRefKey(ref)];
    } else if (matchedScopedKeys.size > 1) {
      return {
        state: 'duplicate',
        packageState: 'duplicate',
      };
    }
  }

  const state = resolveReferenceStateFromEntries(entries);
  const packageState = packageStateForReferenceState(entries, state);
  return {
    ...(ref ? { ref, refKey: contributionRefKey(ref) } : {}),
    state,
    ...(packageState ? { packageState } : {}),
  };
}

function effectTransitionDiagnosticMessage(
  usage: EffectTransitionReferenceUsage,
  resolved: ResolvedEffectTransitionReferenceUsage,
): string {
  const kindLabel = usage.kind === 'effect' ? 'Effect' : 'Transition';
  const refLabel = resolved.refKey
    ?? (usage.managedBy && usage.contributionId
      ? `${usage.kind}:${usage.managedBy}:${usage.contributionId}`
      : usage.contributionId);
  const ownerLabel = `${kindLabel.toLowerCase()} "${usage.ownerId}"`;

  switch (resolved.state) {
    case 'missing':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} has no scoped candidates in the contribution index.`
        : `${kindLabel} contribution for ${ownerLabel} has no scoped candidates in the contribution index.`;
    case 'disabled':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} comes from a user-disabled package.`
        : `${kindLabel} contribution for ${ownerLabel} comes from a user-disabled package.`;
    case 'inactive-reserved':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} is declared but not yet bridged in this runtime.`
        : `${kindLabel} contribution for ${ownerLabel} is declared but not yet bridged in this runtime.`;
    case 'invalid-package':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} comes from an invalid package.`
        : `${kindLabel} contribution for ${ownerLabel} comes from an invalid package.`;
    case 'duplicate':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} has duplicate scoped candidates, so graph authority cannot resolve it.`
        : `${kindLabel} contribution for ${ownerLabel} has duplicate scoped candidates, so graph authority cannot resolve it.`;
    case 'settings-error':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} comes from a package with a settings migration error.`
        : `${kindLabel} contribution for ${ownerLabel} comes from a package with a settings migration error.`;
    case 'runtime-error':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} comes from a package that failed runtime activation.`
        : `${kindLabel} contribution for ${ownerLabel} comes from a package that failed runtime activation.`;
    case 'version-incompatible':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} comes from a version-incompatible package.`
        : `${kindLabel} contribution for ${ownerLabel} comes from a version-incompatible package.`;
    case 'unknown':
      return refLabel
        ? `${kindLabel} ref "${refLabel}" for ${ownerLabel} could not be resolved to a known graph state.`
        : `${kindLabel} contribution for ${ownerLabel} could not be resolved to a known graph state.`;
    case 'resolved':
      return `${kindLabel} ref "${refLabel ?? usage.ownerId}" for ${ownerLabel} resolved successfully.`;
    default: {
      const _exhaustive: never = resolved.state;
      return _exhaustive;
    }
  }
}

function buildEffectTransitionReferenceStatesAndDiagnostics(
  usages: readonly EffectTransitionReferenceUsage[],
  contributionIndex: ContributionIndex | undefined,
): {
  referenceStates: readonly CompositionReferenceStateEntry[];
  diagnostics: readonly ExtensionDiagnostic[];
} {
  if (usages.length === 0) {
    return {
      referenceStates: EMPTY_REFERENCE_STATES,
      diagnostics: EMPTY_DIAGNOSTICS,
    };
  }

  const diagnostics: ExtensionDiagnostic[] = [];
  const orderedRefKeys: string[] = [];
  const mutableByRefKey: Record<string, {
    state: ReferenceState;
    nodeIds: string[];
  }> = {};

  for (const usage of usages) {
    const resolved = resolveEffectTransitionReferenceUsage(usage, contributionIndex);
    if (resolved.refKey) {
      const existing = mutableByRefKey[resolved.refKey];
      if (existing) {
        if (!existing.nodeIds.includes(usage.nodeId)) {
          existing.nodeIds.push(usage.nodeId);
        }
      } else {
        mutableByRefKey[resolved.refKey] = {
          state: resolved.state,
          nodeIds: [usage.nodeId],
        };
        orderedRefKeys.push(resolved.refKey);
      }
    }

    const code = usage.kind === 'effect'
      ? referenceStateToEffectDiagnosticCode(resolved.state)
      : referenceStateToTransitionDiagnosticCode(resolved.state);
    if (!code) {
      continue;
    }

    const extensionId = resolved.ref?.extensionId ?? usage.managedBy;
    const contributionId = resolved.ref?.contributionId ?? usage.contributionId;
    const detail = {
      nodeId: usage.nodeId,
      clipId: usage.clipId,
      ...(resolved.refKey ? { refKey: resolved.refKey } : {}),
      refState: resolved.state,
      resolverState: resolved.state,
      scope: usage.scope,
      ...(extensionId ? { extensionId } : {}),
      ...(contributionId ? { contributionId } : {}),
      ownerKind: usage.ownerKind,
      ownerId: usage.ownerId,
      ...(usage.targetPath ? { targetPath: usage.targetPath } : {}),
      ...(usage.materialSlot ? { materialSlot: usage.materialSlot } : {}),
      ...(usage.materialRefId ? { materialRefId: usage.materialRefId } : {}),
      ...(resolved.packageState ? { packageState: resolved.packageState } : {}),
    } as const;

    diagnostics.push(Object.freeze({
      ...buildCompositionDiagnostic(
        code,
        effectTransitionDiagnosticMessage(usage, resolved),
        detail,
      ),
      ...(extensionId ? { extensionId } : {}),
      ...(contributionId ? { contributionId } : {}),
    } satisfies ExtensionDiagnostic));
  }

  return {
    referenceStates: orderedRefKeys.length > 0
      ? Object.freeze(orderedRefKeys.map((refKey) => Object.freeze({
          refKey,
          state: mutableByRefKey[refKey]!.state,
          nodeIds: Object.freeze([...mutableByRefKey[refKey]!.nodeIds]),
        })))
      : EMPTY_REFERENCE_STATES,
    diagnostics: diagnostics.length > 0 ? Object.freeze(diagnostics) : EMPTY_DIAGNOSTICS,
  };
}

export function canonicalizeAutomationParameterPath(parameterPath: string): string | undefined {
  const trimmed = parameterPath.trim();
  if (trimmed.length === 0) {
    return undefined;
  }

  return trimmed.startsWith('params.') ? trimmed.slice('params.'.length) : trimmed;
}

export function canonicalizeShaderUniformPath(parameterPath: string): string | undefined {
  const trimmed = parameterPath.trim();
  if (trimmed.length === 0) {
    return undefined;
  }

  const uniform = trimmed.startsWith('uniforms.') ? trimmed.slice('uniforms.'.length) : trimmed;
  return uniform.length > 0 ? `uniforms.${uniform}` : undefined;
}

function canonicalAutomationTargetPath(
  automation: Readonly<{
    parameterPath: string;
    targetPath?: string;
  }>,
): string | undefined {
  if (typeof automation.targetPath === 'string' && automation.targetPath.trim().length > 0) {
    return canonicalizeAutomationParameterPath(automation.targetPath);
  }

  return canonicalizeAutomationParameterPath(automation.parameterPath);
}

function canonicalLiveBindingTargetPath(
  binding: Readonly<{
    targetKind?: string;
    targetParamName?: string;
    targetPath?: string;
    targetMaterialId?: string;
  }>,
): string | undefined {
  const targetPath = typeof binding.targetPath === 'string' && binding.targetPath.trim().length > 0
    ? binding.targetPath
    : binding.targetParamName;
  if (typeof targetPath !== 'string' || targetPath.trim().length === 0) {
    return undefined;
  }

  const isShaderUniformTarget =
    binding.targetKind === 'shader-uniform'
    || typeof binding.targetMaterialId === 'string'
    || targetPath.trim().startsWith('uniforms.');

  return isShaderUniformTarget
    ? canonicalizeShaderUniformPath(targetPath)
    : canonicalizeAutomationParameterPath(targetPath);
}

function liveBindingTargetKind(
  binding: Readonly<{
    targetKind?: string;
    targetEffectId?: string;
    targetMaterialId?: string;
  }>,
  targetPath: string,
): 'clip-param' | 'effect-param' | 'shader-uniform' {
  if (
    binding.targetKind === 'clip-param'
    || binding.targetKind === 'effect-param'
    || binding.targetKind === 'shader-uniform'
  ) {
    return binding.targetKind;
  }

  if (typeof binding.targetMaterialId === 'string' || targetPath.startsWith('uniforms.')) {
    return 'shader-uniform';
  }

  if (typeof binding.targetEffectId === 'string') {
    return 'effect-param';
  }

  return 'clip-param';
}

function selectShaderSummaries(input: CompositionGraphInput): readonly TimelineShaderSummary[] {
  const patchOverlayShaders = input.patchOverlay?.shaders;
  if (patchOverlayShaders && patchOverlayShaders.length > 0) {
    return patchOverlayShaders;
  }

  const runtimeOverlayShaders = input.runtimeOverlay?.shaders;
  if (runtimeOverlayShaders && runtimeOverlayShaders.length > 0) {
    return runtimeOverlayShaders;
  }

  return input.snapshot.shaders ?? EMPTY_SHADERS;
}

function scopeNodeId(shader: TimelineShaderSummary): string | undefined {
  if (shader.scope === 'clip') {
    return shader.clipId ? clipNodeId(shader.clipId) : undefined;
  }

  if (shader.scope === 'postprocess') {
    return TIMELINE_POSTPROCESS_NODE_ID;
  }

  return undefined;
}

function scopeLabel(shader: TimelineShaderSummary): 'clip' | 'postprocess' | undefined {
  if (shader.scope === 'clip' || shader.scope === 'postprocess') {
    return shader.scope;
  }
  return undefined;
}

function shaderUniformName(targetPath: string): string {
  return targetPath.startsWith('uniforms.')
    ? targetPath.slice('uniforms.'.length)
    : targetPath;
}

function duplicateScopeMessage(
  shader: Pick<TimelineShaderSummary, 'scope' | 'clipId' | 'shaderId'>,
  winnerShaderId: string,
): string {
  if (shader.scope === 'clip') {
    const clipLabel = shader.clipId ? `clip "${shader.clipId}"` : 'the clip scope';
    return `${clipLabel} has multiple shader assignments; shader "${winnerShaderId}" wins and shader "${shader.shaderId}" is a duplicate.`;
  }

  return `Timeline postprocess has multiple shader assignments; shader "${winnerShaderId}" wins and shader "${shader.shaderId}" is a duplicate.`;
}

function buildDuplicateScopeDiagnostics(
  shaders: readonly TimelineShaderSummary[],
  contributionIndex: ContributionIndex | undefined,
): readonly ExtensionDiagnostic[] {
  const activeShaders = shaders.filter((shader) => {
    if (shader.enabled === false) {
      return false;
    }
    const ref: ContributionRef = {
      kind: 'shader',
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
    };
    return resolveReferenceStateFromEntries(contributionIndex?.[contributionRefKey(ref)]) !== 'disabled';
  });
  const validation = validateShaderComposition(activeShaders);
  if (validation.occupied.length === 0) {
    return EMPTY_DIAGNOSTICS;
  }

  return Object.freeze(validation.occupied.map((occupied) => {
    const incoming = occupied.incoming;
    const nodeId = incoming.scope === 'clip'
      ? clipNodeId(incoming.clipId ?? occupied.clipId ?? '')
      : TIMELINE_POSTPROCESS_NODE_ID;
    const ref: ContributionRef = {
      kind: 'shader',
      extensionId: incoming.extensionId,
      contributionId: incoming.contributionId,
    };
    return Object.freeze({
      ...buildCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
        duplicateScopeMessage(incoming, occupied.existing.shaderId),
        {
          nodeId,
          refKey: contributionRefKey(ref),
          scope: incoming.scope,
          extensionId: incoming.extensionId,
          contributionId: incoming.contributionId,
          shaderId: incoming.shaderId,
        },
      ),
      extensionId: incoming.extensionId,
      contributionId: incoming.contributionId,
    } satisfies ExtensionDiagnostic);
  }));
}

// ---------------------------------------------------------------------------
// Clip-type reference state resolution
// ---------------------------------------------------------------------------

function clipTypeReferenceState(record: ClipTypeRegistryRecord | undefined): ReferenceState {
  if (!record) {
    return 'missing';
  }

  const hasBlockers = record.renderability.blockers && record.renderability.blockers.length > 0;
  if (hasBlockers) {
    return 'disabled';
  }

  if (record.status === 'error') {
    return 'runtime-error';
  }

  if (record.status === 'inactive') {
    return 'inactive-reserved';
  }

  return 'resolved';
}

function clipTypeDiagnosticMessage(refKey: string, state: ReferenceState, clipTypeId: string): string {
  switch (state) {
    case 'missing':
      return `Clip type "${clipTypeId}" ref "${refKey}" has no registered clip type record.`;
    case 'disabled':
      return `Clip type "${clipTypeId}" ref "${refKey}" has renderability blockers.`;
    case 'runtime-error':
      return `Clip type "${clipTypeId}" ref "${refKey}" is in error state.`;
    case 'inactive-reserved':
      return `Clip type "${clipTypeId}" ref "${refKey}" is inactive.`;
    default:
      return `Clip type "${clipTypeId}" ref "${refKey}" is ${state}.`;
  }
}

function buildClipTypeReferenceStatesAndDiagnostics(
  usages: readonly CompositionReferenceUsage[],
  clipTypeRegistry: ClipTypeRegistrySnapshot | undefined,
  refKeyToClipTypeId: ReadonlyMap<string, string>,
): {
  referenceStates: readonly CompositionReferenceStateEntry[];
  diagnostics: readonly ExtensionDiagnostic[];
} {
  if (usages.length === 0 || !clipTypeRegistry) {
    return { referenceStates: EMPTY_REFERENCE_STATES, diagnostics: EMPTY_DIAGNOSTICS };
  }

  const diagnostics: ExtensionDiagnostic[] = [];
  const orderedRefKeys: string[] = [];
  const mutableByRefKey: Record<string, {
    refKey: string;
    state: ReferenceState;
    nodeIds: string[];
    clipTypeId: string;
    ref: ContributionRef;
  }> = {};

  for (const usage of usages) {
    const refKey = contributionRefKey(usage.ref);
    let resolved = mutableByRefKey[refKey];
    if (!resolved) {
      const clipTypeId = refKeyToClipTypeId.get(refKey) ?? '';
      const record = clipTypeRegistry?.get(clipTypeId);
      const state = clipTypeReferenceState(record);
      resolved = {
        refKey,
        state,
        nodeIds: [],
        clipTypeId,
        ref: usage.ref,
      };
      mutableByRefKey[refKey] = resolved;
      orderedRefKeys.push(refKey);
    }

    if (!resolved.nodeIds.includes(usage.nodeId)) {
      resolved.nodeIds.push(usage.nodeId);
    }

    if (resolved.state === 'resolved') {
      continue;
    }

    const code = COMPOSITION_DIAGNOSTIC_CODE[
      resolved.state === 'missing' ? 'MISSING_REF'
      : resolved.state === 'disabled' ? 'DISABLED_REF'
      : resolved.state === 'inactive-reserved' ? 'INACTIVE_RESERVED_REF'
      : resolved.state === 'runtime-error' ? 'RUNTIME_ERROR_REF'
      : 'UNKNOWN_REF'
    ] as CompositionDiagnosticCode;

    const record = clipTypeRegistry?.get(resolved.clipTypeId);
    const nextAction: Record<string, unknown> | undefined = record?.renderability.blockers?.length
      ? Object.freeze({
          kind: 'resolve-blockers',
          blockers: record.renderability.blockers.map((b) => ({
            reason: b.reason,
            message: b.message,
            route: b.route,
          })),
        })
      : undefined;

    const diagnostic = Object.freeze({
      ...buildCompositionDiagnostic(
        code,
        clipTypeDiagnosticMessage(refKey, resolved.state, resolved.clipTypeId),
        {
          nodeId: usage.nodeId,
          refKey,
          refState: resolved.state,
          scope: usage.scope,
          extensionId: usage.ref.extensionId,
          contributionId: usage.ref.contributionId,
          ...(nextAction ? { nextAction } : {}),
        },
      ),
      extensionId: usage.ref.extensionId,
      contributionId: usage.ref.contributionId,
    } satisfies ExtensionDiagnostic);

    diagnostics.push(diagnostic);
  }

  const referenceStates = Object.freeze(orderedRefKeys.map((refKey) => {
    const resolved = mutableByRefKey[refKey]!;
    return Object.freeze({
      refKey,
      state: resolved.state,
      nodeIds: Object.freeze([...resolved.nodeIds]),
    });
  }));

  return {
    referenceStates,
    diagnostics: Object.freeze(diagnostics),
  };
}

// ---------------------------------------------------------------------------
// Main projector
// ---------------------------------------------------------------------------

export function projectCompositionGraph(input: CompositionGraphInput): CompositionGraph {
  const nodes: CompositionGraphNode[] = [];
  const edges: CompositionGraphEdge[] = [];
  const contributionNodeByRefKey = new Map<string, CompositionGraphNode>();

  for (const clip of input.snapshot.clips) {
    nodes.push(Object.freeze({
      id: clipNodeId(clip.id),
      kind: 'clip',
      detail: Object.freeze({
        clipId: clip.id,
        trackId: clip.track,
        at: clip.at,
        clipType: clip.clipType,
        duration: clip.duration,
      }),
    }));
  }

  nodes.push(Object.freeze({
    id: TIMELINE_POSTPROCESS_NODE_ID,
    kind: 'timeline-postprocess',
    detail: Object.freeze({ scope: 'postprocess' }),
  }));

  const contributionIndex = input.contributionIndex;
  const contributionEntries = contributionIndex
    ? Object.entries(contributionIndex).sort(([left], [right]) => left.localeCompare(right))
    : [];
  const contributionEntryByContributionId = buildContributionEntryByContributionId(contributionEntries);
  const effectTransitionRefUsages: EffectTransitionReferenceUsage[] = [];
  for (const [refKey, entries] of contributionEntries) {
    const firstEntry = entries[0];
    if (!firstEntry || contributionNodeByRefKey.has(refKey)) {
      continue;
    }

    const ref = createContributionRef(firstEntry);
    const node = Object.freeze({
      id: contributionNodeId(ref),
      kind: 'contribution' as const,
      ref,
      detail: buildContributionNodeDetail(entries),
    });
    contributionNodeByRefKey.set(refKey, node);
    nodes.push(node);
  }

  for (const clip of input.snapshot.clips) {
    const automations = clip.automation;
    if (!automations?.length) {
      continue;
    }

    const sourceNodeId = clipNodeId(clip.id);
    for (const automation of automations) {
      if (automation.enabled === false) {
        continue;
      }

      const targetPath = canonicalAutomationTargetPath(automation);
      if (!targetPath) {
        continue;
      }

      const contributionEntry = contributionEntryByContributionId.get(automation.contributionId);
      if (!contributionEntry) {
        continue;
      }

      const ref = createContributionRef(contributionEntry);
      const refKey = contributionRefKey(ref);
      let contributionNode = contributionNodeByRefKey.get(refKey);
      if (!contributionNode) {
        contributionNode = Object.freeze({
          id: contributionNodeId(ref),
          kind: 'contribution' as const,
          ref,
        });
        contributionNodeByRefKey.set(refKey, contributionNode);
        nodes.push(contributionNode);
      }

      edges.push(Object.freeze({
        id: `animates:${sourceNodeId}:${contributionNode.id}:${targetPath}`,
        kind: 'animates',
        sourceNodeId,
        targetNodeId: contributionNode.id,
        detail: Object.freeze({
          clipId: clip.id,
          contributionId: automation.contributionId,
          parameterPath: automation.parameterPath,
          targetKind: targetPath.startsWith('uniforms.') ? 'shader-uniform' : 'clip-param',
          targetPath,
          keyframeCount: automation.keyframeCount,
          refKey,
        }),
      }));
    }
  }

  for (const clip of input.snapshot.clips) {
    const liveBindings = clip.liveBindings;
    if (!liveBindings?.length) {
      continue;
    }

    const sourceNodeId = clipNodeId(clip.id);
    for (const binding of liveBindings) {
      if (binding.status !== 'resolved') {
        continue;
      }

      const targetPath = canonicalLiveBindingTargetPath(binding);
      if (!targetPath) {
        continue;
      }

      let targetNodeId = sourceNodeId;
      let refKey: string | undefined;
      const targetContributionId = binding.targetMaterialId ?? binding.targetEffectId;
      if (typeof targetContributionId === 'string' && targetContributionId.length > 0) {
        const contributionEntry = contributionEntryByContributionId.get(targetContributionId);
        if (contributionEntry) {
          const ref = createContributionRef(contributionEntry);
          refKey = contributionRefKey(ref);
          let contributionNode = contributionNodeByRefKey.get(refKey);
          if (!contributionNode) {
            contributionNode = Object.freeze({
              id: contributionNodeId(ref),
              kind: 'contribution' as const,
              ref,
            });
            contributionNodeByRefKey.set(refKey, contributionNode);
            nodes.push(contributionNode);
          }
          targetNodeId = contributionNode.id;
        }
      }

      edges.push(Object.freeze({
        id: `binds-live:${sourceNodeId}:${binding.sourceId}:${binding.bindingId}:${targetPath}`,
        kind: 'binds-live',
        sourceNodeId,
        targetNodeId,
        detail: Object.freeze({
          bindingId: binding.bindingId,
          clipId: clip.id,
          sourceId: binding.sourceId,
          sourceKind: binding.sourceKind,
          status: binding.status,
          targetKind: liveBindingTargetKind(binding, targetPath),
          targetPath,
          ...(binding.targetParamName !== undefined ? { targetParamName: binding.targetParamName } : {}),
          ...(binding.targetEffectId !== undefined ? { targetEffectId: binding.targetEffectId } : {}),
          ...(binding.targetMaterialId !== undefined ? { targetMaterialId: binding.targetMaterialId } : {}),
          ...(refKey !== undefined ? { refKey } : {}),
        }),
      }));
    }
  }

  // ---- clip-type projection --------------------------------------------------
  const clipTypeRefUsages: CompositionReferenceUsage[] = [];
  const refKeyToClipTypeId = new Map<string, string>();
  const clipTypeRegistry = input.clipTypeRegistry;
  if (clipTypeRegistry) {
    for (const clip of input.snapshot.clips) {
      const clipTypeId = clip.clipType;
      if (!clipTypeId) {
        continue;
      }

      const record = clipTypeRegistry.get(clipTypeId);
      if (!record?.ownerExtensionId || !record.contributionId) {
        continue;
      }

      const ref: ContributionRef = {
        kind: 'clipType',
        extensionId: record.ownerExtensionId,
        contributionId: record.contributionId,
      };
      const refKey = contributionRefKey(ref);
      refKeyToClipTypeId.set(refKey, clipTypeId);

      let contributionNode = contributionNodeByRefKey.get(refKey);
      if (!contributionNode) {
        contributionNode = Object.freeze({
          id: contributionNodeId(ref),
          kind: 'contribution' as const,
          ref,
        });
        contributionNodeByRefKey.set(refKey, contributionNode);
        nodes.push(contributionNode);
      }

      const sourceNodeId = clipNodeId(clip.id);
      edges.push(Object.freeze({
        id: `consumes:${sourceNodeId}:${contributionNode.id}:${clipTypeId}`,
        kind: 'consumes',
        sourceNodeId,
        targetNodeId: contributionNode.id,
        detail: Object.freeze({
          clipTypeId,
          clipId: clip.id,
          refKey,
          scope: 'clip',
        }),
      }));

      clipTypeRefUsages.push({
        ref,
        nodeId: sourceNodeId,
        scope: 'clip',
      });
    }
  }

  // ---- effect consumes edges -------------------------------------------------
  for (const clip of input.snapshot.clips) {
    const effects = clip.effects;
    if (!effects?.length) {
      continue;
    }

    const sourceNodeId = clipNodeId(clip.id);
    for (const effect of effects) {
      effectTransitionRefUsages.push({
        kind: 'effect',
        nodeId: sourceNodeId,
        clipId: clip.id,
        scope: 'clip',
        contributionId: effect.effectType,
        managedBy: effect.managedBy,
        ownerKind: 'effect',
        ownerId: effect.id,
      });

      const lookup = resolveEffectContributionEntry(effect, contributionIndex);
      if (!lookup) {
        continue;
      }

      const contributionNode = ensureContributionNode(
        nodes,
        contributionNodeByRefKey,
        lookup.ref,
        lookup.refKey,
      );

      edges.push(Object.freeze({
        id: `consumes:${sourceNodeId}:${contributionNode.id}:${effect.id}`,
        kind: 'consumes',
        sourceNodeId,
        targetNodeId: contributionNode.id,
        detail: Object.freeze({
          effectId: effect.id,
          clipId: clip.id,
          effectType: effect.effectType,
          refKey: lookup.refKey,
          consumedKind: 'effect',
          scope: 'clip',
        }),
      }));
    }
  }

  // ---- transition consumes edges ---------------------------------------------
  for (const clip of input.snapshot.clips) {
    const transition = clip.transition;
    if (!transition) {
      continue;
    }

    const sourceNodeId = clipNodeId(clip.id);
    effectTransitionRefUsages.push({
      kind: 'transition',
      nodeId: sourceNodeId,
      clipId: clip.id,
      scope: 'clip',
      contributionId: transition.transitionType,
      managedBy: transition.managedBy,
      ownerKind: 'transition',
      ownerId: transition.id,
    });

    const lookup = resolveTransitionContributionEntry(transition, contributionIndex);
    if (!lookup) {
      continue;
    }

    const contributionNode = ensureContributionNode(
      nodes,
      contributionNodeByRefKey,
      lookup.ref,
      lookup.refKey,
    );

    edges.push(Object.freeze({
      id: `consumes:${sourceNodeId}:${contributionNode.id}:${transition.id}`,
      kind: 'consumes',
      sourceNodeId,
      targetNodeId: contributionNode.id,
      detail: Object.freeze({
        transitionId: transition.id,
        clipId: clip.id,
        transitionType: transition.transitionType,
        refKey: lookup.refKey,
        consumedKind: 'transition',
        scope: 'clip',
        ownerKind: 'transition',
        ownerId: transition.id,
      }),
    }));
  }

  // ---- transition mask-material consumes edges -------------------------------
  for (const binding of input.materialSlotBindings ?? []) {
    if (binding.owner.kind !== 'transition') {
      continue;
    }

    const clip = input.snapshot.clips.find((candidate) => candidate.id === binding.owner.clipId);
    const transition = clip?.transition;
    if (!clip || !transition || transition.id !== binding.owner.ownerId) {
      continue;
    }

    const sourceNodeId = clipNodeId(clip.id);
    effectTransitionRefUsages.push({
      kind: 'transition',
      nodeId: sourceNodeId,
      clipId: clip.id,
      scope: 'clip',
      contributionId: transition.transitionType,
      managedBy: transition.managedBy,
      ownerKind: binding.owner.kind,
      ownerId: binding.owner.ownerId,
      materialSlot: binding.slotName,
      materialRefId: binding.materialRefId,
    });

    const lookup = resolveTransitionContributionEntry(transition, contributionIndex);
    if (!lookup) {
      continue;
    }

    const contributionNode = ensureContributionNode(
      nodes,
      contributionNodeByRefKey,
      lookup.ref,
      lookup.refKey,
    );

    edges.push(Object.freeze({
      id: `consumes:${sourceNodeId}:${contributionNode.id}:${transition.id}:${binding.slotName}:${binding.materialRefId}`,
      kind: 'consumes',
      sourceNodeId,
      targetNodeId: contributionNode.id,
      detail: Object.freeze({
        transitionId: transition.id,
        clipId: clip.id,
        transitionType: transition.transitionType,
        refKey: lookup.refKey,
        consumedKind: 'mask-material',
        targetSlot: binding.slotName,
        materialRefId: binding.materialRefId,
        scope: 'clip',
        ownerKind: binding.owner.kind,
        ownerId: binding.owner.ownerId,
      }),
    }));
  }

  const shaders = selectShaderSummaries(input);
  const refUsages: CompositionReferenceUsage[] = [];
  for (const shader of shaders) {
    if (shader.enabled === false) {
      continue;
    }

    const sourceNodeId = scopeNodeId(shader);
    const scope = scopeLabel(shader);
    if (!sourceNodeId || !scope) {
      continue;
    }

    const ref: ContributionRef = {
      kind: 'shader',
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
    };
    const refKey = contributionRefKey(ref);
    const refState = resolveReferenceStateFromEntries(contributionIndex?.[refKey]);
    refUsages.push({
      ref,
      nodeId: sourceNodeId,
      scope,
      shaderId: shader.shaderId,
    });
    if (refState === 'disabled') {
      continue;
    }

    let contributionNode = contributionNodeByRefKey.get(refKey);
    if (!contributionNode) {
      contributionNode = Object.freeze({
        id: contributionNodeId(ref),
        kind: 'contribution' as const,
        ref,
      });
      contributionNodeByRefKey.set(refKey, contributionNode);
      nodes.push(contributionNode);
    }

    edges.push(Object.freeze({
      id: `consumes:${sourceNodeId}:${contributionNode.id}:${shader.id}`,
      kind: 'consumes',
      sourceNodeId,
      targetNodeId: contributionNode.id,
      detail: Object.freeze({
        shaderId: shader.shaderId,
        clipId: shader.clipId,
        refKey,
        scope,
      }),
    }));

    for (const [rawTargetPath, keyframes] of Object.entries(shader.keyframes ?? {})) {
      const targetPath = canonicalizeShaderUniformPath(rawTargetPath);
      if (!targetPath || !keyframes.length) {
        continue;
      }

      edges.push(Object.freeze({
        id: `animates:${sourceNodeId}:${contributionNode.id}:${shader.id}:${targetPath}`,
        kind: 'animates',
        sourceNodeId,
        targetNodeId: contributionNode.id,
        detail: Object.freeze({
          shaderId: shader.shaderId,
          clipId: shader.clipId,
          contributionId: shader.contributionId,
          refKey,
          scope,
          targetKind: 'shader-uniform',
          targetPath,
          uniformName: shaderUniformName(targetPath),
          keyframeCount: keyframes.length,
        }),
      }));
    }
  }

  const resolvedReferences = resolveCompositionReferences(refUsages, contributionIndex);
  const duplicateScopeDiagnostics = buildDuplicateScopeDiagnostics(shaders, contributionIndex);
  const clipTypeResolved = buildClipTypeReferenceStatesAndDiagnostics(
    clipTypeRefUsages,
    clipTypeRegistry,
    refKeyToClipTypeId,
  );
  const effectTransitionResolved = buildEffectTransitionReferenceStatesAndDiagnostics(
    effectTransitionRefUsages,
    contributionIndex,
  );
  projectOutputFormatEdges(
    input,
    nodes,
    edges,
    contributionNodeByRefKey,
    contributionEntries,
  );

  // Merge reference states: clip type refs first, then effect/transition refs,
  // then shader refs.
  const mergedReferenceStates = [
    ...clipTypeResolved.referenceStates,
    ...effectTransitionResolved.referenceStates,
    ...resolvedReferences.referenceStates,
  ];

  // Merge diagnostics
  const allDiagnostics = [
    ...duplicateScopeDiagnostics,
    ...clipTypeResolved.diagnostics,
    ...effectTransitionResolved.diagnostics,
    ...resolvedReferences.diagnostics,
  ];

  return Object.freeze({
    nodes: nodes.length > 0 ? Object.freeze(nodes) : EMPTY_NODES,
    edges: edges.length > 0 ? Object.freeze(edges) : EMPTY_EDGES,
    referenceStates: mergedReferenceStates.length > 0
      ? Object.freeze(mergedReferenceStates)
      : EMPTY_REFERENCE_STATES,
    diagnostics: allDiagnostics.length > 0
      ? Object.freeze(allDiagnostics)
      : EMPTY_DIAGNOSTICS,
  } satisfies CompositionGraph);
}
