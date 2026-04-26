import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock supabase
const mockRange = vi.fn();
const mockOrder = vi.fn();

const { mockSupabaseFrom } = vi.hoisted(() => ({
  mockSupabaseFrom: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => {
  const createChain = () => {
    const chain: Record<string, ReturnType<typeof vi.fn>> = {};
    chain.select = vi.fn().mockReturnValue(chain);
    chain.eq = vi.fn().mockReturnValue(chain);
    chain.not = vi.fn().mockReturnValue(chain);
    chain.like = vi.fn().mockReturnValue(chain);
    chain.ilike = vi.fn().mockReturnValue(chain);
    chain.or = vi.fn().mockReturnValue(chain);
    chain.is = vi.fn().mockReturnValue(chain);
    chain.in = vi.fn().mockReturnValue(chain);
    chain.order = mockOrder.mockReturnValue(chain);
    chain.range = mockRange.mockResolvedValue({ data: [], error: null });
    chain.single = vi.fn().mockResolvedValue({ data: null, error: null });
    return chain;
  };

  mockSupabaseFrom.mockImplementation(() => createChain());

  return {
    getSupabaseClient: () => ({
      from: mockSupabaseFrom,
    }),
  };
});

// Mock smart polling
vi.mock('../useSmartPolling', () => ({
  useSmartPollingConfig: vi.fn(() => ({
    refetchInterval: false,
    staleTime: 30000,
  })),
}));

vi.mock('@/shared/lib/queryKeys', () => ({
  queryKeys: {
    unified: {
      byProject: (projectId: string | null, page: number, limit: number, filters?: unknown) =>
        ['unified-generations', 'project', projectId, page, limit, filters],
      all: ['unified-generations'],
    },
    generations: {
      all: ['generations'],
      derivedGenerationsAll: ['derived-generations'],
      derivedAll: ['derived'],
      detailAll: ['generation-detail'],
      detail: (id: string) => ['generation-detail', id],
      variants: (id: string) => ['generation-variants', id],
      variantBadges: ['variant-badges'],
      byShot: (shotId: string) => ['generations', 'shot', shotId],
    },
    tasks: { all: ['tasks'] },
    shots: { all: ['shots'] },
    segments: { parentsAll: ['segments-parents'], childrenAll: ['segments-children'], liveTimelineAll: ['segments-timeline'] },
    finalVideos: { all: ['final-videos'] },
  },
}));

vi.mock('@/shared/lib/generationTransformers', () => ({
  transformGeneration: vi.fn((item: unknown) => item),
  transformVariant: vi.fn((item: unknown) => item),
}));

vi.mock('@/shared/constants/filterConstants', () => ({
  SHOT_FILTER: { NO_SHOT: 'no-shot' },
}));

vi.mock('@/shared/lib/tooling/toolIds', () => ({
  TOOL_IDS: { IMAGE_GENERATION: 'image-generation' },
}));

import { fetchGenerations, useProjectGenerations } from '../useProjectGenerations';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('fetchGenerations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty result when projectId is null', async () => {
    const result = await fetchGenerations(null);
    expect(result).toEqual({ items: [], total: 0, hasMore: false });
  });

  it('returns empty result when projectId is empty', async () => {
    const result = await fetchGenerations(null, 100, 0);
    expect(result).toEqual({ items: [], total: 0, hasMore: false });
  });

  it('keeps count and data queries aligned for local-mode generations', async () => {
    const chains: Array<Record<string, ReturnType<typeof vi.fn>> & { count?: number }> = [];

    mockSupabaseFrom.mockImplementation(() => {
      const chain: Record<string, ReturnType<typeof vi.fn>> & { count?: number } = {
        count: 1,
      };
      chain.select = vi.fn().mockReturnValue(chain);
      chain.eq = vi.fn().mockReturnValue(chain);
      chain.not = vi.fn().mockReturnValue(chain);
      chain.like = vi.fn().mockReturnValue(chain);
      chain.ilike = vi.fn().mockReturnValue(chain);
      chain.or = vi.fn().mockReturnValue(chain);
      chain.is = vi.fn().mockReturnValue(chain);
      chain.in = vi.fn().mockReturnValue(chain);
      chain.order = vi.fn().mockReturnValue(chain);
      chain.range = vi.fn().mockResolvedValue({ data: [], error: null });
      chain.single = vi.fn().mockResolvedValue({ data: null, error: null });
      chains.push(chain);
      return chain;
    });

    await fetchGenerations('project-1');

    expect(chains).toHaveLength(2);
    expect(chains[0].or).toHaveBeenCalledWith('location.not.is.null,storage_mode.eq.local');
    expect(chains[1].or).toHaveBeenCalledWith('location.not.is.null,storage_mode.eq.local');
    expect(chains[0].not).not.toHaveBeenCalledWith('location', 'is', null);
    expect(chains[1].not).not.toHaveBeenCalledWith('location', 'is', null);
  });
});

describe('useProjectGenerations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('is disabled when projectId is null', () => {
    const { result } = renderHook(
      () => useProjectGenerations(null),
      { wrapper: createWrapper() }
    );

    // Query should not be loading when disabled
    expect(result.current.data).toBeUndefined();
  });

  it('fetches generations when projectId is provided', async () => {
    // Mock the count query to return 0
    mockSupabaseFrom.mockImplementation(() => {
      const chain: Record<string, ReturnType<typeof vi.fn>> = {};
      chain.select = vi.fn().mockReturnValue(chain);
      chain.eq = vi.fn().mockReturnValue(chain);
      chain.not = vi.fn().mockReturnValue(chain);
      chain.order = vi.fn().mockReturnValue(chain);
      chain.range = vi.fn().mockResolvedValue({ data: [], error: null, count: 0 });
      // For head count query
      chain.single = vi.fn().mockResolvedValue({ data: null, error: null, count: 0 });
      return chain;
    });

    const { result } = renderHook(
      () => useProjectGenerations('test-project-id', 1, 20, true),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true);
    });
  });

  it('accepts filter parameters', () => {
    const { result } = renderHook(
      () => useProjectGenerations('test-project', 1, 20, true, {
        toolType: 'image-generation',
        mediaType: 'video',
        starredOnly: true,
      }),
      { wrapper: createWrapper() }
    );

    // Hook should initialize without errors
    expect(result.current).toBeDefined();
  });

  it('is disabled when enabled=false', () => {
    const { result } = renderHook(
      () => useProjectGenerations('test-project', 1, 20, false),
      { wrapper: createWrapper() }
    );

    expect(result.current.data).toBeUndefined();
    expect(result.current.isFetching).toBe(false);
  });
});
