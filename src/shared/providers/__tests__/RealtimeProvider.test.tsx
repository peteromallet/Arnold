/**
 * RealtimeProvider Tests
 *
 * Tests for the realtime connection provider.
 */

// @vitest-environment jsdom

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, act, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RawDatabaseEvent } from '@/shared/realtime/types';

const mockedState = vi.hoisted(() => ({
  statusChangeCallback: null as ((state: Record<string, unknown>) => void) | null,
  rawEventCallback: null as ((event: RawDatabaseEvent) => void) | null,
  mockUseProject: vi.fn(),
  mockFetchAndSeedTaskQuery: vi.fn(),
  mockGetCachedTaskSnapshot: vi.fn(),
  mockUpsertRealtimeTaskSnapshot: vi.fn(),
  mockResetRealtimeTaskScope: vi.fn(),
  mockRealtimeEventProcessor: {
    process: vi.fn(),
    clear: vi.fn(),
  },
  mockDataFreshnessManager: {
    reset: vi.fn(),
  },
}));

const mockRealtimeConnection = {
  connect: vi.fn().mockResolvedValue(true),
  disconnect: vi.fn().mockResolvedValue(undefined),
  reset: vi.fn(),
  getState: vi.fn().mockReturnValue({
    status: 'disconnected',
    projectId: null,
    error: null,
    statusChangedAt: Date.now(),
    reconnectAttempt: 0,
    nextRetryAt: null,
  }),
  onStatusChange: vi.fn().mockImplementation((cb: (state: Record<string, unknown>) => void) => {
    mockedState.statusChangeCallback = cb;
    cb({
      status: 'disconnected',
      projectId: null,
      error: null,
      statusChangedAt: Date.now(),
      reconnectAttempt: 0,
      nextRetryAt: null,
    });
    return () => {
      mockedState.statusChangeCallback = null;
    };
  }),
  onEvent: vi.fn().mockImplementation((cb: (event: RawDatabaseEvent) => void) => {
    mockedState.rawEventCallback = cb;
    return () => {
      mockedState.rawEventCallback = null;
    };
  }),
};

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: () => mockedState.mockUseProject(),
  useProjectSelectionContext: () => {
    const value = mockedState.mockUseProject();
    return {
      selectedProjectId: value.selectedProjectId ?? null,
      project: value.project ?? null,
      setSelectedProjectId: vi.fn(),
    };
  },
  useProjectCrudContext: () => ({
    projects: [],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  }),
  useProjectIdentityContext: () => ({ userId: null }),
}));

vi.mock('@/shared/hooks/tasks/useTasks', () => ({
  fetchAndSeedTaskQuery: (...args: unknown[]) => mockedState.mockFetchAndSeedTaskQuery(...args),
  getCachedTaskSnapshot: (...args: unknown[]) => mockedState.mockGetCachedTaskSnapshot(...args),
}));

vi.mock('@/shared/realtime/RealtimeConnection', () => ({
  getRealtimeConnection: vi.fn(() => mockRealtimeConnection),
}));

vi.mock('@/shared/realtime/RealtimeEventProcessor', () => ({
  realtimeEventProcessor: mockedState.mockRealtimeEventProcessor,
}));

vi.mock('@/shared/realtime/DataFreshnessManager', () => ({
  dataFreshnessManager: mockedState.mockDataFreshnessManager,
}));

vi.mock('@/shared/hooks/useRealtimeInvalidation', () => ({
  useRealtimeInvalidation: vi.fn(),
}));

vi.mock('@/shared/state/realtimeStore', () => ({
  getRealtimeTaskSnapshot: vi.fn(() => null),
  upsertRealtimeTaskSnapshot: (...args: unknown[]) => mockedState.mockUpsertRealtimeTaskSnapshot(...args),
  resetRealtimeTaskScope: (...args: unknown[]) => mockedState.mockResetRealtimeTaskScope(...args),
}));

import { RealtimeProvider, useRealtime } from '../RealtimeProvider';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        {ui}
      </QueryClientProvider>
    ),
  };
}

function RealtimeConsumer() {
  const ctx = useRealtime();
  return (
    <div>
      <span data-testid="status">{ctx.status}</span>
      <span data-testid="isConnected">{String(ctx.isConnected)}</span>
      <span data-testid="isConnecting">{String(ctx.isConnecting)}</span>
      <span data-testid="isFailed">{String(ctx.isFailed)}</span>
      <span data-testid="error">{ctx.error ?? 'null'}</span>
      <button data-testid="reconnect" onClick={ctx.reconnect}>
        Reconnect
      </button>
    </div>
  );
}

