/**
 * Family runtime assembly — Phase 4–5 of host-owned runtime normalization.
 *
 * This module builds a frozen, deterministic {@link ExtensionRuntime} from
 * the contribution sequence produced by {@link buildFamilyContributionSequence}.
 * It is intentionally a pure data function — it does not consult the adapter
 * registry, the projection policy, or any host runtime state.
 *
 * Real adapters (metadataFacet, and later effect, transition, shader, etc.)
 * own their normalization; this module delegates to them instead of
 * projecting contributions inline.
 *
 * @module families/FamilyRuntimeAssembly
 */

import type {
  ContributionKind,
  ExtensionContribution,
  ExtensionDiagnostic,
  ParserContribution,
  OutputFormatContribution,
  SearchProviderContribution,
  MetadataFacetContribution,
  AssetDetailSectionContribution,
  EffectContribution,
  TransitionContribution,
  ShaderContribution,
  AgentToolContribution,
  ProcessContribution,
  RenderDependentOutputDescriptor,
  IntegrationCapabilities,
  CapabilityRequirement,
  CapabilitySourceRef,
  ToolResultFamily,
} from '@reigh/editor-sdk';
import { findAdapter } from '@reigh/editor-sdk';
import type { FamilyAdapterRegistry, HostFamilyAdapter } from '@reigh/editor-sdk';
import type { FamilyContributionSequence } from './FamilyContributionSequence';
import { metadataFacetAdapter } from './metadataFacetAdapter';
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
  VideoEditorRouteRequirementDescriptor,
  VideoEditorProcessRequirementDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorPlannerNextActionDescriptor,
  PackageStateInventoryEntry,
  InactiveReservedContribution,
} from '../extensionSurface';

// ---------------------------------------------------------------------------
// Contribution kind labels
// ---------------------------------------------------------------------------

