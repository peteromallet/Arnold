/**
 * @reigh/editor-sdk — Public SDK entrypoint
 *
 * Stable public types and helpers for trusted local extensions.
 * This module must NOT import from editor internals (DataProvider,
 * raw timeline ops, editor runtime contexts, or internal mutation APIs).
 *
 * @publicContract
 */

import {
  createExtensionSettingsService,
  type CreateExtensionSettingsServiceOptions,
} from './extensionSettingsService';
import { runSettingsMigration, getManifestSettingsSchemaVersion } from './extensionSettingsMigration';
import type {
  TimelineReader,
  TimelineSnapshot,
  TimelineProposalInput,
} from '@/sdk/video/timeline/reader.ts';

import {
  VIDEO_FAMILY_LEGACY_MILESTONE_MAP,
  getVideoFamily,
  buildVideoFamilyReport,
} from '@/sdk/video/families/familyDefinitions';
import type { FamilyDefinition } from '@/sdk/core/families/maturity';
import type { FamilyConformanceReport } from '@/sdk/core/families/conformance';
import type { ExecutionMaturity } from '@/sdk/core/families/maturity';

// ---------------------------------------------------------------------------
// Re-exports from leaf modules
// ---------------------------------------------------------------------------

// Import for internal use within this file
import {
  type ExtensionId,
  type ContributionId,
  validateExtensionId,
  validateContributionId,
} from './ids';
import type { DisposeHandle } from './dispose';
import {
  type TargetContext,
  type TargetContextPayload,
  type CommandRunContext,
  type CommandHandler,
  type CommandRegistrationOptions,
} from './commands';
import {
  type ExtensionChromeService,
  type ChromeEvent,
  type ChromeEventPayload,
  type ChromeProgressPayload,
} from './chrome';
import {
  type ExtensionI18nService,
  type ExtensionDiagnosticsService,
  type CreativeContext,
  type ExtensionCommandService,
  type ExtensionContext,
  createCreativeContext,
  createCreativeContextStubs,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
} from './context';
import {
  type ExtensionActivateFn,
  type ReighExtension,
  type DefineExtensionOptions,
  defineExtension,
} from './lifecycle';
import type {
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
  ProcessRoundtripRequest,
  ProcessRoundtripAction,
  ProcessRoundtripResult,
  ProcessProgressEvent,
  ProcessLogSummary,
} from './capabilities';
import { getCapabilityRequirements } from './capabilities';

// M2b family module imports (used in ExtensionManifest union and re-exported)
import type { MetadataFacetContribution } from './video/families/metadataFacet';
import type { AssetDetailSectionContribution } from './video/families/assetDetailSections';
import type {
  OutputFormatContribution,
  CompileOnlyOutputFormatContribution,
  RenderDependentOutputFormatContribution,
  RenderDependentOutputDescriptor,
} from './video/families/outputFormats';
import type {
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
} from './video/families/effects';
import type {
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
} from './video/families/transitions';
import type {
  ClipTypeContribution,
  ClipRenderer,
  ClipInspector,
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
} from './video/families/clipTypeContributions';
import type {
  ShaderPassKind,
  ShaderColorSpace,
  ShaderFallbackBehavior,
  ShaderTextureSourceKind,
  ShaderTextureFilter,
  ShaderTextureWrap,
  ShaderInlineSource,
  ShaderModuleSource,
  ShaderSourceDescriptor,
  ShaderPassDescriptor,
  ShaderUniformType,
  ShaderUniformEnumOption,
  ShaderTextureRef,
  ShaderUniformDefaultValue,
  ShaderUniformDefinition,
  ShaderUniformSchema,
  ShaderTextureDefinition,
  ShaderTextureSchema,
  ShaderMaterializerDescriptor,
  ShaderContribution,
  ShaderRegistrationOptions,
  ShaderRegistrationService,
} from './video/families/shaders';
import type {
  AgentToolContribution,
  AgentToolRegistrationService,
  AgentToolHandler,
} from './video/families/agentTools';
import type { ProcessContribution, ProcessManifestEntry, ProcessSpawnConfig } from './video/families/processes';
import type { SearchProviderContribution } from './video/families/searchProviders';
import type { ParserContribution } from './video/families/parsers';
import type { CommandContribution } from './video/families/commands';
import type { KeybindingContribution } from './video/families/keybindings';
import type { ContextMenuItemContribution } from './video/families/contextMenuItems';

// Re-export publicly
export {
  type ExtensionId,
  type ContributionId,
  validateExtensionId,
  validateContributionId,
};

export type { DisposeHandle };

// ---------------------------------------------------------------------------
// Commands
export {
  type TargetContext,
  type TargetContextPayload,
  type CommandRunContext,
  type CommandHandler,
  type CommandRegistrationOptions,
} from './commands';

// ---------------------------------------------------------------------------
// Chrome
export {
  type ExtensionChromeService,
  type ChromeEvent,
  type ChromeToastPayload,
  type ChromeProgressPayload,
  type ChromeSavePayload,
  type ChromeRenderStatusPayload,
  type ChromeEventPayload,
} from './chrome';

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

// Import for internal use within this file
import {
  type DiagnosticSeverity,
  type DiagnosticSource,
  DIAGNOSTIC_SOURCE_EXTENSION,
  type ExtensionDiagnostic,
  type DiagnosticSourceRange,
  type Diagnostic,
  type DiagnosticCollection,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY,
  type CreateDiagnosticCollectionOptions,
  createDiagnosticCollection,
  type ExportDiagnostic,
} from './diagnostics';

// Re-export publicly
export {
  type DiagnosticSeverity,
  type DiagnosticSource,
  DIAGNOSTIC_SOURCE_EXTENSION,
  type ExtensionDiagnostic,
  type DiagnosticSourceRange,
  type Diagnostic,
  type DiagnosticCollection,
  DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY,
  type CreateDiagnosticCollectionOptions,
  createDiagnosticCollection,
  type ExportDiagnostic,
};

// ---------------------------------------------------------------------------
// Manifest
// ---------------------------------------------------------------------------

// Import for internal use within this file (validateManifest, etc.)
import {
  type ContributionKind,
  type VideoEditorSlotName,
  type ExtensionContribution,
  KNOWN_CONTRIBUTION_KINDS,
  KNOWN_CONTRIBUTION_KINDS_SET,
  KNOWN_SLOT_NAMES,
  KNOWN_SLOT_NAMES_SET,
  INSPECTOR_SECTION_PLACEMENTS,
  PANEL_PLACEMENTS,
  ASSET_DETAIL_SECTION_PLACEMENTS,
  ALL_VALID_PLACEMENTS,
  type ManifestValidationMode,
  type ManifestValidationResult,
} from './manifest';

// Re-export publicly
export {
  type ContributionKind,
  type VideoEditorSlotName,
  type ExtensionContribution,
  KNOWN_CONTRIBUTION_KINDS,
  KNOWN_CONTRIBUTION_KINDS_SET,
  KNOWN_SLOT_NAMES,
  KNOWN_SLOT_NAMES_SET,
  INSPECTOR_SECTION_PLACEMENTS,
  PANEL_PLACEMENTS,
  ASSET_DETAIL_SECTION_PLACEMENTS,
  ALL_VALID_PLACEMENTS,
  type ManifestValidationMode,
  type ManifestValidationResult,
};

// ---------------------------------------------------------------------------
// Packaging
// ---------------------------------------------------------------------------

// Import for internal use within this file (validateInstalledPackage, etc.)
import type {
  DependencyPosture,
  ExtensionDependency,
  IntegrityAlgorithm,
  IntegrityHash,
  MigrationHookKind,
  MigrationDeclaration,
  InstalledExtensionMetadata,
} from './packaging';

// Re-export publicly
export type {
  DependencyPosture,
  ExtensionDependency,
  IntegrityAlgorithm,
  IntegrityHash,
  MigrationHookKind,
  MigrationDeclaration,
  InstalledExtensionMetadata,
};

// ---------------------------------------------------------------------------
// M5: Renderability, blocker, material, and artifact contracts
// ---------------------------------------------------------------------------

