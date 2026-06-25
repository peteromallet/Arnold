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

// ---------------------------------------------------------------------------
// ID validation
// ---------------------------------------------------------------------------

/** A non-empty string that uniquely identifies an extension or contribution. */
export type ExtensionId = string & { readonly __brand: 'ExtensionId' };

/** A non-empty string that uniquely identifies a contribution within an extension. */
export type ContributionId = string & { readonly __brand: 'ContributionId' };

const ID_RE = /^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*$/i;

/**
 * Validate an extension or contribution ID.
 * Returns an array of error messages (empty = valid).
 */
export function validateExtensionId(id: string): string[] {
  const errors: string[] = [];
  if (typeof id !== 'string' || id.length === 0) {
    errors.push('ID must be a non-empty string');
    return errors;
  }
  if (id.length > 128) {
    errors.push('ID must be 128 characters or fewer');
  }
  if (!ID_RE.test(id)) {
    errors.push(
      "ID must match /^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*$/i " +
        '(lowercase start, dot-separated segments of letters/digits/hyphens/underscores)',
    );
  }
  return errors;
}

/**
 * Validate a contribution ID. Same rules as extension IDs.
 */
export function validateContributionId(id: string): string[] {
  return validateExtensionId(id);
}

// ---------------------------------------------------------------------------
// DisposeHandle
// ---------------------------------------------------------------------------

/** A handle returned by lifecycle methods that require cleanup. */
export interface DisposeHandle {
  /** Synchronous, idempotent, must not throw. */
  dispose(): void;
  /** Optional explicit resource management support. */
  readonly [Symbol.dispose]?: () => void;
}

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

export type DiagnosticSeverity = 'error' | 'warning' | 'info';

/**
 * Diagnostic provenance source.
 *
 * - `extension` — authored by a trusted local extension (the only source
 *   extensions themselves can produce).  The SDK pins this value for
 *   extension-reported diagnostics.
 * - `render` — emitted by the host render pipeline.
 * - `provider` — emitted by a host provider (editor runtime, etc.).
 *
 * Extensions MUST NOT set host-owned sources.
 */
export type DiagnosticSource = 'extension' | 'render' | 'provider';

/** The only diagnostic source extensions are permitted to use. */
export const DIAGNOSTIC_SOURCE_EXTENSION: DiagnosticSource = 'extension';

export interface ExtensionDiagnostic {
  severity: DiagnosticSeverity;
  code: string;
  message: string;
  extensionId?: string;
  contributionId?: string;
  /** The earliest milestone that is expected to activate this feature. */
  milestone?: string;
  /**
   * Diagnostic provenance source.
   * Extension-authored diagnostics always use {@link DIAGNOSTIC_SOURCE_EXTENSION}.
   */
  source?: DiagnosticSource;
  /** Additional structured detail (clip reference, effect ID, etc.). */
  detail?: Record<string, unknown>;
}

export interface DiagnosticSourceRange {
  startLine: number;
  startCol: number;
  endLine: number;
  endCol: number;
}

export interface Diagnostic extends ExtensionDiagnostic {
  id: string;
  sourceRange?: DiagnosticSourceRange;
  relatedRanges?: readonly DiagnosticSourceRange[];
}

export interface DiagnosticCollection {
  readonly snapshot: readonly Diagnostic[];
  publish(diagnostic: Diagnostic): void;
  remove(predicate: (diagnostic: Diagnostic) => boolean): void;
  /** Remove all diagnostics belonging to the given extension ID. */
  removeByExtensionId(extensionId: string): void;
  clear(): void;
  subscribe(listener: () => void): DisposeHandle;
  getSnapshot(): readonly Diagnostic[];
}

/** Default per-extension diagnostic capacity before oldest-first eviction. */
export const DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY = 100;

function freezeDiagnostic(diagnostic: Diagnostic): Diagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) } : {}),
    ...(diagnostic.relatedRanges
      ? { relatedRanges: Object.freeze(diagnostic.relatedRanges.map((range) => Object.freeze({ ...range }))) }
      : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

export interface CreateDiagnosticCollectionOptions {
  /**
   * Maximum number of diagnostics allowed per extension ID.
   * When publishing a new diagnostic (not replacing an existing one by ID)
   * would exceed this limit, the oldest diagnostic for that extension is
   * evicted before the new one is added.
   * @default {@link DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY}
   */
  perExtensionCapacity?: number;
}

export function createDiagnosticCollection(
  initialDiagnostics: readonly Diagnostic[] = [],
  options: CreateDiagnosticCollectionOptions = {},
): DiagnosticCollection {
  const capacity = options.perExtensionCapacity ?? DEFAULT_DIAGNOSTIC_PER_EXTENSION_CAPACITY;
  const diagnostics: Diagnostic[] = initialDiagnostics.map(freezeDiagnostic);
  const listeners = new Set<() => void>();
  let snapshot: readonly Diagnostic[] = Object.freeze([...diagnostics]);

  const publishSnapshot = () => {
    snapshot = Object.freeze([...diagnostics]);
    for (const listener of listeners) {
      listener();
    }
  };

  const evictOldestForExtension = (extensionId: string): void => {
    // Find the oldest (lowest index) diagnostic for this extension
    for (let i = 0; i < diagnostics.length; i += 1) {
      if (diagnostics[i].extensionId === extensionId) {
        diagnostics.splice(i, 1);
        return; // only evict one — the oldest
      }
    }
  };

  return {
    get snapshot(): readonly Diagnostic[] {
      return snapshot;
    },
    publish(diagnostic: Diagnostic): void {
      const frozen = freezeDiagnostic(diagnostic);
      const existingIndex = diagnostics.findIndex((item) => item.id === frozen.id);
      if (existingIndex >= 0) {
        // Replace in-place — does NOT count toward capacity
        diagnostics[existingIndex] = frozen;
      } else {
        // New diagnostic: enforce per-extension capacity
        const extId = frozen.extensionId;
        if (extId) {
          const extCount = diagnostics.reduce(
            (count, d) => count + (d.extensionId === extId ? 1 : 0),
            0,
          );
          if (extCount >= capacity) {
            evictOldestForExtension(extId);
          }
        }
        diagnostics.push(frozen);
      }
      publishSnapshot();
    },
    remove(predicate: (diagnostic: Diagnostic) => boolean): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (predicate(diagnostics[index])) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    removeByExtensionId(extensionId: string): void {
      let changed = false;
      for (let index = diagnostics.length - 1; index >= 0; index -= 1) {
        if (diagnostics[index].extensionId === extensionId) {
          diagnostics.splice(index, 1);
          changed = true;
        }
      }
      if (changed) {
        publishSnapshot();
      }
    },
    clear(): void {
      if (diagnostics.length === 0) return;
      diagnostics.length = 0;
      publishSnapshot();
    },
    subscribe(listener: () => void): DisposeHandle {
      listeners.add(listener);
      return {
        dispose(): void {
          listeners.delete(listener);
        },
      };
    },
    getSnapshot(): readonly Diagnostic[] {
      return snapshot;
    },
  };
}

/**
 * An export-scoped diagnostic produced by the pre-render export guard.
 * Carries the same shape as {@link ExtensionDiagnostic} but uses
 * export-prefixed diagnostic codes (e.g. `export/unknown-clip-type`)
 * and includes timeline-specific detail (clip ID, effect name, etc.).
 */
export interface ExportDiagnostic extends ExtensionDiagnostic {
  /** The diagnostic code is always an export-prefixed string. */
  code: `export/${string}`;
  /** Timeline-scoped detail such as clip ID, effect/transition name. */
  detail?: Record<string, unknown> & {
    clipId?: string;
    clipType?: string;
    effectType?: string;
    transitionType?: string;
    shaderId?: string;
    shaderScope?: ShaderMaterializerRequirementScope;
  };
}

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
// M4: Commands, Keybindings, Context Menus — target and handler contracts
// ---------------------------------------------------------------------------

/**
 * Sealed target context union for context-menu contributions.
 *
 * - `clip` — right-click on a single clip
 * - `clip-selection` — right-click when multiple clips are selected
 * - `track` — right-click on a track header/label
 * - `timeline-area` — right-click on the editable canvas background
 *
 * Shot-group contributions are **reserved** and diagnosed rather than
 * silently ignored until the shot-group ambiguity is resolved.
 */
export type TargetContext = 'clip' | 'clip-selection' | 'track' | 'timeline-area';

/**
 * Typed payload discriminator for command invocations originating
 * from a context menu or other target-scoped trigger.
 */
export type TargetContextPayload =
  | { readonly target: 'clip'; readonly clipId: string; readonly trackId: string }
  | { readonly target: 'clip-selection'; readonly clipIds: readonly string[]; readonly trackId: string }
  | { readonly target: 'track'; readonly trackId: string }
  | { readonly target: 'timeline-area' };

/**
 * Context passed to a command handler on invocation.
 *
 * Handlers receive the fully-qualified command ID, the owning extension ID,
 * and an optional `target` payload populated when the command is triggered
 * from a context-menu or other target-scoped surface.
 */
export interface CommandRunContext {
  /** The fully-qualified command ID that was invoked. */
  readonly commandId: string;
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The target context, with its typed payload, when applicable. */
  readonly target?: TargetContextPayload;
}

/**
 * A command handler function registered by an extension during activate().
 *
 * May be synchronous or async.  Thrown errors (or rejected promises) are
 * caught by the runtime and published as diagnostics + host toasts — they
 * must not crash the palette, menus, or editor shell.
 */
export type CommandHandler = (ctx: CommandRunContext) => void | Promise<void>;

/** Options for imperative command registration via ctx.commands.registerCommand(). */
export interface CommandRegistrationOptions {
  /** Human-readable label for the palette (defaults to command ID when absent). */
  label?: string;
  /** Category for palette grouping. */
  category?: string;
}

// ---------------------------------------------------------------------------
// Manifest
// ---------------------------------------------------------------------------

/** Known contribution kinds. Reserved/inactive kinds are validated but not bridged. */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection'
  | 'timelineOverlay'
  // M4: commands, keybindings, context menus
  | 'command'
  | 'keybinding'
  | 'contextMenuItem'
  // M6: parser, output format, search provider, metadata facet, asset detail section
  | 'parser'
  | 'outputFormat'
  | 'searchProvider'
  | 'metadataFacet'
  | 'assetDetailSection'
  // M12: trusted local process descriptors
  | 'process'
  // M7-M9: effect, transition, clip type, automation (bridged in their milestones)
  | 'effect'
  | 'transition'
  | 'clipType'
  // M13: dedicated shader/WebGL contributions
  | 'shader'
  // M9: automation clip type (host-owned)
  | 'automation'
  // M10: agent tool contributions (host-mediated, proposal-backed)
  | 'agentTool'
  // Reserved — not yet bridged
  | 'agent';

/** Slot names the host shell recognizes. */
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

/** A single contribution declaration inside an extension manifest. */
export interface ExtensionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: ContributionKind;
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Slot name — required when kind === 'slot'. */
  slot?: VideoEditorSlotName;
  /** Dialog layer when kind === 'dialog'. */
  layer?: 'modal' | 'overlay';
  /** Inspector placement when kind === 'inspectorSection'. */
  placement?: 'before-default' | 'after-default';
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Reserved for future render provider descriptors. */
  render?: string;
  /** Reserved for future effect descriptors. */
  effectId?: string;
  /** Reserved for future transition descriptors. */
  transitionId?: string;
  /** Reserved for future clip-type descriptors. */
  clipTypeId?: string;
  /** M13: Shader identifier declared by the extension. */
  shaderId?: string;
  /** M6: Parser identifier declared by the extension. */
  parserId?: string;
  /** M6: Output format identifier declared by the extension. */
  outputFormatId?: string;
  /** M6: Search provider identifier declared by the extension. */
  searchProviderId?: string;
  /** M6: Metadata facet identifier declared by the extension. */
  metadataFacetId?: string;
  /** M6: Asset detail section identifier declared by the extension. */
  assetDetailSectionId?: string;
  /** M10: Agent tool identifier declared by the extension. */
  agentToolId?: string;
}

// ---------------------------------------------------------------------------
// Runtime-inspectable contract constants
// ---------------------------------------------------------------------------

/**
 * All known contribution kinds as a runtime-inspectable readonly array.
 * Use this to enumerate valid kinds at runtime without relying on the
 * TypeScript type system alone.
 */
export const KNOWN_CONTRIBUTION_KINDS: readonly ContributionKind[] = [
  'slot',
  'dialog',
  'panel',
  'inspectorSection',
  'timelineOverlay',
  'command',
  'keybinding',
  'contextMenuItem',
  'parser',
  'outputFormat',
  'searchProvider',
  'metadataFacet',
  'assetDetailSection',
  'process',
  'effect',
  'transition',
  'clipType',
  'shader',
  'automation',
  'agentTool',
  'agent',
] as const;

/** Set form of {@link KNOWN_CONTRIBUTION_KINDS} for fast lookups. */
export const KNOWN_CONTRIBUTION_KINDS_SET: ReadonlySet<string> = new Set(KNOWN_CONTRIBUTION_KINDS);

/**
 * All known slot names as a runtime-inspectable readonly array.
 */
export const KNOWN_SLOT_NAMES: readonly VideoEditorSlotName[] = [
  'header',
  'toolbar',
  'leftPanel',
  'rightPanel',
  'codePanel',
  'writingPanel',
  'stagePanel',
  'timelineFooter',
  'statusBar',
  'dialogs',
  'assetPanel',
  'inspectorPanel',
] as const;

/** Set form of {@link KNOWN_SLOT_NAMES} for fast lookups. */
export const KNOWN_SLOT_NAMES_SET: ReadonlySet<string> = new Set(KNOWN_SLOT_NAMES);

// ---- Placement value constants ----

/** Valid placement values for inspectorSection contributions. */
export const INSPECTOR_SECTION_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
] as const;

/** Valid placement values for panel contributions. */
export const PANEL_PLACEMENTS: readonly string[] = [
  'asset-panel',
] as const;

