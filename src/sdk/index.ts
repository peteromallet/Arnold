/**
 * @reigh/editor-sdk — Public SDK entrypoint
 *
 * Stable public types and helpers for trusted local extensions.
 * This module must NOT import from editor internals (DataProvider,
 * raw timeline ops, editor runtime contexts, or internal mutation APIs).
 *
 * @publicContract
 */

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

export interface ExtensionDiagnostic {
  severity: DiagnosticSeverity;
  code: string;
  message: string;
  extensionId?: string;
  contributionId?: string;
  /** The earliest milestone that is expected to activate this feature. */
  milestone?: string;
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
  clear(): void;
  subscribe(listener: () => void): DisposeHandle;
  getSnapshot(): readonly Diagnostic[];
}

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

export function createDiagnosticCollection(initialDiagnostics: readonly Diagnostic[] = []): DiagnosticCollection {
  const diagnostics: Diagnostic[] = initialDiagnostics.map(freezeDiagnostic);
  const listeners = new Set<() => void>();
  let snapshot: readonly Diagnostic[] = Object.freeze([...diagnostics]);

  const publishSnapshot = () => {
    snapshot = Object.freeze([...diagnostics]);
    for (const listener of listeners) {
      listener();
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
        diagnostics[existingIndex] = frozen;
      } else {
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
  };
}

// ---------------------------------------------------------------------------
// M5: Renderability, blocker, material, and artifact contracts
// ---------------------------------------------------------------------------

export {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@/tools/video-editor/runtime/renderability.ts';

export type {
  ArtifactBoundary,
  BakeContract,
  CapabilityFinding,
  CapabilityFindingSeverity,
  ContributionRenderability,
  DeterminismStatus,
  RenderArtifact,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderCapabilityStatus,
  RenderLocatorKind,
  RenderMaterial,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderRoute,
  RenderStorageLocator,
} from '@/tools/video-editor/runtime/renderability.ts';

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
  // Reserved — not yet bridged
  | 'effect'
  | 'transition'
  | 'clipType'
  | 'agentTool'
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
}

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
// Processes (reserved, validated but inactive in M1)
// ---------------------------------------------------------------------------

export interface ProcessSpawnConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
}

export interface ProcessManifestEntry {
  id: string;
  label: string;
  spawn: ProcessSpawnConfig;
  protocol: 'stdio-jsonrpc';
  healthCheck?: string;
  shutdown?: string;
  restartPolicy?: 'never' | 'always' | 'on-failure';
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
    // M7: trusted component effects
    | EffectContribution
    // M8: trusted component transitions
    | TransitionContribution
  )[];
  /** Reserved: descriptive permission metadata. */
  permissions?: readonly ExtensionPermissionDeclaration[];
  /** Reserved: process declarations. */
  processes?: readonly ProcessManifestEntry[];
  /** Reserved: migration hooks. */
  migrations?: readonly Record<string, unknown>[];
  /** Reserved: human-readable comments. */
  comments?: string;
  /** Reserved: dependency declarations. */
  dependsOn?: readonly {
    extensionId: string;
    versionRange?: string;
    contributionIds?: readonly string[];
    optional?: boolean;
  }[];
  /** Reserved: renderability descriptors. */
  renderability?: Record<string, unknown>;
  /** Extension-scoped settings defaults applied when no stored value exists. */
  settingsDefaults?: Record<string, unknown>;
  /** Bundled i18n messages keyed by locale-neutral key. */
  messages?: Record<string, string>;
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
}

/** i18n service: minimal t() scaffolding with namespace fallback. */
export interface ExtensionI18nService {
  t(key: string, replacements?: Record<string, string | number>): string;
}

