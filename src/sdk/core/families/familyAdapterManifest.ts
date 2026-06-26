/**
 * Family adapter manifest — cross-reference checklist mapping every
 * family kind to its adapter, projector, test, conformance gap, and
 * maturity status.
 *
 * This module derives its data from the canonical
 * `VIDEO_FAMILY_REGISTRY` and produces a manifest that can be
 * validated against the adapter registry and runtime labels.
 *
 * @module families/familyAdapterManifest
 * @publicContract
 */

import type {
  DeclarationMaturity,
  ExecutionMaturity,
  FamilyDefinition,
  FamilyRequirementChecklist,
} from './maturity';
import type { ConformanceGap } from './conformance';
import { computeGaps } from './conformance';
import type { FamilyAdapterRegistry } from './familyAdapter';
import { VIDEO_FAMILY_REGISTRY } from '../../video/families/familyDefinitions';
import type { VideoContributionKind } from '../../video/families/contributionKinds';
import { VIDEO_CONTRIBUTION_KINDS } from '../../video/families/contributionKinds';

// ---------------------------------------------------------------------------
// Manifest entry
// ---------------------------------------------------------------------------

/**
 * A single entry in the family adapter manifest.
 *
 * Each entry captures the canonical posture for one contribution kind:
 * adapter path, projector module, test module, conformance gaps,
 * maturity levels, and whether a real adapter is expected.
 */
export interface FamilyAdapterManifestEntry {
  /** Contribution kind (e.g. `'effect'`, `'slot'`). */
  readonly kind: string;

  /** Human-readable label (e.g. `'Effect'`, `'Slot'`). */
  readonly label: string;

  /** Declaration maturity from the family registry. */
  readonly declarationMaturity: DeclarationMaturity;

  /** Execution maturity from the family registry. */
  readonly executionMaturity: ExecutionMaturity;

  /** Host adapter path from the family registry (may be `null`). */
  readonly hostAdapter: string | null;

  /** Whether a real (non-null) host adapter is expected at this maturity. */
  readonly expectsRealAdapter: boolean;

  /** Whether the family is fully conformant (no requirement gaps). */
  readonly isFullyConformant: boolean;

  /** Requirement checklist from the registry. */
  readonly requirements: FamilyRequirementChecklist;

  /** Conformance gaps derived from the family definition. */
  readonly gaps: readonly ConformanceGap[];

  /** Legacy milestone (e.g. `'M1'`, `'M7'`). */
  readonly legacyMilestone: string;

  /** SDK modules that define this family. */
  readonly sdkModules: readonly string[];

  /** Manifest schema definition name (e.g. `'EffectContribution'`). */
  readonly manifestSchemaDefinition: string;
}

// ---------------------------------------------------------------------------
// Manifest
// ---------------------------------------------------------------------------

/**
 * A read-only cross-reference manifest mapping every runtime family
 * kind to its adapter, projector, test, gap, and maturity status.
 *
 * The manifest is built from the canonical
 * {@link VIDEO_FAMILY_REGISTRY} and can be validated against the
 * adapter registry to detect missing adapters, mismatched maturity,
 * and stale host adapter paths.
 */
export interface FamilyAdapterManifest {
  /** All entries, sorted by kind ascending. */
  readonly entries: readonly FamilyAdapterManifestEntry[];

  /** Number of families in the manifest. */
  readonly size: number;

  /** All contribution kinds in the manifest (sorted). */
  readonly kinds: readonly string[];

  /** Look up a manifest entry by kind. Returns `undefined` when the
   *  kind is not in the manifest. */
  getEntry(kind: string): FamilyAdapterManifestEntry | undefined;
}

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------

/**
 * Build a {@link FamilyAdapterManifest} from the canonical video
 * family registry.
 *
 * Every family in {@link VIDEO_FAMILY_REGISTRY} produces exactly one
 * manifest entry.  The manifest is a pure projection of registry data
 * — it performs no host runtime checks and imports no editor internals.
 */
