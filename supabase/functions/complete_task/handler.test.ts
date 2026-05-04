import { beforeEach, describe, expect, it, vi } from 'vitest';
import { completeTaskHandler } from './handler.ts';
import { CompletionError } from './errors.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  enforceRateLimit: vi.fn(),
  parseCompleteTaskRequest: vi.fn(),
  validateStoragePathSecurity: vi.fn(),
  handleStorageOperations: vi.fn(),
  getStoragePublicUrl: vi.fn(),
  cleanupFile: vi.fn(),
  setThumbnailInParams: vi.fn((params: Record<string, unknown>) => params),
  extractTimelinePlacement: vi.fn(),
  getContentType: vi.fn(() => 'image/png'),
  createGenerationFromTask: vi.fn(),
  checkOrchestratorCompletion: vi.fn(),
  validateAndCleanupShotId: vi.fn(),
  triggerCostCalculationIfNotSubTask: vi.fn(),
  completeTaskErrorResponse: vi.fn((message: string, status: number, errorCode?: string, options?: { recoverable?: boolean }) =>
    new Response(JSON.stringify({ message, errorCode, recoverable: options?.recoverable }), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  ),
  fetchTaskContext: vi.fn(),
  markTaskFailed: vi.fn(),
  persistCompletionFollowUpIssues: vi.fn(),
  resolveTaskStorageActor: vi.fn(),
  toErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
  loadTimelineState: vi.fn(),
  saveTimelineConfigVersioned: vi.fn(),
  addMediaClip: vi.fn(),
}));

vi.mock('../_shared/http.ts', () => ({
  jsonResponse: (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
}));

vi.mock('../_shared/rateLimit.ts', () => ({
  enforceRateLimit: (...args: unknown[]) => mocks.enforceRateLimit(...args),
  RATE_LIMITS: {
    userAction: { maxRequests: 100, windowSeconds: 60 },
  },
}));

vi.mock('../_shared/edgeHandler.ts', () => ({
  bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
  NO_SESSION_RUNTIME_OPTIONS: {},
}));

vi.mock('../_shared/errorMessage.ts', () => ({
  toErrorMessage: (...args: unknown[]) => mocks.toErrorMessage(...args),
}));

vi.mock('../_shared/taskActorPolicy.ts', () => ({
  resolveTaskStorageActor: (...args: unknown[]) => mocks.resolveTaskStorageActor(...args),
}));

vi.mock('./request.ts', () => ({
  parseCompleteTaskRequest: (...args: unknown[]) => mocks.parseCompleteTaskRequest(...args),
  validateStoragePathSecurity: (...args: unknown[]) => mocks.validateStoragePathSecurity(...args),
}));

vi.mock('./storage.ts', () => ({
  handleStorageOperations: (...args: unknown[]) => mocks.handleStorageOperations(...args),
  getStoragePublicUrl: (...args: unknown[]) => mocks.getStoragePublicUrl(...args),
  cleanupFile: (...args: unknown[]) => mocks.cleanupFile(...args),
}));

vi.mock('./params.ts', () => ({
  setThumbnailInParams: (...args: unknown[]) => mocks.setThumbnailInParams(...args),
  extractTimelinePlacement: (...args: unknown[]) => mocks.extractTimelinePlacement(...args),
  getContentType: (...args: unknown[]) => mocks.getContentType(...args),
}));

vi.mock('./generation.ts', () => ({
  createGenerationFromTask: (...args: unknown[]) => mocks.createGenerationFromTask(...args),
}));

vi.mock('../ai-timeline-agent/db.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../ai-timeline-agent/db.ts')>();
  return {
    ...actual,
    loadTimelineState: (...args: unknown[]) => mocks.loadTimelineState(...args),
    saveTimelineConfigVersioned: (...args: unknown[]) => mocks.saveTimelineConfigVersioned(...args),
  };
});

vi.mock('../ai-timeline-agent/tools/timeline.ts', () => ({
  addMediaClip: (...args: unknown[]) => mocks.addMediaClip(...args),
}));

vi.mock('./orchestrator.ts', () => ({
  checkOrchestratorCompletion: (...args: unknown[]) => mocks.checkOrchestratorCompletion(...args),
}));

vi.mock('./shotValidation.ts', () => ({
  validateAndCleanupShotId: (...args: unknown[]) => mocks.validateAndCleanupShotId(...args),
}));

