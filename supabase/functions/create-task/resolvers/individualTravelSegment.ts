import type { ResolverContext, ResolverResult, TaskFamilyResolver, TaskInsertObject } from "./types.ts";
import { resolveProjectResolutionFromAspectRatio } from "./shared/resolution.ts";
import { resolveSeed32Bit } from "./shared/seed.ts";
import {
  buildIndividualSegmentFamilyContract,
  composeTaskFamilyPayload,
} from "./shared/taskContracts.ts";
import { mapPathLorasToStrengthRecord } from "./shared/loras.ts";
import {
  TaskValidationError,
} from "./shared/validation.ts";

interface PathLoraConfig {
  path: string;
  strength: number;
}

interface IndividualTravelSegmentInput {
  parent_generation_id?: string;
  shot_id?: string;
  child_generation_id?: string;
  originalParams?: Record<string, unknown>;
  segment_index: number;
  start_image_url: string;
  end_image_url?: string;
  start_image_generation_id?: string;
  end_image_generation_id?: string;
  start_image_variant_id?: string;
  end_image_variant_id?: string;
  pair_shot_generation_id?: string;
  model_name?: string;
  model_type?: "i2v" | "vace";
  base_prompt?: string;
  enhanced_prompt?: string;
  negative_prompt?: string;
  num_frames?: number;
  frame_overlap_from_previous?: number;
  continuation_config?: Record<string, unknown>;
  seed?: number;
  random_seed?: boolean;
  amount_of_motion?: number;
  advanced_mode?: boolean;
  phase_config?: Record<string, unknown>;
  motion_mode?: "basic" | "presets" | "advanced";
  selected_phase_preset_id?: string | null;
  loras?: PathLoraConfig[];
  travel_guidance?: Record<string, unknown>;
  structure_guidance?: Record<string, unknown>;
  structure_videos?: Record<string, unknown>[];
  generation_name?: string;
  parsed_resolution_wh?: string;
  num_inference_steps?: number;
  guidance_scale?: number;
  make_primary_variant?: boolean;
  is_last_segment?: boolean;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
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

async function ensureShotParentGenerationId(
  context: Parameters<TaskFamilyResolver>[1],
  input: IndividualTravelSegmentInput,
): Promise<string> {
  if (input.parent_generation_id) {
    return input.parent_generation_id;
  }
  if (!input.shot_id) {
    throw new Error("parent_generation_id is required when shot_id is missing");
  }

  const { data, error } = await context.supabaseAdmin.rpc("ensure_shot_parent_generation", {
    p_shot_id: input.shot_id,
    p_project_id: context.projectId,
  });

  if (error) {
    throw new Error(`Failed to ensure parent generation for shot ${input.shot_id}: ${error.message}`);
  }
  if (!data || typeof data !== "string") {
    throw new Error(`ensure_shot_parent_generation returned invalid parent ID for shot ${input.shot_id}`);
  }
  return data;
}

async function resolveSegmentGenerationRoute(
  context: Parameters<TaskFamilyResolver>[1],
  input: IndividualTravelSegmentInput,
): Promise<{ parentGenerationId: string; childGenerationId?: string }> {
  const parentGenerationId = await ensureShotParentGenerationId(context, input);

  // When the frontend provides a specific child_generation_id (the lightbox is
  // pointing at a row), trust it after verifying it actually belongs to this
  // parent and pair position. This ensures the new variant lands on the same
  // generation row the UI is rendering — without it, a pair-lookup against
  // historical duplicates can pick a different row than the one shown.
  if (input.child_generation_id) {
    const { data: candidate, error: candidateError } = await context.supabaseAdmin
      .from("generations")
      .select("id, parent_generation_id, pair_shot_generation_id")
      .eq("id", input.child_generation_id)
      .maybeSingle();
    if (candidateError) {
      throw new Error(`validateChildGenerationId failed: ${candidateError.message}`);
    }
    if (
      candidate
      && candidate.parent_generation_id === parentGenerationId
      && (!input.pair_shot_generation_id
        || candidate.pair_shot_generation_id === input.pair_shot_generation_id)
    ) {
      return { parentGenerationId, childGenerationId: candidate.id };
    }
    // Fall through: candidate is stale, missing, or doesn't match this slot.
  }

  if (input.pair_shot_generation_id) {
    // Recovery path when no valid child_generation_id was supplied. Order by
    // created_at DESC so historical duplicates (legacy slots with >1 row for
    // the same pair) at least resolve deterministically to the newest, which
    // is the one buildSegmentSlots also picks for display.
    const { data: pairMatches, error: pairError } = await context.supabaseAdmin
      .from("generations")
      .select("id")
      .eq("parent_generation_id", parentGenerationId)
      .eq("pair_shot_generation_id", input.pair_shot_generation_id)
      .order("created_at", { ascending: false })
      .limit(1);
    if (pairError) {
      throw new Error(`lookupChildGenerationIdByPair failed: ${pairError.message}`);
    }
    const pairMatch = pairMatches?.[0];
    if (typeof pairMatch?.id === "string") {
      return { parentGenerationId, childGenerationId: pairMatch.id };
    }
    // No child at this pair position — this is a new segment.
    return { parentGenerationId };
  }

  // Only fall back to child_order when no pair_shot_generation_id was provided
  const { data, error } = await context.supabaseAdmin
    .from("generations")
    .select("id")
    .eq("parent_generation_id", parentGenerationId)
    .eq("child_order", input.segment_index)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(`lookupChildGenerationIdByOrder failed: ${error.message}`);
  }

