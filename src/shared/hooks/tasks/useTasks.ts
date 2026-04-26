import { useEffect } from 'react';
import { keepPreviousData, useQuery, useQueryClient, type QueryClient, type UseQueryOptions } from '@tanstack/react-query';
import { Task, TaskStatus } from '@/types/tasks';
import { getSupabaseClientResult } from '@/integrations/supabase/client';
import { getVisibleTaskTypes } from '@/shared/lib/tasks/taskConfig';
import { normalizeAndPresentAndRethrow } from '@/shared/lib/errorHandling/runtimeError';
// Removed invalidationRouter - DataFreshnessManager handles all invalidation logic
import { useSmartPollingConfig } from '@/shared/hooks/useSmartPolling';
import { QUERY_PRESETS, STANDARD_RETRY, STANDARD_RETRY_DELAY } from '@/shared/lib/query/queryDefaults';
import { taskQueryKeys } from '@/shared/lib/queryKeys/tasks';
import { useProcessingRefetchGuard } from '@/shared/hooks/tasks/useProcessingRefetchGuard';
import {
  notifyPaginatedTaskFetchFailure,
  notifyPaginatedTaskFetchSuccess,
} from '@/shared/realtime/dataFreshness/taskFetchFreshness';
import {
  fetchPaginatedTasks,
  mapDbTaskToTask,
  type PaginatedTaskQuery,
  type PaginatedTasksResponse as RepositoryPaginatedTasksResponse,
} from '@/shared/hooks/tasks/paginatedTaskRepository';
import { resolveTaskProjectScope } from '@/shared/lib/tasks/resolveTaskProjectScope';
import {
  getRealtimeTaskSnapshot,
  useRealtimeTask,
  upsertRealtimeTaskSnapshot,
} from '@/shared/state/realtimeStore';

// Types for API responses and request bodies
// Ensure these align with your server-side definitions and Task type in @/types/tasks.ts

interface PaginatedTasksParams {
  projectId?: string | null;
  status?: TaskStatus[];
  limit?: number;
  offset?: number;
  taskType?: string | null; // Filter by specific task type
  allProjects?: boolean; // If true, query across all projects
  allProjectIds?: string[]; // List of project IDs to query when allProjects is true
}

export type PaginatedTasksResponse = RepositoryPaginatedTasksResponse;
function createPaginatedTasksQueryFn(filters: PaginatedTaskQuery, cacheProjectKey: string) {
  return async (): Promise<PaginatedTasksResponse> => {
    try {
      const result = await fetchPaginatedTasks(filters);
      notifyPaginatedTaskFetchSuccess(cacheProjectKey);
      return result;
    } catch (error) {
      notifyPaginatedTaskFetchFailure(cacheProjectKey, error);
      normalizeAndPresentAndRethrow(error, {
        context: 'useTasks.fetchPaginatedTasks',
        showToast: false,
        logData: { cacheProjectKey },
      });
    }
  };
}

// Helper to convert DB row (snake_case) to Task interface (camelCase)
// Exported for use in prefetch utilities
export { mapDbTaskToTask };

function seedTaskSnapshot(task: Task | null | undefined, projectId?: string | null): Task | null | undefined {
  if (!task) {
    return task;
  }

  return upsertRealtimeTaskSnapshot(task, projectId) ?? task;
}

async function fetchSingleTask(taskId: string, projectId?: string | null): Promise<Task | null> {
  const effectiveProjectId = resolveTaskProjectScope(projectId);
  const supabaseResult = getSupabaseClientResult();
  if (!supabaseResult.ok) {
    normalizeAndPresentAndRethrow(supabaseResult.error, {
      context: 'useTasks.useGetTask',
      showToast: false,
      logData: { taskId, projectId: effectiveProjectId },
    });
  }

  const { data, error } = await supabaseResult.client
    .from('tasks')
    .select('*')
    .eq('id', taskId)
    .eq('project_id', effectiveProjectId!)
    .maybeSingle();

  if (error) {
    normalizeAndPresentAndRethrow(error, {
      context: 'useTasks.useGetTask',
      showToast: false,
      logData: { taskId, projectId: effectiveProjectId },
    });
  }

  if (!data) {
    return null;
  }

  return seedTaskSnapshot(mapDbTaskToTask(data), effectiveProjectId) ?? null;
}

