import type { ResolverResult, TaskFamilyResolver, TaskInsertObject } from "./types.ts";
import {
  validateLoraConfigs,
} from "./shared/loras.ts";
import { resolveSeed32Bit, validateSeed32Bit } from "./shared/seed.ts";
import {
  setTaskLineageFields,
  type TimelinePlacement,
} from "./shared/lineage.ts";
import type { PlacementIntent } from "../../ai-timeline-agent/types.ts";
import {
  validateNonEmptyString,
  validateNumericRange,
  validateRequiredFields,
  validateUrlString,
} from "./shared/validation.ts";

interface FalLoraConfig {
  path: string;
  scale?: number;
}

interface ZImageTurboImageToImageTaskInput {
  image_url: string;
  prompt?: string;
  strength?: number;
  enable_prompt_expansion?: boolean;
  seed?: number;
  numImages?: number;
  loras?: FalLoraConfig[];
  shot_id?: string;
  based_on?: string;
  source_variant_id?: string;
  create_as_generation?: boolean;
  tool_type?: string;
  timeline_placement?: TimelinePlacement;
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

function validateZImageTurboInput(input: ZImageTurboImageToImageTaskInput): void {
  validateRequiredFields(input, ["image_url"]);
  validateNonEmptyString(input.image_url, "image_url", "Image URL");
  validateUrlString(input.image_url, "image_url", "Image URL");
  validateNumericRange(input.strength, {
    field: "strength",
    label: "Strength",
    min: 0,
    max: 1,
  });
  validateNumericRange(input.numImages, {
    field: "numImages",
    label: "Number of images",
    min: 1,
    max: 16,
  });
  validateSeed32Bit(input.seed);
  validateLoraConfigs(
    input.loras?.map((lora) => ({ path: lora.path, strength: lora.scale ?? 1 })),
    {
      pathField: "path",
      strengthField: "strength",
      strengthLabel: "scale",
      min: 0,
      max: 2,
    },
  );
}

function buildTaskParams(
  input: ZImageTurboImageToImageTaskInput,
  seed: number | undefined,
): Record<string, unknown> {
  const params: Record<string, unknown> = {
    image_url: input.image_url,
    prompt: input.prompt ?? "",
    strength: input.strength ?? 0.6,
    enable_prompt_expansion: input.enable_prompt_expansion ?? false,
    num_images: 1,
    image_size: "auto",
    num_inference_steps: 8,
    output_format: "png",
    enable_safety_checker: true,
    add_in_position: false,
  };

  if (seed !== undefined) {
    params.seed = seed;
  }

  if (input.loras && input.loras.length > 0) {
    params.loras = input.loras.map((lora) => ({
      path: lora.path,
      scale: lora.scale ?? 1.0,
    }));
    params.acceleration = "none";
  } else {
    params.acceleration = "high";
  }

  setTaskLineageFields(params, {
    shotId: input.shot_id,
    basedOn: input.based_on,
    sourceVariantId: input.source_variant_id,
    createAsGeneration: input.create_as_generation,
    toolType: input.tool_type,
    timelinePlacement: input.timeline_placement,
    placementIntent: input.placement_intent,
  });

  return params;
}

export const zImageTurboI2IResolver: TaskFamilyResolver = (request, context): ResolverResult => {
  const input = request.input as unknown as ZImageTurboImageToImageTaskInput;
  validateZImageTurboInput(input);

  const taskCount = input.numImages ?? 1;
  const baseSeed = resolveSeed32Bit({ seed: input.seed, field: "seed" });

  return {
    tasks: Array.from({ length: taskCount }, (_, index) => {
      const seed = taskCount > 1 ? baseSeed + index : (input.seed ?? baseSeed);
      return buildQueuedTask(
        context.projectId,
        "z_image_turbo_i2i",
        buildTaskParams(input, seed),
      );
    }),
  };
};
