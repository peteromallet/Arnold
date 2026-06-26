/**
 * Live Data Bridge — independent video SDK infrastructure.
 *
 * Source, channel, sample, permission, binding, diagnostics, recording,
 * learning, steering, and binding-resolution contracts for live data
 * sessions. These are infrastructure contracts, NOT a contribution
 * family. Do not add them to VIDEO_CONTRIBUTION_KINDS or the family
 * registry.
 *
 * All live data is ephemeral runtime state scoped to the current
 * provider mount. Only live binding metadata persists in timeline config.
 *
 * @publicContract
 */

import type { DiagnosticSeverity } from '../diagnostics';
import type { DisposeHandle } from '../dispose';

// ---------------------------------------------------------------------------
// Live source identity and lifecycle
// ---------------------------------------------------------------------------

/**
 * Kind of a live data source.
 *
 * - `webcam` — browser camera (getUserMedia)
 * - `microphone` — browser microphone (getUserMedia)
 * - `midi` — Web MIDI API device
 * - `serial` — Web Serial API port
 * - `bluetooth` — Web Bluetooth API device
 * - `generated` — procedurally generated frames/data (generative AI, procedural, etc.)
 * - `screen-capture` — getDisplayMedia / screen sharing
 * - `audio-device` — non-microphone audio output capture
 * - `osc` — OSC (Open Sound Control) over UDP/WebSocket
 * - `custom` — extension-defined custom source
 */
export type LiveSourceKind =
  | 'webcam'
  | 'microphone'
  | 'midi'
  | 'serial'
  | 'bluetooth'
  | 'generated'
  | 'screen-capture'
  | 'audio-device'
  | 'osc'
  | 'custom';

/**
 * Lifecycle status of a live data source.
 *
 *   inactive   → source registered, not yet active
 *   activating → permission requested, stream opening
 *   active     → source is streaming live data
 *   error      → source encountered a blocking error
 *   disposed   → source explicitly disposed by provider
 *   orphaned   → source's owning extension was unmounted/disposed
 */
export type LiveSourceStatus =
  | 'inactive'
  | 'activating'
  | 'active'
  | 'error'
  | 'disposed'
  | 'orphaned';

/**
 * A diagnostic produced by a live source or live data operation.
 */
export interface LiveSourceDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code (e.g. 'live/permission-denied'). */
  code: string;
  message: string;
  sourceId?: string;
  channelId?: LiveChannelDescriptor;
  detail?: Record<string, unknown>;
}

/**
 * A provider-scoped live data source.
 *
 * Live sources are ephemeral runtime objects scoped to a single
 * provider mount. They are never persisted in timeline config/history.
 * Only live binding metadata is persisted on timeline objects.
 */
export interface LiveSource {
  /** Unique source identifier (provider-scoped). */
  readonly id: string;
  /** The kind of data this source produces. */
  readonly kind: LiveSourceKind;
  /** Current lifecycle status. */
  readonly status: LiveSourceStatus;
  /** Human-readable label. */
  readonly label?: string;
  /** Current active diagnostics. */
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  /** Opaque source metadata. */
  readonly metadata?: Record<string, unknown>;
  /** Permission state for this source. */
  readonly permission?: LiveSourcePermission;
  /** Recording state, if recording is active. */
  readonly recording?: LiveRecordingState;
  /** Learn-mode state, if learn is active. */
  readonly learnMode?: LiveLearnMode;
}

// --- Live channel descriptors ---

/**
 * Kind of data carried by a live channel.
 */
export type LiveChannelKind =
  | 'video'
  | 'audio'
  | 'midi'
  | 'osc'
  | 'data'
  | 'control';

/**
 * A typed channel descriptor that is string-compatible.
 *
 * LiveChannelDescriptor is a branded string — it can be used anywhere a
 * string is expected (e.g. as a map key, in string concatenation, etc.)
 * but carries a distinct type so the compiler can distinguish channel
 * identifiers from arbitrary strings.
 *
 * This preserves backward compatibility with M10 code that treated
 * getSampleChannel() as returning a plain string.
 */
export type LiveChannelDescriptor = string & { readonly __brand: 'LiveChannelDescriptor' };

/**
 * Rich metadata for a live channel.
 *
 * Obtainable via LiveSessionsService.getChannelMetadata().
 */
