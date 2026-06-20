import type { ExtensionDiagnostic, ShaderUniformDefinition } from '@reigh/editor-sdk';
import type {
  TimelineClipShaderMetadata,
  TimelinePostprocessShaderMetadata,
  TimelineShaderTextureRef,
  TimelineShaderTextureValues,
  TimelineShaderUniformValues,
} from '@/tools/video-editor/types/index.ts';
import type { RenderRoute } from '@/tools/video-editor/runtime/renderability.ts';
import type {
  ShaderEffectRegistryRecord,
  ShaderEffectRegistrySnapshot,
} from '@/tools/video-editor/shaders/registry/types.ts';

export const NO_SHADER = '__none__';

export type ShaderPickerEntry = {
  record: ShaderEffectRegistryRecord;
  passKind: string;
  disabled: boolean;
  hidden: boolean;
  blockedRoutes: readonly RenderRoute[];
  previewOnly: boolean;
  errorDiagnostics: readonly ExtensionDiagnostic[];
};

export function getShaderPassKind(record: ShaderEffectRegistryRecord): string {
  return typeof record.pass === 'string' ? record.pass : record.pass.kind;
}

export function getShaderPassLabel(record: ShaderEffectRegistryRecord): string {
  const passKind = getShaderPassKind(record);
  return passKind.charAt(0).toUpperCase() + passKind.slice(1);
}

export function getShaderBlockedRoutes(record: ShaderEffectRegistryRecord): readonly RenderRoute[] {
  return record.renderability.capabilities
    .filter((capability) => capability.route !== 'preview' && capability.status === 'blocked')
    .map((capability) => capability.route);
}

export function isShaderPreviewOnly(record: ShaderEffectRegistryRecord): boolean {
  const hasPreview = record.renderability.capabilities.some(
    (capability) => capability.route === 'preview' && capability.status === 'supported',
  );
  const hasBrowserExport = record.renderability.capabilities.some(
    (capability) => capability.route === 'browser-export' && capability.status === 'supported',
  );
  const hasWorkerExport = record.renderability.capabilities.some(
    (capability) => capability.route === 'worker-export' && capability.status === 'supported',
  );

  return hasPreview && !hasBrowserExport && !hasWorkerExport;
}

export function listClipShaderPickerEntries(
  snapshot: ShaderEffectRegistrySnapshot | undefined,
): ShaderPickerEntry[] {
  return (snapshot?.records ?? [])
    .map((record): ShaderPickerEntry => {
      const passKind = getShaderPassKind(record);
      const errorDiagnostics = (record.diagnostics ?? []).filter(
        (diagnostic) => diagnostic.severity === 'error',
      );
      return {
        record,
        passKind,
        disabled: record.status !== 'active' || errorDiagnostics.length > 0,
        hidden: passKind !== 'clip',
        blockedRoutes: getShaderBlockedRoutes(record),
        previewOnly: isShaderPreviewOnly(record),
        errorDiagnostics,
      };
    })
    .filter((entry) => !entry.hidden);
}

function getUniformDefault(uniform: ShaderUniformDefinition): unknown {
  if (uniform.default !== undefined) {
    return uniform.default;
  }

  switch (uniform.type) {
    case 'float':
    case 'frame':
    case 'time':
      return uniform.min ?? 0;
    case 'int':
      return Math.trunc(uniform.min ?? 0);
    case 'bool':
      return false;
    case 'vec2':
      return [0, 0];
    case 'vec3':
      return [0, 0, 0];
    case 'vec4':
    case 'color':
      return [1, 1, 1, 1];
    case 'enum':
      return uniform.options?.[0]?.value ?? '';
    case 'textureRef':
      return undefined;
    default:
      return '';
  }
}

function isTimelineTextureRef(value: unknown): value is TimelineShaderTextureRef {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }

  const kind = (value as { kind?: unknown }).kind;
  return kind === 'clip-frame'
    || kind === 'static-image-asset'
    || kind === 'live-generated-frame';
}

function getTextureRefDefault(uniform: ShaderUniformDefinition): TimelineShaderTextureRef {
  return isTimelineTextureRef(uniform.default) ? uniform.default : { kind: 'clip-frame' };
}

export function materializeShaderUniformDefaults(
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): TimelineShaderUniformValues | undefined {
  const defaults = Object.fromEntries((uniforms ?? [])
    .filter((uniform) => uniform.type !== 'textureRef')
    .map((uniform) => [uniform.name, getUniformDefault(uniform)]));

  return Object.keys(defaults).length > 0 ? defaults : undefined;
}

export function materializeShaderTextureDefaults(
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): TimelineShaderTextureValues | undefined {
  const defaults = Object.fromEntries((uniforms ?? [])
    .filter((uniform) => uniform.type === 'textureRef')
    .map((uniform) => [uniform.name, getTextureRefDefault(uniform)]));

  return Object.keys(defaults).length > 0 ? defaults : undefined;
}

export function createTimelineClipShaderMetadata(
  record: ShaderEffectRegistryRecord,
): TimelineClipShaderMetadata {
  const uniforms = materializeShaderUniformDefaults(record.uniforms);
  const textures = materializeShaderTextureDefaults(record.uniforms);

  return {
    scope: 'clip',
    extensionId: record.ownerExtensionId ?? '',
    contributionId: record.contributionId,
    shaderId: record.shaderId,
    label: record.label,
    enabled: true,
    ...(uniforms ? { uniforms } : {}),
    ...(textures ? { textures } : {}),
    metadata: {
      uniformPreset: 'defaults',
      pickerSource: 'clip-panel',
    },
  };
}

export function createTimelinePostprocessShaderMetadata(
  record: ShaderEffectRegistryRecord,
): TimelinePostprocessShaderMetadata {
  const uniforms = materializeShaderUniformDefaults(record.uniforms);
  const textures = materializeShaderTextureDefaults(record.uniforms);

  return {
    scope: 'postprocess',
    extensionId: record.ownerExtensionId ?? '',
    contributionId: record.contributionId,
    shaderId: record.shaderId,
    label: record.label,
    enabled: true,
    ...(uniforms ? { uniforms } : {}),
    ...(textures ? { textures } : {}),
    metadata: {
      uniformPreset: 'defaults',
      pickerSource: 'timeline-postprocess-canary',
    },
  };
}
