/**
 * @reigh/editor-sdk — Public SDK entrypoint
 *
 * Stable public types and helpers for trusted local extensions.
 * This module must NOT import from editor internals (DataProvider,
 * raw timeline ops, editor runtime contexts, or internal mutation APIs).
 *
 * This file is a pure barrel: named re-exports only. All implementations
 * live in canonical modules under src/sdk/.
 *
 * @publicContract
 */

// ===========================================================================
// Core SDK
// ===========================================================================

// ids & dispose
export { type ExtensionId, type ContributionId, validateExtensionId, validateContributionId } from './ids';
export type { DisposeHandle } from './dispose';

// commands
export { type TargetContext, type TargetContextPayload, type CommandRunContext, type CommandHandler, type CommandRegistrationOptions } from './commands';

// chrome
export { type ExtensionChromeService, type ChromeEvent, type ChromeToastPayload, type ChromeProgressPayload, type ChromeSavePayload, type ChromeRenderStatusPayload, type ChromeEventPayload } from './chrome';

// diagnostics
export { type DiagnosticSeverity, type DiagnosticSource, DIAGNOSTIC_SOURCE_EXTENSION, type ExtensionDiagnostic, type DiagnosticSourceRange, type Diagnostic, type DiagnosticCollection, DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY, type CreateDiagnosticCollectionOptions, createDiagnosticCollection, type ExportDiagnostic } from './diagnostics';

// manifest & contribution kinds
export { type ContributionKind, type VideoEditorSlotName, type ExtensionContribution, KNOWN_CONTRIBUTION_KINDS, KNOWN_CONTRIBUTION_KINDS_SET, KNOWN_SLOT_NAMES, KNOWN_SLOT_NAMES_SET, INSPECTOR_SECTION_PLACEMENTS, PANEL_PLACEMENTS, ASSET_DETAIL_SECTION_PLACEMENTS, ALL_VALID_PLACEMENTS, type ManifestValidationMode, type ManifestValidationResult, type ExtensionManifest, type ExtensionPermissionDeclaration, type InstalledExtensionPackage, validateManifest, validateInstalledPackage } from './manifest';

// packaging
export type { DependencyPosture, ExtensionDependency, IntegrityAlgorithm, IntegrityHash, MigrationHookKind, MigrationDeclaration, InstalledExtensionMetadata } from './packaging';

// lifecycle
export { type ExtensionActivateFn, type ReighExtension, type DefineExtensionOptions, defineExtension } from './lifecycle';

// capabilities
export type { CapabilityVersion, CapabilitySourceRef, RouteFitMetadata, CapabilityRequirement, IntegrationCapabilities, SamplingStrategy, SamplingSourceRef, SamplingRange, SamplingAttachmentKind, SamplingAttachmentRule, SamplingConfig, SamplingResultItem, SamplingResult, ProcessRoundtripRequest, ProcessRoundtripAction, ProcessRoundtripResult, ProcessProgressEvent, ProcessLogSummary } from './capabilities';
export { getCapabilityRequirements } from './capabilities';

// settings & persistence
export type { ExtensionSettingsService } from './settings';
export { createExtensionSettingsService, getSettingsPrefix } from './extensionSettingsService';
export type { ExtensionSettingsServiceFactoryResult, CreateExtensionSettingsServiceOptions, SettingsMigrationConfig, SettingsPersistenceError, SettingsPersistenceOperation, SettingsPersistenceSuccess } from './extensionSettingsService';
export { runSettingsMigration, getManifestSettingsSchemaVersion, findSettingsMigrationDeclarations } from './extensionSettingsMigration';
export type { SettingsMigrationHandler, SettingsMigrationResult, RunSettingsMigrationOptions } from './extensionSettingsMigration';

// state repository contracts
export type { SettingsSnapshot, LifecycleEvent, StateRepository } from './contracts';
export { createLifecycleEvent } from './contracts';

// context
export { type ExtensionI18nService, type ExtensionDiagnosticsService, type CreativeContext, type ExtensionCommandService, type ExtensionContext, createCreativeContext, createCreativeContextStubs, disposeExtensionContextServices, CONTEXT_DISPOSE_SYMBOL, ExtensionNotImplementedError, CREATIVE_MEMBER_MILESTONE } from './context';

