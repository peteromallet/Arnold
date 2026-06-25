/**
 * DisposeHandle — disposal-only public contract.
 *
 * Provides the canonical {@link DisposeHandle} interface consumed by
 * lifecycle methods that require cleanup (subscriptions, registrations,
 * listeners, etc.). The interface is intentionally minimal:
 * synchronous, idempotent, and must not throw.
 *
 * @publicContract
 */

/** A handle returned by lifecycle methods that require cleanup. */
export interface DisposeHandle {
  /** Synchronous, idempotent, must not throw. */
  dispose(): void;
  /** Optional explicit resource management support. */
  readonly [Symbol.dispose]?: () => void;
}
