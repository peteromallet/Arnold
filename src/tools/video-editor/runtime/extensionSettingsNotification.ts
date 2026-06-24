/**
 * Host-visible extension-scoped settings notification registry (T9).
 *
 * Provides a single seam through which the manager, runtime lifecycle host,
 * and host-owned UI can observe settings changes across all active extension
 * settings services without importing each service directly.
 *
 * ## Design
 *
 * The registry has two notification lanes:
 *
 * - Host-visible notifications are delivered only by explicit
 *   `notifySettingsChanged()` calls after repository persistence has completed.
 *   Manager reload consumers subscribe to this lane so they never re-read a
 *   stale repository snapshot from an SDK-local, pre-persist mutation.
 * - Local service notifications are delivered from the registered SDK
 *   `ExtensionSettingsService.subscribe()` callback. They are intentionally
 *   exposed only through `subscribeToLocalExtension()` for consumers that need
 *   same-turn local change observation and do not perform repository reloads.
 *
 * ## Lifecycle
 *
 * - Created once per provider mount alongside the lifecycle host.
 * - Services are registered during activation and unregistered on disposal
 *   (via the returned `DisposeHandle`).
 * - The registry itself is disposed when the provider unmounts.
 * - All subscription handles are idempotent and must not throw.
 *
 * ## Thread safety
 *
 * All operations are synchronous and safe to call from any context that has
 * access to the registry. Listener errors are caught and silently dropped
 * (same contract as the SDK settings service).
 */

import type { DisposeHandle, ExtensionSettingsService } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

/**
 * Host-visible registry that aggregates settings-change notifications
 * across all registered extension settings services.
 *
 * Host-owned consumers (manager UI, persistence bridges, diagnostics)
 * subscribe to this registry to react to any extension's settings changes
 * without importing individual service instances.
 */
export interface ExtensionSettingsNotificationRegistry {
  /**
   * Register a settings service for an extension.
   *
   * The registry subscribes to the service's internal notification channel.
   * Returns a `DisposeHandle` that unregisters the service (and cleans up
   * the internal subscription) when called.  Idempotent — calling dispose
   * multiple times is safe.
   *
   * If a service for the same extension ID is already registered, the old
   * subscription is silently replaced.
   */
  registerService(
    extensionId: string,
    service: ExtensionSettingsService,
  ): DisposeHandle;

  /**
   * Subscribe to ALL post-persist extension settings changes.
   *
   * The listener is called (with the extension ID) only when the host explicitly
   * publishes a persisted settings change via `notifySettingsChanged()`. It is
   * not called by SDK-local `set()` / `delete()` notifications.
   *
   * Returns a `DisposeHandle` to unsubscribe.  Idempotent.
   */
  subscribe(listener: (extensionId: string) => void): DisposeHandle;

  /**
   * Subscribe to post-persist settings changes for a single extension.
   *
   * The listener is called only when the host explicitly publishes a persisted
   * settings change for the specified extension via `notifySettingsChanged()`.
   *
   * Returns a `DisposeHandle` to unsubscribe.  Idempotent.
   */
  subscribeToExtension(
    extensionId: string,
    listener: () => void,
  ): DisposeHandle;

  /**
   * Subscribe to immediate SDK-local settings changes for a single extension.
   *
   * This lane is fed by the registered ExtensionSettingsService's own
   * `subscribe()` callback and fires before repository persistence completes.
   * It is intentionally separate from manager-visible subscriptions; consumers
   * that reload repository snapshots should use `subscribeToExtension()`.
   */
  subscribeToLocalExtension(
    extensionId: string,
    listener: () => void,
  ): DisposeHandle;

  /**
   * Whether the registry has been disposed.  Once disposed, all registered
   * service subscriptions are cleaned up and no further notifications
   * will be delivered.
   */
  readonly isDisposed: boolean;

  /**
   * Dispose the registry.  Cleans up all internal service subscriptions
   * and clears all host-side listener registrations.  Idempotent — safe
   * to call multiple times.
   */
  dispose(): void;

  /**
   * Manually notify host-side listeners that an extension's settings have
   * changed after persistence. This is intended for host-owned consumers
   * (e.g. the manager UI) and SDK persistence-success callbacks that have
   * already written through to the repository.
   *
   * Safe to call when the registry is disposed — it will silently no-op.
   */
  notifySettingsChanged(extensionId: string): void;

