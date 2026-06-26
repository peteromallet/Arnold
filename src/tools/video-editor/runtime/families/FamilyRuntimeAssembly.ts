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

import type { ExtensionContribution } from '@reigh/editor-sdk';
import type {
  HostFamilyAdapter,
  FamilyAdapterRegistry,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
} from '@reigh/editor-sdk';
import type { FamilyContributionSequence } from './FamilyContributionSequence';
import { VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY } from './familyAdapterRegistry';
import type {
  ExtensionRuntime,
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
import type { VideoEditorSlotDescriptor } from './slotAdapter';

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
 * When `activeIds` is provided, contributions whose ID appears in the set are
 * counted as active.  When `inactiveCount` is provided, it is used as the
 * inactive count.  Both are optional and default to -1 (unknown) when absent.
 */
export function computePackageContributionSummary(
  manifestContributions: readonly ExtensionContribution[] | undefined | null,
  activeIds?: ReadonlySet<string>,
  inactiveCount?: number,
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
  if (activeIds) {
    active = 0;
    for (const contrib of contribs) {
      if (activeIds.has(contrib.id as string)) {
        active++;
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

  // ---- Phase 4: collect contributions by dispatch source --------------------
  const byKind: Record<string, { kind: string; contributions: typeof sortedBridged }> = {};

  function pushToKind(kind: string, item: (typeof sortedBridged)[number]) {
    if (!byKind[kind]) {
      byKind[kind] = { kind, contributions: [] };
    }
    byKind[kind].contributions.push(item);
  }

  for (const item of sortedBridged) {
    pushToKind(item.contribution.kind, item);
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

  function getReservedContributions(kind: string): typeof sortedBridged {
    if (kind === 'outputFormat') return m6ReservedOutputFormats;
    if (kind === 'searchProvider') return m6ReservedSearchProviders;
    if (kind === 'process') return m12ReservedProcesses;
    return [];
  }

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
        ? byKind[kind]?.contributions ?? []
        : getReservedContributions(kind);

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
      for (const descriptor of result.descriptors as VideoEditorSlotDescriptor[]) {
        if (descriptor.slot && !slots[descriptor.slot]) {
          slots[descriptor.slot] = descriptor.render;
        }
      }
      continue;
    }

    const target = getDescriptorArray(config.field);
    if (target) {
      target.push(...(result.descriptors as unknown[]));
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

  // ---- Compute contribution summaries for package state inventory ---------
  const activeContributionIds = new Set<string>();
  for (const key of Object.keys(slots)) activeContributionIds.add(key);
  for (const d of dialogDescriptors) activeContributionIds.add(d.id);
  for (const p of panelDescriptors) activeContributionIds.add(p.id);
  for (const s of inspectorSectionDescriptors) activeContributionIds.add(s.id);
  for (const o of overlayDescriptors) activeContributionIds.add(o.id);
  for (const ap of assetParserDescriptors) activeContributionIds.add(ap.id);
  for (const of_ of outputFormatDescriptors) activeContributionIds.add(of_.id);
  for (const sp of searchProviderDescriptors) activeContributionIds.add(sp.id);
  for (const mf of metadataFacetDescriptors) activeContributionIds.add(mf.id);
  for (const ads of assetDetailSectionDescriptors) activeContributionIds.add(ads.id);
  for (const eff of effectDescriptors) activeContributionIds.add(eff.id);
  for (const tr of transitionDescriptors) activeContributionIds.add(tr.id);
  for (const sh of shaderDescriptors) activeContributionIds.add(sh.id);
  for (const at of agentToolDescriptors) activeContributionIds.add(at.id);
  for (const pr of processDescriptors) activeContributionIds.add(pr.id);

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
        activeContributionIds,
        inactiveForExt,
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
