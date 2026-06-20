// @vitest-environment jsdom

import { fireEvent, render, screen, within } from '@testing-library/react';
import type { ComponentProps, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClipPanel } from '@/tools/video-editor/components/PropertiesPanel/ClipPanel';
import type { ShaderEffectRegistryRecord, ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
import type { ResolvedTimelineClip, ResolvedTimelineConfig, TrackDefinition } from '@/tools/video-editor/types';

const useEffectResourcesMock = vi.hoisted(() => vi.fn());
const useOptionalShaderEffectRegistryContextMock = vi.hoisted(() => vi.fn());

vi.mock('@/tools/video-editor/hooks/useEffectResources', () => ({
  useEffectResources: () => useEffectResourcesMock(),
}));

vi.mock('@/tools/video-editor/shaders/registry/index.ts', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/shaders/registry/index.ts')>(
    '@/tools/video-editor/shaders/registry/index.ts',
  );
  return {
    ...actual,
    useOptionalShaderEffectRegistryContext: () => useOptionalShaderEffectRegistryContextMock(),
  };
});

vi.mock('@/shared/components/ui/input', () => ({
  Input: ({ onChange, value, ...props }: ComponentProps<'input'>) => (
    <input value={value} onChange={onChange} {...props} />
  ),
}));

vi.mock('@/shared/components/ui/textarea', () => ({
  Textarea: ({ onChange, value, ...props }: ComponentProps<'textarea'>) => (
    <textarea value={value} onChange={onChange} {...props} />
  ),
}));

vi.mock('@/shared/components/ui/number-input', () => ({
  NumberInput: ({ onChange, value, min, max, step }: {
    onChange: (value: number | null) => void;
    value: number | null;
    min?: number;
    max?: number;
    step?: number;
  }) => (
    <input
      role="spinbutton"
      value={value ?? ''}
      min={min}
      max={max}
      step={step}
      onChange={(event) => onChange(event.currentTarget.value === '' ? null : Number(event.currentTarget.value))}
    />
  ),
}));

vi.mock('@/shared/components/ui/select', async () => {
  const actual = await vi.importActual<typeof import('@/shared/components/ui/select')>('@/shared/components/ui/select');
  return {
    ...actual,
    SelectContent: ({ children }: { children: ReactNode }) => <div data-testid="select-content">{children}</div>,
  };
});

vi.mock('@/tools/video-editor/contexts/DataProviderContext', () => ({
  useVideoEditorRuntime: () => ({ userId: 'user-1' }),
}));

vi.mock('@/tools/video-editor/components/EffectCreatorPanel', () => ({
  EffectCreatorPanel: () => null,
}));

vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
  THEME_PACKAGE_REGISTRY: {},
}), { virtual: true });

vi.mock('@/tools/video-editor/sequences/registry', () => ({
  isAvailableSequenceClipType: () => false,
  getAvailableSequenceMetadata: () => undefined,
  resolveAvailableClipType: () => ({ status: 'unknown' }),
}));

const track: TrackDefinition = {
  id: 'V1',
  type: 'video',
  kind: 'visual',
  label: 'Video 1',
};

function clip(overrides?: Partial<ResolvedTimelineClip>): ResolvedTimelineClip {
  return {
    id: 'clip-1',
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 5,
    assetEntry: {
      id: 'asset-1',
      type: 'image/png',
      src: 'https://example.test/image.png',
    },
    ...overrides,
  };
}

function renderability({
  browserExport = 'supported',
  workerExport = 'supported',
}: {
  browserExport?: 'supported' | 'blocked';
  workerExport?: 'supported' | 'blocked';
} = {}): ShaderEffectRegistryRecord['renderability'] {
  return {
    defaultRoute: 'preview',
    determinism: browserExport === 'supported' || workerExport === 'supported'
      ? 'deterministic'
      : 'preview-only',
    capabilities: [
      { route: 'preview', status: 'supported', determinism: 'deterministic' },
      {
        route: 'browser-export',
        status: browserExport,
        determinism: browserExport === 'supported' ? 'deterministic' : 'preview-only',
        ...(browserExport === 'blocked' ? { blockerReason: 'preview-only' } : {}),
      },
      {
        route: 'worker-export',
        status: workerExport,
        determinism: workerExport === 'supported' ? 'deterministic' : 'preview-only',
        ...(workerExport === 'blocked' ? { blockerReason: 'preview-only' } : {}),
      },
    ],
  };
}

function shaderRecord(overrides: Partial<ShaderEffectRegistryRecord> = {}): ShaderEffectRegistryRecord {
  return {
    shaderId: 'shader.clip.bloom',
    ownerExtensionId: 'ext.shader',
    contributionId: 'clip-bloom',
    label: 'Clip Bloom',
    source: {
      kind: 'inline',
      fragment: 'void main() { gl_FragColor = vec4(1.0); }',
    },
    pass: 'clip',
    uniforms: [
      { name: 'intensity', label: 'Intensity', type: 'float', default: 0.5 },
    ],
    provenance: 'bundled-extension',
    renderability: renderability(),
    status: 'active',
    ...overrides,
  };
}

function shaderSnapshot(records: readonly ShaderEffectRegistryRecord[]): ShaderEffectRegistrySnapshot {
  return {
    records,
    diagnostics: [],
    get: (shaderId, ownerExtensionId) => records.find((record) => (
      record.shaderId === shaderId && record.ownerExtensionId === ownerExtensionId
    )),
    getByLookup: (lookup) => records.find((record) => (
      record.shaderId === lookup.shaderId && record.ownerExtensionId === lookup.ownerExtensionId
    )),
    has: (shaderId, ownerExtensionId) => records.some((record) => (
      record.shaderId === shaderId && record.ownerExtensionId === ownerExtensionId
    )),
    hasByLookup: (lookup) => records.some((record) => (
      record.shaderId === lookup.shaderId && record.ownerExtensionId === lookup.ownerExtensionId
    )),
  };
}

