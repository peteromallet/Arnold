import { beforeEach, describe, expect, it, vi } from 'vitest';

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
  mocks.from.mockReturnValue({ select });
  return { select, eq, maybeSingle };
}

describe('SupabaseDataProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    mockTimelinesSelect({
      data: {
        config: buildConfig(),
        config_version: 7,
        asset_registry: { assets: { 'asset-1': { file: 'clips/demo.mp4' } } },
      },
      error: null,
    });

    const timeline = await provider.loadTimeline('timeline-1');
    const registry = await provider.loadAssetRegistry('timeline-1');

    expect(timeline.configVersion).toBe(7);
    expect(registry).toEqual({ assets: { 'asset-1': { file: 'clips/demo.mp4' } } });
    expect(mocks.from).toHaveBeenNthCalledWith(1, 'timelines');
    expect(mocks.from).toHaveBeenNthCalledWith(2, 'timelines');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('saveTimeline posts config and registry to the append service with the user JWT', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({ config_version: 9 }), {
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
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({ config_version: 5 }), {
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

  it('saveTimeline falls back to the live session token when no cached token exists', async () => {
    mocks.readAccessTokenFromStorage.mockReturnValue(null);
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({ config_version: 3 }), {
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
});
