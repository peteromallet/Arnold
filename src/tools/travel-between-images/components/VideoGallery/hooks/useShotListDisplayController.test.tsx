// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { shotQueryKeys } from '@/shared/lib/queryKeys/shots';
import type { Shot } from '@/domains/generation/types';

const mocks = vi.hoisted(() => ({
  useSensor: vi.fn((sensor: unknown, options?: unknown) => ({ sensor, options })),
  useSensors: vi.fn((...sensors: unknown[]) => sensors),
  arrayMove: vi.fn((items: Shot[], from: number, to: number) => {
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    return next;
  }),
  useReorderShots: vi.fn(),
  useShots: vi.fn(),
  useProjectSelectionContext: vi.fn(),
  useProjectCrudContext: vi.fn(),
  useQueryClient: vi.fn(),
  toastError: vi.fn(),
  usePendingNewShotDrop: vi.fn(),
}));

vi.mock('@dnd-kit/core', () => ({
  KeyboardSensor: 'KeyboardSensor',
  MouseSensor: 'MouseSensor',
  TouchSensor: 'TouchSensor',
  useSensor: (...args: unknown[]) => mocks.useSensor(...args),
  useSensors: (...args: unknown[]) => mocks.useSensors(...args),
}));

vi.mock('@dnd-kit/sortable', () => ({
  arrayMove: (...args: unknown[]) => mocks.arrayMove(...args),
  sortableKeyboardCoordinates: vi.fn(),
}));

vi.mock('@/shared/hooks/shots', () => ({
  useReorderShots: mocks.useReorderShots,
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: mocks.useShots,
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: mocks.useProjectSelectionContext,
  useProjectCrudContext: mocks.useProjectCrudContext,
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: mocks.useQueryClient,
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: mocks.toastError,
  },
}));

vi.mock('./usePendingNewShotDrop', () => ({
  usePendingNewShotDrop: mocks.usePendingNewShotDrop,
}));

import { useShotListDisplayController } from './useShotListDisplayController';

describe('useShotListDisplayController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useShots.mockReturnValue({ isLoading: false, error: null });
    mocks.useProjectSelectionContext.mockReturnValue({
      selectedProjectId: 'project-1',
    });
    mocks.useProjectCrudContext.mockReturnValue({
      projects: [{ id: 'project-1', name: 'Project One' }],
    });
    mocks.useReorderShots.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });
    mocks.useQueryClient.mockReturnValue({
      setQueryData: vi.fn(),
      setQueriesData: vi.fn(),
    });
    mocks.usePendingNewShotDrop.mockReturnValue({ kind: 'pending-new-shot' });
  });

  function createShots(): Shot[] {
    return [
      { id: 'shot-1', position: 1, created_at: '2026-03-10T00:00:00.000Z' },
      { id: 'shot-2', position: 2, created_at: '2026-03-11T00:00:00.000Z' },
    ] as Shot[];
  }

  it('sorts shots, exposes project state, and disables dragging while an input is focused', () => {
    const shots = createShots();
    const { result } = renderHook(() => useShotListDisplayController({
      projectId: '',
      shots,
      sortMode: 'newest',
      onGenerationDropForNewShot: vi.fn(),
      onFilesDropForNewShot: vi.fn(),
      onSkeletonSetupReady: vi.fn(),
    }));

    expect(result.current.effectiveProjectId).toBe('project-1');
    expect(result.current.currentProject).toEqual({ id: 'project-1', name: 'Project One' });
    expect(result.current.shots?.map((shot) => shot.id)).toEqual(['shot-2', 'shot-1']);
    expect(result.current.pendingNewShot).toEqual({ kind: 'pending-new-shot' });
    expect(result.current.sortableItems).toEqual(['shot-2', 'shot-1']);

    const input = document.createElement('input');
    document.body.appendChild(input);
    act(() => {
      input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });

    expect(result.current.handleDragStart()).toBe(false);

    act(() => {
      input.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    });
    expect(result.current.handleDragStart()).toBeUndefined();

    input.remove();
  });

  it('reorders shots optimistically and restores cached data when the mutation errors', () => {
    const mutate = vi.fn();
    const queryClient = {
      setQueryData: vi.fn(),
      setQueriesData: vi.fn(),
    };
    mocks.useReorderShots.mockReturnValueOnce({
      isPending: false,
      mutate,
    });
    mocks.useQueryClient.mockReturnValueOnce(queryClient);

    const shots = createShots();
    const { result } = renderHook(() => useShotListDisplayController({
      projectId: 'project-1',
      shots,
      sortMode: 'ordered',
      onGenerationDropForNewShot: vi.fn(),
      onFilesDropForNewShot: vi.fn(),
      onSkeletonSetupReady: vi.fn(),
    }));

    act(() => {
      result.current.handleDragEnd({
        active: { id: 'shot-1' },
        over: { id: 'shot-2' },
      } as never);
    });

    expect(queryClient.setQueryData).toHaveBeenCalledWith(
      shotQueryKeys.list('project-1', 0),
      [
        expect.objectContaining({ id: 'shot-2', position: 1 }),
        expect.objectContaining({ id: 'shot-1', position: 2 }),
      ],
    );
    expect(mutate).toHaveBeenCalledWith(
      {
        projectId: 'project-1',
        shotOrders: [
          { shotId: 'shot-2', position: 1 },
          { shotId: 'shot-1', position: 2 },
        ],
      },
      expect.objectContaining({
        onError: expect.any(Function),
      }),
    );

    const onError = mutate.mock.calls[0][1].onError as (error: Error) => void;
    act(() => {
      onError(new Error('boom'));
    });

    expect(queryClient.setQueriesData).toHaveBeenCalledWith(
      { queryKey: [...shotQueryKeys.all, 'project-1'] },
      shots,
    );
    expect(mocks.toastError).toHaveBeenCalledWith('Failed to reorder shots: boom');
  });
});
