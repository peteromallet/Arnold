import type { Database } from '@/integrations/supabase/databasePublicTypes';
import { getSupabaseClient } from '@/integrations/supabase/client';
import { createExternalUploadGeneration } from '@/integrations/supabase/repositories/generationMutationsRepository';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { uploadBlobToStorage, uploadImageToStorage } from '@/shared/lib/media/imageUploader';
import { extractVideoPosterFrame } from '@/shared/lib/media/videoPosterExtractor';
import { uploadVideoToStorage } from '@/shared/lib/media/videoUploader';
import { saveHandle, type PersistedLocalMediaHandle } from '@/shared/lib/media/localHandleStore';
import {
  generateClientThumbnail,
  uploadImageWithThumbnail,
} from '@/shared/media/clientThumbnailGenerator';

type GenerationRow = Database['public']['Tables']['generations']['Row'];
type GenerationParams = Parameters<typeof createExternalUploadGeneration>[0]['generationParams'];

interface CreateGenerationForUploadedImageInput {
  imageFile: File;
  projectId: string;
  onProgress?: (progress: number) => void;
}

interface CreateGenerationForUploadedVideoInput {
  videoFile: File;
  projectId: string;
  onProgress?: (progress: number) => void;
}

interface CreateLocalGenerationInput {
  file: File;
  projectId: string;
  handle: PersistedLocalMediaHandle;
  mediaType: 'image' | 'video';
}

export async function uploadImageForVariant(
  imageFile: File,
  _projectId: string,
  options: { onProgress?: (progress: number) => void } = {},
): Promise<{ imageUrl: string; thumbnailUrl: string }> {
  void _projectId;
  const { onProgress } = options;

  try {
    const thumbnailResult = await generateClientThumbnail(imageFile, 300, 0.8);
    return await uploadImageWithThumbnail(imageFile, thumbnailResult.thumbnailBlob, {
      onProgress,
    });
  } catch (error) {
    normalizeAndPresentError(error, {
      context: `useShotCreation:thumbnail:${imageFile.name}`,
      showToast: false,
    });

    const imageUrl = await uploadImageToStorage(imageFile, 3, onProgress);
    return {
      imageUrl,
      thumbnailUrl: imageUrl,
    };
  }
}

async function insertUploadedGeneration(input: {
  projectId: string;
  type: 'image' | 'video';
  location: string;
  thumbnailUrl: string;
  generationParams: GenerationParams;
}): Promise<GenerationRow> {
  const generation = await createExternalUploadGeneration({
    imageUrl: input.location,
    thumbnailUrl: input.thumbnailUrl,
    fileType: input.type,
    projectId: input.projectId,
    generationParams: input.generationParams,
  });

  return generation as unknown as GenerationRow;
}

async function uploadThumbnailOnly(input: {
  file: File;
  mediaType: 'image' | 'video';
}): Promise<string> {
  if (input.mediaType === 'image') {
    const thumbnail = await generateClientThumbnail(input.file, 300, 0.8);
    return uploadBlobToStorage(thumbnail.thumbnailBlob, `${input.file.name}-thumbnail.jpg`, 'image/jpeg');
  }

  const posterBlob = await extractVideoPosterFrame(input.file);
  return uploadBlobToStorage(posterBlob, `${input.file.name}-poster.jpg`, 'image/jpeg');
}

async function insertLocalMediaHandle(projectId: string): Promise<string> {
  const client = getSupabaseClient() as unknown as {
    auth: {
      getSession: () => Promise<{ data: { session: { user?: { id?: string | null } } | null } }>;
    };
    from: (table: string) => {
      insert: (payload: Record<string, unknown>) => {
        select: (columns: string) => {
          single: () => Promise<{ data: { id: string } | null; error: unknown }>;
        };
      };
    };
  };

  const sessionResult = await client.auth.getSession();
  const userId = sessionResult.data.session?.user?.id;
  if (!userId) {
    throw new Error('User not authenticated');
  }

  const { data, error } = await client
    .from('local_media_handles')
    .insert({
      user_id: userId,
      project_id: projectId,
    })
    .select('id')
    .single();

  if (error || !data?.id) {
    throw error instanceof Error ? error : new Error('Failed to create local media handle row');
  }

  return data.id;
}

