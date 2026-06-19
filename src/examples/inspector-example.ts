/**
 * inspector-example — M2 inspectorSection contribution example.
 *
 * Demonstrates registering an inspector section contribution using only
 * the public @reigh/editor-sdk entrypoint.  Inspector sections render
 * in the PropertiesPanel with host-supplied SelectionSnapshot.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ContributionKind,
  ExtensionContribution,
  VideoEditorSlotName,
} from '@reigh/editor-sdk';

export const inspectorExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.inspector-m2' as any,
    version: '1.0.0',
    label: 'Inspector M2 Example',
    description:
      'Demonstrates inspectorSection contribution with M2 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-inspector-before' as any,
        kind: 'inspectorSection',
        placement: 'before-default',
        label: 'M2 Inspector (Before Default)',
        order: 50,
      },
      {
        id: 'm2-inspector-after' as any,
        kind: 'inspectorSection',
        placement: 'after-default',
        label: 'M2 Inspector (After Default)',
        order: 150,
      },
    ],
    settingsDefaults: {
      'inspector.showAdvanced': false,
    },
    messages: {
      'activated': 'M2 Inspector example activated.',
      'disposed': 'M2 Inspector example disposed.',
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

/** Re-export commonly used types for SDK consumers. */
export type { ContributionKind, ExtensionContribution, VideoEditorSlotName };
