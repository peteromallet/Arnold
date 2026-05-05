// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import {
  enforceRateLimit,
  RATE_LIMITS,
} from "../_shared/rateLimit.ts";
import { bootstrapEdgeHandler, NO_SESSION_RUNTIME_OPTIONS } from "../_shared/edgeHandler.ts";
import { jsonResponse } from "../_shared/http.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import {
  buildGenerateSequenceMessages,
  extractClassifierPreamble,
  extractSequenceDrafts,
} from "./templates.ts";
import {
  TRUSTED_SEQUENCE_CLIP_TYPES,
  validateSequenceDraft,
  type SequenceDraftValidationError,
} from "./sequence-validation.ts";

const ANTHROPIC_MODEL = "claude-opus-4-6";
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_TIMEOUT_MS = 150_000;

interface LLMResponse {
  content: string;
  model: string;
}

const buildRepairMessages = (
  originalContent: string,
  allowedClipTypes: readonly string[],
  allowedAssetKeys: readonly string[],
): Array<{ role: string; content: string }> => [
  {
    role: "system",
    content: [
      "You repair malformed Reigh sequence draft responses.",
      "Return JSON only, with shape {\"drafts\":[{\"clipType\":string,\"hold\":number,\"params\":object}]}.",
      "Do not include analysis, explanations, Markdown, or text before or after the JSON.",
      "Use only the allowed clipType values and allowed asset keys.",
    ].join("\n"),
  },
  {
    role: "user",
    content: JSON.stringify({
      malformed_response: originalContent.slice(0, 8000),
      allowed_clip_types: allowedClipTypes,
      allowed_asset_keys: allowedAssetKeys,
    }),
  },
];

const asStringArray = (value: unknown): string[] => {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
};

const collectAssetKeys = (...sources: unknown[]): string[] => {
  const keys = new Set<string>();
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const item of source) {
      if (typeof item === "string" && item.trim()) {
        keys.add(item);
      } else if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        for (const field of ["assetKey", "asset_key", "asset", "id", "key"]) {
          const value = record[field];
          if (typeof value === "string" && value.trim()) {
            keys.add(value);
          }
        }
      }
    }
  }
  return [...keys];
};