export {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@/sdk/video/rendering/renderability.ts';

export {
  shaderMissingMaterializerBlockerMessage,
  describeShaderMaterializerRequirementScope,
} from '@/sdk/video/rendering/capabilities.ts';

export {
  EXTENSION_PROJECT_DATA_LIMITS,
  TIMELINE_DIFF_GRANULARITIES,
  TIMELINE_DIFF_KINDS,
  TIMELINE_PATCH_ALL_OP_FAMILIES,
  TIMELINE_PATCH_OP_FAMILIES,
  TIMELINE_PATCH_RESERVED_OP_FAMILIES,
} from '@/sdk/video/timeline/patch.ts';

export {
  TimelineVersionConflictError,
  isTimelineVersionConflictError,
} from '@/sdk/video/timeline/errors.ts';

export {
  BUILTIN_CLIP_TYPES,
} from '@/sdk/video/timeline/clipTypes.ts';

export type {
  BuiltinClipType,
} from '@/sdk/video/timeline/clipTypes.ts';

export {
  getConfigSignature,
  getStableConfigSignature,
} from '@/sdk/video/timeline/configSignature.ts';

export type {
  StableTimelineAssetRegistryInput,
  StableTimelineConfigSignatureInput,
  TimelineConfigSignatureInput,
} from '@/sdk/video/timeline/configSignature.ts';

export type {
  CapabilityFinding,
  CapabilityFindingSeverity,
  ContributionRenderability,
  DeterminismStatus,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderCapabilityStatus,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';

export type {
  ArtifactBoundary,
  BakeContract,
  RenderArtifact,
  RenderArtifactManifest,
  RenderArtifactSidecarDescriptor,
  RenderArtifactSidecarKind,
  RenderLocatorKind,
  RenderMaterial,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts.ts';

export type {
  ShaderMaterializerRequirementScope,
} from '@/sdk/video/rendering/capabilities.ts';

export type {
  ProjectDataLimitCode,
  ProjectDataLimitDetail,
  TimelineDiff,
  TimelineDiffEntry,
  TimelineDiffGranularity,
  TimelineDiffKind,
  TimelinePatch,
  TimelinePatchAnyOpFamily,
  TimelinePatchDiagnostic,
  TimelinePatchOpFamily,
  TimelinePatchOperation,
  TimelinePatchReservedOpFamily,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
} from '@/sdk/video/timeline/patch.ts';

export type {
  TimelineEffectSummary,
  TimelineTransitionSummary,
  TimelineLiveBindingSummary,
  TimelineMaterialRefSummary,
  TimelineRenderPassSummary,
  TimelineSourceRefSummary,
  TimelineRenderGroupSummary,
  TimelineOutputMetadata,
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineTrackSummary,
  TimelineShaderSummary,
  TimelineReader,
  TimelineProposalInput,
} from '@/sdk/video/timeline/reader.ts';

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
export {
  type ExtensionActivateFn,
  type ReighExtension,
  type DefineExtensionOptions,
  defineExtension,
} from './lifecycle';

// ---------------------------------------------------------------------------
// Capabilities, sampling, and process roundtrip
// ---------------------------------------------------------------------------
export type {
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
  ProcessRoundtripRequest,
  ProcessRoundtripAction,
  ProcessRoundtripResult,
  ProcessProgressEvent,
  ProcessLogSummary,
} from './capabilities';
export { getCapabilityRequirements } from './capabilities';

// ---------------------------------------------------------------------------
// M4: Commands, Keybindings, Context Menus — target and handler contracts
// ---------------------------------------------------------------------------
// M6: Metadata facet / asset detail section contributions
// ---------------------------------------------------------------------------

// Re-exported from their video family modules
export type { MetadataFacetContribution } from './video/families/metadataFacet';
export type { AssetDetailSectionContribution } from './video/families/assetDetailSections';

// ---------------------------------------------------------------------------
// M4: Command / keybinding / context-menu contributions
// ---------------------------------------------------------------------------

// CommandContribution is now defined in src/sdk/video/families/commands.ts
// and re-exported below. (M2b extraction)
export type { CommandContribution } from './video/families/commands';

// KeybindingContribution is now defined in src/sdk/video/families/keybindings.ts
// and re-exported below. (M2b extraction)
export type { KeybindingContribution } from './video/families/keybindings';

// ContextMenuItemContribution is now defined in src/sdk/video/families/contextMenuItems.ts
// and re-exported below. (M2b extraction)
export type { ContextMenuItemContribution } from './video/families/contextMenuItems';

// ParserContribution is now defined in src/sdk/video/families/parsers.ts
// and re-exported below. (M2b extraction)

// OutputFormatContribution, CompileOnlyOutputFormatContribution,
// RenderDependentOutputFormatContribution, and RenderDependentOutputDescriptor
// are now defined in src/sdk/video/families/outputFormats.ts and re-exported below.
// (M2b extraction)
export type {
  OutputFormatContribution,
  CompileOnlyOutputFormatContribution,
  RenderDependentOutputFormatContribution,
  RenderDependentOutputDescriptor,
} from './video/families/outputFormats';

// SearchProviderContribution is now defined in
// src/sdk/video/families/searchProviders.ts and re-exported below.
// (M2b extraction)
export type { SearchProviderContribution } from './video/families/searchProviders';

// ParserContribution is now defined in src/sdk/video/families/parsers.ts
// and re-exported below. (M2b extraction)
export type { ParserContribution } from './video/families/parsers';

// ---------------------------------------------------------------------------
// M7: Trusted component effect contributions
// ---------------------------------------------------------------------------

// EffectContribution, EffectComponent, EffectParameterDefinition,
// EffectParameterSchema, EffectRegistrationOptions, and EffectRegistrationService
// are now defined in src/sdk/video/families/effects.ts and re-exported below.
// (M2b extraction)
export type {
  EffectContribution,
  EffectComponent,
  EffectParameterDefinition,
  EffectParameterSchema,
  EffectRegistrationOptions,
  EffectRegistrationService,
} from './video/families/effects';

// ---------------------------------------------------------------------------
// M8: Trusted component transition contributions
// ---------------------------------------------------------------------------

// TransitionContribution, TransitionRenderer, TransitionParameterDefinition,
// TransitionParameterSchema, TransitionRegistrationOptions, and TransitionRegistrationService
// are now defined in src/sdk/video/families/transitions.ts and re-exported below.
// (M2b extraction)
export type {
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
} from './video/families/transitions';

// ---------------------------------------------------------------------------
// M9: Clip type contributions — renderers, inspectors, keyframes, automation
// ---------------------------------------------------------------------------

// ClipTypeContribution, ClipRenderer, ClipInspector, ClipParameterDefinition,
// ClipParameterSchema, ClipTypeRegistrationOptions, and ClipTypeRegistrationService
// are now defined in src/sdk/video/families/clipTypeContributions.ts and re-exported below.
// (M2b extraction)
export type {
  ClipTypeContribution,
  ClipRenderer,
  ClipInspector,
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
} from './video/families/clipTypeContributions';

// ---------------------------------------------------------------------------
// M13: Shader/WebGL contributions
// ---------------------------------------------------------------------------

// ShaderPassKind, ShaderColorSpace, ShaderFallbackBehavior,
// ShaderTextureSourceKind, ShaderTextureFilter, ShaderTextureWrap,
// ShaderInlineSource, ShaderModuleSource, ShaderSourceDescriptor,
// ShaderPassDescriptor, ShaderUniformType, ShaderUniformEnumOption,
// ShaderTextureRef, ShaderUniformDefaultValue, ShaderUniformDefinition,
// ShaderUniformSchema, ShaderTextureDefinition, ShaderTextureSchema,
// ShaderMaterializerDescriptor, ShaderContribution,
// ShaderRegistrationOptions, and ShaderRegistrationService
// are now defined in src/sdk/video/families/shaders.ts and re-exported below.
// (M2b extraction)
export type {
  ShaderPassKind,
  ShaderColorSpace,
  ShaderFallbackBehavior,
  ShaderTextureSourceKind,
  ShaderTextureFilter,
  ShaderTextureWrap,
  ShaderInlineSource,
  ShaderModuleSource,
  ShaderSourceDescriptor,
  ShaderPassDescriptor,
  ShaderUniformType,
  ShaderUniformEnumOption,
  ShaderTextureRef,
  ShaderUniformDefaultValue,
  ShaderUniformDefinition,
  ShaderUniformSchema,
  ShaderTextureDefinition,
  ShaderTextureSchema,
  ShaderMaterializerDescriptor,
  ShaderContribution,
  ShaderRegistrationOptions,
  ShaderRegistrationService,
} from './video/families/shaders';

// KeyframeInterpolation, Keyframe, InterpolatedParam,
// AutomationClipTarget, and AutomationClipParams are now defined in
// src/sdk/video/families/automation.ts and re-exported below.
// (M2b extraction)
export type {
  KeyframeInterpolation,
  Keyframe,
  InterpolatedParam,
  AutomationClipTarget,
  AutomationClipParams,
} from './video/families/automation';

// AgentToolContribution, AgentToolInputSchema, AgentToolInputProperty,
// ToolResultFamily, ToolResult, ToolMutationProposalResult,
// ToolGenerationSessionResult, ToolMaterialArtifactResult,
// ToolEnrichmentSearchResult, ToolExportResult, ToolProcessResult,
// ToolUISummaryResult, ToolSourceRef, ToolArtifactRef,
// ToolSearchResultMatch, ToolResultDiagnostic,
// AgentToolInvocationRequest, AgentToolRequestContext,
// AgentToolExportContext, GenerationSession,
// AgentToolRegistrationService, and AgentToolHandler
// are now defined in src/sdk/video/families/agentTools.ts and re-exported below.
// (M2b extraction)

export type {
  AgentToolContribution,
  AgentToolInputSchema,
  AgentToolInputProperty,
  ToolResultFamily,
  ToolResult,
  ToolMutationProposalResult,
  ToolGenerationSessionResult,
  ToolMaterialArtifactResult,
  ToolEnrichmentSearchResult,
  ToolExportResult,
  ToolProcessResult,
  ToolUISummaryResult,
  ToolSourceRef,
  ToolArtifactRef,
  ToolSearchResultMatch,
  ToolResultDiagnostic,
  AgentToolInvocationRequest,
  AgentToolRequestContext,
  AgentToolExportContext,
  GenerationSession,
  AgentToolRegistrationService,
  AgentToolHandler,
} from './video/families/agentTools';

// ---------------------------------------------------------------------------
// Process family contracts extracted to src/sdk/video/families/processes.ts
// (M2b extraction)
// ---------------------------------------------------------------------------
export type {
  ProcessSpawnConfig,
  ProcessManifestEntry,
  ProcessEnvFieldSpec,
  ProcessOperationSpec,
  ProcessSpec,
  ProcessContribution,
  ProcessLifecycleState,
  ProcessStatusBase,
  ProcessStatus,
} from './video/families/processes';

// M11: Live Data Bridge — re-exported from the live data infrastructure module
// ---------------------------------------------------------------------------
export type {
  LiveSourceKind,
  LiveSourceStatus,
  LiveSourceDiagnostic,
  LiveSource,
  LiveChannelKind,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSampleFormat,
  LiveSampleFrame,
  LiveSample,
  LivePermissionState,
  LiveSourcePermission,
  LiveRecordingMode,
  LiveRecordingState,
  LiveLearnMode,
  LiveBakeTargetKind,
  LiveBakeTarget,
  LiveBakeSelection,
  LiveBakeResult,
  SteeringDecisionKind,
  SteeringParameterHotness,
  SteeringPriorSamplePolicy,
  SteeringProvenance,
  SteeringParameterChange,
  SteeringLineage,
  SteeringDecision,
  GenerationSessionLiveDelivery,
  BindingResolutionStatus,
  LiveBinding,
  LiveBindingResolution,
  LiveBindingMetadata,
  LiveSessionsService,
} from './video/liveData';

// ---------------------------------------------------------------------------
// Permission metadata (descriptive until sandboxing exists)
// ---------------------------------------------------------------------------

export interface ExtensionPermissionDeclaration {
  /** Human-readable reason the permission is requested. */
  reason: string;
  /** Declared posture: what the extension states it accesses. */
  posture?: {
    network?: boolean;
    filesystem?: boolean;
    env?: boolean;
    processes?: boolean;
  };
}

// ---------------------------------------------------------------------------
// M14: Packaging, integrity, settings-schema, and dependency contracts
// ---------------------------------------------------------------------------

// Import for internal use within this file
import type { ExtensionSettingsSchema } from './settings';

// Re-export publicly
export type { ExtensionSettingsSchema };

/** A full installed extension package: manifest + bundle + tracked metadata. */
export interface InstalledExtensionPackage {
  metadata: InstalledExtensionMetadata;
  manifest: ExtensionManifest;
  /** Raw trusted bundle source (bundle.mjs content). */
  bundleContent: string;
}

/**
 * Validate an extension manifest against the expected contract.
 *
 * In 'dev' mode, missing installed-only fields emit warnings.
 * In 'installed' mode, missing required installed metadata fields
 * (integrity, publisher, license) emit blocking errors.
 *
 * Contribution ID uniqueness, ID format, version format, and
 * dependency posture are validated in both modes.
 */
export function validateManifest(
  manifest: ExtensionManifest,
  _mode?: ManifestValidationMode,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];
  const mode: ManifestValidationMode = _mode ?? 'dev';

  const extId = manifest.id as string;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  const isValidSemver = (v: string): boolean => /^\d+\.\d+\.\d+/.test(v);

  /** Basic semver-range check: accepts npm-style range strings. */
  const isValidSemverRange = (range: string): boolean => {
    // Accept common patterns: ^x.y.z, ~x.y.z, >=x.y.z, x.y.z - y.z.w, x, x.y
    return /^(\*|[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)(\s+(?:-?\s*)?[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*(\s+\|\|\s+[\^~><=]*(?:\d+|\*|x)(?:\.(?:\d+|\*|x))?(?:\.(?:\d+|\*|x))?)*\s*$/.test(range.trim());
  };

  const pushErr = (code: string, message: string, contributionId?: string): void => {
    errors.push({
      severity: 'error',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  const pushWarn = (code: string, message: string, contributionId?: string): void => {
    warnings.push({
      severity: 'warning',
      code,
      message,
      extensionId: extId,
      ...(contributionId ? { contributionId } : {}),
    });
  };

  // -----------------------------------------------------------------------
  // ID validation
  // -----------------------------------------------------------------------
  const idErrors = validateExtensionId(extId);
  for (const msg of idErrors) {
    pushErr('manifest/invalid-id', msg);
  }

  // -----------------------------------------------------------------------
  // Version validation
  // -----------------------------------------------------------------------
  if (!manifest.version || typeof manifest.version !== 'string') {
    pushErr('manifest/missing-version', 'Manifest must include a semver version string');
  } else if (!isValidSemver(manifest.version)) {
    pushErr('manifest/invalid-version', `Version "${manifest.version}" does not match semver format`);
  }

  // -----------------------------------------------------------------------
  // Label validation
  // -----------------------------------------------------------------------
  if (!manifest.label || typeof manifest.label !== 'string' || manifest.label.trim().length === 0) {
    pushErr('manifest/missing-label', 'Manifest must include a non-empty label');
  }

  // -----------------------------------------------------------------------
  // API version validation
  // -----------------------------------------------------------------------
  if (manifest.apiVersion !== undefined) {
    if (typeof manifest.apiVersion !== 'number' || !Number.isInteger(manifest.apiVersion) || manifest.apiVersion < 1) {
      pushErr('manifest/invalid-api-version', `apiVersion must be a positive integer, got ${manifest.apiVersion}`);
    }
  }

  // -----------------------------------------------------------------------
  // Contribution validation (ID uniqueness, kind, placement rules)
  // -----------------------------------------------------------------------
  if (manifest.contributions && manifest.contributions.length > 0) {
    const seen = new Set<string>();
    for (const contribution of manifest.contributions) {
      const cId = (contribution as any).id as string;
      const cErrors = validateContributionId(cId);
      for (const msg of cErrors) {
        pushErr('manifest/invalid-contribution-id', `Contribution "${cId}": ${msg}`, cId);
      }
      if (seen.has(cId)) {
        pushErr('manifest/duplicate-contribution-id', `Duplicate contribution ID "${cId}"`, cId);
      }
      seen.add(cId);

      // ---- Contribution kind validation ----
      const cKind = (contribution as any).kind as string | undefined;
      if (!cKind || typeof cKind !== 'string') {
        pushErr('manifest/missing-contribution-kind', `Contribution "${cId}" is missing a kind`, cId);
        continue; // cannot validate kind-specific rules without a kind
      }
      if (!KNOWN_CONTRIBUTION_KINDS_SET.has(cKind)) {
        pushErr(
          'manifest/unknown-contribution-kind',
          `Contribution "${cId}" has unknown kind "${cKind}"; must be one of: ${KNOWN_CONTRIBUTION_KINDS.join(', ')}`,
          cId,
        );
        continue; // unknown kind — skip kind-specific placement rules
      }

      // ---- Kind-specific placement rules ----

      // Slot: must not specify placement
      if (cKind === 'slot') {
        const cPlacement = (contribution as any).placement;
        if (cPlacement !== undefined && cPlacement !== null) {
          pushErr(
            'manifest/slot-no-placement',
            `Slot contribution "${cId}" must not specify placement`,
            cId,
          );
        }
        // Validate slot name if present
        const cSlot = (contribution as any).slot;
        if (cSlot !== undefined && cSlot !== null && !KNOWN_SLOT_NAMES_SET.has(cSlot)) {
          pushErr(
            'manifest/unknown-slot-name',
            `Slot contribution "${cId}" has unknown slot name "${cSlot}"; must be one of: ${KNOWN_SLOT_NAMES.join(', ')}`,
            cId,
          );
        }
      }

      // Panel: placement must be 'asset-panel' when specified
      if (cKind === 'panel') {
        const cPlacement = (contribution as any).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!PANEL_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-panel-placement',
              `Panel contribution "${cId}" placement must be "asset-panel", got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // InspectorSection: validate placement when present; host applies defaults
      if (cKind === 'inspectorSection') {
        const cPlacement = (contribution as any).placement as string | undefined;
        if (cPlacement !== undefined && cPlacement !== null) {
          if (!INSPECTOR_SECTION_PLACEMENTS.includes(cPlacement)) {
            pushErr(
              'manifest/invalid-inspector-placement',
              `InspectorSection contribution "${cId}" placement must be one of: ${INSPECTOR_SECTION_PLACEMENTS.join(', ')}, got "${cPlacement}"`,
              cId,
            );
          }
        }
      }

      // AssetDetailSection: title and placement are required
      if (cKind === 'assetDetailSection') {
        const adsContribution = contribution as { id: string; title?: unknown; placement?: unknown };
        if (!adsContribution.title || typeof adsContribution.title !== 'string' || adsContribution.title.trim().length === 0) {
          pushErr(
            'manifest/missing-asset-detail-title',
            `AssetDetailSection contribution "${cId}" must include a non-empty title`,
            cId,
          );
        }
        if (!adsContribution.placement || typeof adsContribution.placement !== 'string' || !ASSET_DETAIL_SECTION_PLACEMENTS.includes(adsContribution.placement)) {
          pushErr(
            'manifest/invalid-asset-detail-placement',
            `AssetDetailSection contribution "${cId}" must specify placement as one of: ${ASSET_DETAIL_SECTION_PLACEMENTS.join(', ')}, got "${String(adsContribution.placement ?? 'undefined')}"`,
            cId,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Dependency validation
  // -----------------------------------------------------------------------
  if (manifest.dependsOn && manifest.dependsOn.length > 0) {
    for (const dep of manifest.dependsOn) {
      // Dependency ID validation
      const depIdErrors = validateExtensionId(dep.extensionId);
      for (const msg of depIdErrors) {
        pushErr('manifest/invalid-dependency-id', `Dependency "${dep.extensionId}": ${msg}`);
      }

      // Self-dependency check
      if (dep.extensionId === extId) {
        pushErr('manifest/self-dependency', `Extension "${extId}" declares a dependency on itself`);
      }

      // Posture validation
      if (dep.posture !== undefined && dep.posture !== 'required' && dep.posture !== 'optional') {
        pushErr(
          'manifest/invalid-dependency-posture',
          `Dependency "${dep.extensionId}" has invalid posture "${dep.posture}"; must be "required" or "optional"`,
        );
      }

      // optional vs posture consistency
      if (dep.optional === true && dep.posture === 'required') {
        pushWarn(
          'manifest/dependency-posture-mismatch',
          `Dependency "${dep.extensionId}" is marked optional=true but posture is "required"; posture takes precedence`,
        );
      }

      // Version range validation
      if (dep.versionRange !== undefined && typeof dep.versionRange === 'string' && dep.versionRange.length > 0) {
        if (!isValidSemverRange(dep.versionRange)) {
          pushWarn(
            'manifest/invalid-dependency-version-range',
            `Dependency "${dep.extensionId}" has an unrecognised version range "${dep.versionRange}"`,
          );
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Settings schema validation
  // -----------------------------------------------------------------------
  if (manifest.settingsSchema) {
    const version = (manifest.settingsSchema as any).version;
    if (typeof version !== 'number' || !Number.isInteger(version) || version < 0) {
      pushErr(
        'manifest/invalid-settings-schema-version',
        `settingsSchema.version must be a non-negative integer, got ${version}`,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Migration declarations validation
  // -----------------------------------------------------------------------
  const VALID_MIGRATION_KINDS: ReadonlySet<string> = new Set(['settings', 'contribution', 'manifest']);
  if (manifest.migrations && manifest.migrations.length > 0) {
    for (const migration of manifest.migrations) {
      // Legacy shape detection (plain object without 'kind')
      if (typeof migration !== 'object' || migration === null || !('kind' in migration)) {
        // In dev mode these are warnings; in installed mode typed declarations are required
        if (mode === 'installed') {
          pushErr(
            'manifest/legacy-migration-shape',
            'Migration entry lacks "kind"; typed MigrationDeclaration is required for installed extensions',
          );
        } else {
          pushWarn(
            'manifest/legacy-migration-shape',
            'Migration entry is a plain object without "kind"; typed MigrationDeclaration is preferred',
          );
        }
        break; // one diagnostic per manifest
      }

      const m = migration as Record<string, unknown>;

      // Validate kind
      if (!VALID_MIGRATION_KINDS.has(m.kind as string)) {
        pushErr(
          'manifest/invalid-migration-kind',
          `Migration kind "${m.kind}" is not valid; must be one of: settings, contribution, manifest`,
        );
      }

      // Validate fromVersion
      if (typeof m.fromVersion !== 'string' || !isValidSemver(m.fromVersion)) {
        pushErr(
          'manifest/invalid-migration-from-version',
          `Migration fromVersion "${m.fromVersion}" must be a valid semver`,
        );
      }

      // Validate toVersion
      if (typeof m.toVersion !== 'string' || !isValidSemver(m.toVersion)) {
        pushErr(
          'manifest/invalid-migration-to-version',
          `Migration toVersion "${m.toVersion}" must be a valid semver`,
        );
      }
    }
  }

  // -----------------------------------------------------------------------
  // Mode-specific checks: installed vs dev
  // -----------------------------------------------------------------------
  if (mode === 'installed') {
    // ---- Installed-mode required identity fields ----

    // Publisher is required for installed extensions
    if (!manifest.publisher || typeof manifest.publisher !== 'string' || manifest.publisher.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-publisher',
        'Installed extensions must declare a publisher',
      );
    }

    // License is required for installed extensions
    if (!manifest.license || typeof manifest.license !== 'string' || manifest.license.trim().length === 0) {
      pushErr(
        'manifest/installed-missing-license',
        'Installed extensions must declare an SPDX license identifier',
      );
    }

    // Settings schema is recommended for installed extensions
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/installed-missing-settings-schema',
        'Installed extensions should declare a settingsSchema for migration tracking',
      );
    }

    // Integrity is expected to be validated externally (on InstalledExtensionMetadata),
    // but if integrity is passed as a top-level field on manifest we validate the shape.
    const integrity = (manifest as any).integrity as IntegrityHash | undefined;
    if (integrity) {
      if (!integrity.algorithm || integrity.algorithm !== 'sha256') {
        pushErr(
          'manifest/installed-invalid-integrity-algorithm',
          `Integrity algorithm "${integrity.algorithm}" is not supported; only "sha256" is allowed`,
        );
      }
      if (!integrity.value || typeof integrity.value !== 'string' || integrity.value.trim().length === 0) {
        pushErr(
          'manifest/installed-missing-integrity-value',
          'Integrity hash value is required',
        );
      }
    }
  } else {
    // ---- Dev mode: compatibility warnings for legacy (M1/local) manifests ----

    // Warn about missing M14-required fields so extension authors see what will be
    // required for installed-pack compatibility.
    if (!manifest.publisher) {
      pushWarn(
        'manifest/dev-missing-publisher',
        'Publisher is not declared; installed extensions require a publisher',
      );
    }
    if (!manifest.license) {
      pushWarn(
        'manifest/dev-missing-license',
        'License is not declared; installed extensions require an SPDX license identifier',
      );
    }
    if (!manifest.settingsSchema) {
      pushWarn(
        'manifest/dev-missing-settings-schema',
        'settingsSchema is not declared; installed extensions should declare one for migration tracking',
      );
    }
  }

  // -----------------------------------------------------------------------
  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}

// ---------------------------------------------------------------------------
// Installed package validation
// ---------------------------------------------------------------------------

/**
 * Validate a full installed extension package.
 *
 * Checks package structure, metadata/manifest cross-references,
 * integrity hash presence, and delegates manifest-level validation
 * to {@link validateManifest} in 'installed' mode.
 */
export function validateInstalledPackage(
  pack: InstalledExtensionPackage,
): ManifestValidationResult {
  const errors: ExtensionDiagnostic[] = [];
  const warnings: ExtensionDiagnostic[] = [];

  const extId = pack.metadata?.extensionId as string ?? '(unknown)';

  const pushErr = (code: string, message: string): void => {
    errors.push({ severity: 'error', code, message, extensionId: extId });
  };

  const pushWarn = (code: string, message: string): void => {
    warnings.push({ severity: 'warning', code, message, extensionId: extId });
  };

  // Structural checks
  if (!pack.metadata) {
    pushErr('package/missing-metadata', 'Installed package must include metadata');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (!pack.manifest) {
    pushErr('package/missing-manifest', 'Installed package must include a manifest');
    return { valid: false, errors: Object.freeze([...errors]), warnings: Object.freeze([...warnings]) };
  }

  if (typeof pack.bundleContent !== 'string' || pack.bundleContent.trim().length === 0) {
    pushErr('package/missing-bundle', 'Installed package must include non-empty bundleContent');
  }

  // Cross-reference: metadata.extensionId === manifest.id
  if (pack.metadata.extensionId !== pack.manifest.id) {
    pushErr(
      'package/id-mismatch',
      `Metadata extensionId "${pack.metadata.extensionId}" does not match manifest.id "${pack.manifest.id}"`,
    );
  }

  // Cross-reference: metadata.version === manifest.version
  if (pack.metadata.version !== pack.manifest.version) {
    pushErr(
      'package/version-mismatch',
      `Metadata version "${pack.metadata.version}" does not match manifest.version "${pack.manifest.version}"`,
    );
  }

  // Integrity validation
  if (!pack.metadata.integrity) {
    pushErr('package/missing-integrity', 'Installed package metadata must include integrity hash');
  } else {
    if (!pack.metadata.integrity.algorithm || pack.metadata.integrity.algorithm !== 'sha256') {
      pushErr(
        'package/invalid-integrity-algorithm',
        `Integrity algorithm "${pack.metadata.integrity.algorithm}" is not supported; only "sha256" is allowed`,
      );
    }
    if (!pack.metadata.integrity.value || typeof pack.metadata.integrity.value !== 'string' || pack.metadata.integrity.value.trim().length === 0) {
      pushErr('package/missing-integrity-value', 'Integrity hash value is required');
    }
  }

  // Enabled must be boolean
  if (typeof pack.metadata.enabled !== 'boolean') {
    pushErr('package/invalid-enabled', 'Metadata enabled must be a boolean');
  }

  // Delegate to manifest validation in installed mode
  const manifestResult = validateManifest(pack.manifest, 'installed');
  for (const err of manifestResult.errors) {
    errors.push(err);
  }
  for (const warn of manifestResult.warnings) {
    warnings.push(warn);
  }

  return {
    valid: errors.length === 0,
    errors: Object.freeze([...errors]),
    warnings: Object.freeze([...warnings]),
  };
}


// ---------------------------------------------------------------------------
// Extension manifest
// ---------------------------------------------------------------------------
// NOTE: ExtensionManifest remains inline here (not yet in manifest.ts).
// CommandContribution, KeybindingContribution, and ContextMenuItemContribution
// were extracted to canonical family modules in M2b (T16). ExtensionManifest
// can move to manifest.ts with direct imports once all remaining inline
// contribution types are extracted.

export interface ExtensionManifest {
  id: ExtensionId;
  /** Semver string, e.g. "1.0.0". */
  version: string;
  label: string;
  description?: string;
  /** API version this extension targets (currently 1). */
  apiVersion?: number;
  /** Contribution declarations. */
  contributions?: readonly (
    | ExtensionContribution
    | CommandContribution
    | KeybindingContribution
    | ContextMenuItemContribution
    // M6: parser, output format, search provider, metadata facet, asset detail section
    | ParserContribution
    | OutputFormatContribution
    | SearchProviderContribution
    | MetadataFacetContribution
    | AssetDetailSectionContribution
    // M12: trusted local processes
    | ProcessContribution
    // M7: trusted component effects
    | EffectContribution
    // M8: trusted component transitions
    | TransitionContribution
    // M9: contributed clip types
    | ClipTypeContribution
    // M13: shader/WebGL contributions
    | ShaderContribution
    // M10: agent tool contributions
    | AgentToolContribution
  )[];
  /** Descriptive permission metadata. */
  permissions?: readonly ExtensionPermissionDeclaration[];
  /** Process declarations. */
  processes?: readonly ProcessManifestEntry[];
  /** Typed migration hooks (preferred); legacy Record<string, unknown>[] accepted. */
  migrations?: readonly (MigrationDeclaration | Record<string, unknown>)[];
  /** Human-readable comments. */
  comments?: string;
  /** Typed dependency declarations. */
  dependsOn?: readonly ExtensionDependency[];
  /** Renderability descriptors. */
  renderability?: Record<string, unknown>;
  /** Extension-scoped settings defaults applied when no stored value exists. */
  settingsDefaults?: Record<string, unknown>;
  /** Settings schema with version for migration tracking. */
  settingsSchema?: ExtensionSettingsSchema;
  /** Bundled i18n messages keyed by locale-neutral key. */
  messages?: Record<string, string>;
  /** Publisher identity (required for installed extensions). */
  publisher?: string;
  /** SPDX license identifier (recommended for installed extensions). */
  license?: string;
  /** Icon URL or data URI. */
  icon?: string;
}

// ---------------------------------------------------------------------------
// Services
// ---------------------------------------------------------------------------

// Import for internal use within this file
import type { ExtensionSettingsService } from './settings';

// Re-export publicly
export type { ExtensionSettingsService };

// Re-export the injectable settings service factory and persistence callbacks.
export { createExtensionSettingsService, getSettingsPrefix } from './extensionSettingsService';
export { runSettingsMigration, getManifestSettingsSchemaVersion, findSettingsMigrationDeclarations } from './extensionSettingsMigration';
export type {
  ExtensionSettingsServiceFactoryResult,
  CreateExtensionSettingsServiceOptions,
  SettingsMigrationConfig,
  SettingsPersistenceError,
  SettingsPersistenceOperation,
  SettingsPersistenceSuccess,
} from './extensionSettingsService';
export type { SettingsMigrationHandler, SettingsMigrationResult, RunSettingsMigrationOptions } from './extensionSettingsMigration';

// SDK-owned state repository contracts (used by settings services)
export type {
  SettingsSnapshot,
  LifecycleEvent,
  StateRepository,
} from './contracts';
export { createLifecycleEvent } from './contracts';

// ---------------------------------------------------------------------------
// Re-exports from context module
// ---------------------------------------------------------------------------

export {
  type ExtensionI18nService,
  type ExtensionDiagnosticsService,
  type CreativeContext,
  type ExtensionCommandService,
  type ExtensionContext,
  createCreativeContext,
  createCreativeContextStubs,
  disposeExtensionContextServices,
  CONTEXT_DISPOSE_SYMBOL,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
} from './context';

// EffectComponent, EffectParameterDefinition, EffectParameterSchema,
// EffectRegistrationOptions, and EffectRegistrationService are now defined in
// src/sdk/video/families/effects.ts and re-exported above. (M2b extraction)
//
// TransitionRenderer, TransitionParameterDefinition, TransitionParameterSchema,
// TransitionRegistrationOptions, and TransitionRegistrationService are now defined in
// src/sdk/video/families/transitions.ts and re-exported above. (M2b extraction)

// ---------------------------------------------------------------------------
// Editor shell root registry (module-level, set by host shell on mount)
// ---------------------------------------------------------------------------

/**
 * The currently-mounted editor shell root element, if any.
 * Set by the host shell component via {@link setEditorShellRoot} and
 * consumed by the chrome service's `focus()` and `announce()` methods.
 */
let _editorShellRoot: HTMLElement | null = null;

/**
 * Register (or clear) the editor shell root element.
 *
 * The host shell component should call this on mount with its outermost
 * DOM element and on unmount with `null`.  The chrome service's
 * `focus()` and `announce()` methods are no-ops (with diagnostics)
 * when no root is set.
 */
export function setEditorShellRoot(element: HTMLElement | null): void {
  _editorShellRoot = element;
}

/**
 * Return the currently-registered editor shell root element, or `null`
 * if no shell is mounted.
 */
export function getEditorShellRoot(): HTMLElement | null {
  return _editorShellRoot;
}

// ---------------------------------------------------------------------------
// ExtensionContext factory
// ---------------------------------------------------------------------------

/**
 * Create a concrete ExtensionContext for a given extension.
 *
 * Exposes only the approved M1 members:
 * - `apiVersion: 1`
 * - Readonly extension metadata
 * - `chrome` (toast, progress, subscribe, focus, announce)
 * - `services.settings` (localStorage-backed, scoped per extension)
 * - `services.i18n` (minimal t() scaffolding)
 * - `services.diagnostics` (in-memory structured diagnostic reporting)
 * - `creative` stubs that throw typed ExtensionNotImplementedError
 *
 * No raw DataProvider, applyEdit, timeline store, or internal mutation
 * escape hatch is exposed.
 */
export function createExtensionContext(
  extension: ReighExtension,
  creativeOverrides?: Partial<CreativeContext>,
  commands?: ExtensionCommandService,
  effects?: EffectRegistrationService,
  transitions?: TransitionRegistrationService,
  clipTypes?: ClipTypeRegistrationService,
  agentTools?: AgentToolRegistrationService,
  shaders?: ShaderRegistrationService,
  settingsServiceOptions?: CreateExtensionSettingsServiceOptions,
): ExtensionContext {
  const extensionId = extension.manifest.id as string;
  const manifest = extension.manifest; // Already frozen by defineExtension

  // ---- diagnostics service ------------------------------------------------
  const diagnosticsList: ExtensionDiagnostic[] = [];
  const diagnosticsService: ExtensionDiagnosticsService = {
    report(diag: Omit<ExtensionDiagnostic, 'extensionId' | 'source'>): void {
      const full: ExtensionDiagnostic = Object.freeze({
        ...diag,
        extensionId,
        source: DIAGNOSTIC_SOURCE_EXTENSION,
      });
      diagnosticsList.push(full);
    },
    get diagnostics(): readonly ExtensionDiagnostic[] {
      return diagnosticsList;
    },
  };

  // ---- settings service (injectable factory, localStorage-backed) -----------
  const { service: settingsService, dispose: disposeSettings } =
    createExtensionSettingsService(extensionId, manifest, settingsServiceOptions);

  // ---- i18n service (with manifest message bundle fallback) ----------------
  const messages: Record<string, string> | undefined =
    manifest.messages as Record<string, string> | undefined;

  const i18nService: ExtensionI18nService = {
    t(key: string, replacements?: Record<string, string | number>): string {
      // Resolve from message bundle first, fall back to key verbatim
      let resolved = messages?.[key] ?? key;
      if (replacements) {
        for (const [k, v] of Object.entries(replacements)) {
          const placeholder = '{{' + k + '}}';
          while (resolved.includes(placeholder)) {
            resolved = resolved.replace(placeholder, String(v));
          }
        }
      }
      return resolved;
    },
  };

  // ---- chrome service (with subscription cleanup) --------------------------
  const subscribers = new Map<
    string,
    Set<(payload: unknown) => void>
  >();

  // ---- aria-live host node (created lazily on first announce) -------------
  let _ariaLiveHost: HTMLElement | null = null;

  /** Get or create the aria-live container inside the shell root. */
  function getOrCreateAriaLiveHost(politeness: 'polite' | 'assertive'): HTMLElement | null {
    const root = _editorShellRoot;
    if (!root) return null;

    if (_ariaLiveHost && root.contains(_ariaLiveHost)) {
      _ariaLiveHost.setAttribute('aria-live', politeness);
      return _ariaLiveHost;
    }

    // Clear stale reference if node was removed
    _ariaLiveHost = null;

    const host = document.createElement('div');
    host.setAttribute('data-video-editor-aria-live', '');
    host.setAttribute('aria-live', politeness);
    host.setAttribute('aria-atomic', 'true');
    host.className = 'sr-only';
    root.appendChild(host);
    _ariaLiveHost = host;
    return host;
  }

  const chromeService: ExtensionChromeService = {
    toast(message: string, severity: DiagnosticSeverity = 'info'): void {
      // Host-visible toast — dispatched via console + subscriber in dev
      if (typeof console !== 'undefined') {
        const fn = severity === 'error' ? console.error : severity === 'warning' ? console.warn : console.log;
        fn(`[Extension ${extensionId}] ${message}`);
      }
      // Notify toast subscribers
      const subs = subscribers.get('toast');
      if (subs) {
        subs.forEach((handler) => {
          try {
            handler({ message, severity });
          } catch {
            // subscriber errors are silently dropped
          }
        });
      }
    },
    progress(percent: number, label?: string): void {
      const subs = subscribers.get('progress');
      if (subs) {
        subs.forEach((handler) => {
          try {
            handler({ percent, label } as ChromeProgressPayload);
          } catch {
            // subscriber errors are silently dropped
          }
        });
      }
    },
    subscribe<E extends ChromeEvent>(
      event: E,
      handler: (payload: ChromeEventPayload<E>) => void,
    ): DisposeHandle {
      if (!subscribers.has(event)) {
        subscribers.set(event, new Set());
      }
      const eventSubs = subscribers.get(event)!;
      eventSubs.add(handler as (payload: unknown) => void);

      return {
        dispose(): void {
          eventSubs.delete(handler as (payload: unknown) => void);
        },
      };
    },
    focus(selector: string): void {
      const root = _editorShellRoot;
      if (!root) {
        diagnosticsService.report({
          severity: 'warning',
          code: 'chrome/focus-no-shell',
          message: `Cannot focus "${selector}": no editor shell root is mounted.`,
        });
        return;
      }

      // Try to find the element within the shell root
      const element = root.querySelector(selector);
      if (element instanceof HTMLElement) {
        try {
          element.focus();
        } catch {
          // focus() may throw on non-focusable elements in some environments
          diagnosticsService.report({
            severity: 'warning',
            code: 'chrome/focus-not-focusable',
            message: `Cannot focus "${selector}": element is not focusable.`,
          });
        }
        return;
      }

      // Not found in shell root — check if it exists in the document
      // (indicating a portal target or out-of-shell element)
      if (document.querySelector(selector)) {
        diagnosticsService.report({
          severity: 'warning',
          code: 'chrome/focus-out-of-shell',
          message: `Cannot focus "${selector}": element found outside the editor shell root (possible portal target).`,
        });
        return;
      }

      // Not found anywhere
      diagnosticsService.report({
        severity: 'warning',
        code: 'chrome/focus-missing-selector',
        message: `Cannot focus "${selector}": no matching element found.`,
      });
    },
    announce(message: string, politeness: 'polite' | 'assertive' = 'polite'): void {
      const host = getOrCreateAriaLiveHost(politeness);
      if (!host) {
        // Fallback: log to console when no shell root is mounted
        if (typeof console !== 'undefined') {
          console.log(`[Extension ${extensionId} announce] ${message}`);
        }
        return;
      }

      // Clear first so repeated identical messages are re-announced
      host.textContent = '';
      // Force a reflow so the clear takes effect before setting new text.
      // Use requestAnimationFrame so assistive tech registers the change.
      requestAnimationFrame(() => {
        host.textContent = message;
      });
    },
  };

  /** Clean up all chrome event subscribers. */
  function disposeChromeSubscriptions(): void {
    subscribers.clear();
  }

  // ---- creative context (stubs with optional live overrides) --------------
  const creative = createCreativeContext(creativeOverrides);

  // ---- commands service (optional, wired by provider) -----------------------
  const commandsService: ExtensionCommandService = commands ?? {
    registerCommand(_commandId: string, _handler: CommandHandler, _options?: CommandRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'commands/not-wired',
        message: `Cannot register command "${_commandId}" — the CommandRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- effects service (optional, wired by provider) ------------------------
  const effectsService: EffectRegistrationService = effects ?? {
    registerComponent(_effectId: string, _component: EffectComponent, _options?: EffectRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'effects/not-wired',
        message: `Cannot register effect component "${_effectId}" — the EffectRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- transitions service (optional, wired by provider) --------------------
  const transitionsService: TransitionRegistrationService = transitions ?? {
    registerRenderer(_transitionId: string, _renderer: TransitionRenderer, _options?: TransitionRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'transitions/not-wired',
        message: `Cannot register transition renderer "${_transitionId}" — the TransitionRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- clipTypes service (optional, wired by provider) -----------------------
  const clipTypesService: ClipTypeRegistrationService = clipTypes ?? {
    registerClipType(_clipTypeId: string, _renderer: ClipRenderer, _inspector?: ClipInspector, _options?: ClipTypeRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'clipTypes/not-wired',
        message: `Cannot register clip type "${_clipTypeId}" — the ClipTypeRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- shaders service (optional, wired by provider) ------------------------
  const shadersService: ShaderRegistrationService = shaders ?? {
    registerShader(_shaderId: string, _source: ShaderSourceDescriptor, _options?: ShaderRegistrationOptions): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'shaders/not-wired',
        message: `Cannot register shader "${_shaderId}" — the ShaderRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
  };

  // ---- agentTools service (optional, wired by provider) ----------------------
  const agentToolsService: AgentToolRegistrationService = agentTools ?? {
    registerTool(_toolId: string, _handler: AgentToolHandler): DisposeHandle {
      diagnosticsService.report({
        severity: 'error',
        code: 'agentTools/not-wired',
        message: `Cannot register agent tool "${_toolId}" — the AgentToolRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
    },
    async invokeProcess(_toolId: string, _config: ProcessSpawnConfig): Promise<ToolProcessResult> {
      return {
        family: 'process',
        diagnostics: [{
          severity: 'info',
          code: 'agent-tool/process-not-available',
          message: `Process invocation for tool "${_toolId}" is not available until M12.`,
        }],
      };
    },
  };

  // ---- assemble, attach dispose, then freeze -------------------------------
  const ctx = {
    apiVersion: 1,
    extension: {
      id: manifest.id,
      version: manifest.version,
      label: manifest.label,
      description: manifest.description,
      manifest,
    },
    chrome: chromeService,
    services: {
      settings: settingsService,
      i18n: i18nService,
      diagnostics: diagnosticsService,
    },
    creative,
    commands: commandsService,
    effects: effectsService,
    transitions: transitionsService,
    clipTypes: clipTypesService,
    shaders: shadersService,
    agentTools: agentToolsService,
  } as ExtensionContext;

  // Attach host-service disposal so the lifecycle can clean up settings
  // (localStorage keys) and chrome subscriptions without the extension
  // author needing to know about internal service state.
  // Must be attached BEFORE freezing.
  Object.defineProperty(ctx, CONTEXT_DISPOSE_SYMBOL, {
    value: function disposeHostServices(): void {
      disposeSettings();
      disposeChromeSubscriptions();
    },
    writable: false,
    enumerable: false,
    configurable: false,
  });

  // Freeze after property definition so the Symbol key is included.
  const frozenCtx: ExtensionContext = Object.freeze(ctx);
  Object.freeze(frozenCtx.extension);
  Object.freeze(frozenCtx.services);

  return frozenCtx;
}

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

/**
 * The earliest milestone that activates each contribution kind.
 *
 * Derived from the canonical video family registry
 * (`VIDEO_FAMILY_REGISTRY` in `src/sdk/video/families/familyDefinitions.ts`).
 * Any kind not in the registry is treated as not-yet-bridged.
 */
export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> =
  VIDEO_FAMILY_LEGACY_MILESTONE_MAP as Record<ContributionKind, string | undefined>;

/**
 * Execution maturity levels considered "bridged" (runtime behavior exists).
 * `delegated` and `absent` are NOT bridged — they lack real host adapter behavior.
 */
const BRIDGED_EXECUTION_MATURITIES: ReadonlySet<ExecutionMaturity> = new Set<ExecutionMaturity>([
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

/**
 * Check whether a contribution kind is bridged in the current runtime.
 *
 * Derived from the canonical video family registry — a kind is considered
 * bridged when its `executionMaturity` is `runtime-bridged`, `host-integrated`,
 * or `public-supported`.  Kinds with `delegated` or `absent` execution maturity
 * are NOT bridged.
 *
 * Returns the milestone name if NOT bridged, or null if it is bridged.
 */
export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const def = getVideoFamily(kind);
  if (!def) {
    const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
    return milestone || 'unknown';
  }

  if (BRIDGED_EXECUTION_MATURITIES.has(def.executionMaturity)) {
    return null;
  }

  return def.legacyMilestone ?? CONTRIBUTION_KIND_MILESTONE[kind] ?? 'unknown';
}

/**
 * Look up the canonical family definition for a contribution kind.
 * Returns `undefined` when the kind is not in the family registry.
 */
export function getVideoFamilyDefinition(
  kind: ContributionKind,
): FamilyDefinition<ContributionKind> | undefined {
  return getVideoFamily(kind) as FamilyDefinition<ContributionKind> | undefined;
}

/**
 * Build a conformance report for a contribution kind from the family registry.
 * Returns `undefined` when the kind is not in the registry.
 */
export function getVideoFamilyConformanceReport(
  kind: ContributionKind,
): FamilyConformanceReport<ContributionKind> | undefined {
  return buildVideoFamilyReport(kind) as FamilyConformanceReport<ContributionKind> | undefined;
}

/**
 * Report the legacy bridge status for a contribution kind.
 *
 * Returns:
 * - `null` when the kind is bridged (execution maturity ≥ runtime-bridged).
 * - The milestone string (e.g. `'M6'`) when the kind is NOT bridged.
 * - `'unknown'` when the kind is not in the registry and has no milestone entry.
 */
export function getVideoFamilyLegacyBridgeStatus(kind: ContributionKind): string | null {
  return contributionKindNotYetBridged(kind);
}

// ---------------------------------------------------------------------------
// Project requirements metadata
// ---------------------------------------------------------------------------

/** Project-level extension requirement entry. */
export interface ProjectExtensionRequirement {
  extensionId: string;
  versionRange?: string;
  referencedContributionIds?: readonly string[];
  /** Known integrity hash if previously installed. */
  integrity?: string;
  /** Dependency posture: degrade gracefully or require. */
  posture?: 'required' | 'optional';
}

/** Container for project-scoped extension requirement metadata. */
export interface ProjectExtensionRequirements {
  requirements: readonly ProjectExtensionRequirement[];
}

import type {
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts.ts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';
import type {
  TimelineDiff,
  TimelineDiffGranularity,
  TimelinePatch,
  TimelinePatchDiagnostic,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
} from '@/sdk/video/timeline/patch.ts';
import type {
  AssetReadSurface,
  MaterialReadSurface,
  MetadataFacetValueKind,
} from '@/sdk/video/assets/metadata.ts';
import type { ExportService } from '@/sdk/video/exports/outputFormats.ts';

// ---------------------------------------------------------------------------
// M3: TimelineOps — atomic mutation interface
// ---------------------------------------------------------------------------

/**
 * Stable host adapter for atomic timeline mutations.
 *
 * TimelineOps is the only public mutation surface available to extensions
 * and host proposal machinery. It validates full batches, delegates to the
 * existing commitData/history path for undo/persistence, and does not expose
 * internal mutation APIs, provider handles, or raw timeline stores.
 */
export interface TimelineOps {
  /**
   * Validate a patch batch without mutating timeline state.
   * Returns structured diagnostics for every invalid operation.
   */
  validate(patch: TimelinePatch): TimelinePatchValidationResult;

  /**
   * Preview a patch batch against a snapshot of current timeline state.
   * Returns the projected timeline diff and affected object IDs without
   * committing any changes.
   */
  preview(patch: TimelinePatch): TimelinePreviewResult;

  /**
   * Validate and apply a patch batch atomically through the existing
   * commitData/history path. Returns the applied diff.
   *
   * Throws if validation fails — always call validate() first when
   * the caller cannot guarantee validity.
   */
  apply(patch: TimelinePatch): TimelineDiff;

  /**
   * Take a checkpoint of the current timeline state for later rollback.
   * Returns the checkpoint identifier.
   */
  checkpoint(label?: string): string;

  /**
   * Rollback to a previously taken checkpoint, discarding all mutations
   * applied after it.
   *
   * Returns the diff that was undone, or null if the checkpoint is not found.
   */
  rollback(checkpointId: string): TimelineDiff | null;

  /**
   * Convenience: set all audio tracks to the given muted state and commit.
   * Returns the diff describing which tracks were affected.
   */
  setAllTracksMuted(muted: boolean): TimelineDiff;
}

// ---------------------------------------------------------------------------
// M3: TimelineProposal
// ---------------------------------------------------------------------------

/** Lifecycle state of a proposal. */
export type ProposalState =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'stale'
  | 'expired';

/**
 * Structured detail carried by a proposal that reached stale or expired state.
 *
 * Produced by the runtime when a proposal's baseVersion no longer matches
 * the current reader version (stale) or when its TTL has elapsed (expired).
 * Carried on {@link TimelineProposal.expiryDetail} so the UI can surface
 * clear diagnostics without parsing raw timeline-patch codes.
 */
export interface ProposalExpiryDetail {
  /** Why the proposal transitioned to stale/expired. */
  reason: 'base-version-mismatch' | 'ttl-elapsed' | 'manual';
  /** The baseVersion the proposal was created against. */
  baseVersion: number;
  /** The current reader version at the time the proposal transitioned. */
  currentVersion: number;
  /** When the proposal was created (epoch ms). */
  createdAt: number;
  /** When the proposal transitioned to stale/expired (epoch ms). */
  expiredAt: number;
  /** The TTL in ms that was configured when the proposal was created, if any. */
  ttlMs?: number;
}

/** A proposal to mutate the timeline, submitted by an extension or tool. */
export interface TimelineProposal {
  /** Unique proposal identifier assigned by the runtime. */
  id: string;
  /** The source that created this proposal (extension ID, tool name, etc.). */
  source: string;
  /** Human-readable rationale / description. */
  rationale?: string;
  /** Current lifecycle state. */
  state: ProposalState;
  /** The patch to apply if accepted. */
  patch: TimelinePatch;
  /**
   * The baseVersion the proposal was created against.
   * If the current reader version differs at acceptance time, the proposal
   * is stale and must be rejected or refreshed.
   */
  baseVersion: number;
  /**
   * Whether this proposal's effects can be previewed (ghost-rendered)
   * without committing. Reserved operations are non-previewable.
   */
  previewable: boolean;
  /** The diff produced when this proposal was last previewed, if any. */
  previewDiff?: TimelineDiff;
  /** Timestamp when the proposal was created (epoch ms). */
  createdAt: number;
  /** Timestamp when the proposal last changed state (epoch ms). */
  updatedAt: number;
  /**
   * Epoch-ms timestamp after which the proposal is considered expired.
   * When set, the runtime may auto-expire the proposal once this time
   * has elapsed.  If absent, the proposal has no TTL.
   */
  expiresAt?: number;
  /**
   * When the proposal became stale or expired, this carries structured
   * detail about the conflict (version drift, TTL elapsed, etc.).
   * Absent for proposals in pending/accepted/rejected state.
   */
  expiryDetail?: ProposalExpiryDetail;
  /** Diagnostics produced during validation or preview, if any. */
  diagnostics?: readonly TimelinePatchDiagnostic[];
}

/** Input for creating a new proposal — now defined in
 * src/sdk/video/timeline/reader.ts and re-exported above. */
// (TimelineProposalInput is re-exported from reader.ts)

/** Listener callback for proposal state changes. */
export type ProposalListener = (proposal: TimelineProposal) => void;

// ---------------------------------------------------------------------------
// M3: ProposalRuntime
// ---------------------------------------------------------------------------

/**
 * Provider-scoped proposal runtime.
 *
 * Manages the lifecycle of TimelineProposals: creation, preview, acceptance,
 * rejection, and stale detection. Proposals are in-memory and provider-scoped
 * for M3; page refresh drops unaccepted proposals.
 */
export interface ProposalRuntime {
  /**
   * Subscribe to proposal state changes.
   * The listener is called whenever any proposal changes state.
   * Returns a DisposeHandle for unsubscription.
   */
  subscribe(listener: ProposalListener): DisposeHandle;

  /**
   * Create a new pending proposal. If a proposal from the same source
   * already exists in 'pending' state, it is atomically replaced
   * (replaceForSource semantics).
   */
  create(input: TimelineProposalInput): TimelineProposal;

  /**
   * Preview a pending proposal against the current reader snapshot.
   * Returns the projected diff. Does not mutate canonical timeline state.
   * Updates the proposal's previewDiff and previewable fields.
   */
  preview(proposalId: string): TimelinePreviewResult;

  /**
   * Accept a pending proposal. Revalidates baseVersion against the current
   * reader snapshot; if stale, the proposal is marked stale and the call
   * fails with a diagnostic. On success, applies the patch through
   * TimelineOps and marks the proposal accepted.
   *
   * Throws on stale baseVersion or if the proposal is not in 'pending' state.
   */
  accept(proposalId: string): TimelineDiff;

  /**
   * Reject a pending proposal, moving it to 'rejected' state.
   * No timeline mutation occurs.
   */
  reject(proposalId: string, reason?: string): void;

  /**
   * Get a proposal by ID, or undefined if not found.
   */
  get(proposalId: string): TimelineProposal | undefined;

  /**
   * List all proposals, optionally filtered by state.
   */
  list(state?: ProposalState): readonly TimelineProposal[];

  /**
   * Get the current reader snapshot version for baseVersion comparisons.
   */
  readonly currentVersion: number;

  /**
   * Scan pending proposals and transition any whose TTL has elapsed
   * to 'expired' state, populating {@link TimelineProposal.expiryDetail}.
   *
   * @param maxAgeMs - Proposals older than this many ms (relative to now)
   *   are eligible for expiry.  A value of 0 expires every pending proposal.
   * @returns The proposals that were transitioned to 'expired' in this call.
   */
  expireStale(maxAgeMs: number): readonly TimelineProposal[];
}

// ---------------------------------------------------------------------------
// M3: SourceMapRuntime
// ---------------------------------------------------------------------------

/**
 * Provider-scoped runtime for managing SourceMapEntry records.
 *
 * Stores entries in extension project-data under well-known keys so they
 * are replayable, rollback-safe, and stale-aware.
 *
 * SourceMapEntry records are stored in the extension's project-data namespace
 * using the key pattern `__sm__:<entryId>`.  This keeps them alongside other
 * extension-owned data and makes them subject to the same limits.
 */
export interface SourceMapRuntime {
  /**
   * Create a new non-stale source-map entry and persist it via project-data.
   * Returns the created entry.
   */
  create(
    extensionId: string,
    targetId: string,
    targetGranularity: TimelineDiffGranularity,
    sourceUri: string,
    sourceStartLine: number,
    sourceStartColumn: number,
    sourceEndLine: number,
    sourceEndColumn: number,
    meta?: Record<string, unknown>,
  ): SourceMapEntry;

  /**
   * Retrieve a source-map entry by ID from project-data.
   * Returns undefined if not found.
   */
  get(extensionId: string, entryId: string): SourceMapEntry | undefined;

  /**
   * Retrieve all source-map entries for a given timeline target (clip, track, etc.).
   */
  getForTarget(extensionId: string, targetId: string): SourceMapEntry[];

  /**
   * Retrieve all source-map entries for a given source URI.
   */
  getForSource(extensionId: string, sourceUri: string): SourceMapEntry[];

  /**
   * Mark all source-map entries for a given source URI as stale.
   * Updates the stale flag in persisted project-data.
   * Returns the updated entries.
   */
  markStale(extensionId: string, sourceUri: string): SourceMapEntry[];

  /**
   * Mark all source-map entries for a given target as stale.
   */
  markStaleForTarget(extensionId: string, targetId: string): SourceMapEntry[];

  /**
   * Delete a source-map entry from project-data.
   * Returns true if the entry existed and was deleted.
   */
  delete(extensionId: string, entryId: string): boolean;

  /**
   * List all source-map entries for an extension.
   */
  list(extensionId: string): SourceMapEntry[];
}

// ---------------------------------------------------------------------------
// M3: SourceMapEntry
// ---------------------------------------------------------------------------

/**
 * A bidirectional mapping between a timeline object and a source range
 * in extension-owned code or DSL.
 *
 * Source maps enable navigation from timeline objects to the code that
 * generated them and from source ranges back to affected timeline objects.
 */
export interface SourceMapEntry {
  /** Unique identifier for this mapping. */
  id: string;
  /** The extension that owns this mapping. */
  source: string;
  /** Timeline object identifier (clip ID, track ID, etc.). */
  targetId: string;
  /** Granularity of the mapped object. */
  targetGranularity: TimelineDiffGranularity;
  /** Source file path or virtual document URI. */
  sourceUri: string;
  /** 0-based start line in the source. */
  sourceStartLine: number;
  /** 0-based start column in the source. */
  sourceStartColumn: number;
  /** 0-based end line in the source (exclusive). */
  sourceEndLine: number;
  /** 0-based end column in the source (exclusive). */
  sourceEndColumn: number;
  /**
   * True when the mapping may be out of date because the source or the
   * timeline object has changed since the mapping was created.
   */
  stale: boolean;
  /** Opaque metadata attached by the mapping producer. */
  meta?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M3: Generated-object metadata
// ---------------------------------------------------------------------------

/**
 * Metadata attached to timeline objects that were generated or managed
 * by an extension. Stored in the clip/track/app record so the editor can
 * surface ownership, enable confirmation dialogs, and support source-map
 * navigation without importing extension code.
 */
export interface GeneratedObjectMeta {
  /** Extension ID that generated or manages this object. */
  extensionId: string;
  /** The contribution within the extension that produced this object. */
  contributionId?: string;
  /** Opaque generation provenance (source hash, prompt ID, etc.). */
  provenance?: Record<string, unknown>;
  /** Timestamp when the object was generated (epoch ms). */
  generatedAt?: number;
  /** Source-map entry ID that maps this object to its source, if any. */
  sourceMapEntryId?: string;
}

// ---------------------------------------------------------------------------
// M3: Host-owned proposal UI contract (surface shape only)
// ---------------------------------------------------------------------------

/**
 * Contract for the host-owned proposal panel UI surface.
 *
 * The actual UI is implemented by the host using existing
 * TimelineEditorShellCore, AlertDialog, and DiagnosticPanel components.
 * This interface defines the data shape the UI surface expects from the
 * proposal runtime — it does not prescribe rendering details.
 */
export interface ProposalPanelState {
  /** All proposals currently known to the runtime. */
  proposals: readonly TimelineProposal[];
  /** The proposal currently selected for preview, if any. */
  selectedProposalId: string | null;
  /** Whether the proposal panel is visible. */
  visible: boolean;
}

/** Action types the proposal UI can dispatch. */
export type ProposalPanelAction =
  | { type: 'select'; proposalId: string }
  | { type: 'deselect' }
  | { type: 'accept'; proposalId: string }
  | { type: 'reject'; proposalId: string; reason?: string }
  | { type: 'preview'; proposalId: string }
  | { type: 'toggleVisibility' };

/**
 * Serialized proposal envelope returned by edge functions (e.g. the
 * ai-timeline-agent) when operating in proposal mode.
 *
 * This shape is wire-stable and consumed by the client-side
 * `normalizeInvokeResponse` path to hydrate the ProposalPanel UI without
 * parsing unstructured agent response text.
 */
export interface ProposalEnvelope {
  /** The proposals produced by this edge invocation. */
  proposals: readonly TimelineProposal[];
  /**
   * The config version the proposals were created against.
   * Used by the client to detect stale/conflict before rendering the panel.
   */
  baseVersion: number;
  /**
   * Human-readable summary produced by the agent alongside the proposals.
   * May be empty when only proposals are returned.
   */
  summary?: string;
  /**
   * Whether any mutation was applied during this invocation.
   * In pure proposal mode this is always false; the field is present so
   * the client can distinguish proposal-only responses from apply-mode
   * responses that also carry proposals.
   */
  mutationApplied: boolean;
}

// ---------------------------------------------------------------------------
// M1: Proposal import contracts
// ---------------------------------------------------------------------------

/** Status of an individual proposal within an import batch. */
export type ProposalImportStatus = 'imported' | 'skipped' | 'rejected';

/** Diagnostic produced during proposal import validation. */
export interface ProposalImportDiagnostic {
  /** Diagnostic severity. */
  severity: 'error' | 'warning';
  /** Diagnostic code (e.g. 'proposal-import/missing-id'). */
  code: string;
  /** Human-readable diagnostic message. */
  message: string;
  /** Zero-based index of the proposal in the envelope's proposals array. */
  proposalIndex?: number;
  /** The proposal ID, if available. */
  proposalId?: string;
  /** Additional structured detail. */
  detail?: Record<string, unknown>;
}

/** Result of importing proposals from a ProposalEnvelope. */
export interface ProposalImportResult {
  /** Number of proposals successfully imported. */
  imported: number;
  /** Number of proposals skipped (e.g. non-pending state). */
  skipped: number;
  /** Number of proposals rejected during import validation. */
  rejected: number;
  /** Individual per-proposal status entries. */
  statuses: readonly { proposalId: string; status: ProposalImportStatus }[];
  /** Diagnostics produced during import, if any. */
  diagnostics: readonly ProposalImportDiagnostic[];
}

// ---------------------------------------------------------------------------
// M6: Asset metadata, parser, search, output-format, and read-surface contracts
// ---------------------------------------------------------------------------
//
// All portable asset metadata contracts now live in
// src/sdk/video/assets/metadata.ts.  This block re-exports them for
// backward-compatible public consumption through @reigh/editor-sdk.

export type {
  AssetIntegrityMetadata,
  AssetGPSMetadata,
  AssetConsentMetadata,
  AssetProvenanceMetadata,
  EnrichmentStatus,
  DeferredEnrichmentRecord,
  AssetMetadata,
  MetadataFacetValueKind,
  MetadataFacetDescriptor,
  AssetDetailSectionDescriptor,
  AssetReadSurface,
  MaterialReadSurface,
} from '@/sdk/video/assets/metadata';

// Re-export parser runtime contracts from their dedicated module
export type {
  ParserInput,
  ParserResult,
  ParserDiagnostic,
  ParserHandler,
} from '@/sdk/video/assets/parsers';

// Re-export search runtime contracts from their dedicated module
export type {
  SearchMatch,
  SearchProviderResult,
  SearchProviderHandler,
  SearchProviderContext,
} from '@/sdk/video/assets/search';

// Re-export output-format runtime contracts from their dedicated module
export type {
  CompileOnlyOutputResult,
  OutputFormatHandler,
  OutputFormatContext,
  ExportService,
  OutputFormatRegistrationOptions,
} from '@/sdk/video/exports/outputFormats';