function defaultProps(overrides?: Partial<ComponentProps<typeof ClipPanel>>) {
  return {
    clip: clip(),
    track,
    deviceClass: 'desktop' as const,
    interactionMode: 'move' as const,
    precisionEnabled: false,
    hasPredecessor: false,
    onChange: vi.fn(),
    onResetPosition: vi.fn(),
    onClose: vi.fn(),
    onDelete: vi.fn(),
    onToggleMute: vi.fn(),
    onSplitAtPlayhead: vi.fn(),
    onMoveTrackUp: vi.fn(),
    onMoveTrackDown: vi.fn(),
    onSetInteractionMode: vi.fn(),
    onSetPrecisionEnabled: vi.fn(),
    compositionWidth: 1920,
    compositionHeight: 1080,
    registry: {} as ResolvedTimelineConfig['registry'],
    activeTab: 'effects' as const,
    setActiveTab: vi.fn(),
    ...overrides,
  };
}

function getShaderSection(): HTMLElement {
  return screen.getByTestId('clip-panel-shader-section');
}

describe('ClipPanel shader picker', () => {
  beforeEach(() => {
    useEffectResourcesMock.mockReturnValue({
      effects: [],
      entrance: [],
      exit: [],
      continuous: [],
      canCreateEffect: false,
      canUpdateEffect: false,
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([]),
    });
  });

  it('shows valid clip shader entries with Shader and pass badges and hides postprocess records', () => {
    const valid = shaderRecord();
    const postprocess = shaderRecord({
      shaderId: 'shader.post.grade',
      contributionId: 'post-grade',
      label: 'Post Grade',
      pass: 'postprocess',
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([valid, postprocess]),
    });

    render(<ClipPanel {...defaultProps()} />);

    const section = getShaderSection();
    fireEvent.click(within(section).getByRole('combobox'));

    const option = screen.getByRole('option', { name: /Clip Bloom/ });
    expect(option).toHaveTextContent('Shader');
    expect(option).toHaveTextContent('Clip');
    expect(screen.queryByRole('option', { name: /Post Grade/ })).not.toBeInTheDocument();

    expect(option).not.toHaveAttribute('data-disabled');
  });

  it('keeps invalid shader entries visible but disabled', () => {
    const onChange = vi.fn();
    const invalid = shaderRecord({
      shaderId: 'shader.clip.broken',
      contributionId: 'clip-broken',
      label: 'Broken Shader',
      status: 'error',
      diagnostics: [{
        severity: 'error',
        code: 'shader/compile-error',
        message: 'Fragment shader failed to compile.',
      }],
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([invalid]),
    });

    render(<ClipPanel {...defaultProps({ onChange })} />);

    const section = getShaderSection();
    fireEvent.click(within(section).getByRole('combobox'));

    const option = screen.getByRole('option', { name: /Broken Shader/ });
    expect(option).toHaveTextContent('(invalid)');
    expect(option).toHaveAttribute('data-disabled');

    fireEvent.click(option);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('rejects selecting a second clip shader with an explicit diagnostic', () => {
    const onChange = vi.fn();
    const existing = shaderRecord();
    const next = shaderRecord({
      shaderId: 'shader.clip.edge',
      contributionId: 'clip-edge',
      label: 'Clip Edge',
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([existing, next]),
    });

    render(<ClipPanel {...defaultProps({
      onChange,
      clip: clip({
        app: {
          shader: {
            scope: 'clip',
            extensionId: 'ext.shader',
            contributionId: 'clip-bloom',
            shaderId: 'shader.clip.bloom',
          },
        },
      }),
    })} />);

    const section = getShaderSection();
    fireEvent.click(within(section).getByRole('combobox'));
    const option = screen.getByRole('option', { name: /Clip Edge/ });
    fireEvent.pointerDown(option);
    fireEvent.pointerUp(option);

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId('clip-panel-shader-diagnostic')).toHaveTextContent(
      'Cannot add shader "shader.clip.edge" to clip "clip-1" because shader "shader.clip.bloom" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
    );
  });

  it('labels selected preview-only shader entries with a Preview only badge', () => {
    const previewOnly = shaderRecord({
      renderability: renderability({ browserExport: 'blocked', workerExport: 'blocked' }),
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([previewOnly]),
    });

    render(<ClipPanel {...defaultProps({
      clip: clip({
        app: {
          shader: {
            scope: 'clip',
            extensionId: 'ext.shader',
            contributionId: 'clip-bloom',
            shaderId: 'shader.clip.bloom',
          },
        },
      }),
    })} />);

    const section = getShaderSection();
    expect(within(section).getAllByText('Preview only').length).toBeGreaterThan(0);
  });

  it('labels selected export-blocked shader entries with blocked route badges', () => {
    const blocked = shaderRecord({
      renderability: renderability({ browserExport: 'blocked', workerExport: 'supported' }),
    });
    useOptionalShaderEffectRegistryContextMock.mockReturnValue({
      registry: {},
      snapshot: shaderSnapshot([blocked]),
    });

    render(<ClipPanel {...defaultProps({
      clip: clip({
        app: {
          shader: {
            scope: 'clip',
            extensionId: 'ext.shader',
            contributionId: 'clip-bloom',
            shaderId: 'shader.clip.bloom',
          },
        },
      }),
    })} />);

    const section = getShaderSection();
    expect(within(section).getByText('No browser export')).toBeInTheDocument();
  });
});
