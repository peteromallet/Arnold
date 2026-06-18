/**
 * Extension lifecycle state machine and diagnostics service.
 *
 * Manages per-extension lifecycle (inactive → activating → active → deactivating → disposed)
 * with idempotent transitions, synchronous cleanup via DisposeHandle, dev-console grouping,
 * failure capture, and provider-scoped cleanup when extensions are removed or unmounted.
 *
 * This module is host-owned: the provider creates one ExtensionLifecycleHost per render
 * and calls synchronize() when the extensions prop changes.
 */

import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  DiagnosticSeverity,
} from '@reigh/editor-sdk';
import { disposeExtensionContextServices } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Lifecycle state
// ---------------------------------------------------------------------------

/**
 * Ordered lifecycle states for a single extension.
 *
 *   inactive → activating → active ──┐
 *                ↓                   ↓
 *              failed → deactivating → disposed
 *
 * `disposed` is terminal; all operations on a disposed lifecycle are no-ops.
 */
export type ExtensionLifecycleState =
  | 'inactive'
  | 'activating'
  | 'active'
  | 'failed'
  | 'deactivating'
  | 'disposed';

/** Human-readable ordering for diagnostics / assertions. */
export const LIFECYCLE_STATE_ORDER: Record<ExtensionLifecycleState, number> = {
  inactive: 0,
  activating: 1,
  active: 2,
  failed: 2, // same "post-activation" tier as active
  deactivating: 3,
  disposed: 4,
};

// ---------------------------------------------------------------------------
// Per-extension lifecycle
// ---------------------------------------------------------------------------

/**
 * A managed lifecycle for a single extension.
 *
 * All transition methods are idempotent:
 * - Calling activate() on an already-active extension is a no-op.
 * - Calling deactivate() or dispose() on a disposed extension is a no-op.
 * - dispose() always succeeds and never throws.
 */
export interface ExtensionLifecycle {
  /** Current lifecycle state (readonly). */
  readonly state: ExtensionLifecycleState;

  /** The extension this lifecycle manages (frozen by defineExtension). */
  readonly extension: ReighExtension;

  /** The extension ID (derived from manifest). */
  readonly extensionId: string;

  /** Structured diagnostics emitted by this extension (including lifecycle events). */
  readonly diagnostics: readonly ExtensionDiagnostic[];

  /** The diagnostics service passed to this extension during activation. */
  readonly diagnosticsService: ExtensionDiagnosticsService;

  /** If state === 'failed', the error that caused the failure. Otherwise null. */
  readonly failure: Error | null;

  /**
   * Activate the extension with the given context.
   *
   * Idempotent: if already active, activating, deactivating, or disposed, this is a no-op.
   * If previously failed, deactivate() must be called first to reset before re-activation
   * (the failed state preserves the error for diagnostics).
   *
   * Dev-console grouping is emitted around the activation call.
   */
  activate(ctx: ExtensionContext): void;

  /**
   * Synchronously deactivate the extension.
   *
   * Calls dispose() on the handle returned by activate(), then transitions to disposed.
   * Idempotent and never throws — errors during cleanup are captured as diagnostics.
   */
  deactivate(): void;

  /**
   * Dispose the extension immediately (terminal).
   *
   * If active or failed, calls the stored DisposeHandle first. After this call the
   * lifecycle is permanently disposed and all further operations are no-ops.
   * Idempotent and never throws.
   */
  dispose(): void;
}

// ---------------------------------------------------------------------------
// Concrete diagnostics service
// ---------------------------------------------------------------------------

/**
 * Create a mutable diagnostics service for a single extension.
 *
 * The returned service auto-fills `extensionId` on every reported diagnostic.
 * It is owned by the ExtensionLifecycle and should not be shared across extensions.
 */
export function createExtensionDiagnosticsService(
  extensionId: string,
): ExtensionDiagnosticsService {
  const diagnostics: ExtensionDiagnostic[] = [];

  const service: ExtensionDiagnosticsService = {
    report(diag: Omit<ExtensionDiagnostic, 'extensionId'>): void {
      const full: ExtensionDiagnostic = Object.freeze({
        ...diag,
        extensionId,
      });
      diagnostics.push(full);
    },

    get diagnostics(): readonly ExtensionDiagnostic[] {
      return diagnostics;
    },
  };

  return service;
}

// ---------------------------------------------------------------------------
// Lifecycle factory
// ---------------------------------------------------------------------------

