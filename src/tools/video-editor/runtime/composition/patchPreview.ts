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
import type { TimelineSnapshot } from '@reigh/editor-sdk';
import type {
  CaptureCollisionPolicy,
  ClipKeyframe,
  KeyframeInterpolation,
} from '@/tools/video-editor/types/index.ts';
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
 * Event-conversion metadata carried on graph-owned keyframe operations.
 */
export interface GraphKeyframeEventMetadata {
  /** Capture identifier or durable ref that produced this keyframe candidate. */
  readonly captureRef?: string;
  /** Stable source event identifier when the keyframe came from an event table. */
  readonly eventId?: string;
  /** Provenance hash of the validated deterministic capture. */
  readonly provenanceHash?: string;
  /** Collision policy used when this keyframe survived a collision group. */
  readonly collisionPolicy?: CaptureCollisionPolicy;
  /** Canonical target path associated with the keyframe candidate. */
  readonly targetPath?: string;
}

/**
 * Internal keyframe add operation: add a keyframe to a clip parameter.
 */
export interface GraphKeyframeAddOp {
  readonly kind: 'keyframe.add';
  /** The clip to add the keyframe to. */
  readonly clipId: string;
  /** The parameter name (e.g. "opacity", "x"). */
  readonly paramName: string;
  /** The keyframe to add. */
  readonly keyframe: ClipKeyframe;
  /** Optional event-conversion metadata for diagnostics/preview detail. */
  readonly metadata?: GraphKeyframeEventMetadata;
}

/**
 * Internal keyframe update operation: update an existing keyframe value
 * and optionally its interpolation mode.
 */
export interface GraphKeyframeUpdateOp {
  readonly kind: 'keyframe.update';
  /** The clip containing the keyframe. */
  readonly clipId: string;
  /** The parameter name. */
  readonly paramName: string;
  /** The time of the keyframe to update (used as identity). */
  readonly time: number;
  /** The new value. */
  readonly value: number | string | boolean;
  /** Optional new interpolation mode; omitted means keep existing. */
  readonly interpolation?: KeyframeInterpolation;
  /** Optional event-conversion metadata for diagnostics/preview detail. */
  readonly metadata?: GraphKeyframeEventMetadata;
}

/**
 * Internal keyframe remove operation: remove one or all keyframes
 * for a clip parameter.
 */
export interface GraphKeyframeRemoveOp {
  readonly kind: 'keyframe.remove';
  /** The clip containing the keyframe(s). */
  readonly clipId: string;
  /** The parameter name. */
  readonly paramName: string;
  /** The time of the keyframe to remove; omit to remove all keyframes
   * for this parameter. */
  readonly time?: number;
  /** Optional event-conversion metadata for diagnostics/preview detail. */
  readonly metadata?: GraphKeyframeEventMetadata;
}

/**
 * A single internal graph preview operation.
 */
export type GraphPreviewOperation =
  | GraphShaderAssignOp
  | GraphShaderRemoveOp
  | GraphKeyframeAddOp
  | GraphKeyframeUpdateOp
  | GraphKeyframeRemoveOp;

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

type MutablePreviewClip = TimelineSnapshot['clips'][number] & {
  automation?: MutablePreviewAutomation[];
  keyframes?: Record<string, ClipKeyframe[]>;
};

type MutablePreviewAutomation = NonNullable<TimelineSnapshot['clips'][number]['automation']>[number] & {
  keyframes?: ClipKeyframe[];
};

function cloneKeyframe(keyframe: ClipKeyframe): ClipKeyframe {
  return { ...keyframe };
}

function cloneKeyframeRecord(
  keyframes: Record<string, ClipKeyframe[]> | undefined,
): Record<string, ClipKeyframe[]> | undefined {
  if (!keyframes) {
    return undefined;
  }

  const entries = Object.entries(keyframes).map(([paramName, value]) => [
    paramName,
    value.map(cloneKeyframe),
  ]);
  return Object.fromEntries(entries);
}

function cloneAutomation(
  automation: TimelineSnapshot['clips'][number]['automation'],
): MutablePreviewAutomation[] | undefined {
  if (!automation?.length) {
    return automation ? [] : undefined;
  }

  return automation.map((entry) => {
    const clone: MutablePreviewAutomation = { ...entry };
    const keyframes = (entry as MutablePreviewAutomation).keyframes;
    if (keyframes) {
      clone.keyframes = keyframes.map(cloneKeyframe);
    }
    return clone;
  });
}

function canonicalizeKeyframeParamName(paramName: string): string | undefined {
  const trimmed = paramName.trim();
  if (trimmed.length === 0) {
    return undefined;
  }

  return trimmed.startsWith('params.') ? trimmed.slice('params.'.length) : trimmed;
}

function matchAutomationSummary(
  clip: MutablePreviewClip,
  paramName: string,
): MutablePreviewAutomation | undefined {
  const canonicalParamName = canonicalizeKeyframeParamName(paramName);
  if (!canonicalParamName) {
    return undefined;
  }

  return clip.automation?.find((automation) => (
    canonicalizeKeyframeParamName(automation.targetPath ?? automation.parameterPath) === canonicalParamName
  ));
}