export function getCachedTaskSnapshot(
  queryClient: QueryClient,
  taskId: string,
  projectId?: string | null,
): Task | null | undefined {
  const effectiveProjectId = resolveTaskProjectScope(projectId);
  if (!taskId || !effectiveProjectId) {
    return undefined;
  }

  const storeTask = getRealtimeTaskSnapshot(taskId, effectiveProjectId);
  if (storeTask) {
    return storeTask;
  }

  const cachedTask = queryClient.getQueryData<Task | null>(
    taskQueryKeys.single(taskId, effectiveProjectId),
  );
  return seedTaskSnapshot(cachedTask, effectiveProjectId);
}

export function createSingleTaskQueryOptions(
  taskId: string,
  projectId?: string | null,
): UseQueryOptions<Task | null, Error> {
  const effectiveProjectId = resolveTaskProjectScope(projectId);

  return {
    queryKey: taskQueryKeys.single(taskId, effectiveProjectId),
    queryFn: () => fetchSingleTask(taskId, effectiveProjectId),
    enabled: !!taskId && !!effectiveProjectId,
    ...QUERY_PRESETS.immutable,
  };
}

export async function fetchAndSeedTaskQuery(
  queryClient: QueryClient,
  taskId: string,
  projectId?: string | null,
): Promise<Task | null> {
  return queryClient.fetchQuery(createSingleTaskQueryOptions(taskId, projectId));
}

// Hook to get a single task by ID
// Uses IMMUTABLE_PRESET since task data rarely changes after creation
export const useGetTask = (taskId: string, projectId?: string | null) => {
  const effectiveProjectId = resolveTaskProjectScope(projectId);
  const queryClient = useQueryClient();
  const storeTask = useRealtimeTask(taskId, effectiveProjectId);

  useEffect(() => {
    getCachedTaskSnapshot(queryClient, taskId, effectiveProjectId);
  }, [effectiveProjectId, queryClient, taskId]);

  const query = useQuery<Task | null, Error>(createSingleTaskQueryOptions(taskId, effectiveProjectId));

  useEffect(() => {
    if (query.data !== undefined) {
      seedTaskSnapshot(query.data, effectiveProjectId);
    }
  }, [effectiveProjectId, query.data]);

  return {
    ...query,
    data: storeTask ?? query.data,
  };
};

// Hook to list tasks with pagination - GALLERY PATTERN
export const usePaginatedTasks = (params: PaginatedTasksParams) => {
  const { projectId, status, limit = 50, offset = 0, taskType, allProjects, allProjectIds } = params;
  const page = Math.floor(offset / limit) + 1;
  const effectiveProjectId: string | null = projectId ?? null;
  const cacheProjectKey = allProjects ? 'all' : effectiveProjectId;
  const safeCacheProjectKey = cacheProjectKey ?? '__no-project__';
  const visibleTaskTypes = getVisibleTaskTypes();
  const smartPollingConfig = useSmartPollingConfig(taskQueryKeys.paginated(safeCacheProjectKey));

  const query = useQuery<PaginatedTasksResponse, Error>({
    queryKey: [...taskQueryKeys.paginated(safeCacheProjectKey), page, limit, status, taskType],
    queryFn: createPaginatedTasksQueryFn({
      allProjects,
      allProjectIds,
      effectiveProjectId,
      status,
      taskType,
      visibleTaskTypes,
      limit,
      offset,
      page,
    }, safeCacheProjectKey),
    enabled: allProjects ? !!allProjectIds?.length : !!effectiveProjectId,
    placeholderData: keepPreviousData,
    ...QUERY_PRESETS.realtimeBacked,
    ...smartPollingConfig,
    refetchIntervalInBackground: true,
    retry: STANDARD_RETRY,
    retryDelay: STANDARD_RETRY_DELAY,
  });

  useProcessingRefetchGuard(status, query);

  return query;
};