/**
 * Create a new ExtensionLifecycle in the `inactive` state.
 *
 * The returned lifecycle is NOT activated — the caller must call `activate(ctx)`.
 */
export function createExtensionLifecycle(extension: ReighExtension): ExtensionLifecycle {
  const extensionId = extension.manifest.id as string;
  const diagnosticsService = createExtensionDiagnosticsService(extensionId);

  let state: ExtensionLifecycleState = 'inactive';
  let failure: Error | null = null;
  let disposeHandle: DisposeHandle | null = null;
  /** The context passed to activate() — stored so host-service cleanup
   *  (settings localStorage, chrome subscriptions) can run on deactivation. */
  let activeContext: ExtensionContext | null = null;

  // ---- internal helpers ---------------------------------------------------

  function emitLifecycleDiagnostic(
    severity: DiagnosticSeverity,
    code: string,
    message: string,
    detail?: Record<string, unknown>,
  ): void {
    diagnosticsService.report({ severity, code, message, detail });
  }

  function safeDisposeHandle(): void {
    if (!disposeHandle) {
      // Even without an extension-returned handle, clean up host services
      if (activeContext) {
        try {
          disposeExtensionContextServices(activeContext);
        } catch {
          // disposeExtensionContextServices is internally safe
        }
        activeContext = null;
      }
      return;
    }
    const h = disposeHandle;
    disposeHandle = null;
    try {
      if (typeof h.dispose === 'function') {
        h.dispose();
      }
    } catch (err) {
      emitLifecycleDiagnostic(
        'error',
        'lifecycle/dispose-handle-error',
        `Error during DisposeHandle.dispose(): ${String(err)}`,
        { originalError: String(err) },
      );
    }
    // Also honour Symbol.dispose if present
    try {
      if (typeof h[Symbol.dispose] === 'function') {
        (h[Symbol.dispose] as () => void)();
      }
    } catch (err) {
      emitLifecycleDiagnostic(
        'error',
        'lifecycle/symbol-dispose-error',
        `Error during DisposeHandle[Symbol.dispose](): ${String(err)}`,
        { originalError: String(err) },
      );
    }
    // Clean up host-owned services (settings localStorage, chrome subscriptions)
    if (activeContext) {
      try {
        disposeExtensionContextServices(activeContext);
      } catch {
        // disposeExtensionContextServices is internally safe
      }
      activeContext = null;
    }
  }

  function transition(newState: ExtensionLifecycleState): void {
    state = newState;
  }

  // ---- public API ---------------------------------------------------------

  function activate(ctx: ExtensionContext): void {
    // Idempotency guard
    if (state === 'active' || state === 'activating' || state === 'deactivating') {
      // Already in a running or transitioning state — no-op
      return;
    }

    if (state === 'disposed') {
      // Cannot activate a disposed extension
      emitLifecycleDiagnostic(
        'warning',
        'lifecycle/activate-disposed',
        `Cannot activate disposed extension "${extensionId}".`,
      );
      return;
    }

    // failed → allow re-activation (deactivate was already called implicitly via dispose path,
    // but if someone calls activate on a failed extension, we let it retry)
    // Actually, per the task: "failed" means activation threw. The user can call
    // deactivate() to clean up, then activate() to retry. But we should also allow
    // direct activate() from failed as a convenience — it implies deactivate first.

    if (state === 'failed') {
      // Clean up any stale state before retrying
      safeDisposeHandle();
      failure = null;
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/retry-activate',
        `Retrying activation for extension "${extensionId}" after previous failure.`,
      );
    }

    // Transition to activating
    transition('activating');
    emitLifecycleDiagnostic(
      'info',
      'lifecycle/activating',
      `Extension "${extensionId}" is activating.`,
    );

    // Dev-console grouping
    const groupLabel = `Extension [${extensionId}]: activating`;
    const useGroupCollapsed = typeof console.groupCollapsed === 'function';
    const useGroup = typeof console.group === 'function';

    if (useGroupCollapsed) console.groupCollapsed(groupLabel);
    else if (useGroup) console.group(groupLabel);

    // Store the context so host-service cleanup runs on deactivation
    activeContext = ctx;

    try {
      // Call the extension's activate function if it exists
      if (typeof extension.activate === 'function') {
        const result = extension.activate(ctx);
        if (result && typeof result === 'object') {
          disposeHandle = result as DisposeHandle;
        }
      }

      transition('active');
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/activated',
        `Extension "${extensionId}" activated successfully.`,
      );
    } catch (err) {
      transition('failed');
      failure = err instanceof Error ? err : new Error(String(err));
      emitLifecycleDiagnostic(
        'error',
        'lifecycle/activation-failed',
        `Extension "${extensionId}" activation failed: ${String(err)}`,
        { originalError: String(err), stack: failure.stack },
      );
      // Log to dev console within the group
      console.error(`Extension [${extensionId}] activation failed:`, err);
    } finally {
      if (useGroupCollapsed || useGroup) {
        console.groupEnd();
      }
    }
  }

  function deactivate(): void {
    // Idempotency guard
    if (state === 'disposed') return;
    if (state === 'inactive') {
      // Never activated — transition directly to disposed for consistency
      transition('disposed');
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/disposed-inactive',
        `Extension "${extensionId}" disposed (was never activated).`,
      );
      return;
    }
    if (state === 'deactivating') return; // already deactivating

    // Move to deactivating
    const prevState = state;
    transition('deactivating');
    emitLifecycleDiagnostic(
      'info',
      'lifecycle/deactivating',
      `Extension "${extensionId}" is deactivating (from ${prevState}).`,
    );

    // Dev-console grouping
    const groupLabel = `Extension [${extensionId}]: deactivating`;
    const useGroupCollapsed = typeof console.groupCollapsed === 'function';
    const useGroup = typeof console.group === 'function';

    if (useGroupCollapsed) console.groupCollapsed(groupLabel);
    else if (useGroup) console.group(groupLabel);

    try {
      safeDisposeHandle();
      transition('disposed');
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/disposed',
        `Extension "${extensionId}" disposed.`,
      );
    } catch (err) {
      // safeDisposeHandle already catches, but double-guard
      transition('disposed');
      emitLifecycleDiagnostic(
        'error',
        'lifecycle/deactivation-error',
        `Extension "${extensionId}" deactivation error: ${String(err)}`,
        { originalError: String(err) },
      );
    } finally {
      if (useGroupCollapsed || useGroup) {
        console.groupEnd();
      }
    }
  }

  function dispose(): void {
    // Idempotency guard
    if (state === 'disposed') return;

    if (state === 'inactive') {
      // Never activated — just mark disposed
      transition('disposed');
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/disposed-inactive',
        `Extension "${extensionId}" disposed (was never activated).`,
      );
      return;
    }

    // For active/failed/activating/deactivating — clean up then mark disposed
    const prevState = state;
    transition('deactivating');

    const groupLabel = `Extension [${extensionId}]: disposing`;
    const useGroupCollapsed = typeof console.groupCollapsed === 'function';
    const useGroup = typeof console.group === 'function';

    if (useGroupCollapsed) console.groupCollapsed(groupLabel);
    else if (useGroup) console.group(groupLabel);

    try {
      safeDisposeHandle();
    } finally {
      transition('disposed');
      emitLifecycleDiagnostic(
        'info',
        'lifecycle/disposed',
        `Extension "${extensionId}" disposed (was ${prevState}).`,
      );
      if (useGroupCollapsed || useGroup) {
        console.groupEnd();
      }
    }
  }

  // ---- assemble ------------------------------------------------------------

  const lifecycle: ExtensionLifecycle = {
    get state() {
      return state;
    },
    get extension() {
      return extension;
    },
    get extensionId() {
      return extensionId;
    },
    get diagnostics() {
      return diagnosticsService.diagnostics;
    },
    get diagnosticsService() {
      return diagnosticsService;
    },
    get failure() {
      return failure;
    },
    activate,
    deactivate,
    dispose,
  };

  return lifecycle;
}

