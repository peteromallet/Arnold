import type { ReactNode } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type {
  ReighExtension,
  ExtensionContribution,
  ExtensionDiagnostic,
  ContributionKind,
  ParserContribution,
  OutputFormatContribution,
  SearchProviderContribution,
  MetadataFacetContribution,
  AssetDetailSectionContribution,
  MetadataFacetValueKind,
  EffectContribution,
  TransitionContribution,
  ShaderContribution,
  ShaderFallbackBehavior,
  ShaderMaterializerDescriptor,
  ShaderPassDescriptor,
  ShaderPassKind,
  ShaderSourceDescriptor,
  ShaderTextureSchema,
  ShaderUniformSchema,
  AgentToolContribution,
  ToolResultFamily,
  RenderRoute,
  DeterminismStatus,
  RenderBlockerReason,
  RenderDependentOutputDescriptor,
  SamplingConfig,
  RenderArtifactSidecarDescriptor,
  IntegrationCapabilities,
  CapabilityRequirement,
  CapabilitySourceRef,
  ProcessContribution,
  ProcessSpec,
  ProcessOperationSpec,
} from '@reigh/editor-sdk';
import { contributionKindNotYetBridged } from '@reigh/editor-sdk';
import type { TimelineGestureOwner } from '@/tools/video-editor/lib/mobile-interaction-model';

export type VideoEditorSlotName =
  | 'header'
  | 'toolbar'
  | 'leftPanel'
  | 'rightPanel'
  | 'codePanel'
  | 'writingPanel'
  | 'stagePanel'
  | 'timelineFooter'
  | 'statusBar'
  | 'dialogs'
  | 'assetPanel'
  | 'inspectorPanel';

export interface VideoEditorRuntimeSlices {
  data: TimelineEditorDataContextValue;
  ops: TimelineEditorOpsContextValue;
  chrome: TimelineChromeContextValue;
  playback: TimelinePlaybackContextValue;
}

export interface VideoEditorRenderContext extends VideoEditorRuntimeSlices {
  provider: DataProvider;
  timelineId: string;
  timelineName: string | null;
  userId: string;
  extensions: VideoEditorExtensionRuntimeConfig;
}

export type VideoEditorVisibilityPredicate = (context: VideoEditorRenderContext) => boolean;
export type VideoEditorSlotRenderer = (context: VideoEditorRenderContext) => ReactNode;

