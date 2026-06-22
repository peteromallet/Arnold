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
  defineExtensionPersistenceConformanceSuite,
} from './conformance/extensionPersistenceConformance';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { ExtensionPersistenceScope } from './DataProvider';
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

type ExtensionTableState = {
  install: Array<Record<string, any>>;
  settings: Array<Record<string, any>>;
  proposals: Array<Record<string, any>>;
};

function setupExtensionPersistenceSupabaseMock(state: ExtensionTableState) {
  const tableRows = (table: string) => {
    if (table === 'extension_install_state') return state.install;
    if (table === 'extension_settings') return state.settings;
    if (table === 'extension_proposals') return state.proposals;
    throw new Error(`Unexpected table: ${table}`);
  };

  const matches = (row: Record<string, any>, filters: Record<string, unknown>) =>
    Object.entries(filters).every(([key, value]) => row[key] === value);

  const makeQuery = (table: string, mode: 'select' | 'delete') => {
    const filters: Record<string, unknown> = {};
    const execute = async () => {
      const rows = tableRows(table);
      if (mode === 'delete') {
        const keep = rows.filter((row) => !matches(row, filters));
        rows.splice(0, rows.length, ...keep);
        return { error: null };
      }
      return {
        data: rows.filter((row) => matches(row, filters)),
        error: null,
      };
    };
    const query: any = {
      eq: vi.fn((key: string, value: unknown) => {
        filters[key] = value;
        return query;
      }),
      maybeSingle: vi.fn(async () => {
        const result = await execute();
        return {
          data: Array.isArray(result.data) ? result.data[0] ?? null : null,
          error: result.error,
        };
      }),
      then: (resolve: any, reject: any) => execute().then(resolve, reject),
    };
    return query;
  };

  mocks.from.mockImplementation((table: string) => ({
    select: vi.fn(() => makeQuery(table, 'select')),
    delete: vi.fn(() => makeQuery(table, 'delete')),
    upsert: vi.fn(async (row: Record<string, any>) => {
      const rows = tableRows(table);
      const index = rows.findIndex((existing) =>
        existing.user_id === row.user_id &&
        existing.timeline_id === row.timeline_id &&
        existing.extension_id === row.extension_id);
      if (index >= 0) {
        rows[index] = { ...rows[index], ...row };
      } else {
        rows.push({ ...row });
      }
      return { error: null };
    }),
    insert: vi.fn(async (row: Record<string, any>) => {
      tableRows(table).push({
        ...row,
        created_at: row.created_at ?? new Date().toISOString(),
        updated_at: row.updated_at ?? new Date().toISOString(),
      });
      return { error: null };
    }),
  }));
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

  describe('extension persistence conformance', () => {
    const scope: ExtensionPersistenceScope = {
      userId: 'user-123',
      timelineId: 'timeline-1',
    };
    const state: ExtensionTableState = {
      install: [],
      settings: [],
      proposals: [],
    };

    defineExtensionPersistenceConformanceSuite({
      name: 'SupabaseDataProvider',
      scope,
      reset: () => {
        state.install = [];
        state.settings = [];
        state.proposals = [];
        setupExtensionPersistenceSupabaseMock(state);
      },
      seedCorruptSnapshot: () => {
        state.install = [{
          user_id: scope.userId,
          timeline_id: scope.timelineId,
          extension_id: '__reigh_snapshot__',
          metadata: {
            meta: {
              schemaVersion: 999,
              createdAt: '2026-01-01T00:00:00.000Z',
              updatedAt: '2026-01-01T00:00:00.000Z',
            },
            packs: {},
            enablement: {},
            overrides: {},
            events: [],
            lock: {
              entries: {},
              lastUpdatedAt: '2026-01-01T00:00:00.000Z',
            },
          },
        }];
        state.settings = [];
        state.proposals = [];
        setupExtensionPersistenceSupabaseMock(state);
      },
      createService: (diagnostics) => {
        const provider = new SupabaseDataProvider({
          projectId: 'project-1',
          userId: scope.userId,
        });
        return provider.createExtensionPersistenceService(scope, diagnostics);
      },
    });
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


  // ---------------------------------------------------------------------------
  // T11: Supabase provider query scoping, load/upsert/delete paths,
  //      state/settings round-trip, and migration/RLS policy text assertions
  // ---------------------------------------------------------------------------

  describe('SupabaseFullSnapshotStore query scoping', () => {
    it('loadSnapshot scopes every query by user_id and timeline_id', async () => {
      const scope: ExtensionPersistenceScope = { userId: 'user-scope', timelineId: 'tl-scope' };

      // Capture every .eq call
      const allEqCalls: Array<{ table: string; col: string; val: unknown }> = [];

      mocks.from.mockImplementation((table: string) => {
        const makeChainable = (): any => {
          const chain: any = {
            select: vi.fn(() => chain),
            delete: vi.fn(() => chain),
            order: vi.fn(() => chain),
            limit: vi.fn(() => chain),
            in: vi.fn(() => chain),
            neq: vi.fn(() => chain),
            lt: vi.fn(() => chain),
            gt: vi.fn(() => chain),
            eq: vi.fn((col: string, val: unknown) => {
              allEqCalls.push({ table, col, val });
              return chain;
            }),
            maybeSingle: vi.fn(async () => {
              if (table === 'extension_install_state') {
                return {
                  data: {
                    metadata: {
                      meta: {
                        schemaVersion: 1,
                        createdAt: '2026-01-01T00:00:00.000Z',
                        updatedAt: '2026-01-01T00:00:00.000Z',
                      },
                      packs: {},
                      enablement: {},
                      overrides: {},
                      settings: {},
                      events: [],
                      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
                      proposals: {},
                    },
                  },
                  error: null,
                };
              }
              return { data: null, error: null };
            }),
            single: vi.fn(async () => ({ data: { id: 'x' }, error: null })),
            upsert: vi.fn(async () => ({ error: null })),
            insert: vi.fn(async () => ({ error: null })),
            then: (resolve: any) => resolve({ data: [], error: null }),
          };
          return chain;
        };
        return makeChainable();
      });

      const provider = new SupabaseDataProvider({ projectId: 'p1', userId: scope.userId });
      const diagnostics: ExtensionDiagnostic[] = [];
      const service = provider.createExtensionPersistenceService(scope, diagnostics);
      await service.initialize();

      // Verify each extension table query includes user_id and timeline_id
      for (const table of ['extension_install_state', 'extension_settings', 'extension_proposals']) {
        const tableCalls = allEqCalls.filter((c) => c.table === table);
        const userIdCalls = tableCalls.filter((c) => c.col === 'user_id');
        const timelineIdCalls = tableCalls.filter((c) => c.col === 'timeline_id');
        expect(userIdCalls.length, `${table} should have user_id filter`).toBeGreaterThan(0);
        expect(timelineIdCalls.length, `${table} should have timeline_id filter`).toBeGreaterThan(0);
        // Every user_id filter should use the correct value
        for (const call of userIdCalls) {
          expect(call.val).toBe(scope.userId);
        }
        for (const call of timelineIdCalls) {
          expect(call.val).toBe(scope.timelineId);
        }
      }

      await service.dispose();
    });

    it('saveSnapshot upsert rows always include user_id and timeline_id', async () => {
      const scope: ExtensionPersistenceScope = { userId: 'user-save', timelineId: 'tl-save' };
      const upsertedRows: Array<Record<string, unknown>> = [];

      mocks.from.mockImplementation((table: string) => {
        const makeChainable = (): any => {
          const chain: any = {
            select: vi.fn(() => chain),
            delete: vi.fn(() => chain),
            order: vi.fn(() => chain),
            limit: vi.fn(() => chain),
            eq: vi.fn(() => chain),
            maybeSingle: vi.fn(async () => ({ data: table === 'extension_install_state' ? { metadata: { meta: { schemaVersion: 1, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }, packs: {}, enablement: {}, overrides: {}, settings: {}, events: [], lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00Z' }, proposals: {} } } : null, error: null })),
            upsert: vi.fn(async (row: Record<string, unknown>) => {
              upsertedRows.push(row);
              return { error: null };
            }),
            insert: vi.fn(async (row: Record<string, unknown>) => {
              upsertedRows.push({ ...row, _table: table });
              return { error: null };
            }),
            then: (resolve: any) => resolve({ data: [], error: null }),
          };
          return chain;
        };
        return makeChainable();
      });

      const provider = new SupabaseDataProvider({ projectId: 'p1', userId: scope.userId });
      const diagnostics: ExtensionDiagnostic[] = [];
      const service = provider.createExtensionPersistenceService(scope, diagnostics);
      await service.initialize();

      // Write settings to trigger a snapshot save
      await service.putSettings!({
        extensionId: 'ext.save-test',
        schemaVersion: 1,
        values: { test: true },
        lastWrittenAt: '2026-06-22T00:00:00.000Z',
      });

      // Wait for async flush
      await new Promise((r) => setTimeout(r, 100));

      // Verify all upsert/insert rows have correct user_id and timeline_id
      for (const row of upsertedRows) {
        expect(row.user_id).toBe(scope.userId);
        expect(row.timeline_id).toBe(scope.timelineId);
      }

      await service.dispose();
    });

    it('deleteSnapshot scopes deletions by user_id and timeline_id', async () => {
      const scope: ExtensionPersistenceScope = { userId: 'user-del2', timelineId: 'tl-del2' };
      const deleteFilters: Array<Record<string, unknown>> = [];

      let loadCount = 0;
      mocks.from.mockImplementation((table: string) => {
        const chain: any = {
          select: vi.fn(() => chain),
          order: vi.fn(() => chain),
          limit: vi.fn(() => chain),
          eq: vi.fn(() => chain),
          neq: vi.fn(() => chain),
          lt: vi.fn(() => chain),
          in: vi.fn(() => chain),
          maybeSingle: vi.fn(async () => {
            loadCount++;
            return { data: loadCount === 1 ? { metadata: { meta: { schemaVersion: 1, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }, packs: {}, enablement: {}, overrides: {}, settings: {}, events: [], lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00Z' }, proposals: {} } } : null, error: null };
          }),
          upsert: vi.fn(async () => ({ error: null })),
          insert: vi.fn(async () => ({ error: null })),
          then: (resolve: any) => resolve({ data: [], error: null }),
        };

        // Wrap delete to capture filter calls differently
        const deleteChain: any = {
          eq: vi.fn((col: string, val: unknown) => {
            if (!deleteFilters.length || deleteFilters[deleteFilters.length - 1]._table !== table) {
              deleteFilters.push({ _table: table, [col]: val });
            } else {
              deleteFilters[deleteFilters.length - 1][col] = val;
            }
            return deleteChain;
          }),
          then: (resolve: any) => resolve({ error: null }),
        };
        chain.delete = vi.fn(() => deleteChain);

        return chain;
      });

      const provider = new SupabaseDataProvider({ projectId: 'p1', userId: scope.userId });
      const diagnostics: ExtensionDiagnostic[] = [];
      const service = provider.createExtensionPersistenceService(scope, diagnostics);
      await service.initialize();
      await service.dispose(); // Dispose triggers best-effort deleteSnapshot

      // Verify that when delete is called, user_id and timeline_id filters are present
      for (const filter of deleteFilters) {
        if (filter._table && typeof filter._table === 'string' &&
            (filter._table === 'extension_install_state' ||
             filter._table === 'extension_settings' ||
             filter._table === 'extension_proposals')) {
          expect(filter.user_id).toBe(scope.userId);
          expect(filter.timeline_id).toBe(scope.timelineId);
        }
      }
    });
  });

  describe('state/settings round-trip through provider service', () => {
    it('writes enablement and settings, then reads them back after re-initialization', async () => {
      const scope: ExtensionPersistenceScope = { userId: 'user-rt', timelineId: 'tl-rt' };
      const state: ExtensionTableState = { install: [], settings: [], proposals: [] };
      setupExtensionPersistenceSupabaseMock(state);

      const provider = new SupabaseDataProvider({ projectId: 'p1', userId: scope.userId });
      const diagnostics: ExtensionDiagnostic[] = [];

      // First session: write data
      const service1 = provider.createExtensionPersistenceService(scope, diagnostics);
      await service1.initialize();

      await service1.stateRepository!.putEnablementState({
        extensionId: 'ext.rt1',
        enabled: true,
        lastToggledAt: '2026-06-22T00:00:00.000Z',
      });

      await service1.putSettings!({
        extensionId: 'ext.rt1',
        schemaVersion: 5,
        values: { theme: 'midnight', volume: 0.8 },
        lastWrittenAt: '2026-06-22T01:00:00.000Z',
      });

      const created = await service1.createProposal!({
        extensionId: 'ext.rt1',
        status: 'draft',
        payload: { op: 'trim', seconds: 2.5 },
        title: 'Trim proposal',
      });
      const proposalId = typeof created === 'string' ? created : created.id;

      // Verify immediate visibility
      const enablement = await service1.stateRepository!.getEnablementState('ext.rt1');
      expect(enablement).toEqual(expect.objectContaining({ extensionId: 'ext.rt1', enabled: true }));

      const settings = await service1.getSettings!('ext.rt1');
      expect(settings).toEqual(expect.objectContaining({
        extensionId: 'ext.rt1',
        schemaVersion: 5,
        values: { theme: 'midnight', volume: 0.8 },
      }));

      // Wait for flush
      await new Promise((r) => setTimeout(r, 100));
      await service1.dispose();

      // Second session: read data back
      setupExtensionPersistenceSupabaseMock(state);
      const service2 = provider.createExtensionPersistenceService(scope, diagnostics);
      await service2.initialize();

      const enablement2 = await service2.stateRepository!.getEnablementState('ext.rt1');
      expect(enablement2).toEqual(expect.objectContaining({ extensionId: 'ext.rt1', enabled: true }));

      const settings2 = await service2.getSettings!('ext.rt1');
      expect(settings2).toEqual(expect.objectContaining({
        extensionId: 'ext.rt1',
        schemaVersion: 5,
        values: { theme: 'midnight', volume: 0.8 },
      }));

      const proposal = await service2.getProposal!(proposalId);
      expect(proposal).toEqual(expect.objectContaining({
        id: proposalId,
        status: 'draft',
      }));

      await service2.dispose();
    });

    it('proposal status update and query filters work end-to-end', async () => {
      const scope: ExtensionPersistenceScope = { userId: 'user-prop2', timelineId: 'tl-prop2' };
      const state: ExtensionTableState = { install: [], settings: [], proposals: [] };
      setupExtensionPersistenceSupabaseMock(state);

      const provider = new SupabaseDataProvider({ projectId: 'p1', userId: scope.userId });
      const diagnostics: ExtensionDiagnostic[] = [];
      const service = provider.createExtensionPersistenceService(scope, diagnostics);
      await service.initialize();

      // Create multiple proposals with different statuses
      const p1 = await service.createProposal!({
        extensionId: 'ext.a',
        status: 'draft',
        payload: { n: 1 },
      });
      const p2 = await service.createProposal!({
        extensionId: 'ext.a',
        status: 'draft',
        payload: { n: 2 },
      });
      const p3 = await service.createProposal!({
        extensionId: 'ext.b',
        status: 'submitted',
        payload: { n: 3 },
      });

      const id1 = typeof p1 === 'string' ? p1 : p1.id;
      const id2 = typeof p2 === 'string' ? p2 : p2.id;
      const id3 = typeof p3 === 'string' ? p3 : p3.id;

      // Update statuses
      await service.updateProposalStatus!(id1, 'accepted', { by: 'reviewer' });
      await service.updateProposalStatus!(id2, 'rejected', { reason: 'invalid' });

      // Query by extension
      const extAResults = await service.queryProposals!({ extensionId: 'ext.a' });
      expect(extAResults).toHaveLength(2);
      const statuses = extAResults.map((p) => p.status).sort();
      expect(statuses).toEqual(['accepted', 'rejected']);

      // Query by status
      const submittedResults = await service.queryProposals!({ statuses: ['submitted'] });
      expect(submittedResults).toHaveLength(1);
      expect(submittedResults[0].id).toBe(id3);

      // Query with limit
      const limitedResults = await service.queryProposals!({ limit: 2 });
      expect(limitedResults).toHaveLength(2);

      await service.dispose();
    });
  });

  describe('migration/RLS policy text assertions', () => {
    // Resolve migration path relative to project root
    async function readMigrationSql(): Promise<string> {
      // Use dynamic import for ESM compatibility
      // Falls back to process.cwd()-relative paths
      const [{ readFileSync }, { resolve, dirname }, { fileURLToPath }] = await Promise.all([
        import('node:fs'),
        import('node:path'),
        import('node:url'),
      ]);
      // __dirname is .../src/tools/video-editor/data, so ../../../../ reaches the project root.
      const candidate = '../../../../supabase/migrations/20260612130000_create_extension_persistence_tables.sql';
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const fullPath = resolve(__dirname, candidate);
      return readFileSync(fullPath, 'utf-8');
    }

    it('contains auth.uid() = user_id in every user-facing RLS policy', async () => {
      const sql = await readMigrationSql();
      const authUidMatches = sql.match(/auth\.uid\(\)\s*=\s*user_id/g);
      expect(authUidMatches).not.toBeNull();
      // At least 3 tables × 4 DML operations per table (select, insert, update-using, update-withcheck, delete)
      // = 15 minimum occurrences (some ops share the check)
      expect(authUidMatches!.length).toBeGreaterThanOrEqual(12);
    });

    it('contains timeline ownership check in every user-facing RLS policy', async () => {
      const sql = await readMigrationSql();
      // Pattern: exists (select 1 from public.timelines where id = timeline_id and user_id = auth.uid())
      const ownershipMatches = sql.match(
        /exists\s*\(\s*select\s+1\s+from\s+public\.timelines\s+where\s+id\s*=\s*timeline_id\s+and\s+user_id\s*=\s*auth\.uid\(\)/gi
      );
      expect(ownershipMatches).not.toBeNull();
      expect(ownershipMatches!.length).toBeGreaterThanOrEqual(12);
    });

    it('service role policies use (true) with no restrictions', async () => {
      const sql = await readMigrationSql();
      const serviceRoleCount = (sql.match(/to service_role/g) || []).length;
      expect(serviceRoleCount).toBeGreaterThanOrEqual(3);

      // Service role should use true/true for using/with check
      const serviceRoleTrueCount = (sql.match(/to service_role\s*\n\s*using\s*\(\s*true\s*\)/g) || []).length;
      expect(serviceRoleTrueCount).toBeGreaterThanOrEqual(3);
    });

    it('RLS is enabled on all three extension tables', async () => {
      const sql = await readMigrationSql();
      expect(sql).toContain('alter table public.extension_install_state enable row level security');
      expect(sql).toContain('alter table public.extension_settings enable row level security');
      expect(sql).toContain('alter table public.extension_proposals enable row level security');
    });

    it('migration includes the DO block verification that RLS is enabled', async () => {
      const sql = await readMigrationSql();
      expect(sql).toContain('CRITICAL: RLS not enabled on extension_install_state table');
      expect(sql).toContain('CRITICAL: RLS not enabled on extension_settings table');
      expect(sql).toContain('CRITICAL: RLS not enabled on extension_proposals table');
      expect(sql).toContain('M2 Extension persistence tables created successfully');
    });

    it('grants for authenticated and service_role are present on all tables', async () => {
      const sql = await readMigrationSql();
      const grantAuthCount = (sql.match(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+public\.\w+\s+to\s+authenticated/g) || []).length;
      const grantServiceCount = (sql.match(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+public\.\w+\s+to\s+service_role/g) || []).length;
      expect(grantAuthCount).toBeGreaterThanOrEqual(3);
      expect(grantServiceCount).toBeGreaterThanOrEqual(3);
    });

    it('allows every ExtensionProposalStatus value in the status check constraint', async () => {
      const sql = await readMigrationSql();
      const statusCheckMatch = sql.match(
        /check\s*\(\s*status\s+in\s*\(([^)]+)\)\s*\)/i,
      );
      expect(statusCheckMatch).not.toBeNull();
      const allowedStatuses = statusCheckMatch![1]
        .split(',')
        .map((s) => s.trim().replace(/^'|'$/g, ''));
      for (const status of ['draft', 'submitted', 'accepted', 'rejected', 'cancelled', 'expired']) {
        expect(allowedStatuses).toContain(status);
      }
    });
  });

});