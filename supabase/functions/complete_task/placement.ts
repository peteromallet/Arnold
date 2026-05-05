import { getPairTimelineClipDuration } from "../../../src/tools/video-editor/lib/timeline-domain.ts";
import type {
  AssetRegistryEntry,
  TimelineClip,
  TimelineConfig,
} from "../../../src/tools/video-editor/types/index.ts";
import {
  loadTimelineState,
  prepareTimelineConfigForPersistence,
  saveTimelineConfigVersioned,
} from "../ai-timeline-agent/db.ts";
import { addMediaClip } from "../ai-timeline-agent/tools/timeline.ts";
import type { PlacementIntent, SupabaseAdmin as TimelineSupabaseAdmin } from "../ai-timeline-agent/types.ts";
import type { CompletionFollowUpIssue } from "./completionHelpers.ts";
import type { CompletionAssetRef } from "./generation.ts";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asTrimmedString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function asNonNegativeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function inferTrackIds(config: TimelineConfig): Set<string> {
  if (Array.isArray(config.tracks) && config.tracks.length > 0) {
    return new Set(
      config.tracks
        .map((track) => (typeof track.id === "string" ? track.id : null))
        .filter((trackId): trackId is string => Boolean(trackId && trackId.trim().length > 0)),
    );
  }

  return new Set(
    config.clips
      .map((clip) => (typeof clip.track === "string" ? clip.track : null))
      .filter((trackId): trackId is string => Boolean(trackId && trackId.trim().length > 0)),
  );
}

function trackExists(config: TimelineConfig, trackId: string): boolean {
  return inferTrackIds(config).has(trackId);
}

function findClip(config: TimelineConfig, clipId: string): TimelineClip | null {
  return config.clips.find((clip) => clip.id === clipId) ?? null;
}

function normalizeMediaType(mediaType: string): "image" | "video" | null {
  if (mediaType === "image" || mediaType === "video") {
    return mediaType;
  }
  return null;
}

function inferAssetMimeType(completionAssetRef: CompletionAssetRef): string {
  if (completionAssetRef.media_type === "video") {
    return "video/mp4";
  }

  const lowerLocation = completionAssetRef.location.toLowerCase();
  if (lowerLocation.endsWith(".jpg") || lowerLocation.endsWith(".jpeg")) return "image/jpeg";
  if (lowerLocation.endsWith(".webp")) return "image/webp";
  if (lowerLocation.endsWith(".gif")) return "image/gif";
  return "image/png";
}

function buildAssetEntry(completionAssetRef: CompletionAssetRef): AssetRegistryEntry {
  return {
    file: completionAssetRef.location,
    type: inferAssetMimeType(completionAssetRef),
    generationId: completionAssetRef.generation_id,
    ...(completionAssetRef.variant_id ? { variantId: completionAssetRef.variant_id } : {}),
    ...(completionAssetRef.thumbnail_url && completionAssetRef.thumbnail_url !== completionAssetRef.location
      ? { thumbnailUrl: completionAssetRef.thumbnail_url }
      : {}),
  };
}

function buildPlacementIssue(code: string, message: string): CompletionFollowUpIssue {
  return {
    step: "timeline_placement",
    code,
    message,
  };
}

export function extractPlacementIntent(params: unknown): PlacementIntent | null {
  if (!isRecord(params) || !isRecord(params.placement_intent)) {
    return null;
  }

  const placementIntent = params.placement_intent;
  const timelineId = asTrimmedString(placementIntent.timeline_id);
  const anchorClipId = asTrimmedString(placementIntent.anchor_clip_id);
  const preferredTrackId = asTrimmedString(placementIntent.preferred_track_id);
  const fallbackTrackId = asTrimmedString(placementIntent.fallback_track_id);
  const fallbackAt = asNonNegativeNumber(placementIntent.fallback_at);

  if (
    !timelineId
    || !anchorClipId
    || placementIntent.relation !== "after"
    || !preferredTrackId
    || !fallbackTrackId
    || fallbackAt === null
  ) {
    return null;
  }

  const anchorGenerationId = asTrimmedString(placementIntent.anchor_generation_id) ?? undefined;
  const anchorVariantId = asTrimmedString(placementIntent.anchor_variant_id) ?? undefined;

  return {
    timeline_id: timelineId,
    anchor_clip_id: anchorClipId,
    ...(anchorGenerationId ? { anchor_generation_id: anchorGenerationId } : {}),
    ...(anchorVariantId ? { anchor_variant_id: anchorVariantId } : {}),
    relation: "after",
    preferred_track_id: preferredTrackId,
    fallback_at: fallbackAt,
    fallback_track_id: fallbackTrackId,
  };
}

