import { describe, expect, it } from 'vitest';
import {
  createShaderScopeOccupied,
  projectShaderRefs,
  sameCompositionShaderIdentity,
  shaderScopeOccupiedMessage,
  validateShaderComposition,
  validateShaderAssignment,
  validateShaderStack,
  type CompositionShaderStackEntry,
} from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type { ContributionIndex } from '@/tools/video-editor/runtime/extensionSurface.ts';

const clipShader = (overrides: Partial<CompositionShaderStackEntry> = {}): CompositionShaderStackEntry => ({
  scope: 'clip',
  clipId: 'clip-1',
  extensionId: 'com.example.shader',
  contributionId: 'clip-glow-shader',
  shaderId: 'shader.clipGlow',
  ...overrides,
});

const postprocessShader = (
  overrides: Partial<CompositionShaderStackEntry> = {},
): CompositionShaderStackEntry => ({
  scope: 'postprocess',
  extensionId: 'com.example.shader',
  contributionId: 'post-grade-shader',
  shaderId: 'shader.postGrade',
  ...overrides,
});

function shaderContributionIndex(
  entries: readonly {
    contributionId: string;
    status?: 'active' | 'inactive-reserved' | 'disabled' | 'invalid';
    projected?: boolean;
    projectionEligible?: boolean;
    source?: 'descriptor-array' | 'preserved-record';
  }[],
): ContributionIndex {
  const index: Record<string, ContributionIndex[string]> = {};

  for (const entry of entries) {
    const scopedKey = `shader:com.example.shader:${entry.contributionId}`;
    index[scopedKey] = [{
      scopedKey,
      kind: 'shader',
      extensionId: 'com.example.shader',
      contributionId: entry.contributionId,
      status: entry.status ?? 'active',
      diagnostics: [],
      duplicateOrdinal: 0,
      projectionEligible: entry.projectionEligible ?? true,
      projection: {
        duplicateOrdinal: 0,
        eligible: entry.projectionEligible ?? true,
        projected: entry.projected ?? true,
        source: entry.source ?? 'descriptor-array',
      },
    }];
  }

  return index;
}

describe('shaderValidation', () => {
  it('compares shader identity by scope, extension, contribution, and shader ID', () => {
    expect(sameCompositionShaderIdentity(
      clipShader(),
      clipShader(),
    )).toBe(true);

    expect(sameCompositionShaderIdentity(
      clipShader(),
      clipShader({ contributionId: 'clip-edge-shader', shaderId: 'shader.clipEdge' }),
    )).toBe(false);

    expect(sameCompositionShaderIdentity(
      clipShader(),
      postprocessShader({
        contributionId: 'clip-glow-shader',
        shaderId: 'shader.clipGlow',
      }),
    )).toBe(false);
  });

  it('generates exact occupied-scope messages for clip and postprocess scopes', () => {
    expect(shaderScopeOccupiedMessage(
      'clip',
      'shader.clipGlow',
      'shader.clipEdge',
      'clip-1',
    )).toBe(
      'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
    );

    expect(shaderScopeOccupiedMessage(
      'postprocess',
      'shader.postGrade',
      'shader.postVignette',
    )).toBe(
      'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
    );
  });

  it('creates occupied payloads with existing/incoming records and derived clip scope', () => {
    const occupied = createShaderScopeOccupied(
      clipShader(),
      clipShader({
        contributionId: 'clip-edge-shader',
        shaderId: 'shader.clipEdge',
      }),
      3,
    );

    expect(occupied).toEqual({
      scope: 'clip',
      clipId: 'clip-1',
      existing: clipShader(),
      incoming: clipShader({
        contributionId: 'clip-edge-shader',
        shaderId: 'shader.clipEdge',
      }),
      shaderCount: 3,
      message: 'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
    });
  });

  it('validates assignments by allowing same-identity updates and rejecting conflicting scopes', () => {
    expect(validateShaderAssignment(undefined, clipShader())).toEqual({ ok: true });
    expect(validateShaderAssignment(clipShader(), clipShader())).toEqual({ ok: true });

    expect(validateShaderAssignment(
      clipShader(),
      clipShader({
        contributionId: 'clip-edge-shader',
        shaderId: 'shader.clipEdge',
      }),
    )).toEqual({
      ok: false,
      occupied: {
        scope: 'clip',
        clipId: 'clip-1',
        existing: clipShader(),
        incoming: clipShader({
          contributionId: 'clip-edge-shader',
          shaderId: 'shader.clipEdge',
        }),
        shaderCount: 2,
        message: 'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
      },
    });
  });

  it('validates shader stacks by returning the first occupied-scope collision', () => {
    expect(validateShaderStack([clipShader()])).toEqual({ ok: true });

    expect(validateShaderStack([
      postprocessShader(),
      postprocessShader({
        contributionId: 'post-vignette-shader',
        shaderId: 'shader.postVignette',
      }),
    ])).toEqual({
      ok: false,
      occupied: {
        scope: 'postprocess',
        clipId: undefined,
        existing: postprocessShader(),
        incoming: postprocessShader({
          contributionId: 'post-vignette-shader',
          shaderId: 'shader.postVignette',
        }),
        shaderCount: 2,
        message: 'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
      },
    });
  });

  it('projects snapshot shader refs through the contribution index without rewriting unmatched entries', () => {
    const visible = {
      id: 'clip-1:shader:shader.clipGlow',
      ...clipShader(),
      enabled: true,
    };
    const disabled = {
      id: 'clip-1:shader:shader.clipGlow.disabled',
      ...clipShader({
        contributionId: 'clip-glow-disabled',
        shaderId: 'shader.clipGlow.disabled',
      }),
      enabled: true,
    };
    const projected = projectShaderRefs(
      [visible, disabled],
      shaderContributionIndex([
        { contributionId: 'clip-glow-shader' },
        {
          contributionId: 'clip-glow-disabled',
          status: 'disabled',
          projected: false,
          projectionEligible: false,
          source: 'preserved-record',
        },
      ]),
    );

    expect(projected).toEqual([visible]);
  });

  it('validates shader composition by preserving winners and reporting each occupied duplicate', () => {
    const first = {
      id: 'clip-1:shader:shader.clipGlow',
      ...clipShader(),
      enabled: true,
    };
    const duplicate = {
      id: 'clip-1:shader:shader.clipEdge',
      ...clipShader({
        contributionId: 'clip-edge-shader',
        shaderId: 'shader.clipEdge',
      }),
      enabled: true,
    };
    const disabled = {
      id: 'clip-1:shader:shader.clipDisabled',
      ...clipShader({
        contributionId: 'clip-disabled-shader',
        shaderId: 'shader.clipDisabled',
      }),
      enabled: false,
    };

    expect(validateShaderComposition([first, duplicate, disabled])).toEqual({
      shaders: [first, disabled],
      occupied: [
        {
          scope: 'clip',
          clipId: 'clip-1',
          existing: first,
          incoming: duplicate,
          shaderCount: 2,
          message: 'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
        },
      ],
    });
  });
});
