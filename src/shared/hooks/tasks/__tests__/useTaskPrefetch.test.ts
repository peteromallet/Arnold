import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { renderHookWithProviders } from '@/test/test-utils';
import { setProjectSelectionSnapshot, resetProjectSelectionStoreForTests } from '@/shared/contexts/projectSelectionStore';

const mockResolveGenerationTaskMapping = vi.fn();
const mockMaybeSingle = vi.fn();
const mockSingle = vi.fn();
const mockFetchAndSeedTaskQuery = vi.fn();
const mockGetCachedTaskSnapshot = vi.fn();
const mockPrefetchGenerationTaskMapping = vi.fn();

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: vi.fn(() => ({
    from: vi.fn((_table: string) => ({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({
          maybeSingle: mockMaybeSingle,
          single: mockSingle,
        })),
      })),
    })),
  })),
}));

vi.mock('../useTasks', () => ({
  mapDbTaskToTask: vi.fn((data: unknown) => ({ ...data as object, _mapped: true })),
  fetchAndSeedTaskQuery: (...args: unknown[]) => mockFetchAndSeedTaskQuery(...args),
  getCachedTaskSnapshot: (...args: unknown[]) => mockGetCachedTaskSnapshot(...args),
}));

vi.mock('@/shared/lib/tasks/generationTaskRepository', () => ({
  resolveGenerationTaskMapping: (...args: unknown[]) => mockResolveGenerationTaskMapping(...args),
  toGenerationTaskMappingCacheEntry: (
    mapping: { taskId?: string | null; status?: string; queryError?: string } | undefined,
  ) => ({
    taskId: mapping?.taskId ?? null,
    status: mapping?.status ?? 'not_loaded',
    ...(mapping?.queryError ? { queryError: mapping.queryError } : {}),
  }),
}));

vi.mock('@/domains/generation/hooks/tasks/useGenerationTaskMapping', async () => {
  const actual = await vi.importActual<typeof import('@/domains/generation/hooks/tasks/useGenerationTaskMapping')>(
    '@/domains/generation/hooks/tasks/useGenerationTaskMapping'
  );

  return {
    ...actual,
    prefetchGenerationTaskMapping: (...args: unknown[]) => mockPrefetchGenerationTaskMapping(...args),
  };
});

import { useGenerationTaskMapping } from '@/domains/generation/hooks/tasks/useGenerationTaskMapping';
import { usePrefetchTaskData, usePrefetchTaskById } from '../useTaskPrefetch';

const GENERATION_ID = '11111111-1111-4111-8111-111111111111';
const MISSING_GENERATION_ID = '22222222-2222-4222-8222-222222222222';
const PROJECT_ID = '44444444-4444-4444-8444-444444444444';

describe('useGenerationTaskMapping', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResolveGenerationTaskMapping.mockResolvedValue({
      generationId: GENERATION_ID,
      taskId: 'task-1',
      status: 'ok',
    });
  });

  it('is disabled when generationId is empty', () => {
    const { result } = renderHookWithProviders(() => useGenerationTaskMapping(''));
    expect(result.current.isFetching).toBe(false);
  });

  it('returns taskId from generation data', async () => {
    const { result } = renderHookWithProviders(() => useGenerationTaskMapping(GENERATION_ID));

    await waitFor(() => {
      expect(result.current.data).toEqual({ taskId: 'task-1', status: 'ok' });
    });
  });

  it('returns null taskId when generation has no tasks', async () => {
    mockResolveGenerationTaskMapping.mockResolvedValue({
      generationId: GENERATION_ID,
      taskId: null,
      status: 'ok',
    });

    const { result } = renderHookWithProviders(() => useGenerationTaskMapping(GENERATION_ID));

    await waitFor(() => {
      expect(result.current.data).toEqual({ taskId: null, status: 'ok' });
    });
  });

  it('returns null taskId when generation not found', async () => {
    mockResolveGenerationTaskMapping.mockResolvedValue({
      generationId: MISSING_GENERATION_ID,
      taskId: null,
      status: 'missing_generation',
    });

    const { result } = renderHookWithProviders(() => useGenerationTaskMapping(MISSING_GENERATION_ID));

    await waitFor(() => {
      expect(result.current.data).toEqual({ taskId: null, status: 'missing_generation' });
    });
  });

  it('does not query for non-UUID optimistic generation IDs', () => {
    renderHookWithProviders(() => useGenerationTaskMapping('temp-upload-123'));
    expect(mockMaybeSingle).not.toHaveBeenCalled();
  });
});

describe('usePrefetchTaskData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetProjectSelectionStoreForTests();
    mockMaybeSingle.mockResolvedValue({ data: { tasks: ['task-1'] }, error: null });
    mockSingle.mockResolvedValue({ data: { id: 'task-1', status: 'Completed' }, error: null });
    mockGetCachedTaskSnapshot.mockReturnValue(undefined);
    mockFetchAndSeedTaskQuery.mockResolvedValue({ id: 'task-1' });
    mockPrefetchGenerationTaskMapping.mockResolvedValue({ taskId: 'task-1' });
  });

  it('returns a prefetch function', () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskData());
    expect(typeof result.current).toBe('function');
  });

  it('does nothing for empty generationId', async () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskData());

    await act(async () => {
      await result.current('', PROJECT_ID);
    });

    expect(mockMaybeSingle).not.toHaveBeenCalled();
  });

  it('does nothing for non-UUID generationId', async () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskData());

    await act(async () => {
      await result.current('temp-upload-123', PROJECT_ID);
    });

    expect(mockMaybeSingle).not.toHaveBeenCalled();
  });

  it('uses the fallback project scope and seeds the single-task cache when the mapping resolves', async () => {
    setProjectSelectionSnapshot({ selectedProjectId: 'fallback-project' });

    const { result } = renderHookWithProviders(() => usePrefetchTaskData());

    await act(async () => {
      await result.current(GENERATION_ID, null);
    });

    expect(mockPrefetchGenerationTaskMapping).toHaveBeenCalled();
    expect(mockFetchAndSeedTaskQuery).toHaveBeenCalledWith(
      expect.anything(),
      'task-1',
      'fallback-project',
    );
  });
});

describe('usePrefetchTaskById', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetProjectSelectionStoreForTests();
    mockSingle.mockResolvedValue({ data: { id: 'task-1', status: 'Completed' }, error: null });
    mockGetCachedTaskSnapshot.mockReturnValue(undefined);
    mockFetchAndSeedTaskQuery.mockResolvedValue({ id: 'task-1' });
  });

  it('returns a prefetch function', () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskById());
    expect(typeof result.current).toBe('function');
  });

  it('does nothing for empty taskId', async () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskById());

    await act(async () => {
      await result.current('', PROJECT_ID);
    });

    expect(mockSingle).not.toHaveBeenCalled();
  });

  it('does nothing for non-UUID taskId', async () => {
    const { result } = renderHookWithProviders(() => usePrefetchTaskById());

    await act(async () => {
      await result.current('task-not-uuid', PROJECT_ID);
    });

    expect(mockSingle).not.toHaveBeenCalled();
  });

  it('uses the fallback project scope when prefetching a task directly', async () => {
    setProjectSelectionSnapshot({ selectedProjectId: 'fallback-project' });

    const { result } = renderHookWithProviders(() => usePrefetchTaskById());

    await act(async () => {
      await result.current('11111111-1111-4111-8111-111111111112', null);
    });

    expect(mockFetchAndSeedTaskQuery).toHaveBeenCalledWith(
      expect.anything(),
      '11111111-1111-4111-8111-111111111112',
      'fallback-project',
    );
  });
});
