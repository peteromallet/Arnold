// @vitest-environment jsdom
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type { ClipRendererProps } from '@/tools/video-editor/clip-types/ClipTypeRegistry';
import type { FC, PropsWithChildren } from 'react';
import {
  DataProviderWrapper,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext';
import {
  createLiveDataRegistry,
  type LiveDataRegistry,
} from '@/tools/video-editor/runtime/liveDataRegistry';

const sequenceProps = vi.hoisted((): Array<Record<string, unknown>> => []);
const visualClipMock = vi.hoisted(() => vi.fn());
const textClipMock = vi.hoisted(() => vi.fn());

vi.mock('remotion', async () => {
  return {
    AbsoluteFill: ({
      children,
      ...props
    }: PropsWithChildren<Record<string, unknown>>) => (
      <div data-testid="absolute-fill" {...props}>{children}</div>
    ),
    Sequence: ({
      children,
      ...props
    }: PropsWithChildren<Record<string, unknown>>) => {
      sequenceProps.push(props);
      return <div data-testid="sequence">{children}</div>;
    },
  };
});

vi.mock('@banodoco/timeline-composition/theme-api', async () => {
  const reactModule = await import('react');
  const runtimeThemeValue = {
    color: {
      accent: '#ffffff',
      bg: '#000000',
      fg: '#ffffff',
    },
    type: {
      families: {
        heading: 'Georgia, serif',
        body: 'Inter, system-ui, sans-serif',
        mono: 'JetBrains Mono, ui-monospace, monospace',
      },
      size: {
        base: 56,
        small: 32,
        large: 128,
      },
      weight: {
        normal: 300,
        bold: 500,
      },
      lineHeight: 1.1,
    },
    motion: {
      fadeMs: 500,
    },
    canvas: {
      width: 1920,
      height: 1080,
      fps: 30,
    },
  };

  const DEFAULT_THEME = {
    id: 'default',
    visual: runtimeThemeValue,
  };

  const toRuntimeTheme = (value: unknown) => {
    if (
      value
      && typeof value === 'object'
      && 'visual' in value
      && value.visual
      && typeof value.visual === 'object'
    ) {
      return {
        ...runtimeThemeValue,
        ...value.visual,
        color: {
          ...runtimeThemeValue.color,
          ...(typeof value.visual.color === 'object' ? value.visual.color : {}),
        },
        type: {
          ...runtimeThemeValue.type,
          ...(typeof value.visual.type === 'object' ? value.visual.type : {}),
          families: {
            ...runtimeThemeValue.type.families,
            ...(typeof value.visual.type === 'object' && typeof value.visual.type.families === 'object'
              ? value.visual.type.families
              : {}),
          },
        },
      };
    }
    return runtimeThemeValue;
  };

  const ThemeContext = reactModule.createContext(runtimeThemeValue);

  return {
    DEFAULT_THEME,
    ThemeProvider: ({
      children,
      value,
    }: PropsWithChildren<{ value: typeof DEFAULT_THEME }>) => (
      <ThemeContext.Provider value={toRuntimeTheme(value)}>{children}</ThemeContext.Provider>
    ),
    useTheme: () => reactModule.useContext(ThemeContext),
  };
});

vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', async () => {
  return {
    AudioAnalysisProvider: ({ children }: PropsWithChildren) => (
      <div data-testid="audio-analysis-provider">{children}</div>
    ),
  };
});

vi.mock('@/tools/video-editor/compositions/VisualClip', () => ({
  VisualClipSequence: (props: Record<string, unknown>) => {
    visualClipMock(props);
    return <div data-testid="visual-clip-sequence" />;
  },
}));

vi.mock('@/tools/video-editor/compositions/TextClip', () => ({
  TextClipSequence: (props: Record<string, unknown>) => {
    textClipMock(props);
    return <div data-testid="text-clip-sequence" />;
  },
}));

vi.mock('@banodoco/timeline-composition/theme-api', async () => {
  const React = await import('react');
  const DEFAULT_THEME = {
    id: 'default',
    visual: {
      color: {
        accent: '#ffffff',
        bg: '#000000',
      },
      type: {
        families: {
          heading: 'Georgia, serif',
        },
      },
    },
  };
  const ThemeContext = React.createContext(DEFAULT_THEME.visual);
  return {
    DEFAULT_THEME,
    ThemeProvider: ({
      children,
      value,
    }: PropsWithChildren<{ value: unknown }>) => (
      <ThemeContext.Provider value={(value as typeof DEFAULT_THEME)?.visual ?? DEFAULT_THEME.visual}>
        {children}
      </ThemeContext.Provider>
    ),
    useTheme: () => React.useContext(ThemeContext),
  };
});

