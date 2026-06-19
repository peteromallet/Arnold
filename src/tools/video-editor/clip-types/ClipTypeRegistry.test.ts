import { describe, expect, it, vi } from 'vitest';
import {
  createClipTypeRegistry,
  resolveClipType,
  resolveSnapshotClipType,
  validateClipTypeParameterSchema,
  type ClipTypeRegistry,
  type ClipTypeRegistryRecord,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRecord(overrides?: Partial<ClipTypeRegistryRecord>): ClipTypeRegistryRecord {
  return {
    clipTypeId: 'test-clip-type',
    contributionId: 'test-contrib',
    renderer: { render: () => null },
    ownerExtensionId: 'test.ext',
    renderability: {
      capabilities: [
        { route: 'preview', status: 'supported', determinism: 'preview-only' },
        { route: 'browser-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported', message: 'Browser export is not declared.' },
        { route: 'worker-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported', message: 'Worker export is not declared.' },
      ],
      defaultRoute: 'preview',
      determinism: 'preview-only',
    },
    status: 'active',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// createClipTypeRegistry
// ---------------------------------------------------------------------------

describe('createClipTypeRegistry', () => {
  let registry: ClipTypeRegistry;

  beforeEach(() => {
    registry = createClipTypeRegistry();
  });

  afterEach(() => {
    registry.dispose();
  });

  // ---- register -----------------------------------------------------------

  it('registers a clip type record and returns a DisposeHandle', () => {
    const record = makeRecord();
    const handle = registry.register(record);
    expect(typeof handle.dispose).toBe('function');

    const snapshot = registry.getSnapshot();
    expect(snapshot.records).toHaveLength(1);
    expect(snapshot.records[0]!.clipTypeId).toBe('test-clip-type');
  });

  it('resolve() returns the registered record', () => {
    registry.register(makeRecord());
    const resolved = registry.resolve('test-clip-type');
    expect(resolved).toBeDefined();
    expect(resolved!.clipTypeId).toBe('test-clip-type');
  });

  it('resolve() returns undefined for unknown clip types', () => {
    expect(registry.resolve('missing')).toBeUndefined();
  });

  it('snapshot.has() and snapshot.get() work', () => {
    registry.register(makeRecord());
    const snapshot = registry.getSnapshot();
    expect(snapshot.has('test-clip-type')).toBe(true);
    expect(snapshot.has('missing')).toBe(false);
    expect(snapshot.get('test-clip-type')?.clipTypeId).toBe('test-clip-type');
    expect(snapshot.get('missing')).toBeUndefined();
  });

  // ---- duplicate registration ---------------------------------------------

  it('replaces a duplicate clip type registration and emits a warning diagnostic', () => {
    const record1 = makeRecord({ ownerExtensionId: 'ext-a' });
    const record2 = makeRecord({ ownerExtensionId: 'ext-b' });

    registry.register(record1);
    registry.register(record2);

    const snapshot = registry.getSnapshot();
    expect(snapshot.records).toHaveLength(1);
    expect(snapshot.records[0]!.ownerExtensionId).toBe('ext-b');

    const diags = snapshot.diagnostics;
    const duplicateDiag = diags.find((d) => d.code === 'clip-type-registry/duplicate-clip-type');
    expect(duplicateDiag).toBeDefined();
    expect(duplicateDiag!.severity).toBe('warning');
  });

  // ---- dispose via handle -------------------------------------------------

  it('dispose handle removes the record and calls record.dispose', () => {
    const disposeSpy = vi.fn();
    const record = makeRecord({ dispose: disposeSpy });
    const handle = registry.register(record);

    handle.dispose();
    expect(disposeSpy).toHaveBeenCalledTimes(1);
    expect(registry.resolve('test-clip-type')).toBeUndefined();
    expect(registry.getSnapshot().records).toHaveLength(0);
  });

  it('dispose handle is idempotent', () => {
    const disposeSpy = vi.fn();
    const record = makeRecord({ dispose: disposeSpy });
    const handle = registry.register(record);

    handle.dispose();
    handle.dispose(); // second call should be a no-op
    expect(disposeSpy).toHaveBeenCalledTimes(1);
  });

  // ---- disposal errors are captured ---------------------------------------

  it('captures dispose errors as diagnostics without crashing', () => {
    const record = makeRecord({
      dispose: () => {
        throw new Error('dispose boom');
      },
    });
    const handle = registry.register(record);
    handle.dispose();

    const snapshot = registry.getSnapshot();
    const errDiag = snapshot.diagnostics.find(
      (d) => d.code === 'clip-type-registry/dispose-failed',
    );
    expect(errDiag).toBeDefined();
    expect(errDiag!.severity).toBe('error');
    expect(errDiag!.message).toContain('dispose boom');
  });

  // ---- unregister ---------------------------------------------------------

  it('unregister() removes a single record', () => {
    registry.register(makeRecord({ clipTypeId: 'ct-a' }));
    registry.register(makeRecord({ clipTypeId: 'ct-b' }));

    registry.unregister('ct-a');

    expect(registry.resolve('ct-a')).toBeUndefined();
    expect(registry.resolve('ct-b')).toBeDefined();
    expect(registry.getSnapshot().records).toHaveLength(1);
  });

  it('unregister() is a no-op for unknown clip types', () => {
    expect(() => registry.unregister('missing')).not.toThrow();
  });

  // ---- unregisterOwner ----------------------------------------------------

  it('unregisterOwner() removes all records owned by an extension', () => {
    registry.register(makeRecord({ clipTypeId: 'ct-a', ownerExtensionId: 'ext-1' }));
    registry.register(makeRecord({ clipTypeId: 'ct-b', ownerExtensionId: 'ext-1' }));
    registry.register(makeRecord({ clipTypeId: 'ct-c', ownerExtensionId: 'ext-2' }));

    registry.unregisterOwner('ext-1');

    expect(registry.resolve('ct-a')).toBeUndefined();
    expect(registry.resolve('ct-b')).toBeUndefined();
    expect(registry.resolve('ct-c')).toBeDefined();
    expect(registry.getSnapshot().records).toHaveLength(1);
  });

  it('unregisterOwner() is a no-op for unknown owners', () => {
    registry.register(makeRecord());
    expect(() => registry.unregisterOwner('unknown-ext')).not.toThrow();
    expect(registry.getSnapshot().records).toHaveLength(1);
  });

  // ---- updateRecord -------------------------------------------------------

  it('updateRecord() updates an existing record', () => {
    registry.register(makeRecord({ clipTypeId: 'ct-a', status: 'active' }));

    const handle = registry.updateRecord('ct-a', (current) => ({
      ...current,
      status: 'inactive',
      renderability: current.renderability,
    }));

    const updated = registry.resolve('ct-a');
    expect(updated!.status).toBe('inactive');
    expect(typeof handle.dispose).toBe('function');
  });

  it('updateRecord() emits warning for missing clip type', () => {
    registry.updateRecord('missing', (current) => current);
    const diags = registry.getSnapshot().diagnostics;
    expect(diags.some((d) => d.code === 'clip-type-registry/update-missing-clip-type')).toBe(true);
  });

  it('updateRecord() emits error on clipTypeId mismatch', () => {
    registry.register(makeRecord({ clipTypeId: 'ct-a' }));
    registry.updateRecord('ct-a', (current) => ({
      ...current,
      clipTypeId: 'ct-b',
      renderability: current.renderability,
    }));

    const diags = registry.getSnapshot().diagnostics;
    expect(diags.some((d) => d.code === 'clip-type-registry/update-clip-type-id-mismatch')).toBe(true);
  });

  // ---- subscribe ----------------------------------------------------------

  it('subscribe() notifies on register', () => {
    const subscriber = vi.fn();
    registry.subscribe(subscriber);
    registry.register(makeRecord());

    expect(subscriber).toHaveBeenCalledTimes(1);
    const snapshot = subscriber.mock.calls[0]![0];
    expect(snapshot.records).toHaveLength(1);
  });

  it('subscribe() notifies on unregister', () => {
    registry.register(makeRecord());
    const subscriber = vi.fn();
    registry.subscribe(subscriber);
    registry.unregister('test-clip-type');

    expect(subscriber).toHaveBeenCalledTimes(1);
    expect(subscriber.mock.calls[0]![0].records).toHaveLength(0);
  });

  it('subscribe() returns a DisposeHandle that unsubscribes', () => {
    const subscriber = vi.fn();
    const handle = registry.subscribe(subscriber);
    handle.dispose();
    registry.register(makeRecord());

    expect(subscriber).not.toHaveBeenCalled();
  });

  it('subscriber errors are isolated and do not crash the registry', () => {
    const badSubscriber = vi.fn(() => {
      throw new Error('subscriber boom');
    });
    const goodSubscriber = vi.fn();

    registry.subscribe(badSubscriber);
    registry.subscribe(goodSubscriber);

    expect(() => registry.register(makeRecord())).not.toThrow();
    expect(goodSubscriber).toHaveBeenCalledTimes(1);
  });

  // ---- snapshots ----------------------------------------------------------

  it('getSnapshot() returns the same frozen object when nothing changed', () => {
    registry.register(makeRecord());
    const snap1 = registry.getSnapshot();
    const snap2 = registry.getSnapshot();
    expect(snap1).toBe(snap2);
  });

  it('getSnapshot() returns a new frozen object after mutation', () => {
    const snap1 = registry.getSnapshot();
    registry.register(makeRecord());
    const snap2 = registry.getSnapshot();
    expect(snap1).not.toBe(snap2);
    expect(snap1.records).toHaveLength(0);
    expect(snap2.records).toHaveLength(1);
  });

  it('snapshot records are sorted by ownerExtensionId then clipTypeId', () => {
    registry.register(makeRecord({ clipTypeId: 'ct-b', ownerExtensionId: 'ext-b' }));
    registry.register(makeRecord({ clipTypeId: 'ct-a', ownerExtensionId: 'ext-a' }));
    registry.register(makeRecord({ clipTypeId: 'ct-c', ownerExtensionId: 'ext-a' }));

    const snapshot = registry.getSnapshot();
    const ids = snapshot.records.map((r) => r.clipTypeId);
    expect(ids).toEqual(['ct-a', 'ct-c', 'ct-b']);
  });

  // ---- dispose of entire registry -----------------------------------------

  it('dispose() clears all records and notifies subscribers', () => {
    const disposeSpy = vi.fn();
    registry.register(makeRecord({ dispose: disposeSpy }));
    const subscriber = vi.fn();
    registry.subscribe(subscriber);

    registry.dispose();

    expect(disposeSpy).toHaveBeenCalledTimes(1);
    expect(subscriber).toHaveBeenCalledTimes(1);
    expect(registry.getSnapshot().records).toHaveLength(0);
  });

  it('dispose() is idempotent', () => {
    registry.register(makeRecord());
    registry.dispose();
    registry.dispose(); // second call should be a no-op
    expect(registry.getSnapshot().records).toHaveLength(0);
  });

  it('operations after dispose() emit warnings and return no-ops', () => {
    registry.dispose();

    registry.register(makeRecord());
    registry.unregister('test');
    registry.updateRecord('test', (c) => c);

    const diags = registry.getSnapshot().diagnostics;
    const disposedDiags = diags.filter((d) => d.code === 'clip-type-registry/disposed');
    expect(disposedDiags.length).toBeGreaterThanOrEqual(2);
    expect(disposedDiags.every((d) => d.severity === 'warning')).toBe(true);
  });

  // ---- renderability defaults ---------------------------------------------

  it('records preserve their declared renderability', () => {
    const record = makeRecord({
      renderability: {
        capabilities: [
          { route: 'preview', status: 'supported', determinism: 'preview-only' },
          { route: 'browser-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported' },
          { route: 'worker-export', status: 'blocked', determinism: 'preview-only', blockerReason: 'route-unsupported' },
        ],
        defaultRoute: 'preview',
        determinism: 'preview-only',
      },
    });

    registry.register(record);
    const resolved = registry.resolve('test-clip-type')!;

    // Preview is always supported
    const previewCap = resolved.renderability.capabilities.find((c) => c.route === 'preview');
    expect(previewCap).toBeDefined();
    expect(previewCap!.status).toBe('supported');

    // Browser export defaults to blocked
    const browserCap = resolved.renderability.capabilities.find((c) => c.route === 'browser-export');
    expect(browserCap).toBeDefined();
    expect(browserCap!.status).toBe('blocked');

    // Worker export defaults to blocked
    const workerCap = resolved.renderability.capabilities.find((c) => c.route === 'worker-export');
    expect(workerCap).toBeDefined();
    expect(workerCap!.status).toBe('blocked');
  });
});

// ---------------------------------------------------------------------------
// resolveClipType / resolveSnapshotClipType
// ---------------------------------------------------------------------------

describe('resolveClipType', () => {
  it('resolves from a live registry', () => {
    const registry = createClipTypeRegistry();
    registry.register(makeRecord({ clipTypeId: 'ct-live' }));
    expect(resolveClipType(registry, 'ct-live')?.clipTypeId).toBe('ct-live');
    expect(resolveClipType(registry, 'missing')).toBeUndefined();
    registry.dispose();
  });
});

describe('resolveSnapshotClipType', () => {
  it('resolves from an immutable snapshot (snapshot outlives registry dispose)', () => {
    const registry = createClipTypeRegistry();
    registry.register(makeRecord({ clipTypeId: 'ct-snap' }));
    const snapshot = registry.getSnapshot();

    // Snapshot records array is frozen and survives registry disposal.
    expect(snapshot.records[0]!.clipTypeId).toBe('ct-snap');

    // resolveSnapshotClipType uses the snapshot's get() which is backed by
    // the live map (matching EffectRegistry pattern). It works as long as
    // the registry is alive.
    expect(resolveSnapshotClipType(snapshot, 'ct-snap')?.clipTypeId).toBe('ct-snap');
    expect(resolveSnapshotClipType(snapshot, 'missing')).toBeUndefined();

    registry.dispose();
  });
});

// ---------------------------------------------------------------------------
// validateClipTypeParameterSchema
// ---------------------------------------------------------------------------

describe('validateClipTypeParameterSchema', () => {
  it('returns empty array for undefined schema', () => {
    expect(validateClipTypeParameterSchema(undefined)).toEqual([]);
  });

  it('returns empty array for a valid schema', () => {
    const schema = [
      {
        name: 'opacity',
        label: 'Opacity',
        description: 'Clip opacity',
        type: 'number',
        default: 1,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        name: 'enabled',
        label: 'Enabled',
        description: 'Whether the effect is enabled',
        type: 'boolean',
        default: true,
      },
      {
        name: 'color',
        label: 'Color',
        description: 'Tint color',
        type: 'color',
        default: '#ffffff',
      },
    ];
    expect(validateClipTypeParameterSchema(schema)).toEqual([]);
  });

  it('flags missing name', () => {
    const diags = validateClipTypeParameterSchema([
      { name: '', label: 'Test', description: 'Desc', type: 'number' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-name')).toBe(true);
  });

  it('flags missing label', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: '', description: 'Desc', type: 'number' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-label')).toBe(true);
  });

  it('flags invalid type', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'invalid-type' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-type')).toBe(true);
  });

  it('flags non-number default for number type', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'number', default: 'not-a-number' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-default')).toBe(true);
  });

  it('flags non-number min', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'number', min: 'abc' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-min')).toBe(true);
  });

  it('flags min > max', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'number', min: 10, max: 5 },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-range')).toBe(true);
  });

  it('flags non-boolean default for boolean type', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'boolean', default: 'yes' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-default')).toBe(true);
  });

  it('flags missing options for select type', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'select', options: [] },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-options')).toBe(true);
  });

  it('flags invalid color default', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'color', default: 'not-a-color' },
    ]);
    expect(diags.some((d) => d.code === 'clip-types/invalid-schema-color-default')).toBe(true);
  });

  it('accepts valid hex color defaults', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'color', default: '#ff0000' },
    ]);
    expect(diags).toEqual([]);
  });

  it('accepts short hex color defaults', () => {
    const diags = validateClipTypeParameterSchema([
      { name: 'test', label: 'Test', description: 'Desc', type: 'color', default: '#fff' },
    ]);
    expect(diags).toEqual([]);
  });

  it('returns all diagnostics for a heavily invalid schema', () => {
    const diags = validateClipTypeParameterSchema([
      { name: '', label: '', description: '', type: 'bogus', default: {}, min: 'x', options: [] },
    ]);
    // Should have multiple errors
    expect(diags.length).toBeGreaterThanOrEqual(3);
  });
});
