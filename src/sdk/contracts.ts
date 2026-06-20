/**
 * SDK-owned contract types for state repository interactions.
 *
 * These types are the stable public vocabulary used by settings
 * services and migration utilities.  They are intentionally a minimal
 * subset of the internal ExtensionStateRepository contract so that
 * the SDK boundary does not leak full internal repository surfaces.
 *
 * Host-internal modules at @/tools/video-editor/runtime/extensionStateRepository
 * keep their own richer contracts; the SDK only re-exposes what
 * extension authors need to interact with settings persistence.
 */

// ---------------------------------------------------------------------------
// Settings snapshot
// ---------------------------------------------------------------------------

/** SDK-owned settings snapshot contract. */
export interface SettingsSnapshot {
  readonly extensionId: string;
  readonly schemaVersion: number;
  readonly values: Record<string, unknown>;
  readonly lastWrittenAt: string;
}

// ---------------------------------------------------------------------------
// Lifecycle event
// ---------------------------------------------------------------------------

/** SDK-owned lifecycle event contract (settings-migration scope). */
export interface LifecycleEvent {
  readonly id: string;
  readonly extensionId: string;
  readonly kind: string;
  readonly timestamp: string;
  readonly message: string;
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// State repository (minimal subset)
// ---------------------------------------------------------------------------

/**
 * Minimal SDK-owned state repository contract.
 *
 * The full internal ExtensionStateRepository interface has many methods
 * (pack records, enablement, dev overrides, project lock, etc.) that are
 * irrelevant to extension authors.  This contract exposes only the three
 * members that the SDK settings services actually use.
 */
export interface StateRepository {
  /** Whether the repository has been disposed. */
  readonly isDisposed: boolean;

  /** Persist a settings snapshot. */
  putSettingsSnapshot(snapshot: SettingsSnapshot): Promise<void>;

  /** Append a lifecycle event to the repository. */
  appendLifecycleEvent(event: LifecycleEvent): Promise<void>;
}

// ---------------------------------------------------------------------------
// createLifecycleEvent helper
// ---------------------------------------------------------------------------

/**
 * Create a lifecycle event with a generated UUID v4 ID.
 *
 * This is the SDK-owned equivalent of the internal helper so that
 * migration code does not depend on the internal path for value
 * construction.
 */
export function createLifecycleEvent(
  extensionId: string,
  kind: string,
  message: string,
  detail?: Record<string, unknown>,
): LifecycleEvent {
  return Object.freeze({
    id:
      crypto.randomUUID?.() ??
      `${extensionId}-${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    extensionId,
    kind,
    timestamp: new Date().toISOString(),
    message,
    ...(detail ? { detail: Object.freeze({ ...detail }) } : {}),
  });
}
