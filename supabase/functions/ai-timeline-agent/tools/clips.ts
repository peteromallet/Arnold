import type { AssetRegistry, TimelineConfig } from "../../../../src/tools/video-editor/index.ts";
import type { SelectedClipPayload, SupabaseAdmin, TimelineState } from "../types.ts";

function asTrimmedString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function resolveClipGenerationIds(
  clips: Array<Pick<SelectedClipPayload, "clip_id" | "generation_id">>,
  registry: AssetRegistry,
  config: TimelineConfig,
): string[] {
  const generationIds = clips.flatMap(({ clip_id, generation_id }) => {
    const assetKey = config.clips.find((clip) => clip.id === clip_id)?.asset;
    const fallbackGenerationId = typeof generation_id === "string" && generation_id.trim()
      ? generation_id.trim()
      : null;
    const generationId = (assetKey ? registry.assets[assetKey]?.generationId : null) ?? fallbackGenerationId;
    return typeof generationId === "string" && generationId ? [generationId] : [];
  });
  return Array.from(new Set(generationIds));
}

export async function findShotForGenerations(
  supabaseAdmin: SupabaseAdmin,
  generationIds: string[],
): Promise<string | null> {
  const uniqueGenerationIds = Array.from(new Set(generationIds));
  if (!uniqueGenerationIds.length) return null;
  const { data, error } = await supabaseAdmin
    .from("shot_generations")
    .select("shot_id, generation_id")
    .in("generation_id", uniqueGenerationIds);
  if (error) throw new Error(`Failed to load shot generations: ${error.message}`);

  const shotsByGeneration = new Map<string, Set<string>>();
  for (const row of Array.isArray(data) ? data : []) {
    const shotId = typeof row?.shot_id === "string" ? row.shot_id : null;
    const generationId = typeof row?.generation_id === "string" ? row.generation_id : null;
    if (!shotId || !generationId) continue;
    const shotIds = shotsByGeneration.get(generationId) ?? new Set<string>();
    shotIds.add(shotId);
    shotsByGeneration.set(generationId, shotIds);
  }
  if (shotsByGeneration.size !== uniqueGenerationIds.length) return null;

  let sharedShotIds: Set<string> | null = null;
  for (const shotIds of shotsByGeneration.values()) {
    sharedShotIds = sharedShotIds
      ? new Set(Array.from(sharedShotIds).filter((shotId) => shotIds.has(shotId)))
      : new Set(shotIds);
  }
  return sharedShotIds?.size ? Array.from(sharedShotIds)[0] : null;
}

export type SelectedClipShotResolution = {
  shotId: string | null;
  source: "explicit" | "pinned" | "generation" | null;
};

function resolveExplicitShotId(
  selectedClips: SelectedClipPayload[] | undefined,
): SelectedClipShotResolution & { hasConflict: boolean } {
  const shotIds = Array.from(new Set(
    (selectedClips ?? [])
      .map((clip) => asTrimmedString(clip.shot_id))
      .filter((shotId): shotId is string => shotId !== null),
  ));

  if (shotIds.length === 0) {
    return { shotId: null, source: null, hasConflict: false };
  }

  if (shotIds.length > 1) {
    return { shotId: null, source: null, hasConflict: true };
  }

  return {
    shotId: shotIds[0],
    source: "explicit",
    hasConflict: false,
  };
}

function resolvePinnedShotId(
  selectedClips: SelectedClipPayload[] | undefined,
  config: TimelineConfig,
): SelectedClipShotResolution & { hasConflict: boolean } {
  const timelineClipIds = (selectedClips ?? [])
    .map((clip) => asTrimmedString(clip.clip_id))
    .filter((clipId): clipId is string => clipId !== null && !clipId.startsWith("gallery-"));

  if (timelineClipIds.length === 0) {
    return { shotId: null, source: null, hasConflict: false };
  }

  const pinnedGroups = config.pinnedShotGroups ?? [];
  const shotIds = timelineClipIds.map((clipId) => {
    const group = pinnedGroups.find((candidate) => candidate.clipIds.includes(clipId));
    return group ? asTrimmedString(group.shotId) : null;
  });

  if (shotIds.every((shotId) => shotId === null)) {
    return { shotId: null, source: null, hasConflict: false };
  }

  if (shotIds.some((shotId) => shotId === null)) {
    return { shotId: null, source: null, hasConflict: true };
  }

  const sharedShotIds = Array.from(new Set(
    shotIds.filter((shotId): shotId is string => shotId !== null),
  ));

  if (sharedShotIds.length > 1) {
    return { shotId: null, source: null, hasConflict: true };
  }

  return {
    shotId: sharedShotIds[0],
    source: "pinned",
    hasConflict: false,
  };
}

export async function resolveSelectedClipShot(
  supabaseAdmin: SupabaseAdmin,
  timelineState: Pick<TimelineState, "config" | "registry">,
  selectedClips: SelectedClipPayload[] | undefined,
  options?: { additionalGenerationIds?: string[] },
): Promise<SelectedClipShotResolution> {
  const explicitShot = resolveExplicitShotId(selectedClips);
  if (explicitShot.shotId) {
    return explicitShot;
  }
  if (explicitShot.hasConflict) {
    return { shotId: null, source: null };
  }

  const pinnedShot = resolvePinnedShotId(selectedClips, timelineState.config);
  if (pinnedShot.shotId) {
    return pinnedShot;
  }
  if (pinnedShot.hasConflict) {
    return { shotId: null, source: null };
  }

  const additionalGenerationIds = (options?.additionalGenerationIds ?? [])
    .map((generationId) => asTrimmedString(generationId))
    .filter((generationId): generationId is string => generationId !== null);
  const generationIds = Array.from(new Set([
    ...resolveClipGenerationIds(selectedClips ?? [], timelineState.registry, timelineState.config),
    ...additionalGenerationIds,
  ]));

  if (!generationIds.length) {
    return { shotId: null, source: null };
  }

  const shotId = await findShotForGenerations(supabaseAdmin, generationIds);
  return {
    shotId,
    source: shotId ? "generation" : null,
  };
}

export async function createShotWithGenerations(
  supabaseAdmin: SupabaseAdmin,
  args: { projectId: string; shotName: string; generationIds: string[]; position: number },
): Promise<string> {
  const { data, error } = await supabaseAdmin.rpc("insert_shot_at_position", {
    p_project_id: args.projectId,
    p_shot_name: args.shotName,
    p_position: args.position,
  }).maybeSingle();
  const result = data as { shot_id?: unknown; success?: unknown } | null;
  if (error || result?.success !== true || typeof result.shot_id !== "string") {
    throw new Error(`Failed to create shot: ${error?.message ?? "invalid response"}`);
  }

  const shotId = result.shot_id;
  const rows = Array.from(new Set(args.generationIds)).map((generationId) => ({ shot_id: shotId, generation_id: generationId }));
  if (rows.length) {
    const { error: insertError } = await supabaseAdmin.from("shot_generations").insert(rows);
    if (insertError) throw new Error(`Failed to attach generations to shot: ${insertError.message}`);
  }
  return shotId;
}
