import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { useEffect, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  EffectRegistryProvider,
  useEffectRegistryContext,
  useEffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/EffectRegistryContext';
import { effectCatalogToRegistryRecords } from '@/tools/video-editor/effects/registry/adapters/effectSourceAdapters';
import {
  createVideoEditorEffectCatalog,
  EffectCatalogProvider,
  useCreateEffectResource,
  useDeleteEffectResource,
  useEffectResources,
  useResolvedEffectCatalog,
  useUpdateEffectResource,
} from './useEffectResources';

const mocks = vi.hoisted(() => ({
  useListResources: vi.fn(),
  useListPublicResources: vi.fn(),
  useCreateResource: vi.fn(),
  useUpdateResource: vi.fn(),
  useDeleteResource: vi.fn(),
  compileEffect: vi.fn(),
}));

vi.mock('@/features/resources/hooks/useResources', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/resources/hooks/useResources')>();
  return {
    ...actual,
    useListResources: (...args: unknown[]) => mocks.useListResources(...args),
    useListPublicResources: (...args: unknown[]) => mocks.useListPublicResources(...args),
    useCreateResource: (...args: unknown[]) => mocks.useCreateResource(...args),
    useUpdateResource: (...args: unknown[]) => mocks.useUpdateResource(...args),
    useDeleteResource: (...args: unknown[]) => mocks.useDeleteResource(...args),
  };
});

vi.mock('@/tools/video-editor/effects/compileEffect.tsx', () => ({
  compileEffect: mocks.compileEffect,
}));

function CatalogRegistryProbe() {
  const catalog = useEffectResources('user-1');
  const { registry } = useEffectRegistryContext();
  const snapshot = useEffectRegistrySnapshot();

  useEffect(() => {
    const handles = effectCatalogToRegistryRecords(catalog, mocks.compileEffect)
      .map((record) => registry.register(record));

    return () => {
      handles.forEach((handle) => handle.dispose());
    };
  }, [catalog, registry]);

  const mirroredRecords = snapshot.records
    .filter((record) => record.effectId.startsWith('catalog-'))
    .map((record) => ({
      effectId: record.effectId,
      code: record.code,
      provenance: record.provenance,
    }));

  return <output data-testid="registry-records">{JSON.stringify(mirroredRecords)}</output>;
}

function catalogRegistryWrapper(catalog: ReturnType<typeof createVideoEditorEffectCatalog>) {
  return function CatalogRegistryWrapper({ children }: { children: ReactNode }) {
    return (
      <EffectCatalogProvider value={catalog}>
        <EffectRegistryProvider>{children}</EffectRegistryProvider>
      </EffectCatalogProvider>
    );
  };
}

