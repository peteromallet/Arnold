/**
 * clip-local-shader-canary — clip-local WebGL shader canary.
 *
 * Exercises the public shader SDK path: manifest-declared ShaderContribution
 * records, ctx.shaders.registerShader(), uniform defaults, textureRef binding
 * metadata, registry diagnostics, graph-owned shader assignment/removal,
 * shader-uniform keyframe round-trips, preview-only renderability, picker
 * metadata, and planner blockers.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  DisposeHandle,
  ExtensionContext,
  ReighExtension,
  ShaderContribution,
  ShaderInlineSource,
  ShaderTextureSchema,
  ShaderUniformDefinition,
  ShaderUniformSchema,
} from '@reigh/editor-sdk';

export const CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID = 'com.reigh.examples.clip-local-shader-canary';
export const CLIP_LOCAL_SHADER_CANARY_SHADER_ID = 'shader.clipLocalCanary.grade';
export const CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID = 'clip-local-shader-canary';
export const CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID = 'shader.clipLocalCanary.diagnostic';
export const CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID = 'clip-local-shader-canary-diagnostic';
export const CLIP_LOCAL_SHADER_CANARY_VERSION = '1.0.0';

export interface ClipLocalShaderCanaryOptions {
  readonly includeDiagnosticShader?: boolean;
  readonly onReady?: (controller: ClipLocalShaderCanaryController) => void;
}

export interface ClipLocalShaderCanaryController extends DisposeHandle {
  readonly extensionId: string;
  readonly shaderId: string;
  readonly contribution: ShaderContribution;
  readonly diagnosticShaderId: string;
  readonly diagnosticContribution: ShaderContribution;
}

export const CLIP_LOCAL_SHADER_CANARY_SOURCE: ShaderInlineSource = {
  kind: 'inline',
  fragment: `
precision mediump float;
uniform sampler2D u_source;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_frame;
uniform float intensity;
uniform vec4 tint;
uniform vec2 center;
uniform bool showGrid;
uniform int bandCount;
uniform float holdFrame;
uniform float holdTime;
uniform float blendMode;

varying vec2 v_uv;

void main() {
  vec4 base = texture2D(u_source, v_uv);
  vec2 delta = abs(v_uv - center);
  float vignette = smoothstep(0.85, 0.15, max(delta.x, delta.y));
  float grid = showGrid ? step(0.97, fract((v_uv.x + v_uv.y + u_time * 0.05) * float(bandCount))) : 0.0;
  float pulse = 0.5 + 0.5 * sin((u_frame + holdFrame + holdTime * 30.0) * 0.06);
  vec3 graded = mix(base.rgb, tint.rgb, clamp(intensity * vignette * pulse, 0.0, 1.0));
  graded = mix(graded, vec3(1.0) - graded, clamp(blendMode, 0.0, 1.0) * 0.18);
  gl_FragColor = vec4(mix(graded, vec3(1.0), grid * 0.18), base.a);
}
`,
};

export const CLIP_LOCAL_SHADER_CANARY_UNIFORMS: ShaderUniformSchema = Object.freeze([
  {
    name: 'intensity',
    label: 'Intensity',
    type: 'float',
    default: 0.35,
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    name: 'tint',
    label: 'Tint',
    type: 'color',
    default: [0.2, 0.7, 1, 1],
  },
  {
    name: 'center',
    label: 'Center',
    type: 'vec2',
    default: [0.5, 0.5],
  },
  {
    name: 'showGrid',
    label: 'Grid',
    type: 'bool',
    default: true,
  },
  {
    name: 'bandCount',
    label: 'Bands',
    type: 'int',
    default: 8,
    min: 2,
    max: 24,
    step: 1,
  },
  {
    name: 'holdFrame',
    label: 'Frame Hold',
    type: 'frame',
    default: 12,
  },
  {
    name: 'holdTime',
    label: 'Time Hold',
    type: 'time',
    default: 0.25,
  },
  {
    name: 'blendMode',
    label: 'Blend Mode',
    type: 'enum',
    default: 'soft',
    options: [
      { label: 'Soft', value: 'soft' },
      { label: 'Invert Lift', value: 'invert-lift' },
    ],
  },
  {
    name: 'u_source',
    label: 'Source Frame',
    type: 'textureRef',
    default: { kind: 'clip-frame' },
  },
] satisfies readonly ShaderUniformDefinition[]);

export const CLIP_LOCAL_SHADER_CANARY_TEXTURES: ShaderTextureSchema = Object.freeze([
  {
    name: 'u_source',
    label: 'Clip frame',
    uniform: 'u_source',
    sourceKind: 'clip-frame',
    required: true,
    filter: 'linear',
    wrap: 'clamp-to-edge',
    colorSpace: 'srgb',
  },
]);

const diagnosticUniform = {
  name: 'invalidShape',
  label: 'Invalid Shape',
  type: 'matrix3',
  default: [1, 0, 0, 0, 1, 0, 0, 0, 1],
} as unknown as ShaderUniformDefinition;

export const clipLocalShaderCanaryContribution: ShaderContribution = {
  id: CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID as any,
  kind: 'shader',
  shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
  label: 'Clip Local Shader Canary',
  description: 'Preview-only clip-local WebGL shader canary with editable uniforms and clip-frame texture input.',
  pass: {
    kind: 'clip',
    inputTextureUniform: 'u_source',
    colorSpace: 'srgb',
    alpha: 'preserve',
  },
  source: CLIP_LOCAL_SHADER_CANARY_SOURCE,
  uniforms: CLIP_LOCAL_SHADER_CANARY_UNIFORMS,
  textures: CLIP_LOCAL_SHADER_CANARY_TEXTURES,
  fallback: 'bypass',
  order: 50,
};

export const clipLocalShaderDiagnosticContribution: ShaderContribution = {
  id: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID as any,
  kind: 'shader',
  shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
  label: 'Clip Local Shader Canary Diagnostic',
  description: 'Deliberately invalid clip-local shader contribution used to prove diagnostic surfacing.',
  pass: 'clip',
  source: CLIP_LOCAL_SHADER_CANARY_SOURCE,
  uniforms: Object.freeze([diagnosticUniform]),
  fallback: 'transparent',
  order: 51,
};

export function startClipLocalShaderCanary(
  ctx: ExtensionContext,
  options: ClipLocalShaderCanaryOptions = {},
): ClipLocalShaderCanaryController {
  const handles: DisposeHandle[] = [];
  let disposed = false;

  handles.push(ctx.shaders.registerShader(
    CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
    CLIP_LOCAL_SHADER_CANARY_SOURCE,
    {
      label: clipLocalShaderCanaryContribution.label,
      pass: clipLocalShaderCanaryContribution.pass,
      uniforms: CLIP_LOCAL_SHADER_CANARY_UNIFORMS,
      textures: CLIP_LOCAL_SHADER_CANARY_TEXTURES,
      fallback: clipLocalShaderCanaryContribution.fallback,
    },
  ));

  if (options.includeDiagnosticShader !== false) {
    handles.push(ctx.shaders.registerShader(
      CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      CLIP_LOCAL_SHADER_CANARY_SOURCE,
      {
        label: clipLocalShaderDiagnosticContribution.label,
        pass: clipLocalShaderDiagnosticContribution.pass,
        uniforms: clipLocalShaderDiagnosticContribution.uniforms,
        fallback: clipLocalShaderDiagnosticContribution.fallback,
      },
    ));
  }

  ctx.services.diagnostics.report({
    severity: 'info',
    code: 'clip-local-shader-canary/activated',
    message: 'Clip-local shader canary registered through ctx.shaders.',
    detail: {
      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
      diagnosticShaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
    },
  });

  const controller: ClipLocalShaderCanaryController = {
    extensionId: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID,
    shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
    contribution: clipLocalShaderCanaryContribution,
    diagnosticShaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
    diagnosticContribution: clipLocalShaderDiagnosticContribution,
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const handle of handles.splice(0).reverse()) {
        handle.dispose();
      }
    },
  };

  options.onReady?.(controller);
  return controller;
}

export function createClipLocalShaderCanaryExtension(
  options: ClipLocalShaderCanaryOptions = {},
): ReighExtension {
  return defineExtension({
    manifest: {
      id: CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID as any,
      version: CLIP_LOCAL_SHADER_CANARY_VERSION,
      label: 'Clip Local Shader Canary',
      description: 'Canary for clip-local WebGL shader registration, graph-owned assignment/keyframes, diagnostics, preview, picker, and planner behavior.',
      apiVersion: 1,
      contributions: [
        clipLocalShaderCanaryContribution,
        clipLocalShaderDiagnosticContribution,
      ],
      messages: {
        'activation.started': 'Clip Local Shader Canary activating.',
        'activation.ready': 'Clip Local Shader Canary ready.',
        'activation.disposed': 'Clip Local Shader Canary disposed.',
      },
    } as any,
    activate(ctx) {
      return startClipLocalShaderCanary(ctx, options);
    },
  });
}

export const clipLocalShaderCanaryExtension = createClipLocalShaderCanaryExtension();

export default clipLocalShaderCanaryExtension;
