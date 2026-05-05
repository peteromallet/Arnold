import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  from: vi.fn(),
  toastError: vi.fn(),
  normalizeAndPresentError: vi.fn(),
  uploadImageToStorage: vi.fn(),
  generateClientThumbnail: vi.fn(),
  uploadImageWithThumbnail: vi.fn(),
  createGenerationForLocalFile: vi.fn(),
  cropImageToProjectAspectRatio: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: mocks.from,
  }),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: mocks.toastError,
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: mocks.normalizeAndPresentError,
}));

vi.mock('@/shared/lib/media/imageUploader', () => ({
  uploadImageToStorage: mocks.uploadImageToStorage,
}));

vi.mock('@/shared/media/clientThumbnailGenerator', () => ({
  generateClientThumbnail: mocks.generateClientThumbnail,
  uploadImageWithThumbnail: mocks.uploadImageWithThumbnail,
}));

vi.mock('@/shared/lib/media/createGenerationFromFile', async () => {
  const actual = await vi.importActual<typeof import('@/shared/lib/media/createGenerationFromFile')>(
    '@/shared/lib/media/createGenerationFromFile',
  );
  return {
    ...actual,
    createGenerationForLocalFile: mocks.createGenerationForLocalFile,
  };
});

vi.mock('@/shared/lib/media/imageCropper', () => ({
  cropImageToProjectAspectRatio: mocks.cropImageToProjectAspectRatio,
}));

import { processDroppedImages } from './externalImageDrop';

function makeLargeFile(name = 'large.png'): File {
  const file = new File(['large'], name, { type: 'image/png' });
  Object.defineProperty(file, 'size', { value: 26 * 1024 * 1024 });
  return file;
}

function makeStubHandle(file: File): FileSystemFileHandle {
  return {
    kind: 'file',
    name: file.name,
    getFile: async () => file,
    isSameEntry: async () => false,
  } as unknown as FileSystemFileHandle;
}

function createQueryResult(data: unknown) {
  return {
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    single: vi.fn().mockResolvedValue({ data }),
    insert: vi.fn().mockReturnThis(),
  };
}

function createInsertResult(data: unknown) {
  return {
    insert: vi.fn().mockReturnThis(),
    select: vi.fn().mockReturnThis(),
    single: vi.fn().mockResolvedValue({ data, error: null }),
  };
}

function createInsertOnlyResult() {
  return {
    insert: vi.fn().mockResolvedValue({ error: null }),
  };
}

