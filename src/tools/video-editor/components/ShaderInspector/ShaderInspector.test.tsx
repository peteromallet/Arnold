// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ShaderInspector } from '@/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx';
import type { ShaderEffectRegistryRecord, ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
import type { ResolvedTimelineClip, ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

const baseClip: ResolvedTimelineClip = {
  id: 'clip-1',
  at: 0,
  track: 'V1',
  clipType: 'media',
  app: {
    shader: {
      scope: 'clip',
      extensionId: 'com.example.shader',
      contributionId: 'wash',
      shaderId: 'wash',
      uniforms: { intensity: 0.25 },
    },
  },
};

const baseConfig: ResolvedTimelineConfig = {
  output: { resolution: '1280x720', file: 'preview.mp4', fps: 30 },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips: [baseClip],
  registry: {},
};

function createRecord(
  overrides: Partial<ShaderEffectRegistryRecord> = {},
): ShaderEffectRegistryRecord {
  return {
    ownerExtensionId: 'com.example.shader',
    contributionId: 'wash',
    shaderId: 'wash',
    label: 'Color wash',
    source: {
      kind: 'inline',
      fragment: 'void main() { gl_FragColor = vec4(1.0); }',
    },
    pass: 'clip',
    uniforms: [
      {
        name: 'intensity',
        label: 'Intensity',
        type: 'float',
        min: 0,
        max: 1,
        step: 0.01,
        default: 0.5,
      },
    ],
    provenance: 'bundled-extension',
    renderability: {
      determinism: 'preview-only',
      capabilities: [],
    },
    status: 'active',
    ...overrides,
  };
}

function createSnapshot(record: ShaderEffectRegistryRecord): ShaderEffectRegistrySnapshot {
  return {
    records: [record],
    diagnostics: [],
    get: (shaderId, ownerExtensionId) => (
      shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId ? record : undefined
    ),
    getByLookup: (lookup) => (
      lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId ? record : undefined
    ),
    has: (shaderId, ownerExtensionId) => shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId,
    hasByLookup: (lookup) => lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId,
  };
}

function renderInspector({
  clip = baseClip,
  config = baseConfig,
  record = createRecord(),
  applyEdit = vi.fn(),
}: {
  clip?: ResolvedTimelineClip;
  config?: ResolvedTimelineConfig;
  record?: ShaderEffectRegistryRecord;
  applyEdit?: ReturnType<typeof vi.fn>;
} = {}) {
  render(
    <ShaderInspector
      clip={clip}
      resolvedConfig={config}
      shaderSnapshot={createSnapshot(record)}
      applyEdit={applyEdit}
    />,
  );

  return { applyEdit };
}

describe('ShaderInspector', () => {
  it('renders clip-local shader controls and persists edited uniforms on timeline metadata', () => {
    const { applyEdit } = renderInspector();

    const input = screen.getByTestId('schema-form-widget-intensity') as HTMLInputElement;
    expect(input.value).toBe('0.25');

    fireEvent.change(input, { target: { value: '0.75' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));

    expect(applyEdit).toHaveBeenCalledTimes(1);
    const mutation = applyEdit.mock.calls[0][0];
    const nextShader = mutation.resolvedConfig.clips[0].app.shader;
    expect(nextShader.uniforms).toEqual({ intensity: 0.75 });
    expect(nextShader.metadata.uniformPreset).toBe('custom');
    expect(nextShader.metadata.inspectorCompareMode).toBe('shader');
    expect(nextShader.sourceHash).toContain('void main()');
    expect(applyEdit.mock.calls[0][1]).toEqual({ selectedClipId: 'clip-1' });
  });

  it('resets and persists uniform defaults as a defaults preset', () => {
    const { applyEdit } = renderInspector();

    fireEvent.click(screen.getByRole('button', { name: 'Reset defaults' }));

    const mutation = applyEdit.mock.calls[0][0];
    const nextShader = mutation.resolvedConfig.clips[0].app.shader;
    expect(nextShader.uniforms).toEqual({ intensity: 0.5 });
    expect(nextShader.metadata.uniformPreset).toBe('defaults');
    expect(nextShader.metadata.inspectorCompareMode).toBe('shader');
  });

  it('resets defaults without leaving the active bypass compare state', () => {
    const applyEdit = vi.fn();
    const clip: ResolvedTimelineClip = {
      ...baseClip,
      app: {
        shader: {
          ...baseClip.app!.shader!,
          enabled: false,
          metadata: { uniformPreset: 'custom', inspectorCompareMode: 'bypass' },
        },
      },
    };

    renderInspector({
      clip,
      config: { ...baseConfig, clips: [clip] },
      applyEdit,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Reset defaults' }));

    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
    expect(nextShader.uniforms).toEqual({ intensity: 0.5 });
    expect(nextShader.enabled).toBe(false);
    expect(nextShader.metadata.uniformPreset).toBe('defaults');
    expect(nextShader.metadata.inspectorCompareMode).toBe('bypass');
  });

  it('persists bypass through host-owned shader metadata without touching unrelated clip app data', () => {
    const applyEdit = vi.fn();
    const clip: ResolvedTimelineClip = {
      ...baseClip,
      app: {
        editorFlag: 'keep-me',
        shader: {
          ...baseClip.app!.shader!,
          metadata: { uniformPreset: 'custom', existing: true },
        },
      },
    };
    const config: ResolvedTimelineConfig = {
      ...baseConfig,
      clips: [clip],
      registry: { untouched: { file: 'asset.mp4', src: '/asset.mp4', type: 'video' } },
    };

    renderInspector({ clip, config, applyEdit });

    fireEvent.click(screen.getByTestId('shader-inspector-enabled'));

    expect(applyEdit).toHaveBeenCalledTimes(1);
    const mutation = applyEdit.mock.calls[0][0];
    const nextClip = mutation.resolvedConfig.clips[0];
    expect(nextClip.app.editorFlag).toBe('keep-me');
    expect(mutation.resolvedConfig.registry).toBe(config.registry);
    expect(nextClip.app.shader.enabled).toBe(false);
    expect(nextClip.app.shader.uniforms).toEqual({ intensity: 0.25 });
    expect(nextClip.app.shader.metadata).toMatchObject({
      existing: true,
      uniformPreset: 'custom',
      inspectorCompareMode: 'bypass',
    });
  });

  it('persists A/B compare state and leaves split view explicitly deferred', () => {
    const { applyEdit } = renderInspector();

    const splitView = screen.getByTestId('shader-inspector-split-view-deferred');
    expect(splitView).toBeDisabled();
    expect(splitView).toHaveAttribute(
      'title',
      'Split view comparison is deferred for M13; the inspector stores A/B intent without activating a split preview.',
    );
    expect(splitView).toHaveAttribute(
      'aria-label',
      'Split view comparison is deferred for M13; the inspector stores A/B intent without activating a split preview.',
    );
    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByTestId('shader-inspector-compare-bypass'));

    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
    expect(nextShader.enabled).toBe(false);
    expect(nextShader.metadata.inspectorCompareMode).toBe('bypass');
    expect(nextShader.metadata.uniformPreset).toBe('custom');
  });

  it('restores shader A/B mode through host-owned metadata without touching unrelated clip app data', () => {
    const applyEdit = vi.fn();
    const clip: ResolvedTimelineClip = {
      ...baseClip,
      app: {
        editorFlag: 'keep-me',
        shader: {
          ...baseClip.app!.shader!,
          enabled: false,
          metadata: { uniformPreset: 'defaults', inspectorCompareMode: 'bypass' },
        },
      },
    };
    const config: ResolvedTimelineConfig = { ...baseConfig, clips: [clip] };

    renderInspector({ clip, config, applyEdit });

    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByTestId('shader-inspector-compare-shader'));

    const nextClip = applyEdit.mock.calls[0][0].resolvedConfig.clips[0];
    expect(nextClip.app.editorFlag).toBe('keep-me');
    expect(nextClip.app.shader.enabled).toBe(true);
    expect(nextClip.app.shader.metadata.uniformPreset).toBe('defaults');
    expect(nextClip.app.shader.metadata.inspectorCompareMode).toBe('shader');
  });

  it('derives bypass A/B state from host-owned enabled metadata when compare metadata is absent', () => {
    const applyEdit = vi.fn();
    const clip: ResolvedTimelineClip = {
      ...baseClip,
      app: {
        shader: {
          ...baseClip.app!.shader!,
          enabled: false,
        },
      },
    };

    renderInspector({ clip, config: { ...baseConfig, clips: [clip] }, applyEdit });

    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByRole('button', { name: 'Reset defaults' }));

    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
    expect(nextShader.enabled).toBe(false);
    expect(nextShader.metadata.inspectorCompareMode).toBe('bypass');
    expect(nextShader.metadata.uniformPreset).toBe('defaults');
  });

  it('surfaces textureRef diagnostics without blocking supported uniform edits', () => {
    const { applyEdit } = renderInspector({
      record: createRecord({
        uniforms: [
          {
            name: 'intensity',
            label: 'Intensity',
            type: 'float',
            min: 0,
            max: 1,
            step: 0.01,
            default: 0.5,
          },
          {
            name: 'u_texture',
            label: 'Texture',
            type: 'textureRef',
            default: { kind: 'clip-frame' },
          },
        ],
      }),
    });

    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveTextContent(
      'shader-inspector/texture-ref-deferred',
    );
    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveAttribute('role', 'status');
    expect(screen.getByTestId('schema-form-unsupported-u_texture')).toHaveTextContent('Texture');

    fireEvent.change(screen.getByTestId('schema-form-widget-intensity'), { target: { value: '0.75' } });

    const applyButton = screen.getByRole('button', { name: 'Apply shader' });
    expect(applyButton).not.toBeDisabled();
    fireEvent.click(applyButton);

    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
    expect(nextShader.uniforms).toEqual({ intensity: 0.75 });
    expect(nextShader.textures).toEqual({
      u_texture: { kind: 'clip-frame' },
    });
  });

  it('preserves existing host textureRef bindings while resetting editable uniforms', () => {
    const applyEdit = vi.fn();
    const clip: ResolvedTimelineClip = {
      ...baseClip,
      app: {
        shader: {
          ...baseClip.app!.shader!,
          textures: {
            u_texture: { kind: 'static-image-asset', ref: 'asset-42' },
          },
        },
      },
    };

    renderInspector({
      clip,
      config: { ...baseConfig, clips: [clip] },
      record: createRecord({
        uniforms: [
          {
            name: 'intensity',
            label: 'Intensity',
            type: 'float',
            min: 0,
            max: 1,
            step: 0.01,
            default: 0.5,
          },
          {
            name: 'u_texture',
            label: 'Texture',
            type: 'textureRef',
            default: { kind: 'clip-frame' },
          },
        ],
      }),
      applyEdit,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Reset defaults' }));

    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
    expect(nextShader.uniforms).toEqual({ intensity: 0.5 });
    expect(nextShader.textures).toEqual({
      u_texture: { kind: 'static-image-asset', ref: 'asset-42' },
    });
  });

  it('preserves persisted uniform values when a valid source edit updates registry defaults', () => {
    const applyEdit = vi.fn();
    const { rerender } = render(
      <ShaderInspector
        clip={baseClip}
        resolvedConfig={baseConfig}
        shaderSnapshot={createSnapshot(createRecord())}
        applyEdit={applyEdit}
      />,
    );

    expect((screen.getByTestId('schema-form-widget-intensity') as HTMLInputElement).value).toBe('0.25');

    rerender(
      <ShaderInspector
        clip={baseClip}
        resolvedConfig={baseConfig}
        shaderSnapshot={createSnapshot(createRecord({
          source: {
            kind: 'inline',
            fragment: 'void main() { gl_FragColor = vec4(0.5); }',
          },
          uniforms: [{
            name: 'intensity',
            label: 'Intensity',
            type: 'float',
            default: 0.9,
          }],
        }))}
        applyEdit={applyEdit}
      />,
    );

    expect((screen.getByTestId('schema-form-widget-intensity') as HTMLInputElement).value).toBe('0.25');
  });

  it('disables apply when shader diagnostics contain errors', () => {
    renderInspector({
      record: createRecord({
        status: 'error',
        diagnostics: [{
          severity: 'error',
          code: 'shader/compile-error',
          message: 'Fragment shader failed to compile.',
        }],
      }),
    });

    expect(screen.getByRole('button', { name: 'Apply shader' })).toBeDisabled();
    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveTextContent('shader/compile-error');
  });
});
