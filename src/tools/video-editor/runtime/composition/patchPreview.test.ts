import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TimelineShaderSummary, TimelineSnapshot } from '@reigh/editor-sdk';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ClipKeyframe } from '@/tools/video-editor/types/index.ts';
import type { CompositionGraphInput } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import * as graphProjector from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import {
  applyGraphPreviewOperations,
  type GraphShaderAssignOp,
} from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import { COMPOSITION_DIAGNOSTIC_CODE } from '@/tools/video-editor/runtime/composition/diagnostics.ts';

type HostClipSummary = TimelineSnapshot['clips'][number] & {
  keyframes?: Record<string, ClipKeyframe[]>;
};

function keyframe(
  time: number,
  value: number | string | boolean,
  interpolation: ClipKeyframe['interpolation'] = 'linear',
): ClipKeyframe {
  return { time, value, interpolation };
}

function automationClip(overrides: Partial<HostClipSummary> = {}): HostClipSummary {
  return {
    id: 'clip-automation',
    track: 'V1',
    at: 0,
    clipType: 'automation',
    duration: 24,
    managed: false,
    automation: [
      {
        contributionId: 'glow',
        parameterPath: 'params.opacity',
        targetPath: 'opacity',
        keyframeCount: 1,
        enabled: true,
      },
    ],
    keyframes: {
      opacity: [keyframe(0, 0.2)],
    },
    ...overrides,
  };
}

function timelineSnapshot(clips: HostClipSummary[]): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips,
    tracks: [],
    assetKeys: [],
    app: {},
    shaders: [],
  };
}

function indexEntry(
  scopedKey: string,
  overrides: Partial<ContributionIndexEntry> = {},
): ContributionIndexEntry {
  const [kind, extensionId, contributionId] = scopedKey.split(':');
  return {
    scopedKey,
    kind: kind!,
    extensionId: extensionId!,
    contributionId: contributionId!,
    status: overrides.status ?? 'active',
    packageState: overrides.packageState,
    diagnostics: overrides.diagnostics ?? [],
    duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
    projectionEligible: overrides.projectionEligible ?? true,
    projection: overrides.projection ?? {
      duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
      eligible: overrides.projectionEligible ?? true,
      projected: true,
      source: 'descriptor-array',
    },
    renderId: overrides.renderId,
    routeFit: overrides.routeFit,
    resolutionPolicy: overrides.resolutionPolicy,
  };
}

function contributionIndex(): ContributionIndex {
  return {
    'effect:com.example.effects:glow': [
      indexEntry('effect:com.example.effects:glow'),
    ],
  };
}

function graphInput(clip: HostClipSummary): CompositionGraphInput {
  return {
    snapshot: timelineSnapshot([clip]),
    contributionIndex: contributionIndex(),
  };
}

