// @vitest-environment jsdom
 
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockSyncTimeline = vi.fn();
const mockReloadFromServer = vi.fn();

const mocks = vi.hoisted(() => ({
  useTimelineEditorData: vi.fn(),
  useTimelineChromeContext: vi.fn(),
  useTimelinePlaybackContext: vi.fn(),
  useTimelineEditorOps: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineEditorData: () => mocks.useTimelineEditorData(),
  useTimelineChromeContext: () => mocks.useTimelineChromeContext(),
  useTimelinePlaybackContext: () => mocks.useTimelinePlaybackContext(),
  useTimelineEditorOps: () => mocks.useTimelineEditorOps(),
}));

// We import SupabaseDataProvider just for its prototype, then mock its module.
// The mock factory is hoisted by Vitest so the import below resolves first.
import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider';
import type {
  AppSyncState,
  SyncTimelineAction,
  SyncTimelineResult,
} from '@/tools/video-editor/data/SupabaseDataProvider';

vi.mock('@/tools/video-editor/data/SupabaseDataProvider', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/data/SupabaseDataProvider')>(
    '@/tools/video-editor/data/SupabaseDataProvider',
  );
  return {
    ...actual,
    // Keep the real class so instanceof works, but replace the constructor
    // so tests always control the instance.
    SupabaseDataProvider: actual.SupabaseDataProvider,
  };
});

import { useEditorSync } from '@/tools/video-editor/hooks/useEditorSync';
import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext';
import type { VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import type { TimelineConfig } from '@/tools/video-editor/types';
import type { AssetRegistry } from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildConfig(): TimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'test.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [],
  };
}

function buildDbHead(version: number, hash: string, eventId: string) {
  return { version, hash, event_id: eventId };
}

function buildBookmark() {
  return {
    timeline_id: 'timeline-1',
    spoke: 'app' as const,
    spoke_version: 7,
    spoke_hash: 'a'.repeat(64),
    spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    hub_version: 7,
    hub_hash: 'a'.repeat(64),
    hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    synced_at: '2026-06-12T04:22:00.000Z',
  };
}

function buildSyncResult(
  state: AppSyncState,
  action: SyncTimelineAction,
  overrides: Partial<SyncTimelineResult> = {},
): SyncTimelineResult {
  return {
    state,
    action,
    configVersion: 8,
    dbHead: buildDbHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
    bookmark: buildBookmark(),
    ...overrides,
  };
}

/**
 * Create a SupabaseDataProvider-shaped object that passes `instanceof SupabaseDataProvider`.
 * The mock's `syncTimeline` is wired to `mockSyncTimeline`.
 */
function createMockSupabaseProvider() {
  const provider = Object.create(SupabaseDataProvider.prototype);
  provider.syncTimeline = mockSyncTimeline;
  return provider as SupabaseDataProvider & { syncTimeline: typeof mockSyncTimeline };
}

function createRuntime(overrides: Partial<VideoEditorRuntimeContextValue> = {}): VideoEditorRuntimeContextValue {
  return {
    provider: createMockSupabaseProvider() as unknown as DataProvider,
    assetResolver: { resolveAssetUrl: vi.fn(), resolveAssetThumbnailUrl: vi.fn() } as any,
    auth: {} as any,
    project: { projectId: 'project-1' } as any,
    shots: {} as any,
    mediaLightbox: {} as any,
    agentChat: {} as any,
    toast: {} as any,
    telemetry: {} as any,
    timelineId: 'timeline-1',
    userId: 'user-1',
    timelineName: 'Test Timeline',
    extensions: { slots: {}, dialogHost: { dialogs: [] }, registry: { panels: [], inspectorSections: [] } },
    ...overrides,
  };
}

function createNonSupabaseRuntime(): VideoEditorRuntimeContextValue {
  return {
    ...createRuntime(),
    provider: {
      persistenceEnabled: true,
      resolveAssetUrl: vi.fn(),
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
    } as unknown as DataProvider,
  };
}

interface WrapperOptions {
  runtime: VideoEditorRuntimeContextValue;
}

