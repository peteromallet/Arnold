import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';
import type { EffectRegistryProvenance, EffectRegistryRecord, EffectRegistryRecordStatus } from '@/tools/video-editor/effects/registry/types';
import type { ContributionRenderability, RenderCapability, RenderRoute } from '@/tools/video-editor/runtime/renderability';
import type { ParameterSchema } from '@/tools/video-editor/types';
import {
  createVideoEditorEffectCatalog,
  registryRecordToEffectResource,
} from './effect-catalog';
import type { EffectResource } from './effect-catalog';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const dummyComponent: FC<EffectComponentProps> = () => null;

function makeCapability(route: RenderRoute, status: 'supported' | 'blocked' | 'unknown' = 'supported'): RenderCapability {
  return {
    route,
    status,
    determinism: 'deterministic',
  };
}

function makeRenderability(overrides: Partial<ContributionRenderability> = {}): ContributionRenderability {
  return {
    capabilities: [
      makeCapability('preview', 'supported'),
      makeCapability('browser-export', 'blocked'),
      makeCapability('worker-export', 'blocked'),
    ],
    determinism: 'deterministic',
    ...overrides,
  };
}

function makeRegistryRecord(overrides: Partial<EffectRegistryRecord> = {}): EffectRegistryRecord {
  return {
    effectId: 'test-effect-1',
    contributionId: 'contrib-1',
    component: dummyComponent,
    provenance: 'bundled-extension' as EffectRegistryProvenance,
    renderability: makeRenderability(),
    status: 'active' as EffectRegistryRecordStatus,
    ...overrides,
  };
}

function makeDiagnostic(code: string, message: string, severity: 'error' | 'warning' | 'info' = 'error'): ExtensionDiagnostic {
  return { code, message, severity };
}

