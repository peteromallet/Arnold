import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import {
  COMPOSITION_DIAGNOSTIC_CODE,
  referenceStateDiagnosticCode,
  referenceStateSeverity,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import { createProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import { buildExportReadinessPlan } from '@/tools/video-editor/runtime/renderPlanner.ts';
import {
  getVideoFamilyDefinition,
  getVideoFamilyLegacyBridgeStatus,
} from '@reigh/editor-sdk';
import type {
  KnownIdCollection,
  InactiveKnownIds,
  ExportGuardResult,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import type { CompositionGraph, ExtensionContribution, ExtensionDiagnostic, ReferenceState } from '@reigh/editor-sdk';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistrySnapshot,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClip(
  id: string,
  overrides?: Partial<ResolvedTimelineConfig['clips'][number]>,
): ResolvedTimelineConfig['clips'][number] {
  return {
    id,
    at: 0,
    track: 'V1',
    clipType: 'media',
    ...overrides,
  };
}

function makeConfig(
  clips: ResolvedTimelineConfig['clips'],
): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips,
    registry: {},
  };
}

function buildPlannerReadiness(scan: ExportGuardResult) {
  return buildExportReadinessPlan({ guard: scan });
}

function makeProcessDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'proc.descriptor',
    extensionId: 'ext.process',
    processId: 'dataset-process',
    label: 'Dataset Process',
    description: 'Produces attached refs for export readiness.',
    protocol: 'stdio-jsonrpc',
    availableRoutes: ['browser-export'],
    operations: [
      {
        id: 'exportDataset',
        label: 'Export Dataset',
        routes: ['browser-export'],
        outputKinds: ['material', 'artifact'],
        requiredCapabilities: ['browser-export'],
        determinism: 'process-dependent',
      },
    ],
    requiredBy: [{ source: 'extension', extensionId: 'ext.process', contributionId: 'proc.descriptor' }],
    capabilities: {
      defaultRoute: 'browser-export',
      determinism: 'process-dependent',
      capabilityRequirements: [],
    },
    blockers: [],
    nextActions: [],
    spec: {
      id: 'dataset-process',
      label: 'Dataset Process',
      version: { semver: '1.0.0', declaredBy: 'ext.process', contributionId: 'proc.descriptor' },
    },
  } as any;
}

function makeProcessAttachRecord(options?: {
  readonly status?: 'completed' | 'failed';
  readonly includeMaterial?: boolean;
  readonly includeArtifact?: boolean;
}) {
  return createProcessResultAttachRecord({
    processDescriptor: makeProcessDescriptor(),
    attachedAt: '2026-07-04T22:30:00.000Z',
    result: {
      requestId: 'request-1',
      processId: 'dataset-process',
      operationId: 'exportDataset',
      status: options?.status ?? 'completed',
      returnedMaterials: options?.includeMaterial === false
        ? []
        : [{
            id: 'mat-attached',
            mediaKind: 'video',
            locator: { kind: 'provider', uri: 'provider://materials/mat-attached' },
            determinism: 'process-dependent',
            replacementPolicy: 'materialize-on-export',
            producerExtensionId: 'ext.shader',
            provenance: {
              contributionId: 'ext.shader.clip',
              shaderId: 'shader.preview.clip',
            },
          }],
      artifacts: options?.includeArtifact === false
        ? []
        : [{
            id: 'artifact-1',
            route: 'browser-export',
            determinism: 'process-dependent',
            mediaKind: 'video',
            locator: { kind: 'provider', uri: 'provider://artifacts/artifact-1' },
            consumedMaterialRefs: [],
            findings: [],
          }],
      diagnostics: [],
      logs: [],
      availableActions: [],
    } as any,
  });
}

const RegistryEffect: FC<EffectComponentProps> = ({ children }) => children;