describe('useEffectResources', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.compileEffect.mockReturnValue(({ children }: { children?: ReactNode }) => (
      <div data-testid="compiled-registry-effect">{children}</div>
    ));

    mocks.useListResources.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    mocks.useListPublicResources.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    mocks.useCreateResource.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ id: 'created' }),
    });
    mocks.useUpdateResource.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ id: 'updated' }),
    });
    mocks.useDeleteResource.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue(undefined),
    });
  });

  it('deduplicates by resource id and groups effects by category', () => {
    mocks.useListResources.mockReturnValue({
      data: [
        {
          id: 'effect-1',
          type: 'effect',
          metadata: {
            name: 'Slide In',
            slug: 'slide-in',
            code: 'code-1',
            category: 'entrance',
            description: 'Slides in',
            created_by: { is_you: true },
            is_public: false,
          },
        },
        {
          id: 'effect-2',
          type: 'effect',
          metadata: {
            name: 'Fade Out',
            slug: 'fade-out',
            code: 'code-2-private',
            category: 'exit',
            description: 'Fades out',
            created_by: { is_you: true },
            is_public: false,
          },
        },
      ],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    mocks.useListPublicResources.mockReturnValue({
      data: [
        {
          id: 'effect-2',
          type: 'effect',
          metadata: {
            name: 'Fade Out Public',
            slug: 'fade-out-public',
            code: 'code-2-public',
            category: 'exit',
            description: 'Public duplicate',
            created_by: { is_you: false, username: 'other-user' },
            is_public: true,
          },
        },
        {
          id: 'effect-3',
          type: 'effect',
          metadata: {
            name: 'Pulse Loop',
            slug: 'pulse-loop',
            code: 'code-3',
            category: 'continuous',
            description: 'Loops continuously',
            created_by: { is_you: false, username: 'other-user' },
            is_public: true,
          },
        },
      ],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    const { result } = renderHook(() => useEffectResources('user-1'));

    expect(result.current.effects).toHaveLength(3);
    expect(result.current.entrance.map((effect) => effect.id)).toEqual(['effect-1']);
    expect(result.current.exit.map((effect) => effect.id)).toEqual(['effect-2']);
    expect(result.current.continuous.map((effect) => effect.id)).toEqual(['effect-3']);
    expect(result.current.exit[0]).toMatchObject({
      id: 'effect-2',
      name: 'Fade Out Public',
      category: 'exit',
    });
    expect(result.current.canCreateEffect).toBe(true);
    expect(result.current.canUpdateEffect).toBe(true);
  });

  it('uses an injected catalog and disables the Supabase resource queries', () => {
    const injectedCatalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'effect-1',
        type: 'effect',
        name: 'Injected Effect',
        slug: 'injected-effect',
        code: 'code-1',
        category: 'continuous',
        description: 'Injected',
        created_by: { is_you: true },
        is_public: false,
      }],
    });

    const { result } = renderHook(
      () => useResolvedEffectCatalog('user-1', injectedCatalog),
    );

    expect(result.current).toBe(injectedCatalog);
    expect(mocks.useListResources).toHaveBeenCalledWith('effect', { enabled: false });
    expect(mocks.useListPublicResources).toHaveBeenCalledWith('effect', { enabled: false });
  });

  it('prefers the injected catalog from context for consumer hooks', () => {
    const injectedCatalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'effect-1',
        type: 'effect',
        name: 'Standalone Fade',
        slug: 'standalone-fade',
        code: 'code-1',
        category: 'entrance',
        description: 'Standalone',
        created_by: { is_you: true },
        is_public: false,
      }],
    });

    const wrapper = ({ children }: { children: any }) => (
      <EffectCatalogProvider value={injectedCatalog}>
        {children}
      </EffectCatalogProvider>
    );

    const { result } = renderHook(() => useEffectResources('user-1'), { wrapper });

    expect(result.current).toBe(injectedCatalog);
    expect(mocks.useListResources).toHaveBeenCalledWith('effect', { enabled: false });
    expect(mocks.useListPublicResources).toHaveBeenCalledWith('effect', { enabled: false });
  });

  it('wraps create, update, and delete mutations with the fixed effect resource type', async () => {
    const createMutate = vi.fn();
    const createMutateAsync = vi.fn().mockResolvedValue({ id: 'created' });
    const updateMutate = vi.fn();
    const updateMutateAsync = vi.fn().mockResolvedValue({ id: 'updated' });
    const deleteMutate = vi.fn();
    const deleteMutateAsync = vi.fn().mockResolvedValue(undefined);

    mocks.useCreateResource.mockReturnValue({ mutate: createMutate, mutateAsync: createMutateAsync });
    mocks.useUpdateResource.mockReturnValue({ mutate: updateMutate, mutateAsync: updateMutateAsync });
    mocks.useDeleteResource.mockReturnValue({ mutate: deleteMutate, mutateAsync: deleteMutateAsync });

    const createHook = renderHook(() => useCreateEffectResource());
    const updateHook = renderHook(() => useUpdateEffectResource());
    const deleteHook = renderHook(() => useDeleteEffectResource());

    const metadata = {
      name: 'Slide In',
      slug: 'slide-in',
      code: 'code',
      category: 'entrance' as const,
      description: 'Slides in',
      created_by: { is_you: true },
      is_public: false,
    };

    await act(async () => {
      await createHook.result.current.mutateAsync({ metadata });
      await updateHook.result.current.mutateAsync({ id: 'effect-1', metadata });
      await deleteHook.result.current.mutateAsync({ id: 'effect-1' });
    });

    expect(createMutateAsync).toHaveBeenCalledWith({ type: 'effect', metadata }, undefined);
    expect(updateMutateAsync).toHaveBeenCalledWith({ id: 'effect-1', type: 'effect', metadata }, undefined);
    expect(deleteMutateAsync).toHaveBeenCalledWith({ id: 'effect-1', type: 'effect' }, undefined);
  });

  it('mirrors injected catalog resources into the provider registry without replacing catalog APIs', async () => {
    const createEffect = vi.fn(async () => ({ id: 'created-effect' }));
    const updateEffect = vi.fn(async () => ({ id: 'updated-effect' }));
    const initialCatalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'catalog-generated-effect',
        type: 'effect',
        name: 'Generated Catalog Effect',
        slug: 'generated-catalog-effect',
        code: 'export default function GeneratedCatalogEffect() { return null; }',
        category: 'continuous',
        description: 'Generated resource',
        created_by: { is_you: true },
        is_public: false,
        generation_id: 'generation-1',
      }],
      createEffect,
      updateEffect,
    });
    const updatedCatalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'catalog-edited-effect',
        type: 'effect',
        name: 'Edited Catalog Effect',
        slug: 'edited-catalog-effect',
        code: 'export default function EditedCatalogEffect() { return null; }',
        category: 'entrance',
        description: 'Edited resource',
        created_by: { is_you: true },
        is_public: false,
      }],
      createEffect,
      updateEffect,
    });

    const { rerender } = render(<CatalogRegistryProbe />, {
      wrapper: catalogRegistryWrapper(initialCatalog),
    });

    await waitFor(() => {
      expect(screen.getByTestId('registry-records').textContent).toContain('catalog-generated-effect');
    });
    expect(screen.getByTestId('registry-records').textContent).toContain('"provenance":"ai-generated"');
    expect(initialCatalog.canCreateEffect).toBe(true);
    expect(initialCatalog.canUpdateEffect).toBe(true);
    expect(createEffect).not.toHaveBeenCalled();
    expect(updateEffect).not.toHaveBeenCalled();
    expect(mocks.useListResources).toHaveBeenCalledWith('effect', { enabled: false });
    expect(mocks.useListPublicResources).toHaveBeenCalledWith('effect', { enabled: false });

    rerender(
      <EffectCatalogProvider value={updatedCatalog}>
        <EffectRegistryProvider>
          <CatalogRegistryProbe />
        </EffectRegistryProvider>
      </EffectCatalogProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('registry-records').textContent).toContain('catalog-edited-effect');
    });
    expect(screen.getByTestId('registry-records').textContent).not.toContain('catalog-generated-effect');
    expect(screen.getByTestId('registry-records').textContent).toContain('"provenance":"external-catalog"');
  });
});

