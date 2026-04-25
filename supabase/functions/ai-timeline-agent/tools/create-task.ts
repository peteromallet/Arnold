import type {
  GenerationContext,
  PlacementIntent,
  SelectedClipPayload,
  SupabaseAdmin,
  TimelineState,
  ToolResult,
} from "../types.ts";
import type { TimelinePlacement } from "../../create-task/resolvers/shared/lineage.ts";
import { asPositiveNumber, asStringArray, asTrimmedString, isRecord } from "../utils.ts";
import { resolveSelectionContext } from "../selectedClips.ts";
import { createShotWithGenerations, resolveClipGenerationIds, resolveSelectedClipShot } from "./clips.ts";
import { createGenerationTask, type CreateGenerationTaskArgs } from "./generation.ts";

type ExpandPromptsLogger = {
  info?: (message: string, context?: Record<string, unknown>) => void;
  warn?: (message: string, context?: Record<string, unknown>) => void;
  error?: (message: string, context?: Record<string, unknown>) => void;
};

const APPEND_SHOT_POSITION = 2_147_483_647;
const MAX_BATCH_VARIATIONS = 16;
const SUPPORTED_CREATE_TASK_TYPES = new Set([
  "text-to-image",
  "style-transfer",
  "subject-transfer",
  "style-character-transfer",
  "scene-transfer",
  "image-to-video",
  "image-to-image",
  "magic-edit",
  "image-upscale",
  "video-enhance",
  "character-animate",
]);
const TASK_TYPE_TO_REFERENCE_MODE: Record<string, string> = {
  "style-transfer": "style",
  "subject-transfer": "subject",
  "style-character-transfer": "style-character",
  "scene-transfer": "scene",
};
const TASK_TYPES_REQUIRING_PROMPT = new Set([
  "text-to-image",
  "style-transfer",
  "subject-transfer",
  "style-character-transfer",
  "scene-transfer",
  "image-to-video",
  "image-to-image",
  "magic-edit",
]);
const TASK_TYPES_REQUIRING_REFERENCE_IMAGE = new Set([
  "style-transfer",
  "subject-transfer",
  "style-character-transfer",
  "scene-transfer",
  "image-to-image",
  "magic-edit",
  "image-upscale",
  "character-animate",
]);
const TASK_TYPES_REQUIRING_VIDEO = new Set([
  "video-enhance",
  "character-animate",
]);
const TASK_TYPES_SUPPORTING_SOURCE_PLACEMENT = new Set([
  "image-to-image",
  "magic-edit",
  "image-upscale",
]);

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeTimelinePlacementArg(value: unknown): TimelinePlacement | undefined {
  if (!isRecord(value)) {
    return undefined;
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
    return undefined;
  }

  return {
    timeline_id: timelineId,
    source_clip_id: sourceClipId,
    target_track: targetTrack,
    insertion_time: insertionTime,
    intent,
  };
}

function buildPlacementIntent(
  taskType: string,
  resolvedSelectionContexts: ReturnType<typeof resolveSelectionContext>,
): PlacementIntent | undefined {
  if (!TASK_TYPES_SUPPORTING_SOURCE_PLACEMENT.has(taskType)) {
    return undefined;
  }

  const timelineSelections = resolvedSelectionContexts.filter((context) => context.is_on_timeline);
  if (timelineSelections.length !== 1) {
    return undefined;
  }

  const anchor = timelineSelections[0];
  return {
    timeline_id: anchor.timeline_id,
    anchor_clip_id: anchor.clip_id,
    ...(anchor.generation_id ? { anchor_generation_id: anchor.generation_id } : {}),
    ...(anchor.variant_id ? { anchor_variant_id: anchor.variant_id } : {}),
    relation: "after",
    preferred_track_id: anchor.track_id,
    fallback_at: anchor.at + anchor.duration,
    fallback_track_id: anchor.track_id,
  };
}

