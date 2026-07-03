/**
 * Family runtime assembly — Phase 4–5 of host-owned runtime normalization.
 *
 * This module builds a frozen, deterministic {@link ExtensionRuntime} from
 * the contribution sequence produced by {@link buildFamilyContributionSequence}.
 *
 * All family projection is now owned by the registered host adapters in
 * {@link VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY}.  This module is responsible
 * only for dispatch, diagnostics aggregation, config assembly, package
 * summary enrichment, and deep freezing.
 *
 * @module families/FamilyRuntimeAssembly
 */

import type {
  TimelineSnapshot,
  ExtensionContribution,
  ExtensionDiagnostic,
} from '@reigh/editor-sdk';
import type {
  HostFamilyAdapter,
  FamilyAdapterRegistry,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
} from '@reigh/editor-sdk';
import type { FamilyContributionSequence, CollectedContribution } from './FamilyContributionSequence';
import { contributionScopedKey } from './FamilyContributionSequence';
import { VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY } from './familyAdapterRegistry';
import type {
  ExtensionRuntime,
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorExtensionRuntimeConfig,
  VideoEditorSlotRenderer,
  VideoEditorSlotName,
  VideoEditorDialogDescriptor,
  VideoEditorPanelDescriptor,
  VideoEditorInspectorSectionDescriptor,
  VideoEditorOverlayDescriptor,
  VideoEditorAssetParserDescriptor,
  VideoEditorOutputFormatDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorSearchProviderDescriptor,
  VideoEditorMetadataFacetDescriptor,
  VideoEditorAssetDetailSectionDescriptor,
  VideoEditorEffectDescriptor,
  VideoEditorTransitionDescriptor,
  VideoEditorShaderDescriptor,
  VideoEditorAgentToolDescriptor,
  PackageStateInventoryEntry,
} from '../extensionSurface';
import { projectCompositionGraph } from '../composition/graphProjector';
import type { VideoEditorSlotDescriptor } from './slotAdapter';
import { normalizeContributionIndexRouteFit } from '../routeFitMapper';
import { buildShaderDescriptorsFromGraph } from './projectors/shaderProjector';

// ---------------------------------------------------------------------------
// Contribution kind labels
// ---------------------------------------------------------------------------

/** Short human-readable label for each contribution kind. */
const CONTRIBUTION_KIND_LABEL: Partial<Record<string, string>> = {
  slot: 'Slot',
  dialog: 'Dialog',
  panel: 'Panel',
  inspectorSection: 'Inspector section',
  overlay: 'Overlay',
  parser: 'Parser',
  outputFormat: 'Output format',
  searchProvider: 'Search provider',
  metadataFacet: 'Metadata facet',
  assetDetailSection: 'Asset detail',
  effect: 'Effect',
  transition: 'Transition',
  shader: 'Shader',
  agentTool: 'Agent tool',
  process: 'Process',
};

// ---------------------------------------------------------------------------
// Package contribution summary
// ---------------------------------------------------------------------------

/**
 * Manifest-derived contribution summary that survives without active runtime
 * descriptors. Computed from manifest contributions plus optional runtime
 * data for active/inactive counts.
 */
export interface PackageContributionSummary {
  /** Total contributions declared in the extension manifest. */
  readonly declared: number;
  /** Number of contributions currently active (bridged) in the runtime.
   *  -1 when unknown (no active runtime descriptor available). */
  readonly active: number;
  /** Number of contributions reserved but not yet bridged.
   *  -1 when unknown. */
  readonly inactive: number;
  /** Sorted, deduplicated list of contribution kind labels for the summary. */
  readonly kinds: readonly string[];
  /** Per-kind contribution IDs for detailed error/reason display. */
  readonly contributionIds: Readonly<Record<string, readonly string[]>>;
}

/**
 * Compute a {@link PackageContributionSummary} from manifest contributions.
 *
 * When `activeKeys` is provided, contributions whose active identity appears
 * in the set are counted as active. When `owningExtensionId` is provided,
 * active identities are matched by scoped key (`kind:extensionId:contributionId`)
 * so same-extension cross-kind reuse is counted correctly and exact scoped-key
 * duplicates count once. When `inactiveCount` is provided, it is used as the
 * inactive count. Both are optional and default to -1 (unknown) when absent.
 */
