// @vitest-environment jsdom

import type { FC, PropsWithChildren } from 'react';
import { useEffect } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DynamicEffectRegistry } from '@/tools/video-editor/effects/DynamicEffectRegistry.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import { replaceEffectRegistry } from '@/tools/video-editor/effects/index.tsx';
import {
  createEffectRegistry,
  EffectRegistryProvider,
  useEffectRegistryContext,
} from '@/tools/video-editor/effects/registry/index.ts';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/index.ts';
import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence.tsx';
import type { ParameterSchema, ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

let currentFrame = 0;

vi.mock('remotion', async () => ({
  Sequence: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="sequence" {...props}>{children}</div>
  ),
  useCurrentFrame: () => currentFrame,
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

const schema = (defaultValue: number): ParameterSchema => [
  {
    name: 'amount',
    label: 'Amount',
    type: 'number',
    default: defaultValue,
    min: 0,
    max: 10,
  },
];

const clip = (effectType: string): ResolvedTimelineClip => ({
  id: `clip-${effectType}`,
  clipType: 'effect-layer',
  track: 'V1',
  at: 0,
  hold: 1,
  continuous: {
    type: effectType,
    intensity: 0.75,
    params: {},
  },
});

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
  schema: effectSchema,
}: PropsWithChildren<{
  effectId: string;
  component: FC<EffectComponentProps>;
  schema?: ParameterSchema;
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

describe('EffectLayerSequence registry snapshot resolution', () => {
  beforeEach(() => {
    currentFrame = 0;
    vi.restoreAllMocks();
    replaceEffectRegistry(new DynamicEffectRegistry({}));
  });

  it('prefers provider snapshot records and schemas over the legacy singleton for matching effect IDs', async () => {
    const LegacyEffect = makeEffect('legacy-effect');
    replaceEffectRegistry(new DynamicEffectRegistry({ 'provider-shared': LegacyEffect }));
    const ProviderEffect = makeEffect('provider-effect');

    render(
      <EffectRegistryProvider>
        <ProviderRecord effectId="provider-shared" component={ProviderEffect} schema={schema(7)}>
          <EffectLayerSequence clip={clip('provider-shared')} fps={30}>
            <div data-testid="content">content</div>
          </EffectLayerSequence>
        </ProviderRecord>
      </EffectRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('provider-effect')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('legacy-effect')).not.toBeInTheDocument();
    expect(screen.getByTestId('provider-effect')).toHaveAttribute('data-amount', '7');
  });

  it('keeps same effect IDs isolated when renderer tests pass explicit snapshots', () => {
    const FirstEffect = makeEffect('first-effect');
    const SecondEffect = makeEffect('second-effect');
    const firstSnapshot = snapshotWith([record('shared-effect', FirstEffect)]);
    const secondSnapshot = snapshotWith([record('shared-effect', SecondEffect)]);

    render(
      <>
        <EffectLayerSequence clip={clip('custom:shared-effect')} fps={30} effectRegistrySnapshot={firstSnapshot}>
          <div data-testid="first-content">first</div>
        </EffectLayerSequence>
        <EffectLayerSequence clip={clip('custom:shared-effect')} fps={30} effectRegistrySnapshot={secondSnapshot}>
          <div data-testid="second-content">second</div>
        </EffectLayerSequence>
      </>,
    );

    expect(screen.getByTestId('first-effect')).toContainElement(screen.getByTestId('first-content'));
    expect(screen.getByTestId('second-effect')).toContainElement(screen.getByTestId('second-content'));
  });

  it('passes children through when an explicit snapshot is missing the effect', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    replaceEffectRegistry(new DynamicEffectRegistry({ 'legacy-only': makeEffect('legacy-only') }));
    const emptySnapshot = snapshotWith([]);

    render(
      <EffectLayerSequence clip={clip('legacy-only')} fps={30} effectRegistrySnapshot={emptySnapshot}>
        <div data-testid="content">content</div>
      </EffectLayerSequence>,
    );

    expect(screen.getByTestId('content')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-only')).not.toBeInTheDocument();
    expect(warn).toHaveBeenCalledWith('[EffectLayer] effect NOT FOUND for clip=%s type=%s', 'clip-legacy-only', 'legacy-only');
  });

  it('passes children through outside the effect layer frame range', () => {
    currentFrame = 45;
    const snapshot = snapshotWith([record('delayed-effect', makeEffect('delayed-effect'))]);

    render(
      <EffectLayerSequence
        clip={{ ...clip('delayed-effect'), at: 0, hold: 1 }}
        fps={30}
        effectRegistrySnapshot={snapshot}
      >
        <div data-testid="content">content</div>
      </EffectLayerSequence>,
    );

    expect(screen.getByTestId('content')).toBeInTheDocument();
    expect(screen.queryByTestId('delayed-effect')).not.toBeInTheDocument();
  });

  it('resolves effects from the context-based provider registry when no explicit snapshot is passed', async () => {
    const ContextEffect = makeEffect('context-effect');
    render(
      <EffectRegistryProvider>
        <ProviderRecord effectId="context-effect" component={ContextEffect} schema={schema(5)}>
          <EffectLayerSequence clip={clip('context-effect')} fps={30}>
            <div data-testid="ctx-content">content</div>
          </EffectLayerSequence>
        </ProviderRecord>
      </EffectRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('context-effect')).toBeInTheDocument();
    });
    expect(screen.getByTestId('ctx-content')).toBeInTheDocument();
    expect(screen.getByTestId('context-effect')).toHaveAttribute('data-amount', '5');
  });

  it('passes provider record schema defaults to the rendered effect component', async () => {
    const ParamsEffect: FC<EffectComponentProps> = ({ children, params }) => (
      <div data-testid="params-effect" data-amount={String(params?.amount ?? 'none')} data-enabled={String(params?.enabled ?? 'none')}>{children}</div>
    );
    const multiSchema: ParameterSchema = [
      { name: 'amount', label: 'Amount', type: 'number', default: 10, min: 0, max: 20 },
      { name: 'enabled', label: 'Enabled', type: 'boolean', default: true },
    ];

    render(
      <EffectRegistryProvider>
        <ProviderRecord effectId="multi-param-effect" component={ParamsEffect} schema={multiSchema}>
          <EffectLayerSequence clip={clip('multi-param-effect')} fps={30}>
            <div data-testid="mp-content">content</div>
          </EffectLayerSequence>
        </ProviderRecord>
      </EffectRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('params-effect')).toBeInTheDocument();
    });
    expect(screen.getByTestId('params-effect')).toHaveAttribute('data-amount', '10');
    expect(screen.getByTestId('params-effect')).toHaveAttribute('data-enabled', 'true');
  });

  it('context-based resolution falls back to legacy singleton when no provider context exists', async () => {
    const LegacyOnly = makeEffect('legacy-context-only');
    replaceEffectRegistry(new DynamicEffectRegistry({ 'legacy-context-only': LegacyOnly }));

    // No EffectRegistryProvider wrapper — legacy fallback is active
    render(
      <EffectLayerSequence clip={clip('legacy-context-only')} fps={30}>
        <div data-testid="lc-content">content</div>
      </EffectLayerSequence>,
    );

    // With no provider context, falls back to legacy singleton
    await waitFor(() => {
      expect(screen.getByTestId('legacy-context-only')).toBeInTheDocument();
    });
  });
});
