/**
 * Core settings contracts for the public SDK (M2a — extracted from index.ts).
 *
 * @publicContract
 */

import type { DisposeHandle } from './dispose';

// ---------------------------------------------------------------------------
// Settings schema
// ---------------------------------------------------------------------------

/** Settings schema descriptor with version for migration tracking. */
export interface ExtensionSettingsSchema {
  /** Monotonic version number; increments when the settings shape changes. */
  version: number;
  /** Optional JSON Schema-like shape descriptor (subset). */
  schema?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Settings service
// ---------------------------------------------------------------------------

/** Settings service: localStorage-backed key-value store scoped per extension. */
export interface ExtensionSettingsService {
  get<T = unknown>(key: string): T | undefined;
  set<T = unknown>(key: string, value: T): void;
  delete(key: string): void;
  keys(): readonly string[];
  /**
   * Subscribe to settings change notifications.
   *
   * The listener is called after every successful `set()` or `delete()`.
   * Invalid writes blocked by Ajv validation do NOT trigger notifications.
   * Returns a {@link DisposeHandle} to unsubscribe.
   */
  subscribe(listener: () => void): DisposeHandle;
}
