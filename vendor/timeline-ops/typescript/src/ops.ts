/**
 * Pure surgical CRUD operations on TimelineConfig.
 *
 * No I/O, no async, no globals. Each op takes a TimelineConfig and returns
 * a new TimelineConfig (deep-cloned). Lookup-misses (e.g. unknown clipId)
 * return the input cloned unchanged so callers can detect the no-op via
 * { changed: false }.
 *
 * Why a result envelope? The Reigh agent wraps these ops in handlers that
 * already render their own user-facing strings. Returning a structured
 * { config, changed, message } shape lets the existing handler keep its
 * exact output text after the move (snapshot-byte-equivalent LLM tool
 * schema), without leaking string-formatting concerns into the pure layer.
 */

import type { TimelineClipT, TimelineConfigT } from "@banodoco/timeline-schema";

export type OpResult = {
  config: TimelineConfigT;
  changed: boolean;
  /**
   * Optional structured detail. Callers attach their own user-facing strings;
   * this is here so handlers can render "moved from X to Y" without a second
   * pass over the timeline.
   */
  detail?: Record<string, unknown>;
};

function clone<T>(value: T): T {
  return structuredClone(value);
}

function roundSeconds(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function findClipIndex(timeline: TimelineConfigT, clipId: string): number {
  return timeline.clips.findIndex((clip) => clip.id === clipId);
}

/**
 * Insert a clip into the timeline. `position`, when provided, is the
 * destination index in the clips array; otherwise the clip is appended.
 *
 * Out-of-range positions are clamped to [0, clips.length].
 */
export function addClip(
  timeline: TimelineConfigT,
  clip: TimelineClipT,
  position?: number,
): OpResult {
  const next = clone(timeline);
  const insertedClip = clone(clip);
  const length = next.clips.length;
  let index: number;
  if (position === undefined || Number.isNaN(position)) {
    index = length;
  } else {
    index = Math.max(0, Math.min(length, Math.floor(position)));
  }
  next.clips.splice(index, 0, insertedClip);
  return { config: next, changed: true, detail: { index, clipId: insertedClip.id } };
}

export function removeClip(timeline: TimelineConfigT, clipId: string): OpResult {
  const idx = findClipIndex(timeline, clipId);
  if (idx < 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "not_found" } };
  }
  const next = clone(timeline);
  const [removed] = next.clips.splice(idx, 1);
  return { config: next, changed: true, detail: { removedTrack: removed?.track } };
}

/**
 * Reposition a clip on its track. `newPosition` is the timeline start time
 * in seconds (the `at` field), matching the existing
 * `ai-timeline-agent/tools/timeline.ts moveClip` handler. Naming
 * preserved per Sprint 3 brief: "newPosition" matches the signature listed
 * in the brief.
 */
export function moveClip(
  timeline: TimelineConfigT,
  clipId: string,
  newPosition: number,
): OpResult {
  const idx = findClipIndex(timeline, clipId);
  if (idx < 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "not_found" } };
  }
  const next = clone(timeline);
  const previousAt = next.clips[idx].at;
  next.clips[idx].at = roundSeconds(newPosition);
  return {
    config: next,
    changed: previousAt !== next.clips[idx].at,
    detail: { previousAt, nextAt: next.clips[idx].at },
  };
}

const MUTABLE_CLIP_PROPERTIES = [
  "volume",
  "speed",
  "opacity",
  "x",
  "y",
  "width",
  "height",
] as const;

export type MutableClipProperty = (typeof MUTABLE_CLIP_PROPERTIES)[number];

export function isMutableClipProperty(name: string): name is MutableClipProperty {
  return (MUTABLE_CLIP_PROPERTIES as readonly string[]).includes(name);
}

/**
 * Set a numeric mutable property on a clip. Mirrors the
 * `set_clip_property` agent tool's allowlist exactly so behavior stays
 * byte-equivalent through the extraction.
 */
