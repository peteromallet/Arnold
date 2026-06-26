/**
 * Host family adapter contracts — type-only interfaces for adapter
 * registration, manifest metadata, and adapter registry shape.
 *
 * These types are pure contracts. No runtime implementation or host
 * runtime imports (editor internals, DataProvider, timeline ops, etc.).
 * Downstream tasks (T4 registry, T6 metadataFacet adapter, T10 slot-like
 * adapters) implement against these contracts.
 *
 * @module families/familyAdapter
 * @publicContract
 */

import type { ExecutionMaturity } from './maturity';
import type { ExtensionDiagnostic } from '../../diagnostics';
import type { FamilyConformanceReport } from './conformance';

// ---------------------------------------------------------------------------
// Adapter input/output contracts
// ---------------------------------------------------------------------------

/**
 * A single contribution paired with its owning extension ID.
 *
 * This is the canonical input unit for adapter normalization.  It is
 * intentionally plain data — no host runtime imports.
 */
export interface FamilyContributionRef<TContribution = unknown> {
  /** The original contribution value (family-specific shape). */
  readonly contribution: TContribution;

  /** The ID of the extension that declared this contribution. */
  readonly extensionId: string;
}

/**
 * Input to a host family adapter's normalization pass.
 */
export interface NormalizeFamilyInput<TContribution = unknown> {
  /** Sorted contributions ready for projection. */
  readonly contributions: readonly FamilyContributionRef<TContribution>[];

  /**
   * Optional extension order map (extensionId → insertion index).
   *
   * Adapters that need deterministic re-sorting can use this map.  When
   * omitted, adapters should preserve the order of `contributions`.
   */
  readonly extensionOrder?: ReadonlyMap<string, number>;
}

/**
 * Result of a host family adapter's normalization pass.
 *
 * Adapters may optionally return diagnostics (e.g. validation warnings)
 * alongside the projected descriptors.
 */
export interface FamilyNormalizeResult<TDescriptor = unknown> {
  /** Projected, frozen descriptors. */
  readonly descriptors: readonly TDescriptor[];

  /** Optional diagnostics emitted during normalization. */
  readonly diagnostics?: readonly ExtensionDiagnostic[];
}

/**
 * Input to a host family adapter capability query.
 *
 * Kept as a plain-data contract so callers can ask an adapter what
 * execution capabilities it provides without passing host runtime state.
 */
export interface FamilyCapabilityInput {
  /** The contribution kind being queried. */
  readonly kind: string;
}

// ---------------------------------------------------------------------------
// Adapter manifest
// ---------------------------------------------------------------------------

/**
 * Metadata for a registered host family adapter.
 *
 * Describes the adapter's identity, the kind it services, its maturity
 * level, and an optional human-readable description.
 */
export interface HostAdapterManifest {
  /** Unique adapter identifier (e.g. `'metadataFacet-default'`). */
  readonly adapterId: string;

  /** Contribution kind this adapter services. */
  readonly kind: string;

  /** Semver adapter version. */
  readonly version: string;

  /** Execution maturity this adapter provides. */
  readonly maturity: ExecutionMaturity;

  /** Optional human-readable description of the adapter's scope. */
  readonly description?: string;