export interface LiveChannelMetadata {
  /** The channel descriptor (string-compatible identifier). */
  readonly channelId: LiveChannelDescriptor;
  /** The kind of data carried by this channel. */
  readonly kind: LiveChannelKind;
  /** The source this channel is attached to. */
  readonly sourceId: string;
  /** Human-readable label. */
  readonly label?: string;
  /** Opaque channel metadata. */
  readonly metadata?: Record<string, unknown>;
}

// --- Live samples ---

/**
 * Format of a live sample frame's data payload.
 */
export type LiveSampleFormat = 'raw' | 'encoded' | 'json' | 'binary';

/**
 * A single frame/tick of live data.
 *
 * Carries timestamped data in one of several formats. The host
 * must read samples synchronously in render paths.
 */
export interface LiveSampleFrame {
  /** Monotonic timestamp (milliseconds since source start). */
  readonly timestamp: number;
  /** The sample data payload. */
  readonly data: ArrayBuffer | Uint8Array | Record<string, unknown>;
  /** Format of the data payload. */
  readonly format: LiveSampleFormat;
  /** Opaque frame metadata. */
  readonly metadata?: Record<string, unknown>;
}

/**
 * A delivered live sample on a channel.
 */
export interface LiveSample {
  /** The channel this sample arrived on. */
  readonly channelId: LiveChannelDescriptor;
  /** The sample frame data. */
  readonly frame: LiveSampleFrame;
  /** Monotonically increasing sequence number for this channel. */
  readonly sequenceNumber: number;
}

// --- Live permissions ---

/**
 * Permission state for a live source.
 *
 *   prompt      — browser permission prompt not yet shown/answered
 *   granted     — permission granted, stream can open
 *   denied      — permission denied by user or system
 *   unavailable — API not available in this browser/environment
 */
export type LivePermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

/**
 * Permission metadata for a live source.
 */
export interface LiveSourcePermission {
  /** Current permission state. */
  readonly state: LivePermissionState;
  /** Human-readable reason the permission is requested. */
  readonly reason?: string;
  /** User-facing device label. */
  readonly deviceLabel?: string;
  /** ISO 8601 timestamp when permission was requested. */
  readonly requestedAt?: string;
}

// --- Live recording ---

/**
 * Recording mode for a live source.
 *
 *   stream  — continuous recording into ring buffer
 *   take    — discrete take-based recording
 *   loop    — looping buffer (overwrites oldest data)
 *   trigger — triggered capture on external signal
 */
export type LiveRecordingMode = 'stream' | 'take' | 'loop' | 'trigger';

/**
 * Recording state for a live source.
 */
export interface LiveRecordingState {
  /** Whether recording is currently active. */
  readonly active: boolean;
  /** The recording mode in use. */
  readonly mode: LiveRecordingMode;
  /** ISO 8601 timestamp when recording started. */
  readonly startedAt?: string;
  /** Recording duration in milliseconds. */
  readonly duration?: number;
  /** Current take index (for 'take' mode). */
  readonly takeIndex?: number;
}

// --- Live learn mode ---

/**
 * Learn-mode state for a live source.
 *
 *   idle        — not currently learning
 *   mapping     — mapping physical controls to parameters
 *   calibrating — calibrating device range/response
 *   tracking    — actively tracking a learn target
 */
export type LiveLearnMode = 'idle' | 'mapping' | 'calibrating' | 'tracking';

// --- Live bake ---

/**
 * Kind of target that a live bake can produce.
 *
 *   asset           — asset registry entry (video/image/audio bytes)
 *   keyframe        — deterministic keyframe(s) on a clip parameter
 *   automation      — automation clip with baked curves
 *   clip            — standard timeline clip referencing baked asset
 *   sidecar         — metadata sidecar file (JSON, CSV, etc.)
 *   render-material — RenderMaterialRef in the deterministic material vocabulary
 */
export type LiveBakeTargetKind =
  | 'asset'
  | 'keyframe'
  | 'automation'
  | 'clip'
  | 'sidecar'
  | 'render-material';

/**
 * A single bake target descriptor.
 *
 * Specifies what kind of deterministic artifact a live sample stream
 * should be baked into and which reference to populate.
 */