export function setClipProperty(
  timeline: TimelineConfigT,
  clipId: string,
  propertyName: string,
  value: number,
): OpResult {
  if (!isMutableClipProperty(propertyName)) {
    return {
      config: clone(timeline),
      changed: false,
      detail: { reason: "property_not_allowed", propertyName, allowed: [...MUTABLE_CLIP_PROPERTIES] },
    };
  }
  const idx = findClipIndex(timeline, clipId);
  if (idx < 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "not_found" } };
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_value" } };
  }
  const next = clone(timeline);
  const clip = next.clips[idx] as unknown as Record<string, unknown>;
  const previousValue = clip[propertyName];
  clip[propertyName] = value;
  return {
    config: next,
    changed: previousValue !== value,
    detail: { previousValue, nextValue: value, propertyName },
  };
}

/**
 * Set timeline start (`at`) and optionally duration for a clip.
 *
 * `duration` is the desired timeline duration in seconds. When the clip
 * holds an asset (`from` + `to`), duration adjusts `to` (clamped to
 * `from + duration`). When the clip is a hold/text type with `hold`,
 * duration adjusts `hold`. If neither shape is in play and `duration` is
 * provided, we set `hold` to the requested duration.
 */
export function setClipTime(
  timeline: TimelineConfigT,
  clipId: string,
  startTime: number,
  duration?: number,
): OpResult {
  const idx = findClipIndex(timeline, clipId);
  if (idx < 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "not_found" } };
  }
  if (typeof startTime !== "number" || !Number.isFinite(startTime)) {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_start_time" } };
  }
  if (duration !== undefined && (typeof duration !== "number" || !Number.isFinite(duration) || duration <= 0)) {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_duration" } };
  }
  const next = clone(timeline);
  const clip = next.clips[idx];
  const previousAt = clip.at;
  clip.at = roundSeconds(startTime);

  let durationApplied = false;
  if (duration !== undefined) {
    const rounded = roundSeconds(duration);
    if (typeof clip.from === "number" && typeof clip.to === "number") {
      clip.to = roundSeconds(clip.from + rounded);
      durationApplied = true;
    } else if (typeof clip.hold === "number") {
      clip.hold = rounded;
      durationApplied = true;
    } else {
      clip.hold = rounded;
      durationApplied = true;
    }
  }

  return {
    config: next,
    changed: previousAt !== clip.at || durationApplied,
    detail: { previousAt, nextAt: clip.at, durationApplied },
  };
}

const MUTABLE_TIMELINE_PROPERTIES = [
  "theme",
  "theme_overrides",
  "generation_defaults",
  "output",
  "tracks",
  "pinnedShotGroups",
] as const;

export type MutableTimelineProperty = (typeof MUTABLE_TIMELINE_PROPERTIES)[number];

export function isMutableTimelineProperty(name: string): name is MutableTimelineProperty {
  return (MUTABLE_TIMELINE_PROPERTIES as readonly string[]).includes(name);
}

/**
 * Set a top-level property on the timeline (theme slug, theme_overrides,
 * generation_defaults, output, tracks, pinnedShotGroups). The clips array
 * is intentionally NOT mutable through this op — use addClip/removeClip
 * for that.
 */
export function setTimelineProperty(
  timeline: TimelineConfigT,
  propertyName: string,
  value: unknown,
): OpResult {
  if (!isMutableTimelineProperty(propertyName)) {
    return {
      config: clone(timeline),
      changed: false,
      detail: {
        reason: "property_not_allowed",
        propertyName,
        allowed: [...MUTABLE_TIMELINE_PROPERTIES],
      },
    };
  }
  const next = clone(timeline) as unknown as Record<string, unknown>;
  const previousValue = next[propertyName];
  next[propertyName] = value === undefined ? undefined : clone(value);
  return {
    config: next as unknown as TimelineConfigT,
    changed: true,
    detail: { previousValue, propertyName },
  };
}

