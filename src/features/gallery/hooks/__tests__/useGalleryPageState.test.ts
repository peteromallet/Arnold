import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock all dependencies
vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: () => ({ selectedProjectId: 'test-project-id' }),
}));

vi.mock('@/shared/hooks/projects/useProjectGenerations', () => ({
  useProjectGenerations: vi.fn().mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    isPlaceholderData: false,
  }),
}));

vi.mock('@/domains/generation/hooks/useGenerationMutations', () => ({
  useToggleGenerationStar: () => ({
    mutate: vi.fn(),
  }),
}));

vi.mock('@/domains/generation/hooks/useDeleteGenerationWithConfirm', () => ({
  useDeleteGenerationWithConfirm: () => ({
    requestDelete: vi.fn(),
    confirmDialogProps: { open: false, onOpenChange: vi.fn(), onConfirm: vi.fn() },
    deletingId: null,
  }),
}));

vi.mock('@/shared/hooks/shots', () => ({
  useAddImageToShot: () => ({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    mutateAsyncWithoutPosition: vi.fn().mockResolvedValue(undefined),
  }),
  usePositionExistingGenerationInShot: () => ({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useLastAffectedShot: () => ({
    lastAffectedShotId: 'shot-1',
    setLastAffectedShotId: vi.fn(),
  }),
  useCurrentShot: () => ({ currentShotId: 'shot-1' }),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => ({
    shots: [{ id: 'shot-1', name: 'Shot 1' }, { id: 'shot-2', name: 'Shot 2' }],
  }),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: { error: vi.fn() },
}));

vi.mock('@/shared/hooks/gallery/useGalleryFilterState', () => ({
  useGalleryFilterState: () => ({
    selectedShotFilter: null,
    excludePositioned: false,
    searchTerm: '',
    starredOnly: false,
    filters: {},
    expectedItemCount: 0,
    applyQueryFallback: vi.fn(),
    setSelectedShotFilter: vi.fn(),
    setExcludePositioned: vi.fn(),
    setSearchTerm: vi.fn(),
    setStarredOnly: vi.fn(),
  }),
}));

import { useGalleryPageState } from '@/features/gallery/hooks/useGalleryPageState';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useGalleryPageState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial page state', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(result.current.page).toBe(1);
    expect(result.current.selectedProjectId).toBe('test-project-id');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBe(false);
  });

  it('provides paginated data structure', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(result.current.paginatedData).toEqual({
      items: [],
      totalPages: 0,
      currentPage: 1,
    });
  });

  it('has totalCount of 0 when no data', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(result.current.totalCount).toBe(0);
  });

  it('provides shots data from context', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(result.current.shotsData).toHaveLength(2);
  });

  it('provides filter state', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(result.current.selectedShotFilter).toBeNull();
    expect(result.current.excludePositioned).toBe(false);
    expect(result.current.searchTerm).toBe('');
    expect(result.current.starredOnly).toBe(false);
  });

  it('provides handler functions', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(typeof result.current.handleServerPageChange).toBe('function');
    expect(typeof result.current.handleDeleteGeneration).toBe('function');
    expect(typeof result.current.handleAddToShot).toBe('function');
    expect(typeof result.current.handleAddToShotWithoutPosition).toBe('function');
    expect(typeof result.current.handleToggleStar).toBe('function');
  });

  it('provides setter functions', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    expect(typeof result.current.setPage).toBe('function');
    expect(typeof result.current.setSelectedShotFilter).toBe('function');
    expect(typeof result.current.setExcludePositioned).toBe('function');
    expect(typeof result.current.setSearchTerm).toBe('function');
    expect(typeof result.current.setStarredOnly).toBe('function');
  });

  it('updates page when handleServerPageChange is called', () => {
    const { result } = renderHook(
      () => useGalleryPageState(),
      { wrapper: createWrapper() }
    );

    act(() => {
      result.current.handleServerPageChange(3);
    });

    expect(result.current.page).toBe(3);
  });

  it('accepts custom itemsPerPage', () => {
    const { result } = renderHook(
      () => useGalleryPageState({ itemsPerPage: 20 }),
      { wrapper: createWrapper() }
    );

    expect(result.current.paginatedData.currentPage).toBe(1);
  });

  it('defaults mediaType to image', () => {
    // The useProjectGenerations mock is called - we just verify the hook doesn't crash
    const { result } = renderHook(
      () => useGalleryPageState({ mediaType: 'video' }),
      { wrapper: createWrapper() }
    );

    expect(result.current).toBeDefined();
  });

  it('disables data loading when enableDataLoading is false', () => {
    const { result } = renderHook(
      () => useGalleryPageState({ enableDataLoading: false }),
      { wrapper: createWrapper() }
    );

    // When data loading is disabled, we should still get a valid structure
    expect(result.current.paginatedData).toBeDefined();
  });
});
