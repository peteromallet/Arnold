import { describe, expect, it, vi } from 'vitest';
import {
  createRendererRegistry,
  type RendererRegistry,
  type RendererRegistrySnapshot,
} from '@/tools/video-editor/runtime/extensionRendererRegistry';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function noopRenderer(): void {}
function noopRenderer2(): void {}

function lastSnapshot(registry: RendererRegistry): RendererRegistrySnapshot {
  return registry.getSnapshot();
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

describe('createRendererRegistry — registration', () => {
  it('registers a renderer scoped by extension ID + render ID', () => {
    const reg = createRendererRegistry();
    const handle = reg.register('com.example.ext', 'render/btn', noopRenderer);

    expect(reg.resolve('com.example.ext', 'render/btn')).toBe(noopRenderer);
    expect(typeof handle.dispose).toBe('function');
  });

  it('registers multiple renderers for the same extension', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'render/btn', noopRenderer);
    reg.register('com.example.ext', 'render/dlg', noopRenderer2);

    expect(reg.resolve('com.example.ext', 'render/btn')).toBe(noopRenderer);
    expect(reg.resolve('com.example.ext', 'render/dlg')).toBe(noopRenderer2);
  });

  it('registers renderers for different extensions independently', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.a', 'r1', noopRenderer);
    reg.register('com.example.b', 'r1', noopRenderer2);

    expect(reg.resolve('com.example.a', 'r1')).toBe(noopRenderer);
    expect(reg.resolve('com.example.b', 'r1')).toBe(noopRenderer2);
  });

  it('resolve returns undefined for unknown extension or render ID', () => {
    const reg = createRendererRegistry();
    expect(reg.resolve('com.example.nope', 'r1')).toBeUndefined();
    reg.register('com.example.ext', 'r1', noopRenderer);
    expect(reg.resolve('com.example.ext', 'r2')).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Duplicate diagnostics
// ---------------------------------------------------------------------------

describe('createRendererRegistry — duplicate diagnostics', () => {
  it('emits a duplicate diagnostic when re-registering the same extension+renderId', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);

    const before = lastSnapshot(reg);
    expect(before.diagnostics).toHaveLength(0);

    reg.register('com.example.ext', 'r1', noopRenderer2);
    const after = lastSnapshot(reg);

    const dupDiags = after.diagnostics.filter((d) => d.code === 'render/duplicate-renderer');
    expect(dupDiags).toHaveLength(1);
    expect(dupDiags[0].severity).toBe('warning');
    expect(dupDiags[0].extensionId).toBe('com.example.ext');
    expect(dupDiags[0].message).toContain('r1');
    expect(dupDiags[0].message).toContain('com.example.ext');
  });

  it('replaces the previous renderer on duplicate registration', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);
    reg.register('com.example.ext', 'r1', noopRenderer2);

    expect(reg.resolve('com.example.ext', 'r1')).toBe(noopRenderer2);
  });
});

// ---------------------------------------------------------------------------
// DisposeHandle cleanup
// ---------------------------------------------------------------------------