/** Diagnostics service: emit structured diagnostics from extension code. */
export interface ExtensionDiagnosticsService {
  report(diagnostic: Omit<ExtensionDiagnostic, 'extensionId'>): void;
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
  readonly sessions: unknown;
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
  sessions: 'M4',
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
): ExtensionContext {
  const extensionId = extension.manifest.id as string;
  const manifest = extension.manifest; // Already frozen by defineExtension

  // ---- diagnostics service ------------------------------------------------
  const diagnosticsList: ExtensionDiagnostic[] = [];
  const diagnosticsService: ExtensionDiagnosticsService = {
    report(diag: Omit<ExtensionDiagnostic, 'extensionId'>): void {
      const full: ExtensionDiagnostic = Object.freeze({
        ...diag,
        extensionId,
      });
      diagnosticsList.push(full);
    },
    get diagnostics(): readonly ExtensionDiagnostic[] {
      return diagnosticsList;
    },
  };

  // ---- settings service (localStorage-backed, with manifest defaults) -------
  const settingsPrefix = `reigh.ext.${extensionId}.`;
  const settingsDefaults: Record<string, unknown> =
    (manifest.settingsDefaults as Record<string, unknown> | undefined) ?? {};

  /** Track keys set via this service so they can be cleaned up on dispose. */
  const writtenKeys = new Set<string>();

  const settingsService: ExtensionSettingsService = {
    get<T = unknown>(key: string): T | undefined {
      try {
        const raw = localStorage.getItem(settingsPrefix + key);
        if (raw !== null) return JSON.parse(raw) as T;
        // Fall back to manifest defaults
        if (key in settingsDefaults) return settingsDefaults[key] as T;
        return undefined;
      } catch {
        // Fall back to manifest defaults on parse error
        if (key in settingsDefaults) return settingsDefaults[key] as T;
        return undefined;
      }
    },
    set<T = unknown>(key: string, value: T): void {
      try {
        localStorage.setItem(settingsPrefix + key, JSON.stringify(value));
        writtenKeys.add(key);
      } catch {
        // localStorage quota exceeded or unavailable — silently no-op
      }
    },
    delete(key: string): void {
      try {
        localStorage.removeItem(settingsPrefix + key);
        writtenKeys.delete(key);
      } catch {
        // localStorage unavailable — silently no-op
      }
    },
    keys(): readonly string[] {
      try {
        const result: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const lsKey = localStorage.key(i);
          if (lsKey && lsKey.startsWith(settingsPrefix)) {
            result.push(lsKey.slice(settingsPrefix.length));
          }
        }
        // Also include manifest default keys not yet written
        for (const dk of Object.keys(settingsDefaults)) {
          if (!result.includes(dk)) result.push(dk);
        }
        return result;
      } catch {
        return Object.keys(settingsDefaults);
      }
    },
  };

  /** Clean up all localStorage keys written by this extension's settings service. */
  function disposeSettings(): void {
    try {
      writtenKeys.forEach((key) => {
        localStorage.removeItem(settingsPrefix + key);
      });
      writtenKeys.clear();
    } catch {
      // localStorage unavailable — silently no-op
    }
  }

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
        message: `Cannot register command \"${_commandId}\" — the CommandRegistry has not been wired by the host provider.`,
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
        message: `Cannot register effect component \"${_effectId}\" — the EffectRegistry has not been wired by the host provider.`,
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
        message: `Cannot register transition renderer \"${_transitionId}\" — the TransitionRegistry has not been wired by the host provider.`,
      });
      return { dispose() {} };
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
    contributions: manifest.contributions
      ? Object.freeze(manifest.contributions.map((c) => Object.freeze({ ...c })))
      : undefined,
    permissions: manifest.permissions
      ? Object.freeze(manifest.permissions.map((p) => Object.freeze({ ...p })))
      : undefined,
    processes: manifest.processes
      ? Object.freeze(manifest.processes.map((p) => Object.freeze({ ...p })))
      : undefined,
    dependsOn: manifest.dependsOn
      ? Object.freeze(manifest.dependsOn.map((d) => Object.freeze({ ...d })))
      : undefined,
    migrations: manifest.migrations
      ? Object.freeze(manifest.migrations.map((m) => Object.freeze({ ...m })))
      : undefined,
    settingsDefaults: manifest.settingsDefaults
      ? Object.freeze({ ...manifest.settingsDefaults })
      : undefined,
    messages: manifest.messages
      ? Object.freeze({ ...manifest.messages })
      : undefined,
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
  effect: 'M7',
  transition: 'M8',
  clipType: 'M3',
  agentTool: 'M5',
  agent: 'M5',
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

// ---------------------------------------------------------------------------
// M3: TimelinePatch — semantic operation vocabulary
// ---------------------------------------------------------------------------

