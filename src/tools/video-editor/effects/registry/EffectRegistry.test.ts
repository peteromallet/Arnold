import type { FC, ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { createEffectRegistry } from '@/tools/video-editor/effects/registry/EffectRegistry.ts';
import type { EffectRegistryRecord } from '@/tools/video-editor/effects/registry/types.ts';

const Component: FC<{ children: ReactNode }> = ({ children }) => children;
const ReplacementComponent: FC<{ children: ReactNode }> = ({ children }) => children;

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

describe('createEffectRegistry', () => {
  it('registers provider-local records and resolves unknown IDs as undefined', () => {
    const registry = createEffectRegistry();
    const handle = registry.register(record('fx.fade'));

    expect(registry.resolve('fx.fade')?.component).toBe(Component);
    expect(registry.resolve('fx.missing')).toBeUndefined();
    expect(typeof handle.dispose).toBe('function');
  });

  it('produces frozen memoized snapshots and invalidates them on mutation', () => {
    const registry = createEffectRegistry();
    registry.register(record('fx.fade'));

    const snapshotA = registry.getSnapshot();
    const snapshotB = registry.getSnapshot();
    expect(snapshotA).toBe(snapshotB);
    expect(Object.isFrozen(snapshotA)).toBe(true);
    expect(Object.isFrozen(snapshotA.records)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0])).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);

    registry.register(record('fx.zoom'));
    expect(registry.getSnapshot()).not.toBe(snapshotA);
  });

  it('orders snapshot records deterministically by owner then effect ID', () => {
    const registry = createEffectRegistry();
    registry.register(record('fx.z', { ownerExtensionId: 'com.example.b' }));
    registry.register(record('fx.b', { ownerExtensionId: 'com.example.a' }));
    registry.register(record('fx.a', { ownerExtensionId: 'com.example.a' }));

    expect(registry.getSnapshot().records.map((entry) => `${entry.ownerExtensionId}:${entry.effectId}`))
      .toEqual([
        'com.example.a:fx.a',
        'com.example.a:fx.b',
        'com.example.b:fx.z',
      ]);
  });

  it('notifies subscribers with the current snapshot and isolates subscriber errors', () => {
    const registry = createEffectRegistry();
    const bad = vi.fn(() => {
      throw new Error('subscriber failed');
    });
    const good = vi.fn();
    registry.subscribe(bad);
    const handle = registry.subscribe(good);

    registry.register(record('fx.fade'));
    expect(bad).toHaveBeenCalledTimes(1);
    expect(good).toHaveBeenCalledTimes(1);
    expect(good.mock.calls[0][0].records).toHaveLength(1);

    handle.dispose();
    registry.register(record('fx.zoom'));
    expect(good).toHaveBeenCalledTimes(1);
  });

  it('replaces duplicate/HMR records, disposes the previous record once, and leaves stale handles inert', () => {
    const registry = createEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('fx.fade', { dispose: disposeA }));
    const handleB = registry.register(record('fx.fade', {
      component: ReplacementComponent,
      contributionId: 'fx.fade.replacement',
      dispose: disposeB,
    }));

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('fx.fade')?.component).toBe(ReplacementComponent);
    expect(registry.getSnapshot().diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: 'effect-registry/duplicate-effect',
          severity: 'warning',
          contributionId: 'fx.fade.replacement',
        }),
      ]),
    );

    handleA.dispose();
    expect(registry.resolve('fx.fade')?.component).toBe(ReplacementComponent);
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('fx.fade')).toBeUndefined();
  });

  it('updates existing records for HMR replacement without treating stale handles as current', () => {
    const registry = createEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('fx.hmr', { dispose: disposeA }));
    const handleB = registry.updateRecord('fx.hmr', (current) => ({
      ...current,
      component: ReplacementComponent,
      contributionId: 'fx.hmr.replacement',
    }), disposeB);

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('fx.hmr')?.component).toBe(ReplacementComponent);
    expect(registry.resolve('fx.hmr')?.contributionId).toBe('fx.hmr.replacement');

    handleA.dispose();
    expect(registry.resolve('fx.hmr')).toBeDefined();
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('fx.hmr')).toBeUndefined();
  });

  it('unregister disposes a removed record exactly once and preserves other records', () => {
    const registry = createEffectRegistry();
    const disposeFade = vi.fn();
    const disposeZoom = vi.fn();
    registry.register(record('fx.fade', { dispose: disposeFade }));
    registry.register(record('fx.zoom', { dispose: disposeZoom }));

    registry.unregister('fx.fade');
    registry.unregister('fx.fade');

    expect(disposeFade).toHaveBeenCalledTimes(1);
    expect(disposeZoom).not.toHaveBeenCalled();
    expect(registry.resolve('fx.fade')).toBeUndefined();
    expect(registry.resolve('fx.zoom')).toBeDefined();
  });

  it('unregisterOwner cleans up every owner record once without clearing other owners or diagnostics', () => {
    const registry = createEffectRegistry();
    const disposeA1 = vi.fn();
    const disposeA2 = vi.fn();
    const disposeB = vi.fn();
    registry.register(record('fx.a1', { ownerExtensionId: 'com.example.a', dispose: disposeA1 }));
    registry.register(record('fx.a2', { ownerExtensionId: 'com.example.a', dispose: disposeA2 }));
    registry.register(record('fx.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
    registry.register(record('fx.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));

    registry.unregisterOwner('com.example.a');
    registry.unregisterOwner('com.example.a');

    expect(disposeA1).toHaveBeenCalledTimes(1);
    expect(disposeA2).toHaveBeenCalledTimes(1);
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('fx.a1')).toBeUndefined();
    expect(registry.resolve('fx.a2')).toBeUndefined();
    expect(registry.resolve('fx.b')).toBeDefined();
    expect(registry.getSnapshot().diagnostics.some((d) => d.code === 'effect-registry/duplicate-effect'))
      .toBe(true);
  });

  it('dispose is idempotent, clears records, and captures dispose failures as diagnostics', () => {
    const registry = createEffectRegistry();
    const listener = vi.fn();
    registry.subscribe(listener);
    registry.register(record('fx.bad', {
      dispose: () => {
        throw new Error('cleanup failed');
      },
    }));
    listener.mockClear();

    registry.dispose();
    registry.dispose();

    const snapshot = registry.getSnapshot();
    expect(snapshot.records).toHaveLength(0);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0].records).toHaveLength(0);
    expect(snapshot.diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: 'effect-registry/dispose-failed',
          severity: 'error',
          contributionId: 'fx.bad.contribution',
        }),
      ]),
    );
  });

  it('keeps record diagnostics and renderability metadata available in snapshots', () => {
    const registry = createEffectRegistry();
    registry.register(record('fx.preview-only', {
      diagnostics: [{
        severity: 'warning',
        code: 'effect/preview-only',
        message: 'Preview-only effect.',
      }],
      renderability: {
        defaultRoute: 'preview',
        determinism: 'preview-only',
        capabilities: [
          {
            route: 'browser-export',
            status: 'blocked',
            determinism: 'preview-only',
            blockerReason: 'preview-only',
          },
        ],
        blockers: [
          {
            id: 'fx.preview-only.browser-export',
            severity: 'error',
            route: 'browser-export',
            reason: 'preview-only',
            message: 'Effect cannot browser-export without a bake.',
          },
        ],
      },
    }));

    const entry = registry.getSnapshot().get('fx.preview-only');
    expect(entry?.provenance).toBe('trusted-loader');
    expect(entry?.renderability.capabilities[0].route).toBe('browser-export');
    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
    expect(entry?.diagnostics?.[0].code).toBe('effect/preview-only');
    expect(Object.isFrozen(entry?.diagnostics)).toBe(true);
  });
});
