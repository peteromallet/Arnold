import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getSupabaseClient } from '@/integrations/supabase/client.ts';

export const effectsQueryKey = (userId: string | null | undefined) => ['effects', userId] as const;

/** @deprecated Legacy effects table — use resource-based effects via useEffectResources instead. */
export function useReighEffectsCatalog(
  userId: string | null | undefined,
  options?: { enabled?: boolean },
) {
  const queryClient = useQueryClient();

  const effectsQuery = useQuery({
    queryKey: effectsQueryKey(userId),
    enabled: (options?.enabled ?? true) && Boolean(userId),
    queryFn: async () => {
      const { data, error } = await getSupabaseClient()
        .from('effects')
        .select('*')
        .eq('user_id', userId!)
        .order('updated_at', { ascending: false });

      if (error) {
        throw error;
      }

      return data ?? [];
    },
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: effectsQueryKey(userId) });

  const upsertEffect = useMutation({
    mutationFn: async (input: { id?: string; name: string; slug: string; code: string; category: 'entrance' | 'exit' | 'continuous'; description?: string | null }) => {
      const payload = {
        ...input,
        user_id: userId!,
        is_public: false,
        updated_at: new Date().toISOString(),
      };

      if (input.id) {
        const { error } = await getSupabaseClient()
          .from('effects')
          .update(payload)
          .eq('id', input.id)
          .eq('user_id', userId!);
        if (error) throw error;
        return;
      }

      const { error } = await getSupabaseClient()
        .from('effects')
        .insert(payload);
      if (error) throw error;
    },
    onSuccess: () => {
      void invalidate();
    },
  });

  const deleteEffect = useMutation({
    mutationFn: async (effectId: string) => {
      const { error } = await getSupabaseClient()
        .from('effects')
        .delete()
        .eq('id', effectId)
        .eq('user_id', userId!);
      if (error) throw error;
    },
    onSuccess: () => {
      void invalidate();
    },
  });

  return {
    ...effectsQuery,
    upsertEffect,
    deleteEffect,
  };
}
