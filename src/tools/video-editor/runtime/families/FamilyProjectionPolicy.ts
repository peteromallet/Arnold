/**
 * Family projection policy — compatibility boundary between SDK maturity
 * and runtime descriptor surfacing.
 *
 * This module replaces direct calls to `getVideoFamilyLegacyBridgeStatus`
 * with a policy that can consult either the adapter registry (for families
 * with real or placeholder adapters) or fall back to the legacy bridge
 * status (for families not yet adapted).
 *
 * The policy guarantees that runtime descriptor output remains stable
 * during the transition from SDK maturity gating to adapter-owned
 * projection.  Delegated-but-projectable families (outputFormat,
 * searchProvider, process) continue to surface descriptors even though
 * their SDK maturity is `delegated`.
 *
 * @module families/FamilyProjectionPolicy
 */

import type { ContributionKind } from '@reigh/editor-sdk';
import {
  getVideoFamilyDefinition,
  getVideoFamilyLegacyBridgeStatus,
} from '@reigh/editor-sdk';
import type { FamilyAdapterRegistry } from '@/sdk/core/families/familyAdapter';

// ---------------------------------------------------------------------------
// Projection status
// ---------------------------------------------------------------------------

/**
 * The projection posture for a single family kind.
 *
 * This is the single source of truth for whether a family kind's
 * contributions should produce runtime descriptors.  Every consumer
 * that previously branched on `getVideoFamilyLegacyBridgeStatus`
 * should instead branch on `ProjectionStatus`.
 */
export interface ProjectionStatus {
  /** The contribution kind this status describes. */
  readonly kind: ContributionKind;

  /**
   * Whether contributions of this kind should be surfaced as runtime
   * descriptors (i.e. projected into `VideoEditorExtensionRuntimeConfig`).
   *
   * - `true`  → contributions produce descriptors.
   * - `false` → contributions are suppressed (absent execution maturity
   *              with no adapter and no reserved-surfacing path).
   */
  readonly shouldSurface: boolean;

  /**
   * Whether this family is delegated (placeholder adapter or SDK
   * `delegated` execution maturity).  Delegated families that still
   * surface produce conformance gaps.
   */
  readonly isDelegated: boolean;

  /**
   * Legacy milestone string (e.g. `'M6'`, `'M12'`) when the family
   * is not yet runtime-bridged and has no owning adapter.
   *
   * `null` when the family IS runtime-bridged or is owned by an
   * adapter with maturity ≥ `runtime-bridged`.
   */
  readonly legacyBridgeStatus: string | null;

  /**
   * Whether an adapter (real or placeholder/null) is registered
   * for this family kind and therefore owns the projection decision.
   *
   * When `true`, the adapter's maturity determines `shouldSurface`;
   * the legacy bridge status is ignored.
   */
  readonly adapterOwned: boolean;

  /**
   * Execution maturity from the family definition or adapter.
   * Used by downstream consumers that need the raw maturity level.
   */
  readonly executionMaturity: string | undefined;
}

// ---------------------------------------------------------------------------
// Policy evaluation
// ---------------------------------------------------------------------------

/**
 * Execution maturity levels that are considered "active" — contributions
 * should produce runtime descriptors.
 */
const SURFACING_MATURITIES: ReadonlySet<string> = new Set([
  'delegated',
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

/**
 * Evaluate the projection policy for a single contribution kind.
 *
 * Resolution order:
 * 1. If an adapter is registered for `kind` (real or null placeholder),
 *    the adapter owns the decision.  `shouldSurface` is `true` for
 *    all maturity levels except `absent`.
 * 2. If no adapter is registered, fall back to the legacy bridge status
 *    via the SDK family registry.
 *
 * This function is intentionally pure — it reads from the provided
 * registry and the SDK family definitions without mutating anything.
 *
 * @param kind          - The contribution kind to evaluate.
 * @param adapterRegistry - Optional adapter registry.  When omitted,
 *                          the policy falls back to the SDK legacy bridge
 *                          status exclusively.
 * @returns A frozen {@link ProjectionStatus} describing the kind's
 *          projection posture.
 */
export function evaluateProjectionPolicy(
  kind: ContributionKind,
  adapterRegistry?: FamilyAdapterRegistry,
): ProjectionStatus {
  // ── Step 1: check adapter registry ─────────────────────────────────
  if (adapterRegistry !== undefined && adapterRegistry.has(kind)) {
    const adapter = adapterRegistry.get(kind)!; // null or HostFamilyAdapter

    if (adapter === null) {
      // Null placeholder adapter — the family is known but unavailable.
      // A null adapter means delegated projection with a conformance gap.
      // Contributions should still surface (delegated-but-projectable).
      return Object.freeze({
        kind,
        shouldSurface: true,
        isDelegated: true,
        legacyBridgeStatus: null,
        adapterOwned: true,
        executionMaturity: 'delegated',
      });
    }

    // Real adapter — use its manifest maturity.
    const maturity = adapter.manifest.maturity;
    const shouldSurface = SURFACING_MATURITIES.has(maturity);
    return Object.freeze({
      kind,
      shouldSurface,
      isDelegated: maturity === 'delegated',
      // Adapter-owned surfacing families are treated as bridged for
      // sequencing purposes, even when the SDK maturity is delegated.
      legacyBridgeStatus: shouldSurface ? null : undefined,
      adapterOwned: true,
      executionMaturity: maturity,
    });
  }

  // ── Step 2: fall back to SDK family registry ────────────────────────
  const family = getVideoFamilyDefinition(kind);
  const executionMaturity = family?.executionMaturity;
  const legacyBridgeStatus = getVideoFamilyLegacyBridgeStatus(kind);

  // `absent` families: no runtime behavior, should not surface.
  if (executionMaturity === 'absent') {
    return Object.freeze({
      kind,
      shouldSurface: false,
      isDelegated: false,
      legacyBridgeStatus,
      adapterOwned: false,
      executionMaturity,
    });
  }

  // All other maturity levels surface (delegated, runtime-bridged,
  // host-integrated, public-supported).  Even delegated families
  // surface — they are "delegated-but-projectable" (outputFormat,
  // searchProvider, process).
  return Object.freeze({
    kind,
    shouldSurface: executionMaturity !== undefined,
    isDelegated: executionMaturity === 'delegated',
    legacyBridgeStatus,
    adapterOwned: false,
    executionMaturity,
  });
}

// ---------------------------------------------------------------------------
// Convenience: contribution runtime status
// ---------------------------------------------------------------------------

/**
 * Legacy-compatible contribution runtime status, mirroring the shape
 * previously produced by `getContributionRuntimeStatus` in
 * `FamilyContributionSequence.ts`.
 *
 * New code should prefer {@link evaluateProjectionPolicy} directly.
 * This helper exists to minimize the diff during the transition.
 */
export interface ContributionRuntimeStatus {
  readonly legacyBridgeStatus: string | null;
  readonly isDelegated: boolean;
}

/**
 * Evaluate the projection policy and return a legacy-compatible
 * {@link ContributionRuntimeStatus}.
 *
 * This is a thin wrapper around {@link evaluateProjectionPolicy} that
 * extracts only the fields previously used by the contribution
 * sequencing pipeline.
 */
export function getContributionRuntimeStatus(
  kind: ContributionKind,
  adapterRegistry?: FamilyAdapterRegistry,
): ContributionRuntimeStatus {
  const status = evaluateProjectionPolicy(kind, adapterRegistry);
  return {
    legacyBridgeStatus: status.legacyBridgeStatus,
    isDelegated: status.isDelegated,
  };
}
