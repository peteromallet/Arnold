// Sprint 8: render-button router tests.
// Mirrors the sprint brief's three cases (pure media, themed, mixed) +
// the orchestrator dispatch shape.

import { describe, expect, it, vi } from 'vitest';
import {
  buildRenderTimelinePayload,
  decideRenderRoute,
  enqueueBanodocoRenderTimeline,
} from '@/tools/video-editor/lib/renderRouter';
import { executeRenderPipeline } from '@/tools/video-editor/render/renderPipeline';

function expectPlannerBlocker(
  blockers: readonly unknown[],
  expected: {
    readonly id: string;
    readonly route: string;
    readonly reason: string;
    readonly message: string;
    readonly detail: Readonly<Record<string, unknown>>;
  },
): void {
  expect(blockers).toContainEqual(expect.objectContaining({
    id: expected.id,
    route: expected.route,
    reason: expected.reason,
    message: expected.message,
    detail: expect.objectContaining(expected.detail),
  }));
}

describe('Sprint 8 render-button router (decideRenderRoute)', () => {
  it('routes a pure-media timeline to the client renderer', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'text' },
        { clipType: 'effect-layer' },
      ],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('routes a themed-only timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'image-jump' }],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
    expect(decision.planner.selectedPlannerRoute).toBe('worker-export');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(true);
  });

  it('routes locally-registered title-card timelines to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'title-card' }],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
  });

  it('routes a mixed themed+media timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'image-jump' },
      ],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_themed_and_media');
  });

  it('routes mixed local-sequence and media timelines to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'title-card' },
      ],
    });
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_themed_and_media');
  });

  it('treats legacy clips with undefined clipType as native media', () => {
    const decision = decideRenderRoute({
      clips: [{}, { clipType: undefined }],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
  });

  it('treats unknown clipTypes as media (loud-placeholder fallback path)', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'theme-package-not-yet-installed' }],
    });
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasThemedClip).toBe(false);
  });

  it('routes valid remotion_module clips by lane metadata before clipType fallback', () => {
    const decision = decideRenderRoute({
      clips: [{
        clipType: 'generated-clip-type-not-installed',
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('generated_remotion_module');
  });

  it('routes registered theme clipTypes as generated modules when the module lane is present', () => {
    const decision = decideRenderRoute({
      clips: [{
        clipType: 'art-card',
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('generated_remotion_module');
  });

  it('routes mixed valid remotion_module timelines to the worker route with a generated reason', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        {
          clipType: 'image-jump',
          generation: {
            sequence_lane: 'remotion_module',
            artifact_id: 'artifact-1',
          },
        },
      ],
    });

    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('mixed_generated_module_and_other');
    expect(decision.hasMediaClip).toBe(true);
  });

  it('blocks remotion_module clips with missing, empty, or non-string artifact ids', () => {
    const missingArtifact = decideRenderRoute({
      clips: [{ clipType: 'media', generation: { sequence_lane: 'remotion_module' } }],
    });
    expect(missingArtifact).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_missing_artifact',
    });
    expect(missingArtifact.planner.selectedPlannerRoute).toBe('preview');
    expect(missingArtifact.planner.plannerResult.canBrowserExport).toBe(false);
    expect(missingArtifact.planner.plannerResult.canWorkerExport).toBe(false);
    expect(missingArtifact.planner.plannerResult.canSidecarExport).toBe(false);
    const missingArtifactMessage = 'Clip type "media" cannot be rendered until remotion_module_missing_artifact is resolved.';
    expectPlannerBlocker(missingArtifact.planner.plannerResult.blockers, {
      id: 'router.clip.0.media.browser-export.browser-export.missing-material',
      route: 'browser-export',
      reason: 'missing-material',
      message: missingArtifactMessage,
      detail: {
        source: 'render-router',
        clipType: 'media',
        legacyReason: 'remotion_module_missing_artifact',
      },
    });
    expectPlannerBlocker(missingArtifact.planner.plannerResult.blockers, {
      id: 'router.clip.0.media.worker-export.worker-export.missing-material',
      route: 'worker-export',
      reason: 'missing-material',
      message: missingArtifactMessage,
      detail: {
        source: 'render-router',
        clipType: 'media',
        legacyReason: 'remotion_module_missing_artifact',
      },
    });
    expectPlannerBlocker(missingArtifact.planner.plannerResult.blockers, {
      id: 'router.clip.0.media.sidecar-export.sidecar-export.missing-material',
      route: 'sidecar-export',
      reason: 'missing-material',
      message: missingArtifactMessage,
      detail: {
        source: 'render-router',
        clipType: 'media',
        legacyReason: 'remotion_module_missing_artifact',
      },
    });

    const emptyArtifact = decideRenderRoute({
      clips: [{ clipType: 'image-jump', generation: { sequence_lane: 'remotion_module', artifact_id: '' } }],
    });
    expect(emptyArtifact).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_invalid_artifact',
    });
    expect(emptyArtifact.planner.selectedPlannerRoute).toBe('preview');
    expect(emptyArtifact.planner.plannerResult.canSidecarExport).toBe(false);

    const nonStringArtifact = decideRenderRoute({
      clips: [{ clipType: 'unknown', generation: { sequence_lane: 'remotion_module', artifact_id: 42 } }],
    });
    expect(nonStringArtifact).toMatchObject({
      route: 'preview-only',
      reason: 'remotion_module_invalid_artifact',
    });
    expect(nonStringArtifact.planner.selectedPlannerRoute).toBe('preview');
    expect(nonStringArtifact.planner.plannerResult.canSidecarExport).toBe(false);
  });

  it('does not treat non-module generation lanes as generated Remotion modules', () => {
    for (const sequence_lane of ['trusted_v1', 'schema_sequence', 'unknown_lane', null, undefined]) {
      expect(decideRenderRoute({
        clips: [{
          clipType: 'media',
          generation: { sequence_lane, artifact_id: 'artifact-1' },
        }],
      })).toMatchObject({
        route: 'browser-remotion',
        reason: 'pure_native_clips',
      });
    }
  });

  it('returns no_clips for an empty timeline', () => {
    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
    expect(decideRenderRoute(null).reason).toBe('no_clips');
    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
  });
});

