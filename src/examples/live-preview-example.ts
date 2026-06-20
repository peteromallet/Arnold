/**
 * live-preview-example — M11 live data source example.
 *
 * Demonstrates:
 *   1. A `LiveSource` declaration with kind, label, and permission metadata.
 *   2. `ctx.creative.sessions.registerSource()` during activation to
 *      register a live data source for preview in the editor.
 *   3. The lifecycle of a live source: registration, activation, disposal.
 *
 * Live sources are ephemeral runtime objects scoped to a single provider
 * mount. They are never persisted in timeline config/history. Only live
 * binding metadata is persisted on timeline objects after baking.
 *
 * Live source frontend coverage (permission, error, bake-ready states)
 * for canary sources is deferred in V1. This example demonstrates the
 * declarative registration shape that extensions use.
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
  LiveSource,
  LiveSourceKind,
  LiveSourceStatus,
  LiveSourceDiagnostic,
  LiveSourcePermission,
  LiveSessionsService,
  DiagnosticSeverity,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Live source descriptor
// ---------------------------------------------------------------------------

/**
 * A minimal live source descriptor for a webcam feed.
 * Omits `status` and `diagnostics` — those are managed by the host runtime.
 */
const EXAMPLE_LIVE_SOURCE: Omit<LiveSource, 'status' | 'diagnostics'> = {
  id: 'com.reigh.examples.livePreview.webcam-feed',
  kind: 'webcam' as LiveSourceKind,
  label: 'Example Webcam Feed',
  metadata: {
    deviceId: 'default',
    resolution: { width: 1280, height: 720 },
    frameRate: 30,
  },
  permission: {
    kind: 'camera',
    state: 'prompt',
    required: true,
  } as LiveSourcePermission,
};

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const livePreviewExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.live-preview' as any,
    version: '1.0.0',
    label: 'Live Preview Example',
    description:
      'Demonstrates live data source registration via M11 SDK surface.',
    apiVersion: 1,
    messages: {
      activated: 'Live preview example activated.',
      disposed: 'Live preview example disposed.',
      'source-registered': 'Live source "%{sourceId}" registered.',
      'source-disposed': 'Live source "%{sourceId}" disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    const sessions = ctx.creative.sessions as LiveSessionsService | undefined;

    let sourceHandle: DisposeHandle | null = null;

    if (sessions) {
      sourceHandle = sessions.registerSource(EXAMPLE_LIVE_SOURCE);

      ctx.services.diagnostics.report({
        severity: 'info' as DiagnosticSeverity,
        code: 'live/source-registered',
        message: ctx.services.i18n.t('source-registered', {
          sourceId: EXAMPLE_LIVE_SOURCE.id,
        }),
        sourceId: EXAMPLE_LIVE_SOURCE.id,
      } as LiveSourceDiagnostic);
    }

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');

        if (sourceHandle) {
          ctx.services.diagnostics.report({
            severity: 'info' as DiagnosticSeverity,
            code: 'live/source-disposed',
            message: ctx.services.i18n.t('source-disposed', {
              sourceId: EXAMPLE_LIVE_SOURCE.id,
            }),
            sourceId: EXAMPLE_LIVE_SOURCE.id,
          } as LiveSourceDiagnostic);

          sourceHandle.dispose();
        }
      },
    };
  },
});

/** Re-export types for SDK consumers. */
export type {
  LiveSource,
  LiveSourceKind,
  LiveSourceStatus,
  LiveSourceDiagnostic,
  LiveSourcePermission,
  LiveSessionsService,
};
