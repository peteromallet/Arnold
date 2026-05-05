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
  type Resource,
  type SequenceComponentMetadata,
} from '@/features/resources/hooks/useResources.ts';
import {
  createVideoEditorSequenceComponentCatalog,
  type SequenceComponentResource,
  type VideoEditorSequenceComponentCatalog,
} from '@/tools/video-editor/lib/sequence-component-catalog.ts';

export type {
  CreateVideoEditorSequenceComponentInput,
  DeleteVideoEditorSequenceComponentInput,
  SequenceComponentResource,
  UpdateVideoEditorSequenceComponentInput,
  VideoEditorSequenceComponentCatalog,
  VideoEditorSequenceComponentCatalogOptions,
} from '@/tools/video-editor/lib/sequence-component-catalog.ts';

export { createVideoEditorSequenceComponentCatalog } from '@/tools/video-editor/lib/sequence-component-catalog.ts';

function toSequenceComponentResource(resource: Resource): SequenceComponentResource {
  const metadata = resource.metadata as SequenceComponentMetadata;
  return {
    ...metadata,
    id: resource.id,
    type: 'sequence-component',
    userId: resource.userId,
    user_id: resource.user_id,
    isPublic: resource.isPublic,
    is_public: resource.is_public ?? metadata.is_public,
    createdAt: resource.createdAt,
    created_at: resource.created_at,
  };
}

const SequenceComponentCatalogContext = createContext<VideoEditorSequenceComponentCatalog | null>(null);

export function SequenceComponentCatalogProvider({
  value,
  children,
}: {
  value: VideoEditorSequenceComponentCatalog;
  children: React.ReactNode;
}) {
  return createElement(SequenceComponentCatalogContext.Provider, { value }, children);
}

function useSupabaseSequenceComponentCatalog(
  userId: string | null | undefined,
  options?: { enabled?: boolean },
): VideoEditorSequenceComponentCatalog {
  const enabled = options?.enabled ?? true;
  const privateQuery = useListResources('sequence-component', { enabled: enabled && Boolean(userId) });
  const publicQuery = useListPublicResources('sequence-component', { enabled });
  const createComponent = useCreateSequenceComponentResource();
  const updateComponent = useUpdateSequenceComponentResource();
  const deleteComponent = useDeleteSequenceComponentResource();

  const components = useMemo(() => {
    const privateResources = userId ? privateQuery.data ?? [] : [];
    const publicResources = publicQuery.data ?? [];
    const deduped = new Map<string, SequenceComponentResource>();

    for (const resource of [...privateResources, ...publicResources]) {
      deduped.set(resource.id, toSequenceComponentResource(resource));
    }

    return [...deduped.values()];
  }, [privateQuery.data, publicQuery.data, userId]);

  return useMemo(() => createVideoEditorSequenceComponentCatalog({
    components,
    isLoading: privateQuery.isLoading || publicQuery.isLoading,
    isFetching: privateQuery.isFetching || publicQuery.isFetching,
    error: privateQuery.error ?? publicQuery.error ?? null,
    refetch: async () => Promise.all([privateQuery.refetch(), publicQuery.refetch()]),
    createComponent: async (variables) => {
      const resource = await createComponent.mutateAsync(variables);
      return { id: resource.id };
    },
    updateComponent: async (variables) => {
      const resource = await updateComponent.mutateAsync(variables);
      return { id: resource.id };
    },
    deleteComponent: async (variables) => deleteComponent.mutateAsync(variables),
  }), [
    createComponent,
    deleteComponent,
    components,
    privateQuery,
    publicQuery,
    updateComponent,
  ]);
}

export function useResolvedSequenceComponentCatalog(
  userId: string | null | undefined,
  injectedCatalog?: VideoEditorSequenceComponentCatalog | null,
): VideoEditorSequenceComponentCatalog {
  const fallbackCatalog = useSupabaseSequenceComponentCatalog(userId, { enabled: !injectedCatalog });
  return injectedCatalog ?? fallbackCatalog;
}