async function insertLocalGeneration(input: {
  file: File;
  projectId: string;
  mediaType: 'image' | 'video';
  thumbnailUrl: string;
  localHandleId: string;
}): Promise<GenerationRow> {
  const client = getSupabaseClient() as unknown as {
    from: (table: string) => {
      insert: (payload: Record<string, unknown>) => {
        select: () => {
          single: () => Promise<{ data: GenerationRow | null; error: unknown }>;
        };
      };
    };
  };

  const generationParams: GenerationParams = {
    extra: {
      source: 'upload',
      original_filename: input.file.name,
      file_type: input.file.type,
      file_size: input.file.size,
    },
  };

  const { data, error } = await client
    .from('generations')
    .insert({
      location: null,
      thumbnail_url: input.thumbnailUrl,
      type: input.mediaType,
      project_id: input.projectId,
      params: generationParams,
      storage_mode: 'local',
      local_handle_id: input.localHandleId,
      local_file_name: input.file.name,
      local_file_size: input.file.size,
      local_file_mime: input.file.type,
    })
    .select()
    .single();

  if (error || !data) {
    throw error instanceof Error ? error : new Error('Failed to create local generation');
  }

  return data;
}

export async function createGenerationForLocalFile(
  input: CreateLocalGenerationInput,
): Promise<GenerationRow> {
  const thumbnailUrl = await uploadThumbnailOnly({
    file: input.file,
    mediaType: input.mediaType,
  });
  const localHandleId = await insertLocalMediaHandle(input.projectId);
  await saveHandle(localHandleId, input.handle);

  return insertLocalGeneration({
    file: input.file,
    projectId: input.projectId,
    mediaType: input.mediaType,
    thumbnailUrl,
    localHandleId,
  });
}

export async function createGenerationForUploadedImage(
  input: CreateGenerationForUploadedImageInput,
): Promise<GenerationRow> {
  const { imageFile, projectId, onProgress } = input;
  const { imageUrl, thumbnailUrl } = await uploadImageForVariant(imageFile, projectId, {
    onProgress,
  });

  const generationParams: GenerationParams = {
    source: 'upload',
    original_filename: imageFile.name,
    file_type: imageFile.type,
    file_size: imageFile.size,
  };

  return insertUploadedGeneration({
    projectId,
    type: 'image',
    location: imageUrl,
    thumbnailUrl: thumbnailUrl || imageUrl,
    generationParams,
  });
}

async function uploadVideoPosterFrame(videoFile: File): Promise<string> {
  const posterBlob = await extractVideoPosterFrame(videoFile);
  return uploadBlobToStorage(posterBlob, `${videoFile.name}-poster.jpg`, 'image/jpeg');
}

export async function createGenerationForUploadedVideo(
  input: CreateGenerationForUploadedVideoInput,
): Promise<GenerationRow> {
  const { videoFile, projectId, onProgress } = input;
  const videoUrl = await uploadVideoToStorage(videoFile, { onProgress });

  let thumbnailUrl = videoUrl;
  try {
    thumbnailUrl = await uploadVideoPosterFrame(videoFile);
  } catch (error) {
    normalizeAndPresentError(error, {
      context: `createGenerationForUploadedVideo:thumbnail:${videoFile.name}`,
      showToast: false,
    });
  }

  const generationParams: GenerationParams = {
    source: 'upload',
    original_filename: videoFile.name,
    file_type: videoFile.type,
    file_size: videoFile.size,
  };

  return insertUploadedGeneration({
    projectId,
    type: 'video',
    location: videoUrl,
    thumbnailUrl,
    generationParams,
  });
}
