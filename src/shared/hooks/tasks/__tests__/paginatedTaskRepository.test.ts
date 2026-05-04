import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TASK_STATUS } from '@/types/tasks';
import { fetchPaginatedTasks } from '../paginatedTaskRepository';

const mocks = vi.hoisted(() => ({
  getSupabaseClient: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: mocks.getSupabaseClient,
}));

vi.mock('@/shared/lib/tasks/taskConfig', () => ({
  filterVisibleTasks: <T,>(tasks: T[]): T[] => tasks,
}));

interface QueryCapture {
  limit?: number;
  range?: [number, number];
}

interface QueryResult {
  count?: number | null;
  data?: unknown[] | null;
  error: Error | null;
}

function createThenableQuery(result: QueryResult, capture?: QueryCapture) {
  const query = {
    is: vi.fn(() => query),
    in: vi.fn(() => query),
    eq: vi.fn(() => query),
    order: vi.fn(() => query),
    limit: vi.fn((value: number) => {
      if (capture) {
        capture.limit = value;
      }
      return query;
    }),
    range: vi.fn((from: number, to: number) => {
      if (capture) {
        capture.range = [from, to];
      }
      return query;
    }),
    then: (
      onFulfilled?: (value: QueryResult) => unknown,
      onRejected?: (reason: unknown) => unknown,
    ) => Promise.resolve(result).then(onFulfilled, onRejected),
  };

  return query;
}

function buildTaskRow(index: number, status = TASK_STATUS.QUEUED) {
  return {
    id: `task-${index}`,
    task_type: 'text_to_image',
    params: {},
    status,
    created_at: new Date(Date.UTC(2026, 0, 1, 0, index, 0)).toISOString(),
    project_id: 'project-1',
  };
}

describe('fetchPaginatedTasks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches enough processing rows to serve page 2 slicing', async () => {
    const dataCapture: QueryCapture = {};
    const countQuery = createThenableQuery({ count: 120, error: null });
    const dataQuery = createThenableQuery(
      {
        data: Array.from({ length: 100 }, (_, index) => buildTaskRow(index)),
        error: null,
      },
      dataCapture,
    );

    mocks.getSupabaseClient.mockReturnValue({
      from: vi.fn(() => ({
        select: vi.fn((_columns: string, options?: { head?: boolean }) => (
          options?.head ? countQuery : dataQuery
        )),
      })),
    });

    const result = await fetchPaginatedTasks({
      allProjects: false,
      effectiveProjectId: 'project-1',
      status: [TASK_STATUS.QUEUED, TASK_STATUS.IN_PROGRESS],
      taskType: null,
      visibleTaskTypes: ['text_to_image'],
      limit: 50,
      offset: 50,
      page: 2,
    });

    expect(dataCapture.limit).toBe(100);
    expect(result.tasks).toHaveLength(50);
    expect(result.tasks[0]?.id).toBe('task-50');
    expect(result.hasMore).toBe(true);
  });

  it('uses server-side range pagination for non-processing filters', async () => {
    const dataCapture: QueryCapture = {};
    const countQuery = createThenableQuery({ count: 80, error: null });
    const dataQuery = createThenableQuery(
      {
        data: Array.from({ length: 25 }, (_, index) => buildTaskRow(index, TASK_STATUS.COMPLETE)),
        error: null,
      },
      dataCapture,
    );

    mocks.getSupabaseClient.mockReturnValue({
      from: vi.fn(() => ({
        select: vi.fn((_columns: string, options?: { head?: boolean }) => (
          options?.head ? countQuery : dataQuery
        )),
      })),
    });

    await fetchPaginatedTasks({
      allProjects: false,
      effectiveProjectId: 'project-1',
      status: [TASK_STATUS.COMPLETE],
      taskType: null,
      visibleTaskTypes: ['text_to_image'],
      limit: 25,
      offset: 50,
      page: 3,
    });

    expect(dataCapture.range).toEqual([50, 74]);
    expect(dataCapture.limit).toBeUndefined();
  });
});
