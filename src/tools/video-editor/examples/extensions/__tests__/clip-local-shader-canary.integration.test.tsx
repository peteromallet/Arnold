// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  type ExtensionDiagnostic,
  type ExtensionDiagnosticsService,
  type ReighExtension,
  type TimelineSnapshot,
} from '@/sdk/index';
import { createExtensionContext } from '@/tools/video-editor/runtime/extensionContextFactory';
import {
  CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
  CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
  CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
  CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
  CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
  createClipLocalShaderCanaryExtension,
  type ClipLocalShaderCanaryController,
} from '@/tools/video-editor/examples/extensions/clip-local-shader-canary';
import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
import type {
  ShaderEffectRegistry,
  ShaderEffectRegistryRecord,
  ShaderEffectRegistrySnapshot,
} from '@/tools/video-editor/shaders/registry/types.ts';
import {
  createTimelineClipShaderMetadata,
  listClipShaderPickerEntries,
} from '@/tools/video-editor/lib/shader-catalog.ts';
import { serializeTimelineConfigSnapshot } from '@/tools/video-editor/lib/timeline-domain.ts';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import { extractGraphPreviewOps } from '@/tools/video-editor/lib/timeline-patch.ts';
import { ClipShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx';
import { ShaderInspector } from '@/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { applyGraphPreviewOperations } from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import { COMPOSITION_DIAGNOSTIC_CODE } from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import type { ContributionIndex } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
  TimelineShaderKeyframe,
  TimelineShaderUniformKeyframes,
} from '@/tools/video-editor/types/index.ts';

const createWebGLShaderPreviewSurfaceMock = vi.hoisted(() => vi.fn());

vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
  createWebGLShaderPreviewSurface: createWebGLShaderPreviewSurfaceMock,
}));

const emptyAssetRegistry = { assets: {} };

const canaryUniformCases: ReadonlyArray<{
  readonly name: string;
  readonly interpolation: TimelineShaderKeyframe['interpolation'];
  readonly addedValue: TimelineShaderKeyframe['value'];
  readonly updatedValue: TimelineShaderKeyframe['value'];
}> = Object.freeze([
  {
    name: 'intensity',
    interpolation: 'linear',
    addedValue: 0.15,
    updatedValue: 0.65,
  },
  {
    name: 'tint',
    interpolation: 'linear',
    addedValue: [0.2, 0.4, 0.8, 1],
    updatedValue: [0.9, 0.3, 0.1, 1],
  },
  {
    name: 'center',
    interpolation: 'linear',
    addedValue: [0.5, 0.25],
    updatedValue: [0.2, 0.8],
  },
  {
    name: 'showGrid',
    interpolation: 'hold',
    addedValue: true,
    updatedValue: false,
  },
  {
    name: 'bandCount',
    interpolation: 'hold',
    addedValue: 8,
    updatedValue: 12,
  },
  {
    name: 'holdFrame',
    interpolation: 'hold',
    addedValue: 12,
    updatedValue: 24,
  },
  {
    name: 'holdTime',
    interpolation: 'linear',
    addedValue: 0.25,
    updatedValue: 0.5,
  },
  {
    name: 'blendMode',
    interpolation: 'hold',
    addedValue: 'soft',
    updatedValue: 'invert-lift',
  },
]);

function shaderKeyframe(
  time: number,
  value: TimelineShaderKeyframe['value'],
  interpolation: TimelineShaderKeyframe['interpolation'],
): TimelineShaderKeyframe {
  return { time, value, interpolation };
}

function buildCanaryKeyframes(
  selector: 'addedValue' | 'updatedValue',
): TimelineShaderUniformKeyframes {
  return Object.fromEntries(canaryUniformCases.map((entry, index) => {
    const rawPath = index % 2 === 0 ? entry.name : `uniforms.${entry.name}`;
    return [rawPath, [shaderKeyframe(0.5, entry[selector], entry.interpolation)]];
  }));
}

function makeDiagnosticsService(extensionId = CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID): ExtensionDiagnosticsService {
  const diagnostics: ExtensionDiagnostic[] = [];
  return {
    report(diagnostic) {
      diagnostics.push(Object.freeze({
        ...diagnostic,
        extensionId,
      }));
    },
    get diagnostics() {
      return diagnostics;
    },
  };
}

