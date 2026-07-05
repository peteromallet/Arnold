import type { ReactNode } from 'react';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  TimelineChromeContextValue,
  TimelineEditorDataContextValue,
  TimelineEditorOpsContextValue,
  TimelinePlaybackContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import type {
  CompositionGraph,
  ReighExtension,
  ExtensionContribution,
  ExtensionDiagnostic,
  ContributionKind,
  MetadataFacetValueKind,
  RouteFitMetadata,
  ShaderFallbackBehavior,
  ShaderMaterializerDescriptor,
  ShaderPassDescriptor,
  ShaderPassKind,
  ShaderSourceDescriptor,
  ShaderTextureSchema,
  ShaderUniformSchema,
  ToolResultFamily,
  RenderRoute,
  DeterminismStatus,
  RenderBlockerReason,
  SamplingConfig,
  RenderArtifactSidecarDescriptor,
  IntegrationCapabilities,
  CapabilitySourceRef,
  ProcessSpec,
  ProcessOperationSpec,
  ProjectExtensionRequirement,
} from '@reigh/editor-sdk';
import { buildFamilyContributionSequence } from '@/tools/video-editor/runtime/families/FamilyContributionSequence.ts';
import { assembleExtensionRuntime } from '@/tools/video-editor/runtime/families/FamilyRuntimeAssembly.ts';
import { VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY } from '@/tools/video-editor/runtime/families/familyAdapterRegistry.ts';
import type { TimelineGestureOwner } from '@/tools/video-editor/lib/mobile-interaction-model';
import type {
  PackageState,
  PackageMetadata,
} from '@/tools/video-editor/runtime/extensionLoader';

// Re-export types / functions moved to FamilyRuntimeAssembly for backwards compatibility
export {
  computePackageContributionSummary,
} from '@/tools/video-editor/runtime/families/FamilyRuntimeAssembly.ts';
export type { PackageContributionSummary } from '@/tools/video-editor/runtime/families/FamilyRuntimeAssembly.ts';

import type { PackageContributionSummary } from '@/tools/video-editor/runtime/families/FamilyRuntimeAssembly.ts';

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

export type VideoEditorPlannerNextActionKind =
  | 'select-route'
  | 'materialize'
  | 'bake'
  | 'invoke-agent'
  | 'open-settings'
  | 'install-extension'
  | 'enable-extension'
  | 'start-process';

export interface VideoEditorPlannerNextActionDetail {
  specificKind?: 'resolve-blocker' | 'start-process';
}

/** Planner next-action metadata for resolving route/process/material blockers. */
export interface VideoEditorPlannerNextActionDescriptor {
  kind: VideoEditorPlannerNextActionKind;
  label: string;
  route?: RenderRoute;
  processId?: string;
  operationId?: string;
  message?: string;
  detail?: VideoEditorPlannerNextActionDetail;
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

/**
 * A normalized material slot surfaced from a transition's descriptor-declared
 * {@link TransitionMaterialSlotDeclaration}.
 *
 * Each slot can receive a {@link MaterialRef} / {@link RenderMaterialRef}
 * binding at runtime through the internal material.attach graph preview
 * operation.  No new material identity types are introduced — bound
 * materials reuse the existing {@link MaterialRef} / {@link RenderMaterialRef}
 * contract.
 */
export interface VideoEditorTransitionMaterialSlotDescriptor {
  readonly name: string;
  readonly label?: string;
}

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
  /**
   * M5-ready named material (mask) slot declarations normalized from the
   * contribution manifest.  An empty array means the transition declares
   * no material inputs.
   */
  materialSlots: readonly VideoEditorTransitionMaterialSlotDescriptor[];
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
  /** Canonical scoped identity key (`kind:extensionId:contributionId`). */
  scopedKey: string;
  /** Encounter ordinal within an exact scoped-key duplicate group (0 = first). */
  duplicateOrdinal: number;
  /** Whether this declaration remains eligible for descriptor projection fallback. */
  projectionEligible: boolean;
  /** The earliest milestone that activates this kind. */
  milestone: string;
}