// context factory
export { setEditorShellRoot, getEditorShellRoot, createExtensionContext } from './contextFactory';

// family bridge
export { CONTRIBUTION_KIND_MILESTONE, contributionKindNotYetBridged, getVideoFamilyDefinition, getVideoFamilyConformanceReport, getVideoFamilyLegacyBridgeStatus } from './familyBridge';

// project requirements
export type { ProjectExtensionRequirement, ProjectExtensionRequirements } from './projectRequirements';

// ===========================================================================
// Video: Families (contribution contracts)
// ===========================================================================

export type { MetadataFacetContribution } from './video/families/metadataFacet';
export type { AssetDetailSectionContribution } from './video/families/assetDetailSections';
export type { CommandContribution } from './video/families/commands';
export type { KeybindingContribution } from './video/families/keybindings';
export type { ContextMenuItemContribution } from './video/families/contextMenuItems';
export type { ParserContribution } from './video/families/parsers';
export type { SearchProviderContribution } from './video/families/searchProviders';
export type { OutputFormatContribution, CompileOnlyOutputFormatContribution, RenderDependentOutputFormatContribution, RenderDependentOutputDescriptor } from './video/families/outputFormats';
export type { EffectContribution, EffectComponent, EffectParameterDefinition, EffectParameterSchema, EffectRegistrationOptions, EffectRegistrationService } from './video/families/effects';
export type { TransitionContribution, TransitionRenderer, TransitionParameterDefinition, TransitionParameterSchema, TransitionRegistrationOptions, TransitionRegistrationService } from './video/families/transitions';
export type { ClipTypeContribution, ClipRenderer, ClipInspector, ClipParameterDefinition, ClipParameterSchema, ClipTypeRegistrationOptions, ClipTypeRegistrationService } from './video/families/clipTypeContributions';
export type { KeyframeInterpolation, Keyframe, InterpolatedParam, AutomationClipTarget, AutomationClipParams } from './video/families/automation';
export type { AgentToolContribution, AgentToolInputSchema, AgentToolInputProperty, ToolResultFamily, ToolResult, ToolMutationProposalResult, ToolGenerationSessionResult, ToolMaterialArtifactResult, ToolEnrichmentSearchResult, ToolExportResult, ToolProcessResult, ToolUISummaryResult, ToolSourceRef, ToolArtifactRef, ToolSearchResultMatch, ToolResultDiagnostic, AgentToolInvocationRequest, AgentToolRequestContext, AgentToolExportContext, GenerationSession, AgentToolRegistrationService, AgentToolHandler } from './video/families/agentTools';
export type { ProcessSpawnConfig, ProcessManifestEntry, ProcessEnvFieldSpec, ProcessOperationSpec, ProcessSpec, ProcessContribution, ProcessLifecycleState, ProcessStatusBase, ProcessStatus } from './video/families/processes';
export type { ShaderPassKind, ShaderColorSpace, ShaderFallbackBehavior, ShaderTextureSourceKind, ShaderTextureFilter, ShaderTextureWrap, ShaderInlineSource, ShaderModuleSource, ShaderSourceDescriptor, ShaderPassDescriptor, ShaderUniformType, ShaderUniformEnumOption, ShaderTextureRef, ShaderUniformDefaultValue, ShaderUniformDefinition, ShaderUniformSchema, ShaderTextureDefinition, ShaderTextureSchema, ShaderMaterializerDescriptor, ShaderContribution, ShaderRegistrationOptions, ShaderRegistrationService } from './video/families/shaders';

// ===========================================================================
// Video: Rendering
// ===========================================================================

export { DETERMINISM_STATUSES, RENDER_BLOCKER_REASONS, RENDER_ROUTES } from './video/rendering/renderability';
export type { CapabilityFinding, CapabilityFindingSeverity, ContributionRenderability, DeterminismStatus, RenderBlocker, RenderBlockerReason, RenderCapability, RenderCapabilityStatus, RenderRoute } from './video/rendering/renderability';
export { shaderMissingMaterializerBlockerMessage, describeShaderMaterializerRequirementScope } from './video/rendering/capabilities';
export type { ShaderMaterializerRequirementScope } from './video/rendering/capabilities';
export type { ArtifactBoundary, BakeContract, RenderArtifact, RenderArtifactManifest, RenderArtifactSidecarDescriptor, RenderArtifactSidecarKind, RenderLocatorKind, RenderMaterial, RenderMaterialMediaKind, RenderMaterialRef, RenderStorageLocator } from './video/rendering/artifacts';

