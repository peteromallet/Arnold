import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchGenerationRecordByIdMock = vi.fn();
const loadHandleMock = vi.fn();
const ensurePermissionMock = vi.fn();
const probeLocalWorkerMock = vi.fn();
const ingestFileToLocalWorkerMock = vi.fn();
const uploadImageToStorageWithPathMock = vi.fn();
const uploadVideoToStorageWithPathMock = vi.fn();
const generationUpdateSpy = vi.fn();

vi.mock('@/integrations/supabase/repositories/generationRepository', () => ({
  fetchGenerationRecordById: (...args: unknown[]) => fetchGenerationRecordByIdMock(...args),
}));

vi.mock('@/shared/lib/media/localHandleStore', () => ({
  loadHandle: (...args: unknown[]) => loadHandleMock(...args),
  ensurePermission: (...args: unknown[]) => ensurePermissionMock(...args),
}));

vi.mock('@/shared/lib/localWorker/healthcheck', () => ({
  probeLocalWorker: (...args: unknown[]) => probeLocalWorkerMock(...args),
}));

vi.mock('@/shared/lib/localWorker/ingest', () => ({
  ingestFileToLocalWorker: (...args: unknown[]) => ingestFileToLocalWorkerMock(...args),
}));

vi.mock('@/shared/lib/media/imageUploader', () => ({
  uploadImageToStorageWithPath: (...args: unknown[]) => uploadImageToStorageWithPathMock(...args),
}));

vi.mock('@/shared/lib/media/videoUploader', () => ({
  uploadVideoToStorageWithPath: (...args: unknown[]) => uploadVideoToStorageWithPathMock(...args),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: (table: string) => {
      if (table === 'generations') {
        return {
          update: (payload: Record<string, unknown>) => {
            generationUpdateSpy(payload);
            return {
              eq: () => ({
                select: () => ({
                  maybeSingle: async () => ({ data: { id: 'gen' }, error: null }),
                }),
              }),
            };
          },
        };
      }
      throw new Error(`Unexpected table ${table}`);
    },
  }),
}));

import { resolveTaskInputMedia } from '../resolveTaskInputMedia';
import { MaterializeLocalGenerationError } from '../materializeLocalGeneration';
import { beginLocalWorkerSession } from '@/shared/lib/taskCreation/localWorkerSession';

function makeRemoteRecord(id = 'remote-gen', location = 'https://cdn.example.com/foo.png') {
  return { id, location, type: 'image', storage_mode: 'remote' };
}

function makeLocalRecord(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'local-gen',
    location: null,
    storage_mode: 'local',
    local_handle_id: 'handle-1',
    local_file_name: 'photo.png',
    local_file_size: 1024,
    local_file_mime: 'image/png',
    type: 'image',
    ...overrides,
  };
}

function makeFileMock(name = 'photo.png', mime = 'image/png'): File {
  return { name, type: mime, size: 100 } as unknown as File;
}

function makeReadableHandle(file: File) {
  return { getFile: vi.fn().mockResolvedValue(file) };
}

beforeEach(() => {
  fetchGenerationRecordByIdMock.mockReset();
  loadHandleMock.mockReset();
  ensurePermissionMock.mockReset();
  probeLocalWorkerMock.mockReset();
  ingestFileToLocalWorkerMock.mockReset();
  uploadImageToStorageWithPathMock.mockReset();
  uploadVideoToStorageWithPathMock.mockReset();
  generationUpdateSpy.mockReset();
});

