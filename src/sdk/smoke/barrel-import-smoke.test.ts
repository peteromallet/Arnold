/**
 * M2a Barrel-import smoke coverage.
 *
 * Verifies that moved core names are importable BOTH from the public barrel
 * (`@/sdk/index`) and from canonical direct module paths.  Each module
 * family is represented by a small set of its most characteristic exports.
 *
 * The test is intentionally representative rather than exhaustive — it does
 * not attempt to duplicate the full API manifest (the API manifest gate
 * handles that).  It exists to catch import-resolution breakage across the
 * full breadth of moved M2a module families.
 *
 * @publicContract
 */

import { describe, expect, it } from 'vitest';

// ===========================================================================
// Public barrel imports (simulate downstream extension code)
// ===========================================================================
import {
  // ids
  validateExtensionId,
  validateContributionId,
  // lifecycle
  defineExtension,
  // context
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
  // diagnostics
  createDiagnosticCollection,
  DIAGNOSTIC_SOURCE_EXTENSION,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY,
  // manifest / validation
  KNOWN_CONTRIBUTION_KINDS_SET,
  ALL_VALID_PLACEMENTS,
  validateManifest,
  validateInstalledPackage,
  // settings
  createExtensionSettingsService,
  // M1b CompositionGraph
  COMPOSITION_NODE_KINDS,
  COMPOSITION_EDGE_KINDS,
  REFERENCE_STATES,
  // M7a artifact profile kinds
  ARTIFACT_MANIFEST_PROFILE_KINDS,
  contributionRefKey,
} from '@/sdk/index';
import type {
  // ids
  ExtensionId,
  ContributionId,
  // dispose
  DisposeHandle,
  // diagnostics
  DiagnosticSeverity,
  DiagnosticSource,
  ExtensionDiagnostic,
  DiagnosticSourceRange,
  Diagnostic,
  DiagnosticCollection,
  CreateDiagnosticCollectionOptions,
  ExportDiagnostic,
  // manifest
  ContributionKind,
  VideoEditorSlotName,
  ExtensionContribution,
  ManifestValidationMode,
  ManifestValidationResult,
  ExtensionManifest,
  ExtensionPermissionDeclaration,
  InstalledExtensionPackage,
  // packaging
  DependencyPosture,
  ExtensionDependency,
  IntegrityAlgorithm,
  IntegrityHash,
  MigrationHookKind,
  MigrationDeclaration,
  InstalledExtensionMetadata,
  // project requirements
  ProjectExtensionRequirement,
  ProjectExtensionRequirements,
  // settings
  ExtensionSettingsSchema,
  ExtensionSettingsService,
  // commands
  TargetContext,
  TargetContextPayload,
  CommandRunContext,
  CommandHandler,
  CommandRegistrationOptions,
  // chrome
  ExtensionChromeService,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeSavePayload,
  ChromeRenderStatusPayload,
  ChromeEventPayload,
  // context
  ExtensionI18nService,
  ExtensionDiagnosticsService,
  CreativeContext,
  ExtensionCommandService,
  ExtensionContext,
  // lifecycle
  ExtensionActivateFn,
  ReighExtension,
  DefineExtensionOptions,
  // capabilities
  CapabilityVersion,
  CapabilitySourceRef,
  RouteFitMetadata,
  CapabilityRequirement,
  IntegrationCapabilities,
  SamplingStrategy,
  SamplingSourceRef,
  SamplingRange,
  SamplingAttachmentKind,
  SamplingAttachmentRule,
  SamplingConfig,
  SamplingResultItem,
  SamplingResult,
  ProcessLiveSourceValueShape,
  ProcessLiveSourceDeclaration,
  ProcessLiveSourceBinding,
  ProcessContribution,
  ProcessSpawnConfig,
  // M2b video families
  MetadataFacetContribution,
  AssetDetailSectionContribution,
  OutputFormatContribution,
  CompileOnlyOutputFormatContribution,
  RenderDependentOutputFormatContribution,
  RenderDependentOutputDescriptor,
  ExportService,
  CompileOnlyOutputResult,
  OutputFormatRegistrationOptions,
  // M2b effect family
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
  // M2b transition family
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
  // M2b clip-type family
  ClipTypeContribution,
  ClipRenderer,
  ClipInspector,
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
  // M2b automation/keyframe family
  KeyframeInterpolation,
  Keyframe,
  InterpolatedParam,
  AutomationClipTarget,
  AutomationClipParams,
  // M2b shader family
  ShaderContribution,
  ShaderRegistrationService,
  // M2b searchProvider family
  SearchProviderContribution,
  // M2b parser family
  ParserContribution,
  // M2b command/keybinding/contextMenu families
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
  // M11 live data infrastructure
  LiveSourceKind,
  LiveSource,
  LiveChannelDescriptor,
  LiveSample,
  LivePermissionState,
  LiveBakeResult,
  SteeringDecisionKind,
  SteeringDecision,
  BindingResolutionStatus,
  LiveBinding,
  LiveSessionsService,
  // M3 TimelineOps
  TimelineOps,
  // M3 timeline proposal contracts
  ProposalState,
  ProposalExpiryDetail,
  // M3 timeline source-map contracts
  SourceMapRuntime,
  SourceMapEntry,
  GeneratedObjectMeta,
  TimelineProposal,
  ProposalListener,
  ProposalRuntime,
  ProposalPanelState,
  ProposalPanelAction,
  ProposalEnvelope,
  ProposalImportStatus,
  ProposalImportDiagnostic,
  ProposalImportResult,
  // M1b CompositionGraph types
  CompositionNodeKind,
  CompositionEdgeKind,
  ReferenceState,
  CompositionGraphNode,
  CompositionGraphEdge,
  CompositionReferenceStateEntry,
  CompositionGraphPreviewResult,
  CompositionGraph,
  // M7a Output-format route planning types
  OutputFormatRef,
  ArtifactManifestProfile,
  ArtifactManifestProfileKind,
  VideoArtifactManifestProfile,
  AudioArtifactManifestProfile,
  SidecarArtifactManifestProfile,
  PreviewArtifactManifestProfile,
} from '@/sdk/index';

// ===========================================================================
// Canonical direct module imports (simulate SDK-internal code access)
// ===========================================================================
import {
  type ExtensionId as ExtId_Direct,
  type ContributionId as ContribId_Direct,
  validateExtensionId as validateExtId_Direct,
  validateContributionId as validateContribId_Direct,
} from '../ids';

import type { DisposeHandle as DisposeHandle_Direct } from '../dispose';

import {
  type DiagnosticSeverity as DiagSev_Direct,
  type DiagnosticSource as DiagSrc_Direct,
  DIAGNOSTIC_SOURCE_EXTENSION as DIAG_SRC_EXT_Direct,
  type ExtensionDiagnostic as ExtDiag_Direct,
  type DiagnosticSourceRange as DiagSrcRange_Direct,
  type Diagnostic as Diagnostic_Direct,
  type DiagnosticCollection as DiagColl_Direct,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY as DEFAULT_DIAG_CAP_Direct,
  type CreateDiagnosticCollectionOptions as CreateDiagCollOpts_Direct,
  createDiagnosticCollection as createDiagColl_Direct,
  type ExportDiagnostic as ExportDiag_Direct,
} from '../diagnostics';

import {
  type ContributionKind as ContribKind_Direct,
  type VideoEditorSlotName as Slot_Direct,
  type ExtensionContribution as ExtContrib_Direct,
  KNOWN_CONTRIBUTION_KINDS_SET as KNOWN_CONTRIB_KINDS_SET_Direct,
  ALL_VALID_PLACEMENTS as ALL_VALID_PLACEMENTS_Direct,
  type ManifestValidationMode as ManifValMode_Direct,
  type ManifestValidationResult as ManifValResult_Direct,
  type ExtensionManifest as ExtensionManifest_Direct,
  type ExtensionPermissionDeclaration as ExtensionPermissionDeclaration_Direct,
  type InstalledExtensionPackage as InstalledExtensionPackage_Direct,
  validateManifest as validateManifest_Direct,
  validateInstalledPackage as validateInstalledPackage_Direct,
} from '../manifest';

import type {
  DependencyPosture as DepPosture_Direct,
  ExtensionDependency as ExtDep_Direct,
  IntegrityAlgorithm as IntAlg_Direct,
  IntegrityHash as IntHash_Direct,
  MigrationHookKind as MigHookKind_Direct,
  MigrationDeclaration as MigDecl_Direct,
  InstalledExtensionMetadata as InstExtMeta_Direct,
} from '../packaging';

import type {
  ProjectExtensionRequirement as ProjExtReq_Direct,
  ProjectExtensionRequirements as ProjExtReqs_Direct,
} from '../projectRequirements';

import type {
  ExtensionSettingsSchema as ExtSetSchema_Direct,
  ExtensionSettingsService as ExtSetSvc_Direct,
} from '../settings';

import type {
  TargetContext as TargetCtx_Direct,
  TargetContextPayload as TargetCtxPayload_Direct,
  CommandRunContext as CmdRunCtx_Direct,
  CommandHandler as CmdHandler_Direct,
  CommandRegistrationOptions as CmdRegOpts_Direct,
} from '../commands';

import type {
  ExtensionChromeService as ChromeSvc_Direct,
  ChromeEvent as ChromeEvt_Direct,
  ChromeToastPayload as ChromeToast_Direct,
  ChromeProgressPayload as ChromeProg_Direct,
  ChromeSavePayload as ChromeSave_Direct,
  ChromeRenderStatusPayload as ChromeRender_Direct,
  ChromeEventPayload as ChromeEvtPayload_Direct,
} from '../chrome';

import {
  type ExtensionI18nService as I18nSvc_Direct,
  type ExtensionDiagnosticsService as ExtDiagSvc_Direct,
  type CreativeContext as CreativeCtx_Direct,
  type ExtensionCommandService as ExtCmdSvc_Direct,
  type ExtensionContext as ExtCtx_Direct,
  createCreativeContextStubs as createCreativeStubs_Direct,
  ExtensionNotImplementedError as NotImplErr_Direct,
  CREATIVE_MEMBER_MILESTONE as CREATIVE_MEMBER_MILESTONE_Direct,
  disposeExtensionContextServices as disposeExtCtxSvc_Direct,
  CONTEXT_DISPOSE_SYMBOL as CTX_DISPOSE_SYM_Direct,
} from '../context';

import {
  type ExtensionActivateFn as ActivateFn_Direct,
  type ReighExtension as ReighExt_Direct,
  type DefineExtensionOptions as DefExtOpts_Direct,
  defineExtension as defExt_Direct,
} from '../lifecycle';

import type {
  CapabilityVersion as CapVer_Direct,
  CapabilitySourceRef as CapSrcRef_Direct,
  RouteFitMetadata as RouteFit_Direct,
  CapabilityRequirement as CapReq_Direct,
  IntegrationCapabilities as IntCap_Direct,
  SamplingStrategy as SampStrat_Direct,
  SamplingSourceRef as SampSrcRef_Direct,
  SamplingRange as SampRange_Direct,
  SamplingAttachmentKind as SampAttachKind_Direct,
  SamplingAttachmentRule as SampAttachRule_Direct,
  SamplingConfig as SampCfg_Direct,
  SamplingResultItem as SampResultItem_Direct,
  SamplingResult as SampResult_Direct,
  ProcessRoundtripRequest as ProcRRReq_Direct,
  ProcessRoundtripAction as ProcRRAction_Direct,
  ProcessRoundtripResult as ProcRRResult_Direct,
  ProcessProgressEvent as ProcProgEvt_Direct,
  ProcessLogSummary as ProcLogSum_Direct,
} from '../capabilities';

