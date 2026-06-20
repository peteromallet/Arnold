import type {
  Diagnostic,
  DiagnosticSourceRange,
  ShaderTextureDefinition,
  ShaderTextureRef,
  ShaderTextureSchema,
  ShaderTextureSourceKind,
  ShaderUniformDefinition,
  ShaderUniformSchema,
} from '@reigh/editor-sdk';
import {
  compileWebGLShaderProgram,
  type WebGLCanvasFactory,
  type WebGLShaderCompileResult,
} from '@/tools/video-editor/shaders/compile/webgl-adapter.ts';
import type { ShaderValidationContext } from '@/tools/video-editor/shaders/compile/diagnostics.ts';

export type WebGLShaderPreviewSurfaceStatus = 'ready' | 'failed' | 'unsupported' | 'disposed';

export type WebGLShaderPreviewTextureImageSource = TexImageSource;

export type WebGLShaderPreviewTextureSourceMap =
  | ReadonlyMap<string, WebGLShaderPreviewTextureImageSource>
  | Readonly<Record<string, WebGLShaderPreviewTextureImageSource | undefined>>;

export interface WebGLShaderPreviewTextureSources {
  readonly clipFrame?: WebGLShaderPreviewTextureImageSource;
  readonly clipFrames?: WebGLShaderPreviewTextureSourceMap;
  readonly staticImageAssets?: WebGLShaderPreviewTextureSourceMap;
  readonly liveGeneratedFrames?: WebGLShaderPreviewTextureSourceMap;
}

export interface WebGLShaderPreviewSurfaceInput extends ShaderValidationContext {
  readonly canvas?: HTMLCanvasElement;
  readonly canvasFactory?: WebGLCanvasFactory;
  readonly vertexSource?: string;
  readonly fragmentSource: string;
  readonly uniforms?: ShaderUniformSchema;
  readonly uniformValues?: Record<string, unknown>;
  readonly textures?: ShaderTextureSchema;
  readonly textureValues?: Record<string, unknown>;
  readonly textureSources?: WebGLShaderPreviewTextureSources;
  readonly width?: number;
  readonly height?: number;
  readonly contextAttributes?: WebGLContextAttributes;
}

export interface WebGLShaderPreviewFrame {
  readonly time: number;
  readonly frame: number;
  readonly width: number;
  readonly height: number;
}

const DEFAULT_WIDTH = 1;
const DEFAULT_HEIGHT = 1;
const SUPPORTED_TEXTURE_SOURCE_KINDS = new Set<ShaderTextureSourceKind>([
  'clip-frame',
  'static-image-asset',
  'live-generated-frame',
]);
const FULLSCREEN_TRIANGLE_VERTICES = new Float32Array([
  -1, -1,
  3, -1,
  -1, 3,
]);

interface TextureBinding {
  readonly name: string;
  readonly uniform: string;
  readonly sourceKind: unknown;
  readonly ref?: string;
  readonly required?: boolean;
  readonly filter?: ShaderTextureDefinition['filter'];
  readonly wrap?: ShaderTextureDefinition['wrap'];
}

function defaultCanvasFactory(): HTMLCanvasElement | null {
  if (typeof document === 'undefined') return null;
  return document.createElement('canvas');
}

