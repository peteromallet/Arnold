import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { taskReferencesGeneration } from '@/shared/hooks/tasks/usePendingGenerationTasks';
import { realtimeEventProcessor } from '@/shared/realtime/RealtimeEventProcessor';
import { TASK_STATUS } from '@/types/tasks';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import type { ResolvedAssetRegistryEntry } from '@/tools/video-editor/types';

interface UseActiveTaskClipsArgs {
  registry: Record<string, ResolvedAssetRegistryEntry> | undefined;
}

interface UseActiveTaskClipsReturn {
  activeTaskAssetKeys: Set<string>;
}

interface ActiveTaskRow {
  id: string;
  status: string;
  task_type: string;
  params: Record<string, unknown> | null;
}

const ACTIVE_TASK_CLIPS_QUERY_KEY = 'active-task-clips';
const OPTIMISTIC_TIMEOUT_MS = 8000;

const optimisticListeners = new Set<() => void>();
const optimisticTimeouts = new Map<string, ReturnType<typeof setTimeout>>();
let optimisticActiveAssetKeysSnapshot = new Set<string>();

function activeTaskClipsQueryKey(projectId: string | null) {
  return [ACTIVE_TASK_CLIPS_QUERY_KEY, projectId ?? '__no-project__'] as const;
}

function emitOptimisticChange() {
  optimisticListeners.forEach((listener) => listener());
}

function subscribeOptimisticActive(listener: () => void) {
  optimisticListeners.add(listener);
  return () => optimisticListeners.delete(listener);
}

function getOptimisticActiveSnapshot() {
  return optimisticActiveAssetKeysSnapshot;
}

function removeOptimisticActive(assetKeys: Iterable<string>) {
  let nextSnapshot: Set<string> | null = null;

  for (const assetKey of assetKeys) {
    if (!optimisticActiveAssetKeysSnapshot.has(assetKey)) {
      continue;
    }

    if (!nextSnapshot) {
      nextSnapshot = new Set(optimisticActiveAssetKeysSnapshot);
    }

    nextSnapshot.delete(assetKey);

    const timeout = optimisticTimeouts.get(assetKey);
    if (timeout) {
      clearTimeout(timeout);
      optimisticTimeouts.delete(assetKey);
    }
  }

  if (!nextSnapshot) {
    return;
  }

  optimisticActiveAssetKeysSnapshot = nextSnapshot;
  emitOptimisticChange();
}

function scheduleOptimisticExpiry(assetKey: string) {
  const existingTimeout = optimisticTimeouts.get(assetKey);
  if (existingTimeout) {
    clearTimeout(existingTimeout);
  }

  const timeout = setTimeout(() => {
    optimisticTimeouts.delete(assetKey);

    if (!optimisticActiveAssetKeysSnapshot.has(assetKey)) {
      return;
    }

    const nextSnapshot = new Set(optimisticActiveAssetKeysSnapshot);
    nextSnapshot.delete(assetKey);
    optimisticActiveAssetKeysSnapshot = nextSnapshot;
    emitOptimisticChange();
  }, OPTIMISTIC_TIMEOUT_MS);

  optimisticTimeouts.set(assetKey, timeout);
}

export function addOptimisticActive(assetKeys: string[]) {
  let nextSnapshot: Set<string> | null = null;

  for (const assetKey of assetKeys) {
    if (!assetKey) {
      continue;
    }

    if (!optimisticActiveAssetKeysSnapshot.has(assetKey)) {
      if (!nextSnapshot) {
        nextSnapshot = new Set(optimisticActiveAssetKeysSnapshot);
      }
      nextSnapshot.add(assetKey);
    }

    scheduleOptimisticExpiry(assetKey);
  }

  if (!nextSnapshot) {
    return;
  }

  optimisticActiveAssetKeysSnapshot = nextSnapshot;
  emitOptimisticChange();
}

