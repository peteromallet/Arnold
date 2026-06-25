/**
 * stage-canary-example — M2 stage canary example.
 *
 * Demonstrates the stage surface canary using the registry-derived family
 * compatibility helpers and the stage creative context stub. Exercises
 * active, delegated, and absent family diagnostics without treating legacy
 * milestone metadata as the authority.
 *
 * @publicContract
 */

import {
  defineExtension,
  getVideoFamilyDefinition,
  getVideoFamilyLegacyBridgeStatus,
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
    // Demonstrate registry-derived family status across active, delegated,
    // and absent compatibility cases.
    const kinds: ContributionKind[] = [
      'slot',
      'timelineOverlay',
      'agent',
      'process',
      'futureStageSurface' as ContributionKind,
    ];

    for (const kind of kinds) {
      const family = getVideoFamilyDefinition(kind);
      const legacyBridgeStatus = getVideoFamilyLegacyBridgeStatus(kind);

      if (!family) {
        ctx.services.diagnostics.report({
          severity: 'warning',
          code: `stage/kind-${kind}-absent`,
          message:
            `Kind "${kind}" is absent from the family registry; ` +
            'legacy milestone metadata is unavailable.',
        });
        continue;
      }

      const compatibilityMilestone = family.legacyMilestone ?? legacyBridgeStatus ?? undefined;
      const isActive = legacyBridgeStatus === null;
      ctx.services.diagnostics.report({
        severity: isActive ? 'info' : 'warning',
        code: `stage/kind-${kind}-${isActive ? 'active' : family.executionMaturity}`,
        message: isActive
          ? `Kind "${kind}" is active with ${family.executionMaturity} execution maturity; ` +
            `legacy milestone ${compatibilityMilestone ?? 'unknown'} is compatibility metadata only.`
          : `Kind "${kind}" is ${family.executionMaturity} in the current host; ` +
            `legacy milestone ${compatibilityMilestone ?? 'unknown'} is a compatibility hint, not the authority.`,
        milestone: compatibilityMilestone,
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
