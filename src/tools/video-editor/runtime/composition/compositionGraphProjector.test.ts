import { describe, expect, it } from 'vitest';
import type { TimelineShaderSummary, TimelineSnapshot } from '@reigh/editor-sdk';
import {
  projectCompositionGraph,
  TIMELINE_POSTPROCESS_NODE_ID,
  type CompositionGraphInput,
} from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';

function shaderSummary(
  overrides: Partial<TimelineShaderSummary> = {},
): TimelineShaderSummary {
  return {
    id: 'clip-1:shader:shader.clipGlow',
    shaderId: 'shader.clipGlow',
    scope: 'clip',
    clipId: 'clip-1',
    extensionId: 'com.example.shader',
    contributionId: 'clip-glow',
    enabled: true,
    ...overrides,
  };
}

function timelineSnapshot(overrides: Partial<TimelineSnapshot> = {}): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      {
        id: 'clip-1',
        track: 'V1',
        at: 0,
        clipType: 'video',
        duration: 48,
        managed: false,
      },
      {
        id: 'clip-2',
        track: 'V2',
        at: 48,
        clipType: 'video',
        duration: 48,
        managed: false,
      },
      {
        id: 'clip-automation',
        track: 'V3',
        at: 96,
        clipType: 'automation',
        duration: 24,
        managed: false,
      },
    ],
    tracks: [],
    assetKeys: [],
    app: {},
    shaders: [
      shaderSummary(),
      shaderSummary({
        id: 'postprocess:shader:shader.postGrade',
        shaderId: 'shader.postGrade',
        scope: 'postprocess',
        clipId: undefined,
        contributionId: 'post-grade',
      }),
      shaderSummary({
        id: 'clip-2:shader:shader.missing',
        clipId: 'clip-2',
        shaderId: 'shader.missing',
        contributionId: 'missing-shader',
      }),
    ],
    ...overrides,
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
    'shader:com.example.shader:clip-glow': [
      indexEntry('shader:com.example.shader:clip-glow'),
    ],
    'shader:com.example.shader:post-grade': [
      indexEntry('shader:com.example.shader:post-grade'),
    ],
    'effect:com.example.effects:glow': [
      indexEntry('effect:com.example.effects:glow', {
        projection: {
          duplicateOrdinal: 0,
          eligible: true,
          projected: false,
          source: 'preserved-record',
        },
      }),
    ],
  };
}

function project(overrides: Partial<CompositionGraphInput> = {}) {
  return projectCompositionGraph({
    snapshot: timelineSnapshot(),
    contributionIndex: contributionIndex(),
    ...overrides,
  });
}