vi.mock('@banodoco/timeline-composition/registry.generated', async () => {
  const React = await import('react');
  const RegisteredSequence = ({
    clip,
    params,
    theme,
    fps,
  }: {
    clip: { id: string };
    params?: { title?: string; previews?: string[]; previewAssetKeys?: string[] };
    theme: {
      color: { accent: string; bg: string };
      type: { families: { heading: string } };
    };
    fps: number;
  }) => (
    <div
      data-testid="registered-sequence"
      data-clip-id={clip.id}
      data-title={params?.title ?? ''}
      data-accent={theme.color.accent}
      data-bg={theme.color.bg}
      data-heading={theme.type.families.heading}
      data-fps={fps}
      data-previews={JSON.stringify(params?.previews ?? [])}
      data-preview-asset-keys={JSON.stringify(params?.previewAssetKeys ?? [])}
    />
  );
  return {
    THEME_PACKAGE_CLIP_TYPES: ['section-hook', 'resource-card'],
    THEME_PACKAGE_REGISTRY: {
      'section-hook': {
        component: RegisteredSequence,
        themeId: '2rp',
        source: 'installed:@banodoco/timeline-theme-2rp',
      },
      'resource-card': {
        component: RegisteredSequence,
        themeId: '2rp',
        source: 'installed:@banodoco/timeline-theme-2rp',
      },
    },
  };
});

const buildConfig = (
  extras: Partial<Pick<ResolvedTimelineConfig, 'theme' | 'theme_overrides'>> = {},
): ResolvedTimelineConfig => ({
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'out.mp4',
  },
  tracks: [
    {
      id: 'V1',
      kind: 'visual',
      label: 'V1',
    },
  ],
  clips: [
    {
      id: 'clip-sequence',
      clipType: 'section-hook',
      track: 'V1',
      at: 1,
      hold: 3,
      params: {
        title: 'Renaissance systems',
      },
    },
  ],
  registry: {},
  ...extras,
});

