import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({
          order: vi.fn(() => ({
            order: vi.fn(() => ({
              range: vi.fn(() => Promise.resolve({ data: [], error: null })),
            })),
          })),
        })),
      })),
    })),
  }),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: vi.fn(() => ({ shots: [] })),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: vi.fn(() => ({ selectedProjectId: 'proj-1' })),
  useProjectSelectionContext: vi.fn(() => ({ selectedProjectId: 'proj-1', project: null, setSelectedProjectId: vi.fn() })),
  useProjectCrudContext: vi.fn(() => ({
    projects: [],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  })),
  useProjectIdentityContext: vi.fn(() => ({ userId: null })),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: vi.fn(() => ({
    settings: { sortOrder: 'newest' },
    update: vi.fn(),
    isLoading: false,
  })),
}));

vi.mock('@/shared/hooks/projects/useProjectVideoCountsCache', () => ({
  useProjectVideoCountsCache: vi.fn(() => ({
    getShotVideoCount: vi.fn(() => 6),
  })),
}));

vi.mock('@/shared/lib/preloading', () => ({
  preloadingService: {
    preloadImages: vi.fn(),
    clearQueue: vi.fn(),
  },
  hasLoadedImage: vi.fn(() => false),
  PRIORITY: { low: 3 },
}));

import { useVideoGalleryPreloader } from '../useVideoGalleryPreloader';

describe('useVideoGalleryPreloader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns expected shape', () => {
    const { result } = renderHook(() => useVideoGalleryPreloader());

    expect(typeof result.current.preloadedProjectUrls).toBe('number');
    expect(typeof result.current.targetCacheSize).toBe('number');
    expect(typeof result.current.cacheUtilization).toBe('number');
  });

  it('returns zero preloaded URLs initially', () => {
    const { result } = renderHook(() => useVideoGalleryPreloader());

    expect(result.current.preloadedProjectUrls).toBe(0);
    expect(result.current.cacheUtilization).toBe(0);
  });

  it('has a positive target cache size', () => {
    const { result } = renderHook(() => useVideoGalleryPreloader());

    expect(result.current.targetCacheSize).toBeGreaterThan(0);
  });

  it('handles null selectedShot', () => {
    const { result } = renderHook(() =>
      useVideoGalleryPreloader({ selectedShot: null })
    );

    expect(result.current.preloadedProjectUrls).toBe(0);
  });

  it('handles shouldShowShotEditor false', () => {
    const { result } = renderHook(() =>
      useVideoGalleryPreloader({
        shouldShowShotEditor: false,
        selectedShot: {
          id: 'shot-1',
          name: 'Shot 1',
          images: [],
          position: 0,
          created_at: '2025-01-01',
          project_id: 'proj-1',
        },
      })
    );

    expect(result.current.preloadedProjectUrls).toBe(0);
  });
});
