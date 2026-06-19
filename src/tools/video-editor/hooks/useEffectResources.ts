import { createContext, createElement, useContext, useMemo } from 'react';
import type { UseMutationOptions, UseMutationResult } from '@tanstack/react-query';
import {
  type CreateResourceArgs,
  useCreateResource,
  useDeleteResource,
  useListPublicResources,
  useListResources,
  type UpdateResourceArgs,
  useUpdateResource,
  type EffectMetadata,
  type Resource,
} from '@/features/resources/hooks/useResources.ts';
import {
  createVideoEditorEffectCatalog,
  registryRecordToEffectResource,
  type EffectCategory,
  type EffectResource,
  type VideoEditorEffectCatalog,
} from '@/tools/video-editor/lib/effect-catalog.ts';
import { useOptionalEffectRegistryContext } from '@/tools/video-editor/effects/registry/EffectRegistryContext';

export type {
  CreateVideoEditorEffectInput,
  DeleteVideoEditorEffectInput,
  EffectCategory,
  EffectResource,
  EffectResourcesByCategory,
  UpdateVideoEditorEffectInput,
  VideoEditorEffectCatalog,
  VideoEditorEffectCatalogOptions,
} from '@/tools/video-editor/lib/effect-catalog.ts';

export {
  createVideoEditorEffectCatalog,
  registryRecordToEffectResource,
} from '@/tools/video-editor/lib/effect-catalog.ts';

function toEffectResource(resource: Resource): EffectResource {
  const metadata = resource.metadata as EffectMetadata;
  return {
    ...metadata,
    id: resource.id,
    type: 'effect',
    userId: resource.userId,
    user_id: resource.user_id,
    isPublic: resource.isPublic,
    is_public: resource.is_public ?? metadata.is_public,
    createdAt: resource.createdAt,
    created_at: resource.created_at,
  };
}

const EffectCatalogContext = createContext<VideoEditorEffectCatalog | null>(null);

export function EffectCatalogProvider({
  value,
  children,
}: {
  value: VideoEditorEffectCatalog;
  children: React.ReactNode;
}) {
  return createElement(EffectCatalogContext.Provider, { value }, children);
}

function useSupabaseEffectCatalog(
  userId: string | null | undefined,
  options?: { enabled?: boolean },
): VideoEditorEffectCatalog {
  const enabled = options?.enabled ?? true;
  const privateEffectsQuery = useListResources('effect', { enabled: enabled && Boolean(userId) });
  const publicEffectsQuery = useListPublicResources('effect', { enabled });
  const createEffect = useCreateEffectResource();
  const updateEffect = useUpdateEffectResource();
  const deleteEffect = useDeleteEffectResource();

  // Pull provider-scoped registry records to merge into the catalog.
  const registryCtx = useOptionalEffectRegistryContext();
  const registryRecords = registryCtx?.snapshot?.records ?? [];

  const effects = useMemo(() => {
    const privateResources = userId ? privateEffectsQuery.data ?? [] : [];
    const publicResources = publicEffectsQuery.data ?? [];
    const deduped = new Map<string, EffectResource>();

    for (const resource of [...privateResources, ...publicResources]) {
      deduped.set(resource.id, toEffectResource(resource));
    }

    return [...deduped.values()];
  }, [privateEffectsQuery.data, publicEffectsQuery.data, userId]);

  return useMemo(() => createVideoEditorEffectCatalog({
    effects,
    registryRecords,
    isLoading: privateEffectsQuery.isLoading || publicEffectsQuery.isLoading,
    isFetching: privateEffectsQuery.isFetching || publicEffectsQuery.isFetching,
    error: privateEffectsQuery.error ?? publicEffectsQuery.error ?? null,
    refetch: async () => Promise.all([privateEffectsQuery.refetch(), publicEffectsQuery.refetch()]),
    createEffect: async (variables) => {
      const resource = await createEffect.mutateAsync(variables);
      return { id: resource.id };
    },
    updateEffect: async (variables) => {
      const resource = await updateEffect.mutateAsync(variables);
      return { id: resource.id };
    },
    deleteEffect: async (variables) => deleteEffect.mutateAsync(variables),
  }), [
    createEffect,
    deleteEffect,
    effects,
    registryRecords,
    privateEffectsQuery.error,
    privateEffectsQuery.isFetching,
    privateEffectsQuery.isLoading,
    privateEffectsQuery.refetch,
    publicEffectsQuery.error,
    publicEffectsQuery.isFetching,
    publicEffectsQuery.isLoading,
    publicEffectsQuery.refetch,
    updateEffect,
  ]);
}

