import { describe, expect, it } from 'vitest';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  CapabilityFinding,
  CapabilityRequirement,
  RenderMaterialRef,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import type {
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
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
        kind: 'start-process',
        label: 'Start dataset process',
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
    nextActions: [
      {
        kind: 'start-process',
        label: 'Start Dataset process',
        processId: 'dataset-process',
      },
    ],
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
        expect.objectContaining({ kind: 'start-process', processId: 'dataset-process' }),
        expect.objectContaining({ kind: 'start-process', processId: 'dataset-process', route: 'sidecar-export' }),
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
      }),
    ]);
  });
});