export function useSequenceResources(userId?: string | null | undefined) {
  const injectedCatalog = useContext(SequenceComponentCatalogContext);
  const fallbackCatalog = useSupabaseSequenceComponentCatalog(userId, { enabled: !injectedCatalog });
  return injectedCatalog ?? fallbackCatalog;
}

type CreateVars = { metadata: SequenceComponentMetadata };
type UpdateVars = { id: string; metadata: SequenceComponentMetadata };
type DeleteVars = { id: string };

export function useCreateSequenceComponentResource(): Omit<
  UseMutationResult<Resource, Error, CreateVars, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<Resource, Error, CreateVars, unknown>['mutate'];
  mutateAsync: (
    variables: CreateVars,
    options?: UseMutationOptions<Resource, Error, CreateVars, unknown>,
  ) => Promise<Resource>;
} {
  const mutation = useCreateResource();
  const base = mutation as unknown as Omit<
    UseMutationResult<Resource, Error, CreateVars, unknown>,
    'mutate' | 'mutateAsync'
  >;

  return {
    ...base,
    mutate: ((variables, options) => mutation.mutate(
      { type: 'sequence-component', metadata: variables.metadata } as CreateResourceArgs,
      options as Parameters<typeof mutation.mutate>[1],
    )) as UseMutationResult<Resource, Error, CreateVars, unknown>['mutate'],
    mutateAsync: ((variables, options) => mutation.mutateAsync(
      { type: 'sequence-component', metadata: variables.metadata } as CreateResourceArgs,
      options as Parameters<typeof mutation.mutateAsync>[1],
    )) as (
      variables: CreateVars,
      options?: UseMutationOptions<Resource, Error, CreateVars, unknown>,
    ) => Promise<Resource>,
  };
}

export function useUpdateSequenceComponentResource(): Omit<
  UseMutationResult<Resource, Error, UpdateVars, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<Resource, Error, UpdateVars, unknown>['mutate'];
  mutateAsync: (
    variables: UpdateVars,
    options?: UseMutationOptions<Resource, Error, UpdateVars, unknown>,
  ) => Promise<Resource>;
} {
  const mutation = useUpdateResource();
  const base = mutation as unknown as Omit<
    UseMutationResult<Resource, Error, UpdateVars, unknown>,
    'mutate' | 'mutateAsync'
  >;

  return {
    ...base,
    mutate: ((variables, options) => mutation.mutate(
      { id: variables.id, type: 'sequence-component', metadata: variables.metadata } as UpdateResourceArgs,
      options as Parameters<typeof mutation.mutate>[1],
    )) as UseMutationResult<Resource, Error, UpdateVars, unknown>['mutate'],
    mutateAsync: ((variables, options) => mutation.mutateAsync(
      { id: variables.id, type: 'sequence-component', metadata: variables.metadata } as UpdateResourceArgs,
      options as Parameters<typeof mutation.mutateAsync>[1],
    )) as (
      variables: UpdateVars,
      options?: UseMutationOptions<Resource, Error, UpdateVars, unknown>,
    ) => Promise<Resource>,
  };
}

export function useDeleteSequenceComponentResource(): Omit<
  UseMutationResult<void, Error, DeleteVars, unknown>,
  'mutate' | 'mutateAsync'
> & {
  mutate: UseMutationResult<void, Error, DeleteVars, unknown>['mutate'];
  mutateAsync: (
    variables: DeleteVars,
    options?: UseMutationOptions<void, Error, DeleteVars, unknown>,
  ) => Promise<void>;
} {
  const mutation = useDeleteResource();

  return {
    ...mutation,
    mutate: (variables, options) =>
      mutation.mutate({ id: variables.id, type: 'sequence-component' }, options),
    mutateAsync: (variables, options) =>
      mutation.mutateAsync({ id: variables.id, type: 'sequence-component' }, options),
  };
}
