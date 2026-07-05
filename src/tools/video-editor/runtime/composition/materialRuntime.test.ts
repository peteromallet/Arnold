import { describe, expect, it } from 'vitest';
import {
  createProcessResultAttachRecord,
  projectProcessResultContracts,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import {
  getMaterialRuntimeMatrixRow,
  MATERIAL_RUNTIME_DIAGNOSTIC_CODE,
  MATERIAL_RUNTIME_LEGACY_MIGRATIONS,
  MATERIAL_RUNTIME_PLANNER_MATRIX,
  MATERIAL_RUNTIME_PLANNER_MATRIX_BY_KEY,
  materialRuntimeMatrixKey,
  projectHostMaterialRuntime,
  resolveMaterialAttachEntry,
} from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import type {
  ExtensionDiagnostic,
  ProcessRoundtripResult,
  ProcessStatus,
  RenderMaterial,
  RenderMaterialRef,
  RenderMaterialStatus,
} from '@reigh/editor-sdk';
import type {
  ContributionIndex,
  VideoEditorProcessDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

function makeMaterialRef(
  id: string,
  overrides: Partial<RenderMaterialRef> = {},
): RenderMaterialRef {
  return {
    id,
    mediaKind: 'image',
    locator: {
      kind: 'asset-registry',
      uri: `asset://${id}`,
    },
    determinism: 'live-unbaked',
    replacementPolicy: 'materialize-on-export',
    ...overrides,
  };
}

function makeProcessStatus(overrides: Partial<ProcessStatus> & Pick<ProcessStatus, 'processId' | 'state'>): ProcessStatus {
  return {
    message: `Process ${overrides.processId} is ${overrides.state}.`,
    ...overrides,
  } as ProcessStatus;
}

function makeContributionIndex(): ContributionIndex {
  const diagnostic: ExtensionDiagnostic = {
    severity: 'warning',
    code: 'test/contribution-diagnostic',
    message: 'Contribution diagnostic',
  };

  return Object.freeze({
    'shader:ext.shader:shader.contrib': Object.freeze([
      Object.freeze({
        scopedKey: 'shader:ext.shader:shader.contrib',
        kind: 'shader',
        extensionId: 'ext.shader',
        contributionId: 'shader.contrib',
        status: 'active' as const,
        packageState: 'loaded' as const,
        diagnostics: Object.freeze([diagnostic]),
        duplicateOrdinal: 0,
        projectionEligible: true,
        projection: Object.freeze({
          duplicateOrdinal: 0,
          eligible: true,
          projected: true,
          source: 'descriptor-array' as const,
        }),
        routeFit: Object.freeze({
          route: 'worker-export' as const,
          fit: 'supported' as const,
        }),
      }),
    ]),
  });
}

function makeShaderDescriptor(): VideoEditorShaderDescriptor {
  return Object.freeze({
    id: 'shader.contrib',
    extensionId: 'ext.shader',
    shaderId: 'shader.main',
    label: 'Shader Main',
    pass: 'clip',
    hasSourceMetadata: true,
    materializer: Object.freeze({
      routes: Object.freeze(['worker-export'] as const),
      processId: 'shader-proc',
      operationId: 'bake-material',
    }),
  });
}

function makeProcessDescriptor(): VideoEditorProcessDescriptor {
  return Object.freeze({
    id: 'proc.descriptor',
    extensionId: 'ext.shader',
    processId: 'shader-proc',
    label: 'Shader Process',
    spec: {
      id: 'shader-proc',
      label: 'Shader Process',
      protocol: 'stdio-jsonrpc',
      spawn: {
        command: 'shader-proc',
      },
      operations: [
        {
          id: 'bake-material',
          label: 'Bake Material',
          outputKinds: ['material'],
          routes: ['worker-export'],
        },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: Object.freeze([
      Object.freeze({
        id: 'bake-material',
        label: 'Bake Material',
        outputKinds: Object.freeze(['material'] as const),
        routes: Object.freeze(['worker-export'] as const),
      }),
    ]),
    availableRoutes: Object.freeze(['worker-export'] as const),
    requiredBy: Object.freeze([]),
    blockers: Object.freeze([]),
    nextActions: Object.freeze([]),
  }) as VideoEditorProcessDescriptor;
}

function makeReturnedMaterial(
  id: string,
  overrides: Partial<RenderMaterial> = {},
): RenderMaterial {
  return {
    id,
    mediaKind: 'image',
    locator: {
      kind: 'artifact-store',
      uri: `artifact://${id}`,
    },
    determinism: 'process-dependent',
    replacementPolicy: 'materialize-on-export',
    provenance: {
      origin: 'process',
    },
    ...overrides,
  };
}

function makeProcessResult(
  overrides: Partial<ProcessRoundtripResult> = {},
): ProcessRoundtripResult {
  return {
    requestId: 'request-1',
    processId: 'shader-proc',
    operationId: 'bake-material',
    status: 'completed',
    returnedMaterials: [makeReturnedMaterial('mat-attached')],
    artifacts: [],
    sidecars: [],
    diagnostics: [],
    logs: [],
    availableActions: [],
    ...overrides,
  };
}

describe('materialRuntime matrix', () => {
  it('materializes the full status x phase x quality cross-product once', () => {
    expect(MATERIAL_RUNTIME_PLANNER_MATRIX).toHaveLength(60);
    expect(MATERIAL_RUNTIME_PLANNER_MATRIX_BY_KEY.size).toBe(60);
    expect(MATERIAL_RUNTIME_PLANNER_MATRIX.every((row) => Object.isFrozen(row))).toBe(true);
  });

  it('keeps pending queued and pending active distinct without generic missing semantics', () => {
    expect(getMaterialRuntimeMatrixRow('pending')).toMatchObject({
      validity: 'valid',
      normalizedDetail: { phase: 'queued' },
      determinismPosture: 'materialization-pending',
      nextActionKind: 'materialize',
      blocker: {
        kind: 'determinism-derived',
        fallbackReason: 'unknown',
      },
    });

    expect(getMaterialRuntimeMatrixRow('pending', { phase: 'active' })).toMatchObject({
      validity: 'valid',
      normalizedDetail: { phase: 'active' },
      determinismPosture: 'materialization-active',
      nextActionKind: 'bake',
      blocker: {
        kind: 'determinism-derived',
        fallbackReason: 'unknown',
      },
    });
  });

  it('treats live-only as missing plus phase rather than a generic absent package', () => {
    expect(getMaterialRuntimeMatrixRow('missing', { phase: 'live-only' })).toMatchObject({
      validity: 'valid',
      blocker: {
        kind: 'fixed',
        reason: 'live-unbaked',
      },
      routeFit: {
        preview: 'supported',
        authoritative: 'blocked',
      },
      diagnosticCodes: [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.LIVE_ONLY],
      nextActionKind: 'materialize',
    });
  });

  it('keeps stale and failed defaults distinct for blocker and repair semantics', () => {
    expect(getMaterialRuntimeMatrixRow('stale')).toMatchObject({
      validity: 'valid',
      blocker: {
        kind: 'fixed',
        reason: 'materialization-failed',
      },
      diagnosticCodes: [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE],
      nextActionKind: 'materialize',
    });

    expect(getMaterialRuntimeMatrixRow('failed')).toMatchObject({
      validity: 'valid',
      blocker: {
        kind: 'fixed',
        reason: 'materialization-error',
      },
      diagnosticCodes: [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED],
      nextActionKind: 'open-settings',
    });
  });

  it('marks durable-candidate-only qualities and phase mismatches as explicit invalid rows', () => {
    expect(getMaterialRuntimeMatrixRow('missing', { quality: 'weaker-provenance' })).toMatchObject({
      validity: 'invalid',
      diagnosticCodes: [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STATUS_INVALID],
      nextActionKind: 'open-settings',
    });

    expect(getMaterialRuntimeMatrixRow('resolved', { phase: 'queued' })).toMatchObject({
      validity: 'invalid',
      diagnosticCodes: [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STATUS_INVALID],
      nextActionKind: 'open-settings',
    });
  });

  it('maps route-incompatible rows to route-selection posture instead of hardcoded browser export', () => {
    expect(getMaterialRuntimeMatrixRow('resolved', { quality: 'route-incompatible' })).toMatchObject({
      validity: 'valid',
      blocker: {
        kind: 'fixed',
        reason: 'route-unsupported',
      },
      routeFit: {
        sensitivity: 'route-selection-required',
      },
      nextActionKind: 'select-route',
    });
  });

  it('exposes explicit legacy migrations for retired material aliases', () => {
    expect(MATERIAL_RUNTIME_LEGACY_MIGRATIONS.unbaked).toEqual({
      state: 'pending',
      detail: { phase: 'queued' },
      semantics: ['legacy-unbaked'],
    });
    expect(MATERIAL_RUNTIME_LEGACY_MIGRATIONS.baking).toEqual({
      state: 'pending',
      detail: { phase: 'active' },
      semantics: ['legacy-baking'],
    });
    expect(MATERIAL_RUNTIME_LEGACY_MIGRATIONS.degraded).toEqual({
      state: 'stale',
      semantics: ['legacy-degraded'],
    });
    expect(MATERIAL_RUNTIME_LEGACY_MIGRATIONS['live-runtime-only']).toEqual({
      state: 'missing',
      detail: { phase: 'live-only' },
      semantics: ['legacy-live-runtime-only'],
    });
  });

  it('uses stable keys for direct row lookup', () => {
    const key = materialRuntimeMatrixKey('failed', { quality: 'route-incompatible' });
    expect(key).toBe('failed|-|route-incompatible');
    expect(MATERIAL_RUNTIME_PLANNER_MATRIX_BY_KEY.get(key)).toBe(
      getMaterialRuntimeMatrixRow('failed', { quality: 'route-incompatible' }),
    );
  });
});

describe('projectHostMaterialRuntime', () => {
  it('returns a deterministic frozen projection keyed by material ref id', () => {
    const statuses: readonly RenderMaterialStatus[] = [
      {
        materialRefId: 'mat-b',
        state: 'failed',
      },
    ];

    const result = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-b'),
        makeMaterialRef('mat-a', { determinism: 'deterministic' }),
      ],
      materialStatuses: statuses,
      requestedRoutes: ['worker-export', 'preview', 'worker-export'],
      canonicalRoutes: ['browser-export', 'preview'],
    });

    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.materials)).toBe(true);
    expect(result.materialRefIds).toEqual(['mat-a', 'mat-b']);
    expect([...result.byMaterialRefId.keys()]).toEqual(['mat-a', 'mat-b']);
    expect(result.requestedRoutes).toEqual(['preview', 'worker-export']);
    expect(result.canonicalRoutes).toEqual(['preview', 'browser-export']);
    expect(result.routeEvidence).toEqual(['preview', 'browser-export', 'worker-export']);
    expect(result.authoritativeBlockedMaterialRefIds).toEqual(['mat-b']);
    expect(result.hasAuthoritativeBlockers).toBe(true);

    const resolved = result.byMaterialRefId.get('mat-a');
    expect(resolved).toMatchObject({
      status: {
        state: 'resolved',
      },
      determinismPosture: 'resolved',
      provenancePosture: 'unattributed',
      predicates: {
        activeBake: false,
        liveOnly: false,
      },
    });
    expect(Object.isFrozen(resolved!)).toBe(true);

    const failed = result.byMaterialRefId.get('mat-b');
    expect(failed).toMatchObject({
      blocksAuthoritativeExport: true,
      blocker: {
        reason: 'materialization-error',
      },
      nextAction: {
        kind: 'open-settings',
      },
    });
    expect(failed?.diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
      'composition/material-failed',
      'composition/material-missing-provenance',
    ]);
    expect(failed?.routeScopes).toEqual([
      {
        route: 'preview',
        fit: 'blocked',
        sensitivity: 'route-agnostic',
        blocker: {
          reason: 'materialization-error',
          severity: 'error',
          route: 'preview',
        },
        nextAction: {
          kind: 'open-settings',
          route: 'preview',
        },
      },
      {
        route: 'browser-export',
        fit: 'blocked',
        sensitivity: 'route-agnostic',
        blocker: {
          reason: 'materialization-error',
          severity: 'error',
          route: 'browser-export',
        },
        nextAction: {
          kind: 'open-settings',
          route: 'browser-export',
        },
      },
      {
        route: 'worker-export',
        fit: 'blocked',
        sensitivity: 'route-agnostic',
        blocker: {
          reason: 'materialization-error',
          severity: 'error',
          route: 'worker-export',
        },
        nextAction: {
          kind: 'open-settings',
          route: 'worker-export',
        },
      },
    ]);
    const diagnosticCodes = result.diagnostics.map((diagnostic) => diagnostic.code);
    expect(diagnosticCodes).toContain('composition/material-failed');
    expect(diagnosticCodes.filter((c) => c === 'composition/material-missing-provenance')).toHaveLength(2);
  });

  it('does not assign generic material refs to browser-export without route evidence', () => {
    const result = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-live'),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-live',
          state: 'missing',
          detail: {
            phase: 'live-only',
          },
        },
      ],
    });

    expect(result.requestedRoutes).toEqual([]);
    expect(result.canonicalRoutes).toEqual([]);
    expect(result.routeEvidence).toEqual([]);

    const material = result.byMaterialRefId.get('mat-live');
    expect(material).toMatchObject({
      nextAction: {
        kind: 'materialize',
      },
      blocker: {
        reason: 'live-unbaked',
        severity: 'error',
      },
      routeScopes: [],
    });
    expect(material?.nextAction?.route).toBeUndefined();
    expect(material?.blocker?.route).toBeUndefined();
  });

  it('keeps pending predicates and route-incompatible matrix actions aligned with normalized detail', () => {
    const result = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-route', { determinism: 'deterministic' }),
        makeMaterialRef('mat-pending'),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-route',
          state: 'resolved',
          detail: {
            quality: 'route-incompatible',
          },
        },
        {
          materialRefId: 'mat-pending',
          state: 'pending',
          detail: {
            phase: 'active',
          },
        },
      ],
      requestedRoutes: ['preview'],
      canonicalRoutes: ['worker-export'],
    });

    expect(result.byMaterialRefId.get('mat-route')).toMatchObject({
      blocksAuthoritativeExport: true,
      predicates: {
        routeIncompatible: true,
      },
      blocker: {
        reason: 'route-unsupported',
      },
      nextAction: {
        kind: 'select-route',
      },
      routeScopes: [
        {
          route: 'preview',
          fit: 'supported',
        },
        {
          route: 'worker-export',
          fit: 'blocked',
          blocker: {
            reason: 'route-unsupported',
            route: 'worker-export',
          },
          nextAction: {
            kind: 'select-route',
            route: 'worker-export',
          },
        },
      ],
    });
    expect(result.byMaterialRefId.get('mat-route')?.routeScopes[0]?.blocker).toBeUndefined();
    expect(result.byMaterialRefId.get('mat-route')?.routeScopes[0]?.nextAction).toBeUndefined();

    expect(result.byMaterialRefId.get('mat-pending')).toMatchObject({
      status: {
        state: 'pending',
        detail: {
          phase: 'active',
        },
      },
      predicates: {
        activeBake: true,
      },
      blocker: {
        reason: 'live-unbaked',
      },
      nextAction: {
        kind: 'bake',
      },
    });
  });

  it('surfaces descriptor facts, declarative process status, and entry diagnostics without process execution behavior', () => {
    const result = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-descriptor', {
          producerExtensionId: 'ext.shader',
          producerVersion: '1.2.3',
          provenance: {
            contributionId: 'shader.contrib',
            shaderId: 'shader.main',
          },
        }),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-descriptor',
          state: 'pending',
          detail: {
            phase: 'active',
          },
        },
      ],
      contributionIndex: makeContributionIndex(),
      shaders: [makeShaderDescriptor()],
      processes: [makeProcessDescriptor()],
      processStatuses: [makeProcessStatus({ processId: 'shader-proc', state: 'busy' })],
      requestedRoutes: ['preview'],
      canonicalRoutes: ['worker-export'],
    });

    const material = result.byMaterialRefId.get('mat-descriptor');
    expect(material).toMatchObject({
      determinism: 'live-unbaked',
      determinismPosture: 'materialization-active',
      provenancePosture: 'recorded',
      blocksAuthoritativeExport: true,
      descriptorFacts: {
        contribution: {
          scopedKey: 'shader:ext.shader:shader.contrib',
          status: 'active',
        },
        shader: {
          extensionId: 'ext.shader',
          contributionId: 'shader.contrib',
          shaderId: 'shader.main',
          processId: 'shader-proc',
        },
        process: {
          processId: 'shader-proc',
          operationId: 'bake-material',
          state: 'busy',
          declarative: true,
          supportsMaterialOutput: true,
        },
      },
      routeScopes: [
        {
          route: 'preview',
          fit: 'supported',
        },
        {
          route: 'worker-export',
          fit: 'blocked',
          blocker: {
            reason: 'live-unbaked',
          },
          nextAction: {
            kind: 'bake',
            route: 'worker-export',
          },
        },
      ],
      diagnostics: [],
    });
    expect(result.diagnostics).toEqual([]);
  });

  it('enriches attached materials with process attach provenance when the record matches material and operation ids', () => {
    const process = makeProcessDescriptor();
    const attachRecord = createProcessResultAttachRecord({
      processDescriptor: process,
      attachedAt: '2026-07-04T22:10:00.000Z',
      result: makeProcessResult(),
    });
    const projection = projectProcessResultContracts(attachRecord);

    const result = projectHostMaterialRuntime({
      materialRefs: projection.materialRefs,
      materialStatuses: projection.materialStatuses,
      processes: [process],
      processStatuses: [makeProcessStatus({ processId: 'shader-proc', state: 'ready' })],
      processResultAttachRecords: [attachRecord],
      canonicalRoutes: ['worker-export'],
    });

    expect(result.byMaterialRefId.get('mat-attached')).toMatchObject({
      descriptorFacts: {
        process: {
          processId: 'shader-proc',
          operationId: 'bake-material',
          state: 'ready',
          supportsMaterialOutput: true,
          declarative: true,
          availableRoutes: ['worker-export'],
          attachProvenance: {
            kind: 'process.result.attach',
            inputKind: 'process.result.attach',
            materialRefId: 'mat-attached',
            processRef: 'proc.descriptor',
            descriptorId: 'proc.descriptor',
            extensionId: 'ext.shader',
            processId: 'shader-proc',
            operationId: 'bake-material',
            operationLabel: 'Bake Material',
            taskId: 'request-1',
            status: 'completed',
            attachedAt: '2026-07-04T22:10:00.000Z',
            attachedBy: 'host-runtime',
          },
        },
      },
    });
  });

  it('emits invalid-row diagnostics and marks authoritative export as blocked', () => {
    const result = projectHostMaterialRuntime({
      materialRefs: [makeMaterialRef('mat-invalid', { determinism: 'deterministic' })],
      materialStatuses: [
        {
          materialRefId: 'mat-invalid',
          state: 'resolved',
          detail: {
            phase: 'queued',
          },
        },
      ],
      canonicalRoutes: ['worker-export'],
    });

    expect(result.authoritativeBlockedMaterialRefIds).toEqual(['mat-invalid']);
    expect(result.hasAuthoritativeBlockers).toBe(true);
    expect(result.byMaterialRefId.get('mat-invalid')).toMatchObject({
      blocksAuthoritativeExport: true,
      matrix: {
        validity: 'invalid',
      },
      blocker: {
        reason: 'unknown',
      },
      nextAction: {
        kind: 'open-settings',
      },
      diagnostics: [
        {
          code: 'composition/material-status-invalid',
          detail: {
            materialRefId: 'mat-invalid',
            materialStatus: 'resolved',
            detailPhase: 'queued',
            nextAction: {
              kind: 'open-settings',
            },
          },
        },
        {
          code: 'composition/material-missing-provenance',
          detail: {
            materialRefId: 'mat-invalid',
            materialStatus: 'resolved',
            detailPhase: 'queued',
            provenanceGap:
              'No provenance record or producer metadata; material origin cannot be verified.',
            nextAction: {
              kind: 'open-settings',
            },
          },
        },
      ],
    });
  });
});

