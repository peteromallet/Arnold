/**
 * Provider compatibility test: SupabaseDataProvider (mocked)
 *
 * Exercises a subset of the shared providerCompatibility suite against a
 * mocked SupabaseDataProvider. The Supabase provider delegates persistence
 * to an append service via fetch; this test mocks that service to validate
 * provider contract behavior without a live Supabase instance.
 *
 * NOTE: This test exercises the versioned-load path and error-type
 * contracts. Full save/conflict coverage for Supabase lives in
 * SupabaseDataProvider.test.ts. The shared compatibility helper's
 * versionConflictIsSoft=false path is exercised through InMemory.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeIndexedDB, IDBKeyRange } from 'fake-indexeddb';

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  from: vi.fn(),
  readAccessTokenFromStorage: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: vi.fn(() => ({
    auth: { getSession: mocks.getSession },
    from: mocks.from,
    storage: { from: vi.fn(() => ({ getPublicUrl: vi.fn(() => ({ data: { publicUrl: 'https://cdn.example/test.mp4' } })) })) },
  })),
}));

vi.mock('@/shared/lib/supabaseSession', () => ({
  readAccessTokenFromStorage: mocks.readAccessTokenFromStorage,
}));

import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider';
import { TimelineNotFoundError, TimelineVersionConflictError } from '@/tools/video-editor/data/DataProvider';
import type { TimelineConfig, AssetRegistry } from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Minimal config builders
// ---------------------------------------------------------------------------

function buildConfig(overrides: Partial<TimelineConfig> = {}): TimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'timeline.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [],
    ...overrides,
  } as TimelineConfig;
}

const config1 = buildConfig();
const config2 = buildConfig({
  clips: [{ id: 'clip-1', clipType: 'hold', track: 'V1', at: 0, hold: 5 } as any],
});

const registry1: AssetRegistry = {
  assets: { 'asset-1': { file: 'clips/demo.mp4', type: 'video/mp4', duration: 4 } },
};

// ---------------------------------------------------------------------------
// Mock helpers (pattern-matched from SupabaseDataProvider.test.ts)
// ---------------------------------------------------------------------------

function mockTimelinesSelect(config: TimelineConfig, configVersion: number, registry?: AssetRegistry) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: {
      config,
      config_version: configVersion,
      asset_registry: registry ?? { assets: {} },
    },
    error: null,
  });
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, maybeSingle };
}

function mockTimelineHeadSelect(version: number) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: {
      version,
      hash: 'a'.repeat(64),
      event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    },
    error: null,
  });
  const limit = vi.fn().mockReturnValue({ maybeSingle });
  const order = vi.fn().mockReturnValue({ limit });
  const eq = vi.fn().mockReturnValue({ order });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, order, limit, maybeSingle };
}

function mockSyncBookmarkSelect() {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: {
      timeline_id: 'compat-test-timeline',
      spoke: 'app',
      spoke_version: 1,
      spoke_hash: 'a'.repeat(64),
      spoke_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
      hub_version: 1,
      hub_hash: 'a'.repeat(64),
      hub_event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
      synced_at: '2026-06-20T00:00:00.000Z',
    },
    error: null,
  });
  const spokeEq = vi.fn().mockReturnValue({ maybeSingle });
  const timelineEq = vi.fn().mockReturnValue({ eq: spokeEq });
  const select = vi.fn().mockReturnValue({ eq: timelineEq });
  return { select, timelineEq, spokeEq, maybeSingle };
}

// Supply timeline data that matures across saves (for load-after-save tests)
function mockTimelinesSelectMature(config: TimelineConfig, configVersion: number, registry?: AssetRegistry) {
  let currentConfig = config;
  let currentVersion = configVersion;
  let currentRegistry = registry ?? { assets: {} };

  const maybeSingle = vi.fn().mockImplementation(async () => ({
    data: {
      config: currentConfig,
      config_version: currentVersion,
      asset_registry: currentRegistry,
    },
    error: null,
  }));
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, maybeSingle, mature: (c: TimelineConfig, v: number, r?: AssetRegistry) => {
    currentConfig = c;
    currentVersion = v;
    if (r) currentRegistry = r;
  }};
}

function mockTimelineHeadSelectMature(version: number) {
  let currentVersion = version;
  const maybeSingle = vi.fn().mockImplementation(async () => ({
    data: {
      version: currentVersion,
      hash: 'a'.repeat(64),
      event_id: '01ARZ3NDEKTSV4RRFFQ69G5FAB',
    },
    error: null,
  }));
  const limit = vi.fn().mockReturnValue({ maybeSingle });
  const order = vi.fn().mockReturnValue({ limit });
  const eq = vi.fn().mockReturnValue({ order });
  const select = vi.fn().mockReturnValue({ eq });
  return { select, eq, order, limit, maybeSingle, mature: (v: number) => { currentVersion = v; } };
}

// ---------------------------------------------------------------------------
// Tests (manually written, not using the shared suite, because Supabase
// mocks are too intricate for a generic factory)
// ---------------------------------------------------------------------------

describe('SupabaseDataProvider compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('indexedDB', createFakeIndexedDB());
    vi.stubGlobal('IDBKeyRange', IDBKeyRange);
    vi.stubEnv('VITE_REIGH_APPEND_SERVICE_URL', 'https://append-service.example/');
    (import.meta.env as Record<string, string | undefined>).VITE_REIGH_APPEND_SERVICE_URL =
      'https://append-service.example/';
    mocks.readAccessTokenFromStorage.mockReturnValue('cached-user-jwt');
    mocks.getSession.mockResolvedValue({
      data: { session: { access_token: 'session-user-jwt' } },
      error: null,
    });
    vi.stubGlobal('fetch', vi.fn());
  });

  describe('versioned load', () => {
    it('loadTimeline returns configVersion from materialized Supabase row', async () => {
      const timelinesQuery = mockTimelinesSelect(config1, 7);
      const timelineHeadQuery = mockTimelineHeadSelect(7);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const loaded = await provider.loadTimeline('timeline-1');

      expect(loaded.configVersion).toBe(7);
      expect(loaded.config).toBeDefined();
    });

    it('loadAssetRegistry returns asset data from the materialized row', async () => {
      const timelinesQuery = mockTimelinesSelect(config1, 1, registry1);
      const timelineHeadQuery = mockTimelineHeadSelect(1);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const registry = await provider.loadAssetRegistry('timeline-1');

      expect(registry.assets['asset-1']).toBeDefined();
      expect(registry.assets['asset-1'].file).toBe('clips/demo.mp4');
    });
  });

  describe('versioned save', () => {
    it('saveTimeline returns config_version from append-service success response', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(
          JSON.stringify({
            config_version: 9,
            db_head: {
              version: 9,
              hash: 'b'.repeat(64),
              event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBB',
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });
      const nextVersion = await provider.saveTimeline('timeline-1', config1, 8, registry1);

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
        config: config1,
        asset_registry: registry1,
        expected_version: 8,
        actor: { type: 'human', id: 'user-123' },
        source: 'editor_save',
      });
    });

    it('saveTimeline config-only posts without asset_registry', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(
          JSON.stringify({
            config_version: 5,
            db_head: {
              version: 5,
              hash: 'c'.repeat(64),
              event_id: '01ARZ3NDEKTSV4RRFFQ69G5FBC',
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });
      const nextVersion = await provider.saveTimeline('timeline-1', config1, 4);

      expect(nextVersion).toBe(5);

      const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
      const body = JSON.parse(String(init?.body));
      expect(body).toEqual({
        config: config1,
        expected_version: 4,
        actor: { type: 'human', id: 'user-123' },
        source: 'editor_save',
      });
      expect(body).not.toHaveProperty('asset_registry');
    });
  });

  describe('diagnostics: error types', () => {
    it('maps append-service 409 to TimelineVersionConflictError', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(
          JSON.stringify({
            error: 'version_conflict',
            detail: 'timeline config_version mismatch: expected 3, found 4',
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        ),
      );

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-123' });
      await expect(
        provider.saveTimeline('timeline-1', config1, 3),
      ).rejects.toBeInstanceOf(TimelineVersionConflictError);
    });

    it('TimelineVersionConflictError has code timeline_version_conflict', () => {
      const error = new TimelineVersionConflictError('stale baseVersion');
      expect(error.code).toBe('timeline_version_conflict');
      expect(error.name).toBe('TimelineVersionConflictError');
    });
  });

  describe('serialization fidelity', () => {
    it('loadTimeline preserves config shape from Supabase row', async () => {
      const cfg = buildConfig({
        output: { resolution: '3840x2160', fps: 60, file: 'uhd.mp4' },
        tracks: [
          { id: 'V1', kind: 'visual', label: 'Video 1' },
          { id: 'A1', kind: 'audio', label: 'Audio 1' },
        ],
      });

      const timelinesQuery = mockTimelinesSelect(cfg, 2);
      const timelineHeadQuery = mockTimelineHeadSelect(2);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const loaded = await provider.loadTimeline('timeline-1');

      expect(loaded.config.output).toEqual(cfg.output);
      expect(loaded.config.tracks).toHaveLength(2);
    });
  });

  describe('extension requirements', () => {
    it('timeline config preserves extension-owned app data', async () => {
      const cfg = buildConfig({
        app: {
          'com.example.test': { version: 1, settings: { theme: 'dark' } },
        },
      } as any);

      const timelinesQuery = mockTimelinesSelect(cfg, 1);
      const timelineHeadQuery = mockTimelineHeadSelect(1);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const loaded = await provider.loadTimeline('timeline-1');

      expect((loaded.config as any).app).toBeDefined();
      expect((loaded.config as any).app['com.example.test']).toEqual({
        version: 1,
        settings: { theme: 'dark' },
      });
    });
  });

  describe('proposal base-version handling', () => {
    it('loadTimeline returns configVersion suitable for proposal baseVersion', async () => {
      const timelinesQuery = mockTimelinesSelect(config1, 7);
      const timelineHeadQuery = mockTimelineHeadSelect(7);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const loaded = await provider.loadTimeline('timeline-1');

      expect(typeof loaded.configVersion).toBe('number');
      expect(loaded.configVersion).toBeGreaterThanOrEqual(1);
      expect(Number.isInteger(loaded.configVersion)).toBe(true);
    });
  });

  describe('resolveAssetUrl', () => {
    it('returns a public URL via Supabase storage', async () => {
      const timelinesQuery = mockTimelinesSelect(config1, 1);
      const timelineHeadQuery = mockTimelineHeadSelect(1);
      const syncBookmarkQuery = mockSyncBookmarkSelect();

      mocks.from.mockImplementation((table: string) => {
        if (table === 'timelines') return { select: timelinesQuery.select };
        if (table === 'timeline_events') return { select: timelineHeadQuery.select };
        if (table === 'sync_bookmarks') return { select: syncBookmarkQuery.select };
        throw new Error(`Unexpected table: ${table}`);
      });

      const provider = new SupabaseDataProvider({ projectId: 'project-1', userId: 'user-1' });
      const url = await provider.resolveAssetUrl('clips/demo.mp4');

      expect(typeof url).toBe('string');
    });
  });
});
