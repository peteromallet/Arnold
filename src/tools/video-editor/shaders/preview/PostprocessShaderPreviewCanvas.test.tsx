// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
import type { TimelinePostprocessShaderMetadata } from '@/tools/video-editor/types/index.ts';
import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';

const previewSurfaceInstances: Array<{
  input: Record<string, unknown>;
  surface: {
    canvas: HTMLCanvasElement;
    setUniformValues: ReturnType<typeof vi.fn>;
    setTextureValues: ReturnType<typeof vi.fn>;
    resize: ReturnType<typeof vi.fn>;
    renderFrame: ReturnType<typeof vi.fn>;
    dispose: ReturnType<typeof vi.fn>;
  };
}> = [];

vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
  createWebGLShaderPreviewSurface: vi.fn((input: Record<string, unknown>) => {
    const surface = {
      canvas: document.createElement('canvas'),
      setUniformValues: vi.fn(),
      setTextureValues: vi.fn(),
      resize: vi.fn(),
      renderFrame: vi.fn(() => true),
      dispose: vi.fn(),
    };
    previewSurfaceInstances.push({ input, surface });
    return surface;
  }),
}));

function shader(overrides: Partial<TimelinePostprocessShaderMetadata> = {}): TimelinePostprocessShaderMetadata {
  return {
    scope: 'postprocess',
    extensionId: 'ext.shader',
    contributionId: 'ext.shader.post',
    shaderId: 'shader.preview.post',
    uniforms: { intensity: 0.7 },
    textures: {
      source: { kind: 'clip-frame' },
    },
    ...overrides,
  };
}

function record(overrides: Partial<ShaderEffectRegistryRecord> = {}): ShaderEffectRegistryRecord {
  return {
    shaderId: 'shader.preview.post',
    ownerExtensionId: 'ext.shader',
    contributionId: 'ext.shader.post',
    label: 'Preview Postprocess Shader',
    source: {
      kind: 'inline',
      fragment: 'precision mediump float; void main(){ gl_FragColor = vec4(1.0); }',
    },
    pass: 'postprocess',
    uniforms: [
      { name: 'intensity', label: 'Intensity', type: 'float', default: 0.5 },
    ],
    textures: [
      { name: 'source', uniform: 'u_source', sourceKind: 'clip-frame' },
    ],
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'preview-only',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'preview-only',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

describe('PostprocessShaderPreviewCanvas', () => {
  afterEach(() => {
    previewSurfaceInstances.length = 0;
    vi.restoreAllMocks();
  });

  it('creates a preview surface for an active inline postprocess shader and renders the current timeline frame', () => {
    const { rerender } = render(
      <PostprocessShaderPreviewCanvas
        shader={shader({
          keyframes: {
            intensity: [
              { time: 0, value: 0.25, interpolation: 'linear' },
              { time: 2, value: 0.75, interpolation: 'linear' },
            ],
          },
        })}
        record={record()}
        timeSeconds={1.5}
        frame={45}
        width={1920}
        height={1080}
      />,
    );

    expect(screen.getByTestId('postprocess-shader-preview-canvas')).toHaveAttribute('data-shader-scope', 'postprocess');
    expect(previewSurfaceInstances).toHaveLength(1);
    expect(previewSurfaceInstances[0].input).toMatchObject({
      shaderId: 'shader.preview.post',
      extensionId: 'ext.shader',
      contributionId: 'ext.shader.post',
      width: 1920,
      height: 1080,
      uniformValues: { intensity: 0.7 },
      textureValues: { source: { kind: 'clip-frame' } },
    });
    expect(previewSurfaceInstances[0].surface.setUniformValues).toHaveBeenLastCalledWith({ intensity: 0.625 });
    expect(previewSurfaceInstances[0].surface.renderFrame).toHaveBeenLastCalledWith(1.5, 45);

    rerender(
      <PostprocessShaderPreviewCanvas
        shader={shader({ uniforms: { intensity: 0.25 } })}
        record={record()}
        timeSeconds={2}
        frame={60}
        width={1280}
        height={720}
      />,
    );

    expect(screen.getByTestId('postprocess-shader-preview-canvas')).toHaveAttribute('data-shader-frame', '60');
    const activeInstance = previewSurfaceInstances.at(-1);
    expect(activeInstance?.surface.setUniformValues).toHaveBeenLastCalledWith({ intensity: 0.25 });
    expect(activeInstance?.surface.resize).toHaveBeenLastCalledWith(1280, 720);
    expect(activeInstance?.surface.renderFrame).toHaveBeenLastCalledWith(2, 60);
  });

  it('renders nothing for disabled, inactive, non-inline, or non-postprocess records', () => {
    const cases: Array<{
      name: string;
      shader: TimelinePostprocessShaderMetadata;
      record: ShaderEffectRegistryRecord;
    }> = [
      { name: 'disabled', shader: shader({ enabled: false }), record: record() },
      { name: 'inactive', shader: shader(), record: record({ status: 'inactive' }) },
      {
        name: 'module source',
        shader: shader(),
        record: record({
          source: {
            kind: 'module',
            specifier: './shader.ts',
          },
        }),
      },
      { name: 'clip pass', shader: shader(), record: record({ pass: 'clip' }) },
    ];

    for (const item of cases) {
      const { unmount } = render(
        <PostprocessShaderPreviewCanvas
          shader={item.shader}
          record={item.record}
          timeSeconds={1}
          frame={30}
          width={1920}
          height={1080}
          testId={`postprocess-${item.name}`}
        />,
      );

      expect(screen.queryByTestId(`postprocess-${item.name}`)).not.toBeInTheDocument();
      unmount();
    }
    expect(previewSurfaceInstances).toHaveLength(0);
  });
});
