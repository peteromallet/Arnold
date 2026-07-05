import { afterEach, describe, expect, it, vi } from 'vitest';
import type { RenderArtifact, TimelineShaderSummary, TimelineSnapshot } from '@reigh/editor-sdk';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ClipKeyframe } from '@/tools/video-editor/types/index.ts';
import type { CompositionGraphInput } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import * as graphProjector from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import {
  applyGraphPreviewOperations,
  type GraphShaderAssignOp,
} from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import { COMPOSITION_DIAGNOSTIC_CODE } from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';

type HostClipSummary = TimelineSnapshot['clips'][number] & {
  keyframes?: Record<string, ClipKeyframe[]>;
};

type HostTrackSummary = TimelineSnapshot['tracks'][number];

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

function timelineSnapshot(
  clips: HostClipSummary[],
  tracks: readonly HostTrackSummary[] = [],
): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips,
    tracks,
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
    'transition:com.example.transitions:dissolve': [
      indexEntry('transition:com.example.transitions:dissolve'),
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

function transitionClip(overrides: Partial<HostClipSummary> = {}): HostClipSummary {
  return {
    id: 'clip-1',
    track: 'V1',
    at: 0,
    clipType: 'video',
    duration: 24,
    managed: false,
    transition: {
      id: 'clip-1.transition.dissolve',
      clipId: 'clip-1',
      transitionType: 'dissolve',
      duration: 1,
      managed: true,
      managedBy: 'com.example.transitions',
    },
    ...overrides,
  };
}

function trackSummary(overrides: Partial<HostTrackSummary> = {}): HostTrackSummary {
  return {
    id: 'A1',
    kind: 'audio',
    label: 'Audio 1',
    muted: false,
    ...overrides,
  };
}

function artifact(overrides: Partial<RenderArtifact> = {}): RenderArtifact {
  return {
    id: 'artifact.audio',
    route: 'browser-export',
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://exports/audio.wav',
      mimeType: 'audio/wav',
    },
    mediaKind: 'audio',
    determinism: 'deterministic',
    boundary: {
      source: 'worker',
      target: 'artifact-store',
      route: 'browser-export',
      failureBehavior: 'block-export',
    },
    consumedMaterialRefs: [],
    ...overrides,
  };
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

describe('patchPreview material.attach diagnostics', () => {
  it('surfaces transition mask missing diagnostics at the attach boundary without writing bindings', () => {
    const input: CompositionGraphInput = {
      ...graphInput(transitionClip()),
      materialSlotDeclarations: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.dissolve',
          },
          slotName: 'transition-mask',
        },
      ],
      materialRuntime: projectHostMaterialRuntime({
        materialRefs: [],
      }),
    };
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'material.attach',
        owner: {
          kind: 'transition',
          clipId: 'clip-1',
          ownerId: 'clip-1.transition.dissolve',
        },
        slotName: 'transition-mask',
        materialRefId: 'mat-missing',
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    const clonedClip = projectedClip(projectorSpy);

    expect(preview?.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED,
        severity: 'error',
        detail: expect.objectContaining({
          clipId: 'clip-1',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          materialSlot: 'transition-mask',
          materialRefId: 'mat-missing',
          refKey: 'transition:com.example.transitions:dissolve',
          resolverState: 'resolved',
          nextAction: expect.objectContaining({
            kind: 'materialize',
          }),
          repairAction: expect.objectContaining({
            kind: 'materialize',
            ownerKind: 'transition',
            ownerId: 'clip-1.transition.dissolve',
            materialSlot: 'transition-mask',
            materialRefId: 'mat-missing',
          }),
        }),
      }),
    ]));
    expect(clonedInput?.materialSlotBindings).toBeUndefined();
    expect(clonedClip.transition?.params?.materialSlots).toBeUndefined();
    expect(sourceClip.transition?.params?.materialSlots).toBeUndefined();
  });

  it('surfaces transition mask route-incompatible diagnostics at the attach boundary without mutating the source clip', () => {
    const input: CompositionGraphInput = {
      ...graphInput(transitionClip()),
      materialSlotDeclarations: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.dissolve',
          },
          slotName: 'transition-mask',
        },
      ],
      materialRuntime: projectHostMaterialRuntime({
        materialRefs: [
          {
            id: 'mat-route',
            mediaKind: 'image',
            locator: {
              kind: 'asset-registry',
              uri: 'asset://mat-route',
            },
            determinism: 'deterministic',
            replacementPolicy: 'materialize-on-export',
          },
        ],
        materialStatuses: [
          {
            materialRefId: 'mat-route',
            state: 'resolved',
            detail: {
              quality: 'route-incompatible',
            },
          },
        ],
        requestedRoutes: ['preview'],
        canonicalRoutes: ['worker-export'],
      }),
    };
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'material.attach',
        owner: {
          kind: 'transition',
          clipId: 'clip-1',
          ownerId: 'clip-1.transition.dissolve',
        },
        slotName: 'transition-mask',
        materialRefId: 'mat-route',
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    const clonedClip = projectedClip(projectorSpy);

    expect(preview?.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
        severity: 'error',
        detail: expect.objectContaining({
          clipId: 'clip-1',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          materialSlot: 'transition-mask',
          materialRefId: 'mat-route',
          refKey: 'transition:com.example.transitions:dissolve',
          resolverState: 'resolved',
          routeScope: 'worker-export',
          nextAction: expect.objectContaining({
            kind: 'select-route',
            route: 'worker-export',
          }),
          repairAction: expect.objectContaining({
            kind: 'select-route',
            route: 'worker-export',
            ownerKind: 'transition',
            ownerId: 'clip-1.transition.dissolve',
            materialSlot: 'transition-mask',
            materialRefId: 'mat-route',
          }),
        }),
      }),
    ]));
    expect(clonedInput?.materialSlotBindings).toBeUndefined();
    expect(clonedClip.transition?.params?.materialSlots).toBeUndefined();
    expect(sourceClip.transition?.params?.materialSlots).toBeUndefined();
  });
});