async function fetchActiveTasks(projectId: string): Promise<ActiveTaskRow[]> {
  const { getSupabaseClient } = await import('@/integrations/supabase/client');
  const { data, error } = await getSupabaseClient()
    .from('tasks')
    .select('id, status, task_type, params')
    .eq('project_id', projectId)
    .in('status', [TASK_STATUS.QUEUED, TASK_STATUS.IN_PROGRESS]);

  if (error) {
    throw error;
  }

  return (data ?? []).map((task) => ({
    id: task.id,
    status: task.status,
    task_type: task.task_type,
    params: task.params as Record<string, unknown> | null,
  }));
}

export function useActiveTaskClips({ registry }: UseActiveTaskClipsArgs): UseActiveTaskClipsReturn {
  const selectedProjectId = useVideoEditorRuntime().project.projectId;
  const queryClient = useQueryClient();
  const optimisticActiveAssetKeys = useSyncExternalStore(
    subscribeOptimisticActive,
    getOptimisticActiveSnapshot,
    getOptimisticActiveSnapshot
  );

  const generationAssetMap = useMemo(() => {
    const map = new Map<string, string[]>();

    if (!registry) {
      return map;
    }

    for (const [assetKey, entry] of Object.entries(registry)) {
      if (!entry.generationId) {
        continue;
      }

      const assetKeys = map.get(entry.generationId);
      if (assetKeys) {
        assetKeys.push(assetKey);
      } else {
        map.set(entry.generationId, [assetKey]);
      }
    }

    return map;
  }, [registry]);

  const { data: activeTasks = [] } = useQuery({
    queryKey: activeTaskClipsQueryKey(selectedProjectId),
    queryFn: async () => {
      if (!selectedProjectId) {
        return [];
      }

      return fetchActiveTasks(selectedProjectId);
    },
    enabled: !!selectedProjectId,
    refetchInterval: 5000,
    staleTime: 0,
    gcTime: 10000,
    refetchOnWindowFocus: 'always',
  });

  const queriedActiveAssetKeys = useMemo(() => {
    const activeAssetKeys = new Set<string>();

    if (generationAssetMap.size === 0 || activeTasks.length === 0) {
      return activeAssetKeys;
    }

    for (const task of activeTasks) {
      for (const [generationId, assetKeys] of generationAssetMap.entries()) {
        if (!taskReferencesGeneration(task.params, generationId)) {
          continue;
        }

        assetKeys.forEach((assetKey) => activeAssetKeys.add(assetKey));
      }
    }

    return activeAssetKeys;
  }, [activeTasks, generationAssetMap]);

  useEffect(() => {
    if (queriedActiveAssetKeys.size === 0) {
      return;
    }

    removeOptimisticActive(queriedActiveAssetKeys);
  }, [queriedActiveAssetKeys]);

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }

    return realtimeEventProcessor.onEvent((event) => {
      if (event.type === 'tasks-created') {
        const projectMatch = event.tasks.some((task) => task.projectId === selectedProjectId);
        if (projectMatch) {
          void queryClient.invalidateQueries({ queryKey: activeTaskClipsQueryKey(selectedProjectId) });
        }
        return;
      }

      if (event.type === 'tasks-updated') {
        const projectMatch = event.tasks.some((task) => task.projectId === selectedProjectId);
        if (projectMatch) {
          void queryClient.invalidateQueries({ queryKey: activeTaskClipsQueryKey(selectedProjectId) });
        }
      }
    });
  }, [queryClient, selectedProjectId]);

  const activeTaskAssetKeys = useMemo(() => {
    if (queriedActiveAssetKeys.size === 0) {
      return optimisticActiveAssetKeys;
    }

    if (optimisticActiveAssetKeys.size === 0) {
      return queriedActiveAssetKeys;
    }

    const next = new Set(queriedActiveAssetKeys);
    optimisticActiveAssetKeys.forEach((assetKey) => next.add(assetKey));
    return next;
  }, [optimisticActiveAssetKeys, queriedActiveAssetKeys]);

  return {
    activeTaskAssetKeys,
  };
}
