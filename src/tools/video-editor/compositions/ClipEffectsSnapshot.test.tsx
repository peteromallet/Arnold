// @vitest-environment jsdom

import type { FC, PropsWithChildren } from 'react';
import { useEffect } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DynamicEffectRegistry } from '@/tools/video-editor/effects/DynamicEffectRegistry.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import { replaceEffectRegistry } from '@/tools/video-editor/effects/index.tsx';
import {
  createEffectRegistry,
  EffectRegistryProvider,
  useEffectRegistryContext,
  type EffectRegistryRecord,
  type EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/index.ts';
import { TextClip } from '@/tools/video-editor/compositions/TextClip.tsx';
import { VisualClip } from '@/tools/video-editor/compositions/VisualClip.tsx';
import type { ParameterSchema, ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';

let currentFrame = 0;

vi.mock('remotion', async () => ({
  AbsoluteFill: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="absolute-fill" {...props}>{children}</div>
  ),
  Img: ({ src, ...props }: Record<string, unknown>) => (
    <div data-testid="image-asset" data-src={String(src)} {...props} />
  ),
  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="sequence" {...props}>{children}</div>
  ),
  interpolate: () => ({}),
  useCurrentFrame: () => currentFrame,
  useRemotionEnvironment: () => ({ isRendering: false, isClientSideRendering: false }),
  useVideoConfig: () => ({ fps: 30, width: 1920, height: 1080 }),
}));

vi.mock('@remotion/media', () => ({
  Video: ({ src, ...props }: Record<string, unknown>) => (
    <div data-testid="video-asset" data-src={String(src)} {...props} />
  ),
}));

const renderability: EffectRegistryRecord['renderability'] = {
  defaultRoute: 'preview',
  determinism: 'deterministic',
  capabilities: [
    {
      route: 'preview',
      status: 'supported',
      determinism: 'deterministic',
    },
  ],
};

const track: TrackDefinition = {
  id: 'V1',
  type: 'video',
};

const schema: ParameterSchema = [
  {
    name: 'amount',
    label: 'Amount',
    type: 'number',
    default: 9,
    min: 0,
    max: 10,
  },
];

const makeEffect = (testId: string): FC<EffectComponentProps> => ({ children, params }) => (
  <div data-testid={testId} data-amount={String(params?.amount ?? '')}>{children}</div>
);

function record(
  effectId: string,
  component: FC<EffectComponentProps>,
  overrides: Partial<EffectRegistryRecord> = {},
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `test:${effectId}`,
    component,
    provenance: 'trusted-loader',
    ownerExtensionId: 'test-extension',
    renderability,
    status: 'active',
    ...overrides,
  };
}

function snapshotWith(records: readonly EffectRegistryRecord[]): EffectRegistrySnapshot {
  const registry = createEffectRegistry();
  records.forEach((entry) => registry.register(entry));
  return registry.getSnapshot();
}

function ProviderRecord({
  effectId,
  component,
  children,
  effectSchema,
}: PropsWithChildren<{
  effectId: string;
  component: FC<EffectComponentProps>;
  effectSchema?: ParameterSchema;
}>) {
  const { registry } = useEffectRegistryContext();

  useEffect(() => {
    const handle = registry.register(record(effectId, component, {
      ...(effectSchema ? { schema: effectSchema } : {}),
    }));
    return () => handle.dispose();
  }, [component, effectId, effectSchema, registry]);

  return <>{children}</>;
}

function textClip(effectType: string): ResolvedTimelineClip {
  return {
    id: `text-${effectType}`,
    clipType: 'text',
    track: 'V1',
    at: 0,
    hold: 1,
    text: {
      content: 'Provider text',
    },
    entrance: {
      type: effectType,
      params: {},
    },
  };
}

function visualClip(effectType: string): ResolvedTimelineClip {
  return {
    id: `visual-${effectType}`,
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 1,
    assetEntry: {
      id: 'asset-1',
      type: 'image/png',
      src: 'https://example.test/image.png',
    },
    continuous: {
      type: effectType,
      params: {},
    },
  };
}

describe('clip composition effect snapshot resolution', () => {
  afterEach(() => {
    currentFrame = 0;
    replaceEffectRegistry(new DynamicEffectRegistry({}));
    vi.restoreAllMocks();
  });

  it('TextClip prefers provider-owned snapshot records and schemas over built-in IDs', async () => {
    const ProviderFade = makeEffect('provider-fade');

    render(
      <EffectRegistryProvider>
        <ProviderRecord effectId="fade" component={ProviderFade} effectSchema={schema}>
          <TextClip clip={textClip('fade')} track={track} fps={30} />
        </ProviderRecord>
      </EffectRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('provider-fade')).toBeInTheDocument();
    });
    expect(screen.getByTestId('provider-fade')).toHaveAttribute('data-amount', '9');
  });

  it('VisualClip uses explicit snapshots and does not leak to the legacy singleton for same IDs', () => {
    const LegacyShared = makeEffect('legacy-shared');
    replaceEffectRegistry(new DynamicEffectRegistry({ shared: LegacyShared }));
    const ProviderShared = makeEffect('provider-shared');
    const snapshot = snapshotWith([record('shared', ProviderShared, { schema })]);

    render(
      <VisualClip
        clip={visualClip('custom:shared')}
        track={track}
        fps={30}
        effectRegistrySnapshot={snapshot}
      />,
    );

    expect(screen.getByTestId('provider-shared')).toBeInTheDocument();
    expect(screen.getByTestId('provider-shared')).toHaveAttribute('data-amount', '9');
    expect(screen.queryByTestId('legacy-shared')).not.toBeInTheDocument();
  });

  it('VisualClip passes content through when a provided snapshot lacks the effect', () => {
    replaceEffectRegistry(new DynamicEffectRegistry({ shared: makeEffect('legacy-shared') }));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    render(
      <VisualClip
        clip={visualClip('shared')}
        track={track}
        fps={30}
        effectRegistrySnapshot={snapshotWith([])}
      />,
    );

    expect(screen.getByTestId('image-asset')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-shared')).not.toBeInTheDocument();
    expect(warn).toHaveBeenCalledWith('[EffectWrap] continuous effect NOT FOUND for clip=%s type=%s', 'visual-shared', 'shared');
  });
});
