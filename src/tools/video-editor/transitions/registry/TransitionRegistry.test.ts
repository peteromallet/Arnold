import { describe, expect, it, vi } from 'vitest';
import { createTransitionRegistry } from '@/tools/video-editor/transitions/registry/TransitionRegistry.ts';
import type { TransitionRegistryRecord } from '@/tools/video-editor/transitions/registry/types.ts';

function record(
  transitionId: string,
  overrides: Partial<TransitionRegistryRecord> = {},
): TransitionRegistryRecord {
  return {
    transitionId,
    contributionId: `${transitionId}.contribution`,
    renderer: {},
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

describe('createTransitionRegistry', () => {
  it('registers provider-local records and resolves unknown IDs as undefined', () => {
    const registry = createTransitionRegistry();
    const handle = registry.register(record('transition.fade'));

    expect(registry.resolve('transition.fade')?.renderer).toEqual({});
    expect(registry.resolve('transition.missing')).toBeUndefined();
    expect(typeof handle.dispose).toBe('function');
  });

  it('produces frozen memoized snapshots and invalidates them on mutation', () => {
    const registry = createTransitionRegistry();
    registry.register(record('transition.fade'));

    const snapshotA = registry.getSnapshot();
    const snapshotB = registry.getSnapshot();
    expect(snapshotA).toBe(snapshotB);
    expect(Object.isFrozen(snapshotA)).toBe(true);
    expect(Object.isFrozen(snapshotA.records)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0])).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);

    registry.register(record('transition.zoom'));
    expect(registry.getSnapshot()).not.toBe(snapshotA);
  });

  it('orders snapshot records deterministically by owner then transition ID', () => {
    const registry = createTransitionRegistry();
    registry.register(record('transition.z', { ownerExtensionId: 'com.example.b' }));
    registry.register(record('transition.b', { ownerExtensionId: 'com.example.a' }));
    registry.register(record('transition.a', { ownerExtensionId: 'com.example.a' }));

    expect(registry.getSnapshot().records.map((entry) => `${entry.ownerExtensionId}:${entry.transitionId}`))
      .toEqual([
        'com.example.a:transition.a',
        'com.example.a:transition.b',
        'com.example.b:transition.z',
      ]);
  });

  it('notifies subscribers with the current snapshot and isolates subscriber errors', () => {
    const registry = createTransitionRegistry();
    const bad = vi.fn(() => {
      throw new Error('subscriber failed');
    });
    const good = vi.fn();
    registry.subscribe(bad);
    const handle = registry.subscribe(good);

    registry.register(record('transition.fade'));
    expect(bad).toHaveBeenCalledTimes(1);
    expect(good).toHaveBeenCalledTimes(1);
    expect(good.mock.calls[0][0].records).toHaveLength(1);

    handle.dispose();
    registry.register(record('transition.zoom'));
    expect(good).toHaveBeenCalledTimes(1);
  });

  it('replaces duplicate/HMR records, disposes the previous record once, and leaves stale handles inert', () => {
    const registry = createTransitionRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('transition.fade', { dispose: disposeA }));
    const handleB = registry.register(record('transition.fade', {
      renderer: { replacement: true },
      contributionId: 'transition.fade.replacement',
      dispose: disposeB,
    }));

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('transition.fade')?.renderer).toEqual({ replacement: true });
    expect(registry.getSnapshot().diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: 'transition-registry/duplicate-transition',
          severity: 'warning',
          contributionId: 'transition.fade.replacement',
        }),
      ]),
    );

    handleA.dispose();
    expect(registry.resolve('transition.fade')?.renderer).toEqual({ replacement: true });
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('transition.fade')).toBeUndefined();
  });

  it('updates existing records for HMR replacement without treating stale handles as current', () => {
    const registry = createTransitionRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('transition.hmr', { dispose: disposeA }));
    const handleB = registry.updateRecord('transition.hmr', (current) => ({
      ...current,
      renderer: { updated: true },
      contributionId: 'transition.hmr.replacement',
    }), disposeB);

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('transition.hmr')?.renderer).toEqual({ updated: true });
    expect(registry.resolve('transition.hmr')?.contributionId).toBe('transition.hmr.replacement');

    handleA.dispose();
    expect(registry.resolve('transition.hmr')).toBeDefined();
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('transition.hmr')).toBeUndefined();
  });

  it('unregister disposes a removed record exactly once and preserves other records', () => {
    const registry = createTransitionRegistry();
    const disposeFade = vi.fn();
    const disposeZoom = vi.fn();
    registry.register(record('transition.fade', { dispose: disposeFade }));
    registry.register(record('transition.zoom', { dispose: disposeZoom }));

    registry.unregister('transition.fade');
    registry.unregister('transition.fade');

    expect(disposeFade).toHaveBeenCalledTimes(1);
    expect(disposeZoom).not.toHaveBeenCalled();
    expect(registry.resolve('transition.fade')).toBeUndefined();
    expect(registry.resolve('transition.zoom')).toBeDefined();
  });

  it('unregisterOwner cleans up every owner record once without clearing other owners or diagnostics', () => {
    const registry = createTransitionRegistry();
    const disposeA1 = vi.fn();
    const disposeA2 = vi.fn();
    const disposeB = vi.fn();
    registry.register(record('transition.a1', { ownerExtensionId: 'com.example.a', dispose: disposeA1 }));
    registry.register(record('transition.a2', { ownerExtensionId: 'com.example.a', dispose: disposeA2 }));
    registry.register(record('transition.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
    registry.register(record('transition.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));

    registry.unregisterOwner('com.example.a');
    registry.unregisterOwner('com.example.a');

    expect(disposeA1).toHaveBeenCalledTimes(1);
    expect(disposeA2).toHaveBeenCalledTimes(1);
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('transition.a1')).toBeUndefined();
    expect(registry.resolve('transition.a2')).toBeUndefined();
    expect(registry.resolve('transition.b')).toBeDefined();
    expect(registry.getSnapshot().diagnostics.some((d) => d.code === 'transition-registry/duplicate-transition'))
      .toBe(true);
  });

  it('dispose is idempotent, clears records, and captures dispose failures as diagnostics', () => {
    const registry = createTransitionRegistry();
    const listener = vi.fn();
    registry.subscribe(listener);
    registry.register(record('transition.bad', {
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
          code: 'transition-registry/dispose-failed',
          severity: 'error',
          contributionId: 'transition.bad.contribution',
        }),
      ]),
    );
  });

  it('keeps record diagnostics and renderability metadata available in snapshots', () => {
    const registry = createTransitionRegistry();
    registry.register(record('transition.preview-only', {
      diagnostics: [{
        severity: 'warning',
        code: 'transition/preview-only',
        message: 'Preview-only transition.',
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
            id: 'transition.preview-only.browser-export',
            severity: 'error',
            route: 'browser-export',
            reason: 'preview-only',
            message: 'Transition cannot browser-export without a bake.',
          },
        ],
      },
    }));

    const entry = registry.getSnapshot().get('transition.preview-only');
    expect(entry?.provenance).toBe('trusted-loader');
    expect(entry?.renderability.capabilities[0].route).toBe('browser-export');
    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
    expect(entry?.diagnostics?.[0].code).toBe('transition/preview-only');
    expect(Object.isFrozen(entry?.diagnostics)).toBe(true);
  });
});