// ---------------------------------------------------------------------------
// Host-owned contribution index types
// ---------------------------------------------------------------------------

/** Runtime-owned status for a contribution-index entry. */
export type ContributionIndexStatus =
  | 'active'
  | 'inactive-reserved'
  | 'disabled'
  | 'invalid';

/** Projection metadata for a contribution-index entry. */
export interface ContributionIndexProjectionMetadata {
  /** Encounter ordinal within an exact scoped-key duplicate group (0 = first). */
  readonly duplicateOrdinal: number;
  /** Whether this record remained eligible for descriptor projection. */
  readonly eligible: boolean;
  /** Whether the host actually projected this record into a descriptor array. */
  readonly projected: boolean;
  /** Provenance of the runtime-facing record. */
  readonly source: 'descriptor-array' | 'preserved-record';
}

/** Structured host-owned resolution policy for preserved duplicate records. */
export interface ContributionIndexResolutionPolicy {
  readonly kind: 'exact-duplicate';
  readonly strategy: 'first-wins-projection';
  readonly winnerScopedKey: string;
  readonly winnerDuplicateOrdinal: number;
}

/**
 * A single entry in the host-owned contribution index.
 *
 * Each entry maps a scoped key (`kind:extensionId:contributionId`) to its
 * identity triple. This index is populated at runtime assembly time from
 * bridged contributions and is frozen with nested data.
 *
 * These types are **not** exposed through SDK descriptor pointer types or
 * manifest schema — they are owned exclusively by the host runtime.
 */
export interface ContributionIndexEntry {
  readonly scopedKey: string;
  readonly kind: string;
  readonly extensionId: string;
  readonly contributionId: string;
  /** Runtime-owned status for this contribution record. */
  readonly status: ContributionIndexStatus;
  /** Package-state classification when the host supplied package inventory data. */
  readonly packageState?: PackageState;
  /** Optional render identifier assigned by the host render pipeline. */
  readonly renderId?: string;
  /** Optional route-fit metadata attributed to this contribution when a planner
   *  finding or blocker can be resolved to a scoped contribution key. */
  readonly routeFit?: RouteFitMetadata;
  /** Scoped diagnostics directly attributable to this contribution key. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Encounter ordinal within an exact scoped-key duplicate group (0 = first). */
  readonly duplicateOrdinal: number;
  /** Whether this entry was eligible for descriptor projection. */
  readonly projectionEligible: boolean;
  /** Structured projection metadata for planner/runtime consumers. */
  readonly projection: ContributionIndexProjectionMetadata;
  /** Resolution metadata for preserved exact duplicates that were not projected. */
  readonly resolutionPolicy?: ContributionIndexResolutionPolicy;
}

/**
 * Host-owned contribution index keyed by scoped key.
 *
 * Format: `kind:extensionId:contributionId`
 *
 * The index is frozen at assembly time and provides O(1) lookup of
 * contribution identity records by scoped key. Exact scoped-key duplicates
 * are preserved as frozen arrays in encounter order. Batch T8 populates
 * active bridged records plus preserved exact-duplicate records.
 */
export type ContributionIndex = Readonly<Record<string, readonly ContributionIndexEntry[]>>;

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
  /**
   * Host-owned contribution index keyed by scoped key (`kind:extensionId:contributionId`).
   *
   * Built from bridged contributions at assembly time and frozen with nested
   * entry objects. Provides O(1) lookup of contribution identity without
   * scanning descriptor arrays.
   *
   * **Not** exposed through SDK descriptor pointer types or manifest schema.
   */
  readonly contributionIndex: ContributionIndex;
  /**
   * Eager composition-graph projection built from the contribution index.
   *
   * This is the M1b graph authority surface for shader/ref consumers.
   * Legacy descriptor arrays and the contribution index remain attached for
   * compatibility callers that have not migrated yet.
   */
  readonly compositionGraph: CompositionGraph;
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
  /** Project-level extension requirements referenced by the active extensions. */
  readonly requirements: readonly ProjectExtensionRequirement[];
  /**
   * Full package-state inventory for every package that reached the loader,
   * including non-activated packages (disabled, invalid, incompatible,
   * duplicate, settings-error, runtime-error).
   *
   * Empty array when no package-state data was supplied (backward compatible
   * with direct-extension-only providers that bypass the loader).
   */
  readonly packageStateInventory: readonly PackageStateInventoryEntry[];
}

