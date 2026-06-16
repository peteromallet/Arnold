import { useCallback, useContext, useRef, useState } from 'react';
import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { useTimelineEditorData } from '@/tools/video-editor/hooks/timelineStore.ts';
import { useTimelineChromeContext } from '@/tools/video-editor/hooks/timelineStore.ts';
import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider.ts';
import type { SyncTimelineResult } from '@/tools/video-editor/data/SupabaseDataProvider.ts';

export type EditorSyncState =
  | 'idle'
  | 'syncing'
  | 'up_to_date'
  | 'source_only_saved'
  | 'destination_only_reloaded'
  | 'both_advanced'
  | 'bookmark_incompatible'
  | 'error';

export interface EditorSyncResult {
  state: EditorSyncState;
  lastResult: SyncTimelineResult | null;
  error: string | null;
}

/**
 * Thin hook that wraps the provider sync method behind an editor-shell-friendly
 * contract.  All protocol-level decisions about head comparison, bookmark
 * bootstrap, and divergence recording remain inside {@link SupabaseDataProvider}.
 *
 * The hook returns `isSyncAvailable: false` whenever the provider is not a
 * {@link SupabaseDataProvider} or when the runtime context is unavailable
 * (e.g. in isolated unit tests that render the shell without the full app
 * provider tree).
 */
export function useEditorSync(): {
  isSyncAvailable: boolean;
  syncState: EditorSyncState;
  lastSyncResult: SyncTimelineResult | null;
  syncError: string | null;
  performSync: () => Promise<void>;
} {
  const runtime = useContext(DataProviderContext);
  const editorData = useTimelineEditorData();
  const chrome = useTimelineChromeContext();

  if (!runtime) {
    return {
      isSyncAvailable: false,
      syncState: 'idle',
      lastSyncResult: null,
      syncError: null,
      performSync: async () => {},
    };
  }

  const provider = runtime.provider;
  const isSyncAvailable = provider instanceof SupabaseDataProvider;

  const [syncState, setSyncState] = useState<EditorSyncState>('idle');
  const [lastSyncResult, setLastSyncResult] = useState<SyncTimelineResult | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const syncingRef = useRef(false);

  const performSync = useCallback(async () => {
    if (!isSyncAvailable || syncingRef.current) {
      return;
    }

    const supabaseProvider = provider as SupabaseDataProvider;
    const timelineId = runtime.timelineId;
    const config = editorData.data?.config;
    const configVersion = editorData.data?.configVersion ?? 1;
    const registry = editorData.data?.registry;
    const hasUnsavedEdits = chrome.saveStatus === 'dirty' || chrome.saveStatus === 'error';

    if (!config) {
      setSyncState('error');
      setSyncError('No timeline data available for sync');
      return;
    }

    syncingRef.current = true;
    setSyncState('syncing');
    setSyncError(null);
    setLastSyncResult(null);

    try {
      const result = await supabaseProvider.syncTimeline({
        timelineId,
        config,
        currentConfigVersion: configVersion,
        hasUnsavedEdits,
        registry,
      });

      setLastSyncResult(result);

      switch (result.state) {
        case 'up_to_date':
          setSyncState('up_to_date');
          break;
        case 'source_only':
          setSyncState('source_only_saved');
          // The sync already saved the data; reload to refresh local state
          await chrome.reloadFromServer();
          break;
        case 'destination_only':
          if (hasUnsavedEdits) {
            // syncTimeline only returns destination_only when no unsaved edits
            setSyncState('error');
            setSyncError('Unexpected: destination-only with unsaved edits');
          } else {
            // Reload through existing query paths to get latest DB version
            await chrome.reloadFromServer();
            setSyncState('destination_only_reloaded');
          }
          break;
        case 'both_advanced':
          setSyncState('both_advanced');
          break;
        case 'bookmark_missing':
          // bootstrap handled internally by the provider
          setSyncState('up_to_date');
          break;
        case 'bookmark_incompatible':
          setSyncState('bookmark_incompatible');
          break;
        default:
          setSyncState('up_to_date');
      }
    } catch (error) {
      setSyncState('error');
      setSyncError(error instanceof Error ? error.message : 'Sync failed');
    } finally {
      syncingRef.current = false;
    }
  }, [isSyncAvailable, provider, runtime.timelineId, editorData.data, chrome]);

  return {
    isSyncAvailable,
    syncState,
    lastSyncResult,
    syncError,
    performSync,
  };
}
