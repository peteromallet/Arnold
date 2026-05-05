import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef } from 'react';
import type { DataProvider, LoadedTimeline } from '@/tools/video-editor/data/DataProvider.ts';
import type { TimelineConfig } from '@/tools/video-editor/types/index.ts';

export const timelineQueryKey = (timelineId: string | null | undefined) => ['timeline', timelineId] as const;
export const assetRegistryQueryKey = (timelineId: string | null | undefined) => ['asset-registry', timelineId] as const;

export function useTimeline(provider: DataProvider | null, timelineId: string | null | undefined) {
  const queryClient = useQueryClient();
  const configVersionRef = useRef(1);

  const timelineQuery = useQuery({
    queryKey: timelineQueryKey(timelineId),
    enabled: Boolean(provider && timelineId),
    queryFn: async () => {
      const timeline = await provider!.loadTimeline(timelineId!);
      configVersionRef.current = timeline.configVersion;
      return timeline;
    },
  });

  const saveTimeline = useMutation({
    mutationFn: async (config: TimelineConfig) => {
      const nextVersion = await provider!.saveTimeline(
        timelineId!,
        config,
        configVersionRef.current,
      );
      configVersionRef.current = nextVersion;
      return { config, configVersion: nextVersion };
    },
    onMutate: async (config) => {
      await queryClient.cancelQueries({ queryKey: timelineQueryKey(timelineId) });
      const previous = queryClient.getQueryData<LoadedTimeline>(timelineQueryKey(timelineId));
      queryClient.setQueryData<LoadedTimeline>(timelineQueryKey(timelineId), {
        config,
        configVersion: configVersionRef.current,
      });
      return { previous };
    },
    onError: (_error, _config, context) => {
      if (context?.previous) {
        queryClient.setQueryData(timelineQueryKey(timelineId), context.previous);
        configVersionRef.current = context.previous.configVersion;
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: timelineQueryKey(timelineId) });
      void queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) });
    },
  });

  return {
    ...timelineQuery,
    data: timelineQuery.data?.config,
    configVersion: timelineQuery.data?.configVersion ?? configVersionRef.current,
    saveTimeline,
  };
}
