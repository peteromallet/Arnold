import type { GenerationRow } from '@/domains/generation/types';
import { uploadImageToStorage } from '@/shared/lib/media/imageUploader';
import { resolveTaskInputMedia } from '@/shared/lib/media/resolveTaskInputMedia';
import { createTask } from '@/shared/lib/taskCreation';
import { beginLocalWorkerSession, type LocalWorkerSession } from '@/shared/lib/taskCreation/localWorkerSession';
import { createImageInpaintTask } from '@/shared/lib/tasks/imageEditing/imageInpaint';
import { buildMaskedEditTaskParams, type MaskedEditTaskParams } from '@/shared/lib/tasks/imageEditing/buildMaskedEditTaskParams';
import { convertToHiresFixApiParams } from '../useGenerationEditSettings';
import type { StrokeOverlayHandle } from '../../components/StrokeOverlay';
import type { EditAdvancedSettings, QwenEditModel } from './types';

type TaskType = 'inpaint' | 'annotate';

interface TaskTypeConfig {
  fileNamePrefix: string;
  createTask: typeof createImageInpaintTask | typeof createAnnotatedImageEditTask;
}

const TASK_CONFIGS: Record<TaskType, TaskTypeConfig> = {
  inpaint: {
    fileNamePrefix: 'inpaint_mask',
    createTask: createImageInpaintTask,
  },
  annotate: {
    fileNamePrefix: 'annotated_edit_mask',
    createTask: createAnnotatedImageEditTask,
  },
};

interface CreateInpaintingTaskWorkflowParams {
  taskType: TaskType;
  media: GenerationRow;
  selectedProjectId: string;
  shotId?: string;
  toolTypeOverride?: string;
  loras?: Array<{ url: string; strength: number }>;
  activeVariantId?: string | null;
  activeVariantLocation?: string | null;
  createAsGeneration?: boolean;
  advancedSettings?: EditAdvancedSettings;
  qwenEditModel?: QwenEditModel;
  inpaintPrompt: string;
  inpaintNumGenerations: number;
  actualGenerationId: string;
  strokeOverlay: StrokeOverlayHandle;
}

function createAnnotatedImageEditTask(
  params: MaskedEditTaskParams,
  session?: LocalWorkerSession,
): Promise<string> {
  return createTask(
    {
      project_id: params.project_id,
      family: 'masked_edit',
      input: {
        task_type: 'annotated_image_edit',
        image_url: params.image_url,
        mask_url: params.mask_url,
        prompt: params.prompt,
        num_generations: params.num_generations,
        generation_id: params.generation_id,
        shot_id: params.shot_id,
        tool_type: params.tool_type,
        loras: params.loras,
        create_as_generation: params.create_as_generation,
        source_variant_id: params.source_variant_id,
        hires_fix: params.hires_fix,
        qwen_edit_model: params.qwen_edit_model,
      },
    },
    session ? { localWorkerSession: session } : undefined,
  ).then((result) => result.task_id);
}

export async function createInpaintingTaskWorkflow({
  taskType,
  media,
  selectedProjectId,
  shotId,
  toolTypeOverride,
  loras,
  activeVariantId,
  activeVariantLocation,
  createAsGeneration,
  advancedSettings,
  qwenEditModel,
  inpaintPrompt,
  inpaintNumGenerations,
  actualGenerationId,
  strokeOverlay,
}: CreateInpaintingTaskWorkflowParams): Promise<string> {
  const config = TASK_CONFIGS[taskType];
  const maskImageData = strokeOverlay.exportMask({ pixelRatio: 1.5 });

  if (!maskImageData) {
    throw new Error('Failed to export mask from overlay');
  }

  const session = beginLocalWorkerSession();

  const maskBlob = await fetch(maskImageData).then((res) => res.blob());
  const maskFile = new File(
    [maskBlob],
    `${config.fileNamePrefix}_${media.id}_${Date.now()}.png`,
    { type: 'image/png' },
  );
  const maskUrl = await uploadImageToStorage(maskFile);

  let resolvedMediaUrl: string | undefined;
  try {
    const resolved = await resolveTaskInputMedia(media, session);
    resolvedMediaUrl = resolved.url;
  } catch {
    resolvedMediaUrl = undefined;
  }
  const sourceUrl = activeVariantLocation || resolvedMediaUrl || media.imageUrl;
  if (!sourceUrl) {
    throw new Error('Missing source media URL');
  }

  return config.createTask(
    buildMaskedEditTaskParams({
      projectId: selectedProjectId,
      imageUrl: sourceUrl,
      maskUrl,
      prompt: inpaintPrompt,
      numGenerations: inpaintNumGenerations,
      generationId: actualGenerationId,
      shotId,
      toolType: toolTypeOverride,
      loras,
      createAsGeneration,
      sourceVariantId: activeVariantId || undefined,
      hiresFix: convertToHiresFixApiParams(advancedSettings),
      qwenEditModel,
    }),
    session,
  );
}