function makeDbEffect(overrides: Partial<EffectResource> = {}): EffectResource {
  return {
    id: 'db-effect-1',
    type: 'effect',
    name: 'DB Effect',
    slug: 'db-effect',
    code: 'code-1',
    category: 'continuous',
    description: 'A DB effect',
    created_by: { is_you: true },
    is_public: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// registryRecordToEffectResource
// ---------------------------------------------------------------------------

describe('registryRecordToEffectResource', () => {
  it('maps effectId to id', () => {
    const record = makeRegistryRecord({ effectId: 'com.example.glow' });
    const resource = registryRecordToEffectResource(record);
    expect(resource.id).toBe('com.example.glow');
  });

  it('sets type to "effect"', () => {
    const resource = registryRecordToEffectResource(makeRegistryRecord());
    expect(resource.type).toBe('effect');
  });

  it('uses effectId as name and slug', () => {
    const record = makeRegistryRecord({ effectId: 'com.example.glow' });
    const resource = registryRecordToEffectResource(record);
    expect(resource.name).toBe('com.example.glow');
    expect(resource.slug).toBe('com.example.glow');
  });

  it('maps record.code to code, defaulting to empty string', () => {
    const withCode = registryRecordToEffectResource(makeRegistryRecord({ code: 'function Effect() {}' }));
    expect(withCode.code).toBe('function Effect() {}');

    const withoutCode = registryRecordToEffectResource(makeRegistryRecord({ code: undefined }));
    expect(withoutCode.code).toBe('');
  });

  it('defaults category to continuous', () => {
    const resource = registryRecordToEffectResource(makeRegistryRecord());
    expect(resource.category).toBe('continuous');
  });

  it('sets description with provenance', () => {
    const resource = registryRecordToEffectResource(
      makeRegistryRecord({ provenance: 'bundled-extension' }),
    );
    expect(resource.description).toContain('bundled-extension');
  });

  it('maps parameterSchema from record.schema', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', min: 0, max: 1, step: 0.1, default: 0.5 },
    ];
    const resource = registryRecordToEffectResource(makeRegistryRecord({ schema }));
    expect(resource.parameterSchema).toEqual(schema);
  });

  it('leaves parameterSchema undefined when record has no schema', () => {
    const resource = registryRecordToEffectResource(makeRegistryRecord({ schema: undefined }));
    expect(resource.parameterSchema).toBeUndefined();
  });

  it('maps provenance through', () => {
    const provenances: EffectRegistryProvenance[] = [
      'bundled-extension',
      'external-catalog',
      'db-resource',
      'ai-generated',
      'local-storage-draft',
      'trusted-loader',
      'built-in',
      'legacy-db-effect',
    ];
    for (const provenance of provenances) {
      const resource = registryRecordToEffectResource(makeRegistryRecord({ provenance }));
      expect(resource.provenance).toBe(provenance);
    }
  });

  it('maps renderability through', () => {
    const renderability = makeRenderability({
      capabilities: [makeCapability('preview', 'supported'), makeCapability('browser-export', 'supported')],
    });
    const resource = registryRecordToEffectResource(makeRegistryRecord({ renderability }));
    expect(resource.renderability).toBe(renderability);
  });

  it('maps diagnostics through', () => {
    const diagnostics = [makeDiagnostic('effects/invalid-schema', 'Invalid schema')];
    const resource = registryRecordToEffectResource(makeRegistryRecord({ diagnostics }));
    expect(resource.diagnostics).toBe(diagnostics);
  });

  it('maps ownerExtensionId through', () => {
    const resource = registryRecordToEffectResource(
      makeRegistryRecord({ ownerExtensionId: 'ext-1' }),
    );
    expect(resource.ownerExtensionId).toBe('ext-1');
  });

  it('maps registryStatus through', () => {
    const active = registryRecordToEffectResource(makeRegistryRecord({ status: 'active' }));
    expect(active.registryStatus).toBe('active');

    const inactive = registryRecordToEffectResource(makeRegistryRecord({ status: 'inactive' }));
    expect(inactive.registryStatus).toBe('inactive');

    const error = registryRecordToEffectResource(makeRegistryRecord({ status: 'error' }));
    expect(error.registryStatus).toBe('error');
  });

  it('sets readOnly=true for bundled-extension provenance', () => {
    const resource = registryRecordToEffectResource(
      makeRegistryRecord({ provenance: 'bundled-extension' }),
    );
    expect(resource.readOnly).toBe(true);
  });

  it('sets readOnly=false for non-bundled-extension provenances', () => {
    const nonBundled: EffectRegistryProvenance[] = [
      'external-catalog',
      'db-resource',
      'ai-generated',
      'local-storage-draft',
      'trusted-loader',
      'built-in',
      'legacy-db-effect',
    ];
    for (const provenance of nonBundled) {
      const resource = registryRecordToEffectResource(makeRegistryRecord({ provenance }));
      expect(resource.readOnly).toBe(false);
    }
  });

  it('sets created_by with is_you=false', () => {
    const resource = registryRecordToEffectResource(makeRegistryRecord());
    expect(resource.created_by).toEqual({ is_you: false });
  });

  it('sets is_public to false', () => {
    const resource = registryRecordToEffectResource(makeRegistryRecord());
    expect(resource.is_public).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// createVideoEditorEffectCatalog
// ---------------------------------------------------------------------------

describe('createVideoEditorEffectCatalog', () => {
  it('creates catalog from DB effects alone', () => {
    const catalog = createVideoEditorEffectCatalog({
      effects: [makeDbEffect({ id: 'e1', name: 'Effect 1', category: 'entrance' })],
    });

    expect(catalog.effects).toHaveLength(1);
    expect(catalog.entrance).toHaveLength(1);
    expect(catalog.exit).toHaveLength(0);
    expect(catalog.continuous).toHaveLength(0);
    expect(catalog.entrance[0].name).toBe('Effect 1');
  });

  it('merges registry records with DB effects', () => {
    const record = makeRegistryRecord({ effectId: 'ext-effect', provenance: 'bundled-extension' });
    const catalog = createVideoEditorEffectCatalog({
      effects: [makeDbEffect({ id: 'db-effect', name: 'DB', category: 'entrance' })],
      registryRecords: [record],
    });

    expect(catalog.effects).toHaveLength(2);
    // Registry records default to continuous
    const extEffect = catalog.effects.find((e) => e.id === 'ext-effect');
    expect(extEffect).toBeDefined();
    expect(extEffect!.provenance).toBe('bundled-extension');
    const dbEffect = catalog.effects.find((e) => e.id === 'db-effect');
    expect(dbEffect).toBeDefined();
  });

  it('registry record overrides DB effect with same id', () => {
    const record = makeRegistryRecord({
      effectId: 'db-effect-1',
      provenance: 'bundled-extension',
      code: 'registry-code',
    });
    const catalog = createVideoEditorEffectCatalog({
      effects: [makeDbEffect({ id: 'db-effect-1', code: 'db-code' })],
      registryRecords: [record],
    });

    expect(catalog.effects).toHaveLength(1);
    expect(catalog.effects[0].code).toBe('registry-code');
    expect(catalog.effects[0].provenance).toBe('bundled-extension');
  });

  it('registry records without DB effects', () => {
    const record = makeRegistryRecord({ effectId: 'ext-only' });
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: [record],
    });

    expect(catalog.effects).toHaveLength(1);
    expect(catalog.effects[0].id).toBe('ext-only');
  });

  it('empty registry records do not affect DB effects', () => {
    const catalog = createVideoEditorEffectCatalog({
      effects: [makeDbEffect()],
      registryRecords: [],
    });

    expect(catalog.effects).toHaveLength(1);
    expect(catalog.effects[0].id).toBe('db-effect-1');
  });

  it('groups effects by category', () => {
    const catalog = createVideoEditorEffectCatalog({
      effects: [
        makeDbEffect({ id: 'e1', category: 'entrance' }),
        makeDbEffect({ id: 'e2', category: 'exit' }),
        makeDbEffect({ id: 'e3', category: 'continuous' }),
      ],
    });

    expect(catalog.entrance).toHaveLength(1);
    expect(catalog.entrance[0].id).toBe('e1');
    expect(catalog.exit).toHaveLength(1);
    expect(catalog.exit[0].id).toBe('e2');
    expect(catalog.continuous).toHaveLength(1);
    expect(catalog.continuous[0].id).toBe('e3');
  });

  it('registry records default to continuous category', () => {
    const record = makeRegistryRecord({ effectId: 'ext-continuous' });
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: [record],
    });

    expect(catalog.continuous).toHaveLength(1);
    expect(catalog.continuous[0].id).toBe('ext-continuous');
    expect(catalog.entrance).toHaveLength(0);
    expect(catalog.exit).toHaveLength(0);
  });

  it('canCreateEffect is true when createEffect function is provided', () => {
    const withCreate = createVideoEditorEffectCatalog({
      createEffect: async () => ({ id: 'new' }),
    });
    expect(withCreate.canCreateEffect).toBe(true);

    const withoutCreate = createVideoEditorEffectCatalog({});
    expect(withoutCreate.canCreateEffect).toBe(false);
  });

  it('canUpdateEffect is true when updateEffect function is provided', () => {
    const withUpdate = createVideoEditorEffectCatalog({
      updateEffect: async () => ({ id: 'updated' }),
    });
    expect(withUpdate.canUpdateEffect).toBe(true);

    const withoutUpdate = createVideoEditorEffectCatalog({});
    expect(withoutUpdate.canUpdateEffect).toBe(false);
  });

  it('canDeleteEffect is true when deleteEffect function is provided', () => {
    const withDelete = createVideoEditorEffectCatalog({
      deleteEffect: async () => undefined,
    });
    expect(withDelete.canDeleteEffect).toBe(true);

    const withoutDelete = createVideoEditorEffectCatalog({});
    expect(withoutDelete.canDeleteEffect).toBe(false);
  });

  it('preserves error-status records with diagnostics', () => {
    const diagnostics = [makeDiagnostic('effects/invalid-schema', 'Invalid number default')];
    const record = makeRegistryRecord({
      effectId: 'error-effect',
      status: 'error',
      diagnostics,
    });
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: [record],
    });

    const errorEffect = catalog.effects[0];
    expect(errorEffect.registryStatus).toBe('error');
    expect(errorEffect.diagnostics).toEqual(diagnostics);
  });

  it('preserves renderability for preview-only effects', () => {
    const renderability = makeRenderability({
      capabilities: [
        makeCapability('preview', 'supported'),
        makeCapability('browser-export', 'blocked'),
        makeCapability('worker-export', 'blocked'),
      ],
    });
    const record = makeRegistryRecord({ effectId: 'preview-only', renderability });
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: [record],
    });

    expect(catalog.effects[0].renderability).toBe(renderability);
  });

  it('multiple registry records all appear in catalog', () => {
    const records = [
      makeRegistryRecord({ effectId: 'ext-1' }),
      makeRegistryRecord({ effectId: 'ext-2' }),
      makeRegistryRecord({ effectId: 'ext-3' }),
    ];
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: records,
    });

    expect(catalog.effects).toHaveLength(3);
    expect(catalog.effects.map((e) => e.id).sort()).toEqual(['ext-1', 'ext-2', 'ext-3']);
  });

  it('deduplicates effects with same id (registry wins last)', () => {
    // Two registry records with same id — second overwrites first
    const records = [
      makeRegistryRecord({ effectId: 'dup', code: 'first' }),
      makeRegistryRecord({ effectId: 'dup', code: 'second' }),
    ];
    const catalog = createVideoEditorEffectCatalog({
      registryRecords: records,
    });

    expect(catalog.effects).toHaveLength(1);
    expect(catalog.effects[0].code).toBe('second');
  });

  it('defaults isLoading to false', () => {
    const catalog = createVideoEditorEffectCatalog({});
    expect(catalog.isLoading).toBe(false);
  });

  it('defaults isFetching to false', () => {
    const catalog = createVideoEditorEffectCatalog({});
    expect(catalog.isFetching).toBe(false);
  });

  it('defaults error to null', () => {
    const catalog = createVideoEditorEffectCatalog({});
    expect(catalog.error).toBeNull();
  });

  it('provides a noop refetch when not supplied', async () => {
    const catalog = createVideoEditorEffectCatalog({});
    await expect(catalog.refetch()).resolves.toBeUndefined();
  });
});
