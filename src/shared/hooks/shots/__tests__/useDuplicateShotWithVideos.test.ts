import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { queryKeys } from '@/shared/lib/queryKeys';
import { useDuplicateShotWithVideos } from '../useDuplicateShotWithVideos';

const mockFrom = vi.fn();
const mockRpc = vi.fn();

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: (...args: unknown[]) => mockFrom(...args),
    rpc: (...args: unknown[]) => mockRpc(...args),
  }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return {
    queryClient,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children),
  };
}

describe('useDuplicateShotWithVideos', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls duplicate_shot_with_videos, fetches the cloned shot, and avoids duplicate_shot', async () => {
    const clonedShot = {
      id: 'shot-clone',
      name: 'Shot Alpha (copy)',
      project_id: 'project-1',
      position: 2,
    };

    mockRpc.mockResolvedValue({
      data: { shot_id: 'shot-clone', generation_id_map: {}, shot_generation_id_map: {} },
      error: null,
    });
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          single: vi.fn().mockResolvedValue({
            data: clonedShot,
            error: null,
          }),
        }),
      }),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useDuplicateShotWithVideos(), { wrapper });

    await expect(
      act(async () => {
        return await result.current.mutateAsync({
          shotId: 'shot-source',
          projectId: 'project-1',
        });
      }),
    ).resolves.toEqual(clonedShot);

    expect(mockRpc).toHaveBeenCalledTimes(1);
    expect(mockRpc).toHaveBeenCalledWith('duplicate_shot_with_videos', {
      original_shot_id: 'shot-source',
      project_id: 'project-1',
    });
    expect(mockRpc).not.toHaveBeenCalledWith('duplicate_shot', expect.anything());
    expect(mockFrom).toHaveBeenCalledWith('shots');
  });

  it('invalidates shot, final-video, generation, segment, and project/unified caches', async () => {
    const clonedShot = {
      id: 'shot-clone',
      name: 'Shot Alpha (copy)',
      project_id: 'project-1',
      position: 2,
    };

    mockRpc.mockResolvedValue({
      data: { shot_id: 'shot-clone' },
      error: null,
    });
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          single: vi.fn().mockResolvedValue({
            data: clonedShot,
            error: null,
          }),
        }),
      }),
    });

    const { wrapper, queryClient } = createWrapper();
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useDuplicateShotWithVideos(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        shotId: 'shot-source',
        projectId: 'project-1',
      });
    });

    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [...queryKeys.shots.all, 'project-1'],
    });
    for (const shotId of ['shot-source', 'shot-clone']) {
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.shots.detail(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.byShot(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.meta(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.unpositionedCount(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.lastVideo(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.segments.liveTimeline(shotId) });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.segments.parents(shotId, 'project-1') });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.segments.parents(shotId) });
    }
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.finalVideos.byProject('project-1') });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.byProject('project-1') });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.variantsAll });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.derivedAll });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.generations.derivedGenerationsAll });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.unified.projectPrefix('project-1') });

    const predicateCalls = invalidateQueries.mock.calls
      .map(([call]) => call)
      .filter((call): call is { predicate: (query: { queryKey: readonly unknown[] }) => boolean } => (
        Boolean(call && typeof call === 'object' && 'predicate' in call)
      ));

    expect(predicateCalls).toHaveLength(2);
    expect(predicateCalls.some(({ predicate }) => predicate({ queryKey: queryKeys.segments.children('segment-1') }))).toBe(true);
    expect(predicateCalls.some(({ predicate }) => predicate({ queryKey: queryKeys.segments.sourceSlot('slot-1') }))).toBe(true);
  });
});
