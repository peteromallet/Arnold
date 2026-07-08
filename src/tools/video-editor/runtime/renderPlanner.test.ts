import { describe, expect, it } from 'vitest';
import {
  buildExportReadinessPlan,
  planRender,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import { createProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { createRenderArtifactManifest } from '@/tools/video-editor/runtime/renderability.ts';
import {
  blockerToRouteFitMetadata,
  findingToRouteFitMetadata,
} from '@/tools/video-editor/runtime/routeFitMapper.ts';
import type {
  CapabilityFinding,
  CapabilityRequirement,
  ExportDiagnostic,
  RenderArtifact,
  RenderBlocker,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  RenderMaterialRef,
  RenderRoute,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import type { ProcessStatus } from '@/sdk/video/families/processes';
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

function routerRequirement(input: {
  readonly id: string;
  readonly route: RenderRoute;
  readonly clipType: string;
  readonly reason: RenderBlocker['reason'];
  readonly legacyReason: string;
  readonly message: string;
  readonly requiredCapabilities?: readonly string[];
}): CapabilityRequirement {
  return {
    id: input.id,
    sourceRef: { source: 'registry', contributionId: input.clipType },
    route: input.route,
    requiredCapabilities: input.requiredCapabilities ?? [input.route],
    determinism: input.route === 'worker-export' ? 'process-dependent' : 'deterministic',
    blocking: true,
    routeFit: {
      route: input.route,
      fit: 'blocked',
      reason: input.reason,
      message: input.message,
    },
    findings: [
      {
        id: `${input.id}.${input.route}.${input.reason}`,
        severity: 'error',
        route: input.route,
        reason: input.reason,
        message: input.message,
        detail: {
          source: 'render-router',
          clipType: input.clipType,
          legacyReason: input.legacyReason,
        },
      },
    ],
  };
}

function expectPlannerBlocker(
  blockers: readonly RenderBlocker[],
  expected: Pick<RenderBlocker, 'id' | 'route' | 'reason' | 'message'> & {
    readonly detail?: unknown;
  },
): void {
  const blocker = blockers.find((candidate) => candidate.id === expected.id);
  expect(blocker).toBeDefined();
  expect(blocker).toMatchObject({
    severity: 'error',
    ...expected,
  });
}

interface RenderDependentOutputOptions {
  readonly availableRoutes?: readonly RenderRoute[];
  readonly routeRequirementRoutes?: readonly RenderRoute[];
  readonly requiredCapabilities?: readonly string[];
  readonly processRequirementCapabilities?: readonly string[];
  readonly processId?: string;
  readonly operationId?: string;
  readonly unavailableMessage?: string;
  readonly determinism?: 'deterministic' | 'preview-only' | 'live-unbaked' | 'process-dependent' | 'unknown';
}

function renderDependentOutput(options: RenderDependentOutputOptions = {}): VideoEditorOutputFormatDescriptor {
  const availableRoutes = options.availableRoutes ?? ['sidecar-export'];
  const routeRequirementRoutes = options.routeRequirementRoutes ?? availableRoutes;
  const processId = options.processId ?? 'dataset-process';
  const operationId = options.operationId ?? 'exportDataset';
  const requiredCapabilities = options.requiredCapabilities ?? ['sidecar-export', 'json-rpc'];
  const processRequirementCapabilities = options.processRequirementCapabilities ?? ['json-rpc'];
  const unavailableMessage = options.unavailableMessage ?? 'Start the dataset process before exporting the bundle.';
  const determinism = options.determinism ?? 'process-dependent';

  return {
    id: 'dataset.zip',
    extensionId: 'ext.dataset',
    order: 2,
    label: 'Dataset bundle',
    requiresRender: true,
    outputExtension: '.zip',
    outputMimeType: 'application/zip',
    disabled: false,
    availableRoutes,
    routeRequirements: [
      {
        routes: routeRequirementRoutes,
        requiredCapabilities,
        processId,
        operationId,
        determinism,
        unavailableMessage,
      },
    ],
    processRequirements: [
      {
        processId,
        operationId,
        requiredCapabilities: processRequirementCapabilities,
      },
    ],
    blockers: [],
    nextActions: availableRoutes.map((route) => ({
      kind: 'select-route' as const,
      label: `Plan ${route}`,
      route,
      processId,
      operationId,
    })),
    capabilities: {
      extensionId: 'ext.dataset',
      contributionId: 'dataset.zip',
      routes: availableRoutes,
      determinism,
      fullySupported: true,
      anyBlocked: false,
      sourceRefs: [
        { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
      ],
      capabilityRequirements: availableRoutes.map((route) => ({
          id: `ext.dataset.dataset.zip.${route}`,
          sourceRef: { source: 'extension', extensionId: 'ext.dataset', contributionId: 'dataset.zip' },
          route,
          requiredCapabilities: [route],
          determinism,
          routeFit: { route, fit: 'supported' as const },
          blocking: false,
        })),
    },
    sidecars: [],
  };
}

interface ProcessDescriptorOptions {
  readonly processId?: string;
  readonly operationId?: string;
  readonly routes?: readonly RenderRoute[];
  readonly protocol?: string;
  readonly requiredCapabilities?: readonly string[];
  readonly outputKinds?: readonly ('artifact' | 'material' | 'sidecar' | 'diagnostic' | 'planner-result' | 'tool-result')[];
}

function processDescriptor(options: ProcessDescriptorOptions = {}): VideoEditorProcessDescriptor {
  const processId = options.processId ?? 'dataset-process';
  const operationId = options.operationId ?? 'exportDataset';
  const routes = options.routes ?? ['sidecar-export'];
  const protocol = options.protocol ?? 'stdio-jsonrpc';
  const requiredCapabilities = options.requiredCapabilities;
  const outputKinds = options.outputKinds;
  const operation = {
    id: operationId,
    label: 'Export dataset',
    routes,
    ...(requiredCapabilities ? { requiredCapabilities } : {}),
    ...(outputKinds ? { outputKinds } : {}),
  };

  return {
    id: 'process-contribution',
    extensionId: 'ext.dataset',
    processId,
    label: 'Dataset process',
    spec: {
      id: processId,
      label: 'Dataset process',
      protocol: protocol as VideoEditorProcessDescriptor['protocol'],
      spawn: {
        command: 'node',
        args: ['dataset-process.js'],
      },
      operations: [operation],
    },
    protocol: protocol as VideoEditorProcessDescriptor['protocol'],
    operations: [operation],
    availableRoutes: routes,
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

function shaderGraphInput(
  snapshot: TimelineSnapshot = snapshotWithShaders(),
  contributionIndex: ContributionIndex = shaderContributionIndex([
    { contributionId: 'ext.shader.clip' },
    { contributionId: 'ext.shader.post' },
  ]),
) {
  return {
    snapshot,
    extensionRuntime: {
      outputFormats: [],
      processes: [],
      shaders: [],
      contributionIndex,
      compositionGraph: projectCompositionGraph({ snapshot, contributionIndex }),
    },
  };
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

function attachedMaterial(
  id: string,
  overrides: Partial<RenderMaterial> = {},
): RenderMaterial {
  return {
    id,
    mediaKind: 'video',
    locator: { kind: 'provider', uri: `provider://materials/${id}` },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    provenance: {
      origin: 'process',
    },
    ...overrides,
  };
}

function attachedSidecar(
  filename: string,
  overrides: Partial<RenderArtifactSidecarDescriptor> = {},
): RenderArtifactSidecarDescriptor {
  return {
    id: `sidecar.metadata.${filename}`,
    filename,
    mimeType: 'application/json',
    kind: 'metadata',
    ...overrides,
  };
}

function attachedArtifact(
  id: string,
  route: RenderRoute,
  overrides: Partial<RenderArtifact> = {},
): RenderArtifact {
  const outputFormatId = overrides.manifest?.outputFormatId
    ?? (route === 'browser-export' || route === 'worker-export' ? 'video.mp4' : undefined);
  const locator = overrides.locator ?? {
    kind: 'artifact-store' as const,
    uri: `artifact://${id}`,
    mimeType: route === 'preview'
      ? 'image/png'
      : route === 'sidecar-export'
        ? 'application/json'
        : 'video/mp4',
  };
  const mediaKind = overrides.mediaKind
    ?? (route === 'preview'
      ? 'image'
      : route === 'sidecar-export'
        ? 'json'
        : 'video');
  const sidecars = overrides.sidecars ?? [];
  return {
    id,
    route,
    locator,
    mediaKind,
    producerExtensionId: 'ext.dataset',
    consumedMaterialRefs: [],
    determinism: 'deterministic',
    boundary: {
      source: 'worker',
      target: 'export-output',
      route,
      failureBehavior: 'block-export',
    },
    sidecars,
    manifest: createRenderArtifactManifest({
      artifactId: id,
      route,
      determinism: 'deterministic',
      profile: route === 'preview'
        ? 'preview'
        : mediaKind === 'audio'
          ? 'audio'
          : (route === 'sidecar-export' || mediaKind !== 'video')
            ? 'sidecar'
            : 'video',
      ...(outputFormatId ? { outputFormatId } : {}),
      locator,
      mediaKind,
      consumedMaterialRefs: [],
      sidecars,
      provenance: { source: 'test' },
      ...(mediaKind === 'audio' || mediaKind === 'video'
        ? { inputHashes: { [`asset://${id}`]: `sha256:${id}` } }
        : {}),
    }),
    ...overrides,
  };
}

function attachResult(
  overrides: Partial<ProcessRoundtripResult> = {},
): ProcessRoundtripResult {
  return {
    requestId: 'attach-request-1',
    processId: 'dataset-process',
    operationId: 'exportDataset',
    status: 'completed',
    returnedMaterials: [attachedMaterial('mat-attached')],
    artifacts: [],
    sidecars: [],
    diagnostics: [],
    logs: [],
    availableActions: [],
    ...overrides,
  };
}

function exportDiagnostic(
  overrides: Pick<ExportDiagnostic, 'code' | 'message' | 'severity'> & Partial<ExportDiagnostic>,
): ExportDiagnostic {
  return overrides;
}

describe('planRender', () => {
  it('emits router-fed generated-module missing-artifact blockers with complete planner metadata', () => {
    const message = 'Clip type "generated-remotion-module" cannot be rendered until remotion_module_missing_artifact is resolved.';
    const result = planRender({
      requirements: [
        routerRequirement({
          id: 'router.clip.0.generated-remotion-module.browser-export',
          route: 'browser-export',
          clipType: 'generated-remotion-module',
          reason: 'missing-material',
          legacyReason: 'remotion_module_missing_artifact',
          message,
        }),
        routerRequirement({
          id: 'router.clip.0.generated-remotion-module.worker-export',
          route: 'worker-export',
          clipType: 'generated-remotion-module',
          reason: 'missing-material',
          legacyReason: 'remotion_module_missing_artifact',
          message,
          requiredCapabilities: ['worker-export'],
        }),
      ],
    });

    expectPlannerBlocker(result.blockers, {
      id: 'router.clip.0.generated-remotion-module.browser-export.browser-export.missing-material',
      route: 'browser-export',
      reason: 'missing-material',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'remotion_module_missing_artifact',
      },
    });
    expectPlannerBlocker(result.blockers, {
      id: 'router.clip.0.generated-remotion-module.worker-export.worker-export.missing-material',
      route: 'worker-export',
      reason: 'missing-material',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'remotion_module_missing_artifact',
      },
    });
    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
  });

  it('emits router-fed contributed clip conflict blockers with route and legacy reason metadata', () => {
    const message = 'Clip type "generated-remotion-module" cannot be rendered until contributed_blocked_worker_route_conflict is resolved.';
    const result = planRender({
      requirements: [
        routerRequirement({
          id: 'router.generated.contributed-conflict.browser-export',
          route: 'browser-export',
          clipType: 'generated-remotion-module',
          reason: 'route-unsupported',
          legacyReason: 'contributed_blocked_worker_route_conflict',
          message,
        }),
        routerRequirement({
          id: 'router.generated.contributed-conflict.worker-export',
          route: 'worker-export',
          clipType: 'generated-remotion-module',
          reason: 'route-unsupported',
          legacyReason: 'contributed_blocked_worker_route_conflict',
          message,
          requiredCapabilities: ['worker-export'],
        }),
      ],
    });

    expectPlannerBlocker(result.blockers, {
      id: 'router.generated.contributed-conflict.browser-export.browser-export.route-unsupported',
      route: 'browser-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
    expectPlannerBlocker(result.blockers, {
      id: 'router.generated.contributed-conflict.worker-export.worker-export.route-unsupported',
      route: 'worker-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
  });

  it('emits request-owned worker, disabled-format, and compile-only handler blockers with detail metadata', () => {
    const disabledFormat: VideoEditorOutputFormatDescriptor = {
      ...renderDependentOutput({ availableRoutes: ['browser-export'] }),
      requiresRender: false,
      disabled: true,
      disabledReason: 'Encoder is disabled by policy.',
      routeRequirements: [],
      processRequirements: [],
      blockers: [],
      nextActions: [],
      capabilities: undefined,
    };
    const compileOnlyFormat: VideoEditorOutputFormatDescriptor = {
      ...disabledFormat,
      disabled: false,
    };

    const workerUnavailable = planRender({
      request: {
        route: 'worker-export',
        routeAvailability: [{
          route: 'worker-export',
          available: false,
          providerId: 'worker-banodoco',
          message: 'Worker render unavailable for route "generated_remotion_module".',
          detail: { legacyReason: 'generated_remotion_module' },
        }],
      },
    });
    expectPlannerBlocker(workerUnavailable.blockers, {
      id: 'planner.request.worker-export.worker-banodoco.unavailable',
      route: 'worker-export',
      reason: 'process-dependent',
      message: 'Worker render unavailable for route "generated_remotion_module".',
      detail: expect.objectContaining({
        source: 'render-request',
        routeAvailability: 'unavailable',
        providerId: 'worker-banodoco',
        requestedRoute: 'worker-export',
        legacyReason: 'generated_remotion_module',
      }),
    });

    const disabled = planRender({
      outputFormats: [disabledFormat],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });
    expectPlannerBlocker(disabled.blockers, {
      id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.disabled',
      route: 'browser-export',
      reason: 'inactive-extension',
      message: 'Encoder is disabled by policy.',
      detail: expect.objectContaining({
        source: 'render-request',
        outputFormatId: 'dataset.zip',
        requestedRoute: 'browser-export',
        disabled: true,
      }),
    });

    const compileOnlyMissing = planRender({
      outputFormats: [compileOnlyFormat],
      request: {
        outputFormatId: 'dataset.zip',
        route: 'browser-export',
        compileOnlyHandlerAvailable: false,
      },
    });
    expectPlannerBlocker(compileOnlyMissing.blockers, {
      id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.compile-handler-missing',
      route: 'browser-export',
      reason: 'missing-contribution',
      message: 'Export format "Dataset bundle" has no compile-only output handlers registered.',
      detail: expect.objectContaining({
        source: 'render-request',
        outputFormatId: 'dataset.zip',
        requestedRoute: 'browser-export',
        compileOnlyHandlerAvailable: false,
      }),
    });
  });

  it('emits guard-fed unknown contribution and export diagnostic blockers with preserved detail metadata', () => {
    const liveBindingDiagnostic = exportDiagnostic({
      severity: 'error',
      code: 'export/live-binding-unresolved',
      message: 'Live binding webcam-1 must be baked before export.',
      extensionId: 'ext.live',
      contributionId: 'clip.webcam',
      detail: {
        clipId: 'clip-live',
        clipType: 'webcam-live',
        renderRoute: 'browser-export',
        sourceId: 'webcam-1',
      },
    });
    const result = buildExportReadinessPlan({
      guard: {
        unknownClipTypes: ['clip.unknown'],
        unknownEffects: ['effect.unknown'],
        unknownTransitions: ['transition.unknown'],
        diagnostics: [liveBindingDiagnostic],
      },
    });

    expectPlannerBlocker(result.blockers, {
      id: 'planner.guard.unknown-clip-type.clip.unknown.browser-export',
      route: 'browser-export',
      reason: 'missing-contribution',
      message: 'Unknown clip type "clip.unknown" cannot be exported on browser-export.',
      detail: expect.objectContaining({
        source: 'export-guard-compat',
        code: 'export/unknown-clip-type',
        contributionKind: 'clip-type',
        contributionId: 'clip.unknown',
        renderRoute: 'browser-export',
      }),
    });
    expectPlannerBlocker(result.blockers, {
      id: 'planner.guard.unknown-effect.effect.unknown.worker-export',
      route: 'worker-export',
      reason: 'missing-contribution',
      message: 'Unknown effect "effect.unknown" cannot be exported on worker-export.',
      detail: expect.objectContaining({
        source: 'export-guard-compat',
        code: 'export/unknown-effect',
        contributionKind: 'effect',
        contributionId: 'effect.unknown',
        renderRoute: 'worker-export',
      }),
    });
    expectPlannerBlocker(result.blockers, {
      id: 'planner.guard.unknown-transition.transition.unknown.sidecar-export',
      route: 'sidecar-export',
      reason: 'missing-contribution',
      message: 'Unknown transition "transition.unknown" cannot be exported on sidecar-export.',
      detail: expect.objectContaining({
        source: 'export-guard-compat',
        code: 'export/unknown-transition',
        contributionKind: 'transition',
        contributionId: 'transition.unknown',
        renderRoute: 'sidecar-export',
      }),
    });
    expectPlannerBlocker(result.blockers, {
      id: 'export-guard:export/live-binding-unresolved:ext.live:clip.webcam:clip-live:webcam-live',
      route: 'browser-export',
      reason: 'live-unbaked',
      message: 'Live binding webcam-1 must be baked before export.',
      detail: expect.objectContaining({
        source: 'export-guard-compat',
        code: 'export/live-binding-unresolved',
        diagnosticDetail: {
          clipId: 'clip-live',
          clipType: 'webcam-live',
          renderRoute: 'browser-export',
          sourceId: 'webcam-1',
        },
      }),
    });
  });

  it('emits existing planner-owned output and process blockers with stable blocker fields', () => {
    const missingOutput = planRender({
      outputFormats: [renderDependentOutput()],
      request: { outputFormatId: 'missing.format', route: 'sidecar-export' },
    });
    expectPlannerBlocker(missingOutput.blockers, {
      id: 'planner.outputFormat.missing.format.missing',
      route: 'sidecar-export',
      reason: 'missing-contribution',
      message: 'Output format "missing.format" is not registered.',
      detail: {
        source: 'render-request',
        outputFormatId: 'missing.format',
      },
    });

    const unsupportedOutputRoute = planRender({
      outputFormats: [renderDependentOutput({ availableRoutes: ['sidecar-export'] })],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });
    expectPlannerBlocker(unsupportedOutputRoute.blockers, {
      id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.route-unsupported',
      route: 'browser-export',
      reason: 'route-unsupported',
      message: 'Output format "Dataset bundle" is not available on browser-export.',
      detail: expect.objectContaining({
        source: 'render-request',
        outputFormatId: 'dataset.zip',
        requestedRoute: 'browser-export',
      }),
    });

    const processNotInstalled = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [{
        processId: 'dataset-process',
        state: 'not-installed',
        installHint: 'Install the dataset bridge.',
      }],
      request: { outputFormatId: 'dataset.zip' },
    });
    expectPlannerBlocker(processNotInstalled.blockers, {
      id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-not-installed',
      route: 'sidecar-export',
      reason: 'process-not-installed',
      message: 'Process "dataset-process" is not installed for sidecar-export. Hint: Install the dataset bridge.',
      detail: expect.objectContaining({
        source: 'output-format',
        outputFormatId: 'dataset.zip',
        outputLabel: 'Dataset bundle',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        routeScope: 'sidecar-export',
        processProtocol: 'stdio-jsonrpc',
        installHint: 'Install the dataset bridge.',
        processState: 'not-installed',
        lifecycleState: 'not-installed',
      }),
    });
  });

  it('preserves guard-fed unknown IDs as planner-owned missing-contribution blockers', () => {
    const result = buildExportReadinessPlan({
      guard: {
        unknownClipTypes: ['clip.z', 'clip.a'],
        unknownEffects: ['effect.z', 'effect.a'],
        unknownTransitions: ['transition.z', 'transition.a'],
        inactiveExtensionIds: {
          effectIds: new Set(['effect.reserved']),
          transitionIds: new Set(['transition.reserved']),
          clipTypeIds: new Set(['clip.reserved']),
        },
      },
    });

    expect(result.guard.unknownClipTypes).toEqual(['clip.a', 'clip.z']);
    expect(result.guard.unknownEffects).toEqual(['effect.a', 'effect.z']);
    expect(result.guard.unknownTransitions).toEqual(['transition.a', 'transition.z']);
    expect(result.guard.inactiveExtensionIds.effectIds).toEqual(new Set(['effect.reserved']));
    expect(result.guard.inactiveExtensionIds.transitionIds).toEqual(new Set(['transition.reserved']));
    expect(result.guard.inactiveExtensionIds.clipTypeIds).toEqual(new Set(['clip.reserved']));
    expect(result.guard.hasBlockingErrors).toBe(true);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.guard.unknown-clip-type.clip.a.browser-export',
        route: 'browser-export',
        reason: 'missing-contribution',
        contributionId: 'clip.a',
        detail: expect.objectContaining({
          source: 'export-guard-compat',
          code: 'export/unknown-clip-type',
        }),
      }),
      expect.objectContaining({
        id: 'planner.guard.unknown-effect.effect.a.worker-export',
        route: 'worker-export',
        reason: 'missing-contribution',
        contributionId: 'effect.a',
        detail: expect.objectContaining({
          source: 'export-guard-compat',
          code: 'export/unknown-effect',
        }),
      }),
      expect.objectContaining({
        id: 'planner.guard.unknown-transition.transition.a.sidecar-export',
        route: 'sidecar-export',
        reason: 'missing-contribution',
        contributionId: 'transition.a',
        detail: expect.objectContaining({
          source: 'export-guard-compat',
          code: 'export/unknown-transition',
        }),
      }),
    ]));
    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.canSidecarExport).toBe(false);
  });

  it('keeps warning-only inactive extension diagnostics non-blocking', () => {
    const warning = exportDiagnostic({
      severity: 'warning',
      code: 'export/unsupported-reserved-target',
      message: 'Effect effect.reserved is reserved by an inactive extension.',
      extensionId: 'ext.inactive',
      contributionId: 'effect.reserved',
      detail: {
        effectType: 'effect.reserved',
        renderRoute: 'browser-export',
        blockerReason: 'inactive-extension',
      },
    });

    const result = buildExportReadinessPlan({
      guard: {
        diagnostics: [warning],
        inactiveExtensionIds: {
          effectIds: new Set(['effect.reserved']),
          transitionIds: new Set(['transition.reserved']),
          clipTypeIds: new Set(['clip.reserved']),
        },
      },
    });

    expect(result.guard.unknownClipTypes).toEqual([]);
    expect(result.guard.unknownEffects).toEqual([]);
    expect(result.guard.unknownTransitions).toEqual([]);
    expect(result.guard.inactiveExtensionIds.effectIds).toEqual(new Set(['effect.reserved']));
    expect(result.guard.inactiveExtensionIds.transitionIds).toEqual(new Set(['transition.reserved']));
    expect(result.guard.inactiveExtensionIds.clipTypeIds).toEqual(new Set(['clip.reserved']));
    expect(result.guard.hasBlockingErrors).toBe(false);

    const finding = result.findings.find((item) => item.detail?.code === 'export/unsupported-reserved-target');
    expect(finding).toMatchObject({
      severity: 'warning',
      route: 'browser-export',
      message: 'Effect effect.reserved is reserved by an inactive extension.',
      extensionId: 'ext.inactive',
      contributionId: 'effect.reserved',
      detail: {
        source: 'export-guard-compat',
        code: 'export/unsupported-reserved-target',
        diagnosticDetail: {
          effectType: 'effect.reserved',
          renderRoute: 'browser-export',
          blockerReason: 'inactive-extension',
        },
      },
    });
    expect(finding?.reason).toBeUndefined();
    expect(result.blockers).toEqual([]);
    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(true);
    expect(result.canSidecarExport).toBe(true);
  });

  it('maps known and unknown export diagnostics to planner reasons while preserving diagnostic metadata', () => {
    const knownDiagnostic = exportDiagnostic({
      severity: 'error',
      code: 'export/unrenderable-effect',
      message: 'Effect effect.preview cannot render on worker export.',
      extensionId: 'ext.effects',
      contributionId: 'effect.preview',
      detail: {
        clipId: 'clip-1',
        effectType: 'effect.preview',
        renderRoute: 'worker-export',
        blockerReason: 'live-unbaked',
      },
    });
    const unknownDiagnostic = exportDiagnostic({
      severity: 'error',
      code: 'export/vendor-specific' as `export/${string}`,
      message: 'Vendor-specific export readiness failed.',
      extensionId: 'ext.vendor',
      contributionId: 'vendor.effect',
      detail: {
        clipId: 'clip-2',
        effectType: 'vendor.effect',
        renderRoute: 'sidecar-export',
        vendorDetail: 'preserved',
      },
    });
    const liveBindingDiagnostic = exportDiagnostic({
      severity: 'error',
      code: 'export/live-binding-unresolved',
      message: 'Live binding webcam-1 must be baked before export.',
      extensionId: 'ext.live',
      contributionId: 'clip.webcam',
      detail: {
        clipId: 'clip-live',
        clipType: 'webcam-live',
        renderRoute: 'browser-export',
        sourceId: 'webcam-1',
      },
    });

    const result = buildExportReadinessPlan({
      guard: {
        diagnostics: [
          unknownDiagnostic,
          liveBindingDiagnostic,
          knownDiagnostic,
        ],
      },
    });
    const findingForCode = (code: string): CapabilityFinding | undefined =>
      result.findings.find((finding) => finding.detail?.code === code);

    expect(findingForCode('export/unrenderable-effect')).toMatchObject({
      severity: 'error',
      route: 'worker-export',
      reason: 'route-unsupported',
      message: 'Effect effect.preview cannot render on worker export.',
      extensionId: 'ext.effects',
      contributionId: 'effect.preview',
      detail: {
        source: 'export-guard-compat',
        code: 'export/unrenderable-effect',
        diagnosticDetail: {
          clipId: 'clip-1',
          effectType: 'effect.preview',
          renderRoute: 'worker-export',
          blockerReason: 'live-unbaked',
        },
      },
    });
    expect(findingForCode('export/vendor-specific')).toMatchObject({
      severity: 'error',
      route: 'sidecar-export',
      reason: 'unknown',
      detail: {
        source: 'export-guard-compat',
        code: 'export/vendor-specific',
        diagnosticDetail: {
          clipId: 'clip-2',
          effectType: 'vendor.effect',
          renderRoute: 'sidecar-export',
          vendorDetail: 'preserved',
        },
      },
    });
    expect(findingForCode('export/live-binding-unresolved')).toMatchObject({
      severity: 'error',
      route: 'browser-export',
      reason: 'live-unbaked',
      detail: {
        source: 'export-guard-compat',
        code: 'export/live-binding-unresolved',
        diagnosticDetail: {
          clipId: 'clip-live',
          clipType: 'webcam-live',
          renderRoute: 'browser-export',
          sourceId: 'webcam-1',
        },
      },
    });
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({ reason: 'route-unsupported', route: 'worker-export' }),
      expect.objectContaining({ reason: 'unknown', route: 'sidecar-export' }),
      expect.objectContaining({ reason: 'live-unbaked', route: 'browser-export' }),
    ]));
    expect(result.guard.hasBlockingErrors).toBe(true);
    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.canSidecarExport).toBe(false);
  });

  it('keeps buildExportReadinessPlan wrapper readiness identical to direct planRender reduction', () => {
    const guardDiagnostic = exportDiagnostic({
      severity: 'error',
      code: 'export/live-binding-unresolved',
      message: 'Live binding webcam-1 must be baked before export.',
      extensionId: 'ext.live',
      contributionId: 'clip.webcam',
      detail: {
        clipId: 'clip-live',
        clipType: 'webcam-live',
        renderRoute: 'browser-export',
        sourceId: 'webcam-1',
      },
    });
    const adaptedGuardDiagnostic: CapabilityFinding = {
      id: 'export-guard:export/live-binding-unresolved:ext.live:clip.webcam:clip-live:webcam-live',
      severity: 'error',
      route: 'browser-export',
      reason: 'live-unbaked',
      message: 'Live binding webcam-1 must be baked before export.',
      extensionId: 'ext.live',
      contributionId: 'clip.webcam',
      detail: {
        source: 'export-guard-compat',
        code: 'export/live-binding-unresolved',
        diagnosticDetail: {
          clipId: 'clip-live',
          clipType: 'webcam-live',
          renderRoute: 'browser-export',
          sourceId: 'webcam-1',
        },
      },
    };
    const guardFinding: CapabilityFinding = {
      id: 'guard.finding.worker-warning',
      severity: 'warning',
      route: 'worker-export',
      reason: 'unknown',
      message: 'Worker support was not proven by the guard scan.',
      detail: { source: 'export-guard' },
    };
    const guardBlocker: RenderBlocker = {
      id: 'guard.blocker.sidecar',
      severity: 'error',
      route: 'sidecar-export',
      reason: 'unknown',
      message: 'Sidecar export was blocked by guard input.',
      detail: { source: 'export-guard' },
    };

    const wrapperResult = buildExportReadinessPlan({
      guard: {
        diagnostics: [guardDiagnostic],
        findings: [guardFinding],
        blockers: [guardBlocker],
      },
    });
    const directResult = planRender({
      diagnostics: [
        adaptedGuardDiagnostic,
        guardFinding,
        guardBlocker,
      ],
    });

    expect(wrapperResult.guard.diagnostics).toEqual([adaptedGuardDiagnostic]);
    expect(wrapperResult.guard.findings).toEqual([guardFinding]);
    expect(wrapperResult.guard.blockers).toEqual([guardBlocker]);
    expect(wrapperResult.findings).toEqual(directResult.findings);
    expect(wrapperResult.blockers).toEqual(directResult.blockers);
    expect(wrapperResult.routes).toEqual(directResult.routes);
    expect(wrapperResult.routePlans).toEqual(directResult.routePlans);
    expect(wrapperResult.diagnostics).toEqual(directResult.diagnostics);
    expect(wrapperResult.nextActions).toEqual(directResult.nextActions);
    expect(wrapperResult.canBrowserExport).toBe(directResult.canBrowserExport);
    expect(wrapperResult.canWorkerExport).toBe(directResult.canWorkerExport);
    expect(wrapperResult.canSidecarExport).toBe(directResult.canSidecarExport);
  });

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
    const result = planRender(shaderGraphInput());

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
    const snapshot = {
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
    } satisfies TimelineSnapshot;
    const contributionIndex = shaderContributionIndex([
      { contributionId: 'ext.shader.clip' },
      {
        contributionId: 'ext.shader.clip.disabled',
        status: 'disabled',
        projected: false,
        projectionEligible: false,
        source: 'preserved-record',
      },
    ]);
    const result = planRender({
      snapshot,
      extensionRuntime: {
        outputFormats: [],
        processes: [],
        shaders: [],
        contributionIndex,
        compositionGraph: projectCompositionGraph({ snapshot, contributionIndex }),
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
      expect.objectContaining({
        contributionId: 'ext.shader.clip.disabled',
        reason: 'missing-material',
      }),
    ]));
  });

  it('uses registered shader materializer process routes for materialization next actions', () => {
    const graphInput = shaderGraphInput();
    const result = planRender({
      ...graphInput,
      shaders: [shaderMaterializerDescriptor()],
      processes: [shaderMaterializerProcess()],
      extensionRuntime: {
        ...graphInput.extensionRuntime,
        shaders: [shaderMaterializerDescriptor()],
        processes: [shaderMaterializerProcess()],
      },
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
        id: 'graph.shader.0.browser-export.browser-export.process-dependent',
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
        id: 'graph.shader.0.browser-export.browser-export.shader-materializer.discovered',
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
        processId: 'dataset-process',
        operationId: 'exportDataset',
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.route.process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
        processId: 'dataset-process',
        operationId: 'exportDataset',
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

  it('blocks only explicitly requested disabled output formats', () => {
    const disabledFormat: VideoEditorOutputFormatDescriptor = {
      ...renderDependentOutput({ availableRoutes: ['browser-export'] }),
      requiresRender: false,
      disabled: true,
      disabledReason: 'Encoder is disabled by policy.',
      routeRequirements: [],
      processRequirements: [],
      blockers: [],
      nextActions: [],
      capabilities: undefined,
    };

    const generalPlan = planRender({
      outputFormats: [disabledFormat],
    });
    expect(generalPlan.canBrowserExport).toBe(true);
    expect(generalPlan.blockers).toEqual([]);

    const requestedPlan = planRender({
      outputFormats: [disabledFormat],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });
    expect(requestedPlan.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.disabled',
        route: 'browser-export',
        reason: 'inactive-extension',
        message: 'Encoder is disabled by policy.',
        detail: expect.objectContaining({
          source: 'render-request',
          outputFormatId: 'dataset.zip',
          disabled: true,
        }),
      }),
    ]);
  });

  it('blocks compile-only handler absence only for the requested format', () => {
    const compileOnlyFormat: VideoEditorOutputFormatDescriptor = {
      ...renderDependentOutput({ availableRoutes: ['browser-export'] }),
      requiresRender: false,
      disabled: false,
      routeRequirements: [],
      processRequirements: [],
      blockers: [],
      nextActions: [],
      capabilities: undefined,
    };

    const generalPlan = planRender({
      outputFormats: [compileOnlyFormat],
      request: { compileOnlyHandlerAvailable: false },
    });
    expect(generalPlan.blockers).toEqual([]);

    const requestedPlan = planRender({
      outputFormats: [compileOnlyFormat],
      request: {
        outputFormatId: 'dataset.zip',
        route: 'browser-export',
        compileOnlyHandlerAvailable: false,
      },
    });
    expect(requestedPlan.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.compile-handler-missing',
        route: 'browser-export',
        reason: 'missing-contribution',
        message: 'Export format "Dataset bundle" has no compile-only output handlers registered.',
        detail: expect.objectContaining({
          source: 'render-request',
          outputFormatId: 'dataset.zip',
          compileOnlyHandlerAvailable: false,
        }),
      }),
    ]);
  });

  it('uses request-scoped route availability blockers without blocking unrelated routes', () => {
    const result = planRender({
      request: {
        route: 'worker-export',
        routeAvailability: [{
          route: 'worker-export',
          available: false,
          providerId: 'worker-banodoco',
          message: 'Worker render unavailable for route "generated_remotion_module".',
        }],
      },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'worker-export')).toMatchObject({
      blocked: true,
      blockers: [
        expect.objectContaining({
          id: 'planner.request.worker-export.worker-banodoco.unavailable',
          route: 'worker-export',
          reason: 'process-dependent',
          message: 'Worker render unavailable for route "generated_remotion_module".',
          detail: expect.objectContaining({
            source: 'render-request',
            routeAvailability: 'unavailable',
            providerId: 'worker-banodoco',
          }),
        }),
      ],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')?.blocked).toBe(false);
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')?.blocked).toBe(false);
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

  it('projects process.result.attach evidence before material runtime planning while preserving legacy material status fallbacks', () => {
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      attachedAt: '2026-07-04T22:20:00.000Z',
      result: attachResult(),
    });

    const result = planRender({
      processes: [processDescriptor()],
      processStatuses: [{ processId: 'dataset-process', state: 'ready' }],
      materialRefs: [
        materialRef('mat-attached', { producerExtensionId: undefined }),
        materialRef('mat-legacy'),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-attached',
          state: 'pending',
          detail: { phase: 'active' },
          message: 'Legacy status should be superseded by attach evidence.',
        },
        {
          materialRefId: 'mat-legacy',
          state: 'failed',
          message: 'Legacy failed status should still block without attach evidence.',
        },
      ],
      processResultAttachRecords: [attachRecord],
    });

    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-attached')).toBe(false);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'planner.material.mat-legacy.browser-export.materialization-error',
        materialRefId: 'mat-legacy',
        reason: 'materialization-error',
      }),
    ]);
    expect(result.nextActions).toEqual([
      expect.objectContaining({
        kind: 'open-settings',
        label: 'Open settings for mat-legacy',
      }),
    ]);
  });

  it('keeps route artifact completion incomplete until every required profile has evidence', () => {
    const format = {
      ...renderDependentOutput({
        availableRoutes: ['browser-export'],
        routeRequirementRoutes: ['browser-export'],
      }),
      outputExtension: '.mp4',
      outputMimeType: 'video/mp4',
      sidecars: [attachedSidecar('dataset-metadata.json')],
    };
    const process = processDescriptor({
      routes: ['browser-export'],
      outputKinds: ['artifact', 'sidecar'],
    });
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: process,
      attachedAt: '2026-07-04T22:30:00.000Z',
      result: attachResult({
        artifacts: [attachedArtifact('artifact.video.partial', 'browser-export')],
      }),
    });

    const result = planRender({
      outputFormats: [format],
      processes: [process],
      processStatuses: [{ processId: 'dataset-process', state: 'ready' }],
      materialRefs: [materialRef('mat-export', { determinism: 'deterministic' })],
      materialStatuses: [{ materialRefId: 'mat-export', state: 'resolved' }],
      processResultAttachRecords: [attachRecord],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      artifactCompletion: {
        status: 'incomplete',
        requiredProfiles: ['video', 'sidecar'],
        completeProfiles: ['video'],
        incompleteProfiles: ['sidecar'],
        blockedProfiles: [],
      },
    });

    const browserCompletion = result.routePlans.find((routePlan) => routePlan.route === 'browser-export')!.artifactCompletion;
    expect(browserCompletion.profiles.find((profile) => profile.profile === 'video')).toMatchObject({
      status: 'complete',
      artifacts: [expect.objectContaining({ id: 'artifact.video.partial' })],
      requiredBy: expect.arrayContaining([
        expect.objectContaining({ source: 'output-format', outputFormatId: 'dataset.zip' }),
        expect.objectContaining({ source: 'process-requirement', processId: 'dataset-process' }),
        expect.objectContaining({ source: 'material-requirement', materialRefId: 'mat-export' }),
        expect.objectContaining({ source: 'process-attach-record', taskId: 'attach-request-1' }),
      ]),
    });
    expect(browserCompletion.profiles.find((profile) => profile.profile === 'sidecar')).toMatchObject({
      status: 'incomplete',
      sidecars: [],
      requiredBy: expect.arrayContaining([
        expect.objectContaining({ source: 'output-format-sidecar', outputFormatId: 'dataset.zip' }),
        expect.objectContaining({ source: 'process-requirement', processId: 'dataset-process' }),
        expect.objectContaining({ source: 'process-attach-record', taskId: 'attach-request-1' }),
      ]),
    });
  });

  it('marks route artifact completion complete once primary artifacts and sidecars are both attached', () => {
    const format = {
      ...renderDependentOutput({
        availableRoutes: ['browser-export'],
        routeRequirementRoutes: ['browser-export'],
      }),
      outputExtension: '.mp4',
      outputMimeType: 'video/mp4',
      sidecars: [attachedSidecar('dataset-metadata.json')],
    };
    const process = processDescriptor({
      routes: ['browser-export'],
      outputKinds: ['artifact', 'sidecar'],
    });
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: process,
      attachedAt: '2026-07-04T22:35:00.000Z',
      result: attachResult({
        artifacts: [attachedArtifact('artifact.video.complete', 'browser-export')],
        sidecars: [attachedSidecar('route-metadata.json')],
      }),
    });

    const result = planRender({
      outputFormats: [format],
      processes: [process],
      processStatuses: [{ processId: 'dataset-process', state: 'ready' }],
      processResultAttachRecords: [attachRecord],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      artifactCompletion: {
        status: 'complete',
        requiredProfiles: ['video', 'sidecar'],
        completeProfiles: ['video', 'sidecar'],
        incompleteProfiles: [],
        blockedProfiles: [],
      },
    });
    expect(
      result.routePlans.find((routePlan) => routePlan.route === 'browser-export')
        ?.artifactCompletion.profiles.find((profile) => profile.profile === 'sidecar'),
    ).toMatchObject({
      status: 'complete',
      sidecars: [expect.objectContaining({ filename: 'route-metadata.json' })],
    });
  });

  it('marks route artifact completion blocked when route blockers remain after partial artifact attachment', () => {
    const format = {
      ...renderDependentOutput({
        availableRoutes: ['browser-export'],
        routeRequirementRoutes: ['browser-export'],
      }),
      outputExtension: '.mp4',
      outputMimeType: 'video/mp4',
      sidecars: [attachedSidecar('dataset-metadata.json')],
    };
    const process = processDescriptor({
      routes: ['browser-export'],
      outputKinds: ['artifact', 'sidecar'],
    });
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: process,
      attachedAt: '2026-07-04T22:40:00.000Z',
      result: attachResult({
        artifacts: [attachedArtifact('artifact.video.blocked', 'browser-export')],
      }),
    });

    const result = planRender({
      outputFormats: [format],
      processes: [process],
      processStatuses: [{ processId: 'dataset-process', state: 'stopped' }],
      processResultAttachRecords: [attachRecord],
      request: { outputFormatId: 'dataset.zip', route: 'browser-export' },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      artifactCompletion: {
        status: 'blocked',
        requiredProfiles: ['video', 'sidecar'],
        completeProfiles: ['video'],
        incompleteProfiles: ['sidecar'],
        blockedProfiles: [],
      },
    });
    expect(
      result.routePlans.find((routePlan) => routePlan.route === 'browser-export')
        ?.artifactCompletion.profiles.find((profile) => profile.profile === 'video'),
    ).toMatchObject({
      status: 'complete',
      artifacts: [expect.objectContaining({ id: 'artifact.video.blocked' })],
    });
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
    expect(degraded.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-degraded',
        message: 'Dataset process is running with a fallback encoder.',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        detail: expect.objectContaining({
          healthCheck: 'encoder',
          processState: 'degraded',
        }),
      }),
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.route.process-degraded',
        severity: 'warning',
        route: 'sidecar-export',
        reason: 'process-degraded',
        message: 'Dataset process is running with a fallback encoder.',
        processId: 'dataset-process',
        operationId: 'exportDataset',
      }),
    ]));
  });

  it('emits route-scoped start-process dependency actions only for stopped trusted-local processes', () => {
    const stopped = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor()],
      processStatuses: [{ processId: 'dataset-process', state: 'stopped', message: 'Dataset process is stopped.' }],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(stopped.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        detail: expect.objectContaining({
          routeScope: 'sidecar-export',
          lifecycleState: 'stopped',
          processProtocol: 'stdio-jsonrpc',
          nextAction: expect.objectContaining({
            kind: 'start-process',
            route: 'sidecar-export',
            processId: 'dataset-process',
            operationId: 'exportDataset',
            detail: expect.objectContaining({
              specificKind: 'start-process',
            }),
          }),
        }),
      }),
    ]));
    expect(stopped.nextActions).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'start-process',
        route: 'sidecar-export',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        detail: expect.objectContaining({
          specificKind: 'start-process',
        }),
      }),
    ]));
    expect(stopped.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')?.nextActions)
      .toEqual(expect.arrayContaining([
        expect.objectContaining({
          kind: 'start-process',
          route: 'sidecar-export',
          processId: 'dataset-process',
          operationId: 'exportDataset',
        }),
      ]));
    expect(stopped.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      nextActions: [],
    });

    const nonStoppedStates: readonly ProcessStatus[] = [
      { processId: 'dataset-process', state: 'not-installed' },
      { processId: 'dataset-process', state: 'starting' },
      { processId: 'dataset-process', state: 'ready' },
      { processId: 'dataset-process', state: 'busy', operationId: 'exportDataset' },
      { processId: 'dataset-process', state: 'degraded' },
      { processId: 'dataset-process', state: 'failed' },
      { processId: 'dataset-process', state: 'stopping' },
    ];

    for (const status of nonStoppedStates) {
      const result = planRender({
        outputFormats: [renderDependentOutput()],
        processes: [processDescriptor()],
        processStatuses: [status],
        request: { outputFormatId: 'dataset.zip' },
      });

      expect(result.nextActions.some((action) => action.kind === 'start-process')).toBe(false);
      expect(result.findings.some((finding) => finding.detail?.nextAction && finding.route === 'sidecar-export')).toBe(false);
    }

    const untrustedProtocol = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor({ protocol: 'mock-rpc' })],
      processStatuses: [{ processId: 'dataset-process', state: 'stopped' }],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(untrustedProtocol.nextActions.some((action) => action.kind === 'start-process')).toBe(false);
  });

  it('maps missing, not-installed, stopped, busy, and failed process states to route-scoped blockers', () => {
    const scenarios: Array<{
      name: string;
      processes: readonly VideoEditorProcessDescriptor[];
      processStatuses?: readonly ProcessStatus[];
      expectedReason: string;
    }> = [
      {
        name: 'missing',
        processes: [],
        expectedReason: 'missing-contribution',
      },
      {
        name: 'not-installed',
        processes: [processDescriptor()],
        processStatuses: [{ processId: 'dataset-process', state: 'not-installed', installHint: 'Install the dataset bridge.' }],
        expectedReason: 'process-not-installed',
      },
      {
        name: 'stopped',
        processes: [processDescriptor()],
        processStatuses: [{ processId: 'dataset-process', state: 'stopped' }],
        expectedReason: 'process-dependent',
      },
      {
        name: 'busy',
        processes: [processDescriptor()],
        processStatuses: [{ processId: 'dataset-process', state: 'busy', operationId: 'exportDataset' }],
        expectedReason: 'process-dependent',
      },
      {
        name: 'failed',
        processes: [processDescriptor()],
        processStatuses: [{ processId: 'dataset-process', state: 'failed', errorCode: 'PROC_EXIT' }],
        expectedReason: 'process-failed',
      },
    ];

    for (const scenario of scenarios) {
      const result = planRender({
        outputFormats: [
          renderDependentOutput({
            availableRoutes: ['browser-export', 'sidecar-export'],
            routeRequirementRoutes: ['sidecar-export'],
          }),
        ],
        processes: scenario.processes,
        processStatuses: scenario.processStatuses,
        request: { outputFormatId: 'dataset.zip' },
      });

      expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
        blocked: false,
        blockerCount: 0,
      });
      expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
        blocked: true,
        blockerCount: 2,
      });
      expect(result.findings).toEqual(expect.arrayContaining([
        expect.objectContaining({
          route: 'sidecar-export',
          reason: scenario.expectedReason,
          processId: 'dataset-process',
          operationId: 'exportDataset',
        }),
      ]));
    }
  });

  it('collects stopped trusted-local processes as route-scoped repair findings without blocking unrelated routes', () => {
    const result = planRender({
      processes: [processDescriptor({ routes: ['sidecar-export'] })],
      processStatuses: [{ processId: 'dataset-process', state: 'stopped', message: 'Dataset process is stopped.' }],
    });

    expect(result.blockers).toEqual([]);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.process.ext.dataset.process-contribution.sidecar-export.exportDataset.stopped',
        severity: 'info',
        route: 'sidecar-export',
        reason: 'process-dependent',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        detail: expect.objectContaining({
          routeScope: 'sidecar-export',
          lifecycleState: 'stopped',
          processProtocol: 'stdio-jsonrpc',
          nextAction: expect.objectContaining({
            kind: 'start-process',
            route: 'sidecar-export',
            processId: 'dataset-process',
            operationId: 'exportDataset',
            detail: expect.objectContaining({
              specificKind: 'start-process',
            }),
          }),
        }),
      }),
    ]));
    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      nextActions: [],
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
      nextActions: [
        expect.objectContaining({
          kind: 'start-process',
          route: 'sidecar-export',
          processId: 'dataset-process',
          operationId: 'exportDataset',
        }),
      ],
    });
  });

  it('blocks degraded process routes only when the declared operation explicitly requires non-degraded health', () => {
    const degradedStatus: ProcessStatus = {
      processId: 'dataset-process',
      state: 'degraded',
      message: 'Dataset process is running with a fallback encoder.',
      healthCheck: 'encoder',
    };

    const result = planRender({
      outputFormats: [renderDependentOutput()],
      processes: [processDescriptor({ requiredCapabilities: ['process-health:non-degraded'] })],
      processStatuses: [degradedStatus],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: true,
      blockerCount: 2,
    });
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'sidecar-export',
        reason: 'process-degraded',
        processId: 'dataset-process',
        operationId: 'exportDataset',
        detail: expect.objectContaining({
          requireNonDegradedHealth: true,
          healthCheck: 'encoder',
          processState: 'degraded',
        }),
      }),
    ]));
  });

  it('emits process-configuration-error only on routes declared by the output, not unrelated routes', () => {
    const result = planRender({
      outputFormats: [
        renderDependentOutput({
          availableRoutes: ['browser-export', 'sidecar-export'],
          routeRequirementRoutes: ['sidecar-export'],
        }),
      ],
      processes: [processDescriptor({ routes: ['browser-export'] })],
      processStatuses: [{ processId: 'dataset-process', state: 'ready' }],
      request: { outputFormatId: 'dataset.zip' },
    });

    expect(result.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: false,
      blockerCount: 0,
    });
    expect(result.routePlans.find((routePlan) => routePlan.route === 'sidecar-export')).toMatchObject({
      blocked: true,
      blockerCount: 1,
    });
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'sidecar-export',
        reason: 'process-configuration-error',
        processId: 'dataset-process',
        operationId: 'exportDataset',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'process-configuration-error',
      }),
    ]));
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