export interface LiveBakeTarget {
  /** The kind of bake target. */
  readonly kind: LiveBakeTargetKind;
  /** Target reference (asset key, clip ID, param name, etc.). */
  readonly ref: string;
  /** Bake parameters (quantization, downsampling, format, etc.). */
  readonly params?: Record<string, unknown>;
}

/**
 * A partial bake selection — which source(s) and channel(s) to bake,
 * over what time/sample range, into which targets.
 */
export interface LiveBakeSelection {
  /** The source to bake from. */
  readonly sourceId: string;
  /** Specific channels to bake (all channels if omitted). */
  readonly channelIds?: readonly LiveChannelDescriptor[];
  /** Time range to bake (entire buffer if omitted). */
  readonly timeRange?: readonly [startMs: number, endMs: number];
  /** Frame range to bake (entire buffer if omitted). */
  readonly frameRange?: readonly [startFrame: number, endFrame: number];
  /** Sample index range to bake (entire buffer if omitted). */
  readonly sampleRange?: readonly [startIndex: number, endIndex: number];
  /** Discrete take ID to bake (all takes if omitted). */
  readonly takeId?: string;
  /** Targets to bake into. */
  readonly targets: readonly LiveBakeTarget[];
}

/**
 * Result of a live bake operation.
 */
export interface LiveBakeResult {
  /** The source that was baked. */
  readonly sourceId: string;
  /** Results for each bake target. */
  readonly targets: readonly {
    /** The bake target that was processed. */
    readonly target: LiveBakeTarget;
    /** The deterministic output reference (asset key, clip ID, etc.). */
    readonly outputRef: string;
    /** Diagnostics produced during this target's bake. */
    readonly diagnostics?: readonly LiveSourceDiagnostic[];
  }[];
  /** Overall bake diagnostics. */
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  /** Whether all targets baked successfully. */
  readonly success: boolean;
}

// --- Steering ---

/**
 * The kind of steering decision applied to a GenerationSession.
 *
 *   supersede — replace the current generation with new output
 *   fork      — create a parallel generation branch
 *   reject    — discard the generation and clean up
 */
export type SteeringDecisionKind = 'supersede' | 'fork' | 'reject';

/**
 * Whether a parameter can be changed on a live generation without starting a
 * separate branch.
 *
 *   hot     — compatible with in-place supersede when prior samples are replaced
 *   non-hot — requires a fork or explicit rejection
 */
export type SteeringParameterHotness = 'hot' | 'non-hot';

/**
 * Explicit policy for samples produced before a steering change.
 *
 * No GenerationSession live delivery may silently keep prior samples after a
 * steering change; the resolver must choose one of these policies.
 */
export type SteeringPriorSamplePolicy = 'replace' | 'fork' | 'retain' | 'discard';

/**
 * Structured provenance for a steered generation.
 */
export interface SteeringProvenance {
  /** Prompt text or prompt reference used by the producer. */
  readonly prompt: string;
  /** Model identifier used by the producer. */
  readonly model: string;
  /** Seed used by the producer. */
  readonly seed: string | number;
  /** Producer extension identifier, when available. */
  readonly producerExtensionId?: string;
  /** Additional opaque provenance tags. */
  readonly tags?: readonly string[];
}

/**
 * A requested steering parameter change.
 */
export interface SteeringParameterChange {
  /** Stable parameter path, for example `params.prompt` or `params.seed`. */
  readonly path: string;
  /** Value before steering, if known. */
  readonly previousValue?: unknown;
  /** Proposed value after steering. */
  readonly nextValue: unknown;
  /** Hotness classification for this parameter change. */
  readonly hotness?: SteeringParameterHotness;
}

/**
 * Lineage metadata for a steered generation.
 *
 * Carries enough provenance to trace the full steering chain:
 * generation index, steer hash, parent refs, producer version,
 * and optional provenance tags.
 */
export interface SteeringLineage {
  /** Monotonically increasing generation index. */
  readonly generationIndex: number;
  /** Hash of the steering decision that produced this generation. */
  readonly steerHash: string;
  /** Parent generation session IDs. */
  readonly parentRefs: readonly string[];
  /** Version of the producer extension at steering time. */
  readonly producerVersion: string;
  /** Structured prompt/model/seed provenance for this steering decision. */
  readonly provenance: SteeringProvenance;
  /** Opaque provenance tags. */
  readonly provenanceTags?: readonly string[];
}

