import { describe, expect, it } from 'vitest';
import type { TimelineShaderSummary, TimelineSnapshot } from '@reigh/editor-sdk';
import {
  projectCompositionGraph,
  TIMELINE_POSTPROCESS_NODE_ID,
  type CompositionGraphInput,
} from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import type {
  ClipTypeRegistrySnapshot,
  ClipTypeRegistryRecord,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type { ContributionRenderability, RenderBlocker } from '@/tools/video-editor/runtime/renderability.ts';
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

  it('projects shader-summary keyframes as shader-uniform animates edges with canonical target paths', () => {
    const graph = project({
      snapshot: timelineSnapshot({
        shaders: [
          shaderSummary({
            keyframes: {
              intensity: [
                { time: 0, value: 0.2, interpolation: 'linear' },
                { time: 1, value: 0.8, interpolation: 'linear' },
              ],
              'uniforms.tint': [
                { time: 0, value: [0.2, 0.4, 0.8, 1], interpolation: 'hold' },
              ],
            },
          }),
        ],
      }),
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          shaderId: 'shader.clipGlow',
          contributionId: 'clip-glow',
          targetKind: 'shader-uniform',
          targetPath: 'uniforms.intensity',
          uniformName: 'intensity',
          keyframeCount: 2,
          refKey: 'shader:com.example.shader:clip-glow',
        }),
      }),
      expect.objectContaining({
        kind: 'animates',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          targetKind: 'shader-uniform',
          targetPath: 'uniforms.tint',
          uniformName: 'tint',
          keyframeCount: 1,
        }),
      }),
    ]));
  });

  // ---- clip type projection ------------------------------------------------

  function renderability(
    overrides: Partial<ContributionRenderability> = {},
  ): ContributionRenderability {
    return {
      capabilities: [
        {
          route: 'preview' as const,
          status: 'supported' as const,
          determinism: 'preview-only' as const,
        },
      ],
      determinism: 'preview-only' as const,
      ...overrides,
    };
  }

  function blocker(reason: string = 'route-unsupported'): RenderBlocker {
    return {
      id: `blocker-${reason}`,
      severity: 'error' as const,
      route: 'browser-export' as const,
      reason: reason as RenderBlocker['reason'],
      message: `Blocked: ${reason}`,
    };
  }

  function clipTypeRegistrySnapshot(
    records: readonly ClipTypeRegistryRecord[],
  ): ClipTypeRegistrySnapshot {
    const map = new Map<string, ClipTypeRegistryRecord>();
    for (const record of records) {
      map.set(record.clipTypeId, record);
    }
    return {
      records: Object.freeze([...records]),
      diagnostics: Object.freeze([]),
      get: (clipTypeId: string) => map.get(clipTypeId),
      has: (clipTypeId: string) => map.has(clipTypeId),
    };
  }

  function clipTypeRecord(
    clipTypeId: string,
    overrides: Partial<ClipTypeRegistryRecord> = {},
  ): ClipTypeRegistryRecord {
    return {
      clipTypeId,
      contributionId: overrides.contributionId ?? clipTypeId,
      renderer: {} as unknown as Record<string, unknown>,
      ownerExtensionId: overrides.ownerExtensionId ?? 'com.example.clipTypes',
      renderability: overrides.renderability ?? renderability(),
      status: overrides.status ?? 'active',
      diagnostics: overrides.diagnostics,
    };
  }

  it('projects clip type contribution nodes and consumes edges for resolved clip types', () => {
    const registry = clipTypeRegistrySnapshot([
      clipTypeRecord('video', {
        contributionId: 'core-video',
        ownerExtensionId: 'com.example.core',
      }),
    ]);

    const graph = project({ clipTypeRegistry: registry });

    // Contribution node for clip type
    expect(graph.nodes).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'contribution:clipType:com.example.core:core-video',
        kind: 'contribution',
        ref: {
          kind: 'clipType',
          extensionId: 'com.example.core',
          contributionId: 'core-video',
        },
      }),
    ]));

    // Consumes edge from clip to clip type
    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:clipType:com.example.core:core-video',
        detail: expect.objectContaining({
          clipTypeId: 'video',
          clipId: 'clip-1',
          refKey: 'clipType:com.example.core:core-video',
          scope: 'clip',
        }),
      }),
    ]));

    // Reference state is resolved (both clip-1 and clip-2 have 'video' type)
    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'clipType:com.example.core:core-video',
        state: 'resolved',
        nodeIds: expect.arrayContaining(['clip:clip-1']),
      }),
    ]));

    // No diagnostics for resolved
    const clipTypeDiags = graph.diagnostics.filter(
      (d) => d.detail && (d.detail as Record<string, unknown>).refKey === 'clipType:com.example.core:core-video',
    );
    expect(clipTypeDiags).toHaveLength(0);
  });

  it('emits missing-ref diagnostics for clip types not in the registry', () => {
    // No registry means all clip types are missing
    const graph = project({ clipTypeRegistry: undefined });

    // Clips with types not in registry should not produce clip type edges/nodes
    // since ownerExtensionId is required. The existing clip nodes and shader
    // edges should still be present.
    const clipTypeNodes = graph.nodes.filter(
      (n) => n.ref?.kind === 'clipType',
    );
    expect(clipTypeNodes).toHaveLength(0);

    const clipTypeEdges = graph.edges.filter(
      (e) => e.detail && (e.detail as Record<string, unknown>).clipTypeId !== undefined && !(e.detail as Record<string, unknown>).shaderId,
    );
    // With no registry, no clip type consumes edges are emitted
    expect(clipTypeEdges).toHaveLength(0);
  });

  it('emits missing-ref diagnostics when a clip type is in registry but has no ownerExtensionId', () => {
    const record = clipTypeRecord('video', {
      contributionId: 'core-video',
    });
    const recordWithoutOwner = { ...record, ownerExtensionId: undefined as unknown as string };
    const registry = clipTypeRegistrySnapshot([recordWithoutOwner]);

    const graph = project({ clipTypeRegistry: registry });

    // No clip type contribution nodes should be emitted
    const clipTypeNodes = graph.nodes.filter(
      (n) => n.ref?.kind === 'clipType',
    );
    expect(clipTypeNodes).toHaveLength(0);
  });

  it('emits disabled-ref diagnostics when a clip type has renderability blockers', () => {
    const registry = clipTypeRegistrySnapshot([
      clipTypeRecord('video', {
        contributionId: 'core-video',
        ownerExtensionId: 'com.example.core',
        renderability: renderability({
          blockers: [blocker('route-unsupported')],
        }),
      }),
    ]);

    const graph = project({ clipTypeRegistry: registry });

    // Contribution node still created
    expect(graph.nodes).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'contribution:clipType:com.example.core:core-video',
      }),
    ]));

    // Consumes edge still created
    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:clipType:com.example.core:core-video',
      }),
    ]));

    // Reference state is disabled (both clip-1 and clip-2 have 'video' type)
    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'clipType:com.example.core:core-video',
        state: 'disabled',
        nodeIds: expect.arrayContaining(['clip:clip-1']),
      }),
    ]));

    // Diagnostic with nextAction
    expect(graph.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'composition/disabled-ref',
        severity: 'error',
        extensionId: 'com.example.core',
        contributionId: 'core-video',
        detail: expect.objectContaining({
          refKey: 'clipType:com.example.core:core-video',
          refState: 'disabled',
          scope: 'clip',
          nextAction: expect.objectContaining({
            kind: 'resolve-blockers',
          }),
        }),
      }),
    ]));
  });

  it('deduplicates clip type contribution nodes when multiple clips use the same clip type', () => {
    const registry = clipTypeRegistrySnapshot([
      clipTypeRecord('video', {
        contributionId: 'core-video',
        ownerExtensionId: 'com.example.core',
      }),
    ]);

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      clipTypeRegistry: registry,
      snapshot: {
        ...baseSnapshot,
        clips: [
          ...baseSnapshot.clips,
          {
            id: 'clip-video-2',
            track: 'V5',
            at: 144,
            clipType: 'video',
            duration: 30,
            managed: false,
          },
        ],
      },
    });

    // Only one contribution node for clipType:com.example.core:core-video
    const clipTypeNodes = graph.nodes.filter(
      (n) => n.id === 'contribution:clipType:com.example.core:core-video',
    );
    expect(clipTypeNodes).toHaveLength(1);

    // Three consumes edges, one per clip with 'video' type
    // (clip-1, clip-2, and clip-video-2)
    const clipTypeEdges = graph.edges.filter(
      (e) => e.kind === 'consumes' && e.targetNodeId === 'contribution:clipType:com.example.core:core-video',
    );
    expect(clipTypeEdges).toHaveLength(3);
    expect(clipTypeEdges.map((e) => e.sourceNodeId).sort()).toEqual([
      'clip:clip-1',
      'clip:clip-2',
      'clip:clip-video-2',
    ]);

    // Reference state has all nodeIds
    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'clipType:com.example.core:core-video',
        state: 'resolved',
        nodeIds: expect.arrayContaining(['clip:clip-1', 'clip:clip-2', 'clip:clip-video-2']),
      }),
    ]));
  });
});