/** Top-level operation families supported by TimelinePatch. */
export type TimelinePatchOpFamily =
  | 'clip.add'
  | 'clip.update'
  | 'clip.remove'
  | 'clip.move'
  | 'track.add'
  | 'track.update'
  | 'track.remove'
  | 'asset.update'
  | 'asset.remove'
  | 'app.update'
  | 'project-data.write'
  | 'project-data.delete'
  | 'extension.noop';

/** Reserved operation families that are validated but not executed in M3. */
export type TimelinePatchReservedOpFamily =
  | 'clip.split'
  | 'clip.slice';

/** All known operation family strings (active + reserved). */
export type TimelinePatchAnyOpFamily =
  | TimelinePatchOpFamily
  | TimelinePatchReservedOpFamily;

/**
 * A single semantic operation in a TimelinePatch batch.
 *
 * Every operation carries an `op` family, a `target` object identifier
 * (clip ID, track ID, asset key, extension ID, etc.), and an optional
 * `payload` whose shape is family-dependent.
 */
export interface TimelinePatchOperation {
  /** Operation family, e.g. "clip.add", "track.update". */
  op: TimelinePatchAnyOpFamily;
  /** Object identifier scoped to the operation family. */
  target: string;
  /** Family-dependent payload. */
  payload?: Record<string, unknown>;
  /**
   * Sortable anchor for ordering-dependent operations (clip.move, etc.).
   * Interpreted by the patch compiler; ignored for order-independent ops.
   */
  order?: number;
}

/** A batch of TimelinePatch operations applied atomically. */
export interface TimelinePatch {
  /** Monotonically-increasing batch version assigned by the runtime. */
  version: number;
  /** Ordered list of operations in this batch. */
  operations: readonly TimelinePatchOperation[];
  /** Extension or source that produced this patch. */
  source?: string;
  /** Opaque metadata attached by the producer. */
  meta?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M3: TimelinePatch diagnostics
// ---------------------------------------------------------------------------

/**
 * Structured diagnostic produced by TimelinePatch validation or compilation.
 *
 * Diagnostics are exportable to the host diagnostic panel and carry enough
 * context to navigate from the diagnostic to the offending operation/payload.
 */
export interface TimelinePatchDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code, e.g. "timeline-patch/unknown-op". */
  code: `timeline-patch/${string}`;
  message: string;
  /** Zero-based index into the patch operation list, when applicable. */
  operationIndex?: number;
  /** The operation family that triggered the diagnostic. */
  op?: TimelinePatchAnyOpFamily;
  /** The target identifier from the offending operation. */
  target?: string;
  /** Structured detail (expected type, actual value, constraint, etc.). */
  detail?: Record<string, unknown>;
}