function formatGenerationNotMaterializedError(generationId: string): string {
  return JSON.stringify({
    code: "generation_not_materialized",
    generation_id: generationId,
    message: "This generation still lives on the user's device. Open the gallery and let it upload before running a task.",
  });
}

async function findNonRemoteInputGeneration(
  supabaseAdmin: SupabaseAdmin,
  generationIds: Array<string | undefined>,
): Promise<string | null> {
  const uniqueGenerationIds = Array.from(new Set(
    generationIds.filter((generationId): generationId is string => Boolean(generationId && generationId.trim())),
  ));

  if (!uniqueGenerationIds.length) {
    return null;
  }

  const { data, error } = await supabaseAdmin
    .from("generations")
    .select("id, storage_mode")
    .in("id", uniqueGenerationIds);

  if (error) {
    throw new Error(`Failed to load generation storage modes: ${error.message}`);
  }

  for (const row of Array.isArray(data) ? data : []) {
    if (!isRecord(row)) {
      continue;
    }

    const generationId = asTrimmedString(row.id);
    const storageMode = asTrimmedString(row.storage_mode);
    if (generationId && storageMode && storageMode !== "remote") {
      return generationId;
    }
  }

  return null;
}

function withPlacementIntent(
  params: Record<string, unknown> | undefined,
  placementIntent: PlacementIntent | undefined,
): Record<string, unknown> | undefined {
  if (!placementIntent) {
    return params;
  }

  return {
    ...(params ?? {}),
    placement_intent: placementIntent,
  };
}

// Default reference strength params per mode — matches the form's REFERENCE_MODE_DEFAULTS for qwen-image
const REFERENCE_MODE_DEFAULTS: Record<string, Record<string, unknown>> = {
  style: { style_reference_strength: 1.1 },
  subject: { style_reference_strength: 0.4, subject_strength: 1.0 },
  "style-character": { style_reference_strength: 0.4, subject_strength: 1.0 },
  scene: { style_reference_strength: 0.4, in_this_scene: true, in_this_scene_strength: 1.0 },
};