// ---------------------------------------------------------------------------
// Registry record integration in catalog
// ---------------------------------------------------------------------------

describe('registry record integration in useEffectResources catalog', () => {
  it('registry records appear alongside DB effects in the catalog', () => {
    const registryRecords = [{
      effectId: 'ext-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability: {
        capabilities: [
          { route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const },
          { route: 'browser-export' as const, status: 'blocked' as const, determinism: 'deterministic' as const },
          { route: 'worker-export' as const, status: 'blocked' as const, determinism: 'deterministic' as const },
        ],
        determinism: 'deterministic' as const,
      },
      status: 'active' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({
      effects: [{
        id: 'db-effect',
        type: 'effect' as const,
        name: 'DB Effect',
        slug: 'db-effect',
        code: 'code',
        category: 'continuous' as const,
        description: 'DB',
        created_by: { is_you: true },
        is_public: false,
      }],
      registryRecords,
    });

    expect(catalog.effects).toHaveLength(2);
    const extEffect = catalog.effects.find((e) => e.id === 'ext-effect');
    expect(extEffect).toBeDefined();
    expect(extEffect!.provenance).toBe('bundled-extension');
    expect(extEffect!.readOnly).toBe(true);

    const dbEffect = catalog.effects.find((e) => e.id === 'db-effect');
    expect(dbEffect).toBeDefined();
    expect(dbEffect!.provenance).toBeUndefined();
  });

  it('registry records carry provenance through to catalog resources', () => {
    const provenances = [
      'bundled-extension',
      'external-catalog',
      'db-resource',
      'ai-generated',
      'local-storage-draft',
      'trusted-loader',
    ] as const;

    for (const provenance of provenances) {
      const registryRecords = [{
        effectId: `effect-${provenance}`,
        contributionId: 'contrib-1',
        component: (() => null) as any,
        provenance,
        renderability: {
          capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
          determinism: 'deterministic' as const,
        },
        status: 'active' as const,
      }];

      const catalog = createVideoEditorEffectCatalog({ registryRecords });
      expect(catalog.effects[0].provenance).toBe(provenance);
    }
  });

  it('registry records carry renderability through to catalog resources', () => {
    const renderability = {
      capabilities: [
        { route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const },
        { route: 'browser-export' as const, status: 'blocked' as const, determinism: 'preview-only' as const },
      ],
      determinism: 'preview-only' as const,
    };

    const registryRecords = [{
      effectId: 'ext-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability,
      status: 'active' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.effects[0].renderability).toEqual(renderability);
  });

  it('error-status registry records appear in catalog with diagnostics', () => {
    const diagnostics = [{ code: 'effects/invalid-schema', message: 'Bad schema', severity: 'error' as const }];
    const registryRecords = [{
      effectId: 'error-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability: {
        capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
        determinism: 'deterministic' as const,
      },
      status: 'error' as const,
      diagnostics,
    }];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.effects[0].registryStatus).toBe('error');
    expect(catalog.effects[0].diagnostics).toEqual(diagnostics);
  });

  it('inactive-status registry records appear in catalog but with inactive status', () => {
    const registryRecords = [{
      effectId: 'inactive-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability: {
        capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
        determinism: 'deterministic' as const,
      },
      status: 'inactive' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.effects).toHaveLength(1);
    expect(catalog.effects[0].registryStatus).toBe('inactive');
  });

  it('registry record overrides DB effect with same id', () => {
    const dbEffect = {
      id: 'shared-id',
      type: 'effect' as const,
      name: 'DB Version',
      slug: 'db-version',
      code: 'db-code',
      category: 'continuous' as const,
      description: 'DB',
      created_by: { is_you: true },
      is_public: false,
    };

    const registryRecords = [{
      effectId: 'shared-id',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability: {
        capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
        determinism: 'deterministic' as const,
      },
      status: 'active' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({
      effects: [dbEffect],
      registryRecords,
    });

    expect(catalog.effects).toHaveLength(1);
    // Registry record wins — name comes from effectId
    expect(catalog.effects[0].name).toBe('shared-id');
    expect(catalog.effects[0].provenance).toBe('bundled-extension');
  });

  it('registry record parameter schema maps to parameterSchema field', () => {
    const paramSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number' as const, min: 0, max: 1, step: 0.1, default: 0.5 },
    ];
    const registryRecords = [{
      effectId: 'param-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      schema: paramSchema,
      renderability: {
        capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
        determinism: 'deterministic' as const,
      },
      status: 'active' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.effects[0].parameterSchema).toEqual(paramSchema);
  });

  it('registry record without schema has undefined parameterSchema', () => {
    const registryRecords = [{
      effectId: 'no-schema-effect',
      contributionId: 'contrib-1',
      component: (() => null) as any,
      provenance: 'bundled-extension' as const,
      renderability: {
        capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
        determinism: 'deterministic' as const,
      },
      status: 'active' as const,
    }];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.effects[0].parameterSchema).toBeUndefined();
  });

  it('catalog groups registry record effects by category (defaults to continuous)', () => {
    const registryRecords = [
      {
        effectId: 'ext-continuous',
        contributionId: 'contrib-1',
        component: (() => null) as any,
        provenance: 'bundled-extension' as const,
        renderability: {
          capabilities: [{ route: 'preview' as const, status: 'supported' as const, determinism: 'deterministic' as const }],
          determinism: 'deterministic' as const,
        },
        status: 'active' as const,
      },
    ];

    const catalog = createVideoEditorEffectCatalog({ registryRecords });
    expect(catalog.continuous).toHaveLength(1);
    expect(catalog.continuous[0].id).toBe('ext-continuous');
    expect(catalog.entrance).toHaveLength(0);
    expect(catalog.exit).toHaveLength(0);
  });
});
