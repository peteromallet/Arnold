import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getSupabaseClient } from '@/integrations/supabase/client';
import type { Json } from '@/integrations/supabase/jsonTypes';
import { createDefaultTimelineConfig } from '@/tools/video-editor/lib/defaults';

export const timelineListQueryKey = (projectId: string | null | undefined) => ['timelines', projectId] as const;

export function useReighTimelinesList(projectId: string | null | undefined, userId: string | null | undefined) {
  const queryClient = useQueryClient();

  const timelinesQuery = useQuery({
    queryKey: timelineListQueryKey(projectId),
    enabled: Boolean(projectId),
    queryFn: async () => {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase
        .from('timelines')
        .select('*')
        .eq('project_id', projectId!)
        .order('updated_at', { ascending: false });

      if (error) {
        throw error;
      }

      return data ?? [];
    },
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: timelineListQueryKey(projectId) });

  const createTimeline = useMutation({
    mutationFn: async (name: string) => {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase
        .from('timelines')
        .insert({
          name,
          project_id: projectId!,
          user_id: userId!,
          config: createDefaultTimelineConfig() as unknown as Json,
          asset_registry: { assets: {} } as unknown as Json,
        })
        .select('*')
        .single();

      if (error) {
        throw error;
      }

      return data;
    },
    onSuccess: () => {
      void invalidate();
    },
  });

  const renameTimeline = useMutation({
    mutationFn: async ({ timelineId, name }: { timelineId: string; name: string }) => {
      const supabase = getSupabaseClient();
      const { error } = await supabase
        .from('timelines')
        .update({ name, updated_at: new Date().toISOString() })
        .eq('id', timelineId);

      if (error) {
        throw error;
      }
    },
    onSuccess: () => {
      void invalidate();
    },
  });

  const deleteTimeline = useMutation({
    mutationFn: async (timelineId: string) => {
      const supabase = getSupabaseClient();
      const { error } = await supabase
        .from('timelines')
        .delete()
        .eq('id', timelineId);

      if (error) {
        throw error;
      }
    },
    onSuccess: () => {
      void invalidate();
    },
  });

  return {
    ...timelinesQuery,
    createTimeline,
    renameTimeline,
    deleteTimeline,
  };
}