export interface VideoEditorDialogDescriptor {
  id: string;
  order?: number;
  layer?: 'modal' | 'overlay';
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelDescriptor {
  id: string;
  placement: 'asset-panel';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorInspectorSectionDescriptor {
  id: string;
  placement: 'before-default' | 'after-default';
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorOverlayDescriptor {
  id: string;
  order?: number;
  when?: VideoEditorVisibilityPredicate;
  render: VideoEditorSlotRenderer;
}

export interface VideoEditorPanelRegistryConfig {
  panels?: readonly VideoEditorPanelDescriptor[];
  inspectorSections?: readonly VideoEditorInspectorSectionDescriptor[];
}

export interface VideoEditorDialogHostConfig {
  dialogs?: readonly VideoEditorDialogDescriptor[];
}

export interface VideoEditorExtensionConfig {
  slots?: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost?: VideoEditorDialogHostConfig;
  registry?: VideoEditorPanelRegistryConfig;
  overlays?: readonly VideoEditorOverlayDescriptor[];
}

export interface VideoEditorExtensionRuntimeConfig {
  slots: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>>;
  dialogHost: {
    dialogs: readonly VideoEditorDialogDescriptor[];
  };
  registry: {
    panels: readonly VideoEditorPanelDescriptor[];
    inspectorSections: readonly VideoEditorInspectorSectionDescriptor[];
  };
  overlays: readonly VideoEditorOverlayDescriptor[];
  /** M6: Normalized asset parser descriptors, provider-scoped and deterministically ordered. */
  assetParsers: readonly VideoEditorAssetParserDescriptor[];
  /** M6: Normalized output format descriptors (disabled diagnostics for render-dependent). */
  outputFormats: readonly VideoEditorOutputFormatDescriptor[];
  /** M12: Normalized process descriptors, declaration-only until host runtime activation. */
  processes: readonly VideoEditorProcessDescriptor[];
  /** M6: Normalized search provider descriptors, declaration-only until execution is bridged. */
  searchProviders: readonly VideoEditorSearchProviderDescriptor[];
  /** M6: Normalized metadata facet descriptors for the asset panel. */
  metadataFacets: readonly VideoEditorMetadataFacetDescriptor[];
  /** M6: Normalized asset detail section descriptors for the asset detail panel. */
  assetDetailSections: readonly VideoEditorAssetDetailSectionDescriptor[];
  /** M7: Normalized component-backed effect descriptors, provider-scoped and deterministically ordered. */
  effects: readonly VideoEditorEffectDescriptor[];
  /** M8: Normalized component-backed transition descriptors, provider-scoped and deterministically ordered. */
  transitions: readonly VideoEditorTransitionDescriptor[];
  /** M13: Normalized WebGL shader descriptors, provider-scoped and deterministically ordered. */
  shaders: readonly VideoEditorShaderDescriptor[];
  /** M10: Normalized agent tool descriptors, provider-scoped and deterministically ordered. */
  agentTools: readonly VideoEditorAgentToolDescriptor[];
}

export interface ResolvedVideoEditorPanelRegistry {
  assetPanels: readonly VideoEditorPanelDescriptor[];
  inspectorSections: {
    all: readonly VideoEditorInspectorSectionDescriptor[];
    beforeDefault: readonly VideoEditorInspectorSectionDescriptor[];
    afterDefault: readonly VideoEditorInspectorSectionDescriptor[];
  };
}

// ---------------------------------------------------------------------------
// M6: Asset parser / output format / search provider descriptors
// ---------------------------------------------------------------------------

/** A normalized asset parser descriptor produced by runtime normalization. */
export interface VideoEditorAssetParserDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  label: string;
  acceptMimeTypes?: readonly string[];
  acceptExtensions?: readonly string[];
  maxBytes?: number;
  required?: boolean;
}

/** A normalized output format descriptor produced by runtime normalization. */
export interface VideoEditorOutputFormatDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  label: string;
  requiresRender: boolean;
  outputExtension: string;
  outputMimeType?: string;
  description?: string;
  /** When true, direct compile-only execution is unavailable. */
  disabled: boolean;
  /** Reason for disabled state, surfaced in the export UI. */
  disabledReason?: string;
  /** Planner-visible routes declared by render-dependent output formats. */
  availableRoutes: readonly RenderRoute[];
  /** Render route/process requirements for planner-owned execution. */
  routeRequirements: readonly VideoEditorRouteRequirementDescriptor[];
  /** Process requirements referenced by this output format. */
  processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
  /** Declaration-time blockers that the planner should surface before execution. */
  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
  /** Suggested planner actions for making this output executable. */
  nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
  /** Aggregated capability metadata derived from the output declaration. */
  capabilities?: IntegrationCapabilities;
  /** Optional declarative sampling defaults for export configuration. */
  sampling?: SamplingConfig;
  /** Sidecar descriptors the output may produce. */
  sidecars: readonly RenderArtifactSidecarDescriptor[];
}

/** A normalized route requirement record consumed by render planning. */
export interface VideoEditorRouteRequirementDescriptor {
  routes: readonly RenderRoute[];
  requiredCapabilities: readonly string[];
  processId?: string;
  operationId?: string;
  determinism: DeterminismStatus;
  unavailableMessage?: string;
}

/** A normalized process dependency declared by an output or route. */
export interface VideoEditorProcessRequirementDescriptor {
  processId: string;
  operationId?: string;
  requiredCapabilities: readonly string[];
}

/** Declaration-time blocker metadata surfaced to the planner and UI. */
export interface VideoEditorPlannerBlockerDescriptor {
  id: string;
  extensionId: string;
  contributionId: string;
  route?: RenderRoute;
  reason: RenderBlockerReason;
  message: string;
  nextAction?: VideoEditorPlannerNextActionDescriptor;
}

/** Planner next-action metadata for resolving route/process/material blockers. */
export interface VideoEditorPlannerNextActionDescriptor {
  kind: 'select-route' | 'start-process' | 'resolve-blocker';
  label: string;
  route?: RenderRoute;
  processId?: string;
  operationId?: string;
  message?: string;
}

/** A normalized trusted-local process descriptor produced by runtime normalization. */
export interface VideoEditorProcessDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  processId: string;
  label: string;
  description?: string;
  spec: ProcessSpec;
  protocol: ProcessSpec['protocol'];
  operations: readonly ProcessOperationSpec[];
  availableRoutes: readonly RenderRoute[];
  capabilities?: IntegrationCapabilities;
  requiredBy: readonly CapabilitySourceRef[];
  blockers: readonly VideoEditorPlannerBlockerDescriptor[];
  nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
}

/** A normalized search provider descriptor produced by runtime normalization. */
export interface VideoEditorSearchProviderDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  label: string;
  description?: string;
  resultKinds?: readonly ('asset' | 'material')[];
}

