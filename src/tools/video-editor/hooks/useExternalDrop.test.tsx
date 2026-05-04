// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  GENERATION_MULTI_DRAG_TYPE,
  setMultiGenerationDragData,
  setShotDragData,
  type GenerationDropData,
  type ShotDropData,
} from '@/shared/lib/dnd/dragDrop';
import { useExternalDrop } from './useExternalDrop';

const mockUseShots = vi.fn(() => ({
  shots: undefined,
  isLoading: false,
  error: null,
  refetchShots: vi.fn(),
}));
const mockUseFinalVideoAvailable = vi.fn(() => ({
  finalVideoMap: new Map(),
  dismissFinalVideo: vi.fn(),
}));
const mockExtractVideoMetadataFromUrl = vi.fn();

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => mockUseShots(),
}));

vi.mock('@/tools/video-editor/hooks/useFinalVideoAvailable', () => ({
  useFinalVideoAvailable: () => mockUseFinalVideoAvailable(),
}));

vi.mock('@/shared/lib/media/videoMetadata', () => ({
  extractVideoMetadataFromUrl: (...args: unknown[]) => mockExtractVideoMetadataFromUrl(...args),
}));

function createStoredDragPayload(items: GenerationDropData[]) {
  const storedData: Record<string, string> = {};
  const dragStartEvent = {
    dataTransfer: {
      effectAllowed: 'none',
      setData: (type: string, value: string) => {
        storedData[type] = value;
      },
    },
  } as unknown as React.DragEvent;

  setMultiGenerationDragData(dragStartEvent, items);
  return storedData;
}

function createStoredShotPayload(item: ShotDropData) {
  const storedData: Record<string, string> = {};
  const dragStartEvent = {
    dataTransfer: {
      effectAllowed: 'none',
      setData: (type: string, value: string) => {
        storedData[type] = value;
      },
    },
  } as unknown as React.DragEvent;

  setShotDragData(dragStartEvent, item);
  return storedData;
}

function createDropEvent(data: Record<string, string>, types: string[] = [GENERATION_MULTI_DRAG_TYPE, 'text/plain']) {
  return {
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    clientX: 120,
    clientY: 48,
    currentTarget: { dataset: {} as Record<string, string> },
    dataTransfer: {
      types,
      files: [],
      items: [],
      getData: (type: string) => data[type] ?? '',
      setData: vi.fn(),
    },
  } as unknown as React.DragEvent<HTMLDivElement>;
}

function createFileDropEvent(files: File[]) {
  return {
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    clientX: 120,
    clientY: 48,
    currentTarget: { dataset: {} as Record<string, string> },
    dataTransfer: {
      types: ['Files'],
      files,
      items: [],
      getData: vi.fn(() => ''),
      setData: vi.fn(),
    },
  } as unknown as React.DragEvent<HTMLDivElement>;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });

  return { promise, resolve, reject };
}

type DropTestData = {
  config: {
    output: { resolution: string; fps: number; file: string };
    clips: [];
    pinnedShotGroups?: Array<{
      shotId: string;
      trackId: string;
      clipIds: string[];
      mode: 'images' | 'video';
    }>;
  };
  tracks: Array<{ id: string; kind: 'visual'; label: string }>;
  rows: Array<{ id: string; actions: Array<{ id: string; start: number; end: number; effectId: string }> }>;
  meta: Record<string, { track: string; asset?: string; clipType?: string; hold?: number }>;
  clipOrder: Record<string, string[]>;
  registry: { assets: Record<string, { file: string; type?: string; duration?: number }> };
};

function makeDropTestData(overrides: Partial<DropTestData> = {}): DropTestData {
  return {
    config: {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      clips: [],
      ...overrides.config,
    },
    tracks: overrides.tracks ?? [{ id: 'V1', kind: 'visual', label: 'V1' }],
    rows: overrides.rows ?? [{ id: 'V1', actions: [] }],
    meta: overrides.meta ?? {},
    clipOrder: overrides.clipOrder ?? { V1: [] },
    registry: overrides.registry ?? { assets: {} },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  mockUseShots.mockReset();
  mockUseShots.mockReturnValue({
    shots: undefined,
    isLoading: false,
    error: null,
    refetchShots: vi.fn(),
  });
  mockUseFinalVideoAvailable.mockReset();
  mockUseFinalVideoAvailable.mockReturnValue({
    finalVideoMap: new Map(),
    dismissFinalVideo: vi.fn(),
  });
  mockExtractVideoMetadataFromUrl.mockReset();
});

