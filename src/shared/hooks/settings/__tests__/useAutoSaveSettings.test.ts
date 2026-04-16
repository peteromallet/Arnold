import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock dependencies
vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: vi.fn().mockReturnValue({
    settings: null,
    isLoading: false,
    update: vi.fn().mockResolvedValue(undefined),
    hasShotSettings: false,
  }),
  updateToolSettingsSupabase: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/shared/lib/utils/deepEqual', () => ({
  deepEqual: (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b),
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: vi.fn(),
  reportRuntimeError: vi.fn(),
}));

import { useAutoSaveSettings } from '@/shared/settings/hooks/useAutoSaveSettings';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';

type TestSettings = Record<string, unknown> & {
  prompt: string;
  mode: string;
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useAutoSaveSettings', () => {
  const defaults: TestSettings = { prompt: '', mode: 'basic' };

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial state', () => {
    it('returns defaults as initial settings', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      expect(result.current.settings).toEqual(defaults);
    });

    it('starts with idle status when no entity', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: null }),
        { wrapper: createWrapper() }
      );

      expect(result.current.status).toBe('idle');
    });

    it('starts not dirty', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isDirty).toBe(false);
    });

    it('starts without persisted data', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      expect(result.current.hasPersistedData).toBe(false);
    });
  });

  describe('React Query mode', () => {
    it('transitions to ready when DB data arrives', async () => {
      const mockUpdate = vi.fn().mockResolvedValue(undefined);
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: { prompt: 'saved prompt', mode: 'advanced' },
        isLoading: false,
        update: mockUpdate,
        hasShotSettings: true,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      // Should apply DB settings
      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      expect(result.current.status).toBe('ready');
      expect(result.current.settings.prompt).toBe('saved prompt');
      expect(result.current.hasShotSettings).toBe(true);
    });

    it('switches entity state through the reducer when the shot changes', async () => {
      const mockUpdate = vi.fn().mockResolvedValue(undefined);
      let shotId: string | null = 'shot-1';

      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockImplementation((_toolId, options) => ({
        settings: options.shotId === 'shot-1'
          ? { prompt: 'first prompt', mode: 'basic' }
          : { prompt: 'second prompt', mode: 'advanced' },
        isLoading: false,
        update: mockUpdate,
        hasShotSettings: true,
      }));

      const { result, rerender } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      expect(result.current.entityId).toBe('shot-1');
      expect(result.current.settings.prompt).toBe('first prompt');

      shotId = 'shot-2';
      rerender();

      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      expect(result.current.entityId).toBe('shot-2');
      expect(result.current.settings.prompt).toBe('second prompt');
      expect(result.current.status).toBe('ready');
    });

    it('stays idle when no entity ID', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: null }),
        { wrapper: createWrapper() }
      );

      expect(result.current.status).toBe('idle');
    });
  });

  describe('customLoadSave mode', () => {
    it('loads data via custom load function', async () => {
      const mockLoad = vi.fn().mockResolvedValue({ prompt: 'custom loaded', mode: 'expert' });
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'custom-entity-1',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      // Wait for the promise to resolve
      await act(async () => {});

      expect(mockLoad).toHaveBeenCalledWith('custom-entity-1');
      expect(result.current.settings.prompt).toBe('custom loaded');
      expect(result.current.status).toBe('ready');
      expect(result.current.hasPersistedData).toBe(true);
    });

    it('uses defaults when custom load returns null', async () => {
      const mockLoad = vi.fn().mockResolvedValue(null);
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'custom-entity-2',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.settings).toEqual(defaults);
      expect(result.current.hasPersistedData).toBe(false);
    });

    it('bootstraps custom entities from provided seed data when no persisted record exists', async () => {
      const mockLoad = vi.fn().mockResolvedValue(null);
      const mockSave = vi.fn().mockResolvedValue(undefined);
      const bootstrapData = { prompt: '', mode: 'seeded' };

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          bootstrapData,
          customLoadSave: {
            entityId: 'custom-entity-seeded',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.settings).toEqual(bootstrapData);
      expect(result.current.hasPersistedData).toBe(false);
      expect(result.current.isDirty).toBe(false);
    });

    it('handles custom load error', async () => {
      const mockLoad = vi.fn().mockRejectedValue(new Error('load failed'));
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'custom-entity-3',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.status).toBe('error');
      expect(result.current.error).toBeTruthy();
    });

    it('resets to loading defaults before loading the next custom entity', async () => {
      const mockLoad = vi
        .fn()
        .mockResolvedValueOnce({ prompt: 'entity one', mode: 'basic' })
        .mockResolvedValueOnce({ prompt: 'entity two', mode: 'advanced' });
      const mockSave = vi.fn().mockResolvedValue(undefined);
      let entityId = 'custom-entity-1';

      const { result, rerender } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId,
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.settings.prompt).toBe('entity one');
      expect(result.current.status).toBe('ready');

      entityId = 'custom-entity-2';
      rerender();

      expect(result.current.entityId).toBe('custom-entity-2');
      expect(result.current.settings).toEqual(defaults);
      expect(result.current.status).toBe('loading');

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.settings.prompt).toBe('entity two');
      expect(result.current.status).toBe('ready');
    });
  });

  describe('field updates', () => {
    it('updateField updates a single field', () => {
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: defaults,
        isLoading: false,
        update: vi.fn().mockResolvedValue(undefined),
        hasShotSettings: false,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.updateField('prompt', 'new prompt');
      });

      expect(result.current.settings.prompt).toBe('new prompt');
    });

    it('updateFields updates multiple fields at once', () => {
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: defaults,
        isLoading: false,
        update: vi.fn().mockResolvedValue(undefined),
        hasShotSettings: false,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.updateFields({ prompt: 'updated', mode: 'expert' });
      });

      expect(result.current.settings.prompt).toBe('updated');
      expect(result.current.settings.mode).toBe('expert');
    });

    it('updateTextField updates local state without scheduling a debounced save', async () => {
      const mockUpdate = vi.fn().mockResolvedValue(undefined);
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: defaults,
        isLoading: false,
        update: mockUpdate,
        hasShotSettings: false,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1', debounceMs: 100 }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.updateTextField('prompt', 'typed locally');
      });

      expect(result.current.settings.prompt).toBe('typed locally');

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(mockUpdate).not.toHaveBeenCalled();
    });
  });

  describe('revert', () => {
    it('reverts to last loaded settings', async () => {
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: { prompt: 'saved', mode: 'basic' },
        isLoading: false,
        update: vi.fn().mockResolvedValue(undefined),
        hasShotSettings: true,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      // Wait for DB settings to load
      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      expect(result.current.settings.prompt).toBe('saved');

      // Modify
      act(() => {
        result.current.updateField('prompt', 'modified');
      });
      expect(result.current.settings.prompt).toBe('modified');

      // Revert
      act(() => {
        result.current.revert();
      });
      expect(result.current.settings.prompt).toBe('saved');
    });
  });

  describe('reset', () => {
    it('resets to defaults in custom mode', async () => {
      const mockLoad = vi.fn().mockResolvedValue({ prompt: 'loaded', mode: 'advanced' });
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'entity-reset-1',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      // Wait for load
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.settings.prompt).toBe('loaded');

      act(() => {
        result.current.updateField('prompt', 'modified');
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.settings).toEqual(defaults);
    });

    it('resets to provided new defaults in custom mode', async () => {
      const mockLoad = vi.fn().mockResolvedValue({ prompt: 'loaded', mode: 'advanced' });
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'entity-reset-2',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      // Wait for load
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      const newDefaults = { prompt: 'custom default', mode: 'custom' };
      act(() => {
        result.current.reset(newDefaults);
      });

      expect(result.current.settings).toEqual(newDefaults);
    });
  });

  describe('initializeFrom', () => {
    it('applies data in custom mode when no persisted data', async () => {
      const mockLoad = vi.fn().mockResolvedValue(null);
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'entity-init',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      // Wait for load to complete (returns null = no persisted data)
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      act(() => {
        result.current.initializeFrom({ prompt: 'initialized' });
      });

      expect(result.current.settings.prompt).toBe('initialized');
    });

    it('is a no-op in React Query mode', () => {
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: defaults,
        isLoading: false,
        update: vi.fn().mockResolvedValue(undefined),
        hasShotSettings: false,
      });

      const { result } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-1' }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.initializeFrom({ prompt: 'should not apply' });
      });

      expect(result.current.settings.prompt).toBe('');
    });
  });

  describe('disabled hook', () => {
    it('does not load when enabled is false', () => {
      const { result } = renderHook(
        () => useAutoSaveSettings({
          toolId: 'test',
          defaults,
          shotId: 'shot-1',
          enabled: false,
        }),
        { wrapper: createWrapper() }
      );

      expect(result.current.status).toBe('idle');
    });
  });

  describe('entity-change flush', () => {
    it('flushes dirty settings when entity changes in custom mode', async () => {
      const mockLoad = vi.fn().mockResolvedValue({ prompt: 'loaded', mode: 'basic' });
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const wrapper = createWrapper();
      let entityId = 'entity-A';

      const { result, rerender } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId,
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper }
      );

      // Wait for initial load to complete
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.status).toBe('ready');
      expect(result.current.settings.prompt).toBe('loaded');

      // Make a dirty edit (no debounce fire yet)
      act(() => {
        result.current.updateField('prompt', 'dirty edit');
      });
      expect(result.current.settings.prompt).toBe('dirty edit');

      // Clear save mock to isolate the flush call
      mockSave.mockClear();

      // Change entity — triggers cleanup flush of entity-A's pending edits
      entityId = 'entity-B';
      rerender();

      // Allow flush promise to settle
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      // Verify flush: mockSave should have been called with entity-A and dirty data
      expect(mockSave).toHaveBeenCalledWith(
        'entity-A',
        expect.objectContaining({ prompt: 'dirty edit' })
      );
    });
  });

  describe('pending-edit protection', () => {
    it('preserves user edits made during loading in custom mode', async () => {
      let resolveLoad!: (value: TestSettings | null) => void;
      const mockLoad = vi.fn().mockImplementation(
        () => new Promise<TestSettings | null>((resolve) => { resolveLoad = resolve; })
      );
      const mockSave = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          customLoadSave: {
            entityId: 'entity-pending',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      // Trigger the load effect
      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      expect(result.current.status).toBe('loading');
      expect(mockLoad).toHaveBeenCalledWith('entity-pending');

      // User types while load is in flight
      act(() => {
        result.current.updateField('prompt', 'user typed this');
      });

      expect(result.current.settings.prompt).toBe('user typed this');

      // Now resolve the load with DB data
      await act(async () => {
        resolveLoad({ prompt: 'from database', mode: 'advanced' });
      });
      await act(async () => {});

      // User's edit should be preserved — not overwritten by DB data
      expect(result.current.settings.prompt).toBe('user typed this');
      expect(result.current.status).toBe('ready');
    });

    it('preserves user edits made during loading in React Query mode', async () => {
      const mockUpdate = vi.fn().mockResolvedValue(undefined);

      // Start with loading state
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: null,
        isLoading: true,
        update: mockUpdate,
        hasShotSettings: false,
      });

      const { result, rerender } = renderHook(
        () => useAutoSaveSettings({ toolId: 'test', defaults, shotId: 'shot-rq' }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        vi.advanceTimersByTime(10);
      });

      // Status should be loading
      expect(result.current.status).toBe('loading');

      // User types while DB query is in flight
      act(() => {
        result.current.updateField('prompt', 'typed during load');
      });
      expect(result.current.settings.prompt).toBe('typed during load');

      // DB data arrives
      (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        settings: { prompt: 'db value', mode: 'advanced' },
        isLoading: false,
        update: mockUpdate,
        hasShotSettings: true,
      });
      rerender();

      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      // User's edit should be preserved
      expect(result.current.settings.prompt).toBe('typed during load');
      expect(result.current.status).toBe('ready');
    });
  });

  describe('race condition: typing during save', () => {
    it('preserves new edits made during an in-flight save in custom mode', async () => {
      let resolveSave!: () => void;
      const mockLoad = vi.fn().mockResolvedValue({ prompt: 'initial', mode: 'basic' });
      const mockSave = vi.fn().mockImplementation(
        () => new Promise<void>((resolve) => { resolveSave = resolve; })
      );

      const { result } = renderHook(
        () => useAutoSaveSettings({
          defaults,
          debounceMs: 100,
          customLoadSave: {
            entityId: 'entity-race',
            load: mockLoad,
            save: mockSave,
          },
        }),
        { wrapper: createWrapper() }
      );

      // Wait for load
      await act(async () => {
        vi.advanceTimersByTime(10);
      });
      await act(async () => {});

      expect(result.current.status).toBe('ready');

      // First edit — triggers debounced save
      act(() => {
        result.current.updateField('prompt', 'first edit');
      });

      // Fire the debounce — starts the save
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      // Save is now in-flight (mockSave was called but not resolved)
      expect(mockSave).toHaveBeenCalledTimes(1);

      // User types more while save is in-flight
      act(() => {
        result.current.updateField('prompt', 'second edit during save');
      });

      // Resolve the first save
      await act(async () => {
        resolveSave();
      });
      await act(async () => {});

      // The second edit should still be in settings
      expect(result.current.settings.prompt).toBe('second edit during save');
    });
  });
});