/** A normalized metadata facet descriptor produced by runtime normalization. */
export interface VideoEditorMetadataFacetDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  fieldPath: string;
  displayName: string;
  valueKind: MetadataFacetValueKind;
  aggregationPosture?: 'exact' | 'range' | 'presence';
  enumValues?: readonly string[];
}

/** A normalized asset detail section descriptor produced by runtime normalization. */
export interface VideoEditorAssetDetailSectionDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  title: string;
  placement: 'before-default' | 'after-default';
  fieldPaths?: readonly string[];
  when?: string;
}

// ---------------------------------------------------------------------------
// M7: Trusted component effect descriptors
// ---------------------------------------------------------------------------

/** A normalized component-backed effect descriptor produced by runtime normalization. */
export interface VideoEditorEffectDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  /** The effect identifier that must match registerComponent calls. */
  effectId: string;
  /** Human-readable label, falling back to effectId. */
  label: string;
  /** When true, the effect contribution allows browser export. */
  allowBrowserExport: boolean;
  /** When true, the effect contribution allows worker export. */
  allowWorkerExport: boolean;
  /** Whether the contribution has component metadata (always true for active descriptors). */
  hasComponentMetadata: boolean;
}

// ---------------------------------------------------------------------------
// M8: Trusted component transition descriptors
// ---------------------------------------------------------------------------

/** A normalized component-backed transition descriptor produced by runtime normalization. */
export interface VideoEditorTransitionDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  /** The transition identifier that must match registerRenderer calls. */
  transitionId: string;
  /** Human-readable label, falling back to transitionId. */
  label: string;
  /** When true, the transition contribution allows browser export. */
  allowBrowserExport: boolean;
  /** When true, the transition contribution allows worker export. */
  allowWorkerExport: boolean;
  /** Whether the contribution has renderer metadata (always true for active descriptors). */
  hasRendererMetadata: boolean;
}

// ---------------------------------------------------------------------------
// M13: WebGL shader descriptors
// ---------------------------------------------------------------------------

/** A normalized WebGL shader descriptor produced by runtime normalization. */
export interface VideoEditorShaderDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  /** The shader identifier that must match registerShader calls. */
  shaderId: string;
  /** Human-readable label, falling back to shaderId. */
  label: string;
  description?: string;
  /** V1 shader pass scope. */
  pass: ShaderPassKind | ShaderPassDescriptor;
  source?: ShaderSourceDescriptor;
  uniforms?: ShaderUniformSchema;
  textures?: ShaderTextureSchema;
  fallback?: ShaderFallbackBehavior;
  materializer?: ShaderMaterializerDescriptor;
  /** Whether the contribution included declaration-time source metadata. */
  hasSourceMetadata: boolean;
}

// ---------------------------------------------------------------------------
// M10: Agent tool descriptors
// ---------------------------------------------------------------------------

/** A normalized agent tool descriptor produced by runtime normalization. */
export interface VideoEditorAgentToolDescriptor {
  id: string;
  extensionId: string;
  order?: number;
  /** The tool identifier used in ctx.agentTools registration calls. */
  toolId: string;
  /** Human-readable label for discovery / UI. */
  label: string;
  /** Human-readable description shown in tooltips / panel. */
  description?: string;
  /** Result families this tool can produce (empty = all accepted). */
  resultFamilies: readonly ToolResultFamily[];
  /** Whether a handler has been registered (always false at normalization time). */
  hasHandler: boolean;
}

// ---------------------------------------------------------------------------
// Host-owned runtime normalization types
// ---------------------------------------------------------------------------

/** A contribution that was declared but is not yet bridged in this runtime. */
export interface InactiveReservedContribution {
  extensionId: string;
  contributionId: string;
  kind: ContributionKind;
  /** The earliest milestone that activates this kind. */
  milestone: string;
}

/**
 * The normalized, frozen result of host-owned extension runtime normalization.
 * Produced by {@link normalizeExtensionRuntime} and scoped to a provider render.
 */