/** Valid placement values for assetDetailSection contributions. */
export const ASSET_DETAIL_SECTION_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
] as const;

/** Union of all valid placement values across contribution kinds. */
export const ALL_VALID_PLACEMENTS: readonly string[] = [
  'before-default',
  'after-default',
  'asset-panel',
] as const;

// ---------------------------------------------------------------------------
// M6: Metadata facet / asset detail section contributions
// ---------------------------------------------------------------------------

/**
 * M6: A metadata facet contribution declared in an extension manifest.
 *
 * Metadata facets tell the host how to surface a metadata field
 * as a searchable/filterable facet in the asset panel.
 */
export interface MetadataFacetContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'metadataFacet';
  /**
   * Dot-separated path to the metadata field.
   * E.g. 'gps.latitude', 'integrity.algorithm', 'extensions.myExt.tags'.
   */
  fieldPath: string;
  /** Human-readable display name for the facet. */
  displayName: string;
  /** The value kind — determines rendering and filtering strategy. */
  valueKind: MetadataFacetValueKind;
  /** Lower values sort first. Default 0. */
  order?: number;
  /**
   * Aggregation posture hint for the host.
   * - `exact` — values should be surfaced individually
   * - `range` — numeric values can be bucketed
   * - `presence` — only show whether the field exists
   */
  aggregationPosture?: 'exact' | 'range' | 'presence';
  /**
   * Allowed values when `valueKind` is 'enum'.
   * The host uses this for dropdown/checkbox filter UI.
   */
  enumValues?: readonly string[];
}

/**
 * M6: An asset detail section contribution declared in an extension manifest.
 *
 * Asset detail sections are named slots within the asset detail panel.
 * The host owns section placement, empty/error states, search result badges,
 * and provenance-chain rendering.  Extensions provide section descriptors
 * to declare what metadata they surface.
 */
export interface AssetDetailSectionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'assetDetailSection';
  /** Human-readable section title. */
  title: string;
  /**
   * Placement within the asset detail panel.
   * - `before-default` — before host-owned metadata sections
   * - `after-default` — after host-owned metadata sections
   */
  placement: 'before-default' | 'after-default';
  /**
   * The metadata field paths this section reads.
   * The host uses these to determine section visibility and data binding.
   */
  fieldPaths?: readonly string[];
  /** Lower values sort first within their placement group. Default 0. */
  order?: number;
  /**
   * Optional visibility predicate (evaluated by host).
   * E.g. 'asset.metadata.integrity != null'.
   */
  when?: string;
}

// ---------------------------------------------------------------------------
// M4: Command / keybinding / context-menu contributions
// ---------------------------------------------------------------------------

/** A command contribution in an extension manifest. */
export interface CommandContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'command';
  /** The command identifier (e.g. 'myExtension.doSomething'). */
  command: string;
  /** Human-readable label for the command palette. */
  label: string;
  /** Category for palette grouping. */
  category?: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/** A keybinding contribution that binds a keyboard shortcut to a command. */
export interface KeybindingContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'keybinding';
  /** The command identifier this keybinding triggers. */
  command: string;
  /**
   * Platform-aware key notation (e.g. 'CtrlOrCmd+K', 'Alt+Shift+R').
   * Modifier keys: CtrlOrCmd, Ctrl, Cmd, Alt, Shift.
   * Key names are case-insensitive and normalized at registration time.
   */
  key: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/** A context-menu item contribution for clip/track/timeline-area surfaces. */
export interface ContextMenuItemContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'contextMenuItem';
  /** The command identifier this menu item invokes. */
  command: string;
  /** Override label for the menu item (falls back to command contribution label). */
  label?: string;
  /** The target context(s) where this item appears. */
  target: TargetContext;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Optional icon name for the menu item. */
  icon?: string;
}

// ---------------------------------------------------------------------------
// M6: Parser / output format / search provider contributions
// ---------------------------------------------------------------------------

/**
 * M6: A parser contribution declared in an extension manifest.
 *
 * Parsers enrich asset metadata during ingestion.  The contribution declares
 * accepted MIME types, file extensions, max size, and whether the parser is
 * required (blocking) or optional.
 *
 * Actual parser behaviour is registered imperatively during activate() via
 * the host's parser registry (ctx.creative.assets if active, or a
 * dedicated parser registration surface).
 */
export interface ParserContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'parser';
  /** Human-readable label for diagnostics / UI. */
  label: string;
  /**
   * Accepted MIME types.  At least one of `acceptMimeTypes` or
   * `acceptExtensions` must be non-empty.
   */
  acceptMimeTypes?: readonly string[];
  /**
   * Accepted file extensions (without leading dot).  E.g. `['jpg','jpeg']`.
   */
  acceptExtensions?: readonly string[];
  /**
   * Maximum file size in bytes this parser will accept.
   * Files exceeding this size produce a diagnostic and are not passed
   * to the parser handler.
   */
  maxBytes?: number;
  /**
   * When true, parser failure blocks asset ingestion with a clear
   * diagnostic.  When false (default), the failure is diagnostic-only
   * and the asset is still ingested with whatever metadata was already
   * available.
   */
  required?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/**
 * M6: An output format contribution declared in an extension manifest.
 *
 * Output formats produce an artifact from timeline and asset data.
 * Compile-only formats (requiresRender: false) do not invoke the render
 * pipeline; they read timeline/asset data and produce a deterministic
 * artifact (e.g. metadata JSON).
 *
 * Render-dependent formats (requiresRender: true) are declaration-only
 * in M6 and appear disabled in the export UI with a diagnostic explaining
 * that execution is unavailable until render planning activates the route.
 */
export interface OutputFormatContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'outputFormat';
  /** Human-readable label for the export UI. */
  label: string;
  /**
   * When false, this is a compile-only format that does not invoke the
   * render pipeline.  When true, the format requires render planning and
   * is surfaced as disabled/reserved in M6.
   */
  requiresRender: boolean;
  /** File extension for the output artifact (e.g. 'json', 'xml'). */
  outputExtension: string;
  /** MIME type for the output artifact (e.g. 'application/json'). */
  outputMimeType?: string;
  /** Optional human-readable description shown in the export UI. */
  description?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
  /**
   * Render-dependent output route requirements.
   * Required when `requiresRender` is true; ignored for compile-only outputs.
   */
  render?: RenderDependentOutputDescriptor;
  /** Optional declarative sampling defaults for export configuration. */
  sampling?: SamplingConfig;
  /** Sidecar kinds this output may emit. */
  sidecars?: readonly RenderArtifactSidecarDescriptor[];
}

/** M12: Compile-only output formats never enter render planning. */
export interface CompileOnlyOutputFormatContribution extends OutputFormatContribution {
  requiresRender: false;
  render?: never;
}

/** M12: Render-dependent output formats require planner-owned route execution. */
export interface RenderDependentOutputFormatContribution extends OutputFormatContribution {
  requiresRender: true;
  render: RenderDependentOutputDescriptor;
}

/** M12: Route/process requirements for a render-dependent output format. */
export interface RenderDependentOutputDescriptor {
  /** Routes this output can accept after planning. */
  readonly routes: readonly RenderRoute[];
  /** Capabilities required before the output can execute. */
  readonly requiredCapabilities?: readonly string[];
  /** Optional local process needed to produce this output. */
  readonly processId?: string;
  /** Optional process operation needed to produce this output. */
  readonly operationId?: string;
  /** Determinism posture claimed by this output route. */
  readonly determinism?: DeterminismStatus;
  /** Human-readable planner hint shown when the route is unavailable. */
  readonly unavailableMessage?: string;
}

/**
 * M6: A search provider contribution declared in an extension manifest.
 *
 * Search providers supply asset/material search results to the host search
 * surface.  The provider owns indexing, model choice, and refresh; the host
 * owns query dispatch, result merge, and source labeling.
 *
 * Search providers are bounded to host query/result integration — no local
 * model loading, inference, vector database, or ranking ownership is added
 * in M6.
 */
export interface SearchProviderContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'searchProvider';
  /** Human-readable label shown in the search surface. */
  label: string;
  /**
   * Optional description of the search provider capabilities
   * (e.g. 'semantic search over image embeddings').
   */
  description?: string;
  /**
   * Kinds of results this provider can surface.
   * Defaults to ['asset'] when omitted.
   */
  resultKinds?: readonly ('asset' | 'material')[];
  /** Lower values sort first. Default 0. */
  order?: number;
}

// ---------------------------------------------------------------------------
// M7: Trusted component effect contributions
// ---------------------------------------------------------------------------

/**
 * M7: An effect contribution declared in an extension manifest.
 *
 * Trusted component effects render in the browser preview and are blocked
 * from browser-export and worker-export unless the contribution declares
 * stronger capability.
 */
export interface EffectContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'effect';
  /** The effect identifier used in registerComponent calls. */
  effectId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the effect to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the effect to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

// ---------------------------------------------------------------------------
// M8: Trusted component transition contributions
// ---------------------------------------------------------------------------

/**
 * M8: A transition contribution declared in an extension manifest.
 *
 * Trusted component transitions render in the browser preview and are blocked
 * from browser-export and worker-export unless the contribution declares
 * stronger capability.
 */
export interface TransitionContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'transition';
  /** The transition identifier used in registerRenderer calls. */
  transitionId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the transition to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the transition to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

// ---------------------------------------------------------------------------
// M9: Clip type contributions — renderers, inspectors, keyframes, automation
// ---------------------------------------------------------------------------

/**
 * M9: A clip-type contribution declared in an extension manifest.
 *
 * Contributed clip types are trusted local browser-preview components
 * analogous to M7 effects and M8 transitions. Worker execution of
 * contributed clip code stays out of scope for M9.
 */
export interface ClipTypeContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'clipType';
  /** The clip-type identifier used in registerClipType calls. */
  clipTypeId: string;
  /** Human-readable label for diagnostics / UI. */
  label?: string;
  /**
   * When true, allows the clip type to be executed during browser export.
   * Default: false (preview-only).
   */
  allowBrowserExport?: boolean;
  /**
   * When true, allows the clip type to be executed in a worker context.
   * Default: false (preview-only).
   */
  allowWorkerExport?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}

/**
 * M9: A trusted local component registered by an extension as a clip renderer.
 *
 * Clip renderers execute in the browser preview and receive host-interpolated
 * params through ClipRendererProps.
 */
export type ClipRenderer = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * M9: A trusted local component registered by an extension as a clip inspector.
 *
 * Clip inspectors render in the inspector panel when a clip of the
 * owning type is selected.
 */
export type ClipInspector = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * M9: A parameter definition for clip-type parameter schemas.
 *
 * Mirrors the effect/transition parameter definition shape so extensions
 * can declare parameter contracts at registration time.
 */
export interface ClipParameterDefinition {
  /** Unique parameter name (used as the key in params). */
  name: string;
  /** Human-readable label for UI controls. */
  label: string;
  /** Description shown in tooltips / inspector. */
  description: string;
  /** Parameter type determining the control and coercion rules. */
  type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
  /** Default value when no override is provided. */
  default?: number | string | boolean | Record<string, unknown>;
  /** Minimum value (number type only). */
  min?: number;
  /** Maximum value (number type only). */
  max?: number;
  /** Step increment (number type only). */
  step?: number;
  /** Options for select-type parameters. */
  options?: readonly { label: string; value: string }[];
}

/** M9: Ordered array of clip parameter definitions. */
export type ClipParameterSchema = readonly ClipParameterDefinition[];

/** M9: Options for imperative clip-type registration via ctx.clipTypes.registerClipType(). */
export interface ClipTypeRegistrationOptions {
  /** Override label for picker / UI. */
  label?: string;
  /**
   * Parameter schema for this clip type.
   * Validated at registration time.
   */
  parameterSchema?: ClipParameterSchema;
}

/**
 * M9: Clip-type registration service available as `ctx.clipTypes` during activate().
 */
