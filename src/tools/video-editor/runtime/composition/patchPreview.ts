/**
 * Internal graph patch preview — host-owned shader, material-slot, and
 * keyframe preview operations.
 *
 * This module provides host-owned preview logic that clones a composition
 * graph input, applies internal patch operations, re-projects the graph,
 * and returns a {@link CompositionGraphPreviewResult}.  No public SDK
 * timeline patch families are added for M1b.
 *
 * @module composition/patchPreview
 * @hostOwned — NOT exported through public SDK contracts.
 */

import type {
  CompositionGraphPreviewResult,
  ExtensionDiagnostic,
  TimelineSnapshot,
  TimelineShaderSummary,
} from '@reigh/editor-sdk';
import type {
  CompositionGraphInput,
  CompositionGraphMaterialSlotBinding,
  CompositionGraphMaterialSlotOwnerIdentity,
} from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import type {
  CaptureCollisionPolicy,
  ClipKeyframe,
  KeyframeInterpolation,
} from '@/tools/video-editor/types/index.ts';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import {
  resolveMaterialAttachEntry,
} from '@/tools/video-editor/runtime/composition/materialRuntime.ts';

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
 * Internal attach operation: assign a material ref to a descriptor-declared
 * named slot owned by a transition or effect instance.
 */
export interface GraphMaterialAttachOp {
  readonly kind: 'material.attach';
  readonly owner: CompositionGraphMaterialSlotOwnerIdentity;
  readonly slotName: string;
  readonly materialRefId: string;
}

/**
 * Internal remove operation: clear a descriptor-declared named material slot.
 */
export interface GraphMaterialRemoveOp {
  readonly kind: 'material.remove';
  readonly owner: CompositionGraphMaterialSlotOwnerIdentity;
  readonly slotName: string;
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
  | GraphMaterialAttachOp
  | GraphMaterialRemoveOp
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
  effects?: MutablePreviewEffect[];
  transition?: MutablePreviewTransition;
  materialRefs?: MutablePreviewMaterialRefSummary[];
};

type MutablePreviewAutomation = NonNullable<TimelineSnapshot['clips'][number]['automation']>[number] & {
  keyframes?: ClipKeyframe[];
};

type MutablePreviewEffect = NonNullable<TimelineSnapshot['clips'][number]['effects']>[number] & {
  params?: Record<string, unknown>;
};

type MutablePreviewTransition = NonNullable<TimelineSnapshot['clips'][number]['transition']> & {
  params?: Record<string, unknown>;
};

type MutablePreviewMaterialRefSummary = NonNullable<TimelineSnapshot['clips'][number]['materialRefs']>[number] & {
  ownerId?: string;
  ownerKind?: CompositionGraphMaterialSlotOwnerIdentity['kind'];
  slotName?: string;
};

type MutablePreviewSnapshot = TimelineSnapshot & {
  clips: MutablePreviewClip[];
  shaders?: TimelineShaderSummary[];
  materialRefs?: MutablePreviewMaterialRefSummary[];
};

type MutableGraphPreviewInput = CompositionGraphInput & {
  snapshot: MutablePreviewSnapshot;
  materialSlotBindings?: CompositionGraphMaterialSlotBinding[];
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

function cloneParams(
  params: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!params) {
    return undefined;
  }

  const clone: Record<string, unknown> = { ...params };
  const materialSlots = clone.materialSlots;
  if (materialSlots && typeof materialSlots === 'object' && !Array.isArray(materialSlots)) {
    clone.materialSlots = { ...(materialSlots as Record<string, unknown>) };
  }
  return clone;
}

function cloneEffects(
  effects: TimelineSnapshot['clips'][number]['effects'],
): MutablePreviewEffect[] | undefined {
  if (!effects?.length) {
    return effects ? [] : undefined;
  }

  return effects.map((effect) => ({
    ...effect,
    params: cloneParams(effect.params),
  }));
}

function cloneTransition(
  transition: TimelineSnapshot['clips'][number]['transition'],
): MutablePreviewTransition | undefined {
  if (!transition) {
    return undefined;
  }

  return {
    ...transition,
    params: cloneParams(transition.params),
  };
}

function cloneMaterialRefs(
  materialRefs: TimelineSnapshot['clips'][number]['materialRefs'],
): MutablePreviewMaterialRefSummary[] | undefined {
  if (!materialRefs?.length) {
    return materialRefs ? [] : undefined;
  }

  return materialRefs.map((materialRef) => ({ ...materialRef }));
}

