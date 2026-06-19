/**
 * stage-canary-example — M2 stage canary example.
 *
 * Demonstrates the stage surface canary using contribution kind bridging,
 * CONTRIBUTION_KIND_MILESTONE, contributionKindNotYetBridged, and the
 * stage creative context stub.  Exercises reserved/inactive contribution
 * declarations and diagnostic reporting for not-yet-bridged kinds.
 *
 * @publicContract
 */

import {
  defineExtension,
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
} from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ContributionKind,
} from '@reigh/editor-sdk';

export const stageCanaryExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.stage-canary-m2' as any,
    version: '1.0.0',
    label: 'Stage Canary M2 Example',
    description:
      'Demonstrates stage canary surface with contribution kind bridging.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-stage-canary' as any,
        kind: 'slot',
        slot: 'stagePanel',
        label: 'M2 Stage Canary',
      },
      // Reserved / inactive contributions for forward-compatibility testing
      {
        id: 'm2-stage-effect-future' as any,
        kind: 'effect',
        label: 'Stage custom effect (reserved for M3)',
        effectId: 'com.reigh.stage.effect.wipe',
      },
      {
        id: 'm2-stage-agent-future' as any,
        kind: 'agent',
        label: 'Stage agent (reserved for M5)',
      },
    ],
    messages: {
      'activated': 'M2 Stage Canary example activated.',
      'disposed': 'M2 Stage Canary example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Demonstrate contribution kind bridging — which kinds are active?
    const kinds: ContributionKind[] = [
      'slot',
      'dialog',
      'panel',
      'inspectorSection',
      'timelineOverlay',
      'effect',
      'transition',
      'clipType',
      'parser',
      'agentTool',
      'agent',
    ];

    for (const kind of kinds) {
      const notBridged = contributionKindNotYetBridged(kind);
      const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
      ctx.services.diagnostics.report({
        severity: notBridged ? 'warning' : 'info',
        code: `stage/kind-${kind}`,
        message: notBridged
          ? `Kind "${kind}" is not yet bridged (target: ${milestone}).`
          : `Kind "${kind}" is active (milestone: ${milestone}).`,
        milestone: milestone ?? undefined,
      });
    }

    // Demonstrate creative context stub for stage (M5, not yet active)
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'stage/milestone',
      message: `Stage creative context will be active at M5 (currently M2).`,
      milestone: 'M5',
    });

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
