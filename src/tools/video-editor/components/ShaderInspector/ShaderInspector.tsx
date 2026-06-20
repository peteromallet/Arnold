import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/shared/components/ui/button.tsx';
import { Switch } from '@/shared/components/ui/switch.tsx';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm.tsx';
import { updateClipInConfig } from '@/tools/video-editor/lib/editor-utils.ts';
import { getTimelineClipShader } from '@/tools/video-editor/lib/timeline-domain.ts';
import type { TimelineEditorOpsContextValue } from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
  TimelineClipShaderMetadata,
  TimelinePostprocessShaderMetadata,
  TimelineShaderBaseMetadata,
  TimelineShaderTextureRef,
  TimelineShaderTextureValues,
  TimelineShaderUniformValues,
} from '@/tools/video-editor/types/index.ts';
import type { ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
import type { ExtensionDiagnostic, ShaderSourceDescriptor, ShaderUniformDefinition } from '@reigh/editor-sdk';

type ShaderInspectorCompareMode = 'shader' | 'bypass';

export interface ShaderInspectorProps {
  clip: ResolvedTimelineClip | null;
  postprocessShader?: TimelinePostprocessShaderMetadata | null;
  resolvedConfig: ResolvedTimelineConfig | null;
  shaderSnapshot: ShaderEffectRegistrySnapshot;
  applyEdit: TimelineEditorOpsContextValue['applyEdit'];
}

export const SHADER_INSPECTOR_SPLIT_VIEW_DEFERRED_MESSAGE =
  'Split view comparison is deferred for M13; the inspector stores A/B intent without activating a split preview.';

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
    default:
      return '';
  }
}

export function getShaderUniformDefaults(
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): TimelineShaderUniformValues {
  return Object.fromEntries((uniforms ?? [])
    .filter((uniform) => uniform.type !== 'textureRef')
    .map((uniform) => [
      uniform.name,
      getUniformDefault(uniform),
    ]));
}

