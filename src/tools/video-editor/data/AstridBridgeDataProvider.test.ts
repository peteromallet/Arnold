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
  enrichRegistryEntryWithParsers: vi.fn(),
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
  expectUnsupportedExtensionPersistenceDiagnostics,
} from '@/tools/video-editor/data/conformance/extensionPersistenceConformance';
import {
  ensurePermission,
  getDirectoryHandle,
  saveDirectoryHandle,
} from '@/shared/lib/media/localHandleStore.ts';
import { extractAssetRegistryEntry, enrichRegistryEntryWithParsers } from '@/tools/video-editor/lib/mediaMetadata.ts';
import { resolveGenerationAsset } from '@/tools/video-editor/data/generationAssetResolver.ts';
import type { RegisteredParser } from '@/tools/video-editor/lib/assetParserRuntime';
import { hasSearchableMetadata, mergeSearchProviderResults, shouldShowMetadataSearch } from '@/tools/video-editor/lib/assetMetadataUIHelpers';
import type { SearchProviderResultEnvelope } from '@/tools/video-editor/lib/assetMetadataUIHelpers';
import {
  createCompileOnlyOutputFormatRegistry,
  executeCompileOnlyOutputSync,
} from '@/tools/video-editor/runtime/outputFormatRegistry';
import type {
  CompileOnlyOutputFormatEntry,
} from '@/tools/video-editor/runtime/outputFormatRegistry';
import type { OutputFormatContribution, OutputFormatHandler, OutputFormatContext, CompileOnlyOutputResult, TimelineSnapshot, AssetMetadata } from '@reigh/editor-sdk';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';


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
    vi.mocked(enrichRegistryEntryWithParsers).mockReset();
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

  it('keeps extension persistence unsupported for M2 and emits normalized diagnostics', () => {
    const provider = new AstridBridgeDataProvider({
      projectSlug: 'ados-talks',
      timelineRef: 'intro-cut',
    });
    const diagnostics: ExtensionDiagnostic[] = [];

    expectUnsupportedExtensionPersistenceDiagnostics(provider, diagnostics, 'Astrid bridge');
  });

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
      '/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-save',
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
      '/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111/assets/asset-audio',
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
        return new Response('downloaded-video', {
          status: 200,
          headers: { 'Content-Type': 'video/mp4' },
        });
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
        return new Response('downloaded-video', {
          status: 200,
          headers: { 'Content-Type': 'video/mp4' },
        });
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
        return new Response('new-audio', {
          status: 200,
          headers: { 'Content-Type': 'audio/wav' },
        });
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

  // -------------------------------------------------------------------------
  // Local monotonic stale invalidation gap (T14)
  // -------------------------------------------------------------------------
  describe('local monotonic stale invalidation gap', () => {
    it('does NOT reject saves with a stale expectedVersion (no CAS enforcement)', async () => {
      // AstridBridgeDataProvider explicitly ignores expectedVersion
      // (the parameter is named _expectedVersion in saveTimeline).
      // This test demonstrates the gap: without the local monotonic
      // invalidation in useTimelineOps.apply(), a stale patch would
      // silently overwrite newer data.
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

      // Save with a wildly stale expectedVersion (99999) — must NOT throw
      const version = await provider.saveTimeline(
        '11111111-1111-1111-1111-111111111111',
        { output: {}, clips: [], tracks: [] },
        99999,
      );

      // The save succeeds and returns whatever version the bridge returns
      expect(version).toBe(42);
    });

    it('multiple consecutive saves with different stale expectedVersions all succeed', async () => {
      // Because Astrid ignores expectedVersion, every save succeeds
      // regardless of what version the caller thinks the timeline is at.
      // This is the exact scenario where useTimelineOps local invalidation
      // is essential — it must reject stale patches before they reach the
      // provider.
      let callCount = 0;
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        callCount += 1;
        if (url.endsWith('/api/astrid/projects/ados-talks/timelines/11111111-1111-1111-1111-111111111111')) {
          return new Response(JSON.stringify(makePayload()), { status: 200 });
        }
        if (url.endsWith('/registry')) {
          return new Response(JSON.stringify(makePayload().registry), { status: 200 });
        }
        if (url.endsWith('/save')) {
          return new Response(JSON.stringify({
            ...makePayload(),
            config_version: 10 + callCount,
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

      // Three saves, each with a different (and wrong) expectedVersion
      const v1 = await provider.saveTimeline(
        '11111111-1111-1111-1111-111111111111',
        { output: {}, clips: [], tracks: [] },
        1,
      );
      const v2 = await provider.saveTimeline(
        '11111111-1111-1111-1111-111111111111',
        { output: {}, clips: [], tracks: [] },
        5, // stale
      );
      const v3 = await provider.saveTimeline(
        '11111111-1111-1111-1111-111111111111',
        { output: {}, clips: [], tracks: [] },
        999, // very stale
      );

      // All three succeed because Astrid doesn't check expectedVersion
      expect(v1).toBeGreaterThan(0);
      expect(v2).toBeGreaterThan(0);
      expect(v3).toBeGreaterThan(0);
    });

    it('the returned version reflects the bridge state, not the expectedVersion', async () => {
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
            config_version: 77,
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

      // expectedVersion is 5, but the bridge returns version 77
      const version = await provider.saveTimeline(
        '11111111-1111-1111-1111-111111111111',
        { output: {}, clips: [], tracks: [] },
        5,
      );

      expect(version).toBe(77);
      // Version 77 ≠ expectedVersion 5 + 1, proving the bridge ignores
      // expectedVersion entirely and just returns its own head version.
    });

    it('confirms the provider gap that makes useTimelineOps local invalidation essential', async () => {
      // This test explicitly documents why the local monotonic stale
      // invalidation in useTimelineOps.apply() is critical for providers
      // like Astrid that do not enforce CAS:
      //
      // 1. The provider never throws TimelineVersionConflictError
      // 2. Stale writes silently succeed
      // 3. Without the local check, two concurrent editors could
      //    overwrite each other's changes
      //
      // The useTimelineOps.apply() base-version check (patch.version vs
      // dataRef.current.configVersion) catches this BEFORE the provider
      // is called, providing defense-in-depth.

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
            config_version: 100,
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

      // Any expectedVersion, no matter how stale, succeeds
      for (const staleVersion of [1, 2, 5, 10, 50, 9999]) {
        const version = await provider.saveTimeline(
          '11111111-1111-1111-1111-111111111111',
          { output: {}, clips: [], tracks: [] },
          staleVersion,
        );
        expect(version).toBeGreaterThan(0);
      }

      // The provider itself never threw a conflict — the local
      // invalidation in useTimelineOps is the only guard against
      // stale writes for this provider.
    });
  });

  // -------------------------------------------------------------------------
  // M6: Parser-enriched metadata persistence in AstridBridgeDataProvider (T11)
  // -------------------------------------------------------------------------
  describe('M6: parser enrichment in AstridBridgeDataProvider', () => {
    const makeMockParser = (
      id: string,
      extensionId: string,
      overrides = {},
    ) => ({
      descriptor: {
        id,
        extensionId,
        label: 'Parser ' + id,
        acceptMimeTypes: ['video/mp4'],
        ...overrides,
      },
      handler: vi.fn(async () => ({
        metadata: {
          integrity: { sha256: 'abc123' },
          extensions: {
            [extensionId]: { parsed: true },
          },
        },
      })),
    });

    it('enriches upload entries with parser metadata when registeredParsers are configured', async () => {
      const handleTree = createDirectoryHandleTree();
      vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);

      const parser = makeMockParser(
        'com.example.parser.metadata-extractor',
        'com.example.parser',
      );

      const enrichedEntry = {
        file: 'local-drops/demo.mp4',
        type: 'video/mp4',
        duration: 4,
        metadata: {
          integrity: { sha256: 'abc123' },
          extensions: {
            'com.example.parser': { parsed: true },
          },
        },
      };

      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntry,
        diagnostics: [],
        blocked: false,
      });

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef: 'intro-cut',
        timelineId: '11111111-1111-1111-1111-111111111111',
        registeredParsers: [parser],
      });

      const result = await provider.uploadAsset(
        new File(['video'], 'demo.mp4', { type: 'video/mp4' }),
        { timelineId: '11111111-1111-1111-1111-111111111111', userId: 'user-1' },
      );

      // enrichRegistryEntryWithParsers was called
      expect(enrichRegistryEntryWithParsers).toHaveBeenCalledWith(
        expect.any(File),
        expect.objectContaining({
          file: 'local-drops/demo.mp4',
          type: 'video/mp4',
          duration: 4,
        }),
        expect.any(String),
        [parser],
      );

      // registerAsset was called with the enriched entry
      expect(registerAssetSpy).toHaveBeenCalledWith(
        '11111111-1111-1111-1111-111111111111',
        expect.any(String),
        enrichedEntry,
      );

      // The returned result has the enriched entry
      expect(result.entry).toEqual(enrichedEntry);
      expect(result.assetId).toEqual(expect.any(String));
    });

    it('does not call enrichRegistryEntryWithParsers when registeredParsers is undefined', async () => {
      const handleTree = createDirectoryHandleTree();
      vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      // No registeredParsers option
      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef: 'intro-cut',
        timelineId: '11111111-1111-1111-1111-111111111111',
      });

      await provider.uploadAsset(
        new File(['video'], 'demo.mp4', { type: 'video/mp4' }),
        { timelineId: '11111111-1111-1111-1111-111111111111', userId: 'user-1' },
      );

      // enrichRegistryEntryWithParsers must NOT be called
      expect(enrichRegistryEntryWithParsers).not.toHaveBeenCalled();

      // registerAsset was called with the raw entry (no enrichment)
      expect(registerAssetSpy).toHaveBeenCalledWith(
        '11111111-1111-1111-1111-111111111111',
        expect.any(String),
        expect.objectContaining({
          file: 'local-drops/demo.mp4',
          type: 'video/mp4',
          duration: 4,
        }),
      );
    });

    it('preserves existing upload behavior when registeredParsers is an empty array', async () => {
      const handleTree = createDirectoryHandleTree();
      vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      // Empty registeredParsers
      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef: 'intro-cut',
        timelineId: '11111111-1111-1111-1111-111111111111',
        registeredParsers: [],
      });

      const result = await provider.uploadAsset(
        new File(['video'], 'demo.mp4', { type: 'video/mp4' }),
        { timelineId: '11111111-1111-1111-1111-111111111111', userId: 'user-1' },
      );

      // enrichRegistryEntryWithParsers must NOT be called
      expect(enrichRegistryEntryWithParsers).not.toHaveBeenCalled();

      // The entry is the raw extracted entry (no metadata enrichment)
      expect(result.entry).toEqual(expect.objectContaining({
        file: 'local-drops/demo.mp4',
        type: 'video/mp4',
        duration: 4,
      }));
      // No metadata field on unenriched entries
      expect(result.entry.metadata).toBeUndefined();

      expect(registerAssetSpy).toHaveBeenCalledTimes(1);
    });

    it('persists parser-produced enrichment claims and integrity metadata through the upload return value', async () => {
      const handleTree = createDirectoryHandleTree();
      vi.mocked(getDirectoryHandle).mockResolvedValue(handleTree.projectRootHandle);

      const parser = makeMockParser(
        'com.example.claims.parser',
        'com.example.claims',
      );

      const enrichedEntryWithClaims = {
        file: 'local-drops/demo.mp4',
        type: 'video/mp4',
        duration: 4,
        metadata: {
          enrichment: {
            pending: 1,
            failed: 0,
            claims: [
              {
                claimId: 'claim-1',
                parserId: 'com.example.claims',
                timestamp: '2026-06-19T00:00:00.000Z',
                field: 'description',
                summary: 'Analyzed with AI',
              },
            ],
          },
          integrity: { sha256: 'def456' },
        },
      };

      const parserDiagnostics = [
        {
          severity: 'info',
          code: 'parser/claim-enqueued',
          message: 'Enqueued enrichment claim claim-1 for deferred execution.',
          extensionId: 'com.example.claims',
          contributionId: 'com.example.claims.parser',
        },
      ];

      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntryWithClaims,
        diagnostics: parserDiagnostics,
        blocked: false,
      });

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef: 'intro-cut',
        timelineId: '11111111-1111-1111-1111-111111111111',
        registeredParsers: [parser],
      });

      const result = await provider.uploadAsset(
        new File(['video'], 'demo.mp4', { type: 'video/mp4' }),
        { timelineId: '11111111-1111-1111-1111-111111111111', userId: 'user-1' },
      );

      // The enrichment claims are in the persisted entry
      expect(registerAssetSpy).toHaveBeenCalledWith(
        '11111111-1111-1111-1111-111111111111',
        expect.any(String),
        expect.objectContaining({
          metadata: expect.objectContaining({
            enrichment: expect.objectContaining({
              claims: expect.arrayContaining([
                expect.objectContaining({
                  claimId: 'claim-1',
                  parserId: 'com.example.claims',
                }),
              ]),
            }),
            integrity: expect.objectContaining({
              sha256: 'def456',
            }),
          }),
        }),
      );

      // The returned result carries the enriched metadata
      expect(result.entry.metadata).toBeDefined();
      expect(result.entry.metadata.enrichment).toBeDefined();
    });

    it('persists parser-enriched metadata through local save/reload cycle via fetchLocalTimelinePayload', async () => {
      const timelineRef = '01JM4K5N7P0000000000000017';
      const enrichedEntry = {
        file: 'local-drops/test-image.png',
        type: 'image/png',
        metadata: {
          integrity: { algorithm: 'sha256', hash: 'deadbeef1234', size: 100 },
          provenance: { importedAt: '2026-06-19T00:00:00.000Z', source: 'astrid-local-test' },
          enrichment: {
            pending: 1,
            failed: 0,
            claims: [
              {
                claimId: 'claim-1',
                parserId: 'com.example.astrid',
                timestamp: '2026-06-19T00:00:00.000Z',
                field: 'description',
                summary: 'Astrid local test enrichment',
              },
            ],
          },
          extensions: {
            'com.example.astrid': { parsedBy: 'astrid-test-parser', version: 1 },
          },
        },
      };

      // Build the local file system fixture with assembly.json, registry.json, and one asset file
      const localTree = createFileSystemHandleTree({
        'project.json': JSON.stringify({ slug: 'ados-talks' }),
        [`timelines/${timelineRef}/assembly.json`]: JSON.stringify({
          clips: [],
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        }),
        [`timelines/${timelineRef}/registry.json`]: JSON.stringify({
          assets: {},
        }),
        'sources/local-drops/test-image.png': new Blob(['image-bytes'], { type: 'image/png' }),
      });
      vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);

      // Mock parser enrichment to return metadata with integrity, provenance, enrichment claims, and extension namespace
      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntry,
        diagnostics: [],
        blocked: false,
      });

      const parser = makeMockParser(
        'com.example.astrid.parser',
        'com.example.astrid',
      );

      // Spy on registerAsset to prevent HTTP PUT — we want local-only persistence
      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
        registeredParsers: [parser],
      });

      // Upload an asset — enrichRegistryEntryWithParsers is called, then registerAsset (spied)
      const uploadResult = await provider.uploadAsset(
        new File(['image'], 'test-image.png', { type: 'image/png' }),
        { timelineId: timelineRef, userId: 'user-1' },
      );

      // The returned entry must carry parser-enriched metadata
      expect(uploadResult.entry.metadata).toBeDefined();
      expect(uploadResult.entry.metadata.integrity).toBeDefined();
      expect(uploadResult.assetId).toEqual(expect.any(String));

      const assetId = uploadResult.assetId;

      // Save the timeline with the enriched entry — this writes registry.json and assembly.json to local disk
      const version = await provider.saveTimeline(
        timelineRef,
        {
          output: { resolution: '1280x720', fps: 30, file: 'output.mp4' },
          clips: [],
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        },
        1,
        {
          assets: {
            [assetId]: enrichedEntry,
          },
        },
      );

      expect(version).toBeGreaterThanOrEqual(1);

      // Assert registry.json on "disk" contains the enriched metadata (integrity, enrichment claims, extensions)
      const savedRegistry = JSON.parse(
        String(localTree.files[`timelines/${timelineRef}/registry.json`]),
      );
      expect(savedRegistry.assets[assetId]).toBeDefined();
      expect(savedRegistry.assets[assetId].metadata).toBeDefined();
      expect(savedRegistry.assets[assetId].metadata.integrity.hash).toBe('deadbeef1234');
      expect(savedRegistry.assets[assetId].metadata.integrity.algorithm).toBe('sha256');
      expect(savedRegistry.assets[assetId].metadata.integrity.size).toBe(100);
      expect(savedRegistry.assets[assetId].metadata.provenance).toEqual({
        importedAt: '2026-06-19T00:00:00.000Z',
        source: 'astrid-local-test',
      });
      expect(savedRegistry.assets[assetId].metadata.enrichment.pending).toBe(1);
      expect(savedRegistry.assets[assetId].metadata.enrichment.failed).toBe(0);
      expect(savedRegistry.assets[assetId].metadata.enrichment.claims).toHaveLength(1);
      expect(savedRegistry.assets[assetId].metadata.enrichment.claims[0]).toEqual(
        expect.objectContaining({
          claimId: 'claim-1',
          parserId: 'com.example.astrid',
        }),
      );
      expect(savedRegistry.assets[assetId].metadata.extensions['com.example.astrid']).toEqual({
        parsedBy: 'astrid-test-parser',
        version: 1,
      });

      // Verify assembly.json was also written
      const savedAssembly = JSON.parse(
        String(localTree.files[`timelines/${timelineRef}/assembly.json`]),
      );
      expect(savedAssembly.clips).toEqual([]);
      expect(savedAssembly.tracks).toHaveLength(1);

      // -------------------------------------------------------------------
      // Simulate a full reload: a fresh provider instance against the same
      // local file system that calls fetchLocalTimelinePayload() internally
      // -------------------------------------------------------------------
      const reloadedProvider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
        // No registeredParsers on reload — the metadata should already be in registry.json
      });

      const reloadedRegistry = await reloadedProvider.loadAssetRegistry(timelineRef);

      // Assert enriched metadata survived the reload via fetchLocalTimelinePayload
      expect(reloadedRegistry.assets[assetId]).toBeDefined();
      expect(reloadedRegistry.assets[assetId].metadata).toBeDefined();
      expect(reloadedRegistry.assets[assetId].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'deadbeef1234',
        size: 100,
      });
      expect(reloadedRegistry.assets[assetId].metadata.provenance).toEqual({
        importedAt: '2026-06-19T00:00:00.000Z',
        source: 'astrid-local-test',
      });
      expect(reloadedRegistry.assets[assetId].metadata.enrichment.pending).toBe(1);
      expect(reloadedRegistry.assets[assetId].metadata.enrichment.failed).toBe(0);
      expect(reloadedRegistry.assets[assetId].metadata.enrichment.claims).toHaveLength(1);
      expect(reloadedRegistry.assets[assetId].metadata.enrichment.claims[0]).toEqual(
        expect.objectContaining({
          claimId: 'claim-1',
          parserId: 'com.example.astrid',
          field: 'description',
          summary: 'Astrid local test enrichment',
        }),
      );
      expect(reloadedRegistry.assets[assetId].metadata.extensions['com.example.astrid']).toEqual({
        parsedBy: 'astrid-test-parser',
        version: 1,
      });

      // Verify the reloaded provider did NOT make any HTTP calls — it used local files exclusively
      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('exercises the extension authoring loop: read, patch, save, reload — mutation persists, extension source does not', async () => {
      const timelineRef = '01JM4K5N7P0000000000000018';

      const localTree = createFileSystemHandleTree({
        'project.json': JSON.stringify({ slug: 'ados-talks' }),
        [`timelines/${timelineRef}/assembly.json`]: JSON.stringify({
          clips: [],
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        }),
        [`timelines/${timelineRef}/registry.json`]: JSON.stringify({
          assets: {
            'asset-original': {
              file: 'clips/original.mp4',
              type: 'video/mp4',
              duration: 3,
            },
          },
        }),
        'sources/clips/original.mp4': new Blob(['original-video'], { type: 'video/mp4' }),
      });
      vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);

      const parser = makeMockParser(
        'com.example.authoring-loop.parser',
        'com.example.authoring-loop',
        {
          acceptMimeTypes: ['video/mp4'],
        },
      );

      const enrichedEntryPatch = {
        file: 'clips/original.mp4',
        type: 'video/mp4',
        duration: 3,
        metadata: {
          integrity: { algorithm: 'sha256', hash: 'abcdef1234567890', size: 14 },
          provenance: { importedAt: '2026-06-19T10:00:00.000Z', source: 'authoring-loop-test' },
          enrichment: {
            pending: 1,
            failed: 0,
            claims: [
              {
                claimId: 'claim-authoring-1',
                parserId: 'com.example.authoring-loop',
                timestamp: '2026-06-19T10:00:00.000Z',
                field: 'description',
                summary: 'Authoring loop enrichment claim',
              },
            ],
          },
          extensions: {
            'com.example.authoring-loop': { analyzed: true, score: 0.95 },
          },
        },
      };

      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntryPatch,
        diagnostics: [
          {
            severity: 'info',
            code: 'parser/claim-enqueued',
            message: 'Enqueued enrichment claim for authoring loop.',
            extensionId: 'com.example.authoring-loop',
            contributionId: 'com.example.authoring-loop.parser',
          },
        ],
        blocked: false,
      });

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
        registeredParsers: [parser],
      });

      const loaded = await provider.loadTimeline(timelineRef);
      const initialRegistry = await provider.loadAssetRegistry(timelineRef);

      expect(loaded.config.tracks).toHaveLength(1);
      expect(initialRegistry.assets['asset-original']).toBeDefined();
      expect(initialRegistry.assets['asset-original'].file).toBe('clips/original.mp4');

      await provider.registerAsset(timelineRef, 'asset-original', enrichedEntryPatch);

      const secondAssetEntry = {
        file: 'clips/second.mp4',
        type: 'video/mp4',
        duration: 5,
        metadata: {
          integrity: { algorithm: 'sha256', hash: 'deadbeef9999', size: 50 },
          extensions: {
            'com.example.authoring-loop': { analyzed: true, score: 0.8 },
          },
        },
      };
      await provider.registerAsset(timelineRef, 'asset-second', secondAssetEntry);

      const patchedConfig = {
        output: { resolution: '1920x1080', fps: 24, file: 'patched-output.mp4' },
        clips: [
          { id: 'clip-1', assetId: 'asset-original', trackId: 'V1', start: 0, end: 3 },
        ],
        tracks: [
          { id: 'V1', kind: 'visual', label: 'V1' },
          { id: 'A1', kind: 'audio', label: 'A1' },
        ],
      };

      const version = await provider.saveTimeline(
        timelineRef,
        patchedConfig,
        1,
        {
          assets: {
            'asset-original': enrichedEntryPatch,
            'asset-second': secondAssetEntry,
          },
        },
      );
      expect(version).toBeGreaterThanOrEqual(1);

      const savedRegistryRaw = String(localTree.files[`timelines/${timelineRef}/registry.json`]);
      const savedRegistry = JSON.parse(savedRegistryRaw);
      const savedAssemblyRaw = String(localTree.files[`timelines/${timelineRef}/assembly.json`]);
      const savedAssembly = JSON.parse(savedAssemblyRaw);

      expect(savedRegistry.assets['asset-original']).toBeDefined();
      expect(savedRegistry.assets['asset-original'].metadata).toBeDefined();
      expect(savedRegistry.assets['asset-original'].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'abcdef1234567890',
        size: 14,
      });
      expect(savedRegistry.assets['asset-original'].metadata.provenance).toEqual({
        importedAt: '2026-06-19T10:00:00.000Z',
        source: 'authoring-loop-test',
      });
      expect(savedRegistry.assets['asset-original'].metadata.enrichment.pending).toBe(1);
      expect(savedRegistry.assets['asset-original'].metadata.enrichment.claims).toHaveLength(1);
      expect(savedRegistry.assets['asset-original'].metadata.extensions['com.example.authoring-loop']).toEqual({
        analyzed: true,
        score: 0.95,
      });
      expect(savedRegistry.assets['asset-second']).toBeDefined();
      expect(savedRegistry.assets['asset-second'].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'deadbeef9999',
        size: 50,
      });

      expect(savedAssembly.output.resolution).toBe('1920x1080');
      expect(savedAssembly.output.fps).toBe(24);
      expect(savedAssembly.clips).toHaveLength(1);
      expect(savedAssembly.clips[0].assetId).toBe('asset-original');
      expect(savedAssembly.tracks).toHaveLength(2);
      expect(savedAssembly.tracks[1].id).toBe('A1');

      expect(savedRegistryRaw).not.toContain('function');
      expect(savedRegistryRaw).not.toContain('handler');
      expect(savedRegistryRaw).not.toContain('makeMockParser');
      expect(savedRegistryRaw).not.toContain('vi.fn');
      expect(savedAssemblyRaw).not.toContain('function');
      expect(savedAssemblyRaw).not.toContain('handler');
      expect(savedAssemblyRaw).not.toContain('registeredParsers');

      expect(savedRegistryRaw).not.toContain('com.example.authoring-loop.parser');
      expect(savedRegistryRaw).not.toContain('acceptMimeTypes');
      expect(savedAssemblyRaw).not.toContain('com.example.authoring-loop.parser');
      expect(savedAssemblyRaw).not.toContain('acceptMimeTypes');

      expect(savedRegistryRaw).toContain('com.example.authoring-loop');

      const reloadedProvider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
      });

      const reloadedTimeline = await reloadedProvider.loadTimeline(timelineRef);
      const reloadedRegistry = await reloadedProvider.loadAssetRegistry(timelineRef);

      expect(reloadedTimeline.config.output.resolution).toBe('1920x1080');
      expect(reloadedTimeline.config.output.fps).toBe(24);
      expect(reloadedTimeline.config.clips).toHaveLength(1);
      expect(reloadedTimeline.config.tracks).toHaveLength(2);

      expect(reloadedRegistry.assets['asset-original']).toBeDefined();
      expect(reloadedRegistry.assets['asset-original'].metadata).toBeDefined();
      expect(reloadedRegistry.assets['asset-original'].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'abcdef1234567890',
        size: 14,
      });
      expect(reloadedRegistry.assets['asset-original'].metadata.enrichment).toEqual({
        pending: 1,
        failed: 0,
        claims: [
          {
            claimId: 'claim-authoring-1',
            parserId: 'com.example.authoring-loop',
            timestamp: '2026-06-19T10:00:00.000Z',
            field: 'description',
            summary: 'Authoring loop enrichment claim',
          },
        ],
      });
      expect(reloadedRegistry.assets['asset-original'].metadata.extensions).toEqual({
        'com.example.authoring-loop': { analyzed: true, score: 0.95 },
      });
      expect(reloadedRegistry.assets['asset-second']).toBeDefined();
      expect(reloadedRegistry.assets['asset-second'].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'deadbeef9999',
        size: 50,
      });

      expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    // -----------------------------------------------------------------------
    // T26: End-to-end M6 workflow — parser + compile-only export + stub
    //       search provider + asset ingestion + Astrid reload + metadata/search
    //       UI state + deterministic metadata export artifact
    // -----------------------------------------------------------------------
    it('registers a parser, compile-only export, and stub search provider; ingests an asset; persists metadata through Astrid reload; renders metadata/search UI state; and exports a deterministic artifact', async () => {
      const timelineRef = '01JM4K5N7P00000000000000E2E';

      // ---- 1. Create file system tree with assembly.json, registry.json, and assets ----
      const localTree = createFileSystemHandleTree({
        'project.json': JSON.stringify({ slug: 'ados-talks' }),
        [`timelines/${timelineRef}/assembly.json`]: JSON.stringify({
          clips: [],
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        }),
        [`timelines/${timelineRef}/registry.json`]: JSON.stringify({
          assets: {
            'asset-initial': {
              file: 'clips/initial.mp4',
              type: 'video/mp4',
              duration: 3,
            },
          },
        }),
        'sources/clips/initial.mp4': new Blob(['initial-video'], { type: 'video/mp4' }),
      });
      vi.mocked(getDirectoryHandle).mockResolvedValue(localTree.projectRootHandle);

      // ---- 2. Register a parser that produces integrity + provenance + enrichment + extensions ----
      const parser = makeMockParser(
        'com.example.e2e.integrity-parser',
        'com.example.e2e',
        {
          acceptMimeTypes: ['video/mp4'],
        },
      );

      const enrichedEntry = {
        file: 'clips/initial.mp4',
        type: 'video/mp4',
        duration: 3,
        metadata: {
          integrity: { algorithm: 'sha256', hash: 'e2e-hash-abcdef1234567890', size: 14 },
          provenance: { importedAt: '2026-06-19T12:00:00.000Z', source: 'e2e-test', importedBy: 'e2e-runner' },
          enrichment: {
            pending: 1,
            failed: 0,
            claims: [
              {
                claimId: 'e2e-claim-1',
                parserId: 'com.example.e2e',
                timestamp: '2026-06-19T12:00:00.000Z',
                field: 'description',
                summary: 'E2E test enrichment claim',
              },
            ],
          },
          extensions: {
            'com.example.e2e': { parsedBy: 'e2e-parser', version: 1, tags: ['e2e', 'test'] },
          },
        },
      };

      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntry,
        diagnostics: [
          {
            severity: 'info',
            code: 'parser/claim-enqueued',
            message: 'E2E parser produced enrichment claim.',
            extensionId: 'com.example.e2e',
            contributionId: 'com.example.e2e.integrity-parser',
          },
        ],
        blocked: false,
      });

      const registerAssetSpy = vi.spyOn(AstridBridgeDataProvider.prototype, 'registerAsset')
        .mockResolvedValue(undefined);

      // ---- 3. Create provider with registered parsers and upload an asset ----
      const provider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
        registeredParsers: [parser],
      });

      const result = await provider.uploadAsset(
        new File(['e2e-video-data'], 'initial.mp4', { type: 'video/mp4' }),
        { timelineId: timelineRef, userId: 'e2e-runner' },
      );

      // ---- 4. Assert parser enrichment was called and result carries enriched metadata ----
      expect(enrichRegistryEntryWithParsers).toHaveBeenCalled();
      expect(result.entry.metadata).toBeDefined();
      expect(result.entry.metadata.integrity.hash).toBe('e2e-hash-abcdef1234567890');
      expect(result.entry.metadata.provenance.source).toBe('e2e-test');
      expect(result.entry.metadata.enrichment.claims).toHaveLength(1);
      expect(result.entry.metadata.extensions['com.example.e2e']).toEqual({
        parsedBy: 'e2e-parser',
        version: 1,
        tags: ['e2e', 'test'],
      });

      // ---- 5. Save timeline to persist the enriched metadata ----
      const version = await provider.saveTimeline(
        timelineRef,
        {
          output: { resolution: '1920x1080', fps: 30, file: 'e2e-output.mp4' },
          clips: [],
          tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        },
        1,
        {
          assets: {
            'asset-initial': enrichedEntry,
          },
        },
      );
      expect(version).toBeGreaterThanOrEqual(1);

      // Verify on-disk registry.json contains the enriched metadata
      const savedRegistryRaw = String(localTree.files[`timelines/${timelineRef}/registry.json`]);
      const savedRegistry = JSON.parse(savedRegistryRaw);
      expect(savedRegistry.assets['asset-initial'].metadata.integrity.hash).toBe('e2e-hash-abcdef1234567890');
      expect(savedRegistry.assets['asset-initial'].metadata.provenance.source).toBe('e2e-test');
      expect(savedRegistry.assets['asset-initial'].metadata.extensions['com.example.e2e']).toEqual({
        parsedBy: 'e2e-parser',
        version: 1,
        tags: ['e2e', 'test'],
      });
      expect(savedRegistryRaw).not.toContain('handler');
      expect(savedRegistryRaw).not.toContain('makeMockParser');

      // ---- 6. Simulate Astrid reload: fresh provider loads from local files ----
      const reloadedProvider = new AstridBridgeDataProvider({
        projectSlug: 'ados-talks',
        timelineRef,
        timelineId: timelineRef,
      });

      const reloadedRegistry = await reloadedProvider.loadAssetRegistry(timelineRef);

      // Assert enriched metadata survived the reload
      expect(reloadedRegistry.assets['asset-initial']).toBeDefined();
      expect(reloadedRegistry.assets['asset-initial'].metadata).toBeDefined();
      expect(reloadedRegistry.assets['asset-initial'].metadata.integrity).toEqual({
        algorithm: 'sha256',
        hash: 'e2e-hash-abcdef1234567890',
        size: 14,
      });
      expect(reloadedRegistry.assets['asset-initial'].metadata.provenance).toEqual({
        importedAt: '2026-06-19T12:00:00.000Z',
        source: 'e2e-test',
        importedBy: 'e2e-runner',
      });
      expect(reloadedRegistry.assets['asset-initial'].metadata.enrichment.pending).toBe(1);
      expect(reloadedRegistry.assets['asset-initial'].metadata.enrichment.failed).toBe(0);
      expect(reloadedRegistry.assets['asset-initial'].metadata.enrichment.claims).toHaveLength(1);
      expect(reloadedRegistry.assets['asset-initial'].metadata.extensions['com.example.e2e']).toEqual({
        parsedBy: 'e2e-parser',
        version: 1,
        tags: ['e2e', 'test'],
      });
      expect(globalThis.fetch).not.toHaveBeenCalled();

      // ---- 7. Metadata/search UI state assertions (data-level) ----
      // Verify hasSearchableMetadata returns true for host-owned fields
      expect(hasSearchableMetadata(reloadedRegistry.assets['asset-initial'])).toBe(true);

      // Verify shouldShowMetadataSearch returns true when registry has searchable metadata
      expect(shouldShowMetadataSearch(reloadedRegistry.assets)).toBe(true);

      // ---- 8. Stub search provider result integration ----
      const stubProviderResult: SearchProviderResultEnvelope = {
        providerId: 'com.example.e2e.search',
        providerLabel: 'E2E Search Provider',
        providerOrder: 10,
        result: {
          matches: [
            { ref: 'asset-initial', kind: 'asset', score: 0.85, excerpt: 'E2E semantic match' },
            { ref: 'mat-1', kind: 'material', score: 0.75, excerpt: 'Material match from e2e' },
          ],
          totalCount: 2,
          hasMore: false,
          diagnostics: [],
        },
      };

      const mergedResults = mergeSearchProviderResults(
        reloadedRegistry.assets,
        'e2e-hash',
        [stubProviderResult],
      );

      // Assert merge ordering: built-in metadata filter match scores highest
      expect(mergedResults.matches.length).toBeGreaterThanOrEqual(1);
      const assetMatch = mergedResults.matches.find(m => m.ref === 'asset-initial');
      expect(assetMatch).toBeDefined();
      // Built-in metadata filter matches the integrity hash text, so score should be 1.0
      if (assetMatch) {
        expect(assetMatch.matchSource).toBe('metadata-filter');
        expect(assetMatch.score).toBe(1.0);
        expect(assetMatch.sourceProviderId).toBe('__host__');
      }

      // Provider match for the same asset should be present as well
      const providerMatches = mergedResults.matches.filter(m => m.sourceProviderId === 'com.example.e2e.search');
      expect(providerMatches.length).toBeGreaterThanOrEqual(1);

      // Material match should be present
      const matMatch = mergedResults.matches.find(m => m.ref === 'mat-1');
      expect(matMatch).toBeDefined();
      if (matMatch) {
        expect(matMatch.kind).toBe('material');
        expect(matMatch.excerpt).toBe('Material match from e2e');
      }

      // Diagnostics should be empty (no provider errors)
      expect(mergedResults.diagnostics).toEqual([]);

      // ---- 9. Compile-only metadata export artifact ----
      // Build a compile-only output format handler that serializes the asset metadata to JSON
      const exportHandler: OutputFormatHandler = (ctx: OutputFormatContext): CompileOnlyOutputResult => {
        const assetsObj: Record<string, unknown> = {};
        ctx.assets.forEach((meta, key) => {
          assetsObj[key] = {
            integrity: meta.integrity ?? null,
            provenance: meta.provenance ?? null,
            consent: meta.consent ?? null,
            enrichment: meta.enrichment ?? null,
            extensions: meta.extensions ?? null,
          };
        });

        const exportDoc = {
          exportInfo: {
            format: 'metadata-json',
            version: '1.0.0',
            extensionId: ctx.extensionId,
            contributionId: ctx.contributionId,
            exportedAt: '2026-06-19T12:00:00.000Z',
          },
          timeline: {
            projectId: ctx.timeline.projectId,
            baseVersion: ctx.timeline.baseVersion,
            currentVersion: ctx.timeline.currentVersion,
            assetKeys: ctx.timeline.assetKeys,
          },
          assets: assetsObj,
        };

        const json = JSON.stringify(exportDoc);
        return {
          data: new TextEncoder().encode(json),
          mimeType: 'application/json',
          filename: 'metadata-export.json',
          hasBlockingErrors: false,
        };
      };

      const exportContribution: OutputFormatContribution = {
        id: 'com.example.e2e.metadata-json',
        kind: 'outputFormat',
        label: 'E2E Metadata JSON Export',
        requiresRender: false,
        outputExtension: 'json',
        outputMimeType: 'application/json',
        description: 'Deterministic metadata JSON export for e2e test',
        order: 0,
      };

      const registry = createCompileOnlyOutputFormatRegistry([
        {
          contribution: exportContribution,
          handler: exportHandler,
          extensionId: 'com.example.e2e',
          extensionVersion: '1.0.0',
        },
      ]);

      const timelineSnapshot: TimelineSnapshot = {
        projectId: timelineRef,
        baseVersion: 1,
        currentVersion: version,
        extensionRequirements: [],
        clips: [],
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        assetKeys: ['asset-initial'],
        app: {},
      };

      const assetsMap: ReadonlyMap<string, Readonly<AssetMetadata>> = new Map(
        Object.entries(reloadedRegistry.assets).map(([key, entry]) => [key, Object.freeze(entry.metadata ?? {})]),
      );

      const exportResult = executeCompileOnlyOutputSync(registry, {
        formatId: 'com.example.e2e.metadata-json',
        timeline: timelineSnapshot,
        assets: assetsMap,
        extensionId: 'com.example.e2e',
        extensionVersion: '1.0.0',
      });

      // Assert compile-only export succeeded
      expect(exportResult).not.toBeNull();
      expect(exportResult!.hasBlockingErrors).toBe(false);

      // Parse the exported JSON artifact
      const exportedJson = JSON.parse(new TextDecoder().decode(exportResult!.data));
      expect(exportedJson.exportInfo.format).toBe('metadata-json');
      expect(exportedJson.exportInfo.extensionId).toBe('com.example.e2e');
      expect(exportedJson.timeline.assetKeys).toEqual(['asset-initial']);
      expect(exportedJson.assets['asset-initial']).toBeDefined();

      // Assert the enriched metadata is present in the export artifact
      expect(exportedJson.assets['asset-initial'].integrity).toEqual({
        algorithm: 'sha256',
        hash: 'e2e-hash-abcdef1234567890',
        size: 14,
      });
      expect(exportedJson.assets['asset-initial'].provenance).toEqual({
        importedAt: '2026-06-19T12:00:00.000Z',
        source: 'e2e-test',
        importedBy: 'e2e-runner',
      });
      expect(exportedJson.assets['asset-initial'].enrichment.pending).toBe(1);
      expect(exportedJson.assets['asset-initial'].enrichment.claims).toHaveLength(1);
      expect(exportedJson.assets['asset-initial'].extensions).toEqual({
        'com.example.e2e': { parsedBy: 'e2e-parser', version: 1, tags: ['e2e', 'test'] },
      });

      // Assert determinism: two exports produce byte-identical results
      const exportResult2 = executeCompileOnlyOutputSync(registry, {
        formatId: 'com.example.e2e.metadata-json',
        timeline: timelineSnapshot,
        assets: assetsMap,
        extensionId: 'com.example.e2e',
        extensionVersion: '1.0.0',
      });
      expect(exportResult2).not.toBeNull();
      const json1 = new TextDecoder().decode(exportResult!.data);
      const json2 = new TextDecoder().decode(exportResult2!.data);
      expect(json1).toBe(json2);

      // Cleanup
      registerAssetSpy.mockRestore();
    });

  });

});
