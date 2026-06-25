export {
  TimelineVersionConflictError,
  isTimelineVersionConflictError,
} from '@/sdk/video/timeline/errors.ts';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';
import type { AssetResolver } from '@/tools/video-editor/data/AssetResolver.ts';
export type {
  AssetProfile,
  SilenceRegion,
  UploadedAssetResult,
  UploadAssetOptions,
} from '@/tools/video-editor/data/AssetResolver.ts';

export interface LoadedTimeline {
  config: TimelineConfig;
  configVersion: number;
}

export class TimelineNotFoundError extends Error {
  code = 'timeline_not_found' as const;

  constructor(timelineId: string) {
    super(`Timeline ${timelineId} not found — it may have been deleted`);
    this.name = 'TimelineNotFoundError';
  }
}

export function isTimelineNotFoundError(error: unknown): error is TimelineNotFoundError {
  return error instanceof TimelineNotFoundError
    || (error instanceof Error && error.name === 'TimelineNotFoundError');
}

// ---------------------------------------------------------------------------
// Extension persistence contracts (M2 Provider Persistence Spine)
// ---------------------------------------------------------------------------

import type {
  ExtensionStateRepository,
  ExtensionSettingsSnapshot,
} from '@/tools/video-editor/runtime/extensionStateRepository.ts';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';


// ---------------------------------------------------------------------------
// Stable diagnostic codes for unsupported extension persistence capabilities
// ---------------------------------------------------------------------------

/**
 * Emitted when a {@link DataProvider} does not support extension state
 * persistence (enablement, packs, lifecycle events, dev overrides, project
 * lock metadata).
 */
export const PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED =
  'provider_capability_extension_state_unsupported' as const;

/**
 * Emitted when a {@link DataProvider} does not support extension settings
 * snapshot persistence.
 */
export const PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED =
  'provider_capability_extension_settings_unsupported' as const;

/**
 * Emitted when a {@link DataProvider} does not support extension proposal
 * storage (M3 handoff foundation).
 */
export const PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED =
  'provider_capability_extension_proposals_unsupported' as const;

/**
 * Scope that binds extension persistence to a specific user and timeline.
 *
 * All extension state, settings, and proposals managed by an
 * {@link ExtensionPersistenceService} are scoped to this (userId, timelineId)
 * pair. Providers that implement extension persistence MUST isolate data by
 * this scope so that no cross-user or cross-timeline state leakage occurs.
 */
export interface ExtensionPersistenceScope {
  /** The owning user identifier (auth subject). */
  readonly userId: string;
  /** The timeline identifier that owns the extension state. */
  readonly timelineId: string;
}

// ---------------------------------------------------------------------------
// Proposal foundation types (M3 handoff)
// ---------------------------------------------------------------------------

/** The lifecycle status of an extension proposal. */
export type ExtensionProposalStatus =
  | 'draft'
  | 'submitted'
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'stale'
  | 'cancelled'
  | 'expired';

/** A single persisted proposal record. */
export interface ExtensionProposalRecord {
  /** Unique proposal identifier. */
  readonly id: string;
  /** The extension that emitted the proposal. */
  readonly extensionId: string;
  /** ISO 8601 timestamp of creation. */
  readonly createdAt: string;
  /** ISO 8601 timestamp of last update. */
  readonly updatedAt: string;
  /** Current lifecycle status. */
  readonly status: ExtensionProposalStatus;
  /** Opaque payload as defined by the extension (JSON-serializable). */
  readonly payload: Record<string, unknown>;
  /** Optional human-readable title for UI surfacing. */
  readonly title?: string;
  /** Backward-compatible display label used by early M2 cache tests. */
  readonly label?: string;
  /** Optional structured detail for filtering / display. */
  readonly detail?: Record<string, unknown>;
  /**
   * The timeline config version this proposal was created against.
   * Used for stale/expired conflict diagnostics (M3).
   */
  readonly baseVersion?: number;
  /**
   * Epoch-ms timestamp when this proposal expires.
   * `undefined` means no expiry (M3).
   */
  readonly expiresAt?: number;
  /**
   * ISO 8601 timestamp when this proposal was accepted.
   * Only present when status is `accepted` (M3).
   */
  readonly acceptedAt?: string;
  /**
   * ISO 8601 timestamp when this proposal was rejected.
   * Only present when status is `rejected` (M3).
   */
  readonly rejectedAt?: string;
}

/** A diagnostic code for proposal storage degradation (e.g., IndexedDB down). */
export const PROPOSAL_STORAGE_DEGRADED =
  'proposal_storage_degraded' as const;

export type ExtensionProposal = ExtensionProposalRecord;