async function callAnthropic(
  messages: Array<{ role: string; content: string }>,
  logger: { info: (msg: string) => void },
): Promise<LLMResponse> {
  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("[ai-generate-sequence] Missing ANTHROPIC_API_KEY");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANTHROPIC_TIMEOUT_MS);
  const systemContent = messages.find((message) => message.role === "system")?.content;
  const chatMessages = messages.filter((message) => message.role !== "system");

  try {
    const startedAt = Date.now();
    logger.info(`[AI-GENERATE-SEQUENCE] Anthropic streaming request: model=${ANTHROPIC_MODEL}`);
    const response = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: 4096,
        temperature: 0.3,
        ...(systemContent ? { system: systemContent } : {}),
        messages: chatMessages,
        stream: true,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`Anthropic ${response.status}: ${text.slice(0, 500)}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let content = "";
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        try {
          const chunk = JSON.parse(data);
          if (chunk.type === "content_block_delta" && chunk.delta?.type === "text_delta") {
            content += chunk.delta.text;
          }
        } catch {
          // Ignore malformed SSE chunks.
        }
      }
    }
    content = content.trim();
    logger.info(`[AI-GENERATE-SEQUENCE] Anthropic response in ${Date.now() - startedAt}ms, model=${ANTHROPIC_MODEL}, length=${content.length}`);
    return { content, model: ANTHROPIC_MODEL };
  } finally {
    clearTimeout(timeout);
  }
}

serve(async (req) => {
  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "ai-generate-sequence",
    logPrefix: "[AI-GENERATE-SEQUENCE]",
    parseBody: "strict",
    auth: {
      required: true,
      options: { allowJwtUserAuth: true },
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  });
  if (!bootstrap.ok) {
    return bootstrap.response;
  }

  const { supabaseAdmin, logger, auth, body } = bootstrap.value;
  if (!auth?.userId) {
    return jsonResponse({ error: "Authentication failed" }, 401);
  }

  const rateLimitDenied = await enforceRateLimit({
    supabaseAdmin,
    functionName: "ai-generate-sequence",
    userId: auth.userId,
    config: RATE_LIMITS.expensive,
    logger,
    logPrefix: "[AI-GENERATE-SEQUENCE]",
    responses: {
      serviceUnavailable: () => jsonResponse({ error: "Rate limit service unavailable" }, 503),
    },
  });
  if (rateLimitDenied) {
    return rateLimitDenied;
  }

  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  if (!prompt) {
    return jsonResponse({ error: "prompt is required" }, 400);
  }

  const trustedClipTypes = [...TRUSTED_SEQUENCE_CLIP_TYPES];
  const requestedClipTypes = asStringArray(body.allowed_clip_types);
  const allowedClipTypes = requestedClipTypes.length > 0
    ? requestedClipTypes.filter((clipType) => (trustedClipTypes as readonly string[]).includes(clipType))
    : trustedClipTypes;
  if (allowedClipTypes.length === 0) {
    return jsonResponse({ error: "allowed_clip_types contains no trusted sequence types" }, 400);
  }

  const allowedAssetKeys = collectAssetKeys(
    body.allowed_assets,
    body.selected_clips,
    body.attached_clips,
  );

  try {
    const { systemMsg, userMsg } = buildGenerateSequenceMessages({
      prompt,
      mode: body.mode === "edit" ? "edit" : "generate",
      editContext: body.edit_context,
      timeline: body.timeline,
      selectedClips: body.selected_clips,
      attachedClips: body.attached_clips,
      animationIntent: body.animation_intent,
      allowedClipTypes,
      allowedAssetKeys,
      theme: body.theme,
      themeOverrides: body.theme_overrides,
    });

    logger.info(`[AI-GENERATE-SEQUENCE] create → ${ANTHROPIC_MODEL} (Anthropic)`);
    await logger.flush();
    const llmResponse = await callAnthropic([
      { role: "system", content: systemMsg },
      { role: "user", content: userMsg },
    ], logger);

    // Unified-UX classifier preamble: if the model decides this request
    // requires a custom sequence component instead of a JSON draft edit,
    // it emits `// PATH: code` + `// REASON: …` and no drafts. Surface
    // the classifier verdict to the front-end (sequenceGenerationService
    // dispatches the follow-up call to ai-generate-sequence-component).
    const classifier = extractClassifierPreamble(llmResponse.content);
    if (classifier?.path === "code") {
      logger.info(`[AI-GENERATE-SEQUENCE] classifier path=code, reason=${classifier.reason.slice(0, 200)}`);
      await logger.flush();
      return jsonResponse({
        classifier: { path: "code", reason: classifier.reason },
        drafts: [],
        invalid_drafts: [],
        model: llmResponse.model,
      });
    }
    // For path=json (or legacy responses without a preamble), strip the
    // preamble before parsing drafts so the JSON parser sees clean input.
    const draftsContent = classifier?.rest ?? llmResponse.content;

    let rawDrafts: unknown[];
    try {
      rawDrafts = extractSequenceDrafts(draftsContent);
    } catch (parseErr: unknown) {
      const parseMsg = parseErr instanceof Error ? parseErr.message : String(parseErr);
      logger.info(`[AI-GENERATE-SEQUENCE] extraction failed: ${parseMsg}; retrying JSON repair`);
      await logger.flush();
      const repairResponse = await callAnthropic(
        buildRepairMessages(llmResponse.content, allowedClipTypes, allowedAssetKeys),
        logger,
      );
      try {
        rawDrafts = extractSequenceDrafts(repairResponse.content);
        llmResponse.content = repairResponse.content;
      } catch (repairErr: unknown) {
        const repairMsg = repairErr instanceof Error ? repairErr.message : String(repairErr);
        logger.info(`[AI-GENERATE-SEQUENCE] repair extraction failed: ${repairMsg}`);
        await logger.flush();
        return jsonResponse({ error: repairMsg }, 422);
      }
    }

    const drafts = [];
    const invalidDrafts: Array<{ index: number; errors: SequenceDraftValidationError[] }> = [];
    rawDrafts.forEach((rawDraft, index) => {
      const validation = validateSequenceDraft(rawDraft, {
        allowedClipTypes,
        allowedAssetKeys,
      });
      if (validation.ok) {
        drafts.push(validation.draft);
      } else {
        invalidDrafts.push({ index, errors: validation.errors });
      }
    });

    logger.info(`[AI-GENERATE-SEQUENCE] validated drafts=${drafts.length}, invalid=${invalidDrafts.length}`);
    await logger.flush();
    return jsonResponse({
      drafts,
      invalid_drafts: invalidDrafts,
      model: llmResponse.model,
      ...(classifier ? { classifier: { path: classifier.path, reason: classifier.reason } } : {}),
    });
  } catch (err: unknown) {
    const message = toErrorMessage(err);
    console.error("[ai-generate-sequence] Error generating sequence:", message);
    logger.info(`[AI-GENERATE-SEQUENCE] error: ${message}`);
    await logger.flush();
    return jsonResponse({ error: "Internal server error", details: message }, 500);
  }
});
