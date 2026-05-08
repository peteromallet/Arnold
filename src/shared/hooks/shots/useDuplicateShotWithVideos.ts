import type { QueryClient } from '@tanstack/react-query';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import type { Shot } from '@/domains/generation/types';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { queryKeys } from '@/shared/lib/queryKeys';

import { invalidateShotsQueries, upsertShotInCache } from './cacheUtils';

type DuplicateShotWithVideosInput = {
  shotId: string;
  projectId: string;
};

type DuplicateShotWithVideosResult = {
  shot_id?: unknown;
};

function extractDuplicatedShotId(data: unknown): string {
  if (typeof data === 'string' && data.length > 0) {
    return data;
  }

  if (data && typeof data === 'object') {
    const { shot_id } = data as DuplicateShotWithVideosResult;
    if (typeof shot_id === 'string' && shot_id.length > 0) {
      return shot_id;
    }
  }

  throw new Error('duplicate_shot_with_videos did not return a cloned shot id');
}

function invalidateShotScopedGraphCaches(
  queryClient: QueryClient,
  shotId: string,
  projectId: string,
): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.shots.detail(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.byShot(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.meta(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.unpositionedCount(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.lastVideo(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.segments.liveTimeline(shotId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.segments.parents(shotId, projectId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.segments.parents(shotId) });
}

function invalidateDuplicateWithVideosCaches(
  queryClient: QueryClient,
  projectId: string,
  sourceShotId: string,
  clonedShotId: string,
): void {
  invalidateShotsQueries(queryClient, projectId);

  for (const shotId of new Set([sourceShotId, clonedShotId])) {
    invalidateShotScopedGraphCaches(queryClient, shotId, projectId);
  }

  queryClient.invalidateQueries({ queryKey: queryKeys.finalVideos.byProject(projectId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.byProject(projectId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.variantsAll });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.derivedAll });
  queryClient.invalidateQueries({ queryKey: queryKeys.generations.derivedGenerationsAll });
  queryClient.invalidateQueries({ queryKey: queryKeys.unified.projectPrefix(projectId) });

  queryClient.invalidateQueries({
    predicate: (query) => query.queryKey[0] === queryKeys.segments.childrenAll[0],
  });
  queryClient.invalidateQueries({
    predicate: (query) => query.queryKey[0] === queryKeys.segments.sourceSlotAll[0],
  });
}

export const useDuplicateShotWithVideos = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ shotId, projectId }: DuplicateShotWithVideosInput): Promise<Shot> => {
      const { data, error } = await supabase().rpc('duplicate_shot_with_videos', {
        original_shot_id: shotId,
        project_id: projectId,
      });

      if (error) throw error;

      const clonedShotId = extractDuplicatedShotId(data);

      const { data: shotData, error: fetchError } = await supabase().from('shots')
        .select()
        .eq('id', clonedShotId)
        .single();

      if (fetchError) throw fetchError;

      return shotData as Shot;
    },

    onSuccess: (data, variables) => {
      upsertShotInCache(queryClient, variables.projectId, data);
      invalidateDuplicateWithVideosCaches(queryClient, variables.projectId, variables.shotId, data.id);
    },

    onError: (error: Error) => {
      normalizeAndPresentError(error, {
        context: 'useDuplicateShotWithVideos',
        toastTitle: 'Failed to duplicate shot with videos',
      });
    },
  });
};