export interface ClipTypeRegistrationService {
  /**
   * Register a trusted local renderer and optional inspector for a clip type.
   *
   * The `clipTypeId` must match the `clipTypeId` field of a `ClipTypeContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the clip type when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerClipType(
    clipTypeId: string,
    renderer: ClipRenderer,
    inspector?: ClipInspector,
    options?: ClipTypeRegistrationOptions,
  ): DisposeHandle;
}

// ---------------------------------------------------------------------------
// M13: Shader/WebGL contributions
// ---------------------------------------------------------------------------

/** M13: Shader pass scopes supported by the V1 WebGL bridge. */
export type ShaderPassKind = 'clip' | 'overlay' | 'postprocess';

/** M13: Color-space posture declared by a shader pass or texture input. */
export type ShaderColorSpace = 'srgb' | 'linear';

/** M13: Host-owned fallback posture when a shader cannot compile or preview. */
export type ShaderFallbackBehavior = 'bypass' | 'transparent' | 'solid-black';

/** M13: Texture source categories supported by the V1 shader bridge. */
export type ShaderTextureSourceKind =
  | 'clip-frame'
  | 'static-image-asset'
  | 'live-generated-frame';

/** M13: Texture sampling filter used by the WebGL preview bridge. */
export type ShaderTextureFilter = 'nearest' | 'linear';

/** M13: Texture coordinate wrapping policy used by the WebGL preview bridge. */
export type ShaderTextureWrap = 'clamp-to-edge' | 'repeat' | 'mirrored-repeat';

/**
 * M13: Shader source supplied inline by the manifest or during registration.
 *
 * Fragment source is required for inline programs. Vertex source is optional
 * because the host can provide the default fullscreen-triangle vertex shader.
 */
export interface ShaderInlineSource {
  readonly kind: 'inline';
  readonly fragment: string;
  readonly vertex?: string;
}

/** M13: Shader source resolved by the extension runtime from a module export. */
export interface ShaderModuleSource {
  readonly kind: 'module';
  readonly specifier: string;
  readonly exportName?: string;
}

/** M13: Public shader source descriptor. */
export type ShaderSourceDescriptor = ShaderInlineSource | ShaderModuleSource;

/**
 * M13: Shader pass descriptor.
 *
 * V1 supports a single shader per clip scope and one active postprocess shader.
 * Ordered stacks, multipass FBO chains, feedback buffers, and shader transitions
 * remain outside this SDK contract.
 */
export interface ShaderPassDescriptor {
  readonly kind: ShaderPassKind;
  /** Uniform name of the host-provided input texture for this pass, if any. */
  readonly inputTextureUniform?: string;
  /** Expected color space for input and output conversion. */
  readonly colorSpace?: ShaderColorSpace;
  /** Whether the output alpha is preserved or treated as opaque by the host. */
  readonly alpha?: 'preserve' | 'opaque';
}

/** M13: Supported shader uniform control/value kinds for V1. */
export type ShaderUniformType =
  | 'float'
  | 'int'
  | 'bool'
  | 'vec2'
  | 'vec3'
  | 'vec4'
  | 'color'
  | 'enum'
  | 'textureRef'
  | 'frame'
  | 'time';

/** M13: Enum option for shader uniform controls. */
export interface ShaderUniformEnumOption {
  readonly label: string;
  readonly value: string;
}

/** M13: Texture reference value used by textureRef uniforms. */
export interface ShaderTextureRef {
  readonly kind: ShaderTextureSourceKind;
  /** Asset key, live source ID, generated frame ID, or host-defined frame ref. */
  readonly ref?: string;
}

/** M13: Default values accepted by shader uniform definitions. */
export type ShaderUniformDefaultValue =
  | number
  | boolean
  | string
  | readonly number[]
  | ShaderTextureRef;

/** M13: A host-rendered shader uniform definition. */
export interface ShaderUniformDefinition {
  readonly name: string;
  readonly label: string;
  readonly description?: string;
  readonly type: ShaderUniformType;
  readonly default?: ShaderUniformDefaultValue;
  readonly min?: number;
  readonly max?: number;
  readonly step?: number;
  readonly options?: readonly ShaderUniformEnumOption[];
}

/** M13: Ordered shader uniform schema. */
export type ShaderUniformSchema = readonly ShaderUniformDefinition[];

/** M13: A host-provided texture input binding for a shader. */
export interface ShaderTextureDefinition {
  readonly name: string;
  readonly label?: string;
  readonly description?: string;
  /** The sampler uniform that receives this texture. Defaults to `name`. */
  readonly uniform?: string;
  readonly sourceKind: ShaderTextureSourceKind;
  readonly required?: boolean;
  readonly colorSpace?: ShaderColorSpace;
  readonly filter?: ShaderTextureFilter;
  readonly wrap?: ShaderTextureWrap;
}

/** M13: Ordered shader texture binding schema. */
export type ShaderTextureSchema = readonly ShaderTextureDefinition[];

/**
 * M13: Optional materializer metadata.
 *
 * This descriptor advertises where a later planner may look for a route that
 * produces RenderMaterial. It does not make browser preview exportable.
 */
export interface ShaderMaterializerDescriptor {
  readonly routes?: readonly RenderRoute[];
  readonly requiredCapabilities?: readonly string[];
  readonly processId?: string;
  readonly operationId?: string;
  readonly unavailableMessage?: string;
}

/** M13: A shader/WebGL contribution declared in an extension manifest. */
export interface ShaderContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'shader';
  /** Identifier used in ctx.shaders.registerShader(). */
  shaderId: string;
  /** Human-readable label for picker, inspector, and diagnostics. */
  label: string;
  readonly description?: string;
  /** Pass scope; use a descriptor when color/alpha/input details matter. */
  pass: ShaderPassKind | ShaderPassDescriptor;
  readonly source?: ShaderSourceDescriptor;
  readonly uniforms?: ShaderUniformSchema;
  readonly textures?: ShaderTextureSchema;
  readonly fallback?: ShaderFallbackBehavior;
  readonly materializer?: ShaderMaterializerDescriptor;
  /** Lower values sort first. Default 0. */
  readonly order?: number;
  /** Optional visibility predicate (evaluated by host). */
  readonly when?: string;
}

/** M13: Options for imperative shader registration via ctx.shaders.registerShader(). */
export interface ShaderRegistrationOptions {
  readonly label?: string;
  readonly pass?: ShaderPassKind | ShaderPassDescriptor;
  readonly uniforms?: ShaderUniformSchema;
  readonly textures?: ShaderTextureSchema;
  readonly fallback?: ShaderFallbackBehavior;
  readonly materializer?: ShaderMaterializerDescriptor;
}

/**
 * M13: Shader registration service available as `ctx.shaders` during activate().
 *
 * Shaders are registered through a dedicated WebGL bridge surface, not through
 * `ctx.effects.registerComponent()`. The `shaderId` must match a
 * {@link ShaderContribution} in the extension manifest.
 */
export interface ShaderRegistrationService {
  registerShader(
    shaderId: string,
    source: ShaderSourceDescriptor,
    options?: ShaderRegistrationOptions,
  ): DisposeHandle;
}

// ---------------------------------------------------------------------------
// M9: Keyframe contracts
// ---------------------------------------------------------------------------

/**
 * M9: Interpolation mode for keyframe curves.
 *
 * - `linear` — lerp between adjacent keyframe values.
 * - `hold` — step function; value holds until the next keyframe.
 */
export type KeyframeInterpolation = 'linear' | 'hold';

/**
 * M9: A single keyframe stored as JSON-serializable timeline data on a clip.
 *
 * Keyframes are host-owned timeline data validated against the owning
 * parameter schema, with interpolation performed by the host before
 * passing computed params to renderers.
 */
export interface Keyframe {
  /** Time in seconds. */
  time: number;
  /** JSON-serializable value (number | string | boolean). */
  value: number | string | boolean;
  /** Interpolation mode from this keyframe to the next. */
  interpolation: KeyframeInterpolation;
}

/**
 * M9: Interpolated parameter value at a specific time.
 *
 * Produced by the host keyframe interpolator and passed to clip renderers
 * so extension code never needs to implement timeline interpolation.
 */
export interface InterpolatedParam {
  /** The parameter name. */
  name: string;
  /** The interpolated value at the requested time. */
  value: number | string | boolean;
}

// ---------------------------------------------------------------------------
// M9: Automation clip contracts
// ---------------------------------------------------------------------------

/**
 * M9: Target descriptor for an automation clip.
 *
 * Automation clips are host-owned timeline clips (clipType: 'automation')
 * that reference target parameters by contribution ID and parameter path.
 */
export interface AutomationClipTarget {
  /** The contribution ID that owns the target parameter. */
  contributionId: string;
  /** Dot-separated path to the target parameter within the contribution. */
  parameterPath: string;
}

/**
 * M9: Params stored on an automation clip.
 *
 * Automation clips apply baked keyframe curves to override target
 * extension parameter values during preview and export.
 */
export interface AutomationClipParams {
  /** The target parameter this automation clip controls. */
  target: AutomationClipTarget;
  /** Ordered keyframes defining the automation curve. */
  keyframes: readonly Keyframe[];
  /** Whether this automation clip is active. */
  enabled: boolean;
}

// ---------------------------------------------------------------------------
// M10: Agent tool contributions — host-mediated, proposal-backed
// ---------------------------------------------------------------------------

/**
 * M10: An agent tool contribution declared in an extension manifest.
 *
 * Agent tools are host-mediated: the host owns invocation, progress,
 * cancellation, proposal creation, and UI. Extensions contribute tool
 * metadata, input schemas, and a handler that returns {@link ToolResult}
 * records. All mutations are proposal-backed through host-owned
 * {@link ProposalRuntime}.
 */
export interface AgentToolContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'agentTool';
  /** The tool identifier used in ctx.agentTools registration calls. */
  toolId: string;
  /** Human-readable label for discovery / UI. */
  label: string;
  /** Human-readable description shown in tooltips / panel. */
  description?: string;
  /**
   * Input schema defining the shape of the tool's invocation payload.
   * Uses a StandardSchema-compatible subset validated at registration time.
   */
  inputSchema?: AgentToolInputSchema;
  /**
   * Result families this tool can produce.
   * When empty, all families are accepted (validated at runtime).
   */
  resultFamilies?: readonly ToolResultFamily[];
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
}

/**
 * Supported StandardSchema subset for agent tool input schemas.
 *
 * The host uses SchemaForm to render these schemas. Only a minimal
 * StandardSchema subset is supported in M10:
 * - type: 'object' with properties
 * - property types: string, number, boolean, enum (string[])
 * - nested objects (one level)
 * - required fields
 * - title, description annotations
 */
export interface AgentToolInputSchema {
  type: 'object';
  properties?: Record<string, AgentToolInputProperty>;
  required?: readonly string[];
  title?: string;
  description?: string;
}

/** A single property in an agent tool input schema. */
export interface AgentToolInputProperty {
  type: 'string' | 'number' | 'boolean' | 'object';
  title?: string;
  description?: string;
  default?: string | number | boolean;
  enum?: readonly string[];
  /** Nested properties (only when type === 'object'). */
  properties?: Record<string, AgentToolInputProperty>;
  /** Nested required fields (only when type === 'object'). */
  required?: readonly string[];
}

/**
 * Stable result families for agent tool outputs.
 *
 * New result shapes must fit an existing family or justify a new family
 * in SDK review. Reject one-off feature-specific result objects with
 * diagnostics.
 */
export type ToolResultFamily =
  | 'mutation/proposal'
  | 'generation/session'
  | 'material/artifact'
  | 'enrichment/search'
  | 'export'
  | 'process'
  | 'ui/summary';

/**
 * M10: Grouped ToolResult union.
 *
 * Every result carries a `family` discriminator and a `family`-specific
 * payload. Results that don't fit a known family are rejected with
 * diagnostics before proposals or UI updates are created.
 */
export type ToolResult =
  | ToolMutationProposalResult
  | ToolGenerationSessionResult
  | ToolMaterialArtifactResult
  | ToolEnrichmentSearchResult
  | ToolExportResult
  | ToolProcessResult
  | ToolUISummaryResult;

/** Timeline-mutation proposal result. */
export interface ToolMutationProposalResult {
  family: 'mutation/proposal';
  /** Rationale / explanation for the proposed change. */
  rationale?: string;
  /** The patch(es) to propose via ProposalRuntime. */
  patches: readonly TimelinePatch[];
  /** Affected object IDs for UI context (clip IDs, track IDs, etc.). */
  affectedObjectIds?: readonly string[];
  /** Source-to-output reference map for traceability. */
  sourceRefs?: readonly ToolSourceRef[];
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Generation/session result for long-running generation tools. */
export interface ToolGenerationSessionResult {
  family: 'generation/session';
  /** Session handle for progress tracking and cancellation. */
  session: GenerationSession;
  /** Optional live sample delivery activation metadata. */
  liveDelivery?: GenerationSessionLiveDelivery;
  /** Rationale / explanation for the generation. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Material/artifact result referencing baked or placeholder asset refs. */
export interface ToolMaterialArtifactResult {
  family: 'material/artifact';
  /** Material or artifact references produced by the tool. */
  refs: readonly ToolArtifactRef[];
  /** Rationale / explanation for the generated artifacts. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Enrichment / search result for asset metadata suggestions. */
export interface ToolEnrichmentSearchResult {
  family: 'enrichment/search';
  /** Enrichment suggestions keyed by asset/material key. */
  suggestions?: Record<string, Record<string, unknown>>;
  /** Search result matches, when applicable. */
  matches?: readonly ToolSearchResultMatch[];
  /** Rationale / explanation for the enrichment. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Export result (planner-compatible findings). */
export interface ToolExportResult {
  family: 'export';
  /** Planner-compatible findings (CapabilityFinding shape). */
  findings?: readonly Record<string, unknown>[];
  /** Export-scoped diagnostics. */
  diagnostics?: readonly ToolResultDiagnostic[];
  /** Rationale / explanation for the findings. */
  rationale?: string;
}

/** Process invocation result (pre-M12 placeholder). */
export interface ToolProcessResult {
  family: 'process';
  /** Structured pending diagnostic (always present before M12). */
  diagnostics: readonly ToolResultDiagnostic[];
}

/** UI-only summary result (e.g. copilot explanation, analysis). */
export interface ToolUISummaryResult {
  family: 'ui/summary';
  /** Human-readable summary text. */
  summary: string;
  /** Structured detail for UI rendering. */
  detail?: Record<string, unknown>;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** A source-to-output reference for traceability. */
export interface ToolSourceRef {
  /** Source identifier (clip ID, asset key, track ID, etc.). */
  sourceId: string;
  /** Output identifier produced from the source. */
  outputId: string;
  /** Human-readable description of the transformation. */
  description?: string;
}

/** An artifact reference produced by a tool. */
export interface ToolArtifactRef {
  /** Artifact identifier (asset key, material key, etc.). */
  ref: string;
  /** Kind of artifact (asset, material, placeholder). */
  kind: 'asset' | 'material' | 'placeholder';
  /** Human-readable label for UI. */
  label?: string;
  /** Opaque metadata (e.g. bake parameters, resolution, format). */
  meta?: Record<string, unknown>;
}

/** A search result match from an enrichment tool. */
export interface ToolSearchResultMatch {
  /** Asset or material key. */
  key: string;
  /** Relevance score (0-1). */
  score: number;
  /** Human-readable label. */
  label?: string;
}

/** Structured diagnostic produced during tool execution. */
export interface ToolResultDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code, e.g. 'agent-tool/unsupported-schema'. */
  code: `agent-tool/${string}`;
  message: string;
  /** Structured detail for debugging. */
  detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M10: AgentToolInvocationRequest
// ---------------------------------------------------------------------------

/**
 * Request to invoke an agent tool.
 *
 * Carries the tool ID, extension context, creative context slices,
 * and any tool-specific input. Edge and worker adapters receive only
 * explicit serializable slices — never raw provider internals.
 */
export interface AgentToolInvocationRequest {
  /** The tool identifier being invoked. */
  toolId: string;
  /** The extension ID that registered the tool. */
  extensionId: string;
  /** The contribution ID of the agent tool in the manifest. */
  contributionId: string;
  /** Tool-specific input matching the declared input schema. */
  input?: Record<string, unknown>;
  /**
   * Explicit creative context slices for tool execution.
   * Only serializable projections are included — never raw provider internals.
   */
  context?: AgentToolRequestContext;
}

/** Explicit creative context slices passed to a tool invocation. */
export interface AgentToolRequestContext {
  /** Read-only timeline snapshot at invocation time. */
  timeline?: TimelineSnapshot;
  /** Asset keys and metadata relevant to the request. */
  assets?: readonly { key: string; metadata?: Record<string, unknown> }[];
  /** Material keys and metadata relevant to the request. */
  materials?: readonly { key: string; metadata?: Record<string, unknown> }[];
  /** Export context (selected format, blockers, etc.). */
  export?: AgentToolExportContext;
  /** Opaque request metadata. */
  meta?: Record<string, unknown>;
}

/** Export context passed to export-adjacent tools. */
export interface AgentToolExportContext {
  /** Selected output format ID. */
  outputFormatId?: string;
  /** Known render blockers at invocation time. */
  blockers?: readonly Record<string, unknown>[];
  /** Contribution IDs available for export. */
  contributionIds?: readonly string[];
}

// ---------------------------------------------------------------------------
// M10: GenerationSession (long-running generation)
// ---------------------------------------------------------------------------

/**
 * Session handle for long-running generation tools.
 *
 * Provides progress reporting, cancellation, and a preview-only
 * sample channel placeholder. Live media buffers and bake internals
 * are deferred to M11/M12.
 */
export interface GenerationSession {
  /** Unique session identifier. */
  readonly id: string;
  /** Current progress (0-100). */
  readonly progress: number;
  /** Human-readable progress label. */
  readonly progressLabel?: string;
  /** Whether the session has been cancelled. */
  readonly cancelled: boolean;
  /** Whether the session is complete. */
  readonly done: boolean;
  /** Structured diagnostics produced during generation. */
  readonly diagnostics: readonly ToolResultDiagnostic[];
  /** Optional live delivery metadata used by the host to activate sample delivery. */
  readonly liveDelivery?: GenerationSessionLiveDelivery;
  /** Deterministic final refs produced by the session, when known. */
  readonly finalRefs?: readonly string[];
  /** Deterministic baked refs produced by the session, when known. */
  readonly bakedRefs?: readonly string[];