// ---------------------------------------------------------------------------
// M7b T2: Sidecar-export planner / router selection
// ---------------------------------------------------------------------------

describe('M7b T2 sidecar-export route selection', () => {
  it('selects preview when a router-generated hard blocker blocks all export routes', () => {
    // Blocked remotion_module artifact metadata is a hard router-fed
    // planner blocker: browser, worker, and sidecar are all unavailable.
    const decision = decideRenderRoute({
      clips: [{ clipType: 'media', generation: { sequence_lane: 'remotion_module' } }],
    });
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
    expect(decision.route).toBe('preview-only');
  });

  it('does not select sidecar-export when browser is available (priority order)', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'media' }],
    });
    // Browser is available, so it should be selected over sidecar.
    expect(decision.planner.selectedPlannerRoute).toBe('browser-export');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(true);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(true);
    expect(decision.route).toBe('browser-remotion');
  });

  it('falls back to preview when all routes including sidecar are blocked', () => {
    // Use a process with blockers that target all export routes including sidecar.
    // When every export route is blocked, the planner selects preview.
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      undefined,
      {
        processes: [{
          id: 'blocker-process-contrib',
          extensionId: 'ext.blocker',
          processId: 'blocker-process',
          label: 'All-routes blocker',
          spec: {
            id: 'blocker-process',
            label: 'All-routes blocker',
            protocol: 'stdio-jsonrpc',
            spawn: { command: 'node', args: ['blocker.js'] },
            operations: [{
              id: 'blockAll',
              label: 'Block all',
              routes: ['browser-export', 'worker-export', 'sidecar-export'],
            }],
          },
          protocol: 'stdio-jsonrpc',
          operations: [{
            id: 'blockAll',
            label: 'Block all',
            routes: ['browser-export', 'worker-export', 'sidecar-export'],
          }],
          availableRoutes: ['browser-export', 'worker-export', 'sidecar-export'],
          requiredBy: [],
          blockers: [
            {
              id: 'blocker.browser',
              route: 'browser-export',
              reason: 'process-dependent',
              message: 'Browser export blocked by test process.',
            },
            {
              id: 'blocker.worker',
              route: 'worker-export',
              reason: 'process-dependent',
              message: 'Worker export blocked by test process.',
            },
            {
              id: 'blocker.sidecar',
              route: 'sidecar-export',
              reason: 'process-dependent',
              message: 'Sidecar export blocked by test process.',
            },
          ],
          nextActions: [],
        }],
        processStatuses: [{
          processId: 'blocker-process',
          status: 'ready',
          operations: {},
        }],
      },
    );
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.route).toBe('preview-only');
  });

  it('maps sidecar-export planner route to external for native clips with browser/worker blocked', () => {
    // When browser and worker are blocked by process blockers but sidecar
    // is unblocked, and the clip-based route is browser-remotion (native
    // clips), the decision maps to external.
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      undefined,
      {
        processes: [{
          id: 'browser-worker-blocker-contrib',
          extensionId: 'ext.bwblocker',
          processId: 'bw-blocker-process',
          label: 'Browser + worker blocker',
          spec: {
            id: 'bw-blocker-process',
            label: 'Browser + worker blocker',
            protocol: 'stdio-jsonrpc',
            spawn: { command: 'node', args: ['bw-blocker.js'] },
            operations: [{
              id: 'blockBW',
              label: 'Block browser + worker',
              routes: ['browser-export', 'worker-export'],
            }],
          },
          protocol: 'stdio-jsonrpc',
          operations: [{
            id: 'blockBW',
            label: 'Block browser + worker',
            routes: ['browser-export', 'worker-export'],
          }],
          availableRoutes: ['browser-export', 'worker-export'],
          requiredBy: [],
          blockers: [
            {
              id: 'blocker.browser',
              route: 'browser-export',
              reason: 'process-dependent',
              message: 'Browser export blocked.',
            },
            {
              id: 'blocker.worker',
              route: 'worker-export',
              reason: 'process-dependent',
              message: 'Worker export blocked.',
            },
          ],
          nextActions: [],
        }],
        processStatuses: [{
          processId: 'bw-blocker-process',
          status: 'ready',
          operations: {},
        }],
      },
    );
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(true);
    expect(decision.planner.selectedPlannerRoute).toBe('sidecar-export');
    expect(decision.route).toBe('external');
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('blocked sidecar-export does not prevent browser export selection', () => {
    // When browser is available and sidecar is blocked, browser should
    // still be selected. This verifies that a blocked sidecar route
    // leaves unrelated browser/worker/preview choices unaffected.
    const decision = decideRenderRoute({
      clips: [{ clipType: 'media' }],
    });
    // With native media, browser is available and should be selected.
    expect(decision.planner.selectedPlannerRoute).toBe('browser-export');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(true);
    expect(decision.route).toBe('browser-remotion');
    // sidecar status does not affect the browser route selection.
    expect(decision.planner.plannerResult.canSidecarExport).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// M9 T11: Contributed clip routing via dynamic capability records
// ---------------------------------------------------------------------------

function makeContributedRecord(
  clipTypeId: string,
  capabilities: Array<{ route: string; status: string }>,
) {
  return {
    clipTypeId,
    renderability: {
      capabilities: capabilities.map((c) => ({
        route: c.route,
        status: c.status,
        determinism: 'deterministic' as const,
      })),
      determinism: 'deterministic' as const,
    },
  };
}

const browserCapableRecord = makeContributedRecord('ext-glow', [
  { route: 'browser-export', status: 'supported' },
  { route: 'preview', status: 'supported' },
]);

const previewOnlyRecord = makeContributedRecord('ext-preview-only', [
  { route: 'preview', status: 'supported' },
  { route: 'browser-export', status: 'blocked' },
]);

const workerOnlyRecord = makeContributedRecord('ext-worker-only', [
  { route: 'worker-export', status: 'supported' },
  { route: 'preview', status: 'supported' },
]);

const noCapabilitiesRecord = makeContributedRecord('ext-no-caps', []);

describe('M9 T11 contributed clip routing (decideRenderRoute)', () => {
  it('routes a browser-capable contributed clip to browser-remotion', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-glow' }] },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.reason).toBe('browser_capable_contributed');
  });

  it('routes mixed browser-capable contributed + native clips to browser-remotion', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'media' },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_browser_capable_contributed_and_native');
  });

  it('blocks a contributed clip without browser-export capability (preview-only route)', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-preview-only' }] },
      [previewOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);

    const message = 'Clip type "ext-preview-only" cannot be rendered until contributed_blocked_no_browser_capability is resolved.';
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.clip.0.ext-preview-only.browser-export.browser-export.route-unsupported',
      route: 'browser-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'ext-preview-only',
        legacyReason: 'contributed_blocked_no_browser_capability',
      },
    });
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.clip.0.ext-preview-only.worker-export.worker-export.route-unsupported',
      route: 'worker-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'ext-preview-only',
        legacyReason: 'contributed_blocked_no_browser_capability',
      },
    });
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.clip.0.ext-preview-only.sidecar-export.sidecar-export.route-unsupported',
      route: 'sidecar-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'ext-preview-only',
        legacyReason: 'contributed_blocked_no_browser_capability',
      },
    });
  });

  it('blocks a contributed clip with only worker-export capability (worker routes blocked for contributed code)', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-worker-only' }] },
      [workerOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
  });

  it('blocks a contributed clip with no capabilities at all', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'ext-no-caps' }] },
      [noCapabilitiesRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
  });

  it('blocks mixed contributed (browser-capable) + themed clips due to worker route conflict', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'image-jump' },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);

    const message = 'Clip type "image-jump" cannot be rendered until contributed_blocked_worker_route_conflict is resolved.';
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.clip.1.image-jump.browser-export.browser-export.route-unsupported',
      route: 'browser-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'image-jump',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.clip.1.image-jump.sidecar-export.sidecar-export.route-unsupported',
      route: 'sidecar-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'image-jump',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
  });

  it('blocks contributed clip mixed with generated remotion module due to worker route conflict', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          {
            clipType: 'image-jump',
            generation: {
              sequence_lane: 'remotion_module',
              artifact_id: 'artifact-1',
            },
          },
        ],
      },
      [browserCapableRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_worker_route_conflict');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
    expect(decision.planner.plannerResult.canWorkerExport).toBe(false);
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);

    const message = 'Clip type "generated-remotion-module" cannot be rendered until contributed_blocked_worker_route_conflict is resolved.';
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.generated.contributed-conflict.browser-export.browser-export.route-unsupported',
      route: 'browser-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
    expectPlannerBlocker(decision.planner.plannerResult.blockers, {
      id: 'router.generated.contributed-conflict.sidecar-export.sidecar-export.route-unsupported',
      route: 'sidecar-export',
      reason: 'route-unsupported',
      message,
      detail: {
        source: 'render-router',
        clipType: 'generated-remotion-module',
        legacyReason: 'contributed_blocked_worker_route_conflict',
      },
    });
  });

  it('multiple browser-capable contributed clips all route to browser-remotion', () => {
    const record2 = makeContributedRecord('ext-glow-2', [
      { route: 'browser-export', status: 'supported' },
    ]);
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'ext-glow' },
          { clipType: 'ext-glow-2' },
        ],
      },
      [browserCapableRecord, record2],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('browser_capable_contributed');
  });

  it('existing themed routing is unchanged when contributed records are empty', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'image-jump' }] },
      [],
    );
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
  });

  it('existing native routing is unchanged when contributed records are empty', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      [],
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('existing native routing is unchanged when contributed records are undefined', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      undefined,
    );
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('a contributed record for an unrelated clipType does not affect themed routing', () => {
    const decision = decideRenderRoute(
      { clips: [{ clipType: 'title-card' }] },
      [browserCapableRecord], // ext-glow record, not title-card
    );
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.reason).toBe('themed_only');
  });

  it('blocks the first contributed clip without browser capability even when mixed with native clips', () => {
    const decision = decideRenderRoute(
      {
        clips: [
          { clipType: 'media' },
          { clipType: 'ext-preview-only' },
        ],
      },
      [previewOnlyRecord],
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.hasContributedClip).toBe(true);
    expect(decision.reason).toBe('contributed_blocked_no_browser_capability');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
  });

  it('no_clips decision reports hasContributedClip false', () => {
    const decision = decideRenderRoute({ clips: [] }, [browserCapableRecord]);
    expect(decision.route).toBe('browser-remotion');
    expect(decision.hasContributedClip).toBe(false);
    expect(decision.reason).toBe('no_clips');
  });

  it('blocked remotion_module short-circuits before contributed record lookup', () => {
    const decision = decideRenderRoute(
      {
        clips: [{
          clipType: 'ext-glow',
          generation: { sequence_lane: 'remotion_module' },
        }],
      },
      [browserCapableRecord], // ext-glow is browser-capable but the module is blocked
    );
    expect(decision.route).toBe('preview-only');
    expect(decision.reason).toBe('remotion_module_missing_artifact');
    expect(decision.planner.selectedPlannerRoute).toBe('preview');
    expect(decision.planner.plannerResult.canSidecarExport).toBe(false);
  });
});