// M2b video family direct imports
import type { MetadataFacetContribution as MetadataFacetContribution_Direct } from '../video/families/metadataFacet';
import type { AssetDetailSectionContribution as AssetDetailSectionContribution_Direct } from '../video/families/assetDetailSections';
import type {
  OutputFormatContribution as OutputFormatContribution_Direct,
  CompileOnlyOutputFormatContribution as CompileOnlyOutputFormatContribution_Direct,
  RenderDependentOutputFormatContribution as RenderDependentOutputFormatContribution_Direct,
  RenderDependentOutputDescriptor as RenderDependentOutputDescriptor_Direct,
} from '../video/families/outputFormats';
import type {
  ExportService as ExportService_Direct,
  CompileOnlyOutputResult as CompileOnlyOutputResult_Direct,
  OutputFormatRegistrationOptions as OutputFormatRegistrationOptions_Direct,
} from '../video/exports/outputFormats';
import type {
  EffectContribution as EffectContribution_Direct,
  EffectComponent as EffectComponent_Direct,
  EffectParameterDefinition as EffectParameterDefinition_Direct,
  EffectParameterSchema as EffectParameterSchema_Direct,
  EffectRegistrationOptions as EffectRegistrationOptions_Direct,
  EffectRegistrationService as EffectRegistrationService_Direct,
} from '../video/families/effects';
import type {
  TransitionContribution as TransitionContribution_Direct,
  TransitionRenderer as TransitionRenderer_Direct,
  TransitionParameterDefinition as TransitionParameterDefinition_Direct,
  TransitionParameterSchema as TransitionParameterSchema_Direct,
  TransitionRegistrationOptions as TransitionRegistrationOptions_Direct,
  TransitionRegistrationService as TransitionRegistrationService_Direct,
} from '../video/families/transitions';
import type {
  ClipTypeContribution as ClipTypeContribution_Direct,
  ClipRenderer as ClipRenderer_Direct,
  ClipInspector as ClipInspector_Direct,
  ClipParameterDefinition as ClipParameterDefinition_Direct,
  ClipParameterSchema as ClipParameterSchema_Direct,
  ClipTypeRegistrationOptions as ClipTypeRegistrationOptions_Direct,
  ClipTypeRegistrationService as ClipTypeRegistrationService_Direct,
} from '../video/families/clipTypeContributions';
import type {
  KeyframeInterpolation as KeyframeInterpolation_Direct,
  Keyframe as Keyframe_Direct,
  InterpolatedParam as InterpolatedParam_Direct,
  AutomationClipTarget as AutomationClipTarget_Direct,
  AutomationClipParams as AutomationClipParams_Direct,
} from '../video/families/automation';
import type {
  ShaderContribution as ShaderContribution_Direct,
  ShaderRegistrationService as ShaderRegistrationService_Direct,
} from '../video/families/shaders';
import type {
  AgentToolContribution as AgentToolContribution_Direct,
  AgentToolInputSchema as AgentToolInputSchema_Direct,
  AgentToolInputProperty as AgentToolInputProperty_Direct,
  ToolResultFamily as ToolResultFamily_Direct,
  ToolResult as ToolResult_Direct,
  ToolMutationProposalResult as ToolMutationProposalResult_Direct,
  ToolGenerationSessionResult as ToolGenerationSessionResult_Direct,
  ToolMaterialArtifactResult as ToolMaterialArtifactResult_Direct,
  ToolEnrichmentSearchResult as ToolEnrichmentSearchResult_Direct,
  ToolExportResult as ToolExportResult_Direct,
  ToolProcessResult as ToolProcessResult_Direct,
  ToolUISummaryResult as ToolUISummaryResult_Direct,
  ToolSourceRef as ToolSourceRef_Direct,
  ToolArtifactRef as ToolArtifactRef_Direct,
  ToolSearchResultMatch as ToolSearchResultMatch_Direct,
  ToolResultDiagnostic as ToolResultDiagnostic_Direct,
  AgentToolInvocationRequest as AgentToolInvocationRequest_Direct,
  AgentToolRequestContext as AgentToolRequestContext_Direct,
  AgentToolExportContext as AgentToolExportContext_Direct,
  GenerationSession as GenerationSession_Direct,
  AgentToolRegistrationService as AgentToolRegistrationService_Direct,
  AgentToolHandler as AgentToolHandler_Direct,
} from '../video/families/agentTools';
import type {
  ProcessContribution as ProcessContribution_Direct,
  ProcessSpawnConfig as ProcessSpawnConfig_Direct,
  ProcessOutputKind as ProcessOutputKind_Direct,
  ProcessLiveSourceValueShape as ProcessLiveSourceValueShape_Direct,
  ProcessLiveSourceDeclaration as ProcessLiveSourceDeclaration_Direct,
  ProcessLiveSourceBinding as ProcessLiveSourceBinding_Direct,
  ProcessSpec as ProcessSpec_Direct,
  ProcessLifecycleState as ProcessLifecycleState_Direct,
  ProcessStatus as ProcessStatus_Direct,
} from '../video/families/processes';
import type { SearchProviderContribution as SearchProviderContribution_Direct } from '../video/families/searchProviders';
import type { ParserContribution as ParserContribution_Direct } from '../video/families/parsers';
import type { ParserInput as ParserInput_Direct, ParserResult as ParserResult_Direct, ParserDiagnostic as ParserDiagnostic_Direct, ParserHandler as ParserHandler_Direct } from '../video/assets/parsers';
import type { CommandContribution as CommandContribution_Direct } from '../video/families/commands';
import type { KeybindingContribution as KeybindingContribution_Direct } from '../video/families/keybindings';
import type { ContextMenuItemContribution as ContextMenuItemContribution_Direct } from '../video/families/contextMenuItems';

// M3 timeline proposal contracts (not a contribution family)
import type {
  ProposalState as ProposalState_Direct,
  ProposalExpiryDetail as ProposalExpiryDetail_Direct,
  TimelineProposal as TimelineProposal_Direct,
  ProposalListener as ProposalListener_Direct,
  ProposalRuntime as ProposalRuntime_Direct,
  ProposalPanelState as ProposalPanelState_Direct,
  ProposalPanelAction as ProposalPanelAction_Direct,
  ProposalEnvelope as ProposalEnvelope_Direct,
  ProposalImportStatus as ProposalImportStatus_Direct,
  ProposalImportDiagnostic as ProposalImportDiagnostic_Direct,
  ProposalImportResult as ProposalImportResult_Direct,
} from '../video/timeline/proposals';

// M3 timeline source-map contracts (not a contribution family)
import type {
  SourceMapRuntime as SourceMapRuntime_Direct,
  SourceMapEntry as SourceMapEntry_Direct,
  GeneratedObjectMeta as GeneratedObjectMeta_Direct,
} from '../video/timeline/sourceMap';

// M3 TimelineOps (not a contribution family)
import type { TimelineOps as TimelineOps_Direct } from '../video/timeline/timelineOps';

// M11 live data infrastructure (not a contribution family)
import type {
  LiveSourceKind as LiveSourceKind_Direct,
  LiveSource as LiveSource_Direct,
  LiveChannelDescriptor as LiveChannelDescriptor_Direct,
  LiveSample as LiveSample_Direct,
  LivePermissionState as LivePermissionState_Direct,
  LiveBakeResult as LiveBakeResult_Direct,
  SteeringDecisionKind as SteeringDecisionKind_Direct,
  SteeringDecision as SteeringDecision_Direct,
  BindingResolutionStatus as BindingResolutionStatus_Direct,
  LiveBinding as LiveBinding_Direct,
  LiveSessionsService as LiveSessionsService_Direct,
} from '../video/liveData';

// M1b CompositionGraph direct imports
import {
  type CompositionNodeKind as CompNodeKind_Direct,
  type CompositionEdgeKind as CompEdgeKind_Direct,
  type ReferenceState as RefState_Direct,
  type CompositionGraphNode as CompGraphNode_Direct,
  type CompositionGraphEdge as CompGraphEdge_Direct,
  type CompositionReferenceStateEntry as CompRefStateEntry_Direct,
  type CompositionGraphPreviewResult as CompGraphPreview_Direct,
  type CompositionGraph as CompGraph_Direct,
  COMPOSITION_NODE_KINDS as COMP_NODE_KINDS_Direct,
  COMPOSITION_EDGE_KINDS as COMP_EDGE_KINDS_Direct,
  REFERENCE_STATES as REF_STATES_Direct,
} from '../video/composition/graph';

// ===========================================================================
// Smoke coverage: each module family is exercised through a focused test
// that confirms its representative names are reachable and well-formed.
// ===========================================================================

// ── ids ────────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — ids', () => {
  it('validateExtensionId is callable from the barrel and returns an array', () => {
    const result = validateExtensionId('my.extension');
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual([]);
  });

  it('validateExtensionId rejects empty strings', () => {
    const result = validateExtensionId('');
    expect(result.length).toBeGreaterThan(0);
  });

  it('validateContributionId delegates to the same validation logic', () => {
    expect(validateContributionId('my.extension')).toEqual([]);
    expect(validateContributionId('')).toEqual(validateExtensionId(''));
  });

  it('canonical direct import yields the same function', () => {
    const barrelResult = validateExtensionId('test.id');
    const directResult = validateExtId_Direct('test.id');
    expect(directResult).toEqual(barrelResult);
  });
});

// ── dispose ────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — dispose', () => {
  it('DisposeHandle type is importable from the barrel (structural check)', () => {
    const handle: DisposeHandle = { dispose: () => {} };
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  it('DisposeHandle type is importable from canonical direct path', () => {
    const handle: DisposeHandle_Direct = { dispose: () => {} };
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });
});

// ── diagnostics ────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — diagnostics', () => {
  it('createDiagnosticCollection is callable from the barrel', () => {
    const coll = createDiagnosticCollection();
    expect(coll).toBeDefined();
    expect(Array.isArray(coll.snapshot)).toBe(true);
    expect(coll.snapshot.length).toBe(0);
  });

  it('DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY is a positive number', () => {
    expect(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY).toBeGreaterThan(0);
  });

  it('DIAGNOSTIC_SOURCE_EXTENSION is the literal "extension"', () => {
    expect(DIAGNOSTIC_SOURCE_EXTENSION).toBe('extension');
  });

  it('canonical direct import yields the same constants', () => {
    const coll = createDiagColl_Direct();
    expect(coll).toBeDefined();
    expect(DIAG_SRC_EXT_Direct).toBe('extension');
    expect(DEFAULT_DIAG_CAP_Direct).toBe(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY);
  });

  it('publish + snapshot works through barrel import', () => {
    const coll = createDiagnosticCollection();
    coll.publish({
      id: 'test.1',
      severity: 'info',
      code: 'test/info',
      message: 'hello',
    });
    expect(coll.snapshot.length).toBe(1);
    expect(coll.snapshot[0].id).toBe('test.1');
  });
});

// ── manifest / validation ──────────────────────────────────────────────────