  /**
   * Subscribe to progress updates.
   * Returns a DisposeHandle for unsubscription.
   */
  onProgress(listener: (progress: number, label?: string) => void): DisposeHandle;

  /**
   * Cancel the generation session.
   * Idempotent — safe to call multiple times.
   */
  cancel(): void;

  /**
   * Get the typed sample channel descriptor for this session.
   *
   * Returns a LiveChannelDescriptor — a branded string that is
   * backward-compatible with M10 code that treated the return
   * value as a plain string. The channel carries live media
   * frames when the session is active.
   */
  getSampleChannel(): LiveChannelDescriptor;

  /**
   * Subscribe to live samples delivered on this session's channel.
   * The listener receives every sample pushed to the channel.
   * Returns a DisposeHandle for unsubscription.
   */
  onSample(listener: (sample: LiveSample) => void): DisposeHandle;

  /**
   * Get the current steering lineage for this session.
   * Returns undefined if no steering decision has been applied yet.
   */
  getSteeringLineage(): SteeringLineage | undefined;

  /**
   * Mark the session as complete with final result data.
   * Safe to call once; subsequent calls are ignored.
   */
  complete(result?: Record<string, unknown>): void;
}

// ---------------------------------------------------------------------------
// M10: AgentToolRegistrationService
// ---------------------------------------------------------------------------

/**
 * Agent tool registration service available as `ctx.agentTools` during activate().
 *
 * Extensions register agent tool handlers imperatively. The host owns
 * invocation, progress, cancellation, proposal creation, and UI.
 */
export interface AgentToolRegistrationService {
  /**
   * Register an agent tool handler.
   *
   * The `toolId` must match the `toolId` field of an `AgentToolContribution`
   * declared by this extension in its manifest.
   *
   * The handler receives an {@link AgentToolInvocationRequest} and returns
   * a {@link ToolResult} (or Promise thereof).
   *
   * Returns a DisposeHandle that unregisters the handler when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerTool(
    toolId: string,
    handler: AgentToolHandler,
  ): DisposeHandle;

  /**
   * Invoke a process-backed tool (pre-M12 placeholder).
   *
   * Always returns a `ToolProcessResult` with a structured pending
   * diagnostic indicating process execution is not available until M12.
   */
  invokeProcess(
    toolId: string,
    config: ProcessSpawnConfig,
  ): Promise<ToolProcessResult>;
}

/**
 * Agent tool handler function registered by an extension.
 *
 * Receives an invocation request with explicit context slices and
 * returns a ToolResult. May be synchronous or async. Thrown errors
 * are caught by the runtime and published as diagnostics.
 */
export type AgentToolHandler = (
  request: AgentToolInvocationRequest,
) => ToolResult | Promise<ToolResult>;

// ---------------------------------------------------------------------------

export interface ProcessSpawnConfig {
  command: string;
  args?: readonly string[];
  env?: Record<string, string>;
  cwd?: string;
}

export type ProcessManifestEntry = ProcessSpec;

/** M12: Declarative environment field for trusted local process configuration. */
export interface ProcessEnvFieldSpec {
  readonly key: string;
  readonly label?: string;
  readonly description?: string;
  readonly required?: boolean;
  readonly secret?: boolean;
  readonly defaultValue?: string;
  readonly platformDefaults?: Partial<Record<'darwin' | 'linux' | 'win32', string>>;
}

/** M12: Operation a trusted local process exposes to tools, render routes, or export formats. */
export interface ProcessOperationSpec {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly inputSchema?: AgentToolInputSchema;
  readonly outputKinds?: readonly ('artifact' | 'material' | 'sidecar' | 'diagnostic' | 'planner-result' | 'tool-result')[];
  readonly requiredCapabilities?: readonly string[];
  readonly routes?: readonly RenderRoute[];
  readonly determinism?: DeterminismStatus;
}

/** M12: Declarative trusted-local process specification. */
export interface ProcessSpec {
  id: string;
  label: string;
  description?: string;
  spawn: ProcessSpawnConfig;
  protocol: 'stdio-jsonrpc';
  healthCheck?: string;
  shutdown?: string;
  restartPolicy?: 'never' | 'always' | 'on-failure';
  version?: CapabilityVersion;
  env?: readonly ProcessEnvFieldSpec[];
  operations?: readonly ProcessOperationSpec[];
  capabilities?: IntegrationCapabilities;
  requiredBy?: readonly CapabilitySourceRef[];
}

/** M12: Process contribution declared in an extension manifest. */
export interface ProcessContribution {
  readonly id: ContributionId;
  readonly kind: 'process';
  readonly label?: string;
  readonly order?: number;
  readonly spec: ProcessSpec;
}

export type ProcessLifecycleState =
  | 'not-installed'
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'busy'
  | 'degraded'
  | 'failed'
  | 'stopping';

export interface ProcessStatusBase {
  readonly processId: string;
  readonly state: ProcessLifecycleState;
  readonly label?: string;
  readonly message?: string;
  readonly updatedAt?: string;
  readonly blockingOperations?: readonly string[];
  readonly diagnostics?: readonly ExtensionDiagnostic[];
}

export type ProcessStatus =
  | (ProcessStatusBase & { readonly state: 'not-installed'; readonly installHint?: string })
  | (ProcessStatusBase & { readonly state: 'stopped' })
  | (ProcessStatusBase & { readonly state: 'starting'; readonly startedAt?: string })
  | (ProcessStatusBase & { readonly state: 'ready'; readonly pid?: number; readonly version?: CapabilityVersion })
  | (ProcessStatusBase & { readonly state: 'busy'; readonly operationId?: string; readonly progress?: ProcessProgressEvent })
  | (ProcessStatusBase & { readonly state: 'degraded'; readonly healthCheck?: string })
  | (ProcessStatusBase & { readonly state: 'failed'; readonly errorCode?: string; readonly recoverable?: boolean })
  | (ProcessStatusBase & { readonly state: 'stopping'; readonly reason?: string });

export interface ProcessProgressEvent {
  readonly operationId: string;
  readonly percent?: number;
  readonly message?: string;
  readonly currentStep?: string;
  readonly totalSteps?: number;
}

export interface ProcessLogSummary {
  readonly level: 'debug' | 'info' | 'warning' | 'error';
  readonly message: string;
  readonly at?: string;
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M11: Live Data Bridge — source, channel, sample, bake, permission,
// recording, learn, steering, and binding-resolution contracts
// ---------------------------------------------------------------------------

/**
 * Kind of a live data source.
 *
 * - `webcam` — browser camera (getUserMedia)
 * - `microphone` — browser microphone (getUserMedia)
 * - `midi` — Web MIDI API device
 * - `serial` — Web Serial API port
 * - `bluetooth` — Web Bluetooth API device
 * - `generated` — procedurally generated frames/data (generative AI, procedural, etc.)
 * - `screen-capture` — getDisplayMedia / screen sharing
 * - `audio-device` — non-microphone audio output capture
 * - `osc` — OSC (Open Sound Control) over UDP/WebSocket
 * - `custom` — extension-defined custom source
 */
export type LiveSourceKind =
  | 'webcam'
  | 'microphone'
  | 'midi'
  | 'serial'
  | 'bluetooth'
  | 'generated'
  | 'screen-capture'
  | 'audio-device'
  | 'osc'
  | 'custom';

/**
 * Lifecycle status of a live data source.
 *
 *   inactive   → source registered, not yet active
 *   activating → permission requested, stream opening
 *   active     → source is streaming live data
 *   error      → source encountered a blocking error
 *   disposed   → source explicitly disposed by provider
 *   orphaned   → source's owning extension was unmounted/disposed
 */
export type LiveSourceStatus =
  | 'inactive'
  | 'activating'
  | 'active'
  | 'error'
  | 'disposed'
  | 'orphaned';

/**
 * A diagnostic produced by a live source or live data operation.
 */
export interface LiveSourceDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code (e.g. 'live/permission-denied'). */
  code: string;
  message: string;
  sourceId?: string;
  channelId?: LiveChannelDescriptor;
  detail?: Record<string, unknown>;
}

/**
 * A provider-scoped live data source.
 *
 * Live sources are ephemeral runtime objects scoped to a single
 * provider mount. They are never persisted in timeline config/history.
 * Only live binding metadata is persisted on timeline objects.
 */
export interface LiveSource {
  /** Unique source identifier (provider-scoped). */
  readonly id: string;
  /** The kind of data this source produces. */
  readonly kind: LiveSourceKind;
  /** Current lifecycle status. */
  readonly status: LiveSourceStatus;
  /** Human-readable label. */
  readonly label?: string;
  /** Current active diagnostics. */
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  /** Opaque source metadata. */
  readonly metadata?: Record<string, unknown>;
  /** Permission state for this source. */
  readonly permission?: LiveSourcePermission;
  /** Recording state, if recording is active. */
  readonly recording?: LiveRecordingState;
  /** Learn-mode state, if learn is active. */
  readonly learnMode?: LiveLearnMode;
}

// --- Live channel descriptors ---

/**
 * Kind of data carried by a live channel.
 */
export type LiveChannelKind =
  | 'video'
  | 'audio'
  | 'midi'
  | 'osc'
  | 'data'
  | 'control';

/**
 * A typed channel descriptor that is string-compatible.
 *
 * LiveChannelDescriptor is a branded string — it can be used anywhere a
 * string is expected (e.g. as a map key, in string concatenation, etc.)
 * but carries a distinct type so the compiler can distinguish channel
 * identifiers from arbitrary strings.
 *
 * This preserves backward compatibility with M10 code that treated
 * getSampleChannel() as returning a plain string.
 */
export type LiveChannelDescriptor = string & { readonly __brand: 'LiveChannelDescriptor' };

/**
 * Rich metadata for a live channel.
 *
 * Obtainable via LiveSessionsService.getChannelMetadata().
 */
export interface LiveChannelMetadata {
  /** The channel descriptor (string-compatible identifier). */
  readonly channelId: LiveChannelDescriptor;
  /** The kind of data carried by this channel. */
  readonly kind: LiveChannelKind;
  /** The source this channel is attached to. */
  readonly sourceId: string;
  /** Human-readable label. */
  readonly label?: string;
  /** Opaque channel metadata. */
  readonly metadata?: Record<string, unknown>;
}

// --- Live samples ---

/**
 * Format of a live sample frame's data payload.
 */
export type LiveSampleFormat = 'raw' | 'encoded' | 'json' | 'binary';

/**
 * A single frame/tick of live data.
 *
 * Carries timestamped data in one of several formats. The host
 * must read samples synchronously in render paths.
 */
export interface LiveSampleFrame {
  /** Monotonic timestamp (milliseconds since source start). */
  readonly timestamp: number;
  /** The sample data payload. */
  readonly data: ArrayBuffer | Uint8Array | Record<string, unknown>;
  /** Format of the data payload. */
  readonly format: LiveSampleFormat;
  /** Opaque frame metadata. */
  readonly metadata?: Record<string, unknown>;
}

/**
 * A delivered live sample on a channel.
 */
export interface LiveSample {
  /** The channel this sample arrived on. */
  readonly channelId: LiveChannelDescriptor;
  /** The sample frame data. */
  readonly frame: LiveSampleFrame;
  /** Monotonically increasing sequence number for this channel. */
  readonly sequenceNumber: number;
}

// --- Live permissions ---

/**
 * Permission state for a live source.
 *
 *   prompt      — browser permission prompt not yet shown/answered
 *   granted     — permission granted, stream can open
 *   denied      — permission denied by user or system
 *   unavailable — API not available in this browser/environment
 */
export type LivePermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

/**
 * Permission metadata for a live source.
 */
export interface LiveSourcePermission {
  /** Current permission state. */
  readonly state: LivePermissionState;
  /** Human-readable reason the permission is requested. */
  readonly reason?: string;
  /** User-facing device label. */
  readonly deviceLabel?: string;
  /** ISO 8601 timestamp when permission was requested. */
  readonly requestedAt?: string;
}

// --- Live recording ---

/**
 * Recording mode for a live source.
 *
 *   stream  — continuous recording into ring buffer
 *   take    — discrete take-based recording
 *   loop    — looping buffer (overwrites oldest data)
 *   trigger — triggered capture on external signal
 */
export type LiveRecordingMode = 'stream' | 'take' | 'loop' | 'trigger';

/**
 * Recording state for a live source.
 */
export interface LiveRecordingState {
  /** Whether recording is currently active. */
  readonly active: boolean;
  /** The recording mode in use. */
  readonly mode: LiveRecordingMode;
  /** ISO 8601 timestamp when recording started. */
  readonly startedAt?: string;
  /** Recording duration in milliseconds. */
  readonly duration?: number;
  /** Current take index (for 'take' mode). */
  readonly takeIndex?: number;
}

// --- Live learn mode ---

/**
 * Learn-mode state for a live source.
 *
 *   idle        — not currently learning
 *   mapping     — mapping physical controls to parameters
 *   calibrating — calibrating device range/response
 *   tracking    — actively tracking a learn target
 */
export type LiveLearnMode = 'idle' | 'mapping' | 'calibrating' | 'tracking';

// --- Live bake ---

/**
 * Kind of target that a live bake can produce.
 *
 *   asset           — asset registry entry (video/image/audio bytes)
 *   keyframe        — deterministic keyframe(s) on a clip parameter
 *   automation      — automation clip with baked curves
 *   clip            — standard timeline clip referencing baked asset
 *   sidecar         — metadata sidecar file (JSON, CSV, etc.)
 *   render-material — RenderMaterialRef in the deterministic material vocabulary
 */
export type LiveBakeTargetKind =
  | 'asset'
  | 'keyframe'
  | 'automation'
  | 'clip'
  | 'sidecar'
  | 'render-material';

/**
 * A single bake target descriptor.
 *
 * Specifies what kind of deterministic artifact a live sample stream
 * should be baked into and which reference to populate.
 */
export interface LiveBakeTarget {
  /** The kind of bake target. */
  readonly kind: LiveBakeTargetKind;
  /** Target reference (asset key, clip ID, param name, etc.). */
  readonly ref: string;
  /** Bake parameters (quantization, downsampling, format, etc.). */
  readonly params?: Record<string, unknown>;
}

/**
 * A partial bake selection — which source(s) and channel(s) to bake,
 * over what time/sample range, into which targets.
 */
export interface LiveBakeSelection {
  /** The source to bake from. */
  readonly sourceId: string;
  /** Specific channels to bake (all channels if omitted). */
  readonly channelIds?: readonly LiveChannelDescriptor[];
  /** Time range to bake (entire buffer if omitted). */
  readonly timeRange?: readonly [startMs: number, endMs: number];
  /** Frame range to bake (entire buffer if omitted). */
  readonly frameRange?: readonly [startFrame: number, endFrame: number];
  /** Sample index range to bake (entire buffer if omitted). */
  readonly sampleRange?: readonly [startIndex: number, endIndex: number];
  /** Discrete take ID to bake (all takes if omitted). */
  readonly takeId?: string;
  /** Targets to bake into. */
  readonly targets: readonly LiveBakeTarget[];
}

/**
 * Result of a live bake operation.
 */
export interface LiveBakeResult {
  /** The source that was baked. */
  readonly sourceId: string;
  /** Results for each bake target. */
  readonly targets: readonly {
    /** The bake target that was processed. */
    readonly target: LiveBakeTarget;
    /** The deterministic output reference (asset key, clip ID, etc.). */
    readonly outputRef: string;
    /** Diagnostics produced during this target's bake. */
    readonly diagnostics?: readonly LiveSourceDiagnostic[];
  }[];
  /** Overall bake diagnostics. */
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  /** Whether all targets baked successfully. */
  readonly success: boolean;
}

// --- Steering ---

/**
 * The kind of steering decision applied to a GenerationSession.
 *
 *   supersede — replace the current generation with new output
 *   fork      — create a parallel generation branch
 *   reject    — discard the generation and clean up
 */
export type SteeringDecisionKind = 'supersede' | 'fork' | 'reject';

/**
 * Whether a parameter can be changed on a live generation without starting a
 * separate branch.
 *
 *   hot     — compatible with in-place supersede when prior samples are replaced
 *   non-hot — requires a fork or explicit rejection
 */
export type SteeringParameterHotness = 'hot' | 'non-hot';

/**
 * Explicit policy for samples produced before a steering change.
 *
 * No GenerationSession live delivery may silently keep prior samples after a
 * steering change; the resolver must choose one of these policies.
 */
export type SteeringPriorSamplePolicy = 'replace' | 'fork' | 'retain' | 'discard';

/**
 * Structured provenance for a steered generation.
 */
export interface SteeringProvenance {
  /** Prompt text or prompt reference used by the producer. */
  readonly prompt: string;
  /** Model identifier used by the producer. */
  readonly model: string;
  /** Seed used by the producer. */
  readonly seed: string | number;
  /** Producer extension identifier, when available. */
  readonly producerExtensionId?: string;
  /** Additional opaque provenance tags. */
  readonly tags?: readonly string[];
}

/**
 * A requested steering parameter change.
 */
export interface SteeringParameterChange {
  /** Stable parameter path, for example `params.prompt` or `params.seed`. */
  readonly path: string;
  /** Value before steering, if known. */
  readonly previousValue?: unknown;
  /** Proposed value after steering. */
  readonly nextValue: unknown;
  /** Hotness classification for this parameter change. */
  readonly hotness?: SteeringParameterHotness;
}

/**
 * Lineage metadata for a steered generation.
 *
 * Carries enough provenance to trace the full steering chain:
 * generation index, steer hash, parent refs, producer version,
 * and optional provenance tags.
 */
export interface SteeringLineage {
  /** Monotonically increasing generation index. */
  readonly generationIndex: number;
  /** Hash of the steering decision that produced this generation. */
  readonly steerHash: string;
  /** Parent generation session IDs. */
  readonly parentRefs: readonly string[];
  /** Version of the producer extension at steering time. */
  readonly producerVersion: string;
  /** Structured prompt/model/seed provenance for this steering decision. */
  readonly provenance: SteeringProvenance;
  /** Opaque provenance tags. */
  readonly provenanceTags?: readonly string[];
}

/**
 * A steering decision applied to a GenerationSession.
 *
 * The steering resolver (Step 14) must always return an explicit
 * supersede, fork, or reject decision. GenerationSession live sample
 * delivery must not activate without complete steering lineage.
 */
export interface SteeringDecision {
  /** The kind of steering decision. */
  readonly kind: SteeringDecisionKind;
  /** The generation session this decision applies to. */
  readonly sessionId: string;
  /** Complete steering lineage. */
  readonly lineage: SteeringLineage;
  /** Human-readable reason for the decision. */
  readonly reason?: string;
  /** Replacement channel for supersede decisions. */
  readonly replacementChannelId?: LiveChannelDescriptor;
}

/**
 * Explicit live sample delivery metadata for a GenerationSession.
 *
 * Supplying this object asks the host to bridge preview samples from the
 * GenerationSession into provider-scoped live ring buffers. Activation is
 * gated by the Step 14 steering resolver: `steeringDecision` must be a complete
 * supersede or fork decision with lineage.
 */
export interface GenerationSessionLiveDelivery {
  /** Origin of this live session, e.g. an agent tool or SDK session helper. */
  readonly origin: string;
  /** Explicit steering decision from the live steering resolver. */
  readonly steeringDecision: SteeringDecision;
  /** Optional source ID; defaults to a host-generated generation-session source. */
  readonly sourceId?: string;
  /** Optional source label. */
  readonly sourceLabel?: string;
  /** Channel kind to open for delivered samples. */
  readonly channelKind?: LiveChannelKind;
  /** Channels already known to be active for this session. */
  readonly activeChannels?: readonly LiveChannelDescriptor[];
  /** Deterministic final output refs, when known before completion. */
  readonly finalRefs?: readonly string[];
  /** Deterministic baked output refs, when known before completion. */
  readonly bakedRefs?: readonly string[];
  /** Opaque activation metadata. */
  readonly metadata?: Record<string, unknown>;
}

// --- Binding resolution ---

/**
 * Resolution status of a live binding.
 *
 *   resolved   — source is active and binding is fully resolved
 *   unresolved — binding exists but source is not yet active
 *   orphaned   — binding's owning extension was disposed
 *   disposed   — binding's source was explicitly disposed
 *   missing    — binding references a source that was never registered
 */
export type BindingResolutionStatus =
  | 'resolved'
  | 'unresolved'
  | 'orphaned'
  | 'disposed'
  | 'missing';

/**
 * A persisted live binding on a timeline object (clip or effect).
 *
 * Live binding metadata is the only live state that persists in
 * timeline config. It survives provider unmount/disposal. Unresolved
 * metadata (including orphaned and disposed sources) blocks export
 * until explicit bake or remove.
 */
export interface LiveBinding {
  /** Unique binding identifier. */
  readonly bindingId: string;
  /** The source this binding references. */
  readonly sourceId: string;
  /** Channel descriptor, if a specific channel is bound. */
  readonly channelId?: LiveChannelDescriptor;
  /** Clip ID this binding is attached to, if any. */
  readonly targetClipId?: string;
  /** Effect ID this binding is attached to, if any. */
  readonly targetEffectId?: string;
  /** Parameter name on the target, if binding to a specific param. */
  readonly targetParamName?: string;
  /** Current resolution status. */
  readonly status: BindingResolutionStatus;
  /** Diagnostic explaining unresolved status, if any. */
  readonly diagnostic?: LiveSourceDiagnostic;
}

/**
 * The resolved state of a live binding.
 *
 * Produced by the binding resolver when a consumer requests
 * resolution of a specific binding.
 */
export interface LiveBindingResolution {
  /** The binding that was resolved. */
  readonly bindingId: string;
  /** Current resolution status. */
  readonly status: BindingResolutionStatus;
  /** The resolved live source, if found and active. */
  readonly source?: LiveSource;
  /** The resolved channel metadata, if available. */
  readonly channel?: LiveChannelMetadata;
  /** Diagnostic explaining why resolution failed, if applicable. */
  readonly diagnostic?: LiveSourceDiagnostic;
}

/**
 * Aggregate metadata about all live bindings in the current session.
 *
 * The pure binding scanner is the source of truth for unresolved
 * live references. It produces this aggregate to power export guard
 * and UI diagnostics.
 */
export interface LiveBindingMetadata {
  /** All live bindings currently persisted on timeline objects. */
  readonly bindings: readonly LiveBinding[];
  /** Count of unresolved bindings. */
  readonly unresolvedCount: number;
  /** Count of orphaned bindings (extension disposed). */
  readonly orphanedCount: number;
  /** Count of disposed bindings (source explicitly disposed). */
  readonly disposedCount: number;
}

// --- Live sessions service ---

/**
 * Live sessions service available as `ctx.creative.sessions` during activate().
 *
 * Provides provider-scoped live source lifecycle management, channel
 * operations, sample delivery, bake, binding resolution, and steering.
 *
 * All live data is ephemeral runtime state scoped to the current
 * provider mount. Only live binding metadata persists in timeline config.
 */
export interface LiveSessionsService {
  // ── Source lifecycle ──────────────────────────────────────────────

