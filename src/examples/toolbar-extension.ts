/**
 * toolbar-extension — Extension example with slot contributions.
 *
 * Demonstrates declaring toolbar and statusBar slot contributions
 * through the public SDK.  The activate function emits a diagnostic
 * to confirm the extension was loaded correctly.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
} from '@reigh/editor-sdk';

export const toolbarExtension: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.toolbar' as any,
    version: '1.2.0',
    label: 'Toolbar Demo Extension',
    description: 'Adds a toolbar contribution and a status-bar entry.',
    apiVersion: 1,
    contributions: [
      {
        id: 'toolbar-demo' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 100,
        label: 'Demo toolbar widget',
      },
      {
        id: 'status-indicator' as any,
        kind: 'slot',
        slot: 'statusBar',
        order: 50,
        label: 'Extension status indicator',
      },
    ],
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'toolbar-example/activated',
      message: `Toolbar extension v${ctx.extension.version} activated.`,
    });

    return {
      dispose(): void {
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'toolbar-example/disposed',
          message: 'Toolbar extension disposed.',
        });
      },
    };
  },
});