// ---------------------------------------------------------------------------
// Package state inventory (M5: propagated from ExtensionLoader load result)
// ---------------------------------------------------------------------------

/**
 * A single entry in the package-state inventory, propagated from the
 * ExtensionLoader's load result so UI consumers can read package-state
 * data directly without deriving it from active `loadedExtensions`.
 *
 * Mirrors the state/metadata fields of {@link ExtensionLoadEntry} but is
 * owned by the runtime normalization layer.
 */
export interface PackageStateInventoryEntry {
  readonly extensionId: string;
  readonly packageState: PackageState;
  readonly stateReason: string;
  readonly packageMetadata: PackageMetadata | null;
  /**
   * Manifest contributions preserved from the loader so contribution
   * summaries can be derived for disabled/error packages without
   * active runtime descriptors.
   */
  readonly manifestContributions?: readonly ExtensionContribution[] | null;
  /**
   * Precomputed contribution summary for UI rendering.
   * Populated by {@link normalizeExtensionRuntime} so the ExtensionManager
   * can render contribution counts, kind labels, and contribution IDs
   * for every package regardless of activation state.
   */
  readonly contributionSummary?: PackageContributionSummary | null;
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

const EMPTY_TRANSITION_MATERIAL_SLOTS: readonly VideoEditorTransitionMaterialSlotDescriptor[] = Object.freeze([]);
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

const EMPTY_RUNTIME_COMPOSITION_GRAPH: CompositionGraph = Object.freeze({
  nodes: Object.freeze([
    Object.freeze({
      id: 'timeline-postprocess',
      kind: 'timeline-postprocess',
      detail: Object.freeze({ scope: 'postprocess' }),
    }),
  ]),
  edges: Object.freeze([]),
  referenceStates: Object.freeze([]),
  diagnostics: Object.freeze([]),
});

/**
 * Host-owned runtime normalization: converts a list of ReighExtension objects
 * into a frozen, deterministic, provider-scoped {@link ExtensionRuntime}.
 *
 * - Preserves {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity when
 *   the extension list is empty or all contributions are inactive/reserved.
 * - Detects duplicate extension IDs and exact scoped-key duplicate
 *   contribution declarations, emitting structured diagnostics without
 *   dropping preserved records.
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
  packageStateEntries?: readonly PackageStateInventoryEntry[],
): ExtensionRuntime {
  // ---- Empty fast path: preserve the default empty identity ----------------
  if (extensions.length === 0 && (!packageStateEntries || packageStateEntries.length === 0)) {
    return EMPTY_EXTENSION_RUNTIME;
  }

  // ---- Phase 1–3: sequence contributions -----------------------------------
  const seq = buildFamilyContributionSequence(extensions);

  // ---- Phase 4–5: assemble and freeze (delegated to FamilyRuntimeAssembly) --
  return assembleExtensionRuntime(
    seq,
    packageStateEntries,
    DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
    VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
  );
}

/** Frozen empty runtime, preserving {@link DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME} identity. */
const EMPTY_EXTENSION_RUNTIME: ExtensionRuntime = Object.freeze({
  config: DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
  extensions: Object.freeze([]),
  diagnostics: Object.freeze([]),
  inactiveReserved: Object.freeze([]),
  knownRenderIds: Object.freeze(new Set<string>()),
  contributionIndex: Object.freeze({}),
  compositionGraph: EMPTY_RUNTIME_COMPOSITION_GRAPH,
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
  requirements: Object.freeze([]),
  packageStateInventory: Object.freeze([]),
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