  /**
   * Register a new live source.
   * Returns a DisposeHandle that disposes the source when called.
   */
  registerSource(source: Omit<LiveSource, 'status' | 'diagnostics'>): DisposeHandle;

  /**
   * Get a registered live source by ID.
   * Returns undefined if the source is not found.
   */
  getSource(sourceId: string): LiveSource | undefined;

  /**
   * List all registered live sources.
   */
  listSources(): readonly LiveSource[];

  // ── Channel operations ────────────────────────────────────────────

  /**
   * Open a typed channel on a source.
   * Returns a LiveChannelDescriptor that is string-compatible.
   */
  openChannel(
    sourceId: string,
    kind: LiveChannelKind,
    metadata?: Record<string, unknown>,
  ): LiveChannelDescriptor;

  /**
   * Close a live channel.
   * Idempotent — safe to call on already-closed channels.
   */
  closeChannel(channelId: LiveChannelDescriptor): void;

  /**
   * Get rich metadata for a channel.
   * Returns undefined if the channel is not found.
   */
  getChannelMetadata(channelId: LiveChannelDescriptor): LiveChannelMetadata | undefined;

  // ── Sample delivery ───────────────────────────────────────────────

  /**
   * Push a sample frame into a channel's ring buffer.
   * Samples are read synchronously by render paths.
   */
  pushSample(channelId: LiveChannelDescriptor, frame: LiveSampleFrame): void;

  /**
   * Subscribe to samples on a channel.
   * The listener receives every sample pushed to the channel.
   * Returns a DisposeHandle for unsubscription.
   */
  subscribeSamples(
    channelId: LiveChannelDescriptor,
    listener: (sample: LiveSample) => void,
  ): DisposeHandle;

  // ── Bake ──────────────────────────────────────────────────────────

  /**
   * Bake live samples into deterministic timeline artifacts.
   *
   * Bake converts live data into asset registry entries, keyframes,
   * automation clips, standard clips, metadata sidecars, or RenderMaterial
   * refs. Failed bakes leave live sources unchanged.
   *
   * This is one of the two bridges from live runtime to deterministic
   * timeline state (the other being removeLiveBindings).
   */
  bake(selection: LiveBakeSelection): LiveBakeResult;

  /**
   * Remove live bindings for a source.
   *
   * After removal, the source's bindings are cleared from timeline
   * metadata, unblocking export. This is the second bridge from live
   * runtime to deterministic timeline state (alongside bake).
   */
  removeLiveBindings(sourceId: string): void;

