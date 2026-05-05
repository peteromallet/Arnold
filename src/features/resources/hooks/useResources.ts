import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import type { LoraModel } from '@/domains/lora/types/lora';
import { PhaseConfig } from '@/shared/types/phaseConfig';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import type { Database } from '@/integrations/supabase/databasePublicTypes';
import type { Json } from '@/integrations/supabase/jsonTypes';
import { toJson } from '@/shared/lib/supabaseTypeHelpers';
import type { VideoMetadata } from '@/shared/lib/media/videoUploader';
import { QUERY_PRESETS } from '@/shared/lib/query/queryDefaults';
import { resourceQueryKeys } from '@/shared/lib/queryKeys/resources';
import type { ParameterSchema } from '@/tools/video-editor';

export interface PhaseConfigMetadata {
    name: string;
    description: string;
    phaseConfig: PhaseConfig;
    created_by: {
        is_you: boolean;
        username?: string;
    };
    is_public: boolean;
    tags?: string[];
    use_count?: number;
    created_at: string;
    sample_generations?: {
        url: string;
        type: 'image' | 'video';
        alt_text?: string;
    }[];
    main_generation?: string;
    // Prompt and generation settings
    basePrompt?: string;
    negativePrompt?: string;
    textBeforePrompts?: string;
    textAfterPrompts?: string;
    enhancePrompt?: boolean;
    durationFrames?: number;
    selectedLoras?: Array<{ id: string; name: string; strength: number }>;
    // Generation type mode (I2V = image-to-video, VACE = structure video guidance)
    generationTypeMode?: 'i2v' | 'vace';
}

export interface StyleReferenceMetadata {
    name: string;
    styleReferenceImage: string;
    styleReferenceImageOriginal: string;
    thumbnailUrl: string | null;
    generationId?: string;
    styleReferenceStrength: number;
    subjectStrength: number;
    subjectDescription: string;
    inThisScene: boolean;
    inThisSceneStrength: number;
    referenceMode: 'style' | 'subject' | 'style-character' | 'scene' | 'custom';
    styleBoostTerms: string;
    created_by: {
        is_you: boolean;
        username?: string;
    };
    is_public: boolean;
    createdAt: string;
    updatedAt: string;
}

export interface StructureVideoMetadata {
    name: string;
    videoUrl: string;
    thumbnailUrl: string | null;
    videoMetadata: VideoMetadata;
    created_by: {
        is_you: boolean;
        username?: string;
    };
    is_public: boolean;
    createdAt: string;
}

export interface EffectMetadata {
    name: string;
    slug: string;
    code: string;
    category: 'entrance' | 'exit' | 'continuous';
    description: string;
    parameterSchema?: ParameterSchema;
    created_by: {
        is_you: boolean;
        username?: string;
    };
    is_public: boolean;
}

export interface SequenceComponentMetadata {
    name: string;
    slug: string;
    code: string;
    schemaJson: object;
    defaultsJson: object;
    clipType: string;
    themeId: string;
    description: string;
    created_by: {
        is_you: boolean;
        username?: string;
    };
    is_public: boolean;
}

export type ResourceType = 'lora' | 'phase-config' | 'style-reference' | 'structure-video' | 'effect' | 'sequence-component';
export type ResourceMetadata = LoraModel | PhaseConfigMetadata | StyleReferenceMetadata | StructureVideoMetadata | EffectMetadata | SequenceComponentMetadata;
type ResourceRow = Database['public']['Tables']['resources']['Row'] & {
    generation_id?: string | null;
};

export interface Resource {
    id: string;
    userId?: string;
    user_id?: string;
    generation_id?: string | null;
    type: ResourceType;
    metadata: ResourceMetadata | Json;
    isPublic?: boolean;
    is_public?: boolean;
    createdAt?: string;
    created_at?: string;
}

function isResourceType(type: string): type is ResourceType {
    return type === 'lora' || type === 'phase-config' || type === 'style-reference' || type === 'structure-video' || type === 'effect' || type === 'sequence-component';
}

function mapResourceRow(row: ResourceRow, fallbackType?: ResourceType): Resource {
    const resolvedType = isResourceType(row.type) ? row.type : fallbackType;
    if (!resolvedType) {
        throw new Error(`Unknown resource type: ${row.type}`);
    }
    return {
        ...row,
        type: resolvedType,
    };
}