/** Query criteria for listing proposals. */
export interface ExtensionProposalQuery {
  /** Filter by extension identifier. */
  extensionId?: string;
  /** Filter by one or more lifecycle statuses. */
  statuses?: readonly ExtensionProposalStatus[];
  /** Inclusive start timestamp (ISO 8601). */
  since?: string;
  /** Inclusive end timestamp (ISO 8601). */
  until?: string;
  /** Maximum number of proposals to return. */
  limit?: number;
}

// ---------------------------------------------------------------------------
// ExtensionPersistenceCapabilities
// ---------------------------------------------------------------------------

/**
 * Describes which extension persistence capabilities a provider's
 * {@link ExtensionPersistenceService} supports.
 *
 * ## Capability truth: factory-plus-conformance
 *
 * A provider advertises support for a capability **solely** by implementing
 * the corresponding method on its {@link ExtensionPersistenceService} and
 * passing the shared provider conformance suite. The booleans on this
 * interface are derived from actual method availability — they are
 * descriptive, not prescriptive.
 *
 * Providers that do not implement a factory method MUST return `false` for
 * the matching capability and MUST NOT silently no-op when the capability
 * is requested. Callers should consult the conformance suite result rather
 * than these flags alone when deciding whether to depend on a capability.
 */
export interface ExtensionPersistenceCapabilities {
  /** The provider supports extension state persistence (enablement, packs, lifecycle). */
  readonly state: boolean;
  /** The provider supports extension settings snapshot persistence. */
  readonly settings: boolean;
  /** The provider supports extension proposal storage (M3 foundation). */
  readonly proposals: boolean;
}

// ---------------------------------------------------------------------------
// ExtensionPersistenceService
// ---------------------------------------------------------------------------

/**
 * Provider-owned service that encapsulates extension persistence for a
 * single (userId, timelineId) scope.
 *
 * Providers advertise support by implementing
 * {@link DataProvider.createExtensionPersistenceService}. When a provider
 * does not support extension persistence, the factory is absent and
 * callers receive normalized unsupported diagnostics.
 *
 * The service wraps:
 * - An {@link ExtensionStateRepository} for enablement, packs, lifecycle
 *   events, dev overrides, and project lock metadata.
 * - A settings facade backed by {@link ExtensionSettingsSnapshot} (imported
 *   and reused from `extensionStateRepository.ts` — no parallel settings
 *   model exists).
 * - A proposal storage foundation for M3 handoff (create, read, update
 *   status, list — policy execution is owned by M3).
 *
 * ## Lifecycle
 *
 * 1. The provider creates the service via its factory.
 * 2. Callers invoke `initialize()` before any data access.
 * 3. Callers invoke `dispose()` when the scope is torn down.
 * 4. After disposal, all methods reject with a descriptive error.
 */
export interface ExtensionPersistenceService {
  /** The scope this service instance is bound to. */
  readonly scope: ExtensionPersistenceScope;

  /** The capabilities this service instance provides. */
  readonly capabilities: ExtensionPersistenceCapabilities;

  /**
   * Initialize the service (hydrate caches, open connections).
   *
   * Must be called before any other method. Idempotent.
   */
  initialize(): Promise<void>;

  /**
   * Dispose the service, closing connections and releasing resources.
   *
   * After disposal, all methods reject. Idempotent.
   */
  dispose(): Promise<void>;

  /** Whether the service has been disposed. */
  readonly isDisposed: boolean;

  /**
   * The underlying extension state repository.
   *
   * Only available when {@link ExtensionPersistenceCapabilities.state} is
   * `true`. Returns `undefined` for providers that only support settings
   * or proposals.
   */
  readonly stateRepository?: ExtensionStateRepository;

  /**
   * Persist an extension settings snapshot for the given extension.
   *
   * Only available when {@link ExtensionPersistenceCapabilities.settings}
   * is `true`. Overwrites any existing snapshot for the same extension ID.
   */
  putSettings?(snapshot: ExtensionSettingsSnapshot): Promise<void>;

  /**
   * Retrieve a settings snapshot for the given extension.
   *
   * Returns `null` when no snapshot exists or settings are unsupported.
   */
  getSettings?(extensionId: string): Promise<ExtensionSettingsSnapshot | null>;

  /**
   * Retrieve all settings snapshots in this scope.
   */
  getAllSettings?(): Promise<ExtensionSettingsSnapshot[]>;

  /**
   * Delete a settings snapshot (e.g. on uninstall).
   *
   * Idempotent.
   */
  deleteSettings?(extensionId: string): Promise<void>;

  // -----------------------------------------------------------------------
  // Proposal storage foundation (M3 handoff)
  // -----------------------------------------------------------------------

