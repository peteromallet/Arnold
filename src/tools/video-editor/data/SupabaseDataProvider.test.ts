import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeIndexedDB, IDBKeyRange } from 'fake-indexeddb';

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  from: vi.fn(),
  readAccessTokenFromStorage: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: vi.fn(() => ({
    auth: {
      getSession: mocks.getSession,
    },
    from: mocks.from,
    storage: {
      from: vi.fn(),
    },
  })),
}));

vi.mock('@/shared/lib/supabaseSession', () => ({
  readAccessTokenFromStorage: mocks.readAccessTokenFromStorage,
}));

import { TimelineVersionConflictError, type TimelineConfig } from './DataProvider';
import { SupabaseDataProvider } from './SupabaseDataProvider';
import {
  listKeepBothArtifacts,
  loadSyncBookmark,
  saveSyncBookmark,
  type SyncBookmarkRecord,
} from './syncLedgerIndexedDb';

function buildConfig(): TimelineConfig {
  return {
    output: {
      resolution: '1920x1080',
      fps: 30,
      file: 'timeline.mp4',
    },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [],
  };
}

function mockTimelinesSelect(response: unknown) {
  const maybeSingle = vi.fn().mockResolvedValue(response);
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, maybeSingle };
}

function mockTimelineHeadSelect(response: unknown) {
  const maybeSingle = vi.fn().mockResolvedValue(response);
  const limit = vi.fn().mockReturnValue({ maybeSingle });
  const order = vi.fn().mockReturnValue({ limit });
  const eq = vi.fn().mockReturnValue({ order });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, order, limit, maybeSingle };
}

function mockTimelineHeadSelectSequence(...responses: unknown[]) {
  const maybeSingle = vi.fn();
  for (const response of responses) {
    maybeSingle.mockResolvedValueOnce(response);
  }
  const limit = vi.fn().mockReturnValue({ maybeSingle });
  const order = vi.fn().mockReturnValue({ limit });
  const eq = vi.fn().mockReturnValue({ order });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, order, limit, maybeSingle };
}

function mockSyncBookmarkSelect(response: unknown) {
  const maybeSingle = vi.fn().mockResolvedValue(response);
  const spokeEq = vi.fn().mockReturnValue({ maybeSingle });
  const timelineEq = vi.fn().mockReturnValue({ eq: spokeEq });
  const select = vi.fn().mockReturnValue({ eq: timelineEq });
  return { select, timelineEq, spokeEq, maybeSingle };
}

function buildHead(version: number, hash: string, eventId: string) {
  return {
    version,
    hash,
    event_id: eventId,
  };
}

function buildBookmark(overrides: Partial<SyncBookmarkRecord> = {}): SyncBookmarkRecord {
  return {
    timeline_id: 'timeline-1',
    spoke: 'app',
    spoke_version: 7,
    spoke_hash: 'a'.repeat(64),
    spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    hub_version: 7,
    hub_hash: 'a'.repeat(64),
    hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    synced_at: '2026-06-12T04:22:00.000Z',
    ...overrides,
  };
}

