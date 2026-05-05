import type { SequenceComponentMetadata } from '@/features/resources/hooks/useResources';

export type SequenceComponentResource = SequenceComponentMetadata & {
  id: string;
  type: 'sequence-component';
  userId?: string;
  user_id?: string;
  isPublic?: boolean;
  is_public?: boolean;
  createdAt?: string;
  created_at?: string;
};

export interface CreateVideoEditorSequenceComponentInput {
  metadata: SequenceComponentMetadata;
}

export interface UpdateVideoEditorSequenceComponentInput {
  id: string;
  metadata: SequenceComponentMetadata;
}

export interface DeleteVideoEditorSequenceComponentInput {
  id: string;
}

export interface VideoEditorSequenceComponentCatalogOptions {
  components?: SequenceComponentResource[];
  isLoading?: boolean;
  isFetching?: boolean;
  error?: Error | null;
  refetch?: () => Promise<unknown>;
  createComponent?: (input: CreateVideoEditorSequenceComponentInput) => Promise<{ id: string }>;
  updateComponent?: (input: UpdateVideoEditorSequenceComponentInput) => Promise<{ id: string }>;
  deleteComponent?: (input: DeleteVideoEditorSequenceComponentInput) => Promise<void>;
}

export interface VideoEditorSequenceComponentCatalog {
  components: SequenceComponentResource[];
  byClipType: Record<string, SequenceComponentResource>;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
  canCreateComponent: boolean;
  canUpdateComponent: boolean;
  canDeleteComponent: boolean;
  createComponent?: (input: CreateVideoEditorSequenceComponentInput) => Promise<{ id: string }>;
  updateComponent?: (input: UpdateVideoEditorSequenceComponentInput) => Promise<{ id: string }>;
  deleteComponent?: (input: DeleteVideoEditorSequenceComponentInput) => Promise<void>;
}

function dedupeComponentResources(
  resources: SequenceComponentResource[],
): SequenceComponentResource[] {
  const deduped = new Map<string, SequenceComponentResource>();
  for (const resource of resources) {
    deduped.set(resource.id, resource);
  }
  return [...deduped.values()];
}

function indexByClipType(
  resources: SequenceComponentResource[],
): Record<string, SequenceComponentResource> {
  const index: Record<string, SequenceComponentResource> = {};
  for (const resource of resources) {
    if (resource.clipType) {
      // Last write wins on collision — caller should ensure clipType is unique.
      index[resource.clipType] = resource;
    }
  }
  return index;
}

export function createVideoEditorSequenceComponentCatalog(
  options: VideoEditorSequenceComponentCatalogOptions = {},
): VideoEditorSequenceComponentCatalog {
  const components = dedupeComponentResources(options.components ?? []);
  const byClipType = indexByClipType(components);

  return {
    components,
    byClipType,
    isLoading: options.isLoading ?? false,
    isFetching: options.isFetching ?? false,
    error: options.error ?? null,
    refetch: options.refetch ?? (async () => undefined),
    canCreateComponent: typeof options.createComponent === 'function',
    canUpdateComponent: typeof options.updateComponent === 'function',
    canDeleteComponent: typeof options.deleteComponent === 'function',
    createComponent: options.createComponent,
    updateComponent: options.updateComponent,
    deleteComponent: options.deleteComponent,
  };
}