// ---------------------------------------------------------------------------
// Lifecycle host — manages a collection of lifecycles
// ---------------------------------------------------------------------------

/**
 * Host-owned manager for a collection of ExtensionLifecycle instances.
 *
 * Created once per provider render.  The provider calls `synchronize()` whenever
 * the extensions prop changes; the host diffs the list and activates new
 * extensions while deactivating removed ones.
 *
 * On provider unmount, call `disposeAll()` to synchronously clean up every
 * managed extension.
 */
export interface ExtensionLifecycleHost {
  /** All managed lifecycles, keyed by extension ID. */
  readonly lifecycles: ReadonlyMap<string, ExtensionLifecycle>;

  /** Aggregated diagnostics from all managed lifecycles. */
  readonly diagnostics: readonly ExtensionDiagnostic[];

  /**
   * Synchronize the managed set with a new extension list.
   *
   * - New extensions (not yet managed) are registered and activated.
   * - Removed extensions are deactivated and disposed.
   * - Existing extensions with changed manifests are deactivated and re-activated
   *   (the old lifecycle is disposed, a new one created).
   *
   * @param extensions  The current extension list from the provider props.
   * @param contextFactory  Creates an ExtensionContext for a given extension.
   */
  synchronize(
    extensions: readonly ReighExtension[],
    contextFactory: (ext: ReighExtension) => ExtensionContext,
  ): void;