/** Short human-readable label for each contribution kind. */
const CONTRIBUTION_KIND_LABEL: Partial<Record<ContributionKind, string>> = {
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
// Main assembly function
// ---------------------------------------------------------------------------

/**
 * Phase 4–5 of host-owned runtime normalization: project the sequenced
 * contributions into runtime descriptors, assemble the frozen
 * {@link ExtensionRuntime}, and compute package contribution summaries.
 *
 * When an `adapterRegistry` is provided, family kinds that have real
 * adapters registered are normalized through the adapter coordinator
 * instead of inline projection.  Currently only `metadataFacet` is
 * routed this way; all other families remain inline.
 *
 * @param seq - The contribution sequence from Phase 1–3.
 * @param packageStateEntries - Optional package-state inventory entries.
 * @param defaultConfig - The default config to use when no configurable
 *   contributions exist (pass {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME}
 *   to preserve identity).
 * @param adapterRegistry - Optional adapter registry for coordinator-backed
 *   family normalization.  When absent, falls back to direct adapter import.
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
    sortedBridged: sorted,
    m6ReservedOutputFormats,
    m6ReservedSearchProviders,
    m12ReservedProcesses,
  } = seq;

  // ---- Phase 4: project onto VideoEditorExtensionRuntimeConfig --------------
  const slots: Record<string, VideoEditorSlotRenderer> = {};
  const dialogDescriptors: VideoEditorDialogDescriptor[] = [];
  const panelDescriptors: VideoEditorPanelDescriptor[] = [];
  const inspectorSectionDescriptors: VideoEditorInspectorSectionDescriptor[] = [];
  const overlayDescriptors: VideoEditorOverlayDescriptor[] = [];
  const assetParserDescriptors: VideoEditorAssetParserDescriptor[] = [];
  const metadataFacetDescriptors: VideoEditorMetadataFacetDescriptor[] = [];
  const assetDetailSectionDescriptors: VideoEditorAssetDetailSectionDescriptor[] = [];
  const effectDescriptors: VideoEditorEffectDescriptor[] = [];
  const transitionDescriptors: VideoEditorTransitionDescriptor[] = [];
  const shaderDescriptors: VideoEditorShaderDescriptor[] = [];
  const agentToolDescriptors: VideoEditorAgentToolDescriptor[] = [];

  // ---- Separate metadataFacet contributions for adapter-owned normalization --
  const metadataFacetContributions = sorted.filter(
    (c) => c.contribution.kind === 'metadataFacet',
  );
  const nonMetadataFacet = sorted.filter(
    (c) => c.contribution.kind !== 'metadataFacet',
  );

  for (const { contribution, extensionId } of nonMetadataFacet) {
    switch (contribution.kind) {
      case 'slot': {
        if (contribution.slot) {
          // Slots are rendered by the host; we register a placeholder that
          // extension activation can replace with a real render function.
          // For now, slots collect metadata without render functions.
          // (Render functions are wired during activation in a later task.)
          slots[contribution.slot] = slots[contribution.slot] ?? (null as unknown as VideoEditorSlotRenderer);
        }
        break;
      }
      case 'dialog': {
        dialogDescriptors.push({
          id: contribution.id as VideoEditorDialogDescriptor['id'],
          order: contribution.order,
          layer: contribution.layer,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      case 'panel': {
        panelDescriptors.push({
          id: contribution.id as VideoEditorPanelDescriptor['id'],
          placement: 'asset-panel',
          order: contribution.order,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      case 'inspectorSection': {
        inspectorSectionDescriptors.push({
          id: contribution.id as VideoEditorInspectorSectionDescriptor['id'],
          placement: contribution.placement ?? 'after-default',
          order: contribution.order,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      case 'timelineOverlay': {
        overlayDescriptors.push({
          id: contribution.id as VideoEditorOverlayDescriptor['id'],
          order: contribution.order,
          render: null as unknown as VideoEditorSlotRenderer, // placeholder
        });
        break;
      }
      // M6: parser — bridge parser contributions into assetParsers
      case 'parser': {
        const parserContrib = contribution as unknown as ParserContribution;
        assetParserDescriptors.push({
          id: contribution.id as string,
          extensionId,
          order: contribution.order,
          label: parserContrib.label ?? contribution.id as string,
          acceptMimeTypes: parserContrib.acceptMimeTypes,
          acceptExtensions: parserContrib.acceptExtensions,
          maxBytes: parserContrib.maxBytes,
          required: parserContrib.required,
        });
        break;
      }
      // M6: assetDetailSection — bridge into assetDetailSections
      case 'assetDetailSection': {
        const sectionContrib = contribution as unknown as AssetDetailSectionContribution;
        assetDetailSectionDescriptors.push({
          id: contribution.id as string,
          extensionId,
          order: contribution.order,
          title: sectionContrib.title,
          placement: sectionContrib.placement,
          fieldPaths: sectionContrib.fieldPaths,
          when: sectionContrib.when,
        });
        break;
      }
      // M7: effect — bridge component-backed effects into effects
      case 'effect': {
        const effectContrib = contribution as unknown as EffectContribution;
        if (effectContrib.effectId) {
          effectDescriptors.push({
            id: contribution.id as string,
            extensionId,
            order: contribution.order,
            effectId: effectContrib.effectId,
            label: effectContrib.label ?? effectContrib.effectId,
            allowBrowserExport: effectContrib.allowBrowserExport ?? false,
            allowWorkerExport: effectContrib.allowWorkerExport ?? false,
            hasComponentMetadata: true,
          });
        }
        // Effects without effectId are filtered in Phase 2; they never reach here.
        break;
      }
      // M8: transition — bridge renderer-backed transitions into transitions
      case 'transition': {
        const transitionContrib = contribution as unknown as TransitionContribution;
        if (transitionContrib.transitionId) {
          transitionDescriptors.push({
            id: contribution.id as string,
            extensionId,
            order: contribution.order,
            transitionId: transitionContrib.transitionId,
            label: transitionContrib.label ?? transitionContrib.transitionId,
            allowBrowserExport: transitionContrib.allowBrowserExport ?? false,
            allowWorkerExport: transitionContrib.allowWorkerExport ?? false,
            hasRendererMetadata: true,
          });
        }
        // Transitions without transitionId are filtered in Phase 2; they never reach here.
        break;
      }
      // M13: shader — bridge dedicated WebGL shader contributions into shaders
      case 'shader': {
        const shaderContrib = contribution as unknown as ShaderContribution;
        if (shaderContrib.shaderId) {
          shaderDescriptors.push({
            id: contribution.id as string,
            extensionId,
            order: contribution.order,
            shaderId: shaderContrib.shaderId,
            label: shaderContrib.label ?? shaderContrib.shaderId,
            description: shaderContrib.description,
            pass: shaderContrib.pass,
            source: shaderContrib.source,
            uniforms: shaderContrib.uniforms,
            textures: shaderContrib.textures,
            fallback: shaderContrib.fallback,
            materializer: shaderContrib.materializer,
            hasSourceMetadata: shaderContrib.source !== undefined,
          });
        } else {
          diagnostics.push({
            severity: 'error',
            code: 'runtime/shader-missing-shader-id',
            message:
              `Shader contribution "${contribution.id as string}" in extension "${extensionId}" ` +
              'has no shaderId. The shader will be inactive.',
            extensionId,
            contributionId: contribution.id as string,
          });
        }
        break;
      }
      // M10: agentTool — bridge agent tool contributions into agentTools
      case 'agentTool': {
        const at = contribution as unknown as AgentToolContribution;
        agentToolDescriptors.push({
          id: contribution.id as string,
          extensionId,
          order: contribution.order,
          toolId: at.toolId,
          label: at.label,
          description: at.description,
          resultFamilies: (at.resultFamilies ?? []) as readonly ToolResultFamily[],
          hasHandler: false,
        });
        break;
      }
      default:
        // Unknown bridged kinds are silently skipped (should not occur)
        break;
    }
  }

  // ---- Adapter-owned normalization: metadataFacet ----------------------------
  // Route through the adapter coordinator when a registry is available;
  // fall back to the direct adapter import for callers that haven't wired
  // the registry yet (backwards compatibility).
  if (metadataFacetContributions.length > 0) {
    if (adapterRegistry) {
      const adapter = findAdapter(adapterRegistry, 'metadataFacet');
      if (adapter && adapter !== null) {
        // The coordinator returns a generic HostFamilyAdapter; narrow to the
        // metadataFacet shape so we can call normalize().
        const facetAdapter = adapter as unknown as typeof metadataFacetAdapter;
        metadataFacetDescriptors.push(
          ...facetAdapter.normalize(metadataFacetContributions),
        );
      }
    } else {
      // No registry — fall back to direct adapter import (backwards compat).
      metadataFacetDescriptors.push(
        ...metadataFacetAdapter.normalize(metadataFacetContributions),
      );
    }
  }

  // ---- Phase 4b: project M6 reserved contributions --------------------------
  // OutputFormat: surfaced with planner metadata for render-dependent formats.
  const outputFormatDescriptors: VideoEditorOutputFormatDescriptor[] = [];
  for (const { contribution, extensionId } of m6ReservedOutputFormats) {
    const of = contribution as unknown as OutputFormatContribution;
    const requiresRender = of.requiresRender ?? false;
    const renderDescriptor = requiresRender ? of.render : undefined;
    const routeRequirements = buildRouteRequirements(renderDescriptor);
    const processRequirements = buildProcessRequirements(renderDescriptor);
    const blockers = buildOutputFormatBlockers(extensionId, contribution.id as string, of, renderDescriptor);
    const nextActions = buildOutputFormatNextActions(of, renderDescriptor, blockers);
    const capabilities = buildOutputFormatCapabilities(extensionId, contribution.id as string, of, renderDescriptor, blockers);
    outputFormatDescriptors.push({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      label: of.label ?? contribution.id as string,
      requiresRender,
      outputExtension: of.outputExtension,
      outputMimeType: of.outputMimeType,
      description: of.description,
      disabled: false,
      disabledReason: undefined,
      availableRoutes: Object.freeze([...(renderDescriptor?.routes ?? [])]),
      routeRequirements,
      processRequirements,
      blockers,
      nextActions,
      capabilities,
      sampling: of.sampling,
      sidecars: Object.freeze([...(of.sidecars ?? [])]),
    });
  }

  // Order output formats by extension order, then contribution order, then ID
  outputFormatDescriptors.sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;
    const orderA = a.order ?? 0;
    const orderB = b.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return a.id.localeCompare(b.id);
  });

  // Process: surfaced as planner-visible declarations without runtime spawn.
  const processDescriptors: VideoEditorProcessDescriptor[] = [];
  for (const { contribution, extensionId } of m12ReservedProcesses) {
    const processContrib = contribution as unknown as ProcessContribution;
    const spec = processContrib.spec;
    const operations = Object.freeze([...(spec.operations ?? [])]);
    const availableRoutes = Object.freeze(
      Array.from(new Set(operations.flatMap((operation) => operation.routes ?? []))),
    );
    processDescriptors.push({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      processId: spec.id,
      label: processContrib.label ?? spec.label ?? spec.id,
      description: spec.description,
      spec,
      protocol: spec.protocol,
      operations,
      availableRoutes,
      capabilities: spec.capabilities,
      requiredBy: Object.freeze([...(spec.requiredBy ?? [])]),
      blockers: Object.freeze([]),
      nextActions: Object.freeze([
        {
          kind: 'start-process',
          label: `Start ${processContrib.label ?? spec.label ?? spec.id}`,
          processId: spec.id,
          message: 'Process execution is host-owned and must be activated before route planning can dispatch operations.',
        },
      ]),
    });
  }

  processDescriptors.sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;
    const orderA = a.order ?? 0;
    const orderB = b.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return a.id.localeCompare(b.id);
  });

  // SearchProvider: surfaced as declaration-only descriptors
  const searchProviderDescriptors: VideoEditorSearchProviderDescriptor[] = [];
  for (const { contribution, extensionId } of m6ReservedSearchProviders) {
    const sp = contribution as unknown as SearchProviderContribution;
    searchProviderDescriptors.push({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      label: sp.label ?? contribution.id as string,
      description: sp.description,
      resultKinds: sp.resultKinds,
    });
  }

  // Order search providers by extension order, then contribution order, then ID
  searchProviderDescriptors.sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;
    const orderA = a.order ?? 0;
    const orderB = b.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return a.id.localeCompare(b.id);
  });

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
    // Try to find the matching active extension for this package
    const ext = uniqueExtensions.find(
      (e) => (e.manifest.id as string) === entry.extensionId,
    );
    
    let contributionSummary: PackageContributionSummary | null = null;
    
    if (ext) {
      // Active extension: derive full summary from manifest + runtime
      const inactiveForExt = inactiveReserved.filter(
        (r) => r.extensionId === entry.extensionId,
      ).length;
      contributionSummary = computePackageContributionSummary(
        ext.manifest.contributions,
        activeContributionIds,
        inactiveForExt,
      );
    } else if (entry.manifestContributions) {
      // Non-active package: derive from preserved manifest contributions
      contributionSummary = computePackageContributionSummary(
        entry.manifestContributions,
      );
    }
    
    // Keep any preexisting contributionSummary if already set by caller
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

// ---------------------------------------------------------------------------
// Output-format planner helpers
// ---------------------------------------------------------------------------

function buildRouteRequirements(
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorRouteRequirementDescriptor[] {
  if (!renderDescriptor) return Object.freeze([]);

  return Object.freeze([
    Object.freeze({
      routes: Object.freeze([...renderDescriptor.routes]),
      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      determinism: renderDescriptor.determinism ?? 'unknown',
      unavailableMessage: renderDescriptor.unavailableMessage,
    }),
  ]);
}

function buildProcessRequirements(
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorProcessRequirementDescriptor[] {
  if (!renderDescriptor?.processId) return Object.freeze([]);

  return Object.freeze([
    Object.freeze({
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
    }),
  ]);
}

function buildOutputFormatBlockers(
  extensionId: string,
  contributionId: string,
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorPlannerBlockerDescriptor[] {
  if (!contribution.requiresRender || renderDescriptor) return Object.freeze([]);

  const nextAction: VideoEditorPlannerNextActionDescriptor = Object.freeze({
    kind: 'resolve-blocker',
    label: 'Add render route requirements',
    message: 'Render-dependent output formats must declare render routes before planning can execute them.',
  });

  return Object.freeze([
    Object.freeze({
      id: `${extensionId}.${contributionId}.missing-render-descriptor`,
      extensionId,
      contributionId,
      reason: 'route-unsupported',
      message: `Output format "${contribution.label ?? contributionId}" requires render planning but did not declare route requirements.`,
      nextAction,
    }),
  ]);
}

function buildOutputFormatNextActions(
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  if (!contribution.requiresRender) return Object.freeze([]);
  if (blockers[0]?.nextAction) return Object.freeze([blockers[0].nextAction]);

  const actions: VideoEditorPlannerNextActionDescriptor[] = [];
  if (renderDescriptor?.processId) {
    actions.push(Object.freeze({
      kind: 'start-process',
      label: `Start process ${renderDescriptor.processId}`,
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      message: renderDescriptor.unavailableMessage,
    }));
  }

  for (const route of renderDescriptor?.routes ?? []) {
    actions.push(Object.freeze({
      kind: 'select-route',
      label: `Plan ${route}`,
      route,
      processId: renderDescriptor?.processId,
      operationId: renderDescriptor?.operationId,
      message: renderDescriptor?.unavailableMessage,
    }));
  }

  return Object.freeze(actions);
}

function buildOutputFormatCapabilities(
  extensionId: string,
  contributionId: string,
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
): IntegrationCapabilities | undefined {
  const sourceRef: CapabilitySourceRef = Object.freeze({
    source: 'extension',
    extensionId,
    contributionId,
  });

  if (!contribution.requiresRender) {
    return Object.freeze({
      extensionId,
      contributionId,
      routes: Object.freeze([]),
      determinism: 'deterministic',
      capabilityRequirements: Object.freeze([]),
      sourceRefs: Object.freeze([sourceRef]),
      fullySupported: true,
      anyBlocked: false,
    });
  }

  const routes = Object.freeze([...(renderDescriptor?.routes ?? [])]);
  const determinism = renderDescriptor?.determinism ?? 'unknown';
  const requiredCapabilities = Object.freeze([...(renderDescriptor?.requiredCapabilities ?? [])]);
  const routeFit = renderDescriptor
    ? undefined
    : Object.freeze({
        route: 'sidecar-export' as const,
        fit: 'blocked' as const,
        reason: 'route-unsupported' as const,
        message: blockers[0]?.message,
      });

  const capabilityRequirements: CapabilityRequirement[] = routes.map((route) => Object.freeze({
    id: `${extensionId}.${contributionId}.${route}`,
    sourceRef,
    route,
    requiredCapabilities,
    determinism,
    routeFit: Object.freeze({
      route,
      fit: 'supported' as const,
      message: renderDescriptor?.unavailableMessage,
    }),
    blocking: false,
  }));

  if (!renderDescriptor) {
    capabilityRequirements.push(Object.freeze({
      id: `${extensionId}.${contributionId}.missing-render-descriptor`,
      sourceRef,
      route: 'sidecar-export',
      requiredCapabilities: Object.freeze([]),
      determinism: 'unknown',
      routeFit,
      findings: Object.freeze(blockers.map((blocker) => Object.freeze({
        id: blocker.id,
        severity: 'error' as const,
        route: blocker.route,
        reason: blocker.reason,
        message: blocker.message,
        extensionId: blocker.extensionId,
        contributionId: blocker.contributionId,
      }))),
      blocking: true,
    }));
  }

  return Object.freeze({
    extensionId,
    contributionId,
    routes,
    determinism,
    capabilityRequirements: Object.freeze(capabilityRequirements),
    sourceRefs: Object.freeze([sourceRef]),
    fullySupported: blockers.length === 0,
    anyBlocked: blockers.length > 0,
  });
}
