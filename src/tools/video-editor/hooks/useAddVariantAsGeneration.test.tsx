// @vitest-environment jsdom

import { act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHookWithProviders } from '@/test/test-utils';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';

const mocks = vi.hoisted(() => ({
  addClip: vi.fn(),
  loadPrimaryVariantForGeneration: vi.fn(),
  patchRegistry: vi.fn(),
  promoteVariant: vi.fn(),
  registerAsset: vi.fn(),
  toastError: vi.fn(),
  unpatchRegistry: vi.fn(),
}));

vi.mock('@/tools/video-editor/contexts/DataProviderContext.tsx', () => ({
  useVideoEditorRuntime: () => ({
    project: { projectId: 'project-1' },
    toast: { error: (...args: unknown[]) => mocks.toastError(...args) },
  }),
}));

vi.mock('@/tools/video-editor/hooks/useTimelineCommands.ts', () => ({
  useTimelineCommands: () => ({
    addClip: mocks.addClip,
  }),
}));

vi.mock('@/tools/video-editor/hooks/timelineStore.ts', () => ({
  useTimelineEditorOps: () => ({
    patchRegistry: mocks.patchRegistry,
    registerAsset: mocks.registerAsset,
    unpatchRegistry: mocks.unpatchRegistry,
  }),
  useTimelineMutableAdapters: () => ({
    dataRef: {
      current: {
        meta: {
          'clip-1': { asset: 'asset-1' },
        },
        registry: {
          assets: {
            'asset-1': { id: 'asset-1', src: 'source.png' },
          },
        },
      },
    },
  }),
}));

vi.mock('@/tools/video-editor/adapters/reigh/variantPromotionLookup.ts', () => ({
  loadPrimaryVariantForGeneration: (...args: unknown[]) => mocks.loadPrimaryVariantForGeneration(...args),
}));

vi.mock('@/shared/hooks/variants/usePromoteVariantToGeneration.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/hooks/variants/usePromoteVariantToGeneration')>();
  return {
    ...actual,
    usePromoteVariantToGeneration: () => ({
      mutateAsync: mocks.promoteVariant,
      isPending: false,
    }),
  };
});

import { VARIANT_PROMOTION_UNSUPPORTED_CODE } from '@/shared/hooks/variants/usePromoteVariantToGeneration';
import { useAddVariantAsGeneration } from './useAddVariantAsGeneration';

const variant: GenerationVariant = {
  id: 'variant-1',
  generation_id: 'generation-1',
  location: 'variant.png',
  thumbnail_url: 'variant-thumb.png',
  params: null,
  is_primary: false,
  starred: false,
  variant_type: null,
  name: null,
  created_at: '2026-01-01T00:00:00.000Z',
  viewed_at: null,
};

describe('useAddVariantAsGeneration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not register an asset or insert a clip when variant promotion is unsupported', async () => {
    mocks.promoteVariant.mockRejectedValue({
      code: VARIANT_PROMOTION_UNSUPPORTED_CODE,
      message: 'variant promotion disabled',
    });

    const { result } = renderHookWithProviders(() => useAddVariantAsGeneration());

    await act(async () => {
      await result.current.addVariantAsGenerationAfterClip('clip-1', variant);
    });

    expect(mocks.loadPrimaryVariantForGeneration).not.toHaveBeenCalled();
    expect(mocks.patchRegistry).not.toHaveBeenCalled();
    expect(mocks.registerAsset).not.toHaveBeenCalled();
    expect(mocks.addClip).not.toHaveBeenCalled();
    expect(mocks.unpatchRegistry).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith('variant promotion disabled');
  });
});