export function computePackageContributionSummary(
  manifestContributions: readonly ExtensionContribution[] | undefined | null,
  activeKeys?: ReadonlySet<string>,
  inactiveCount?: number,
  owningExtensionId?: string,
): PackageContributionSummary | null {
  const contribs = manifestContributions ?? [];
  const declared = contribs.length;
  if (declared === 0) return null;

  const kinds = new Set<string>();
  const contributionIds: Record<string, string[]> = {};

  for (const contrib of contribs) {
    const kindLabel = CONTRIBUTION_KIND_LABEL[contrib.kind] ?? contrib.kind;
    kinds.add(kindLabel);

    const cid = contrib.id as string;
    if (!contributionIds[kindLabel]) {
      contributionIds[kindLabel] = [];
    }
    contributionIds[kindLabel].push(cid);
  }

  // Freeze contribution IDs per kind
  const frozenIds: Record<string, readonly string[]> = {};
  for (const kind of Object.keys(contributionIds)) {
    frozenIds[kind] = Object.freeze([...contributionIds[kind]]);
  }

  let active = -1;
  if (activeKeys) {
    active = 0;
    const countedScopedKeys = new Set<string>();
    for (const contrib of contribs) {
      const scopedKey = owningExtensionId
        ? contributionScopedKey(owningExtensionId, contrib)
        : `${contrib.kind}:${contrib.id as string}`;
      const activeKey = owningExtensionId ? scopedKey : (contrib.id as string);
      if (activeKeys.has(activeKey) && !countedScopedKeys.has(scopedKey)) {
        active++;
        countedScopedKeys.add(scopedKey);
      }
    }
  }

  return Object.freeze({
    declared,
    active: active,
    inactive: inactiveCount ?? -1,
    kinds: Object.freeze([...kinds].sort()),
    contributionIds: Object.freeze(frozenIds),
  });
}

// ---------------------------------------------------------------------------
// Adapter dispatch configuration
// ---------------------------------------------------------------------------

type ConfigField =
  | 'slots'
  | 'dialogHost.dialogs'
  | 'registry.panels'
  | 'registry.inspectorSections'
  | 'overlays'
  | 'assetParsers'
  | 'outputFormats'
  | 'processes'
  | 'searchProviders'
  | 'metadataFacets'
  | 'assetDetailSections'
  | 'effects'
  | 'transitions'
  | 'shaders'
  | 'agentTools';

interface DispatchConfig {
  readonly field: ConfigField | null;
  readonly source: 'bridged' | 'reservedOutputFormat' | 'reservedSearchProvider' | 'reservedProcess';
}

const ADAPTER_DISPATCH: Readonly<Record<string, DispatchConfig>> = {
  slot: { field: 'slots', source: 'bridged' },
  dialog: { field: 'dialogHost.dialogs', source: 'bridged' },
  panel: { field: 'registry.panels', source: 'bridged' },
  inspectorSection: { field: 'registry.inspectorSections', source: 'bridged' },
  timelineOverlay: { field: 'overlays', source: 'bridged' },
  parser: { field: 'assetParsers', source: 'bridged' },
  outputFormat: { field: 'outputFormats', source: 'reservedOutputFormat' },
  searchProvider: { field: 'searchProviders', source: 'reservedSearchProvider' },
  process: { field: 'processes', source: 'reservedProcess' },
  metadataFacet: { field: 'metadataFacets', source: 'bridged' },
  assetDetailSection: { field: 'assetDetailSections', source: 'bridged' },
  effect: { field: 'effects', source: 'bridged' },
  transition: { field: 'transitions', source: 'bridged' },
  shader: { field: 'shaders', source: 'bridged' },
  agentTool: { field: 'agentTools', source: 'bridged' },
};

const EMPTY_RUNTIME_COMPOSITION_SNAPSHOT: TimelineSnapshot = Object.freeze({
  projectId: null,
  baseVersion: 0,
  currentVersion: 0,
  extensionRequirements: Object.freeze([]),
  clips: Object.freeze([]),
  tracks: Object.freeze([]),
  assetKeys: Object.freeze([]),
  app: Object.freeze({}),
  shaders: Object.freeze([]),
});

function buildCompositionGraph(contributionIndex: ContributionIndex) {
  return projectCompositionGraph({
    snapshot: EMPTY_RUNTIME_COMPOSITION_SNAPSHOT,
    contributionIndex,
  });
}