  /** Dispose all managed lifecycles. Idempotent. */
  disposeAll(): void;
}

/**
 * Create a new ExtensionLifecycleHost.
 */
export function createExtensionLifecycleHost(): ExtensionLifecycleHost {
  const lifecycles = new Map<string, ExtensionLifecycle>();
  const hostDiagnostics: ExtensionDiagnostic[] = [];
  let disposed = false;

  function computeDiagnostics(): readonly ExtensionDiagnostic[] {
    const all: ExtensionDiagnostic[] = [...hostDiagnostics];
    for (const lc of lifecycles.values()) {
      all.push(...lc.diagnostics);
    }
    return Object.freeze(all);
  }

  function synchronize(
    extensions: readonly ReighExtension[],
    contextFactory: (ext: ReighExtension) => ExtensionContext,
  ): void {
    if (disposed) {
      // Host is disposed — log warning but don't crash
      if (typeof console !== 'undefined' && console.warn) {
        console.warn(
          'ExtensionLifecycleHost.synchronize() called after dispose. Ignoring.',
        );
      }
      return;
    }

    const incomingIds = new Set<string>();
    const toActivate: ExtensionLifecycle[] = [];

    for (const ext of extensions) {
      const id = ext.manifest.id as string;
      incomingIds.add(id);

      const existing = lifecycles.get(id);
      if (existing) {
        // Check if manifest changed (by reference comparison, since manifests are frozen)
        if (existing.extension.manifest !== ext.manifest) {
          // Manifest changed — dispose old and create new
          existing.dispose();
          lifecycles.delete(id);
          const newLc = createExtensionLifecycle(ext);
          lifecycles.set(id, newLc);
          toActivate.push(newLc);
        }
        // else: same extension, nothing to do
      } else {
        // New extension
        const lc = createExtensionLifecycle(ext);
        lifecycles.set(id, lc);
        toActivate.push(lc);
      }
    }

    // Remove extensions no longer in the list
    for (const [id, lc] of lifecycles) {
      if (!incomingIds.has(id)) {
        lc.dispose();
        lifecycles.delete(id);
      }
    }

    // Activate new/changed extensions
    for (const lc of toActivate) {
      try {
        const ctx = contextFactory(lc.extension);
        lc.activate(ctx);
      } catch (err) {
        // Context factory threw — capture in both the lifecycle's diagnostics
        // and the persistent host diagnostics so they survive lifecycle removal.
        const diag: ExtensionDiagnostic = Object.freeze({
          severity: 'error' as const,
          code: 'lifecycle/context-factory-error',
          message: `Failed to create context for extension "${lc.extensionId}": ${String(err)}`,
          extensionId: lc.extensionId,
          detail: { originalError: String(err) },
        });
        lc.diagnosticsService.report({
          severity: diag.severity,
          code: diag.code,
          message: diag.message,
          detail: diag.detail,
        });
        hostDiagnostics.push(diag);
        // Force-dispose and remove the lifecycle since we can't activate it
        lc.dispose();
        lifecycles.delete(lc.extensionId);
      }
    }
  }

  function disposeAll(): void {
    if (disposed) return;
    disposed = true;

    for (const lc of lifecycles.values()) {
      try {
        lc.dispose();
      } catch {
        // dispose() itself is already safe, but double-guard
      }
    }
    lifecycles.clear();
  }

  const host: ExtensionLifecycleHost = {
    get lifecycles() {
      return lifecycles as ReadonlyMap<string, ExtensionLifecycle>;
    },
    get diagnostics() {
      return computeDiagnostics();
    },
    synchronize,
    disposeAll,
  };

  return host;
}
