/**
 * overlay-example — M2 timelineOverlay contribution example.
 *
 * Demonstrates registering a timeline overlay contribution using only
 * the public @reigh/editor-sdk entrypoint. Timeline overlays render above
 * the edit area with viewport and interaction policy props; the example
 * reports registry-derived family status instead of treating milestone
 * constants as authoritative.
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
  DiagnosticSeverity,
} from '@reigh/editor-sdk';

export const overlayExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.overlay-m2' as any,
    version: '1.0.0',
    label: 'Timeline Overlay M2 Example',
    description:
      'Demonstrates timelineOverlay contribution with M2 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-overlay-viewport-labels' as any,
        kind: 'timelineOverlay',
        label: 'M2 Viewport Labels Overlay',
        order: 100,
      },
    ],
    messages: {
      'activated': 'M2 Timeline Overlay example activated.',
      'disposed': 'M2 Timeline Overlay example disposed.',
      'overlay-family-status':
        'timelineOverlay is {{status}} with {{executionMaturity}} execution maturity; legacy milestone {{milestone}} is compatibility metadata.',
      'overlay-family-missing':
        'timelineOverlay is absent from the family registry; compatibility metadata is unavailable.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    const overlayFamily = getVideoFamilyDefinition('timelineOverlay');
    const legacyBridgeStatus = getVideoFamilyLegacyBridgeStatus('timelineOverlay');
    const milestoneMsg = overlayFamily
      ? ctx.services.i18n.t('overlay-family-status', {
          status: legacyBridgeStatus === null ? 'active' : overlayFamily.executionMaturity,
          executionMaturity: overlayFamily.executionMaturity,
          milestone: overlayFamily.legacyMilestone ?? legacyBridgeStatus ?? 'unknown',
        })
      : ctx.services.i18n.t('overlay-family-missing');
    ctx.services.diagnostics.report({
      severity: 'info' as DiagnosticSeverity,
      code: overlayFamily ? 'overlay/family-status' : 'overlay/family-missing',
      message: milestoneMsg,
    });

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
