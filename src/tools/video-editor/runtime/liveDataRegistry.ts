/**
 * M11: Provider-scoped live data registry.
 *
 * Implements LiveSessionsService with:
 * - Source lifecycle (register, get, list, dispose)
 * - Bounded per-channel ring buffers with synchronous read facades
 * - Sample metadata tracking
 * - Diagnostics (per-source and registry-wide)
 * - Cancellation/reconnect/error lifecycle transitions
 * - Dispose cleanup with disposed-source tombstones
 * - Subscriptions and listener notification
 *
 * Live samples stay outside timeline mutation/history systems entirely.
 * Persisted binding metadata is the only timeline-resident live state.
 *
 * @module liveDataRegistry
 * @milestone M11
 */

import type {
  DisposeHandle,
  DiagnosticSeverity,
  LiveSourceKind,
  LiveSourceStatus,
  LiveSourceDiagnostic,
  LiveSource,
  LiveChannelKind,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSampleFormat,
  LiveSampleFrame,
  LiveSample,
  LiveSourcePermission,
  LiveRecordingState,
  LiveLearnMode,
  LiveBakeTarget,
  LiveBakeSelection,
  LiveBakeResult,
  SteeringDecisionKind,
  SteeringLineage,
  SteeringDecision,
  BindingResolutionStatus,
  LiveBinding,
  LiveBindingResolution,
  LiveBindingMetadata,
  LiveSessionsService,
} from '@reigh/editor-sdk';
import { bakeLiveSource } from './liveBake';
import {
  evaluateGenerationSessionLiveDeliveryGate,
  validateSteeringDecision,
} from './liveSteering';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export interface LiveDataRegistryConfig {
  /** Maximum number of samples per ring buffer (default: 300). */
  readonly maxSamplesPerChannel?: number;
  /** Whether to emit diagnostic events on lifecycle transitions (default: true). */
  readonly emitLifecycleDiagnostics?: boolean;
}

const DEFAULT_MAX_SAMPLES_PER_CHANNEL = 300;

// ---------------------------------------------------------------------------
// Internal ring buffer
// ---------------------------------------------------------------------------

interface RingBufferEntry {
  readonly frame: LiveSampleFrame;
  readonly sequenceNumber: number;
  /** Wall-clock timestamp when the sample was pushed (ms since epoch). */
  readonly receivedAt: number;
}

interface ChannelRingBuffer {
  readonly channelId: LiveChannelDescriptor;
  readonly maxSamples: number;
  readonly entries: RingBufferEntry[];
  /** Monotonically increasing sequence number counter. */
  nextSequenceNumber: number;
}

function createChannelRingBuffer(channelId: LiveChannelDescriptor, maxSamples: number): ChannelRingBuffer {
  return {
    channelId,
    maxSamples,
    entries: [],
    nextSequenceNumber: 0,
  };
}

function pushToRingBuffer(buffer: ChannelRingBuffer, frame: LiveSampleFrame): LiveSample {
  const sequenceNumber = buffer.nextSequenceNumber;
  buffer.nextSequenceNumber += 1;

  const entry: RingBufferEntry = {
    frame,
    sequenceNumber,
    receivedAt: Date.now(),
  };

  buffer.entries.push(entry);

  // Evict oldest entries if over capacity
  while (buffer.entries.length > buffer.maxSamples) {
    buffer.entries.shift();
  }

  return {
    channelId: buffer.channelId,
    frame,
    sequenceNumber,
  };
}

// ---------------------------------------------------------------------------
// Internal source record
// ---------------------------------------------------------------------------

interface InternalSource {
  id: string;
  kind: LiveSourceKind;
  status: LiveSourceStatus;
  label?: string;
  metadata?: Record<string, unknown>;
  permission?: LiveSourcePermission;
  recording?: LiveRecordingState;
  learnMode?: LiveLearnMode;
  /** Channels open on this source. */
  channels: Map<string, InternalChannel>;
  /** Diagnostics specific to this source. */
  diagnostics: LiveSourceDiagnostic[];
  /** Extension ID that registered this source. */
  extensionId?: string;
  /** ISO 8601 timestamp when source was registered. */
  registeredAt: string;
  /** ISO 8601 timestamp when source was disposed (if disposed). */
  disposedAt?: string;
}