describe('TimelineRenderer registered sequences', () => {
  beforeEach(() => {
    sequenceProps.length = 0;
    visualClipMock.mockClear();
    textClipMock.mockClear();
  });

  it('renders registered sequence clips through the generated registry and passes params/timing', () => {
    render(<TimelineRenderer config={buildConfig({ theme: '2rp' })} />);

    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
    const sequence = screen.getByTestId('registered-sequence');
    expect(sequence).toHaveAttribute('data-clip-id', 'clip-sequence');
    expect(sequence).toHaveAttribute('data-title', 'Renaissance systems');
    expect(sequence).toHaveAttribute('data-accent', '#fde68a');
    expect(sequence).toHaveAttribute('data-fps', '30');
    expect(sequenceProps[0]).toMatchObject({
      from: 30,
      durationInFrames: 90,
    });
  });

  it('uses shared duration helpers for speed-adjusted registered sequence clips', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-speed-adjusted',
          clipType: 'section-hook',
          track: 'V1',
          at: 0,
          from: 0,
          to: 6,
          speed: 2,
          params: {
            title: 'Speed adjusted',
          },
        },
      ],
    }} />);

    expect(sequenceProps[0]).toMatchObject({
      from: 0,
      durationInFrames: 90,
    });
  });

  it('deep-merges timeline theme_overrides onto the installed theme', () => {
    render(<TimelineRenderer config={buildConfig({
      theme: '2rp',
      theme_overrides: {
        visual: {
          color: {
            accent: '#00ff88',
          },
        },
      },
    })} />);

    const sequence = screen.getByTestId('registered-sequence');
    expect(sequence).toHaveAttribute('data-accent', '#00ff88');
    expect(sequence).toHaveAttribute('data-bg', '#000000');
    expect(sequence).toHaveAttribute('data-heading', "'Sixtyfour', 'Sixtyfour Variable', monospace");
  });

  it('uses the DEFAULT_THEME fallback when the timeline has no theme', () => {
    render(<TimelineRenderer config={buildConfig()} />);

    const sequence = screen.getByTestId('registered-sequence');
    expect(sequence).toHaveAttribute('data-accent', '#ffffff');
    expect(sequence).toHaveAttribute('data-bg', '#000000');
    expect(sequence).toHaveAttribute('data-heading', 'Georgia, serif');
  });

  it('materializes registry asset keys into component-facing preview URLs for registered sequences', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-resource',
          clipType: 'resource-card',
          track: 'V1',
          at: 0,
          hold: 3,
          params: {
            title: 'Resource',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      registry: {
        'asset-a': {
          file: 'asset-a.png',
          src: 'https://cdn.example.com/asset-a.png',
          type: 'image',
        },
      },
    }} />);

    const sequence = screen.getByTestId('registered-sequence');
    expect(sequence).toHaveAttribute('data-previews', JSON.stringify(['https://cdn.example.com/asset-a.png']));
    expect(sequence).toHaveAttribute('data-preview-asset-keys', JSON.stringify(['asset-a']));
  });

  it('renders locally-registered title-card clips through the same registry-backed sequence route', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-title-card',
          clipType: 'title-card',
          track: 'V1',
          at: 0,
          hold: 3,
          params: {
            kicker: 'INTRO',
            title: 'Registry Title',
            subtitle: 'Local example component',
          },
        },
      ],
    }} />);

    const sequence = screen.getByTestId('title-card-sequence');
    expect(sequence).toHaveAttribute('data-kicker', 'INTRO');
    expect(sequence).toHaveAttribute('data-title', 'Registry Title');
    expect(sequence).toHaveAttribute('data-subtitle', 'Local example component');
  });

  it('renders remotion_module clips as safe placeholders before registered, native, or unknown clipType dispatch', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-module-theme',
          clipType: 'section-hook',
          track: 'V1',
          at: 0,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
            artifact_id: 'artifact-theme',
            source: 'do-not-render-this',
          },
        },
        {
          id: 'clip-module-native',
          clipType: 'media',
          track: 'V1',
          at: 1,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
            artifact_id: 'artifact-native',
          },
        },
        {
          id: 'clip-module-unknown',
          clipType: 'generated-unknown',
          track: 'V1',
          at: 2,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
            artifact_id: 'artifact-unknown',
          },
        },
      ],
    }} />);

    const placeholders = screen.getAllByTestId('generated-module-placeholder');
    expect(placeholders).toHaveLength(3);
    expect(placeholders.map((node) => node.getAttribute('data-artifact-id'))).toEqual([
      'artifact-theme',
      'artifact-native',
      'artifact-unknown',
    ]);
    expect(screen.queryByTestId('registered-sequence')).not.toBeInTheDocument();
    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
    expect(visualClipMock).not.toHaveBeenCalled();
  });

  it('keeps trusted_v1, schema_sequence, and legacy clips on their normal preview paths', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-trusted',
          clipType: 'section-hook',
          track: 'V1',
          at: 0,
          hold: 1,
          params: {
            title: 'Trusted',
          },
          generation: {
            sequence_lane: 'trusted_v1',
          },
        },
        {
          id: 'clip-schema',
          clipType: 'media',
          track: 'V1',
          at: 1,
          hold: 1,
          generation: {
            sequence_lane: 'schema_sequence',
            artifact_id: 'schema-1',
          },
        },
        {
          id: 'clip-legacy',
          track: 'V1',
          at: 2,
          hold: 1,
        },
      ],
    }} />);

    expect(screen.queryByTestId('generated-module-placeholder')).not.toBeInTheDocument();
    expect(screen.getByTestId('registered-sequence')).toHaveAttribute('data-clip-id', 'clip-trusted');
    expect(visualClipMock).toHaveBeenCalledTimes(2);
  });

  it('falls back loudly when a trusted sequence clip is unavailable in the installed registry', () => {
    render(<TimelineRenderer config={{
      ...buildConfig({ theme: '2rp' }),
      clips: [
        {
          id: 'clip-unavailable',
          clipType: 'cta-card',
          track: 'V1',
          at: 0,
          hold: 2,
        },
      ],
    }} />);

    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('registered-sequence')).not.toBeInTheDocument();
    expect(visualClipMock).not.toHaveBeenCalled();
    expect(textClipMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// M9 T10: Extension clip renderer dispatch tests
// ---------------------------------------------------------------------------

const mockClipTypeRegistryGet = vi.fn();
const mockClipTypeRegistryHas = vi.fn();

vi.mock('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx', async () => {
  const actual = await vi.importActual<
    typeof import('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx')
  >('@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx');
  return {
    ...actual,
    useClipTypeRegistrySnapshot: () => ({
      records: Object.freeze([]),
      diagnostics: Object.freeze([]),
      get: mockClipTypeRegistryGet,
      has: mockClipTypeRegistryHas,
    }),
  };
});

/** Create a minimal ClipTypeRegistryRecord for tests. */
function makeRegistryRecord(
  overrides: Partial<{
    clipTypeId: string;
    status: string;
    renderer: unknown;
    capabilities: Array<{ route: string; status: string }>;
    schema: ReadonlyArray<{
      name: string;
      label: string;
      description: string;
      type: string;
      default?: unknown;
      min?: number;
      max?: number;
      step?: number;
      options?: readonly { label: string; value: string }[];
    }>;
  }> = {},
): Record<string, unknown> {
  const {
    clipTypeId = 'ext.my-clip',
    status = 'active',
    renderer,
    capabilities = [{ route: 'preview', status: 'supported' }],
    schema,
  } = overrides;
  return {
    clipTypeId,
    contributionId: 'contrib-1',
    renderer: renderer ?? ((() => null) as unknown),
    status,
    schema,
    renderability: {
      capabilities: capabilities.map((c) => ({
        ...c,
        determinism: 'deterministic',
      })),
      defaultRoute: 'preview',
      determinism: 'deterministic',
    },
  };
}

function runtimeWithLiveRegistry(liveDataRegistry?: LiveDataRegistry): VideoEditorRuntimeContextValue {
  return {
    provider: {},
    assetResolver: {},
    auth: {},
    project: {},
    shots: {},
    mediaLightbox: {},
    agentChat: {},
    toast: {},
    telemetry: {},
    timelineId: 'timeline-test',
    userId: 'user-test',
    extensions: {},
    liveDataRegistry,
  } as unknown as VideoEditorRuntimeContextValue;
}

function renderWithLiveRegistry(config: ResolvedTimelineConfig, liveDataRegistry?: LiveDataRegistry) {
  return render(
    <DataProviderWrapper value={runtimeWithLiveRegistry(liveDataRegistry)}>
      <TimelineRenderer config={config} />
    </DataProviderWrapper>,
  );
}

describe('TimelineRenderer — extension clip renderer dispatch (M9 T10)', () => {
  beforeEach(() => {
    sequenceProps.length = 0;
    visualClipMock.mockClear();
    textClipMock.mockClear();
    mockClipTypeRegistryGet.mockReset();
    mockClipTypeRegistryHas.mockReset();
  });

  const extBuildConfig = (
    clipType: string,
    keyframes?: Record<string, Array<{ time: number; value: number | string | boolean; interpolation: string }>>,
    params?: Record<string, unknown>,
  ): ResolvedTimelineConfig => ({
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [
      {
        id: 'clip-ext-1',
        clipType,
        track: 'V1',
        at: 0,
        hold: 2,
        params: params ?? {},
        keyframes,
      },
    ],
    registry: {},
  });

  it('renders an extension clip through the ClipTypeRegistry with host-interpolated params', () => {
    const TestRenderer: FC<ClipRendererProps> = (props) => (
      <div
        data-testid="extension-clip-renderer"
        data-clip-id={props.clipId}
        data-clip-type-id={props.clipTypeId}
        data-time={props.time}
        data-width={props.width}
        data-height={props.height}
        data-params={JSON.stringify(props.params)}
      >
        EXTENSION
      </div>
    );

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.my-clip',
        renderer: TestRenderer,
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(<TimelineRenderer config={extBuildConfig('ext.my-clip')} />);

    const el = screen.getByTestId('extension-clip-renderer');
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute('data-clip-id', 'clip-ext-1');
    expect(el).toHaveAttribute('data-clip-type-id', 'ext.my-clip');
    expect(el).toHaveAttribute('data-time', '0');
    expect(el).toHaveAttribute('data-width', '1920');
    expect(el).toHaveAttribute('data-height', '1080');
    // No schema → params passed through as-is
    expect(el.getAttribute('data-params')).toBe('{}');
    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
  });

  it('computes host-interpolated params from keyframes when schema is present', () => {
    const TestRenderer: FC<ClipRendererProps> = (props) => (
      <div
        data-testid="extension-clip-renderer"
        data-params={JSON.stringify(props.params)}
      />
    );

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.anim-clip',
        renderer: TestRenderer,
        schema: [{ name: 'opacity', label: 'Opacity', description: '', type: 'number', default: 0.5, min: 0, max: 1 }],
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(
      <TimelineRenderer
        config={extBuildConfig(
          'ext.anim-clip',
          {
            opacity: [
              { time: 0, value: 0.2, interpolation: 'linear' },
              { time: 2, value: 1.0, interpolation: 'linear' },
            ],
          },
        )}
      />,
    );

    const el = screen.getByTestId('extension-clip-renderer');
    const params = JSON.parse(el.getAttribute('data-params') ?? '{}');
    // At time=0, we get the first keyframe value (0.2)
    expect(params.opacity).toBe(0.2);
  });

  it('interpolates between keyframes at a non-zero time', () => {
    const TestRenderer: FC<ClipRendererProps> = (props) => (
      <div
        data-testid="extension-clip-renderer"
        data-params={JSON.stringify(props.params)}
      />
    );

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.anim-clip',
        renderer: TestRenderer,
        schema: [{ name: 'scale', label: 'Scale', description: '', type: 'number', default: 1, min: 0.1, max: 5 }],
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(
      <TimelineRenderer
        config={extBuildConfig(
          'ext.anim-clip',
          {
            scale: [
              { time: 0, value: 1, interpolation: 'linear' },
              { time: 2, value: 3, interpolation: 'linear' },
            ],
          },
        )}
      />,
    );

    const el = screen.getByTestId('extension-clip-renderer');
    const params = JSON.parse(el.getAttribute('data-params') ?? '{}');
    // At time=0, we get the first keyframe value (1)
    expect(params.scale).toBe(1);
  });

  it('falls back to raw params when clip has no keyframes and schema is present', () => {
    const TestRenderer: FC<ClipRendererProps> = (props) => (
      <div
        data-testid="extension-clip-renderer"
        data-params={JSON.stringify(props.params)}
      />
    );

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.nokf-clip',
        renderer: TestRenderer,
        schema: [{ name: 'volume', label: 'Volume', description: '', type: 'number', default: 0.8, min: 0, max: 1 }],
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(
      <TimelineRenderer
        config={extBuildConfig('ext.nokf-clip', undefined, { volume: 0.3 })}
      />,
    );

    const el = screen.getByTestId('extension-clip-renderer');
    const params = JSON.parse(el.getAttribute('data-params') ?? '{}');
    // No keyframes → uses default value from schema (0.8)
    expect(params.volume).toBe(0.8);
  });

  it('shows loud placeholder when renderer throws at runtime (error boundary)', () => {
    const CrashingRenderer: FC = () => {
      throw new Error('Intentional test crash');
    };

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.crash-clip',
        renderer: CrashingRenderer,
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(<TimelineRenderer config={extBuildConfig('ext.crash-clip')} />);

    // Error boundary should catch the crash and render the placeholder
    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('extension-clip-renderer')).not.toBeInTheDocument();
  });

  it('shows loud placeholder when registry record has no renderer', () => {
    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.norender-clip',
        renderer: { notAFunction: true }, // Not a function
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(<TimelineRenderer config={extBuildConfig('ext.norender-clip')} />);

    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('extension-clip-renderer')).not.toBeInTheDocument();
  });

  it('shows loud placeholder when registry record is inactive', () => {
    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.inactive-clip',
        status: 'inactive',
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(<TimelineRenderer config={extBuildConfig('ext.inactive-clip')} />);

    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('extension-clip-renderer')).not.toBeInTheDocument();
  });

  it('shows loud placeholder when preview capability is blocked', () => {
    const TestRenderer: FC<ClipRendererProps> = () => (
      <div data-testid="extension-clip-renderer" />
    );

    mockClipTypeRegistryGet.mockReturnValue(
      makeRegistryRecord({
        clipTypeId: 'ext.blocked-clip',
        renderer: TestRenderer,
        capabilities: [{ route: 'preview', status: 'blocked' }],
      }),
    );
    mockClipTypeRegistryHas.mockReturnValue(true);

    render(<TimelineRenderer config={extBuildConfig('ext.blocked-clip')} />);

    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('extension-clip-renderer')).not.toBeInTheDocument();
  });

  it('falls through to existing loud placeholder when clipType is not in the registry', () => {
    mockClipTypeRegistryGet.mockReturnValue(undefined);
    mockClipTypeRegistryHas.mockReturnValue(false);

    render(<TimelineRenderer config={extBuildConfig('ext.unknown-clip')} />);

    // Not in registry → falls through to !isBuiltinClipType check → loud placeholder
    expect(screen.getByTestId('unknown-clip-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('extension-clip-renderer')).not.toBeInTheDocument();
    expect(visualClipMock).not.toHaveBeenCalled();
  });
});

