import { fetchGenerationRecordById } from '@/integrations/supabase/repositories/generationRepository';
import {
  ensurePermission,
  loadHandle,
  type PersistedLocalMediaHandle,
} from '@/shared/lib/media/localHandleStore';
import { uploadImageToStorageWithPath } from '@/shared/lib/media/imageUploader';
import { uploadVideoToStorageWithPath } from '@/shared/lib/media/videoUploader';
import { ingestFileToLocalWorker } from '@/shared/lib/localWorker/ingest';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { MaterializeLocalGenerationError } from '@/shared/lib/media/materializeLocalGeneration';
import type { LocalWorkerSession } from '@/shared/lib/taskCreation/localWorkerSession';

interface ResolveTaskInputMediaInput {
  id?: string | null;
  generation_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

interface RawGenerationRecord extends Record<string, unknown> {
  id: string;
  location: string | null;
  type?: string | null;
  storage_mode?: 'remote' | 'local' | 'uploading' | null;
  local_handle_id?: string | null;
  local_file_name?: string | null;
  local_file_size?: number | null;
  local_file_mime?: string | null;
}

interface LocalMediaHandleWithFile extends PersistedLocalMediaHandle {
  getFile: () => Promise<File>;
}

function hasReadableFile(handle: PersistedLocalMediaHandle | null): handle is LocalMediaHandleWithFile {
  return !!handle && typeof handle.getFile === 'function';
}

function isVideoFile(file: File, generation: RawGenerationRecord): boolean {
  const mime = file.type || generation.local_file_mime || '';
  return mime.startsWith('video/') || generation.type === 'video';
}

async function loadLocalFile(generation: RawGenerationRecord): Promise<File> {
  if (!generation.local_handle_id) {
    throw new MaterializeLocalGenerationError(
      'handle-missing',
      'Local file handle is missing. Drop the file again or upload it instead.',
    );
  }

  const handle = await loadHandle(generation.local_handle_id);
  if (!hasReadableFile(handle)) {
    throw new MaterializeLocalGenerationError(
      'handle-missing',
      'Local file handle is missing. Drop the file again or upload it instead.',
    );
  }

  const permission = await ensurePermission(handle, 'read');
  if (permission !== 'granted') {
    throw new MaterializeLocalGenerationError(
      'permission-denied',
      'Read permission is required before this local file can be uploaded.',
    );
  }

  try {
    return await handle.getFile();
  } catch (error) {
    throw new MaterializeLocalGenerationError(
      'handle-missing',
      'The local file could not be read. It may have moved or lost permission.',
      error,
    );
  }
}

export async function resolveTaskInputMedia(
  media: ResolveTaskInputMediaInput,
  session: LocalWorkerSession,
): Promise<{ url: string }> {
  const generationId = getGenerationId(media as { id?: string | null; generation_id?: string | null; metadata?: Record<string, unknown> });
  if (!generationId) {
    throw new MaterializeLocalGenerationError(
      'generation-not-found',
      'Cannot resolve task input media without a generation_id.',
    );
  }

  const record = (await fetchGenerationRecordById(generationId)) as RawGenerationRecord | null;
  if (!record) {
    throw new MaterializeLocalGenerationError(
      'generation-not-found',
      `Generation ${generationId} not found.`,
    );
  }

  if (record.storage_mode !== 'local') {
    if (typeof record.location !== 'string' || record.location.length === 0) {
      throw new MaterializeLocalGenerationError(
        'generation-not-found',
        `Generation ${generationId} has no location URL.`,
      );
    }
    return { url: record.location };
  }

  const cached = session.cached(generationId);
  if (cached) {
    return { url: cached.url };
  }

  const file = await loadLocalFile(record);
  const reachable = await session.probe();

  if (reachable) {
    const { fileUrl, cleanupPath } = await ingestFileToLocalWorker(file, { generationId });
    session.register({ generation_id: generationId, kind: 'file', target: cleanupPath }, fileUrl);
    return { url: fileUrl };
  }

  if (isVideoFile(file, record)) {
    const { publicUrl, path } = await uploadVideoToStorageWithPath(file);
    session.register({ generation_id: generationId, kind: 'remote', target: path }, publicUrl);
    return { url: publicUrl };
  }

  const { publicUrl, path } = await uploadImageToStorageWithPath(file);
  session.register({ generation_id: generationId, kind: 'remote', target: path }, publicUrl);
  return { url: publicUrl };
}
