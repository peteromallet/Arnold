import type { ResolverResult, TaskFamilyResolver, TaskInsertObject } from "./types.ts";
import { setTaskLineageFields } from "./shared/lineage.ts";
import type { PlacementIntent } from "../../ai-timeline-agent/types.ts";
import {
  validateNumericRange,
  validateNonEmptyString,
  validateRequiredFields,
  validateUrlString,
} from "./shared/validation.ts";

interface ImageUpscaleTaskInput {
  image_url: string;
  generation_id?: string | null;
  source_variant_id?: string;
  scale_factor?: number;
  noise_scale?: number;
  output_format?: string;
  shot_id?: string;
  placement_intent?: PlacementIntent;
}

function buildQueuedTask(
  projectId: string,
  taskType: string,
  params: Record<string, unknown>,
): TaskInsertObject {
  return {
    project_id: projectId,
    task_type: taskType,
    params,
    status: "Queued",
    created_at: new Date().toISOString(),
    dependant_on: null,
  };
}

function validateImageUpscaleInput(input: ImageUpscaleTaskInput): void {
  validateRequiredFields(input, ["image_url"]);
  validateNonEmptyString(input.image_url, "image_url", "Image URL");
  validateUrlString(input.image_url, "image_url", "Image URL");
  validateNumericRange(input.scale_factor, {
    field: "scale_factor",
    label: "Scale factor",
    min: 1,
    max: 8,
  });
}

function buildImageUpscaleTaskParams(input: ImageUpscaleTaskInput): Record<string, unknown> {
  const params: Record<string, unknown> = {
    image: input.image_url,
    scale_factor: input.scale_factor ?? 2,
    noise_scale: input.noise_scale ?? 0.1,
    output_format: input.output_format ?? "jpeg",
  };

  if (input.generation_id) {
    params.generation_id = input.generation_id;
  }

  setTaskLineageFields(params, {
    shotId: input.shot_id,
    basedOn: input.generation_id ?? undefined,
    sourceVariantId: input.source_variant_id,
    markPrimaryWhenBasedOn: true,
    placementIntent: input.placement_intent,
  });

  return params;
}

export const imageUpscaleResolver: TaskFamilyResolver = (request, context): ResolverResult => {
  const input = request.input as unknown as ImageUpscaleTaskInput;
  validateImageUpscaleInput(input);

  return {
    tasks: [
      buildQueuedTask(
        context.projectId,
        "image-upscale",
        buildImageUpscaleTaskParams(input),
      ),
    ],
  };
};
