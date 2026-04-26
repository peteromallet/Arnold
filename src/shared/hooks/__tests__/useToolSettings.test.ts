import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import {
  extractSettingsFromCache,
  updateToolSettingsSupabase,
  updateSettingsCache,
} from '@/shared/hooks/settings/useToolSettings';
import { enqueueSettingsWrite } from '@/shared/lib/settingsWriteQueue';

// ============================================================================
// Tests for exported pure helper functions
// ============================================================================

describe('extractSettingsFromCache', () => {
  it('returns undefined for null/undefined input', () => {
    expect(extractSettingsFromCache(null)).toBeUndefined();
    expect(extractSettingsFromCache(undefined)).toBeUndefined();
  });

  it('extracts settings from wrapper format', () => {
    const cacheData = {
      settings: { prompt: 'test', seed: 42 },
      hasShotSettings: true,
    };
    const result = extractSettingsFromCache<{ prompt: string; seed: number }>(cacheData);
    expect(result).toEqual({ prompt: 'test', seed: 42 });
  });

  it('returns data as-is for flat format (legacy)', () => {
    const cacheData = { prompt: 'test', seed: 42 };
    const result = extractSettingsFromCache<{ prompt: string; seed: number }>(cacheData);
    expect(result).toEqual({ prompt: 'test', seed: 42 });
  });

  it('handles empty settings object in wrapper format', () => {
    const cacheData = { settings: {}, hasShotSettings: false };
    const result = extractSettingsFromCache<Record<string, unknown>>(cacheData);
    expect(result).toEqual({});
  });
});

describe('updateSettingsCache', () => {
  it('merges updates into wrapper format', () => {
    const prev = {
      settings: { prompt: 'old', seed: 42 },
      hasShotSettings: true,
    };
    const result = updateSettingsCache<{ prompt: string; seed: number }>(prev, { prompt: 'new' });

    expect(result.settings).toEqual({ prompt: 'new', seed: 42 });
    expect(result.hasShotSettings).toBe(true);
  });

  it('merges updates into flat format (legacy)', () => {
    const prev = { prompt: 'old', seed: 42 };
    const result = updateSettingsCache<{ prompt: string; seed: number }>(prev, { prompt: 'new' });

    expect(result.settings).toEqual({ prompt: 'new', seed: 42 });
    expect(result.hasShotSettings).toBe(false);
  });

  it('handles null prev data', () => {
    const result = updateSettingsCache<{ prompt: string }>(null, { prompt: 'new' });

    expect(result.settings).toEqual({ prompt: 'new' });
    expect(result.hasShotSettings).toBe(false);
  });

  it('handles undefined prev data', () => {
    const result = updateSettingsCache<{ prompt: string }>(undefined, { prompt: 'new' });

    expect(result.settings).toEqual({ prompt: 'new' });
    expect(result.hasShotSettings).toBe(false);
  });

  it('supports function updater', () => {
    const prev = {
      settings: { count: 5, label: 'test' },
      hasShotSettings: false,
    };

    const result = updateSettingsCache<{ count: number; label: string }>(
      prev,
      (prevSettings) => ({ count: prevSettings.count + 1 })
    );

    expect(result.settings).toEqual({ count: 6, label: 'test' });
  });

  it('preserves hasShotSettings from existing wrapper', () => {
    const prev = {
      settings: { prompt: 'old' },
      hasShotSettings: true,
    };
    const result = updateSettingsCache<{ prompt: string }>(prev, { prompt: 'new' });

    expect(result.hasShotSettings).toBe(true);
  });

  it('sets hasShotSettings to false for non-wrapper format', () => {
    const prev = { prompt: 'old' };
    const result = updateSettingsCache<{ prompt: string }>(prev, { prompt: 'new' });

    expect(result.hasShotSettings).toBe(false);
  });
});