function projectedClip(spy: ReturnType<typeof vi.spyOn>): HostClipSummary {
  const input = spy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
  const clip = input?.snapshot.clips[0] as HostClipSummary | undefined;
  if (!clip) {
    throw new Error('Expected projectCompositionGraph to receive a cloned clip.');
  }
  return clip;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('patchPreview keyframe graph operations', () => {
  it('adds keyframes against cloned input without mutating the source snapshot and updates animates edge detail', () => {
    const input = graphInput(automationClip());
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'keyframe.add',
        clipId: 'clip-automation',
        paramName: 'params.opacity',
        keyframe: keyframe(12, 0.8),
      },
    ]);

    const clonedClip = projectedClip(projectorSpy);

    expect(clonedClip).not.toBe(sourceClip);
    expect(clonedClip.automation).not.toBe(sourceClip.automation);
    expect(clonedClip.keyframes).not.toBe(sourceClip.keyframes);
    expect(clonedClip.keyframes?.opacity).toEqual([
      keyframe(0, 0.2),
      keyframe(12, 0.8),
    ]);
    expect(clonedClip.automation?.[0]?.keyframeCount).toBe(2);
    expect(sourceClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(sourceClip.automation?.[0]?.keyframeCount).toBe(1);
    expect(preview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: 'opacity',
          keyframeCount: 2,
        }),
      }),
    ]));
  });

  it('updates targeted cloned keyframes while preserving source values', () => {
    const input = graphInput(automationClip());
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    applyGraphPreviewOperations(input, [
      {
        kind: 'keyframe.update',
        clipId: 'clip-automation',
        paramName: 'opacity',
        time: 0,
        value: 0.5,
        interpolation: 'hold',
      },
    ]);

    const clonedClip = projectedClip(projectorSpy);

    expect(clonedClip.keyframes?.opacity).toEqual([keyframe(0, 0.5, 'hold')]);
    expect(clonedClip.automation?.[0]?.keyframeCount).toBe(1);
    expect(sourceClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(sourceClip.automation?.[0]?.keyframeCount).toBe(1);
  });

  it('removes targeted cloned keyframes and re-projects the reduced animates keyframeCount', () => {
    const input = graphInput(automationClip({
      automation: [
        {
          contributionId: 'glow',
          parameterPath: 'params.opacity',
          targetPath: 'opacity',
          keyframeCount: 2,
          enabled: true,
        },
      ],
      keyframes: {
        opacity: [keyframe(0, 0.2), keyframe(12, 0.8)],
      },
    }));
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'keyframe.remove',
        clipId: 'clip-automation',
        paramName: 'params.opacity',
        time: 12,
      },
    ]);

    const clonedClip = projectedClip(projectorSpy);

    expect(clonedClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(clonedClip.automation?.[0]?.keyframeCount).toBe(1);
    expect(sourceClip.keyframes?.opacity).toEqual([keyframe(0, 0.2), keyframe(12, 0.8)]);
    expect(sourceClip.automation?.[0]?.keyframeCount).toBe(2);
    expect(preview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: 'opacity',
          keyframeCount: 1,
        }),
      }),
    ]));
  });

  it('leaves cloned automation/keyframe state unchanged for invalid keyframe targets', () => {
    const input = graphInput(automationClip());
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'keyframe.add',
        clipId: 'missing-clip',
        paramName: 'params.opacity',
        keyframe: keyframe(12, 0.8),
      },
      {
        kind: 'keyframe.update',
        clipId: 'clip-automation',
        paramName: 'params.missing',
        time: 0,
        value: 0.9,
      },
      {
        kind: 'keyframe.remove',
        clipId: 'clip-automation',
        paramName: 'params.missing',
        time: 0,
      },
    ]);

    const clonedClip = projectedClip(projectorSpy);

    expect(clonedClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(clonedClip.automation?.[0]?.keyframeCount).toBe(1);
    expect(sourceClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(sourceClip.automation?.[0]?.keyframeCount).toBe(1);
    expect(preview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: 'opacity',
          keyframeCount: 1,
        }),
      }),
    ]));
  });
});

// ---------------------------------------------------------------------------
// Shader test helpers
// ---------------------------------------------------------------------------

function clipShaderSummary(overrides: Partial<TimelineShaderSummary> = {}): TimelineShaderSummary {
  return {
    id: 'clip-1:shader:shader.clipGlow',
    shaderId: 'shader.clipGlow',
    scope: 'clip',
    clipId: 'clip-1',
    extensionId: 'com.example.shader',
    contributionId: 'clip-glow-shader',
    enabled: true,
    ...overrides,
  };
}

function postprocessShaderSummary(overrides: Partial<TimelineShaderSummary> = {}): TimelineShaderSummary {
  return {
    id: 'postprocess:shader:shader.postGrade',
    shaderId: 'shader.postGrade',
    scope: 'postprocess',
    clipId: undefined,
    extensionId: 'com.example.shader',
    contributionId: 'post-grade-shader',
    enabled: true,
    ...overrides,
  };
}

function shaderAssignOp(shader: TimelineShaderSummary): GraphShaderAssignOp {
  return { kind: 'shader.assign', shader };
}

function snapshotWithShaders(shaders: TimelineShaderSummary[]): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [],
    tracks: [],
    assetKeys: [],
    app: {},
    shaders,
  };
}

function inputWithShaders(shaders: TimelineShaderSummary[]): CompositionGraphInput {
  return {
    snapshot: snapshotWithShaders(shaders),
    contributionIndex: contributionIndex(),
  };
}

// ---------------------------------------------------------------------------
// Shader DUPLICATE_SCOPE guard tests
// ---------------------------------------------------------------------------