describe('RealtimeProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedState.statusChangeCallback = null;
    mockedState.rawEventCallback = null;
    mockedState.mockUseProject.mockReturnValue({ selectedProjectId: 'proj-1' });
    mockedState.mockGetCachedTaskSnapshot.mockReturnValue(undefined);
    mockedState.mockFetchAndSeedTaskQuery.mockResolvedValue(null);
  });

  it('renders children', () => {
    renderWithProviders(
      <RealtimeProvider>
        <div data-testid="child">Hello</div>
      </RealtimeProvider>
    );

    expect(screen.getByTestId('child')).toHaveTextContent('Hello');
  });

  it('provides initial disconnected state', () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    expect(screen.getByTestId('status')).toHaveTextContent('disconnected');
    expect(screen.getByTestId('isConnected')).toHaveTextContent('false');
    expect(screen.getByTestId('isConnecting')).toHaveTextContent('false');
    expect(screen.getByTestId('isFailed')).toHaveTextContent('false');
    expect(screen.getByTestId('error')).toHaveTextContent('null');
  });

  it('connects when project is selected', () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    expect(mockRealtimeConnection.connect).toHaveBeenCalledWith('proj-1');
    expect(mockedState.mockResetRealtimeTaskScope).toHaveBeenCalledWith('proj-1');
  });

  it('subscribes to status changes', () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    expect(mockRealtimeConnection.onStatusChange).toHaveBeenCalled();
  });

  it('hydrates canonical task rows into the scoped realtime store before processing the event', async () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    const event: RawDatabaseEvent = {
      table: 'tasks',
      eventType: 'UPDATE',
      receivedAt: Date.now(),
      new: {
        id: 'task-1',
        task_type: 'image_generation',
        params: { source_generation_id: 'gen-1' },
        status: 'In Progress',
        created_at: '2026-04-17T00:00:00.000Z',
        project_id: 'proj-1',
      },
      old: {
        id: 'task-1',
        project_id: 'proj-1',
        status: 'Queued',
      },
    };

    act(() => {
      mockedState.rawEventCallback?.(event);
    });

    await waitFor(() => {
      expect(mockedState.mockUpsertRealtimeTaskSnapshot).toHaveBeenCalledWith(expect.objectContaining({
        id: 'task-1',
        taskType: 'image_generation',
        projectId: 'proj-1',
        status: 'In Progress',
      }), 'proj-1');
    });
    expect(mockedState.mockRealtimeEventProcessor.process).toHaveBeenCalledWith(event);
    expect(mockedState.mockUpsertRealtimeTaskSnapshot.mock.invocationCallOrder[0]).toBeLessThan(
      mockedState.mockRealtimeEventProcessor.process.mock.invocationCallOrder[0]
    );
  });

  it('falls back to targeted single-task fetch when the raw row is incomplete', async () => {
    const fetchedTask = {
      id: 'task-2',
      taskType: 'video_generation',
      params: { source_generation_id: 'gen-2' },
      status: 'Queued',
      createdAt: '2026-04-17T00:00:00.000Z',
      projectId: 'proj-1',
    };
    mockedState.mockFetchAndSeedTaskQuery.mockResolvedValue(fetchedTask);

    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    const event: RawDatabaseEvent = {
      table: 'tasks',
      eventType: 'INSERT',
      receivedAt: Date.now(),
      new: {
        id: 'task-2',
        project_id: 'proj-1',
        status: 'Queued',
      },
      old: null,
    };

    act(() => {
      mockedState.rawEventCallback?.(event);
    });

    await waitFor(() => {
      expect(mockedState.mockFetchAndSeedTaskQuery).toHaveBeenCalledWith(expect.anything(), 'task-2', 'proj-1');
    });
    expect(mockedState.mockUpsertRealtimeTaskSnapshot).toHaveBeenCalledWith(fetchedTask, 'proj-1');
  });

  it('clears previous project scope and disconnects when the selected project changes away or clears', () => {
    const { queryClient, rerender } = renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    mockedState.mockUseProject.mockReturnValue({ selectedProjectId: 'proj-2' });
    rerender(
      <QueryClientProvider client={queryClient}>
        <RealtimeProvider>
          <RealtimeConsumer />
        </RealtimeProvider>
      </QueryClientProvider>
    );

    expect(mockedState.mockResetRealtimeTaskScope).toHaveBeenCalledWith('proj-1');
    expect(mockedState.mockResetRealtimeTaskScope).toHaveBeenCalledWith('proj-2');
    expect(mockRealtimeConnection.disconnect).toHaveBeenCalledTimes(0);

    mockedState.mockUseProject.mockReturnValue({ selectedProjectId: null });
    rerender(
      <QueryClientProvider client={queryClient}>
        <RealtimeProvider>
          <RealtimeConsumer />
        </RealtimeProvider>
      </QueryClientProvider>
    );

    expect(mockedState.mockResetRealtimeTaskScope).toHaveBeenCalledWith('proj-2');
    expect(mockRealtimeConnection.disconnect).toHaveBeenCalledTimes(1);
    expect(mockedState.mockDataFreshnessManager.reset).toHaveBeenCalledTimes(1);
  });

  it('updates state when status changes', () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    act(() => {
      mockedState.statusChangeCallback?.({
        status: 'connected',
        projectId: 'proj-1',
        error: null,
        statusChangedAt: Date.now(),
        reconnectAttempt: 0,
        nextRetryAt: null,
      });
    });

    expect(screen.getByTestId('status')).toHaveTextContent('connected');
    expect(screen.getByTestId('isConnected')).toHaveTextContent('true');
  });

  it('provides reconnect function', () => {
    renderWithProviders(
      <RealtimeProvider>
        <RealtimeConsumer />
      </RealtimeProvider>
    );

    act(() => {
      screen.getByTestId('reconnect').click();
    });

    expect(mockRealtimeConnection.reset).toHaveBeenCalled();
    expect(mockRealtimeConnection.connect).toHaveBeenCalledWith('proj-1');
  });

  describe('useRealtime hook', () => {
    it('returns default values when used outside provider', () => {
      function OutsideConsumer() {
        const ctx = useRealtime();
        return <span data-testid="status">{ctx.status}</span>;
      }

      render(<OutsideConsumer />);
      expect(screen.getByTestId('status')).toHaveTextContent('disconnected');
    });
  });
});
