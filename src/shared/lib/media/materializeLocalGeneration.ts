import { getSupabaseClient } from '@/integrations/supabase/client';
import { fetchGenerationRecordById } from '@/integrations/supabase/repositories/generationRepository';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { VARIANT_TYPE } from '@/shared/constants/variantTypes';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import {
  ensurePermission,
  loadHandle,
  type PersistedLocalMediaHandle,
} from '@/shared/lib/media/localHandleStore';
import { uploadImageToStorage } from '@/shared/lib/media/imageUploader';
import { uploadVideoToStorage } from '@/shared/lib/media/videoUploader';

export type MaterializeLocalGenerationErrorCode =
  | 'permission-denied'
  | 'handle-missing'
  | 'network-failure'
  | 'generation-not-found';

export interface MaterializeLocalGenerationOptions {
  signal?: AbortSignal;
  onProgress?: (progress: number) => void;
  handleOverride?: PersistedLocalMediaHandle | null;
}

interface RawGenerationRecord extends Record<string, unknown> {
  id: string;
  location: string | null;
  thumbnail_url?: string | null;
  type?: string | null;
  params?: Record<string, unknown> | null;
  storage_mode?: 'remote' | 'local' | 'uploading' | null;
  local_handle_id?: string | null;
  local_file_name?: string | null;
  local_file_size?: number | null;
  local_file_mime?: string | null;
  primary_variant_id?: string | null;
}

interface LocalMediaHandleWithFile extends PersistedLocalMediaHandle {
  getFile: () => Promise<File>;
}

const inFlightMaterializations = new Map<string, Promise<{ location: string }>>();

function hasReadableFile(handle: PersistedLocalMediaHandle | null): handle is LocalMediaHandleWithFile {
  return !!handle && typeof handle.getFile === 'function';
}

function asRawGenerationRecord(value: Record<string, unknown> | null): RawGenerationRecord | null {
  if (!value || typeof value.id !== 'string') {
    return null;
  }

  return value as RawGenerationRecord;
}

function isVideoFile(file: File, generation: RawGenerationRecord): boolean {
  const mime = file.type || generation.local_file_mime || '';
  return mime.startsWith('video/') || generation.type === 'video';
}

function buildMaterializationError(
  code: MaterializeLocalGenerationErrorCode,
  message: string,
  cause?: unknown,
): MaterializeLocalGenerationError {
  return new MaterializeLocalGenerationError(code, message, cause);
}

async function updateGeneration(generationId: string, patch: Record<string, unknown>): Promise<void> {
  const client = getSupabaseClient() as unknown as {
    from: (table: string) => {
      update: (payload: Record<string, unknown>) => {
        eq: (column: string, value: string) => {
          select: (columns: string) => {
            maybeSingle: () => Promise<{ data: { id: string } | null; error: unknown }>;
          };
        };
      };
    };
  };

  const { error } = await client
    .from('generations')
    .update(patch)
    .eq('id', generationId)
    .select('id')
    .maybeSingle();

  if (error) {
    throw error instanceof Error ? error : new Error('Failed to update generation');
  }
}

async function insertPrimaryVariant(generation: RawGenerationRecord, location: string): Promise<string> {
  const client = getSupabaseClient() as unknown as {
    from: (table: string) => {
      insert: (payload: Record<string, unknown>) => {
        select: (columns: string) => {
          single: () => Promise<{ data: { id: string } | null; error: unknown }>;
        };
      };
    };
  };

  const { data, error } = await client
    .from('generation_variants')
    .insert({
      generation_id: generation.id,
      location,
      thumbnail_url: generation.thumbnail_url ?? location,
      is_primary: true,
      variant_type: VARIANT_TYPE.ORIGINAL,
      name: 'Original',
      params: generation.params ?? null,
    })
    .select('id')
    .single();

  if (error || !data?.id) {
    throw error instanceof Error ? error : new Error('Failed to create primary variant');
  }

  return data.id;
}

async function revertToLocal(generation: RawGenerationRecord): Promise<void> {
  try {
    await updateGeneration(generation.id, {
      storage_mode: 'local',
      local_handle_id: generation.local_handle_id ?? null,
      local_file_name: generation.local_file_name ?? null,
      local_file_size: generation.local_file_size ?? null,
      local_file_mime: generation.local_file_mime ?? null,
    });
  } catch (error) {
    normalizeAndPresentError(error, {
      context: 'materializeLocalGeneration.revertToLocal',
      showToast: false,
    });
  }
}

