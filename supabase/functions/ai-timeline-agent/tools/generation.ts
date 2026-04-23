import type { ToolHandler, ToolResult } from "../types.ts";
import type { TimelinePlacement } from "../../create-task/resolvers/shared/lineage.ts";
import {
  asPositiveNumber,
  asStringArray,
  asTrimmedString,
  isRecord,
} from "../utils.ts";

export interface CreateGenerationTaskArgs {
  project_id?: string;
  prompt?: string;
  count?: number;
  task_type?: string;
  idempotency_key?: string;
  params?: Record<string, unknown>;
  reference_image_url?: string;
  reference_mode?: string;
  shot_id?: string;
  model_name?: string;
  image_urls?: string[];
  video_url?: string;
  strength?: number;
  based_on?: string;
  source_variant_id?: string;
  generation_id?: string;
  timeline_placement?: TimelinePlacement;
}

type CreateTaskRequest = {
  family: string;
  input: Record<string, unknown>;
};

const IMAGE_GENERATION_MODELS = new Set([
  "qwen-image",
  "qwen-image-2512",
  "z-image",
]);

const TRAVEL_MODEL_NAME_BY_ID: Record<string, string> = {
  "wan-2.2": "wan_2_2_i2v_lightning_baseline_2_2_2",
  "ltx-2.3": "ltx2_22B",
  "ltx-2.3-fast": "ltx2_22B_distilled_1_1",
};

const TASK_LABELS: Record<string, string> = {
  "text-to-image": "text-to-image",
  "style-transfer": "style-transfer",
  "subject-transfer": "subject-transfer",
  "scene-transfer": "scene-transfer",
  "image-to-video": "image-to-video",
  "image-to-image": "image-to-image",
  "magic-edit": "magic-edit",
  "image-upscale": "image-upscale",
  "video-enhance": "video-enhance",
  "character-animate": "character-animate",
  image_generation: "image_generation",
  travel_between_images: "image-to-video",
  z_image_turbo_i2i: "image-to-image",
  magic_edit: "magic-edit",
  image_upscale: "image-upscale",
  video_enhance: "video-enhance",
  character_animate: "character-animate",
};