describe('patchPreview shader DUPLICATE_SCOPE guard', () => {
  it('rejects assigning a different shader to an occupied clip scope with a DUPLICATE_SCOPE diagnostic', () => {
    const existing = clipShaderSummary();
    const incoming = clipShaderSummary({
      shaderId: 'shader.clipEdge',
      contributionId: 'clip-edge-shader',
      id: 'clip-1:shader:shader.clipEdge',
    });

    const input = inputWithShaders([existing]);
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [shaderAssignOp(incoming)]);

    // Verify diagnostics contain the DUPLICATE_SCOPE error
    expect(preview).toBeDefined();
    const diagnostic = preview!.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
    );
    expect(diagnostic).toBeDefined();
    expect(diagnostic!.severity).toBe('error');
    expect(diagnostic!.detail).toEqual(
      expect.objectContaining({
        scope: 'clip',
        clipId: 'clip-1',
        extensionId: 'com.example.shader',
        contributionId: 'clip-edge-shader',
        shaderId: 'shader.clipEdge',
      }),
    );

    // The cloned input should still have only the original shader (incoming was rejected)
    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    expect(clonedInput?.snapshot.shaders).toHaveLength(1);
    expect(clonedInput?.snapshot.shaders?.[0]?.shaderId).toBe('shader.clipGlow');
  });

  it('rejects assigning a different shader to an occupied postprocess scope with a DUPLICATE_SCOPE diagnostic', () => {
    const existing = postprocessShaderSummary();
    const incoming = postprocessShaderSummary({
      shaderId: 'shader.postVignette',
      contributionId: 'post-vignette-shader',
      id: 'postprocess:shader:shader.postVignette',
    });

    const input = inputWithShaders([existing]);
    const preview = applyGraphPreviewOperations(input, [shaderAssignOp(incoming)]);

    expect(preview).toBeDefined();
    const diagnostic = preview!.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
    );
    expect(diagnostic).toBeDefined();
    expect(diagnostic!.severity).toBe('error');
    expect(diagnostic!.detail).toEqual(
      expect.objectContaining({
        scope: 'postprocess',
        extensionId: 'com.example.shader',
        contributionId: 'post-vignette-shader',
        shaderId: 'shader.postVignette',
      }),
    );
  });

  it('allows same-shader same-scope assignment (idempotent, consistent with validateShaderAssignment)', () => {
    const existing = clipShaderSummary();
    const sameShader = clipShaderSummary(); // same identity

    const input = inputWithShaders([existing]);
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [shaderAssignOp(sameShader)]);

    expect(preview).toBeDefined();

    // No DUPLICATE_SCOPE diagnostic expected for same-identity shader
    const duplicateDiag = preview!.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
    );
    expect(duplicateDiag).toBeUndefined();

    // The shader should still be present (replaced with same identity)
    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    expect(clonedInput?.snapshot.shaders).toHaveLength(1);
    expect(clonedInput?.snapshot.shaders?.[0]?.shaderId).toBe('shader.clipGlow');
  });

  it('allows assigning a shader to an empty scope (no pre-existing shader)', () => {
    const shader = clipShaderSummary();
    const input = inputWithShaders([]);
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [shaderAssignOp(shader)]);

    expect(preview).toBeDefined();

    // No DUPLICATE_SCOPE diagnostic expected for empty scope
    const duplicateDiag = preview!.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
    );
    expect(duplicateDiag).toBeUndefined();

    // The shader should be added
    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    expect(clonedInput?.snapshot.shaders).toHaveLength(1);
    expect(clonedInput?.snapshot.shaders?.[0]?.shaderId).toBe('shader.clipGlow');
  });

  it('does not mutate the source snapshot when rejecting a duplicate-scope assignment', () => {
    const existing = clipShaderSummary();
    const incoming = clipShaderSummary({
      shaderId: 'shader.clipEdge',
      contributionId: 'clip-edge-shader',
      id: 'clip-1:shader:shader.clipEdge',
    });

    const input = inputWithShaders([existing]);
    const sourceShaders = input.snapshot.shaders;

    applyGraphPreviewOperations(input, [shaderAssignOp(incoming)]);

    // Source snapshot must be unchanged
    expect(sourceShaders).toHaveLength(1);
    expect(sourceShaders?.[0]?.shaderId).toBe('shader.clipGlow');
    // Confirm it's the same reference (no mutation)
    expect(input.snapshot.shaders).toBe(sourceShaders);
  });
});
