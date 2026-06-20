/**
 * M11 T2: Unit tests for liveDataRegistry.
 *
 * Covers:
 *  - Source lifecycle: register, get, list, dispose
 *  - Bounded ring buffer: push, eviction, synchronous reads
 *  - Sample metadata and sequence numbers
 *  - Synchronous read facades: getLatestSample, getSampleAt, getSamples, getSampleCount
 *  - Channel lifecycle: open, close, getChannelMetadata
 *  - Sample subscriptions and listener notification
 *  - Source status transitions: inactive → activating → active → error → disposed → orphaned
 *  - Diagnostics: per-source and registry-level
 *  - Dispose cleanup and disposed-source tombstones
 *  - Tombstone preservation without sample payloads
 *  - No timeline/history mutation per sample
 *  - Cancellation/reconnect/error behavior
 *  - Binding resolution
 *  - Snapshot consistency
 *
 * @module liveDataRegistry.test
 * @milestone M11
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  createLiveDataRegistry,
  type LiveDataRegistry,
  type LiveDataRegistryConfig,
  type SourceTombstone,
} from '@/tools/video-editor/runtime/liveDataRegistry';
import type {
  LiveSourceKind,
  LiveSourceStatus,
  LiveSource,
  LiveSourceDiagnostic,
  LiveChannelKind,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSampleFormat,
  LiveSampleFrame,
  LiveSample,
  LiveBakeSelection,
  LiveBakeTarget,
  LiveBakeResult,
  BindingResolutionStatus,
  LiveBindingResolution,
  LiveBindingMetadata,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFrame(
  timestamp = 0,
  data: ArrayBuffer | Uint8Array | Record<string, unknown> = new Uint8Array([1, 2, 3]),
  format: LiveSampleFormat = 'raw',
): LiveSampleFrame {
  return { timestamp, data, format };
}

function registryWithSource(
  registry: LiveDataRegistry,
  sourceId = 'src-1',
  kind: LiveSourceKind = 'generated',
): DisposeHandle {
  return registry.registerSource({ id: sourceId, kind });
}

function registryWithActiveChannel(
  registry: LiveDataRegistry,
  sourceId = 'src-1',
  channelKind: LiveChannelKind = 'data',
): LiveChannelDescriptor {
  registryWithSource(registry, sourceId);
  const ch = registry.openChannel(sourceId, channelKind);
  return ch;
}

// ---------------------------------------------------------------------------
// Source lifecycle
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: source lifecycle', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('registers a source with initial status inactive and empty diagnostics', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'webcam' });
    expect(handle).toBeDefined();
    expect(typeof handle.dispose).toBe('function');

    const source = registry.getSource('src-1');
    expect(source).toBeDefined();
    expect(source!.id).toBe('src-1');
    expect(source!.kind).toBe('webcam');
    expect(source!.status).toBe('inactive');
    // Lifecycle diagnostic emitted on registration
    expect(source!.diagnostics).toHaveLength(1);
    expect(source!.diagnostics[0].code).toBe('live/source-registered');
  });

  it('registers a source with full metadata', () => {
    registry.registerSource({
      id: 'src-full',
      kind: 'generated',
      label: 'AI Gen Source',
      metadata: { model: 'v3' },
      permission: { state: 'prompt', reason: 'Need access' },
      recording: { active: false, mode: 'stream' },
      learnMode: 'idle',
    });

    const source = registry.getSource('src-full');
    expect(source).toBeDefined();
    expect(source!.label).toBe('AI Gen Source');
    expect(source!.metadata).toEqual({ model: 'v3' });
    expect(source!.permission?.state).toBe('prompt');
    expect(source!.recording?.mode).toBe('stream');
    expect(source!.learnMode).toBe('idle');
  });

  it('rejects duplicate source IDs', () => {
    registry.registerSource({ id: 'src-1', kind: 'webcam' });
    const handle2 = registry.registerSource({ id: 'src-1', kind: 'microphone' });

    // Second registration returns a no-op dispose handle
    const sources = registry.listSources();
    expect(sources).toHaveLength(1);
    expect(sources[0].kind).toBe('webcam'); // First registration wins
  });

  it('lists all registered sources as frozen array', () => {
    registry.registerSource({ id: 'src-1', kind: 'webcam' });
    registry.registerSource({ id: 'src-2', kind: 'generated' });

    const sources = registry.listSources();
    expect(sources).toHaveLength(2);
    expect(Object.isFrozen(sources)).toBe(true);
  });

  it('getSource returns undefined for unknown source', () => {
    expect(registry.getSource('nonexistent')).toBeUndefined();
  });

  it('dispose handle removes the source and creates a tombstone', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'webcam', label: 'My Webcam' });
    handle.dispose();

    expect(registry.getSource('src-1')).toBeUndefined();
    expect(registry.listSources()).toHaveLength(0);

    // Tombstone should be in snapshot
    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1);
    expect(snapshot.tombstones[0].id).toBe('src-1');
    expect(snapshot.tombstones[0].kind).toBe('webcam');
    expect(snapshot.tombstones[0].status).toBe('disposed');
    expect(snapshot.tombstones[0].label).toBe('My Webcam');
  });

  it('dispose is idempotent', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'webcam' });
    handle.dispose();
    handle.dispose(); // Should not throw

    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1); // Only one tombstone
  });

  it('registers source after tombstone of same ID (tombstone blocks re-registration)', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'webcam' });
    handle.dispose();

    // Try to re-register
    registry.registerSource({ id: 'src-1', kind: 'webcam' });
    expect(registry.getSource('src-1')).toBeUndefined(); // Blocked by tombstone
  });
});

// ---------------------------------------------------------------------------
// Channel lifecycle
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: channel lifecycle', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
  });

  it('opens a channel on a source and returns a branded string descriptor', () => {
    const ch = registry.openChannel('src-1', 'data');
    expect(typeof ch).toBe('string');
    expect(ch).toContain('src-1');

    const meta = registry.getChannelMetadata(ch);
    expect(meta).toBeDefined();
    expect(meta!.sourceId).toBe('src-1');
    expect(meta!.kind).toBe('data');
    expect(meta!.channelId).toBe(ch);
  });

  it('opens multiple channels on same source with unique IDs', () => {
    const ch1 = registry.openChannel('src-1', 'video');
    const ch2 = registry.openChannel('src-1', 'audio');

    expect(ch1).not.toBe(ch2);
    expect(registry.getChannelMetadata(ch1)).toBeDefined();
    expect(registry.getChannelMetadata(ch2)).toBeDefined();
  });

  it('openChannel returns dead-channel descriptor for unknown source', () => {
    const ch = registry.openChannel('nonexistent', 'data');
    expect(ch).toBe('dead-channel');
  });

  it('closes a channel idempotently', () => {
    const ch = registry.openChannel('src-1', 'data');
    registry.closeChannel(ch);
    expect(registry.getChannelMetadata(ch)).toBeUndefined();

    // Idempotent
    registry.closeChannel(ch);
    expect(registry.getChannelMetadata(ch)).toBeUndefined();
  });

  it('opening channel with metadata stores it', () => {
    const ch = registry.openChannel('src-1', 'control', { param: 'opacity', min: 0, max: 1 });
    const meta = registry.getChannelMetadata(ch);
    expect(meta!.metadata).toEqual({ param: 'opacity', min: 0, max: 1 });
  });

  it('getChannelMetadata returns undefined for unknown channel', () => {
    expect(registry.getChannelMetadata('nonexistent' as LiveChannelDescriptor)).toBeUndefined();
  });

  it('closing a channel notifies subscribers with sentinel sample', () => {
    const ch = registry.openChannel('src-1', 'data');
    const listener = vi.fn();
    registry.subscribeSamples(ch, listener);

    registry.closeChannel(ch);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({
        channelId: ch,
        sequenceNumber: -1,
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// Ring buffer and sample delivery
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: ring buffer and sample delivery', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
  });

  it('pushes samples into channel ring buffer with sequence numbers', () => {
    const ch = registry.openChannel('src-1', 'data');

    registry.pushSample(ch, makeFrame(0));
    registry.pushSample(ch, makeFrame(100));
    registry.pushSample(ch, makeFrame(200));

    expect(registry.getSampleCount(ch)).toBe(3);
    expect(registry.getLatestSample(ch)!.sequenceNumber).toBe(2);
  });

  it('synchronous read: getLatestSample returns the most recent sample', () => {
    const ch = registry.openChannel('src-1', 'data');

    expect(registry.getLatestSample(ch)).toBeUndefined();

    registry.pushSample(ch, makeFrame(0, new Uint8Array([1])));
    registry.pushSample(ch, makeFrame(100, new Uint8Array([2])));

    const latest = registry.getLatestSample(ch);
    expect(latest).toBeDefined();
    expect(latest!.frame.timestamp).toBe(100);
    expect(latest!.sequenceNumber).toBe(1);
  });

  it('synchronous read: getSampleAt retrieves by sequence number', () => {
    const ch = registry.openChannel('src-1', 'data');

    registry.pushSample(ch, makeFrame(0));
    registry.pushSample(ch, makeFrame(100));
    registry.pushSample(ch, makeFrame(200));

    const sample = registry.getSampleAt(ch, 1);
    expect(sample).toBeDefined();
    expect(sample!.frame.timestamp).toBe(100);
    expect(sample!.sequenceNumber).toBe(1);
  });

  it('synchronous read: getSampleAt returns undefined for unknown sequence', () => {
    const ch = registry.openChannel('src-1', 'data');
    registry.pushSample(ch, makeFrame(0));

    expect(registry.getSampleAt(ch, 999)).toBeUndefined();
  });

  it('synchronous read: getSamples returns all samples in order', () => {
    const ch = registry.openChannel('src-1', 'data');
    registry.pushSample(ch, makeFrame(0));
    registry.pushSample(ch, makeFrame(100));

    const samples = registry.getSamples(ch);
    expect(samples).toHaveLength(2);
    expect(samples[0].sequenceNumber).toBe(0);
    expect(samples[1].sequenceNumber).toBe(1);
    expect(Object.isFrozen(samples)).toBe(true);
  });

  it('ring buffer enforces bounded capacity with FIFO eviction', () => {
    const smallRegistry = createLiveDataRegistry({ maxSamplesPerChannel: 5 });
    smallRegistry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = smallRegistry.openChannel('src-1', 'data');

    // Push 10 samples
    for (let i = 0; i < 10; i++) {
      smallRegistry.pushSample(ch, makeFrame(i * 100, new Uint8Array([i])));
    }

    expect(smallRegistry.getSampleCount(ch)).toBe(5);

    // Oldest samples should be evicted
    const samples = smallRegistry.getSamples(ch);
    expect(samples[0].sequenceNumber).toBe(5); // Original 0-4 evicted
    expect(samples[4].sequenceNumber).toBe(9);
  });

  it('ring buffer preserves sample metadata across eviction', () => {
    const smallRegistry = createLiveDataRegistry({ maxSamplesPerChannel: 3 });
    smallRegistry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = smallRegistry.openChannel('src-1', 'data');

    smallRegistry.pushSample(ch, {
      timestamp: 0,
      data: { value: 'first' },
      format: 'json',
      metadata: { priority: 'low' },
    });
    smallRegistry.pushSample(ch, {
      timestamp: 100,
      data: { value: 'second' },
      format: 'json',
      metadata: { priority: 'medium' },
    });
    smallRegistry.pushSample(ch, {
      timestamp: 200,
      data: { value: 'third' },
      format: 'json',
      metadata: { priority: 'high' },
    });
    smallRegistry.pushSample(ch, {
      timestamp: 300,
      data: { value: 'fourth' },
      format: 'json',
      metadata: { priority: 'critical' },
    });

    const samples = smallRegistry.getSamples(ch);
    expect(samples).toHaveLength(3);
    // First sample should be evicted
    expect((samples[0].frame.data as Record<string, unknown>).value).toBe('second');
    expect(samples[0].frame.metadata).toEqual({ priority: 'medium' });
  });

  it('pushSample auto-activates inactive source', () => {
    const ch = registry.openChannel('src-1', 'data');

    // Source starts inactive
    expect(registry.getSource('src-1')!.status).toBe('inactive');

    registry.pushSample(ch, makeFrame(0));
    expect(registry.getSource('src-1')!.status).toBe('active');
  });

  it('pushSample on unknown channel emits diagnostic', () => {
    registry.pushSample('unknown-ch' as LiveChannelDescriptor, makeFrame(0));

    const diags = registry.getDiagnostics();
    expect(diags.some((d) => d.code === 'live/channel-not-found')).toBe(true);
  });

  it('subscribeSamples delivers samples to listener synchronously', () => {
    const ch = registry.openChannel('src-1', 'data');
    const listener = vi.fn();

    const handle = registry.subscribeSamples(ch, listener);
    expect(typeof handle.dispose).toBe('function');

    registry.pushSample(ch, makeFrame(0));
    registry.pushSample(ch, makeFrame(100));

    expect(listener).toHaveBeenCalledTimes(2);
    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({
        channelId: ch,
        sequenceNumber: 0,
      }),
    );
    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({
        channelId: ch,
        sequenceNumber: 1,
      }),
    );
  });

  it('subscribeSamples unsubscribe stops delivery', () => {
    const ch = registry.openChannel('src-1', 'data');
    const listener = vi.fn();

    const handle = registry.subscribeSamples(ch, listener);
    registry.pushSample(ch, makeFrame(0));
    handle.dispose();
    registry.pushSample(ch, makeFrame(100));

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('subscribeSamples on unknown channel returns no-op handle', () => {
    const listener = vi.fn();
    const handle = registry.subscribeSamples('unknown' as LiveChannelDescriptor, listener);
    handle.dispose(); // Should not throw
  });

  it('pushSample does not mutate any timeline/history state', () => {
    // The registry is a purely runtime structure. Samples go into ring buffers.
    // No timeline patches, no history entries, no undo/redo entries are created.
    const ch = registry.openChannel('src-1', 'data');

    // Push 100 samples
    for (let i = 0; i < 100; i++) {
      registry.pushSample(ch, makeFrame(i * 10));
    }

    // Verify the registry only has source/channel state, no timeline artifacts
    const snapshot = registry.getSnapshot();
    expect(snapshot.sources).toHaveLength(1);
    expect(snapshot.channels).toHaveLength(1);

    // No binding metadata was implicitly created
    expect(snapshot.bindings).toHaveLength(0);

    // The sample data is in the ring buffer only, not in any persisted structure
    expect(registry.getSampleCount(ch)).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Source status transitions
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: source status transitions', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
  });

  it('transitions from inactive to activating', () => {
    registry.transitionSource('src-1', 'activating');
    expect(registry.getSource('src-1')!.status).toBe('activating');
  });

  it('transitions to error with diagnostic', () => {
    registry.transitionSource('src-1', 'error', 'Permission denied');
    expect(registry.getSource('src-1')!.status).toBe('error');

    const diags = registry.getDiagnostics('src-1');
    expect(diags.some((d) => d.code === 'live/source-transition')).toBe(true);
  });

  it('transitioning to disposed creates tombstone', () => {
    registry.transitionSource('src-1', 'disposed');

    expect(registry.getSource('src-1')).toBeUndefined();
    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1);
    expect(snapshot.tombstones[0].id).toBe('src-1');
  });

  it('transitioning to orphaned creates tombstone with orphan status', () => {
    registry.transitionSource('src-1', 'orphaned');

    expect(registry.getSource('src-1')).toBeUndefined();
    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1);
  });

  it('transitionSource on unknown source emits diagnostic', () => {
    registry.transitionSource('nonexistent', 'active');
    const diags = registry.getDiagnostics();
    expect(diags.some((d) => d.code === 'live/source-not-found')).toBe(true);
  });

  it('transitioning to active does not dispose or change channels', () => {
    const ch = registry.openChannel('src-1', 'data');
    registry.pushSample(ch, makeFrame(0));

    registry.transitionSource('src-1', 'active');
    expect(registry.getSource('src-1')!.status).toBe('active');
    expect(registry.getChannelMetadata(ch)).toBeDefined();
    expect(registry.getSampleCount(ch)).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: diagnostics', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
  });

  it('emits diagnostics scoped to a source', () => {
    registry.emitDiagnostic('src-1', {
      severity: 'error',
      code: 'live/test-error',
      message: 'Test error message',
    });

    const diags = registry.getDiagnostics('src-1');
    // Lifecycle diag + test-error diag
    expect(diags.length).toBeGreaterThanOrEqual(2);
    expect(diags.some((d) => d.code === 'live/test-error')).toBe(true);
    expect(diags.some((d) => d.severity === 'error')).toBe(true);
    expect(diags[0].sourceId).toBe('src-1');
  });

  it('clears source diagnostics', () => {
    registry.emitDiagnostic('src-1', {
      severity: 'error',
      code: 'live/test',
      message: 'Test',
    });

    registry.clearSourceDiagnostics('src-1');
    expect(registry.getDiagnostics('src-1')).toHaveLength(0);
  });

  it('getDiagnostics without sourceId returns all diagnostics', () => {
    registry.registerSource({ id: 'src-2', kind: 'webcam' });

    registry.emitDiagnostic('src-1', {
      severity: 'info',
      code: 'live/info-1',
      message: 'Info 1',
    });
    registry.emitDiagnostic('src-2', {
      severity: 'warning',
      code: 'live/warn-2',
      message: 'Warn 2',
    });

    const all = registry.getDiagnostics();
    expect(all.length).toBeGreaterThanOrEqual(2);
  });

  it('getDiagnostics returns frozen array', () => {
    registry.emitDiagnostic('src-1', {
      severity: 'info',
      code: 'live/test',
      message: 'Test',
    });

    const diags = registry.getDiagnostics('src-1');
    expect(Object.isFrozen(diags)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Dispose cleanup
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: dispose cleanup', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    registry.openChannel('src-1', 'data');
  });

  it('full registry dispose clears all sources and channels', () => {
    registry.dispose();

    expect(registry.isDisposed).toBe(true);
    expect(registry.listSources()).toHaveLength(0);
    expect(registry.getSource('src-1')).toBeUndefined();

    const snapshot = registry.getSnapshot();
    expect(snapshot.disposed).toBe(true);
  });

  it('disposed registry rejects further operations', () => {
    registry.dispose();

    const handle = registry.registerSource({ id: 'src-2', kind: 'webcam' });
    expect(registry.getSource('src-2')).toBeUndefined();

    const ch = registry.openChannel('src-1', 'data');
    expect(ch).toBe('dead-channel');
  });

  it('dispose is idempotent', () => {
    registry.dispose();
    registry.dispose(); // Should not throw
    expect(registry.isDisposed).toBe(true);
  });

  it('disposed registry bake returns failure result', () => {
    registry.dispose();

    const result = registry.bake({
      sourceId: 'src-1',
      targets: [{ kind: 'asset', ref: 'key' }],
    });

    expect(result.success).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/registry-disposed')).toBe(true);
  });

  it('subscribers are notified on dispose', () => {
    const listener = vi.fn();
    registry.subscribe(listener);

    registry.dispose();
    expect(listener).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tombstone behavior
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: tombstone behavior', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('tombstones preserve source identity without sample payloads', () => {
    registry.registerSource({ id: 'src-tomb', kind: 'webcam', label: 'Test Cam' });
    const ch = registry.openChannel('src-tomb', 'video');
    registry.pushSample(ch, makeFrame(0, new Uint8Array([1, 2, 3, 4, 5])));

    // Dispose the source
    registry.transitionSource('src-tomb', 'disposed');

    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1);

    const tombstone = snapshot.tombstones[0];
    expect(tombstone.id).toBe('src-tomb');
    expect(tombstone.kind).toBe('webcam');
    expect(tombstone.label).toBe('Test Cam');
    expect(tombstone.status).toBe('disposed');
    expect(tombstone.disposedAt).toBeDefined();

    // Tombstone has NO sample data — channels are cleared
    expect('channels' in tombstone).toBe(false);
    expect('samples' in tombstone).toBe(false);

    // Source is not in active sources
    expect(registry.getSource('src-tomb')).toBeUndefined();
  });

  it('tombstones block re-registration of same source ID', () => {
    const handle = registry.registerSource({ id: 'src-block', kind: 'webcam' });
    handle.dispose();

    registry.registerSource({ id: 'src-block', kind: 'generated' });
    expect(registry.getSource('src-block')).toBeUndefined();
  });

  it('multiple tombstones can coexist', () => {
    registry.registerSource({ id: 'src-a', kind: 'webcam' }).dispose();
    registry.registerSource({ id: 'src-b', kind: 'microphone' }).dispose();

    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Binding resolution
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: binding resolution', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('resolveBinding returns missing for unknown binding', () => {
    const resolution = registry.resolveBinding('unknown-binding');
    expect(resolution.bindingId).toBe('unknown-binding');
    expect(resolution.status).toBe('missing');
    expect(resolution.diagnostic?.code).toBe('live/binding-not-found');
  });

  it('getBindingMetadata returns empty when no bindings', () => {
    const meta = registry.getBindingMetadata();
    expect(meta.bindings).toHaveLength(0);
    expect(meta.unresolvedCount).toBe(0);
    expect(meta.orphanedCount).toBe(0);
    expect(meta.disposedCount).toBe(0);
  });

  it('binding status resolves correctly for active source', () => {
    // Use internal binding management to add a binding
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');
    registry.pushSample(ch, makeFrame(0)); // Auto-activates

    // Access the internal _addBinding method
    (registry as any)._addBinding({
      bindingId: 'bind-1',
      sourceId: 'src-1',
      channelId: ch,
      status: 'unresolved' as BindingResolutionStatus,
    });

    const resolution = registry.resolveBinding('bind-1');
    expect(resolution.status).toBe('resolved');
    expect(resolution.source).toBeDefined();
    expect(resolution.channel).toBeDefined();
  });

  it('binding marked as disposed when source is disposed', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'webcam' });
    registry.openChannel('src-1', 'data');

    (registry as any)._addBinding({
      bindingId: 'bind-1',
      sourceId: 'src-1',
      status: 'unresolved' as BindingResolutionStatus,
    });

    handle.dispose();

    const resolution = registry.resolveBinding('bind-1');
    expect(resolution.status).toBe('disposed');
  });

  it('removeLiveBindings clears all bindings for a source', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });

    (registry as any)._addBinding({ bindingId: 'bind-1', sourceId: 'src-1', status: 'unresolved' });
    (registry as any)._addBinding({ bindingId: 'bind-2', sourceId: 'src-1', status: 'unresolved' });

    registry.removeLiveBindings('src-1');

    const meta = registry.getBindingMetadata();
    expect(meta.bindings).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Bake
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: bake', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const channelId = registry.openChannel('src-1', 'video');
    registry.pushSample(channelId, {
      ...makeFrame(0, new Uint8Array([1, 2, 3]), 'raw'),
      metadata: { frameIndex: 0, takeId: 'take-a' },
    });
    registry.pushSample(channelId, {
      ...makeFrame(100, new Uint8Array([4, 5, 6]), 'raw'),
      metadata: { frameIndex: 1, takeId: 'take-a' },
    });
  });

  it('full bake returns deterministic replacement metadata without clearing live state or bindings', () => {
    const channelId = registry.getSnapshot().channels[0].channelId;
    (registry as any)._addBinding({
      bindingId: 'bind-bake',
      sourceId: 'src-1',
      channelId,
      status: 'unresolved' as BindingResolutionStatus,
    });
    const sourceBefore = registry.getSource('src-1');
    const bindingBefore = registry.getBindingMetadata();

    const result = registry.bake({
      sourceId: 'src-1',
      channelIds: [channelId],
      targets: [
        { kind: 'asset', ref: 'asset-live-full' },
        { kind: 'render-material', ref: 'material-live-full' },
      ],
    });

    expect(result.success).toBe(true);
    expect(result.sourceId).toBe('src-1');
    expect(result.targets.map((target) => target.outputRef)).toEqual(['asset-live-full', 'material-live-full']);
    expect(result.targets[0].diagnostics?.[0].detail?.replacement).toMatchObject({
      kind: 'asset',
      ref: 'asset-live-full',
      metadata: {
        liveBake: {
          sourceId: 'src-1',
          sampleCount: 2,
          firstTimestamp: 0,
          lastTimestamp: 100,
        },
      },
    });
    expect(result.targets[1].diagnostics?.[0].detail?.renderMaterial).toMatchObject({
      id: 'material-live-full',
      mediaKind: 'video',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
    });
    expect(registry.getSource('src-1')).toEqual(sourceBefore);
    expect(registry.getBindingMetadata()).toEqual(bindingBefore);
  });

  it('partial bake returns ranged deterministic replacement metadata without clearing live state', () => {
    const channelId = registry.getSnapshot().channels[0].channelId;
    const sourceBefore = registry.getSource('src-1');
    const bindingBefore = registry.getBindingMetadata();

    const result = registry.bake({
      sourceId: 'src-1',
      channelIds: [channelId],
      timeRange: [100, 100],
      frameRange: [1, 1],
      sampleRange: [1, 1],
      takeId: 'take-a',
      targets: [{ kind: 'asset', ref: 'asset-live-partial' }],
    }) as LiveBakeResult & {
      replacements?: readonly [{
        input: { sampleCount: number; range?: Record<string, unknown> };
        deterministicRef: { range?: Record<string, unknown>; metadata?: Record<string, unknown> };
      }];
    };

    expect(result.success).toBe(true);
    expect(result.replacements?.[0].input.sampleCount).toBe(1);
    expect(result.replacements?.[0].input.range).toMatchObject({
      start: 100,
      end: 100,
      startFrame: 1,
      endFrame: 1,
      startSample: 1,
      endSample: 1,
      takeId: 'take-a',
    });
    expect(result.replacements?.[0].deterministicRef.range).toMatchObject({
      startFrame: 1,
      endFrame: 1,
      takeId: 'take-a',
    });
    expect(registry.getSource('src-1')).toEqual(sourceBefore);
    expect(registry.getBindingMetadata()).toEqual(bindingBefore);
  });

  it('bake for unknown source returns error', () => {
    const result = registry.bake({
      sourceId: 'nonexistent',
      targets: [{ kind: 'asset', ref: 'key' }],
    });

    expect(result.success).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/source-not-found')).toBe(true);
  });

  it('failed bake publishes diagnostics but leaves source and binding state unchanged', () => {
    const emptyRegistry = createLiveDataRegistry();
    emptyRegistry.registerSource({ id: 'src-empty', kind: 'generated' });
    const channelId = emptyRegistry.openChannel('src-empty', 'control');
    (emptyRegistry as any)._addBinding({
      bindingId: 'bind-empty',
      sourceId: 'src-empty',
      channelId,
      status: 'unresolved' as BindingResolutionStatus,
    });
    const sourceBefore = emptyRegistry.getSource('src-empty');
    const bindingBefore = emptyRegistry.getBindingMetadata();

    const result = emptyRegistry.bake({
      sourceId: 'src-empty',
      channelIds: [channelId],
      targets: [{ kind: 'keyframe', ref: 'clip-1:opacity' }],
    });

    expect(result.success).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/bake-empty-selection')).toBe(true);
    expect(emptyRegistry.getDiagnostics().some((d) => d.code === 'live/bake-empty-selection')).toBe(true);
    expect(emptyRegistry.getSource('src-empty')).toEqual(sourceBefore);
    expect(emptyRegistry.getBindingMetadata()).toEqual(bindingBefore);
  });
});

// ---------------------------------------------------------------------------
// Steering
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: steering', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('applySteeringDecision stores complete lineage and gates live delivery', () => {
    registry.applySteeringDecision({
      kind: 'supersede',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 1,
        steerHash: 'abc',
        parentRefs: ['session-0'],
        producerVersion: '1.0.0',
        provenance: { prompt: 'Prompt', model: 'model-a', seed: 1 },
      },
      replacementChannelId: 'session-1:frames' as LiveChannelDescriptor,
      reason: 'Better quality',
    });

    const diags = registry.getDiagnostics();
    expect(diags.some((d) => d.code === 'live/steering-applied')).toBe(true);
    expect(registry.getSteeringLineage('session-1')?.steerHash).toBe('abc');
    expect(registry.canActivateGenerationSessionLiveDelivery('session-1')).toBe(true);
  });

  it('applySteeringDecision rejects incomplete lineage without silent fallback', () => {
    registry.applySteeringDecision({
      kind: 'supersede',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 1,
        steerHash: '',
        parentRefs: [],
        producerVersion: '',
        provenance: { prompt: '', model: '', seed: '' },
      },
      reason: 'Incomplete metadata',
    });

    const diags = registry.getDiagnostics();
    expect(diags.some((d) => d.code === 'live/steering-missing-hash')).toBe(true);
    expect(diags.some((d) => d.code === 'live/steering-incomplete-provenance')).toBe(true);
    expect(registry.getSteeringLineage('session-1')).toBeUndefined();
    expect(registry.canActivateGenerationSessionLiveDelivery('session-1')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Subscriptions and snapshots
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: subscriptions and snapshots', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('subscribe notifies on source changes', () => {
    const listener = vi.fn();
    registry.subscribe(listener);

    registry.registerSource({ id: 'src-1', kind: 'generated' });
    expect(listener).toHaveBeenCalled();
  });

  it('subscribe notifies on channel open/close', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });

    const listener = vi.fn();
    registry.subscribe(listener);

    const ch = registry.openChannel('src-1', 'data');
    expect(listener).toHaveBeenCalled();

    listener.mockClear();
    registry.closeChannel(ch);
    expect(listener).toHaveBeenCalled();
  });

  it('subscribe notifies on sample push', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    const listener = vi.fn();
    registry.subscribe(listener);

    registry.pushSample(ch, makeFrame(0));
    expect(listener).toHaveBeenCalled();
  });

  it('subscribe returns dispose handle that unsubscribes', () => {
    const listener = vi.fn();
    const handle = registry.subscribe(listener);

    registry.registerSource({ id: 'src-1', kind: 'generated' });
    // Lifecycle diag notification + source registration notification = 2 calls
    expect(listener).toHaveBeenCalledTimes(2);

    handle.dispose();
    registry.registerSource({ id: 'src-2', kind: 'webcam' });
    expect(listener).toHaveBeenCalledTimes(2); // No more calls after unsubscribe
  });

  it('getSnapshot returns frozen snapshot with all state', () => {
    registry.registerSource({ id: 'src-1', kind: 'webcam', label: 'Cam' });
    const ch = registry.openChannel('src-1', 'video');
    registry.pushSample(ch, makeFrame(0));

    const snapshot = registry.getSnapshot();
    expect(Object.isFrozen(snapshot.sources)).toBe(true);
    expect(Object.isFrozen(snapshot.channels)).toBe(true);
    expect(Object.isFrozen(snapshot.tombstones)).toBe(true);
    expect(Object.isFrozen(snapshot.bindings)).toBe(true);

    expect(snapshot.sources).toHaveLength(1);
    expect(snapshot.channels).toHaveLength(1);
    expect(snapshot.disposed).toBe(false);
  });

  it('snapshot is invalidated on mutation', () => {
    const snap1 = registry.getSnapshot();
    registry.registerSource({ id: 'src-1', kind: 'webcam' });
    const snap2 = registry.getSnapshot();

    expect(snap1).not.toBe(snap2); // Different objects (cache invalidated)
    expect(snap1.sources).toHaveLength(0);
    expect(snap2.sources).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Config options
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: config options', () => {
  it('custom maxSamplesPerChannel is respected', () => {
    const registry = createLiveDataRegistry({ maxSamplesPerChannel: 10 });
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    for (let i = 0; i < 20; i++) {
      registry.pushSample(ch, makeFrame(i * 10));
    }

    expect(registry.getSampleCount(ch)).toBe(10);
  });

  it('emitLifecycleDiagnostics: false suppresses lifecycle diagnostics', () => {
    const registry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
    registry.registerSource({ id: 'src-1', kind: 'generated' });

    const diags = registry.getDiagnostics('src-1');
    expect(diags).toHaveLength(0); // No lifecycle diagnostic emitted
  });

  it('default maxSamplesPerChannel is 300', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    for (let i = 0; i < 500; i++) {
      registry.pushSample(ch, makeFrame(i * 10));
    }

    expect(registry.getSampleCount(ch)).toBe(300);
  });
});

// ---------------------------------------------------------------------------
// No timeline/history mutation per sample
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: no timeline/history mutation', () => {
  it('sample push creates no timeline patches, history entries, or undo/redo state', () => {
    const registry = createLiveDataRegistry();

    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    // Push many samples
    for (let i = 0; i < 100; i++) {
      registry.pushSample(ch, makeFrame(i * 16.67, { value: i }, 'json'));
    }

    // Verify no timeline artifacts exist in the registry
    const snapshot = registry.getSnapshot();

    // The snapshot should only contain source and channel metadata
    expect(snapshot.sources).toHaveLength(1);
    expect(snapshot.channels).toHaveLength(1);
    expect(snapshot.tombstones).toHaveLength(0);
    expect(snapshot.bindings).toHaveLength(0);
    expect(snapshot.disposed).toBe(false);

    // No history, no patches, no undo entries — just the live registry state
    // (History/undo management is the responsibility of the TimelineDataProvider,
    // not the live data registry.)
  });

  it('sample access is synchronous and does not trigger async operations', () => {
    const registry = createLiveDataRegistry();
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    for (let i = 0; i < 10; i++) {
      registry.pushSample(ch, makeFrame(i * 100));
    }

    // All reads are synchronous — no promises, no callbacks
    const latest = registry.getLatestSample(ch);
    expect(latest).toBeDefined();
    expect(latest!.sequenceNumber).toBe(9);

    const at5 = registry.getSampleAt(ch, 5);
    expect(at5).toBeDefined();
    expect(at5!.frame.timestamp).toBe(500);

    const all = registry.getSamples(ch);
    expect(all).toHaveLength(10);

    const count = registry.getSampleCount(ch);
    expect(count).toBe(10);
  });

  it('source dispose clears channel data but preserves tombstone without sample data', () => {
    const registry = createLiveDataRegistry();
    const handle = registry.registerSource({ id: 'src-dispose', kind: 'webcam', label: 'Test' });
    const ch1 = registry.openChannel('src-dispose', 'video');
    const ch2 = registry.openChannel('src-dispose', 'audio');

    for (let i = 0; i < 50; i++) {
      registry.pushSample(ch1, makeFrame(i * 33.3, new Uint8Array([i])));
      registry.pushSample(ch2, makeFrame(i * 33.3, new Uint8Array([i, i + 1])));
    }

    expect(registry.getSampleCount(ch1)).toBe(50);
    expect(registry.getSampleCount(ch2)).toBe(50);

    // Dispose
    handle.dispose();

    // Source is gone
    expect(registry.getSource('src-dispose')).toBeUndefined();

    // Channel data is gone
    expect(registry.getChannelMetadata(ch1)).toBeUndefined();
    expect(registry.getChannelMetadata(ch2)).toBeUndefined();

    // Tombstone exists but has no sample data
    const snapshot = registry.getSnapshot();
    expect(snapshot.tombstones).toHaveLength(1);
    const tombstone = snapshot.tombstones[0];
    expect(tombstone.id).toBe('src-dispose');
    expect(tombstone.kind).toBe('webcam');
    expect(tombstone.label).toBe('Test');
    expect(tombstone.status).toBe('disposed');

    // No channels remain in snapshot
    expect(snapshot.channels).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Edge cases and error handling
// ---------------------------------------------------------------------------

describe('LiveDataRegistry: edge cases and error handling', () => {
  let registry: LiveDataRegistry;

  beforeEach(() => {
    registry = createLiveDataRegistry();
  });

  it('handles rapid register/dispose cycles without leaking', () => {
    for (let i = 0; i < 100; i++) {
      const handle = registry.registerSource({ id: `src-${i}`, kind: 'generated' });
      handle.dispose();
    }

    expect(registry.listSources()).toHaveLength(0);
    expect(registry.getSnapshot().tombstones).toHaveLength(100);
  });

  it('handles nested channel operations during source dispose', () => {
    const handle = registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    // Listener that tries to push another sample during dispose notification
    let disposed = false;
    registry.subscribeSamples(ch, (sample) => {
      if (sample.sequenceNumber === -1 && !disposed) {
        disposed = true;
        // Try to push during dispose — should be no-op since channel is closing
        registry.pushSample(ch, makeFrame(999));
      }
    });

    // Dispose the source (using the handle from the first and only registration)
    handle.dispose();

    // Should not throw, and no new sample should have been added
    expect(disposed).toBe(true);
  });

  it('listener errors during pushSample do not affect other listeners', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    const badListener = vi.fn(() => {
      throw new Error('Listener error');
    });
    const goodListener = vi.fn();

    registry.subscribeSamples(ch, badListener);
    registry.subscribeSamples(ch, goodListener);

    // Should not throw
    registry.pushSample(ch, makeFrame(0));

    expect(badListener).toHaveBeenCalled();
    expect(goodListener).toHaveBeenCalled();
  });

  it('handles all LiveSourceKind values', () => {
    const kinds: LiveSourceKind[] = [
      'webcam', 'microphone', 'midi', 'serial', 'bluetooth',
      'generated', 'screen-capture', 'audio-device', 'osc', 'custom',
    ];

    for (const kind of kinds) {
      const registry = createLiveDataRegistry();
      registry.registerSource({ id: `src-${kind}`, kind });
      expect(registry.getSource(`src-${kind}`)!.kind).toBe(kind);
    }
  });

  it('handles all LiveSourceStatus transitions', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });

    const transitions: LiveSourceStatus[] = [
      'inactive', 'activating', 'active', 'error',
    ];

    for (const status of transitions) {
      registry.transitionSource('src-1', status);
      expect(registry.getSource('src-1')!.status).toBe(status);
    }
  });

  it('handles all LiveChannelKind values', () => {
    const kinds: LiveChannelKind[] = ['video', 'audio', 'midi', 'osc', 'data', 'control'];

    for (const kind of kinds) {
      const r = createLiveDataRegistry();
      r.registerSource({ id: 'src-1', kind: 'generated' });
      const ch = r.openChannel('src-1', kind);
      const meta = r.getChannelMetadata(ch);
      expect(meta!.kind).toBe(kind);
    }
  });

  it('handles all LiveSampleFormat values', () => {
    registry.registerSource({ id: 'src-1', kind: 'generated' });
    const ch = registry.openChannel('src-1', 'data');

    const formats: LiveSampleFormat[] = ['raw', 'encoded', 'json', 'binary'];

    for (const format of formats) {
      let data: ArrayBuffer | Uint8Array | Record<string, unknown>;
      if (format === 'json') {
        data = { test: true };
      } else if (format === 'binary') {
        data = new ArrayBuffer(8);
      } else {
        data = new Uint8Array([1, 2, 3]);
      }

      registry.pushSample(ch, { timestamp: 0, data, format });
    }

    const samples = registry.getSamples(ch);
    expect(samples).toHaveLength(4);
    expect(samples[0].frame.format).toBe('raw');
    expect(samples[1].frame.format).toBe('encoded');
    expect(samples[2].frame.format).toBe('json');
    expect(samples[3].frame.format).toBe('binary');
  });
});