describe('createRendererRegistry — DisposeHandle cleanup', () => {
  it('disposing a handle removes the binding', () => {
    const reg = createRendererRegistry();
    const handle = reg.register('com.example.ext', 'r1', noopRenderer);

    expect(reg.resolve('com.example.ext', 'r1')).toBe(noopRenderer);

    handle.dispose();
    expect(reg.resolve('com.example.ext', 'r1')).toBeUndefined();
  });

  it('disposing a handle is idempotent', () => {
    const reg = createRendererRegistry();
    const handle = reg.register('com.example.ext', 'r1', noopRenderer);

    handle.dispose();
    handle.dispose(); // should not throw
    expect(reg.resolve('com.example.ext', 'r1')).toBeUndefined();
  });

  it('disposing one handle does not affect other bindings', () => {
    const reg = createRendererRegistry();
    const h1 = reg.register('com.example.ext', 'r1', noopRenderer);
    reg.register('com.example.ext', 'r2', noopRenderer2);

    h1.dispose();
    expect(reg.resolve('com.example.ext', 'r1')).toBeUndefined();
    expect(reg.resolve('com.example.ext', 'r2')).toBe(noopRenderer2);
  });

  it('unregister removes a single binding', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);
    reg.register('com.example.ext', 'r2', noopRenderer2);

    reg.unregister('com.example.ext', 'r1');
    expect(reg.resolve('com.example.ext', 'r1')).toBeUndefined();
    expect(reg.resolve('com.example.ext', 'r2')).toBe(noopRenderer2);
  });

  it('unregister is a no-op for unknown bindings', () => {
    const reg = createRendererRegistry();
    expect(() => reg.unregister('com.example.nope', 'r1')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// unregisterAll — extension disposal
// ---------------------------------------------------------------------------

describe('createRendererRegistry — unregisterAll (extension disposal)', () => {
  it('removes all renderers for a given extension', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.a', 'r1', noopRenderer);
    reg.register('com.example.a', 'r2', noopRenderer2);
    reg.register('com.example.b', 'r1', noopRenderer);

    reg.unregisterAll('com.example.a');

    expect(reg.resolve('com.example.a', 'r1')).toBeUndefined();
    expect(reg.resolve('com.example.a', 'r2')).toBeUndefined();
    // Other extension unaffected
    expect(reg.resolve('com.example.b', 'r1')).toBe(noopRenderer);
  });

  it('unregisterAll is idempotent', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.a', 'r1', noopRenderer);

    reg.unregisterAll('com.example.a');
    reg.unregisterAll('com.example.a'); // should not throw
    expect(reg.resolve('com.example.a', 'r1')).toBeUndefined();
  });

  it('unregisterAll does not clear historical diagnostics', () => {
    const reg = createRendererRegistry();
    // Produce a duplicate diagnostic
    reg.register('com.example.ext', 'r1', noopRenderer);
    reg.register('com.example.ext', 'r1', noopRenderer2);

    const beforeUnregister = lastSnapshot(reg);
    const dupCount = beforeUnregister.diagnostics.filter((d) => d.code === 'render/duplicate-renderer').length;
    expect(dupCount).toBe(1);

    reg.unregisterAll('com.example.ext');

    const after = lastSnapshot(reg);
    expect(after.diagnostics.filter((d) => d.code === 'render/duplicate-renderer')).toHaveLength(1);
  });

  it('unregisterAll for unknown extension is a no-op', () => {
    const reg = createRendererRegistry();
    expect(() => reg.unregisterAll('com.example.nope')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Subscribers
// ---------------------------------------------------------------------------

describe('createRendererRegistry — subscribers', () => {
  it('notifies subscribers after registration', () => {
    const reg = createRendererRegistry();
    const listener = vi.fn();
    reg.subscribe(listener);

    reg.register('com.example.ext', 'r1', noopRenderer);
    expect(listener).toHaveBeenCalledTimes(1);

    const snap = listener.mock.calls[0][0] as RendererRegistrySnapshot;
    expect(snap.entries).toHaveLength(1);
    expect(snap.entries[0].extensionId).toBe('com.example.ext');
    expect(snap.entries[0].renderId).toBe('r1');
  });

  it('notifies subscribers after unregister', () => {
    const reg = createRendererRegistry();
    const handle = reg.register('com.example.ext', 'r1', noopRenderer);
    const listener = vi.fn();
    reg.subscribe(listener);

    handle.dispose();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0].entries).toHaveLength(0);
  });

  it('notifies subscribers after unregisterAll', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);
    const listener = vi.fn();
    reg.subscribe(listener);

    reg.unregisterAll('com.example.ext');
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0].entries).toHaveLength(0);
  });

  it('subscribe returns a DisposeHandle that stops notifications', () => {
    const reg = createRendererRegistry();
    const listener = vi.fn();
    const subHandle = reg.subscribe(listener);

    subHandle.dispose();
    reg.register('com.example.ext', 'r1', noopRenderer);
    expect(listener).not.toHaveBeenCalled();
  });

  it('subscriber errors do not prevent other subscribers', () => {
    const reg = createRendererRegistry();
    const badListener = vi.fn().mockImplementation(() => {
      throw new Error('boom');
    });
    const goodListener = vi.fn();

    reg.subscribe(badListener);
    reg.subscribe(goodListener);

    reg.register('com.example.ext', 'r1', noopRenderer);

    expect(badListener).toHaveBeenCalledTimes(1);
    expect(goodListener).toHaveBeenCalledTimes(1);
  });

  it('multiple subscribers all receive notifications', () => {
    const reg = createRendererRegistry();
    const a = vi.fn();
    const b = vi.fn();
    reg.subscribe(a);
    reg.subscribe(b);

    reg.register('com.example.ext', 'r1', noopRenderer);
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Snapshot
// ---------------------------------------------------------------------------

describe('createRendererRegistry — snapshot', () => {
  it('getSnapshot returns a frozen snapshot', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);

    const snap = reg.getSnapshot();
    expect(Object.isFrozen(snap)).toBe(true);
    expect(Object.isFrozen(snap.entries)).toBe(true);
    expect(Object.isFrozen(snap.diagnostics)).toBe(true);
    expect(Object.isFrozen(snap.entries[0])).toBe(true);
  });

  it('getSnapshot is referentially stable when nothing changes', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);

    const snap1 = reg.getSnapshot();
    const snap2 = reg.getSnapshot();
    expect(snap1).toBe(snap2);
  });

  it('getSnapshot returns a new reference after mutation', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);
    const snap1 = reg.getSnapshot();

    reg.register('com.example.ext', 'r2', noopRenderer2);
    const snap2 = reg.getSnapshot();
    expect(snap1).not.toBe(snap2);
  });

  it('entries are sorted by extensionId then renderId', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.b', 'render/z', noopRenderer);
    reg.register('com.example.a', 'render/b', noopRenderer);
    reg.register('com.example.a', 'render/a', noopRenderer);
    reg.register('com.example.b', 'render/a', noopRenderer);

    const snap = reg.getSnapshot();
    const ids = snap.entries.map((e) => `${e.extensionId}::${e.renderId}`);
    expect(ids).toEqual([
      'com.example.a::render/a',
      'com.example.a::render/b',
      'com.example.b::render/a',
      'com.example.b::render/z',
    ]);
  });

  it('get lookup helper resolves entries', () => {
    const reg = createRendererRegistry();
    reg.register('com.example.ext', 'r1', noopRenderer);
    reg.register('com.example.ext', 'r2', noopRenderer2);

    const snap = reg.getSnapshot();
    expect(snap.get('com.example.ext', 'r1')).toBe(noopRenderer);
    expect(snap.get('com.example.ext', 'r2')).toBe(noopRenderer2);
    expect(snap.get('com.example.nope', 'r1')).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Empty registry
// ---------------------------------------------------------------------------

describe('createRendererRegistry — empty registry', () => {
  it('returns a valid empty snapshot for a fresh registry', () => {
    const reg = createRendererRegistry();
    const snap = reg.getSnapshot();

    expect(snap.entries).toHaveLength(0);
    expect(snap.diagnostics).toHaveLength(0);
    expect(Object.isFrozen(snap)).toBe(true);
  });

  it('resolve on empty registry returns undefined', () => {
    const reg = createRendererRegistry();
    expect(reg.resolve('com.example.ext', 'r1')).toBeUndefined();
  });
});
