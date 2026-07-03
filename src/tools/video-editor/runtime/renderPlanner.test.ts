import { describe, expect, it } from 'vitest';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  blockerToRouteFitMetadata,
  findingToRouteFitMetadata,
} from '@/tools/video-editor/runtime/routeFitMapper.ts';
import type {
  CapabilityFinding,
  CapabilityRequirement,
  ProcessStatus,
  RenderBlocker,
  RenderMaterialRef,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import type {
  ContributionIndex,
  VideoEditorOutputFormatDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

function snapshotWithLiveBinding(): TimelineSnapshot {
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
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'V1',
        kind: 'visual',
        label: 'V1',
        muted: false,
      },
    ],
    assetKeys: [],
    app: {},
    liveBindings: [
      {
        bindingId: 'binding-1',
        clipId: 'clip-1',
        sourceId: 'webcam-1',
        sourceKind: 'webcam',
        status: 'active',
      },
    ],
    outputMetadata: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
  };
}

function snapshotWithShaders(): TimelineSnapshot {
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
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'V1',
        kind: 'visual',
        label: 'V1',
        muted: false,
      },
    ],
    assetKeys: [],
    app: {},
    shaders: [
      {
        id: 'clip-1:shader:shader.preview.clip',
        shaderId: 'shader.preview.clip',
        scope: 'clip',
        clipId: 'clip-1',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
        enabled: true,
      },
      {
        id: 'postprocess:shader:shader.preview.post',
        shaderId: 'shader.preview.post',
        scope: 'postprocess',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
        enabled: true,
      },
    ],
    outputMetadata: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
  };
}

function requirement(input: Partial<CapabilityRequirement> & Pick<CapabilityRequirement, 'id' | 'route'>): CapabilityRequirement {
  return {
    sourceRef: { source: 'extension', extensionId: 'ext.requirements', contributionId: 'reqs' },
    requiredCapabilities: ['browser-export'],
    determinism: 'deterministic',
    ...input,
  };
}

