import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/integrations/supabase/client.ts', () => ({
  getSupabaseClient: vi.fn(),
}));

vi.mock('@/shared/lib/media/localHandleStore.ts', () => ({
  ensurePermission: vi.fn(),
  getDirectoryHandle: vi.fn(),
  saveDirectoryHandle: vi.fn(),
}));

vi.mock('@/tools/video-editor/lib/mediaMetadata.ts', () => ({
  extractAssetRegistryEntry: vi.fn(),
}));

vi.mock('@/tools/video-editor/data/generationAssetResolver.ts', () => ({
  resolveGenerationAsset: vi.fn(),
}));

import { getSupabaseClient } from '@/integrations/supabase/client.ts';
import {
  AstridBridgeDataProvider,
  defaultAstridBridgeAssetBaseUrl,
} from '@/tools/video-editor/data/AstridBridgeDataProvider.ts';
import { TimelineNotFoundError } from '@/tools/video-editor/data/DataProvider.ts';
import {
  ensurePermission,
  getDirectoryHandle,
  saveDirectoryHandle,
} from '@/shared/lib/media/localHandleStore.ts';
import { extractAssetRegistryEntry } from '@/tools/video-editor/lib/mediaMetadata.ts';
import { resolveGenerationAsset } from '@/tools/video-editor/data/generationAssetResolver.ts';

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
  const originalShowDirectoryPicker = (globalThis as typeof globalThis & {
    showDirectoryPicker?: unknown;
  }).showDirectoryPicker;

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(makePayload()), { status: 200 })));
    vi.mocked(getDirectoryHandle).mockResolvedValue(null);
    vi.mocked(saveDirectoryHandle).mockResolvedValue(undefined);
    vi.mocked(ensurePermission).mockResolvedValue('granted');
    vi.mocked(extractAssetRegistryEntry).mockResolvedValue({
      file: 'local-drops/demo.mp4',
      type: 'video/mp4',
      duration: 4,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    if (originalShowDirectoryPicker === undefined) {
      delete (globalThis as typeof globalThis & { showDirectoryPicker?: unknown }).showDirectoryPicker;
    } else {
      (globalThis as typeof globalThis & { showDirectoryPicker?: unknown }).showDirectoryPicker = originalShowDirectoryPicker;
    }
  });

  function createDirectoryHandleTree() {
    const writable = {
      write: vi.fn(async () => undefined),
      close: vi.fn(async () => undefined),
      abort: vi.fn(async () => undefined),
    };
    const fileHandle = {
      createWritable: vi.fn(async () => writable),
    };
    const localDropsHandle = {
      kind: 'directory' as const,
      name: 'local-drops',
      queryPermission: vi.fn(async () => 'granted' as const),
      requestPermission: vi.fn(async () => 'granted' as const),
      getFileHandle: vi
        .fn()
        .mockRejectedValueOnce(new Error('missing'))
        .mockResolvedValue(fileHandle),
      getDirectoryHandle: vi.fn(),
    };
    const sourcesHandle = {
      kind: 'directory' as const,
      name: 'sources',
      queryPermission: vi.fn(async () => 'granted' as const),
      requestPermission: vi.fn(async () => 'granted' as const),
      getFileHandle: vi.fn(),
      getDirectoryHandle: vi.fn(async (name: string) => {
        if (name === 'local-drops') {
          return localDropsHandle;
        }
        throw new Error(`unexpected nested directory: ${name}`);
      }),
    };
    const projectRootHandle = {
      kind: 'directory' as const,
      name: 'ados-talks',
      queryPermission: vi.fn(async () => 'granted' as const),
      requestPermission: vi.fn(async () => 'granted' as const),
      getFileHandle: vi.fn(async (name: string) => {
        if (name === 'project.json') {
          return {};
        }
        throw new Error(`unexpected root file: ${name}`);
      }),
      getDirectoryHandle: vi.fn(async (name: string) => {
        if (name === 'sources') {
          return sourcesHandle;
        }
        throw new Error(`unexpected root directory: ${name}`);
      }),
    };

    return { projectRootHandle, sourcesHandle, localDropsHandle, fileHandle, writable };
  }

  function createFileSystemHandleTree(files: Record<string, string | Blob>) {
    const writes: Array<{ path: string; data: BlobPart }> = [];
    const removed: string[] = [];
    const normalize = (path: string) => path.replace(/^\/+/, '').replace(/\/+/g, '/');

    const makeFileHandle = (path: string) => ({
      getFile: vi.fn(async () => {
        const stored = files[normalize(path)];
        if (stored instanceof Blob) {
          return new File([stored], path.split('/').pop() ?? 'file');
        }
        if (typeof stored === 'string') {
          return new File([stored], path.split('/').pop() ?? 'file', { type: 'application/json' });
        }
        throw new Error(`missing file: ${path}`);
      }),
      createWritable: vi.fn(async () => {
        const chunks: BlobPart[] = [];
        return {
          write: vi.fn(async (data: BlobPart) => {
            chunks.push(data);
            writes.push({ path: normalize(path), data });
          }),
          close: vi.fn(async () => {
            files[normalize(path)] = chunks.length === 1 ? chunks[0] : new Blob(chunks);
          }),
          abort: vi.fn(async () => undefined),
        };
      }),
    });

    const makeDirectoryHandle = (path: string): {
      kind: 'directory';
      name: string;
      queryPermission: ReturnType<typeof vi.fn>;
      requestPermission: ReturnType<typeof vi.fn>;
      getFileHandle: ReturnType<typeof vi.fn>;
      getDirectoryHandle: ReturnType<typeof vi.fn>;
      removeEntry: ReturnType<typeof vi.fn>;
    } => ({
      kind: 'directory' as const,
      name: path.split('/').filter(Boolean).pop() ?? 'root',
      queryPermission: vi.fn(async () => 'granted' as const),
      requestPermission: vi.fn(async () => 'granted' as const),
      getFileHandle: vi.fn(async (name: string, options?: { create?: boolean }) => {
        const filePath = normalize(path ? `${path}/${name}` : name);
        if (!(filePath in files) && !options?.create) {
          throw new Error(`missing file: ${filePath}`);
        }
        return makeFileHandle(filePath);
      }),
      getDirectoryHandle: vi.fn(async (name: string) => makeDirectoryHandle(normalize(path ? `${path}/${name}` : name))),
      removeEntry: vi.fn(async (name: string) => {
        const entryPath = normalize(path ? `${path}/${name}` : name);
        removed.push(entryPath);
        for (const key of Object.keys(files)) {
          if (key === entryPath || key.startsWith(`${entryPath}/`)) {
            delete files[key];
          }
        }
      }),
    });

    return {
      files,
      writes,
      removed,
      projectRootHandle: makeDirectoryHandle(''),
    };
  }

  it('loads timeline JSON through the api base, defaults configVersion to 1, and fills missing output', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      apiBaseUrl: '/api/astrid',
      assetBaseUrl: 'http://127.0.0.1:17333',
    });

    const loaded = await provider.loadTimeline('11111111-1111-1111-1111-111111111111');

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111');
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

  it('persists registry before config save, ignores expectedVersion conflicts, and refreshes cached assets from the bridge payload', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify(makePayload()), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        expect(init?.method).toBe('PUT');
        expect(init?.body).toBe(JSON.stringify({
          assets: {
            'asset-save': { file: 'clips/saved.mp4', type: 'video/mp4', duration: 8 },
          },
        }));
        return new Response(JSON.stringify({
          assets: {
            'asset-save': { file: 'clips/saved.mp4', type: 'video/mp4', duration: 8 },
          },
        }), { status: 200 });
      }
      if (url.endsWith('/save')) {
        expect(init?.method).toBe('POST');
        expect(init?.body).toBe(JSON.stringify({
          config: {
            output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
            clips: [],
            tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          },
        }));
        return new Response(JSON.stringify({
          ...makePayload(),
          config: {
            output: { resolution: '1280x720', fps: 30, file: 'saved-output.mp4' },
            clips: [],
            tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
          },
          config_version: 7,
          registry: {
            assets: {
              'asset-save': { file: 'clips/saved.mp4', type: 'video/mp4', duration: 8 },
            },
          },
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    const nextVersion = await provider.saveTimeline('11111111-1111-1111-1111-111111111111', {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    }, 999, {
      assets: {
        'asset-save': { file: 'clips/saved.mp4', type: 'video/mp4', duration: 8 },
      },
    });

    expect(nextVersion).toBe(7);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      '/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111',
      '/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/registry',
      '/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/save',
    ]);
    await expect(provider.resolveAssetUrl('clips/saved.mp4')).resolves.toBe(
      'http://127.0.0.1:17333/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-save',
    );
    expect(getSupabaseClient).not.toHaveBeenCalled();
  });

  it('fails the whole save when registry persistence fails', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify(makePayload()), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        return new Response(JSON.stringify({
          error: 'invalid_registry',
          detail: 'registry body must contain an assets object',
        }), { status: 400 });
      }
      if (url.endsWith('/save')) {
        return new Response('{}', { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.saveTimeline('11111111-1111-1111-1111-111111111111', {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    }, 1)).rejects.toThrow('Astrid bridge save registry failed: registry body must contain an assets object');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('maps missing timelines to TimelineNotFoundError during save', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify(makePayload()), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        return new Response(JSON.stringify({
          error: 'timeline_not_found',
          detail: 'timeline missing',
        }), { status: 404 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.saveTimeline('11111111-1111-1111-1111-111111111111', {
      output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
      clips: [],
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    }, 1)).rejects.toBeInstanceOf(TimelineNotFoundError);
  });

  it('keeps checkpoint APIs reachable with local no-op behavior', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.saveCheckpoint('11111111-1111-1111-1111-111111111111', {
      timelineId: '11111111-1111-1111-1111-111111111111',
      config: {
        output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
        clips: [],
        tracks: [],
      },
      createdAt: '2026-06-11T10:00:00.000Z',
      triggerType: 'manual',
      label: 'Manual checkpoint',
      editsSinceLastCheckpoint: 3,
    })).resolves.toContain('11111111-1111-1111-1111-111111111111-checkpoint-local-');
    await expect(provider.loadCheckpoints('11111111-1111-1111-1111-111111111111')).resolves.toEqual([]);
  });

  it('registerAsset PUTs a merged full registry and refreshes asset maps', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify(makePayload()), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        expect(init?.method).toBe('PUT');
        expect(init?.body).toBe(JSON.stringify({
          assets: {
            'asset-video': { file: 'clips/demo.mp4', type: 'video/mp4', duration: 4 },
            'asset-image': { file: 'stills/cover.png', type: 'image/png' },
            'asset-audio': { file: 'audio/voice.wav', type: 'audio/wav', duration: 2.5 },
          },
        }));
        return new Response(JSON.stringify({
          assets: {
            'asset-video': { file: 'clips/demo.mp4', type: 'video/mp4', duration: 4 },
            'asset-image': { file: 'stills/cover.png', type: 'image/png' },
            'asset-audio': { file: 'audio/voice.wav', type: 'audio/wav', duration: 2.5 },
          },
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await provider.registerAsset('11111111-1111-1111-1111-111111111111', 'asset-audio', {
      file: 'audio/voice.wav',
      type: 'audio/wav',
      duration: 2.5,
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    await expect(provider.resolveAssetUrl('audio/voice.wav')).resolves.toBe(
      'http://127.0.0.1:17333/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-audio',
    );
  });

  it('saveTimeline calls the save endpoint and returns the bridge head version without a registry argument', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify({
          ...makePayload(),
          config_version: 5,
        }), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        expect(init?.method).toBe('PUT');
        expect(init?.body).toBe(JSON.stringify(makePayload().registry));
        return new Response(JSON.stringify(makePayload().registry), { status: 200 });
      }
      if (url.endsWith('/save')) {
        expect(init?.method).toBe('POST');
        expect(init?.body).toBe(JSON.stringify({
          config: { output: {}, clips: [], tracks: [] },
        }));
        return new Response(JSON.stringify({
          ...makePayload(),
          config_version: 12,
          config: { output: {}, clips: [], tracks: [] },
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    const version = await provider.saveTimeline(
      '11111111-1111-1111-1111-111111111111',
      { output: {}, clips: [], tracks: [] },
      1,
    );

    expect(version).toBe(12);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(getSupabaseClient).not.toHaveBeenCalled();
  });

  it('does not throw TimelineVersionConflictError for stale expectedVersion', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
        return new Response(JSON.stringify(makePayload()), { status: 200 });
      }
      if (url.endsWith('/registry')) {
        return new Response(JSON.stringify(makePayload().registry), { status: 200 });
      }
      if (url.endsWith('/save')) {
        return new Response(JSON.stringify({
          ...makePayload(),
          config_version: 42,
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    // Stale expectedVersion (99999) must not throw TimelineVersionConflictError
    const version = await provider.saveTimeline(
      '11111111-1111-1111-1111-111111111111',
      { output: {}, clips: [], tracks: [] },
      99999,
    );

    expect(version).toBe(42);
  });

  it('writes local drops under sources/local-drops, registers them, and reuses the persisted project handle', async () => {
    const handleTree = createDirectoryHandleTree();
    vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);

    const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
      .mockResolvedValue(undefined);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    const result = await provider.uploadAsset(new File(['video'], 'demo.mp4', { type: 'video/mp4' }), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    });

    expect(ensurePermission).toHaveBeenCalledWith(handleTree.projectRootHandle, 'readwrite');
    expect(handleTree.projectRootHandle.getFileHandle).toHaveBeenCalledWith('project.json');
    expect(handleTree.projectRootHandle.getDirectoryHandle).toHaveBeenCalledWith('sources');
    expect(handleTree.sourcesHandle.getDirectoryHandle).toHaveBeenCalledWith('local-drops', { create: true });
    expect(handleTree.localDropsHandle.getFileHandle).toHaveBeenNthCalledWith(1, 'demo.mp4');
    expect(handleTree.localDropsHandle.getFileHandle).toHaveBeenNthCalledWith(2, 'demo.mp4', { create: true });
    expect(handleTree.writable.write).toHaveBeenCalledTimes(1);
    expect(handleTree.writable.close).toHaveBeenCalledTimes(1);
    expect(extractAssetRegistryEntry).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'demo.mp4', type: 'video/mp4' }),
      'local-drops/demo.mp4',
    );
    expect(registerAssetSpy).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      expect.any(String),
      {
        file: 'local-drops/demo.mp4',
        type: 'video/mp4',
        duration: 4,
      },
    );
    expect(result).toEqual({
      assetId: expect.any(String),
      entry: {
        file: 'local-drops/demo.mp4',
        type: 'video/mp4',
        duration: 4,
      },
    });
  });

  it('prompts for an Astrid project root when no persisted handle exists', async () => {
    const handleTree = createDirectoryHandleTree();
    const showDirectoryPicker = vi.fn(async () => handleTree.projectRootHandle);
    vi.stubGlobal('showDirectoryPicker', showDirectoryPicker);

    const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
      .mockResolvedValue(undefined);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await provider.uploadAsset(new File(['image'], 'cover.png', { type: 'image/png' }), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    });

    expect(showDirectoryPicker).toHaveBeenCalledTimes(1);
    expect(saveDirectoryHandle).toHaveBeenCalledWith('astrid-project-root:ados-talks', handleTree.projectRootHandle);
    expect(registerAssetSpy).toHaveBeenCalledTimes(1);
  });

  it('reports unsupported browsers when File System Access is unavailable', async () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.uploadAsset(new File(['x'], 'demo.txt'), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    })).rejects.toThrow('Local asset drop requires a browser with File System Access support');
  });

  it('throws and does not mutate the registry, disk, or timeline when directory permission is denied', async () => {
    const handleTree = createDirectoryHandleTree();
    vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);
    vi.mocked(ensurePermission).mockResolvedValue('denied');

    const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
      .mockResolvedValue(undefined);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    await expect(provider.uploadAsset(new File(['video'], 'demo.mp4', { type: 'video/mp4' }), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    })).rejects.toThrow('Astrid local asset drop requires read/write access to the selected project folder');

    expect(ensurePermission).toHaveBeenCalledWith(handleTree.projectRootHandle, 'readwrite');
    expect(registerAssetSpy).not.toHaveBeenCalled();
    expect(handleTree.writable.write).not.toHaveBeenCalled();
    expect(handleTree.writable.close).not.toHaveBeenCalled();
  });

  it('produces a registry entry with a sources-relative file path and verifies the entry shape after uploadAsset', async () => {
    const handleTree = createDirectoryHandleTree();
    vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);
    vi.mocked(extractAssetRegistryEntry).mockResolvedValue({
      file: 'local-drops/voice.wav',
      type: 'audio/wav',
      duration: 2.5,
    });

    const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
      .mockResolvedValue(undefined);

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
      timelineId: '11111111-1111-1111-1111-111111111111',
    });

    const result = await provider.uploadAsset(new File(['audio'], 'voice.wav', { type: 'audio/wav' }), {
      timelineId: '11111111-1111-1111-1111-111111111111',
      userId: 'user-1',
    });

    // Registry entry shape verification
    expect(result.entry).toEqual({
      file: 'local-drops/voice.wav',
      type: 'audio/wav',
      duration: 2.5,
    });
    expect(result.entry.file).toMatch(/^local-drops\//);
    expect(result.assetId).toEqual(expect.any(String));
    expect(result.assetId.length).toBeGreaterThan(0);

    // registerAsset is called with the sources-relative path
    expect(registerAssetSpy).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      expect.any(String),
      expect.objectContaining({
        file: 'local-drops/voice.wav',
      }),
    );
  });

  it('loads local assembly and registry files through the persisted project handle and resolves source-relative files', async () => {
    const originalCreateObjectUrl = URL.createObjectURL;
    const localTree = createFileSystemHandleTree({
      'project.json': JSON.stringify({ slug: 'ados-talks' }),
      'timelines/01JM4K5N7P0000000000000017/assembly.json': JSON.stringify({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      }),
      'timelines/01JM4K5N7P0000000000000017/registry.json': JSON.stringify({
        assets: {
          'asset-video': { file: 'clips/demo.mp4', type: 'video/mp4' },
        },
      }),
      'sources/clips/demo.mp4': new Blob(['video-bytes'], { type: 'video/mp4' }),
    });
    vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);
    const createObjectUrl = vi.fn(() => 'blob:local-demo');
    URL.createObjectURL = createObjectUrl;

    try {
      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef: '01JM4K5N7P0000000000000017',
        timelineId: '01JM4K5N7P0000000000000017',
      });

      const loaded = await provider.loadTimeline('01JM4K5N7P0000000000000017');
      const registry = await provider.loadAssetRegistry('01JM4K5N7P0000000000000017');

      expect(loaded.config.output).toEqual(expect.objectContaining({
        resolution: '1280x720',
        fps: 30,
        file: 'output.mp4',
      }));
      expect(registry.assets['asset-video'].file).toBe('clips/demo.mp4');
      await expect(provider.resolveAssetUrl('clips/demo.mp4')).resolves.toBe('blob:local-demo');
      expect(createObjectUrl).toHaveBeenCalledTimes(1);
      expect(globalThis.fetch).not.toHaveBeenCalled();
    } finally {
      URL.createObjectURL = originalCreateObjectUrl;
    }
  });

  it('materializes generation-backed assets to sources/assets and persists a consistent registry after download', async () => {
    const localTree = createFileSystemHandleTree({
      'project.json': JSON.stringify({ slug: 'ados-talks' }),
      'timelines/01JM4K5N7P0000000000000017/assembly.json': JSON.stringify({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      }),
      'timelines/01JM4K5N7P0000000000000017/registry.json': JSON.stringify({
        assets: {
          'asset-generation': {
            file: '',
            type: 'video/mp4',
            generationId: 'gen-1',
            origin: 'refreshable-from-generation',
          },
        },
      }),
    });
    vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);
    vi.mocked(resolveGenerationAsset).mockResolvedValue({
      ok: true,
      asset: {
        entry: {
          file: '',
          type: 'video/mp4',
          generationId: 'gen-1',
          origin: 'refreshable-from-generation',
          url: 'https://storage.example/object/sign/generation-media/gen-1/demo.mp4?token=abc',
        },
        generationId: 'gen-1',
        url: 'https://storage.example/object/sign/generation-media/gen-1/demo.mp4?token=abc',
        mediaType: 'video',
        mimeType: 'video/mp4',
        refreshed: false,
        storage: null,
      },
    });
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).startsWith('https://storage.example/')) {
        return new Response(new Blob(['downloaded-video'], { type: 'video/mp4' }), { status: 200 });
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }));

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: '01JM4K5N7P0000000000000017',
      timelineId: '01JM4K5N7P0000000000000017',
    });

    const registry = await provider.loadAssetRegistry('01JM4K5N7P0000000000000017');

    expect(registry.assets['asset-generation']).toEqual(expect.objectContaining({
      file: 'assets/demo.mp4',
      generationId: 'gen-1',
      url: 'https://storage.example/object/sign/generation-media/gen-1/demo.mp4?token=abc',
    }));
    expect((localTree.files['sources/assets/demo.mp4'] as Blob).size).toBeGreaterThan(0);
    expect(String(localTree.files['timelines/01JM4K5N7P0000000000000017/registry.json'])).toContain('"file": "assets/demo.mp4"');
    expect(localTree.writes.map((write) => write.path)).toEqual(expect.arrayContaining([
      expect.stringMatching(/^sources\/assets\/\.incoming\/.+\/demo\.mp4$/),
      'sources/assets/demo.mp4',
      expect.stringMatching(/^timelines\/01JM4K5N7P0000000000000017\/\.registry\.json\..+\.tmp$/),
      'timelines/01JM4K5N7P0000000000000017/registry.json',
    ]));
    expect(provider.getMaterializationSummary().states['asset-generation']).toEqual({
      state: 'materialized',
      file: 'assets/demo.mp4',
    });
  });

  it('keeps failed generation materialization out of the persisted registry and records a diagnostic', async () => {
    const originalRegistry = {
      assets: {
        'asset-generation': {
          file: '',
          type: 'video/mp4',
          generationId: 'gen-1',
          origin: 'refreshable-from-generation',
        },
      },
    };
    const localTree = createFileSystemHandleTree({
      'project.json': JSON.stringify({ slug: 'ados-talks' }),
      'timelines/01JM4K5N7P0000000000000017/assembly.json': JSON.stringify({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      }),
      'timelines/01JM4K5N7P0000000000000017/registry.json': JSON.stringify(originalRegistry),
    });
    vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);
    vi.mocked(resolveGenerationAsset).mockResolvedValue({
      ok: false,
      missingReason: 'unresolvable_asset',
      diagnostic: {
        code: 'refresh-required',
        message: 'bucket/path cannot be derived',
        generationId: 'gen-1',
        assetId: 'asset-generation',
      },
    });

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: '01JM4K5N7P0000000000000017',
      timelineId: '01JM4K5N7P0000000000000017',
    });

    const registry = await provider.loadAssetRegistry('01JM4K5N7P0000000000000017');

    expect(registry.assets['asset-generation']).toEqual(originalRegistry.assets['asset-generation']);
    expect(JSON.parse(String(localTree.files['timelines/01JM4K5N7P0000000000000017/registry.json']))).toEqual(originalRegistry);
    expect(localTree.writes).toEqual([]);
    expect(provider.getMaterializationSummary().states['asset-generation']).toEqual({
      state: 'skipped-with-diagnostic',
      diagnostic: {
        assetId: 'asset-generation',
        generationId: 'gen-1',
        reason: 'refresh-required',
        message: 'bucket/path cannot be derived',
      },
    });
  });

  it('materializes resolvable assets, preserves failed entries, and surfaces diagnostics in one local registry pass', async () => {
    const originalRegistry = {
      assets: {
        'asset-success': {
          file: '',
          type: 'video/mp4',
          generationId: 'gen-success',
          origin: 'refreshable-from-generation',
        },
        'asset-failure': {
          file: '',
          type: 'image/png',
          generationId: 'gen-failure',
          origin: 'refreshable-from-generation',
        },
      },
    };
    const localTree = createFileSystemHandleTree({
      'project.json': JSON.stringify({ slug: 'ados-talks' }),
      'timelines/01JM4K5N7P0000000000000017/assembly.json': JSON.stringify({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      }),
      'timelines/01JM4K5N7P0000000000000017/registry.json': JSON.stringify(originalRegistry),
    });
    vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);
    vi.mocked(resolveGenerationAsset).mockImplementation(async ({ assetId }) => {
      if (assetId === 'asset-success') {
        return {
          ok: true,
          asset: {
            entry: {
              file: '',
              type: 'video/mp4',
              generationId: 'gen-success',
              origin: 'refreshable-from-generation',
              url: 'https://storage.example/object/sign/generation-media/gen-success/demo.mp4?token=abc',
            },
            generationId: 'gen-success',
            url: 'https://storage.example/object/sign/generation-media/gen-success/demo.mp4?token=abc',
            mediaType: 'video',
            mimeType: 'video/mp4',
            refreshed: false,
            storage: null,
          },
        };
      }

      return {
        ok: false,
        missingReason: 'unresolvable_asset',
        diagnostic: {
          code: 'refresh-required',
          message: 'signed URL can no longer be re-minted',
          generationId: 'gen-failure',
          assetId: 'asset-failure',
        },
      };
    });
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).startsWith('https://storage.example/')) {
        return new Response(new Blob(['downloaded-video'], { type: 'video/mp4' }), { status: 200 });
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }));

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: '01JM4K5N7P0000000000000017',
      timelineId: '01JM4K5N7P0000000000000017',
    });

    const registry = await provider.loadAssetRegistry('01JM4K5N7P0000000000000017');
    const persistedRegistry = JSON.parse(String(localTree.files['timelines/01JM4K5N7P0000000000000017/registry.json']));
    const summary = provider.getMaterializationSummary();

    expect(registry.assets['asset-success']).toEqual(expect.objectContaining({
      file: 'assets/demo.mp4',
      generationId: 'gen-success',
    }));
    expect(registry.assets['asset-failure']).toEqual(originalRegistry.assets['asset-failure']);
    expect(persistedRegistry).toEqual({
      assets: {
        'asset-success': expect.objectContaining({
          file: 'assets/demo.mp4',
          generationId: 'gen-success',
        }),
        'asset-failure': originalRegistry.assets['asset-failure'],
      },
    });
    expect(persistedRegistry.assets['asset-failure'].file).toBe('');
    expect((localTree.files['sources/assets/demo.mp4'] as Blob).size).toBeGreaterThan(0);
    expect(localTree.files['sources/assets/failure.png']).toBeUndefined();
    expect(summary.states['asset-success']).toEqual({
      state: 'materialized',
      file: 'assets/demo.mp4',
    });
    expect(summary.states['asset-failure']).toEqual({
      state: 'skipped-with-diagnostic',
      diagnostic: {
        assetId: 'asset-failure',
        generationId: 'gen-failure',
        reason: 'refresh-required',
        message: 'signed URL can no longer be re-minted',
      },
    });
    expect(summary.diagnostics).toEqual([
      {
        assetId: 'asset-failure',
        generationId: 'gen-failure',
        reason: 'refresh-required',
        message: 'signed URL can no longer be re-minted',
      },
    ]);
  });

  it('does not automatically retry skipped assets on local save but still materializes newly attempted ones', async () => {
    const localTree = createFileSystemHandleTree({
      'project.json': JSON.stringify({ slug: 'ados-talks' }),
      'timelines/01JM4K5N7P0000000000000017/assembly.json': JSON.stringify({
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      }),
      'timelines/01JM4K5N7P0000000000000017/registry.json': JSON.stringify({
        assets: {
          'asset-skipped': {
            file: '',
            type: 'video/mp4',
            generationId: 'gen-skipped',
            origin: 'refreshable-from-generation',
          },
        },
      }),
    });
    vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);
    const resolveGenerationAssetMock = vi.mocked(resolveGenerationAsset);
    resolveGenerationAssetMock.mockImplementation(async ({ assetId }) => {
      if (assetId === 'asset-skipped') {
        return {
          ok: false,
          missingReason: 'unresolvable_asset',
          diagnostic: {
            code: 'refresh-required',
            message: 'gen-skipped still cannot be refreshed',
            generationId: 'gen-skipped',
            assetId: 'asset-skipped',
          },
        };
      }

      if (assetId === 'asset-new') {
        return {
          ok: true,
          asset: {
            entry: {
              file: '',
              type: 'audio/wav',
              generationId: 'gen-new',
              origin: 'refreshable-from-generation',
              url: 'https://storage.example/object/sign/generation-media/gen-new/new.wav?token=abc',
            },
            generationId: 'gen-new',
            url: 'https://storage.example/object/sign/generation-media/gen-new/new.wav?token=abc',
            mediaType: 'audio',
            mimeType: 'audio/wav',
            refreshed: false,
            storage: null,
          },
        };
      }

      throw new Error(`Unexpected assetId: ${assetId}`);
    });
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).startsWith('https://storage.example/')) {
        return new Response(new Blob(['new-audio'], { type: 'audio/wav' }), { status: 200 });
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }));

    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: '01JM4K5N7P0000000000000017',
      timelineId: '01JM4K5N7P0000000000000017',
    });

    await provider.loadAssetRegistry('01JM4K5N7P0000000000000017');
    expect(provider.getMaterializationSummary().states['asset-skipped']).toEqual({
      state: 'skipped-with-diagnostic',
      diagnostic: {
        assetId: 'asset-skipped',
        generationId: 'gen-skipped',
        reason: 'refresh-required',
        message: 'gen-skipped still cannot be refreshed',
      },
    });
    resolveGenerationAssetMock.mockClear();

    const version = await provider.saveTimeline(
      '01JM4K5N7P0000000000000017',
      {
        output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      },
      1,
      {
        assets: {
          'asset-skipped': {
            file: '',
            type: 'video/mp4',
            generationId: 'gen-skipped',
            origin: 'refreshable-from-generation',
          },
          'asset-new': {
            file: '',
            type: 'audio/wav',
            generationId: 'gen-new',
            origin: 'refreshable-from-generation',
          },
        },
      },
    );

    const persistedRegistry = JSON.parse(String(localTree.files['timelines/01JM4K5N7P0000000000000017/registry.json']));
    const materializedAssetIds = resolveGenerationAssetMock.mock.calls.map(([request]) => request.assetId);

    expect(version).toBe(2);
    expect(materializedAssetIds).toEqual(['asset-new']);
    expect(persistedRegistry.assets['asset-skipped']).toEqual({
      file: '',
      type: 'video/mp4',
      generationId: 'gen-skipped',
      origin: 'refreshable-from-generation',
    });
    expect(persistedRegistry.assets['asset-new']).toEqual(expect.objectContaining({
      file: 'assets/new.wav',
      generationId: 'gen-new',
      type: 'audio/wav',
    }));
    expect((localTree.files['sources/assets/new.wav'] as Blob).size).toBeGreaterThan(0);
    expect(provider.getMaterializationSummary()).toEqual({
      states: {
        'asset-skipped': {
          state: 'skipped-with-diagnostic',
          diagnostic: {
            assetId: 'asset-skipped',
            generationId: 'gen-skipped',
            reason: 'refresh-required',
            message: 'gen-skipped still cannot be refreshed',
          },
        },
        'asset-new': {
          state: 'materialized',
          file: 'assets/new.wav',
        },
      },
      diagnostics: [
        {
          assetId: 'asset-skipped',
          generationId: 'gen-skipped',
          reason: 'refresh-required',
          message: 'gen-skipped still cannot be refreshed',
        },
      ],
    });
  });

  it('uses the direct localhost asset base default', () => {
    expect(defaultAstridBridgeAssetBaseUrl()).toBe('http://127.0.0.1:17333');
  });
});