export interface ExtensionRuntime {
  /** The rendered runtime config consumed by shell chrome and slots. */
  readonly config: VideoEditorExtensionRuntimeConfig;
  /** All enabled extensions in deterministic order. */
  readonly extensions: readonly ReighExtension[];
  /** Structured diagnostics from registration (duplicates, validation, etc.). */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Contributions whose kind is not yet bridged in this runtime. */
  readonly inactiveReserved: readonly InactiveReservedContribution[];
  /** Set of contribution IDs that are known to have render declarations. */
  readonly knownRenderIds: ReadonlySet<string>;
  /** Extension-scoped settings defaults keyed by extension ID. */
  readonly settingsDefaults: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  /** M6: Normalized parser descriptors, ordered by extension order then contribution order. */
  readonly assetParsers: readonly VideoEditorAssetParserDescriptor[];
  /** M6: Output format descriptors with disabled diagnostics for render-dependent formats. */
  readonly outputFormats: readonly VideoEditorOutputFormatDescriptor[];
  /** M12: Process descriptors, declaration-only until host runtime activation. */
  readonly processes: readonly VideoEditorProcessDescriptor[];
  /** M6: Search provider descriptors, declaration-only. */
  readonly searchProviders: readonly VideoEditorSearchProviderDescriptor[];
  /** M6: Metadata facet descriptors from all extensions. */
  readonly metadataFacets: readonly VideoEditorMetadataFacetDescriptor[];
  /** M6: Asset detail section descriptors from all extensions. */
  readonly assetDetailSections: readonly VideoEditorAssetDetailSectionDescriptor[];
  /** M7: Normalized component-backed effect descriptors. */
  readonly effects: readonly VideoEditorEffectDescriptor[];
  /** M8: Normalized component-backed transition descriptors. */
  readonly transitions: readonly VideoEditorTransitionDescriptor[];
  /** M13: Normalized WebGL shader descriptors. */
  readonly shaders: readonly VideoEditorShaderDescriptor[];
  /** M10: Normalized agent tool descriptors. */
  readonly agentTools: readonly VideoEditorAgentToolDescriptor[];
}

/** Signature for host-owned runtime normalization. */
export type ExtensionHost = (extensions: readonly ReighExtension[]) => ExtensionRuntime;

const EMPTY_SLOTS: Partial<Record<VideoEditorSlotName, VideoEditorSlotRenderer>> = Object.freeze({});
const EMPTY_DIALOGS: readonly VideoEditorDialogDescriptor[] = Object.freeze([]);
const EMPTY_OVERLAYS: readonly VideoEditorOverlayDescriptor[] = Object.freeze([]);
const EMPTY_PANELS: readonly VideoEditorPanelDescriptor[] = Object.freeze([]);
const EMPTY_INSPECTOR_SECTIONS: readonly VideoEditorInspectorSectionDescriptor[] = Object.freeze([]);
const EMPTY_ASSET_PARSERS: readonly VideoEditorAssetParserDescriptor[] = Object.freeze([]);
const EMPTY_OUTPUT_FORMATS: readonly VideoEditorOutputFormatDescriptor[] = Object.freeze([]);
const EMPTY_PROCESSES: readonly VideoEditorProcessDescriptor[] = Object.freeze([]);
const EMPTY_SEARCH_PROVIDERS: readonly VideoEditorSearchProviderDescriptor[] = Object.freeze([]);
const EMPTY_METADATA_FACETS: readonly VideoEditorMetadataFacetDescriptor[] = Object.freeze([]);
const EMPTY_ASSET_DETAIL_SECTIONS: readonly VideoEditorAssetDetailSectionDescriptor[] = Object.freeze([]);
const EMPTY_EFFECTS: readonly VideoEditorEffectDescriptor[] = Object.freeze([]);
const EMPTY_TRANSITIONS: readonly VideoEditorTransitionDescriptor[] = Object.freeze([]);
const EMPTY_SHADERS: readonly VideoEditorShaderDescriptor[] = Object.freeze([]);
const EMPTY_AGENT_TOOLS: readonly VideoEditorAgentToolDescriptor[] = Object.freeze([]);
const EMPTY_RESOLVED_PANEL_REGISTRY: ResolvedVideoEditorPanelRegistry = Object.freeze({
  assetPanels: EMPTY_PANELS,
  inspectorSections: Object.freeze({
    all: EMPTY_INSPECTOR_SECTIONS,
    beforeDefault: EMPTY_INSPECTOR_SECTIONS,
    afterDefault: EMPTY_INSPECTOR_SECTIONS,
  }),
});

export const DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME: VideoEditorExtensionRuntimeConfig = Object.freeze({
  slots: EMPTY_SLOTS,
  dialogHost: Object.freeze({
    dialogs: EMPTY_DIALOGS,
  }),
  registry: Object.freeze({
    panels: EMPTY_PANELS,
    inspectorSections: EMPTY_INSPECTOR_SECTIONS,
  }),
  overlays: EMPTY_OVERLAYS,
  assetParsers: EMPTY_ASSET_PARSERS,
  outputFormats: EMPTY_OUTPUT_FORMATS,
  processes: EMPTY_PROCESSES,
  searchProviders: EMPTY_SEARCH_PROVIDERS,
  metadataFacets: EMPTY_METADATA_FACETS,
  assetDetailSections: EMPTY_ASSET_DETAIL_SECTIONS,
  effects: EMPTY_EFFECTS,
  transitions: EMPTY_TRANSITIONS,
  shaders: EMPTY_SHADERS,
  agentTools: EMPTY_AGENT_TOOLS,
});