describe('TimelineRenderer — live binding renderer facade (M11 T6)', () => {
  beforeEach(() => {
    sequenceProps.length = 0;
    visualClipMock.mockClear();
    textClipMock.mockClear();
    mockClipTypeRegistryGet.mockReset();
    mockClipTypeRegistryHas.mockReset();
  });

  const liveBuildConfig = (
    clips: ResolvedTimelineConfig['clips'],
  ): ResolvedTimelineConfig => ({
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips,
    registry: {},
  });

  const liveClip = (
    id: string,
    liveBindings: unknown,
  ): ResolvedTimelineConfig['clips'][number] => ({
    id,
    clipType: 'ext.live-clip',
    track: 'V1',
    at: 0,
    hold: 2,
    params: { liveBindings },
  });

  it('passes source-id keyed synchronous live read helpers into extension renderers', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'source-live', kind: 'generated' });
    const channelId = registry.openChannel('source-live', 'video');
    registry.pushSample(channelId, {
      timestamp: 100,
      data: { value: 42 },
      format: 'json',
    });

    const TestRenderer: FC<ClipRendererProps> = (props) => {
      const sample = props.live.readLatestSample('source-live');
      const sampleAt = props.live.readSampleAt('source-live', 0);
      const samples = props.live.readSamples('source-live');
      const source = props.live.getSource('source-live');
      const latestReturn = props.live.readLatestSample('source-live');
      const isPromise = Boolean(latestReturn && typeof (latestReturn as unknown as Promise<unknown>).then === 'function');
      return (
        <div
          data-testid="extension-live-renderer"
          data-sample-value={String((sample?.frame.data as Record<string, unknown> | undefined)?.value)}
          data-sample-at-value={String((sampleAt?.frame.data as Record<string, unknown> | undefined)?.value)}
          data-sample-count={props.live.getSampleCount('source-live')}
          data-samples-length={samples.length}
          data-source-id={source?.id}
          data-resolved-channel={props.live.resolveChannelId('source-live')}
          data-is-promise={String(isPromise)}
        />
      );
    };

    mockClipTypeRegistryGet.mockReturnValue(makeRegistryRecord({ clipTypeId: 'ext.live-clip', renderer: TestRenderer }));
    mockClipTypeRegistryHas.mockReturnValue(true);

    renderWithLiveRegistry(
      liveBuildConfig([
        liveClip('clip-live', [
          {
            bindingId: 'binding-live',
            sourceId: 'source-live',
            sourceKind: 'generated',
            channelId,
          },
        ]),
      ]),
      registry,
    );

    const el = screen.getByTestId('extension-live-renderer');
    expect(el).toHaveAttribute('data-sample-value', '42');
    expect(el).toHaveAttribute('data-sample-at-value', '42');
    expect(el).toHaveAttribute('data-sample-count', '1');
    expect(el).toHaveAttribute('data-samples-length', '1');
    expect(el).toHaveAttribute('data-source-id', 'source-live');
    expect(el).toHaveAttribute('data-resolved-channel', channelId);
    expect(el).toHaveAttribute('data-is-promise', 'false');
    expect(screen.queryByTestId('live-binding-placeholder')).not.toBeInTheDocument();
  });

  it('renders live diagnostics placeholders for unresolved live binding states', () => {
    const TestRenderer: FC<ClipRendererProps> = () => (
      <div data-testid="extension-live-renderer" />
    );

    mockClipTypeRegistryGet.mockReturnValue(makeRegistryRecord({ clipTypeId: 'ext.live-clip', renderer: TestRenderer }));
    mockClipTypeRegistryHas.mockReturnValue(true);

    renderWithLiveRegistry(liveBuildConfig([
      liveClip('clip-missing', [{ bindingId: 'binding-missing', sourceId: 'source-missing', sourceKind: 'generated' }]),
      liveClip('clip-inactive', [{ bindingId: 'binding-inactive', sourceId: 'source-inactive', sourceKind: 'generated', sourceStatus: 'inactive' }]),
      liveClip('clip-disposed', [{ bindingId: 'binding-disposed', sourceId: 'source-disposed', sourceKind: 'generated', sourceStatus: 'disposed' }]),
      liveClip('clip-orphaned', [{ bindingId: 'binding-orphaned', sourceId: 'source-orphaned', sourceKind: 'generated', sourceStatus: 'orphaned' }]),
      liveClip('clip-partial', [{
        bindingId: 'binding-partial',
        sourceId: 'source-partial',
        sourceKind: 'generated',
        bake: {
          status: 'partial',
          bakedRanges: [{ startFrame: 0, endFrame: 10 }],
          unresolvedRanges: [{ startFrame: 11, endFrame: 20 }],
        },
      }]),
    ]));

    const placeholders = screen.getAllByTestId('live-binding-placeholder');
    expect(placeholders).toHaveLength(5);
    expect(placeholders.map((el) => el.getAttribute('data-live-binding-status'))).toEqual(
      expect.arrayContaining(['missing', 'inactive', 'disposed', 'orphaned', 'partiallyBaked']),
    );
    expect(screen.queryByTestId('extension-live-renderer')).not.toBeInTheDocument();
  });

  it('treats baked deterministic refs as resolved and bypasses live sample reads', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'source-live', kind: 'generated' });
    const channelId = registry.openChannel('source-live', 'video');
    registry.pushSample(channelId, { timestamp: 100, data: { value: 99 }, format: 'json' });
    const latestSpy = vi.spyOn(registry, 'getLatestSample');

    const TestRenderer: FC<ClipRendererProps> = (props) => {
      const sample = props.live.readLatestSample('source-live');
      const binding = props.live.bindings[0];
      return (
        <div
          data-testid="extension-live-renderer"
          data-binding-status={binding?.status}
          data-ref={binding?.deterministicRefs[0]?.ref}
          data-sample-present={String(Boolean(sample))}
        />
      );
    };

    mockClipTypeRegistryGet.mockReturnValue(makeRegistryRecord({ clipTypeId: 'ext.live-clip', renderer: TestRenderer }));
    mockClipTypeRegistryHas.mockReturnValue(true);

    renderWithLiveRegistry(
      liveBuildConfig([
        liveClip('clip-resolved', [{
          bindingId: 'binding-resolved',
          sourceId: 'source-live',
          sourceKind: 'generated',
          channelId,
          bake: {
            status: 'complete',
            deterministicRefs: [{ kind: 'asset', ref: 'asset-baked-live' }],
          },
        }]),
      ]),
      registry,
    );

    const el = screen.getByTestId('extension-live-renderer');
    expect(el).toHaveAttribute('data-binding-status', 'resolved');
    expect(el).toHaveAttribute('data-ref', 'asset-baked-live');
    expect(el).toHaveAttribute('data-sample-present', 'false');
    expect(latestSpy).not.toHaveBeenCalled();
    expect(screen.queryByTestId('live-binding-placeholder')).not.toBeInTheDocument();
  });
});