vi.mock('./billing.ts', () => ({
  triggerCostCalculationIfNotSubTask: (...args: unknown[]) => mocks.triggerCostCalculationIfNotSubTask(...args),
}));

vi.mock('./completionHelpers.ts', () => ({
  completeTaskErrorResponse: (...args: unknown[]) => mocks.completeTaskErrorResponse(...args),
  fetchTaskContext: (...args: unknown[]) => mocks.fetchTaskContext(...args),
  markTaskFailed: (...args: unknown[]) => mocks.markTaskFailed(...args),
  persistCompletionFollowUpIssues: (...args: unknown[]) => mocks.persistCompletionFollowUpIssues(...args),
}));

function createLogger() {
  return {
    setDefaultTaskId: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    critical: vi.fn(),
    debug: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
  };
}

function createSupabaseAdmin() {
  const finalEq = vi.fn().mockResolvedValue({ error: null });
  const firstEq = vi.fn().mockReturnValue({ eq: finalEq });
  const update = vi.fn().mockReturnValue({ eq: firstEq });
  const maybeSingle = vi.fn().mockResolvedValue({ error: null });
  const rpc = vi.fn().mockReturnValue({ maybeSingle });
  const from = vi.fn().mockReturnValue({ update });
  return { from, update, firstEq, finalEq, rpc, maybeSingle };
}

