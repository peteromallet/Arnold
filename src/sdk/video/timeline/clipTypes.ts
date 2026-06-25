/**
 * Canonical built-in clip type constants and derived type.
 *
 * Host code and extensions consume these bindings from the SDK so that
 * identity-sensitive values resolve against a single source of truth.
 *
 * @publicContract
 */

/**
 * Ordered list of built-in clip types recognized by the editor.
 *
 * - `media` — asset-backed video or audio clip
 * - `hold` — visual still or background hold clip
 * - `text` — inline-editable text overlay clip
 * - `effect-layer` — continuous effect layer applied over lower visual tracks
 * - `automation` — host-owned automation clip for keyframe curve overrides
 */
export const BUILTIN_CLIP_TYPES = ['media', 'hold', 'text', 'effect-layer', 'automation'] as const;

/** Narrow string union of the known built-in clip type identifiers. */
export type BuiltinClipType = (typeof BUILTIN_CLIP_TYPES)[number];
