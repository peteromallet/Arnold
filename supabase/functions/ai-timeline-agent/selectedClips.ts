import { isRecord } from "./llm/messages.ts";
import { getPairTimelineClipDuration } from "../../../src/tools/video-editor/index.ts";
import type { TimelinePlacement } from "../create-task/resolvers/shared/lineage.ts";
import type {
  ResolvedSelectionContext,
  SelectedClipPayload,
  SupabaseAdmin,
  TimelineState,
} from "./types.ts";

function firstPromptString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return undefined;
}

function extractGenerationPrompt(params: unknown): string | undefined {
  if (!isRecord(params)) {
    return undefined;
  }

  const originalParams = isRecord(params.originalParams) ? params.originalParams : undefined;
  const orchestratorDetails = isRecord(originalParams?.orchestrator_details)
    ? originalParams.orchestrator_details
    : undefined;
  const metadataBlock = isRecord(params.metadata) ? params.metadata : undefined;

  return firstPromptString(
    orchestratorDetails?.prompt,
    params.prompt,
    metadataBlock?.prompt,
  );
}

function normalizeTimelinePlacement(value: unknown): TimelinePlacement | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const timelineId = typeof value.timeline_id === "string" && value.timeline_id.trim()
    ? value.timeline_id.trim()
    : undefined;
  const sourceClipId = typeof value.source_clip_id === "string" && value.source_clip_id.trim()
    ? value.source_clip_id.trim()
    : undefined;
  const targetTrack = typeof value.target_track === "string" && value.target_track.trim()
    ? value.target_track.trim()
    : undefined;
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

export function resolveTimelinePlacement(
  clip: SelectedClipPayload,
  timelineState: TimelineState,
  timelineId: string,
): TimelinePlacement | null {
  const [resolvedContext] = resolveSelectionContext([clip], timelineState, timelineId);
  if (!resolvedContext?.is_on_timeline) {
    return null;
  }

  return {
    timeline_id: resolvedContext.timeline_id,
    source_clip_id: resolvedContext.clip_id,
    target_track: resolvedContext.track_id,
    insertion_time: resolvedContext.at + resolvedContext.duration,
    intent: "after_source",
  };
}

export function resolveSelectionContext(
  selectedClips: SelectedClipPayload[],
  timelineState: TimelineState,
  timelineId: string,
): ResolvedSelectionContext[] {
  const liveClipsById = new Map(
    timelineState.config.clips.map((clip) => [clip.id, clip] as const),
  );

  return selectedClips.map((clip) => {
    const clipId = clip.clip_id.trim();
    const liveClip = clipId && !clipId.startsWith("gallery-")
      ? liveClipsById.get(clipId)
      : undefined;

    if (liveClip) {
      return {
        timeline_id: timelineId,
        clip_id: clipId,
        ...(clip.generation_id ? { generation_id: clip.generation_id } : {}),
        ...(clip.variant_id ? { variant_id: clip.variant_id } : {}),
        track_id: liveClip.track,
        at: liveClip.at,
        duration: getPairTimelineClipDuration(liveClip, timelineState.registry),
        ...(clip.shot_id ? { shot_id: clip.shot_id } : {}),
        ...(clip.shot_name ? { shot_name: clip.shot_name } : {}),
        source: "timeline" as const,
        is_on_timeline: true,
      };
    }

    return {
      timeline_id: timelineId,
      clip_id: clipId,
      ...(clip.generation_id ? { generation_id: clip.generation_id } : {}),
      ...(clip.variant_id ? { variant_id: clip.variant_id } : {}),
      track_id: "",
      at: 0,
      duration: 0,
      ...(clip.shot_id ? { shot_id: clip.shot_id } : {}),
      ...(clip.shot_name ? { shot_name: clip.shot_name } : {}),
      source: "gallery" as const,
      is_on_timeline: false,
    };
  });
}