/**
 * Sprint 4 (SD-018): themed-clip params editor.
 *
 * Shallow-merges `paramsPatch` into `clip.params`. Keys present in the
 * patch with `null` are deleted from the merged params. Keys absent from
 * the patch are preserved. Adds new keys when not already set.
 *
 * Edge cases:
 *   - clipId missing → `not_found`, unchanged.
 *   - paramsPatch not an object → `invalid_value`, unchanged.
 *   - empty patch → unchanged: false.
 */
export function setClipParams(
  timeline: TimelineConfigT,
  clipId: string,
  paramsPatch: Record<string, unknown>,
): OpResult {
  const idx = findClipIndex(timeline, clipId);
  if (idx < 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "not_found" } };
  }
  if (paramsPatch === null || typeof paramsPatch !== "object" || Array.isArray(paramsPatch)) {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_value" } };
  }
  const patchKeys = Object.keys(paramsPatch);
  if (patchKeys.length === 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "empty_patch" } };
  }
  const next = clone(timeline);
  const clip = next.clips[idx] as unknown as Record<string, unknown>;
  const existing = (clip.params && typeof clip.params === "object" && !Array.isArray(clip.params))
    ? (clip.params as Record<string, unknown>)
    : {};
  const merged: Record<string, unknown> = { ...existing };
  const previousValues: Record<string, unknown> = {};
  const appliedKeys: string[] = [];
  for (const key of patchKeys) {
    previousValues[key] = existing[key];
    const value = paramsPatch[key];
    if (value === null) {
      delete merged[key];
    } else {
      merged[key] = clone(value);
    }
    appliedKeys.push(key);
  }
  clip.params = merged;
  return {
    config: next,
    changed: true,
    detail: { previousValues, appliedKeys },
  };
}

/**
 * Sprint 4 (SD-018): set the active theme slug on a timeline.
 *
 * Edge cases:
 *   - empty / non-string themeId → `invalid_value`, unchanged.
 */
export function setTimelineTheme(
  timeline: TimelineConfigT,
  themeId: string,
): OpResult {
  if (typeof themeId !== "string" || themeId.trim() === "") {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_value" } };
  }
  const next = clone(timeline);
  const previousTheme = next.theme;
  next.theme = themeId;
  return {
    config: next,
    changed: previousTheme !== themeId,
    detail: { previousTheme, nextTheme: themeId },
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function deepMergeOverrides(
  base: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const key of Object.keys(patch)) {
    const patchValue = patch[key];
    if (patchValue === null) {
      delete out[key];
      continue;
    }
    const baseValue = out[key];
    if (isPlainObject(patchValue) && isPlainObject(baseValue)) {
      out[key] = deepMergeOverrides(baseValue, patchValue);
    } else {
      out[key] = isPlainObject(patchValue) ? clone(patchValue) : patchValue;
    }
  }
  return out;
}

/**
 * Sprint 4 (SD-018): deep-merge a `theme_overrides` patch onto the
 * timeline. `null` patch values clear that key (at any nesting depth).
 *
 * Edge cases:
 *   - non-object patch → `invalid_value`, unchanged.
 *   - empty patch → changed: false.
 *   - merging onto undefined `theme_overrides` initializes it.
 */
export function setThemeOverrides(
  timeline: TimelineConfigT,
  overridesPatch: Record<string, unknown>,
): OpResult {
  if (!isPlainObject(overridesPatch)) {
    return { config: clone(timeline), changed: false, detail: { reason: "invalid_value" } };
  }
  const patchKeys = Object.keys(overridesPatch);
  if (patchKeys.length === 0) {
    return { config: clone(timeline), changed: false, detail: { reason: "empty_patch" } };
  }
  const next = clone(timeline) as unknown as Record<string, unknown>;
  const previous = isPlainObject(next.theme_overrides) ? (next.theme_overrides as Record<string, unknown>) : {};
  next.theme_overrides = deepMergeOverrides(previous, overridesPatch);
  return {
    config: next as unknown as TimelineConfigT,
    changed: true,
    detail: { appliedKeys: patchKeys },
  };
}