/**
 * A steering decision applied to a GenerationSession.
 *
 * The steering resolver (Step 14) must always return an explicit
 * supersede, fork, or reject decision. GenerationSession live sample
 * delivery must not activate without complete steering lineage.
 */
export interface SteeringDecision {
  /** The kind of steering decision. */
  readonly kind: SteeringDecisionKind;
  /** The generation session this decision applies to. */
  readonly sessionId: string;
  /** Complete steering lineage. */
  readonly lineage: SteeringLineage;
  /** Human-readable reason for the decision. */
  readonly reason?: string;
  /** Replacement channel for supersede decisions. */
  readonly replacementChannelId?: LiveChannelDescriptor;
}

/**
 * Explicit live sample delivery metadata for a GenerationSession.
 *
 * Supplying this object asks the host to bridge preview samples from the
 * GenerationSession into provider-scoped live ring buffers. Activation is
 * gated by the Step 14 steering resolver: `steeringDecision` must be a complete
 * supersede or fork decision with lineage.
 */
export interface GenerationSessionLiveDelivery {
  /** Origin of this live session, e.g. an agent tool or SDK session helper. */
  readonly origin: string;
  /** Explicit steering decision from the live steering resolver. */
  readonly steeringDecision: SteeringDecision;
  /** Optional source ID; defaults to a host-generated generation-session source. */
  readonly sourceId?: string;
  /** Optional source label. */
  readonly sourceLabel?: string;
  /** Channel kind to open for delivered samples. */
  readonly channelKind?: LiveChannelKind;
  /** Channels already known to be active for this session. */
  readonly activeChannels?: readonly LiveChannelDescriptor[];
  /** Deterministic final output refs, when known before completion. */
  readonly finalRefs?: readonly string[];
  /** Deterministic baked output refs, when known before completion. */
  readonly bakedRefs?: readonly string[];
  /** Opaque activation metadata. */
  readonly metadata?: Record<string, unknown>;
}

// --- Binding resolution ---

/**
 * Resolution status of a live binding.
 *
 *   resolved   — source is active and binding is fully resolved
 *   unresolved — binding exists but source is not yet active
 *   orphaned   — binding's owning extension was disposed
 *   disposed   — binding's source was explicitly disposed
 *   missing    — binding references a source that was never registered
 */
export type BindingResolutionStatus =
  | 'resolved'
  | 'unresolved'
  | 'orphaned'
  | 'disposed'
  | 'missing';

/**
 * A persisted live binding on a timeline object (clip or effect).
 *
 * Live binding metadata is the only live state that persists in
 * timeline config. It survives provider unmount/disposal. Unresolved
 * metadata (including orphaned and disposed sources) blocks export
 * until explicit bake or remove.
 */
export interface LiveBinding {
  /** Unique binding identifier. */
  readonly bindingId: string;
  /** The source this binding references. */
  readonly sourceId: string;
  /** Channel descriptor, if a specific channel is bound. */
  readonly channelId?: LiveChannelDescriptor;
  /** Clip ID this binding is attached to, if any. */
  readonly targetClipId?: string;
  /** Effect ID this binding is attached to, if any. */
  readonly targetEffectId?: string;
  /** Parameter name on the target, if binding to a specific param. */
  readonly targetParamName?: string;
  /** Current resolution status. */
  readonly status: BindingResolutionStatus;
  /** Diagnostic explaining unresolved status, if any. */
  readonly diagnostic?: LiveSourceDiagnostic;
}

/**
 * The resolved state of a live binding.
 *
 * Produced by the binding resolver when a consumer requests
 * resolution of a specific binding.
 */
export interface LiveBindingResolution {
  /** The binding that was resolved. */
  readonly bindingId: string;
  /** Current resolution status. */
  readonly status: BindingResolutionStatus;
  /** The resolved live source, if found and active. */
  readonly source?: LiveSource;
  /** The resolved channel metadata, if available. */
  readonly channel?: LiveChannelMetadata;
  /** Diagnostic explaining why resolution failed, if applicable. */
  readonly diagnostic?: LiveSourceDiagnostic;
}

/**
 * Aggregate metadata about all live bindings in the current session.
 *
 * The pure binding scanner is the source of truth for unresolved
 * live references. It produces this aggregate to power export guard
 * and UI diagnostics.
 */