function renderDependentOutput(): VideoEditorOutputFormatDescriptor {
  return {
    id: 'dataset.zip',
    extensionId: 'ext.dataset',
    order: 2,
    label: 'Dataset bundle',
    requiresRender: true,
    outputExtension: '.zip',
    outputMimeType: 'application/zip',
    disabled: false,
    availableRoutes: ['sidecar-export'],
    routeRequirements: [
      {
        routes: ['sidecar-export'],
        requiredCapabilities: ['sidecar-export', 'json-rpc'],
        processId: 'dataset-process',
        operationId: 'exportDataset',
        determinism: 'process-dependent',
        unavailableMessage: 'Start the dataset process before exporting the bundle.',
      },
    ],
    processRequirements: [
      {
        processId: 'dataset-process',
        operationId: 'exportDataset',
        requiredCapabilities: ['json-rpc'],
      },
    ],
    blockers: [],
    nextActions: [
      {
        kind: 'select-route',
        label: 'Plan sidecar-export',
        route: 'sidecar-export',
        processId: 'dataset-process',
        operationId: 'exportDataset',
      },
    ],
    capabilities: {
      extensionId: 'ext.dataset',
      contributionId: 'dataset.zip',
      routes: ['sidecar-export'],
      determinism: 'process-dependent',
      fullySupported: true,
      anyBlocked: false,
      sourceRefs: [
        { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
      ],
      capabilityRequirements: [
        {
          id: 'ext.dataset.dataset.zip.sidecar-export',
          sourceRef: { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
          route: 'sidecar-export',
          requiredCapabilities: ['sidecar-export'],
          determinism: 'process-dependent',
          routeFit: { route: 'sidecar-export', fit: 'supported' },
          blocking: false,
        },
      ],
    },
    sidecars: [],
  };
}

function processDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'process-contribution',
    extensionId: 'ext.dataset',
    processId: 'dataset-process',
    label: 'Dataset process',
    spec: {
      id: 'dataset-process',
      label: 'Dataset process',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'node',
        args: ['dataset-process.js'],
      },
      operations: [
        {
          id: 'exportDataset',
          label: 'Export dataset',
          routes: ['sidecar-export'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'exportDataset',
        label: 'Export dataset',
        routes: ['sidecar-export'],
      },
    ],
    availableRoutes: ['sidecar-export'],
    requiredBy: [
      { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
    ],
    blockers: [],
    nextActions: [],
  };
}

function shaderMaterializerDescriptor(): VideoEditorShaderDescriptor {
  return {
    id: 'ext.shader.clip',
    extensionId: 'ext.shader',
    shaderId: 'shader.preview.clip',
    label: 'Preview clip shader',
    pass: 'clip',
    materializer: {
      processId: 'shader-materializer',
      operationId: 'materializeClipShader',
      requiredCapabilities: ['render-material', 'shader-materializer'],
    },
    hasSourceMetadata: false,
  };
}

function shaderMaterializerProcess(): VideoEditorProcessDescriptor {
  return {
    id: 'shader-materializer-process',
    extensionId: 'ext.shader',
    processId: 'shader-materializer',
    label: 'Shader materializer',
    spec: {
      id: 'shader-materializer',
      label: 'Shader materializer',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'node',
        args: ['shader-materializer.js'],
      },
      operations: [
        {
          id: 'materializeClipShader',
          label: 'Materialize clip shader',
          routes: ['browser-export'],
          outputKinds: ['material'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'materializeClipShader',
        label: 'Materialize clip shader',
        routes: ['browser-export'],
        outputKinds: ['material'],
      },
    ],
    availableRoutes: ['browser-export'],
    requiredBy: [
      { source: 'extension', extensionId: 'ext.shader', contributionId: 'ext.shader.clip' },
    ],
    blockers: [],
    nextActions: [],
  };
}

function shaderContributionIndex(
  entries: readonly {
    contributionId: string;
    extensionId?: string;
    status?: 'active' | 'inactive-reserved' | 'disabled' | 'invalid';
    projected?: boolean;
    projectionEligible?: boolean;
    source?: 'descriptor-array' | 'preserved-record';
  }[],
): ContributionIndex {
  const index: Record<string, ContributionIndex[string]> = {};

  for (const entry of entries) {
    const extensionId = entry.extensionId ?? 'ext.shader';
    const scopedKey = `shader:${extensionId}:${entry.contributionId}`;
    index[scopedKey] = [{
      scopedKey,
      kind: 'shader',
      extensionId,
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

function materialRef(
  id: string,
  overrides: Partial<RenderMaterialRef> = {},
): RenderMaterialRef {
  return {
    id,
    mediaKind: 'video',
    locator: { kind: 'provider', uri: `provider://materials/${id}` },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    producerExtensionId: 'ext.materials',
    ...overrides,
  };
}

describe('planRender', () => {
  it('derives route blockers from a public TimelineSnapshot without registry inputs', () => {
    const result = planRender({ snapshot: snapshotWithLiveBinding() });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(true);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 1, findingCount: 2, blocked: true },
      { route: 'worker-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'sidecar-export', blockerCount: 0, findingCount: 0, blocked: false },
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'snapshot.liveBinding.2.browser-export.live-unbaked',
        route: 'browser-export',
        reason: 'live-unbaked',
        severity: 'error',
      }),
    ]);
  });

  it('keeps findings, blockers, next actions, and route plans deterministic', () => {
    const warning: CapabilityFinding = {
      id: 'z-warning',
      severity: 'warning',
      route: 'worker-export',
      reason: 'unknown',
      message: 'Worker route has not been classified.',
    };
    const result = planRender({
      requirements: [
        requirement({
          id: 'b-requirement',
          route: 'worker-export',
          requiredCapabilities: ['worker-export'],
          determinism: 'unknown',
          routeFit: {
            route: 'worker-export',
            fit: 'unknown',
            reason: 'unknown',
            message: 'Worker route has not been classified.',
          },
          findings: [warning],
        }),
        requirement({
          id: 'a-requirement',
          route: 'browser-export',
          requiredCapabilities: ['browser-export'],
          determinism: 'deterministic',
          routeFit: { route: 'browser-export', fit: 'supported' },
        }),
      ],
    });

    expect(result.findings.map((finding) => finding.id)).toEqual([
      'b-requirement.worker-export.unknown',
      'z-warning',
    ]);
    expect(result.blockers).toEqual([]);
    expect(result.routePlans.map((routePlan) => routePlan.route)).toEqual([
      'preview',
      'browser-export',
      'worker-export',
      'sidecar-export',
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: false,
      determinism: 'unknown',
      findingCount: 2,
      requiredCapabilities: ['worker-export'],
    });
  });

  it('records worker route downgrades as route warnings without blocking worker export', () => {
    const result = planRender({
      requirements: [
        requirement({
          id: 'shader-transition-worker-downgrade',
          route: 'worker-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['worker-export', 'shader-fallback'],
          determinism: 'process-dependent',
          routeFit: {
            route: 'worker-export',
            fit: 'degraded',
            reason: 'process-dependent',
            message: 'Worker export will use a deterministic shader fallback.',
          },
        }),
      ],
    });

    expect(result.canWorkerExport).toBe(true);
    expect(result.blockers).toEqual([]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'shader-transition-worker-downgrade.worker-export.process-dependent',
        severity: 'warning',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Worker export will use a deterministic shader fallback.',
        extensionId: 'ext.shader',
        contributionId: 'transition.shader-wipe',
        detail: {
          source: 'capability-requirement',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['shader-fallback', 'worker-export'],
          determinism: 'process-dependent',
          routeFit: {
            route: 'worker-export',
            fit: 'degraded',
            reason: 'process-dependent',
            message: 'Worker export will use a deterministic shader fallback.',
          },
        },
      }),
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      findingCount: 1,
      determinism: 'process-dependent',
      requiredCapabilities: ['shader-fallback', 'worker-export'],
    });
  });

  it('blocks worker export for browser-only shader transitions with complete route metadata', () => {
    const result = planRender({
      requirements: [
        requirement({
          id: 'shader-transition-browser-route',
          route: 'browser-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['browser-export', 'webgl-shader'],
          determinism: 'deterministic',
          routeFit: {
            route: 'browser-export',
            fit: 'supported',
          },
        }),
        requirement({
          id: 'shader-transition-worker-route',
          route: 'worker-export',
          sourceRef: {
            source: 'extension',
            extensionId: 'ext.shader',
            contributionId: 'transition.shader-wipe',
          },
          requiredCapabilities: ['worker-export', 'webgl-shader'],
          determinism: 'process-dependent',
          blocking: true,
          routeFit: {
            route: 'worker-export',
            fit: 'blocked',
            reason: 'process-dependent',
            message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
          },
        }),
      ],
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(false);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      requiredCapabilities: ['browser-export', 'webgl-shader'],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: true,
      blockerCount: 1,
      findingCount: 1,
      determinism: 'process-dependent',
      requiredCapabilities: ['webgl-shader', 'worker-export'],
      blockers: [
        expect.objectContaining({
          id: 'shader-transition-worker-route.worker-export.process-dependent',
          severity: 'error',
          route: 'worker-export',
          reason: 'process-dependent',
          message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
          extensionId: 'ext.shader',
          contributionId: 'transition.shader-wipe',
          detail: {
            source: 'capability-requirement',
            sourceRef: {
              source: 'extension',
              extensionId: 'ext.shader',
              contributionId: 'transition.shader-wipe',
            },
            requiredCapabilities: ['webgl-shader', 'worker-export'],
            determinism: 'process-dependent',
            routeFit: {
              route: 'worker-export',
              fit: 'blocked',
              reason: 'process-dependent',
              message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
            },
          },
        }),
      ],
    });
  });

  it('blocks export for timeline shader metadata until a materializer produces RenderMaterial', () => {
    const result = planRender({ snapshot: snapshotWithShaders() });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      }),
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
      }),
    ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')?.requiredCapabilities)
      .toEqual(expect.arrayContaining(['render-material', 'shader-materializer']));
  });

  it('diagnoses duplicate clip and postprocess shaders instead of stacking planner requirements', () => {
    const snapshot = snapshotWithShaders();
    const result = planRender({
      snapshot: {
        ...snapshot,
        shaders: [
          ...(snapshot.shaders ?? []),
          {
            id: 'clip-1:shader:shader.preview.clip.second',
            shaderId: 'shader.preview.clip.second',
            scope: 'clip',
            clipId: 'clip-1',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip.second',
            enabled: true,
          },
          {
            id: 'postprocess:shader:shader.preview.post.second',
            shaderId: 'shader.preview.post.second',
            scope: 'postprocess',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.post.second',
            enabled: true,
          },
        ],
      },
      extensionRuntime: {
        outputFormats: [],
        processes: [],
        shaders: [],
        contributionIndex: shaderContributionIndex([
          { contributionId: 'ext.shader.clip' },
          { contributionId: 'ext.shader.post' },
          { contributionId: 'ext.shader.clip.second' },
          { contributionId: 'ext.shader.post.second' },
        ]),
      },
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.shaderComposition.clip:clip-1.shader.preview.clip.second.browser-export.scope-occupied',
        severity: 'error',
        route: 'browser-export',
        reason: 'unknown',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip.second',
        detail: {
          source: 'shader-composition-limit',
          scope: 'clip',
          clipId: 'clip-1',
          existingShaderId: 'shader.preview.clip',
          incomingShaderId: 'shader.preview.clip.second',
        },
      }),
      expect.objectContaining({
        id: 'planner.shaderComposition.clip:clip-1.shader.preview.clip.second.worker-export.scope-occupied',
        severity: 'error',
        route: 'worker-export',
      }),
      expect.objectContaining({
        id: 'planner.shaderComposition.postprocess.shader.preview.post.second.browser-export.scope-occupied',
        severity: 'error',
        route: 'browser-export',
        reason: 'unknown',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post.second',
        detail: {
          source: 'shader-composition-limit',
          scope: 'postprocess',
          clipId: undefined,
          existingShaderId: 'shader.preview.post',
          incomingShaderId: 'shader.preview.post.second',
        },
      }),
      expect.objectContaining({
        id: 'planner.shaderComposition.postprocess.shader.preview.post.second.worker-export.scope-occupied',
        severity: 'error',
        route: 'worker-export',
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'unknown',
        message: 'Cannot add shader "shader.preview.clip.second" to clip "clip-1" because shader "shader.preview.clip" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip.second',
      }),
      expect.objectContaining({
        route: 'browser-export',
        reason: 'unknown',
        message: 'Cannot add postprocess shader "shader.preview.post.second" because postprocess shader "shader.preview.post" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post.second',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        message: 'Shader "shader.preview.clip.second" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
      expect.objectContaining({
        message: 'Shader "shader.preview.post.second" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
      }),
    ]));
  });

  it('projects snapshot shader refs through the contribution index before duplicate-scope diagnosis', () => {
    const result = planRender({
      snapshot: {
        ...snapshotWithShaders(),
        shaders: [
          {
            id: 'clip-1:shader:shader.preview.clip',
            shaderId: 'shader.preview.clip',
            scope: 'clip',
            clipId: 'clip-1',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip',
            enabled: true,
          },
          {
            id: 'clip-1:shader:shader.preview.clip.disabled',
            shaderId: 'shader.preview.clip.disabled',
            scope: 'clip',
            clipId: 'clip-1',
            extensionId: 'ext.shader',
            contributionId: 'ext.shader.clip.disabled',
            enabled: true,
          },
        ],
      },
      extensionRuntime: {
        outputFormats: [],
        processes: [],
        shaders: [],
        contributionIndex: shaderContributionIndex([
          { contributionId: 'ext.shader.clip' },
          {
            contributionId: 'ext.shader.clip.disabled',
            status: 'disabled',
            projected: false,
            projectionEligible: false,
            source: 'preserved-record',
          },
        ]),
      },
    });

    expect(result.findings).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.shaderComposition.clip:clip-1.shader.preview.clip.disabled.browser-export.scope-occupied',
      }),
      expect.objectContaining({
        id: 'planner.shaderComposition.clip:clip-1.shader.preview.clip.disabled.worker-export.scope-occupied',
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        contributionId: 'ext.shader.clip',
        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ contributionId: 'ext.shader.clip.disabled' }),
    ]));
  });

  it('uses registered shader materializer process routes for materialization next actions', () => {
    const result = planRender({
      snapshot: snapshotWithShaders(),
      shaders: [shaderMaterializerDescriptor()],
      processes: [shaderMaterializerProcess()],
      processStatuses: [
        {
          processId: 'shader-materializer',
          state: 'busy',
          message: 'Materializing clip shader.',
        },
      ],
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'snapshot.shader.2.browser-export.process-dependent',
        route: 'browser-export',
        reason: 'process-dependent',
        message: 'Shader "shader.preview.clip" has a materializer route for browser-export; run process "shader-materializer" to produce RenderMaterial.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
    ]));
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'snapshot.shader.2.browser-export.shader-materializer.discovered',
        severity: 'info',
        route: 'browser-export',
        detail: expect.objectContaining({
          source: 'shader-materializer',
          shaderId: 'shader.preview.clip',
          processId: 'shader-materializer',
          operationId: 'materializeClipShader',
          processState: 'busy',
          materializationState: 'in-progress',
        }),
      }),
    ]));
    expect(result.nextActions).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'materialize',
        route: 'browser-export',
        label: 'Materialize shader shader.preview.clip',
        processId: 'shader-materializer',
        operationId: 'materializeClipShader',
        detail: expect.objectContaining({
          specificKind: 'resolve-blocker',
        }),
      }),
    ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')?.nextActions)
      .toEqual(expect.arrayContaining([
        expect.objectContaining({
          kind: 'materialize',
          route: 'browser-export',
          processId: 'shader-materializer',
          operationId: 'materializeClipShader',
          detail: expect.objectContaining({
            specificKind: 'resolve-blocker',
          }),
        }),
      ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')?.nextActions)
      .toEqual([]);
  });

  it('plans normalized render-dependent output formats as process-dependent route blockers', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'worker-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'sidecar-export', blockerCount: 2, findingCount: 2, blocked: true },
    ]);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      outputFormatIds: ['dataset.zip'],
      processRequirements: [
        {
          processId: 'dataset-process',
          operationId: 'exportDataset',
          requiredCapabilities: ['json-rpc'],
        },
      ],
      nextActions: [
        expect.objectContaining({
          kind: 'select-route',
          processId: 'dataset-process',
          route: 'sidecar-export',
        }),
      ],
    });
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
      }),
    ]);
  });

  it('surfaces missing requested output formats as structured request blockers', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      request: { outputFormatId: 'missing.format', route: 'sidecar-export' },
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: true,
      blockerCount: 1,
    });
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.missing.format.missing',
        route: 'sidecar-export',
        reason: 'missing-contribution',
        contributionId: 'missing.format',
      }),
    ]);
  });

  it('surfaces requested route support and request-level capabilities in route plans', () => {
    const result = planRender({
      outputFormats: [renderDependentOutput()],
      request: {
        outputFormatId: 'dataset.zip',
        routes: ['browser-export', 'sidecar-export'],
        requiredCapabilities: ['timeline-render'],
      },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      requiredCapabilities: ['timeline-render'],
      blockers: [
        expect.objectContaining({
          id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.route-unsupported',
          reason: 'route-unsupported',
        }),
      ],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      requiredCapabilities: ['json-rpc', 'sidecar-export', 'timeline-render'],
      outputFormatIds: ['dataset.zip'],
    });
  });

  it('converts materialize-on-export live material refs into browser-export blockers', () => {
    const materialRef: RenderMaterialRef = {
      id: 'mat-live-1',
      mediaKind: 'video',
      locator: { kind: 'provider', uri: 'provider://live/mat-live-1' },
      determinism: 'live-unbaked',
      replacementPolicy: 'materialize-on-export',
    };

    const result = planRender({ materialRefs: [materialRef] });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-live-1.browser-export.live-unbaked',
        route: 'browser-export',
        reason: 'live-unbaked',
        materialRefId: 'mat-live-1',
        detail: expect.objectContaining({
          materialState: 'pending',
          materialPhase: 'queued',
        }),
      }),
    ]);
  });

  it('materializes missing and stale material next actions while resolved material refs do not block', () => {
    const result = planRender({
      materialRefs: [
        materialRef('mat-missing'),
        materialRef('mat-stale'),
        materialRef('mat-resolved'),
      ],
      materialStatuses: [
        { materialRefId: 'mat-missing', state: 'missing', message: 'Material bytes are unavailable.' },
        { materialRefId: 'mat-stale', state: 'stale', message: 'Material was produced from an older source hash.' },
        { materialRefId: 'mat-resolved', state: 'resolved' },
      ],
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-missing.browser-export.missing-material',
        reason: 'missing-material',
        materialRefId: 'mat-missing',
      }),
      expect.objectContaining({
        id: 'planner.material.mat-stale.browser-export.materialization-failed',
        reason: 'materialization-failed',
        materialRefId: 'mat-stale',
      }),
    ]);
    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-resolved')).toBe(false);
    expect(result.nextActions).toEqual([
      expect.objectContaining({
        kind: 'materialize',
        label: 'Materialize mat-missing',
        message: 'Material bytes are unavailable.',
        detail: expect.objectContaining({
          specificKind: 'resolve-blocker',
        }),
      }),
      expect.objectContaining({
        kind: 'materialize',
        label: 'Materialize mat-stale',
        message: 'Material was produced from an older source hash.',
        detail: expect.objectContaining({
          specificKind: 'resolve-blocker',
        }),
      }),
    ]);
  });

  it('derives matrix-backed material repair actions from legacy material refs and statuses', () => {
    const result = planRender({
      materialRefs: [
        materialRef('mat-baking'),
        materialRef('mat-failed'),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-baking',
          state: 'pending',
          detail: { phase: 'active' },
          message: 'Materialization is already running.',
        },
        {
          materialRefId: 'mat-failed',
          state: 'failed',
          message: 'Materialization crashed.',
        },
      ],
    });

    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-baking.browser-export.process-dependent',
        reason: 'process-dependent',
        materialRefId: 'mat-baking',
        detail: expect.objectContaining({
          materialState: 'pending',
          materialPhase: 'active',
        }),
      }),
      expect.objectContaining({
        id: 'planner.material.mat-failed.browser-export.materialization-error',
        reason: 'materialization-error',
        materialRefId: 'mat-failed',
        detail: expect.objectContaining({
          materialState: 'failed',
        }),
      }),
    ]);
    expect(result.nextActions).toEqual([
      expect.objectContaining({
        kind: 'bake',
        label: 'Bake mat-baking',
        message: 'Materialization is already running.',
        detail: expect.objectContaining({
          specificKind: 'resolve-blocker',
        }),
      }),
      expect.objectContaining({
        kind: 'open-settings',
        label: 'Open settings for mat-failed',
        message: 'Materialization crashed.',
        detail: expect.objectContaining({
          specificKind: 'resolve-blocker',
        }),
      }),
    ]);
  });

  it('accepts a prebuilt material projection without re-deriving planner material status logic', () => {
    const prebuiltMaterialRuntime = projectHostMaterialRuntime({
      materialRefs: [materialRef('mat-projected')],
      materialStatuses: [
        {
          materialRefId: 'mat-projected',
          state: 'failed',
          message: 'Use the prebuilt material runtime.',
        },
      ],
    });

    const result = planRender({
      materialRefs: [materialRef('mat-projected')],
      materialStatuses: [
        {
          materialRefId: 'mat-projected',
          state: 'resolved',
        },
      ],
      materialRuntime: prebuiltMaterialRuntime,
    });

    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-projected.browser-export.materialization-error',
        reason: 'materialization-error',
        materialRefId: 'mat-projected',
      }),
    ]);
    expect(result.nextActions).toEqual([
      expect.objectContaining({
        kind: 'open-settings',
        label: 'Open settings for mat-projected',
        message: 'Use the prebuilt material runtime.',
      }),
    ]);
  });

  it('treats ready processes as resolved and degraded processes as warnings without subprocess work', () => {
    const readyStatus: ProcessStatus = {
      processId: 'dataset-process',
      state: 'ready',
      pid: 1234,
    };
    const degradedStatus: ProcessStatus = {
      processId: 'dataset-process',
      state: 'degraded',
      message: 'Dataset process is running with a fallback encoder.',
      healthCheck: 'encoder',
    };

    const ready = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [readyStatus],
      request: { outputFormatId: 'dataset.zip' },
    });
    const degraded = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [degradedStatus],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(ready.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      processRequirements: [
        {
          processId: 'dataset-process',
          operationId: 'exportDataset',
          requiredCapabilities: ['json-rpc'],
        },
      ],
    });
    expect(ready.blockers).toEqual([]);

    expect(degraded.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      findingCount: 2,
    });
    expect(degraded.findings).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent.degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-dependent',
        message: 'Dataset process is running with a fallback encoder.',
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent.degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-dependent',
        message: 'Dataset process is running with a fallback encoder.',
      }),
    ]);
  });

  it('blocks required missing and stale render-group passes and ignores resolved or optional passes', () => {
    const result = planRender({
      snapshot: {
        projectId: 'project-render-groups',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: [],
        app: {},
        renderGroups: [
          {
            id: 'hero-shot',
            clipIds: ['clip-a', 'clip-b'],
            groupType: 'multi-pass',
            requiredPasses: ['beauty', 'depth', 'normal'],
            passes: [
              {
                id: 'beauty-pass',
                passName: 'beauty',
                required: true,
                composable: true,
                materialRefId: 'mat-beauty',
                status: 'resolved',
              },
              {
                id: 'depth-pass',
                passName: 'depth',
                required: true,
                composable: true,
                materialRefId: 'mat-depth',
                status: 'missing',
              },
              {
                id: 'normal-pass',
                passName: 'normal',
                required: true,
                composable: true,
                materialRefId: 'mat-normal',
                status: 'stale',
              },
              {
                id: 'thumbnail-pass',
                passName: 'thumbnail',
                required: false,
                composable: false,
                status: 'missing',
              },
            ],
          },
        ],
      },
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.renderGroup.hero-shot.depth-pass.browser-export.missing-material',
        reason: 'missing-material',
        materialRefId: 'mat-depth',
      }),
      expect.objectContaining({
        id: 'planner.renderGroup.hero-shot.normal-pass.browser-export.materialization-failed',
        reason: 'materialization-failed',
        materialRefId: 'mat-normal',
      }),
    ]);
    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-beauty')).toBe(false);
    expect(result.blockers.some((blocker) => blocker.id.includes('thumbnail-pass'))).toBe(false);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      requiredCapabilities: ['render-groups'],
      determinism: 'process-dependent',
      nextActions: [
        expect.objectContaining({ label: 'Materialize hero-shot:depth' }),
        expect.objectContaining({ label: 'Materialize hero-shot:normal' }),
      ],
    });
  });

  // ---------------------------------------------------------------------------
  // Route planner / route-fit compatibility (M1a T17)
  // ---------------------------------------------------------------------------

  describe('route planner / route-fit compatibility', () => {
    const attributableIdx: ContributionIndex = shaderContributionIndex([
      { contributionId: 'ext.shader.clip', extensionId: 'ext.shader' },
      { contributionId: 'ext.shader.post', extensionId: 'ext.shader' },
    ]);

    const ambiguousIdx: ContributionIndex = (() => {
      const map: Record<string, ContributionIndex[string]> = {};
      const create = (scopedKey: string, contributionId: string, extensionId: string) => {
        map[scopedKey] = [{
          scopedKey,
          kind: scopedKey.split(':')[0],
          extensionId,
          contributionId,
          status: 'active' as const,
          diagnostics: Object.freeze([]),
          duplicateOrdinal: 0,
          projectionEligible: true,
          projection: Object.freeze({
            duplicateOrdinal: 0,
            eligible: true,
            projected: true,
            source: 'descriptor-array' as const,
          }),
        }];
      };
      create('shader:ext-a:shared', 'shared', 'ext-a');
      create('output-format:ext-a:shared', 'shared', 'ext-a');
      return Object.freeze(map);
    })();

    it('produces identical RenderPlannerResult top-level keys regardless of contributionIndex', () => {
      const without = planRender({ snapshot: snapshotWithShaders() });
      const withIdx = planRender({
        snapshot: snapshotWithShaders(),
        extensionRuntime: {
          outputFormats: [],
          processes: [],
          shaders: [],
          contributionIndex: attributableIdx,
        },
      });

      // All top-level result keys must be present in both paths.
      const resultKeys: readonly (keyof typeof without)[] = [
        'guard', 'findings', 'blockers', 'routes', 'routePlans',
        'diagnostics', 'nextActions', 'canBrowserExport', 'canWorkerExport',
      ];
      for (const key of resultKeys) {
        expect(withIdx).toHaveProperty(key);
        expect(without).toHaveProperty(key);
      }
    });

    it('preserves route plans with identical blocker counts when contributionIndex has only active entries', () => {
      const without = planRender({ snapshot: snapshotWithShaders() });
      const withIdx = planRender({
        snapshot: snapshotWithShaders(),
        extensionRuntime: {
          outputFormats: [],
          processes: [],
          shaders: [],
          contributionIndex: attributableIdx,
        },
      });

      // Route shape must be identical when no projection filtering changes the shader list.
      for (const route of ['browser-export', 'worker-export'] as const) {
        const withoutPlan = without.routePlans.find((rp) => rp.route === route);
        const withPlan = withIdx.routePlans.find((rp) => rp.route === route);
        expect(withPlan?.blockerCount).toBe(withoutPlan?.blockerCount);
        expect(withPlan?.blocked).toBe(withoutPlan?.blocked);
      }
    });

    it('keeps canBrowserExport and canWorkerExport consistent when contributionIndex does not filter shaders', () => {
      const withIdx = planRender({
        snapshot: snapshotWithShaders(),
        extensionRuntime: {
          outputFormats: [],
          processes: [],
          shaders: [],
          contributionIndex: attributableIdx,
        },
      });

      // Shader-only snapshots without materializers block both exports.
      expect(withIdx.canBrowserExport).toBe(false);
      expect(withIdx.canWorkerExport).toBe(false);
    });

    it('produces route-fit metadata from blockers only when the blocker is directly attributable', () => {
      const result = planRender({
        snapshot: snapshotWithShaders(),
        extensionRuntime: {
          outputFormats: [],
          processes: [],
          shaders: [],
          contributionIndex: attributableIdx,
        },
      });

      // Shader blockers carry extensionId + contributionId.
      const shaderBlockers = result.blockers.filter(
        (b): b is VideoEditorPlannerBlockerDescriptor =>
          typeof (b as VideoEditorPlannerBlockerDescriptor).extensionId === 'string',
      );

      for (const blocker of shaderBlockers) {
        const metadata = blockerToRouteFitMetadata(blocker, attributableIdx);
        expect(metadata).toBeDefined();
        expect(metadata!.route).toBe(blocker.route);
        expect(metadata!.fit).toBe('blocked');
        expect(metadata!.reason).toBe(blocker.reason);
      }
    });

    it('omits route-fit metadata for blockers whose identity is not in the contribution index', () => {
      const blocker: VideoEditorPlannerBlockerDescriptor = {
        id: 'blocker-unknown',
        extensionId: 'ext.unknown',
        contributionId: 'unknown-contrib',
        route: 'browser-export',
        reason: 'route-unsupported',
        message: 'Unknown contribution.',
      };

      expect(blockerToRouteFitMetadata(blocker, attributableIdx)).toBeUndefined();
    });

    it('omits route-fit metadata when contributionIndex is undefined', () => {
      const blocker: VideoEditorPlannerBlockerDescriptor = {
        id: 'blocker-no-index',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
        route: 'browser-export',
        reason: 'missing-material',
        message: 'No material.',
      };

      expect(blockerToRouteFitMetadata(blocker, undefined)).toBeUndefined();
    });

    it('omits route-fit metadata from blockers with ambiguous extensionId+contributionId', () => {
      const blocker: VideoEditorPlannerBlockerDescriptor = {
        id: 'blocker-ambiguous',
        extensionId: 'ext-a',
        contributionId: 'shared',
        route: 'sidecar-export',
        reason: 'process-dependent',
        message: 'Shared identity ambiguous.',
      };

      expect(blockerToRouteFitMetadata(blocker, ambiguousIdx)).toBeUndefined();
    });

    it('produces route-fit metadata from findings only when extensionId and contributionId are directly attributable', () => {
      const finding: CapabilityFinding = {
        id: 'finding-attributable',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-material',
        message: 'Material missing.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      };

      const metadata = findingToRouteFitMetadata(finding, attributableIdx);
      expect(metadata).toBeDefined();
      expect(metadata!.route).toBe('browser-export');
      expect(metadata!.fit).toBe('blocked'); // error severity → blocked
    });

    it('maps warning-severity findings to degraded route-fit', () => {
      const finding: CapabilityFinding = {
        id: 'finding-warning',
        severity: 'warning',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Degraded.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
      };

      const metadata = findingToRouteFitMetadata(finding, attributableIdx);
      expect(metadata).toBeDefined();
      expect(metadata!.fit).toBe('degraded');
    });

    it('omits route-fit metadata from findings when extensionId is missing', () => {
      const finding: CapabilityFinding = {
        id: 'finding-no-ext',
        severity: 'error',
        route: 'browser-export',
        reason: 'unknown',
        message: 'No extension.',
      };

      expect(findingToRouteFitMetadata(finding, attributableIdx)).toBeUndefined();
    });

    it('omits route-fit metadata from findings when contributionId is missing', () => {
      const finding: CapabilityFinding = {
        id: 'finding-no-contrib',
        severity: 'error',
        route: 'browser-export',
        reason: 'unknown',
        message: 'No contribution.',
        extensionId: 'ext.shader',
      };

      expect(findingToRouteFitMetadata(finding, attributableIdx)).toBeUndefined();
    });

    it('omits route-fit metadata from findings when contributionIndex is undefined', () => {
      const finding: CapabilityFinding = {
        id: 'finding-no-index',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-material',
        message: 'No index.',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
      };

      expect(findingToRouteFitMetadata(finding, undefined)).toBeUndefined();
    });

    it('omits route-fit metadata from findings with ambiguous identity', () => {
      const finding: CapabilityFinding = {
        id: 'finding-ambiguous',
        severity: 'error',
        route: 'sidecar-export',
        reason: 'unknown',
        message: 'Ambiguous.',
        extensionId: 'ext-a',
        contributionId: 'shared',
      };

      expect(findingToRouteFitMetadata(finding, ambiguousIdx)).toBeUndefined();
    });

    it('returns route-fit metadata from a real planner blocker only when the scoped contribution is in the index', () => {
      // Use a blocker produced by the planner with a known contribution.
      const result = planRender({
        snapshot: snapshotWithShaders(),
      });

      const clipBlocker = result.blockers.find(
        (b) => (b as RenderBlocker).contributionId === 'ext.shader.clip',
      ) as VideoEditorPlannerBlockerDescriptor | undefined;

      if (clipBlocker) {
        // With the proper index the blocker should be attributable.
        const meta = blockerToRouteFitMetadata(clipBlocker, attributableIdx);
        expect(meta).toBeDefined();
        expect(meta!.route).toBe('browser-export');

        // Without the index it should be undefined.
        expect(blockerToRouteFitMetadata(clipBlocker, undefined)).toBeUndefined();
      }
    });

    it('does not leak route-fit metadata for planner blockers whose contribution is not in the contribution index', () => {
      // Empty index — no entries are attributable.
      const emptyIndex: ContributionIndex = Object.freeze({});

      const result = planRender({
        snapshot: snapshotWithShaders(),
      });

      for (const blocker of result.blockers) {
        const descriptor = blocker as VideoEditorPlannerBlockerDescriptor;
        if (descriptor.extensionId && descriptor.contributionId) {
          // With empty index the identity cannot be resolved.
          expect(blockerToRouteFitMetadata(descriptor, emptyIndex)).toBeUndefined();
        }
      }
    });
  });
});