// ---------------------------------------------------------------------------
// Main assembly function
// ---------------------------------------------------------------------------

/**
 * Phase 4–5 of host-owned runtime normalization: project the sequenced
 * contributions into runtime descriptors, assemble the frozen
 * {@link ExtensionRuntime}, and compute package contribution summaries.
 *
 * @param seq - The contribution sequence from Phase 1–3.
 * @param packageStateEntries - Optional package-state inventory entries.
 * @param defaultConfig - The default config to use when no configurable
 *   contributions exist (pass {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME}
 *   to preserve identity).
 * @param adapterRegistry - Optional adapter registry for coordinator-backed
 *   family normalization.  When omitted, the canonical
 *   {@link VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY} is used.
 */
export function assembleExtensionRuntime(
  seq: FamilyContributionSequence,
  packageStateEntries: readonly PackageStateInventoryEntry[] | undefined,
  defaultConfig: VideoEditorExtensionRuntimeConfig,
  adapterRegistry?: FamilyAdapterRegistry,
): ExtensionRuntime {
  const {
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
  } = seq;

  const registry = adapterRegistry ?? VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY;
  type BridgedContributionRecord = (typeof sortedBridged)[number];
  const activeContributionScopedKeys = new Set<string>();
  const projectedContributionRecordKeys = new Set<string>();

  // ---- Phase 4: collect projection candidates by dispatch source ------------
  const projectionCandidatesByKind: Record<string, { kind: string; contributions: typeof sortedBridged }> = {};

  function pushToKind(kind: string, item: (typeof sortedBridged)[number]) {
    if (!projectionCandidatesByKind[kind]) {
      projectionCandidatesByKind[kind] = { kind, contributions: [] };
    }
    projectionCandidatesByKind[kind].contributions.push(item);
  }

  for (const item of sortedBridged) {
    if (item.projectionEligible) {
      pushToKind(item.contribution.kind, item);
    }
  }

  // ---- Phase 4a: dispatch to adapters --------------------------------------
  const slots: Record<string, VideoEditorSlotRenderer> = {};
  const dialogDescriptors: VideoEditorDialogDescriptor[] = [];
  const panelDescriptors: VideoEditorPanelDescriptor[] = [];
  const inspectorSectionDescriptors: VideoEditorInspectorSectionDescriptor[] = [];
  const overlayDescriptors: VideoEditorOverlayDescriptor[] = [];
  const assetParserDescriptors: VideoEditorAssetParserDescriptor[] = [];
  const outputFormatDescriptors: VideoEditorOutputFormatDescriptor[] = [];
  const processDescriptors: VideoEditorProcessDescriptor[] = [];
  const searchProviderDescriptors: VideoEditorSearchProviderDescriptor[] = [];
  const metadataFacetDescriptors: VideoEditorMetadataFacetDescriptor[] = [];
  const assetDetailSectionDescriptors: VideoEditorAssetDetailSectionDescriptor[] = [];
  const effectDescriptors: VideoEditorEffectDescriptor[] = [];
  const transitionDescriptors: VideoEditorTransitionDescriptor[] = [];
  const shaderDescriptors: VideoEditorShaderDescriptor[] = [];
  const agentToolDescriptors: VideoEditorAgentToolDescriptor[] = [];

  function getDescriptorArray(field: ConfigField): unknown[] | null {
    switch (field) {
      case 'dialogHost.dialogs':
        return dialogDescriptors;
      case 'registry.panels':
        return panelDescriptors;
      case 'registry.inspectorSections':
        return inspectorSectionDescriptors;
      case 'overlays':
        return overlayDescriptors;
      case 'assetParsers':
        return assetParserDescriptors;
      case 'outputFormats':
        return outputFormatDescriptors;
      case 'processes':
        return processDescriptors;
      case 'searchProviders':
        return searchProviderDescriptors;
      case 'metadataFacets':
        return metadataFacetDescriptors;
      case 'assetDetailSections':
        return assetDetailSectionDescriptors;
      case 'effects':
        return effectDescriptors;
      case 'transitions':
        return transitionDescriptors;
      case 'shaders':
        return shaderDescriptors;
      case 'agentTools':
        return agentToolDescriptors;
      case 'slots':
      default:
        return null;
    }
  }

  function getReservedProjectionCandidates(kind: string): typeof sortedBridged {
    const preserved =
      kind === 'outputFormat'
        ? m6ReservedOutputFormats
        : kind === 'searchProvider'
          ? m6ReservedSearchProviders
          : kind === 'process'
            ? m12ReservedProcesses
            : [];
    if (preserved.length === 0) {
      return [];
    }
    const projectionCandidates = preserved.filter((item) => item.projectionEligible);
    if (projectionCandidates.length === preserved.length) {
      return preserved;
    }
    return projectionCandidates;
  }

  function contributionRecordKey(
    item: Readonly<{ scopedKey: string; duplicateOrdinal: number }>,
  ): string {
    return `${item.scopedKey}#${item.duplicateOrdinal}`;
  }

  function duplicateResolutionPolicy(
    item: Readonly<{ scopedKey: string; duplicateOrdinal: number }>,
  ): ContributionIndexEntry['resolutionPolicy'] {
    if (item.duplicateOrdinal === 0) {
      return undefined;
    }
    return Object.freeze({
      kind: 'exact-duplicate' as const,
      strategy: 'first-wins-projection' as const,
      winnerScopedKey: item.scopedKey,
      winnerDuplicateOrdinal: 0,
    });
  }

  function markProjectedContribution(item: BridgedContributionRecord): void {
    activeContributionScopedKeys.add(item.scopedKey);
    projectedContributionRecordKeys.add(contributionRecordKey(item));
  }

  function recordProjectedDescriptorKeys(
    contributions: ReadonlyArray<BridgedContributionRecord>,
    descriptors: readonly unknown[],
  ): void {
    const descriptorCounts = new Map<string, number>();

    for (const descriptor of descriptors) {
      if (!descriptor || typeof descriptor !== 'object') {
        continue;
      }
      const id = 'id' in descriptor && typeof descriptor.id === 'string'
        ? descriptor.id
        : null;
      if (!id) {
        continue;
      }
      const extensionId = 'extensionId' in descriptor && typeof descriptor.extensionId === 'string'
        ? descriptor.extensionId
        : null;
      const key = extensionId ? `${extensionId}::${id}` : id;
      descriptorCounts.set(key, (descriptorCounts.get(key) ?? 0) + 1);
    }

    for (const item of contributions) {
      const contributionId = item.contribution.id as string;
      const exactKey = `${item.extensionId}::${contributionId}`;
      const fallbackKey = contributionId;
      const exactCount = descriptorCounts.get(exactKey) ?? 0;
      if (exactCount > 0) {
        descriptorCounts.set(exactKey, exactCount - 1);
        markProjectedContribution(item);
        continue;
      }
      const fallbackCount = descriptorCounts.get(fallbackKey) ?? 0;
      if (fallbackCount > 0) {
        descriptorCounts.set(fallbackKey, fallbackCount - 1);
        markProjectedContribution(item);
      }
    }
  }

  function recordProjectedSlotKeys(
    contributions: ReadonlyArray<BridgedContributionRecord>,
    descriptors: readonly VideoEditorSlotDescriptor[],
  ): void {
    const projectedSlots = new Set(descriptors.map((descriptor) => descriptor.slot));
    const consumedSlots = new Set<string>();
    for (const item of contributions) {
      const slotName = (item.contribution as ExtensionContribution & {
        readonly slot?: string;
      }).slot;
      if (slotName && projectedSlots.has(slotName) && !consumedSlots.has(slotName)) {
        consumedSlots.add(slotName);
        markProjectedContribution(item);
      }
    }
  }

  function freezeDiagnostic(
    diagnostic: Readonly<ExtensionDiagnostic>,
  ): Readonly<ExtensionDiagnostic> {
    return Object.freeze({
      ...diagnostic,
      ...(diagnostic.detail
        ? { detail: Object.freeze({ ...diagnostic.detail }) }
        : {}),
    });
  }

  function buildDiagnosticsByScopedKey(): ReadonlyMap<string, readonly ReturnType<typeof freezeDiagnostic>[]> {
    const activeByScopedKey = new Map<string, BridgedContributionRecord[]>();
    const activeByExtensionContribution = new Map<string, BridgedContributionRecord[]>();

    for (const item of sortedBridged) {
      const scopedItems = activeByScopedKey.get(item.scopedKey) ?? [];
      scopedItems.push(item);
      activeByScopedKey.set(item.scopedKey, scopedItems);

      const extensionContributionKey = `${item.extensionId}::${item.contribution.id as string}`;
      const ambiguousItems = activeByExtensionContribution.get(extensionContributionKey) ?? [];
      ambiguousItems.push(item);
      activeByExtensionContribution.set(extensionContributionKey, ambiguousItems);
    }

    // Also index inactive-reserved items so their diagnostics can be attached
    const inactiveByScopedKey = new Map<string, typeof inactiveReserved>();
    const inactiveByExtensionContribution = new Map<string, typeof inactiveReserved>();
    for (const item of inactiveReserved) {
      const scopedItems = inactiveByScopedKey.get(item.scopedKey) ?? [];
      scopedItems.push(item);
      inactiveByScopedKey.set(item.scopedKey, scopedItems);

      const extensionContributionKey = `${item.extensionId}::${item.contributionId}`;
      const ambiguousItems = inactiveByExtensionContribution.get(extensionContributionKey) ?? [];
      ambiguousItems.push(item);
      inactiveByExtensionContribution.set(extensionContributionKey, ambiguousItems);
    }

    const attached = new Map<string, ReturnType<typeof freezeDiagnostic>[]>();

    for (const diagnostic of diagnostics) {
      if (!diagnostic.extensionId || !diagnostic.contributionId) {
        continue;
      }

      const frozenDiagnostic = freezeDiagnostic(diagnostic);
      const extensionContributionKey =
        `${diagnostic.extensionId}::${diagnostic.contributionId}`;
      const candidateItems = activeByExtensionContribution.get(extensionContributionKey) ?? [];
      const inactiveCandidateItems = inactiveByExtensionContribution.get(extensionContributionKey) ?? [];
      if (candidateItems.length === 0 && inactiveCandidateItems.length === 0) {
        continue;
      }

      let targetScopedKeys: readonly string[] = [];
      if (candidateItems.length === 1 && inactiveCandidateItems.length === 0) {
        targetScopedKeys = [candidateItems[0].scopedKey];
      } else if (candidateItems.length === 0 && inactiveCandidateItems.length === 1) {
        targetScopedKeys = [inactiveCandidateItems[0].scopedKey];
      } else {
        const detailKind =
          typeof diagnostic.detail?.contributionKind === 'string'
            ? diagnostic.detail.contributionKind
            : null;
        const activeKindMatches = candidateItems.filter((item) => {
          if (detailKind) {
            return item.contribution.kind === detailKind;
          }
          return diagnostic.message.includes(`kind: ${item.contribution.kind}`);
        });
        const inactiveKindMatches = inactiveCandidateItems.filter((item) => {
          if (detailKind) {
            return item.kind === detailKind;
          }
          return diagnostic.message.includes(`kind: ${item.kind}`);
        });
        const matchedScopedKeys = new Set([
          ...activeKindMatches.map((item) => item.scopedKey),
          ...inactiveKindMatches.map((item) => item.scopedKey),
        ]);

        if (matchedScopedKeys.size > 0) {
          targetScopedKeys = [...matchedScopedKeys];
        } else if (!detailKind) {
          // Fall back only when the diagnostic cannot identify a unique kind.
          targetScopedKeys = [
            ...new Set([
              ...candidateItems.map((item) => item.scopedKey),
              ...inactiveCandidateItems.map((item) => item.scopedKey),
            ]),
          ];
        }
      }

      for (const scopedKey of targetScopedKeys) {
        const scopedDiagnostics = attached.get(scopedKey) ?? [];
        scopedDiagnostics.push(frozenDiagnostic);
        attached.set(scopedKey, scopedDiagnostics);
      }
    }

    return new Map(
      [...attached.entries()].map(([scopedKey, scopedDiagnostics]) => [
        scopedKey,
        Object.freeze(scopedDiagnostics),
      ]),
    );
  }

  function freezeContributionIndex(
    contributionIndex: Record<string, ContributionIndexEntry[]>,
  ): Readonly<Record<string, readonly ContributionIndexEntry[]>> {
    const frozenIndex: Record<string, readonly ContributionIndexEntry[]> = {};
    for (const [key, entries] of Object.entries(contributionIndex)) {
      frozenIndex[key] = Object.freeze(entries);
    }
    return Object.freeze(frozenIndex);
  }

  function packageStateToIndexStatus(
    state: PackageStateInventoryEntry['packageState'],
  ): ContributionIndexEntry['status'] {
    switch (state) {
      case 'invalid':
        return 'invalid';
      case 'disabled-by-user':
        return 'disabled';
      case 'incompatible':
      case 'duplicate':
      case 'settings-error':
      case 'runtime-error':
        return 'disabled';
      default:
        return 'active';
    }
  }

  function buildContributionIndexEntries(): Readonly<Record<string, readonly ContributionIndexEntry[]>> {
    const contributionIndex: Record<string, ContributionIndexEntry[]> = {};
    const diagnosticsByScopedKey = buildDiagnosticsByScopedKey();
    const packageStateByExtensionId = new Map<string, PackageStateInventoryEntry['packageState']>();
    for (const entry of packageStateEntries ?? []) {
      if (!packageStateByExtensionId.has(entry.extensionId)) {
        packageStateByExtensionId.set(entry.extensionId, entry.packageState);
      }
    }

    // Track which extension IDs have active bridged contributions
    const activeExtensionIds = new Set<string>();
    for (const item of sortedBridged) {
      activeExtensionIds.add(item.extensionId);
    }

    for (const item of sortedBridged) {
      if (!contributionIndex[item.scopedKey]) {
        contributionIndex[item.scopedKey] = [];
      }
      const projected = projectedContributionRecordKeys.has(contributionRecordKey(item));
      const resolutionPolicy = !projected ? duplicateResolutionPolicy(item) : undefined;
      const diagnosticsForScopedKey =
        diagnosticsByScopedKey.get(item.scopedKey) ?? Object.freeze([]);
      contributionIndex[item.scopedKey].push(Object.freeze({
        scopedKey: item.scopedKey,
        kind: item.contribution.kind,
        extensionId: item.extensionId,
        contributionId: item.contribution.id as string,
        status: 'active',
        packageState: packageStateByExtensionId.get(item.extensionId),
        diagnostics: diagnosticsForScopedKey,
        duplicateOrdinal: item.duplicateOrdinal,
        projectionEligible: item.projectionEligible,
        projection: Object.freeze({
          duplicateOrdinal: item.duplicateOrdinal,
          eligible: item.projectionEligible,
          projected,
          source: projected ? 'descriptor-array' : 'preserved-record',
        }),
        ...(resolutionPolicy ? { resolutionPolicy } : {}),
      }));
    }

    // ---- Inactive-reserved contributions ------------------------------------
    for (const item of inactiveReserved) {
      if (!contributionIndex[item.scopedKey]) {
        contributionIndex[item.scopedKey] = [];
      }
      const projected = projectedContributionRecordKeys.has(contributionRecordKey(item));
      const resolutionPolicy = !projected ? duplicateResolutionPolicy(item) : undefined;
      const diagnosticsForScopedKey =
        diagnosticsByScopedKey.get(item.scopedKey) ?? Object.freeze([]);
      contributionIndex[item.scopedKey].push(Object.freeze({
        scopedKey: item.scopedKey,
        kind: item.kind,
        extensionId: item.extensionId,
        contributionId: item.contributionId,
        status: 'inactive-reserved',
        packageState: packageStateByExtensionId.get(item.extensionId),
        diagnostics: diagnosticsForScopedKey,
        duplicateOrdinal: item.duplicateOrdinal,
        projectionEligible: item.projectionEligible,
        projection: Object.freeze({
          duplicateOrdinal: item.duplicateOrdinal,
          eligible: item.projectionEligible,
          projected,
          source: projected ? 'descriptor-array' : 'preserved-record',
        }),
        ...(resolutionPolicy ? { resolutionPolicy } : {}),
      }));
    }

    // ---- Disabled / invalid package contributions ---------------------------
    for (const entry of packageStateEntries ?? []) {
      const packageState = entry.packageState;
      // Skip loaded packages — their contributions are already in sortedBridged
      if (packageState === 'loaded') continue;
      // Skip if this extension already has active bridged contributions
      if (activeExtensionIds.has(entry.extensionId)) continue;

      const manifestContribs = entry.manifestContributions;
      if (!manifestContribs || manifestContribs.length === 0) continue;

      const indexStatus = packageStateToIndexStatus(packageState);
      const frozenEmptyDiagnostics = Object.freeze([]);

      for (const contrib of manifestContribs) {
        const scopedKey = contributionScopedKey(entry.extensionId, contrib);
        if (!contributionIndex[scopedKey]) {
          contributionIndex[scopedKey] = [];
        }
        contributionIndex[scopedKey].push(Object.freeze({
          scopedKey,
          kind: contrib.kind,
          extensionId: entry.extensionId,
          contributionId: contrib.id as string,
          status: indexStatus,
          packageState,
          diagnostics: frozenEmptyDiagnostics,
          duplicateOrdinal: 0,
          projectionEligible: false,
          projection: Object.freeze({
            duplicateOrdinal: 0,
            eligible: false,
            projected: false,
            source: 'preserved-record',
          }),
        }));
      }
    }

    return freezeContributionIndex(contributionIndex);
  }

  let shaderContributionsForGraph: readonly CollectedContribution[] | undefined;

  for (const [kind, config] of Object.entries(ADAPTER_DISPATCH)) {
    const adapter = registry.get(kind) as HostFamilyAdapter<string, unknown, unknown> | null | undefined;
    if (!adapter || adapter === null) {
      // No adapter registered — skip projection.  This is only expected for
      // families whose execution maturity is absent/delegated and that have
      // no placeholder yet.
      continue;
    }

    const contributions =
      config.source === 'bridged'
        ? projectionCandidatesByKind[kind]?.contributions ?? []
        : getReservedProjectionCandidates(kind);

    if (contributions.length === 0) {
      continue;
    }

    const input: NormalizeFamilyInput<unknown> = {
      contributions,
      extensionOrder,
    };

    const result: FamilyNormalizeResult<unknown> = adapter.normalize(input);

    if (result.diagnostics && result.diagnostics.length > 0) {
      diagnostics.push(...result.diagnostics);
    }

    if (config.field === null) {
      continue;
    }

    if (config.field === 'slots') {
      const slotDescriptors = result.descriptors as VideoEditorSlotDescriptor[];
      recordProjectedSlotKeys(contributions, slotDescriptors);
      for (const descriptor of slotDescriptors) {
        if (descriptor.slot && !slots[descriptor.slot]) {
          slots[descriptor.slot] = descriptor.render;
        }
      }
      continue;
    }

    // Capture shader contributions for graph-derived projection later
    if (kind === 'shader') {
      shaderContributionsForGraph = contributions;
    }

    const target = getDescriptorArray(config.field);
    if (target) {
      const descriptors = result.descriptors as unknown[];
      target.push(...descriptors);
      recordProjectedDescriptorKeys(contributions, descriptors);
    }
  }

  const contributionIndex = buildContributionIndexEntries();

  // ---- Route-fit normalization ---------------------------------------------
  // Enrich contribution index entries with route-fit metadata from
  // descriptor blockers whose identity can be directly or uniquely
  // resolved to a scoped key.  Ambiguous blockers are silently skipped.
  const descriptorBlockers = [
    ...outputFormatDescriptors.flatMap((fmt) => fmt.blockers),
    ...processDescriptors.flatMap((proc) => proc.blockers),
  ];
  const routeFitContributionIndex =
    normalizeContributionIndexRouteFit(contributionIndex, descriptorBlockers);
  const compositionGraph = buildCompositionGraph(routeFitContributionIndex);

  // ---- Graph-derived shader descriptor shim (M1b) ---------------------------
  // When the composition graph carries shader consumes edges it becomes the
  // authority for which shader contributions produce descriptors.  The
  // independently-built shaderDescriptors array is replaced with a
  // graph-derived projection so it cannot act as a second authority for
  // M1b shader/ref resolution.
  // Graph-absent (edge-less) assembly preserves the adapter-built descriptors
  // and diagnostics exactly as they were, avoiding duplicated diagnostics.
  if (
    shaderContributionsForGraph &&
    shaderContributionsForGraph.length > 0 &&
    compositionGraph.edges.length > 0
  ) {
    const graphShaderResult = buildShaderDescriptorsFromGraph(
      shaderContributionsForGraph,
      extensionOrder,
      compositionGraph,
    );
    shaderDescriptors.length = 0;
    shaderDescriptors.push(...graphShaderResult.descriptors);
    if (graphShaderResult.diagnostics.length > 0) {
      diagnostics.push(...graphShaderResult.diagnostics);
    }
  }

  // ---- Phase 5: assemble and freeze ----------------------------------------
  /** Whether any contributions — bridged or M6-reserved — affect the config. */
  const hasAnyConfigurableContent =
    Object.keys(slots).length > 0 ||
    dialogDescriptors.length > 0 ||
    panelDescriptors.length > 0 ||
    inspectorSectionDescriptors.length > 0 ||
    overlayDescriptors.length > 0 ||
    assetParserDescriptors.length > 0 ||
    outputFormatDescriptors.length > 0 ||
    processDescriptors.length > 0 ||
    searchProviderDescriptors.length > 0 ||
    metadataFacetDescriptors.length > 0 ||
    assetDetailSectionDescriptors.length > 0 ||
    effectDescriptors.length > 0 ||
    transitionDescriptors.length > 0 ||
    shaderDescriptors.length > 0 ||
    agentToolDescriptors.length > 0;

  const config: VideoEditorExtensionRuntimeConfig = hasAnyConfigurableContent
    ? Object.freeze({
        slots: Object.freeze(slots) as Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>,
        dialogHost: Object.freeze({
          dialogs: Object.freeze(dialogDescriptors),
        }),
        registry: Object.freeze({
          panels: Object.freeze(panelDescriptors),
          inspectorSections: Object.freeze(inspectorSectionDescriptors),
        }),
        overlays: Object.freeze(overlayDescriptors),
        assetParsers: Object.freeze(assetParserDescriptors),
        outputFormats: Object.freeze(outputFormatDescriptors),
        processes: Object.freeze(processDescriptors),
        searchProviders: Object.freeze(searchProviderDescriptors),
        metadataFacets: Object.freeze(metadataFacetDescriptors),
        assetDetailSections: Object.freeze(assetDetailSectionDescriptors),
        effects: Object.freeze(effectDescriptors),
        transitions: Object.freeze(transitionDescriptors),
        shaders: Object.freeze(shaderDescriptors),
        agentTools: Object.freeze(agentToolDescriptors),
      })
    : defaultConfig;

  const enrichedPackageStateEntries = (packageStateEntries ?? []).map((entry) => {
    const ext = uniqueExtensions.find(
      (e) => (e.manifest.id as string) === entry.extensionId,
    );

    let contributionSummary: PackageContributionSummary | null = null;

    if (ext) {
      const inactiveForExt = inactiveReserved.filter(
        (r) => r.extensionId === entry.extensionId,
      ).length;
      contributionSummary = computePackageContributionSummary(
        ext.manifest.contributions,
        activeContributionScopedKeys,
        inactiveForExt,
        entry.extensionId,
      );
    } else if (entry.manifestContributions) {
      contributionSummary = computePackageContributionSummary(
        entry.manifestContributions,
      );
    }

    const summary = entry.contributionSummary ?? contributionSummary;

    return Object.freeze({
      ...entry,
      contributionSummary: summary ? Object.freeze({ ...summary }) : null,
    });
  });

  const runtime: ExtensionRuntime = Object.freeze({
    config,
    extensions: Object.freeze([...uniqueExtensions]),
    diagnostics: Object.freeze(diagnostics),
    inactiveReserved: Object.freeze(inactiveReserved),
    knownRenderIds: Object.freeze(new Set(knownRenderIds)),
    contributionIndex: routeFitContributionIndex,
    compositionGraph,
    settingsDefaults: Object.freeze(
      Object.fromEntries(
        Object.entries(settingsDefaults).map(([k, v]) => [k, Object.freeze(v)]),
      ),
    ),
    assetParsers: Object.freeze(assetParserDescriptors),
    outputFormats: Object.freeze(outputFormatDescriptors),
    processes: Object.freeze(processDescriptors),
    searchProviders: Object.freeze(searchProviderDescriptors),
    metadataFacets: Object.freeze(metadataFacetDescriptors),
    assetDetailSections: Object.freeze(assetDetailSectionDescriptors),
    effects: Object.freeze(effectDescriptors),
    transitions: Object.freeze(transitionDescriptors),
    shaders: Object.freeze(shaderDescriptors),
    agentTools: Object.freeze(agentToolDescriptors),
    requirements: Object.freeze([]),
    packageStateInventory: Object.freeze(enrichedPackageStateEntries),
  });

  return runtime;
}