  // ── Binding resolution ────────────────────────────────────────────

  /**
   * Resolve a single live binding to its current status and source.
   */
  resolveBinding(bindingId: string): LiveBindingResolution;

  /**
   * Get aggregate live binding metadata.
   * The pure binding scanner produces this aggregate, which is the
   * source of truth for unresolved live references.
   */
  getBindingMetadata(): LiveBindingMetadata;

  // ── Steering ──────────────────────────────────────────────────────

  /**
   * Apply a steering decision to a GenerationSession.
   *
   * The steering resolver must always return an explicit supersede,
   * fork, or reject. GenerationSession live sample delivery must not
   * activate without complete steering lineage.
   */
  applySteeringDecision(decision: SteeringDecision): void;

  // ── Diagnostics ───────────────────────────────────────────────────

  /**
   * Get diagnostics for all sources or a specific source.
   */
  getDiagnostics(sourceId?: string): readonly LiveSourceDiagnostic[];
}

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

/** Posture of a dependency: required blocks activation, optional degrades. */
export type DependencyPosture = 'required' | 'optional';

/** A typed dependency declared by an extension. */
export interface ExtensionDependency {
  /** Extension ID this dependency references. */
  extensionId: string;
  /** Semver range (e.g. "^1.2.0", ">=2.0.0 <3.0.0"). */
  versionRange?: string;
  /** Specific contribution IDs required from the dependency. */
  contributionIds?: readonly string[];
  /** Whether this dependency was originally declared as optional. */
  optional?: boolean;
  /** Dependency posture: required blocks activation, optional allows degraded activation. */
  posture?: DependencyPosture;
}

/** Settings schema descriptor with version for migration tracking. */
export interface ExtensionSettingsSchema {
  /** Monotonic version number; increments when the settings shape changes. */
  version: number;
  /** Optional JSON Schema-like shape descriptor (subset). */
  schema?: Record<string, unknown>;
}

/** Supported integrity algorithms. */
export type IntegrityAlgorithm = 'sha256';

/** An SRI-style integrity hash. */
export interface IntegrityHash {
  algorithm: IntegrityAlgorithm;
  /** Base64-encoded hash value (without algorithm prefix). */
  value: string;
}

/** Kinds of migration hooks an extension may declare. */
export type MigrationHookKind = 'settings' | 'contribution' | 'manifest';

/** A typed migration declaration for extension upgrades. */
export interface MigrationDeclaration {
  kind: MigrationHookKind;
  /** Semver of the source version being migrated from. */
  fromVersion: string;
  /** Semver of the target version being migrated to. */
  toVersion: string;
  /** Handler identifier (module export name or inline function name). */
  handler?: string;
  /** Human-readable description of the migration. */
  description?: string;
}

/** Metadata recorded when an extension is installed as a trusted bundle. */
export interface InstalledExtensionMetadata {
  extensionId: ExtensionId;
  version: string;
  apiVersion?: number;
  /** Required: SHA-256 SRI integrity of the installed bundle. */
  integrity: IntegrityHash;
  /** ISO 8601 timestamp of installation. */
  installedAt?: string;
  /** Whether the extension is currently enabled. */
  enabled: boolean;
  /** Settings schema version at install time. */
  settingsSchemaVersion?: number;
  /** Resolved dependency graph at install time. */
  dependencies?: readonly ExtensionDependency[];
  /** Stored extension-scoped settings keyed by key. */
  settings?: Record<string, unknown>;
  /** Optional publisher identity for installed extensions. */
  publisher?: string;
  /** Optional SPDX license identifier. */
  license?: string;
  /** Optional icon URL or data URI. */
  icon?: string;
}

/** A full installed extension package: manifest + bundle + tracked metadata. */
export interface InstalledExtensionPackage {
  metadata: InstalledExtensionMetadata;
  manifest: ExtensionManifest;
  /** Raw trusted bundle source (bundle.mjs content). */
  bundleContent: string;
}

/** Validation mode: 'dev' produces warnings, 'installed' produces strict errors. */
export type ManifestValidationMode = 'dev' | 'installed';

/** Result of validating an extension manifest. */
export interface ManifestValidationResult {
  /** True when no blocking errors exist. */
  valid: boolean;
  /** Blocking diagnostics (strict errors in installed mode). */
  errors: readonly ExtensionDiagnostic[];
  /** Non-blocking diagnostics (warnings in dev mode, supplemental in installed mode). */
  warnings: readonly ExtensionDiagnostic[];
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

/** Settings service: localStorage-backed key-value store scoped per extension. */
export interface ExtensionSettingsService {
  get<T = unknown>(key: string): T | undefined;
  set<T = unknown>(key: string, value: T): void;
  delete(key: string): void;
  keys(): readonly string[];
  /**
   * Subscribe to settings change notifications.
   *
   * The listener is called after every successful `set()` or `delete()`.
   * Invalid writes blocked by Ajv validation do NOT trigger notifications.
   * Returns a {@link DisposeHandle} to unsubscribe.
   */
  subscribe(listener: () => void): DisposeHandle;
}

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

/** i18n service: minimal t() scaffolding with namespace fallback. */
export interface ExtensionI18nService {
  t(key: string, replacements?: Record<string, string | number>): string;
}

/** Diagnostics service: emit structured diagnostics from extension code. */
export interface ExtensionDiagnosticsService {
  /**
   * Report a diagnostic.  `extensionId` and `source` are owned by the
   * extension lifecycle — the host overwrites any caller-provided values
   * with the authoritative extension ID and {@link DIAGNOSTIC_SOURCE_EXTENSION}.
   */
  report(diagnostic: Omit<ExtensionDiagnostic, 'extensionId' | 'source'>): void;
  /** All diagnostics emitted by this extension (live snapshot). */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

/** Chrome service: host-visible toast/progress/subscribe scaffolding. */
export interface ExtensionChromeService {
  toast(message: string, severity?: DiagnosticSeverity): void;
  progress(percent: number, label?: string): void;
  subscribe<E extends ChromeEvent>(
    event: E,
    handler: (payload: ChromeEventPayload<E>) => void,
  ): DisposeHandle;
  /**
   * Focus an element matching the CSS selector within the editor shell root.
   *
   * Scoped to the editor shell root: only descendants of the shell root are
   * considered valid targets.  Emits diagnostics when:
   * - No shell root is mounted (`chrome/focus-no-shell`)
   * - The selector matches an element outside the shell root, e.g. a portal
   *   target (`chrome/focus-out-of-shell`)
   * - The selector does not match any element (`chrome/focus-missing-selector`)
   *
   * Safe to call from extension code at any time.
   */
  focus(selector: string): void;
  /**
   * Announce a message to assistive technology via an aria-live region
   * within the editor shell root.
   *
   * Creates a `.sr-only` container with `aria-live` and `aria-atomic`
   * inside the shell root on first call.  Subsequent calls update the
   * text content so screen readers re-announce.  If no shell root is
   * mounted the message is logged to the console as a fallback.
   *
   * @param message     The text to announce.
   * @param politeness  `'polite'` (default) or `'assertive'`.
   */
  announce(message: string, politeness?: 'polite' | 'assertive'): void;
}

// ---------------------------------------------------------------------------
// Chrome events
// ---------------------------------------------------------------------------

export type ChromeEvent =
  | 'toast'
  | 'progress'
  | 'save'
  | 'renderStatus';

export interface ChromeToastPayload {
  message: string;
  severity: DiagnosticSeverity;
}

export interface ChromeProgressPayload {
  percent: number;
  label?: string;
}

export interface ChromeSavePayload {
  status: 'started' | 'completed' | 'failed';
  error?: string;
}

export interface ChromeRenderStatusPayload {
  status: 'idle' | 'rendering' | 'completed' | 'failed';
  error?: string;
}

export type ChromeEventPayload<E extends ChromeEvent> =
  E extends 'toast' ? ChromeToastPayload :
  E extends 'progress' ? ChromeProgressPayload :
  E extends 'save' ? ChromeSavePayload :
  E extends 'renderStatus' ? ChromeRenderStatusPayload :
  never;

// ---------------------------------------------------------------------------
// Creative context (reserved stubs)
// ---------------------------------------------------------------------------

/** Reserved creative context members — each becomes live in its owning milestone. */
export interface CreativeContext {
  readonly project: unknown;
  /** Public mutation surface for atomic timeline operations (M3). */
  readonly timeline: TimelineOps;
  /** Read-only snapshot projection of the current timeline state (M3). */
  readonly reader: TimelineReader;
  /** Provider-scoped proposal lifecycle manager (M3). */
  readonly proposals: ProposalRuntime;
  /** Read-only asset metadata surface (M6). */
  readonly assets: AssetReadSurface;
  /** Read-only material metadata surface (M6). */
  readonly materials: MaterialReadSurface;
  /** Live data sessions service for source/channel/bake/steering operations (M11). */
  readonly sessions: LiveSessionsService;
  /** Export service for registering output format handlers (M6). */
  readonly export: ExportService;
  readonly stage: unknown;
  readonly writing: unknown;
}

/** The milestone that activates each creative context member. */
export const CREATIVE_MEMBER_MILESTONE: Record<keyof CreativeContext, string> = {
  project: 'M2',
  timeline: 'M3',
  reader: 'M3',
  proposals: 'M3',
  assets: 'M6',
  materials: 'M6',
  sessions: 'M11',
  export: 'M2',
  stage: 'M5',
  writing: 'M2',
};

/**
 * Error thrown when accessing a reserved creative context member
 * that is not yet implemented in the current milestone.
 */
export class ExtensionNotImplementedError extends Error {
  readonly feature: string;
  readonly milestone: string;