/** Result of validating a TimelinePatch batch. */
export interface TimelinePatchValidationResult {
  /** True when every operation in the batch passes validation. */
  valid: boolean;
  /** Diagnostics produced during validation (empty when valid). */
  diagnostics: readonly TimelinePatchDiagnostic[];
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
// M3: TimelineDiff — semantic change description
// ---------------------------------------------------------------------------

/** Granularity of a diff entry. */
export type TimelineDiffGranularity =
  | 'clip'
  | 'track'
  | 'asset'
  | 'app'
  | 'project-data';

/** The kind of change represented by a diff entry. */
export type TimelineDiffKind = 'added' | 'removed' | 'modified' | 'reordered';

/** A single entry in a TimelineDiff describing what changed. */
export interface TimelineDiffEntry {
  granularity: TimelineDiffGranularity;
  kind: TimelineDiffKind;
  /** Object identifier (clip ID, track ID, asset key, extension ID, etc.). */
  target: string;
  /** The operation family that produced this change. */
  op: TimelinePatchAnyOpFamily;
  /**
   * Pre-mutation value snapshot (summary). Omitted for 'added' entries.
   * Never exposes raw internal row/meta shapes.
   */
  before?: Record<string, unknown>;
  /**
   * Post-mutation value snapshot (summary). Omitted for 'removed' entries.
   * Never exposes raw internal row/meta shapes.
   */
  after?: Record<string, unknown>;
}

/**
 * Semantic diff describing what a patch batch changed.
 *
 * This is the public change description — it never exposes raw internal
 * timeline row data, provider metadata, or mutation engine internals.
 */
export interface TimelineDiff {
  /** The patch version this diff corresponds to. */
  version: number;
  /** Ordered list of changes produced by the patch. */
  entries: readonly TimelineDiffEntry[];
  /** Set of all object IDs affected by this patch. */
  affectedObjectIds: readonly string[];
}

/** Result of previewing a patch batch against current timeline state. */
export interface TimelinePreviewResult {
  /** The projected diff if the patch were applied. */
  diff: TimelineDiff;
  /**
   * Whether every operation in the patch is previewable.
   * Non-previewable operations (e.g. clip.split reserved) still produce
   * diagnostics but the diff may be incomplete.
   */
  fullyPreviewable: boolean;
  /** Diagnostics for non-previewable or problematic operations. */
  diagnostics: readonly TimelinePatchDiagnostic[];
}

// ---------------------------------------------------------------------------
// M3: TimelineSnapshot / TimelineReader
// ---------------------------------------------------------------------------

/**
 * Stable, read-only projection of timeline state for extensions and proposal
 * machinery. Never exposes raw internal rows, provider handles, or mutation
 * engine internals.
 */
export interface TimelineSnapshot {
  /** Project identifier, when available. */
  projectId: string | null;
  /**
   * Base version for concurrency control. This is the version the snapshot
   * was taken at; proposals based on this snapshot must revalidate against
   * the current reader version before acceptance.
   */
  baseVersion: number;
  /**
   * Current version at the time the snapshot was taken. Equal to baseVersion
   * when there are no uncommitted local edits.
   */
  currentVersion: number;
  /** Extensions referenced by this project with version-range constraints. */
  extensionRequirements: readonly ProjectExtensionRequirement[];
  /** Ordered list of clip summaries (ID, track, at, clipType, duration). */
  clips: readonly TimelineClipSummary[];
  /** Ordered list of track summaries (ID, kind, label, muted). */
  tracks: readonly TimelineTrackSummary[];
  /** Asset keys present in the timeline. */
  assetKeys: readonly string[];
  /** Extension-owned app data (project-data) keyed by extension ID. */
  app: Record<string, unknown>;
  /**
   * Source-map entries extracted from extension project-data.
   * Each entry maps a timeline object to a source location.
   */
  sourceMapEntries?: readonly SourceMapEntry[];
}

/** Lightweight clip summary for TimelineSnapshot projection. */
export interface TimelineClipSummary {
  id: string;
  track: string;
  at: number;
  clipType?: string;
  /** Duration in frames (derived from to-from or hold). */
  duration: number;
  /** True when this clip is managed by a registered extension. */
  managed: boolean;
  /** Extension ID that manages this clip, if managed. */
  managedBy?: string;
  /** Generated-object metadata attached by the owning extension, if any. */
  generatedMeta?: GeneratedObjectMeta;
}

/** Lightweight track summary for TimelineSnapshot projection. */
export interface TimelineTrackSummary {
  id: string;
  kind: 'visual' | 'audio';
  label: string;
  muted: boolean;
  /** Extension-owned app data attached to this track. */
  app?: Record<string, unknown>;
  /** Generated-object metadata attached by the owning extension, if any. */
  generatedMeta?: GeneratedObjectMeta;
}

/**
 * Read-only timeline reader exposed to host and extension code.
 * Provides stable snapshots without exposing internal stores.
 */
export interface TimelineReader {
  /** Take a point-in-time snapshot of the current timeline state. */
  snapshot(): TimelineSnapshot;
}

// ---------------------------------------------------------------------------
// M3: TimelineProposal
// ---------------------------------------------------------------------------

/** Lifecycle state of a proposal. */
export type ProposalState =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'stale';

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
  /** Diagnostics produced during validation or preview, if any. */
  diagnostics?: readonly TimelinePatchDiagnostic[];
}

/** Input for creating a new proposal. */
export interface TimelineProposalInput {
  source: string;
  rationale?: string;
  patch: TimelinePatch;
  baseVersion: number;
}

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
// M3: Extension project-data limits
// ---------------------------------------------------------------------------

/**
 * Hard limits on extension-owned project data stored in TimelineConfig.app.
 *
 * These limits are enforced by the patch compiler and the project-data
 * validation path. Exceeding any limit produces a diagnostic — the host
 * may choose to surface this as a warning or block the write.
 */
