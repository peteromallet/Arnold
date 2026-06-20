// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createExtensionContext,
  type ExtensionDiagnostic,
  type ExtensionDiagnosticsService,
  type ReighExtension,
  type TimelineSnapshot,
} from '@/sdk/index';
import {
  POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID,
  POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
  POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
  POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
  POSTPROCESS_SHADER_CANARY_SHADER_ID,
  createPostprocessShaderCanaryExtension,
  type PostprocessShaderCanaryController,
} from '@/tools/video-editor/examples/extensions/postprocess-shader-canary';
import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
import type {
  ShaderEffectRegistry,
  ShaderEffectRegistryRecord,
  ShaderEffectRegistrySnapshot,
} from '@/tools/video-editor/shaders/registry/types.ts';
import { createTimelinePostprocessShaderMetadata } from '@/tools/video-editor/lib/shader-catalog.ts';
import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
import { ShaderInspector } from '@/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

const VERTEX_SHADER = 0x8B31;
const FRAGMENT_SHADER = 0x8B30;
const COMPILE_STATUS = 0x8B81;
const LINK_STATUS = 0x8B82;
const ARRAY_BUFFER = 0x8892;
const STATIC_DRAW = 0x88E4;
const FLOAT = 0x1406;
const TRIANGLES = 0x0004;
const FRAMEBUFFER = 0x8D40;
const COLOR_BUFFER_BIT = 0x4000;
const RGBA = 0x1908;
const UNSIGNED_BYTE = 0x1401;
const TEXTURE_2D = 0x0DE1;
const TEXTURE0 = 0x84C0;
const TEXTURE_MIN_FILTER = 0x2801;
const TEXTURE_MAG_FILTER = 0x2800;
const TEXTURE_WRAP_S = 0x2802;
const TEXTURE_WRAP_T = 0x2803;
const LINEAR = 0x2601;
const CLAMP_TO_EDGE = 0x812F;

interface MockShader {
  readonly id: number;
  readonly type: number;
}

interface MockProgram {
  readonly id: number;
}

interface MockBuffer {
  readonly id: number;
}

interface MockTexture {
  readonly id: number;
}

interface MockUniformLocation {
  readonly name: string;
}

interface MockWebGLState {
  readonly uniformValues: Map<string, unknown>;
  readonly pixels: Uint8Array;
  viewport: readonly [number, number, number, number];
}

