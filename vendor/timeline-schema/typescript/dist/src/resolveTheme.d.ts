import type { TimelineConfigT, ThemeT } from "./schemas.js";
export type ThemeRegistry = Record<string, ThemeT>;
export type ThemeResolvableTimeline = Pick<TimelineConfigT, "theme_overrides"> & {
    theme: string;
};
/**
 * Deep-merge `overlay` onto `base` for theme blocks.
 *
 * Top-level keys (visual, generation, voice, audio, pacing) merge one level
 * deep. Nested dicts inside (e.g. visual.canvas) merge key-by-key. Lists such
 * as generation.references / generation.assets are replaced wholesale.
 *
 * Port of `tools/timeline.py:622-651` (_deep_merge_theme).
 */
export declare function deepMergeTheme(base: Record<string, unknown>, overlay: Record<string, unknown>): Record<string, unknown>;
/**
 * Merge per-clip generation atop the resolved theme.generation block.
 * Per-clip keys win on conflict; lists are replaced wholesale.
 *
 * Port of `tools/timeline.py:605-619` (merge_generation).
 */
export declare function mergeGeneration(themeGeneration: Record<string, unknown> | null | undefined, perClip: Record<string, unknown> | null | undefined): Record<string, unknown>;
/**
 * Resolve the merged theme view for a timeline.
 *
 * Port of `tools/timeline.py:654-673` (resolve_timeline_theme), but takes a
 * pre-loaded theme registry instead of reading from disk so it works in both
 * Node (fs-loaded) and browser (bundled) contexts.
 */
export declare function resolveTheme(timeline: ThemeResolvableTimeline, registry: ThemeRegistry): Record<string, unknown>;
//# sourceMappingURL=resolveTheme.d.ts.map