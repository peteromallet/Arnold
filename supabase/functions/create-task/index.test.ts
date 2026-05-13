import { beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../_tests/mocks/denoHttpServer.ts';
import * as CreateTaskEntrypoint from './index.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  enforceRateLimit: vi.fn(),
  parseCreateTaskBody: vi.fn(),
  buildTaskInsertObject: vi.fn(),
  getErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
  getTaskFamilyResolver: vi.fn(),
}));

vi.mock('../_shared/edgeHandler.ts', () => ({
  bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
  NO_SESSION_RUNTIME_OPTIONS: {},
}));

vi.mock('../_shared/rateLimit.ts', () => ({
  enforceRateLimit: (...args: unknown[]) => mocks.enforceRateLimit(...args),
  RATE_LIMITS: {
    taskCreation: { maxRequests: 20, windowSeconds: 60 },
  },
}));

vi.mock('./request.ts', () => ({
  parseCreateTaskBody: (...args: unknown[]) => mocks.parseCreateTaskBody(...args),
  buildTaskInsertObject: (...args: unknown[]) => mocks.buildTaskInsertObject(...args),
  getErrorMessage: (...args: unknown[]) => mocks.getErrorMessage(...args),
}));

vi.mock('./resolvers/registry.ts', () => ({
  getTaskFamilyResolver: (...args: unknown[]) => mocks.getTaskFamilyResolver(...args),
}));

function createLogger() {
  return {
    info: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    critical: vi.fn(),
    setDefaultTaskId: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
  };
}

function createTasksInsertChain(taskId = 'task-1') {
  const single = vi.fn().mockResolvedValue({ data: { id: taskId }, error: null });
  const select = vi.fn().mockReturnValue({ single });
  const insert = vi.fn().mockReturnValue({ select });
  return { insert, select, single };
}

function createTasksIdempotentLookupChain(task: { id: string; status: string; project_id: string }) {
  const single = vi.fn().mockResolvedValue({ data: task, error: null });
  const eq = vi.fn().mockReturnValue({ single });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, single };
}

function createProjectsLookupChain(project: { user_id?: string; aspect_ratio?: string }) {
  const single = vi.fn().mockResolvedValue({ data: project, error: null });
  const eq = vi.fn().mockReturnValue({ single });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, single };
}

async function loadHandler() {
  await import('./index.ts');
  return __getServeHandler();
}

