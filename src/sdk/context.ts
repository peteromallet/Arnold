/**
 * Portable context contracts and safe helpers for the Reigh Editor SDK.
 *
 * Core extension context types, creative context stubs, command registration
 * contracts, and disposal utilities.  This module is free of host wiring —
 * no DOM, localStorage, console, React lifecycle, requestAnimationFrame,
 * or provider-service imports.
 *
 * NOTE: createExtensionContext() was moved to `src/sdk/contextFactory.ts`
 * in M2b because it is deeply coupled to host wiring (DOM manipulation,
 * localStorage, console I/O, provider services, and React lifecycle).
 * context.ts remains host-wiring-free.
 *
 * @publicContract
 */

import type { ExtensionDiagnostic } from './diagnostics';
import type { CommandHandler, CommandRegistrationOptions } from './commands';
import type { DisposeHandle } from './dispose';
import type { ExtensionId } from './ids';
import type { ExtensionChromeService } from './chrome';
import type { ExtensionSettingsService } from './settings';
import type { TimelineReader } from '@/sdk/video/timeline/reader.ts';
import type {
  AssetReadSurface,
  MaterialReadSurface,
} from '@/sdk/video/assets/metadata.ts';
import type { ExportService } from '@/sdk/video/exports/outputFormats.ts';

// M2b family types now extracted to dedicated family modules.
// import type is erased at compile time — zero runtime cost, no host wiring.
import type { EffectRegistrationService } from './video/families/effects';
import type { ClipTypeRegistrationService } from './video/families/clipTypeContributions';
import type { ShaderRegistrationService } from './video/families/shaders';
import type { LiveSessionsService } from './video/liveData';
import type { ProposalRuntime } from './video/timeline/proposals';
import type { TimelineOps } from './video/timeline/timelineOps';
import type { TransitionRegistrationService } from './video/families/transitions';
import type { ExtensionManifest } from './manifest';
import type { AgentToolRegistrationService } from './video/families/agentTools';

// ---------------------------------------------------------------------------
// Context service contracts (pure interfaces)
// ---------------------------------------------------------------------------

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
// Context disposal
// ---------------------------------------------------------------------------

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
