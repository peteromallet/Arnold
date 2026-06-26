/**
 * Family adapter coordinator — bulk normalization, disposal, and
 * capability projection over a {@link FamilyAdapterRegistry}.
 *
 * This module is a pure coordination layer. It does NOT import host
 * runtime code (editor internals, DataProvider, timeline ops, etc.).
 * All operations are side-effect-free except for the explicit
 * `disposeAll` path (which calls a caller-provided disposer).
 *
 * @module families/familyAdapterCoordinator
 * @publicContract
 */

import type { ExecutionMaturity } from './maturity';
import type {
  HostFamilyAdapter,
  FamilyAdapterRegistry,
} from './familyAdapter';

// ---------------------------------------------------------------------------
// Bulk normalization
// ---------------------------------------------------------------------------

/**
 * Normalize a batch of adapters into a deduplicated map keyed by
 * contribution kind.  When multiple adapters declare the same kind,
 * the **last** adapter in the input array wins.
 *
 * `null` entries are silently skipped — normalization only produces
 * entries for real (non-null) adapters.
 *
 * @returns A `Map<string, HostFamilyAdapter>` containing one entry per
 *          unique kind, in insertion order.
 */
export function normalizeAdapters(
  adapters: ReadonlyArray<HostFamilyAdapter>,
): Map<string, HostFamilyAdapter> {
  const map = new Map<string, HostFamilyAdapter>();
  for (const adapter of adapters) {
    if (adapter !== null) {
      map.set(adapter.kind, adapter);
    }
  }
  return map;
}

// ---------------------------------------------------------------------------
// Bulk disposal
// ---------------------------------------------------------------------------

/**
 * Call a caller-provided disposer on every adapter in the array.
 *
 * The disposer is responsible for the actual teardown logic (e.g.
 * unregistering host hooks, freeing resources).  The coordinator
 * merely iterates and delegates.
 *
 * Each adapter is disposed exactly once, in array order.  Exceptions
 * thrown by the disposer are NOT caught — the caller is expected to
 * handle errors.
 */
export function disposeAll(
  adapters: ReadonlyArray<HostFamilyAdapter>,
  dispose: (adapter: HostFamilyAdapter) => void,
): void {
  for (const adapter of adapters) {
    if (adapter !== null) {
      dispose(adapter);
    }
  }
}

// ---------------------------------------------------------------------------
// Capability projection
// ---------------------------------------------------------------------------

/**
 * Project the maturity capability posture for every kind registered
 * in a {@link FamilyAdapterRegistry}.
 *
 * The projection maps each registered kind to its effective execution
 * maturity:
 * - Real adapters use their manifest maturity (possibly overridden at
 *   registration time).
 * - `null` entries are projected as `'delegated'`.
 *
 * Kinds not in the registry are excluded from the projection.
 *
 * @returns A frozen `ReadonlyMap<string, ExecutionMaturity>` keyed by
 *          contribution kind.
 */
export function projectMaturityCapabilities(
  registry: FamilyAdapterRegistry,
): ReadonlyMap<string, ExecutionMaturity> {
  const projection = new Map<string, ExecutionMaturity>();
  for (const [kind, adapter] of registry) {
    if (adapter === null) {
      projection.set(kind, 'delegated');
    } else {
      projection.set(kind, adapter.manifest.maturity);
    }
  }
  return projection;
}

// ---------------------------------------------------------------------------
// Lookup helpers
// ---------------------------------------------------------------------------

/**
 * Look up an adapter in a registry by contribution kind.
 *
 * This is a thin pass-through over `Map.get()`, provided for
 * convenience when working with the `FamilyAdapterRegistry` type
 * directly.
 *
 * @returns The adapter, `null` for known-unavailable families, or
 *          `undefined` when the kind has never been registered.
 */
export function findAdapter(
  registry: FamilyAdapterRegistry,
  kind: string,
): HostFamilyAdapter | null | undefined {
  return registry.get(kind);
}

/**
 * Return all contribution kinds currently present in the registry,
 * sorted alphabetically for deterministic iteration.
 */
export function listRegisteredKinds(
  registry: FamilyAdapterRegistry,
): string[] {
  return [...registry.keys()].sort();
}