describe('useExternalDrop', () => {
  it('accepts generation-multi drags during drag over', () => {
    const dataRef = { current: null } as React.MutableRefObject<DropTestData | null>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const event = createDropEvent({
      [GENERATION_MULTI_DRAG_TYPE]: JSON.stringify([{
        generationId: 'gen-1',
        imageUrl: 'https://example.com/image.png',
      }]),
      'text/plain': '__reigh_generation_multi__:[{"generationId":"gen-1","imageUrl":"https://example.com/image.png"}]',
    });

    const coordinator = {
      update: vi.fn(() => ({
        time: 0,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isReject: false,
        isNewTrackTop: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      })),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: null,
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit: vi.fn(),
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn() },
      coordinator,
      registerGenerationAsset: vi.fn(),
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop: vi.fn(),
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    result.current.onTimelineDragOver(event);

    expect(event.preventDefault).toHaveBeenCalled();
    expect(event.currentTarget.dataset.dragOver).toBe('true');
  });

  it('drops multi-generation payloads sequentially and checks the multi payload before the single payload', async () => {
    const dataRef = {
      current: makeDropTestData({
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        rows: [],
        clipOrder: { V1: [] },
        registry: { assets: {} as Record<string, { file: string; type?: string; duration?: number }> },
      }),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;

    const patchRegistry = vi.fn((assetId: string, entry: { file: string; type?: string; duration?: number }) => {
      dataRef.current.registry.assets[assetId] = entry;
    });
    const registerGenerationAsset = vi.fn((generation: GenerationDropData & { durationSeconds?: number; assetId?: string }) => {
      const assetId = generation.assetId ?? `asset-${generation.generationId}`;
      const type = generation.variantType === 'video' ? 'video/mp4' : 'image/png';
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type,
        ...(typeof generation.durationSeconds === 'number' ? { duration: generation.durationSeconds } : {}),
      };
      return assetId;
    });
    const handleAssetDrop = vi.fn((
      _assetKey: string,
      trackId: string | undefined,
      _time: number,
      forceNewTrack?: boolean,
      insertAtTop?: boolean,
    ) => {
      if (!forceNewTrack) {
        return;
      }

      const newTrack = { id: 'V2', kind: 'visual', label: 'V2' };
      dataRef.current = {
        ...dataRef.current,
        tracks: insertAtTop
          ? [newTrack, ...dataRef.current.tracks]
          : [...dataRef.current.tracks, newTrack],
        rows: insertAtTop
          ? [{ id: 'V2', actions: [] }, ...dataRef.current.rows]
          : [...dataRef.current.rows, { id: 'V2', actions: [] }],
        clipOrder: {
          ...dataRef.current.clipOrder,
          V2: [],
        },
      };

      if (trackId) {
        throw new Error('expected first multi-drop to create a new track');
      }
    });

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: undefined,
        trackKind: 'visual',
        trackName: '',
        isNewTrack: true,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: 'visual',
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit: vi.fn(),
      patchRegistry,
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn() },
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop,
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const multiItems: GenerationDropData[] = [
      {
        generationId: 'gen-video',
        variantType: 'video',
        imageUrl: 'https://example.com/video.mp4',
        metadata: {
          content_type: 'video/mp4',
          duration_seconds: 8,
        },
      },
      {
        generationId: 'gen-image',
        variantType: 'image',
        imageUrl: 'https://example.com/image.png',
        metadata: {
          content_type: 'image/png',
        },
      },
    ];
    const storedData = createStoredDragPayload(multiItems);
    const event = createDropEvent(storedData);

    await result.current.onTimelineDrop(event);

    expect(registerGenerationAsset).toHaveBeenCalledTimes(2);
    expect(registerGenerationAsset).toHaveBeenNthCalledWith(1, expect.objectContaining({
      generationId: 'gen-video',
      durationSeconds: 8,
    }));
    const firstRegisteredAssetId = registerGenerationAsset.mock.calls[0]?.[0]?.assetId as string;
    const secondRegisteredAssetId = registerGenerationAsset.mock.calls[1]?.[0]?.assetId as string;
    expect(handleAssetDrop).toHaveBeenNthCalledWith(1, firstRegisteredAssetId, undefined, 12, true, false);
    expect(handleAssetDrop).toHaveBeenNthCalledWith(2, secondRegisteredAssetId, 'V2', 20, false, false);
    expect(dataRef.current.registry.assets[firstRegisteredAssetId]).toEqual({
      file: 'https://example.com/video.mp4',
      type: 'video/mp4',
      duration: 8,
    });
  });

  it('tracks pending uploads per file until each async upload settles', async () => {
    const dataRef = {
      current: makeDropTestData({
        tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
        rows: [{ id: 'V1', actions: [] }],
        clipOrder: { V1: [] },
        registry: { assets: {} as Record<string, { file: string; type?: string; duration?: number }> },
      }),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const firstUpload = deferred<{
      generationId: string;
      variantType: 'video';
      imageUrl: string;
      thumbUrl: string;
      durationSeconds?: number;
      metadata: {
        content_type: string;
        original_filename: string;
      };
    }>();
    const secondUpload = deferred<{
      generationId: string;
      variantType: 'video';
      imageUrl: string;
      thumbUrl: string;
      durationSeconds?: number;
      metadata: {
        content_type: string;
        original_filename: string;
      };
    }>();
    const uploadQueue = [firstUpload, secondUpload];

    const applyEdit = vi.fn();
    const uploadVideoGeneration = vi
      .fn<(file: File) => Promise<{
        generationId: string;
        variantType: 'video';
        imageUrl: string;
        thumbUrl: string;
        durationSeconds?: number;
        metadata: {
          content_type: string;
          original_filename: string;
        };
      }>>()
      .mockImplementation(() => {
        const nextUpload = uploadQueue.shift();
        if (!nextUpload) {
          throw new Error('unexpected upload');
        }

        return nextUpload.promise;
      });
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn(async (file: string) => `https://cdn.example/${file}`) },
      coordinator,
      registerGenerationAsset: vi.fn(),
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration,
      handleAssetDrop: vi.fn(),
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createFileDropEvent([
      new File(['one'], 'one.mp4', { type: 'video/mp4' }),
      new File(['two'], 'two.mp4', { type: 'video/mp4' }),
    ]);

    await act(async () => {
      await result.current.onTimelineDrop(event);
    });

    expect(uploadVideoGeneration).toHaveBeenCalledTimes(2);
    expect(pendingOpsRef.current).toBe(2);

    firstUpload.resolve({
      generationId: 'gen-1',
      variantType: 'video',
      imageUrl: 'https://cdn.example/one.mp4',
      thumbUrl: 'https://cdn.example/one.jpg',
      durationSeconds: 4,
      metadata: {
        content_type: 'video/mp4',
        original_filename: 'one.mp4',
      },
    });
    await waitFor(() => {
      expect(pendingOpsRef.current).toBe(1);
    });

    secondUpload.reject(new Error('upload failed'));
    await waitFor(() => {
      expect(pendingOpsRef.current).toBe(0);
    });

    expect(consoleError).toHaveBeenCalledWith('[drop] Upload failed:', expect.any(Error));
    expect(applyEdit).toHaveBeenCalled();
  });

  it('drops a shot as one rows edit with group start plus ordered children from loop state and never calls handleAssetDrop', async () => {
    mockUseShots.mockReturnValue({
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/1.png', thumbUrl: 'https://example.com/1-thumb.png', contentType: 'image/png', type: 'image' },
          { generation_id: 'gen-2', imageUrl: 'https://example.com/2.png', thumbUrl: 'https://example.com/2-thumb.png', contentType: 'image/png', type: 'image' },
        ],
      }],
      isLoading: false,
      error: null,
      refetchShots: vi.fn(),
    });

    const dataRef = {
      current: makeDropTestData(),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const applyEdit = vi.fn();
    const handleAssetDrop = vi.fn();
    const registerGenerationAsset = vi.fn((generation: GenerationDropData) => {
      const assetId = `asset-${generation.generationId}`;
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: 'image/png',
      };
      return assetId;
    });

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn() },
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop,
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createDropEvent(
      createStoredShotPayload({
        shotId: 'shot-1',
        shotName: 'Shot 1',
        imageGenerationIds: ['gen-1', 'gen-2'],
      }),
      ['application/x-shot', 'text/plain'],
    );

    await result.current.onTimelineDrop(event);

    expect(registerGenerationAsset).toHaveBeenCalledTimes(2);
    expect(handleAssetDrop).not.toHaveBeenCalled();
    expect(applyEdit).toHaveBeenCalledTimes(1);

    const [mutation, options] = applyEdit.mock.calls[0];
    const createdClipIds = mutation.rows[0].actions.map((action: { id: string }) => action.id);
    expect(mutation.type).toBe('rows');
    expect(mutation.pinnedShotGroupsOverride).toEqual([{
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: createdClipIds,
      mode: 'images',
    }]);
    expect(mutation.rows).toEqual([{
      id: 'V1',
      actions: [
        { id: createdClipIds[0], start: 12, end: 17, effectId: `effect-${createdClipIds[0]}` },
        { id: createdClipIds[1], start: 17, end: 22, effectId: `effect-${createdClipIds[1]}` },
      ],
    }]);
    expect(mutation.clipOrderOverride).toEqual({ V1: createdClipIds });
    expect(Object.keys(mutation.metaUpdates)).toEqual(createdClipIds);
    expect(options).toEqual({ selectedClipId: createdClipIds[0], selectedTrackId: 'V1' });
  });

  it('drops a shot to its final video by default when one exists', async () => {
    mockUseShots.mockReturnValue({
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/1.png', thumbUrl: 'https://example.com/1-thumb.png', contentType: 'image/png', type: 'image' },
        ],
      }],
      isLoading: false,
      error: null,
      refetchShots: vi.fn(),
    });
    mockUseFinalVideoAvailable.mockReturnValue({
      finalVideoMap: new Map([[
        'shot-1',
        {
          id: 'final-1',
          location: 'https://example.com/final.mp4',
          thumbnailUrl: 'https://example.com/final-thumb.jpg',
        },
      ]]),
      dismissFinalVideo: vi.fn(),
    });
    mockExtractVideoMetadataFromUrl.mockResolvedValue({
      duration_seconds: 3.5,
      frame_rate: 30,
      total_frames: 105,
      width: 1920,
      height: 1080,
      file_size: 0,
    });

    const dataRef = {
      current: makeDropTestData(),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const applyEdit = vi.fn();
    const handleAssetDrop = vi.fn();
    const registerGenerationAsset = vi.fn((generation: GenerationDropData & { durationSeconds?: number }) => {
      const assetId = `asset-${generation.generationId}`;
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: generation.variantType === 'video' ? 'video/mp4' : 'image/png',
        ...(typeof generation.durationSeconds === 'number' ? { duration: generation.durationSeconds } : {}),
      };
      return assetId;
    });

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn() },
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop,
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createDropEvent(
      createStoredShotPayload({
        shotId: 'shot-1',
        shotName: 'Shot 1',
        imageGenerationIds: ['gen-1'],
      }),
      ['application/x-shot', 'text/plain'],
    );

    await result.current.onTimelineDrop(event);

    expect(registerGenerationAsset).toHaveBeenCalledTimes(1);
    expect(registerGenerationAsset).toHaveBeenCalledWith(expect.objectContaining({
      generationId: 'final-1',
      variantType: 'video',
      imageUrl: 'https://example.com/final.mp4',
      thumbUrl: 'https://example.com/final-thumb.jpg',
      durationSeconds: 3.5,
    }));
    expect(handleAssetDrop).not.toHaveBeenCalled();

    const [mutation, options] = applyEdit.mock.calls[0];
    const createdClipId = mutation.rows[0].actions[0].id;
    expect(mutation.pinnedShotGroupsOverride).toEqual([{
      shotId: 'shot-1',
      trackId: 'V1',
      clipIds: [createdClipId],
      mode: 'video',
      videoAssetKey: 'asset-final-1',
    }]);
    expect(mutation.rows).toEqual([{
      id: 'V1',
      actions: [
        { id: createdClipId, start: 12, end: 15.5, effectId: `effect-${createdClipId}` },
      ],
    }]);
    expect(options).toEqual({ selectedClipId: createdClipId, selectedTrackId: 'V1' });
  });

  it('retries final video duration resolution once before falling back to five seconds', async () => {
    mockUseShots.mockReturnValue({
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/1.png', thumbUrl: 'https://example.com/1-thumb.png', contentType: 'image/png', type: 'image' },
        ],
      }],
      isLoading: false,
      error: null,
      refetchShots: vi.fn(),
    });
    mockUseFinalVideoAvailable.mockReturnValue({
      finalVideoMap: new Map([[
        'shot-1',
        {
          id: 'final-1',
          location: 'https://example.com/final.mp4',
          thumbnailUrl: 'https://example.com/final-thumb.jpg',
        },
      ]]),
      dismissFinalVideo: vi.fn(),
    });
    mockExtractVideoMetadataFromUrl
      .mockResolvedValueOnce({
        duration_seconds: undefined,
      })
      .mockResolvedValueOnce({
        duration_seconds: 3.5,
        frame_rate: 30,
        total_frames: 105,
        width: 1920,
        height: 1080,
        file_size: 0,
      });

    const dataRef = {
      current: makeDropTestData(),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const applyEdit = vi.fn();
    const registerGenerationAsset = vi.fn((generation: GenerationDropData & { durationSeconds?: number }) => {
      const assetId = `asset-${generation.generationId}`;
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: generation.variantType === 'video' ? 'video/mp4' : 'image/png',
        ...(typeof generation.durationSeconds === 'number' ? { duration: generation.durationSeconds } : {}),
      };
      return assetId;
    });

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      timelineId: 'timeline-1',
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      assetResolver: { resolveAssetUrl: vi.fn() },
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop: vi.fn(),
      shots: mockUseShots().shots,
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createDropEvent(
      createStoredShotPayload({
        shotId: 'shot-1',
        shotName: 'Shot 1',
        imageGenerationIds: ['gen-1'],
      }),
      ['application/x-shot', 'text/plain'],
    );

    await result.current.onTimelineDrop(event);

    expect(mockExtractVideoMetadataFromUrl).toHaveBeenCalledTimes(2);
    expect(registerGenerationAsset).toHaveBeenCalledWith(expect.objectContaining({
      durationSeconds: 3.5,
    }));
    expect(applyEdit.mock.calls[0][0].rows[0].actions[0]).toEqual(expect.objectContaining({
      start: 12,
      end: 15.5,
    }));
  });

  it('keeps the registry duration unset but inserts a five-second clip when final video duration stays unresolved', async () => {
    mockUseShots.mockReturnValue({
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/1.png', thumbUrl: 'https://example.com/1-thumb.png', contentType: 'image/png', type: 'image' },
        ],
      }],
      isLoading: false,
      error: null,
      refetchShots: vi.fn(),
    });
    mockUseFinalVideoAvailable.mockReturnValue({
      finalVideoMap: new Map([[
        'shot-1',
        {
          id: 'final-1',
          location: 'https://example.com/final.mp4',
          thumbnailUrl: 'https://example.com/final-thumb.jpg',
        },
      ]]),
      dismissFinalVideo: vi.fn(),
    });
    mockExtractVideoMetadataFromUrl
      .mockResolvedValueOnce({ duration_seconds: undefined })
      .mockResolvedValueOnce({ duration_seconds: undefined });

    const dataRef = {
      current: makeDropTestData(),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const applyEdit = vi.fn();
    const registerGenerationAsset = vi.fn((generation: GenerationDropData & { durationSeconds?: number; assetId?: string }) => {
      const assetId = generation.assetId ?? `asset-${generation.generationId}`;
      dataRef.current.registry.assets[assetId] = {
        file: generation.imageUrl,
        type: 'video/mp4',
        ...(typeof generation.durationSeconds === 'number' ? { duration: generation.durationSeconds } : {}),
      };
      return assetId;
    });

    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: false,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: null,
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop: vi.fn(),
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createDropEvent(
      createStoredShotPayload({
        shotId: 'shot-1',
        shotName: 'Shot 1',
        imageGenerationIds: ['gen-1'],
      }),
      ['application/x-shot', 'text/plain'],
    );

    await result.current.onTimelineDrop(event);

    expect(mockExtractVideoMetadataFromUrl).toHaveBeenCalledTimes(2);
    expect(registerGenerationAsset).toHaveBeenCalledWith(expect.not.objectContaining({
      durationSeconds: expect.any(Number),
    }));
    expect(applyEdit.mock.calls[0][0].rows[0].actions[0]).toEqual(expect.objectContaining({
      start: 12,
      end: 17,
    }));
  });

  it('does not create a new track or patch assets when final video registration planning fails', async () => {
    mockUseShots.mockReturnValue({
      shots: [{
        id: 'shot-1',
        name: 'Shot 1',
        images: [
          { generation_id: 'gen-1', imageUrl: 'https://example.com/1.png', thumbUrl: 'https://example.com/1-thumb.png', contentType: 'image/png', type: 'image' },
        ],
      }],
      isLoading: false,
      error: null,
      refetchShots: vi.fn(),
    });
    mockUseFinalVideoAvailable.mockReturnValue({
      finalVideoMap: new Map([[
        'shot-1',
        {
          id: 'final-1',
          location: '',
          thumbnailUrl: null,
        },
      ]]),
      dismissFinalVideo: vi.fn(),
    });
    mockExtractVideoMetadataFromUrl.mockResolvedValue({ duration_seconds: 4 });

    const dataRef = {
      current: makeDropTestData(),
    } as React.MutableRefObject<DropTestData>;
    const pendingOpsRef = { current: 0 } as React.MutableRefObject<number>;
    const applyEdit = vi.fn();
    const registerGenerationAsset = vi.fn();
    const coordinator = {
      update: vi.fn(),
      showSecondaryGhosts: vi.fn(),
      end: vi.fn(),
      lastPosition: {
        time: 12,
        rowIndex: 0,
        trackId: 'V1',
        trackKind: 'visual',
        trackName: 'V1',
        isNewTrack: true,
        isNewTrackTop: false,
        isReject: false,
        newTrackKind: 'visual',
        screenCoords: {
          rowTop: 0,
          rowLeft: 0,
          rowWidth: 0,
          rowHeight: 0,
          clipLeft: 0,
          clipWidth: 0,
          ghostCenter: 0,
        },
      },
      editAreaRef: { current: null },
    };

    const { result } = renderHook(() => useExternalDrop({
      dataRef,
      pendingOpsRef,
      scale: 1,
      scaleWidth: 1,
      selectedTrackId: null,
      applyEdit,
      patchRegistry: vi.fn(),
      registerAsset: vi.fn(),
      uploadAsset: vi.fn(),
      invalidateAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(),
      coordinator,
      registerGenerationAsset,
      uploadImageGeneration: vi.fn(),
      uploadVideoGeneration: vi.fn(),
      handleAssetDrop: vi.fn(),
      finalVideoMap: mockUseFinalVideoAvailable().finalVideoMap,
    }));

    const event = createDropEvent(
      createStoredShotPayload({
        shotId: 'shot-1',
        shotName: 'Shot 1',
        imageGenerationIds: ['gen-1'],
      }),
      ['application/x-shot', 'text/plain'],
    );

    await result.current.onTimelineDrop(event);

    expect(registerGenerationAsset).not.toHaveBeenCalled();
    expect(applyEdit).not.toHaveBeenCalled();
    expect(dataRef.current.tracks).toEqual([{ id: 'V1', kind: 'visual', label: 'V1' }]);
    expect(dataRef.current.rows).toEqual([{ id: 'V1', actions: [] }]);
  });
});