interface InternalChannel {
  channelId: LiveChannelDescriptor;
  kind: LiveChannelKind;
  sourceId: string;
  label?: string;
  metadata?: Record<string, unknown>;
  ringBuffer: ChannelRingBuffer;
  listeners: Set<(sample: LiveSample) => void>;
}

// ---------------------------------------------------------------------------
// Internal tombstone (preserved after source disposal)
// ---------------------------------------------------------------------------

interface SourceTombstone {
  readonly id: string;
  readonly kind: LiveSourceKind;
  readonly status: 'disposed' | 'orphaned';
  readonly label?: string;
  readonly disposedAt: string;
  readonly extensionId?: string;
}

// ---------------------------------------------------------------------------
// Internal binding record
// ---------------------------------------------------------------------------

interface InternalBinding {
  bindingId: string;
  sourceId: string;
  channelId?: LiveChannelDescriptor;
  targetClipId?: string;
  targetEffectId?: string;
  targetParamName?: string;
  status: BindingResolutionStatus;
  diagnostic?: LiveSourceDiagnostic;
}

// ---------------------------------------------------------------------------
// Registry implementation
// ---------------------------------------------------------------------------

export interface LiveDataRegistry extends LiveSessionsService {
  // ---- Extended diagnostics and lifecycle ----

  /** Emit a diagnostic scoped to a specific source. */
  emitDiagnostic(sourceId: string, diagnostic: LiveSourceDiagnostic): void;

  /** Clear diagnostics for a specific source. */
  clearSourceDiagnostics(sourceId: string): void;

  /** Transition a source to a new status. */
  transitionSource(sourceId: string, status: LiveSourceStatus, reason?: string): void;

  /** Check if the registry has been disposed. */
  readonly isDisposed: boolean;

  /** Subscribe to all registry changes. */
  subscribe(listener: () => void): DisposeHandle;

  /** Get a frozen snapshot of the registry state (useful for synchronous reads in render). */
  getSnapshot(): LiveDataRegistrySnapshot;

  /** Register a source with an owning extension ID for lifecycle binding. */
  registerSourceWithOwner(
    source: Omit<LiveSource, 'status' | 'diagnostics'>,
    extensionId: string,
  ): DisposeHandle;

  /** Orphan-dispose all sources registered by an extension. */
  disposeExtensionSources(extensionId: string): void;

  /** Get all sources registered by an extension (for diagnostics). */
  getSourcesByExtension(extensionId: string): readonly LiveSource[];

  /** Get the latest applied steering decision for a generation session. */
  getSteeringDecision(sessionId: string): SteeringDecision | undefined;

  /** Get the latest applied steering lineage for a generation session. */
  getSteeringLineage(sessionId: string): SteeringLineage | undefined;

  /** Check whether Step 15 live sample delivery may activate for a session. */
  canActivateGenerationSessionLiveDelivery(sessionId: string): boolean;

  /** Read the latest sample from a channel's ring buffer synchronously. */
  getLatestSample(channelId: LiveChannelDescriptor): LiveSample | undefined;

  /** Read a sample by sequence number synchronously. */
  getSampleAt(channelId: LiveChannelDescriptor, sequenceNumber: number): LiveSample | undefined;

  /** Read all retained samples from a channel's ring buffer synchronously. */
  getSamples(channelId: LiveChannelDescriptor): readonly LiveSample[];

  /** Count retained samples in a channel's ring buffer synchronously. */
  getSampleCount(channelId: LiveChannelDescriptor): number;
}