export function buildFamilyAdapterManifest(): FamilyAdapterManifest {
  const entries: FamilyAdapterManifestEntry[] = [];

  for (const def of VIDEO_FAMILY_REGISTRY as readonly FamilyDefinition<VideoContributionKind>[]) {
    const expectsRealAdapter =
      def.executionMaturity !== 'absent' &&
      def.executionMaturity !== 'delegated';

    const gaps = computeGaps(def);

    const entry: FamilyAdapterManifestEntry = {
      kind: def.kind,
      label: def.label ?? def.kind,
      declarationMaturity: def.declarationMaturity,
      executionMaturity: def.executionMaturity,
      hostAdapter: def.hostAdapter ?? null,
      expectsRealAdapter,
      isFullyConformant: gaps.length === 0,
      requirements: { ...def.requirements },
      gaps,
      legacyMilestone: def.legacyMilestone ?? '',
      sdkModules: [...(def.sdkModules ?? [])],
      manifestSchemaDefinition: def.manifestSchemaDefinition ?? '',
    };

    entries.push(entry);
  }

  // Sort by kind ascending (matches registry order)
  entries.sort((a, b) => a.kind.localeCompare(b.kind));

  const storedEntries: readonly FamilyAdapterManifestEntry[] = entries;
  const kinds: readonly string[] = entries.map((e) => e.kind);

  return {
    entries: storedEntries,
    size: entries.length,
    kinds,
    getEntry(kind: string): FamilyAdapterManifestEntry | undefined {
      return entries.find((e) => e.kind === kind);
    },
  };
}

// ---------------------------------------------------------------------------
// Cross-reference validation
// ---------------------------------------------------------------------------

/**
 * Result of cross-referencing the manifest against the adapter registry
 * and contribution kinds authority.
 */
export interface ManifestCrossReferenceResult {
  /** Kinds in the manifest but missing from the adapter registry. */
  readonly missingFromRegistry: readonly string[];

  /** Kinds in the adapter registry but missing from the manifest. */
  readonly missingFromManifest: readonly string[];

  /** Kinds in the manifest that expect a real adapter but have `null`
   *  (or are missing) in the registry. */
  readonly kindsNeedingAdapter: readonly string[];

  /** Kinds that exist in both manifest and registry with matching adapter. */
  readonly kindsWithAdapter: readonly string[];

  /** Kinds in {@link VIDEO_CONTRIBUTION_KINDS} but not in the manifest. */
  readonly contributionKindsNotInManifest: readonly string[];

  /** Kinds in the manifest but not in {@link VIDEO_CONTRIBUTION_KINDS}. */
  readonly manifestKindsNotInContributionKinds: readonly string[];

  /** Whether the manifest, registry, and contribution kinds are fully
   *  aligned (no missing entries in any direction). */
  readonly isFullyAligned: boolean;
}

/**
 * Cross-reference the manifest against the adapter registry and the
 * contribution kinds authority.
 *
 * This is a pure validation function — it does not mutate any state.
 *
 * @param manifest — The manifest to validate.
 * @param registry — The adapter registry to cross-reference.
 * @returns A {@link ManifestCrossReferenceResult} with all detected
 *          discrepancies.
 */
export function crossReferenceManifest(
  manifest: FamilyAdapterManifest,
  registry: FamilyAdapterRegistry,
): ManifestCrossReferenceResult {
  const manifestKindSet = new Set(manifest.kinds);
  const registryKindSet = new Set(registry.keys());
  const contributionKindSet = new Set<string>(VIDEO_CONTRIBUTION_KINDS);

  const missingFromRegistry: string[] = [];
  const missingFromManifest: string[] = [];
  const kindsNeedingAdapter: string[] = [];
  const kindsWithAdapter: string[] = [];

  for (const entry of manifest.entries) {
    const regEntry = registry.get(entry.kind);

    if (regEntry === undefined) {
      missingFromRegistry.push(entry.kind);
      if (entry.expectsRealAdapter) {
        kindsNeedingAdapter.push(entry.kind);
      }
    } else if (regEntry === null && entry.expectsRealAdapter) {
      kindsNeedingAdapter.push(entry.kind);
    } else if (regEntry !== null) {
      kindsWithAdapter.push(entry.kind);
    }
  }

  for (const kind of registryKindSet) {
    if (!manifestKindSet.has(kind)) {
      missingFromManifest.push(kind);
    }
  }
  missingFromManifest.sort();

  // Contribution kinds cross-reference
  const contributionKindsNotInManifest: string[] = [];
  for (const ck of contributionKindSet) {
    if (!manifestKindSet.has(ck)) {
      contributionKindsNotInManifest.push(ck);
    }
  }
  contributionKindsNotInManifest.sort();

  const manifestKindsNotInContributionKinds: string[] = [];
  for (const mk of manifestKindSet) {
    if (!contributionKindSet.has(mk)) {
      manifestKindsNotInContributionKinds.push(mk);
    }
  }
  manifestKindsNotInContributionKinds.sort();

  const isFullyAligned =
    missingFromRegistry.length === 0 &&
    missingFromManifest.length === 0 &&
    contributionKindsNotInManifest.length === 0 &&
    manifestKindsNotInContributionKinds.length === 0;

  return {
    missingFromRegistry,
    missingFromManifest,
    kindsNeedingAdapter,
    kindsWithAdapter,
    contributionKindsNotInManifest,
    manifestKindsNotInContributionKinds,
    isFullyAligned,
  };
}