export type PlacementExecutionResult =
  | {
    status: "placed";
    timelineId: string;
    assetKey: string;
    clipId?: string;
    usedFallback: boolean;
    configVersion: number;
  }
  | {
    status: "skipped";
    issue: CompletionFollowUpIssue;
  };

export async function executePlacement(
  supabaseAdmin: TimelineSupabaseAdmin,
  placementIntent: PlacementIntent,
  completionAssetRef: CompletionAssetRef,
): Promise<PlacementExecutionResult> {
  const mediaType = normalizeMediaType(completionAssetRef.media_type);
  if (!mediaType) {
    return {
      status: "skipped",
      issue: buildPlacementIssue(
        "placement_media_type_unsupported",
        `Cannot place completion asset with unsupported media type: ${completionAssetRef.media_type}.`,
      ),
    };
  }

  const timelineState = await loadTimelineState(supabaseAdmin, placementIntent.timeline_id);
  const anchorClip = findClip(timelineState.config, placementIntent.anchor_clip_id);

  let targetTrackId: string;
  let targetAt: number;
  let usedFallback = false;

  if (anchorClip) {
    if (!trackExists(timelineState.config, placementIntent.preferred_track_id)) {
      return {
        status: "skipped",
        issue: buildPlacementIssue(
          "placement_preferred_track_missing",
          `Preferred track ${placementIntent.preferred_track_id} no longer exists on timeline ${placementIntent.timeline_id}.`,
        ),
      };
    }

    targetTrackId = placementIntent.preferred_track_id;
    targetAt = anchorClip.at + getPairTimelineClipDuration(anchorClip, timelineState.registry);
  } else if (trackExists(timelineState.config, placementIntent.fallback_track_id)) {
    targetTrackId = placementIntent.fallback_track_id;
    targetAt = placementIntent.fallback_at;
    usedFallback = true;
  } else {
    return {
      status: "skipped",
      issue: buildPlacementIssue(
        "placement_anchor_and_fallback_missing",
        `Skipped placement because anchor clip ${placementIntent.anchor_clip_id} was missing and fallback track ${placementIntent.fallback_track_id} no longer exists on timeline ${placementIntent.timeline_id}.`,
      ),
    };
  }

  const assetKey = `asset-${crypto.randomUUID().slice(0, 6)}`;
  const assetEntry = buildAssetEntry(completionAssetRef);

  const { error: assetRegistryError } = await supabaseAdmin
    .rpc("upsert_asset_registry_entry", {
      p_timeline_id: placementIntent.timeline_id,
      p_asset_id: assetKey,
      p_entry: assetEntry,
    })
    .maybeSingle();

  if (assetRegistryError) {
    throw new Error(`Failed to register timeline asset: ${assetRegistryError.message}`);
  }

  const nextRegistry = {
    ...timelineState.registry,
    assets: {
      ...timelineState.registry.assets,
      [assetKey]: assetEntry,
    },
  };
  const insertionResult = addMediaClip(timelineState.config, nextRegistry, {
    track: targetTrackId,
    at: targetAt,
    assetKey,
    mediaType,
  });

  if (!insertionResult.config) {
    return {
      status: "skipped",
      issue: buildPlacementIssue(
        "placement_insert_failed",
        insertionResult.result,
      ),
    };
  }

  const configToSave = prepareTimelineConfigForPersistence(insertionResult.config, nextRegistry);

  const nextVersion = await saveTimelineConfigVersioned(
    supabaseAdmin,
    placementIntent.timeline_id,
    timelineState.configVersion,
    configToSave,
  );

  if (nextVersion === null) {
    return {
      status: "skipped",
      issue: buildPlacementIssue(
        "placement_save_conflict",
        `Skipped placement because timeline ${placementIntent.timeline_id} changed before the placement could be saved.`,
      ),
    };
  }

  const placedClip = configToSave.clips.find((clip) => clip.asset === assetKey);

  return {
    status: "placed",
    timelineId: placementIntent.timeline_id,
    assetKey,
    clipId: placedClip?.id,
    usedFallback,
    configVersion: nextVersion,
  };
}
