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
import { ClipShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx';
import { ShaderInspector } from '@/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types/index.ts';

const createWebGLShaderPreviewSurfaceMock = vi.hoisted(() => vi.fn());

vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
  createWebGLShaderPreviewSurface: createWebGLShaderPreviewSurfaceMock,
}));

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

  it('graph authority does not leak future surface kinds and keeps checks scoped to M1b shader/ref consumes edges', () => {
    const test = activateCanary({ includeDiagnosticShader: false });
    const runtime = normalizeExtensionRuntime([test.extension]);
    const graph = runtime.compositionGraph;
    expect(graph).toBeDefined();

    // Only M1b node kinds are present
    const kinds = new Set(graph.nodes.map((node) => node.kind));
    expect(kinds.has('clip')).toBe(true);
    expect(kinds.has('timeline-postprocess')).toBe(true);
    expect(kinds.has('contribution')).toBe(true);
    expect(kinds.has('track')).toBe(false);
    expect(kinds.has('output')).toBe(false);
    expect(kinds.has('process')).toBe(false);

    // Only consumes edges
    const edgeKinds = new Set(graph.edges.map((edge) => edge.kind));
    expect(edgeKinds.has('consumes')).toBe(true);
    expect(edgeKinds.size).toBeLessThanOrEqual(1);
    expect(edgeKinds.has('animates')).toBe(false);
    expect(edgeKinds.has('binds-live')).toBe(false);

    // Reference states only use the 10 M1b states
    const states = new Set(graph.referenceStates.map((entry) => entry.state));
    for (const state of states) {
      expect([
        'resolved', 'missing', 'disabled', 'inactive-reserved',
        'invalid-package', 'duplicate', 'settings-error', 'runtime-error',
        'version-incompatible', 'unknown',
      ]).toContain(state);
    }

    test.dispose();
  });
});
