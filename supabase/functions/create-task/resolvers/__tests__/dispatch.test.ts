import { beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../../../_tests/mocks/denoHttpServer.ts';
import { parseTaskCreationResponse } from '../../../../../src/shared/lib/taskCreation/parseTaskCreationResponse.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  enforceRateLimit: vi.fn(),
  parseCreateTaskBody: vi.fn(),
  buildTaskInsertObject: vi.fn(),
  getErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
  getTaskFamilyResolver: vi.fn(),
}));

vi.mock('https://deno.land/std@0.224.0/http/server.ts', async () => {
  const actual = await import('../../../_tests/mocks/denoHttpServer.ts');
  return {
    serve: actual.serve,
    __getServeHandler: actual.__getServeHandler,
    __resetServeHandler: actual.__resetServeHandler,
  };
});

vi.mock('../../../_shared/edgeHandler.ts', () => ({
  bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
  NO_SESSION_RUNTIME_OPTIONS: {},
}));

vi.mock('../../../_shared/rateLimit.ts', () => ({
  enforceRateLimit: (...args: unknown[]) => mocks.enforceRateLimit(...args),
  RATE_LIMITS: {
    taskCreation: { maxRequests: 20, windowSeconds: 60 },
  },
}));

vi.mock('../../request.ts', () => ({
  parseCreateTaskBody: (...args: unknown[]) => mocks.parseCreateTaskBody(...args),
  buildTaskInsertObject: (...args: unknown[]) => mocks.buildTaskInsertObject(...args),
  getErrorMessage: (...args: unknown[]) => mocks.getErrorMessage(...args),
}));

