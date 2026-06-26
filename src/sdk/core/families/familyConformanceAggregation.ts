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
} from './conformance';
import { buildConformanceReport } from './conformance';
import type { FamilyAdapterRegistry } from './familyAdapter';

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
  registryEntry: HostFamilyAdapterOrNull | undefined,
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

  // Delegated-gap: registry has null but maturity is runtime-bridged or higher
  if (
    registryEntry === null &&
    maturityExpectsAdapter
  ) {
    gaps.push({
      category: 'host-adapter-missing',
      message:
        `Kind "${definition.kind}" is registered as known-unavailable ` +
        `(null adapter) but execution maturity is ` +
        `"${definition.executionMaturity}", which requires a real adapter.`,
      metadata: {
        kind: definition.kind,
        delegatedKind: true,
        executionMaturity: definition.executionMaturity,
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

  return maturityExpectsAdapter;
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

import type { HostFamilyAdapter } from './familyAdapter';

/** A registry entry or `undefined` when not registered. */
type HostFamilyAdapterOrNull = HostFamilyAdapter | null | undefined;