describe('M2a barrel-import smoke — manifest / validation', () => {
  it('KNOWN_CONTRIBUTION_KINDS_SET is a Set with expected members', () => {
    expect(KNOWN_CONTRIBUTION_KINDS_SET instanceof Set).toBe(true);
    expect(KNOWN_CONTRIBUTION_KINDS_SET.has('slot')).toBe(true);
    expect(KNOWN_CONTRIBUTION_KINDS_SET.has('command')).toBe(true);
  });

  it('ALL_VALID_PLACEMENTS is a readonly array', () => {
    expect(Array.isArray(ALL_VALID_PLACEMENTS)).toBe(true);
    expect(ALL_VALID_PLACEMENTS.length).toBeGreaterThan(0);
    expect(ALL_VALID_PLACEMENTS).toContain('before-default');
  });

  it('canonical direct import yields the same values', () => {
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toEqual(ALL_VALID_PLACEMENTS);
    // Both paths reference the exact same objects (module singleton)
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toBe(ALL_VALID_PLACEMENTS);
  });

  // ── M2b direct import coverage: manifest/package contracts ──────────────

  it('ExtensionManifest is importable from the barrel', () => {
    const manifest: ExtensionManifest = {
      id: 'com.example' as ExtensionId,
      version: '1.0.0',
      label: 'Test Extension',
    };
    expect(manifest.id).toBe('com.example');
    expect(manifest.label).toBe('Test Extension');
  });

  it('ExtensionManifest is importable from canonical direct path', () => {
    const manifest: ExtensionManifest_Direct = {
      id: 'com.example.direct' as ExtensionId,
      version: '2.0.0',
      label: 'Direct Test',
    };
    expect(manifest.id).toBe('com.example.direct');
    expect(manifest.label).toBe('Direct Test');
  });

  it('ExtensionPermissionDeclaration is importable from the barrel', () => {
    const perm: ExtensionPermissionDeclaration = {
      reason: 'Needs network access for API calls',
      posture: {
        network: true,
        filesystem: false,
        env: true,
        processes: false,
      },
    };
    expect(perm.reason).toBe('Needs network access for API calls');
    expect(perm.posture?.network).toBe(true);
    expect(perm.posture?.filesystem).toBe(false);
    expect(perm.posture?.env).toBe(true);
    expect(perm.posture?.processes).toBe(false);
  });

  it('ExtensionPermissionDeclaration is importable from canonical direct path', () => {
    const perm: ExtensionPermissionDeclaration_Direct = {
      reason: 'Direct import test',
      posture: {
        network: false,
        filesystem: true,
        env: false,
        processes: true,
      },
    };
    expect(perm.reason).toBe('Direct import test');
    expect(perm.posture?.filesystem).toBe(true);
    expect(perm.posture?.processes).toBe(true);
  });

  it('InstalledExtensionPackage is importable from the barrel', () => {
    const pkg: InstalledExtensionPackage = {
      metadata: {
        extensionId: 'com.example' as ExtensionId,
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc123' },
        enabled: true,
      },
      manifest: {
        id: 'com.example' as ExtensionId,
        version: '1.0.0',
        label: 'Test',
      },
      bundleContent: 'export function activate() {}',
    };
    expect(pkg.metadata.extensionId).toBe('com.example');
    expect(pkg.bundleContent).toBe('export function activate() {}');
  });

  it('InstalledExtensionPackage is importable from canonical direct path', () => {
    const pkg: InstalledExtensionPackage_Direct = {
      metadata: {
        extensionId: 'com.example.direct' as ExtensionId,
        version: '2.0.0',
        integrity: { algorithm: 'sha256', value: 'def456' },
        enabled: true,
      },
      manifest: {
        id: 'com.example.direct' as ExtensionId,
        version: '2.0.0',
        label: 'Direct Pkg Test',
      },
      bundleContent: '',
    };
    expect(pkg.manifest.label).toBe('Direct Pkg Test');
  });

  it('validateManifest is callable from the barrel and returns a result', () => {
    const result = validateManifest({
      id: 'com.test' as ExtensionId,
      version: '1.0.0',
      label: 'Test',
    }, 'dev');
    expect(result).toBeDefined();
    expect(typeof result.valid).toBe('boolean');
    expect(Array.isArray(result.errors)).toBe(true);
    expect(Array.isArray(result.warnings)).toBe(true);
  });

  it('validateManifest is callable from canonical direct path', () => {
    const result = validateManifest_Direct({
      id: 'com.test.direct' as ExtensionId,
      version: '1.0.0',
      label: 'Direct Test',
    }, 'dev');
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('validateInstalledPackage is callable from the barrel', () => {
    const result = validateInstalledPackage({
      metadata: {
        extensionId: 'com.test' as ExtensionId,
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc123' },
        enabled: true,
      },
      manifest: {
        id: 'com.test' as ExtensionId,
        version: '1.0.0',
        label: 'Test',
      },
      bundleContent: 'export function activate() {}',
    });
    expect(result).toBeDefined();
    expect(typeof result.valid).toBe('boolean');
  });

  it('validateInstalledPackage is callable from canonical direct path', () => {
    const result = validateInstalledPackage_Direct({
      metadata: {
        extensionId: 'com.test.direct' as ExtensionId,
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc123' },
        enabled: true,
      },
      manifest: {
        id: 'com.test.direct' as ExtensionId,
        version: '1.0.0',
        label: 'Direct Test',
        publisher: 'Test Publisher',
        license: 'MIT',
      },
      bundleContent: 'export function activate() {}',
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});

// ── packaging ──────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — packaging', () => {
  it('DependencyPosture accepts valid literal', () => {
    const posture: DependencyPosture = 'required';
    expect(posture).toBe('required');
  });

  it('MigrationHookKind accepts valid literal', () => {
    const kind: MigrationHookKind = 'settings';
    expect(kind).toBe('settings');
  });

  it('InstalledExtensionMetadata has expected shape', () => {
    const meta: InstalledExtensionMetadata = {
      extensionId: 'com.example' as ExtensionId,
      version: '1.0.0',
      integrity: { algorithm: 'sha256', value: 'abc123' },
      enabled: true,
    };
    expect(meta.extensionId).toBe('com.example');
    expect(meta.integrity.algorithm).toBe('sha256');
  });
});

// ── project requirements ───────────────────────────────────────────────────

describe('M2a barrel-import smoke — project requirements', () => {
  it('ProjectExtensionRequirement is importable from the barrel', () => {
    const req: ProjectExtensionRequirement = {
      extensionId: 'com.example.dep',
      versionRange: '>=1.0.0',
      posture: 'required',
    };
    expect(req.extensionId).toBe('com.example.dep');
    expect(req.posture).toBe('required');
  });

  it('ProjectExtensionRequirements is importable from the barrel', () => {
    const reqs: ProjectExtensionRequirements = {
      requirements: [{ extensionId: 'com.example.dep' }],
    };
    expect(reqs.requirements).toHaveLength(1);
    expect(reqs.requirements[0].extensionId).toBe('com.example.dep');
  });

  // ── direct import coverage ──────────────────────────────────────────────

  it('ProjectExtensionRequirement is importable from canonical direct path', () => {
    const req: ProjExtReq_Direct = {
      extensionId: 'com.example.direct',
      versionRange: '>=2.0.0',
      referencedContributionIds: ['contrib-1'],
      integrity: 'sha256-abc',
      posture: 'optional',
    };
    expect(req.extensionId).toBe('com.example.direct');
    expect(req.referencedContributionIds).toContain('contrib-1');
    expect(req.integrity).toBe('sha256-abc');
    expect(req.posture).toBe('optional');
  });

  it('ProjectExtensionRequirements is importable from canonical direct path', () => {
    const reqs: ProjExtReqs_Direct = {
      requirements: [
        { extensionId: 'com.a.direct' },
        { extensionId: 'com.b.direct', posture: 'required' },
      ],
    };
    expect(reqs.requirements).toHaveLength(2);
    expect(reqs.requirements[1].posture).toBe('required');
  });
});

// ── settings ───────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — settings', () => {
  it('ExtensionSettingsSchema has expected shape', () => {
    const schema: ExtensionSettingsSchema = { version: 1 };
    expect(schema.version).toBe(1);
  });

  it('createExtensionSettingsService is callable from the barrel', () => {
    const svc = createExtensionSettingsService('com.example' as ExtensionId, {
      id: 'com.example' as ExtensionId,
      label: 'test',
      apiVersion: 1,
    });
    expect(svc).toBeDefined();
    expect(svc.service).toBeDefined();
    expect(typeof svc.service.get).toBe('function');
    expect(typeof svc.service.set).toBe('function');
  });
});

// ── commands ───────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — commands', () => {
  it('TargetContext accepts valid literal', () => {
    const ctx: TargetContext = 'clip';
    expect(ctx).toBe('clip');
  });

  it('CommandHandler is a callable type', () => {
    const handler: CommandHandler = (_ctx) => {};
    expect(typeof handler).toBe('function');
  });
});

// ── chrome ─────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — chrome', () => {
  it('ChromeEvent accepts valid union member', () => {
    const evt: ChromeEvent = 'toast';
    expect(evt).toBe('toast');
  });

  it('ChromeToastPayload has expected fields', () => {
    const payload: ChromeToastPayload = {
      message: 'hello',
      severity: 'info' as DiagnosticSeverity,
    };
    expect(payload.message).toBe('hello');
    expect(payload.severity).toBe('info');
  });
});

// ── context ────────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — context', () => {
  it('createCreativeContextStubs returns a frozen CreativeContext', () => {
    const ctx = createCreativeContextStubs();
    expect(ctx).toBeDefined();
    expect(Object.isFrozen(ctx)).toBe(true);
  });

  it('stub members throw ExtensionNotImplementedError', () => {
    const ctx = createCreativeContextStubs();
    expect(() => (ctx as any).timeline).toThrow(ExtensionNotImplementedError);
    try {
      (ctx as any).timeline;
    } catch (e) {
      expect(e).toBeInstanceOf(ExtensionNotImplementedError);
      expect((e as ExtensionNotImplementedError).feature).toBe('timeline');
    }
  });

  it('CREATIVE_MEMBER_MILESTONE is a record with expected keys', () => {
    expect(CREATIVE_MEMBER_MILESTONE).toBeDefined();
    expect(typeof CREATIVE_MEMBER_MILESTONE.project).toBe('string');
    expect(typeof CREATIVE_MEMBER_MILESTONE.timeline).toBe('string');
  });

  it('CONTEXT_DISPOSE_SYMBOL is a unique symbol', () => {
    expect(typeof CONTEXT_DISPOSE_SYMBOL).toBe('symbol');
  });

  it('canonical direct imports match barrel values', () => {
    const stubsViaBarrel = createCreativeContextStubs();
    const stubsViaDirect = createCreativeStubs_Direct();
    expect(stubsViaDirect).toBeDefined();
    expect(Object.isFrozen(stubsViaDirect)).toBe(true);

    expect(CREATIVE_MEMBER_MILESTONE_Direct).toBe(CREATIVE_MEMBER_MILESTONE);
    expect(CTX_DISPOSE_SYM_Direct).toBe(CONTEXT_DISPOSE_SYMBOL);
  });
});

// ── lifecycle ──────────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — lifecycle', () => {
  it('defineExtension returns a frozen ReighExtension for a valid manifest', () => {
    const ext = defineExtension({
      manifest: {
        id: 'smoke.lifecycle',
        label: 'Smoke',
        apiVersion: 1,
      },
    });
    expect(ext).toBeDefined();
    expect(Object.isFrozen(ext)).toBe(true);
    expect(ext.manifest.id).toBe('smoke.lifecycle');
  });

  it('defineExtension throws on invalid extension ID', () => {
    expect(() =>
      defineExtension({
        manifest: { id: '', label: 'Bad', apiVersion: 1 },
      }),
    ).toThrow();
  });

  it('canonical direct import defineExtension matches barrel', () => {
    const barrelExt = defineExtension({
      manifest: { id: 'smoke.canon', label: 'Canon', apiVersion: 1 },
    });
    const directExt = defExt_Direct({
      manifest: { id: 'smoke.canon', label: 'Canon', apiVersion: 1 },
    });
    expect(directExt.manifest.id).toBe(barrelExt.manifest.id);
    expect(directExt.manifest.label).toBe(barrelExt.manifest.label);
  });
});

// ── capabilities ───────────────────────────────────────────────────────────

describe('M2a barrel-import smoke — capabilities', () => {
  it('CapabilityRequirement type is importable from the barrel', () => {
    const req: CapabilityRequirement = {
      id: 'test.req',
      sourceRef: { source: 'built-in' },
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: 'deterministic',
    };
    expect(req.id).toBe('test.req');
    expect(req.sourceRef.source).toBe('built-in');
  });

  it('SamplingConfig type is importable from the barrel', () => {
    const cfg: SamplingConfig = {
      strategy: 'whole-timeline',
      sources: [{ kind: 'timeline', id: 't1' }],
    };
    expect(cfg.strategy).toBe('whole-timeline');
    expect(cfg.sources[0].kind).toBe('timeline');
  });

  it('ProcessRoundtripResult type is importable from canonical direct path', () => {
    const result: ProcRRResult_Direct = {
      requestId: 'r1',
      processId: 'p1',
      operationId: 'op1',
      status: 'completed',
      returnedMaterials: [],
    };
    expect(result.status).toBe('completed');
  });
});

// ── metadataFacet (M2b video family) ───────────────────────────────────────

describe('M2b barrel-import smoke — metadataFacet', () => {
  it('MetadataFacetContribution is importable from the public barrel', () => {
    const contrib: MetadataFacetContribution = {
      id: 'test.mf' as any,
      kind: 'metadataFacet',
      fieldPath: 'gps.latitude',
      displayName: 'GPS Latitude',
      valueKind: 'number',
      order: 0,
      aggregationPosture: 'range',
    };
    expect(contrib.kind).toBe('metadataFacet');
    expect(contrib.fieldPath).toBe('gps.latitude');
    expect(contrib.valueKind).toBe('number');
    expect(contrib.displayName).toBe('GPS Latitude');
  });

  it('MetadataFacetContribution is importable from canonical direct path', () => {
    const contrib: MetadataFacetContribution_Direct = {
      id: 'test.mf' as any,
      kind: 'metadataFacet',
      fieldPath: 'integrity.algorithm',
      displayName: 'Hash Algorithm',
      valueKind: 'enum',
      enumValues: ['sha256', 'md5'],
    };
    expect(contrib.kind).toBe('metadataFacet');
    expect(contrib.enumValues).toEqual(['sha256', 'md5']);
  });

  it('optional fields are truly optional', () => {
    const minimal: MetadataFacetContribution = {
      id: 'test.min' as any,
      kind: 'metadataFacet',
      fieldPath: 'extensions.myExt.foo',
      displayName: 'Foo',
      valueKind: 'string',
    };
    expect(minimal.order).toBeUndefined();
    expect(minimal.aggregationPosture).toBeUndefined();
    expect(minimal.enumValues).toBeUndefined();
  });
});

// ── assetDetailSections (M2b video family) ─────────────────────────────────

describe('M2b barrel-import smoke — assetDetailSections', () => {
  it('AssetDetailSectionContribution is importable from the public barrel', () => {
    const contrib: AssetDetailSectionContribution = {
      id: 'my.section' as any,
      kind: 'assetDetailSection',
      title: 'Integrity',
      placement: 'before-default',
      fieldPaths: ['integrity.algorithm', 'integrity.hash'],
      order: 10,
    };
    expect(contrib.kind).toBe('assetDetailSection');
    expect(contrib.title).toBe('Integrity');
    expect(contrib.placement).toBe('before-default');
    expect(contrib.fieldPaths).toEqual(['integrity.algorithm', 'integrity.hash']);
  });

  it('AssetDetailSectionContribution is importable from canonical direct path', () => {
    const contrib: AssetDetailSectionContribution_Direct = {
      id: 'direct.section' as any,
      kind: 'assetDetailSection',
      title: 'GPS',
      placement: 'after-default',
      fieldPaths: ['gps.latitude', 'gps.longitude'],
      order: 20,
    };
    expect(contrib.kind).toBe('assetDetailSection');
    expect(contrib.title).toBe('GPS');
    expect(contrib.placement).toBe('after-default');
    expect(contrib.order).toBe(20);
  });

  it('optional fields are truly optional', () => {
    const minimal: AssetDetailSectionContribution = {
      id: 'minimal.section' as any,
      kind: 'assetDetailSection',
      title: 'Minimal',
      placement: 'before-default',
    };
    expect(minimal.fieldPaths).toBeUndefined();
    expect(minimal.order).toBeUndefined();
    expect(minimal.when).toBeUndefined();
  });
});

// ── outputFormats family (M2b video family) ──────────────────────────────────

