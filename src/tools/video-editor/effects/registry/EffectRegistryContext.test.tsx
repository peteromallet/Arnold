import type { FC, ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  EffectRegistryProvider,
  useEffectRegistryContext,
  useEffectRegistrySnapshot,
  useOptionalEffectRegistryContext,
} from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import type { EffectRegistryRecord } from '@/tools/video-editor/effects/registry/types.ts';

const Component: FC<{ children: ReactNode }> = ({ children }) => children;

function record(
  effectId: string,
  overrides: Partial<EffectRegistryRecord> = {},
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `${effectId}.contribution`,
    component: Component,
    provenance: 'trusted-loader',
    ownerExtensionId: 'com.example.owner',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

const wrapper = ({ children }: { children: ReactNode }) => (
  <EffectRegistryProvider>{children}</EffectRegistryProvider>
);

describe('EffectRegistryContext', () => {
  it('returns an empty frozen snapshot outside a provider and a nullable optional context', () => {
    const snapshotHook = renderHook(() => useEffectRegistrySnapshot());
    const optionalHook = renderHook(() => useOptionalEffectRegistryContext());

    expect(snapshotHook.result.current.records).toEqual([]);
    expect(snapshotHook.result.current.get('fx.missing')).toBeUndefined();
    expect(snapshotHook.result.current.has('fx.missing')).toBe(false);
    expect(Object.isFrozen(snapshotHook.result.current)).toBe(true);
    expect(optionalHook.result.current).toBeNull();
  });

  it('throws for required context access outside a provider', () => {
    expect(() => renderHook(() => useEffectRegistryContext())).toThrow(
      'useEffectRegistryContext must be called inside an EffectRegistryProvider',
    );
  });

  it('exposes a provider-local registry and updates snapshots through useSyncExternalStore subscriptions', () => {
    const { result } = renderHook(() => ({
      context: useEffectRegistryContext(),
      snapshot: useEffectRegistrySnapshot(),
    }), { wrapper });

    const initialSnapshot = result.current.snapshot;
    expect(initialSnapshot.records).toHaveLength(0);

    act(() => {
      result.current.context.registry.register(record('fx.fade'));
    });

    expect(result.current.snapshot).not.toBe(initialSnapshot);
    expect(result.current.snapshot.records.map((entry) => entry.effectId)).toEqual(['fx.fade']);
    expect(result.current.snapshot.get('fx.fade')?.component).toBe(Component);
    expect(result.current.context.snapshot).toBe(result.current.snapshot);
  });

  it('scopes registries per provider mount', () => {
    const first = renderHook(() => useEffectRegistryContext(), { wrapper });
    const second = renderHook(() => useEffectRegistryContext(), { wrapper });

    expect(first.result.current.registry).not.toBe(second.result.current.registry);

    act(() => {
      first.result.current.registry.register(record('fx.first'));
    });

    expect(first.result.current.snapshot.has('fx.first')).toBe(true);
    expect(second.result.current.snapshot.has('fx.first')).toBe(false);
  });

  it('disposes the provider-owned registry on unmount', () => {
    const dispose = vi.fn();
    const { result, unmount } = renderHook(() => useEffectRegistryContext(), { wrapper });

    act(() => {
      result.current.registry.register(record('fx.cleanup', { dispose }));
    });
    unmount();

    expect(dispose).toHaveBeenCalledTimes(1);
  });
});
