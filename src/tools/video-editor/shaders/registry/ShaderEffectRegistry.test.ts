import { describe, expect, it, vi } from 'vitest';
import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';

const FRAGMENT_SOURCE = 'void main() { gl_FragColor = vec4(1.0); }';
const REPLACEMENT_FRAGMENT_SOURCE = 'void main() { gl_FragColor = vec4(0.0); }';

function record(
  shaderId: string,
  overrides: Partial<ShaderEffectRegistryRecord> = {},
): ShaderEffectRegistryRecord {
  return {
    shaderId,
    contributionId: `${shaderId}.contribution`,
    label: shaderId,
    source: {
      kind: 'inline',
      fragment: FRAGMENT_SOURCE,
    },
    pass: {
      kind: 'clip',
      inputTextureUniform: 'uTexture',
      colorSpace: 'srgb',
      alpha: 'preserve',
    },
    uniforms: [
      {
        name: 'amount',
        label: 'Amount',
        type: 'float',
        default: 0.5,
        min: 0,
        max: 1,
        step: 0.01,
      },
    ],
    textures: [
      {
        name: 'clipFrame',
        label: 'Clip Frame',
        sourceKind: 'clip-frame',
        required: true,
        filter: 'linear',
        wrap: 'clamp-to-edge',
      },
    ],
    fallback: 'bypass',
    provenance: 'trusted-loader',
    ownerExtensionId: 'com.example.owner',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'preview-only',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'preview-only',
        },
        {
          route: 'worker-export',
          status: 'blocked',
          determinism: 'preview-only',
          blockerReason: 'missing-material',
          message: 'Shader preview is not export support.',
        },
      ],
      blockers: [
        {
          id: `${shaderId}.worker-export`,
          severity: 'error',
          route: 'worker-export',
          reason: 'missing-material',
          message: 'Shader requires a materializer before export.',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

describe('createShaderEffectRegistry', () => {
  it('registers provider-owner scoped records and resolves unknown IDs as undefined', () => {
    const registry = createShaderEffectRegistry();
    const handle = registry.register(record('shader.glow'));

    expect(registry.resolve('shader.glow', 'com.example.owner')?.source).toMatchObject({
      kind: 'inline',
      fragment: FRAGMENT_SOURCE,
    });
    expect(registry.resolve('shader.glow')).toBeUndefined();
    expect(registry.resolve('shader.missing', 'com.example.owner')).toBeUndefined();
    expect(typeof handle.dispose).toBe('function');
  });

  it('allows the same shader ID from different owner scopes without replacement', () => {
    const registry = createShaderEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    registry.register(record('shader.glow', {
      ownerExtensionId: 'com.example.a',
      contributionId: 'a.glow',
      dispose: disposeA,
    }));
    registry.register(record('shader.glow', {
      ownerExtensionId: 'com.example.b',
      contributionId: 'b.glow',
      dispose: disposeB,
    }));

    expect(registry.getSnapshot().records).toHaveLength(2);
    expect(registry.resolve('shader.glow', 'com.example.a')?.contributionId).toBe('a.glow');
    expect(registry.resolve('shader.glow', 'com.example.b')?.contributionId).toBe('b.glow');
    expect(disposeA).not.toHaveBeenCalled();
    expect(disposeB).not.toHaveBeenCalled();
  });

  it('produces frozen memoized snapshots and invalidates them on mutation', () => {
    const registry = createShaderEffectRegistry();
    registry.register(record('shader.glow'));

    const snapshotA = registry.getSnapshot();
    const snapshotB = registry.getSnapshot();
    expect(snapshotA).toBe(snapshotB);
    expect(Object.isFrozen(snapshotA)).toBe(true);
    expect(Object.isFrozen(snapshotA.records)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0])).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].source)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].pass)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].uniforms)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].uniforms?.[0])).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].textures)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);
    expect(Object.isFrozen(snapshotA.records[0].renderability.blockers)).toBe(true);

    registry.register(record('shader.zoom'));
    expect(registry.getSnapshot()).not.toBe(snapshotA);
  });

  it('orders snapshot records deterministically by owner, shader ID, then contribution ID', () => {
    const registry = createShaderEffectRegistry();
    registry.register(record('shader.z', { ownerExtensionId: 'com.example.b' }));
    registry.register(record('shader.b', { ownerExtensionId: 'com.example.a', contributionId: 'a.b.2' }));
    registry.register(record('shader.a', { ownerExtensionId: 'com.example.a' }));

    expect(registry.getSnapshot().records.map((entry) => `${entry.ownerExtensionId}:${entry.shaderId}:${entry.contributionId}`))
      .toEqual([
        'com.example.a:shader.a:shader.a.contribution',
        'com.example.a:shader.b:a.b.2',
        'com.example.b:shader.z:shader.z.contribution',
      ]);
  });

  it('notifies subscribers with the current snapshot and isolates subscriber errors', () => {
    const registry = createShaderEffectRegistry();
    const bad = vi.fn(() => {
      throw new Error('subscriber failed');
    });
    const good = vi.fn();
    registry.subscribe(bad);
    const handle = registry.subscribe(good);

    registry.register(record('shader.glow'));
    expect(bad).toHaveBeenCalledTimes(1);
    expect(good).toHaveBeenCalledTimes(1);
    expect(good.mock.calls[0][0].records).toHaveLength(1);

    handle.dispose();
    registry.register(record('shader.zoom'));
    expect(good).toHaveBeenCalledTimes(1);
  });

  it('replaces duplicates in the same owner scope, disposes the previous record once, and leaves stale handles inert', () => {
    const registry = createShaderEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('shader.glow', { dispose: disposeA }));
    const handleB = registry.register(record('shader.glow', {
      contributionId: 'shader.glow.replacement',
      source: {
        kind: 'inline',
        fragment: REPLACEMENT_FRAGMENT_SOURCE,
      },
      dispose: disposeB,
    }));

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('shader.glow', 'com.example.owner')?.source).toMatchObject({
      kind: 'inline',
      fragment: REPLACEMENT_FRAGMENT_SOURCE,
    });
    expect(registry.getSnapshot().diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: 'shader-effect-registry/duplicate-shader',
          severity: 'warning',
          contributionId: 'shader.glow.replacement',
        }),
      ]),
    );

    handleA.dispose();
    expect(registry.resolve('shader.glow', 'com.example.owner')?.contributionId)
      .toBe('shader.glow.replacement');
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('shader.glow', 'com.example.owner')).toBeUndefined();
  });

  it('updates existing owner-scoped records without treating stale handles as current', () => {
    const registry = createShaderEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    const handleA = registry.register(record('shader.hmr', { dispose: disposeA }));
    const handleB = registry.updateRecord(
      { shaderId: 'shader.hmr', ownerExtensionId: 'com.example.owner' },
      (current) => ({
        ...current,
        contributionId: 'shader.hmr.replacement',
        source: {
          kind: 'inline',
          fragment: REPLACEMENT_FRAGMENT_SOURCE,
        },
      }),
      disposeB,
    );

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(registry.resolve('shader.hmr', 'com.example.owner')?.contributionId)
      .toBe('shader.hmr.replacement');

    handleA.dispose();
    expect(registry.resolve('shader.hmr', 'com.example.owner')).toBeDefined();
    expect(disposeA).toHaveBeenCalledTimes(1);

    handleB.dispose();
    handleB.dispose();
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('shader.hmr', 'com.example.owner')).toBeUndefined();
  });

  it('rejects updates that change the owner-scoped shader key and keeps the existing record', () => {
    const registry = createShaderEffectRegistry();
    const disposeA = vi.fn();
    registry.register(record('shader.keyed', { dispose: disposeA }));
    const handle = registry.updateRecord(
      { shaderId: 'shader.keyed', ownerExtensionId: 'com.example.owner' },
      (current) => ({
        ...current,
        shaderId: 'shader.other',
      }),
    );

    expect(registry.resolve('shader.keyed', 'com.example.owner')).toBeDefined();
    expect(registry.resolve('shader.other', 'com.example.owner')).toBeUndefined();
    expect(disposeA).not.toHaveBeenCalled();
    expect(registry.getSnapshot().diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: 'shader-effect-registry/update-shader-key-mismatch',
          severity: 'error',
        }),
      ]),
    );
    handle.dispose();
    expect(registry.resolve('shader.keyed', 'com.example.owner')).toBeDefined();
  });

  it('unregister disposes a removed record exactly once and preserves other owner scopes', () => {
    const registry = createShaderEffectRegistry();
    const disposeA = vi.fn();
    const disposeB = vi.fn();
    registry.register(record('shader.glow', { ownerExtensionId: 'com.example.a', dispose: disposeA }));
    registry.register(record('shader.glow', { ownerExtensionId: 'com.example.b', dispose: disposeB }));

    registry.unregister('shader.glow', 'com.example.a');
    registry.unregister('shader.glow', 'com.example.a');

    expect(disposeA).toHaveBeenCalledTimes(1);
    expect(disposeB).not.toHaveBeenCalled();
    expect(registry.resolve('shader.glow', 'com.example.a')).toBeUndefined();
    expect(registry.resolve('shader.glow', 'com.example.b')).toBeDefined();
  });

  it('unregisterOwner cleans up every owner record once without clearing other owners or diagnostics', () => {
    const registry = createShaderEffectRegistry();
    const disposeA1 = vi.fn();
    const disposeA2 = vi.fn();
    const disposeB = vi.fn();
    registry.register(record('shader.a1', { ownerExtensionId: 'com.example.a', dispose: disposeA1 }));
    registry.register(record('shader.a2', { ownerExtensionId: 'com.example.a', dispose: disposeA2 }));
    registry.register(record('shader.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
    registry.register(record('shader.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));

    registry.unregisterOwner('com.example.a');
    registry.unregisterOwner('com.example.a');

    expect(disposeA1).toHaveBeenCalledTimes(1);
    expect(disposeA2).toHaveBeenCalledTimes(1);
    expect(disposeB).toHaveBeenCalledTimes(1);
    expect(registry.resolve('shader.a1', 'com.example.a')).toBeUndefined();
    expect(registry.resolve('shader.a2', 'com.example.a')).toBeUndefined();
    expect(registry.resolve('shader.b', 'com.example.b')).toBeDefined();
    expect(registry.getSnapshot().diagnostics.some((d) => d.code === 'shader-effect-registry/duplicate-shader'))
      .toBe(true);
  });

  it('preserves error-status records and freezes record diagnostics', () => {
    const registry = createShaderEffectRegistry();
    registry.register(record('shader.invalid', {
      status: 'error',
      diagnostics: [
        {
          severity: 'error',
          code: 'shader/compile-failed',
          message: 'Fragment shader failed to compile.',
          detail: {
            source: 'fragment',
            line: 1,
          },
        },
      ],
      renderability: {
        defaultRoute: 'preview',
        determinism: 'preview-only',
        capabilities: [
          {
            route: 'preview',
            status: 'blocked',
            determinism: 'preview-only',
            blockerReason: 'unknown',
            message: 'Shader cannot preview until compile errors are resolved.',
          },
        ],
      },
    }));

    const entry = registry.getSnapshot().get('shader.invalid', 'com.example.owner');
    expect(entry?.status).toBe('error');
    expect(entry?.diagnostics?.[0]).toMatchObject({
      code: 'shader/compile-failed',
      severity: 'error',
      detail: {
        source: 'fragment',
        line: 1,
      },
    });
    expect(Object.isFrozen(entry?.diagnostics)).toBe(true);
    expect(Object.isFrozen(entry?.diagnostics?.[0])).toBe(true);
    expect(Object.isFrozen(entry?.diagnostics?.[0].detail)).toBe(true);
  });

  it('dispose is idempotent, clears records, and captures dispose failures as diagnostics', () => {
    const registry = createShaderEffectRegistry();
    const listener = vi.fn();
    registry.subscribe(listener);
    registry.register(record('shader.bad', {
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
          code: 'shader-effect-registry/dispose-failed',
          severity: 'error',
          contributionId: 'shader.bad.contribution',
        }),
      ]),
    );
  });
});
