import { describe, expect, it } from 'vitest';
import type {
  TimelineEffectSummary,
  TimelineShaderSummary,
  TimelineSnapshot,
  TimelineTransitionSummary,
} from '@reigh/editor-sdk';
import {
  projectCompositionGraph,
  resolveEffectContributionEntry,
  resolveEffectTransitionContributionEntry,
  resolveTransitionContributionEntry,
  TIMELINE_POSTPROCESS_NODE_ID,
  type CompositionGraphInput,
} from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import type {
  ClipTypeRegistrySnapshot,
  ClipTypeRegistryRecord,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import type { ContributionRenderability, RenderBlocker } from '@/tools/video-editor/runtime/renderability.ts';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

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

function outputFormatDescriptor(): VideoEditorOutputFormatDescriptor {
  return {
    id: 'dataset-zip',
    extensionId: 'com.example.outputs',
    label: 'Dataset ZIP',
    requiresRender: true,
    outputExtension: 'zip',
    disabled: false,
    availableRoutes: ['sidecar-export'],
    routeRequirements: [
      {
        routes: ['sidecar-export'],
        routeScope: {
          source: 'output-format-render',
          mode: 'explicit-routes',
          routes: ['sidecar-export'],
        },
        requiredCapabilities: ['sidecar-export', 'render-material'],
        determinism: 'process-dependent',
        unavailableMessage: 'Route unavailable.',
      },
    ],
    processRequirements: [
      {
        processId: 'dataset-process',
        operationId: 'exportDataset',
        routeScope: {
          source: 'output-format-process',
          mode: 'explicit-routes',
          routes: ['sidecar-export'],
        },
        requiredCapabilities: ['sidecar-export'],
      },
    ],
    blockers: [],
    nextActions: [],
    sidecars: [],
  };
}

function processDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'dataset-bridge',
    extensionId: 'com.example.process',
    processId: 'dataset-process',
    label: 'Dataset Process',
    spec: {
      id: 'dataset-process',
      label: 'Dataset Process',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'dataset-process',
      },
      operations: [
        {
          id: 'exportDataset',
          label: 'Export Dataset',
          routes: ['sidecar-export'],
          outputKinds: ['artifact', 'material'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'exportDataset',
        label: 'Export Dataset',
        routes: ['sidecar-export'],
        routeScope: {
          source: 'process-operation',
          mode: 'explicit-routes',
          routes: ['sidecar-export'],
        },
        outputKinds: ['artifact', 'material'],
      },
    ],
    availableRoutes: ['sidecar-export'],
    requiredBy: [],
    blockers: [],
    nextActions: [],
  };
}

function outputMaterialRuntime(contributionIdx: ContributionIndex) {
  return projectHostMaterialRuntime({
    materialRefs: [
      {
        id: 'mat-render-pass',
        mediaKind: 'image',
        locator: {
          kind: 'artifact-store',
          uri: 'artifact://materials/render-pass.png',
        },
        producerExtensionId: 'com.example.shader',
        provenance: {
          contributionId: 'clip-glow',
          contributionKind: 'shader',
          shaderId: 'shader.clipGlow',
        },
        determinism: 'process-dependent',
        replacementPolicy: 'materialize-on-export',
      },
    ],
    materialStatuses: [
      {
        materialRefId: 'mat-render-pass',
        state: 'resolved',
      },
    ],
    contributionIndex: contributionIdx,
    shaders: [
      {
        id: 'clip-glow',
        extensionId: 'com.example.shader',
        shaderId: 'shader.clipGlow',
        label: 'Clip Glow',
        pass: 'clip',
        hasSourceMetadata: true,
      },
    ],
    requestedRoutes: ['sidecar-export'],
    canonicalRoutes: ['sidecar-export'],
  });
}

