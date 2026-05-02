// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type { PropsWithChildren } from 'react';

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
});