export const EXTENSION_PROJECT_DATA_LIMITS = {
  /** Maximum size in bytes for a single project-data entry (JSON-serialized). */
  MAX_ENTRY_BYTES: 64 * 1024, // 64 KB
  /** Maximum total size in bytes for all entries owned by one extension. */
  MAX_EXTENSION_TOTAL_BYTES: 1 * 1024 * 1024, // 1 MB
  /** Maximum number of entries one extension may store. */
  MAX_ENTRIES_PER_EXTENSION: 128,
} as const;

/** Diagnostic codes produced when project-data limits are exceeded. */
export type ProjectDataLimitCode =
  | 'project-data/entry-size-exceeded'
  | 'project-data/extension-total-exceeded'
  | 'project-data/entry-count-exceeded';

/**
 * Structured detail carried in TimelinePatchDiagnostic.detail when a
 * project-data limit is exceeded.
 */
export interface ProjectDataLimitDetail {
  extensionId: string;
  limit: number;
  actual: number;
  unit: 'bytes' | 'entries';
  code: ProjectDataLimitCode;
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

// ---------------------------------------------------------------------------
// M6: Asset metadata types
// ---------------------------------------------------------------------------

/**
 * Integrity metadata for an asset (checksum, algorithm, byte size).
 * Host-owned top-level shape under `AssetMetadata.integrity`.
 */
export interface AssetIntegrityMetadata {
  /** Checksum algorithm (e.g. 'sha256'). */
  algorithm: string;
  /** Hex-encoded checksum digest. */
  hash: string;
  /** File size in bytes. */
  size: number;
}

/**
 * GPS / geolocation metadata extracted from asset headers.
 * Host-owned top-level shape under `AssetMetadata.gps`.
 */
export interface AssetGPSMetadata {
  /** Latitude in decimal degrees (WGS84). */
  latitude?: number;
  /** Longitude in decimal degrees (WGS84). */
  longitude?: number;
  /** Altitude in metres above WGS84 ellipsoid. */
  altitude?: number;
  /** GPS timestamp if available (epoch ms). */
  timestamp?: number;
}

/**
 * Consent / rights metadata for an asset.
 * Host-owned top-level shape under `AssetMetadata.consent`.
 */
export interface AssetConsentMetadata {
  /** Human-readable source attribution. */
  source?: string;
  /** Consent / rights note (e.g. 'CC BY 4.0', 'all rights reserved'). */
  rightsNote?: string;
  /** Whether consent has been explicitly recorded. */
  consentRecorded?: boolean;
  /** ISO 8601 timestamp when consent was recorded. */
  consentTimestamp?: string;
}

/**
 * Provenance metadata describing where an asset came from.
 * Host-owned top-level shape under `AssetMetadata.provenance`.
 */
export interface AssetProvenanceMetadata {
  /** Human-readable origin description. */
  origin?: string;
  /** ID of the asset this was derived from, if any. */
  derivedFromAssetId?: string;
  /** Whether this asset was generated by AI/ML. */
  generated?: boolean;
  /** ISO 8601 capture or import timestamp. */
  capturedAt?: string;
  /** ISO 8601 import timestamp. */
  importedAt?: string;
}

/**
 * Enrichment status lifecycle state machine.
 *
 *   pending   → record created, not yet claimed
 *   claimed   → claimed by an extension/agent for processing
 *   resolving → processing in progress
 *   resolved  → enrichment completed successfully
 *   failed    → enrichment failed with a diagnostic
 *   expired   → enrichment timed out or was cancelled
 */
export type EnrichmentStatus =
  | 'pending'
  | 'claimed'
  | 'resolving'
  | 'resolved'
  | 'failed'
  | 'expired';

/**
 * A deferred enrichment record persisted inside asset metadata.
 *
 * Parsers that need ML inference may emit deferred enrichment records
 * instead of blocking ingestion.  The record carries an asset reference,
 * enrichment kind, input parameters, status, and owning extension.
 * M6 persists and displays the shape; M10/M12 activate claim/resolve
 * execution through agent/process contracts.
 */
export interface DeferredEnrichmentRecord {
  /** Unique record identifier. */
  id: string;
  /** The asset this enrichment targets. */
  assetId: string;
  /** Enrichment kind (e.g. 'embedding', 'caption', 'object-detection'). */
  kind: string;
  /** Input parameters for the enrichment process. */
  input?: Record<string, unknown>;
  /** Current lifecycle state. */
  status: EnrichmentStatus;
  /** The extension that owns this enrichment record. */
  extensionId: string;
  /** Contribution ID within the extension, if any. */
  contributionId?: string;
  /** ISO 8601 timestamp when the record was created. */
  createdAt: string;
  /** ISO 8601 timestamp when the record was last updated. */
  updatedAt: string;
  /** Diagnostic message when status is 'failed' or 'expired'. */
  diagnostic?: string;
  /** Enrichment output when status is 'resolved'. */
  output?: Record<string, unknown>;
}

/**
 * Top-level asset metadata shape persisted in AssetRegistryEntry.
 *
 * Host-owned keys (integrity, gps, consent, provenance, enrichment) are
 * at the top level.  Extension-owned metadata is namespaced under
 * `extensions[extensionId]`.
 */
export interface AssetMetadata {
  /** Integrity / checksum metadata. */
  integrity?: AssetIntegrityMetadata;
  /** GPS / geolocation metadata. */
  gps?: AssetGPSMetadata;
  /** Consent / rights metadata. */
  consent?: AssetConsentMetadata;
  /** Provenance / origin metadata. */
  provenance?: AssetProvenanceMetadata;
  /**
   * Extension-owned metadata namespaced by extension ID.
   * Extensions may store arbitrary structured data under their own key.
   */
  extensions?: Record<string, Record<string, unknown>>;
  /**
   * Deferred enrichment records for this asset.
   * Parsers may enqueue enrichment tasks without blocking ingestion.
   */
  enrichment?: readonly DeferredEnrichmentRecord[];
}

// ---------------------------------------------------------------------------
// M6: Metadata facet descriptors
// ---------------------------------------------------------------------------

/**
 * The value kind of a metadata facet field.
 *
 * Determines how the host renders filter/aggregation UI for the facet.
 */
export type MetadataFacetValueKind =
  | 'string'
  | 'number'
  | 'boolean'
  | 'date'
  | 'enum';

/**
 * A descriptor that tells the host how to surface a metadata field
 * as a searchable/filterable facet in the asset panel.
 *
 * The host owns facet rendering and aggregation; extensions provide
 * the descriptor and the metadata values.
 */
export interface MetadataFacetDescriptor {
  /**
   * Dot-separated path to the metadata field.
   * E.g. 'gps.latitude', 'integrity.algorithm', 'extensions.myExt.tags'.
   */
  fieldPath: string;
  /** Human-readable display name for the facet. */
  displayName: string;
  /** The value kind — determines rendering and filtering strategy. */
  valueKind: MetadataFacetValueKind;
  /**
   * Sort order for this facet relative to others (lower = first).
   * Default 0.
   */
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

// ---------------------------------------------------------------------------
// M6: Asset detail section descriptors
// ---------------------------------------------------------------------------

/**
 * A descriptor for a named section slot inside the asset detail panel.
 *
 * Asset detail sections are named slots within the asset panel (not whole
 * replacement panels).  The host owns section placement, empty/error states,
 * search result badges, and provenance-chain rendering.  Extensions provide
 * section descriptors to declare what metadata they surface.
 */
export interface AssetDetailSectionDescriptor {
  /** Unique section identifier within the extension. */
  id: string;
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
// M6: Parser runtime types
// ---------------------------------------------------------------------------

/**
 * Input passed to a parser handler during asset ingestion.
 *
 * Parsers receive metadata about the ingested file but not the raw
 * file bytes — the host validates size/type before invoking the parser
 * and the parser receives only the fields it declares interest in.
 */
export interface ParserInput {
  /** Asset key in the registry. */
  assetKey: string;
  /** Detected MIME type of the uploaded file. */
  mimeType: string;
  /** File extension (without leading dot). */
  extension: string;
  /** File size in bytes. */
  byteSize: number;
  /** Original filename from the upload. */
  filename?: string;
  /**
   * Any metadata already collected for this asset before this parser runs.
   * Parsers may read existing metadata to avoid recomputing values.
   */
  existingMetadata?: Readonly<AssetMetadata>;
}

/**
 * Result returned by a parser handler.
 *
 * Parsers return only the metadata they wish to contribute.
 * The host shallow-merges blessed registry fields and deep-merges
 * metadata by namespace.  Unknown top-level fields are rejected with
 * a diagnostic.
 */
export interface ParserResult {
  /**
   * Metadata to merge into the asset's metadata.
   * Extension-owned fields should be placed under `extensions[extensionId]`.
   */
  metadata?: Partial<AssetMetadata>;
  /** Diagnostics produced by the parser. */
  diagnostics?: readonly ParserDiagnostic[];
  /**
   * Deferred enrichment records the parser wishes to enqueue.
   * These are persisted alongside the asset and surface in the asset
   * detail panel; execution is deferred to M10/M12.
   */
  enrichment?: readonly DeferredEnrichmentRecord[];
}

/**
 * A diagnostic produced by a parser during asset ingestion.
 *
 * Parser diagnostics use `parser/`-prefixed codes and carry
 * enough context to identify the asset and the parser that produced
 * the diagnostic.
 */
export interface ParserDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code, e.g. 'parser/unsupported-mime-type'. */
  code: `parser/${string}`;
  message: string;
  /** The asset key that triggered the diagnostic. */
  assetKey?: string;
  /** The extension that owns the parser. */
  extensionId?: string;
  /** The parser contribution ID. */
  contributionId?: string;
  /** Structured detail (expected MIME, actual MIME, size limit, etc.). */
  detail?: Record<string, unknown>;
}

/**
 * A parser handler function registered by an extension.
 *
 * Receives a {@link ParserInput} and returns a {@link ParserResult}
 * or a Promise of one.  Thrown errors are caught by the host and
 * published as parser diagnostics.
 */
export type ParserHandler = (
  input: ParserInput,
) => ParserResult | Promise<ParserResult>;

// ---------------------------------------------------------------------------
// M6: Compile-only output result types
// ---------------------------------------------------------------------------

/**
 * The result of executing a compile-only output format.
 *
 * Compile-only formats (requiresRender: false) produce an artifact
 * without entering the render pipeline.  The output is a byte buffer
 * plus metadata describing the artifact.
 */
export interface CompileOnlyOutputResult {
  /** The output artifact bytes. */
  data: Uint8Array;
  /** MIME type of the output artifact. */
  mimeType: string;
  /** Suggested filename for the output artifact. */
  filename: string;
  /**
   * Diagnostics produced during compilation.
   * Non-error diagnostics do not prevent artifact production.
   */
  diagnostics?: readonly ParserDiagnostic[];
  /** Whether the compilation produced blocking errors. */
  hasBlockingErrors: boolean;
}

/**
 * A compile-only output format handler registered by an extension.
 *
 * Receives read-only access to timeline and asset data and produces
 * a deterministic artifact.  Must not mutate timeline state.
 */
export type OutputFormatHandler = (
  context: OutputFormatContext,
) => CompileOnlyOutputResult | Promise<CompileOnlyOutputResult>;

/**
 * Context passed to an output format handler.
 *
 * Provides read-only access to timeline snapshot and asset metadata
 * without exposing mutation surfaces.
 */
export interface OutputFormatContext {
  /** Read-only snapshot of the current timeline state. */
  readonly timeline: TimelineSnapshot;
  /** Read-only map of asset key to asset metadata. */
  readonly assets: ReadonlyMap<string, Readonly<AssetMetadata>>;
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The output format contribution ID. */
  readonly contributionId: string;
}

// ---------------------------------------------------------------------------
// M6: Search provider runtime types
// ---------------------------------------------------------------------------

/**
 * A single search result match from a search provider.
 */
export interface SearchMatch {
  /** Asset or material reference key. */
  ref: string;
  /** Kind of the referenced item. */
  kind: 'asset' | 'material';
  /**
   * Relevance score (0–1). Higher = more relevant.
   * Relative ordering is provider-owned; host may normalize.
   */
  score: number;
  /** Short excerpt or description for display in search results. */
  excerpt?: string;
  /** Opaque provider metadata (embedding distance, model version, etc.). */
  meta?: Record<string, unknown>;
}

/**
 * Result returned by a search provider for a host query.
 */
export interface SearchProviderResult {
  /** Ordered list of matches (highest score first). */
  matches: readonly SearchMatch[];
  /** Total number of results available beyond the returned matches. */
  totalCount?: number;
  /** Whether the provider has more results available. */
  hasMore?: boolean;
  /** Provider-owned diagnostics (indexing errors, etc.). */
  diagnostics?: readonly ParserDiagnostic[];
}

/**
 * A search provider handler registered by an extension.
 *
 * Receives a query string and returns scored asset/material refs.
 * Providers own indexing, model choice, and refresh; the host
 * owns query dispatch, result merge, and source labeling.
 */
export type SearchProviderHandler = (
  query: string,
  context: SearchProviderContext,
) => SearchProviderResult | Promise<SearchProviderResult>;

/**
 * Context passed to a search provider handler.
 */
export interface SearchProviderContext {
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The search provider contribution ID. */
  readonly contributionId: string;
  /** Maximum number of results the host will display. */
  readonly maxResults: number;
  /** Optional filter scoping the search to asset/material kind. */
  readonly resultKind?: 'asset' | 'material';
}

// ---------------------------------------------------------------------------
// M6: Asset read surface
// ---------------------------------------------------------------------------

/**
 * Read-only asset metadata surface exposed to extension code.
 *
 * Extensions can query asset metadata by key and list all asset keys
 * known to the registry.  This is a read-only projection — no mutation
 * or persistence surface is exposed.
 */
export interface AssetReadSurface {
  /**
   * Get metadata for a single asset by its registry key.
   * Returns undefined if the asset is not found.
   */
  get(assetKey: string): Readonly<AssetMetadata> | undefined;

