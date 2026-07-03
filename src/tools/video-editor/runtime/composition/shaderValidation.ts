import type { TimelineShaderSummary } from '@reigh/editor-sdk';
import type { ContributionIndex } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { TimelineShaderScope } from '@/tools/video-editor/types/index.ts';

export interface CompositionShaderIdentity {
  readonly scope: TimelineShaderScope;
  readonly extensionId: string;
  readonly contributionId: string;
  readonly shaderId: string;
}

export interface CompositionShaderStackEntry extends CompositionShaderIdentity {
  readonly clipId?: string;
}

export interface ShaderScopeOccupied<T extends CompositionShaderStackEntry = CompositionShaderStackEntry> {
  readonly scope: TimelineShaderScope;
  readonly clipId?: string;
  readonly existing: T;
  readonly incoming: T;
  readonly shaderCount: number;
  readonly message: string;
}

export type ShaderStackValidationResult<T extends CompositionShaderStackEntry = CompositionShaderStackEntry> =
  | { readonly ok: true }
  | { readonly ok: false; readonly occupied: ShaderScopeOccupied<T> };

export interface ShaderCompositionValidationResult<
  T extends CompositionShaderStackEntry = CompositionShaderStackEntry,
> {
  readonly shaders: readonly T[] | undefined;
  readonly occupied: readonly ShaderScopeOccupied<T>[];
}

export function sameCompositionShaderIdentity(
  left: CompositionShaderIdentity,
  right: CompositionShaderIdentity,
): boolean {
  return (
    left.scope === right.scope
    && left.extensionId === right.extensionId
    && left.contributionId === right.contributionId
    && left.shaderId === right.shaderId
  );
}

export function shaderScopeOccupiedMessage(
  scope: TimelineShaderScope,
  existingShaderId: string,
  incomingShaderId: string,
  clipId?: string,
): string {
  if (scope === 'clip') {
    const target = clipId ? `clip "${clipId}"` : 'the clip scope';
    return `Cannot add shader "${incomingShaderId}" to ${target} because shader "${existingShaderId}" is already assigned. `
      + 'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
  }

  return `Cannot add postprocess shader "${incomingShaderId}" because postprocess shader "${existingShaderId}" is already assigned. `
    + 'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
}

export function createShaderScopeOccupied<T extends CompositionShaderStackEntry>(
  existing: T,
  incoming: T,
  shaderCount = 2,
): ShaderScopeOccupied<T> {
  return {
    scope: incoming.scope,
    clipId: incoming.scope === 'clip' ? incoming.clipId ?? existing.clipId : undefined,
    existing,
    incoming,
    shaderCount,
    message: shaderScopeOccupiedMessage(
      incoming.scope,
      existing.shaderId,
      incoming.shaderId,
      incoming.scope === 'clip' ? incoming.clipId ?? existing.clipId : undefined,
    ),
  };
}

export function validateShaderAssignment<T extends CompositionShaderStackEntry>(
  existing: T | undefined,
  incoming: T,
): ShaderStackValidationResult<T> {
  if (!existing || sameCompositionShaderIdentity(existing, incoming)) {
    return { ok: true };
  }

  return {
    ok: false,
    occupied: createShaderScopeOccupied(existing, incoming),
  };
}

export function validateShaderStack<T extends CompositionShaderStackEntry>(
  stack: readonly T[],
): ShaderStackValidationResult<T> {
  if (stack.length < 2) {
    return { ok: true };
  }

  return {
    ok: false,
    occupied: createShaderScopeOccupied(stack[0]!, stack[1]!, stack.length),
  };
}

function shaderContributionScopedKey(
  shader: Pick<TimelineShaderSummary, 'extensionId' | 'contributionId'>,
): string {
  return `shader:${shader.extensionId}:${shader.contributionId}`;
}

export function projectShaderRefs(
  shaderSummaries: readonly TimelineShaderSummary[] | undefined,
  contributionIndex: ContributionIndex | undefined,
): readonly TimelineShaderSummary[] | undefined {
  if (!shaderSummaries?.length || !contributionIndex) {
    return shaderSummaries;
  }

  let changed = false;
  const projected: TimelineShaderSummary[] = [];
  for (const shader of shaderSummaries) {
    if (shader.enabled === false) {
      projected.push(shader);
      continue;
    }

    const entries = contributionIndex[shaderContributionScopedKey(shader)];
    const projectedEntry = entries
      ?.find((entry) => entry.kind === 'shader' && entry.status === 'active' && entry.projection.projected);
    if (!projectedEntry) {
      if (entries) {
        changed = true;
        continue;
      }
      projected.push(shader);
      continue;
    }

    projected.push(shader);
  }

  return changed ? projected : shaderSummaries;
}

function shaderCompositionKey(shader: CompositionShaderStackEntry & { readonly enabled?: boolean }): string | undefined {
  if (shader.enabled === false) return undefined;
  if (shader.scope === 'clip') return `clip:${shader.clipId ?? ''}`;
  return 'postprocess';
}

export function validateShaderComposition<T extends CompositionShaderStackEntry & { readonly enabled?: boolean }>(
  stack: readonly T[] | undefined,
): ShaderCompositionValidationResult<T> {
  if (!stack?.length) {
    return { shaders: stack, occupied: [] };
  }

  let changed = false;
  const firstByScope = new Map<string, T>();
  const filteredShaders: T[] = [];
  const occupied: ShaderScopeOccupied<T>[] = [];

  for (const shader of stack) {
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

    changed = true;
    occupied.push(createShaderScopeOccupied(existing, shader));
  }

  return {
    shaders: changed ? filteredShaders : stack,
    occupied,
  };
}