/** Frozen snapshot for synchronous reads in render paths. */
export interface LiveDataRegistrySnapshot {
  readonly sources: readonly LiveSource[];
  readonly channels: readonly LiveChannelMetadata[];
  readonly tombstones: readonly SourceTombstone[];
  readonly bindings: readonly LiveBinding[];
  readonly disposed: boolean;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createLiveDataRegistry(config: LiveDataRegistryConfig = {}): LiveDataRegistry {
  const maxSamplesPerChannel = config.maxSamplesPerChannel ?? DEFAULT_MAX_SAMPLES_PER_CHANNEL;
  const emitLifecycleDiagnostics = config.emitLifecycleDiagnostics ?? true;

  // sourceId → InternalSource
  const sources = new Map<string, InternalSource>();

  // channelId → InternalChannel (for fast lookup)
  const channels = new Map<string, InternalChannel>();

  // sourceId → SourceTombstone (preserved after disposal)
  const tombstones = new Map<string, SourceTombstone>();

  // bindingId → InternalBinding
  const bindings = new Map<string, InternalBinding>();

  // sessionId → latest validated steering decision
  const steeringDecisions = new Map<string, SteeringDecision>();

  // Registry-level diagnostics
  const registryDiagnostics: LiveSourceDiagnostic[] = [];

  const listeners = new Set<() => void>();
  let disposed = false;
  let frozenSnapshot: LiveDataRegistrySnapshot | null = null;

  // ---- Helpers -----------------------------------------------------------

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function notifyListeners(): void {
    for (const listener of listeners) {
      listener();
    }
  }

  function guardDisposed(operation: string): boolean {
    if (disposed) {
      registryDiagnostics.push({
        severity: 'warning',
        code: 'live/registry-disposed',
        message: `LiveDataRegistry operation "${operation}" called after dispose.`,
        detail: { operation },
      });
      return true;
    }
    return false;
  }

  function addSourceDiagnostic(
    sourceId: string,
    severity: DiagnosticSeverity,
    code: string,
    message: string,
    detail?: Record<string, unknown>,
  ): void {
    const source = sources.get(sourceId);
    if (!source) return;
    source.diagnostics.push({
      severity,
      code,
      message,
      sourceId,
      detail,
    });
    invalidateSnapshot();
    notifyListeners();
  }

  function clearSourceDiags(sourceId: string): void {
    const source = sources.get(sourceId);
    if (!source) return;
    if (source.diagnostics.length > 0) {
      source.diagnostics = [];
      invalidateSnapshot();
      notifyListeners();
    }
  }

  function toLiveSource(source: InternalSource): LiveSource {
    return {
      id: source.id,
      kind: source.kind,
      status: source.status,
      label: source.label,
      diagnostics: Object.freeze([...source.diagnostics]) as readonly LiveSourceDiagnostic[],
      metadata: source.metadata ? Object.freeze({ ...source.metadata }) : undefined,
      permission: source.permission ? Object.freeze({ ...source.permission }) : undefined,
      recording: source.recording ? Object.freeze({ ...source.recording }) : undefined,
      learnMode: source.learnMode,
    };
  }

  function toLiveChannelMetadata(channel: InternalChannel): LiveChannelMetadata {
    return {
      channelId: channel.channelId,
      kind: channel.kind,
      sourceId: channel.sourceId,
      label: channel.label,
      metadata: channel.metadata ? Object.freeze({ ...channel.metadata }) : undefined,
    };
  }

  function toLiveSample(entry: RingBufferEntry, channelId: LiveChannelDescriptor): LiveSample {
    return {
      channelId,
      frame: entry.frame,
      sequenceNumber: entry.sequenceNumber,
    };
  }

  function resolveBindingStatus(sourceId: string): BindingResolutionStatus {
    // Check for tombstone (disposed or orphaned source)
    const tombstone = tombstones.get(sourceId);
    if (tombstone) return tombstone.status;

    const source = sources.get(sourceId);
    if (!source) return 'missing';

    if (source.status === 'orphaned') return 'orphaned';
    if (source.status === 'disposed') return 'disposed';
    if (source.status === 'inactive' || source.status === 'activating') return 'unresolved';
    if (source.status === 'error') return 'unresolved';
    if (source.status === 'active') return 'resolved';

    return 'unresolved';
  }

  // ---- Source lifecycle --------------------------------------------------

  function registerSource(
    sourceInput: Omit<LiveSource, 'status' | 'diagnostics'>,
  ): DisposeHandle {
    if (guardDisposed('registerSource')) {
      return { dispose() {} };
    }

    // Check for duplicate ID
    if (sources.has(sourceInput.id) || tombstones.has(sourceInput.id)) {
      registryDiagnostics.push({
        severity: 'warning',
        code: 'live/duplicate-source',
        message: `Source "${sourceInput.id}" is already registered or disposed.`,
        sourceId: sourceInput.id,
      });
      return { dispose() {} };
    }

    const source: InternalSource = {
      id: sourceInput.id,
      kind: sourceInput.kind,
      status: 'inactive',
      label: sourceInput.label,
      metadata: sourceInput.metadata ? { ...sourceInput.metadata } : undefined,
      channels: new Map(),
      diagnostics: [],
      registeredAt: new Date().toISOString(),
    };

    if (sourceInput.permission) {
      source.permission = { ...sourceInput.permission };
    }
    if (sourceInput.recording) {
      source.recording = { ...sourceInput.recording };
    }
    if (sourceInput.learnMode) {
      source.learnMode = sourceInput.learnMode;
    }

    sources.set(source.id, source);

    if (emitLifecycleDiagnostics) {
      addSourceDiagnostic(source.id, 'info', 'live/source-registered', `Source "${source.id}" registered.`);
    }

    invalidateSnapshot();
    notifyListeners();

    let unregistered = false;

    return {
      dispose(): void {
        if (unregistered) return;
        unregistered = true;
        disposeSource(source.id);
      },
    };
  }

  function getSource(sourceId: string): LiveSource | undefined {
    if (disposed) return undefined;
    const source = sources.get(sourceId);
    if (!source) return undefined;
    return toLiveSource(source);
  }

  function listSources(): readonly LiveSource[] {
    if (disposed) return Object.freeze([]);
    return Object.freeze(Array.from(sources.values()).map(toLiveSource));
  }

  function disposeSource(sourceId: string, orphaned = false): void {
    const source = sources.get(sourceId);
    if (!source) return;

    // Close all channels and notify listeners
    for (const channel of source.channels.values()) {
      channels.delete(channel.channelId);
      // Notify listeners with a special "channel closed" sample
      for (const listener of channel.listeners) {
        try {
          listener({
            channelId: channel.channelId,
            frame: { timestamp: -1, data: new Uint8Array(), format: 'raw' },
            sequenceNumber: -1,
          });
        } catch {
          // Swallow listener errors during teardown
        }
      }
      channel.listeners.clear();
    }

    // Create tombstone
    const tombstone: SourceTombstone = {
      id: source.id,
      kind: source.kind,
      status: orphaned ? 'orphaned' : 'disposed',
      label: source.label,
      disposedAt: new Date().toISOString(),
      extensionId: source.extensionId,
    };
    tombstones.set(source.id, tombstone);

    // Remove from sources
    sources.delete(source.id);

    if (emitLifecycleDiagnostics) {
      const code = orphaned ? 'live/source-orphaned' : 'live/source-disposed';
      const message = orphaned
        ? `Source "${sourceId}" orphaned (owner disposed).`
        : `Source "${sourceId}" disposed.`;
      registryDiagnostics.push({
        severity: 'info',
        code,
        message,
        sourceId,
      });
    }

    // Update bindings that reference this source
    for (const binding of bindings.values()) {
      if (binding.sourceId === sourceId) {
        binding.status = orphaned ? 'orphaned' : 'disposed';
        binding.diagnostic = {
          severity: 'warning',
          code: orphaned ? 'live/orphaned-source' : 'live/disposed-source',
          message: orphaned
            ? `Source "${sourceId}" was orphaned — its owning extension was disposed.`
            : `Source "${sourceId}" was explicitly disposed.`,
          sourceId,
        };
      }
    }

    invalidateSnapshot();
    notifyListeners();
  }

  // ---- Channel operations -------------------------------------------------

  function openChannel(
    sourceId: string,
    kind: LiveChannelKind,
    metadata?: Record<string, unknown>,
  ): LiveChannelDescriptor {
    if (guardDisposed('openChannel')) {
      return 'dead-channel' as LiveChannelDescriptor;
    }

    const source = sources.get(sourceId);
    if (!source) {
      registryDiagnostics.push({
        severity: 'error',
        code: 'live/source-not-found',
        message: `Cannot open channel — source "${sourceId}" not found.`,
        sourceId,
      });
      return 'dead-channel' as LiveChannelDescriptor;
    }

    // Generate a unique channel ID
    const channelId = `${sourceId}:ch-${source.channels.size + 1}` as LiveChannelDescriptor;

    const channel: InternalChannel = {
      channelId,
      kind,
      sourceId,
      metadata: metadata ? { ...metadata } : undefined,
      ringBuffer: createChannelRingBuffer(channelId, maxSamplesPerChannel),
      listeners: new Set(),
    };

    source.channels.set(channelId, channel);
    channels.set(channelId, channel);

    if (emitLifecycleDiagnostics) {
      addSourceDiagnostic(sourceId, 'info', 'live/channel-opened', `Channel "${channelId}" (${kind}) opened on source "${sourceId}".`);
    }

    invalidateSnapshot();
    notifyListeners();

    return channelId;
  }

  function closeChannel(channelId: LiveChannelDescriptor): void {
    if (guardDisposed('closeChannel')) return;

    const channel = channels.get(channelId);
    if (!channel) return; // Idempotent

    const source = sources.get(channel.sourceId);
    if (source) {
      source.channels.delete(channelId);
    }

    channels.delete(channelId);

    // Notify listeners
    for (const listener of channel.listeners) {
      try {
        listener({
          channelId: channel.channelId,
          frame: { timestamp: -1, data: new Uint8Array(), format: 'raw' },
          sequenceNumber: -1,
        });
      } catch {
        // Swallow errors
      }
    }
    channel.listeners.clear();

    invalidateSnapshot();
    notifyListeners();
  }

  function getChannelMetadata(channelId: LiveChannelDescriptor): LiveChannelMetadata | undefined {
    if (disposed) return undefined;
    const channel = channels.get(channelId);
    if (!channel) return undefined;
    return toLiveChannelMetadata(channel);
  }

  // ---- Sample delivery ----------------------------------------------------

  function pushSample(channelId: LiveChannelDescriptor, frame: LiveSampleFrame): void {
    if (guardDisposed('pushSample')) return;

    const channel = channels.get(channelId);
    if (!channel) {
      registryDiagnostics.push({
        severity: 'warning',
        code: 'live/channel-not-found',
        message: `Cannot push sample — channel "${channelId}" not found.`,
        channelId,
      });
      return;
    }

    const source = sources.get(channel.sourceId);
    if (source && source.status !== 'active') {
      // Auto-activate if pushing samples
      source.status = 'active';
      if (emitLifecycleDiagnostics) {
        addSourceDiagnostic(source.id, 'info', 'live/source-activated', `Source "${source.id}" auto-activated by sample push.`);
      }
    }

    const sample = pushToRingBuffer(channel.ringBuffer, frame);

    // Notify listeners synchronously
    for (const listener of channel.listeners) {
      try {
        listener(sample);
      } catch {
        // Swallow listener errors
      }
    }

    invalidateSnapshot();
    notifyListeners();
  }

  function subscribeSamples(
    channelId: LiveChannelDescriptor,
    listener: (sample: LiveSample) => void,
  ): DisposeHandle {
    if (guardDisposed('subscribeSamples')) {
      return { dispose() {} };
    }

    const channel = channels.get(channelId);
    if (!channel) {
      registryDiagnostics.push({
        severity: 'warning',
        code: 'live/channel-not-found',
        message: `Cannot subscribe — channel "${channelId}" not found.`,
        channelId,
      });
      return { dispose() {} };
    }

    channel.listeners.add(listener);

    let unsubscribed = false;

    return {
      dispose(): void {
        if (unsubscribed) return;
        unsubscribed = true;
        channel.listeners.delete(listener);
      },
    };
  }

  // ---- Synchronous read facades ------------------------------------------

  /** Read the latest sample from a channel's ring buffer (synchronous, non-blocking). */
  function getLatestSample(channelId: LiveChannelDescriptor): LiveSample | undefined {
    const channel = channels.get(channelId);
    if (!channel || channel.ringBuffer.entries.length === 0) return undefined;
    const entry = channel.ringBuffer.entries[channel.ringBuffer.entries.length - 1];
    return toLiveSample(entry, channelId);
  }

  /** Read a sample at a specific sequence index (synchronous). */
  function getSampleAt(channelId: LiveChannelDescriptor, sequenceNumber: number): LiveSample | undefined {
    const channel = channels.get(channelId);
    if (!channel) return undefined;
    const entry = channel.ringBuffer.entries.find((e) => e.sequenceNumber === sequenceNumber);
    if (!entry) return undefined;
    return toLiveSample(entry, channelId);
  }

  /** Get all samples currently in a channel's ring buffer (synchronous). */
  function getSamples(channelId: LiveChannelDescriptor): readonly LiveSample[] {
    const channel = channels.get(channelId);
    if (!channel) return Object.freeze([]);
    return Object.freeze(
      channel.ringBuffer.entries.map((e) => toLiveSample(e, channelId)),
    );
  }

  /** Get the number of samples in a channel's ring buffer. */
  function getSampleCount(channelId: LiveChannelDescriptor): number {
    const channel = channels.get(channelId);
    if (!channel) return 0;
    return channel.ringBuffer.entries.length;
  }

  // ---- Source status transitions ------------------------------------------

  function transitionSource(sourceId: string, status: LiveSourceStatus, reason?: string): void {
    if (guardDisposed('transitionSource')) return;

    const source = sources.get(sourceId);
    if (!source) {
      registryDiagnostics.push({
        severity: 'warning',
        code: 'live/source-not-found',
        message: `Cannot transition — source "${sourceId}" not found.`,
        sourceId,
      });
      return;
    }

    const oldStatus = source.status;
    source.status = status;

    if (emitLifecycleDiagnostics) {
      addSourceDiagnostic(
        sourceId,
        status === 'error' ? 'error' : 'info',
        'live/source-transition',
        `Source "${sourceId}" transitioned ${oldStatus} → ${status}${reason ? `: ${reason}` : ''}.`,
        { oldStatus, newStatus: status, reason },
      );
    }

    // If transitioning to error, clear any channel listeners
    if (status === 'error' || status === 'disposed' || status === 'orphaned') {
      if (status === 'disposed' || status === 'orphaned') {
        disposeSource(sourceId, status === 'orphaned');
        return;
      }
    }

    invalidateSnapshot();
    notifyListeners();
  }

  // ---- Diagnostics --------------------------------------------------------

  function emitDiagnostic(sourceId: string, diagnostic: LiveSourceDiagnostic): void {
    if (guardDisposed('emitDiagnostic')) return;

    const source = sources.get(sourceId);
    if (!source) {
      registryDiagnostics.push({
        ...diagnostic,
        sourceId,
      });
      return;
    }

    source.diagnostics.push({ ...diagnostic, sourceId });
    invalidateSnapshot();
    notifyListeners();
  }

  function clearSourceDiagnostics(sourceId: string): void {
    if (guardDisposed('clearSourceDiagnostics')) return;
    clearSourceDiags(sourceId);
  }

  function getDiagnostics(sourceId?: string): readonly LiveSourceDiagnostic[] {
    if (sourceId) {
      const source = sources.get(sourceId);
      if (!source) return Object.freeze([]);
      return Object.freeze([...source.diagnostics]);
    }

    // All diagnostics: source-level + registry-level
    const all: LiveSourceDiagnostic[] = [...registryDiagnostics];
    for (const source of sources.values()) {
      all.push(...source.diagnostics);
    }
    return Object.freeze(all);
  }

  // ---- Bake ---------------------------------------------------------------

  function bake(selection: LiveBakeSelection): LiveBakeResult {
    if (guardDisposed('bake')) {
      return {
        sourceId: selection.sourceId,
        targets: [],
        diagnostics: [{ severity: 'error', code: 'live/registry-disposed', message: 'Registry is disposed.' }],
        success: false,
      };
    }

    const source = sources.get(selection.sourceId);
    if (!source) {
      return {
        sourceId: selection.sourceId,
        targets: [],
        diagnostics: [{
          severity: 'error',
          code: 'live/source-not-found',
          message: `Source "${selection.sourceId}" not found.`,
          sourceId: selection.sourceId,
        }],
        success: false,
      };
    }

    const selectedChannelIds = new Set(selection.channelIds ?? []);
    const selectedChannels = Array.from(source.channels.values())
      .filter((channel) => selectedChannelIds.size === 0 || selectedChannelIds.has(channel.channelId));
    const missingChannelDiagnostics = Array.from(selectedChannelIds)
      .filter((channelId) => !source.channels.has(channelId))
      .map<LiveSourceDiagnostic>((channelId) => ({
        severity: 'error',
        code: 'live/channel-not-found',
        message: `Cannot bake channel "${channelId}" — channel not found on source "${selection.sourceId}".`,
        sourceId: selection.sourceId,
        channelId,
      }));

    if (missingChannelDiagnostics.length > 0) {
      registryDiagnostics.push(...missingChannelDiagnostics);
      invalidateSnapshot();
      notifyListeners();
      return {
        sourceId: selection.sourceId,
        targets: selection.targets.map((target) => ({ target, outputRef: '', diagnostics: missingChannelDiagnostics })),
        diagnostics: missingChannelDiagnostics,
        success: false,
      };
    }

    const result = bakeLiveSource({
      selection,
      source: toLiveSource(source),
      channels: selectedChannels.map((channel) => ({
        metadata: toLiveChannelMetadata(channel),
        samples: getSamples(channel.channelId),
      })),
      bindingIds: Array.from(bindings.values())
        .filter((binding) => binding.sourceId === selection.sourceId
          && (!binding.channelId || selectedChannelIds.size === 0 || selectedChannelIds.has(binding.channelId)))
        .map((binding) => binding.bindingId),
    });

    if (!result.success && result.diagnostics.length > 0) {
      registryDiagnostics.push(...result.diagnostics);
      invalidateSnapshot();
      notifyListeners();
    }

    return result;
  }

  function removeLiveBindings(sourceId: string): void {
    if (guardDisposed('removeLiveBindings')) return;

    for (const [bindingId, binding] of bindings) {
      if (binding.sourceId === sourceId) {
        bindings.delete(bindingId);
      }
    }

    invalidateSnapshot();
    notifyListeners();
  }

  // ---- Binding resolution -------------------------------------------------

  function resolveBinding(bindingId: string): LiveBindingResolution {
    const binding = bindings.get(bindingId);

    if (!binding) {
      return {
        bindingId,
        status: 'missing',
        diagnostic: {
          severity: 'warning',
          code: 'live/binding-not-found',
          message: `Binding "${bindingId}" not found.`,
        },
      };
    }

    const status = resolveBindingStatus(binding.sourceId);
    binding.status = status;

    const source = sources.get(binding.sourceId);
    const channel = binding.channelId ? channels.get(binding.channelId) : undefined;

    return {
      bindingId: binding.bindingId,
      status,
      source: source ? toLiveSource(source) : undefined,
      channel: channel ? toLiveChannelMetadata(channel) : undefined,
      diagnostic: binding.diagnostic,
    };
  }

  function getBindingMetadata(): LiveBindingMetadata {
    const allBindings: LiveBinding[] = [];
    let unresolvedCount = 0;
    let orphanedCount = 0;
    let disposedCount = 0;

    for (const binding of bindings.values()) {
      const status = resolveBindingStatus(binding.sourceId);
      binding.status = status;

      allBindings.push({
        bindingId: binding.bindingId,
        sourceId: binding.sourceId,
        channelId: binding.channelId,
        targetClipId: binding.targetClipId,
        targetEffectId: binding.targetEffectId,
        targetParamName: binding.targetParamName,
        status,
        diagnostic: binding.diagnostic,
      });

      if (status !== 'resolved') unresolvedCount += 1;
      if (status === 'orphaned') orphanedCount += 1;
      if (status === 'disposed') disposedCount += 1;
    }

    return {
      bindings: Object.freeze(allBindings),
      unresolvedCount,
      orphanedCount,
      disposedCount,
    };
  }

  // ---- Steering -----------------------------------------------------------

  function applySteeringDecision(decision: SteeringDecision): void {
    if (guardDisposed('applySteeringDecision')) return;

    const validationDiagnostics = validateSteeringDecision(decision);
    if (validationDiagnostics.some((diagnostic) => diagnostic.severity === 'error')) {
      registryDiagnostics.push(...validationDiagnostics);
    } else {
      steeringDecisions.set(decision.sessionId, decision);
      const gate = evaluateGenerationSessionLiveDeliveryGate(decision);
      registryDiagnostics.push({
        severity: 'info',
        code: 'live/steering-applied',
        message: `Steering decision "${decision.kind}" for session "${decision.sessionId}" applied.`,
        detail: {
          kind: decision.kind,
          sessionId: decision.sessionId,
          generationIndex: decision.lineage.generationIndex,
          steerHash: decision.lineage.steerHash,
          parentRefs: decision.lineage.parentRefs,
          producerVersion: decision.lineage.producerVersion,
          provenance: decision.lineage.provenance,
          canActivateLiveDelivery: gate.canActivate,
        },
      });
    }

    invalidateSnapshot();
    notifyListeners();
  }

  function getSteeringDecision(sessionId: string): SteeringDecision | undefined {
    return steeringDecisions.get(sessionId);
  }

  function getSteeringLineage(sessionId: string): SteeringLineage | undefined {
    return steeringDecisions.get(sessionId)?.lineage;
  }

  function canActivateGenerationSessionLiveDelivery(sessionId: string): boolean {
    return evaluateGenerationSessionLiveDeliveryGate(steeringDecisions.get(sessionId)).canActivate;
  }

  // ---- Subscriptions & snapshots ------------------------------------------

  function subscribe(listener: () => void): DisposeHandle {
    if (disposed) {
      return { dispose() {} };
    }

    listeners.add(listener);

    let unsubscribed = false;

    return {
      dispose(): void {
        if (unsubscribed) return;
        unsubscribed = true;
        listeners.delete(listener);
      },
    };
  }

  function buildSnapshot(): LiveDataRegistrySnapshot {
    return {
      sources: Object.freeze(Array.from(sources.values()).map(toLiveSource)),
      channels: Object.freeze(Array.from(channels.values()).map(toLiveChannelMetadata)),
      tombstones: Object.freeze(Array.from(tombstones.values())),
      bindings: Object.freeze(
        Array.from(bindings.values()).map((b) => {
          const status = resolveBindingStatus(b.sourceId);
          return {
            bindingId: b.bindingId,
            sourceId: b.sourceId,
            channelId: b.channelId,
            targetClipId: b.targetClipId,
            targetEffectId: b.targetEffectId,
            targetParamName: b.targetParamName,
            status,
            diagnostic: b.diagnostic,
          };
        }),
      ),
      disposed,
    };
  }

  function getSnapshot(): LiveDataRegistrySnapshot {
    if (!frozenSnapshot) {
      frozenSnapshot = buildSnapshot();
    }
    return frozenSnapshot;
  }

  // ---- Dispose ------------------------------------------------------------

  function registryDispose(): void {
    if (disposed) return;
    disposed = true;

    // Dispose all sources
    for (const sourceId of Array.from(sources.keys())) {
      disposeSource(sourceId);
    }

    // Clear channels
    for (const channel of channels.values()) {
      channel.listeners.clear();
    }
    channels.clear();

    // Clear bindings
    bindings.clear();

    // Clear steering session metadata
    steeringDecisions.clear();

    // Notify listeners one last time
    notifyListeners();

    // Clear listeners
    listeners.clear();

    invalidateSnapshot();
  }

  // ---- Extension-scoped source registration --------------------------------

  function registerSourceWithOwner(
    sourceInput: Omit<LiveSource, 'status' | 'diagnostics'>,
    extensionId: string,
  ): DisposeHandle {
    const handle = registerSource(sourceInput);
    const source = sources.get(sourceInput.id);
    if (source) {
      source.extensionId = extensionId;
    }
    return handle;
  }

  function disposeExtensionSources(extensionId: string): void {
    for (const [sourceId, source] of sources) {
      if (source.extensionId === extensionId) {
        disposeSource(sourceId, /* orphaned */ true);
      }
    }
  }

  function getSourcesByExtension(extensionId: string): readonly LiveSource[] {
    const result: LiveSource[] = [];
    for (const source of sources.values()) {
      if (source.extensionId === extensionId) {
        result.push(toLiveSource(source));
      }
    }
    return Object.freeze(result);
  }

  // ---- Internal binding management (for use by scanner in T5) --------------

  function _addBinding(binding: InternalBinding): void {
    bindings.set(binding.bindingId, binding);
    invalidateSnapshot();
    notifyListeners();
  }

  function _removeBinding(bindingId: string): boolean {
    const result = bindings.delete(bindingId);
    if (result) {
      invalidateSnapshot();
      notifyListeners();
    }
    return result;
  }

  function _getBinding(bindingId: string): InternalBinding | undefined {
    return bindings.get(bindingId);
  }

  // ---- Return the registry ------------------------------------------------

  const registry: LiveDataRegistry = {
    // LiveSessionsService methods
    registerSource,
    getSource,
    listSources,
    openChannel,
    closeChannel,
    getChannelMetadata,
    pushSample,
    subscribeSamples,
    bake,
    removeLiveBindings,
    resolveBinding,
    getBindingMetadata,
    applySteeringDecision,
    getDiagnostics,

    // Extended methods
    emitDiagnostic,
    clearSourceDiagnostics,
    transitionSource,
    get isDisposed() {
      return disposed;
    },
    subscribe,
    getSnapshot,

    // Extended lifecycle methods
    registerSourceWithOwner,
    disposeExtensionSources,
    getSourcesByExtension,
    getSteeringDecision,
    getSteeringLineage,
    canActivateGenerationSessionLiveDelivery,

    // Internal methods exposed for testing/binding scanner
    _addBinding,
    _removeBinding,
    _getBinding,

    // Synchronous read facades
    getLatestSample,
    getSampleAt,
    getSamples,
    getSampleCount,

    // Full dispose
    dispose: registryDispose,
  };

  return registry;
}

// Re-export the synchronous read facades as standalone functions for use
// in render paths where the full registry object is available but we want
// to be explicit about synchronous-only access.

export type { SourceTombstone };