export function normalizeSelectedClips(value: unknown): SelectedClipPayload[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    if (!isRecord(item)) {
      return [];
    }

    const clipId = typeof item.clip_id === "string" ? item.clip_id.trim() : "";
    const generationId = typeof item.generation_id === "string" ? item.generation_id.trim() : "";
    const variantId = typeof item.variant_id === "string" && item.variant_id.trim()
      ? item.variant_id.trim()
      : undefined;
    const prompt = typeof item.prompt === "string" && item.prompt.trim() ? item.prompt.trim() : undefined;
    const shotId = typeof item.shot_id === "string" && item.shot_id.trim() ? item.shot_id.trim() : undefined;
    const shotName = typeof item.shot_name === "string" && item.shot_name.trim() ? item.shot_name.trim() : undefined;
    const trackId = typeof item.track_id === "string" && item.track_id.trim() ? item.track_id.trim() : undefined;
    const at = typeof item.at === "number" && Number.isFinite(item.at) ? item.at : undefined;
    const duration = typeof item.duration === "number" && Number.isFinite(item.duration) && item.duration >= 0
      ? item.duration
      : undefined;
    const isTimelineBacked = typeof item.is_timeline_backed === "boolean" ? item.is_timeline_backed : undefined;
    const timelinePlacement = normalizeTimelinePlacement(item.timeline_placement);
    const shotSelectionClipCount = typeof item.shot_selection_clip_count === "number"
      && Number.isFinite(item.shot_selection_clip_count)
      && item.shot_selection_clip_count > 0
      ? item.shot_selection_clip_count
      : undefined;
    const normalizedClipId = clipId || (generationId ? `gallery-${generationId}` : "");
    const url = typeof item.url === "string" ? item.url.trim() : "";
    const mediaType = item.media_type;

    if (!normalizedClipId || !url || (mediaType !== "image" && mediaType !== "video")) {
      return [];
    }

    return [{
      clip_id: normalizedClipId,
      url,
      media_type: mediaType,
      ...(generationId ? { generation_id: generationId } : {}),
      ...(variantId ? { variant_id: variantId } : {}),
      ...(prompt ? { prompt } : {}),
      ...(shotId ? { shot_id: shotId } : {}),
      ...(shotName ? { shot_name: shotName } : {}),
      ...(trackId ? { track_id: trackId } : {}),
      ...(typeof at === "number" ? { at } : {}),
      ...(typeof duration === "number" ? { duration } : {}),
      ...(typeof isTimelineBacked === "boolean" ? { is_timeline_backed: isTimelineBacked } : {}),
      ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
      ...(shotSelectionClipCount ? { shot_selection_clip_count: shotSelectionClipCount } : {}),
    }];
  });
}

export async function enrichClipsWithPrompts(
  supabaseAdmin: SupabaseAdmin,
  clips: SelectedClipPayload[],
): Promise<SelectedClipPayload[]> {
  if (!clips.length) {
    return clips;
  }

  const generationIds = Array.from(new Set(
    clips.flatMap((clip) => (
      typeof clip.generation_id === "string" && clip.generation_id.trim()
        ? [clip.generation_id.trim()]
        : []
    )),
  ));

  if (!generationIds.length) {
    return clips;
  }

  const { data, error } = await supabaseAdmin
    .from("generations")
    .select("id, params")
    .in("id", generationIds);

  if (error) {
    throw new Error(`Failed to load generation prompts: ${error.message}`);
  }

  const promptsByGenerationId = new Map<string, string>();
  for (const row of Array.isArray(data) ? data : []) {
    if (!isRecord(row)) {
      continue;
    }

    const generationId = typeof row.id === "string" ? row.id.trim() : "";
    const prompt = extractGenerationPrompt(row.params);
    if (generationId && prompt) {
      promptsByGenerationId.set(generationId, prompt);
    }
  }

  return clips.map((clip) => {
    const prompt = clip.prompt ?? (
      clip.generation_id
        ? promptsByGenerationId.get(clip.generation_id)
        : undefined
    );

    return prompt ? { ...clip, prompt } : clip;
  });
}
