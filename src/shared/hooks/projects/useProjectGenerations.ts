/**
 * Project-Wide Generation Queries
 * ================================
 *
 * This module provides hooks for querying generations at the PROJECT level.
 * Mutations live in `useGenerationMutations.ts` (re-exported here for compatibility).
 *
 * ## When to Use
 * - Displaying a gallery of generations across the project (GenerationsPane, MediaGallery)
 * - Filtering by tool type, media type, starred, search term
 * - Fetching derived items (edits based on a generation)
 *
 * ## When NOT to Use
 * - Querying images within a specific shot → use `useShotImages.ts` instead
 * - Timeline-specific data (frame positions, pair prompts) → use `useShotImages.ts`
 * - Page-level state management (filters, pagination) → use `useGalleryPageState.ts`
 * - Mutations (create, delete, star) → import from `useGenerationMutations.ts` directly
 *
 * ## Key Exports
 * - `useProjectGenerations(projectId, page, limit, filters)` - Paginated gallery data
 * - `fetchGenerations(projectId, limit, offset, filters)` - Direct fetch function
 * - `GenerationsPaginatedResponse` - Response type
 *
 * ## Data Source
 * Queries `generations` table directly (project-scoped, not shot-scoped)
 *
 * @module useProjectGenerations
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query';
import type { GeneratedImageWithMetadata } from '@/shared/components/MediaGallery/types';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { useSmartPollingConfig } from '../useSmartPolling';
import { unifiedGenerationQueryKeys } from '@/shared/lib/queryKeys/unified';
import { transformGeneration, transformVariant, type RawGeneration, type RawVariant } from '@/shared/lib/generationTransformers';
import type { PostgrestFilterBuilder } from '@supabase/postgrest-js';
import { SHOT_FILTER } from '@/shared/constants/filterConstants';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { getProjectSelectionFallbackId } from '@/shared/contexts/projectSelectionStore';

/** Cache garbage collection time for paginated generation queries */
const GENERATIONS_GC_TIME_MS = 10 * 60 * 1000; // 10 minutes

type AnyPostgrestFilterBuilder = PostgrestFilterBuilder<unknown, unknown, unknown, unknown, unknown>;

/** Common filter options for generation queries */
interface GenerationBaseFilters {
  toolType?: string;
  mediaType?: 'all' | 'image' | 'video';
  shotId?: string;
  excludePositioned?: boolean;
  starredOnly?: boolean;
  searchTerm?: string;
  editsOnly?: boolean;
}

/**
 * Apply common filters to a generations query.
 * Used by both count and data queries to ensure consistency.
 */
// TODO: type properly - PostgrestFilterBuilder generics are complex Supabase internals
function applyGenerationFilters<T extends AnyPostgrestFilterBuilder>(
  query: T,
  filters: GenerationBaseFilters | undefined
): T {
  if (!filters) return query;

  // Tool type filter (skip when shot filter is active - shot filter takes precedence)
  if (filters.toolType && !filters.shotId) {
    if (filters.toolType === TOOL_IDS.IMAGE_GENERATION) {
      query = query.eq('params->>tool_type', TOOL_IDS.IMAGE_GENERATION) as T;
    } else {
      query = query.or(`params->>tool_type.eq.${filters.toolType},params->>tool_type.eq.${filters.toolType}-reconstructed-client`) as T;
    }
  }

  // Media type filter
  if (filters.mediaType && filters.mediaType !== 'all') {
    if (filters.mediaType === 'video') {
      query = query.like('type', '%video%') as T;
    } else if (filters.mediaType === 'image') {
      query = query.not('type', 'like', '%video%') as T;
    }
  }

  // Starred filter
  if (filters.starredOnly) {
    query = query.eq('starred', true) as T;
  }

  // Edits only filter (generations derived from another)
  if (filters.editsOnly) {
    query = query.not('based_on', 'is', null) as T;
  }

  // Search filter
  if (filters.searchTerm?.trim()) {
    const searchPattern = `%${filters.searchTerm.trim()}%`;
    query = query.ilike('params->originalParams->orchestrator_details->>prompt', searchPattern) as T;
  }

  // Shot filter
  if (filters.shotId === SHOT_FILTER.NO_SHOT) {
    query = query.or('shot_data.is.null,shot_data.eq.{}') as T;
  } else if (filters.shotId) {
    query = query.not(`shot_data->${filters.shotId}`, 'is', null) as T;
    if (filters.excludePositioned) {
      query = query.or(`shot_data->${filters.shotId}.eq.null,shot_data->${filters.shotId}.eq.-1,shot_data->${filters.shotId}.cs.[null],shot_data->${filters.shotId}.cs.[-1]`) as T;
    }
  }

  return query;
}

/**
 * Fetch edit variants from generation_variants table for a project
 * Filters by tool_type in params (set by complete_task)
 * 
 * NOTE: Requires the project_id column on generation_variants (added via migration)
 * The column is auto-populated by a trigger from the parent generation
 */