async function expandPrompts(
  basePrompt: string,
  count: number,
  logger?: ExpandPromptsLogger,
  variationIntent?: string,
): Promise<string[]> {
  const logError = (message: string, context?: Record<string, unknown>) => {
    if (logger?.error) logger.error(message, context);
    else console.error(message, context ?? "");
  };
  if (logger?.info) {
    logger.info("[agent] expandPrompts: called", {
      count,
      loggerPresent: true,
      hasVariationIntent: Boolean(variationIntent && variationIntent.trim()),
    });
  } else {
    console.log("[agent] expandPrompts: called (no logger)", { count });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!supabaseUrl || !serviceRoleKey) {
      logError("[agent] expandPrompts: missing SUPABASE_URL or SERVICE_ROLE_KEY, returning base prompt only");
      return [basePrompt];
    }

    const response = await fetch(`${supabaseUrl}/functions/v1/ai-prompt`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${serviceRoleKey}`,
        apikey: serviceRoleKey,
      },
      body: JSON.stringify({
        task: "generate_prompts",
        overallPromptText: basePrompt,
        numberToGenerate: count,
        existingPrompts: [],
        temperature: 0.9,
        ...(variationIntent && variationIntent.trim() ? { variationIntent: variationIntent.trim() } : {}),
      }),
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "<unreadable>");
      logError("[agent] expandPrompts: ai-prompt HTTP error, returning base prompt only", {
        status: response.status,
        statusText: response.statusText,
        body: body.slice(0, 500),
        count,
      });
      return [basePrompt];
    }
    const data = await response.json() as { prompts?: string[] };
    if (Array.isArray(data.prompts) && data.prompts.length > 0) {
      const prompts = data.prompts.slice(0, count);
      const uniqueNormalized = new Set(
        prompts.map((p) => p.replace(/\s+/g, " ").trim().toLowerCase()),
      );
      if (logger?.info) {
        logger.info("[agent] expandPrompts: ai-prompt returned", {
          requested: count,
          returned: data.prompts.length,
          uniqueNormalized: uniqueNormalized.size,
          firstTwoHeads: prompts.slice(0, 2).map((p) => p.slice(0, 120)),
        });
      }
      return prompts;
    }
    logError("[agent] expandPrompts: ai-prompt returned no prompts, returning base prompt only", {
      responseKeys: Object.keys(data ?? {}),
      count,
    });
  } catch (err) {
    const message = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    logError("[agent] expandPrompts: threw, returning base prompt only", { error: message, count });
  }
  return [basePrompt];
}

function normalizePromptKey(prompt: string): string {
  return prompt.replace(/\s+/g, " ").trim().toLowerCase();
}

function ensureDistinctPrompts(prompts: string[], count: number): string[] {
  const uniquePrompts: string[] = [];
  const seen = new Set<string>();

  for (const candidate of prompts) {
    const prompt = candidate.trim();
    if (!prompt) {
      continue;
    }

    const key = normalizePromptKey(prompt);
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    uniquePrompts.push(prompt);

    if (uniquePrompts.length >= count) {
      return uniquePrompts;
    }
  }

  return uniquePrompts;
}

async function sha256Hex(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

// Batch timestamp ensures "10 more" creates new tasks instead of deduplicating against previous batches
let batchTimestamp: string | null = null;
function getBatchTimestamp(): string {
  if (!batchTimestamp) {
    batchTimestamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }
  return batchTimestamp;
}

async function buildBatchIdempotencyKey(args: CreateGenerationTaskArgs, batchIndex: number): Promise<string> {
  const payload = JSON.stringify({
    project_id: args.project_id,
    request: {
      prompt: args.prompt,
      task_type: args.task_type,
      reference_mode: args.reference_mode,
      reference_image_url: args.reference_image_url,
      shot_id: args.shot_id,
      model_name: args.model_name,
      image_urls: args.image_urls,
      video_url: args.video_url,
      strength: args.strength,
      based_on: args.based_on,
      generation_id: args.generation_id,
      timeline_placement: args.timeline_placement,
      params: args.params,
      batch_index: batchIndex,
      batch_ts: getBatchTimestamp(),
    },
  });
  const digest = await sha256Hex(payload);
  return `timeline-agent:${digest.slice(0, 40)}`;
}

export async function executeCreateTask(
  args: Record<string, unknown>,
  timelineState: TimelineState,
  selectedClips: SelectedClipPayload[] | undefined,
  supabaseAdmin: SupabaseAdmin,
  generationContext?: GenerationContext,
  timelineId = "",
  logger?: ExpandPromptsLogger,
): Promise<Pick<ToolResult, "result">> {
  const imageContext = generationContext?.image ?? null;
  const travelContext = generationContext?.travel ?? null;
  const taskType = asTrimmedString(args.task_type);
  const prompt = asTrimmedString(args.prompt);
  if (!taskType) {
    return { result: "create_task requires task_type." };
  }
  if (!SUPPORTED_CREATE_TASK_TYPES.has(taskType)) {
    return { result: `create_task does not support task_type ${taskType}.` };
  }
  if (TASK_TYPES_REQUIRING_PROMPT.has(taskType) && !prompt) {
    return { result: `create_task ${taskType} requires prompt.` };
  }

  const requestedReferenceImageUrls = asStringArray(args.reference_image_urls);
  const activeReference = imageContext?.activeReference ?? null;
  const shouldUseActiveReference = requestedReferenceImageUrls.length === 0
    && Boolean(TASK_TYPE_TO_REFERENCE_MODE[taskType])
    && Boolean(activeReference?.url);
  const referenceImageUrls = shouldUseActiveReference && activeReference?.url
    ? [activeReference.url]
    : requestedReferenceImageUrls;
  const referenceMode = asTrimmedString(args.reference_mode) ?? TASK_TYPE_TO_REFERENCE_MODE[taskType] ?? undefined;
  const videoUrl = asTrimmedString(args.video_url);
  const strength = typeof args.strength === "number" && Number.isFinite(args.strength) ? args.strength : undefined;
  if (strength !== undefined && (strength < 0 || strength > 1)) {
    return { result: "create_task strength must be between 0 and 1." };
  }
  const timelinePlacement = normalizeTimelinePlacementArg(args.timeline_placement);
  if (args.timeline_placement !== undefined && !timelinePlacement) {
    return {
      result: "create_task timeline_placement must include timeline_id, source_clip_id, target_track, insertion_time, and intent.",
    };
  }
  if (taskType === "image-to-video" && referenceImageUrls.length < 1) {
    return { result: "create_task image-to-video requires at least one reference_image_url." };
  }
  if (TASK_TYPES_REQUIRING_REFERENCE_IMAGE.has(taskType) && referenceImageUrls.length === 0) {
    return { result: `create_task ${taskType} requires reference_image_urls.` };
  }
  if (TASK_TYPES_REQUIRING_VIDEO.has(taskType) && !videoUrl) {
    return { result: `create_task ${taskType} requires video_url.` };
  }

  const resolvedSelectionContexts = resolveSelectionContext(selectedClips ?? [], timelineState, timelineId);
  const selectedClipEntries = (selectedClips ?? []).map((clip, index) => ({
    clip,
    resolvedContext: resolvedSelectionContexts[index],
  }));
  const selectedReferenceEntries = selectedClipEntries.filter(({ clip }) => referenceImageUrls.includes(clip.url));
  const selectedVideoEntry = videoUrl
    ? selectedClipEntries.find(({ clip }) => clip.url === videoUrl)
    : undefined;
  const selectedEntriesForShot = selectedVideoEntry && !selectedReferenceEntries.some(({ clip }) => clip.url === selectedVideoEntry.clip.url)
    ? [...selectedReferenceEntries, selectedVideoEntry]
    : selectedReferenceEntries;
  const selectedClipsForShot = selectedEntriesForShot.map(({ clip }) => clip);
  const placementIntent = buildPlacementIntent(taskType, resolvedSelectionContexts);
  const generationIds = resolveClipGenerationIds(selectedClipsForShot, timelineState.registry, timelineState.config);
  let shotId = (
    await resolveSelectedClipShot(supabaseAdmin, timelineState, selectedClipsForShot)
  ).shotId;
  let shotNote = "";
  const shotName = asTrimmedString(args.shot_name);
  const needsAutoShot = !shotId && generationIds.length > 0 && taskType === "image-to-video";
  if (!shotId && (shotName || needsAutoShot) && generationIds.length > 0) {
    const effectiveShotName = shotName || `Shot ${new Date().toISOString().slice(11, 19)}`;
    shotId = await createShotWithGenerations(supabaseAdmin, {
      projectId: timelineState.projectId,
      shotName: effectiveShotName,
      generationIds,
      position: APPEND_SHOT_POSITION,
    });
    shotNote = ` Created shot ${effectiveShotName} (${shotId}).`;
  } else if (shotId) {
    shotNote = ` Reused shot ${shotId}.`;
  }

  const asNew = args.as_new === true;
  const shouldDefaultPrimaryVariant = taskType === "image-to-image" || taskType === "magic-edit";
  const makePrimary = asNew
    ? undefined
    : typeof args.make_primary === "boolean"
      ? args.make_primary
      : shouldDefaultPrimaryVariant
        ? true
        : undefined;
  const basedOn = asNew
    ? undefined
    : (asTrimmedString(args.based_on) ?? (taskType === "video-enhance"
      ? selectedVideoEntry?.resolvedContext?.generation_id
      : selectedReferenceEntries[0]?.resolvedContext?.generation_id));
  const sourceVariantId = TASK_TYPES_SUPPORTING_SOURCE_PLACEMENT.has(taskType)
    ? (asTrimmedString(args.source_variant_id) ?? (taskType === "video-enhance"
      ? selectedVideoEntry?.resolvedContext?.variant_id
      : selectedReferenceEntries[0]?.resolvedContext?.variant_id))
    : asTrimmedString(args.source_variant_id);
  const generationId = taskType === "image-upscale"
    ? selectedReferenceEntries[0]?.resolvedContext?.generation_id
    : undefined;
  const nonRemoteGenerationId = await findNonRemoteInputGeneration(supabaseAdmin, [
    ...selectedReferenceEntries.map(({ resolvedContext }) => resolvedContext?.generation_id),
    selectedVideoEntry?.resolvedContext?.generation_id,
    basedOn,
    generationId,
  ]);
  if (nonRemoteGenerationId) {
    return { result: formatGenerationNotMaterializedError(nonRemoteGenerationId) };
  }
  const defaultModelName = taskType === "image-to-video"
    ? travelContext?.selectedModel
    : (taskType === "text-to-image" || Boolean(TASK_TYPE_TO_REFERENCE_MODE[taskType]))
      ? imageContext?.defaultModelName
      : undefined;
  const activeReferenceParams = shouldUseActiveReference && activeReference
    ? {
      ...(activeReference.styleReferenceStrength !== undefined
        ? { style_reference_strength: activeReference.styleReferenceStrength }
        : {}),
      ...(activeReference.subjectStrength !== undefined
        ? { subject_strength: activeReference.subjectStrength }
        : {}),
      ...(typeof activeReference.subjectDescription === "string" && activeReference.subjectDescription.trim()
        ? { subject_description: activeReference.subjectDescription }
        : {}),
      ...(activeReference.inThisScene !== undefined
        ? { in_this_scene: activeReference.inThisScene }
        : {}),
      ...(activeReference.inThisSceneStrength !== undefined
        ? { in_this_scene_strength: activeReference.inThisSceneStrength }
        : {}),
    }
    : undefined;
  const effectiveModel = referenceMode
    ? "qwen-image"
    : (asTrimmedString(args.model) ?? defaultModelName ?? undefined);
  const loraCategory = TASK_TYPE_TO_REFERENCE_MODE[taskType]
    ? "qwen"
    : (effectiveModel?.startsWith("z-") ? "z-image" : "qwen");
  const loras = imageContext?.selectedLorasByCategory?.[loraCategory] ?? [];
  const rawMotion = asFiniteNumber(args.amount_of_motion);
  const travelParams = taskType === "image-to-video"
    ? {
      amount_of_motion: rawMotion !== null
        ? rawMotion / 100
        : (travelContext ? travelContext.amountOfMotion / 100 : undefined),
      steps: asPositiveNumber(args.steps) ?? travelContext?.steps,
      guidance_scale: asFiniteNumber(args.guidance_scale) ?? travelContext?.guidanceScale,
      enhance_prompt: typeof args.enhance_prompt === "boolean" ? args.enhance_prompt : travelContext?.enhancePrompt,
      turbo_mode: typeof args.turbo_mode === "boolean" ? args.turbo_mode : travelContext?.turboMode,
      loras: travelContext?.loras?.map((lora) => ({ path: lora.path, strength: lora.strength })),
      negative_prompts: travelContext?.negativePrompt ? [travelContext.negativePrompt] : undefined,
      text_before_prompts: travelContext?.textBeforePrompts || undefined,
      text_after_prompts: travelContext?.textAfterPrompts || undefined,
      segment_frames: travelContext ? [travelContext.frames] : undefined,
      model_type: travelContext?.generationTypeMode,
      generation_mode: travelContext ? (travelContext.generationMode ?? "timeline") : undefined,
      phase_config: travelContext?.phaseConfig,
    }
    : undefined;
  // For transfer tasks: start with mode defaults, then overlay active reference params (which may override)
  const modeDefaults = referenceMode ? (REFERENCE_MODE_DEFAULTS[referenceMode] ?? {}) : {};
  const mergedParams = {
    ...modeDefaults,
    ...(activeReferenceParams ?? {}),
    ...(loras.length > 0 ? { loras } : {}),
  };
  const filteredTravelParams = travelParams
    ? Object.fromEntries(Object.entries(travelParams).filter(([, value]) => value !== undefined))
    : undefined;

  const requestedCount = asPositiveNumber(args.count) ?? 1;
  const variationIntent = asTrimmedString(args.variation_intent);
  const taskParams = taskType === "image-to-video"
    ? (filteredTravelParams && Object.keys(filteredTravelParams).length > 0 ? filteredTravelParams : undefined)
    : (() => {
      const variantParams = {
        ...mergedParams,
        ...(makePrimary !== undefined ? { is_primary: makePrimary } : {}),
      };
      return Object.keys(variantParams).length > 0 ? variantParams : undefined;
    })();
  const taskParamsWithPlacement = withPlacementIntent(taskParams, placementIntent);

  // When count > 1 and there's a prompt, expand into varied prompts and create separate tasks
  batchTimestamp = null; // Reset so each batch gets a unique timestamp
  if (requestedCount > 1 && prompt) {
    const targetCount = Math.min(requestedCount, MAX_BATCH_VARIATIONS);
    const expandedPrompts = ensureDistinctPrompts(
      await expandPrompts(prompt, targetCount, logger, variationIntent ?? undefined),
      targetCount,
    );
    let queuedCount = 0;
    let failedCount = 0;
    let deduplicatedCount = 0;

    for (const [index, expandedPrompt] of expandedPrompts.entries()) {
      const generationArgs: CreateGenerationTaskArgs = {
        project_id: timelineState.projectId,
        prompt: expandedPrompt,
        count: 1,
        task_type: taskType,
        reference_mode: referenceMode,
        reference_image_url: referenceImageUrls[0],
        image_urls: taskType === "image-to-video" ? referenceImageUrls : undefined,
        video_url: videoUrl ?? undefined,
        strength,
        model_name: effectiveModel,
        params: taskParamsWithPlacement,
        based_on: basedOn ?? undefined,
        source_variant_id: sourceVariantId ?? undefined,
        generation_id: generationId ?? undefined,
        shot_id: shotId ?? undefined,
        ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
      };

      const result = await createGenerationTask({
        ...generationArgs,
        idempotency_key: await buildBatchIdempotencyKey(generationArgs, index),
      });

      if (result.result.startsWith("Failed to create task:")) {
        failedCount += 1;
      } else if (result.result.includes("(deduplicated)")) {
        deduplicatedCount += 1;
      } else {
        queuedCount += 1;
      }
    }

    const summaryParts = [`Queued ${queuedCount} ${queuedCount === 1 ? "task" : "tasks"} with varied prompts.`];
    if (expandedPrompts.length < targetCount) {
      summaryParts.push(`Only ${expandedPrompts.length} of ${targetCount} distinct prompt variations were available from the prompt generator.`);
    }
    if (failedCount > 0) {
      summaryParts.push(`${failedCount} failed.`);
    }
    if (deduplicatedCount > 0) {
      summaryParts.push(`${deduplicatedCount} were duplicates of existing tasks.`);
    }
    if (requestedCount > MAX_BATCH_VARIATIONS) {
      summaryParts.push(`Requested ${requestedCount}, capped at ${MAX_BATCH_VARIATIONS}.`);
    }

    return { result: `${summaryParts.join(" ")}${shotNote}`.trim() };
  }

  const result = await createGenerationTask({
    project_id: timelineState.projectId,
    prompt: prompt ?? undefined,
    count: 1,
    task_type: taskType,
    reference_mode: referenceMode,
    reference_image_url: referenceImageUrls[0],
    image_urls: taskType === "image-to-video" ? referenceImageUrls : undefined,
    video_url: videoUrl ?? undefined,
    strength,
    model_name: effectiveModel,
    params: taskParamsWithPlacement,
    based_on: basedOn ?? undefined,
    source_variant_id: sourceVariantId ?? undefined,
    generation_id: generationId ?? undefined,
    shot_id: shotId ?? undefined,
    ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
  });
  return { result: `${result.result}${shotNote}`.trim() };
}