  /**
   * Return a snapshot of the currently registered extension IDs.
   * Useful for debugging and testing.
   */
  getRegisteredExtensionIds(): readonly string[];
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a new host-visible settings notification registry.
 *
 * The returned registry is ready for use immediately.  It does not depend
 * on any external services and owns all internal state.
 */
export function createExtensionSettingsNotificationRegistry(): ExtensionSettingsNotificationRegistry {
  // Per-extension service dispose handles (for cleanup on unregister/dispose)
  const serviceSubscriptions = new Map<string, DisposeHandle>();

  // Host-side listeners: all-extensions
  const globalListeners = new Set<(extensionId: string) => void>();

  // Host-side listeners: per-extension
  const perExtensionListeners = new Map<string, Set<() => void>>();

  // Immediate service listeners: per-extension, explicitly local-only.
  const perExtensionLocalListeners = new Map<string, Set<() => void>>();

  let disposed = false;

  // ---- internal -----------------------------------------------------------

  /** Notify all host-side listeners that an extension's settings changed. */
  function notifyHostListeners(extensionId: string): void {
    // Global listeners
    for (const listener of globalListeners) {
      try {
        listener(extensionId);
      } catch {
        // Listener errors are silently dropped
      }
    }

    // Per-extension listeners
    const extListeners = perExtensionListeners.get(extensionId);
    if (extListeners) {
      for (const listener of extListeners) {
        try {
          listener();
        } catch {
          // Listener errors are silently dropped
        }
      }
    }
  }

  /** Notify explicit local-only listeners that a registered service changed. */
  function notifyLocalListeners(extensionId: string): void {
    const extListeners = perExtensionLocalListeners.get(extensionId);
    if (!extListeners) return;

    for (const listener of extListeners) {
      try {
        listener();
      } catch {
        // Listener errors are silently dropped
      }
    }
  }

  // ---- public -------------------------------------------------------------

  function registerService(
    extensionId: string,
    service: ExtensionSettingsService,
  ): DisposeHandle {
    if (disposed) {
      return { dispose() {} };
    }

    // Dispose any existing subscription for this extension
    const existing = serviceSubscriptions.get(extensionId);
    if (existing) {
      try {
        existing.dispose();
      } catch {
        // dispose is safe
      }
    }

    // Subscribe to the service's internal, pre-persist notification. This is
    // intentionally isolated from host-visible manager reload subscribers.
    const handle = service.subscribe(() => {
      notifyLocalListeners(extensionId);
    });

    serviceSubscriptions.set(extensionId, handle);

    return {
      dispose(): void {
        const current = serviceSubscriptions.get(extensionId);
        if (current === handle) {
          try {
            handle.dispose();
          } catch {
            // dispose is safe
          }
          serviceSubscriptions.delete(extensionId);
        }
      },
    };
  }

  function subscribe(listener: (extensionId: string) => void): DisposeHandle {
    globalListeners.add(listener);
    return {
      dispose(): void {
        globalListeners.delete(listener);
      },
    };
  }

  function subscribeToExtension(
    extensionId: string,
    listener: () => void,
  ): DisposeHandle {
    if (!perExtensionListeners.has(extensionId)) {
      perExtensionListeners.set(extensionId, new Set());
    }
    const extListeners = perExtensionListeners.get(extensionId)!;
    extListeners.add(listener);

    return {
      dispose(): void {
        extListeners.delete(listener);
        if (extListeners.size === 0) {
          perExtensionListeners.delete(extensionId);
        }
      },
    };
  }

  function subscribeToLocalExtension(
    extensionId: string,
    listener: () => void,
  ): DisposeHandle {
    if (!perExtensionLocalListeners.has(extensionId)) {
      perExtensionLocalListeners.set(extensionId, new Set());
    }
    const extListeners = perExtensionLocalListeners.get(extensionId)!;
    extListeners.add(listener);

    return {
      dispose(): void {
        extListeners.delete(listener);
        if (extListeners.size === 0) {
          perExtensionLocalListeners.delete(extensionId);
        }
      },
    };
  }

  function disposeRegistry(): void {
    if (disposed) return;
    disposed = true;

    // Dispose all service subscriptions
    for (const [, handle] of serviceSubscriptions) {
      try {
        handle.dispose();
      } catch {
        // dispose is safe
      }
    }
    serviceSubscriptions.clear();

    // Clear all host-side listeners
    globalListeners.clear();
    perExtensionListeners.clear();
    perExtensionLocalListeners.clear();
  }

  function notifySettingsChanged(extensionId: string): void {
    if (disposed) return;
    notifyHostListeners(extensionId);
  }

  function getRegisteredExtensionIds(): readonly string[] {
    return [...serviceSubscriptions.keys()];
  }

  const registry: ExtensionSettingsNotificationRegistry = {
    registerService,
    subscribe,
    subscribeToExtension,
    subscribeToLocalExtension,
    notifySettingsChanged,
    get isDisposed(): boolean {
      return disposed;
    },
    dispose: disposeRegistry,
    getRegisteredExtensionIds,
  };

  return registry;
}