  return {
    parentGenerationId,
    childGenerationId: typeof data?.id === "string" ? data.id : undefined,
  };
}

function resolveFinalResolution(
  input: IndividualTravelSegmentInput,
  aspectRatio: string | null,
): string {
  const originalParams = asRecord(input.originalParams);
  const originalOrchestrator = asRecord(originalParams?.orchestrator_details);
  const originalResolution = asString(input.parsed_resolution_wh)
    ?? asString(originalParams?.parsed_resolution_wh)
    ?? asString(originalOrchestrator?.parsed_resolution_wh);

  return resolveProjectResolutionFromAspectRatio({
    aspectRatio,
    customResolution: originalResolution,
  }).resolution;
}

function validateInput(input: IndividualTravelSegmentInput): void {
  const errors: string[] = [];
  if (!input.parent_generation_id && !input.shot_id) {
    errors.push("Either parent_generation_id or shot_id is required");
  }
  if (typeof input.segment_index !== "number" || input.segment_index < 0) {
    errors.push("segment_index must be a non-negative number");
  }
  if (!input.start_image_url) {
    errors.push("start_image_url is required");
  }
  if (errors.length > 0) {
    throw new TaskValidationError(errors.join(", "));
  }
}

interface SegmentLayout {
  segmentFramesExpanded: number[];
  frameOverlapExpanded: number[];
  stitchedStartFrame: number;
  guidanceStartFrame: number;
}

