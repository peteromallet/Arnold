/**
 * overlay-example — M2 timelineOverlay contribution example.
 *
 * Demonstrates registering a timeline overlay contribution using only
 * the public @reigh/editor-sdk entrypoint.  Timeline overlays are an M2
 * feature that render above the edit area with viewport and interaction
 * policy props.
 *
 * @publicContract
 */

import { defineExtension, CONTRIBUTION_KIND_MILESTONE } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
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
      'overlay-milestone':
        'timelineOverlay kind is bridged at milestone {{milestone}}.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Demonstrate milestone lookup for the timelineOverlay kind
    const overlayMilestone = CONTRIBUTION_KIND_MILESTONE['timelineOverlay'];
    const milestoneMsg = ctx.services.i18n.t('overlay-milestone', {
      milestone: String(overlayMilestone ?? 'unknown'),
    });
    ctx.services.diagnostics.report({
      severity: 'info' as DiagnosticSeverity,
      code: 'overlay/milestone-info',
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