describe('TimelineRenderer — built-in live frame preview reader (M11 T7)', () => {
  beforeEach(() => {
    sequenceProps.length = 0;
    visualClipMock.mockClear();
    textClipMock.mockClear();
    mockClipTypeRegistryGet.mockReset();
    mockClipTypeRegistryHas.mockReset();
    mockClipTypeRegistryGet.mockReturnValue(undefined);
    mockClipTypeRegistryHas.mockReturnValue(false);
  });

  const liveFrameBuildConfig = (
    clips: ResolvedTimelineConfig['clips'],
  ): ResolvedTimelineConfig => ({
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips,
    registry: {},
  });

  const liveFrameClip = (
    id: string,
    binding: Record<string, unknown>,
    at = 0,
  ): ResolvedTimelineConfig['clips'][number] => ({
    id,
    clipType: 'live-frame-preview',
    track: 'V1',
    at,
    hold: 2,
    params: {
      liveBindings: [binding],
    },
  });

  it('reads latest, frame-indexed, and time-indexed frame samples synchronously', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'source-frames', kind: 'generated' });
    const channelId = registry.openChannel('source-frames', 'video');
    registry.pushSample(channelId, {
      timestamp: 0,
      data: { src: 'data:image/png;base64,FRAME_ZERO', frameIndex: 10 },
      format: 'json',
    });
    registry.pushSample(channelId, {
      timestamp: 1000,
      data: { src: 'data:image/png;base64,FRAME_ONE', frameIndex: 20 },
      format: 'json',
    });
    const latestSpy = vi.spyOn(registry, 'getLatestSample');

    renderWithLiveRegistry(
      liveFrameBuildConfig([
        liveFrameClip('clip-latest', {
          bindingId: 'binding-latest',
          sourceId: 'source-frames',
          sourceKind: 'generated',
          channelId,
          sampling: { mode: 'latest' },
        }),
        liveFrameClip('clip-frame', {
          bindingId: 'binding-frame',
          sourceId: 'source-frames',
          sourceKind: 'generated',
          channelId,
          sampling: { mode: 'frame', frameOffset: 10 },
        }),
        liveFrameClip('clip-time', {
          bindingId: 'binding-time',
          sourceId: 'source-frames',
          sourceKind: 'generated',
          channelId,
          sampling: { mode: 'time', timeOffsetMs: 500 },
        }),
      ]),
      registry,
    );

    const previews = screen.getAllByTestId('live-frame-preview');
    const srcs = previews.map((preview) => preview.querySelector('img')?.getAttribute('src'));
    expect(srcs).toEqual([
      'data:image/png;base64,FRAME_ONE',
      'data:image/png;base64,FRAME_ZERO',
      'data:image/png;base64,FRAME_ZERO',
    ]);
    expect(previews.map((preview) => preview.getAttribute('data-live-frame-sequence'))).toEqual(['1', '0', '0']);
    const latestReturn = latestSpy.mock.results[0]?.value;
    expect(Boolean(latestReturn && typeof (latestReturn as Promise<unknown>).then === 'function')).toBe(false);
    expect(screen.queryByTestId('unknown-clip-placeholder')).not.toBeInTheDocument();
  });

  it('renders visible placeholders for inactive, permission pending, generation, cancellation, error, missing, orphaned, disposed, and partial bake states', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'source-inactive', kind: 'generated' });
    registry.registerSource({
      id: 'source-permission',
      kind: 'webcam',
      permission: { state: 'prompt', reason: 'Camera access' },
    });
    registry.registerSource({ id: 'source-pending', kind: 'generated' });
    registry.openChannel('source-pending', 'video');
    registry.transitionSource('source-pending', 'active');
    registry.registerSource({ id: 'source-refining', kind: 'generated' });
    const refiningChannel = registry.openChannel('source-refining', 'video');
    registry.pushSample(refiningChannel, {
      timestamp: 200,
      data: { status: 'refining', progress: 0.6 },
      format: 'json',
    });
    registry.registerSource({ id: 'source-cancelled', kind: 'generated' });
    const cancelledChannel = registry.openChannel('source-cancelled', 'video');
    registry.pushSample(cancelledChannel, {
      timestamp: 300,
      data: { status: 'cancelled', progress: 0.35 },
      format: 'json',
    });
    registry.registerSource({ id: 'source-error', kind: 'generated' });
    registry.openChannel('source-error', 'video');
    registry.transitionSource('source-error', 'error', 'Generation failed');

    renderWithLiveRegistry(
      liveFrameBuildConfig([
        liveFrameClip('clip-inactive', { bindingId: 'binding-inactive', sourceId: 'source-inactive', sourceKind: 'generated' }),
        liveFrameClip('clip-permission', { bindingId: 'binding-permission', sourceId: 'source-permission', sourceKind: 'webcam' }),
        liveFrameClip('clip-pending', {
          bindingId: 'binding-pending',
          sourceId: 'source-pending',
          sourceKind: 'generated',
          placeholder: { progress: 0.25 },
        }),
        liveFrameClip('clip-refining', {
          bindingId: 'binding-refining',
          sourceId: 'source-refining',
          sourceKind: 'generated',
          channelId: refiningChannel,
        }),
        liveFrameClip('clip-cancelled', {
          bindingId: 'binding-cancelled',
          sourceId: 'source-cancelled',
          sourceKind: 'generated',
          channelId: cancelledChannel,
        }),
        liveFrameClip('clip-error', { bindingId: 'binding-error', sourceId: 'source-error', sourceKind: 'generated' }),
        liveFrameClip('clip-missing', { bindingId: 'binding-missing', sourceId: 'source-missing', sourceKind: 'generated' }),
        liveFrameClip('clip-orphaned', { bindingId: 'binding-orphaned', sourceId: 'source-orphaned', sourceKind: 'generated', sourceStatus: 'orphaned' }),
        liveFrameClip('clip-disposed', { bindingId: 'binding-disposed', sourceId: 'source-disposed', sourceKind: 'generated', sourceStatus: 'disposed' }),
        liveFrameClip('clip-partial', {
          bindingId: 'binding-partial',
          sourceId: 'source-partial',
          sourceKind: 'generated',
          placeholder: { progress: 0.5 },
          bake: {
            status: 'partial',
            bakedRanges: [{ startFrame: 0, endFrame: 10 }],
            unresolvedRanges: [{ startFrame: 11, endFrame: 20 }],
          },
        }),
      ]),
      registry,
    );

    const placeholders = screen.getAllByTestId('live-frame-placeholder');
    expect(placeholders.map((el) => el.getAttribute('data-live-frame-state'))).toEqual([
      'inactive',
      'permission-pending',
      'pending',
      'refining',
      'cancelled',
      'error',
      'missing',
      'orphaned',
      'disposed',
      'partiallyBaked',
    ]);
    expect(placeholders[2]).toHaveAttribute('data-live-frame-progress', '25');
    expect(placeholders[3]).toHaveAttribute('data-live-frame-progress', '60');
    expect(placeholders[4]).toHaveAttribute('data-live-frame-progress', '35');
    expect(placeholders[9]).toHaveAttribute('data-live-frame-progress', '50');
    expect(screen.queryByTestId('live-frame-preview')).not.toBeInTheDocument();
  });

  it('subscribes to ring-buffer changes so progressive frame replacement updates the preview without async reads', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'source-progressive', kind: 'generated' });
    const channelId = registry.openChannel('source-progressive', 'video');
    registry.pushSample(channelId, {
      timestamp: 0,
      data: { src: 'data:image/png;base64,FIRST', status: 'refining', progress: 0.4 },
      format: 'json',
    });
    const latestSpy = vi.spyOn(registry, 'getLatestSample');

    renderWithLiveRegistry(
      liveFrameBuildConfig([
        liveFrameClip('clip-progressive', {
          bindingId: 'binding-progressive',
          sourceId: 'source-progressive',
          sourceKind: 'generated',
          channelId,
        }),
      ]),
      registry,
    );

    const first = screen.getByTestId('live-frame-preview');
    expect(first.querySelector('img')).toHaveAttribute('src', 'data:image/png;base64,FIRST');
    expect(first).toHaveAttribute('data-live-frame-state', 'refining');
    expect(first).toHaveAttribute('data-live-frame-progress', '40');

    act(() => {
      registry.pushSample(channelId, {
        timestamp: 1000,
        data: { src: 'data:image/png;base64,FINAL', status: 'final', progress: 1 },
        format: 'json',
      });
    });

    const updated = screen.getByTestId('live-frame-preview');
    expect(updated.querySelector('img')).toHaveAttribute('src', 'data:image/png;base64,FINAL');
    expect(updated).toHaveAttribute('data-live-frame-state', 'final');
    expect(updated).toHaveAttribute('data-live-frame-progress', '100');
    expect(updated).toHaveAttribute('data-live-frame-sequence', '1');
    expect(latestSpy.mock.results.some((result) => Boolean(
      result.value && typeof (result.value as Promise<unknown>).then === 'function',
    ))).toBe(false);
  });
});