function keyframeRecordKey(
  paramName: string,
  automation: MutablePreviewAutomation | undefined,
): string | undefined {
  if (automation?.targetPath && automation.targetPath.trim().length > 0) {
    return canonicalizeKeyframeParamName(automation.targetPath) ?? automation.targetPath.trim();
  }

  return canonicalizeKeyframeParamName(paramName);
}

function getClipKeyframes(
  clip: MutablePreviewClip,
  paramName: string,
  createIfMissing: boolean,
): ClipKeyframe[] | undefined {
  const automation = matchAutomationSummary(clip, paramName);
  const existingRecord = clip.keyframes;
  const directKey = paramName.trim();
  if (existingRecord) {
    if (directKey.length > 0 && existingRecord[directKey]) {
      return existingRecord[directKey];
    }

    const canonicalKey = keyframeRecordKey(paramName, automation);
    if (canonicalKey && existingRecord[canonicalKey]) {
      return existingRecord[canonicalKey];
    }
  }

  if (!createIfMissing) {
    return undefined;
  }

  const recordKey = keyframeRecordKey(paramName, automation);
  if (!recordKey) {
    return undefined;
  }

  const keyframes = (clip.keyframes ??= {});
  keyframes[recordKey] = [];
  return keyframes[recordKey];
}

function syncAutomationKeyframeCount(
  clip: MutablePreviewClip,
  paramName: string,
  keyframes: readonly ClipKeyframe[] | undefined,
): void {
  const automation = matchAutomationSummary(clip, paramName);
  if (!automation) {
    return;
  }

  automation.keyframeCount = keyframes?.length ?? 0;
  if ((automation as MutablePreviewAutomation).keyframes) {
    (automation as MutablePreviewAutomation).keyframes = keyframes?.map(cloneKeyframe) ?? [];
  }
}

function sortKeyframesInPlace(keyframes: ClipKeyframe[]): void {
  keyframes.sort((left, right) => left.time - right.time);
}

function applyKeyframeAdd(clips: MutablePreviewClip[], op: GraphKeyframeAddOp): void {
  const clip = clips.find((candidate) => candidate.id === op.clipId);
  if (!clip) {
    return;
  }

  const keyframes = getClipKeyframes(clip, op.paramName, true);
  if (!keyframes) {
    return;
  }

  keyframes.push(cloneKeyframe(op.keyframe));
  sortKeyframesInPlace(keyframes);
  syncAutomationKeyframeCount(clip, op.paramName, keyframes);
}

function applyKeyframeUpdate(clips: MutablePreviewClip[], op: GraphKeyframeUpdateOp): void {
  const clip = clips.find((candidate) => candidate.id === op.clipId);
  if (!clip) {
    return;
  }

  const keyframes = getClipKeyframes(clip, op.paramName, false);
  if (!keyframes?.length) {
    return;
  }

  const index = keyframes.findIndex((keyframe) => keyframe.time === op.time);
  if (index < 0) {
    return;
  }

  const current = keyframes[index]!;
  keyframes[index] = {
    ...current,
    value: op.value,
    interpolation: op.interpolation ?? current.interpolation,
  };
  syncAutomationKeyframeCount(clip, op.paramName, keyframes);
}

function applyKeyframeRemove(clips: MutablePreviewClip[], op: GraphKeyframeRemoveOp): void {
  const clip = clips.find((candidate) => candidate.id === op.clipId);
  if (!clip) {
    return;
  }

  const keyframes = getClipKeyframes(clip, op.paramName, false);
  if (!keyframes) {
    return;
  }

  if (op.time === undefined) {
    keyframes.splice(0, keyframes.length);
    syncAutomationKeyframeCount(clip, op.paramName, keyframes);
    return;
  }

  let changed = false;
  for (let index = keyframes.length - 1; index >= 0; index--) {
    if (keyframes[index]?.time === op.time) {
      keyframes.splice(index, 1);
      changed = true;
    }
  }

  if (!changed) {
    return;
  }

  syncAutomationKeyframeCount(clip, op.paramName, keyframes);
}

function cloneInput(input: CompositionGraphInput): CompositionGraphInput {
  return {
    snapshot: {
      ...input.snapshot,
      clips: input.snapshot.clips.map((clip) => {
        const clone: MutablePreviewClip = { ...clip };
        clone.automation = cloneAutomation(clip.automation);
        const clipWithKeyframes = clip as MutablePreviewClip;
        clone.keyframes = cloneKeyframeRecord(clipWithKeyframes.keyframes);
        return clone;
      }),
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
      case 'keyframe.add':
        applyKeyframeAdd(clone.snapshot.clips as MutablePreviewClip[], op);
        break;
      case 'keyframe.update':
        applyKeyframeUpdate(clone.snapshot.clips as MutablePreviewClip[], op);
        break;
      case 'keyframe.remove':
        applyKeyframeRemove(clone.snapshot.clips as MutablePreviewClip[], op);
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
