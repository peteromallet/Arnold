/**
 * writing-canary-example — M2 writing canary example.
 *
 * Demonstrates the writing surface canary using creative context stubs,
 * ExtensionNotImplementedError, and the writing milestone metadata.
 * Exercises the CreativeContext and CREATIVE_MEMBER_MILESTONE public
 * surface classes.
 *
 * @publicContract
 */

import {
  defineExtension,
  createCreativeContextStubs,
  CREATIVE_MEMBER_MILESTONE,
  ExtensionNotImplementedError,
} from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  CreativeContext,
} from '@reigh/editor-sdk';

export const writingCanaryExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.writing-canary-m2' as any,
    version: '1.0.0',
    label: 'Writing Canary M2 Example',
    description:
      'Demonstrates writing canary surface with creative context stubs.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-writing-canary' as any,
        kind: 'slot',
        slot: 'writingPanel',
        label: 'M2 Writing Canary',
      },
    ],
    messages: {
      'activated': 'M2 Writing Canary example activated.',
      'disposed': 'M2 Writing Canary example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Demonstrate creative context stubs — writing is active in M2
    const writingMilestone = CREATIVE_MEMBER_MILESTONE['writing'];
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'writing/milestone',
      message: `Writing creative context is active at ${writingMilestone}.`,
    });

    // Demonstrate creative context stub creation (independent of ctx)
    const stubs: CreativeContext = createCreativeContextStubs();

    // Verify that `writing` is enumerable on the stubs
    const hasWriting = 'writing' in stubs;
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'writing/canary-check',
      message: `Writing stub enumerable: ${hasWriting}`,
    });

    // Demonstrate ExtensionNotImplementedError for a future member
    let stageNotReady = false;
    try {
      void stubs.stage;
    } catch (err) {
      stageNotReady = err instanceof ExtensionNotImplementedError;
      ctx.services.diagnostics.report({
        severity: 'info',
        code: 'writing/stage-not-ready',
        message: `Stage stub correctly throws: ${stageNotReady}`,
        detail: {
          feature: (err as ExtensionNotImplementedError).feature,
          milestone: (err as ExtensionNotImplementedError).milestone,
        },
      });
    }

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