function activateCanary(options: {
  includeDiagnosticShader?: boolean;
} = {}): {
  extension: ReighExtension;
  registry: ShaderEffectRegistry;
  snapshot: ShaderEffectRegistrySnapshot;
  diagnosticsService: ExtensionDiagnosticsService;
  controller: ClipLocalShaderCanaryController;
  dispose: () => void;
} {
  const extension = createClipLocalShaderCanaryExtension({
    includeDiagnosticShader: options.includeDiagnosticShader,
  });
  const registry = createShaderEffectRegistry();
  const diagnosticsService = makeDiagnosticsService();
  const shaders = createShaderRegistrationService({
    extension,
    shaderRegistry: registry,
    diagnosticsService,
  });
  const ctx = createExtensionContext(
    extension,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    shaders,
  );
  const handle = extension.activate?.(ctx);
  const controller = handle as ClipLocalShaderCanaryController;

  return {
    extension,
    registry,
    snapshot: registry.getSnapshot(),
    diagnosticsService,
    controller,
    dispose() {
      handle?.dispose();
      registry.dispose();
    },
  };
}

function requireCanaryRecord(snapshot: ShaderEffectRegistrySnapshot): ShaderEffectRegistryRecord {
  const record = snapshot.get(CLIP_LOCAL_SHADER_CANARY_SHADER_ID, CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID);
  expect(record).toBeDefined();
  return record!;
}

function makeClip(record: ShaderEffectRegistryRecord): ResolvedTimelineClip {
  return {
    id: 'clip-canary',
    track: 'V1',
    at: 0,
    hold: 60,
    clipType: 'media',
    app: {
      shader: createTimelineClipShaderMetadata(record),
      untouched: { survives: true },
    },
  } as ResolvedTimelineClip;
}

function makeConfig(clip: ResolvedTimelineClip): ResolvedTimelineConfig {
  return {
    output: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [clip],
    registry: {},
  } as ResolvedTimelineConfig;
}

async function roundTripSnapshot(config: ResolvedTimelineConfig): Promise<TimelineSnapshot> {
  const serialized = serializeTimelineConfigSnapshot(config).config;
  const data = await buildTimelineData(serialized, emptyAssetRegistry);
  return createTimelineReader({ data }).snapshot();
}

function makeShaderSnapshot(clip: ResolvedTimelineClip): TimelineSnapshot {
  const shader = clip.app?.shader!;
  return {
    projectId: 'project-shader-canary',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [{
      id: clip.id,
      track: clip.track,
      at: clip.at,
      duration: clip.hold ?? 60,
      clipType: clip.clipType ?? 'media',
      managed: false,
    }],
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
    assetKeys: [],
    app: {},
    shaders: [{
      id: `${clip.id}:shader:${shader.shaderId}`,
      shaderId: shader.shaderId,
      scope: 'clip',
      clipId: clip.id,
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
      enabled: shader.enabled !== false,
    }],
    outputMetadata: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
  };
}

function makeGraphCoverageSnapshot(clip: ResolvedTimelineClip): TimelineSnapshot {
  const base = makeShaderSnapshot(clip);
  const shader = clip.app?.shader!;
  return {
    ...base,
    clips: [
      {
        ...base.clips[0],
        liveBindings: [{
          bindingId: 'clip-live-binding',
          clipId: clip.id,
          sourceId: 'live-source',
          sourceKind: 'generated',
          targetKind: 'shader-uniform',
          targetMaterialId: shader.contributionId,
          targetPath: 'uniforms.intensity',
          status: 'resolved',
        }],
      },
      {
        id: 'clip-automation',
        track: 'V1',
        at: 12,
        duration: 12,
        clipType: 'automation',
        managed: false,
        automation: [{
          contributionId: shader.contributionId,
          parameterPath: 'params.intensity',
          targetPath: 'uniforms.intensity',
          keyframeCount: 2,
          enabled: true,
        }],
      },
    ],
  };
}

function makePreviewSurface() {
  return {
    canvas: document.createElement('canvas'),
    status: 'ready',
    diagnostics: [],
    setUniformValues: vi.fn(),
    setTextureValues: vi.fn(),
    resize: vi.fn(),
    renderFrame: vi.fn(),
    dispose: vi.fn(),
  };
}

afterEach(() => {
  cleanup();
  createWebGLShaderPreviewSurfaceMock.mockReset();
  vi.restoreAllMocks();
});

