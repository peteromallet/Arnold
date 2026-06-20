import type { Diagnostic } from '@reigh/editor-sdk';
import {
  SHADER_DIAGNOSTIC_CODES,
  parseWebGLInfoLog,
  type ShaderValidationContext,
} from '@/tools/video-editor/shaders/compile/diagnostics.ts';

export type WebGLShaderCompileStatus = 'compiled' | 'failed' | 'unsupported';

export type WebGLCanvasFactory = () => HTMLCanvasElement | null | undefined;

export interface WebGLShaderCompileInput extends ShaderValidationContext {
  readonly vertexSource?: string;
  readonly fragmentSource: string;
  readonly canvas?: HTMLCanvasElement;
  readonly canvasFactory?: WebGLCanvasFactory;
  readonly contextAttributes?: WebGLContextAttributes;
}

export interface WebGLShaderCompileResult {
  readonly status: WebGLShaderCompileStatus;
  readonly diagnostics: readonly Diagnostic[];
  readonly gl?: WebGLRenderingContext | WebGL2RenderingContext;
  readonly program?: WebGLProgram;
  dispose(): void;
}

const DEFAULT_VERTEX_SOURCE = [
  'attribute vec2 a_position;',
  'varying vec2 vUv;',
  'void main() {',
  '  vUv = a_position * 0.5 + 0.5;',
  '  gl_Position = vec4(a_position, 0.0, 1.0);',
  '}',
].join('\n');

const WEBGL_CONTEXT_IDS = ['webgl2', 'webgl', 'experimental-webgl'] as const;

function defaultCanvasFactory(): HTMLCanvasElement | null {
  if (typeof document === 'undefined') return null;
  return document.createElement('canvas');
}

