/**
 * Shader projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * Preserves the shader asymmetry: shader contributions remain projectable
 * through sequencing, and missing `shaderId` diagnostics are emitted here
 * rather than in Phase 2 filtering.
 *
 * M1b: When a {@link CompositionGraph} is supplied the projector treats the
 * graph's `consumes` edges as the authority for which shader contributions
 * produce descriptors.  The descriptor-array shape stays identical so
 * downstream callers are not broken.
 *
 * @module families/projectors/shaderProjector
 */

import type {
  ShaderContribution,
  ExtensionDiagnostic,
  CompositionGraph,
  CompositionGraphNode,
} from '@reigh/editor-sdk';
import { contributionRefKey } from '@reigh/editor-sdk';
import type { VideoEditorShaderDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export interface ShaderProjectionResult {
  readonly descriptors: readonly VideoEditorShaderDescriptor[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

/** Reference states whose graph-consuming shaders are considered visible. */
const GRAPH_VISIBLE_REFERENCE_STATES = new Set<string>(['resolved', 'missing']);

// ---------------------------------------------------------------------------
// Graph-derived shader descriptor shim (M1b)
// ---------------------------------------------------------------------------

/**
 * Build shader descriptors from graph edges when the composition graph is
 * present.  Falls back to {@link buildShaderDescriptors} when the graph is
 * absent or carries no shader `consumes` edges.
 *
 * The graph is the authoritative source for *which* shader contributions
 * produce descriptors; the contribution data still supplies the descriptor
 * payload fields (`pass`, `source`, `uniforms`, etc.).  This prevents the
 * descriptor array from becoming a second authority for M1b shader/ref
 * resolution.
 */
export function buildShaderDescriptorsFromGraph(
  contributions: readonly CollectedContribution[],
  extensionOrder: ReadonlyMap<string, number> | undefined,
  compositionGraph: CompositionGraph | undefined,
): ShaderProjectionResult {
  if (!compositionGraph || compositionGraph.edges.length === 0) {
    return buildShaderDescriptors(contributions, extensionOrder);
  }

  // Index contribution data by ref key for O(1) lookup
  const contribByRefKey = new Map<string, CollectedContribution>();
  for (const item of contributions) {
    const refKey = `shader:${item.extensionId}:${item.contribution.id as string}`;
    if (!contribByRefKey.has(refKey)) {
      contribByRefKey.set(refKey, item);
    }
  }

  // Index graph nodes by id
  const nodeById = new Map<string, CompositionGraphNode>(
    compositionGraph.nodes.map((node) => [node.id, node]),
  );

  // Index reference states by ref key
  const refStateByKey = new Map<string, string>(
    compositionGraph.referenceStates.map((entry) => [entry.refKey, entry.state]),
  );

  const descriptors: VideoEditorShaderDescriptor[] = [];
  const diagnostics: ExtensionDiagnostic[] = [];
  const emittedRefKeys = new Set<string>();

  // Walk graph consumes edges targeting shader contribution nodes
  for (const edge of compositionGraph.edges) {
    if (edge.kind !== 'consumes') continue;

    const targetNode = nodeById.get(edge.targetNodeId);
    if (!targetNode?.ref || targetNode.ref.kind !== 'shader') continue;

    const refKey = contributionRefKey(targetNode.ref);
    if (emittedRefKeys.has(refKey)) continue;

    const refState = refStateByKey.get(refKey);
    if (!refState || !GRAPH_VISIBLE_REFERENCE_STATES.has(refState)) continue;

    const shaderId = edge.detail?.shaderId;
    if (typeof shaderId !== 'string' || shaderId.length === 0) continue;

    const contrib = contribByRefKey.get(refKey);
    if (!contrib) {
      // Synthesise a minimal descriptor from graph data when the contribution
      // record is absent (e.g. a shader assigned via preview operations).
      const contribution = { id: targetNode.ref.contributionId } as ShaderContribution & { id: string; order?: number };
      descriptors.push(freezeDescriptor({
        id: targetNode.ref.contributionId,
        extensionId: targetNode.ref.extensionId,
        order: undefined,
        shaderId,
        label: shaderId,
        description: undefined,
        pass: (contribution as ShaderContribution).pass,
        source: (contribution as ShaderContribution).source,
        uniforms: (contribution as ShaderContribution).uniforms,
        textures: (contribution as ShaderContribution).textures,
        fallback: (contribution as ShaderContribution).fallback,
        materializer: (contribution as ShaderContribution).materializer,
        hasSourceMetadata: (contribution as ShaderContribution).source !== undefined,
      }));
      emittedRefKeys.add(refKey);
      continue;
    }

    const shaderContrib = contrib.contribution as unknown as ShaderContribution;
    const id = contrib.contribution.id as string;

    descriptors.push(freezeDescriptor({
      id,
      extensionId: contrib.extensionId,
      order: contrib.contribution.order,
      shaderId,
      label: shaderContrib.label ?? shaderId,
      description: shaderContrib.description,
      pass: shaderContrib.pass,
      source: shaderContrib.source,
      uniforms: shaderContrib.uniforms,
      textures: shaderContrib.textures,
      fallback: shaderContrib.fallback,
      materializer: shaderContrib.materializer,
      hasSourceMetadata: shaderContrib.source !== undefined,
    }));
    emittedRefKeys.add(refKey);
  }

  return {
    descriptors: Object.freeze(descriptors),
    diagnostics: Object.freeze(diagnostics),
  };
}

// ---------------------------------------------------------------------------
// Legacy descriptor projection (graph-absent callers)
// ---------------------------------------------------------------------------

export function buildShaderDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): ShaderProjectionResult {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  const descriptors: VideoEditorShaderDescriptor[] = [];
  const diagnostics: ExtensionDiagnostic[] = [];

  for (const { contribution, extensionId } of sorted) {
    const shaderContrib = contribution as unknown as ShaderContribution;
    const id = contribution.id as string;
    if (!shaderContrib.shaderId) {
      diagnostics.push({
        severity: 'error',
        code: 'runtime/shader-missing-shader-id',
        message:
          `Shader contribution "${id}" in extension "${extensionId}" ` +
          'has no shaderId. The shader will be inactive.',
        extensionId,
        contributionId: id,
      });
      continue;
    }

    descriptors.push(freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      shaderId: shaderContrib.shaderId,
      label: shaderContrib.label ?? shaderContrib.shaderId,
      description: shaderContrib.description,
      pass: shaderContrib.pass,
      source: shaderContrib.source,
      uniforms: shaderContrib.uniforms,
      textures: shaderContrib.textures,
      fallback: shaderContrib.fallback,
      materializer: shaderContrib.materializer,
      hasSourceMetadata: shaderContrib.source !== undefined,
    }));
  }

  return {
    descriptors: Object.freeze(descriptors),
    diagnostics: Object.freeze(diagnostics),
  };
}