describe('clip-local-shader-canary extension', () => {
  it('registers through the public shader SDK path and exposes runtime, diagnostics, renderability, and picker contracts', () => {
    const test = activateCanary();
    const runtime = normalizeExtensionRuntime([test.extension]);
    const record = requireCanaryRecord(test.snapshot);
    const diagnosticRecord = test.snapshot.get(
      CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
    );

    expect(runtime.shaders.map((shader) => shader.id)).toEqual([
      CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
    ]);
    expect(runtime.effects.some((effect) => effect.id === CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID)).toBe(false);

    expect(record).toMatchObject({
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
      ownerExtensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      status: 'active',
      source: { kind: 'inline' },
      pass: { kind: 'clip', inputTextureUniform: 'u_source' },
    });
    expect(record.uniforms?.map((uniform) => uniform.type)).toEqual([
      'float',
      'color',
      'vec2',
      'bool',
      'int',
      'frame',
      'time',
      'enum',
      'textureRef',
    ]);
    expect(record.textures).toEqual([
      expect.objectContaining({
        name: 'u_source',
        sourceKind: 'clip-frame',
        required: true,
      }),
    ]);
    expect(record.renderability.capabilities).toEqual(expect.arrayContaining([
      expect.objectContaining({ route: 'preview', status: 'supported' }),
      expect.objectContaining({ route: 'browser-export', status: 'blocked', blockerReason: 'missing-material' }),
      expect.objectContaining({ route: 'worker-export', status: 'blocked', blockerReason: 'missing-material' }),
    ]));

    expect(diagnosticRecord).toMatchObject({
      shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      status: 'error',
      diagnostics: [
        expect.objectContaining({
          severity: 'error',
          code: 'shader/uniform-unsupported',
        }),
      ],
    });
    expect(test.diagnosticsService.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'info',
        code: 'shaders/registered',
        detail: expect.objectContaining({ shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID }),
      }),
      expect.objectContaining({
        severity: 'error',
        code: 'shader/uniform-unsupported',
        detail: expect.objectContaining({ shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID }),
      }),
    ]));

    const pickerEntries = listClipShaderPickerEntries(test.snapshot);
    expect(pickerEntries).toEqual(expect.arrayContaining([
      expect.objectContaining({
        record,
        passKind: 'clip',
        disabled: false,
        previewOnly: true,
        blockedRoutes: expect.arrayContaining(['browser-export', 'worker-export']),
      }),
      expect.objectContaining({
        record: diagnosticRecord,
        disabled: true,
        errorDiagnostics: [expect.objectContaining({ code: 'shader/uniform-unsupported' })],
      }),
    ]));

    test.dispose();
  });

  it('materializes timeline metadata defaults, inspector edits, preview input, and planner export blockers for the canary shader', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);
    const config = makeConfig(clip);
    const applyEdit = vi.fn();

    expect(clip.app?.shader).toEqual(expect.objectContaining({
      scope: 'clip',
      extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
      uniforms: expect.objectContaining({
        intensity: 0.35,
        tint: [0.2, 0.7, 1, 1],
        center: [0.5, 0.5],
        showGrid: true,
        bandCount: 8,
        holdFrame: 12,
        holdTime: 0.25,
        blendMode: 'soft',
      }),
      textures: {
        u_source: { kind: 'clip-frame' },
      },
    }));

    render(
      <ShaderInspector
        resolvedConfig={config}
        clip={clip}
        applyEdit={applyEdit}
        shaderSnapshot={test.snapshot}
      />,
    );
    fireEvent.change(screen.getByTestId('schema-form-widget-intensity'), {
      target: { value: '0.65' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));

    expect(applyEdit).toHaveBeenCalledTimes(1);
    expect(applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader).toEqual(expect.objectContaining({
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
      uniforms: expect.objectContaining({ intensity: 0.65 }),
      textures: { u_source: { kind: 'clip-frame' } },
      metadata: expect.objectContaining({ uniformPreset: 'custom' }),
    }));
    cleanup();

    const previewSurface = makePreviewSurface();
    createWebGLShaderPreviewSurfaceMock.mockReturnValue(previewSurface);
    render(
      <ClipShaderPreviewCanvas
        shader={clip.app!.shader!}
        record={record}
        timeSeconds={1.25}
        frame={38}
        width={640}
        height={360}
        testId="canary-clip-shader-preview"
      />,
    );

    expect(screen.getByTestId('canary-clip-shader-preview')).toHaveAttribute(
      'data-shader-id',
      CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
    );
    expect(createWebGLShaderPreviewSurfaceMock).toHaveBeenCalledWith(expect.objectContaining({
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
      extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      fragmentSource: expect.stringContaining('gl_FragColor'),
      uniforms: record.uniforms,
      uniformValues: clip.app!.shader!.uniforms,
      textures: record.textures,
      textureValues: clip.app!.shader!.textures,
      width: 640,
      height: 360,
    }));
    expect(previewSurface.renderFrame).toHaveBeenCalledWith(1.25, 38);

    const planner = planRender({ snapshot: makeShaderSnapshot(clip) });
    expect(planner.canBrowserExport).toBe(false);
    expect(planner.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
        message: `Shader "${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}" cannot export because no shader materializer produced RenderMaterial for clip "clip-canary".`,
      }),
    ]));

    test.dispose();
  });

  it('routes clip shader assign/remove and all eight shader-uniform keyframe mutations through graph preview and timeline serialization', async () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const runtime = normalizeExtensionRuntime([test.extension]);
    const record = requireCanaryRecord(test.snapshot);
    const assignedClip = makeClip(record);
    const unassignedClip = {
      ...assignedClip,
      app: {
        ...assignedClip.app,
      },
    } as ResolvedTimelineClip;
    delete (unassignedClip.app as Record<string, unknown>).shader;

    const unassignedSnapshot = await roundTripSnapshot(makeConfig(unassignedClip));
    const assignedSnapshot = await roundTripSnapshot(makeConfig(assignedClip));
    const assignedShader = assignedSnapshot.shaders[0];
    expect(assignedShader).toBeDefined();

    const assignOps = extractGraphPreviewOps([
      {
        op: 'clip.update',
        target: assignedClip.id,
        payload: {
          app: {
            shader: assignedClip.app?.shader,
          },
        },
      } as any,
    ]);
    expect(assignOps).toEqual([
      expect.objectContaining({
        kind: 'shader.assign',
        shader: expect.objectContaining({
          id: `clip:${assignedClip.id}:shader:${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}`,
          clipId: assignedClip.id,
          shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
        }),
      }),
    ]);

    const assignPreview = applyGraphPreviewOperations({
      snapshot: unassignedSnapshot,
      contributionIndex: runtime.contributionIndex,
    }, assignOps);
    expect(assignPreview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: `clip:${assignedClip.id}`,
        targetNodeId: `contribution:shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
        detail: expect.objectContaining({
          clipId: assignedClip.id,
          shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
          refKey: `shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
        }),
      }),
    ]));

    const removeOps = extractGraphPreviewOps([
      {
        op: 'clip.update',
        target: assignedClip.id,
        payload: {
          app: {
            shader: null,
          },
        },
      } as any,
    ]);
    expect(removeOps).toEqual([
      expect.objectContaining({
        kind: 'shader.remove',
        scope: 'clip',
        clipId: assignedClip.id,
      }),
    ]);

    const removePreview = applyGraphPreviewOperations({
      snapshot: assignedSnapshot,
      contributionIndex: runtime.contributionIndex,
    }, removeOps);
    expect(removePreview?.edges.some((edge) => (
      edge.kind === 'consumes'
      && edge.detail?.shaderId === CLIP_LOCAL_SHADER_CANARY_SHADER_ID
      && edge.detail?.clipId === assignedClip.id
    ))).toBe(false);

    const addOps = canaryUniformCases.map((entry, index) => ({
      kind: 'keyframe.add' as const,
      shaderId: assignedShader!.id,
      uniformPath: index % 2 === 0 ? entry.name : `uniforms.${entry.name}`,
      keyframe: shaderKeyframe(0.5, entry.addedValue, entry.interpolation),
    }));
    const updateOps = canaryUniformCases.map((entry, index) => ({
      kind: 'keyframe.update' as const,
      shaderId: assignedShader!.id,
      uniformPath: index % 2 === 0 ? entry.name : `uniforms.${entry.name}`,
      time: 0.5,
      value: entry.updatedValue,
      interpolation: entry.interpolation,
    }));
    const removeKeyframeOps = canaryUniformCases.map((entry, index) => ({
      kind: 'keyframe.remove' as const,
      shaderId: assignedShader!.id,
      uniformPath: index % 2 === 0 ? entry.name : `uniforms.${entry.name}`,
      time: 0.5,
    }));

    const addPreview = applyGraphPreviewOperations({
      snapshot: assignedSnapshot,
      contributionIndex: runtime.contributionIndex,
    }, addOps);
    expect(addPreview?.edges).toEqual(expect.arrayContaining(canaryUniformCases.map((entry) => (
      expect.objectContaining({
        kind: 'animates',
        sourceNodeId: `clip:${assignedClip.id}`,
        targetNodeId: `contribution:shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
        detail: expect.objectContaining({
          targetKind: 'shader-uniform',
          targetPath: `uniforms.${entry.name}`,
          uniformName: entry.name,
          keyframeCount: 1,
          shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
          clipId: assignedClip.id,
        }),
      })
    ))));

    const updatedKeyframes = buildCanaryKeyframes('updatedValue');
    const updatePreview = applyGraphPreviewOperations({
      snapshot: assignedSnapshot,
      contributionIndex: runtime.contributionIndex,
    }, [...addOps, ...updateOps]);
    expect(updatePreview?.edges).toEqual(expect.arrayContaining(canaryUniformCases.map((entry) => (
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: `uniforms.${entry.name}`,
          keyframeCount: 1,
        }),
      })
    ))));

    const keyframedClip = {
      ...assignedClip,
      app: {
        ...assignedClip.app,
        shader: {
          ...assignedClip.app!.shader!,
          keyframes: updatedKeyframes,
        },
      },
    } as ResolvedTimelineClip;
    const roundTrippedSnapshot = await roundTripSnapshot(makeConfig(keyframedClip));
    expect(roundTrippedSnapshot.clips.map((clip) => clip.id)).toEqual([assignedClip.id]);
    expect(roundTrippedSnapshot.shaders).toEqual([
      expect.objectContaining({
        id: `${assignedClip.id}:shader:${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}`,
        clipId: assignedClip.id,
        shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
        keyframes: Object.fromEntries(canaryUniformCases.map((entry) => [
          `uniforms.${entry.name}`,
          [shaderKeyframe(0.5, entry.updatedValue, entry.interpolation)],
        ])),
      }),
    ]);

    const graph = projectCompositionGraph({
      snapshot: roundTrippedSnapshot,
      contributionIndex: runtime.contributionIndex,
    });
    expect(graph.edges).toEqual(expect.arrayContaining(canaryUniformCases.map((entry) => (
      expect.objectContaining({
        kind: 'animates',
        sourceNodeId: `clip:${assignedClip.id}`,
        targetNodeId: `contribution:shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
        detail: expect.objectContaining({
          clipId: assignedClip.id,
          shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
          targetKind: 'shader-uniform',
          targetPath: `uniforms.${entry.name}`,
          uniformName: entry.name,
          keyframeCount: 1,
        }),
      })
    ))));

    const previewSurface = makePreviewSurface();
    createWebGLShaderPreviewSurfaceMock.mockReturnValue(previewSurface);
    render(
      <ClipShaderPreviewCanvas
        shader={keyframedClip.app!.shader!}
        record={record}
        timeSeconds={1.25}
        frame={38}
        width={640}
        height={360}
        testId="canary-clip-keyframed-preview"
      />,
    );

    const resolvedUniformValues = {
      ...assignedClip.app!.shader!.uniforms,
      ...Object.fromEntries(canaryUniformCases.map((entry) => [entry.name, entry.updatedValue])),
    };
    expect(previewSurface.setUniformValues).toHaveBeenLastCalledWith(resolvedUniformValues);

    const removeKeyframePreview = applyGraphPreviewOperations({
      snapshot: assignedSnapshot,
      contributionIndex: runtime.contributionIndex,
    }, [...addOps, ...updateOps, ...removeKeyframeOps]);
    expect(removeKeyframePreview?.edges.some((edge) => (
      edge.kind === 'animates' && edge.detail?.targetKind === 'shader-uniform'
    ))).toBe(false);

    test.dispose();
  });

  it('graph-present planRender uses compositionGraph shader authority and emits legacy warning when graph is absent', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);
    const snapshot = makeShaderSnapshot(clip);
    const runtime = normalizeExtensionRuntime([test.extension]);

    // Graph-present: planRender derives shader facts from the compositionGraph.
    const plannerWithGraph = planRender({ snapshot, extensionRuntime: runtime });

    // The graph-present planner still reports the missing-material blocker
    // because the canary shader has no export materializer — this is derived
    // from graph edges, not legacy snapshot shader fields.
    expect(plannerWithGraph.canBrowserExport).toBe(false);
    expect(plannerWithGraph.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export', reason: 'missing-material',
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      }),
    ]));

    // Legacy (graph-absent): planRender falls back to snapshot shader metadata
    // and emits a compatibility warning.
    const plannerWithoutGraph = planRender({ snapshot });
    expect(plannerWithoutGraph.canBrowserExport).toBe(false);
    expect(plannerWithoutGraph.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export', reason: 'missing-material',
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      }),
    ]));

    // The legacy path should include a compatibility warning finding
    const legacyWarning = plannerWithoutGraph.findings.find(
      (finding) => finding.id.startsWith('planner.compositionGraph.legacy'),
    );
    expect(legacyWarning).toBeDefined();
    expect(legacyWarning?.severity).toBe('warning');

    test.dispose();
  });

  it('keeps graph node kinds scoped while projecting animates and binds-live edges for shader timelines', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const runtime = normalizeExtensionRuntime([test.extension]);
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);
    const snapshot = makeGraphCoverageSnapshot(clip);
    const graph = projectCompositionGraph({
      snapshot,
      contributionIndex: runtime.contributionIndex,
    });
    expect(graph).toBeDefined();

    const kinds = new Set(graph.nodes.map((node) => node.kind));
    expect(kinds.has('clip')).toBe(true);
    expect(kinds.has('timeline-postprocess')).toBe(true);
    expect(kinds.has('contribution')).toBe(true);
    expect(kinds.has('track')).toBe(false);
    expect(kinds.has('output')).toBe(false);
    expect(kinds.has('process')).toBe(false);

    const edgeKinds = new Set(graph.edges.map((edge) => edge.kind));
    expect(edgeKinds.has('consumes')).toBe(true);
    expect(edgeKinds.has('animates')).toBe(true);
    expect(edgeKinds.has('binds-live')).toBe(true);
    expect(edgeKinds.size).toBe(3);

    const planner = planRender({
      snapshot,
      compositionGraph: graph,
      shaders: runtime.shaders,
    });
    expect(planner.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      }),
    ]));

    const states = new Set(graph.referenceStates.map((entry) => entry.state));
    for (const state of states) {
      expect([
        'resolved', 'missing', 'disabled', 'inactive-reserved',
        'invalid-package', 'duplicate', 'settings-error', 'runtime-error',
        'version-incompatible', 'unknown',
      ]).toContain(state);
    }

    const targetKinds = new Set(
      graph.edges
        .map((edge) => edge.detail?.targetKind)
        .filter((value): value is string => typeof value === 'string'),
    );
    for (const targetKind of targetKinds) {
      expect(['clip-param', 'effect-param', 'transition-param', 'shader-uniform']).toContain(targetKind);
    }

    test.dispose();
  });

  it('emits MISSING_REF diagnostics for shaders whose contribution ref is absent from the contribution index', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);
    const snapshot = makeShaderSnapshot(clip);

    // Empty contribution index means the shader contribution ref resolves as missing
    const emptyIndex: ContributionIndex = {
      entries: [],
      byExtensionId: new Map(),
      byContributionId: new Map(),
    };

    const graph = projectCompositionGraph({
      snapshot,
      contributionIndex: emptyIndex,
    });

    // Verify MISSING_REF diagnostic for the shader contribution ref
    const missingDiag = graph.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF,
    );
    expect(missingDiag).toBeDefined();
    expect(missingDiag!.severity).toBe('warning');
    expect(missingDiag!.detail).toEqual(expect.objectContaining({
      refKey: `shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
      refState: 'missing',
      extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
    }));

    // Reference states include the missing entry
    const missingRefState = graph.referenceStates.find(
      (entry) => entry.refKey === `shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID}`,
    );
    expect(missingRefState).toBeDefined();
    expect(missingRefState!.state).toBe('missing');
    expect(missingRefState!.nodeIds).toContain(`clip:${clip.id}`);

    // The consumes edge still exists for the non-resolved ref
    const consumesEdge = graph.edges.find(
      (edge) => edge.kind === 'consumes'
        && edge.detail?.shaderId === CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
    );
    expect(consumesEdge).toBeDefined();

    test.dispose();
  });

  it('emits DISABLED_REF diagnostics for a shader that is in error state (diagnostic shader)', () => {
    const test = activateCanary({ includeDiagnosticShader: true });
    const runtime = normalizeExtensionRuntime([test.extension]);

    // The diagnostic shader enters 'error' status due to unsupported uniform
    const diagnosticRecord = test.snapshot.get(
      CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
    );
    expect(diagnosticRecord).toBeDefined();
    expect(diagnosticRecord!.status).toBe('error');

    const clip: ResolvedTimelineClip = {
      id: 'clip-diag',
      track: 'V1',
      at: 0,
      hold: 60,
      clipType: 'media',
      app: {
        shader: {
          scope: 'clip',
          shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
          extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
          contributionId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
          enabled: true,
          uniforms: {},
          textures: {},
        },
      },
    } as ResolvedTimelineClip;

    const snapshot: TimelineSnapshot = {
      projectId: 'project-diag',
      baseVersion: 1,
      currentVersion: 1,
      extensionRequirements: [],
      clips: [{
        id: clip.id,
        track: clip.track,
        at: clip.at,
        duration: clip.hold ?? 60,
        clipType: clip.clipType ?? 'media',
        managed: false,
      }],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
      assetKeys: [],
      app: {},
      shaders: [{
        id: `${clip.id}:shader:${CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID}`,
        shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
        scope: 'clip',
        clipId: clip.id,
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
        enabled: true,
      }],
      outputMetadata: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
    };

    const graph = projectCompositionGraph({
      snapshot,
      contributionIndex: runtime.contributionIndex,
    });

    // The contribution ref for the diagnostic shader should be in a non-resolved state
    const diagRefState = graph.referenceStates.find(
      (entry) => entry.refKey === `shader:${CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID}:${CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID}`,
    );
    expect(diagRefState).toBeDefined();
    // The diagnostic shader has an unsupported uniform so it's in runtime-error or disabled state
    expect(['runtime-error', 'disabled', 'settings-error']).toContain(diagRefState!.state);

    // Verify a non-resolved diagnostic exists for the diagnostic shader's ref
    const nonResolvedDiags = graph.diagnostics.filter(
      (d) => d.detail?.contributionId === CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID
        && d.code !== 'composition/resolved',
    );
    expect(nonResolvedDiags.length).toBeGreaterThan(0);

    test.dispose();
  });

  it('rejects a different shader assigned to an occupied clip scope with a DUPLICATE_SCOPE diagnostic through graph-owned operations', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const runtime = normalizeExtensionRuntime([test.extension]);
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);
    const snapshot = makeShaderSnapshot(clip);

    // Create a second shader assignment (different shader) targeting the same clip scope
    const secondShader: TimelineShaderSummary = {
      id: `${clip.id}:shader:shader.alt`,
      shaderId: 'shader.alt',
      scope: 'clip',
      clipId: clip.id,
      extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: 'alt-contribution',
      enabled: true,
    };

    const assignOps = [{
      kind: 'shader.assign' as const,
      shader: secondShader,
    }];

    const preview = applyGraphPreviewOperations({
      snapshot,
      contributionIndex: runtime.contributionIndex,
    }, assignOps);

    expect(preview).toBeDefined();

    // Verify DUPLICATE_SCOPE diagnostic
    const duplicateDiag = preview!.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_SCOPE,
    );
    expect(duplicateDiag).toBeDefined();
    expect(duplicateDiag!.severity).toBe('error');
    expect(duplicateDiag!.detail).toEqual(expect.objectContaining({
      scope: 'clip',
      clipId: clip.id,
      extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
      contributionId: 'alt-contribution',
      shaderId: 'shader.alt',
    }));

    // The original shader should still be the only one
    expect(preview!.snapshot.shaders).toHaveLength(1);
    expect(preview!.snapshot.shaders?.[0]?.shaderId).toBe(CLIP_LOCAL_SHADER_CANARY_SHADER_ID);

    test.dispose();
  });

  it('projects animates edges with accurate multi-keyframe counts and canonical target paths for non-canonical input', async () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);

    // Build a snapshot with 3 keyframes on intensity and non-canonical paths
    const keyframedClip = {
      ...clip,
      app: {
        ...clip.app,
        shader: {
          ...clip.app!.shader!,
          keyframes: {
            'intensity': [
              shaderKeyframe(0, 0.1, 'linear'),
              shaderKeyframe(1, 0.5, 'linear'),
              shaderKeyframe(2, 1.0, 'hold'),
            ],
            // Non-canonical path (no uniforms. prefix) should normalize
            'tint': [
              shaderKeyframe(0.5, [0.2, 0.4, 0.8, 1], 'linear'),
            ],
            'uniforms.center': [
              shaderKeyframe(0, [0, 0], 'linear'),
              shaderKeyframe(1, [1, 1], 'linear'),
            ],
          },
        },
      },
    } as ResolvedTimelineClip;

    const roundTrippedSnapshot = await roundTripSnapshot(makeConfig(keyframedClip));
    const runtime = normalizeExtensionRuntime([test.extension]);

    const graph = projectCompositionGraph({
      snapshot: roundTrippedSnapshot,
      contributionIndex: runtime.contributionIndex,
    });

    // Verify intensity has 3 keyframes
    const intensityEdge = graph.edges.find(
      (edge) => edge.kind === 'animates'
        && edge.detail?.targetKind === 'shader-uniform'
        && edge.detail?.uniformName === 'intensity',
    );
    expect(intensityEdge).toBeDefined();
    expect(intensityEdge!.detail?.keyframeCount).toBe(3);
    expect(intensityEdge!.detail?.targetPath).toBe('uniforms.intensity');

    // Verify center has 2 keyframes
    const centerEdge = graph.edges.find(
      (edge) => edge.kind === 'animates'
        && edge.detail?.targetKind === 'shader-uniform'
        && edge.detail?.uniformName === 'center',
    );
    expect(centerEdge).toBeDefined();
    expect(centerEdge!.detail?.keyframeCount).toBe(2);
    expect(centerEdge!.detail?.targetPath).toBe('uniforms.center');

    // Verify tint (non-canonical input path) was normalized to uniforms.tint
    const tintEdge = graph.edges.find(
      (edge) => edge.kind === 'animates'
        && edge.detail?.targetKind === 'shader-uniform'
        && edge.detail?.uniformName === 'tint',
    );
    expect(tintEdge).toBeDefined();
    expect(tintEdge!.detail?.targetPath).toBe('uniforms.tint');
    expect(tintEdge!.detail?.keyframeCount).toBe(1);

    test.dispose();
  });

  it('emits clip-type MISSING_REF diagnostics with nextAction detail when a clip type is absent from the registry', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);

    // Use a clipType that doesn't exist in the registry
    const snapshot: TimelineSnapshot = {
      projectId: 'project-ct-missing',
      baseVersion: 1,
      currentVersion: 1,
      extensionRequirements: [],
      clips: [{
        id: clip.id,
        track: clip.track,
        at: clip.at,
        duration: clip.hold ?? 60,
        clipType: 'com.example.nonexistent',
        managed: false,
      }],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
      assetKeys: [],
      app: {},
      shaders: [{
        id: `${clip.id}:shader:${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}`,
        shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
        scope: 'clip',
        clipId: clip.id,
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
        enabled: true,
      }],
      outputMetadata: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
    };

    const runtime = normalizeExtensionRuntime([test.extension]);

    // Empty clip-type registry (no records)
    const emptyClipTypeRegistry: ClipTypeRegistrySnapshot = {
      records: [],
      diagnostics: [],
      get: () => undefined,
      has: () => false,
    };

    const graph = projectCompositionGraph({
      snapshot,
      contributionIndex: runtime.contributionIndex,
      clipTypeRegistry: emptyClipTypeRegistry,
    });

    // Verify MISSING_REF diagnostic for the clip type
    const missingDiag = graph.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF
        && d.detail?.refKey?.startsWith('clipType:'),
    );
    expect(missingDiag).toBeDefined();
    expect(missingDiag!.severity).toBe('warning');
    expect(missingDiag!.detail).toEqual(expect.objectContaining({
      refState: 'missing',
      clipId: clip.id,
    }));

    // Verify ref state entry exists for the missing clip type
    const ctRefState = graph.referenceStates.find(
      (entry) => entry.refKey.startsWith('clipType:'),
    );
    expect(ctRefState).toBeDefined();
    expect(ctRefState!.state).toBe('missing');
    expect(ctRefState!.nodeIds).toContain(`clip:${clip.id}`);

    test.dispose();
  });

  it('emits clip-type DISABLED_REF diagnostics with nextAction detail when a clip type has renderability blockers', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const clip = makeClip(record);

    const blockedClipTypeId = 'com.example.blocked-type';
    const snapshot: TimelineSnapshot = {
      projectId: 'project-ct-blocked',
      baseVersion: 1,
      currentVersion: 1,
      extensionRequirements: [],
      clips: [{
        id: clip.id,
        track: clip.track,
        at: clip.at,
        duration: clip.hold ?? 60,
        clipType: blockedClipTypeId,
        managed: false,
      }],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
      assetKeys: [],
      app: {},
      shaders: [{
        id: `${clip.id}:shader:${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}`,
        shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
        scope: 'clip',
        clipId: clip.id,
        extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
        contributionId: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID,
        enabled: true,
      }],
      outputMetadata: { resolution: '1280x720', fps: 30, file: 'out.mp4' },
    };

    const runtime = normalizeExtensionRuntime([test.extension]);

    // Build a clip-type registry with a record that has renderability blockers
    const blockedRegistry: ClipTypeRegistrySnapshot = {
      records: [{
        clipTypeId: blockedClipTypeId,
        contributionId: 'blocked-ct-contrib',
        renderer: {},
        renderability: {
          capabilities: [],
          determinism: 'preview-only' as any,
          blockers: [{
            id: 'ct-blocker-1',
            severity: 'error' as const,
            reason: 'missing-material' as any,
            message: 'Clip type is missing a required materializer.',
            route: 'browser-export' as any,
          }],
        },
        status: 'active',
        ownerExtensionId: 'com.example.blocked-ext',
      }],
      diagnostics: [],
      get: (ctId: string) => ctId === blockedClipTypeId
        ? blockedRegistry.records[0]
        : undefined,
      has: (ctId: string) => ctId === blockedClipTypeId,
    };

    const graph = projectCompositionGraph({
      snapshot,
      contributionIndex: runtime.contributionIndex,
      clipTypeRegistry: blockedRegistry,
    });

    // Verify DISABLED_REF diagnostic with nextAction for the blocked clip type
    const disabledDiag = graph.diagnostics.find(
      (d) => d.code === COMPOSITION_DIAGNOSTIC_CODE.DISABLED_REF
        && d.detail?.refKey?.startsWith('clipType:'),
    );
    expect(disabledDiag).toBeDefined();
    expect(disabledDiag!.severity).toBe('error');
    expect(disabledDiag!.detail).toEqual(expect.objectContaining({
      refState: 'disabled',
    }));
    expect(disabledDiag!.detail?.nextAction).toBeDefined();
    expect(disabledDiag!.detail!.nextAction).toEqual(expect.objectContaining({
      kind: 'resolve-blockers',
      blockers: expect.arrayContaining([
        expect.objectContaining({
          reason: 'missing-material',
        }),
      ]),
    }));

    // Verify reference state entry
    const ctRefState = graph.referenceStates.find(
      (entry) => entry.refKey.startsWith('clipType:'),
    );
    expect(ctRefState).toBeDefined();
    expect(ctRefState!.state).toBe('disabled');

    test.dispose();
  });
});