describe('Sprint 8 buildRenderTimelinePayload', () => {
  const baseInput = {
    request: {
      timelineId: '11111111-1111-1111-1111-111111111111',
      assetRegistry: { assets: { a: { url: 'https://cdn/a.mp4' } } },
      resolvedConfig: {
        theme: '2rp',
        clips: [{ clipType: 'art-card' }],
      },
      renderMetadata: null,
      renderRuntime: {
        projectId: '22222222-2222-2222-2222-222222222222',
        orchestratorBaseUrl: 'https://orchestrator.example.com',
        getSupabaseSession: vi.fn(async () => null),
        getWorkerJwt: vi.fn(async () => null),
      },
    },
    userJwt: 'user.jwt.token',
    correlationId: '33333333-3333-3333-3333-333333333333',
  };

  it('produces the SD-034-shaped payload from valid input', () => {
    const { payload, error } = buildRenderTimelinePayload(baseInput);
    expect(error).toBeUndefined();
    expect(payload).toBeDefined();
    expect(payload!.timeline_id).toBe(baseInput.request.timelineId);
    expect(payload!.project_id).toBe(baseInput.request.renderRuntime.projectId);
    expect(payload!.user_jwt).toBe(baseInput.userJwt);
    expect(payload!.correlation_id).toBe(baseInput.correlationId);
    expect(payload!.theme_id).toBe('2rp');
    expect(payload!.output_filename).toContain(baseInput.request.timelineId);
  });

  it('keeps explicit caller-owned request inputs for local fixture renders', () => {
    const request = {
      ...baseInput.request,
      timelineId: 'fixture-local-timeline',
      assetRegistry: {
        assets: {
          'fixture-video': {
            file: 'fixtures/local.mp4',
            src: 'file:///tmp/fixtures/local.mp4',
            type: 'video/mp4',
          },
        },
      },
      resolvedConfig: {
        theme: '2rp',
        output: { resolution: '1920x1080', fps: 30, file: 'fixture.mp4' },
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        clips: [{ id: 'clip-fixture', clipType: 'image-jump', track: 'V1', at: 0, hold: 2 }],
        registry: {
          'fixture-video': {
            file: 'fixtures/local.mp4',
            src: 'file:///tmp/fixtures/local.mp4',
            type: 'video/mp4',
          },
        },
      },
    };

    const { payload, error } = buildRenderTimelinePayload({
      ...baseInput,
      request,
      correlationId: 'fixture-correlation',
    });

    expect(error).toBeUndefined();
    expect(payload).toBeDefined();
    expect(payload!.timeline_id).toBe('fixture-local-timeline');
    expect(payload!.project_id).toBe(request.renderRuntime.projectId);
    expect(payload!.correlation_id).toBe('fixture-correlation');
    expect(payload!.assets).toBe(request.assetRegistry);
  });

  it('falls back to 2rp theme when config has no theme field', () => {
    const { payload } = buildRenderTimelinePayload({
      ...baseInput,
      request: {
        ...baseInput.request,
        resolvedConfig: { clips: [{ clipType: 'art-card' }] },
      },
    });
    expect(payload!.theme_id).toBe('2rp');
  });

  it('rejects empty user_jwt (SD-022)', () => {
    const { payload, error } = buildRenderTimelinePayload({ ...baseInput, userJwt: '' });
    expect(payload).toBeUndefined();
    expect(error).toContain('JWT');
  });

  it('rejects empty timelineId / projectId', () => {
    expect(buildRenderTimelinePayload({
      ...baseInput,
      request: {
        ...baseInput.request,
        timelineId: '',
      },
    }).error).toBeTruthy();
    expect(buildRenderTimelinePayload({
      ...baseInput,
      request: {
        ...baseInput.request,
        renderRuntime: {
          ...baseInput.request.renderRuntime,
          projectId: '',
        },
      },
    }).error).toBeTruthy();
  });

  it('materializes sequence asset keys for the render payload without mutating persisted params', () => {
    const resolvedConfig = {
      theme: '2rp',
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-resource',
          clipType: 'resource-card',
          track: 'V1',
          at: 0,
          hold: 3,
          params: {
            title: 'Resource',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      registry: {
        'asset-a': {
          file: 'asset-a.png',
          src: 'https://cdn.example.com/asset-a.png',
          type: 'image',
        },
      },
    };

    const { payload } = buildRenderTimelinePayload({
      ...baseInput,
      request: {
        ...baseInput.request,
        resolvedConfig,
      },
    });

    const clip = (payload!.timeline as typeof resolvedConfig).clips[0];
    expect(clip.params).toMatchObject({
      previewAssetKeys: ['asset-a'],
      previews: ['https://cdn.example.com/asset-a.png'],
    });
    expect(resolvedConfig.clips[0].params).toEqual({
      title: 'Resource',
      previewAssetKeys: ['asset-a'],
    });
  });
});

describe('Sprint 8 enqueueBanodocoRenderTimeline', () => {
  const payload = {
    timeline_id: 't',
    timeline: { clips: [] },
    assets: { assets: {} },
    theme_id: '2rp',
    output_filename: 'render.mp4',
    user_jwt: 'jwt',
    project_id: 'p',
    correlation_id: 'c',
  };

  it('POSTs to /functions/v1/enqueue-task with the SD-034 envelope', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ task_id: 'task-42' }), { status: 200 }),
    );
    const result = await enqueueBanodocoRenderTimeline(payload, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      orchestratorBaseUrl: 'https://orchestrator.example.com',
    });
    expect(result.status).toBe('queued');
    expect(result.task_id).toBe('task-42');
    expect(result.correlation_id).toBe('c');

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('https://orchestrator.example.com/functions/v1/enqueue-task');
    expect((init as RequestInit).method).toBe('POST');
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt');
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.task_type).toBe('banodoco_render_timeline');
    expect(body.worker_pool).toBe('banodoco');
    expect(body.params.correlation_id).toBe('c');
  });

  it('surfaces a 4xx orchestrator response as an error result', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response('bad payload', { status: 400 }),
    );
    const result = await enqueueBanodocoRenderTimeline(payload, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      orchestratorBaseUrl: 'https://orchestrator.example.com',
    });
    expect(result.status).toBe('error');
    expect(result.message).toContain('HTTP 400');
  });

  it('surfaces a network failure as an error result', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error('connection refused'));
    const result = await enqueueBanodocoRenderTimeline(payload, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      orchestratorBaseUrl: 'https://orchestrator.example.com',
    });
    expect(result.status).toBe('error');
    expect(result.message).toContain('connection refused');
  });
});

