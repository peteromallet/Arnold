import { QueryClient } from '@tanstack/react-query';
import type { GenerationRow } from '@/domains/generation/types';
import { Task } from '@/types/tasks';
import { taskQueryKeys } from '@/shared/lib/queryKeys/tasks';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { resolveTaskProjectScope } from '@/shared/lib/tasks/resolveTaskProjectScope';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { fetchAndSeedTaskQuery, getCachedTaskSnapshot } from '@/shared/hooks/tasks/useTasks';
import {
  resolveGenerationTaskMappings,
  toGenerationTaskMappingCacheEntry,
  type GenerationTaskMappingCacheEntry,
  type GenerationTaskMappingStatus,
} from '@/shared/lib/tasks/generationTaskRepository';

interface PreloadGenerationTaskMappingsOptions {
  batchSize?: number;
  delayBetweenBatches?: number;
  preloadFullTaskData?: boolean;
}

interface GenerationWithTaskData extends GenerationRow {
  taskId?: string | null;
  taskData?: Task | null;
  taskMappingStatus?: GenerationTaskMappingStatus;
  taskMappingError?: string;
}

/** Preload cached generation -> task mappings for a batch of generations. */
export async function preloadGenerationTaskMappings(
  queryClient: QueryClient,
  generationIds: string[],
  projectId: string | null,
  options: PreloadGenerationTaskMappingsOptions = {},
) {
  const effectiveProjectId = resolveTaskProjectScope(projectId);
  const {
    batchSize = 5,
    delayBetweenBatches = 200,
    preloadFullTaskData = false,
  } = options;

  for (let i = 0; i < generationIds.length; i += batchSize) {
    const batch = generationIds.slice(i, i + batchSize);

    const mappings = await resolveGenerationTaskMappings(batch, {
      projectId: effectiveProjectId ?? undefined,
    });
    let reportedBatchQueryFailure = false;

    const prefetchTasks: Array<Promise<unknown>> = [];

    batch.forEach((generationId) => {
      const mapping = mappings.get(generationId);
      const cacheEntry = toGenerationTaskMappingCacheEntry(mapping);
      queryClient.setQueryData<GenerationTaskMappingCacheEntry>(
        taskQueryKeys.generationMapping(generationId),
        cacheEntry,
      );

      if (!reportedBatchQueryFailure && cacheEntry.status === 'query_failed' && cacheEntry.queryError) {
        reportedBatchQueryFailure = true;
        normalizeAndPresentError(new Error(cacheEntry.queryError), {
          context: 'GenerationTaskCache',
          showToast: false,
        });
      }

      if (preloadFullTaskData && effectiveProjectId && cacheEntry.taskId && cacheEntry.status === 'ok') {
        prefetchTasks.push(fetchAndSeedTaskQuery(queryClient, cacheEntry.taskId, effectiveProjectId));
      }
    });

    if (prefetchTasks.length > 0) {
      await Promise.all(prefetchTasks);
    }

    if (i + batchSize < generationIds.length) {
      await new Promise((resolve) => setTimeout(resolve, delayBetweenBatches));
    }
  }
}

export function mergeGenerationsWithTaskData(
  generations: GenerationRow[],
  queryClient: QueryClient,
  projectId: string | null,
): GenerationWithTaskData[] {
  const effectiveProjectId = resolveTaskProjectScope(projectId);

  return generations.map((generation) => {
    const generationId = getGenerationId(generation);
    const cachedMapping = queryClient.getQueryData<GenerationTaskMappingCacheEntry>(
      taskQueryKeys.generationMapping(generationId),
    );
    const taskId = cachedMapping?.taskId || null;
    const taskData = (taskId && effectiveProjectId)
      ? getCachedTaskSnapshot(queryClient, taskId, effectiveProjectId) ?? null
      : null;
    const taskMappingStatus = cachedMapping?.status ?? (taskId ? 'ok' : 'not_loaded');

    return {
      ...generation,
      taskId,
      taskData,
      taskMappingStatus,
      ...(cachedMapping?.queryError ? { taskMappingError: cachedMapping.queryError } : {}),
    };
  });
}
