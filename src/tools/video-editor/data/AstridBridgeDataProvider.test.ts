import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/integrations/supabase/client.ts', () => ({
  getSupabaseClient: vi.fn(),
}));

import { getSupabaseClient } from '@/integrations/supabase/client.ts';
import {
  AstridBridgeDataProvider,
  AstridBridgeReadOnlyError,
  defaultAstridBridgeAssetBaseUrl,
} from '@/tools/video-editor/data/AstridBridgeDataProvider.ts';

const makePayload = () => ({
  timeline_id: '11111111-1111-1111-1111-111111111111',
  timeline_ulid: '01JM4K5N7P0000000000000017',
  slug: 'intro-cut',
  config: {
    clips: [],
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  },
  registry: {
    assets: {
      'asset-video': { file: 'clips/demo.mp4', type: 'video/mp4', duration: 4 },
      'asset-image': { file: 'stills/cover.png', type: 'image/png' },
    },
  },
});

describe('AstridBridgeDataProvider', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(makePayload()), { status: 200 })));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
  });

  it('loads timeline JSON through the api base, defaults configVersion to 1, and fills missing output', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      apiBaseUrl: '/api/astrid',
      assetBaseUrl: 'http://127.0.0.1:17333',
    });

    const loaded = await provider.loadTimeline('11111111-1111-1111-1111-111111111111');

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/astrid/projects/ados-talks/timelines/intro-cut');
    expect(loaded.configVersion).toBe(1);
    expect(loaded.config.output).toEqual(expect.objectContaining({
      resolution: '1280x720',
      fps: 30,
      file: 'output.mp4',
    }));
    expect(getSupabaseClient).not.toHaveBeenCalled();
  });

  it('loads the registry once, keeps assetKey and file maps, and resolves direct bridge asset URLs', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
      apiBaseUrl: '/api/astrid',
      assetBaseUrl: 'http://127.0.0.1:17333',
    });

    const registry = await provider.loadAssetRegistry('11111111-1111-1111-1111-111111111111');

    expect(registry.assets['asset-video'].file).toBe('clips/demo.mp4');
    await expect(provider.resolveAssetUrl('clips/demo.mp4')).resolves.toBe(
      'http://127.0.0.1:17333/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-video',
    );
    await expect(provider.resolveAssetUrl('https://cdn.example/test.mp4')).resolves.toBe('https://cdn.example/test.mp4');
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(getSupabaseClient).not.toHaveBeenCalled();
  });

  it('prefers the explicit asset key during onResolve when files overlap', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      ...makePayload(),
      registry: {
        assets: {
          'asset-a': { file: 'shared/file.mp4', type: 'video/mp4' },
          'asset-b': { file: 'shared/file.mp4', type: 'video/mp4' },
        },
      },
    }), { status: 200 })));

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
      assetBaseUrl: 'http://127.0.0.1:17333',
    });

    await provider.loadAssetRegistry('11111111-1111-1111-1111-111111111111');

    await expect(provider.onResolve({
      file: 'shared/file.mp4',
      assetId: 'asset-b',
    })).resolves.toBe(
      'http://127.0.0.1:17333/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-b',
    );
  });

  it('rejects write-like methods with a read-only error', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.saveTimeline('11111111-1111-1111-1111-111111111111', {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [],
      tracks: [],
    }, 1)).rejects.toBeInstanceOf(AstridBridgeReadOnlyError);
    await expect(provider.registerAsset('11111111-1111-1111-1111-111111111111', 'asset-1', {
      file: 'clips/demo.mp4',
    })).rejects.toMatchObject({ code: 'astrid_bridge_read_only' });
    await expect(provider.uploadAsset(new File(['x'], 'demo.txt'), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    })).rejects.toMatchObject({ code: 'astrid_bridge_read_only' });
  });

  it('uses the direct localhost asset base default', () => {
    expect(defaultAstridBridgeAssetBaseUrl()).toBe('http://127.0.0.1:17333');
  });
});
