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
// Manifest
// ---------------------------------------------------------------------------

/** Known contribution kinds. Reserved/inactive kinds are validated but not bridged. */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection'
  // Reserved — not yet bridged in M1
  | 'effect'
  | 'transition'
  | 'clipType'
  | 'parser'
  | 'agentTool'
  | 'agent';

/** Slot names the host shell recognizes. */
export type VideoEditorSlotName =
  | 'header'
  | 'toolbar'
  | 'leftPanel'
  | 'rightPanel'
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
  contributions?: readonly ExtensionContribution[];
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
  readonly timeline: unknown;
  readonly assets: unknown;
  readonly materials: unknown;
  readonly sessions: unknown;
  readonly export: unknown;
  readonly stage: unknown;
  readonly writing: unknown;
}

/** The milestone that activates each creative context member. */
export const CREATIVE_MEMBER_MILESTONE: Record<keyof CreativeContext, string> = {
  project: 'M2',
  timeline: 'M2',
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

// ---------------------------------------------------------------------------
// ExtensionContext
// ---------------------------------------------------------------------------

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
  /** Reserved creative context stubs — throw typed "not implemented until Mx". */
  readonly creative: CreativeContext;
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
 * - `chrome` (toast, progress, subscribe)
 * - `services.settings` (localStorage-backed, scoped per extension)
 * - `services.i18n` (minimal t() scaffolding)
 * - `services.diagnostics` (in-memory structured diagnostic reporting)
 * - `creative` stubs that throw typed ExtensionNotImplementedError
 *
 * No raw DataProvider, applyEdit, timeline store, or internal mutation
 * escape hatch is exposed.
 */
export function createExtensionContext(extension: ReighExtension): ExtensionContext {
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
  };

  /** Clean up all chrome event subscribers. */
  function disposeChromeSubscriptions(): void {
    subscribers.clear();
  }

  // ---- creative stubs -----------------------------------------------------
  const creative = createCreativeContextStubs();

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
  effect: 'M3',
  transition: 'M3',
  clipType: 'M3',
  parser: 'M4',
  agentTool: 'M5',
  agent: 'M5',
};

/**
 * Check whether a contribution kind is bridged in the current runtime.
 * Returns the milestone name if NOT bridged, or null if it is bridged.
 */
export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (milestone && milestone === 'M1') return null;
  return milestone ?? 'unknown';
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