describe('M2b barrel-import smoke — outputFormats family', () => {
  it('OutputFormatContribution is importable from the public barrel', () => {
    const contrib: OutputFormatContribution = {
      id: 'my.export' as any,
      kind: 'outputFormat',
      label: 'Metadata JSON',
      requiresRender: false,
      outputExtension: 'json',
      outputMimeType: 'application/json',
    };
    expect(contrib.kind).toBe('outputFormat');
    expect(contrib.requiresRender).toBe(false);
    expect(contrib.outputExtension).toBe('json');
  });

  it('CompileOnlyOutputFormatContribution is importable from the public barrel', () => {
    const contrib: CompileOnlyOutputFormatContribution = {
      id: 'compile.only' as any,
      kind: 'outputFormat',
      label: 'Compile Only',
      requiresRender: false,
      outputExtension: 'json',
    };
    expect(contrib.requiresRender).toBe(false);
  });

  it('RenderDependentOutputFormatContribution is importable from the public barrel', () => {
    const contrib: RenderDependentOutputFormatContribution = {
      id: 'render.dep' as any,
      kind: 'outputFormat',
      label: 'Render Dependent',
      requiresRender: true,
      outputExtension: 'mp4',
      render: {
        routes: ['browser-export'],
      },
    };
    expect(contrib.requiresRender).toBe(true);
    expect(contrib.render.routes).toEqual(['browser-export']);
  });

  it('RenderDependentOutputDescriptor is importable from the public barrel', () => {
    const desc: RenderDependentOutputDescriptor = {
      routes: ['worker-export'],
      requiredCapabilities: ['gpu'],
      determinism: 'deterministic',
      unavailableMessage: 'Worker is offline',
    };
    expect(desc.routes).toEqual(['worker-export']);
    expect(desc.requiredCapabilities).toEqual(['gpu']);
    expect(desc.determinism).toBe('deterministic');
    expect(desc.unavailableMessage).toBe('Worker is offline');
  });

  it('OutputFormatContribution is importable from canonical direct path', () => {
    const contrib: OutputFormatContribution_Direct = {
      id: 'direct.comp' as any,
      kind: 'outputFormat',
      label: 'Direct',
      requiresRender: false,
      outputExtension: 'xml',
    };
    expect(contrib.kind).toBe('outputFormat');
    expect(contrib.label).toBe('Direct');
  });

  it('CompileOnlyOutputFormatContribution is importable from canonical direct path', () => {
    const contrib: CompileOnlyOutputFormatContribution_Direct = {
      id: 'direct.compile' as any,
      kind: 'outputFormat',
      label: 'Direct Compile',
      requiresRender: false,
      outputExtension: 'csv',
    };
    expect(contrib.requiresRender).toBe(false);
  });

  it('RenderDependentOutputFormatContribution is importable from canonical direct path', () => {
    const contrib: RenderDependentOutputFormatContribution_Direct = {
      id: 'direct.render' as any,
      kind: 'outputFormat',
      label: 'Direct Render',
      requiresRender: true,
      outputExtension: 'mov',
      render: {
        routes: ['sidecar-export'],
        processId: 'my-process',
        operationId: 'encode',
        determinism: 'process-dependent',
      },
    };
    expect(contrib.render.processId).toBe('my-process');
    expect(contrib.render.operationId).toBe('encode');
    expect(contrib.render.determinism).toBe('process-dependent');
  });

  it('RenderDependentOutputDescriptor is importable from canonical direct path', () => {
    const desc: RenderDependentOutputDescriptor_Direct = {
      routes: ['preview', 'browser-export'],
    };
    expect(desc.routes.length).toBe(2);
    expect(desc.requiredCapabilities).toBeUndefined();
  });
});

// ── outputFormats (M2b video family) ────────────────────────────────────────