function getEditableShaderUniformValues(
  values: TimelineShaderUniformValues | undefined,
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): TimelineShaderUniformValues {
  if (!values) {
    return {};
  }

  const editableNames = new Set((uniforms ?? [])
    .filter((uniform) => uniform.type !== 'textureRef')
    .map((uniform) => uniform.name));

  return Object.fromEntries(Object.entries(values)
    .filter(([name]) => editableNames.has(name)));
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

function getShaderTextureDefaults(
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): TimelineShaderTextureValues {
  return Object.fromEntries((uniforms ?? [])
    .filter((uniform) => uniform.type === 'textureRef')
    .map((uniform) => [uniform.name, getTextureRefDefault(uniform)]));
}

function createSourceHash(source: ShaderSourceDescriptor): string {
  if (source.kind === 'inline') {
    return `inline:${source.vertex ?? ''}:${source.fragment}`;
  }

  return `module:${source.specifier}:${source.exportName ?? 'default'}`;
}

function hasDiagnosticError(diagnostics: readonly ExtensionDiagnostic[] | undefined): boolean {
  return diagnostics?.some((diagnostic) => diagnostic.severity === 'error') ?? false;
}

type EditableShaderMetadata = TimelineClipShaderMetadata | TimelinePostprocessShaderMetadata;

function getCompareMode(shader: TimelineShaderBaseMetadata): ShaderInspectorCompareMode {
  if (shader.enabled === false) {
    return 'bypass';
  }

  return shader.metadata?.inspectorCompareMode === 'bypass' ? 'bypass' : 'shader';
}

function getUniformPreset(shader: TimelineShaderBaseMetadata): 'custom' | 'defaults' {
  return shader.metadata?.uniformPreset === 'defaults' ? 'defaults' : 'custom';
}

function collectTextureRefDiagnostics(
  shader: EditableShaderMetadata,
  uniforms: readonly ShaderUniformDefinition[] | undefined,
): readonly ExtensionDiagnostic[] {
  return (uniforms ?? [])
    .filter((uniform) => uniform.type === 'textureRef')
    .map((uniform) => ({
      severity: 'warning' as const,
      code: 'shader-inspector/texture-ref-deferred',
      message: `Texture uniform "${uniform.label ?? uniform.name}" requires host texture binding; inspector editing is deferred for M13.`,
      detail: {
        ownerExtensionId: shader.extensionId,
        contributionId: shader.contributionId,
        shaderId: shader.shaderId,
        fieldName: uniform.name,
        unsupportedType: 'textureRef',
      },
    }));
}

function collectShaderDiagnostics(
  shader: EditableShaderMetadata,
  shaderSnapshot: ShaderEffectRegistrySnapshot,
  recordDiagnostics: readonly ExtensionDiagnostic[] | undefined,
): readonly ExtensionDiagnostic[] {
  return [
    ...(recordDiagnostics ?? []),
    ...shaderSnapshot.diagnostics.filter((diagnostic) => {
      const detail = diagnostic.detail as Record<string, unknown> | undefined;
      return detail?.shaderId === shader.shaderId
        || detail?.contributionId === shader.contributionId
        || detail?.ownerExtensionId === shader.extensionId;
    }),
  ];
}

function sameJson(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function ShaderInspector({
  clip,
  postprocessShader,
  resolvedConfig,
  shaderSnapshot,
  applyEdit,
}: ShaderInspectorProps) {
  const shader = clip ? getTimelineClipShader(clip) : postprocessShader ?? undefined;
  const record = shader
    ? shaderSnapshot.get(shader.shaderId, shader.extensionId)
    : undefined;
  const diagnostics = shader && record
    ? collectShaderDiagnostics(shader, shaderSnapshot, record.diagnostics)
    : [];
  const textureRefDiagnostics = shader
    ? collectTextureRefDiagnostics(shader, record?.uniforms)
    : [];
  const registryError = (record?.status === 'error') || hasDiagnosticError(diagnostics);
  const defaultUniforms = useMemo(
    () => getShaderUniformDefaults(record?.uniforms),
    [record?.uniforms],
  );
  const defaultTextures = useMemo(
    () => getShaderTextureDefaults(record?.uniforms),
    [record?.uniforms],
  );
  const persistedUniforms = useMemo(
    () => getEditableShaderUniformValues(shader?.uniforms, record?.uniforms),
    [record?.uniforms, shader?.uniforms],
  );
  const initialUniforms = useMemo(
    () => ({ ...defaultUniforms, ...persistedUniforms }),
    [defaultUniforms, persistedUniforms],
  );
  const [values, setValues] = useState<Record<string, unknown>>(initialUniforms);
  const [schemaDiagnostics, setSchemaDiagnostics] = useState<ExtensionDiagnostic[]>([]);

  useEffect(() => {
    setValues(initialUniforms);
    setSchemaDiagnostics([]);
  }, [
    initialUniforms,
    shader?.extensionId,
    shader?.contributionId,
    shader?.shaderId,
  ]);

  if (!resolvedConfig || !shader || (shader.scope === 'clip' && !clip)) {
    return null;
  }

  const missingRecord = !record;
  const allDiagnostics = [
    ...diagnostics,
    ...textureRefDiagnostics,
    ...schemaDiagnostics,
    ...(missingRecord
      ? [{
          severity: 'error' as const,
          code: 'shader-inspector/missing-registry-record',
          message: `Shader "${shader.shaderId}" is assigned to this clip but is not registered.`,
        }]
      : []),
  ];
  const hasErrors = registryError || missingRecord || hasDiagnosticError(schemaDiagnostics);
  const isDirty = !sameJson(values, initialUniforms);
  const enabled = shader.enabled !== false;
  const compareMode = getCompareMode(shader);

  const persist = (
    nextUniforms: Record<string, unknown>,
    preset: 'custom' | 'defaults',
    nextEnabled = enabled,
    nextCompareMode = compareMode,
  ) => {
    if (!record) {
      return;
    }

    const nextShader: EditableShaderMetadata = {
      ...shader,
      label: shader.label ?? record.label,
      uniforms: nextUniforms,
      ...((Object.keys(defaultTextures).length > 0 || shader.textures)
        ? { textures: { ...defaultTextures, ...(shader.textures ?? {}) } }
        : {}),
      enabled: nextEnabled,
      sourceHash: createSourceHash(record.source),
      metadata: {
        ...(shader.metadata ?? {}),
        uniformPreset: preset,
        inspectorCompareMode: nextCompareMode,
      },
    };
    if (nextShader.scope === 'clip') {
      const nextConfig = updateClipInConfig(resolvedConfig, clip!.id, (currentClip) => ({
        ...currentClip,
        app: {
          ...(currentClip.app ?? {}),
          shader: nextShader,
        },
      }));

      applyEdit({ type: 'config', resolvedConfig: nextConfig }, { selectedClipId: clip!.id });
      return;
    }

    const nextConfig = {
      ...resolvedConfig,
      app: {
        ...(resolvedConfig.app ?? {}),
        shaderPostprocess: nextShader,
      },
    };

    applyEdit({ type: 'config', resolvedConfig: nextConfig }, { selectedClipId: null, selectedTrackId: null });
  };

  const setEnabled = (nextEnabled: boolean) => {
    persist(
      values,
      getUniformPreset(shader),
      nextEnabled,
      nextEnabled ? 'shader' : 'bypass',
    );
  };

  return (
    <section
      className="space-y-3 rounded-xl border border-border bg-card/80 p-3"
      data-testid="shader-inspector"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {shader.scope === 'postprocess' ? 'Postprocess Shader' : 'Shader'}
          </div>
          <div className="truncate text-sm font-medium text-foreground">
            {record?.label ?? shader.label ?? shader.shaderId}
          </div>
          <div className="text-xs text-muted-foreground">
            {shader.extensionId} / {shader.contributionId}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
          <span>{enabled ? 'Enabled' : 'Bypassed'}</span>
          <Switch
            checked={enabled}
            onCheckedChange={setEnabled}
            disabled={missingRecord}
            data-testid="shader-inspector-enabled"
          />
        </div>
      </div>

      {allDiagnostics.length > 0 && (
        <div className="space-y-2">
          {allDiagnostics.map((diagnostic, index) => (
            <div
              key={`${diagnostic.code}:${index}`}
              className="rounded-lg border border-destructive/40 bg-destructive/5 p-3"
              data-testid={`shader-inspector-diagnostic-${index}`}
              role={diagnostic.severity === 'error' ? 'alert' : 'status'}
            >
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-destructive">
                {diagnostic.code}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {diagnostic.message}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2 rounded-lg border border-border/70 bg-background/60 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium text-foreground">
              A/B
            </div>
            <div className="text-xs text-muted-foreground">
              {compareMode === 'bypass' ? 'Bypass' : 'Shader'}
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              type="button"
              variant={compareMode === 'bypass' ? 'secondary' : 'outline'}
              size="sm"
              onClick={() => persist(values, getUniformPreset(shader), false, 'bypass')}
              disabled={missingRecord}
              aria-pressed={compareMode === 'bypass'}
              data-testid="shader-inspector-compare-bypass"
            >
              A: Bypass
            </Button>
            <Button
              type="button"
              variant={compareMode === 'shader' ? 'secondary' : 'outline'}
              size="sm"
              onClick={() => persist(values, getUniformPreset(shader), true, 'shader')}
              disabled={missingRecord}
              aria-pressed={compareMode === 'shader'}
              data-testid="shader-inspector-compare-shader"
            >
              B: Shader
            </Button>
          </div>
        </div>
        {/* M13 stores A/B intent on host metadata; live split preview is planned for a later preview bridge. */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled
          title={SHADER_INSPECTOR_SPLIT_VIEW_DEFERRED_MESSAGE}
          aria-label={SHADER_INSPECTOR_SPLIT_VIEW_DEFERRED_MESSAGE}
          data-testid="shader-inspector-split-view-deferred"
        >
          Split
        </Button>
      </div>

      {record?.uniforms && record.uniforms.length > 0 ? (
        <SchemaForm
          schema={record.uniforms}
          values={values}
          onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))}
          diagnostics={diagnostics}
          onDiagnostics={(nextDiagnostics) => {
            setSchemaDiagnostics(nextDiagnostics.filter((diagnostic) => diagnostic.code !== 'schema/texture-ref-unsupported'));
          }}
          disabled={hasErrors}
        />
      ) : (
        <div className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs text-muted-foreground">
          This shader does not expose editable uniforms.
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            setValues(defaultUniforms);
            persist(defaultUniforms, 'defaults');
          }}
          disabled={hasErrors || missingRecord}
        >
          Reset defaults
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => persist(values, 'custom')}
          disabled={hasErrors || missingRecord || !isDirty}
        >
          Apply shader
        </Button>
      </div>
    </section>
  );
}
