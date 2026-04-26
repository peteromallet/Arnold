import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { renderHookWithProviders } from '@/test/test-utils';
import { resetProjectSelectionStoreForTests } from '@/shared/contexts/projectSelectionStore';
import {
  __resetRealtimeTaskStoreForTests,
  getRealtimeTaskSnapshot,
  upsertRealtimeTaskSnapshot,
} from '@/shared/state/realtimeStore';

const mockSelect = vi.fn();
vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({
          in: vi.fn(() => mockSelect()),
        })),
      })),
    })),
  }),
}));

vi.mock('@/types/tasks', () => ({
  TASK_STATUS: { QUEUED: 'Queued', IN_PROGRESS: 'In Progress' },
}));

import { usePendingGenerationTasks } from '@/shared/hooks/tasks/usePendingGenerationTasks';

describe('usePendingGenerationTasks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetRealtimeTaskStoreForTests();
    resetProjectSelectionStoreForTests();
  });

  it('returns empty when generationId is null', () => {
    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks(null, 'proj-1')
    );
    expect(result.current.pendingCount).toBe(0);
    expect(result.current.pendingTasks).toEqual([]);
  });

  it('returns empty when projectId is null', () => {
    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks('gen-1', null)
    );
    expect(result.current.pendingCount).toBe(0);
  });

  it('bootstraps current-project pending rows into the realtime store and derives generation-specific results from the selector', async () => {
    mockSelect.mockResolvedValue({
      data: [
        {
          id: 't1',
          status: 'Queued',
          task_type: 'video_generation',
          params: { based_on: 'gen-1' },
          created_at: '2026-04-17T00:00:00.000Z',
          project_id: 'proj-1',
          updated_at: null,
        },
        {
          id: 't2',
          status: 'In Progress',
          task_type: 'video_generation',
          params: { based_on: 'gen-other' },
          created_at: '2026-04-17T00:00:01.000Z',
          project_id: 'proj-1',
          updated_at: null,
        },
      ],
      error: null,
    });

    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks('gen-1', 'proj-1')
    );

    await waitFor(() => {
      expect(result.current.pendingCount).toBe(1);
    });
    expect(result.current.pendingTasks[0].id).toBe('t1');
    expect(getRealtimeTaskSnapshot('t1', 'proj-1')).toMatchObject({
      id: 't1',
      taskType: 'video_generation',
      projectId: 'proj-1',
    });
  });

  it('handles query errors gracefully', async () => {
    mockSelect.mockResolvedValue({
      data: null,
      error: { message: 'Query failed' },
    });

    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks('gen-1', 'proj-1')
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.pendingCount).toBe(0);
  });

  it('detects generation references in nested params', async () => {
    mockSelect.mockResolvedValue({
      data: [
        {
          id: 't1',
          status: 'Queued',
          task_type: 'travel_segment',
          params: {
            orchestrator_details: {
              pair_shot_generation_ids: ['gen-1', 'gen-2'],
            },
          },
          created_at: '2026-04-17T00:00:00.000Z',
          project_id: 'proj-1',
          updated_at: null,
        },
      ],
      error: null,
    });

    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks('gen-1', 'proj-1')
    );

    await waitFor(() => {
      expect(result.current.pendingCount).toBe(1);
    });
  });

  it('reflects realtime-store updates for the same generation after the bootstrap query seeds the project scope', async () => {
    mockSelect.mockResolvedValue({
      data: [
        {
          id: 't1',
          status: 'Queued',
          task_type: 'video_generation',
          params: { based_on: 'gen-1' },
          created_at: '2026-04-17T00:00:00.000Z',
          project_id: 'proj-1',
          updated_at: null,
        },
      ],
      error: null,
    });

    const { result } = renderHookWithProviders(() =>
      usePendingGenerationTasks('gen-1', 'proj-1')
    );

    await waitFor(() => {
      expect(result.current.pendingCount).toBe(1);
    });

    act(() => {
      upsertRealtimeTaskSnapshot({
        id: 't2',
        taskType: 'travel_segment',
        params: { orchestrator_details: { pair_shot_generation_ids: ['gen-1'] } },
        status: 'In Progress',
        createdAt: '2026-04-17T00:00:02.000Z',
        projectId: 'proj-1',
      });
    });

    await waitFor(() => {
      expect(result.current.pendingCount).toBe(2);
    });
    expect(result.current.pendingTasks.map((task) => task.id)).toEqual(['t1', 't2']);
  });
});