describe('M2b barrel-import smoke — outputFormats', () => {
  it('ExportService is importable from the public barrel', () => {
    const svc: ExportService = {
      registerOutputFormat(_formatId: string, _handler: any) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerOutputFormat).toBe('function');
    const handle = svc.registerOutputFormat('test', () => ({
      data: new Uint8Array(),
      mimeType: 'text/plain',
      filename: 'test.txt',
      hasBlockingErrors: false,
    }));
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  it('CompileOnlyOutputResult is importable from the public barrel', () => {
    const result: CompileOnlyOutputResult = {
      data: new Uint8Array([1, 2, 3]),
      mimeType: 'application/json',
      filename: 'export.json',
      hasBlockingErrors: false,
    };
    expect(result.data.length).toBe(3);
    expect(result.mimeType).toBe('application/json');
    expect(result.filename).toBe('export.json');
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('OutputFormatRegistrationOptions is importable from the public barrel', () => {
    const opts: OutputFormatRegistrationOptions = {
      label: 'My Export',
      description: 'A custom output format',
    };
    expect(opts.label).toBe('My Export');
    expect(opts.description).toBe('A custom output format');
  });

  it('optional fields are truly optional', () => {
    const empty: OutputFormatRegistrationOptions = {};
    expect(empty.label).toBeUndefined();
    expect(empty.description).toBeUndefined();
  });

  it('ExportService is importable from canonical direct path', () => {
    const svc: ExportService_Direct = {
      registerOutputFormat(_formatId, _handler) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerOutputFormat).toBe('function');
    const handle = svc.registerOutputFormat('test', () => ({
      data: new Uint8Array(),
      mimeType: 'text/plain',
      filename: 'test.txt',
      hasBlockingErrors: false,
    }));
    expect(typeof handle.dispose).toBe('function');
  });

  it('CompileOnlyOutputResult is importable from canonical direct path', () => {
    const result: CompileOnlyOutputResult_Direct = {
      data: new Uint8Array(),
      mimeType: 'text/csv',
      filename: 'data.csv',
      hasBlockingErrors: false,
    };
    expect(result.mimeType).toBe('text/csv');
    expect(result.filename).toBe('data.csv');
  });
});

// ── effects family (M2b video family) ──────────────────────────────────────────

describe('M2b barrel-import smoke — effects family', () => {
  it('EffectContribution is importable from the public barrel', () => {
    const contrib: EffectContribution = {
      id: 'my.effect' as any,
      kind: 'effect',
      effectId: 'glow',
      label: 'Glow Effect',
      allowBrowserExport: false,
      allowWorkerExport: false,
      order: 0,
    };
    expect(contrib.kind).toBe('effect');
    expect(contrib.effectId).toBe('glow');
    expect(contrib.label).toBe('Glow Effect');
    expect(contrib.allowBrowserExport).toBe(false);
  });

  it('EffectComponent type accepts a plain object', () => {
    const comp: EffectComponent = { render: () => {} };
    expect(typeof (comp as any).render).toBe('function');
  });

  it('EffectComponent type accepts a function', () => {
    const comp: EffectComponent = () => 'rendered';
    expect(typeof comp).toBe('function');
  });

  it('EffectParameterDefinition is importable from the public barrel', () => {
    const param: EffectParameterDefinition = {
      name: 'intensity',
      label: 'Intensity',
      description: 'Effect intensity',
      type: 'number',
      default: 50,
      min: 0,
      max: 100,
      step: 1,
    };
    expect(param.name).toBe('intensity');
    expect(param.type).toBe('number');
    expect(param.default).toBe(50);
    expect(param.min).toBe(0);
    expect(param.max).toBe(100);
    expect(param.step).toBe(1);
  });

  it('EffectParameterSchema is importable from the public barrel', () => {
    const schema: EffectParameterSchema = [
      { name: 'intensity', label: 'Intensity', description: 'Strength', type: 'number' },
      { name: 'color', label: 'Color', description: 'Tint color', type: 'color' },
    ];
    expect(schema.length).toBe(2);
    expect(schema[0].name).toBe('intensity');
    expect(schema[1].type).toBe('color');
  });

  it('EffectRegistrationOptions is importable from the public barrel', () => {
    const opts: EffectRegistrationOptions = {
      label: 'Custom Glow',
      parameterSchema: [
        { name: 'radius', label: 'Radius', description: 'Glow spread', type: 'number', default: 10 },
      ],
    };
    expect(opts.label).toBe('Custom Glow');
    expect(opts.parameterSchema![0].name).toBe('radius');
  });

  it('optional fields on EffectRegistrationOptions are truly optional', () => {
    const empty: EffectRegistrationOptions = {};
    expect(empty.label).toBeUndefined();
    expect(empty.parameterSchema).toBeUndefined();
  });

  it('EffectRegistrationService is importable from the public barrel', () => {
    const svc: EffectRegistrationService = {
      registerComponent(_effectId: string, _component: EffectComponent, _options?: EffectRegistrationOptions) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerComponent).toBe('function');
    const handle = svc.registerComponent('glow', {});
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('EffectContribution is importable from canonical direct path', () => {
    const contrib: EffectContribution_Direct = {
      id: 'direct.effect' as any,
      kind: 'effect',
      effectId: 'vignette',
      label: 'Vignette',
    };
    expect(contrib.kind).toBe('effect');
    expect(contrib.effectId).toBe('vignette');
  });

  it('EffectParameterDefinition is importable from canonical direct path', () => {
    const param: EffectParameterDefinition_Direct = {
      name: 'opacity',
      label: 'Opacity',
      description: 'Layer opacity',
      type: 'number',
      default: 100,
      min: 0,
      max: 100,
    };
    expect(param.name).toBe('opacity');
    expect(param.default).toBe(100);
  });

  it('EffectRegistrationService is importable from canonical direct path', () => {
    const svc: EffectRegistrationService_Direct = {
      registerComponent(_effectId, _component, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerComponent).toBe('function');
    const handle = svc.registerComponent('test', () => {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ── transitions family (M2b video family) ──────────────────────────────────────

describe('M2b barrel-import smoke — transitions family', () => {
  it('TransitionContribution is importable from the public barrel', () => {
    const contrib: TransitionContribution = {
      id: 'my.transition' as any,
      kind: 'transition',
      transitionId: 'dissolve',
      label: 'Dissolve',
      allowBrowserExport: false,
      allowWorkerExport: false,
      order: 0,
    };
    expect(contrib.kind).toBe('transition');
    expect(contrib.transitionId).toBe('dissolve');
    expect(contrib.label).toBe('Dissolve');
    expect(contrib.allowBrowserExport).toBe(false);
  });

  it('TransitionRenderer type accepts a plain object', () => {
    const renderer: TransitionRenderer = { render: () => {} };
    expect(typeof (renderer as any).render).toBe('function');
  });

  it('TransitionRenderer type accepts a function', () => {
    const renderer: TransitionRenderer = () => 'rendered';
    expect(typeof renderer).toBe('function');
  });

  it('TransitionParameterDefinition is importable from the public barrel', () => {
    const param: TransitionParameterDefinition = {
      name: 'duration',
      label: 'Duration',
      description: 'Transition duration',
      type: 'number',
      default: 1.0,
      min: 0,
      max: 10,
      step: 0.1,
    };
    expect(param.name).toBe('duration');
    expect(param.type).toBe('number');
    expect(param.default).toBe(1.0);
    expect(param.min).toBe(0);
    expect(param.max).toBe(10);
    expect(param.step).toBe(0.1);
  });

  it('TransitionParameterSchema is importable from the public barrel', () => {
    const schema: TransitionParameterSchema = [
      { name: 'duration', label: 'Duration', description: 'Length', type: 'number' },
      { name: 'direction', label: 'Direction', description: 'Swipe direction', type: 'select', options: [{ label: 'Left', value: 'left' }, { label: 'Right', value: 'right' }] },
    ];
    expect(schema.length).toBe(2);
    expect(schema[0].name).toBe('duration');
    expect(schema[1].type).toBe('select');
  });

  it('TransitionRegistrationOptions is importable from the public barrel', () => {
    const opts: TransitionRegistrationOptions = {
      label: 'Custom Dissolve',
      parameterSchema: [
        { name: 'softness', label: 'Softness', description: 'Edge softness', type: 'number', default: 0.5 },
      ],
    };
    expect(opts.label).toBe('Custom Dissolve');
    expect(opts.parameterSchema![0].name).toBe('softness');
  });

  it('optional fields on TransitionRegistrationOptions are truly optional', () => {
    const empty: TransitionRegistrationOptions = {};
    expect(empty.label).toBeUndefined();
    expect(empty.parameterSchema).toBeUndefined();
  });

  it('TransitionRegistrationService is importable from the public barrel', () => {
    const svc: TransitionRegistrationService = {
      registerRenderer(_transitionId: string, _renderer: TransitionRenderer, _options?: TransitionRegistrationOptions) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerRenderer).toBe('function');
    const handle = svc.registerRenderer('dissolve', {});
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('TransitionContribution is importable from canonical direct path', () => {
    const contrib: TransitionContribution_Direct = {
      id: 'direct.transition' as any,
      kind: 'transition',
      transitionId: 'wipe',
      label: 'Wipe',
    };
    expect(contrib.kind).toBe('transition');
    expect(contrib.transitionId).toBe('wipe');
  });

  it('TransitionParameterDefinition is importable from canonical direct path', () => {
    const param: TransitionParameterDefinition_Direct = {
      name: 'angle',
      label: 'Angle',
      description: 'Wipe angle',
      type: 'number',
      default: 90,
      min: 0,
      max: 360,
    };
    expect(param.name).toBe('angle');
    expect(param.default).toBe(90);
  });

  it('TransitionRegistrationService is importable from canonical direct path', () => {
    const svc: TransitionRegistrationService_Direct = {
      registerRenderer(_transitionId, _renderer, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerRenderer).toBe('function');
    const handle = svc.registerRenderer('test', () => {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ── clipType family (M2b video family) ────────────────────────────────────────

describe('M2b barrel-import smoke — clipType family', () => {
  it('ClipTypeContribution is importable from the public barrel', () => {
    const contrib: ClipTypeContribution = {
      id: 'my.clipType' as any,
      kind: 'clipType',
      clipTypeId: 'procedural',
      label: 'Procedural Clip',
      allowBrowserExport: false,
      allowWorkerExport: false,
      order: 0,
    };
    expect(contrib.kind).toBe('clipType');
    expect(contrib.clipTypeId).toBe('procedural');
    expect(contrib.label).toBe('Procedural Clip');
    expect(contrib.allowBrowserExport).toBe(false);
  });

  it('ClipRenderer type accepts a plain object', () => {
    const renderer: ClipRenderer = { render: () => {} };
    expect(typeof (renderer as any).render).toBe('function');
  });

  it('ClipRenderer type accepts a function', () => {
    const renderer: ClipRenderer = () => 'rendered';
    expect(typeof renderer).toBe('function');
  });

  it('ClipInspector type accepts a plain object', () => {
    const inspector: ClipInspector = { render: () => {} };
    expect(typeof (inspector as any).render).toBe('function');
  });

  it('ClipParameterDefinition is importable from the public barrel', () => {
    const param: ClipParameterDefinition = {
      name: 'intensity',
      label: 'Intensity',
      description: 'Clip intensity',
      type: 'number',
      default: 50,
      min: 0,
      max: 100,
      step: 1,
    };
    expect(param.name).toBe('intensity');
    expect(param.type).toBe('number');
    expect(param.default).toBe(50);
    expect(param.min).toBe(0);
    expect(param.max).toBe(100);
    expect(param.step).toBe(1);
  });

  it('ClipParameterSchema is importable from the public barrel', () => {
    const schema: ClipParameterSchema = [
      { name: 'intensity', label: 'Intensity', description: 'Strength', type: 'number' },
      { name: 'color', label: 'Color', description: 'Tint color', type: 'color' },
    ];
    expect(schema.length).toBe(2);
    expect(schema[0].name).toBe('intensity');
    expect(schema[1].type).toBe('color');
  });

  it('ClipTypeRegistrationOptions is importable from the public barrel', () => {
    const opts: ClipTypeRegistrationOptions = {
      label: 'Custom Procedural',
      parameterSchema: [
        { name: 'seed', label: 'Seed', description: 'Random seed', type: 'number', default: 42 },
      ],
    };
    expect(opts.label).toBe('Custom Procedural');
    expect(opts.parameterSchema![0].name).toBe('seed');
  });

  it('optional fields on ClipTypeRegistrationOptions are truly optional', () => {
    const empty: ClipTypeRegistrationOptions = {};
    expect(empty.label).toBeUndefined();
    expect(empty.parameterSchema).toBeUndefined();
  });

  it('ClipTypeRegistrationService is importable from the public barrel', () => {
    const svc: ClipTypeRegistrationService = {
      registerClipType(_clipTypeId: string, _renderer: ClipRenderer, _inspector?: ClipInspector, _options?: ClipTypeRegistrationOptions) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerClipType).toBe('function');
    const handle = svc.registerClipType('procedural', {});
    expect(typeof handle.dispose).toBe('function');
    handle.dispose(); // should not throw
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('ClipTypeContribution is importable from canonical direct path', () => {
    const contrib: ClipTypeContribution_Direct = {
      id: 'direct.clipType' as any,
      kind: 'clipType',
      clipTypeId: 'keyframed',
      label: 'Keyframed',
    };
    expect(contrib.kind).toBe('clipType');
    expect(contrib.clipTypeId).toBe('keyframed');
  });

  it('ClipParameterDefinition is importable from canonical direct path', () => {
    const param: ClipParameterDefinition_Direct = {
      name: 'speed',
      label: 'Speed',
      description: 'Animation speed',
      type: 'number',
      default: 1.0,
      min: 0.1,
      max: 10,
    };
    expect(param.name).toBe('speed');
    expect(param.default).toBe(1.0);
  });

  it('ClipTypeRegistrationService is importable from canonical direct path', () => {
    const svc: ClipTypeRegistrationService_Direct = {
      registerClipType(_clipTypeId, _renderer, _inspector, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerClipType).toBe('function');
    const handle = svc.registerClipType('test', () => {});
    expect(typeof handle.dispose).toBe('function');
  });
});

// ── automation/keyframe family ──────────────────────────────────────────────

describe('M2b barrel-import smoke — automation/keyframe family', () => {
  it('KeyframeInterpolation is importable from the public barrel', () => {
    const mode: KeyframeInterpolation = 'linear';
    expect(mode).toBe('linear');
    const hold: KeyframeInterpolation = 'hold';
    expect(hold).toBe('hold');
  });

  it('Keyframe is importable from the public barrel', () => {
    const kf: Keyframe = {
      time: 1.5,
      value: 100,
      interpolation: 'linear',
    };
    expect(kf.time).toBe(1.5);
    expect(kf.value).toBe(100);
    expect(kf.interpolation).toBe('linear');
  });

  it('InterpolatedParam is importable from the public barrel', () => {
    const param: InterpolatedParam = {
      name: 'opacity',
      value: 0.75,
    };
    expect(param.name).toBe('opacity');
    expect(param.value).toBe(0.75);
  });

  it('AutomationClipTarget is importable from the public barrel', () => {
    const target: AutomationClipTarget = {
      contributionId: 'my.effect',
      parameterPath: 'intensity',
    };
    expect(target.contributionId).toBe('my.effect');
    expect(target.parameterPath).toBe('intensity');
  });

  it('AutomationClipParams is importable from the public barrel', () => {
    const params: AutomationClipParams = {
      target: { contributionId: 'my.effect', parameterPath: 'intensity' },
      keyframes: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 2, value: 100, interpolation: 'linear' },
      ],
      enabled: true,
    };
    expect(params.target.contributionId).toBe('my.effect');
    expect(params.keyframes.length).toBe(2);
    expect(params.enabled).toBe(true);
  });

  it('AutomationClipParams with empty keyframes is valid', () => {
    const params: AutomationClipParams = {
      target: { contributionId: 'x', parameterPath: 'p' },
      keyframes: [],
      enabled: false,
    };
    expect(params.keyframes).toEqual([]);
    expect(params.enabled).toBe(false);
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('Keyframe is importable from canonical direct path', () => {
    const kf: Keyframe_Direct = {
      time: 3.0,
      value: 'active',
      interpolation: 'hold',
    };
    expect(kf.time).toBe(3.0);
    expect(kf.value).toBe('active');
    expect(kf.interpolation).toBe('hold');
  });

  it('AutomationClipTarget is importable from canonical direct path', () => {
    const target: AutomationClipTarget_Direct = {
      contributionId: 'direct.transition',
      parameterPath: 'progress',
    };
    expect(target.contributionId).toBe('direct.transition');
    expect(target.parameterPath).toBe('progress');
  });

  it('AutomationClipParams is importable from canonical direct path', () => {
    const params: AutomationClipParams_Direct = {
      target: { contributionId: 'd', parameterPath: 'p' },
      keyframes: [{ time: 1, value: 50, interpolation: 'linear' }],
      enabled: true,
    };
    expect(params.keyframes[0].time).toBe(1);
    expect(params.keyframes[0].value).toBe(50);
    expect(params.enabled).toBe(true);
  });
});

// ── shader family ──────────────────────────────────────────────────────────

describe('M2b barrel-import smoke — shader family', () => {
  it('ShaderContribution is importable from the public barrel', () => {
    const contrib: ShaderContribution = {
      id: 'test.shader' as ContributionId,
      kind: 'shader',
      shaderId: 'my-shader',
      label: 'Test Shader',
      pass: 'postprocess',
    };
    expect(contrib.kind).toBe('shader');
    expect(contrib.shaderId).toBe('my-shader');
    expect(contrib.label).toBe('Test Shader');
  });

  it('ShaderRegistrationService is importable from the public barrel', () => {
    const svc: ShaderRegistrationService = {
      registerShader(_shaderId, _source, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerShader).toBe('function');
    const handle = svc.registerShader('test', { kind: 'inline', fragment: 'void main() {}' });
    expect(typeof handle.dispose).toBe('function');
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('ShaderContribution is importable from canonical direct path', () => {
    const contrib: ShaderContribution_Direct = {
      id: 'direct.shader' as ContributionId,
      kind: 'shader',
      shaderId: 'direct-shader',
      label: 'Direct Shader',
      pass: 'clip',
    };
    expect(contrib.kind).toBe('shader');
    expect(contrib.shaderId).toBe('direct-shader');
  });

  it('ShaderRegistrationService is importable from canonical direct path', () => {
    const svc: ShaderRegistrationService_Direct = {
      registerShader(_shaderId, _source, _options) {
        return { dispose() {} };
      },
    };
    expect(typeof svc.registerShader).toBe('function');
  });
});

// ── agentTool family (M2b video family) ───────────────────────────────────────

describe('M2b barrel-import smoke — agentTool family', () => {
  it('AgentToolContribution is importable from the public barrel', () => {
    const contrib: AgentToolContribution = {
      id: 'my.agent-tool' as any,
      kind: 'agentTool',
      toolId: 'my-tool',
      label: 'My Agent Tool',
      description: 'A test agent tool',
      order: 0,
    };
    expect(contrib.kind).toBe('agentTool');
    expect(contrib.toolId).toBe('my-tool');
    expect(contrib.label).toBe('My Agent Tool');
  });

  it('AgentToolInputSchema is importable from the public barrel', () => {
    const schema: AgentToolInputSchema = {
      type: 'object',
      properties: {},
      required: [],
    };
    expect(schema.type).toBe('object');
  });

  it('ToolResultFamily union is importable from the public barrel', () => {
    const family: ToolResultFamily = 'mutation/proposal';
    expect(family).toBe('mutation/proposal');
  });

  it('ToolMutationProposalResult is importable from the public barrel', () => {
    const result: ToolMutationProposalResult = {
      family: 'mutation/proposal',
      patches: [],
    };
    expect(result.family).toBe('mutation/proposal');
  });

  it('ToolResultDiagnostic is importable from the public barrel', () => {
    const diag: ToolResultDiagnostic = {
      severity: 'error' as any,
      code: 'TEST',
      message: 'Test diagnostic',
    };
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('TEST');
    expect(diag.message).toBe('Test diagnostic');
  });

  it('AgentToolInvocationRequest is importable from the public barrel', () => {
    const req: AgentToolInvocationRequest = {
      toolId: 'my-tool',
      extensionId: 'my.extension',
      contributionId: 'my.agent-tool',
    };
    expect(req.toolId).toBe('my-tool');
    expect(req.extensionId).toBe('my.extension');
  });

  it('AgentToolRegistrationService is importable from the public barrel', () => {
    const svc: AgentToolRegistrationService = {
      registerTool(_toolId: string, _handler: AgentToolHandler) {
        return { dispose() {} };
      },
      async invokeProcess(_toolId: string, _config: ProcessSpawnConfig) {
        return { family: 'process' as const, diagnostics: [] };
      },
    };
    expect(typeof svc.registerTool).toBe('function');
    expect(typeof svc.invokeProcess).toBe('function');
    const handle = svc.registerTool('test', async (_req) => ({ family: 'ui/summary', summary: 'ok' }));
    expect(typeof handle.dispose).toBe('function');
  });

  it('AgentToolHandler is importable from the public barrel', () => {
    const handler: AgentToolHandler = (_request) => ({
      family: 'ui/summary',
      summary: 'done',
    });
    expect(typeof handler).toBe('function');
    const result = handler({ toolId: 't', extensionId: 'e', contributionId: 'c' });
    expect((result as any).family).toBe('ui/summary');
  });

  it('GenerationSession is importable from the public barrel', () => {
    const session: GenerationSession = {
      id: 'session-1',
      progress: 50,
      progressLabel: 'Halfway',
      cancelled: false,
      completed: false,
      diagnostics: [],
      updateProgress(_p: number, _l?: string) {},
      cancel() {},
      complete(_r?: Record<string, unknown>) {},
    };
    expect(session.id).toBe('session-1');
    expect(session.progress).toBe(50);
    expect(session.cancelled).toBe(false);
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('AgentToolContribution is importable from canonical direct path', () => {
    const contrib: AgentToolContribution_Direct = {
      id: 'my.agent-tool' as any,
      kind: 'agentTool',
      toolId: 'my-tool',
      label: 'Direct Tool',
    };
    expect(contrib.kind).toBe('agentTool');
    expect(contrib.toolId).toBe('my-tool');
  });

  it('AgentToolRegistrationService is importable from canonical direct path', () => {
    const svc: AgentToolRegistrationService_Direct = {
      registerTool(_toolId: string, _handler: AgentToolHandler_Direct) {
        return { dispose() {} };
      },
      async invokeProcess(_toolId: string, _config: ProcessSpawnConfig_Direct) {
        return { family: 'process' as const, diagnostics: [] };
      },
    };
    expect(typeof svc.registerTool).toBe('function');
  });
});

// ── process family (M2b video family) ───────────────────────────────────────

describe('M2b barrel-import smoke — process family', () => {
  it('ProcessContribution is importable from the public barrel', () => {
    const contrib: ProcessContribution = {
      id: 'my.process' as any,
      kind: 'process',
      label: 'My Process',
      order: 0,
      spec: {
        id: 'my-process',
        label: 'My Process',
        spawn: { command: 'node', args: ['script.js'] },
        protocol: 'stdio-jsonrpc',
      },
    };
    expect(contrib.kind).toBe('process');
    expect(contrib.spec.id).toBe('my-process');
  });

  it('ProcessSpawnConfig is importable from the public barrel', () => {
    const config: ProcessSpawnConfig = {
      command: 'python',
      args: ['-m', 'mymodule'],
      env: { PATH: '/usr/bin' },
      cwd: '/tmp',
    };
    expect(config.command).toBe('python');
    expect(config.cwd).toBe('/tmp');
  });

  it('ProcessSpec is importable from canonical direct path', () => {
    const outputKinds: ProcessOutputKind_Direct[] = ['live-source-scalar'];
    const valueShape: ProcessLiveSourceValueShape_Direct = 'scalar';
    const liveSource: ProcessLiveSourceDeclaration_Direct = {
      sourceId: 'preview-scalar',
      valueShape,
      sourceKind: 'generated',
    };
    const spec: ProcessSpec_Direct = {
      id: 'my-process',
      label: 'My Process',
      spawn: { command: 'node' },
      protocol: 'stdio-jsonrpc',
      restartPolicy: 'on-failure',
      operations: [
        {
          id: 'stream-preview',
          label: 'Stream Preview',
          outputKinds,
        },
      ],
      liveSources: [liveSource],
    };
    expect(spec.id).toBe('my-process');
    expect(spec.protocol).toBe('stdio-jsonrpc');
    expect(spec.restartPolicy).toBe('on-failure');
    expect(spec.liveSources?.[0]).toEqual(liveSource);
  });

  it('ProcessLifecycleState is importable from canonical direct path', () => {
    const state: ProcessLifecycleState_Direct = 'ready';
    expect(state).toBe('ready');
    const states: ProcessLifecycleState_Direct[] = ['not-installed', 'stopped', 'starting', 'ready', 'busy', 'degraded', 'failed', 'stopping'];
    expect(states).toContain('ready');
  });

  it('ProcessStatus is importable from canonical direct path', () => {
    const status: ProcessStatus_Direct = {
      processId: 'proc-1',
      state: 'ready' as const,
      pid: 12345,
    };
    expect(status.processId).toBe('proc-1');
    expect(status.state).toBe('ready');
  });

  it('ProcessLiveSourceBinding is importable from the public barrel', () => {
    const binding: ProcessLiveSourceBinding = {
      processId: 'my-process',
    };
    expect(binding.processId).toBe('my-process');
  });

  // ── direct import coverage ──────────────────────────────────────────────────

  it('ProcessContribution is importable from canonical direct path', () => {
    const contrib: ProcessContribution_Direct = {
      id: 'my.process' as any,
      kind: 'process',
      spec: {
        id: 'direct-process',
        label: 'Direct Process',
        spawn: { command: 'node' },
        protocol: 'stdio-jsonrpc',
      },
    };
    expect(contrib.kind).toBe('process');
    expect(contrib.spec.id).toBe('direct-process');
  });

  it('ProcessSpawnConfig is importable from canonical direct path', () => {
    const config: ProcessSpawnConfig_Direct = {
      command: 'echo',
      args: ['hello'],
    };
    expect(config.command).toBe('echo');
  });

  it('process live-source declaration types are importable from canonical direct path', () => {
    const outputKinds: ProcessOutputKind_Direct[] = ['live-source-structured'];
    const valueShape: ProcessLiveSourceValueShape_Direct = 'structured';
    const liveSource: ProcessLiveSourceDeclaration_Direct = {
      sourceId: 'direct-preview',
      valueShape,
    };
    const binding: ProcessLiveSourceBinding_Direct = {
      processId: 'direct-process',
    };

    expect(outputKinds).toEqual(['live-source-structured']);
    expect(liveSource.valueShape).toBe('structured');
    expect(binding.processId).toBe('direct-process');
  });
});

// ── searchProviders (M2b video family) ──────────────────────────────────────

describe('M2b barrel-import smoke — searchProviders', () => {
  it('SearchProviderContribution is importable from the public barrel', () => {
    const contrib: SearchProviderContribution = {
      id: 'semantic-search' as any,
      kind: 'searchProvider',
      label: 'Semantic Search',
      description: 'Semantic search over image embeddings',
      resultKinds: ['asset', 'material'],
      order: 0,
    };
    expect(contrib.kind).toBe('searchProvider');
    expect(contrib.label).toBe('Semantic Search');
    expect(contrib.resultKinds).toEqual(['asset', 'material']);
    expect(contrib.description).toBe('Semantic search over image embeddings');
  });

  it('SearchProviderContribution is importable from canonical direct path', () => {
    const contrib: SearchProviderContribution_Direct = {
      id: 'direct.search' as any,
      kind: 'searchProvider',
      label: 'Direct Search',
      resultKinds: ['asset'],
    };
    expect(contrib.kind).toBe('searchProvider');
    expect(contrib.label).toBe('Direct Search');
    expect(contrib.resultKinds).toEqual(['asset']);
  });

  it('optional fields are truly optional', () => {
    const minimal: SearchProviderContribution = {
      id: 'min.search' as any,
      kind: 'searchProvider',
      label: 'Minimal Search',
    };
    expect(minimal.description).toBeUndefined();
    expect(minimal.resultKinds).toBeUndefined();
    expect(minimal.order).toBeUndefined();
  });
});

// ── parsers (M2b video family) ───────────────────────────────────────────────

describe('M2b barrel-import smoke — parsers (family)', () => {
  it('ParserContribution is importable from the public barrel', () => {
    const contrib: ParserContribution = {
      id: 'exif-parser' as any,
      kind: 'parser',
      label: 'EXIF Parser',
      acceptMimeTypes: ['image/jpeg', 'image/tiff'],
      acceptExtensions: ['jpg', 'jpeg', 'tiff'],
      maxBytes: 50_000_000,
      required: false,
      order: 0,
    };
    expect(contrib.kind).toBe('parser');
    expect(contrib.label).toBe('EXIF Parser');
    expect(contrib.acceptMimeTypes).toEqual(['image/jpeg', 'image/tiff']);
    expect(contrib.acceptExtensions).toEqual(['jpg', 'jpeg', 'tiff']);
    expect(contrib.maxBytes).toBe(50_000_000);
    expect(contrib.required).toBe(false);
  });

  it('ParserContribution is importable from canonical direct path', () => {
    const contrib: ParserContribution_Direct = {
      id: 'direct.parser' as any,
      kind: 'parser',
      label: 'Direct Parser',
    };
    expect(contrib.kind).toBe('parser');
    expect(contrib.label).toBe('Direct Parser');
  });

  it('optional fields are truly optional', () => {
    const minimal: ParserContribution = {
      id: 'min.parser' as any,
      kind: 'parser',
      label: 'Minimal Parser',
    };
    expect(minimal.acceptMimeTypes).toBeUndefined();
    expect(minimal.acceptExtensions).toBeUndefined();
    expect(minimal.maxBytes).toBeUndefined();
    expect(minimal.required).toBeUndefined();
    expect(minimal.order).toBeUndefined();
  });
});

// ── parsers (M2b video assets — runtime) ─────────────────────────────────────

describe('M2b barrel-import smoke — parsers (assets/runtime)', () => {
  it('ParserInput is constructable from barrel', () => {
    const input: ParserInput_Direct = {
      assetKey: 'asset-001',
      mimeType: 'image/jpeg',
      extension: 'jpg',
      byteSize: 1024,
    };
    expect(input.assetKey).toBe('asset-001');
    expect(input.mimeType).toBe('image/jpeg');
  });

  it('ParserResult is constructable from barrel', () => {
    const result: ParserResult_Direct = {
      metadata: {},
      diagnostics: [],
    };
    expect(result.metadata).toEqual({});
    expect(result.diagnostics).toEqual([]);
  });

  it('ParserDiagnostic is constructable from barrel', () => {
    const diag: ParserDiagnostic_Direct = {
      severity: 'error' as any,
      code: 'parser/unsupported-mime-type',
      message: 'Unsupported MIME type',
    };
    expect(diag.code).toBe('parser/unsupported-mime-type');
    expect(diag.message).toBe('Unsupported MIME type');
  });

  it('ParserHandler type is assignable', () => {
    const handler: ParserHandler_Direct = (input) => ({
      metadata: { extensions: { test: { parsed: true } } } as any,
    });
    expect(typeof handler).toBe('function');
    const result = handler({
      assetKey: 'test',
      mimeType: 'image/png',
      extension: 'png',
      byteSize: 100,
    });
    expect(result).toBeDefined();
  });
});

// ── commands (M2b video family) ───────────────────────────────────────────────

describe('M2b barrel-import smoke — commands (family)', () => {
  it('CommandContribution is importable from the public barrel', () => {
    const contrib: CommandContribution = {
      id: 'my.command' as any,
      kind: 'command',
      command: 'myExtension.doSomething',
      label: 'Do Something',
    };
    expect(contrib.kind).toBe('command');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.label).toBe('Do Something');
  });

  it('CommandContribution is importable from canonical direct path', () => {
    const contrib: CommandContribution_Direct = {
      id: 'direct.cmd' as any,
      kind: 'command',
      command: 'direct.command',
      label: 'Direct Command',
    };
    expect(contrib.kind).toBe('command');
    expect(contrib.label).toBe('Direct Command');
  });

  it('optional fields are truly optional', () => {
    const minimal: CommandContribution = {
      id: 'min.cmd' as any,
      kind: 'command',
      command: 'min',
      label: 'Minimal',
    };
    expect(minimal.category).toBeUndefined();
    expect(minimal.when).toBeUndefined();
    expect(minimal.order).toBeUndefined();
  });
});

// ── keybindings (M2b video family) ────────────────────────────────────────────

describe('M2b barrel-import smoke — keybindings (family)', () => {
  it('KeybindingContribution is importable from the public barrel', () => {
    const contrib: KeybindingContribution = {
      id: 'my.keybinding' as any,
      kind: 'keybinding',
      command: 'myExtension.doSomething',
      key: 'CtrlOrCmd+K',
    };
    expect(contrib.kind).toBe('keybinding');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.key).toBe('CtrlOrCmd+K');
  });

  it('KeybindingContribution is importable from canonical direct path', () => {
    const contrib: KeybindingContribution_Direct = {
      id: 'direct.key' as any,
      kind: 'keybinding',
      command: 'direct.command',
      key: 'Alt+Shift+R',
    };
    expect(contrib.kind).toBe('keybinding');
    expect(contrib.key).toBe('Alt+Shift+R');
  });

  it('optional fields are truly optional', () => {
    const minimal: KeybindingContribution = {
      id: 'min.key' as any,
      kind: 'keybinding',
      command: 'min',
      key: 'Ctrl+K',
    };
    expect(minimal.when).toBeUndefined();
    expect(minimal.order).toBeUndefined();
  });
});

// ── contextMenuItems (M2b video family) ────────────────────────────────────────

describe('M2b barrel-import smoke — contextMenuItems (family)', () => {
  it('ContextMenuItemContribution is importable from the public barrel', () => {
    const contrib: ContextMenuItemContribution = {
      id: 'my.menu' as any,
      kind: 'contextMenuItem',
      command: 'myExtension.doSomething',
      target: 'clip' as any,
    };
    expect(contrib.kind).toBe('contextMenuItem');
    expect(contrib.command).toBe('myExtension.doSomething');
    expect(contrib.target).toBe('clip');
  });

  it('ContextMenuItemContribution is importable from canonical direct path', () => {
    const contrib: ContextMenuItemContribution_Direct = {
      id: 'direct.menu' as any,
      kind: 'contextMenuItem',
      command: 'direct.command',
      target: 'track' as any,
    };
    expect(contrib.kind).toBe('contextMenuItem');
    expect(contrib.target).toBe('track');
  });

  it('optional fields are truly optional', () => {
    const minimal: ContextMenuItemContribution = {
      id: 'min.menu' as any,
      kind: 'contextMenuItem',
      command: 'min',
      target: 'timeline-area' as any,
    };
    expect(minimal.label).toBeUndefined();
    expect(minimal.when).toBeUndefined();
    expect(minimal.order).toBeUndefined();
    expect(minimal.icon).toBeUndefined();
  });
});

// ── M11 live data infrastructure (not a contribution family) ────────────────

describe('M2b barrel-import smoke — live data infrastructure', () => {
  it('LiveSourceKind is importable from the public barrel', () => {
    const kind: LiveSourceKind = 'webcam';
    expect(kind).toBe('webcam');
    const kinds: LiveSourceKind[] = ['webcam', 'microphone', 'midi', 'generated', 'custom'];
    expect(kinds).toHaveLength(5);
  });

  it('LiveSource is importable from the public barrel', () => {
    const source: LiveSource = {
      id: 'source-1',
      kind: 'webcam',
      status: 'active',
      diagnostics: [],
    };
    expect(source.id).toBe('source-1');
    expect(source.status).toBe('active');
  });

  it('LiveChannelDescriptor is importable from the public barrel', () => {
    const ch: LiveChannelDescriptor = 'video.main' as LiveChannelDescriptor;
    expect(typeof ch).toBe('string');
  });

  it('LiveSample is importable from the public barrel', () => {
    const sample: LiveSample = {
      channelId: 'audio.main' as LiveChannelDescriptor,
      frame: { timestamp: 0, data: new Uint8Array(), format: 'raw' },
      sequenceNumber: 1,
    };
    expect(sample.sequenceNumber).toBe(1);
  });

  it('LivePermissionState is importable from the public barrel', () => {
    const state: LivePermissionState = 'granted';
    expect(state).toBe('granted');
    const states: LivePermissionState[] = ['prompt', 'granted', 'denied', 'unavailable'];
    expect(states).toContain('denied');
  });

  it('LiveBakeResult is importable from the public barrel', () => {
    const result: LiveBakeResult = {
      sourceId: 'src-1',
      targets: [],
      diagnostics: [],
      success: true,
    };
    expect(result.success).toBe(true);
  });

  it('SteeringDecision is importable from the public barrel', () => {
    const decision: SteeringDecision = {
      kind: 'supersede',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 0,
        steerHash: 'abc',
        parentRefs: [],
        producerVersion: '1.0.0',
        provenance: { prompt: 'test', model: 'test', seed: '42' },
      },
    };
    expect(decision.kind).toBe('supersede');
  });

  it('LiveBinding is importable from the public barrel', () => {
    const binding: LiveBinding = {
      bindingId: 'bind-1',
      sourceId: 'src-1',
      status: 'resolved',
    };
    expect(binding.bindingId).toBe('bind-1');
    expect(binding.status).toBe('resolved');
  });

  it('LiveSessionsService is importable from the public barrel', () => {
    const svc: LiveSessionsService = {
      registerSource(_source) { return { dispose() {} }; },
      getSource(_sourceId) { return undefined; },
      listSources() { return []; },
      openChannel(_sourceId, _kind) { return 'ch' as LiveChannelDescriptor; },
      closeChannel(_channelId) {},
      getChannelMetadata(_channelId) { return undefined; },
      pushSample(_channelId, _frame) {},
      subscribeSamples(_channelId, _listener) { return { dispose() {} }; },
      bake(_selection) { return { sourceId: '', targets: [], diagnostics: [], success: true }; },
      removeLiveBindings(_sourceId) {},
      resolveBinding(_bindingId) { return { bindingId: '', status: 'unresolved' }; },
      getBindingMetadata() { return { bindings: [], unresolvedCount: 0, orphanedCount: 0, disposedCount: 0 }; },
      applySteeringDecision(_decision) {},
      getDiagnostics(_sourceId) { return []; },
    };
    expect(typeof svc.registerSource).toBe('function');
    expect(typeof svc.bake).toBe('function');
  });

  // ── direct import coverage ──────────────────────────────────────────────

  it('LiveSourceKind is importable from canonical direct path', () => {
    const kind: LiveSourceKind_Direct = 'midi';
    expect(kind).toBe('midi');
  });

  it('LiveSource is importable from canonical direct path', () => {
    const source: LiveSource_Direct = {
      id: 'direct-source',
      kind: 'microphone',
      status: 'inactive',
      diagnostics: [],
    };
    expect(source.id).toBe('direct-source');
  });

  it('LiveChannelDescriptor is importable from canonical direct path', () => {
    const ch: LiveChannelDescriptor_Direct = 'data.sensor' as LiveChannelDescriptor_Direct;
    expect(typeof ch).toBe('string');
  });

  it('LiveSample is importable from canonical direct path', () => {
    const sample: LiveSample_Direct = {
      channelId: 'video.main' as LiveChannelDescriptor_Direct,
      frame: { timestamp: 100, data: new ArrayBuffer(0), format: 'encoded' },
      sequenceNumber: 5,
    };
    expect(sample.sequenceNumber).toBe(5);
  });

  it('LiveBinding is importable from canonical direct path', () => {
    const binding: LiveBinding_Direct = {
      bindingId: 'direct-bind',
      sourceId: 'direct-src',
      status: 'missing',
    };
    expect(binding.status).toBe('missing');
  });

  it('LiveSessionsService is importable from canonical direct path', () => {
    const svc: LiveSessionsService_Direct = {
      registerSource(_source) { return { dispose() {} }; },
      getSource(_sourceId) { return undefined; },
      listSources() { return []; },
      openChannel(_sourceId, _kind) { return 'ch' as LiveChannelDescriptor_Direct; },
      closeChannel(_channelId) {},
      getChannelMetadata(_channelId) { return undefined; },
      pushSample(_channelId, _frame) {},
      subscribeSamples(_channelId, _listener) { return { dispose() {} }; },
      bake(_selection) { return { sourceId: '', targets: [], diagnostics: [], success: true }; },
      removeLiveBindings(_sourceId) {},
      resolveBinding(_bindingId) { return { bindingId: '', status: 'unresolved' }; },
      getBindingMetadata() { return { bindings: [], unresolvedCount: 0, orphanedCount: 0, disposedCount: 0 }; },
      applySteeringDecision(_decision) {},
      getDiagnostics(_sourceId) { return []; },
    };
    expect(typeof svc.subscribeSamples).toBe('function');
  });
});

// ── M3 timeline proposal contracts ──────────────────────────────────────────

describe('M2b barrel-import smoke — proposals', () => {
  it('ProposalState is importable from the public barrel', () => {
    const state: ProposalState = 'pending';
    expect(state).toBe('pending');
    const expired: ProposalState = 'expired';
    expect(expired).toBe('expired');
  });

  it('ProposalExpiryDetail is importable from the public barrel', () => {
    const detail: ProposalExpiryDetail = {
      reason: 'base-version-mismatch',
      baseVersion: 5,
      currentVersion: 7,
      createdAt: 1000,
      expiredAt: 2000,
    };
    expect(detail.reason).toBe('base-version-mismatch');
    expect(detail.baseVersion).toBe(5);
  });

  it('TimelineProposal is importable from the public barrel', () => {
    const proposal: TimelineProposal = {
      id: 'prop-1',
      source: 'test.extension',
      rationale: 'test rationale',
      state: 'pending',
      patch: { ops: [] },
      baseVersion: 1,
      previewable: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    expect(proposal.id).toBe('prop-1');
    expect(proposal.state).toBe('pending');
    expect(proposal.patch.ops).toEqual([]);
  });

  it('ProposalListener is importable from the public barrel', () => {
    const listener: ProposalListener = (_proposal) => {};
    expect(typeof listener).toBe('function');
  });

  it('ProposalRuntime is importable from the public barrel', () => {
    const runtime: ProposalRuntime = {
      subscribe(_listener) { return { dispose() {} }; },
      create(_input) {
        return {
          id: 'p1', source: 'test', state: 'pending',
          patch: { ops: [] }, baseVersion: 1, previewable: true,
          createdAt: 0, updatedAt: 0,
        };
      },
      preview(_proposalId) { return { diff: { entries: [] } }; },
      accept(_proposalId) { return { entries: [] }; },
      reject(_proposalId, _reason) {},
      get(_proposalId) { return undefined; },
      list(_state) { return []; },
      currentVersion: 1,
      expireStale(_maxAgeMs) { return []; },
    };
    expect(typeof runtime.subscribe).toBe('function');
    expect(runtime.currentVersion).toBe(1);
  });

  it('ProposalPanelState is importable from the public barrel', () => {
    const state: ProposalPanelState = {
      proposals: [],
      selectedProposalId: null,
      visible: false,
    };
    expect(state.proposals).toEqual([]);
    expect(state.selectedProposalId).toBeNull();
  });

  it('ProposalPanelAction is importable from the public barrel', () => {
    const select: ProposalPanelAction = { type: 'select', proposalId: 'p1' };
    expect(select.type).toBe('select');
    const toggle: ProposalPanelAction = { type: 'toggleVisibility' };
    expect(toggle.type).toBe('toggleVisibility');
  });

  it('ProposalEnvelope is importable from the public barrel', () => {
    const envelope: ProposalEnvelope = {
      proposals: [],
      baseVersion: 1,
      summary: 'test',
      mutationApplied: false,
    };
    expect(envelope.baseVersion).toBe(1);
    expect(envelope.mutationApplied).toBe(false);
  });

  it('ProposalImportStatus is importable from the public barrel', () => {
    const status: ProposalImportStatus = 'imported';
    expect(status).toBe('imported');
  });

  it('ProposalImportDiagnostic is importable from the public barrel', () => {
    const diag: ProposalImportDiagnostic = {
      severity: 'error',
      code: 'proposal-import/missing-id',
      message: 'Missing proposal ID',
    };
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('proposal-import/missing-id');
  });

  it('ProposalImportResult is importable from the public barrel', () => {
    const result: ProposalImportResult = {
      imported: 3,
      skipped: 1,
      rejected: 0,
      statuses: [{ proposalId: 'p1', status: 'imported' }],
      diagnostics: [],
    };
    expect(result.imported).toBe(3);
    expect(result.statuses).toHaveLength(1);
  });

  // ── direct import coverage ──────────────────────────────────────────────

  it('ProposalState is importable from canonical direct path', () => {
    const state: ProposalState_Direct = 'accepted';
    expect(state).toBe('accepted');
  });

  it('ProposalExpiryDetail is importable from canonical direct path', () => {
    const detail: ProposalExpiryDetail_Direct = {
      reason: 'ttl-elapsed',
      baseVersion: 1,
      currentVersion: 2,
      createdAt: 100,
      expiredAt: 200,
      ttlMs: 5000,
    };
    expect(detail.reason).toBe('ttl-elapsed');
    expect(detail.ttlMs).toBe(5000);
  });

  it('TimelineProposal is importable from canonical direct path', () => {
    const proposal: TimelineProposal_Direct = {
      id: 'direct-prop',
      source: 'direct.ext',
      state: 'rejected',
      patch: { ops: [] },
      baseVersion: 0,
      previewable: false,
      createdAt: 0,
      updatedAt: 0,
    };
    expect(proposal.id).toBe('direct-prop');
    expect(proposal.state).toBe('rejected');
  });

  it('ProposalListener is importable from canonical direct path', () => {
    const listener: ProposalListener_Direct = () => {};
    expect(typeof listener).toBe('function');
  });

  it('ProposalRuntime is importable from canonical direct path', () => {
    const runtime: ProposalRuntime_Direct = {
      subscribe(_listener) { return { dispose() {} }; },
      create(_input) {
        return { id: '', source: '', state: 'pending', patch: { ops: [] }, baseVersion: 0, previewable: false, createdAt: 0, updatedAt: 0 };
      },
      preview(_proposalId) { return { diff: { entries: [] } }; },
      accept(_proposalId) { return { entries: [] }; },
      reject(_proposalId, _reason) {},
      get(_proposalId) { return undefined; },
      list(_state) { return []; },
      currentVersion: 0,
      expireStale(_maxAgeMs) { return []; },
    };
    expect(typeof runtime.create).toBe('function');
  });

  it('ProposalPanelState is importable from canonical direct path', () => {
    const state: ProposalPanelState_Direct = {
      proposals: [],
      selectedProposalId: 'p1',
      visible: true,
    };
    expect(state.selectedProposalId).toBe('p1');
  });

  it('ProposalPanelAction is importable from canonical direct path', () => {
    const reject: ProposalPanelAction_Direct = { type: 'reject', proposalId: 'p1', reason: 'stale' };
    expect(reject.type).toBe('reject');
    expect(reject.reason).toBe('stale');
  });

  it('ProposalEnvelope is importable from canonical direct path', () => {
    const envelope: ProposalEnvelope_Direct = {
      proposals: [],
      baseVersion: 5,
      mutationApplied: true,
    };
    expect(envelope.baseVersion).toBe(5);
  });

  it('ProposalImportStatus is importable from canonical direct path', () => {
    const status: ProposalImportStatus_Direct = 'skipped';
    expect(status).toBe('skipped');
  });

  it('ProposalImportDiagnostic is importable from canonical direct path', () => {
    const diag: ProposalImportDiagnostic_Direct = {
      severity: 'warning',
      code: 'test',
      message: 'test',
      proposalIndex: 0,
    };
    expect(diag.proposalIndex).toBe(0);
  });

  it('ProposalImportResult is importable from canonical direct path', () => {
    const result: ProposalImportResult_Direct = {
      imported: 0,
      skipped: 0,
      rejected: 1,
      statuses: [],
      diagnostics: [],
    };
    expect(result.rejected).toBe(1);
  });
});

// ── M3 TimelineOps ──────────────────────────────────────────────────────────

describe('M2b barrel-import smoke — TimelineOps', () => {
  it('TimelineOps is importable from the public barrel', () => {
    const ops: TimelineOps = {
      validate(_patch) {
        return { valid: true, diagnostics: [] };
      },
      preview(_patch) {
        return { fullyPreviewable: true, diff: { version: 0, entries: [], affectedObjectIds: [] }, diagnostics: [] };
      },
      apply(_patch) {
        return { version: 0, entries: [], affectedObjectIds: [] };
      },
      checkpoint(_label) { return 'ckpt-1'; },
      rollback(_checkpointId) { return null; },
      setAllTracksMuted(_muted) {
        return { version: 0, entries: [], affectedObjectIds: [] };
      },
    };
    expect(typeof ops.validate).toBe('function');
    expect(typeof ops.setAllTracksMuted).toBe('function');
  });

  // ── direct import coverage ──────────────────────────────────────────────

  it('TimelineOps is importable from canonical direct path', () => {
    const ops: TimelineOps_Direct = {
      validate(_patch) {
        return { valid: true, diagnostics: [] };
      },
      preview(_patch) {
        return { fullyPreviewable: true, diff: { version: 0, entries: [], affectedObjectIds: [] }, diagnostics: [] };
      },
      apply(_patch) {
        return { version: 0, entries: [], affectedObjectIds: [] };
      },
      checkpoint(_label) { return 'ckpt-1'; },
      rollback(_checkpointId) { return null; },
      setAllTracksMuted(_muted) {
        return { version: 0, entries: [], affectedObjectIds: [] };
      },
    };
    expect(typeof ops.validate).toBe('function');
    expect(typeof ops.apply).toBe('function');
  });
});

// ── M3 timeline source-map contracts ────────────────────────────────────────

describe('M2b barrel-import smoke — source maps', () => {
  it('SourceMapRuntime is importable from the public barrel', () => {
    const runtime: SourceMapRuntime = {
      create(_ext, _target, _gran, _uri, _sl, _sc, _el, _ec, _meta) {
        return {
          id: 'sme-1', source: _ext, targetId: _target,
          targetGranularity: _gran, sourceUri: _uri,
          sourceStartLine: _sl, sourceStartColumn: _sc,
          sourceEndLine: _el, sourceEndColumn: _ec,
          stale: false,
        };
      },
      get(_ext, _id) { return undefined; },
      getForTarget(_ext, _target) { return []; },
      getForSource(_ext, _uri) { return []; },
      markStale(_ext, _uri) { return []; },
      markStaleForTarget(_ext, _target) { return []; },
      delete(_ext, _id) { return false; },
      list(_ext) { return []; },
    };
    expect(typeof runtime.create).toBe('function');
    expect(typeof runtime.get).toBe('function');
  });

  it('SourceMapEntry is importable from the public barrel', () => {
    const entry: SourceMapEntry = {
      id: 'sme-1',
      source: 'com.test.ext',
      targetId: 'clip-1',
      targetGranularity: 'clip',
      sourceUri: 'file:///src/main.ts',
      sourceStartLine: 10,
      sourceStartColumn: 0,
      sourceEndLine: 15,
      sourceEndColumn: 20,
      stale: false,
    };
    expect(entry.id).toBe('sme-1');
    expect(entry.targetGranularity).toBe('clip');
    expect(entry.stale).toBe(false);
  });

  it('GeneratedObjectMeta is importable from the public barrel', () => {
    const meta: GeneratedObjectMeta = {
      extensionId: 'com.test.ext',
      contributionId: 'gen-1',
      provenance: { hash: 'abc123' },
      generatedAt: 1700000000000,
      sourceMapEntryId: 'sme-1',
    };
    expect(meta.extensionId).toBe('com.test.ext');
    expect(meta.sourceMapEntryId).toBe('sme-1');
  });

  // ── direct import coverage ──────────────────────────────────────────────

  it('SourceMapRuntime is importable from canonical direct path', () => {
    const runtime: SourceMapRuntime_Direct = {
      create(_ext, _target, _gran, _uri, _sl, _sc, _el, _ec, _meta) {
        return {
          id: 'direct-sme', source: _ext, targetId: _target,
          targetGranularity: _gran, sourceUri: _uri,
          sourceStartLine: _sl, sourceStartColumn: _sc,
          sourceEndLine: _el, sourceEndColumn: _ec,
          stale: false,
        };
      },
      get(_ext, _id) { return undefined; },
      getForTarget(_ext, _target) { return []; },
      getForSource(_ext, _uri) { return []; },
      markStale(_ext, _uri) { return []; },
      markStaleForTarget(_ext, _target) { return []; },
      delete(_ext, _id) { return false; },
      list(_ext) { return []; },
    };
    expect(typeof runtime.markStale).toBe('function');
  });

  it('SourceMapEntry is importable from canonical direct path', () => {
    const entry: SourceMapEntry_Direct = {
      id: 'direct-entry',
      source: 'direct.ext',
      targetId: 'track-1',
      targetGranularity: 'track',
      sourceUri: 'file:///src/gen.ts',
      sourceStartLine: 0,
      sourceStartColumn: 0,
      sourceEndLine: 10,
      sourceEndColumn: 5,
      stale: false,
    };
    expect(entry.targetGranularity).toBe('track');
    expect(entry.source).toBe('direct.ext');
  });

  it('GeneratedObjectMeta is importable from canonical direct path', () => {
    const meta: GeneratedObjectMeta_Direct = {
      extensionId: 'direct.ext',
      generatedAt: 0,
    };
    expect(meta.extensionId).toBe('direct.ext');
    expect(meta.generatedAt).toBe(0);
  });
});

// ===========================================================================
// M1b: CompositionGraph barrel-import smoke
// ===========================================================================

describe('M1b barrel-import smoke — CompositionGraph', () => {
  it('COMPOSITION_NODE_KINDS is importable from the barrel', () => {
    expect(COMPOSITION_NODE_KINDS).toEqual(['clip', 'timeline-postprocess', 'contribution']);
    expect(COMPOSITION_NODE_KINDS).toHaveLength(3);
  });

  it('COMPOSITION_EDGE_KINDS is importable from the barrel', () => {
    expect(COMPOSITION_EDGE_KINDS).toEqual(['consumes', 'animates', 'binds-live', 'requires']);
    expect(COMPOSITION_EDGE_KINDS).toHaveLength(4);
  });

  it('REFERENCE_STATES is importable from the barrel', () => {
    expect(REFERENCE_STATES).toHaveLength(10);
    expect(REFERENCE_STATES).toContain('resolved');
    expect(REFERENCE_STATES).toContain('missing');
    expect(REFERENCE_STATES).toContain('disabled');
    expect(REFERENCE_STATES).toContain('inactive-reserved');
    expect(REFERENCE_STATES).toContain('invalid-package');
    expect(REFERENCE_STATES).toContain('duplicate');
    expect(REFERENCE_STATES).toContain('settings-error');
    expect(REFERENCE_STATES).toContain('runtime-error');
    expect(REFERENCE_STATES).toContain('version-incompatible');
    expect(REFERENCE_STATES).toContain('unknown');
  });

  it('CompositionGraphNode is constructable from the barrel', () => {
    const node: CompositionGraphNode = { id: 'node-1', kind: 'clip' };
    expect(node.kind).toBe('clip');
  });

  it('CompositionGraphEdge is constructable from the barrel', () => {
    const edge: CompositionGraphEdge = {
      id: 'edge-1', kind: 'consumes', sourceNodeId: 'src', targetNodeId: 'tgt',
    };
    expect(edge.kind).toBe('consumes');
  });

  it('CompositionReferenceStateEntry is constructable from the barrel', () => {
    const entry: CompositionReferenceStateEntry = {
      refKey: 'shader:ext:contrib', state: 'resolved', nodeIds: ['n1'],
    };
    expect(entry.state).toBe('resolved');
  });

  it('CompositionGraphPreviewResult is constructable from the barrel', () => {
    const preview: CompositionGraphPreviewResult = {
      nodes: [], edges: [], referenceStates: [], diagnostics: [],
    };
    expect(preview.diagnostics).toEqual([]);
  });

  it('CompositionGraph is constructable from the barrel', () => {
    const graph: CompositionGraph = {
      nodes: [], edges: [], referenceStates: [], diagnostics: [],
    };
    expect(graph.nodes).toEqual([]);
  });

  it('canonical direct import yields the same constants', () => {
    expect(COMP_NODE_KINDS_Direct).toEqual(COMPOSITION_NODE_KINDS);
    expect(COMP_EDGE_KINDS_Direct).toEqual(COMPOSITION_EDGE_KINDS);
    expect(REF_STATES_Direct).toEqual(REFERENCE_STATES);
  });

  it('CompositionGraphNode is importable from canonical direct path', () => {
    const node: CompGraphNode_Direct = { id: 'direct-node', kind: 'timeline-postprocess' };
    expect(node.kind).toBe('timeline-postprocess');
  });

  it('CompositionGraphEdge is importable from canonical direct path', () => {
    const edge: CompGraphEdge_Direct = {
      id: 'direct-edge', kind: 'consumes', sourceNodeId: 's', targetNodeId: 't',
    };
    expect(edge.kind).toBe('consumes');
  });

  it('CompositionReferenceStateEntry is importable from canonical direct path', () => {
    const entry: CompRefStateEntry_Direct = { refKey: 'k', state: 'missing', nodeIds: [] };
    expect(entry.state).toBe('missing');
  });

  it('CompositionGraphPreviewResult is importable from canonical direct path', () => {
    const preview: CompGraphPreview_Direct = {
      nodes: [], edges: [], referenceStates: [], diagnostics: [],
    };
    expect(preview.nodes).toEqual([]);
  });

  it('CompositionGraph is importable from canonical direct path', () => {
    const graph: CompGraph_Direct = {
      nodes: [], edges: [], referenceStates: [], diagnostics: [],
    };
    expect(graph.edges).toEqual([]);
  });

  it('ReferenceState only accepts the 10 M1b states from the barrel', () => {
    const states: ReferenceState[] = [
      'resolved', 'missing', 'disabled', 'inactive-reserved',
      'invalid-package', 'duplicate', 'settings-error', 'runtime-error',
      'version-incompatible', 'unknown',
    ];
    expect(states).toHaveLength(10);
  });

  it('CompositionNodeKind only accepts the 3 M1b kinds', () => {
    const kinds: CompositionNodeKind[] = ['clip', 'timeline-postprocess', 'contribution'];
    expect(kinds).toHaveLength(3);
  });

  it('CompositionEdgeKind accepts the public edge-kind union', () => {
    const kinds: CompositionEdgeKind[] = ['consumes', 'animates', 'binds-live'];
    expect(kinds).toEqual(['consumes', 'animates', 'binds-live']);
  });
});

// ===========================================================================
// Cross-cutting: barrel and direct imports refer to identical runtime values
// ===========================================================================

describe('M2a barrel-import smoke — cross-cutting identity', () => {
  it('value exports (not type-exports) are identical regardless of import path', () => {
    // Value exports from ids
    expect(validateExtId_Direct).toBe(validateExtensionId);

    // Value exports from diagnostics
    expect(DIAG_SRC_EXT_Direct).toBe(DIAGNOSTIC_SOURCE_EXTENSION);
    expect(DEFAULT_DIAG_CAP_Direct).toBe(DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY);
    expect(createDiagColl_Direct).toBe(createDiagnosticCollection);

    // Value exports from manifest
    expect(KNOWN_CONTRIB_KINDS_SET_Direct).toBe(KNOWN_CONTRIBUTION_KINDS_SET);
    expect(ALL_VALID_PLACEMENTS_Direct).toBe(ALL_VALID_PLACEMENTS);

    // Value exports from context
    expect(createCreativeStubs_Direct).toBe(createCreativeContextStubs);
    expect(NotImplErr_Direct).toBe(ExtensionNotImplementedError);
    expect(CREATIVE_MEMBER_MILESTONE_Direct).toBe(CREATIVE_MEMBER_MILESTONE);
    expect(disposeExtCtxSvc_Direct).toBe(disposeExtensionContextServices);
    expect(CTX_DISPOSE_SYM_Direct).toBe(CONTEXT_DISPOSE_SYMBOL);

    // Value exports from lifecycle
    expect(defExt_Direct).toBe(defineExtension);
  });
});

// ===========================================================================
// M7a: Output-format route planning barrel-import smoke
// ===========================================================================

describe('M7a barrel-import smoke — Output-format route planning', () => {
  it('OutputFormatRef is importable from the barrel', () => {
    const ref: OutputFormatRef = {
      kind: 'outputFormat',
      extensionId: 'com.test.ext',
      contributionId: 'my-format',
    };
    expect(ref.kind).toBe('outputFormat');
  });

  it('ARTIFACT_MANIFEST_PROFILE_KINDS is importable from the barrel', () => {
    expect(ARTIFACT_MANIFEST_PROFILE_KINDS).toEqual(['video', 'audio', 'sidecar', 'preview', 'machine-path', 'executable-package']);
    expect(ARTIFACT_MANIFEST_PROFILE_KINDS).toHaveLength(6);
  });

  it('contributionRefKey is importable from the barrel', () => {
    const key = contributionRefKey({
      kind: 'outputFormat',
      extensionId: 'com.test.ext',
      contributionId: 'my-format',
    });
    expect(key).toBe('outputFormat:com.test.ext:my-format');
  });

  it('VideoArtifactManifestProfile is constructable from the barrel', () => {
    const p: VideoArtifactManifestProfile = {
      kind: 'video', schemaVersion: 1, mimeType: 'video/mp4',
      consumedMaterialRefs: [], inputHashes: [],
    };
    expect(p.kind).toBe('video');
  });

  it('AudioArtifactManifestProfile is constructable from the barrel', () => {
    const p: AudioArtifactManifestProfile = {
      kind: 'audio', schemaVersion: 1, mimeType: 'audio/mp3',
      consumedMaterialRefs: [], inputHashes: [],
    };
    expect(p.kind).toBe('audio');
  });

  it('SidecarArtifactManifestProfile is constructable from the barrel', () => {
    const p: SidecarArtifactManifestProfile = {
      kind: 'sidecar', schemaVersion: 1, mimeType: 'application/json',
      consumedMaterialRefs: [], inputHashes: [],
    };
    expect(p.kind).toBe('sidecar');
  });

  it('PreviewArtifactManifestProfile is constructable from the barrel', () => {
    const p: PreviewArtifactManifestProfile = {
      kind: 'preview', schemaVersion: 1, mimeType: 'image/png',
      consumedMaterialRefs: [], inputHashes: [],
    };
    expect(p.kind).toBe('preview');
  });

  it('ArtifactManifestProfile discriminated union works via barrel', () => {
    const profiles: ArtifactManifestProfile[] = [
      { kind: 'video', schemaVersion: 1, mimeType: 'video/mp4', consumedMaterialRefs: [], inputHashes: [] },
      { kind: 'audio', schemaVersion: 1, mimeType: 'audio/mp3', consumedMaterialRefs: [], inputHashes: [] },
      { kind: 'sidecar', schemaVersion: 1, mimeType: 'text/plain', consumedMaterialRefs: [], inputHashes: [] },
      { kind: 'preview', schemaVersion: 1, mimeType: 'image/png', consumedMaterialRefs: [], inputHashes: [] },
    ];
    expect(profiles.map(p => p.kind)).toEqual(['video', 'audio', 'sidecar', 'preview']);
  });
});
