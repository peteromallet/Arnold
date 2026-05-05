import type { EffectMetadata } from '@/features/resources/hooks/useResources.ts';

export type EffectCategory = EffectMetadata['category'];

export type EffectResource = EffectMetadata & {
  id: string;
  type: 'effect';
  userId?: string;
  user_id?: string;
  isPublic?: boolean;
  is_public?: boolean;
  createdAt?: string;
  created_at?: string;
};

export type EffectResourcesByCategory = Record<EffectCategory, EffectResource[]>;

export interface CreateVideoEditorEffectInput {
  metadata: EffectMetadata;
}

export interface UpdateVideoEditorEffectInput {
  id: string;
  metadata: EffectMetadata;
}

export interface DeleteVideoEditorEffectInput {
  id: string;
}

export interface VideoEditorEffectCatalogOptions {
  effects?: EffectResource[];
  isLoading?: boolean;
  isFetching?: boolean;
  error?: Error | null;
  refetch?: () => Promise<unknown>;
  createEffect?: (input: CreateVideoEditorEffectInput) => Promise<{ id: string }>;
  updateEffect?: (input: UpdateVideoEditorEffectInput) => Promise<{ id: string }>;
  deleteEffect?: (input: DeleteVideoEditorEffectInput) => Promise<void>;
}

export interface VideoEditorEffectCatalog {
  data: EffectResourcesByCategory;
  effects: EffectResource[];
  entrance: EffectResource[];
  exit: EffectResource[];
  continuous: EffectResource[];
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
  canCreateEffect: boolean;
  canUpdateEffect: boolean;
  canDeleteEffect: boolean;
  createEffect?: (input: CreateVideoEditorEffectInput) => Promise<{ id: string }>;
  updateEffect?: (input: UpdateVideoEditorEffectInput) => Promise<{ id: string }>;
  deleteEffect?: (input: DeleteVideoEditorEffectInput) => Promise<void>;
}

export const EMPTY_EFFECT_GROUPS: EffectResourcesByCategory = {
  entrance: [],
  exit: [],
  continuous: [],
};

function dedupeEffectResources(resources: EffectResource[]): EffectResource[] {
  const deduped = new Map<string, EffectResource>();

  for (const resource of resources) {
    deduped.set(resource.id, resource);
  }

  return [...deduped.values()];
}

function groupEffectResources(resources: EffectResource[]): EffectResourcesByCategory {
  if (resources.length === 0) {
    return EMPTY_EFFECT_GROUPS;
  }

  return resources.reduce<EffectResourcesByCategory>((groups, resource) => {
    groups[resource.category].push(resource);
    return groups;
  }, {
    entrance: [],
    exit: [],
    continuous: [],
  });
}

export function createVideoEditorEffectCatalog(
  options: VideoEditorEffectCatalogOptions = {},
): VideoEditorEffectCatalog {
  const effects = dedupeEffectResources(options.effects ?? []);
  const data = groupEffectResources(effects);

  return {
    data,
    effects,
    entrance: data.entrance,
    exit: data.exit,
    continuous: data.continuous,
    isLoading: options.isLoading ?? false,
    isFetching: options.isFetching ?? false,
    error: options.error ?? null,
    refetch: options.refetch ?? (async () => undefined),
    canCreateEffect: typeof options.createEffect === 'function',
    canUpdateEffect: typeof options.updateEffect === 'function',
    canDeleteEffect: typeof options.deleteEffect === 'function',
    createEffect: options.createEffect,
    updateEffect: options.updateEffect,
    deleteEffect: options.deleteEffect,
  };
}
