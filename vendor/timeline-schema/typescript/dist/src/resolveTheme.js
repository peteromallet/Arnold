/**
 * Deep-merge `overlay` onto `base` for theme blocks.
 *
 * Top-level keys (visual, generation, voice, audio, pacing) merge one level
 * deep. Nested dicts inside (e.g. visual.canvas) merge key-by-key. Lists such
 * as generation.references / generation.assets are replaced wholesale.
 *
 * Port of `tools/timeline.py:622-651` (_deep_merge_theme).
 */
export function deepMergeTheme(base, overlay) {
    const result = { ...base };
    for (const [key, value] of Object.entries(overlay)) {
        const baseValue = result[key];
        if (isPlainObject(baseValue) && isPlainObject(value)) {
            const merged = { ...baseValue };
            for (const [subKey, subValue] of Object.entries(value)) {
                const innerBase = merged[subKey];
                if (isPlainObject(innerBase) && isPlainObject(subValue)) {
                    merged[subKey] = { ...innerBase, ...subValue };
                }
                else {
                    merged[subKey] = subValue;
                }
            }
            result[key] = merged;
        }
        else {
            result[key] = value;
        }
    }
    return result;
}
/**
 * Merge per-clip generation atop the resolved theme.generation block.
 * Per-clip keys win on conflict; lists are replaced wholesale.
 *
 * Port of `tools/timeline.py:605-619` (merge_generation).
 */
export function mergeGeneration(themeGeneration, perClip) {
    const merged = {};
    if (isPlainObject(themeGeneration))
        Object.assign(merged, themeGeneration);
    if (isPlainObject(perClip))
        Object.assign(merged, perClip);
    return merged;
}
/**
 * Resolve the merged theme view for a timeline.
 *
 * Port of `tools/timeline.py:654-673` (resolve_timeline_theme), but takes a
 * pre-loaded theme registry instead of reading from disk so it works in both
 * Node (fs-loaded) and browser (bundled) contexts.
 */
export function resolveTheme(timeline, registry) {
    const slug = timeline.theme;
    if (typeof slug !== "string" || slug.length === 0) {
        throw new Error("Timeline.theme must be a non-empty slug");
    }
    const base = registry[slug];
    if (!base || typeof base !== "object") {
        throw new Error(`Theme ${JSON.stringify(slug)} not found in registry`);
    }
    const overrides = timeline.theme_overrides;
    if (isPlainObject(overrides) && Object.keys(overrides).length > 0) {
        return deepMergeTheme(base, overrides);
    }
    return { ...base };
}
function isPlainObject(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
//# sourceMappingURL=resolveTheme.js.map