function buildIndividualTravelSegmentParams(
  input: IndividualTravelSegmentInput,
  finalResolution: string,
  parentGenerationId: string,
  childGenerationId: string | undefined,
  projectId: string,
  segmentLayout?: SegmentLayout,
): Record<string, unknown> {
  const inputImages = input.end_image_url
    ? [input.start_image_url, input.end_image_url]
    : [input.start_image_url];
  const finalSeed = resolveSeed32Bit({
    seed: input.seed,
    randomize: input.random_seed === true,
    fallbackSeed: 789,
    field: "seed",
  });
  const additionalLoras = input.loras && input.loras.length > 0
    ? mapPathLorasToStrengthRecord(input.loras)
    : {};
  const phaseConfig = input.phase_config as {
    phases?: Array<{ guidance_scale?: number; loras?: Array<{ url: string; multiplier: string }> }>;
    flow_shift?: number;
    sample_solver?: string;
    model_switch_phase?: number;
    num_phases?: number;
    steps_per_phase?: number[];
  } | undefined;
  const numInferenceSteps = input.num_inference_steps
    ?? (phaseConfig?.steps_per_phase?.reduce((sum, steps) => sum + steps, 0) ?? 6);
  // Start from the original orchestrator_details (preserves pipeline layout fields
  // like segment_frames_expanded, frame_overlap_expanded, etc.) then override with
  // the user-editable fields. This way new fields added to the pipeline path don't
  // silently disappear on frontend retries.
  const origParams = asRecord(input.originalParams);
  const origOrchestrator = asRecord(origParams?.orchestrator_details) ?? {};
  const orchestratorDetails: Record<string, unknown> = {
    ...origOrchestrator,
    generation_source: "individual_segment",
    parsed_resolution_wh: finalResolution,
    input_image_paths_resolved: inputImages,
    seed_base: finalSeed,
    model_name: input.model_name ?? "wan_2_2_i2v_lightning_baseline_2_2_2",
    flow_shift: phaseConfig?.flow_shift ?? 5,
    sample_solver: phaseConfig?.sample_solver ?? "euler",
    guidance_scale: input.guidance_scale ?? phaseConfig?.phases?.[0]?.guidance_scale ?? 1,
    guidance2_scale: phaseConfig?.phases?.[1]?.guidance_scale ?? 1,
    guidance_phases: phaseConfig?.num_phases ?? 2,
    num_inference_steps: numInferenceSteps,
    model_switch_phase: phaseConfig?.model_switch_phase ?? 1,
    additional_loras: additionalLoras,
    advanced_mode: input.advanced_mode ?? (input.motion_mode !== "basic" && !!input.phase_config),
    motion_mode: input.motion_mode ?? "basic",
    amount_of_motion: input.amount_of_motion ?? 0.5,
    parent_generation_id: parentGenerationId,
    fps_helpers: 16,
    ...(input.model_type ? { model_type: input.model_type } : {}),
    independent_segments: !input.continuation_config,
    chain_segments: Boolean(input.continuation_config),
    ...(input.continuation_config ? { continuation_config: input.continuation_config } : {}),
    ...(input.travel_guidance ? { travel_guidance: input.travel_guidance } : {}),
    ...(segmentLayout ? {
      segment_frames_expanded: segmentLayout.segmentFramesExpanded,
      frame_overlap_expanded: segmentLayout.frameOverlapExpanded,
    } : {}),
  };

  const hasPairShotGenerationId = Boolean(
    input.pair_shot_generation_id || input.start_image_variant_id || input.end_image_variant_id,
  );

  const composedPayload = composeTaskFamilyPayload({
    taskFamily: "individual_travel_segment",
    orchestratorDetails,
    orchestrationInput: {
      taskFamily: "individual_travel_segment",
      parentGenerationId,
      childGenerationId,
      childOrder: input.segment_index,
      shotId: input.shot_id,
    },
    taskViewInput: {
      inputImages,
      prompt: input.base_prompt,
      enhancedPrompt: input.enhanced_prompt,
      negativePrompt: input.negative_prompt,
      modelName: input.model_name,
      resolution: finalResolution,
    },
    familyContract: buildIndividualSegmentFamilyContract({
      segmentIndex: input.segment_index,
      hasEndImage: Boolean(input.end_image_url),
      hasPairShotGenerationId,
    }),
  });

  return {
    flow_shift: phaseConfig?.flow_shift ?? 5,
    lora_names: [],
    model_name: input.model_name ?? "wan_2_2_i2v_lightning_baseline_2_2_2",
    project_id: projectId,
    shot_id: input.shot_id,
    base_prompt: input.base_prompt ?? "",
    fps_helpers: 16,
    seed_to_use: finalSeed,
    cfg_zero_step: -1,
    sample_solver: phaseConfig?.sample_solver ?? "euler",
    segment_index: input.segment_index,
    guidance_scale: input.guidance_scale ?? phaseConfig?.phases?.[0]?.guidance_scale ?? 1,
    cfg_star_switch: 0,
    guidance2_scale: phaseConfig?.phases?.[1]?.guidance_scale ?? 1,
    guidance_phases: phaseConfig?.num_phases ?? 2,
    is_last_segment: input.is_last_segment ?? !input.end_image_url,
    negative_prompt: input.negative_prompt ?? "",
    is_first_segment: input.segment_index === 0,
    additional_loras: additionalLoras,
    lora_multipliers: phaseConfig?.phases?.flatMap((phase) =>
      (phase.loras || []).map((lora) => ({
        url: lora.url,
        multiplier: Number(lora.multiplier) || 0,
      })),
    ) ?? [],
    model_switch_phase: phaseConfig?.model_switch_phase ?? 1,
    num_inference_steps: numInferenceSteps,
    parsed_resolution_wh: finalResolution,
    num_frames: Math.min(input.num_frames ?? 49, 81),
    ...(input.frame_overlap_from_previous !== undefined
      ? { frame_overlap_from_previous: input.frame_overlap_from_previous }
      : {}),
    ...(segmentLayout
      ? {
        stitched_start_frame: segmentLayout.stitchedStartFrame,
        guidance_start_frame: segmentLayout.guidanceStartFrame,
      }
      : {
        ...(origParams?.stitched_start_frame !== undefined
          ? { stitched_start_frame: origParams.stitched_start_frame }
          : {}),
        ...(origParams?.guidance_start_frame !== undefined
          ? { guidance_start_frame: origParams.guidance_start_frame }
          : {}),
      }),
    amount_of_motion: input.amount_of_motion ?? 0.5,
    orchestrator_details: orchestratorDetails,
    parent_generation_id: parentGenerationId,
    ...(childGenerationId ? { child_generation_id: childGenerationId } : {}),
    input_image_paths_resolved: inputImages,
    after_first_post_generation_saturation: 1,
    after_first_post_generation_brightness: 0,
    motion_mode: input.motion_mode ?? "basic",
    ...(input.enhanced_prompt ? { enhanced_prompt: input.enhanced_prompt } : {}),
    ...(input.continuation_config ? { continuation_config: input.continuation_config } : {}),
    ...(input.travel_guidance ? { travel_guidance: input.travel_guidance } : {}),
    ...(input.start_image_generation_id ? { start_image_generation_id: input.start_image_generation_id } : {}),
    ...(input.end_image_generation_id ? { end_image_generation_id: input.end_image_generation_id } : {}),
    ...(input.pair_shot_generation_id ? { pair_shot_generation_id: input.pair_shot_generation_id } : {}),
    ...(input.generation_name ? { generation_name: input.generation_name } : {}),
    make_primary_variant: input.make_primary_variant ?? true,
    ...composedPayload,
    individual_segment_params: {
      input_image_paths_resolved: inputImages,
      start_image_url: input.start_image_url,
      ...(input.end_image_url ? { end_image_url: input.end_image_url } : {}),
      base_prompt: input.base_prompt ?? "",
      negative_prompt: input.negative_prompt ?? "",
      num_frames: Math.min(input.num_frames ?? 49, 81),
      seed_to_use: finalSeed,
      random_seed: input.random_seed ?? false,
      amount_of_motion: input.amount_of_motion ?? 0.5,
      motion_mode: input.motion_mode ?? "basic",
      advanced_mode: input.advanced_mode ?? false,
      ...(input.frame_overlap_from_previous !== undefined
        ? { frame_overlap_from_previous: input.frame_overlap_from_previous }
        : {}),
      additional_loras: additionalLoras,
      after_first_post_generation_saturation: 1,
      after_first_post_generation_brightness: 0,
      ...(input.phase_config ? { phase_config: input.phase_config } : {}),
      ...(input.continuation_config ? { continuation_config: input.continuation_config } : {}),
      ...(input.start_image_generation_id ? { start_image_generation_id: input.start_image_generation_id } : {}),
      ...(input.end_image_generation_id ? { end_image_generation_id: input.end_image_generation_id } : {}),
      ...(input.pair_shot_generation_id ? { pair_shot_generation_id: input.pair_shot_generation_id } : {}),
      ...(input.start_image_variant_id ? { start_image_variant_id: input.start_image_variant_id } : {}),
      ...(input.end_image_variant_id ? { end_image_variant_id: input.end_image_variant_id } : {}),
      ...(input.enhanced_prompt ? { enhanced_prompt: input.enhanced_prompt } : {}),
      ...(input.selected_phase_preset_id ? { selected_phase_preset_id: input.selected_phase_preset_id } : {}),
    },
  };
}

