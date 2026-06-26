/**
 * Family bridging utilities for the public SDK surface.
 *
 * Thin wrappers around the canonical video family registry that answer
 * contribution-kind bridging questions without exposing raw registry
 * internals to consuming extensions.
 *
 * M2b extraction: moved from inline in src/sdk/index.ts.
 *
 * @publicContract
 */

import type { ContributionKind } from './manifest';
import {
  VIDEO_FAMILY_LEGACY_MILESTONE_MAP,
  getVideoFamily,
  buildVideoFamilyReport,
} from '@/sdk/video/families/familyDefinitions';
import type { FamilyDefinition, ExecutionMaturity } from '@/sdk/core/families/maturity';
import type { FamilyConformanceReport } from '@/sdk/core/families/conformance';

// ---------------------------------------------------------------------------
// Milestone map
// ---------------------------------------------------------------------------

/**
 * The earliest milestone that activates each contribution kind.
 *
 * Derived from the canonical video family registry
 * (`VIDEO_FAMILY_REGISTRY` in `src/sdk/video/families/familyDefinitions.ts`).
 * Any kind not in the registry is treated as not-yet-bridged.
 */
export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> =
  VIDEO_FAMILY_LEGACY_MILESTONE_MAP as Record<ContributionKind, string | undefined>;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Execution maturity levels considered "bridged" (runtime behavior exists).
 * `delegated` and `absent` are NOT bridged — they lack real host adapter behavior.
 */
const BRIDGED_EXECUTION_MATURITIES: ReadonlySet<ExecutionMaturity> = new Set<ExecutionMaturity>([
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

// ---------------------------------------------------------------------------
// Public bridging functions
// ---------------------------------------------------------------------------

/**
 * Check whether a contribution kind is bridged in the current runtime.
 *
 * Derived from the canonical video family registry — a kind is considered
 * bridged when its `executionMaturity` is `runtime-bridged`, `host-integrated`,
 * or `public-supported`.  Kinds with `delegated` or `absent` execution maturity
 * are NOT bridged.
 *
 * Returns the milestone name if NOT bridged, or null if it is bridged.
 */
export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const def = getVideoFamily(kind);
  if (!def) {
    const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
    return milestone || 'unknown';
  }

  if (BRIDGED_EXECUTION_MATURITIES.has(def.executionMaturity)) {
    return null;
  }

  return def.legacyMilestone ?? CONTRIBUTION_KIND_MILESTONE[kind] ?? 'unknown';
}

/**
 * Look up the canonical family definition for a contribution kind.
 * Returns `undefined` when the kind is not in the family registry.
 */
export function getVideoFamilyDefinition(
  kind: ContributionKind,
): FamilyDefinition<ContributionKind> | undefined {
  return getVideoFamily(kind) as FamilyDefinition<ContributionKind> | undefined;
}

/**
 * Build a conformance report for a contribution kind from the family registry.
 * Returns `undefined` when the kind is not in the registry.
 */
export function getVideoFamilyConformanceReport(
  kind: ContributionKind,
): FamilyConformanceReport<ContributionKind> | undefined {
  return buildVideoFamilyReport(kind) as FamilyConformanceReport<ContributionKind> | undefined;
}

/**
 * Report the legacy bridge status for a contribution kind.
 *
 * Returns:
 * - `null` when the kind is bridged (execution maturity ≥ runtime-bridged).
 * - The milestone string (e.g. `'M6'`) when the kind is NOT bridged.
 * - `'unknown'` when the kind is not in the registry and has no milestone entry.
 */
export function getVideoFamilyLegacyBridgeStatus(kind: ContributionKind): string | null {
  return contributionKindNotYetBridged(kind);
}
