import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  RenderMaterialRef,
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import {
  RENDER_MATERIAL_STATUSES,
  TIMELINE_PATCH_ALL_OP_FAMILIES,
} from '@reigh/editor-sdk';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorProcessDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { CompositionGraphInput } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import * as graphProjector from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import { applyGraphPreviewOperations } from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import { assertFinalArtifactHasManifest } from '@/tools/video-editor/runtime/renderability.ts';
import {
  projectProcessResultContracts,
  createProcessResultAttachRecord,
  PROCESS_RESULT_ATTACH_ALIAS_KIND,
  PROCESS_RESULT_ATTACH_KIND,
  ProcessResultAttachError,
  assertNoTimelinePlacementMutation,
} from './processResultAttach';

function processDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'process.ext.dataset',
    extensionId: 'ext.process',
    processId: 'dataset-process',
    label: 'Dataset Process',
    description: 'Produces sidecar datasets.',
    spec: {
      id: 'dataset-process',
      label: 'Dataset Process',
      description: 'Produces sidecar datasets.',
      spawn: { command: 'dataset-process' },
      protocol: 'stdio-jsonrpc',
      version: { semver: '1.2.3', declaredBy: 'ext.process', contributionId: 'process.ext.dataset' },
      operations: [
        {
          id: 'exportDataset',
          label: 'Export Dataset',
          routes: ['sidecar-export'],
          outputKinds: ['material', 'artifact', 'sidecar'],
          requiredCapabilities: ['sidecar-export'],
          determinism: 'process-dependent',
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      {
        id: 'exportDataset',
        label: 'Export Dataset',
        routes: ['sidecar-export'],
        outputKinds: ['material', 'artifact', 'sidecar'],
        requiredCapabilities: ['sidecar-export'],
        determinism: 'process-dependent',
      },
    ],
    availableRoutes: ['sidecar-export'],
    requiredBy: [{ source: 'extension', extensionId: 'ext.process', contributionId: 'process.ext.dataset' }],
    blockers: [],
    nextActions: [],
  };
}

function material(overrides: Partial<RenderMaterial> = {}): RenderMaterial {
  return {
    id: 'material.dataset',
    mediaKind: 'json',
    locator: { kind: 'artifact-store', uri: 'artifact://materials/dataset.json', mimeType: 'application/json' },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    provenance: { origin: 'process' },
    ...overrides,
  };
}

function artifact(overrides: Partial<RenderArtifact> = {}): RenderArtifact {
  return {
    id: 'artifact.dataset',
    route: 'sidecar-export',
    locator: { kind: 'artifact-store', uri: 'artifact://exports/dataset.csv', mimeType: 'text/csv' },
    mediaKind: 'text',
    determinism: 'process-dependent',
    boundary: {
      source: 'sidecar-process',
      target: 'artifact-store',
      route: 'sidecar-export',
      failureBehavior: 'emit-diagnostic',
    },
    consumedMaterialRefs: [material()],
    ...overrides,
  };
}

function sidecar(overrides: Partial<RenderArtifactSidecarDescriptor> = {}): RenderArtifactSidecarDescriptor {
  return {
    id: 'sidecar.log',
    filename: 'dataset.log',
    mimeType: 'text/plain',
    kind: 'log',
    locator: { kind: 'artifact-store', uri: 'artifact://sidecars/dataset.log', mimeType: 'text/plain' },
    provenance: { source: 'dataset-process' },
    ...overrides,
  };
}

function result(overrides: Partial<ProcessRoundtripResult> = {}): ProcessRoundtripResult {
  return {
    requestId: 'task-7',
    processId: 'dataset-process',
    operationId: 'exportDataset',
    status: 'completed',
    returnedMaterials: [material()],
    artifacts: [artifact()],
    sidecars: [sidecar()],
    diagnostics: [{
      id: 'diag.dataset.warn',
      severity: 'warning',
      route: 'sidecar-export',
      message: 'Dataset export omitted optional captions.',
    }],
    logs: [{
      level: 'info',
      message: 'Export complete.',
      at: '2026-07-04T20:00:00.000Z',
    }],
    progress: {
      operationId: 'exportDataset',
      percent: 100,
      message: 'Done',
    },
    availableActions: ['download-sidecar', 'create-proposal'],
    metadata: { batchId: 'b-10' },
    ...overrides,
  };
}

