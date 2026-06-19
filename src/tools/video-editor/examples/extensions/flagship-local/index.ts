/**
 * flagship-local-extension — Flagship trusted-local extension example.
 *
 * Demonstrates the full M1 SDK surface using only the public @reigh/editor-sdk
 * entrypoint:
 *
 *   - Activation / deactivation lifecycle with diagnostics
 *   - Toolbar and status-bar slot contributions
 *   - Settings with manifest-declared defaults
 *   - Diagnostics service (report + read-back)
 *   - Chrome toast/progress scaffolding
 *   - Trusted-local safety-warning copy emitted on activation
 *   - Command palette, keybinding, and clip context-menu contributions
 *   - Patch-backed command behavior through public creative timeline APIs
 *   - Future inactive contribution declarations (effect, transition, clipType,
 *     parser, agentTool) in the manifest for forward-compatibility testing
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  CommandContribution,
  CommandRunContext,
  ContextMenuItemContribution,
  KeybindingContribution,
  TimelinePatch,
} from '@reigh/editor-sdk';

const FLAGSHIP_EXTENSION_ID = 'com.reigh.examples.flagship-local';
const FLAGSHIP_MARK_REVIEW_COMMAND =
  `${FLAGSHIP_EXTENSION_ID}.markClipReview`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Read a settings value with a strongly-typed fallback. */
function setting<T>(
  ctx: ExtensionContext,
  key: string,
  fallback: T,
): T {
  const val = ctx.services.settings.get<T>(key);
  return val !== undefined ? val : fallback;
}

/** Report an info diagnostic through the extension's scoped service. */
function info(ctx: ExtensionContext, code: string, message: string): void {
  ctx.services.diagnostics.report({ severity: 'info', code, message });
}

/** Report a warning diagnostic through the extension's scoped service. */
function warn(ctx: ExtensionContext, code: string, message: string): void {
  ctx.services.diagnostics.report({ severity: 'warning', code, message });
}

/** Report an error diagnostic through the extension's scoped service. */
function error(ctx: ExtensionContext, code: string, message: string): void {
  ctx.services.diagnostics.report({ severity: 'error', code, message });
}

/** Build a small extension-owned patch that records the latest command run. */
function buildFlagshipReviewPatch(
  ctx: ExtensionContext,
  run: CommandRunContext,
): TimelinePatch {
  const snapshot = ctx.creative.reader.snapshot();
  const targetClipId = run.target?.target === 'clip'
    ? run.target.clipId
    : snapshot.clips[0]?.id ?? null;

  return {
    version: snapshot.baseVersion,
    source: ctx.extension.id as string,
    meta: { kind: 'flagship-review-marker' },
    operations: [
      {
        op: 'project-data.write',
        target: ctx.extension.id as string,
        payload: {
          key: 'flagship.lastReviewMarker',
          value: {
            commandId: run.commandId,
            targetClipId,
            clipCount: snapshot.clips.length,
            trackCount: snapshot.tracks.length,
            snapshotVersion: snapshot.currentVersion,
          },
          mode: 'replace',
        },
      },
    ],
  };
}