// List public resources (available to all users)
export const useListPublicResources = (
    type: ResourceType,
    options?: { enabled?: boolean },
) => {
    return useQuery<Resource[], Error>({
        queryKey: resourceQueryKeys.publicByType(type),
        enabled: options?.enabled ?? true,
        queryFn: async () => {
            
            // Manual pagination to bypass 1000 limit
            let allData: Resource[] = [];
            let page = 0;
            const pageSize = 1000;
            let hasMore = true;

            while (hasMore) {
                const { data, error } = await supabase().from('resources')
                    .select('*')
                    .eq('type', type)
                    .eq('is_public', true)
                    .range(page * pageSize, (page + 1) * pageSize - 1);
                
                if (error) {
                    normalizeAndPresentError(error, { context: 'useListPublicResources', showToast: false, logData: { type } });
                    throw error;
                }
                
                if (data) {
                    allData = [...allData, ...data.map((row) => mapResourceRow(row, type))];
                    if (data.length < pageSize) {
                        hasMore = false;
                    } else {
                        page++;
                    }
                } else {
                    hasMore = false;
                }
                
                // Safety limit to prevent infinite loops
                if (allData.length >= 20000) {
                    hasMore = false;
                }
            }
            
            return allData;
        },
        // Use static preset - public resources change infrequently
        ...QUERY_PRESETS.static,
        staleTime: 15 * 60 * 1000, // Override: 15 minutes (public resources are very stable)
        gcTime: 30 * 60 * 1000, // Keep in cache longer
    });
};

// List resources
export const useListResources = (
    type: ResourceType,
    options?: { enabled?: boolean },
) => {
    return useQuery<Resource[], Error>({
        // Note: Using ['resources', type] pattern for user resources (no projectId needed)
        queryKey: resourceQueryKeys.listByType(type),
        enabled: options?.enabled ?? true,
        queryFn: async () => {
            const { data: { user } } = await supabase().auth.getUser();
            if (!user) throw new Error('Not authenticated');
            
            // Manual pagination to bypass 1000 limit
            let allData: Resource[] = [];
            let page = 0;
            const pageSize = 1000;
            let hasMore = true;

            while (hasMore) {
                const { data, error } = await supabase().from('resources')
                    .select('*')
                    .eq('user_id', user.id)
                    .eq('type', type)
                    .range(page * pageSize, (page + 1) * pageSize - 1);
                
                if (error) throw error;

                if (data) {
                    allData = [...allData, ...data.map((row) => mapResourceRow(row, type))];
                    if (data.length < pageSize) {
                        hasMore = false;
                    } else {
                        page++;
                    }
                } else {
                    hasMore = false;
                }
                
                 // Safety limit
                 if (allData.length >= 20000) break;
            }

            return allData;
        },
        // Use static preset - user resources change only via mutations (which invalidate)
        ...QUERY_PRESETS.static,
    });
};

// Create a new resource
export interface CreateResourceArgs {
    type: ResourceType;
    metadata: ResourceMetadata;
    generation_id?: string | null;
}

export const useCreateResource = () => {
    const queryClient = useQueryClient();
    return useMutation<Resource, Error, CreateResourceArgs>({
        mutationFn: async ({ type, metadata, generation_id }) => {
            const { data: { user } } = await supabase().auth.getUser();
            if (!user) throw new Error('Not authenticated');
            
            // Extract is_public from metadata for the column
            const isPublic = 'is_public' in metadata ? Boolean((metadata as Record<string, unknown>).is_public) : false;

            const insertPayload = {
                type,
                metadata: toJson(metadata),
                user_id: user.id,
                is_public: isPublic,
                ...(generation_id !== undefined ? { generation_id } : {}),
            } as Database['public']['Tables']['resources']['Insert'] & { generation_id?: string | null };
            
            const { data, error } = await supabase().from('resources')
                    .insert(insertPayload)
                .select()
                .single();
            
            if (error) throw error;
            return mapResourceRow(data, type);
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: [...resourceQueryKeys.all, data.type] });
            queryClient.invalidateQueries({ queryKey: resourceQueryKeys.public(data.type) });
        },
        onError: (error) => {
            normalizeAndPresentError(error, { context: 'useCreateResource', toastTitle: 'Failed to create resource' });
        },
    });
};

// Update a resource
export interface UpdateResourceArgs {
    id: string;
    type: ResourceType;
    metadata: ResourceMetadata;
}

