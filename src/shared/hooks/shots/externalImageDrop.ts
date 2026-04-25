import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import type { Database } from '@/integrations/supabase/databasePublicTypes';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { cropImageToProjectAspectRatio } from '@/shared/lib/media/imageCropper';
import { parseRatio } from '@/shared/lib/media/aspectRatios';
import { createGenerationForUploadedImage } from '@/shared/lib/media/createGenerationFromFile';

export interface ExternalImageDropVariables {
  imageFiles: File[];
  targetShotId: string | null;
  currentProjectQueryKey: string | null;
  currentShotCount: number;
  skipAutoPosition?: boolean;
  positions?: number[];
  onProgress?: (fileIndex: number, fileProgress: number, overallProgress: number) => void;
}

export interface UploadedGenerationMetadata {
  generationId: string;
  location: string | null;
  thumbnail_url: string | null;
  type: string | null;
  created_at: string;
  params: Database['public']['Tables']['generations']['Row']['params'];
  primary_variant_id: string | null;
  shot_generation_id: string;
  timeline_frame: number | null;
}

interface CropConfig {
  shouldCrop: boolean;
  targetAspectRatio: number | null;
  aspectRatioSource: 'none' | 'shot' | 'project';
}

interface ProcessDroppedImagesInput {
  variables: ExternalImageDropVariables;
  projectId: string;
  createShot: (input: {
    name: string;
    projectId: string;
    shouldSelectAfterCreation: boolean;
  }) => Promise<{ shot?: { id?: string } } | null | undefined>;
  addImageToShot: (input: {
    shot_id: string;
    generation_id: string;
    project_id: string;
    imageUrl?: string;
    thumbUrl?: string;
    timelineFrame?: number;
  }) => Promise<unknown>;
  addImageToShotWithoutPosition: (input: {
    shot_id: string;
    generation_id: string;
    project_id: string;
    imageUrl?: string;
    thumbUrl?: string;
  }) => Promise<unknown>;
  createGeneration?: typeof createGenerationForUploadedImage;
}

const buildProgressHandler = (
  onProgress: ExternalImageDropVariables['onProgress'],
  fileIndex: number,
  totalFiles: number,
) =>
  onProgress
    ? (progress: number) => {
        const overallProgress = Math.round(((fileIndex + progress / 100) / totalFiles) * 100);
        onProgress(fileIndex, progress, overallProgress);
      }
    : undefined;


async function getCropConfig(projectId: string, shotId: string | null): Promise<CropConfig> {
  const config: CropConfig = {
    shouldCrop: true,
    targetAspectRatio: null,
    aspectRatioSource: 'none',
  };

  try {
    const { data: projectData } = await supabase().from('projects')
      .select('aspect_ratio, settings')
      .eq('id', projectId)
      .single();

    let shotAspectRatio: string | null = null;
    if (shotId) {
      const { data: shotData } = await supabase().from('shots')
        .select('aspect_ratio')
        .eq('id', shotId)
        .single();
      shotAspectRatio = shotData?.aspect_ratio || null;
    }

    const uploadSettings = (projectData?.settings as Record<string, unknown> | null)?.upload as Record<string, unknown> | undefined;
    const cropToProjectSize = uploadSettings?.cropToProjectSize;
    config.shouldCrop = typeof cropToProjectSize === 'boolean' ? cropToProjectSize : true;

    const effectiveRatioStr = shotAspectRatio || projectData?.aspect_ratio || null;
    if (effectiveRatioStr) {
      config.targetAspectRatio = parseRatio(effectiveRatioStr);
      config.aspectRatioSource = shotAspectRatio ? 'shot' : 'project';
    }
  } catch (error) {
    normalizeAndPresentError(error, { context: 'useShotCreation:aspectRatio', showToast: false });
  }

  return config;
}

async function cropFilesIfNeeded(imageFiles: File[], config: CropConfig): Promise<File[]> {
  const { shouldCrop, targetAspectRatio } = config;
  if (!shouldCrop || !targetAspectRatio || Number.isNaN(targetAspectRatio)) {
    return imageFiles;
  }

  try {
    const cropPromises = imageFiles.map(async (file) => {
      try {
        if (!file.type.startsWith('image/')) {
          return file;
        }

        const result = await cropImageToProjectAspectRatio(file, targetAspectRatio);
        return result?.croppedFile || file;
      } catch (error) {
        normalizeAndPresentError(error, { context: `useShotCreation:crop:${file.name}`, showToast: false });
        return file;
      }
    });

    return await Promise.all(cropPromises);
  } catch (error) {
    normalizeAndPresentError(error, { context: 'useShotCreation:batchCrop', showToast: false });
    return imageFiles;
  }
}

async function ensureTargetShotId(
  targetShotId: string | null,
  currentShotCount: number,
  projectId: string,
  createShot: ProcessDroppedImagesInput['createShot'],
): Promise<string | null> {
  if (targetShotId) {
    return targetShotId;
  }

  const newShotName = `Shot ${currentShotCount + 1}`;
  const result = await createShot({
    name: newShotName,
    projectId,
    shouldSelectAfterCreation: true,
  });

  if (!result?.shot?.id) {
    toast.error('Failed to create new shot.');
    return null;
  }

  return result.shot.id;
}

