/**
 * status-surface-example — M2 statusBar slot contribution example.
 *
 * Demonstrates registering a status-bar slot contribution using only
 * the public @reigh/editor-sdk entrypoint.  Includes chrome event
 * subscription scaffolding (toast, progress, save, renderStatus)
 * and settings persistence with manifest defaults.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ChromeEvent,
  ChromeToastPayload,
  ChromeProgressPayload,
  ChromeSavePayload,
  ChromeRenderStatusPayload,
  ChromeEventPayload,
} from '@reigh/editor-sdk';

export const statusSurfaceExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.status-m2' as any,
    version: '1.0.0',
    label: 'Status Surface M2 Example',
    description:
      'Demonstrates status-bar slot contribution with M2 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-status-timeline-name' as any,
        kind: 'slot',
        slot: 'statusBar',
        order: 100,
        label: 'M2 Status: Timeline Name',
      },
      {
        id: 'm2-status-playback' as any,
        kind: 'slot',
        slot: 'statusBar',
        order: 200,
        label: 'M2 Status: Playback',
      },
    ],
    settingsDefaults: {
      'status.showTimelineName': true,
      'status.pollIntervalMs': 5000,
    },
    messages: {
      'activated': 'M2 Status Surface example activated.',
      'disposed': 'M2 Status Surface example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Demonstrate settings service
    const showTimeline = ctx.services.settings.get<boolean>(
      'status.showTimelineName',
    );
    const pollMs = ctx.services.settings.get<number>(
      'status.pollIntervalMs',
    );

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'status/config',
      message: `Status config: showTimelineName=${showTimeline}, pollIntervalMs=${pollMs}`,
    });

    // Demonstrate chrome event subscriptions
    const toastSub = ctx.chrome.subscribe('toast' as ChromeEvent, (_payload) => {
      // Extension would react to toast events here
    });

    const saveSub = ctx.chrome.subscribe('save' as ChromeEvent, (_payload) => {
      // Extension would react to save events here
    });

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');
    ctx.chrome.progress(100);

    return {
      dispose(): void {
        toastSub.dispose();
        saveSub.dispose();
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