  /**
   * List all asset keys known to the registry.
   */
  keys(): readonly string[];

  /**
   * Check whether an asset key exists in the registry.
   */
  has(assetKey: string): boolean;

  /**
   * Search assets by a metadata field path and value.
   * Returns matching asset keys.  Bounded to exact field matches
   * on host-owned metadata fields; extension-owned fields may be
   * searched only when a search provider is active.
   */
  search(fieldPath: string, value: string): readonly string[];
}

/**
 * Read-only material metadata surface exposed to extension code.
 *
 * Materials reference assets with additional media-specific metadata
 * (resolution, frame rate, codec, etc.).  This is a read-only projection.
 */
export interface MaterialReadSurface {
  /**
   * Get material metadata by its registry key.
   * Returns undefined if the material is not found.
   */
  get(materialKey: string): Readonly<Record<string, unknown>> | undefined;

  /**
   * List all material keys known to the registry.
   */
  keys(): readonly string[];

  /**
   * Check whether a material key exists in the registry.
   */
  has(materialKey: string): boolean;
}

// ---------------------------------------------------------------------------
// Updated CreativeContext with M6 types
// ---------------------------------------------------------------------------

// NOTE: CreativeContext is declared above (line ~590).
// The `assets`, `materials`, and `export` members are typed here
// but the runtime stubs still throw ExtensionNotImplementedError
// until the host provider wires live implementations.

// ---------------------------------------------------------------------------
// M6: Export service
// ---------------------------------------------------------------------------

/**
 * Export service available to extensions for registering output format
 * handlers imperatively during activate().
 *
 * Output formats must have a matching `OutputFormatContribution` in the
 * extension manifest.  Handlers are registered via `registerOutputFormat()`
 * and the returned DisposeHandle unregisters them on dispose.
 */
export interface ExportService {
  /**
   * Register a compile-only output format handler.
   *
   * The `formatId` must match the `id` of an `OutputFormatContribution`
   * declared by this extension in its manifest with `requiresRender: false`.
   *
   * Returns a DisposeHandle that unregisters the handler when dispose()
   * is called (safe to call multiple times; idempotent).
   */
  registerOutputFormat(
    formatId: string,
    handler: OutputFormatHandler,
    options?: OutputFormatRegistrationOptions,
  ): DisposeHandle;
}

/** Options for imperative output format registration. */
export interface OutputFormatRegistrationOptions {
  /** Override label for the export UI. */
  label?: string;
  /** Override description for the export UI. */
  description?: string;
}