describe('processDroppedImages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.generateClientThumbnail.mockResolvedValue({
      thumbnailBlob: new Blob(['thumb'], { type: 'image/jpeg' }),
    });
    mocks.uploadImageWithThumbnail.mockResolvedValue({
      imageUrl: 'https://example.com/image.png',
      thumbnailUrl: 'https://example.com/thumb.png',
    });
    mocks.uploadImageToStorage.mockResolvedValue('https://example.com/image.png');
    mocks.from.mockImplementation((table: string) => {
      if (table === 'projects') {
        return createQueryResult({ aspect_ratio: null, settings: null });
      }
      if (table === 'shots') {
        return createQueryResult({ aspect_ratio: null });
      }
      if (table === 'generations') {
        return createInsertResult({
          id: 'gen-1',
          location: 'https://example.com/image.png',
          thumbnail_url: 'https://example.com/thumb.png',
          type: 'image',
          created_at: '2026-04-06T00:00:00.000Z',
          params: {
            source: 'upload',
            original_filename: 'frame.png',
            file_type: 'image/png',
            file_size: 3,
          },
          primary_variant_id: null,
        });
      }
      if (table === 'generation_variants') {
        return createInsertOnlyResult();
      }
      return createQueryResult(null);
    });
  });

  it('returns null when shot creation fails for missing target shot', async () => {
    const result = await processDroppedImages({
      variables: {
        imageFiles: [new File(['img'], 'one.png', { type: 'image/png' })],
        targetShotId: null,
        currentProjectQueryKey: 'project-1',
        currentShotCount: 2,
      },
      projectId: 'project-1',
      createShot: vi.fn().mockResolvedValue(null),
      addImageToShot: vi.fn(),
      addImageToShotWithoutPosition: vi.fn(),
    });

    expect(result).toBeNull();
    expect(mocks.toastError).toHaveBeenCalledWith('Failed to create new shot.');
    expect(mocks.uploadImageToStorage).not.toHaveBeenCalled();
    expect(mocks.uploadImageWithThumbnail).not.toHaveBeenCalled();
  });

  it('uploads, creates generation, and attaches with explicit timeline position', async () => {
    const addImageToShot = vi.fn().mockResolvedValue({
      id: 'shot-gen-1',
      generation_id: 'gen-1',
      timeline_frame: 42,
    });
    const addImageToShotWithoutPosition = vi.fn().mockResolvedValue(undefined);

    const result = await processDroppedImages({
      variables: {
        imageFiles: [new File(['img'], 'frame.png', { type: 'image/png' })],
        targetShotId: 'shot-1',
        currentProjectQueryKey: 'project-1',
        currentShotCount: 1,
        positions: [42],
      },
      projectId: 'project-1',
      createShot: vi.fn(),
      addImageToShot,
      addImageToShotWithoutPosition,
    });

    expect(result).toEqual({
      shotId: 'shot-1',
      generationIds: ['gen-1'],
      generationMetadata: [
        {
          generationId: 'gen-1',
          location: 'https://example.com/image.png',
          thumbnail_url: 'https://example.com/thumb.png',
          type: 'image',
          created_at: '2026-04-06T00:00:00.000Z',
          params: {
            source: 'upload',
            original_filename: 'frame.png',
            file_type: 'image/png',
            file_size: 3,
          },
          primary_variant_id: null,
          shot_generation_id: 'shot-gen-1',
          timeline_frame: 42,
        },
      ],
    });
    expect(addImageToShot).toHaveBeenCalledWith(
      expect.objectContaining({
        shot_id: 'shot-1',
        generation_id: 'gen-1',
        timelineFrame: 42,
      }),
    );
    expect(addImageToShotWithoutPosition).not.toHaveBeenCalled();
    expect(mocks.generateClientThumbnail).toHaveBeenCalledTimes(1);
    expect(mocks.uploadImageWithThumbnail).toHaveBeenCalledTimes(1);
  });

  it('routes large files with a usable handle through the local-handle path', async () => {
    const largeFile = makeLargeFile('big.png');
    const handle = makeStubHandle(largeFile);
    mocks.createGenerationForLocalFile.mockResolvedValue({
      id: 'gen-local-1',
      location: null,
      thumbnail_url: 'https://example.com/local-thumb.png',
      type: 'image',
      created_at: '2026-04-06T00:00:00.000Z',
      params: { source: 'local-handle', original_filename: 'big.png' },
      primary_variant_id: null,
    });
    const addImageToShot = vi.fn().mockResolvedValue({
      id: 'shot-gen-local-1',
      generation_id: 'gen-local-1',
      timeline_frame: 99,
    });

    const result = await processDroppedImages({
      variables: {
        imageFiles: [largeFile],
        targetShotId: 'shot-1',
        currentProjectQueryKey: 'project-1',
        currentShotCount: 1,
        positions: [99],
        handles: [handle],
      },
      projectId: 'project-1',
      createShot: vi.fn(),
      addImageToShot,
      addImageToShotWithoutPosition: vi.fn(),
    });

    expect(result?.generationIds).toEqual(['gen-local-1']);
    expect(mocks.createGenerationForLocalFile).toHaveBeenCalledTimes(1);
    expect(mocks.createGenerationForLocalFile).toHaveBeenCalledWith({
      file: largeFile,
      projectId: 'project-1',
      handle,
      mediaType: 'image',
    });
    expect(mocks.uploadImageWithThumbnail).not.toHaveBeenCalled();
    expect(mocks.uploadImageToStorage).not.toHaveBeenCalled();
    expect(addImageToShot).toHaveBeenCalledWith(
      expect.objectContaining({
        shot_id: 'shot-1',
        generation_id: 'gen-local-1',
        thumbUrl: 'https://example.com/local-thumb.png',
        timelineFrame: 99,
      }),
    );
  });

  it('uses the upload path for small files even when a handle is supplied', async () => {
    const smallFile = new File(['tiny'], 'tiny.png', { type: 'image/png' });
    const handle = makeStubHandle(smallFile);

    const result = await processDroppedImages({
      variables: {
        imageFiles: [smallFile],
        targetShotId: 'shot-1',
        currentProjectQueryKey: 'project-1',
        currentShotCount: 1,
        positions: [10],
        handles: [handle],
      },
      projectId: 'project-1',
      createShot: vi.fn(),
      addImageToShot: vi.fn().mockResolvedValue({ id: 'shot-gen-small', generation_id: 'gen-1', timeline_frame: 10 }),
      addImageToShotWithoutPosition: vi.fn(),
    });

    expect(result?.generationIds).toEqual(['gen-1']);
    expect(mocks.createGenerationForLocalFile).not.toHaveBeenCalled();
    expect(mocks.uploadImageWithThumbnail).toHaveBeenCalledTimes(1);
  });

  it('uses the upload path for large files when no handle is supplied', async () => {
    const largeFile = makeLargeFile('big-no-handle.png');

    const result = await processDroppedImages({
      variables: {
        imageFiles: [largeFile],
        targetShotId: 'shot-1',
        currentProjectQueryKey: 'project-1',
        currentShotCount: 1,
        positions: [11],
        handles: [null],
      },
      projectId: 'project-1',
      createShot: vi.fn(),
      addImageToShot: vi.fn().mockResolvedValue({ id: 'shot-gen-no-handle', generation_id: 'gen-1', timeline_frame: 11 }),
      addImageToShotWithoutPosition: vi.fn(),
    });

    expect(result?.generationIds).toEqual(['gen-1']);
    expect(mocks.createGenerationForLocalFile).not.toHaveBeenCalled();
    expect(mocks.uploadImageWithThumbnail).toHaveBeenCalledTimes(1);
  });

  it('falls back to upload when cropFilesIfNeeded replaces the file reference', async () => {
    const largeFile = makeLargeFile('crop-me.png');
    const handle = makeStubHandle(largeFile);
    const replacementFile = new File(['cropped'], 'crop-me.png', { type: 'image/png' });
    Object.defineProperty(replacementFile, 'size', { value: 26 * 1024 * 1024 });

    mocks.cropImageToProjectAspectRatio.mockResolvedValue({
      croppedFile: replacementFile,
      croppedImageUrl: 'blob:cropped',
    });
    mocks.from.mockImplementation((table: string) => {
      if (table === 'projects') {
        return createQueryResult({ aspect_ratio: '16:9', settings: null });
      }
      if (table === 'shots') {
        return createQueryResult({ aspect_ratio: '16:9' });
      }
      if (table === 'generations') {
        return createInsertResult({
          id: 'gen-after-crop',
          location: 'https://example.com/image.png',
          thumbnail_url: 'https://example.com/thumb.png',
          type: 'image',
          created_at: '2026-04-06T00:00:00.000Z',
          params: { source: 'upload', original_filename: 'crop-me.png', file_type: 'image/png', file_size: 26 * 1024 * 1024 },
          primary_variant_id: null,
        });
      }
      return createQueryResult(null);
    });

    const result = await processDroppedImages({
      variables: {
        imageFiles: [largeFile],
        targetShotId: 'shot-1',
        currentProjectQueryKey: 'project-1',
        currentShotCount: 1,
        positions: [12],
        handles: [handle],
      },
      projectId: 'project-1',
      createShot: vi.fn(),
      addImageToShot: vi.fn().mockResolvedValue({ id: 'shot-gen-crop', generation_id: 'gen-after-crop', timeline_frame: 12 }),
      addImageToShotWithoutPosition: vi.fn(),
    });

    expect(result?.generationIds).toEqual(['gen-after-crop']);
    expect(mocks.cropImageToProjectAspectRatio).toHaveBeenCalledTimes(1);
    expect(mocks.createGenerationForLocalFile).not.toHaveBeenCalled();
    expect(mocks.uploadImageWithThumbnail).toHaveBeenCalledTimes(1);
  });
});