  constructor(feature: string, milestone: string) {
    super(`ctx.creative.${feature} is not implemented until ${milestone}.`);
    this.name = 'ExtensionNotImplementedError';
    this.feature = feature;
    this.milestone = milestone;
  }
}

/** Create a creative context object whose every member throws on access. */
export function createCreativeContextStubs(): CreativeContext {
  const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as (keyof CreativeContext)[];

  const stub: Record<string, unknown> = {};
  for (const member of members) {
    const milestone = CREATIVE_MEMBER_MILESTONE[member];
    Object.defineProperty(stub, member, {
      get(): never {
        throw new ExtensionNotImplementedError(member, milestone);
      },
      enumerable: true,
      configurable: false,
    });
  }

  return Object.freeze(stub) as unknown as CreativeContext;
}

/**
 * Create a CreativeContext with optional live overrides.
 *
 * Members present in `overrides` are used directly; all other members
 * retain the default throwing-stub behavior from createCreativeContextStubs().
 * This lets host providers inject live timeline services for extensions
 * running inside a mounted video-editor context while keeping stubs for
 * unmounted or non-editor contexts.
 */
export function createCreativeContext(
  overrides?: Partial<CreativeContext>,
): CreativeContext {
  if (!overrides) {
    return createCreativeContextStubs();
  }

  const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as (keyof CreativeContext)[];
  const merged: Record<string, unknown> = {};

  for (const member of members) {
    if (member in overrides) {
      Object.defineProperty(merged, member, {
        value: (overrides as Record<string, unknown>)[member],
        enumerable: true,
        writable: false,
        configurable: false,
      });
    } else {
      const milestone = CREATIVE_MEMBER_MILESTONE[member];
      Object.defineProperty(merged, member, {
        get(): never {
          throw new ExtensionNotImplementedError(member, milestone);
        },
        enumerable: true,
        configurable: false,
      });
    }
  }

  return Object.freeze(merged) as unknown as CreativeContext;
}

// ---------------------------------------------------------------------------
// M4: Command registration service
// ---------------------------------------------------------------------------

/**
 * Command registration service available as `ctx.commands` during activate().
 *
 * Commands must have a matching `command` contribution in the extension
 * manifest.  Handlers are registered imperatively via `registerCommand()`
 * and the returned DisposeHandle unregisters them on dispose.
 */
export interface ExtensionCommandService {
  /**
   * Register a command handler imperatively during activate().
   *
   * The `commandId` must match the `command` field of a `CommandContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the handler when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerCommand(
    commandId: string,
    handler: CommandHandler,
    options?: CommandRegistrationOptions,
  ): DisposeHandle;
}

// ---------------------------------------------------------------------------
// M7: Effect registration service
// ---------------------------------------------------------------------------

/**
 * A trusted local component registered by an extension as an effect.
 *
 * Component effects execute in the browser preview and are blocked from
 * export contexts unless the owning contribution declares stronger capability.
 */
export type EffectComponent = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * A parameter definition for effect parameter schemas.
 *
 * This lightweight SDK type mirrors the video-editor internal ParameterDefinition
 * shape so extensions can declare parameter contracts at registration time.
 * The video-editor runtime validates these at registration time and coerces
 * parameter values at render time.
 */
export interface EffectParameterDefinition {
  /** Unique parameter name (used as the key in params). */
  name: string;
  /** Human-readable label for UI controls. */
  label: string;
  /** Description shown in tooltips / inspector. */
  description: string;
  /** Parameter type determining the control and coercion rules. */
  type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
  /** Default value when no override is provided. */
  default?: number | string | boolean | Record<string, unknown>;
  /** Minimum value (number type only). */
  min?: number;
  /** Maximum value (number type only). */
  max?: number;
  /** Step increment (number type only). */
  step?: number;
  /** Options for select-type parameters. */
  options?: readonly { label: string; value: string }[];
}

/** Ordered array of parameter definitions. */
export type EffectParameterSchema = readonly EffectParameterDefinition[];

/** Options for imperative effect registration via ctx.effects.registerComponent(). */
export interface EffectRegistrationOptions {
  /** Override label for the effect picker / UI. */
  label?: string;
  /**
   * Parameter schema for this effect.
   *
   * When provided, the schema is validated at registration time. An invalid
   * schema produces `status: 'error'` on the registry record with diagnostics
   * but does not prevent the component from rendering (render-time parameter
   * coercion continues to work for already-applied legacy data).
   */
  parameterSchema?: EffectParameterSchema;
}

/**
 * Effect registration service available as `ctx.effects` during activate().
 *
 * Trusted component effects must have a matching {@link EffectContribution}
 * in the extension manifest.  Components are registered imperatively via
 * `registerComponent()` and the returned DisposeHandle unregisters them on
 * dispose.
 */
export interface EffectRegistrationService {
  /**
   * Register a trusted local component as an effect.
   *
   * The `effectId` must match the `effectId` field of an `EffectContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the component when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerComponent(
    effectId: string,
    component: EffectComponent,
    options?: EffectRegistrationOptions,
  ): DisposeHandle;
}

// ---------------------------------------------------------------------------
// M8: Transition registration service
// ---------------------------------------------------------------------------

/**
 * A trusted local renderer registered by an extension as a transition.
 *
 * Transition renderers execute in the browser preview and are blocked from
 * export contexts unless the owning contribution declares stronger capability.
 */
export type TransitionRenderer = Record<string, unknown> | ((...args: unknown[]) => unknown);

/**
 * A parameter definition for transition parameter schemas.
 *
 * This lightweight SDK type mirrors the video-editor internal ParameterDefinition
 * shape so extensions can declare parameter contracts at registration time.
 * The video-editor runtime validates these at registration time and coerces
 * parameter values at render time.
 */
export interface TransitionParameterDefinition {
  /** Unique parameter name (used as the key in params). */
  name: string;
  /** Human-readable label for UI controls. */
  label: string;
  /** Description shown in tooltips / inspector. */
  description: string;
  /** Parameter type determining the control and coercion rules. */
  type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
  /** Default value when no override is provided. */
  default?: number | string | boolean | Record<string, unknown>;
  /** Minimum value (number type only). */
  min?: number;
  /** Maximum value (number type only). */
  max?: number;
  /** Step increment (number type only). */
  step?: number;
  /** Options for select-type parameters. */
  options?: readonly { label: string; value: string }[];
}

/** Ordered array of transition parameter definitions. */
export type TransitionParameterSchema = readonly TransitionParameterDefinition[];

/** Options for imperative transition registration via ctx.transitions.registerRenderer(). */
export interface TransitionRegistrationOptions {
  /** Override label for the transition picker / UI. */
  label?: string;
  /**
   * Parameter schema for this transition.
   *
   * When provided, the schema is validated at registration time. An invalid
   * schema produces `status: 'error'` on the registry record with diagnostics
   * but does not prevent the renderer from rendering (render-time parameter
   * coercion continues to work for already-applied legacy data).
   */
  parameterSchema?: TransitionParameterSchema;
}

/**
 * Transition registration service available as `ctx.transitions` during activate().
 *
 * Trusted component transitions must have a matching {@link TransitionContribution}
 * in the extension manifest.  Renderers are registered imperatively via
 * `registerRenderer()` and the returned DisposeHandle unregisters them on
 * dispose.
 */
export interface TransitionRegistrationService {
  /**
   * Register a trusted local renderer as a transition.
   *
   * The `transitionId` must match the `transitionId` field of a `TransitionContribution`
   * declared by this extension in its manifest.
   *
   * Returns a DisposeHandle that unregisters the renderer when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerRenderer(
    transitionId: string,
    renderer: TransitionRenderer,
    options?: TransitionRegistrationOptions,
  ): DisposeHandle;
}

/**
 * The context passed to an extension during activation.
 * Exposes only approved M1 members; no raw DataProvider, applyEdit,
 * timeline store, or internal mutation escape hatch.
 */
export interface ExtensionContext {
  /** Current API version (1 in M1). */
  readonly apiVersion: number;
  /** Readonly extension metadata. */
  readonly extension: {
    readonly id: ExtensionId;
    readonly version: string;
    readonly label: string;
    readonly description?: string;
    readonly manifest: Readonly<ExtensionManifest>;
  };
  /** Host chrome services. */
  readonly chrome: ExtensionChromeService;
  /** Scoped services. */
  readonly services: {
    readonly settings: ExtensionSettingsService;
    readonly i18n: ExtensionI18nService;
    readonly diagnostics: ExtensionDiagnosticsService;
  };
  /** Reserved creative context stubs — throw typed \"not implemented until Mx\". */
  readonly creative: CreativeContext;
  /** M4: Command registration service for imperative handler binding. */
  readonly commands: ExtensionCommandService;
  /** M7: Effect registration service for trusted component effects. */
  readonly effects: EffectRegistrationService;
  /** M8: Transition registration service for trusted component transitions. */
  readonly transitions: TransitionRegistrationService;
  /** M9: Clip-type registration service for contributed clip types. */
  readonly clipTypes: ClipTypeRegistrationService;
  /** M13: Shader registration service for dedicated WebGL shader passes. */
  readonly shaders: ShaderRegistrationService;
  /** M10: Agent tool registration service for host-mediated agent tools. */
  readonly agentTools: AgentToolRegistrationService;
}

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

/**
 * Symbol key for host-service disposal attached to every ExtensionContext.
 * The runtime lifecycle calls this during deactivation/disposal to clean up
 * localStorage keys, chrome event subscribers, and any future host-owned
 * service state scoped to this extension activation.
 */
export const CONTEXT_DISPOSE_SYMBOL: unique symbol = Symbol('reigh.extensionContext.dispose');

/**
 * Dispose host-owned services (settings localStorage, chrome subscriptions)
 * attached to an ExtensionContext. Safe to call on contexts that lack the
 * dispose function or on already-disposed contexts.
 */
export function disposeExtensionContextServices(ctx: ExtensionContext): void {
  const dispose = (ctx as unknown as Record<string | symbol, unknown>)[CONTEXT_DISPOSE_SYMBOL];
  if (typeof dispose === 'function') {
    try {
      (dispose as () => void)();
    } catch {
      // dispose functions are internally safe, but double-guard
    }
  }
}

// ---------------------------------------------------------------------------
// Extension lifecycle
// ---------------------------------------------------------------------------

/** An extension's activate function. */
export type ExtensionActivateFn = (ctx: ExtensionContext) => DisposeHandle | void;

/** The public extension shape returned by defineExtension(). */
export interface ReighExtension {
  readonly manifest: Readonly<ExtensionManifest>;
  readonly activate?: ExtensionActivateFn;
}

// ---------------------------------------------------------------------------
// defineExtension()
// ---------------------------------------------------------------------------

/** Options passed to defineExtension(). */
export interface DefineExtensionOptions {
  manifest: ExtensionManifest;
  activate?: ExtensionActivateFn;
}

function freezeManifestValue<T>(value: T): T {
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer) {
    return value;
  }
  if (Array.isArray(value)) {
    return Object.freeze(value.map((item) => freezeManifestValue(item))) as T;
  }
  if (value && typeof value === 'object') {
    const frozenEntries = Object.entries(value as Record<string, unknown>).map(
      ([key, entry]) => [key, freezeManifestValue(entry)],
    );
    return Object.freeze(Object.fromEntries(frozenEntries)) as T;
  }
  return value;
}

/**
 * Create a frozen ReighExtension from a manifest and optional activate function.
 * Validates the extension ID and contribution IDs, and preserves literal IDs
 * through the returned object.
 */
export function defineExtension(options: DefineExtensionOptions): ReighExtension {
  const { manifest, activate } = options;

  // Validate extension ID
  const idErrors = validateExtensionId(manifest.id);
  if (idErrors.length > 0) {
    throw new Error(`Invalid extension ID "${manifest.id}": ${idErrors.join('; ')}`);
  }

  // Validate contribution IDs for uniqueness
  if (manifest.contributions && manifest.contributions.length > 0) {
    const seen = new Set<string>();
    for (const contribution of manifest.contributions) {
      const cErrors = validateContributionId(contribution.id);
      if (cErrors.length > 0) {
        throw new Error(
          `Invalid contribution ID "${contribution.id}" in extension "${manifest.id}": ${cErrors.join('; ')}`,
        );
      }
      if (seen.has(contribution.id)) {
        throw new Error(
          `Duplicate contribution ID "${contribution.id}" in extension "${manifest.id}"`,
        );
      }
      seen.add(contribution.id);
    }
  }

  // Freeze the manifest deeply so literal IDs are preserved and the shape is immutable
  const frozenManifest: ExtensionManifest = Object.freeze({
    ...manifest,
    contributions: manifest.contributions ? freezeManifestValue(manifest.contributions) : undefined,
    permissions: manifest.permissions ? freezeManifestValue(manifest.permissions) : undefined,
    processes: manifest.processes ? freezeManifestValue(manifest.processes) : undefined,
    dependsOn: manifest.dependsOn ? freezeManifestValue(manifest.dependsOn) : undefined,
    migrations: manifest.migrations ? freezeManifestValue(manifest.migrations) : undefined,
    settingsDefaults: manifest.settingsDefaults ? freezeManifestValue(manifest.settingsDefaults) : undefined,
    settingsSchema: manifest.settingsSchema ? freezeManifestValue(manifest.settingsSchema) : undefined,
    messages: manifest.messages ? freezeManifestValue(manifest.messages) : undefined,
  });

  const extension: ReighExtension = Object.freeze({
    manifest: frozenManifest,
    activate,
  });

  return extension;
}

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

/**
 * The earliest milestone that activates each contribution kind.
 * Any kind not in this map is treated as not-yet-bridged.
 */
export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> = {
  slot: 'M1',
  dialog: 'M1',
  panel: 'M1',
  inspectorSection: 'M1',
  timelineOverlay: 'M2',
  command: 'M4',
  keybinding: 'M4',
  contextMenuItem: 'M4',
  // M6: parser, output format, search provider, metadata facet, asset detail section
  parser: 'M6',
  outputFormat: 'M6',
  searchProvider: 'M6',
  metadataFacet: 'M6',
  assetDetailSection: 'M6',
  process: 'M12',
  effect: 'M7',
  transition: 'M8',
  // M9: clip type dispatch and basic keyframes
  clipType: 'M9',
  shader: 'M13',
  automation: 'M9',
  agentTool: 'M10',
  agent: 'M10',
};

/**
 * Check whether a contribution kind is bridged in the current runtime.
 * Returns the milestone name if NOT bridged, or null if it is bridged.
 */
export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (!milestone) return 'unknown';

  // M1 / M2 are fully bridged.
  if (milestone === 'M1' || milestone === 'M2') return null;

  // M4: command, keybinding, and contextMenuItem are bridged.
  // Other M4 kinds remain inactive (none exist as of M6).
  if (
    milestone === 'M4' &&
    (kind === 'command' || kind === 'keybinding' || kind === 'contextMenuItem')
  ) {
    return null;
  }

  // M6: parser, metadataFacet, and assetDetailSection are M6-active.
  // outputFormat and searchProvider are typed but execution is reserved
  // (declarable, not yet bridged for runtime).
  if (
    milestone === 'M6' &&
    (kind === 'parser' || kind === 'metadataFacet' || kind === 'assetDetailSection')
  ) {
    return null;
  }

  // M7: effect is bridged.
  if (milestone === 'M7' && kind === 'effect') {
    return null;
  }

  // M8: transition is bridged.
  if (milestone === 'M8' && kind === 'transition') {
    return null;
  }

  // M9: clipType and automation are bridged.
  if (milestone === 'M9' && (kind === 'clipType' || kind === 'automation')) {
    return null;
  }

  // M10: agentTool and agent are bridged.
  if (milestone === 'M10' && (kind === 'agentTool' || kind === 'agent')) {
    return null;
  }

  // M13: shader is bridged as a dedicated WebGL contribution kind.
  if (milestone === 'M13' && kind === 'shader') {
    return null;
  }

