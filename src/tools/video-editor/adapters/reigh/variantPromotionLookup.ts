import { getSupabaseClient } from '@/integrations/supabase/client';

export async function loadPrimaryVariantForGeneration(generationId: string) {
  const { data, error } = await getSupabaseClient()
    .from('generation_variants')
    .select('id, location, thumbnail_url')
    .eq('generation_id', generationId)
    .eq('is_primary', true)
    .maybeSingle();

  if (error) {
    throw error;
  }

  return data;
}