/**
 * Host-owned runtime normalization: converts a list of ReighExtension objects
 * into a frozen, deterministic, provider-scoped {@link ExtensionRuntime}.
 *
 * - Preserves {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity when
 *   the extension list is empty or all contributions are inactive/reserved.
 * - Detects duplicate extension IDs and duplicate contribution IDs (both
 *   intra-extension and cross-extension) and emits structured diagnostics.
 * - Separates bridged M1 contributions (slot, dialog, panel, inspectorSection)
 *   from reserved future kinds (effect, transition, clipType, parser, agentTool,
 *   agent) and collects the latter as inactive reserved metadata.
 * - Orders contributions deterministically: by `order` ascending, then by
 *   contribution ID alphabetically. (Built-in priority is reserved for a
 *   future flag.)
 * - Collects known render IDs and extension-scoped settings defaults.
 * - Freezes the returned runtime and all nested objects.
 */
export function normalizeExtensionRuntime(
  extensions: readonly ReighExtension[],
): ExtensionRuntime {
  // ---- Empty fast path: preserve the default empty identity ----------------
  if (extensions.length === 0) {
    return EMPTY_EXTENSION_RUNTIME;
  }

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

  // ---- Phase 2: collect contributions, detect duplicate contribution IDs ----
  interface CollectedContribution {
    contribution: ExtensionContribution;
    extensionId: string;
  }

  const bridged: CollectedContribution[] = [];
  const inactiveReserved: InactiveReservedContribution[] = [];
  const knownRenderIds = new Set<string>();
  const settingsDefaults: Record<string, Record<string, unknown>> = {};

  // M6: Collect contributions that are reserved for execution but still
  // need to be surfaced as disabled/reserved descriptors in the runtime config.
  const m6ReservedOutputFormats: CollectedContribution[] = [];
  const m6ReservedSearchProviders: CollectedContribution[] = [];
  const m12ReservedProcesses: CollectedContribution[] = [];

  const seenContributionIds = new Map<string, string>(); // contribId -> extensionId

  for (const ext of uniqueExtensions) {
    const extId = ext.manifest.id as string;

    // Settings defaults — each extension gets its declared defaults, frozen
    settingsDefaults[extId] = ext.manifest.settingsDefaults
      ? { ...ext.manifest.settingsDefaults }
      : {};

    const contribs = ext.manifest.contributions ?? [];
    for (const contrib of contribs) {
      const contribId = contrib.id as string;

      // Cross-extension duplicate detection
      const existingOwner = seenContributionIds.get(contribId);
      if (existingOwner !== undefined) {
        diagnostics.push({
          severity: 'error',
          code: 'runtime/duplicate-contribution',
          message:
            `Duplicate contribution ID "${contribId}" in extension "${extId}" ` +
            `(already declared by "${existingOwner}"). Skipping.`,
          extensionId: extId,
          contributionId: contribId,
        });
        continue;
      }
      seenContributionIds.set(contribId, extId);

      // Check if the contribution kind is bridged in the current runtime
      const notYetBridged = contributionKindNotYetBridged(contrib.kind);

      // M7: Effect contributions with component metadata (effectId) are
      // treated as active and projected into deterministic descriptors.
      // Effects without component metadata remain inactive with diagnostics.
      if (contrib.kind === 'effect') {
        const effectContrib = contrib as unknown as EffectContribution;
        if (effectContrib.effectId) {
          // Component-backed: treat as active
          bridged.push({ contribution: contrib, extensionId: extId });
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        } else {
          // Unsupported: no component metadata — inactive with diagnostic
          inactiveReserved.push({
            extensionId: extId,
            contributionId: contribId,
            kind: contrib.kind,
            milestone: notYetBridged ?? 'unknown',
          });
          diagnostics.push({
            severity: 'warn',
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
          bridged.push({ contribution: contrib, extensionId: extId });
          if (contrib.render) {
            knownRenderIds.add(contrib.render);
          }
        } else {
          // Unsupported: no renderer metadata — inactive with diagnostic
          inactiveReserved.push({
            extensionId: extId,
            contributionId: contribId,
            kind: contrib.kind,
            milestone: notYetBridged ?? 'unknown',
          });
          diagnostics.push({
            severity: 'warn',
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
        notYetBridged !== null &&
        (contrib.kind === 'outputFormat' || contrib.kind === 'searchProvider')
      ) {
        // Add to inactive reserved for diagnostics
        inactiveReserved.push({
          extensionId: extId,
          contributionId: contribId,
          kind: contrib.kind,
          milestone: notYetBridged,
        });
        diagnostics.push({
          severity: 'info',
          code: 'runtime/contribution-kind-not-yet-bridged',
          message:
            `Contribution "${contribId}" (kind: ${contrib.kind}) in extension "${extId}" ` +
            `is reserved for ${notYetBridged}.`,
          extensionId: extId,
          contributionId: contribId,
          milestone: notYetBridged,
        });
        // Still collect known render IDs even for inactive contributions
        if (contrib.render) {
          knownRenderIds.add(contrib.render);
        }
        // Collect into the appropriate M6 reserved list for later projection
        if (contrib.kind === 'outputFormat') {
          m6ReservedOutputFormats.push({ contribution: contrib, extensionId: extId });
        } else {
          m6ReservedSearchProviders.push({ contribution: contrib, extensionId: extId });
        }
        continue;
      }
      if (notYetBridged !== null && contrib.kind === 'process') {
        inactiveReserved.push({
          extensionId: extId,
          contributionId: contribId,
          kind: contrib.kind,
          milestone: notYetBridged,
        });
        diagnostics.push({
          severity: 'info',
          code: 'runtime/contribution-kind-not-yet-bridged',
          message:
            `Contribution "${contribId}" (kind: ${contrib.kind}) in extension "${extId}" ` +
            `is reserved for ${notYetBridged}.`,
          extensionId: extId,
          contributionId: contribId,
          milestone: notYetBridged,
        });
        if (contrib.render) {
          knownRenderIds.add(contrib.render);
        }
        m12ReservedProcesses.push({ contribution: contrib, extensionId: extId });
        continue;
      }
      if (notYetBridged !== null) {
        inactiveReserved.push({
          extensionId: extId,
          contributionId: contribId,
          kind: contrib.kind,
          milestone: notYetBridged,
        });
        diagnostics.push({
          severity: 'info',
          code: 'runtime/contribution-kind-not-yet-bridged',
          message:
            `Contribution "${contribId}" (kind: ${contrib.kind}) in extension "${extId}" ` +
            `is reserved for ${notYetBridged}.`,
          extensionId: extId,
          contributionId: contribId,
          milestone: notYetBridged,
        });
        // Still collect known render IDs even for inactive contributions
        if (contrib.render) {
          knownRenderIds.add(contrib.render);
        }
        continue;
      }

      bridged.push({ contribution: contrib, extensionId: extId });

      // Track known render IDs
      if (contrib.render) {
        knownRenderIds.add(contrib.render);
      }
    }
  }

  // ---- Phase 3: deterministic ordering -------------------------------------
  // Sort by extension order (primary), then contribution order ascending,
  // then contribution ID alphabetically (stable tiebreaker).
  const sorted = [...bridged].sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;
    const orderA = a.contribution.order ?? 0;
    const orderB = b.contribution.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return (a.contribution.id as string).localeCompare(b.contribution.id as string);
  });

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

  for (const { contribution, extensionId } of sorted) {
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
      // M6: metadataFacet — bridge into metadataFacets
      case 'metadataFacet': {
        const facetContrib = contribution as unknown as MetadataFacetContribution;
        metadataFacetDescriptors.push({
          id: contribution.id as string,
          extensionId,
          order: contribution.order,
          fieldPath: facetContrib.fieldPath,
          displayName: facetContrib.displayName,
          valueKind: facetContrib.valueKind,
          aggregationPosture: facetContrib.aggregationPosture,
          enumValues: facetContrib.enumValues,
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
    : DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME;

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
  });

  return runtime;
}

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

/** Frozen empty runtime, preserving {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity. */
const EMPTY_EXTENSION_RUNTIME: ExtensionRuntime = Object.freeze({
  config: DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
  extensions: Object.freeze([]),
  diagnostics: Object.freeze([]),
  inactiveReserved: Object.freeze([]),
  knownRenderIds: Object.freeze(new Set<string>()),
  settingsDefaults: Object.freeze({}),
  assetParsers: EMPTY_ASSET_PARSERS,
  outputFormats: EMPTY_OUTPUT_FORMATS,
  processes: EMPTY_PROCESSES,
  searchProviders: EMPTY_SEARCH_PROVIDERS,
  metadataFacets: EMPTY_METADATA_FACETS,
  assetDetailSections: EMPTY_ASSET_DETAIL_SECTIONS,
  effects: EMPTY_EFFECTS,
  transitions: EMPTY_TRANSITIONS,
  shaders: EMPTY_SHADERS,
  agentTools: EMPTY_AGENT_TOOLS,
});

type RegistryDescriptor = {
  id: string;
  order?: number;
  when?: VideoEditorVisibilityPredicate;
};

function sortRegistryDescriptors<T extends RegistryDescriptor>(descriptors: readonly T[]) {
  return [...descriptors].sort((left, right) => {
    const leftOrder = left.order ?? 0;
    const rightOrder = right.order ?? 0;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }

    return left.id.localeCompare(right.id);
  });
}

function resolveVisibleRegistryDescriptors<T extends RegistryDescriptor>(
  descriptors: readonly T[],
  context: VideoEditorRenderContext,
) {
  if (descriptors.length === 0) {
    return EMPTY_PANELS as unknown as readonly T[];
  }

  return sortRegistryDescriptors(
    descriptors.filter((descriptor) => !descriptor.when || descriptor.when(context)),
  );
}

export function resolveVideoEditorPanelRegistry(
  registry: VideoEditorExtensionRuntimeConfig['registry'],
  context: VideoEditorRenderContext,
): ResolvedVideoEditorPanelRegistry {
  const assetPanels = resolveVisibleRegistryDescriptors(registry.panels, context);
  const inspectorSections = resolveVisibleRegistryDescriptors(registry.inspectorSections, context);

  if (assetPanels.length === 0 && inspectorSections.length === 0) {
    return EMPTY_RESOLVED_PANEL_REGISTRY;
  }

  const beforeDefault = inspectorSections.filter((descriptor) => descriptor.placement === 'before-default');
  const afterDefault = inspectorSections.filter((descriptor) => descriptor.placement === 'after-default');

  return {
    assetPanels,
    inspectorSections: {
      all: inspectorSections,
      beforeDefault,
      afterDefault,
    },
  };
}

// ---------------------------------------------------------------------------
// getInspectorContributions — canonical selector for inspector consumers
// ---------------------------------------------------------------------------

/** Selection context supplied by the host to inspector contributions. */
export interface InspectorSelectionSnapshot {
  /** Discriminated kind of the current selection. */
  readonly kind: 'clip' | 'selection' | 'track' | 'timeline' | 'shader';
  /** Single clip ID when kind === 'clip'. */
  readonly clipId?: string;
  /** Multiple clip IDs when kind === 'selection'. */
  readonly clipIds?: readonly string[];
  /** Track ID when kind === 'track'. */
  readonly trackId?: string;
  /** Shader scope when kind === 'shader'. */
  readonly shaderScope?: 'clip' | 'postprocess';
  /** Shader ID when kind === 'shader'. */
  readonly shaderId?: string;
  /** Owning extension ID when kind === 'shader'. */
  readonly extensionId?: string;
  /** Contribution ID when kind === 'shader'. */
  readonly contributionId?: string;
}

/** A resolved, selection-aware inspector contribution ready for rendering. */
export interface InspectorContribution {
  readonly id: string;
  readonly placement: 'before-default' | 'after-default';
  readonly order?: number;
  /** Render the contribution with full host context and the current selection snapshot. */
  readonly render: (
    context: VideoEditorRenderContext,
    selection: InspectorSelectionSnapshot | null,
  ) => ReactNode;
}

/**
 * Canonical selector that resolves inspector contributions scoped to the
 * current host state.
 *
 * Consumed by the PropertiesPanel and any other inspector host surfaces.
 * Delegates to {@link resolveVideoEditorPanelRegistry} for visibility
 * filtering and deterministic ordering.
 *
 * @returns frozen-structured buckets keyed by placement.
 */
export function getInspectorContributions(
  registry: VideoEditorExtensionRuntimeConfig['registry'],
  context: VideoEditorRenderContext,
  _selection: InspectorSelectionSnapshot | null,
): {
  readonly all: readonly InspectorContribution[];
  readonly beforeDefault: readonly InspectorContribution[];
  readonly afterDefault: readonly InspectorContribution[];
} {
  const resolved = resolveVideoEditorPanelRegistry(registry, context);

  // Map inspector section descriptors to InspectorContribution wrappers
  // that forward selection alongside the render context.
  const wrap = (descriptor: VideoEditorInspectorSectionDescriptor): InspectorContribution => {
    const originalRender = descriptor.render;
    return {
      id: descriptor.id,
      placement: descriptor.placement,
      order: descriptor.order,
      render: (ctx, _sel) => originalRender(ctx),
    };
  };

  const all = resolved.inspectorSections.all.map(wrap);
  const beforeDefault = resolved.inspectorSections.beforeDefault.map(wrap);
  const afterDefault = resolved.inspectorSections.afterDefault.map(wrap);

  // Preserve empty array identity for stable React memo comparisons
  if (all.length === 0) {
    return {
      all: EMPTY_INSPECTOR_CONTRIBUTIONS,
      beforeDefault: EMPTY_INSPECTOR_CONTRIBUTIONS,
      afterDefault: EMPTY_INSPECTOR_CONTRIBUTIONS,
    };
  }

  return { all, beforeDefault, afterDefault };
}

const EMPTY_INSPECTOR_CONTRIBUTIONS: readonly InspectorContribution[] = Object.freeze([]);

// ---------------------------------------------------------------------------
// Timeline overlay — host rendering contract
// ---------------------------------------------------------------------------

/** Viewport and interaction policy props the host passes to each overlay renderer. */
export interface TimelineOverlayRenderProps {
  /** Current horizontal scroll offset (px). */
  readonly scrollLeft: number;
  /** Current vertical scroll offset (px). */
  readonly scrollTop: number;
  /** Width of the visible viewport (px). */
  readonly viewportWidth: number;
  /** Height of the visible viewport (px). */
  readonly viewportHeight: number;
  /** Total scrollable width (px). */
  readonly totalWidth: number;
  /** Total scrollable height (px). */
  readonly totalHeight: number;
  /** Pixels per second of timeline (scale-derived). */
  readonly pixelsPerSecond: number;
  /** Left offset where timeline content begins (px). */
  readonly startLeft: number;
  /** Current playhead position in seconds. */
  readonly playheadTime: number;
  /** Whether playback is active. */
  readonly isPlaying: boolean;
  /** Currently selected clip IDs. */
  readonly selectedClipIds: ReadonlySet<string>;
  /** Currently selected track ID (null if none). */
  readonly selectedTrackId: string | null;
  /** Which subsystem currently owns the gesture. */
  readonly gestureOwner: TimelineGestureOwner;
  /** Callback to request gesture ownership. */
  readonly setGestureOwner: (owner: TimelineGestureOwner) => void;
  /** Whether this overlay currently claims pointer events. */
  readonly pointerClaimed: boolean;
  /** Claim pointer events for this overlay (makes it pointer-events-auto). */
  readonly claimPointer: () => void;
  /** Release pointer events for this overlay (reverts to pointer-events-none). */
  readonly releasePointer: () => void;
}

/** A resolved timeline overlay contribution ready for rendering. */
export interface TimelineOverlayContribution {
  readonly id: string;
  readonly extensionId: string;
  readonly order?: number;
  /** Render the overlay with host-supplied viewport and interaction policy props. */
  readonly render: (props: TimelineOverlayRenderProps) => ReactNode;
}

const EMPTY_TIMELINE_OVERLAY_CONTRIBUTIONS: readonly TimelineOverlayContribution[] = Object.freeze([]);

/**
 * Canonical selector for timeline overlay contributions.
 *
 * Overlays render above the edit area in TimelineEditorCore / TimelineCanvas.
 * They default to `pointer-events: none` and must call `claimPointer()` to
 * capture pointer or scroll gestures, preventing accidental interference
 * with core timeline interactions.
 */
export function getTimelineOverlayContributions(
  overlays: readonly VideoEditorOverlayDescriptor[],
  overlayRenderProps: Omit<
    TimelineOverlayRenderProps,
    'pointerClaimed' | 'claimPointer' | 'releasePointer'
  > & {
    claimPointer: (overlayId: string) => void;
    releasePointer: (overlayId: string) => void;
  },
  claimedOverlayId: string | null,
): readonly TimelineOverlayContribution[] {
  if (overlays.length === 0) {
    return EMPTY_TIMELINE_OVERLAY_CONTRIBUTIONS;
  }

  const contributions: TimelineOverlayContribution[] = overlays.map((descriptor) => {
    const pointerClaimed = claimedOverlayId === descriptor.id;

    const _renderProps: TimelineOverlayRenderProps = {
      ...overlayRenderProps,
      pointerClaimed,
      claimPointer: () => overlayRenderProps.claimPointer(descriptor.id),
      releasePointer: () => overlayRenderProps.releasePointer(descriptor.id),
    };

    return {
      id: descriptor.id,
      extensionId: '',
      order: descriptor.order,
      render: () => (descriptor.render ? descriptor.render(null as unknown as VideoEditorRenderContext) : null),
    };
  });

  return contributions;
}