  return milestone;
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
  RenderArtifactSidecarKind,
  RenderMaterial,
  RenderMaterialRef,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts.ts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderBlockerReason,
  RenderRoute,
} from '@/sdk/video/rendering/renderability.ts';
import type { ShaderMaterializerRequirementScope } from '@/sdk/video/rendering/capabilities.ts';
import { shaderMissingMaterializerBlockerMessage } from '@/sdk/video/rendering/capabilities.ts';
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
  ExportService,
  MaterialReadSurface,
  MetadataFacetValueKind,
} from '@/sdk/video/assets/metadata.ts';

// ---------------------------------------------------------------------------
// M12: Planner requirement contracts — capability requirements, source refs,
// route-fit metadata, capability versioning, and integration capabilities
// ---------------------------------------------------------------------------

/**
 * M12: Version descriptor for a capability or contribution declaration.
 *
 * Carries a semver version and declaration provenance so planners can
 * detect version conflicts and stale registrations without importing
 * registry internals.
 */
export interface CapabilityVersion {
  /** Semantic version string (e.g. "1.0.0"). */
  readonly semver: string;
  /** Extension that declared this version, when applicable. */
  readonly declaredBy?: string;
  /** Contribution that declared this version, when applicable. */
  readonly contributionId?: string;
}

/**
 * M12: Source reference for a capability requirement.
 *
 * Identifies where a capability requirement originates so planners
 * can attribute blockers and findings to the right extension,
 * registry, or built-in source.
 */
export interface CapabilitySourceRef {
  /** The kind of source that produced this capability. */
  readonly source: 'extension' | 'built-in' | 'registry' | 'manifest' | 'provider';
  /** Extension ID, when the source is an extension. */
  readonly extensionId?: string;
  /** Contribution ID, when the source is a specific contribution. */
  readonly contributionId?: string;
  /** Version of the capability declaration, when known. */
  readonly version?: CapabilityVersion;
}

/**
 * M12: Route-fit metadata describing how well a capability maps to a route.
 *
 * Planners use route-fit metadata to decide whether a contribution can
 * authoritatively execute on a given route, or whether it must fall back
 * or block.
 */
export interface RouteFitMetadata {
  /** The route this fit metadata applies to. */
  readonly route: RenderRoute;
  /** Whether the capability supports, blocks, degrades, or is unknown for this route. */
  readonly fit: 'supported' | 'blocked' | 'degraded' | 'unknown';
  /** Reason for the fit, when not 'supported'. */
  readonly reason?: RenderBlockerReason;
  /** Human-readable message explaining the fit. */
  readonly message?: string;
}

/**
 * M12: A single capability requirement produced by the planner.
 *
 * Each CapabilityRequirement describes what a contribution needs for a
 * specific route, its determinism posture, version, source provenance,
 * and any findings discovered during planning. This is the primary
 * record consumed by TimelineReader capability inspection and
 * renderPlanner aggregation.
 */
export interface CapabilityRequirement {
  /** Stable, unique identifier for this requirement. */
  readonly id: string;
  /** Where this requirement originates from. */
  readonly sourceRef: CapabilitySourceRef;
  /** The route this requirement applies to. */
  readonly route: RenderRoute;
  /** Required capabilities for this route (e.g. 'browser-export', 'worker-export'). */
  readonly requiredCapabilities: readonly string[];
  /** Determinism posture for this requirement. */
  readonly determinism: DeterminismStatus;
  /** Route-fit metadata describing how well this requirement fits the route. */
  readonly routeFit?: RouteFitMetadata;
  /** Version of the capability declaration, when known. */
  readonly version?: CapabilityVersion;
  /** Capability findings produced during planning. */
  readonly findings?: readonly CapabilityFinding[];
  /** Whether this requirement is a blocker for its route. */
  readonly blocking?: boolean;
}

/**
 * M12: Minimal integration capabilities consumed by TimelineReader and
 * renderPlanner.
 *
 * Aggregates capability requirements, source references, and route
 * summaries so planners can consume a single normalized capabilities
 * record without importing registry internals or provider state.
 */
export interface IntegrationCapabilities {
  /** Extension that owns these capabilities, when scoped to a single extension. */
  readonly extensionId?: string;
  /** Contribution that owns these capabilities, when scoped to a single contribution. */
  readonly contributionId?: string;
  /** Routes covered by these capabilities. */
  readonly routes: readonly RenderRoute[];
  /** Aggregate determinism posture across all capabilities. */
  readonly determinism: DeterminismStatus;
  /** Individual capability requirements collected during planning. */
  readonly capabilityRequirements: readonly CapabilityRequirement[];
  /** Source references for all capabilities in this integration record. */
  readonly sourceRefs: readonly CapabilitySourceRef[];
  /** Whether all routes are fully supported (no blockers). */
  readonly fullySupported: boolean;
  /** Whether any route is blocked. */
  readonly anyBlocked: boolean;
}

// ---------------------------------------------------------------------------
// M12: Artifact manifest, sidecar, sampling, and process roundtrip contracts
// ---------------------------------------------------------------------------

export type SamplingStrategy =
  | 'whole-timeline'
  | 'clip-slices'
  | 'frame-extracts'
  | 'thumbnail-grid'
  | 'audio-windows'
  | 'render-groups';

export interface SamplingSourceRef {
  readonly kind: 'timeline' | 'clip' | 'track' | 'asset' | 'material' | 'render-group';
  readonly id: string;
  readonly clipId?: string;
  readonly trackId?: string;
  readonly assetKey?: string;
  readonly materialRefId?: string;
  readonly renderGroupId?: string;
}

export interface SamplingRange {
  readonly startFrame?: number;
  readonly endFrame?: number;
  readonly startSeconds?: number;
  readonly endSeconds?: number;
  readonly startSample?: number;
  readonly endSample?: number;
}

export type SamplingAttachmentKind = 'label' | 'caption' | 'cue' | 'provenance' | 'metadata';

export interface SamplingAttachmentRule {
  readonly kind: SamplingAttachmentKind;
  readonly fieldPath?: string;
  readonly sidecarKind?: RenderArtifactSidecarKind;
  readonly required?: boolean;
}

/** M12: Declarative sampling request consumed by planners and export shells. */
export interface SamplingConfig {
  readonly id?: string;
  readonly strategy: SamplingStrategy;
  readonly sources: readonly SamplingSourceRef[];
  readonly range?: SamplingRange;
  readonly fps?: number;
  readonly sampleRate?: number;
  readonly resolution?: string;
  readonly sliceClips?: boolean;
  readonly attachments?: readonly SamplingAttachmentRule[];
  readonly includeLabels?: boolean;
  readonly includeCaptions?: boolean;
  readonly includeProvenance?: boolean;
}

export interface SamplingResultItem {
  readonly id: string;
  readonly sourceRef: SamplingSourceRef;
  readonly range?: SamplingRange;
  readonly frame?: number;
  readonly timestampSeconds?: number;
  readonly artifactId?: string;
  readonly manifestEntryId?: string;
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
}

/** M12: Result vocabulary for dry-runs and dataset/show-control exports. */
export interface SamplingResult {
  readonly configId?: string;
  readonly items: readonly SamplingResultItem[];
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly manifestRefs?: readonly string[];
  readonly diagnostics?: readonly CapabilityFinding[];
}

export interface ProcessRoundtripRequest {
  readonly id: string;
  readonly processId: string;
  readonly operationId: string;
  readonly inputMaterialRefs?: readonly RenderMaterialRef[];
  readonly inputArtifactRefs?: readonly RenderArtifact[];
  readonly params?: Record<string, unknown>;
  readonly frameRange?: SamplingRange;
  readonly renderGroupId?: string;
  readonly passNames?: readonly string[];
  readonly sampling?: SamplingConfig;
}

export type ProcessRoundtripAction =
  | 'insert-as-clip'
  | 'replace-clip'
  | 'attach-to-clip'
  | 'download-sidecar'
  | 'discard'
  | 'create-proposal';

export interface ProcessRoundtripResult {
  readonly requestId: string;
  readonly processId: string;
  readonly operationId: string;
  readonly status: 'completed' | 'failed' | 'cancelled';
  readonly returnedMaterials: readonly RenderMaterial[];
  readonly artifacts?: readonly RenderArtifact[];
  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics?: readonly CapabilityFinding[];
  readonly logs?: readonly ProcessLogSummary[];
  readonly progress?: ProcessProgressEvent;
  readonly availableActions?: readonly ProcessRoundtripAction[];
  readonly metadata?: Record<string, unknown>;
}

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
// M3 / M12: TimelineSnapshot, summary types, TimelineReader — now in
// src/sdk/video/timeline/reader.ts (re-exported above)
// ---------------------------------------------------------------------------
// M12: getCapabilityRequirements — provider-free capability inspection
// (TimelineSnapshot, summary types, and TimelineReader are now defined in
// src/sdk/video/timeline/reader.ts and re-exported above.)
// ---------------------------------------------------------------------------

/**
 * M12: Derive capability requirements from a TimelineSnapshot.
 *
 * Inspects clip types, effects, transitions, live bindings, and material
 * refs present in the snapshot and emits {@link CapabilityRequirement}
 * records without importing provider stores, raw timeline rows, or
 * mutation APIs.
 *
 * The returned requirements are data-only; they carry route-fit metadata
 * and determinism posture so planners can aggregate them without
 * re-deriving the same information from raw timeline data.
 *
 * @param snapshot - A TimelineSnapshot produced by a TimelineReader.
 * @returns Ordered array of CapabilityRequirement records.
 */
export function getCapabilityRequirements(
  snapshot: TimelineSnapshot,
): CapabilityRequirement[] {
  const requirements: CapabilityRequirement[] = [];
  let reqCounter = 0;

  const nextId = (prefix: string): string => {
    reqCounter += 1;
    return `snapshot.${prefix}.${reqCounter}`;
  };

  // Guard: if snapshot has no clips, return empty.
  if (!snapshot.clips || snapshot.clips.length === 0) {
    return requirements;
  }

  // ── Clip-type requirements ──────────────────────────────────────────
  const seenClipTypes = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.clipType || seenClipTypes.has(clip.clipType)) continue;
    seenClipTypes.add(clip.clipType);

    const sourceRef: CapabilitySourceRef = clip.managedBy
      ? {
          source: 'extension',
          extensionId: clip.managedBy,
        }
      : { source: 'built-in' };

    requirements.push({
      id: nextId('clipType'),
      sourceRef,
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: clip.managedBy ? 'preview-only' : 'deterministic',
    });
  }

  // ── Effect requirements ─────────────────────────────────────────────
  const seenEffects = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.effects) continue;
    for (const effect of clip.effects) {
      const effectKey = `${clip.id}.${effect.effectType ?? 'unknown'}`;
      if (seenEffects.has(effectKey)) continue;
      seenEffects.add(effectKey);

      const sourceRef: CapabilitySourceRef = effect.managedBy
        ? {
            source: 'extension',
            extensionId: effect.managedBy,
          }
        : { source: 'built-in' };

      requirements.push({
        id: nextId('effect'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export'],
        determinism: effect.managedBy ? 'preview-only' : 'deterministic',
        findings: effect.managedBy
          ? undefined
          : [
              {
                id: `builtin.effect.${effect.effectType ?? 'unknown'}.${clip.id}`,
                severity: 'info',
                route: 'browser-export',
                message: `Built-in effect "${effect.effectType ?? 'unknown'}" on clip "${clip.id}" is deterministic for browser export.`,
                clipId: clip.id,
              },
            ],
      });
    }
  }

  // ── Transition requirements ─────────────────────────────────────────
  const seenTransitions = new Set<string>();
  for (const clip of snapshot.clips) {
    if (!clip.transition) continue;
    const tKey = `${clip.id}.${clip.transition.transitionType ?? 'unknown'}`;
    if (seenTransitions.has(tKey)) continue;
    seenTransitions.add(tKey);

    const sourceRef: CapabilitySourceRef = clip.transition.managedBy
      ? {
          source: 'extension',
          extensionId: clip.transition.managedBy,
        }
      : { source: 'built-in' };

    requirements.push({
      id: nextId('transition'),
      sourceRef,
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: clip.transition.managedBy ? 'preview-only' : 'deterministic',
    });
  }

  // ── Live-binding requirements ───────────────────────────────────────
  if (snapshot.liveBindings) {
    const seenBindings = new Set<string>();
    for (const binding of snapshot.liveBindings) {
      if (seenBindings.has(binding.bindingId)) continue;
      seenBindings.add(binding.bindingId);

      const sourceRef: CapabilitySourceRef = {
        source: 'provider',
      };

      const isBlocking = binding.status !== 'resolved';

      requirements.push({
        id: nextId('liveBinding'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export', 'sidecar-export'],
        determinism: 'live-unbaked',
        blocking: isBlocking,
        routeFit: isBlocking
          ? {
              route: 'browser-export',
              fit: 'blocked',
              reason: 'live-unbaked',
              message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is not resolved.`,
            }
          : {
              route: 'browser-export',
              fit: 'supported',
            },
        findings: [
          isBlocking
            ? {
                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
                severity: 'warning',
                route: 'browser-export',
                reason: 'live-unbaked',
                message: `Live binding "${binding.bindingId}" (source: ${binding.sourceKind}) on clip "${binding.clipId}" has status "${binding.status ?? 'unknown'}".`,
                clipId: binding.clipId,
              }
            : {
                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
                severity: 'info',
                route: 'browser-export',
                message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is resolved.`,
                clipId: binding.clipId,
              },
        ],
      });
    }
  }

  // ── Material-ref requirements ───────────────────────────────────────
  if (snapshot.materialRefs) {
    for (const ref of snapshot.materialRefs) {
      const sourceRef: CapabilitySourceRef = {
        source: 'registry',
      };

      requirements.push({
        id: nextId('materialRef'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: ['browser-export'],
        determinism: ref.determinism ?? 'unknown',
      });
    }
  }

  // ── Source-ref requirements ────────────────────────────────────────
  if (snapshot.sourceRefs) {
    for (const ref of snapshot.sourceRefs) {
      const sourceRef: CapabilitySourceRef = ref.extensionId
        ? {
            source: 'extension',
            extensionId: ref.extensionId,
          }
        : {
            source: ref.sourceKind === 'generation' ? 'provider' : 'registry',
          };

      const determinism = ref.determinism ?? 'unknown';
      const blocksBrowserExport =
        determinism === 'process-dependent' || determinism === 'live-unbaked';

      requirements.push({
        id: nextId('sourceRef'),
        sourceRef,
        route: 'browser-export',
        requiredCapabilities: blocksBrowserExport
          ? ['browser-export', 'sidecar-export']
          : ['browser-export'],
        determinism,
        ...(blocksBrowserExport
          ? {
              blocking: true,
              routeFit: {
                route: 'browser-export',
                fit: 'blocked',
                reason: determinism,
                message: `Source ref "${ref.id}" on clip "${ref.clipId}" requires materialization before browser export.`,
              },
            }
          : {}),
      });
    }
  }

  // ── Shader materializer requirements ───────────────────────────────
  if (snapshot.shaders) {
    for (const shader of snapshot.shaders) {
      if (shader.enabled === false) continue;

      const sourceRef: CapabilitySourceRef = {
        source: 'extension',
        extensionId: shader.extensionId,
        contributionId: shader.contributionId,
      };
      const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];

      for (const route of routes) {
        const message = shaderMissingMaterializerBlockerMessage(
          shader.shaderId,
          shader.scope,
          shader.clipId,
        );
        requirements.push({
          id: nextId('shader'),
          sourceRef,
          route,
          requiredCapabilities: ['render-material', 'shader-materializer'],
          determinism: 'preview-only',
          blocking: true,
          routeFit: {
            route,
            fit: 'blocked',
            reason: 'missing-material',
            message,
          },
        });
      }
    }
  }

  return requirements;
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
  ParserInput,
  ParserResult,
  ParserDiagnostic,
  ParserHandler,
  CompileOnlyOutputResult,
  OutputFormatHandler,
  OutputFormatContext,
  SearchMatch,
  SearchProviderResult,
  SearchProviderHandler,
  SearchProviderContext,
  AssetReadSurface,
  MaterialReadSurface,
  ExportService,
  OutputFormatRegistrationOptions,
} from '@/sdk/video/assets/metadata';