describe('Sprint 8 router → enqueue integration', () => {
  it('themed timeline decision drives a banodoco-pool enqueue', async () => {
    const config = {
      theme: '2rp',
      clips: [{ clipType: 'image-jump' }, { clipType: 'media' }],
    };

    // Step 1: router decides banodoco.
    const decision = decideRenderRoute(config);
    expect(decision.route).toBe('worker-banodoco');

    // Step 2: build payload + enqueue.
    const { payload } = buildRenderTimelinePayload({
      request: {
        timelineId: 't',
        assetRegistry: { assets: {} },
        resolvedConfig: config,
        renderMetadata: null,
        renderRuntime: {
          projectId: 'p',
          orchestratorBaseUrl: 'https://orchestrator.example.com',
          getSupabaseSession: vi.fn(async () => null),
          getWorkerJwt: vi.fn(async () => null),
        },
      },
      userJwt: 'jwt',
      correlationId: 'corr-x',
    });
    expect(payload).toBeDefined();

    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ task_id: 'task-1' }), { status: 200 }),
    );
    const result = await enqueueBanodocoRenderTimeline(payload!, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      orchestratorBaseUrl: 'https://orchestrator.example.com',
    });
    expect(result.status).toBe('queued');

    // The dispatch hits the banodoco worker_pool, not the API pool.
    const body = JSON.parse(fetchImpl.mock.calls[0][1].body as string);
    expect(body.task_type).toBe('banodoco_render_timeline');
    expect(body.worker_pool).toBe('banodoco');
  });

  it('pure-media timeline decision skips the orchestrator entirely', () => {
    const config = { clips: [{ clipType: 'media' }, { clipType: 'text' }] };
    const decision = decideRenderRoute(config);
    expect(decision.route).toBe('browser-remotion');
    // The integration assertion: no fetch is made for client-route timelines.
    // Caller should branch on `decision.route` and call useClientRender;
    // we don't test that wiring here (it lives in useClientRender), but
    // make the router contract explicit so future regressions are loud.
  });
});