function makeDiagnosticsService(extensionId = POSTPROCESS_SHADER_CANARY_EXTENSION_ID): ExtensionDiagnosticsService {
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

function createMockWebGL(): WebGLRenderingContext & { readonly __state: MockWebGLState } {
  let nextShaderId = 1;
  let nextProgramId = 1;
  let nextBufferId = 1;
  let nextTextureId = 1;
  const state: MockWebGLState = {
    uniformValues: new Map<string, unknown>(),
    pixels: new Uint8Array([0, 0, 0, 255]),
    viewport: [0, 0, 0, 0],
  };

  const gl = {
    __state: state,
    VERTEX_SHADER,
    FRAGMENT_SHADER,
    COMPILE_STATUS,
    LINK_STATUS,
    ARRAY_BUFFER,
    STATIC_DRAW,
    FLOAT,
    TRIANGLES,
    FRAMEBUFFER,
    COLOR_BUFFER_BIT,
    RGBA,
    UNSIGNED_BYTE,
    TEXTURE_2D,
    TEXTURE0,
    TEXTURE_MIN_FILTER,
    TEXTURE_MAG_FILTER,
    TEXTURE_WRAP_S,
    TEXTURE_WRAP_T,
    LINEAR,
    NEAREST: LINEAR,
    CLAMP_TO_EDGE,
    REPEAT: CLAMP_TO_EDGE,
    MIRRORED_REPEAT: CLAMP_TO_EDGE,
    createShader: vi.fn((type: number): MockShader => ({ id: nextShaderId++, type })),
    shaderSource: vi.fn(),
    compileShader: vi.fn(),
    getShaderParameter: vi.fn((_shader: MockShader, parameter: number): boolean => parameter === COMPILE_STATUS),
    getShaderInfoLog: vi.fn((): string => ''),
    deleteShader: vi.fn(),
    createProgram: vi.fn((): MockProgram => ({ id: nextProgramId++ })),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    getProgramParameter: vi.fn((_program: MockProgram, parameter: number): boolean => parameter === LINK_STATUS),
    getProgramInfoLog: vi.fn((): string => ''),
    deleteProgram: vi.fn(),
    createBuffer: vi.fn((): MockBuffer => ({ id: nextBufferId++ })),
    bindBuffer: vi.fn(),
    bufferData: vi.fn(),
    getAttribLocation: vi.fn((_program: MockProgram, name: string): number => (name === 'a_position' ? 0 : -1)),
    enableVertexAttribArray: vi.fn(),
    vertexAttribPointer: vi.fn(),
    getUniformLocation: vi.fn((_program: MockProgram, name: string): MockUniformLocation => ({ name })),
    createTexture: vi.fn((): MockTexture => ({ id: nextTextureId++ })),
    activeTexture: vi.fn(),
    bindTexture: vi.fn(),
    texParameteri: vi.fn(),
    texImage2D: vi.fn(),
    uniform1f: vi.fn((location: MockUniformLocation, value: number): void => {
      state.uniformValues.set(location.name, value);
    }),
    uniform1i: vi.fn((location: MockUniformLocation, value: number): void => {
      state.uniformValues.set(location.name, value);
    }),
    uniform2f: vi.fn((location: MockUniformLocation, x: number, y: number): void => {
      state.uniformValues.set(location.name, [x, y]);
    }),
    uniform3f: vi.fn((location: MockUniformLocation, x: number, y: number, z: number): void => {
      state.uniformValues.set(location.name, [x, y, z]);
    }),
    uniform4f: vi.fn((location: MockUniformLocation, x: number, y: number, z: number, w: number): void => {
      state.uniformValues.set(location.name, [x, y, z, w]);
    }),
    viewport: vi.fn((x: number, y: number, width: number, height: number): void => {
      state.viewport = [x, y, width, height];
    }),
    bindFramebuffer: vi.fn(),
    useProgram: vi.fn(),
    clearColor: vi.fn(),
    clear: vi.fn(),
    drawArrays: vi.fn((): void => {
      const resolution = state.uniformValues.get('u_resolution') as readonly number[] | undefined;
      const frame = state.uniformValues.get('u_frame') as number | undefined;
      const intensity = state.uniformValues.get('intensity') as number | undefined;
      state.pixels[0] = resolution?.[0] ?? 0;
      state.pixels[1] = resolution?.[1] ?? 0;
      state.pixels[2] = Math.floor((frame ?? 0) + (intensity ?? 0) * 100);
      state.pixels[3] = 255;
    }),
    readPixels: vi.fn((
      _x: number,
      _y: number,
      _width: number,
      _height: number,
      _format: number,
      _type: number,
      pixels: Uint8Array,
    ): void => {
      pixels.set(state.pixels);
    }),
    deleteBuffer: vi.fn(),
    deleteTexture: vi.fn(),
  };

  return gl as unknown as WebGLRenderingContext & { readonly __state: MockWebGLState };
}

function activateCanary(options: {
  includeDiagnosticShader?: boolean;
} = {}): {
  extension: ReighExtension;
  registry: ShaderEffectRegistry;
  snapshot: ShaderEffectRegistrySnapshot;
  diagnosticsService: ExtensionDiagnosticsService;
  controller: PostprocessShaderCanaryController;
  dispose: () => void;
} {
  const extension = createPostprocessShaderCanaryExtension({
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
  const controller = handle as PostprocessShaderCanaryController;

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
  const record = snapshot.get(POSTPROCESS_SHADER_CANARY_SHADER_ID, POSTPROCESS_SHADER_CANARY_EXTENSION_ID);
  expect(record).toBeDefined();
  return record!;
}

function makeConfig(record: ShaderEffectRegistryRecord): ResolvedTimelineConfig {
  return {
    output: { resolution: '320x180', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{
      id: 'clip-base',
      track: 'V1',
      at: 0,
      hold: 60,
      clipType: 'media',
    }],
    app: {
      shaderPostprocess: createTimelinePostprocessShaderMetadata(record),
    },
    registry: {},
  } as ResolvedTimelineConfig;
}

function makeShaderSnapshot(config: ResolvedTimelineConfig): TimelineSnapshot {
  const shader = config.app?.shaderPostprocess!;
  return {
    projectId: 'project-postprocess-shader-canary',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [{
      id: 'clip-base',
      track: 'V1',
      at: 0,
      duration: 60,
      clipType: 'media',
      managed: false,
    }],
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
    assetKeys: [],
    app: {},
    shaders: [{
      id: `postprocess:shader:${shader.shaderId}`,
      shaderId: shader.shaderId,
      scope: 'postprocess',
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
      enabled: shader.enabled !== false,
    }],
    outputMetadata: { resolution: '320x180', fps: 30, file: 'out.mp4' },
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('postprocess-shader-canary extension', () => {
  it('registers through the public shader SDK path and exposes runtime, diagnostics, and renderability contracts', () => {
    const test = activateCanary();
    const runtime = normalizeExtensionRuntime([test.extension]);
    const record = requireCanaryRecord(test.snapshot);
    const diagnosticRecord = test.snapshot.get(
      POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
    );

    expect(runtime.shaders.map((shader) => shader.id)).toEqual([
      POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID,
      POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID,
    ]);
    expect(runtime.effects.some((effect) => effect.id === POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID)).toBe(false);

    expect(record).toMatchObject({
      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
      ownerExtensionId: POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
      contributionId: POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID,
      status: 'active',
      source: { kind: 'inline' },
      pass: { kind: 'postprocess', inputTextureUniform: 'u_composite' },
    });
    expect(record.uniforms?.map((uniform) => uniform.type)).toEqual([
      'float',
      'color',
      'vec3',
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
        name: 'u_composite',
        sourceKind: 'clip-frame',
        required: false,
      }),
    ]);
    expect(record.renderability.capabilities).toEqual(expect.arrayContaining([
      expect.objectContaining({ route: 'preview', status: 'supported' }),
      expect.objectContaining({ route: 'browser-export', status: 'blocked', blockerReason: 'missing-material' }),
      expect.objectContaining({ route: 'worker-export', status: 'blocked', blockerReason: 'missing-material' }),
    ]));

    expect(diagnosticRecord).toMatchObject({
      shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
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
        detail: expect.objectContaining({ shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID }),
      }),
      expect.objectContaining({
        severity: 'error',
        code: 'shader/uniform-unsupported',
        detail: expect.objectContaining({ shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID }),
      }),
    ]));

    test.dispose();
  });

  it('materializes timeline metadata, inspector edits, deterministic browser preview output, and planner export blockers', () => {
    const gl = createMockWebGL();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((contextId: string) => (
      contextId === 'webgl2' || contextId === 'webgl' || contextId === 'experimental-webgl'
        ? gl
        : null
    ) as RenderingContext | null);

    const test = activateCanary({ includeDiagnosticShader: false });
    const record = requireCanaryRecord(test.snapshot);
    const config = makeConfig(record);
    const shader = config.app!.shaderPostprocess!;
    const applyEdit = vi.fn();

    expect(shader).toEqual(expect.objectContaining({
      scope: 'postprocess',
      extensionId: POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
      contributionId: POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID,
      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
      uniforms: expect.objectContaining({
        intensity: 0.42,
        tint: [1, 0.45, 0.2, 1],
        lift: [0.15, 0.25, 0.45],
        center: [0.5, 0.5],
        showScanlines: true,
        bandCount: 6,
        holdFrame: 9,
        holdTime: 0.2,
        blendMode: 'screen',
      }),
      textures: {
        u_composite: { kind: 'clip-frame' },
      },
    }));

    render(
      <ShaderInspector
        resolvedConfig={config}
        postprocessShader={shader}
        applyEdit={applyEdit}
        shaderSnapshot={test.snapshot}
      />,
    );
    fireEvent.change(screen.getByTestId('schema-form-widget-intensity'), {
      target: { value: '0.73' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));

    expect(applyEdit).toHaveBeenCalledTimes(1);
    expect(applyEdit.mock.calls[0][0].resolvedConfig.app.shaderPostprocess).toEqual(expect.objectContaining({
      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
      uniforms: expect.objectContaining({ intensity: 0.73 }),
      textures: { u_composite: { kind: 'clip-frame' } },
      metadata: expect.objectContaining({ uniformPreset: 'custom' }),
    }));
    cleanup();

    const preview = render(
      <PostprocessShaderPreviewCanvas
        shader={shader}
        record={record}
        timeSeconds={1.5}
        frame={45}
        width={320}
        height={180}
        testId="canary-postprocess-preview"
      />,
    );

    expect(screen.getByTestId('canary-postprocess-preview')).toHaveAttribute(
      'data-shader-scope',
      'postprocess',
    );
    expect(screen.getByTestId('canary-postprocess-preview')).toHaveAttribute(
      'data-shader-id',
      POSTPROCESS_SHADER_CANARY_SHADER_ID,
    );
    expect(gl.__state.uniformValues.get('u_resolution')).toEqual([320, 180]);
    expect(gl.__state.uniformValues.get('u_time')).toBe(1.5);
    expect(gl.__state.uniformValues.get('u_frame')).toBe(45);
    expect(gl.__state.uniformValues.get('intensity')).toBe(0.42);

    const firstPixels = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, RGBA, UNSIGNED_BYTE, firstPixels);
    expect([...firstPixels]).toEqual([64, 180, 87, 255]);

    preview.rerender(
      <PostprocessShaderPreviewCanvas
        shader={{ ...shader, uniforms: { ...shader.uniforms, intensity: 0.1 } }}
        record={record}
        timeSeconds={2}
        frame={60}
        width={128}
        height={72}
        testId="canary-postprocess-preview-next"
      />,
    );

    const secondPixels = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, RGBA, UNSIGNED_BYTE, secondPixels);
    expect([...secondPixels]).toEqual([128, 72, 70, 255]);
    cleanup();

    const planner = planRender({ snapshot: makeShaderSnapshot(config) });
    expect(planner.canBrowserExport).toBe(false);
    expect(planner.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        extensionId: POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
        contributionId: POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID,
        message: `Shader "${POSTPROCESS_SHADER_CANARY_SHADER_ID}" cannot export because no shader materializer produced RenderMaterial for postprocess.`,
      }),
    ]));

    test.dispose();
  });
});
