import type {
  AssetRegistry,
  PinnedShotGroup,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from "../../../../src/tools/video-editor/types/index.ts";
import type { ToolHandler, ToolResult } from "../types.ts";
// Sprint 3 (SD-018): surgical CRUD ops moved to @banodoco/timeline-ops.
// `moveClip` and `setClipProperty` here delegate to the shared package; the
// handler-level result strings remain byte-equivalent so the LLM tool
// schema (`tool-schemas.ts`) and the parsed-command output are unchanged.
import {
  moveClip as opsMoveClip,
  setClipParams as opsSetClipParams,
  setClipProperty as opsSetClipProperty,
  setThemeOverrides as opsSetThemeOverrides,
  setTimelineTheme as opsSetTimelineTheme,
  type MutableClipProperty,
} from "@banodoco/timeline-ops";
import type { TimelineConfigT } from "@banodoco/timeline-schema";

export type TimelineToolResult = ToolResult;

type ClipProperty = "volume" | "speed" | "opacity" | "x" | "y" | "width" | "height";

const MUTABLE_CLIP_PROPERTIES: ClipProperty[] = [
  "volume",
  "speed",
  "opacity",
  "x",
  "y",
  "width",
  "height",
];

function roundSeconds(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function cloneConfig(config: TimelineConfig): TimelineConfig {
  return structuredClone(config);
}

function getAssetDuration(registry: AssetRegistry, assetId?: string): number | null {
  if (!assetId) {
    return null;
  }

  const duration = registry.assets?.[assetId]?.duration;
  return typeof duration === "number" ? duration : null;
}

function getClipSourceDuration(clip: TimelineClip, registry: AssetRegistry): number {
  if (typeof clip.hold === "number") {
    return clip.hold;
  }

  if (typeof clip.from === "number" && typeof clip.to === "number") {
    return clip.to - clip.from;
  }

  return getAssetDuration(registry, clip.asset) ?? 0;
}

function getClipTimelineDuration(clip: TimelineClip, registry: AssetRegistry): number {
  const speed = clip.speed ?? 1;
  return getClipSourceDuration(clip, registry) / speed;
}

function getShotLabel(shotId: string, shotNamesById: Record<string, string>): string {
  return shotNamesById[shotId] ?? shotId;
}

function buildShotGroupByClipId(config: TimelineConfig): Map<string, PinnedShotGroup> {
  const shotGroupByClipId = new Map<string, PinnedShotGroup>();
  for (const group of config.pinnedShotGroups ?? []) {
    for (const clipId of group.clipIds) {
      shotGroupByClipId.set(clipId, group);
    }
  }
  return shotGroupByClipId;
}

function formatClipLine(
  clip: TimelineClip,
  registry: AssetRegistry,
  shotGroupByClipId: Map<string, PinnedShotGroup>,
  shotNamesById: Record<string, string>,
): string {
  const duration = roundSeconds(getClipTimelineDuration(clip, registry));
  const parts = [
    `id=${clip.id}`,
    `track=${clip.track}`,
    `at=${roundSeconds(clip.at)}s`,
    `duration=${duration}s`,
    `type=${clip.clipType ?? "media"}`,
    `asset=${clip.asset ?? "none"}`,
  ];

  if (clip.x != null) parts.push(`x=${clip.x}`);
  if (clip.y != null) parts.push(`y=${clip.y}`);
  if (clip.width != null) parts.push(`width=${clip.width}`);
  if (clip.height != null) parts.push(`height=${clip.height}`);
  if (clip.opacity != null && clip.opacity !== 1) parts.push(`opacity=${clip.opacity}`);
  if (clip.volume != null && clip.volume !== 1) parts.push(`volume=${clip.volume}`);
  if (clip.speed != null && clip.speed !== 1) parts.push(`speed=${clip.speed}`);
  if (clip.clipType === "text" && clip.text?.content) parts.push(`text="${clip.text.content}"`);

  const shotGroup = shotGroupByClipId.get(clip.id);
  if (shotGroup) {
    parts.push(`shot=${getShotLabel(shotGroup.shotId, shotNamesById)}`);
    parts.push(`shotId=${shotGroup.shotId}`);
  }

  return parts.join(" | ");
}

function getTrackDefinitions(config: TimelineConfig): TrackDefinition[] {
  if (config.tracks?.length) {
    return config.tracks;
  }

  const inferredTrackIds = Array.from(new Set(config.clips.map((clip) => clip.track)));
  return inferredTrackIds.map((trackId) => ({
    id: trackId,
    label: trackId,
    kind: "visual",
  }));
}

function getClipIndex(config: TimelineConfig, clipId: string): number {
  return config.clips.findIndex((clip) => clip.id === clipId);
}

function describeTimeline(
  config: TimelineConfig,
  registry: AssetRegistry,
  shotNamesById: Record<string, string>,
): string {
  const tracks = getTrackDefinitions(config);
  const shotGroupByClipId = buildShotGroupByClipId(config);
  const shotGroups = config.pinnedShotGroups ?? [];
  const totalDuration = config.clips.reduce((maxDuration, clip) => {
    return Math.max(maxDuration, clip.at + getClipTimelineDuration(clip, registry));
  }, 0);

  const lines = [
    `Timeline summary: ${tracks.length} track(s), ${config.clips.length} clip(s), total duration ${roundSeconds(totalDuration)}s.`,
    "Tracks:",
    ...tracks.map((track) => `- ${track.id} (${track.kind}): ${track.label}`),
    "Clips:",
    ...config.clips.map((clip) => `- ${formatClipLine(clip, registry, shotGroupByClipId, shotNamesById)}`),
    "Shot groups:",
    ...(shotGroups.length > 0
      ? shotGroups.map((group) => (
        `- shot=${getShotLabel(group.shotId, shotNamesById)} | shotId=${group.shotId} | trackId=${group.trackId} | clipIds=${group.clipIds.join(",")} | mode=${group.mode ?? "images"}`
      ))
      : ["- none"]),
  ];

  return lines.join("\n");
}

export function viewTimeline(
  config: TimelineConfig,
  registry: AssetRegistry,
  shotNamesById: Record<string, string> = {},
): TimelineToolResult {
  return {
    result: describeTimeline(config, registry, shotNamesById),
  };
}

export function moveClip(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { clipId?: string; at?: number },
): TimelineToolResult {
  if (typeof args.clipId !== "string" || typeof args.at !== "number") {
    return { result: "move_clip requires clipId and at." };
  }

  // Delegate to @banodoco/timeline-ops moveClip. Result string format is
  // preserved byte-for-byte so the LLM-visible tool output is identical
  // pre/post extraction (Sprint 3 snapshot test enforces this).
  const opResult = opsMoveClip(config as unknown as TimelineConfigT, args.clipId, args.at);
  if (!opResult.changed && opResult.detail?.reason === "not_found") {
    return { result: `Clip ${args.clipId} was not found.` };
  }
  const previousAt = opResult.detail?.previousAt as number;
  return {
    config: opResult.config as unknown as TimelineConfig,
    result: `Moved clip ${args.clipId} from ${roundSeconds(previousAt)}s to ${roundSeconds(args.at)}s.`,
  };
}

export function splitClip(
  config: TimelineConfig,
  registry: AssetRegistry,
  args: { clipId?: string; time?: number },
): TimelineToolResult {
  if (typeof args.clipId !== "string" || typeof args.time !== "number") {
    return { result: "split_clip requires clipId and time." };
  }

  const nextConfig = cloneConfig(config);
  const clipIndex = getClipIndex(nextConfig, args.clipId);
  if (clipIndex < 0) {
    return { result: `Clip ${args.clipId} was not found.` };
  }

  const clip = nextConfig.clips[clipIndex];
  const clipEnd = clip.at + getClipTimelineDuration(clip, registry);
  if (!(args.time > clip.at && args.time < clipEnd)) {
    return { result: `Split time ${roundSeconds(args.time)}s must be inside clip ${clip.id}.` };
  }

  const splitTime = roundSeconds(args.time);
  const rightClipId = `clip-${crypto.randomUUID().slice(0, 6)}`;
  let leftClip: TimelineClip;
  let rightClip: TimelineClip;

  if (typeof clip.hold === "number") {
    const elapsed = roundSeconds(splitTime - clip.at);
    const remaining = roundSeconds(clip.hold - elapsed);
    leftClip = {
      ...clip,
      hold: elapsed,
    };
    rightClip = {
      ...clip,
      id: rightClipId,
      at: splitTime,
      hold: remaining,
    };
  } else {
    const speed = clip.speed ?? 1;
    const splitSource = roundSeconds((clip.from ?? 0) + (splitTime - clip.at) * speed);
    leftClip = {
      ...clip,
      to: splitSource,
    };
    rightClip = {
      ...clip,
      id: rightClipId,
      at: splitTime,
      from: splitSource,
    };
  }

  nextConfig.clips.splice(clipIndex, 1, leftClip, rightClip);

  return {
    config: nextConfig,
    result: `Split clip ${clip.id} at ${splitTime}s into ${clip.id} and ${rightClipId}.`,
  };
}

export function trimClip(
  config: TimelineConfig,
  registry: AssetRegistry,
  args: { clipId?: string; from?: number; to?: number; duration?: number },
): TimelineToolResult {
  if (typeof args.clipId !== "string") {
    return { result: "trim_clip requires clipId." };
  }

  const nextConfig = cloneConfig(config);
  const clipIndex = getClipIndex(nextConfig, args.clipId);
  if (clipIndex < 0) {
    return { result: `Clip ${args.clipId} was not found.` };
  }

  const clip = nextConfig.clips[clipIndex];
  const assetDuration = getAssetDuration(registry, clip.asset);
  const currentFrom = typeof clip.from === "number" ? clip.from : 0;
  const currentTo = typeof clip.to === "number"
    ? clip.to
    : typeof clip.hold === "number"
      ? clip.hold
      : assetDuration ?? 0;

  let nextFrom = typeof args.from === "number" ? args.from : currentFrom;
  let nextTo = typeof args.to === "number" ? args.to : currentTo;

  if (typeof args.duration === "number") {
    if (args.duration <= 0) {
      return { result: "trim_clip duration must be greater than 0." };
    }

    if (typeof args.from === "number") {
      nextTo = args.from + args.duration;
    } else if (typeof args.to === "number") {
      nextFrom = args.to - args.duration;
    } else if (typeof clip.hold === "number" && !clip.asset) {
      clip.hold = roundSeconds(args.duration);
      return {
        config: nextConfig,
        result: `Updated hold duration for clip ${clip.id} to ${roundSeconds(args.duration)}s.`,
      };
    } else {
      nextTo = nextFrom + args.duration;
    }
  }

  if (nextFrom < 0 || nextTo <= nextFrom) {
    return { result: `Invalid trim range for clip ${clip.id}.` };
  }

  if (assetDuration !== null && nextTo > assetDuration + 0.0001) {
    return {
      result: `Trim range for clip ${clip.id} exceeds asset duration ${roundSeconds(assetDuration)}s.`,
    };
  }

  clip.from = roundSeconds(nextFrom);
  clip.to = roundSeconds(nextTo);
  delete clip.hold;

  return {
    config: nextConfig,
    result: `Trimmed clip ${clip.id} to source range ${roundSeconds(nextFrom)}s-${roundSeconds(nextTo)}s.`,
  };
}

export function setClipProperty(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { clipId?: string; property?: string; value?: unknown },
): TimelineToolResult {
  if (
    typeof args.clipId !== "string"
    || typeof args.property !== "string"
    || typeof args.value !== "number"
  ) {
    return { result: "set_clip_property requires clipId, property, and numeric value." };
  }

  // Delegate to @banodoco/timeline-ops setClipProperty. The package owns
  // the allow-list (mirrors MUTABLE_CLIP_PROPERTIES below for type
  // narrowing). Result strings preserved byte-for-byte.
  const opResult = opsSetClipProperty(
    config as unknown as TimelineConfigT,
    args.clipId,
    args.property,
    args.value,
  );
  if (!opResult.changed) {
    if (opResult.detail?.reason === "property_not_allowed") {
      return {
        result: `Property ${args.property} is not allowed. Use one of ${MUTABLE_CLIP_PROPERTIES.join(", ")}.`,
      };
    }
    if (opResult.detail?.reason === "not_found") {
      return { result: `Clip ${args.clipId} was not found.` };
    }
    if (opResult.detail?.reason === "invalid_value") {
      return { result: "set_clip_property requires clipId, property, and numeric value." };
    }
  }
  const previousValue = opResult.detail?.previousValue as number | undefined;
  // Touch MutableClipProperty so the type alias isn't dead code.
  const _typedProp: MutableClipProperty = args.property as MutableClipProperty;
  void _typedProp;
  return {
    config: opResult.config as unknown as TimelineConfig,
    result: `Set ${args.property} on clip ${args.clipId} from ${previousValue ?? "unset"} to ${args.value}.`,
  };
}

export function deleteClip(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { clipId?: string },
): TimelineToolResult {
  if (typeof args.clipId !== "string") {
    return { result: "delete_clip requires clipId." };
  }

  const clip = config.clips.find((item) => item.id === args.clipId);
  if (!clip) {
    return { result: `Clip ${args.clipId} was not found.` };
  }

  const nextConfig = cloneConfig(config);
  nextConfig.clips = nextConfig.clips.filter((item) => item.id !== args.clipId);

  return {
    config: nextConfig,
    result: `Deleted clip ${clip.id} on track ${clip.track}.`,
  };
}

export function addTextClip(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { track?: string; at?: number; duration?: number; text?: string },
): TimelineToolResult {
  if (
    typeof args.track !== "string"
    || typeof args.at !== "number"
    || typeof args.duration !== "number"
    || typeof args.text !== "string"
  ) {
    return { result: "add_text_clip requires track, at, duration, and text." };
  }

  if (args.duration <= 0) {
    return { result: "add_text_clip duration must be greater than 0." };
  }

  const tracks = getTrackDefinitions(config);
  if (tracks.length > 0 && !tracks.some((track) => track.id === args.track)) {
    return { result: `Track ${args.track} does not exist.` };
  }

  const nextConfig = cloneConfig(config);
  const clipId = `clip-${crypto.randomUUID().slice(0, 6)}`;
  nextConfig.clips.push({
    id: clipId,
    at: roundSeconds(args.at),
    track: args.track,
    clipType: "text",
    hold: roundSeconds(args.duration),
    text: {
      content: args.text,
    },
  });

  return {
    config: nextConfig,
    result: `Added text clip ${clipId} on track ${args.track} at ${roundSeconds(args.at)}s for ${roundSeconds(args.duration)}s.`,
  };
}

export function addMediaClip(
  config: TimelineConfig,
  registry: AssetRegistry,
  args: { track?: string; at?: number; assetKey?: string; mediaType?: "image" | "video" },
): TimelineToolResult {
  if (
    typeof args.track !== "string"
    || typeof args.at !== "number"
    || typeof args.assetKey !== "string"
    || (args.mediaType !== "image" && args.mediaType !== "video")
  ) {
    return { result: "add_media_clip requires track, at, assetKey, and mediaType." };
  }

  const tracks = getTrackDefinitions(config);
  if (tracks.length > 0 && !tracks.some((track) => track.id === args.track)) {
    return { result: `Track ${args.track} does not exist.` };
  }

  const nextConfig = cloneConfig(config);
  const clipId = `clip-${crypto.randomUUID().slice(0, 6)}`;
  const clip = args.mediaType === "video"
    ? {
      id: clipId,
      at: roundSeconds(args.at),
      track: args.track,
      asset: args.assetKey,
      clipType: "media" as const,
      from: 0,
      to: roundSeconds(getAssetDuration(registry, args.assetKey) ?? 5),
      speed: 1,
      volume: 1,
      opacity: 1,
    }
    : {
      id: clipId,
      at: roundSeconds(args.at),
      track: args.track,
      asset: args.assetKey,
      clipType: "hold" as const,
      hold: 5,
      opacity: 1,
    };
  nextConfig.clips.push(clip);

  return {
    config: nextConfig,
    result: `Added media clip ${clipId} on track ${args.track} at ${roundSeconds(args.at)}s using asset ${args.assetKey}.`,
  };
}

export function swapClipAsset(
  config: TimelineConfig,
  registry: AssetRegistry,
  args: { clipId?: string; assetKey?: string; mediaType?: "image" | "video" },
): TimelineToolResult {
  if (
    typeof args.clipId !== "string"
    || typeof args.assetKey !== "string"
    || (args.mediaType !== "image" && args.mediaType !== "video")
  ) {
    return { result: "swap_clip_asset requires clipId, assetKey, and mediaType." };
  }

  const nextConfig = cloneConfig(config);
  const clipIndex = getClipIndex(nextConfig, args.clipId);
  if (clipIndex < 0) {
    return { result: `Clip ${args.clipId} was not found.` };
  }

  const clip = nextConfig.clips[clipIndex];
  if (clip.clipType === "text" || clip.clipType === "effect-layer") {
    return { result: `Clip ${clip.id} cannot swap media assets.` };
  }

  const currentMediaType = clip.clipType === "hold" ? "image" : "video";
  clip.asset = args.assetKey;

  if (currentMediaType === args.mediaType) {
    return {
      config: nextConfig,
      result: `Swapped asset on clip ${clip.id} to ${args.assetKey}.`,
    };
  }

  if (args.mediaType === "video") {
    clip.clipType = "media";
    clip.from = 0;
    clip.to = roundSeconds(getAssetDuration(registry, args.assetKey) ?? 5);
    clip.speed = 1;
    clip.volume = 1;
    delete clip.hold;
  } else {
    clip.clipType = "hold";
    clip.hold = 5;
    delete clip.from;
    delete clip.to;
    delete clip.speed;
    delete clip.volume;
  }

  return {
    config: nextConfig,
    result: `Swapped clip ${clip.id} to ${args.mediaType} asset ${args.assetKey}.`,
  };
}

export function queryTimeline(config: TimelineConfig, registry: AssetRegistry): TimelineToolResult {
  const nextConfig = cloneConfig(config);
  const trackDefinitions = getTrackDefinitions(nextConfig);
  const clipsByTrack = new Map<string, TimelineClip[]>();
  let totalDuration = 0;
  let longest: { id: string; duration: number } | null = null;
  let shortest: { id: string; duration: number } | null = null;
  let gapCount = 0;
  let overlapCount = 0;

  for (const track of trackDefinitions) {
    clipsByTrack.set(track.id, []);
  }

  for (const clip of nextConfig.clips) {
    const duration = roundSeconds(getClipTimelineDuration(clip, registry));
    totalDuration = Math.max(totalDuration, roundSeconds(clip.at + duration));

    if (!longest || duration > longest.duration) {
      longest = { id: clip.id, duration };
    }
    if (!shortest || duration < shortest.duration) {
      shortest = { id: clip.id, duration };
    }

    const trackClips = clipsByTrack.get(clip.track) ?? [];
    trackClips.push(clip);
    clipsByTrack.set(clip.track, trackClips);
  }

  for (const trackClips of clipsByTrack.values()) {
    const sortedClips = [...trackClips].sort((left, right) => left.at - right.at);
    for (let index = 1; index < sortedClips.length; index += 1) {
      const previousClip = sortedClips[index - 1];
      const currentClip = sortedClips[index];
      const previousEnd = previousClip.at + getClipTimelineDuration(previousClip, registry);

      if (currentClip.at - previousEnd > 0.01) {
        gapCount += 1;
      }

      if (previousEnd - currentClip.at > 0.01) {
        overlapCount += 1;
      }
    }
  }

  const trackSummary = trackDefinitions.length > 0
    ? trackDefinitions.map((track) => `${track.id}(${clipsByTrack.get(track.id)?.length ?? 0})`).join(" ")
    : "none";

  return {
    result: [
      `Duration: ${roundSeconds(totalDuration)}s | Clips: ${nextConfig.clips.length} | Tracks: ${trackSummary}`,
      `Longest: ${longest ? `${longest.id} ${roundSeconds(longest.duration)}s` : "none"} | Shortest: ${
        shortest ? `${shortest.id} ${roundSeconds(shortest.duration)}s` : "none"
      }`,
      `Gaps: ${gapCount} | Overlaps: ${overlapCount}`,
    ].join("\n"),
  };
}

export function findIssues(config: TimelineConfig, registry: AssetRegistry): TimelineToolResult {
  const issues: string[] = [];
  const clipsByTrack = new Map<string, TimelineClip[]>();

  for (const clip of config.clips) {
    const currentTrackClips = clipsByTrack.get(clip.track) ?? [];
    currentTrackClips.push(clip);
    clipsByTrack.set(clip.track, currentTrackClips);

    const assetDuration = getAssetDuration(registry, clip.asset);
    const clipSourceEnd = typeof clip.to === "number"
      ? clip.to
      : typeof clip.hold === "number"
        ? clip.hold
        : assetDuration ?? null;

    if (assetDuration !== null && typeof clipSourceEnd === "number" && clipSourceEnd > assetDuration + 0.0001) {
      issues.push(
        `Clip ${clip.id} exceeds asset duration (${roundSeconds(clipSourceEnd)}s > ${roundSeconds(assetDuration)}s).`,
      );
    }
  }

  for (const [trackId, trackClips] of clipsByTrack.entries()) {
    const sortedClips = [...trackClips].sort((left, right) => left.at - right.at);

    for (let index = 1; index < sortedClips.length; index += 1) {
      const previousClip = sortedClips[index - 1];
      const currentClip = sortedClips[index];
      const previousEnd = previousClip.at + getClipTimelineDuration(previousClip, registry);

      if (currentClip.at - previousEnd > 0.01) {
        issues.push(
          `Gap on track ${trackId} between ${previousClip.id} and ${currentClip.id}: ${roundSeconds(currentClip.at - previousEnd)}s.`,
        );
      }

      if (previousEnd - currentClip.at > 0.01) {
        issues.push(
          `Overlap on track ${trackId} between ${previousClip.id} and ${currentClip.id}: ${roundSeconds(previousEnd - currentClip.at)}s.`,
        );
      }
    }
  }

  // Mid-sentence cut detection depends on transcript data that the current timeline provider does not expose.
  return {
    result: issues.length > 0 ? issues.join("\n") : "No timeline issues found.",
  };
}

export function setTextContent(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { clipId?: string; text?: string },
): TimelineToolResult {
  if (typeof args.clipId !== "string" || typeof args.text !== "string") {
    return { result: "set_text requires clipId and text." };
  }

  const idx = getClipIndex(config, args.clipId);
  if (idx === -1) return { result: `Clip ${args.clipId} was not found.` };
  const clip = config.clips[idx];
  if (clip.clipType !== "text") return { result: `Clip ${args.clipId} is not a text clip.` };

  const nextConfig = cloneConfig(config);
  nextConfig.clips[idx] = {
    ...nextConfig.clips[idx],
    text: { ...nextConfig.clips[idx].text, content: args.text },
  };

  return { config: nextConfig, result: `Updated text on ${args.clipId} to "${args.text}".` };
}

export function duplicateClip(
  config: TimelineConfig,
  registry: AssetRegistry,
  args: { clipId?: string; count?: number },
): TimelineToolResult {
  if (typeof args.clipId !== "string") return { result: "duplicate requires clipId." };

  const sourceClip = config.clips.find((c) => c.id === args.clipId);
  if (!sourceClip) return { result: `Clip ${args.clipId} was not found.` };

  const count = typeof args.count === "number" ? Math.max(1, Math.round(args.count)) : 1;
  const duration = getClipTimelineDuration(sourceClip, registry);

  const nextConfig = cloneConfig(config);
  const newIds: string[] = [];
  for (let i = 0; i < count; i++) {
    const id = `clip-${crypto.randomUUID().slice(0, 6)}`;
    newIds.push(id);
    nextConfig.clips.push({
      ...sourceClip,
      id,
      at: roundSeconds(sourceClip.at + duration * (i + 1)),
    });
  }

  return {
    config: nextConfig,
    result: `Duplicated ${args.clipId} ${count}x. New clips: ${newIds.join(", ")}.`,
  };
}

export function batchAddText(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { track?: string; startAt?: number; interval?: number; duration?: number; count?: number; text?: string },
): TimelineToolResult {
  const track = args.track;
  const startAt = typeof args.startAt === "number" ? args.startAt : 0;
  const interval = typeof args.interval === "number" ? args.interval : 0.1;
  const duration = typeof args.duration === "number" ? args.duration : 0.1;
  const count = typeof args.count === "number" ? args.count : 10;
  const text = typeof args.text === "string" ? args.text : "TEXT";

  if (!track) return { result: "batch_add_text requires track." };
  if (count <= 0 || count > 200) return { result: "count must be 1-200." };
  if (duration <= 0) return { result: "duration must be > 0." };

  const tracks = getTrackDefinitions(config);
  if (tracks.length > 0 && !tracks.some((t) => t.id === track)) {
    return { result: `Track ${track} does not exist.` };
  }

  const nextConfig = cloneConfig(config);
  const ids: string[] = [];
  for (let i = 0; i < count; i++) {
    const id = `clip-${crypto.randomUUID().slice(0, 6)}`;
    ids.push(id);
    nextConfig.clips.push({
      id,
      at: roundSeconds(startAt + interval * i),
      track,
      clipType: "text",
      hold: roundSeconds(duration),
      text: { content: text },
    });
  }

  return {
    config: nextConfig,
    result: `Added ${count} text clips on ${track} from ${startAt}s, ${interval}s apart, ${duration}s each.`,
  };
}

// Sprint 4 (SD-018): three new ops for themed-clip / theme editing.
// Each delegates to @banodoco/timeline-ops and renders a result string.

export function setClipParams(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { clipId?: string; params?: unknown },
): TimelineToolResult {
  if (typeof args.clipId !== "string" || args.params === undefined || args.params === null
      || typeof args.params !== "object" || Array.isArray(args.params)) {
    return { result: "set_params requires clipId and a params object." };
  }
  const opResult = opsSetClipParams(
    config as unknown as TimelineConfigT,
    args.clipId,
    args.params as Record<string, unknown>,
  );
  if (!opResult.changed) {
    if (opResult.detail?.reason === "not_found") {
      return { result: `Clip ${args.clipId} was not found.` };
    }
    if (opResult.detail?.reason === "invalid_value") {
      return { result: "set_params requires clipId and a params object." };
    }
    if (opResult.detail?.reason === "empty_patch") {
      return { result: `set_params received an empty params object for clip ${args.clipId}.` };
    }
  }
  const appliedKeys = (opResult.detail?.appliedKeys as string[] | undefined) ?? Object.keys(args.params as Record<string, unknown>);
  return {
    config: opResult.config as unknown as TimelineConfig,
    result: `Set params on clip ${args.clipId}: ${appliedKeys.join(", ")}.`,
  };
}

export function setTheme(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { themeId?: string },
): TimelineToolResult {
  if (typeof args.themeId !== "string") {
    return { result: "set_theme requires themeId." };
  }
  const opResult = opsSetTimelineTheme(config as unknown as TimelineConfigT, args.themeId);
  if (!opResult.changed) {
    if (opResult.detail?.reason === "invalid_value") {
      return { result: "set_theme requires a non-empty themeId." };
    }
    // Theme already matches; return identity update so loop can no-op.
    return { result: `Theme is already ${args.themeId}.` };
  }
  const previous = opResult.detail?.previousTheme as string | undefined;
  return {
    config: opResult.config as unknown as TimelineConfig,
    result: `Switched theme from ${previous ?? "unset"} to ${args.themeId}. (Note: existing themed clips referencing the old theme's clipType may need remapping.)`,
  };
}

export function setThemeOverrides(
  config: TimelineConfig,
  _registry: AssetRegistry,
  args: { overrides?: unknown },
): TimelineToolResult {
  if (args.overrides === undefined || args.overrides === null
      || typeof args.overrides !== "object" || Array.isArray(args.overrides)) {
    return { result: "set_theme_overrides requires an overrides object." };
  }
  const opResult = opsSetThemeOverrides(
    config as unknown as TimelineConfigT,
    args.overrides as Record<string, unknown>,
  );
  if (!opResult.changed) {
    if (opResult.detail?.reason === "invalid_value") {
      return { result: "set_theme_overrides requires an overrides object." };
    }
    if (opResult.detail?.reason === "empty_patch") {
      return { result: "set_theme_overrides received an empty overrides object." };
    }
  }
  const appliedKeys = (opResult.detail?.appliedKeys as string[] | undefined) ?? Object.keys(args.overrides as Record<string, unknown>);
  return {
    config: opResult.config as unknown as TimelineConfig,
    result: `Updated theme_overrides keys: ${appliedKeys.join(", ")}.`,
  };
}

export const timelineTools = {
  add_media_clip: addMediaClip,
  add_text_clip: addTextClip,
  delete_clip: deleteClip,
  duplicate_clip: duplicateClip,
  find_issues: findIssues,
  move_clip: moveClip,
  query_timeline: queryTimeline,
  set_clip_property: setClipProperty,
  set_params: setClipParams,
  set_text_content: setTextContent,
  set_theme: setTheme,
  set_theme_overrides: setThemeOverrides,
  split_clip: splitClip,
  swap_clip_asset: swapClipAsset,
  trim_clip: trimClip,
  view_timeline: viewTimeline,
};

export const handlers: Record<string, ToolHandler> = {
  add_media_clip: (args, ctx) => addMediaClip(ctx.config, ctx.registry, args),
  add_text_clip: (args, ctx) => addTextClip(ctx.config, ctx.registry, args),
  delete_clip: (args, ctx) => deleteClip(ctx.config, ctx.registry, args),
  duplicate_clip: (args, ctx) => duplicateClip(ctx.config, ctx.registry, args),
  find_issues: (_args, ctx) => findIssues(ctx.config, ctx.registry),
  move_clip: (args, ctx) => moveClip(ctx.config, ctx.registry, args),
  query_timeline: (_args, ctx) => queryTimeline(ctx.config, ctx.registry),
  set_clip_property: (args, ctx) => setClipProperty(ctx.config, ctx.registry, args),
  set_params: (args, ctx) => setClipParams(ctx.config, ctx.registry, args),
  set_text_content: (args, ctx) => setTextContent(ctx.config, ctx.registry, args),
  set_theme: (args, ctx) => setTheme(ctx.config, ctx.registry, args),
  set_theme_overrides: (args, ctx) => setThemeOverrides(ctx.config, ctx.registry, args),
  split_clip: (args, ctx) => splitClip(ctx.config, ctx.registry, args),
  swap_clip_asset: (args, ctx) => swapClipAsset(ctx.config, ctx.registry, args),
  trim_clip: (args, ctx) => trimClip(ctx.config, ctx.registry, args),
  view_timeline: (_args, ctx) => viewTimeline(ctx.config, ctx.registry, ctx.shotNamesById),
};
