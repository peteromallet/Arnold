import { getSupabaseClient } from '@/integrations/supabase/client';

export interface PrimaryVariantInfo {
  location: string;
  variant_id: string;
}

export async function fetchPrimaryVariantLocations(generationIds: string[]): Promise<Record<string, PrimaryVariantInfo | null>> {
  if (generationIds.length === 0) {
    return {};
  }

  const { data, error } = await getSupabaseClient()
    .from('generations')
    .select(`
      id,
      primary_variant:generation_variants!generations_primary_variant_id_fkey (
        id,
        location
      )
    `)
    .in('id', generationIds);

  if (error) {
    throw error;
  }

  const map: Record<string, PrimaryVariantInfo | null> = {};
  for (const row of data ?? []) {
    const primaryVariant = row.primary_variant as { id: string; location: string } | null;
    map[row.id] = primaryVariant ? { location: primaryVariant.location, variant_id: primaryVariant.id } : null;
  }

  return map;
}

export async function fetchCurrentPrimaryVariant(generationId: string) {
  const { data, error } = await getSupabaseClient()
    .from('generations')
    .select(`
      primary_variant_id,
      primary_variant:generation_variants!generations_primary_variant_id_fkey (
        id,
        location,
        thumbnail_url
      )
    `)
    .eq('id', generationId)
    .single();

  if (error || !data?.primary_variant) {
    return null;
  }

  return data.primary_variant as { id: string; location: string; thumbnail_url: string | null };
}
