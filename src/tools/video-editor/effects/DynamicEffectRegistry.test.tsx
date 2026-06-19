import { act, render, screen, waitFor } from '@testing-library/react';
import { useSyncExternalStore, type FC } from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

const remotionState = vi.hoisted(() => ({
  frame: 0,
  videoConfig: { fps: 30, width: 1920, height: 1080 },
}));

vi.mock('remotion', async (importOriginal) => {
  const actual = await importOriginal<typeof import('remotion')>();
  return {
    ...actual,
    useCurrentFrame: vi.fn(() => remotionState.frame),
    useVideoConfig: vi.fn(() => remotionState.videoConfig),
  };
});

import * as compileEffectModule from '@/tools/video-editor/effects/compileEffect';
import * as effectsModule from '@/tools/video-editor/effects';
import {
  entranceEffects,
  getEffectRegistry,
  replaceEffectRegistry,
  wrapWithClipEffects,
  wrapWithEffect,
} from '@/tools/video-editor/effects';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';
import { DynamicEffectRegistry } from '@/tools/video-editor/effects/DynamicEffectRegistry';
import { EffectErrorBoundary } from '@/tools/video-editor/effects/EffectErrorBoundary';
import {
  EffectRegistryProvider,
  useEffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/EffectRegistryContext';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types';
import { validateAndCoerceParams } from '@/tools/video-editor/effects/validateParams';
import { useEffectRegistry } from '@/tools/video-editor/hooks/useEffectRegistry';
import type { EffectResource } from '@/tools/video-editor/hooks/useEffectResources';
import type { ParameterSchema, ResolvedTimelineClip } from '@/tools/video-editor/types';

function BuiltInFade(_props: EffectComponentProps) {
  return <div data-testid="builtin-fade" />;
}

const EFFECT_CODE = 'export default function Effect(){ return <div data-testid="dynamic-effect" />; }';

function makeResourceEffect(id: string, code: string, parameterSchema?: ParameterSchema): EffectResource {
  return {
    id,
    type: 'effect',
    name: id,
    slug: id,
    code,
    category: 'continuous',
    description: id,
    ...(parameterSchema ? { parameterSchema } : {}),
    created_by: { is_you: true },
    is_public: false,
  };
}

describe('DynamicEffectRegistry', () => {
  beforeAll(async () => {
    await compileEffectModule.preloadSucrase();
  });

  afterEach(() => {
    localStorage.clear();
    replaceEffectRegistry(new DynamicEffectRegistry({}));
    vi.restoreAllMocks();
  });

  it('prefers built-in effects over dynamic name collisions and resolves custom prefix lookups', async () => {
    const registry = new DynamicEffectRegistry({ fade: BuiltInFade });
    registry.register('fade', 'export default function Effect(){ return <div data-testid="dynamic-fade" />; }');
    await registry.registerAsync('test', 'export default function Effect(){ return <div data-testid="custom-test" />; }');

    const FadeComponent = registry.get('fade');
    const CustomComponent = registry.get('custom:test');

    expect(FadeComponent).toBe(BuiltInFade);
    expect(CustomComponent).toBeDefined();
    expect(registry.getCode('custom:test')).toContain('custom-test');
  });

  it('returns a compile error overlay instead of throwing for invalid custom code', async () => {
    const registry = new DynamicEffectRegistry({});
    expect(() => registry.register('broken', 'export default function Effect( {')).not.toThrow();
    expect(registry.get('broken')).toBeDefined();
  });

  it('compiles and renders an effect that calls useAudioReactive without a provider', async () => {
    const result = await compileEffectModule.tryCompileEffectAsync(`
      function AudioReactiveEffect() {
        const audio = useAudioReactive();
        return <div data-testid="audio-reactive-effect">{String(audio.amplitude)}:{String(audio.isBeat)}</div>;
      }
      exports.default = AudioReactiveEffect;
    `);

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }

    render(<result.component durationInFrames={1}>{null}</result.component>);

    expect(screen.getByTestId('audio-reactive-effect').textContent).toBe('0:false');
  });

  it('compiles and renders an effect that calls useAudioParam', async () => {
    const result = await compileEffectModule.tryCompileEffectAsync(`
      function AudioParamEffect(props) {
        const value = useAudioParam(props.params?.binding);
        return <div data-testid="audio-param-effect">{String(value)}</div>;
      }
      exports.default = AudioParamEffect;
    `);

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }

    render(
      <result.component
        durationInFrames={1}
        params={{ binding: { source: 'amplitude', min: 2, max: 5 } }}
      >
        {null}
      </result.component>,
    );

    expect(screen.getByTestId('audio-param-effect').textContent).toBe('2');
  });

  it('tracks subscriptions, deduplicates unchanged registrations, batches notifications, and stores schemas', async () => {
    const schema: ParameterSchema = [
      { name: 'amount', label: 'Amount', description: 'Adjust amount', type: 'number', default: 2, min: 0, max: 5 },
    ];
    const sameSchema: ParameterSchema = [
      { name: 'amount', label: 'Amount', description: 'Adjust amount', type: 'number', default: 2, min: 0, max: 5 },
    ];
    const changedSchema: ParameterSchema = [
      { name: 'amount', label: 'Amount', description: 'Adjust amount', type: 'number', default: 3, min: 0, max: 5 },
    ];
    const registry = new DynamicEffectRegistry({});
    const listener = vi.fn();
    const unsubscribe = registry.subscribe(listener);

    expect(registry.getSnapshot()).toBe(0);

    registry.register('alpha', EFFECT_CODE);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(registry.getSnapshot()).toBe(1);

    registry.register('alpha', EFFECT_CODE);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(registry.getSnapshot()).toBe(1);

    registry.register('schema-effect', EFFECT_CODE, schema);
    expect(listener).toHaveBeenCalledTimes(2);
    expect(registry.getSnapshot()).toBe(2);

    registry.register('schema-effect', EFFECT_CODE, sameSchema);
    expect(listener).toHaveBeenCalledTimes(2);
    expect(registry.getSnapshot()).toBe(2);

    registry.register('schema-effect', EFFECT_CODE, changedSchema);
    expect(listener).toHaveBeenCalledTimes(3);
    expect(registry.getSnapshot()).toBe(3);

    await registry.batch(async () => {
      registry.register('beta', EFFECT_CODE.replace('dynamic-effect', 'beta-effect'));
      registry.register('gamma', EFFECT_CODE.replace('dynamic-effect', 'gamma-effect'), schema);
    });

    unsubscribe();

    expect(listener).toHaveBeenCalledTimes(4);
    expect(registry.getSnapshot()).toBe(4);
    expect(registry.getSchema('custom:gamma')).toEqual(schema);
  });

  it('renders the fallback when an effect throws inside the boundary', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const ThrowingEffect = () => {
      throw new Error('boom');
    };

    render(
      <EffectErrorBoundary effectName="explode" fallback={<div data-testid="effect-fallback" />}>
        <ThrowingEffect />
      </EffectErrorBoundary>,
    );

    expect(screen.getByTestId('effect-fallback')).toBeInTheDocument();
    expect(errorSpy).toHaveBeenCalledWith('[EffectErrorBoundary] "explode" runtime error: boom');
    errorSpy.mockRestore();
  });

  it('wrapWithEffect validates params before rendering the effect', () => {
    let receivedProps: Omit<EffectComponentProps, 'children'> | null = null;
    const InspectEffect = ({ children, ...props }: EffectComponentProps) => {
      receivedProps = props;
      return <div data-testid="wrapped-effect">{children}</div>;
    };
    const schema: ParameterSchema = [
      { name: 'amount', label: 'Amount', description: 'Effect amount', type: 'number', default: 2, min: 0, max: 5 },
      { name: 'enabled', label: 'Enabled', description: 'Enable effect', type: 'boolean', default: false },
    ];

    render(
      <>
        {wrapWithEffect(<div data-testid="wrapped-child" />, InspectEffect, {
          effectName: 'inspect',
          durationInFrames: 24,
          effectFrames: 12,
          intensity: 0.75,
          params: { amount: 'bad', enabled: 'true' },
          schema,
        })}
      </>,
    );

    expect(screen.getByTestId('wrapped-effect')).toBeInTheDocument();
    expect(screen.getByTestId('wrapped-child')).toBeInTheDocument();
    expect(receivedProps).toEqual({
      durationInFrames: 24,
      effectFrames: 12,
      intensity: 0.75,
      params: { amount: 2, enabled: false },
    });
  });

  it('wrapWithEffect falls back to the original content when the effect throws', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const ThrowingEffect = () => {
      throw new Error('wrap failure');
    };

    render(
      <>
        {wrapWithEffect(<div data-testid="wrap-fallback" />, ThrowingEffect, {
          effectName: 'wrap-failure',
          durationInFrames: 10,
        })}
      </>,
    );

    expect(screen.getByTestId('wrap-fallback')).toBeInTheDocument();
    expect(errorSpy).toHaveBeenCalledWith('[EffectErrorBoundary] "wrap-failure" runtime error: wrap failure');
  });

  it('keeps the deprecated singleton bridge seedable without mutating built-in exports or wrappers', () => {
    const originalFade = entranceEffects.fade;
    const LegacyBridgeEffect = ({ children }: EffectComponentProps) => (
      <div data-testid="legacy-bridge-effect">{children}</div>
    );
    const DirectEffect = ({ children }: EffectComponentProps) => (
      <div data-testid="direct-wrapped-effect">{children}</div>
    );
    const seededRegistry = new DynamicEffectRegistry({
      'legacy-bridge': LegacyBridgeEffect,
    });

    expect(replaceEffectRegistry(seededRegistry)).toBe(seededRegistry);
    expect(getEffectRegistry()).toBe(seededRegistry);
    expect(getEffectRegistry().get('custom:legacy-bridge')).toBe(LegacyBridgeEffect);

    render(
      <>
        {wrapWithEffect(<div data-testid="direct-child" />, DirectEffect, {
          effectName: 'direct',
          durationInFrames: 10,
        })}
      </>,
    );

    expect(entranceEffects.fade).toBe(originalFade);
    expect(getEffectRegistry()).toBe(seededRegistry);
    expect(screen.getByTestId('direct-wrapped-effect')).toContainElement(screen.getByTestId('direct-child'));
  });

  it('re-renders subscribed components when async registration completes', async () => {
    const registry = new DynamicEffectRegistry({});

    function RegistryConsumer() {
      const version = useSyncExternalStore(registry.subscribe, registry.getSnapshot);
      const effect = registry.get('async-test');
      return (
        <div data-testid="consumer">
          v{version}:{effect ? 'found' : 'missing'}
        </div>
      );
    }

    render(<RegistryConsumer />);
    expect(screen.getByTestId('consumer').textContent).toBe('v0:missing');

    await act(async () => {
      await registry.registerAsync('async-test', EFFECT_CODE);
    });

    expect(screen.getByTestId('consumer').textContent).toBe('v1:found');
  });

  it('does not let a slower async registration overwrite newer code', async () => {
    const registry = new DynamicEffectRegistry({});
    const pending = new Map<string, (component: FC<EffectComponentProps>) => void>();
    const makeEffect = (testId: string): FC<EffectComponentProps> => {
      return function MockEffect({ children }) {
        return <div data-testid={testId}>{children}</div>;
      };
    };
    vi.spyOn(compileEffectModule, 'compileEffectAsync').mockImplementation((code: string) => {
      return new Promise<FC<EffectComponentProps>>((resolve) => {
        pending.set(code, resolve);
      });
    });

    registry.register('race', EFFECT_CODE.replace('dynamic-effect', 'race-v1'));

    const staleRegistration = registry.registerAsync('race', 'v1-old');
    const newestRegistration = registry.registerAsync('race', 'v2');

    pending.get('v2')?.(makeEffect('race-v2'));
    await newestRegistration;

    pending.get('v1-old')?.(makeEffect('race-v1-old'));
    await staleRegistration;

    expect(registry.getCode('race')).toBe('v2');

    const RegisteredEffect = registry.get('race');
    expect(RegisteredEffect).toBeDefined();

    render(
      RegisteredEffect ? (
        <RegisteredEffect durationInFrames={1}>
          <div data-testid="race-child" />
        </RegisteredEffect>
      ) : null,
    );

    expect(screen.getByTestId('race-v2')).toBeInTheDocument();
    expect(screen.queryByTestId('race-v1-old')).not.toBeInTheDocument();
  });

  it('loads effects into the provider registry without mutating the legacy singleton', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const replaceSpy = vi.spyOn(effectsModule, 'replaceEffectRegistry');

    const resourceEffects: EffectResource[] = [
      makeResourceEffect('resource-effect', EFFECT_CODE),
    ];

    function RegistryHost() {
      const registry = useEffectRegistry(undefined, resourceEffects);
      const snapshot = useEffectRegistrySnapshot();
      const effect = snapshot.get('resource-effect');
      return (
        <div data-testid="registry-state">
          {snapshot === registry.getSnapshot() ? 'same' : 'different'}:{effect ? 'found' : 'missing'}
        </div>
      );
    }

    replaceEffectRegistry(new DynamicEffectRegistry({}));
    replaceSpy.mockClear();
    render(
      <EffectRegistryProvider>
        <RegistryHost />
      </EffectRegistryProvider>,
    );

    expect(replaceSpy).toHaveBeenCalledTimes(0);
    expect(getEffectRegistry().get('custom:resource-effect')).toBeUndefined();

    await waitFor(() => {
      expect(screen.getByTestId('registry-state').textContent).toBe('same:found');
    });
    expect(replaceSpy).toHaveBeenCalledTimes(0);
    expect(getEffectRegistry().get('custom:resource-effect')).toBeUndefined();
  });

  it('resolves built-ins, normalized custom resources, schemas, and wrapping from provider snapshots', async () => {
    let receivedProps: Omit<EffectComponentProps, 'children'> | null = null;
    const schema: ParameterSchema = [
      { name: 'amount', label: 'Amount', description: 'Effect amount', type: 'number', default: 4, min: 0, max: 10 },
      { name: 'enabled', label: 'Enabled', description: 'Enable effect', type: 'boolean', default: true },
    ];
    vi.spyOn(compileEffectModule, 'compileEffect').mockImplementation((code: string) => {
      return function ProviderCompiledEffect({ children, ...props }: EffectComponentProps) {
        receivedProps = props;
        return <div data-testid={`provider-${code}`}>{children}</div>;
      };
    });

    const resourceEffects: EffectResource[] = [
      makeResourceEffect('custom:provider-custom', 'provider-custom-code', schema),
    ];

    function ProviderSnapshotHost() {
      const registry = useEffectRegistry(undefined, resourceEffects);
      const snapshot = useEffectRegistrySnapshot();
      const clip = {
        id: 'clip-1',
        continuous: {
          type: 'custom:provider-custom',
          params: { amount: 'bad', enabled: 'false' },
          intensity: 0.8,
        },
      } as ResolvedTimelineClip;
      const wrapped = wrapWithClipEffects(
        <div data-testid="provider-child" />,
        clip,
        30,
        30,
        snapshot,
      );
      const customRecord = snapshot.get('provider-custom');
      return (
        <div data-testid="provider-snapshot-state">
          <span data-testid="builtin-state">
            {snapshot.get('fade')?.component === entranceEffects.fade ? 'builtin-found' : 'builtin-missing'}
          </span>
          <span data-testid="custom-state">
            {customRecord?.schema === schema && registry.resolve('provider-custom') === customRecord
              ? 'custom-found'
              : 'custom-missing'}
          </span>
          {wrapped}
        </div>
      );
    }

    replaceEffectRegistry(new DynamicEffectRegistry({}));
    render(
      <EffectRegistryProvider>
        <ProviderSnapshotHost />
      </EffectRegistryProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('builtin-state').textContent).toBe('builtin-found');
      expect(screen.getByTestId('custom-state').textContent).toBe('custom-found');
      expect(screen.getByTestId('provider-provider-custom-code')).toContainElement(screen.getByTestId('provider-child'));
    });
    expect(receivedProps).toEqual({
      durationInFrames: 30,
      effectFrames: 30,
      intensity: 0.8,
      params: { amount: 4, enabled: true },
    });
    expect(getEffectRegistry().get('custom:provider-custom')).toBeUndefined();
  });

  it('isolates same effect IDs across provider registries without leaking components or singleton state', async () => {
    const compileSpy = vi.spyOn(compileEffectModule, 'compileEffect').mockImplementation((code: string) => {
      return function MockCompiledEffect({ children }: EffectComponentProps) {
        return <div data-testid={`compiled-${code}`}>{children}</div>;
      };
    });

    function ProviderRegistryHost({
      label,
      resourceEffects,
    }: {
      label: string;
      resourceEffects: EffectResource[];
    }) {
      const registry = useEffectRegistry(undefined, resourceEffects);
      const snapshot = useEffectRegistrySnapshot();
      const record = snapshot.get('shared-effect');
      const CompiledEffect = record?.component;
      const registryRecord = registry.resolve('shared-effect');
      return (
        <div data-testid={`${label}-state`}>
          <span data-testid={`${label}-code`}>{registryRecord?.code ?? 'missing'}</span>
          {CompiledEffect ? (
            <CompiledEffect durationInFrames={1}>
              <span data-testid={`${label}-child`} />
            </CompiledEffect>
          ) : null}
        </div>
      );
    }

    replaceEffectRegistry(new DynamicEffectRegistry({}));
    render(
      <>
        <EffectRegistryProvider>
          <ProviderRegistryHost
            label="provider-a"
            resourceEffects={[makeResourceEffect('shared-effect', 'provider-a')]}
          />
        </EffectRegistryProvider>
        <EffectRegistryProvider>
          <ProviderRegistryHost
            label="provider-b"
            resourceEffects={[makeResourceEffect('shared-effect', 'provider-b')]}
          />
        </EffectRegistryProvider>
      </>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('provider-a-code').textContent).toBe('provider-a');
      expect(screen.getByTestId('provider-b-code').textContent).toBe('provider-b');
    });

    expect(screen.getByTestId('compiled-provider-a')).toContainElement(screen.getByTestId('provider-a-child'));
    expect(screen.getByTestId('compiled-provider-b')).toContainElement(screen.getByTestId('provider-b-child'));
    expect(screen.queryByTestId('compiled-provider-a')).not.toContainElement(screen.getByTestId('provider-b-child'));
    expect(screen.queryByTestId('compiled-provider-b')).not.toContainElement(screen.getByTestId('provider-a-child'));
    expect(getEffectRegistry().get('custom:shared-effect')).toBeUndefined();
    expect(compileSpy).toHaveBeenCalledWith('provider-a');
    expect(compileSpy).toHaveBeenCalledWith('provider-b');
  });

  it('uses a memoized standalone fallback registry outside a provider', async () => {
    const resourceEffects: EffectResource[] = [
      makeResourceEffect('standalone-resource-effect', EFFECT_CODE),
    ];

    function RegistryHost() {
      const registry = useEffectRegistry(undefined, resourceEffects);
      const effect = registry.resolve('standalone-resource-effect');
      return (
        <div data-testid="standalone-registry-state">
          {effect ? 'found' : 'missing'}:{registry.getSnapshot().records.length}
        </div>
      );
    }

    replaceEffectRegistry(new DynamicEffectRegistry({}));
    render(<RegistryHost />);

    expect(getEffectRegistry().get('custom:standalone-resource-effect')).toBeUndefined();

    await waitFor(() => {
      expect(screen.getByTestId('standalone-registry-state').textContent).toMatch(/^found:/);
    });
    expect(getEffectRegistry().get('custom:standalone-resource-effect')).toBeUndefined();
  });

  it('seeds provider-unaware fallback registries locally without leaking same effect IDs', async () => {
    vi.spyOn(compileEffectModule, 'compileEffect').mockImplementation((code: string) => {
      return function MockCompiledEffect({ children }: EffectComponentProps) {
        return <div data-testid={`standalone-${code}`}>{children}</div>;
      };
    });

    function StandaloneRegistryHost({
      label,
      resourceEffects,
    }: {
      label: string;
      resourceEffects: EffectResource[];
    }) {
      const registry = useEffectRegistry(undefined, resourceEffects);
      const record = registry.resolve('fallback-shared-effect');
      const CompiledEffect = record?.component;
      return (
        <div data-testid={`${label}-fallback-state`}>
          <span data-testid={`${label}-fallback-code`}>{record?.code ?? 'missing'}</span>
          {CompiledEffect ? (
            <CompiledEffect durationInFrames={1}>
              <span data-testid={`${label}-fallback-child`} />
            </CompiledEffect>
          ) : null}
        </div>
      );
    }

    replaceEffectRegistry(new DynamicEffectRegistry({}));
    render(
      <>
        <StandaloneRegistryHost
          label="fallback-a"
          resourceEffects={[makeResourceEffect('fallback-shared-effect', 'fallback-a')]}
        />
        <StandaloneRegistryHost
          label="fallback-b"
          resourceEffects={[makeResourceEffect('fallback-shared-effect', 'fallback-b')]}
        />
      </>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('fallback-a-fallback-code').textContent).toBe('fallback-a');
      expect(screen.getByTestId('fallback-b-fallback-code').textContent).toBe('fallback-b');
    });

    expect(screen.getByTestId('standalone-fallback-a')).toContainElement(screen.getByTestId('fallback-a-fallback-child'));
    expect(screen.getByTestId('standalone-fallback-b')).toContainElement(screen.getByTestId('fallback-b-fallback-child'));
    expect(screen.queryByTestId('standalone-fallback-a')).not.toContainElement(screen.getByTestId('fallback-b-fallback-child'));
    expect(screen.queryByTestId('standalone-fallback-b')).not.toContainElement(screen.getByTestId('fallback-a-fallback-child'));
    expect(getEffectRegistry().get('custom:fallback-shared-effect')).toBeUndefined();
  });

  it('wrapWithClipEffects prefers provider record component and schema over legacy singleton for same effect ID', () => {
    const LegacyComponent = ({ children }: EffectComponentProps) => (
      <div data-testid="legacy-override-component">{children}</div>
    );
    const ProviderComponent = ({ children, params }: EffectComponentProps) => (
      <div data-testid="provider-override-component" data-amount={String(params?.amount ?? '')}>{children}</div>
    );
    const providerSchema: ParameterSchema = [
      { name: 'amount', label: 'Amount', type: 'number', default: 42, min: 0, max: 100 },
    ];
    const legacySchema: ParameterSchema = [
      { name: 'amount', label: 'Amount', type: 'number', default: 1, min: 0, max: 10 },
    ];

    // Seed the legacy singleton with one component and schema
    replaceEffectRegistry(new DynamicEffectRegistry({ 'override-effect': LegacyComponent }));
    getEffectRegistry().register('override-effect', 'export default function Effect(){}', legacySchema);

    // Build a provider snapshot with a different component and schema for the same ID
    const providerRecord: EffectRegistryRecord = {
      effectId: 'override-effect',
      contributionId: 'test:override-effect',
      component: ProviderComponent,
      provenance: 'trusted-loader',
      ownerExtensionId: 'test-ext',
      status: 'active',
      schema: providerSchema,
      renderability: {
        defaultRoute: 'preview',
        determinism: 'deterministic',
        capabilities: [
          { route: 'preview', status: 'supported', determinism: 'deterministic' },
        ],
      },
    };
    const providerSnapshot: EffectRegistrySnapshot = Object.freeze({
      records: Object.freeze([providerRecord]),
      diagnostics: Object.freeze([]),
      get: (effectId: string) => effectId === 'override-effect' ? providerRecord : undefined,
      has: (effectId: string) => effectId === 'override-effect',
    }) as EffectRegistrySnapshot;

    const clip: ResolvedTimelineClip = {
      id: 'clip-override',
      clipType: 'media',
      track: 'V1',
      at: 0,
      hold: 1,
      continuous: { type: 'override-effect', params: {}, intensity: 0.5 },
    };

    render(
      <>
        {wrapWithClipEffects(
          <div data-testid="override-child" />,
          clip,
          30,
          30,
          providerSnapshot,
        )}
      </>,
    );

    // Provider component renders, not legacy
    expect(screen.getByTestId('provider-override-component')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-override-component')).not.toBeInTheDocument();
    // Provider schema default (42) used, not legacy default (1)
    expect(screen.getByTestId('provider-override-component')).toHaveAttribute('data-amount', '42');
    // Legacy singleton is unchanged
    expect(getEffectRegistry().get('custom:override-effect')).toBe(LegacyComponent);
  });

  it('validates and coerces effect params from schema defaults', () => {
    const schema: ParameterSchema = [
      { name: 'size', label: 'Size', description: 'Effect size', type: 'number', default: 2, min: 0, max: 5 },
      { name: 'opacity', label: 'Opacity', description: 'Effect opacity', type: 'number', default: 0.5, min: 0, max: 1 },
      { name: 'enabled', label: 'Enabled', description: 'Enable effect', type: 'boolean', default: false },
      {
        name: 'mode',
        label: 'Mode',
        description: 'Effect mode',
        type: 'select',
        options: [
          { label: 'Soft', value: 'soft' },
          { label: 'Hard', value: 'hard' },
        ],
      },
      { name: 'color', label: 'Color', description: 'Tint color', type: 'color', default: '#123abc' },
      {
        name: 'binding',
        label: 'Binding',
        description: 'Audio binding',
        type: 'audio-binding',
        default: { source: 'bass', min: 1, max: 3 },
      },
    ];

    expect(validateAndCoerceParams({
      size: '3',
      opacity: 9,
      enabled: 'true',
      mode: 'missing',
      color: 'blue',
      binding: { source: 'noise', min: 'low', max: null },
      customSeed: 42,
    }, schema)).toEqual({
      size: 2,
      opacity: 1,
      enabled: false,
      mode: 'soft',
      color: '#123abc',
      binding: { source: 'bass', min: 1, max: 3 },
      customSeed: 42,
    });
  });
});