async function resolveLocalFile(
  generation: RawGenerationRecord,
  handleOverride?: PersistedLocalMediaHandle | null,
): Promise<File> {
  const overrideHandle = handleOverride ?? null;

  if (!generation.local_handle_id && !overrideHandle) {
    throw buildMaterializationError(
      'handle-missing',
      'Local file handle is missing. Drop the file again or upload it instead.',
    );
  }

  const handle = overrideHandle ?? await loadHandle(generation.local_handle_id!);
  if (!hasReadableFile(handle)) {
    throw buildMaterializationError(
      'handle-missing',
      'Local file handle is missing. Drop the file again or upload it instead.',
    );
  }

  const permission = await ensurePermission(handle, 'read');
  if (permission !== 'granted') {
    throw buildMaterializationError(
      'permission-denied',
      'Read permission is required before this local file can be uploaded.',
    );
  }

  try {
    return await handle.getFile();
  } catch (error) {
    throw buildMaterializationError(
      'handle-missing',
      'The local file could not be read. It may have moved or lost permission.',
      error,
    );
  }
}

async function uploadOriginalFile(
  generation: RawGenerationRecord,
  file: File,
  options?: MaterializeLocalGenerationOptions,
): Promise<string> {
  try {
    if (isVideoFile(file, generation)) {
      return await uploadVideoToStorage(file, {
        signal: options?.signal,
        onProgress: options?.onProgress,
      });
    }

    return await uploadImageToStorage(file, {
      signal: options?.signal,
      onProgress: options?.onProgress,
    });
  } catch (error) {
    throw buildMaterializationError(
      'network-failure',
      'Failed to upload the original file.',
      error,
    );
  }
}

async function materializeLocalGenerationInternal(
  generationId: string,
  options?: MaterializeLocalGenerationOptions,
): Promise<{ location: string }> {
  const record = asRawGenerationRecord(
    await fetchGenerationRecordById(generationId) as Record<string, unknown> | null,
  );

  if (!record) {
    throw buildMaterializationError(
      'generation-not-found',
      'Generation not found.',
    );
  }

  if (record.storage_mode === 'remote' && typeof record.location === 'string' && record.location.length > 0) {
    return { location: record.location };
  }

  await updateGeneration(record.id, { storage_mode: 'uploading' });

  try {
    const file = await resolveLocalFile(record, options?.handleOverride);
    const location = await uploadOriginalFile(record, file, options);
    const primaryVariantId = await insertPrimaryVariant(record, location);

    await updateGeneration(record.id, {
      location,
      primary_variant_id: primaryVariantId,
      storage_mode: 'remote',
      local_handle_id: null,
      local_file_name: null,
      local_file_size: null,
      local_file_mime: null,
    });

    return { location };
  } catch (error) {
    await revertToLocal(record);

    if (error instanceof MaterializeLocalGenerationError) {
      if (error.code === 'network-failure') {
        toast.error('Failed to upload the original file. The generation stayed in local mode.');
      }
      throw error;
    }

    const wrapped = buildMaterializationError(
      'network-failure',
      'Failed to upload the original file.',
      error,
    );
    toast.error('Failed to upload the original file. The generation stayed in local mode.');
    throw wrapped;
  }
}

export async function materializeLocalGeneration(
  generationId: string,
  options?: MaterializeLocalGenerationOptions,
): Promise<{ location: string }> {
  const existingPromise = inFlightMaterializations.get(generationId);
  if (existingPromise) {
    return existingPromise;
  }

  const promise = materializeLocalGenerationInternal(generationId, options).finally(() => {
    inFlightMaterializations.delete(generationId);
  });

  inFlightMaterializations.set(generationId, promise);
  return promise;
}

export class MaterializeLocalGenerationError extends Error {
  readonly code: MaterializeLocalGenerationErrorCode;
  declare readonly cause: unknown;

  constructor(code: MaterializeLocalGenerationErrorCode, message: string, cause?: unknown) {
    super(message);
    this.name = 'MaterializeLocalGenerationError';
    this.code = code;
    this.cause = cause;
  }
}