  /**
   * Optional free-form metadata for registry consumers (e.g. delegation
   * owner/reason/expiration, provenance, or audit tags).
   */
  readonly metadata?: Readonly<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Host family adapter contract
// ---------------------------------------------------------------------------

/**
 * Core host family adapter contract.
 *
 * Every host adapter (real or placeholder) must satisfy this interface.
 * This is a type-only contract — no runtime methods are mandated here
 * because normalization, lifecycle, diagnostics, and projection are
 * family-specific.  Concrete adapters extend or implement a narrower
 * per-family shape derived from this contract.
 *
 * @typeParam Kind   — The contribution kind this adapter services.
 * @typeParam TContribution — The contribution shape for this family
 *                    (e.g. `MetadataFacetContribution`).
 */
export interface HostFamilyAdapter<
  Kind extends string = string,
  TContribution = unknown,
  TDescriptor = unknown,
> {
  /** Contribution kind this adapter handles. */
  readonly kind: Kind;

  /** Adapter classification: real independent adapter or delegated placeholder. */
  readonly classification: 'real' | 'placeholder';

  /** Adapter manifest metadata. */
  readonly manifest: HostAdapterManifest;

  /**
   * Normalize a batch of contributions into projected descriptors.
   *
   * The input contributions are assumed to be sorted in canonical order
   * (extension order → contribution.order → contribution.id).  The adapter
   * must not mutate the input.
   */
  normalize(
    input: NormalizeFamilyInput<TContribution>,
  ): FamilyNormalizeResult<TDescriptor>;

  /**
   * Build a conformance report for this adapter's family.
   *
   * Real adapters usually read the canonical SDK family definition.
   * Placeholder adapters may additionally annotate delegated gaps.
   */
  buildConformanceReport(): FamilyConformanceReport<Kind>;
}

// ---------------------------------------------------------------------------
// Adapter registry shape
// ---------------------------------------------------------------------------

/**
 * Read-only mapping from contribution kind to its registered adapter.
 *
 * `null` entries represent known-but-unavailable families (e.g. families
 * whose execution maturity is `absent` or whose adapter has not been
 * registered yet).  `undefined` means the kind was never registered.
 */
export type FamilyAdapterRegistry = ReadonlyMap<string, HostFamilyAdapter | null>;

// ---------------------------------------------------------------------------
// Adapter registration descriptor
// ---------------------------------------------------------------------------

/**
 * Descriptor used to register a host adapter into the registry.
 *
 * The registry accepts these descriptors and derives `HostAdapterManifest`
 * from them before storing the adapter.
 */
export interface HostAdapterRegistrationDescriptor<
  Kind extends string = string,
  TContribution = unknown,
> {
  /** The adapter instance (or `null` for a known-unavailable family). */
  readonly adapter: HostFamilyAdapter<Kind, TContribution> | null;

  /** Optional override for the adapter's effective maturity. */
  readonly overrideMaturity?: ExecutionMaturity;

  /** Optional free-form metadata for registry consumers. */
  readonly metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Passive adapter registry implementation
// ---------------------------------------------------------------------------

/**
 * A passive, in-memory host family adapter registry.
 *
 * Stores adapters keyed by contribution kind and exposes lookup-only
 * methods: `get`, `require`, and `kinds`.  The registry itself is
 * intentionally passive — it has no host runtime imports, no side
 * effects, and no lifecycle hooks.  Registration is explicit via
 * `register()`.
 *
 * A frozen `ReadonlyMap` snapshot is available via `snapshot()` and
 * conforms to the {@link FamilyAdapterRegistry} type contract.
 */
export class FamilyAdapterRegistryImpl {
  private readonly _map: Map<string, HostFamilyAdapter | null>;

  constructor(
    entries?: ReadonlyArray<readonly [string, HostFamilyAdapter | null]>,
  ) {
    this._map = new Map(entries ?? []);
  }

  // -----------------------------------------------------------------------
  // Lookup
  // -----------------------------------------------------------------------

  /**
   * Look up an adapter by contribution kind.
   *
   * @returns The adapter, `null` for known-unavailable families, or
   *          `undefined` when the kind has never been registered.
   */
  get(kind: string): HostFamilyAdapter | null | undefined {
    if (!this._map.has(kind)) return undefined;
    return this._map.get(kind)!;
  }

  /**
   * Look up an adapter by contribution kind, throwing if the kind
   * was never registered.
   *
   * @returns The adapter, or `null` for known-unavailable families.
   * @throws Error when the kind is not in the registry.
   */
  require(kind: string): HostFamilyAdapter | null {
    if (!this._map.has(kind)) {
      throw new Error(
        `FamilyAdapterRegistry: kind "${kind}" is not registered.`,
      );
    }
    return this._map.get(kind)!;
  }

  /**
   * Return all contribution kinds currently registered in the adapter
   * registry, sorted alphabetically for deterministic iteration.
   */
  kinds(): string[] {
    return [...this._map.keys()].sort();
  }

  // -----------------------------------------------------------------------
  // Mutation
  // -----------------------------------------------------------------------

  /**
   * Register an adapter from a {@link HostAdapterRegistrationDescriptor}.
   *
   * If `overrideMaturity` is provided on the descriptor and the adapter
   * is non-null, the adapter's manifest maturity is replaced with the
   * override value before storage.  The original adapter object is NOT
   * mutated — a shallow copy is stored.
   *
   * Registering `null` marks the kind as known-but-unavailable.
   */
  register(
    descriptor: HostAdapterRegistrationDescriptor,
  ): void {
    const { adapter, overrideMaturity } = descriptor;

    if (adapter === null) {
      // For a null adapter the kind must come from descriptor metadata
      // because the adapter itself carries no kind information.
      const kindFromMeta =
        descriptor.metadata?.kind as string | undefined;
      if (kindFromMeta) {
        this._map.set(kindFromMeta, null);
      }
      return;
    }

    const kind = adapter.kind;

    if (overrideMaturity) {
      const adapted: HostFamilyAdapter = {
        ...adapter,
        manifest: { ...adapter.manifest, maturity: overrideMaturity },
      };
      this._map.set(kind, adapted);
    } else {
      this._map.set(kind, adapter);
    }
  }

  // -----------------------------------------------------------------------
  // Snapshot
  // -----------------------------------------------------------------------

  /**
   * Return a frozen `ReadonlyMap` snapshot of the current registry state.
   *
   * The snapshot conforms to the {@link FamilyAdapterRegistry} type
   * contract and is safe for consumers that need a read-only view.
   */
  snapshot(): FamilyAdapterRegistry {
    return new Map(this._map) as FamilyAdapterRegistry;
  }

  /**
   * The number of registered kinds (including known-unavailable entries).
   */
  get size(): number {
    return this._map.size;
  }
}
