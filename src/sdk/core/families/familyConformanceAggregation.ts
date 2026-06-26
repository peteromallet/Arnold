/**
 * Family conformance aggregation — host-side report aggregation and
 * delegated-gap validation.
 *
 * This module builds on {@link FamilyConformanceReport} and the
 * adapter registry to produce host-level conformance views.  It does
 * NOT import host runtime code (editor internals, DataProvider,
 * timeline ops, etc.).
 *
 * @module families/familyConformanceAggregation
 * @publicContract
 */

import type { FamilyDefinition } from './maturity';
import type { ExecutionMaturity } from './maturity';
import type {
  FamilyConformanceReport,
  ConformanceGap,
  ConformanceGapCategory,
} from './conformance';
import { buildConformanceReport } from './conformance';
import type { FamilyAdapterRegistry, HostFamilyAdapter } from './familyAdapter';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A registry entry or `undefined` when not registered. */
type HostFamilyAdapterOrNull = HostFamilyAdapter | null | undefined;

// ---------------------------------------------------------------------------
// Host-level report aggregation
// ---------------------------------------------------------------------------

/**
 * Build a conformance report for every family definition and annotate
 * gaps with host-adapter registry context.
 *
 * For each family definition the function:
 * 1. Builds a base {@link FamilyConformanceReport} via
 *    {@link buildConformanceReport}.
 * 2. Checks the adapter registry for a registered adapter.
 * 3. Adds `host-adapter-missing` gaps when execution maturity expects
 *    an adapter but the registry has `null` or `undefined` for that kind.
 * 4. Adds `delegated-gap` annotations when the registry has a `null`
 *    entry (known-unavailable) and execution maturity is at least
 *    `runtime-bridged`.
 *
 * @param definitions  — Family definitions to aggregate.
 * @param registry     — Adapter registry to validate against.
 * @returns An array of {@link FamilyConformanceReport} instances, one per
 *          definition, with registry-annotated gaps.
 */
export function aggregateHostConformance(
  definitions: ReadonlyArray<FamilyDefinition>,
  registry: FamilyAdapterRegistry,
): FamilyConformanceReport[] {
  const reports: FamilyConformanceReport[] = [];

  for (const definition of definitions) {
    const baseReport = buildConformanceReport(definition);
    const registryEntry = registry.get(definition.kind);

    // Collect additional registry-derived gaps
    const registryGaps = computeRegistryGaps(definition, registryEntry);

    // Merge registry gaps into the base report
    const mergedGaps: ConformanceGap[] = [
      ...baseReport.gaps,
      ...registryGaps,
    ];

    reports.push({
      ...baseReport,
      gaps: mergedGaps,
    });
  }

  return reports;
}

// ---------------------------------------------------------------------------
// Delegated conformance gap (release-mode)
// ---------------------------------------------------------------------------

/**
 * Release-mode delegated conformance gap.
 *
 * Unlike base {@link ConformanceGap} whose `owner`, `reason`, and
 * `expiration` are optional, a `DelegatedConformanceGap` carries
 * **required** delegation metadata:
 * - `owner`      — Team or system responsible for the delegated family.
 * - `reason`     — Why this family is delegated.
 * - `expiration` — ISO-8601 date when the delegated posture must be
 *                  resolved, or `'never'` for indefinitely deferred.
 *
 * This type is used by host-side conformance aggregation to enforce
 * release-mode traceability for every delegated family gap.  Base SDK
 * gaps (from {@link buildConformanceReport}) keep metadata optional.
 */
export interface DelegatedConformanceGap extends ConformanceGap {
  readonly category: ConformanceGapCategory;
  readonly message: string;
  readonly owner: string;
  readonly reason: string;
  readonly expiration: string;
  readonly metadata: {
    /** The contribution kind. */
    readonly kind: string;
    /** Marker indicating this is a delegated kind gap. */
    readonly delegatedKind: true;
    /** The execution maturity that triggered this gap. */
    readonly executionMaturity: ExecutionMaturity;
    /** Registry status at time of aggregation. */
    readonly registryStatus: string;
  };
}

// ---------------------------------------------------------------------------
// Registry gap computation
// ---------------------------------------------------------------------------

/**
 * Compute gaps derived from the adapter registry for a single family.
 *
 * @param definition   — The family definition to check.
 * @param registryEntry — The registry entry for this family's kind
 *                        (adapter, null, or undefined).
 * @returns An array of registry-derived {@link ConformanceGap} entries.
 */