async function attachGenerationToShot(input: {
  shotId: string;
  generation: Database['public']['Tables']['generations']['Row'];
  projectId: string;
  thumbnailUrl?: string | null;
  fileIndex: number;
  variables: ExternalImageDropVariables;
  addImageToShot: ProcessDroppedImagesInput['addImageToShot'];
  addImageToShotWithoutPosition: ProcessDroppedImagesInput['addImageToShotWithoutPosition'];
}): Promise<{ shot_generation_id: string; timeline_frame: number | null }> {
  const {
    shotId,
    generation,
    projectId,
    thumbnailUrl,
    fileIndex,
    variables,
    addImageToShot,
    addImageToShotWithoutPosition,
  } = input;

  const { positions, skipAutoPosition } = variables;
  const explicitPosition = positions && positions.length > fileIndex ? positions[fileIndex] : undefined;
  const baseInput = {
    shot_id: shotId,
    generation_id: generation.id as string,
    project_id: projectId,
    imageUrl: generation.location || undefined,
    thumbUrl: thumbnailUrl || generation.location || undefined,
  };

  if (explicitPosition !== undefined) {
    const result = await addImageToShot({
      ...baseInput,
      timelineFrame: explicitPosition,
    });
    const shotGenerationId = typeof (result as { id?: unknown })?.id === 'string'
      ? (result as { id: string }).id
      : null;
    if (!shotGenerationId) {
      throw new Error('Failed to attach uploaded generation with explicit position.');
    }
    return {
      shot_generation_id: shotGenerationId,
      timeline_frame: typeof (result as { timeline_frame?: unknown })?.timeline_frame === 'number'
        ? (result as { timeline_frame: number }).timeline_frame
        : explicitPosition,
    };
  }

  if (skipAutoPosition) {
    const result = await addImageToShotWithoutPosition(baseInput);
    const shotGenerationId = typeof (result as { id?: unknown })?.id === 'string'
      ? (result as { id: string }).id
      : null;
    if (!shotGenerationId) {
      throw new Error('Failed to attach uploaded generation without position.');
    }
    return {
      shot_generation_id: shotGenerationId,
      timeline_frame: null,
    };
  }

  const result = await addImageToShot({
    ...baseInput,
  });
  const shotGenerationId = typeof (result as { id?: unknown })?.id === 'string'
    ? (result as { id: string }).id
    : null;
  if (!shotGenerationId) {
    throw new Error('Failed to attach uploaded generation to shot.');
  }
  return {
    shot_generation_id: shotGenerationId,
    timeline_frame: typeof (result as { timeline_frame?: unknown })?.timeline_frame === 'number'
      ? (result as { timeline_frame: number }).timeline_frame
      : null,
  };
}

async function processSingleDroppedImage(input: {
  imageFile: File;
  fileIndex: number;
  totalFiles: number;
  shotId: string;
  projectId: string;
  variables: ExternalImageDropVariables;
  addImageToShot: ProcessDroppedImagesInput['addImageToShot'];
  addImageToShotWithoutPosition: ProcessDroppedImagesInput['addImageToShotWithoutPosition'];
  createGeneration: typeof createGenerationForUploadedImage;
}): Promise<UploadedGenerationMetadata | null> {
  const {
    imageFile,
    fileIndex,
    totalFiles,
    shotId,
    projectId,
    variables,
    addImageToShot,
    addImageToShotWithoutPosition,
    createGeneration,
  } = input;

  let generation: Database['public']['Tables']['generations']['Row'];
  try {
    generation = await createGeneration({
      imageFile,
      projectId,
      onProgress: buildProgressHandler(variables.onProgress, fileIndex, totalFiles),
    });
  } catch (error) {
    toast.error(`Failed to create generation data for ${imageFile.name}: ${(error as Error).message}`);
    return null;
  }

  if (!generation?.id) {
    toast.error(`Failed to create generation record for ${imageFile.name}.`);
    return null;
  }

  const attachment = await attachGenerationToShot({
    shotId,
    generation,
    projectId,
    thumbnailUrl: generation.thumbnail_url ?? generation.location,
    fileIndex,
    variables,
    addImageToShot,
    addImageToShotWithoutPosition,
  });

  return {
    generationId: generation.id,
    location: generation.location,
    thumbnail_url: generation.thumbnail_url ?? generation.location,
    type: generation.type,
    created_at: generation.created_at,
    params: generation.params,
    primary_variant_id: generation.primary_variant_id,
    shot_generation_id: attachment.shot_generation_id,
    timeline_frame: attachment.timeline_frame,
  };
}
export async function processDroppedImages(
  input: ProcessDroppedImagesInput,
): Promise<{ shotId: string; generationIds: string[]; generationMetadata: UploadedGenerationMetadata[] } | null> {
  const {
    variables,
    projectId,
    createShot,
    addImageToShot,
    addImageToShotWithoutPosition,
    createGeneration = createGenerationForUploadedImage,
  } = input;
  const { imageFiles, targetShotId, currentShotCount } = variables;

  const cropConfig = await getCropConfig(projectId, targetShotId);
  const processedFiles = await cropFilesIfNeeded(imageFiles, cropConfig);
  const shotId = await ensureTargetShotId(targetShotId, currentShotCount, projectId, createShot);
  if (!shotId) {
    return null;
  }

  const generationIds: string[] = [];
  const generationMetadata: UploadedGenerationMetadata[] = [];
  for (let fileIndex = 0; fileIndex < processedFiles.length; fileIndex++) {
    const imageFile = processedFiles[fileIndex];
    try {
      const metadata = await processSingleDroppedImage({
        imageFile,
        fileIndex,
        totalFiles: processedFiles.length,
        shotId,
        projectId,
        variables,
        addImageToShot,
        addImageToShotWithoutPosition,
        createGeneration,
      });
      if (metadata) {
        generationIds.push(metadata.generationId);
        generationMetadata.push(metadata);
      }
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useShotCreation', toastTitle: `Failed to process file ${imageFile.name}` });
    }
  }

  return generationIds.length > 0 ? { shotId, generationIds, generationMetadata } : null;
}
