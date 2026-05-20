// @vitest-environment jsdom

import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  addImageToShot: vi.fn(),
  promoteVariant: vi.fn(),
  supabaseFrom: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: (...args: unknown[]) => mocks.toastError(...args),
  },
}));

vi.mock('@/shared/hooks/variants/usePromoteVariantToGeneration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/hooks/variants/usePromoteVariantToGeneration')>();
  return {
    ...actual,
    usePromoteVariantToGeneration: () => ({
      mutateAsync: mocks.promoteVariant,
      isPending: false,
    }),
  };
});

vi.mock('@/shared/hooks/shots', () => ({
  useAddImageToShot: () => ({
    mutateAsync: mocks.addImageToShot,
  }),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: (...args: unknown[]) => mocks.supabaseFrom(...args),
  }),
}));

import { VARIANT_PROMOTION_UNSUPPORTED_CODE } from '@/shared/hooks/variants/usePromoteVariantToGeneration';
import { useVariantPromotion } from './useVariantPromotion';

describe('useVariantPromotion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not query shot rows or add to a shot when variant promotion is unsupported', async () => {
    mocks.promoteVariant.mockRejectedValue({
      code: VARIANT_PROMOTION_UNSUPPORTED_CODE,
      message: 'variant promotion disabled',
    });

    const { result } = renderHook(() => useVariantPromotion({ selectedProjectId: 'project-1' }));

    let added = true;
    await act(async () => {
      added = await result.current.handleAddVariantAsNewGenerationToShot('shot-1', 'variant-1', 10);
    });

    expect(added).toBe(false);
    expect(mocks.supabaseFrom).not.toHaveBeenCalled();
    expect(mocks.addImageToShot).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith('variant promotion disabled');
  });
});
