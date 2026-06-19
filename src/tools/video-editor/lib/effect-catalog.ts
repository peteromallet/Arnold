import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { EffectMetadata } from '@/features/resources/hooks/useResources.ts';
import type {
  EffectRegistryProvenance,
  EffectRegistryRecord,
  EffectRegistryRecordStatus,
} from '@/tools/video-editor/effects/registry/types.ts';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';

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
  /** Registry provenance when sourced from a provider-scoped registry record. */
  provenance?: EffectRegistryProvenance;
  /** Renderability summary when sourced from a registry record. */
  renderability?: ContributionRenderability;
  /** Diagnostics associated with the registry record, if any. */
  diagnostics?: readonly ExtensionDiagnostic[];
  /** Extension that owns this effect (bundled-extension provenance). */
  ownerExtensionId?: string;
  /** Whether this effect record is read-only (e.g. bundled-extension effects per SD3). */
  readOnly?: boolean;
  /** Registry record status (active, inactive, error). */
  registryStatus?: EffectRegistryRecordStatus;
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
  /** Provider-scoped registry records to merge into the catalog. */
  registryRecords?: readonly EffectRegistryRecord[];
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

/**
 * Determine if an EffectRegistryRecord should be treated as read-only.
 * Per SD3: bundled-extension component effects are read-only in M7.
 */
function isReadOnlyRecord(record: EffectRegistryRecord): boolean {
  return record.provenance === 'bundled-extension';
}

/**
 * Derive an EffectCategory from a registry record's metadata.
 * Registry records don't natively carry a category, so we default to
 * 'continuous' unless the record has enough metadata to infer one.
 * Callers can override by providing a category mapping.
 */
function inferCategory(_record: EffectRegistryRecord): EffectCategory {
  // Registry records from bundled extensions don't carry category metadata.
  // Default to 'continuous' so they appear in the catalog alongside DB effects.
  return 'continuous';
}

/**
 * Convert a provider-scoped {@link EffectRegistryRecord} into a catalog
 * {@link EffectResource} so it can appear in the effect picker alongside
 * DB-backed and built-in effects.
 */
export function registryRecordToEffectResource(
  record: EffectRegistryRecord,
): EffectResource {
  const category = inferCategory(record);

  return {
    id: record.effectId,
    type: 'effect' as const,
    name: record.effectId,
    slug: record.effectId,
    code: record.code ?? '',
    category,
    description: `Trusted component effect (${record.provenance})`,
    created_by: { is_you: false },
    is_public: false,
    parameterSchema: record.schema,
    provenance: record.provenance,
    renderability: record.renderability,
    diagnostics: record.diagnostics,
    ownerExtensionId: record.ownerExtensionId,
    readOnly: isReadOnlyRecord(record),
    registryStatus: record.status,
  };
}

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

/**
 * Merge DB/resource effects with provider-scoped registry records.
 *
 * Duplicate resolution: registry records take precedence over DB effects
 * with the same id. Legacy `custom:{resourceId}` ids are preserved as-is
 * (normalization happens at the registry boundary, not here).
 */
function mergeEffectSources(
  dbEffects: EffectResource[],
  registryRecords: readonly EffectRegistryRecord[],
): EffectResource[] {
  if (registryRecords.length === 0) {
    return dbEffects;
  }

  const merged = new Map<string, EffectResource>();

  // DB effects go in first (lower priority)
  for (const effect of dbEffects) {
    merged.set(effect.id, effect);
  }

  // Registry records overwrite DB effects with the same id
  for (const record of registryRecords) {
    const resource = registryRecordToEffectResource(record);
    merged.set(resource.id, resource);
  }

  return [...merged.values()];
}

export function createVideoEditorEffectCatalog(
  options: VideoEditorEffectCatalogOptions = {},
): VideoEditorEffectCatalog {
  const dbEffects = options.effects ?? [];
  const registryRecords = options.registryRecords ?? [];
  const merged = mergeEffectSources(dbEffects, registryRecords);
  const effects = dedupeEffectResources(merged);
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
