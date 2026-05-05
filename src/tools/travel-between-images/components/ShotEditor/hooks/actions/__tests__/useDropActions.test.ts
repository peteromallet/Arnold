// @vitest-environment jsdom

import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, beforeEach, afterAll, describe, expect, it, vi } from 'vitest';
import type { Shot, GenerationRow } from '@/domains/generation/types';
import { generationQueryKeys } from '@/shared/lib/queryKeys/generations';
import { useDropActions } from '../useDropActions';

const {
  addImageToShotMutateAsyncMock,
  cropImagesToShotAspectRatioMock,
  demoteOrphanedVariantsMock,
  enqueueVariantInvalidationMock,
  fetchNextAvailableFrameForShotMock,
  fromMock,
  generationVariantsInsertMock,
  handleExternalImageDropMutateAsyncMock,
  normalizeAndPresentErrorMock,
  persistTimelinePositionsMock,
  selectEqMock,
  selectMock,
  shotGenerationsLimitMock,
  shotGenerationsInMock,
  supabaseClientMock,
  toastErrorMock,
  updateShotAspectRatioMock,
  uploadImageForVariantMock,
  useAddImageToShotMock,
  useHandleExternalImageDropMock,
  useProjectMock,
  useToolSettingsMock,
} = vi.hoisted(() => ({
  addImageToShotMutateAsyncMock: vi.fn(),
  cropImagesToShotAspectRatioMock: vi.fn(),
  demoteOrphanedVariantsMock: vi.fn(),
  enqueueVariantInvalidationMock: vi.fn(),
  fetchNextAvailableFrameForShotMock: vi.fn(),
  fromMock: vi.fn(),
  generationVariantsInsertMock: vi.fn(),
  handleExternalImageDropMutateAsyncMock: vi.fn(),
  normalizeAndPresentErrorMock: vi.fn(),
  persistTimelinePositionsMock: vi.fn(),
  selectEqMock: vi.fn(),
  selectMock: vi.fn(),
  shotGenerationsLimitMock: vi.fn(),
  shotGenerationsInMock: vi.fn(),
  supabaseClientMock: vi.fn(),
  toastErrorMock: vi.fn(),
  updateShotAspectRatioMock: vi.fn(),
  uploadImageForVariantMock: vi.fn(),
  useAddImageToShotMock: vi.fn(),
  useHandleExternalImageDropMock: vi.fn(),
  useProjectMock: vi.fn(),
  useToolSettingsMock: vi.fn(),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: toastErrorMock,
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: normalizeAndPresentErrorMock,
}));

vi.mock('@/shared/hooks/invalidation/useGenerationInvalidation', () => ({
  enqueueVariantInvalidation: enqueueVariantInvalidationMock,
}));

vi.mock('@/shared/lib/media/createGenerationFromFile', () => ({
  uploadImageForVariant: uploadImageForVariantMock,
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: useProjectMock,
  useProjectSelectionContext: () => ({
    selectedProjectId: 'project-1',
    project: null,
    setSelectedProjectId: vi.fn(),
  }),
  useProjectCrudContext: () => ({
    projects: [],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  }),
  useProjectIdentityContext: () => ({ userId: null }),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: useToolSettingsMock,
}));

vi.mock('@/shared/hooks/shots', () => ({
  useAddImageToShot: useAddImageToShotMock,
  useHandleExternalImageDrop: useHandleExternalImageDropMock,
  useUpdateShotAspectRatio: () => ({
    updateShotAspectRatio: updateShotAspectRatioMock,
  }),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: supabaseClientMock,
}));

vi.mock('../../editor-state/timelineDropHelpers', () => ({
  cropImagesToShotAspectRatio: cropImagesToShotAspectRatioMock,
  fetchNextAvailableFrameForShot: fetchNextAvailableFrameForShotMock,
  persistTimelinePositions: persistTimelinePositionsMock,
}));

vi.mock('../../../../hooks/workflow/useDemoteOrphanedVariants', () => ({
  useDemoteOrphanedVariants: () => ({
    demoteOrphanedVariants: demoteOrphanedVariantsMock,
  }),
}));

type ProbeBehavior = {
  readerMode: 'load' | 'error';
  imageMode: 'load' | 'error';
  width: number;
  height: number;
};

const probeBehavior: ProbeBehavior = {
  readerMode: 'load',
  imageMode: 'load',
  width: 1920,
  height: 1080,
};

const originalFileReader = globalThis.FileReader;
const originalImage = globalThis.Image;
const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