export const useUpdateResource = () => {
    const queryClient = useQueryClient();
    return useMutation<Resource, Error, UpdateResourceArgs>({
        mutationFn: async ({ id, metadata }) => {

            const { data: { user } } = await supabase().auth.getUser();
            if (!user) {
                const err = new Error('Not authenticated');
                normalizeAndPresentError(err, { context: 'useUpdateResource', showToast: false });
                throw err;
            }

            // First, let's check if the resource exists at all (without user_id filter)
            const { data: resourceCheck } = await supabase().from('resources')
                .select('id, user_id, type')
                .eq('id', id)
                .maybeSingle();
            
            // Now verify the resource exists and belongs to the user
            const { data: existingResource, error: checkError } = await supabase().from('resources')
                .select('id, user_id, type')
                .eq('id', id)
                .eq('user_id', user.id)
                .maybeSingle();
            
            if (checkError) {
                normalizeAndPresentError(checkError, { context: 'useUpdateResource', showToast: false });
                throw new Error(`Failed to verify resource: ${checkError.message}`);
            }
            
            if (!existingResource) {
                normalizeAndPresentError(new Error('Resource not found or access denied'), { context: 'useUpdateResource', showToast: false, logData: {
                    id,
                    userId: user.id,
                    resourceExists: !!resourceCheck,
                    resourceOwner: resourceCheck?.user_id
                }});

                // Provide a more specific error message
                if (resourceCheck && resourceCheck.user_id !== user.id) {
                    throw new Error('This resource belongs to another user');
                }
                throw new Error('Resource not found or you do not have permission to update it');
            }
            
            // Extract is_public from metadata for the column
            const isPublic = 'is_public' in metadata ? Boolean((metadata as Record<string, unknown>).is_public) : false;
            
            // Now perform the update
            const { data, error } = await supabase().from('resources')
                .update({ metadata: toJson(metadata), is_public: isPublic })
                .eq('id', id)
                .eq('user_id', user.id)
                .select()
                .maybeSingle();
            
            if (error) {
                normalizeAndPresentError(error, { context: 'useUpdateResource', showToast: false, logData: {
                    code: error.code,
                    details: error.details,
                    hint: error.hint
                }});
                throw error;
            }
            
            if (!data) {
                normalizeAndPresentError(new Error('Update succeeded but no data returned'), { context: 'useUpdateResource', showToast: false });
                // If update succeeded but no data returned, fetch it separately
                const { data: fetchedData, error: fetchError } = await supabase().from('resources')
                    .select('*')
                    .eq('id', id)
                    .maybeSingle();
                
                if (fetchError || !fetchedData) {
                    normalizeAndPresentError(fetchError || new Error('No data returned'), { context: 'useUpdateResource', showToast: false });
                    throw new Error('Update may have succeeded but failed to fetch updated resource');
                }
                
                return mapResourceRow(fetchedData, existingResource.type as ResourceType);
            }
            
            return mapResourceRow(data, existingResource.type as ResourceType);
        },
        onSuccess: (data) => {
            // Prefix invalidation: ['resources', type] prefix-matches ['resources', type, 'v2']
            queryClient.invalidateQueries({ queryKey: [...resourceQueryKeys.all, data.type] });
            queryClient.invalidateQueries({ queryKey: resourceQueryKeys.public(data.type) });
            // Invalidate specific-resources queries that include this resource ID
            // Using predicate to find any query that contains this resource ID
            queryClient.invalidateQueries({
                predicate: (query) => {
                    const key = query.queryKey;
                    if (key[0] === 'specific-resources' && typeof key[1] === 'string') {
                        return key[1].includes(data.id);
                    }
                    return false;
                }
            });
        },
        onError: (error) => {
            normalizeAndPresentError(error, { context: 'useUpdateResource', toastTitle: 'Failed to update resource' });
        },
    });
};

// Delete a resource
export const useDeleteResource = () => {
    const queryClient = useQueryClient();
    return useMutation<void, Error, { id: string, type: ResourceType }>({
        mutationFn: async ({ id }) => {
            const { data: { user } } = await supabase().auth.getUser();
            if (!user) throw new Error('Not authenticated');

            const { error } = await supabase().from('resources')
                .delete()
                .eq('id', id)
                .eq('user_id', user.id);

            if (error) throw error;
        },
        onSuccess: (_data, variables) => {
            // Remove the individual resource cache entry
            queryClient.removeQueries({ queryKey: resourceQueryKeys.detail(variables.id) });
            // Also invalidate the list queries
            queryClient.invalidateQueries({ queryKey: [...resourceQueryKeys.all, variables.type] });
            queryClient.invalidateQueries({ queryKey: resourceQueryKeys.public(variables.type) });
        },
        onError: (error) => {
            normalizeAndPresentError(error, { context: 'useDeleteResource', toastTitle: 'Failed to delete resource' });
        },
    });
};

// =============================================================================
// Convenience hooks that extract metadata directly
// These eliminate the need for consumers to manually map resource.metadata
// =============================================================================

/** Fetch all public LoRAs with metadata extracted */
export const usePublicLoras = () => {
    const query = useListPublicResources('lora');
    const data = useMemo(
        () => (query.data || []).map(r => r.metadata || {}) as LoraModel[],
        [query.data]
    );
    return { ...query, data };
};

/** Fetch all public style references with metadata extracted */
export const usePublicStyleReferences = () => {
    const query = useListPublicResources('style-reference');
    const data = useMemo(
        () => (query.data || []).map(r => r.metadata || {}) as StyleReferenceMetadata[],
        [query.data]
    );
    return { ...query, data };
};

/** Fetch current user's style references with metadata extracted */
export const useMyStyleReferences = () => {
    const query = useListResources('style-reference');
    const data = useMemo(
        () => (query.data || []).map(r => r.metadata || {}) as StyleReferenceMetadata[],
        [query.data]
    );
    return { ...query, data };
};