// ===========================================================================
// Video: Timeline
// ===========================================================================

export { EXTENSION_PROJECT_DATA_LIMITS, TIMELINE_DIFF_GRANULARITIES, TIMELINE_DIFF_KINDS, TIMELINE_PATCH_ALL_OP_FAMILIES, TIMELINE_PATCH_OP_FAMILIES, TIMELINE_PATCH_RESERVED_OP_FAMILIES } from './video/timeline/patch';
export type { ProjectDataLimitCode, ProjectDataLimitDetail, TimelineDiff, TimelineDiffEntry, TimelineDiffGranularity, TimelineDiffKind, TimelinePatch, TimelinePatchAnyOpFamily, TimelinePatchDiagnostic, TimelinePatchOpFamily, TimelinePatchOperation, TimelinePatchReservedOpFamily, TimelinePatchValidationResult, TimelinePreviewResult } from './video/timeline/patch';
export { TimelineVersionConflictError, isTimelineVersionConflictError } from './video/timeline/errors';
export { BUILTIN_CLIP_TYPES } from './video/timeline/clipTypes';
export type { BuiltinClipType } from './video/timeline/clipTypes';
export { getConfigSignature, getStableConfigSignature } from './video/timeline/configSignature';
export type { StableTimelineAssetRegistryInput, StableTimelineConfigSignatureInput, TimelineConfigSignatureInput } from './video/timeline/configSignature';
export type { TimelineEffectSummary, TimelineTransitionSummary, TimelineLiveBindingSummary, TimelineMaterialRefSummary, TimelineRenderPassSummary, TimelineSourceRefSummary, TimelineRenderGroupSummary, TimelineOutputMetadata, TimelineSnapshot, TimelineClipSummary, TimelineTrackSummary, TimelineShaderSummary, TimelineReader, TimelineProposalInput } from './video/timeline/reader';
export type { TimelineOps } from './video/timeline/timelineOps';
export type { ProposalState, ProposalExpiryDetail, TimelineProposal, ProposalListener, ProposalRuntime, ProposalPanelState, ProposalPanelAction, ProposalEnvelope, ProposalImportStatus, ProposalImportDiagnostic, ProposalImportResult } from './video/timeline/proposals';
export type { SourceMapRuntime, SourceMapEntry, GeneratedObjectMeta } from './video/timeline/sourceMap';

// ===========================================================================
// Video: Assets
// ===========================================================================

export type { AssetIntegrityMetadata, AssetGPSMetadata, AssetConsentMetadata, AssetProvenanceMetadata, EnrichmentStatus, DeferredEnrichmentRecord, AssetMetadata, MetadataFacetValueKind, MetadataFacetDescriptor, AssetDetailSectionDescriptor, AssetReadSurface, MaterialReadSurface } from './video/assets/metadata';
export type { ParserInput, ParserResult, ParserDiagnostic, ParserHandler } from './video/assets/parsers';
export type { SearchMatch, SearchProviderResult, SearchProviderHandler, SearchProviderContext } from './video/assets/search';

// ===========================================================================
// Video: Exports
// ===========================================================================

export type { CompileOnlyOutputResult, OutputFormatHandler, OutputFormatContext, ExportService, OutputFormatRegistrationOptions } from './video/exports/outputFormats';

// ===========================================================================
// Video: Live Data
// ===========================================================================

export type { LiveSourceKind, LiveSourceStatus, LiveSourceDiagnostic, LiveSource, LiveChannelKind, LiveChannelDescriptor, LiveChannelMetadata, LiveSampleFormat, LiveSampleFrame, LiveSample, LivePermissionState, LiveSourcePermission, LiveRecordingMode, LiveRecordingState, LiveLearnMode, LiveBakeTargetKind, LiveBakeTarget, LiveBakeSelection, LiveBakeResult, SteeringDecisionKind, SteeringParameterHotness, SteeringPriorSamplePolicy, SteeringProvenance, SteeringParameterChange, SteeringLineage, SteeringDecision, GenerationSessionLiveDelivery, BindingResolutionStatus, LiveBinding, LiveBindingResolution, LiveBindingMetadata, LiveSessionsService } from './video/liveData';
