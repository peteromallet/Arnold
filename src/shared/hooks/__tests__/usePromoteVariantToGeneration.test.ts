import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import { renderHookWithProviders } from '@/test/test-utils';

const mockVariantSingle = vi.fn();
const mockInsertSingle = vi.fn();

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: vi.fn((table: string) => {
      if (table === 'generation_variants') {
        return {
          select: vi.fn(() => ({
            eq: vi.fn(() => ({
              single: () => mockVariantSingle(),
            })),
          })),
        };
      }
      return {
        insert: vi.fn(() => ({
          select: vi.fn(() => ({
            single: () => mockInsertSingle(),
          })),
        })),
      };
    }),
  }),
}));

vi.mock('@/shared/lib/typeGuards', () => ({
  hasVideoExtension: vi.fn((url: string) => url?.endsWith('.mp4')),
}));

import { usePromoteVariantToGeneration } from '@/shared/hooks/variants/usePromoteVariantToGeneration';

describe('usePromoteVariantToGeneration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns mutation object', () => {
    const { result } = renderHookWithProviders(() => usePromoteVariantToGeneration());
    expect(typeof result.current.mutateAsync).toBe('function');
    expect(result.current.isPending).toBe(false);
  });

  it('fails closed before fetching variants or inserting generations', async () => {
    const { result } = renderHookWithProviders(() => usePromoteVariantToGeneration());

    await act(async () => {
      await expect(
        result.current.mutateAsync({ variantId: 'v-1', projectId: 'proj-1' })
      ).rejects.toThrow('Creating a standalone generation from a variant is disabled');
    });

    expect(mockVariantSingle).not.toHaveBeenCalled();
    expect(mockInsertSingle).not.toHaveBeenCalled();
  });
});