describe('resolveMaterialAttachEntry', () => {
  const transitionMaskContext = Object.freeze({
    clipId: 'clip-1',
    scope: 'clip' as const,
    ownerKind: 'transition',
    ownerId: 'clip-1.transition.dissolve',
    materialSlot: 'transition-mask',
    refKey: 'transition:com.example.transitions:dissolve',
    extensionId: 'com.example.transitions',
    contributionId: 'dissolve',
    resolverState: 'resolved' as const,
    packageState: 'loaded',
  });

  it('maps unresolved attach states to material-not-resolved with transition slot repair detail', () => {
    const projection = projectHostMaterialRuntime({
      materialRefs: [makeMaterialRef('mat-pending')],
      materialStatuses: [
        {
          materialRefId: 'mat-pending',
          state: 'pending',
          detail: {
            phase: 'active',
          },
        },
      ],
      canonicalRoutes: ['worker-export'],
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-missing', transitionMaskContext)).toMatchObject({
      ok: false,
      diagnostic: {
        code: 'composition/material-not-resolved',
        severity: 'error',
        detail: {
          clipId: 'clip-1',
          scope: 'clip',
          ownerKind: 'transition',
          ownerId: 'clip-1.transition.dissolve',
          materialSlot: 'transition-mask',
          materialRefId: 'mat-missing',
          refKey: 'transition:com.example.transitions:dissolve',
          refState: 'resolved',
          resolverState: 'resolved',
          packageState: 'loaded',
          nextAction: {
            kind: 'materialize',
          },
          repairAction: {
            kind: 'materialize',
            clipId: 'clip-1',
            ownerKind: 'transition',
            ownerId: 'clip-1.transition.dissolve',
            materialSlot: 'transition-mask',
            materialRefId: 'mat-missing',
          },
        },
      },
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-pending', transitionMaskContext)).toMatchObject({
      ok: false,
      diagnostic: {
        code: 'composition/material-not-resolved',
        severity: 'error',
        detail: {
          materialRefId: 'mat-pending',
          materialStatus: 'pending',
          detailPhase: 'active',
          materialSlot: 'transition-mask',
          nextAction: {
            kind: 'bake',
          },
          repairAction: {
            kind: 'bake',
            clipId: 'clip-1',
            ownerKind: 'transition',
            ownerId: 'clip-1.transition.dissolve',
            materialSlot: 'transition-mask',
            materialRefId: 'mat-pending',
          },
        },
      },
    });
  });

  it('maps stale, failed, and route-incompatible attach states to the matching diagnostics', () => {
    const projection = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-stale', { determinism: 'deterministic' }),
        makeMaterialRef('mat-failed'),
        makeMaterialRef('mat-route', { determinism: 'deterministic' }),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-stale',
          state: 'stale',
        },
        {
          materialRefId: 'mat-failed',
          state: 'failed',
        },
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
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-stale', transitionMaskContext)).toMatchObject({
      ok: false,
      diagnostic: {
        code: 'composition/material-stale',
        severity: 'warning',
        detail: {
          materialRefId: 'mat-stale',
          materialStatus: 'stale',
          materialSlot: 'transition-mask',
          nextAction: {
            kind: 'materialize',
          },
          repairAction: {
            kind: 'materialize',
            materialRefId: 'mat-stale',
          },
        },
      },
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-failed', transitionMaskContext)).toMatchObject({
      ok: false,
      diagnostic: {
        code: 'composition/material-failed',
        severity: 'error',
        detail: {
          materialRefId: 'mat-failed',
          materialStatus: 'failed',
          materialSlot: 'transition-mask',
          nextAction: {
            kind: 'open-settings',
          },
          repairAction: {
            kind: 'open-settings',
            materialRefId: 'mat-failed',
          },
        },
      },
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-route', transitionMaskContext)).toMatchObject({
      ok: false,
      diagnostic: {
        code: 'composition/material-route-incompatible',
        severity: 'error',
        detail: {
          materialRefId: 'mat-route',
          materialStatus: 'resolved',
          detailQuality: 'route-incompatible',
          routeScope: 'worker-export',
          materialSlot: 'transition-mask',
          nextAction: {
            kind: 'select-route',
            route: 'worker-export',
          },
          repairAction: {
            kind: 'select-route',
            route: 'worker-export',
            materialRefId: 'mat-route',
          },
        },
      },
    });
  });

  it('does not block attach for resolved materials that only carry warning diagnostics', () => {
    const projection = projectHostMaterialRuntime({
      materialRefs: [
        makeMaterialRef('mat-warning', {
          determinism: 'deterministic',
          provenance: {
            contributionId: 'shader.contrib',
          },
        }),
      ],
      materialStatuses: [
        {
          materialRefId: 'mat-warning',
          state: 'resolved',
          detail: {
            quality: 'weaker-provenance',
          },
        },
      ],
    });

    expect(resolveMaterialAttachEntry(projection, 'mat-warning', transitionMaskContext)).toMatchObject({
      ok: true,
      entry: {
        materialRef: {
          id: 'mat-warning',
        },
      },
    });
  });
});