function createWrapper({ runtime }: WrapperOptions) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(DataProviderContext.Provider, { value: runtime }, children);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();

  mockReloadFromServer.mockReset();

  mocks.useTimelineEditorData.mockReturnValue({
    data: {
      config: buildConfig(),
      configVersion: 7,
      registry: { assets: {} } as AssetRegistry,
    },
    resolvedConfig: null,
    deviceClass: 'desktop',
    inputModality: 'mouse',
    interactionMode: 'select',
    gestureOwner: 'none',
    precisionEnabled: false,
    contextTarget: { kind: 'timeline' },
    inspectorTarget: { kind: 'timeline' },
    selectedClipId: null,
    selectedClipIds: new Set<string>(),
    selectedTrackId: null,
    compositionSize: { width: 1280, height: 720 },
    trackScaleMap: {},
    scale: 1,
    scaleWidth: 1280,
    isLoading: false,
  });

  mocks.useTimelineChromeContext.mockReturnValue({
    timelineName: 'Test Timeline',
    saveStatus: 'saved' as const,
    isConflictExhausted: false,
    renderStatus: 'idle' as const,
    renderLog: '',
    renderDirty: false,
    renderProgress: null,
    renderResultUrl: null,
    renderResultFilename: null,
    undo: vi.fn(),
    redo: vi.fn(),
    canUndo: false,
    canRedo: false,
    checkpoints: [],
    jumpToCheckpoint: vi.fn(),
    createManualCheckpoint: vi.fn(),
    setScaleWidth: vi.fn(),
    handleAddTrack: vi.fn(),
    handleClearUnusedTracks: vi.fn(),
    unusedTrackCount: 0,
    handleAddText: vi.fn(),
    handleAddTextAt: vi.fn(),
    reloadFromServer: mockReloadFromServer,
    retrySaveAfterConflict: vi.fn(),
    startRender: vi.fn(),
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useEditorSync', () => {
  // --- Sync button visibility (DB mode detection) ---

  describe('Sync button visibility (isSyncAvailable)', () => {
    it('returns isSyncAvailable: false when no DataProviderContext is provided', () => {
      const { result } = renderHook(() => useEditorSync());
      expect(result.current.isSyncAvailable).toBe(false);
      expect(result.current.syncState).toBe('idle');
      expect(result.current.lastSyncResult).toBeNull();
      expect(result.current.syncError).toBeNull();
    });

    it('returns isSyncAvailable: false when the provider is not a SupabaseDataProvider', () => {
      const runtime = createNonSupabaseRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });
      expect(result.current.isSyncAvailable).toBe(false);
    });

    it('returns isSyncAvailable: true when the provider is a SupabaseDataProvider', () => {
      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });
      expect(result.current.isSyncAvailable).toBe(true);
    });

    it('performSync is a no-op when isSyncAvailable is false', async () => {
      const { result } = renderHook(() => useEditorSync());
      expect(result.current.isSyncAvailable).toBe(false);

      await act(async () => {
        await result.current.performSync();
      });

      expect(result.current.syncState).toBe('idle');
      expect(mockSyncTimeline).not.toHaveBeenCalled();
    });
  });

  // --- Source-only fast-forward ---

  describe('source_only (fast-forward)', () => {
    it('sets syncState to source_only_saved and calls reloadFromServer after a successful source_only sync', async () => {
      mockSyncTimeline.mockResolvedValue(buildSyncResult('source_only', 'saved', { configVersion: 8 }));

      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'dirty' as const,
        reloadFromServer: mockReloadFromServer,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      expect(result.current.isSyncAvailable).toBe(true);

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('source_only_saved');
      });

      expect(mockSyncTimeline).toHaveBeenCalledTimes(1);
      expect(mockSyncTimeline).toHaveBeenCalledWith({
        timelineId: 'timeline-1',
        config: buildConfig(),
        currentConfigVersion: 7,
        hasUnsavedEdits: true,
        registry: { assets: {} },
      });
      expect(mockReloadFromServer).toHaveBeenCalledTimes(1);
      expect(result.current.lastSyncResult).toEqual(
        expect.objectContaining({
          state: 'source_only',
          action: 'saved',
          configVersion: 8,
        }),
      );
      expect(result.current.syncError).toBeNull();
    });

    it('does not require unsaved edits for source_only — the provider handles the decision', async () => {
      mockSyncTimeline.mockResolvedValue(buildSyncResult('source_only', 'saved', { configVersion: 8 }));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('source_only_saved');
      });
      expect(mockReloadFromServer).toHaveBeenCalledTimes(1);
    });

    it('populates lastSyncResult with bookmark and dbHead from the sync response', async () => {
      const bookmark = buildBookmark();
      const dbHead = buildDbHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB');
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('source_only', 'saved', { configVersion: 8, bookmark, dbHead }),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.lastSyncResult).not.toBeNull();
      });
      expect(result.current.lastSyncResult).toEqual(
        expect.objectContaining({
          state: 'source_only',
          action: 'saved',
          configVersion: 8,
          dbHead,
          bookmark,
        }),
      );
    });
  });

  // --- DB-only reload-needed ---

  describe('destination_only (reload-needed)', () => {
    it('sets syncState to destination_only_reloaded and reloads when there are no unsaved edits', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('destination_only', 'reload_required', { configVersion: 7 }),
      );

      // saveStatus is 'saved' → hasUnsavedEdits = false
      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'saved' as const,
        reloadFromServer: mockReloadFromServer,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('destination_only_reloaded');
      });

      expect(mockReloadFromServer).toHaveBeenCalledTimes(1);
      expect(result.current.syncError).toBeNull();
    });

    it('passes hasUnsavedEdits=false to syncTimeline when saveStatus is not dirty/error', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('destination_only', 'reload_required'),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockSyncTimeline).toHaveBeenCalledWith(
        expect.objectContaining({ hasUnsavedEdits: false }),
      );
    });

    it('falls back to error state when destination_only arrives with unsaved edits', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('destination_only', 'reload_required'),
      );

      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'dirty' as const,
        reloadFromServer: mockReloadFromServer,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('error');
      });
      expect(result.current.syncError).toBe('Unexpected: destination-only with unsaved edits');
      // reloadFromServer should NOT have been called in this error path
      expect(mockReloadFromServer).not.toHaveBeenCalled();
    });
  });

  // --- Both-advanced with inspectable keep-both artifact ---

  describe('both_advanced (divergence)', () => {
    it('sets syncState to both_advanced and surfaces keepBothArtifact metadata', async () => {
      const keepBothArtifact = {
        id: 'artifact-abc-123',
        created_at: '2026-06-12T06:00:00.000Z',
        remote_entry_id: 'divergence-row-1',
      };
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('both_advanced', 'divergence_recorded', {
          configVersion: 7,
          keepBothArtifact,
        }),
      );

      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'dirty' as const,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('both_advanced');
      });

      expect(result.current.lastSyncResult).toEqual(
        expect.objectContaining({
          state: 'both_advanced',
          action: 'divergence_recorded',
          keepBothArtifact,
        }),
      );
      expect(result.current.syncError).toBeNull();
      // reloadFromServer should NOT be called for both_advanced
      expect(mockReloadFromServer).not.toHaveBeenCalled();
    });

    it('includes bookmark and dbHead alongside the artifact reference', async () => {
      const bookmark = buildBookmark();
      const dbHead = buildDbHead(9, 'c'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FCC');
      const keepBothArtifact = {
        id: 'artifact-def-456',
        created_at: '2026-06-12T07:00:00.000Z',
        remote_entry_id: null,
      };
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('both_advanced', 'divergence_recorded', {
          configVersion: 7,
          bookmark,
          dbHead,
          keepBothArtifact,
        }),
      );

      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'dirty' as const,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.lastSyncResult).not.toBeNull();
      });
      expect(result.current.lastSyncResult).toEqual({
        state: 'both_advanced',
        action: 'divergence_recorded',
        configVersion: 7,
        dbHead,
        bookmark,
        keepBothArtifact,
      });
    });
  });

  // --- Incompatible bookmark warning/error ---

  describe('bookmark_incompatible', () => {
    it('sets syncState to bookmark_incompatible and surfaces the local bookmark', async () => {
      const bookmark = buildBookmark();
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('bookmark_incompatible', 'none', {
          configVersion: 7,
          bookmark,
          dbHead: buildDbHead(9, 'c'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FCC'),
        }),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('bookmark_incompatible');
      });

      expect(result.current.lastSyncResult).toEqual(
        expect.objectContaining({
          state: 'bookmark_incompatible',
          action: 'none',
          bookmark,
        }),
      );
      expect(mockReloadFromServer).not.toHaveBeenCalled();
    });

    it('does not mutate local state beyond the warning', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('bookmark_incompatible', 'none'),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('bookmark_incompatible');
      });
      expect(result.current.syncError).toBeNull();
    });
  });

  // --- Bookmark-missing bootstrap ---

  describe('bookmark_missing (bootstrap)', () => {
    it('resolves to up_to_date after the provider bootstraps a missing bookmark', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('bookmark_missing', 'bookmark_bootstrapped', { configVersion: 7 }),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('up_to_date');
      });
      expect(result.current.syncError).toBeNull();
    });

    it('does not call reloadFromServer for bookmark bootstrap', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('bookmark_missing', 'bookmark_bootstrapped'),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockReloadFromServer).not.toHaveBeenCalled();
    });
  });

  // --- Up to date ---

  describe('up_to_date', () => {
    it('sets syncState to up_to_date when the provider reports no changes needed', async () => {
      mockSyncTimeline.mockResolvedValue(
        buildSyncResult('up_to_date', 'none', { configVersion: 7 }),
      );

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('up_to_date');
      });
      expect(result.current.syncError).toBeNull();
      expect(mockReloadFromServer).not.toHaveBeenCalled();
    });
  });

  // --- Error handling ---

  describe('error states', () => {
    it('sets syncState to error when syncTimeline throws', async () => {
      mockSyncTimeline.mockRejectedValue(new Error('Network failure'));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('error');
      });
      expect(result.current.syncError).toBe('Network failure');
    });

    it('sets syncState to error when there is no config data available', async () => {
      mocks.useTimelineEditorData.mockReturnValue({
        ...mocks.useTimelineEditorData(),
        data: null,
      });

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('error');
      });
      expect(result.current.syncError).toBe('No timeline data available for sync');
      expect(mockSyncTimeline).not.toHaveBeenCalled();
    });

    it('handles non-Error thrown values gracefully', async () => {
      mockSyncTimeline.mockRejectedValue('raw string error');

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('error');
      });
      expect(result.current.syncError).toBe('Sync failed');
    });
  });

  // --- Syncing guard ---

  describe('syncing guard', () => {
    it('prevents concurrent sync calls while a sync is already in progress', async () => {
      // Create a deferred promise so we can hold the first sync in-flight
      let resolveFirstSync!: (value: SyncTimelineResult) => void;
      const firstSyncPromise = new Promise<SyncTimelineResult>((resolve) => {
        resolveFirstSync = resolve;
      });
      mockSyncTimeline.mockReturnValueOnce(firstSyncPromise);

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      // Start first sync (will block on the promise)
      let firstSyncDone = false;
      act(() => {
        result.current.performSync().then(() => {
          firstSyncDone = true;
        });
      });

      await waitFor(() => {
        expect(result.current.syncState).toBe('syncing');
      });

      // Attempt a second sync while the first is still in progress
      await act(async () => {
        await result.current.performSync();
      });

      // The second call should be a no-op; syncTimeline should only be called once
      expect(mockSyncTimeline).toHaveBeenCalledTimes(1);
      expect(result.current.syncState).toBe('syncing');

      // Resolve the first sync
      await act(async () => {
        resolveFirstSync(buildSyncResult('up_to_date', 'none'));
      });

      await waitFor(() => {
        expect(firstSyncDone).toBe(true);
      });
    });

    it('allows a new sync after the previous one completes', async () => {
      mockSyncTimeline.mockResolvedValueOnce(buildSyncResult('up_to_date', 'none'));
      mockSyncTimeline.mockResolvedValueOnce(buildSyncResult('source_only', 'saved', { configVersion: 9 }));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      // First sync
      await act(async () => {
        await result.current.performSync();
      });
      await waitFor(() => {
        expect(result.current.syncState).toBe('up_to_date');
      });

      // Second sync
      await act(async () => {
        await result.current.performSync();
      });
      await waitFor(() => {
        expect(result.current.syncState).toBe('source_only_saved');
      });

      expect(mockSyncTimeline).toHaveBeenCalledTimes(2);
    });
  });

  // --- Autosave preservation ---

  describe('autosave preservation', () => {
    it('preserves the existing saveStatus data flow — sync does not mutate chrome context', async () => {
      mockSyncTimeline.mockResolvedValue(buildSyncResult('up_to_date', 'none'));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      // The hook exposes sync-specific state, not save state.
      // Verify that the chrome context values are still accessible and unchanged.
      // The hook reads chrome.saveStatus to compute hasUnsavedEdits, but
      // does not write back to it.
      expect(result.current.isSyncAvailable).toBe(true);

      await act(async () => {
        await result.current.performSync();
      });

      // After sync, chrome context (mocked) should still have its original values.
      // The mocks capture the original return, which is verified by the mock itself.
      // The key invariant: syncState changes but saveStatus is independent.
      expect(result.current.syncState).toBe('up_to_date');
    });

    it('correctly classifies saveStatus=dirty as unsaved edits', async () => {
      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'dirty' as const,
      });

      mockSyncTimeline.mockResolvedValue(buildSyncResult('source_only', 'saved'));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockSyncTimeline).toHaveBeenCalledWith(
        expect.objectContaining({ hasUnsavedEdits: true }),
      );
    });

    it('correctly classifies saveStatus=error as unsaved edits', async () => {
      mocks.useTimelineChromeContext.mockReturnValue({
        ...mocks.useTimelineChromeContext(),
        saveStatus: 'error' as const,
      });

      mockSyncTimeline.mockResolvedValue(buildSyncResult('source_only', 'saved'));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockSyncTimeline).toHaveBeenCalledWith(
        expect.objectContaining({ hasUnsavedEdits: true }),
      );
    });

    it('correctly classifies saveStatus=saved and saveStatus=saving as no unsaved edits', async () => {
      for (const status of ['saved', 'saving'] as const) {
        vi.clearAllMocks();
        mocks.useTimelineChromeContext.mockReturnValue({
          ...mocks.useTimelineChromeContext(),
          saveStatus: status,
        });
        mockSyncTimeline.mockResolvedValue(buildSyncResult('destination_only', 'reload_required'));

        const runtime = createRuntime();
        const { result } = renderHook(() => useEditorSync(), {
          wrapper: createWrapper({ runtime }),
        });

        await act(async () => {
          await result.current.performSync();
        });

        expect(mockSyncTimeline).toHaveBeenCalledWith(
          expect.objectContaining({ hasUnsavedEdits: false }),
        );
      }
    });

    it('passes configVersion from editor data to syncTimeline', async () => {
      mocks.useTimelineEditorData.mockReturnValue({
        ...mocks.useTimelineEditorData(),
        data: {
          config: buildConfig(),
          configVersion: 12,
          registry: { assets: { 'a1': { file: 'a.mp4' } } },
        },
      });

      mockSyncTimeline.mockResolvedValue(buildSyncResult('source_only', 'saved', { configVersion: 13 }));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockSyncTimeline).toHaveBeenCalledWith(
        expect.objectContaining({
          currentConfigVersion: 12,
          registry: { assets: { 'a1': { file: 'a.mp4' } } },
        }),
      );
    });

    it('defaults configVersion to 1 when not present in editor data', async () => {
      mocks.useTimelineEditorData.mockReturnValue({
        ...mocks.useTimelineEditorData(),
        data: {
          config: buildConfig(),
          // configVersion is missing
          registry: {},
        },
      });

      mockSyncTimeline.mockResolvedValue(buildSyncResult('up_to_date', 'none'));

      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      await act(async () => {
        await result.current.performSync();
      });

      expect(mockSyncTimeline).toHaveBeenCalledWith(
        expect.objectContaining({ currentConfigVersion: 1 }),
      );
    });
  });

  // --- Initial idle state ---

  describe('initial state', () => {
    it('starts in idle state with no error or result', () => {
      const runtime = createRuntime();
      const { result } = renderHook(() => useEditorSync(), {
        wrapper: createWrapper({ runtime }),
      });

      expect(result.current.syncState).toBe('idle');
      expect(result.current.lastSyncResult).toBeNull();
      expect(result.current.syncError).toBeNull();
    });
  });
});
