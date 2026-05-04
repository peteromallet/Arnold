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
/**
 * Insert a clip into the timeline. `position`, when provided, is the
 * destination index in the clips array; otherwise the clip is appended.
 *
 * Out-of-range positions are clamped to [0, clips.length].
 */
export declare function addClip(timeline: TimelineConfigT, clip: TimelineClipT, position?: number): OpResult;
export declare function removeClip(timeline: TimelineConfigT, clipId: string): OpResult;
/**
 * Reposition a clip on its track. `newPosition` is the timeline start time
 * in seconds (the `at` field), matching the existing
 * `ai-timeline-agent/tools/timeline.ts moveClip` handler. Naming
 * preserved per Sprint 3 brief: "newPosition" matches the signature listed
 * in the brief.
 */
export declare function moveClip(timeline: TimelineConfigT, clipId: string, newPosition: number): OpResult;
declare const MUTABLE_CLIP_PROPERTIES: readonly ["volume", "speed", "opacity", "x", "y", "width", "height"];
export type MutableClipProperty = (typeof MUTABLE_CLIP_PROPERTIES)[number];
export declare function isMutableClipProperty(name: string): name is MutableClipProperty;
/**
 * Set a numeric mutable property on a clip. Mirrors the
 * `set_clip_property` agent tool's allowlist exactly so behavior stays
 * byte-equivalent through the extraction.
 */
export declare function setClipProperty(timeline: TimelineConfigT, clipId: string, propertyName: string, value: number): OpResult;
/**
 * Set timeline start (`at`) and optionally duration for a clip.
 *
 * `duration` is the desired timeline duration in seconds. When the clip
 * holds an asset (`from` + `to`), duration adjusts `to` (clamped to
 * `from + duration`). When the clip is a hold/text type with `hold`,
 * duration adjusts `hold`. If neither shape is in play and `duration` is
 * provided, we set `hold` to the requested duration.
 */
export declare function setClipTime(timeline: TimelineConfigT, clipId: string, startTime: number, duration?: number): OpResult;
declare const MUTABLE_TIMELINE_PROPERTIES: readonly ["theme", "theme_overrides", "generation_defaults", "output", "tracks", "pinnedShotGroups"];
export type MutableTimelineProperty = (typeof MUTABLE_TIMELINE_PROPERTIES)[number];
export declare function isMutableTimelineProperty(name: string): name is MutableTimelineProperty;
/**
 * Set a top-level property on the timeline (theme slug, theme_overrides,
 * generation_defaults, output, tracks, pinnedShotGroups). The clips array
 * is intentionally NOT mutable through this op — use addClip/removeClip
 * for that.
 */
export declare function setTimelineProperty(timeline: TimelineConfigT, propertyName: string, value: unknown): OpResult;
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
export declare function setClipParams(timeline: TimelineConfigT, clipId: string, paramsPatch: Record<string, unknown>): OpResult;
/**
 * Sprint 4 (SD-018): set the active theme slug on a timeline.
 *
 * Edge cases:
 *   - empty / non-string themeId → `invalid_value`, unchanged.
 */
export declare function setTimelineTheme(timeline: TimelineConfigT, themeId: string): OpResult;
/**
 * Sprint 4 (SD-018): deep-merge a `theme_overrides` patch onto the
 * timeline. `null` patch values clear that key (at any nesting depth).
 *
 * Edge cases:
 *   - non-object patch → `invalid_value`, unchanged.
 *   - empty patch → changed: false.
 *   - merging onto undefined `theme_overrides` initializes it.
 */
export declare function setThemeOverrides(timeline: TimelineConfigT, overridesPatch: Record<string, unknown>): OpResult;
export {};
//# sourceMappingURL=ops.d.ts.map