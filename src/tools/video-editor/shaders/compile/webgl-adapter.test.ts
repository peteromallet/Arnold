import { describe, expect, it, vi } from 'vitest';
import { SHADER_DIAGNOSTIC_CODES } from '@/tools/video-editor/shaders/compile/diagnostics.ts';
import { compileWebGLShaderProgram } from '@/tools/video-editor/shaders/compile/webgl-adapter.ts';

const VERTEX_SHADER = 0x8B31;
const FRAGMENT_SHADER = 0x8B30;
const COMPILE_STATUS = 0x8B81;
const LINK_STATUS = 0x8B82;

const CONTEXT = {
  shaderId: 'shader.grade',
  extensionId: 'com.example.shader',
  contributionId: 'grade.contribution',
};

const VERTEX_SOURCE = [
  'attribute vec2 a_position;',
  'void main() {',
  '  gl_Position = vec4(a_position, 0.0, 1.0);',
  '}',
].join('\n');

const FRAGMENT_SOURCE = [
  'precision mediump float;',
  'void main() {',
  '  gl_FragColor = vec4(1.0);',
  '}',
].join('\n');

interface MockShader {
  readonly id: number;
  readonly type: number;
}

interface MockProgram {
  readonly id: number;
}

function createMockCanvas(gl: WebGLRenderingContext): HTMLCanvasElement {
  return {
    getContext: vi.fn((contextId: string) => (contextId === 'webgl2' ? gl : null)),
  } as unknown as HTMLCanvasElement;
}

function createMockWebGL(options: {
  readonly vertexCompile?: boolean;
  readonly fragmentCompile?: boolean;
  readonly link?: boolean;
  readonly vertexInfoLog?: string;
  readonly fragmentInfoLog?: string;
  readonly linkInfoLog?: string;
} = {}): WebGLRenderingContext {
  const vertexCompile = options.vertexCompile ?? true;
  const fragmentCompile = options.fragmentCompile ?? true;
  const link = options.link ?? true;
  let nextShaderId = 1;
  let nextProgramId = 1;
  const shaderSources = new Map<MockShader, string>();

  const gl = {
    VERTEX_SHADER,
    FRAGMENT_SHADER,
    COMPILE_STATUS,
    LINK_STATUS,
    createShader: vi.fn((type: number): MockShader => ({ id: nextShaderId++, type })),
    shaderSource: vi.fn((shader: MockShader, source: string): void => {
      shaderSources.set(shader, source);
    }),
    compileShader: vi.fn(),
    getShaderParameter: vi.fn((shader: MockShader, parameter: number): boolean => {
      if (parameter !== COMPILE_STATUS) return false;
      return shader.type === VERTEX_SHADER ? vertexCompile : fragmentCompile;
    }),
    getShaderInfoLog: vi.fn((shader: MockShader): string => (
      shader.type === VERTEX_SHADER
        ? options.vertexInfoLog ?? ''
        : options.fragmentInfoLog ?? ''
    )),
    deleteShader: vi.fn(),
    createProgram: vi.fn((): MockProgram => ({ id: nextProgramId++ })),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    getProgramParameter: vi.fn((_program: MockProgram, parameter: number): boolean => (
      parameter === LINK_STATUS ? link : false
    )),
    getProgramInfoLog: vi.fn((): string => options.linkInfoLog ?? ''),
    deleteProgram: vi.fn(),
  };

  return gl as unknown as WebGLRenderingContext;
}

describe('compileWebGLShaderProgram', () => {
  it('compiles vertex and fragment sources and returns a disposable WebGL program', () => {
    const gl = createMockWebGL();
    const result = compileWebGLShaderProgram({
      ...CONTEXT,
      vertexSource: VERTEX_SOURCE,
      fragmentSource: FRAGMENT_SOURCE,
      canvas: createMockCanvas(gl),
    });

    expect(result.status).toBe('compiled');
    expect(result.diagnostics).toEqual([]);
    expect(result.program).toBeDefined();
    expect(gl.shaderSource).toHaveBeenNthCalledWith(1, expect.objectContaining({ type: VERTEX_SHADER }), VERTEX_SOURCE);
    expect(gl.shaderSource).toHaveBeenNthCalledWith(2, expect.objectContaining({ type: FRAGMENT_SHADER }), FRAGMENT_SOURCE);
    expect(gl.linkProgram).toHaveBeenCalledOnce();

    result.dispose();
    result.dispose();
    expect(gl.deleteProgram).toHaveBeenCalledOnce();
  });

  it('turns fragment compile failures into structured diagnostics with source ranges without throwing', () => {
    const gl = createMockWebGL({
      fragmentCompile: false,
      fragmentInfoLog: "ERROR: 0:3:5: 'gl_FragColor' : undeclared identifier",
    });

    const result = compileWebGLShaderProgram({
      ...CONTEXT,
      vertexSource: VERTEX_SOURCE,
      fragmentSource: FRAGMENT_SOURCE,
      canvas: createMockCanvas(gl),
    });

    expect(result.status).toBe('failed');
    expect(result.program).toBeUndefined();
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR,
        severity: 'error',
        extensionId: CONTEXT.extensionId,
        contributionId: CONTEXT.contributionId,
        message: "'gl_FragColor' : undeclared identifier",
        sourceRange: { startLine: 3, startCol: 5, endLine: 3, endCol: 6 },
        detail: expect.objectContaining({
          shaderId: CONTEXT.shaderId,
          phase: 'fragment',
          line: 3,
          column: 5,
        }),
      }),
    ]);
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
    expect(Object.isFrozen(result.diagnostics[0].sourceRange)).toBe(true);
    expect(gl.linkProgram).not.toHaveBeenCalled();
    expect(gl.deleteShader).toHaveBeenCalledTimes(2);
  });

  it('turns link failures into structured diagnostics without throwing', () => {
    const gl = createMockWebGL({
      link: false,
      linkInfoLog: 'ERROR: program link failed: fragment shader varying mismatch',
    });

    const result = compileWebGLShaderProgram({
      ...CONTEXT,
      vertexSource: VERTEX_SOURCE,
      fragmentSource: FRAGMENT_SOURCE,
      canvas: createMockCanvas(gl),
    });

    expect(result.status).toBe('failed');
    expect(result.program).toBeUndefined();
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.LINK_ERROR,
        severity: 'error',
        message: 'program link failed: fragment shader varying mismatch',
        detail: expect.objectContaining({
          shaderId: CONTEXT.shaderId,
          phase: 'link',
          infoLogLine: 'ERROR: program link failed: fragment shader varying mismatch',
        }),
      }),
    ]);
    expect(result.diagnostics[0]).not.toHaveProperty('sourceRange');
    expect(gl.deleteShader).toHaveBeenCalledTimes(2);
    expect(gl.deleteProgram).toHaveBeenCalledOnce();
  });

  it('reports unavailable WebGL as an unsupported diagnostic in jsdom-safe tests', () => {
    const result = compileWebGLShaderProgram({
      ...CONTEXT,
      fragmentSource: FRAGMENT_SOURCE,
      canvasFactory: () => null,
    });

    expect(result.status).toBe('unsupported');
    expect(result.program).toBeUndefined();
    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        code: 'shader/webgl-unavailable',
        severity: 'error',
        message: 'WebGL shader compilation requires a browser canvas.',
        detail: expect.objectContaining({
          shaderId: CONTEXT.shaderId,
          status: 'unsupported',
        }),
      }),
    ]);
  });
});

