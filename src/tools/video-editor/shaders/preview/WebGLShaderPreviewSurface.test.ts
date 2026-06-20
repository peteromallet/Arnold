import { describe, expect, it, vi } from 'vitest';
import type { ShaderUniformSchema } from '@reigh/editor-sdk';
import { createWebGLShaderPreviewSurface } from '@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts';

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
const NEAREST = 0x2600;
const LINEAR = 0x2601;
const CLAMP_TO_EDGE = 0x812F;
const REPEAT = 0x2901;
const MIRRORED_REPEAT = 0x8370;

const CONTEXT = {
  shaderId: 'shader.preview.grade',
  extensionId: 'com.example.shader',
  contributionId: 'preview-grade',
};

const FRAGMENT_SOURCE = [
  'precision mediump float;',
  'uniform vec2 u_resolution;',
  'uniform float u_time;',
  'uniform int u_frame;',
  'uniform float intensity;',
  'uniform int passes;',
  'uniform bool enabled;',
  'uniform vec2 offset;',
  'uniform vec3 axis;',
  'uniform vec4 tint;',
  'uniform int mode;',
  'uniform sampler2D ignoredTexture;',
  'void main() {',
  '  gl_FragColor = vec4(tint.rgb * intensity, tint.a);',
  '}',
].join('\n');

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
  readonly textureUploads: unknown[];
  viewport: readonly [number, number, number, number];
}

type MockCanvas = HTMLCanvasElement & {
  __dispatchWebGLEvent(type: 'webglcontextlost' | 'webglcontextrestored', event?: Partial<Event>): Partial<Event>;
  __setWebGLContext(gl: WebGLRenderingContext): void;
};

function createMockCanvas(gl: WebGLRenderingContext): MockCanvas {
  let currentContext = gl;
  const listeners = new Map<string, Set<EventListener>>();
  return {
    width: 0,
    height: 0,
    getContext: vi.fn((contextId: string) => (contextId === 'webgl2' ? currentContext : null)),
    addEventListener: vi.fn((type: string, listener: EventListener): void => {
      listeners.set(type, listeners.get(type) ?? new Set());
      listeners.get(type)!.add(listener);
    }),
    removeEventListener: vi.fn((type: string, listener: EventListener): void => {
      listeners.get(type)?.delete(listener);
    }),
    __dispatchWebGLEvent(type: 'webglcontextlost' | 'webglcontextrestored', event: Partial<Event> = {}) {
      for (const listener of listeners.get(type) ?? []) {
        listener(event as Event);
      }
      return event;
    },
    __setWebGLContext(nextContext: WebGLRenderingContext): void {
      currentContext = nextContext;
    },
  } as unknown as MockCanvas;
}

function createMockWebGL(options: {
  readonly fragmentCompile?: boolean;
  readonly fragmentInfoLog?: string;
  readonly link?: boolean;
} = {}): WebGLRenderingContext & { readonly __state: MockWebGLState } {
  const fragmentCompile = options.fragmentCompile ?? true;
  const link = options.link ?? true;
  let nextShaderId = 1;
  let nextProgramId = 1;
  let nextBufferId = 1;
  let nextTextureId = 1;

  const state: MockWebGLState = {
    uniformValues: new Map<string, unknown>(),
    textureUploads: [],
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
    NEAREST,
    LINEAR,
    CLAMP_TO_EDGE,
    REPEAT,
    MIRRORED_REPEAT,
    createShader: vi.fn((type: number): MockShader => ({ id: nextShaderId++, type })),
    shaderSource: vi.fn(),
    compileShader: vi.fn(),
    getShaderParameter: vi.fn((shader: MockShader, parameter: number): boolean => (
      parameter === COMPILE_STATUS && (shader.type === VERTEX_SHADER || fragmentCompile)
    )),
    getShaderInfoLog: vi.fn((shader: MockShader): string => (
      shader.type === FRAGMENT_SHADER ? options.fragmentInfoLog ?? '' : ''
    )),
    deleteShader: vi.fn(),
    createProgram: vi.fn((): MockProgram => ({ id: nextProgramId++ })),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    getProgramParameter: vi.fn((_program: MockProgram, parameter: number): boolean => (
      parameter === LINK_STATUS ? link : false
    )),
    getProgramInfoLog: vi.fn((): string => 'ERROR: program link failed'),
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
    texImage2D: vi.fn((
      _target: number,
      _level: number,
      _internalformat: number,
      _format: number,
      _type: number,
      source: unknown,
    ): void => {
      state.textureUploads.push(source);
    }),
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
    drawArrays: vi.fn(),
    readPixels: vi.fn((
      _x: number,
      _y: number,
      _width: number,
      _height: number,
      _format: number,
      _type: number,
      pixels: Uint8Array,
    ): void => {
      const resolution = state.uniformValues.get('u_resolution') as readonly number[] | undefined;
      const frame = state.uniformValues.get('u_frame') as number | undefined;
      pixels[0] = resolution?.[0] ?? 0;
      pixels[1] = resolution?.[1] ?? 0;
      pixels[2] = frame ?? 0;
      pixels[3] = 255;
    }),
    deleteBuffer: vi.fn(),
    deleteTexture: vi.fn(),
  };

  return gl as unknown as WebGLRenderingContext & { readonly __state: MockWebGLState };
}