function asUnitInterval(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function normalizeImageGenerationModelName(value: unknown): string | null {
  const modelName = asTrimmedString(value);
  if (!modelName || modelName === "wan-2.2") {
    return null;
  }
  return IMAGE_GENERATION_MODELS.has(modelName) ? modelName : null;
}

function normalizeTravelModelName(value: unknown): string | null {
  const modelName = asTrimmedString(value);
  if (!modelName) {
    return null;
  }
  return TRAVEL_MODEL_NAME_BY_ID[modelName] ?? modelName;
}

function normalizeTimelinePlacement(value: unknown): TimelinePlacement | null {
  if (!isRecord(value)) {
    return null;
  }

  const timelineId = asTrimmedString(value.timeline_id);
  const sourceClipId = asTrimmedString(value.source_clip_id);
  const targetTrack = asTrimmedString(value.target_track);
  const insertionTime = typeof value.insertion_time === "number" && Number.isFinite(value.insertion_time)
    ? value.insertion_time
    : undefined;
  const intent = value.intent === "after_source" || value.intent === "replace"
    ? value.intent
    : undefined;

  if (!timelineId || !sourceClipId || !targetTrack || insertionTime === undefined || !intent) {
    return null;
  }

  return {
    timeline_id: timelineId,
    source_clip_id: sourceClipId,
    target_track: targetTrack,
    insertion_time: insertionTime,
    intent,
  };
}

function getTimelinePlacement(
  args: CreateGenerationTaskArgs,
  legacyInput: Record<string, unknown>,
): TimelinePlacement | null {
  const timelinePlacement = normalizeTimelinePlacement(args.timeline_placement)
    ?? normalizeTimelinePlacement(legacyInput.timeline_placement);
  delete legacyInput.timeline_placement;
  return timelinePlacement;
}

function buildImageGenerationInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const prompt = asTrimmedString(args.prompt) ?? asTrimmedString(legacyInput.prompt);
  const count = asPositiveNumber(args.count) ?? asPositiveNumber(legacyInput.count) ?? 1;
  const prompts = Array.isArray(legacyInput.prompts)
    ? legacyInput.prompts
    : (prompt ? [{ id: "prompt-1", fullPrompt: prompt }] : null);

  if (!prompts) {
    return null;
  }

  delete legacyInput.prompt;
  delete legacyInput.count;

  const referenceMode = asTrimmedString(args.reference_mode) ?? asTrimmedString(legacyInput.reference_mode);
  const referenceImageUrl = asTrimmedString(args.reference_image_url)
    ?? asTrimmedString(legacyInput.reference_image_url)
    ?? asTrimmedString(legacyInput.style_reference_image);
  const subjectReferenceImage = asTrimmedString(legacyInput.subject_reference_image) ?? referenceImageUrl;
  const modelName = normalizeImageGenerationModelName(args.model_name)
    ?? normalizeImageGenerationModelName(legacyInput.model_name)
    ?? (referenceMode ? "qwen-image" : null);
  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  return {
    ...legacyInput,
    prompts,
    imagesPerPrompt: asPositiveNumber(legacyInput.imagesPerPrompt) ?? count,
    ...(referenceMode ? { reference_mode: referenceMode } : {}),
    ...(referenceImageUrl ? { style_reference_image: referenceImageUrl } : {}),
    ...(subjectReferenceImage && referenceMode && referenceMode !== "style"
      ? { subject_reference_image: subjectReferenceImage }
      : {}),
    ...(shotId ? { shot_id: shotId } : {}),
    ...(modelName ? { model_name: modelName } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildTravelBetweenImagesInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const prompt = asTrimmedString(args.prompt) ?? asTrimmedString(legacyInput.prompt);
  const imageUrls = Array.from(new Set([
    ...asStringArray(args.image_urls),
    ...asStringArray(legacyInput.image_urls),
  ]));
  if (!prompt || imageUrls.length < 1) {
    return null;
  }

  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const modelName = normalizeTravelModelName(args.model_name) ?? normalizeTravelModelName(legacyInput.model_name);
  const basePrompts = asStringArray(legacyInput.base_prompts);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  return {
    ...legacyInput,
    image_urls: imageUrls,
    base_prompts: basePrompts.length ? basePrompts : [prompt],
    segment_frames: Array.isArray(legacyInput.segment_frames) ? legacyInput.segment_frames : [49],
    frame_overlap: Array.isArray(legacyInput.frame_overlap) ? legacyInput.frame_overlap : [2],
    ...(shotId ? { shot_id: shotId } : {}),
    ...(modelName ? { model_name: modelName } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildZImageI2IInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const imageUrl = asTrimmedString(args.reference_image_url) ?? asTrimmedString(legacyInput.image_url);
  if (!imageUrl) {
    return null;
  }

  const prompt = asTrimmedString(args.prompt) ?? asTrimmedString(legacyInput.prompt);
  const count = asPositiveNumber(args.count) ?? asPositiveNumber(legacyInput.numImages);
  const strength = asUnitInterval(args.strength) ?? asUnitInterval(legacyInput.strength);
  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const basedOn = asTrimmedString(args.based_on) ?? asTrimmedString(legacyInput.based_on);
  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  delete legacyInput.count;

  return {
    ...legacyInput,
    image_url: imageUrl,
    ...(prompt ? { prompt } : {}),
    ...(strength !== undefined ? { strength } : {}),
    ...(count ? { numImages: count } : {}),
    ...(shotId ? { shot_id: shotId } : {}),
    ...(basedOn ? { based_on: basedOn } : {}),
    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildMagicEditInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const prompt = asTrimmedString(args.prompt) ?? asTrimmedString(legacyInput.prompt);
  const imageUrl = asTrimmedString(args.reference_image_url) ?? asTrimmedString(legacyInput.image_url);
  if (!prompt || !imageUrl) {
    return null;
  }

  const count = asPositiveNumber(args.count) ?? asPositiveNumber(legacyInput.numImages);
  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const basedOn = asTrimmedString(args.based_on) ?? asTrimmedString(legacyInput.based_on);
  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  delete legacyInput.count;

  return {
    ...legacyInput,
    prompt,
    image_url: imageUrl,
    ...(count ? { numImages: count } : {}),
    ...(shotId ? { shot_id: shotId } : {}),
    ...(basedOn ? { based_on: basedOn } : {}),
    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildImageUpscaleInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const imageUrl = asTrimmedString(args.reference_image_url) ?? asTrimmedString(legacyInput.image_url);
  if (!imageUrl) {
    return null;
  }

  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const generationId = asTrimmedString(args.generation_id) ?? asTrimmedString(legacyInput.generation_id);
  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  return {
    ...legacyInput,
    image_url: imageUrl,
    ...(generationId ? { generation_id: generationId } : {}),
    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
    ...(shotId ? { shot_id: shotId } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildVideoEnhanceInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const videoUrl = asTrimmedString(args.video_url) ?? asTrimmedString(legacyInput.video_url);
  if (!videoUrl) {
    return null;
  }

  const shotId = asTrimmedString(args.shot_id) ?? asTrimmedString(legacyInput.shot_id);
  const basedOn = asTrimmedString(args.based_on) ?? asTrimmedString(legacyInput.based_on);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  return {
    ...legacyInput,
    video_url: videoUrl,
    enable_interpolation: true,
    enable_upscale: true,
    ...(shotId ? { shot_id: shotId } : {}),
    ...(basedOn ? { based_on: basedOn } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildCharacterAnimateInput(args: CreateGenerationTaskArgs): Record<string, unknown> | null {
  const legacyInput = isRecord(args.params) ? { ...args.params } : {};
  const characterImageUrl = asTrimmedString(args.reference_image_url)
    ?? asTrimmedString(legacyInput.character_image_url);
  const motionVideoUrl = asTrimmedString(args.video_url) ?? asTrimmedString(legacyInput.motion_video_url);
  if (!characterImageUrl || !motionVideoUrl) {
    return null;
  }

  const prompt = asTrimmedString(args.prompt) ?? asTrimmedString(legacyInput.prompt);
  const basedOn = asTrimmedString(args.based_on) ?? asTrimmedString(legacyInput.based_on);
  const timelinePlacement = getTimelinePlacement(args, legacyInput);

  return {
    ...legacyInput,
    character_image_url: characterImageUrl,
    motion_video_url: motionVideoUrl,
    mode: "animate",
    resolution: "480p",
    ...(prompt ? { prompt } : {}),
    ...(basedOn ? { based_on: basedOn } : {}),
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  };
}

function buildCreateTaskRequest(args: CreateGenerationTaskArgs): CreateTaskRequest | null {
  const taskType = asTrimmedString(args.task_type) ?? "image_generation";
  switch (taskType) {
    case "image-to-video": {
      const input = buildTravelBetweenImagesInput(args);
      return input ? { family: "travel_between_images", input } : null;
    }
    case "image-to-image": {
      const input = buildZImageI2IInput(args);
      return input ? { family: "z_image_turbo_i2i", input } : null;
    }
    case "magic-edit": {
      const input = buildMagicEditInput(args);
      return input ? { family: "magic_edit", input } : null;
    }
    case "image-upscale": {
      const input = buildImageUpscaleInput(args);
      return input ? { family: "image_upscale", input } : null;
    }
    case "video-enhance": {
      const input = buildVideoEnhanceInput(args);
      return input ? { family: "video_enhance", input } : null;
    }
    case "character-animate": {
      const input = buildCharacterAnimateInput(args);
      return input ? { family: "character_animate", input } : null;
    }
    default: {
      const input = buildImageGenerationInput(args);
      return input ? { family: "image_generation", input } : null;
    }
  }
}

function requireEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) {
    throw new Error(`[ai-timeline-agent] Missing ${name}`);
  }
  return value;
}

async function sha256Hex(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function getIdempotencyKey(args: CreateGenerationTaskArgs): Promise<string> {
  if (typeof args.idempotency_key === "string" && args.idempotency_key.trim()) {
    return args.idempotency_key.trim();
  }

  const payload = JSON.stringify({
    project_id: args.project_id,
    request: buildCreateTaskRequest(args),
  });
  const digest = await sha256Hex(payload);
  return `timeline-agent:${digest.slice(0, 40)}`;
}

export async function createGenerationTask(args: CreateGenerationTaskArgs): Promise<ToolResult> {
  if (typeof args.project_id !== "string" || !args.project_id.trim()) {
    return { result: "create_generation_task requires project_id." };
  }

  const request = buildCreateTaskRequest(args);
  if (!request) {
    return { result: "create_generation_task requires the required inputs for the selected task type." };
  }

  const supabaseUrl = requireEnv("SUPABASE_URL");
  const serviceRoleKey = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  const idempotencyKey = await getIdempotencyKey(args);

  const response = await fetch(`${supabaseUrl}/functions/v1/create-task`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${serviceRoleKey}`,
      apikey: serviceRoleKey,
    },
    body: JSON.stringify({
      family: request.family,
      input: request.input,
      project_id: args.project_id.trim(),
      dependant_on: null,
      idempotency_key: idempotencyKey,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    const message = errorText || "Failed to create task";
    return { result: `Failed to create task: ${message}` };
  }

  const data = await response.json() as { task_id?: string; deduplicated?: boolean };
  const taskLabel = TASK_LABELS[asTrimmedString(args.task_type) ?? ""]
    ?? TASK_LABELS[request.family]
    ?? request.family;

  return {
    result: data.task_id
      ? `Queued ${taskLabel} task ${data.task_id}${data.deduplicated ? " (deduplicated)." : "."}`
      : `Queued ${taskLabel} task.`,
  };
}

export const handlers: Record<string, ToolHandler> = {
  create_generation_task: (args) => createGenerationTask(args),
};
