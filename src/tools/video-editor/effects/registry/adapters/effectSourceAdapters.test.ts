import type { FC } from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  builtInEffectsToRegistryRecords,
  createDefaultEffectRenderability,
  effectCatalogToRegistryRecords,
  effectResourcesToRegistryRecords,
  legacyDbEffectsToRegistryRecords,
  localDraftEffectsToRegistryRecords,
  normalizeEffectRegistryId,
} from '@/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import { createVideoEditorEffectCatalog } from '@/tools/video-editor/lib/effect-catalog.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

const BuiltInFade: FC<EffectComponentProps> = ({ children }) => children;
const BuiltInZoom: FC<EffectComponentProps> = ({ children }) => children;
const DraftEffect: FC<EffectComponentProps> = ({ children }) => children;
const DbEffect: FC<EffectComponentProps> = ({ children }) => children;
const ResourceEffect: FC<EffectComponentProps> = ({ children }) => children;
const CatalogEffect: FC<EffectComponentProps> = ({ children }) => children;

function schema(defaultValue: number): ParameterSchema {
  return [
    {
      name: 'amount',
      label: 'Amount',
      description: 'Effect amount',
      type: 'number',
      default: defaultValue,
      min: 0,
      max: 10,
    },
  ];
}

describe('effect source registry adapters', () => {
  it('normalizes one custom prefix without otherwise changing effect IDs', () => {
    expect(normalizeEffectRegistryId('custom:glitch')).toBe('glitch');
    expect(normalizeEffectRegistryId('glitch')).toBe('glitch');
    expect(normalizeEffectRegistryId('custom:custom:glitch')).toBe('custom:glitch');
  });

  it('maps built-in effect maps to active built-in records without mutating source maps', () => {
    const builtIns = {
      fade: BuiltInFade,
      'custom:zoom': BuiltInZoom,
    };
    const zoomSchema = schema(3);
    const records = builtInEffectsToRegistryRecords(builtIns, {
      schemaByEffectId: {
        zoom: zoomSchema,
      },
    });

    expect(Object.keys(builtIns)).toEqual(['fade', 'custom:zoom']);
    expect(records).toHaveLength(2);
    expect(records[0]).toEqual(expect.objectContaining({
      effectId: 'fade',
      contributionId: 'built-in:effect:fade',
      component: BuiltInFade,
      provenance: 'built-in',
      status: 'active',
    }));
    expect(records[1]).toEqual(expect.objectContaining({
      effectId: 'zoom',
      contributionId: 'built-in:effect:zoom',
      component: BuiltInZoom,
      provenance: 'built-in',
      schema: zoomSchema,
      status: 'active',
    }));
  });

  it('maps local draft code through an injected compiler and preserves code, schema, and provenance', () => {
    const compile = vi.fn((_code: string, _effectId: string) => DraftEffect);
    const amountSchema = schema(5);
    const records = localDraftEffectsToRegistryRecords({
      'custom:draft-effect': 'export default function Draft() {}',
    }, compile, {
      schemaByEffectId: {
        'custom:draft-effect': amountSchema,
      },
    });

    expect(compile).toHaveBeenCalledWith('export default function Draft() {}', 'draft-effect');
    expect(records).toEqual([
      expect.objectContaining({
        effectId: 'draft-effect',
        contributionId: 'local-draft:effect:draft-effect',
        component: DraftEffect,
        code: 'export default function Draft() {}',
        schema: amountSchema,
        provenance: 'local-storage-draft',
        status: 'active',
      }),
    ]);
  });

  it('lets adapter callers override owner, status, contribution prefix, and renderability', () => {
    const renderability = createDefaultEffectRenderability();
    const records = builtInEffectsToRegistryRecords({ fade: BuiltInFade }, {
      contributionIdPrefix: 'host:effect',
      ownerExtensionId: 'host',
      renderability,
      status: 'inactive',
    });

    expect(records[0]).toEqual(expect.objectContaining({
      contributionId: 'host:effect:fade',
      ownerExtensionId: 'host',
      renderability,
      status: 'inactive',
    }));
  });

  it('uses deterministic preview and browser-export defaults with explicit unsupported export routes', () => {
    const records = localDraftEffectsToRegistryRecords({ draft: 'code' }, () => DraftEffect);
    const renderability = records[0].renderability;

    expect(renderability.defaultRoute).toBe('preview');
    expect(renderability.determinism).toBe('deterministic');
    expect(renderability.capabilities).toEqual([
      expect.objectContaining({ route: 'preview', status: 'supported', determinism: 'deterministic' }),
      expect.objectContaining({ route: 'browser-export', status: 'supported', determinism: 'deterministic' }),
      expect.objectContaining({
        route: 'worker-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
      }),
      expect.objectContaining({
        route: 'sidecar-export',
        status: 'blocked',
        determinism: 'unknown',
        blockerReason: 'route-unsupported',
      }),
    ]);
  });

  it('maps legacy DB effect rows by slug with legacy provenance and compiled string code', () => {
    const compile = vi.fn((_code: string, _effectId: string) => DbEffect);
    const amountSchema = schema(2);
    const records = legacyDbEffectsToRegistryRecords([
      {
        id: 'row-1',
        slug: 'custom:db-shake',
        code: 'export default function DbShake() {}',
        parameterSchema: amountSchema,
      },
    ], compile);

    expect(compile).toHaveBeenCalledWith('export default function DbShake() {}', 'db-shake');
    expect(records).toEqual([
      expect.objectContaining({
        effectId: 'db-shake',
        contributionId: 'legacy-db:effect:db-shake',
        component: DbEffect,
        code: 'export default function DbShake() {}',
        schema: amountSchema,
        provenance: 'legacy-db-effect',
        status: 'active',
      }),
    ]);
  });

  it('maps resource-table effects by resource id with db-resource provenance and schemas', () => {
    const compile = vi.fn((_code: string, _effectId: string) => ResourceEffect);
    const amountSchema = schema(4);
    const records = effectResourcesToRegistryRecords([
      {
        id: 'resource-effect',
        type: 'effect',
        name: 'Resource Effect',
        slug: 'resource-effect-slug',
        code: 'export default function ResourceEffect() {}',
        category: 'continuous',
        description: 'Resource-backed effect',
        parameterSchema: amountSchema,
        created_by: { is_you: true },
        is_public: false,
      },
    ], compile);

    expect(compile).toHaveBeenCalledWith('export default function ResourceEffect() {}', 'resource-effect');
    expect(records).toEqual([
      expect.objectContaining({
        effectId: 'resource-effect',
        contributionId: 'db-resource:effect:resource-effect',
        component: ResourceEffect,
        code: 'export default function ResourceEffect() {}',
        schema: amountSchema,
        provenance: 'db-resource',
        status: 'active',
      }),
    ]);
  });

  it('maps external effect catalogs without changing catalog grouping or resource APIs', () => {
    const compile = vi.fn((_code: string, _effectId: string) => CatalogEffect);
    const catalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'catalog-effect',
        type: 'effect',
        name: 'Catalog Effect',
        slug: 'catalog-effect',
        code: 'export default function CatalogEffect() {}',
        category: 'entrance',
        description: 'Catalog-backed effect',
        created_by: { is_you: false, username: 'library' },
        is_public: true,
      }],
      createEffect: async () => ({ id: 'created' }),
    });

    const records = effectCatalogToRegistryRecords(catalog, compile);

    expect(catalog.canCreateEffect).toBe(true);
    expect(catalog.entrance.map((effect) => effect.id)).toEqual(['catalog-effect']);
    expect(records).toEqual([
      expect.objectContaining({
        effectId: 'catalog-effect',
        contributionId: 'external-catalog:effect:catalog-effect',
        component: CatalogEffect,
        code: 'export default function CatalogEffect() {}',
        provenance: 'external-catalog',
      }),
    ]);
  });

  it('marks generated compiled-string resources with ai-generated provenance when metadata supports it', () => {
    const compile = vi.fn((_code: string, _effectId: string) => ResourceEffect);
    const records = effectResourcesToRegistryRecords([
      {
        id: 'generated-effect',
        type: 'effect',
        name: 'Generated Effect',
        slug: 'generated-effect',
        code: 'export default function GeneratedEffect() {}',
        category: 'exit',
        description: 'Generated by AI',
        created_by: { is_you: true },
        is_public: false,
        generation_id: 'generation-1',
      },
    ], compile);

    expect(records[0]).toEqual(expect.objectContaining({
      effectId: 'generated-effect',
      contributionId: 'db-resource:effect:generated-effect',
      code: 'export default function GeneratedEffect() {}',
      provenance: 'ai-generated',
    }));
  });

  it('keeps source adapters pure and does not require browser globals', () => {
    const compile = vi.fn((_code: string, _effectId: string) => ResourceEffect);
    const originalWindow = (globalThis as { window?: unknown }).window;

    try {
      Reflect.deleteProperty(globalThis, 'window');
      const records = effectResourcesToRegistryRecords([
        {
          id: 'headless-resource',
          type: 'effect',
          name: 'Headless Resource',
          slug: 'headless-resource',
          code: 'export default function HeadlessResource() {}',
          category: 'entrance',
          description: 'Headless adapter fixture',
          created_by: { is_you: true },
          is_public: false,
        },
      ], compile);

      expect(records[0]).toMatchObject({
        effectId: 'headless-resource',
        provenance: 'db-resource',
      });
      expect(compile).toHaveBeenCalledWith('export default function HeadlessResource() {}', 'headless-resource');
    } finally {
      if (originalWindow !== undefined) {
        Object.defineProperty(globalThis, 'window', {
          configurable: true,
          value: originalWindow,
        });
      }
    }
  });
});