describe('resolveTaskInputMedia', () => {
  it('remote generation passes through without probing or registering', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(makeRemoteRecord('rem-1', 'https://cdn/foo.png'));
    const session = beginLocalWorkerSession();

    const result = await resolveTaskInputMedia({ generation_id: 'rem-1' }, session);

    expect(result).toEqual({ url: 'https://cdn/foo.png' });
    expect(probeLocalWorkerMock).not.toHaveBeenCalled();
    expect(ingestFileToLocalWorkerMock).not.toHaveBeenCalled();
    expect(uploadImageToStorageWithPathMock).not.toHaveBeenCalled();
    expect(uploadVideoToStorageWithPathMock).not.toHaveBeenCalled();
    expect(session.records()).toEqual([]);
    expect(generationUpdateSpy).not.toHaveBeenCalled();
  });

  it('local + worker reachable → ingest, returns file:// URL, registers kind:file', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(makeLocalRecord());
    const file = makeFileMock();
    loadHandleMock.mockResolvedValue(makeReadableHandle(file));
    ensurePermissionMock.mockResolvedValue('granted');
    probeLocalWorkerMock.mockResolvedValue(true);
    ingestFileToLocalWorkerMock.mockResolvedValue({
      fileUrl: 'file:///Users/me/.reigh-local-files/local-gen.png',
      cleanupPath: '/Users/me/.reigh-local-files/local-gen.png',
    });
    const session = beginLocalWorkerSession();

    const result = await resolveTaskInputMedia({ generation_id: 'local-gen' }, session);

    expect(result).toEqual({ url: 'file:///Users/me/.reigh-local-files/local-gen.png' });
    expect(probeLocalWorkerMock).toHaveBeenCalledTimes(1);
    expect(ingestFileToLocalWorkerMock).toHaveBeenCalledTimes(1);
    expect(uploadImageToStorageWithPathMock).not.toHaveBeenCalled();
    expect(uploadVideoToStorageWithPathMock).not.toHaveBeenCalled();
    expect(session.records()).toEqual([
      { generation_id: 'local-gen', kind: 'file', target: '/Users/me/.reigh-local-files/local-gen.png' },
    ]);
    expect(generationUpdateSpy).not.toHaveBeenCalled();
  });

  it('local + worker unreachable → image upload, returns https URL, registers kind:remote', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(makeLocalRecord());
    const file = makeFileMock();
    loadHandleMock.mockResolvedValue(makeReadableHandle(file));
    ensurePermissionMock.mockResolvedValue('granted');
    probeLocalWorkerMock.mockResolvedValue(false);
    uploadImageToStorageWithPathMock.mockResolvedValue({
      publicUrl: 'https://cdn.example/uploads/abc.png',
      path: 'user-1/uploads/abc.png',
    });
    const session = beginLocalWorkerSession();

    const result = await resolveTaskInputMedia({ generation_id: 'local-gen' }, session);

    expect(result).toEqual({ url: 'https://cdn.example/uploads/abc.png' });
    expect(uploadImageToStorageWithPathMock).toHaveBeenCalledTimes(1);
    expect(uploadVideoToStorageWithPathMock).not.toHaveBeenCalled();
    expect(ingestFileToLocalWorkerMock).not.toHaveBeenCalled();
    expect(session.records()).toEqual([
      { generation_id: 'local-gen', kind: 'remote', target: 'user-1/uploads/abc.png' },
    ]);
    expect(generationUpdateSpy).not.toHaveBeenCalled();
  });

  it('intra-session dedupe: second resolve of same generation_id returns cached URL without re-materializing', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(makeLocalRecord());
    const file = makeFileMock();
    loadHandleMock.mockResolvedValue(makeReadableHandle(file));
    ensurePermissionMock.mockResolvedValue('granted');
    probeLocalWorkerMock.mockResolvedValue(false);
    uploadImageToStorageWithPathMock.mockResolvedValue({
      publicUrl: 'https://cdn.example/uploads/cached.png',
      path: 'user-1/uploads/cached.png',
    });
    const session = beginLocalWorkerSession();

    const first = await resolveTaskInputMedia({ generation_id: 'local-gen' }, session);
    const second = await resolveTaskInputMedia({ generation_id: 'local-gen' }, session);

    expect(first).toEqual(second);
    expect(uploadImageToStorageWithPathMock).toHaveBeenCalledTimes(1);
    expect(loadHandleMock).toHaveBeenCalledTimes(1);
    expect(session.records()).toHaveLength(1);
  });

  it('probe runs at most once across N local inputs in the same session', async () => {
    fetchGenerationRecordByIdMock
      .mockResolvedValueOnce(makeLocalRecord({ id: 'local-a', local_handle_id: 'h-a' }))
      .mockResolvedValueOnce(makeLocalRecord({ id: 'local-b', local_handle_id: 'h-b' }))
      .mockResolvedValueOnce(makeLocalRecord({ id: 'local-c', local_handle_id: 'h-c' }));
    const file = makeFileMock();
    loadHandleMock.mockResolvedValue(makeReadableHandle(file));
    ensurePermissionMock.mockResolvedValue('granted');
    probeLocalWorkerMock.mockResolvedValue(false);
    uploadImageToStorageWithPathMock.mockResolvedValue({
      publicUrl: 'https://cdn.example/uploads/x.png',
      path: 'user-1/uploads/x.png',
    });
    const session = beginLocalWorkerSession();

    await resolveTaskInputMedia({ generation_id: 'local-a' }, session);
    await resolveTaskInputMedia({ generation_id: 'local-b' }, session);
    await resolveTaskInputMedia({ generation_id: 'local-c' }, session);

    expect(probeLocalWorkerMock).toHaveBeenCalledTimes(1);
    expect(session.records()).toHaveLength(3);
  });

  it('permission denied throws MaterializeLocalGenerationError{code:permission-denied} and registers nothing', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(makeLocalRecord());
    loadHandleMock.mockResolvedValue(makeReadableHandle(makeFileMock()));
    ensurePermissionMock.mockResolvedValue('denied');
    const session = beginLocalWorkerSession();

    let thrown: unknown;
    try {
      await resolveTaskInputMedia({ generation_id: 'local-gen' }, session);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(MaterializeLocalGenerationError);
    expect((thrown as MaterializeLocalGenerationError).code).toBe('permission-denied');
    expect(session.records()).toEqual([]);
    expect(probeLocalWorkerMock).not.toHaveBeenCalled();
    expect(uploadImageToStorageWithPathMock).not.toHaveBeenCalled();
    expect(generationUpdateSpy).not.toHaveBeenCalled();
  });

  it('video file dispatches via isVideoFile to uploadVideoToStorageWithPath', async () => {
    fetchGenerationRecordByIdMock.mockResolvedValue(
      makeLocalRecord({ id: 'local-vid', type: 'video', local_file_mime: 'video/mp4' }),
    );
    const videoFile = makeFileMock('clip.mp4', 'video/mp4');
    loadHandleMock.mockResolvedValue(makeReadableHandle(videoFile));
    ensurePermissionMock.mockResolvedValue('granted');
    probeLocalWorkerMock.mockResolvedValue(false);
    uploadVideoToStorageWithPathMock.mockResolvedValue({
      publicUrl: 'https://cdn.example/uploads/clip.mp4',
      path: 'user-1/uploads/clip.mp4',
    });
    const session = beginLocalWorkerSession();

    const result = await resolveTaskInputMedia({ generation_id: 'local-vid' }, session);

    expect(result).toEqual({ url: 'https://cdn.example/uploads/clip.mp4' });
    expect(uploadVideoToStorageWithPathMock).toHaveBeenCalledTimes(1);
    expect(uploadImageToStorageWithPathMock).not.toHaveBeenCalled();
    expect(session.records()).toEqual([
      { generation_id: 'local-vid', kind: 'remote', target: 'user-1/uploads/clip.mp4' },
    ]);
  });

  it('never writes to generations.location/storage_mode/local_handle_id/local_file_* on any branch', async () => {
    // Run each branch with a fresh session because probe() is memoised per-session.

    // Branch 1: remote passthrough.
    {
      const session = beginLocalWorkerSession();
      fetchGenerationRecordByIdMock.mockResolvedValueOnce(makeRemoteRecord('rem-x', 'https://x'));
      await resolveTaskInputMedia({ generation_id: 'rem-x' }, session);
    }

    // Branch 2: local + worker reachable -> file:// URL.
    {
      const session = beginLocalWorkerSession();
      fetchGenerationRecordByIdMock.mockResolvedValueOnce(makeLocalRecord({ id: 'l-1', local_handle_id: 'h1' }));
      loadHandleMock.mockResolvedValueOnce(makeReadableHandle(makeFileMock()));
      ensurePermissionMock.mockResolvedValueOnce('granted');
      probeLocalWorkerMock.mockResolvedValueOnce(true);
      ingestFileToLocalWorkerMock.mockResolvedValueOnce({ fileUrl: 'file:///tmp/h1.png', cleanupPath: '/tmp/h1.png' });
      await resolveTaskInputMedia({ generation_id: 'l-1' }, session);
    }

    // Branch 3: local + worker unreachable -> upload.
    {
      const session = beginLocalWorkerSession();
      fetchGenerationRecordByIdMock.mockResolvedValueOnce(makeLocalRecord({ id: 'l-2', local_handle_id: 'h2' }));
      loadHandleMock.mockResolvedValueOnce(makeReadableHandle(makeFileMock()));
      ensurePermissionMock.mockResolvedValueOnce('granted');
      probeLocalWorkerMock.mockResolvedValueOnce(false);
      uploadImageToStorageWithPathMock.mockResolvedValueOnce({ publicUrl: 'https://cdn/abc', path: 'p/abc' });
      await resolveTaskInputMedia({ generation_id: 'l-2' }, session);
    }

    // Branch 4: permission denied.
    {
      const session = beginLocalWorkerSession();
      fetchGenerationRecordByIdMock.mockResolvedValueOnce(makeLocalRecord({ id: 'l-3', local_handle_id: 'h3' }));
      loadHandleMock.mockResolvedValueOnce(makeReadableHandle(makeFileMock()));
      ensurePermissionMock.mockResolvedValueOnce('denied');
      await expect(
        resolveTaskInputMedia({ generation_id: 'l-3' }, session),
      ).rejects.toBeInstanceOf(MaterializeLocalGenerationError);
    }

    expect(generationUpdateSpy).not.toHaveBeenCalled();
  });
});
