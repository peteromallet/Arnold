// deno-lint-ignore-file
import { TRUSTED_SEQUENCE_METADATA } from "./sequence-validation.ts";

export type BuildGenerateSequenceMessagesInput = {
  prompt: string;
  mode?: "generate" | "edit";
  editContext?: unknown;
  timeline?: unknown;
  selectedClips?: unknown;
  attachedClips?: unknown;
  animationIntent?: unknown;
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

  const systemMsg = `You generate and edit trusted structured timeline sequence drafts for the Reigh video editor.

CLASSIFIER PREAMBLE (always emit first, on its own two lines, before any JSON):
- Decide whether the user's request can be satisfied by editing the existing
  trusted sequence params (path=json) OR whether it requires a custom
  sequence component implemented in code (path=code).
- The classifier sees the current schema, current params, and the user prompt
  (all already part of this prompt context).
- path=json: the request is "param-tweakable" — slower, faster, vertical
  layout, swap to these images, change a tunable param, etc.
- path=code: the request is structurally impossible in JSON — pulse on
  entry, custom easing curve mid-animation, vignette behind title, any
  visual primitive not covered by the schema.
- Ambiguous? Prefer path=json and let the user follow up with "go deeper
  with code".
- Output format:
    // PATH: json
    // REASON: <brief reason, one sentence>
    {"drafts":[ ... ]}
  OR
    // PATH: code
    // REASON: <brief reason, one sentence>
  (When path=code, emit ONLY the two preamble lines. Do NOT emit JSON drafts.)

Rules (apply when path=json):
- Return JSON only, with shape {"drafts":[{"clipType":string,"hold":number,"params":object}]}.
- Do not include analysis, explanations, Markdown, or text before or after the JSON (the PATH/REASON preamble lines are the only exception).
- Use only the supplied clipType values and params.
- In edit mode, preserve the user's existing sequence unless the edit instruction specifically asks to change that part.
- In edit mode, modify the supplied source draft into an improved draft. Do not ignore it and start over.
- Prefer image-jump for prompts about selected images jumping, moving, cycling, swapping, flashing, or animating without explicit text.
- For image-jump mode, choose one of: jump, snap, gallery, pulse, shuffle. Match the user's motion language; do not always return jump.
- Treat animation_intent as guidance for choosing trusted clip types, timing, asset reuse, and safe params only. It does not authorize code, imports, raw URLs, source/render fields, or arbitrary animation references.
- For image-jump images, emit params.imageAssetKeys with allowed registry asset keys; never emit params.images or raw image URLs.
- Do not force title, caption, label, metric, or CTA fields unless the chosen clipType requires them and the user's request actually asks for text.
- Do not generate code, JSX, HTML, imports, scripts, raw URLs, data URLs, blob URLs, entrance, exit, transition, or animation refs.
- Asset-valued params must use only allowed registry asset keys. Do not invent or emit component-facing URL params such as previews or images.
- Effects are wrappers; sequences are first-class timeline clips.`;

  const userMsg = JSON.stringify({
    mode: input.mode ?? "generate",
    prompt: input.prompt,
    edit_context: input.editContext ?? null,
    trusted_sequence_metadata: metadata,
    allowed_clip_types: input.allowedClipTypes,
    allowed_asset_keys: input.allowedAssetKeys,
    theme: input.theme ?? null,
    theme_overrides: input.themeOverrides ?? null,
    selected_clips: input.selectedClips ?? [],
    attached_clips: input.attachedClips ?? [],
    animation_intent: input.animationIntent ?? null,
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

const PATH_PATTERN = /^\s*\/\/\s*PATH\s*:\s*(json|code)\s*$/im;
const REASON_PATTERN = /^\s*\/\/\s*REASON\s*:\s*(.*)$/im;

export interface SequenceClassifierResult {
  path: "json" | "code";
  reason: string;
  /** The model output with the PATH/REASON preamble stripped (for path=json drafts parsing). */
  rest: string;
}

/**
 * Read the `// PATH: json|code` + `// REASON: …` preamble from a model
 * response. Returns null if no PATH preamble is present (legacy responses
 * without the classifier — caller should fall back to extractSequenceDrafts).
 */
export const extractClassifierPreamble = (
  content: string,
): SequenceClassifierResult | null => {
  const pathMatch = PATH_PATTERN.exec(content);
  if (!pathMatch || pathMatch.index === undefined) return null;

  const path = (pathMatch[1] ?? "").toLowerCase() as "json" | "code";
  const pathLineEnd = (() => {
    const newline = content.indexOf("\n", pathMatch.index);
    return newline === -1 ? content.length : newline + 1;
  })();

  const reasonMatch = REASON_PATTERN.exec(content);
  const reason = reasonMatch?.[1]?.trim() ?? "";
  const reasonLineEnd = reasonMatch && reasonMatch.index !== undefined
    ? (() => {
        const newline = content.indexOf("\n", reasonMatch.index);
        return newline === -1 ? content.length : newline + 1;
      })()
    : pathLineEnd;

  // Strip both preamble lines from the rest so callers can parse the
  // remaining JSON drafts unchanged.
  const stripStart = Math.min(pathMatch.index, reasonMatch?.index ?? pathMatch.index);
  const stripEnd = Math.max(pathLineEnd, reasonLineEnd);
  const rest = (content.slice(0, stripStart) + content.slice(stripEnd)).trim();

  return { path, reason, rest };
};