export function useResolvedEffectCatalog(
  userId: string | null | undefined,
  injectedCatalog?: VideoEditorEffectCatalog | null,
): VideoEditorEffectCatalog {
  const fallbackCatalog = useSupabaseEffectCatalog(userId, { enabled: !injectedCatalog });
  return injectedCatalog ?? fallbackCatalog;
}

export function useEffectResources(userId?: string | null | undefined) {
  const injectedCatalog = useContext(EffectCatalogContext);
  const fallbackCatalog = useSupabaseEffectCatalog(userId, { enabled: !injectedCatalog });
  return injectedCatalog ?? fallbackCatalog;
}

export function useCreateEffectResource(): Omit<
  UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>['mutate'];
  mutateAsync: (variables: { metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { metadata: EffectMetadata }, unknown>) => Promise<Resource>;
} {
  const mutation = useCreateResource();
  const base = mutation as unknown as Omit<
    UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>,
    'mutate' | 'mutateAsync'
  >;

  return {
    ...base,
    mutate: ((variables, options) => mutation.mutate(
      { type: 'effect', metadata: variables.metadata } as CreateResourceArgs,
      options as Parameters<typeof mutation.mutate>[1],
    )) as UseMutationResult<Resource, Error, { metadata: EffectMetadata }, unknown>['mutate'],
    mutateAsync: ((variables, options) => mutation.mutateAsync(
      { type: 'effect', metadata: variables.metadata } as CreateResourceArgs,
      options as Parameters<typeof mutation.mutateAsync>[1],
    )) as (variables: { metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { metadata: EffectMetadata }, unknown>) => Promise<Resource>,
  };
}

export function useUpdateEffectResource(): Omit<
  UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>['mutate'];
  mutateAsync: (variables: { id: string; metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>) => Promise<Resource>;
} {
  const mutation = useUpdateResource();
  const base = mutation as unknown as Omit<
    UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>,
    'mutate' | 'mutateAsync'
  >;

  return {
    ...base,
    mutate: ((variables, options) => mutation.mutate(
      { id: variables.id, type: 'effect', metadata: variables.metadata } as UpdateResourceArgs,
      options as Parameters<typeof mutation.mutate>[1],
    )) as UseMutationResult<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>['mutate'],
    mutateAsync: ((variables, options) => mutation.mutateAsync(
      { id: variables.id, type: 'effect', metadata: variables.metadata } as UpdateResourceArgs,
      options as Parameters<typeof mutation.mutateAsync>[1],
    )) as (variables: { id: string; metadata: EffectMetadata }, options?: UseMutationOptions<Resource, Error, { id: string; metadata: EffectMetadata }, unknown>) => Promise<Resource>,
  };
}

export function useDeleteEffectResource(): Omit<
  UseMutationResult<void, Error, { id: string }, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<void, Error, { id: string }, unknown>['mutate'];
  mutateAsync: (variables: { id: string }, options?: UseMutationOptions<void, Error, { id: string }, unknown>) => Promise<void>;
} {
  const mutation = useDeleteResource();

  return {
    ...mutation,
    mutate: (variables, options) => mutation.mutate({ id: variables.id, type: 'effect' }, options),
    mutateAsync: (variables, options) => mutation.mutateAsync({ id: variables.id, type: 'effect' }, options),
  };
}