const commandContributions: readonly [
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
] = [
  {
    id: 'flagship-mark-review-command' as any,
    kind: 'command',
    command: FLAGSHIP_MARK_REVIEW_COMMAND,
    label: 'Flagship: Mark Clip for Review',
    category: 'Flagship',
    order: 10,
  },
  {
    id: 'flagship-mark-review-keybinding' as any,
    kind: 'keybinding',
    command: FLAGSHIP_MARK_REVIEW_COMMAND,
    key: 'CtrlOrCmd+Alt+F',
    order: 10,
  },
  {
    id: 'flagship-mark-review-menu' as any,
    kind: 'contextMenuItem',
    command: FLAGSHIP_MARK_REVIEW_COMMAND,
    label: 'Flagship: Mark Clip for Review',
    target: 'clip',
    when: 'target.clipId != null',
    order: 10,
  },
];

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const flagshipLocalExtension: ReighExtension = defineExtension({
  manifest: {
    id: FLAGSHIP_EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Flagship Local Extension',
    description:
      'Flagship trusted-local extension example demonstrating the full M1 SDK surface.',
    apiVersion: 1,

    // ---- Bridged M1 slot contributions ------------------------------------
    contributions: [
      ...commandContributions,
      {
        id: 'flagship-toolbar-button' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 200,
        label: 'Flagship toolbar',
      },
      {
        id: 'flagship-status' as any,
        kind: 'slot',
        slot: 'statusBar',
        order: 100,
        label: 'Flagship status',
      },

      // ---- Future inactive contribution declarations -----------------------
      // These are reserved for later milestones; the runtime will emit
      // info-level diagnostics noting they are not yet bridged.
      {
        id: 'flagship-effect-future' as any,
        kind: 'effect',
        label: 'Flagship custom effect (reserved for M3)',
        effectId: 'com.reigh.flagship.effect.glow',
      },
      {
        id: 'flagship-transition-future' as any,
        kind: 'transition',
        label: 'Flagship custom transition (reserved for M3)',
        transitionId: 'com.reigh.flagship.transition.crossfade',
      },
      {
        id: 'flagship-cliptype-future' as any,
        kind: 'clipType',
        label: 'Flagship custom clip type (reserved for M3)',
        clipTypeId: 'com.reigh.flagship.cliptype.annotation',
      },
      {
        id: 'flagship-parser-future' as any,
        kind: 'parser',
        label: 'Flagship custom parser (reserved for M4)',
      },
      {
        id: 'flagship-agent-tool-future' as any,
        kind: 'agentTool',
        label: 'Flagship agent tool (reserved for M5)',
      },
    ],

    // ---- Settings defaults (fall back when localStorage has no value) ------
    settingsDefaults: {
      'toolbar.label': 'Flagship',
      'toolbar.enabled': true,
      'status.showTimelineName': true,
      'status.pollIntervalMs': 5000,
    },

    // ---- i18n message bundle (resolved via ctx.services.i18n.t()) ----------
    messages: {
      'activation.started':
        'Flagship local extension v{{version}} activating…',
      'activation.ready':
        'Flagship local extension v{{version}} ready.',
      'activation.disposed':
        'Flagship local extension disposed.',
      'warning.trustedLocal':
        '⚠️ Trusted-local extension: this extension executes with full ' +
        'browser-renderer privileges. Review the extension source before ' +
        'enabling it in a shared project.',
      'progress.label': 'Chrome progress scaffold',
      'toast.error':
        'Flagship encountered an error: {{error}}',
      'toast.info':
        'Flagship status update: {{message}}',
      'command.markReview.ready':
        'Flagship review marker command registered.',
      'command.markReview.done':
        'Flagship review marker stored.',
    },
  },

  // -----------------------------------------------------------------------
  // activate
  // -----------------------------------------------------------------------
  activate(ctx: ExtensionContext): DisposeHandle {
    // --- Emit the trusted-local warning on every activation --------------
    const trustedWarning = ctx.services.i18n.t('warning.trustedLocal');
    warn(ctx, 'flagship/trusted-local-warning', trustedWarning);

    // --- Activation-start diagnostic ------------------------------------
    const startedMsg = ctx.services.i18n.t('activation.started', {
      version: ctx.extension.version,
    });
    info(ctx, 'flagship/activation-started', startedMsg);

    // --- Chrome toast scaffolding ---------------------------------------
    ctx.chrome.toast(startedMsg, 'info');

    // --- Settings demonstration -----------------------------------------
    const toolbarLabel = setting(ctx, 'toolbar.label', 'Flagship');
    const toolbarEnabled = setting(ctx, 'toolbar.enabled', true);
    const showTimelineName = setting(ctx, 'status.showTimelineName', true);
    const pollIntervalMs = setting(ctx, 'status.pollIntervalMs', 5000);

    info(
      ctx,
      'flagship/settings-loaded',
      `Settings loaded: toolbar.label="${toolbarLabel}", ` +
        `toolbar.enabled=${toolbarEnabled}, ` +
        `status.showTimelineName=${showTimelineName}, ` +
        `status.pollIntervalMs=${pollIntervalMs}`,
    );

    // Persist a setting so the lifecycle cleanup hook can remove it later
    ctx.services.settings.set('flagship.lastActivatedAt', Date.now());

    // --- Chrome progress scaffolding ------------------------------------
    ctx.chrome.progress(0, ctx.services.i18n.t('progress.label'));
    ctx.chrome.progress(50, ctx.services.i18n.t('progress.label'));
    ctx.chrome.progress(100, ctx.services.i18n.t('progress.label'));

    // --- Command contribution handler ------------------------------------
    const commandHandle = ctx.commands.registerCommand(
      FLAGSHIP_MARK_REVIEW_COMMAND,
      (run: CommandRunContext): void => {
        const patch = buildFlagshipReviewPatch(ctx, run);
        ctx.creative.timeline.apply(patch);
        const doneMsg = ctx.services.i18n.t('command.markReview.done');
        info(ctx, 'flagship/mark-review-command-ran', doneMsg);
        ctx.chrome.toast(doneMsg, 'info');
      },
      {
        label: 'Flagship: Mark Clip for Review',
        category: 'Flagship',
      },
    );

    info(
      ctx,
      'flagship/mark-review-command-ready',
      ctx.services.i18n.t('command.markReview.ready'),
    );

    // --- Chrome event subscriptions -------------------------------------
    // Subscribe to toast events to demonstrate the subscribe API
    const toastSub = ctx.chrome.subscribe('toast', (payload) => {
      // Log incoming toast events for debugging/demo purposes
      if (typeof console !== 'undefined') {
        console.log(
          `[Flagship] toast event received: severity=${payload.severity} message="${payload.message}"`,
        );
      }
    });

    // Subscribe to render status events as a scaffold for future use
    const renderSub = ctx.chrome.subscribe('renderStatus', (payload) => {
      if (typeof console !== 'undefined') {
        console.log(
          `[Flagship] render status: ${payload.status}` +
            (payload.error ? ` (error: ${payload.error})` : ''),
        );
      }
    });

    // --- Activation-ready diagnostic ------------------------------------
    const readyMsg = ctx.services.i18n.t('activation.ready', {
      version: ctx.extension.version,
    });
    info(ctx, 'flagship/activation-ready', readyMsg);
    ctx.chrome.toast(readyMsg, 'info');

    // --- Diagnostics read-back (demonstrate reading emitted diagnostics) -
    const currentDiags = ctx.services.diagnostics.diagnostics;
    info(
      ctx,
      'flagship/diagnostics-count',
      `Emitted ${currentDiags.length} diagnostics during activation.`,
    );

    // --- Return dispose handle ------------------------------------------
    return {
      dispose(): void {
        // Unsubscribe chrome event handlers
        toastSub.dispose();
        renderSub.dispose();
        commandHandle.dispose();

        // Emit disposal diagnostic
        const disposedMsg = ctx.services.i18n.t('activation.disposed');
        info(ctx, 'flagship/disposed', disposedMsg);

        // Clean up the persisted setting
        ctx.services.settings.delete('flagship.lastActivatedAt');

        // Final toast
        ctx.chrome.toast(disposedMsg, 'info');
      },
    };
  },
});