function freezeDiagnostic(diagnostic: Diagnostic): Diagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange
      ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) as DiagnosticSourceRange }
      : {}),
    ...(diagnostic.relatedRanges
      ? { relatedRanges: Object.freeze(diagnostic.relatedRanges.map((range) => Object.freeze({ ...range }))) }
      : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

function makePreviewDiagnostic(
  context: ShaderValidationContext,
  status: Exclude<WebGLShaderPreviewSurfaceStatus, 'ready'>,
  code: string,
  message: string,
  detail: Record<string, unknown> = {},
): Diagnostic {
  return freezeDiagnostic({
    id: [
      'shader',
      'preview-surface',
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

function normalizeDimension(value: number | undefined, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
  return Math.max(1, Math.floor(value));
}

function isWebGL2RenderingContext(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
): gl is WebGL2RenderingContext {
  return typeof (gl as WebGL2RenderingContext).deleteVertexArray === 'function';
}

function defaultUniformValue(uniform: ShaderUniformDefinition, frame: WebGLShaderPreviewFrame): unknown {
  if (uniform.type === 'time') return frame.time;
  if (uniform.type === 'frame') return frame.frame;
  return uniform.default;
}

function toFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function toFiniteVector(value: unknown, size: number): readonly number[] | undefined {
  return Array.isArray(value)
    && value.length >= size
    && value.slice(0, size).every((item) => typeof item === 'number' && Number.isFinite(item))
    ? value.slice(0, size) as readonly number[]
    : undefined;
}

function enumIndexFor(uniform: ShaderUniformDefinition, value: unknown): number | undefined {
  if (typeof value !== 'string') return undefined;
  const index = uniform.options?.findIndex((option) => option.value === value);
  return index === undefined || index < 0 ? undefined : index;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isShaderTextureRef(value: unknown): value is ShaderTextureRef {
  return isRecord(value) && typeof value.kind === 'string';
}

function isSupportedTextureSourceKind(value: unknown): value is ShaderTextureSourceKind {
  return SUPPORTED_TEXTURE_SOURCE_KINDS.has(value as ShaderTextureSourceKind);
}

function lookupTextureSource(
  sources: WebGLShaderPreviewTextureSourceMap | undefined,
  ref: string | undefined,
): WebGLShaderPreviewTextureImageSource | undefined {
  if (!sources || !ref) return undefined;
  if (sources instanceof Map) return sources.get(ref);
  return sources[ref];
}

function textureFilterValue(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  filter: ShaderTextureDefinition['filter'] | undefined,
): number {
  return filter === 'nearest' ? gl.NEAREST : gl.LINEAR;
}

function textureWrapValue(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  wrap: ShaderTextureDefinition['wrap'] | undefined,
): number {
  if (wrap === 'repeat') return gl.REPEAT;
  if (wrap === 'mirrored-repeat') return gl.MIRRORED_REPEAT;
  return gl.CLAMP_TO_EDGE;
}

function uploadUniformValue(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  location: WebGLUniformLocation,
  uniform: ShaderUniformDefinition,
  value: unknown,
): void {
  switch (uniform.type) {
    case 'float':
    case 'time': {
      const numberValue = toFiniteNumber(value);
      if (numberValue !== undefined) gl.uniform1f(location, numberValue);
      break;
    }
    case 'int':
    case 'frame': {
      const numberValue = toFiniteNumber(value);
      if (numberValue !== undefined) gl.uniform1i(location, Math.floor(numberValue));
      break;
    }
    case 'bool':
      if (typeof value === 'boolean') gl.uniform1i(location, value ? 1 : 0);
      break;
    case 'vec2': {
      const vector = toFiniteVector(value, 2);
      if (vector) gl.uniform2f(location, vector[0], vector[1]);
      break;
    }
    case 'vec3': {
      const vector = toFiniteVector(value, 3);
      if (vector) gl.uniform3f(location, vector[0], vector[1], vector[2]);
      break;
    }
    case 'vec4':
    case 'color': {
      const vector = toFiniteVector(value, 4);
      if (vector) gl.uniform4f(location, vector[0], vector[1], vector[2], vector[3]);
      break;
    }
    case 'enum': {
      const index = enumIndexFor(uniform, value);
      if (index !== undefined) gl.uniform1i(location, index);
      break;
    }
    case 'textureRef':
      break;
  }
}

export class WebGLShaderPreviewSurface {
  readonly canvas?: HTMLCanvasElement;
  gl?: WebGLRenderingContext | WebGL2RenderingContext;
  program?: WebGLProgram;
  diagnostics: readonly Diagnostic[] = Object.freeze([]);

  #status: WebGLShaderPreviewSurfaceStatus;
  #compileResult?: WebGLShaderCompileResult;
  #buffer: WebGLBuffer | null = null;
  #vertexArray: WebGLVertexArrayObject | null = null;
  #textures = new Map<string, WebGLTexture>();
  #positionLocation = -1;
  #width: number;
  #height: number;
  #disposed = false;
  #uniforms: ShaderUniformSchema;
  #uniformValues: Record<string, unknown>;
  #textureDefinitions: ShaderTextureSchema;
  #textureValues: Record<string, unknown>;
  #textureSources: WebGLShaderPreviewTextureSources;
  #uniformLocations = new Map<string, WebGLUniformLocation | null>();
  #builtinLocations = new Map<string, WebGLUniformLocation | null>();
  #context: ShaderValidationContext;
  #canvasFactory?: WebGLCanvasFactory;
  #vertexSource?: string;
  #fragmentSource: string;
  #contextAttributes: WebGLContextAttributes;
  #contextLostListener?: (event: Event) => void;
  #contextRestoredListener?: () => void;

  constructor(input: WebGLShaderPreviewSurfaceInput) {
    this.#context = {
      shaderId: input.shaderId,
      extensionId: input.extensionId,
      contributionId: input.contributionId,
    };
    this.#width = normalizeDimension(input.width, DEFAULT_WIDTH);
    this.#height = normalizeDimension(input.height, DEFAULT_HEIGHT);
    this.#uniforms = input.uniforms ?? Object.freeze([]);
    this.#uniformValues = { ...(input.uniformValues ?? {}) };
    this.#textureDefinitions = input.textures ?? Object.freeze([]);
    this.#textureValues = { ...(input.textureValues ?? {}) };
    this.#textureSources = { ...(input.textureSources ?? {}) };
    this.#vertexSource = input.vertexSource;
    this.#fragmentSource = input.fragmentSource;
    this.#contextAttributes = {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: true,
      ...(input.contextAttributes ?? {}),
    };

    const canvasFactory = input.canvas ? undefined : input.canvasFactory ?? defaultCanvasFactory;
    this.#canvasFactory = canvasFactory;
    const canvas = input.canvas ?? canvasFactory?.();
    if (canvas) {
      this.canvas = canvas;
      this.#applyCanvasSize();
      this.#attachContextRecoveryListeners(canvas);
    }

    this.#status = 'unsupported';
    this.#compileAndSetup();
  }

  get status(): WebGLShaderPreviewSurfaceStatus {
    return this.#status;
  }

  get width(): number {
    return this.#width;
  }

  get height(): number {
    return this.#height;
  }

  resize(width: number, height: number): void {
    if (this.#disposed) return;
    this.#width = normalizeDimension(width, this.#width);
    this.#height = normalizeDimension(height, this.#height);
    this.#applyCanvasSize();
  }

  setUniformValues(values: Record<string, unknown>): void {
    if (this.#disposed) return;
    this.#uniformValues = { ...values };
  }

  updateUniformValues(values: Record<string, unknown>): void {
    if (this.#disposed) return;
    this.#uniformValues = { ...this.#uniformValues, ...values };
  }

  setTextureValues(values: Record<string, unknown>): void {
    if (this.#disposed) return;
    this.#textureValues = { ...values };
    this.#refreshTextureDiagnostics();
  }

  updateTextureSources(sources: WebGLShaderPreviewTextureSources): void {
    if (this.#disposed) return;
    this.#textureSources = { ...this.#textureSources, ...sources };
    this.#refreshTextureDiagnostics();
  }

  renderFrame(frameTime: number, frameIndex?: number): boolean {
    if (this.#status !== 'ready' || this.#disposed || !this.gl || !this.program) return false;

    const time = Number.isFinite(frameTime) ? frameTime : 0;
    const frameNumber = typeof frameIndex === 'number' && Number.isFinite(frameIndex)
      ? frameIndex
      : Math.floor(time);
    const frame = {
      time,
      frame: Math.floor(frameNumber),
      width: this.#width,
      height: this.#height,
    };
    const gl = this.gl;

    gl.viewport(0, 0, this.#width, this.#height);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.useProgram(this.program);
    this.#bindFullscreenGeometry();
    this.#uploadBuiltins(frame);
    this.#uploadConfiguredUniforms(frame);
    if (!this.#bindConfiguredTextures()) return false;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    return true;
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#disposed = true;

    if (this.canvas && this.#contextLostListener) {
      this.canvas.removeEventListener('webglcontextlost', this.#contextLostListener);
    }
    if (this.canvas && this.#contextRestoredListener) {
      this.canvas.removeEventListener('webglcontextrestored', this.#contextRestoredListener);
    }
    this.#contextLostListener = undefined;
    this.#contextRestoredListener = undefined;
    this.#releaseWebGLResources();
    this.#status = 'disposed';
  }

  #releaseWebGLResources(): void {
    if (this.gl && this.#vertexArray && isWebGL2RenderingContext(this.gl)) {
      this.gl.deleteVertexArray(this.#vertexArray);
    }
    this.#vertexArray = null;

    if (this.gl && this.#buffer) {
      this.gl.deleteBuffer(this.#buffer);
    }
    this.#buffer = null;
    for (const texture of this.#textures.values()) {
      this.gl?.deleteTexture(texture);
    }
    this.#textures.clear();
    this.#uniformLocations.clear();
    this.#builtinLocations.clear();
    this.#compileResult?.dispose();
    this.#compileResult = undefined;
    this.gl = undefined;
    this.program = undefined;
  }

  #applyCanvasSize(): void {
    if (!this.canvas) return;
    this.canvas.width = this.#width;
    this.canvas.height = this.#height;
  }

  #attachContextRecoveryListeners(canvas: HTMLCanvasElement): void {
    this.#contextLostListener = (event: Event): void => {
      if (this.#disposed) return;
      event.preventDefault();
      this.#releaseWebGLResources();
      this.#status = 'unsupported';
      this.diagnostics = Object.freeze([
        ...this.diagnostics,
        makePreviewDiagnostic(
          this.#context,
          'unsupported',
          'shader/webgl-context-lost',
          'WebGL shader preview context was lost; rendering is paused until the context is restored.',
        ),
      ]);
    };
    this.#contextRestoredListener = (): void => {
      if (this.#disposed) return;
      this.#compileAndSetup();
    };
    canvas.addEventListener('webglcontextlost', this.#contextLostListener);
    canvas.addEventListener('webglcontextrestored', this.#contextRestoredListener);
  }

  #compileAndSetup(): void {
    this.#releaseWebGLResources();
    const compileResult = compileWebGLShaderProgram({
      ...this.#context,
      canvas: this.canvas,
      canvasFactory: this.canvas ? undefined : this.#canvasFactory,
      vertexSource: this.#vertexSource,
      fragmentSource: this.#fragmentSource,
      contextAttributes: this.#contextAttributes,
    });

    this.#compileResult = compileResult;
    this.gl = compileResult.gl;
    this.program = compileResult.program;
    this.diagnostics = Object.freeze([
      ...compileResult.diagnostics,
      ...this.#collectTextureBindingDiagnostics(),
    ]);
    this.#status = compileResult.status === 'compiled'
      ? 'ready'
      : compileResult.status;

    if (this.#status !== 'ready' || !this.gl || !this.program) return;

    const setupDiagnostic = this.#setupFullscreenGeometry();
    if (setupDiagnostic) {
      this.diagnostics = Object.freeze([...this.diagnostics, setupDiagnostic]);
      this.#status = 'failed';
      this.#releaseWebGLResources();
    }
  }

  #setupFullscreenGeometry(): Diagnostic | undefined {
    if (!this.gl || !this.program) return undefined;
    const gl = this.gl;
    const buffer = gl.createBuffer();
    if (!buffer) {
      return makePreviewDiagnostic(
        this.#context,
        'failed',
        'shader/preview-buffer-unavailable',
        'WebGL shader preview could not allocate a fullscreen vertex buffer.',
      );
    }

    this.#buffer = buffer;
    if (isWebGL2RenderingContext(gl) && typeof gl.createVertexArray === 'function') {
      this.#vertexArray = gl.createVertexArray();
      if (this.#vertexArray) gl.bindVertexArray(this.#vertexArray);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, FULLSCREEN_TRIANGLE_VERTICES, gl.STATIC_DRAW);

    this.#positionLocation = gl.getAttribLocation(this.program, 'a_position');
    if (this.#positionLocation >= 0) {
      gl.enableVertexAttribArray(this.#positionLocation);
      gl.vertexAttribPointer(this.#positionLocation, 2, gl.FLOAT, false, 0, 0);
    }

    if (isWebGL2RenderingContext(gl) && this.#vertexArray) {
      gl.bindVertexArray(null);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    return undefined;
  }

  #bindFullscreenGeometry(): void {
    if (!this.gl) return;
    const gl = this.gl;
    if (isWebGL2RenderingContext(gl) && this.#vertexArray) {
      gl.bindVertexArray(this.#vertexArray);
      return;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.#buffer);
    if (this.#positionLocation >= 0) {
      gl.enableVertexAttribArray(this.#positionLocation);
      gl.vertexAttribPointer(this.#positionLocation, 2, gl.FLOAT, false, 0, 0);
    }
  }

  #getUniformLocation(name: string): WebGLUniformLocation | null {
    if (!this.gl || !this.program) return null;
    if (this.#uniformLocations.has(name)) return this.#uniformLocations.get(name) ?? null;
    const location = this.gl.getUniformLocation(this.program, name);
    this.#uniformLocations.set(name, location);
    return location;
  }

  #getBuiltinLocation(name: string): WebGLUniformLocation | null {
    if (!this.gl || !this.program) return null;
    if (this.#builtinLocations.has(name)) return this.#builtinLocations.get(name) ?? null;
    const location = this.gl.getUniformLocation(this.program, name);
    this.#builtinLocations.set(name, location);
    return location;
  }

  #uploadBuiltins(frame: WebGLShaderPreviewFrame): void {
    if (!this.gl) return;
    const gl = this.gl;
    const timeLocation = this.#getBuiltinLocation('u_time');
    if (timeLocation) gl.uniform1f(timeLocation, frame.time);
    const frameLocation = this.#getBuiltinLocation('u_frame');
    if (frameLocation) gl.uniform1i(frameLocation, frame.frame);
    const resolutionLocation = this.#getBuiltinLocation('u_resolution');
    if (resolutionLocation) gl.uniform2f(resolutionLocation, frame.width, frame.height);
  }

  #uploadConfiguredUniforms(frame: WebGLShaderPreviewFrame): void {
    if (!this.gl) return;
    for (const uniform of this.#uniforms) {
      if (uniform.type === 'textureRef') continue;
      const location = this.#getUniformLocation(uniform.name);
      if (!location) continue;
      const value = Object.hasOwn(this.#uniformValues, uniform.name)
        ? this.#uniformValues[uniform.name]
        : defaultUniformValue(uniform, frame);
      uploadUniformValue(this.gl, location, uniform, value);
    }
  }

  #textureRefForName(name: string): ShaderTextureRef | undefined {
    const value = Object.hasOwn(this.#textureValues, name)
      ? this.#textureValues[name]
      : this.#uniformValues[name];
    if (isShaderTextureRef(value)) return value;
    const uniform = this.#uniforms.find((item) => item.name === name && item.type === 'textureRef');
    return isShaderTextureRef(uniform?.default) ? uniform.default : undefined;
  }

  #textureBindings(): readonly TextureBinding[] {
    const schemaBindings = this.#textureDefinitions.map((texture) => {
      const ref = this.#textureRefForName(texture.name) ?? this.#textureRefForName(texture.uniform ?? texture.name);
      return {
        name: texture.name,
        uniform: texture.uniform ?? texture.name,
        sourceKind: ref?.kind ?? texture.sourceKind,
        ref: ref?.ref,
        required: texture.required,
        filter: texture.filter,
        wrap: texture.wrap,
      } satisfies TextureBinding;
    });
    const schemaUniformNames = new Set(schemaBindings.map((binding) => binding.uniform));
    const textureRefUniformBindings = this.#uniforms
      .filter((uniform) => uniform.type === 'textureRef' && !schemaUniformNames.has(uniform.name))
      .map((uniform) => {
        const ref = this.#textureRefForName(uniform.name);
        return {
          name: uniform.name,
          uniform: uniform.name,
          sourceKind: ref?.kind ?? 'clip-frame',
          ref: ref?.ref,
        } satisfies TextureBinding;
      });
    return Object.freeze([...schemaBindings, ...textureRefUniformBindings]);
  }

  #resolveTextureSource(binding: TextureBinding): WebGLShaderPreviewTextureImageSource | undefined {
    if (binding.sourceKind === 'clip-frame') {
      return binding.ref
        ? lookupTextureSource(this.#textureSources.clipFrames, binding.ref) ?? this.#textureSources.clipFrame
        : this.#textureSources.clipFrame;
    }

    if (binding.sourceKind === 'static-image-asset') {
      return lookupTextureSource(this.#textureSources.staticImageAssets, binding.ref);
    }

    if (binding.sourceKind === 'live-generated-frame') {
      return lookupTextureSource(this.#textureSources.liveGeneratedFrames, binding.ref);
    }

    return undefined;
  }

  #collectTextureBindingDiagnostics(): readonly Diagnostic[] {
    const diagnostics: Diagnostic[] = [];
    for (const binding of this.#textureBindings()) {
      if (!isSupportedTextureSourceKind(binding.sourceKind)) {
        diagnostics.push(makePreviewDiagnostic(
          this.#context,
          'failed',
          'shader/texture-unsupported',
          `Shader texture "${binding.name}" uses unsupported source kind "${String(binding.sourceKind)}".`,
          {
            textureName: binding.name,
            uniformName: binding.uniform,
            sourceKind: binding.sourceKind,
            supportedSourceKinds: [...SUPPORTED_TEXTURE_SOURCE_KINDS],
          },
        ));
        continue;
      }

      if (binding.required === true && !this.#resolveTextureSource(binding)) {
        diagnostics.push(makePreviewDiagnostic(
          this.#context,
          'failed',
          'shader/texture-unavailable',
          `Shader texture "${binding.name}" requires a ${binding.sourceKind} source that is not available.`,
          {
            textureName: binding.name,
            uniformName: binding.uniform,
            sourceKind: binding.sourceKind,
            ref: binding.ref,
          },
        ));
      }
    }

    return Object.freeze(diagnostics);
  }

  #refreshTextureDiagnostics(): void {
    const nonTextureDiagnostics = this.diagnostics.filter((diagnostic) => (
      diagnostic.code !== 'shader/texture-unsupported'
      && diagnostic.code !== 'shader/texture-unavailable'
    ));
    this.diagnostics = Object.freeze([
      ...nonTextureDiagnostics,
      ...this.#collectTextureBindingDiagnostics(),
    ]);
  }

  #bindConfiguredTextures(): boolean {
    if (!this.gl) return false;
    const diagnostics = this.#collectTextureBindingDiagnostics();
    this.#refreshTextureDiagnostics();
    if (diagnostics.some((diagnostic) => diagnostic.severity === 'error')) return false;

    const gl = this.gl;
    let unit = 0;
    for (const binding of this.#textureBindings()) {
      const source = this.#resolveTextureSource(binding);
      if (!source) continue;
      const location = this.#getUniformLocation(binding.uniform);
      if (!location) continue;
      let texture = this.#textures.get(binding.uniform);
      if (!texture) {
        texture = gl.createTexture();
        if (!texture) return false;
        this.#textures.set(binding.uniform, texture);
      }

      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, textureFilterValue(gl, binding.filter));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, textureFilterValue(gl, binding.filter));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, textureWrapValue(gl, binding.wrap));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, textureWrapValue(gl, binding.wrap));
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
      gl.uniform1i(location, unit);
      unit += 1;
    }

    return true;
  }
}

export function createWebGLShaderPreviewSurface(
  input: WebGLShaderPreviewSurfaceInput,
): WebGLShaderPreviewSurface {
  return new WebGLShaderPreviewSurface(input);
}