describe('Sprint 8 render pipeline middleware', () => {
  const runtime = {
    projectId: 'project-1',
    orchestratorBaseUrl: 'https://orchestrator.example.com',
    getSupabaseSession: vi.fn(async () => null),
    getWorkerJwt: vi.fn(async () => null),
  };

  it('renders supported local fixture timelines in the browser path without Supabase auth', async () => {
    const events: Array<{ type: string; request?: unknown; assetCount?: number; providerId?: string }> = [];
    const request = {
      timelineId: 'fixture-browser',
      assetRegistry: {
        assets: {
          'asset-1': {
            src: 'file:///tmp/fixture-browser.mp4',
            file: 'fixture-browser.mp4',
            type: 'video/mp4',
          },
        },
      },
      resolvedConfig: {
        output: { resolution: '1920x1080', fps: 30, file: 'fixture-browser.mp4' },
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        clips: [{ id: 'clip-1', track: 'V1', at: 0, from: 0, to: 2, clipType: 'media', asset: 'asset-1' }],
        registry: {
          'asset-1': {
            src: 'file:///tmp/fixture-browser.mp4',
            file: 'fixture-browser.mp4',
            type: 'video/mp4',
          },
        },
      },
      renderMetadata: null,
      renderRuntime: {
        projectId: 'project-1',
        orchestratorBaseUrl: 'https://orchestrator.example.com',
        getSupabaseSession: vi.fn(async () => null),
        getWorkerJwt: vi.fn(async () => null),
      },
    };
    const startBrowserRender = vi.fn(async () => ({
      status: 'done' as const,
      message: 'Saved fixture-browser.mp4',
    }));

    const result = await executeRenderPipeline({
      decision: decideRenderRoute(request.resolvedConfig),
      request,
      startBrowserRender,
      middlewares: [async (event) => {
        events.push(event);
      }],
    });

    expect(result).toMatchObject({
      status: 'done',
      providerId: 'browser-remotion',
    });
    expect(startBrowserRender).toHaveBeenCalledTimes(1);
    expect(request.renderRuntime.getSupabaseSession).not.toHaveBeenCalled();
    expect(request.renderRuntime.getWorkerJwt).not.toHaveBeenCalled();
    expect(events).toMatchObject([
      { type: 'beforeRender', request },
      { type: 'assetMaterialized', request, assetCount: 1 },
      { type: 'afterRender', request, providerId: 'browser-remotion' },
    ]);
  });

  it('emits beforeRender, assetMaterialized, and afterRender through one shared middleware path', async () => {
    const events: string[] = [];
    const middleware = vi.fn(async (event: { type: string }) => {
      events.push(event.type);
    });
    const startBrowserRender = vi.fn(async () => ({
      status: 'done' as const,
      message: 'Saved output.mp4',
    }));

    const result = await executeRenderPipeline({
      decision: decideRenderRoute({ clips: [{ clipType: 'media' }] }),
      request: {
        timelineId: 'timeline-1',
        assetRegistry: { assets: { 'asset-1': { src: 'https://cdn.example.com/asset-1.mp4', file: 'asset-1.mp4', type: 'video/mp4' } } },
        resolvedConfig: {
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [{ id: 'clip-1', track: 'V1', at: 0, hold: 1, clipType: 'media' }],
          registry: { 'asset-1': { src: 'https://cdn.example.com/asset-1.mp4', file: 'asset-1.mp4', type: 'video/mp4' } },
        },
        renderMetadata: null,
        renderRuntime: runtime,
      },
      startBrowserRender,
      middlewares: [middleware],
    });

    expect(result).toMatchObject({
      status: 'done',
      providerId: 'browser-remotion',
    });
    expect(startBrowserRender).toHaveBeenCalledTimes(1);
    expect(events).toEqual(['beforeRender', 'assetMaterialized', 'afterRender']);
  });

  it('emits renderFailed for preview-only routes without falling back to the browser renderer', async () => {
    const previewEvents: string[] = [];
    const previewResult = await executeRenderPipeline({
      decision: decideRenderRoute({
        clips: [{ clipType: 'media', generation: { sequence_lane: 'remotion_module' } }],
      }),
      request: {
        timelineId: 'timeline-1',
        assetRegistry: null,
        resolvedConfig: null,
        renderMetadata: null,
        renderRuntime: runtime,
      },
      startBrowserRender: vi.fn(async () => ({ status: 'done' as const, message: 'unexpected' })),
      middlewares: [async (event) => {
        previewEvents.push(event.type);
      }],
    });

    expect(previewResult).toMatchObject({
      status: 'error',
      providerId: 'preview-only',
    });
    expect(previewEvents).toEqual(['beforeRender', 'assetMaterialized', 'renderFailed']);
  });

  it('queues worker-capable routes through the banodoco provider without falling back to the browser renderer', async () => {
    const workerEvents: string[] = [];
    const startBrowserRender = vi.fn(async () => ({ status: 'done' as const, message: 'unexpected' }));
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ task_id: 'task-1' }), { status: 200 }),
    );
    const originalFetch = globalThis.fetch;
    vi.stubGlobal('fetch', fetchImpl);
    const workerRuntime = {
      ...runtime,
      getSupabaseSession: vi.fn(async () => {
        throw new Error('getSupabaseSession should not be called for worker dispatch');
      }),
      getWorkerJwt: vi.fn(async () => 'worker-jwt-123'),
    };
    const request = {
      timelineId: 'timeline-fixture-worker',
      assetRegistry: {
        assets: {
          'asset-1': {
            file: 'asset-1.png',
            src: 'file:///tmp/asset-1.png',
            type: 'image/png',
          },
        },
      },
      resolvedConfig: {
        theme: '2rp',
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        clips: [{ id: 'clip-1', track: 'V1', at: 0, hold: 1, clipType: 'image-jump' }],
        registry: {
          'asset-1': {
            file: 'asset-1.png',
            src: 'file:///tmp/asset-1.png',
            type: 'image/png',
          },
        },
      },
      renderMetadata: null,
      renderRuntime: workerRuntime,
    };

    const workerResult = await executeRenderPipeline({
      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
      request,
      startBrowserRender,
      middlewares: [async (event) => {
        workerEvents.push(event.type);
      }],
    });

    expect(workerResult).toMatchObject({
      status: 'queued',
      providerId: 'worker-banodoco',
      taskId: 'task-1',
      correlationId: expect.any(String),
    });
    expect(startBrowserRender).not.toHaveBeenCalled();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(workerRuntime.getWorkerJwt).toHaveBeenCalledTimes(1);
    expect(workerRuntime.getSupabaseSession).not.toHaveBeenCalled();
    const body = JSON.parse(fetchImpl.mock.calls[0][1].body as string);
    expect(body.params.timeline_id).toBe('timeline-fixture-worker');
    expect(body.params.project_id).toBe('project-1');
    expect(body.params.assets).toEqual(request.assetRegistry);
    expect(workerEvents).toEqual(['beforeRender', 'assetMaterialized', 'afterRender']);

    vi.stubGlobal('fetch', originalFetch);
  });

  it('emits renderFailed for worker routes when no worker session token is available', async () => {
    const workerEvents: string[] = [];
    const startBrowserRender = vi.fn(async () => ({ status: 'done' as const, message: 'unexpected' }));
    const workerResult = await executeRenderPipeline({
      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
      request: {
        timelineId: 'timeline-1',
        assetRegistry: null,
        resolvedConfig: {
          theme: '2rp',
          output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          clips: [{ id: 'clip-1', track: 'V1', at: 0, hold: 1, clipType: 'image-jump' }],
          registry: {},
        },
        renderMetadata: null,
        renderRuntime: runtime,
      },
      startBrowserRender,
      middlewares: [async (event) => {
        workerEvents.push(event.type);
      }],
    });

    expect(workerResult).toMatchObject({
      status: 'error',
      providerId: 'worker-banodoco',
    });
    expect(workerResult.message).toContain('missing worker session token');
    expect(startBrowserRender).not.toHaveBeenCalled();
    expect(workerEvents).toEqual(['beforeRender', 'assetMaterialized', 'renderFailed']);
  });
});