describe('patchPreview media.attach and media.remove operations', () => {
  it('attaches an audio artifact to a cloned audio track target without mutating the source input', () => {
    const input: CompositionGraphInput = {
      snapshot: timelineSnapshot([
        {
          id: 'clip-audio',
          track: 'A1',
          at: 0,
          clipType: 'audio',
          duration: 48,
          managed: false,
        },
      ], [trackSummary()]),
      contributionIndex: contributionIndex(),
      artifacts: [artifact()],
    };
    const sourceTracks = input.snapshot.tracks;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'media.attach',
        owner: {
          kind: 'track',
          trackId: 'A1',
          clipId: 'clip-audio',
        },
        artifactId: 'artifact.audio',
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;

    expect(clonedInput?.snapshot.tracks).not.toBe(sourceTracks);
    expect(clonedInput?.mediaTrackBindings).toEqual([
      {
        owner: {
          kind: 'track',
          trackId: 'A1',
          clipId: 'clip-audio',
        },
        artifactId: 'artifact.audio',
      },
    ]);
    expect(input.mediaTrackBindings).toBeUndefined();
    expect(preview?.diagnostics.some((diagnostic) => diagnostic.severity === 'error')).toBe(false);
  });

  it('removes cloned audio-track media attachments without mutating the source input', () => {
    const input: CompositionGraphInput = {
      snapshot: timelineSnapshot([
        {
          id: 'clip-audio',
          track: 'A1',
          at: 0,
          clipType: 'audio',
          duration: 48,
          managed: false,
        },
      ], [trackSummary()]),
      contributionIndex: contributionIndex(),
      artifacts: [artifact()],
      mediaTrackBindings: [
        {
          owner: {
            kind: 'track',
            trackId: 'A1',
            clipId: 'clip-audio',
          },
          artifactId: 'artifact.audio',
        },
      ],
    };
    const sourceBindings = input.mediaTrackBindings;
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    applyGraphPreviewOperations(input, [
      {
        kind: 'media.remove',
        owner: {
          kind: 'track',
          trackId: 'A1',
          clipId: 'clip-audio',
        },
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;

    expect(clonedInput?.mediaTrackBindings).toEqual([]);
    expect(input.mediaTrackBindings).toBe(sourceBindings);
    expect(input.mediaTrackBindings).toEqual([
      {
        owner: {
          kind: 'track',
          trackId: 'A1',
          clipId: 'clip-audio',
        },
        artifactId: 'artifact.audio',
      },
    ]);
  });

  it('rejects media.attach for non-audio track targets without writing bindings', () => {
    const input: CompositionGraphInput = {
      snapshot: timelineSnapshot([], [trackSummary({ id: 'V1', kind: 'visual', label: 'Video 1' })]),
      contributionIndex: contributionIndex(),
      artifacts: [artifact()],
    };
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'media.attach',
        owner: {
          kind: 'track',
          trackId: 'V1',
        },
        artifactId: 'artifact.audio',
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;

    expect(preview?.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: COMPOSITION_DIAGNOSTIC_CODE.NON_BINDABLE_TARGET,
        severity: 'error',
        detail: expect.objectContaining({
          trackId: 'V1',
          trackKind: 'visual',
          targetKind: 'track',
        }),
      }),
    ]));
    expect(clonedInput?.mediaTrackBindings).toBeUndefined();
    expect(input.mediaTrackBindings).toBeUndefined();
  });

  it('keeps material.attach limited to material slots by rejecting audio artifacts there', () => {
    const input: CompositionGraphInput = {
      ...graphInput(transitionClip()),
      artifacts: [artifact()],
      materialSlotDeclarations: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.dissolve',
          },
          slotName: 'transition-mask',
        },
      ],
      materialRuntime: projectHostMaterialRuntime({
        materialRefs: [],
      }),
    };
    const projectorSpy = vi.spyOn(graphProjector, 'projectCompositionGraph');

    const preview = applyGraphPreviewOperations(input, [
      {
        kind: 'material.attach',
        owner: {
          kind: 'transition',
          clipId: 'clip-1',
          ownerId: 'clip-1.transition.dissolve',
        },
        slotName: 'transition-mask',
        materialRefId: 'artifact.audio',
      },
    ]);

    const clonedInput = projectorSpy.mock.calls[0]?.[0] as CompositionGraphInput | undefined;
    const clonedClip = projectedClip(projectorSpy);

    expect(preview?.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: COMPOSITION_DIAGNOSTIC_CODE.TARGET_VALUE_TYPE_ERROR,
        severity: 'error',
        detail: expect.objectContaining({
          clipId: 'clip-1',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          materialSlot: 'transition-mask',
          materialRefId: 'artifact.audio',
          artifactId: 'artifact.audio',
          mediaKind: 'audio',
        }),
      }),
    ]));
    expect(clonedInput?.materialSlotBindings).toBeUndefined();
    expect(clonedClip.transition?.params?.materialSlots).toBeUndefined();
  });
});