describe('compositionGraphProjector', () => {
  it('projects clip, timeline-postprocess, and contribution nodes plus shader consumes edges', () => {
    const graph = project();

    expect(graph.nodes).toEqual([
      expect.objectContaining({
        id: 'clip:clip-1',
        kind: 'clip',
        detail: expect.objectContaining({
          clipId: 'clip-1',
          trackId: 'V1',
        }),
      }),
      expect.objectContaining({
        id: 'clip:clip-2',
        kind: 'clip',
      }),
      expect.objectContaining({
        id: 'clip:clip-automation',
        kind: 'clip',
      }),
      expect.objectContaining({
        id: TIMELINE_POSTPROCESS_NODE_ID,
        kind: 'timeline-postprocess',
      }),
      expect.objectContaining({
        id: 'contribution:effect:com.example.effects:glow',
        kind: 'contribution',
        ref: {
          kind: 'effect',
          extensionId: 'com.example.effects',
          contributionId: 'glow',
        },
      }),
      expect.objectContaining({
        id: 'contribution:shader:com.example.shader:clip-glow',
        kind: 'contribution',
        ref: {
          kind: 'shader',
          extensionId: 'com.example.shader',
          contributionId: 'clip-glow',
        },
      }),
      expect.objectContaining({
        id: 'contribution:shader:com.example.shader:post-grade',
        kind: 'contribution',
      }),
      expect.objectContaining({
        id: 'contribution:shader:com.example.shader:missing-shader',
        kind: 'contribution',
      }),
    ]);

    expect(graph.edges).toEqual([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          shaderId: 'shader.clipGlow',
          scope: 'clip',
          refKey: 'shader:com.example.shader:clip-glow',
        }),
      }),
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: TIMELINE_POSTPROCESS_NODE_ID,
        targetNodeId: 'contribution:shader:com.example.shader:post-grade',
        detail: expect.objectContaining({
          shaderId: 'shader.postGrade',
          scope: 'postprocess',
        }),
      }),
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-2',
        targetNodeId: 'contribution:shader:com.example.shader:missing-shader',
      }),
    ]);

    expect(graph.referenceStates).toEqual([
      {
        refKey: 'shader:com.example.shader:clip-glow',
        state: 'resolved',
        nodeIds: ['clip:clip-1'],
      },
      {
        refKey: 'shader:com.example.shader:post-grade',
        state: 'resolved',
        nodeIds: [TIMELINE_POSTPROCESS_NODE_ID],
      },
      {
        refKey: 'shader:com.example.shader:missing-shader',
        state: 'missing',
        nodeIds: ['clip:clip-2'],
      },
    ]);

    expect(graph.diagnostics).toEqual([
      expect.objectContaining({
        code: 'composition/missing-ref',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-2',
          refKey: 'shader:com.example.shader:missing-shader',
          refState: 'missing',
          scope: 'clip',
          shaderId: 'shader.missing',
        }),
      }),
    ]);
  });

  it('treats undefined runtime overlay and an explicitly empty runtime overlay as equivalent no-ops', () => {
    const baseGraph = project();
    const graphWithEmptyOverlay = project({
      runtimeOverlay: {
        shaders: [],
      },
    });

    expect(graphWithEmptyOverlay).toEqual(baseGraph);
  });

  it('projects animates edges for enabled automation summaries using canonical target-path detail', () => {
    const baseSnapshot = timelineSnapshot();
    const graph = project({
      snapshot: {
        ...baseSnapshot,
        clips: [
          ...baseSnapshot.clips,
          {
            id: 'clip-automation-2',
            track: 'V4',
            at: 120,
            clipType: 'automation',
            duration: 12,
            managed: false,
            automation: [
              {
                contributionId: 'glow',
                parameterPath: 'params.intensity',
                keyframeCount: 3,
                enabled: true,
              },
              {
                contributionId: 'glow',
                parameterPath: 'params.disabled',
                keyframeCount: 1,
                enabled: false,
              },
            ],
          },
        ],
      },
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        sourceNodeId: 'clip:clip-automation-2',
        targetNodeId: 'contribution:effect:com.example.effects:glow',
        detail: expect.objectContaining({
          contributionId: 'glow',
          parameterPath: 'params.intensity',
          targetKind: 'clip-param',
          targetPath: 'intensity',
          keyframeCount: 3,
          refKey: 'effect:com.example.effects:glow',
        }),
      }),
    ]));
    expect(graph.edges).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          parameterPath: 'params.disabled',
        }),
      }),
    ]));
  });

  it('projects binds-live edges only for resolved live bindings using canonical target-path detail', () => {
    const baseSnapshot = timelineSnapshot();
    const graph = project({
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) => (
          clip.id === 'clip-1'
            ? {
                ...clip,
                liveBindings: [
                  {
                    bindingId: 'live-opacity',
                    clipId: 'clip-1',
                    sourceId: 'source-opacity',
                    sourceKind: 'webcam',
                    targetKind: 'clip-param',
                    targetParamName: 'params.opacity',
                    status: 'resolved',
                  },
                  {
                    bindingId: 'live-shader',
                    clipId: 'clip-1',
                    sourceId: 'source-shader',
                    sourceKind: 'midi',
                    targetKind: 'shader-uniform',
                    targetMaterialId: 'clip-glow',
                    targetParamName: 'intensity',
                    status: 'resolved',
                  },
                  {
                    bindingId: 'live-active',
                    clipId: 'clip-1',
                    sourceId: 'source-active',
                    sourceKind: 'generated',
                    targetKind: 'clip-param',
                    targetParamName: 'params.scale',
                    status: 'active',
                  },
                ],
              }
            : clip
        )),
      },
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'binds-live',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'clip:clip-1',
        detail: expect.objectContaining({
          bindingId: 'live-opacity',
          sourceId: 'source-opacity',
          targetKind: 'clip-param',
          targetPath: 'opacity',
        }),
      }),
      expect.objectContaining({
        kind: 'binds-live',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          bindingId: 'live-shader',
          sourceId: 'source-shader',
          targetKind: 'shader-uniform',
          targetMaterialId: 'clip-glow',
          targetPath: 'uniforms.intensity',
          refKey: 'shader:com.example.shader:clip-glow',
        }),
      }),
    ]));
    expect(graph.edges).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'binds-live',
        detail: expect.objectContaining({
          bindingId: 'live-active',
        }),
      }),
    ]));
  });
});