function calculateStitchedStart(
  segmentFramesExpanded: number[],
  frameOverlapExpanded: number[],
  segmentIndex: number,
): number {
  let totalStitchedFrames = 0;
  const segmentStitchedOffsets: number[] = [];

  for (let idx = 0; idx < segmentFramesExpanded.length; idx += 1) {
    const segmentTotalFrames = segmentFramesExpanded[idx];
    if (idx === 0) {
      segmentStitchedOffsets.push(0);
      totalStitchedFrames = segmentTotalFrames;
      continue;
    }

    const overlap = idx - 1 < frameOverlapExpanded.length ? frameOverlapExpanded[idx - 1] : 0;
    const segmentStart = totalStitchedFrames - overlap;
    segmentStitchedOffsets.push(segmentStart);
    totalStitchedFrames = segmentStart + segmentTotalFrames;
  }

  return segmentStitchedOffsets[segmentIndex] ?? 0;
}

/**
 * Query sibling segments' completed tasks to reconstruct the pipeline layout.
 * Returns segment_frames_expanded and frame_overlap_expanded so the worker
 * can compute stitched positions for travel guidance slicing.
 *
 * Falls back gracefully: if siblings can't be queried or segment_index is 0,
 * returns undefined (no layout needed).
 */
async function resolveSegmentLayout(
  context: ResolverContext,
  parentGenerationId: string,
  segmentIndex: number,
  currentNumFrames: number,
): Promise<SegmentLayout | undefined> {
  if (segmentIndex === 0) return undefined;

  // Find the most recent completed task for each sibling segment
  const { data: siblingTasks } = await context.supabaseAdmin
    .from("tasks")
    .select("params")
    .eq("params->>parent_generation_id", parentGenerationId)
    .eq("task_type", "individual_travel_segment")
    .in("status", ["Complete", "In Progress"])
    .order("created_at", { ascending: false });

  if (!siblingTasks || siblingTasks.length === 0) return undefined;

  // Build a map of segment_index -> num_frames from the most recent task per segment
  const framesBySegment = new Map<number, number>();
  const overlapBySegment = new Map<number, number>();
  for (const task of siblingTasks) {
    const params = task.params as Record<string, unknown>;
    const idx = typeof params.segment_index === "number" ? params.segment_index : -1;
    if (idx < 0 || framesBySegment.has(idx)) continue; // keep most recent (first in desc order)
    framesBySegment.set(idx, typeof params.num_frames === "number" ? params.num_frames : 49);
    overlapBySegment.set(idx, typeof params.frame_overlap_from_previous === "number" ? params.frame_overlap_from_previous : 0);
  }

  // Include current segment
  framesBySegment.set(segmentIndex, currentNumFrames);

  // Build arrays up to at least segmentIndex
  const maxIdx = Math.max(segmentIndex, ...framesBySegment.keys());
  const segmentFramesExpanded: number[] = [];
  const frameOverlapExpanded: number[] = [];
  for (let i = 0; i <= maxIdx; i++) {
    segmentFramesExpanded.push(framesBySegment.get(i) ?? 49);
    if (i > 0) {
      frameOverlapExpanded.push(overlapBySegment.get(i) ?? 0);
    }
  }

  const guidanceStartFrame = segmentFramesExpanded
    .slice(0, segmentIndex)
    .reduce((sum, frames) => sum + frames, 0);
  const stitchedStartFrame = calculateStitchedStart(
    segmentFramesExpanded,
    frameOverlapExpanded,
    segmentIndex,
  );

  return {
    segmentFramesExpanded,
    frameOverlapExpanded,
    stitchedStartFrame,
    guidanceStartFrame,
  };
}