export interface LiveBindingMetadata {
  /** All live bindings currently persisted on timeline objects. */
  readonly bindings: readonly LiveBinding[];
  /** Count of unresolved bindings. */
  readonly unresolvedCount: number;
  /** Count of orphaned bindings (extension disposed). */
  readonly orphanedCount: number;
  /** Count of disposed bindings (source explicitly disposed). */
  readonly disposedCount: number;
}

// --- Live sessions service ---

/**
 * Live sessions service available as `ctx.creative.sessions` during activate().
 *
 * Provides provider-scoped live source lifecycle management, channel
 * operations, sample delivery, bake, binding resolution, and steering.
 *
 * All live data is ephemeral runtime state scoped to the current
 * provider mount. Only live binding metadata persists in timeline config.
 */
export interface LiveSessionsService {
  // ── Source lifecycle ──────────────────────────────────────────────

  /**
   * Register a new live source.
   * Returns a DisposeHandle that disposes the source when called.
   */
  registerSource(source: Omit<LiveSource, 'status' | 'diagnostics'>): DisposeHandle;

  /**
   * Get a registered live source by ID.
   * Returns undefined if the source is not found.
   */
  getSource(sourceId: string): LiveSource | undefined;

  /**
   * List all registered live sources.
   */
  listSources(): readonly LiveSource[];

  // ── Channel operations ────────────────────────────────────────────

  /**
   * Open a typed channel on a source.
   * Returns a LiveChannelDescriptor that is string-compatible.
   */
  openChannel(
    sourceId: string,
    kind: LiveChannelKind,
    metadata?: Record<string, unknown>,
  ): LiveChannelDescriptor;

  /**
   * Close a live channel.
   * Idempotent — safe to call on already-closed channels.
   */
  closeChannel(channelId: LiveChannelDescriptor): void;

  /**
   * Get rich metadata for a channel.
   * Returns undefined if the channel is not found.
   */
  getChannelMetadata(channelId: LiveChannelDescriptor): LiveChannelMetadata | undefined;

  // ── Sample delivery ───────────────────────────────────────────────

  /**
   * Push a sample frame into a channel's ring buffer.
   * Samples are read synchronously by render paths.
   */
  pushSample(channelId: LiveChannelDescriptor, frame: LiveSampleFrame): void;

  /**
   * Subscribe to samples on a channel.
   * The listener receives every sample pushed to the channel.
   * Returns a DisposeHandle for unsubscription.
   */
  subscribeSamples(
    channelId: LiveChannelDescriptor,
    listener: (sample: LiveSample) => void,
  ): DisposeHandle;

  // ── Bake ──────────────────────────────────────────────────────────

  /**
   * Bake live samples into deterministic timeline artifacts.
   *
   * Bake converts live data into asset registry entries, keyframes,
   * automation clips, standard clips, metadata sidecars, or RenderMaterial
   * refs. Failed bakes leave live sources unchanged.
   *
   * This is one of the two bridges from live runtime to deterministic
   * timeline state (the other being removeLiveBindings).
   */
  bake(selection: LiveBakeSelection): LiveBakeResult;

  /**
   * Remove live bindings for a source.
   *
   * After removal, the source's bindings are cleared from timeline
   * metadata, unblocking export. This is the second bridge from live
   * runtime to deterministic timeline state (alongside bake).
   */
  removeLiveBindings(sourceId: string): void;

  // ── Binding resolution ────────────────────────────────────────────

  /**
   * Resolve a single live binding to its current status and source.
   */
  resolveBinding(bindingId: string): LiveBindingResolution;

  /**
   * Get aggregate live binding metadata.
   * The pure binding scanner produces this aggregate, which is the
   * source of truth for unresolved live references.
   */
  getBindingMetadata(): LiveBindingMetadata;

  // ── Steering ──────────────────────────────────────────────────────

  /**
   * Apply a steering decision to a GenerationSession.
   *
   * The steering resolver must always return an explicit supersede,
   * fork, or reject. GenerationSession live sample delivery must not
   * activate without complete steering lineage.
   */
  applySteeringDecision(decision: SteeringDecision): void;

  // ── Diagnostics ───────────────────────────────────────────────────

  /**
   * Get diagnostics for all sources or a specific source.
   */
  getDiagnostics(sourceId?: string): readonly LiveSourceDiagnostic[];
}
