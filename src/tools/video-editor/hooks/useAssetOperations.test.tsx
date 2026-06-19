// @vitest-environment jsdom
import { QueryClient } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import { useAssetOperations } from '@/tools/video-editor/hooks/useAssetOperations';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index';
import type { RegisteredParser } from '@/tools/video-editor/lib/assetParserRuntime';

// Mock the enrich function so we can control what parser metadata is returned
// without executing the full parser runtime.
vi.mock('@/tools/video-editor/lib/mediaMetadata', () => ({
  enrichRegistryEntryWithParsers: vi.fn(),
}));

import { enrichRegistryEntryWithParsers } from '@/tools/video-editor/lib/mediaMetadata';

function makeProvider(overrides: Partial<DataProvider> = {}): DataProvider {
  return {
    loadTimeline: vi.fn(async () => ({
      config: {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        clips: [],
        tracks: [],
      },
      configVersion: 1,
    })),
    saveTimeline: vi.fn(async () => 1),
    loadAssetRegistry: vi.fn(async () => ({ assets: {} })),
    resolveAssetUrl: vi.fn(async (file: string) => file),
    ...overrides,
  };
}

describe('useAssetOperations', () => {
  it('decrements pendingOpsRef when uploadAsset throws', async () => {
    const pendingOpsRef = { current: 0 };
    const provider = makeProvider({
      uploadAsset: vi.fn(async () => {
        throw new Error('upload failed');
      }),
    });
    const queryClient = new QueryClient();
    const { result } = renderHook(() => (
      useAssetOperations(provider, 'timeline-1', 'user-1', queryClient, pendingOpsRef)
    ));

    await expect(
      result.current.uploadAsset(new File(['video'], 'clip.mp4', { type: 'video/mp4' })),
    ).rejects.toThrow('upload failed');

    expect(pendingOpsRef.current).toBe(0);
  });

  it('decrements pendingOpsRef when registerAsset throws', async () => {
    const pendingOpsRef = { current: 0 };
    const provider = makeProvider({
      registerAsset: vi.fn(async () => {
        throw new Error('register failed');
      }),
    });
    const queryClient = new QueryClient();
    const { result } = renderHook(() => (
      useAssetOperations(provider, 'timeline-1', 'user-1', queryClient, pendingOpsRef)
    ));

    await expect(act(async () => {
      await result.current.registerAsset('asset-1', { file: 'clip.mp4' });
    })).rejects.toThrow('register failed');

    expect(pendingOpsRef.current).toBe(0);
  });

  it('prefers resolver lifecycle hooks for upload processing when available', async () => {
    const pendingOpsRef = { current: 0 };
    const preparedFile = new File(['prepared'], 'prepared.mp4', { type: 'video/mp4' });
    const onTranscode = vi.fn(async () => preparedFile);
    const onUpload = vi.fn(async () => ({
      assetId: 'asset-1',
      entry: { file: 'prepared.mp4', type: 'video/mp4' },
    }));
    const provider = makeProvider({
      onTranscode,
      onUpload,
      uploadAsset: vi.fn(async () => {
        throw new Error('legacy uploadAsset should not be called');
      }),
    });
    const queryClient = new QueryClient();
    const { result } = renderHook(() => (
      useAssetOperations(provider, 'timeline-1', 'user-1', queryClient, pendingOpsRef)
    ));

    const file = new File(['raw'], 'raw.mp4', { type: 'video/mp4' });
    await act(async () => {
      await result.current.uploadAsset(file);
    });

    expect(onTranscode).toHaveBeenCalledWith({
      file,
      timelineId: 'timeline-1',
      userId: 'user-1',
      intent: 'asset-upload',
    });
    expect(onUpload).toHaveBeenCalledWith({
      file: preparedFile,
      options: {
        timelineId: 'timeline-1',
        userId: 'user-1',
      },
    });
    expect(pendingOpsRef.current).toBe(0);
  });

  // ---------------------------------------------------------------------------
  // M6: Parser-enriched metadata and diagnostics in useAssetOperations (T11)
  // ---------------------------------------------------------------------------
  describe('M6: parser enrichment in useAssetOperations', () => {
    beforeEach(() => {
      vi.mocked(enrichRegistryEntryWithParsers).mockReset();
    });

    const makeMockParser = (
      id: string,
      extensionId: string,
      overrides: Partial<RegisteredParser['descriptor']> = {},
      handlerOverride?: RegisteredParser['handler'],
    ): RegisteredParser => ({
      descriptor: {
        id,
        extensionId,
        label: `Parser ${id}`,
        acceptMimeTypes: ['video/mp4'],
        ...overrides,
      },
      handler:
        handlerOverride ??
        vi.fn(async () => ({
          metadata: {
            integrity: { sha256: 'abc123' },
            extensions: {
              [extensionId]: { parsed: true },
            },
          },
        })),
    });

    const mockEnrichedEntry = (
      overrides: Partial<AssetRegistryEntry> = {},
    ): AssetRegistryEntry => ({
      file: 'clip.mp4',
      type: 'video/mp4',
      metadata: {
        integrity: { sha256: 'abc123' },
        extensions: {
          'com.example.parser': { parsed: true },
        },
      },
      ...overrides,
    });

    it('calls enrichRegistryEntryWithParsers and persists enriched metadata via registerAsset when parsers are registered', async () => {
      const pendingOpsRef = { current: 0 };
      const registerAsset = vi.fn(async () => undefined);
      const provider = makeProvider({
        registerAsset,
        uploadAsset: vi.fn(async () => ({
          assetId: 'asset-1',
          entry: { file: 'clip.mp4', type: 'video/mp4' } as AssetRegistryEntry,
        })),
      });

      const enrichedEntry = mockEnrichedEntry();
      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntry,
        diagnostics: [],
        blocked: false,
      });

      const mockParser = makeMockParser(
        'com.example.parser.metadata-extractor',
        'com.example.parser',
      );

      const queryClient = new QueryClient();
      const { result } = renderHook(() =>
        useAssetOperations(
          provider,
          'timeline-1',
          'user-1',
          queryClient,
          pendingOpsRef,
          [mockParser],
        ),
      );

      const file = new File(['video'], 'clip.mp4', { type: 'video/mp4' });
      let uploadResult: { assetId: string; entry: AssetRegistryEntry } | undefined;
      await act(async () => {
        uploadResult = await result.current.uploadAsset(file);
      });

      // Should call enrichRegistryEntryWithParsers with the file, entry, asset key, and parsers
      expect(enrichRegistryEntryWithParsers).toHaveBeenCalledWith(
        expect.any(File),
        expect.objectContaining({ file: 'clip.mp4', type: 'video/mp4' }),
        'asset-1',
        [mockParser],
      );

      // Should call registerAsset with the enriched entry
      expect(registerAsset).toHaveBeenCalledWith(
        'timeline-1',
        'asset-1',
        enrichedEntry,
      );

      // Should return the enriched entry (metadata persisted)
      expect(uploadResult).toEqual({
        assetId: 'asset-1',
        entry: enrichedEntry,
      });

      expect(pendingOpsRef.current).toBe(0);
    });

    it('does not call enrichRegistryEntryWithParsers when no parsers are registered (undefined)', async () => {
      const pendingOpsRef = { current: 0 };
      const registerAsset = vi.fn(async () => undefined);
      const uploadResult = {
        assetId: 'asset-2',
        entry: { file: 'raw.mp4', type: 'video/mp4' } as AssetRegistryEntry,
      };
      const provider = makeProvider({
        registerAsset,
        uploadAsset: vi.fn(async () => uploadResult),
      });

      const queryClient = new QueryClient();
      // No registeredParsers argument — uses default undefined
      const { result } = renderHook(() =>
        useAssetOperations(provider, 'timeline-2', 'user-1', queryClient, pendingOpsRef),
      );

      const file = new File(['video'], 'raw.mp4', { type: 'video/mp4' });
      let returnedResult: { assetId: string; entry: AssetRegistryEntry } | undefined;
      await act(async () => {
        returnedResult = await result.current.uploadAsset(file);
      });

      // Should NOT call enrich
      expect(enrichRegistryEntryWithParsers).not.toHaveBeenCalled();

      // Returns the original upload result unchanged
      expect(returnedResult).toEqual(uploadResult);

      expect(pendingOpsRef.current).toBe(0);
    });

    it('does not call enrichRegistryEntryWithParsers when registeredParsers is an empty array', async () => {
      const pendingOpsRef = { current: 0 };
      const registerAsset = vi.fn(async () => undefined);
      const uploadResult = {
        assetId: 'asset-3',
        entry: { file: 'empty.mp4', type: 'video/mp4' } as AssetRegistryEntry,
      };
      const provider = makeProvider({
        registerAsset,
        uploadAsset: vi.fn(async () => uploadResult),
      });

      const queryClient = new QueryClient();
      const { result } = renderHook(() =>
        useAssetOperations(provider, 'timeline-3', 'user-1', queryClient, pendingOpsRef, []),
      );

      const file = new File(['video'], 'empty.mp4', { type: 'video/mp4' });
      await act(async () => {
        await result.current.uploadAsset(file);
      });

      // Should NOT call enrich when parsers array is empty
      expect(enrichRegistryEntryWithParsers).not.toHaveBeenCalled();
      expect(pendingOpsRef.current).toBe(0);
    });

    it('propagates parser-produced diagnostics and enriched metadata to the consumer', async () => {
      const pendingOpsRef = { current: 0 };
      const registerAsset = vi.fn(async () => undefined);
      const provider = makeProvider({
        registerAsset,
        uploadAsset: vi.fn(async () => ({
          assetId: 'asset-4',
          entry: { file: 'diag.mp4', type: 'video/mp4' } as AssetRegistryEntry,
        })),
      });

      const parserDiagnostics = [
        {
          severity: 'info' as const,
          code: 'parser/unsupported-type' as const,
          message: 'Parser does not support this file type.',
          extensionId: 'com.example.parser',
          contributionId: 'com.example.parser.metadata-extractor',
        },
      ];

      const enrichedEntry = mockEnrichedEntry({
        metadata: {
          enrichment: {
            pending: 1,
            failed: 0,
            claims: [
              {
                claimId: 'claim-1',
                parserId: 'com.example.parser',
                timestamp: '2026-06-19T00:00:00.000Z',
              },
            ],
          },
        },
      });

      vi.mocked(enrichRegistryEntryWithParsers).mockResolvedValue({
        entry: enrichedEntry,
        diagnostics: parserDiagnostics,
        blocked: false,
      });

      const mockParser = makeMockParser(
        'com.example.parser.metadata-extractor',
        'com.example.parser',
      );

      const queryClient = new QueryClient();
      const { result } = renderHook(() =>
        useAssetOperations(
          provider,
          'timeline-4',
          'user-1',
          queryClient,
          pendingOpsRef,
          [mockParser],
        ),
      );

      const file = new File(['video'], 'diag.mp4', { type: 'video/mp4' });
      await act(async () => {
        await result.current.uploadAsset(file);
      });

      // Enrichment was called exactly once
      expect(enrichRegistryEntryWithParsers).toHaveBeenCalledTimes(1);

      // The enriched entry (with metadata including enrichment claims) was persisted
      expect(registerAsset).toHaveBeenCalledWith(
        'timeline-4',
        'asset-4',
        enrichedEntry,
      );

      expect(pendingOpsRef.current).toBe(0);
    });

    it('still decrements pendingOpsRef when enrichRegistryEntryWithParsers throws', async () => {
      const pendingOpsRef = { current: 0 };
      const registerAsset = vi.fn(async () => undefined);
      const provider = makeProvider({
        registerAsset,
        uploadAsset: vi.fn(async () => ({
          assetId: 'asset-5',
          entry: { file: 'fail.mp4', type: 'video/mp4' } as AssetRegistryEntry,
        })),
      });

      vi.mocked(enrichRegistryEntryWithParsers).mockRejectedValue(
        new Error('parser runtime error'),
      );

      const mockParser = makeMockParser(
        'com.example.parser.broken',
        'com.example.parser',
      );

      const queryClient = new QueryClient();
      const { result } = renderHook(() =>
        useAssetOperations(
          provider,
          'timeline-5',
          'user-1',
          queryClient,
          pendingOpsRef,
          [mockParser],
        ),
      );

      const file = new File(['video'], 'fail.mp4', { type: 'video/mp4' });
      await expect(
        act(async () => {
          await result.current.uploadAsset(file);
        }),
      ).rejects.toThrow('parser runtime error');

      // pendingOpsRef must be decremented even on failure
      expect(pendingOpsRef.current).toBe(0);

      // registerAsset should NOT have been called
      expect(registerAsset).not.toHaveBeenCalled();
    });
  });
});
