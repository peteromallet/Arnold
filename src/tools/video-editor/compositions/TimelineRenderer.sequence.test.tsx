// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

const sequenceProps = vi.hoisted((): Array<Record<string, unknown>> => []);

vi.mock('remotion', async () => {
  const React = await import('react');
  return {
    AbsoluteFill: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div data-testid="absolute-fill" {...props}>{children}</div>
    ),
    Sequence: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => {
      sequenceProps.push(props);
      return <div data-testid="sequence">{children}</div>;
    },
  };
});

vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', async () => {
  const React = await import('react');
  return {
    AudioAnalysisProvider: ({ children }: React.PropsWithChildren) => (
      <div data-testid="audio-analysis-provider">{children}</div>
    ),
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
});
