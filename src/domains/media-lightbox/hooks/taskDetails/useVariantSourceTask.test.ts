// @vitest-environment jsdom

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useGetTask: vi.fn(),
  getSourceTaskIdLegacyCompatible: vi.fn(),
  hasOrchestratorDetails: vi.fn(),
}));

vi.mock('@/shared/hooks/tasks/useTasks', () => ({
  useGetTask: (...args: unknown[]) => mocks.useGetTask(...args),
}));

vi.mock('@/shared/lib/taskIdHelpers', () => ({
  getSourceTaskIdLegacyCompatible: (...args: unknown[]) =>
    mocks.getSourceTaskIdLegacyCompatible(...args),
  hasOrchestratorDetails: (...args: unknown[]) => mocks.hasOrchestratorDetails(...args),
}));

import { useVariantSourceTask } from './useVariantSourceTask';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useVariantSourceTask', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getSourceTaskIdLegacyCompatible.mockImplementation(
      (params: Record<string, unknown> | undefined) =>
        typeof params?.source_task_id === 'string' ? params.source_task_id : undefined,
    );
    mocks.hasOrchestratorDetails.mockImplementation(
      (params: Record<string, unknown> | undefined) => Boolean(params?.orchestrator_details),
    );
    mocks.useGetTask.mockReturnValue({
      data: undefined,
      error: null,
      isLoading: false,
    });
  });

  it('fetches the source task when the active variant references a different task', async () => {
    mocks.useGetTask.mockReturnValueOnce({
      data: {
        id: 'source-task',
        params: { input_image: 'from-source-task.png' },
      },
      error: null,
      isLoading: false,
    });

    const { result } = renderHook(
      () =>
        useVariantSourceTask({
          projectId: 'project-1',
          activeVariant: { params: { source_task_id: 'source-task' } },
          taskDetailsData: { taskId: 'other-task' } as never,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.variantSourceTask).toEqual({
        id: 'source-task',
        params: { input_image: 'from-source-task.png' },
      });
    });

    expect(result.current.variantSourceTaskId).toBe('source-task');
    expect(result.current.variantHasOrchestratorDetails).toBe(false);
    expect(mocks.useGetTask).toHaveBeenCalledWith('source-task', 'project-1');
  });

  it('normalizes non-Error query failures into Error instances', async () => {
    mocks.useGetTask.mockReturnValueOnce({
      data: undefined,
      error: { message: 'fetch failed' },
      isLoading: false,
    });

    const { result } = renderHook(
      () =>
        useVariantSourceTask({
          projectId: 'project-1',
          activeVariant: { params: { source_task_id: 'source-task' } },
          taskDetailsData: undefined,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.variantSourceTaskError?.message).toBe('Failed to fetch source task');
    });
  });

  it('skips fetching when orchestrator details already exist on the variant', () => {
    const { result } = renderHook(
      () =>
        useVariantSourceTask({
          projectId: 'project-1',
          activeVariant: {
            params: {
              source_task_id: 'source-task',
              orchestrator_details: { step: 'already-present' },
            },
          },
          taskDetailsData: { taskId: 'other-task' } as never,
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.variantSourceTaskId).toBe('source-task');
    expect(result.current.variantHasOrchestratorDetails).toBe(true);
    expect(mocks.useGetTask).toHaveBeenCalledWith('', 'project-1');
  });
});