  /**
   * Create a new proposal record.
   *
   * Only available when {@link ExtensionPersistenceCapabilities.proposals}
   * is `true`.
   */
  createProposal?(record: Omit<ExtensionProposalRecord, 'id' | 'createdAt' | 'updatedAt'>): Promise<ExtensionProposalRecord | string>;

  /**
   * Retrieve a proposal by ID.
   *
   * Returns `null` when no proposal exists.
   */
  getProposal?(id: string): Promise<ExtensionProposalRecord | null>;

  /**
   * Update the status (and optionally detail) of an existing proposal.
   */
  updateProposalStatus?(id: string, status: ExtensionProposalStatus, detail?: Record<string, unknown>): Promise<ExtensionProposalRecord | void>;

  /**
   * Query proposals matching the given criteria.
   *
   * Returns proposals in reverse chronological order (newest first).
   */
  queryProposals?(query: ExtensionProposalQuery): Promise<ExtensionProposalRecord[]>;
}

// ---------------------------------------------------------------------------
// DataProvider extension
// ---------------------------------------------------------------------------

export interface DataProvider extends AssetResolver {
  persistenceEnabled?: boolean;
  loadTimeline(timelineId: string): Promise<LoadedTimeline>;
  saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number>;
  saveCheckpoint?(timelineId: string, checkpoint: Omit<Checkpoint, 'id'>): Promise<string>;
  loadCheckpoints?(timelineId: string): Promise<Checkpoint[]>;
  loadAssetRegistry(timelineId: string): Promise<AssetRegistry>;

  /**
   * Create an extension persistence service for the given scope.
   *
   * Optional — providers that do not support extension persistence leave
   * this method absent. When absent, callers receive normalized unsupported
   * diagnostics instead of silently no-oping.
   *
   * The returned service's {@link ExtensionPersistenceCapabilities} reflect
   * the provider's actual capabilities. A provider that implements this
   * factory MUST pass the shared provider conformance suite for every
   * capability it advertises.
   *
   * @param scope   The (userId, timelineId) scope for all extension data.
   * @param diagnostics An array the provider may append
   *   {@link ExtensionDiagnostic} entries to (unsupported notices,
   *   degraded-mode warnings, etc.).
   */
  createExtensionPersistenceService?(
    scope: ExtensionPersistenceScope,
    diagnostics: ExtensionDiagnostic[],
  ): ExtensionPersistenceService;
}

export function isDataProviderPersistenceEnabled(provider: DataProvider | null | undefined): boolean {
  return provider?.persistenceEnabled !== false;
}

// The persistence boundary for the headless editor core remains the existing
// data provider contract. Core/runtime ports can rename or regroup host inputs,
// but persistence should continue to flow through this canonical interface.
export type VideoEditorPersistencePort = DataProvider;

// ---------------------------------------------------------------------------
// Unsupported capability diagnostics helper
// ---------------------------------------------------------------------------

/**
 * Append {@link ExtensionDiagnostic} entries to `diagnostics` for every
 * extension persistence capability that is not supported by the provider.
 *
 * This is the **single helper path** for emitting the three stable
 * `provider_capability_extension_*_unsupported` codes. Callers that
 * encounter a provider without a
 * {@link DataProvider.createExtensionPersistenceService} factory (or whose
 * factory returns `null`) should call this helper instead of silently
 * no-oping so that downstream consumers (diagnostics UIs, telemetry,
 * conformance reporters) receive normalized, predictable signals.
 *
 * @param diagnostics  The array to append diagnostic entries to.
 * @param capabilities  Optional capability flags. When omitted or when a key
 *   is absent, that capability is treated as **unsupported** and a diagnostic
 *   is emitted. When a key is `true`, the corresponding diagnostic is
 *   suppressed (the provider supports that capability). When a key is
 *   `false`, the diagnostic is emitted (explicit unsupported).
 * @param providerName  Optional human-readable provider name used in
 *   diagnostic messages. Defaults to `"this provider"`.
 */
export function pushUnsupportedCapabilityDiagnostics(
  diagnostics: ExtensionDiagnostic[],
  capabilities?: {
    readonly state?: boolean;
    readonly settings?: boolean;
    readonly proposals?: boolean;
  },
  providerName?: string,
): void {
  const name = providerName ?? 'this provider';

  const emit = (code: string, capability: string): void => {
    diagnostics.push({
      severity: 'info',
      code,
      message: `Extension ${capability} persistence is not supported by ${name}.`,
      milestone: 'm2',
    });
  };

  if (!capabilities) {
    emit(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED, 'state');
    emit(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED, 'settings');
    emit(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED, 'proposal');
    return;
  }

  if (!capabilities.state) {
    emit(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED, 'state');
  }
  if (!capabilities.settings) {
    emit(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED, 'settings');
  }
  if (!capabilities.proposals) {
    emit(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED, 'proposal');
  }
}
