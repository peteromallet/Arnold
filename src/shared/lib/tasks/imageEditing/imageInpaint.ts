import { createTask } from '@/shared/lib/taskCreation';
import type { LocalWorkerSession } from '@/shared/lib/taskCreation/localWorkerSession';
import type { MaskedEditTaskParams } from './buildMaskedEditTaskParams';

type CreateImageInpaintTaskParams = MaskedEditTaskParams;

export function createImageInpaintTask(
  params: CreateImageInpaintTaskParams,
  session?: LocalWorkerSession,
): Promise<string> {
  return createTask(
    {
      project_id: params.project_id,
      family: 'masked_edit',
      input: {
        task_type: 'image_inpaint',
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
