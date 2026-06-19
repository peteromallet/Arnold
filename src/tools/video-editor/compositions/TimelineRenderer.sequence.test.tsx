// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type { ClipRendererProps } from '@/tools/video-editor/clip-types/ClipTypeRegistry';
import type { FC, PropsWithChildren } from 'react';

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
