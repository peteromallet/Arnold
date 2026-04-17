/**
 * Utilities for prefetching generation-linked task data.
 *
 * The canonical generation -> task mapping query lives in the generation
 * domain; this module only handles best-effort prefetch.
 */

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { taskQueryKeys } from '@/shared/lib/queryKeys/tasks';
import { isUuid } from '@/shared/lib/uuid';
import type { GenerationTaskMappingCacheEntry } from '@/shared/lib/tasks/generationTaskRepository';
import { resolveTaskProjectScope } from '@/shared/lib/tasks/resolveTaskProjectScope';
import { prefetchGenerationTaskMapping } from '@/domains/generation/hooks/tasks/useGenerationTaskMapping';
import { fetchAndSeedTaskQuery, getCachedTaskSnapshot } from './useTasks';

/**
 * Hook to prefetch task data for a generation on hover.
 * Returns a function that can be called onMouseEnter to prefetch
 * both the task ID mapping and the full task data.
 */
export function usePrefetchTaskData() {
  const queryClient = useQueryClient();

  const prefetch = useCallback(async (generationId: string, projectId?: string | null) => {
    const effectiveProjectId = resolveTaskProjectScope(projectId);
    if (!generationId || !effectiveProjectId || !isUuid(generationId)) return;

    // Check if task ID mapping is already cached (including { taskId: null } for no-task generations)
    let taskId: string | null = null;
    const cachedMapping = queryClient.getQueryData(taskQueryKeys.generationMapping(generationId)) as GenerationTaskMappingCacheEntry | undefined;

    if (cachedMapping !== undefined) {
      // Already cached - use the cached value (could be null if no task)
      taskId = cachedMapping.taskId;
    } else {
      // Not cached - fetch the task ID mapping
      try {
        const result = await prefetchGenerationTaskMapping(queryClient, generationId);
        taskId = result?.taskId ?? null;
      } catch {
        return;
      }
    }

    // Prefetch the full task data if we have a task ID and it's not cached
    if (taskId) {
      const cachedTask = getCachedTaskSnapshot(queryClient, taskId, effectiveProjectId);
      if (!cachedTask) {
        try {
          await fetchAndSeedTaskQuery(queryClient, taskId, effectiveProjectId);
        } catch {
          // Silently fail - prefetch is best-effort
        }
      }
    }
  }, [queryClient]);

  return prefetch;
}

/**
 * Hook to prefetch a task directly by task ID.
 * Use this when you already have the task ID (e.g., from variant.params.source_task_id).
 */
export function usePrefetchTaskById() {
  const queryClient = useQueryClient();

  const prefetch = useCallback(async (taskId: string, projectId?: string | null) => {
    const effectiveProjectId = resolveTaskProjectScope(projectId);
    if (!taskId || !effectiveProjectId || !isUuid(taskId)) return;

    // Check if already cached
    const cached = getCachedTaskSnapshot(queryClient, taskId, effectiveProjectId);
    if (cached) {
      return;
    }

    try {
      await fetchAndSeedTaskQuery(queryClient, taskId, effectiveProjectId);
    } catch {
      // Silently fail - prefetch is best-effort
    }
  }, [queryClient]);

  return prefetch;
}
