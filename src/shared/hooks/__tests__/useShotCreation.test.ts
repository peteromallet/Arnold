import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock contexts and hooks
vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: vi.fn(() => ({ selectedProjectId: 'test-project-id' })),
  useProjectSelectionContext: vi.fn(() => ({ selectedProjectId: 'test-project-id', project: null, setSelectedProjectId: vi.fn() })),
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

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: vi.fn(() => ({
    shots: [
      { id: 'shot-1', name: 'Shot 1', images: [] },
      { id: 'shot-2', name: 'Shot 2', images: [] },
    ],
  })),
}));

vi.mock('@/shared/hooks/shots/useLastAffectedShot', () => ({
  useLastAffectedShot: vi.fn(() => ({
    setLastAffectedShotId: vi.fn(),
  })),
}));

const mockMutateAsync = vi.fn();
const mockCreateShotWithGenerationsMutateAsync = vi.fn();

vi.mock('@/shared/hooks/shots', () => ({
  useCreateShot: vi.fn(() => ({
    mutateAsync: mockMutateAsync.mockResolvedValue({
      shot: { id: 'new-shot', name: 'Shot 3' },
    }),
  })),
  useCreateShotWithGenerations: vi.fn(() => ({
    mutateAsync: mockCreateShotWithGenerationsMutateAsync.mockResolvedValue({
      shot_id: 'new-shot-with-generations',
      shot_name: 'Shot 3',
      shot_position: 2,
      shot_generations: [],
      success: true,
    }),
  })),
  useHandleExternalImageDrop: vi.fn(() => ({
    mutateAsync: vi.fn().mockResolvedValue({
      shotId: 'new-shot-with-files',
      generationIds: ['gen-1', 'gen-2'],
    }),
  })),
}));

vi.mock('@/shared/lib/shotSettingsInheritance', () => ({
  inheritSettingsForNewShot: vi.fn(),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

vi.mock('@/shared/lib/queryKeys', () => ({
  queryKeys: {
    shots: {
      list: (projectId: string, limit: number) => ['shots', projectId, limit],
      all: ['shots'],
      detail: (shotId: string) => ['shots', shotId],
    },
  },
}));

import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useShotCreation', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock window.dispatchEvent for skeleton events
    vi.spyOn(window, 'dispatchEvent').mockImplementation(() => true);
  });

  it('returns initial state', () => {
    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isCreating).toBe(false);
    expect(result.current.lastCreatedShot).toBeNull();
    expect(typeof result.current.createShot).toBe('function');
    expect(typeof result.current.clearLastCreated).toBe('function');
  });

  it('creates empty shot with auto-generated name', async () => {
    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    let shotResult: Awaited<ReturnType<typeof result.current.createShot>> = null;

    await act(async () => {
      shotResult = await result.current.createShot();
    });

    expect(shotResult).not.toBeNull();
    expect(shotResult?.shotId).toBe('new-shot');
  });

  it('creates shot with custom name', async () => {
    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.createShot({ name: 'Custom Shot' });
    });

    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Custom Shot' })
    );
  });

  it('clearLastCreated resets state', async () => {
    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    // Create a shot first
    await act(async () => {
      await result.current.createShot();
    });

    expect(result.current.lastCreatedShot).not.toBeNull();

    // Clear it
    act(() => {
      result.current.clearLastCreated();
    });

    expect(result.current.lastCreatedShot).toBeNull();
  });

  it('dispatches skeleton event when creating with generation', async () => {
    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.createShot({ generationId: 'gen-1' });
    });

    expect(window.dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'shot-pending-create',
      })
    );
  });

  it('calls onSuccess callback after creation', async () => {
    const onSuccess = vi.fn();

    const { result } = renderHook(() => useShotCreation(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.createShot({ onSuccess });
    });

    expect(onSuccess).toHaveBeenCalledWith(
      expect.objectContaining({ shotId: 'new-shot' })
    );
  });
});
