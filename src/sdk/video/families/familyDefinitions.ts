/**
 * Video contribution family registry — canonical definitions, projection
 * helpers, and conformance report utilities.
 *
 * This module is the single source of truth for family maturity posture.
 * All generators, gates, drift checks, and host consumers derive their
 * family data from the registry defined here.
 *
 * @module video/families/familyDefinitions
 * @publicContract
 */

import type {
  DeclarationMaturity,
  ExecutionMaturity,
  FamilyDefinition,
  FamilyRequirementChecklist,
} from '@/sdk/core/families/maturity';

import {
  buildConformanceReport,
  computeGaps,
  isFullyConformant,
  type FamilyConformanceReport,
  buildLegacyMilestoneMap,
} from '@/sdk/core/families/conformance';

import type { VideoContributionKind } from '@/sdk/video/families/contributionKinds';

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

/**
 * The canonical video family maturity registry.
 *
 * Each entry defines the maturity posture for a single `VideoContributionKind`.
 * The array is the source of truth for generators, drift checks, and
 * conformance gates.
 *
 * Sorted by kind string ascending for deterministic iteration.
 */
export const VIDEO_FAMILY_REGISTRY: readonly FamilyDefinition<VideoContributionKind>[] = [
  // ---- Agent (M10) ----
  {
    kind: 'agent',
    declarationMaturity: 'typed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Agent contributions are proposal-backed; the host mediates tool dispatch ' +
      'and generation sessions. No standalone host adapter exists yet — execution ' +
      'is delegated through the agent-tool registration service.',
    requiresTrustedCode: true,
    manifestSchemaDefinition: 'AgentContribution',
    sdkModules: [
      'src/sdk/video/agent/index.ts',
    ],
    hostAdapter: null,
    requirements: {
      manifestSchema: undefined,
      normalizedDescriptor: false,
      registrationApi: false,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
    },
    legacyMilestone: 'M10',
    label: 'Agent',
    description:
      'Agent contributions expose a tool dispatch surface and generation session ' +
      'contract. Execution is host-mediated via proposal-backed tool invocation.',
  },

  // ---- Agent Tool (M10) ----
  {
    kind: 'agentTool',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Agent tool contributions are host-mediated: the host owns invocation, ' +
      'progress, cancellation, proposal creation, and UI. Extensions register ' +
      'tool handlers imperatively via ctx.agentTools. Execution posture is ' +
      'delegated to a placeholder adapter while descriptor projection remains ' +
      'stable. Evidence: AgentToolContribution interface, ' +
      'AgentToolRegistrationService, and manifest schema oneOf coverage.',
    requiresTrustedCode: true,
    manifestSchemaDefinition: 'AgentToolContribution',
    sdkModules: [
      'src/sdk/video/families/agentTools.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/agentToolAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M10',
    label: 'Agent Tool',
    description:
      'Agent tool contributions expose host-mediated tool handlers with ' +
      'input schemas, proposal-backed mutations, and host-owned invocation ' +
      'lifecycle. Registered imperatively via ctx.agentTools.',
  },

  // ---- Asset Detail Section (M6) ----
  {
    kind: 'assetDetailSection',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Asset detail section contributions add custom sections to the asset ' +
      'detail panel with title and placement validation. Descriptor projection ' +
      'is delegated to a distinct placeholder adapter separate from ' +
      'metadataFacet. Evidence: manifest validation enforces non-empty title ' +
      'and valid placement (before-default, after-default).',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'AssetDetailSectionContribution',
    sdkModules: [
      'src/sdk/video/families/assetDetailSections.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/assetDetailSectionAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: false,
      lifecycleCleanup: false,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M6',
    label: 'Asset Detail Section',
    description:
      'Asset detail section contributions add custom sections to the asset ' +
      'detail panel with placement control and title validation. ' +
      'Bridged at M6.',
  },

  // ---- Automation (M9) ----
  {
    kind: 'automation',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'runtime-bridged',
    hostIntegrationNotes:
      'Automation clips are host-owned timeline clips (built-in clip type) ' +
      'with baked keyframe curves that override target extension parameter ' +
      'values during preview and export. Bridged at M9 alongside clipType. ' +
      'Evidence: BUILTIN_CLIP_TYPES includes automation; AutomationClipTarget ' +
      'and AutomationClipParams types exist; contributionKindNotYetBridged ' +
      'returns null for automation at M9.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'AutomationContribution',
    sdkModules: [
      'src/sdk/video/timeline/clipTypes.ts',
      'src/sdk/video/families/automation.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/automationAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: false,
      lifecycleCleanup: false,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M9',
    label: 'Automation',
    description:
      'Automation clips are host-owned timeline clips that apply baked ' +
      'keyframe curves to override target extension parameters. ' +
      'Bridged at M9 as a built-in clip type.',
  },

  // ---- Clip Type (M9) ----
  {
    kind: 'clipType',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'runtime-bridged',
    hostIntegrationNotes:
      'Clip-type contributions are dispatched through the timeline composition ' +
      'registry. The host adapter normalizes clip-type descriptors and owns ' +
      'lifecycle. Keyframe interpolation is host-owned.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'ClipTypeContribution',
    sdkModules: [
      'src/sdk/video/timeline/clipTypes.ts',
      'src/sdk/video/families/clipTypeContributions.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/clipTypeAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: true,
    },
    legacyMilestone: 'M9',
    label: 'Clip Type',
    description:
      'Clip types define the compositional and dispatch contract for ' +
      'timeline clips. The host owns keyframes, render planning, and ' +
      'export projection.',
  },

  // ---- Command (M4) ----
  {
    kind: 'command',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Commands are fully bridged with palette, context-menu dispatch, ' +
      'keybinding wiring, and export-scoped guard participation.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'CommandContribution',
    sdkModules: [
      'src/sdk/video/families/commands.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/commandAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M4',
    label: 'Command',
    description:
      'Commands are palette-invocable actions with optional target context ' +
      'dispatch (clip, clip-selection, track, timeline-area). Fully bridged ' +
      'with host adapter, keybinding, and context-menu wiring.',
  },

  // ---- Context Menu Item (M4) ----
  {
    kind: 'contextMenuItem',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Context menu item contributions add items to clip, track, and ' +
      'timeline-area context menus. Fully bridged at M4 through the ' +
      'command dispatch system. Evidence: command-extension.ts example ' +
      'includes a clip-target context menu item.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'ContextMenuItemContribution',
    sdkModules: [
      'src/sdk/video/families/contextMenuItems.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/contextMenuItemAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M4',
    label: 'Context Menu Item',
    description:
      'Context menu item contributions add items to context menus for ' +
      'clip, track, and timeline-area surfaces with target filtering.',
  },

  // ---- Dialog (M1) ----
  {
    kind: 'dialog',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Dialog contributions render into named dialog layers (modal, overlay). ' +
      'Bridged at M1 through the slot extension surface. Schema: ' +
      'DialogContribution with layer enum validation.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'DialogContribution',
    sdkModules: [
      'src/sdk/manifest.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/dialogAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M1',
    label: 'Dialog',
    description:
      'Dialog contributions render into named dialog layers (modal or overlay) ' +
      'with order control and when-clause filtering. Bridged at M1.',
  },

  // ---- Effect (M7) ----
  {
    kind: 'effect',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Effect contributions are trusted local browser-preview components. ' +
      'Extensions register effect components imperatively via ctx.effects. ' +
      'Descriptor projection is delegated to a placeholder adapter while ' +
      'runtime registration remains host-mediated. Evidence: ' +
      'EffectContribution interface, EffectRegistrationService, manifest ' +
      'schema oneOf coverage, and kind enum inclusion.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'EffectContribution',
    sdkModules: [
      'src/sdk/video/families/effects.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/effectAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M7',
    label: 'Effect',
    description:
      'Effect contributions register trusted local render components that ' +
      'execute in the browser preview. Blocked from export unless ' +
      'allowBrowserExport or allowWorkerExport is declared. Bridged at M7.',
  },

  // ---- Inspector Section (M1) ----
  {
    kind: 'inspectorSection',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Inspector section contributions add custom sections to the inspector ' +
      'panel. Placement can be before-default or after-default. Evidence: ' +
      'dedicated inspector-example.ts with both placement values.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'InspectorSectionContribution',
    sdkModules: [
      'src/sdk/manifest.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/inspectorSectionAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M1',
    label: 'Inspector Section',
    description:
      'Inspector section contributions add custom sections to the inspector ' +
      'panel with placement control (before-default, after-default).',
  },

  // ---- Keybinding (M4) ----
  {
    kind: 'keybinding',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Keybinding contributions bind keyboard shortcuts to commands with ' +
      'platform-aware key notation. Bridged at M4 through the command ' +
      'dispatch system. Evidence: command-extension.ts example includes ' +
      'a CtrlOrCmd+Alt+R keybinding.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'KeybindingContribution',
    sdkModules: [
      'src/sdk/video/families/keybindings.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/keybindingAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M4',
    label: 'Keybinding',
    description:
      'Keybinding contributions bind keyboard shortcuts to commands ' +
      'with platform-aware key notation and when-clause filtering.',
  },

  // ---- Metadata Facet (M6) ----
  {
    kind: 'metadataFacet',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'runtime-bridged',
    hostIntegrationNotes:
      'Metadata facet contributions tell the host how to surface a metadata ' +
      'field as a searchable/filterable facet in the asset panel. Bridged at M6. ' +
      'Evidence: MetadataFacetContribution interface, kind enum inclusion, ' +
      'and M6-active bridging status in contributionKindNotYetBridged.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'MetadataFacetContribution',
    sdkModules: [
      'src/sdk/video/families/metadataFacet.ts',
      'src/sdk/video/assets/metadata.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/metadataFacetAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: false,
      lifecycleCleanup: false,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M6',
    label: 'Metadata Facet',
    description:
      'Metadata facet contributions surface metadata fields as searchable ' +
      'and filterable facets in the asset panel with dot-separated field paths. ' +
      'Bridged at M6.',
  },

  // ---- Output Format (M6) ----
  {
    kind: 'outputFormat',
    declarationMaturity: 'typed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Output format types are declared but runtime execution is reserved. ' +
      'Descriptor projection is delegated to a placeholder adapter that ' +
      'surfaces compile-only and render-dependent planner stubs.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'OutputFormatContribution',
    sdkModules: [
      'src/sdk/video/families/outputFormats.ts',
      'src/sdk/video/exports/outputFormats.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/outputFormatAdapter.ts',
    requirements: {
      manifestSchema: false,
      normalizedDescriptor: false,
      registrationApi: false,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
      sidecarExport: false,
      artifactRouteCompletion: false,
    },
    legacyMilestone: 'M6',
    label: 'Output Format',
    description:
      'Output format contributions declare compile-only or render-dependent ' +
      'output pipelines. Types exist but runtime execution is reserved.',
  },

  // ---- Panel (M1) ----
  {
    kind: 'panel',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Panel contributions render into the asset panel region. Placement ' +
      'is limited to asset-panel. Bridged at M1 through the slot extension ' +
      'surface. Evidence: panel placement validation in SDK tests.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'PanelContribution',
    sdkModules: [
      'src/sdk/manifest.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/panelAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: false,
      tests: true,
    },
    legacyMilestone: 'M1',
    label: 'Panel',
    description:
      'Panel contributions render into the asset panel region. Placement ' +
      'is limited to asset-panel. Bridged at M1.',
  },

  // ---- Parser (M6) ----
  {
    kind: 'parser',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Parser contributions are bridged through the asset ingestion pipeline. ' +
      'Descriptor projection is delegated to a placeholder adapter; real ' +
      'ingestion lifecycle remains host-owned.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'ParserContribution',
    sdkModules: [
      'src/sdk/video/families/parsers.ts',
      'src/sdk/video/assets/parsers.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/parserAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: true,
    },
    legacyMilestone: 'M6',
    label: 'Parser',
    description:
      'Parsers convert assets from import formats into editor-native representations. ' +
      'Fully bridged at M6 with host adapter, diagnostics, and lifecycle.',
  },

  // ---- Process (M12) ----
  {
    kind: 'process',
    declarationMaturity: 'typed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Process contributions declare trusted local process descriptors with ' +
      'installation posture, lifecycle, and capability requirements. ' +
      'Execution is reserved for M12 — processes are declarable in manifests ' +
      'but not yet bridged for runtime. Evidence: ProcessContribution interface, ' +
      'ProcessSpec, ProcessLifecycleState types; contributionKindNotYetBridged ' +
      'returns M12.',
    requiresTrustedCode: true,
    manifestSchemaDefinition: 'ProcessContribution',
    sdkModules: [
      'src/sdk/video/families/processes.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/processAdapter.ts',
    requirements: {
      manifestSchema: false,
      normalizedDescriptor: false,
      registrationApi: false,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
      sidecarExport: false,
      artifactRouteCompletion: false,
    },
    legacyMilestone: 'M12',
    label: 'Process',
    description:
      'Process contributions declare trusted local process descriptors that ' +
      'the host manages (install, start, stop, restart). Types and manifest ' +
      'declaration exist; runtime execution is reserved for M12.',
  },

  // ---- Search Provider (M6) ----
  {
    kind: 'searchProvider',
    declarationMaturity: 'typed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Search provider contributions supply asset/material search results to ' +
      'the host search surface. The provider owns indexing, model choice, and ' +
      'refresh; the host owns query dispatch, result merge, and source labeling. ' +
      'Typed but execution is reserved (declarable, not yet bridged for runtime). ' +
      'Evidence: SearchProviderContribution interface; contributionKindNotYetBridged ' +
      'returns M6.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'SearchProviderContribution',
    sdkModules: [
      'src/sdk/video/families/searchProviders.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/searchProviderAdapter.ts',
    requirements: {
      manifestSchema: false,
      normalizedDescriptor: false,
      registrationApi: false,
      lifecycleCleanup: undefined,
      diagnostics: undefined,
      hostCapabilityProjection: undefined,
      uiIntegration: undefined,
      persistencePosture: undefined,
      examples: undefined,
      tests: undefined,
    },
    legacyMilestone: 'M6',
    label: 'Search Provider',
    description:
      'Search provider contributions supply search results to the host search ' +
      'surface with configurable result kinds and ordering. Types exist; ' +
      'runtime execution is reserved.',
  },

  // ---- Shader (M13) ----
  {
    kind: 'shader',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Shader contributions declare WebGL materializer descriptors. ' +
      'Descriptor projection is delegated to a placeholder adapter while ' +
      'materializer requirements remain validated at export time.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'ShaderContribution',
    sdkModules: [
      'src/sdk/video/rendering/capabilities.ts',
      'src/sdk/video/families/shaders.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/shaderAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: false,
      lifecycleCleanup: false,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M13',
    label: 'Shader',
    description:
      'Shader contributions declare WebGL/WebGPU materializer contracts for ' +
      'custom rendering passes. Types exist; runtime execution is delegated.',
  },

  // ---- Slot (M1) — bridged surface ----
  {
    kind: 'slot',
    declarationMaturity: 'documented',
    executionMaturity: 'public-supported',
    hostIntegrationNotes:
      'Slot contributions are the original extension surface. Fully bridged ' +
      'with lifecycle, diagnostics, UI, persistence, examples, and tests.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'SlotContribution',
    sdkModules: [
      'src/sdk/manifest.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/slotAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: true,
      uiIntegration: true,
      persistencePosture: true,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M1',
    label: 'Slot',
    description:
      'Slots are the primary extension surface — header, toolbar, panels, ' +
      'and other host chrome regions. Fully supported with lifecycle, ' +
      'diagnostics, and persistence.',
  },

  // ---- Timeline Overlay (M2) ----
  {
    kind: 'timelineOverlay',
    declarationMaturity: 'documented',
    executionMaturity: 'host-integrated',
    hostIntegrationNotes:
      'Timeline overlay contributions render over the timeline surface ' +
      'with order control and when-clause filtering. Bridged at M2. ' +
      'Evidence: dedicated overlay-example.ts.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'TimelineOverlayContribution',
    sdkModules: [
      'src/sdk/manifest.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/timelineOverlayAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: true,
      hostCapabilityProjection: false,
      uiIntegration: true,
      persistencePosture: false,
      examples: true,
      tests: true,
    },
    legacyMilestone: 'M2',
    label: 'Timeline Overlay',
    description:
      'Timeline overlay contributions render over the timeline surface ' +
      'with order control and when-clause filtering. Bridged at M2.',
  },

  // ---- Transition (M8) ----
  {
    kind: 'transition',
    declarationMaturity: 'schema-backed',
    executionMaturity: 'delegated',
    hostIntegrationNotes:
      'Transition contributions are trusted local browser-preview renderers ' +
      'for cross-clip transitions. Extensions register transition renderers ' +
      'imperatively via ctx.transitions. Descriptor projection is delegated ' +
      'to a placeholder adapter while runtime registration remains host-mediated. ' +
      'Evidence: TransitionContribution interface, TransitionRegistrationService, ' +
      'manifest schema oneOf coverage, and kind enum inclusion.',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'TransitionContribution',
    sdkModules: [
      'src/sdk/video/families/transitions.ts',
    ],
    hostAdapter: 'src/tools/video-editor/runtime/families/transitionAdapter.ts',
    requirements: {
      manifestSchema: true,
      normalizedDescriptor: true,
      registrationApi: true,
      lifecycleCleanup: true,
      diagnostics: false,
      hostCapabilityProjection: false,
      uiIntegration: false,
      persistencePosture: false,
      examples: false,
      tests: false,
    },
    legacyMilestone: 'M8',
    label: 'Transition',
    description:
      'Transition contributions register trusted local renderers for ' +
      'cross-clip transitions. Blocked from export unless allowBrowserExport ' +
      'or allowWorkerExport is declared. Bridged at M8.',
  },
];

// ---------------------------------------------------------------------------
// Projection helpers
// ---------------------------------------------------------------------------

/**
 * Look up a family definition by kind.
 * Returns `undefined` when the kind is not in the registry.
 */
export function getVideoFamily(
  kind: VideoContributionKind,
): FamilyDefinition<VideoContributionKind> | undefined {
  return VIDEO_FAMILY_REGISTRY.find((def) => def.kind === kind);
}

/**
 * Build a conformance report for every family in the registry.
 * Reports are returned in registry order (kind ascending).
 */
export function buildVideoFamilyReports(): readonly FamilyConformanceReport<VideoContributionKind>[] {
  return VIDEO_FAMILY_REGISTRY.map(buildConformanceReport);
}

/**
 * Build a conformance report for a single kind.
 * Returns `undefined` when the kind is not in the registry.
 */
export function buildVideoFamilyReport(
  kind: VideoContributionKind,
): FamilyConformanceReport<VideoContributionKind> | undefined {
  const def = getVideoFamily(kind);
  return def ? buildConformanceReport(def) : undefined;
}

/**
 * Legacy milestone map derived from the registry.
 * Compatible with the current `CONTRIBUTION_KIND_MILESTONE` shape.
 */
export const VIDEO_FAMILY_LEGACY_MILESTONE_MAP: Record<string, string | undefined> =
  buildLegacyMilestoneMap(VIDEO_FAMILY_REGISTRY);

/**
 * All kinds present in the registry.
 * Useful for checking registry coverage against `VIDEO_CONTRIBUTION_KINDS`.
 */
export function getVideoFamilyKinds(): VideoContributionKind[] {
  return VIDEO_FAMILY_REGISTRY.map((def) => def.kind);
}

/**
 * Compute aggregate registry statistics.
 */
export interface VideoFamilyStats {
  /** Total number of families in the registry. */
  readonly totalFamilies: number;
  /** Count of families that are fully conformant. */
  readonly fullyConformantCount: number;
  /** Count of families with at least one gap. */
  readonly familiesWithGaps: number;
  /** Total number of gaps across all families. */
  readonly totalGaps: number;
  /** Families grouped by declaration maturity. */
  readonly byDeclarationMaturity: Record<DeclarationMaturity, number>;
  /** Families grouped by execution maturity. */
  readonly byExecutionMaturity: Record<ExecutionMaturity, number>;
}

/**
 * Compute aggregate statistics for the video family registry.
 */
export function computeVideoFamilyStats(): VideoFamilyStats {
  const byDeclarationMaturity: Record<DeclarationMaturity, number> = {
    typed: 0,
    'schema-backed': 0,
    documented: 0,
  };
  const byExecutionMaturity: Record<ExecutionMaturity, number> = {
    absent: 0,
    delegated: 0,
    'runtime-bridged': 0,
    'host-integrated': 0,
    'public-supported': 0,
  };

  let fullyConformantCount = 0;
  let familiesWithGaps = 0;
  let totalGaps = 0;

  for (const def of VIDEO_FAMILY_REGISTRY) {
    byDeclarationMaturity[def.declarationMaturity] += 1;
    byExecutionMaturity[def.executionMaturity] += 1;

    if (isFullyConformant(def)) {
      fullyConformantCount += 1;
    }

    const gaps = computeGaps(def);
    if (gaps.length > 0) {
      familiesWithGaps += 1;
    }
    totalGaps += gaps.length;
  }

  return {
    totalFamilies: VIDEO_FAMILY_REGISTRY.length,
    fullyConformantCount,
    familiesWithGaps,
    totalGaps,
    byDeclarationMaturity,
    byExecutionMaturity,
  };
}

/**
 * Find all families that have a specific requirement unmet or unassessed.
 */
export function findVideoFamiliesWithRequirementGap(
  requirementKey: keyof FamilyRequirementChecklist,
): readonly FamilyDefinition<VideoContributionKind>[] {
  return VIDEO_FAMILY_REGISTRY.filter((def) => {
    const value = def.requirements[requirementKey];
    return value === false || value === undefined;
  });
}
