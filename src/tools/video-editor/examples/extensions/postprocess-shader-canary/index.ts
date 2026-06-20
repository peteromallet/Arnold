/**
 * postprocess-shader-canary - M13 timeline postprocess WebGL shader canary.
 *
 * Exercises the public shader SDK path for timeline-scope postprocess shaders:
 * manifest-declared ShaderContribution records, ctx.shaders.registerShader(),
 * uniform defaults, textureRef metadata, registry diagnostics, preview-only
 * renderability, browser preview output, inspector persistence, and M12 planner
 * blockers.
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

export const POSTPROCESS_SHADER_CANARY_EXTENSION_ID = 'com.reigh.examples.postprocess-shader-canary';
export const POSTPROCESS_SHADER_CANARY_SHADER_ID = 'shader.postprocessCanary.scanline';
export const POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID = 'postprocess-shader-canary';
export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID = 'shader.postprocessCanary.diagnostic';
export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID = 'postprocess-shader-canary-diagnostic';
export const POSTPROCESS_SHADER_CANARY_VERSION = '1.0.0';

export interface PostprocessShaderCanaryOptions {
  readonly includeDiagnosticShader?: boolean;
  readonly onReady?: (controller: PostprocessShaderCanaryController) => void;
}

export interface PostprocessShaderCanaryController extends DisposeHandle {
  readonly extensionId: string;
  readonly shaderId: string;
  readonly contribution: ShaderContribution;
  readonly diagnosticShaderId: string;
  readonly diagnosticContribution: ShaderContribution;
}

export const POSTPROCESS_SHADER_CANARY_SOURCE: ShaderInlineSource = {
  kind: 'inline',
  fragment: `
precision mediump float;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_frame;
uniform float intensity;
uniform vec4 tint;
uniform vec3 lift;
uniform vec2 center;
uniform bool showScanlines;
uniform int bandCount;
uniform float holdFrame;
uniform float holdTime;
uniform float blendMode;

varying vec2 vUv;

void main() {
  vec2 pixel = vUv * u_resolution;
  float bands = max(float(bandCount), 1.0);
  float scanline = showScanlines ? step(0.5, fract((pixel.y + u_frame + holdFrame) / bands)) : 0.0;
  float radial = 1.0 - smoothstep(0.0, 0.85, distance(vUv, center));
  float pulse = 0.5 + 0.5 * sin((u_time + holdTime) * 6.2831853);
  vec3 base = vec3(vUv.x, vUv.y, pulse);
  vec3 graded = mix(base, tint.rgb + lift * 0.15, clamp(intensity * radial, 0.0, 1.0));
  graded = mix(graded, vec3(1.0) - graded, clamp(blendMode, 0.0, 1.0) * 0.12);
  gl_FragColor = vec4(mix(graded, vec3(1.0), scanline * 0.16), tint.a);
}
`,
};

export const POSTPROCESS_SHADER_CANARY_UNIFORMS: ShaderUniformSchema = Object.freeze([
  {
    name: 'intensity',
    label: 'Intensity',
    type: 'float',
    default: 0.42,
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    name: 'tint',
    label: 'Tint',
    type: 'color',
    default: [1, 0.45, 0.2, 1],
  },
  {
    name: 'lift',
    label: 'Lift',
    type: 'vec3',
    default: [0.15, 0.25, 0.45],
  },
  {
    name: 'center',
    label: 'Center',
    type: 'vec2',
    default: [0.5, 0.5],
  },
  {
    name: 'showScanlines',
    label: 'Scanlines',
    type: 'bool',
    default: true,
  },
  {
    name: 'bandCount',
    label: 'Bands',
    type: 'int',
    default: 6,
    min: 2,
    max: 24,
    step: 1,
  },
  {
    name: 'holdFrame',
    label: 'Frame Hold',
    type: 'frame',
    default: 9,
  },
  {
    name: 'holdTime',
    label: 'Time Hold',
    type: 'time',
    default: 0.2,
  },
  {
    name: 'blendMode',
    label: 'Blend Mode',
    type: 'enum',
    default: 'screen',
    options: [
      { label: 'Screen', value: 'screen' },
      { label: 'Invert Drift', value: 'invert-drift' },
    ],
  },
  {
    name: 'u_composite',
    label: 'Composite Frame',
    type: 'textureRef',
    default: { kind: 'clip-frame' },
  },
] satisfies readonly ShaderUniformDefinition[]);

export const POSTPROCESS_SHADER_CANARY_TEXTURES: ShaderTextureSchema = Object.freeze([
  {
    name: 'u_composite',
    label: 'Composite frame',
    uniform: 'u_composite',
    sourceKind: 'clip-frame',
    required: false,
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

export const postprocessShaderCanaryContribution: ShaderContribution = {
  id: POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID as any,
  kind: 'shader',
  shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
  label: 'Postprocess Shader Canary',
  description: 'Preview-only timeline postprocess WebGL shader canary with editable uniforms.',
  pass: {
    kind: 'postprocess',
    inputTextureUniform: 'u_composite',
    colorSpace: 'srgb',
    alpha: 'preserve',
  },
  source: POSTPROCESS_SHADER_CANARY_SOURCE,
  uniforms: POSTPROCESS_SHADER_CANARY_UNIFORMS,
  textures: POSTPROCESS_SHADER_CANARY_TEXTURES,
  fallback: 'bypass',
  order: 60,
};

export const postprocessShaderDiagnosticContribution: ShaderContribution = {
  id: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID as any,
  kind: 'shader',
  shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
  label: 'Postprocess Shader Canary Diagnostic',
  description: 'Deliberately invalid postprocess shader contribution used to prove diagnostic surfacing.',
  pass: 'postprocess',
  source: POSTPROCESS_SHADER_CANARY_SOURCE,
  uniforms: Object.freeze([diagnosticUniform]),
  fallback: 'transparent',
  order: 61,
};

export function startPostprocessShaderCanary(
  ctx: ExtensionContext,
  options: PostprocessShaderCanaryOptions = {},
): PostprocessShaderCanaryController {
  const handles: DisposeHandle[] = [];
  let disposed = false;

  handles.push(ctx.shaders.registerShader(
    POSTPROCESS_SHADER_CANARY_SHADER_ID,
    POSTPROCESS_SHADER_CANARY_SOURCE,
    {
      label: postprocessShaderCanaryContribution.label,
      pass: postprocessShaderCanaryContribution.pass,
      uniforms: POSTPROCESS_SHADER_CANARY_UNIFORMS,
      textures: POSTPROCESS_SHADER_CANARY_TEXTURES,
      fallback: postprocessShaderCanaryContribution.fallback,
    },
  ));

  if (options.includeDiagnosticShader !== false) {
    handles.push(ctx.shaders.registerShader(
      POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
      POSTPROCESS_SHADER_CANARY_SOURCE,
      {
        label: postprocessShaderDiagnosticContribution.label,
        pass: postprocessShaderDiagnosticContribution.pass,
        uniforms: postprocessShaderDiagnosticContribution.uniforms,
        fallback: postprocessShaderDiagnosticContribution.fallback,
      },
    ));
  }

  ctx.services.diagnostics.report({
    severity: 'info',
    code: 'postprocess-shader-canary/activated',
    message: 'Postprocess shader canary registered through ctx.shaders.',
    detail: {
      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
      diagnosticShaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
    },
  });

  const controller: PostprocessShaderCanaryController = {
    extensionId: POSTPROCESS_SHADER_CANARY_EXTENSION_ID,
    shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
    contribution: postprocessShaderCanaryContribution,
    diagnosticShaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
    diagnosticContribution: postprocessShaderDiagnosticContribution,
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

export function createPostprocessShaderCanaryExtension(
  options: PostprocessShaderCanaryOptions = {},
): ReighExtension {
  return defineExtension({
    manifest: {
      id: POSTPROCESS_SHADER_CANARY_EXTENSION_ID as any,
      version: POSTPROCESS_SHADER_CANARY_VERSION,
      label: 'Postprocess Shader Canary',
      description: 'M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.',
      apiVersion: 1,
      contributions: [
        postprocessShaderCanaryContribution,
        postprocessShaderDiagnosticContribution,
      ],
      messages: {
        'activation.started': 'Postprocess Shader Canary activating.',
        'activation.ready': 'Postprocess Shader Canary ready.',
        'activation.disposed': 'Postprocess Shader Canary disposed.',
      },
    } as any,
    activate(ctx) {
      return startPostprocessShaderCanary(ctx, options);
    },
  });
}

export const postprocessShaderCanaryExtension = createPostprocessShaderCanaryExtension();

export default postprocessShaderCanaryExtension;
