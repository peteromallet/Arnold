import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock store selectors
vi.mock('@/shared/state/selectionStore', () => ({
  useCurrentShot: vi.fn().mockReturnValue({ currentShotId: null }),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: vi.fn().mockReturnValue({
    shots: [],
    allImagesCount: 10,
    noShotImagesCount: 3,
  }),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: vi.fn().mockReturnValue({
    settings: null,
    update: vi.fn(),
    isLoading: false,
  }),
}));

import { useGalleryFilterState } from '../useGalleryFilterState';
import { SHOT_FILTER } from '@/shared/constants/filterConstants';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useGalleryFilterState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('returns default filter state', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      // Default filter when no currentShotId is 'no-shot'
      expect(result.current.selectedShotFilter).toBe(SHOT_FILTER.NO_SHOT);
      expect(result.current.excludePositioned).toBe(true);
      expect(result.current.searchTerm).toBe('');
      expect(result.current.starredOnly).toBe(false);
    });

    it('returns correct shape', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      expect(result.current).toHaveProperty('selectedShotFilter');
      expect(result.current).toHaveProperty('excludePositioned');
      expect(result.current).toHaveProperty('searchTerm');
      expect(result.current).toHaveProperty('starredOnly');
      expect(result.current).toHaveProperty('setSelectedShotFilter');
      expect(result.current).toHaveProperty('setExcludePositioned');
      expect(result.current).toHaveProperty('setSearchTerm');
      expect(result.current).toHaveProperty('setStarredOnly');
      expect(result.current).toHaveProperty('filters');
      expect(result.current).toHaveProperty('expectedItemCount');
      expect(result.current).toHaveProperty('applyQueryFallback');
    });
  });

  describe('filter setters', () => {
    it('setSearchTerm updates search term', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSearchTerm('landscape');
      });

      expect(result.current.searchTerm).toBe('landscape');
    });

    it('setStarredOnly updates starred filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setStarredOnly(true);
      });

      expect(result.current.starredOnly).toBe(true);
    });

    it('setSelectedShotFilter updates filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      expect(result.current.selectedShotFilter).toBe(SHOT_FILTER.ALL);
    });
  });

  describe('computed filters', () => {
    it('includes mediaType in filters', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'video'
          ),
        { wrapper }
      );

      expect(result.current.filters.mediaType).toBe('video');
    });

    it('includes toolType in filters when provided', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image',
            'edit-images'
          ),
        { wrapper }
      );

      expect(result.current.filters.toolType).toBe('edit-images');
    });

    it('does not include shotId for ALL filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      expect(result.current.filters.shotId).toBeUndefined();
    });

    it('includes shotId for specific shot filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter('shot-uuid-123');
      });

      expect(result.current.filters.shotId).toBe('shot-uuid-123');
    });

    it('includes starredOnly in filters', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setStarredOnly(true);
      });

      expect(result.current.filters.starredOnly).toBe(true);
    });

    it('trims and omits empty search term', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSearchTerm('  ');
      });

      expect(result.current.filters.searchTerm).toBeUndefined();
    });

    it('includes trimmed search term when non-empty', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSearchTerm('  landscape  ');
      });

      expect(result.current.filters.searchTerm).toBe('landscape');
    });

    it('does not include excludePositioned for special filters', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      expect(result.current.filters.excludePositioned).toBeUndefined();
    });
  });

  describe('expectedItemCount', () => {
    it('uses allImagesCount for ALL filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      // allImagesCount is 10, capped at 60
      expect(result.current.expectedItemCount).toBe(10);
    });

    it('uses noShotImagesCount for NO_SHOT filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      // Default is NO_SHOT for null currentShotId
      expect(result.current.expectedItemCount).toBe(3);
    });

    it('caps expected count at 60', async () => {
      const { useShots } = await import('@/shared/contexts/ShotsContext');
      (useShots as unknown).mockReturnValue({
        shots: [],
        allImagesCount: 200,
        noShotImagesCount: 150,
      });

      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      expect(result.current.expectedItemCount).toBe(60);
    });
  });

  describe('video mediaType', () => {
    it('sets excludePositioned to false for video', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'video'
          ),
        { wrapper }
      );

      expect(result.current.excludePositioned).toBe(false);
    });
  });

  describe('applyQueryFallback', () => {
    it('does not fall back when data is still loading', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      // Set to a specific shot filter first
      act(() => {
        result.current.setSelectedShotFilter('shot-123');
      });

      act(() => {
        result.current.applyQueryFallback(
          { isLoading: true, isFetching: true, total: undefined, hasResponse: false },
          1
        );
      });

      // Should not have changed
      expect(result.current.selectedShotFilter).toBe('shot-123');
    });

    it('does not fall back for ALL filter', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter(SHOT_FILTER.ALL);
      });

      act(() => {
        result.current.applyQueryFallback(
          { isLoading: false, isFetching: false, total: 0, hasResponse: true },
          1
        );
      });

      expect(result.current.selectedShotFilter).toBe(SHOT_FILTER.ALL);
    });

    it('does not fall back for page > 1', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () =>
          useGalleryFilterState(
            { shouldLoadData: true },
            'image'
          ),
        { wrapper }
      );

      act(() => {
        result.current.setSelectedShotFilter('shot-123');
      });

      act(() => {
        result.current.applyQueryFallback(
          { isLoading: false, isFetching: false, total: 0, hasResponse: true },
          2
        );
      });

      // Should not have changed since page > 1
      expect(result.current.selectedShotFilter).toBe('shot-123');
    });
  });
});
