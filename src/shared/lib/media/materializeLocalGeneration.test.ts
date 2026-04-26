import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchGenerationRecordByIdMock = vi.fn();
const loadHandleMock = vi.fn();
const ensurePermissionMock = vi.fn();
const uploadImageToStorageMock = vi.fn();
const uploadVideoToStorageMock = vi.fn();
const toastErrorMock = vi.fn();

const generationsUpdatePayloads: Array<Record<string, unknown>> = [];
const generationVariantInsertPayloads: Array<Record<string, unknown>> = [];

vi.mock('@/integrations/supabase/repositories/generationRepository', () => ({
  fetchGenerationRecordById: (...args: unknown[]) => fetchGenerationRecordByIdMock(...args),
}));

vi.mock('@/shared/lib/media/localHandleStore', () => ({
  loadHandle: (...args: unknown[]) => loadHandleMock(...args),
  ensurePermission: (...args: unknown[]) => ensurePermissionMock(...args),
}));

vi.mock('@/shared/lib/media/imageUploader', () => ({
  uploadImageToStorage: (...args: unknown[]) => uploadImageToStorageMock(...args),
}));

vi.mock('@/shared/lib/media/videoUploader', () => ({
  uploadVideoToStorage: (...args: unknown[]) => uploadVideoToStorageMock(...args),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: (table: string) => {
      if (table === 'generations') {
        return {
          update: (payload: Record<string, unknown>) => ({
            eq: () => ({
              select: () => ({
                maybeSingle: async () => {
                  generationsUpdatePayloads.push(payload);
                  return { data: { id: 'gen-1' }, error: null };
                },
              }),
            }),
          }),
        };
      }

      if (table === 'generation_variants') {
        return {
          insert: (payload: Record<string, unknown>) => ({
            select: () => ({
              single: async () => {
                generationVariantInsertPayloads.push(payload);
                return { data: { id: 'variant-1' }, error: null };
              },
            }),
          }),
        };
      }

      throw new Error(`Unexpected table ${table}`);
    },
  }),
}));

function buildLocalGenerationRecord(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'gen-1',
    location: null,
    thumbnail_url: 'https://example.com/thumb.png',
    type: 'image',
    params: { source: 'upload' },
    storage_mode: 'local',
    local_handle_id: 'handle-1',
    local_file_name: 'frame.png',
    local_file_size: 1024,
    local_file_mime: 'image/png',
    ...overrides,
  };
}

let materializeLocalGeneration: typeof import('./materializeLocalGeneration').materializeLocalGeneration;
describe('materializeLocalGeneration', () => {
  beforeAll(async () => {
    ({ materializeLocalGeneration } = await import('./materializeLocalGeneration'));
  });

  beforeEach(() => {
    vi.clearAllMocks();
    generationsUpdatePayloads.length = 0;
    generationVariantInsertPayloads.length = 0;

    fetchGenerationRecordByIdMock.mockImplementation(async (generationId: string) => (
      buildLocalGenerationRecord({ id: generationId })
    ));
    loadHandleMock.mockResolvedValue({
      kind: 'file',
      name: 'frame.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn().mockResolvedValue(new File(['image'], 'frame.png', { type: 'image/png' })),
    });
    ensurePermissionMock.mockResolvedValue('granted');
    uploadImageToStorageMock.mockResolvedValue('https://example.com/full.png');
    uploadVideoToStorageMock.mockResolvedValue('https://example.com/full.mp4');
  });

  it('materializes a local generation to a remote original and inserts a primary variant', async () => {
    const result = await materializeLocalGeneration('gen-1');

    expect(result).toEqual({ location: 'https://example.com/full.png' });
    expect(generationsUpdatePayloads[0]).toEqual({ storage_mode: 'uploading' });
    expect(generationsUpdatePayloads[1]).toEqual({
      location: 'https://example.com/full.png',
      primary_variant_id: 'variant-1',
      storage_mode: 'remote',
      local_handle_id: null,
      local_file_name: null,
      local_file_size: null,
      local_file_mime: null,
    });
    expect(generationVariantInsertPayloads[0]).toEqual(expect.objectContaining({
      generation_id: 'gen-1',
      location: 'https://example.com/full.png',
      thumbnail_url: 'https://example.com/thumb.png',
      is_primary: true,
      variant_type: 'original',
    }));
  });

  it('uses a single in-flight upload for concurrent callers of the same generation', async () => {
    let resolveUpload!: (value: string) => void;
    let signalUploadStarted!: () => void;
    const uploadStarted = new Promise<void>((resolve) => {
      signalUploadStarted = resolve;
    });
    uploadImageToStorageMock.mockImplementation(() => new Promise<string>((resolve) => {
      resolveUpload = resolve;
      signalUploadStarted();
    }));

    const first = materializeLocalGeneration('gen-2');
    const second = materializeLocalGeneration('gen-2');

    await uploadStarted;

    resolveUpload('https://example.com/full.png');

    await expect(first).resolves.toEqual({ location: 'https://example.com/full.png' });
    await expect(second).resolves.toEqual({ location: 'https://example.com/full.png' });
    expect(uploadImageToStorageMock).toHaveBeenCalledTimes(1);
  });

  it('returns handle-missing when the local handle cannot be loaded and flips back to local', async () => {
    loadHandleMock.mockResolvedValue(null);

    await expect(materializeLocalGeneration('gen-3')).rejects.toMatchObject({
      code: 'handle-missing',
    });

    expect(generationsUpdatePayloads[0]).toEqual({ storage_mode: 'uploading' });
    expect(generationsUpdatePayloads[1]).toEqual({
      storage_mode: 'local',
      local_handle_id: 'handle-1',
      local_file_name: 'frame.png',
      local_file_size: 1024,
      local_file_mime: 'image/png',
    });
  });

  it('returns permission-denied when the handle permission is not granted and flips back to local', async () => {
    ensurePermissionMock.mockResolvedValue('prompt');

    await expect(materializeLocalGeneration('gen-4')).rejects.toMatchObject({
      code: 'permission-denied',
    });

    expect(generationsUpdatePayloads[0]).toEqual({ storage_mode: 'uploading' });
    expect(generationsUpdatePayloads[1]).toEqual({
      storage_mode: 'local',
      local_handle_id: 'handle-1',
      local_file_name: 'frame.png',
      local_file_size: 1024,
      local_file_mime: 'image/png',
    });
  });

  it('returns network-failure when upload fails, flips back to local, and shows an error toast', async () => {
    uploadImageToStorageMock.mockRejectedValue(new Error('boom'));

    await expect(materializeLocalGeneration('gen-5')).rejects.toMatchObject({
      code: 'network-failure',
    });

    expect(generationsUpdatePayloads[0]).toEqual({ storage_mode: 'uploading' });
    expect(generationsUpdatePayloads[1]).toEqual({
      storage_mode: 'local',
      local_handle_id: 'handle-1',
      local_file_name: 'frame.png',
      local_file_size: 1024,
      local_file_mime: 'image/png',
    });
    expect(toastErrorMock).toHaveBeenCalledWith(
      'Failed to upload the original file. The generation stayed in local mode.',
    );
  });
});
