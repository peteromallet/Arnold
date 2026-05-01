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

const parseJson = (text: string): unknown | null => {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

const extractFencedJson = (text: string): string | null => {
  const match = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  return match?.[1]?.trim() ?? null;
};

const extractBalancedJson = (text: string): string | null => {
  for (let start = 0; start < text.length; start += 1) {
    const firstChar = text[start];
    if (firstChar !== "{" && firstChar !== "[") {
      continue;
    }

    const expectedClosers: string[] = [];
    let inString = false;
    let escaping = false;

    for (let index = start; index < text.length; index += 1) {
      const char = text[index];

      if (inString) {
        if (escaping) {
          escaping = false;
        } else if (char === "\\") {
          escaping = true;
        } else if (char === "\"") {
          inString = false;
        }
        continue;
      }

      if (char === "\"") {
        inString = true;
        continue;
      }

      if (char === "{") {
        expectedClosers.push("}");
        continue;
      }

      if (char === "[") {
        expectedClosers.push("]");
        continue;
      }

      const expectedCloser = expectedClosers[expectedClosers.length - 1];
      if ((char === "}" || char === "]") && char !== expectedCloser) {
        break;
      }

      if (char === expectedCloser) {
        expectedClosers.pop();
        if (expectedClosers.length === 0) {
          return text.slice(start, index + 1);
        }
      }
    }
  }

  return null;
};

const parseModelJson = (content: string): unknown => {
  const candidates = [
    stripMarkdownFences(content),
    extractFencedJson(content),
    extractBalancedJson(content),
  ].filter((candidate): candidate is string => Boolean(candidate?.trim()));

  for (const candidate of candidates) {
    const parsed = parseJson(candidate);
    if (parsed !== null) {
      return parsed;
    }
  }

  throw new Error("Model response did not contain valid sequence JSON.");
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
- Do not include analysis, explanations, Markdown, or text before or after the JSON.
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
  const parsed = parseModelJson(content);
  if (Array.isArray(parsed)) {
    return parsed;
  }
  if (parsed && typeof parsed === "object" && Array.isArray((parsed as { drafts?: unknown }).drafts)) {
    return (parsed as { drafts: unknown[] }).drafts;
  }
  throw new Error("Model response must be a JSON array or an object with drafts.");
};