function createUniformSchema(): ShaderUniformSchema {
  return Object.freeze([
    { name: 'intensity', label: 'Intensity', type: 'float', default: 0.5 },
    { name: 'passes', label: 'Passes', type: 'int', default: 2 },
    { name: 'enabled', label: 'Enabled', type: 'bool', default: false },
    { name: 'offset', label: 'Offset', type: 'vec2', default: [0.1, 0.2] },
    { name: 'axis', label: 'Axis', type: 'vec3', default: [0, 1, 0] },
    { name: 'tint', label: 'Tint', type: 'color', default: [1, 0.5, 0.25, 1] },
    {
      name: 'mode',
      label: 'Mode',
      type: 'enum',
      default: 'screen',
      options: [
        { label: 'Normal', value: 'normal' },
        { label: 'Screen', value: 'screen' },
      ],
    },
    { name: 'ignoredTexture', label: 'Texture', type: 'textureRef', default: { kind: 'clip-frame' } },
  ]);
}

describe('WebGLShaderPreviewSurface', () => {
  it('sets up a deterministic canvas-backed WebGL program and uploads uniforms during renderFrame', () => {
    const gl = createMockWebGL();
    const canvas = createMockCanvas(gl);
    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;

    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas,
      fragmentSource: FRAGMENT_SOURCE,
      uniforms: createUniformSchema(),
      textureSources: { clipFrame: clipFrameSource },
      uniformValues: {
        intensity: 0.75,
        enabled: true,
        offset: [0.3, 0.4],
        tint: [0.2, 0.3, 0.4, 0.5],
        mode: 'normal',
      },
      width: 320.8,
      height: 180.2,
    });

    expect(surface.status).toBe('ready');
    expect(canvas.width).toBe(320);
    expect(canvas.height).toBe(180);
    expect(canvas.getContext).toHaveBeenCalledWith('webgl2', expect.objectContaining({
      antialias: false,
      depth: false,
      preserveDrawingBuffer: true,
      stencil: false,
    }));
    expect(gl.bufferData).toHaveBeenCalledWith(ARRAY_BUFFER, expect.any(Float32Array), STATIC_DRAW);

    expect(surface.renderFrame(12.9)).toBe(true);

    expect(gl.viewport).toHaveBeenLastCalledWith(0, 0, 320, 180);
    expect(gl.bindFramebuffer).toHaveBeenCalledWith(FRAMEBUFFER, null);
    expect(gl.useProgram).toHaveBeenCalledWith(surface.program);
    expect(gl.uniform1f).toHaveBeenCalledWith(expect.objectContaining({ name: 'u_time' }), 12.9);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'u_frame' }), 12);
    expect(gl.uniform2f).toHaveBeenCalledWith(expect.objectContaining({ name: 'u_resolution' }), 320, 180);
    expect(gl.uniform1f).toHaveBeenCalledWith(expect.objectContaining({ name: 'intensity' }), 0.75);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'passes' }), 2);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'enabled' }), 1);
    expect(gl.uniform2f).toHaveBeenCalledWith(expect.objectContaining({ name: 'offset' }), 0.3, 0.4);
    expect(gl.uniform3f).toHaveBeenCalledWith(expect.objectContaining({ name: 'axis' }), 0, 1, 0);
    expect(gl.uniform4f).toHaveBeenCalledWith(expect.objectContaining({ name: 'tint' }), 0.2, 0.3, 0.4, 0.5);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'mode' }), 0);
    expect(gl.getUniformLocation).toHaveBeenCalledWith(surface.program, 'ignoredTexture');
    expect(gl.activeTexture).toHaveBeenCalledWith(TEXTURE0);
    expect(gl.bindTexture).toHaveBeenCalledWith(TEXTURE_2D, expect.objectContaining({ id: 1 }));
    expect(gl.texImage2D).toHaveBeenCalledWith(TEXTURE_2D, 0, RGBA, RGBA, UNSIGNED_BYTE, clipFrameSource);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'ignoredTexture' }), 0);
    expect(gl.drawArrays).toHaveBeenCalledWith(TRIANGLES, 0, 3);
  });

  it('binds static image asset and live generated frame texture sources when available', () => {
    const gl = createMockWebGL();
    const staticSource = { src: 'static.png' } as unknown as TexImageSource;
    const liveSource = { src: 'live.png' } as unknown as TexImageSource;
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas: createMockCanvas(gl),
      fragmentSource: FRAGMENT_SOURCE,
      textures: [
        {
          name: 'assetTexture',
          uniform: 'u_static',
          sourceKind: 'static-image-asset',
          filter: 'nearest',
          wrap: 'clamp-to-edge',
        },
        {
          name: 'liveTexture',
          uniform: 'u_live',
          sourceKind: 'live-generated-frame',
          filter: 'linear',
          wrap: 'repeat',
        },
      ],
      textureValues: {
        assetTexture: { kind: 'static-image-asset', ref: 'asset-1' },
        liveTexture: { kind: 'live-generated-frame', ref: 'gen-1' },
      },
      textureSources: {
        staticImageAssets: { 'asset-1': staticSource },
        liveGeneratedFrames: new Map([['gen-1', liveSource]]),
      },
    });

    expect(surface.renderFrame(3)).toBe(true);

    expect(gl.activeTexture).toHaveBeenCalledWith(TEXTURE0);
    expect(gl.activeTexture).toHaveBeenCalledWith(TEXTURE0 + 1);
    expect(gl.texParameteri).toHaveBeenCalledWith(TEXTURE_2D, TEXTURE_MIN_FILTER, NEAREST);
    expect(gl.texParameteri).toHaveBeenCalledWith(TEXTURE_2D, TEXTURE_MAG_FILTER, LINEAR);
    expect(gl.texParameteri).toHaveBeenCalledWith(TEXTURE_2D, TEXTURE_WRAP_S, REPEAT);
    expect(gl.texImage2D).toHaveBeenCalledWith(TEXTURE_2D, 0, RGBA, RGBA, UNSIGNED_BYTE, staticSource);
    expect(gl.texImage2D).toHaveBeenCalledWith(TEXTURE_2D, 0, RGBA, RGBA, UNSIGNED_BYTE, liveSource);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'u_static' }), 0);
    expect(gl.uniform1i).toHaveBeenCalledWith(expect.objectContaining({ name: 'u_live' }), 1);
  });

  it('reports unsupported texture source kinds and skips rendering', () => {
    const gl = createMockWebGL();
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas: createMockCanvas(gl),
      fragmentSource: FRAGMENT_SOURCE,
      uniforms: Object.freeze([
        {
          name: 'badTexture',
          label: 'Bad texture',
          type: 'textureRef',
          default: { kind: 'video-element' },
        } as ShaderUniformSchema[number],
      ]),
    });

    expect(surface.status).toBe('ready');
    expect(surface.diagnostics).toEqual([
      expect.objectContaining({
        code: 'shader/texture-unsupported',
        detail: expect.objectContaining({
          sourceKind: 'video-element',
          supportedSourceKinds: ['clip-frame', 'static-image-asset', 'live-generated-frame'],
        }),
      }),
    ]);
    expect(surface.renderFrame(1)).toBe(false);
    expect(gl.drawArrays).not.toHaveBeenCalled();
  });

  it('resizes the drawing buffer and leaves deterministic pixels available for readPixels', () => {
    const gl = createMockWebGL();
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas: createMockCanvas(gl),
      fragmentSource: FRAGMENT_SOURCE,
    });

    surface.resize(4, 2);
    expect(surface.renderFrame(10.8)).toBe(true);
    const firstPixels = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, RGBA, UNSIGNED_BYTE, firstPixels);

    expect(surface.renderFrame(10.8)).toBe(true);
    const secondPixels = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, RGBA, UNSIGNED_BYTE, secondPixels);

    expect([...firstPixels]).toEqual([4, 2, 10, 255]);
    expect([...secondPixels]).toEqual([...firstPixels]);
  });

  it('reports compile failures without rendering', () => {
    const gl = createMockWebGL({
      fragmentCompile: false,
      fragmentInfoLog: "ERROR: 0:3:5: 'bad' : undeclared identifier",
    });
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas: createMockCanvas(gl),
      fragmentSource: FRAGMENT_SOURCE,
    });

    expect(surface.status).toBe('failed');
    expect(surface.renderFrame(1)).toBe(false);
    expect(surface.diagnostics).toEqual([
      expect.objectContaining({
        code: 'shader/compile-error',
        message: "'bad' : undeclared identifier",
      }),
    ]);
    expect(gl.drawArrays).not.toHaveBeenCalled();
  });

  it('disposes preview-owned WebGL resources exactly once', () => {
    const gl = createMockWebGL();
    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas: createMockCanvas(gl),
      fragmentSource: FRAGMENT_SOURCE,
      uniforms: createUniformSchema(),
      textureSources: { clipFrame: clipFrameSource },
    });

    surface.renderFrame(1);
    surface.dispose();
    surface.dispose();

    expect(surface.status).toBe('disposed');
    expect(surface.renderFrame(2)).toBe(false);
    expect(gl.deleteBuffer).toHaveBeenCalledOnce();
    expect(gl.deleteProgram).toHaveBeenCalledOnce();
    expect(gl.deleteTexture).toHaveBeenCalledOnce();
  });

  it('recovers from context loss by recompiling with preserved source, uniforms, and texture sources', () => {
    const glBeforeLoss = createMockWebGL();
    const glAfterRestore = createMockWebGL();
    const canvas = createMockCanvas(glBeforeLoss);
    const clipFrameSource = { nodeName: 'CANVAS' } as unknown as TexImageSource;
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvas,
      fragmentSource: FRAGMENT_SOURCE,
      uniforms: createUniformSchema(),
      uniformValues: {
        intensity: 0.8,
        tint: [0.9, 0.8, 0.7, 1],
      },
      textureSources: { clipFrame: clipFrameSource },
      width: 64,
      height: 32,
    });

    expect(surface.renderFrame(4)).toBe(true);
    const lostEvent = { preventDefault: vi.fn() };
    canvas.__dispatchWebGLEvent('webglcontextlost', lostEvent);

    expect(lostEvent.preventDefault).toHaveBeenCalledOnce();
    expect(surface.status).toBe('unsupported');
    expect(surface.renderFrame(5)).toBe(false);

    canvas.__setWebGLContext(glAfterRestore);
    canvas.__dispatchWebGLEvent('webglcontextrestored');

    expect(surface.status).toBe('ready');
    expect(glAfterRestore.shaderSource).toHaveBeenCalledWith(expect.anything(), FRAGMENT_SOURCE);
    expect(surface.renderFrame(6)).toBe(true);
    expect(glAfterRestore.uniform1f).toHaveBeenCalledWith(expect.objectContaining({ name: 'intensity' }), 0.8);
    expect(glAfterRestore.uniform4f).toHaveBeenCalledWith(expect.objectContaining({ name: 'tint' }), 0.9, 0.8, 0.7, 1);
    expect(glAfterRestore.texImage2D).toHaveBeenCalledWith(TEXTURE_2D, 0, RGBA, RGBA, UNSIGNED_BYTE, clipFrameSource);
    expect(glAfterRestore.viewport).toHaveBeenLastCalledWith(0, 0, 64, 32);
  });

  it('returns unsupported status when no canvas can be created', () => {
    const surface = createWebGLShaderPreviewSurface({
      ...CONTEXT,
      canvasFactory: () => null,
      fragmentSource: FRAGMENT_SOURCE,
    });

    expect(surface.status).toBe('unsupported');
    expect(surface.gl).toBeUndefined();
    expect(surface.renderFrame(1)).toBe(false);
    expect(surface.diagnostics[0]).toEqual(expect.objectContaining({
      code: 'shader/webgl-unavailable',
    }));
  });
});