vi.mock('../registry.ts', () => ({
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

function createProjectsLookupChain(project: { user_id?: string; aspect_ratio?: string }) {
  const single = vi.fn().mockResolvedValue({ data: project, error: null });
  const eq = vi.fn().mockReturnValue({ single });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, single };
}

function createTaskTableChain(taskResponses: Array<{ type: 'insert' | 'lookup'; value: unknown }>) {
  let index = 0;

  const single = vi.fn().mockImplementation(() => {
    const next = taskResponses[index++];
    if (!next) {
      throw new Error('Unexpected tasks.single() call');
    }

    if (next.type === 'insert') {
      return Promise.resolve(next.value);
    }

    return Promise.resolve(next.value);
  });

  const eq = vi.fn().mockReturnValue({ single });
  const select = vi.fn().mockImplementation((columns?: string) => {
    if (columns === 'id') {
      return { single };
    }
    return { eq, single };
  });
  const insert = vi.fn().mockReturnValue({ select });

  return { insert, select, eq, single };
}

async function loadHandler() {
  vi.resetModules();
  vi.doMock('https://deno.land/std@0.224.0/http/server.ts', async () => {
    const actual = await import('../../../_tests/mocks/denoHttpServer.ts');
    return {
      serve: actual.serve,
      __getServeHandler: actual.__getServeHandler,
      __resetServeHandler: actual.__resetServeHandler,
    };
  });
  vi.doMock('../../../_shared/edgeHandler.ts', () => ({
    bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
    NO_SESSION_RUNTIME_OPTIONS: {},
  }));
  vi.doMock('../../../_shared/rateLimit.ts', () => ({
    enforceRateLimit: (...args: unknown[]) => mocks.enforceRateLimit(...args),
    RATE_LIMITS: {
      taskCreation: { maxRequests: 20, windowSeconds: 60 },
    },
  }));
  vi.doMock('../../request.ts', () => ({
    parseCreateTaskBody: (...args: unknown[]) => mocks.parseCreateTaskBody(...args),
    buildTaskInsertObject: (...args: unknown[]) => mocks.buildTaskInsertObject(...args),
    getErrorMessage: (...args: unknown[]) => mocks.getErrorMessage(...args),
  }));
  vi.doMock('../registry.ts', () => ({
    getTaskFamilyResolver: (...args: unknown[]) => mocks.getTaskFamilyResolver(...args),
  }));
  await import('../../index.ts');
  return __getServeHandler();
}

describe('create-task resolver dispatch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetServeHandler();
    mocks.enforceRateLimit.mockResolvedValue(null);
    mocks.parseCreateTaskBody.mockReturnValue({
      ok: true,
      value: {
        task_id: 'legacy-task-client-id',
        params: { prompt: 'legacy' },
        task_type: 'image_generation',
        project_id: 'project-1',
        normalizedDependantOn: null,
        idempotency_key: null,
      },
    });
  });

  it('dispatches family requests through the registered resolver', async () => {
    const logger = createLogger();
    const tasks = createTaskTableChain([
      {
        type: 'insert',
        value: { data: { id: 'task-created-1' }, error: null },
      },
    ]);

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

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {
          from: vi.fn().mockImplementation((table: string) => {
            if (table === 'tasks') return { insert: tasks.insert };
            if (table === 'projects') return createProjectsLookupChain({ user_id: 'user-1', aspect_ratio: '16:9' });
            throw new Error(`Unexpected table: ${table}`);
          }),
          rpc: vi.fn().mockResolvedValue({ data: 'image_upscale', error: null }),
        },
        logger,
        auth: { isServiceRole: false, isJwtAuth: true, userId: 'user-1' },
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
    expect(mocks.getTaskFamilyResolver).toHaveBeenCalledWith('image_upscale');
    expect(mocks.parseCreateTaskBody).not.toHaveBeenCalled();
  });

  it('returns recovered and newly inserted task ids for batched resolver requests', async () => {
    const logger = createLogger();
    const duplicateError = {
      code: '23505',
      message: 'duplicate key value violates unique constraint on idempotency_key',
    };
    const tasks = createTaskTableChain([
      {
        type: 'insert',
        value: { data: null, error: duplicateError },
      },
      {
        type: 'lookup',
        value: { data: { id: 'task-existing-1', status: 'Queued', project_id: 'project-1' }, error: null },
      },
      {
        type: 'insert',
        value: { data: { id: 'task-created-2' }, error: null },
      },
    ]);

    mocks.getTaskFamilyResolver.mockReturnValue(
      vi.fn().mockResolvedValue({
        tasks: [
          {
            project_id: 'project-1',
            task_type: 'z_image_turbo_i2i',
            params: { image_url: 'https://example.com/one.png', seed: 111 },
            status: 'Queued',
          },
          {
            project_id: 'project-1',
            task_type: 'z_image_turbo_i2i',
            params: { image_url: 'https://example.com/two.png', seed: 112 },
            status: 'Queued',
          },
        ],
      }),
    );

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {
          from: vi.fn().mockImplementation((table: string) => {
            if (table === 'tasks') {
              return {
                insert: tasks.insert,
                select: tasks.select,
              };
            }
            if (table === 'projects') return createProjectsLookupChain({ aspect_ratio: '16:9' });
            throw new Error(`Unexpected table: ${table}`);
          }),
          rpc: vi.fn().mockResolvedValue({ data: 'z_image_turbo_i2i', error: null }),
        },
        logger,
        auth: { isServiceRole: true, userId: null },
        body: {
          family: 'z_image_turbo_i2i',
          project_id: 'project-1',
          input: { image_url: 'https://example.com/source.png', numImages: 2 },
          idempotency_key: 'stable-request-key',
        },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/create-task', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      task_ids: ['task-existing-1', 'task-created-2'],
      status: 'Task queued',
    });
  });
});

describe('parseTaskCreationResponse', () => {
  const context = {
    requestId: 'request-1',
    taskType: 'image_generation',
    projectId: 'project-1',
  };

  it('parses single-task responses', () => {
    expect(parseTaskCreationResponse({
      task_id: 'task-1',
      status: 'Task queued',
    }, context)).toEqual({
      task_id: 'task-1',
      status: 'Task queued',
    });
  });

  it('parses batch responses and preserves meta', () => {
    expect(parseTaskCreationResponse({
      task_ids: ['task-1', 'task-2'],
      status: 'Task queued',
      meta: { parentGenerationId: 'parent-1' },
    }, context)).toEqual({
      task_id: 'task-1',
      task_ids: ['task-1', 'task-2'],
      status: 'Task queued',
      meta: { parentGenerationId: 'parent-1' },
    });
  });
});