/**
 * Worker-created segment tasks (from travel_orchestrator) include
 * orchestrator_task_id_ref and a fully-built payload. Pass through as-is
 * to preserve pipeline linkage fields the stitch task needs.
 */
function isWorkerCreatedSegment(input: Record<string, unknown>): boolean {
  return typeof input.orchestrator_task_id_ref === "string";
}

export const individualTravelSegmentResolver: TaskFamilyResolver = async (
  request,
  context,
): Promise<ResolverResult> => {
  const rawInput = request.input as Record<string, unknown>;

  if (isWorkerCreatedSegment(rawInput)) {
    // Worker-created segment: pass through the full payload as-is
    return {
      tasks: [
        buildQueuedTask(context.projectId, "individual_travel_segment", rawInput),
      ],
    };
  }

  // Frontend-created segment: full validation and param resolution
  const input = rawInput as unknown as IndividualTravelSegmentInput;
  validateInput(input);

  const { parentGenerationId, childGenerationId } = await resolveSegmentGenerationRoute(context, input);
  const finalResolution = resolveFinalResolution(input, context.aspectRatio);
  const segmentLayout = await resolveSegmentLayout(
    context,
    parentGenerationId,
    input.segment_index,
    Math.min(input.num_frames ?? 49, 81),
  );

  return {
    tasks: [
      buildQueuedTask(
        context.projectId,
        "individual_travel_segment",
        buildIndividualTravelSegmentParams(input, finalResolution, parentGenerationId, childGenerationId, context.projectId, segmentLayout),
      ),
    ],
  };
};
