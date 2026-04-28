// Sprint 8: render-button router tests.
// Mirrors the sprint brief's three cases (pure media, themed, mixed) +
// the orchestrator dispatch shape.

import { describe, expect, it, vi } from 'vitest';
import {
  buildRenderTimelinePayload,
  decideRenderRoute,
  enqueueBanodocoRenderTimeline,
} from '@/tools/video-editor/lib/renderRouter';

describe('Sprint 8 render-button router (decideRenderRoute)', () => {
  it('routes a pure-media timeline to the client renderer', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'text' },
        { clipType: 'effect-layer' },
      ],
    });
    expect(decision.route).toBe('client');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('pure_native_clips');
  });

  it('routes a themed-only timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'art-card' }, { clipType: 'cta-card' }],
    });
    expect(decision.route).toBe('banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(false);
    expect(decision.reason).toBe('themed_only');
  });

  it('routes a mixed themed+media timeline to banodoco_render_timeline', () => {
    const decision = decideRenderRoute({
      clips: [
        { clipType: 'media' },
        { clipType: 'art-card' },
      ],
    });
    expect(decision.route).toBe('banodoco');
    expect(decision.hasThemedClip).toBe(true);
    expect(decision.hasMediaClip).toBe(true);
    expect(decision.reason).toBe('mixed_themed_and_media');
  });

  it('treats legacy clips with undefined clipType as native media', () => {
    const decision = decideRenderRoute({
      clips: [{}, { clipType: undefined }],
    });
    expect(decision.route).toBe('client');
    expect(decision.hasThemedClip).toBe(false);
    expect(decision.hasMediaClip).toBe(true);
  });

  it('treats unknown clipTypes as media (loud-placeholder fallback path)', () => {
    const decision = decideRenderRoute({
      clips: [{ clipType: 'theme-package-not-yet-installed' }],
    });
    expect(decision.route).toBe('client');
    expect(decision.hasThemedClip).toBe(false);
  });

  it('returns no_clips for an empty timeline', () => {
    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
    expect(decideRenderRoute(null).reason).toBe('no_clips');
    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
  });
});

describe('Sprint 8 buildRenderTimelinePayload', () => {
  const baseInput = {
    timelineId: '11111111-1111-1111-1111-111111111111',
    projectId: '22222222-2222-2222-2222-222222222222',
    resolvedConfig: {
      theme: '2rp',
      clips: [{ clipType: 'art-card' }],
    },
    assetRegistry: { assets: { a: { url: 'https://cdn/a.mp4' } } },
    userJwt: 'user.jwt.token',
    correlationId: '33333333-3333-3333-3333-333333333333',
  };

  it('produces the SD-034-shaped payload from valid input', () => {
    const { payload, error } = buildRenderTimelinePayload(baseInput);
    expect(error).toBeUndefined();
    expect(payload).toBeDefined();
    expect(payload!.timeline_id).toBe(baseInput.timelineId);
    expect(payload!.project_id).toBe(baseInput.projectId);
    expect(payload!.user_jwt).toBe(baseInput.userJwt);
    expect(payload!.correlation_id).toBe(baseInput.correlationId);
    expect(payload!.theme_id).toBe('2rp');
    expect(payload!.output_filename).toContain(baseInput.timelineId);
  });

  it('falls back to 2rp theme when config has no theme field', () => {
    const { payload } = buildRenderTimelinePayload({
      ...baseInput,
      resolvedConfig: { clips: [{ clipType: 'art-card' }] },
    });
    expect(payload!.theme_id).toBe('2rp');
  });

  it('rejects empty user_jwt (SD-022)', () => {
    const { payload, error } = buildRenderTimelinePayload({ ...baseInput, userJwt: '' });
    expect(payload).toBeUndefined();
    expect(error).toContain('JWT');
  });

  it('rejects empty timelineId / projectId', () => {
    expect(buildRenderTimelinePayload({ ...baseInput, timelineId: '' }).error).toBeTruthy();
    expect(buildRenderTimelinePayload({ ...baseInput, projectId: '' }).error).toBeTruthy();
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
      clips: [{ clipType: 'art-card' }, { clipType: 'media' }],
    };

    // Step 1: router decides banodoco.
    const decision = decideRenderRoute(config);
    expect(decision.route).toBe('banodoco');

    // Step 2: build payload + enqueue.
    const { payload } = buildRenderTimelinePayload({
      timelineId: 't',
      projectId: 'p',
      resolvedConfig: config,
      assetRegistry: { assets: {} },
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
    expect(decision.route).toBe('client');
    // The integration assertion: no fetch is made for client-route timelines.
    // Caller should branch on `decision.route` and call useClientRender;
    // we don't test that wiring here (it lives in useClientRender), but
    // make the router contract explicit so future regressions are loud.
  });
});