function cloneMaterialSlotBindings(
  bindings: readonly CompositionGraphMaterialSlotBinding[] | undefined,
): CompositionGraphMaterialSlotBinding[] | undefined {
  if (!bindings?.length) {
    return bindings ? [] : undefined;
  }

  return bindings.map((binding) => ({
    owner: { ...binding.owner },
    slotName: binding.slotName,
    materialRefId: binding.materialRefId,
  }));
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

function normalizeMaterialSlotName(slotName: string): string | undefined {
  const normalized = slotName.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function ownerKey(owner: CompositionGraphMaterialSlotOwnerIdentity): string {
  return `${owner.kind}:${owner.clipId}:${owner.ownerId}`;
}

function sameOwner(
  left: CompositionGraphMaterialSlotOwnerIdentity,
  right: CompositionGraphMaterialSlotOwnerIdentity,
): boolean {
  return ownerKey(left) === ownerKey(right);
}

function hasDeclaredMaterialSlot(
  input: CompositionGraphInput,
  owner: CompositionGraphMaterialSlotOwnerIdentity,
  slotName: string,
): boolean {
  return (input.materialSlotDeclarations ?? []).some((declaration) => (
    sameOwner(declaration.owner, owner) && declaration.slotName === slotName
  ));
}

function findMaterialSlotOwner(
  clips: MutablePreviewClip[],
  owner: CompositionGraphMaterialSlotOwnerIdentity,
): MutablePreviewEffect | MutablePreviewTransition | undefined {
  const clip = clips.find((candidate) => candidate.id === owner.clipId);
  if (!clip) {
    return undefined;
  }

  if (owner.kind === 'transition') {
    return clip.transition?.id === owner.ownerId ? clip.transition : undefined;
  }

  return clip.effects?.find((effect) => effect.id === owner.ownerId);
}

function ensureMaterialSlotRecord(
  owner: MutablePreviewEffect | MutablePreviewTransition,
): Record<string, unknown> {
  owner.params ??= {};
  const current = owner.params.materialSlots;
  if (current && typeof current === 'object' && !Array.isArray(current)) {
    return current as Record<string, unknown>;
  }

  const next: Record<string, unknown> = {};
  owner.params.materialSlots = next;
  return next;
}

function removeMaterialSlotRecord(
  owner: MutablePreviewEffect | MutablePreviewTransition,
  slotName: string,
): void {
  const params = owner.params;
  if (!params) {
    return;
  }

  const record = params.materialSlots;
  if (!record || typeof record !== 'object' || Array.isArray(record)) {
    return;
  }

  delete (record as Record<string, unknown>)[slotName];
  if (Object.keys(record as Record<string, unknown>).length === 0) {
    delete params.materialSlots;
  }
}

function syncSnapshotMaterialRefs(snapshot: MutablePreviewSnapshot): void {
  const materialRefs = snapshot.clips.flatMap((clip) => clip.materialRefs ?? []);
  snapshot.materialRefs = materialRefs.length > 0
    ? materialRefs.map((materialRef) => ({ ...materialRef }))
    : undefined;
}

function syncClipMaterialRefSummary(
  snapshot: MutablePreviewSnapshot,
  owner: CompositionGraphMaterialSlotOwnerIdentity,
  slotName: string,
  materialRefId: string | undefined,
  materialDetail?: Readonly<{
    mediaKind?: string;
    determinism?: MutablePreviewMaterialRefSummary['determinism'];
  }>,
): void {
  const clip = snapshot.clips.find((candidate) => candidate.id === owner.clipId);
  if (!clip) {
    return;
  }

  const nextRefs = [...(clip.materialRefs ?? [])].filter((materialRef) => !(
    materialRef.ownerKind === owner.kind
    && materialRef.ownerId === owner.ownerId
    && materialRef.slotName === slotName
  ));

  if (materialRefId) {
    nextRefs.push({
      id: materialRefId,
      clipId: owner.clipId,
      ownerId: owner.ownerId,
      ownerKind: owner.kind,
      slotName,
      ...(materialDetail?.mediaKind ? { mediaKind: materialDetail.mediaKind } : {}),
      ...(materialDetail?.determinism ? { determinism: materialDetail.determinism } : {}),
    });
  }

  clip.materialRefs = nextRefs.length > 0 ? nextRefs : undefined;
  syncSnapshotMaterialRefs(snapshot);
}

function ensureMutableMaterialBindings(
  input: MutableGraphPreviewInput,
): CompositionGraphMaterialSlotBinding[] {
  const existing = input.materialSlotBindings;
  if (existing) {
    return existing;
  }

  const next = cloneMaterialSlotBindings(input.materialSlotBindings) ?? [];
  input.materialSlotBindings = next;
  return next;
}

function applyMaterialAttach(
  input: MutableGraphPreviewInput,
  op: GraphMaterialAttachOp,
  diagnostics: ExtensionDiagnostic[],
): void {
  const slotName = normalizeMaterialSlotName(op.slotName);
  if (!slotName || !hasDeclaredMaterialSlot(input, op.owner, slotName)) {
    return;
  }

  const owner = findMaterialSlotOwner(input.snapshot.clips, op.owner);
  if (!owner) {
    return;
  }

  const resolution = resolveMaterialAttachEntry(input.materialRuntime, op.materialRefId);
  if (!resolution.ok) {
    diagnostics.push(resolution.diagnostic);
    return;
  }

  const materialSlots = ensureMaterialSlotRecord(owner);
  materialSlots[slotName] = resolution.entry.materialRef.id;

  const bindings = ensureMutableMaterialBindings(input);
  const nextBinding: CompositionGraphMaterialSlotBinding = {
    owner: { ...op.owner },
    slotName,
    materialRefId: resolution.entry.materialRef.id,
  };
  const existingIndex = bindings.findIndex((binding) => (
    sameOwner(binding.owner, op.owner) && binding.slotName === slotName
  ));
  if (existingIndex >= 0) {
    bindings[existingIndex] = nextBinding;
  } else {
    bindings.push(nextBinding);
  }

  syncClipMaterialRefSummary(
    input.snapshot,
    op.owner,
    slotName,
    resolution.entry.materialRef.id,
    {
      mediaKind: resolution.entry.materialRef.mediaKind,
      determinism: resolution.entry.materialRef.determinism,
    },
  );
}

function applyMaterialRemove(
  input: MutableGraphPreviewInput,
  op: GraphMaterialRemoveOp,
): void {
  const slotName = normalizeMaterialSlotName(op.slotName);
  if (!slotName || !hasDeclaredMaterialSlot(input, op.owner, slotName)) {
    return;
  }

  const owner = findMaterialSlotOwner(input.snapshot.clips, op.owner);
  if (!owner) {
    return;
  }

  removeMaterialSlotRecord(owner, slotName);

  const bindings = ensureMutableMaterialBindings(input);
  const existingIndex = bindings.findIndex((binding) => (
    sameOwner(binding.owner, op.owner) && binding.slotName === slotName
  ));
  if (existingIndex >= 0) {
    bindings.splice(existingIndex, 1);
  }

  syncClipMaterialRefSummary(input.snapshot, op.owner, slotName, undefined);
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
        clone.effects = cloneEffects(clip.effects);
        clone.transition = cloneTransition(clip.transition);
        clone.materialRefs = cloneMaterialRefs(clip.materialRefs);
        return clone;
      }),
      shaders: input.snapshot.shaders ? cloneShaders(input.snapshot.shaders) : [],
      materialRefs: input.snapshot.materialRefs ? input.snapshot.materialRefs.map((materialRef) => ({ ...materialRef })) : undefined,
    },
    contributionIndex: input.contributionIndex,
    materialRuntime: input.materialRuntime,
    materialSlotDeclarations: input.materialSlotDeclarations,
    materialSlotBindings: cloneMaterialSlotBindings(input.materialSlotBindings),
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

  const clone = cloneInput(input) as MutableGraphPreviewInput;
  const operationDiagnostics: ExtensionDiagnostic[] = [];

  for (const op of operations) {
    switch (op.kind) {
      case 'shader.assign':
        applyShaderAssign(clone.snapshot.shaders ?? [], op);
        break;
      case 'shader.remove':
        applyShaderRemove(clone.snapshot.shaders ?? [], op);
        break;
      case 'material.attach':
        applyMaterialAttach(clone, op, operationDiagnostics);
        break;
      case 'material.remove':
        applyMaterialRemove(clone, op);
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
    diagnostics: operationDiagnostics.length > 0
      ? Object.freeze([...projected.diagnostics, ...operationDiagnostics])
      : projected.diagnostics,
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
