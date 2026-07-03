import type {
  ReighExtension,
  ExtensionContribution,
  ExtensionDiagnostic,
  FamilyContributionRef,
  EffectContribution,
  TransitionContribution,
} from '@reigh/editor-sdk';
import type { InactiveReservedContribution } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { getContributionRuntimeStatus } from '@/tools/video-editor/runtime/families/FamilyProjectionPolicy.ts';
import { VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY } from '@/tools/video-editor/runtime/families/familyAdapterRegistry.ts';

// ---------------------------------------------------------------------------
// Collected contribution (used during Phase 2 & Phase 3)
// ---------------------------------------------------------------------------

/** A contribution paired with its owning extension ID during sequencing. */
export interface CollectedContribution
  extends FamilyContributionRef<ExtensionContribution> {
  readonly scopedKey: string;
  readonly duplicateOrdinal: number;
  readonly projectionEligible: boolean;
}

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

/** Aggregate produced by the contribution-sequencing phase. */
export interface FamilyContributionSequence {
  diagnostics: ExtensionDiagnostic[];
  inactiveReserved: InactiveReservedContribution[];
  knownRenderIds: Set<string>;
  settingsDefaults: Record<string, Record<string, unknown>>;
  /** extensionId → insertion index (primary sort key) */
  extensionOrder: Map<string, number>;
  /** Unique, deduplicated extensions in order of first occurrence. */
  uniqueExtensions: ReighExtension[];
  /** Bridged contributions sorted by extension-order → order → id. */
  sortedBridged: CollectedContribution[];
  /** Reserved M6 output-format contributions (may project when inactive). */
  m6ReservedOutputFormats: CollectedContribution[];
  /** Reserved M6 search-provider contributions. */
  m6ReservedSearchProviders: CollectedContribution[];
  /** Reserved M12 process contributions. */
  m12ReservedProcesses: CollectedContribution[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function recordInactiveReservedContribution(
  inactiveReserved: InactiveReservedContribution[],
  diagnostics: ExtensionDiagnostic[],
  knownRenderIds: Set<string>,
  collected: CollectedContribution,
  milestone: string,
): void {
  const { extensionId, contribution, scopedKey, duplicateOrdinal, projectionEligible } = collected;
  inactiveReserved.push({
    extensionId,
    contributionId: contribution.id as string,
    kind: contribution.kind,
    scopedKey,
    duplicateOrdinal,
    projectionEligible,
    milestone,
  });
  diagnostics.push({
    severity: 'info',
    code: 'runtime/contribution-kind-not-yet-bridged',
    message:
      `Contribution "${contribution.id as string}" (kind: ${contribution.kind}) in extension "${extensionId}" ` +
      `is reserved for ${milestone}.`,
    extensionId,
    contributionId: contribution.id as string,
    milestone,
  });
  if (contribution.render) {
    knownRenderIds.add(contribution.render);
  }
}

export function contributionScopedKey(
  extensionId: string,
  contribution: ExtensionContribution,
): string {
  return `${contribution.kind}:${extensionId}:${contribution.id as string}`;
}

function collectContributionRecord(
  extensionId: string,
  contribution: ExtensionContribution,
  seenScopedContributionCounts: Map<string, number>,
): CollectedContribution {
  const scopedKey = contributionScopedKey(extensionId, contribution);
  const duplicateOrdinal = seenScopedContributionCounts.get(scopedKey) ?? 0;
  seenScopedContributionCounts.set(scopedKey, duplicateOrdinal + 1);
  return {
    contribution,
    extensionId,
    scopedKey,
    duplicateOrdinal,
    projectionEligible: duplicateOrdinal === 0,
  };
}

// ---------------------------------------------------------------------------
// Main sequencing function
// ---------------------------------------------------------------------------

/**
 * Phase 1-3 of host-owned runtime normalization: validate extensions,
 * collect and classify contributions, and produce a deterministically
 * ordered sequence ready for descriptor projection.
 *
 * This is intentionally a pure data function — it does not construct any
 * runtime descriptors or freeze anything.
 */
export function buildFamilyContributionSequence(
  extensions: readonly ReighExtension[],
): FamilyContributionSequence {
  // ---- Phase 1: validate extension IDs, detect duplicates ------------------
  const diagnostics: ExtensionDiagnostic[] = [];
  const seenExtensionIds = new Set<string>();
  /**
   * Extension order map: extensionId -> insertion index.
   * Used as the primary sort key for deterministic contribution ordering.
   */
  const extensionOrder = new Map<string, number>();
  const uniqueExtensions: ReighExtension[] = [];

  for (const ext of extensions) {
    const id = ext.manifest.id as string;
    if (seenExtensionIds.has(id)) {
      diagnostics.push({
        severity: 'error',
        code: 'runtime/duplicate-extension',
        message: `Duplicate extension ID "${id}". Only the first occurrence will be used.`,
        extensionId: id,
      });
    } else {
      seenExtensionIds.add(id);
      extensionOrder.set(id, uniqueExtensions.length);
      uniqueExtensions.push(ext);
    }
  }

  // ---- Phase 2: collect contributions, detect exact scoped-key duplicates ---
  const bridged: CollectedContribution[] = [];
  const inactiveReserved: InactiveReservedContribution[] = [];
  const knownRenderIds = new Set<string>();
  const settingsDefaults: Record<string, Record<string, unknown>> = {};

  // M6: Collect contributions that are reserved for execution but still
  // need to be surfaced as disabled/reserved descriptors in the runtime config.
  const m6ReservedOutputFormats: CollectedContribution[] = [];
  const m6ReservedSearchProviders: CollectedContribution[] = [];
  const m12ReservedProcesses: CollectedContribution[] = [];

  const seenScopedContributionCounts = new Map<string, number>();

  for (const ext of uniqueExtensions) {
    const extId = ext.manifest.id as string;

    // Settings defaults — each extension gets its declared defaults, frozen
    settingsDefaults[extId] = ext.manifest.settingsDefaults
      ? { ...ext.manifest.settingsDefaults }
      : {};

    const contribs = ext.manifest.contributions ?? [];
    for (const contrib of contribs) {
      const contribId = contrib.id as string;
      const collected = collectContributionRecord(
        extId,
        contrib,
        seenScopedContributionCounts,
      );

      if (collected.duplicateOrdinal > 0) {
        diagnostics.push({
          severity: 'warning',
          code: 'runtime/duplicate-contribution',
          message:
            `Duplicate contribution declaration "${contribId}" (kind: ${contrib.kind}) ` +
            `in extension "${extId}". Preserving the duplicate record.`,
          extensionId: extId,
          contributionId: contribId,
        });
      }

      // outputFormat/searchProvider/process remain historically reserved
      // (surfaced as descriptors but recorded as inactive reserved).
      // All other families consult the adapter registry so delegated
      // placeholder adapters are treated as projectable / bridged.
      const historicallyReserved =
        contrib.kind === 'outputFormat' ||
        contrib.kind === 'searchProvider' ||
        contrib.kind === 'process';
      const runtimeStatus = getContributionRuntimeStatus(
        contrib.kind,
        historicallyReserved ? undefined : VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
      );
      const notYetBridged = runtimeStatus.legacyBridgeStatus;

      // M7: Effect contributions with component metadata (effectId) are
      // treated as active and projected into deterministic descriptors.
      // Effects without component metadata remain inactive with diagnostics.
      if (contrib.kind === 'effect') {
        const effectContrib = contrib as unknown as EffectContribution;
        if (effectContrib.effectId) {
          // Component-backed: treat as active
          bridged.push(collected);
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        } else {
          // Unsupported: no component metadata — inactive with diagnostic
          inactiveReserved.push({
            extensionId: extId,
            contributionId: contribId,
            kind: contrib.kind,
            scopedKey: collected.scopedKey,
            duplicateOrdinal: collected.duplicateOrdinal,
            projectionEligible: collected.projectionEligible,
            milestone: notYetBridged ?? 'unknown',
          });
          diagnostics.push({
            severity: 'warning',
            code: 'runtime/effect-missing-component-metadata',
            message:
              `Effect contribution "${contribId}" in extension "${extId}" ` +
              `has no effectId (component metadata). The effect will be inactive.`,
            extensionId: extId,
            contributionId: contribId,
          });
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        }
        continue;
      }

      // M8: Transition contributions with renderer metadata (transitionId) are
      // treated as active and projected into deterministic descriptors.
      // Transitions without renderer metadata remain inactive with diagnostics.
      if (contrib.kind === 'transition') {
        const transitionContrib = contrib as unknown as TransitionContribution;
        if (transitionContrib.transitionId) {
          // Renderer-backed: treat as active
          bridged.push(collected);
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        } else {
          // Unsupported: no renderer metadata — inactive with diagnostic
          inactiveReserved.push({
            extensionId: extId,
            contributionId: contribId,
            kind: contrib.kind,
            scopedKey: collected.scopedKey,
            duplicateOrdinal: collected.duplicateOrdinal,
            projectionEligible: collected.projectionEligible,
            milestone: notYetBridged ?? 'unknown',
          });
          diagnostics.push({
            severity: 'warning',
            code: 'runtime/transition-missing-renderer-metadata',
            message:
              `Transition contribution "${contribId}" in extension "${extId}" ` +
              `has no transitionId (renderer metadata). The transition will be inactive.`,
            extensionId: extId,
            contributionId: contribId,
          });
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        }
        continue;
      }

      // M6: OutputFormat and SearchProvider are reserved for execution but
      // must still be collected as descriptors in the runtime config.
      if (
        runtimeStatus.isDelegated &&
        notYetBridged !== null &&
        (contrib.kind === 'outputFormat' || contrib.kind === 'searchProvider')
      ) {
        recordInactiveReservedContribution(
          inactiveReserved,
          diagnostics,
          knownRenderIds,
          collected,
          notYetBridged,
        );
        // Collect into the appropriate M6 reserved list for later projection
        if (contrib.kind === 'outputFormat') {
          m6ReservedOutputFormats.push(collected);
        } else {
          m6ReservedSearchProviders.push(collected);
        }
        continue;
      }
      if (runtimeStatus.isDelegated && notYetBridged !== null && contrib.kind === 'process') {
        recordInactiveReservedContribution(
          inactiveReserved,
          diagnostics,
          knownRenderIds,
          collected,
          notYetBridged,
        );
        m12ReservedProcesses.push(collected);
        continue;
      }
      if (notYetBridged !== null) {
        recordInactiveReservedContribution(
          inactiveReserved,
          diagnostics,
          knownRenderIds,
          collected,
          notYetBridged,
        );
        continue;
      }

      bridged.push(collected);

      // Track known render IDs
      if (contrib.render) {
        knownRenderIds.add(contrib.render);
      }
    }
  }

  // ---- Phase 3: deterministic ordering -------------------------------------
  // Sort by extension order (primary), then contribution order ascending,
  // then contribution ID alphabetically (stable tiebreaker).
  const sortedBridged = [...bridged].sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;
    const orderA = a.contribution.order ?? 0;
    const orderB = b.contribution.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    const idCompare = (a.contribution.id as string).localeCompare(b.contribution.id as string);
    if (idCompare !== 0) return idCompare;
    if (a.scopedKey === b.scopedKey) {
      return a.duplicateOrdinal - b.duplicateOrdinal;
    }
    return 0;
  });

  return {
    diagnostics,
    inactiveReserved,
    knownRenderIds,
    settingsDefaults,
    extensionOrder,
    uniqueExtensions,
    sortedBridged,
    m6ReservedOutputFormats,
    m6ReservedSearchProviders,
    m12ReservedProcesses,
  };
}