describe('create-task edge entrypoint', () => {
  it('imports entrypoint module directly', () => {
    expect(CreateTaskEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    __resetServeHandler();

    mocks.enforceRateLimit.mockResolvedValue(null);
    mocks.parseCreateTaskBody.mockReturnValue({
      ok: true,
      value: {
        project_id: 'project-1',
        family: 'image_upscale',
        input: { image_url: 'https://example.com/source.png' },
      },
    });
    mocks.buildTaskInsertObject.mockReturnValue({ id: 'task-client-1' });
    mocks.getTaskFamilyResolver.mockReturnValue(
      vi.fn().mockResolvedValue({
        tasks: [
          {
            project_id: 'project-1',
            task_type: 'image_upscale',
            params: { image_url: 'https://example.com/source.png' },
            status: 'Queued',
          },
        ],
      }),
    );

    const taskInsert = createTasksInsertChain('task-created-1');
    const supabaseAdmin = {
      from: vi.fn().mockImplementation((table: string) => {
        if (table === 'tasks') return { insert: taskInsert.insert };
        if (table === 'projects') return { select: createProjectsLookupChain({ aspect_ratio: '16:9' }).select };
        throw new Error(`Unexpected table: ${table}`);
      }),
      rpc: vi.fn().mockResolvedValue({ data: 'image_upscale', error: null }),
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger: createLogger(),
        auth: { isServiceRole: true, userId: null },
        body: {
          family: 'image_upscale',
          project_id: 'project-1',
          input: { image_url: 'https://example.com/source.png' },
        },
      },
    });
  });

  it('handles CORS preflight', async () => {
    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'OPTIONS' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
    expect(mocks.bootstrapEdgeHandler).not.toHaveBeenCalled();
  });

  it('returns bootstrap failure response untouched', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: false,
      response: new Response('blocked', { status: 401 }),
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(401);
    await expect(response.text()).resolves.toBe('blocked');
  });

  it('returns 400 when request body parse fails', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: { from: vi.fn() },
        logger,
        auth: { isServiceRole: true, userId: null },
        body: {},
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      errorCode: 'invalid_request_body',
      message: 'family field is required',
    });
    expect(logger.flush).toHaveBeenCalled();
  });

  it('requires project_id for service-role requests', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: { from: vi.fn() },
        logger,
        auth: { isServiceRole: true, userId: null },
        body: {
          family: 'image_upscale',
          input: { image_url: 'https://example.com/source.png' },
        },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      errorCode: 'invalid_request_body',
      message: 'project_id required',
    });
    expect(logger.flush).toHaveBeenCalled();
  });

  it('creates task successfully for service-role requests', async () => {
    const logger = createLogger();
    const taskInsert = createTasksInsertChain('task-created-1');
    const supabaseAdmin = {
      from: vi.fn().mockImplementation((table: string) => {
        if (table === 'tasks') return { insert: taskInsert.insert };
        if (table === 'projects') return { select: createProjectsLookupChain({ aspect_ratio: '16:9' }).select };
        throw new Error(`Unexpected table: ${table}`);
      }),
      rpc: vi.fn().mockResolvedValue({ data: 'image_upscale', error: null }),
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { isServiceRole: true, userId: null },
        body: {
          family: 'image_upscale',
          project_id: 'project-1',
          input: { image_url: 'https://example.com/source.png' },
        },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-created-1',
      status: 'Task queued',
    });
    expect(mocks.enforceRateLimit).not.toHaveBeenCalled();
    expect(logger.setDefaultTaskId).toHaveBeenCalledWith('task-created-1');
    expect(logger.flush).toHaveBeenCalled();
  });

  it('returns the existing task when idempotent recovery stays within the authorized project', async () => {
    const logger = createLogger();
    const duplicateError = {
      code: '23505',
      message: 'duplicate key value violates unique constraint on idempotency_key',
    };
    const insertSingle = vi.fn().mockResolvedValue({ data: null, error: duplicateError });
    const insertSelect = vi.fn().mockReturnValue({ single: insertSingle });
    const insert = vi.fn().mockReturnValue({ select: insertSelect });
    const projects = createProjectsLookupChain({ user_id: 'user-1', aspect_ratio: '16:9' });
    const existingTask = createTasksIdempotentLookupChain({
      id: 'task-existing-1',
      status: 'Queued',
      project_id: 'project-1',
    });
    const supabaseAdmin = {
      from: vi.fn().mockImplementation((table: string) => {
        if (table === 'projects') return { select: projects.select };
        if (table === 'tasks') {
          return {
            insert,
            select: existingTask.select,
          };
        }
        throw new Error(`Unexpected table: ${table}`);
      }),
      rpc: vi.fn().mockResolvedValue({ data: 'image_upscale', error: null }),
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { isServiceRole: false, userId: 'user-1', isJwtAuth: true },
        body: {
          family: 'image_upscale',
          project_id: 'project-1',
          input: { image_url: 'https://example.com/source.png' },
          idempotency_key: 'idem-1',
        },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-existing-1',
      status: 'Task queued',
      deduplicated: true,
    });
    expect(projects.eq).toHaveBeenCalledWith('id', 'project-1');
    expect(existingTask.eq).toHaveBeenCalledWith('idempotency_key', 'idem-1');
  });

  it('rejects idempotent recovery when the existing task belongs to another project', async () => {
    const logger = createLogger();
    const duplicateError = {
      code: '23505',
      message: 'duplicate key value violates unique constraint on idempotency_key',
    };
    const insertSingle = vi.fn().mockResolvedValue({ data: null, error: duplicateError });
    const insertSelect = vi.fn().mockReturnValue({ single: insertSingle });
    const insert = vi.fn().mockReturnValue({ select: insertSelect });
    const projects = createProjectsLookupChain({ user_id: 'user-1', aspect_ratio: '16:9' });
    const existingTask = createTasksIdempotentLookupChain({
      id: 'task-existing-1',
      status: 'Queued',
      project_id: 'project-other',
    });
    const supabaseAdmin = {
      from: vi.fn().mockImplementation((table: string) => {
        if (table === 'projects') return { select: projects.select };
        if (table === 'tasks') {
          return {
            insert,
            select: existingTask.select,
          };
        }
        throw new Error(`Unexpected table: ${table}`);
      }),
      rpc: vi.fn().mockResolvedValue({ data: 'image_upscale', error: null }),
    };

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin,
        logger,
        auth: { isServiceRole: false, userId: 'user-1', isJwtAuth: true },
        body: {
          family: 'image_upscale',
          project_id: 'project-1',
          input: { image_url: 'https://example.com/source.png' },
          idempotency_key: 'idem-1',
        },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      errorCode: 'project_forbidden',
      message: 'Forbidden: duplicate task belongs to a different project',
      recoverable: false,
    });
    expect(logger.setDefaultTaskId).not.toHaveBeenCalled();
    expect(logger.flush).toHaveBeenCalled();
  });
});
