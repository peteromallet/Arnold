import { beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../_tests/mocks/denoHttpServer.ts';
import * as ClaimNextTaskEntrypoint from './index.ts';

const mocks = vi.hoisted(() => ({
  withEdgeRequest: vi.fn(),
  rpc: vi.fn(),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
  loggerDebug: vi.fn(),
  loggerSetDefaultTaskId: vi.fn(),
}));

vi.mock('../_shared/edgeHandler.ts', () => ({
  withEdgeRequest: (...args: unknown[]) => mocks.withEdgeRequest(...args),
}));

function createContext(body: Record<string, unknown>, auth: { userId?: string | null; isServiceRole?: boolean }) {
  return {
    supabaseAdmin: {
      rpc: mocks.rpc,
    },
    logger: {
      info: mocks.loggerInfo,
      error: mocks.loggerError,
      debug: mocks.loggerDebug,
      setDefaultTaskId: mocks.loggerSetDefaultTaskId,
    },
    body,
    auth,
  };
}

async function loadHandler() {
  await import('./index.ts');
  return __getServeHandler();
}

describe('claim-next-task edge entrypoint', () => {
  it('imports entrypoint module directly', () => {
    expect(ClaimNextTaskEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    __resetServeHandler();

    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({}, { userId: 'user-1', isServiceRole: false }));
      },
    );
  });

  it('returns 401 when auth is missing', async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({}, { userId: null, isServiceRole: false }));
      },
    );

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(401);
    await expect(response.text()).resolves.toContain('Authentication failed');
  });

  it('returns 204 when PAT user has no eligible tasks', async () => {
    mocks.rpc.mockResolvedValue({ data: [], error: null });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(204);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_user_pat', {
      p_user_id: 'user-1',
      p_include_active: false,
    });
  });

  it('returns claimed task for PAT user', async () => {
    mocks.rpc.mockResolvedValue({
      data: [
        {
          task_id: 'task-42',
          params: { prompt: 'hello' },
          task_type: 'image_generation',
          project_id: 'project-7',
        },
      ],
      error: null,
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-42',
      params: { prompt: 'hello' },
      task_type: 'image_generation',
      project_id: 'project-7',
    });
    expect(mocks.loggerSetDefaultTaskId).toHaveBeenCalledWith('task-42');
  });

  it('uses service-role RPC path when service role auth is present', async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({ run_type: 'api', same_model_only: true }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({
      data: [
        {
          task_id: 'task-service',
          params: {},
          task_type: 'video_generation',
          project_id: 'project-service',
        },
      ],
      error: null,
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', {
      p_worker_id: expect.any(String),
      p_include_active: false,
      p_run_type: 'api',
      p_same_model_only: true,
      p_max_task_wait_minutes: 5,
      p_worker_pool: null,
      p_task_types: null,
    });
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-service',
      params: {},
      task_type: 'video_generation',
      project_id: 'project-service',
    });
  });

  it('passes through max_task_wait_minutes for service-role claims', async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({
          run_type: 'gpu',
          same_model_only: true,
          max_task_wait_minutes: 3,
        }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({
      data: [
        {
          task_id: 'task-service-2',
          params: {},
          task_type: 'video_generation',
          project_id: 'project-service-2',
        },
      ],
      error: null,
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', {
      p_worker_id: expect.any(String),
      p_include_active: false,
      p_run_type: 'gpu',
      p_same_model_only: true,
      p_max_task_wait_minutes: 3,
      p_worker_pool: null,
      p_task_types: null,
    });
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-service-2',
      params: {},
      task_type: 'video_generation',
      project_id: 'project-service-2',
    });
  });

  it('forwards worker_pool and banodoco-worker run_type for banodoco pool', async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({
          worker_id: 'banodoco-worker-1',
          run_type: 'banodoco-worker',
          worker_pool: 'banodoco',
          task_types: ['banodoco_timeline_generate', 'banodoco_render_timeline'],
        }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({
      data: [
        {
          task_id: 'task-banodoco-1',
          params: { foo: 'bar' },
          task_type: 'banodoco_timeline_generate',
          project_id: 'project-banodoco',
        },
      ],
      error: null,
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    // banodoco-worker run_type is NOT passed into RPC's p_run_type (the RPC's
    // get_task_run_type filter only knows about gpu/api). Filtering happens
    // via p_worker_pool and p_task_types instead.
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', {
      p_worker_id: 'banodoco-worker-1',
      p_include_active: false,
      p_run_type: null,
      p_same_model_only: false,
      p_max_task_wait_minutes: 5,
      p_worker_pool: 'banodoco',
      p_task_types: ['banodoco_timeline_generate', 'banodoco_render_timeline'],
    });
    await expect(response.json()).resolves.toEqual({
      task_id: 'task-banodoco-1',
      params: { foo: 'bar' },
      task_type: 'banodoco_timeline_generate',
      project_id: 'project-banodoco',
    });
  });

  it('passes a single task_types entry through to the RPC', async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({
          worker_id: 'banodoco-worker-2',
          run_type: 'banodoco-worker',
          worker_pool: 'banodoco',
          task_types: ['banodoco_timeline_generate'],
        }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({
      data: [
        {
          task_id: 'task-banodoco-2',
          params: {},
          task_type: 'banodoco_timeline_generate',
          project_id: 'project-banodoco-2',
        },
      ],
      error: null,
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', expect.objectContaining({
      p_worker_pool: 'banodoco',
      p_task_types: ['banodoco_timeline_generate'],
    }));
  });

  it('rejects banodoco-worker run_type when worker_pool is not banodoco', async () => {
    // Without worker_pool='banodoco', the run_type 'banodoco-worker' is not
    // a recognized value and should be coerced to null. This prevents a
    // misconfigured worker from claiming everything as if it had no run_type
    // filter while still asserting it's a banodoco worker.
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({
          worker_id: 'rogue-worker',
          run_type: 'banodoco-worker',
          // worker_pool intentionally absent
        }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({ data: [], error: null });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(204);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', expect.objectContaining({
      p_run_type: null,
      p_worker_pool: null,
      p_task_types: null,
    }));
  });

  it('does not send banodoco worker_pool from gpu/api worker requests', async () => {
    // Sanity: gpu/api workers never set worker_pool, so they continue to call
    // the RPC with p_worker_pool=null and p_task_types=null. This guards
    // against accidentally narrowing their candidate set.
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({ run_type: 'gpu' }, { userId: null, isServiceRole: true }));
      },
    );

    mocks.rpc.mockResolvedValue({ data: [], error: null });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));

    expect(response.status).toBe(204);
    expect(mocks.rpc).toHaveBeenCalledWith('claim_next_task_service_role', expect.objectContaining({
      p_run_type: 'gpu',
      p_worker_pool: null,
      p_task_types: null,
    }));
  });
});
