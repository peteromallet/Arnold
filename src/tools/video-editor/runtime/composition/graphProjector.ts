import type {
  CompositionGraph,
  CompositionGraphEdge,
  CompositionGraphNode,
  ContributionRef,
  ExtensionDiagnostic,
  TimelineShaderSummary,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import { contributionRefKey } from '@reigh/editor-sdk';
import {
  buildCompositionDiagnostic,
  COMPOSITION_DIAGNOSTIC_CODE,
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

export interface CompositionGraphInput {
  readonly snapshot: TimelineSnapshot;
  readonly contributionIndex: ContributionIndex | undefined;
  readonly runtimeOverlay?: CompositionGraphRuntimeOverlay;
  readonly patchOverlay?: CompositionGraphPatchOverlay;
}

const EMPTY_NODES: readonly CompositionGraphNode[] = Object.freeze([]);
const EMPTY_EDGES: readonly CompositionGraphEdge[] = Object.freeze([]);
const EMPTY_DIAGNOSTICS: readonly ExtensionDiagnostic[] = Object.freeze([]);
const EMPTY_SHADERS: readonly TimelineShaderSummary[] = Object.freeze([]);

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
  }

  const resolvedReferences = resolveCompositionReferences(refUsages, contributionIndex);
  const duplicateScopeDiagnostics = buildDuplicateScopeDiagnostics(shaders);

  return Object.freeze({
    nodes: nodes.length > 0 ? Object.freeze(nodes) : EMPTY_NODES,
    edges: edges.length > 0 ? Object.freeze(edges) : EMPTY_EDGES,
    referenceStates: resolvedReferences.referenceStates,
    diagnostics: duplicateScopeDiagnostics.length > 0
      ? Object.freeze([...duplicateScopeDiagnostics, ...resolvedReferences.diagnostics])
      : resolvedReferences.diagnostics,
  } satisfies CompositionGraph);
}