describe('updateToolSettingsSupabase', () => {
  beforeEach(() => {
    vi.mocked(enqueueSettingsWrite).mockClear();
  });

  it('accepts mode via an explicit options object', async () => {
    await updateToolSettingsSupabase(
      {
        scope: 'user',
        id: 'user-1',
        toolId: 'tool-1',
        patch: { foo: 'bar' },
      },
      { mode: 'immediate' },
    );

    expect(enqueueSettingsWrite).toHaveBeenCalledWith(
      expect.objectContaining({
        scope: 'user',
        entityId: 'user-1',
        toolId: 'tool-1',
        patch: { foo: 'bar' },
      }),
      'immediate',
      expect.any(Function),
    );
  });

  it('accepts signal + mode via an explicit options object and forwards the signal', async () => {
    const controller = new AbortController();

    await updateToolSettingsSupabase(
      {
        scope: 'project',
        id: 'project-1',
        toolId: 'tool-1',
        patch: { foo: 'bar' },
      },
      { signal: controller.signal, mode: 'immediate' },
    );

    expect(enqueueSettingsWrite).toHaveBeenCalledWith(
      expect.objectContaining({
        scope: 'project',
        entityId: 'project-1',
        toolId: 'tool-1',
        patch: { foo: 'bar' },
        signal: controller.signal,
      }),
      'immediate',
      expect.any(Function),
    );
  });
});

// ============================================================================
// Tests for the useToolSettings hook
// ============================================================================

// Mock dependencies
vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: () => ({ selectedProjectId: 'project-1' }),
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1', project: null, setSelectedProjectId: vi.fn() }),
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
  useProjectIdentityContext: () => ({ userId: 'user-1' }),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: null }),
    }),
    rpc: vi.fn().mockResolvedValue({ data: null, error: null }),
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: 'user-1' } }, error: null }),
    },
  }),
}));

vi.mock('@/shared/settings', async () => {
  const actual = await vi.importActual<typeof import('@/shared/settings')>(
    '@/shared/settings',
  );
  return {
    ...actual,
    ensureToolSettingsAuthCacheInitialized: vi.fn().mockResolvedValue(undefined),
    fetchToolSettingsSupabase: vi.fn().mockResolvedValue({
      settings: { prompt: 'default', seed: 1 },
      hasShotSettings: false,
    }),
    resolveAndCacheUserId: vi.fn().mockResolvedValue({ data: { user: { id: 'user-1' } } }),
  };
});

vi.mock('@/shared/lib/settingsWriteQueue', () => ({
  enqueueSettingsWrite: vi.fn().mockResolvedValue({ prompt: 'saved' }),
}));

vi.mock('@/shared/lib/errorHandling/errorUtils', () => ({
  isCancellationError: () => false,
  getErrorMessage: (error: unknown) => error instanceof Error ? error.message : String(error),
  isErrorWithCode: () => false,
  isErrorWithStatus: () => false,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useToolSettings hook', () => {
  // Import the hook directly — vi.mock hoisting ensures mocks are applied
   
  let useToolSettings: typeof import('@/shared/hooks/settings/useToolSettings').useToolSettings;

  beforeEach(async () => {
    vi.mocked(enqueueSettingsWrite).mockClear();
    const mod = await import('@/shared/hooks/settings/useToolSettings');
    useToolSettings = mod.useToolSettings;
  });

  it('returns loading state initially', () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useToolSettings('test-tool'), { wrapper });

    // Should have the expected shape
    expect(result.current).toHaveProperty('settings');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('update');
    expect(result.current).toHaveProperty('isUpdating');
    expect(result.current).toHaveProperty('hasShotSettings');
  });

  it('returns a stable update function', () => {
    const wrapper = createWrapper();
    const { result, rerender } = renderHook(() => useToolSettings('test-tool'), { wrapper });

    const firstUpdate = result.current.update;
    rerender();
    expect(result.current.update).toBe(firstUpdate);
  });

  it('respects enabled option', () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useToolSettings('test-tool', { enabled: false }),
      { wrapper }
    );

    // When disabled, settings should be undefined
    expect(result.current.settings).toBeUndefined();
  });

  it('uses provided projectId over context', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useToolSettings('test-tool', { projectId: 'custom-project' }),
      { wrapper }
    );

    await waitFor(() => {
      // Just verify it doesn't crash with custom projectId
      expect(result.current).toHaveProperty('settings');
    });
  });

  it('throws auth_required for user-scope updates without an authenticated user', async () => {
    const toolSettingsService = await import('@/shared/settings');
    vi.mocked(toolSettingsService.resolveAndCacheUserId).mockResolvedValueOnce({
      data: { user: null },
      error: null,
    });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useToolSettings<Record<string, unknown>>('test-tool'), { wrapper });

    await expect(result.current.update('user', { prompt: 'test' })).rejects.toMatchObject({
      code: 'auth_required',
    });
    expect(enqueueSettingsWrite).not.toHaveBeenCalled();
  });
});
