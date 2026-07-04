import type {
  CompositionGraph,
  CompositionGraphEdge,
  CompositionGraphNode,
  CompositionReferenceStateEntry,
  ContributionRef,
  ExtensionDiagnostic,
  ReferenceState,
  TimelineShaderSummary,
  TimelineSnapshot,
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
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import {
  resolveCompositionReferences,
  type CompositionReferenceUsage,
} from '@/tools/video-editor/runtime/composition/referenceResolver.ts';
import { validateShaderComposition } from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';

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

export interface CompositionGraphInput {
  readonly snapshot: TimelineSnapshot;
  readonly contributionIndex: ContributionIndex | undefined;
  readonly clipTypeRegistry?: ClipTypeRegistrySnapshot;
  readonly runtimeOverlay?: CompositionGraphRuntimeOverlay;
  readonly patchOverlay?: CompositionGraphPatchOverlay;
  readonly materialRuntime?: HostMaterialRuntimeProjection;
  readonly materialSlotDeclarations?: readonly CompositionGraphMaterialSlotDeclaration[];
  readonly materialSlotBindings?: readonly CompositionGraphMaterialSlotBinding[];
}

const EMPTY_NODES: readonly CompositionGraphNode[] = Object.freeze([]);
const EMPTY_EDGES: readonly CompositionGraphEdge[] = Object.freeze([]);
const EMPTY_DIAGNOSTICS: readonly ExtensionDiagnostic[] = Object.freeze([]);
const EMPTY_SHADERS: readonly TimelineShaderSummary[] = Object.freeze([]);
const EMPTY_REFERENCE_STATES: readonly CompositionReferenceStateEntry[] = Object.freeze([]);

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
): readonly ExtensionDiagnostic[] {
  const activeShaders = shaders.filter((shader) => shader.enabled !== false);
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
      return `Clip type \"${clipTypeId}\" ref \"${refKey}\" has no registered clip type record.`;
    case 'disabled':
      return `Clip type \"${clipTypeId}\" ref \"${refKey}\" has renderability blockers.`;
    case 'runtime-error':
      return `Clip type \"${clipTypeId}\" ref \"${refKey}\" is in error state.`;
    case 'inactive-reserved':
      return `Clip type \"${clipTypeId}\" ref \"${refKey}\" is inactive.`;
    default:
      return `Clip type \"${clipTypeId}\" ref \"${refKey}\" is ${state}.`;
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

    refUsages.push({
      ref,
      nodeId: sourceNodeId,
      scope,
      shaderId: shader.shaderId,
    });

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
  const duplicateScopeDiagnostics = buildDuplicateScopeDiagnostics(shaders);
  const clipTypeResolved = buildClipTypeReferenceStatesAndDiagnostics(
    clipTypeRefUsages,
    clipTypeRegistry,
    refKeyToClipTypeId,
  );

  // Merge reference states: clip type refs first, then shader refs
  const mergedReferenceStates = [
    ...clipTypeResolved.referenceStates,
    ...resolvedReferences.referenceStates,
  ];

  // Merge diagnostics
  const allDiagnostics = [
    ...duplicateScopeDiagnostics,
    ...clipTypeResolved.diagnostics,
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