function freezeDiagnostic(diagnostic: Diagnostic): Diagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) } : {}),
    ...(diagnostic.relatedRanges
      ? { relatedRanges: Object.freeze(diagnostic.relatedRanges.map((range) => Object.freeze({ ...range }))) }
      : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

function makeAdapterDiagnostic(
  context: ShaderValidationContext,
  status: WebGLShaderCompileStatus,
  code: string,
  message: string,
  detail: Record<string, unknown> = {},
): Diagnostic {
  return freezeDiagnostic({
    id: [
      'shader',
      'webgl-adapter',
      code.replace(/^shader\//, ''),
      context.extensionId ?? 'host',
      context.contributionId ?? context.shaderId ?? 'anonymous',
      status,
    ].join(':'),
    severity: 'error',
    code,
    message,
    ...(context.extensionId ? { extensionId: context.extensionId } : {}),
    ...(context.contributionId ? { contributionId: context.contributionId } : {}),
    detail: {
      ...(context.shaderId ? { shaderId: context.shaderId } : {}),
      status,
      ...detail,
    },
  });
}

function getWebGLContext(
  canvas: HTMLCanvasElement,
  attributes: WebGLContextAttributes | undefined,
): WebGLRenderingContext | WebGL2RenderingContext | null {
  for (const contextId of WEBGL_CONTEXT_IDS) {
    const context = canvas.getContext(contextId as 'webgl', attributes) as
      | WebGLRenderingContext
      | WebGL2RenderingContext
      | null;
    if (context) return context;
  }
  return null;
}

function safeDeleteShader(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  shader: WebGLShader | null,
): void {
  if (!shader) return;
  try {
    gl.deleteShader(shader);
  } catch {
    // Best-effort cleanup; diagnostics should describe compile/link outcomes.
  }
}

function safeDeleteProgram(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  program: WebGLProgram | null,
): void {
  if (!program) return;
  try {
    gl.deleteProgram(program);
  } catch {
    // Best-effort cleanup; diagnostics should describe compile/link outcomes.
  }
}

function compileShader(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  shaderType: number,
  phase: 'vertex' | 'fragment',
  source: string,
  context: ShaderValidationContext,
): { shader: WebGLShader | null; diagnostics: readonly Diagnostic[] } {
  const shader = gl.createShader(shaderType);
  if (!shader) {
    return {
      shader: null,
      diagnostics: [
        makeAdapterDiagnostic(
          context,
          'failed',
          SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR,
          `WebGL could not create a ${phase} shader.`,
          { phase },
        ),
      ],
    };
  }

  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (gl.getShaderParameter(shader, gl.COMPILE_STATUS) === true) {
    return { shader, diagnostics: Object.freeze([]) };
  }

  const infoLog = gl.getShaderInfoLog(shader);
  const diagnostics = parseWebGLInfoLog(infoLog || `${phase} shader compilation failed.`, {
    ...context,
    phase,
    source,
  });
  return { shader, diagnostics };
}

function linkProgram(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  vertexShader: WebGLShader,
  fragmentShader: WebGLShader,
  context: ShaderValidationContext,
): { program: WebGLProgram | null; diagnostics: readonly Diagnostic[] } {
  const program = gl.createProgram();
  if (!program) {
    return {
      program: null,
      diagnostics: [
        makeAdapterDiagnostic(
          context,
          'failed',
          SHADER_DIAGNOSTIC_CODES.LINK_ERROR,
          'WebGL could not create a shader program.',
          { phase: 'link' },
        ),
      ],
    };
  }

  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);

  if (gl.getProgramParameter(program, gl.LINK_STATUS) === true) {
    return { program, diagnostics: Object.freeze([]) };
  }

  const infoLog = gl.getProgramInfoLog(program);
  return {
    program,
    diagnostics: parseWebGLInfoLog(infoLog || 'Shader program link failed.', {
      ...context,
      phase: 'link',
    }),
  };
}

export function compileWebGLShaderProgram(input: WebGLShaderCompileInput): WebGLShaderCompileResult {
  const context: ShaderValidationContext = {
    shaderId: input.shaderId,
    extensionId: input.extensionId,
    contributionId: input.contributionId,
  };
  const diagnostics: Diagnostic[] = [];
  const canvas = input.canvas ?? (input.canvasFactory ?? defaultCanvasFactory)();

  if (!canvas) {
    return {
      status: 'unsupported',
      diagnostics: Object.freeze([
        makeAdapterDiagnostic(
          context,
          'unsupported',
          'shader/webgl-unavailable',
          'WebGL shader compilation requires a browser canvas.',
        ),
      ]),
      dispose(): void {},
    };
  }

  const gl = getWebGLContext(canvas, input.contextAttributes);
  if (!gl) {
    return {
      status: 'unsupported',
      diagnostics: Object.freeze([
        makeAdapterDiagnostic(
          context,
          'unsupported',
          'shader/webgl-unavailable',
          'No WebGL rendering context is available for shader compilation.',
        ),
      ]),
      dispose(): void {},
    };
  }

  let vertexShader: WebGLShader | null = null;
  let fragmentShader: WebGLShader | null = null;
  let program: WebGLProgram | null = null;
  let disposed = false;

  try {
    const vertexResult = compileShader(
      gl,
      gl.VERTEX_SHADER,
      'vertex',
      input.vertexSource ?? DEFAULT_VERTEX_SOURCE,
      context,
    );
    vertexShader = vertexResult.shader;
    diagnostics.push(...vertexResult.diagnostics);

    const fragmentResult = compileShader(
      gl,
      gl.FRAGMENT_SHADER,
      'fragment',
      input.fragmentSource,
      context,
    );
    fragmentShader = fragmentResult.shader;
    diagnostics.push(...fragmentResult.diagnostics);

    if (diagnostics.some((diagnostic) => diagnostic.severity === 'error')) {
      safeDeleteShader(gl, vertexShader);
      safeDeleteShader(gl, fragmentShader);
      return {
        status: 'failed',
        gl,
        diagnostics: Object.freeze([...diagnostics]),
        dispose(): void {},
      };
    }

    if (!vertexShader || !fragmentShader) {
      safeDeleteShader(gl, vertexShader);
      safeDeleteShader(gl, fragmentShader);
      return {
        status: 'failed',
        gl,
        diagnostics: Object.freeze([...diagnostics]),
        dispose(): void {},
      };
    }

    const linkResult = linkProgram(gl, vertexShader, fragmentShader, context);
    program = linkResult.program;
    diagnostics.push(...linkResult.diagnostics);

    safeDeleteShader(gl, vertexShader);
    safeDeleteShader(gl, fragmentShader);
    vertexShader = null;
    fragmentShader = null;

    if (diagnostics.some((diagnostic) => diagnostic.severity === 'error') || !program) {
      safeDeleteProgram(gl, program);
      return {
        status: 'failed',
        gl,
        diagnostics: Object.freeze([...diagnostics]),
        dispose(): void {},
      };
    }

    const linkedProgram = program;
    return {
      status: 'compiled',
      gl,
      program: linkedProgram,
      diagnostics: Object.freeze([...diagnostics]),
      dispose(): void {
        if (disposed) return;
        disposed = true;
        safeDeleteProgram(gl, linkedProgram);
      },
    };
  } catch (error) {
    safeDeleteProgram(gl, program);
    safeDeleteShader(gl, vertexShader);
    safeDeleteShader(gl, fragmentShader);
    return {
      status: 'failed',
      gl,
      diagnostics: Object.freeze([
        ...diagnostics,
        makeAdapterDiagnostic(
          context,
          'failed',
          SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR,
          `WebGL shader compilation failed: ${String(error)}`,
        ),
      ]),
      dispose(): void {},
    };
  }
}