function computeRegistryGaps(
  definition: FamilyDefinition,
  registryEntry: HostFamilyAdapterOrNull,
): ConformanceGap[] {
  const gaps: ConformanceGap[] = [];

  // Host-adapter-missing: execution maturity expects an adapter but
  // the registry has no real adapter.
  const maturityExpectsAdapter =
    definition.executionMaturity !== 'absent' &&
    definition.executionMaturity !== 'delegated';

  if (maturityExpectsAdapter && !registryEntry) {
    gaps.push({
      category: 'host-adapter-missing',
      message:
        `Execution maturity "${definition.executionMaturity}" expects ` +
        `a host adapter for kind "${definition.kind}", but the registry ` +
        `has ${registryEntry === null ? 'a null (known-unavailable) entry' : 'no entry'}.`,
      metadata: {
        kind: definition.kind,
        executionMaturity: definition.executionMaturity,
        registryStatus: registryEntry === null ? 'null' : 'unregistered',
      },
    });
  }

  // Delegated-gap: registry has null but maturity is runtime-bridged or higher.
  // Release-mode: must include owner, reason, and expiration.
  if (registryEntry === null && maturityExpectsAdapter) {
    const defRec = definition as unknown as Record<string, unknown>;
    const owner =
      (defRec.delegatedOwner as string | undefined) ?? 'video-editor-runtime';
    const reason =
      (defRec.delegatedReason as string | undefined) ??
      `Kind "${definition.kind}" has a null (known-unavailable) adapter entry ` +
      `but execution maturity "${definition.executionMaturity}" expects a real adapter.`;
    const expiration =
      (defRec.delegatedExpiration as string | undefined) ?? 'M4';

    gaps.push({
      category: 'host-adapter-missing',
      owner,
      reason,
      expiration,
      message:
        `Kind "${definition.kind}" is registered as known-unavailable ` +
        `(null adapter) but execution maturity is ` +
        `"${definition.executionMaturity}", which requires a real adapter.`,
      metadata: {
        kind: definition.kind,
        delegatedKind: true as const,
        executionMaturity: definition.executionMaturity,
        registryStatus: 'null',
      },
    });
  }

  return gaps;
}

// ---------------------------------------------------------------------------
// Delegated-gap validation
// ---------------------------------------------------------------------------

/**
 * Validate whether a {@link ConformanceGap} is a legitimate delegated gap.
 *
 * A delegated gap is valid when:
 * - The gap's metadata includes `delegatedKind: true`.
 * - The adapter registry has a `null` entry for that kind (known-unavailable).
 * - The family's execution maturity is at least `runtime-bridged`.
 * - **Release-mode enforcement**: the gap includes non-empty `owner`,
 *   `reason`, and `expiration` strings.  These are required by
 *   {@link DelegatedConformanceGap} for host-side aggregation.
 *
 * Base SDK gaps (from {@link buildConformanceReport}) with optional
 * metadata are not validated against the owner/reason/expiration
 * requirement — only host-aggregated delegated gaps carry these.
 *
 * @param gap      — The gap to validate.
 * @param registry — The adapter registry to cross-reference.
 * @returns `true` when the gap is a valid delegated gap.
 */
export function isValidDelegatedGap(
  gap: ConformanceGap,
  registry: FamilyAdapterRegistry,
): boolean {
  // Must have metadata indicating it's a delegated kind
  if (!gap.metadata?.delegatedKind) {
    return false;
  }

  const kind = gap.metadata.kind as string | undefined;
  if (!kind) {
    return false;
  }

  // Registry must have a null entry for this kind
  const registryEntry = registry.get(kind);
  if (registryEntry !== null) {
    return false;
  }

  // Execution maturity from metadata must be runtime-bridged or higher
  const executionMaturity = gap.metadata.executionMaturity as
    | ExecutionMaturity
    | undefined;
  if (!executionMaturity) {
    return false;
  }

  const maturityExpectsAdapter =
    executionMaturity !== 'absent' &&
    executionMaturity !== 'delegated';

  if (!maturityExpectsAdapter) {
    return false;
  }

  // ── Release-mode enforcement ──────────────────────────────────────────
  // Host-aggregated delegated gaps MUST carry owner, reason, and expiration.
  // Base SDK gaps (with optional metadata) skip this check:
  // owner/reason/expiration are only required on host-side aggregation,
  // not on base ConformanceGap instances from buildConformanceReport.
  const metadata = gap.metadata;
  if (metadata.registryStatus === 'null') {
    // This is a host-aggregated gap — enforce release-mode metadata.
    const owner = gap.owner;
    const reason = gap.reason;
    const expiration = gap.expiration;

    if (!owner || owner.length === 0) return false;
    if (!reason || reason.length === 0) return false;
    if (!expiration || expiration.length === 0) return false;
  }
  // For non-host-aggregated gaps (registryStatus !== 'null'), the
  // owner/reason/expiration fields are optional (base SDK contract).

  return true;
}

// ---------------------------------------------------------------------------
// Delegated-family identification
// ---------------------------------------------------------------------------

/**
 * Identify all contribution kinds that are registered as
 * known-unavailable (null adapter) in the registry.
 *
 * @param registry — The adapter registry to scan.
 * @returns An alphabetically sorted array of kind strings for
 *          delegated families.
 */
export function identifyDelegatedFamilies(
  registry: FamilyAdapterRegistry,
): string[] {
  const delegated: string[] = [];
  for (const [kind, adapter] of registry) {
    if (adapter === null) {
      delegated.push(kind);
    }
  }
  delegated.sort();
  return delegated;
}