function pendingMaterialRef(overrides: Partial<RenderMaterialRef> = {}): RenderMaterialRef {
  return {
    id: 'material.pending',
    mediaKind: 'json',
    locator: { kind: 'artifact-store', uri: 'artifact://materials/pending.json', mimeType: 'application/json' },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    ...overrides,
  };
}

type HostClipSummary = TimelineSnapshot['clips'][number];

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe('processResultAttach', () => {
  it('creates a canonical host-internal attach record from a process roundtrip result', () => {
    const record = createProcessResultAttachRecord({
      kind: PROCESS_RESULT_ATTACH_KIND,
      processDescriptor: processDescriptor(),
      result: result(),
      attachedAt: '2026-07-04T20:30:00.000Z',
      upstreamProvenance: { transport: 'stdio-jsonrpc' },
    });

    expect(record).toMatchObject({
      kind: PROCESS_RESULT_ATTACH_KIND,
      processRef: 'process.ext.dataset',
      processId: 'dataset-process',
      operationId: 'exportDataset',
      taskId: 'task-7',
      status: 'completed',
      returnedMaterialRefs: ['material.dataset'],
      artifactRefs: ['artifact.dataset'],
      availableActions: ['download-sidecar', 'create-proposal'],
      metadata: { batchId: 'b-10' },
      provenance: {
        attachedAt: '2026-07-04T20:30:00.000Z',
        attachedBy: 'host-runtime',
        inputKind: PROCESS_RESULT_ATTACH_KIND,
        descriptor: {
          descriptorId: 'process.ext.dataset',
          extensionId: 'ext.process',
          processId: 'dataset-process',
          protocol: 'stdio-jsonrpc',
        },
        operation: {
          id: 'exportDataset',
          label: 'Export Dataset',
          routes: ['sidecar-export'],
          outputKinds: ['material', 'artifact', 'sidecar'],
          requiredCapabilities: ['sidecar-export'],
          determinism: 'process-dependent',
        },
        result: {
          requestId: 'task-7',
          taskId: 'task-7',
          processId: 'dataset-process',
          operationId: 'exportDataset',
          status: 'completed',
        },
        upstream: { transport: 'stdio-jsonrpc' },
      },
    });
    expect(record.returnedMaterials[0]).not.toBe(result().returnedMaterials[0]);
    expect(TIMELINE_PATCH_ALL_OP_FAMILIES).not.toContain(PROCESS_RESULT_ATTACH_KIND);
    expect(TIMELINE_PATCH_ALL_OP_FAMILIES).not.toContain(PROCESS_RESULT_ATTACH_ALIAS_KIND);
  });

  it('accepts the compatibility alias while canonicalizing the record kind', () => {
    const record = createProcessResultAttachRecord({
      kind: PROCESS_RESULT_ATTACH_ALIAS_KIND,
      processDescriptor: processDescriptor(),
      result: result(),
    });

    expect(record.kind).toBe(PROCESS_RESULT_ATTACH_KIND);
    expect(record.provenance.inputKind).toBe(PROCESS_RESULT_ATTACH_ALIAS_KIND);
  });

  it('projects attached results through existing material and artifact contracts', () => {
    const record = createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      result: result(),
      attachedAt: '2026-07-04T20:30:00.000Z',
    });

    const projection = projectProcessResultContracts(record);

    expect(projection.materialStatuses).toEqual([
      expect.objectContaining({
        materialRefId: 'material.dataset',
        state: 'resolved',
        updatedAt: '2026-07-04T20:30:00.000Z',
      }),
    ]);
    expect(projection.materialStatuses.every((status) =>
      RENDER_MATERIAL_STATUSES.includes(status.state))).toBe(true);
    expect(projection.materialRefs[0]).toMatchObject({
      id: 'material.dataset',
      producerExtensionId: 'ext.process',
      producerVersion: '1.2.3',
      provenance: {
        origin: 'process',
        process: expect.objectContaining({
          processRef: 'process.ext.dataset',
          processId: 'dataset-process',
          operationId: 'exportDataset',
          taskId: 'task-7',
          status: 'completed',
        }),
      },
    });

    const projectedArtifact = projection.artifacts[0]!;
    assertFinalArtifactHasManifest(projectedArtifact, 'process.result.attach');
    expect(projectedArtifact.manifest).toMatchObject({
      profile: 'sidecar',
      processId: 'dataset-process',
      operationId: 'exportDataset',
      route: 'sidecar-export',
      artifactId: 'artifact.dataset',
    });
    expect(projectedArtifact.sidecars).toEqual([
      expect.objectContaining({
        id: 'sidecar.log',
        kind: 'log',
      }),
    ]);
    expect(projectedArtifact.consumedMaterialRefs[0]).toEqual(projection.materialRefs[0]);
  });

  it('maps failed process-owned pending materials onto the existing failed material status', () => {
    const record = createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      result: result({
        status: 'failed',
        returnedMaterials: [],
        artifacts: [],
        sidecars: [],
      }),
      attachedAt: '2026-07-04T20:35:00.000Z',
    });

    const projection = projectProcessResultContracts(record, {
      failedMaterialRefs: [pendingMaterialRef()],
    });
    const runtime = projectHostMaterialRuntime({
      materialRefs: projection.materialRefs,
      materialStatuses: projection.materialStatuses,
    });

    expect(projection.materialStatuses).toEqual([
      expect.objectContaining({
        materialRefId: 'material.pending',
        state: 'failed',
      }),
    ]);
    expect(projection.materialStatuses.every((status) =>
      RENDER_MATERIAL_STATUSES.includes(status.state))).toBe(true);
    expect(runtime.byMaterialRefId.get('material.pending')?.status.state).toBe('failed');
  });

  it('lets timeline-facing material.attach consume only attached material refs', () => {
    const record = createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      result: result(),
    });
    const projection = projectProcessResultContracts(record);
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
        materialRefs: projection.materialRefs,
        materialStatuses: projection.materialStatuses,
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
        materialRefId: projection.materialRefs[0]!.id,
      },
    ]);

    const clonedClip = projectedClip(projectorSpy);

    expect(preview?.diagnostics ?? []).toEqual([]);
    expect(clonedClip.transition?.params?.materialSlots).toEqual({
      'transition-mask': 'material.dataset',
    });
    expect(sourceClip.transition?.params?.materialSlots).toBeUndefined();
  });

  it('rejects process descriptors whose declared operation does not match the result operationId', () => {
    expect(() => createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      result: result({ operationId: 'renderPreview' }),
    })).toThrow(ProcessResultAttachError);

    try {
      createProcessResultAttachRecord({
        processDescriptor: processDescriptor(),
        result: result({ operationId: 'renderPreview' }),
      });
    } catch (error) {
      expect((error as ProcessResultAttachError).code).toBe('descriptor-operation-missing');
    }
  });

  it('rejects mismatched task IDs and process refs', () => {
    expect(() => createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      processRef: 'process.ext.other',
      result: result(),
    })).toThrow(ProcessResultAttachError);

    expect(() => createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      taskId: 'task-8',
      result: result(),
    })).toThrow(ProcessResultAttachError);
  });

  it('rejects direct timeline placement mutation fields', () => {
    expect(() => assertNoTimelinePlacementMutation({
      processRef: 'process.ext.dataset',
      processId: 'dataset-process',
      operationId: 'exportDataset',
      taskId: 'task-7',
      timelinePlacement: {
        targetClipId: 'clip-1',
      },
    })).toThrow(ProcessResultAttachError);

    expect(() => createProcessResultAttachRecord({
      processDescriptor: processDescriptor(),
      result: result(),
      timelinePatch: {
        operations: [{ op: 'clip.add', target: 'clip-1' }],
      },
    } as unknown as Parameters<typeof createProcessResultAttachRecord>[0])).toThrow(ProcessResultAttachError);
  });
});
