/**
 * toolbar-example — M2 toolbar slot contribution example.
 *
 * Demonstrates registering a toolbar slot contribution using only the
 * public @reigh/editor-sdk entrypoint.  This example is SDK-only and
 * must NOT import from editor internals.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
} from '@reigh/editor-sdk';

export const toolbarExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.toolbar-m2' as any,
    version: '1.0.0',
    label: 'Toolbar M2 Example',
    description: 'Demonstrates toolbar slot contribution with M2 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-toolbar-primary' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 200,
        label: 'M2 Toolbar Button',
      },
      {
        id: 'm2-toolbar-secondary' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 300,
        label: 'M2 Toolbar Secondary',
      },
    ],
    settingsDefaults: {
      'toolbar.visible': true,
    },
    messages: {
      'activated': 'M2 Toolbar example activated.',
      'disposed': 'M2 Toolbar example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
