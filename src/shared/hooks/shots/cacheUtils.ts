import type { InvalidateQueryFilters, QueryClient, QueryKey } from '@tanstack/react-query';
import { Shot, GenerationRow } from '@/domains/generation/types';
import { queryKeys } from '@/shared/lib/queryKeys';

function getShotsProjectPrefix(projectId: string): QueryKey {
  return [...queryKeys.shots.all, projectId] as const;
}

function getShotListQueries(queryClient: QueryClient, projectId: string) {
  return queryClient.getQueriesData<Shot[]>({
    queryKey: getShotsProjectPrefix(projectId),
  });
}

/**
 * @param onlyExisting - If true, only update caches that already exist.
 *                       If false (default), will create cache entries if needed.
 */
export function updateAllShotsCaches(
  queryClient: QueryClient,
  projectId: string,
  updater: (old: Shot[] | undefined) => Shot[],
  onlyExisting: boolean = false
): void {
  const cachedQueries = getShotListQueries(queryClient, projectId);
  if (cachedQueries.length === 0) {
    if (!onlyExisting) {
      queryClient.setQueryData<Shot[]>(
        queryKeys.shots.list(projectId, 0),
        (old) => updater(old)
      );
    }
    return;
  }

  cachedQueries.forEach(([key, existing]) => {
    if (onlyExisting && existing === undefined) {
      return;
    }
    queryClient.setQueryData<Shot[]>(key, (old) => updater(old));
  });
}

export function rollbackShotsCaches(
  queryClient: QueryClient,
  projectId: string,
  previous: Shot[] | undefined
): void {
  if (!previous) return;
  const cachedQueries = getShotListQueries(queryClient, projectId);
  if (cachedQueries.length === 0) {
    queryClient.setQueryData(queryKeys.shots.list(projectId, 0), previous);
    return;
  }

  cachedQueries.forEach(([key]) => {
    queryClient.setQueryData(key, previous);
  });
}

export async function cancelShotsQueries(
  queryClient: QueryClient,
  projectId: string
): Promise<void> {
  await queryClient.cancelQueries({ queryKey: getShotsProjectPrefix(projectId) });
}

export function invalidateShotsQueries(
  queryClient: QueryClient,
  projectId: string,
  filters: Omit<InvalidateQueryFilters, 'queryKey'> = {},
): void {
  queryClient.invalidateQueries({
    queryKey: [...queryKeys.shots.all, projectId],
    ...filters,
  });
}

export function findShotsCache(
  queryClient: QueryClient,
  projectId: string
): Shot[] | undefined {
  const cachedQueries = getShotListQueries(queryClient, projectId);
  for (const [, data] of cachedQueries) {
    if (data && data.length > 0) {
      return data;
    }
  }
  for (const [, data] of cachedQueries) {
    if (data !== undefined) {
      return data;
    }
  }
  return undefined;
}

export function upsertShotInCache(
  queryClient: QueryClient,
  projectId: string,
  shot: Shot
): void {
  const shotPosition = shot.position ?? Number.MAX_SAFE_INTEGER;

  updateAllShotsCaches(queryClient, projectId, (oldShots = []) => {
    const remainingShots = oldShots.filter((existingShot) => existingShot.id !== shot.id);
    const insertionIndex = remainingShots.findIndex(
      (existingShot) => (existingShot.position ?? Number.MAX_SAFE_INTEGER) > shotPosition
    );

    if (insertionIndex === -1) {
      return [...remainingShots, shot];
    }

    const updatedShots = [...remainingShots];
    updatedShots.splice(insertionIndex, 0, shot);
    return updatedShots;
  });

  queryClient.setQueryData(queryKeys.shots.detail(shot.id), shot);
}

export function rollbackShotGenerationsCache(
  queryClient: QueryClient,
  shotId: string,
  previous: GenerationRow[] | undefined
): void {
  if (!previous) return;
  queryClient.setQueryData(queryKeys.generations.byShot(shotId), previous);
}

export async function cancelShotGenerationsQuery(
  queryClient: QueryClient,
  shotId: string
): Promise<void> {
  await queryClient.cancelQueries({ queryKey: queryKeys.generations.byShot(shotId) });
}
