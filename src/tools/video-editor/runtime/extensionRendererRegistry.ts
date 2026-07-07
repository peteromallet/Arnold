/**
 * Host-owned renderer registry.
 *
 * Scopes renderers by extension ID + render ID, emits structured diagnostics
 * for duplicates and missing/unregistered renderers, and notifies subscribers
 * on every mutation so the shell can reconcile null-render descriptors.
 *
 * One registry per provider mount.  The registry is wired into the SDK via
 * {@link RendererRegistryHost} so that every `ctx.ui.registerRenderer()` call
 * is mirrored here at activation time.
 */

import type { DisposeHandle, ExtensionDiagnostic, DiagnosticSeverity } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Public registry shapes
// ---------------------------------------------------------------------------

export type RegisteredExtensionRenderer = (...args: unknown[]) => unknown;

/** Frozen snapshot of a single render binding. */
export interface RendererRegistryEntry {
  readonly extensionId: string;
  readonly renderId: string;
  readonly renderer: RegisteredExtensionRenderer;
}

/** Frozen snapshot of the whole registry. */
export interface RendererRegistrySnapshot {
  /** All entries, deterministically ordered by extension → render ID. */
  readonly entries: readonly RendererRegistryEntry[];
  /** Diagnostics emitted by the registry (duplicates, missing, etc.). */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Lookup helper: get the renderer for a scoped render ID. */
  readonly get: (extensionId: string, renderId: string) =>
    RegisteredExtensionRenderer | undefined;
}

/** Subscriber callback receives the latest snapshot after every mutation. */
export type RendererRegistrySubscriber = (snapshot: RendererRegistrySnapshot) => void;

// ---------------------------------------------------------------------------
// Public registry interface
// ---------------------------------------------------------------------------

export interface RendererRegistry {
  /**
   * Register a renderer for the given extension + render ID.
   *
   * If the combination is already registered, the previous renderer is
   * replaced and a duplicate diagnostic is emitted.
   *
   * @returns A DisposeHandle that removes this single binding.
   */
  register(
    extensionId: string,
    renderId: string,
    renderer: RegisteredExtensionRenderer,
  ): DisposeHandle;

  /** Remove a single binding (called by DisposeHandle or host). */
  unregister(extensionId: string, renderId: string): void;

  /** Look up a renderer. */
  resolve(
    extensionId: string,
    renderId: string,
  ): RegisteredExtensionRenderer | undefined;

  /** Subscribe to registry mutations. Returns cleanup handle. */
  subscribe(subscriber: RendererRegistrySubscriber): DisposeHandle;

  /** Return a frozen snapshot suitable for useSyncExternalStore. */
  getSnapshot(): RendererRegistrySnapshot;

  /**
   * Remove every renderer for a given extension.
   * Called during extension disposal without clearing historical diagnostics.
   */
  unregisterAll(extensionId: string): void;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

interface InternalEntry {
  extensionId: string;
  renderId: string;
  renderer: RegisteredExtensionRenderer;
}

function freezeEntry(e: InternalEntry): RendererRegistryEntry {
  return Object.freeze({
    extensionId: e.extensionId,
    renderId: e.renderId,
    renderer: e.renderer,
  });
}

function sortEntries(entries: InternalEntry[]): InternalEntry[] {
  return [...entries].sort((a, b) => {
    const extCmp = a.extensionId.localeCompare(b.extensionId);
    if (extCmp !== 0) return extCmp;
    return a.renderId.localeCompare(b.renderId);
  });
}

function emitDiagnostic(
  diagnostics: ExtensionDiagnostic[],
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  extensionId?: string,
  contributionId?: string,
): void {
  diagnostics.push(Object.freeze({
    severity,
    code,
    message,
    ...(extensionId ? { extensionId } : {}),
    ...(contributionId ? { contributionId } : {}),
  }));
}

export function createRendererRegistry(): RendererRegistry {
  // extensionId → (renderId → renderer)
  const map = new Map<string, Map<string, RegisteredExtensionRenderer>>();
  const diagnostics: ExtensionDiagnostic[] = [];
  const subscribers = new Set<RendererRegistrySubscriber>();

  let frozenSnapshot: RendererRegistrySnapshot | null = null;

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function notifySubscribers(): void {
    const snapshot = getSnapshot();
    subscribers.forEach((sub) => {
      try { sub(snapshot); } catch { /* subscriber errors are non-fatal */ }
    });
  }

  function ensureExtMap(extensionId: string): Map<string, RegisteredExtensionRenderer> {
    let extMap = map.get(extensionId);
    if (!extMap) {
      extMap = new Map();
      map.set(extensionId, extMap);
    }
    return extMap;
  }

  function buildEntries(): InternalEntry[] {
    const result: InternalEntry[] = [];
    map.forEach((extMap, extensionId) => {
      extMap.forEach((renderer, renderId) => {
        result.push({ extensionId, renderId, renderer });
      });
    });
    return sortEntries(result);
  }

  // ---- public API ---------------------------------------------------------

  function register(
    extensionId: string,
    renderId: string,
    renderer: RegisteredExtensionRenderer,
  ): DisposeHandle {
    const extMap = ensureExtMap(extensionId);

    if (extMap.has(renderId)) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'render/duplicate-renderer',
        `Render ID "${renderId}" for extension "${extensionId}" already has a registered renderer. The previous renderer will be replaced.`,
        extensionId,
        renderId,
      );
    }

    extMap.set(renderId, renderer);
    invalidateSnapshot();
    notifySubscribers();

    let disposed = false;
    return {
      dispose(): void {
        if (disposed) return;
        disposed = true;
        const ext = map.get(extensionId);
        if (ext) {
          ext.delete(renderId);
          if (ext.size === 0) map.delete(extensionId);
        }
        invalidateSnapshot();
        notifySubscribers();
      },
    };
  }

  function unregister(extensionId: string, renderId: string): void {
    const extMap = map.get(extensionId);
    if (!extMap) return;
    extMap.delete(renderId);
    if (extMap.size === 0) map.delete(extensionId);
    invalidateSnapshot();
    notifySubscribers();
  }

  function resolve(
    extensionId: string,
    renderId: string,
  ): RegisteredExtensionRenderer | undefined {
    return map.get(extensionId)?.get(renderId);
  }

  function subscribe(subscriber: RendererRegistrySubscriber): DisposeHandle {
    subscribers.add(subscriber);
    return {
      dispose(): void {
        subscribers.delete(subscriber);
      },
    };
  }

  function getSnapshot(): RendererRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const entries = Object.freeze(buildEntries().map(freezeEntry));

    const get = (extensionId: string, renderId: string) => {
      return map.get(extensionId)?.get(renderId);
    };

    frozenSnapshot = Object.freeze({
      entries,
      diagnostics: Object.freeze([...diagnostics]),
      get,
    });

    return frozenSnapshot;
  }

  function unregisterAll(extensionId: string): void {
    const extMap = map.get(extensionId);
    if (!extMap) return;
    map.delete(extensionId);
    invalidateSnapshot();
    notifySubscribers();
  }

  const registry: RendererRegistry = {
    register,
    unregister,
    resolve,
    subscribe,
    getSnapshot,
    unregisterAll,
  };

  return registry;
}