function effectRecord(
  effectId: string,
  overrides: Partial<EffectRegistryRecord> = {},
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `test:effect:${effectId}`,
    component: RegistryEffect,
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function snapshotWith(records: readonly EffectRegistryRecord[]): EffectRegistrySnapshot {
  const byId = new Map(records.map((record) => [record.effectId, record]));
  return Object.freeze({
    records: Object.freeze([...records]),
    diagnostics: Object.freeze([]),
    get: (effectId: string) => byId.get(effectId),
    has: (effectId: string) => byId.has(effectId),
  });
}

function clipTypeRecord(
  clipTypeId: string,
  overrides: Partial<ClipTypeRegistryRecord> = {},
): ClipTypeRegistryRecord {
  return {
    clipTypeId,
    contributionId: `test:clipType:${clipTypeId}`,
    renderer: { render: () => null },
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function clipTypeSnapshotWith(records: readonly ClipTypeRegistryRecord[]): ClipTypeRegistrySnapshot {
  const byId = new Map(records.map((record) => [record.clipTypeId, record]));
  return Object.freeze({
    records: Object.freeze([...records]),
    diagnostics: Object.freeze([]),
    get: (clipTypeId: string) => byId.get(clipTypeId),
    has: (clipTypeId: string) => byId.has(clipTypeId),
  });
}

function makeCompositionDiagnostic(
  code: string,
  detail: Record<string, unknown>,
  severity: 'warning' | 'error' = 'warning',
): ExtensionDiagnostic {
  return {
    code,
    severity,
    message: `Diagnostic ${code}`,
    extensionId: detail.extensionId as string | undefined,
    contributionId: detail.contributionId as string | undefined,
    detail,
  };
}

const BLOCKING_REFERENCE_STATE_CASES: ReadonlyArray<{
  readonly state: ReferenceState;
  readonly reason: string;
  readonly packageState?: string;
}> = [
  { state: 'disabled', reason: 'inactive-extension', packageState: 'disabled-by-user' },
  { state: 'duplicate', reason: 'missing-contribution' },
  { state: 'invalid-package', reason: 'inactive-extension', packageState: 'invalid' },
  { state: 'settings-error', reason: 'inactive-extension', packageState: 'settings-error' },
  { state: 'runtime-error', reason: 'inactive-extension', packageState: 'runtime-error' },
  { state: 'version-incompatible', reason: 'inactive-extension', packageState: 'version-incompatible' },
  { state: 'unknown', reason: 'unknown' },
];

function makeReferenceDiagnostic(state: ReferenceState): ExtensionDiagnostic {
  const code = referenceStateDiagnosticCode(state);
  if (!code) {
    throw new Error(`Expected diagnostic code for ${state}`);
  }

  return makeCompositionDiagnostic(
    code,
    {
      nodeId: `contribution:shader:ext.shader:${state}`,
      refKey: `shader:ext.shader:${state}`,
      refState: state,
      extensionId: 'ext.shader',
      contributionId: state,
      resolverState: state,
      packageState: BLOCKING_REFERENCE_STATE_CASES.find((entry) => entry.state === state)?.packageState,
      ownerKind: 'shader',
      ownerId: state,
    },
    referenceStateSeverity(state) as 'warning' | 'error',
  );
}

function makeCompositionGraph(options: {
  readonly diagnostics?: readonly ExtensionDiagnostic[];
  readonly includeResolvedClipShader?: boolean;
  readonly includeResolvedPostprocessShader?: boolean;
  readonly resolvedClipContributionId?: string;
  readonly resolvedClipShaderId?: string;
} = {}): CompositionGraph {
  const nodes: CompositionGraph['nodes'][number][] = [
    {
      id: 'clip:c1',
      kind: 'clip',
      detail: { clipId: 'c1' },
    },
    {
      id: 'timeline-postprocess',
      kind: 'timeline-postprocess',
      detail: { scope: 'postprocess' },
    },
  ];
  const edges: CompositionGraph['edges'][number][] = [];
  const referenceStates: CompositionGraph['referenceStates'][number][] = [];

  if (options.includeResolvedClipShader) {
    const contributionId = options.resolvedClipContributionId ?? 'clip';
    const shaderId = options.resolvedClipShaderId ?? 'shader.clip';
    nodes.push({
      id: `contribution:shader:ext.shader:${contributionId}`,
      kind: 'contribution',
      ref: {
        kind: 'shader',
        extensionId: 'ext.shader',
        contributionId,
      },
    });
    edges.push({
      id: `consumes:clip:c1:contribution:shader:ext.shader:${contributionId}`,
      kind: 'consumes',
      sourceNodeId: 'clip:c1',
      targetNodeId: `contribution:shader:ext.shader:${contributionId}`,
      detail: {
        scope: 'clip',
        clipId: 'c1',
        shaderId,
      },
    });
    referenceStates.push({
      refKey: `shader:ext.shader:${contributionId}`,
      state: 'resolved',
      nodeIds: [`contribution:shader:ext.shader:${contributionId}`],
    });
  }

  if (options.includeResolvedPostprocessShader) {
    nodes.push({
      id: 'contribution:shader:ext.shader:post',
      kind: 'contribution',
      ref: {
        kind: 'shader',
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
      },
    });
    edges.push({
      id: 'consumes:timeline-postprocess:contribution:shader:ext.shader:post',
      kind: 'consumes',
      sourceNodeId: 'timeline-postprocess',
      targetNodeId: 'contribution:shader:ext.shader:post',
      detail: {
        scope: 'postprocess',
        shaderId: 'shader.preview.post',
      },
    });
    referenceStates.push({
      refKey: 'shader:ext.shader:ext.shader.post',
      state: 'resolved',
      nodeIds: ['contribution:shader:ext.shader:post'],
    });
  }

  return {
    nodes,
    edges,
    referenceStates,
    diagnostics: options.diagnostics ?? [],
  };
}

// ---------------------------------------------------------------------------
// Built-in ID collection
// ---------------------------------------------------------------------------

describe('collectBuiltInKnownIds', () => {
  it('returns a frozen KnownIdCollection', () => {
    const ids = collectBuiltInKnownIds();
    expect(Object.isFrozen(ids)).toBe(true);
  });

  it('includes BUILTIN_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('media')).toBe(true);
    expect(ids.clipTypes.has('hold')).toBe(true);
    expect(ids.clipTypes.has('text')).toBe(true);
    expect(ids.clipTypes.has('effect-layer')).toBe(true);
  });

  it('includes TRUSTED_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('image-jump')).toBe(true);
    expect(ids.clipTypes.has('title-card')).toBe(true);
    expect(ids.clipTypes.has('section-hook')).toBe(true);
    expect(ids.clipTypes.has('art-card')).toBe(true);
    expect(ids.clipTypes.has('resource-card')).toBe(true);
    expect(ids.clipTypes.has('cta-card')).toBe(true);
  });

  it('includes built-in entrance effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('slide-up')).toBe(true);
    expect(ids.effectTypes.has('fade')).toBe(true);
    expect(ids.effectTypes.has('zoom-in')).toBe(true);
    expect(ids.effectTypes.has('bounce')).toBe(true);
  });

  it('includes built-in exit effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('fade-out')).toBe(true);
    expect(ids.effectTypes.has('dissolve')).toBe(true);
    expect(ids.effectTypes.has('shrink')).toBe(true);
  });

  it('includes built-in continuous effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('ken-burns')).toBe(true);
    expect(ids.effectTypes.has('float')).toBe(true);
    expect(ids.effectTypes.has('glitch')).toBe(true);
    expect(ids.effectTypes.has('slow-zoom')).toBe(true);
    expect(ids.effectTypes.has('drift')).toBe(true);
  });

  it('includes built-in transition types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.transitionTypes.has('crossfade')).toBe(true);
    expect(ids.transitionTypes.has('wipe')).toBe(true);
    expect(ids.transitionTypes.has('slide-push')).toBe(true);
    expect(ids.transitionTypes.has('zoom-through')).toBe(true);
  });

  it('has no effect/transition overlap with clip types', () => {
    const ids = collectBuiltInKnownIds();
    // Clip types and effect types are separate namespaces
    for (const ct of ids.clipTypes) {
      expect(ids.effectTypes.has(ct)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// Extension-declared ID collection
// ---------------------------------------------------------------------------

describe('collectExtensionDeclaredIds', () => {
  it('returns frozen empty sets for empty input', () => {
    const result = collectExtensionDeclaredIds([]);
    expect(Object.isFrozen(result)).toBe(true);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores bridged contribution kinds (slot, dialog, panel, inspectorSection)', () => {
    // M1-bridged kinds are skipped — they are active, not inactive
    const contributions: ExtensionContribution[] = [
      { id: 'c1' as any, kind: 'slot', slot: 'toolbar' },
      { id: 'c2' as any, kind: 'dialog' },
      { id: 'c3' as any, kind: 'panel' },
      { id: 'c4' as any, kind: 'inspectorSection' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores inactive contributions without effectId/transitionId/clipTypeId', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
  });

  it('collects effect-kind declared IDs now that effect is delegated to a placeholder adapter', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect', effectId: 'my-custom-effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    // Effect executionMaturity is now 'delegated', so declared IDs are collected as inactive.
    expect(result.effectIds.has('my-custom-effect')).toBe(true);
  });

  it('collects transition-kind declared IDs now that transition is delegated to a placeholder adapter', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.2' as any, kind: 'transition', transitionId: 'my-custom-transition' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    // Transition executionMaturity is now 'delegated', so declared IDs are collected as inactive.
    expect(result.transitionIds.has('my-custom-transition')).toBe(true);
  });

  it('preserves the clipType declared-ID bypass even though clipType is runtime-bridged', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.3' as any, kind: 'clipType', clipTypeId: 'my-custom-clip' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(getVideoFamilyDefinition('clipType')?.executionMaturity).toBe('runtime-bridged');
    expect(getVideoFamilyLegacyBridgeStatus('clipType')).toBeNull();
    expect(result.clipTypeIds.has('my-custom-clip')).toBe(true);
  });

  it('deduplicates across multiple contributions (clipType, not bridged)', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'clipType', clipTypeId: 'shared-clip' },
      { id: 'contrib.2' as any, kind: 'clipType', clipTypeId: 'shared-clip' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.clipTypeIds.size).toBe(1);
    expect(result.clipTypeIds.has('shared-clip')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — empty / null config
// ---------------------------------------------------------------------------

describe('scanExportConfig — empty config', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('returns empty result for null config', () => {
    const result = scanExportConfig(null, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns empty result for config with no clips', () => {
    const result = scanExportConfig(makeConfig([]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known clip types pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known clip types', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes built-in clip type "media"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'media' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes built-in clip type "text"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'text' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "title-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'title-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "art-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'art-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — live binding blockers
// ---------------------------------------------------------------------------

describe('scanExportConfig — live binding blockers', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  function validCaptureRef(
    ref: string,
  ): Record<string, unknown> {
    return {
      kind: 'deterministic-capture',
      ref,
      metadata: {
        liveBake: {
          targetKind: 'deterministic-capture',
        },
        deterministicCapture: {
          captureId: ref,
          profile: 'event',
          provenanceHash: 'a'.repeat(64),
          routeConstraints: ['preview', 'browser-export'],
          determinism: 'deterministic',
        },
      },
    };
  }

  function liveClip(
    id: string,
    binding: Record<string, unknown>,
  ): ResolvedTimelineConfig['clips'][number] {
    return makeClip(id, {
      app: {
        live: {
          bindings: [binding],
        },
      },
    } as Partial<ResolvedTimelineConfig['clips'][number]>);
  }

  it('blocks active, missing, disposed, orphaned, malformed, and partially baked live bindings', () => {
    const config = makeConfig([
      liveClip('active-clip', {
        bindingId: 'active-binding',
        sourceId: 'src-active',
        sourceKind: 'generated',
        resolutionStatus: 'active',
      }),
      liveClip('missing-clip', {
        bindingId: 'missing-binding',
        sourceId: 'src-missing',
        sourceKind: 'generated',
      }),
      liveClip('disposed-clip', {
        bindingId: 'disposed-binding',
        sourceId: 'src-disposed',
        sourceKind: 'generated',
        sourceStatus: 'disposed',
      }),
      liveClip('orphaned-clip', {
        bindingId: 'orphaned-binding',
        sourceId: 'src-orphaned',
        sourceKind: 'generated',
        sourceStatus: 'orphaned',
      }),
      liveClip('partial-clip', {
        bindingId: 'partial-binding',
        sourceId: 'src-partial',
        sourceKind: 'generated',
        bake: {
          status: 'partial',
          unresolvedRanges: [{ startFrame: 10, endFrame: 20 }],
        },
      }),
      liveClip('malformed-clip', {
        sourceId: 'src-malformed',
        sourceKind: 'generated',
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.hasBlockingErrors).toBe(true);
    expect(result.diagnostics.filter((diag) => diag.code === 'export/live-binding-unresolved')).toHaveLength(6);
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toHaveLength(6);
    expect(result.findings.map((finding) => finding.detail?.resolutionStatus).sort()).toEqual([
      'active',
      'disposed',
      'malformed',
      'missing',
      'orphaned',
      'partiallyBaked',
    ]);
  });

  it('does not block fully baked deterministic live bindings', () => {
    const config = makeConfig([
      liveClip('baked-clip', {
        bindingId: 'baked-binding',
        sourceId: 'src-baked',
        sourceKind: 'generated',
        bake: {
          status: 'complete',
          deterministicRefs: [
            {
              kind: 'asset',
              ref: 'asset:baked',
              producerId: 'test-producer',
              inputHash: 'sha256:baked',
            },
          ],
        },
      }),
      liveClip('render-material-clip', {
        bindingId: 'render-material-binding',
        sourceId: 'src-render-material',
        sourceKind: 'generated',
        bake: {
          status: 'complete',
          deterministicRefs: [
            {
              kind: 'render-material',
              ref: 'mat:live-baked',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.filter((diag) => diag.code === 'export/live-binding-unresolved')).toEqual([]);
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('keeps sidecar-only, malformed capture, and capture-on-media bindings export-blocking', () => {
    const config = makeConfig([
      liveClip('sidecar-only-clip', {
        bindingId: 'sidecar-only-binding',
        sourceId: 'src-sidecar',
        sourceKind: 'generated',
        resolutionStatus: 'resolved',
        bake: {
          status: 'complete',
          deterministicRefs: [
            {
              kind: 'sidecar',
              ref: 'sidecar:analysis',
            },
          ],
        },
      }),
      liveClip('malformed-capture-clip', {
        bindingId: 'malformed-capture-binding',
        sourceId: 'src-capture-malformed',
        sourceKind: 'generated',
        targetParamName: 'params.opacity',
        targetPath: 'opacity',
        resolutionStatus: 'resolved',
        bake: {
          status: 'complete',
          deterministicRefs: [
            {
              kind: 'deterministic-capture',
              ref: 'capture-malformed',
              metadata: {
                liveBake: {
                  targetKind: 'deterministic-capture',
                },
                deterministicCapture: {
                  captureId: 'capture-malformed',
                  profile: 'event',
                  provenanceHash: 'bad-hash',
                  routeConstraints: ['preview', 'browser-export'],
                  determinism: 'deterministic',
                },
              },
            },
          ],
        },
      }),
      liveClip('media-capture-clip', {
        bindingId: 'media-capture-binding',
        sourceId: 'src-media-capture',
        sourceKind: 'generated',
        targetParamName: 'texture',
        resolutionStatus: 'resolved',
        bake: {
          status: 'complete',
          deterministicRefs: [validCaptureRef('capture-media-only')],
        },
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);
    const liveFindings = result.findings.filter((finding) => finding.reason === 'live-unbaked');

    expect(liveFindings).toHaveLength(3);
    expect(liveFindings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        clipId: 'sidecar-only-clip',
        detail: expect.objectContaining({
          resolutionStatus: 'missing',
          deterministicRefKinds: ['sidecar'],
          bakeStatus: 'complete',
        }),
      }),
      expect.objectContaining({
        clipId: 'malformed-capture-clip',
        detail: expect.objectContaining({
          resolutionStatus: 'malformed',
          deterministicRefKinds: ['deterministic-capture'],
        }),
      }),
      expect.objectContaining({
        clipId: 'media-capture-clip',
        detail: expect.objectContaining({
          resolutionStatus: 'missing',
          deterministicRefKinds: ['deterministic-capture'],
          bakeStatus: 'complete',
        }),
      }),
    ]));
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toHaveLength(3);
  });

  it('does not block validated deterministic-capture refs for non-media live bindings', () => {
    const config = makeConfig([
      liveClip('capture-clip', {
        bindingId: 'capture-binding',
        sourceId: 'src-capture',
        sourceKind: 'generated',
        targetParamName: 'params.opacity',
        targetPath: 'opacity',
        resolutionStatus: 'resolved',
        bake: {
          status: 'complete',
          deterministicRefs: [validCaptureRef('capture-opacity-1')],
        },
      }),
    ]);

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.filter((diag) => diag.code === 'export/live-binding-unresolved')).toEqual([]);
    expect(result.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown clip type
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown clip type', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error diagnostic for truly unknown clip type', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'alien-format' })]);
    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.detail?.clipId).toBe('c1');
    expect(diag.detail?.clipType).toBe('alien-format');
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning diagnostic for extension-declared (inactive) clip type', () => {
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.c' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const config = makeConfig([makeClip('c1', { clipType: 'future-clip' })]);
    const result = scanExportConfig(config, builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('warning');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.message).toContain('inactive extension');
    // Extension-declared clip types do NOT appear in unknownClipTypes
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known effects pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes provider snapshot effect IDs that are absent from legacy known IDs', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'provider-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([effectRecord('provider-glow')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown effects
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
        detail: { effectType: 'crazy-spin', slot: 'entrance' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
      }),
    ]);
  });

  it('keeps scan output as planner-wrapper compatibility input', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const scan = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    const planned = buildPlannerReadiness(scan);

    expect(planned.canBrowserExport).toBe(false);
    expect(planned.routePlans.find((routePlan) => routePlan.route === 'browser-export')).toMatchObject({
      blocked: true,
      blockers: expect.arrayContaining([
        expect.objectContaining({
          id: 'export.effect.c1.entrance.crazy-spin.missing',
          reason: 'missing-contribution',
        }),
      ]),
    });
  });

  it('emits error for unknown continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['hyperspace']);
  });

  it('emits error for unknown exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['explode-out']);
  });

  it('emits warning for extension-declared (inactive) clipType with unknown effect', () => {
    // Effect is bridged, so the metadata-only declared-ID bypass is exercised via clipType.
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.e' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-clip',
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits shared export blocker vocabulary for provider snapshot effects that cannot browser-export', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'preview-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('preview-glow', {
        ownerExtensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'preview-only',
            },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview Glow only supports interactive preview.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'preview-glow',
          renderRoute: 'browser-export',
          blockerReason: 'preview-only',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        clipId: 'c1',
        detail: { effectType: 'preview-glow', slot: 'continuous', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
      }),
    ]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('blocks worker-export independently of browser-export for provider effects that lack worker capability', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'browser-only-effect', duration: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('browser-only-effect', {
        ownerExtensionId: 'ext.browser',
        contributionId: 'ext.browser:effect:browser-only-effect',
        renderability: {
          defaultRoute: 'browser-export',
          determinism: 'deterministic',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'blocked',
              determinism: 'process-dependent',
              blockerReason: 'process-dependent',
              message: 'Browser-only effect requires DOM APIs unavailable in worker.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    // Browser-export is supported, worker-export is blocked — one error diagnostic
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: 'Browser-only effect requires DOM APIs unavailable in worker.',
        extensionId: 'ext.browser',
        contributionId: 'ext.browser:effect:browser-only-effect',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'browser-only-effect',
          renderRoute: 'worker-export',
          blockerReason: 'process-dependent',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.browser-only-effect.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Browser-only effect requires DOM APIs unavailable in worker.',
        clipId: 'c1',
        detail: { effectType: 'browser-only-effect', slot: 'entrance', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.browser-only-effect.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
      }),
    ]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits per-route blockers for inactive provider records across all GUARD_ROUTES', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'stale-effect', intensity: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('stale-effect', {
        ownerExtensionId: 'ext.stale',
        contributionId: 'ext.stale:effect:stale-effect',
        status: 'inactive',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: expect.stringContaining('inactive'),
        extensionId: 'ext.stale',
        contributionId: 'ext.stale:effect:stale-effect',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'stale-effect',
          effectStatus: 'inactive',
          provenance: 'bundled-extension',
        }),
      }),
    ]);
    // One finding+blocker per GUARD_ROUTE
    expect(result.findings).toHaveLength(3);
    expect(result.findings.map((f) => f.route).sort()).toEqual(['browser-export', 'preview', 'worker-export']);
    expect(result.blockers).toHaveLength(3);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits unknown-route-support warnings for provider effects with unknown worker-export capability', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'unclassified-effect', duration: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('unclassified-effect', {
        ownerExtensionId: 'ext.unclass',
        contributionId: 'ext.unclass:effect:unclassified-effect',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'unknown',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'unknown',
              determinism: 'unknown',
              message: 'Worker-export support has not been classified for this effect.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    // One warning for unknown worker-export
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message: 'Worker-export support has not been classified for this effect.',
        extensionId: 'ext.unclass',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'unclassified-effect',
          renderRoute: 'worker-export',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.exit.unclassified-effect.worker-export.unknown',
        severity: 'warning',
        route: 'worker-export',
        reason: 'unknown',
      }),
    ]);
    // Unknown support is non-blocking
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known transitions pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known transition "crossfade"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'crossfade', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known transition "wipe"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown transitions
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown transition', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'star-wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-transition-type');
    expect(result.diagnostics[0].detail?.transitionType).toBe('star-wipe');
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared (inactive) clipType with unknown transition', () => {
    // Transition is bridged, so the metadata-only declared-ID bypass is exercised via clipType.
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.t' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-clip',
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Multiple diagnostics
// ---------------------------------------------------------------------------

describe('scanExportConfig — multiple diagnostics', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('collects multiple unknown types in one scan', () => {
    const clips = [
      makeClip('c1', {
        clipType: 'alien-format',
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
      makeClip('c2', {
        clipType: 'media',
        transition: { type: 'star-wipe', duration: 1 },
        continuous: { type: 'hyperspace', intensity: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 4 diagnostics: unknown clip type + unknown entrance + unknown transition + unknown continuous
    expect(result.diagnostics.length).toBe(4);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('handles multiple clips with same unknown types without duplication', () => {
    const clips = [
      makeClip('c1', { clipType: 'alien-format' }),
      makeClip('c2', { clipType: 'alien-format' }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 2 diagnostics (one per clip) but only one entry in unknownClipTypes
    expect(result.diagnostics.length).toBe(2);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clips (built-in clip type with effects)
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer clips', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits error for unknown continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('hyperspace');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('explode-out');
    expect(result.unknownEffects).toEqual(['explode-out']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared clipType on effect-layer clip', () => {
    // Effect is bridged, so the metadata-only declared-ID bypass is exercised via clipType.
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.el' as any,
        kind: 'clipType',
        clipTypeId: 'future-effect-layer',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'future-effect-layer',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-clip-type');
    expect(result.diagnostics[0].detail?.clipType).toBe('future-effect-layer');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clip with unknown clip type + unknown effects combined
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer combined diagnostics', () => {
  it('collects both unknown clip type and unknown effect for effect-layer style clips', () => {
    const builtIn = collectBuiltInKnownIds();
    const extIds = collectExtensionDeclaredIds([]);

    const clips = [
      makeClip('c1', {
        clipType: 'custom-effect-layer',
        continuous: { type: 'hyperspace', intensity: 0.5 },
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 3 diagnostics: unknown clip type + unknown continuous + unknown entrance
    expect(result.diagnostics.length).toBe(3);
    expect(result.unknownClipTypes).toEqual(['custom-effect-layer']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — clip-type registry snapshot
// ---------------------------------------------------------------------------

describe('scanExportConfig — clip-type registry snapshot', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes a clip type registered in the snapshot with active status and supported browser-export', () => {
    const clip = makeClip('c1', { clipType: 'provider-slideshow' });
    const snapshot = clipTypeSnapshotWith([clipTypeRecord('provider-slideshow')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits error for an inactive clip type in the registry snapshot', () => {
    const clip = makeClip('c1', { clipType: 'stale-clip-type' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('stale-clip-type', {
        ownerExtensionId: 'ext.stale',
        status: 'inactive',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-clip-type',
        message: expect.stringContaining('inactive'),
        extensionId: 'ext.stale',
        contributionId: 'test:clipType:stale-clip-type',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'stale-clip-type',
          clipTypeStatus: 'inactive',
          provenance: 'bundled-extension',
        }),
      }),
    ]);
    // One finding+blocker per CLIP_TYPE_GUARD_ROUTE
    expect(result.findings).toHaveLength(3);
    expect(result.findings.map((f) => f.route).sort()).toEqual(['browser-export', 'preview', 'worker-export']);
    expect(result.blockers).toHaveLength(3);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for a clip type registered but blocked on browser-export', () => {
    const clip = makeClip('c1', { clipType: 'preview-only-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('preview-only-clip', {
        ownerExtensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'preview-only',
            },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview-only clip type cannot browser-export.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-clip-type',
        message: 'Preview-only clip type cannot browser-export.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'preview-only-clip',
          renderRoute: 'browser-export',
          blockerReason: 'preview-only',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
        message: 'Preview-only clip type cannot browser-export.',
        clipId: 'c1',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:clipType:preview-only-clip',
        detail: { clipType: 'preview-only-clip', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.preview-only-clip.browser-export.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
      }),
    ]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for unknown route support on a clip type', () => {
    const clip = makeClip('c1', { clipType: 'unclassified-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('unclassified-clip', {
        ownerExtensionId: 'ext.unclass',
        contributionId: 'ext.unclass:clipType:unclassified-clip',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'unknown',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'unknown',
              determinism: 'unknown',
              message: 'Worker-export support has not been classified for this clip type.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/unknown-route-support',
        message: 'Worker-export support has not been classified for this clip type.',
        extensionId: 'ext.unclass',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'unclassified-clip',
          renderRoute: 'worker-export',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.unclassified-clip.worker-export.unknown',
        severity: 'warning',
        route: 'worker-export',
        reason: 'unknown',
      }),
    ]);
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('still blocks truly unknown clip types not in registry, not in built-in, not extension-declared', () => {
    const clip = makeClip('c1', { clipType: 'alien-format' });
    const snapshot = clipTypeSnapshotWith([]); // empty registry

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unknown-clip-type',
        message: expect.stringContaining('not recognised'),
        detail: { clipId: 'c1', clipType: 'alien-format' },
      }),
    ]);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.alien-format.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
        detail: { clipType: 'alien-format' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.alien-format.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
      }),
    ]);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('prioritises registry snapshot over built-in for non-built-in clip types (does not collide)', () => {
    // 'media' is built-in — registry snapshot is irrelevant
    // 'provider-hero' is only in registry — should pass
    const clip = makeClip('c1', { clipType: 'provider-hero' });
    const snapshot = clipTypeSnapshotWith([clipTypeRecord('provider-hero')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits exact missing materializer blockers for graph clip and postprocess shader summaries', () => {
    const clipShaderMessage = 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".';
    const postprocessShaderMessage = 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.';
    const graph = makeCompositionGraph({
      includeResolvedClipShader: true,
      includeResolvedPostprocessShader: true,
      resolvedClipContributionId: 'ext.shader.clip',
      resolvedClipShaderId: 'shader.preview.clip',
    });

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-shader',
        message: clipShaderMessage,
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.clip',
        detail: expect.objectContaining({
          clipId: 'c1',
          shaderId: 'shader.preview.clip',
          shaderScope: 'clip',
          renderRoute: 'browser-export',
        }),
      }),
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-shader',
        message: postprocessShaderMessage,
        extensionId: 'ext.shader',
        contributionId: 'ext.shader.post',
        detail: expect.objectContaining({
          shaderId: 'shader.preview.post',
          shaderScope: 'postprocess',
          renderRoute: 'browser-export',
        }),
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: clipShaderMessage,
      }),
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        message: postprocessShaderMessage,
      }),
    ]));
    expect(buildPlannerReadiness(result).canBrowserExport).toBe(false);
  });

  it('blocks graph-absent legacy shader metadata through compatibility only', () => {
    const clip = makeClip('c1', {
      app: {
        shader: {
          scope: 'clip',
          extensionId: 'ext.shader',
          contributionId: 'ext.shader.clip',
          shaderId: 'shader.preview.clip',
        },
      },
    });
    const config = {
      ...makeConfig([clip]),
      app: {
        shaderPostprocess: {
          scope: 'postprocess',
          extensionId: 'ext.shader',
          contributionId: 'ext.shader.post',
          shaderId: 'shader.preview.post',
        },
      },
    };

    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'exportGuard.compositionGraph.legacy-shader-ref-compatibility.browser-export',
        route: 'browser-export',
        severity: 'error',
        reason: 'unknown',
        detail: expect.objectContaining({
          source: 'composition-graph-compatibility',
          compatibilityMode: 'legacy-shader-ref',
        }),
      }),
      expect.objectContaining({
        id: 'exportGuard.compositionGraph.legacy-shader-ref-compatibility.worker-export',
        route: 'worker-export',
        severity: 'error',
        reason: 'unknown',
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'exportGuard.compositionGraph.legacy-shader-ref-compatibility.browser-export',
        route: 'browser-export',
        severity: 'error',
        reason: 'unknown',
      }),
      expect.objectContaining({
        id: 'exportGuard.compositionGraph.legacy-shader-ref-compatibility.worker-export',
        route: 'worker-export',
        severity: 'error',
        reason: 'unknown',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ reason: 'missing-material' }),
    ]));
    expect(buildPlannerReadiness(result).canBrowserExport).toBe(false);
  });

  it('suppresses graph shader materializer blockers when a completed process attach already returned the matching material', () => {
    const graph = makeCompositionGraph({
      includeResolvedClipShader: true,
      resolvedClipContributionId: 'ext.shader.clip',
      resolvedClipShaderId: 'shader.preview.clip',
    });

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
      [makeProcessAttachRecord()],
    );

    expect(result.diagnostics).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('keeps graph shader materializer blockers when the process attach did not return the material', () => {
    const graph = makeCompositionGraph({
      includeResolvedClipShader: true,
      resolvedClipContributionId: 'ext.shader.clip',
      resolvedClipShaderId: 'shader.preview.clip',
    });

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
      [makeProcessAttachRecord({ status: 'failed', includeMaterial: false })],
    );

    expect(result.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'export/unrenderable-shader',
        contributionId: 'ext.shader.clip',
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
      }),
    ]));
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('registry snapshot clip type with missing browser-export capability emits blocker', () => {
    const clip = makeClip('c1', { clipType: 'worker-only-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('worker-only-clip', {
        ownerExtensionId: 'ext.worker',
        contributionId: 'ext.worker:clipType:worker-only-clip',
        renderability: {
          defaultRoute: 'worker-export',
          determinism: 'process-dependent',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            // No browser-export capability declared — passes silently
            {
              route: 'worker-export',
              status: 'supported',
              determinism: 'process-dependent',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    // No browser-export capability = pass silently (same as effect pattern)
    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits per-route blockers for active clip types with blocked worker-export', () => {
    const clip = makeClip('c1', { clipType: 'browser-only-clip' });
    const snapshot = clipTypeSnapshotWith([
      clipTypeRecord('browser-only-clip', {
        ownerExtensionId: 'ext.browser',
        contributionId: 'ext.browser:clipType:browser-only-clip',
        renderability: {
          defaultRoute: 'browser-export',
          determinism: 'deterministic',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'browser-export',
              status: 'supported',
              determinism: 'deterministic',
            },
            {
              route: 'worker-export',
              status: 'blocked',
              determinism: 'process-dependent',
              blockerReason: 'process-dependent',
              message: 'Browser-only clip type requires DOM APIs unavailable in worker.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, undefined, undefined, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-clip-type',
        message: 'Browser-only clip type requires DOM APIs unavailable in worker.',
        extensionId: 'ext.browser',
        contributionId: 'ext.browser:clipType:browser-only-clip',
        detail: expect.objectContaining({
          clipId: 'c1',
          clipType: 'browser-only-clip',
          renderRoute: 'worker-export',
          blockerReason: 'process-dependent',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.browser-only-clip.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Browser-only clip type requires DOM APIs unavailable in worker.',
        clipId: 'c1',
        extensionId: 'ext.browser',
        contributionId: 'ext.browser:clipType:browser-only-clip',
        detail: { clipType: 'browser-only-clip', provenance: 'trusted-loader' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.clipType.c1.browser-only-clip.worker-export.process-dependent',
        severity: 'error',
        route: 'worker-export',
        reason: 'process-dependent',
      }),
    ]);
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — composition graph target diagnostics
// ---------------------------------------------------------------------------

describe('scanExportConfig — composition graph target diagnostics', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it.each(BLOCKING_REFERENCE_STATE_CASES)(
    'promotes graph-derived $state reference diagnostics to export blockers',
    ({ state, reason }) => {
      const diagnostic = makeReferenceDiagnostic(state);
      const graph = makeCompositionGraph({ diagnostics: [diagnostic] });

      const result = scanExportConfig(
        makeConfig([makeClip('c1')]),
        builtIn,
        extIds,
        undefined,
        undefined,
        undefined,
        graph,
      );

      expect(result.diagnostics).toEqual([
        expect.objectContaining({
          severity: 'error',
          code: 'export/unresolved-ref',
          message: `Diagnostic ${diagnostic.code}`,
          extensionId: 'ext.shader',
          contributionId: state,
          detail: expect.objectContaining({
            source: 'composition-graph',
            graphDiagnosticCode: diagnostic.code,
            refKey: `shader:ext.shader:${state}`,
            refState: state,
            resolverState: state,
          }),
        }),
      ]);
      expect(result.findings).toHaveLength(2);
      expect(result.findings.map((finding) => finding.route).sort()).toEqual(['browser-export', 'worker-export']);
      expect(result.blockers).toHaveLength(2);
      expect(result.blockers).toEqual(expect.arrayContaining([
        expect.objectContaining({
          route: 'browser-export',
          severity: 'error',
          reason,
          extensionId: 'ext.shader',
          contributionId: state,
          detail: expect.objectContaining({
            graphDiagnosticCode: diagnostic.code,
            refState: state,
            resolverState: state,
          }),
        }),
        expect.objectContaining({
          route: 'worker-export',
          severity: 'error',
          reason,
          extensionId: 'ext.shader',
          contributionId: state,
        }),
      ]));
      expect(result.hasBlockingErrors).toBe(true);
    },
  );

  it.each([
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.INVALID_TARGET_PATH,
      exportCode: 'export/invalid-target-path',
      reason: 'unknown',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        targetKind: 'clip-param',
        targetPath: 'params.opacity',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET,
      exportCode: 'export/unsupported-reserved-target',
      reason: 'inactive-extension',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        targetKind: 'reserved-target',
        targetPath: 'timeline.audio.level',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF,
      exportCode: 'export/unknown-target-ref',
      reason: 'missing-contribution',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        refKey: 'effect:ext.fx:missing',
        targetKind: 'effect-param',
        targetPath: 'gain',
        extensionId: 'ext.fx',
        contributionId: 'missing',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM,
      exportCode: 'export/unknown-uniform',
      reason: 'unknown',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        refKey: 'shader:ext.shader:clip',
        targetKind: 'shader-uniform',
        targetPath: 'uniforms.glow',
        uniformName: 'glow',
        extensionId: 'ext.shader',
        contributionId: 'clip',
        shaderId: 'shader.clip',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.NON_BINDABLE_TARGET,
      exportCode: 'export/non-bindable-target',
      reason: 'unknown',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        targetKind: 'effect-param',
        targetPath: 'intensity',
        extensionId: 'ext.fx',
        contributionId: 'fx',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.TARGET_VALUE_TYPE_ERROR,
      exportCode: 'export/target-value-type-error',
      reason: 'unknown',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        targetKind: 'clip-param',
        targetPath: 'opacity',
        expectedValueType: 'number',
        actualValueType: 'string',
      },
    },
    {
      graphCode: COMPOSITION_DIAGNOSTIC_CODE.TARGET_INTERPOLATION_GAP,
      exportCode: 'export/target-interpolation-gap',
      reason: 'unknown',
      detail: {
        clipId: 'c1',
        nodeId: 'clip:c1',
        targetKind: 'clip-param',
        targetPath: 'opacity',
        interpolation: 'linear',
      },
    },
  ])(
    'emits scanner blockers for $graphCode and planner-wrapper findings',
    ({ graphCode, exportCode, reason, detail }) => {
      const graph = makeCompositionGraph({
        diagnostics: [makeCompositionDiagnostic(graphCode, detail)],
      });

      const result = scanExportConfig(
        makeConfig([makeClip('c1')]),
        builtIn,
        extIds,
        undefined,
        undefined,
        undefined,
        graph,
      );

      expect(result.diagnostics).toEqual([
        expect.objectContaining({
          severity: 'error',
          code: exportCode,
          message: `Diagnostic ${graphCode}`,
          detail: expect.objectContaining({
            source: 'composition-graph',
            graphDiagnosticCode: graphCode,
            clipId: 'c1',
            targetKind: detail.targetKind,
            targetPath: detail.targetPath,
          }),
        }),
      ]);
      expect(result.findings).toHaveLength(2);
      expect(result.findings.map((finding) => finding.route).sort()).toEqual(['browser-export', 'worker-export']);
      expect(result.blockers).toHaveLength(2);
      expect(result.blockers).toEqual(expect.arrayContaining([
        expect.objectContaining({
          severity: 'error',
          route: 'browser-export',
          reason,
          detail: expect.objectContaining({
            graphDiagnosticCode: graphCode,
            targetKind: detail.targetKind,
            targetPath: detail.targetPath,
          }),
        }),
      ]));
      expect(result.hasBlockingErrors).toBe(true);

      const planner = buildPlannerReadiness(result);
      expect(planner.canBrowserExport).toBe(false);
      expect(planner.canWorkerExport).toBe(false);
      expect(planner.findings).toEqual(expect.arrayContaining([
        expect.objectContaining({
          severity: 'error',
          route: 'browser-export',
          reason,
          detail: expect.objectContaining({
            source: 'composition-graph',
            graphDiagnosticCode: graphCode,
            targetKind: detail.targetKind,
            targetPath: detail.targetPath,
          }),
        }),
      ]));
    },
  );

  it('suppresses graph target blockers when a completed process attach already returned the referenced artifact', () => {
    const graph = makeCompositionGraph({
      diagnostics: [
        makeCompositionDiagnostic(COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE, {
          clipId: 'c1',
          nodeId: 'clip:c1',
          targetKind: 'capture-target',
          targetPath: 'params.dataset',
          captureRef: 'artifact-1',
          provenanceHash: 'a'.repeat(64),
        }),
      ],
    });

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
      [makeProcessAttachRecord()],
    );

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('keeps graph shader materializer blockers unchanged when target blockers are also present', () => {
    const graph = makeCompositionGraph({
      includeResolvedClipShader: true,
      diagnostics: [
        makeCompositionDiagnostic(COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM, {
          clipId: 'c1',
          nodeId: 'clip:c1',
          refKey: 'shader:ext.shader:clip',
          targetKind: 'shader-uniform',
          targetPath: 'uniforms.glow',
          uniformName: 'glow',
          extensionId: 'ext.shader',
          contributionId: 'clip',
          shaderId: 'shader.clip',
        }),
      ],
    });

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'export/unknown-uniform',
        detail: expect.objectContaining({
          graphDiagnosticCode: COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM,
          targetPath: 'uniforms.glow',
        }),
      }),
      expect.objectContaining({
        code: 'export/unrenderable-shader',
        message: 'Shader "shader.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".',
        detail: expect.objectContaining({
          clipId: 'c1',
          shaderId: 'shader.clip',
          shaderScope: 'clip',
          renderRoute: 'browser-export',
        }),
      }),
    ]));
    expect(result.blockers.filter((blocker) => blocker.reason === 'missing-material')).toHaveLength(2);
    expect(result.blockers.filter((blocker) => blocker.reason === 'unknown')).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// M5 (Effect / Transition) composition graph diagnostics
// ---------------------------------------------------------------------------

describe('scanExportConfig — composition graph M5 diagnostics', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  function makeM5CompositionGraph(diagnostics: ExtensionDiagnostic[]): CompositionGraph {
    return {
      nodes: [
        { id: 'clip:c1', kind: 'clip' as const, detail: { clipId: 'c1' } },
      ],
      edges: [],
      referenceStates: [],
      diagnostics,
    };
  }

  it('emits scanner blockers for effect error diagnostic (EFFECT_DISABLED_REF)', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.EFFECT_DISABLED_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:effect:ext.fx:disabled-fx',
          refKey: 'effect:ext.fx:disabled-fx',
          refState: 'disabled',
          extensionId: 'ext.fx',
          contributionId: 'disabled-fx',
          resolverState: 'disabled',
          packageState: 'disabled-by-user',
          ownerKind: 'effect',
          ownerId: 'disabled-fx',
        },
        'error',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/effect-unresolved-ref',
        message: 'Diagnostic composition/effect-disabled-ref',
        detail: expect.objectContaining({
          source: 'composition-graph',
          graphDiagnosticCode: COMPOSITION_DIAGNOSTIC_CODE.EFFECT_DISABLED_REF,
          clipId: 'c1',
          diagnosticKind: 'effect',
          refState: 'disabled',
        }),
      }),
    ]);
    expect(result.findings).toHaveLength(2);
    expect(result.findings.map((f) => f.route).sort()).toEqual(['browser-export', 'worker-export']);
    expect(result.blockers).toHaveLength(2);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        route: 'browser-export',
        reason: 'inactive-extension',
      }),
    ]));
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('surfaces effect warning diagnostic (EFFECT_MISSING_REF) as findings but does NOT block export', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.EFFECT_MISSING_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:effect:ext.fx:missing',
          refKey: 'effect:ext.fx:missing',
          refState: 'missing',
          extensionId: 'ext.fx',
          contributionId: 'missing',
          resolverState: 'missing',
          ownerKind: 'effect',
          ownerId: 'missing-fx',
        },
        'warning',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    // Should have a warning diagnostic but no blockers
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/effect-unresolved-ref',
      }),
    ]);
    expect(result.findings).toHaveLength(2);
    expect(result.blockers).toHaveLength(0);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits scanner blockers for transition error diagnostic (TRANSITION_DISABLED_REF)', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.TRANSITION_DISABLED_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:transition:ext.tx:disabled-tx',
          refKey: 'transition:ext.tx:disabled-tx',
          refState: 'disabled',
          extensionId: 'ext.tx',
          contributionId: 'disabled-tx',
          resolverState: 'disabled',
          packageState: 'disabled-by-user',
          ownerKind: 'transition',
          ownerId: 'disabled-tx',
        },
        'error',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/transition-unresolved-ref',
        message: 'Diagnostic composition/transition-disabled-ref',
        detail: expect.objectContaining({
          source: 'composition-graph',
          graphDiagnosticCode: COMPOSITION_DIAGNOSTIC_CODE.TRANSITION_DISABLED_REF,
          clipId: 'c1',
          diagnosticKind: 'transition',
          refState: 'disabled',
        }),
      }),
    ]);
    expect(result.findings).toHaveLength(2);
    expect(result.blockers).toHaveLength(2);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('surfaces transition warning diagnostic (TRANSITION_MISSING_REF) as findings but does NOT block export', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.TRANSITION_MISSING_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:transition:ext.tx:missing',
          refKey: 'transition:ext.tx:missing',
          refState: 'missing',
          extensionId: 'ext.tx',
          contributionId: 'missing',
          resolverState: 'missing',
          ownerKind: 'transition',
          ownerId: 'missing-tx',
        },
        'warning',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'warning',
        code: 'export/transition-unresolved-ref',
      }),
    ]);
    expect(result.findings).toHaveLength(2);
    expect(result.blockers).toHaveLength(0);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('clears blockers when M5 graph has no diagnostics (resolved state)', () => {
    const graph = makeM5CompositionGraph([]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('feeds M5 scanner output into planner wrapper readiness', () => {
    // With error diagnostic - planner wrapper marks export blocked.
    const blockedGraph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.EFFECT_DISABLED_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:effect:ext.fx:disabled',
          refKey: 'effect:ext.fx:disabled',
          refState: 'disabled',
          extensionId: 'ext.fx',
          contributionId: 'disabled',
          resolverState: 'disabled',
          packageState: 'disabled-by-user',
          ownerKind: 'effect',
        },
        'error',
      ),
    ]);

    const blockedScan = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      blockedGraph,
    );
    const blockedPlanner = buildPlannerReadiness(blockedScan);
    expect(blockedPlanner.canBrowserExport).toBe(false);
    expect(blockedPlanner.canWorkerExport).toBe(false);
    expect(blockedPlanner.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        route: 'browser-export',
        reason: 'inactive-extension',
        detail: expect.objectContaining({
          source: 'composition-graph',
          graphDiagnosticCode: COMPOSITION_DIAGNOSTIC_CODE.EFFECT_DISABLED_REF,
        }),
      }),
    ]));

    // With no diagnostics (resolved) - planner wrapper clears export.
    const resolvedGraph = makeM5CompositionGraph([]);
    const resolvedScan = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      resolvedGraph,
    );
    const resolvedPlanner = buildPlannerReadiness(resolvedScan);
    expect(resolvedPlanner.canBrowserExport).toBe(true);
    expect(resolvedPlanner.canWorkerExport).toBe(true);
  });

  it('emits inactive-extension scanner blockers for transition invalid package refs', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.TRANSITION_INVALID_PACKAGE_REF,
        {
          clipId: 'c1',
          nodeId: 'contribution:transition:ext.tx:invalid-pkg',
          refKey: 'transition:ext.tx:invalid-pkg',
          refState: 'invalid-package',
          extensionId: 'ext.tx',
          contributionId: 'invalid-pkg',
          resolverState: 'invalid-package',
          packageState: 'invalid',
          ownerKind: 'transition',
          ownerId: 'invalid-pkg',
        },
        'error',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/transition-unresolved-ref',
      }),
    ]);
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        reason: 'inactive-extension',
        route: 'browser-export',
      }),
    ]));
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('handles both effect and transition diagnostics simultaneously', () => {
    const graph = makeM5CompositionGraph([
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.EFFECT_DISABLED_REF,
        {
          clipId: 'c1',
          nodeId: 'n1',
          refKey: 'effect:ext.fx:disabled',
          refState: 'disabled',
          extensionId: 'ext.fx',
          contributionId: 'disabled',
          resolverState: 'disabled',
          ownerKind: 'effect',
        },
        'error',
      ),
      makeCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.TRANSITION_MISSING_REF,
        {
          clipId: 'c1',
          nodeId: 'n2',
          refKey: 'transition:ext.tx:missing',
          refState: 'missing',
          extensionId: 'ext.tx',
          contributionId: 'missing',
          resolverState: 'missing',
          ownerKind: 'transition',
        },
        'warning',
      ),
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1')]),
      builtIn,
      extIds,
      undefined,
      undefined,
      undefined,
      graph,
    );

    // Both diagnostics surfaced
    expect(result.diagnostics).toHaveLength(2);
    expect(result.diagnostics.map((d) => d.code).sort()).toEqual([
      'export/effect-unresolved-ref',
      'export/transition-unresolved-ref',
    ]);
    // Only the effect error emits scanner blockers.
    expect(result.blockers).toHaveLength(2); // 2 routes for the blocking effect
    expect(result.findings).toHaveLength(4); // 2 routes × 2 diagnostics
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('scanExportConfig — edge cases', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('handles clip with no clipType', () => {
    const clip = makeClip('c1', { clipType: undefined });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('handles clip without effects or transitions', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: undefined,
      exit: undefined,
      continuous: undefined,
      transition: undefined,
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('frozen result cannot be mutated', () => {
    const result = scanExportConfig(null, builtIn, extIds);
    expect(() => {
      (result as { diagnostics: unknown[] }).diagnostics = [];
    }).toThrow();
  });

  it('preserves inactiveExtensionIds in result', () => {
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.e' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1', { clipType: 'media' })]),
      builtIn,
      extIdsWithClip,
    );

    expect(result.inactiveExtensionIds.clipTypeIds.has('future-clip')).toBe(true);
  });
});
