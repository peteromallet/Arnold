/**
 * Host-wired ExtensionContext factory.
 *
 * Creates a concrete ExtensionContext for a given extension.  This module
 * lives under `src/tools/video-editor/runtime/` and is the canonical home
 * for host wiring (DOM, localStorage, console, provider services) that is
 * deliberately kept OUT of `src/sdk/context.ts`, which remains a
 * host-wiring-free contract module.
 *
 * Moved from `src/sdk/contextFactory.ts` as part of M4 SDK boundary closure.
 *
 * @hostContract
 */

import type { DisposeHandle } from '@/sdk/dispose';
import type {
  ExtensionI18nService,
  ExtensionDiagnosticsService,
  ExtensionCommandService,
  ExtensionContext,
  CreativeContext,
} from '@/sdk/context';
import { createCreativeContext, CONTEXT_DISPOSE_SYMBOL } from '@/sdk/context';
import {
  attachInternalExtensionRenderSurface,
  type InternalExtensionRenderSurface,
} from '@/sdk/internalExtensionRenderSurface';
import type { CommandHandler, CommandRegistrationOptions } from '@/sdk/commands';
import type {
  ExtensionChromeService,
  ChromeEvent,
  ChromeEventPayload,
  ChromeProgressPayload,
} from '@/sdk/chrome';
import type {
  DiagnosticSeverity,
  ExtensionDiagnostic,
} from '@/sdk/diagnostics';
import { DIAGNOSTIC_SOURCE_EXTENSION } from '@/sdk/diagnostics';
import type { ReighExtension } from '@/sdk/lifecycle';
import {
  createExtensionSettingsService,
  type CreateExtensionSettingsServiceOptions,
} from '@/sdk/extensionSettingsService';

// M2b family module imports (type-only, compile-erased)
import type {
  EffectComponent,
  EffectRegistrationOptions,
  EffectRegistrationService,
} from '@/sdk/video/families/effects';
import type {
  TransitionRenderer,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
} from '@/sdk/video/families/transitions';
import type {
  ClipRenderer,
  ClipInspector,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
} from '@/sdk/video/families/clipTypeContributions';
import type {
  ShaderSourceDescriptor,
  ShaderRegistrationOptions,
  ShaderRegistrationService,
} from '@/sdk/video/families/shaders';
import type {
  AgentToolRegistrationService,
  AgentToolHandler,
  ToolProcessResult,
} from '@/sdk/video/families/agentTools';
import type { ProcessSpawnConfig } from '@/sdk/video/families/processes';

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
  internalRenderSurface?: InternalExtensionRenderSurface,
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
  if (internalRenderSurface) {
    attachInternalExtensionRenderSurface(ctx, internalRenderSurface);
  }

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
