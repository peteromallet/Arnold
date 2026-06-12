import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Mock Supabase client with a chainable from/select/eq/order shape.
// The read path (useQuery) calls:
//   supabase.from('timelines').select('*').eq('project_id', ...).order(...)
// The mutation paths create additional chains but must not throw on setup.
// ---------------------------------------------------------------------------

// We use a mutable variable so beforeEach can reset it, and wrap it in a
// thenable so `await supabase.from(...).select(...).eq(...).order(...)` works.
let timelineResponse: { data: unknown; error: { message: string } | null } = { data: [], error: null };

function createTimelineTerminal() {
  // PostgrestFilterBuilder is thenable — `await` calls its .then().
  // The queryFn destructures `{ data, error }` from the resolved value,
  // so we always resolve with the { data, error } object (never reject).
  return {
    then(resolve: (value: unknown) => void) {
      resolve(timelineResponse);
    },
  };
}

const mockTimelineOrder = vi.fn().mockReturnValue(createTimelineTerminal());
const mockTimelineEq = vi.fn().mockReturnValue({ order: mockTimelineOrder });
const mockTimelineSelect = vi.fn().mockReturnValue({ eq: mockTimelineEq });

// Mutations use insert/update/delete chains that we don't call in read tests.
const mockInsertSelect = vi.fn();
const mockInsertSingle = vi.fn().mockReturnValue(mockInsertSelect);
const mockInsert = vi.fn().mockReturnValue({ select: mockInsertSingle });

const mockUpdateEq = vi.fn();
const mockUpdate = vi.fn().mockReturnValue({ eq: mockUpdateEq });

const mockDeleteEq = vi.fn();
const mockDelete = vi.fn().mockReturnValue({ eq: mockDeleteEq });

const mockFrom = vi.fn((table: string) => {
  if (table === 'timelines') {
    return {
      select: mockTimelineSelect,
      insert: mockInsert,
      update: mockUpdate,
      delete: mockDelete,
    };
  }
  return { select: vi.fn() };
});

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: mockFrom,
  }),
}));

vi.mock('@/shared/lib/supabaseSession', () => ({
  readAccessTokenFromStorage: vi.fn(),
}));

import { useReighTimelinesList } from './useReighTimelinesList';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';
const USER_ID = '22222222-2222-2222-2222-222222222222';

describe('useReighTimelinesList — read path', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: the select query returns an empty array.
    timelineResponse = { data: [], error: null };
  });

  it('reads materialized timelines rows including config via select(*)', async () => {
    const timelineRow = {
      id: 'timeline-1',
      project_id: PROJECT_ID,
      user_id: USER_ID,
      name: 'Test Timeline',
      config: { output: { resolution: '1920x1080', fps: 30, file: 'tl.mp4' }, tracks: [], clips: [] },
      config_version: 7,
      asset_registry: { assets: { 'a1': { file: 'clips/demo.mp4' } } },
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-06-12T00:00:00Z',
    };
    timelineResponse = { data: [timelineRow], error: null };

    const { result } = renderHook(
      () => useReighTimelinesList(PROJECT_ID, USER_ID),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // The Supabase query must target the timelines table.
    expect(mockFrom).toHaveBeenCalledWith('timelines');
    expect(mockTimelineSelect).toHaveBeenCalledWith('*');
    expect(mockTimelineEq).toHaveBeenCalledWith('project_id', PROJECT_ID);
    expect(mockTimelineOrder).toHaveBeenCalledWith('updated_at', { ascending: false });

    // The returned data must preserve the materialized config field.
    expect(result.current.data).toEqual([timelineRow]);
    expect(result.current.data![0].config).toEqual(timelineRow.config);
    expect(result.current.data![0].config_version).toBe(7);
    expect(result.current.data![0].asset_registry).toEqual(timelineRow.asset_registry);
  });

  it('returns an empty array when there are no timelines', async () => {
    timelineResponse = { data: null, error: null };

    const { result } = renderHook(
      () => useReighTimelinesList(PROJECT_ID, USER_ID),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
  });

  it('disables the query when projectId is null', () => {
    const { result } = renderHook(
      () => useReighTimelinesList(null, USER_ID),
      { wrapper: createWrapper() },
    );

    // When disabled, the queryFn is never called.
    expect(mockFrom).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('disables the query when projectId is undefined', () => {
    const { result } = renderHook(
      () => useReighTimelinesList(undefined, USER_ID),
      { wrapper: createWrapper() },
    );

    expect(mockFrom).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it('throws on Supabase query error', async () => {
    timelineResponse = { data: null, error: { message: 'connection refused' } };

    const { result } = renderHook(
      () => useReighTimelinesList(PROJECT_ID, USER_ID),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});
