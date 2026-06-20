import type { FC } from 'react';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type {
  EffectRegistryProvenance,
  EffectRegistryRecord,
  EffectRegistryRecordStatus,
} from '@/tools/video-editor/effects/registry/types.ts';
import type {
  EffectResource,
  VideoEditorEffectCatalog,
} from '@/tools/video-editor/lib/effect-catalog.ts';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

export type EffectComponentMap = Readonly<Record<string, FC<EffectComponentProps>>>;
export type EffectSchemaMap = Readonly<Record<string, ParameterSchema | undefined>>;
export type EffectCodeCompiler = (code: string, effectId: string) => FC<EffectComponentProps>;

export interface EffectAdapterOptions {
  readonly ownerExtensionId?: string;
  readonly renderability?: ContributionRenderability;
  readonly status?: EffectRegistryRecordStatus;
  readonly schemaByEffectId?: EffectSchemaMap;
}

export interface BuiltInEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export interface LocalDraftEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export interface LegacyDbEffectRow {
  readonly id?: string;
  readonly slug: string;
  readonly code: string;
  readonly parameterSchema?: ParameterSchema;
}

export interface LegacyDbEffectAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
}

export type EffectResourceWithGenerationMetadata = EffectResource & {
  readonly generation_id?: string | null;
  readonly generationId?: string | null;
  readonly generatedAt?: string;
  readonly generated_at?: string;
  readonly provenance?: string;
};

export interface EffectResourceAdapterOptions extends EffectAdapterOptions {
  readonly contributionIdPrefix?: string;
  readonly provenance?: EffectRegistryProvenance;
}

export type EffectCatalogAdapterOptions = EffectResourceAdapterOptions;

export function normalizeEffectRegistryId(effectId: string): string {
  return effectId.startsWith('custom:') ? effectId.slice('custom:'.length) : effectId;
}

export function createDefaultEffectRenderability(): ContributionRenderability {
  return {
    defaultRoute: 'preview',
    determinism: 'deterministic',
    capabilities: [
      {
        route: 'preview',
        status: 'supported',
        determinism: 'deterministic',
      },
      {
        route: 'browser-export',
        status: 'supported',
        determinism: 'deterministic',
      },
      {
        route: 'worker-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
        message: 'Effect rendering is not available in worker export by default.',
      },
      {
        route: 'sidecar-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
        message: 'Effect rendering is not available in sidecar export by default.',
      },
    ],
  };
}

function schemaFor(
  schemaByEffectId: EffectSchemaMap | undefined,
  rawEffectId: string,
  effectId: string,
): ParameterSchema | undefined {
  return schemaByEffectId?.[rawEffectId] ?? schemaByEffectId?.[effectId];
}

function createEffectRecord({
  effectId,
  contributionId,
  component,
  provenance,
  code,
  schema,
  options,
}: {
  effectId: string;
  contributionId: string;
  component: FC<EffectComponentProps>;
  provenance: EffectRegistryProvenance;
  code?: string;
  schema?: ParameterSchema;
  options: EffectAdapterOptions;
}): EffectRegistryRecord {
  return {
    effectId,
    contributionId,
    component,
    ...(schema !== undefined ? { schema } : {}),
    ...(code !== undefined ? { code } : {}),
    provenance,
    ...(options.ownerExtensionId ? { ownerExtensionId: options.ownerExtensionId } : {}),
    renderability: options.renderability ?? createDefaultEffectRenderability(),
    status: options.status ?? 'active',
  };
}

export function builtInEffectsToRegistryRecords(
  effects: EffectComponentMap,
  options: BuiltInEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'built-in:effect';

  return Object.entries(effects).map(([rawEffectId, component]) => {
    const effectId = normalizeEffectRegistryId(rawEffectId);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component,
      provenance: 'built-in',
      schema: schemaFor(options.schemaByEffectId, rawEffectId, effectId),
      options,
    });
  });
}

export function localDraftEffectsToRegistryRecords(
  drafts: Readonly<Record<string, string>>,
  compile: EffectCodeCompiler,
  options: LocalDraftEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'local-draft:effect';

  return Object.entries(drafts).map(([rawEffectId, code]) => {
    const effectId = normalizeEffectRegistryId(rawEffectId);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component: compile(code, effectId),
      provenance: 'local-storage-draft',
      code,
      schema: schemaFor(options.schemaByEffectId, rawEffectId, effectId),
      options,
    });
  });
}

function provenanceForEffectResource(
  resource: EffectResourceWithGenerationMetadata,
  fallback: EffectRegistryProvenance,
): EffectRegistryProvenance {
  if (
    resource.provenance === 'ai-generated'
    || resource.generation_id
    || resource.generationId
    || resource.generatedAt
    || resource.generated_at
  ) {
    return 'ai-generated';
  }

  return fallback;
}

export function legacyDbEffectsToRegistryRecords(
  effects: readonly LegacyDbEffectRow[] | undefined,
  compile: EffectCodeCompiler,
  options: LegacyDbEffectAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'legacy-db:effect';

  return (effects ?? []).map((effect) => {
    const effectId = normalizeEffectRegistryId(effect.slug);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component: compile(effect.code, effectId),
      provenance: 'legacy-db-effect',
      code: effect.code,
      schema: effect.parameterSchema ?? schemaFor(options.schemaByEffectId, effect.slug, effectId),
      options,
    });
  });
}

export function effectResourcesToRegistryRecords(
  resources: readonly EffectResourceWithGenerationMetadata[] | undefined,
  compile: EffectCodeCompiler,
  options: EffectResourceAdapterOptions = {},
): EffectRegistryRecord[] {
  const contributionIdPrefix = options.contributionIdPrefix ?? 'db-resource:effect';
  const fallbackProvenance = options.provenance ?? 'db-resource';

  return (resources ?? []).map((resource) => {
    const effectId = normalizeEffectRegistryId(resource.id);
    return createEffectRecord({
      effectId,
      contributionId: `${contributionIdPrefix}:${effectId}`,
      component: compile(resource.code, effectId),
      provenance: provenanceForEffectResource(resource, fallbackProvenance),
      code: resource.code,
      schema: resource.parameterSchema ?? schemaFor(options.schemaByEffectId, resource.id, effectId),
      options,
    });
  });
}

export function effectCatalogToRegistryRecords(
  catalog: Pick<VideoEditorEffectCatalog, 'effects'> | null | undefined,
  compile: EffectCodeCompiler,
  options: EffectCatalogAdapterOptions = {},
): EffectRegistryRecord[] {
  return effectResourcesToRegistryRecords(catalog?.effects, compile, {
    contributionIdPrefix: options.contributionIdPrefix ?? 'external-catalog:effect',
    provenance: options.provenance ?? 'external-catalog',
    ...options,
  });
}