async function fetchEditVariants(
  projectId: string,
  limit: number,
  offset: number,
  filters?: {
    toolType?: string;
    mediaType?: 'all' | 'image' | 'video';
    sort?: 'newest' | 'oldest';
    parentsOnly?: boolean; // Exclude child variants (those with parent_variant_id in params)
  }
): Promise<{
  items: GeneratedImageWithMetadata[];
  total: number;
  hasMore: boolean;
}> {
  const toolType = filters?.toolType;
  const sort = filters?.sort || 'newest';
  const mediaType = filters?.mediaType || 'all';
  const parentsOnly = filters?.parentsOnly ?? true;

  // Build count query
  let countQuery = supabase().from('generation_variants')
    .select('*', { count: 'exact', head: true })
    .eq('project_id', projectId);
  
  // Only filter by toolType if specified
  if (toolType) {
    countQuery = countQuery.eq('params->>tool_type', toolType);
  }
  
  // Filter by media type - variants don't have a type column, so filter by URL extension
  if (mediaType === 'video') {
    countQuery = countQuery.or('location.ilike.%.mp4,location.ilike.%.webm,location.ilike.%.mov');
  } else if (mediaType === 'image') {
    countQuery = countQuery.not('location', 'ilike', '%.mp4').not('location', 'ilike', '%.webm').not('location', 'ilike', '%.mov');
  }
  
  // Exclude child variants (those created from another variant)
  if (parentsOnly) {
    countQuery = countQuery.is('params->>parent_variant_id', null);
  }

  const { count, error: countError } = await countQuery;

  if (countError) {
    throw countError;
  }

  const totalCount = count || 0;

  if (totalCount === 0) {
    return { items: [], total: 0, hasMore: false };
  }

  // Data query with pagination
  const ascending = sort === 'oldest';
  let dataQuery = supabase().from('generation_variants')
    .select(`
      id,
      generation_id,
      location,
      thumbnail_url,
      params,
      variant_type,
      name,
      created_at
    `)
    .eq('project_id', projectId);
  
  // Only filter by toolType if specified
  if (toolType) {
    dataQuery = dataQuery.eq('params->>tool_type', toolType);
  }
  
  // Filter by media type in data query too
  if (mediaType === 'video') {
    dataQuery = dataQuery.or('location.ilike.%.mp4,location.ilike.%.webm,location.ilike.%.mov');
  } else if (mediaType === 'image') {
    dataQuery = dataQuery.not('location', 'ilike', '%.mp4').not('location', 'ilike', '%.webm').not('location', 'ilike', '%.mov');
  }
  
  // Exclude child variants in data query too
  if (parentsOnly) {
    dataQuery = dataQuery.is('params->>parent_variant_id', null);
  }
  
  dataQuery = dataQuery
    .order('created_at', { ascending })
    .range(offset, offset + limit - 1);

  const { data, error } = await dataQuery;

  if (error) {
    throw error;
  }

  // Transform variants using shared transformer
  const items: GeneratedImageWithMetadata[] = (data || []).map((variant) =>
    transformVariant(variant as unknown as RawVariant, { toolType })
  );

  return {
    items,
    total: totalCount,
    hasMore: offset + items.length < totalCount,
  };
}

export type GenerationFilters = GenerationBaseFilters & {
  includeChildren?: boolean;
  parentGenerationId?: string;
  sort?: 'newest' | 'oldest';
  editsOnly?: boolean; // Filter for images with based_on set (derived/edited images)
  parentsOnly?: boolean; // For variants: exclude child variants (those with parent_variant_id)
  variantsOnly?: boolean; // Fetch edit variants from generation_variants table
};

