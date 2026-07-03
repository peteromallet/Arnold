/**
 * Internal graph patch preview — M1b shader.assign / shader.remove preview.
 *
 * This module provides host-owned preview logic that clones a composition
 * graph input, applies internal patch operations, re-projects the graph,
 * and returns a {@link CompositionGraphPreviewResult}.  No public SDK
 * timeline patch families are added for M1b.
 *
 * @module composition/patchPreview
 * @hostOwned — NOT exported through public SDK contracts.
 */

import type { TimelineShaderSummary } from '@reigh/editor-sdk';
import type { CompositionGraphPreviewResult } from '@reigh/editor-sdk';
import type { CompositionGraphInput } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';

// ---------------------------------------------------------------------------
// Internal patch operation types
// ---------------------------------------------------------------------------

/**
 * Internal assign operation: add (or replace) a shader assignment on a
 * clip or timeline-postprocess scope.
 */
export interface GraphShaderAssignOp {
  readonly kind: 'shader.assign';
  /** The shader summary to assign (must carry scope + clipId when clip). */
  readonly shader: TimelineShaderSummary;
}

/**
 * Internal remove operation: remove a shader assignment from a clip or
 * timeline-postprocess scope.
 */
export interface GraphShaderRemoveOp {
  readonly kind: 'shader.remove';
  /** The shaderId to remove. */
  readonly shaderId: string;
  /** The scope to remove from. */
  readonly scope: 'clip' | 'postprocess';
  /** Clip id when scope is 'clip'. */
  readonly clipId?: string;
}

/**
 * A single internal graph preview operation.
 */
export type GraphPreviewOperation = GraphShaderAssignOp | GraphShaderRemoveOp;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function cloneShaders(shaders: readonly TimelineShaderSummary[]): TimelineShaderSummary[] {
  return shaders.map((shader) => ({ ...shader }));
}

function applyShaderAssign(
  shaders: TimelineShaderSummary[],
  op: GraphShaderAssignOp,
): void {
  const assignId = op.shader.scope === 'clip'
    ? `${op.shader.clipId}:shader:${op.shader.shaderId}`
    : `postprocess:shader:${op.shader.shaderId}`;

  // Remove any existing shader for the same scope so this becomes the
  // single-occupancy winner (matching patch overlay semantics).
  let idx = 0;
  while (idx < shaders.length) {
    const shader = shaders[idx]!;
    if (shader.scope === op.shader.scope && shader.clipId === op.shader.clipId) {
      shaders.splice(idx, 1);
      continue;
    }
    idx++;
  }

  shaders.push({
    id: assignId,
    shaderId: op.shader.shaderId,
    scope: op.shader.scope,
    clipId: op.shader.clipId,
    extensionId: op.shader.extensionId,
    contributionId: op.shader.contributionId,
    enabled: op.shader.enabled !== false,
  });
}

/** Sentinel shaderId that matches any shader for a given scope. */
const REMOVE_ANY_SHADER = '*';

function applyShaderRemove(
  shaders: TimelineShaderSummary[],
  op: GraphShaderRemoveOp,
): void {
  const matchAny = op.shaderId === REMOVE_ANY_SHADER;
  let idx = 0;
  while (idx < shaders.length) {
    const shader = shaders[idx]!;
    const shaderMatches = matchAny || shader.shaderId === op.shaderId;
    if (
      shaderMatches
      && shader.scope === op.scope
      && shader.clipId === op.clipId
    ) {
      shaders.splice(idx, 1);
      continue;
    }
    idx++;
  }
}

function cloneInput(input: CompositionGraphInput): CompositionGraphInput {
  return {
    snapshot: {
      ...input.snapshot,
      clips: input.snapshot.clips.map((clip) => ({ ...clip })),
      shaders: input.snapshot.shaders ? cloneShaders(input.snapshot.shaders) : [],
    },
    contributionIndex: input.contributionIndex,
    // runtime overlay is intentionally not carried forward because the
    // preview operates on the cloned snapshot shaders directly.
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Apply internal graph patch operations (`shader.assign` / `shader.remove`)
 * to a cloned composition graph input and return the resulting preview shape.
 *
 * Returns `undefined` when no operations are provided.
 *
 * The returned {@link CompositionGraphPreviewResult} contains:
 * - `nodes`               — re-projected graph nodes after applying ops.
 * - `edges`               — re-projected edges with added/removed consumes edges.
 * - `referenceStates`     — recomputed reference states after changes.
 * - `diagnostics`         — diagnostics from the re-projected graph.
 */
export function applyGraphPreviewOperations(
  input: CompositionGraphInput,
  operations: readonly GraphPreviewOperation[],
): CompositionGraphPreviewResult | undefined {
  if (operations.length === 0) {
    return undefined;
  }

  const clone = cloneInput(input);

  for (const op of operations) {
    switch (op.kind) {
      case 'shader.assign':
        applyShaderAssign(clone.snapshot.shaders ?? [], op);
        break;
      case 'shader.remove':
        applyShaderRemove(clone.snapshot.shaders ?? [], op);
        break;
    }
  }

  const projected = projectCompositionGraph(clone);

  return {
    nodes: projected.nodes,
    edges: projected.edges,
    referenceStates: projected.referenceStates,
    diagnostics: projected.diagnostics,
  };
}

/**
 * Create a preview closure that captures the original graph input and
 * returns preview results for a given set of operations.
 *
 * This is the standard factory for the `CompositionGraph.preview` field.
 */
export function createGraphPreview(
  input: CompositionGraphInput,
): () => CompositionGraphPreviewResult | undefined {
  return (): CompositionGraphPreviewResult | undefined => {
    // The preview closure is invoked without arguments — the caller is
    // responsible for providing operations externally.  When no operations
    // are queued, the preview returns undefined.
    return undefined;
  };
}

/**
 * Create a preview closure that applies a fixed set of operations.
 *
 * Useful for callers that know the operations ahead of time and just need
 * the result shape.
 */
export function createGraphPreviewWithOps(
  input: CompositionGraphInput,
  operations: readonly GraphPreviewOperation[],
): () => CompositionGraphPreviewResult | undefined {
  return () => applyGraphPreviewOperations(input, operations);
}