class MockFileReader {
  onload: ((event: ProgressEvent<FileReader>) => void) | null = null;
  onerror: ((event: ProgressEvent<FileReader>) => void) | null = null;

  readAsDataURL(_file: File) {
    if (probeBehavior.readerMode === 'error') {
      this.onerror?.(new ProgressEvent('error') as ProgressEvent<FileReader>);
      return;
    }

    this.onload?.({
      target: {
        result: 'data:image/png;base64,mock',
      },
    } as ProgressEvent<FileReader>);
  }
}

class MockImage {
  onload: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  width = 0;
  height = 0;

  set src(_value: string) {
    if (probeBehavior.imageMode === 'error') {
      this.onerror?.(new Event('error'));
      return;
    }

    this.width = probeBehavior.width;
    this.height = probeBehavior.height;
    this.onload?.(new Event('load'));
  }
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function createFile(name: string = 'drop.png') {
  return new File(['image'], name, { type: 'image/png' });
}

function createSelectedShot(overrides: Partial<Shot> = {}): Shot {
  return {
    id: 'shot-1',
    name: 'Shot 1',
    aspect_ratio: '1:1',
    ...overrides,
  } as Shot;
}

function renderUseDropActions({
  selectedShot = createSelectedShot(),
  cropToProjectSize = true,
  queryClient = createQueryClient(),
}: {
  selectedShot?: Shot;
  cropToProjectSize?: boolean;
  queryClient?: QueryClient;
} = {}) {
  useToolSettingsMock.mockReturnValue({
    settings: { cropToProjectSize },
  });

  const setUploadingImage = vi.fn();
  const setAutoAdjustedAspectRatio = vi.fn();
  const { result } = renderHook(
    () => useDropActions({
      actions: {
        setUploadingImage,
        setAutoAdjustedAspectRatio,
      },
      selectedShot,
      projectId: 'project-1',
      batchVideoFrames: 12,
    }),
    {
      wrapper: createWrapper(queryClient),
    }
  );

  return {
    result,
    queryClient,
    actions: {
      setUploadingImage,
      setAutoAdjustedAspectRatio,
    },
  };
}

describe('useDropActions', () => {
  beforeAll(() => {
    vi.stubGlobal('FileReader', MockFileReader as unknown as typeof FileReader);
    vi.stubGlobal('Image', MockImage as unknown as typeof Image);
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(() => 'blob:optimistic-image'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  afterAll(() => {
    vi.stubGlobal('FileReader', originalFileReader);
    vi.stubGlobal('Image', originalImage);
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: originalCreateObjectURL,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: originalRevokeObjectURL,
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();

    probeBehavior.readerMode = 'load';
    probeBehavior.imageMode = 'load';
    probeBehavior.width = 1920;
    probeBehavior.height = 1080;

    shotGenerationsLimitMock.mockResolvedValue({
      data: [{ id: 'sg-1', timeline_frame: 12 }],
      error: null,
    });
    generationVariantsInsertMock.mockResolvedValue({ error: null });
    shotGenerationsInMock.mockReturnValue({ limit: shotGenerationsLimitMock });
    selectEqMock.mockReturnValue({ in: shotGenerationsInMock });
    selectMock.mockReturnValue({ eq: selectEqMock });
    fromMock.mockImplementation((table: string) => {
      if (table === 'generation_variants') {
        return { insert: generationVariantsInsertMock };
      }
      return { select: selectMock };
    });
    supabaseClientMock.mockReturnValue({ from: fromMock });

    useProjectMock.mockReturnValue({
      projects: [{ id: 'project-1', aspectRatio: '16:9' }],
    });
    useAddImageToShotMock.mockReturnValue({
      mutateAsync: addImageToShotMutateAsyncMock,
    });
    useHandleExternalImageDropMock.mockReturnValue({
      mutateAsync: handleExternalImageDropMutateAsyncMock,
    });

    updateShotAspectRatioMock.mockResolvedValue(true);
    fetchNextAvailableFrameForShotMock.mockResolvedValue(12);
    cropImagesToShotAspectRatioMock.mockImplementation(async (files: File[]) => files);
    uploadImageForVariantMock.mockResolvedValue({
      imageUrl: 'https://example.com/variant.png',
      thumbnailUrl: 'https://example.com/variant-thumb.png',
    });
    persistTimelinePositionsMock.mockResolvedValue(undefined);
    handleExternalImageDropMutateAsyncMock.mockResolvedValue({
      generationIds: ['generation-1'],
    });
    addImageToShotMutateAsyncMock.mockResolvedValue(undefined);
    demoteOrphanedVariantsMock.mockResolvedValue(undefined);
  });

  it.each([true, false])(
    'auto-switches a dropped 16:9 image onto a 1:1 shot when cropToProjectSize=%s',
    async (cropToProjectSize) => {
      const file = createFile();
      const { result, actions } = renderUseDropActions({ cropToProjectSize });

      await act(async () => {
        await result.current.handleTimelineImageDrop([file], 24);
      });

      expect(updateShotAspectRatioMock).toHaveBeenCalledWith(
        'shot-1',
        'project-1',
        '16:9',
        { immediate: true }
      );
      expect(actions.setAutoAdjustedAspectRatio).toHaveBeenCalledWith({
        previousAspectRatio: '1:1',
        adjustedTo: '16:9',
      });
      expect(cropImagesToShotAspectRatioMock).toHaveBeenCalledWith(
        [file],
        expect.objectContaining({
          id: 'shot-1',
          aspect_ratio: '16:9',
        }),
        'project-1',
        expect.any(Array),
        { cropToProjectSize }
      );
    }
  );

  it('does not auto-switch when the dropped image already matches the shot aspect ratio', async () => {
    probeBehavior.width = 1000;
    probeBehavior.height = 1000;

    const file = createFile('square.png');
    const { result, actions } = renderUseDropActions();

    await act(async () => {
      await result.current.handleTimelineImageDrop([file], 10);
    });

    expect(updateShotAspectRatioMock).not.toHaveBeenCalled();
    expect(actions.setAutoAdjustedAspectRatio).not.toHaveBeenCalled();
    expect(cropImagesToShotAspectRatioMock).toHaveBeenCalledWith(
      [file],
      expect.objectContaining({
        id: 'shot-1',
        aspect_ratio: '1:1',
      }),
      'project-1',
      expect.any(Array),
      { cropToProjectSize: true }
    );
  });

  it('continues the batch drop with the original shot when the aspect-ratio update returns false', async () => {
    updateShotAspectRatioMock.mockResolvedValue(false);

    const queryClient = createQueryClient();
    queryClient.setQueryData<GenerationRow[]>(generationQueryKeys.byShot('shot-1'), []);

    const file = createFile('batch.png');
    const { result, actions } = renderUseDropActions({ queryClient });

    let thrownError: unknown = null;
    try {
      await act(async () => {
        await result.current.handleBatchImageDrop([file], 8);
      });
    } catch (error) {
      thrownError = error;
    }

    expect(thrownError).toBeNull();
    expect(actions.setAutoAdjustedAspectRatio).not.toHaveBeenCalled();
    expect(cropImagesToShotAspectRatioMock).toHaveBeenCalledWith(
      [file],
      expect.objectContaining({
        id: 'shot-1',
        aspect_ratio: '1:1',
      }),
      'project-1',
      expect.any(Array),
      { cropToProjectSize: true }
    );

    const cache = queryClient.getQueryData<GenerationRow[]>(generationQueryKeys.byShot('shot-1')) || [];
    expect(cache.some((item) => item.id.startsWith('temp-upload-'))).toBe(true);
  });

  it('continues unchanged when probing dropped image dimensions fails', async () => {
    probeBehavior.imageMode = 'error';

    const file = createFile('broken.png');
    const { result, actions } = renderUseDropActions();

    let thrownError: unknown = null;
    try {
      await act(async () => {
        await result.current.handleTimelineImageDrop([file], 5);
      });
    } catch (error) {
      thrownError = error;
    }

    expect(thrownError).toBeNull();
    expect(updateShotAspectRatioMock).not.toHaveBeenCalled();
    expect(actions.setAutoAdjustedAspectRatio).not.toHaveBeenCalled();
    expect(cropImagesToShotAspectRatioMock).toHaveBeenCalledWith(
      [file],
      expect.objectContaining({
        id: 'shot-1',
        aspect_ratio: '1:1',
      }),
      'project-1',
      expect.any(Array),
      { cropToProjectSize: true }
    );
  });

  it('creates a dropped variant from a generation drop and invalidates the main-image cache', async () => {
    const queryClient = createQueryClient();
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderUseDropActions({ queryClient });

    await act(async () => {
      await result.current.handleVariantDrop({
        sourceGenerationId: 'generation-source',
        sourceVariantId: 'variant-source',
        imageUrl: 'https://example.com/source.png',
        thumbUrl: 'https://example.com/source-thumb.png',
        targetGenerationId: 'generation-target',
        mode: 'main',
      });
    });

    expect(generationVariantsInsertMock).toHaveBeenCalledWith({
      generation_id: 'generation-target',
      project_id: 'project-1',
      location: 'https://example.com/source.png',
      thumbnail_url: 'https://example.com/source-thumb.png',
      is_primary: true,
      variant_type: 'dropped',
      params: {
        source: 'generation-drop',
        source_generation_id: 'generation-source',
        source_variant_id: 'variant-source',
      },
    });
    expect(enqueueVariantInvalidationMock).toHaveBeenCalledWith(queryClient, {
      generationId: 'generation-target',
      shotId: 'shot-1',
      reason: 'variant-drop',
    });
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({
      queryKey: generationQueryKeys.byShot('shot-1'),
    });
    expect(uploadImageForVariantMock).not.toHaveBeenCalled();
    expect(handleExternalImageDropMutateAsyncMock).not.toHaveBeenCalled();
  });

  it('uploads a file variant without creating a new generation row', async () => {
    const queryClient = createQueryClient();
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderUseDropActions({ queryClient });
    const file = createFile('variant-file.png');

    await act(async () => {
      await result.current.handleVariantDrop({
        files: [file],
        targetGenerationId: 'generation-target',
        mode: 'variant',
      });
    });

    expect(uploadImageForVariantMock).toHaveBeenCalledWith(file, 'project-1');
    expect(generationVariantsInsertMock).toHaveBeenCalledWith({
      generation_id: 'generation-target',
      project_id: 'project-1',
      location: 'https://example.com/variant.png',
      thumbnail_url: 'https://example.com/variant-thumb.png',
      is_primary: false,
      variant_type: 'dropped',
      params: {
        source: 'file-drop',
        original_filename: 'variant-file.png',
      },
    });
    expect(enqueueVariantInvalidationMock).toHaveBeenCalledWith(queryClient, {
      generationId: 'generation-target',
      shotId: 'shot-1',
      reason: 'variant-drop',
    });
    expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
      queryKey: generationQueryKeys.byShot('shot-1'),
    });
    expect(handleExternalImageDropMutateAsyncMock).not.toHaveBeenCalled();
    expect(addImageToShotMutateAsyncMock).not.toHaveBeenCalled();
  });

  it('forwards the handles array into the external-drop mutation payload', async () => {
    probeBehavior.width = 1000;
    probeBehavior.height = 1000;

    const fileA = createFile('a.png');
    const fileB = createFile('b.png');
    const handleA = { kind: 'file', name: 'a.png', getFile: async () => fileA, isSameEntry: async () => false } as unknown as FileSystemFileHandle;
    const handleB = { kind: 'file', name: 'b.png', getFile: async () => fileB, isSameEntry: async () => false } as unknown as FileSystemFileHandle;
    const { result } = renderUseDropActions();

    await act(async () => {
      await result.current.handleTimelineImageDrop([fileA, fileB], 24, [handleA, handleB]);
    });

    expect(handleExternalImageDropMutateAsyncMock).toHaveBeenCalledTimes(1);
    expect(handleExternalImageDropMutateAsyncMock).toHaveBeenCalledWith(
      expect.objectContaining({
        imageFiles: [fileA, fileB],
        handles: [handleA, handleB],
      }),
    );
  });

  it('nulls the handle for the replaced index when cropImagesToShotAspectRatio returns a new File for that index', async () => {
    probeBehavior.width = 1000;
    probeBehavior.height = 1000;

    const fileA = createFile('a.png');
    const fileB = createFile('b.png');
    const replacementA = new File(['cropped'], 'a.png', { type: 'image/png' });
    const handleA = { kind: 'file', name: 'a.png', getFile: async () => fileA, isSameEntry: async () => false } as unknown as FileSystemFileHandle;
    const handleB = { kind: 'file', name: 'b.png', getFile: async () => fileB, isSameEntry: async () => false } as unknown as FileSystemFileHandle;

    cropImagesToShotAspectRatioMock.mockImplementationOnce(async (files: File[]) => [
      replacementA,
      files[1],
    ]);

    const { result } = renderUseDropActions();

    await act(async () => {
      await result.current.handleTimelineImageDrop([fileA, fileB], 24, [handleA, handleB]);
    });

    expect(handleExternalImageDropMutateAsyncMock).toHaveBeenCalledTimes(1);
    const payload = handleExternalImageDropMutateAsyncMock.mock.calls[0][0];
    expect(payload.imageFiles).toEqual([replacementA, fileB]);
    expect(payload.handles).toEqual([null, handleB]);
  });
});