async function fetchGenerationsForProject(
  projectId: string,
  limit: number = 100,
  offset: number = 0,
  filters?: GenerationFilters
): Promise<{
  items: GeneratedImageWithMetadata[];
  total: number;
  hasMore: boolean;
}> {
  // Special path for variantsOnly - fetch from generation_variants table
  if (filters?.variantsOnly) {
    return fetchEditVariants(projectId, limit, offset, {
      toolType: filters.toolType,
      mediaType: filters.mediaType,
      sort: filters.sort,
      parentsOnly: filters.parentsOnly ?? true, // Default to parents only
    });
  }

  // Build count query
  let countQuery = supabase().from('generations')
    .select('*', { count: 'exact', head: true })
    .eq('project_id', projectId);
  
  // Only include generations with valid output URLs - UNLESS fetching children of a specific parent
  // (children may still be processing and need to show as placeholders)
  if (!filters?.parentGenerationId) {
    countQuery = countQuery.or('location.not.is.null,storage_mode.eq.local');
  }

  // Parent/Child filtering (count query specific)
  if (filters?.parentGenerationId) {
    countQuery = countQuery.eq('parent_generation_id', filters.parentGenerationId);
  } else if (!filters?.includeChildren) {
    countQuery = countQuery.eq('is_child', false);
  }

  // Apply common filters (toolType, mediaType, starred, edits, search, shot)
  countQuery = applyGenerationFilters(countQuery, filters);

  const { count, error: countError } = await countQuery;
  if (countError) {
    throw countError;
  }
  const totalCount = count || 0;

  // Select only the fields needed for the gallery view
  let dataQuery = supabase().from('generations')
    .select(`
      id,
      location,
      thumbnail_url,
      primary_variant_id,
      storage_mode,
      local_handle_id,
      local_file_name,
      local_file_size,
      local_file_mime,
      primary_variant:generation_variants!generations_primary_variant_id_fkey (
        location,
        thumbnail_url
      ),
      type,
      created_at,
      updated_at,
      params,
      starred,
      tasks,
      based_on,
      shot_data,
      name,
      is_child,
      parent_generation_id,
      child_order
    `)
    .eq('project_id', projectId);

  // Parent/Child filtering - apply BEFORE location filter since parentGenerationId affects whether we filter by location
  // Parent/Child filtering (data query specific - has ordering)
  if (filters?.parentGenerationId) {
    dataQuery = dataQuery.eq('parent_generation_id', filters.parentGenerationId);
    dataQuery = dataQuery.order('child_order', { ascending: true });
  } else {
    dataQuery = dataQuery.or('location.not.is.null,storage_mode.eq.local');
    if (!filters?.includeChildren) {
      dataQuery = dataQuery.eq('is_child', false);
    }
  }

  // Apply common filters (toolType, mediaType, starred, edits, search, shot)
  dataQuery = applyGenerationFilters(dataQuery, filters);


  // Determine sort order
  const sort = filters?.sort || 'newest';
  const ascending = sort === 'oldest';

  // Execute query with standard server-side pagination
  const { data, error } = await dataQuery
    .order('created_at', { ascending })
    .range(offset, offset + limit - 1);

  if (error) {
    throw error;
  }

  if (!data) {
    return { items: [], total: totalCount, hasMore: false };
  }


  const finalData = data || [];
  const hasMore = (offset + limit) < totalCount;

  // Badge data (derivedCount, hasUnviewedVariants, unviewedVariantCount) is now loaded
  // lazily via useVariantBadges hook to avoid blocking gallery display

  // Use shared transformer instead of inline transformation logic
  const items = finalData?.map((item) => {
    // Transform using shared function - handles all the complex logic
    return transformGeneration(item as unknown as RawGeneration, {
      shotId: filters?.shotId,
    });
  }) || [];

  return { items, total: totalCount, hasMore };
}

export function fetchGenerations(
  projectId: string | null,
  limit: number = 100,
  offset: number = 0,
  filters?: GenerationFilters
): Promise<{
  items: GeneratedImageWithMetadata[];
  total: number;
  hasMore: boolean;
}> {
  if (!projectId) {
    return Promise.resolve({ items: [], total: 0, hasMore: false });
  }
  return fetchGenerationsForProject(projectId, limit, offset, filters);
}


export type GenerationsPaginatedResponse = {
  items: GeneratedImageWithMetadata[];
  total: number;
  hasMore: boolean;
};

export function useProjectGenerations(
  projectId: string | null,
  page: number = 1,
  limit: number = 100,
  enabled: boolean = true,
  filters?: GenerationFilters,
  options?: {
    disablePolling?: boolean; // Disable smart polling (useful for long-running tasks)
  }
) {
  const offset = (page - 1) * limit;
  const effectiveProjectId = projectId ?? getProjectSelectionFallbackId();
  const filtersKey = filters ? JSON.stringify(filters) : null;
  const queryKey = unifiedGenerationQueryKeys.byProject(
    effectiveProjectId ?? '__no-project__',
    page,
    limit,
    filtersKey
  );


  // Use DataFreshnessManager for intelligent polling decisions.
  // Can be disabled for tools with long-running tasks to prevent gallery flicker.
  const smartPollingConfig = useSmartPollingConfig(['generations', effectiveProjectId ?? '__no-project__']);
  const pollingDisabled = Boolean(options?.disablePolling);
  const pollingConfig: { refetchInterval: number | false; staleTime: number } = pollingDisabled
    ? { refetchInterval: false, staleTime: Infinity }
    : smartPollingConfig;

  const result = useQuery<GenerationsPaginatedResponse, Error>({
    queryKey: queryKey,
    queryFn: () => fetchGenerationsForProject(effectiveProjectId!, limit, offset, filters),
    enabled: !!effectiveProjectId && enabled,
    // Use `placeholderData` with `keepPreviousData` to prevent UI flashes on pagination/filter changes
    placeholderData: keepPreviousData,
    // Cache management to prevent memory leaks as pagination grows
    gcTime: GENERATIONS_GC_TIME_MS,
    refetchOnWindowFocus: false, // Prevent double-fetches

    // Intelligent polling based on realtime health (or disabled)
    ...pollingConfig,
    refetchIntervalInBackground: !pollingDisabled, // Only poll in background if polling is enabled
    refetchOnReconnect: false, // Prevent double-fetches
  });

  return result;
}

// ===== MUTATIONS =====
// These hooks live in useGenerationMutations.ts — import directly from there.

// ===== DERIVED ITEMS =====
// DerivedItem and useDerivedItems live in useDerivedItems.ts — import directly from there.