describe('completeTaskHandler', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('Deno', {
      env: {
        get: (key: string) => {
          if (key === 'SUPABASE_SERVICE_ROLE_KEY') return 'service-role-key';
          if (key === 'SUPABASE_URL') return 'https://example.supabase.co';
          return undefined;
        },
      },
    });

    mocks.enforceRateLimit.mockResolvedValue(null);
    mocks.parseCompleteTaskRequest.mockResolvedValue({
      success: true,
      data: {
        taskId: 'task-1',
        mode: 'upload',
        filename: 'out.png',
        requiresOrchestratorCheck: false,
        storagePath: null,
        storagePathTaskId: null,
      },
    });
    mocks.resolveTaskStorageActor.mockResolvedValue({
      ok: true,
      value: {
        isServiceRole: true,
        taskOwnerVerified: true,
        callerId: 'service-role',
        taskUserId: 'user-1',
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: {},
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.handleStorageOperations.mockResolvedValue({
      publicUrl: 'https://cdn.example.com/tasks/task-1/out.png',
      objectPath: 'tasks/user-1/task-1/out.png',
      thumbnailUrl: null,
    });
    mocks.validateAndCleanupShotId.mockResolvedValue({
      needsUpdate: false,
      updatedParams: {},
    });
    mocks.extractTimelinePlacement.mockReturnValue(null);
    mocks.createGenerationFromTask.mockResolvedValue({
      status: 'created',
      generation: { id: 'gen-1' },
      completionAsset: null,
    });
    mocks.checkOrchestratorCompletion.mockResolvedValue(undefined);
    mocks.triggerCostCalculationIfNotSubTask.mockResolvedValue({ ok: true });
    mocks.persistCompletionFollowUpIssues.mockResolvedValue({ ok: true });
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: 'project-1',
      shotNamesById: {},
    });
    mocks.addMediaClip.mockReturnValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [{ id: 'clip-added', track: 'V1', at: 12.5, asset: 'asset-added', clipType: 'hold', hold: 5 }],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      result: 'Added media clip clip-added on track V1 at 12.5s.',
    });
    mocks.saveTimelineConfigVersioned.mockResolvedValue(2);
  });

  it('returns bootstrap response when bootstrap fails', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: false,
      response: new Response('blocked', { status: 401 }),
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(401);
    await expect(response.text()).resolves.toBe('blocked');
  });

  it('returns parse failure response from request parser', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: createSupabaseAdmin(),
        logger,
        auth: { userId: 'user-1', isServiceRole: false },
      },
    });

    mocks.parseCompleteTaskRequest.mockResolvedValue({
      success: false,
      response: new Response('invalid', { status: 400 }),
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(400);
    await expect(response.text()).resolves.toBe('invalid');
  });

  it('completes task and returns success payload', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      success: true,
      public_url: 'https://cdn.example.com/tasks/task-1/out.png',
      thumbnail_url: null,
      follow_up: { status: 'ok', issues: [] },
      message: 'Task completed and file uploaded successfully',
    });

    expect(logger.setDefaultTaskId).toHaveBeenCalledWith('task-1');
    expect(mocks.resolveTaskStorageActor).toHaveBeenCalled();
    expect(mocks.fetchTaskContext).toHaveBeenCalled();
    expect(mocks.createGenerationFromTask).toHaveBeenCalled();
    expect(supabaseAdmin.from).toHaveBeenCalledWith('tasks');
    expect(logger.flush).toHaveBeenCalled();
  });

  it('preserves structured CompletionError details when generation creation fails', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.createGenerationFromTask.mockRejectedValue(
      new CompletionError({
        code: 'generation_route_no_result',
        message: 'No generation route produced a result',
        context: 'createGenerationFromTask',
        recoverable: false,
        metadata: { task_id: 'task-1' },
      }),
    );

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      message: 'No generation route produced a result',
      errorCode: 'generation_route_no_result',
      recoverable: false,
    });
    expect(logger.error).toHaveBeenCalledWith('Generation creation failed', expect.objectContaining({
      error_code: 'generation_route_no_result',
      recoverable: false,
      error_context: 'createGenerationFromTask',
      error_metadata: { task_id: 'task-1' },
    }));
    expect(mocks.markTaskFailed).toHaveBeenCalledWith(
      supabaseAdmin,
      'task-1',
      'Generation creation failed [generation_route_no_result]: No generation route produced a result',
    );
    expect(mocks.completeTaskErrorResponse).toHaveBeenCalledWith(
      'No generation route produced a result',
      500,
      'generation_route_no_result',
      { recoverable: false },
    );
  });

  it('wraps plain generation failures with the generic internal server response', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.createGenerationFromTask.mockRejectedValue(new Error('boom'));

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      message: 'Internal server error',
      errorCode: 'internal_server_error',
      recoverable: undefined,
    });
    expect(logger.error).toHaveBeenCalledWith('Generation creation failed', expect.objectContaining({
      error: 'boom',
      error_code: 'generation_completion_failed',
      recoverable: true,
    }));
    expect(mocks.markTaskFailed).toHaveBeenCalledWith(
      supabaseAdmin,
      'task-1',
      'Generation creation failed: boom',
    );
  });

  it('attempts legacy timeline insertion when timeline_placement is present in task params', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    const timelinePlacement = {
      timeline_id: 'timeline-1',
      source_clip_id: 'clip-source-1',
      target_track: 'V1',
      insertion_time: 12.5,
      intent: 'after_source' as const,
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: { timeline_placement: timelinePlacement },
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.extractTimelinePlacement.mockReturnValue(timelinePlacement);
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
        pinnedShotGroups: [{
          shotId: 'shot-1',
          trackId: 'stale-track',
          clipIds: ['missing-clip'],
          mode: 'images',
        }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: 'project-1',
      shotNamesById: {},
    });
    mocks.addMediaClip.mockReturnValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [{ id: 'clip-added', track: 'V1', at: 12.5, asset: 'asset-added', clipType: 'media' }],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
        pinnedShotGroups: [{
          shotId: 'shot-1',
          trackId: 'stale-track',
          clipIds: ['missing-clip'],
          mode: 'images',
        }],
      },
      result: 'Added media clip clip-added on track V1 at 12.5s.',
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    expect(mocks.extractTimelinePlacement).toHaveBeenCalledWith({ timeline_placement: timelinePlacement });
    expect(mocks.loadTimelineState).toHaveBeenCalledWith(supabaseAdmin, 'timeline-1');
    expect(supabaseAdmin.rpc).toHaveBeenCalledWith('upsert_asset_registry_entry', expect.objectContaining({
      p_timeline_id: 'timeline-1',
      p_entry: expect.objectContaining({
        file: 'https://cdn.example.com/tasks/task-1/out.png',
        generationId: 'gen-1',
        type: 'image/png',
      }),
    }));

    const rpcArgs = supabaseAdmin.rpc.mock.calls[0]?.[1] as { p_asset_id: string };
    expect(mocks.addMediaClip).toHaveBeenCalledWith(
      expect.objectContaining({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      }),
      expect.objectContaining({
        assets: expect.objectContaining({
          [rpcArgs.p_asset_id]: expect.objectContaining({
            file: 'https://cdn.example.com/tasks/task-1/out.png',
            generationId: 'gen-1',
          }),
        }),
      }),
      {
        track: 'V1',
        at: 12.5,
        assetKey: rpcArgs.p_asset_id,
        mediaType: 'image',
      },
    );
    expect(mocks.saveTimelineConfigVersioned).toHaveBeenCalledWith(
      supabaseAdmin,
      'timeline-1',
      1,
      expect.objectContaining({
        clips: expect.any(Array),
        pinnedShotGroups: [],
      }),
    );
    expect(mocks.persistCompletionFollowUpIssues).not.toHaveBeenCalled();
  });

  it('still completes successfully when legacy timeline insertion fails after generation creation', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    const timelinePlacement = {
      timeline_id: 'timeline-1',
      source_clip_id: 'clip-source-1',
      target_track: 'V1',
      insertion_time: 12.5,
      intent: 'after_source' as const,
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: { timeline_placement: timelinePlacement },
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.extractTimelinePlacement.mockReturnValue(timelinePlacement);
    mocks.addMediaClip.mockReturnValue({
      result: 'Track V1 does not exist.',
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      success: true,
      public_url: 'https://cdn.example.com/tasks/task-1/out.png',
      thumbnail_url: null,
      follow_up: {
        status: 'degraded',
        issues: [{
          step: 'timeline_placement',
          code: 'timeline_placement_failed',
          message: 'Track V1 does not exist.',
        }],
      },
      message: 'Task completed with follow-up warnings',
    });
    expect(mocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(mocks.persistCompletionFollowUpIssues).toHaveBeenCalledWith(
      supabaseAdmin,
      'task-1',
      {},
      [{
        step: 'timeline_placement',
        code: 'timeline_placement_failed',
        message: 'Track V1 does not exist.',
      }],
    );
    expect(logger.error).toHaveBeenCalledWith('Timeline placement follow-up failed', expect.objectContaining({
      generation_id: 'gen-1',
      timeline_placement: timelinePlacement,
    }));
    expect(mocks.markTaskFailed).not.toHaveBeenCalled();
  });

  it('places a completed asset after the live anchor clip when placement_intent is present', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    const placementIntent = {
      timeline_id: 'timeline-1',
      anchor_clip_id: 'clip-source-1',
      anchor_generation_id: 'gen-source-1',
      anchor_variant_id: 'variant-source-1',
      relation: 'after' as const,
      preferred_track_id: 'V1',
      fallback_at: 22.25,
      fallback_track_id: 'V1',
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: { placement_intent: placementIntent },
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.createGenerationFromTask.mockResolvedValue({
      status: 'created',
      generation: { id: 'gen-1' },
      completionAsset: {
        generation_id: 'gen-1',
        variant_id: 'variant-1',
        location: 'https://cdn.example.com/tasks/task-1/out.png',
        media_type: 'image',
        created_as: 'variant',
      },
    });
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [{ id: 'clip-source-1', at: 8, track: 'V1', clipType: 'hold', hold: 2.5 }],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: 'project-1',
      shotNamesById: {},
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    expect(mocks.extractTimelinePlacement).not.toHaveBeenCalled();
    expect(mocks.loadTimelineState).toHaveBeenCalledWith(supabaseAdmin, 'timeline-1');
    expect(supabaseAdmin.rpc).toHaveBeenCalledWith('upsert_asset_registry_entry', expect.objectContaining({
      p_timeline_id: 'timeline-1',
      p_entry: expect.objectContaining({
        file: 'https://cdn.example.com/tasks/task-1/out.png',
        generationId: 'gen-1',
        variantId: 'variant-1',
        type: 'image/png',
      }),
    }));

    const rpcArgs = supabaseAdmin.rpc.mock.calls[0]?.[1] as { p_asset_id: string };
    expect(mocks.addMediaClip).toHaveBeenCalledWith(
      {
        clips: [{ id: 'clip-source-1', at: 8, track: 'V1', clipType: 'hold', hold: 2.5 }],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      expect.objectContaining({
        assets: expect.objectContaining({
          [rpcArgs.p_asset_id]: expect.objectContaining({
            generationId: 'gen-1',
            variantId: 'variant-1',
          }),
        }),
      }),
      {
        track: 'V1',
        at: 10.5,
        assetKey: rpcArgs.p_asset_id,
        mediaType: 'image',
      },
    );
    expect(mocks.saveTimelineConfigVersioned).toHaveBeenCalledWith(
      supabaseAdmin,
      'timeline-1',
      1,
      expect.objectContaining({
        clips: expect.any(Array),
      }),
    );
    expect(mocks.persistCompletionFollowUpIssues).not.toHaveBeenCalled();
  });

  it('falls back to the stored placement coordinates when the anchor clip is gone', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    const placementIntent = {
      timeline_id: 'timeline-1',
      anchor_clip_id: 'clip-source-1',
      relation: 'after' as const,
      preferred_track_id: 'V1',
      fallback_at: 22.25,
      fallback_track_id: 'V1',
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: { placement_intent: placementIntent },
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.createGenerationFromTask.mockResolvedValue({
      status: 'created',
      generation: { id: 'gen-1' },
      completionAsset: {
        generation_id: 'gen-1',
        variant_id: 'variant-1',
        location: 'https://cdn.example.com/tasks/task-1/out.png',
        media_type: 'image',
        created_as: 'variant',
      },
    });
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: 'project-1',
      shotNamesById: {},
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    const rpcArgs = supabaseAdmin.rpc.mock.calls[0]?.[1] as { p_asset_id: string };
    expect(mocks.addMediaClip).toHaveBeenCalledWith(
      {
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      expect.objectContaining({
        assets: expect.objectContaining({
          [rpcArgs.p_asset_id]: expect.objectContaining({
            generationId: 'gen-1',
            variantId: 'variant-1',
          }),
        }),
      }),
      {
        track: 'V1',
        at: 22.25,
        assetKey: rpcArgs.p_asset_id,
        mediaType: 'image',
      },
    );
    expect(mocks.saveTimelineConfigVersioned).toHaveBeenCalled();
    expect(mocks.persistCompletionFollowUpIssues).not.toHaveBeenCalled();
  });

  it('records a degraded follow-up when both the anchor clip and fallback track are gone', async () => {
    const logger = createLogger();
    const supabaseAdmin = createSupabaseAdmin();
    const placementIntent = {
      timeline_id: 'timeline-1',
      anchor_clip_id: 'clip-source-1',
      relation: 'after' as const,
      preferred_track_id: 'V1',
      fallback_at: 22.25,
      fallback_track_id: 'V1',
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { userId: null, isServiceRole: true },
      },
    });
    mocks.fetchTaskContext.mockResolvedValue({
      id: 'task-1',
      task_type: 'image_generation',
      project_id: 'project-1',
      params: { placement_intent: placementIntent },
      result_data: {},
      tool_type: 'wan',
      category: 'image',
      content_type: 'image',
      variant_type: null,
    });
    mocks.createGenerationFromTask.mockResolvedValue({
      status: 'created',
      generation: { id: 'gen-1' },
      completionAsset: {
        generation_id: 'gen-1',
        variant_id: 'variant-1',
        location: 'https://cdn.example.com/tasks/task-1/out.png',
        media_type: 'image',
        created_as: 'variant',
      },
    });
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [],
        tracks: [{ id: 'V2', kind: 'visual', label: 'Visual 2' }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: 'project-1',
      shotNamesById: {},
    });

    const response = await completeTaskHandler(
      new Request('https://edge.test/complete-task', { method: 'POST' }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      success: true,
      public_url: 'https://cdn.example.com/tasks/task-1/out.png',
      thumbnail_url: null,
      follow_up: {
        status: 'degraded',
        issues: [{
          step: 'timeline_placement',
          code: 'placement_anchor_and_fallback_missing',
          message: 'Skipped placement because anchor clip clip-source-1 was missing and fallback track V1 no longer exists on timeline timeline-1.',
        }],
      },
      message: 'Task completed with follow-up warnings',
    });
    expect(supabaseAdmin.rpc).not.toHaveBeenCalled();
    expect(mocks.addMediaClip).not.toHaveBeenCalled();
    expect(mocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(mocks.persistCompletionFollowUpIssues).toHaveBeenCalledWith(
      supabaseAdmin,
      'task-1',
      {},
      [{
        step: 'timeline_placement',
        code: 'placement_anchor_and_fallback_missing',
        message: 'Skipped placement because anchor clip clip-source-1 was missing and fallback track V1 no longer exists on timeline timeline-1.',
      }],
    );
    expect(mocks.markTaskFailed).not.toHaveBeenCalled();
  });
});