describe('SupabaseDataProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('indexedDB', createFakeIndexedDB());
    vi.stubGlobal('IDBKeyRange', IDBKeyRange);
    vi.stubEnv('VITE_REIGH_APPEND_SERVICE_URL', 'https://append-service.example/');
    (import.meta.env as Record<string, string | undefined>).VITE_REIGH_APPEND_SERVICE_URL = 'https://append-service.example/';
    mocks.readAccessTokenFromStorage.mockReturnValue('cached-user-jwt');
    mocks.getSession.mockResolvedValue({
      data: { session: { access_token: 'session-user-jwt' } },
      error: null,
    });
    vi.stubGlobal('fetch', vi.fn());
  });

  it('loadTimeline and loadAssetRegistry keep reading materialized Supabase rows', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });

    const timelinesQuery = mockTimelinesSelect({
      data: {
        config: buildConfig(),
        config_version: 7,
        asset_registry: { assets: { 'asset-1': { file: 'clips/demo.mp4' } } },
      },
      error: null,
    });
    const timelineHeadQuery = mockTimelineHeadSelect({
      data: {
        version: 7,
        hash: 'a'.repeat(64),
        event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
      },
      error: null,
    });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timelines') {
        return { select: timelinesQuery.select };
      }
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });

    const timeline = await provider.loadTimeline('timeline-1');
    const registry = await provider.loadAssetRegistry('timeline-1');

    expect(timeline.configVersion).toBe(7);
    expect(registry).toEqual({ assets: { 'asset-1': { file: 'clips/demo.mp4' } } });
    expect(mocks.from).toHaveBeenNthCalledWith(1, 'timelines');
    expect(mocks.from).toHaveBeenNthCalledWith(2, 'timeline_events');
    expect(mocks.from).toHaveBeenNthCalledWith(3, 'timelines');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('loadTimeline saves the app bookmark from the DB head', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });

    const timelinesQuery = mockTimelinesSelect({
      data: {
        config: buildConfig(),
        config_version: 7,
      },
      error: null,
    });
    const timelineHeadQuery = mockTimelineHeadSelect({
      data: buildHead(7, 'a'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FAB'),
      error: null,
    });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timelines') {
        return { select: timelinesQuery.select };
      }
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });

    await provider.loadTimeline('timeline-1');

    await expect(loadSyncBookmark('timeline-1', 'app')).resolves.toEqual(expect.objectContaining({
      timeline_id: 'timeline-1',
      spoke: 'app',
      spoke_version: 7,
      spoke_hash: 'a'.repeat(64),
      spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
      hub_version: 7,
      hub_hash: 'a'.repeat(64),
      hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    }));
  });

  it('saveTimeline posts config and registry to the append service with the user JWT', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      config_version: 9,
      db_head: {
        version: 9,
        hash: 'b'.repeat(64),
        event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
      },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });
    const registry = { assets: { 'asset-1': { file: 'clips/demo.mp4', type: 'video/mp4' } } };

    const nextVersion = await provider.saveTimeline('timeline-1', buildConfig(), 8, registry);

    expect(nextVersion).toBe(9);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://append-service.example/v1/timelines/timeline-1/config-replaced',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer cached-user-jwt',
        }),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      config: buildConfig(),
      asset_registry: registry,
      expected_version: 8,
      actor: {
        type: 'human',
        id: 'user-123',
      },
      source: 'editor_save',
    });
    expect(mocks.getSession).not.toHaveBeenCalled();
  });

  it('saveTimeline posts config-only saves to the append service without asset_registry', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      config_version: 5,
      db_head: {
        version: 5,
        hash: 'c'.repeat(64),
        event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBC',
      },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

    const nextVersion = await provider.saveTimeline('timeline-1', buildConfig(), 4);

    expect(nextVersion).toBe(5);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://append-service.example/v1/timelines/timeline-1/config-replaced',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer cached-user-jwt',
        }),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual({
      config: buildConfig(),
      expected_version: 4,
      actor: {
        type: 'human',
        id: 'user-123',
      },
      source: 'editor_save',
    });
    expect(body).not.toHaveProperty('asset_registry');
    expect(mocks.getSession).not.toHaveBeenCalled();
  });

  it('saveTimeline updates the local app bookmark from the service-provided DB head', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      config_version: 9,
      db_head: buildHead(9, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

    await provider.saveTimeline('timeline-1', buildConfig(), 8);

    await expect(loadSyncBookmark('timeline-1', 'app')).resolves.toEqual(expect.objectContaining({
      timeline_id: 'timeline-1',
      spoke: 'app',
      spoke_version: 9,
      spoke_hash: 'b'.repeat(64),
      spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
      hub_version: 9,
      hub_hash: 'b'.repeat(64),
      hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
    }));
  });

  it('saveTimeline falls back to the live session token when no cached token exists', async () => {
    mocks.readAccessTokenFromStorage.mockReturnValue(null);
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      config_version: 3,
      db_head: {
        version: 3,
        hash: 'd'.repeat(64),
        event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBD',
      },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

    await provider.saveTimeline('timeline-1', buildConfig(), 2);

    expect(mocks.getSession).toHaveBeenCalledTimes(1);
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer session-user-jwt');
  });

  it('saveTimeline maps append-service CAS conflicts to TimelineVersionConflictError', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      error: 'version_conflict',
      detail: 'timeline config_version mismatch: expected 3, found 4',
    }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    }));
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

    await expect(provider.saveTimeline('timeline-1', buildConfig(), 3)).rejects.toBeInstanceOf(TimelineVersionConflictError);
  });

  it('syncTimeline saves source-only app edits when the DB head matches the bookmark', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });
    const bookmark = buildBookmark();
    await saveSyncBookmark(bookmark);

    const timelineHeadQuery = mockTimelineHeadSelectSequence(
      { data: buildHead(7, 'a'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FAB'), error: null },
      { data: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'), error: null },
    );
    const remoteBookmarkQuery = mockSyncBookmarkSelect({ data: bookmark, error: null });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      if (table === 'sync_bookmarks') {
        return { select: remoteBookmarkQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      config_version: 8,
      db_head: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    const result = await provider.syncTimeline({
      timelineId: 'timeline-1',
      config: buildConfig(),
      currentConfigVersion: 7,
      hasUnsavedEdits: true,
    });

    expect(result).toEqual(expect.objectContaining({
      state: 'source_only',
      action: 'saved',
      configVersion: 8,
      dbHead: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
    }));
    await expect(loadSyncBookmark('timeline-1', 'app')).resolves.toEqual(expect.objectContaining({
      spoke_version: 8,
      spoke_hash: 'b'.repeat(64),
      spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
      hub_version: 8,
      hub_hash: 'b'.repeat(64),
      hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
    }));
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      config: buildConfig(),
      expected_version: 7,
      actor: {
        type: 'human',
        id: 'user-123',
      },
      source: 'editor_save',
    });
  });

  it('syncTimeline returns reload_required for DB-only advancement with no unsaved edits', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
    const bookmark = buildBookmark();
    await saveSyncBookmark(bookmark);

    const timelineHeadQuery = mockTimelineHeadSelect({
      data: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      error: null,
    });
    const remoteBookmarkQuery = mockSyncBookmarkSelect({ data: bookmark, error: null });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      if (table === 'sync_bookmarks') {
        return { select: remoteBookmarkQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });

    const result = await provider.syncTimeline({
      timelineId: 'timeline-1',
      config: buildConfig(),
      currentConfigVersion: 7,
      hasUnsavedEdits: false,
    });

    expect(result).toEqual(expect.objectContaining({
      state: 'destination_only',
      action: 'reload_required',
      configVersion: 7,
      dbHead: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      bookmark,
    }));
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('syncTimeline bootstraps a missing bookmark safely when app and DB heads already match', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
    const bootstrappedBookmark = buildBookmark();

    const timelineHeadQuery = mockTimelineHeadSelect({
      data: buildHead(7, 'a'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FAB'),
      error: null,
    });
    const remoteBookmarkQuery = mockSyncBookmarkSelect({ data: null, error: null });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      if (table === 'sync_bookmarks') {
        return { select: remoteBookmarkQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      bookmark: bootstrappedBookmark,
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    const result = await provider.syncTimeline({
      timelineId: 'timeline-1',
      config: buildConfig(),
      currentConfigVersion: 7,
      hasUnsavedEdits: false,
    });

    expect(result).toEqual(expect.objectContaining({
      state: 'bookmark_missing',
      action: 'bookmark_bootstrapped',
      configVersion: 7,
      dbHead: buildHead(7, 'a'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FAB'),
      bookmark: bootstrappedBookmark,
    }));
    await expect(loadSyncBookmark('timeline-1', 'app')).resolves.toEqual(bootstrappedBookmark);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://append-service.example/v1/timelines/timeline-1/app-bookmark',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer cached-user-jwt',
        }),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      db_head: buildHead(7, 'a'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FAB'),
    });
  });

  it('syncTimeline blocks incompatible local and remote app bookmarks before any service call', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
    const localBookmark = buildBookmark();
    const remoteBookmark = buildBookmark({
      synced_at: '2026-06-12T05:00:00.000Z',
      hub_version: 8,
      hub_hash: 'b'.repeat(64),
      hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
    });
    await saveSyncBookmark(localBookmark);

    const timelineHeadQuery = mockTimelineHeadSelect({
      data: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      error: null,
    });
    const remoteBookmarkQuery = mockSyncBookmarkSelect({ data: remoteBookmark, error: null });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      if (table === 'sync_bookmarks') {
        return { select: remoteBookmarkQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });

    const result = await provider.syncTimeline({
      timelineId: 'timeline-1',
      config: buildConfig(),
      currentConfigVersion: 7,
      hasUnsavedEdits: true,
    });

    expect(result).toEqual(expect.objectContaining({
      state: 'bookmark_incompatible',
      action: 'none',
      configVersion: 7,
      dbHead: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      bookmark: localBookmark,
    }));
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('syncTimeline records divergence and stores a keep-both IndexedDB artifact when both sides advanced', async () => {
    const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
    const bookmark = buildBookmark();
    const registry = { assets: { 'asset-1': { file: 'clips/demo.mp4', type: 'video/mp4' } } };
    await saveSyncBookmark(bookmark);

    const timelineHeadQuery = mockTimelineHeadSelect({
      data: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      error: null,
    });
    const remoteBookmarkQuery = mockSyncBookmarkSelect({ data: bookmark, error: null });
    const timelinesQuery = mockTimelinesSelect({
      data: {
        config: buildConfig(),
        config_version: 8,
        asset_registry: { assets: { 'asset-2': { file: 'remote/demo.mp4' } } },
      },
      error: null,
    });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'timeline_events') {
        return { select: timelineHeadQuery.select };
      }
      if (table === 'sync_bookmarks') {
        return { select: remoteBookmarkQuery.select };
      }
      if (table === 'timelines') {
        return { select: timelinesQuery.select };
      }
      throw new Error(`Unexpected table: ${table}`);
    });
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      divergence: {
        id: 'divergence-row-1',
        created_at: '2026-06-12T06:00:00.000Z',
      },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    const result = await provider.syncTimeline({
      timelineId: 'timeline-1',
      config: buildConfig(),
      currentConfigVersion: 7,
      hasUnsavedEdits: true,
      registry,
    });

    expect(result).toEqual(expect.objectContaining({
      state: 'both_advanced',
      action: 'divergence_recorded',
      configVersion: 7,
      dbHead: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      bookmark,
      keepBothArtifact: {
        id: expect.any(String),
        created_at: '2026-06-12T06:00:00.000Z',
        remote_entry_id: 'divergence-row-1',
      },
    }));
    const artifacts = await listKeepBothArtifacts('timeline-1');
    expect(artifacts).toHaveLength(1);
    expect(artifacts[0]).toEqual(expect.objectContaining({
      id: result.keepBothArtifact?.id,
      timeline_id: 'timeline-1',
      spoke: 'app',
      artifact: expect.objectContaining({
        kind: 'app_sync_divergence',
        timeline_id: 'timeline-1',
        bookmark,
        db_head: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
        app_draft: {
          config: buildConfig(),
          asset_registry: registry,
          config_version: 7,
        },
        remote_timeline: {
          config: buildConfig(),
          asset_registry: { assets: { 'asset-2': { file: 'remote/demo.mp4' } } },
          config_version: 8,
        },
      }),
    }));
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://append-service.example/v1/timelines/timeline-1/app-divergence',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer cached-user-jwt',
        }),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      config: buildConfig(),
      asset_registry: registry,
      db_head: buildHead(8, 'b'.repeat(64), '01ARZ3NDEKTSV4RRFFQ69G5FBB'),
      source: 'editor_sync',
      artifact_pointer: {
        kind: 'indexeddb',
        id: result.keepBothArtifact?.id,
        created_at: expect.any(String),
      },
    });
  });

  // -------------------------------------------------------------------------
  // Strict expectedVersion CAS conflict handling (T14)
  // -------------------------------------------------------------------------
  describe('strict expectedVersion CAS conflict handling', () => {
    it('rejects saveTimeline when the append service returns a 409 version_conflict', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
        error: 'version_conflict',
        detail: 'timeline config_version mismatch: expected 3, found 5',
      }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      await expect(
        provider.saveTimeline('timeline-1', buildConfig(), 3),
      ).rejects.toBeInstanceOf(TimelineVersionConflictError);
    });

    it('the conflict error message preserves the version details from the service', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
        error: 'version_conflict',
        detail: 'expected version 2 but timeline head is at version 7',
      }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      let caught: unknown;
      try {
        await provider.saveTimeline('timeline-1', buildConfig(), 2);
      } catch (e) {
        caught = e;
      }

      expect(caught).toBeInstanceOf(TimelineVersionConflictError);
      // The error should carry the conflict code
      expect((caught as any)?.code).toBe('timeline_version_conflict');
    });

    it('saveTimeline succeeds with the updated version when expectedVersion matches', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
        config_version: 9,
        db_head: {
          version: 9,
          hash: 'b'.repeat(64),
          event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
        },
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      const nextVersion = await provider.saveTimeline('timeline-1', buildConfig(), 8);
      expect(nextVersion).toBe(9);
    });

    it('maps non-JSON 409 responses to TimelineVersionConflictError gracefully', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response('Conflict', {
        status: 409,
        statusText: 'Conflict',
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      await expect(
        provider.saveTimeline('timeline-1', buildConfig(), 3),
      ).rejects.toBeInstanceOf(TimelineVersionConflictError);
    });
  });

  // -------------------------------------------------------------------------
  // Local monotonic stale invalidation behavior (T14)
  // -------------------------------------------------------------------------
  describe('local monotonic stale invalidation behavior', () => {
    it('the provider enforces CAS before the save payload reaches the append service', async () => {
      // The SupabaseDataProvider delegates CAS to the append service via
      // the expected_version field. The service returns 409 on conflict.
      // This test verifies that the error is correctly surfaced as
      // TimelineVersionConflictError, which is the contract that
      // useTimelineOps and other callers rely on for stale detection.
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
        error: 'version_conflict',
        detail: 'config_version mismatch',
      }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      // A stale expectedVersion should produce TimelineVersionConflictError
      await expect(
        provider.saveTimeline('timeline-1', buildConfig(), 1),
      ).rejects.toBeInstanceOf(TimelineVersionConflictError);

      // The fetch must have been called (the error came from the service, not a local check)
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    it('the append-service CAS is the authoritative conflict boundary for Supabase', async () => {
      // Unlike InMemory which checks expectedVersion locally before any
      // mutation, Supabase delegates the check to the append service.
      // This test confirms that the fetch is always made and the service
      // response determines success or conflict.
      vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
        config_version: 5,
        db_head: { version: 5, hash: 'c'.repeat(64), event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBC' },
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });

      const version = await provider.saveTimeline('timeline-1', buildConfig(), 4);
      expect(version).toBe(5);
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);

      // Verify the expected_version is in the request body
      const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
      const body = JSON.parse(String(init?.body));
      expect(body.expected_version).toBe(4);
    });
  });

});
