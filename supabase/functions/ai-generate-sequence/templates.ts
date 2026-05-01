// deno-lint-ignore-file
import { TRUSTED_SEQUENCE_METADATA } from "./sequence-validation.ts";

export type BuildGenerateSequenceMessagesInput = {
  prompt: string;
  timeline?: unknown;
  selectedClips?: unknown;
  attachedClips?: unknown;
  allowedClipTypes: readonly string[];
  allowedAssetKeys: readonly string[];
  theme?: unknown;
  themeOverrides?: unknown;
};

const stripMarkdownFences = (text: string): string => {
  return text
    .trim()
    .replace(/^\s*```(?:json)?\s*/i, "")
    .replace(/\s*```\s*$/i, "")
    .trim();
};

export const buildGenerateSequenceMessages = (
  input: BuildGenerateSequenceMessagesInput,
): { systemMsg: string; userMsg: string } => {
  const metadata = TRUSTED_SEQUENCE_METADATA
    .filter((entry) => input.allowedClipTypes.includes(entry.clipType))
    .map((entry) => ({
      clipType: entry.clipType,
      hold: entry.hold,
      params: entry.params,
    }));

  const systemMsg = `You generate trusted structured timeline sequence drafts for the Reigh video editor.

Rules:
- Return JSON only, with shape {"drafts":[{"clipType":string,"hold":number,"params":object}]}.
- Use only the supplied clipType values and params.
- Do not generate code, JSX, HTML, imports, scripts, raw URLs, data URLs, blob URLs, entrance, exit, transition, or animation refs.
- Asset-valued params must use only allowed registry asset keys. Do not invent or emit component-facing URL params such as previews.
- Effects are wrappers; sequences are first-class timeline clips.`;

  const userMsg = JSON.stringify({
    prompt: input.prompt,
    trusted_sequence_metadata: metadata,
    allowed_clip_types: input.allowedClipTypes,
    allowed_asset_keys: input.allowedAssetKeys,
    theme: input.theme ?? null,
    theme_overrides: input.themeOverrides ?? null,
    selected_clips: input.selectedClips ?? [],
    attached_clips: input.attachedClips ?? [],
    timeline: input.timeline ?? null,
  });

  return { systemMsg, userMsg };
};

export const extractSequenceDrafts = (content: string): unknown[] => {
  const cleaned = stripMarkdownFences(content);
  const parsed = JSON.parse(cleaned);
  if (Array.isArray(parsed)) {
    return parsed;
  }
  if (parsed && typeof parsed === "object" && Array.isArray((parsed as { drafts?: unknown }).drafts)) {
    return (parsed as { drafts: unknown[] }).drafts;
  }
  throw new Error("Model response must be a JSON array or an object with drafts.");
};