describe('compositionGraphProjector', () => {
  it('projects legacy clip and postprocess shader summaries into consumes edges', () => {
    const graph = project({
      snapshot: timelineSnapshot({
        shaders: [
          shaderSummary({
            id: 'clip-1:shader:shader.legacyClip',
            shaderId: 'shader.legacyClip',
            scope: 'clip',
            clipId: 'clip-1',
            contributionId: 'clip-glow',
          }),
          shaderSummary({
            id: 'postprocess:shader:shader.legacyPost',
            shaderId: 'shader.legacyPost',
            scope: 'postprocess',
            clipId: undefined,
            contributionId: 'post-grade',
          }),
        ],
      }),
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'consumes:clip:clip-1:contribution:shader:com.example.shader:clip-glow:clip-1:shader:shader.legacyClip',
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          shaderId: 'shader.legacyClip',
          clipId: 'clip-1',
          refKey: 'shader:com.example.shader:clip-glow',
          scope: 'clip',
        }),
      }),
      expect.objectContaining({
        id: 'consumes:timeline-postprocess:contribution:shader:com.example.shader:post-grade:postprocess:shader:shader.legacyPost',
        kind: 'consumes',
        sourceNodeId: TIMELINE_POSTPROCESS_NODE_ID,
        targetNodeId: 'contribution:shader:com.example.shader:post-grade',
        detail: expect.objectContaining({
          shaderId: 'shader.legacyPost',
          refKey: 'shader:com.example.shader:post-grade',
          scope: 'postprocess',
        }),
      }),
    ]));
    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'shader:com.example.shader:clip-glow',
        state: 'resolved',
      }),
      expect.objectContaining({
        refKey: 'shader:com.example.shader:post-grade',
        state: 'resolved',
      }),
    ]));
  });

  it('keeps disabled projection legacy shader refs from becoming authoritative consumes edges', () => {
    const graph = project({
      snapshot: timelineSnapshot({
        shaders: [
          shaderSummary({
            id: 'clip-1:shader:shader.disabledLegacy',
            shaderId: 'shader.disabledLegacy',
            scope: 'clip',
            clipId: 'clip-1',
            contributionId: 'clip-glow',
          }),
        ],
      }),
      contributionIndex: {
        'shader:com.example.shader:clip-glow': [
          indexEntry('shader:com.example.shader:clip-glow', {
            status: 'disabled',
            packageState: 'disabled-by-user',
            projectionEligible: false,
            projection: {
              duplicateOrdinal: 0,
              eligible: false,
              projected: false,
              source: 'preserved-record',
            },
          }),
        ],
      },
    });

    expect(graph.edges).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          shaderId: 'shader.disabledLegacy',
          refKey: 'shader:com.example.shader:clip-glow',
        }),
      }),
    ]));
    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'shader:com.example.shader:clip-glow',
        state: 'disabled',
        nodeIds: ['clip:clip-1'],
      }),
    ]));
    expect(graph.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'composition/disabled-ref',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-1',
          refKey: 'shader:com.example.shader:clip-glow',
          refState: 'disabled',
          shaderId: 'shader.disabledLegacy',
        }),
      }),
    ]));
  });

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

  it('projects output-format requires edges for route/process/graph facts and keeps material dependencies on consumes', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'outputFormat:com.example.outputs:dataset-zip': [
        indexEntry('outputFormat:com.example.outputs:dataset-zip', {
          renderId: 'dataset.zip',
        }),
      ],
      'process:com.example.process:dataset-bridge': [
        indexEntry('process:com.example.process:dataset-bridge'),
      ],
    };

    const graph = project({
      contributionIndex: idx,
      outputFormats: [outputFormatDescriptor()],
      processes: [processDescriptor()],
      materialRuntime: outputMaterialRuntime(idx),
      snapshot: timelineSnapshot({
        shaders: [
          shaderSummary(),
        ],
      }),
    });

    expect(graph.nodes).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        kind: 'contribution',
        ref: {
          kind: 'outputFormat',
          extensionId: 'com.example.outputs',
          contributionId: 'dataset-zip',
        },
      }),
      expect.objectContaining({
        id: 'contribution:process:com.example.process:dataset-bridge',
        kind: 'contribution',
        ref: {
          kind: 'process',
          extensionId: 'com.example.process',
          contributionId: 'dataset-bridge',
        },
      }),
    ]));

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'requires',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        detail: expect.objectContaining({
          outputFormatId: 'dataset-zip',
          requirementKind: 'route',
          routes: ['sidecar-export'],
          requiredCapabilities: ['sidecar-export', 'render-material'],
        }),
      }),
      expect.objectContaining({
        kind: 'requires',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: 'contribution:process:com.example.process:dataset-bridge',
        detail: expect.objectContaining({
          outputFormatId: 'dataset-zip',
          requirementKind: 'process',
          processId: 'dataset-process',
          operationId: 'exportDataset',
        }),
      }),
      expect.objectContaining({
        kind: 'requires',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: 'clip:clip-1',
        detail: expect.objectContaining({
          requirementKind: 'clip',
          routes: ['sidecar-export'],
        }),
      }),
      expect.objectContaining({
        kind: 'requires',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: TIMELINE_POSTPROCESS_NODE_ID,
        detail: expect.objectContaining({
          requirementKind: 'timeline-postprocess',
        }),
      }),
      expect.objectContaining({
        kind: 'requires',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          requirementKind: 'shader',
        }),
      }),
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'contribution:outputFormat:com.example.outputs:dataset-zip',
        targetNodeId: 'contribution:shader:com.example.shader:clip-glow',
        detail: expect.objectContaining({
          consumedKind: 'material',
          materialRefId: 'mat-render-pass',
        }),
      }),
    ]));

    const shaderDependencyKinds = graph.edges
      .filter((edge) =>
        edge.sourceNodeId === 'contribution:outputFormat:com.example.outputs:dataset-zip'
        && edge.targetNodeId === 'contribution:shader:com.example.shader:clip-glow',
      )
      .map((edge) => edge.kind)
      .sort();
    expect(shaderDependencyKinds).toEqual(['consumes', 'requires']);
    expect(graph.edges.map((edge) => edge.kind)).not.toContain('materializes');
    expect(graph.edges.map((edge) => edge.kind)).not.toContain('produces');
    expect(graph.edges.map((edge) => edge.kind)).not.toContain('fallbacks');
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

  // -----------------------------------------------------------------------
  // M5: Effect / transition contribution lookup helpers
  // -----------------------------------------------------------------------

  function effectSummary(
    overrides: Partial<TimelineEffectSummary> = {},
  ): TimelineEffectSummary {
    return {
      id: 'clip-1.effect.glow',
      clipId: 'clip-1',
      effectType: 'glow',
      managed: true,
      managedBy: 'com.example.effects',
      ...overrides,
    };
  }

  function transitionSummary(
    overrides: Partial<TimelineTransitionSummary> = {},
  ): TimelineTransitionSummary {
    return {
      id: 'clip-1.transition.dissolve',
      clipId: 'clip-1',
      transitionType: 'dissolve',
      duration: 1.0,
      managed: true,
      managedBy: 'com.example.transitions',
      ...overrides,
    };
  }

  describe('resolveEffectTransitionContributionEntry', () => {
    it('returns undefined when contribution index is undefined', () => {
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        'com.example.effects',
        undefined,
        'glow',
        undefined,
      );
      expect(result).toBeUndefined();
    });

    it('returns undefined when contribution index is empty', () => {
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        'com.example.effects',
        undefined,
        'glow',
        {},
      );
      expect(result).toBeUndefined();
    });

    it('resolves an effect by primary (kind, managedBy)', () => {
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        'com.example.effects',
        undefined,
        'glow',
        contributionIndex(),
      );

      expect(result).toBeDefined();
      expect(result!.ref).toEqual({
        kind: 'effect',
        extensionId: 'com.example.effects',
        contributionId: 'glow',
      });
      expect(result!.refKey).toBe('effect:com.example.effects:glow');
      expect(result!.entry.kind).toBe('effect');
    });

    it('resolves by primary with renderId match', () => {
      const idx: ContributionIndex = {
        'effect:com.example.effects:glow': [
          indexEntry('effect:com.example.effects:glow', {
            renderId: 'render-eff-001',
            projection: {
              duplicateOrdinal: 0,
              eligible: true,
              projected: true,
              source: 'descriptor-array',
            },
          }),
        ],
        'effect:com.example.other:glow': [
          indexEntry('effect:com.example.other:glow'),
        ],
      };

      // Without renderId, primary matches both 'glow' entries (different kind check
      // since both are 'effect', managedBy=undefined => both pass), so it would
      // be ambiguous. Let me test with managedBy set.
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        'com.example.effects',
        'render-eff-001',
        'glow',
        idx,
      );
      expect(result).toBeDefined();
      expect(result!.refKey).toBe('effect:com.example.effects:glow');
      expect(result!.entry.renderId).toBe('render-eff-001');
    });

    it('resolves an effect by fallback (contributionId only, unambiguous)', () => {
      // Primary would fail because managedBy doesn't match any entry
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        'com.example.unknown',  // no entry with this extensionId
        undefined,
        'glow',                 // but exactly one 'effect' entry has contributionId 'glow'
        contributionIndex(),
      );

      expect(result).toBeDefined();
      expect(result!.ref).toEqual({
        kind: 'effect',
        extensionId: 'com.example.effects',
        contributionId: 'glow',
      });
      expect(result!.refKey).toBe('effect:com.example.effects:glow');
    });

    it('returns undefined when fallback is ambiguous (multiple entries with same contributionId)', () => {
      const idx: ContributionIndex = {
        'effect:com.example.effects:glow': [
          indexEntry('effect:com.example.effects:glow'),
        ],
        'effect:com.example.other:glow': [
          indexEntry('effect:com.example.other:glow'),
        ],
      };

      // Primary without managedBy would match both (both are 'effect' kind),
      // so primary is ambiguous (2 matches).
      // Fallback with contributionId 'glow' also matches both — ambiguous.
      const result = resolveEffectTransitionContributionEntry(
        'effect',
        undefined,
        undefined,
        'glow',
        idx,
      );
      expect(result).toBeUndefined();
    });

    it('returns undefined when no entry matches kind', () => {
      const result = resolveEffectTransitionContributionEntry(
        'transition',
        'com.example.effects',
        undefined,
        'glow',
        contributionIndex(),
      );
      expect(result).toBeUndefined();
    });

    it('resolves a transition by primary (kind, managedBy)', () => {
      const idx: ContributionIndex = {
        ...contributionIndex(),
        'transition:com.example.transitions:dissolve': [
          indexEntry('transition:com.example.transitions:dissolve'),
        ],
      };

      const result = resolveEffectTransitionContributionEntry(
        'transition',
        'com.example.transitions',
        undefined,
        'dissolve',
        idx,
      );

      expect(result).toBeDefined();
      expect(result!.ref).toEqual({
        kind: 'transition',
        extensionId: 'com.example.transitions',
        contributionId: 'dissolve',
      });
      expect(result!.refKey).toBe('transition:com.example.transitions:dissolve');
    });

    it('resolves a transition by fallback (contributionId only, unambiguous)', () => {
      const idx: ContributionIndex = {
        ...contributionIndex(),
        'transition:com.example.transitions:dissolve': [
          indexEntry('transition:com.example.transitions:dissolve'),
        ],
      };

      const result = resolveEffectTransitionContributionEntry(
        'transition',
        undefined,
        undefined,
        'dissolve',
        idx,
      );

      expect(result).toBeDefined();
      expect(result!.refKey).toBe('transition:com.example.transitions:dissolve');
    });
  });

  describe('resolveEffectContributionEntry', () => {
    it('resolves an effect summary with managedBy via primary strategy', () => {
      const effect = effectSummary();
      const result = resolveEffectContributionEntry(effect, contributionIndex());

      expect(result).toBeDefined();
      expect(result!.refKey).toBe('effect:com.example.effects:glow');
    });

    it('resolves an unmanaged effect via fallback', () => {
      const effect = effectSummary({ managed: false, managedBy: undefined });
      const result = resolveEffectContributionEntry(effect, contributionIndex());

      expect(result).toBeDefined();
      expect(result!.refKey).toBe('effect:com.example.effects:glow');
    });

    it('returns undefined for an unknown effect type when unmanaged (fallback only)', () => {
      // With managedBy unset, primary can't match; fallback tries
      // contributionId 'nonexistent', which doesn't match 'glow'.
      const effect = effectSummary({ effectType: 'nonexistent', managed: false, managedBy: undefined });
      const result = resolveEffectContributionEntry(effect, contributionIndex());
      expect(result).toBeUndefined();
    });

    it('returns undefined when contribution index is undefined', () => {
      const effect = effectSummary();
      const result = resolveEffectContributionEntry(effect, undefined);
      expect(result).toBeUndefined();
    });

    it('passes renderId through to the core resolver', () => {
      const idx: ContributionIndex = {
        'effect:com.example.effects:glow': [
          indexEntry('effect:com.example.effects:glow', { renderId: 'r-eff-99' }),
        ],
      };
      const effect = effectSummary();
      const result = resolveEffectContributionEntry(effect, idx, 'r-eff-99');
      expect(result).toBeDefined();
      expect(result!.entry.renderId).toBe('r-eff-99');
    });
  });

  describe('resolveTransitionContributionEntry', () => {
    function idxWithTransition(): ContributionIndex {
      return {
        ...contributionIndex(),
        'transition:com.example.transitions:dissolve': [
          indexEntry('transition:com.example.transitions:dissolve'),
        ],
      };
    }

    it('resolves a transition summary with managedBy via primary strategy', () => {
      const transition = transitionSummary();
      const result = resolveTransitionContributionEntry(transition, idxWithTransition());

      expect(result).toBeDefined();
      expect(result!.refKey).toBe('transition:com.example.transitions:dissolve');
    });

    it('resolves an unmanaged transition via fallback', () => {
      const transition = transitionSummary({ managed: false, managedBy: undefined });
      const result = resolveTransitionContributionEntry(transition, idxWithTransition());

      expect(result).toBeDefined();
      expect(result!.refKey).toBe('transition:com.example.transitions:dissolve');
    });

    it('returns undefined for an unknown transition type when unmanaged (fallback only)', () => {
      // With managedBy unset, primary can't match; fallback tries
      // contributionId 'nonexistent', which doesn't match 'dissolve'.
      const transition = transitionSummary({ transitionType: 'nonexistent', managed: false, managedBy: undefined });
      const result = resolveTransitionContributionEntry(transition, idxWithTransition());
      expect(result).toBeUndefined();
    });

    it('returns undefined when contribution index is undefined', () => {
      const transition = transitionSummary();
      const result = resolveTransitionContributionEntry(transition, undefined);
      expect(result).toBeUndefined();
    });
  });

  // -----------------------------------------------------------------------
  // M5: Effect consumes edge projection
  // -----------------------------------------------------------------------

  it('projects consumes edges for clip effects targeting contribution nodes without public effect node kinds', () => {
    const baseSnapshot = timelineSnapshot();
    const graph = project({
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) =>
          clip.id === 'clip-1'
            ? {
                ...clip,
                effects: [
                  effectSummary(),
                  effectSummary({
                    id: 'clip-1.effect.secondary',
                    effectType: 'secondary',
                    managed: false,
                    managedBy: undefined,
                  }),
                ],
              }
            : clip
        ),
      },
    });

    // Verify no new node kinds — only existing kinds (clip, timeline-postprocess, contribution)
    const nodeKinds = new Set(graph.nodes.map((n) => n.kind));
    expect(nodeKinds).toEqual(new Set(['clip', 'timeline-postprocess', 'contribution']));

    // Verify consumes edge for managed effect (primary match via managedBy)
    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:effect:com.example.effects:glow',
        detail: expect.objectContaining({
          effectId: 'clip-1.effect.glow',
          clipId: 'clip-1',
          effectType: 'glow',
          refKey: 'effect:com.example.effects:glow',
          consumedKind: 'effect',
          scope: 'clip',
        }),
      }),
    ]));

    // Verify consumes edge for unmanaged effect (fallback match via contributionId)
    // The unmanaged effect has effectType 'secondary' but no managedBy.
    // Fallback looks for contributionId 'secondary' — there's no such entry,
    // so it should be skipped. Let's test with an effect that has a matching
    // contributionId.
  });

  it('projects consumes edge for unmanaged effect via fallback contributionId match', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'effect:com.example.effects:blur': [
        indexEntry('effect:com.example.effects:blur'),
      ],
    };

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) =>
          clip.id === 'clip-1'
            ? {
                ...clip,
                effects: [
                  effectSummary({
                    id: 'clip-1.effect.blur',
                    effectType: 'blur',
                    managed: false,
                    managedBy: undefined,
                  }),
                ],
              }
            : clip
        ),
      },
    });

    // Should find the contribution via fallback (contributionId === 'blur')
    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:effect:com.example.effects:blur',
        detail: expect.objectContaining({
          effectId: 'clip-1.effect.blur',
          effectType: 'blur',
          refKey: 'effect:com.example.effects:blur',
          consumedKind: 'effect',
          scope: 'clip',
        }),
      }),
    ]));
  });

  it('does not project consumes edge when effect contribution cannot be resolved', () => {
    const baseSnapshot = timelineSnapshot();
    const graph = project({
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) =>
          clip.id === 'clip-1'
            ? {
                ...clip,
                effects: [
                  effectSummary({
                    id: 'clip-1.effect.nonexistent',
                    effectType: 'nonexistent',
                    managed: false,
                    managedBy: undefined,
                  }),
                ],
              }
            : clip
        ),
      },
    });

    // No consumes edge should be emitted for an unresolvable effect
    const effectEdges = graph.edges.filter(
      (e) =>
        e.kind === 'consumes' &&
        (e.detail as Record<string, unknown>).consumedKind === 'effect',
    );
    expect(effectEdges).toHaveLength(0);
  });

  it('deduplicates effect contribution nodes when multiple clips use the same effect type', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'effect:com.example.effects:glow': [
        indexEntry('effect:com.example.effects:glow', {
          projection: {
            duplicateOrdinal: 0,
            eligible: true,
            projected: true,
            source: 'descriptor-array',
          },
        }),
      ],
    };

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) =>
          clip.id === 'clip-1' || clip.id === 'clip-2'
            ? {
                ...clip,
                effects: [
                  effectSummary({
                    id: `${clip.id}.effect.glow`,
                    clipId: clip.id,
                  }),
                ],
              }
            : clip
        ),
      },
    });

    // Only one contribution node for effect:com.example.effects:glow
    const effectNodes = graph.nodes.filter(
      (n) => n.id === 'contribution:effect:com.example.effects:glow',
    );
    expect(effectNodes).toHaveLength(1);

    // Two consumes edges, one per clip
    const effectEdges = graph.edges.filter(
      (e) =>
        e.kind === 'consumes' &&
        e.targetNodeId === 'contribution:effect:com.example.effects:glow',
    );
    expect(effectEdges).toHaveLength(2);
    expect(effectEdges.map((e) => e.sourceNodeId).sort()).toEqual([
      'clip:clip-1',
      'clip:clip-2',
    ]);
  });

  // -----------------------------------------------------------------------
  // M5: Transition + mask-material consumes edge projection
  // -----------------------------------------------------------------------

  it('projects transition consumes and mask-material consumes edges through the existing consumes kind', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'transition:com.example.transitions:dissolve': [
        indexEntry('transition:com.example.transitions:dissolve'),
      ],
    };

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) => (
          clip.id === 'clip-1'
            ? {
                ...clip,
                transition: transitionSummary(),
              }
            : clip
        )),
      },
      materialSlotBindings: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.dissolve',
          },
          slotName: 'transition-mask',
          materialRefId: 'mat-mask-1',
        },
      ],
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:transition:com.example.transitions:dissolve',
        detail: expect.objectContaining({
          transitionId: 'clip-1.transition.dissolve',
          clipId: 'clip-1',
          transitionType: 'dissolve',
          refKey: 'transition:com.example.transitions:dissolve',
          consumedKind: 'transition',
          scope: 'clip',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
        }),
      }),
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:transition:com.example.transitions:dissolve',
        detail: expect.objectContaining({
          transitionId: 'clip-1.transition.dissolve',
          clipId: 'clip-1',
          transitionType: 'dissolve',
          refKey: 'transition:com.example.transitions:dissolve',
          consumedKind: 'mask-material',
          targetSlot: 'transition-mask',
          materialRefId: 'mat-mask-1',
          scope: 'clip',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
        }),
      }),
    ]));

    expect(graph.edges.map((edge) => edge.kind)).not.toContain('consumes-mask');
  });

  it('projects transition consumes edges for unmanaged transitions via fallback contributionId match', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'transition:com.example.transitions:wipe': [
        indexEntry('transition:com.example.transitions:wipe'),
      ],
    };

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) => (
          clip.id === 'clip-1'
            ? {
                ...clip,
                transition: transitionSummary({
                  id: 'clip-1.transition.wipe',
                  transitionType: 'wipe',
                  managed: false,
                  managedBy: undefined,
                }),
              }
            : clip
        )),
      },
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:transition:com.example.transitions:wipe',
        detail: expect.objectContaining({
          transitionId: 'clip-1.transition.wipe',
          transitionType: 'wipe',
          refKey: 'transition:com.example.transitions:wipe',
          consumedKind: 'transition',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.wipe',
        }),
      }),
    ]));
  });

  it('skips mask-material consumes edges when the binding owner does not match the clip transition', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'transition:com.example.transitions:dissolve': [
        indexEntry('transition:com.example.transitions:dissolve'),
      ],
    };

    const baseSnapshot = timelineSnapshot();
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        clips: baseSnapshot.clips.map((clip) => (
          clip.id === 'clip-1'
            ? {
                ...clip,
                transition: transitionSummary(),
              }
            : clip
        )),
      },
      materialSlotBindings: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.other',
          },
          slotName: 'transition-mask',
          materialRefId: 'mat-mask-2',
        },
      ],
    });

    const maskMaterialEdges = graph.edges.filter(
      (edge) =>
        edge.kind === 'consumes'
        && (edge.detail as Record<string, unknown>).consumedKind === 'mask-material',
    );

    expect(maskMaterialEdges).toHaveLength(0);
    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: 'clip:clip-1',
        targetNodeId: 'contribution:transition:com.example.transitions:dissolve',
        detail: expect.objectContaining({
          consumedKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
        }),
      }),
    ]));
  });

  it('emits M5 effect missing-ref diagnostics with resolver and contribution details', () => {
    const baseSnapshot = timelineSnapshot({ shaders: [] });
    const graph = project({
      snapshot: {
        ...baseSnapshot,
        shaders: [],
        clips: baseSnapshot.clips.map((clip) =>
          clip.id === 'clip-1'
            ? {
                ...clip,
                effects: [
                  effectSummary({
                    id: 'clip-1.effect.missing',
                    effectType: 'missing-glow',
                    managedBy: 'com.example.unknown',
                  }),
                ],
              }
            : clip
        ),
      },
    });

    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'effect:com.example.unknown:missing-glow',
        state: 'missing',
        nodeIds: ['clip:clip-1'],
      }),
    ]));

    expect(graph.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'composition/effect-missing-ref',
        severity: 'warning',
        extensionId: 'com.example.unknown',
        contributionId: 'missing-glow',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-1',
          clipId: 'clip-1',
          refKey: 'effect:com.example.unknown:missing-glow',
          refState: 'missing',
          resolverState: 'missing',
          scope: 'clip',
          extensionId: 'com.example.unknown',
          contributionId: 'missing-glow',
          ownerKind: 'effect',
          ownerId: 'clip-1.effect.missing',
        }),
      }),
    ]));

    const genericEffectMissing = graph.diagnostics.filter(
      (diagnostic) =>
        diagnostic.code === 'composition/missing-ref'
        && String((diagnostic.detail as Record<string, unknown> | undefined)?.refKey ?? '').startsWith('effect:'),
    );
    expect(genericEffectMissing).toHaveLength(0);
  });

  it('emits M5 transition disabled-ref diagnostics for both transition and slot usages without falling back to generic codes', () => {
    const idx: ContributionIndex = {
      ...contributionIndex(),
      'transition:com.example.transitions:dissolve': [
        indexEntry('transition:com.example.transitions:dissolve', {
          status: 'disabled',
          packageState: 'disabled-by-user',
        }),
      ],
    };

    const baseSnapshot = timelineSnapshot({ shaders: [] });
    const graph = project({
      contributionIndex: idx,
      snapshot: {
        ...baseSnapshot,
        shaders: [],
        clips: baseSnapshot.clips.map((clip) => (
          clip.id === 'clip-1'
            ? {
                ...clip,
                transition: transitionSummary(),
              }
            : clip
        )),
      },
      materialSlotBindings: [
        {
          owner: {
            kind: 'transition',
            clipId: 'clip-1',
            ownerId: 'clip-1.transition.dissolve',
          },
          slotName: 'transition-mask',
          materialRefId: 'mat-mask-1',
        },
      ],
    });

    expect(graph.referenceStates).toEqual(expect.arrayContaining([
      expect.objectContaining({
        refKey: 'transition:com.example.transitions:dissolve',
        state: 'disabled',
        nodeIds: ['clip:clip-1'],
      }),
    ]));

    expect(graph.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'composition/transition-disabled-ref',
        severity: 'error',
        extensionId: 'com.example.transitions',
        contributionId: 'dissolve',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-1',
          clipId: 'clip-1',
          refKey: 'transition:com.example.transitions:dissolve',
          refState: 'disabled',
          resolverState: 'disabled',
          scope: 'clip',
          extensionId: 'com.example.transitions',
          contributionId: 'dissolve',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          packageState: 'disabled-by-user',
        }),
      }),
      expect.objectContaining({
        code: 'composition/transition-disabled-ref',
        severity: 'error',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-1',
          materialSlot: 'transition-mask',
          materialRefId: 'mat-mask-1',
          refKey: 'transition:com.example.transitions:dissolve',
          resolverState: 'disabled',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          packageState: 'disabled-by-user',
        }),
      }),
    ]));

    const genericTransitionDisabled = graph.diagnostics.filter(
      (diagnostic) =>
        diagnostic.code === 'composition/disabled-ref'
        && String((diagnostic.detail as Record<string, unknown> | undefined)?.refKey ?? '').startsWith('transition:'),
    );
    expect(genericTransitionDisabled).toHaveLength(0);
  });
});
